/***************************************************************************
 * Jail sentences (owner, 2026-11-12).                                      *
 *                                                                          *
 * A mortal must not escape an active sentence. Death, FARSLAY, suicide,    *
 * travel, items, remort, disconnecting, relogging and rebooting do not     *
 * release them; only staff (JAIL <name> RELEASE) or the expiry of a term   *
 * staff set does. An indefinite sentence lasts until staff release it.     *
 *                                                                          *
 * The rule follows the sentence, never the room. It used to be the        *
 * ROOM_JAIL flag that every travel check asked, so a prisoner outside a    *
 * correctly flagged cell -- an exit added, a flag taken off, a file saved  *
 * somewhere else -- walked free, and nothing ever ran the timer out.       *
 * Now char_to_room asks jail_hold_room() at every placement in the game:   *
 * a prisoner put anywhere but the cell (ROOM_VNUM_JAIL) is put in the      *
 * cell instead, which covers every death (the death room), every spell,    *
 * every portal, the login and anything written later. The commands that    *
 * would otherwise do something first -- a prayer's audience, a pocket      *
 * room, a projection, a remort, a deletion -- refuse early through         *
 * jail_refuses(), so the boundary never has to undo half of one.           *
 *                                                                          *
 * The sentence is PLR_JAILED with pcdata->jw_timer (the absolute release   *
 * time, JAIL_INDEFINITE for none) and JailInfo: when it began, who set     *
 * the term, and which restrictions it imposed (JAIL_ADDED_*), so a release *
 * lifts only those and never a nochannel or notitle staff gave separately. *
 * Jailing and releasing are saved at once and reported as they landed.     *
 ***************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "merc.h"
#include "interp.h"
#include "numparse.h"

/* The legacy jail's own title, " . (JAILED)" -- read back from a file
   without its leading space. A release puts the class title back over
   it, since nothing remembers what was there before. */
#define JAIL_LEGACY_TITLE   ". (JAILED)"
/* A release whose save failed is tried again this many seconds later. */
#define JAIL_RETRY_SECS     10

bool is_jailed( const CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && IS_SET(ch->act, PLR_JAILED);
}

static bool jail_timed( const CHAR_DATA *ch )
{
    return is_jailed( ch ) && ch->pcdata->jw_timer > 0;
}

/* Said by every command a sentence stops before it does anything. */
bool jail_refuses( CHAR_DATA *ch )
{
    if ( !is_jailed( ch ) )
        return false;
    send_to_char( "You are serving a jail sentence. Nothing takes you out of "
                  "the cell but your release.\n\r", ch );
    return true;
}

/* TRANSFER, ITRANS and DRAG: staff moving a prisoner anywhere but the
   cell are told to release them first. There is no override that keeps
   the sentence and moves the prisoner; JAIL RELEASE is the deliberate,
   logged act that lets them out. */
bool jail_refuses_staff_move( CHAR_DATA *ch, CHAR_DATA *victim,
                              ROOM_INDEX_DATA *to )
{
    char buf[MAX_STRING_LENGTH];

    if ( !is_jailed( victim ) || ( to != NULL && to->vnum == ROOM_VNUM_JAIL ) )
        return false;
    snprintf( buf, sizeof(buf), "%s is serving a jail sentence; JAIL %s RELEASE "
              "lets them out.\n\r", victim->name, victim->name );
    send_to_char( buf, ch );
    return true;
}

/*
 * char_to_room's boundary: where a character about to be placed in `to`
 * is really placed. A prisoner goes to the cell, whatever was asked. A
 * missing cell (an area edit) cannot hold anybody, and is logged.
 */
