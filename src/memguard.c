/*
 * memguard.c -- stale pointers seen at once, logged loudly and survived
 * (owner, 2026-11-11: "Memory Safeguards" in AGENTS.md).
 *
 * Since ROM's pools went, a character, object or descriptor handed to
 * recycle.c is freed for real, and a pointer that outlives its target
 * reads freed memory. recycle.c keeps every released block whole for a
 * quarantine window, tagged MEM_DEAD_*; this file is what looks for
 * pointers to those tags:
 *
 *   - memguard_sweep(), once a second from update_handler, walks the
 *     character list, the object list, every room's people and contents,
 *     the descriptor list and the hunter list, and checks every stored
 *     pointer at a character, object or descriptor. One that points at a
 *     dead block is written to log/toc.log as
 *         MEMORY: stale <field> on <who> -> dead <kind> (<what it was>)
 *     with a nameless BUG row in the play journal and a WIZINFO (one per
 *     field a minute), counted, and repaired: see memguard_repair_*.
 *   - The hot spots that follow a long-lived pointer on a timer --
 *     violence_update's fighting, hunt_victim's hunting, the hunter list,
 *     the output loop's descriptor, do_reply's reply -- ask the same check
 *     first, so a stale pointer between sweeps is never followed.
 *   - MEMCHECK shows it all to staff.
 *
 * Whether a target is live, dead or freed is memtrack.c's answer by
 * address (char_liveness and its kin): nothing here reads a pointer to
 * learn whether it may be read. A dead block -- released, still in
 * quarantine -- is whole, and its own list link is read to unlink it. A
 * freed one (its window over, the quarantine past its cap, or an address
 * that was never ours) is never read: it is logged "-> freed", a list is
 * cut at it, and what followed the cut is found again from the other side
 * -- an object's carried_by, in_obj or in_room, a character's in_room or
 * desc -- by mg_relink. Nothing here reads a dead block's strings:
 * free_char and extract_obj have freed them. What a dead block was comes
 * from the label recycle.c wrote at its release.
 */

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200112L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"

extern ROOM_INDEX_DATA *room_index_hash[MAX_KEY_HASH];
int delete_from_hunter_list( CHAR_DATA *hunter );     /* hunt.c */

#define MG_EVENTS           5       /* MEMCHECK's newest events */
#define MG_EVENT_LEN        200
#define MG_LOG_BURST        10      /* log lines a field a minute; the rest counted */
#define MG_LIST_STEPS       200000  /* a list longer than this is a loop */

/* Every field the sweep and the hot spots check, by name. A quiet one is
   compared by pointer only and goes stale by design -- a resurrection
   offer's corpse rots, a descriptor remembers the body it last sent GMCP
   for -- so it is cleared and counted, not reported. */
static const struct
{
    const char *name;
    bool        quiet;
} mg_fields[] =
{
    { "fighting",           FALSE },
    { "master",             FALSE },
    { "leader",             FALSE },
    { "pet",                FALSE },
    { "hunting",            FALSE },
    { "reply",              FALSE },
    { "questgiver",         FALSE },
    { "desc",               FALSE },
    { "in_object",          FALSE },
    { "carrying",           FALSE },
    { "stash",              FALSE },
    { "resurrect_corpse",   FALSE },   /* cleared at extraction since 2026-11-11 */
    { "character_list",     FALSE },
    { "object_list",        FALSE },
    { "carried_by",         FALSE },
    { "in_obj",             FALSE },
    { "trapped",            FALSE },
    { "contains",           FALSE },
    { "room people",        FALSE },
    { "room contents",      FALSE },
    { "d character",        FALSE },
    { "d original",         FALSE },
    { "d snoop_by",         FALSE },
    { "d gmcp_last_character", FALSE },
    { "descriptor_list",    FALSE },
    { "hunter_list",        FALSE },
};
#define MG_FIELDS ( (int) ( sizeof(mg_fields) / sizeof(mg_fields[0]) ) )

static long     mg_caught[MG_FIELDS];
static long     mg_total;
static long     mg_freed_total;     /* of mg_total, found already freed */
static long     mg_relinked;        /* found again after a list was cut */

static void     mg_selftest_retire  ( void );

/*
 * Lists cut at a freed block this sweep, so mg_relink can put back what
 * followed. Past MG_CUTS every holder is checked.
 */
