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
    bool          held;         /* a transfer under way: not written */
    int           pending;      /* PEND_*: whose receipt is still open */
    char          op[64];       /* that receipt: death:<id>, resurrect:<id> */
    bool          record_ok;    /* death: the record is on the disk */
    time_t        last_try;     /* when it was last pushed toward settling */
} CORPSE_TRACK;

/*
 * A corpse whose contents are moving between it and its owner's file is
 * PENDING: a death (the file still held everything until the owner's
 * post-death save) or a resurrection (the corpse's things given back).
 * Its receipt sits in the ledger, the mark restore:<op> goes in the
 * owner's Fixes, and it settles only from the owner's FILE: a save of
 * theirs on the disk with the mark commits it; a file without the mark
 * undoes it. Nothing in between is taken for either.
 */
#define PEND_NONE        0
#define PEND_DEATH       1
#define PEND_RESURRECT   2
#define PEND_RETRY_SECS  10

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

static OBJ_DATA *corpse_make_object( const CORPSE_RECORD *rec );
static ROOM_INDEX_DATA *corpse_room( int vnum, char *note, size_t size );
static void corpse_fill( OBJ_DATA *corpse, OBJ_DATA *list );

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
    ROOM_INDEX_DATA *room;
    const char *outcome = "archived";
    int left = 0;
    OBJ_DATA *o;

    /* A transfer under way: the record on the disk is the one copy that
       says what the corpse held before it began, and the object may be
       empty now (ACCEPT took everything out). Archiving it from the
       object wrote the emptied corpse into history and removed the held
       record (review, 2026-10-27). The object goes; the record stays as
       it was until the transfer settles. */
    if ( t->held || t->pending != PEND_NONE )
    {
        snprintf( buf, sizeof(buf), "the object ended (%s: %s) while a transfer was "
                  "unsettled; its record is kept as it was", state, why );
        corpse_log( &t->rec, buf );
        t->corpse = NULL;
        return;
    }
    room = corpse_where( t->corpse, &carrier );

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
        else if ( !durable_dir_sync( path ) )
            bug( "corpses: an ended corpse's removal is not confirmed on the disk", 0 );
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
        if ( rename( from, to ) != 0 )
        {
            left++;
            continue;
        }
        /* Both directories: gone from live/ and arrived in history. */
        {
            bool from_ok = durable_dir_sync( from );
            bool to_ok = durable_dir_sync( to );

            recovery_record( "corpse", from_ok && to_ok ? "archived" : "archive-unconfirmed",
                             rec.owner, rec.id, rec.state, "corpse keeper",
                             from_ok && to_ok ? "its end state, kept aside, reached history"
                             : "its end state was moved to history, but the move is not "
                               "confirmed on the disk" );
        }
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

    /*
     * A death is a transfer: everything carried is in the corpse now, and
     * the owner's file still holds it all until their post-death save
     * (review, 2026-10-27: that save was commented out, so a crash laid
     * the corpse at boot beside a file holding the same things). The
     * receipt first, then the mark in their memory -- every later save of
     * theirs carries it -- then the record, held: the post-death save in
     * raw_kill settles it (corpse_registry_death_settle), and a crash at
     * any point is settled from their file. Without the receipt or the
     * mark the old way is all there is: the corpse kept as it lies.
     */
    snprintf( t->op, sizeof(t->op), "death:%s", t->rec.id );
    {
        char mark[96];

        snprintf( mark, sizeof(mark), "restore:%s", t->op );
        snprintf( buf, sizeof(buf), "corpse %s in room %d", t->rec.id, t->rec.room );
        if ( !player_fix_can_record( ch, mark ) )
            bug( "corpse_registry_died: the Fixes list is full; the death is not ledgered", 0 );
        else if ( !recovery_record( "request", "pending", ch->name, t->op, "death",
                                    playlog_cause(), buf ) )
            bug( "corpse_registry_died: the ledger refused the death's receipt", 0 );
        else if ( !player_fix_record( ch, mark ) )
        {
            recovery_record( "request", "abandoned", ch->name, t->op, "death", "-",
                             "the mark could not be kept; the corpse is kept as it lies" );
            bug( "corpse_registry_died: the death's mark could not be kept", 0 );
        }
        else
        {
            t->pending = PEND_DEATH;
            t->held = true;
            t->last_try = current_time;
        }
        if ( t->pending == PEND_NONE )
            t->op[0] = '\0';
    }

    /* On the disk before the game goes on: the death is the moment it
       matters most. */
    if ( track_write( t ) )
        t->record_ok = true;
    else
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

