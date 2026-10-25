/***************************************************************************
 * disaster.c -- area disasters and the Great Black Dragon.
 *
 * Owner, 2026-10-23: fix the disasters, rework them, and make the black
 * dragon something to meet. A disaster strikes an area somebody is in, at
 * random or from staff with DISASTER, and runs like this:
 *
 * - It is announced first. The cycle that strikes only warns the area --
 *   the ground trembles, the wind rises -- and the first blow lands on the
 *   next cycle, six or seven seconds later. Until then nothing hurt anyone
 *   who had a chance to see it coming.
 * - Each later cycle it ends half the time, or strikes again. A brush fire,
 *   a tidal wave and the dragon strike once.
 * - It never kills. A blow leaves at least one hit point, and an
 *   earthquake knocks a character off their feet for a moment instead of
 *   stunning them until the next tick.
 * - Shelter: staff, characters below DISASTER_MIN_LEVEL, and anybody in a
 *   safe room, the Temple, the altar or an arena are spared. So are Mud
 *   School and Limbo, which are never struck.
 *
 * The dragon: a vast shadow circles the area, and on the next cycle the
 * Great Black Dragon snatches one character standing outdoors, carries
 * them to another room of the same area and lands beside them, scaled to
 * their level. It is not aggressive. KILL it for its hoard, or walk away;
 * it takes off after DRAGON_WAIT seconds, or soon after its prey leaves.
 *
 * Test worlds turn the random strikes off (TOC_NO_DISASTERS, set by
 * tests/live_mud.py); DISASTER still works there.
 ***************************************************************************/

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"

extern AREA_DATA *area_first;

#define DISASTER_CHANCE      2       /* in 10,000, per occupied area per cycle */
#define DISASTER_MIN_LEVEL   10      /* below this, the gods shelter you */
#define MOB_VNUM_BLACK_DRAGON 4474
#define DRAGON_WAIT          180     /* seconds it waits to be fought */
#define DRAGON_PREY_GONE     15      /* seconds after its prey leaves */
#define DRAGON_HOARD_KILLS   40      /* its coin, in kills of the prey's level */
#define DRAGON_RARE_CHANCE   10      /* a black market rarity besides */

const char *const disaster_name[DISASTER_COUNT] =
{
    "none", "a flood", "a lightning storm", "an earthquake", "a tornado",
    "a sand storm", "a brush fire", "a tidal wave", "the black dragon"
};

/* The words staff type: DISASTER <word>. */
static const char *const disaster_word[DISASTER_COUNT] =
{
    "none", "flood", "lightning", "earthquake", "tornado",
    "sandstorm", "fire", "tidal", "dragon"
};

/* What the area hears on the cycle a disaster strikes, a cycle before it
   hurts anybody. */
static const char *const disaster_warning[DISASTER_COUNT] =
{
    "",
    "Far off, you hear a low roar of rushing water, growing louder.",
    "The sky darkens, and thunder rolls closer with every breath.",
    "The ground begins to tremble beneath your feet.",
    "The wind rises to a howl, and the sky turns a sickly green.",
    "A wall of darkness rises on the horizon, racing toward you.",
    "You smell smoke on the wind, and the air turns hot and dry.",
    "The water draws back from the shore, strangely, all at once.",
    "A vast shadow sweeps across the ground. Something enormous is "
        "circling overhead."
};

/* And when it is over. */
static const char *const disaster_ending[DISASTER_COUNT] =
{
    "",
    "The flood waters drain away.",
    "The storm rumbles off into the distance.",
    "The tremors fade, and the ground is still again.",
    "The wind dies away, and the sky clears.",
    "The sand settles, and the air clears.",
    "The fire burns itself out.",
    "The sea settles back to its old shore.",
    "The shadow passes on."
};

static CHAR_DATA *dragon = NULL;        /* the one dragon in the world */
static CHAR_DATA *dragon_prey = NULL;   /* who it carried off */
static time_t dragon_leaves = 0;        /* when it takes off unfought */
static int dragon_prey_level = 0;       /* sizes the hoard, even if they quit */
/* For the dragon achievements: whether its prey ever struck it, the prey's
   death count when taken (a death since means it did not get away), and
   whether staff set it on somebody -- a demonstration earns nothing. */
static bool dragon_prey_struck = false;
static long dragon_prey_deaths = 0;
static bool dragon_by_staff = false;


/* The disaster type a word names, or 0. */
static int disaster_lookup( const char *word )
{
    int type;

    if ( word == NULL || word[0] == '\0' )
        return 0;
    for ( type = 1; type < DISASTER_COUNT; type++ )
        if ( !str_prefix( word, disaster_word[type] ) )
            return type;
    return 0;
}