#define MG_CUTS             32
#define MG_CUT_CARRYING     1
#define MG_CUT_CONTAINS     2
#define MG_CUT_CONTENTS     3
#define MG_CUT_PEOPLE       4
#define MG_CUT_STASH        5
static struct
{
    int         type;
    const void *holder;
} mg_cuts[MG_CUTS];
static int      mg_cut_count;
static bool     mg_cut_overflow;
static bool     mg_desc_cut;
static time_t   mg_wizinfo_at[MG_FIELDS];
static time_t   mg_log_minute[MG_FIELDS];
static int      mg_log_count[MG_FIELDS];
static long     mg_log_suppressed[MG_FIELDS];
static char     mg_events[MG_EVENTS][MG_EVENT_LEN];
static int      mg_event_level[MG_EVENTS];  /* who may read it: every name in it */
static int      mg_event_next;

static long     mg_runs;
static double   mg_last_ms;
static double   mg_max_ms;
static double   mg_sum_ms;
static int      mg_seen_chars;
static int      mg_seen_players;
static int      mg_seen_objs;
static int      mg_seen_descs;
static long     mg_seen_ptrs;


static int mg_field( const char *name )
{
    int i;

    for ( i = 0; i < MG_FIELDS; i++ )
        if ( !strcmp( mg_fields[i].name, name ) )
            return i;
    return 0;
}

static double mg_now_ms( void )
{
    struct timespec ts;

    clock_gettime( CLOCK_MONOTONIC, &ts );
    return (double) ts.tv_sec * 1000.0 + (double) ts.tv_nsec / 1.0e6;
}

/* Who holds a pointer: a live character, read safely. */
static void mg_char_label( const CHAR_DATA *ch, char *out, size_t size )
{
    if ( ch == NULL )
        toc_strlcpy( out, "nobody", size );
    else if ( IS_NPC(ch) && ch->pIndexData != NULL )
        snprintf( out, size, "mob %d %s", ch->pIndexData->vnum,
                  ch->short_descr != NULL ? ch->short_descr : "?" );
    else
        snprintf( out, size, "%s", ch->name != NULL ? ch->name : "?" );
}

static void mg_obj_label( const OBJ_DATA *obj, char *out, size_t size )
{
    if ( obj->pIndexData != NULL )
        snprintf( out, size, "obj %d %s", obj->pIndexData->vnum,
                  obj->pIndexData->short_descr != NULL
                      ? obj->pIndexData->short_descr : "?" );
    else
        toc_strlcpy( out, "an object", size );
}

/* A staff notice naming a player goes out at their notice level. */
static int mg_notice_level( const CHAR_DATA *holder )
{
    if ( holder != NULL && !IS_NPC(holder) )
        return staff_notice_level( holder, LEVEL_IMMORTAL );
    return LEVEL_IMMORTAL;
}

/* What memtrack says of a target, by the kind the field holds. */
static int mg_liveness( const void *target, const char *kind )
{
    if ( !strcmp( kind, "object" ) )
        return obj_liveness( target );
    if ( !strcmp( kind, "descriptor" ) )
        return desc_liveness( target );
    return char_liveness( target );
}

/*
 * One stale pointer: counted always; logged (MG_LOG_BURST a field a
 * minute, the rest counted and said with the next line); a nameless BUG
 * row in the play journal; a WIZINFO once a field a minute; and kept for
 * MEMCHECK. "dead" when the target is still in quarantine and its label
 * names it; "freed" when it is not, and was not read. The caller repairs.
 */
