/*
 * tutorial.c -- the new-player tutorial (owner, 2026-11-13).
 *
 * Short hints tied to what just happened -- the first step, a Mud School
 * sign, the first thing picked up or worn, the first fight, kill, death and
 * level, the first walk out of Mud School, the guild choice at level 3 and
 * PKILL at 15 -- never a timed stream and never a quest. A character made
 * from now starts with it on; a file written before it existed has no
 * Tutorial line and reads as off, and TUTORIAL ON opts in. TUTORIAL
 * ON|OFF|STATUS|NEXT.
 *
 * State: pcdata->tutorial_on and tutorial_done (a bit a step: TUT_*) are
 * saved as "Tutorial <on> <done>" under case 'T' of fread_char; the queue
 * of hints waiting to be shown is memory only, so a reconnect keeps it and
 * a quit drops it (the event will come again, or TUTORIAL NEXT finds it).
 * A remort keeps both: a step shown is never shown again.
 *
 * One hint at a time: an event queues its step (never one already shown or
 * queued), and tutorial_update, once a second, shows the oldest only when
 * the player is out of a fight, not paging, not on a WALKTO or a BUILD,
 * awake, and TUTORIAL_GAP seconds past the last one. Using a command a hint
 * teaches before the hint comes marks it done without a word (CONSIDER,
 * WIMPY, WALKTO, COMPARE, WEAR).
 *
 * The guild steps are for a mage, cleric, thief or warrior in no guild:
 * monks and necromancers have their own, and a member has chosen. At level
 * 6 a guildless character is put in their class's guild free
 * (advance_level_body), and the tutorial says so.
 *
 * Beyond the brief, from the players' own logs (owner, 2026-11-13: "use
 * all your best judgement with what you know from existing players"):
 * a closed door walked into ("The locked is closed." 32 times), the first
 * "You are hungry." now that hunger hurts, the altar where the stash is
 * (GET X STASH was tried for weeks), the oak the questmaster sits above
 * (five players stopped one climb short), and a second unknown word in a
 * sitting (HELP, COMMANDS and the Oracle).
 *
 * PKILL is presented as optional and lasting; the tutorial never turns it
 * on, never asks for a password and never says it is needed.
 *
 * Counts, never names: a "tutorial" row in log/play.tsv every
 * TUTORIAL_CENSUS_SECS (an hour; TOC_TUTORIAL_CENSUS_SECS for tests) when
 * anything happened -- each step's showings, NEXT, ON, OFF and completions.
 */
#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"
#include "numparse.h"

#define TUTORIAL_GAP            6       /* seconds between two hints */
#define TUTORIAL_CENSUS_SECS    3600

/* A bit each in pcdata->tutorial_done, saved: append, never renumber. */
enum
{
    TUT_MOVE, TUT_SIGN, TUT_CONSIDER, TUT_ITEM, TUT_WEAR, TUT_FIGHT,
    TUT_KILL, TUT_DEATH, TUT_LEVEL, TUT_WALKTO, TUT_GUILD_CHOICE,
    TUT_GUILD_REMIND, TUT_GUILD_AUTO, TUT_PKILL,
    /* From what the players' logs showed them stumbling on (2026-10-23 to
       11-13): closed doors, hunger, the stash, the questmaster one climb
       up, and words the game did not know. */
    TUT_DOOR, TUT_HUNGER, TUT_STASH, TUT_QUEST, TUT_HELP,
    /* The Oracle, tried once (owner, 2026-11-13: "make sure to have them
       test the oracle"); asking her a question earns Seeker of Answers. */
    TUT_ORACLE,
    TUT_MAX
};

/* The steps, in the order TUTORIAL NEXT and STATUS take them. `core`
   steps are the ones every character meets; seeing them all, and PKILL
   once level 15 comes, is a completed tutorial. */
