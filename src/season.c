/*
 * season.c  --  Real-world calendar-aware seasonal area selection.
 *
 * At boot, the area loader calls get_seasonal_area() for each filename in
 * area.lst so that the appropriate holiday variant is loaded automatically.
 * No area.lst edits or reboots are needed to switch seasons.
 *
 * WoW-inspired seasonal calendar:
 *   Hallows End  : Oct 18 – Nov  1  (halloween variants)
 *   Winter Veil  : Dec 16 – Jan  6  (xmas variants)
 *   (all other dates load the standard versions)
 */

#include <time.h>
#include <string.h>
#include "merc.h"
#include "list.h"

/* Internal season identifier. */
typedef enum
{
    SEASON_NORMAL    = 0,
    SEASON_HALLOWEEN = 1,
    SEASON_CHRISTMAS = 2
} SEASON_TYPE;

/*
 * Determine the current real-world season from the OS clock.
 * The server runs NTP-synced, so no internet call is needed.
 */
static SEASON_TYPE get_current_season( void )
{
    time_t     now;
    struct tm *tm_now;
    int        mon, day;

    now    = time( NULL );
    tm_now = localtime( &now );
    mon    = tm_now->tm_mon + 1;   /* 1-12 */
    day    = tm_now->tm_mday;      /* 1-31 */

    /* Hallows End: Oct 18 – Nov 1 */
    if ( (mon == 10 && day >= 18) || (mon == 11 && day == 1) )
        return SEASON_HALLOWEEN;

    /* Winter Veil: Dec 16 – Jan 6 */
    if ( (mon == 12 && day >= 16) || (mon == 1 && day <= 6) )
        return SEASON_CHRISTMAS;

    return SEASON_NORMAL;
}

/*
 * Return a human-readable season name for display in do_time(),
 * or NULL during normal (off-season) periods.
 */
const char *get_season_name( void )
{
    switch ( get_current_season() )
    {
        case SEASON_HALLOWEEN: return "Hallows End";
        case SEASON_CHRISTMAS: return "Winter Veil";
        default:               return NULL;
    }
}

/*
 * Given a base area filename from area.lst, return the season-appropriate
 * variant if one exists, otherwise return the original filename unchanged.
 *
 * Mappings:
 *   dresden.are  → dresden_halloween.are  (Halloween)
 *                  dresden_xmas.are       (Christmas)
 *   limbo.are    → limbo_halloween.are    (Halloween)
 *                  limbo_xmas.are         (Christmas)
 *   midennir.are → midennir_halloween.are (Halloween only)
 */
const char *get_seasonal_area( const char *area_file )
{
    SEASON_TYPE season;

    if ( area_file == NULL )
        return area_file;

    season = get_current_season();

    if ( season == SEASON_HALLOWEEN )
    {
        if ( !str_cmp( area_file, "dresden.are"  ) ) return "dresden_halloween.are";
        if ( !str_cmp( area_file, "limbo.are"    ) ) return "limbo_halloween.are";
        if ( !str_cmp( area_file, "midennir.are" ) ) return "midennir_halloween.are";
    }
    else if ( season == SEASON_CHRISTMAS )
    {
        if ( !str_cmp( area_file, "dresden.are"  ) ) return "dresden_xmas.are";
        if ( !str_cmp( area_file, "limbo.are"    ) ) return "limbo_xmas.are";
        if ( !str_cmp( area_file, "midennir.are" ) ) return "midennir_xmas.are";
    }

    return area_file;
}

/* =========================================================
 * Seasonal Event Boss System
 *
 * A powerful holiday boss mob spawns once every ~48 hours in Dresden
 * (room #2401, Oak Tree Square / Christmas Tree Square), announced with
 * a world-wide shout.  The boss periodically yells taunts, and
 * auto-despawns after two real hours.  Immortals may spawn or force-
 * despawn it with the "summonevent" command.
 *
 * Halloween: the Headless Horseman (vnum 29910) — undead, negative dmg
 * Winter Veil: Father Winter (vnum 29911) — human, cold dmg
 *
 * Rare drops (see seasonal.are #29920-29927):
 *   - Horseman's Reaper / Frostbite (powerful weapons)
 *   - Horseman's helm / Winter Veil mantle (powerful armor)
 *   - Pumpkin charm / Snowflake pendant (trinkets)
 *   - Shadowed horseman's cake / Yule log (ITEM_CAKE: +1 train on eat)
 * ========================================================= */

/* Vnum of the currently-spawned event boss (0 = none). */
CHAR_DATA *event_boss_mob = NULL;

/* Real-world time when the boss was spawned (0 = not running). */
static time_t event_boss_spawn_time = 0;

