/***************************************************************************
 * WALKTO: walk to a named place from wherever you are standing.            *
 *                                                                          *
 * The routes the website, the Mudlet package and HELP WALKTO publish all   *
 * start at the Oak Tree Square, which is no help to somebody standing      *
 * anywhere else. This finds the way from the room the player is in and     *
 * walks it for them, one room at a time on the game's pulse, through       *
 * move_char like any other step -- so every rule a walking player obeys    *
 * (private rooms, guild guards, boats, flying, lag, movement points)       *
 * still applies, and a refusal simply ends the walk.                       *
 *                                                                          *
 * The way is found again before every step rather than planned once. A     *
 * door somebody shuts, a portal that is gone, a room that has filled up    *
 * or a teleport that carried the walker on are then just the next step     *
 * of the search, not a stale plan walked into a wall.                      *
 *                                                                          *
 * The destinations are area/walkto.dat, which tools/build_directions.py    *
 * writes from the same data as webadmin/directions.json, so WALKTO, the    *
 * website and the Oracle name the same places.                             *
 ***************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "merc.h"
#include "interp.h"

extern char * const dir_name[];
bool has_key( CHAR_DATA *ch, int key );

#define WALKTO_FILE            "walkto.dat"
#define WALKTO_MAX_DEST        400

/* A room every half second: quick enough to be worth using, slow enough
   that a walker still reads like somebody walking. */
#define WALKTO_STEP_PULSES     2

/* Bounds on one walk. A route the size of the world is under 120 rooms;
   600 steps means something is going round in circles. Waiting in a
   room that carries you is allowed two minutes, looked at once a second. */
#define WALKTO_MAX_STEPS       600
#define WALKTO_MAX_WAIT        120

/* What a move is worth, as tools/build_directions.py prices it: a step
   or a portal is one room, a room that carries you on a timer is eight,
   because you wait on it and cannot steer. */
#define WALK_COST_MOVE         1
#define WALK_COST_WAIT         8
/* A portal that takes 500 gold: used only where nothing free goes. */
#define WALK_COST_FARE         40
#define WALK_FARE_GOLD         500

/* A room vnum is an sh_int, so this covers every room there can be. */
#define WALK_SLOTS             32768
#define WALK_MAX_MOVES         48
#define WALK_MAX_CLOSED        512

/* Hyrule, as act_move.c numbers it (HYRULE_ROOM_MIN/MAX and the two
   items its water and gaps ask for). */
#define WALK_HYRULE_FIRST      30200
#define WALK_HYRULE_LAST       30799
#define WALK_HYRULE_RAFT       30411
#define WALK_HYRULE_STEPLADDER 30412

typedef struct walkto_dest
{
    char kind[12];          /* place, guild, clerk, trainer, area */
    int  vnum;
    char name[96];
    char place[64];
    char keywords[256];
    char who[96];           /* who a guard lets in, or "" */
} WALKTO_DEST;

static WALKTO_DEST walkto_dests[WALKTO_MAX_DEST];
static int         walkto_count = 0;

enum { WALK_EXIT, WALK_OBJECT, WALK_WAIT };

typedef struct walk_move
{
    int               kind;
    int               door;      /* WALK_EXIT */
    OBJ_DATA *        obj;       /* WALK_OBJECT */
    ROOM_INDEX_DATA * to;
    int               cost;
} WALK_MOVE;

typedef struct walk_heap_node
{
    int               cost;
    ROOM_INDEX_DATA * room;
} WALK_HEAP_NODE;

/* Scratch for the search, stamped with a generation rather than cleared:
   a slot belongs to this search only when its stamp says so. */
static unsigned int walk_generation = 0;
static unsigned int walk_seen_gen[WALK_SLOTS];
static unsigned int walk_closed_gen[WALK_SLOTS];
static int          walk_cost[WALK_SLOTS];
static short        walk_first[WALK_SLOTS];
static bool         walk_done[WALK_SLOTS];

static WALK_HEAP_NODE *walk_heap = NULL;
static int             walk_heap_size = 0;
static int             walk_heap_cap = 0;


/* ---------------------------------------------------------------------
 * The destination list.
 * ------------------------------------------------------------------- */

/* One tab-separated field into dst; "-" means empty. */
static char *walkto_field( char *src, char *dst, size_t size )
{
    char *tab = src != NULL ? strchr( src, '\t' ) : NULL;

    if ( src == NULL )
    {
        dst[0] = '\0';
        return NULL;
    }
    if ( tab != NULL )
        *tab = '\0';
    toc_strlcpy( dst, strcmp( src, "-" ) ? src : "", size );
    return tab != NULL ? tab + 1 : NULL;
}

