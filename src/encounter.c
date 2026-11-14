/*
 * encounter.c -- what players come across, and what they do about it.
 *
 * Owner, 2026-11-13: "count/track components and herbs and stuff so we
 * can see how often players are coming across them during normal
 * gameplay, and see which ones they choose to pick up or move past ...
 * implement as much logging for all things like this so we can adjust and
 * tweak balance and identify bugs".
 *
 * Every row goes to log/play.tsv through playlog_row (its common columns:
 * epoch, kind, name, level, room, area), so the journal's rules hold: a
 * wizinvis player writes nothing, and a room the dealer or the goblin
 * stands in is "-". Staff (is_staff, by level) are never counted: their
 * sightings would read as players'. Nothing here is saved.
 *
 * Things on the ground with a life of their own -- herbs, spell
 * components, Noblegarden's eggs, area maps and coin -- are followed one
 * by one (the "life kinds"):
 *
 *   laid     a scatterer put it down (component_scatter, the egg hunt, a
 *            goblin's spill): id, kind, vnum, name, room, area, source.
 *   spotted  a player saw it lying there, once per player per stint on
 *            the ground (LOOK or arriving): id, kind, vnum, name, seconds
 *            it had lain, how many players had seen it, source, how.
 *   picked   a player took it from the ground: id, kind, vnum, name,
 *            seconds lain, seconds since this player spotted it (-1:
 *            never seen, e.g. in the dark), seers, source, command.
 *   passed   a player who spotted it went elsewhere (or quit) leaving it:
 *            id, kind, vnum, name, seconds lain, seconds they had it in
 *            view, seers, source, the room they left.
 *   cleared  it left the ground other than into a player's hands: a
 *            mobile picked it up, staff, a purge, a container: id, kind,
 *            vnum, name, seconds lain, seers, source, why, who, room.
 *
 * The rare visitors -- the black market dealer, the treasure goblin, the
 * cartographer, the holiday bosses, the black dragon and Hermie -- get
 * rare-seen, rare-acted (fought, bought) and rare-passed rows, keyed by
 * the visitor's own instance, so a visit is counted however often it is
 * seen.
 *
 * Everything else is counted, not rowed: every mobile a player saw
 * against those they fought (and of those, how many attacked first), and
 * every takeable object lying about against those taken -- a table per
 * sitting, written as `sightings` rows at its end (and when the table
 * fills): "mob <vnum>:<seen>/<fought>/<attacked> ..." and
 * "item <vnum>:<seen>/<taken> ...".
 *
 * A `census` row every ENC_CENSUS_SECS (15 minutes; TOC_ENCOUNTER_CENSUS_SECS
 * for tests) while anybody plays: herbs, components, eggs and coin piles on
 * the ground, herbs and components players carry, players, and the rows of
 * each kind since the last census.
 *
 * tools/log_report.py's "== encounters" section reads all of it.
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
#include "numparse.h"

#define ENC_RING          160   /* sightings a sitting remembers */
#define ENC_TALLY_MAX     96    /* vnums counted before a sightings row */
#define ENC_CENSUS_SECS   900
#define ENC_FIELDS        600   /* playlog.c's row holds PLAY_LINE + 256 */
#define ENC_SEEN          1L
#define ENC_ACTED         2L
#define ENC_PASSED        4L
#define ENC_FLAGS         3     /* bits below the id in a ring entry */

typedef struct
{
    int  vnum;
    bool mob;
    int  seen;
    int  acted;
    int  attacked;
} ENC_TALLY;

struct encounter_state
{
    long      ring[ENC_RING];      /* id << ENC_FLAGS | flags; 0 empty */
    time_t    ring_at[ENC_RING];   /* when it was first seen */
    int       next;
    int       room;                /* the room last looked at, by vnum */
    ENC_TALLY tally[ENC_TALLY_MAX];
    int       rows;
};

static long enc_next_id;

/* Since the last census. */
static struct
{
    long laid, spotted, picked, passed, cleared, rare, mobs_seen, mobs_fought;
} enc_count;

/* ------------------------------------------------------------ helpers */

