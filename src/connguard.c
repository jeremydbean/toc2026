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
 * the last few months, or is playing from now, is never held back, however
 * often its client times out and reconnects; an address that keeps
 * connecting and has never carried a player is shut out for a while. An
 * immortal's BAN is a separate list and still shuts out anybody. And (owner,
 * the same day) staff hear of every automatic pause. So:
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
 *  - A pause stops new characters, never a login. A real player on an
 *    address the list does not know yet -- a new ISP, a phone, a carrier's
 *    shared address -- still gets the greeting, logs in with their
 *    character, and that login trusts the address and lifts the pause. Only
 *    creating a character is refused while it lasts, with how long is left.
 *  - An untrusted address is paused after GUARD_STRIKES connections within
 *    GUARD_STRIKE_WINDOW that went nowhere, or GUARD_BURST connections
 *    within a minute: GUARD_BLOCK_BASE the first time, doubling for each
 *    pause in the last week, to GUARD_BLOCK_MAX. A connection "went
 *    nowhere" when it closed before reaching a password prompt -- an
 *    existing character's, or a new one's after its name was confirmed.
 *    Never a strike: a connection the login prompt timed out (a client left
 *    open, which reconnects on its own), one that asked for MSSP (the
 *    listing crawlers), and one bridged by the web client (a page reload is
 *    a connection).
 *  - A flood -- GUARD_FLOOD connections within a minute -- is refused
 *    before the greeting for GUARD_FLOOD_SECS, flat. No player's client
 *    reconnects sixty times a minute; the busiest seen did fifteen.
 *  - Any address holds at most GUARD_PENDING_MAX connections that are not
 *    playing yet; the next is refused, not paused.
 *  - Silent connections -- closed without sending a line -- are counted, not
 *    logged one by one; GUARD_REPORT_SECS apart a summary line says how many
 *    there were, how many were refused and how many addresses were paused,
 *    to the log, and to staff as WIZINFO when anything was refused or paused.
 *  - Staff hear, as WIZINFO: every pause and flood refusal, a pause lifted
 *    by a login, a new character refused, and an address that hits the
 *    waiting limit -- the last two once an address in GUARD_NOTICE_SECS.
 *
 * Loopback is exempt, as the login throttle exempts it (the web bridge and
 * the health probe); TOC_GUARD_LOOPBACK=1 includes it, for the tests (apart
 * from the throttle's switch, whose tests make many failed connections),
 * and TOC_GUARD_STRIKES / TOC_GUARD_BURST lower the limits for them.
 * TOC_GUARD_FLOOD lowers the flood. Staff DNS GUARD lists pauses and trusted
 * counts; DNS ALLOW <address> lifts a pause and trusts the address.
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
#define GUARD_FLOOD            60
#define GUARD_FLOOD_SECS     3600
#define GUARD_PENDING_MAX       8
#define GUARD_REPORT_SECS    3600
#define GUARD_NOTICE_SECS     600
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
    time_t   blocked_until;  /* a pause: no new characters */
    time_t   last_block;     /* when the last pause began */
    int      blocks;         /* pauses in the last week, for doubling */
    time_t   flood_until;    /* a flood: refused before the greeting */
    time_t   noticed_at;     /* staff last told of a refusal here */
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
static long        guard_new_refused;  /* new characters refused */
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

/* Staff are told, and the log keeps it. */
static void guard_say( const char *text )
{
    log_string( text );
    wizinfo( text, LEVEL_IMMORTAL );
}

/* A pause: no new characters from it for a while. Logins still work, and
   one lifts it. */
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
    guard_blocks_new++;
    guard_ip_text( e->ip, addr, sizeof(addr) );
    snprintf( buf, sizeof(buf),
              "Connection guard: %s paused for %ld hours (%s; no player has logged in from it "
              "in %d days). Logins still work; new characters wait. DNS ALLOW %s lifts it.",
              addr, length / 3600, why, GUARD_TRUST_DAYS, addr );
    guard_say( buf );
}

/* Whether staff should hear of another refusal at this address yet. */
static bool guard_notice_due( GUARD_ENTRY *e )
{
    if ( e->noticed_at != 0 && current_time - e->noticed_at < GUARD_NOTICE_SECS )
        return false;
    e->noticed_at = current_time;
    return true;
}

/* The address counts for the guard at all: not loopback (bar the tests),
   no player logged in from it lately, nobody playing from it now. */
static bool guard_watches( uint32_t ip, DESCRIPTOR_DATA *self )
{
    DESCRIPTOR_DATA *od;

    if ( !guard_applies( ip ) )
        return false;
    guard_load();
    /* A player's address is never held back by the guard (owner,
       2026-11-06): one a player has logged in from in the last
       GUARD_TRUST_DAYS, or one a player is playing from now. An immortal's
       BAN is another list, asked at the name and the password as always,
       and still shuts anybody out. */
    if ( guard_trusted_has( ip ) )
        return false;
    for ( od = descriptor_list; od != NULL; od = od->next )
        if ( od != self && od->ip == ip && od->connected == CON_PLAYING )
            return false;
    return true;
}

