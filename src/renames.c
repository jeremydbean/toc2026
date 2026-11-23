/*
 * The rename record (review of 2b6b5826d, 2026-11-23).
 *
 * RENAME moves a character to a new name, and three things kept the old one:
 * notes addressed to it or sent by it, other players' IGNORE lists, and the
 * BUG/TYPO/IDEA replies waiting in area/bug_replies.dat. With the old name
 * free, a new character made under it read the renamed player's private
 * notes, an ignored player was heard again, and a reply went to whoever held
 * the name next -- or nowhere.
 *
 * Every rename that lands is written here, one whole line each:
 *
 *     <epoch>\t<Old>\t<New>\n
 *
 * appended and flushed to player/recovery/renames.tsv before the old file
 * goes. An old name is then never anybody else's: the name prompt follows it
 * to the character it became (the password asked is that character's, so a
 * returning player keeps their way in and nobody else gains one), and a
 * rename or a new character may not take it. Notes, IGNORE lists and
 * replies are moved along the same record -- at the rename, and again at
 * boot and at each load, so a crash between the rename and those writes
 * loses nothing.
 *
 * The latest line naming a name decides it: "Old became New" retires Old,
 * and a later "X became Old" (a rename back) gives Old back to that
 * character. A chain is followed to its end, at most RENAME_MAX_HOPS steps.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200112L
#endif

#include <sys/types.h>
#include <sys/stat.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "merc.h"

#define RENAME_FILE      RECOVERY_DIR "renames.tsv"
#define RENAME_MAX_HOPS  32
#define RENAME_NAME_MAX  16

typedef struct rename_entry
{
    long when;
    char old_name[RENAME_NAME_MAX];
    char new_name[RENAME_NAME_MAX];
} RENAME_ENTRY;

static RENAME_ENTRY *renames = NULL;
static int rename_count = 0, rename_cap = 0;
static bool renames_loaded = false;
static bool rename_load_warned = false;


/* 2 to 12 letters, as a player's name is. */
static bool rename_name_ok( const char *name )
{
    size_t n = 0;

    if ( name == NULL )
        return false;
    for ( ; name[n] != '\0'; n++ )
        if ( !isalpha( (unsigned char) name[n] ) )
            return false;
    return n >= 2 && n <= 12;
}

static void rename_capitalize( char *name )
{
    size_t i;

    for ( i = 0; name[i] != '\0'; i++ )
        name[i] = (char) ( i == 0 ? UPPER( (unsigned char) name[i] )
                                  : LOWER( (unsigned char) name[i] ) );
}

static bool rename_remember( long when, const char *old_name, const char *new_name )
{
    if ( rename_count >= rename_cap )
    {
        int cap = rename_cap > 0 ? rename_cap * 2 : 32;
        RENAME_ENTRY *grown = realloc( renames, (size_t) cap * sizeof(*grown) );

        if ( grown == NULL )
            return false;
        renames = grown;
        rename_cap = cap;
    }
    renames[rename_count].when = when;
    toc_strlcpy( renames[rename_count].old_name, old_name, RENAME_NAME_MAX );
    toc_strlcpy( renames[rename_count].new_name, new_name, RENAME_NAME_MAX );
    rename_capitalize( renames[rename_count].old_name );
    rename_capitalize( renames[rename_count].new_name );
    rename_count++;
    return true;
}

/* Read on first use: whole lines only; anything else is skipped and counted.
   Marked loaded only when the whole file was read, or there is none: a file
   that is there and cannot be opened or read is logged once and tried again
   at the next use. Until 2026-11-23 the flag was set before the open, so one
   EACCES, EIO or EMFILE at the first lookup freed every retired name for the
   rest of the boot. Fault point rename-load. */