static const char *life_kind( const OBJ_DATA *obj )
{
    if ( obj == NULL || obj->pIndexData == NULL )
        return NULL;
    if ( is_forage_obj( obj ) )
        return obj->item_type == ITEM_HERB ? "herb" : "component";
    if ( obj->pIndexData->vnum == OBJ_VNUM_PAINTED_EGG )
        return "egg";
    if ( obj->pIndexData->vnum == OBJ_VNUM_AREA_MAP )
        return "map";
    if ( obj->item_type == ITEM_MONEY )
        return "coin";
    return NULL;
}

/* Something on the floor worth counting as seen and taken: a thing a
   player could pick up, not a corpse. */
static bool floor_item( const OBJ_DATA *obj )
{
    return obj != NULL && obj->pIndexData != NULL
        && CAN_WEAR( obj, ITEM_TAKE )
        && obj->item_type != ITEM_CORPSE_NPC
        && obj->item_type != ITEM_CORPSE_PC;
}

static const char *rare_kind( const CHAR_DATA *mob )
{
    int vnum;

    if ( mob == NULL || !IS_NPC(mob) || mob->pIndexData == NULL )
        return NULL;
    if ( is_black_market_dealer( mob ) )
        return "dealer";
    if ( is_treasure_goblin( mob ) )
        return "goblin";
    vnum = mob->pIndexData->vnum;
    if ( vnum == MOB_VNUM_CARTOGRAPHER )
        return "cartographer";
    if ( vnum == MOB_VNUM_EVENT_HORSEMAN || vnum == MOB_VNUM_EVENT_FATHER )
        return "holiday-boss";
    if ( vnum == 4474 )                 /* disaster.c's black dragon */
        return "dragon";
    if ( vnum == MOB_VNUM_SPELLUP )
        return "hermie";
    return NULL;
}

/* A player whose comings and goings are counted: playing, a mortal by
   level, not wizinvis. */
static bool counted( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && ch->desc != NULL && ch->desc->connected == CON_PLAYING
        && !is_staff( ch ) && !IS_SET( ch->act, PLR_WIZINVIS );
}

static ENCOUNTER_STATE *state_of( CHAR_DATA *ch )
{
    if ( ch->pcdata->encounter == NULL )
        ch->pcdata->encounter = alloc_mem( (int) sizeof(ENCOUNTER_STATE) );
    return ch->pcdata->encounter;
}

static long *ring_find( ENCOUNTER_STATE *st, long id, time_t **at )
{
    int i;

    if ( id <= 0 )
        return NULL;
    for ( i = 0; i < ENC_RING; i++ )
        if ( st->ring[i] != 0 && ( st->ring[i] >> ENC_FLAGS ) == id )
        {
            if ( at != NULL )
                *at = &st->ring_at[i];
            return &st->ring[i];
        }
    return NULL;
}

static long *ring_add( ENCOUNTER_STATE *st, long id )
{
    long *e = &st->ring[st->next];

    st->ring_at[st->next] = current_time;
    st->next = ( st->next + 1 ) % ENC_RING;
    *e = ( id << ENC_FLAGS ) | ENC_SEEN;
    return e;
}

static long obj_id( OBJ_DATA *obj )
{
    if ( obj->enc_id == 0 )
        obj->enc_id = ++enc_next_id;
    return obj->enc_id;
}

static long mob_id( CHAR_DATA *mob )
{
    if ( mob->enc_id == 0 )
        mob->enc_id = ++enc_next_id;
    return mob->enc_id;
}

static long lain( const OBJ_DATA *obj )
{
    return obj->enc_since > 0 ? (long) ( current_time - obj->enc_since ) : -1L;
}

static void room_text( int vnum, char *room, size_t rsize, char *area, size_t asize )
{
    ROOM_INDEX_DATA *r = vnum > 0 ? get_room_index( vnum ) : NULL;

    if ( r == NULL )
    {
        snprintf( room, rsize, "0" );
        snprintf( area, asize, "-" );
    }
    else if ( room_hides_from_log( r ) )
    {
        snprintf( room, rsize, "-" );
        snprintf( area, asize, "-" );
    }
    else
    {
        snprintf( room, rsize, "%d", r->vnum );
        playlog_clean( area, asize, r->area != NULL ? r->area->file_name : "?" );
    }
}

