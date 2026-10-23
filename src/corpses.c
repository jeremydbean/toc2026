/***************************************************************************
 * corpses.c -- a player's corpse outlasts a restart, as it actually is.
 *
 * Owner, 2026-10-23, after Alaric died AFK in the Korzath maze: his corpse
 * rotted in half an hour, its gear lay on the floor, and the morning's
 * deploy restarted the game and took it. A player's corpse now lasts a
 * week (PC_CORPSE_TICKS) and survives restarts.
 *
 * The first version kept a list of untouched corpses and made each again
 * from its owner's death snapshot -- and dropped a corpse from the list
 * for good the moment anything came out of it, so a corpse half looted
 * lost the other half at the next restart (handoff review, 2026-10-23).
 * Now every player's corpse is written down as it actually is:
 *
 *   ../corpse/live/<id>.corpse   the corpse now: its room, its timer and
 *                                every object in it, at any depth
 *                                (corpse_file_write in save.c)
 *   ../corpse/history/<Owner>/<id>.death.corpse   as it was made
 *   ../corpse/history/<Owner>/<id>.<state>.corpse as it was at the end
 *   ../corpse/history/<Owner>/<id>.log            what went in and out,
 *                                                 when, and by whose command
 *
 * It is written at the death, then within a second of any change -- an
 * object out or in, the corpse moved -- and every ten minutes besides, for
 * its timer. At boot, every live corpse is made again in its room with
 * exactly what it held. When it ends -- picked up, rotted, purged,
 * sacrificed, a restore of its owner -- its last state goes to history
 * with the reason, and stays there: PRESTORE <player> CORPSES lists them,
 * and PRESTORE <player> CORPSE <id> GEAR gives back what one held.
 *
 * Not at shutdown: the world is freed then without anybody touching it,
 * and what is written is what lay there (corpse_registry_flush_all).
 ***************************************************************************/

#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "merc.h"

#define CORPSE_LIVE_DIR      CORPSE_DIR "live/"
#define CORPSE_HISTORY_DIR   CORPSE_DIR "history/"
#define CORPSE_LEGACY        CORPSE_DIR "registry.tsv"
#define CORPSE_REFRESH_SECS  600          /* the timer, written this often */

typedef struct corpse_track
{
    CORPSE_RECORD rec;
    OBJ_DATA     *corpse;
    bool          dirty;
} CORPSE_TRACK;

static CORPSE_TRACK *tracks = NULL;
static int track_count = 0, track_cap = 0;
static bool corpse_registry_rebuilding = false;
static time_t corpse_last_flush = 0, corpse_last_refresh = 0;
static unsigned corpse_id_counter = 0;
/* make_corpse puts a new corpse in its room before it is recorded: that
   is a death, not a corpse put down again (fight.c sets this). */
static bool adopting_blocked = false;

void corpse_registry_making( bool making )
{
    adopting_blocked = making;
}

extern bool merc_down;


static void corpse_new_id( char *id, size_t size )
{
    snprintf( id, size, "c%08lx%02x%04x",
              (unsigned long) current_time & 0xffffffffUL,
              ( ++corpse_id_counter ) & 0xffU,
              (unsigned) number_range( 0, 0xffff ) );
}

static int track_find( const OBJ_DATA *corpse )
{
    int i;

    if ( corpse == NULL || corpse->item_type != ITEM_CORPSE_PC )
        return -1;
    for ( i = 0; i < track_count; i++ )
        if ( tracks[i].corpse == corpse )
            return i;
    return -1;
}

static CORPSE_TRACK *track_add( void )
{
    if ( track_count >= track_cap )
    {
        int cap = track_cap ? track_cap * 2 : 64;
        CORPSE_TRACK *grown = realloc( tracks, (size_t) cap * sizeof(*grown) );

        if ( grown == NULL )
        {
            bug( "corpses: out of memory for the corpse list", 0 );
            return NULL;
        }
        tracks = grown;
        track_cap = cap;
    }
    memset( &tracks[track_count], 0, sizeof(tracks[0]) );
    return &tracks[track_count++];
}

static void track_drop( int i )
{
    tracks[i] = tracks[--track_count];
}

static bool corpse_dirs( const char *owner, char *hdir, size_t size )
{
    if ( !recovery_ensure_dir( CORPSE_DIR ) || !recovery_ensure_dir( CORPSE_LIVE_DIR )
    ||   !recovery_ensure_dir( CORPSE_HISTORY_DIR ) )
        return false;
    if ( hdir == NULL )
        return true;
    snprintf( hdir, size, "%s%s", CORPSE_HISTORY_DIR, capitalize( owner ) );
    return recovery_ensure_dir( hdir );
}