static void rename_load( void )
{
    FILE *fp;
    char line[256];
    int bad = 0;

    if ( renames_loaded )
        return;
    rename_count = 0;     /* a retry starts from the file, not from a partial read */
    if ( recovery_fault( "rename-load" ) )
        fp = NULL, errno = EIO;
    else
        fp = fopen( RENAME_FILE, "r" );
    if ( fp == NULL )
    {
        if ( errno == ENOENT )
        {
            renames_loaded = true;   /* no ledger: nothing retired yet, and that is known */
            return;
        }
        if ( !rename_load_warned )
            bug( "Renames: " RENAME_FILE " could not be read; retired names are not known until it can be", 0 );
        rename_load_warned = true;
        return;
    }
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char old_name[64], new_name[64];
        long when;
        size_t len = strlen( line );

        if ( len == 0 || line[len - 1] != '\n' )
        {
            int c;

            /* A torn last line, or one longer than a record: drained. */
            if ( len == sizeof(line) - 1 )
                while ( ( c = fgetc( fp ) ) != EOF && c != '\n' )
                    ;
            bad++;
            continue;
        }
        if ( sscanf( line, "%ld\t%63[A-Za-z]\t%63[A-Za-z]", &when, old_name, new_name ) != 3
        ||   when <= 0 || !rename_name_ok( old_name ) || !rename_name_ok( new_name )
        ||   !str_cmp( old_name, new_name ) )
        {
            bad++;
            continue;
        }
        rename_remember( when, old_name, new_name );
    }
    if ( ferror( fp ) )
    {
        /* What was read stays known; the whole file is read again next time. */
        if ( !rename_load_warned )
            bug( "Renames: a read error in " RENAME_FILE "; it will be read again", 0 );
        rename_load_warned = true;
        fclose( fp );
        return;
    }
    fclose( fp );
    renames_loaded = true;
    rename_load_warned = false;
    if ( bad > 0 )
    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf), "Renames: %d line%s of " RENAME_FILE
                  " skipped as not whole records.", bad, bad == 1 ? "" : "s" );
        log_string( buf );
    }
}

/*
 * The name a character known as `name` goes by now. True, with `out` the
 * current name, when `name` was given up by a rename; false (and `out` the
 * name itself, capitalised) when it is nobody's old name.
 */
bool rename_current_name( const char *name, char *out, size_t size )
{
    char now[RENAME_NAME_MAX];
    int hops;

    if ( out != NULL && size > 0 )
        out[0] = '\0';
    if ( !rename_name_ok( name ) )
    {
        if ( out != NULL && size > 0 && name != NULL )
            toc_strlcpy( out, name, size );
        return false;
    }
    rename_load( );
    toc_strlcpy( now, name, sizeof(now) );
    rename_capitalize( now );
    for ( hops = 0; hops < RENAME_MAX_HOPS; hops++ )
    {
        int i;
        const char *next = NULL;

        /* The latest line naming it decides. */
        for ( i = rename_count - 1; i >= 0; i-- )
        {
            if ( !str_cmp( renames[i].new_name, now ) )
                break;                      /* somebody became it: theirs */
            if ( !str_cmp( renames[i].old_name, now ) )
            {
                next = renames[i].new_name;  /* it became something else */
                break;
            }
        }
        if ( next == NULL )
            break;
        toc_strlcpy( now, next, sizeof(now) );
    }
    if ( out != NULL && size > 0 )
        toc_strlcpy( out, now, size );
    return str_cmp( now, name ) != 0;
}

/* Given up by a rename: nobody else may take it. */
bool rename_retired( const char *name )
{
    char now[RENAME_NAME_MAX];

    return rename_current_name( name, now, sizeof(now) );
}

/*
 * A line written and flushed, cut back off: true when the ledger is as it was
 * before `before`. The caller undoes a rename only when rename_record() says
 * false, so a false must leave no record on the disk.
 */
static bool rename_take_back( off_t before )
{
    int fd = open( RENAME_FILE, O_WRONLY );
    bool ok = fd >= 0 && ftruncate( fd, before ) == 0 && fsync( fd ) == 0;

    if ( fd >= 0 )
        close( fd );
    return ok;
}