static void obj_name( const OBJ_DATA *obj, char *buf, size_t size )
{
    playlog_clean( buf, size, obj->short_descr != NULL ? obj->short_descr : "?" );
}

static ENC_TALLY *tally_get( CHAR_DATA *ch, ENCOUNTER_STATE *st, bool mob, int vnum );

/* ------------------------------------------------------- the ground */

/* obj_to_room: anything put on the ground begins a stint there. Moving
   from room to room (a bounce, a river) keeps the stint going. */
void encounter_obj_floor( OBJ_DATA *obj )
{
    if ( obj == NULL )
        return;
    if ( !obj->enc_floor )
    {
        obj->enc_id     = ++enc_next_id;      /* a new stint, a new id */
        obj->enc_since  = current_time;
        obj->enc_seers  = 0;
        obj->enc_source = playlog_actor()[0] == '(' ? "world" : "dropped";
        obj->enc_floor  = true;
    }
}

/* A scatterer laid it (after obj_to_room): component_scatter, the egg
   hunt, a goblin's spill. */
void encounter_laid( OBJ_DATA *obj, const char *source )
{
    char fields[ENC_FIELDS], name[80], room[16], area[64];
    const char *kind;

    if ( obj == NULL || obj->in_room == NULL )
        return;
    encounter_obj_floor( obj );
    obj->enc_source = source;
    if ( ( kind = life_kind( obj ) ) == NULL )
        return;
    enc_count.laid++;
    obj_name( obj, name, sizeof(name) );
    room_text( obj->in_room->vnum, room, sizeof(room), area, sizeof(area) );
    snprintf( fields, sizeof(fields), "%ld\t%s\t%d\t%s\t%s\t%s\t%s",
              obj_id( obj ), kind, obj->pIndexData->vnum, name, room, area, source );
    playlog_row( "laid", NULL, fields );
}

static void write_cleared( OBJ_DATA *obj, const char *kind, const char *why )
{
    char fields[ENC_FIELDS], name[80], room[16], area[64], actor[96];
    int vnum = obj->in_room != NULL ? obj->in_room->vnum : 0;

    /* A wizinvis immortal's GET, SACRIFICE or PURGE: no trace, room or
       otherwise (review, 2026-11-13: the row named the room and "staff"). */
    if ( playlog_hidden_command() )
        return;
    enc_count.cleared++;
    obj_name( obj, name, sizeof(name) );
    room_text( vnum, room, sizeof(room), area, sizeof(area) );
    playlog_clean( actor, sizeof(actor), playlog_actor() );
    snprintf( fields, sizeof(fields), "%ld\t%s\t%d\t%s\t%ld\t%d\t%s\t%s\t%s\t%s\t%s",
              obj_id( obj ), kind, obj->pIndexData->vnum, name, lain( obj ),
              obj->enc_seers, obj->enc_source != NULL ? obj->enc_source : "-",
              why, actor, room, area );
    playlog_row( "cleared", NULL, fields );
}

/* It reached somebody's hands from the ground (get_obj's room branch,
   before obj_from_room, and obj_to_char for every other way). */
