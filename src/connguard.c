/*
 * The connection guard (2026-11-06): what the game does about addresses that
 * connect and never play.
 *
 * The log for 2026-09-17 to 11-06 held 13,977 outside connections from 982
 * addresses; 951 of those addresses never logged in, and the busiest of them
 * came back four hundred times each, up to 108 times in one minute. Each one
 * cost a blocking hostname lookup (now async, dnsasync.c), two log lines and
 * a descriptor that nothing ever timed out.
 *
 * The owner's rule (2026-11-06): an address a player has logged in from in
 * the last few months, or is playing from now, is never held back, however often its client times
 * out and reconnects; an address that keeps connecting and has never carried
 * a player is shut out for a while. An immortal's BAN is a separate list and
 * still shuts out anybody. So:
 *
 *  - A successful login trusts its address while it stays active: a player
 *    logged in from it within GUARD_TRUST_DAYS (90; owner, 2026-11-06:
 *    "players who've logged in within the last few months"). Trusted
 *    addresses are kept in log/player_addresses.tsv (a dotted address and
 *    when a player last logged in from it, a line; a login adds a line once
 *    a day at most, and the newest line for an address wins), seeded at
 *    boot from that file, from the login journal's numeric hosts and times,
 *    and from the log's own record of which connection logged in. log/ is
 *    published, as the login journal already is; the file holds nothing
 *    that journal and toc.log do not.
 *  - An untrusted address is blocked after GUARD_STRIKES connections within
 *    GUARD_STRIKE_WINDOW, or GUARD_BURST within a minute: GUARD_BLOCK_BASE
 *    the first time, doubling for each block in the last week, to
 *    GUARD_BLOCK_MAX. A blocked connection is told how long and closed
 *    before the greeting, with no lookup and no log line.
 *  - Any address holds at most GUARD_PENDING_MAX connections that are not
 *    playing yet; the next is refused, not blocked.
 *  - Silent connections -- closed without sending a line -- are counted, not
 *    logged one by one; GUARD_REPORT_SECS apart a summary line says how many
 *    there were, how many were refused and how many addresses were blocked.
 *
 * Loopback is exempt, as the login throttle exempts it (the web bridge and
 * the health probe); TOC_GUARD_LOOPBACK=1 includes it, for the tests (apart
 * from the throttle's switch, whose tests make many failed connections),
 * and TOC_GUARD_STRIKES / TOC_GUARD_BURST lower the limits for them.
 * Staff DNS GUARD lists blocks and trusted counts; DNS ALLOW <address> lifts
 * a block and trusts the address.
 */
#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <arpa/inet.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"

#define GUARD_SLOTS           512
#define GUARD_TRUST_MAX      4096
#define GUARD_TRUST_DAYS       90
#define GUARD_TRUST_FILE_MAX 20000    /* lines before the file is rewritten */
#define GUARD_STRIKES           6
#define GUARD_STRIKE_WINDOW  ( 6 * 3600 )
#define GUARD_BURST            20
#define GUARD_BLOCK_BASE     ( 6 * 3600 )
#define GUARD_BLOCK_MAX      ( 7 * 86400 )
#define GUARD_PENDING_MAX       8
#define GUARD_REPORT_SECS    3600
#define GUARD_TRUST_FILE     "../log/player_addresses.tsv"
#define GUARD_LOGINS_FILE    "../log/logins.tsv"
#define GUARD_TOC_LOG        "../log/toc.log"

typedef struct guard_entry
{
    uint32_t ip;
    bool     used;
    time_t   last_seen;
    time_t   window_start;   /* the strike window */
    int      conns;
    time_t   burst_start;    /* the minute */
    int      burst;
    time_t   blocked_until;
    time_t   last_block;     /* when the last block began */
    int      blocks;         /* blocks in the last week, for doubling */
} GUARD_ENTRY;

static GUARD_ENTRY guard_table[GUARD_SLOTS];
typedef struct guard_trust
{
    uint32_t ip;
    time_t   last;      /* a player last logged in from it */
} GUARD_TRUST;

