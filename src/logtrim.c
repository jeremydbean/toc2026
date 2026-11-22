/***************************************************************************
 * logtrim.c -- keeping the game's two unbounded logs bounded, and what is
 * cut summed up first (review and owner, 2026-11-22).
 *
 * log/toc.log only ever grew -- 23 MB by Nov 22, about two and a half a
 * week with one or two players on -- and so did log/webadmin-events.tsv.
 * The state sync commits both whole every five minutes, and GitHub refuses
 * a push holding any file over 100 MB: every player save would have
 * stopped reaching GitHub with nothing saying why, the way the full disk
 * stopped them the morning of Nov 22. So each is cut to its newest half
 * past log_trim_limit().
 *
 * Owner: "you need to move the summary of the logs [to something]
 * reportable or sortable ... compress by moving to a summary of useful
 * data". Before a line is cut it is counted into log/toc-summary.tsv, one
 * row per day, source, kind and key:
 *
 *     2026-11-21<TAB>toc<TAB>bug<TAB>Dam_message: bad dt #.<TAB>3
 *
 * kinds: login and commands (by character -- typed commands only, socials
 * and refusals included, as the watch log writes them), level, quest (by
 * area), death and kill (by character), watch (the other events the watch
 * log writes -- arrivals, coin, items, alignment, affects, the Oracle --
 * keyed by a fixed word), bug (the message), anomaly, memory (the field),
 * event (the black market, the goblin and the like, by their first words),
 * guard (connection and address lines: counted, never their text), and
 * other (the line's first word). A key never holds an address, a host
 * name, a path or a mail address (summary_safe_key: any word that looks
 * like one is '*'), and numbers in it are #, so the same bug at two rooms
 * is one row. tools/log_report.py reads the file. The full lines are still
 * in git's history.
 *
 * A trim is idempotent (review, 2026-11-22: a failed replacement of the log
 * left the summed lines in it, and the next trim summed them again). Each
 * trim's rows are one batch, ended by a marker line --
 *
 *     #batch<TAB>toc<TAB><dev><TAB><inode><TAB><bytes><TAB><fnv64><TAB><epoch>
 *
 * -- saying which file it summed (device and inode: the cut's rename gives
 * the log a new inode) and how much of it from the start, with a checksum
 * of those bytes. A trim that finds the last marker for its source naming
 * the same file, whose first <bytes> still check, knows those lines were
 * summed and only cuts them. Rows after the file's last marker are a batch
 * cut short (a crash, a full disk) and are cut off before the next batch is
 * written; readers count only rows a marker closes.
 ***************************************************************************/

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200112L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "merc.h"
#include "numparse.h"

#define DIGEST_SLOTS    8192
#define DIGEST_KEY      120
#define BATCH_TAG       "#batch\t"

typedef struct
{
    char day[11];
    char kind[24];
    char key[DIGEST_KEY + 1];
    long count;
    bool used;
} DIGEST_ROW;

typedef struct
{
    DIGEST_ROW *rows;
    long        overflow;       /* rows that found no slot: counted, not lost */
    const char *source;
} DIGEST;

/* What a summary file says of one source's last batch, and where its last
   whole batch ends. */
typedef struct
{
    bool          found;        /* a marker for this source */
    unsigned long dev;
    unsigned long ino;
    long          bytes;
    unsigned long long hash;
    long          good_end;     /* after the last marker; rows past it are torn */
    bool          any_marker;
    bool          exists;
} SUMMARY_STATE;

/* Where a log is trimmed: GAME_LOG_MAX, or TOC_LOG_TRIM_BYTES for tests. */
long log_trim_limit( void )
{
    static long limit = 0;

    if ( limit == 0 )
    {
        const char *env = getenv( "TOC_LOG_TRIM_BYTES" );
        long value = 0;

        if ( env == NULL || !parse_long( env, 4096, 1L << 40, &value ) )
            value = GAME_LOG_MAX;
        limit = value;
    }
    return limit;
}

