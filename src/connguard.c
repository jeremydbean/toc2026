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
 *    addresses are kept in log/player_addresses.tsv (an address, IPv4 or
 *    IPv6, and when a player last logged in from it, a line; a line a day
 *    at most, measured from the last line that landed, every write checked
 *    and a failed one retried, the newest line for an address winning --
 *    guardstore.c). The file is the record; with none yet it is started
 *    once from the login journal's and toc.log's login records that name
 *    their own numeric address, and nothing else. log/ is published, as
 *    the login journal already is; the file holds nothing that journal and
 *    toc.log do not.
 *  - A paused address is refused at accept, before the greeting (owner,
 *    2026-11-13: "prevent them from even establishing a connection at all
 *    when paused"; it used to stop new characters only). The game cannot
 *    refuse the TCP handshake itself -- the kernel completes it -- so the
 *    connection is reset at once with no reply (SO_LINGER 0, d->guard_reset),
 *    as a closed port answers: nothing tells a scanner anything is there.
 *    A player's address is never paused (above), and a player on a new
 *    address that was paused asks staff: DNS ALLOW lifts it.
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
 *    playing yet; the next is refused, not paused. And the whole game holds
 *    at most GUARD_GLOBAL_PENDING such connections from addresses no player
 *    uses (a flood from many addresses); a player's address is never
 *    refused by either limit.
 *  - Pauses, floods and the strikes and pause history behind them survive a
 *    restart (owner, 2026-11-13: deploys came often enough that every pause
 *    was a first one and none lasted its six hours): GUARD_PAUSE_FILE,
 *    written aside and renamed in -- at once when a pause starts or ends,
 *    within GUARD_SAVE_SECS of a strike -- and read at boot. A file there
 *    and not read whole is never written over until a boot reads it, as
 *    the lockouts' is.
 *  - Every connection that closes before a password prompt is logged with
 *    its address, whether it spoke and whether it counted (owner,
 *    2026-11-13). Refusals are logged per address too, the first at once
 *    and then one line a GUARD_REFUSAL_LOG_SECS with how many came since.
 *    GUARD_REPORT_SECS apart a summary line says how many there were, how
 *    many were refused and how many addresses were paused, to the log, and
 *    to staff as WIZINFO when anything was refused or paused.
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
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "guardstore.h"

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
#define GUARD_GLOBAL_PENDING  200   /* not playing yet, from every address */
#define GUARD_REPORT_SECS    3600
#define GUARD_NOTICE_SECS     600
#define GUARD_TRUST_FILE     "../log/player_addresses.tsv"
#define GUARD_LOGINS_FILE    "../log/logins.tsv"
#define GUARD_TOC_LOG        "../log/toc.log"
#define GUARD_PAUSE_FILE     "../log/guard_pauses.tsv"
#define GUARD_SAVE_SECS        30   /* a strike reaches the file within this */
#define GUARD_REFUSAL_LOG_SECS 60   /* one refusal line an address this often */
#define GUARD_HISTORY        ( 7 * 86400 )   /* pauses counted for doubling */

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
    time_t   refusal_logged; /* the last refusal line for it */
    long     refusals_unlogged;  /* refused since that line */
    long     refused_total;  /* refused while paused or flooding, all time */
    char     text[NET_ADDR_TEXT];   /* the address last seen for this key */
} GUARD_ENTRY;

static GUARD_ENTRY guard_table[GUARD_SLOTS];

/* Players' addresses: guardstore.c, which keeps the login seen apart from
   the login the file holds and checks every write. */
static GUARD_TRUST guard_trust_rows[GUARD_TRUST_MAX];
static GUARD_STORE guard_trust;
static bool        guard_loaded;
static time_t      guard_retry_at;    /* the next look for unwritten logins */
static long        guard_silent;     /* since the last report */
static long        guard_refused;
static long        guard_blocks_new;
static long        guard_new_refused;  /* new characters refused */
static time_t      guard_report_at;
static bool        guard_pause_dirty;   /* a strike not yet written */
static time_t      guard_pause_saved;
static bool        guard_pause_read_only;

