/*
 * Telnet option handling. See telnet_proto.h for why this exists.
 */
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <arpa/telnet.h>
#include <stdlib.h>
#include <zlib.h>

#include "merc.h"
#include "telnet_proto.h"

/* Parser states for the input filter. */
#define TS_DATA         0       /* ordinary application bytes           */
#define TS_IAC          1       /* saw IAC                              */
#define TS_NEGOTIATE    2       /* saw IAC WILL/WONT/DO/DONT            */
#define TS_SB_OPTION    3       /* saw IAC SB, reading the option byte   */
#define TS_SB_DATA      4       /* inside subnegotiation payload         */
#define TS_SB_IAC       5       /* saw IAC inside a subnegotiation       */

extern time_t   boot_time_stamp;

/*
 * Raw descriptor writes. Negotiation must not go through write_to_buffer():
 * that path is for player-facing text and performs colour conversion, which
 * would corrupt protocol bytes.
 */
static void telnet_send_raw( DESCRIPTOR_DATA *d, const char *data, size_t length )
{
    if ( d == NULL || d->descriptor < 0 || data == NULL || length == 0 )
        return;

    /*
     * Goes through write_to_descriptor() rather than write() so protocol
     * output is compressed once MCCP is running. It must not go through
     * write_to_buffer(), which is the player-text path and performs colour
     * conversion that would corrupt these bytes.
     */
    write_to_descriptor( d, data, (int)length );
}

/* Bypass compression: used only for the MCCP handshake itself. */
static void telnet_send_uncompressed( DESCRIPTOR_DATA *d, const char *data,
                                      size_t length )
{
    if ( d == NULL || d->descriptor < 0 || data == NULL || length == 0 )
        return;

    write_raw_to_descriptor( d, data, (int)length );
}

#define MCCP_BUFFER_SIZE        8192

/*
 * Begin MCCP2. The acknowledgement sequence has to reach the client
 * uncompressed, because everything after it is deflate output; the stream is
 * therefore only armed once that sequence is on the wire.
 */
static void telnet_start_compression( DESCRIPTOR_DATA *d )
{
    z_stream *stream;
    char ack[5];

    if ( d == NULL || d->out_compress != NULL )
        return;

    stream = calloc( 1, sizeof(*stream) );
    if ( stream == NULL )
        return;

    d->out_compress_buf = malloc( MCCP_BUFFER_SIZE );
    if ( d->out_compress_buf == NULL )
    {
        free( stream );
        return;
    }

    /* Default level: compression here is about bandwidth, not CPU time. */
    if ( deflateInit( stream, Z_DEFAULT_COMPRESSION ) != Z_OK )
    {
        free( d->out_compress_buf );
        d->out_compress_buf = NULL;
        free( stream );
        return;
    }

    ack[0] = (char)(unsigned char)IAC;
    ack[1] = (char)(unsigned char)SB;
    ack[2] = (char)TELOPT_COMPRESS2;
    ack[3] = (char)(unsigned char)IAC;
    ack[4] = (char)(unsigned char)SE;
    telnet_send_uncompressed( d, ack, sizeof(ack) );

    d->out_compress = stream;
}

void telnet_end_compression( DESCRIPTOR_DATA *d )
{
    z_stream *stream;

    if ( d == NULL || d->out_compress == NULL )
        return;

    stream = (z_stream *) d->out_compress;

    /*
     * Clear the pointer first: deflateEnd() must not re-enter the compressed
     * write path, and the socket is going away regardless.
     */
    d->out_compress = NULL;
    deflateEnd( stream );
    free( stream );

    free( d->out_compress_buf );
    d->out_compress_buf = NULL;
}

bool telnet_write_compressed( DESCRIPTOR_DATA *d, const char *txt, int length )
{
    z_stream *stream;
    size_t remaining;

    if ( d == NULL || txt == NULL )
        return true;

    stream = (z_stream *) d->out_compress;
    if ( stream == NULL )
        return write_raw_to_descriptor( d, txt, length );

    remaining = ( length <= 0 ) ? strlen( txt ) : (size_t)length;
    if ( remaining == 0 )
        return true;

    stream->next_in  = (Bytef *) txt;
    stream->avail_in = (uInt) remaining;

    while ( stream->avail_in > 0 )
    {
        stream->next_out  = (Bytef *) d->out_compress_buf;
        stream->avail_out = MCCP_BUFFER_SIZE;

        if ( deflate( stream, Z_SYNC_FLUSH ) != Z_OK )
        {
            /* Stream is unusable; drop back to plain output rather than
             * silently losing the player's session. */
            telnet_end_compression( d );
            return write_raw_to_descriptor( d, txt, length );
        }

        {
            size_t produced = MCCP_BUFFER_SIZE - stream->avail_out;

            if ( produced > 0
            &&   !write_raw_to_descriptor( d, (const char *) d->out_compress_buf,
                                           (int) produced ) )
                return false;
        }
    }

    return true;
}