void encounter_obj_held( OBJ_DATA *obj, CHAR_DATA *ch )
{
    char fields[ENC_FIELDS], name[80], how[64];
    const char *kind;
    ENCOUNTER_STATE *st;
    long *e;
    time_t *at = NULL;

    if ( obj == NULL || ch == NULL || !obj->enc_floor )
        return;
    kind = life_kind( obj );
    if ( !counted( ch ) )
    {
        if ( kind != NULL )
        {
            char why[48];

            if ( IS_NPC(ch) )
                snprintf( why, sizeof(why), "mob %d",
                          ch->pIndexData != NULL ? ch->pIndexData->vnum : 0 );
            else
                snprintf( why, sizeof(why), "%s", is_staff( ch ) ? "staff" : "player-not-playing" );
            if ( IS_NPC(ch) || !IS_SET(ch->act, PLR_WIZINVIS) )
                write_cleared( obj, kind, why );
        }
        obj->enc_floor = false;
        return;
    }

    st = state_of( ch );
    e  = ring_find( st, obj->enc_id, &at );
    if ( kind != NULL )
    {
        enc_count.picked++;
        obj_name( obj, name, sizeof(name) );
        playlog_clean( how, sizeof(how), playlog_how( ch ) );
        snprintf( fields, sizeof(fields), "%ld\t%s\t%d\t%s\t%ld\t%ld\t%d\t%s\t%s",
                  obj_id( obj ), kind, obj->pIndexData->vnum, name, lain( obj ),
                  e != NULL && at != NULL ? (long) ( current_time - *at ) : -1L,
                  obj->enc_seers, obj->enc_source != NULL ? obj->enc_source : "-", how );
        playlog_row( "picked", ch, fields );
    }
    else if ( floor_item( obj ) && ( e == NULL || !( *e & ENC_ACTED ) ) )
    {
        ENC_TALLY *t = tally_get( ch, st, false, obj->pIndexData->vnum );

        if ( e == NULL && t != NULL )
            t->seen++;                  /* taken unseen: in the dark, by name */
        if ( t != NULL )
            t->acted++;
    }
    if ( e == NULL )
        e = ring_add( st, obj_id( obj ) );
    *e |= ENC_ACTED;
    obj->enc_floor = false;
}

/* It left the ground for anywhere but somebody's hands: a container,
   extraction (a purge, a sacrifice, a junk). */
void encounter_obj_off_floor( OBJ_DATA *obj, const char *why )
{
    const char *kind;

    if ( obj == NULL || !obj->enc_floor )
        return;
    obj->enc_floor = false;
    if ( ( kind = life_kind( obj ) ) != NULL )
        write_cleared( obj, kind, why );
}

/* ------------------------------------------------------- the tallies */

static void tally_flush( CHAR_DATA *ch, ENCOUNTER_STATE *st )
{
    char fields[ENC_FIELDS];
    int pass, i;

    for ( pass = 0; pass < 2; pass++ )
    {
        bool mob = pass == 0;
        size_t n = 0;

        fields[0] = '\0';
        for ( i = 0; i < st->rows; i++ )
        {
            ENC_TALLY *t = &st->tally[i];
            char entry[64];
            int len;

            if ( t->mob != mob )
                continue;
            len = mob ? snprintf( entry, sizeof(entry), "%s%d:%d/%d/%d", n > 0 ? " " : "",
                                  t->vnum, t->seen, t->acted, t->attacked )
                      : snprintf( entry, sizeof(entry), "%s%d:%d/%d", n > 0 ? " " : "",
                                  t->vnum, t->seen, t->acted );
            if ( len < 0 )
                continue;
            if ( n + (size_t) len + 16 >= sizeof(fields) )
            {
                char row[ENC_FIELDS + 8];

                snprintf( row, sizeof(row), "%s\t%s", mob ? "mob" : "item", fields );
                playlog_row( "sightings", ch, row );
                n = 0;
                fields[0] = '\0';
                len = mob ? snprintf( entry, sizeof(entry), "%d:%d/%d/%d",
                                      t->vnum, t->seen, t->acted, t->attacked )
                          : snprintf( entry, sizeof(entry), "%d:%d/%d",
                                      t->vnum, t->seen, t->acted );
            }
            toc_strlcat( fields, entry, sizeof(fields) );
            n += (size_t) len;
        }
        if ( n > 0 )
        {
            char row[ENC_FIELDS + 8];

            snprintf( row, sizeof(row), "%s\t%s", mob ? "mob" : "item", fields );
            playlog_row( "sightings", ch, row );
        }
    }
    st->rows = 0;
}

static ENC_TALLY *tally_get( CHAR_DATA *ch, ENCOUNTER_STATE *st, bool mob, int vnum )
{
    int i;

    for ( i = 0; i < st->rows; i++ )
        if ( st->tally[i].vnum == vnum && st->tally[i].mob == mob )
            return &st->tally[i];
    if ( st->rows >= ENC_TALLY_MAX )
        tally_flush( ch, st );
    st->tally[st->rows].vnum = vnum;
    st->tally[st->rows].mob = mob;
    st->tally[st->rows].seen = 0;
    st->tally[st->rows].acted = 0;
    st->tally[st->rows].attacked = 0;
    return &st->tally[st->rows++];
}

