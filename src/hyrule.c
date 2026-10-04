/***************************************************************************
 * Hyrule's NES machinery: what the dungeon maps and compasses tell you,   *
 * the secret caves and what they give, the seals on hidden entrances, and *
 * what the items do in your hands.                                         *
 *                                                                          *
 * Movement, the dungeon gates and the small keys stay in act_move.c and    *
 * combat in fight.c; this file holds what the NES game did with the items  *
 * and the caves. The plan, and why each rule is the NES one, is in         *
 * wiki/hyrule-area.md; scripts/build_hyrule_area.py writes the objects     *
 * and rooms these rules read, and tests/test_hyrule_progression.py holds   *
 * the tables here to the generator's.                                      *
 ***************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "merc.h"
#include "interp.h"
#include "magic.h"

extern const char *dir_name[];
void    check_killer    ( CHAR_DATA *ch, CHAR_DATA *victim );

/* --------------------------------------------------------------------
 * Dungeon maps and compasses.
 *
 * Each dungeon's map is an ITEM_MAP with value[0] HYRULE_DUNGEON_MAP and
 * its compass one with HYRULE_DUNGEON_COMPASS; value[4] is the dungeon's
 * level. The map carries its floor plan as an extra description the
 * generator writes (HYRULE_PLAN_KEYWORD): eight rows of eight room vnums,
 * north row first and 0 for no room, then the map and compass rooms and
 * each block-stair cellar with the room above it. Everything else -- the
 * entrance, the guardian, the treasure room and what the guardian's door
 * asks for -- is the dungeon's row of hyrule_progress_gate (act_move.c),
 * so the map can never disagree with the gate.
 * ------------------------------------------------------------------ */

#define HYRULE_PLAN_KEYWORD     "hyrule-floor-plan"
#define HYRULE_PLAN_SIDE        8
#define HYRULE_PLAN_CELLARS     4
#define HYRULE_DUNGEON_SPAN     128     /* rooms a dungeon may hold */

static const char *const hyrule_dungeon_titles[10] =
{
    "", "The Eagle", "The Moon", "The Manji", "The Snake", "The Lizard",
    "The Dragon", "The Demon", "The Lion", "Death Mountain"
};

typedef struct hyrule_plan
{
    int cell[HYRULE_PLAN_SIDE][HYRULE_PLAN_SIDE];
    int map_room;
    int compass_room;
    int cellar[HYRULE_PLAN_CELLARS];
    int cellar_above[HYRULE_PLAN_CELLARS];
    int cellars;
} HYRULE_PLAN;

bool hyrule_is_dungeon_tool( const OBJ_DATA *obj )
{
    return obj != NULL && obj->item_type == ITEM_MAP
        && ( obj->value[0] == HYRULE_DUNGEON_MAP
          || obj->value[0] == HYRULE_DUNGEON_COMPASS )
        && obj->value[4] >= 1 && obj->value[4] <= 9;
}

static const char *plan_text( const OBJ_DATA *obj )
{
    const char *text;

    text = get_extra_descr( HYRULE_PLAN_KEYWORD, obj->extra_descr );
    if ( text == NULL && obj->pIndexData != NULL )
        text = get_extra_descr( HYRULE_PLAN_KEYWORD, obj->pIndexData->extra_descr );
    return text;
}

/* Reads the next integer from *cursor, skipping anything that is not a
   digit; false at the end of the text. */
static bool plan_number( const char **cursor, int *value )
{
    const char *p = *cursor;
    char *end;
    long n;

    while ( *p != '\0' && !isdigit( (unsigned char) *p ) )
        p++;
    if ( *p == '\0' )
        return false;
    n = strtol( p, &end, 10 );
    *cursor = end;
    if ( n < 0 || n > 99999 )
        return false;
    *value = (int) n;
    return true;
}

static bool read_plan( const OBJ_DATA *obj, HYRULE_PLAN *plan )
{
    const char *text = plan_text( obj );
    const char *cursor;
    int row;
    int col;

    memset( plan, 0, sizeof(*plan) );
    if ( text == NULL )
        return false;

    cursor = text;
    for ( row = 0; row < HYRULE_PLAN_SIDE; row++ )
        for ( col = 0; col < HYRULE_PLAN_SIDE; col++ )
            if ( !plan_number( &cursor, &plan->cell[row][col] ) )
                return false;
    if ( !plan_number( &cursor, &plan->map_room )
    ||   !plan_number( &cursor, &plan->compass_room ) )
        return false;
    while ( plan->cellars < HYRULE_PLAN_CELLARS
    &&      plan_number( &cursor, &plan->cellar[plan->cellars] )
    &&      plan_number( &cursor, &plan->cellar_above[plan->cellars] ) )
        plan->cellars++;
    return true;
}

static bool plan_find( const HYRULE_PLAN *plan, int vnum, int *row, int *col )
{
    int r;
    int c;

    for ( r = 0; r < HYRULE_PLAN_SIDE; r++ )
        for ( c = 0; c < HYRULE_PLAN_SIDE; c++ )
            if ( vnum > 0 && plan->cell[r][c] == vnum )
            {
                *row = r;
                *col = c;
                return true;
            }
    return false;
}

/* What joins two neighbouring rooms on the map: ' ' nothing the player can
   see, '!' the way into the guardian's chamber (its gate), '+' a door shut
   now, or the open way in `open'. Bomb walls stay hidden until bombed, as
   they are on the NES map. */
static char plan_link( const HYRULE_DUNGEON_GATE *gate, int from_vnum,
                       int to_vnum, int door, char open )
{
    ROOM_INDEX_DATA *from;
    EXIT_DATA *pexit;

    if ( from_vnum <= 0 || to_vnum <= 0
    ||   ( from = get_room_index( from_vnum ) ) == NULL
    ||   ( pexit = from->exit[door] ) == NULL
    ||   pexit->u1.to_room == NULL
    ||   pexit->u1.to_room->vnum != to_vnum
    ||   IS_SET( pexit->exit_info, EX_SECRET ) )
        return ' ';

    if ( ( to_vnum == gate->boss_room && from_vnum != gate->goal_room )
    ||   ( from_vnum == gate->boss_room && to_vnum != gate->goal_room ) )
        return gate->boss_need != 0 ? '!' : open;
    if ( IS_SET( pexit->exit_info, EX_CLOSED ) )
        return '+';
    return open;
}

static char plan_symbol( const HYRULE_DUNGEON_GATE *gate,
                         const HYRULE_PLAN *plan, int vnum, int here_vnum )
{
    int i;

    if ( vnum <= 0 )
        return ' ';
    if ( vnum == here_vnum )
        return '@';
    if ( vnum == gate->boss_room )
        return 'B';
    if ( vnum == gate->goal_room )
        return 'T';
    if ( vnum == gate->entrance )
        return 'E';
    if ( vnum == plan->map_room )
        return 'M';
    if ( vnum == plan->compass_room )
        return 'C';
    for ( i = 0; i < plan->cellars; i++ )
        if ( vnum == plan->cellar_above[i] )
            return 'S';
    return 'o';
}

static void trim_right( char *line )
{
    size_t length = strlen( line );

    while ( length > 0 && line[length - 1] == ' ' )
        line[--length] = '\0';
}

