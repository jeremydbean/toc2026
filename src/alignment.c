/*
 * Alignment, rebuilt (owner, 2026-10-21: "reimagine and rebuild the
 * alignment system to be more modern").
 *
 * Alignment is still one number from -1000 to 1000, saved as it always
 * was, and IS_GOOD / IS_EVIL still begin at 300 and -300, so every item
 * and spell that reads them means what it meant. What changed is
 * everything around the number:
 *
 *  - Seven named tiers: Paragon, Virtuous and Kind of the light; Balanced;
 *    Ruthless, Vile and Fiend of the dark. ALIGNMENT shows where you
 *    stand, what you get and how to move; SCORE names the tier.
 *  - You are what you slay. Killing the evil moves you toward the light
 *    and killing the good toward the dark, a point for every hundred of
 *    the victim's alignment, half for a foe eight levels below you and
 *    nothing fifteen below. The neutral move nothing, so nobody drifts by
 *    accident and nobody is stuck at an end: a Fiend who wants the light
 *    hunts evil. A quest target of either side moves you further.
 *  - DEVOTE at the Temple steers on purpose: a hundred points toward the
 *    light, the dark or the balance, for twenty kills' coin, once every
 *    thirty minutes.
 *  - Each tier gives something, and more the deeper you go: the light
 *    regenerates faster and strikes harder with holy power, the dark
 *    drains life with its blows and strikes harder with negative power,
 *    the balanced shrug off a share of both. Slaying the other side pays
 *    more experience; nothing pays less (the old table halved a kill for
 *    choosing the wrong victim). Shopkeepers of your side charge up to a
 *    tenth less; those of the other side a tenth more, and pay a tenth less.
 *  - Gear limits stay, and say which tier they turn away.
 *
 * Perks are for players. Mobiles keep their alignment for what it always
 * did -- spells, gear, and which side a kill serves.
 */

#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"

#define ALIGN_PERK_STEP     5   /* % per tier: regeneration, holy, negative */
#define ALIGN_DRAIN_STEP    2   /* % of a blow returned, per dark tier */
#define ALIGN_BALANCE_WARD  15  /* % off holy and negative for the balanced */
#define ALIGN_XP_STEP       10  /* % per tier for slaying the other side */
#define ALIGN_PRICE_SHARE   10  /* a shop's price moves by a tenth */

/* Tiers from the light down. IS_GOOD is Kind and above, IS_EVIL Ruthless
   and below, so the gear and spells that read those keep their meaning. */
int alignment_tier( int a )
{
    if ( a >= 900 )  return 3;
    if ( a >= 550 )  return 2;
    if ( a >= 300 )  return 1;
    if ( a > -300 )  return 0;
    if ( a > -550 )  return -1;
    if ( a > -900 )  return -2;
    return -3;
}

const char *alignment_tier_name( int a )
{
    static const char *const names[7] =
        { "Fiend", "Vile", "Ruthless", "Balanced", "Kind", "Virtuous", "Paragon" };

    return names[alignment_tier( a ) + 3];
}

/* -1 evil, 0 neutral, 1 good: the same lines IS_EVIL and IS_GOOD draw. */
int alignment_side( int a )
{
    return a >= 300 ? 1 : a <= -300 ? -1 : 0;
}

/* Where tier 1, 2 or 3 of the light begins; the dark mirrors it. */
static int tier_floor( int tier )
{
    static const int floors[4] = { 0, 300, 550, 900 };

    return floors[URANGE( 1, tier, 3 )];
}

/*
 * Worn gear that will not stay on this side comes off, as it always has
 * after a kill -- now also after a DEVOTE, a quest or a dark spell.
 */
void alignment_check_gear( CHAR_DATA *ch )
{
    OBJ_DATA *obj, *obj_next;

    if ( ch == NULL || IS_NPC(ch) || ch->in_room == NULL )
        return;
    for ( obj = ch->carrying; obj != NULL; obj = obj_next )
    {
        obj_next = obj->next_content;
        if ( obj->wear_loc == WEAR_NONE || !alignment_rejects_obj( ch, obj ) )
            continue;
        act( "You are zapped by $p.", ch, obj, NULL, TO_CHAR );
        act( "$n is zapped by $p.",   ch, obj, NULL, TO_ROOM );
        obj_from_char( obj );
        obj_to_room( obj, ch->in_room );
    }
}