/* Despawn after this many real seconds (2 hours). */
#define EVENT_BOSS_DURATION  7200

/* Average ticks between spawns: 48 hours × 60 ticks/hour = 2880. */
#define EVENT_BOSS_SPAWN_ODDS  2880

/* ---- Seasonal vendors ---- */
CHAR_DATA *event_vendor_halloween = NULL;
CHAR_DATA *event_vendor_winter    = NULL;
static time_t vendor_spawn_time   = 0;

/* Average ticks before vendors spawn: 6 hours × 60 ticks/hour = 360. */
#define VENDOR_SPAWN_ODDS  360


/* -----------------------------------------------------------
 * Yell messages broadcast to the boss's area.
 * ----------------------------------------------------------- */
static const char *horseman_yells[] =
{
    "I seek a head to replace my own — yours will do nicely!",
    "None shall leave Dresden alive this night!",
    "Your skull will adorn my saddle before dawn breaks!",
    "The Horseman rides again — and all shall FEAR him!",
    "Kneel before me, or I will take your head as a trophy!",
    NULL
};

static const char *father_winter_yells[] =
{
    "You dare face Father Winter?  I shall freeze the marrow in your bones!",
    "There is no warmth left in this world — only my eternal cold!",
    "Your gifts are forfeit.  This Winter Veil belongs to ME!",
    "The blizzard has no mercy, and neither do I!",
    "Dresden shall be buried in ice before this night is through!",
    NULL
};


/* -----------------------------------------------------------
 * Broadcast a message to the whole world (no area filter).
 * Uses shout-style color so it looks like an announcement.
 * ----------------------------------------------------------- */
static void boss_global_shout( const char *msg )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof(buf), "{%02X[Event] %s{00\n\r", COL_SHOUTS, msg );

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        if ( d->connected != CON_PLAYING )
            continue;
        if ( IS_SET(d->character->comm, COMM_NOSHOUT) )
            continue;
        if ( IS_SET(d->character->comm, COMM_QUIET) )
            continue;
        send_to_char( buf, d->character );
    }
}


/* -----------------------------------------------------------
 * Verify the event_boss_mob pointer is still valid by scanning
 * character_list.  If the mob was killed/extracted, clears the pointer.
 * Returns TRUE if the boss is alive.
 * ----------------------------------------------------------- */
static bool verify_event_boss( void )
{
    LIST_ITERATOR iter;
    CHAR_DATA    *ch;

    if ( event_boss_mob == NULL )
        return FALSE;

    FOR_EACH_CHARACTER( iter, ch )
    {
        if ( ch == event_boss_mob )
            return TRUE;
    }

    /* Not found in character_list: was killed or extracted. */
    event_boss_mob        = NULL;
    event_boss_spawn_time = 0;
    return FALSE;
}


/* -----------------------------------------------------------
 * Return the boss vnum appropriate for the current season.
 * Falls back to the Headless Horseman if called off-season.
 * ----------------------------------------------------------- */
int get_event_boss_vnum( void )
{
    switch ( get_current_season() )
    {
        case SEASON_HALLOWEEN: return MOB_VNUM_EVENT_HORSEMAN;
        case SEASON_CHRISTMAS: return MOB_VNUM_EVENT_FATHER;
        default:               return MOB_VNUM_EVENT_HORSEMAN; /* testing */
    }
}


/* -----------------------------------------------------------
 * Spawn the event boss in Dresden's Oak Tree Square (#2401).
 * forced_vnum != 0 overrides the auto-detected seasonal default.
 * ----------------------------------------------------------- */
void spawn_event_boss( int forced_vnum )
{
    MOB_INDEX_DATA  *pMobIndex;
    ROOM_INDEX_DATA *room;
    int              vnum;
    char             msg[MAX_STRING_LENGTH];

    /* Already alive — do not double-spawn. */
    if ( verify_event_boss() )
        return;

    vnum = ( forced_vnum != 0 ) ? forced_vnum : get_event_boss_vnum();
    if ( ( pMobIndex = get_mob_index( vnum ) ) == NULL )
    {
        bug( "spawn_event_boss: mob vnum %d not found.", vnum );
        return;
    }

    if ( ( room = get_room_index( EVENT_BOSS_SPAWN_ROOM ) ) == NULL )
    {
        bug( "spawn_event_boss: spawn room %d not found.", EVENT_BOSS_SPAWN_ROOM );
        return;
    }

    event_boss_mob        = create_mobile( pMobIndex );
    char_to_room( event_boss_mob, room );
    event_boss_spawn_time = time( NULL );

    if ( vnum == MOB_VNUM_EVENT_HORSEMAN )
    {
        snprintf( msg, sizeof(msg),
            "A CRACK of thunder shakes Dresden as the Headless Horseman "
            "rides into Oak Tree Square on his spectral steed!" );
    }
    else if ( vnum == MOB_VNUM_EVENT_FATHER )
    {
        snprintf( msg, sizeof(msg),
            "The temperature drops sharply as Father Winter strides into "
            "Dresden's Christmas Tree Square, frost crackling in his wake!" );
    }
    else
    {
        snprintf( msg, sizeof(msg),
            "A crack of thunder shakes Dresden as a terrible figure "
            "appears in Oak Tree Square!" );
    }

    boss_global_shout( msg );

    /* Local act so players IN the room see the arrival too. */
    act( "$N arrives with a thunderous crash!", NULL, NULL, event_boss_mob, TO_ROOM );
}