static void live_path( const CORPSE_RECORD *rec, char *path, size_t size )
{
    snprintf( path, size, "%s%s.corpse", CORPSE_LIVE_DIR, rec->id );
}

/* One line in the corpse's own history: what happened, when, by whom. */
static void corpse_log( const CORPSE_RECORD *rec, const char *text )
{
    char hdir[MAX_INPUT_LENGTH], path[MAX_STRING_LENGTH];
    FILE *fp;

    if ( !corpse_dirs( rec->owner, hdir, sizeof(hdir) ) )
        return;
    snprintf( path, sizeof(path), "%s/%s.log", hdir, rec->id );
    if ( ( fp = fopen( path, "a" ) ) == NULL )
        return;
    fprintf( fp, "%ld\t%s\t%s\n", (long) current_time, playlog_cause(), text );
    fclose( fp );
}

/* Where the corpse is, now: the room of whatever holds it at the top. */
static ROOM_INDEX_DATA *corpse_where( OBJ_DATA *corpse, CHAR_DATA **carrier )
{
    OBJ_DATA *top = corpse;

    *carrier = NULL;
    while ( top->in_obj != NULL )
        top = top->in_obj;
    if ( top->carried_by != NULL )
        *carrier = top->carried_by;
    return top->in_room;
}

static bool track_write( CORPSE_TRACK *t )
{
    char path[MAX_STRING_LENGTH];
    CHAR_DATA *carrier;
    ROOM_INDEX_DATA *room = corpse_where( t->corpse, &carrier );
    int status;

    if ( room != NULL )
        t->rec.room = room->vnum;
    t->rec.timer = t->corpse->timer;
    if ( !corpse_dirs( t->rec.owner, NULL, 0 ) )
    {
        t->dirty = true;
        return false;
    }
    live_path( &t->rec, path, sizeof(path) );
    status = corpse_file_write( path, &t->rec, t->corpse->contains );
    if ( status != DURABLE_OK )
    {
        /* In place but unconfirmed, or not written: written again next
           second, either way. */
        t->dirty = true;
        if ( status == DURABLE_FAILED )
            bug( "corpses: a corpse could not be written; it is tried again", 0 );
        return false;
    }
    t->dirty = false;
    return true;
}

/* A free name in a directory: "<id>.<label>.corpse", then _02... */
static void history_name( const char *dir, const char *id, const char *label,
                          char *path, size_t size )
{
    struct stat st;
    int n;

    snprintf( path, size, "%s/%s.%s.corpse", dir, id, label );
    for ( n = 2; stat( path, &st ) == 0 && n < 100; n++ )
        snprintf( path, size, "%s/%s.%s_%02d.corpse", dir, id, label, n );
}

/* A copy into the owner's history: as made ("death"), or as it ended.
   DURABLE_OK only when it is there and on the disk. */
static int track_history( CORPSE_TRACK *t, const char *label )
{
    char hdir[MAX_INPUT_LENGTH], path[MAX_STRING_LENGTH];
    int status;

    if ( !corpse_dirs( t->rec.owner, hdir, sizeof(hdir) ) )
    {
        bug( "corpses: a corpse's history directory could not be made", 0 );
        return DURABLE_FAILED;
    }
    history_name( hdir, t->rec.id, label, path, sizeof(path) );
    status = corpse_file_write( path, &t->rec, t->corpse != NULL ? t->corpse->contains : NULL );
    if ( status != DURABLE_OK )
        bug( "corpses: a corpse's history copy could not be written", 0 );
    return status;
}

/* End states waiting to reach history: <id>.ending.corpse in live/. */
static int corpse_pending_endings = 0;

/*
 * It ended: its last state into history with why, then out of the live
 * list. The live copy goes only once the end state is safely written --
 * into history, or, when history cannot be written, beside the live copy
 * as <id>.ending.corpse, which is moved into history later. A failed
 * history write used to delete the live copy all the same, and the exact
 * remainder of a looted corpse was gone (independent review, 2026-10-23).
 * Nothing keeps the object pointer after this: the corpse is about to be
 * carried, spilled or freed.
 */
