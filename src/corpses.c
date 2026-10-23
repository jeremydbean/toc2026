/***************************************************************************
 * corpses.c -- a player's corpse outlasts a restart.
 *
 * Owner, 2026-10-23, after Alaric died AFK in the Korzath maze: his corpse
 * rotted in half an hour, its gear lay on the floor, and the morning's
 * deploy restarted the game and took it. A player's corpse now lasts days
 * (PC_CORPSE_TICKS), and every one is written down here when it is made:
 * whose it is, the room, and the "before death" snapshot taken a moment
 * before (player_snapshot_milestone). At boot, every corpse still on the
 * list is made again in its room from that snapshot.
 *
 * A corpse comes off the list -- for good -- the moment anything is taken
 * out of it, it is picked up, or it is gone (rotted, purged, sacrificed):
 * from then on the world, not the snapshot, says what is left, and making
 * it again would make two of something. A restore of the player from a
 * snapshot takes their corpses off too (PRESTORE, restores.c).
 *
 * The list is ../corpse/registry.tsv: owner, snapshot file, room, epoch of
 * death, level, owned (0 for a WANTED player's lootable corpse).
 ***************************************************************************/

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "merc.h"

#define CORPSE_REGISTRY      CORPSE_DIR "registry.tsv"
#define CORPSE_REGISTRY_MAX  256

typedef struct corpse_entry
{
    char      owner[16];
    char      snapshot[96];
    int       room;
    long      died;
    int       level;
    bool      owned;
    OBJ_DATA *corpse;            /* the object in this boot, or NULL */
} CORPSE_ENTRY;

static CORPSE_ENTRY corpse_registry[CORPSE_REGISTRY_MAX];
static int corpse_registry_count = 0;
static bool corpse_registry_rebuilding = false;

extern bool merc_down;


static void corpse_registry_write( void )
{
    FILE *fp;
    int i;

    if ( mkdir( CORPSE_DIR, 0755 ) != 0 && errno != EEXIST )
    {
        bug( "corpse_registry_write: cannot make " CORPSE_DIR, 0 );
        return;
    }
    if ( ( fp = fopen( CORPSE_REGISTRY ".tmp", "w" ) ) == NULL )
    {
        bug( "corpse_registry_write: cannot open " CORPSE_REGISTRY ".tmp", 0 );
        return;
    }
    for ( i = 0; i < corpse_registry_count; i++ )
    {
        const CORPSE_ENTRY *e = &corpse_registry[i];

        fprintf( fp, "%s\t%s\t%d\t%ld\t%d\t%d\n", e->owner, e->snapshot,
                 e->room, e->died, e->level, e->owned ? 1 : 0 );
    }
    temp_file_commit( fp, CORPSE_REGISTRY ".tmp", CORPSE_REGISTRY );
}

static int corpse_registry_find( const OBJ_DATA *corpse )
{
    int i;

    if ( corpse == NULL || corpse->item_type != ITEM_CORPSE_PC )
        return -1;
    for ( i = 0; i < corpse_registry_count; i++ )
        if ( corpse_registry[i].corpse == corpse )
            return i;
    return -1;
}

static void corpse_registry_remove( int i, const char *why )
{
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse off the list (%s).",
              corpse_registry[i].owner, why );
    log_string( buf );
    corpse_registry[i] = corpse_registry[--corpse_registry_count];
    corpse_registry_write();
}


/* A player's corpse was just made, by make_corpse, in their death room. */
void corpse_registry_died( CHAR_DATA *ch, OBJ_DATA *corpse )
{
    const char *snapshot = player_snapshot_last_milestone();
    CORPSE_ENTRY *e;
    size_t len;

    if ( ch == NULL || IS_NPC(ch) || corpse == NULL || corpse->in_room == NULL )
        return;
    /* Only the death snapshot of this very character will do. */
    len = strlen( ch->name );
    if ( snapshot == NULL || strncmp( snapshot, ch->name, len ) != 0
    ||   snapshot[len] != '.' || strstr( snapshot, ".death" ) == NULL )
        return;
    if ( corpse_registry_count >= CORPSE_REGISTRY_MAX )
    {
        /* The oldest makes room; it has had the longest to be fetched. */
        int i, oldest = 0;

        for ( i = 1; i < corpse_registry_count; i++ )
            if ( corpse_registry[i].died < corpse_registry[oldest].died )
                oldest = i;
        corpse_registry_remove( oldest, "the list is full" );
    }
    e = &corpse_registry[corpse_registry_count++];
    memset( e, 0, sizeof(*e) );
    toc_strlcpy( e->owner, ch->name, sizeof(e->owner) );
    toc_strlcpy( e->snapshot, snapshot, sizeof(e->snapshot) );
    e->room = corpse->in_room->vnum;
    e->died = (long) current_time;
    e->level = ch->level;
    e->owned = corpse->owner != NULL;
    e->corpse = corpse;
    corpse_registry_write();
}

/* Something came out of the corpse, or it was picked up, or it is gone:
   from now on the world says what is left. Not at shutdown, which frees
   the world without anybody having touched it. */
void corpse_registry_touched( OBJ_DATA *corpse, const char *why )
{
    int i;

    if ( corpse_registry_rebuilding || merc_down )
        return;
    if ( ( i = corpse_registry_find( corpse ) ) >= 0 )
        corpse_registry_remove( i, why );
}