static void guard_pause_save( void );
static void guard_pause_load( void );

static int guard_limit( const char *env, int fallback )
{
    const char *value = getenv( env );
    long n;

    if ( value == NULL || value[0] == '\0' )
        return fallback;
    n = strtol( value, NULL, 10 );
    return n > 0 && n < 100000 ? (int) n : fallback;
}

/* Whether the guard looks at this key at all. */
static bool guard_applies( uint32_t ip )
{
    const char *opt;

    if ( ip == 0 )
        return false;
    if ( !net_addr_key_is_v6( ip ) && ( ntohl( ip ) >> 24 ) == 127 )
    {
        opt = getenv( "TOC_GUARD_LOOPBACK" );
        return opt != NULL && opt[0] == '1';
    }
    return true;
}

/* A player logged in from it within GUARD_TRUST_DAYS. */
static bool guard_trusted_has( uint32_t ip )
{
    return guard_store_trusted( &guard_trust, ip, current_time, GUARD_TRUST_DAYS );
}

static int guard_active_count( void )
{
    return guard_store_active( &guard_trust, current_time, GUARD_TRUST_DAYS );
}

/* The whole list, written aside and renamed in; logged if it fails. */
static bool guard_trust_rewrite( void )
{
    if ( guard_store_rewrite( &guard_trust, GUARD_TRUST_FILE, GUARD_TRUST_FILE ".tmp" ) )
        return true;
    log_string( "Connection guard: could not rewrite " GUARD_TRUST_FILE "; will try again." );
    return false;
}

/*
 * Boot: the record of players' addresses. Its own file is the record; once
 * it exists the older journals are never read again, so nothing depends on
 * them to repair it (review, 2026-11-06).
 *
 * With no file yet, the record is started once from what the journals
 * reliably say: a login row or line that names its own numeric address
 * (guard_seed_login_row, guard_seed_log_line). A login recorded by host
 * name is left out -- before 2026-11-06 the name was looked up at accept,
 * so most were -- and so is the old guess that joined a connection line
 * to the next login line, which an unrelated connection between them
 * made wrong. A player missed this way is not shut out: a pause stops only
 * new characters, and their next login trusts the address.
 */
static void guard_load( void )
{
    char line[1024];
    FILE *fp;
    NET_ADDR a;
    time_t when;
    long seeded = 0;

    if ( guard_loaded )
        return;
    guard_loaded = true;
    guard_store_init( &guard_trust, guard_trust_rows, GUARD_TRUST_MAX );
    if ( guard_report_at == 0 )
        guard_report_at = current_time;

    switch ( guard_store_load( &guard_trust, GUARD_TRUST_FILE, current_time ) )
    {
    case GUARD_LOAD_ABSENT:
        break;                          /* no record yet: start one below */
    case GUARD_LOAD_UNREADABLE:
        /* There, and not read whole (permission, an I/O error). Only a file
           that is truly absent may be started again from the journals:
           this one may hold more than memory does, so the store is read-
           only until a reboot finds it readable (review of f1388da0). */
        snprintf( line, sizeof(line),
                  "Connection guard: " GUARD_TRUST_FILE " exists but could not be read "
                  "whole (%d addresses read); it will not be written until a reboot "
                  "can read it.", guard_trust.count );
        log_string( line );
        return;
    default:
        if ( guard_trust.bad_lines > 0 )
        {
            /* An unfinished last record or a line that is no record: the
               good ones are kept and the file is written again without the
               rest. */
            snprintf( line, sizeof(line),
                      "Connection guard: %d line%s of " GUARD_TRUST_FILE " were not "
                      "records (an unfinished write, a bad time); rewriting without them.",
                      guard_trust.bad_lines, guard_trust.bad_lines == 1 ? "" : "s" );
            log_string( line );
            guard_trust_rewrite();
        }
        return;
    }

    if ( ( fp = fopen( GUARD_LOGINS_FILE, "r" ) ) != NULL )
    {
        while ( fgets( line, sizeof(line), fp ) != NULL )
            if ( guard_seed_login_row( line, &a, &when ) && guard_store_note( &guard_trust, &a, when ) )
                seeded++;
        fclose( fp );
    }
    if ( ( fp = fopen( GUARD_TOC_LOG, "r" ) ) != NULL )
    {
        while ( fgets( line, sizeof(line), fp ) != NULL )
            if ( guard_seed_log_line( line, &a, &when ) && guard_store_note( &guard_trust, &a, when ) )
                seeded++;
        fclose( fp );
    }
    snprintf( line, sizeof(line),
              "Connection guard: started the record of players' addresses from the journals: "
              "%d addresses from %ld login records naming one.", guard_trust.count, seeded );
    log_string( line );
    guard_trust_rewrite();
}

