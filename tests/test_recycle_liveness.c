/*
 * The real src/recycle.c and src/memtrack.c, linked with stand-ins for the
 * few game functions recycle.c calls, under ASan, by
 * tests/test_memory_ranges.py: a liveness check must never read a block
 * that has been freed.
 *
 * Before 2026-11-12 char_is_live, obj_is_live and desc_is_live read the
 * block's mem_magic tag. That is safe while the block is in quarantine and
 * a use after free once recycle_flush has freed it -- after the window, or
 * at once when MEM_QUARANTINE_MAX more blocks are released behind it. The
 * "cap" mode is that case exactly: window 60 s, one character released,
 * MEM_QUARANTINE_MAX more behind it, a flush, then char_is_live on the
 * first. ASan stopped the old code there with heap-use-after-free.
 *
 * "reuse" (2026-11-12): a pointer kept with its MEM_REF (SET_CHAR_REF) to
 * a character released and freed, whose address is then registered again
 * as a new character -- what the allocator does when it hands the address
 * to the next one made -- reads MEM_STATE_REUSED, though the address alone
 * reads live. The old recycle.c had no MEM_REF: the address read live and
 * nothing more could be asked. Never reads the freed block.
 *
 * "standin": a stand-in on the stack reads freed until it is registered,
 * live while registered, is never released, and freed again after.
 *
 * Usage: test_recycle_liveness zero|window|cap|standin|reuse
 */
#include "merc.h"

time_t current_time;
static int bugs;

void bug( const char *str, int param )
{
    (void) str;
    (void) param;
    bugs++;
}

int staff_notice_level( const CHAR_DATA *ch, int level )
{
    (void) ch;
    return level;
}

bool is_perm_memory( const void *pMem )
{
    (void) pMem;
    return false;
}

void *alloc_mem( int sMem )
{
    return calloc( 1, (size_t) sMem );
}

void free_mem( void *pMem, int sMem )
{
    (void) sMem;
    free( pMem );
}

void free_string( char *pstr )
{
    (void) pstr;
}

size_t toc_strlcpy( char *dst, const char *src, size_t siz )
{
    size_t len = strlen( src );

    if ( siz > 0 )
    {
        size_t n = len < siz - 1 ? len : siz - 1;

        memcpy( dst, src, n );
        dst[n] = '\0';
    }
    return len;
}

static int failures;
static int checks;

static void expect( int ok, const char *what )
{
    checks++;
    if ( !ok )
    {
        failures++;
        printf( "FAIL %s\n", what );
    }
}

/* One of each kind, released and then flushed out of quarantine. */
static void release_all_and_check( bool flushed_out )
{
    CHAR_DATA *ch = char_data_new( );
    OBJ_DATA *obj = obj_data_new( );
    DESCRIPTOR_DATA *d = descriptor_data_new( );
    int before = bugs;

    expect( char_is_live( ch ) && obj_is_live( obj ) && desc_is_live( d ), "made live" );
    expect( char_liveness( NULL ) == MEM_STATE_LIVE, "NULL is live" );
    expect( !char_data_released( ch ) && !obj_data_released( obj ), "not released" );

    char_data_release( ch );
    obj_data_release( obj );
    descriptor_data_release( d );
    expect( char_liveness( ch ) == MEM_STATE_DEAD, "char dead in quarantine" );
    expect( obj_liveness( obj ) == MEM_STATE_DEAD, "obj dead in quarantine" );
    expect( desc_liveness( d ) == MEM_STATE_DEAD, "desc dead in quarantine" );
    /* A dead block is a different kind of nothing to the other checks. */
    expect( obj_liveness( (OBJ_DATA *) (void *) ch ) == MEM_STATE_FREED, "wrong kind" );

    recycle_flush( );
    if ( flushed_out )
    {
        /* Freed now: answered from the address alone. */
        expect( char_liveness( ch ) == MEM_STATE_FREED, "char freed" );
        expect( obj_liveness( obj ) == MEM_STATE_FREED, "obj freed" );
        expect( desc_liveness( d ) == MEM_STATE_FREED, "desc freed" );
        expect( !char_is_live( ch ) && !obj_is_live( obj ) && !desc_is_live( d ),
                "freed is not live" );
        expect( char_data_released( ch ) && obj_data_released( obj ), "freed is released" );
        /* A second release of a freed block is refused without reading it. */
        char_data_release( ch );
        obj_data_release( obj );
        descriptor_data_release( d );
        expect( bugs == before + 3, "second release refused" );
    }
    else
    {
        expect( char_liveness( ch ) == MEM_STATE_DEAD, "char still in quarantine" );
        char_data_release( ch );
        expect( bugs == before + 1, "second release refused in quarantine" );
    }
}

