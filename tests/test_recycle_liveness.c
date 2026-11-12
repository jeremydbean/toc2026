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
 * Usage: test_recycle_liveness zero|window|cap|standin
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

        /* A stand-in on the stack was never made here: it reads as freed,
           so nothing may store a pointer to one where the sweep looks, and
           releasing it is refused. */
        memset( &standin, 0, sizeof(standin) );
        memset( &candidate, 0, sizeof(candidate) );
        expect( char_liveness( &standin ) == MEM_STATE_FREED, "stand-in unknown" );
        expect( obj_liveness( &candidate ) == MEM_STATE_FREED, "candidate unknown" );
        char_data_release( &standin );
        obj_data_release( &candidate );
        expect( bugs == before + 2, "stand-ins refused" );
    }
    else
    {
        printf( "unknown mode %s\n", mode );
        return 2;
    }

    printf( "%s: %d checks, %d failures\n", mode, checks, failures );
    return failures == 0 ? 0 : 1;
}