/* ----------------------------------------------------- moving past */

static bool stands_in( CHAR_DATA *ch, ROOM_INDEX_DATA *room )
{
    CHAR_DATA *rch;

    for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
        if ( rch == ch )
            return true;
    return false;
}

/* What the player spotted in the room they last looked at, and left
   lying or standing there: one passed row each, once. `anyway` for a
   quit, where they have not left. */
static void passed_check( CHAR_DATA *ch, ENCOUNTER_STATE *st, bool anyway, const char *how )
{
    ROOM_INDEX_DATA *room;
    OBJ_DATA *obj;
    CHAR_DATA *rch;
    char fields[ENC_FIELDS], name[80], rtext[16], area[64];
    bool hidden;

    if ( st->room <= 0 || ( room = get_room_index( st->room ) ) == NULL )
        return;
    if ( !anyway && room == ch->in_room )
        return;
    room_text( room->vnum, rtext, sizeof(rtext), area, sizeof(area) );
    /* Left a room the dealer or the goblin stands in: the rows about it
       must not carry the room walked into either, one exit away, or the
       journal maps him (review, 2026-11-13). */
    hidden = room_hides_from_log( room );

    for ( obj = room->contents; obj != NULL; obj = obj->next_content )
    {
        const char *kind = life_kind( obj );
        time_t *at = NULL;
        long *e;

        if ( kind == NULL || !obj->enc_floor
        ||   ( e = ring_find( st, obj->enc_id, &at ) ) == NULL
        ||   ( *e & ( ENC_ACTED | ENC_PASSED ) ) )
            continue;
        *e |= ENC_PASSED;
        enc_count.passed++;
        obj_name( obj, name, sizeof(name) );
        snprintf( fields, sizeof(fields), "%ld\t%s\t%d\t%s\t%ld\t%ld\t%d\t%s\t%s\t%s",
                  obj->enc_id, kind, obj->pIndexData->vnum, name, lain( obj ),
                  at != NULL ? (long) ( current_time - *at ) : -1L,
                  obj->enc_seers, obj->enc_source != NULL ? obj->enc_source : "-",
                  rtext, how );
        if ( hidden )
            playlog_row_unplaced( "passed", ch, fields );
        else
            playlog_row( "passed", ch, fields );
    }
    for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
    {
        const char *kind = rare_kind( rch );
        time_t *at = NULL;
        long *e;

        if ( kind == NULL
        ||   ( e = ring_find( st, rch->enc_id, &at ) ) == NULL
        ||   ( *e & ( ENC_ACTED | ENC_PASSED ) ) )
            continue;
        *e |= ENC_PASSED;
        snprintf( fields, sizeof(fields), "%s\t%d\t%ld\t%ld\t%s",
                  kind, rch->pIndexData->vnum, rch->enc_id,
                  at != NULL ? (long) ( current_time - *at ) : -1L, how );
        if ( hidden )
            playlog_row_unplaced( "rare-passed", ch, fields );
        else
            playlog_row( "rare-passed", ch, fields );
    }
}

/* ------------------------------------------------------- seeing */

/* do_look's room view, arriving or looking: what lies and stands there,
   as the player was shown it. Not a room seen from elsewhere
   (clairvoyance borrows in_room for its LOOK). */
