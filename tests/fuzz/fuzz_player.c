/*
 * Fuzz target (b): the player-file loader -- load_char_obj and everything
 * under it (fread_char, fread_obj, fread_pet, the #STASH section, the
 * Nest and container checks, revive_at_load, unwear_illegal_at_load) --
 * on arbitrary bytes, through offline_player_load, the door every
 * offline command uses.
 *
 * The world (the repository's area files, copied to /dev/shm) is booted
 * once. Each input is written to player/Zfuzz and loaded. Oracles, beyond
 * ASan and UBSan:
 *
 *   - exit() while reading is a crash: a player file refuses that
 *     character, never the game (fuzz_world.c, FUZZ_EXIT_ABORT);
 *   - a copy the loader accepted and extract_char was given leaves no
 *     player in the character list (a copy stuck there is "in the game"
 *     to player_in_game for the life of the process);
 *   - a file the loader accepted, saved by the game's own writer, loads
 *     again (TOC_FUZZ_ROUNDTRIP=0 turns this off): what the writer writes
 *     the reader must read.
 *
 * Synthetic files only: the seed corpus is made in a disposable world
 * (tests/fuzz/make_seeds.py); never a real character's file.
 */
#include "merc.h"
#include "fuzz_world.h"

#include <sys/stat.h>

static bool roundtrip = true;

int LLVMFuzzerInitialize( int *argc, char ***argv )
{
    const char *env = getenv( "TOC_FUZZ_ROUNDTRIP" );

    (void) argc;
    (void) argv;
    if ( env != NULL && env[0] == '0' )
        roundtrip = false;
    fuzz_world_boot( true );
    return 0;
}

static int players_in_world( void )
{
    LIST_ITERATOR iter;
    CHAR_DATA *wch;
    int n = 0;

    FOR_EACH_CHARACTER( iter, wch )
        if ( !IS_NPC(wch) )
            n++;
    return n;
}

static void put_away( CHAR_DATA *ch, const char *when )
{
    extract_char( ch, true );
    if ( players_in_world( ) != 0 )
    {
        fprintf( stderr, "fuzz: an offline copy is still in the character "
                 "list after extract_char (%s).\n", when );
        abort();
    }
}

int LLVMFuzzerTestOneInput( const uint8_t *data, size_t size )
{
    static DESCRIPTOR_DATA d;
    const char *why = NULL;
    CHAR_DATA *ch;
    char path[MAX_INPUT_LENGTH];

    snprintf( path, sizeof(path), "%s%s", PLAYER_DIR, "Zfuzz" );
    if ( !fuzz_write_file( path, data, size ) )
        abort();

    fuzz_exit_mode = FUZZ_EXIT_ABORT;
    ch = offline_player_load( &d, "Zfuzz", &why );
    if ( ch != NULL )
    {
        /* The roundtrip writes where the file's own Name says; only a
           file that names itself, so a fuzzed Name never picks the path. */
        if ( roundtrip && ch->name != NULL && !str_cmp( ch->name, "Zfuzz" )
          && save_char_obj( ch ) )
        {
            CHAR_DATA *again;

            put_away( ch, "first load" );
            again = offline_player_load( &d, "Zfuzz", &why );
            if ( again == NULL )
            {
                fprintf( stderr, "fuzz: the game's own save of a file it "
                         "accepted does not load again: %s", why != NULL ? why : "?\n" );
                abort();
            }
            put_away( again, "reload" );
        }
        else
            put_away( ch, "load" );
    }
    fuzz_exit_mode = FUZZ_EXIT_REAL;
    recycle_flush( );
    return 0;
}
