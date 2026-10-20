/*
 * The treasure goblin: a rare, cowardly thief with a sack of coin, after
 * Diablo's (owner's design, 2026-10-20).
 *
 * There is always one somewhere in the world: a new one appears, at a
 * random room, a minute or so after the last is killed. He wanders a
 * step now and then, and while nobody is after him he now and then
 * vanishes and turns up somewhere else entirely. He never goes where he
 * could not be struck (gob_room_ok). Nothing finds him from afar -- he is
 * hidden exactly as the black market dealer is (black_market_sees in
 * blackmarket.c), so WHERE, the travel spells, clairvoyance, PROJECT and
 * the Oracle all miss him, and SCAN sees him one room away.
 *
 * He never fights back. Every blow that lands spills coin on the floor
 * and sends him running through a random exit, so killing him is a chase.
 * A landed blow takes a fixed share of his health, set by how hard it hit
 * (treasure_goblin_blow): the hardest hitter needs GOBLIN_BLOWS_MIN blows
 * -- twelve flights -- and the gentlest GOBLIN_BLOWS_MAX, so a level 3
 * and a level 59 both finish him and the strong one runs a few rooms
 * less (owner, 2026-10-20). A stun pins him: stunned, asleep or knocked
 * down he cannot run, though he shakes a stun off quickly.
 *
 * As in Diablo, the chase has to be kept up: a tick without a blow --
 * whether his chaser lost him or stands there idle -- and he starts
 * tearing open a portal, and a pulse later is through it and somewhere
 * else, wounds and all. A blow while it opens collapses it; a stun stops
 * him opening one.
 *
 * Coin spilt and coin hoarded are counted in kills at the striker's level
 * (black_market_kill_value), so it is a good sum for a level 5 and for a
 * level 55 alike. Dead, his sack bursts: about GOBLIN_HOARD_KILLS kills'
 * worth of coin, often the best piece the world places for some slot at
 * the killer's level (black_market_gear_for_level), and now and then one
 * of the black market's rarities. The coin piles he spilt on the way
 * mark the trail.
 *
 * Appearances and kills go to the log and to staff on WIZINFO with the
 * room; his escapes and drifts go to the log.
 */
#include <time.h>
#include <stdlib.h>
#include <limits.h>
#include "merc.h"

extern char * const dir_name[];

CHAR_DATA *treasure_goblin = NULL;

/* When the next one appears, while there is none. */
static time_t gob_next_spawn = 0;
/* When a mortal last stood with him, while he is being chased. */
static time_t gob_last_company = 0;
/* When he next drifts elsewhere, and next wanders a step, while nobody
   is after him. He is a sentinel to mobile_update, which would walk him
   into rooms nobody could strike him in. */
static time_t gob_next_drift = 0;
static time_t gob_next_step = 0;
/* The area he is in, and since when: GOBLIN_AREA_MAX there with nobody
   after him and he crosses to another (owner, 2026-10-20). */
static AREA_DATA *gob_area = NULL;
static time_t gob_area_since = 0;
#define GOBLIN_AREA_MAX     ( 10 * 60 )
#define GOBLIN_STEP_MIN     20
#define GOBLIN_STEP_MAX     50
/* Hit points he may not regenerate past: the chase keeps its progress. */
static int gob_hp = 0;
static bool gob_chased = false;
/* The last blow, and the portal he is opening (0 when none). */
static time_t gob_last_hit = 0;
static time_t gob_portal_at = 0;

#define GOBLIN_BLOWS_MIN    13          /* landed blows, hardest hitter */
#define GOBLIN_BLOWS_MAX    18          /* landed blows, gentlest */
#define GOBLIN_RESPAWN_MIN  60
#define GOBLIN_RESPAWN_MAX  180
#define GOBLIN_ALONE        60          /* a tick without a blow: a portal */
#define GOBLIN_DRIFT_MIN    ( 20 * 60 )
#define GOBLIN_DRIFT_MAX    ( 40 * 60 )
#define GOBLIN_UNSTUN_ODDS  25          /* percent per mobile pulse */
/* Coin spilt on each blow, and the hoard in his corpse, in kills' worth
   of coin at the striker's level: at level 50 a kill is about 13
   platinum, so a hoard is about 2,700. */