/* At boot, before the game loop: toc.log runs to megabytes, and reading it
   at the first connection would be a stall of the kind this file exists to
   end. */
void conn_guard_boot( void )
{
    guard_load();
    guard_pause_load();
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

/* What staff see for an entry: its address, and for IPv6 that the guard
   counts the whole /64 -- never the internal key as though it were one. */
static void guard_ip_text( const GUARD_ENTRY *e, char *buf, size_t size )
{
    if ( e->text[0] == '\0' )
        toc_strlcpy( buf, "?", size );
    else if ( net_addr_key_is_v6( e->ip ) )
        snprintf( buf, size, "%s (its /64)", e->text );
    else
        toc_strlcpy( buf, e->text, size );
}

/* Worth keeping across a restart: a pause or flood standing, the pauses
   of the last week that make the next one longer, or strikes still in
   their window. */
static bool guard_entry_kept( const GUARD_ENTRY *e )
{
    if ( !e->used || e->text[0] == '\0' )
        return false;
    return e->blocked_until > current_time || e->flood_until > current_time
        || ( e->blocks > 0 && current_time - e->last_block <= GUARD_HISTORY )
        || ( e->conns > 0 && current_time - e->window_start <= GUARD_STRIKE_WINDOW );
}

/* The whole table, written aside and renamed in (GUARD_PAUSE_FILE). */
static void guard_pause_save( void )
{
    static time_t said;
    FILE *fp;
    int i;

    guard_pause_dirty = false;
    guard_pause_saved = current_time;
    if ( guard_pause_read_only )
        return;                 /* the boot's notice said so */
    if ( ( fp = fopen( GUARD_PAUSE_FILE ".tmp", "w" ) ) == NULL )
    {
        if ( current_time - said >= 3600 )
        {
            said = current_time;
            log_string( "Connection guard: could not write " GUARD_PAUSE_FILE "; will try again." );
        }
        guard_pause_dirty = true;
        return;
    }
    fprintf( fp, "# address\tpaused until\tpauses this week\tlast pause\tflood until"
                 "\tstrike window\tstrikes\trefused in all: connguard.c\n" );
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        const GUARD_ENTRY *e = &guard_table[i];

        if ( !guard_entry_kept( e ) )
            continue;
        fprintf( fp, "%s\t%ld\t%d\t%ld\t%ld\t%ld\t%d\t%ld\n", e->text,
                 (long) e->blocked_until, e->blocks, (long) e->last_block,
                 (long) e->flood_until, (long) e->window_start, e->conns,
                 e->refused_total );
    }
    if ( !temp_file_commit( fp, GUARD_PAUSE_FILE ".tmp", GUARD_PAUSE_FILE ) )
    {
        guard_pause_dirty = true;
        if ( current_time - said >= 3600 )
        {
            said = current_time;
            log_string( "Connection guard: could not write " GUARD_PAUSE_FILE "; will try again." );
        }
    }
}

