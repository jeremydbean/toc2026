/*
 * holiday.c -- the holiday calendar and its fairs (owner, 2026-11-02:
 * "align with the world of warcraft holiday schedule", minor holidays
 * kept simple -- clovers with a purpose, a Valentine's theme).
 *
 * The calendar, in the order a date is checked (the first that matches
 * wins, so a short holiday inside a longer one is not lost):
 *
 *   Winter Veil         Dec 16 - Jan  6   (season.c swaps three areas)
 *   Lunar Festival      Jan 21 - Feb  4
 *   Love is in the Air  Feb  7 - Feb 20
 *   St. Patrick's Day   Mar 14 - Mar 17
 *   Noblegarden         the six days before Easter, and Easter Sunday
 *   Children's Week     Apr 30 - May  6
 *   Midsummer Fire      Jun 21 - Jul  5
 *   Pirates' Day        Sep 19
 *   Brewfest            Sep 20 - Oct  6
 *   Hallows End         Oct 18 - Nov  1   (season.c swaps three areas)
 *   Day of the Dead     Nov  2 - Nov  3
 *   Pilgrim's Bounty    Thanksgiving week, Monday to Sunday
 *
 * Every holiday has a fair: a vendor who stands in the Oak Tree Square
 * for the whole of it (BUY, never SELL), a decoration beside them (the
 * two big seasons decorate the whole town instead), a treat that NPC
 * kills drop, a line at login and in TIME, and a word from every
 * shopkeeper. The things with a purpose:
 *
 *   a four-leaf clover  eaten, the next foe you slay spills a pot of gold
 *   a red envelope      OPEN it: lucky money, three kills' worth
 *   a red rose          GIVE it to another player: both are blessed
 *   a festival firework DROP it: it bursts over the whole area
 *   painted eggs        hidden all over Dresden in Noblegarden; OPEN them
 *   a candy heart       eaten, it blesses you and says something sweet
 *   trick-or-treat candy eaten, a treat or a (harmless) trick
 *   the festival keg    a fountain of ale in the square for Brewfest
 *
 * The rest are pills the world already understands (EAT casts their
 * spells), drinks, and things to wear. Everything here is in
 * holidays.are, vnums 29800-29899, except the two seasons' own things in
 * seasonal.are.
 *
 * TOC_SEASON overrides the calendar (a holiday's key below, or "none");
 * TOC_DATE=YYYY-MM-DD sets the date it is read from, and
 * TOC_HOLIDAY_DROPS=always makes every NPC kill drop the treat. All three
 * are for tests.
 */

#include <time.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "merc.h"
#include "list.h"
#include "holiday_rules.h"

enum { RULE_FIXED, RULE_EASTER, RULE_THANKSGIVING };

typedef struct holiday_def
{
    const char *key;          /* TOC_SEASON and HOLIDAYS <key> */
    const char *name;
    int         rule;
    int         m1, d1, m2, d2;   /* fixed: from m1/d1 to m2/d2; Easter and
                                     Thanksgiving: d1 and d2 are offsets
                                     in days from that day */
    const char *greeting;     /* login and TIME */
    const char *shop_line;    /* act(), $n is the shopkeeper */
    int         drop_vnum;    /* what NPC kills drop, 0 for nothing */
    int         drop_chance;  /* percent */
    int         vendor_vnum;
    int         wares[4];     /* 0 ends the list */
    const char *vendor_arrive;
    const char *vendor_leave; /* act(), $n is the vendor */
    int         decor_vnum;   /* stood in the square, 0 for none */
} HOLIDAY;