static void telnet_command( DESCRIPTOR_DATA *d, unsigned char verb,
                            unsigned char option )
{
    char buf[3];

    buf[0] = (char)(unsigned char)IAC;
    buf[1] = (char)verb;
    buf[2] = (char)option;
    telnet_send_raw( d, buf, sizeof(buf) );
}

void telnet_offer_options( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    d->telnet_state  = TS_DATA;
    d->telnet_sb_len = 0;
    d->term_width    = 0;
    d->term_height   = 0;
    d->gmcp_enabled  = false;

    /* We are willing to report status, speak GMCP, and compress output. */
    telnet_command( d, WILL, TELOPT_MSSP );
    telnet_command( d, WILL, TELOPT_GMCP );
    telnet_command( d, WILL, TELOPT_COMPRESS2 );

    /* And we would like to know the client's window size. */
    telnet_command( d, DO,   TELOPT_NAWS );
}

/* ------------------------------------------------------------------ MSSP */

static int telnet_count_players( void )
{
    DESCRIPTOR_DATA *d;
    int players = 0;

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        if ( d->connected == CON_PLAYING && d->character != NULL )
            players++;
    }

    return players;
}

static void mssp_pair( char *buf, size_t size, size_t *len,
                       const char *name, const char *value )
{
    size_t need;

    if ( name == NULL || value == NULL )
        return;

    /* 1 marker + name + 1 marker + value */
    need = 1 + strlen(name) + 1 + strlen(value);
    if ( *len + need >= size )
        return;         /* Drop a field rather than emit a truncated block. */

    buf[(*len)++] = (char)MSSP_VAR;
    memcpy( buf + *len, name, strlen(name) );
    *len += strlen(name);

    buf[(*len)++] = (char)MSSP_VAL;
    memcpy( buf + *len, value, strlen(value) );
    *len += strlen(value);
}

/*
 * Answer a crawler's MSSP request. Only public, already-advertised facts go
 * out here: name, player count, uptime, codebase. Nothing operational.
 */
static void telnet_send_mssp( DESCRIPTOR_DATA *d )
{
    char buf[MAX_TELNET_SUBNEG];
    char value[64];
    size_t len = 0;

    if ( d == NULL )
        return;

    buf[len++] = (char)(unsigned char)IAC;
    buf[len++] = (char)(unsigned char)SB;
    buf[len++] = (char)TELOPT_MSSP;

    mssp_pair( buf, sizeof(buf), &len, "NAME", "Times of Chaos" );

    snprintf( value, sizeof(value), "%d", telnet_count_players() );
    mssp_pair( buf, sizeof(buf), &len, "PLAYERS", value );

    snprintf( value, sizeof(value), "%ld", (long)boot_time_stamp );
    mssp_pair( buf, sizeof(buf), &len, "UPTIME", value );

    mssp_pair( buf, sizeof(buf), &len, "CODEBASE", "ROM 2.4" );
    mssp_pair( buf, sizeof(buf), &len, "FAMILY", "DikuMUD" );
    mssp_pair( buf, sizeof(buf), &len, "CHARSET", "ISO-8859-1" );
    mssp_pair( buf, sizeof(buf), &len, "ANSI", "1" );
    mssp_pair( buf, sizeof(buf), &len, "GMCP", "1" );
    mssp_pair( buf, sizeof(buf), &len, "MCCP", "1" );
    mssp_pair( buf, sizeof(buf), &len, "PAY TO PLAY", "0" );
    mssp_pair( buf, sizeof(buf), &len, "PAY FOR PERKS", "0" );

    if ( len + 2 >= sizeof(buf) )
        return;

    buf[len++] = (char)(unsigned char)IAC;
    buf[len++] = (char)(unsigned char)SE;

    telnet_send_raw( d, buf, len );
}

/* ------------------------------------------------------------------ GMCP */

void telnet_send_gmcp( DESCRIPTOR_DATA *d, const char *package, const char *json )
{
    char buf[MAX_TELNET_SUBNEG];
    size_t len = 0;
    size_t need;

    if ( d == NULL || !d->gmcp_enabled || package == NULL || json == NULL )
        return;

    need = 3 + strlen(package) + 1 + strlen(json) + 2;
    if ( need >= sizeof(buf) )
        return;

    buf[len++] = (char)(unsigned char)IAC;
    buf[len++] = (char)(unsigned char)SB;
    buf[len++] = (char)TELOPT_GMCP;

    memcpy( buf + len, package, strlen(package) );
    len += strlen(package);
    buf[len++] = ' ';

    memcpy( buf + len, json, strlen(json) );
    len += strlen(json);

    buf[len++] = (char)(unsigned char)IAC;
    buf[len++] = (char)(unsigned char)SE;

    telnet_send_raw( d, buf, len );
}

/* --------------------------------------------------------- subnegotiation */

