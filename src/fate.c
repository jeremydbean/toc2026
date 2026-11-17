/*
 * fate.c -- FATE: the creator's hand on a player's next roll (owner,
 * 2026-11-17: "a creator [can] trigger on demand, but only a creator").
 *
 * FATE <player>                    what is fated for them
 * FATE <player> MISRECALL [<vnum>] their next recall prayer misfires, into
 *                                  that room (a death trap too) or, without
 *                                  one, anywhere a misfire may throw them
 * FATE <player> EMERGENCY|RUSH     their next quest is that contract
 * FATE <player> MAP                the next creature they kill drops the
 *                                  map of its area (where a map can drop)
 * FATE <player> DISASTER <kind>    a sure strike the first time they stand
 *                                  where that kind can reach them
 * FATE <player> CLEAR              nothing fated
 *
 * Each is spent by the roll it replaces, in the code that makes that roll
 * (recall_travel, the questmaster's contract roll, raw_kill_internal,
 * disaster_update), and nothing else about that code changes: a prayer
 * the gods refuse in a no-recall room is refused and the fate waits; a
 * misfire costs what a misfire costs. It is saved (`Fate`, case 'F') until
 * spent, so it waits across logins, and a player who is offline is loaded,
 * fated and saved -- it waits for them (owner: "allow these luck commands
 * to be used on a player when they are offline and queue it"). It is
 * never told to the player. GRANTPSI (psionics) and DISASTER <kind>
 * <player> are the creator's other dice. The command sits at CR in the
 * command table; nobody below the creator's trust can type it.
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
    if ( victim->pcdata->fate_disaster > 0 )
    {
        snprintf( buf, sizeof(buf), "  A %s strikes them, sure, where it can reach them.\n\r",
                  disaster_kind_word( victim->pcdata->fate_disaster ) );
        send_to_char( buf, ch );
        any = true;
    }
    if ( !any )
        send_to_char( "  Nothing: their dice roll as anybody's do.\n\r", ch );
}

/* The player to fate: online, or loaded from their file into `offline`'s
   stand-in descriptor (then *loaded is true and the caller saves and
   extracts the copy). NULL, with the creator told why, when neither. */
static CHAR_DATA *fate_find( CHAR_DATA *ch, const char *name,
                             DESCRIPTOR_DATA *offline, bool *loaded )
{
    CHAR_DATA *victim;
    bool logging_in;

    *loaded = false;
    victim = player_in_game( name, &logging_in );
    if ( victim != NULL && logging_in )
    {
        send_to_char( "They are logging in; try again in a moment.\n\r", ch );
        return NULL;
    }
    if ( victim == NULL )
    {
        if ( ( victim = offline_player_load( offline, name, NULL ) ) == NULL )
        {
            send_to_char( "No player by that name is online or saved.\n\r", ch );
            return NULL;
        }
        *loaded = true;
    }
    if ( IS_NPC(victim) || victim->pcdata == NULL )
    {
        send_to_char( "Only players have a fate.\n\r", ch );
        if ( *loaded )
            extract_char( victim, true );
        return NULL;
    }
    if ( victim != fate_actor( ch ) && rank_protects( ch, victim ) )
    {
        send_to_char( "They outrank you.\n\r", ch );
        if ( *loaded )
            extract_char( victim, true );
        return NULL;
    }
    return victim;
}

/* A fate set is written at once, online or not, and the creator told how
   it landed. An offline copy whose save failed keeps nothing: the file is
   as it was. The copy is extracted here. */
static void fate_save( CHAR_DATA *ch, CHAR_DATA *victim, bool loaded )
{
    int status;

    save_char_obj( victim );
    status = save_char_obj_status();
    if ( status == DURABLE_FAILED )
        send_to_char( loaded ? "Their file could not be saved, so nothing was kept: try again.\n\r"
                             : "Their file could not be saved just now; it is in effect and\n\r"
                               "their next save writes it.\n\r", ch );
    else if ( status == DURABLE_UNCERTAIN )
        send_to_char( "Written to their file, but the disk has not confirmed it.\n\r", ch );
    else if ( loaded )
        send_to_char( "They are offline: it is saved and waits for them.\n\r", ch );
    if ( loaded )
        extract_char( victim, true );
}