static const HOLIDAY holidays[] =
{
    { "xmas", "Winter Veil", RULE_FIXED, 12, 16, 1, 6,
      "It is the Feast of Winter Veil! Tinsel the gift elf is in the Oak Tree "
      "Square, and every creature in the world carries a little gift.",
      "$n gestures to the small evergreen decorated behind the counter. 'Happy Winter Veil!'",
      OBJ_VNUM_SEASONAL_GIFT, 15,
      MOB_VNUM_VENDOR_WINTER, { OBJ_VNUM_ELF_HAT, OBJ_VNUM_SPICED_CIDER, 0 },
      "Tinsel the Winter Veil gift elf has skipped into Dresden's Oak Tree "
      "Square with holiday gifts and treats for sale!",
      "$n gives a cheerful wave and disappears in a flurry of snowflakes.",
      0 },

    { "lunar", "the Lunar Festival", RULE_FIXED, 1, 21, 2, 4,
      "The Lunar Festival has begun! Red envelopes of lucky money turn up on "
      "the creatures of the world -- OPEN them. Grandmother Lin sells lanterns "
      "and rockets in the Oak Tree Square.",
      "$n bows and wishes you a prosperous new year.",
      OBJ_VNUM_RED_ENVELOPE, 10,
      MOB_VNUM_VENDOR_LUNAR, { OBJ_VNUM_PAPER_LANTERN, OBJ_VNUM_FIREWORK, OBJ_VNUM_RICE_CAKE, 0 },
      "Grandmother Lin the lantern seller has set up beneath the Oak Tree, "
      "with lanterns and rockets for the Lunar Festival!",
      "$n bows to the square, shoulders her lantern pole and goes on her way.",
      OBJ_VNUM_DECOR_LUNAR },

    { "love", "Love is in the Air", RULE_FIXED, 2, 7, 2, 20,
      "Love is in the Air! Rosalind sells roses in the Oak Tree Square -- GIVE "
      "one to another adventurer and you are both blessed. Candy hearts turn "
      "up everywhere.",
      "$n has tucked a red paper heart into the corner of the price list.",
      OBJ_VNUM_CANDY_HEART, 10,
      MOB_VNUM_VENDOR_LOVE, { OBJ_VNUM_RED_ROSE, OBJ_VNUM_CHOCOLATES, OBJ_VNUM_HEART_LOCKET, 0 },
      "Rosalind the flower seller has wheeled her cart of roses into the Oak "
      "Tree Square. Love is in the Air!",
      "$n gathers up the last of her roses, blows the square a kiss and is gone.",
      OBJ_VNUM_DECOR_LOVE },

    { "stpatrick", "St. Patrick's Day", RULE_FIXED, 3, 14, 3, 17,
      "Happy St. Patrick's Day! Four-leaf clovers turn up on the creatures of "
      "the world: eat one, and the next foe you slay spills a pot of gold.",
      "$n is wearing a sprig of shamrock and grins at you.",
      OBJ_VNUM_FOUR_LEAF_CLOVER, 8,
      MOB_VNUM_VENDOR_STPATRICK, { OBJ_VNUM_GREEN_HAT, OBJ_VNUM_GREEN_STOUT, 0 },
      "Finnegan the tinker has rolled a keg into the Oak Tree Square and sat "
      "himself on it. Happy St. Patrick's Day!",
      "$n tips his hat, finishes his pint and whistles himself away.",
      OBJ_VNUM_DECOR_STPATRICK },

    { "noblegarden", "Noblegarden", RULE_EASTER, 0, -6, 0, 0,
      "Noblegarden is here! Painted eggs are hidden all over Dresden -- find "
      "them and OPEN them. Hopscotch the egg warden is in the Oak Tree Square.",
      "$n has a painted egg sitting on the counter for luck.",
      OBJ_VNUM_PAINTED_EGG, 4,
      MOB_VNUM_VENDOR_NOBLEGARDEN, { OBJ_VNUM_BUNNY_EARS, OBJ_VNUM_CHOCOLATE_RABBIT, 0 },
      "Hopscotch the egg warden has hopped into the Oak Tree Square. Painted "
      "eggs are hidden all over Dresden for Noblegarden!",
      "$n waggles his ears goodbye and hops off to hide more eggs elsewhere.",
      OBJ_VNUM_DECOR_NOBLEGARDEN },

    { "children", "Children's Week", RULE_FIXED, 4, 30, 5, 6,
      "It is Children's Week! Matron Abigail sells toys for the orphanage in "
      "the Oak Tree Square, and lollipops turn up in the oddest places.",
      "$n has a jar of lollipops on the counter 'for the little ones'.",
      OBJ_VNUM_LOLLIPOP, 10,
      MOB_VNUM_VENDOR_CHILDREN, { OBJ_VNUM_SPINNING_TOP, OBJ_VNUM_PAPER_KITE, OBJ_VNUM_LOLLIPOP, 0 },
      "Matron Abigail has brought the orphans to the Oak Tree Square for "
      "Children's Week, with toys for sale!",
      "$n rounds up the orphans, counts them twice and herds them home.",
      OBJ_VNUM_DECOR_CHILDREN },

    { "midsummer", "the Midsummer Fire Festival", RULE_FIXED, 6, 21, 7, 5,
      "The Midsummer Fire Festival burns in the Oak Tree Square! Festival "
      "fireworks turn up everywhere -- DROP one and stand back.",
      "$n is wearing a crown of summer flowers, a little scorched.",
      OBJ_VNUM_FIREWORK, 8,
      MOB_VNUM_VENDOR_MIDSUMMER, { OBJ_VNUM_FLOWER_CROWN, OBJ_VNUM_FIREWORK, 0 },
      "Keeper Ashby has lit the great midsummer bonfire in the Oak Tree "
      "Square. Honour the flame!",
      "$n banks the last of the fire and walks off trailing sparks.",
      OBJ_VNUM_DECOR_MIDSUMMER },

    { "pirates", "Pirates' Day", RULE_FIXED, 9, 19, 9, 19,
      "Arr! It be Pirates' Day! Captain Saltbeard sells hats and grog in the "
      "Oak Tree Square, and every scurvy creature carries a bottle.",
      "$n squints at you with one eye shut and says 'Arr.'",
      OBJ_VNUM_GROG, 10,
      MOB_VNUM_VENDOR_PIRATES, { OBJ_VNUM_TRICORN, OBJ_VNUM_GROG, 0 },
      "Captain Saltbeard has come ashore in the Oak Tree Square for Pirates' "
      "Day. Arr!",
      "$n stumps off toward the sea, his parrot shrieking about doubloons.",
      OBJ_VNUM_DECOR_PIRATES },

    { "brewfest", "Brewfest", RULE_FIXED, 9, 20, 10, 6,
      "Brewfest is on! The festival keg in the Oak Tree Square is free to "
      "DRINK from, and Barley Thumbtap sells steins and pretzels.",
      "$n raises a mug to you. 'Happy Brewfest!'",
      OBJ_VNUM_AUTUMN_ALE, 10,
      MOB_VNUM_VENDOR_BREWFEST, { OBJ_VNUM_STEIN, OBJ_VNUM_PRETZEL, OBJ_VNUM_AUTUMN_ALE, 0 },
      "Barley Thumbtap has rolled the Brewfest keg into the Oak Tree Square. "
      "Drinks are on the house!",
      "$n corks the keg, slaps it fondly and rolls it away down the road.",
      OBJ_VNUM_DECOR_BREWFEST },

    { "halloween", "Hallows End", RULE_FIXED, 10, 18, 11, 1,
      "Hallows End is here! Madame Hexley sells masks and sweets in the Oak "
      "Tree Square, and trick-or-treat candy turns up everywhere -- eat it if "
      "you dare.",
      "$n slides a bowl of trick-or-treat candy across the counter with a grin.",
      OBJ_VNUM_SEASONAL_CANDY, 15,
      MOB_VNUM_VENDOR_HALLOWEEN, { OBJ_VNUM_JACK_O_MASK, OBJ_VNUM_CANDY_CORN, 0 },
      "Madame Hexley the Hallows End merchant has appeared in Dresden's Oak "
      "Tree Square with holiday wares for sale!",
      "$n calls out 'Come find me again next year!' and vanishes into the shadows.",
      0 },

    { "deadday", "the Day of the Dead", RULE_FIXED, 11, 2, 11, 3,
      "It is the Day of the Dead. An ofrenda stands beneath the Oak Tree, and "
      "sugar skulls let you see a little of what the departed see.",
      "$n has lit a small candle beside the till, for someone.",
      OBJ_VNUM_SUGAR_SKULL, 10,
      MOB_VNUM_VENDOR_DEADDAY, { OBJ_VNUM_MARIGOLDS, OBJ_VNUM_SKULL_MASK, OBJ_VNUM_SUGAR_SKULL, 0 },
      "Catrina the candle-keeper has raised an ofrenda in the Oak Tree "
      "Square for the Day of the Dead.",
      "$n blows out a single candle, smiles, and is simply not there any more.",
      OBJ_VNUM_DECOR_DEADDAY },

    { "pilgrim", "Pilgrim's Bounty", RULE_THANKSGIVING, 0, -3, 0, 3,
      "Pilgrim's Bounty! The harvest table in the Oak Tree Square is laden, "
      "Goodwife Prudence is cooking, and a good meal leaves you stronger.",
      "$n is still chewing something, and offers you a slice of pie.",
      OBJ_VNUM_PUMPKIN_PIE, 10,
      MOB_VNUM_VENDOR_PILGRIM, { OBJ_VNUM_PILGRIM_HAT, OBJ_VNUM_ROAST_TURKEY, OBJ_VNUM_PUMPKIN_PIE, 0 },
      "Goodwife Prudence has laid the Pilgrim's Bounty table in the Oak Tree "
      "Square. Come and eat!",
      "$n clears the last of the plates and bustles off to start on next year's.",
      OBJ_VNUM_DECOR_PILGRIM },

    { NULL, NULL, 0, 0, 0, 0, 0, NULL, NULL, 0, 0, 0, { 0 }, NULL, NULL, 0 }
};