/*
 * Every change to a player's alignment goes through here: it clamps, says
 * a change of tier to everyone, because a tier is what the change is for,
 * and -- when loud -- says the small moves to anyone with DAMAGENUMBERS on
 * and takes off gear that will not stay on the new side. A vampiric weapon
 * moves its wielder a point a hit and is quiet: one line a swing was
 * spam, and zapping the weapon mid-swing would pull it out from under the
 * blow it is landing; violence_update checks the gear at the round's end.
 */
void alignment_shift( CHAR_DATA *ch, int delta, bool loud )
{
    char buf[MAX_STRING_LENGTH];
    int was, now;

    if ( ch == NULL || delta == 0 )
        return;
    was = ch->alignment;
    now = URANGE( -1000, was + delta, 1000 );
    if ( now == was )
        return;
    ch->alignment = (sh_int) now;
    if ( IS_NPC(ch) )
        return;

    if ( loud && IS_SET(ch->act, PLR_DAMAGE_NUMBERS) )
    {
        snprintf( buf, sizeof(buf), "Your alignment has %s by %d.\n\r",
                  now > was ? "risen" : "lowered",
                  now > was ? now - was : was - now );
        send_to_char( buf, ch );
    }
    if ( alignment_tier( now ) != alignment_tier( was ) )
    {
        snprintf( buf, sizeof(buf), "Your soul %s: you are now %s.\n\r",
                  now > was ? "brightens" : "darkens",
                  alignment_tier_name( now ) );
        send_to_char( buf, ch );
        watch_log( ch, "alignment %d -> %d (%s)", was, now,
                   alignment_tier_name( now ) );
    }
    if ( loud && alignment_side( now ) != alignment_side( was ) )
        alignment_check_gear( ch );
}

/* A slain mobile of a side moves the slayer toward the other side. */
void alignment_kill( CHAR_DATA *gch, CHAR_DATA *victim )
{
    int amount, gap;

    if ( gch == NULL || victim == NULL || IS_NPC(gch)
    ||   !IS_NPC(victim) || IS_SET(victim->act, ACT_NOALIGN)
    ||   alignment_side( victim->alignment ) == 0 )
        return;

    amount = UMIN( 1000, UMAX( victim->alignment, -victim->alignment ) ) / 100;
    gap = gch->level - victim->level;
    if ( gap >= 15 )
        return;
    if ( gap >= 8 )
        amount = ( amount + 1 ) / 2;
    alignment_shift( gch, victim->alignment < 0 ? amount : -amount, true );
}

/* Experience for a kill, in percent. Never below a hundred. */
int alignment_xp_percent( CHAR_DATA *gch, CHAR_DATA *victim )
{
    int tier, side;

    if ( gch == NULL || victim == NULL || IS_NPC(gch)
    ||   IS_SET(victim->act, ACT_NOALIGN) )
        return 100;
    side = alignment_side( victim->alignment );
    if ( side == 0 )
        return 100;
    tier = alignment_tier( gch->alignment );
    if ( tier == 0 )
        return 100 + ALIGN_XP_STEP;
    if ( ( tier > 0 && side < 0 ) || ( tier < 0 && side > 0 ) )
        return 100 + ALIGN_XP_STEP * ( tier > 0 ? tier : -tier );
    return 100;
}

/* Holy and negative damage: the light and the dark hit harder with their
   own, and the balanced take less of either. Asked in damage() before
   immunities. */
int alignment_damage_mod( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dam_type )
{
    int tier;

    if ( dam <= 0 || ( dam_type != DAM_HOLY && dam_type != DAM_NEGATIVE ) )
        return dam;

    if ( ch != NULL && !IS_NPC(ch) && ch != victim )
    {
        tier = alignment_tier( ch->alignment );
        if ( dam_type == DAM_HOLY && tier > 0 )
            dam += dam * ALIGN_PERK_STEP * tier / 100;
        else if ( dam_type == DAM_NEGATIVE && tier < 0 )
            dam += dam * ALIGN_PERK_STEP * -tier / 100;
    }
    if ( victim != NULL && !IS_NPC(victim)
    &&   alignment_tier( victim->alignment ) == 0 )
        dam -= dam * ALIGN_BALANCE_WARD / 100;
    return dam;
}