static const struct
{
    const char *key;
    const char *title;
    bool        core;
    bool        nextable;       /* may TUTORIAL NEXT show it unasked-for */
} tut_steps[TUT_MAX] =
{
    { "move",         "moving about",                 true,  true  },
    { "sign",         "Mud School's signs",           true,  true  },
    { "consider",     "sizing up a fight",            true,  true  },
    { "item",         "carrying and wearing things",  true,  true  },
    { "wear",         "your equipment",               true,  true  },
    { "fight",        "fighting and fleeing",         true,  true  },
    { "kill",         "after a kill",                 true,  true  },
    { "death",        "dying",                        true,  true  },
    { "level",        "a new level",                  true,  true  },
    { "walkto",       "finding your way",             true,  true  },
    { "guild",        "choosing a guild",             false, true  },
    { "guild-remind", "the guild deadline",           false, false },
    { "guild-auto",   "your class's guild",           false, false },
    { "pkill",        "player killing (optional)",    false, true  },
    { "door",         "doors",                        false, true  },
    { "hunger",       "food and drink",               false, true  },
    { "stash",        "your stash",                   false, true  },
    { "quest",        "quests",                       false, true  },
    { "help",         "finding help",                 false, true  },
    { "oracle",       "asking the Oracle",            true,  true  },
};

static long tut_shown[TUT_MAX];
static long tut_next_used, tut_turned_on, tut_turned_off, tut_completed;

static bool tut_done( CHAR_DATA *ch, int step )
{
    return ( ch->pcdata->tutorial_done & ( 1 << step ) ) != 0;
}

/* A mage, cleric, thief or warrior who has joined no guild, and may still
   (JOIN works from level 3; at 6 the class's guild is given). */
static bool guild_choice_open( CHAR_DATA *ch )
{
    return ch->class >= CLASS_MAGE && ch->class <= CLASS_WARRIOR
        && ch->pcdata->guild == GUILD_NONE
        && ch->level >= 3 && ch->level < 6;
}

/* Whether a step has anything to say to this character now. */
static bool tut_applies( CHAR_DATA *ch, int step )
{
    switch ( step )
    {
    case TUT_GUILD_CHOICE:
    case TUT_GUILD_REMIND:
        return guild_choice_open( ch );
    case TUT_GUILD_AUTO:
        return ch->class >= CLASS_MAGE && ch->class <= CLASS_WARRIOR;
    case TUT_PKILL:
        return ch->level >= 15 && ch->pcdata->pk_state != 1;
    case TUT_QUEST:
        return ch->level >= 3;
    case TUT_HUNGER:
        return hunger_thirst_applies( ch );
    default:
        return true;
    }
}

static bool tut_counted( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL && !is_staff( ch );
}

static bool tut_complete( CHAR_DATA *ch )
{
    int step;

    for ( step = 0; step < TUT_MAX; step++ )
        if ( tut_steps[step].core && !tut_done( ch, step ) )
            return false;
    /* And, from level 15, the word on player killing (unless they took it). */
    return ch->level < 15 || ch->pcdata->pk_state == 1 || tut_done( ch, TUT_PKILL );
}

/* The tutorial done: once, an achievement (Schooled) and a word. */
static void tut_finished( CHAR_DATA *ch, bool was_complete )
{
    if ( was_complete || !tut_complete( ch ) )
        return;
    tut_completed++;
    achievement_record_event( ch, ACHIEVEMENT_EVENT_TUTORIAL_DONE, true );
    send_to_char( "{0E[Tutorial]{00 That is every hint so far.  TUTORIAL OFF puts the "
                  "tutorial away;\n\rHELP BEGINNERS and HELP TUTORIAL are always there.\n\r", ch );
}

static void tut_unqueue( CHAR_DATA *ch, int step )
{
    int i, j;

    for ( i = 0; i < ch->pcdata->tutorial_queued; i++ )
        if ( ch->pcdata->tutorial_queue[i] == step )
        {
            for ( j = i; j + 1 < ch->pcdata->tutorial_queued; j++ )
                ch->pcdata->tutorial_queue[j] = ch->pcdata->tutorial_queue[j + 1];
            ch->pcdata->tutorial_queued--;
            return;
        }
}