static void track_archive( int i, const char *state, const char *why )
{
    CORPSE_TRACK *t = &tracks[i];
    char path[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *carrier;
    ROOM_INDEX_DATA *room = corpse_where( t->corpse, &carrier );
    const char *outcome = "archived";
    int left = 0;
    OBJ_DATA *o;

    if ( room != NULL )
        t->rec.room = room->vnum;
    t->rec.timer = t->corpse->timer;
    toc_strlcpy( t->rec.state, state, sizeof(t->rec.state) );
    toc_strlcpy( t->rec.why, why, sizeof(t->rec.why) );
    for ( o = t->corpse->contains; o != NULL; o = o->next_content )
        left++;
    live_path( &t->rec, path, sizeof(path) );

    if ( track_history( t, state ) == DURABLE_OK )
    {
        if ( remove( path ) != 0 && errno != ENOENT )
            bug( "corpses: an ended corpse's live copy could not be removed", 0 );
        durable_dir_sync( path );
    }
    else
    {
        char ending[MAX_STRING_LENGTH];

        snprintf( ending, sizeof(ending), "%s%s.ending.corpse", CORPSE_LIVE_DIR, t->rec.id );
        if ( corpse_file_write( ending, &t->rec, t->corpse->contains ) != DURABLE_FAILED )
        {
            if ( remove( path ) != 0 && errno != ENOENT )
                bug( "corpses: an ended corpse's live copy could not be removed", 0 );
            durable_dir_sync( path );
            corpse_pending_endings++;
            outcome = "pending-archive";
        }
        else
        {
            /* Nothing could be written: the last good copy stays, renamed
               so the next boot does not lay it in the world again. */
            char stale[MAX_STRING_LENGTH];

            snprintf( stale, sizeof(stale), "%s%s.stale.corpse", CORPSE_LIVE_DIR, t->rec.id );
            if ( rename( path, stale ) != 0 )
                bug( "corpses: an ended corpse could not be recorded at all", 0 );
            outcome = "archive-failed";
        }
    }
    snprintf( buf, sizeof(buf), "ended (%s): %s; %d object%s left in it%s", state, why,
              left, left == 1 ? "" : "s",
              !strcmp( outcome, "archived" ) ? ""
              : !strcmp( outcome, "pending-archive" ) ? " (its history could not be written "
                "yet; the end state waits in live/ and is moved there later)"
              : " (NOTHING could be written; the last copy was kept as .stale)" );
    corpse_log( &t->rec, buf );
    recovery_record( "corpse", outcome, t->rec.owner, t->rec.id, state, playlog_cause(), buf );
    snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s %s%s.", t->rec.owner,
              t->rec.id, why, !strcmp( outcome, "archived" ) ? ""
              : " -- its end state is NOT yet in history" );
    log_string( buf );
    if ( strcmp( outcome, "archived" ) )
        wizinfo( buf, LEVEL_IMMORTAL );
    track_drop( i );
}

/* End states waiting in live/: into history, when it will take them. */
static void corpse_retry_endings( void )
{
    DIR *dp;
    struct dirent *de;
    int left = 0;

    if ( ( dp = opendir( CORPSE_LIVE_DIR ) ) == NULL )
        return;
    while ( ( de = readdir( dp ) ) != NULL )
    {
        CORPSE_RECORD rec;
        char from[MAX_INPUT_LENGTH * 2], to[MAX_STRING_LENGTH], hdir[MAX_INPUT_LENGTH];
        size_t len = strlen( de->d_name );

        if ( len < 15 || strcmp( de->d_name + len - 14, ".ending.corpse" ) != 0 )
            continue;
        snprintf( from, sizeof(from), "%s%s", CORPSE_LIVE_DIR, de->d_name );
        if ( corpse_file_header( from, &rec ) < 0 )
            continue;
        if ( !corpse_dirs( rec.owner, hdir, sizeof(hdir) ) )
        {
            left++;
            continue;
        }
        history_name( hdir, rec.id, rec.state[0] != '\0' ? rec.state : "ended", to, sizeof(to) );
        if ( rename( from, to ) != 0 || !durable_dir_sync( to ) )
        {
            left++;
            continue;
        }
        durable_dir_sync( from );
        recovery_record( "corpse", "archived", rec.owner, rec.id, rec.state, "corpse keeper",
                         "its end state, kept aside, reached history" );
        snprintf( to, sizeof(to), "Corpse keeper: %s's corpse %s's end state reached history.",
                  rec.owner, rec.id );
        log_string( to );
    }
    closedir( dp );
    corpse_pending_endings = left;
}


/*
 * A player's corpse was just made, by make_corpse, in their death room.
 * `snapshot` is the death snapshot just published, if it is this
 * character's; a corpse is written down whatever the snapshot came to,
 * since the corpse file is the record of what it holds.
 */