static void telnet_handle_subneg( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    switch ( d->telnet_option )
    {
    case TELOPT_NAWS:
        /*
         * Two 16-bit big-endian values. Clamp to something sane: a hostile
         * or confused client must not be able to drive page length or wrap
         * width to absurd values.
         */
        if ( d->telnet_sb_len >= 4 )
        {
            int width  = ((unsigned char)d->telnet_sb[0] << 8)
                       |  (unsigned char)d->telnet_sb[1];
            int height = ((unsigned char)d->telnet_sb[2] << 8)
                       |  (unsigned char)d->telnet_sb[3];

            d->term_width  = (sh_int)URANGE( 40, width,  250 );
            d->term_height = (sh_int)URANGE( 10, height, 100 );

            /*
             * Deliberately does not touch the player's page length. In
             * do_scroll(), lines == 0 means "paging disabled", which is a
             * choice a player made; silently overriding it because their
             * client reported a window size would take that away. The size is
             * recorded here and applied only when the player asks for it with
             * `scroll auto`.
             */
        }
        break;

    case TELOPT_MSSP:
        telnet_send_mssp( d );
        break;

    default:
        break;
    }
}

/* ------------------------------------------------------------ input filter */

size_t telnet_filter_input( DESCRIPTOR_DATA *d, const char *raw, size_t length,
                            char *out, size_t out_max )
{
    size_t i;
    size_t written = 0;

    if ( d == NULL || raw == NULL || out == NULL )
        return 0;

    for ( i = 0; i < length; i++ )
    {
        unsigned char c = (unsigned char)raw[i];

        switch ( d->telnet_state )
        {
        case TS_DATA:
            if ( c == (unsigned char)IAC )
            {
                d->telnet_state = TS_IAC;
                break;
            }
            if ( written < out_max )
                out[written++] = (char)c;
            break;

        case TS_IAC:
            switch ( c )
            {
            case IAC:
                /* Escaped 255: a literal data byte. */
                if ( written < out_max )
                    out[written++] = (char)c;
                d->telnet_state = TS_DATA;
                break;
            case WILL: case WONT: case DO: case DONT:
                d->telnet_option = c;
                d->telnet_state  = TS_NEGOTIATE;
                break;
            case SB:
                d->telnet_state  = TS_SB_OPTION;
                d->telnet_sb_len = 0;
                break;
            default:
                /* Standalone command (GA, NOP, ...): nothing to do. */
                d->telnet_state = TS_DATA;
                break;
            }
            break;

        case TS_NEGOTIATE:
        {
            unsigned char verb   = d->telnet_option;
            unsigned char option = c;

            if ( verb == DO || verb == DONT )
            {
                bool wanted = (verb == DO);

                switch ( option )
                {
                case TELOPT_MSSP:
                    if ( wanted )
                        telnet_send_mssp( d );
                    break;
                case TELOPT_GMCP:
                    d->gmcp_enabled = wanted;
                    break;
                case TELOPT_COMPRESS2:
                    if ( wanted )
                        telnet_start_compression( d );
                    else
                        telnet_end_compression( d );
                    break;
                default:
                    /* Refuse anything we do not implement, once. */
                    if ( wanted )
                        telnet_command( d, WONT, option );
                    break;
                }
            }
            else if ( verb == WILL || verb == WONT )
            {
                if ( option == TELOPT_NAWS )
                {
                    if ( verb == WONT )
                    {
                        d->term_width  = 0;
                        d->term_height = 0;
                    }
                }
                else if ( verb == WILL )
                {
                    /* We did not ask; decline rather than stay silent. */
                    telnet_command( d, DONT, option );
                }
            }

            d->telnet_state = TS_DATA;
            break;
        }

        case TS_SB_OPTION:
            d->telnet_option = c;
            d->telnet_sb_len = 0;
            d->telnet_state  = TS_SB_DATA;
            break;

        case TS_SB_DATA:
            if ( c == (unsigned char)IAC )
            {
                d->telnet_state = TS_SB_IAC;
                break;
            }
            /*
             * Overlong payloads are dropped, not truncated: keep counting so
             * the terminating IAC SE still ends the subnegotiation cleanly.
             */
            if ( d->telnet_sb_len < MAX_TELNET_SUBNEG )
                d->telnet_sb[d->telnet_sb_len++] = (char)c;
            break;

        case TS_SB_IAC:
            if ( c == (unsigned char)IAC )
            {
                /* Escaped 255 inside the payload. */
                if ( d->telnet_sb_len < MAX_TELNET_SUBNEG )
                    d->telnet_sb[d->telnet_sb_len++] = (char)c;
                d->telnet_state = TS_SB_DATA;
                break;
            }
            if ( c == (unsigned char)SE )
                telnet_handle_subneg( d );
            /* Any other byte here is malformed; drop the subnegotiation. */
            d->telnet_sb_len = 0;
            d->telnet_state  = TS_DATA;
            break;

        default:
            d->telnet_state = TS_DATA;
            break;
        }
    }

    return written;
}