static void mg_report( const char *field, const char *who, int level,
                       const void *target, const char *kind )
{
    char label[80];
    char line[MAX_STRING_LENGTH];
    int f = mg_field( field );
    int target_level;
    bool freed = mg_liveness( target, kind ) == MEM_STATE_FREED;
    const char *state = freed ? "freed" : "dead";

    mg_caught[f]++;
    if ( mg_fields[f].quiet )
        return;
    mg_total++;
    if ( freed )
        mg_freed_total++;

    /* The event names the holder and the dead target: it is for staff who
       could see both (a wizinvis name is for its own level and up). */
    recycle_dead_label( target, label, sizeof(label), &target_level );
    level = UMAX( level, target_level );
    if ( freed )
        /* Out of quarantine, or never ours: nothing is known of it, and it
           was not read to find out. */
        snprintf( line, sizeof(line),
                  "MEMORY: stale %s on %s -> freed %s (gone from quarantine; not read)",
                  field, who, kind );
    else
        snprintf( line, sizeof(line), "MEMORY: stale %s on %s -> dead %s (%s)",
                  field, who, kind, label );
    snprintf( mg_events[mg_event_next], MG_EVENT_LEN, "%.24s %.170s",
              ctime( &current_time ), line );
    mg_event_level[mg_event_next] = level;
    mg_event_next = ( mg_event_next + 1 ) % MG_EVENTS;

    if ( current_time - mg_log_minute[f] >= 60 )
    {
        if ( mg_log_suppressed[f] > 0 )
        {
            char more[MAX_INPUT_LENGTH];

            snprintf( more, sizeof(more),
                      "MEMORY: %ld more stale %s not logged in the last minute",
                      mg_log_suppressed[f], field );
            log_string( more );
        }
        mg_log_minute[f]     = current_time;
        mg_log_count[f]      = 0;
        mg_log_suppressed[f] = 0;
    }
    if ( mg_log_count[f] < MG_LOG_BURST )
    {
        char journal[MAX_INPUT_LENGTH];

        mg_log_count[f]++;
        log_string( line );
        /* The journal is published and keeps the wizinvis out: no names. */
        snprintf( journal, sizeof(journal),
                  "MEMORY: stale %s -> %s %s, repaired", field, state, kind );
        playlog_bug( journal );
    }
    else
        mg_log_suppressed[f]++;

    if ( current_time - mg_wizinfo_at[f] >= 60 )
    {
        char notice[MAX_STRING_LENGTH];

        mg_wizinfo_at[f] = current_time;
        snprintf( notice, sizeof(notice),
                  "MEMORY: stale %s on %s -> %s %s; repaired (MEMCHECK, log/toc.log)",
                  field, who, state, kind );
        wizinfo( notice, level );
    }
}

static void mg_report_char( const char *field, CHAR_DATA *holder,
                            const void *target, const char *kind )
{
    char who[MAX_INPUT_LENGTH];

    mg_char_label( holder, who, sizeof(who) );
    mg_report( field, who, mg_notice_level( holder ), target, kind );
}

static void mg_report_obj( const char *field, OBJ_DATA *holder,
                           const void *target, const char *kind )
{
    char who[MAX_INPUT_LENGTH];

    mg_obj_label( holder, who, sizeof(who) );
    mg_report( field, who, LEVEL_IMMORTAL, target, kind );
}

/* ------------------------------------------------------------ repairs */

/*
 * fighting: cleared first, then stop_fighting resets the position --
 * stop_fighting itself would read the dead opponent's room and write its
 * battle ticks, so it never sees the pointer.
 */
bool memguard_fighting_ok( CHAR_DATA *ch )
{
    if ( ch == NULL || char_is_live( ch->fighting ) )
        return TRUE;
    mg_report_char( "fighting", ch, ch->fighting, "character" );
    ch->fighting = NULL;
    stop_fighting( ch, FALSE );
    return FALSE;
}

/*
 * hunting: out of the hunter list and cleared. Not do_stop_hunting, whose
 * notice reads the prey's name, a freed string once the prey is dead.
 */
bool memguard_hunting_ok( CHAR_DATA *ch )
{
    if ( ch == NULL || char_is_live( ch->hunting ) )
        return TRUE;
    mg_report_char( "hunting", ch, ch->hunting, "character" );
    delete_from_hunter_list( ch );
    ch->hunting = NULL;
    return FALSE;
}

/* A hunter-list slot naming a dead hunter is emptied, never followed. */
bool memguard_hunter_slot_ok( int slot )
{
    CHAR_DATA *hunter;

    if ( slot < 0 || slot >= MAX_HUNTERS )
        return FALSE;
    hunter = hunter_list[slot].ch;
    if ( char_is_live( hunter ) )
        return TRUE;
    mg_report( "hunter_list", "the hunter list", LEVEL_IMMORTAL, hunter, "character" );
    hunter_list[slot].ch     = NULL;
    hunter_list[slot].status = 0;
    return FALSE;
}

