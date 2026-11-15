/*
 * hunting.c -- HUNTING: creatures worth hunting at a level (2026-11-15).
 *
 * A read-only view a player asks for. It names a few creatures to hunt at
 * their level (or a level they name), each in a different area and with
 * the WALKTO that reaches it, so a level's players are spread over several
 * choices rather than sent to the same few rooms.
 *
 * Where players near that level have killed enough to measure, the figures
 * are theirs: the dashboard writes area/hunting.txt from its leveling guide
 * (webadmin/hunting.py), numbers only -- level, creature, experience an
 * hour, seconds a kill, how often it ended in a flee or a death -- and only
 * for creatures measured from at least three characters; nothing in it
 * names a player or a room. Where there is no such row (no dashboard, a new
 * world, a quiet level), it estimates from the world itself: creatures a
 * reset places near the level, in areas WALKTO publishes, one an area.
 *
 * It keeps no state but a cache of the file, reread when it changes, and
 * writes nothing.
 */
#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <sys/stat.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include "merc.h"
#include "interp.h"
#include "dstring.h"
#include "numparse.h"

extern AREA_DATA *area_first;

#define HUNTING_FILE       "hunting.txt"
#define HUNTING_ROWS_MAX   1200       /* 59 levels of 5, with room to spare */
#define HUNTING_SHOWN      5          /* suggestions a view (one screen) */
#define HUNTING_LEVEL_MAX  59         /* mortal levels */
#define HUNTING_RISKY      150        /* permille of fights fled or died in */
#define HUNTING_BELOW      2          /* the estimate's band about a level */
#define HUNTING_ABOVE      3

typedef struct
{
    int  level;
    int  vnum;
    bool measured;
    int  xp_hour;
    int  seconds;
    int  risk;          /* permille, -1 unknown */
    bool aggressive;
    char area_file[64];
} HUNT_ROW;

static HUNT_ROW hunt_rows[HUNTING_ROWS_MAX];
static int      hunt_count;
static time_t   hunt_mtime;
static off_t    hunt_size = -1;

/* A row's area file: letters, digits, '.', '_' and '-', ending ".are". */
static bool hunt_area_word( const char *word )
{
    size_t len = strlen( word );
    const char *p;

    if ( len < 5 || len >= sizeof(hunt_rows[0].area_file)
    ||   str_cmp( word + len - 4, ".are" ) )
        return false;
    for ( p = word; *p != '\0'; p++ )
        if ( !isalnum( (unsigned char) *p ) && *p != '.' && *p != '_' && *p != '-' )
            return false;
    return true;
}