static GUARD_TRUST guard_trusted[GUARD_TRUST_MAX];
static int         guard_trusted_count;
static long        guard_trust_lines;  /* lines in the file, for the rewrite */
static bool        guard_loaded;
static long        guard_silent;     /* since the last report */
static long        guard_refused;
static long        guard_blocks_new;
static time_t      guard_report_at;

static int guard_limit( const char *env, int fallback )
{
    const char *value = getenv( env );
    long n;

    if ( value == NULL || value[0] == '\0' )
        return fallback;
    n = strtol( value, NULL, 10 );
    return n > 0 && n < 100000 ? (int) n : fallback;
}

/* Whether the guard looks at this address at all. */
static bool guard_applies( uint32_t ip )
{
    const char *opt;

    if ( ip == 0 )
        return false;
    if ( ( ntohl( ip ) >> 24 ) == 127 )
    {
        opt = getenv( "TOC_GUARD_LOOPBACK" );
        return opt != NULL && opt[0] == '1';
    }
    return true;
}

static GUARD_TRUST *guard_trust_find( uint32_t ip )
{
    int i;

    for ( i = 0; i < guard_trusted_count; i++ )
        if ( guard_trusted[i].ip == ip )
            return &guard_trusted[i];
    return NULL;
}

/* A player logged in from it within GUARD_TRUST_DAYS. */
static bool guard_trusted_has( uint32_t ip )
{
    GUARD_TRUST *t = guard_trust_find( ip );

    return t != NULL && current_time - t->last <= (time_t) GUARD_TRUST_DAYS * 86400;
}

/* Note a login from ip at `when`: the newest time wins. The previous time,
   or 0 for an address not on the list. */
static time_t guard_trusted_note( uint32_t ip, time_t when )
{
    GUARD_TRUST *t;
    time_t before;
    int i, oldest;

    if ( ip == 0 || when <= 0 )
        return 0;
    if ( ( t = guard_trust_find( ip ) ) != NULL )
    {
        before = t->last;
        if ( when > t->last )
            t->last = when;
        return before;
    }
    if ( guard_trusted_count >= GUARD_TRUST_MAX )
    {
        /* The address longest unseen gives way: the list is bounded so a
           long life cannot grow it without end. */
        oldest = 0;
        for ( i = 1; i < guard_trusted_count; i++ )
            if ( guard_trusted[i].last < guard_trusted[oldest].last )
                oldest = i;
        guard_trusted[oldest] = guard_trusted[--guard_trusted_count];
    }
    guard_trusted[guard_trusted_count].ip = ip;
    guard_trusted[guard_trusted_count].last = when;
    guard_trusted_count++;
    return 0;
}

static int guard_active_count( void )
{
    int i, n = 0;

    for ( i = 0; i < guard_trusted_count; i++ )
        if ( current_time - guard_trusted[i].last <= (time_t) GUARD_TRUST_DAYS * 86400 )
            n++;
    return n;
}

/* toc.log's "Wed Nov  4 03:18:53 2026 :: ..." as an epoch, or 0. Local
   time, as the log writes it. */
static time_t guard_log_time( const char *line )
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

/* A dotted IPv4 address, whole, or 0. */
static uint32_t guard_parse( const char *text )
{
    struct in_addr address;
    char buf[INET_ADDRSTRLEN];
    size_t n = 0;

    while ( text[n] != '\0' && ( isdigit( (unsigned char) text[n] ) || text[n] == '.' )
         && n + 1 < sizeof(buf) )
    {
        buf[n] = text[n];
        n++;
    }
    buf[n] = '\0';
    if ( n == 0 || inet_pton( AF_INET, buf, &address ) != 1 )
        return 0;
    return address.s_addr;
}

/*
 * Boot: the trusted list, its own file first, then what the login journal
 * and the log already say about which addresses players came from. The
 * journal records a numeric host when the lookup gave none; the log names a
 * connection's address ("Sock.sinaddr:") and, a line or few later, the
 * player it carried ("... has connected.", "... reconnected.", "... new
 * player."). Anything misread here only trusts an address too readily,
 * which is the safe way round.
 */