void corpse_registry_died( CHAR_DATA *ch, OBJ_DATA *corpse, const char *snapshot )
{
    CORPSE_TRACK *t;
    char buf[MAX_STRING_LENGTH];
    size_t len;

    if ( ch == NULL || IS_NPC(ch) || corpse == NULL || corpse->in_room == NULL )
        return;
    if ( ( t = track_add() ) == NULL )
        return;
    t->corpse = corpse;
    corpse_new_id( t->rec.id, sizeof(t->rec.id) );
    toc_strlcpy( t->rec.owner, ch->name, sizeof(t->rec.owner) );
    toc_strlcpy( t->rec.uid, recovery_uid( ch->name ), sizeof(t->rec.uid) );
    len = strlen( ch->name );
    if ( snapshot != NULL && !strncmp( snapshot, ch->name, len ) && snapshot[len] == '.'
    &&   strstr( snapshot, ".death" ) != NULL )
        toc_strlcpy( t->rec.snapshot, snapshot, sizeof(t->rec.snapshot) );
    toc_strlcpy( t->rec.state, "live", sizeof(t->rec.state) );
    t->rec.room = corpse->in_room->vnum;
    t->rec.died = (long) current_time;
    t->rec.level = ch->level;
    t->rec.owned = corpse->owner != NULL;

    /* On the disk before the game goes on: the death is the moment it
       matters most. */
    if ( !track_write( t ) )
        t->dirty = true;
    track_history( t, "death" );
    {
        int n = 0;
        OBJ_DATA *o;

        for ( o = corpse->contains; o != NULL; o = o->next_content )
            n++;
        snprintf( buf, sizeof(buf), "made in room %d holding %d object%s%s%s",
                  t->rec.room, n, n == 1 ? "" : "s",
                  t->rec.snapshot[0] != '\0' ? "; death snapshot " : "; no death snapshot",
                  t->rec.snapshot );
    }
    corpse_log( &t->rec, buf );
    recovery_record( "corpse", "created", ch->name, t->rec.id, "death", "-", buf );
}

/* Something went into or came out of a container: if the container is,
   or is inside, a player's corpse, that corpse is written again. */
void corpse_note_change( OBJ_DATA *container, OBJ_DATA *obj, bool in )
{
    OBJ_DATA *top = container;
    char buf[MAX_STRING_LENGTH];
    int i = -1;

    if ( corpse_registry_rebuilding || merc_down || container == NULL || track_count == 0 )
        return;
    for ( ; top != NULL; top = top->in_obj )
        if ( ( i = track_find( top ) ) >= 0 )
            break;
    if ( i < 0 )
        return;
    tracks[i].dirty = true;
    if ( obj != NULL )
    {
        snprintf( buf, sizeof(buf), "%s %s (vnum %d)%s%s", in ? "put in" : "took out",
                  obj->short_descr != NULL ? obj->short_descr : "something",
                  obj->pIndexData != NULL ? obj->pIndexData->vnum : 0,
                  container != tracks[i].corpse ? " -- inside " : "",
                  container != tracks[i].corpse && container->short_descr != NULL
                      ? container->short_descr : "" );
        corpse_log( &tracks[i].rec, buf );
    }
}

/* The corpse itself was picked up, or is gone (rotted, purged,
   sacrificed): what it held then goes to history. */
void corpse_registry_touched( OBJ_DATA *corpse, const char *why )
{
    int i;

    if ( corpse_registry_rebuilding || merc_down )
        return;
    if ( ( i = track_find( corpse ) ) >= 0 )
    {
        const char *state = strstr( why, "rot" ) != NULL ? "rotted"
                          : strstr( why, "picked" ) != NULL ? "carried" : "gone";
        track_archive( i, state, why );
    }
}

/* It moved -- dragged, or teleported -- and is still a corpse. One that
   ended (picked up) and has been put down in a room again is kept again,
   as a new record: dropped, it is as much at risk as it ever was. */
void corpse_registry_moved( OBJ_DATA *corpse )
{
    CORPSE_TRACK *t;
    char owner[16];
    char buf[MAX_STRING_LENGTH];
    int i;

    if ( corpse_registry_rebuilding || merc_down || corpse == NULL
    ||   corpse->item_type != ITEM_CORPSE_PC )
        return;
    if ( ( i = track_find( corpse ) ) >= 0 )
    {
        tracks[i].dirty = true;
        return;
    }
    if ( corpse->in_room == NULL || corpse->contains == NULL || adopting_blocked )
        return;
    /* Whose: the owner, or for a lootable one the name it was made with. */
    if ( corpse->owner != NULL )
        toc_strlcpy( owner, corpse->owner, sizeof(owner) );
    else
        one_argument( corpse->name, owner );
    if ( owner[0] == '\0' || ( t = track_add() ) == NULL )
        return;
    t->corpse = corpse;
    corpse_new_id( t->rec.id, sizeof(t->rec.id) );
    toc_strlcpy( t->rec.owner, capitalize( owner ), sizeof(t->rec.owner) );
    toc_strlcpy( t->rec.uid, recovery_uid( owner ), sizeof(t->rec.uid) );
    toc_strlcpy( t->rec.state, "live", sizeof(t->rec.state) );
    t->rec.room = corpse->in_room->vnum;
    t->rec.died = (long) current_time;
    t->rec.level = corpse->level;
    t->rec.owned = corpse->owner != NULL;
    t->dirty = true;
    snprintf( buf, sizeof(buf), "put down in room %d and kept again", t->rec.room );
    corpse_log( &t->rec, buf );
    recovery_record( "corpse", "created", t->rec.owner, t->rec.id, "dropped",
                     playlog_cause(), buf );
}

