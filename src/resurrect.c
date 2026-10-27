/***************************************************************************
 * Resurrection (owner, 2026-10-25).
 *
 * A member of the cleric guild casts RESURRECTION on a player's corpse.
 * Nothing happens to the dead until they say so: the corpse's owner is
 * offered the return, and ACCEPT brings them to the corpse at one hit
 * point with everything it held; DECLINE, or two minutes, ends the offer.
 *
 * The offer lives on the owner, in memory only -- a quit or a reboot ends
 * it. It points at the corpse, and a corpse can rot, be purged or be
 * carried off while the offer stands, so ACCEPT looks for that pointer in
 * the object list again before trusting anything about it.
 *
 * Coming back is a way out of where the owner stands, so it asks what
 * recall asks of the room left (no-recall, jail) and what the travel
 * spells ask of the room arrived in (travel_spell_refuses, privacy).
 ***************************************************************************/

#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "merc.h"
#include "interp.h"

#define RESURRECT_OFFER_SECONDS  120
/* The most top-level objects one ACCEPT carries (a corpse holds a
   character's kit, not a warehouse). */
#define MAX_RESURRECT_OBJECTS    512

/* Whose body this is: the owner, or for a corpse left lootable (a WANTED
   player's) the name it was made with -- as the corpse registry reads it. */
static void resurrect_corpse_owner( OBJ_DATA *corpse, char *out, size_t size )
{
    char word[MAX_INPUT_LENGTH];

    out[0] = '\0';
    if ( corpse == NULL || corpse->item_type != ITEM_CORPSE_PC )
        return;
    if ( corpse->owner != NULL && corpse->owner[0] != '\0' )
    {
        toc_strlcpy( out, corpse->owner, size );
        return;
    }
    if ( corpse->name != NULL )
    {
        one_argument( corpse->name, word );
        toc_strlcpy( out, word, size );
    }
}

/* The player in the game by that name, switched or not. */
static CHAR_DATA *resurrect_find_owner( const char *name )
{
    DESCRIPTOR_DATA *d;

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *who = d->original != NULL ? d->original : d->character;

        if ( d->connected != CON_PLAYING || who == NULL || IS_NPC(who) )
            continue;
        if ( !str_cmp( who->name, name ) )
            return who;
    }
    return NULL;
}

/* The corpse an offer named, if it is still a corpse of this player's
   lying in a room; NULL otherwise. */
static OBJ_DATA *resurrect_corpse_still( CHAR_DATA *ch )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    char owner[MAX_INPUT_LENGTH];

    if ( ch->pcdata->resurrect_corpse == NULL )
        return NULL;
    FOR_EACH_OBJECT( iter, obj )
    {
        if ( obj != ch->pcdata->resurrect_corpse )
            continue;
        resurrect_corpse_owner( obj, owner, sizeof(owner) );
        if ( obj->in_room == NULL || str_cmp( owner, ch->name ) )
            return NULL;
        return obj;
    }
    return NULL;
}

static void resurrect_clear( CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    ch->pcdata->resurrect_by[0] = '\0';
    ch->pcdata->resurrect_corpse = NULL;
    ch->pcdata->resurrect_until = 0;
}

static bool resurrect_offer_open( CHAR_DATA *ch )
{
    if ( IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->resurrect_by[0] == '\0' )
        return false;
    if ( current_time > ch->pcdata->resurrect_until )
    {
        resurrect_clear( ch );
        return false;
    }
    return true;
}

