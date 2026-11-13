/*
 * Exploration maps (owner, 2026-11-12): "the mudlet starter map should
 * only display rooms you have been to unless you get the area map item,
 * excluding dresden and starting areas."
 *
 * The game is the truth about what a character knows of the world, and
 * the client only draws it. A room is known to a character when
 *
 *   - its area is always known (map_always_known_files: Dresden, where
 *     everybody starts, Mud School, Limbo and the training yard), or
 *   - they have walked into it (the achievements' "rooms" set, which
 *     every move already keeps), or
 *   - they hold the whole map of its region: an area's map, or a Hyrule
 *     dungeon's (the NES dungeon map -- achievement_hyrule_maps, which
 *     the map object has always set -- or a GRANTMAP of that dungeon).
 *
 * Staff know everything. A map region is an area, except that each of
 * Hyrule's nine dungeons is a region of its own and an area map of
 * Hyrule shows the overworld.
 *
 * The client hears it as GMCP Map.Known (gmcp_send_map_known): the known
 * rooms as vnum ranges, in parts that each fit one GMCP message, sent at
 * the first prompt of a connection and again whenever a map is learned.
 * A room walked into after that is known from its Room.Info.
 *
 * Maps come from three places: a map item (one prototype, OBJ_VNUM_AREA_MAP,
 * whose value[1] names a room of the area it shows) that READ teaches and
 * uses up; now and then a slain mobile's corpse (map_corpse_drop); and
 * the wandering cartographer, who drops the map of wherever he falls.
 * Staff GRANTMAP gives one, or all of them.
 *
 * An area is "explored" when every room of it that counts has been
 * walked into (map_room_countable): the exploration achievements count
 * those, in the set "explored-areas".
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include "merc.h"

/* value[2] of an area map found on a fallen foe (Treasure Map). */
#define MAP_FOUND_ON_FOE 1
#include "interp.h"
#include "telnet_proto.h"
#include "dstring.h"

extern AREA_DATA *area_first;
extern char * const dir_name[];

/* Areas everybody knows from the start: the city with the start room, the
   school a new character starts in, Limbo and the yard reached from the
   city. Named once, here. */
static const char *const map_always_known_files[] =
{
    "dresden.are", "school.are", "limbo.are", "dummy.are", NULL
};

#define MAP_HYRULE_FILE         "hyrule.are"
/* An area walked end to end counts toward the exploration achievements
   only when it has at least this many rooms that count: walking into the
   one room of the training yard is not exploring it. */
#define MAP_EXPLORE_MIN_ROOMS   10
#define MAP_HYRULE_LEVELS       9

/* A slain mobile's corpse holds its area's map one time in this many
   thousand (owner: "map items drop"; rare). */
#define MAP_DROP_PER_MILLE      5

/* Map.Known: the room ranges of one part fit one GMCP message (telnet's
   buffer is MAX_TELNET_SUBNEG with the package name and framing). */
#define MAP_KNOWN_PART_BYTES    1600

/* ------------------------------------------------------------------
 * Which rooms count, area by area
 * ------------------------------------------------------------------ */

typedef struct map_area_info
{
    AREA_DATA * area;
    long        id;
    int *       rooms;          /* countable room vnums, ascending */
    int         count;
    int         cap;
} MAP_AREA_INFO;

static MAP_AREA_INFO *map_info = NULL;
static int map_info_count = 0;
static int map_info_built_rooms = -1;
static int map_info_built_top = -1;

bool map_area_always_known( const AREA_DATA *area )
{
    int i;

    if ( area == NULL || area->file_name == NULL )
        return false;
    for ( i = 0; map_always_known_files[i] != NULL; i++ )
        if ( !str_cmp( area->file_name, map_always_known_files[i] ) )
            return true;
    return false;
}

static bool map_is_hyrule( const AREA_DATA *area )
{
    return area != NULL && area->file_name != NULL
        && !str_cmp( area->file_name, MAP_HYRULE_FILE );
}

/* Which Hyrule dungeon a room is in, 1 to 9, or 0. */
static int map_hyrule_level( const ROOM_INDEX_DATA *room )
{
    int level;

    if ( room == NULL || !map_is_hyrule( room->area ) )
        return 0;
    for ( level = 1; level <= MAP_HYRULE_LEVELS; level++ )
    {
        const HYRULE_DUNGEON_GATE *gate = hyrule_dungeon_gate( level );

        if ( gate != NULL && room->vnum >= gate->first_room
        &&   room->vnum <= gate->last_room )
            return level;
    }
    return 0;
}

/* A dungeon's region: a stable 31-bit number, as an area's is. */
static long map_dungeon_id( int level )
{
    char key[64];
    unsigned long hash = 2166136261UL;
    const char *p;

    snprintf( key, sizeof(key), "%s#dungeon-%d", MAP_HYRULE_FILE, level );
    for ( p = key; *p != '\0'; p++ )
    {
        hash ^= (unsigned char)*p;
        hash = ( hash * 16777619UL ) & 0xFFFFFFFFUL;
    }
    return (long)( hash & 0x7FFFFFFFUL );
}

long map_region_id( const ROOM_INDEX_DATA *room )
{
    int level;

    if ( room == NULL )
        return -1;
    if ( ( level = map_hyrule_level( room ) ) > 0 )
        return map_dungeon_id( level );
    return achievement_area_id( room->area );
}

/*
 * A room that counts toward walking an area end to end: one the
 * exploration achievements already count (achievement_room_counts: the
 * shipped world, no staff room, jail or Limbo), and one anybody can walk
 * into -- not a death trap, not a newbie's or a hero's room, not inside a
 * guild hall, and with an exit from some other room leading in.
 */
static bool map_room_countable( ROOM_INDEX_DATA *room, const unsigned char *entered,
                                const unsigned char *hall )
{
    if ( room == NULL || room->vnum < 0 || room->vnum > map_info_built_top
    ||   !achievement_room_counts( room ) )
        return false;
    if ( IS_SET( room->room_flags, ROOM_DT )
    ||   IS_SET( room->room_flags, ROOM_NEWBIES_ONLY )
    ||   IS_SET( room->room_flags, ROOM_HEROES_ONLY ) )
        return false;
    return entered[room->vnum] != 0 && hall[room->vnum] == 0;
}

static void map_info_free( void )
{
    int i;

    for ( i = 0; i < map_info_count; i++ )
        free( map_info[i].rooms );
    free( map_info );
    map_info = NULL;
    map_info_count = 0;
}

static MAP_AREA_INFO *map_info_slot( const AREA_DATA *area )
{
    int i;

    for ( i = 0; i < map_info_count; i++ )
        if ( map_info[i].area == area )
            return &map_info[i];
    return NULL;
}

