/*
 * src/netaddr.c and src/guardstore.c, alone (review, 2026-11-06).
 *
 * Built and run by tests/test_guard_addresses.py with a scratch directory
 * as its only argument. Prints "ok" and exits 0, or a FAIL line for each
 * check that does not hold.
 */
/* fileno and ftruncate are POSIX: visible under -std=c17 only with these,
   before any header, as the game's own files do. */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "netaddr.h"
#include "guardstore.h"

static int failures;

#define CHECK(cond, what) \
    do { if ( !(cond) ) { printf( "FAIL %s (line %d)\n", what, __LINE__ ); failures++; } } while (0)

static const char *dir;

/*
 * Built with -DGUARD_STORE_FFLUSH=test_fflush: guardstore.c flushes through
 * this. When `flush_fail_once` is set, the next flush writes what it has,
 * cuts the file to half and reports failure, as a disk does that takes part
 * of a write; every later flush succeeds -- the sequence that let the old
 * rewrite forget its first failure and rename an incomplete file in.
 */
static int flush_fail_once;

int test_fflush( FILE *fp )
{
    if ( flush_fail_once && fp != NULL )
    {
        struct stat st;

        flush_fail_once = 0;
        fflush( fp );
        if ( fstat( fileno( fp ), &st ) == 0 && ftruncate( fileno( fp ), st.st_size / 2 ) != 0 )
            return EOF;
        return EOF;
    }
    return fflush( fp );
}

static void write_file( const char *path, const char *text )
{
    FILE *fp = fopen( path, "w" );

    if ( fp != NULL )
    {
        fputs( text, fp );
        fclose( fp );
    }
}

static long read_file( const char *path, char *buf, size_t size )
{
    FILE *fp = fopen( path, "r" );
    size_t n;

    if ( fp == NULL )
        return -1;
    n = fread( buf, 1, size - 1, fp );
    buf[n] = '\0';
    fclose( fp );
    return (long) n;
}

static void path_in( char *buf, size_t size, const char *name )
{
    snprintf( buf, size, "%s/%s", dir, name );
}

static void test_addresses( void )
{
    NET_ADDR a, b;
    char text[NET_ADDR_TEXT];

    CHECK( net_addr_parse( "203.0.113.7", &a ) && a.family == 4, "dotted IPv4 parses" );
    CHECK( !net_addr_parse( "203.0.113.7x", &a ), "a numeric prefix is no address" );
    CHECK( !net_addr_parse( "203.0.113", &a ), "three parts is no address" );
    CHECK( !net_addr_parse( " 203.0.113.7", &a ), "a leading space is no address" );
    CHECK( !net_addr_parse( "203.0.113.7 ", &a ), "a trailing space is no address" );
    CHECK( !net_addr_parse( "host.example.net", &a ), "a host name is no address" );
    CHECK( !net_addr_parse( "", &a ), "nothing is no address" );

    /* The bridge sends compressed IPv6; a staff member may type it whole. */
    CHECK( net_addr_parse( "2001:db8::1", &a ) && a.family == 6, "compressed IPv6 parses" );
    CHECK( net_addr_parse( "2001:0DB8:0000:0000:0000:0000:0000:0001", &b ), "expanded IPv6 parses" );
    CHECK( net_addr_equal( &a, &b ), "expanded and compressed IPv6 are one address" );
    net_addr_text( &b, text, sizeof(text) );
    CHECK( !strcmp( text, "2001:db8::1" ), "IPv6 text is canonical" );
    CHECK( net_addr_canonical( "2001:0DB8::0001", text, sizeof(text) ) && !strcmp( text, "2001:db8::1" ),
           "canonical rewrites an IPv6 literal" );
    CHECK( !net_addr_canonical( "bad.host.example", text, sizeof(text) )
           && !strcmp( text, "bad.host.example" ), "canonical leaves a host name alone" );

    /* An IPv4-mapped peer is that IPv4 address. */
    CHECK( net_addr_parse( "::ffff:198.51.100.4", &a ) && a.family == 4, "mapped IPv6 is IPv4" );
    CHECK( net_addr_parse( "198.51.100.4", &b ) && net_addr_equal( &a, &b ), "mapped equals dotted" );

    CHECK( net_addr_parse( "203.0.113.7", &a ) && net_addr_parse( "203.0.113.70", &b )
           && !net_addr_equal( &a, &b ), "1.2.3.7 is not 1.2.3.70" );
    CHECK( net_addr_parse( "203.0.113.7", &a ) && net_addr_parse( "::ffff:203.0.113.8", &b )
           && !net_addr_equal( &a, &b ), "different addresses differ" );
    memset( &a, 0, sizeof(a) );
    memset( &b, 0, sizeof(b) );
    CHECK( !net_addr_equal( &a, &b ), "two empty addresses are not one" );

    CHECK( net_addr_parse( "127.0.0.1", &a ) && net_addr_is_loopback( &a ), "127.0.0.1 is loopback" );
    CHECK( net_addr_parse( "::1", &a ) && net_addr_is_loopback( &a ), "::1 is loopback" );
    CHECK( net_addr_parse( "128.0.0.1", &a ) && !net_addr_is_loopback( &a ), "128.0.0.1 is not" );

    /* The guard key: an IPv4 address is itself; an IPv6 /64 is folded into
       240.0.0.0/4, one key for the whole /64. */
    CHECK( net_addr_parse( "203.0.113.7", &a ) && !net_addr_key_is_v6( net_addr_guard_key( &a ) ),
           "an IPv4 key is no IPv6 key" );
    CHECK( net_addr_parse( "2001:db8:1:2::5", &a ) && net_addr_parse( "2001:db8:1:2:ffff::9", &b )
           && net_addr_guard_key( &a ) == net_addr_guard_key( &b ), "one /64 is one key" );
    CHECK( net_addr_key_is_v6( net_addr_guard_key( &a ) ), "an IPv6 key is marked" );
    CHECK( net_addr_parse( "2001:db8:1:3::5", &b ) && net_addr_guard_key( &a ) != net_addr_guard_key( &b ),
           "another /64 is another key" );
}