/* Seconds a failed cut waits: LOG_TRIM_RETRY_SECS, or
   TOC_LOG_TRIM_RETRY_SECS for tests. */
static long log_trim_retry( void )
{
    const char *env = getenv( "TOC_LOG_TRIM_RETRY_SECS" );
    long value = 0;

    if ( env != NULL && parse_long( env, 0, 86400, &value ) )
        return value;
    return LOG_TRIM_RETRY_SECS;
}

static unsigned long digest_hash( const char *a, const char *b, const char *c )
{
    unsigned long h = 5381;
    const char *parts[3];
    int i;

    parts[0] = a; parts[1] = b; parts[2] = c;
    for ( i = 0; i < 3; i++ )
    {
        const char *p;

        for ( p = parts[i]; *p != '\0'; p++ )
            h = h * 33 + (unsigned char) *p;
        h = h * 33 + 0x1f;
    }
    return h;
}

static void digest_count( DIGEST *dg, const char *day, const char *kind, const char *key )
{
    unsigned long at = digest_hash( day, kind, key ) % DIGEST_SLOTS;
    int probe;

    for ( probe = 0; probe < DIGEST_SLOTS; probe++ )
    {
        DIGEST_ROW *row = &dg->rows[( at + (unsigned long) probe ) % DIGEST_SLOTS];

        if ( !row->used )
        {
            row->used = true;
            toc_strlcpy( row->day, day, sizeof(row->day) );
            toc_strlcpy( row->kind, kind, sizeof(row->kind) );
            toc_strlcpy( row->key, key, sizeof(row->key) );
            row->count = 1;
            return;
        }
        if ( !strcmp( row->day, day ) && !strcmp( row->kind, kind )
        &&   !strcmp( row->key, key ) )
        {
            row->count++;
            return;
        }
    }
    dg->overflow++;
}

/* The punctuation a sentence puts after a word, which is not the word's. */
#define TRAILING_PUNCT ".,;:!?)]'\""

/*
 * Whether one word of a key could identify somebody or something outside
 * the game: a host name, an address (IPv4 is dots and digits, IPv6 has
 * inner colons), a mail address, a path or a URL. Trailing punctuation is
 * the sentence's, not the word's ("room #." is fine).
 */
static bool word_looks_private( const char *w, size_t len )
{
    size_t i;

    while ( len > 0 && strchr( TRAILING_PUNCT, w[len - 1] ) != NULL )
        len--;
    for ( i = 0; i < len; i++ )
    {
        char c = w[i];

        if ( c == '@' || c == '/' || c == '\\' || c == '=' || c == '.' || c == ':' )
            return true;
    }
    return false;
}

/*
 * A key fit for a public file (review, 2026-11-22: "c-1-2-3.example.net
 * input spamming!" kept its host name, since only digits were masked): no
 * tabs or control bytes, every run of digits one '#', every word that
 * looks like a host, address, path or mail address one '*', held to
 * DIGEST_KEY bytes. Letters, a sentence's punctuation and code-written
 * words (a function's name before its colon) stay, so the same message
 * sums together.
 */
static void summary_safe_key( char *out, size_t size, const char *text, size_t len )
{
    size_t o = 0, i = 0;

    while ( i < len && text[i] != '\0' && o + 1 < size )
    {
        size_t start = i, wlen;

        if ( isspace( (unsigned char) text[i] ) || (unsigned char) text[i] < 32
        ||   text[i] == 127 )
        {
            if ( o > 0 && out[o - 1] != ' ' )
                out[o++] = ' ';
            i++;
            continue;
        }
        while ( i < len && text[i] != '\0' && !isspace( (unsigned char) text[i] )
        &&      (unsigned char) text[i] >= 32 && text[i] != 127 )
            i++;
        wlen = i - start;
        if ( word_looks_private( text + start, wlen ) )
        {
            /* Keep the sentence's trailing punctuation ("*." not "*"). */
            size_t core = wlen;

            while ( core > 0 && strchr( TRAILING_PUNCT, text[start + core - 1] ) != NULL )
                core--;
            out[o++] = '*';
            for ( ; core < wlen && o + 1 < size; core++ )
                out[o++] = text[start + core];
            continue;
        }
        {
            bool digits = false;
            size_t k;

            for ( k = start; k < i && o + 1 < size; k++ )
            {
                if ( isdigit( (unsigned char) text[k] ) )
                {
                    if ( !digits )
                        out[o++] = '#';
                    digits = true;
                    continue;
                }
                digits = false;
                out[o++] = text[k];
            }
        }
    }
    while ( o > 0 && out[o - 1] == ' ' )
        o--;
    out[o] = '\0';
    if ( o == 0 )
        toc_strlcpy( out, "-", size );
}

