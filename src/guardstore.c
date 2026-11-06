/*
 * The connection guard's record of players' addresses: see guardstore.h.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "guardstore.h"

void guard_store_init( GUARD_STORE *s, GUARD_TRUST *rows, int max )
{
    s->rows = rows;
    s->count = 0;
    s->max = max;
    s->file_lines = 0;
    s->read_only = 0;
    s->bad_lines = 0;
}

GUARD_TRUST *guard_store_find( GUARD_STORE *s, uint32_t key )
{
    int i;

    if ( key == 0 )
        return NULL;
    for ( i = 0; i < s->count; i++ )
        if ( s->rows[i].key == key )
            return &s->rows[i];
    return NULL;
}

GUARD_TRUST *guard_store_note( GUARD_STORE *s, const NET_ADDR *a, time_t when )
{
    GUARD_TRUST *t;
    uint32_t key = net_addr_guard_key( a );
    int i, oldest;

    if ( key == 0 || when <= 0 || s->max <= 0 )
        return NULL;
    if ( ( t = guard_store_find( s, key ) ) != NULL )
    {
        if ( when > t->last )
        {
            t->last = when;
            net_addr_text( a, t->text, sizeof(t->text) );
        }
        return t;
    }
    if ( s->count >= s->max )
    {
        oldest = 0;
        for ( i = 1; i < s->count; i++ )
            if ( s->rows[i].last < s->rows[oldest].last )
                oldest = i;
        s->rows[oldest] = s->rows[--s->count];
    }
    t = &s->rows[s->count++];
    memset( t, 0, sizeof(*t) );
    t->key = key;
    t->last = when;
    net_addr_text( a, t->text, sizeof(t->text) );
    return t;
}

int guard_store_trusted( GUARD_STORE *s, uint32_t key, time_t now, long days )
{
    GUARD_TRUST *t = guard_store_find( s, key );

    return t != NULL && now - t->last <= (time_t) days * 86400;
}

int guard_store_active( GUARD_STORE *s, time_t now, long days )
{
    int i, n = 0;

    for ( i = 0; i < s->count; i++ )
        if ( now - s->rows[i].last <= (time_t) days * 86400 )
            n++;
    return n;
}

int guard_store_dirty( const GUARD_TRUST *t )
{
    return t != NULL && t->last > t->persisted;
}

int guard_store_due( const GUARD_TRUST *t )
{
    return guard_store_dirty( t )
        && ( t->persisted == 0 || t->last - t->persisted >= GUARD_PERSIST_GAP );
}

/* A test harness may stand in for fflush to fail it on purpose. */
#ifdef GUARD_STORE_FFLUSH
int GUARD_STORE_FFLUSH( FILE *fp );
#define store_fflush GUARD_STORE_FFLUSH
#else
#define store_fflush fflush
#endif

/*
 * Every error is kept: a short write or a full disk shows at the flush or
 * the close, not at the fprintf, and a flush that failed once may "succeed"
 * the next time with the bytes it dropped still dropped -- so the stream's
 * error flag is asked too, and `ok` once false stays false (review of
 * f1388da0, 2026-11-06: the rewrite's first flush failure was forgotten
 * and an incomplete file renamed in). The stream is always closed. `sync`
 * flushes to the disk, and only after a flush that worked.
 */
static int finish( FILE *fp, int ok, int sync )
{
    if ( store_fflush( fp ) != 0 )
        ok = 0;
    if ( ferror( fp ) )
        ok = 0;
    if ( ok && sync && fsync( fileno( fp ) ) != 0 )
        ok = 0;
    if ( fclose( fp ) != 0 )
        ok = 0;
    return ok;
}

/* 1 when the file is empty or ends in a newline, 0 when its last record is
   unfinished, -1 when that cannot be told. */
static int ends_whole( const char *path )
{
    FILE *fp;
    int c, whole;

    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return errno == ENOENT ? 1 : -1;
    if ( fseek( fp, 0, SEEK_END ) != 0 )
    {
        fclose( fp );
        return -1;
    }
    if ( ftell( fp ) <= 0 )
    {
        fclose( fp );
        return 1;
    }
    if ( fseek( fp, -1, SEEK_END ) != 0 || ( c = getc( fp ) ) == EOF )
    {
        fclose( fp );
        return -1;
    }
    whole = c == '\n';
    fclose( fp );
    return whole;
}

