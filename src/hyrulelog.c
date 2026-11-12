/*
 * log/hyrule.tsv -- Hyrule play, written down for balance and trends
 * (owner, 2026-11-10: "I'd like hyrule play logged heavily so we can
 * balance/improve it and gain trends").
 *
 * The play journal (log/play.tsv) says what a player typed and what the
 * game answered; this says what that meant in Hyrule: which part of it
 * they were in and for how long, which gate turned them back and for
 * want of what, which seal they opened, what they came away with, which
 * one-time claim they took, and every guardian fight -- who came, at what
 * level and health, how long it lasted, and how it ended (the guardian's
 * health when somebody fled or died is the number that sizes a guardian).
 *
 * One row an event, tab-separated:
 *
 *   epoch  kind  name  level  remorts  class  room  zone  fields...
 *
 * zone is "over" (the overworld), "L1".."L9" (a dungeon) or "out"; the
 * fields are key=value words, so a reader can take what it knows and
 * skip the rest, and a later field never moves an earlier one. Kinds:
 * enter, leave, gate, seal, got, claim, engage, guardian-down, flee,
 * death, cleared. tools/log_report.py reads them.
 *
 * Mortals only: staff testing would skew every number, and wizinvis
 * staff leave no trace in any journal. Like the play journal it names
 * players -- log/ is public, and so are their names on WHO -- and never
 * says a thing anybody said. Trimmed past HYLOG_MAX lines to the newest
 * HYLOG_KEEP.
 */
#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "merc.h"

#define HYLOG_FILE      "../log/hyrule.tsv"
#define HYLOG_MAX       40000
#define HYLOG_KEEP      20000

/* Appended a whole row at a time and trimmed as the play journal is
   (telemetry_append, playlog.c). */
static TELEMETRY_LOG hylog_log =
    TELEMETRY_LOG_INIT( HYLOG_FILE, HYLOG_MAX, HYLOG_KEEP, false );
static bool hylog_busy;

/* 0 outside Hyrule, 1 the overworld, 2-10 the dungeons 1-9, by the room
   ranges of hyrule_progress_gate (act_move.c), which the maps read too. */
static int hylog_zone_of( ROOM_INDEX_DATA *room )
{
    const HYRULE_DUNGEON_GATE *gate;
    int level;

    if ( room == NULL || !IS_HYRULE_ROOM_VNUM( room->vnum ) )
        return 0;
    for ( level = 1; level <= 9; level++ )
        if ( ( gate = hyrule_dungeon_gate( level ) ) != NULL
        &&   room->vnum >= gate->first_room && room->vnum <= gate->last_room )
            return level + 1;
    return 1;
}

