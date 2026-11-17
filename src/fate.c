/*
 * fate.c -- FATE: the creator's hand on a player's next roll (owner,
 * 2026-11-17: "a creator [can] trigger on demand, but only a creator").
 *
 * FATE <player>                    what is fated for them
 * FATE <player> MISRECALL [<vnum>] their next recall prayer misfires, into
 *                                  that room or, without one, anywhere a
 *                                  misfire may throw them
 * FATE <player> EMERGENCY|RUSH     their next quest is that contract
 * FATE <player> MAP                the next creature they kill drops the
 *                                  map of its area (where a map can drop)
 * FATE <player> CLEAR              nothing fated
 *
 * Each is spent by the roll it replaces, in the code that makes that roll
 * (recall_travel, the questmaster's contract roll, raw_kill_internal), and
 * nothing else about that code changes: a prayer the gods refuse in a
 * no-recall room is refused and the fate waits; a misfire costs what a
 * misfire costs. It is memory only, so a quit forgets it, and it is never
 * told to the player. GRANTPSI (psionics) and DISASTER <kind> <player>
 * (a sure strike) are the creator's other dice. The command sits at CR in
 * the command table; nobody below the creator's trust can type it.
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

static const char *fate_contract_word( int contract )
{
    switch ( contract )
    {
    case FATE_CONTRACT_EMERGENCY: return "an emergency contract";
    case FATE_CONTRACT_RUSH:      return "a rush contract";
    default:                      return "nothing";
    }
}

/* Who is choosing: the creator's own character, through a switch too. */
static CHAR_DATA *fate_actor( CHAR_DATA *ch )
{
    return ch->desc != NULL && ch->desc->original != NULL ? ch->desc->original : ch;
}

static void fate_note( CHAR_DATA *ch, CHAR_DATA *victim, const char *what )
{
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof(buf), "Fate: %s fated %s %.200s.", fate_actor( ch )->name,
              victim->name, what );
    log_string( buf );
    wizinfo( buf, LEVEL_CREATOR );
}

static void fate_show( CHAR_DATA *ch, CHAR_DATA *victim )
{
    char buf[MAX_STRING_LENGTH];
    char room[64];
    bool any = false;

    snprintf( buf, sizeof(buf), "Fated for %s:\n\r", victim->name );
    send_to_char( buf, ch );
    if ( victim->pcdata->fate_misrecall )
    {
        if ( victim->pcdata->fate_recall_room > 0 )
            snprintf( room, sizeof(room), "room %d", victim->pcdata->fate_recall_room );
        else
            toc_strlcpy( room, "a random room", sizeof(room) );
        snprintf( buf, sizeof(buf), "  Their next recall prayer misfires, into %s.\n\r", room );
        send_to_char( buf, ch );
        any = true;
    }
    if ( victim->pcdata->fate_contract != FATE_CONTRACT_NONE )
    {
        snprintf( buf, sizeof(buf), "  Their next quest is %s.\n\r",
                  fate_contract_word( victim->pcdata->fate_contract ) );
        send_to_char( buf, ch );
        any = true;
    }
    if ( victim->pcdata->fate_map )
    {
        send_to_char( "  The next creature they kill drops its area's map.\n\r", ch );
        any = true;
    }
    if ( !any )
        send_to_char( "  Nothing: their dice roll as anybody's do.\n\r", ch );
}