/* Whether an area is never struck: Mud School and Limbo. */
static bool disaster_spares_area( const AREA_DATA *area )
{
    ROOM_INDEX_DATA *school = get_room_index( ROOM_VNUM_SCHOOL );
    ROOM_INDEX_DATA *limbo = get_room_index( ROOM_VNUM_LIMBO );

    return ( school != NULL && school->area == area )
        || ( limbo != NULL && limbo->area == area );
}

/* Whether a room shelters whoever is in it. */
static bool disaster_room_shelters( const ROOM_INDEX_DATA *room )
{
    return room == NULL
        || IS_SET(room->room_flags, ROOM_SAFE)
        || IS_SET(room->room_flags, ROOM_ARENA)
        || room->vnum == ROOM_VNUM_TEMPLE
        || room->vnum == ROOM_VNUM_ALTAR;
}

/* Whether a disaster passes this character by. */
static bool disaster_spares( CHAR_DATA *vch )
{
    return IS_NPC(vch)
        || IS_IMMORTAL(vch)
        || vch->level < DISASTER_MIN_LEVEL
        || vch->in_room == NULL
        || disaster_room_shelters( vch->in_room );
}

/* A disaster's blow: never the last hit point. Hit points come off
   directly rather than through damage(), which would make the character
   their own attacker -- feeding the dark's drain and a vampiric weapon
   from their own wounds. */
static void disaster_harm( CHAR_DATA *vch, int dam )
{
    dam = UMIN( dam, vch->hit - 1 );
    if ( dam <= 0 )
        return;
    vch->hit -= dam;
    update_pos( vch );
}

/* Knocked off your feet: a moment's lag, not a stun to the next tick. */
static void disaster_knock_down( CHAR_DATA *vch )
{
    if ( !IS_NPC(vch) && vch->pcdata->mounted )
        return;
    if ( vch->position == POS_STANDING )
        vch->position = POS_SITTING;
    WAIT_STATE( vch, PULSE_VIOLENCE );
}

/* Carried along by water: up to `moves' rooms through open exits that
   lead nowhere deadly, each a real move, so guards and private rooms
   still refuse, and a blow in each. Stops if anything takes them away. */
static void disaster_sweep( CHAR_DATA *vch, int moves, int dam_dice )
{
    for ( ; moves > 0; moves-- )
    {
        ROOM_INDEX_DATA *from = vch->in_room;
        EXIT_DATA *pexit;
        int doors[10];
        int count = 0;
        int door;

        if ( from == NULL )
            return;
        for ( door = 0; door < 10; door++ )
            if ( ( pexit = from->exit[door] ) != NULL
              && !IS_SET(pexit->exit_info, EX_CLOSED)
              && pexit->u1.to_room != NULL
              && !IS_SET(pexit->u1.to_room->room_flags, ROOM_DT)
              && !disaster_room_shelters( pexit->u1.to_room ) )
                doors[count++] = door;
        if ( count == 0 )
            return;
        door = doors[number_range( 0, count - 1 )];
        send_to_char( "You struggle in vain as the water carries you along.\n\r", vch );
        move_char( vch, door, false );
        if ( vch->in_room == from || vch->in_room == NULL
          || vch->position <= POS_STUNNED )
            return;
        act( "$n arrives on a wave of water, spluttering.", vch, NULL, NULL, TO_ROOM );
        disaster_harm( vch, dice( dam_dice, 4 ) );
    }
}