static const char *zone_name( int zone )
{
    static const char *const names[] =
        { "out", "over", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9" };

    return zone >= 0 && zone <= 10 ? names[zone] : "?";
}

static bool hylog_counts( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && !IS_SET( ch->act, PLR_WIZINVIS )
        && !IS_TRUSTED( ch, LEVEL_IMMORTAL );
}

/* A pet or a charmed follower's deed is its master's. */
static CHAR_DATA *hylog_actor( CHAR_DATA *ch )
{
    if ( ch != NULL && IS_NPC(ch) && ch->master != NULL && !IS_NPC(ch->master) )
        return ch->master;
    return ch;
}

static int pct( long now, long max )
{
    return max > 0 ? (int) ( 100L * now / max ) : 0;
}

/* Tabs and line ends out of anything copied in (an object's name). */
static void hylog_clean( char *dest, size_t size, const char *src )
{
    size_t n = 0;

    if ( src == NULL )
        src = "-";
    for ( ; *src != '\0' && n + 1 < size; src++ )
    {
        unsigned char c = (unsigned char) *src;

        if ( c == '{' && src[1] != '\0' && src[2] != '\0' )
        {
            src += 2;       /* a colour token */
            continue;
        }
        dest[n++] = (char) ( c < ' ' || c == 127 || c == ' ' ? '_' : c );
    }
    dest[n] = '\0';
}

static void hylog_write( const char *kind, CHAR_DATA *ch, ROOM_INDEX_DATA *room,
                         const char *fields )
{
    /* The fields are at most HYLOG_GUARDIAN_FIELDS (672) bytes (the
       writers' buffers) and the common columns under 150: a row that
       would not fit is refused whole. */
    char row[1024], name[32];
    int zone, n;

    if ( hylog_busy || !hylog_counts( ch ) )
        return;
    hylog_busy = true;
    if ( room == NULL )
        room = ch->in_room;
    zone = hylog_zone_of( room );
    hylog_clean( name, sizeof(name), ch->name );
    n = snprintf( row, sizeof(row), "%ld\t%s\t%s\t%d\t%d\t%s\t%d\t%s\t%s\n",
                  (long) current_time, kind, name, ch->level,
                  ch->pcdata->num_remorts,
                  ch->class >= 0 && ch->class < MAX_CLASS
                      ? class_table[ch->class].who_name : "?",
                  room != NULL && !room_hides_from_log( room ) ? room->vnum : 0,
                  zone_name( zone ), fields );
    telemetry_append( &hylog_log, row, n, sizeof(row) );
    hylog_busy = false;
}

/* The buffs that decide a guardian fight, as letters: T titanic,
   E empower, S sanctuary, H haste (the same as log/progress.tsv). */
static const char *hylog_buffs( CHAR_DATA *ch )
{
    static char buffs[8];
    int n = 0;

    if ( is_affected( ch, gsn_titanic ) ) buffs[n++] = 'T';
    if ( is_affected( ch, gsn_empower ) ) buffs[n++] = 'E';
    if ( IS_AFFECTED( ch, AFF_SANCTUARY ) ) buffs[n++] = 'S';
    if ( IS_AFFECTED( ch, AFF_HASTE ) ) buffs[n++] = 'H';
    if ( n == 0 )
        buffs[n++] = '-';
    buffs[n] = '\0';
    return buffs;
}

/* Every mortal in the guardian's room, as "party=N levels=32,30
   classes=Cle,War hps=80,41 buffs=SH,-". */
static void hylog_party( CHAR_DATA *guardian, char *out, size_t size )
{
    char levels[96] = "", classes[96] = "", hps[96] = "", buffs[96] = "";
    char one[24];
    CHAR_DATA *rch;
    int party = 0;

    if ( guardian->in_room != NULL )
        for ( rch = guardian->in_room->people; rch != NULL; rch = rch->next_in_room )
        {
            if ( IS_NPC(rch) || IS_TRUSTED( rch, LEVEL_IMMORTAL ) )
                continue;
            party++;
            snprintf( one, sizeof(one), "%s%d", party > 1 ? "," : "", rch->level );
            toc_strlcat( levels, one, sizeof(levels) );
            snprintf( one, sizeof(one), "%s%s", party > 1 ? "," : "",
                      rch->class >= 0 && rch->class < MAX_CLASS
                          ? class_table[rch->class].who_name : "?" );
            toc_strlcat( classes, one, sizeof(classes) );
            snprintf( one, sizeof(one), "%s%d", party > 1 ? "," : "",
                      pct( rch->hit, rch->max_hit ) );
            toc_strlcat( hps, one, sizeof(hps) );
            snprintf( one, sizeof(one), "%s%s", party > 1 ? "," : "", hylog_buffs( rch ) );
            toc_strlcat( buffs, one, sizeof(buffs) );
        }
    snprintf( out, size, "party=%d levels=%s classes=%s hps=%s buffs=%s",
              party, party ? levels : "-", party ? classes : "-",
              party ? hps : "-", party ? buffs : "-" );
}

static long fight_secs( CHAR_DATA *mob )
{
    return mob != NULL && mob->fight_began_ms > 0
         ? ( playlog_now_ms() - mob->fight_began_ms ) / 1000 : -1;
}

/* ------------------------------------------------------------------ */

/* From char_to_room: a mortal crossing between outside, the overworld
   and a dungeon. The zone left is closed with the seconds spent in it. */
void hylog_moved( CHAR_DATA *ch )
{
    char fields[160];
    int zone, was;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->in_room == NULL )
        return;
    zone = hylog_zone_of( ch->in_room );
    was = ch->pcdata->hylog_zone;
    if ( zone == was )
        return;
    if ( was != 0 )
    {
        snprintf( fields, sizeof(fields), "to=%s how=%s secs=%ld hp=%d",
                  zone_name( zone ), playlog_how( ch ),
                  (long) ( current_time - ch->pcdata->hylog_since ),
                  pct( ch->hit, ch->max_hit ) );
        hylog_write( "leave", ch, get_room_index( ch->last_room_vnum ), fields );
    }
    ch->pcdata->hylog_zone = zone;
    ch->pcdata->hylog_since = current_time;
    if ( zone != 0 )
    {
        snprintf( fields, sizeof(fields), "from=%s how=%s hp=%d",
                  zone_name( was ), playlog_how( ch ), pct( ch->hit, ch->max_hit ) );
        hylog_write( "enter", ch, NULL, fields );
    }
}