/* The dark's weapon blows give back a share of what they take. Called
   only where hit points really came off, so the training dummy, which
   absorbs every blow, feeds nobody. Only what the victim had counts --
   a killing blow of 500 on a foe with 20 left took 20 -- and never the
   treasure goblin, whose "damage" is a share of his health set by the
   chase, not by the blow. */
void alignment_drain( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dt )
{
    int tier, heal;

    if ( ch == NULL || IS_NPC(ch) || victim == NULL || ch == victim
    ||   dam <= 0 || dt < TYPE_HIT || ch->hit >= ch->max_hit
    ||   is_treasure_goblin( victim ) )
        return;
    if ( victim->hit < 0 )
        dam += victim->hit;     /* hit points were already taken off */
    if ( dam <= 0 )
        return;
    tier = alignment_tier( ch->alignment );
    if ( tier >= 0 )
        return;
    heal = dam * ALIGN_DRAIN_STEP * -tier / 100;
    if ( heal > 0 )
        ch->hit = UMIN( ch->max_hit, ch->hit + heal );
}

/* The light's hit point regeneration, from hit_gain. */
int alignment_regen( CHAR_DATA *ch, int gain )
{
    int tier;

    if ( ch == NULL || IS_NPC(ch) || gain <= 0 )
        return gain;
    tier = alignment_tier( ch->alignment );
    if ( tier > 0 )
        gain += gain * ALIGN_PERK_STEP * tier / 100;
    return gain;
}

/*
 * A shopkeeper of your side charges a tenth less, never below what the
 * thing is worth; one of the other side charges a tenth more and pays a
 * tenth less. Nobody pays you more than list: no shop buys anything back
 * for more than its worth (the highest buyback in the world is 100), so
 * as long as nobody sells below worth either, no loop of buying at one
 * shop and selling at another can turn a profit. The first draft paid a
 * tenth more to your own side too, and that opened thousands of them.
 * Neutral keepers and balanced customers trade at the list price, and
 * the black market never haggles.
 */
long alignment_price( CHAR_DATA *ch, CHAR_DATA *keeper, long cost, bool fBuy )
{
    int ours, theirs;
    long share, worth;
    int markup;

    if ( cost <= 0 || ch == NULL || IS_NPC(ch) || keeper == NULL
    ||   keeper->pIndexData == NULL || keeper->pIndexData->pShop == NULL
    ||   is_black_market_dealer( keeper ) )
        return cost;
    ours = alignment_side( ch->alignment );
    theirs = alignment_side( keeper->alignment );
    if ( ours == 0 || theirs == 0 )
        return cost;
    share = cost / ALIGN_PRICE_SHARE;
    if ( !fBuy )
        return ours == theirs ? cost : cost - share;
    if ( ours != theirs )
        return cost + share;
    /* What it is worth: the list price without the shop's markup, rounded
       up so a copper of rounding cannot open a loop either. */
    markup = keeper->pIndexData->pShop->profit_buy;
    worth = markup > 100
        ? cost / markup * 100 + ( cost % markup * 100 + markup - 1 ) / markup
        : cost;
    return UMIN( cost, UMAX( cost - share, worth ) );
}

bool alignment_rejects_obj( CHAR_DATA *ch, OBJ_DATA *obj )
{
    return ( IS_OBJ_STAT(obj, ITEM_ANTI_EVIL)    && IS_EVIL(ch)    )
        || ( IS_OBJ_STAT(obj, ITEM_ANTI_GOOD)    && IS_GOOD(ch)    )
        || ( IS_OBJ_STAT(obj, ITEM_ANTI_NEUTRAL) && IS_NEUTRAL(ch) );
}

/* Who may wear it, in tiers: "" when anyone may. */
const char *alignment_obj_requirement( OBJ_DATA *obj )
{
    bool good = !IS_OBJ_STAT(obj, ITEM_ANTI_GOOD);
    bool evil = !IS_OBJ_STAT(obj, ITEM_ANTI_EVIL);
    bool neutral = !IS_OBJ_STAT(obj, ITEM_ANTI_NEUTRAL);

    if ( good && evil && neutral )  return "";
    if ( good && evil )             return "the light or the dark (Kind or Ruthless and beyond)";
    if ( good && neutral )          return "the light or the balanced (not Ruthless or darker)";
    if ( evil && neutral )          return "the dark or the balanced (not Kind or brighter)";
    if ( good )                     return "the light (Kind or brighter)";
    if ( evil )                     return "the dark (Ruthless or darker)";
    if ( neutral )                  return "the balanced";
    return "nobody";
}

