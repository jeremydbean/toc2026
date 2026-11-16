/*
 * lfg.c -- LFG and HELPER: finding a group, and players glad to help
 * (2026-11-15).
 *
 * Both are opt-in. LFG marks a player looking for a group for an hour, or
 * until they are in one; HELPER, saved, marks a player of level 10 or more
 * glad to answer questions and group with newer players. WHO shows both,
 * LFG LIST lists them for a player near the asker's level (anybody the
 * asker could see in WHO, never anyone either of them IGNOREs), and turning
 * LFG on tells the helpers online once -- at most every LFG_NOTICE_GAP --
 * which is the only thing either ever sends unasked. Nothing about it is
 * written to a log but the command itself.
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

#define LFG_SECONDS        ( 60 * 60 )    /* an LFG mark lasts this long */
#define LFG_NOTICE_GAP     ( 10 * 60 )    /* helpers told at most this often */
#define LFG_NEAR           10             /* LFG LIST: levels either side */
#define HELPER_MIN_LEVEL   10

/* In a group with another player in the game. */
static bool lfg_grouped( CHAR_DATA *ch )
{
    DESCRIPTOR_DATA *d;

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected == CON_PLAYING && wch != NULL && wch != ch && !IS_NPC(wch)
        &&   is_same_group( ch, wch ) )
            return true;
    }
    return false;
}

bool player_lfg( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && ch->pcdata->lfg_until > current_time && !lfg_grouped( ch );
}

/* A group with another player was just formed (GROUP, from do_group):
   whoever was looking has found one. The mark is cleared, not suppressed,
   so leaving the group within the hour does not bring it back. */
static void lfg_found( CHAR_DATA *ch )
{
    if ( ch->pcdata->lfg_until > current_time )
        send_to_char( "You have a group: you are no longer marked as looking for one.\n\r", ch );
    ch->pcdata->lfg_until = 0;
}

void lfg_group_formed( CHAR_DATA *leader, CHAR_DATA *member )
{
    if ( leader == NULL || member == NULL || leader == member
    ||   IS_NPC(leader) || IS_NPC(member)
    ||   leader->pcdata == NULL || member->pcdata == NULL )
        return;
    lfg_found( leader );
    lfg_found( member );
}

bool player_helper( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL && ch->pcdata->helper
        && ch->level >= HELPER_MIN_LEVEL;
}

/* Whether one may be told of or shown the other: seen as WHO would, and
   neither ignoring the other. */
static bool lfg_may_meet( CHAR_DATA *ch, CHAR_DATA *wch )
{
    return wch != ch && !IS_NPC(wch) && online_can_list( ch, wch )
        && !is_ignoring( ch, wch ) && !is_ignoring( wch, ch );
}

/* The helpers online, told once that somebody wants a group. */
static void lfg_tell_helpers( CHAR_DATA *ch )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];
    int told = 0;

    if ( ch->pcdata->lfg_noticed + LFG_NOTICE_GAP > current_time )
        return;
    snprintf( buf, sizeof(buf), "[LFG] %s, level %d %s, is looking for a group.  (LFG LIST)\n\r",
              ch->name, ch->level, class_table[ch->class].name );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || wch == NULL || !player_helper( wch )
        ||   !lfg_may_meet( wch, ch ) )
            continue;
        send_to_char( buf, wch );
        told++;
    }
    if ( told > 0 )
        ch->pcdata->lfg_noticed = current_time;
}