/* Done without a word: the player used what the hint would teach. */
static void tut_known( CHAR_DATA *ch, int step )
{
    bool was_complete;

    if ( !tut_counted( ch ) )
        return;
    was_complete = tut_complete( ch );
    ch->pcdata->tutorial_done |= ( 1 << step );
    tut_unqueue( ch, step );
    if ( ch->pcdata->tutorial_on )
        tut_finished( ch, was_complete );
}

/* An event: queue its step, once, while the tutorial is on. */
static void tut_event( CHAR_DATA *ch, int step )
{
    int i;

    if ( !tut_counted( ch ) || !ch->pcdata->tutorial_on
    ||   tut_done( ch, step ) || !tut_applies( ch, step ) )
        return;
    for ( i = 0; i < ch->pcdata->tutorial_queued; i++ )
        if ( ch->pcdata->tutorial_queue[i] == step )
            return;
    if ( ch->pcdata->tutorial_queued >= TUTORIAL_QUEUE )
        return;                 /* full: the event comes again, or NEXT */
    ch->pcdata->tutorial_queue[ch->pcdata->tutorial_queued++] = (sh_int) step;
}

/* ------------------------------------------------------------ the text */

static void tut_text( CHAR_DATA *ch, int step, char *buf, size_t size )
{
    const char *cls = ch->class >= 0 && ch->class < MAX_CLASS
                    ? class_table[ch->class].name : "warrior";
    char upper[32];
    size_t i;

    for ( i = 0; cls[i] != '\0' && i + 1 < sizeof(upper); i++ )
        upper[i] = UPPER( cls[i] );
    upper[i] = '\0';

    switch ( step )
    {
    case TUT_MOVE:
        snprintf( buf, size,
            "Move with N, S, E, W, U and D (and NE, NW, SE, SW).  EXITS lists\n\r"
            "the ways out of a room and LOOK shows it again.  From the Entrance to\n\r"
            "Mud School, go north: the school teaches as you walk through it.\n\r" );
        break;
    case TUT_SIGN:
        snprintf( buf, size,
            "There is a sign here.  Mud School's signs are its lessons: LOOK SIGN\n\r"
            "reads one.  Do what it says, then move on.\n\r" );
        break;
    case TUT_CONSIDER:
        snprintf( buf, size,
            "Before you fight something, CONSIDER <name> tells you how it is\n\r"
            "likely to go.  KILL <name> starts a fight and FLEE runs from one.\n\r" );
        break;
    case TUT_ITEM:
        snprintf( buf, size,
            "You picked something up.  INVENTORY lists what you carry.  WEAR\n\r"
            "<item> puts it on (WIELD a weapon, HOLD a light), and WEAR ALL\n\r"
            "wears everything that fits.\n\r" );
        break;
    case TUT_WEAR:
        snprintf( buf, size,
            "EQUIPMENT shows what you have on.  COMPARE <item> weighs something you\n\r"
            "carry against what you wear, and COMPARE UPGRADES suggests better gear\n\r"
            "for your level and where it is found.\n\r" );
        break;
    case TUT_FIGHT:
        snprintf( buf, size,
            "That was a fight: it runs by itself once begun.  WIMPY sets the hit\n\r"
            "points at which you flee by yourself (WIMPY alone sets a fifth of your\n\r"
            "maximum), and FLEE runs at once.  REST or SLEEP heals you between fights.\n\r" );
        break;
    case TUT_KILL:
        snprintf( buf, size,
            "A kill leaves a corpse.  GET ALL CORPSE takes what it held, and\n\r"
            "SACRIFICE CORPSE clears it away.  AUTOLOOT can loot for you: HELP AUTO.\n\r" );
        break;
    case TUT_DEATH:
        snprintf( buf, size,
            "You died.  Your things are in your corpse where you fell: go back and\n\r"
            "GET ALL CORPSE.  Nobody else may loot it unless you allow it (HELP\n\r"
            "NOLOOT).  HELP DEATH says what a death costs.\n\r" );
        break;
    case TUT_LEVEL:
        snprintf( buf, size,
            "A new level!  Each brings practice sessions and a training session.\n\r"
            "At a trainer, PRACTICE <skill> improves what you know and TRAIN <stat>\n\r"
            "raises an attribute or your hit points.  GAINLIST shows the skills and\n\r"
            "spells you can still GAIN, what they cost and who teaches them.\n\r" );
        break;
    case TUT_WALKTO:
        snprintf( buf, size,
            "WALKTO <place> walks you to an area, a trainer or a guild hall, and\n\r"
            "WALKTO alone lists the places.  RECALL prays you home to the Temple:\n\r"
            "now and then it goes unanswered, or sets you down somewhere else\n\r"
            "(HELP RECALL).\n\r" );
        break;
    case TUT_GUILD_CHOICE:
        snprintf( buf, size,
            "You may now join a guild.  It adds a second class's training to your\n\r"
            "own, and you choose once, before you reach level 6.  To decide:\n\r"
            "  HELP GUILDS                        what each guild gives\n\r"
            "  GAINLIST PREVIEW <class> <guild>   a build, e.g. GAINLIST PREVIEW %s THIEF\n\r"
            "  WALKTO MELANCHOLY                  the guild clerk\n\r"
            "  JOIN <guild>                       mage, cleric, thief or warrior (1 gold)\n\r"
            "Choose nothing and at level 6 you join the %s guild, free.\n\r",
            upper, cls );
        break;
    case TUT_GUILD_REMIND:
        snprintf( buf, size,
            "You have not joined a guild, and level 6 ends the choice.  To choose:\n\r"
            "WALKTO MELANCHOLY, then JOIN <mage|cleric|thief|warrior>.  Otherwise you\n\r"
            "join the %s guild, free, at level 6.  HELP GUILDS compares them.\n\r",
            cls );
        break;
    case TUT_GUILD_AUTO:
        snprintf( buf, size,
            "You reached level 6 without choosing a guild, so you are now in the\n\r"
            "%s guild, free.  GAINLIST shows what it lets you learn, and HELP\n\r"
            "GUILDS names its hall.\n\r", cls );
        break;
    case TUT_DOOR:
        snprintf( buf, size,
            "A closed door is in the way.  OPEN <direction> opens it (OPEN NORTH).\n\r"
            "A locked one needs its key: UNLOCK <direction>, then OPEN.  EXITS shows\n\r"
            "which ways have doors.\n\r" );
        break;
    case TUT_HUNGER:
        snprintf( buf, size,
            "EAT <food> and DRINK <drink> put hunger and thirst right; shops sell\n\r"
            "both, and a fountain or a waterskin will do for water.  Hungry or\n\r"
            "thirsty you heal more slowly, and left long enough it starts to hurt\n\r"
            "(HELP HUNGER).\n\r" );
        break;
    case TUT_STASH:
        snprintf( buf, size,
            "This is the Temple altar, where your stash is kept.  STASH PUT <item>\n\r"
            "stores something from anywhere; STASH GET <item> takes it out, here\n\r"
            "only.  STASH alone lists what is in it (HELP STASH).\n\r" );
        break;
    case TUT_QUEST:
        snprintf( buf, size,
            "The questmaster sends you after creatures and items for coin and quest\n\r"
            "points.  From the Oak Tree Square (WALKTO SQUARE) climb UP through the\n\r"
            "oak to the very top -- the Questmaster's Globe is one climb above its\n\r"
            "crown -- and AQUEST REQUEST there.  HELP AQUEST says more.\n\r" );
        break;
    case TUT_HELP:
        snprintf( buf, size,
            "When a word does not work, HELP <word> explains a command and COMMANDS\n\r"
            "lists them all.  Stuck?  PRAY takes you to the Oracle, who answers\n\r"
            "questions about the game (HELP ORACLE).\n\r" );
        break;
    case TUT_ORACLE:
        snprintf( buf, size,
            "Try the Oracle: she answers questions about the game.  PRAY takes you\n\r"
            "to her sanctum; ASK <question> there, or simply SAY it -- where to\n\r"
            "hunt at your level, what a spell does, how to reach a place.  SAY DONE\n\r"
            "brings you back where you prayed.  She will not hide you from a fight:\n\r"
            "not during one, nor just after you flee.\n\r" );
        break;
    case TUT_PKILL:
        snprintf( buf, size,
            "Level 15 opens player killing.  It is entirely optional -- nothing in\n\r"
            "the game needs it -- and it lasts: a player killer may be attacked by\n\r"
            "other player killers, and cannot undo the choice.  Read HELP PKILL\n\r"
            "before you decide anything.\n\r" );
        break;
    default:
        buf[0] = '\0';
        break;
    }
}