#define GOBLIN_SPILL_KILLS_MIN  4
#define GOBLIN_SPILL_KILLS_MAX  8
#define GOBLIN_HOARD_KILLS      200
/* What else is in the sack, percent. */
#define GOBLIN_GEAR_CHANCE  50
#define GOBLIN_RARE_CHANCE  10


bool is_treasure_goblin( const CHAR_DATA *ch )
{
    return ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
        && ch->pIndexData->vnum == MOB_VNUM_TREASURE_GOBLIN;
}

/* "room 4207 (Before the Altar., dresden.are)" */
static void gob_where( ROOM_INDEX_DATA *room, char *out, size_t len )
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

/* Whoever gets the credit for a blow or a kill: a pet's master. */
static CHAR_DATA *gob_credit( CHAR_DATA *ch )
{
    if ( ch != NULL && IS_NPC(ch) && IS_AFFECTED(ch, AFF_CHARM)
    &&   ch->master != NULL )
        return ch->master;
    return ch;
}

static bool gob_has_company( CHAR_DATA *gob )
{
    CHAR_DATA *rch;

    if ( gob->in_room == NULL )
        return false;
    for ( rch = gob->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( !IS_NPC(rch) && !IS_TRUSTED( rch, LEVEL_IMMORTAL ) )
            return true;
    return false;
}

/* Where he may run, wander or land: the dealer's rooms, less any room he
   could not be struck in -- a goblin in a safe room is a goblin nobody
   can finish. */
static bool gob_room_ok( ROOM_INDEX_DATA *room )
{
    return black_market_room_ok( room )
        && !IS_SET( room->room_flags, ROOM_SAFE )
        && room->vnum != ROOM_VNUM_TEMPLE && room->vnum != ROOM_VNUM_ALTAR;
}

/* A room he may land in, anywhere but in `avoid` (NULL: anywhere). */
static ROOM_INDEX_DATA *gob_random_room( AREA_DATA *avoid )
{
    int tries;

    for ( tries = 0; tries < 20; tries++ )
    {
        ROOM_INDEX_DATA *room = black_market_random_room( avoid );

        if ( room != NULL && gob_room_ok( room ) )
            return room;
    }
    return NULL;
}

/* A random exit he may take from where he stands, or -1. */
static int gob_pick_exit( CHAR_DATA *gob )
{
    int doors[10], n = 0, door;

    for ( door = 0; door <= 9; door++ )
    {
        EXIT_DATA *pexit = gob->in_room->exit[door];

        if ( pexit != NULL && pexit->u1.to_room != NULL
        &&   !IS_SET( pexit->exit_info, EX_CLOSED )
        &&   gob_room_ok( pexit->u1.to_room ) )
            doors[n++] = door;
    }
    return n > 0 ? doors[number_range( 0, n - 1 )] : -1;
}

/* Stunned, asleep, knocked down: in no state to run. */
static bool gob_pinned( CHAR_DATA *gob )
{
    return IS_AFFECTED2(gob, AFF2_STUNNED) || IS_AFFECTED(gob, AFF_SLEEP)
        || gob->position < POS_FIGHTING;
}

/* For damage(), before it stands him up for the fight. */
bool treasure_goblin_held( CHAR_DATA *gob )
{
    return gob != NULL && gob_pinned( gob );
}

static void gob_teleport( CHAR_DATA *gob, AREA_DATA *avoid, const char *why )
{
    ROOM_INDEX_DATA *to = gob_random_room( avoid );
    char from[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH * 2 + 128];

    gob_chased = false;
    gob_portal_at = 0;
    gob_next_drift = current_time + number_range( GOBLIN_DRIFT_MIN, GOBLIN_DRIFT_MAX );
    if ( to == NULL || to == gob->in_room )
        return;
    gob_where( gob->in_room, from, sizeof(from) );
    stop_fighting( gob, true );
    act( "$n cackles, tears open a shimmering rift and dives through it, sack and all.",
         gob, NULL, NULL, TO_ROOM );
    char_from_room( gob );
    char_to_room( gob, to );
    act( "A shimmering rift tears open and $n tumbles out, clutching $s sack.",
         gob, NULL, NULL, TO_ROOM );
    /* Not where he went: log/ is published every five minutes. */
    snprintf( line, sizeof(line), "Treasure goblin: vanished from %s (%s).",
              from, why );
    log_string( line );
}

/* A new one, somewhere at random -- or in `room`, for staff. */
bool treasure_goblin_spawn( ROOM_INDEX_DATA *room )
{
    MOB_INDEX_DATA *pMob;
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH + 64];

    if ( treasure_goblin != NULL )
        return false;
    if ( ( pMob = get_mob_index( MOB_VNUM_TREASURE_GOBLIN ) ) == NULL )
    {
        bug( "Treasure goblin: mobile %d is missing.", MOB_VNUM_TREASURE_GOBLIN );
        return false;
    }
    if ( room == NULL && ( room = gob_random_room( NULL ) ) == NULL )
        return false;

    treasure_goblin = create_mobile( pMob );
    char_to_room( treasure_goblin, room );
    act( "A shimmering rift tears open and $n tumbles out, clutching $s sack.",
         treasure_goblin, NULL, NULL, TO_ROOM );
    gob_hp = treasure_goblin->max_hit;
    gob_chased = false;
    gob_area = NULL;                /* a new goblin starts a fresh clock */
    gob_portal_at = 0;
    gob_next_drift = current_time + number_range( GOBLIN_DRIFT_MIN, GOBLIN_DRIFT_MAX );

    log_string( "Treasure goblin: appeared." );
    gob_where( room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Treasure goblin: appeared in %s.", where );
    wizinfo( line, LEVEL_IMMORTAL );
    return true;
}

void treasure_goblin_dismiss( void )
{
    if ( treasure_goblin == NULL )
        return;
    if ( treasure_goblin->in_room != NULL )
        act( "$n cackles and is gone through a shimmering rift.",
             treasure_goblin, NULL, NULL, TO_ROOM );
    extract_char( treasure_goblin, true );    /* clears treasure_goblin */
    treasure_goblin = NULL;
    log_string( "Treasure goblin: dismissed." );
}

/* extract_char calls this; a death schedules the next one. */
void treasure_goblin_forget( CHAR_DATA *ch )
{
    if ( ch == NULL || ch != treasure_goblin )
        return;
    treasure_goblin = NULL;
    gob_chased = false;
    gob_next_spawn = current_time
                   + number_range( GOBLIN_RESPAWN_MIN, GOBLIN_RESPAWN_MAX );
}

/*
 * What a blow does to him: a share of his health set by how hard it
 * landed, not the blow itself, so his hit points never decide who can
 * kill him. A newbie's ten-point swing takes one GOBLIN_BLOWS_MAX'th, a
 * hero's two-hundred-point one one GOBLIN_BLOWS_MIN'th, and everything
 * between steps across. damage() asks this before its message.
 */
int treasure_goblin_blow( CHAR_DATA *gob, int dam )
{
    static const int step[] = { 15, 30, 60, 100, 160 };   /* damage */
    int blows = GOBLIN_BLOWS_MAX, i;

    if ( dam <= 0 || gob->max_hit <= 0 )
        return dam;
    /* A heal since the last blow is undone before this one lands. */
    if ( gob == treasure_goblin && gob->hit > gob_hp )
        gob->hit = gob_hp;
    for ( i = 0; i < (int)( sizeof(step) / sizeof(step[0]) ); i++ )
        if ( dam >= step[i] )
            blows--;
    blows = URANGE( GOBLIN_BLOWS_MIN, blows, GOBLIN_BLOWS_MAX );
    return ( gob->max_hit + blows - 1 ) / blows;
}

/* Copper laid on the floor as the fewest piles that carry it. */
static OBJ_DATA *gob_spill( ROOM_INDEX_DATA *room, long copper )
{
    static const long unit[4] =
        { COPPER_PER_PLATINUM, COPPER_PER_GOLD, COPPER_PER_SILVER, 1 };
    static const int type[4] =
        { TYPE_PLATINUM, TYPE_GOLD, TYPE_SILVER, TYPE_COPPER };
    OBJ_DATA *first = NULL;
    int i;

    for ( i = 0; i < 4 && copper > 0; i++ )
    {
        long n = UMIN( copper / unit[i], 1000000L );
        OBJ_DATA *pile;

        if ( n <= 0 )
            continue;
        copper -= n * unit[i];
        pile = create_money( (int) n, type[i] );
        obj_to_room( pile, room );
        if ( first == NULL )
            first = pile;
    }
    return first;
}

/*
 * damage() calls this once a blow has landed and he is still alive: coin
 * spills, and unless something holds him he bolts through a random exit.
 */
void treasure_goblin_struck( CHAR_DATA *ch, CHAR_DATA *gob, bool held )
{
    OBJ_DATA *coins;
    int door;
    ROOM_INDEX_DATA *was_in = gob->in_room;

    if ( was_in == NULL )
        return;
    /* The chase's clocks belong to the one goblin the world keeps; a copy
       staff loaded by hand runs and spills, but must not move them. */
    if ( gob == treasure_goblin )
    {
        /* Never higher than the last blow left him: a heal between blows
           would otherwise be the new ceiling, and a cleric could keep him
           spilling coin for ever. */
        gob_hp = UMIN( gob_hp, gob->hit );
        gob->hit = gob_hp;
        gob_chased = true;
        gob_last_company = current_time;
        gob_last_hit = current_time;
        if ( gob_portal_at != 0 )
        {
            gob_portal_at = 0;
            act( "The half-open portal collapses as $n yelps in pain!",
                 gob, NULL, NULL, TO_ROOM );
        }
    }

    {
        CHAR_DATA *who = gob_credit( ch );

        coins = gob_spill( was_in, number_range( GOBLIN_SPILL_KILLS_MIN,
                                                 GOBLIN_SPILL_KILLS_MAX )
                           * black_market_kill_value( who != NULL ? who->level : 1 ) );
        if ( coins != NULL )
            act( "$n shrieks as $p spills from a hole in $s sack!",
                 gob, coins, NULL, TO_ROOM );
    }

    if ( held || gob_pinned( gob ) )
    {
        /* damage() stood him up for the fight; a held goblin stays down
           until treasure_goblin_update's roll lets him up. */
        if ( held && gob->position > POS_RESTING )
            gob->position = POS_RESTING;
        act( "$n flails about, too dazed to run!", gob, NULL, NULL, TO_ROOM );
        return;
    }

    /* The fight is over the moment he runs: nobody swings at the air. */
    stop_fighting( gob, true );
    if ( ( door = gob_pick_exit( gob ) ) >= 0 )
    {
        act( "$n clutches $s sack and scurries off $T!", gob, NULL,
             dir_name[door], TO_ROOM );
        move_char( gob, door, false );
    }
    if ( gob->in_room == was_in )
        gob_teleport( gob, NULL, "nowhere to run" );
}

/*
 * raw_kill_internal asks this first. An instant kill -- a death ray, a
 * fatality, a farslayer -- would end the chase with one word, so it lands
 * as a hard blow instead: the largest share, and he runs. Only a death
 * damage() has already decided (POS_DEAD), or a slay by staff, kills him.
 * True when the death is called off.
 */
bool treasure_goblin_cheats_death( CHAR_DATA *killer, CHAR_DATA *gob )
{
    if ( !is_treasure_goblin( gob ) || gob->position == POS_DEAD )
        return false;
    if ( killer != NULL && !IS_NPC(killer) && IS_TRUSTED( killer, LEVEL_IMMORTAL ) )
        return false;
    /* What the instant kill did to his hit points first (a farslayer
       sets them to 1) is not the blow; the blow is the share below. */
    if ( gob == treasure_goblin && gob->hit < gob_hp )
        gob->hit = gob_hp;
    gob->hit -= ( gob->max_hit + GOBLIN_BLOWS_MIN - 1 ) / GOBLIN_BLOWS_MIN;
    if ( gob->hit < 1 )
    {
        gob->position = POS_DEAD;
        return false;
    }
    act( "$n reels from the blow -- but a treasure goblin is harder to kill than that!",
         gob, NULL, NULL, TO_ROOM );
    treasure_goblin_struck( killer, gob, false );
    return true;
}

/*
 * Before make_corpse: the hoard goes into his purse, so it comes out in
 * the corpse as coin piles, and the kill is told to staff.
 */
void treasure_goblin_slain( CHAR_DATA *ch, CHAR_DATA *gob )
{
    CHAR_DATA *who = gob_credit( ch );
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH * 2 + MAX_INPUT_LENGTH];
    char price[MAX_INPUT_LENGTH];
    long per_kill, hoard;

    /* A trap or his own fall is nobody's kill. */
    if ( who == gob )
        who = NULL;
    per_kill = black_market_kill_value( who != NULL ? who->level : 1 );
    /* Where long is 32 bits, two hundred level 59 kills do not fit. */
    hoard = per_kill > LONG_MAX / ( 2 * GOBLIN_HOARD_KILLS )
          ? LONG_MAX / 2 : GOBLIN_HOARD_KILLS * per_kill;

    /* Give or take a quarter. */
    hoard = hoard / 4 * 3 + number_range( 0, 100 ) * ( hoard / 200 );
    hoard = UMAX( 100L, hoard );
    gain_copper( gob, hoard );
    format_price( hoard, price, sizeof(price) );
    /* The rest of the sack goes into the corpse with the coin. */
    {
        int vnum = 0;
        OBJ_INDEX_DATA *pObj;

        if ( number_percent() <= GOBLIN_RARE_CHANCE )
            vnum = black_market_rarity();
        else if ( number_percent() <= GOBLIN_GEAR_CHANCE && who != NULL )
            vnum = black_market_gear_for_level( who->level );
        if ( vnum > 0 && ( pObj = get_obj_index( vnum ) ) != NULL )
        {
            OBJ_DATA *obj = create_object( pObj, -UMAX( 1, pObj->level ) );

            obj_to_char( obj, gob );
            snprintf( line, sizeof(line), "Treasure goblin: his sack held %s (%d).",
                      obj->short_descr, vnum );
            log_string( line );
        }
    }
    act( "$n's sack bursts open as $e falls, and a river of coin pours out!",
         gob, NULL, NULL, TO_ROOM );
    gob_where( gob->in_room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Treasure goblin: slain by %s in %s, dropping "
              "%s.",
              who == NULL ? "nothing" : ( IS_NPC(who) ? who->short_descr : who->name ),
              where, price );
    log_string( line );
    wizinfo( line, LEVEL_IMMORTAL );
}