/*
 * Resurrection gives a corpse's contents to its owner (resurrect.c), and
 * the gift is only real once the owner's file is on the disk. Until then
 * the corpse's live record must stay exactly as it was before anything
 * moved -- it is the only other copy (review, 2026-10-26: ACCEPT ended the
 * corpse and only then saved, and a failed save with a crash lost both).
 *
 * HOLD writes the record now, on the disk, and stops every later write
 * of it. UNHOLD lets it be written again (the transfer was put back).
 * TRANSFERRED moves the held record -- exactly what was given -- into the
 * owner's history as "resurrected" and stops keeping the corpse; it says
 * false if the record could not be moved out of live/, which the caller
 * must not then call done: a live record would be laid again at boot.
 */
bool corpse_registry_hold( OBJ_DATA *corpse, char *id, size_t size )
{
    int i = track_find( corpse );

    if ( size > 0 )
        id[0] = '\0';
    /* One transfer at a time: a death still settling, or another call. */
    if ( i < 0 || tracks[i].held || tracks[i].pending != PEND_NONE
    ||   !track_write( &tracks[i] ) )
        return false;
    tracks[i].held = true;
    toc_strlcpy( id, tracks[i].rec.id, size );
    return true;
}

void corpse_registry_unhold( OBJ_DATA *corpse )
{
    int i = track_find( corpse );

    if ( i >= 0 )
    {
        tracks[i].held = false;
        tracks[i].dirty = true;
        tracks[i].pending = PEND_NONE;
        tracks[i].op[0] = '\0';
    }
}

/* The held live record into history under `label`, by rename: what is
   moved is exactly what was on the disk. DURABLE_OK only when both
   directories confirm it -- the name gone from live/ and arrived in
   history; DURABLE_UNCERTAIN when it was renamed but either is not
   confirmed (a power cut could leave it where it was), so a caller keeps
   its receipt open; DURABLE_FAILED when nothing moved. Only the arrival
   used to be checked (review, 2026-10-27). */
static int corpse_live_to_history( const CORPSE_RECORD *rec, const char *label )
{
    char from[MAX_STRING_LENGTH], to[MAX_STRING_LENGTH], hdir[MAX_INPUT_LENGTH];
    bool from_ok, to_ok;

    live_path( rec, from, sizeof(from) );
    if ( !corpse_dirs( rec->owner, hdir, sizeof(hdir) ) )
        return DURABLE_FAILED;
    history_name( hdir, rec->id, label, to, sizeof(to) );
    if ( recovery_fault( "corpse-move" ) || rename( from, to ) != 0 )
        return DURABLE_FAILED;
    from_ok = durable_dir_sync( from );
    to_ok = durable_dir_sync( to );
    return from_ok && to_ok ? DURABLE_OK : DURABLE_UNCERTAIN;
}

/* ACCEPT: the held corpse's contents are going to their owner under
   this receipt (resurrect.c). The owner's next save on the disk holding
   the mark settles it (corpse_registry_owner_saved). */
void corpse_registry_pending( OBJ_DATA *corpse, const char *op )
{
    int i = track_find( corpse );

    if ( i < 0 )
        return;
    tracks[i].pending = PEND_RESURRECT;
    toc_strlcpy( tracks[i].op, op, sizeof(tracks[i].op) );
    tracks[i].last_try = current_time;
}

/* Whether this corpse's transfer is still open. */
bool corpse_registry_is_pending( OBJ_DATA *corpse )
{
    int i = track_find( corpse );

    return i >= 0 && tracks[i].pending != PEND_NONE;
}