/* Built at first use and again whenever rooms are made or unmade. */
static void map_info_build( void )
{
    AREA_DATA *area;
    ROOM_INDEX_DATA *hall_rooms[512];
    unsigned char *entered;
    unsigned char *hall;
    int areas = 0;
    int vnum;
    int i;
    int halls;

    if ( map_info != NULL && map_info_built_rooms == top_room
    &&   map_info_built_top == top_vnum_room )
        return;
    map_info_free( );
    map_info_built_rooms = top_room;
    map_info_built_top = top_vnum_room;

    for ( area = area_first; area != NULL; area = area->next )
        areas++;
    map_info = calloc( (size_t) UMAX( 1, areas ), sizeof(MAP_AREA_INFO) );
    entered = calloc( (size_t) top_vnum_room + 1, 1 );
    hall = calloc( (size_t) top_vnum_room + 1, 1 );
    if ( map_info == NULL || entered == NULL || hall == NULL )
    {
        bug( "map_info_build: out of memory.", 0 );
        free( entered );
        free( hall );
        free( map_info );
        map_info = NULL;
        return;
    }
    for ( area = area_first; area != NULL; area = area->next )
    {
        map_info[map_info_count].area = area;
        map_info[map_info_count].id = achievement_area_id( area );
        map_info_count++;
    }

    /* Every room some other room's exit leads into. */
    for ( vnum = 0; vnum <= top_vnum_room; vnum++ )
    {
        ROOM_INDEX_DATA *room = get_room_index( vnum );
        int door;

        if ( room == NULL )
            continue;
        for ( door = 0; door < 10; door++ )
        {
            EXIT_DATA *pexit = room->exit[door];

            if ( pexit != NULL && pexit->u1.to_room != NULL
            &&   pexit->u1.to_room != room
            &&   pexit->u1.to_room->vnum >= 0
            &&   pexit->u1.to_room->vnum <= top_vnum_room )
                entered[pexit->u1.to_room->vnum] = 1;
        }
    }
    halls = guild_hall_rooms( hall_rooms, (int)( sizeof(hall_rooms) / sizeof(hall_rooms[0]) ) );
    for ( i = 0; i < halls; i++ )
        if ( hall_rooms[i] != NULL && hall_rooms[i]->vnum >= 0
        &&   hall_rooms[i]->vnum <= top_vnum_room )
            hall[hall_rooms[i]->vnum] = 1;

    for ( vnum = 0; vnum <= top_vnum_room; vnum++ )
    {
        ROOM_INDEX_DATA *room = get_room_index( vnum );
        MAP_AREA_INFO *info;

        if ( room == NULL || !map_room_countable( room, entered, hall )
        ||   ( info = map_info_slot( room->area ) ) == NULL )
            continue;
        if ( info->count >= info->cap )
        {
            int cap = info->cap < 16 ? 16 : info->cap * 2;
            int *grown = realloc( info->rooms, (size_t) cap * sizeof(int) );

            if ( grown == NULL )
                continue;
            info->rooms = grown;
            info->cap = cap;
        }
        info->rooms[info->count++] = vnum;
    }
    free( entered );
    free( hall );
}

static MAP_AREA_INFO *map_info_for( const AREA_DATA *area )
{
    map_info_build( );
    return area == NULL ? NULL : map_info_slot( area );
}

/* An area a map can be made of: rooms that count, and not one everybody
   knows already. */
bool map_area_mappable( const AREA_DATA *area )
{
    MAP_AREA_INFO *info = map_info_for( area );

    return info != NULL && info->count > 0 && !map_area_always_known( area );
}

/* The room a map of the area names: its first room that counts. */
static ROOM_INDEX_DATA *map_area_anchor( const AREA_DATA *area )
{
    MAP_AREA_INFO *info = map_info_for( area );

    if ( info == NULL || info->count <= 0 )
        return NULL;
    return get_room_index( info->rooms[0] );
}

static int map_area_walked( CHAR_DATA *ch, const MAP_AREA_INFO *info )
{
    int walked = 0;
    int i;

    for ( i = 0; i < info->count; i++ )
        if ( achievement_set_has( ch, ACH_SET_ROOMS, info->rooms[i] ) )
            walked++;
    return walked;
}

bool map_area_fully_explored( CHAR_DATA *ch, const AREA_DATA *area )
{
    MAP_AREA_INFO *info = map_info_for( area );
    int i;

    if ( ch == NULL || IS_NPC(ch) || info == NULL
    ||   info->count < MAP_EXPLORE_MIN_ROOMS )
        return false;
    for ( i = 0; i < info->count; i++ )
        if ( !achievement_set_has( ch, ACH_SET_ROOMS, info->rooms[i] ) )
            return false;
    return true;
}

/* "Camelot", or "Hyrule: Level 3" for a dungeon. */
static void map_region_title( const ROOM_INDEX_DATA *room, char *out, size_t size )
{
    int level = map_hyrule_level( room );

    if ( level > 0 )
    {
        snprintf( out, size, "Hyrule: Level %d", level );
        return;
    }
    quest_area_name( room != NULL && room->area != NULL ? room->area->name : NULL,
                     out, size );
}

/* ------------------------------------------------------------------
 * What a character knows
 * ------------------------------------------------------------------ */

static bool map_region_held( const CHAR_DATA *ch, const ROOM_INDEX_DATA *room )
{
    int level = map_hyrule_level( room );

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return false;
    if ( level > 0
    &&   ( ch->pcdata->achievement_hyrule_maps & ( 1UL << ( level - 1 ) ) ) != 0 )
        return true;
    return achievement_set_has( ch, ACH_SET_MAP_AREAS, map_region_id( room ) );
}

/* Whose map shows every room: an immortal by level, never by trust
   (owner, 2026-11-12: "trusted players shouldn't get all maps, only
   actual level immortals"). A mortal given staff trust to build or help
   explores like anyone. One of the deliberate level, not trust, tests
   (AGENTS.md, Permission Helpers). */
static bool map_sees_all( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->level >= LEVEL_IMMORTAL;
}

bool map_room_known( CHAR_DATA *ch, ROOM_INDEX_DATA *room )
{
    if ( ch == NULL || room == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return false;
    if ( map_sees_all( ch ) )
        return true;
    if ( map_area_always_known( room->area ) )
        return true;
    if ( achievement_set_has( ch, ACH_SET_ROOMS, room->vnum ) )
        return true;
    return map_region_held( ch, room );
}

/* Whole maps held: the regions learned, and every Hyrule dungeon whose
   NES map they have had that was not also granted. */
long map_held_count( const CHAR_DATA *ch )
{
    long held;
    int level;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return 0;
    held = achievement_set_size( ch, ACH_SET_MAP_AREAS );
    for ( level = 1; level <= MAP_HYRULE_LEVELS; level++ )
        if ( ( ch->pcdata->achievement_hyrule_maps & ( 1UL << ( level - 1 ) ) ) != 0
        &&   !achievement_set_has( ch, ACH_SET_MAP_AREAS, map_dungeon_id( level ) ) )
            held++;
    return held;
}

/* The client's Map.Known is out of date: send it again at the next prompt. */
void map_known_changed( CHAR_DATA *ch )
{
    DESCRIPTOR_DATA *d;

    if ( ch == NULL )
        return;
    for ( d = descriptor_list; d != NULL; d = d->next )
        if ( d->character == ch || d->original == ch )
            d->gmcp_map_known_sent = false;
}

/* Learns the whole map of the anchor's region. True when it was new. */
bool map_grant_region( CHAR_DATA *ch, ROOM_INDEX_DATA *anchor, bool announce )
{
    long id;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || anchor == NULL
    ||   map_region_held( ch, anchor ) )
        return false;
    if ( ( id = map_region_id( anchor ) ) < 0
    ||   !achievement_note( ch, ACH_SET_MAP_AREAS, id ) )
        return false;
    achievement_check_state( ch, announce );
    map_known_changed( ch );
    return true;
}

