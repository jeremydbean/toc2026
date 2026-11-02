/*
 * season.c  --  Real-world calendar-aware seasonal area selection.
 *
 * At boot, the area loader calls get_seasonal_area() for each filename in
 * area.lst so that the appropriate holiday variant is loaded automatically.
 * area.lst never changes to switch seasons, but the swap happens only at
 * boot: a world booted before Hallows End or Winter Veil keeps the
 * ordinary areas until its next reboot, and one booted in season keeps
 * the decorated copies after it ends (season_loaded_name() says which a
 * running world has). The fair in the square -- holiday.c -- follows the
 * calendar without a reboot.
 *
 * The dates are holiday.c's calendar (holiday_key), which has every
 * holiday; two of them swap areas here:
 *   Hallows End  : Oct 18 - Nov  1  (halloween variants)
 *   Winter Veil  : Dec 16 - Jan  6  (xmas variants)
 *   (all other dates load the standard versions)
 */

#include <time.h>
#include <string.h>
#include <stdlib.h>
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
    /* One calendar for both (holiday.c, which also reads TOC_SEASON and
       TOC_DATE): two of its holidays swap areas here. */
    const char *key = holiday_key();

    if ( key != NULL && !str_cmp( key, "halloween" ) )
        return SEASON_HALLOWEEN;
    if ( key != NULL && !str_cmp( key, "xmas" ) )
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
/* The season whose copies boot loaded (the first base name it mapped),
   which is not always the season now: see the top of this file. */
static SEASON_TYPE season_loaded = SEASON_NORMAL;

const char *season_loaded_name( void )
{
    switch ( season_loaded )
    {
        case SEASON_HALLOWEEN: return "Hallows End";
        case SEASON_CHRISTMAS: return "Winter Veil";
        default:               return NULL;
    }
}

