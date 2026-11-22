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
 * kinds: login and commands (by character), level, quest (by area), death,
 * bug (the message, numbers as #), anomaly, memory (the field), event (the
 * black market, the goblin and the like, by their first words), guard
 * (connection and address lines: counted, never their text), and other (the
 * line's first word). A key never holds an address or a host name; numbers
 * in it are #, so the same bug at two rooms is one row. tools/log_report.py
 * reads the file. The full lines are still in git's history.
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
#include <sys/types.h>
#include <sys/stat.h>
#include "merc.h"
#include "numparse.h"

#define DIGEST_SLOTS    8192
#define DIGEST_KEY      120

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

/* A key fit for a public file: no tabs or control bytes, every run of
   digits one '#' (an address is all digits and dots, so it reads #.#.#.#),
   held to DIGEST_KEY bytes. */
static void digest_key( char *out, size_t size, const char *text, size_t len )
{
    size_t o = 0, i;
    bool digits = false;

    for ( i = 0; i < len && text[i] != '\0' && o + 1 < size; i++ )
    {
        unsigned char c = (unsigned char) text[i];

        if ( isdigit( c ) )
        {
            if ( !digits )
                out[o++] = '#';
            digits = true;
            continue;
        }
        digits = false;
        out[o++] = (char) ( c < 32 || c == 127 ? ' ' : c );
    }
    while ( o > 0 && out[o - 1] == ' ' )
        o--;
    out[o] = '\0';
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
    if ( ( p = strstr( text, "BUG:" ) ) != NULL )
    {
        p += 4;
        while ( *p == ' ' )
            p++;
        digest_key( key, sizeof(key), p, strlen( p ) );
        digest_count( dg, day, "bug", key );
        return;
    }
    if ( starts( text, "ANOMALY:" ) )
    {
        digest_key( key, sizeof(key), text + 8, 60 );
        digest_count( dg, day, "anomaly", key );
        return;
    }
    /* Anything that can carry an address is counted, never kept. */
    if ( strstr( text, "Sock.sinaddr" ) || strstr( text, "shares an address" )
    ||   starts( text, "Connection guard" ) || starts( text, "Login lock" )
    ||   strstr( text, "closed without a word" ) || starts( text, "DNS" ) )
    {
        digest_count( dg, day, "guard", "-" );
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
        /* The watch log: "Log <Name> [<room>]: <command>". */
        char name[16];
        const char *cmd = strstr( text, "]: " );

        digest_word( name, sizeof(name), text + 4 );
        cmd = cmd != NULL ? cmd + 3 : "";
        if ( starts( cmd, "level " ) )
            digest_count( dg, day, "level", name );
        else if ( starts( cmd, "quest assigned:" ) && ( p = strstr( cmd, " in " ) ) != NULL )
        {
            size_t n = strcspn( p + 4, ", " );

            digest_key( key, sizeof(key), p + 4, n );
            digest_count( dg, day, "quest", key );
        }
        else if ( starts( cmd, "died to" ) || starts( cmd, "killed " ) )
            digest_count( dg, day, "death", name );
        digest_count( dg, day, "commands", name );
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
        digest_key( key, sizeof(key), by, n );
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
        digest_key( key, sizeof(key), text, n );
        digest_count( dg, day, "event", key );
        return;
    }
    {
        size_t n = strcspn( text, " :" );

        digest_key( key, sizeof(key), text, n < 24 ? n : 24 );
        digest_count( dg, day, "other", key[0] != '\0' ? key : "-" );
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

/* Append the summary; true when every row reached the file. */
static bool digest_write( DIGEST *dg )
{
    FILE *fp;
    struct stat st;
    bool fresh = stat( LOG_SUMMARY_FILE, &st ) != 0;
    int i;
    bool ok = true;

    if ( ( fp = fopen( LOG_SUMMARY_FILE, "a" ) ) == NULL )
        return false;
    if ( fresh )
        fprintf( fp, "# What was cut from the game's logs, summed per day "
                 "(src/logtrim.c): day, source, kind, key, count.\n" );
    qsort( dg->rows, DIGEST_SLOTS, sizeof(DIGEST_ROW), digest_order );
    for ( i = 0; i < DIGEST_SLOTS && dg->rows[i].used; i++ )
        if ( fprintf( fp, "%s\t%s\t%s\t%s\t%ld\n", dg->rows[i].day, dg->source,
                      dg->rows[i].kind, dg->rows[i].key, dg->rows[i].count ) < 0 )
            ok = false;
    if ( dg->overflow > 0 )
        fprintf( fp, "-\t%s\toverflow\t(lines past the summary's room)\t%ld\n",
                 dg->source, dg->overflow );
    if ( ferror( fp ) )
        ok = false;
    if ( fclose( fp ) != 0 )
        ok = false;
    return ok;
}

/*
 * Keep a log's newest `keep` bytes, from the start of a line, after summing
 * every line cut into LOG_SUMMARY_FILE. The tail is copied aside first, then
 * the cut lines summed, then the copy renamed in (temp_file_commit), so a
 * full disk or a crash keeps the old file whole, a summary that did not land
 * cuts nothing, and a copy that failed sums nothing (the next try would count
 * the same lines again). A failure is not tried again for
 * LOG_TRIM_RETRY_SECS: the callers ask every few hundred lines, and a cut
 * that cannot work (a log directory gone read-only, a summary that is not a
 * file) would otherwise read the whole log and say it failed each time.
 * Answers LOG_TRIM_CUT, LOG_TRIM_FAILED, or LOG_TRIM_SKIPPED when there was
 * nothing to cut or a failure is being waited out. A failed commit says so
 * through log_string, so log_string closes its own handle and sets it NULL
 * before calling this.
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
    long target;
    long tail_at = -1;
    size_t n;
    bool whole = true;
    bool copied = true;
    int slot = digest == LOG_DIGEST_EVENTS ? 1 : 0;
    time_t now = time( NULL );

    if ( failed_at[slot] != 0 && now >= failed_at[slot]
    &&   now - failed_at[slot] < LOG_TRIM_RETRY_SECS )
        return LOG_TRIM_SKIPPED;
    if ( keep <= 0 || !toc_path_join( temp, sizeof(temp), path, "", ".tmp" ) )
        return LOG_TRIM_SKIPPED;
    if ( stat( path, &st ) != 0 || !S_ISREG( st.st_mode ) || (long) st.st_size <= keep )
        return LOG_TRIM_SKIPPED;
    failed_at[slot] = now;          /* cleared below once the cut lands */
    if ( ( in = fopen( path, "rb" ) ) == NULL )
        return LOG_TRIM_FAILED;
    target = (long) st.st_size - keep;

    /* Where the kept tail starts: the first line beginning at or past the
       target. */
    while ( fgets( line, sizeof(line), in ) != NULL )
    {
        size_t len = strlen( line );

        if ( len > 0 && line[len - 1] == '\n' && ftell( in ) >= target )
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

    /* The lines before the tail, each counted once: a line longer than the
       buffer is counted from its first piece and the rest passed over. */
    dg.rows = calloc( DIGEST_SLOTS, sizeof(DIGEST_ROW) );
    dg.overflow = 0;
    dg.source = digest == LOG_DIGEST_EVENTS ? "events" : "toc";
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

        if ( whole )
        {
            line[strcspn( line, "\r\n" )] = '\0';
            digest_line( &dg, digest, line );
        }
        whole = ends;
    }
    if ( ferror( in ) || !digest_write( &dg ) )
    {
        free( dg.rows );
        fclose( in );
        fclose( out );
        remove( temp );
        return LOG_TRIM_FAILED;
    }
    free( dg.rows );
    fclose( in );
    if ( !temp_file_commit( out, temp, path ) )
        return LOG_TRIM_FAILED;
    failed_at[slot] = 0;
    return LOG_TRIM_CUT;
}