int guard_store_append( GUARD_STORE *s, const char *path, GUARD_TRUST *t )
{
    FILE *fp;
    int ok;

    int whole;

    if ( s->read_only || t == NULL || t->text[0] == '\0' )
        return 0;
    /* An unfinished last record -- a crash mid-line, a write that failed
       part way -- is ended before this one, or the two run together and
       the loader read the pair as one record with a time from the far
       future (review of f1388da0). The ended fragment is a line the loader
       refuses and the next rewrite drops. */
    if ( ( whole = ends_whole( path ) ) < 0 || ( fp = fopen( path, "a" ) ) == NULL )
        return 0;
    ok = 1;
    if ( !whole && fputc( '\n', fp ) == EOF )
        ok = 0;
    if ( ok && fprintf( fp, "%s\t%ld\n", t->text, (long) t->last ) < 0 )
        ok = 0;
    if ( !finish( fp, ok, 0 ) )
        return 0;
    t->persisted = t->last;
    s->file_lines++;
    return 1;
}

int guard_store_rewrite( GUARD_STORE *s, const char *path, const char *tmp )
{
    FILE *fp;
    int ok = 1;
    int i;

    if ( s->read_only || ( fp = fopen( tmp, "w" ) ) == NULL )
        return 0;
    if ( fprintf( fp, "# address\tlast login (epoch): connguard.c\n" ) < 0 )
        ok = 0;
    for ( i = 0; ok && i < s->count; i++ )
        if ( s->rows[i].text[0] != '\0'
        &&   fprintf( fp, "%s\t%ld\n", s->rows[i].text, (long) s->rows[i].last ) < 0 )
            ok = 0;
    if ( !finish( fp, ok, 1 ) || rename( tmp, path ) != 0 )
    {
        unlink( tmp );
        return 0;
    }
    s->bad_lines = 0;
    for ( i = 0; i < s->count; i++ )
        s->rows[i].persisted = s->rows[i].last;
    s->file_lines = s->count + 1;
    return 1;
}

/* One whole record, "<address>\t<time>\n", from `line`: 1 and the
   address and time, or 0. */
static int parse_record( char *line, time_t now, NET_ADDR *a, time_t *when )
{
    char *tab, *end, *p;
    size_t len = strlen( line );
    long value;

    if ( len == 0 || line[len - 1] != '\n' )
        return 0;                       /* unfinished: no newline */
    line[--len] = '\0';
    if ( len > 0 && line[len - 1] == '\r' )
        line[--len] = '\0';
    if ( ( tab = strchr( line, '\t' ) ) == NULL )
        return 0;
    *tab = '\0';
    for ( p = tab + 1; *p != '\0'; p++ )
        if ( !isdigit( (unsigned char) *p ) )
            return 0;                   /* a sign, a space, a second field */
    if ( p == tab + 1 || p - ( tab + 1 ) > 19 )
        return 0;
    errno = 0;
    value = strtol( tab + 1, &end, 10 );
    if ( errno == ERANGE || *end != '\0' || value <= 0 )
        return 0;
    if ( (time_t) value > now + GUARD_CLOCK_SKEW )
        return 0;                       /* from the future: not believed */
    if ( !net_addr_parse( line, a ) )
        return 0;
    *when = (time_t) value;
    return 1;
}

long guard_store_load( GUARD_STORE *s, const char *path, time_t now )
{
    char line[512];
    FILE *fp;
    long lines = 0;
    int failed = 0;

    if ( ( fp = fopen( path, "r" ) ) == NULL )
    {
        if ( errno == ENOENT )
            return GUARD_LOAD_ABSENT;
        s->read_only = 1;               /* there, and not readable */
        return GUARD_LOAD_UNREADABLE;
    }
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        NET_ADDR a;
        GUARD_TRUST *t;
        time_t when;
        size_t len = strlen( line );

        lines++;
        if ( len == sizeof(line) - 1 && line[len - 1] != '\n' )
        {
            /* Longer than any record: skip the rest of it. */
            int c;

            while ( ( c = getc( fp ) ) != EOF && c != '\n' )
                ;
            s->bad_lines++;
            continue;
        }
        if ( line[0] == '#' && len > 0 && line[len - 1] == '\n' )
            continue;
        if ( !parse_record( line, now, &a, &when ) )
        {
            s->bad_lines++;
            continue;
        }
        if ( ( t = guard_store_note( s, &a, when ) ) != NULL && t->persisted < t->last )
            t->persisted = t->last;     /* the file holds it */
    }
    if ( ferror( fp ) )
        failed = 1;
    if ( fclose( fp ) != 0 )
        failed = 1;
    s->file_lines = lines;
    if ( failed )
    {
        s->read_only = 1;               /* read in part: never written over */
        return GUARD_LOAD_UNREADABLE;
    }
    return lines;
}