static const char *object_name( int vnum )
{
    OBJ_INDEX_DATA *index = get_obj_index( vnum );

    return index != NULL && index->short_descr != NULL
         ? index->short_descr : "something";
}

void hyrule_show_map( CHAR_DATA *ch, OBJ_DATA *obj )
{
    const HYRULE_DUNGEON_GATE *gate;
    HYRULE_PLAN plan;
    char out[MAX_STRING_LENGTH];
    char line[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    int here_vnum = 0;
    bool below = false;
    bool inside;
    int first_row = HYRULE_PLAN_SIDE;
    int last_row = -1;
    int row;
    int col;
    int i;

    gate = hyrule_dungeon_gate( obj->value[4] );
    if ( gate == NULL || !read_plan( obj, &plan ) )
    {
        send_to_char( "The parchment is smudged past reading.\n\r", ch );
        return;
    }

    inside = ch->in_room != NULL
          && ch->in_room->vnum >= gate->first_room
          && ch->in_room->vnum <= gate->last_room;
    if ( inside )
    {
        here_vnum = ch->in_room->vnum;
        if ( !plan_find( &plan, here_vnum, &row, &col ) )
            for ( i = 0; i < plan.cellars; i++ )
                if ( plan.cellar[i] == here_vnum )
                {
                    here_vnum = plan.cellar_above[i];
                    below = true;
                }
    }

    for ( row = 0; row < HYRULE_PLAN_SIDE; row++ )
        for ( col = 0; col < HYRULE_PLAN_SIDE; col++ )
            if ( plan.cell[row][col] > 0 )
            {
                first_row = UMIN( first_row, row );
                last_row = UMAX( last_row, row );
            }

    snprintf( out, sizeof(out), "Level %d: %s -- the dungeon map%s\n\r\n\r",
              gate->level, hyrule_dungeon_titles[gate->level],
              "              N" );
    for ( row = first_row; row <= last_row; row++ )
    {
        int length = 0;

        /* The rooms and what joins them east and west. */
        length = snprintf( line, sizeof(line), "    " );
        for ( col = 0; col < HYRULE_PLAN_SIDE && length < (int) sizeof(line) - 4; col++ )
        {
            int vnum = plan.cell[row][col];

            line[length++] = plan_symbol( gate, &plan, vnum, here_vnum );
            if ( col + 1 < HYRULE_PLAN_SIDE )
                line[length++] = plan_link( gate, vnum, plan.cell[row][col + 1],
                                            DIR_EAST, '-' );
            line[length] = '\0';
        }
        trim_right( line );
        toc_strlcat( out, line, sizeof(out) );
        toc_strlcat( out, "\n\r", sizeof(out) );

        if ( row == last_row )
            break;

        /* What joins them to the row below (south). */
        length = snprintf( line, sizeof(line), "    " );
        for ( col = 0; col < HYRULE_PLAN_SIDE && length < (int) sizeof(line) - 4; col++ )
        {
            line[length++] = plan_link( gate, plan.cell[row][col],
                                        plan.cell[row + 1][col], DIR_SOUTH, '|' );
            if ( col + 1 < HYRULE_PLAN_SIDE )
                line[length++] = ' ';
            line[length] = '\0';
        }
        trim_right( line );
        toc_strlcat( out, line, sizeof(out) );
        toc_strlcat( out, "\n\r", sizeof(out) );
    }

    toc_strlcat( out,
        "\n\r  @ you    E entrance    M map    C compass    S stair to a cellar\n\r"
        "  B the guardian's chamber    T the Triforce chest\n\r"
        "  - | an open way    + a shut door    ! the way to the guardian\n\r",
        sizeof(out) );

    if ( gate->boss_need != 0 )
    {
        snprintf( buf, sizeof(buf),
                  "  ! The way to the guardian needs %s, from Level %d's chest.\n\r",
                  object_name( gate->boss_need ), gate->level - 1 );
        toc_strlcat( out, buf, sizeof(out) );
    }
    toc_strlcat( out,
        "  T The chest is locked; the guardian carries its key.\n\r", sizeof(out) );

    if ( !inside )
        toc_strlcat( out,
            "  You are not in this dungeon, so the map cannot show where you stand.\n\r",
            sizeof(out) );
    else if ( below )
        toc_strlcat( out,
            "  You are in the cellar beneath the room marked @.\n\r", sizeof(out) );

    send_to_char( out, ch );
}

/*
 * The compass's shortest path: breadth first over the dungeon's own exits,
 * stairs and cellars included, never leaving its vnum range. Rooms are
 * indexed by their offset in the range, so no room flags are touched and
 * nothing is allocated.
 */
static int compass_route( const HYRULE_DUNGEON_GATE *gate,
                          ROOM_INDEX_DATA *source, int target_vnum,
                          int *first_door, bool *first_hidden )
{
    int distance[HYRULE_DUNGEON_SPAN];
    int first[HYRULE_DUNGEON_SPAN];
    bool hidden[HYRULE_DUNGEON_SPAN];
    int queue[HYRULE_DUNGEON_SPAN];
    int head = 0;
    int tail = 0;
    int span = gate->last_room - gate->first_room + 1;
    int i;

    *first_door = -1;
    *first_hidden = false;
    if ( span <= 0 || span > HYRULE_DUNGEON_SPAN || source == NULL
    ||   source->vnum < gate->first_room || source->vnum > gate->last_room
    ||   target_vnum < gate->first_room || target_vnum > gate->last_room )
        return -1;

    for ( i = 0; i < span; i++ )
    {
        distance[i] = -1;
        first[i] = -1;
        hidden[i] = false;
    }
    distance[source->vnum - gate->first_room] = 0;
    queue[tail++] = source->vnum - gate->first_room;

    while ( head < tail )
    {
        int at = queue[head++];
        ROOM_INDEX_DATA *room = get_room_index( gate->first_room + at );
        int door;

        if ( room == NULL )
            continue;
        if ( gate->first_room + at == target_vnum )
        {
            *first_door = first[at];
            *first_hidden = hidden[at];
            return distance[at];
        }
        for ( door = 0; door <= DIR_DOWN; door++ )
        {
            EXIT_DATA *pexit = room->exit[door];
            int next;

            if ( pexit == NULL || pexit->u1.to_room == NULL )
                continue;
            next = pexit->u1.to_room->vnum - gate->first_room;
            if ( next < 0 || next >= span || distance[next] >= 0 )
                continue;
            distance[next] = distance[at] + 1;
            first[next] = at == source->vnum - gate->first_room ? door : first[at];
            hidden[next] = at == source->vnum - gate->first_room
                         ? IS_SET( pexit->exit_info, EX_SECRET ) != 0 : hidden[at];
            queue[tail++] = next;
        }
    }
    return -1;
}

static const char *compass_heading( int door )
{
    switch ( door )
    {
    case DIR_UP:   return "upward, to the stair above";
    case DIR_DOWN: return "downward, to the stair below";
    default:       return dir_name[door];
    }
}

void hyrule_show_compass( CHAR_DATA *ch, OBJ_DATA *obj )
{
    const HYRULE_DUNGEON_GATE *gate;
    char buf[MAX_STRING_LENGTH];
    int door;
    bool hidden;
    int to_chest;
    int to_guardian;
    int guardian_door;
    bool guardian_hidden;

    gate = hyrule_dungeon_gate( obj->value[4] );
    if ( gate == NULL )
    {
        send_to_char( "The compass needle hangs loose and lifeless.\n\r", ch );
        return;
    }

    if ( ch->in_room == NULL
    ||   ch->in_room->vnum < gate->first_room
    ||   ch->in_room->vnum > gate->last_room )
    {
        snprintf( buf, sizeof(buf),
                  "The needle circles and will not settle. It knows only the halls of Level %d: %s.\n\r",
                  gate->level, hyrule_dungeon_titles[gate->level] );
        send_to_char( buf, ch );
        return;
    }

    if ( ch->in_room->vnum == gate->goal_room )
    {
        send_to_char( "The needle swings round and settles on the chest beside you: the Triforce is here.\n\r", ch );
        return;
    }

    to_chest = compass_route( gate, ch->in_room, gate->goal_room, &door, &hidden );
    to_guardian = compass_route( gate, ch->in_room, gate->boss_room,
                                 &guardian_door, &guardian_hidden );
    if ( to_chest < 0 || door < 0 )
    {
        send_to_char( "The needle trembles; no way from here leads to the Triforce.\n\r", ch );
        return;
    }

    if ( ch->in_room->vnum == gate->boss_room )
    {
        snprintf( buf, sizeof(buf),
                  "The needle points %s, through the guardian's locked door: the Triforce chest is in the next room.\n\r",
                  compass_heading( door ) );
        send_to_char( buf, ch );
        return;
    }

    if ( hidden )
        snprintf( buf, sizeof(buf),
                  "The needle points %s -- at the bare wall, as though the way lay through the stone.\n\r",
                  compass_heading( door ) );
    else
        snprintf( buf, sizeof(buf), "The needle swings %s.\n\r",
                  compass_heading( door ) );
    send_to_char( buf, ch );

    if ( to_guardian > 0 && to_guardian < to_chest )
        snprintf( buf, sizeof(buf),
                  "The Triforce chest lies %d room%s away, behind the guardian's chamber, which is %d room%s away.\n\r",
                  to_chest, to_chest == 1 ? "" : "s",
                  to_guardian, to_guardian == 1 ? "" : "s" );
    else
        snprintf( buf, sizeof(buf), "The Triforce chest lies %d room%s away.\n\r",
                  to_chest, to_chest == 1 ? "" : "s" );
    send_to_char( buf, ch );
}

/* LOOK, EXAMINE and READ all come here for a dungeon map or compass. */
bool hyrule_look_tool( CHAR_DATA *ch, char *argument )
{
    OBJ_DATA *obj;

    if ( ch == NULL || argument == NULL || argument[0] == '\0' )
        return false;
    obj = get_obj_carry( ch, argument );
    if ( obj == NULL )
        obj = get_obj_here( ch, argument );
    if ( !hyrule_is_dungeon_tool( obj ) )
        return false;

    if ( obj->value[0] == HYRULE_DUNGEON_MAP )
        hyrule_show_map( ch, obj );
    else
        hyrule_show_compass( ch, obj );
    return true;
}

/* --------------------------------------------------------------------
 * What a character has had from Hyrule's secrets.
 *
 * pcdata->hyrule_secrets is one saved word (HyruleSecrets, case 'H' in
 * fread_char), a bit per cave: anything that pays out once is paid once
 * per character, for good, however many times the area resets.
 *
 *   0-13   the fourteen "It's a secret to everybody" money caves
 *   16-20  a Heart Container taken: the four take-any caves, then the dock
 *   21-24  the choice made in each take-any cave (heart or potion)
 *   25-26  the bigger bomb bags of Levels 5 and 7
 * ------------------------------------------------------------------ */

#define SECRET_HEART_FIRST      16
#define SECRET_CHOICE_FIRST     21
#define SECRET_BOMB_BAG_FIRST   25
#define SECRET_MASK             0xffffffffUL

static bool secret_has( const CHAR_DATA *ch, int bit )
{
    return ch->pcdata != NULL && bit >= 0 && bit < 32
        && ( ch->pcdata->hyrule_secrets & ( 1UL << bit ) ) != 0;
}

static void secret_set( CHAR_DATA *ch, int bit )
{
    if ( ch->pcdata == NULL || bit < 0 || bit >= 32 )
        return;
    ch->pcdata->hyrule_secrets |= 1UL << bit;
    ch->pcdata->hyrule_secrets &= SECRET_MASK;
}

static bool is_hyrule_vnum( int vnum )
{
    return IS_HYRULE_ROOM_VNUM( vnum );
}

/* The money caves, in the order of their secret bits. The amounts are the
   NES's; scripts/build_hyrule_area.py writes the caves at these rooms and
   tests/test_hyrule_progression.py holds the two to each other. */
static const struct hyrule_money_cave
{
    int room;
    int rupees;
} hyrule_money_caves[] =
{
    { 30660,  10 }, { 30661,  30 }, { 30662, 100 }, { 30663,  30 },
    { 30664,  10 }, { 30665,  30 }, { 30666,  30 }, { 30667,  30 },
    { 30668,  10 }, { 30669, 100 }, { 30670,  30 }, { 30671,  30 },
    { 30672,  10 }, { 30673, 100 },
};

/* Called whenever a character arrives in a room (move_char and do_enter):
   the moblin of a money cave pays once, as he did on the NES. */
void hyrule_enter_room( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    size_t i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->in_room == NULL
    ||   !is_hyrule_vnum( ch->in_room->vnum ) )
        return;

    for ( i = 0; i < sizeof(hyrule_money_caves) / sizeof(hyrule_money_caves[0]); i++ )
    {
        if ( hyrule_money_caves[i].room != ch->in_room->vnum )
            continue;
        if ( secret_has( ch, (int) i ) )
        {
            send_to_char( "The moblin shrugs and spreads empty paws: you have had your share.\n\r", ch );
            return;
        }
        secret_set( ch, (int) i );
        add_money( ch, hyrule_money_caves[i].rupees );
        snprintf( buf, sizeof(buf),
                  "The moblin grins, presses %d gold into your hand and taps his snout.\n\r",
                  hyrule_money_caves[i].rupees );
        send_to_char( buf, ch );
        act( "The moblin slips $n a handful of gold coins.", ch, NULL, NULL, TO_ROOM );
        save_char_obj( ch );
        return;
    }
}

