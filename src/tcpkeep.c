/*
 * TCP keepalive on a connection: see tcpkeep.h. Includes no merc.h.
 */
#include <errno.h>
#include <stddef.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

#include "tcpkeep.h"

#if defined(TCP_KEEPIDLE)
#define TOC_TCP_IDLE        TCP_KEEPIDLE
#define TOC_TCP_IDLE_NAME   "TCP_KEEPIDLE"
#elif defined(TCP_KEEPALIVE)
/* macOS: the same option under its BSD name. */
#define TOC_TCP_IDLE        TCP_KEEPALIVE
#define TOC_TCP_IDLE_NAME   "TCP_KEEPALIVE"
#endif

const char *tcp_keepalive_idle_option( void )
{
#if defined(TOC_TCP_IDLE)
    return TOC_TCP_IDLE_NAME;
#else
    return NULL;
#endif
}

/* One option, its bit set in *failed when setsockopt refuses it. */
static void keep_opt( int fd, int level, int name, int value, int bit, int *failed )
{
    if ( setsockopt( fd, level, name, (const void *) &value, sizeof(value) ) < 0 )
        *failed |= bit;
}

int tcp_keepalive_set( int fd, int idle_secs, int probe_gap, int probe_max,
                       int *missing )
{
    int failed = 0;
    int absent = 0;

    keep_opt( fd, SOL_SOCKET, SO_KEEPALIVE, 1, TCPKEEP_ON, &failed );
#if defined(TOC_TCP_IDLE)
    keep_opt( fd, IPPROTO_TCP, TOC_TCP_IDLE, idle_secs, TCPKEEP_IDLE, &failed );
#else
    (void) idle_secs;
    absent |= TCPKEEP_IDLE;
#endif
#if defined(TCP_KEEPINTVL)
    keep_opt( fd, IPPROTO_TCP, TCP_KEEPINTVL, probe_gap, TCPKEEP_GAP, &failed );
#else
    (void) probe_gap;
    absent |= TCPKEEP_GAP;
#endif
#if defined(TCP_KEEPCNT)
    keep_opt( fd, IPPROTO_TCP, TCP_KEEPCNT, probe_max, TCPKEEP_COUNT, &failed );
#else
    (void) probe_max;
    absent |= TCPKEEP_COUNT;
#endif
    if ( missing != NULL )
        *missing = absent;
    return failed;
}