static void guard_load( void )
{
    char line[1024];
    FILE *fp;
    uint32_t pending = 0;
    int since = 0;

    if ( guard_loaded )
        return;
    guard_loaded = true;

    if ( ( fp = fopen( GUARD_TRUST_FILE, "r" ) ) != NULL )
    {
        while ( fgets( line, sizeof(line), fp ) != NULL )
        {
            char *tab = strchr( line, '\t' );

            guard_trust_lines++;
            if ( tab != NULL )
                guard_trusted_note( guard_parse( line ), (time_t) strtol( tab + 1, NULL, 10 ) );
        }
        fclose( fp );
    }

    /* <epoch> <name> <host> <event>...: a numeric host is an address. */
    if ( ( fp = fopen( GUARD_LOGINS_FILE, "r" ) ) != NULL )
    {
        while ( fgets( line, sizeof(line), fp ) != NULL )
        {
            char *tab = strchr( line, '\t' );

            if ( tab != NULL && ( tab = strchr( tab + 1, '\t' ) ) != NULL )
                guard_trusted_note( guard_parse( tab + 1 ), (time_t) strtol( line, NULL, 10 ) );
        }
        fclose( fp );
    }

    if ( ( fp = fopen( GUARD_TOC_LOG, "r" ) ) != NULL )
    {
        while ( fgets( line, sizeof(line), fp ) != NULL )
        {
            char *at = strstr( line, ":: Sock.sinaddr:" );

            if ( at != NULL )
            {
                at += strlen( ":: Sock.sinaddr:" );
                while ( *at == ' ' )
                    at++;
                pending = guard_parse( at );
                since = 0;
                continue;
            }
            if ( pending == 0 )
                continue;
            if ( ++since > 12 )
            {
                pending = 0;
                continue;
            }
            if ( strstr( line, " has connected." ) != NULL
            ||   strstr( line, " reconnected." ) != NULL
            ||   strstr( line, " new player." ) != NULL )
            {
                guard_trusted_note( pending, guard_log_time( line ) );
                pending = 0;
            }
        }
        fclose( fp );
    }

    if ( guard_report_at == 0 )
        guard_report_at = current_time;
}

/* At boot, before the game loop: toc.log runs to megabytes, and reading it
   at the first connection would be a stall of the kind this file exists to
   end. */
void conn_guard_boot( void )
{
    guard_load();
}

static GUARD_ENTRY *guard_find( uint32_t ip, bool claim )
{
    GUARD_ENTRY *oldest = &guard_table[0];
    int i;

    for ( i = 0; i < GUARD_SLOTS; i++ )
        if ( guard_table[i].used && guard_table[i].ip == ip )
            return &guard_table[i];
    if ( !claim )
        return NULL;
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        if ( !guard_table[i].used )
        {
            oldest = &guard_table[i];
            break;
        }
        /* Never recycle a standing block while an older slot will do. */
        if ( ( oldest->blocked_until > current_time ) > ( guard_table[i].blocked_until > current_time )
        ||   ( ( oldest->blocked_until > current_time ) == ( guard_table[i].blocked_until > current_time )
            && guard_table[i].last_seen < oldest->last_seen ) )
            oldest = &guard_table[i];
    }
    memset( oldest, 0, sizeof(*oldest) );
    oldest->ip = ip;
    oldest->used = true;
    return oldest;
}

static void guard_ip_text( uint32_t ip, char *buf, size_t size )
{
    struct in_addr address;

    address.s_addr = ip;
    if ( inet_ntop( AF_INET, &address, buf, (socklen_t) size ) == NULL )
        toc_strlcpy( buf, "?", size );
}