bool memguard_reply_ok( CHAR_DATA *ch )
{
    if ( ch == NULL || char_is_live( ch->reply ) )
        return TRUE;
    mg_report_char( "reply", ch, ch->reply, "character" );
    ch->reply = NULL;
    return FALSE;
}

/*
 * A descriptor's pointers. A dead snoop_by or original is cleared. A dead
 * character is the one that matters: a switched player goes back into
 * their own body when that is alive; otherwise the connection is marked
 * write_failed and the output loop closes it -- there is nothing left to
 * save, and a connection with no character cannot be played. Returns
 * false when the descriptor is to be closed.
 */
bool memguard_descriptor_ok( DESCRIPTOR_DATA *d )
{
    char who[MAX_INPUT_LENGTH];

    if ( d == NULL )
        return TRUE;
    snprintf( who, sizeof(who), "descriptor %d", d->descriptor );

    if ( !desc_is_live( d->snoop_by ) )
    {
        mg_report( "d snoop_by", who, LEVEL_IMMORTAL, d->snoop_by, "descriptor" );
        d->snoop_by = NULL;
    }
    if ( !char_is_live( d->gmcp_last_character ) )
    {
        mg_report( "d gmcp_last_character", who, LEVEL_IMMORTAL,
                   d->gmcp_last_character, "character" );
        d->gmcp_last_character = NULL;
    }
    if ( !char_is_live( d->original ) )
    {
        mg_report( "d original", who, LEVEL_IMMORTAL, d->original, "character" );
        d->original = NULL;
    }
    if ( !char_is_live( d->character ) )
    {
        mg_report( "d character", who, LEVEL_IMMORTAL, d->character, "character" );
        d->character = NULL;
        if ( d->original != NULL )
        {
            d->character        = d->original;
            d->original         = NULL;
            d->character->desc  = d;
            send_to_char( "The body you were in is gone; you return to your own.\n\r",
                          d->character );
            return TRUE;
        }
        d->write_failed = TRUE;
        return FALSE;
    }
    return TRUE;
}

/*
 * An object whose holder is dead is in no live list: it is put on the
 * floor of Limbo (staff can fetch it; the log line names it) rather than
 * extracted, because it may well be a player's.
 */
static void mg_rehome_obj( OBJ_DATA *obj )
{
    ROOM_INDEX_DATA *limbo = get_room_index( ROOM_VNUM_LIMBO );

    obj->carried_by   = NULL;
    obj->in_obj       = NULL;
    obj->next_content = NULL;
    obj->wear_loc     = WEAR_NONE;
    if ( limbo != NULL )
        obj_to_room( obj, limbo );
}

/* A list cut at a freed block: remembered so mg_relink can look for what
   followed the cut. */
static void mg_note_cut( int type, const void *holder )
{
    if ( mg_cut_count < MG_CUTS )
    {
        mg_cuts[mg_cut_count].type   = type;
        mg_cuts[mg_cut_count].holder = holder;
        mg_cut_count++;
    }
    else
        mg_cut_overflow = TRUE;
}

static bool mg_was_cut( int type, const void *holder )
{
    int i;

    if ( holder == NULL )
        return FALSE;
    if ( mg_cut_overflow )
        return TRUE;
    for ( i = 0; i < mg_cut_count; i++ )
        if ( mg_cuts[i].type == type && mg_cuts[i].holder == holder )
            return TRUE;
    return FALSE;
}

/*
 * Unlink dead objects from a next_content list, reading the dead block's
 * own link, which quarantine keeps whole. A freed block's link cannot be
 * read: the list is cut there, and mg_relink puts back what followed.
 */
static void mg_obj_list( OBJ_DATA **head, const char *field, int cut_type,
                         const void *holder, CHAR_DATA *char_holder,
                         OBJ_DATA *obj_holder, const char *room_holder )
{
    OBJ_DATA **link = head;
    long steps = 0;

    while ( *link != NULL && steps++ < MG_LIST_STEPS )
    {
        OBJ_DATA *obj = *link;
        int state = obj_liveness( obj );

        mg_seen_ptrs++;
        if ( state == MEM_STATE_LIVE )
        {
            link = &obj->next_content;
            continue;
        }
        if ( char_holder != NULL )
            mg_report_char( field, char_holder, obj, "object" );
        else if ( obj_holder != NULL )
            mg_report_obj( field, obj_holder, obj, "object" );
        else
            mg_report( field, room_holder, LEVEL_IMMORTAL, obj, "object" );
        if ( state == MEM_STATE_DEAD )
            *link = obj->next_content;
        else
        {
            *link = NULL;
            mg_note_cut( cut_type, holder );
        }
    }
}