/* One strike of an area's disaster on one character. */
static void disaster_strike_char( CHAR_DATA *vch, int type )
{
    int sector = vch->in_room->sector_type;
    int dam = 0;

    switch ( type )
    {
    case DISASTER_FLOOD:
        send_to_char( "You hear a rushing sound...\n\r", vch );
        if ( sector == SECT_INSIDE )
        {
            send_to_char( "and the building you're in trembles as a wall of water strikes it.\n\r", vch );
            return;
        }
        if ( IS_AFFECTED(vch, AFF_FLYING)
          || ( sector != SECT_UNDERGROUND
            && dice( 3, 8 ) <= get_curr_stat( vch, STAT_DEX ) - 5 ) )
        {
            send_to_char( "and you get yourself out of the water's path just in time!\n\r", vch );
            return;
        }
        send_to_char( sector == SECT_UNDERGROUND
                      ? "and a wall of water slams you against the tunnel walls!\n\r"
                      : "followed by a wall of water that sweeps you off your feet!\n\r", vch );
        act( "$n is carried off by the flood waters.", vch, NULL, NULL, TO_ROOM );
        disaster_sweep( vch, dice( 1, 3 ), 4 );
        return;

    case DISASTER_LIGHTNING:
        if ( sector == SECT_INSIDE || sector == SECT_UNDERGROUND
          || sector == SECT_UNDER_WATER )
        {
            send_to_char( "Thunder shakes the walls around you. Good thing you're under cover.\n\r", vch );
            return;
        }
        send_to_char( "Lightning splits the sky all around you...\n\r", vch );
        if ( saves_spell( vch->level, vch ) )
        {
            send_to_char( "<<BOOM>> That one struck close. Too close.\n\r", vch );
            return;
        }
        send_to_char( "and a bolt strikes you square! <<BOOM>>\n\r", vch );
        act( "A bolt of lightning strikes $n!", vch, NULL, NULL, TO_ROOM );
        disaster_harm( vch, dice( 4, 10 ) );
        return;

    case DISASTER_EARTHQUAKE:
        if ( sector == SECT_WATER_SWIM || sector == SECT_WATER_NOSWIM
          || sector == SECT_AIR || sector == SECT_UNDER_WATER )
            return;
        send_to_char( "The earth heaves under your feet...\n\r", vch );
        if ( saves_spell( vch->level, vch ) )
        {
            send_to_char( "but you keep your footing.\n\r", vch );
            return;
        }
        switch ( sector )
        {
        case SECT_INSIDE:
            send_to_char( "and the ceiling comes down on you!\n\r", vch );
            dam = dice( 2, 10 );
            break;
        case SECT_CITY:
            send_to_char( "and the buildings rain debris on you as they break apart!\n\r", vch );
            dam = dice( 1, 20 );
            break;
        case SECT_FOREST:
            send_to_char( "and the trees around you sway... TIMBER!\n\r", vch );
            dam = dice( 1, 20 );
            break;
        case SECT_HILLS:
            send_to_char( "and rocks break loose and bounce off your head!\n\r", vch );
            dam = dice( 1, 20 );
            break;
        case SECT_MOUNTAIN:
            send_to_char( "and boulders avalanche down on top of you!\n\r", vch );
            dam = dice( 2, 20 );
            break;
        case SECT_UNDERGROUND:
            send_to_char( "and the tunnel begins to collapse all around you!\n\r", vch );
            dam = dice( 2, 20 );
            break;
        default:
            send_to_char( "and fissures open all around you as you are thrown down!\n\r", vch );
            break;
        }
        act( "$n is thrown to the ground!", vch, NULL, NULL, TO_ROOM );
        disaster_harm( vch, dam );
        disaster_knock_down( vch );
        return;

    case DISASTER_TORNADO:
        if ( sector == SECT_UNDERGROUND )
            return;
        send_to_char( sector == SECT_INSIDE
                      ? "The wind tears the roof off the building!\n\r"
                      : "A dark funnel touches down beside you!\n\r", vch );
        if ( saves_spell( vch->level, vch ) )
        {
            send_to_char( "You grab hold of something and hang on until it passes. Phew!\n\r", vch );
            return;
        }
        {
            ROOM_INDEX_DATA *to = random_travel_room( vch, false );

            if ( to == NULL || to == vch->in_room )
                return;
            send_to_char( "OH NO! You've been sucked into the tornado!\n\r", vch );
            act( "$n is sucked into the tornado!", vch, NULL, NULL, TO_ROOM );
            if ( !IS_NPC(vch) && vch->pcdata->mounted )
                do_dismount( vch, "" );
            char_from_room( vch );
            char_to_room( vch, to );
            send_to_char( "\n\r<<<SPLAT>>>\n\rOh, ouch, that hurt!\n\r", vch );
            act( "$n drops out of the sky and lands with a <<<SPLAT>>>.", vch, NULL, NULL, TO_ROOM );
            disaster_harm( vch, vch->hit / 2 );
            do_look( vch, "auto" );
        }
        return;

    case DISASTER_SANDSTORM:
        if ( sector != SECT_DESERT )
            return;
        send_to_char( "The wall of sand reaches you...\n\r", vch );
        if ( saves_spell( vch->level, vch ) )
        {
            send_to_char( "but you find shelter and wait out the sand storm.\n\r", vch );
            return;
        }
        send_to_char( "and you are choking on sand", vch );
        /* The blindness used to land only on somebody already blind. */
        if ( !IS_AFFECTED(vch, AFF_BLIND) )
        {
            AFFECT_DATA af;

            af.type      = (sh_int)skill_lookup( "blindness" );
            af.level     = vch->level;
            af.location  = APPLY_HITROLL;
            af.modifier  = -4;
            af.duration  = (sh_int)dice( 1, 3 );
            af.bitvector = AFF_BLIND;
            af.bitvector2 = 0;
            affect_to_char( vch, &af );
            send_to_char( " and blinded!\n\r", vch );
            act( "$n appears to be blinded.", vch, NULL, NULL, TO_ROOM );
        }
        else
            send_to_char( "!\n\r", vch );
        disaster_harm( vch, dice( 2, 10 ) );
        return;

    case DISASTER_FIRE:
        if ( sector != SECT_FIELD && sector != SECT_FOREST && sector != SECT_HILLS )
            return;
        send_to_char( "A wall of fire comes racing toward you!\n\r", vch );
        if ( saves_spell( vch->level, vch ) )
        {
            send_to_char( "Good thing you're quick on your feet!\n\r", vch );
            return;
        }
        send_to_char( "Oh no! You're surrounded by fire!\n\r", vch );
        disaster_harm( vch, dice( 6, 6 ) );
        return;

    case DISASTER_TIDAL:
        if ( sector != SECT_WATER_SWIM && sector != SECT_WATER_NOSWIM )
            return;
        send_to_char( "A huge wall of water thunders down on you!\n\r", vch );
        act( "A huge wave crashes over $n!", vch, NULL, NULL, TO_ROOM );
        disaster_harm( vch, vch->hit / 3 );
        disaster_sweep( vch, 1, 2 );
        return;
    }
}