static void guard_block( GUARD_ENTRY *e, const char *why )
{
    char addr[INET_ADDRSTRLEN];
    char buf[MAX_STRING_LENGTH];
    long length;
    int shift;

    if ( e->last_block == 0 || current_time - e->last_block > 7 * 86400 )
        e->blocks = 0;
    shift = UMIN( e->blocks, 10 );
    length = (long) GUARD_BLOCK_BASE << shift;
    if ( length > GUARD_BLOCK_MAX )
        length = GUARD_BLOCK_MAX;
    e->blocks++;
    e->last_block = current_time;
    e->blocked_until = current_time + length;
    e->conns = 0;
    e->burst = 0;
    guard_blocks_new++;
    guard_ip_text( e->ip, addr, sizeof(addr) );
    snprintf( buf, sizeof(buf),
              "Connection guard: %s blocked for %ld hours (%s; no player has ever logged in from it).",
              addr, length / 3600, why );
    log_string( buf );
    wizinfo( buf, LEVEL_IMMORTAL );
}

/*
 * At accept, before the greeting: NULL to admit, or the line to send before
 * closing. Counts the connection against its address.
 */
const char *conn_guard_admit( DESCRIPTOR_DATA *d, char *buf, size_t size )
{
    DESCRIPTOR_DATA *od;
    GUARD_ENTRY *e;
    int pending = 0;

    if ( d == NULL || !guard_applies( d->ip ) )
        return NULL;
    guard_load();
    /* A player's address is never held back by the guard (owner,
       2026-11-06): one a player has logged in from in the last
       GUARD_TRUST_DAYS, or one a player is playing from now. An immortal's BAN is another list, asked at the
       name and the password as always, and still shuts anybody out. */
    if ( guard_trusted_has( d->ip ) )
        return NULL;
    for ( od = descriptor_list; od != NULL; od = od->next )
        if ( od != d && od->ip == d->ip && od->connected == CON_PLAYING )
            return NULL;
    e = guard_find( d->ip, true );
    e->last_seen = current_time;

    if ( e->blocked_until > current_time )
    {
        long left = (long) ( e->blocked_until - current_time );

        guard_refused++;
        snprintf( buf, size,
                  "Connections from your address are paused for %ld more minute%s.\n\r",
                  ( left + 59 ) / 60, ( left + 59 ) / 60 == 1 ? "" : "s" );
        return buf;
    }

    if ( e->window_start == 0 || current_time - e->window_start > GUARD_STRIKE_WINDOW )
    {
        e->window_start = current_time;
        e->conns = 0;
    }
    if ( e->burst_start == 0 || current_time - e->burst_start > 60 )
    {
        e->burst_start = current_time;
        e->burst = 0;
    }
    e->conns++;
    e->burst++;
    if ( e->burst >= guard_limit( "TOC_GUARD_BURST", GUARD_BURST ) )
        guard_block( e, "too many connections in a minute" );
    else if ( e->conns >= guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES ) )
        guard_block( e, "kept connecting without playing" );
    if ( e->blocked_until > current_time )
    {
        guard_refused++;
        snprintf( buf, size, "Connections from your address are paused for a while.\n\r" );
        return buf;
    }

    for ( od = descriptor_list; od != NULL; od = od->next )
        if ( od != d && od->ip == d->ip && od->connected != CON_PLAYING )
            pending++;
    if ( pending >= GUARD_PENDING_MAX )
    {
        guard_refused++;
        snprintf( buf, size, "Too many connections from your address are waiting to log in.\n\r" );
        return buf;
    }
    return NULL;
}

/* The whole list, newest times only, written aside and renamed in. */
static void guard_trust_rewrite( void )
{
    char addr[INET_ADDRSTRLEN];
    FILE *fp;
    int i;

    if ( ( fp = fopen( GUARD_TRUST_FILE ".tmp", "w" ) ) == NULL )
        return;
    for ( i = 0; i < guard_trusted_count; i++ )
    {
        guard_ip_text( guard_trusted[i].ip, addr, sizeof(addr) );
        fprintf( fp, "%s\t%ld\n", addr, (long) guard_trusted[i].last );
    }
    if ( temp_file_commit( fp, GUARD_TRUST_FILE ".tmp", GUARD_TRUST_FILE ) )
        guard_trust_lines = guard_trusted_count;
}

/* A player logged in: their address is trusted for GUARD_TRUST_DAYS from
   now. Written down once a day at most per address. */
