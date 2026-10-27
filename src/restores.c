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
 * A gear or stash request is applied at the player's next login, once.
 * Once is kept by the recovery ledger (recovery.c), which no restore of
 * the player's file can roll back. It used to be kept only in the file
 * ("restore:<id>" among the login fixes), and a full PRESTORE to the copy
 * taken just before the request -- the obvious undo -- took that mark
 * away, so the next login applied the same request again (handoff
 * review, 2026-10-23). The mark is still written to the file, as the one
 * way to tell, after a crash, whether a request that was pending reached
 * the file: pending in the ledger and marked in the file means it did.
 *
 *   pending     written before anything is applied
 *   committed   the player file holding the objects has been saved
 *   rejected    it can never apply (no such snapshot, one that is not
 *               whole, two that match); a new id is needed
 *   retry       noted, nothing more: a file that would not open, a save
 *               that failed, a corpse still holding things -- tried again
 *               at the next login
 *
 * Undoing a request is a new action -- a PRESTORE of the copy taken
 * before it, itself recorded -- and never makes the request apply again.
 * Ids are never reused.
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

typedef struct restore_entry
{
    char id[32];
    char player[16];
    char kind[8];
    char stamp[48];
    char file[64];
} RESTORE_ENTRY;

static RESTORE_ENTRY *restores = NULL;
static int restores_count = 0, restores_cap = 0;


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
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        RESTORE_ENTRY *e;
        int fields;

        /* As many as the file holds: a fixed table stopped at 200 and
           left every later request unread (handoff review, 2026-10-23). */
        if ( restores_count >= restores_cap )
        {
            int cap = restores_cap ? restores_cap * 2 : 64;
            RESTORE_ENTRY *grown = realloc( restores, (size_t) cap * sizeof(*grown) );

            if ( grown == NULL )
            {
                bug( "restores_boot: out of memory", 0 );
                break;
            }
            restores = grown;
            restores_cap = cap;
        }
        e = &restores[restores_count];

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
   name it is a prefix of. 1 found, 0 none, -1 more than one. */
