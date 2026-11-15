/*
 * errand.c -- ERRAND: three starter errands and the expedition (2026-11-15).
 *
 * Three short jobs about town for a character's first levels, each taken
 * by choice and paid once: a fight (three creatures in Mud School), a
 * delivery (Melancholy's letter to the questmaster at the top of the oak)
 * and a walk (four landmarks: the Oak Tree Square, the Temple altar, the
 * training yard and the Hall of Heroes). Then, from level 5, an expedition:
 * an area at the character's level with two or three of its creatures to
 * slay, chosen from what resets place there, paid at most once a day.
 *
 * Progress counts only once a job is taken. Pay is small -- a tenth of a
 * level for an errand, a quarter for an expedition, and coin worth five or
 * fifteen kills at the character's level -- and staff (by level) take none.
 * Saved as "Errand <done> <taken> <kills> <letter> <seen>" and "Expedition
 * <area> <mob> <mob> <mob> <got> <day> <wait>" under case 'E' (save.c).
 */
#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <string.h>
#include "merc.h"
#include "interp.h"
#include "dstring.h"

extern AREA_DATA *area_first;

#define ERRAND_PESTS        0
#define ERRAND_LETTER       1
#define ERRAND_TOWN         2
#define ERRANDS             3
#define ERRAND_MAX_LEVEL    10            /* taken up to this level */
#define ERRAND_PEST_KILLS   3
#define ERRAND_SCHOOL_FILE  "school.are"
#define ERRAND_CLERK        2429          /* Melancholy, the guild clerk */
#define ERRAND_QUESTMASTER  201           /* at the top of the oak */
#define EXPEDITION_MIN_LEVEL 5
#define EXPEDITION_MAX_LEVEL 59
#define EXPEDITION_WAIT     ( 10 * 60 )   /* after giving one up */
#define EXPEDITION_TRIES    12            /* areas tried for a route */

static const int town_rooms[] = { 2401, 4208, 2419, 4649 };
static const char *const town_names[] = {
    "the Oak Tree Square", "the Temple altar", "the training yard", "the Hall of Heroes"
};
#define TOWN_ROOMS 4

static const char *const errand_titles[ERRANDS] = {
    "Pests: slay three creatures in Mud School",
    "A letter: Melancholy's, to the questmaster",
    "The town: see four landmarks of Dresden"
};

static bool errand_player( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL && !is_staff( ch );
}

static bool errand_bit( int set, int i )
{
    return ( set & ( 1 << i ) ) != 0;
}

/* Whether any errand is still to be had: ADVENTURE mentions them then. */
bool errand_offered( CHAR_DATA *ch )
{
    int i;

    if ( !errand_player( ch ) || ch->level > ERRAND_MAX_LEVEL )
        return false;
    for ( i = 0; i < ERRANDS; i++ )
        if ( !errand_bit( ch->pcdata->errand_done, i )
        &&   !errand_bit( ch->pcdata->errand_taken, i ) )
            return true;
    return false;
}

static long errand_day( void )
{
    return (long) ( current_time / 86400 );
}

static AREA_DATA *expedition_area( long id )
{
    AREA_DATA *area;

    if ( id == 0 )
        return NULL;
    for ( area = area_first; area != NULL; area = area->next )
        if ( achievement_area_id( area ) == id )
            return area;
    return NULL;
}

