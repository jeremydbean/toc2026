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
/* Two workers, so one resolver that takes its time does not hold up every
   lookup queued behind it; a queued job older than this is dropped unmade
   (its connection has long since been shown its address). */
#define DNS_WORKERS      2
#define DNS_JOB_MAX_AGE 30

typedef struct dns_job
{
    long serial;
    struct sockaddr_storage addr;
    socklen_t len;
    char host[DNS_HOST_MAX];
    int found;
    int check;          /* the guard's: confirm the name leads back */
    int confirmed;      /* it does */
    int transient;      /* the resolver failed, rather than said no */
    time_t queued;
} DNS_JOB;

static pthread_mutex_t dns_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  dns_wake = PTHREAD_COND_INITIALIZER;
static DNS_JOB dns_todo[DNS_QUEUE_MAX];
static int     dns_todo_count;
static DNS_JOB dns_done[DNS_QUEUE_MAX];
static int     dns_done_count;
static DNS_JOB dns_checked[DNS_QUEUE_MAX];   /* the guard's answers */
static int     dns_checked_count;
static int     dns_running;            /* lookups the workers hold */
static int     dns_started;            /* 1 started, -1 could not start */
static long    dns_delay_ms;           /* TOC_DNS_DELAY_MS, tests only */
static long    dns_check_fails;        /* TOC_DNS_CHECK_FAILS, tests only */
static DNS_ASYNC_STATS dns_stats;      /* under dns_lock */

static long dns_now_ms( void )
{
    struct timespec now;

    clock_gettime( CLOCK_MONOTONIC, &now );
    return (long) now.tv_sec * 1000L + now.tv_nsec / 1000000L;
}

/* A resolver error that is the resolver's, not an answer: a timeout, a
   server failure, no memory. Asked again soon, not in six hours (review,
   2026-11-24). */
static int dns_transient( int rc )
{
    if ( rc == EAI_AGAIN || rc == EAI_MEMORY )
        return 1;
#ifdef EAI_SYSTEM
    if ( rc == EAI_SYSTEM )
        return 1;
#endif
    return 0;
}

/* Whether `name` resolves back to the address it was found for: a PTR
   record is the far end's to write, so a name alone proves nothing until
   its own forward lookup leads back (forward-confirmed reverse DNS). A
   forward lookup that failed for the resolver's sake sets *transient. */
static int dns_leads_back( const DNS_JOB *job, int *transient )
{
    struct addrinfo hints, *found = NULL, *ai;
    int back = 0, rc;

    memset( &hints, 0, sizeof(hints) );
    hints.ai_family = job->addr.ss_family;
    hints.ai_socktype = SOCK_STREAM;
    if ( ( rc = getaddrinfo( job->host, NULL, &hints, &found ) ) != 0 )
    {
        *transient = dns_transient( rc );
        return 0;
    }
    for ( ai = found; ai != NULL && !back; ai = ai->ai_next )
    {
        if ( ai->ai_family == AF_INET && job->addr.ss_family == AF_INET )
            back = memcmp( &( (const struct sockaddr_in *) (const void *) ai->ai_addr )->sin_addr,
                           &( (const struct sockaddr_in *) (const void *) &job->addr )->sin_addr,
                           sizeof(struct in_addr) ) == 0;
        else if ( ai->ai_family == AF_INET6 && job->addr.ss_family == AF_INET6 )
            back = memcmp( &( (const struct sockaddr_in6 *) (const void *) ai->ai_addr )->sin6_addr,
                           &( (const struct sockaddr_in6 *) (const void *) &job->addr )->sin6_addr,
                           sizeof(struct in6_addr) ) == 0;
    }
    freeaddrinfo( found );
    return back;
}