void walkto_load( void )
{
    FILE *fp;
    char line[1024];
    char vnum[16];

    walkto_count = 0;
    if ( ( fp = fopen( WALKTO_FILE, "r" ) ) == NULL )
    {
        log_string( "walkto_load: no " WALKTO_FILE "; WALKTO knows no places." );
        return;
    }

    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        WALKTO_DEST *d;
        char *p;
        size_t len = strlen( line );

        while ( len > 0 && ( line[len - 1] == '\n' || line[len - 1] == '\r' ) )
            line[--len] = '\0';
        if ( line[0] == '\0' || line[0] == '#' )
            continue;
        if ( walkto_count >= WALKTO_MAX_DEST )
        {
            bug( "walkto_load: more than %d destinations; the rest ignored.",
                 WALKTO_MAX_DEST );
            break;
        }

        d = &walkto_dests[walkto_count];
        p = walkto_field( line, d->kind, sizeof(d->kind) );
        p = walkto_field( p, vnum, sizeof(vnum) );
        p = walkto_field( p, d->name, sizeof(d->name) );
        p = walkto_field( p, d->place, sizeof(d->place) );
        p = walkto_field( p, d->keywords, sizeof(d->keywords) );
        walkto_field( p, d->who, sizeof(d->who) );

        if ( !is_number( vnum ) || ( d->vnum = atoi( vnum ) ) <= 0
        ||   d->vnum >= WALK_SLOTS || d->name[0] == '\0' )
            continue;
        walkto_count++;
    }
    fclose( fp );

    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf), "walkto_load: %d destinations.",
                  walkto_count );
        log_string( buf );
    }
}


/* ---------------------------------------------------------------------
 * Finding the way.
 * ------------------------------------------------------------------- */

/* A vnum the scratch arrays have a slot for. Rooms hold an sh_int, so
   that is every room; asked anyway, in case the type ever grows. */
static bool walk_slot( int vnum )
{
    return vnum > 0 && vnum < WALK_SLOTS;
}

static bool walk_is_hyrule( ROOM_INDEX_DATA *room )
{
    return room->vnum >= WALK_HYRULE_FIRST && room->vnum <= WALK_HYRULE_LAST;
}

static TELEPORT_ROOM_DATA *walk_teleport( ROOM_INDEX_DATA *room )
{
    TELEPORT_ROOM_DATA *t;

    if ( !IS_SET(room->room_flags, ROOM_TELEPORT) )
        return NULL;
    for ( t = teleport_room_list; t != NULL; t = t->next )
        if ( t->room == room )
            return t;
    return NULL;
}

/* A room that teleports whoever stands in it to the Temple is a trap or
   a joke -- the House of Pancakes -- and never a way anywhere. */
static bool walk_is_ejector( ROOM_INDEX_DATA *room )
{
    TELEPORT_ROOM_DATA *t = walk_teleport( room );

    return t != NULL && ( t->to_room == ROOM_VNUM_TEMPLE
                       || t->to_room == ROOM_VNUM_ALTAR );
}

static bool walk_has_boat( CHAR_DATA *ch )
{
    OBJ_DATA *obj;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->item_type == ITEM_BOAT )
            return true;
    return false;
}

/* Whether this character may stand in this room on the way. */
static bool walk_room_ok( CHAR_DATA *ch, ROOM_INDEX_DATA *room,
                          ROOM_INDEX_DATA *target )
{
    int iClass, iGuild;

    if ( room == NULL || !walk_slot( room->vnum ) )
        return false;
    /* Never, not even as the destination. */
    if ( IS_SET(room->room_flags, ROOM_DT) )
        return false;
    if ( walk_closed_gen[room->vnum] == walk_generation )
        return false;
    if ( !can_see_room( ch, room ) || !can_enter_private_room( ch, room ) )
        return false;
    if ( !IS_IMMORTAL(ch) && ch->level > 10
    &&   IS_SET(room->room_flags, ROOM_NEWBIES_ONLY) )
        return false;
    if ( room != target && walk_is_ejector( room ) )
        return false;

    /* move_char's "You aren't allowed in there": another class's room. */
    for ( iClass = 0; iClass < MAX_CLASS; iClass++ )
    {
        if ( iClass == ch->class )
            continue;
        for ( iGuild = 0; iGuild < MAX_GUILD; iGuild++ )
            if ( class_table[iClass].guild[iGuild] == room->vnum )
                return false;
    }
    return true;
}

/* Whether this exit can be walked, opening it on the way if it is shut. */
static bool walk_exit_ok( CHAR_DATA *ch, ROOM_INDEX_DATA *from, EXIT_DATA *pexit,
                          bool flying, bool boat )
{
    ROOM_INDEX_DATA *to;

    if ( pexit == NULL || ( to = pexit->u1.to_room ) == NULL )
        return false;
    if ( IS_SET(pexit->exit_info, EX_WIZLOCKED) && ch->level < 68 )
        return false;
    if ( IS_SET(pexit->exit_info, EX_LOCKED) )
        return false;
    if ( IS_SET(pexit->exit_info, EX_SECRET) )
    {
        /* A Hyrule seal opens only to its own act with its own tool
           (hyrule_seal_refuses), and a secret door with no name cannot
           be opened by name at all. */
        if ( walk_is_hyrule( from ) || pexit->keyword == NULL
        ||   pexit->keyword[0] == '\0' )
            return false;
    }
    if ( walk_is_hyrule( from ) && pexit->keyword != NULL )
    {
        if ( is_name( "raft", pexit->keyword ) && !has_key( ch, WALK_HYRULE_RAFT ) )
            return false;
        if ( is_name( "stepladder", pexit->keyword )
        &&   !has_key( ch, WALK_HYRULE_STEPLADDER ) )
            return false;
        if ( is_name( "triforce", pexit->keyword ) )
            return false;
    }
    if ( ( from->sector_type == SECT_AIR || to->sector_type == SECT_AIR )
    &&   !flying )
        return false;
    if ( ( from->sector_type == SECT_WATER_NOSWIM
        || to->sector_type == SECT_WATER_NOSWIM )
    &&   !flying && !boat )
        return false;
    return true;
}