/* The first word of text, letters only (a name), into out. */
static void digest_word( char *out, size_t size, const char *text )
{
    size_t o = 0;

    while ( *text == ' ' )
        text++;
    while ( isalpha( (unsigned char) *text ) && o + 1 < size )
        out[o++] = *text++;
    out[o] = '\0';
    if ( o == 0 )
        toc_strlcpy( out, "-", size );
}

static bool starts( const char *text, const char *prefix )
{
    return !strncmp( text, prefix, strlen( prefix ) );
}

/* "<word> <digits> -> " (level 34 -> 35, alignment 300 -> 310). */
static bool number_arrow( const char *text, const char *word )
{
    const char *p;

    if ( !starts( text, word ) )
        return false;
    p = text + strlen( word );
    if ( *p == '-' )
        p++;
    if ( !isdigit( (unsigned char) *p ) )
        return false;
    while ( isdigit( (unsigned char) *p ) )
        p++;
    return starts( p, " -> " );
}

/* "<word> <sign><digits>" (copper +12, gold -3, coin +5 loot). */
static bool signed_amount( const char *text, const char *word )
{
    const char *p;

    if ( !starts( text, word ) )
        return false;
    p = text + strlen( word );
    if ( *p != '+' && *p != '-' )
        return false;
    return isdigit( (unsigned char) p[1] ) != 0;
}

/*
 * What a watch-log body (after "Log <name> [<room>]: ") is, when it is not
 * a command (review, 2026-11-22: every one of these was summed as a
 * command, arrivals the most of all). watch_log() writes them (interp.c and
 * its callers); a typed command's line starts with the command's own word,
 * or "(social)" / "(refused)" for anything the game did not know, so each
 * shape here asks for a token no command line begins with. Returns the
 * fixed word it is summed under, or NULL for a command.
 */
static const char *watch_event_word( const char *body )
{
    if ( starts( body, "arrived (" ) )                  return "arrived";
    if ( signed_amount( body, "copper " )
    ||   signed_amount( body, "gold " )
    ||   signed_amount( body, "coin " ) )               return "coin";
    if ( strstr( body, " (vnum " ) != NULL
    &&   ( starts( body, "received " ) || starts( body, "gave " )
        || starts( body, "sold " ) || starts( body, "bought " )
        || starts( body, "stashed " ) || starts( body, "withdrew " )
        || starts( body, "took " ) || strstr( body, " took " ) != NULL ) )
                                                        return "item";
    if ( number_arrow( body, "level " ) )               return "level";
    if ( number_arrow( body, "alignment " ) )           return "alignment";
    if ( starts( body, "affects off: " ) )              return "affects";
    if ( starts( body, "quest assigned: " ) )           return "quest";
    if ( starts( body, "quest complete: " )
    ||   starts( body, "daily quest complete: " )
    ||   starts( body, "daily points: " ) )             return "quest-done";
    if ( starts( body, "died to " ) )                   return "death";
    if ( starts( body, "killed " ) )                    return "kill";
    if ( starts( body, "resurrected by " ) )            return "resurrected";
    if ( starts( body, "remort " ) && isdigit( (unsigned char) body[7] ) )
                                                        return "remort";
    if ( starts( body, "asked the Oracle" )
    ||   starts( body, "disputed an Oracle answer" ) )  return "oracle";
    return NULL;
}