static void tut_show( CHAR_DATA *ch, int step, bool asked )
{
    char text[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH + 128];
    bool was_complete = tut_complete( ch );

    tut_text( ch, step, text, sizeof(text) );
    snprintf( buf, sizeof(buf), "\n\r{0E[Tutorial: %s]{00\n\r%s", tut_steps[step].title, text );
    send_to_char( buf, ch );
    ch->pcdata->tutorial_done |= ( 1 << step );
    tut_unqueue( ch, step );
    ch->pcdata->tutorial_last = current_time;
    tut_shown[step]++;
    if ( asked )
        tut_next_used++;
    tut_finished( ch, was_complete );
}

/* ------------------------------------------------------------ events */

/* A character just made (the nanny, after their outfit): on, nothing seen. */
void tutorial_new_character( CHAR_DATA *ch )
{
    const char *off = getenv( "TOC_NO_TUTORIAL" );

    if ( !tut_counted( ch ) )
        return;
    /* Test worlds (tests/live_mud.py) make their characters with it off,
       so its hints never land in another test's replies. */
    ch->pcdata->tutorial_on     = off == NULL || off[0] == '\0' || !strcmp( off, "0" );
    ch->pcdata->tutorial_done   = 0;
    ch->pcdata->tutorial_queued = 0;
    ch->pcdata->tutorial_last   = 0;
}