/* Whether an object in the room is a way through that WALKTO may use:
   a portal, or a rope, hole or ledge you climb, crawl or jump. A portal
   that takes 500 gold is one only for somebody who can pay it, and costs
   enough in the search that any free way wins. Levers, buttons and
   anything wanting a tool are not ways anywhere. */
static ROOM_INDEX_DATA *walk_object_to( CHAR_DATA *ch, OBJ_DATA *obj )
{
    if ( !can_see_obj( ch, obj ) )
        return NULL;

    if ( obj->item_type == ITEM_PORTAL )
    {
        switch ( obj->value[0] )
        {
        case 0:
        case 5:
            break;
        case 6:
            if ( obj->value[4] > 0 && !has_key( ch, obj->value[4] ) )
                return NULL;
            break;
        case 1:         /* the Hall of Heroes' windows: 500 gold */
            if ( !IS_IMMORTAL(ch) && !has_enough_gold( ch, WALK_FARE_GOLD ) )
                return NULL;
            break;
        default:        /* 2 and 3 are spells, 4 a crystal ball */
            return NULL;
        }
        return get_room_index( obj->value[1] );
    }

    if ( obj->item_type == ITEM_MANIPULATION )
    {
        switch ( obj->value[0] )
        {
        case 6:         /* climb up */
        case 7:         /* climb down */
        case 8:         /* crawl */
            break;
        case 9:         /* jump: down, up or over */
            if ( obj->value[2] < 1 || obj->value[2] > 3 )
                return NULL;
            break;
        default:
            return NULL;
        }
        return get_room_index( obj->value[1] );
    }

    return NULL;
}

/* Every move out of a room this character could make, in moves[]. */
static int walk_moves( CHAR_DATA *ch, ROOM_INDEX_DATA *room,
                       ROOM_INDEX_DATA *target, WALK_MOVE *moves,
                       bool flying, bool boat )
{
    TELEPORT_ROOM_DATA *tele;
    OBJ_DATA *obj;
    int count = 0;
    int door;

    for ( door = 0; door <= DIR_SOUTHWEST && count < WALK_MAX_MOVES; door++ )
    {
        EXIT_DATA *pexit = room->exit[door];

        if ( !walk_exit_ok( ch, room, pexit, flying, boat )
        ||   !walk_room_ok( ch, pexit->u1.to_room, target )
        ||   hyrule_gate_would_refuse( ch, room, pexit->u1.to_room ) )
            continue;
        moves[count].kind = WALK_EXIT;
        moves[count].door = door;
        moves[count].obj  = NULL;
        moves[count].to   = pexit->u1.to_room;
        moves[count].cost = WALK_COST_MOVE;
        count++;
    }

    for ( obj = room->contents; obj != NULL && count < WALK_MAX_MOVES;
          obj = obj->next_content )
    {
        ROOM_INDEX_DATA *to = walk_object_to( ch, obj );

        if ( to == NULL || to == room || !walk_room_ok( ch, to, target ) )
            continue;
        moves[count].kind = WALK_OBJECT;
        moves[count].door = -1;
        moves[count].obj  = obj;
        moves[count].to   = to;
        moves[count].cost = ( obj->item_type == ITEM_PORTAL
                              && obj->value[0] == 1 && !IS_IMMORTAL(ch) )
                            ? WALK_COST_FARE : WALK_COST_MOVE;
        count++;
    }

    if ( count < WALK_MAX_MOVES && ( tele = walk_teleport( room ) ) != NULL )
    {
        ROOM_INDEX_DATA *to = get_room_index( tele->to_room );

        if ( to != NULL && to != room && !walk_is_ejector( room )
        &&   walk_room_ok( ch, to, target ) )
        {
            moves[count].kind = WALK_WAIT;
            moves[count].door = -1;
            moves[count].obj  = NULL;
            moves[count].to   = to;
            moves[count].cost = WALK_COST_WAIT;
            count++;
        }
    }

    return count;
}

static void walk_heap_push( int cost, ROOM_INDEX_DATA *room )
{
    int i;

    if ( walk_heap_size >= walk_heap_cap )
    {
        int cap = walk_heap_cap > 0 ? walk_heap_cap * 2 : 4096;
        WALK_HEAP_NODE *grown = realloc( walk_heap, (size_t)cap * sizeof(*grown) );

        if ( grown == NULL )
            return;
        walk_heap = grown;
        walk_heap_cap = cap;
    }

    i = walk_heap_size++;
    while ( i > 0 && walk_heap[(i - 1) / 2].cost > cost )
    {
        walk_heap[i] = walk_heap[(i - 1) / 2];
        i = (i - 1) / 2;
    }
    walk_heap[i].cost = cost;
    walk_heap[i].room = room;
}

static WALK_HEAP_NODE walk_heap_pop( void )
{
    WALK_HEAP_NODE top = walk_heap[0];
    WALK_HEAP_NODE last = walk_heap[--walk_heap_size];
    int i = 0;

    for ( ;; )
    {
        int child = 2 * i + 1;

        if ( child >= walk_heap_size )
            break;
        if ( child + 1 < walk_heap_size
        &&   walk_heap[child + 1].cost < walk_heap[child].cost )
            child++;
        if ( walk_heap[child].cost >= last.cost )
            break;
        walk_heap[i] = walk_heap[child];
        i = child;
    }
    if ( walk_heap_size > 0 )
        walk_heap[i] = last;
    return top;
}