/* A restore gave the player their things back: none of their corpses may
   come back at the next boot too. Each ends in history, with that said. */
void corpse_registry_forget_player( const char *name )
{
    int i;

    for ( i = track_count - 1; i >= 0; i-- )
        if ( !str_cmp( tracks[i].rec.owner, name ) )
            track_archive( i, "restored", "the player was restored; it will not "
                           "come back after a restart" );
}

/* Whether a player has a corpse being kept -- in the world this boot. */
bool corpse_registry_has( const char *name )
{
    int i;

    for ( i = 0; i < track_count; i++ )
        if ( !str_cmp( tracks[i].rec.owner, name ) )
            return true;
    return false;
}

/* Every pulse: what changed, written within a second; the timers every
   ten minutes; a corpse that has ended up carried by somebody, archived. */
void corpse_registry_update( void )
{
    int i;

    if ( corpse_pending_endings > 0 && track_count == 0 && current_time % 60 == 0
    &&   current_time != corpse_last_flush )
    {
        corpse_last_flush = current_time;
        corpse_retry_endings();
    }
    if ( track_count == 0 || corpse_registry_rebuilding || merc_down )
        return;
    if ( current_time - corpse_last_refresh >= CORPSE_REFRESH_SECS )
    {
        corpse_last_refresh = current_time;
        for ( i = 0; i < track_count; i++ )
            tracks[i].dirty = true;
    }
    if ( current_time == corpse_last_flush )
        return;
    corpse_last_flush = current_time;
    if ( corpse_pending_endings > 0 && current_time % 60 == 0 )
        corpse_retry_endings();
    for ( i = track_count - 1; i >= 0; i-- )
    {
        CHAR_DATA *carrier;
        ROOM_INDEX_DATA *room = corpse_where( tracks[i].corpse, &carrier );

        if ( room == NULL )
        {
            char why[MAX_INPUT_LENGTH];

            snprintf( why, sizeof(why), "carried by %s",
                      carrier != NULL && carrier->name != NULL ? carrier->name : "nobody" );
            track_archive( i, "carried", why );
            continue;
        }
        if ( tracks[i].dirty )
            track_write( &tracks[i] );
    }
}

/* At shutdown, before the world goes: every corpse as it lies. */
void corpse_registry_flush_all( void )
{
    int i;

    for ( i = 0; i < track_count; i++ )
    {
        CHAR_DATA *carrier;

        if ( corpse_where( tracks[i].corpse, &carrier ) != NULL )
            track_write( &tracks[i] );
    }
}


/* A corpse object for an owner, as make_corpse dresses one. */
static OBJ_DATA *corpse_make_object( const CORPSE_RECORD *rec )
{
    OBJ_INDEX_DATA *pCorpse = get_obj_index( OBJ_VNUM_CORPSE_PC );
    OBJ_DATA *corpse;
    char buf[MAX_STRING_LENGTH];

    if ( pCorpse == NULL )
        return NULL;
    corpse = create_object( pCorpse, 0 );
    snprintf( buf, sizeof(buf), "%s corpse", rec->owner );
    free_string( corpse->name );
    corpse->name = str_dup( buf );
    snprintf( buf, sizeof(buf), corpse->short_descr, rec->owner );
    free_string( corpse->short_descr );
    corpse->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), corpse->description, rec->owner );
    free_string( corpse->description );
    corpse->description = str_dup( buf );
    corpse->owner = rec->owned ? str_dup( rec->owner ) : NULL;
    corpse->level = (sh_int) rec->level;
    corpse->cost = 0;
    corpse->timer = (sh_int) URANGE( 60, rec->timer > 0 ? rec->timer : PC_CORPSE_TICKS,
                                     PC_CORPSE_TICKS );
    return corpse;
}

