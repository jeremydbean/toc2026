/*
 * adventure.c -- ADVENTURE: what a character might do next (2026-11-15).
 *
 * A read-only view a player asks for. It says a few things that apply to
 * this character now, each with the exact command or a route WALKTO
 * already publishes: the Mud School diploma, a first fight and training,
 * the guild choice before level 6, a quest, places at their level, and a
 * group. It shows only what applies, names nothing hidden (no room, no
 * quest target, no player), changes nothing, and is never sent unasked:
 * the TUTORIAL keeps its own hints, on or off as the character set it.
 *
 * It keeps no state of its own. Every line reads what the game already
 * keeps: the tutorial's guild window and diploma lookup
 * (tutorial_guild_choice_open, tutorial_diploma_state), the quest
 * master's refusal (quest_ready_phrase), WALKTO's published areas and the
 * achievements' sets of areas entered and explored
 * (walkto_adventure_areas), the lifetime kill count (AchKills), the
 * practice and training sessions, and the group (is_same_group).
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

#define ADVENTURE_PLACES     3          /* areas offered at a time */
#define ADVENTURE_NEAR       5          /* "near your level" for the group line */
#define ADVENTURE_SCHOOL_MAX 10         /* newbie rooms refuse past this level */

static void adventure_line( DString *out, int *shown, const char *text )
{
    (*shown)++;
    dstring_append_cstr( out, text );
}

/* The diploma, held as it should be, or the way to it. */
static void adventure_school( CHAR_DATA *ch, DString *out, int *shown )
{
    switch ( tutorial_diploma_state( ch ) )
    {
    case DIPLOMA_HELD:
        return;
    case DIPLOMA_CARRIED:
        adventure_line( out, shown,
            "* Your diploma: HOLD DIPLOMA, and keep it held while you level (+10\n\r"
            "  intelligence, wisdom and constitution).\n\r" );
        return;
    case DIPLOMA_STASHED:
        adventure_line( out, shown,
            "* Your diploma is in your stash: WALKTO ALTAR, STASH GET DIPLOMA, then\n\r"
            "  HOLD DIPLOMA.\n\r" );
        return;
    default:
        if ( ch->level > ADVENTURE_SCHOOL_MAX )
            return;
        adventure_line( out, shown,
            "* Mud School: WALKTO MUD SCHOOL, walk north and LOOK SIGN at each sign.  Its\n\r"
            "  diploma, held, adds 10 intelligence, wisdom and constitution.\n\r" );
        return;
    }
}

/* A first fight, and sessions waiting to be spent. */
static void adventure_training( CHAR_DATA *ch, DString *out, int *shown )
{
    char buf[MAX_STRING_LENGTH];

    if ( ch->pcdata->achievement_mob_kills <= 0 )
        adventure_line( out, shown,
            "* First fight: CONSIDER <name> sizes a creature up, KILL <name> fights,\n\r"
            "  FLEE runs, and WIMPY flees for you when you are hurt.\n\r" );
    if ( ch->practice > 0 || ch->train > 0 )
    {
        snprintf( buf, sizeof(buf),
            "* Training: %d practice%s and %d train%s to spend.  GAINLIST shows what to\n\r"
            "  learn and who teaches it; WALKTO TRAINERS lists the trainers.\n\r",
            ch->practice, ch->practice == 1 ? "" : "s",
            ch->train, ch->train == 1 ? "" : "s" );
        adventure_line( out, shown, buf );
    }
}

/* The guild choice, the tutorial's own window: levels 3 to 5, no guild. */
static void adventure_guild( CHAR_DATA *ch, DString *out, int *shown )
{
    char buf[MAX_STRING_LENGTH];

    if ( !tutorial_guild_choice_open( ch ) )
        return;
    snprintf( buf, sizeof(buf),
        "* Guild: choose before level 6%s, or at 6 you join the %s\n\r"
        "  guild free.  HELP GUILDS; WALKTO MELANCHOLY, then JOIN <guild>.\n\r",
        ch->level >= 5 ? " (this is your last level to choose)" : "",
        class_table[ch->class].name );
    adventure_line( out, shown, buf );
}