ROOM_INDEX_DATA *jail_hold_room( CHAR_DATA *ch, ROOM_INDEX_DATA *to )
{
    static time_t said_missing;
    ROOM_INDEX_DATA *cell;
    char buf[MAX_STRING_LENGTH];

    if ( to == NULL || !is_jailed( ch ) )
        return to;
    cell = get_room_index( ROOM_VNUM_JAIL );
    if ( cell == NULL )
    {
        if ( current_time - said_missing >= 60 )
        {
            said_missing = current_time;
            bug( "jail_hold_room: the jail cell (room %d) is missing; "
                 "a prisoner cannot be held.", ROOM_VNUM_JAIL );
        }
        return to;
    }
    if ( to == cell )
        return to;
    snprintf( buf, sizeof(buf), "JAIL: %s kept in the cell (was bound for room %d).",
              ch->name, to->vnum );
    log_string( buf );
    return cell;
}

/* "2026-11-12 18:04 UTC": the same for every reader, whatever the host. */
static void jail_when( long when, char *buf, size_t size )
{
    time_t t = (time_t) when;
    struct tm *tm = gmtime( &t );

    if ( tm == NULL || strftime( buf, size, "%Y-%m-%d %H:%M UTC", tm ) == 0 )
        snprintf( buf, size, "%ld", when );
}

/* "2d 3h 4m", rounded up to the minute; "less than a minute". */
static void jail_span( long secs, char *buf, size_t size )
{
    long days, hours, mins;

    if ( secs <= 0 )
    {
        snprintf( buf, size, "now" );
        return;
    }
    mins  = ( secs + 59 ) / 60;
    days  = mins / ( 24 * 60 );
    mins -= days * 24 * 60;
    hours = mins / 60;
    mins -= hours * 60;
    if ( days > 0 )
        snprintf( buf, size, "%ldd %ldh %ldm", days, hours, mins );
    else if ( hours > 0 )
        snprintf( buf, size, "%ldh %ldm", hours, mins );
    else
        snprintf( buf, size, "%ldm", mins );
}

/* One line for SCORE and the login: what the sentence is. */
void jail_term_text( const CHAR_DATA *ch, char *buf, size_t size )
{
    char when[64], span[64];

    if ( !is_jailed( ch ) )
    {
        buf[0] = '\0';
        return;
    }
    if ( !jail_timed( ch ) )
    {
        snprintf( buf, size, "You are jailed until staff release you." );
        return;
    }
    jail_when( ch->pcdata->jw_timer, when, sizeof(when) );
    jail_span( ch->pcdata->jw_timer - (long) current_time, span, sizeof(span) );
    snprintf( buf, size, "You are jailed until %s (%s).", when, span );
}

/*
 * After a player file is read (load_char_obj, found files only). A file
 * from before JailInfo carries no record of what the sentence imposed:
 * nothing is invented. Its restrictions are left in place at release
 * (JAIL_LEGACY), and a Jw_Timer of 0 -- which the old code wrote for
 * "no deadline" -- is an indefinite sentence, never one that expired at
 * the epoch. A deadline below -1 is read the same, conservatively.
 */
void jail_load_fixup( CHAR_DATA *ch )
{
    PC_DATA *pc;

    if ( ch == NULL || IS_NPC(ch) || ( pc = ch->pcdata ) == NULL )
        return;
    if ( !IS_SET(ch->act, PLR_JAILED) )
    {
        pc->jw_timer   = 0;
        pc->jail_since = 0;
        pc->jail_added = 0;
        pc->jail_by[0] = '\0';
        return;
    }
    if ( pc->jw_timer == 0 || pc->jw_timer < JAIL_INDEFINITE )
        pc->jw_timer = JAIL_INDEFINITE;
    if ( !pc->jail_info_read )
    {
        pc->jail_added = JAIL_LEGACY;
        pc->jail_since = 0;
        pc->jail_by[0] = '\0';
    }
    pc->jail_added &= JAIL_ADDED_KNOWN;
}

/* Staff changed a restriction the sentence may have imposed: from then on
   it is theirs, and the release leaves it alone. */