/* One line: eight words, every number checked; anything else is skipped. */
static bool hunt_parse( const char *line, HUNT_ROW *row )
{
    char w[8][64];
    int n = 0, measured_letter;
    const char *p = line;

    while ( n < 8 )
    {
        size_t len = 0;

        while ( *p == ' ' || *p == '\t' )
            p++;
        if ( *p == '\0' || *p == '\n' || *p == '\r' )
            break;
        while ( *p != '\0' && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r' )
        {
            if ( len + 1 >= sizeof(w[n]) )
                return false;
            w[n][len++] = *p++;
        }
        w[n][len] = '\0';
        n++;
    }
    while ( *p == ' ' || *p == '\t' )
        p++;
    if ( n != 8 || ( *p != '\0' && *p != '\n' && *p != '\r' ) )
        return false;
    measured_letter = w[2][0];
    if ( w[2][1] != '\0' || ( measured_letter != 'M' && measured_letter != 'E' ) )
        return false;
    if ( !parse_int( w[0], 1, HUNTING_LEVEL_MAX, &row->level )
    ||   !parse_int( w[1], 1, MAX_VNUM, &row->vnum )
    ||   !parse_int( w[3], 0, 9999999, &row->xp_hour )
    ||   !parse_int( w[4], 0, 9999, &row->seconds )
    ||   !parse_int( w[5], -1, 1000, &row->risk )
    ||   ( strcmp( w[6], "0" ) && strcmp( w[6], "1" ) )
    ||   !hunt_area_word( w[7] ) )
        return false;
    row->measured = measured_letter == 'M';
    row->aggressive = w[6][0] == '1';
    toc_strlcpy( row->area_file, w[7], sizeof(row->area_file) );
    return true;
}

/* Read the file again when it has changed; keep nothing when it is gone. */
static void hunt_load( void )
{
    struct stat st;
    FILE *fp;
    char line[256];

    if ( stat( HUNTING_FILE, &st ) != 0 )
    {
        hunt_count = 0;
        hunt_size = -1;
        return;
    }
    if ( st.st_mtime == hunt_mtime && st.st_size == hunt_size )
        return;
    hunt_count = 0;
    hunt_mtime = st.st_mtime;
    hunt_size = st.st_size;
    if ( ( fp = fopen( HUNTING_FILE, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        size_t len = strlen( line );

        /* A line longer than the buffer is no row: drain and skip it. */
        if ( len > 0 && line[len - 1] != '\n' && !feof( fp ) )
        {
            int c;

            while ( ( c = fgetc( fp ) ) != EOF && c != '\n' )
                ;
            continue;
        }
        if ( line[0] == '#' || hunt_count >= HUNTING_ROWS_MAX )
            continue;
        if ( hunt_parse( line, &hunt_rows[hunt_count] ) )
            hunt_count++;
    }
    fclose( fp );
}

/* A creature anybody may hunt: no shopkeeper, trainer, healer, questmaster
   or creature nothing may kill, no wanderer of the rare kind, not the yard's
   dummy, and placed somewhere a player may walk to (checked by the room). */
static bool hunt_prey( MOB_INDEX_DATA *mob )
{
    if ( mob == NULL || mob->pShop != NULL )
        return false;
    if ( IS_SET(mob->act, ACT_TRAIN) || IS_SET(mob->act, ACT_PRACTICE)
    ||   IS_SET(mob->act, ACT_IS_HEALER) || IS_SET(mob->act, ACT_GAIN)
    ||   IS_SET(mob->act, ACT_QUESTM) || IS_SET(mob->act, ACT_NOKILL)
    ||   IS_SET(mob->act, ACT_PET) )
        return false;
    return mob->vnum != MOB_VNUM_TRAINING_DUMMY && mob->vnum != MOB_VNUM_BLACK_MARKET
        && mob->vnum != MOB_VNUM_TREASURE_GOBLIN && mob->vnum != MOB_VNUM_CARTOGRAPHER;
}

/* The area a row names, by the file the world loaded it from (a seasonal
   copy answers to its base's name). */
static AREA_DATA *hunt_area( const char *file )
{
    AREA_DATA *area;

    for ( area = area_first; area != NULL; area = area->next )
        if ( area->file_name != NULL
        &&   ( !str_cmp( area->file_name, file )
            || !str_cmp( season_base_area( area->file_name ), file ) ) )
            return area;
    return NULL;
}

/* A room a reset places this creature in, inside the area: one a player
   may stand in (not a death trap, not Hyrule, not a safe room). */
static ROOM_INDEX_DATA *hunt_placed( AREA_DATA *area, int vnum )
{
    RESET_DATA *r;
    ROOM_INDEX_DATA *room;

    for ( r = area->reset_first; r != NULL; r = r->next )
    {
        if ( r->command != 'M' || r->arg1 != vnum )
            continue;
        if ( ( room = get_room_index( r->arg3 ) ) == NULL || room->area != area
        ||   IS_SET(room->room_flags, ROOM_DT) || IS_SET(room->room_flags, ROOM_SAFE)
        ||   walkto_room_is_hyrule( room ) )
            continue;
        return room;
    }
    return NULL;
}

/* Copy text without colour tokens, at most size-1 bytes. */
static void hunt_plain( char *out, size_t size, const char *text )
{
    size_t n = 0;
    const char *p;

    for ( p = text ? text : ""; *p != '\0' && n + 1 < size; p++ )
    {
        if ( color_token_prefix( *p ) && isxdigit( (unsigned char) p[1] )
        &&   isxdigit( (unsigned char) p[2] ) )
        {
            p += 2;
            continue;
        }
        out[n++] = ( *p == '\n' || *p == '\r' ) ? ' ' : *p;
    }
    out[n] = '\0';
}

typedef struct
{
    MOB_INDEX_DATA *mob;
    AREA_DATA *area;
    char walk[ADVENTURE_PLACE_LEN];
    bool walkable;
    const HUNT_ROW *row;       /* NULL for an estimate */
} HUNT_PICK;

/* Whether the area may be suggested, and its WALKTO: a name WALKTO finds
   it by alone. Dresden, where the game starts, has no route of its own and
   is named without one. Cheap; hunt_reachable is the route search. */
static bool hunt_area_named( AREA_DATA *area, HUNT_PICK *pick )
{
    pick->walkable = walkto_area_walk_name( area, pick->walk, sizeof(pick->walk) );
    if ( pick->walkable )
        return true;
    return area->file_name != NULL
        && !str_cmp( season_base_area( area->file_name ), "dresden.are" );
}

/* Whether WALKTO could walk this character there now (the town always). */
static bool hunt_reachable( CHAR_DATA *ch, HUNT_PICK *pick )
{
    return !pick->walkable || walkto_area_reachable( ch, pick->area );
}

static bool hunt_area_taken( HUNT_PICK *picks, int n, AREA_DATA *area )
{
    int i;

    for ( i = 0; i < n; i++ )
        if ( picks[i].area == area )
            return true;
    return false;
}

/* The measured suggestions for a level, best first as written. */
static int hunt_measured( CHAR_DATA *ch, int level, HUNT_PICK *picks )
{
    int i, n = 0;

    hunt_load();
    for ( i = 0; i < hunt_count && n < HUNTING_SHOWN; i++ )
    {
        const HUNT_ROW *row = &hunt_rows[i];
        HUNT_PICK *pk = &picks[n];

        if ( row->level != level )
            continue;
        if ( ( pk->mob = get_mob_index( row->vnum ) ) == NULL || !hunt_prey( pk->mob )
        ||   ( pk->area = hunt_area( row->area_file ) ) == NULL
        ||   hunt_area_taken( picks, n, pk->area )
        ||   hunt_placed( pk->area, row->vnum ) == NULL
        ||   !hunt_area_named( pk->area, pk ) || !hunt_reachable( ch, pk ) )
            continue;
        pk->row = row;
        n++;
    }
    return n;
}

#define HUNT_AREAS_MAX 512

/* An estimate from the world: per area, the placed creature nearest the
   level within the band; areas nearest the level first, each one WALKTO
   could walk the character to now (searched only for those shown). */
static int hunt_estimated( CHAR_DATA *ch, int level, HUNT_PICK *picks, int n )
{
    static HUNT_PICK cand[HUNT_AREAS_MAX];
    static int gap[HUNT_AREAS_MAX];
    AREA_DATA *area;
    int found = 0, i;

    for ( area = area_first; area != NULL && found < HUNT_AREAS_MAX; area = area->next )
    {
        RESET_DATA *r;
        MOB_INDEX_DATA *best = NULL;
        HUNT_PICK pk;
        int best_gap = 1000;

        if ( hunt_area_taken( picks, n, area ) || !hunt_area_named( area, &pk ) )
            continue;
        for ( r = area->reset_first; r != NULL; r = r->next )
        {
            MOB_INDEX_DATA *mob;
            int g;

            if ( r->command != 'M' || ( mob = get_mob_index( r->arg1 ) ) == NULL
            ||   !hunt_prey( mob )
            ||   mob->level < level - HUNTING_BELOW || mob->level > level + HUNTING_ABOVE
            ||   hunt_placed( area, mob->vnum ) == NULL )
                continue;
            g = mob->level >= level ? mob->level - level : level - mob->level;
            if ( best == NULL || g < best_gap || ( g == best_gap && mob->vnum < best->vnum ) )
            {
                best = mob;
                best_gap = g;
            }
        }
        if ( best == NULL )
            continue;
        pk.mob = best;
        pk.area = area;
        pk.row = NULL;
        /* Nearest first, stable: insert in order. */
        for ( i = found; i > 0 && gap[i - 1] > best_gap; i-- )
        {
            cand[i] = cand[i - 1];
            gap[i] = gap[i - 1];
        }
        cand[i] = pk;
        gap[i] = best_gap;
        found++;
    }
    for ( i = 0; i < found && n < HUNTING_SHOWN; i++ )
        if ( hunt_reachable( ch, &cand[i] ) )
            picks[n++] = cand[i];
    return n;
}

/* Up to max distinct creatures a reset places in the area, ordinary prey
   within the estimate's band about the level (EXPEDITION, errand.c). */
int hunting_area_prey( AREA_DATA *area, int level, MOB_INDEX_DATA **out, int max )
{
    RESET_DATA *r;
    int n = 0, i;

    if ( area == NULL )
        return 0;
    for ( r = area->reset_first; r != NULL && n < max; r = r->next )
    {
        MOB_INDEX_DATA *mob;

        if ( r->command != 'M' || ( mob = get_mob_index( r->arg1 ) ) == NULL
        ||   !hunt_prey( mob )
        ||   mob->level < level - HUNTING_BELOW || mob->level > level + HUNTING_ABOVE
        ||   hunt_placed( area, mob->vnum ) == NULL )
            continue;
        for ( i = 0; i < n && out[i] != mob; i++ )
            ;
        if ( i == n )
            out[n++] = mob;
    }
    return n;
}

static void hunt_number( char *out, size_t size, int value )
{
    if ( value >= 1000000 )
        snprintf( out, size, "%d,%03d,%03d", value / 1000000, value / 1000 % 1000, value % 1000 );
    else if ( value >= 1000 )
        snprintf( out, size, "%d,%03d", value / 1000, value % 1000 );
    else
        snprintf( out, size, "%d", value );
}

void do_hunting( CHAR_DATA *ch, char *argument )
{
    HUNT_PICK picks[HUNTING_SHOWN];
    char arg[MAX_INPUT_LENGTH];
    DString out;
    int level, n, from_file, i, timed = 0;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players go hunting.\n\r", ch );
        return;
    }
    one_argument( argument, arg );
    level = UMIN( ch->level, HUNTING_LEVEL_MAX );
    if ( arg[0] != '\0' && !parse_int( arg, 1, HUNTING_LEVEL_MAX, &level ) )
    {
        send_to_char( "Syntax: hunting [level]   (a level from 1 to 59)\n\r", ch );
        return;
    }
    memset( picks, 0, sizeof(picks) );
    from_file = hunt_measured( ch, level, picks );
    n = hunt_estimated( ch, level, picks, from_file );

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    if ( n == 0 )
    {
        dstring_printf( &out, "No creatures to suggest at level %d just now.  ADVENTURE lists places\n\r"
                              "at your level, and CONSIDER sizes up whatever you meet.\n\r", level );
        page_to_char( dstring_cstr( &out ), ch );
        dstring_free( &out );
        return;
    }
    dstring_printf( &out, "Creatures to hunt at level %d, one in each area:\n\r", level );
    for ( i = 0; i < n; i++ )
    {
        HUNT_PICK *pk = &picks[i];
        char name[48], line[256], extra[160], xp[24];

        hunt_plain( name, sizeof(name), pk->mob->short_descr );
        color_truncate( name, 40 );
        snprintf( line, sizeof(line), "  %s (level %d)\n\r", name, pk->mob->level );
        dstring_append_cstr( &out, line );
        /* The whole name WALKTO finds, never cut: it is what to type. */
        if ( pk->walkable )
            snprintf( line, sizeof(line), "    WALKTO %s\n\r", pk->walk );
        else
            snprintf( line, sizeof(line), "    Here in town, %s\n\r", area_shown_name( pk->area->name ) );
        dstring_append_cstr( &out, line );
        if ( pk->row != NULL )
        {
            hunt_number( xp, sizeof(xp), pk->row->xp_hour );
            snprintf( extra, sizeof(extra), "about %ds a kill, %s xp/hour, %s%s%s",
                      UMAX( 1, pk->row->seconds ), xp,
                      pk->row->measured ? "measured" : "estimated",
                      pk->row->risk >= HUNTING_RISKY ? ", risky" : "",
                      pk->row->aggressive ? ", attacks on sight" : "" );
            if ( pk->row->measured )
                timed++;
        }
        else
            snprintf( extra, sizeof(extra), "estimated%s",
                      IS_SET(pk->mob->act, ACT_AGGRESSIVE) ? ", attacks on sight" : "" );
        snprintf( line, sizeof(line), "    %s.\n\r", extra );
        dstring_append_cstr( &out, line );
    }
    dstring_append_cstr( &out, timed > 0
        ? "Measured: timed from players near this level.  The rest are estimates.\n\r"
        : "Estimates: no players' kills are measured at this level yet.\n\r" );
    dstring_append_cstr( &out, "CONSIDER before you fight: levels and gear differ.  HELP HUNTING says more.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}