/*
 * The cheapest way from the character's room to target. Returns the cost
 * and fills *first with the move to make now; 0 means already there and
 * -1 means no way this character can walk.
 */
static int walk_find( CHAR_DATA *ch, ROOM_INDEX_DATA *target, WALK_MOVE *first )
{
    ROOM_INDEX_DATA *src = ch->in_room;
    ROOM_INDEX_DATA *closed[WALK_MAX_CLOSED];
    WALK_MOVE start[WALK_MAX_MOVES];
    WALK_MOVE moves[WALK_MAX_MOVES];
    bool flying, boat;
    int nstart, nclosed, i;

    if ( src == NULL || target == NULL )
        return -1;
    if ( src == target )
        return 0;
    if ( !walk_slot( target->vnum ) || !walk_slot( src->vnum ) )
        return -1;

    if ( ++walk_generation == 0 )
    {
        /* Wrapped: every stamp is now ambiguous, so start them over. */
        memset( walk_seen_gen, 0, sizeof(walk_seen_gen) );
        memset( walk_closed_gen, 0, sizeof(walk_closed_gen) );
        walk_generation = 1;
    }

    /* The rooms behind a guild guard who would turn this character away
       (special.c). The guard would stop them at the door anyway; knowing
       it here means WALKTO says so instead of walking them up to him. */
    nclosed = guild_closed_rooms( ch, closed, WALK_MAX_CLOSED );
    for ( i = 0; i < nclosed; i++ )
        if ( closed[i] != NULL && walk_slot( closed[i]->vnum ) )
            walk_closed_gen[closed[i]->vnum] = walk_generation;

    if ( !walk_room_ok( ch, target, target ) )
        return -1;

    flying = IS_AFFECTED(ch, AFF_FLYING) || IS_IMMORTAL(ch);
    boat   = IS_IMMORTAL(ch) || walk_has_boat( ch );

    walk_heap_size = 0;
    walk_seen_gen[src->vnum] = walk_generation;
    walk_cost[src->vnum] = 0;
    walk_done[src->vnum] = true;

    nstart = walk_moves( ch, src, target, start, flying, boat );
    for ( i = 0; i < nstart; i++ )
    {
        int v = start[i].to->vnum;

        if ( walk_seen_gen[v] == walk_generation && walk_cost[v] <= start[i].cost )
            continue;
        walk_seen_gen[v] = walk_generation;
        walk_cost[v] = start[i].cost;
        walk_first[v] = (short)i;
        walk_done[v] = false;
        walk_heap_push( start[i].cost, start[i].to );
    }

    while ( walk_heap_size > 0 )
    {
        WALK_HEAP_NODE node = walk_heap_pop();
        ROOM_INDEX_DATA *here = node.room;
        int n, j;

        if ( walk_done[here->vnum] || node.cost > walk_cost[here->vnum] )
            continue;
        walk_done[here->vnum] = true;

        if ( here == target )
        {
            *first = start[walk_first[here->vnum]];
            return node.cost;
        }

        n = walk_moves( ch, here, target, moves, flying, boat );
        for ( j = 0; j < n; j++ )
        {
            int v = moves[j].to->vnum;
            int cost = node.cost + moves[j].cost;

            if ( walk_seen_gen[v] == walk_generation
            &&   ( walk_done[v] || walk_cost[v] <= cost ) )
                continue;
            walk_seen_gen[v] = walk_generation;
            walk_cost[v] = cost;
            walk_first[v] = walk_first[here->vnum];
            walk_done[v] = false;
            walk_heap_push( cost, moves[j].to );
        }
    }

    return -1;
}


/* ---------------------------------------------------------------------
 * Walking it.
 * ------------------------------------------------------------------- */

static const char *walkto_dest_name( CHAR_DATA *ch )
{
    int i = ch->pcdata->walkto_dest;
    ROOM_INDEX_DATA *room;

    if ( i >= 0 && i < walkto_count && walkto_dests[i].vnum == ch->pcdata->walkto_vnum )
        return walkto_dests[i].name;
    room = get_room_index( ch->pcdata->walkto_vnum );
    return room != NULL ? room->name : "where you were going";
}

void walkto_clear( CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    ch->pcdata->walkto_vnum   = 0;
    ch->pcdata->walkto_dest   = -1;
    ch->pcdata->walkto_steps  = 0;
    ch->pcdata->walkto_waited = 0;
    ch->pcdata->walkto_expect = 0;
}

static void walkto_stop( CHAR_DATA *ch, const char *msg )
{
    walkto_clear( ch );
    if ( msg != NULL && msg[0] != '\0' )
        send_to_char( msg, ch );
}

static void walkto_arrive( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof(buf), "You have arrived at %s.\n\r",
              walkto_dest_name( ch ) );
    walkto_stop( ch, buf );
}

/* "2.rope": how get_obj_here will find exactly this object. */
static void walk_object_arg( CHAR_DATA *ch, OBJ_DATA *obj, char *out, size_t size )
{
    char name[MAX_INPUT_LENGTH];
    char word[MAX_INPUT_LENGTH];
    OBJ_DATA *o;
    int count = 0;

    toc_strlcpy( name, obj->name != NULL ? obj->name : "", sizeof(name) );
    one_argument( name, word );
    for ( o = ch->in_room->contents; o != NULL; o = o->next_content )
    {
        if ( can_see_obj( ch, o ) && is_name( word, o->name ) )
            count++;
        if ( o == obj )
            break;
    }
    snprintf( out, size, "%d.%.60s", UMAX( count, 1 ), word );
}