/* Whether `obj` is, or lies inside, a corpse whose death has not reached
   its owner's file: nothing may come out of it or carry it off, since the
   file may still hold the same things (get_obj asks). */
bool corpse_registry_settling( OBJ_DATA *obj )
{
    OBJ_DATA *top;
    int i;

    if ( track_count == 0 )
        return false;
    for ( top = obj; top != NULL; top = top->in_obj )
        if ( ( i = track_find( top ) ) >= 0 && tracks[i].pending == PEND_DEATH )
            return true;
    return false;
}

static int track_find_op( const char *op )
{
    int i;

    for ( i = 0; i < track_count; i++ )
        if ( tracks[i].pending != PEND_NONE && !strcmp( tracks[i].op, op ) )
            return i;
    return -1;
}

static void pend_mark( const CORPSE_TRACK *t, char *mark, size_t size )
{
    snprintf( mark, size, "restore:%s", t->op );
}

/*
 * The owner's file holds the mark, on the disk: the transfer happened.
 * A death's corpse becomes an ordinary kept corpse; a resurrection's held
 * record goes to history and the corpse is spent. `owner` is the
 * character if one is loaded (whose spent mark is then dropped), or NULL
 * when the file was read. False if it could not be finished now: the
 * track stays pending and is tried again.
 */
static bool pend_commit( int i, CHAR_DATA *owner, const char *how )
{
    CORPSE_TRACK *t = &tracks[i];
    char mark[96], buf[MAX_STRING_LENGTH], op[64];
    int status;

    pend_mark( t, mark, sizeof(mark) );
    toc_strlcpy( op, t->op, sizeof(op) );
    if ( t->pending == PEND_DEATH )
    {
        if ( t->corpse == NULL )
        {
            /* The object ended while the death was unsettled (rotted,
               sacrificed): what it held goes to history now. */
            if ( corpse_live_to_history( &t->rec, "gone" ) == DURABLE_FAILED )
                return false;
        }
        if ( !recovery_record( "request", "committed", t->rec.owner, op, "death", "-",
                               how ) )
            return false;
        snprintf( buf, sizeof(buf), "the death reached the owner's file (%s)", how );
        corpse_log( &t->rec, buf );
        if ( owner != NULL )
            player_fix_forget( owner, mark );
        if ( t->corpse == NULL )
        {
            track_drop( i );
            return true;
        }
        t->pending = PEND_NONE;
        t->op[0] = '\0';
        t->held = false;
        t->dirty = true;
        return true;
    }

    /* A resurrection. */
    if ( recovery_fault( "crash-before-commit" ) )
        _exit( 3 );             /* the test of a crash between the two */
    status = corpse_live_to_history( &t->rec, "resurrected" );
    if ( status == DURABLE_FAILED )
    {
        if ( t->last_try == 0 || current_time - t->last_try >= 60 )
            bug( "corpses: a resurrected corpse's record could not leave live/; tried again", 0 );
        t->last_try = current_time;
        return false;
    }
    snprintf( buf, sizeof(buf), "ended (resurrected): everything in it went to its owner, "
              "whose file holds it (%s)%s", how, status == DURABLE_OK ? ""
              : " -- the move to history is not confirmed on the disk; the receipt stays "
                "open and is settled from their file" );
    corpse_log( &t->rec, buf );
    recovery_record( "corpse", status == DURABLE_OK ? "archived" : "archive-unconfirmed",
                     t->rec.owner, t->rec.id, "resurrected", playlog_cause(), buf );
    {
        char who[sizeof(t->rec.owner)];

        toc_strlcpy( who, t->rec.owner, sizeof(who) );
        track_drop( i );
        if ( status != DURABLE_OK
        ||   !recovery_record( "request", "committed", who, op, "resurrect", "-", how ) )
            return true;
    }
    if ( owner != NULL )
        player_fix_forget( owner, mark );
    return true;
}

/* Put a resurrected corpse back in the world from its held record: the
   gift never reached the owner's file. */