/* From playlog_session: the sitting ends (quit, a lost link, shutdown)
   in Hyrule. A lost link keeps the character in the room, so the next
   move after a reconnect enters again. */
void hylog_session_end( CHAR_DATA *ch, const char *how )
{
    char fields[160];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->hylog_zone == 0 )
        return;
    snprintf( fields, sizeof(fields), "to=out how=%s secs=%ld hp=%d",
              how != NULL ? how : "-",
              (long) ( current_time - ch->pcdata->hylog_since ),
              pct( ch->hit, ch->max_hit ) );
    hylog_write( "leave", ch, NULL, fields );
    ch->pcdata->hylog_zone = 0;
}

/* A gate turned them back: which dungeon, which gate (entry or
   guardian) and what it wanted. */
void hylog_gate( CHAR_DATA *ch, int level, const char *which, int need )
{
    char fields[200], what[80];
    OBJ_INDEX_DATA *index = need > 0 ? get_obj_index( need ) : NULL;

    hylog_clean( what, sizeof(what), index != NULL ? index->short_descr : "-" );
    /* A flight that tries the gated way is a flight, not a visit turned
       back: the fight is what the row would be about, and every try
       wrote one. */
    if ( ch != NULL && ch->fighting != NULL )
        return;
    snprintf( fields, sizeof(fields), "dungeon=%d gate=%s need=%d need_name=%s how=%s",
              level, which, need, what, playlog_how( ch ) );
    hylog_write( "gate", ch, NULL, fields );
}

/* A seal opened: the puzzle object, the way it opened and the command. */
void hylog_seal( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char fields[200], what[80];

    if ( obj == NULL || obj->pIndexData == NULL || ch == NULL || ch->in_room == NULL
    ||   !IS_HYRULE_ROOM_VNUM( ch->in_room->vnum ) )
        return;
    hylog_clean( what, sizeof(what), obj->short_descr );
    snprintf( fields, sizeof(fields), "obj=%d obj_name=%s dir=%d how=%s",
              obj->pIndexData->vnum, what, obj->value[2], playlog_how( ch ) );
    hylog_write( "seal", ch, NULL, fields );
}

/* From obj_to_char: a Hyrule object reaching a playing mortal, however
   it came -- picked up, bought, claimed, handed over, looted, made by
   COMBINE, taken from the stash -- with the command that brought it. */
void hylog_got( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char fields[240], what[80];

    if ( obj == NULL || obj->pIndexData == NULL || ch == NULL || IS_NPC(ch)
    ||   obj->pIndexData->vnum < HYRULE_OBJ_FIRST || obj->pIndexData->vnum > HYRULE_OBJ_LAST
    ||   obj->item_type == ITEM_MONEY
    ||   ch->desc == NULL || ch->desc->connected != CON_PLAYING )
        return;
    hylog_clean( what, sizeof(what), obj->short_descr );
    snprintf( fields, sizeof(fields), "obj=%d obj_name=%s type=%s obj_level=%d how=%s",
              obj->pIndexData->vnum, what, item_type_name( obj ),
              obj->level, playlog_how( ch ) );
    hylog_write( "got", ch, NULL, fields );
}

/* A once-per-character claim: a money cave, a Heart Container, a
   take-any choice, a bigger bomb bag. */
void hylog_claim( CHAR_DATA *ch, const char *what, int detail )
{
    char fields[120];

    snprintf( fields, sizeof(fields), "what=%s detail=%d", what, detail );
    hylog_write( "claim", ch, NULL, fields );
}

/* The fields of a guardian's row: the guardian's words (under 100
   bytes), its cleaned name and the party, so a full party is never cut
   off the end of a row the reports read word by word. */
#define HYLOG_PARTY             480
#define HYLOG_GUARDIAN_FIELDS   ( 128 + 64 + HYLOG_PARTY )