void jail_restriction_touched( CHAR_DATA *victim, long comm_bits )
{
    if ( !is_jailed( victim ) )
        return;
    if ( comm_bits & COMM_NOCHANNELS )
        victim->pcdata->jail_added &= ~JAIL_ADDED_NOCHANNELS;
    if ( comm_bits & COMM_NOTITLE )
        victim->pcdata->jail_added &= ~JAIL_ADDED_NOTITLE;
}

/* Everything a jail or a release changes, to put back when the save that
   records it does not land. */
typedef struct
{
    long act;
    long comm;
    long timer;
    long since;
    int  added;
    char by[16];
    char *title;            /* a copy, when the release replaced it */
    bool title_custom;
} JAIL_UNDO;

static void jail_undo_take( CHAR_DATA *ch, JAIL_UNDO *u )
{
    u->act   = ch->act;
    u->comm  = ch->comm;
    u->timer = ch->pcdata->jw_timer;
    u->since = ch->pcdata->jail_since;
    u->added = ch->pcdata->jail_added;
    toc_strlcpy( u->by, ch->pcdata->jail_by, sizeof(u->by) );
    u->title = NULL;
    u->title_custom = ch->pcdata->title_custom;
}

static void jail_undo_put( CHAR_DATA *ch, JAIL_UNDO *u )
{
    ch->act  = u->act;
    ch->comm = u->comm;
    ch->pcdata->jw_timer   = u->timer;
    ch->pcdata->jail_since = u->since;
    ch->pcdata->jail_added = u->added;
    toc_strlcpy( ch->pcdata->jail_by, u->by, sizeof(ch->pcdata->jail_by) );
    if ( u->title != NULL )
    {
        free_string( ch->pcdata->title );
        ch->pcdata->title = u->title;
        u->title = NULL;
        ch->pcdata->title_custom = u->title_custom;
    }
}

static void jail_undo_forget( JAIL_UNDO *u )
{
    if ( u->title != NULL )
    {
        free_string( u->title );
        u->title = NULL;
    }
}

/* The save that records a jail or a release. "jail-write-<Name>" fails
   it for the tests (TOC_FAULT_FILE), without the word "save" (AGENTS:
   TOC_FAULT matches by substring). */
static int jail_write( CHAR_DATA *ch )
{
    char point[64];

    snprintf( point, sizeof(point), "jail-write-%s", ch->name );
    if ( recovery_fault( point ) )
        return DURABLE_FAILED;
    save_char_obj( ch );
    return save_char_obj_status();
}

static const char *jail_status_word( int status )
{
    return status == DURABLE_OK ? "saved"
         : status == DURABLE_UNCERTAIN ? "written, not confirmed on the disk"
         : "NOT saved";
}

/* Out of a projection or a switch, off a mount, out of a fight and a
   walk, and into the cell: the sentence taking hold of somebody online. */
static void jail_take_in( CHAR_DATA *victim )
{
    DESCRIPTOR_DATA *d;
    ROOM_INDEX_DATA *cell = get_room_index( ROOM_VNUM_JAIL );

    for ( d = descriptor_list; d != NULL; d = d->next )
        if ( d->original == victim && d->character != NULL )
        {
            do_return( d->character, "" );
            break;
        }

    if ( victim->fighting != NULL || victim->position == POS_FIGHTING )
        stop_fighting( victim, true );
    walkto_clear( victim );
    if ( victim->pcdata->mounted )
    {
        if ( victim->pet != NULL )
            victim->pet->ridden = false;
        victim->pcdata->mounted = false;
    }
    /* Idle in the void: the void's way back is to a room left behind. */
    victim->was_in_room = NULL;

    if ( cell != NULL && victim->in_room != cell )
    {
        /* A pet standing with them -- a mount just dismounted -- goes
           too, as TRANSFER takes a ridden one: left behind, it would be
           dropped from the next save. */
        CHAR_DATA *pet = victim->pet;

        if ( pet != NULL && pet->in_room != victim->in_room )
            pet = NULL;
        if ( victim->in_room != NULL )
        {
            act( "$n is led away to jail.", victim, NULL, NULL, TO_ROOM );
            char_from_room( victim );
        }
        char_to_room( victim, cell );
        if ( pet != NULL )
        {
            if ( pet->fighting != NULL )
                stop_fighting( pet, true );
            char_from_room( pet );
            char_to_room( pet, cell );
        }
        if ( victim->desc != NULL )
            do_look( victim, "auto" );
    }
}