static int restore_find_snapshot( const RESTORE_ENTRY *e, char *path, size_t size )
{
    char dir[MAX_INPUT_LENGTH];
    char want[MAX_INPUT_LENGTH];
    char found[MAX_INPUT_LENGTH] = "";
    DIR *dp;
    struct dirent *de;
    int matches = 0;
    bool exact = false;

    snprintf( dir, sizeof(dir), "%s%s", PLAYER_VER_DIR, e->player );
    /* A request that brought its own file means the copy boot installed. */
    if ( e->file[0] != '\0' )
        snprintf( want, sizeof(want), "%s.%.15s.import", e->player, e->stamp );
    else
        snprintf( want, sizeof(want), "%s.%s", e->player, e->stamp );
    if ( ( dp = opendir( dir ) ) == NULL )
        return 0;
    while ( ( de = readdir( dp ) ) != NULL )
    {
        if ( !strcmp( de->d_name, want ) )
        {
            toc_strlcpy( found, de->d_name, sizeof(found) );
            exact = true;
            break;
        }
        if ( !strncmp( de->d_name, want, strlen( want ) ) )
        {
            toc_strlcpy( found, de->d_name, sizeof(found) );
            matches++;
        }
    }
    closedir( dp );
    if ( !exact && matches > 1 )
        return -1;
    if ( !exact && matches == 0 )
        return 0;
    if ( (size_t) snprintf( path, size, "%s/%.255s", dir, found ) >= size )
        return 0;
    return 1;
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

/* Whether a snapshot can be read at all now (false: try again later) and,
   if so, whether it is a whole player file (false in *whole: never). */
static bool restore_readable( const char *path, bool *whole )
{
    FILE *fp = fopen( path, "r" );
    char line[MAX_INPUT_LENGTH];

    *whole = false;
    if ( fp == NULL )
        return false;
    while ( fgets( line, sizeof(line), fp ) != NULL )
        if ( !strncmp( line, "#END", 4 ) )
            *whole = true;
    if ( ferror( fp ) )
    {
        fclose( fp );
        return false;
    }
    fclose( fp );
    return true;
}

static void restore_note( const RESTORE_ENTRY *e, const char *state, const char *detail,
                          bool tell_staff )
{
    char buf[MAX_STRING_LENGTH];

    recovery_record( "request", state, e->player, e->id, e->kind, "restores.dat", detail );
    snprintf( buf, sizeof(buf), "Restores: %s for %s %s: %s.", e->id, e->player,
              !strcmp( state, "committed" ) ? "applied"
              : !strcmp( state, "rejected" ) ? "rejected for good"
              : "waits", detail );
    log_string( buf );
    if ( tell_staff )
        wizinfo( buf, LEVEL_IMMORTAL );
}

/* From the nanny, once they are in their room: their requests, once. */
void restores_login( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    char why[MAX_INPUT_LENGTH];
    char path[MAX_STRING_LENGTH];
    char mark[64];
    int i, added, found, state;
    bool whole;
    OBJ_DATA *list, *obj;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    for ( i = 0; i < restores_count; i++ )
    {
        RESTORE_ENTRY *e = &restores[i];

        if ( str_cmp( e->player, ch->name ) || !strcmp( e->kind, "import" ) )
            continue;
        snprintf( mark, sizeof(mark), "restore:%s", e->id );
        state = recovery_request_state( e->id );
        if ( state == RECOVERY_COMMITTED || state == RECOVERY_REJECTED )
            continue;
        /* The file says it landed: from before the ledger, or a crash
           between the save and the ledger's line. Either way, done. */
        if ( player_fix_has( ch, mark ) )
        {
            restore_note( e, "committed", state == RECOVERY_PENDING
                          ? "the player file already held it (finished after a crash)"
                          : "the player file already held it (applied before the ledger)",
                          false );
            continue;
        }
        if ( restore_corpse_waiting( ch->name ) )
        {
            snprintf( buf, sizeof(buf), "Restores: %s waits -- %s's corpse still holds "
                      "things.", e->id, ch->name );
            log_string( buf );
            continue;
        }
        found = restore_find_snapshot( e, path, sizeof(path) );
        if ( found < 0 )
        {
            restore_note( e, "rejected", "more than one snapshot matches its stamp", true );
            continue;
        }
        if ( found == 0 )
        {
            /* A file the request brought may not be installed yet; a stamp
               with no file names a snapshot that does not exist. */
            if ( e->file[0] != '\0' )
                restore_note( e, "retry", "its imported file is not installed yet", false );
            else
                restore_note( e, "rejected", "no snapshot matches its stamp", true );
            continue;
        }
        if ( !restore_readable( path, &whole ) )
        {
            restore_note( e, "retry", "its snapshot could not be read just now", true );
            continue;
        }
        if ( !whole )
        {
            restore_note( e, "rejected", "its snapshot is not a whole player file", true );
            continue;
        }

        /* Read aside first: nothing is promised until all of it read. */
        list = NULL;
        added = !strcmp( e->kind, "gear" )
              ? snapshot_read_gear( ch, path, why, sizeof(why), &list )
              : snapshot_read_stash( ch, path, why, sizeof(why), &list );
        if ( added < 0 )
        {
            restore_note( e, "rejected", why, true );
            continue;
        }
        /* The mark that will say it landed must fit whole, or a crash
           after the save would read it as never given. */
        if ( !player_fix_can_record( ch, mark ) )
        {
            snapshot_discard_gear( list );
            restore_note( e, "retry", "their Fixes list is full; the mark would not fit", true );
            continue;
        }
        /* The copy to undo it by, then the pending line: if either fails,
           nothing has been given and it is tried again next login. */
        if ( !player_snapshot_milestone( ch, "gitrestore", true ) )
        {
            snapshot_discard_gear( list );
            restore_note( e, "retry", "the copy before it could not be taken", true );
            continue;
        }
        snprintf( buf, sizeof(buf), "%d object%s from %.200s; undo with %s", added,
                  added == 1 ? "" : "s", path, player_snapshot_last_milestone() );
        if ( !recovery_record( "request", "pending", ch->name, e->id, e->kind,
                               "restores.dat", buf ) )
        {
            snapshot_discard_gear( list );
            restore_note( e, "retry", "the ledger could not be written", true );
            continue;
        }

        while ( ( obj = list ) != NULL )
        {
            list = obj->next_content;
            obj->next_content = NULL;
            if ( !strcmp( e->kind, "gear" ) )
                obj_to_char( obj, ch );
            else
                stash_receive( ch, obj );
        }
        if ( !player_fix_record( ch, mark ) )
            bug( "restores_login: a mark that fit a moment ago did not", 0 );
        corpse_registry_forget_player( ch->name );
        if ( !save_char_obj( ch ) )
        {
            /* Not on the disk (or not confirmed there): the next save will
               carry it and the mark, and the pending line is settled at
               the next login by the mark. */
            snprintf( buf, sizeof(buf), "Restores: %s for %s applied in memory, but the "
                      "save %s; it stays pending until the next login settles it.", e->id,
                      ch->name, save_char_obj_status() == DURABLE_UNCERTAIN
                      ? "is not confirmed on the disk" : "failed" );
            log_string( buf );
            wizinfo( buf, LEVEL_IMMORTAL );
        }
        else
        {
            snprintf( buf, sizeof(buf), "gave back %d %s object%s", added, e->kind,
                      added == 1 ? "" : "s" );
            restore_note( e, "committed", buf, true );
        }
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
}