/* Noblegarden's hunt: at most this many eggs lie in Dresden at once. */
#define EGG_CEILING          12

/* Coin is counted in kills at a level (black_market_kill_value). */
#define ENVELOPE_KILLS        3
#define POT_OF_GOLD_KILLS     5
#define EGG_COIN_KILLS        2

/* A clover's luck keeps for this many kills at most. */
#define LUCK_MAX              3

/* The whole area hears a firework at most this often (seconds). */
#define FIREWORK_AREA_GAP    20

CHAR_DATA *event_vendor = NULL;
static const HOLIDAY *vendor_holiday = NULL;
static const HOLIDAY *decorated = NULL;


/* ------------------------------------------------------------ the date */

#define days_from_civil   holiday_days_from_civil
#define easter_date       holiday_easter
#define thanksgiving_day  holiday_thanksgiving

/* A test's date, from TOC_DATE_FILE (read at every call, so one running
   world can be walked from holiday to holiday) or TOC_DATE. Either must
   be a whole, real YYYY-MM-DD; anything else is logged once and ignored,
   and the host's clock is used. */
static bool holiday_test_date( int *y, int *m, int *d )
{
    static char complained[64];
    const char *file = getenv( "TOC_DATE_FILE" );
    const char *text = getenv( "TOC_DATE" );
    char line[64];

    if ( file != NULL && file[0] != '\0' )
    {
        FILE *fp = fopen( file, "r" );

        line[0] = '\0';
        if ( fp != NULL )
        {
            if ( fgets( line, sizeof(line), fp ) == NULL )
                line[0] = '\0';
            fclose( fp );
        }
        line[strcspn( line, "\r\n" )] = '\0';
        if ( line[0] == '\0' )
            return false;          /* an empty file: the clock */
        text = line;
    }
    if ( text == NULL || text[0] == '\0' )
        return false;
    if ( holiday_parse_date( text, y, m, d ) )
        return true;
    if ( strcmp( complained, text ) )
    {
        char buf[MAX_STRING_LENGTH];

        toc_strlcpy( complained, text, sizeof(complained) );
        snprintf( buf, sizeof(buf), "holiday: test date '%s' is not a real "
                  "YYYY-MM-DD; using the clock.", text );
        log_string( buf );
    }
    return false;
}

/* Today. The calendar follows the host's local clock (localtime, so the
   TZ the game runs under), unless a test sets a date. */
void holiday_date( int *year, int *mon, int *day )
{
    time_t now;
    struct tm *tm_now;

    if ( holiday_test_date( year, mon, day ) )
        return;
    now = time( NULL );
    tm_now = localtime( &now );
    *year = tm_now->tm_year + 1900;
    *mon  = tm_now->tm_mon + 1;
    *day  = tm_now->tm_mday;
}

/* The first and last day of a holiday whose window holds year y's date
   (as day numbers). A window that crosses the new year starts in y-1
   when asked about January. */
static void holiday_span( const HOLIDAY *h, int y, int mon, long *first, long *last )
{
    int m, d;

    switch ( h->rule )
    {
    case RULE_EASTER:
        easter_date( y, &m, &d );
        *first = days_from_civil( y, m, d ) + h->d1;
        *last  = days_from_civil( y, m, d ) + h->d2;
        return;
    case RULE_THANKSGIVING:
        d = thanksgiving_day( y );
        *first = days_from_civil( y, 11, d ) + h->d1;
        *last  = days_from_civil( y, 11, d ) + h->d2;
        return;
    default:
        if ( h->m1 * 100 + h->d1 <= h->m2 * 100 + h->d2 )
        {
            *first = days_from_civil( y, h->m1, h->d1 );
            *last  = days_from_civil( y, h->m2, h->d2 );
        }
        else if ( mon <= h->m2 )
        {
            *first = days_from_civil( y - 1, h->m1, h->d1 );
            *last  = days_from_civil( y, h->m2, h->d2 );
        }
        else
        {
            *first = days_from_civil( y, h->m1, h->d1 );
            *last  = days_from_civil( y + 1, h->m2, h->d2 );
        }
        return;
    }
}

static const HOLIDAY *holiday_by_key( const char *key )
{
    int i;

    if ( key == NULL || key[0] == '\0' )
        return NULL;
    if ( !str_cmp( key, "christmas" ) )
        key = "xmas";
    for ( i = 0; holidays[i].key != NULL; i++ )
        if ( !str_cmp( key, holidays[i].key ) )
            return &holidays[i];
    return NULL;
}

