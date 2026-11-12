/*
 * The fuzz targets' shared harness: a disposable world booted once per
 * process, and exit() redirected while an input is read (fuzz_world.h).
 * Not part of the game; see tests/fuzz/README.md.
 */
#include "merc.h"
#include "fuzz_world.h"

#include <dirent.h>
#include <errno.h>
#include <ftw.h>
#include <sys/stat.h>

#ifndef TOC_FUZZ_REPO
#define TOC_FUZZ_REPO "."
#endif

enum fuzz_exit_mode fuzz_exit_mode = FUZZ_EXIT_REAL;
jmp_buf            *fuzz_exit_trap = NULL;

extern char   str_boot_time[];
extern time_t boot_time_stamp;
void boot_db( void );

/* -Wl,--wrap=exit: every exit() in the linked game reaches here. */
void __real_exit( int status ) __attribute__((noreturn));
void __wrap_exit( int status ) __attribute__((noreturn));
void __wrap_exit( int status )
{
    if ( fuzz_exit_mode == FUZZ_EXIT_CATCH && fuzz_exit_trap != NULL )
        longjmp( *fuzz_exit_trap, 1 );
    if ( fuzz_exit_mode == FUZZ_EXIT_ABORT )
    {
        fprintf( stderr, "fuzz: exit(%d) while reading an input -- the game "
                 "would have stopped.\n", status );
        abort();
    }
    __real_exit( status );
}

static char world_root[1024];

const char *fuzz_world_root( void )
{
    return world_root;
}

bool fuzz_write_file( const char *path, const uint8_t *data, size_t size )
{
    FILE *fp = fopen( path, "wb" );
    bool ok;

    if ( fp == NULL )
        return false;
    ok = size == 0 || fwrite( data, 1, size, fp ) == size;
    if ( fclose( fp ) != 0 )
        ok = false;
    return ok;
}

static void copy_file( const char *from, const char *to )
{
    FILE *in = fopen( from, "rb" );
    FILE *out;
    char buf[65536];
    size_t n;

    if ( in == NULL )
        return;
    if ( ( out = fopen( to, "wb" ) ) == NULL )
    {
        fclose( in );
        return;
    }
    while ( ( n = fread( buf, 1, sizeof(buf), in ) ) > 0 )
        if ( fwrite( buf, 1, n, out ) != n )
            break;
    fclose( in );
    fclose( out );
}

static bool ends_with( const char *s, const char *tail )
{
    size_t a = strlen( s ), b = strlen( tail );

    return a >= b && !strcmp( s + a - b, tail );
}

static void make_dir( const char *root, const char *name )
{
    char path[1100];

    snprintf( path, sizeof(path), "%s/%s", root, name );
    if ( mkdir( path, 0700 ) != 0 && errno != EEXIST )
    {
        perror( path );
        abort();
    }
}

static int remove_one( const char *path, const struct stat *st, int flag, struct FTW *ftw )
{
    (void) st;
    (void) flag;
    (void) ftw;
    remove( path );
    return 0;
}

/* The world goes with the process, unless TOC_FUZZ_KEEP asks to look at
   it. A crash leaves it: the input is what matters, and it is saved. */
static void world_remove( void )
{
    const char *keep = getenv( "TOC_FUZZ_KEEP" );

    if ( world_root[0] != '\0' && ( keep == NULL || keep[0] == '\0' ) )
        nftw( world_root, remove_one, 16, FTW_DEPTH | FTW_PHYS );
}

void fuzz_world_boot( bool full )
{
    static const char *dirs[] = { "area", "player", "gods", "heroes", "log",
                                  "corpse", "backups", "notes" };
    const char *base = getenv( "TOC_FUZZ_DIR" );
    const char *repo = getenv( "TOC_FUZZ_REPO" );
    char from[1100], to[1100];
    DIR *dir;
    struct dirent *de;
    size_t i;
    time_t now;

    if ( repo == NULL || repo[0] == '\0' )
        repo = TOC_FUZZ_REPO;
    if ( base == NULL || base[0] == '\0' )
    {
        struct stat st;

        base = stat( "/dev/shm", &st ) == 0 ? "/dev/shm" : "/tmp";
    }
    snprintf( world_root, sizeof(world_root), "%s/tocfuzz-%ld", base, (long) getpid() );
    if ( mkdir( world_root, 0700 ) != 0 && errno != EEXIST )
    {
        perror( world_root );
        abort();
    }
    atexit( world_remove );
    for ( i = 0; i < sizeof(dirs) / sizeof(dirs[0]); i++ )
        make_dir( world_root, dirs[i] );

    /* The area files are code; the runtime .txt files beside them are the
       live game's state and are not copied (tests/live_mud.py does the same). */
    snprintf( from, sizeof(from), "%s/area", repo );
    if ( ( dir = opendir( from ) ) == NULL )
    {
        perror( from );
        abort();
    }
    while ( ( de = readdir( dir ) ) != NULL )
    {
        if ( !ends_with( de->d_name, ".are" ) && !ends_with( de->d_name, ".dat" )
          && strcmp( de->d_name, "area.lst" ) )
            continue;
        if ( !full && strcmp( de->d_name, "changes.dat" ) )
            continue;
        snprintf( from, sizeof(from), "%s/area/%s", repo, de->d_name );
        snprintf( to, sizeof(to), "%s/area/%s", world_root, de->d_name );
        copy_file( from, to );
    }
    closedir( dir );
    if ( !full )
    {
        snprintf( to, sizeof(to), "%s/area/area.lst", world_root );
        fuzz_write_file( to, (const uint8_t *) "$\n", 2 );
    }

    /* The game log goes nowhere: a long run writes millions of lines. */
    snprintf( to, sizeof(to), "%s/log/toc.log", world_root );
    if ( symlink( "/dev/null", to ) != 0 && errno != EEXIST )
        perror( to );

    snprintf( to, sizeof(to), "%s/area", world_root );
    if ( chdir( to ) != 0 )
    {
        perror( to );
        abort();
    }

    time( &now );
    current_time = now;
    toc_strlcpy( str_boot_time, ctime( &current_time ), MAX_INPUT_LENGTH );
    boot_time_stamp = current_time;
    if ( ( fpReserve = fopen( NULL_FILE, "r" ) ) == NULL )
        abort();

    /* A world that does not load is the harness's fault, not an input's. */
    fuzz_exit_mode = FUZZ_EXIT_ABORT;
    boot_db( );
    fuzz_exit_mode = FUZZ_EXIT_REAL;
}