/* ------------------------------------------------------------------ */
/* The Great Black Dragon                                              */
/* ------------------------------------------------------------------ */

bool is_disaster_dragon( const CHAR_DATA *ch )
{
    return ch != NULL && ch == dragon;
}

/* From damage(): any blow, landed or missed, the prey aims at the dragon
   that took it (or that the prey's pet aims). */
void disaster_dragon_struck( CHAR_DATA *ch, CHAR_DATA *victim )
{
    if ( ch == NULL || victim == NULL || victim != dragon || dragon_prey == NULL )
        return;
    if ( IS_NPC(ch) && ch->master != NULL )
        ch = ch->master;
    if ( ch == dragon_prey )
        dragon_prey_struck = true;
}

void disaster_dragon_forget( CHAR_DATA *ch )
{
    if ( ch == NULL )
        return;
    if ( ch == dragon )
    {
        dragon = NULL;
        dragon_prey = NULL;
    }
    else if ( ch == dragon_prey )
        dragon_prey = NULL;
}

/* How long the dragon waits to be fought; TOC_DRAGON_WAIT shortens it
   for the live tests. */
static int dragon_wait( void )
{
    const char *env = getenv( "TOC_DRAGON_WAIT" );
    int seconds = env != NULL ? atoi( env ) : 0;

    return seconds > 0 ? seconds : DRAGON_WAIT;
}

/* Whether the dragon may snatch this character: a mortal at least
   DISASTER_MIN_LEVEL, standing outdoors, not fighting, not riding,
   somewhere no flag keeps them. */
static bool dragon_can_snatch( CHAR_DATA *vch )
{
    ROOM_INDEX_DATA *room = vch->in_room;

    return !disaster_spares( vch )
        && vch->desc != NULL
        && vch->fighting == NULL
        && vch->position >= POS_RESTING
        && !IS_SET(room->room_flags, ROOM_INDOORS)
        && room->sector_type != SECT_INSIDE
        && room->sector_type != SECT_UNDERGROUND
        && room->sector_type != SECT_UNDER_WATER
        && !IS_SET(room->room_flags, ROOM_NO_RECALL)
        && !IS_SET(room->room_flags, ROOM_JAIL);
}

/* Where it lands with them: another outdoor room of the same area --
   whatever lives there suits the level they chose to be at -- empty of
   players, one a mobile may stand in, and one the character could have
   walked to without a guard or a gate turning them away. */
static ROOM_INDEX_DATA *dragon_landing( CHAR_DATA *vch )
{
    int attempts;

    for ( attempts = 0; attempts < 60; attempts++ )
    {
        ROOM_INDEX_DATA *room = random_scatter_room( vch->in_room->area );
        CHAR_DATA *rch;
        bool occupied = false;

        if ( room == NULL )
            return NULL;
        if ( room == vch->in_room
          || IS_SET(room->room_flags, ROOM_INDOORS)
          || IS_SET(room->room_flags, ROOM_NO_MOB)
          || IS_SET(room->room_flags, ROOM_SAFE)
          || IS_SET(room->room_flags, ROOM_PRIVATE)
          || IS_SET(room->room_flags, ROOM_SOLITARY)
          || IS_SET(room->room_flags, ROOM_DT)
          || IS_SET(room->room_flags, ROOM_NO_RECALL)
          || IS_SET(room->room_flags, ROOM_JAIL)
          || IS_SET(room->room_flags, ROOM_TELEPORT)
          || IS_SET(room->room_flags, ROOM_RIVER)
          || room->sector_type == SECT_INSIDE
          || room->sector_type == SECT_AIR
          || room->sector_type == SECT_WATER_NOSWIM
          || room->sector_type == SECT_UNDER_WATER
          || disaster_room_shelters( room )
          || !can_see_room( vch, room )
          || travel_spell_refuses( vch, room ) )
            continue;
        for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
            if ( !IS_NPC(rch) )
                occupied = true;
        if ( !occupied )
            return room;
    }
    return NULL;
}

/* Make the dragon a fight for this character: two levels above them,
   three times the hit points of a typical mobile of that level -- a long
   fight -- and that level's typical blow, the training dummy's curve
   (dummy.c). Its own skills -- bash, disarm, dodge, parry, a tail
   sweep, trip, and an extra attack -- make it hard. */