/* Entering the game: the first entry says the tutorial is on and how to
   turn it off; a later one, briefly, that it still is; and what an
   opted-in character's level already calls for is queued. */
void tutorial_login( CHAR_DATA *ch, bool is_new_character )
{
    if ( !tut_counted( ch ) || !ch->pcdata->tutorial_on )
        return;
    if ( is_new_character )
        send_to_char(
            "{0E[Tutorial]{00 The tutorial is ON: short hints appear as you play, one at\n\r"
            "a time.  TUTORIAL NEXT shows one now, TUTORIAL STATUS your progress, and\n\r"
            "{0FTUTORIAL OFF{00 turns it off (TUTORIAL ON brings it back where you left it).\n\r", ch );
    else
        send_to_char( "{0E[Tutorial]{00 Hints are on: TUTORIAL NEXT for one, TUTORIAL OFF to stop.\n\r", ch );
    ch->pcdata->tutorial_last = current_time;
    tut_event( ch, TUT_GUILD_CHOICE );
    if ( ch->level >= 5 && tut_done( ch, TUT_GUILD_CHOICE ) )
        tut_event( ch, TUT_GUILD_REMIND );
    tut_event( ch, TUT_PKILL );
}

static bool is_school( ROOM_INDEX_DATA *room )
{
    return room != NULL && room->area != NULL && room->area->file_name != NULL
        && !str_cmp( room->area->file_name, "school.are" );
}