/* A whole decimal field, or -1. */
static long guard_number( const char *text )
{
    char *end;
    long n;

    if ( text == NULL || !isdigit( (unsigned char) text[0] ) )
        return -1;
    errno = 0;
    n = strtol( text, &end, 10 );
    if ( errno == ERANGE || *end != '\0' )
        return -1;
    return n;
}

/* Boot: the pauses, floods and strikes a restart must not forget. Only a
   whole record counts, and nothing from further ahead than the longest
   pause can be. */
static void guard_pause_load( void )
{
    char line[256];
    FILE *fp;
    int kept = 0, paused = 0;
    bool failed = false;

    if ( ( fp = fopen( GUARD_PAUSE_FILE, "r" ) ) == NULL )
    {
        int err = errno;

        if ( err == ENOENT )
            return;
        guard_pause_read_only = true;
        snprintf( line, sizeof(line),
                  "Connection guard: could not read " GUARD_PAUSE_FILE " (%s); it will not be "
                  "written over until a boot reads it.", strerror( err ) );
        log_string( line );
        return;
    }
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char *field[8], *p = line;
        size_t len = strlen( line );
        long v[7];
        NET_ADDR a;
        GUARD_ENTRY *e;
        int n;

        if ( len == sizeof(line) - 1 && line[len - 1] != '\n' )
        {
            int c;

            while ( ( c = getc( fp ) ) != EOF && c != '\n' )
                ;
            continue;
        }
        if ( line[0] == '#' || len == 0 || line[len - 1] != '\n' )
            continue;
        line[--len] = '\0';
        for ( n = 0; n < 8; n++ )
        {
            field[n] = p;
            if ( n < 7 )
            {
                if ( ( p = strchr( p, '\t' ) ) == NULL )
                    break;
                *p++ = '\0';
            }
        }
        if ( n < 8 || strchr( field[7], '\t' ) != NULL || !net_addr_parse( field[0], &a ) )
            continue;
        for ( n = 0; n < 7; n++ )
            if ( ( v[n] = guard_number( field[n + 1] ) ) < 0 )
                break;
        if ( n < 7 || v[1] > 64 || v[5] > 100000
        ||   v[0] > (long) current_time + GUARD_BLOCK_MAX
        ||   v[3] > (long) current_time + GUARD_FLOOD_SECS
        ||   v[2] > (long) current_time + 86400 || v[4] > (long) current_time + 86400 )
            continue;
        if ( !guard_applies( net_addr_guard_key( &a ) ) )
            continue;
        e = guard_find( net_addr_guard_key( &a ), true );
        net_addr_text( &a, e->text, sizeof(e->text) );
        e->blocked_until = (time_t) v[0];
        e->blocks        = (int) v[1];
        e->last_block    = (time_t) v[2];
        e->flood_until   = (time_t) v[3];
        e->window_start  = (time_t) v[4];
        e->conns         = (int) v[5];
        e->refused_total = v[6];
        e->last_seen     = current_time;
        if ( !guard_entry_kept( e ) )
        {
            e->used = false;
            continue;
        }
        kept++;
        if ( e->blocked_until > current_time || e->flood_until > current_time )
            paused++;
    }
    if ( ferror( fp ) )
        failed = true;
    if ( fclose( fp ) != 0 )
        failed = true;
    if ( failed )
    {
        guard_pause_read_only = true;
        snprintf( line, sizeof(line),
                  "Connection guard: " GUARD_PAUSE_FILE " was read only in part (%d address%s); "
                  "it will not be written over until a boot reads it whole.",
                  kept, kept == 1 ? "" : "es" );
        log_string( line );
    }
    snprintf( line, sizeof(line),
              "Connection guard: %d address%s remembered from before the boot, %d paused now.",
              kept, kept == 1 ? "" : "es", paused );
    log_string( line );
}