/* One toc.log message (after "<ctime> :: "), counted under its day. */
static void digest_game_text( DIGEST *dg, const char *day, const char *text )
{
    char key[DIGEST_KEY + 1];
    const char *p;

    if ( starts( text, "MEMORY:" ) )
    {
        /* "MEMORY: stale <field> on ..." -- the field. */
        p = strstr( text, "stale " );
        digest_word( key, sizeof(key), p != NULL ? p + 6 : "" );
        digest_count( dg, day, "memory", key );
        return;
    }
    /* Anything that can carry an address is counted, never kept -- asked
       first, since an address line can say BUG too. */
    if ( strstr( text, "Sock.sinaddr" ) || strstr( text, "shares an address" )
    ||   starts( text, "Connection guard" ) || starts( text, "Login lock" )
    ||   strstr( text, "closed without a word" ) || starts( text, "DNS" )
    ||   strstr( text, " input spamming" ) || strstr( text, " input overflow" ) )
    {
        digest_count( dg, day, "guard", "-" );
        return;
    }
    if ( ( p = strstr( text, "BUG:" ) ) != NULL )
    {
        p += 4;
        while ( *p == ' ' )
            p++;
        summary_safe_key( key, sizeof(key), p, strlen( p ) );
        digest_count( dg, day, "bug", key );
        return;
    }
    if ( starts( text, "ANOMALY:" ) )
    {
        summary_safe_key( key, sizeof(key), text + 8, 60 );
        digest_count( dg, day, "anomaly", key );
        return;
    }
    /* "Name@host has connected." and its kin: the name, never the host. */
    if ( ( p = strchr( text, '@' ) ) != NULL
    &&   ( strstr( text, "has connected" ) || strstr( text, "reconnected" )
        || strstr( text, "new player" ) ) )
    {
        digest_word( key, sizeof(key), text );
        digest_count( dg, day, "login", key );
        return;
    }
    if ( starts( text, "Log " ) )
    {
        /* The watch log: "Log <Name> [<room>]: <command or event>", and
           the unwatched LOG_ALWAYS line, "Log <Name>: <command>". */
        char name[16];
        const char *body = strstr( text, "]: " );
        const char *event;

        digest_word( name, sizeof(name), text + 4 );
        if ( body != NULL )
            body += 3;
        else if ( ( body = strstr( text + 4, ": " ) ) != NULL )
            body += 2;
        else
            body = "";
        if ( ( event = watch_event_word( body ) ) == NULL )
        {
            digest_count( dg, day, "commands", name );
            return;
        }
        if ( !strcmp( event, "level" ) )
            digest_count( dg, day, "level", name );
        else if ( !strcmp( event, "death" ) )
            digest_count( dg, day, "death", name );
        else if ( !strcmp( event, "kill" ) )
            digest_count( dg, day, "kill", name );
        else if ( !strcmp( event, "quest" ) && ( p = strstr( body, " in " ) ) != NULL )
        {
            /* The area file, which names no one: kept only when it is
               one ("korzath1.are"), never free text. */
            size_t n = strcspn( p + 4, ", " ), k;
            bool area = n > 4 && n < sizeof(key) && !strncmp( p + 4 + n - 4, ".are", 4 );

            for ( k = 0; area && k < n - 4; k++ )
                if ( !isalnum( (unsigned char) p[4 + k] ) && p[4 + k] != '_' && p[4 + k] != '-' )
                    area = false;
            if ( area )
            {
                memcpy( key, p + 4, n );
                key[n] = '\0';
            }
            else
                toc_strlcpy( key, "*", sizeof(key) );
            digest_count( dg, day, "quest", key );
        }
        else
            digest_count( dg, day, "watch", event );
        return;
    }
    if ( strstr( text, " killed by " ) )
    {
        /* "<Name> killed by <killer> at <room>": who fell, and to what. */
        const char *by = strstr( text, " killed by " ) + 11;
        size_t n = strcspn( by, "(" );
        const char *at = strstr( by, " at " );

        if ( at != NULL && (size_t) ( at - by ) < n )
            n = (size_t) ( at - by );
        summary_safe_key( key, sizeof(key), by, n );
        digest_count( dg, day, "death", key );
        return;
    }
    if ( starts( text, "Black market:" ) || starts( text, "Treasure goblin:" )
    ||   starts( text, "Forage:" ) || starts( text, "Bug replies:" )
    ||   starts( text, "Telemetry:" ) || starts( text, "JAIL:" )
    ||   starts( text, "Disaster" ) || starts( text, "Fate:" )
    ||   starts( text, "Login fix" ) || starts( text, "Holiday" ) )
    {
        /* The kind of event, by its first words up to a room or a list. */
        size_t n = strcspn( text, "(;" );

        if ( n > 48 )
            n = 48;
        summary_safe_key( key, sizeof(key), text, n );
        digest_count( dg, day, "event", key );
        return;
    }
    {
        size_t n = strcspn( text, " :" );

        summary_safe_key( key, sizeof(key), text, n < 24 ? n : 24 );
        digest_count( dg, day, "other", key );
    }
}