/* A quest under way, or whether one may be asked for. */
static void adventure_quest( CHAR_DATA *ch, DString *out, int *shown )
{
    /* quest_refusal_text's phrases are a line each. */
    char phrase[160], daily[160], buf[MAX_STRING_LENGTH];
    bool ready, daily_ready;

    if ( ch->level < 3 )
        return;
    if ( IS_SET(ch->act, PLR_QUESTOR) )
    {
        adventure_line( out, shown,
            "* Your quest: AQUEST INFO repeats what you were sent for, AQUEST TIME the\n\r"
            "  time left; WALKTO QUEST walks you to its area.\n\r" );
        return;
    }
    ready = quest_ready_phrase( ch, false, phrase, sizeof(phrase) );
    daily_ready = quest_ready_phrase( ch, true, daily, sizeof(daily) );
    snprintf( buf, sizeof(buf),
        "* Quests: a quest %s.\n\r"
        "  A daily quest: %s.\n\r%s",
        phrase, daily,
        ready || daily_ready
        ? "  WALKTO SQUARE, climb UP the oak, then AQUEST REQUEST or AQUEST DAILY REQUEST.\n\r"
        : "" );
    adventure_line( out, shown, buf );
}

/* Places at their level, from what WALKTO publishes. */
static void adventure_places( CHAR_DATA *ch, DString *out, int *shown )
{
    char names[ADVENTURE_PLACES][ADVENTURE_PLACE_LEN];
    int kind[ADVENTURE_PLACES];
    char buf[MAX_STRING_LENGTH];
    int n, i;

    if ( ( n = walkto_adventure_areas( ch, names, kind, ADVENTURE_PLACES ) ) <= 0 )
        return;
    toc_strlcpy( buf, "* Places at your level (CONSIDER first; MAPS shows how much you have walked):\n\r",
                 sizeof(buf) );
    for ( i = 0; i < n; i++ )
    {
        char line[256];   /* a name of at most 47, a pad, a note */

        snprintf( line, sizeof(line), "    WALKTO %-32s %s\n\r", names[i],
                  kind[i] == ADVENTURE_NEW ? "new to you" : "not yet walked end to end" );
        toc_strlcat( buf, line, sizeof(buf) );
    }
    adventure_line( out, shown, buf );
}

/* A group, or how many players near their level could make one. Counts,
   never names: WHO is where names are. */
static void adventure_group( CHAR_DATA *ch, DString *out, int *shown )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];
    int mates = 0, near = 0;

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || wch == NULL || wch == ch || IS_NPC(wch)
        ||   is_staff( wch ) || !online_can_list( ch, wch ) )
            continue;
        if ( is_same_group( ch, wch ) )
            mates++;
        else if ( wch->level >= ch->level - ADVENTURE_NEAR
               && wch->level <= ch->level + ADVENTURE_NEAR )
            near++;
    }
    if ( mates > 0 )
    {
        snprintf( buf, sizeof(buf),
            "* Your group: you are grouped with %d other%s.  GROUP shows them, GTELL\n\r"
            "  talks to them, and a kill shares its experience with the group there.\n\r",
            mates, mates == 1 ? "" : "s" );
        adventure_line( out, shown, buf );
    }
    else if ( near > 0 )
    {
        snprintf( buf, sizeof(buf),
            "* Company: %d other player%s near your level %s on (WHO lists them).  Ask\n\r"
            "  on the QUESTION channel, or FOLLOW someone and ask to be GROUPed.\n\r",
            near, near == 1 ? "" : "s", near == 1 ? "is" : "are" );
        adventure_line( out, shown, buf );
    }
}

void do_adventure( CHAR_DATA *ch, char *argument )
{
    DString out;
    int shown = 0;

    UNUSED_PARAM(argument);
    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players have adventures to plan.\n\r", ch );
        return;
    }
    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    dstring_printf( &out, "What you might do next, %s (level %d %s):\n\r", ch->name,
                    ch->level, class_table[ch->class].name );
    adventure_school( ch, &out, &shown );
    adventure_training( ch, &out, &shown );
    adventure_guild( ch, &out, &shown );
    adventure_quest( ch, &out, &shown );
    adventure_places( ch, &out, &shown );
    adventure_group( ch, &out, &shown );
    if ( shown == 0 )
        dstring_append_cstr( &out,
            "* Nothing in particular calls just now.  AQUEST, ACHIEVEMENTS and MAPS are\n\r"
            "  always there, and PRAY asks the Oracle anything about the game.\n\r" );
    dstring_append_cstr( &out,
        "(Only a list: it changes nothing.  HUNTING suggests creatures to fight.)\n\r" );
    /* At most 19 lines with every section shown, so it never pages under
       the default PAGELEN (22): a paged view eats the next command. */
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}
