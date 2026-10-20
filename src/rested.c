/*
 * Rested experience, after World of Warcraft's (owner's design, 2026-10-20).
 *
 * Time spent out of the game banks bonus experience -- but only if the
 * character quit somewhere a body could rest: a safe room, a room that
 * heals (hit point or mana regeneration), the Temple, the altar where the
 * pit healer stands, or the character's own recall point. Quitting in a
 * dungeon, a field or a jail banks nothing.
 *
 * Each hour away banks REST_PERCENT_PER_HOUR percent of a level's
 * experience, up to REST_CAP_PERCENT percent. While the pool lasts, every
 * kill's experience is doubled, the extra drawn from the pool, and the
 * pool is spent only where gain_exp would pay it -- never at level 50 or
 * at the remort cap, where it would be thrown away.
 *
 * Where they quit is decided at QUIT (rest_xp_on_quit, before the save); an
 * idle character the game has already moved into the void is judged by
 * the room it was taken from. What has accrued is added at the next real
 * login (rest_xp_on_login, from the nanny), never at a reconnect to a
 * character still in the game. RESTED shows the pool and whether the room
 * you stand in would count.
 */
#include <time.h>
#include "merc.h"

#define REST_PERCENT_PER_HOUR   5       /* of a level, per hour away */
#define REST_CAP_PERCENT        150     /* a level and a half at most */
#define REST_MIN_AWAY           ( 15 * 60 )  /* a relog is not a rest */

/* A level's worth of experience at this character's level. Below hero it
   is exp_per_level; a hero's levels follow next_xp_level's own steps. */
static long rest_level_span( CHAR_DATA *ch )
{
    /* next_xp_level(L) - next_xp_level(L - 1), for a hero. */
    if ( ch->level >= LEVEL_HERO )
        return 10000L + (long) HERO_STEP_XP * ( ch->level - LEVEL_HERO );
    return UMAX( 1, exp_per_level( ch, ch->pcdata->points ) );
}

/* Whether experience would be paid at all: gain_exp's own refusals. */
static bool rest_xp_usable( CHAR_DATA *ch )
{
    return !IS_NPC(ch) && ch->pcdata != NULL
        && ch->level <= LEVEL_KING && ch->level != 50
        && ch->level < 54 + ch->pcdata->num_remorts;
}

/* Somewhere a body could rest. */
bool rest_room_ok( CHAR_DATA *ch, ROOM_INDEX_DATA *room )
{
    if ( ch == NULL || room == NULL )
        return false;
    if ( IS_SET( room->room_flags, ROOM_JAIL ) )
        return false;
    if ( IS_SET( room->room_flags, ROOM_SAFE )
    ||   IS_SET( room->room_flags, ROOM_HP_REGEN )
    ||   IS_SET( room->room_flags, ROOM_MANA_REGEN )
    ||   room->vnum == ROOM_VNUM_TEMPLE
    ||   room->vnum == ROOM_VNUM_ALTAR )
        return true;
    return !IS_NPC(ch) && room == recall_room( ch );
}

/* At QUIT, before the save: where are they lying down? */
void rest_xp_on_quit( CHAR_DATA *ch )
{
    ROOM_INDEX_DATA *room;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;
    /* The idle are moved into the void before they are purged; judge
       the room they were taken from. */
    room = ch->in_room;
    if ( room != NULL && room->vnum == ROOM_VNUM_LIMBO && ch->was_in_room != NULL )
        room = ch->was_in_room;
    ch->pcdata->rest_eligible = rest_room_ok( ch, room );
}

/* At a real login, past the password: bank the time away. */
void rest_xp_on_login( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];
    long away, gained, cap, span;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;
    away = ch->pcdata->last_logout > 0
         ? (long) current_time - ch->pcdata->last_logout : 0;
    span = rest_level_span( ch );
    cap = span * REST_CAP_PERCENT / 100;

    if ( ch->pcdata->rest_eligible && away >= REST_MIN_AWAY && rest_xp_usable( ch ) )
    {
        /* Whole minutes, capped at what fills the pool from nothing, so
           a year away cannot overflow a 32-bit long. */
        long minutes = UMIN( away / 60,
                             60L * REST_CAP_PERCENT / REST_PERCENT_PER_HOUR );

        gained = span * REST_PERCENT_PER_HOUR / 100 * minutes / 60;
        if ( gained > 0 && ch->pcdata->rest_xp < cap )
        {
            ch->pcdata->rest_xp = UMIN( cap, ch->pcdata->rest_xp + gained );
            achievement_record_event( ch, ACHIEVEMENT_EVENT_WELL_RESTED, true );
            snprintf( buf, sizeof(buf), "{0BYou feel well rested.{00  Your kills "
                      "earn double experience until %ld more is spent "
                      "(%ld%% of a level).  RESTED tells you more.\n\r",
                      ch->pcdata->rest_xp, ch->pcdata->rest_xp * 100 / span );
            send_to_char( buf, ch );
        }
    }
    else if ( !ch->pcdata->rest_eligible && away >= 60 * 60 && rest_xp_usable( ch ) )
        send_to_char( "You slept rough last time.  Quit somewhere safe -- a "
                      "healing room, the Temple, your recall point -- to come "
                      "back rested.\n\r", ch );
    ch->pcdata->rest_eligible = false;
}

/* What a kill worth `xp` draws from the pool: as much again, while it
   lasts, and only where it would be paid. */
int rest_xp_bonus( CHAR_DATA *ch, int xp )
{
    long bonus;

    if ( xp <= 0 || IS_NPC(ch) || ch->pcdata == NULL
    ||   ch->pcdata->rest_xp <= 0 || !rest_xp_usable( ch ) )
        return 0;
    bonus = UMIN( (long) xp, ch->pcdata->rest_xp );
    ch->pcdata->rest_xp -= bonus;
    if ( ch->pcdata->rest_xp <= 0 )
    {
        ch->pcdata->rest_xp = 0;
        send_to_char( "You no longer feel rested.\n\r", ch );
    }
    return (int) bonus;
}

void do_rested( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    long span;

    UNUSED_PARAM(argument);
    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;
    span = rest_level_span( ch );
    if ( ch->pcdata->rest_xp > 0 )
        snprintf( buf, sizeof(buf), "You are rested: your kills earn double "
                  "experience until %ld more is spent (%ld%% of a level).\n\r",
                  ch->pcdata->rest_xp, ch->pcdata->rest_xp * 100 / span );
    else
        snprintf( buf, sizeof(buf), "You are not rested.\n\r" );
    send_to_char( buf, ch );
    if ( !rest_xp_usable( ch ) )
        send_to_char( "You earn no experience at your level, so rest would "
                      "be kept until you do.\n\r", ch );
    snprintf( buf, sizeof(buf), "Quitting here %s.\n\r",
              rest_room_ok( ch, ch->in_room )
                  ? "would let you rest"
                  : "would not let you rest -- try a healing room, the "
                    "Temple, the altar or your recall point" );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf), "Each hour away banks %d%% of a level, up to "
              "%d%%.\n\r", REST_PERCENT_PER_HOUR, REST_CAP_PERCENT );
    send_to_char( buf, ch );
}