/* A refused connection, in the log by address: the first at once, then
   one line a GUARD_REFUSAL_LOG_SECS saying how many came since. */
static void guard_log_refusal( GUARD_ENTRY *e, const char *why )
{
    char addr[NET_ADDR_TEXT + 16];
    char buf[MAX_STRING_LENGTH];

    e->refusals_unlogged++;
    if ( e->refusal_logged != 0 && current_time - e->refusal_logged < GUARD_REFUSAL_LOG_SECS )
        return;
    guard_ip_text( e, addr, sizeof(addr) );
    snprintf( buf, sizeof(buf), "Connection guard: refused %ld connection%s from %s (%s; "
              "%ld refused in all, pause %d this week, %ld minutes left).",
              e->refusals_unlogged, e->refusals_unlogged == 1 ? "" : "s", addr, why,
              e->refused_total, e->blocks,
              (long) ( UMAX( e->blocked_until, e->flood_until ) - current_time + 59 ) / 60 );
    log_string( buf );
    e->refusal_logged = current_time;
    e->refusals_unlogged = 0;
}

/* Staff are told, and the log keeps it. `level` is the least trust that
   hears it: LEVEL_IMMORTAL for a notice naming only an address, and a
   character's staff_notice_level for one naming them, so a wizinvis
   creator logging in is never named to staff who cannot see him (review
   of f1388da0, 2026-11-06). */
static void guard_say( const char *text, int level )
{
    log_string( text );
    wizinfo( text, UMAX( level, LEVEL_IMMORTAL ) );
}

/* A pause: no new characters from it for a while. Logins still work, and
   one lifts it. */
