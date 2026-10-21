/*
 * MCCP2 against the real src/telnet_proto.c, with the socket writes
 * stubbed to record what would have gone on the wire.
 *
 * tests/test_mccp.py builds and runs this and decodes the output with
 * zlib. Each phase is written to stdout as a four-byte big-endian length
 * and the bytes the client would have received during it:
 *
 *   0  the 8,192 incompressible bytes written in phase 2
 *   1  the reply to IAC DO COMPRESS2 (the uncompressed handshake)
 *   2  one write of phase 0's bytes -- all of it must decode at once
 *   3  one write of "hello"
 *   4  the reply to IAC DONT COMPRESS2 -- the end of the stream
 *   5  one write of "plain" -- plaintext after the stream
 *   6  IAC DO COMPRESS2 again, then a write of "again"
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <arpa/telnet.h>
#include "merc.h"
#include "telnet_proto.h"

DESCRIPTOR_DATA *descriptor_list;
time_t           boot_time_stamp;

static unsigned char wire[65536];
static size_t        wire_len;

bool write_raw_to_descriptor( DESCRIPTOR_DATA *d, const char *txt, int length )
{
    (void) d;
    if ( length <= 0 )
        length = (int) strlen( txt );
    if ( wire_len + (size_t) length > sizeof(wire) )
        abort();
    memcpy( wire + wire_len, txt, (size_t) length );
    wire_len += (size_t) length;
    return TRUE;
}

bool write_to_descriptor( DESCRIPTOR_DATA *d, const char *txt, int length )
{
    if ( d->out_compress != NULL )
        return telnet_write_compressed( d, txt, length );
    return write_raw_to_descriptor( d, txt, length );
}

void gmcp_on_enabled( DESCRIPTOR_DATA *d ) { (void) d; }
void gmcp_on_disabled( DESCRIPTOR_DATA *d ) { (void) d; }
void gmcp_handle_message( DESCRIPTOR_DATA *d, const char *m ) { (void) d; (void) m; }

static void phase( void )
{
    unsigned char len[4];

    len[0] = (unsigned char) ( wire_len >> 24 );
    len[1] = (unsigned char) ( wire_len >> 16 );
    len[2] = (unsigned char) ( wire_len >> 8 );
    len[3] = (unsigned char) wire_len;
    fwrite( len, 1, 4, stdout );
    fwrite( wire, 1, wire_len, stdout );
    wire_len = 0;
}

static void negotiate( DESCRIPTOR_DATA *d, unsigned char verb )
{
    char in[3], out[16];

    in[0] = (char) IAC;
    in[1] = (char) verb;
    in[2] = (char) TELOPT_COMPRESS2;
    telnet_filter_input( d, in, sizeof(in), out, sizeof(out) );
}

int main( void )
{
    static DESCRIPTOR_DATA d;
    static char noise[8192];
    unsigned long seed = 12345;
    size_t i;

    for ( i = 0; i < sizeof(noise); i++ )
    {
        seed = seed * 1103515245UL + 12345UL;
        noise[i] = (char) ( ( seed >> 16 ) & 0xff );
    }
    memcpy( wire, noise, sizeof(noise) );
    wire_len = sizeof(noise);
    phase();

    d.descriptor = 1;
    telnet_offer_options( &d );
    wire_len = 0;                       /* the offers are not under test */

    negotiate( &d, DO );
    phase();
    if ( !telnet_write_compressed( &d, noise, (int) sizeof(noise) ) )
        return 2;
    phase();
    if ( !telnet_write_compressed( &d, "hello", 5 ) )
        return 3;
    phase();
    negotiate( &d, DONT );
    phase();
    if ( !write_to_descriptor( &d, "plain", 5 ) )
        return 4;
    phase();
    negotiate( &d, DO );
    if ( !write_to_descriptor( &d, "again", 5 ) )
        return 5;
    phase();
    telnet_end_compression( &d );
    return 0;
}
