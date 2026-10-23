/***************************************************************************
 * restores.c -- player restores asked for through git.
 *
 * Owner, 2026-10-23: staff and the cloud sessions that maintain the game
 * must both be able to put a player back, easily. Staff have PRESTORE in
 * the game. A cloud session cannot reach the host at all; what it can do
 * is push, and a push is a deploy. So a restore can be asked for in
 * area/restores.dat, which ships with the code:
 *
 *   <id> <player> <kind> <stamp> [<file>]
 *
 *   gear    the snapshot's worn and carried objects, into their inventory
 *   stash   the snapshot's stash, added to what their stash holds
 *   import  nothing applied: only <file> installed, for staff to PRESTORE
 *
 * <stamp> names a snapshot in player/versions/<Player>/ by what follows
 * "<Player>." -- "20261023_023244.death", or a unique prefix of it. <file>
 * is a player file taken from git history, under area/restores/; at boot
 * it is installed as the snapshot <Player>.<stamp>.import (the stamp then
 * a plain YYYYMMDD_HHMMSS), so PRESTORE lists it like any other and a
 * gear or stash request can name "<stamp>.import".
 *
 * A gear or stash request is applied at the player's next login, once:
 * its id joins the login fixes' record in their file ("restore:<id>"). It
 * waits while their corpse still holds things, as PRESTORE GEAR refuses
 * to make two of everything. Ids are never reused.
 ***************************************************************************/

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "merc.h"

#define RESTORES_FILE  "restores.dat"
#define RESTORES_DIR   "restores/"
#define RESTORES_MAX   200

typedef struct restore_entry
{
    char id[32];
    char player[16];
    char kind[8];
    char stamp[48];
    char file[64];
} RESTORE_ENTRY;

static RESTORE_ENTRY restores[RESTORES_MAX];
static int restores_count = 0;


static bool restore_word_ok( const char *s, bool dots )
{
    for ( ; *s != '\0'; s++ )
        if ( !isalnum( (unsigned char) *s ) && *s != '_' && *s != '-'
        &&   !( dots && *s == '.' ) )
            return false;
    return true;
}

/* Copy a whole file, to a partial name renamed into place. */
static bool restore_copy( const char *from, const char *to )
{
    char partial[MAX_STRING_LENGTH + 16];
    FILE *in, *out;
    int c;
    bool ok = true;

    if ( ( in = fopen( from, "rb" ) ) == NULL )
        return false;
    snprintf( partial, sizeof(partial), "%s.partial", to );
    if ( ( out = fopen( partial, "wb" ) ) == NULL )
    {
        fclose( in );
        return false;
    }
    while ( ( c = fgetc( in ) ) != EOF )
        if ( fputc( c, out ) == EOF )
        {
            ok = false;
            break;
        }
    fclose( in );
    if ( fclose( out ) != 0 )
        ok = false;
    if ( !ok || rename( partial, to ) != 0 )
    {
        remove( partial );
        return false;
    }
    return true;
}

/* Whether a file ends in a player file's #END, so a cut copy never joins. */
static bool restore_file_whole( const char *path )
{
    FILE *fp = fopen( path, "r" );
    char line[MAX_INPUT_LENGTH];
    bool whole = false;

    if ( fp == NULL )
        return false;
    while ( fgets( line, sizeof(line), fp ) != NULL )
        if ( !strncmp( line, "#END", 4 ) )
            whole = true;
    fclose( fp );
    return whole;
}