/* One step, or one pulse of waiting. */
static void walkto_step( CHAR_DATA *ch )
{
    PC_DATA *pc = ch->pcdata;
    ROOM_INDEX_DATA *here = ch->in_room;
    ROOM_INDEX_DATA *target;
    WALK_MOVE move;
    int cost;

    if ( here == NULL )
    {
        walkto_clear( ch );
        return;
    }

    if ( ( target = get_room_index( pc->walkto_vnum ) ) == NULL )
    {
        walkto_stop( ch, "You have lost the way, and stop walking.\n\r" );
        return;
    }

    /* Moved by something other than the walk -- a recall, a summons, a
       death, a leader you follow. That is the end of this walk, unless
       the room it left was one that carries you on: then being carried
       was the plan, or at worst a detour the next search starts from. */
    if ( pc->walkto_expect != 0 && here->vnum != pc->walkto_expect )
    {
        ROOM_INDEX_DATA *was = get_room_index( pc->walkto_expect );

        if ( was == NULL
        ||   !IS_SET(was->room_flags, ROOM_TELEPORT | ROOM_RIVER) )
        {
            walkto_stop( ch, "You have been taken off your path, and stop walking.\n\r" );
            return;
        }
        pc->walkto_expect = here->vnum;
        pc->walkto_waited = 0;
    }

    if ( here == target )
    {
        walkto_arrive( ch );
        return;
    }
    if ( ch->fighting != NULL )
    {
        walkto_stop( ch, "You stop walking to fight.\n\r" );
        return;
    }
    if ( ch->position != POS_STANDING )
    {
        walkto_stop( ch, "You stop walking.\n\r" );
        return;
    }

    if ( ( cost = walk_find( ch, target, &move ) ) < 0 )
    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf),
                  "You can find no way on to %s from here, and stop walking.\n\r",
                  walkto_dest_name( ch ) );
        walkto_stop( ch, buf );
        return;
    }
    if ( cost == 0 )
    {
        walkto_arrive( ch );
        return;
    }

    if ( move.kind == WALK_WAIT )
    {
        /* Stand still and let the room carry you, looking again once a
           second rather than every pulse. */
        if ( ++pc->walkto_waited > WALKTO_MAX_WAIT )
            walkto_stop( ch, "Nothing has carried you on, and you stop waiting.\n\r" );
        else
            WAIT_STATE( ch, PULSE_PER_SECOND );
        return;
    }

    if ( ++pc->walkto_steps > WALKTO_MAX_STEPS )
    {
        walkto_stop( ch, "You have walked a long way without arriving, and stop.\n\r" );
        return;
    }

    /* walk_room_ok already refused it; this is the belt to those braces. */
    if ( move.to == NULL || IS_SET(move.to->room_flags, ROOM_DT) )
    {
        walkto_stop( ch, "You stop walking.\n\r" );
        return;
    }

    if ( move.kind == WALK_OBJECT )
    {
        char arg[MAX_INPUT_LENGTH];

        walk_object_arg( ch, move.obj, arg, sizeof(arg) );
        if ( move.obj->item_type == ITEM_PORTAL && move.obj->value[0] == 1
        &&   !IS_IMMORTAL(ch) )
            act( "You pay the 500 gold $p asks.", ch, move.obj, NULL, TO_CHAR );
        if ( move.obj->item_type == ITEM_PORTAL )
            do_enter( ch, arg );
        else
            do_manipulate( ch, arg );
    }
    else
    {
        EXIT_DATA *pexit = here->exit[move.door];

        if ( IS_SET(pexit->exit_info, EX_CLOSED | EX_SECRET) )
        {
            char word[MAX_INPUT_LENGTH];

            if ( IS_SET(pexit->exit_info, EX_SECRET) )
            {
                char name[MAX_INPUT_LENGTH];

                toc_strlcpy( name, pexit->keyword, sizeof(name) );
                one_argument( name, word );
            }
            else
                toc_strlcpy( word, dir_name[move.door], sizeof(word) );

            do_open( ch, word );
            if ( ch->in_room != here )
            {
                walkto_clear( ch );     /* whatever was behind it moved them */
                return;
            }
            if ( IS_SET(pexit->exit_info, EX_CLOSED | EX_SECRET) )
            {
                walkto_stop( ch, "The way is shut, and you stop walking.\n\r" );
                return;
            }
            if ( ch->fighting != NULL )
            {
                walkto_stop( ch, "You stop walking to fight.\n\r" );
                return;
            }
        }
        move_char( ch, move.door, false );
    }

    if ( ch->in_room == NULL )
    {
        walkto_clear( ch );
        return;
    }
    if ( ch->in_room == here )
    {
        /* Refused: move_char, the portal or the guard has said why. */
        walkto_stop( ch, "You stop walking.\n\r" );
        return;
    }

    pc->walkto_expect = ch->in_room->vnum;
    pc->walkto_waited = 0;
    WAIT_STATE( ch, WALKTO_STEP_PULSES );

    if ( ch->in_room == target )
        walkto_arrive( ch );
}

