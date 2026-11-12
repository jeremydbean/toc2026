/*
 * Fuzz target (c): the area-file loader -- load_area_file and every
 * section loader under it (load_area, load_areadata, load_helps,
 * load_mobiles, load_objects, load_resets, load_rooms, load_shops,
 * load_socials, load_specials), then the boot's own checks over what was
 * loaded (fix_exits, fix_reset_room_limits) -- on arbitrary bytes, as one
 * extra area at boot.
 *
 * A malformed area file stops the boot, by design: the world loads whole
 * or not at all. So exit() is the expected way out of a bad input here,
 * and the harness catches it (fuzz_world.c, FUZZ_EXIT_CATCH) instead of
 * forking a process per input. What it must never do is crash, read or
 * write out of bounds, hit undefined behaviour, or hang -- each of those
 * is a finding.
 *
 * The world under the input is empty (an area.lst naming nothing; boot
 * makes only the builder's area), so an input can touch nothing but its
 * own records, and fuzz_world_rewind (db.c, TOC_FUZZ only) takes them all
 * back out before the next input.
 *
 * Leak detection is off for this target (fuzz/run.sh): the loaders take
 * strings at boot that are never meant to be freed.
 */
#include "merc.h"
#include "fuzz_world.h"

extern bool  fBootDb;
extern FILE *fpArea;
void load_area_file( const char *area_filename );
void fix_exits( void );
void fix_reset_room_limits( void );
void fuzz_world_mark( void );
void fuzz_world_rewind( void );

#define FUZZ_AREA_FILE "zfuzz.are"

/* TOC_FUZZ_VERBOSE=1 says how each input ended (for checking a seed). */
static bool verbose;

int LLVMFuzzerInitialize( int *argc, char ***argv )
{
    (void) argc;
    (void) argv;
    verbose = getenv( "TOC_FUZZ_VERBOSE" ) != NULL;
    fuzz_world_boot( false );
    fuzz_world_mark( );
    return 0;
}

int LLVMFuzzerTestOneInput( const uint8_t *data, size_t size )
{
    jmp_buf trap;

    if ( !fuzz_write_file( FUZZ_AREA_FILE, data, size ) )
        abort();

    fBootDb        = true;
    fuzz_exit_trap = &trap;
    fuzz_exit_mode = FUZZ_EXIT_CATCH;
    if ( setjmp( trap ) == 0 )
    {
        load_area_file( FUZZ_AREA_FILE );
        fix_exits( );
        fix_reset_room_limits( );
        if ( verbose )
            fprintf( stderr, "fuzz_area: loaded whole (%d rooms, %d mobiles, %d objects)\n",
                     top_room, top_mob_index, top_obj_index );
    }
    else if ( verbose )
        fprintf( stderr, "fuzz_area: the boot would stop here\n" );
    fuzz_exit_mode = FUZZ_EXIT_REAL;
    fuzz_exit_trap = NULL;
    if ( fpArea != NULL )
        fclose( fpArea );
    fpArea  = NULL;
    fBootDb = false;
    fuzz_world_rewind( );
    return 0;
}