/* Which side a quest target serves: the side its death helps. */
int alignment_quest_side( MOB_INDEX_DATA *pMob )
{
    if ( pMob == NULL || IS_SET(pMob->act, ACT_NOALIGN) )
        return 0;
    return -alignment_side( pMob->alignment );
}

void alignment_quest_kill( CHAR_DATA *ch, MOB_INDEX_DATA *pMob )
{
    int side = alignment_quest_side( pMob );

    if ( ch == NULL || IS_NPC(ch) || side == 0 )
        return;
    send_to_char( side > 0 ? "Your hunt serves the light.\n\r"
                           : "Your hunt serves the dark.\n\r", ch );
    alignment_shift( ch, side * ALIGN_QUEST_SHIFT, true );
}

/* ------------------------------------------------------------- commands */

static void alignment_bar( CHAR_DATA *ch, char *buf, size_t size )
{
    char bar[64];
    int i, mark;

    mark = URANGE( 0, ( ch->alignment + 1000 ) / 50, 40 );
    for ( i = 0; i <= 40; i++ )
    {
        int at = i * 50 - 1000;

        if ( i == mark )
            bar[i] = '*';
        else if ( at == -300 || at == 300 )
            bar[i] = '|';
        else if ( at == -550 || at == -900 || at == 550 || at == 900 )
            bar[i] = ':';
        else
            bar[i] = '-';
    }
    bar[41] = '\0';
    snprintf( buf, size, "  dark [%s] light\n\r", bar );
}

static void alignment_perks( CHAR_DATA *ch, char *buf, size_t size )
{
    int tier = alignment_tier( ch->alignment );
    int t = tier < 0 ? -tier : tier;

    if ( tier > 0 )
        snprintf( buf, size,
            "  Hit point regeneration +%d%%, holy damage +%d%%.\n\r"
            "  Experience +%d%% for slaying the evil.\n\r",
            ALIGN_PERK_STEP * t, ALIGN_PERK_STEP * t, ALIGN_XP_STEP * t );
    else if ( tier < 0 )
        snprintf( buf, size,
            "  Your weapon blows drain %d%% of their damage as hit points,\n\r"
            "  negative damage +%d%%. Experience +%d%% for slaying the good.\n\r",
            ALIGN_DRAIN_STEP * t, ALIGN_PERK_STEP * t, ALIGN_XP_STEP * t );
    else
        snprintf( buf, size,
            "  Holy and negative damage against you -%d%%.\n\r"
            "  Experience +%d%% for slaying the good or the evil.\n\r",
            ALIGN_BALANCE_WARD, ALIGN_XP_STEP );
}