/* Twice a day for a hundred days; the file must say the last day. */
static void test_frequent_logins( void )
{
    static GUARD_TRUST rows[16], rows2[16];
    GUARD_STORE s, s2;
    char path[512];
    NET_ADDR a;
    time_t start = 1700000000, now = start;
    int day;

    path_in( path, sizeof(path), "frequent.tsv" );
    remove( path );
    guard_store_init( &s, rows, 16 );
    net_addr_parse( "198.51.100.20", &a );
    for ( day = 0; day < 100; day++ )
    {
        int twice;

        for ( twice = 0; twice < 2; twice++ )
        {
            GUARD_TRUST *t;

            now = start + (time_t) day * 86400 + twice * 43200 + 600;
            t = guard_store_note( &s, &a, now );
            if ( guard_store_due( t ) )
                CHECK( guard_store_append( &s, path, t ), "append lands" );
        }
    }
    CHECK( guard_store_trusted( &s, net_addr_guard_key( &a ), now, 90 ), "trusted in memory" );

    guard_store_init( &s2, rows2, 16 );
    CHECK( guard_store_load( &s2, path, now ) > 0, "the file reads back" );
    CHECK( guard_store_trusted( &s2, net_addr_guard_key( &a ), now, 90 ),
           "after a restart the address is still trusted" );
    CHECK( guard_store_find( &s2, net_addr_guard_key( &a ) ) != NULL
           && now - guard_store_find( &s2, net_addr_guard_key( &a ) )->last <= 86400,
           "the file holds a login within the last day" );
    CHECK( s.file_lines <= 101, "about a line a day, not a line a login" );
}

/* A write that fails is tried again at the next chance. */
static void test_failed_write( void )
{
    static GUARD_TRUST rows[4], rows2[4];
    GUARD_STORE s, s2;
    char good[512];
    NET_ADDR a;
    GUARD_TRUST *t;

    path_in( good, sizeof(good), "retry.tsv" );
    remove( good );
    guard_store_init( &s, rows, 4 );
    net_addr_parse( "192.0.2.55", &a );
    t = guard_store_note( &s, &a, 1700000000 );
    CHECK( guard_store_due( t ), "a first login is due" );
    /* A full disk: the bytes are buffered, the close fails. */
    CHECK( !guard_store_append( &s, "/dev/full", t ), "a full disk is a failed write" );
    CHECK( t->persisted == 0, "a failed write records nothing" );
    CHECK( !guard_store_append( &s, "/nonexistent-dir/x.tsv", t ), "no directory is a failed write" );
    t = guard_store_note( &s, &a, 1700000000 + 3600 );
    CHECK( guard_store_due( t ), "an hour later it is still due" );
    CHECK( guard_store_append( &s, good, t ), "the retry lands" );
    CHECK( t->persisted == t->last && !guard_store_dirty( t ), "and is recorded" );
    t = guard_store_note( &s, &a, 1700000000 + 7200 );
    CHECK( !guard_store_due( t ) && guard_store_dirty( t ), "within a day it waits" );

    guard_store_init( &s2, rows2, 4 );
    CHECK( guard_store_load( &s2, good, 1700000000 + 7200 ) > 0
           && guard_store_trusted( &s2, net_addr_guard_key( &a ), 1700000000 + 7200, 90 ),
           "a restart reads the retried line" );
}