/* It moved -- dragged, or teleported -- and is still whole. */
void corpse_registry_moved( OBJ_DATA *corpse )
{
    int i = corpse_registry_find( corpse );

    if ( i >= 0 && corpse->in_room != NULL
    &&   corpse_registry[i].room != corpse->in_room->vnum )
    {
        corpse_registry[i].room = corpse->in_room->vnum;
        corpse_registry_write();
    }
}

/* A restore gave the player their things back from a snapshot: none of
   their corpses may be made again at the next boot. */
void corpse_registry_forget_player( const char *name )
{
    int i;

    for ( i = corpse_registry_count - 1; i >= 0; i-- )
        if ( !str_cmp( corpse_registry[i].owner, name ) )
            corpse_registry_remove( i, "the player was restored" );
}

/* Whether a player has a corpse on the list -- in the world this boot. */
bool corpse_registry_has( const char *name )
{
    int i;

    for ( i = 0; i < corpse_registry_count; i++ )
        if ( !str_cmp( corpse_registry[i].owner, name ) )
            return true;
    return false;
}


/* Make one corpse again, in its room, from its snapshot. */
static OBJ_DATA *corpse_rebuild( CORPSE_ENTRY *e, char *why, size_t why_size )
{
    DESCRIPTOR_DATA offline_desc;
    CHAR_DATA *vessel;
    ROOM_INDEX_DATA *room;
    OBJ_INDEX_DATA *pCorpse = get_obj_index( OBJ_VNUM_CORPSE_PC );
    OBJ_DATA *corpse, *list = NULL, *obj;
    char path[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH];
    long ticks;
    int read;

    if ( pCorpse == NULL )
    {
        snprintf( why, why_size, "there is no corpse object" );
        return NULL;
    }
    if ( ( room = get_room_index( e->room ) ) == NULL
    &&   ( room = get_room_index( ROOM_VNUM_ALTAR ) ) == NULL )
    {
        snprintf( why, why_size, "room %d is gone", e->room );
        return NULL;
    }
    snprintf( path, sizeof(path), "%s%s/%s", PLAYER_VER_DIR,
              capitalize( e->owner ), e->snapshot );
    /* fread_obj reads through a character; their own file, loaded aside,
       carries the version and the stash slot it reads into. */
    if ( ( vessel = offline_player_load( &offline_desc, e->owner, NULL ) ) == NULL )
    {
        snprintf( why, why_size, "the player file is gone" );
        return NULL;
    }
    read = snapshot_read_gear( vessel, path, why, why_size, &list );
    extract_char( vessel, true );
    if ( read < 0 )
        return NULL;

    corpse = create_object( pCorpse, 0 );
    snprintf( buf, sizeof(buf), "%s corpse", e->owner );
    free_string( corpse->name );
    corpse->name = str_dup( buf );
    snprintf( buf, sizeof(buf), corpse->short_descr, e->owner );
    free_string( corpse->short_descr );
    corpse->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), corpse->description, e->owner );
    free_string( corpse->description );
    corpse->description = str_dup( buf );
    corpse->owner = e->owned ? str_dup( e->owner ) : NULL;
    corpse->level = (sh_int) e->level;
    corpse->cost = 0;
    /* What is left of its days, counted in minutes as ticks nearly are. */
    ticks = PC_CORPSE_TICKS - ( (long) current_time - e->died ) / 60;
    corpse->timer = (sh_int) URANGE( 60, ticks, PC_CORPSE_TICKS );

    /* As make_corpse treats them: what goes off at a death goes, a key
       crumbles in time. */
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
        if ( obj->item_type == ITEM_KEY && !IS_HYRULE_BOSS_KEY(obj->pIndexData->vnum) )
            obj->timer = (sh_int) number_range( 40, 80 );
        REMOVE_BIT( obj->extra_flags, ITEM_VIS_DEATH );
        obj_to_obj( obj, corpse );
    }
    obj_to_room( corpse, room );
    return corpse;
}

/* At boot, after the world: every corpse still on the list, made again. */
void corpse_registry_boot( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char why[MAX_INPUT_LENGTH];
    int i;

    corpse_registry_count = 0;
    if ( ( fp = fopen( CORPSE_REGISTRY, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL
         && corpse_registry_count < CORPSE_REGISTRY_MAX )
    {
        CORPSE_ENTRY *e = &corpse_registry[corpse_registry_count];
        int owned = 1;

        memset( e, 0, sizeof(*e) );
        if ( sscanf( line, "%15s %95s %d %ld %d %d", e->owner, e->snapshot,
                     &e->room, &e->died, &e->level, &owned ) < 5 )
            continue;
        e->owned = owned != 0;
        corpse_registry_count++;
    }
    fclose( fp );

    corpse_registry_rebuilding = true;
    for ( i = corpse_registry_count - 1; i >= 0; i-- )
    {
        CORPSE_ENTRY *e = &corpse_registry[i];

        if ( (long) current_time - e->died > PC_CORPSE_TICKS * 60L
        ||   ( e->corpse = corpse_rebuild( e, why, sizeof(why) ) ) == NULL )
        {
            if ( (long) current_time - e->died > PC_CORPSE_TICKS * 60L )
                toc_strlcpy( why, "it would have rotted by now", sizeof(why) );
            snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse was not made again: %s.",
                      e->owner, why );
            log_string( buf );
            corpse_registry[i] = corpse_registry[--corpse_registry_count];
            continue;
        }
        snprintf( buf, sizeof(buf), "Corpse keeper: %s's corpse made again in room %d "
                  "from %s.", e->owner, e->room, e->snapshot );
        log_string( buf );
    }
    corpse_registry_rebuilding = false;
    corpse_registry_write();
}