/* --------------------------------------------------------------------
 * Hearts. The NES counts hearts and the MUD has hit points, so a heart is
 * counted the NES way: three to start, one for each guardian of Levels
 * 1-8 you have defeated (their achievements), and one for each Heart
 * Container taken from a take-any cave or the dock -- sixteen at most.
 * ------------------------------------------------------------------ */

static const char *const hyrule_guardian_keys[8] =
{
    "hyrule-eagle", "hyrule-moon", "hyrule-manji", "hyrule-snake",
    "hyrule-lizard", "hyrule-dragon", "hyrule-demon", "hyrule-lion"
};

int hyrule_hearts( CHAR_DATA *ch )
{
    int hearts = 3;
    int i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return 3;
    for ( i = 0; i < 8; i++ )
        if ( achievement_has_key( ch, hyrule_guardian_keys[i] ) )
            hearts++;
    for ( i = SECRET_HEART_FIRST; i < SECRET_HEART_FIRST + 5; i++ )
        if ( secret_has( ch, i ) )
            hearts++;
    return hearts;
}

void do_hearts( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    int guardians = 0;
    int containers = 0;
    int i;

    UNUSED_PARAM(argument);
    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;
    for ( i = 0; i < 8; i++ )
        if ( achievement_has_key( ch, hyrule_guardian_keys[i] ) )
            guardians++;
    for ( i = SECRET_HEART_FIRST; i < SECRET_HEART_FIRST + 5; i++ )
        if ( secret_has( ch, i ) )
            containers++;
    snprintf( buf, sizeof(buf),
              "You have %d hearts: 3 to start, %d from Hyrule's guardians and %d from\n\r"
              "Heart Containers you took. The White Sword wants 5, the Magical Sword 12.\n\r",
              hyrule_hearts( ch ), guardians, containers );
    send_to_char( buf, ch );
}