static void lfg_list( CHAR_DATA *ch )
{
    DESCRIPTOR_DATA *d;
    DString out;
    int looking = 0, helpers = 0;

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    dstring_printf( &out, "Looking for a group, within %d levels of you:\n\r", LFG_NEAR );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || wch == NULL || !lfg_may_meet( ch, wch )
        ||   !player_lfg( wch ) || wch->level < ch->level - LFG_NEAR
        ||   wch->level > ch->level + LFG_NEAR )
            continue;
        dstring_printf( &out, "  %-12s level %2d %s\n\r", wch->name, wch->level,
                        class_table[wch->class].name );
        looking++;
    }
    if ( looking == 0 )
        dstring_append_cstr( &out, "  nobody just now\n\r" );
    dstring_append_cstr( &out, "Helpers, glad to answer questions and group with newer players:\n\r" );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || wch == NULL || !lfg_may_meet( ch, wch )
        ||   !player_helper( wch ) )
            continue;
        dstring_printf( &out, "  %-12s level %2d %s\n\r", wch->name, wch->level,
                        class_table[wch->class].name );
        helpers++;
    }
    if ( helpers == 0 )
        dstring_append_cstr( &out, "  none on just now: try the QUESTION channel\n\r" );
    dstring_append_cstr( &out, "TELL someone to say hello; FOLLOW them and ask to be GROUPed.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}

void do_lfg( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players look for groups.\n\r", ch );
        return;
    }
    one_argument( argument, arg );
    if ( !str_cmp( arg, "list" ) )
    {
        lfg_list( ch );
        return;
    }
    /* The bare word toggles what WHO shows: a grouped player's stored mark
       shows nothing, so it is not "on" to turn off. */
    if ( !str_cmp( arg, "off" ) || ( arg[0] == '\0' && player_lfg( ch ) ) )
    {
        ch->pcdata->lfg_until = 0;
        send_to_char( "You are no longer marked as looking for a group.\n\r", ch );
        return;
    }
    if ( arg[0] != '\0' && str_cmp( arg, "on" ) )
    {
        send_to_char( "Syntax: lfg [on|off|list]\n\r", ch );
        return;
    }
    if ( lfg_grouped( ch ) )
    {
        ch->pcdata->lfg_until = 0;
        send_to_char( "You are in a group already.  LFG LIST still shows who else is looking.\n\r", ch );
        return;
    }
    ch->pcdata->lfg_until = current_time + LFG_SECONDS;
    send_to_char( "You are marked as looking for a group for an hour, or until you join one.\n\r"
                  "WHO shows it; LFG LIST shows who else is looking and the helpers on.\n\r", ch );
    lfg_tell_helpers( ch );
}

void do_helper( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players can be helpers.\n\r", ch );
        return;
    }
    one_argument( argument, arg );
    if ( arg[0] == '\0' )
        toc_strlcpy( arg, ch->pcdata->helper ? "off" : "on", sizeof(arg) );
    if ( !str_cmp( arg, "off" ) )
    {
        ch->pcdata->helper = false;
        send_to_char( "You are no longer marked as a helper.\n\r", ch );
        save_char_obj( ch );
        return;
    }
    if ( str_cmp( arg, "on" ) )
    {
        send_to_char( "Syntax: helper [on|off]\n\r", ch );
        return;
    }
    if ( ch->level < HELPER_MIN_LEVEL )
    {
        send_to_char( "Helpers are level 10 or more.  Until then, LFG finds you company.\n\r", ch );
        return;
    }
    ch->pcdata->helper = true;
    save_char_obj( ch );
    send_to_char( "You are marked as a helper: WHO shows it, LFG LIST lists you, and you will\n\r"
                  "hear when somebody marks themselves LFG (once in a while, never from anyone\n\r"
                  "either of you ignores).  HELPER OFF stops it.\n\r", ch );
}

/* ADVENTURE's company line: who near the level is looking, and helpers on. */
void lfg_counts( CHAR_DATA *ch, int near, int *looking, int *helpers )
{
    DESCRIPTOR_DATA *d;

    *looking = *helpers = 0;
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *wch = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || wch == NULL || !lfg_may_meet( ch, wch ) )
            continue;
        if ( player_lfg( wch ) && wch->level >= ch->level - near && wch->level <= ch->level + near )
            (*looking)++;
        if ( player_helper( wch ) )
            (*helpers)++;
    }
}
