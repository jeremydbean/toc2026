/*
 * The address set behind char_is_live, obj_is_live and desc_is_live
 * (src/memtrack.c), against a brute-force reference, under ASan, by
 * tests/test_memory_ranges.py.
 *
 * Only addresses are stored and compared; no tracked block is ever read,
 * which is the point: memguard.c asks of pointers whose target may already
 * be freed.
 *
 * "ok serials" (2026-11-12): every registration has a serial of its own,
 * so an address released, forgotten and registered again as the same kind
 * -- live again by address, which is all the old set could say -- carries
 * a new serial a stored one no longer matches. "ok standins": a stand-in
 * reads live, is refused by memtrack_dead, and is unknown once forgotten.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "memtrack.h"

#define N       60000
#define ROUNDS  400000

static int failures;
static int checks;

static void expect( int ok, const char *what, long n )
{
    checks++;
    if ( !ok && failures++ < 20 )
        printf( "FAIL %s (%ld)\n", what, n );
}

/* The reference: one state and kind per slot of a fake address range. */
static unsigned char ref_state[N];
static unsigned char ref_kind[N];
static uint64_t ref_serial[N];      /* as memtrack gave it at registration */
static char *arena;

static unsigned long rng = 88172645463325252UL;
static unsigned long next_rand( void )
{
    rng ^= rng << 13;
    rng ^= rng >> 7;
    rng ^= rng << 17;
    return rng;
}

static void *addr_of( long i )
{
    /* 16 apart, like allocations: the hash ignores the low bits. */
    return arena + 16 * i;
}

