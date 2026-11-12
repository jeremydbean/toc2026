/*
 * TCP keepalive on a connection (review, 2026-11-12).
 *
 * The idle time before the first probe is TCP_KEEPIDLE on Linux and the
 * BSDs, TCP_KEEPALIVE on macOS (which has no TCP_KEEPIDLE): new_descriptor
 * asked for the first alone, so on macOS idle_secs was never set and both
 * builds warned it was unused. No merc.h, so tests/test_tcpkeep.c can set
 * the options on a real socket and read them back.
 */
#ifndef TOC_TCPKEEP_H
#define TOC_TCPKEEP_H

/* Bits of what tcp_keepalive_set reports. */
#define TCPKEEP_ON      0x1     /* SO_KEEPALIVE */
#define TCPKEEP_IDLE    0x2     /* TCP_KEEPIDLE or, on macOS, TCP_KEEPALIVE */
#define TCPKEEP_GAP     0x4     /* TCP_KEEPINTVL */
#define TCPKEEP_COUNT   0x8     /* TCP_KEEPCNT */

/* Turn keepalive on for fd and set the idle seconds before the first
   probe, the seconds between probes and how many go unanswered before the
   peer is given up on. Returns the TCPKEEP_* bits whose setsockopt failed
   (errno is the last failure's); *missing, when not NULL, gets the bits
   this platform has no option for. */
int tcp_keepalive_set( int fd, int idle_secs, int probe_gap, int probe_max,
                       int *missing );

/* The name of the idle option this build sets ("TCP_KEEPIDLE",
   "TCP_KEEPALIVE"), or NULL when it has neither. */
const char *tcp_keepalive_idle_option( void );

#endif