static void mg_char_room_list( ROOM_INDEX_DATA *room )
{
    CHAR_DATA **link = &room->people;
    long steps = 0;
    char who[64];

    while ( *link != NULL && steps++ < MG_LIST_STEPS )
    {
        CHAR_DATA *rch = *link;
        int state = char_liveness( rch );

        mg_seen_ptrs++;
        if ( state == MEM_STATE_LIVE )
        {
            link = &rch->next_in_room;
            continue;
        }
        snprintf( who, sizeof(who), "room %d", room->vnum );
        mg_report( "room people", who, LEVEL_IMMORTAL, rch, "character" );
        if ( state == MEM_STATE_DEAD )
            *link = rch->next_in_room;
        else
        {
            *link = NULL;
            mg_note_cut( MG_CUT_PEOPLE, room );
        }
    }
}

static bool mg_obj_listed( const OBJ_DATA *list, const OBJ_DATA *obj )
{
    long steps = 0;

    for ( ; list != NULL && steps++ < MG_LIST_STEPS; list = list->next_content )
        if ( list == obj )
            return TRUE;
    return FALSE;
}

/*
 * After a list was cut at a freed block, whatever followed the cut is
 * found again from its own side: a live object's carried_by, in_obj or
 * in_room names the list it belongs in, a live character's in_room its
 * room's people, a live character's desc the descriptor list. Each is put
 * back at the front of its list if it is missing. A stash keeps no owner
 * on its objects, so what followed a cut there is not found: the line says
 * so, and PRESTORE STASH is the way back.
 */
static void mg_relink( void )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    CHAR_DATA *ch;
    long objs = 0;
    long chars = 0;
    long descs = 0;
    bool stash_cut = FALSE;
    int i;

    for ( i = 0; i < mg_cut_count; i++ )
        if ( mg_cuts[i].type == MG_CUT_STASH )
            stash_cut = TRUE;

    FOR_EACH_OBJECT( iter, obj )
    {
        OBJ_DATA **head = NULL;

        if ( !obj_is_live( obj ) )
            continue;
        if ( obj->carried_by != NULL )
        {
            if ( mg_was_cut( MG_CUT_CARRYING, obj->carried_by )
            &&   char_is_live( obj->carried_by ) )
                head = &obj->carried_by->carrying;
        }
        else if ( obj->in_obj != NULL )
        {
            if ( mg_was_cut( MG_CUT_CONTAINS, obj->in_obj ) && obj_is_live( obj->in_obj ) )
                head = &obj->in_obj->contains;
        }
        else if ( obj->in_room != NULL && mg_was_cut( MG_CUT_CONTENTS, obj->in_room ) )
            head = &obj->in_room->contents;
        if ( head == NULL || mg_obj_listed( *head, obj ) )
            continue;
        obj->next_content = *head;
        *head = obj;
        objs++;
    }

    FOR_EACH_CHARACTER( iter, ch )
    {
        if ( !char_is_live( ch ) )
            continue;
        if ( ch->in_room != NULL && mg_was_cut( MG_CUT_PEOPLE, ch->in_room ) )
        {
            CHAR_DATA *rch;
            long steps = 0;

            for ( rch = ch->in_room->people; rch != NULL && rch != ch
                  && steps++ < MG_LIST_STEPS; rch = rch->next_in_room )
                ;
            if ( rch != ch )
            {
                ch->next_in_room   = ch->in_room->people;
                ch->in_room->people = ch;
                chars++;
            }
        }
        if ( mg_desc_cut && ch->desc != NULL && desc_is_live( ch->desc ) )
        {
            DESCRIPTOR_DATA *d;
            long steps = 0;

            for ( d = descriptor_list; d != NULL && d != ch->desc
                  && steps++ < MG_LIST_STEPS; d = d->next )
                ;
            if ( d != ch->desc )
            {
                ch->desc->next  = descriptor_list;
                descriptor_list = ch->desc;
                descs++;
            }
        }
    }

    mg_relinked += objs + chars + descs;
    {
        char line[MAX_STRING_LENGTH];

        snprintf( line, sizeof(line),
                  "MEMORY: a list was cut at a freed block; found again %ld object%s, "
                  "%ld character%s, %ld descriptor%s%s",
                  objs, objs == 1 ? "" : "s", chars, chars == 1 ? "" : "s",
                  descs, descs == 1 ? "" : "s",
                  stash_cut ? "; a stash's objects past the cut are lost to it (PRESTORE STASH)"
                            : "" );
        log_string( line );
    }
}