static void *dns_worker( void *unused )
{
    (void) unused;
    for ( ;; )
    {
        DNS_JOB job;
        long began, took;
        int fake_failure = 0, rc;

        pthread_mutex_lock( &dns_lock );
        for ( ;; )
        {
            while ( dns_todo_count == 0 )
                pthread_cond_wait( &dns_wake, &dns_lock );
            job = dns_todo[0];
            memmove( &dns_todo[0], &dns_todo[1], sizeof(DNS_JOB) * (size_t) ( dns_todo_count - 1 ) );
            dns_todo_count--;
            if ( time( NULL ) - job.queued <= DNS_JOB_MAX_AGE )
                break;
            dns_stats.expired++;
        }
        if ( job.check && dns_check_fails > 0 )
        {
            dns_check_fails--;
            fake_failure = 1;
        }
        dns_running++;
        pthread_mutex_unlock( &dns_lock );

        if ( dns_delay_ms > 0 )
        {
            struct timespec pause;

            pause.tv_sec = dns_delay_ms / 1000;
            pause.tv_nsec = ( dns_delay_ms % 1000 ) * 1000000L;
            nanosleep( &pause, NULL );
        }
        /* NI_NAMEREQD: no name is no answer, and the address stays. */
        began = dns_now_ms();
        if ( fake_failure )
        {
            /* The tests' resolver outage: a lookup that failed for the
               resolver's sake, as a timeout or SERVFAIL does. */
            job.found = 0;
            job.transient = 1;
        }
        else
        {
            rc = getnameinfo( (struct sockaddr *) &job.addr, job.len,
                              job.host, sizeof(job.host), NULL, 0, NI_NAMEREQD );
            job.found = rc == 0;
            job.transient = !job.found && dns_transient( rc );
            if ( job.found && job.check )
                job.confirmed = dns_leads_back( &job, &job.transient );
        }
        if ( !job.found )
            job.host[0] = '\0';
        took = dns_now_ms() - began;

        pthread_mutex_lock( &dns_lock );
        dns_running--;
        if ( job.found )
            dns_stats.found++;
        else
            dns_stats.failed++;
        dns_stats.total_ms += took;
        if ( took > dns_stats.slowest_ms )
            dns_stats.slowest_ms = took;
        /* The guard's lookups are answered whatever came of them: a lookup
           that found nothing, or failed, says so -- or the guard would wait
           on it for six hours (review, 2026-11-24). */
        if ( job.check )
        {
            if ( dns_checked_count < DNS_QUEUE_MAX )
                dns_checked[dns_checked_count++] = job;
        }
        else if ( job.found && dns_done_count < DNS_QUEUE_MAX )
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
    int i, started = 0;

    if ( dns_started != 0 )
        return dns_started > 0;
    delay = getenv( "TOC_DNS_DELAY_MS" );
    if ( delay != NULL )
        dns_delay_ms = strtol( delay, NULL, 10 );
    if ( dns_delay_ms < 0 || dns_delay_ms > 60000 )
        dns_delay_ms = 0;
    delay = getenv( "TOC_DNS_CHECK_FAILS" );
    if ( delay != NULL )
        dns_check_fails = strtol( delay, NULL, 10 );
    if ( dns_check_fails < 0 || dns_check_fails > 1000 )
        dns_check_fails = 0;
    dns_started = -1;
    if ( pthread_attr_init( &attr ) != 0 )
        return 0;
    pthread_attr_setdetachstate( &attr, PTHREAD_CREATE_DETACHED );
    for ( i = 0; i < DNS_WORKERS; i++ )
        if ( pthread_create( &thread, &attr, dns_worker, NULL ) == 0 )
            started++;
    pthread_attr_destroy( &attr );
    pthread_mutex_lock( &dns_lock );
    dns_stats.workers = started;
    pthread_mutex_unlock( &dns_lock );
    if ( started > 0 )
        dns_started = 1;
    return dns_started > 0;
}

static int dns_queue( long serial, const struct sockaddr *addr, socklen_t len, int check )
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
        job->check = check;
        job->queued = time( NULL );
        queued = 1;
        dns_stats.submitted++;
        pthread_cond_signal( &dns_wake );
    }
    else
        dns_stats.queue_full++;
    pthread_mutex_unlock( &dns_lock );
    return queued;
}

int dns_async_submit( long serial, const struct sockaddr *addr, socklen_t len )
{
    return dns_queue( serial, addr, len, 0 );
}

int dns_async_check( const struct sockaddr *addr, socklen_t len )
{
    return dns_queue( 0, addr, len, 1 );
}

int dns_async_take_checked( struct sockaddr_storage *addr, char *host, size_t size, int *outcome )
{
    int taken = 0;

    if ( dns_started <= 0 || addr == NULL || host == NULL || size == 0 || outcome == NULL )
        return 0;
    pthread_mutex_lock( &dns_lock );
    if ( dns_checked_count > 0 )
    {
        *addr = dns_checked[0].addr;
        strncpy( host, dns_checked[0].host, size - 1 );
        host[size - 1] = '\0';
        *outcome = dns_checked[0].transient ? DNS_CHECK_RETRY
                 : !dns_checked[0].found     ? DNS_CHECK_NO_NAME
                 : dns_checked[0].confirmed  ? DNS_CHECK_CONFIRMED
                 : DNS_CHECK_UNCONFIRMED;
        memmove( &dns_checked[0], &dns_checked[1],
                 sizeof(DNS_JOB) * (size_t) ( dns_checked_count - 1 ) );
        dns_checked_count--;
        taken = 1;
    }
    pthread_mutex_unlock( &dns_lock );
    return taken;
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

void dns_async_cancel( long serial )
{
    int i;

    if ( dns_started <= 0 || serial == 0 )
        return;
    pthread_mutex_lock( &dns_lock );
    for ( i = 0; i < dns_todo_count; i++ )
        if ( dns_todo[i].serial == serial )
        {
            memmove( &dns_todo[i], &dns_todo[i + 1], sizeof(DNS_JOB) * (size_t) ( dns_todo_count - i - 1 ) );
            dns_todo_count--;
            dns_stats.cancelled++;
            break;
        }
    pthread_mutex_unlock( &dns_lock );
}

void dns_async_stats( DNS_ASYNC_STATS *out )
{
    if ( out == NULL )
        return;
    pthread_mutex_lock( &dns_lock );
    *out = dns_stats;
    pthread_mutex_unlock( &dns_lock );
}