/*
 * At accept, before the greeting: NULL to admit, or the line to send before
 * closing. Counts the connection's minute against its address; a paused
 * address is admitted and marked (d->guard_paused), since a player may be
 * behind it.
 */
const char *conn_guard_admit( DESCRIPTOR_DATA *d, char *buf, size_t size )
{
    DESCRIPTOR_DATA *od;
    GUARD_ENTRY *e;
    char addr[INET_ADDRSTRLEN];
    char note[MAX_STRING_LENGTH];
    int pending = 0;

    if ( d == NULL || !guard_watches( d->ip, d ) )
        return NULL;
    e = guard_find( d->ip, true );
    e->last_seen = current_time;

    if ( e->flood_until > current_time )
    {
        long left = (long) ( e->flood_until - current_time );

        guard_refused++;
        snprintf( buf, size,
                  "Connections from your address are paused for %ld more minute%s.\n\r",
                  ( left + 59 ) / 60, ( left + 59 ) / 60 == 1 ? "" : "s" );
        return buf;
    }

    if ( e->burst_start == 0 || current_time - e->burst_start > 60 )
    {
        e->burst_start = current_time;
        e->burst = 0;
    }
    e->burst++;
    if ( e->burst >= guard_limit( "TOC_GUARD_FLOOD", GUARD_FLOOD ) )
    {
        e->flood_until = current_time + GUARD_FLOOD_SECS;
        e->burst = 0;
        guard_blocks_new++;
        guard_refused++;
        guard_ip_text( e->ip, addr, sizeof(addr) );
        snprintf( note, sizeof(note),
                  "Connection guard: %s refused for %d minutes (%d connections in a minute; "
                  "no player has logged in from it in %d days). DNS ALLOW %s lifts it.",
                  addr, GUARD_FLOOD_SECS / 60, guard_limit( "TOC_GUARD_FLOOD", GUARD_FLOOD ),
                  GUARD_TRUST_DAYS, addr );
        guard_say( note );
        snprintf( buf, size, "Connections from your address are paused for a while.\n\r" );
        return buf;
    }
    if ( e->burst >= guard_limit( "TOC_GUARD_BURST", GUARD_BURST )
    &&   e->blocked_until <= current_time )
        guard_block( e, "too many connections in a minute" );

    for ( od = descriptor_list; od != NULL; od = od->next )
        if ( od != d && od->ip == d->ip && od->connected != CON_PLAYING )
            pending++;
    if ( pending >= GUARD_PENDING_MAX )
    {
        guard_refused++;
        if ( guard_notice_due( e ) )
        {
            guard_ip_text( e->ip, addr, sizeof(addr) );
            snprintf( note, sizeof(note),
                      "Connection guard: %s refused a connection: %d already waiting at the login "
                      "prompt (told again in %d minutes at most).",
                      addr, pending, GUARD_NOTICE_SECS / 60 );
            guard_say( note );
        }
        snprintf( buf, size, "Too many connections from your address are waiting to log in.\n\r" );
        return buf;
    }
    d->guard_paused = e->blocked_until > current_time;
    return NULL;
}

/*
 * A connection closed. One that went nowhere -- no password prompt reached
 * -- is a strike against its address, unless it is one a player's client
 * makes on its own: timed out at the prompt, an MSSP poll, a web bridge.
 */
void conn_guard_closed( DESCRIPTOR_DATA *d )
{
    GUARD_ENTRY *e;

    if ( d == NULL || d->guard_refused || !guard_applies( d->ip ) )
        return;
    if ( !d->first_line_read )
        guard_silent++;
    if ( d->guard_named || d->guard_idle_closed || d->guard_mssp || d->guard_proxied
    ||   d->connected == CON_PLAYING )
        return;
    if ( !guard_watches( d->ip, d ) )
        return;
    e = guard_find( d->ip, true );
    e->last_seen = current_time;
    if ( e->window_start == 0 || current_time - e->window_start > GUARD_STRIKE_WINDOW )
    {
        e->window_start = current_time;
        e->conns = 0;
    }
    e->conns++;
    if ( e->conns >= guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES )
    &&   e->blocked_until <= current_time )
        guard_block( e, "kept connecting without logging in" );
}

/*
 * A new character asked for: NULL to go on, or the line to send. Only a
 * pause stops one; the player is told how long and that a character
 * already made may still log in.
 */