static bool map_playing( const CHAR_DATA *ch )
{
    return ch != NULL && ch->desc != NULL && ch->desc->connected == CON_PLAYING;
}

/* achievement_record_room_visit, for a room walked into the first time:
   the last room of an area that counts. */
void map_room_visited( CHAR_DATA *ch, ROOM_INDEX_DATA *room )
{
    char title[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    long id;

    if ( ch == NULL || IS_NPC(ch) || room == NULL || room->area == NULL )
        return;
    id = achievement_area_id( room->area );
    if ( achievement_set_has( ch, ACH_SET_EXPLORED_AREAS, id )
    ||   !map_area_fully_explored( ch, room->area ) )
        return;
    if ( !achievement_note( ch, ACH_SET_EXPLORED_AREAS, id ) || !map_playing( ch ) )
        return;
    quest_area_name( room->area->name, title, sizeof(title) );
    snprintf( buf, sizeof(buf),
              "{0E[explored]{00 You have walked into every corner of %s.\n\r", title );
    send_to_char( buf, ch );
}

/* At login, once in their room: an area walked end to end before the
   exploration achievements existed is counted from the rooms the file
   already proves they walked. */
void map_login( CHAR_DATA *ch )
{
    int i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL
    ||   is_staff( ch ) )
        return;
    map_info_build( );
    for ( i = 0; i < map_info_count; i++ )
        if ( map_info[i].count >= MAP_EXPLORE_MIN_ROOMS
        &&   !achievement_set_has( ch, ACH_SET_EXPLORED_AREAS, map_info[i].id )
        &&   map_area_walked( ch, &map_info[i] ) == map_info[i].count )
            achievement_note( ch, ACH_SET_EXPLORED_AREAS, map_info[i].id );
}

/* ------------------------------------------------------------------
 * GMCP Map.Known
 * ------------------------------------------------------------------ */

typedef struct map_run
{
    int first;
    int last;
} MAP_RUN;

/*
 * Map.Known {"part":1,"parts":2,"all":false,"rooms":[[3700,3722],...]}
 *
 * Every room the character knows, as runs of vnums: a run holds known
 * rooms only, and vnums no room has are skipped over, so a run never
 * covers an existing room they do not know. Parts arrive in order and
 * the client acts on the last; "all" is true for staff, who know every
 * room, and then no ranges are sent.
 */
void gmcp_send_map_known( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    MAP_RUN *runs = NULL;
    int count = 0;
    int cap = 0;
    int vnum;
    int parts;
    int part;
    int index;
    bool open = false;
    char json[MAX_TELNET_SUBNEG];
    char item[64];

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING
    ||   d->gmcp_map_known_sent )
        return;
    ch = d->original != NULL ? d->original : d->character;
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    d->gmcp_map_known_sent = true;

    if ( map_sees_all( ch ) )
    {
        telnet_send_gmcp( d, "Map.Known",
                          "{\"part\":1,\"parts\":1,\"all\":true,\"rooms\":[]}" );
        return;
    }

    for ( vnum = 0; vnum <= top_vnum_room; vnum++ )
    {
        ROOM_INDEX_DATA *room = get_room_index( vnum );

        if ( room == NULL )
            continue;
        if ( !map_room_known( ch, room ) )
        {
            open = false;
            continue;
        }
        if ( open )
        {
            runs[count - 1].last = vnum;
            continue;
        }
        if ( count >= cap )
        {
            int grown_cap = cap < 64 ? 64 : cap * 2;
            MAP_RUN *grown = realloc( runs, (size_t) grown_cap * sizeof(MAP_RUN) );

            if ( grown == NULL )
                break;
            runs = grown;
            cap = grown_cap;
        }
        runs[count].first = vnum;
        runs[count].last = vnum;
        count++;
        open = true;
    }

    /* How many parts, then each. */
    parts = 1;
    {
        size_t used = 0;

        for ( index = 0; index < count; index++ )
        {
            size_t len = (size_t) snprintf( item, sizeof(item), "[%d,%d],",
                                            runs[index].first, runs[index].last );

            if ( used > 0 && used + len > MAP_KNOWN_PART_BYTES )
            {
                parts++;
                used = 0;
            }
            used += len;
        }
    }

    index = 0;
    for ( part = 1; part <= parts; part++ )
    {
        size_t used = 0;
        bool first = true;

        snprintf( json, sizeof(json), "{\"part\":%d,\"parts\":%d,\"all\":false,\"rooms\":[",
                  part, parts );
        while ( index < count )
        {
            size_t len = (size_t) snprintf( item, sizeof(item), "%s[%d,%d]",
                                            first ? "" : ",",
                                            runs[index].first, runs[index].last );

            if ( used > 0 && used + len > MAP_KNOWN_PART_BYTES )
                break;
            toc_strlcat( json, item, sizeof(json) );
            used += len;
            first = false;
            index++;
        }
        toc_strlcat( json, "]}", sizeof(json) );
        telnet_send_gmcp( d, "Map.Known", json );
    }
    free( runs );
}

/* ------------------------------------------------------------------
 * The map item
 * ------------------------------------------------------------------ */

/* A map of the anchor's region, or NULL. */
OBJ_DATA *map_item_create( ROOM_INDEX_DATA *anchor )
{
    OBJ_INDEX_DATA *proto;
    OBJ_DATA *obj;
    char title[MAX_INPUT_LENGTH];
    char words[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    size_t at = 0;
    const char *p;

    if ( anchor == NULL || anchor->area == NULL )
        return NULL;
    if ( ( proto = get_obj_index( OBJ_VNUM_AREA_MAP ) ) == NULL )
    {
        bug( "map_item_create: object %d is missing.", OBJ_VNUM_AREA_MAP );
        return NULL;
    }
    obj = create_object( proto, 0 );
    obj->value[0] = MAP_ITEM_AREA;
    obj->value[1] = anchor->vnum;
    map_region_title( anchor, title, sizeof(title) );

    /* Keywords: map, parchment and the region's words, lower case. */
    for ( p = title; *p != '\0' && at + 1 < sizeof(words); p++ )
    {
        if ( isalnum( (unsigned char) *p ) )
            words[at++] = (char) LOWER( *p );
        else if ( at > 0 && words[at - 1] != ' ' )
            words[at++] = ' ';
    }
    words[at] = '\0';
    snprintf( buf, sizeof(buf), "map parchment %s", words );
    free_string( obj->name );
    obj->name = str_dup( buf );
    snprintf( buf, sizeof(buf), "a map of %s", title );
    free_string( obj->short_descr );
    obj->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), "A rolled map of %s lies here.", title );
    free_string( obj->description );
    obj->description = str_dup( buf );
    return obj;
}

