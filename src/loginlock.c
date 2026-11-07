/*
 * Wrong passwords: warnings, escalating lockouts, and alerts (2026-11-06).
 *
 * Owner, 2026-11-06: "If the wrong password is entered over x times I want
 * to ban the IP for x time. Increasing with warning." This replaces the
 * login throttle that lived in comm.c (five failures in ten minutes, then
 * thirty seconds doubling to a fifteen-minute cap, in memory, 64 addresses,
 * and no word to the player before the door shut).
 *
 *  - Every wrong password says how many more an address may make, and how
 *    long the lockout will be, before it is locked out.
 *  - LOCK_THRESHOLD (5) wrong passwords from one address within LOCK_WINDOW
 *    (15 minutes) lock it out, refused before the greeting. Each lockout in
 *    the last LOCK_MEMORY (7 days) makes the next longer: 15 minutes, an
 *    hour, 6 hours, a day, then 7 days (lock_ladder).
 *  - An address a player has logged in from in the last 90 days (the
 *    connection guard's record) is never locked out for more than
 *    LOCK_TRUSTED_MAX (an hour): a player who forgot a password must not
 *    shut their household out for a week. It is still locked out -- the
 *    owner's rule is that a player's address is exempt from the scanner
 *    guard, never from password limits.
 *  - Lockouts and their history are written to log/login_lockouts.tsv and
 *    read at boot, so a restart or a deploy does not wipe them.
 *  - A successful login clears an address's count only when every failure
 *    counted was for the character who just logged in -- a player who
 *    mistyped their own password. Logging into one's own character between
 *    guesses at somebody else's no longer resets the count.
 *  - Failures are also counted per character, across addresses: the
 *    character is told at their next login how many failed password
 *    attempts were made on them and from how many addresses (never in
 *    words a client could take for its own login failing), and staff are told (WIZINFO,
 *    at the character's staff_notice_level) when one character draws
 *    LOCK_ACCOUNT_ALERT (10) in an hour -- guessing spread across many
 *    addresses, which no per-address limit sees.
 *  - Staff DNS GUARD lists lockouts; DNS ALLOW <address> lifts one.
 *
 * Keyed by the connection's guard key (net_addr_guard_key): an IPv4 address,
 * or an IPv6 /64, so stepping through addresses inside one does not escape.
 * Loopback is exempt unless TOC_THROTTLE_LOOPBACK=1 (the web bridge names
 * its players' real addresses in a PROXY header, so they are counted by
 * theirs). TOC_LOGIN_LOCK_SECS sets the first rung for tests, and every
 * other rung scales with it.
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

#define LOCK_SLOTS          1024
#define LOCK_THRESHOLD         5
#define LOCK_WINDOW          900        /* failures counted within 15 minutes */
#define LOCK_MEMORY    (7 * 86400)      /* lockouts remembered for a week     */
#define LOCK_FIRST           900        /* the first rung, 15 minutes         */
#define LOCK_TRUSTED_MAX    3600        /* a player's address: an hour at most */
#define LOCK_NAME_SLOTS      256
#define LOCK_ACCOUNT_ALERT    10        /* wrong passwords on one character... */
#define LOCK_ACCOUNT_WINDOW 3600        /* ...within an hour                   */
#define LOCK_KEYS              8        /* addresses remembered per character  */
#define LOCK_FILE   "../log/login_lockouts.tsv"

static const long lock_ladder[] = { 900, 3600, 6 * 3600, 86400, 7 * 86400 };
#define LOCK_RUNGS ( (int) ( sizeof(lock_ladder) / sizeof(lock_ladder[0]) ) )

typedef struct lock_entry
{
    bool     used;
    uint32_t key;
    char     text[NET_ADDR_TEXT];
    int      failures;          /* within LOCK_WINDOW */
    time_t   last_fail;
    char     fail_name[16];     /* the character every counted failure named */
    bool     mixed;             /* failures named more than one character */
    time_t   locked_until;
    int      lockouts;          /* within LOCK_MEMORY of last_lockout */
    time_t   last_lockout;
} LOCK_ENTRY;