static bool pend_relay( int i )
{
    CORPSE_TRACK *t = &tracks[i];
    char path[MAX_STRING_LENGTH], why[MAX_INPUT_LENGTH], note[MAX_INPUT_LENGTH];
    OBJ_DATA *list = NULL, *corpse;
    ROOM_INDEX_DATA *room;
    CORPSE_RECORD rec;

    live_path( &t->rec, path, sizeof(path) );
    if ( corpse_file_read( path, &rec, &list, why, sizeof(why) ) < 0
    ||   ( room = corpse_room( rec.room, note, sizeof(note) ) ) == NULL
    ||   ( corpse = corpse_make_object( &rec ) ) == NULL )
    {
        snapshot_discard_gear( list );
        return false;
    }
    corpse_fill( corpse, list );
    corpse_registry_rebuilding = true;
    obj_to_room( corpse, room );
    corpse_registry_rebuilding = false;
    t->corpse = corpse;
    return true;
}

/*
 * The owner's file does NOT hold the mark: the transfer never reached it.
 * After a death, the file still holds everything the corpse holds, so
 * the corpse is a duplicate: its record goes to history as "undone" and
 * the object, with what is in it, goes. After a resurrection, the file
 * lacks the gift, so the corpse comes back as its held record says.
 */
static bool pend_undo( int i, const char *how )
{
    CORPSE_TRACK *t = &tracks[i];
    char buf[MAX_STRING_LENGTH], op[64];
    OBJ_DATA *corpse = t->corpse;

    toc_strlcpy( op, t->op, sizeof(op) );
    if ( t->pending == PEND_DEATH )
    {
        if ( corpse_live_to_history( &t->rec, "undone" ) == DURABLE_FAILED )
            return false;
        snprintf( buf, sizeof(buf), "undone: the death never reached their file, which still "
                  "holds everything (%s)", how );
        corpse_log( &t->rec, buf );
        recovery_record( "request", "abandoned", t->rec.owner, op, "death", "-", buf );
        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s was undone -- the death "
                  "never reached their file (%s).", t->rec.owner, t->rec.id, how );
        log_string( buf );
        track_drop( i );
        if ( corpse != NULL )
            extract_obj( corpse );      /* its twin is in their file */
        return true;
    }
    if ( corpse == NULL && !pend_relay( i ) )
        return false;
    t = &tracks[i];
    snprintf( buf, sizeof(buf), "the resurrection never reached the owner's file; the "
              "corpse lies again with everything in it (%s)", how );
    corpse_log( &t->rec, buf );
    recovery_record( "request", "abandoned", t->rec.owner, op, "resurrect", "-", buf );
    t->pending = PEND_NONE;
    t->op[0] = '\0';
    t->held = false;
    t->dirty = true;
    return true;
}

/* Before a save of `ch`: a death of theirs whose corpse record is not yet
   on the disk must not have its post-death file written first -- that
   file would hold neither the things nor a corpse that does. The save is
   refused and the old file stands. */
bool corpse_registry_may_save( CHAR_DATA *ch )
{
    char mark[96];
    int i;

    if ( ch == NULL || IS_NPC(ch) || track_count == 0 )
        return true;
    for ( i = 0; i < track_count; i++ )
    {
        CORPSE_TRACK *t = &tracks[i];

        if ( t->pending != PEND_DEATH || t->record_ok || str_cmp( t->rec.owner, ch->name ) )
            continue;
        pend_mark( t, mark, sizeof(mark) );
        if ( !player_fix_has( ch, mark ) )
            continue;
        if ( t->corpse != NULL && track_write( t ) )
            t->record_ok = true;
        else
            return false;
    }
    return true;
}

/* After a save of `ch` that is on the disk: every transfer of theirs
   whose mark it carried is settled. */
void corpse_registry_owner_saved( CHAR_DATA *ch )
{
    char mark[96];
    int i;

    if ( ch == NULL || IS_NPC(ch) || track_count == 0 )
        return;
    for ( i = track_count - 1; i >= 0; i-- )
    {
        if ( i >= track_count || tracks[i].pending == PEND_NONE
        ||   str_cmp( tracks[i].rec.owner, ch->name ) )
            continue;
        if ( tracks[i].pending == PEND_DEATH && !tracks[i].record_ok )
            continue;
        pend_mark( &tracks[i], mark, sizeof(mark) );
        if ( player_fix_has( ch, mark ) )
            pend_commit( i, ch, "their save reached the disk" );
    }
}