static const HOLIDAY *holiday_on( int y, int m, int d )
{
    long today = days_from_civil( y, m, d );
    long first, last;
    int i;

    for ( i = 0; holidays[i].key != NULL; i++ )
    {
        holiday_span( &holidays[i], y, m, &first, &last );
        if ( today >= first && today <= last )
            return &holidays[i];
    }
    return NULL;
}

static const HOLIDAY *holiday_current( void )
{
    const char *forced = getenv( "TOC_SEASON" );
    int y, m, d;

    if ( forced != NULL && forced[0] != '\0' )
    {
        if ( !str_cmp( forced, "none" ) || !str_cmp( forced, "off" ) )
            return NULL;
        if ( holiday_by_key( forced ) != NULL )
            return holiday_by_key( forced );
    }
    holiday_date( &y, &m, &d );
    return holiday_on( y, m, d );
}

const char *holiday_name( void )
{
    const HOLIDAY *h = holiday_current();

    return h != NULL ? h->name : NULL;
}

/* The key of what is on, for season.c, which swaps areas for two of
   them. NULL when nothing is. */
const char *holiday_key( void )
{
    const HOLIDAY *h = holiday_current();

    return h != NULL ? h->key : NULL;
}


/* --------------------------------------------------------- the things */

static OBJ_DATA *holiday_make( int vnum )
{
    OBJ_INDEX_DATA *pObj = get_obj_index( vnum );

    if ( pObj == NULL )
    {
        bug( "holiday_make: missing object %d.", vnum );
        return NULL;
    }
    return create_object( pObj, 0 );
}

/* Copper into a container as the fewest piles that carry it. */
static void holiday_coin_into( OBJ_DATA *container, long copper )
{
    static const long unit[4] =
        { COPPER_PER_PLATINUM, COPPER_PER_GOLD, COPPER_PER_SILVER, 1 };
    static const int type[4] =
        { TYPE_PLATINUM, TYPE_GOLD, TYPE_SILVER, TYPE_COPPER };
    int i;

    for ( i = 0; i < 4 && copper > 0; i++ )
    {
        long n = UMIN( copper / unit[i], 1000000L );

        if ( n <= 0 )
            continue;
        copper -= n * unit[i];
        obj_to_obj( create_money( (int) n, type[i] ), container );
    }
}

/* What a red envelope or a painted egg holds, filled as it is made.
   level is the level of whatever carried it, and sets the coin. */
static void holiday_fill( OBJ_DATA *obj, int level )
{
    OBJ_DATA *inside;
    int roll;

    if ( obj == NULL || obj->pIndexData == NULL )
        return;
    level = URANGE( 1, level, LEVEL_HERO );

    if ( obj->pIndexData->vnum == OBJ_VNUM_RED_ENVELOPE )
    {
        holiday_coin_into( obj, black_market_kill_value( level ) * ENVELOPE_KILLS );
        return;
    }
    if ( obj->pIndexData->vnum != OBJ_VNUM_PAINTED_EGG )
        return;

    roll = number_percent();
    if ( roll <= 40 )
        inside = holiday_make( OBJ_VNUM_CHOCOLATE_RABBIT );
    else if ( roll <= 70 )
        inside = holiday_make( OBJ_VNUM_LOLLIPOP );
    else if ( roll <= 95 )
    {
        holiday_coin_into( obj, black_market_kill_value( level ) * EGG_COIN_KILLS );
        return;
    }
    else
        inside = holiday_make( OBJ_VNUM_BUNNY_EARS );
    if ( inside != NULL )
        obj_to_obj( inside, obj );
}

/* make_corpse: the holiday's treat, now and then, on a slain NPC. */
void holiday_corpse_drop( OBJ_DATA *corpse, CHAR_DATA *victim )
{
    const HOLIDAY *h = holiday_current();
    OBJ_DATA *treat;

    const char *always = getenv( "TOC_HOLIDAY_DROPS" );   /* tests only */

    if ( h == NULL || corpse == NULL || victim == NULL || !IS_NPC(victim)
    ||   h->drop_vnum == 0 )
        return;
    if ( !( always != NULL && !str_cmp( always, "always" ) )
    &&   number_percent() > h->drop_chance )
        return;
    if ( ( treat = holiday_make( h->drop_vnum ) ) == NULL )
        return;
    holiday_fill( treat, victim->level );
    obj_to_obj( treat, corpse );
}


/* ------------------------------------------------- what things do */

static void holiday_cast( const char *spell, int level, CHAR_DATA *ch, CHAR_DATA *victim )
{
    int sn = skill_lookup( spell );

    if ( sn > 0 )
        obj_cast_spell( sn, level, ch, victim, NULL );
}

static const char *candy_heart_words[] =
{
    "BE MINE", "TRUE LOVE", "HUG ME", "SWEET PEA", "KISS ME", "CUTIE PIE",
    "MY HERO", "SO FINE", "CALL ME", "ALL MINE", "LOVE BUG", "ADVENTURE AWAITS",
    NULL
};

/* A holiday treat whose point is the eating -- a clover, a candy heart,
   a piece of trick-or-treat candy -- is a bite, not a meal: do_eat lets
   it past "You are too full", which every new character starts as. */
bool holiday_snack( OBJ_DATA *obj )
{
    if ( obj == NULL || obj->pIndexData == NULL )
        return false;
    switch ( obj->pIndexData->vnum )
    {
    case OBJ_VNUM_FOUR_LEAF_CLOVER:
    case OBJ_VNUM_CANDY_HEART:
    case OBJ_VNUM_SEASONAL_CANDY:
        return true;
    }
    return false;
}

/* do_eat, before anything is eaten: a clover is refused, and kept, when
   the eater already carries all the luck they can -- it used to be eaten
   and wasted with a line saying so. True when refused. */