void encounter_room_seen( CHAR_DATA *ch, bool arrived )
{
    ENCOUNTER_STATE *st;
    OBJ_DATA *obj;
    CHAR_DATA *rch;
    char fields[ENC_FIELDS], name[80];
    const char *how = arrived ? "arrive" : "look";

    if ( !counted( ch ) || ch->in_room == NULL || !stands_in( ch, ch->in_room ) )
        return;
    st = state_of( ch );
    if ( st->room != ch->in_room->vnum )
    {
        passed_check( ch, st, false, "left" );
        st->room = ch->in_room->vnum;
    }

    for ( obj = ch->in_room->contents; obj != NULL; obj = obj->next_content )
    {
        const char *kind;

        if ( obj->description == NULL || obj->description[0] == '\0'
        ||   !can_see_obj( ch, obj ) )
            continue;
        kind = life_kind( obj );
        if ( kind == NULL && !floor_item( obj ) )
            continue;
        if ( ring_find( st, obj_id( obj ), NULL ) != NULL )
            continue;
        ring_add( st, obj->enc_id );
        if ( kind != NULL )
        {
            obj->enc_seers++;
            enc_count.spotted++;
            obj_name( obj, name, sizeof(name) );
            snprintf( fields, sizeof(fields), "%ld\t%s\t%d\t%s\t%ld\t%d\t%s\t%s",
                      obj->enc_id, kind, obj->pIndexData->vnum, name, lain( obj ),
                      obj->enc_seers, obj->enc_source != NULL ? obj->enc_source : "-", how );
            playlog_row( "spotted", ch, fields );
        }
        else
        {
            ENC_TALLY *t = tally_get( ch, st, false, obj->pIndexData->vnum );

            if ( t != NULL )
                t->seen++;
        }
    }

    for ( rch = ch->in_room->people; rch != NULL; rch = rch->next_in_room )
    {
        const char *kind;
        ENC_TALLY *t;

        if ( rch == ch || !IS_NPC(rch) || rch->pIndexData == NULL
        ||   rch->master == ch || !can_see( ch, rch ) )
            continue;
        if ( ring_find( st, mob_id( rch ), NULL ) != NULL )
            continue;
        ring_add( st, rch->enc_id );
        enc_count.mobs_seen++;
        if ( ( t = tally_get( ch, st, true, rch->pIndexData->vnum ) ) != NULL )
            t->seen++;
        if ( ( kind = rare_kind( rch ) ) != NULL )
        {
            enc_count.rare++;
            snprintf( fields, sizeof(fields), "%s\t%d\t%ld\t%s",
                      kind, rch->pIndexData->vnum, rch->enc_id, how );
            playlog_row( "rare-seen", ch, fields );
        }
    }
}

/* ------------------------------------------------------- acting */

static void rare_acted( CHAR_DATA *ch, CHAR_DATA *mob, const char *kind,
                        const char *what, time_t *at )
{
    char fields[ENC_FIELDS];

    snprintf( fields, sizeof(fields), "%s\t%d\t%ld\t%s\t%ld",
              kind, mob->pIndexData->vnum, mob->enc_id, what,
              at != NULL ? (long) ( current_time - *at ) : -1L );
    playlog_row( "rare-acted", ch, fields );
}

/* set_fighting: a player and a mobile entering a fight, whichever side.
   Fought once per mobile per player; "attacked" when no command of the
   player's started it (an aggressive mobile, a fight joined on a tick). */
void encounter_fight( CHAR_DATA *ch, CHAR_DATA *victim )
{
    CHAR_DATA *pc, *mob;
    ENCOUNTER_STATE *st;
    ENC_TALLY *t;
    long *e;
    time_t *at = NULL;
    const char *kind;

    if ( ch == NULL || victim == NULL || IS_NPC(ch) == IS_NPC(victim) )
        return;
    pc  = IS_NPC(ch) ? victim : ch;
    mob = IS_NPC(ch) ? ch : victim;
    if ( !counted( pc ) || mob->pIndexData == NULL || mob->master == pc )
        return;
    st = state_of( pc );
    if ( ( e = ring_find( st, mob_id( mob ), &at ) ) == NULL )
    {
        e = ring_add( st, mob->enc_id );
        enc_count.mobs_seen++;
        if ( ( t = tally_get( pc, st, true, mob->pIndexData->vnum ) ) != NULL )
            t->seen++;
    }
    if ( *e & ENC_ACTED )
        return;
    *e |= ENC_ACTED;
    enc_count.mobs_fought++;
    if ( ( t = tally_get( pc, st, true, mob->pIndexData->vnum ) ) != NULL )
    {
        t->acted++;
        if ( !playlog_own_command( pc ) )
            t->attacked++;
    }
    if ( ( kind = rare_kind( mob ) ) != NULL )
        rare_acted( pc, mob, kind, playlog_own_command( pc ) ? "fought" : "attacked", at );
}