/* "Sun Nov 22 17:10:44 2026 :: text" -> "2026-11-22" and the text. */
static bool digest_game_line( const char *line, char *day, size_t size, const char **text )
{
    static const char *months = "JanFebMarAprMayJunJulAugSepOctNovDec";
    const char *sep = strstr( line, " :: " );
    const char *m;
    int d, y;

    if ( sep == NULL || sep - line != 24 )
        return false;
    {
        char mon[4];

        memcpy( mon, line + 4, 3 );
        mon[3] = '\0';
        m = strstr( months, mon );
    }
    if ( m == NULL || ( m - months ) % 3 != 0
    ||   sscanf( line + 8, "%2d", &d ) != 1 || sscanf( line + 20, "%4d", &y ) != 1 )
        return false;
    if ( y < 1970 || y > 9999 || d < 1 || d > 31 )
        return false;
    snprintf( day, size, "%04d-%02d-%02d", y, (int) ( m - months ) / 3 + 1, d );
    *text = sep + 4;
    return true;
}

/* "epoch<TAB>channel<TAB>level<TAB>text": counted by channel. */
static void digest_events_line( DIGEST *dg, const char *line )
{
    char day[32], kind[24], channel[16];
    long epoch;
    size_t n = strcspn( line, "\t" );
    char num[24];
    time_t when;
    struct tm *tm;

    if ( n == 0 || n >= sizeof(num) )
        return;
    memcpy( num, line, n );
    num[n] = '\0';
    if ( !parse_long( num, 0, 1L << 40, &epoch ) || line[n] != '\t' )
        return;
    when = (time_t) epoch;
    if ( ( tm = gmtime( &when ) ) == NULL )
        return;
    snprintf( day, sizeof(day), "%04d-%02d-%02d", ( tm->tm_year + 1900 ) % 10000,
              ( tm->tm_mon + 1 ) % 100, tm->tm_mday % 100 );
    digest_word( channel, sizeof(channel), line + n + 1 );
    snprintf( kind, sizeof(kind), "event:%s", channel );
    digest_count( dg, day, kind, "-" );
}

static void digest_line( DIGEST *dg, int digest, const char *line )
{
    char day[32];
    const char *text;

    if ( digest == LOG_DIGEST_EVENTS )
        digest_events_line( dg, line );
    else if ( digest_game_line( line, day, sizeof(day), &text ) )
        digest_game_text( dg, day, text );
}