/* Every pulse: each walker who is not lagged takes a step. */
void walkto_update( void )
{
    DESCRIPTOR_DATA *d, *d_next;

    for ( d = descriptor_list; d != NULL; d = d_next )
    {
        CHAR_DATA *ch;

        d_next = d->next;
        if ( d->connected != CON_PLAYING || ( ch = d->character ) == NULL
        ||   IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->walkto_vnum == 0 )
            continue;

        /* A command is waiting: let it run. Typing one stops the walk
           (walkto_interrupt), so this only holds the step back a pulse. */
        if ( d->incomm[0] != '\0' )
            continue;

        /* The input loop only counts lag down when there is input to
           hold back, and a walker typing nothing has none. */
        if ( ch->wait > 0 )
        {
            --ch->wait;
            continue;
        }

        walkto_step( ch );
    }
}

/*
 * A typed line while walking. Anything but WALKTO itself stops the walk
 * before it runs, so a player is never carried on through a fight they
 * started or past the shop they stopped to look at. A blank line is just
 * asking for the prompt, and leaves the walk going.
 */
void walkto_interrupt( CHAR_DATA *ch, const char *line )
{
    char copy[MAX_INPUT_LENGTH];
    char word[MAX_INPUT_LENGTH];
    int cmd;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL
    ||   ch->pcdata->walkto_vnum == 0 || line == NULL )
        return;

    toc_strlcpy( copy, line, sizeof(copy) );
    one_argument( copy, word );
    if ( word[0] == '\0' )
        return;

    cmd = cmd_tab_sn_lookup( word, get_trust( ch ) );
    if ( cmd >= 0 && cmd_table[cmd].do_fun == do_walkto )
        return;

    walkto_stop( ch, "You stop walking.\n\r" );
}


/* ---------------------------------------------------------------------
 * Naming a place.
 * ------------------------------------------------------------------- */

/* Lower-case words of letters and digits, one space apart: "Wyvern's
   Tower (Tyrst)" is "wyverns tower tyrst". */
static void walk_words( const char *src, char *dst, size_t size )
{
    size_t n = 0;
    bool space = false;

    if ( size == 0 )
        return;
    for ( ; src != NULL && *src != '\0' && n + 1 < size; src++ )
    {
        unsigned char c = (unsigned char)*src;

        if ( isalnum( c ) )
        {
            if ( space && n > 0 && n + 2 < size )
                dst[n++] = ' ';
            space = false;
            dst[n++] = (char)LOWER( c );
        }
        else if ( c == '\'' )
            continue;
        else
            space = true;
    }
    dst[n] = '\0';
}

static bool walk_is_filler( const char *word )
{
    return !str_cmp( word, "the" ) || !str_cmp( word, "of" )
        || !str_cmp( word, "a" ) || !str_cmp( word, "an" )
        || !str_cmp( word, "to" );
}

/* Whether every word of want starts some word of hay. */
static bool walk_words_match( const char *want, const char *hay )
{
    char wbuf[MAX_INPUT_LENGTH];
    char *w = wbuf;
    bool any = false;

    toc_strlcpy( wbuf, want, sizeof(wbuf) );
    while ( *w != '\0' )
    {
        char word[MAX_INPUT_LENGTH];
        const char *h = hay;
        bool found = false;

        w = one_argument( w, word );
        if ( word[0] == '\0' || walk_is_filler( word ) )
            continue;
        any = true;
        while ( *h != '\0' )
        {
            size_t len = strlen( word );

            if ( !strncmp( h, word, len ) )
            {
                found = true;
                break;
            }
            h = strchr( h, ' ' );
            if ( h == NULL )
                break;
            h++;
        }
        if ( !found )
            return false;
    }
    return any;
}

/* 3 an exact name, 2 the start of a name, 1 every word found, 0 none. */
static int walk_quality( const WALKTO_DEST *d, const char *want )
{
    char name[256];
    char hay[512];
    char words[256];

    walk_words( d->name, name, sizeof(name) );
    if ( !strcmp( name, want ) )
        return 3;
    if ( !str_prefix( want, name ) )
        return 2;
    snprintf( hay, sizeof(hay), "%s %s %s", d->name, d->place, d->keywords );
    walk_words( hay, words, sizeof(words) );
    return walk_words_match( want, words ) ? 1 : 0;
}

/* The best match for what was typed, or -1. *also counts the others
   that matched as well, and others[] names up to three of them. */
static int walkto_find( const char *argument, int *also, int others[3] )
{
    char want[MAX_INPUT_LENGTH];
    int best = -1, best_q = 0, i;

    *also = 0;
    walk_words( argument, want, sizeof(want) );
    if ( want[0] == '\0' )
        return -1;

    for ( i = 0; i < walkto_count; i++ )
    {
        int q = walk_quality( &walkto_dests[i], want );

        if ( q == 0 )
            continue;
        if ( q > best_q )
        {
            best = i;
            best_q = q;
            *also = 0;
        }
        else if ( q == best_q )
        {
            if ( *also < 3 )
                others[*also] = i;
            (*also)++;
        }
    }
    return best;
}


/* ---------------------------------------------------------------------
 * The lists.
 * ------------------------------------------------------------------- */

/* Append item to a comma-separated list in buf, wrapping lines at 76
   columns under an indent. */
static void walk_wrap( char *buf, size_t size, size_t *col, const char *item,
                       bool first, int indent )
{
    size_t len = strlen( item );

    if ( !first )
    {
        toc_strlcat( buf, ",", size );
        (*col)++;
        if ( *col + 1 + len > 76 )
        {
            int i;

            toc_strlcat( buf, "\n\r", size );
            for ( i = 0; i < indent; i++ )
                toc_strlcat( buf, " ", size );
            *col = (size_t)indent;
        }
        else
        {
            toc_strlcat( buf, " ", size );
            (*col)++;
        }
    }
    toc_strlcat( buf, item, size );
    *col += len;
}