/* READ <map>: learn it, and the parchment is used up. True when the
   object read was an area map, whatever came of it. */
bool map_item_read( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char title[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *obj;
    ROOM_INDEX_DATA *anchor;

    if ( ch == NULL || argument == NULL )
        return false;
    one_argument( argument, arg );
    if ( arg[0] == '\0' || ( obj = get_obj_carry( ch, arg ) ) == NULL
    ||   obj->item_type != ITEM_MAP || obj->value[0] != MAP_ITEM_AREA )
        return false;

    anchor = get_room_index( obj->value[1] );
    if ( anchor == NULL || anchor->area == NULL )
    {
        send_to_char( "The ink has run; nothing on this map can be made out.\n\r", ch );
        return true;
    }
    if ( IS_NPC(ch) )
    {
        send_to_char( "You cannot make sense of it.\n\r", ch );
        return true;
    }
    map_region_title( anchor, title, sizeof(title) );
    /* Hindsight: the map of an area already walked end to end. */
    if ( achievement_set_has( ch, ACH_SET_EXPLORED_AREAS,
                              achievement_area_id( anchor->area ) ) )
        achievement_record_event( ch, ACHIEVEMENT_EVENT_MAP_TOO_LATE, true );
    if ( map_region_held( ch, anchor ) || map_area_always_known( anchor->area ) )
    {
        snprintf( buf, sizeof(buf), "You already know every path of %s; this map "
                  "has nothing new for you.\n\r", title );
        send_to_char( buf, ch );
        return true;
    }
    if ( !map_grant_region( ch, anchor, true ) )
    {
        send_to_char( "You cannot take in any more maps.\n\r", ch );
        return true;
    }
    act( "$n pores over $p, tracing its paths with a finger.", ch, obj, NULL, TO_ROOM );
    snprintf( buf, sizeof(buf), "You study the map of %s until every path is fixed in "
              "your memory.\n\rThe old parchment crumbles to dust in your hands.\n\r", title );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf), "%s learned the map of %s.", ch->name, title );
    log_string( buf );
    if ( obj->value[2] == MAP_FOUND_ON_FOE )
        achievement_record_event( ch, ACHIEVEMENT_EVENT_MAP_FROM_FOE, true );
    extract_obj( obj );
    save_char_obj( ch );
    return true;
}

/* make_corpse: now and then, the map of the area a mobile fell in. Not in
   Hyrule, whose dungeons have maps of their own, and never for somebody's
   pet or servant. */
void map_corpse_drop( OBJ_DATA *corpse, CHAR_DATA *victim )
{
    const char *always = getenv( "TOC_MAP_DROPS" );    /* tests only */
    ROOM_INDEX_DATA *anchor;
    OBJ_DATA *map;
    AREA_DATA *area;

    if ( corpse == NULL || victim == NULL || !IS_NPC(victim)
    ||   victim->in_room == NULL || is_cartographer( victim )
    ||   IS_AFFECTED( victim, AFF_CHARM ) || IS_SET( victim->act, ACT_PET ) )
        return;
    area = victim->in_room->area;
    if ( map_is_hyrule( area ) || !map_area_mappable( area ) )
        return;
    if ( !( always != NULL && !str_cmp( always, "always" ) )
    &&   number_range( 1, 1000 ) > MAP_DROP_PER_MILLE )
        return;
    if ( ( anchor = map_area_anchor( area ) ) == NULL
    ||   ( map = map_item_create( anchor ) ) == NULL )
        return;
    map->value[2] = MAP_FOUND_ON_FOE;       /* Treasure Map, when it is read */
    obj_to_obj( map, corpse );
}

/* ------------------------------------------------------------------
 * MAPS
 * ------------------------------------------------------------------ */

static int map_info_by_title( const void *a, const void *b )
{
    const MAP_AREA_INFO *x = (const MAP_AREA_INFO *) a;
    const MAP_AREA_INFO *y = (const MAP_AREA_INFO *) b;
    char tx[MAX_INPUT_LENGTH];
    char ty[MAX_INPUT_LENGTH];

    const char *a_at = tx;
    const char *b_at = ty;

    quest_area_name( x->area->name, tx, sizeof(tx) );
    quest_area_name( y->area->name, ty, sizeof(ty) );
    while ( *a_at != '\0' && LOWER( *a_at ) == LOWER( *b_at ) )
    {
        a_at++;
        b_at++;
    }
    return (int)(unsigned char) LOWER( *a_at ) - (int)(unsigned char) LOWER( *b_at );
}

