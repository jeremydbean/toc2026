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
void resurrect_corpse_owner( OBJ_DATA *corpse, char *out, size_t size )
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

/* The player in the game by that name, switched or not -- never a copy
   loaded from a file for a moment (STASH TAKE, GRANTPSI), which sits in
   the character list but plays nowhere. */
CHAR_DATA *resurrect_find_owner( const char *name )
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

/* An object leaving the game: any offer that names it is forgotten, so no
   pointer to the corpse outlives it (review, 2026-11-11: the memory
   sweep read the purged corpse through the offer). Corpses only, so the
   walk over the characters is rare. */
void resurrect_forget_corpse( OBJ_DATA *obj )
{
    LIST_ITERATOR iter;
    CHAR_DATA *ch;

    if ( obj == NULL || ( obj->item_type != ITEM_CORPSE_PC
                       && obj->item_type != ITEM_CORPSE_NPC ) )
        return;
    FOR_EACH_CHARACTER( iter, ch )
        if ( !IS_NPC(ch) && ch->pcdata != NULL && ch->pcdata->resurrect_corpse == obj )
            ch->pcdata->resurrect_corpse = NULL;
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
    if ( is_jailed( ch )
    ||   IS_SET( ch->in_room->room_flags, ROOM_JAIL )
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
 * A corpse's contents given to its owner, on the disk or not at all
 * (review, 2026-10-26; shared with RAISE DEAD, review 2026-11-04, which
 * moved the things, extracted the corpse and ignored the save, so a
 * failed save and a crash lost the kit it gave back):
 *
 *   1. the corpse's record written now and HELD as it is (corpses.c), and
 *      the mark restore:resurrect:<id> proved to fit the owner's Fixes;
 *   2. a pending receipt, resurrect:<corpse id>, in the ledger, opened on
 *      the corpse too;
 *   3. the mark, then the objects moved to the owner -- every one, or with
 *      only_what_fits those their hands and back can take (RAISE DEAD's
 *      rule), the rest staying in the corpse;
 *   4. the owner's save. One on the disk settles the transfer through the
 *      save itself: the held record into history as "resurrected", then
 *      the committed receipt (corpse_registry_owner_saved).
 *
 * Answers CORPSE_GIVE_REFUSED with `why` filled when nothing was begun
 * (a death still settling, another transfer, a full Fixes list, a ledger
 * that would not take the receipt); DURABLE_FAILED when the save failed
 * and everything went back as it lay -- mark off, hold lifted, receipt
 * abandoned; DURABLE_UNCERTAIN when the file was renamed into place but
 * not confirmed -- it holds the gift, so nothing is taken back and the
 * transfer stays pending for the next save, the login or the boot; or
 * DURABLE_OK. `moved` and `given` say what went; `op` names the receipt.
 */
int corpse_give_to_owner( CHAR_DATA *owner, OBJ_DATA *corpse, const char *spell,
                          const char *by, bool only_what_fits, const char *fault_point,
                          OBJ_DATA **moved, int max_moved, int *given,
                          char *op, size_t opsize, char *why, size_t whysize )
{
    OBJ_DATA *obj, *obj_next;
    char id[32], mark[96], note[MAX_STRING_LENGTH];
    int count = 0, i, status;

    *given = 0;
    if ( opsize > 0 )
        op[0] = '\0';
    if ( whysize > 0 )
        why[0] = '\0';
    /* An unsettled death holds the owner's file still: no save of theirs
       may land, so nothing would. */
    if ( corpse_registry_holds_still( owner ) )
    {
        toc_strlcpy( why, "A death is still being laid to rest, so nothing was moved.  Try "
                     "again in a moment.", whysize );
        return CORPSE_GIVE_REFUSED;
    }
    for ( obj = corpse->contains; obj != NULL; obj = obj->next_content )
        count++;
    if ( count > max_moved )
    {
        toc_strlcpy( why, "The body holds more than one call can carry back; let somebody "
                     "lighten it first.", whysize );
        return CORPSE_GIVE_REFUSED;
    }

    /* 1: the corpse as it is, on the disk and held; the mark must fit. A
       death still being written down holds the corpse already, so it is
       refused here too. */
    if ( corpse_registry_hold( corpse, id, sizeof(id) ) == false )
    {
        toc_strlcpy( why, "The body's record could not be kept safe -- or the death is "
                     "still being written down -- so nothing was moved.  Try again in a "
                     "moment.", whysize );
        return CORPSE_GIVE_REFUSED;
    }
    snprintf( op, opsize, "resurrect:%s", id );
    snprintf( mark, sizeof(mark), "restore:%s", op );
    if ( !player_fix_can_record( owner, mark ) )
    {
        corpse_registry_unhold( corpse );
        toc_strlcpy( why, "The record that would prove the return is full, so nothing was "
                     "moved.  Staff can see why in the log.", whysize );
        return CORPSE_GIVE_REFUSED;
    }

    /* 2: the receipt. */
    snprintf( note, sizeof(note), "corpse %s in room %d, %s by %s", id,
              corpse->in_room != NULL ? corpse->in_room->vnum : 0, spell, by );
    if ( !recovery_record( "request", "pending", owner->name, op, "resurrect", by, note ) )
    {
        corpse_registry_unhold( corpse );
        toc_strlcpy( why, "The return could not be recorded, so nothing was moved.", whysize );
        return CORPSE_GIVE_REFUSED;
    }
    corpse_registry_pending( corpse, op );

    /* 3: the mark, then the things. */
    if ( !player_fix_record( owner, mark ) )
    {
        corpse_registry_unhold( corpse );
        recovery_record( "request", "abandoned", owner->name, op, "resurrect", by,
                         "the mark could not be kept; nothing was moved" );
        toc_strlcpy( why, "The return could not be recorded, so nothing was moved.", whysize );
        return CORPSE_GIVE_REFUSED;
    }
    for ( obj = corpse->contains; obj != NULL; obj = obj_next )
    {
        obj_next = obj->next_content;
        if ( only_what_fits
        &&   ( owner->carry_number + get_obj_number( obj ) > can_carry_n( owner )
            || query_carry_weight( owner ) + get_obj_weight( obj ) > can_carry_w( owner ) ) )
            continue;
        obj_from_obj( obj );
        obj_to_char( obj, owner );
        moved[(*given)++] = obj;
    }

    /* 4: on the disk, or none of it. A test fails this save alone with the
       caller's fault point: "save-<Name>" can be taken first by an
       autosave. */
    if ( fault_point != NULL && recovery_fault( fault_point ) )
        status = DURABLE_FAILED;
    else
    {
        save_char_obj( owner );
        status = save_char_obj_status();
    }
    if ( status == DURABLE_FAILED )
    {
        /* Back as it lay -- obj_to_obj puts each at the front, so last
           first -- and the record free to be written again. */
        for ( i = *given - 1; i >= 0; i-- )
        {
            obj_from_char( moved[i] );
            obj_to_obj( moved[i], corpse );
        }
        *given = 0;
        player_fix_forget( owner, mark );
        corpse_registry_unhold( corpse );
        recovery_record( "request", "abandoned", owner->name, op, "resurrect", by,
                         "the owner's file could not be saved; everything was put back" );
        return DURABLE_FAILED;
    }
    if ( status != DURABLE_OK )
    {
        snprintf( note, sizeof(note), "RESURRECT: %s's %s is in their file but not "
                  "confirmed on the disk (corpse %s); it stays pending and is settled by "
                  "their next save, their login or the next boot.", owner->name, spell, id );
        log_string( note );
    }
    else if ( corpse_registry_is_pending( corpse ) )
    {
        /* Saved, but the record would not leave live/: the keeper tries
           again, and never lays it while the receipt is open. */
        send_to_char( "Your body's record could not be closed yet; it is tried again, and "
                      "will not come back.\n\r", owner );
        bug( "corpse_give_to_owner: the corpse's record could not be closed after the save", 0 );
    }
    return status;
}

/*
 * ACCEPT gives the corpse's contents to its owner through
 * corpse_give_to_owner, above: done, on the disk, or not done at all. A
 * save that FAILED put everything back and the offer stands; one renamed
 * into place but not confirmed holds the gift, so nothing is taken back
 * and it is settled by the owner's next save, their login or the boot.
 */
void do_accept( CHAR_DATA *ch, char *argument )
{
    OBJ_DATA *corpse, *obj;
    OBJ_DATA *moved[MAX_RESURRECT_OBJECTS];
    ROOM_INDEX_DATA *to;
    CHAR_DATA *caster;
    const char *why;
    char caster_name[sizeof(ch->pcdata->resurrect_by)];
    char note[MAX_STRING_LENGTH];
    char op[64];
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
    toc_strlcpy( caster_name, ch->pcdata->resurrect_by, sizeof(caster_name) );
    status = corpse_give_to_owner( ch, corpse, "called", caster_name, false, "accept-save",
                                   moved, MAX_RESURRECT_OBJECTS, &given, op, sizeof(op),
                                   note, sizeof(note) );
    if ( status == CORPSE_GIVE_REFUSED )
    {
        send_to_char( "The call wavers: ", ch );
        send_to_char( note, ch );
        send_to_char( "\n\r", ch );
        return;
    }
    if ( status == DURABLE_FAILED )
    {
        send_to_char( "The call wavers and holds: your return could not be written down, "
                      "so your body still lies where it was with everything in it.  The "
                      "call still stands -- ACCEPT again in a moment.\n\r", ch );
        snprintf( note, sizeof(note), "RESURRECT: %s's ACCEPT was undone: their file could "
                  "not be saved (%s).", ch->name, op );
        log_string( note );
        snprintf( note, sizeof(note), "moved=0 caster=%s", caster_name );
        playlog_outcome( ch, "resurrect-accept", "failure", "save", op, note );
        return;
    }
    /* The rest of the way it reached the disk: say so in the journal,
       under the receipt's id (review, 2026-11-03). No room: where the
       corpse lay is the corpse's business. */
    {
        char jnote[128];

        snprintf( jnote, sizeof(jnote), "objects=%d caster=%s", given, caster_name );
        playlog_outcome( ch, "resurrect-accept",
                         status == DURABLE_OK ? "success" : "uncertain",
                         status == DURABLE_OK ? "-" : "save-unconfirmed", op, jnote );
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