static ROOM_INDEX_DATA *corpse_room( int vnum, char *note, size_t size )
{
    ROOM_INDEX_DATA *room;

    note[0] = '\0';
    if ( ( room = get_room_index( vnum ) ) != NULL )
        return room;
    snprintf( note, size, " (room %d is gone; laid at the altar)", vnum );
    return get_room_index( ROOM_VNUM_ALTAR );
}

/* Put objects read aside into a corpse, in their order. */
static void corpse_fill( OBJ_DATA *corpse, OBJ_DATA *list )
{
    OBJ_DATA *obj;

    while ( ( obj = list ) != NULL )
    {
        list = obj->next_content;
        obj->next_content = NULL;
        obj_to_obj( obj, corpse );
    }
}

/* The first version's list, from before the corpse files: each untouched
   corpse is made again from its death snapshot, then kept as the rest. */
static void corpse_migrate_legacy( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH];

    if ( ( fp = fopen( CORPSE_LEGACY, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        CORPSE_RECORD rec;
        DESCRIPTOR_DATA offline_desc;
        CHAR_DATA *vessel;
        ROOM_INDEX_DATA *room;
        OBJ_DATA *list = NULL, *obj, *corpse;
        CORPSE_TRACK *t;
        char path[MAX_STRING_LENGTH];
        char why[MAX_INPUT_LENGTH];
        char note[MAX_INPUT_LENGTH];
        int owned = 1;

        memset( &rec, 0, sizeof(rec) );
        if ( sscanf( line, "%15s %255s %d %ld %d %d", rec.owner, rec.snapshot,
                     &rec.room, &rec.died, &rec.level, &owned ) < 5 )
            continue;
        rec.owned = owned != 0;
        if ( (long) current_time - rec.died > PC_CORPSE_TICKS * 60L )
            continue;
        snprintf( path, sizeof(path), "%s%s/%s", PLAYER_VER_DIR,
                  capitalize( rec.owner ), rec.snapshot );
        if ( ( vessel = offline_player_load( &offline_desc, rec.owner, NULL ) ) == NULL )
            continue;
        if ( snapshot_read_gear( vessel, path, why, sizeof(why), &list ) < 0 )
        {
            extract_char( vessel, true );
            snprintf( buf, sizeof(buf), "Corpse keeper: %s's old-list corpse not made "
                      "again: %s.", rec.owner, why );
            log_string( buf );
            continue;
        }
        extract_char( vessel, true );
        rec.timer = (int) ( PC_CORPSE_TICKS - ( (long) current_time - rec.died ) / 60 );
        corpse_new_id( rec.id, sizeof(rec.id) );
        toc_strlcpy( rec.uid, recovery_uid( rec.owner ), sizeof(rec.uid) );
        toc_strlcpy( rec.state, "live", sizeof(rec.state) );
        if ( ( corpse = corpse_make_object( &rec ) ) == NULL
        ||   ( room = corpse_room( rec.room, note, sizeof(note) ) ) == NULL )
        {
            snapshot_discard_gear( list );
            continue;
        }
        /* As make_corpse treats them: what goes off at a death goes. */
        while ( ( obj = list ) != NULL )
        {
            list = obj->next_content;
            obj->next_content = NULL;
            if ( IS_SET(obj->extra_flags, ITEM_ROT_DEATH)
            ||   IS_SET(obj->extra_flags, ITEM_INVENTORY) )
            {
                snapshot_discard_gear( obj );
                continue;
            }
            REMOVE_BIT( obj->extra_flags, ITEM_VIS_DEATH );
            obj_to_obj( obj, corpse );
        }
        obj_to_room( corpse, room );
        if ( ( t = track_add() ) != NULL )
        {
            t->rec = rec;
            t->corpse = corpse;
            track_write( t );
            track_history( t, "death" );
            corpse_log( &t->rec, "made again from its death snapshot (the old list)" );
        }
        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse made again in room %d "
                  "from %s%s.", rec.owner, room->vnum, rec.snapshot, note );
        log_string( buf );
    }
    fclose( fp );
    rename( CORPSE_LEGACY, CORPSE_LEGACY ".migrated" );
}