static const char *seasonal_variant( SEASON_TYPE season, const char *area_file )
{

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

const char *get_seasonal_area( const char *area_file )
{
    SEASON_TYPE season;
    const char *variant;

    if ( area_file == NULL )
        return area_file;

    season  = get_current_season();
    variant = seasonal_variant( season, area_file );
    if ( variant != area_file )
        season_loaded = season;
    return variant;
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
 * Halloween: the Headless Horseman (vnum 29910) -- undead, negative dmg
 * Winter Veil: Father Winter (vnum 29911) -- human, cold dmg
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


/* -----------------------------------------------------------
 * Yell messages broadcast to the boss's area.
 * ----------------------------------------------------------- */
static const char *horseman_yells[] =
{
    "I seek a head to replace my own -- yours will do nicely!",
    "None shall leave Dresden alive this night!",
    "Your skull will adorn my saddle before dawn breaks!",
    "The Horseman rides again -- and all shall FEAR him!",
    "Kneel before me, or I will take your head as a trophy!",
    NULL
};

static const char *father_winter_yells[] =
{
    "You dare face Father Winter?  I shall freeze the marrow in your bones!",
    "There is no warmth left in this world -- only my eternal cold!",
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
 * Whether the boss is in the world. event_boss_mob is cleared the moment
 * the boss leaves it -- record_event_boss_defeat at a death, and
 * event_boss_forget from extract_char for any other way out -- so the
 * pointer is never stale. It used to be checked by scanning the
 * character list for the same address, which a purged boss's recycled
 * CHAR_DATA passed: the next MLOAD came back at that address and was
 * taken for the boss (review, 2026-11-02).
 * ----------------------------------------------------------- */
bool verify_event_boss( void )
{
    return event_boss_mob != NULL;
}

/* extract_char, before the CHAR_DATA can be reused: a boss taken out any
   way but a death (PURGE, a staff despawn, the timer) is gone quietly --
   it was not defeated, and nobody is told it was. */
void event_boss_forget( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];

    if ( ch == NULL || ch != event_boss_mob )
        return;
    snprintf( buf, sizeof(buf), "Event boss %s (mob %d) left the world without being slain.",
              ch->short_descr != NULL ? ch->short_descr : "?",
              ch->pIndexData != NULL ? ch->pIndexData->vnum : 0 );
    log_string( buf );
    event_boss_mob        = NULL;
    event_boss_spawn_time = 0;
}

void record_event_boss_defeat( CHAR_DATA *boss )
{
    char msg[MAX_STRING_LENGTH];

    if ( boss == NULL || event_boss_mob != boss )
        return;

    snprintf( msg, sizeof(msg),
        "%s has been defeated! Dresden breathes again.",
        boss->short_descr != NULL ? boss->short_descr : "The event boss" );
    event_boss_mob = NULL;
    event_boss_spawn_time = 0;
    boss_global_shout( msg );
}


/* -----------------------------------------------------------
 * What each boss leaves on its corpse. make_corpse rolls these and LOOK
 * reads them back (owner, 2026-10-20: looking at the boss should say
 * what it drops), so a change here changes both.
 * ----------------------------------------------------------- */
static const EVENT_DROP horseman_drops[] =
{
    { OBJ_VNUM_HORSEMAN_REAPER, 50, EVENT_DROP_PRIMARY  },
    { OBJ_VNUM_HORSEMAN_HELM,   50, EVENT_DROP_PRIMARY  },
    { OBJ_VNUM_PUMPKIN_CHARM,   75, EVENT_DROP_FALLBACK },
    { OBJ_VNUM_HORSEMAN_CAKE,    5, EVENT_DROP_RARE     },
    { 0, 0, 0 }
};

static const EVENT_DROP father_winter_drops[] =
{
    { OBJ_VNUM_WINTER_HAMMER,   50, EVENT_DROP_PRIMARY  },
    { OBJ_VNUM_WINTER_MANTLE,   50, EVENT_DROP_PRIMARY  },
    { OBJ_VNUM_SNOWFLAKE_PEND,  75, EVENT_DROP_FALLBACK },
    { OBJ_VNUM_WINTER_CAKE,      5, EVENT_DROP_RARE     },
    { 0, 0, 0 }
};

const EVENT_DROP *event_boss_drops( int mob_vnum )
{
    if ( mob_vnum == MOB_VNUM_EVENT_HORSEMAN )
        return horseman_drops;
    if ( mob_vnum == MOB_VNUM_EVENT_FATHER )
        return father_winter_drops;
    return NULL;
}

static const char *drop_chance_words( int chance )
{
    switch ( chance )
    {
        case 100: return "every time";
        case  75: return "three times in four";
        case  50: return "half the time";
        case  25: return "one time in four";
        case  10: return "one time in ten";
        case   5: return "one time in twenty";
        default:  return NULL;
    }
}

/* Appended to LOOK <boss>: the table above, in words. Nothing for any
   other mobile, so it is safe to call for every look. */
void event_boss_show_drops( CHAR_DATA *victim, CHAR_DATA *ch )
{
    const EVENT_DROP *table;
    OBJ_INDEX_DATA *pObj;
    char buf[MAX_STRING_LENGTH];
    char odds[64];
    const char *words;
    int i;

    if ( victim == NULL || !IS_NPC(victim) || victim->pIndexData == NULL )
        return;
    if ( ( table = event_boss_drops( victim->pIndexData->vnum ) ) == NULL )
        return;

    snprintf( buf, sizeof(buf), "\n\rSlain, %s leaves on the corpse:\n\r",
              victim->short_descr );
    send_to_char( buf, ch );
    for ( i = 0; table[i].vnum != 0; i++ )
    {
        if ( ( pObj = get_obj_index( table[i].vnum ) ) == NULL )
            continue;
        if ( ( words = drop_chance_words( table[i].chance ) ) != NULL )
            toc_strlcpy( odds, words, sizeof(odds) );
        else
            snprintf( odds, sizeof(odds), "%d%% of the time", table[i].chance );
        snprintf( buf, sizeof(buf), "  %-40s %s%s\n\r", pObj->short_descr, odds,
                  table[i].role == EVENT_DROP_FALLBACK
                      ? ", and always when nothing else fell" : "" );
        send_to_char( buf, ch );
    }
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

    /* Already alive -- do not double-spawn. */
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

    /* Local act so players IN the room see the arrival too. The boss is
       the actor: act() with no actor sends nothing at all, so with the
       shouts turned off a player standing in the square saw no boss
       arrive (review, 2026-11-02). */
    act( "$n arrives with a thunderous crash!", event_boss_mob, NULL, NULL, TO_ROOM );
}


/* -----------------------------------------------------------
 * Forcibly remove the event boss and clear state.
 * If quiet=TRUE, no departure message is sent.
 * ----------------------------------------------------------- */
void despawn_event_boss( void )
{
    if ( !verify_event_boss() )
        return;

    /* Farewell message, the boss its actor (see spawn_event_boss). */
    act( "$n lets out a final roar and fades from the world!", event_boss_mob, NULL, NULL, TO_ROOM );

    /* extract_char clears event_boss_mob through event_boss_forget. */
    extract_char( event_boss_mob, TRUE );
    event_boss_mob        = NULL;
    event_boss_spawn_time = 0;
}


/* -----------------------------------------------------------
 * Called once per PULSE_TICK (~60 real seconds) from update_handler.
 *
 *  1. (A boss's death is announced by record_event_boss_defeat, and any
 *     other way out clears it in event_boss_forget.)
 *  2. If the boss has been up too long, despawns it.
 *  3. If the boss is alive, occasionally makes it yell.
 *  4. If no boss is alive, rolls for a new spawn (holiday season only).
 * ----------------------------------------------------------- */
void tick_event_boss( void )
{
    /* The holiday fair in the square: vendor, decoration, eggs. */
    holiday_tick();

    /* --- Case 2: boss alive -- check despawn timer --- */
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

    /* --- Case 4: no boss -- roll for a new spawn (seasonal only) --- */
    if ( get_current_season() != SEASON_NORMAL )
    {
        if ( number_range( 1, EVENT_BOSS_SPAWN_ODDS ) == 1 )
            spawn_event_boss( 0 );  /* 0 = auto-detect from season */
    }
}