/* -----------------------------------------------------------
 * Forcibly remove the event boss and clear state.
 * If quiet=TRUE, no departure message is sent.
 * ----------------------------------------------------------- */
void despawn_event_boss( void )
{
    if ( !verify_event_boss() )
        return;

    /* Farewell message. */
    act( "$N lets out a final roar and fades from the world!", NULL, NULL, event_boss_mob, TO_ROOM );

    extract_char( event_boss_mob, TRUE );
    event_boss_mob        = NULL;
    event_boss_spawn_time = 0;
}


/* -----------------------------------------------------------
 * Called once per PULSE_TICK (~60 real seconds) from update_handler.
 *
 *  1. If the boss was killed, clears state.
 *  2. If the boss has been up too long, despawns it.
 *  3. If the boss is alive, occasionally makes it yell.
 *  4. If no boss is alive, rolls for a new spawn (holiday season only).
 * ----------------------------------------------------------- */
void tick_event_boss( void )
{
    /* Tick vendor spawning alongside boss spawning. */
    tick_seasonal_vendors();

    /* --- Case 1: check if boss still lives --- */
    if ( event_boss_mob != NULL && !verify_event_boss() )
    {
        /* Already cleared by verify_event_boss; announce the defeat. */
        boss_global_shout(
            "The event boss has been defeated!  Dresden breathes again." );
        return;
    }

    /* --- Case 2: boss alive — check despawn timer --- */
    if ( event_boss_mob != NULL )
    {
        time_t elapsed = time( NULL ) - event_boss_spawn_time;

        if ( elapsed >= EVENT_BOSS_DURATION )
        {
            boss_global_shout(
                "The event boss vanishes as suddenly as it appeared, "
                "leaving only silence and scattered debris." );
            despawn_event_boss();
            return;
        }

        /* --- Case 3: periodic yell --- */
        if ( number_range( 1, 3 ) == 1 )    /* ~33% chance each tick */
        {
            DESCRIPTOR_DATA     *d;
            const char * const  *yell_pool;
            int                  count;
            const char          *msg;
            char                 buf[MAX_STRING_LENGTH];
            int                  pick;

            if ( event_boss_mob->pIndexData->vnum == MOB_VNUM_EVENT_HORSEMAN )
                yell_pool = horseman_yells;
            else
                yell_pool = father_winter_yells;

            /* Count entries */
            for ( count = 0; yell_pool[count] != NULL; count++ )
                ;

            pick = number_range( 0, count - 1 );
            msg  = yell_pool[pick];

            snprintf( buf, sizeof(buf),
                "{%02X%s yells '%s'{00\n\r",
                COL_SHOUTS,
                event_boss_mob->short_descr,
                msg );

            /* Broadcast to the boss's area (yell-style). */
            for ( d = descriptor_list; d != NULL; d = d->next )
            {
                CHAR_DATA *victim;

                if ( d->connected != CON_PLAYING )
                    continue;
                if ( event_boss_mob->in_room == NULL )
                    break;

                victim = d->original ? d->original : d->character;
                if ( victim->in_room == NULL )
                    continue;
                if ( victim->in_room->area != event_boss_mob->in_room->area )
                    continue;
                if ( IS_SET(victim->comm, COMM_QUIET) )
                    continue;

                send_to_char( buf, d->character );
            }
        }

        return;     /* boss is alive and handled */
    }

    /* --- Case 4: no boss — roll for a new spawn (seasonal only) --- */
    if ( get_current_season() != SEASON_NORMAL )
    {
        if ( number_range( 1, EVENT_BOSS_SPAWN_ODDS ) == 1 )
            spawn_event_boss( 0 );  /* 0 = auto-detect from season */
    }
}


/* ===========================================================
 * Seasonal vendor support
 * ===========================================================
 *
 * During active seasonal events, one or two wandering merchants
 * appear in Dresden's Oak Tree Square selling holiday items.
 * They despawn after VENDOR_DURATION seconds (4 hours).
 * =========================================================== */