static int digest_order( const void *a, const void *b )
{
    const DIGEST_ROW *x = a, *y = b;
    int c;

    if ( x->used != y->used )
        return x->used ? -1 : 1;
    if ( ( c = strcmp( x->day, y->day ) ) != 0 )
        return c;
    if ( ( c = strcmp( x->kind, y->kind ) ) != 0 )
        return c;
    return x->count > y->count ? -1 : x->count < y->count ? 1 : strcmp( x->key, y->key );
}

static void fnv_bytes( unsigned long long *h, const char *p, size_t n )
{
    size_t i;

    for ( i = 0; i < n; i++ )
    {
        *h ^= (unsigned char) p[i];
        *h *= 1099511628211ULL;
    }
}

/* The checksum of a file's first `bytes` bytes; false when they could not
   all be read. */
static bool file_head_hash( FILE *fp, long bytes, unsigned long long *out )
{
    char block[65536];
    unsigned long long h = 14695981039346656037ULL;
    long left = bytes;

    if ( fseek( fp, 0L, SEEK_SET ) != 0 )
        return false;
    while ( left > 0 )
    {
        size_t want = left > (long) sizeof(block) ? sizeof(block) : (size_t) left;
        size_t got = fread( block, 1, want, fp );

        if ( got == 0 )
            return false;
        fnv_bytes( &h, block, got );
        left -= (long) got;
    }
    *out = h;
    return true;
}

/*
 * Read the summary: the last marker for `source`, and the end of the last
 * whole batch of any source -- after the last marker, or, with none yet,
 * after the header's comment lines. Every row past that end is a batch cut
 * short (no summary was written before markers: no live log had reached
 * the limit). False when the file is there and could not be read.
 */
static bool summary_state_read( const char *source, SUMMARY_STATE *st )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    long last_line_end = 0;

    memset( st, 0, sizeof(*st) );
    if ( ( fp = fopen( LOG_SUMMARY_FILE, "rb" ) ) == NULL )
        return access( LOG_SUMMARY_FILE, F_OK ) != 0;
    st->exists = true;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        size_t len = strlen( line );

        if ( len == 0 || line[len - 1] != '\n' )
            break;                          /* a torn last line */
        last_line_end = ftell( fp );
        if ( starts( line, BATCH_TAG ) )
        {
            char src[16];
            unsigned long dev = 0, ino = 0;
            long bytes = 0;
            unsigned long long hash = 0;

            st->any_marker = true;
            st->good_end = last_line_end;
            if ( sscanf( line + strlen( BATCH_TAG ), "%15[^\t]\t%lu\t%lu\t%ld\t%llx",
                         src, &dev, &ino, &bytes, &hash ) == 5
            &&   !strcmp( src, source ) && bytes > 0 )
            {
                st->found = true;
                st->dev = dev;
                st->ino = ino;
                st->bytes = bytes;
                st->hash = hash;
            }
        }
        else if ( line[0] == '#' && !st->any_marker && st->good_end == last_line_end - (long) len )
            st->good_end = last_line_end;   /* the header, before any row */
    }
    if ( ferror( fp ) )
    {
        fclose( fp );
        return false;
    }
    fclose( fp );
    return true;
}

/*
 * Append one batch: the summary is first cut back to the end of its last
 * whole batch (a batch a crash or a full disk cut short), then the rows and
 * the marker are written and flushed to the disk. On a failure the file is
 * cut back again, so it never ends in a batch without its marker for long:
 * the next trim would cut it off anyway. True when the marker is on disk.
 */