typedef struct lock_name
{
    bool     used;
    char     name[16];
    int      failures;          /* since the character last logged in */
    int      recent;            /* within LOCK_ACCOUNT_WINDOW of recent_start */
    time_t   recent_start;
    time_t   last_fail;
    time_t   alerted_at;
    uint32_t keys[LOCK_KEYS];
    int      nkeys;
    int      more_keys;         /* addresses past LOCK_KEYS */
} LOCK_NAME;

static LOCK_ENTRY lock_table[LOCK_SLOTS];
static LOCK_NAME  lock_names[LOCK_NAME_SLOTS];

/* Seconds for the rung given, scaled by TOC_LOGIN_LOCK_SECS for tests. */
static long lock_scaled( long seconds )
{
    static long first = -1;

    if ( first < 0 )
    {
        const char *opt = getenv( "TOC_LOGIN_LOCK_SECS" );
        long n = opt != NULL ? strtol( opt, NULL, 10 ) : 0;

        first = n > 0 && n <= LOCK_FIRST ? n : LOCK_FIRST;
    }
    return UMAX( 1, seconds * first / LOCK_FIRST );
}

/* How long a lockout lasts, given the lockouts already this week. */
static long lock_duration( int lockouts_before, bool trusted )
{
    long length = lock_ladder[URANGE( 0, lockouts_before, LOCK_RUNGS - 1 )];

    if ( trusted && length > LOCK_TRUSTED_MAX )
        length = LOCK_TRUSTED_MAX;
    return lock_scaled( length );
}

/* "15 minutes", "1 hour", "7 days", "40 seconds": rounded up, never 0. */
static void lock_say_time( long seconds, char *buf, size_t size )
{
    long n;
    const char *unit;

    if ( seconds >= 86400 && seconds % 86400 == 0 )
    {
        n = seconds / 86400;
        unit = "day";
    }
    else if ( seconds >= 3600 && seconds % 3600 == 0 )
    {
        n = seconds / 3600;
        unit = "hour";
    }
    else if ( seconds >= 120 )
    {
        n = ( seconds + 59 ) / 60;
        unit = "minute";
    }
    else
    {
        n = UMAX( 1, seconds );
        unit = "second";
    }
    snprintf( buf, size, "%ld %s%s", n, unit, n == 1 ? "" : "s" );
}

static bool lock_applies( const DESCRIPTOR_DATA *d )
{
    const char *opt;

    if ( d == NULL || d->ip == 0 )
        return false;
    if ( !net_addr_key_is_v6( d->ip ) && ( ntohl( d->ip ) >> 24 ) == 127 )
    {
        opt = getenv( "TOC_THROTTLE_LOOPBACK" );
        return opt != NULL && opt[0] == '1';
    }
    return true;
}

static LOCK_ENTRY *lock_find( uint32_t key )
{
    int i;

    for ( i = 0; i < LOCK_SLOTS; i++ )
        if ( lock_table[i].used && lock_table[i].key == key )
            return &lock_table[i];
    return NULL;
}

/* Find or claim. Never recycle a standing lockout while anything else will
   do; otherwise the entry quiet longest gives way. */
static LOCK_ENTRY *lock_claim( uint32_t key, const char *text )
{
    LOCK_ENTRY *e, *victim = NULL;
    int i;

    if ( ( e = lock_find( key ) ) != NULL )
        return e;
    for ( i = 0; i < LOCK_SLOTS; i++ )
    {
        e = &lock_table[i];
        if ( !e->used )
        {
            victim = e;
            break;
        }
        if ( victim == NULL
        ||   ( victim->locked_until > current_time ) > ( e->locked_until > current_time )
        ||   ( ( victim->locked_until > current_time ) == ( e->locked_until > current_time )
            && UMAX( e->last_fail, e->last_lockout ) < UMAX( victim->last_fail, victim->last_lockout ) ) )
            victim = e;
    }
    memset( victim, 0, sizeof(*victim) );
    victim->used = true;
    victim->key = key;
    toc_strlcpy( victim->text, text != NULL ? text : "?", sizeof(victim->text) );
    return victim;
}