void do_fate( CHAR_DATA *ch, char *argument )
{
    char name[MAX_INPUT_LENGTH];
    char what[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA offline;
    CHAR_DATA *victim;
    bool loaded;

    argument = one_argument( argument, name );
    argument = one_argument( argument, what );
    if ( name[0] == '\0' )
    {
        send_to_char( "Syntax: fate <player> [misrecall [<room vnum>] | emergency | rush | map |\n\r"
                      "                       disaster <kind> | clear]\n\r"
                      "A fate is spent by the roll it replaces and never told to the player.  It is\n\r"
                      "saved until spent, and an offline player's waits for them.\n\r", ch );
        return;
    }
    if ( ( victim = fate_find( ch, name, &offline, &loaded ) ) == NULL )
        return;
    if ( what[0] == '\0' )
    {
        fate_show( ch, victim );
        if ( loaded )
            extract_char( victim, true );
        return;
    }

    if ( !str_prefix( what, "misrecall" ) && strlen( what ) >= 3 )
    {
        int vnum = 0;

        if ( argument[0] != '\0' )
        {
            ROOM_INDEX_DATA *room = NULL;

            if ( !is_number( argument ) || !parse_int( argument, 1, MAX_VNUM, &vnum )
            ||   ( room = get_room_index( vnum ) ) == NULL )
            {
                send_to_char( room == NULL && vnum > 0 ? "No room has that vnum.\n\r"
                              : "Give the room as its vnum, or no room for a random one.\n\r", ch );
                if ( loaded )
                    extract_char( victim, true );
                return;
            }
            /* A death trap is allowed (owner, 2026-11-17): the creator is
               told what it means, and the tick's death trap does the rest. */
            if ( IS_SET(room->room_flags, ROOM_DT) )
                send_to_char( "That room is a death trap: the misfire will kill them.\n\r", ch );
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
    }
    else if ( !str_prefix( what, "emergency" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_contract = FATE_CONTRACT_EMERGENCY;
        fate_note( ch, victim, "an emergency contract" );
        snprintf( buf, sizeof(buf), "%s's next quest will be an emergency contract.\n\r", victim->name );
        send_to_char( buf, ch );
    }
    else if ( !str_prefix( what, "rush" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_contract = FATE_CONTRACT_RUSH;
        fate_note( ch, victim, "a rush contract" );
        snprintf( buf, sizeof(buf), "%s's next quest will be a rush contract.\n\r", victim->name );
        send_to_char( buf, ch );
    }
    else if ( !str_cmp( what, "map" ) )
    {
        victim->pcdata->fate_map = true;
        fate_note( ch, victim, "an area map from their next kill" );
        snprintf( buf, sizeof(buf), "The next creature %s kills drops its area's map (not in Hyrule,\n\r"
                  "nor from a pet; the fate waits for a kill where a map can drop).\n\r", victim->name );
        send_to_char( buf, ch );
    }
    else if ( !str_prefix( what, "disaster" ) && strlen( what ) >= 3 )
    {
        int type = disaster_kind_lookup( argument );

        if ( type <= 0 )
        {
            send_to_char( "Which disaster?  flood, lightning, earthquake, tornado, sandstorm, fire,\n\r"
                          "tidal or dragon.\n\r", ch );
            if ( loaded )
                extract_char( victim, true );
            return;
        }
        victim->pcdata->fate_disaster = type;
        snprintf( buf, sizeof(buf), "a %s, sure, where it can reach them", disaster_kind_word( type ) );
        fate_note( ch, victim, buf );
        snprintf( buf, sizeof(buf), "A %s strikes %s, sure, the first time they stand where it can\n\r"
                  "reach them (never in a shelter, never lethal).\n\r",
                  disaster_kind_word( type ), victim->name );
        send_to_char( buf, ch );
    }
    else if ( !str_prefix( what, "clear" ) && strlen( what ) >= 2 )
    {
        victim->pcdata->fate_misrecall = false;
        victim->pcdata->fate_recall_room = 0;
        victim->pcdata->fate_contract = FATE_CONTRACT_NONE;
        victim->pcdata->fate_map = false;
        victim->pcdata->fate_disaster = 0;
        fate_note( ch, victim, "nothing (cleared)" );
        snprintf( buf, sizeof(buf), "Nothing is fated for %s now.\n\r", victim->name );
        send_to_char( buf, ch );
    }
    else
    {
        if ( loaded )
            extract_char( victim, true );
        do_fate( ch, "" );
        return;
    }
    fate_save( ch, victim, loaded );
}

/* DISASTER <kind> <player> for somebody not playing: the strike waits for
   them as FATE <player> DISASTER <kind> would. True when it was queued
   (the creator is told); false when there is nobody saved by that name. */
bool fate_queue_disaster( CHAR_DATA *ch, const char *name, int type )
{
    DESCRIPTOR_DATA offline;
    CHAR_DATA *victim;
    char buf[MAX_STRING_LENGTH];
    bool loaded;

    if ( ( victim = fate_find( ch, name, &offline, &loaded ) ) == NULL )
        return false;
    if ( !loaded )
    {
        /* Online after all (they logged in meanwhile): strike now. */
        disaster_strike_sure( ch, victim, type );
        return true;
    }
    victim->pcdata->fate_disaster = type;
    snprintf( buf, sizeof(buf), "a %s, sure, where it can reach them", disaster_kind_word( type ) );
    fate_note( ch, victim, buf );
    snprintf( buf, sizeof(buf), "A %s waits for %s: it strikes, sure, the first time they stand\n\r"
              "where it can reach them.\n\r", disaster_kind_word( type ), victim->name );
    send_to_char( buf, ch );
    fate_save( ch, victim, loaded );
    return true;
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