/*
 * Out of the cell to the Temple, with the pet that stands beside them
 * (review, 2026-11-12). save_char_obj writes a pet only from its owner's
 * room, so a pet left in the cell was dropped from the next save and lost
 * at the quit. The release's own save, made before this with both in the
 * cell, already holds the pet; a crash between it and this move logs the
 * owner in at the Temple (jail_login_place) with the pet placed beside
 * them, so the file and the world agree either way.
 *
 * A rider is moved mounted, the mount with them, as TRANSFER moves one:
 * RIDE lets a prisoner mount their own horse again in the cell, and the
 * rider alone in the Temple was left "mounted" on a horse still "ridden"
 * in the cell. A rider whose mount is not beside them is not riding
 * (release_mount).
 */
static void jail_release_move( CHAR_DATA *victim )
{
    ROOM_INDEX_DATA *temple = get_room_index( ROOM_VNUM_TEMPLE );
    ROOM_INDEX_DATA *cell;
    CHAR_DATA *pet;

    if ( temple == NULL || victim->in_room == NULL || victim->in_room == temple )
        return;
    if ( victim->in_room->vnum != ROOM_VNUM_JAIL
    &&   !IS_SET(victim->in_room->room_flags, ROOM_JAIL) )
        return;
    cell = victim->in_room;
    pet = victim->pet;
    if ( pet != NULL && pet->in_room != cell )
        pet = NULL;
    if ( victim->pcdata->mounted && pet == NULL )
        release_mount( victim );

    char_from_room( victim );
    char_to_room( victim, temple );
    if ( pet != NULL )
    {
        if ( pet->fighting != NULL )
            stop_fighting( pet, true );
        char_from_room( pet );
        char_to_room( pet, temple );
        if ( !pet->ridden )
            act( "$n follows $N out of the cell.", pet, NULL, victim, TO_NOTVICT );
    }
    if ( victim->desc != NULL )
        do_look( victim, "auto" );
}

/*
 * Release: the sentence and what it imposed, nothing else. Saved before
 * anything moves; a definite failure puts everything back (still jailed,
 * still in the cell) and says so. An unconfirmed save keeps the release:
 * the file may already be the new one.
 */
static int jail_release( CHAR_DATA *victim, bool offline )
{
    JAIL_UNDO undo;
    PC_DATA *pc = victim->pcdata;
    int status;

    jail_undo_take( victim, &undo );
    REMOVE_BIT( victim->act, PLR_JAILED );
    if ( ( pc->jail_added & JAIL_ADDED_NOCHANNELS ) )
        REMOVE_BIT( victim->comm, COMM_NOCHANNELS );
    if ( ( pc->jail_added & JAIL_ADDED_NOTITLE ) )
        REMOVE_BIT( victim->comm, COMM_NOTITLE );
    if ( ( pc->jail_added & JAIL_LEGACY ) && pc->title != NULL
    &&   !strcmp( pc->title + strspn( pc->title, " " ), JAIL_LEGACY_TITLE ) )
    {
        undo.title = str_dup( pc->title );
        set_class_title( victim, true );
    }
    /* A history flag, as the old release set it. */
    SET_BIT( victim->act, PLR_EXCON );
    pc->jw_timer   = 0;
    pc->jail_since = 0;
    pc->jail_added = 0;
    pc->jail_by[0] = '\0';
    pc->jail_retry_at = 0;

    status = jail_write( victim );
    if ( status == DURABLE_FAILED )
    {
        jail_undo_put( victim, &undo );
        return status;
    }
    jail_undo_forget( &undo );
    if ( !offline )
    {
        send_to_char( "You have been released from jail.\n\r", victim );
        jail_release_move( victim );
    }
    return status;
}