void conn_guard_trust( uint32_t ip )
{
    GUARD_ENTRY *e;
    FILE *fp;
    char addr[INET_ADDRSTRLEN];
    time_t before;

    if ( !guard_applies( ip ) )
        return;
    guard_load();
    if ( ( e = guard_find( ip, false ) ) != NULL )
    {
        e->blocked_until = 0;
        e->conns = e->burst = 0;
    }
    before = guard_trusted_note( ip, current_time );
    if ( before != 0 && current_time - before < 86400 )
        return;
    if ( guard_trust_lines >= GUARD_TRUST_FILE_MAX )
    {
        guard_trust_rewrite();
        return;
    }
    guard_ip_text( ip, addr, sizeof(addr) );
    if ( ( fp = fopen( GUARD_TRUST_FILE, "a" ) ) != NULL )
    {
        fprintf( fp, "%s\t%ld\n", addr, (long) current_time );
        fclose( fp );
        guard_trust_lines++;
    }
}

bool conn_guard_trusted( uint32_t ip )
{
    guard_load();
    return guard_trusted_has( ip );
}

/* A connection that closed without a word: counted for the summary. */
void conn_guard_silent( DESCRIPTOR_DATA *d )
{
    if ( d != NULL && guard_applies( d->ip ) )
        guard_silent++;
}

/* Once a pulse: the summary, GUARD_REPORT_SECS apart, when there is one. */
void conn_guard_tick( void )
{
    char buf[MAX_STRING_LENGTH];
    int blocked = 0;
    int i;

    if ( guard_report_at == 0 )
        guard_report_at = current_time;
    if ( current_time - guard_report_at < GUARD_REPORT_SECS )
        return;
    guard_report_at = current_time;
    if ( guard_silent == 0 && guard_refused == 0 && guard_blocks_new == 0 )
        return;
    for ( i = 0; i < GUARD_SLOTS; i++ )
        if ( guard_table[i].used && guard_table[i].blocked_until > current_time )
            blocked++;
    snprintf( buf, sizeof(buf),
              "Connection guard: last hour %ld closed without a word, %ld refused, "
              "%ld newly blocked; %d addresses blocked now, %d active player addresses.",
              guard_silent, guard_refused, guard_blocks_new, blocked, guard_active_count() );
    log_string( buf );
    guard_silent = guard_refused = guard_blocks_new = 0;
}

/* Staff DNS GUARD. */
void conn_guard_report( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    char addr[INET_ADDRSTRLEN];
    int shown = 0;
    int i;

    guard_load();
    snprintf( buf, sizeof(buf),
              "Connection guard: %d active player addresses (a player logged in from each\n\r"
              "in the last %d days) are never limited or blocked; an immortal's BAN still is.\n\r"
              "Untrusted: blocked after %d connections in %d hours or %d in a minute,\n\r"
              "for %d hours doubling to %d days. Since the last hourly line: %ld silent,\n\r"
              "%ld refused.\n\r",
              guard_active_count(), GUARD_TRUST_DAYS, guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES ),
              GUARD_STRIKE_WINDOW / 3600, guard_limit( "TOC_GUARD_BURST", GUARD_BURST ),
              GUARD_BLOCK_BASE / 3600, GUARD_BLOCK_MAX / 86400, guard_silent, guard_refused );
    send_to_char( buf, ch );
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        if ( !guard_table[i].used || guard_table[i].blocked_until <= current_time )
            continue;
        guard_ip_text( guard_table[i].ip, addr, sizeof(addr) );
        snprintf( buf, sizeof(buf), "  %-16s blocked %ld more minutes (block %d this week)\n\r",
                  addr, (long) ( guard_table[i].blocked_until - current_time + 59 ) / 60,
                  guard_table[i].blocks );
        send_to_char( buf, ch );
        shown++;
    }
    if ( shown == 0 )
        send_to_char( "  Nobody is blocked.\n\r", ch );
}

/* Staff DNS ALLOW <address>: lift a block and trust the address. */
bool conn_guard_allow( const char *text )
{
    uint32_t ip = guard_parse( text );

    if ( ip == 0 )
        return false;
    conn_guard_trust( ip );
    return true;
}