int main( void )
{
    long i;
    size_t live, dead, capacity;

    /* An address range nothing reads: memtrack keeps only the numbers. */
    if ( ( arena = malloc( (size_t) N * 16 ) ) == NULL )
        return 2;

    /* The basics. */
    {
        int x;

        expect( memtrack_state( NULL, 1 ) == MEMTRACK_UNKNOWN, "NULL unknown", 0 );
        expect( memtrack_state( &x, 1 ) == MEMTRACK_UNKNOWN, "stack unknown", 0 );
        expect( !memtrack_alive( NULL, 1 ), "NULL not registered", 0 );
        expect( !memtrack_dead( &x ), "dead of unknown", 0 );
        memtrack_forget( &x );
        expect( memtrack_alive( &x, 1 ), "register", 0 );
        expect( memtrack_state( &x, 1 ) == MEMTRACK_LIVE, "live", 0 );
        expect( memtrack_state( &x, 2 ) == MEMTRACK_OTHER, "other kind", 0 );
        expect( memtrack_dead( &x ), "release", 0 );
        expect( memtrack_state( &x, 1 ) == MEMTRACK_DEAD, "dead", 0 );
        expect( memtrack_state( &x, 2 ) == MEMTRACK_OTHER, "dead, other kind", 0 );
        /* The allocator hands the address back out: live again, either kind. */
        expect( memtrack_alive( &x, 2 ), "reused", 0 );
        expect( memtrack_state( &x, 2 ) == MEMTRACK_LIVE, "reused live", 0 );
        expect( memtrack_state( &x, 1 ) == MEMTRACK_OTHER, "reused by another kind", 0 );
        memtrack_forget( &x );
        expect( memtrack_state( &x, 2 ) == MEMTRACK_UNKNOWN, "forgotten", 0 );
        memtrack_counts( &live, &dead, &capacity );
        expect( live == 0 && dead == 0, "empty again", 0 );
        printf( "ok basics\n" );
    }

    /* Serials: what tells a reused address from the one a pointer named. */
    {
        int x, y;
        uint64_t s1, s2, s3, got;

        expect( memtrack_serial( &x, 1 ) == 0, "no serial unregistered", 0 );
        expect( memtrack_alive( &x, 1 ), "register", 0 );
        s1 = memtrack_serial( &x, 1 );
        expect( s1 != 0, "a serial", 0 );
        expect( memtrack_serial( &x, 2 ) == 0, "no serial as another kind", 0 );
        expect( memtrack_lookup( &x, 1, &got ) == MEMTRACK_LIVE && got == s1, "lookup live", 0 );
        expect( memtrack_dead( &x ), "release", 0 );
        expect( memtrack_lookup( &x, 1, &got ) == MEMTRACK_DEAD && got == s1,
                "a dead block keeps its serial", 0 );
        expect( memtrack_serial( &x, 1 ) == 0, "no live serial when dead", 0 );
        memtrack_forget( &x );
        expect( memtrack_lookup( &x, 1, &got ) == MEMTRACK_UNKNOWN && got == 0, "forgotten", 0 );
        /* The allocator hands the address to a new block of the same kind:
           the address alone says live, as before; the serial says new. */
        expect( memtrack_alive( &x, 1 ), "reused", 0 );
        s2 = memtrack_serial( &x, 1 );
        expect( memtrack_state( &x, 1 ) == MEMTRACK_LIVE, "reused reads live", 0 );
        expect( s2 != 0 && s2 != s1, "reused has a new serial", 0 );
        /* Never repeated, whatever the address. */
        expect( memtrack_alive( &y, 1 ), "another", 0 );
        s3 = memtrack_serial( &y, 1 );
        expect( s3 != s1 && s3 != s2, "serials unique", 0 );
        memtrack_forget( &x );
        memtrack_forget( &y );
        printf( "ok serials\n" );
    }

    /* Stand-ins: live while in use, never released, gone after. */
    {
        int s;
        size_t now;
        uint64_t ever;

        expect( memtrack_standin( &s, 3 ), "stand-in registered", 0 );
        expect( memtrack_state( &s, 3 ) == MEMTRACK_LIVE, "stand-in live", 0 );
        expect( memtrack_serial( &s, 3 ) != 0, "stand-in has a serial", 0 );
        expect( memtrack_is_standin( &s ), "is a stand-in", 0 );
        expect( !memtrack_dead( &s ), "a stand-in is never released", 0 );
        expect( memtrack_state( &s, 3 ) == MEMTRACK_LIVE, "still live after a refused release", 0 );
        memtrack_standin_counts( &now, &ever );
        expect( now == 1 && ever == 1, "counted", (long) now );
        memtrack_forget( &s );
        expect( memtrack_state( &s, 3 ) == MEMTRACK_UNKNOWN, "stand-in ended", 0 );
        expect( !memtrack_is_standin( &s ), "no longer a stand-in", 0 );
        memtrack_standin_counts( &now, &ever );
        expect( now == 0 && ever == 1, "counted after", (long) now );
        /* An address registered for real is not a stand-in. */
        expect( memtrack_alive( &s, 3 ) && !memtrack_is_standin( &s ), "real is not", 0 );
        memtrack_forget( &s );
        memtrack_counts( &live, &dead, &capacity );
        expect( live == 0 && dead == 0, "empty after stand-ins", 0 );
        printf( "ok standins\n" );
    }

    /* Random churn against the reference: register, release, forget,
       re-register as another kind -- every lookup must agree, which is what
       proves the backward-shift deletion never strands an entry. */
    for ( i = 0; i < ROUNDS; i++ )
    {
        long slot = (long) ( next_rand( ) % N );
        void *p = addr_of( slot );
        int op = (int) ( next_rand( ) % 4 );
        int kind = 1 + (int) ( next_rand( ) % 3 );

        switch ( op )
        {
        case 0:
        {
            uint64_t before = ref_serial[slot];

            expect( memtrack_alive( p, kind ), "alive", i );
            ref_state[slot]  = MEMTRACK_LIVE;
            ref_kind[slot]   = (unsigned char) kind;
            ref_serial[slot] = memtrack_serial( p, kind );
            expect( ref_serial[slot] != 0 && ref_serial[slot] != before, "new serial", i );
            break;
        }
        case 1:
            expect( memtrack_dead( p ) == ( ref_state[slot] != 0 ), "dead result", i );
            if ( ref_state[slot] != 0 )
                ref_state[slot] = MEMTRACK_DEAD;
            break;
        case 2:
            memtrack_forget( p );
            ref_state[slot] = 0;
            break;
        default:
        {
            int want = ref_state[slot] == 0 ? MEMTRACK_UNKNOWN
                     : ref_kind[slot] != kind ? MEMTRACK_OTHER
                     : ref_state[slot];

            uint64_t got;

            expect( memtrack_lookup( p, kind, &got ) == want, "lookup", i );
            /* The serial survives every backward shift of its slot. */
            if ( want == MEMTRACK_LIVE || want == MEMTRACK_DEAD )
                expect( got == ref_serial[slot], "serial kept", i );
            break;
        }
        }
    }
    {
        size_t want_live = 0, want_dead = 0;

        for ( i = 0; i < N; i++ )
        {
            int want = ref_state[i];

            expect( memtrack_state( addr_of( i ), ref_kind[i] )
                        == ( want == 0 ? MEMTRACK_UNKNOWN : want ), "final", i );
            want_live += want == MEMTRACK_LIVE;
            want_dead += want == MEMTRACK_DEAD;
        }
        memtrack_counts( &live, &dead, &capacity );
        expect( live == want_live, "live count", (long) live );
        expect( dead == want_dead, "dead count", (long) dead );
        expect( capacity >= 2 * ( live + dead ), "half full at most", (long) capacity );
    }
    printf( "ok churn\n" );

    /* Everything forgotten leaves nothing behind. */
    for ( i = 0; i < N; i++ )
        memtrack_forget( addr_of( i ) );
    memtrack_counts( &live, &dead, &capacity );
    expect( live == 0 && dead == 0, "all forgotten", 0 );
    for ( i = 0; i < N; i++ )
        expect( memtrack_state( addr_of( i ), 1 ) == MEMTRACK_UNKNOWN, "unknown after", i );
    printf( "ok forget\n" );

    free( arena );
    printf( "%d checks, %d failures\n", checks, failures );
    return failures == 0 ? 0 : 1;
}