/*
 * The rename on the disk, before the old file goes. True when the ledger
 * records it; false only when it does not, and then the caller undoes the
 * rename. A failure before the line is flushed cuts the file back; a failure
 * after it -- the directory sync of a new ledger, the table failing to grow --
 * takes the line back off too, and if even that cannot be done the rename is
 * kept, because the disk keeps it (review, 2026-11-23: these returned false
 * with the line already flushed, the caller deleted the new file, and after a
 * restart the old name led to a file that was gone). Fault points
 * rename-record, rename-sync-dir, rename-remember.
 */
bool rename_record( const char *old_name, const char *new_name )
{
    char line[128];
    struct stat st;
    size_t len, done = 0;
    off_t before;
    bool created, ok = true;
    int fd;

    if ( !rename_name_ok( old_name ) || !rename_name_ok( new_name ) )
        return false;
    rename_load( );
    snprintf( line, sizeof(line), "%ld\t%s\t%s\n", (long) current_time, old_name, new_name );
    len = strlen( line );
    if ( !recovery_ensure_dir( "../player" ) || !recovery_ensure_dir( RECOVERY_DIR ) )
        return false;
    created = stat( RENAME_FILE, &st ) != 0;
    if ( ( fd = open( RENAME_FILE, O_WRONLY | O_CREAT | O_APPEND, 0644 ) ) < 0 )
        return false;
    if ( ( before = lseek( fd, 0, SEEK_END ) ) < 0 )
    {
        close( fd );
        return false;
    }
    if ( recovery_fault( "rename-record" ) )
    {
        /* Half a line, then the failure: what a full disk does. */
        if ( write( fd, line, len / 2 ) < 0 )
            ok = false;
        ok = false;
    }
    while ( ok && done < len )
    {
        ssize_t n = write( fd, line + done, len - done );

        if ( n <= 0 )
            ok = false;
        else
            done += (size_t) n;
    }
    if ( ok && fsync( fd ) != 0 )
        ok = false;
    if ( !ok )
    {
        if ( ftruncate( fd, before ) != 0 || fsync( fd ) != 0 )
            bug( "Renames: a failed write could not be cut back", 0 );
        close( fd );
        return false;
    }
    close( fd );
    if ( ( created && ( recovery_fault( "rename-sync-dir" ) || !durable_dir_sync( RENAME_FILE ) ) )
    ||   recovery_fault( "rename-remember" )
    ||   !rename_remember( (long) current_time, old_name, new_name ) )
    {
        if ( rename_take_back( before ) )
            return false;
        bug( "Renames: a flushed record could not be taken back; the rename stands", 0 );
        renames_loaded = false;      /* the table learns it from the disk */
    }
    return true;
}

/*
 * A list of names, each word that is a retired name replaced by the name it
 * became; every other word kept as it was. True, with `out` the new list,
 * when anything changed. A word too long for a name is kept untouched.
 */
bool rename_follow_words( const char *list, char *out, size_t size )
{
    bool changed = false;
    const char *p = list;

    if ( out == NULL || size == 0 )
        return false;
    out[0] = '\0';
    if ( list == NULL )
        return false;
    while ( *p != '\0' )
    {
        char word[MAX_INPUT_LENGTH];
        char now[RENAME_NAME_MAX];
        size_t n = 0;

        if ( isspace( (unsigned char) *p ) )
        {
            char space[2] = { *p, '\0' };

            toc_strlcat( out, space, size );
            p++;
            continue;
        }
        while ( p[n] != '\0' && !isspace( (unsigned char) p[n] ) )
            n++;
        if ( n < sizeof(word) )
        {
            memcpy( word, p, n );
            word[n] = '\0';
            if ( rename_current_name( word, now, sizeof(now) ) )
            {
                toc_strlcat( out, now, size );
                changed = true;
            }
            else
                toc_strlcat( out, word, size );
        }
        else
        {
            size_t at = strlen( out );

            if ( at + n < size )
            {
                memcpy( out + at, p, n );
                out[at + n] = '\0';
            }
        }
        p += n;
    }
    return changed;
}