static void dragon_scale( CHAR_DATA *drake, int level )
{
    long blow;
    int i;

    level = URANGE( DISASTER_MIN_LEVEL, level + 2, MAX_LEVEL - 10 );
    drake->level = (sh_int)level;
    drake->max_hit = (int)UMIN( 30000L, dummy_typical_hp( level ) * 3 );
    drake->hit = drake->max_hit;
    drake->hitroll = (sh_int)( level / 3 + 2 );
    drake->damroll = (sh_int)( level / 5 + 1 );
    blow = (long)level * 2 + 6;
    drake->damage[0] = (sh_int)UMAX( 1, blow / 6 );
    drake->damage[1] = 6;
    drake->damage[2] = (sh_int)UMAX( 0, blow / 3 );
    for ( i = 0; i < 4; i++ )
        drake->armor[i] = (sh_int)( -level * 3 );
    drake->alignment = -1000;
}

/* Snatch one character in the area, or the one staff named. */
static bool dragon_snatch( AREA_DATA *area, CHAR_DATA *named, CHAR_DATA *staff )
{
    MOB_INDEX_DATA *pDragon = get_mob_index( MOB_VNUM_BLACK_DRAGON );
    CHAR_DATA *candidates[64];
    CHAR_DATA *vch;
    CHAR_DATA *prey = named;
    ROOM_INDEX_DATA *landing;
    ROOM_INDEX_DATA *from;
    char buf[MAX_STRING_LENGTH];
    int count = 0;
    LIST_ITERATOR iter;

    if ( dragon != NULL || pDragon == NULL )
    {
        if ( staff != NULL )
            send_to_char( dragon != NULL ? "The dragon is already about.\n\r"
                                         : "There is no dragon mobile (4474).\n\r", staff );
        return false;
    }
    if ( prey == NULL )
    {
        FOR_EACH_CHARACTER( iter, vch )
            if ( count < 64 && vch->in_room != NULL && vch->in_room->area == area
              && dragon_can_snatch( vch ) )
                candidates[count++] = vch;
        if ( count == 0 )
            return false;
        prey = candidates[number_range( 0, count - 1 )];
    }
    else if ( !dragon_can_snatch( prey ) )
    {
        if ( staff != NULL )
            send_to_char( "The dragon cannot reach them: they must be a mortal of level 10 or "
                          "more, outdoors and out of a fight, somewhere they may be carried "
                          "from.\n\r", staff );
        return false;
    }
    if ( ( landing = dragon_landing( prey ) ) == NULL )
    {
        if ( staff != NULL )
            send_to_char( "There is nowhere in that area for the dragon to land.\n\r", staff );
        return false;
    }

    from = prey->in_room;
    send_to_char( "\n\rWith a roar like a landslide, the Great Black Dragon swoops out of "
                  "the sky and snatches you up in its claws!\n\r", prey );
    act( "With a roar like a landslide, a huge black dragon swoops out of the sky "
         "and carries $n off in its claws!", prey, NULL, NULL, TO_ROOM );
    if ( !IS_NPC(prey) && prey->pcdata->mounted )
        do_dismount( prey, "" );
    char_from_room( prey );
    char_to_room( prey, landing );
    send_to_char( "The ground races past far below. Then the dragon drops you, and lands "
                  "beside you with a crash.\n\r\n\r", prey );
    do_look( prey, "auto" );

    dragon = create_mobile( pDragon );
    dragon->spec_fun = NULL;            /* spec_kidnapper is retired */
    REMOVE_BIT( dragon->act, ACT_AGGRESSIVE );
    SET_BIT( dragon->act, ACT_SENTINEL );
    dragon_scale( dragon, prey->level );
    char_to_room( dragon, landing );
    dragon_prey = prey;
    dragon_prey_level = prey->level;
    dragon_leaves = current_time + dragon_wait();
    dragon_prey_struck = false;
    dragon_prey_deaths = prey->pcdata != NULL ? prey->pcdata->achievement_deaths : 0;
    dragon_by_staff = staff != NULL || ( area != NULL && area->disaster_by_staff );
    act( "$n folds its wings and regards you, smoke curling from its nostrils.",
         dragon, NULL, prey, TO_VICT );
    snprintf( buf, sizeof(buf),
              "{0BIt has not decided whether you are prey or a meal. KILL DRAGON to "
              "fight it for its hoard, or walk away -- it will not wait long.{00\n\r" );
    send_to_char( buf, prey );

    /* The log is published: it says who and from which area, never where
       the dragon is waiting. Staff online hear the room. */
    snprintf( buf, sizeof(buf), "Black dragon: snatched %s (level %d) from %s; "
              "the dragon is level %d.", prey->name, prey->level,
              from->area != NULL && from->area->file_name != NULL
              ? from->area->file_name : "?", dragon->level );
    log_string( buf );
    snprintf( buf, sizeof(buf), "The black dragon carried %s from room %d to room %d.",
              prey->name, from->vnum, landing->vnum );
    wizinfo( buf, LEVEL_IMMORTAL );
    if ( staff != NULL )
        send_to_char( "Done.\n\r", staff );
    return true;
}