static bool summary_append_batch( DIGEST *dg, const SUMMARY_STATE *ss, const struct stat *log_st,
                                  long bytes, unsigned long long hash )
{
    FILE *fp;
    int i, rows = 0, half;
    bool ok = true;

    if ( ( fp = fopen( LOG_SUMMARY_FILE, ss->exists ? "r+b" : "w+b" ) ) == NULL )
        return false;
    if ( ftruncate( fileno( fp ), (off_t) ss->good_end ) != 0
    ||   fseek( fp, ss->good_end, SEEK_SET ) != 0 )
    {
        fclose( fp );
        return false;
    }
    if ( ss->good_end == 0 )
        fprintf( fp, "# What was cut from the game's logs, summed per day "
                 "(src/logtrim.c): day, source, kind, key, count. Rows count "
                 "only when a #batch line follows them.\n" );
    qsort( dg->rows, DIGEST_SLOTS, sizeof(DIGEST_ROW), digest_order );
    for ( i = 0; i < DIGEST_SLOTS && dg->rows[i].used; i++ )
        rows++;
    half = rows / 2;
    for ( i = 0; i < rows; i++ )
    {
        if ( i == half && recovery_fault( "logtrim-torn" ) )
        {
            /* Tests only: a crash part way through the batch. */
            fflush( fp );
            _exit( 75 );
        }
        if ( fprintf( fp, "%s\t%s\t%s\t%s\t%ld\n", dg->rows[i].day, dg->source,
                      dg->rows[i].kind, dg->rows[i].key, dg->rows[i].count ) < 0 )
            ok = false;
    }
    if ( dg->overflow > 0 )
        fprintf( fp, "-\t%s\toverflow\t(lines past the summary's room)\t%ld\n",
                 dg->source, dg->overflow );
    if ( fprintf( fp, BATCH_TAG "%s\t%lu\t%lu\t%ld\t%016llx\t%ld\n", dg->source,
                  (unsigned long) log_st->st_dev, (unsigned long) log_st->st_ino,
                  bytes, hash, (long) time( NULL ) ) < 0 )
        ok = false;
    if ( fflush( fp ) != 0 || ferror( fp ) )
        ok = false;
    if ( ok && fsync( fileno( fp ) ) != 0 )
        ok = false;
    if ( !ok )
    {
        /* Nothing of this batch stays. */
        if ( ftruncate( fileno( fp ), (off_t) ss->good_end ) != 0 )
            ok = false;
    }
    if ( fclose( fp ) != 0 )
        ok = false;
    return ok;
}

/*
 * Keep a log's newest `keep` bytes, from the start of a line, after summing
 * every line cut into LOG_SUMMARY_FILE. In order: the tail is copied aside;
 * the lines before it are summed and written as one batch with its marker,
 * on the disk; then the copy is renamed over the log (temp_file_commit). A
 * failure before the batch lands cuts and sums nothing; a failure after it
 * -- the rename refused, a crash -- leaves the log whole and the batch
 * standing, and the next trim, finding its marker naming this very file and
 * its bytes still the same, sums only what came after them (review,
 * 2026-11-22: they were summed twice). A failure is not tried again for
 * LOG_TRIM_RETRY_SECS: the callers ask every few hundred lines, and a cut
 * that cannot work would otherwise read the whole log each time. Answers
 * LOG_TRIM_CUT, LOG_TRIM_FAILED, or LOG_TRIM_SKIPPED when there was nothing
 * to cut or a failure is being waited out. A failed commit says so through
 * log_string, so log_string closes its own handle and sets it NULL before
 * calling this.
 */