/* At boot, after the world: every live corpse, made again exactly. */
void corpse_registry_boot( void )
{
    DIR *dp;
    struct dirent *de;
    char buf[MAX_STRING_LENGTH];
    int made = 0, failed = 0;

    track_count = 0;
    corpse_last_refresh = current_time;
    corpse_registry_rebuilding = true;
    if ( corpse_dirs( "-", NULL, 0 ) && ( dp = opendir( CORPSE_LIVE_DIR ) ) != NULL )
    {
        while ( ( de = readdir( dp ) ) != NULL )
        {
            CORPSE_RECORD rec;
            OBJ_DATA *list = NULL, *corpse;
            ROOM_INDEX_DATA *room;
            CORPSE_TRACK *t;
            char path[MAX_INPUT_LENGTH * 2];
            char why[MAX_INPUT_LENGTH];
            char note[MAX_INPUT_LENGTH];
            size_t len = strlen( de->d_name );

            if ( len < 8 || strcmp( de->d_name + len - 7, ".corpse" ) != 0 )
                continue;
            /* Ended corpses waiting for history, and ones kept stale when
               nothing could be written: records, not corpses in the world. */
            if ( strstr( de->d_name, ".ending.corpse" ) != NULL
            ||   strstr( de->d_name, ".stale.corpse" ) != NULL )
            {
                if ( strstr( de->d_name, ".ending.corpse" ) != NULL )
                    corpse_pending_endings++;
                continue;
            }
            snprintf( path, sizeof(path), "%s%s", CORPSE_LIVE_DIR, de->d_name );
            if ( corpse_file_read( path, &rec, &list, why, sizeof(why) ) < 0
            ||   ( corpse = corpse_make_object( &rec ) ) == NULL
            ||   ( room = corpse_room( rec.room, note, sizeof(note) ) ) == NULL )
            {
                /* Never thrown away: set aside where staff can see it. */
                char aside[MAX_INPUT_LENGTH * 2 + 16];

                snapshot_discard_gear( list );
                snprintf( aside, sizeof(aside), "%s.unreadable", path );
                rename( path, aside );
                snprintf( buf, sizeof(buf), "Corpse keeper: %.300s could not be made again "
                          "(%.200s); kept as %.320s.", path, why, aside );
                log_string( buf );
                bug( "corpse_registry_boot: a corpse file could not be read", 0 );
                failed++;
                continue;
            }
            corpse_fill( corpse, list );
            obj_to_room( corpse, room );
            if ( ( t = track_add() ) != NULL )
            {
                t->rec = rec;
                t->corpse = corpse;
                if ( note[0] != '\0' )
                    t->dirty = true;
                corpse_log( &t->rec, note[0] != '\0' ? note + 1 : "made again after a restart" );
            }
            made++;
            snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s made again in room "
                      "%d with %d object%s%s.", rec.owner, rec.id, room->vnum,
                      rec.objects, rec.objects == 1 ? "" : "s", note );
            log_string( buf );
        }
        closedir( dp );
    }
    corpse_migrate_legacy();
    if ( corpse_pending_endings > 0 )
        corpse_retry_endings();
    corpse_registry_rebuilding = false;
    if ( made > 0 || failed > 0 )
    {
        snprintf( buf, sizeof(buf), "Corpse keeper: %d corpse%s made again, %d set aside.",
                  made, made == 1 ? "" : "s", failed );
        log_string( buf );
    }
}