/* A guardian entering a fight with a mortal (set_fighting). */
void hylog_engage( CHAR_DATA *guardian, CHAR_DATA *ch )
{
    char fields[HYLOG_GUARDIAN_FIELDS], party[HYLOG_PARTY], name[64];

    ch = hylog_actor( ch );
    if ( !is_hyrule_guardian( guardian ) || !hylog_counts( ch ) )
        return;
    hylog_clean( name, sizeof(name), guardian->short_descr );
    hylog_party( guardian, party, sizeof(party) );
    snprintf( fields, sizeof(fields), "foe=%d foe_name=%s foe_hp=%d foe_max=%d %s",
              guardian->pIndexData->vnum, name, pct( guardian->hit, guardian->max_hit ),
              guardian->max_hit, party );
    hylog_write( "engage", ch, guardian->in_room, fields );
}

/* A guardian slain, before its corpse is made: the fight's length and
   everybody who was there, as they stood at the end. */
void hylog_guardian_down( CHAR_DATA *ch, CHAR_DATA *guardian )
{
    char fields[HYLOG_GUARDIAN_FIELDS], party[HYLOG_PARTY], name[64];

    ch = hylog_actor( ch );
    if ( !is_hyrule_guardian( guardian ) || !hylog_counts( ch ) )
        return;
    hylog_clean( name, sizeof(name), guardian->short_descr );
    hylog_party( guardian, party, sizeof(party) );
    snprintf( fields, sizeof(fields), "foe=%d foe_name=%s secs=%ld foe_max=%d %s",
              guardian->pIndexData->vnum, name, fight_secs( guardian ),
              guardian->max_hit, party );
    hylog_write( "guardian-down", ch, guardian->in_room, fields );
}

/* A mortal fled a fight in Hyrule: what from, and how much of it was
   left -- for a guardian, how close the fight was. Called once they are
   out, so the room is the one they fled from. */
void hylog_flee( CHAR_DATA *ch, CHAR_DATA *foe )
{
    char fields[240], name[64];
    ROOM_INDEX_DATA *from;

    if ( ch == NULL || foe == NULL || !IS_NPC(foe) || foe->pIndexData == NULL )
        return;
    from = foe->in_room;
    if ( from == NULL || !IS_HYRULE_ROOM_VNUM( from->vnum ) )
        return;
    hylog_clean( name, sizeof(name), foe->short_descr );
    snprintf( fields, sizeof(fields), "foe=%d foe_name=%s guardian=%d foe_hp=%d secs=%ld hp=%d",
              foe->pIndexData->vnum, name, is_hyrule_guardian( foe ) ? 1 : 0,
              pct( foe->hit, foe->max_hit ), fight_secs( foe ),
              pct( ch->hit, ch->max_hit ) );
    hylog_write( "flee", ch, from, fields );
}

/* A mortal died in Hyrule (raw_kill, before the corpse): to what, and
   how much of it was left. */
void hylog_death( CHAR_DATA *killer, CHAR_DATA *victim )
{
    char fields[240], name[64];
    CHAR_DATA *foe = killer;

    if ( victim == NULL || IS_NPC(victim) || victim->in_room == NULL
    ||   !IS_HYRULE_ROOM_VNUM( victim->in_room->vnum ) )
        return;
    if ( foe == victim || ( foe != NULL && !IS_NPC(foe) ) )
        foe = NULL;
    hylog_clean( name, sizeof(name), foe != NULL ? foe->short_descr : "-" );
    snprintf( fields, sizeof(fields), "foe=%d foe_name=%s guardian=%d foe_hp=%d secs=%ld how=%s",
              foe != NULL && foe->pIndexData != NULL ? foe->pIndexData->vnum : 0,
              name, is_hyrule_guardian( foe ) ? 1 : 0,
              foe != NULL ? pct( foe->hit, foe->max_hit ) : -1,
              fight_secs( foe ),
              killer == NULL ? "none" : killer == victim ? "self"
              : IS_NPC(killer) ? "mob" : "player" );
    hylog_write( "death", victim, NULL, fields );
}

/* The last foe of a Hyrule room fell (after raw_kill's extraction). */
void hylog_room_cleared( CHAR_DATA *ch, ROOM_INDEX_DATA *room, bool foe_died )
{
    CHAR_DATA *rch;

    ch = hylog_actor( ch );
    if ( !foe_died || room == NULL || !IS_HYRULE_ROOM_VNUM( room->vnum ) )
        return;
    for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
        if ( hyrule_foe( rch ) )
            return;
    hylog_write( "cleared", ch, room, "foes=0" );
}