/* Every mobile pulse, from update_handler. */
void treasure_goblin_update( void )
{
    CHAR_DATA *gob = treasure_goblin;

    if ( gob == NULL )
    {
        /* There is always one: the first at boot, the next shortly after
           each death. Test worlds start without (tests/live_mud.py). */
        if ( getenv( "TOC_NO_GOBLIN" ) != NULL )
            return;
        if ( current_time >= gob_next_spawn && !treasure_goblin_spawn( NULL ) )
            gob_next_spawn = current_time + 60;
        return;
    }
    if ( gob->in_room == NULL )
        return;

    /* Ticks heal mobiles; his wounds are the chase's progress. */
    if ( gob->hit > gob_hp )
        gob->hit = gob_hp;
    else
        gob_hp = gob->hit;

    /* He runs all day. */
    gob->move = gob->max_move;

    /* Nothing else lifts a stun from a mobile that never attacks, and
       nothing stands him up: a stunning blow, a sleep spell or a bash
       holds him a few seconds, never for the rest of the fight. */
    if ( gob->hit > 0
    &&   ( IS_AFFECTED2(gob, AFF2_STUNNED) || IS_AFFECTED(gob, AFF_SLEEP)
        || ( gob->position >= POS_STUNNED && gob->position < POS_FIGHTING ) )
    &&   number_percent() <= GOBLIN_UNSTUN_ODDS )
    {
        affect_strip( gob, gsn_stunning_blow );
        affect_strip( gob, gsn_sleep );
        REMOVE_BIT( gob->affected_by2, AFF2_STUNNED );
        REMOVE_BIT( gob->affected_by, AFF_SLEEP );
        gob->position = gob->fighting != NULL ? POS_FIGHTING : POS_STANDING;
        act( "$n shakes $s head and scrambles up, no longer dazed.", gob, NULL, NULL, TO_ROOM );
    }

    if ( gob_has_company( gob ) )
        gob_last_company = current_time;
    if ( getenv( "TOC_GOBLIN_STILL" ) != NULL || gob_pinned( gob ) )
        return;

    /* A chase not kept up: a tick without a blow, and he opens a portal;
       a pulse later he is through it, unless a blow collapsed it. */
    if ( gob_chased )
    {
        if ( gob_portal_at != 0 )
        {
            if ( current_time >= gob_portal_at )
                gob_teleport( gob, NULL, current_time - gob_last_company >= GOBLIN_ALONE
                              ? "left alone after a chase" : "nobody struck him" );
        }
        else if ( current_time - gob_last_hit >= GOBLIN_ALONE )
        {
            gob_portal_at = current_time + 1;
            act( "$n cackles and starts tearing open a shimmering portal!",
                 gob, NULL, NULL, TO_ROOM );
        }
        return;
    }
    if ( gob_has_company( gob ) )
        return;
    /* Too long in one area: across the world to another. */
    if ( gob->in_room->area != gob_area )
    {
        gob_area = gob->in_room->area;
        gob_area_since = current_time;
    }
    else if ( current_time - gob_area_since >= GOBLIN_AREA_MAX )
    {
        gob_teleport( gob, gob_area, "too long in one area" );
        return;
    }
    if ( current_time >= gob_next_drift )
        gob_teleport( gob, NULL, "drifting" );
    else if ( current_time >= gob_next_step )
    {
        int door = gob_pick_exit( gob );

        gob_next_step = current_time + number_range( GOBLIN_STEP_MIN, GOBLIN_STEP_MAX );
        if ( door >= 0 )
            move_char( gob, door, false );
    }
}