/* The end of a death (fight.c): the post-death file, on the disk, with
   the mark -- which settles the death through the save itself. */
void corpse_registry_death_settle( CHAR_DATA *ch )
{
    int i;
    bool any = false;

    if ( ch == NULL || IS_NPC(ch) )
        return;
    for ( i = 0; i < track_count; i++ )
        if ( tracks[i].pending == PEND_DEATH && !str_cmp( tracks[i].rec.owner, ch->name ) )
            any = true;
    if ( !any )
        return;
    /* "death-save-<Name>" fails this save alone, for the tests: the death
       snapshot's own save comes first and would take "save-<Name>". */
    {
        char point[64];

        snprintf( point, sizeof(point), "death-save-%s", ch->name );
        if ( recovery_fault( point ) )
        {
            log_string( "Corpse keeper: a death's save failed (injected by a test)." );
            return;
        }
    }
    if ( !save_char_obj( ch ) )
    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf), "Corpse keeper: %s's death %s; it is settled by their "
                  "next save on the disk.", ch->name,
                  save_char_obj_status() == DURABLE_UNCERTAIN
                  ? "was saved but is not confirmed on the disk" : "could not be saved" );
        log_string( buf );
    }
}

/* At login, from the file just read: a pending transfer of theirs that
   has a corpse is settled by its mark. False if `op` has none here, for
   the ledger's own reconciling (recovery.c). */
bool corpse_registry_reconcile_login( CHAR_DATA *ch, const char *op )
{
    char mark[96];
    int i = track_find_op( op );

    if ( i < 0 )
        return false;
    pend_mark( &tracks[i], mark, sizeof(mark) );
    if ( player_fix_has( ch, mark ) )
        pend_commit( i, ch, "settled at their login" );
    else
        pend_undo( i, "settled at their login" );
    return true;
}

/* Every few seconds: push open transfers toward settling. A death's
   record not yet on the disk is written; an owner in the game whose
   memory holds the mark is saved; an owner out of it is settled from
   their file. */