/* --------------------------------------------------------------------
 * Gifts that lie on a cave floor: the swords, the Letter, the Power
 * Bracelet, the take-any caves and the dock's Heart Container. GET gives
 * the character a copy and leaves the gift where it is, so nobody takes a
 * cave's prize from everybody else until the next reset.
 *
 * A row with a choice bit is once per character for good: a take-any
 * cave's two offerings share one, so taking either refuses the other. A
 * row without one gives a copy to anybody not already carrying one. A copy
 * is worth nothing to a shop, so no cave is a mine.
 * ------------------------------------------------------------------ */

typedef struct hyrule_claim
{
    int room;
    int obj;
    int heart_bit;      /* a Heart Container: counts as a heart, or -1 */
    int choice_bit;     /* once per character, or -1: one at a time */
    int hearts;         /* hearts needed, or 0 */
} HYRULE_CLAIM;

static const HYRULE_CLAIM hyrule_claims[] =
{
    /* Take any one you want: L8, M3, H5 and P3 on the NES map. */
    { 30654, OBJ_VNUM_HYRULE_HEART_CONTAINER, 16, 21, 0 },
    { 30654, OBJ_VNUM_HYRULE_RED_POTION,      -1, 21, 0 },
    { 30655, OBJ_VNUM_HYRULE_HEART_CONTAINER, 17, 22, 0 },
    { 30655, OBJ_VNUM_HYRULE_RED_POTION,      -1, 22, 0 },
    { 30656, OBJ_VNUM_HYRULE_HEART_CONTAINER, 18, 23, 0 },
    { 30656, OBJ_VNUM_HYRULE_RED_POTION,      -1, 23, 0 },
    { 30657, OBJ_VNUM_HYRULE_HEART_CONTAINER, 19, 24, 0 },
    { 30657, OBJ_VNUM_HYRULE_RED_POTION,      -1, 24, 0 },
    /* The Heart Container on the P6 dock. */
    { 30658, OBJ_VNUM_HYRULE_HEART_CONTAINER, 20, 20, 0 },
    /* "Master using it and you can have this." */
    { 30651, OBJ_VNUM_HYRULE_WHITE_SWORD,     -1, -1, 5 },
    { 30652, OBJ_VNUM_HYRULE_MAGICAL_SWORD,   -1, -1, 12 },
    /* "It's dangerous to go alone! Take this." */
    { 30650, OBJ_VNUM_HYRULE_WOODEN_SWORD,    -1, -1, 0 },
    { 30653, OBJ_VNUM_HYRULE_LETTER,          -1, -1, 0 },
    { 30674, OBJ_VNUM_HYRULE_POWER_BRACELET,  -1, -1, 0 },
};

bool hyrule_claim( CHAR_DATA *ch, OBJ_DATA *obj )
{
    const HYRULE_CLAIM *claim = NULL;
    OBJ_DATA *copy;
    char buf[MAX_STRING_LENGTH];
    size_t i;

    if ( ch == NULL || obj == NULL || obj->in_room == NULL || obj->pIndexData == NULL
    ||   !is_hyrule_vnum( obj->in_room->vnum ) )
        return false;
    for ( i = 0; i < sizeof(hyrule_claims) / sizeof(hyrule_claims[0]); i++ )
        if ( hyrule_claims[i].room == obj->in_room->vnum
        &&   hyrule_claims[i].obj == obj->pIndexData->vnum )
        {
            claim = &hyrule_claims[i];
            break;
        }
    if ( claim == NULL )
        return false;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "You can't take that.\n\r", ch );
        return true;
    }
    if ( claim->hearts > 0 && hyrule_hearts( ch ) < claim->hearts )
    {
        snprintf( buf, sizeof(buf),
                  "The old man shakes his head. \"Master using it and you can have this.\"\n\r"
                  "He wants a hero of %d hearts; you have %d. (See HEARTS.)\n\r",
                  claim->hearts, hyrule_hearts( ch ) );
        send_to_char( buf, ch );
        return true;
    }
    if ( claim->choice_bit >= 0 && secret_has( ch, claim->choice_bit ) )
    {
        send_to_char( claim->heart_bit == claim->choice_bit
            ? "You have already taken this Heart Container; it waits for someone else now.\n\r"
            : "You have already made your choice in this cave. The other gift is not yours to take.\n\r",
            ch );
        return true;
    }
    if ( claim->choice_bit < 0 && hyrule_carries( ch, claim->obj ) )
    {
        act( "You already carry $p; the old man will not give you two.", ch, obj, NULL, TO_CHAR );
        return true;
    }

    copy = create_object( obj->pIndexData, obj->level );
    copy->cost = 0;
    /* One at a time, and yours: the old man refuses a second only while
       you carry the first, so a gift stashed or handed over could be
       claimed again for ever -- Magical Swords and Letters for alts who
       never earned the hearts. NODROP keeps it with whoever claimed it;
       lose it, and he gives you another. */
    if ( claim->choice_bit < 0 )
        SET_BIT( copy->extra_flags, ITEM_NODROP );
    obj_to_char( copy, ch );
    act( "You take $p.", ch, copy, NULL, TO_CHAR );
    act( "$n takes $p.", ch, copy, NULL, TO_ROOM );

    if ( claim->choice_bit >= 0 )
    {
        secret_set( ch, claim->choice_bit );
        if ( claim->heart_bit >= 0 )
            secret_set( ch, claim->heart_bit );
        if ( claim->heart_bit != claim->choice_bit )
            send_to_char( "The old man nods, and the other gift is no longer yours to take.\n\r", ch );
        if ( claim->heart_bit >= 0 )
        {
            snprintf( buf, sizeof(buf), "Your heart swells: you have %d hearts now.\n\r",
                      hyrule_hearts( ch ) );
            send_to_char( buf, ch );
        }
        save_char_obj( ch );
    }
    return true;
}

/* --------------------------------------------------------------------
 * Bombs. A purchase is four, in one object whose value[0] counts them;
 * BOMB uses one. The bag carries eight, and the old men of Levels 5 and 7
 * each sell room for four more (a bigger bomb bag, 100 rupees, once).
 * ------------------------------------------------------------------ */

#define HYRULE_BOMB_BAG_BASE    8
#define HYRULE_BOMB_BAG_STEP    4
#define HYRULE_BOMB_BAG_ROOM_L5 30496
#define HYRULE_BOMB_BAG_ROOM_L7 30539

static bool is_bombs( const OBJ_DATA *obj )
{
    return obj != NULL && obj->pIndexData != NULL
        && obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMBS;
}