/* The tab-separated field `n` (from 0) of `line`, copied into buf. */
static int field( const char *line, int n, char *buf, size_t size )
{
    const char *p = line;
    size_t len = 0;

    while ( n-- > 0 )
    {
        p = strchr( p, '\t' );
        if ( p == NULL )
            return 0;
        p++;
    }
    while ( p[len] != '\0' && p[len] != '\t' && p[len] != '\n' && p[len] != '\r' )
        len++;
    if ( len == 0 || len >= size )
        return 0;
    memcpy( buf, p, len );
    buf[len] = '\0';
    return 1;
}

int guard_seed_login_row( const char *line, NET_ADDR *a, time_t *when )
{
    char stamp[32], host[96], event[32];
    char *end;
    long epoch;

    if ( line == NULL || !field( line, 0, stamp, sizeof(stamp) )
    ||   !field( line, 2, host, sizeof(host) ) || !field( line, 3, event, sizeof(event) ) )
        return 0;
    if ( strcmp( event, "connect" ) && strcmp( event, "reconnect" ) && strcmp( event, "new" ) )
        return 0;
    epoch = strtol( stamp, &end, 10 );
    if ( *end != '\0' || epoch <= 0 || !net_addr_parse( host, a ) )
        return 0;
    *when = (time_t) epoch;
    return 1;
}

/* toc.log's "Wed Nov  4 03:18:53 2026 :: ..." as an epoch, or 0. Local
   time, as the log writes it. */
static time_t log_time( const char *line )
{
    static const char *const months[] =
        { "Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec" };
    char wday[4], mon[4];
    struct tm tm;
    int day, hh, mm, ss, year, i;

    if ( sscanf( line, "%3s %3s %d %d:%d:%d %d", wday, mon, &day, &hh, &mm, &ss, &year ) != 7 )
        return 0;
    memset( &tm, 0, sizeof(tm) );
    tm.tm_mon = -1;
    for ( i = 0; i < 12; i++ )
        if ( !strcmp( mon, months[i] ) )
            tm.tm_mon = i;
    if ( tm.tm_mon < 0 )
        return 0;
    tm.tm_mday = day;
    tm.tm_hour = hh;
    tm.tm_min = mm;
    tm.tm_sec = ss;
    tm.tm_year = year - 1900;
    tm.tm_isdst = -1;
    return mktime( &tm );
}

int guard_seed_log_line( const char *line, NET_ADDR *a, time_t *when )
{
    static const char *const tails[] = { " has connected.", " reconnected.", " new player." };
    const char *msg, *at, *sp;
    char host[96];
    size_t i, len;
    time_t t;

    if ( line == NULL || ( msg = strstr( line, " :: " ) ) == NULL )
        return 0;
    msg += 4;
    /* <Name>@<host><tail>, the name letters only: a character's name. */
    for ( at = msg; isalpha( (unsigned char) *at ); at++ )
        ;
    if ( at == msg || *at != '@' )
        return 0;
    at++;
    if ( ( sp = strchr( at, ' ' ) ) == NULL )
        return 0;
    for ( i = 0; i < sizeof(tails) / sizeof(tails[0]); i++ )
        if ( !strncmp( sp, tails[i], strlen( tails[i] ) ) )
            break;
    if ( i == sizeof(tails) / sizeof(tails[0]) )
        return 0;
    len = (size_t) ( sp - at );
    if ( len == 0 || len >= sizeof(host) )
        return 0;
    memcpy( host, at, len );
    host[len] = '\0';
    if ( !net_addr_parse( host, a ) || ( t = log_time( line ) ) <= 0 )
        return 0;
    *when = t;
    return 1;
}