/* Why a dead player may not come back to that room now; NULL if they may. */
static const char *resurrect_refusal( CHAR_DATA *ch, ROOM_INDEX_DATA *to )
{
    if ( ch->in_room == NULL || to == NULL )
        return "Your soul cannot find the way.";
    if ( ch->fighting != NULL || ch->position == POS_FIGHTING )
        return "You cannot answer the call in the middle of a fight.";
    if ( ch->position < POS_RESTING )
        return "You are in no state to answer anything.";
    if ( ch->in_room == to )
        return "You are already standing beside your body.";
    if ( IS_SET( to->room_flags, ROOM_DT ) )
        return "Your body lies where nothing living can stand.";
    if ( IS_SET( ch->in_room->room_flags, ROOM_JAIL )
    ||   IS_SET( to->room_flags, ROOM_JAIL ) )
        return "No god's call reaches past those bars.";
    if ( IS_SET( ch->in_room->room_flags, ROOM_NO_RECALL )
    &&   !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
        return "Something here holds you; the call cannot pull you out.";
    if ( travel_spell_refuses( ch, to ) )
        return "Your body lies somewhere you may not go.";
    if ( room_is_private( to ) && !can_enter_private_room( ch, to ) )
        return "Your body lies in a room too crowded to come back to.";
    return NULL;
}

void spell_resurrection( int sn, int level, CHAR_DATA *ch, void *vo )
{
    OBJ_DATA *corpse;
    CHAR_DATA *owner;
    char name[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];

    UNUSED_PARAM( sn );
    UNUSED_PARAM( level );
    UNUSED_PARAM( vo );

    if ( IS_NPC(ch) || ch->pcdata == NULL || ch->in_room == NULL )
        return;
    if ( ch->pcdata->guild != GUILD_CLERIC && !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
    {
        send_to_char( "Only those sworn to the cleric guild may call a soul back.\n\r", ch );
        return;
    }
    if ( target_name == NULL || target_name[0] == '\0' )
    {
        send_to_char( "Whose body do you mean to call a soul back to?\n\r", ch );
        return;
    }
    corpse = get_obj_list( ch, target_name, ch->in_room->contents );
    if ( corpse == NULL )
    {
        send_to_char( "You see no such body here.\n\r", ch );
        return;
    }
    if ( corpse->item_type != ITEM_CORPSE_PC )
    {
        act( "$p never held a soul that could answer.", ch, corpse, NULL, TO_CHAR );
        return;
    }
    resurrect_corpse_owner( corpse, name, sizeof(name) );
    if ( name[0] == '\0' )
    {
        act( "No name binds $p to a soul.", ch, corpse, NULL, TO_CHAR );
        return;
    }
    if ( !str_cmp( name, ch->name ) )
    {
        send_to_char( "You are already among the living; take what is yours.\n\r", ch );
        return;
    }
    if ( ( owner = resurrect_find_owner( name ) ) == NULL )
    {
        act( "You call, but the soul that owned $p is not in this world to hear it.",
            ch, corpse, NULL, TO_CHAR );
        return;
    }

    toc_strlcpy( owner->pcdata->resurrect_by, ch->name,
                 sizeof(owner->pcdata->resurrect_by) );
    owner->pcdata->resurrect_corpse = corpse;
    owner->pcdata->resurrect_until = current_time + RESURRECT_OFFER_SECONDS;

    act( "You kneel over $p and call its soul home.", ch, corpse, NULL, TO_CHAR );
    act( "$n kneels over $p, calling its soul home.", ch, corpse, NULL, TO_ROOM );
    snprintf( buf, sizeof(buf),
        "%s calls your soul back to your body in %s.\n\r"
        "Type ACCEPT to rise there at one hit point with everything it holds,"
        " or DECLINE. The call fades in two minutes.\n\r",
        PERS( ch, owner ), corpse->in_room->name );
    send_to_char( buf, owner );
    act( "The call goes out to $T.", ch, NULL, capitalize( name ), TO_CHAR );
    snprintf( buf, sizeof(buf), "RESURRECT: %s offered %s a return to their corpse.",
        ch->name, owner->name );
    log_string( buf );
}

/*
 * ACCEPT gives the corpse's contents to its owner as a transfer that is
 * either done -- on the disk -- or not done at all (review, 2026-10-26: it
 * ended the corpse first and saved last, ignoring the result, so a failed
 * save and a crash lost both copies):
 *
 *   1. the corpse's record written now and HELD as it is (corpses.c), and
 *      the mark restore:resurrect:<id> proved to fit the owner's Fixes;
 *   2. a pending receipt, resurrect:<corpse id>, in the ledger, opened on
 *      the corpse too;
 *   3. the mark, then everything moved to the owner -- coin as coin;
 *   4. the owner's save. One on the disk settles the transfer through the
 *      save itself: the held record into history as "resurrected", then
 *      the committed receipt (corpse_registry_owner_saved).
 *
 * A save that FAILED left the old file in place: everything goes back in
 * the corpse, the mark comes off and the offer stands. A save renamed
 * into place but NOT CONFIRMED on the disk is neither: the file holds the
 * gift, so it is not taken back (review, 2026-10-27: putting it back and
 * abandoning the receipt left it in the file and the corpse, and a crash
 * laid both). It stays pending and is settled by the owner's next save on
 * the disk, at their login, or at boot -- each from the file's mark.
 */
void do_accept( CHAR_DATA *ch, char *argument )
{
    OBJ_DATA *corpse, *obj, *obj_next;
    OBJ_DATA *moved[MAX_RESURRECT_OBJECTS];
    ROOM_INDEX_DATA *to;
    CHAR_DATA *caster;
    const char *why;
    char caster_name[sizeof(ch->pcdata->resurrect_by)];
    char note[MAX_STRING_LENGTH];
    char id[32], op[64], mark[96];
    int given = 0, kept = 0, i, status;

    UNUSED_PARAM( argument );
    if ( IS_NPC(ch) || ch->pcdata == NULL || !resurrect_offer_open( ch ) )
    {
        send_to_char( "Nobody is calling you back.\n\r", ch );
        return;
    }
    if ( ( corpse = resurrect_corpse_still( ch ) ) == NULL )
    {
        send_to_char( "The call fades: your body is no longer there to return to.\n\r", ch );
        resurrect_clear( ch );
        return;
    }
    to = corpse->in_room;
    if ( ( why = resurrect_refusal( ch, to ) ) != NULL )
    {
        /* The offer stands, so they can come back once they may. */
        send_to_char( why, ch );
        send_to_char( "\n\r", ch );
        return;
    }
    for ( obj = corpse->contains; obj != NULL; obj = obj->next_content )
        given++;
    if ( given > MAX_RESURRECT_OBJECTS )
    {
        send_to_char( "Your body holds more than one call can carry back; let somebody "
                      "lighten it first.\n\r", ch );
        return;
    }
    given = 0;

    /* 1: the corpse as it is, on the disk and held; the mark must fit. */
    if ( !corpse_registry_hold( corpse, id, sizeof(id) ) )
    {
        send_to_char( "The call wavers: your body's record could not be kept safe -- or "
                      "your death is still being written down -- so nothing was moved.  "
                      "Try again in a moment.\n\r", ch );
        return;
    }
    snprintf( op, sizeof(op), "resurrect:%s", id );
    snprintf( mark, sizeof(mark), "restore:%s", op );
    if ( !player_fix_can_record( ch, mark ) )
    {
        corpse_registry_unhold( corpse );
        send_to_char( "The call wavers: the record that would prove your return is full, "
                      "so nothing was moved.  Staff can see why in the log.\n\r", ch );
        return;
    }

    /* 2: the receipt. */
    toc_strlcpy( caster_name, ch->pcdata->resurrect_by, sizeof(caster_name) );
    snprintf( note, sizeof(note), "corpse %s in room %d, called by %s", id, to->vnum,
              caster_name );
    if ( !recovery_record( "request", "pending", ch->name, op, "resurrect", caster_name, note ) )
    {
        corpse_registry_unhold( corpse );
        send_to_char( "The call wavers: it could not be recorded, so nothing was moved.\n\r", ch );
        return;
    }
    corpse_registry_pending( corpse, op );

    /* 3: the mark, then everything to its owner, coin as coin until the
       gift is kept. */
    if ( !player_fix_record( ch, mark ) )
    {
        corpse_registry_unhold( corpse );
        recovery_record( "request", "abandoned", ch->name, op, "resurrect", caster_name,
                         "the mark could not be kept; nothing was moved" );
        send_to_char( "The call wavers: your return could not be recorded, so nothing was "
                      "moved.\n\r", ch );
        return;
    }
    for ( obj = corpse->contains; obj != NULL; obj = obj_next )
    {
        obj_next = obj->next_content;
        obj_from_obj( obj );
        obj_to_char( obj, ch );
        moved[given++] = obj;
    }

    /* 4: on the disk, or none of it. A test fails this save alone with
       "accept-save": "save-<Name>" can be taken first by the autosave. */
    if ( recovery_fault( "accept-save" ) )
        status = DURABLE_FAILED;
    else
    {
        save_char_obj( ch );
        status = save_char_obj_status();
    }
    if ( status == DURABLE_FAILED )
    {
        /* Back as it lay -- obj_to_obj puts each at the front, so last
           first -- and the record free to be written again. */
        for ( i = given - 1; i >= 0; i-- )
        {
            obj_from_char( moved[i] );
            obj_to_obj( moved[i], corpse );
        }
        player_fix_forget( ch, mark );
        corpse_registry_unhold( corpse );
        recovery_record( "request", "abandoned", ch->name, op, "resurrect", caster_name,
                         "the owner's file could not be saved; everything was put back" );
        send_to_char( "The call wavers and holds: your return could not be written down, "
                      "so your body still lies where it was with everything in it.  The "
                      "call still stands -- ACCEPT again in a moment.\n\r", ch );
        snprintf( note, sizeof(note), "RESURRECT: %s's ACCEPT was undone: their file could "
                  "not be saved (corpse %s).", ch->name, id );
        log_string( note );
        return;
    }
    if ( status != DURABLE_OK )
    {
        snprintf( note, sizeof(note), "RESURRECT: %s's ACCEPT is in their file but not "
                  "confirmed on the disk (corpse %s); it stays pending and is settled by "
                  "their next save, their login or the next boot.", ch->name, id );
        log_string( note );
    }
    else if ( corpse_registry_is_pending( corpse ) )
    {
        /* Saved, but the record would not leave live/: the keeper tries
           again, and never lays it while the receipt is open. */
        send_to_char( "Your body's record could not be closed yet; it is tried again, and "
                      "will not come back.\n\r", ch );
        bug( "do_accept: a resurrection's record could not be closed after the save", 0 );
    }
    resurrect_clear( ch );

    /* Coin into the purse now; what it cannot take falls to the floor. The
       file already holds it as coin, so a failure here loses nothing. */
    for ( i = 0; i < given; i++ )
    {
        obj = moved[i];
        if ( obj->item_type != ITEM_MONEY )
            continue;
        if ( obj->value[0] > 0 && can_adjust_coin_balance( ch, obj->value[0], obj->value[1] ) )
        {
            obj_from_char( obj );
            adjust_coin_balance( ch, obj->value[0], obj->value[1] );
            extract_obj( obj );
        }
        else
            kept++;
    }

    act( "$n fades away like a breath on glass.", ch, NULL, NULL, TO_ROOM );
    char_from_room( ch );
    char_to_room( ch, to );
    ch->hit = 1;
    if ( ch->position < POS_STANDING )
        ch->position = POS_STANDING;
    for ( i = 0; i < given && kept > 0; i++ )
    {
        obj = moved[i];
        if ( obj->item_type == ITEM_MONEY && obj->carried_by == ch )
        {
            obj_from_char( obj );
            obj_to_room( obj, to );
            kept--;
        }
    }

    act( "$p stirs, and $n rises from it, pale and gasping.", ch, corpse, NULL, TO_ROOM );
    send_to_char( "You open your eyes in your own body again, at the very edge of life.\n\r", ch );
    act( "$p crumbles to dust.", ch, corpse, NULL, TO_CHAR );
    act( "$p crumbles to dust.", ch, corpse, NULL, TO_ROOM );
    extract_obj( corpse );

    if ( ( caster = resurrect_find_owner( caster_name ) ) != NULL && caster != ch )
        act( "$N answers your call and lives again.", caster, NULL, ch, TO_CHAR );
    snprintf( note, sizeof(note), "RESURRECT: %s accepted %s's call and rose with %d object%s.",
        ch->name, caster_name, given, given == 1 ? "" : "s" );
    log_string( note );
    watch_log( ch, "resurrected by %s", caster_name );
    snprintf( note, sizeof(note), "%s raised %s at their corpse (room %d).",
        caster_name, ch->name, to->vnum );
    /* Names both: never to staff who could see neither (a caster no
       longer in the game is no presence to give away). */
    wizinfo( note, staff_notice_level_pair( ch, caster, LEVEL_IMMORTAL ) );
    do_look( ch, "auto" );
    save_char_obj( ch );
}

void do_decline( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *caster;
    char caster_name[MAX_INPUT_LENGTH];

    UNUSED_PARAM( argument );
    if ( IS_NPC(ch) || ch->pcdata == NULL || !resurrect_offer_open( ch ) )
    {
        send_to_char( "Nobody is calling you back.\n\r", ch );
        return;
    }
    toc_strlcpy( caster_name, ch->pcdata->resurrect_by, sizeof(caster_name) );
    resurrect_clear( ch );
    send_to_char( "You let the call fade. Your body stays where it lies.\n\r", ch );
    if ( ( caster = resurrect_find_owner( caster_name ) ) != NULL && caster != ch )
        act( "$N lets your call fade unanswered.", caster, NULL, ch, TO_CHAR );
}