/* The whole list of lockouts worth remembering, written aside and renamed. */
static void lock_save( void )
{
    FILE *fp;
    int i;

    if ( ( fp = fopen( LOCK_FILE ".tmp", "w" ) ) == NULL )
    {
        log_string( "Login lockout: could not write " LOCK_FILE "." );
        return;
    }
    fprintf( fp, "# address\tlocked until\tlockouts\tlast lockout: loginlock.c\n" );
    for ( i = 0; i < LOCK_SLOTS; i++ )
    {
        const LOCK_ENTRY *e = &lock_table[i];

        if ( !e->used || e->lockouts <= 0 || e->text[0] == '\0' )
            continue;
        if ( e->locked_until <= current_time && current_time - e->last_lockout > LOCK_MEMORY )
            continue;
        fprintf( fp, "%s\t%ld\t%d\t%ld\n", e->text, (long) e->locked_until,
                 e->lockouts, (long) e->last_lockout );
    }
    if ( !temp_file_commit( fp, LOCK_FILE ".tmp", LOCK_FILE ) )
        log_string( "Login lockout: could not write " LOCK_FILE "." );
}

/* A whole decimal field, or -1. */
static long lock_number( const char *text )
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

/* Boot: the lockouts a restart must not forget. */
void login_lock_boot( void )
{
    char line[256];
    FILE *fp;
    int kept = 0;

    if ( ( fp = fopen( LOCK_FILE, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char *field[4], *p = line;
        size_t len = strlen( line );
        NET_ADDR a;
        LOCK_ENTRY *e;
        long until, count, last;
        int n;

        if ( line[0] == '#' || len == 0 || line[len - 1] != '\n' )
            continue;                   /* a comment, or an unfinished line */
        line[--len] = '\0';
        for ( n = 0; n < 4; n++ )
        {
            field[n] = p;
            if ( n < 3 )
            {
                if ( ( p = strchr( p, '\t' ) ) == NULL )
                    break;
                *p++ = '\0';
            }
        }
        if ( n < 4 || strchr( field[3], '\t' ) != NULL || !net_addr_parse( field[0], &a ) )
            continue;
        until = lock_number( field[1] );
        count = lock_number( field[2] );
        last  = lock_number( field[3] );
        if ( until < 0 || count < 1 || count > 1000 || last <= 0 )
            continue;
        /* Nothing believed from the future past the longest rung. */
        if ( until > (long) current_time + lock_ladder[LOCK_RUNGS - 1]
        ||   last > (long) current_time + 86400 )
            continue;
        if ( until <= (long) current_time && (long) current_time - last > LOCK_MEMORY )
            continue;
        e = lock_claim( net_addr_guard_key( &a ), field[0] );
        e->locked_until = (time_t) until;
        e->lockouts = (int) count;
        e->last_lockout = (time_t) last;
        kept++;
    }
    fclose( fp );
    if ( kept > 0 )
    {
        snprintf( line, sizeof(line), "Login lockout: %d address%s remembered from before the boot.",
                  kept, kept == 1 ? "" : "es" );
        log_string( line );
    }
}

/* Seconds left on an address's lockout, or 0. */
long login_lock_remaining( const DESCRIPTOR_DATA *d )
{
    LOCK_ENTRY *e;

    if ( !lock_applies( d ) || ( e = lock_find( d->ip ) ) == NULL )
        return 0;
    return e->locked_until > current_time ? (long) ( e->locked_until - current_time ) : 0;
}

/* What a locked-out connection is told before it is closed. */
void login_lock_refusal( const DESCRIPTOR_DATA *d, char *buf, size_t size )
{
    char left[64];

    lock_say_time( login_lock_remaining( d ), left, sizeof(left) );
    snprintf( buf, size,
              "Too many failed login attempts from your address: it is locked out for %s more.\n\r"
              "Each lockout within a week lasts longer than the last.\n\r", left );
}

static LOCK_NAME *lock_name_claim( const char *name )
{
    LOCK_NAME *n, *victim = NULL;
    int i;

    for ( i = 0; i < LOCK_NAME_SLOTS; i++ )
        if ( lock_names[i].used && !str_cmp( lock_names[i].name, name ) )
            return &lock_names[i];
    for ( i = 0; i < LOCK_NAME_SLOTS; i++ )
    {
        n = &lock_names[i];
        if ( !n->used )
        {
            victim = n;
            break;
        }
        if ( victim == NULL || n->last_fail < victim->last_fail )
            victim = n;
    }
    memset( victim, 0, sizeof(*victim) );
    victim->used = true;
    toc_strlcpy( victim->name, name, sizeof(victim->name) );
    return victim;
}

/* A wrong password for `ch` (the copy being logged in) counted against the
   character, wherever it came from. */
static void lock_count_character( const DESCRIPTOR_DATA *d, CHAR_DATA *ch )
{
    LOCK_NAME *n;
    char buf[MAX_STRING_LENGTH];
    int i;

    if ( ch == NULL || ch->name == NULL || ch->name[0] == '\0' )
        return;
    n = lock_name_claim( ch->name );
    n->failures++;
    n->last_fail = current_time;
    if ( n->recent_start == 0 || current_time - n->recent_start > LOCK_ACCOUNT_WINDOW )
    {
        n->recent_start = current_time;
        n->recent = 0;
    }
    n->recent++;
    for ( i = 0; i < n->nkeys && n->keys[i] != d->ip; i++ )
        ;
    if ( i == n->nkeys )
    {
        if ( n->nkeys < LOCK_KEYS )
            n->keys[n->nkeys++] = d->ip;
        else
            n->more_keys++;
    }
    if ( n->recent >= LOCK_ACCOUNT_ALERT
    &&   ( n->alerted_at == 0 || current_time - n->alerted_at >= LOCK_ACCOUNT_WINDOW ) )
    {
        n->alerted_at = current_time;
        snprintf( buf, sizeof(buf),
                  "Login lockout: %d wrong passwords for %s in the last hour, from %d%s address%s.",
                  n->recent, ch->name, n->nkeys, n->more_keys > 0 ? "+" : "",
                  n->nkeys == 1 && n->more_keys == 0 ? "" : "es" );
        log_string( buf );
        wizinfo( buf, staff_notice_level( ch, LEVEL_IMMORTAL ) );
    }
}

/*
 * A wrong password: counted, and the connection told what comes next --
 * how many more it may make, or that its address is now locked out and for
 * how long. The caller closes the connection. `ch` is the character the
 * password was for.
 */
void login_wrong_password( DESCRIPTOR_DATA *d, CHAR_DATA *ch )
{
    LOCK_ENTRY *e;
    char buf[MAX_STRING_LENGTH];
    char length[64];
    const char *name = ch != NULL && ch->name != NULL ? ch->name : "";
    bool trusted;
    long dur;

    /* A Mudlet login told how it ended, before the close (comm.c). */
    if ( d != NULL && d->gmcp_login_state == 2 )
    {
        gmcp_login_forget( d );
        gmcp_login_result( d, false, "Wrong password." );
    }

    lock_count_character( d, ch );
    if ( !lock_applies( d ) )
    {
        write_to_buffer( d, "Wrong password.\n\r", 0 );
        return;
    }
    e = lock_claim( d->ip, d->addr_text );
    toc_strlcpy( e->text, d->addr_text, sizeof(e->text) );
    if ( e->last_fail != 0 && current_time - e->last_fail > LOCK_WINDOW )
    {
        e->failures = 0;                /* honest slips do not pile up */
        e->fail_name[0] = '\0';
        e->mixed = false;
    }
    if ( e->last_lockout != 0 && current_time - e->last_lockout > LOCK_MEMORY )
        e->lockouts = 0;
    e->failures++;
    e->last_fail = current_time;
    if ( e->fail_name[0] == '\0' )
        toc_strlcpy( e->fail_name, name, sizeof(e->fail_name) );
    else if ( str_cmp( e->fail_name, name ) )
        e->mixed = true;

    trusted = conn_guard_trusted( d->ip );
    dur = lock_duration( e->lockouts, trusted );
    lock_say_time( dur, length, sizeof(length) );

    if ( e->failures < LOCK_THRESHOLD )
    {
        int left = LOCK_THRESHOLD - e->failures;

        snprintf( buf, sizeof(buf),
                  "Wrong password.\n\r"
                  "%d more wrong password%s from your address within 15 minutes and it is "
                  "locked out for %s.\n\r",
                  left, left == 1 ? "" : "s", length );
        write_to_buffer( d, buf, 0 );
        return;
    }

    e->locked_until = current_time + dur;
    e->lockouts++;
    e->last_lockout = current_time;
    e->failures = 0;
    e->fail_name[0] = '\0';
    e->mixed = false;
    lock_save();

    snprintf( buf, sizeof(buf),
              "Wrong password.\n\r"
              "Too many wrong passwords: your address is locked out for %s.\n\r"
              "Each lockout within a week lasts longer than the last.\n\r", length );
    write_to_buffer( d, buf, 0 );

    snprintf( buf, sizeof(buf),
              "Login lockout: %s locked out for %s (%d wrong passwords; lockout %d this week%s).",
              e->text, length, LOCK_THRESHOLD, e->lockouts,
              trusted ? "; a player's address, so an hour at most" : "" );
    log_string( buf );
    wizinfo( buf, LEVEL_IMMORTAL );
}

/*
 * A login that has finished (login_note_success): the address's count goes
 * only when every failure counted was for this character -- a player who
 * mistyped their own password -- never when they were guesses at somebody
 * else's. The character hears of wrong passwords tried on them since.
 */
void login_lock_success( DESCRIPTOR_DATA *d, CHAR_DATA *ch )
{
    LOCK_ENTRY *e;
    char buf[MAX_STRING_LENGTH];
    int i;

    if ( d == NULL || ch == NULL || ch->name == NULL )
        return;
    if ( ( e = lock_find( d->ip ) ) != NULL && !e->mixed
    &&   ( e->fail_name[0] == '\0' || !str_cmp( e->fail_name, ch->name ) ) )
    {
        e->failures = 0;
        e->fail_name[0] = '\0';
    }
    for ( i = 0; i < LOCK_NAME_SLOTS; i++ )
    {
        LOCK_NAME *n = &lock_names[i];
        int where;

        if ( !n->used || str_cmp( n->name, ch->name ) )
            continue;
        if ( n->failures > 0 )
        {
            where = n->nkeys + n->more_keys;
            snprintf( buf, sizeof(buf),
                      "%d failed password attempt%s made on your character since you last "
                      "logged in, from %d address%s.%s\n\r",
                      n->failures, n->failures == 1 ? " was" : "s were",
                      where, where == 1 ? "" : "es",
                      n->failures >= LOCK_THRESHOLD
                          ? " If they were not yours, choose a new password (PASSWORD)." : "" );
            send_to_char( buf, ch );
        }
        memset( n, 0, sizeof(*n) );
        break;
    }
}

/* Staff DNS ALLOW: lift an address's lockout and forget its history. */
bool login_lock_lift( const NET_ADDR *a )
{
    LOCK_ENTRY *e = lock_find( net_addr_guard_key( a ) );

    if ( e == NULL )
        return false;
    memset( e, 0, sizeof(*e) );
    lock_save();
    return true;
}

/* Staff DNS GUARD: the lockouts standing, and the week's history. */
void login_lock_report( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    char left[64];
    int shown = 0, remembered = 0;
    int i;

    snprintf( buf, sizeof(buf),
              "Login lockouts: %d wrong passwords in 15 minutes lock an address out for\n\r"
              "15 minutes, then 1 hour, 6 hours, 1 day and 7 days for each lockout in a\n\r"
              "week (a player's address: 1 hour at most). Kept across reboots.\n\r",
              LOCK_THRESHOLD );
    send_to_char( buf, ch );
    for ( i = 0; i < LOCK_SLOTS; i++ )
    {
        const LOCK_ENTRY *e = &lock_table[i];

        if ( !e->used || e->lockouts <= 0 )
            continue;
        if ( e->locked_until <= current_time )
        {
            remembered++;
            continue;
        }
        lock_say_time( (long) ( e->locked_until - current_time ), left, sizeof(left) );
        snprintf( buf, sizeof(buf), "  %-24s locked out %s more (lockout %d this week)\n\r",
                  e->text, left, e->lockouts );
        send_to_char( buf, ch );
        shown++;
    }
    if ( shown == 0 )
        send_to_char( "  Nobody is locked out.\n\r", ch );
    if ( remembered > 0 )
    {
        snprintf( buf, sizeof(buf), "  %d more address%s locked out earlier this week.\n\r",
                  remembered, remembered == 1 ? "" : "es" );
        send_to_char( buf, ch );
    }
}