/* Every pointer a live character holds. */
static void mg_check_char( CHAR_DATA *ch )
{
    mg_seen_ptrs += 10;
    memguard_fighting_ok( ch );
    memguard_hunting_ok( ch );
    memguard_reply_ok( ch );

    if ( !char_is_live( ch->master ) )
    {
        mg_report_char( "master", ch, ch->master, "character" );
        ch->master = NULL;
        if ( IS_NPC(ch) )
            ch->ridden = FALSE;
        if ( IS_AFFECTED(ch, AFF_CHARM) )
        {
            REMOVE_BIT( ch->affected_by, AFF_CHARM );
            affect_strip( ch, gsn_charm_person );
        }
    }
    if ( !char_is_live( ch->leader ) )
    {
        mg_report_char( "leader", ch, ch->leader, "character" );
        ch->leader = NULL;
    }
    if ( !char_is_live( ch->pet ) )
    {
        mg_report_char( "pet", ch, ch->pet, "character" );
        ch->pet = NULL;
        if ( !IS_NPC(ch) && ch->pcdata != NULL )
            ch->pcdata->mounted = FALSE;
    }
    if ( !char_is_live( ch->questgiver ) )
    {
        mg_report_char( "questgiver", ch, ch->questgiver, "character" );
        ch->questgiver = NULL;
    }
    if ( !desc_is_live( ch->desc ) )
    {
        /* Its connection is gone: the character is link-dead. */
        mg_report_char( "desc", ch, ch->desc, "descriptor" );
        ch->desc = NULL;
    }

    mg_obj_list( &ch->carrying, "carrying", MG_CUT_CARRYING, ch, ch, NULL, NULL );
    if ( !IS_NPC(ch) && ch->pcdata != NULL )
    {
        mg_obj_list( &ch->pcdata->stash, "stash", MG_CUT_STASH, ch, ch, NULL, NULL );
        if ( !obj_is_live( ch->pcdata->resurrect_corpse ) )
        {
            mg_report_char( "resurrect_corpse", ch,
                            ch->pcdata->resurrect_corpse, "object" );
            ch->pcdata->resurrect_corpse = NULL;
        }
    }

    /* Last, since it may extract: a mobile shut in a bottle that is gone
       goes with it, as char_from_obj does; a player is set down at the
       altar, as extract_char does. */
    if ( !obj_is_live( ch->in_object ) )
    {
        mg_report_char( "in_object", ch, ch->in_object, "object" );
        ch->in_object = NULL;
        if ( ch->in_room == NULL )
        {
            if ( IS_NPC(ch) )
            {
                char_to_room( ch, get_room_index( ROOM_VNUM_LIMBO ) );
                extract_char( ch, TRUE );
            }
            else
                char_to_room( ch, get_room_index( ROOM_VNUM_ALTAR ) );
        }
    }
}

static void mg_check_obj( OBJ_DATA *obj )
{
    mg_seen_ptrs += 3;
    if ( !char_is_live( obj->trapped ) )
    {
        mg_report_obj( "trapped", obj, obj->trapped, "character" );
        obj->trapped = NULL;
    }
    mg_obj_list( &obj->contains, "contains", MG_CUT_CONTAINS, obj, NULL, obj, NULL );
    if ( !char_is_live( obj->carried_by ) )
    {
        mg_report_obj( "carried_by", obj, obj->carried_by, "character" );
        mg_rehome_obj( obj );
    }
    else if ( !obj_is_live( obj->in_obj ) )
    {
        mg_report_obj( "in_obj", obj, obj->in_obj, "object" );
        mg_rehome_obj( obj );
    }
}

/*
 * Once a second. Cheap: a few reads per character, object, room and
 * descriptor; MEMCHECK shows what it costs.
 */