static void guard_block( GUARD_ENTRY *e, const char *why )
{
    char addr[NET_ADDR_TEXT + 16];
    char buf[MAX_STRING_LENGTH];
    long length;
    int shift;

    if ( e->last_block == 0 || current_time - e->last_block > GUARD_HISTORY )
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
    guard_ip_text( e, addr, sizeof(addr) );
    snprintf( buf, sizeof(buf),
              "Connection guard: %s paused for %ld hours (pause %d this week; %s; no player has "
              "logged in from it in %d days). Its connections are refused until then. "
              "DNS ALLOW %s lifts it.",
              addr, length / 3600, e->blocks, why, GUARD_TRUST_DAYS, addr );
    guard_say( buf, LEVEL_IMMORTAL );
    guard_pause_save();
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
 * closing. Counts the connection's minute against its address; a paused or
 * flooding address is refused (owner, 2026-11-13).
 */
const char *conn_guard_admit( DESCRIPTOR_DATA *d, char *buf, size_t size )
{
    DESCRIPTOR_DATA *od;
    GUARD_ENTRY *e;
    char addr[NET_ADDR_TEXT + 16];
    char note[MAX_STRING_LENGTH];
    int pending = 0;
    int everyone = 0;

    if ( d == NULL || !guard_watches( d->ip, d ) )
        return NULL;
    e = guard_find( d->ip, true );
    e->last_seen = current_time;
    toc_strlcpy( e->text, d->addr_text, sizeof(e->text) );

    if ( e->flood_until > current_time )
    {
        long left = (long) ( e->flood_until - current_time );

        guard_refused++;
        e->refused_total++;
        guard_pause_dirty = true;
        guard_log_refusal( e, "a flood" );
        /* No reply: reset, as a closed port is (owner, 2026-11-13: "i'm
           not sure paused should get any notification"; make scanners
           give up). */
        d->guard_reset = TRUE;
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
        guard_ip_text( e, addr, sizeof(addr) );
        snprintf( note, sizeof(note),
                  "Connection guard: %s refused for %d minutes (%d connections in a minute; "
                  "no player has logged in from it in %d days). DNS ALLOW %s lifts it.",
                  addr, GUARD_FLOOD_SECS / 60, guard_limit( "TOC_GUARD_FLOOD", GUARD_FLOOD ),
                  GUARD_TRUST_DAYS, addr );
        guard_say( note, LEVEL_IMMORTAL );
        guard_pause_save();
        d->guard_reset = TRUE;
        snprintf( buf, size, "Connections from your address are paused for a while.\n\r" );
        return buf;
    }
    if ( e->burst >= guard_limit( "TOC_GUARD_BURST", GUARD_BURST )
    &&   e->blocked_until <= current_time )
        guard_block( e, "too many connections in a minute" );

    /* Paused: refused before the greeting (owner, 2026-11-13). The
       address is no player's (guard_watches), so nobody playing is shut
       out; a new player behind it asks staff for DNS ALLOW. */
    if ( e->blocked_until > current_time )
    {
        long left = (long) ( e->blocked_until - current_time );

        guard_refused++;
        e->refused_total++;
        guard_pause_dirty = true;
        guard_log_refusal( e, "paused" );
        d->guard_reset = TRUE;
        snprintf( buf, size,
                  "Connections from your address are paused for %ld more minute%s.\n\r",
                  ( left + 59 ) / 60, ( left + 59 ) / 60 == 1 ? "" : "s" );
        return buf;
    }

    /* A connection whose client has already hung up is not waiting at a
       prompt: it is closed on the next pass. All the connections waiting
       on the port are accepted in one pass now (comm.c, init_descriptors),
       so one that came and went -- a health probe, a port scan -- can still
       be in the list beside the client that came after it, and counting it
       turned that client away as "very busy" (review, 2026-11-12). */
    for ( od = descriptor_list; od != NULL; od = od->next )
        if ( od != d && od->connected != CON_PLAYING && !descriptor_hung_up( od ) )
        {
            everyone++;
            if ( od->ip == d->ip )
                pending++;
        }
    /* The whole game's budget of connections not yet playing: a flood from
       many addresses at once is shed here, untrusted connections first --
       a player's address returned above and is never refused by it, and
       nobody already playing is touched (review, 2026-11-06). */
    if ( everyone >= guard_limit( "TOC_GUARD_GLOBAL_PENDING", GUARD_GLOBAL_PENDING ) )
    {
        static time_t said;

        guard_refused++;
        if ( current_time - said >= GUARD_NOTICE_SECS )
        {
            said = current_time;
            snprintf( note, sizeof(note),
                      "Connection guard: %d connections are waiting at the login prompts; "
                      "new ones from addresses no player uses are refused for now.", everyone );
            guard_say( note, LEVEL_IMMORTAL );
        }
        snprintf( buf, size, "The game is very busy; please try again in a minute.\n\r" );
        return buf;
    }
    if ( pending >= GUARD_PENDING_MAX )
    {
        guard_refused++;
        if ( guard_notice_due( e ) )
        {
            guard_ip_text( e, addr, sizeof(addr) );
            snprintf( note, sizeof(note),
                      "Connection guard: %s refused a connection: %d already waiting at the login "
                      "prompt (told again in %d minutes at most).",
                      addr, pending, GUARD_NOTICE_SECS / 60 );
            guard_say( note, LEVEL_IMMORTAL );
        }
        guard_log_refusal( e, "too many waiting at the login prompt" );
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
    char buf[MAX_STRING_LENGTH];
    const char *how;
    const char *exempt = NULL;
    int strikes = guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES );

    if ( d == NULL || d->guard_refused || !guard_applies( d->ip )
    ||   d->guard_named || d->connected == CON_PLAYING )
        return;
    if ( !d->first_line_read )
        guard_silent++;
    how = d->first_line_read ? "closed before a password prompt" : "closed without a word";
    /* Logged by address, every one (owner, 2026-11-13): with the reason
       when it does not count. */
    if ( d->guard_idle_closed )
        exempt = "timed out at the prompt";
    else if ( d->guard_mssp )
        exempt = "an MSSP poll";
    else if ( d->guard_proxied )
        exempt = "the web client";
    else if ( !guard_watches( d->ip, d ) )
        exempt = "a player's address";
    if ( exempt != NULL )
    {
        snprintf( buf, sizeof(buf), "Connection guard: %s %s (%s; not counted).",
                  d->addr_text, how, exempt );
        log_string( buf );
        return;
    }
    e = guard_find( d->ip, true );
    e->last_seen = current_time;
    toc_strlcpy( e->text, d->addr_text, sizeof(e->text) );
    if ( e->window_start == 0 || current_time - e->window_start > GUARD_STRIKE_WINDOW )
    {
        e->window_start = current_time;
        e->conns = 0;
    }
    e->conns++;
    snprintf( buf, sizeof(buf), "Connection guard: %s %s (strike %d of %d in %d hours).",
              d->addr_text, how, e->conns, strikes, GUARD_STRIKE_WINDOW / 3600 );
    log_string( buf );
    guard_pause_dirty = true;
    if ( e->conns >= strikes && e->blocked_until <= current_time )
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
    char addr[NET_ADDR_TEXT + 16];
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
        guard_ip_text( e, addr, sizeof(addr) );
        snprintf( note, sizeof(note),
                  "Connection guard: new character '%s' refused from paused %s "
                  "(%ld minutes left). DNS ALLOW %s lets it in.",
                  name != NULL ? name : "?", addr, ( left + 59 ) / 60, addr );
        guard_say( note, LEVEL_IMMORTAL );
    }
    snprintf( buf, size,
              "New characters cannot be made from your address for %ld more minute%s.\n\r"
              "If you already play here, log in with your character.\n\rName: ",
              ( left + 59 ) / 60, ( left + 59 ) / 60 == 1 ? "" : "s" );
    return buf;
}