static void test_rewrite_and_ipv6( void )
{
    static GUARD_TRUST rows[4], rows2[4];
    GUARD_STORE s, s2;
    char path[512], tmp[512];
    NET_ADDR a, other;
    GUARD_TRUST *t;

    path_in( path, sizeof(path), "rewrite.tsv" );
    path_in( tmp, sizeof(tmp), "rewrite.tsv.tmp" );
    guard_store_init( &s, rows, 4 );
    net_addr_parse( "2001:db8:aa:bb::1", &a );
    guard_store_note( &s, &a, 1700000000 );
    CHECK( guard_store_rewrite( &s, path, tmp ), "rewrite lands" );
    CHECK( !guard_store_dirty( &s.rows[0] ), "rewrite persists every row" );
    CHECK( !guard_store_rewrite( &s, path, "/nonexistent-dir/t" ), "a failed rewrite says so" );

    guard_store_init( &s2, rows2, 4 );
    guard_store_load( &s2, path, 1700000000 );
    net_addr_parse( "2001:db8:aa:bb:ffff::2", &other );
    t = guard_store_find( &s2, net_addr_guard_key( &other ) );
    CHECK( t != NULL, "an IPv6 address is read back by its /64" );
    CHECK( t != NULL && !strcmp( t->text, "2001:db8:aa:bb::1" ), "and shown as the address itself" );
}

static void test_seeding( void )
{
    NET_ADDR a, want;
    time_t when;

    /* The login journal: written after the password; a numeric host only. */
    CHECK( guard_seed_login_row( "1700000000\tZed\t203.0.113.9\tconnect\n", &a, &when )
           && net_addr_parse( "203.0.113.9", &want ) && net_addr_equal( &a, &want )
           && when == 1700000000, "a numeric connect row trusts its address" );
    CHECK( guard_seed_login_row( "1700000000\tZed\t203.0.113.9\treconnect\n", &a, &when ), "reconnect counts" );
    CHECK( guard_seed_login_row( "1700000000\tZed\t2001:db8::7\tnew\n", &a, &when ) && a.family == 6,
           "a new character's IPv6 row counts" );
    CHECK( !guard_seed_login_row( "1700000000\tZed\thost.example.net\tconnect\n", &a, &when ),
           "a host-name row ties no address" );
    CHECK( !guard_seed_login_row( "1700000000\tZed\t203.0.113.9\tquit\t300\n", &a, &when ),
           "a logout row is no login" );
    CHECK( !guard_seed_login_row( "1700000000\tZed\t203.0.113.9x\tconnect\n", &a, &when ),
           "a numeric prefix is no address" );
    CHECK( !guard_seed_login_row( "garbage", &a, &when ), "a torn row is nothing" );

    /* toc.log: the login line itself must carry the address. Connections
       interleaved before it are never joined to it. */
    CHECK( !guard_seed_log_line( "Wed Nov  4 03:18:50 2026 :: Sock.sinaddr:  198.51.100.1\n", &a, &when ),
           "a connection line trusts nobody" );
    CHECK( !guard_seed_log_line( "Wed Nov  4 03:18:51 2026 :: Sock.sinaddr:  198.51.100.2\n", &a, &when ),
           "nor a second, interleaved one" );
    CHECK( !guard_seed_log_line( "Wed Nov  4 03:19:40 2026 :: Zed@host.example.net has connected.\n", &a, &when ),
           "a login by host name ties no address, however near a connection line" );
    CHECK( guard_seed_log_line( "Wed Nov  4 03:25:00 2026 :: Zed@198.51.100.1 has connected.\n", &a, &when )
           && net_addr_parse( "198.51.100.1", &want ) && net_addr_equal( &a, &want ) && when > 0,
           "a login naming its address, however late, trusts that address" );
    CHECK( guard_seed_log_line( "Wed Nov  4 03:25:00 2026 :: Zed@198.51.100.1 reconnected.\n", &a, &when ),
           "a reconnect counts" );
    CHECK( guard_seed_log_line( "Wed Nov  4 03:25:00 2026 :: Zed@198.51.100.1 new player.\n", &a, &when ),
           "a new player counts" );
    CHECK( !guard_seed_log_line( "Wed Nov  4 03:25:00 2026 :: Zed@198.51.100.1 has quit.\n", &a, &when ),
           "a quit is no login" );
    CHECK( !guard_seed_log_line( "Wed Nov  4 03:25:00 2026 :: Zed shares an address with Ann: "
                                 "2 players on from 198.51.100.1 has connected.\n", &a, &when ),
           "only a Name@host line" );
}