/* The first bundle with a bomb in it, in hand or one bag down. */
static OBJ_DATA *find_bombs( CHAR_DATA *ch )
{
    OBJ_DATA *obj;
    OBJ_DATA *inner;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        if ( is_bombs( obj ) && obj->value[0] > 0 )
            return obj;
        if ( obj->item_type != ITEM_CONTAINER )
            continue;
        for ( inner = obj->contains; inner != NULL; inner = inner->next_content )
            if ( is_bombs( inner ) && inner->value[0] > 0 )
                return inner;
    }
    return NULL;
}

/* Every bomb in a list, however deep the bags go. */
static int count_bombs_in( OBJ_DATA *list, int depth )
{
    OBJ_DATA *obj;
    int count = 0;

    if ( depth > 16 )
        return 0;
    for ( obj = list; obj != NULL; obj = obj->next_content )
    {
        if ( is_bombs( obj ) )
            count += UMAX( 0, obj->value[0] );
        if ( obj->contains != NULL )
            count += count_bombs_in( obj->contains, depth + 1 );
    }
    return count;
}

/* What counts against the bag: everything carried, at any depth, and the
   stash. Only hand and one bag down used to count, so a character could
   stash eight, buy eight more, and carry on for good. */
int hyrule_bombs_carried( CHAR_DATA *ch )
{
    int count = count_bombs_in( ch->carrying, 0 );

    if ( !IS_NPC(ch) && ch->pcdata != NULL )
        count += count_bombs_in( ch->pcdata->stash, 0 );
    return count;
}

int hyrule_bomb_capacity( CHAR_DATA *ch )
{
    int capacity = HYRULE_BOMB_BAG_BASE;

    if ( secret_has( ch, SECRET_BOMB_BAG_FIRST ) )
        capacity += HYRULE_BOMB_BAG_STEP;
    if ( secret_has( ch, SECRET_BOMB_BAG_FIRST + 1 ) )
        capacity += HYRULE_BOMB_BAG_STEP;
    return capacity;
}

static void name_bombs( OBJ_DATA *obj )
{
    char buf[MAX_INPUT_LENGTH];
    static const char *const words[] =
        { "no bombs", "a bomb", "two bombs", "three bombs", "four bombs" };

    if ( obj->value[0] >= 0 && obj->value[0] <= 4 )
        toc_strlcpy( buf, words[obj->value[0]], sizeof(buf) );
    else
        snprintf( buf, sizeof(buf), "%d bombs", obj->value[0] );
    free_string( obj->short_descr );
    obj->short_descr = str_dup( buf );
}

/* Uses one bomb; false, and nothing used, when there is none. */
bool hyrule_use_bomb( CHAR_DATA *ch )
{
    OBJ_DATA *bombs = find_bombs( ch );

    if ( bombs == NULL )
        return false;
    if ( --bombs->value[0] <= 0 )
        extract_obj( bombs );
    else
        name_bombs( bombs );
    return true;
}

static int bomb_bag_bit( CHAR_DATA *ch )
{
    if ( ch->in_room == NULL )
        return -1;
    if ( ch->in_room->vnum == HYRULE_BOMB_BAG_ROOM_L5 )
        return SECRET_BOMB_BAG_FIRST;
    if ( ch->in_room->vnum == HYRULE_BOMB_BAG_ROOM_L7 )
        return SECRET_BOMB_BAG_FIRST + 1;
    return -1;
}

/* do_buy asks before it takes the money. */
bool hyrule_buy_refuses( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char buf[MAX_STRING_LENGTH];

    if ( obj == NULL || obj->pIndexData == NULL || IS_NPC(ch) )
        return false;
    if ( obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMBS
    &&   hyrule_bombs_carried( ch ) + obj->value[0] > hyrule_bomb_capacity( ch ) )
    {
        snprintf( buf, sizeof(buf),
                  "Your bomb bag will not take four more: it holds %d, and you carry %d.\n\r",
                  hyrule_bomb_capacity( ch ), hyrule_bombs_carried( ch ) );
        send_to_char( buf, ch );
        return true;
    }
    if ( obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMB_BAG )
    {
        int bit = bomb_bag_bit( ch );

        if ( bit < 0 || secret_has( ch, bit ) )
        {
            send_to_char( "\"You have had your bigger bag from me already,\" the old man says.\n\r", ch );
            return true;
        }
    }
    return false;
}

/* do_buy's last word: a bag becomes room in yours, and four bombs join
   the ones you have. True when obj has been used up and is gone. */
bool hyrule_bought( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *other;

    if ( obj == NULL || obj->pIndexData == NULL || IS_NPC(ch) )
        return false;

    if ( obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMB_BAG )
    {
        int bit = bomb_bag_bit( ch );

        extract_obj( obj );
        secret_set( ch, bit );
        snprintf( buf, sizeof(buf),
                  "The old man stitches the bigger bag into yours. It carries %d bombs now.\n\r",
                  hyrule_bomb_capacity( ch ) );
        send_to_char( buf, ch );
        save_char_obj( ch );
        return true;
    }

    if ( is_bombs( obj ) )
    {
        for ( other = ch->carrying; other != NULL; other = other->next_content )
            if ( other != obj && is_bombs( other ) )
            {
                other->value[0] += obj->value[0];
                name_bombs( other );
                extract_obj( obj );
                return true;
            }
        name_bombs( obj );
    }
    return false;
}

/* BOMB at a creature: fire, one bomb used, a round of lag. Dodongo
   swallows it whole and loses half his health, as on the NES. */
bool hyrule_bomb_creature( CHAR_DATA *ch, CHAR_DATA *victim )
{
    int dam;

    if ( victim == NULL || victim == ch )
        return false;
    if ( hyrule_bombs_carried( ch ) <= 0 )
    {
        send_to_char( "You have no bombs. The arrow shops sell four for 20 gold.\n\r", ch );
        return true;
    }
    if ( is_safe( ch, victim ) )
        return true;

    hyrule_use_bomb( ch );
    WAIT_STATE( ch, PULSE_VIOLENCE );
    if ( IS_NPC(victim) && victim->pIndexData != NULL
    &&   victim->pIndexData->vnum == HYRULE_DODONGO_VNUM )
    {
        act( "You roll a bomb beneath $N. It swallows it -- and the blast tears through its hide!",
             ch, NULL, victim, TO_CHAR );
        act( "$n rolls a bomb beneath $N, which swallows it. The explosion fills the chamber!",
             ch, NULL, victim, TO_ROOM );
        damage( ch, victim, UMAX( 1, victim->max_hit / 2 ), TYPE_UNDEFINED, DAM_FIRE );
        return true;
    }

    act( "You light a bomb and toss it at $N. It goes off with a roar!", ch, NULL, victim, TO_CHAR );
    act( "$n tosses a lit bomb at $N, and it goes off with a roar!", ch, NULL, victim, TO_NOTVICT );
    act( "$n tosses a lit bomb at you, and it goes off with a roar!", ch, NULL, victim, TO_VICT );
    dam = ch->level + dice( 2, UMAX( 4, ch->level ) );
    damage( ch, victim, dam, TYPE_UNDEFINED, DAM_FIRE );
    return true;
}

/* --------------------------------------------------------------------
 * The bow and the boomerangs: SHOOT with one wielded.
 * ------------------------------------------------------------------ */

