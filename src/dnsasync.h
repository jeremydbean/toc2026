/*
 * Host names off the game loop (2026-11-06).
 *
 * A reverse lookup can take a resolver half a second or more, and the game
 * is one thread: new_descriptor's getnameinfo froze every player for that
 * long whenever anybody connected -- the play journal's stall rows lined up
 * with every outside connection, internet scanners included. A worker
 * thread does the lookups now. The game hands it an address and a serial
 * and carries on with the address as the host; each pulse it takes the
 * answers back and gives each to the descriptor still holding that serial.
 *
 * Nothing here touches game state: the worker sees only its own queues,
 * under one mutex, so this file includes no merc.h.
 */
#ifndef TOC_DNSASYNC_H
#define TOC_DNSASYNC_H

#include <stddef.h>
#include <sys/socket.h>

/* Queue a reverse lookup; false (nothing queued) when the queue is full or
   no worker could be started -- the caller keeps the address. */
int  dns_async_submit( long serial, const struct sockaddr *addr, socklen_t len );

/* One finished lookup, if any: its serial and the name found. Lookups that
   found no name are not returned. 1 when one was taken, 0 when none. */
int  dns_async_take( long *serial, char *host, size_t size );

/* Lookups queued or running, for staff DNS. */
int  dns_async_pending( void );

/* A connection closed: its lookup, if still queued, is dropped. One a
   worker is already making finishes and is thrown away on collection. */
void dns_async_cancel( long serial );

/* What the resolver has done since boot, for staff DNS. */
typedef struct dns_async_stats
{
    int  workers;          /* started; 0 when none could be */
    long submitted;
    long queue_full;       /* refused: the queue was full */
    long cancelled;        /* dropped from the queue: its connection closed */
    long expired;          /* dropped from the queue: waited past DNS_JOB_MAX_AGE */
    long found;
    long failed;           /* the resolver found no name */
    long slowest_ms;       /* the longest single lookup */
    long total_ms;         /* all lookups, for the average */
} DNS_ASYNC_STATS;

void dns_async_stats( DNS_ASYNC_STATS *out );

#endif
