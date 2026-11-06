/*
 * src/netaddr.c and src/guardstore.c, alone (review, 2026-11-06).
 *
 * Built and run by tests/test_guard_addresses.py with a scratch directory
 * as its only argument. Prints "ok" and exits 0, or a FAIL line for each
 * check that does not hold.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "netaddr.h"
#include "guardstore.h"

static int failures;

#define CHECK(cond, what) \
    do { if ( !(cond) ) { printf( "FAIL %s (line %d)\n", what, __LINE__ ); failures++; } } while (0)

static const char *dir;

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
    CHECK( guard_store_load( &s2, path ) > 0, "the file reads back" );
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
    CHECK( guard_store_load( &s2, good ) > 0
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
    guard_store_load( &s2, path );
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
    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}