/* The dragon's own clock, each disaster cycle: it waits to be fought,
   and takes off once nobody does. */
static void dragon_update( void )
{
    char buf[MAX_STRING_LENGTH];

    if ( dragon == NULL || dragon->in_room == NULL )
        return;
    if ( dragon->fighting != NULL )
    {
        dragon_leaves = UMAX( dragon_leaves, current_time + DRAGON_PREY_GONE );
        return;
    }
    if ( dragon_prey == NULL || dragon_prey->in_room != dragon->in_room )
        dragon_leaves = UMIN( dragon_leaves, current_time + DRAGON_PREY_GONE );
    if ( current_time < dragon_leaves )
        return;

    /* Discretion Is an Option: the prey walked away, alive, never having
       raised a hand to it. */
    if ( dragon_prey != NULL && !dragon_by_staff && !dragon_prey_struck
      && dragon_prey->pcdata != NULL
      && dragon_prey->pcdata->achievement_deaths == dragon_prey_deaths
      && dragon_prey->in_room != dragon->in_room && dragon_prey->hit > 0 )
        achievement_record_event( dragon_prey, ACHIEVEMENT_EVENT_DRAGON_DISCRETION, true );

    act( "$n spreads its vast wings, laughs at you all, and takes to the sky.",
         dragon, NULL, NULL, TO_ROOM );
    snprintf( buf, sizeof(buf), "Black dragon: took off unfought%s.",
              dragon->hit < dragon->max_hit ? " (wounded)" : "" );
    log_string( buf );
    extract_char( dragon, true );       /* forgets it */
}

/* Its hoard, into its purse before make_corpse, as the goblin's goes. */
/* A piece of the hoard, carried in its purse until make_corpse empties it.
   Returns the short description for the log, or NULL. */
static const char *dragon_hoard_item( CHAR_DATA *drake, int vnum )
{
    OBJ_INDEX_DATA *pObj;
    OBJ_DATA *obj;

    if ( vnum <= 0 || ( pObj = get_obj_index( vnum ) ) == NULL )
        return NULL;
    obj = create_object( pObj, -UMAX( 1, pObj->level ) );
    obj_to_char( obj, drake );
    return obj->short_descr;
}

/* Its hoard goes into its purse before make_corpse, as the goblin's goes:
   coin worth DRAGON_HOARD_KILLS kills of the level of the one it carried
   off, a good piece of gear for that level -- the black market's pick of
   the best placed piece for a random slot, within five levels below it
   (owner, 2026-10-23) -- and now and then a rarity besides. */
void disaster_dragon_slain( CHAR_DATA *ch, CHAR_DATA *drake )
{
    CHAR_DATA *who = ch;
    char buf[MAX_STRING_LENGTH];
    char price[MAX_INPUT_LENGTH];
    const char *gear, *rare = NULL;
    long per_kill, hoard;
    int level = dragon_prey_level > 0 ? dragon_prey_level : drake->level - 2;

    if ( who != NULL && IS_NPC(who) && who->master != NULL )
        who = who->master;
    per_kill = black_market_kill_value( level );
    hoard = per_kill > LONG_MAX / ( 2 * DRAGON_HOARD_KILLS )
          ? LONG_MAX / 2 : DRAGON_HOARD_KILLS * per_kill;
    hoard = hoard / 4 * 3 + number_range( 0, 100 ) * ( hoard / 200 );
    hoard = UMAX( 100L, hoard );
    gain_copper( drake, hoard );
    format_price( hoard, price, sizeof(price) );

    gear = dragon_hoard_item( drake, black_market_gear_for_level( level ) );
    if ( gear == NULL || number_percent() <= DRAGON_RARE_CHANCE )
        rare = dragon_hoard_item( drake, black_market_rarity() );

    act( "$n crashes to the ground, and the hoard it carried spills across the earth!",
         drake, NULL, NULL, TO_ROOM );
    snprintf( buf, sizeof(buf), "Black dragon: slain by %s, dropping %s, %s%s%s.",
              who == NULL ? "nothing" : IS_NPC(who) ? who->short_descr : who->name,
              price, gear != NULL ? gear : "no gear",
              rare != NULL ? " and " : "", rare != NULL ? rare : "" );
    log_string( buf );
    wizinfo( buf, LEVEL_IMMORTAL );

    /* Dragon Trouble for everyone in at the kill; You Picked the Wrong
       Passenger for the one it carried off, if they struck it and are
       there for its end. A staff demonstration earns nothing. */
    if ( drake == dragon && !dragon_by_staff && who != NULL && drake->in_room != NULL )
    {
        achievement_party_count( who, drake->in_room, ACH_CTR_DRAGON_KILLS );
        if ( dragon_prey != NULL && dragon_prey_struck
          && dragon_prey->in_room == drake->in_room && !IS_TRUSTED( dragon_prey, LEVEL_IMMORTAL )
          && ( dragon_prey == who || is_same_group( dragon_prey, who ) ) )
            achievement_record_event( dragon_prey, ACHIEVEMENT_EVENT_DRAGON_PASSENGER, true );
    }
}