void memguard_sweep( void )
{
    LIST_ITERATOR iter;
    CHAR_DATA *ch;
    OBJ_DATA *obj;
    DESCRIPTOR_DATA **dlink;
    double started = mg_now_ms( );
    double took;
    int i;

    mg_seen_chars = mg_seen_players = mg_seen_objs = mg_seen_descs = 0;
    mg_seen_ptrs  = 0;
    mg_cut_count    = 0;
    mg_cut_overflow = FALSE;
    mg_desc_cut     = FALSE;

    FOR_EACH_CHARACTER( iter, ch )
    {
        if ( !char_is_live( ch ) )
        {
            mg_report( "character_list", "the character list", LEVEL_IMMORTAL,
                       ch, "character" );
            unregister_character( ch );
            continue;
        }
        mg_seen_chars++;
        if ( !IS_NPC(ch) )
            mg_seen_players++;
        mg_check_char( ch );
    }

    FOR_EACH_OBJECT( iter, obj )
    {
        if ( !obj_is_live( obj ) )
        {
            mg_report( "object_list", "the object list", LEVEL_IMMORTAL,
                       obj, "object" );
            unregister_object( obj );
            continue;
        }
        mg_seen_objs++;
        mg_check_obj( obj );
    }

    for ( i = 0; i < MAX_KEY_HASH; i++ )
    {
        ROOM_INDEX_DATA *room;

        for ( room = room_index_hash[i]; room != NULL; room = room->next )
        {
            char who[64];

            mg_char_room_list( room );
            if ( room->contents != NULL )
            {
                snprintf( who, sizeof(who), "room %d", room->vnum );
                mg_obj_list( &room->contents, "room contents", MG_CUT_CONTENTS,
                             room, NULL, NULL, who );
            }
        }
    }

    for ( dlink = &descriptor_list; *dlink != NULL; )
    {
        DESCRIPTOR_DATA *d = *dlink;
        int state = desc_liveness( d );

        if ( state != MEM_STATE_LIVE )
        {
            mg_report( "descriptor_list", "the descriptor list", LEVEL_IMMORTAL,
                       d, "descriptor" );
            if ( state == MEM_STATE_DEAD )
                *dlink = d->next;
            else
            {
                /* Cut: mg_relink finds the rest through their characters. */
                *dlink = NULL;
                mg_desc_cut = TRUE;
            }
            continue;
        }
        mg_seen_descs++;
        mg_seen_ptrs += 4;
        memguard_descriptor_ok( d );
        dlink = &d->next;
    }

    for ( i = 0; i < MAX_HUNTERS; i++ )
        if ( hunter_list[i].ch != NULL )
            memguard_hunter_slot_ok( i );

    if ( mg_cut_count > 0 || mg_cut_overflow || mg_desc_cut )
        mg_relink( );
    mg_selftest_retire( );

    took = mg_now_ms( ) - started;
    mg_runs++;
    mg_last_ms = took;
    mg_sum_ms += took;
    if ( took > mg_max_ms )
        mg_max_ms = took;
}

/* ------------------------------------------------------------ MEMCHECK */

/*
 * The self-test (TOC_MEMCHECK_SELFTEST=1 only): a mobile made and retired
 * straight through recycle.c, as a bug would leave it -- no extract_char,
 * so nothing clears the pointer -- with the caller's reply aimed at it.
 * It is retired at the end of the next sweep (mg_selftest_retire), so the
 * sweep after that is the first to see it, and always across at least one
 * recycle_flush: inside the quarantine window the catch reads "dead", with
 * no window (TOC_MEM_QUARANTINE_SECS=0) "freed", never read.
 */
static CHAR_DATA *mg_selftest_mob;

static void mg_selftest_retire( void )
{
    CHAR_DATA *mob = mg_selftest_mob;

    if ( mob == NULL )
        return;
    mg_selftest_mob = NULL;
    recycle_label_char( mob );
    char_data_release( mob );
}