void do_alignment( CHAR_DATA *ch, char *argument )
{
    static const char *const ordinal[4] = { "", "first", "second", "third" };
    char buf[MAX_STRING_LENGTH];
    char price[64];
    int tier, next;
    long wait;

    UNUSED_PARAM(argument);
    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only a player's alignment is tended that way.\n\r", ch );
        return;
    }
    tier = alignment_tier( ch->alignment );

    if ( tier == 0 )
        snprintf( buf, sizeof(buf), "You are Balanced, between the light "
                  "and the dark (alignment %d).\n\r", ch->alignment );
    else
        snprintf( buf, sizeof(buf), "You are %s, the %s of three tiers of "
                  "the %s (alignment %d).\n\r", alignment_tier_name( ch->alignment ),
                  ordinal[tier < 0 ? -tier : tier], tier > 0 ? "light" : "dark",
                  ch->alignment );
    send_to_char( buf, ch );
    alignment_bar( ch, buf, sizeof(buf) );
    send_to_char( buf, ch );

    if ( tier >= 0 && tier < 3 )
    {
        next = tier_floor( tier + 1 );
        snprintf( buf, sizeof(buf), "  %s is %d toward the light",
                  alignment_tier_name( next ), next - ch->alignment );
        send_to_char( buf, ch );
        if ( tier == 0 )
        {
            snprintf( buf, sizeof(buf), "; Ruthless %d toward the dark",
                      ch->alignment - ( -300 ) );
            send_to_char( buf, ch );
        }
        send_to_char( ".\n\r", ch );
    }
    else if ( tier < 0 && tier > -3 )
    {
        next = -tier_floor( -( tier - 1 ) );
        snprintf( buf, sizeof(buf), "  %s is %d toward the dark.\n\r",
                  alignment_tier_name( next ), ch->alignment - next );
        send_to_char( buf, ch );
    }

    send_to_char( "What it gives you:\n\r", ch );
    alignment_perks( ch, buf, sizeof(buf) );
    send_to_char( buf, ch );
    send_to_char( "  Shopkeepers of your side charge up to 10% less; those of the\n\r"
                  "  other side charge 10% more and pay 10% less.\n\r", ch );

    send_to_char( "What moves it:\n\r"
                  "  Slaying the evil raises it and slaying the good lowers it, more\n\r"
                  "  for the more extreme and less for foes far below you. Slaying\n\r"
                  "  the neutral moves nothing. A quest target of a side moves it\n\r"
                  "  further.\n\r", ch );
    format_price( black_market_kill_value( ch->level ) * ALIGN_DEED_KILLS,
                  price, sizeof(price) );
    wait = ch->pcdata->align_deed_at - (long) current_time;
    if ( wait > 0 )
        snprintf( buf, sizeof(buf), "  DEVOTE LIGHT, DARK or BALANCE at the Temple: "
                  "%d for %s, ready in %ld minute%s.\n\r", ALIGN_DEED_SHIFT, price,
                  ( wait + 59 ) / 60, ( wait + 59 ) / 60 == 1 ? "" : "s" );
    else
        snprintf( buf, sizeof(buf), "  DEVOTE LIGHT, DARK or BALANCE at the Temple: "
                  "%d for %s, ready now.\n\r", ALIGN_DEED_SHIFT, price );
    send_to_char( buf, ch );
}

/*
 * What a devotion would do, decided once for DEVOTE, DEVOTE PREVIEW and
 * the staff's ALIGNCHECK, so the preview cannot promise what the deed
 * will not do. Returns the move (0 with *refusal set when there is
 * none) and its price in *cost. Where it is made and whether the gods are
 * ready are the deed's own questions, asked after.
 */
static int devote_plan( CHAR_DATA *ch, const char *arg, long *cost, const char **refusal )
{
    int delta, moves;
    long whole;

    *cost = 0;
    *refusal = NULL;
    if ( !str_prefix( arg, "light" ) )
        delta = ALIGN_DEED_SHIFT;
    else if ( !str_prefix( arg, "dark" ) )
        delta = -ALIGN_DEED_SHIFT;
    else if ( !str_prefix( arg, "balance" ) )
    {
        if ( ch->alignment == 0 )
        {
            *refusal = "You are already perfectly balanced.\n\r";
            return 0;
        }
        delta = ch->alignment > 0 ? -UMIN( ALIGN_DEED_SHIFT, ch->alignment )
                                  : UMIN( ALIGN_DEED_SHIFT, -ch->alignment );
    }
    else
    {
        *refusal = "Devote yourself to the light, the dark or the balance.\n\r";
        return 0;
    }
    if ( ( delta > 0 && ch->alignment >= 1000 )
    ||   ( delta < 0 && ch->alignment <= -1000 ) )
    {
        *refusal = "You could go no further that way.\n\r";
        return 0;
    }

    /* A devotion that can only go part of the way -- LIGHT at 950, or
       BALANCE five from the middle -- costs that part of the price. In two
       parts, so a level 60's price times a hundred cannot overflow a
       32-bit long. */
    moves = URANGE( -1000, ch->alignment + delta, 1000 ) - ch->alignment;
    if ( moves < 0 )
        moves = -moves;
    whole = black_market_kill_value( ch->level ) * ALIGN_DEED_KILLS;
    *cost = whole / ALIGN_DEED_SHIFT * moves
          + whole % ALIGN_DEED_SHIFT * moves / ALIGN_DEED_SHIFT;
    *cost = UMAX( 1, *cost );
    return delta;
}

/*
 * The worn pieces that would come off at an alignment, by the same test
 * alignment_check_gear makes: the alignment is set for the asking and put
 * back before anything else runs. Writes their names into buf; returns
 * how many.
 */