int log_file_keep_tail( const char *path, long keep, int digest )
{
    static time_t failed_at[2];
    char temp[512];
    char line[MAX_STRING_LENGTH];
    char block[65536];
    struct stat st;
    FILE *in, *out;
    DIGEST dg;
    SUMMARY_STATE ss;
    long target;
    long tail_at = -1;
    long summed = 0;
    unsigned long long hash = 14695981039346656037ULL;
    size_t n;
    bool whole = true;
    bool copied = true;
    int slot = digest == LOG_DIGEST_EVENTS ? 1 : 0;
    const char *source = digest == LOG_DIGEST_EVENTS ? "events" : "toc";
    time_t now = time( NULL );

    if ( failed_at[slot] != 0 && now >= failed_at[slot]
    &&   now - failed_at[slot] < log_trim_retry() )
        return LOG_TRIM_SKIPPED;
    if ( keep <= 0 || !toc_path_join( temp, sizeof(temp), path, "", ".tmp" ) )
        return LOG_TRIM_SKIPPED;
    if ( stat( path, &st ) != 0 || !S_ISREG( st.st_mode ) || (long) st.st_size <= keep )
        return LOG_TRIM_SKIPPED;
    failed_at[slot] = now;          /* cleared below once the cut lands */
    if ( !summary_state_read( source, &ss ) )
        return LOG_TRIM_FAILED;
    if ( ( in = fopen( path, "rb" ) ) == NULL )
        return LOG_TRIM_FAILED;
    target = (long) st.st_size - keep;

    /* What an earlier attempt summed and could not cut: its marker names
       this file, and its bytes are still the file's first. */
    if ( ss.found && ss.dev == (unsigned long) st.st_dev
    &&   ss.ino == (unsigned long) st.st_ino && ss.bytes <= (long) st.st_size )
    {
        unsigned long long check = 0;

        if ( file_head_hash( in, ss.bytes, &check ) && check == ss.hash )
            summed = ss.bytes;
    }

    /* Where the kept tail starts: the first line beginning at or past the
       target, and never before what was summed. */
    if ( fseek( in, 0L, SEEK_SET ) != 0 )
    {
        fclose( in );
        return LOG_TRIM_FAILED;
    }
    while ( fgets( line, sizeof(line), in ) != NULL )
    {
        size_t len = strlen( line );

        if ( len > 0 && line[len - 1] == '\n' && ftell( in ) >= target
        &&   ftell( in ) >= summed )
        {
            tail_at = ftell( in );
            break;
        }
    }
    if ( ferror( in ) || tail_at < 0 || ( out = fopen( temp, "wb" ) ) == NULL )
    {
        fclose( in );
        return LOG_TRIM_FAILED;
    }
    while ( ( n = fread( block, 1, sizeof(block), in ) ) > 0 )
        if ( fwrite( block, 1, n, out ) != n )
        {
            copied = false;
            break;
        }
    if ( !copied || ferror( in ) || fflush( out ) != 0 || ferror( out ) )
    {
        fclose( in );
        fclose( out );
        remove( temp );
        return LOG_TRIM_FAILED;
    }

    /* The lines before the tail: all of them checksummed for the marker,
       those past what was already summed counted, each once (a line longer
       than the buffer is counted from its first piece). */
    dg.rows = calloc( DIGEST_SLOTS, sizeof(DIGEST_ROW) );
    dg.overflow = 0;
    dg.source = source;
    if ( dg.rows == NULL || fseek( in, 0L, SEEK_SET ) != 0 )
    {
        free( dg.rows );
        fclose( in );
        fclose( out );
        remove( temp );
        return LOG_TRIM_FAILED;
    }
    while ( ftell( in ) < tail_at && fgets( line, sizeof(line), in ) != NULL )
    {
        size_t len = strlen( line );
        bool ends = len > 0 && line[len - 1] == '\n';
        long after = ftell( in );

        fnv_bytes( &hash, line, len );
        if ( whole && after > summed )
        {
            line[strcspn( line, "\r\n" )] = '\0';
            digest_line( &dg, digest, line );
        }
        whole = ends;
    }
    if ( ferror( in ) || !summary_append_batch( &dg, &ss, &st, tail_at, hash ) )
    {
        free( dg.rows );
        fclose( in );
        fclose( out );
        remove( temp );
        return LOG_TRIM_FAILED;
    }
    free( dg.rows );
    fclose( in );

    /* Tests only: the replacement refused, or the game gone, after the
       batch landed. */
    if ( recovery_fault( "logtrim-commit" ) )
    {
        fclose( out );
        remove( temp );
        return LOG_TRIM_FAILED;
    }
    if ( recovery_fault( "logtrim-crash" ) )
        _exit( 75 );
    if ( !temp_file_commit( out, temp, path ) )
        return LOG_TRIM_FAILED;
    failed_at[slot] = 0;
    return LOG_TRIM_CUT;
}