void do_maps( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char title[MAX_INPUT_LENGTH];
    MAP_AREA_INFO *sorted;
    DString out;
    bool everything;
    int explored = 0;
    int listed = 0;
    int level;
    int i;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players keep maps.\n\r", ch );
        return;
    }
    one_argument( argument, arg );
    everything = arg[0] != '\0' && !str_prefix( arg, "all" );
    map_info_build( );
    if ( map_info_count <= 0 )
    {
        send_to_char( "The world has no maps to keep.\n\r", ch );
        return;
    }
    sorted = calloc( (size_t) map_info_count, sizeof(MAP_AREA_INFO) );
    if ( sorted == NULL )
    {
        send_to_char( "Your maps cannot be counted just now.\n\r", ch );
        return;
    }
    memcpy( sorted, map_info, (size_t) map_info_count * sizeof(MAP_AREA_INFO) );
    qsort( sorted, (size_t) map_info_count, sizeof(MAP_AREA_INFO), map_info_by_title );

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &out, "Your maps (HELP MAPS):\n\r\n\r  Always known: " );
    {
        bool first = true;

        for ( i = 0; i < map_info_count; i++ )
            if ( map_area_always_known( sorted[i].area ) )
            {
                quest_area_name( sorted[i].area->name, title, sizeof(title) );
                dstring_printf( &out, "%s%s", first ? "" : ", ", title );
                first = false;
            }
        dstring_append_cstr( &out, "\n\r" );
    }
    if ( map_sees_all( ch ) )
        dstring_append_cstr( &out, "  You are an immortal: your map shows every room.\n\r" );

    dstring_printf( &out, "\n\r  %-34s %-6s %s\n\r", "Area", "Map", "Walked" );
    for ( i = 0; i < map_info_count; i++ )
    {
        MAP_AREA_INFO *info = &sorted[i];
        ROOM_INDEX_DATA *anchor;
        bool held;
        int walked;

        bool always;

        if ( info->count <= 0 )
            continue;
        always = map_area_always_known( info->area );
        anchor = get_room_index( info->rooms[0] );
        held = always || ( anchor != NULL && map_region_held( ch, anchor ) );
        walked = map_area_walked( ch, info );
        if ( walked == info->count && info->count >= MAP_EXPLORE_MIN_ROOMS )
            explored++;
        if ( !everything && ( always || !held ) && walked == 0 )
            continue;
        quest_area_name( info->area->name, title, sizeof(title) );
        if ( !dstring_fits( &out, 200 ) )
            break;
        dstring_printf( &out, "  %-34.34s %-6s %d/%d%s\n\r", title,
                        always ? "always" : held ? "held" : "-", walked, info->count,
                        walked == info->count && info->count >= MAP_EXPLORE_MIN_ROOMS
                            ? "  explored" : "" );
        listed++;
    }
    if ( listed == 0 )
        dstring_append_cstr( &out, "  Nothing yet: walk somewhere new, or find a map.\n\r" );

    {
        int dungeons = 0;

        for ( level = 1; level <= MAP_HYRULE_LEVELS; level++ )
            if ( ( ch->pcdata->achievement_hyrule_maps & ( 1UL << ( level - 1 ) ) ) != 0
            ||   achievement_set_has( ch, ACH_SET_MAP_AREAS, map_dungeon_id( level ) ) )
            {
                if ( dungeons++ == 0 )
                    dstring_append_cstr( &out, "\n\r  Hyrule dungeon maps:" );
                dstring_printf( &out, " %d", level );
            }
        if ( dungeons > 0 )
            dstring_append_cstr( &out, "\n\r" );
    }
    dstring_printf( &out, "\n\r  Whole maps held: %ld.  Areas walked end to end: %d.\n\r",
                    map_held_count( ch ), explored );
    if ( !everything )
        dstring_append_cstr( &out, "  MAPS ALL lists every area.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
    free( sorted );
}

/* ------------------------------------------------------------------
 * GRANTMAP
 * ------------------------------------------------------------------ */

/* The region a staff word names: an area by file ("camelot",
   "camelot.are") or by the start of its name, or a Hyrule dungeon as
   hyrule1 to hyrule9. The region's anchor room, or NULL. */
static ROOM_INDEX_DATA *map_region_named( const char *word )
{
    char stem[MAX_INPUT_LENGTH];
    char title[MAX_INPUT_LENGTH];
    int i;

    if ( word == NULL || word[0] == '\0' )
        return NULL;
    if ( !str_prefix( "hyrule", word ) && strlen( word ) == 7
    &&   word[6] >= '1' && word[6] <= '9' )
    {
        const HYRULE_DUNGEON_GATE *gate = hyrule_dungeon_gate( word[6] - '0' );

        return gate != NULL ? get_room_index( gate->first_room ) : NULL;
    }
    map_info_build( );
    for ( i = 0; i < map_info_count; i++ )
    {
        const char *file = map_info[i].area->file_name;
        const char *dot;

        if ( map_info[i].count <= 0 || file == NULL )
            continue;
        toc_strlcpy( stem, file, sizeof(stem) );
        if ( ( dot = strrchr( stem, '.' ) ) != NULL )
            stem[dot - stem] = '\0';
        if ( !str_cmp( word, file ) || !str_cmp( word, stem ) )
            return get_room_index( map_info[i].rooms[0] );
    }
    for ( i = 0; i < map_info_count; i++ )
    {
        if ( map_info[i].count <= 0 )
            continue;
        quest_area_name( map_info[i].area->name, title, sizeof(title) );
        if ( !str_prefix( word, title ) )
            return get_room_index( map_info[i].rooms[0] );
    }
    return NULL;
}