/* PRESTORE <player> CORPSES: every corpse of theirs, kept or ended. */
void corpse_registry_list( CHAR_DATA *ch, const char *name )
{
    char hdir[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char *out;
    size_t size = 64 * 1024;
    DIR *dp;
    struct dirent *de;
    int i, shown = 0;

    if ( ( out = malloc( size ) ) == NULL )
        return;
    snprintf( out, size, "Corpses of %s:\n\r", capitalize( name ) );
    for ( i = 0; i < track_count; i++ )
    {
        OBJ_DATA *o;
        int n = 0;
        CHAR_DATA *carrier;
        ROOM_INDEX_DATA *room;

        if ( str_cmp( tracks[i].rec.owner, name ) )
            continue;
        for ( o = tracks[i].corpse->contains; o != NULL; o = o->next_content )
            n++;
        room = corpse_where( tracks[i].corpse, &carrier );
        snprintf( buf, sizeof(buf), "  %s  in the world, room %d, %d thing%s in it, "
                  "%d ticks left\n\r", tracks[i].rec.id, room != NULL ? room->vnum : 0,
                  n, n == 1 ? "" : "s", tracks[i].corpse->timer );
        toc_strlcat( out, buf, size );
        shown++;
    }
    /* End states waiting to reach history, or kept stale. */
    if ( ( dp = opendir( CORPSE_LIVE_DIR ) ) != NULL )
    {
        while ( ( de = readdir( dp ) ) != NULL )
        {
            CORPSE_RECORD rec;
            char path[MAX_INPUT_LENGTH * 2];

            if ( strstr( de->d_name, ".ending.corpse" ) == NULL
            &&   strstr( de->d_name, ".stale.corpse" ) == NULL )
                continue;
            snprintf( path, sizeof(path), "%s%s", CORPSE_LIVE_DIR, de->d_name );
            if ( corpse_file_header( path, &rec ) < 0 || str_cmp( rec.owner, name ) )
                continue;
            snprintf( buf, sizeof(buf), "  %s  ended %s: %s; %d object%s in it then "
                      "(NOT yet in history)\n\r", rec.id, rec.state,
                      rec.why[0] != '\0' ? rec.why : "-", rec.objects,
                      rec.objects == 1 ? "" : "s" );
            toc_strlcat( out, buf, size );
            shown++;
        }
        closedir( dp );
    }
    snprintf( hdir, sizeof(hdir), "%s%s", CORPSE_HISTORY_DIR, capitalize( name ) );
    if ( ( dp = opendir( hdir ) ) != NULL )
    {
        while ( ( de = readdir( dp ) ) != NULL )
        {
            CORPSE_RECORD rec;
            char path[MAX_INPUT_LENGTH * 2];
            char when[32];
            time_t died;
            size_t len = strlen( de->d_name );

            if ( len < 8 || strcmp( de->d_name + len - 7, ".corpse" ) != 0
            ||   strstr( de->d_name, ".death" ) != NULL )
                continue;
            snprintf( path, sizeof(path), "%s/%s", hdir, de->d_name );
            if ( corpse_file_header( path, &rec ) < 0 )
                continue;
            died = (time_t) rec.died;
            strftime( when, sizeof(when), "%b %d %H:%M %Z", localtime( &died ) );
            snprintf( buf, sizeof(buf), "  %s  died %s, ended %s: %s; %d object%s in it then\n\r",
                      rec.id, when, rec.state, rec.why[0] != '\0' ? rec.why : "-",
                      rec.objects, rec.objects == 1 ? "" : "s" );
            toc_strlcat( out, buf, size );
            shown++;
        }
        closedir( dp );
    }
    if ( shown == 0 )
        toc_strlcat( out, "  none on record.\n\r", size );
    else
        toc_strlcat( out, "PRESTORE <player> CORPSE <id> SHOW lists what one held; GEAR "
                     "gives that back, once it is no longer in the world.\n\r", size );
    page_to_char( out, ch );
    free( out );
}

/*
 * The file to restore a corpse from: its end state in history, or, if it
 * never ended, its first copy -- and *live says it is still in the world.
 */
bool corpse_record_path( const char *owner, const char *id, char *path, size_t size,
                         bool *live, CORPSE_RECORD *rec )
{
    char hdir[MAX_INPUT_LENGTH];
    char best[MAX_INPUT_LENGTH * 2] = "";
    char death[MAX_INPUT_LENGTH * 2] = "";
    DIR *dp;
    struct dirent *de;
    size_t idlen = strlen( id );
    int i;

    *live = false;
    for ( i = 0; i < track_count; i++ )
        if ( !str_cmp( tracks[i].rec.id, id ) && !str_cmp( tracks[i].rec.owner, owner ) )
            *live = true;
    snprintf( hdir, sizeof(hdir), "%s%s", CORPSE_HISTORY_DIR, capitalize( owner ) );
    dp = opendir( hdir );
    while ( dp != NULL && ( de = readdir( dp ) ) != NULL )
    {
        size_t len = strlen( de->d_name );

        if ( strncmp( de->d_name, id, idlen ) != 0 || de->d_name[idlen] != '.'
        ||   len < 8 || strcmp( de->d_name + len - 7, ".corpse" ) != 0 )
            continue;
        if ( strstr( de->d_name + idlen, ".death" ) == de->d_name + idlen )
            toc_strlcpy( death, de->d_name, sizeof(death) );
        else if ( strcmp( de->d_name, best ) > 0 )
            toc_strlcpy( best, de->d_name, sizeof(best) );
    }
    if ( dp != NULL )
        closedir( dp );
    if ( best[0] == '\0' )
    {
        /* An end state still waiting to reach history, or one kept stale
           when nothing could be written, beats the copy made at death. */
        static const char *const aside[] = { "ending", "stale", NULL };
        int k;

        for ( k = 0; aside[k] != NULL; k++ )
        {
            snprintf( path, size, "%s%s.%s.corpse", CORPSE_LIVE_DIR, id, aside[k] );
            if ( corpse_file_header( path, rec ) > 0 && !str_cmp( rec->owner, owner ) )
                return true;
        }
    }
    if ( best[0] == '\0' && death[0] == '\0' )
        return false;
    snprintf( path, size, "%s/%s", hdir, best[0] != '\0' ? best : death );
    return corpse_file_header( path, rec ) > 0;
}