/* A trainer's name without the "(place)" the list already heads it with. */
static void walk_short_name( const WALKTO_DEST *d, char *out, size_t size )
{
    char suffix[96];
    size_t nlen = strlen( d->name ), slen;

    toc_strlcpy( out, d->name, size );
    snprintf( suffix, sizeof(suffix), " (%s)", d->place );
    slen = strlen( suffix );
    if ( d->place[0] != '\0' && nlen > slen
    &&   !strcmp( d->name + nlen - slen, suffix ) && nlen - slen < size )
        out[nlen - slen] = '\0';
}

static void walkto_show_summary( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH * 2];
    size_t col;
    bool first;
    int i;

    toc_strlcpy( buf,
        "WALKTO <place> walks you there from wherever you are standing.\n\r"
        "WALKTO STOP, or any other command, stops you on the way.\n\r\n\r",
        sizeof(buf) );

    toc_strlcat( buf, "Places:      ", sizeof(buf) );
    col = 13;
    first = true;
    for ( i = 0; i < walkto_count; i++ )
        if ( !str_cmp( walkto_dests[i].kind, "place" )
        ||   !str_cmp( walkto_dests[i].kind, "clerk" ) )
        {
            walk_wrap( buf, sizeof(buf), &col, walkto_dests[i].name, first, 13 );
            first = false;
        }
    toc_strlcat( buf, "\n\rGuild halls: ", sizeof(buf) );
    col = 13;
    first = true;
    for ( i = 0; i < walkto_count; i++ )
        if ( !str_cmp( walkto_dests[i].kind, "guild" ) )
        {
            walk_wrap( buf, sizeof(buf), &col, walkto_dests[i].name, first, 13 );
            first = false;
        }
    toc_strlcat( buf,
        "\n\r\n\rWALKTO GUILDS, WALKTO TRAINERS and WALKTO AREAS list the rest.\n\r"
        "Name a place by any part of its name: WALKTO NECRO MASTER.\n\r",
        sizeof(buf) );
    send_to_char( buf, ch );
}

static void walkto_show_guilds( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH * 2];
    char line[MAX_STRING_LENGTH];
    int i;

    toc_strlcpy( buf, "Guild halls, and who the guards let in:\n\r", sizeof(buf) );
    for ( i = 0; i < walkto_count; i++ )
    {
        const WALKTO_DEST *d = &walkto_dests[i];

        if ( !str_cmp( d->kind, "guild" ) )
            snprintf( line, sizeof(line), "  %-36s %s\n\r", d->name,
                      d->who[0] != '\0' ? d->who : "anyone" );
        else if ( !str_cmp( d->kind, "clerk" ) )
            snprintf( line, sizeof(line), "  %-36s %s\n\r", d->name,
                      "joins you to a guild" );
        else
            continue;
        toc_strlcat( buf, line, sizeof(buf) );
    }
    toc_strlcat( buf, "WALKTO TRAINERS names everyone who teaches inside them.\n\r",
                 sizeof(buf) );
    send_to_char( buf, ch );
}

static void walkto_show_trainers( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH * 4];
    char place[64];
    char name[96];
    size_t col = 0;
    bool first = true;
    int i;

    toc_strlcpy( buf, "Guildmasters and trainers, by where they are:\n\r", sizeof(buf) );
    place[0] = '\0';
    for ( i = 0; i < walkto_count; i++ )
    {
        const WALKTO_DEST *d = &walkto_dests[i];

        if ( str_cmp( d->kind, "trainer" ) )
            continue;
        if ( strcmp( place, d->place ) )
        {
            char head[256];

            toc_strlcpy( place, d->place, sizeof(place) );
            snprintf( head, sizeof(head), "%s%s%s%s:\n\r    ",
                      first ? "" : "\n\r",
                      place[0] != '\0' ? place : "Elsewhere",
                      d->who[0] != '\0' ? " -- " : "",
                      d->who );
            toc_strlcat( buf, head, sizeof(buf) );
            col = 4;
            first = true;
        }
        walk_short_name( d, name, sizeof(name) );
        walk_wrap( buf, sizeof(buf), &col, name, first, 4 );
        first = false;
    }
    toc_strlcat( buf,
        "\n\rTEACHLIST and GAINLIST say which of them will teach you.\n\r",
        sizeof(buf) );
    page_to_char( buf, ch );
}

static void walkto_show_areas( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH * 4];
    char cell[64];
    int i, n = 0;

    toc_strlcpy( buf, "Areas you can walk to (HELP WALKTO says how far each is):\n\r",
                 sizeof(buf) );
    for ( i = 0; i < walkto_count; i++ )
    {
        const WALKTO_DEST *d = &walkto_dests[i];
        char *paren;

        if ( str_cmp( d->kind, "area" ) )
            continue;
        /* "Moria (Alfa)": the builder's name is the help's business. */
        toc_strlcpy( cell, d->name, sizeof(cell) );
        if ( ( paren = strrchr( cell, '(' ) ) != NULL && paren > cell )
        {
            *paren = '\0';
            while ( paren > cell && paren[-1] == ' ' )
                *--paren = '\0';
        }
        if ( strlen( cell ) > 25 )
            cell[25] = '\0';
        {
            char item[64];

            snprintf( item, sizeof(item), "%-26s", cell );
            toc_strlcat( buf, item, sizeof(buf) );
        }
        if ( ++n % 3 == 0 )
            toc_strlcat( buf, "\n\r", sizeof(buf) );
    }
    if ( n % 3 != 0 )
        toc_strlcat( buf, "\n\r", sizeof(buf) );
    page_to_char( buf, ch );
}