bool holiday_eat_refused( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char buf[MAX_STRING_LENGTH];

    if ( ch == NULL || obj == NULL || obj->pIndexData == NULL || IS_NPC(ch)
    ||   obj->pIndexData->vnum != OBJ_VNUM_FOUR_LEAF_CLOVER
    ||   ch->pcdata->holiday_luck < LUCK_MAX )
        return false;
    snprintf( buf, sizeof(buf),
              "You already carry all the luck one person can: %d kills' worth. "
              "Keep the clover until a pot of gold has spilled.\n\r", LUCK_MAX );
    send_to_char( buf, ch );
    return true;
}

/* do_eat, once the thing is eaten (and gone): what holiday treats do
   besides feed or cast. The character may be gone if a pill's spell
   moved them, so the caller asks first. */
void holiday_eaten( CHAR_DATA *ch, int vnum )
{
    char buf[MAX_STRING_LENGTH];
    int n;

    if ( ch == NULL || ch->in_room == NULL )
        return;

    switch ( vnum )
    {
    case OBJ_VNUM_FOUR_LEAF_CLOVER:
        if ( IS_NPC(ch) )
            return;
        if ( ch->pcdata->holiday_luck >= LUCK_MAX )
            return;      /* holiday_eat_refused stops this before the bite */
        ch->pcdata->holiday_luck++;
        snprintf( buf, sizeof(buf),
                  "{0AA warm, green luck settles over you. The next foe you slay "
                  "will spill a pot of gold.{00\n\r"
                  "You carry luck for %d kill%s (at most %d). It lasts until you "
                  "leave the game.\n\r",
                  ch->pcdata->holiday_luck, ch->pcdata->holiday_luck == 1 ? "" : "s",
                  LUCK_MAX );
        send_to_char( buf, ch );
        return;

    case OBJ_VNUM_CANDY_HEART:
        for ( n = 0; candy_heart_words[n] != NULL; n++ )
            ;
        snprintf( buf, sizeof(buf), "The candy heart says '%s'.\n\r",
                  candy_heart_words[number_range( 0, n - 1 )] );
        send_to_char( buf, ch );
        return;

    case OBJ_VNUM_SEASONAL_CANDY:
        switch ( number_range( 1, 6 ) )
        {
        case 1:
            send_to_char( "Treat! A warm, sugary glow fills you.\n\r", ch );
            holiday_cast( "refresh", 15, ch, ch );
            break;
        case 2:
            send_to_char( "Treat! You feel a little less battered.\n\r", ch );
            holiday_cast( "cure light", 15, ch, ch );
            break;
        case 3:
            send_to_char( "Treat! You feel blessed.\n\r", ch );
            holiday_cast( "bless", 15, ch, ch );
            break;
        case 4:
            send_to_char( "Trick! Your teeth glow orange for a moment.\n\r", ch );
            act( "$n grins, and $s teeth glow pumpkin orange for a moment.",
                 ch, NULL, NULL, TO_ROOM );
            break;
        case 5:
            send_to_char( "Trick! You let out an enormous, ghostly hiccup.\n\r", ch );
            act( "$n hiccups, and a tiny ghost pops out and flies away.",
                 ch, NULL, NULL, TO_ROOM );
            break;
        default:
            send_to_char( "Trick! A bat flies out of the wrapper and away.\n\r", ch );
            act( "A bat flutters out of $n's candy wrapper and away into the dark.",
                 ch, NULL, NULL, TO_ROOM );
            break;
        }
        return;
    }
}

/* do_give, once a thing has changed hands: a rose given to another
   player blesses both and is spent. True when obj is gone. */