const char *conn_guard_new_char( DESCRIPTOR_DATA *d, const char *name, char *buf, size_t size )
{
    GUARD_ENTRY *e;
    char addr[INET_ADDRSTRLEN];
    char note[MAX_STRING_LENGTH];
    long left;

    if ( d == NULL || !guard_watches( d->ip, d ) )
        return NULL;
    if ( ( e = guard_find( d->ip, false ) ) == NULL || e->blocked_until <= current_time )
        return NULL;
    left = (long) ( e->blocked_until - current_time );
    guard_new_refused++;
    if ( guard_notice_due( e ) )
    {
        guard_ip_text( e->ip, addr, sizeof(addr) );
        snprintf( note, sizeof(note),
                  "Connection guard: new character '%s' refused from paused %s "
                  "(%ld minutes left). DNS ALLOW %s lets it in.",
                  name != NULL ? name : "?", addr, ( left + 59 ) / 60, addr );
        guard_say( note );
    }
    snprintf( buf, size,
              "New characters cannot be made from your address for %ld more minute%s.\n\r"
              "If you already play here, log in with your character.\n\rName: ",
              ( left + 59 ) / 60, ( left + 59 ) / 60 == 1 ? "" : "s" );
    return buf;
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

/* A player logged in (or staff allowed the address): it is trusted for
   GUARD_TRUST_DAYS from now, and any pause on it ends. Written down once a
   day at most per address. `who` says why, for staff; NULL when the caller
   tells them itself. */
void conn_guard_trust( uint32_t ip, const char *who )
{
    GUARD_ENTRY *e;
    FILE *fp;
    char addr[INET_ADDRSTRLEN];
    char buf[MAX_STRING_LENGTH];
    time_t before;

    if ( !guard_applies( ip ) )
        return;
    guard_load();
    guard_ip_text( ip, addr, sizeof(addr) );
    if ( ( e = guard_find( ip, false ) ) != NULL )
    {
        if ( who != NULL && ( e->blocked_until > current_time || e->flood_until > current_time ) )
        {
            snprintf( buf, sizeof(buf), "Connection guard: pause on %s lifted -- %s.", addr, who );
            guard_say( buf );
        }
        e->blocked_until = e->flood_until = 0;
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

/* Once a pulse: the summary, GUARD_REPORT_SECS apart, when there is one;
   staff hear it when something was refused or paused. */
void conn_guard_tick( void )
{
    char buf[MAX_STRING_LENGTH];
    int paused = 0, flooded = 0;
    int i;

    if ( guard_report_at == 0 )
        guard_report_at = current_time;
    if ( current_time - guard_report_at < GUARD_REPORT_SECS )
        return;
    guard_report_at = current_time;
    if ( guard_silent == 0 && guard_refused == 0 && guard_blocks_new == 0 && guard_new_refused == 0 )
        return;
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        if ( !guard_table[i].used )
            continue;
        if ( guard_table[i].flood_until > current_time )
            flooded++;
        else if ( guard_table[i].blocked_until > current_time )
            paused++;
    }
    snprintf( buf, sizeof(buf),
              "Connection guard: last hour %ld closed without a word, %ld refused, "
              "%ld new characters refused, %ld newly paused; %d addresses paused and %d refused "
              "now, %d active player addresses.",
              guard_silent, guard_refused, guard_new_refused, guard_blocks_new, paused, flooded,
              guard_active_count() );
    log_string( buf );
    if ( guard_refused > 0 || guard_blocks_new > 0 || guard_new_refused > 0 )
        wizinfo( buf, LEVEL_IMMORTAL );
    guard_silent = guard_refused = guard_blocks_new = guard_new_refused = 0;
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
              "in the last %d days) are never limited or paused; an immortal's BAN still is.\n\r"
              "Untrusted: paused after %d connections in %d hours that reach no password\n\r"
              "prompt, or %d in a minute, for %d hours doubling to %d days. A pause stops\n\r"
              "new characters only; a login lifts it. %d in a minute is refused outright\n\r"
              "for %d minutes. Since the last hourly line: %ld silent, %ld refused,\n\r"
              "%ld new characters refused.\n\r",
              guard_active_count(), GUARD_TRUST_DAYS, guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES ),
              GUARD_STRIKE_WINDOW / 3600, guard_limit( "TOC_GUARD_BURST", GUARD_BURST ),
              GUARD_BLOCK_BASE / 3600, GUARD_BLOCK_MAX / 86400,
              guard_limit( "TOC_GUARD_FLOOD", GUARD_FLOOD ), GUARD_FLOOD_SECS / 60,
              guard_silent, guard_refused, guard_new_refused );
    send_to_char( buf, ch );
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        const GUARD_ENTRY *e = &guard_table[i];

        if ( !e->used || ( e->blocked_until <= current_time && e->flood_until <= current_time ) )
            continue;
        guard_ip_text( e->ip, addr, sizeof(addr) );
        if ( e->flood_until > current_time )
            snprintf( buf, sizeof(buf), "  %-16s refused %ld more minutes (a flood)\n\r",
                      addr, (long) ( e->flood_until - current_time + 59 ) / 60 );
        else
            snprintf( buf, sizeof(buf), "  %-16s paused %ld more minutes (pause %d this week)\n\r",
                      addr, (long) ( e->blocked_until - current_time + 59 ) / 60, e->blocks );
        send_to_char( buf, ch );
        shown++;
    }
    if ( shown == 0 )
        send_to_char( "  Nobody is paused.\n\r", ch );
}

/* Staff DNS ALLOW <address>: lift a pause and trust the address. */
bool conn_guard_allow( const char *text )
{
    uint32_t ip = guard_parse( text );

    if ( ip == 0 )
        return false;
    conn_guard_trust( ip, NULL );   /* DNS ALLOW says so itself */
    return true;
}