/* A term run out, online or at login. */
static void jail_expire( CHAR_DATA *ch, const char *when )
{
    char buf[MAX_STRING_LENGTH];
    int status;

    if ( get_room_index( ROOM_VNUM_TEMPLE ) == NULL )
    {
        if ( ch->pcdata->jail_retry_at <= current_time )
        {
            ch->pcdata->jail_retry_at = current_time + 60;
            bug( "jail_expire: the Temple (room %d) is missing; nobody can be "
                 "released to it.", ROOM_VNUM_TEMPLE );
        }
        return;
    }
    status = jail_release( ch, false );
    if ( status == DURABLE_FAILED )
    {
        ch->pcdata->jail_retry_at = current_time + JAIL_RETRY_SECS;
        snprintf( buf, sizeof(buf), "JAIL: %s's sentence ran out (%s), but the "
                  "release could not be saved; they stay jailed and it is tried "
                  "again in %d seconds.", ch->name, when, JAIL_RETRY_SECS );
        log_string( buf );
        wizinfo( buf, staff_notice_level( ch, LEVEL_IMMORTAL ) );
        return;
    }
    snprintf( buf, sizeof(buf), "JAIL: %s's sentence ran out (%s); released, %s.",
              ch->name, when, jail_status_word( status ) );
    log_string( buf );
    wizinfo( buf, staff_notice_level( ch, LEVEL_IMMORTAL ) );
    send_to_char( "Your sentence has been served.\n\r", ch );
}

/* Once a second (update_handler): a term that has run out ends, with
   nobody typing anything. Link-dead prisoners too. */
void jail_update( void )
{
    LIST_ITERATOR iter;
    CHAR_DATA *ch;

    FOR_EACH_CHARACTER( iter, ch )
    {
        if ( !jail_timed( ch ) || ch->pcdata->jw_timer > (long) current_time )
            continue;
        if ( ch->pcdata->jail_retry_at > current_time )
            continue;
        if ( ch->desc != NULL && ch->desc->connected != CON_PLAYING )
            continue;
        jail_expire( ch, "online" );
    }
}

/* Before the login places the character: somebody free whose file put
   them in the cell (a release that crashed before the move, a staff
   GOTO) starts at the Temple instead. A prisoner is placed in the cell
   by char_to_room itself. */
void jail_login_place( CHAR_DATA *ch )
{
    ROOM_INDEX_DATA *temple;

    if ( ch == NULL || IS_NPC(ch) || is_jailed( ch ) || ch->in_room == NULL
    ||   ch->in_room->vnum != ROOM_VNUM_JAIL || is_staff( ch ) )
        return;
    if ( ( temple = get_room_index( ROOM_VNUM_TEMPLE ) ) != NULL )
        ch->in_room = temple;
}

/* After corpse_registry_login, before the first LOOK: a term that ran
   out while they were away ends now, saved; otherwise they hear what
   the sentence is. */
void jail_login( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];

    if ( !is_jailed( ch ) )
        return;
    if ( jail_timed( ch ) && ch->pcdata->jw_timer <= (long) current_time )
    {
        jail_expire( ch, "at login" );
        if ( !is_jailed( ch ) )
            return;
    }
    jail_term_text( ch, buf, sizeof(buf) );
    toc_strlcat( buf, "\n\r", sizeof(buf) );
    send_to_char( buf, ch );
}

/*
 * A duration: digits with an optional unit -- m(inutes), h(ours) or
 * d(ays); a bare number is days, as JAIL always took. Nothing else: no
 * sign, no zero, nothing after the unit, and no more than thirty days.
 * Returns NULL with *secs set, or why not.
 */