static int alignment_would_reject( CHAR_DATA *ch, int alignment, char *buf, size_t size )
{
    OBJ_DATA *obj;
    int saved = ch->alignment;
    int count = 0;

    buf[0] = '\0';
    ch->alignment = (sh_int) URANGE( -1000, alignment, 1000 );
    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        if ( obj->wear_loc == WEAR_NONE || !alignment_rejects_obj( ch, obj ) )
            continue;
        if ( count++ > 0 )
            toc_strlcat( buf, ", ", size );
        toc_strlcat( buf, obj->short_descr != NULL ? obj->short_descr : "something", size );
    }
    ch->alignment = (sh_int) saved;
    return count;
}

/* One devotion's forecast, about who, told to viewer. */
static void devote_forecast( CHAR_DATA *viewer, CHAR_DATA *who, const char *way )
{
    char buf[MAX_STRING_LENGTH];
    char names[1024];
    char price[64];
    const char *refusal;
    long cost;
    int delta, after, rejected;

    delta = devote_plan( who, way, &cost, &refusal );
    if ( delta == 0 )
    {
        snprintf( buf, sizeof(buf), "  %-8s %s", way, refusal );
        send_to_char( buf, viewer );
        return;
    }
    after = URANGE( -1000, who->alignment + delta, 1000 );
    format_price( cost, price, sizeof(price) );
    snprintf( buf, sizeof(buf), "  %-8s %d -> %d (%s -> %s), offering %s%s.\n\r",
              way, who->alignment, after, alignment_tier_name( who->alignment ),
              alignment_tier_name( after ), price,
              has_enough_copper( who, cost ) ? "" : " -- more than is carried" );
    send_to_char( buf, viewer );
    rejected = alignment_would_reject( who, after, names, sizeof(names) );
    if ( rejected > 0 )
    {
        snprintf( buf, sizeof(buf), "           would come off and fall to the floor: %s.\n\r",
                  names );
        send_to_char( buf, viewer );
    }
}

/* The forecasts and readiness, for DEVOTE PREVIEW and ALIGNCHECK. way is
   one of light, dark or balance, or empty for all three. */
static void devote_preview( CHAR_DATA *viewer, CHAR_DATA *who, const char *way )
{
    char buf[MAX_STRING_LENGTH];
    long wait = who->pcdata->align_deed_at - (long) current_time;

    if ( way[0] != '\0' && str_prefix( way, "light" ) && str_prefix( way, "dark" )
    &&   str_prefix( way, "balance" ) )
    {
        send_to_char( "DEVOTE PREVIEW LIGHT, DARK or BALANCE -- or PREVIEW alone for all three.\n\r",
                      viewer );
        return;
    }
    send_to_char( "A devotion would make it (nothing is offered by looking):\n\r", viewer );
    if ( way[0] == '\0' || !str_prefix( way, "light" ) )
        devote_forecast( viewer, who, "light" );
    if ( way[0] == '\0' || !str_prefix( way, "dark" ) )
        devote_forecast( viewer, who, "dark" );
    if ( way[0] == '\0' || !str_prefix( way, "balance" ) )
        devote_forecast( viewer, who, "balance" );
    if ( wait > 0 )
        snprintf( buf, sizeof(buf), "The gods will hear %s again in %ld minute%s.\n\r",
                  viewer == who ? "you" : "them", ( wait + 59 ) / 60,
                  ( wait + 59 ) / 60 == 1 ? "" : "s" );
    else
        snprintf( buf, sizeof(buf), "The gods would hear %s now, at the Temple or its altar.\n\r",
                  viewer == who ? "you" : "them" );
    send_to_char( buf, viewer );
}

/*
 * ALIGNCHECK <player>: staff, read-only. The player's alignment as
 * ALIGNMENT tells it to them, what is worn that their side already
 * rejects, and the three devotions forecast.
 */