void do_goblin( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *gob = treasure_goblin;

    one_argument( argument, arg );

    if ( arg[0] == '\0' || !str_prefix( arg, "status" ) )
    {
        if ( gob == NULL || gob->in_room == NULL )
            snprintf( buf, sizeof(buf), "There is no treasure goblin; the next "
                      "appears in about %ld seconds.\n\r",
                      (long) UMAX( 0, gob_next_spawn - current_time ) );
        else
            snprintf( buf, sizeof(buf), "The treasure goblin is in room %d (%s), "
                      "%d/%d hit points%s.\n\r", gob->in_room->vnum,
                      gob->in_room->name, gob->hit, gob->max_hit,
                      gob_chased ? ", being chased" : "" );
        send_to_char( buf, ch );
        send_to_char( "Syntax: goblin [status|spawn|here|dismiss]\n\r", ch );
        return;
    }

    if ( !str_prefix( arg, "spawn" ) || !str_prefix( arg, "here" ) )
    {
        bool here = !str_prefix( arg, "here" );

        if ( gob != NULL && here )
            treasure_goblin_dismiss();
        else if ( gob != NULL )
        {
            send_to_char( "There is one already; GOBLIN HERE brings it to you.\n\r", ch );
            return;
        }
        if ( !treasure_goblin_spawn( here ? ch->in_room : NULL ) )
        {
            send_to_char( "No goblin would come.\n\r", ch );
            return;
        }
        snprintf( buf, sizeof(buf), "The treasure goblin is in room %d.\n\r",
                  treasure_goblin->in_room->vnum );
        send_to_char( buf, ch );
        snprintf( buf, sizeof(buf), "%s called a treasure goblin.", ch->name );
        log_string( buf );
        return;
    }

    if ( !str_prefix( arg, "dismiss" ) )
    {
        if ( gob == NULL )
        {
            send_to_char( "There is no treasure goblin.\n\r", ch );
            return;
        }
        treasure_goblin_dismiss();
        send_to_char( "The treasure goblin is gone; another will come.\n\r", ch );
        return;
    }

    send_to_char( "Syntax: goblin [status|spawn|here|dismiss]\n\r", ch );
}