/* ------------------------------------------------------------------ */
/* Disasters                                                           */
/* ------------------------------------------------------------------ */

/* Tell everyone in an area, sheltered or not. */
static void disaster_tell_area( AREA_DATA *area, const char *text )
{
    CHAR_DATA *vch;
    LIST_ITERATOR iter;

    FOR_EACH_CHARACTER( iter, vch )
        if ( !IS_NPC(vch) && vch->in_room != NULL && vch->in_room->area == area )
        {
            send_to_char( text, vch );
            send_to_char( "\n\r", vch );
        }
}

/* Start a disaster in an area: warn it, and strike on the next cycle. */
static void disaster_begin( AREA_DATA *area, int type )
{
    char buf[MAX_STRING_LENGTH];

    area->disaster_type = (sh_int)type;
    area->disaster_warned = false;
    area->disaster_by_staff = false;
    disaster_tell_area( area, disaster_warning[type] );
    snprintf( buf, sizeof(buf), "%s has been struck by %s.",
              area_shown_name( area->name ), disaster_name[type] );
    wizinfo( buf, LEVEL_IMMORTAL );
    snprintf( buf, sizeof(buf), "Disaster: %s in %s.", disaster_name[type],
              area->file_name != NULL ? area->file_name : "?" );
    log_string( buf );
}

static void disaster_end( AREA_DATA *area, bool quietly )
{
    char buf[MAX_STRING_LENGTH];
    int type = area->disaster_type;

    bool by_staff = area->disaster_by_staff;
    DESCRIPTOR_DATA *d;

    area->disaster_type = 0;
    area->disaster_warned = false;
    area->disaster_by_staff = false;
    if ( quietly || type <= 0 || type >= DISASTER_COUNT )
        return;
    disaster_tell_area( area, disaster_ending[type] );

    /* Everyone it struck who is still here, alive, at its end lived
       through it. The dragon is not one of these. */
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *vch = d->character;

        if ( d->connected != CON_PLAYING || vch == NULL || IS_NPC(vch)
          || vch->pcdata == NULL || vch->pcdata->disaster_area != area
          || vch->pcdata->disaster_kind != type )
            continue;
        vch->pcdata->disaster_area = NULL;
        vch->pcdata->disaster_kind = 0;
        /* Alive at the end, with no death since it struck: a flood or a
           tornado that carried somebody out of the area still counts. */
        if ( by_staff || type == DISASTER_DRAGON || vch->hit <= 0
          || vch->position <= POS_STUNNED
          || vch->pcdata->achievement_deaths != vch->pcdata->disaster_deaths )
            continue;
        achievement_record_event( vch,
            (achievement_event_type)( ACHIEVEMENT_EVENT_DISASTER_FIRST + type ), true );
    }
    snprintf( buf, sizeof(buf), "%s is no longer a disaster area.",
              area_shown_name( area->name ) );
    wizinfo( buf, LEVEL_IMMORTAL );
}

/* A random strike: which disaster, given the weather. 0 when the roll
   names a storm the sky is not making. */
static int disaster_roll( void )
{
    int pick = number_percent();

    if ( pick <= 15 )
        return weather_info.sky >= SKY_RAINING ? DISASTER_FLOOD : 0;
    if ( pick <= 35 )
        /* A lightning storm needs lightning; it used to need clouds. */
        return weather_info.sky == SKY_LIGHTNING ? DISASTER_LIGHTNING : 0;
    if ( pick <= 50 )
        return DISASTER_EARTHQUAKE;
    if ( pick <= 70 )
        return DISASTER_TORNADO;
    if ( pick <= 75 )
        return DISASTER_SANDSTORM;
    if ( pick <= 80 )
        return DISASTER_FIRE;
    if ( pick <= 90 )
        return DISASTER_TIDAL;
    return DISASTER_DRAGON;
}

