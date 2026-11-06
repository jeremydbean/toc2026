/*
 * Host names off the game loop: see dnsasync.h.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <netdb.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include "dnsasync.h"

/* A connection storm (a scanner sweeping the port) must not grow these
   without end: past the limit a connection keeps its address. */
#define DNS_QUEUE_MAX   64
#define DNS_HOST_MAX    256

typedef struct dns_job
{
    long serial;
    struct sockaddr_storage addr;
    socklen_t len;
    char host[DNS_HOST_MAX];
    int found;
} DNS_JOB;

static pthread_mutex_t dns_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  dns_wake = PTHREAD_COND_INITIALIZER;
static DNS_JOB dns_todo[DNS_QUEUE_MAX];
static int     dns_todo_count;
static DNS_JOB dns_done[DNS_QUEUE_MAX];
static int     dns_done_count;
static int     dns_running;            /* a lookup the worker holds */
static int     dns_started;            /* 1 started, -1 could not start */
static long    dns_delay_ms;           /* TOC_DNS_DELAY_MS, tests only */

static void *dns_worker( void *unused )
{
    (void) unused;
    for ( ;; )
    {
        DNS_JOB job;

        pthread_mutex_lock( &dns_lock );
        while ( dns_todo_count == 0 )
            pthread_cond_wait( &dns_wake, &dns_lock );
        job = dns_todo[0];
        memmove( &dns_todo[0], &dns_todo[1], sizeof(DNS_JOB) * (size_t) ( dns_todo_count - 1 ) );
        dns_todo_count--;
        dns_running = 1;
        pthread_mutex_unlock( &dns_lock );

        if ( dns_delay_ms > 0 )
        {
            struct timespec pause;

            pause.tv_sec = dns_delay_ms / 1000;
            pause.tv_nsec = ( dns_delay_ms % 1000 ) * 1000000L;
            nanosleep( &pause, NULL );
        }
        /* NI_NAMEREQD: no name is no answer, and the address stays. */
        job.found = getnameinfo( (struct sockaddr *) &job.addr, job.len,
                                 job.host, sizeof(job.host), NULL, 0, NI_NAMEREQD ) == 0;

        pthread_mutex_lock( &dns_lock );
        dns_running = 0;
        if ( job.found && dns_done_count < DNS_QUEUE_MAX )
            dns_done[dns_done_count++] = job;
        pthread_mutex_unlock( &dns_lock );
    }
    return NULL;
}

static int dns_start( void )
{
    pthread_attr_t attr;
    pthread_t thread;
    const char *delay;

    if ( dns_started != 0 )
        return dns_started > 0;
    delay = getenv( "TOC_DNS_DELAY_MS" );
    if ( delay != NULL )
        dns_delay_ms = strtol( delay, NULL, 10 );
    if ( dns_delay_ms < 0 || dns_delay_ms > 60000 )
        dns_delay_ms = 0;
    dns_started = -1;
    if ( pthread_attr_init( &attr ) != 0 )
        return 0;
    pthread_attr_setdetachstate( &attr, PTHREAD_CREATE_DETACHED );
    if ( pthread_create( &thread, &attr, dns_worker, NULL ) == 0 )
        dns_started = 1;
    pthread_attr_destroy( &attr );
    return dns_started > 0;
}

int dns_async_submit( long serial, const struct sockaddr *addr, socklen_t len )
{
    int queued = 0;

    if ( addr == NULL || len <= 0 || (size_t) len > sizeof(struct sockaddr_storage)
    ||   !dns_start() )
        return 0;
    pthread_mutex_lock( &dns_lock );
    if ( dns_todo_count < DNS_QUEUE_MAX )
    {
        DNS_JOB *job = &dns_todo[dns_todo_count++];

        memset( job, 0, sizeof(*job) );
        job->serial = serial;
        memcpy( &job->addr, addr, (size_t) len );
        job->len = len;
        queued = 1;
        pthread_cond_signal( &dns_wake );
    }
    pthread_mutex_unlock( &dns_lock );
    return queued;
}

int dns_async_take( long *serial, char *host, size_t size )
{
    int taken = 0;

    if ( dns_started <= 0 || serial == NULL || host == NULL || size == 0 )
        return 0;
    pthread_mutex_lock( &dns_lock );
    if ( dns_done_count > 0 )
    {
        *serial = dns_done[0].serial;
        strncpy( host, dns_done[0].host, size - 1 );
        host[size - 1] = '\0';
        memmove( &dns_done[0], &dns_done[1], sizeof(DNS_JOB) * (size_t) ( dns_done_count - 1 ) );
        dns_done_count--;
        taken = 1;
    }
    pthread_mutex_unlock( &dns_lock );
    return taken;
}

int dns_async_pending( void )
{
    int n;

    if ( dns_started <= 0 )
        return 0;
    pthread_mutex_lock( &dns_lock );
    n = dns_todo_count + dns_running;
    pthread_mutex_unlock( &dns_lock );
    return n;
}