/* Only a file that is not there starts again; one that cannot be read is
   never written over. */
static void test_unreadable( void )
{
    static GUARD_TRUST rows[4];
    GUARD_STORE s;
    char path[512], tmp[512], before[256], after[256];
    NET_ADDR a;
    GUARD_TRUST *t;

    path_in( path, sizeof(path), "nothere.tsv" );
    remove( path );
    guard_store_init( &s, rows, 4 );
    CHECK( guard_store_load( &s, path, 1700000000 ) == GUARD_LOAD_ABSENT, "no file is absent" );
    CHECK( !s.read_only, "an absent file is no reason to stop writing" );

    /* A directory where the file should be: it opens and cannot be read,
       whoever runs this. */
    path_in( path, sizeof(path), "isdir.tsv" );
    mkdir( path, 0700 );
    guard_store_init( &s, rows, 4 );
    CHECK( guard_store_load( &s, path, 1700000000 ) == GUARD_LOAD_UNREADABLE, "a read error is no absence" );
    CHECK( s.read_only, "and the store will not write" );

    /* A real permission failure, where the system enforces one. */
    if ( geteuid() != 0 )
    {
        path_in( path, sizeof(path), "locked.tsv" );
        write_file( path, "198.51.100.5\t1700000000\n" );
        chmod( path, 0 );
        guard_store_init( &s, rows, 4 );
        CHECK( guard_store_load( &s, path, 1700000000 ) == GUARD_LOAD_UNREADABLE,
               "an unreadable file is no absence" );
        chmod( path, 0600 );
    }

    /* A read-only store leaves the file exactly as it was. */
    path_in( path, sizeof(path), "kept.tsv" );
    path_in( tmp, sizeof(tmp), "kept.tsv.tmp" );
    write_file( path, "198.51.100.6\t1700000000\n" );
    read_file( path, before, sizeof(before) );
    guard_store_init( &s, rows, 4 );
    s.read_only = 1;
    net_addr_parse( "198.51.100.7", &a );
    t = guard_store_note( &s, &a, 1700000100 );
    CHECK( !guard_store_append( &s, path, t ), "a read-only store does not append" );
    CHECK( !guard_store_rewrite( &s, path, tmp ), "nor rewrite" );
    read_file( path, after, sizeof(after) );
    CHECK( !strcmp( before, after ), "the file is untouched" );
}

/* A record counts only whole. */
static void test_records( void )
{
    static GUARD_TRUST rows[16];
    GUARD_STORE s;
    char path[512];
    NET_ADDR a;
    time_t now = 1700000000;
    GUARD_TRUST *t;

    path_in( path, sizeof(path), "records.tsv" );
    write_file( path,
        "# comment\n"
        "198.51.100.10\t1699990000\n"           /* good */
        "198.51.100.11\t99999999999\n"          /* centuries ahead */
        "198.51.100.12\t99999999999999999999999\n" /* overflows */
        "198.51.100.13\t1699990000x\n"          /* trailing letters */
        "198.51.100.14\t-5\n"                   /* negative */
        "198.51.100.15\t1699990000 2\n"         /* a second field */
        "198.51.100.16x\t1699990000\n"          /* not an address */
        "198.51.100.17\t\n"                     /* no time */
        "198.51.100.18\t1700050000\n"           /* within the skew: believed */
        "198.51.100.19\t1699990000" );          /* unfinished: no newline */
    guard_store_init( &s, rows, 16 );
    CHECK( guard_store_load( &s, path, now ) == 11, "every line is read" );
    CHECK( s.count == 2, "only the whole, believable records count" );
    net_addr_parse( "198.51.100.10", &a );
    CHECK( guard_store_find( &s, net_addr_guard_key( &a ) ) != NULL, "the good record is kept" );
    net_addr_parse( "198.51.100.18", &a );
    CHECK( guard_store_find( &s, net_addr_guard_key( &a ) ) != NULL, "a little clock skew is believed" );
    net_addr_parse( "198.51.100.11", &a );
    CHECK( guard_store_find( &s, net_addr_guard_key( &a ) ) == NULL, "no record from the future" );
    net_addr_parse( "198.51.100.19", &a );
    CHECK( guard_store_find( &s, net_addr_guard_key( &a ) ) == NULL, "no unfinished record" );
    CHECK( s.bad_lines == 8, "the eight others are counted for the rewrite" );
    for ( t = s.rows; t < s.rows + s.count; t++ )
        CHECK( t->last <= now + GUARD_CLOCK_SKEW, "nothing trusted past the skew" );
}