static const char *jail_parse_duration( const char *word, long *secs )
{
    char digits[32];
    size_t len = strlen( word ), n = 0;
    long count, unit = 24L * 60L * 60L;
    char last;

    if ( len == 0 || len >= sizeof(digits) )
        return "That is not a duration.";
    last = (char) LOWER( word[len - 1] );
    if ( last == 'm' || last == 'h' || last == 'd' )
    {
        unit = last == 'm' ? 60L : last == 'h' ? 60L * 60L : 24L * 60L * 60L;
        len--;
    }
    if ( len == 0 )
        return "That is not a duration.";
    for ( n = 0; n < len; n++ )
    {
        if ( !isdigit( (unsigned char) word[n] ) )
            return "That is not a duration.";
        digits[n] = word[n];
    }
    digits[n] = '\0';
    if ( !parse_long( digits, 0, LONG_MAX, &count ) )
        return "That duration is far too long; the most is 30 days.";
    if ( count == 0 )
        return "A duration of zero is no sentence; use RELEASE to free them.";
    if ( count > JAIL_MAX_SECONDS / unit )
        return "The most a timed sentence may be is 30 days; use INDEFINITE "
               "for longer.";
    *secs = count * unit;
    return NULL;
}

static void jail_syntax( CHAR_DATA *ch )
{
    send_to_char( "Syntax: jail <player> status\n\r"
                  "        jail <player> <duration>   30m, 2h, 7d, or a number of days (most 30d)\n\r"
                  "        jail <player> indefinite   until staff release them\n\r"
                  "        jail <player> release      (or 0)\n\r"
                  "A duration starts now and replaces any term they were serving.\n\r", ch );
}

static void jail_show_status( CHAR_DATA *ch, CHAR_DATA *victim, const char *where )
{
    char buf[MAX_STRING_LENGTH], when[64], span[64];
    PC_DATA *pc = victim->pcdata;

    if ( !is_jailed( victim ) )
    {
        snprintf( buf, sizeof(buf), "%s is not jailed (%s).\n\r", victim->name, where );
        send_to_char( buf, ch );
        return;
    }
    if ( jail_timed( victim ) )
    {
        jail_when( pc->jw_timer, when, sizeof(when) );
        if ( pc->jw_timer <= (long) current_time )
            snprintf( span, sizeof(span), "%s",
                      !str_cmp( where, "offline" ) ? "served; released at their next login"
                                                    : "served; being released" );
        else
        {
            char left[48];

            jail_span( pc->jw_timer - (long) current_time, left, sizeof(left) );
            snprintf( span, sizeof(span), "%s left", left );
        }
        snprintf( buf, sizeof(buf), "%s is jailed (%s) until %s (%s).\n\r",
                  victim->name, where, when, span );
    }
    else
        snprintf( buf, sizeof(buf), "%s is jailed (%s) indefinitely, until staff "
                  "release them.\n\r", victim->name, where );
    send_to_char( buf, ch );

    if ( pc->jail_added & JAIL_LEGACY )
        send_to_char( "Sentenced before sentences were recorded: a release leaves "
                      "their channels and title as they are.\n\r", ch );
    else
    {
        jail_when( pc->jail_since, when, sizeof(when) );
        snprintf( buf, sizeof(buf), "Since %s; term set by %s. This sentence "
                  "imposed:%s%s%s.\n\r", when,
                  pc->jail_by[0] != '\0' ? pc->jail_by : "someone",
                  ( pc->jail_added & JAIL_ADDED_NOCHANNELS ) ? " nochannels" : "",
                  ( pc->jail_added & JAIL_ADDED_NOTITLE ) ? " notitle" : "",
                  ( pc->jail_added & ( JAIL_ADDED_NOCHANNELS | JAIL_ADDED_NOTITLE ) )
                      ? "" : " nothing" );
        send_to_char( buf, ch );
    }
    if ( victim->in_room != NULL && str_cmp( where, "offline" ) )
    {
        snprintf( buf, sizeof(buf), "They are in room %d%s.\n\r", victim->in_room->vnum,
                  victim->in_room->vnum == ROOM_VNUM_JAIL ? " (the cell)" : "" );
        send_to_char( buf, ch );
    }
}

