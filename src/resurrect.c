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
#include "merc.h"
#include "interp.h"

#define RESURRECT_OFFER_SECONDS  120

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

void do_accept( CHAR_DATA *ch, char *argument )
{
    OBJ_DATA *corpse, *obj, *obj_next;
    ROOM_INDEX_DATA *to;
    CHAR_DATA *caster;
    const char *why;
    char caster_name[sizeof(ch->pcdata->resurrect_by)];
    char note[MAX_STRING_LENGTH];
    int given = 0, kept = 0;

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
    resurrect_clear( ch );

    act( "$n fades away like a breath on glass.", ch, NULL, NULL, TO_ROOM );
    char_from_room( ch );
    char_to_room( ch, to );
    ch->hit = 1;
    if ( ch->position < POS_STANDING )
        ch->position = POS_STANDING;

    /* Everything the body held comes back with its owner, coin into the
       purse, the rest as it lay -- weight or no weight, as any restore. */
    for ( obj = corpse->contains; obj != NULL; obj = obj_next )
    {
        obj_next = obj->next_content;
        if ( obj->item_type == ITEM_MONEY )
        {
            if ( obj->value[0] <= 0
            ||   !can_adjust_coin_balance( ch, obj->value[0], obj->value[1] ) )
            {
                kept++;
                continue;
            }
            obj_from_obj( obj );
            adjust_coin_balance( ch, obj->value[0], obj->value[1] );
            extract_obj( obj );
            given++;
            continue;
        }
        obj_from_obj( obj );
        obj_to_char( obj, ch );
        given++;
    }

    act( "$p stirs, and $n rises from it, pale and gasping.", ch, corpse, NULL, TO_ROOM );
    send_to_char( "You open your eyes in your own body again, at the very edge of life.\n\r", ch );

    /* Always used up, as RAISE DEAD's is: a corpse left holding coin
       could call its owner back to it again and again. What the purse
       could not take falls to the floor here. */
    snprintf( note, sizeof(note), "resurrected by %s", caster_name );
    if ( kept > 0 && corpse->contains != NULL )
    {
        send_to_char( "Some of the coin is more than you can carry; it falls to the ground.\n\r", ch );
        spill_corpse( corpse );
    }
    corpse_registry_touched( corpse, note );
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
    wizinfo( note, LEVEL_IMMORTAL );
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