static bool mob_here( CHAR_DATA *ch, int vnum )
{
    CHAR_DATA *rch;

    if ( ch->in_room == NULL )
        return false;
    for ( rch = ch->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( IS_NPC(rch) && rch->pIndexData != NULL && rch->pIndexData->vnum == vnum
        &&   can_see( ch, rch ) )
            return true;
    return false;
}

/* Pay a job: experience and coin, said, saved and journalled. */
static void errand_pay( CHAR_DATA *ch, const char *what, int exp_share, int kills )
{
    char buf[MAX_STRING_LENGTH], price[64];
    long coin = black_market_kill_value( ch->level ) * kills;
    int exp = exp_per_level( ch, ch->pcdata->points ) / exp_share;
    long before = ch->exp;

    playlog_exp_as( "errand" );
    gain_exp( ch, exp );
    playlog_coin_as( "errands" );
    if ( !gain_copper( ch, coin ) )
        coin = 0;
    playlog_coin_as( NULL );
    if ( coin > 0 )
        format_price( coin, price, sizeof(price) );
    else
        toc_strlcpy( price, "nothing", sizeof(price) );
    snprintf( buf, sizeof(buf), "%s  You gain %ld experience and %s.\n\r",
              what, ch->exp - before, price );
    send_to_char( buf, ch );
    save_char_obj( ch );
}

static void errand_finish( CHAR_DATA *ch, int i, const char *how )
{
    char buf[MAX_STRING_LENGTH];

    ch->pcdata->errand_taken &= ~( 1 << i );
    ch->pcdata->errand_done |= 1 << i;
    snprintf( buf, sizeof(buf), "{0FErrand done:{00 %s.", how );
    errand_pay( ch, buf, 10, 5 );
    playlog_outcome( ch, "errand", "success", errand_titles[i], NULL, NULL );
}

/* A kill that pays the character (group_gain, beside diary_kill). */
void errand_kill( CHAR_DATA *ch, CHAR_DATA *victim )
{
    PC_DATA *pc;
    AREA_DATA *area;
    int i;

    if ( !errand_player( ch ) || victim == NULL || !IS_NPC(victim)
    ||   victim->pIndexData == NULL || victim->in_room == NULL
    ||   ( area = victim->in_room->area ) == NULL )
        return;
    pc = ch->pcdata;
    if ( errand_bit( pc->errand_taken, ERRAND_PESTS ) && area->file_name != NULL
    &&   !str_cmp( area->file_name, ERRAND_SCHOOL_FILE ) )
    {
        pc->errand_kills = UMIN( ERRAND_PEST_KILLS, pc->errand_kills + 1 );
        if ( pc->errand_kills >= ERRAND_PEST_KILLS )
            errand_finish( ch, ERRAND_PESTS, "three of Mud School's creatures slain" );
        else
        {
            char buf[MAX_STRING_LENGTH];

            snprintf( buf, sizeof(buf), "Errand: %d of %d of Mud School's creatures slain.\n\r",
                      pc->errand_kills, ERRAND_PEST_KILLS );
            send_to_char( buf, ch );
        }
    }
    if ( pc->expedition_area == 0 || achievement_area_id( area ) != pc->expedition_area )
        return;
    for ( i = 0; i < 3; i++ )
    {
        if ( pc->expedition_mob[i] != victim->pIndexData->vnum
        ||   errand_bit( pc->expedition_got, i ) )
            continue;
        pc->expedition_got |= 1 << i;
        break;
    }
    if ( i == 3 )
        return;
    for ( i = 0; i < 3; i++ )
        if ( pc->expedition_mob[i] > 0 && !errand_bit( pc->expedition_got, i ) )
        {
            send_to_char( "Expedition: one more of its creatures slain.  ERRAND shows the rest.\n\r", ch );
            return;
        }
    pc->expedition_area = 0;
    pc->expedition_got = 0;
    memset( pc->expedition_mob, 0, sizeof(pc->expedition_mob) );
    pc->expedition_day = errand_day();
    errand_pay( ch, "{0FExpedition done:{00 every creature it asked for slain.", 4, 15 );
    playlog_outcome( ch, "expedition", "success", NULL, NULL, NULL );
}

/* What the character stands and looks in (do_look's room view, beside the
   tutorial's): the town walk's landmarks. */
void errand_room_seen( CHAR_DATA *ch )
{
    PC_DATA *pc;
    int i;

    if ( !errand_player( ch ) || ch->in_room == NULL
    ||   !errand_bit( ch->pcdata->errand_taken, ERRAND_TOWN ) )
        return;
    pc = ch->pcdata;
    for ( i = 0; i < TOWN_ROOMS; i++ )
    {
        char buf[MAX_STRING_LENGTH];
        int j, seen = 0;

        if ( ch->in_room->vnum != town_rooms[i] || errand_bit( pc->errand_seen, i ) )
            continue;
        /* Only the room stood in: a clairvoyant look borrows in_room. */
        {
            CHAR_DATA *rch;

            for ( rch = ch->in_room->people; rch != NULL && rch != ch; rch = rch->next_in_room )
                ;
            if ( rch == NULL )
                return;
        }
        pc->errand_seen |= 1 << i;
        for ( j = 0; j < TOWN_ROOMS; j++ )
            if ( errand_bit( pc->errand_seen, j ) )
                seen++;
        if ( seen >= TOWN_ROOMS )
        {
            errand_finish( ch, ERRAND_TOWN, "all four landmarks seen" );
            return;
        }
        snprintf( buf, sizeof(buf), "Errand: %s seen, %d of %d.\n\r", town_names[i], seen, TOWN_ROOMS );
        send_to_char( buf, ch );
        return;
    }
}

/* The letter, collected or delivered when its people are here. */
static bool errand_letter_step( CHAR_DATA *ch )
{
    PC_DATA *pc = ch->pcdata;

    if ( !errand_bit( pc->errand_taken, ERRAND_LETTER ) )
        return false;
    if ( pc->errand_letter == 0 && mob_here( ch, ERRAND_CLERK ) )
    {
        pc->errand_letter = 1;
        send_to_char( "Melancholy hands you a sealed letter: \"For the questmaster, at the top\n\r"
                      "of the oak.  WALKTO SQUARE, then climb UP, and ERRAND again there.\"\n\r", ch );
        save_char_obj( ch );
        return true;
    }
    if ( pc->errand_letter == 1 && mob_here( ch, ERRAND_QUESTMASTER ) )
    {
        pc->errand_letter = 0;
        send_to_char( "The questmaster breaks the seal, reads, and nods.  \"AQUEST REQUEST,\n\r"
                      "when you want work.\"\n\r", ch );
        errand_finish( ch, ERRAND_LETTER, "Melancholy's letter delivered" );
        return true;
    }
    return false;
}

static void errand_status( CHAR_DATA *ch )
{
    PC_DATA *pc = ch->pcdata;
    DString out;
    AREA_DATA *area;
    int i;

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &out, "Errands about town, each paid once (taken up to level 10):\n\r" );
    for ( i = 0; i < ERRANDS; i++ )
    {
        char mark[24];

        if ( errand_bit( pc->errand_done, i ) )
            toc_strlcpy( mark, "done", sizeof(mark) );
        else if ( !errand_bit( pc->errand_taken, i ) )
            toc_strlcpy( mark, "    ", sizeof(mark) );
        else if ( i == ERRAND_PESTS )
            snprintf( mark, sizeof(mark), "%d/%d", pc->errand_kills, ERRAND_PEST_KILLS );
        else if ( i == ERRAND_LETTER )
            toc_strlcpy( mark, pc->errand_letter ? "held" : "on", sizeof(mark) );
        else
        {
            int j, seen = 0;

            for ( j = 0; j < TOWN_ROOMS; j++ )
                if ( errand_bit( pc->errand_seen, j ) )
                    seen++;
            snprintf( mark, sizeof(mark), "%d/%d", seen, TOWN_ROOMS );
        }
        dstring_printf( &out, "  [%-4s] %d. %s\n\r", mark, i + 1, errand_titles[i] );
    }
    if ( errand_bit( pc->errand_taken, ERRAND_PESTS ) )
        dstring_append_cstr( &out, "  Pests: WALKTO MUD SCHOOL; any creature there counts.\n\r" );
    if ( errand_bit( pc->errand_taken, ERRAND_LETTER ) )
        dstring_append_cstr( &out, pc->errand_letter
            ? "  Letter: WALKTO SQUARE, climb UP to the questmaster, and type ERRAND.\n\r"
            : "  Letter: WALKTO MELANCHOLY and type ERRAND there to collect it.\n\r" );
    if ( errand_bit( pc->errand_taken, ERRAND_TOWN ) )
    {
        dstring_append_cstr( &out, "  Town: still to see --" );
        for ( i = 0; i < TOWN_ROOMS; i++ )
            if ( !errand_bit( pc->errand_seen, i ) )
                dstring_printf( &out, " %s;", town_names[i] );
        dstring_append_cstr( &out, "\n\r  (WALKTO SQUARE, WALKTO ALTAR, WALKTO DUMMY; the Hall is DOWN from the\n\r"
                                   "  square's centre.)\n\r" );
    }

    if ( ( area = expedition_area( pc->expedition_area ) ) != NULL )
    {
        char walk[ADVENTURE_PLACE_LEN];

        if ( walkto_area_walk_name( area, walk, sizeof(walk) ) )
            dstring_printf( &out, "Expedition: WALKTO %s and slay one each of:\n\r", walk );
        else
            dstring_printf( &out, "Expedition: in %s, slay one each of:\n\r", area_shown_name( area->name ) );
        for ( i = 0; i < 3; i++ )
        {
            MOB_INDEX_DATA *mob = get_mob_index( pc->expedition_mob[i] );

            if ( pc->expedition_mob[i] <= 0 || mob == NULL )
                continue;
            dstring_printf( &out, "  [%-4s] %s (level %d)\n\r",
                            errand_bit( pc->expedition_got, i ) ? "done" : "",
                            mob->short_descr, mob->level );
        }
        dstring_append_cstr( &out, "ERRAND EXPEDITION ABANDON gives it up.\n\r" );
    }
    else if ( ch->level >= EXPEDITION_MIN_LEVEL )
        dstring_append_cstr( &out, pc->expedition_day == errand_day()
            ? "Expedition: one finished today; another tomorrow.\n\r"
            : "Expedition: ERRAND EXPEDITION sends you to an area at your level.\n\r" );
    dstring_append_cstr( &out, "ERRAND TAKE <1-3|ALL> takes an errand; ERRAND ABANDON <1-3> drops one.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}

/* An area at the level, a route to it, and two or three creatures there. */
static void expedition_take( CHAR_DATA *ch )
{
    PC_DATA *pc = ch->pcdata;
    AREA_DATA *cands[512], *area;
    MOB_INDEX_DATA *prey[16];
    char buf[MAX_STRING_LENGTH];
    int ncand = 0, tries, level = UMIN( ch->level, EXPEDITION_MAX_LEVEL );

    if ( ch->level < EXPEDITION_MIN_LEVEL )
    {
        send_to_char( "Expeditions start at level 5.  The errands come first.\n\r", ch );
        return;
    }
    if ( pc->expedition_area != 0 )
    {
        send_to_char( "You are on one already: ERRAND shows it.\n\r", ch );
        return;
    }
    if ( pc->expedition_day == errand_day() )
    {
        send_to_char( "You finished an expedition today.  Another tomorrow.\n\r", ch );
        return;
    }
    if ( pc->expedition_wait > current_time )
    {
        snprintf( buf, sizeof(buf), "You gave one up a moment ago: another in %ld minute%s.\n\r",
                  ( pc->expedition_wait - current_time + 59 ) / 60,
                  ( pc->expedition_wait - current_time + 59 ) / 60 == 1 ? "" : "s" );
        send_to_char( buf, ch );
        return;
    }
    for ( area = area_first; area != NULL && ncand < 512; area = area->next )
    {
        char walk[ADVENTURE_PLACE_LEN];
        int low, high;

        if ( !walkto_area_level_range( area, &low, &high ) || level < low || level > high
        ||   !walkto_area_walk_name( area, walk, sizeof(walk) )
        ||   hunting_area_prey( area, level, prey, 16 ) < 2 )
            continue;
        cands[ncand++] = area;
    }
    for ( tries = 0; tries < EXPEDITION_TRIES && ncand > 0; tries++ )
    {
        int pick = number_range( 0, ncand - 1 ), n, i;

        area = cands[pick];
        cands[pick] = cands[--ncand];
        if ( !walkto_area_reachable( ch, area ) )
            continue;
        n = hunting_area_prey( area, level, prey, 16 );
        /* Up to three, at random, all different. */
        for ( i = 0; i < n; i++ )
        {
            int j = number_range( i, n - 1 );
            MOB_INDEX_DATA *t = prey[i];

            prey[i] = prey[j];
            prey[j] = t;
        }
        memset( pc->expedition_mob, 0, sizeof(pc->expedition_mob) );
        for ( i = 0; i < 3 && i < n; i++ )
            pc->expedition_mob[i] = prey[i]->vnum;
        pc->expedition_area = achievement_area_id( area );
        pc->expedition_got = 0;
        save_char_obj( ch );
        send_to_char( "An expedition: slay one each of a few creatures at your level.\n\r", ch );
        errand_status( ch );
        return;
    }
    send_to_char( "No area at your level has a way there from here just now.  Try again from\n\r"
                  "town, or later.\n\r", ch );
}

static int errand_number( const char *arg )
{
    if ( arg[0] >= '1' && arg[0] <= '3' && arg[1] == '\0' )
        return arg[0] - '1';
    return -1;
}

void do_errand( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
    PC_DATA *pc;
    int i;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players run errands.\n\r", ch );
        return;
    }
    if ( is_staff( ch ) )
    {
        send_to_char( "Errands and expeditions are for players.\n\r", ch );
        return;
    }
    pc = ch->pcdata;
    argument = one_argument( argument, arg );
    one_argument( argument, arg2 );

    if ( arg[0] == '\0' )
    {
        if ( errand_letter_step( ch ) )
            return;
        errand_status( ch );
        return;
    }
    if ( !str_prefix( arg, "take" ) )
    {
        int took = 0, k;

        if ( ch->level > ERRAND_MAX_LEVEL )
        {
            send_to_char( "The errands are for levels 1 to 10.  ERRAND EXPEDITION is yours.\n\r", ch );
            return;
        }
        i = errand_number( arg2 );
        if ( str_cmp( arg2, "all" ) && i < 0 )
        {
            send_to_char( "ERRAND TAKE 1, 2, 3 or ALL.\n\r", ch );
            return;
        }
        for ( k = 0; k < ERRANDS; k++ )
        {
            if ( ( i >= 0 && k != i ) || errand_bit( pc->errand_done, k )
            ||   errand_bit( pc->errand_taken, k ) )
                continue;
            pc->errand_taken |= 1 << k;
            took++;
        }
        if ( took == 0 )
        {
            send_to_char( "Nothing to take: done or taken already.  ERRAND shows them.\n\r", ch );
            return;
        }
        save_char_obj( ch );
        errand_status( ch );
        return;
    }
    if ( !str_prefix( arg, "abandon" ) )
    {
        if ( ( i = errand_number( arg2 ) ) < 0 || !errand_bit( pc->errand_taken, i ) )
        {
            send_to_char( "ERRAND ABANDON and the number of an errand you have taken.\n\r", ch );
            return;
        }
        pc->errand_taken &= ~( 1 << i );
        if ( i == ERRAND_PESTS )
            pc->errand_kills = 0;
        else if ( i == ERRAND_LETTER )
            pc->errand_letter = 0;
        else
            pc->errand_seen = 0;
        save_char_obj( ch );
        send_to_char( "Dropped.  You may take it again whenever you like.\n\r", ch );
        return;
    }
    if ( !str_prefix( arg, "expedition" ) )
    {
        if ( arg2[0] != '\0' && !str_prefix( arg2, "abandon" ) )
        {
            if ( pc->expedition_area == 0 )
            {
                send_to_char( "You are on no expedition.\n\r", ch );
                return;
            }
            pc->expedition_area = 0;
            pc->expedition_got = 0;
            memset( pc->expedition_mob, 0, sizeof(pc->expedition_mob) );
            pc->expedition_wait = current_time + EXPEDITION_WAIT;
            save_char_obj( ch );
            send_to_char( "Given up.  Another in ten minutes.\n\r", ch );
            playlog_outcome( ch, "expedition", "refusal", "abandoned", NULL, NULL );
            return;
        }
        expedition_take( ch );
        return;
    }
    send_to_char( "Syntax: errand                 what you have taken, and the letter's next step\n\r"
                  "        errand take <1-3|all>\n\r"
                  "        errand abandon <1-3>\n\r"
                  "        errand expedition [abandon]\n\r", ch );
}