int main( int argc, char **argv )
{
    const char *mode = argc > 1 ? argv[1] : "zero";
    int held, window, cap;
    long oldest, freed, live, dead;

    current_time = 1000000;
    if ( !strcmp( mode, "zero" ) )
    {
        setenv( "TOC_MEM_QUARANTINE_SECS", "0", 1 );
        release_all_and_check( true );
    }
    else if ( !strcmp( mode, "window" ) )
    {
        CHAR_DATA *ch;

        setenv( "TOC_MEM_QUARANTINE_SECS", "60", 1 );
        release_all_and_check( false );
        ch = char_data_new( );
        char_data_release( ch );
        current_time += 59;
        recycle_flush( );
        expect( char_liveness( ch ) == MEM_STATE_DEAD, "inside the window" );
        current_time += 2;
        recycle_flush( );
        expect( char_liveness( ch ) == MEM_STATE_FREED, "after the window" );
        expect( !char_is_live( ch ), "after the window, not live" );
    }
    else if ( !strcmp( mode, "cap" ) )
    {
        CHAR_DATA *first;
        CHAR_DATA *last = NULL;
        int i;

        setenv( "TOC_MEM_QUARANTINE_SECS", "60", 1 );
        first = char_data_new( );
        char_data_release( first );
        for ( i = 0; i < MEM_QUARANTINE_MAX; i++ )
        {
            last = char_data_new( );
            char_data_release( last );
        }
        recycle_stats( &held, &oldest, &freed, &window, &cap );
        expect( held == MEM_QUARANTINE_MAX + 1, "held past the cap until the flush" );
        recycle_flush( );
        recycle_stats( &held, &oldest, &freed, &window, &cap );
        expect( held == MEM_QUARANTINE_MAX && freed == 1, "the oldest freed at the cap" );
        /* The window is not over, but the cap freed it: still never read. */
        expect( !char_is_live( first ), "capped out, not live" );
        expect( char_liveness( first ) == MEM_STATE_FREED, "capped out, freed" );
        expect( char_liveness( last ) == MEM_STATE_DEAD, "the newest still held" );
        recycle_tracked( &live, &dead );
        expect( live == 0 && dead == MEM_QUARANTINE_MAX, "tracked counts" );
    }
    else if ( !strcmp( mode, "standin" ) )
    {
        CHAR_DATA standin;
        OBJ_DATA candidate;
        int before = bugs;

        DESCRIPTOR_DATA offline;
        MEM_REF ref;
        long now, ever;

        /* Not in use: never made here, it reads as freed, and releasing it
           is refused. */
        memset( &standin, 0, sizeof(standin) );
        memset( &candidate, 0, sizeof(candidate) );
        memset( &offline, 0, sizeof(offline) );
        expect( char_liveness( &standin ) == MEM_STATE_FREED, "stand-in unknown" );
        expect( obj_liveness( &candidate ) == MEM_STATE_FREED, "candidate unknown" );
        char_data_release( &standin );
        obj_data_release( &candidate );
        expect( bugs == before + 2, "stand-ins refused" );

        /* In use: registered, it reads live -- with a serial a ref can
           keep -- and is still never released or freed. */
        mem_standin_begin( &standin, MEMTRACK_KIND_CHAR );
        mem_standin_begin( &candidate, MEMTRACK_KIND_OBJ );
        mem_standin_begin( &offline, MEMTRACK_KIND_DESC );
        expect( char_is_live( &standin ) && obj_is_live( &candidate ) && desc_is_live( &offline ),
                "stand-ins live while in use" );
        mem_ref_note( &ref, &standin, MEMTRACK_KIND_CHAR );
        expect( ref.serial != 0 && mem_ref_liveness( &standin, &ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_LIVE, "a ref to a stand-in" );
        recycle_standins( &now, &ever );
        expect( now == 3 && ever == 3, "three in use" );
        char_data_release( &standin );
        obj_data_release( &candidate );
        descriptor_data_release( &offline );
        expect( bugs == before + 5, "a stand-in in use is refused too" );
        expect( char_is_live( &standin ), "and stays live" );
        recycle_flush( );
        expect( char_is_live( &standin ), "never flushed" );
        mem_standin_end( &standin );
        mem_standin_end( &candidate );
        mem_standin_end( &offline );
        expect( char_liveness( &standin ) == MEM_STATE_FREED
                && obj_liveness( &candidate ) == MEM_STATE_FREED
                && desc_liveness( &offline ) == MEM_STATE_FREED, "ended: unknown again" );
        expect( mem_ref_liveness( &standin, &ref, MEMTRACK_KIND_CHAR ) == MEM_STATE_FREED,
                "a ref to an ended stand-in" );
        recycle_standins( &now, &ever );
        expect( now == 0 && ever == 3, "none in use" );
        /* Ending what is not a stand-in leaves a real block alone. */
        {
            CHAR_DATA *real = char_data_new( );

            mem_standin_end( real );
            expect( char_is_live( real ), "a real block is not ended" );
            char_data_release( real );
        }
    }
    else if ( !strcmp( mode, "reuse" ) )
    {
        HUNTER_DATA slot;
        CHAR_DATA holder;
        CHAR_DATA *old;
        CHAR_DATA *other;
        uintptr_t addr;
        int found = 0;
        int i;

        setenv( "TOC_MEM_QUARANTINE_SECS", "0", 1 );
        memset( &holder, 0, sizeof(holder) );
        memset( &slot, 0, sizeof(slot) );

        old = char_data_new( );
        SET_CHAR_REF( &holder, fighting, old );
        SET_CHAR_REF( &slot, ch, old );
        expect( holder.fighting_ref.ptr == old && holder.fighting_ref.serial != 0, "ref written" );
        expect( mem_ref_liveness( holder.fighting, &holder.fighting_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_LIVE, "live through its ref" );
        /* A fresh pointer to a fresh block: live, not reused. */
        other = char_data_new( );
        SET_CHAR_REF( &holder, reply, other );
        expect( mem_ref_liveness( holder.reply, &holder.reply_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_LIVE, "a fresh one is live" );

        char_data_release( old );
        expect( mem_ref_liveness( holder.fighting, &holder.fighting_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_DEAD, "dead in quarantine" );
        recycle_flush( );
        expect( mem_ref_liveness( holder.fighting, &holder.fighting_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_FREED, "freed" );

        /* The address handed to a new character, as malloc does. Only the
           number is used: the block is freed and never read. */
        addr = (uintptr_t) old;
        expect( memtrack_alive( (void *) addr, MEMTRACK_KIND_CHAR ), "registered again" );
        expect( char_is_live( holder.fighting ), "by address alone it reads live" );
        expect( mem_ref_liveness( holder.fighting, &holder.fighting_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_REUSED, "the ref says reused" );
        expect( mem_ref_liveness( slot.ch, &slot.ch_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_REUSED, "the hunter slot says reused" );
        /* Reused and then released again: still not this pointer's. */
        expect( memtrack_dead( (void *) addr ), "the newer one released" );
        expect( mem_ref_liveness( holder.fighting, &holder.fighting_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_REUSED, "reused while the newer one is dead" );
        memtrack_forget( (void *) addr );

        /* A field written by hand (no ref for this pointer) is answered by
           the address, as before. */
        holder.leader = other;
        expect( mem_ref_liveness( holder.leader, &holder.leader_ref, MEMTRACK_KIND_CHAR )
                    == MEM_STATE_LIVE, "unverified, by address" );
        SET_CHAR_REF( &holder, leader, NULL );
        expect( holder.leader_ref.ptr == NULL && holder.leader_ref.serial == 0, "NULL ref" );

        /* Where the allocator really does hand an address back, the same.
           glibc's calloc passes over its per-thread cache, so enough are
           freed together to spill past it; ASan's own quarantine holds
           every freed block, so under ASan none comes back. Only the
           numbers of the old addresses are compared. */
        {
            enum { OLD = 32, FRESH = 64 };
            CHAR_DATA *olds[OLD];
            MEM_REF refs[OLD];
            CHAR_DATA *fresh[FRESH];
            int j;

            for ( i = 0; i < OLD; i++ )
            {
                olds[i] = char_data_new( );
                mem_ref_note( &refs[i], olds[i], MEMTRACK_KIND_CHAR );
            }
            for ( i = 0; i < OLD; i++ )
                char_data_release( olds[i] );
            recycle_flush( );
            for ( i = 0; i < FRESH; i++ )
            {
                fresh[i] = char_data_new( );
                for ( j = 0; j < OLD; j++ )
                    if ( (uintptr_t) fresh[i] == (uintptr_t) olds[j] )
                    {
                        found++;
                        expect( char_is_live( olds[j] ), "real reuse reads live by address" );
                        expect( mem_ref_liveness( olds[j], &refs[j], MEMTRACK_KIND_CHAR )
                                    == MEM_STATE_REUSED, "real reuse caught by serial" );
                    }
            }
            for ( i = 0; i < FRESH; i++ )
                char_data_release( fresh[i] );
        }
        printf( "real allocator reuse %s (%d)\n", found ? "seen" : "not seen", found );
        char_data_release( other );
        recycle_flush( );
    }
    else
    {
        printf( "unknown mode %s\n", mode );
        return 2;
    }

    printf( "%s: %d checks, %d failures\n", mode, checks, failures );
    return failures == 0 ? 0 : 1;
}