static void memcheck_selftest( CHAR_DATA *ch )
{
    const char *env = getenv( "TOC_MEMCHECK_SELFTEST" );
    MOB_INDEX_DATA *pMob = NULL;
    CHAR_DATA *mob;
    char buf[MAX_STRING_LENGTH];
    int vnum;

    if ( env == NULL || strcmp( env, "1" ) )
    {
        send_to_char( "The self-test runs only in a test world (TOC_MEMCHECK_SELFTEST=1).\n\r", ch );
        return;
    }
    /* Any ordinary mobile: the first prototype with no special. */
    for ( vnum = 1; vnum <= top_vnum_mob && pMob == NULL; vnum++ )
        if ( ( pMob = get_mob_index( vnum ) ) != NULL && pMob->spec_fun != NULL )
            pMob = NULL;
    if ( pMob == NULL )
    {
        send_to_char( "The self-test found no mobile to retire.\n\r", ch );
        return;
    }
    if ( mg_selftest_mob != NULL )
    {
        send_to_char( "A self-test is already waiting for the sweep.\n\r", ch );
        return;
    }
    /* Out of every list, in no room: only the caller's reply names it. */
    mob = create_mobile( pMob );
    unregister_character( mob );
    --pMob->count;
    mobile_count--;
    mg_selftest_mob = mob;
    ch->reply = mob;
    snprintf( buf, sizeof(buf),
              "Self-test: your reply now points at a mobile (vnum %d) the next sweep "
              "retires; the sweep after must catch it.\n\r", pMob->vnum );
    send_to_char( buf, ch );
}

void do_memcheck( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    int held, window, cap, i, shown;
    long oldest, freed, tracked_live, tracked_dead;

    one_argument( argument, arg );
    if ( !str_cmp( arg, "selftest" ) )
    {
        memcheck_selftest( ch );
        return;
    }
    if ( arg[0] != '\0' )
    {
        send_to_char( "Syntax: memcheck\n\r", ch );
        return;
    }

    recycle_stats( &held, &oldest, &freed, &window, &cap );
    send_to_char( "Memory safeguards (recycle.c, memguard.c):\n\r", ch );
    snprintf( buf, sizeof(buf),
              "  Quarantine: %d blocks held, oldest %lds; window %ds, cap %d; %ld freed since boot.\n\r",
              held, oldest, window, cap, freed );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf),
              "  Live: %d characters (%d players), %d objects, %d descriptors.\n\r",
              mg_seen_chars, mg_seen_players, mg_seen_objs, mg_seen_descs );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf),
              "  Sweep: %ld runs; last %.3f ms, slowest %.3f ms, average %.3f ms; %ld pointers last run.\n\r",
              mg_runs, mg_last_ms, mg_max_ms,
              mg_runs > 0 ? mg_sum_ms / (double) mg_runs : 0.0, mg_seen_ptrs );
    send_to_char( buf, ch );
    recycle_tracked( &tracked_live, &tracked_dead );
    snprintf( buf, sizeof(buf),
              "  Tracked by address: %ld live, %ld in quarantine. A pointer to neither is\n\r"
              "  taken as freed and never read; one to an address reused by the same\n\r"
              "  kind reads as live and is not caught.\n\r",
              tracked_live, tracked_dead );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf), "  Stale pointers caught since boot: %ld.\n\r", mg_total );
    send_to_char( buf, ch );
    if ( mg_freed_total > 0 || mg_relinked > 0 )
    {
        snprintf( buf, sizeof(buf),
                  "    of them already freed: %ld; found again after a cut list: %ld.\n\r",
                  mg_freed_total, mg_relinked );
        send_to_char( buf, ch );
    }
    for ( i = 0, shown = 0; i < MG_FIELDS; i++ )
    {
        if ( mg_caught[i] == 0 )
            continue;
        snprintf( buf, sizeof(buf), "    %-22s %ld%s\n\r", mg_fields[i].name,
                  mg_caught[i], mg_fields[i].quiet ? " (expected; cleared quietly)" : "" );
        send_to_char( buf, ch );
        shown++;
    }
    if ( shown == 0 )
        send_to_char( "    (none)\n\r", ch );
    send_to_char( "  Last events:\n\r", ch );
    for ( i = 0, shown = 0; i < MG_EVENTS; i++ )
    {
        int slot = ( mg_event_next + MG_EVENTS - 1 - i ) % MG_EVENTS;
        const char *event = mg_events[slot];

        /* Never a name the viewer could not see (review, 2026-11-11). */
        if ( event[0] == '\0' || get_trust( ch ) < mg_event_level[slot] )
            continue;
        snprintf( buf, sizeof(buf), "    %s\n\r", event );
        send_to_char( buf, ch );
        shown++;
    }
    if ( shown == 0 )
        send_to_char( "    (none)\n\r", ch );
}