/* do_look's room view: arriving or LOOK. */
void tutorial_room_seen( CHAR_DATA *ch, bool arrived )
{
    EXTRA_DESCR_DATA *ed;
    CHAR_DATA *rch;

    if ( !tut_counted( ch ) || !ch->pcdata->tutorial_on || ch->in_room == NULL )
        return;
    if ( arrived )
        tut_event( ch, TUT_MOVE );
    if ( is_school( ch->in_room ) )
    {
        for ( ed = ch->in_room->extra_descr; ed != NULL; ed = ed->next )
            if ( ed->keyword != NULL && is_name( "sign", ed->keyword ) )
            {
                tut_event( ch, TUT_SIGN );
                break;
            }
    }
    else if ( arrived && ch->in_room->vnum != ROOM_VNUM_LIMBO )
        tut_event( ch, TUT_WALKTO );
    if ( ch->in_room->vnum == ROOM_VNUM_ALTAR )
        tut_event( ch, TUT_STASH );
    /* The square and the oak above it: five players stopped one climb
       short of the questmaster in October's logs. */
    if ( ch->in_room->vnum == 2401 || ch->in_room->vnum == 2410
    ||   ch->in_room->vnum == 2411 || ch->in_room->vnum == ROOM_VNUM_OAK_TOP )
        tut_event( ch, TUT_QUEST );

    if ( IS_SET( ch->in_room->room_flags, ROOM_SAFE ) )
        return;
    for ( rch = ch->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( IS_NPC(rch) && rch->master != ch && rch->pIndexData != NULL
        &&   rch->pIndexData->pShop == NULL
        &&   !IS_SET( rch->act, ACT_TRAIN | ACT_PRACTICE | ACT_IS_HEALER | ACT_GAIN )
        &&   can_see( ch, rch ) )
        {
            tut_event( ch, TUT_CONSIDER );
            break;
        }
}

/* obj_to_char: something reaching a playing character's hands. */
void tutorial_got( CHAR_DATA *ch, OBJ_DATA *obj )
{
    if ( obj == NULL || ch == NULL || ch->desc == NULL
    ||   ch->desc->connected != CON_PLAYING || obj->item_type == ITEM_MONEY )
        return;
    if ( obj->wear_flags & ~ITEM_TAKE )
        tut_event( ch, TUT_ITEM );
}

/* After a command of the player's own (interpret): what they already use
   needs no hint, and wearing something opens the equipment one. */
void tutorial_command( CHAR_DATA *ch, const char *cmd )
{
    if ( !tut_counted( ch ) || cmd == NULL )
        return;
    if ( !str_cmp( cmd, "consider" ) )
        tut_known( ch, TUT_CONSIDER );
    else if ( !str_cmp( cmd, "wimpy" ) )
        tut_known( ch, TUT_FIGHT );
    else if ( !str_cmp( cmd, "walkto" ) )
        tut_known( ch, TUT_WALKTO );
    else if ( !str_cmp( cmd, "stash" ) )
        tut_known( ch, TUT_STASH );
    else if ( !str_cmp( cmd, "aquest" ) )
        tut_known( ch, TUT_QUEST );
    else if ( !str_cmp( cmd, "open" ) || !str_cmp( cmd, "unlock" ) )
        tut_known( ch, TUT_DOOR );
    else if ( !str_cmp( cmd, "eat" ) || !str_cmp( cmd, "drink" ) )
        tut_known( ch, TUT_HUNGER );
    else if ( !str_cmp( cmd, "help" ) || !str_cmp( cmd, "pray" ) )
        tut_known( ch, TUT_HELP );
    else if ( !str_cmp( cmd, "compare" ) )
        tut_known( ch, TUT_WEAR );
    else if ( !str_cmp( cmd, "wear" ) || !str_cmp( cmd, "wield" ) || !str_cmp( cmd, "hold" ) )
    {
        tut_known( ch, TUT_ITEM );
        tut_event( ch, TUT_WEAR );
    }
}

/* set_fighting: a player in a fight with a mobile; shown once it is over. */
void tutorial_fight( CHAR_DATA *ch, CHAR_DATA *victim )
{
    if ( ch == NULL || victim == NULL || IS_NPC(ch) == IS_NPC(victim) )
        return;
    tut_event( IS_NPC(ch) ? victim : ch, TUT_FIGHT );
}

/* A closed door walked into (move_char). */
void tutorial_door( CHAR_DATA *ch )
{
    tut_event( ch, TUT_DOOR );
}

/* "You are hungry." or "You are thirsty." (update.c). */
void tutorial_hunger( CHAR_DATA *ch )
{
    tut_event( ch, TUT_HUNGER );
}

/* A word the game did not know (interpret): the second in a sitting. */
void tutorial_refused( CHAR_DATA *ch )
{
    if ( !tut_counted( ch ) )
        return;
    if ( ++ch->pcdata->tutorial_misses >= 2 )
        tut_event( ch, TUT_HELP );
}

/* A question put to the Oracle (oracle.c): the hint has done its job. */
void tutorial_oracle( CHAR_DATA *ch )
{
    tut_known( ch, TUT_ORACLE );
}

void tutorial_kill( CHAR_DATA *ch )
{
    tut_event( ch, TUT_KILL );
}

void tutorial_death( CHAR_DATA *ch )
{
    tut_event( ch, TUT_DEATH );
}

/* advance_level_body, after the level's own lines; `guild_given` when this
   level put them in their class's guild. */
void tutorial_level( CHAR_DATA *ch, bool guild_given )
{
    if ( !tut_counted( ch ) )
        return;
    tut_event( ch, TUT_LEVEL );
    tut_event( ch, TUT_ORACLE );        /* after the level's own word */
    if ( ch->level == 3 || ch->level == 4 )
        tut_event( ch, TUT_GUILD_CHOICE );
    if ( ch->level == 5 )
    {
        if ( !tut_done( ch, TUT_GUILD_CHOICE ) )
            tut_event( ch, TUT_GUILD_CHOICE );
        else
            tut_event( ch, TUT_GUILD_REMIND );
    }
    if ( guild_given )
    {
        tut_unqueue( ch, TUT_GUILD_CHOICE );
        tut_unqueue( ch, TUT_GUILD_REMIND );
        tut_event( ch, TUT_GUILD_AUTO );
    }
    if ( ch->level >= 15 )
        tut_event( ch, TUT_PKILL );
}

/* A queued step that no longer applies (they joined a guild, took PKILL)
   is dropped rather than shown late. */
static int tut_first_queued( CHAR_DATA *ch )
{
    while ( ch->pcdata->tutorial_queued > 0 )
    {
        int step = ch->pcdata->tutorial_queue[0];

        if ( step >= 0 && step < TUT_MAX && !tut_done( ch, step ) && tut_applies( ch, step ) )
            return step;
        tut_unqueue( ch, step );
    }
    return -1;
}

static long census_secs( void )
{
    static long secs = -1;

    if ( secs < 0 )
    {
        const char *env = getenv( "TOC_TUTORIAL_CENSUS_SECS" );
        long v = 0;

        secs = TUTORIAL_CENSUS_SECS;
        if ( env != NULL && parse_long( env, 1, 86400, &v ) )
            secs = v;
    }
    return secs;
}

static void tut_census( void )
{
    static time_t last;
    char fields[900], part[160];
    long any = tut_next_used + tut_turned_on + tut_turned_off + tut_completed;
    int step;

    if ( last == 0 )
    {
        last = current_time;
        return;
    }
    if ( current_time - last < census_secs() )
        return;
    last = current_time;
    for ( step = 0; step < TUT_MAX; step++ )
        any += tut_shown[step];
    if ( any == 0 )
        return;
    toc_strlcpy( fields, "shown", sizeof(fields) );
    for ( step = 0; step < TUT_MAX; step++ )
    {
        snprintf( part, sizeof(part), " %s=%ld", tut_steps[step].key, tut_shown[step] );
        toc_strlcat( fields, part, sizeof(fields) );
        tut_shown[step] = 0;
    }
    snprintf( part, sizeof(part), "\tnext=%ld on=%ld off=%ld completed=%ld",
              tut_next_used, tut_turned_on, tut_turned_off, tut_completed );
    toc_strlcat( fields, part, sizeof(fields) );
    tut_next_used = tut_turned_on = tut_turned_off = tut_completed = 0;
    playlog_row( "tutorial", NULL, fields );
}

/* Once a second (update_handler): a waiting hint for whoever can take it. */
void tutorial_update( void )
{
    DESCRIPTOR_DATA *d;

    tut_census();
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *ch = d->character;
        int step;

        if ( d->connected != CON_PLAYING || d->original != NULL || ch == NULL
        ||   !tut_counted( ch ) || !ch->pcdata->tutorial_on
        ||   ch->pcdata->tutorial_queued <= 0 )
            continue;
        if ( ch->fighting != NULL || ch->position < POS_RESTING
        ||   d->showstr_point != NULL || ch->pcdata->walkto_vnum != 0
        ||   build_wizard_active( ch )
        ||   current_time - ch->pcdata->tutorial_last < TUTORIAL_GAP )
            continue;
        if ( ( step = tut_first_queued( ch ) ) >= 0 )
            tut_show( ch, step, false );
    }
}