static void map_grantmap_list( CHAR_DATA *ch )
{
    char title[MAX_INPUT_LENGTH];
    char stem[MAX_INPUT_LENGTH];
    DString out;
    int i;

    map_info_build( );
    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &out, "Maps GRANTMAP can give (the word, then the area):\n\r" );
    for ( i = 0; i < map_info_count; i++ )
    {
        const char *dot;

        if ( !map_area_mappable( map_info[i].area ) || map_info[i].area->file_name == NULL )
            continue;
        toc_strlcpy( stem, map_info[i].area->file_name, sizeof(stem) );
        if ( ( dot = strrchr( stem, '.' ) ) != NULL )
            stem[dot - stem] = '\0';
        quest_area_name( map_info[i].area->name, title, sizeof(title) );
        if ( !dstring_fits( &out, 200 ) )
            break;
        dstring_printf( &out, "  %-14s %s (%d rooms)\n\r", stem, title, map_info[i].count );
    }
    dstring_append_cstr( &out, "  hyrule1 .. hyrule9  Hyrule's dungeons, Level 1 to 9\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}

/* Every map there is: each mappable area and each Hyrule dungeon. */
static int map_grant_everything( CHAR_DATA *victim )
{
    int granted = 0;
    int level;
    int i;

    map_info_build( );
    for ( i = 0; i < map_info_count; i++ )
        if ( map_area_mappable( map_info[i].area )
        &&   map_grant_region( victim, get_room_index( map_info[i].rooms[0] ), false ) )
            granted++;
    for ( level = 1; level <= MAP_HYRULE_LEVELS; level++ )
    {
        const HYRULE_DUNGEON_GATE *gate = hyrule_dungeon_gate( level );

        if ( gate != NULL
        &&   map_grant_region( victim, get_room_index( gate->first_room ), false ) )
            granted++;
    }
    achievement_check_state( victim, map_playing( victim ) );
    return granted;
}

/*
 * GRANTMAP ... REVOKE: the map of the anchor's region taken back. True when
 * it was held through the map-areas set (a grant, a map READ, the
 * cartographer's). A Hyrule dungeon's NES map found in play is the
 * achievements' record (AchMaps) and stays: *kept says so. Rooms walked
 * stay known whatever is revoked, and nothing earned is taken back.
 */
static bool map_revoke_region( CHAR_DATA *victim, ROOM_INDEX_DATA *anchor, bool *kept )
{
    int level = map_hyrule_level( anchor );
    bool taken;

    taken = achievement_set_remove( victim, ACH_SET_MAP_AREAS, map_region_id( anchor ) );
    *kept = level > 0
         && ( victim->pcdata->achievement_hyrule_maps & ( 1UL << ( level - 1 ) ) ) != 0;
    if ( taken )
        map_known_changed( victim );
    return taken;
}

/* Every map held through the set; how many. Dungeon maps found in play
   stay (*kept counts them). */
static int map_revoke_everything( CHAR_DATA *victim, int *kept )
{
    int taken = achievement_set_clear( victim, ACH_SET_MAP_AREAS );
    int level;

    *kept = 0;
    for ( level = 1; level <= MAP_HYRULE_LEVELS; level++ )
        if ( ( victim->pcdata->achievement_hyrule_maps & ( 1UL << ( level - 1 ) ) ) != 0 )
            ( *kept )++;
    if ( taken > 0 )
        map_known_changed( victim );
    return taken;
}

void do_grantmap( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char what[MAX_INPUT_LENGTH];
    char verb[MAX_INPUT_LENGTH];
    char title[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA offline_desc;
    CHAR_DATA *victim;
    ROOM_INDEX_DATA *anchor = NULL;
    bool offline = false;
    bool everything;
    bool revoke = false;
    bool logging_in = false;
    int granted;
    int kept = 0;
    int status;

    argument = one_argument( argument, arg );
    argument = one_argument( argument, what );
    argument = one_argument( argument, verb );
    if ( arg[0] != '\0' && !str_cmp( arg, "list" ) )
    {
        map_grantmap_list( ch );
        return;
    }
    if ( verb[0] != '\0' && !str_cmp( verb, "revoke" ) )
        revoke = true;
    if ( arg[0] == '\0' || what[0] == '\0'
    ||   ( verb[0] != '\0' && !revoke ) || argument[0] != '\0' )
    {
        send_to_char( "Syntax: grantmap <player> <area|hyrule1..hyrule9|all>\n\r"
                      "        grantmap <player> <area|hyrule1..hyrule9|all> revoke\n\r"
                      "        grantmap list\n\r", ch );
        return;
    }
    everything = !str_cmp( what, "all" );
    if ( !everything && ( anchor = map_region_named( what ) ) == NULL )
    {
        send_to_char( "No map by that name; GRANTMAP LIST names them.\n\r", ch );
        return;
    }
    if ( !everything && map_area_always_known( anchor->area ) )
    {
        send_to_char( revoke ? "Everybody knows that area; there is no map to take back.\n\r"
                             : "Everybody knows that area already.\n\r", ch );
        return;
    }

    victim = player_in_game( arg, &logging_in );
    if ( victim != NULL && logging_in )
    {
        send_to_char( "They are logging in; try again in a moment.\n\r", ch );
        return;
    }
    if ( victim == NULL )
    {
        if ( ( victim = offline_player_load( &offline_desc, arg, NULL ) ) == NULL )
        {
            send_to_char( "No player by that name is online or saved.\n\r", ch );
            return;
        }
        offline = true;
    }
    if ( IS_NPC(victim) || victim->pcdata == NULL )
    {
        send_to_char( "Not on NPCs.\n\r", ch );
        if ( offline )
            extract_char( victim, true );
        return;
    }
    if ( victim != ch && rank_protects( ch, victim ) )
    {
        send_to_char( "You failed.\n\r", ch );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    if ( revoke )
    {
        bool dungeon_kept = false;

        if ( everything )
        {
            granted = map_revoke_everything( victim, &kept );
            toc_strlcpy( title, "every map", sizeof(title) );
        }
        else
        {
            granted = map_revoke_region( victim, anchor, &dungeon_kept ) ? 1 : 0;
            kept = dungeon_kept ? 1 : 0;
            map_region_title( anchor, title, sizeof(title) );
        }
        if ( granted == 0 )
        {
            snprintf( buf, sizeof(buf), "%s holds no %s%s to take back%s.\n\r",
                      victim->name, everything ? "map" : "map of ",
                      everything ? "" : title,
                      kept > 0 ? " (a Hyrule map found in play is kept)" : "" );
            send_to_char( buf, ch );
            if ( offline )
                extract_char( victim, true );
            return;
        }
        save_char_obj( victim );
        status = save_char_obj_status( );
        if ( offline && status == DURABLE_FAILED )
        {
            send_to_char( "Their player file could not be saved, so nothing was taken.\n\r", ch );
            extract_char( victim, true );
            return;
        }
        if ( everything )
            snprintf( buf, sizeof(buf), "%s no longer holds any map (%d taken back).\n\r",
                      victim->name, granted );
        else
            snprintf( buf, sizeof(buf), "%s no longer holds the map of %s.\n\r",
                      victim->name, title );
        send_to_char( buf, ch );
        if ( kept > 0 )
        {
            snprintf( buf, sizeof(buf), "%d Hyrule dungeon map%s found in play %s kept: "
                      "REVOKE takes back only what is held as a map.\n\r",
                      kept, kept == 1 ? "" : "s", kept == 1 ? "is" : "are" );
            send_to_char( buf, ch );
        }
        send_to_char( "Rooms they have walked stay on their map.\n\r", ch );
        if ( status == DURABLE_UNCERTAIN )
            send_to_char( "Written to their player file, but the disk has not confirmed it.\n\r", ch );
        else if ( status == DURABLE_FAILED )
            send_to_char( "Their file could not be saved just now; their next save writes it.\n\r", ch );
        if ( !offline && map_playing( victim ) )
        {
            snprintf( buf, sizeof(buf), "{0E[map]{00 The gods take back %s%s; your map "
                      "keeps only the rooms you have walked there.\n\r",
                      everything ? "your maps" : "the map of ",
                      everything ? "" : title );
            send_to_char( buf, victim );
        }
        snprintf( buf, sizeof(buf), "%s revoked %s's %s%s (%d taken back)%s.", ch->name,
                  victim->name, everything ? "maps" : "map of ",
                  everything ? "" : title, granted, offline ? " while offline" : "" );
        log_string( buf );
        wizinfo( buf, staff_notice_level_pair( ch, victim, LEVEL_IMMORTAL ) );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    if ( everything )
    {
        granted = map_grant_everything( victim );
        toc_strlcpy( title, "every map", sizeof(title) );
    }
    else
    {
        granted = map_grant_region( victim, anchor, map_playing( victim ) ) ? 1 : 0;
        map_region_title( anchor, title, sizeof(title) );
    }
    if ( granted == 0 )
    {
        snprintf( buf, sizeof(buf), "%s already %s %s.\n\r", victim->name,
                  everything ? "holds" : "knows the map of", title );
        send_to_char( buf, ch );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    save_char_obj( victim );
    status = save_char_obj_status( );
    if ( offline && status == DURABLE_FAILED )
    {
        send_to_char( "Their player file could not be saved, so nothing was given.\n\r", ch );
        extract_char( victim, true );
        return;
    }
    snprintf( buf, sizeof(buf), "%s now %s %s (%d new).\n\r", victim->name,
              everything ? "holds" : "knows the map of", title, granted );
    send_to_char( buf, ch );
    if ( status == DURABLE_UNCERTAIN )
        send_to_char( "Written to their player file, but the disk has not confirmed it.\n\r", ch );
    else if ( status == DURABLE_FAILED )
        send_to_char( "Their file could not be saved just now; their next save writes it.\n\r", ch );
    if ( !offline && map_playing( victim ) )
    {
        snprintf( buf, sizeof(buf), "{0E[map]{00 The gods show you %s%s.\n\r",
                  everything ? "" : "the whole map of ", title );
        send_to_char( buf, victim );
    }
    snprintf( buf, sizeof(buf), "%s granted %s %s%s (%d new)%s.", ch->name,
              victim->name, everything ? "" : "the map of ", title, granted,
              offline ? " while offline" : "" );
    log_string( buf );
    wizinfo( buf, staff_notice_level_pair( ch, victim, LEVEL_IMMORTAL ) );
    if ( offline )
        extract_char( victim, true );
}

/* ------------------------------------------------------------------
 * The wandering cartographer
 *
 * Now and then -- a visit of twenty to forty minutes every few hours --
 * a cartographer turns up somewhere in an area that has a map, and walks
 * it a room at a time. He is hidden as the black market dealer is
 * (is_unfindable_mob): seen in his own room and nowhere else. He fights
 * back like anybody at the level of the area's monsters; slain, he drops
 * the whole map of the area he fell in. Where he stands is never written
 * to the public log: his arrival is logged without a room and staff see
 * it on WIZINFO.
 * ------------------------------------------------------------------ */

CHAR_DATA *cartographer = NULL;

static time_t cart_next_spawn = 0;
static time_t cart_leaves = 0;
static time_t cart_next_step = 0;
static AREA_DATA *cart_area = NULL;
static time_t cart_arrived = 0;     /* names the visit: A Man With a Map */

#define CART_FIRST_MIN      ( 30 * 60 )
#define CART_FIRST_MAX      ( 3 * 60 * 60 )
#define CART_VISIT_MIN      ( 20 * 60 )
#define CART_VISIT_MAX      ( 40 * 60 )
#define CART_AWAY_MIN       ( 2 * 60 * 60 )
#define CART_AWAY_MAX       ( 5 * 60 * 60 )
#define CART_OVERSTAY       ( 10 * 60 )     /* company keeps him this long past */
#define CART_STEP_MIN       30
#define CART_STEP_MAX       75

bool is_cartographer( const CHAR_DATA *ch )
{
    return ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
        && ch->pIndexData->vnum == MOB_VNUM_CARTOGRAPHER;
}

/* Where he walks: the dealer's rooms (black_market_room_ok), less a safe
   room, in an area a map can be made of and outside Hyrule. */
static bool cart_room_ok( ROOM_INDEX_DATA *room )
{
    return room != NULL && black_market_room_ok( room )
        && !IS_SET( room->room_flags, ROOM_SAFE )
        && !map_is_hyrule( room->area ) && map_area_mappable( room->area );
}

static void cart_where( ROOM_INDEX_DATA *room, char *out, size_t len )
{
    if ( room == NULL )
    {
        toc_strlcpy( out, "nowhere", len );
        return;
    }
    snprintf( out, len, "room %d (%s, %s)", room->vnum,
              room->name != NULL ? room->name : "?",
              room->area != NULL && room->area->file_name != NULL
                  ? room->area->file_name : "?" );
}

static bool cart_has_company( CHAR_DATA *cart )
{
    CHAR_DATA *rch;

    if ( cart->in_room == NULL )
        return false;
    for ( rch = cart->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( !IS_NPC(rch) && !is_staff( rch ) )
            return true;
    return false;
}

/* The level of the area's own monsters, near enough: the mean of the
   mobiles in it now, less pets, shopkeepers and staff toys. */
static int cart_level_for( AREA_DATA *area )
{
    LIST_ITERATOR iter;
    CHAR_DATA *vch;
    long total = 0;
    int count = 0;

    FOR_EACH_CHARACTER( iter, vch )
        if ( IS_NPC(vch) && vch->in_room != NULL && vch->in_room->area == area
        &&   !is_cartographer( vch ) && !is_unfindable_mob( vch )
        &&   !IS_SET( vch->act, ACT_PET ) && !IS_AFFECTED( vch, AFF_CHARM )
        &&   ( vch->pIndexData == NULL || vch->pIndexData->pShop == NULL )
        &&   vch->level < LEVEL_IMMORTAL )
        {
            total += vch->level;
            count++;
        }
    if ( count == 0 )
        return 10;
    return URANGE( 5, (int)( total / count ), 55 );
}

static void cart_scale( CHAR_DATA *cart, int level )
{
    long blow;
    int i;

    cart->level = (sh_int) level;
    cart->max_hit = (int) UMIN( (long) POOL_MAX, dummy_typical_hp( level ) );
    cart->hit = cart->max_hit;
    cart->hitroll = level / 3 + 2;
    cart->damroll = level / 5 + 1;
    blow = (long) level * 2 + 6;
    cart->damage[0] = (sh_int) UMAX( 1, blow / 6 );
    cart->damage[1] = 6;
    cart->damage[2] = (sh_int) UMAX( 0, blow / 3 );
    for ( i = 0; i < 4; i++ )
        cart->armor[i] = -level * 2;
}

bool cartographer_spawn( ROOM_INDEX_DATA *room )
{
    MOB_INDEX_DATA *proto;
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH + 64];

    if ( cartographer != NULL )
        return false;
    if ( ( proto = get_mob_index( MOB_VNUM_CARTOGRAPHER ) ) == NULL )
    {
        bug( "Cartographer: mobile %d is missing.", MOB_VNUM_CARTOGRAPHER );
        return false;
    }
    if ( room == NULL && ( room = random_room_where( cart_room_ok ) ) == NULL )
        return false;

    cartographer = create_mobile( proto );
    cart_scale( cartographer, cart_level_for( room->area ) );
    char_to_room( cartographer, room );
    act( "$n strides in, a folio of charts under one arm, and looks about with a "
         "keen, measuring eye.", cartographer, NULL, NULL, TO_ROOM );
    cart_area = room->area;
    cart_arrived = current_time;
    cart_leaves = current_time + number_range( CART_VISIT_MIN, CART_VISIT_MAX );
    cart_next_step = current_time + number_range( CART_STEP_MIN, CART_STEP_MAX );

    /* Not where: log/ is published every five minutes. */
    log_string( "Cartographer: appeared." );
    cart_where( room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Cartographer: appeared in %s (level %d).", where,
              cartographer->level );
    wizinfo( line, LEVEL_IMMORTAL );
    return true;
}

static void cartographer_depart( const char *why )
{
    char from[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH + 128];

    if ( cartographer == NULL )
        return;
    cart_where( cartographer->in_room, from, sizeof(from) );
    if ( cartographer->in_room != NULL )
        act( "$n rolls up $s charts, tucks them away and strides off beyond the "
             "edge of the map.", cartographer, NULL, NULL, TO_ROOM );
    extract_char( cartographer, true );      /* cartographer_forget clears it */
    cartographer = NULL;
    snprintf( line, sizeof(line), "Cartographer: left %s (%s).", from, why );
    log_string( line );
}

/* extract_char calls this, however he goes: the next visit is hours off. */
void cartographer_forget( CHAR_DATA *ch )
{
    if ( ch == NULL || ch != cartographer )
        return;
    cartographer = NULL;
    cart_area = NULL;
    cart_next_spawn = current_time + number_range( CART_AWAY_MIN, CART_AWAY_MAX );
}

/* raw_kill_internal, before make_corpse: the map of where he fell goes
   into his pack, so it comes out in the corpse. */
void cartographer_slain( CHAR_DATA *ch, CHAR_DATA *victim )
{
    CHAR_DATA *who = ch;
    ROOM_INDEX_DATA *anchor = NULL;
    OBJ_DATA *map;
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH * 2];

    if ( !is_cartographer( victim ) || victim->in_room == NULL )
        return;
    if ( who != NULL && IS_NPC(who) && IS_AFFECTED( who, AFF_CHARM ) && who->master != NULL )
        who = who->master;
    if ( who == victim )
        who = NULL;

    if ( map_area_mappable( victim->in_room->area ) && !map_is_hyrule( victim->in_room->area ) )
        anchor = map_area_anchor( victim->in_room->area );
    else if ( victim == cartographer && cart_area != NULL )
        anchor = map_area_anchor( cart_area );
    if ( anchor != NULL && ( map = map_item_create( anchor ) ) != NULL )
    {
        map->value[2] = MAP_FOUND_ON_FOE;   /* Treasure Map, when it is read */
        obj_to_char( map, victim );
        act( "Charts spill from $n's folio as $e falls.", victim, NULL, NULL, TO_ROOM );
    }

    cart_where( victim->in_room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Cartographer: slain by %s in %s.",
              who == NULL ? "nothing" : ( IS_NPC(who) ? who->short_descr : who->name ),
              where );
    log_string( line );
    wizinfo( line, LEVEL_IMMORTAL );
    if ( who != NULL && !IS_NPC(who) )
        achievement_party_event( who, victim->in_room, ACHIEVEMENT_EVENT_CARTOGRAPHER );
}

/* A step to a room of the same area he may stand in, or nowhere. */
static void cart_wander( CHAR_DATA *cart )
{
    int doors[10];
    int n = 0;
    int door;

    for ( door = 0; door <= 9; door++ )
    {
        EXIT_DATA *pexit = cart->in_room->exit[door];

        if ( pexit != NULL && pexit->u1.to_room != NULL
        &&   !IS_SET( pexit->exit_info, EX_CLOSED )
        &&   pexit->u1.to_room->area == cart->in_room->area
        &&   cart_room_ok( pexit->u1.to_room ) )
            doors[n++] = door;
    }
    if ( n > 0 )
        move_char( cart, doors[number_range( 0, n - 1 )], false );
}

/* Every mobile pulse, from update_handler. */
void cartographer_update( void )
{
    CHAR_DATA *cart = cartographer;

    if ( cart == NULL )
    {
        /* Test worlds have none unless staff call one (tests/live_mud.py). */
        if ( getenv( "TOC_NO_CARTOGRAPHER" ) != NULL )
            return;
        if ( cart_next_spawn == 0 )
            cart_next_spawn = current_time + number_range( CART_FIRST_MIN, CART_FIRST_MAX );
        else if ( current_time >= cart_next_spawn && !cartographer_spawn( NULL ) )
            cart_next_spawn = current_time + 5 * 60;
        return;
    }
    if ( cart->in_room == NULL )
        return;
    /* A Man With a Map: every mortal who stands with him and sees him has
       found him, once a visit (the set keeps the visit's arrival time). */
    {
        CHAR_DATA *rch;

        for ( rch = cart->in_room->people; rch != NULL; rch = rch->next_in_room )
            if ( !IS_NPC(rch) && !is_staff( rch ) && can_see( rch, cart ) )
                achievement_note( rch, ACH_SET_CARTOGRAPHER_VISITS,
                                  (long) UMIN( cart_arrived, (time_t) INT_MAX ) );
    }
    if ( cart->fighting != NULL || cart->position < POS_STANDING )
        return;
    cart->move = cart->max_move;
    if ( current_time >= cart_leaves
    &&   ( !cart_has_company( cart ) || current_time >= cart_leaves + CART_OVERSTAY ) )
    {
        cartographer_depart( "his visit is over" );
        return;
    }
    if ( getenv( "TOC_CARTOGRAPHER_STILL" ) != NULL || cart_has_company( cart ) )
        return;
    if ( current_time >= cart_next_step )
    {
        cart_next_step = current_time + number_range( CART_STEP_MIN, CART_STEP_MAX );
        cart_wander( cart );
    }
}

void do_cartographer( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];

    one_argument( argument, arg );
    if ( arg[0] == '\0' || !str_prefix( arg, "status" ) )
    {
        if ( cartographer == NULL || cartographer->in_room == NULL )
            snprintf( buf, sizeof(buf), "There is no cartographer about; the next comes "
                      "in about %ld minutes.\n\r",
                      cart_next_spawn > current_time
                          ? (long)( cart_next_spawn - current_time ) / 60 : 0L );
        else
            snprintf( buf, sizeof(buf), "The cartographer is in room %d (%s), level %d, "
                      "%d/%d hit points; he leaves in about %ld minutes.\n\r",
                      cartographer->in_room->vnum, cartographer->in_room->name,
                      cartographer->level, cartographer->hit, cartographer->max_hit,
                      cart_leaves > current_time ? (long)( cart_leaves - current_time ) / 60 : 0L );
        send_to_char( buf, ch );
        send_to_char( "Syntax: cartographer [status|spawn|here|dismiss]\n\r", ch );
        return;
    }
    if ( !str_prefix( arg, "spawn" ) || !str_prefix( arg, "here" ) )
    {
        bool here = !str_prefix( arg, "here" );

        if ( cartographer != NULL && here )
            cartographer_depart( "called away by staff" );
        else if ( cartographer != NULL )
        {
            send_to_char( "He is about already; CARTOGRAPHER HERE brings him to you.\n\r", ch );
            return;
        }
        if ( here && ch->in_room != NULL && map_is_hyrule( ch->in_room->area ) )
        {
            send_to_char( "He will not set foot in Hyrule.\n\r", ch );
            return;
        }
        if ( !cartographer_spawn( here ? ch->in_room : NULL ) )
        {
            send_to_char( "No cartographer would come.\n\r", ch );
            return;
        }
        snprintf( buf, sizeof(buf), "The cartographer is in room %d.\n\r",
                  cartographer->in_room->vnum );
        send_to_char( buf, ch );
        snprintf( buf, sizeof(buf), "%s called the cartographer.", ch->name );
        log_string( buf );
        return;
    }
    if ( !str_prefix( arg, "dismiss" ) )
    {
        if ( cartographer == NULL )
        {
            send_to_char( "There is no cartographer about.\n\r", ch );
            return;
        }
        cartographer_depart( "dismissed by staff" );
        send_to_char( "The cartographer is gone; another will come in a few hours.\n\r", ch );
        return;
    }
    send_to_char( "Syntax: cartographer [status|spawn|here|dismiss]\n\r", ch );
}