/* At boot: read the requests, and install the files they bring. */
void restores_boot( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH];
    int i;

    restores_count = 0;
    if ( ( fp = fopen( RESTORES_FILE, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL && restores_count < RESTORES_MAX )
    {
        RESTORE_ENTRY *e = &restores[restores_count];
        int fields;

        if ( line[0] == '#' || line[0] == '\n' || line[0] == '\r' )
            continue;
        memset( e, 0, sizeof(*e) );
        fields = sscanf( line, "%31s %15s %7s %47s %63s",
                         e->id, e->player, e->kind, e->stamp, e->file );
        if ( fields < 4
        ||   ( strcmp( e->kind, "gear" ) && strcmp( e->kind, "stash" )
            && strcmp( e->kind, "import" ) )
        ||   !restore_word_ok( e->id, false ) || !restore_word_ok( e->player, false )
        ||   !restore_word_ok( e->stamp, true )
        ||   ( e->file[0] != '\0' && !restore_word_ok( e->file, true ) )
        ||   strstr( e->file, ".." ) != NULL )
        {
            snprintf( buf, sizeof(buf), "Restores: line not understood: %.200s", line );
            log_string( buf );
            continue;
        }
        toc_strlcpy( e->player, capitalize( e->player ), sizeof(e->player) );
        restores_count++;
    }
    fclose( fp );

    /* A file from git history becomes a snapshot PRESTORE can see. */
    for ( i = 0; i < restores_count; i++ )
    {
        RESTORE_ENTRY *e = &restores[i];
        char from[MAX_INPUT_LENGTH], dir[MAX_INPUT_LENGTH], to[MAX_STRING_LENGTH];
        struct stat st;

        if ( e->file[0] == '\0' )
            continue;
        snprintf( from, sizeof(from), "%s%s", RESTORES_DIR, e->file );
        snprintf( dir, sizeof(dir), "%s%s", PLAYER_VER_DIR, e->player );
        snprintf( to, sizeof(to), "%s/%s.%.15s.import", dir, e->player, e->stamp );
        if ( stat( to, &st ) == 0 )
            continue;                   /* installed at an earlier boot */
        if ( !restore_file_whole( from ) )
        {
            snprintf( buf, sizeof(buf), "Restores: %s's file %s is missing or not whole; "
                      "not installed.", e->player, e->file );
            log_string( buf );
            continue;
        }
        if ( ( mkdir( PLAYER_VER_DIR, 0755 ) != 0 && errno != EEXIST )
        ||   ( mkdir( dir, 0755 ) != 0 && errno != EEXIST )
        ||   !restore_copy( from, to ) )
        {
            snprintf( buf, sizeof(buf), "Restores: could not install %s for %s.",
                      e->file, e->player );
            log_string( buf );
            continue;
        }
        snprintf( buf, sizeof(buf), "Restores: installed %s as %s's snapshot %.15s.import "
                  "(request %s).", e->file, e->player, e->stamp, e->id );
        log_string( buf );
    }
}

/* The snapshot a stamp names: "<Player>.<stamp>" exactly, or the one
   name it is a prefix of. */
static bool restore_find_snapshot( const RESTORE_ENTRY *e, char *path, size_t size )
{
    char dir[MAX_INPUT_LENGTH];
    char want[MAX_INPUT_LENGTH];
    char found[MAX_INPUT_LENGTH] = "";
    DIR *dp;
    struct dirent *de;
    int matches = 0;

    snprintf( dir, sizeof(dir), "%s%s", PLAYER_VER_DIR, e->player );
    /* A request that brought its own file means the copy boot installed. */
    if ( e->file[0] != '\0' )
        snprintf( want, sizeof(want), "%s.%.15s.import", e->player, e->stamp );
    else
        snprintf( want, sizeof(want), "%s.%s", e->player, e->stamp );
    if ( ( dp = opendir( dir ) ) == NULL )
        return false;
    while ( ( de = readdir( dp ) ) != NULL )
    {
        if ( !strcmp( de->d_name, want ) )
        {
            toc_strlcpy( found, de->d_name, sizeof(found) );
            matches = 1;
            break;
        }
        if ( !strncmp( de->d_name, want, strlen( want ) ) )
        {
            toc_strlcpy( found, de->d_name, sizeof(found) );
            matches++;
        }
    }
    closedir( dp );
    if ( matches != 1 )
        return false;
    if ( (size_t) snprintf( path, size, "%s/%.255s", dir, found ) >= size )
        return false;
    return true;
}

static bool restore_corpse_waiting( const char *player )
{
    OBJ_DATA *obj;
    LIST_ITERATOR iter;

    FOR_EACH_OBJECT( iter, obj )
        if ( obj->item_type == ITEM_CORPSE_PC && obj->owner != NULL
        &&   !str_cmp( obj->owner, player ) && obj->contains != NULL )
            return true;
    return false;
}

/* From the nanny, once they are in their room: their requests, once. */
void restores_login( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    char why[MAX_INPUT_LENGTH];
    char path[MAX_STRING_LENGTH];
    char mark[64];
    int i, added;
    bool changed = false;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    for ( i = 0; i < restores_count; i++ )
    {
        RESTORE_ENTRY *e = &restores[i];

        if ( str_cmp( e->player, ch->name ) || !strcmp( e->kind, "import" ) )
            continue;
        snprintf( mark, sizeof(mark), "restore:%s", e->id );
        if ( player_fix_has( ch, mark ) )
            continue;
        if ( restore_corpse_waiting( ch->name ) )
        {
            snprintf( buf, sizeof(buf), "Restores: %s waits -- %s's corpse still holds "
                      "things.", e->id, ch->name );
            log_string( buf );
            continue;
        }
        if ( !restore_find_snapshot( e, path, sizeof(path) ) )
        {
            snprintf( buf, sizeof(buf), "Restores: %s -- no single snapshot of %s matches %s.",
                      e->id, ch->name, e->stamp );
            log_string( buf );
            continue;
        }

        player_snapshot_milestone( ch, "gitrestore", true );
        added = !strcmp( e->kind, "gear" )
              ? gear_restore_from_file( ch, path, why, sizeof(why) )
              : stash_restore_from_file( ch, path, why, sizeof(why) );
        /* Once either way: a snapshot that does not read now never will. */
        player_fix_record( ch, mark );
        changed = true;
        if ( added < 0 )
        {
            snprintf( buf, sizeof(buf), "Restores: %s for %s refused: %s.",
                      e->id, ch->name, why );
            log_string( buf );
            wizinfo( buf, LEVEL_IMMORTAL );
            continue;
        }
        corpse_registry_forget_player( ch->name );
        snprintf( buf, sizeof(buf), "Restores: %s gave %s back %d %s object%s from %.300s.",
                  e->id, ch->name, added, e->kind, added == 1 ? "" : "s", path );
        log_string( buf );
        wizinfo( buf, LEVEL_IMMORTAL );
        if ( added > 0 )
        {
            snprintf( buf, sizeof(buf),
                      "{0BThe staff have given back %d object%s you lost; %s.{00\n\r",
                      added, added == 1 ? "" : "s",
                      !strcmp( e->kind, "gear" ) ? "they are in your inventory"
                                                 : "they are in your stash" );
            send_to_char( buf, ch );
        }
    }
    if ( changed )
        save_char_obj( ch );
}