static bool hyrule_kind_is( const CHAR_DATA *victim, int kind )
{
    int vnum;

    if ( victim == NULL || !IS_NPC(victim) || victim->pIndexData == NULL )
        return false;
    vnum = victim->pIndexData->vnum;
    return vnum >= HYRULE_TIER_FIRST_VNUM && vnum <= HYRULE_TIER_LAST_VNUM
        && HYRULE_KIND_FROM_TIER( vnum ) == kind;
}

static bool is_hyrule_enemy( const CHAR_DATA *victim )
{
    return victim != NULL && IS_NPC(victim) && victim->pIndexData != NULL
        && victim->pIndexData->vnum >= HYRULE_TIER_FIRST_VNUM
        && victim->pIndexData->vnum <= HYRULE_TIER_LAST_VNUM;
}

/* Whether victim is still standing in ch's room: the safe question after
   anything that may have killed it, since a dead mobile is freed. */
static bool still_here( CHAR_DATA *ch, CHAR_DATA *victim )
{
    CHAR_DATA *here;

    if ( ch == NULL || ch->in_room == NULL || victim == NULL )
        return false;
    for ( here = ch->in_room->people; here != NULL; here = here->next_in_room )
        if ( here == victim )
            return true;
    return false;
}

static bool shot_refused( CHAR_DATA *ch, CHAR_DATA *victim, const char *verb )
{
    char buf[MAX_STRING_LENGTH];

    if ( victim == NULL )
    {
        snprintf( buf, sizeof(buf), "%s at whom? They must be here with you.\n\r", verb );
        send_to_char( buf, ch );
        return true;
    }
    if ( victim == ch )
    {
        send_to_char( "Not at yourself.\n\r", ch );
        return true;
    }
    if ( is_safe( ch, victim ) )
        return true;
    if ( victim->fighting != NULL && victim->fighting != ch
    &&   !is_same_group( ch, victim->fighting ) )
    {
        send_to_char( "Kill stealing is not permitted.\n\r", ch );
        return true;
    }
    return false;
}

static void calm_stun( CHAR_DATA *victim )
{
    AFFECT_DATA af;
    int sn = skill_lookup( "calm" );

    if ( sn < 0 || IS_AFFECTED(victim, AFF_CALM) )
        return;
    stop_fighting( victim, true );
    af.type      = (sh_int) sn;
    af.level     = victim->level;
    af.duration  = 0;
    af.location  = APPLY_NONE;
    af.modifier  = 0;
    af.bitvector = AFF_CALM;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
}

/*
 * do_shoot asks this first. True when it was a Hyrule bow or boomerang
 * and the shot has been dealt with, whatever came of it.
 *
 * The bow needs no Archery: it shoots an enemy in the room for its dice,
 * your damroll and half your level, and each arrow costs a rupee, as on
 * the NES. A pols voice dies to one arrow. Gohma's finishing blow is the
 * bow's already (damage() in fight.c).
 *
 * A boomerang is thrown and comes back: light damage, and the enemy is
 * stunned out of the fight until it is struck again; a keese or a gel dies
 * outright. A guardian is too big to stun.
 */
bool hyrule_shoot( CHAR_DATA *ch, OBJ_DATA *weapon, char *argument )
{
    CHAR_DATA *victim;
    int vnum;
    int dam;

    if ( weapon == NULL || weapon->pIndexData == NULL )
        return false;
    vnum = weapon->pIndexData->vnum;
    if ( vnum != OBJ_VNUM_HYRULE_BOW && vnum != OBJ_VNUM_HYRULE_BOOMERANG
    &&   vnum != OBJ_VNUM_HYRULE_MAGICAL_BOOMERANG )
        return false;

    victim = argument[0] != '\0' ? get_char_room( ch, argument ) : ch->fighting;

    if ( vnum == OBJ_VNUM_HYRULE_BOW )
    {
        if ( !hyrule_carries( ch, OBJ_VNUM_HYRULE_ARROWS ) )
        {
            send_to_char( "You have no arrows. The arrow shops sell a quiver for 80 gold.\n\r", ch );
            return true;
        }
        if ( shot_refused( ch, victim, "Shoot" ) )
            return true;
        if ( !has_enough_gold( ch, 1 ) )
        {
            send_to_char( "Each arrow costs a gold coin, and you have none.\n\r", ch );
            return true;
        }
        add_money( ch, -1 );
        check_killer( ch, victim );
        WAIT_STATE( ch, PULSE_VIOLENCE );
        act( "You draw, aim at $N and let an arrow fly.", ch, NULL, victim, TO_CHAR );
        act( "$n draws, aims at $N and lets an arrow fly.", ch, NULL, victim, TO_NOTVICT );
        act( "$n draws and looses an arrow at you!", ch, NULL, victim, TO_VICT );
        if ( hyrule_kind_is( victim, HYRULE_KIND_POLS_VOICE ) )
        {
            act( "$N shrieks at the arrow's whistle and bursts like a bubble!",
                 ch, NULL, victim, TO_CHAR );
            act( "$N shrieks at the arrow's whistle and bursts like a bubble!",
                 ch, NULL, victim, TO_NOTVICT );
            damage( ch, victim, victim->hit + 10, gsn_archery, DAM_PIERCE );
            return true;
        }
        dam = dice( weapon->value[1], weapon->value[2] ) + GET_DAMROLL(ch) + ch->level / 2;
        damage( ch, victim, UMAX( 1, dam ), gsn_archery, DAM_PIERCE );
        return true;
    }

    if ( shot_refused( ch, victim, "Throw" ) )
        return true;
    check_killer( ch, victim );
    WAIT_STATE( ch, PULSE_VIOLENCE );
    act( "You hurl $p at $N; it whirls out and back to your hand.", ch, weapon, victim, TO_CHAR );
    act( "$n hurls $p at $N, and it whirls back to $s hand.", ch, weapon, victim, TO_NOTVICT );
    act( "$n hurls $p at you!", ch, weapon, victim, TO_VICT );
    if ( hyrule_kind_is( victim, HYRULE_KIND_KEESE ) || hyrule_kind_is( victim, HYRULE_KIND_GEL ) )
    {
        damage( ch, victim, victim->hit + 10, TYPE_UNDEFINED, DAM_BASH );
        return true;
    }
    dam = dice( weapon->value[1], weapon->value[2] ) + ch->level / 4
        + ( vnum == OBJ_VNUM_HYRULE_MAGICAL_BOOMERANG ? ch->level / 4 : 0 );
    damage( ch, victim, UMAX( 1, dam ), TYPE_UNDEFINED, DAM_BASH );
    /* The blow may have killed it, and a dead mobile is freed: look for it
       in the room again rather than trust the pointer. */
    if ( still_here( ch, victim ) && victim->position > POS_STUNNED
    &&   is_hyrule_enemy( victim ) && !IS_AFFECTED(victim, AFF_CALM) )
    {
        calm_stun( victim );
        act( "$N reels, stunned, and forgets the fight.", ch, NULL, victim, TO_CHAR );
        act( "$N reels, stunned, and forgets the fight.", ch, NULL, victim, TO_NOTVICT );
    }
    return true;
}

/* --------------------------------------------------------------------
 * Candles, bait, the Recorder, the potions and the Rod.
 * ------------------------------------------------------------------ */

/* BURN at a creature: a lick of flame from the candle in the light slot.
   The Red Candle burns hotter, and a gibdo's wrappings catch at once. */