/* A torn last record and an append: two records, never one. */
static void test_torn_tail( void )
{
    static GUARD_TRUST rows[8], rows2[8];
    GUARD_STORE s, s2;
    char path[512];
    NET_ADDR a, b;
    GUARD_TRUST *t;
    time_t now = 1700000500;

    path_in( path, sizeof(path), "torn.tsv" );
    write_file( path, "198.51.100.20\t1700000000\n198.51.100.21\t1700000000" );
    guard_store_init( &s, rows, 8 );
    net_addr_parse( "198.51.100.22", &b );
    t = guard_store_note( &s, &b, now );
    CHECK( guard_store_append( &s, path, t ), "the append lands" );

    guard_store_init( &s2, rows2, 8 );
    guard_store_load( &s2, path, now );
    t = guard_store_find( &s2, net_addr_guard_key( &b ) );
    CHECK( t != NULL && t->last == now, "the appended record reads back whole" );
    net_addr_parse( "198.51.100.20", &a );
    CHECK( guard_store_find( &s2, net_addr_guard_key( &a ) ) != NULL, "the record before the tear is kept" );
    net_addr_parse( "198.51.100.21", &a );
    t = guard_store_find( &s2, net_addr_guard_key( &a ) );
    CHECK( t == NULL || t->last <= 1700000000, "the torn record gains no later time" );
    for ( t = s2.rows; t < s2.rows + s2.count; t++ )
        CHECK( t->last <= now + GUARD_CLOCK_SKEW, "no far-future trust" );
}

/* The first flush fails, the next succeeds: the rewrite must fail. */
static void test_flush_failure_is_sticky( void )
{
    static GUARD_TRUST rows[64];
    GUARD_STORE s;
    char path[512], tmp[512], before[4096], after[4096];
    NET_ADDR a;
    char text[NET_ADDR_TEXT];
    int i;

    path_in( path, sizeof(path), "sticky.tsv" );
    path_in( tmp, sizeof(tmp), "sticky.tsv.tmp" );
    write_file( path, "198.51.100.30\t1700000000\n" );
    read_file( path, before, sizeof(before) );
    guard_store_init( &s, rows, 64 );
    for ( i = 0; i < 40; i++ )
    {
        snprintf( text, sizeof(text), "203.0.113.%d", i + 1 );
        net_addr_parse( text, &a );
        guard_store_note( &s, &a, 1700000000 + i );
    }
    flush_fail_once = 1;
    CHECK( !guard_store_rewrite( &s, path, tmp ), "a rewrite whose first flush failed fails" );
    read_file( path, after, sizeof(after) );
    CHECK( !strcmp( before, after ), "the good file is not replaced" );
    CHECK( guard_store_dirty( &s.rows[0] ), "nothing is marked persisted" );
    CHECK( access( tmp, F_OK ) != 0, "the temporary file is removed" );

    flush_fail_once = 1;
    CHECK( !guard_store_append( &s, path, &s.rows[0] ), "an append whose flush failed fails" );
    CHECK( guard_store_dirty( &s.rows[0] ), "and records nothing" );
    CHECK( guard_store_append( &s, path, &s.rows[0] ), "the next append lands as its own record" );
}

int main( int argc, char **argv )
{
    if ( argc < 2 )
    {
        printf( "FAIL usage: test_guard_addresses <scratch dir>\n" );
        return 1;
    }
    dir = argv[1];
    test_addresses();
    test_frequent_logins();
    test_failed_write();
    test_rewrite_and_ipv6();
    test_seeding();
    test_unreadable();
    test_records();
    test_torn_tail();
    test_flush_failure_is_sticky();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}