/* A rare visitor used: a purchase from the dealer (black_market_record). */
void encounter_mob_acted( CHAR_DATA *ch, CHAR_DATA *mob, const char *what )
{
    ENCOUNTER_STATE *st;
    const char *kind;
    long *e;
    time_t *at = NULL;

    if ( !counted( ch ) || mob == NULL || ( kind = rare_kind( mob ) ) == NULL )
        return;
    st = state_of( ch );
    if ( ( e = ring_find( st, mob_id( mob ), &at ) ) == NULL )
        e = ring_add( st, mob->enc_id );
    if ( *e & ENC_ACTED )
        return;
    *e |= ENC_ACTED;
    rare_acted( ch, mob, kind, what, at );
}

/* ------------------------------------------------------- a sitting */

/* playlog_session: QUIT, link loss, shutdown. What was left where they
   stand counts as passed; the tallies are written. */
void encounter_session_end( CHAR_DATA *ch, const char *how )
{
    ENCOUNTER_STATE *st;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL
    ||   ( st = ch->pcdata->encounter ) == NULL )
        return;
    if ( !is_staff( ch ) && !IS_SET( ch->act, PLR_WIZINVIS ) )
    {
        passed_check( ch, st, true, how );
        tally_flush( ch, st );
    }
    memset( st, 0, sizeof(*st) );
}

void encounter_free( CHAR_DATA *ch )
{
    if ( ch == NULL || ch->pcdata == NULL || ch->pcdata->encounter == NULL )
        return;
    free_mem( ch->pcdata->encounter, (int) sizeof(ENCOUNTER_STATE) );
    ch->pcdata->encounter = NULL;
}

/* ------------------------------------------------------- the census */

static long census_secs( void )
{
    static long secs = -1;

    if ( secs < 0 )
    {
        const char *env = getenv( "TOC_ENCOUNTER_CENSUS_SECS" );
        long v = 0;

        secs = ENC_CENSUS_SECS;
        if ( env != NULL && parse_long( env, 1, 86400, &v ) )
            secs = v;
    }
    return secs;
}

/* Once a second from update_handler; writes every census_secs() while
   anybody plays. */
void encounter_census( void )
{
    static time_t last;
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    char fields[ENC_FIELDS];
    int herbs = 0, comps = 0, eggs = 0, coin = 0, herbs_held = 0, comps_held = 0;
    int players;

    if ( last == 0 )
    {
        last = current_time;
        return;
    }
    if ( current_time - last < census_secs() )
        return;
    last = current_time;
    if ( ( players = telnet_count_players() ) < 1 )
    {
        memset( &enc_count, 0, sizeof(enc_count) );
        return;
    }

    FOR_EACH_OBJECT( iter, obj )
    {
        const char *kind = life_kind( obj );
        OBJ_DATA *top;

        if ( kind == NULL )
            continue;
        if ( obj->in_room != NULL )
        {
            if ( !strcmp( kind, "herb" ) )           herbs++;
            else if ( !strcmp( kind, "component" ) ) comps++;
            else if ( !strcmp( kind, "egg" ) )       eggs++;
            else if ( !strcmp( kind, "coin" ) )      coin++;
            continue;
        }
        for ( top = obj; top->in_obj != NULL; top = top->in_obj )
            ;
        if ( top->carried_by != NULL && !IS_NPC(top->carried_by) )
        {
            if ( !strcmp( kind, "herb" ) )
                herbs_held++;
            else if ( !strcmp( kind, "component" ) )
                comps_held++;
        }
    }

    snprintf( fields, sizeof(fields),
              "herbs=%d/%d components=%d/%d eggs=%d coin_piles=%d"
              "\therbs_held=%d components_held=%d players=%d"
              "\tlaid=%ld spotted=%ld picked=%ld passed=%ld cleared=%ld"
              " rare=%ld mobs_seen=%ld mobs_fought=%ld secs=%ld",
              herbs, HERB_CEILING, comps, COMPONENT_CEILING, eggs, coin,
              herbs_held, comps_held, players,
              enc_count.laid, enc_count.spotted, enc_count.picked, enc_count.passed,
              enc_count.cleared, enc_count.rare, enc_count.mobs_seen,
              enc_count.mobs_fought, census_secs() );
    playlog_row( "census", NULL, fields );
    memset( &enc_count, 0, sizeof(enc_count) );
}