/* Every six or seven seconds, from update_handler. */
void disaster_update( void )
{
    AREA_DATA *pArea;
    CHAR_DATA *vch;
    LIST_ITERATOR iter;
    bool random_off = getenv( "TOC_NO_DISASTERS" ) != NULL;

    dragon_update();

    for ( pArea = area_first; pArea != NULL; pArea = pArea->next )
    {
        int type;

        if ( disaster_spares_area( pArea ) )
            continue;
        if ( pArea->nplayer == 0 )
        {
            disaster_end( pArea, true );
            continue;
        }

        if ( pArea->disaster_type <= 0 )
        {
            if ( random_off || number_range( 1, 10000 ) > DISASTER_CHANCE )
                continue;
            if ( ( type = disaster_roll() ) > 0 )
                disaster_begin( pArea, type );
            continue;                   /* warned; it strikes next cycle */
        }

        type = pArea->disaster_type;
        if ( pArea->disaster_warned && number_percent() <= 50 )
        {
            disaster_end( pArea, false );
            continue;
        }
        pArea->disaster_warned = true;

        if ( type == DISASTER_DRAGON )
        {
            if ( !dragon_snatch( pArea, NULL, NULL ) )
                disaster_end( pArea, false );
            else
                disaster_end( pArea, true );
            continue;
        }

        FOR_EACH_CHARACTER( iter, vch )
        {
            if ( vch->in_room == NULL || vch->in_room->area != pArea
              || disaster_spares( vch ) )
                continue;
            if ( !IS_NPC(vch) && vch->pcdata != NULL )
            {
                if ( vch->pcdata->disaster_area != pArea
                  || vch->pcdata->disaster_kind != type )
                    vch->pcdata->disaster_deaths = vch->pcdata->achievement_deaths;
                vch->pcdata->disaster_area = pArea;
                vch->pcdata->disaster_kind = type;
            }
            disaster_strike_char( vch, type );
        }
        if ( type == DISASTER_FIRE || type == DISASTER_TIDAL )
            disaster_end( pArea, false );
    }
}


/*
 * DISASTER                      areas suffering one now
 * DISASTER <kind>               strike the area you stand in
 * DISASTER STOP                 end the one in your area
 * DISASTER DRAGON <player>      the dragon takes that player, now
 */
void do_disaster( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    AREA_DATA *pArea;
    int type;

    argument = one_argument( argument, arg );
    if ( arg[0] == '\0' )
    {
        bool any = false;

        for ( pArea = area_first; pArea != NULL; pArea = pArea->next )
        {
            if ( pArea->disaster_type <= 0 || pArea->disaster_type >= DISASTER_COUNT )
                continue;
            snprintf( buf, sizeof(buf), "  %-40s %s%s\n\r", area_shown_name( pArea->name ),
                      disaster_name[pArea->disaster_type],
                      pArea->disaster_warned ? "" : " (warned, strikes next)" );
            send_to_char( buf, ch );
            any = true;
        }
        if ( !any )
            send_to_char( "No area is suffering a disaster.\n\r", ch );
        if ( dragon != NULL && dragon->in_room != NULL )
        {
            snprintf( buf, sizeof(buf), "The black dragon (level %d) waits in room %d with %s.\n\r",
                      dragon->level, dragon->in_room->vnum,
                      dragon_prey != NULL ? dragon_prey->name : "nobody" );
            send_to_char( buf, ch );
        }
        send_to_char( "Syntax: disaster <flood|lightning|earthquake|tornado|sandstorm|fire|"
                      "tidal|dragon> | disaster stop | disaster dragon <player>\n\r", ch );
        return;
    }

    if ( ch->in_room == NULL )
        return;
    pArea = ch->in_room->area;

    if ( !str_cmp( arg, "stop" ) )
    {
        if ( pArea->disaster_type <= 0 )
        {
            send_to_char( "This area is not suffering a disaster.\n\r", ch );
            return;
        }
        disaster_end( pArea, false );
        send_to_char( "Ended.\n\r", ch );
        return;
    }

    if ( ( type = disaster_lookup( arg ) ) == 0 )
    {
        send_to_char( "No such disaster. Type DISASTER for the list.\n\r", ch );
        return;
    }

    if ( type == DISASTER_DRAGON && argument[0] != '\0' )
    {
        CHAR_DATA *victim = get_char_world( ch, argument );

        if ( victim == NULL || IS_NPC(victim) )
        {
            send_to_char( "They aren't here.\n\r", ch );
            return;
        }
        if ( rank_protects( ch, victim ) )
        {
            send_to_char( "They outrank you.\n\r", ch );
            return;
        }
        dragon_snatch( victim->in_room->area, victim, ch );
        return;
    }

    if ( disaster_spares_area( pArea ) )
    {
        send_to_char( "Mud School and Limbo are never struck.\n\r", ch );
        return;
    }
    if ( pArea->disaster_type > 0 )
    {
        send_to_char( "This area is already suffering one. DISASTER STOP first.\n\r", ch );
        return;
    }
    disaster_begin( pArea, type );
    pArea->disaster_by_staff = true;
    snprintf( buf, sizeof(buf), "%s strikes next cycle. DISASTER STOP ends it.\n\r",
              capitalize( disaster_name[type] ) );
    send_to_char( buf, ch );
}