static void give_vendor_items( CHAR_DATA *vendor, int item_vnum1, int item_vnum2 )
{
    OBJ_INDEX_DATA *pObj;
    OBJ_DATA       *obj;
    int             i;

    for ( i = 0; i < 10; i++ )
    {
        if ( ( pObj = get_obj_index( item_vnum1 ) ) != NULL )
        {
            obj = create_object( pObj, 0 );
            obj_to_char( obj, vendor );
        }
    }
    for ( i = 0; i < 10; i++ )
    {
        if ( ( pObj = get_obj_index( item_vnum2 ) ) != NULL )
        {
            obj = create_object( pObj, 0 );
            obj_to_char( obj, vendor );
        }
    }
}


void spawn_seasonal_vendors( void )
{
    MOB_INDEX_DATA  *pMob;
    ROOM_INDEX_DATA *room;
    SEASON_TYPE      season;

    season = get_current_season();
    if ( season == SEASON_NORMAL )
        return;

    if ( ( room = get_room_index( VENDOR_SPAWN_ROOM ) ) == NULL )
    {
        bug( "spawn_seasonal_vendors: spawn room %d not found.", VENDOR_SPAWN_ROOM );
        return;
    }

    if ( season == SEASON_HALLOWEEN && event_vendor_halloween == NULL )
    {
        if ( ( pMob = get_mob_index( MOB_VNUM_VENDOR_HALLOWEEN ) ) != NULL )
        {
            event_vendor_halloween = create_mobile( pMob );
            char_to_room( event_vendor_halloween, room );
            give_vendor_items( event_vendor_halloween,
                               OBJ_VNUM_JACK_O_MASK,
                               OBJ_VNUM_CANDY_CORN );
            boss_global_shout(
                "Madame Hexley the Hallows End merchant has appeared in "
                "Dresden's Oak Tree Square with holiday wares for sale!" );
        }
    }
    else if ( season == SEASON_CHRISTMAS && event_vendor_winter == NULL )
    {
        if ( ( pMob = get_mob_index( MOB_VNUM_VENDOR_WINTER ) ) != NULL )
        {
            event_vendor_winter = create_mobile( pMob );
            char_to_room( event_vendor_winter, room );
            give_vendor_items( event_vendor_winter,
                               OBJ_VNUM_ELF_HAT,
                               OBJ_VNUM_SPICED_CIDER );
            boss_global_shout(
                "Tinsel the Winter Veil gift elf has skipped into Dresden's "
                "Oak Tree Square with holiday gifts and treats for sale!" );
        }
    }

    vendor_spawn_time = time( NULL );
}


void despawn_seasonal_vendors( void )
{
    if ( event_vendor_halloween != NULL )
    {
        act( "$N calls out 'Come find me again next year!' and vanishes into the shadows.",
             NULL, NULL, event_vendor_halloween, TO_ROOM );
        extract_char( event_vendor_halloween, TRUE );
        event_vendor_halloween = NULL;
    }
    if ( event_vendor_winter != NULL )
    {
        act( "$N gives a cheerful wave and disappears in a flurry of snowflakes.",
             NULL, NULL, event_vendor_winter, TO_ROOM );
        extract_char( event_vendor_winter, TRUE );
        event_vendor_winter = NULL;
    }
    vendor_spawn_time = 0;
}


void tick_seasonal_vendors( void )
{
    SEASON_TYPE season;

    /* Despawn if either vendor has overstayed their welcome. */
    if ( ( event_vendor_halloween != NULL || event_vendor_winter != NULL )
         && vendor_spawn_time > 0
         && ( time(NULL) - vendor_spawn_time ) >= VENDOR_DURATION )
    {
        despawn_seasonal_vendors();
        return;
    }

    /* Clear stale pointers if the mob was killed or extracted. */
    if ( event_vendor_halloween != NULL && event_vendor_halloween->in_room == NULL )
    {
        event_vendor_halloween = NULL;
        vendor_spawn_time      = 0;
    }
    if ( event_vendor_winter != NULL && event_vendor_winter->in_room == NULL )
    {
        event_vendor_winter = NULL;
        vendor_spawn_time   = 0;
    }

    /* Roll for a new spawn if none active. */
    season = get_current_season();
    if ( season == SEASON_NORMAL )
        return;

    if ( season == SEASON_HALLOWEEN && event_vendor_halloween == NULL )
    {
        if ( number_range( 1, VENDOR_SPAWN_ODDS ) == 1 )
            spawn_seasonal_vendors();
    }
    else if ( season == SEASON_CHRISTMAS && event_vendor_winter == NULL )
    {
        if ( number_range( 1, VENDOR_SPAWN_ODDS ) == 1 )
            spawn_seasonal_vendors();
    }
}