void do_aligncheck( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char names[1024];
    CHAR_DATA *victim;

    one_argument( argument, arg );
    if ( arg[0] == '\0' )
    {
        send_to_char( "ALIGNCHECK <player>: alignment, perks, gear and devotions, changing nothing.\n\r", ch );
        return;
    }
    if ( ( victim = get_char_world( ch, arg ) ) == NULL || IS_NPC(victim)
    ||   victim->pcdata == NULL )
    {
        send_to_char( "No player by that name is in the game.\n\r", ch );
        return;
    }
    if ( victim != ch && rank_protects( ch, victim ) )
    {
        send_to_char( "They outrank you.\n\r", ch );
        return;
    }
    snprintf( buf, sizeof(buf), "%s is %s (alignment %d).\n\r", victim->name,
              alignment_tier_name( victim->alignment ), victim->alignment );
    send_to_char( buf, ch );
    alignment_bar( victim, buf, sizeof(buf) );
    send_to_char( buf, ch );
    alignment_perks( victim, buf, sizeof(buf) );
    send_to_char( buf, ch );
    if ( alignment_would_reject( victim, victim->alignment, names, sizeof(names) ) > 0 )
    {
        snprintf( buf, sizeof(buf), "Worn now and rejected by their own side (comes off at the next check): %s.\n\r",
                  names );
        send_to_char( buf, ch );
    }
    devote_preview( ch, victim, "" );
}

void do_devote( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char price[64];
    const char *refusal;
    long cost, wait;
    int delta;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only a player's alignment is tended that way.\n\r", ch );
        return;
    }
    argument = one_argument( argument, arg );
    if ( arg[0] == '\0' )
    {
        send_to_char( "DEVOTE LIGHT, DEVOTE DARK or DEVOTE BALANCE, at the Temple; "
                      "DEVOTE PREVIEW to see first. See ALIGNMENT.\n\r", ch );
        return;
    }
    /* Anywhere, and free: what a devotion would cost and change. */
    if ( !str_prefix( arg, "preview" ) && strlen( arg ) >= 2 )
    {
        one_argument( argument, arg );
        devote_preview( ch, ch, arg );
        return;
    }
    if ( ch->in_room == NULL
    ||   ( ch->in_room->vnum != ROOM_VNUM_TEMPLE
    &&     ch->in_room->vnum != ROOM_VNUM_ALTAR ) )
    {
        send_to_char( "Devotion is made at the Temple, or at its altar.\n\r", ch );
        return;
    }

    if ( ( delta = devote_plan( ch, arg, &cost, &refusal ) ) == 0 )
    {
        send_to_char( refusal, ch );
        return;
    }

    wait = ch->pcdata->align_deed_at - (long) current_time;
    if ( wait > 0 )
    {
        snprintf( buf, sizeof(buf), "The gods will hear you again in %ld minute%s.\n\r",
                  ( wait + 59 ) / 60, ( wait + 59 ) / 60 == 1 ? "" : "s" );
        send_to_char( buf, ch );
        return;
    }

    format_price( cost, price, sizeof(price) );
    if ( !has_enough_copper( ch, cost ) )
    {
        snprintf( buf, sizeof(buf), "A devotion asks an offering of %s.\n\r", price );
        send_to_char( buf, ch );
        return;
    }
    spend_copper( ch, cost );

    if ( !str_prefix( arg, "light" ) )
    {
        snprintf( buf, sizeof(buf), "You lay %s upon the altar and pray for "
                  "the light.\n\r", price );
        send_to_char( buf, ch );
        act( "$n lays an offering upon the altar and prays.", ch, NULL, NULL, TO_ROOM );
    }
    else if ( !str_prefix( arg, "dark" ) )
    {
        snprintf( buf, sizeof(buf), "You spill %s and a little blood upon the "
                  "altar stone, and whisper to what listens below.\n\r", price );
        send_to_char( buf, ch );
        act( "$n spills blood upon the altar stone and whispers.", ch, NULL, NULL, TO_ROOM );
    }
    else
    {
        snprintf( buf, sizeof(buf), "You leave %s at the altar, kneel, and "
                  "empty your mind.\n\r", price );
        send_to_char( buf, ch );
        act( "$n kneels before the altar in silence.", ch, NULL, NULL, TO_ROOM );
    }

    alignment_shift( ch, delta, true );
    ch->pcdata->align_deed_at = (long) current_time + ALIGN_DEED_COOLDOWN;
    snprintf( buf, sizeof(buf), "You are %s (alignment %d).\n\r",
              alignment_tier_name( ch->alignment ), ch->alignment );
    send_to_char( buf, ch );
    WAIT_STATE( ch, PULSE_VIOLENCE );
    save_char_obj( ch );
}