/* Logged with everything that decided it, and told to staff who may see
   both people. */
static void jail_note( CHAR_DATA *ch, CHAR_DATA *victim, const char *text )
{
    log_string( text );
    wizinfo( text, staff_notice_level_pair( ch, victim, LEVEL_IMMORTAL ) );
}

void do_jail( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH], when[64], where[16];
    DESCRIPTOR_DATA offline_desc;
    CHAR_DATA *victim;
    bool offline = false, logging_in = false, release = false;
    bool status_only = false, indefinite = false;
    long secs = 0, deadline;
    const char *why;
    int status;

    argument = one_argument( argument, arg );
    argument = one_argument( argument, arg2 );

    if ( arg[0] == '\0' || arg2[0] == '\0' || argument[0] != '\0' )
    {
        jail_syntax( ch );
        return;
    }

    /* Everything about the words first: a bad one changes nobody. */
    if ( !str_cmp( arg2, "status" ) )
        status_only = true;
    else if ( !str_cmp( arg2, "release" ) || !strcmp( arg2, "0" ) )
        release = true;
    else if ( !str_cmp( arg2, "indefinite" ) )
        indefinite = true;
    else if ( ( why = jail_parse_duration( arg2, &secs ) ) != NULL )
    {
        send_to_char( why, ch );
        send_to_char( "\n\r", ch );
        jail_syntax( ch );
        return;
    }

    if ( !status_only && get_room_index( ROOM_VNUM_JAIL ) == NULL )
    {
        snprintf( buf, sizeof(buf), "The jail cell (room %d) is missing, so nobody "
                  "can be held or released; nothing was changed.\n\r", ROOM_VNUM_JAIL );
        send_to_char( buf, ch );
        return;
    }
    if ( release && get_room_index( ROOM_VNUM_TEMPLE ) == NULL )
    {
        snprintf( buf, sizeof(buf), "The Temple (room %d), where a release lands, is "
                  "missing; nothing was changed.\n\r", ROOM_VNUM_TEMPLE );
        send_to_char( buf, ch );
        return;
    }

    /* By name, seen or not; never a second copy of somebody in the game,
       and nobody halfway through logging in. */
    victim = player_in_game( arg, &logging_in );
    if ( victim != NULL && logging_in )
    {
        send_to_char( "They are logging in; try again in a moment.\n\r", ch );
        return;
    }
    if ( victim == NULL )
    {
        why = NULL;
        if ( ( victim = offline_player_load( &offline_desc, arg, &why ) ) == NULL )
        {
            send_to_char( why != NULL ? why : "No such character is saved.\n\r", ch );
            return;
        }
        offline = true;
    }

    if ( victim != ch && rank_protects( ch, victim ) )
    {
        send_to_char( "You failed.\n\r", ch );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    snprintf( where, sizeof(where), "%s", offline ? "offline"
              : victim->desc == NULL ? "link-dead" : "online" );

    if ( status_only )
    {
        jail_show_status( ch, victim, where );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    if ( release )
    {
        if ( !is_jailed( victim ) )
        {
            send_to_char( "That player isn't in jail!\n\r", ch );
            if ( offline )
                extract_char( victim, true );
            return;
        }
        status = jail_release( victim, offline );
        if ( status == DURABLE_FAILED )
        {
            snprintf( buf, sizeof(buf), "%s's player file could not be saved, so they "
                      "were NOT released: still jailed, nothing changed. Try again.\n\r",
                      victim->name );
            send_to_char( buf, ch );
        }
        else
        {
            snprintf( buf, sizeof(buf), "%s released from jail (%s; %s).\n\r",
                      victim->name, where, jail_status_word( status ) );
            send_to_char( buf, ch );
        }
        snprintf( buf, sizeof(buf), "JAIL: %s released %s (%s): %s.", ch->name,
                  victim->name, where, status == DURABLE_FAILED
                  ? "NOT saved, still jailed" : jail_status_word( status ) );
        jail_note( ch, victim, buf );
        if ( offline )
            extract_char( victim, true );
        return;
    }

    /* A sentence: a new one, or a new term replacing the old from now. */
    {
        JAIL_UNDO undo;
        PC_DATA *pc = victim->pcdata;
        bool was = is_jailed( victim );

        jail_undo_take( victim, &undo );
        deadline = indefinite ? JAIL_INDEFINITE : (long) current_time + secs;
        if ( !was )
        {
            pc->jail_added = 0;
            if ( !IS_SET(victim->comm, COMM_NOCHANNELS) )
            {
                SET_BIT( victim->comm, COMM_NOCHANNELS );
                pc->jail_added |= JAIL_ADDED_NOCHANNELS;
            }
            if ( !IS_SET(victim->comm, COMM_NOTITLE) )
            {
                SET_BIT( victim->comm, COMM_NOTITLE );
                pc->jail_added |= JAIL_ADDED_NOTITLE;
            }
            pc->jail_since = (long) current_time;
            SET_BIT( victim->act, PLR_JAILED );
        }
        pc->jw_timer = deadline;
        toc_strlcpy( pc->jail_by, ch->name, sizeof(pc->jail_by) );
        pc->jail_retry_at = 0;
        /* A deletion asked for before the sentence does not finish in it. */
        pc->confirm_delete = false;

        status = jail_write( victim );
        if ( indefinite )
            snprintf( when, sizeof(when), "indefinitely" );
        else
        {
            char at[48];

            jail_when( deadline, at, sizeof(at) );
            snprintf( when, sizeof(when), "until %s", at );
        }
        if ( status == DURABLE_FAILED )
        {
            jail_undo_put( victim, &undo );
            snprintf( buf, sizeof(buf), "%s's player file could not be saved, so the "
                      "sentence was NOT applied: nothing changed. Try again.\n\r",
                      victim->name );
            send_to_char( buf, ch );
            snprintf( buf, sizeof(buf), "JAIL: %s %s %s (%s) %s: NOT saved, nothing "
                      "applied.", ch->name, was ? "re-sentenced" : "jailed",
                      victim->name, where, when );
            jail_note( ch, victim, buf );
            if ( offline )
                extract_char( victim, true );
            return;
        }
        jail_undo_forget( &undo );

        snprintf( buf, sizeof(buf), "%s is %s %s (%s; %s).\n\r", victim->name,
                  was ? "now jailed, the old term replaced," : "now in jail",
                  when, where, jail_status_word( status ) );
        send_to_char( buf, ch );
        snprintf( buf, sizeof(buf), "JAIL: %s %s %s (%s) %s: %s.", ch->name,
                  was ? "re-sentenced" : "jailed", victim->name, where, when,
                  jail_status_word( status ) );
        jail_note( ch, victim, buf );

        if ( !was )
        {
            snprintf( buf, sizeof(buf), "%s has been jailed for breaking the rules!",
                      victim->name );
            send_info( buf );
        }
        if ( !offline )
        {
            if ( !was )
                send_to_char( "GO TO JAIL, do not pass GO, do not collect $200.\n\r",
                              victim );
            jail_take_in( victim );
            jail_term_text( victim, buf, sizeof(buf) );
            toc_strlcat( buf, "\n\r", sizeof(buf) );
            send_to_char( buf, victim );
        }
        else
            extract_char( victim, true );
    }
}