bool holiday_given( CHAR_DATA *ch, CHAR_DATA *victim, OBJ_DATA *obj )
{
    if ( ch == NULL || victim == NULL || obj == NULL || obj->pIndexData == NULL
    ||   obj->pIndexData->vnum != OBJ_VNUM_RED_ROSE )
        return false;
    if ( IS_NPC(ch) || IS_NPC(victim) || ch == victim )
        return false;

    act( "The rose blooms in $N's hands, and its petals drift over you both.",
         ch, NULL, victim, TO_CHAR );
    act( "The rose blooms in your hands, and its petals drift over you both.",
         ch, NULL, victim, TO_VICT );
    act( "The rose $n gave $N blooms, and its petals drift over them both.",
         ch, NULL, victim, TO_NOTVICT );
    extract_obj( obj );
    holiday_cast( "bless", 20, ch, ch );
    if ( ch->in_room != NULL && victim->in_room != NULL )
        holiday_cast( "bless", 20, victim, victim );
    if ( !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
        achievement_record_event( ch, ACHIEVEMENT_EVENT_HOLIDAY_ROSE, true );
    return true;
}

/* When each area last heard a firework burst overhead. One slot per area
   (review, 2026-11-02: a single "last area" forgot A's burst as soon as
   B had one, so A, B, A broadcast three times in a few seconds). Areas
   are few and never freed, so a slot is kept for good; past the table's
   end the oldest slot is reused, which errs toward a broadcast. */
#define FIREWORK_AREAS  512
static HOLIDAY_COOLDOWN firework_heard[FIREWORK_AREAS];

/* True, and the area's clock started, when it may hear another burst
   (holiday_cooldown_ready, which tests/test_holiday_rules.c plays at
   the boundary). */
static bool firework_area_ready( AREA_DATA *area )
{
    return holiday_cooldown_ready( firework_heard, FIREWORK_AREAS, area,
                                   (long) current_time, FIREWORK_AREA_GAP ) != 0;
}

/* do_drop, a single thing dropped: a firework goes up. True when obj is
   gone. The whole area sees it, but no more than once in a while, so a
   bag of rockets cannot be a way to shout. */
bool holiday_dropped( CHAR_DATA *ch, OBJ_DATA *obj )
{
    static const char *bursts[] =
    {
        "{0Ca shower of green and gold stars{00",
        "{09a great red chrysanthemum of sparks{00",
        "{0Da crackling purple willow that drips to the ground{00",
        "{0Ba ring of blue fire that spins as it fades{00",
        "{0Ea burst of gold that rains down glittering{00",
        NULL
    };
    DESCRIPTOR_DATA *d;
    AREA_DATA *area;
    char buf[MAX_STRING_LENGTH];
    int n;

    if ( ch == NULL || obj == NULL || obj->pIndexData == NULL
    ||   obj->pIndexData->vnum != OBJ_VNUM_FIREWORK || ch->in_room == NULL )
        return false;

    for ( n = 0; bursts[n] != NULL; n++ )
        ;
    n = number_range( 0, n - 1 );
    act( "$p fizzes, whistles straight up into the sky and bursts!", ch, obj, NULL, TO_CHAR );
    act( "$p fizzes, whistles straight up into the sky and bursts!", ch, obj, NULL, TO_ROOM );
    extract_obj( obj );
    if ( !IS_NPC(ch) && !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
        achievement_record_event( ch, ACHIEVEMENT_EVENT_HOLIDAY_FIREWORK, true );

    area = ch->in_room->area;
    if ( !firework_area_ready( area ) )
        return true;

    snprintf( buf, sizeof(buf), "Overhead, a firework bursts into %s.\n\r", bursts[n] );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *who = d->character;

        if ( d->connected != CON_PLAYING || who == NULL || who->in_room == NULL
        ||   who->in_room->area != area || !IS_AWAKE(who) )
            continue;
        if ( IS_SET( who->in_room->room_flags, ROOM_INDOORS ) )
            continue;
        send_to_char( buf, who );
    }
    return true;
}

/* raw_kill, before the corpse is made: a clover's luck turns the kill
   into a pot of gold, put in the victim's purse so make_corpse lays it
   out with the rest of its coin. */
void holiday_kill( CHAR_DATA *ch, CHAR_DATA *victim )
{
    long gold;

    if ( ch == NULL || victim == NULL || IS_NPC(ch) || !IS_NPC(victim)
    ||   ch->pcdata->holiday_luck <= 0 || ch == victim )
        return;
    ch->pcdata->holiday_luck--;
    gold = black_market_kill_value( victim->level ) * POT_OF_GOLD_KILLS;
    gain_copper( victim, gold );
    act( "{0ELuck is with you: a pot of gold tumbles out of $N's things!{00",
         ch, NULL, victim, TO_CHAR );
    act( "A pot of gold tumbles out of $N's things!", ch, NULL, victim, TO_ROOM );
    if ( !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
        achievement_record_event( ch, ACHIEVEMENT_EVENT_HOLIDAY_GOLD, true );
}


/* ------------------------------------------------ the fair in the square */

/* extract_char, before the CHAR_DATA can be reused: the vendor is
   gone, whatever took them. Comparing addresses against the character
   list instead was fooled by the next mobile created, which the pool
   hands the same address (review, 2026-11-02: PURGE ROSALIND then LOAD
   MOB made the loaded guard "the vendor", and the next holiday's change
   took the guard away). vendor_holiday stays, so the tick puts the same
   holiday's vendor back quietly. */
void holiday_forget( CHAR_DATA *ch )
{
    if ( ch != NULL && ch == event_vendor )
        event_vendor = NULL;
}

/* One of each, as a shop's endless stock (ITEM_INVENTORY): BUY hands over
   a fresh copy and LIST shows the item once. Madame Hexley used to carry
   ten plain copies of each, and LIST printed all twenty (2026-10-23). */
static void give_vendor_items( CHAR_DATA *vendor, const int *wares )
{
    OBJ_INDEX_DATA *pObj;
    OBJ_DATA       *obj;
    int             i;

    for ( i = 0; i < 4 && wares[i] != 0; i++ )
    {
        if ( ( pObj = get_obj_index( wares[i] ) ) == NULL )
            continue;
        obj = create_object( pObj, 0 );
        SET_BIT( obj->extra_flags, ITEM_INVENTORY );
        obj_to_char( obj, vendor );
    }
}

static void holiday_shout( const char *msg )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof(buf), "{%02X[Event] %s{00\n\r", COL_SHOUTS, msg );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        if ( d->connected != CON_PLAYING || d->character == NULL )
            continue;
        if ( IS_SET(d->character->comm, COMM_NOSHOUT)
        ||   IS_SET(d->character->comm, COMM_QUIET) )
            continue;
        send_to_char( buf, d->character );
    }
}

static void vendor_leave( void )
{
    if ( event_vendor != NULL )
    {
        if ( vendor_holiday != NULL && vendor_holiday->vendor_leave != NULL )
            act( vendor_holiday->vendor_leave, event_vendor, NULL, NULL, TO_ROOM );
        extract_char( event_vendor, true );   /* holiday_forget clears it */
    }
    event_vendor = NULL;
    vendor_holiday = NULL;
}

static void vendor_arrive( const HOLIDAY *h, bool loud )
{
    MOB_INDEX_DATA *pMob;
    ROOM_INDEX_DATA *room;

    if ( h == NULL || h->vendor_vnum == 0 )
        return;
    if ( ( room = get_room_index( VENDOR_SPAWN_ROOM ) ) == NULL
    ||   ( pMob = get_mob_index( h->vendor_vnum ) ) == NULL )
    {
        bug( "holiday vendor: missing room or mobile %d.", h->vendor_vnum );
        return;
    }
    event_vendor = create_mobile( pMob );
    char_to_room( event_vendor, room );
    give_vendor_items( event_vendor, h->wares );
    vendor_holiday = h;
    act( "$n arrives and sets out $s wares.", event_vendor, NULL, NULL, TO_ROOM );
    if ( loud && h->vendor_arrive != NULL )
        holiday_shout( h->vendor_arrive );
}

/* The decoration in the square, found by vnum rather than kept as a
   pointer, so a purge cannot leave one dangling. */
static OBJ_DATA *decoration_in( ROOM_INDEX_DATA *room, int vnum )
{
    OBJ_DATA *obj;

    if ( room == NULL || vnum == 0 )
        return NULL;
    for ( obj = room->contents; obj != NULL; obj = obj->next_content )
        if ( obj->pIndexData != NULL && obj->pIndexData->vnum == vnum )
            return obj;
    return NULL;
}

/* A painted egg lying on the ground (not carried, not inside anything). */
static bool egg_lying( const OBJ_DATA *obj )
{
    return obj->pIndexData != NULL && obj->pIndexData->vnum == OBJ_VNUM_PAINTED_EGG
        && obj->in_room != NULL;
}