void do_fate( CHAR_DATA *ch, char *argument )
{
    char name[MAX_INPUT_LENGTH];
    char what[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim;
    bool logging_in;

    argument = one_argument( argument, name );
    argument = one_argument( argument, what );
    if ( name[0] == '\0' )
    {
        send_to_char( "Syntax: fate <player> [misrecall [<room vnum>] | emergency | rush | map | clear]\n\r"
                      "A fate is spent by the roll it replaces, is never told to the player, and\n\r"
                      "is forgotten if they leave the game.  See also DISASTER <kind> <player>.\n\r", ch );
        return;
    }
    victim = player_in_game( name, &logging_in );
    if ( victim == NULL || logging_in || IS_NPC(victim) || victim->pcdata == NULL )
    {
        send_to_char( "Nobody playing by that name.\n\r", ch );
        return;
    }
    if ( victim != fate_actor( ch ) && rank_protects( ch, victim ) )
    {
        send_to_char( "They outrank you.\n\r", ch );
        return;
    }
    if ( what[0] == '\0' )
    {
        fate_show( ch, victim );
        return;
    }

    if ( !str_prefix( what, "misrecall" ) && strlen( what ) >= 3 )
    {
        int vnum = 0;

        if ( argument[0] != '\0' )
        {
            ROOM_INDEX_DATA *room;

            if ( !is_number( argument ) || !parse_int( argument, 1, MAX_VNUM, &vnum ) )
            {
                send_to_char( "Give the room as its vnum, or no room for a random one.\n\r", ch );
                return;
            }
            if ( ( room = get_room_index( vnum ) ) == NULL )
            {
                send_to_char( "No room has that vnum.\n\r", ch );
                return;
            }
            if ( IS_SET(room->room_flags, ROOM_DT) )
            {
                send_to_char( "That room is a death trap; a misfire is not a death.\n\r", ch );
                return;
            }
        }
        victim->pcdata->fate_misrecall = true;
        victim->pcdata->fate_recall_room = vnum;
        if ( vnum > 0 )
            snprintf( buf, sizeof(buf), "a misfired recall into room %d", vnum );
        else
            toc_strlcpy( buf, "a misfired recall into a random room", sizeof(buf) );
        fate_note( ch, victim, buf );
        snprintf( buf, sizeof(buf), "%s's next recall prayer will misfire%s.  (A prayer the gods\n\r"
                  "refuse -- a no-recall room, a curse -- is refused, and the fate waits.)\n\r",
                  victim->name, vnum > 0 ? " into that room" : "" );
        send_to_char( buf, ch );
        return;
    }
    if ( !str_prefix( what, "emergency" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_contract = FATE_CONTRACT_EMERGENCY;
        fate_note( ch, victim, "an emergency contract" );
        snprintf( buf, sizeof(buf), "%s's next quest will be an emergency contract.\n\r", victim->name );
        send_to_char( buf, ch );
        return;
    }
    if ( !str_prefix( what, "rush" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_contract = FATE_CONTRACT_RUSH;
        fate_note( ch, victim, "a rush contract" );
        snprintf( buf, sizeof(buf), "%s's next quest will be a rush contract.\n\r", victim->name );
        send_to_char( buf, ch );
        return;
    }
    if ( !str_cmp( what, "map" ) )
    {
        victim->pcdata->fate_map = true;
        fate_note( ch, victim, "an area map from their next kill" );
        snprintf( buf, sizeof(buf), "The next creature %s kills drops its area's map (not in Hyrule,\n\r"
                  "nor from a pet; the fate waits for a kill where a map can drop).\n\r", victim->name );
        send_to_char( buf, ch );
        return;
    }
    if ( !str_prefix( what, "clear" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_misrecall = false;
        victim->pcdata->fate_recall_room = 0;
        victim->pcdata->fate_contract = FATE_CONTRACT_NONE;
        victim->pcdata->fate_map = false;
        fate_note( ch, victim, "nothing (cleared)" );
        snprintf( buf, sizeof(buf), "Nothing is fated for %s now.\n\r", victim->name );
        send_to_char( buf, ch );
        return;
    }
    do_fate( ch, "" );
}

/* recall_travel, at a misfire it was fated to make: where it throws them.
   The fated room if it is still there, else anywhere a misfire may go. */
ROOM_INDEX_DATA *fate_take_misrecall( CHAR_DATA *ch )
{
    ROOM_INDEX_DATA *room = NULL;
    char buf[MAX_STRING_LENGTH];

    if ( ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL && ch->pcdata->fate_misrecall )
    {
        if ( ch->pcdata->fate_recall_room > 0 )
            room = get_room_index( ch->pcdata->fate_recall_room );
        ch->pcdata->fate_misrecall = false;
        ch->pcdata->fate_recall_room = 0;
        snprintf( buf, sizeof(buf), "Fate: %s's recall misfired as fated.", ch->name );
        log_string( buf );
    }
    return room != NULL ? room : get_random_room( ch );
}

/* The questmaster's contract roll: a fated contract, spent; or none. */
int fate_take_contract( CHAR_DATA *ch )
{
    int contract;
    char buf[MAX_STRING_LENGTH];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return FATE_CONTRACT_NONE;
    contract = ch->pcdata->fate_contract;
    if ( contract != FATE_CONTRACT_NONE )
    {
        ch->pcdata->fate_contract = FATE_CONTRACT_NONE;
        snprintf( buf, sizeof(buf), "Fate: %s's quest is %s, as fated.", ch->name,
                  fate_contract_word( contract ) );
        log_string( buf );
    }
    return contract;
}

/* raw_kill_internal, once the corpse is made: a fated map goes into it,
   and the fate is spent only when it did (an area with no map, Hyrule or
   a pet keeps it for the next kill). */
void fate_kill_map( CHAR_DATA *killer, CHAR_DATA *victim, OBJ_DATA *corpse )
{
    CHAR_DATA *who = killer;
    OBJ_DATA *obj;
    char buf[MAX_STRING_LENGTH];

    if ( who != NULL && IS_NPC(who) && who->master != NULL && IS_AFFECTED(who, AFF_CHARM) )
        who = who->master;
    if ( who == NULL || IS_NPC(who) || who->pcdata == NULL || !who->pcdata->fate_map
    ||   corpse == NULL || victim == NULL || !IS_NPC(victim) )
        return;
    for ( obj = corpse->contains; obj != NULL; obj = obj->next_content )
        if ( obj->pIndexData != NULL && obj->pIndexData->vnum == OBJ_VNUM_AREA_MAP )
            break;
    if ( obj == NULL && !map_corpse_drop_sure( corpse, victim ) )
        return;
    who->pcdata->fate_map = false;
    snprintf( buf, sizeof(buf), "Fate: %s's kill dropped its area's map, as fated.", who->name );
    log_string( buf );
}