static void pend_retry( void )
{
    int i;

    for ( i = track_count - 1; i >= 0; i-- )
    {
        CORPSE_TRACK *t;
        CHAR_DATA *owner;
        bool logging_in = false;
        char mark[96];
        int has;

        if ( i >= track_count )
            continue;
        t = &tracks[i];
        if ( t->pending == PEND_NONE || current_time - t->last_try < PEND_RETRY_SECS )
            continue;
        t->last_try = current_time;
        if ( t->pending == PEND_DEATH && !t->record_ok && t->corpse != NULL
        &&   track_write( t ) )
            t->record_ok = true;
        pend_mark( t, mark, sizeof(mark) );
        if ( ( owner = player_in_game( t->rec.owner, &logging_in ) ) != NULL )
        {
            if ( logging_in || IS_NPC(owner) || !player_fix_has( owner, mark ) )
                continue;
            if ( t->pending == PEND_DEATH && !t->record_ok )
                continue;
            save_char_obj( owner );     /* settles it, through the save */
            return;                     /* the list may have changed */
        }
        has = player_file_fix_has( t->rec.owner, mark );
        if ( has == 1 && ( t->pending != PEND_DEATH || t->record_ok ) )
            pend_commit( i, NULL, "read from their file" );
        else if ( has == 0 )
            pend_undo( i, "read from their file" );
    }
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
    pend_retry();
    for ( i = track_count - 1; i >= 0; i-- )
    {
        CHAR_DATA *carrier;
        ROOM_INDEX_DATA *room;

        if ( tracks[i].held )
            continue;
        room = corpse_where( tracks[i].corpse, &carrier );
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

        if ( !tracks[i].held && corpse_where( tracks[i].corpse, &carrier ) != NULL )
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

            /* A resurrection the last run left pending: the owner's file
               says whether the gift reached it. If it did, the corpse is
               spent -- into history, never laid again; if it did not,
               nothing was given and the corpse lies where it was. */
            if ( corpse_file_header( path, &rec ) >= 0 )
            {
                char op[64], mark[96];
                int has, moved;

                snprintf( op, sizeof(op), "resurrect:%s", rec.id );
                snprintf( mark, sizeof(mark), "restore:%s", op );
                if ( recovery_request_state( op ) == RECOVERY_PENDING )
                {
                    has = player_file_fix_has( rec.owner, mark );
                    moved = has == 1 ? corpse_live_to_history( &rec, "resurrected" )
                                     : DURABLE_FAILED;
                    if ( moved != DURABLE_FAILED )
                    {
                        /* Renamed but not confirmed: the receipt stays open,
                           and the login (or the next boot) settles it from
                           the same mark. */
                        if ( moved == DURABLE_OK )
                            recovery_record( "request", "committed", rec.owner, op,
                                             "reconcile", "boot", "the owner's file held it; "
                                             "the corpse went to history at boot" );
                        corpse_log( &rec, "ended (resurrected): settled at boot -- the "
                                    "owner's file held everything" );
                        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s was "
                                  "resurrected before the restart; settled.", rec.owner, rec.id );
                        log_string( buf );
                        continue;
                    }
                    if ( has != 0 )
                    {
                        /* Cannot say: never laid in the world twice. */
                        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s has a "
                                  "resurrection pending that cannot be settled now; it is "
                                  "kept in live/ and not laid in the world.", rec.owner, rec.id );
                        log_string( buf );
                        bug( "corpse_registry_boot: a pending resurrection was left unsettled", 0 );
                        continue;
                    }
                    recovery_record( "request", "abandoned", rec.owner, op, "reconcile", "boot",
                                     "it never reached the owner's file; the corpse lies "
                                     "where it was" );
                }

                /* A death the last run left pending: marked, the post-death
                   file is on the disk and the corpse is theirs; not marked,
                   their file still holds everything, and the corpse --
                   its twin -- goes to history unlaid. */
                snprintf( op, sizeof(op), "death:%s", rec.id );
                snprintf( mark, sizeof(mark), "restore:%s", op );
                if ( recovery_request_state( op ) == RECOVERY_PENDING )
                {
                    has = player_file_fix_has( rec.owner, mark );
                    if ( has == 1 )
                        recovery_record( "request", "committed", rec.owner, op, "reconcile",
                                         "boot", "the owner's file held the death; the "
                                         "corpse is laid" );
                    else if ( has == 0 )
                    {
                        if ( corpse_live_to_history( &rec, "undone" ) == DURABLE_FAILED )
                        {
                            bug( "corpse_registry_boot: an undone death's record could not "
                                 "leave live/; it is not laid", 0 );
                            continue;
                        }
                        recovery_record( "request", "abandoned", rec.owner, op, "reconcile",
                                         "boot", "the death never reached their file, which "
                                         "still holds everything; the corpse is not laid" );
                        corpse_log( &rec, "undone at boot: the death never reached their "
                                    "file, which still holds everything" );
                        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s was not "
                                  "laid -- the death never reached their file, which still "
                                  "holds everything.", rec.owner, rec.id );
                        log_string( buf );
                        continue;
                    }
                    else
                    {
                        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse %s has a "
                                  "death pending that cannot be settled now (their file "
                                  "cannot be read); it is kept in live/ and not laid.",
                                  rec.owner, rec.id );
                        log_string( buf );
                        bug( "corpse_registry_boot: a pending death was left unsettled", 0 );
                        continue;
                    }
                }
            }
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
        if ( tracks[i].corpse == NULL )
        {
            snprintf( buf, sizeof(buf), "  %s  no longer in the world; its transfer (%s) "
                      "is still being settled\n\r", tracks[i].rec.id, tracks[i].op );
            toc_strlcat( out, buf, size );
            shown++;
            continue;
        }
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