/* A login's address, written down when a day has passed since the last
   line that landed for it; a write that fails is tried again (here at the
   next login, or by conn_guard_tick). */
static void guard_trust_persist( GUARD_TRUST *t )
{
    static time_t said;

    if ( t == NULL || guard_trust.read_only || !guard_store_due( t ) )
        return;
    if ( guard_trust.file_lines >= GUARD_TRUST_FILE_MAX )
    {
        guard_trust_rewrite();
        return;
    }
    if ( guard_store_append( &guard_trust, GUARD_TRUST_FILE, t ) )
        return;
    if ( current_time - said >= 3600 )
    {
        said = current_time;
        log_string( "Connection guard: could not write " GUARD_TRUST_FILE "; will try again." );
    }
}

/* A player logged in (or staff allowed the address): it is trusted for
   GUARD_TRUST_DAYS from now, and any pause on it ends. `who` says why, for
   staff; NULL when the caller tells them itself. `notice_level` is the
   least trust that may read `who` -- the player's staff_notice_level. */
void conn_guard_trust( const NET_ADDR *a, const char *who, int notice_level )
{
    GUARD_ENTRY *e;
    char addr[NET_ADDR_TEXT + 16];
    char buf[MAX_STRING_LENGTH];
    uint32_t ip = net_addr_guard_key( a );

    if ( !guard_applies( ip ) )
        return;
    guard_load();
    if ( ( e = guard_find( ip, false ) ) != NULL )
    {
        if ( e->text[0] == '\0' )
            net_addr_text( a, e->text, sizeof(e->text) );
        if ( who != NULL && ( e->blocked_until > current_time || e->flood_until > current_time ) )
        {
            guard_ip_text( e, addr, sizeof(addr) );
            snprintf( buf, sizeof(buf), "Connection guard: pause on %s lifted -- %s.", addr, who );
            guard_say( buf, notice_level );
        }
        if ( e->blocked_until > 0 || e->flood_until > 0 || e->conns > 0 )
        {
            e->blocked_until = e->flood_until = 0;
            e->conns = e->burst = 0;
            guard_pause_save();
        }
    }
    guard_trust_persist( guard_store_note( &guard_trust, a, current_time ) );
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
    /* A login whose line did not land is written again, so the record does
       not wait on that player's next login. */
    if ( guard_loaded && current_time >= guard_retry_at )
    {
        guard_retry_at = current_time + 300;
        for ( i = 0; i < guard_trust.count; i++ )
            guard_trust_persist( &guard_trust.rows[i] );
    }
    /* Strikes reach the file within GUARD_SAVE_SECS; refusals not yet in
       the log are written once their address goes quiet. */
    if ( guard_pause_dirty && current_time - guard_pause_saved >= GUARD_SAVE_SECS )
        guard_pause_save();
    for ( i = 0; i < GUARD_SLOTS; i++ )
        if ( guard_table[i].used && guard_table[i].refusals_unlogged > 0
        &&   current_time - guard_table[i].refusal_logged >= GUARD_REFUSAL_LOG_SECS )
        {
            guard_table[i].refusals_unlogged--;   /* guard_log_refusal counts it again */
            guard_log_refusal( &guard_table[i], "since the last line" );
        }
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
    char addr[NET_ADDR_TEXT + 16];
    int shown = 0;
    int i;

    guard_load();
    snprintf( buf, sizeof(buf),
              "Connection guard: %d active player addresses (a player logged in from each\n\r"
              "in the last %d days) are never limited or paused; an immortal's BAN still is.\n\r"
              "Untrusted: paused after %d connections in %d hours that reach no password\n\r"
              "prompt, or %d in a minute, for %d hours doubling to %d days. A paused\n\r"
              "address is refused at connect; DNS ALLOW lifts it. %d in a minute is refused\n\r"
              "for %d minutes. Pauses survive a restart (" GUARD_PAUSE_FILE ").\n\r"
              "Since the last hourly line: %ld silent, %ld refused,\n\r"
              "%ld new characters refused.\n\r",
              guard_active_count(), GUARD_TRUST_DAYS, guard_limit( "TOC_GUARD_STRIKES", GUARD_STRIKES ),
              GUARD_STRIKE_WINDOW / 3600, guard_limit( "TOC_GUARD_BURST", GUARD_BURST ),
              GUARD_BLOCK_BASE / 3600, GUARD_BLOCK_MAX / 86400,
              guard_limit( "TOC_GUARD_FLOOD", GUARD_FLOOD ), GUARD_FLOOD_SECS / 60,
              guard_silent, guard_refused, guard_new_refused );
    send_to_char( buf, ch );
    if ( guard_pause_read_only )
        send_to_char( "  NOT KEPT: " GUARD_PAUSE_FILE " could not be read whole at boot; pauses\n\r"
                      "  hold in memory and nothing is written to it until a boot reads it.\n\r", ch );
    if ( guard_trust.read_only )
        send_to_char( "The record of players' addresses could not be read at boot: what was\n\r"
                      "read is used, and nothing is written to it until a reboot can read it.\n\r",
                      ch );
    for ( i = 0; i < GUARD_SLOTS; i++ )
    {
        const GUARD_ENTRY *e = &guard_table[i];

        if ( !e->used || ( e->blocked_until <= current_time && e->flood_until <= current_time ) )
            continue;
        guard_ip_text( e, addr, sizeof(addr) );
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

/* Staff DNS ALLOW <address>: lift a pause and trust the address -- IPv4,
   or IPv6, whose whole /64 the guard counts as one, exactly as admission
   keys it. */
bool conn_guard_allow( const char *text )
{
    NET_ADDR a;

    if ( !net_addr_parse( text, &a ) )
        return false;
    conn_guard_trust( &a, NULL, LEVEL_IMMORTAL );   /* DNS ALLOW says so itself */
    return true;
}