/* ------------------------------------------------------------ TUTORIAL */

static void tut_status( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    int step, seen = 0, shown = 0;

    send_to_char( ch->pcdata->tutorial_on
                  ? "The tutorial is {0FON{00.\n\r" : "The tutorial is {0FOFF{00.\n\r", ch );
    for ( step = 0; step < TUT_MAX; step++ )
    {
        if ( !tut_steps[step].nextable && !tut_done( ch, step ) )
            continue;
        shown++;
        if ( tut_done( ch, step ) )
            seen++;
        snprintf( buf, sizeof(buf), "  [%c] %s\n\r", tut_done( ch, step ) ? 'x' : ' ',
                  tut_steps[step].title );
        send_to_char( buf, ch );
    }
    snprintf( buf, sizeof(buf), "%d of %d seen%s.\n\r", seen, shown,
              ch->pcdata->tutorial_queued > 0 ? "; a hint is waiting" : "" );
    send_to_char( buf, ch );
    send_to_char( "TUTORIAL ON, TUTORIAL OFF, TUTORIAL NEXT.  HELP TUTORIAL says more.\n\r", ch );
}

void do_tutorial( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    int step;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players have a tutorial.\n\r", ch );
        return;
    }
    one_argument( argument, arg );

    if ( arg[0] == '\0' || !str_prefix( arg, "status" ) )
    {
        tut_status( ch );
        return;
    }
    if ( !str_cmp( arg, "on" ) )
    {
        if ( ch->pcdata->tutorial_on )
        {
            send_to_char( "The tutorial is already on.  TUTORIAL NEXT shows a hint now.\n\r", ch );
            return;
        }
        ch->pcdata->tutorial_on = true;
        ch->pcdata->tutorial_last = current_time;
        if ( tut_counted( ch ) )
            tut_turned_on++;
        send_to_char( "The tutorial is ON.  Hints come as you play, picking up where you\n\r"
                      "left off; TUTORIAL NEXT shows one now and TUTORIAL OFF stops them.\n\r", ch );
        save_char_obj( ch );
        return;
    }
    if ( !str_cmp( arg, "off" ) )
    {
        if ( !ch->pcdata->tutorial_on )
        {
            send_to_char( "The tutorial is already off.  TUTORIAL ON brings it back.\n\r", ch );
            return;
        }
        ch->pcdata->tutorial_on = false;
        ch->pcdata->tutorial_queued = 0;
        if ( tut_counted( ch ) )
            tut_turned_off++;
        send_to_char( "The tutorial is OFF.  What you have seen is kept: TUTORIAL ON picks up\n\r"
                      "where you left off, and HELP BEGINNERS is always there.\n\r", ch );
        save_char_obj( ch );
        return;
    }
    if ( !str_prefix( arg, "next" ) )
    {
        if ( ( step = tut_first_queued( ch ) ) < 0 )
            for ( step = 0; step < TUT_MAX; step++ )
                if ( tut_steps[step].nextable && !tut_done( ch, step ) && tut_applies( ch, step ) )
                    break;
        if ( step < 0 || step >= TUT_MAX )
        {
            send_to_char( "You have seen every hint there is for you now.  More come at level 3\n\r"
                          "and level 15; HELP BEGINNERS is a short guide.\n\r", ch );
            return;
        }
        if ( !tut_counted( ch ) )
        {
            char text[MAX_STRING_LENGTH];

            tut_text( ch, step, text, sizeof(text) );
            send_to_char( text, ch );
            return;
        }
        tut_show( ch, step, true );
        return;
    }
    send_to_char( "Syntax: tutorial [on|off|status|next]\n\r", ch );
}