/* ---------------------------------------------------------------------
 * The command.
 * ------------------------------------------------------------------- */

void do_walkto( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char want[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    ROOM_INDEX_DATA *target;
    WALK_MOVE move;
    const char *name;
    const char *who;
    int found, also, others[3], cost, i;
    size_t len;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players can walk to places.\n\r", ch );
        return;
    }

    while ( isspace( (unsigned char)*argument ) )
        argument++;
    toc_strlcpy( want, argument, sizeof(want) );
    len = strlen( want );
    while ( len > 0 && isspace( (unsigned char)want[len - 1] ) )
        want[--len] = '\0';
    argument = want;
    one_argument( argument, arg );

    if ( walkto_count == 0 )
    {
        send_to_char( "Nobody has told you where anything is.\n\r", ch );
        return;
    }

    if ( arg[0] == '\0' )
    {
        walkto_show_summary( ch );
        return;
    }
    if ( !str_cmp( argument, "stop" ) )
    {
        if ( ch->pcdata->walkto_vnum == 0 )
            send_to_char( "You are not walking anywhere.\n\r", ch );
        else
            walkto_stop( ch, "You stop walking.\n\r" );
        return;
    }
    if ( !str_cmp( argument, "guild" ) || !str_cmp( argument, "guilds" ) )
    {
        walkto_show_guilds( ch );
        return;
    }
    if ( !str_cmp( argument, "trainer" ) || !str_cmp( argument, "trainers" )
    ||   !str_cmp( argument, "guildmasters" ) )
    {
        walkto_show_trainers( ch );
        return;
    }
    if ( !str_cmp( argument, "area" ) || !str_cmp( argument, "areas" ) )
    {
        walkto_show_areas( ch );
        return;
    }

    /* Any other WALKTO replaces the walk under way, whether or not it
       finds somewhere to go. */
    if ( ch->pcdata->walkto_vnum != 0 )
        walkto_clear( ch );

    if ( is_number( argument ) && IS_TRUSTED(ch, LEVEL_IMMORTAL) )
    {
        /* Staff may name a room by number; nobody else, since a vnum is
           no name a player is ever shown. */
        found = -1;
        also = 0;
        if ( ( target = get_room_index( atoi( argument ) ) ) == NULL )
        {
            send_to_char( "No room has that number.\n\r", ch );
            return;
        }
        name = target->name;
        who = "";
    }
    else
    {
        if ( ( found = walkto_find( argument, &also, others ) ) < 0 )
        {
            snprintf( buf, sizeof(buf),
                      "You know of nowhere called '%s'.  WALKTO lists the places.\n\r",
                      argument );
            send_to_char( buf, ch );
            return;
        }
        if ( ( target = get_room_index( walkto_dests[found].vnum ) ) == NULL )
        {
            send_to_char( "That place is not in the world just now.\n\r", ch );
            return;
        }
        name = walkto_dests[found].name;
        who = walkto_dests[found].who;
    }

    if ( ch->in_room == target )
    {
        snprintf( buf, sizeof(buf), "You are already at %s.\n\r", name );
        send_to_char( buf, ch );
        return;
    }
    if ( ch->fighting != NULL )
    {
        send_to_char( "Not while you are fighting.\n\r", ch );
        return;
    }
    if ( ch->position != POS_STANDING )
    {
        send_to_char( "You will have to stand up first.\n\r", ch );
        return;
    }

    if ( ( cost = walk_find( ch, target, &move ) ) < 0 )
    {
        if ( who[0] != '\0' )
            snprintf( buf, sizeof(buf),
                      "You can find no way to %s from here.  Only %s are let in.\n\r",
                      name, who );
        else
            snprintf( buf, sizeof(buf),
                      "You can find no way to %s from here that you can walk.\n\r",
                      name );
        send_to_char( buf, ch );
        return;
    }

    ch->pcdata->walkto_vnum   = target->vnum;
    ch->pcdata->walkto_dest   = found;
    ch->pcdata->walkto_steps  = 0;
    ch->pcdata->walkto_waited = 0;
    ch->pcdata->walkto_expect = ch->in_room->vnum;

    snprintf( buf, sizeof(buf),
              "You set off for %s, about %d room%s away.\n\r"
              "WALKTO STOP, or any other command, stops you.\n\r",
              name, cost, cost == 1 ? "" : "s" );
    send_to_char( buf, ch );

    if ( also > 0 )
    {
        toc_strlcpy( buf, "Also called that:", sizeof(buf) );
        for ( i = 0; i < also && i < 3; i++ )
        {
            toc_strlcat( buf, i == 0 ? " " : ", ", sizeof(buf) );
            toc_strlcat( buf, walkto_dests[others[i]].name, sizeof(buf) );
        }
        if ( also > 3 )
            toc_strlcat( buf, ", and more", sizeof(buf) );
        toc_strlcat( buf, ".  Name more of it to choose.\n\r", sizeof(buf) );
        send_to_char( buf, ch );
    }
}
