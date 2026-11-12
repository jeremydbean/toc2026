/*
 * tcp_keepalive_set on a real loopback connection (review, 2026-11-12):
 * keepalive is on, and the idle time before the first probe -- TCP_KEEPIDLE
 * on Linux, TCP_KEEPALIVE on macOS -- reads back as what was asked, as do
 * the gap and the count where the platform has them. Built and run by
 * tests/test_tcpkeep.py: cc -std=c17 -I src tests/test_tcpkeep.c src/tcpkeep.c
 */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L

#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "tcpkeep.h"

static int failures;

static void check( int ok, const char *what )
{
    if ( !ok )
    {
        printf( "FAIL: %s\n", what );
        failures++;
    }
}

static int read_opt( int fd, int level, int name )
{
    int value = -1;
    socklen_t len = sizeof(value);

    if ( getsockopt( fd, level, name, &value, &len ) < 0 )
        return -1;
    return value;
}

int main( void )
{
    struct sockaddr_in sa;
    socklen_t len = sizeof(sa);
    int lfd, cfd, sfd, failed, missing = -1;
    const char *idle = tcp_keepalive_idle_option();

    memset( &sa, 0, sizeof(sa) );
    sa.sin_family = AF_INET;
    sa.sin_addr.s_addr = htonl( INADDR_LOOPBACK );
    lfd = socket( AF_INET, SOCK_STREAM, 0 );
    if ( lfd < 0 || bind( lfd, (struct sockaddr *) &sa, sizeof(sa) ) < 0
    ||   listen( lfd, 1 ) < 0 || getsockname( lfd, (struct sockaddr *) &sa, &len ) < 0 )
    {
        printf( "FAIL: no loopback listener\n" );
        return 1;
    }
    cfd = socket( AF_INET, SOCK_STREAM, 0 );
    if ( cfd < 0 || connect( cfd, (struct sockaddr *) &sa, sizeof(sa) ) < 0 )
    {
        printf( "FAIL: no loopback connection\n" );
        return 1;
    }
    sfd = accept( lfd, NULL, NULL );
    check( sfd >= 0, "accept" );

    failed = tcp_keepalive_set( sfd, 120, 30, 4, &missing );
    check( failed == 0, "every option the platform has was set" );
    check( read_opt( sfd, SOL_SOCKET, SO_KEEPALIVE ) != 0, "SO_KEEPALIVE is on" );

#if defined(__linux__) || defined(__APPLE__)
    /* Both name an idle option: Linux TCP_KEEPIDLE, macOS TCP_KEEPALIVE. */
    check( idle != NULL, "an idle option on Linux and macOS" );
    check( ( missing & TCPKEEP_IDLE ) == 0, "the idle time is not missing" );
#endif
#if defined(TCP_KEEPIDLE)
    check( idle != NULL && strcmp( idle, "TCP_KEEPIDLE" ) == 0, "TCP_KEEPIDLE chosen" );
    check( read_opt( sfd, IPPROTO_TCP, TCP_KEEPIDLE ) == 120, "TCP_KEEPIDLE reads 120" );
#elif defined(TCP_KEEPALIVE)
    check( idle != NULL && strcmp( idle, "TCP_KEEPALIVE" ) == 0, "TCP_KEEPALIVE chosen" );
    check( read_opt( sfd, IPPROTO_TCP, TCP_KEEPALIVE ) == 120, "TCP_KEEPALIVE reads 120" );
#endif
#if defined(TCP_KEEPINTVL)
    check( read_opt( sfd, IPPROTO_TCP, TCP_KEEPINTVL ) == 30, "TCP_KEEPINTVL reads 30" );
#endif
#if defined(TCP_KEEPCNT)
    check( read_opt( sfd, IPPROTO_TCP, TCP_KEEPCNT ) == 4, "TCP_KEEPCNT reads 4" );
#endif

    /* A closed descriptor fails every option, and says so. */
    close( cfd );
    close( sfd );
    failed = tcp_keepalive_set( sfd, 120, 30, 4, NULL );
    check( ( failed & TCPKEEP_ON ) != 0, "a refused setsockopt is reported" );
    close( lfd );

    printf( "%s (%s)\n", failures ? "FAILED" : "OK", idle != NULL ? idle : "no idle option" );
    return failures ? 1 : 0;
}