/* Eggs lying in one area's rooms, or anywhere with area NULL. The hunt's
   budget counts only the square's own area, where hide_an_egg puts them:
   counting the world let a dozen eggs dropped elsewhere stop the hunt
   for good (review, 2026-11-02). */
static int eggs_lying( const AREA_DATA *area )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    int n = 0;

    FOR_EACH_OBJECT( iter, obj )
        if ( egg_lying( obj ) && ( area == NULL || obj->in_room->area == area ) )
            n++;
    return n;
}

/* When Noblegarden ends: every egg on the ground anywhere, however many.
   It gathered into a fixed array before and left everything past the
   ninety-sixth (review, 2026-11-02). Extracting as it walks is safe: the
   object list tombstones what is removed (list.c), the egg's own
   contents included, and the iterator steps over them. Eggs someone
   carries, or has put in a bag, are theirs and stay. */
static int eggs_clear( void )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    int n = 0;

    FOR_EACH_OBJECT( iter, obj )
        if ( egg_lying( obj ) )
        {
            extract_obj( obj );
            n++;
        }
    return n;
}

/* Somewhere a player can walk in and find an egg: not the square
   itself, not the sky, deep or under water, and not an arena. A pick
   that fails is tried again, up to eight times, so a refresh hides an
   egg rather than now and then giving up on a single unlucky roll. */
static bool egg_room_ok( const ROOM_INDEX_DATA *room, const ROOM_INDEX_DATA *square )
{
    return room != NULL && room != square
        && room->sector_type != SECT_AIR
        && room->sector_type != SECT_WATER_NOSWIM
        && room->sector_type != SECT_UNDER_WATER
        && !IS_SET( room->room_flags, ROOM_ARENA );
}

static void hide_an_egg( void )
{
    ROOM_INDEX_DATA *square = get_room_index( VENDOR_SPAWN_ROOM );
    ROOM_INDEX_DATA *room = NULL;
    OBJ_DATA *egg;
    int tries;

    if ( square == NULL )
        return;
    for ( tries = 0; tries < 8 && !egg_room_ok( room, square ); tries++ )
        room = random_scatter_room( square->area );
    if ( !egg_room_ok( room, square ) || ( egg = holiday_make( OBJ_VNUM_PAINTED_EGG ) ) == NULL )
        return;
    holiday_fill( egg, number_range( 5, 30 ) );
    obj_to_room( egg, room );
}

/* Once a tick, from tick_event_boss, and by HOLIDAYS REFRESH: put the
   fair up for what is on and take down what is over. Loud only when the
   change happened on its own, not at boot. */
void holiday_tick( void )
{
    static bool booted = false;
    const HOLIDAY *h = holiday_current();
    ROOM_INDEX_DATA *square = get_room_index( VENDOR_SPAWN_ROOM );
    OBJ_DATA *decor;
    bool loud = booted;
    bool fresh = false;

    booted = true;

    if ( decorated != h )
    {
        if ( decorated != NULL
        &&   ( decor = decoration_in( square, decorated->decor_vnum ) ) != NULL )
            extract_obj( decor );
        if ( decorated != NULL && decorated->drop_vnum == OBJ_VNUM_PAINTED_EGG )
            eggs_clear();
        decorated = h;
    }
    if ( vendor_holiday != h )
    {
        vendor_leave();
        fresh = true;
    }
    if ( h == NULL )
        return;

    if ( h->decor_vnum != 0 && square != NULL
    &&   decoration_in( square, h->decor_vnum ) == NULL )
    {
        OBJ_DATA *obj = holiday_make( h->decor_vnum );

        if ( obj != NULL )
            obj_to_room( obj, square );
    }
    /* Announced only when a holiday begins, not when a purged vendor
       is put back. */
    if ( event_vendor == NULL )
        vendor_arrive( h, loud && fresh );

    if ( h->drop_vnum == OBJ_VNUM_PAINTED_EGG && telnet_count_players() > 0
    &&   square != NULL && eggs_lying( square->area ) < EGG_CEILING )
        hide_an_egg();
}

/* At login, after the notes: what is on. */
void holiday_login_notice( CHAR_DATA *ch )
{
    const HOLIDAY *h = holiday_current();
    char buf[MAX_STRING_LENGTH];

    if ( h == NULL || ch == NULL )
        return;
    snprintf( buf, sizeof(buf), "\n\r{0E%s{00\n\r", h->greeting );
    send_to_char( buf, ch );
}

/* Every shopkeeper's word at LIST. */
void holiday_shop_flavour( CHAR_DATA *keeper, CHAR_DATA *ch )
{
    const HOLIDAY *h = holiday_current();

    if ( h != NULL && h->shop_line != NULL )
        act( h->shop_line, keeper, NULL, ch, TO_VICT );
}


/* ------------------------------------------------------- HOLIDAYS */