void hyrule_burn_creature( CHAR_DATA *ch, CHAR_DATA *victim, OBJ_DATA *candle )
{
    bool red = candle->pIndexData != NULL
            && candle->pIndexData->vnum == OBJ_VNUM_HYRULE_RED_CANDLE;
    int dam;

    if ( victim == ch || is_safe( ch, victim ) )
        return;
    check_killer( ch, victim );
    WAIT_STATE( ch, PULSE_VIOLENCE );
    act( "You thrust $p at $N and a tongue of flame leaps from it!", ch, candle, victim, TO_CHAR );
    act( "$n thrusts $p at $N, and a tongue of flame leaps out!", ch, candle, victim, TO_NOTVICT );
    act( "$n thrusts $p at you, and fire leaps out!", ch, candle, victim, TO_VICT );
    dam = red ? ch->level + dice( 3, 8 ) : ch->level / 2 + dice( 2, 6 );
    if ( hyrule_kind_is( victim, HYRULE_KIND_GIBDO ) )
        dam *= 2;
    damage( ch, victim, UMAX( 1, dam ), TYPE_UNDEFINED, DAM_FIRE );
}

/* FEED BAIT with no hungry Goriya about: set it down, and the room's
   enemies forget the fight and turn to the smell. The bait is kept, as on
   the NES; a guardian is not fooled. */
bool hyrule_set_bait( CHAR_DATA *ch, OBJ_DATA *bait )
{
    CHAR_DATA *victim;
    bool calmed = false;

    if ( ch->in_room == NULL || !is_hyrule_vnum( ch->in_room->vnum ) )
    {
        send_to_char( "Nothing here is hungry for it.\n\r", ch );
        return false;
    }
    WAIT_STATE( ch, 2 * PULSE_VIOLENCE );
    act( "You set $p down and step back.", ch, bait, NULL, TO_CHAR );
    act( "$n sets $p down and steps back.", ch, bait, NULL, TO_ROOM );
    for ( victim = ch->in_room->people; victim != NULL; victim = victim->next_in_room )
    {
        if ( !is_hyrule_enemy( victim ) || IS_AFFECTED(victim, AFF_CALM) )
            continue;
        calm_stun( victim );
        act( "$n sniffs, forgets you, and noses at the bait.", victim, NULL, NULL, TO_ROOM );
        calmed = true;
    }
    if ( !calmed )
        send_to_char( "Nothing here takes any notice of it.\n\r", ch );
    act( "You pick $p up again.", ch, bait, NULL, TO_CHAR );
    return calmed;
}

/* Where the Recorder's whirlwind sets you down: each dungeon's screen. */
static const int hyrule_dungeon_screens[9] =
{
    30271, 30276, 30205, 30253, 30323, 30282, 30250, 30229, 30317
};

/*
 * The Recorder with no lake to drain. It shrinks every digdogger in the
 * room to a third of its health, once; and on the overworld its whirlwind
 * carries you to the next dungeon, in order, whose Triforce piece you
 * carry. True when the tune did something.
 */
bool hyrule_play_recorder( CHAR_DATA *ch )
{
    CHAR_DATA *victim;
    ROOM_INDEX_DATA *to_room;
    bool shrank = false;
    int here = -1;
    int step;
    int i;

    for ( victim = ch->in_room->people; victim != NULL; victim = victim->next_in_room )
    {
        if ( !hyrule_kind_is( victim, HYRULE_KIND_DIGDOGGER )
        ||   victim->hit <= victim->max_hit / 3 )
            continue;
        victim->hit = UMAX( 1, victim->max_hit / 3 );
        act( "$n shudders at the melody and shrinks to a third of its size!",
             victim, NULL, NULL, TO_ROOM );
        shrank = true;
    }
    if ( shrank )
        return true;

    if ( ch->in_room->vnum < HYRULE_OVERWORLD_FIRST
    ||   ch->in_room->vnum > HYRULE_OVERWORLD_LAST )
        return false;
    if ( ch->fighting != NULL )
    {
        send_to_char( "A whirlwind will not come for someone in the middle of a fight.\n\r", ch );
        return true;
    }

    for ( i = 0; i < 9; i++ )
        if ( hyrule_dungeon_screens[i] == ch->in_room->vnum )
            here = i;
    for ( step = 1; step <= 9; step++ )
    {
        i = ( here + step + 9 ) % 9;
        if ( !hyrule_carries( ch, HYRULE_PIECE_VNUM( i + 1 ) ) )
            continue;
        if ( ( to_room = get_room_index( hyrule_dungeon_screens[i] ) ) == NULL
        ||   to_room == ch->in_room )
            break;
        act( "A whirlwind spins down out of a clear sky and snatches you up!", ch, NULL, NULL, TO_CHAR );
        act( "A whirlwind spins down, snatches $n up and is gone.", ch, NULL, NULL, TO_ROOM );
        char_from_room( ch );
        char_to_room( ch, to_room );
        act( "A whirlwind spins down and sets $n on the grass.", ch, NULL, NULL, TO_ROOM );
        do_look( ch, "auto" );
        WAIT_STATE( ch, PULSE_VIOLENCE );
        return true;
    }
    send_to_char( "The wind stirs, then dies. It knows the way only to dungeons whose Triforce piece you carry.\n\r", ch );
    return true;
}

/* The red 2nd Potion turns blue when drunk, as on the NES. */
void hyrule_after_quaff( CHAR_DATA *ch, int vnum )
{
    OBJ_INDEX_DATA *blue;
    OBJ_DATA *potion;

    if ( vnum != OBJ_VNUM_HYRULE_RED_POTION || ch == NULL || ch->in_room == NULL
    ||   ( blue = get_obj_index( OBJ_VNUM_HYRULE_BLUE_POTION ) ) == NULL )
        return;
    potion = create_object( blue, blue->level );
    potion->cost = 0;
    obj_to_char( potion, ch );
    act( "What is left in the bottle turns blue: $p.", ch, potion, NULL, TO_CHAR );
}

bool hyrule_rod_is_endless( const OBJ_DATA *wand )
{
    return wand != NULL && wand->pIndexData != NULL
        && wand->pIndexData->vnum == OBJ_VNUM_HYRULE_MAGICAL_ROD;
}

/* After the Rod's blast: with the Magic Book carried it bursts into flame
   as well. victim may not have survived the blast, so it is looked for in
   the room again rather than trusted. */
void hyrule_after_zap( CHAR_DATA *ch, CHAR_DATA *victim, OBJ_DATA *wand )
{
    if ( !hyrule_rod_is_endless( wand ) || victim == NULL || ch->in_room == NULL
    ||   !hyrule_carries( ch, OBJ_VNUM_HYRULE_MAGIC_BOOK ) )
        return;
    if ( !still_here( ch, victim ) || victim == ch || is_safe( ch, victim ) )
        return;
    act( "The Magic Book flares, and the Rod's blast bursts into flame around $N!",
         ch, NULL, victim, TO_CHAR );
    act( "A burst of flame from $n's rod engulfs $N!", ch, NULL, victim, TO_NOTVICT );
    act( "A burst of flame from $n's rod engulfs you!", ch, NULL, victim, TO_VICT );
    damage( ch, victim, dice( 4, 10 ) + ch->level, TYPE_UNDEFINED, DAM_FIRE );
}