static void holiday_span_words( const HOLIDAY *h, int y, char *buf, size_t size )
{
    static const char *months[] = { "", "Jan", "Feb", "Mar", "Apr", "May",
        "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
    long first, last;
    int fy, fm, fd, ly, lm, ld;

    holiday_span( h, y, h->rule == RULE_FIXED ? h->m1 : 6, &first, &last );
    holiday_civil_from_days( first, &fy, &fm, &fd );
    holiday_civil_from_days( last, &ly, &lm, &ld );
    UNUSED_PARAM( fy );
    UNUSED_PARAM( ly );
    if ( first == last )
        snprintf( buf, size, "%s %2d", months[fm], fd );
    else
        snprintf( buf, size, "%s %2d - %s %2d", months[fm], fd, months[lm], ld );
}

/* What a staff HOLIDAYS adds: where the date came from, what is on and
   why, which seasonal areas boot loaded (they change only at a reboot,
   so they can disagree with the calendar), and the fair as it stands. */
static void holiday_staff_lines( CHAR_DATA *ch, const HOLIDAY *now )
{
    ROOM_INDEX_DATA *square = get_room_index( VENDOR_SPAWN_ROOM );
    const char *forced = getenv( "TOC_SEASON" );
    const char *file = getenv( "TOC_DATE_FILE" );
    const char *loaded = season_loaded_name();
    const char *source;
    char buf[MAX_STRING_LENGTH];
    char decor[MAX_INPUT_LENGTH];
    int y, m, d;

    if ( holiday_test_date( &y, &m, &d ) )
        source = file != NULL && file[0] != '\0' ? "TOC_DATE_FILE" : "TOC_DATE";
    else
    {
        holiday_date( &y, &m, &d );
        source = "the host's clock, local time";
    }
    snprintf( buf, sizeof(buf), "\n\r[staff] date %04d-%02d-%02d, from %s.\n\r",
              y, m, d, source );
    send_to_char( buf, ch );

    if ( forced != NULL && forced[0] != '\0'
    &&   ( !str_cmp( forced, "none" ) || !str_cmp( forced, "off" )
           || holiday_by_key( forced ) != NULL ) )
        snprintf( buf, sizeof(buf), "[staff] holiday: %s (TOC_SEASON=%s sets it, "
                  "not the date).\n\r", now != NULL ? now->name : "none", forced );
    else
        snprintf( buf, sizeof(buf), "[staff] holiday: %s, by the calendar.\n\r",
                  now != NULL ? now->name : "none" );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf),
              "[staff] seasonal areas loaded at boot: %s%s\n\r",
              loaded != NULL ? loaded : "the ordinary ones",
              ( loaded == NULL ) != ( get_season_name() == NULL )
              || ( loaded != NULL && get_season_name() != NULL
                   && strcmp( loaded, get_season_name() ) )
                  ? " -- not the season now; they change only at a reboot." : "." );
    send_to_char( buf, ch );

    if ( now == NULL || now->decor_vnum == 0 )
        toc_strlcpy( decor, "none", sizeof(decor) );
    else
        snprintf( decor, sizeof(decor), "%s",
                  decoration_in( square, now->decor_vnum ) != NULL ? "standing" : "missing" );
    if ( event_vendor != NULL )
        snprintf( buf, sizeof(buf), "[staff] fair: vendor %s (mob %d) in room %d; "
                  "decoration %s; eggs lying in the square's area %d of %d, "
                  "anywhere %d.\n\r",
                  event_vendor->short_descr,
                  event_vendor->pIndexData != NULL ? event_vendor->pIndexData->vnum : 0,
                  event_vendor->in_room != NULL ? event_vendor->in_room->vnum : 0,
                  decor, square != NULL ? eggs_lying( square->area ) : 0, EGG_CEILING,
                  eggs_lying( NULL ) );
    else
        snprintf( buf, sizeof(buf), "[staff] fair: no vendor; decoration %s; eggs "
                  "lying in the square's area %d of %d, anywhere %d.\n\r",
                  decor, square != NULL ? eggs_lying( square->area ) : 0, EGG_CEILING,
                  eggs_lying( NULL ) );
    send_to_char( buf, ch );
    send_to_char( "[staff] HOLIDAYS REFRESH puts the fair up now.\n\r", ch );
}

/* HOLIDAYS: what is on, and the year's calendar. HOLIDAYS <year> shows
   another year's dates and HOLIDAYS ON <yyyy-mm-dd> what any one day
   would be, from the same code as today. Staff: HOLIDAYS REFRESH puts up
   the fair now instead of at the next tick. */
void do_holidays( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char when[64];
    const HOLIDAY *now;
    int y, m, d, i;

    argument = one_argument( argument, arg );
    holiday_date( &y, &m, &d );

    if ( !str_cmp( arg, "refresh" ) && IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
    {
        holiday_tick();
        send_to_char( "The fair in the Oak Tree Square is up to date.\n\r", ch );
        return;
    }
    if ( !str_cmp( arg, "on" ) )
    {
        const HOLIDAY *then;
        char date[MAX_INPUT_LENGTH];

        one_argument( argument, date );
        if ( !holiday_parse_date( date, &y, &m, &d ) )
        {
            send_to_char( "Name a real day as YYYY-MM-DD, from 1900 to 9999: "
                          "HOLIDAYS ON 2027-03-28.\n\r", ch );
            return;
        }
        then = holiday_on( y, m, d );
        if ( then != NULL )
            snprintf( buf, sizeof(buf), "On %04d-%02d-%02d the world celebrates %s.\n\r",
                      y, m, d, then->name );
        else
            snprintf( buf, sizeof(buf), "No holiday falls on %04d-%02d-%02d.\n\r",
                      y, m, d );
        send_to_char( buf, ch );
        return;
    }
    if ( is_number( arg ) )
    {
        int asked = atoi( arg );

        if ( asked < 1900 || asked > 9999 )
        {
            send_to_char( "Name a year from 1900 to 9999.\n\r", ch );
            return;
        }
        y = asked;
    }
    else if ( arg[0] != '\0' )
    {
        send_to_char( "HOLIDAYS, HOLIDAYS <year> or HOLIDAYS ON <yyyy-mm-dd>.\n\r", ch );
        return;
    }

    now = holiday_current();
    if ( now != NULL )
    {
        snprintf( buf, sizeof(buf), "The world is celebrating %s!\n\r%s\n\r\n\r",
                  now->name, now->greeting );
        send_to_char( buf, ch );
    }
    else
        send_to_char( "No holiday is being celebrated just now.\n\r\n\r", ch );

    snprintf( buf, sizeof(buf), "The holidays of %d:\n\r", y );
    send_to_char( buf, ch );
    for ( i = 0; holidays[i].key != NULL; i++ )
    {
        holiday_span_words( &holidays[i], y, when, sizeof(when) );
        snprintf( buf, sizeof(buf), "  %-30s %s%s\n\r", holidays[i].name, when,
                  &holidays[i] == now ? "   <-- now" : "" );
        send_to_char( buf, ch );
    }
    send_to_char( "\n\rHELP HOLIDAYS says what each one brings.\n\r", ch );

    if ( IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
        holiday_staff_lines( ch, now );
}