/* --------------------------------------------------------------------
 * The old women who sell a hint. GIVE her rupees.
 * ------------------------------------------------------------------ */

#define HYRULE_HINT_ROOM_WOODS      30330   /* A8 on the NES map */
#define HYRULE_HINT_ROOM_WATERFALL  30331   /* K2, behind the waterfall */

/* do_give asks before gold changes hands. True when she has dealt with it
   (whether or not she kept the money). */
bool hyrule_paid_to_talk( CHAR_DATA *ch, CHAR_DATA *victim, int amount )
{
    const char *answer = NULL;

    if ( IS_NPC(ch) || victim == NULL || !IS_NPC(victim) || ch->in_room == NULL )
        return false;

    if ( ch->in_room->vnum == HYRULE_HINT_ROOM_WOODS )
    {
        if ( amount == 10 )
            answer = "\"This ain't enough to talk.\" She pockets it all the same.";
        else if ( amount == 30 )
            answer = "\"Go north, west, south, west to the forest of maze.\"";
        else if ( amount == 50 )
            answer = "\"Boy, you're rich!\" And that is all she says.";
    }
    else if ( ch->in_room->vnum == HYRULE_HINT_ROOM_WATERFALL )
    {
        if ( amount == 5 || amount == 10 )
            answer = "\"This ain't enough to talk.\" She pockets it all the same.";
        else if ( amount == 20 )
            answer = "\"Go up, up, the mountain ahead.\"";
    }
    else
        return false;

    if ( answer == NULL )
    {
        act( "$N pushes the coins back at you. \"Pay me and I'll talk.\"", ch, NULL, victim, TO_CHAR );
        send_to_char( ch->in_room->vnum == HYRULE_HINT_ROOM_WOODS
                      ? "She will take 10, 30 or 50 gold.\n\r"
                      : "She will take 5, 10 or 20 gold.\n\r", ch );
        return true;
    }

    adjust_coin_balance( ch, -amount, TYPE_GOLD );
    act( "You pay $N.", ch, NULL, victim, TO_CHAR );
    act( "$n pays $N.", ch, NULL, victim, TO_ROOM );
    act( answer, ch, NULL, victim, TO_CHAR );
    return true;
}

/* The potion shops sell only to someone carrying Princess Zelda's Letter. */
bool hyrule_keeper_refuses( CHAR_DATA *keeper, CHAR_DATA *ch )
{
    if ( IS_NPC(ch) || keeper == NULL || keeper->in_room == NULL
    ||   keeper->in_room->vnum < HYRULE_POTION_SHOP_FIRST
    ||   keeper->in_room->vnum > HYRULE_POTION_SHOP_LAST
    ||   hyrule_carries( ch, OBJ_VNUM_HYRULE_LETTER ) )
        return false;
    act( "$n looks you over for a royal seal. \"Show me the Princess's letter first.\"",
         keeper, NULL, ch, TO_VICT );
    return true;
}

/* --------------------------------------------------------------------
 * What a guardian leaves besides its key, Heart Container, weapon and
 * Heart Guard: two of its five drop-table pieces, at random. The pieces
 * are written by scripts/build_hyrule_area.py at
 * OBJ_VNUM_HYRULE_BOSS_DROP_FIRST + (level - 1) * 5 + n.
 * ------------------------------------------------------------------ */

static const int hyrule_guardian_vnums[9] =
{
    30222, 30218, 30305, 30307, 30309, 30223, 30314, 30316, 30225
};

void hyrule_boss_drops( CHAR_DATA *boss, OBJ_DATA *corpse )
{
    OBJ_INDEX_DATA *index;
    int picked[HYRULE_BOSS_DROPS_PER_KILL];
    int level = 0;
    int count = 0;
    int i;

    if ( boss == NULL || corpse == NULL || !IS_NPC(boss) || boss->pIndexData == NULL )
        return;
    for ( i = 0; i < 9; i++ )
        if ( hyrule_guardian_vnums[i] == boss->pIndexData->vnum )
            level = i + 1;
    if ( level == 0 )
        return;

    while ( count < HYRULE_BOSS_DROPS_PER_KILL )
    {
        int n = number_range( 0, HYRULE_BOSS_DROPS_PER_GUARDIAN - 1 );
        bool seen = false;

        for ( i = 0; i < count; i++ )
            if ( picked[i] == n )
                seen = true;
        if ( seen )
            continue;
        picked[count++] = n;
        index = get_obj_index( OBJ_VNUM_HYRULE_BOSS_DROP_FIRST
                               + ( level - 1 ) * HYRULE_BOSS_DROPS_PER_GUARDIAN + n );
        if ( index == NULL )
        {
            bug( "hyrule_boss_drops: missing drop for Level %d.", level );
            continue;
        }
        obj_to_obj( create_object( index, index->level ), corpse );
    }
}

/* --------------------------------------------------------------------
 * The tenth enemy has the bomb: ten Hyrule enemies killed in a row
 * without a wound, and the tenth leaves you a bomb (Level 8's old man).
 * ------------------------------------------------------------------ */

void hyrule_note_kill( CHAR_DATA *ch, CHAR_DATA *victim )
{
    OBJ_INDEX_DATA *index;
    OBJ_DATA *bomb;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || !is_hyrule_enemy( victim ) )
        return;
    if ( ++ch->pcdata->hyrule_streak < 10 )
        return;
    ch->pcdata->hyrule_streak = 0;
    if ( hyrule_bombs_carried( ch ) >= hyrule_bomb_capacity( ch )
    ||   ( index = get_obj_index( OBJ_VNUM_HYRULE_BOMBS ) ) == NULL )
        return;
    bomb = create_object( index, 0 );
    bomb->value[0] = 1;
    bomb->cost = 0;
    obj_to_char( bomb, ch );
    if ( !hyrule_bought( ch, bomb ) )
        name_bombs( bomb );
    send_to_char( "Ten foes in a row without a scratch: the tenth leaves you a bomb.\n\r", ch );
}

void hyrule_note_wound( CHAR_DATA *victim )
{
    if ( victim != NULL && !IS_NPC(victim) && victim->pcdata != NULL )
        victim->pcdata->hyrule_streak = 0;
}

/* --------------------------------------------------------------------
 * The fountain fairies (spec_hyrule_fairy in special.c calls this).
 * ------------------------------------------------------------------ */

bool hyrule_fairy_restores( CHAR_DATA *fairy )
{
    CHAR_DATA *ch;
    bool healed = false;

    if ( fairy == NULL || fairy->in_room == NULL )
        return false;
    for ( ch = fairy->in_room->people; ch != NULL; ch = ch->next_in_room )
    {
        if ( IS_NPC(ch) || ch->fighting != NULL
        || ( ch->hit >= ch->max_hit && ch->mana >= ch->max_mana && ch->move >= ch->max_move ) )
            continue;
        ch->hit  = UMAX( ch->hit, ch->max_hit );
        ch->mana = UMAX( ch->mana, ch->max_mana );
        ch->move = UMAX( ch->move, ch->max_move );
        update_pos( ch );
        act( "$n circles you in a ring of light, and every wound closes.", fairy, NULL, ch, TO_VICT );
        act( "$n circles $N in a ring of light.", fairy, NULL, ch, TO_NOTVICT );
        healed = true;
    }
    return healed;
}
