/*
 * The play journal: gameplay recorded so bugs can be found from what
 * players actually did (owner, 2026-10-21: "really advanced logging for
 * players who play to help identify potential bugs through gameplay").
 *
 * The watch log in toc.log says what a player typed. This says what
 * happened, in a form a tool can read (tools/log_report.py does):
 *
 *   log/play.tsv   one line per command a player runs -- who, level,
 *                  room, area, position, health, whether in a fight, the
 *                  command, the first lines the game answered, and how
 *                  long it took -- plus BUG lines with the command that
 *                  was running, anomalies found by the tick's sanity
 *                  checks, a summary of every session at quit or link
 *                  loss (with its coin split by where it came from), and
 *                  every BUG/TYPO/IDEA report with the player's last few
 *                  commands beside it.
 *   log/crash.log  on a crash, the last CRASH_RING commands and what the
 *                  game loop was doing, written from the signal handler.
 *
 * log/ reaches a public repository every five minutes, so the journal
 * keeps the watch log's rules and adds its own: the words of TELL, REPLY
 * and GTELL, and anything after a password command, are never written,
 * and neither is what the game answered them; a room holding the black
 * market dealer or the treasure goblin is written "-" (room_hides_from_log);
 * nothing about a player's address is ever looked at.
 *
 * Columns, tab-separated: epoch, kind, name, level, room, area, then the
 * kind's own fields (see the writers below). The file is trimmed like
 * the channel journal: past PLAY_JOURNAL_MAX lines it keeps the newest
 * PLAY_JOURNAL_KEEP.
 */

#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#include <sys/time.h>
#endif
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "merc.h"

#define PLAY_JOURNAL_FILE   "../log/play.tsv"
#define CRASH_LOG_FILE      "../log/crash.log"
#define PLAY_JOURNAL_MAX    30000
#define PLAY_JOURNAL_KEEP   15000
#define PLAY_LINE           640
#define PLAY_REPLY          240     /* the answer kept for a command */
#define PLAY_REPLY_LINES    3       /* ... its first lines, joined with " // " */
#define CRASH_RING          128
#define CRASH_LINE          200
#define ANOMALY_QUIET       ( 10 * 60 )   /* one line per kind per player */

/* What the game loop is doing, for a crash outside any command. */
const char *playlog_phase = "boot";

static char crash_ring[CRASH_RING][CRASH_LINE];
static int  crash_next;
static int  crash_fd = -1;
static long journal_lines = -1;     /* -1: not counted yet */
static bool journal_busy;           /* a bug() while writing must not recurse */

/* The command running now, for bug()'s context. */
static char current_name[32];
static bool current_hidden;            /* the running command's player is wizinvis */
static char current_room[16];
static char current_line[100];
static char current_cmd[32];        /* the command's own name, for coin */
static bool current_set;
/* What the running command came to, when a handler said so
   (playlog_result / playlog_outcome): "result:reason", or "" for none. */
static char current_outcome[48];

/* Where a session's coin came from (playlog_coin). SPENT is every loss. */
enum { COIN_LOOT, COIN_QUEST, COIN_DAILY, COIN_SOLD, COIN_GAMBLING,
       COIN_OTHER, COIN_SPENT };
static const char *const coin_source_names[PLAY_COIN_KINDS] =
    { "loot", "quests", "dailies", "sales", "gambling", "other", "spent" };
static const char *coin_override;   /* playlog_coin_as() */
static const char *exp_override;    /* playlog_exp_as() */
static void playlog_pulse_command( const char *name, long ms );

/* ------------------------------------------------------------ helpers */

/*
 * Add `amount` under `label` in a session tally of PLAY_TALLY_KINDS
 * labels: its own slot, the first free one, or past the last, "other".
 * The label is cleaned and cut to fit; sums saturate.
 */
static void tally_add( char names[][PLAY_TALLY_NAME], long *vals,
                       const char *label, long amount )
{
    char clean[PLAY_TALLY_NAME];
    size_t n = 0;
    int i, slot = PLAY_TALLY_KINDS - 1;

    for ( ; label != NULL && *label != '\0' && n + 1 < sizeof(clean); label++ )
        if ( *label > ' ' && *label < 127 && *label != ',' )
            clean[n++] = (char) LOWER( *label );
    clean[n] = '\0';
    if ( clean[0] == '\0' )
        toc_strlcpy( clean, "other", sizeof(clean) );
    for ( i = 0; i < PLAY_TALLY_KINDS - 1; i++ )
        if ( names[i][0] == '\0' || !strcmp( names[i], clean ) )
        {
            slot = i;
            break;
        }
    if ( slot == PLAY_TALLY_KINDS - 1 )     /* full: into "other" */
        for ( i = 0; i < PLAY_TALLY_KINDS - 1; i++ )
            if ( !strcmp( names[i], "other" ) )
            {
                slot = i;
                break;
            }
    toc_strlcpy( names[slot], slot < PLAY_TALLY_KINDS - 1 ? clean : "other",
                 PLAY_TALLY_NAME );
    if ( amount > 0 && vals[slot] > LONG_MAX - amount )
        vals[slot] = LONG_MAX;
    else if ( amount < 0 && vals[slot] < LONG_MIN - amount )
        vals[slot] = LONG_MIN;
    else
        vals[slot] += amount;
}

static const char *play_position( int pos )
{
    static const char *const names[] =
        { "dead", "mortal", "incap", "stunned", "sleeping",
          "resting", "sitting", "fighting", "standing" };

    return pos >= 0 && pos < (int) ( sizeof(names) / sizeof(names[0]) )
        ? names[pos] : "?";
}

/* Tabs and line breaks would split a record; anything not printable
   ASCII is dropped (the journal, like everything the game writes, is
   read as Latin-1 and the tools want plain text). */
static void play_clean( char *dest, size_t size, const char *src )
{
    size_t n = 0;

    if ( size == 0 )
        return;
    for ( ; src != NULL && *src != '\0' && n + 1 < size; src++ )
    {
        unsigned char c = (unsigned char) *src;

        if ( c == '\t' || c == '\n' || c == '\r' )
            dest[n++] = ' ';
        else if ( c >= 32 && c < 127 )
            dest[n++] = (char) c;
    }
    dest[n] = '\0';
}

static void play_room( CHAR_DATA *ch, char *room, size_t rsize,
                       char *area, size_t asize )
{
    if ( ch == NULL || ch->in_room == NULL )
    {
        snprintf( room, rsize, "0" );
        snprintf( area, asize, "-" );
    }
    else if ( room_hides_from_log( ch->in_room ) )
    {
        snprintf( room, rsize, "-" );
        snprintf( area, asize, "-" );
    }
    else
    {
        snprintf( room, rsize, "%d", ch->in_room->vnum );
        play_clean( area, asize, ch->in_room->area != NULL
                                 ? ch->in_room->area->file_name : "?" );
    }
}

/* Held open, like log_string's: a command a line, and an open and close
   for each is a filesystem round trip in the middle of the game loop. */
static FILE *journal_fp;

/*
 * Past PLAY_JOURNAL_MAX lines, keep the newest PLAY_JOURNAL_KEEP: copy them
 * to a temporary file and rename it over the journal, a line at a time,
 * so no buffer the size of the file is ever held.
 */
static void journal_trim( void )
{
    char line[PLAY_LINE];
    FILE *in, *out;
    long total = 0, skip, seen = 0;

    if ( journal_fp != NULL )
    {
        fclose( journal_fp );
        journal_fp = NULL;
    }
    if ( ( in = fopen( PLAY_JOURNAL_FILE, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), in ) != NULL )
        if ( strchr( line, '\n' ) != NULL )
            total++;
    journal_lines = total;
    if ( total <= PLAY_JOURNAL_MAX
    ||   ( out = fopen( PLAY_JOURNAL_FILE ".tmp", "w" ) ) == NULL )
    {
        fclose( in );
        return;
    }
    skip = total - PLAY_JOURNAL_KEEP;
    rewind( in );
    while ( fgets( line, sizeof(line), in ) != NULL )
    {
        if ( seen >= skip )
            fputs( line, out );
        if ( strchr( line, '\n' ) != NULL )
            seen++;
    }
    fclose( in );
    /* temp_file_commit checks the write as well as the close: a full disk
       renamed a short journal over the whole one. */
    if ( temp_file_commit( out, PLAY_JOURNAL_FILE ".tmp", PLAY_JOURNAL_FILE ) )
        journal_lines = PLAY_JOURNAL_KEEP;
}

/*
 * Wizinvis staff leave no trace in the journal (owner, 2026-11-09): no
 * row about them -- their commands, outcomes, state, crafts, items,
 * deaths, sessions, reports or kills in progress.tsv -- and no name or
 * room where a row is about something else (a BUG line's context, the
 * crash ring). The journal is published; their presence is not. The
 * rows outcome/state/craft/item used to write with the name left out
 * are now not written. The watch log in toc.log is a staff tool and
 * keeps its own rules.
 */
static bool play_hidden( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && IS_SET( ch->act, PLR_WIZINVIS );
}

/* One record: the common columns, then `fields` (already tab-joined). */
static void journal_write( const char *kind, CHAR_DATA *ch, const char *fields )
{
    char room[16], area[64], name[32];

    if ( journal_busy || play_hidden( ch ) )
        return;
    journal_busy = true;
    if ( journal_lines < 0 || journal_lines >= PLAY_JOURNAL_MAX )
        journal_trim();
    if ( journal_fp == NULL )
        journal_fp = fopen( PLAY_JOURNAL_FILE, "a" );
    if ( journal_fp != NULL )
    {
        play_room( ch, room, sizeof(room), area, sizeof(area) );
        play_clean( name, sizeof(name), ch != NULL ? ch->name : "-" );
        fprintf( journal_fp, "%ld\t%s\t%s\t%d\t%s\t%s\t%s\n", (long) current_time,
                 kind, name, ch != NULL ? ch->level : 0, room, area, fields );
        fflush( journal_fp );   /* the state sync reads it every five minutes */
        journal_lines++;
    }
    journal_busy = false;
}

/* One line of the answer onto what is kept, " // " between lines (SCORE
   and the boxed displays draw with "|"). A line of nothing but rules and
   borders says nothing and is skipped. */
static void reply_add( char *dest, size_t size, char *line, size_t *n, int *lines )
{
    char clean[PLAY_REPLY];
    const char *p;
    bool says = false;

    line[*n] = '\0';
    for ( p = line; *p != '\0'; p++ )
        if ( isalnum( (unsigned char) *p ) )
            says = true;
    if ( says )
    {
        play_clean( clean, sizeof(clean), line );
        if ( *lines > 0 )
            toc_strlcat( dest, " // ", size );
        toc_strlcat( dest, clean, size );
        ( *lines )++;
    }
    *n = 0;
}

/*
 * The first PLAY_REPLY_LINES lines the game sent back, from the
 * descriptor's output buffer: colour and Telnet negotiation (GMCP rides
 * the same buffer) stripped, blank lines skipped. One line was not
 * enough: AQUEST COMPLETE, SCORE and EQUIPMENT all open with a line that
 * says nothing (2026-10-22), and the reward or the change was on the next.
 */
static bool first_reply_line( const char *out, int len, char *dest, size_t size )
{
    char line[PLAY_REPLY];
    size_t n = 0;
    int i, lines = 0;
    bool cut = false;

    dest[0] = '\0';
    for ( i = 0; i < len && lines < PLAY_REPLY_LINES; i++ )
    {
        unsigned char c = (unsigned char) out[i];

        if ( c == 255 )                 /* IAC: a Telnet sequence */
        {
            if ( i + 1 < len && (unsigned char) out[i + 1] == 250 )
            {                           /* SB ... IAC SE */
                for ( i += 2; i + 1 < len; i++ )
                    if ( (unsigned char) out[i] == 255
                    &&   (unsigned char) out[i + 1] == 240 )
                        break;
                i++;
            }
            else
                i += 2;
            continue;
        }
        if ( c == 27 )                  /* ESC [ ... letter: ANSI colour */
        {
            for ( i++; i < len && !( ( out[i] >= 'A' && out[i] <= 'Z' )
                                  || ( out[i] >= 'a' && out[i] <= 'z' ) ); i++ )
                ;
            continue;
        }
        if ( c == '\n' || c == '\r' )
        {
            reply_add( dest, size, line, &n, &lines );
            continue;
        }
        if ( c >= 32 && c < 127 )
        {
            if ( n + 1 < sizeof(line) )
                line[n++] = (char) c;
            else
                cut = true;             /* a line longer than is kept */
        }
    }
    if ( lines < PLAY_REPLY_LINES )
        reply_add( dest, size, line, &n, &lines );
    /* Anything the game said past the lines kept -- another line with
       something in it -- means the record holds only the start. */
    for ( ; !cut && i < len; i++ )
    {
        unsigned char c = (unsigned char) out[i];

        if ( c == 255 )                 /* Telnet: GMCP is not words */
        {
            if ( i + 1 < len && (unsigned char) out[i + 1] == 250 )
            {
                for ( i += 2; i + 1 < len; i++ )
                    if ( (unsigned char) out[i] == 255
                    &&   (unsigned char) out[i + 1] == 240 )
                        break;
                i++;
            }
            else
                i += 2;
            continue;
        }
        if ( c == 27 )                  /* a colour code's digits neither */
        {
            for ( i++; i < len && !( ( out[i] >= 'A' && out[i] <= 'Z' )
                                  || ( out[i] >= 'a' && out[i] <= 'z' ) ); i++ )
                ;
            continue;
        }
        if ( isalnum( c ) )
            cut = true;
    }
    if ( strlen( dest ) + 1 >= size )
        cut = true;
    return cut;
}

/* -------------------------------------------------------------- crash */

static void crash_write( int fd, const char *text )
{
    size_t left = strlen( text );

    while ( left > 0 )
    {
        ssize_t done = write( fd, text, left );

        if ( done <= 0 )
            return;
        text += done;
        left -= (size_t) done;
    }
}

/* Async-signal-safe: no stdio, a number written by hand. */
static void crash_number( int fd, long value )
{
    char digits[24];
    int n = 0;
    bool negative = value < 0;

    if ( negative )
        value = -value;
    do
    {
        digits[n++] = (char) ( '0' + value % 10 );
        value /= 10;
    } while ( value > 0 && n < 22 );
    if ( negative )
        digits[n++] = '-';
    while ( n > 0 )
    {
        char c = digits[--n];

        if ( write( fd, &c, 1 ) != 1 )
            return;
    }
}

static void crash_handler( int sig )
{
    int i;

    if ( crash_fd >= 0 )
    {
        crash_write( crash_fd, "=== crash: signal " );
        crash_number( crash_fd, sig );
        crash_write( crash_fd, " at " );
        crash_number( crash_fd, (long) time( NULL ) );
        crash_write( crash_fd, " during " );
        crash_write( crash_fd, playlog_phase != NULL ? playlog_phase : "?" );
        crash_write( crash_fd, "; the last commands, oldest first:\n" );
        for ( i = 0; i < CRASH_RING; i++ )
        {
            const char *line = crash_ring[( crash_next + i ) % CRASH_RING];

            if ( line[0] != '\0' )
            {
                crash_write( crash_fd, line );
                crash_write( crash_fd, "\n" );
            }
        }
        crash_write( crash_fd, "=== end ===\n" );
    }
    signal( sig, SIG_DFL );
    raise( sig );
}

/*
 * At boot. The crash log is opened now, because the handler may not
 * call fopen. Not under a sanitizer build: AddressSanitizer reports a
 * crash from its own handler, and that report is worth more than this.
 */
void playlog_boot( void )
{
    playlog_phase = "game loop";
#if defined(__SANITIZE_ADDRESS__)
    return;
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
    return;
#endif
#endif
    crash_fd = open( CRASH_LOG_FILE, O_WRONLY | O_CREAT | O_APPEND, 0644 );
    if ( crash_fd < 0 )
        return;
    signal( SIGSEGV, crash_handler );
    signal( SIGBUS,  crash_handler );
    signal( SIGFPE,  crash_handler );
    signal( SIGILL,  crash_handler );
    signal( SIGABRT, crash_handler );
}

/* --------------------------------------------------------- a command */

/* Who caused what is happening now: the player whose command is running
   ("Alaric: get all corpse"), or the update phase. For records that want
   to say who did it, such as a corpse's history (corpses.c). */
const char *playlog_cause( void )
{
    static char cause[160];

    if ( current_set )
        snprintf( cause, sizeof(cause), "%s: %s", current_name, current_cmd );
    else
        snprintf( cause, sizeof(cause), "(%s)", playlog_phase );
    return cause;
}

/* How something happened to ch, as one word: their own command running
   ("north", "recall", "play"), "<other>'s" for somebody else's command, or
   the update phase in brackets ("(violence_update)"). For log/hyrule.tsv
   (hyrulelog.c). A hidden command is "-". */
const char *playlog_how( CHAR_DATA *ch )
{
    static char how[64];

    if ( !current_set )
        snprintf( how, sizeof(how), "(%s)", playlog_phase );
    else if ( current_hidden )
        snprintf( how, sizeof(how), "-" );
    else if ( ch != NULL && ch->name != NULL && !str_cmp( ch->name, current_name ) )
        snprintf( how, sizeof(how), "%s", current_cmd[0] != '\0' ? current_cmd : "-" );
    else
        snprintf( how, sizeof(how), "%s(another's)", current_cmd[0] != '\0' ? current_cmd : "-" );
    return how;
}

/*
 * interpret() calls begin before the command and end after it, at its
 * outermost level only. `shown` is the line as it may be written down
 * (interp.c withholds the arguments of private and password commands).
 */
void playlog_begin( CHAR_DATA *ch, const char *cmd_name, const char *shown )
{
    char line[CRASH_LINE];

    if ( ch == NULL || IS_NPC(ch) )
        return;
    play_clean( current_name, sizeof(current_name), ch->name );
    current_hidden = play_hidden( ch );
    play_clean( current_cmd, sizeof(current_cmd), cmd_name != NULL ? cmd_name : "" );
    if ( ch->in_room == NULL )
        snprintf( current_room, sizeof(current_room), "0" );
    else if ( room_hides_from_log( ch->in_room ) )
        snprintf( current_room, sizeof(current_room), "-" );
    else
        snprintf( current_room, sizeof(current_room), "%d", ch->in_room->vnum );
    play_clean( current_line, sizeof(current_line), shown );
    current_outcome[0] = '\0';
    current_set = true;
    playlog_phase = "a command";

    /* A wizinvis command is kept nowhere that is published later: not in
       the crash ring, nor in the recent commands a BUG/TYPO/IDEA report
       carries once they are visible again. A blank name and room were
       not enough -- the words themselves can name somebody or a room
       (review, 2026-11-09). */
    if ( current_hidden )
        return;

    snprintf( line, sizeof(line), "%ld %s [%s] %s", (long) current_time,
              current_name, current_room, current_line );
    toc_strlcpy( crash_ring[crash_next], line, CRASH_LINE );
    crash_next = ( crash_next + 1 ) % CRASH_RING;

    if ( ch->pcdata != NULL )
    {
        toc_strlcpy( ch->pcdata->play_recent[ch->pcdata->play_recent_next],
                     current_line, sizeof(ch->pcdata->play_recent[0]) );
        ch->pcdata->play_recent_next =
            ( ch->pcdata->play_recent_next + 1 ) % PLAY_RECENT;
        ch->pcdata->play_cmds++;
    }
}

/*
 * After the command. The character and descriptor are passed as they
 * were before it, and the caller has already checked that the descriptor
 * still holds the character (QUIT frees both). `out` is everything the
 * command wrote to the descriptor.
 */
void playlog_end( CHAR_DATA *ch, const char *cmd_name, const char *shown,
                  bool secret, bool refused, const char *out, int out_len,
                  long ms, int pos_before, int hp_pct_before, bool fighting_before )
{
    char reply[PLAY_REPLY];
    char fields[PLAY_LINE];
    char args[120];
    const char *space;
    bool cut = false;

    current_set = false;
    playlog_phase = "game loop";
    playlog_pulse_command( play_hidden( ch ) ? "-" : refused ? "(refused)" : cmd_name, ms );
    if ( ch == NULL || IS_NPC(ch) )
        return;
    if ( refused && ch->pcdata != NULL && !play_hidden( ch ) )
        ch->pcdata->play_refused++;

    /* The line as it may be shown, less the command word. */
    space = strchr( shown, ' ' );
    play_clean( args, sizeof(args), space != NULL ? space + 1 : "" );
    if ( secret || out == NULL || out_len <= 0 )
        reply[0] = '\0';
    else
        cut = first_reply_line( out, out_len, reply, sizeof(reply) );

    /* Two columns after the reply (2026-11-03), so a reader that stops at
       the reply still reads every row: what the command came to, when its
       handler said (playlog_result), and "+" when the reply kept is only
       the start of what the game said. */
    snprintf( fields, sizeof(fields), "%s\t%d\t%ld\t%s\t%s\t%s\t%s\t%s\t%s",
              play_position( pos_before ), hp_pct_before, ms,
              fighting_before ? "fight" : "-",
              cmd_name != NULL ? cmd_name : "?", args,
              secret ? "(withheld)" : reply,
              current_outcome[0] != '\0' ? current_outcome
                                         : refused ? "refusal:unknown-command" : "-",
              cut && !secret ? "+" : "-" );
    current_outcome[0] = '\0';
    journal_write( refused ? "refused" : "cmd", ch, fields );
}

/*
 * What a command came to, from inside its handler: a command the game
 * knows can still fail, and its row said only "cmd" (review, 2026-11-03).
 * `result` is one of success, refusal, partial, failure, pending or
 * uncertain; `reason` a short code ("frozen", "owner-save"). Kept for the
 * running command of `ch` only, and written as its row's outcome column;
 * the first result said wins, since the first refusal is the reason.
 */
void playlog_result( CHAR_DATA *ch, const char *result, const char *reason )
{
    char clean[48];

    if ( ch == NULL || IS_NPC(ch) || !current_set || current_outcome[0] != '\0'
    ||   ch->name == NULL || str_cmp( ch->name, current_name ) )
        return;
    snprintf( clean, sizeof(clean), "%s:%s", result != NULL ? result : "?",
              reason != NULL && reason[0] != '\0' ? reason : "-" );
    play_clean( current_outcome, sizeof(current_outcome), clean );
}

/*
 * An operation that moves or changes something worth following: one
 * "outcome" row -- op, result, reason, the recovery operation id it rode
 * under ("-" for none), and `detail`, the before/after numbers as
 * key=value words ("qp=120->160 coin=+3g"). Also the running command's
 * outcome. Callers pass no private words, addresses or hidden rooms; the
 * row's own room is written by the journal's rules.
 */
void playlog_outcome( CHAR_DATA *ch, const char *op, const char *result,
                      const char *reason, const char *op_id, const char *detail )
{
    char fields[PLAY_LINE];
    char c_op[32], c_res[16], c_reason[32], c_id[48], c_detail[PLAY_LINE / 2];

    if ( ch == NULL || IS_NPC(ch) )
        return;
    playlog_result( ch, result, reason );
    play_clean( c_op, sizeof(c_op), op );
    play_clean( c_res, sizeof(c_res), result );
    play_clean( c_reason, sizeof(c_reason), reason != NULL && reason[0] != '\0' ? reason : "-" );
    play_clean( c_id, sizeof(c_id), op_id != NULL && op_id[0] != '\0' ? op_id : "-" );
    play_clean( c_detail, sizeof(c_detail), detail != NULL ? detail : "" );
    snprintf( fields, sizeof(fields), "%s\t%s\t%s\t%s\t%s", c_op, c_res, c_reason,
              c_id, c_detail );
    journal_write( "outcome", ch, fields );
}

/*
 * SCORE, as numbers: a SCORE row keeps only the first lines of the sheet
 * -- 53 of them in one day held nothing but its header (review,
 * 2026-11-03) -- so the state behind it goes in a row of its own, words
 * of key=value: level, pools, alignment, wealth (copper, carried and
 * banked), quest points, practices, trains, stash and remorts.
 */
void playlog_state( CHAR_DATA *ch )
{
    char fields[PLAY_LINE];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    snprintf( fields, sizeof(fields),
              "lvl=%d hp=%d/%d mana=%d/%d mv=%d/%d align=%d exp=%ld coin=%ld bank=%ld "
              "qp=%d prac=%d train=%d stash=%d/%d remorts=%d",
              ch->level, ch->hit, ch->max_hit, ch->mana, ch->max_mana,
              ch->move, ch->max_move, ch->alignment, (long) ch->exp,
              coins_to_copper( ch ), ch->pcdata->bank, ch->questpoints,
              ch->practice, ch->train, stash_count( ch ), ch->pcdata->stash_max,
              ch->pcdata->num_remorts );
    journal_write( "state", ch, fields );
}

/* For bug(): " (during Name's 'look' in room 4207)", or "". */
void playlog_bug_context( char *buf, size_t size )
{
    if ( !current_set )
    {
        snprintf( buf, size, " (during %s)", playlog_phase );
        return;
    }
    if ( current_hidden )
    {
        snprintf( buf, size, " (during a command)" );
        return;
    }
    snprintf( buf, size, " (during %s's '%s' in room %s)",
              current_name, current_line, current_room );
}

/* A BUG line into the journal too, so one file holds the whole story. */
void playlog_bug( const char *message )
{
    char fields[PLAY_LINE];
    char text[PLAY_LINE - 128];        /* room for the tab and the line */

    play_clean( text, sizeof(text), message );
    snprintf( fields, sizeof(fields), "%s\t%s", text,
              !current_set ? playlog_phase : current_hidden ? "-" : current_line );
    journal_write( "bug", NULL, fields );
}

/* -------------------------------------------------------- the reports */

/* BUG, TYPO and IDEA: the report with the last few commands beside it,
   which is what turns "it's broken" into something a fix can start from. */
void playlog_report( CHAR_DATA *ch, const char *kind, const char *text )
{
    char fields[PLAY_LINE];
    char recent[PLAY_LINE / 2];
    char said[200];
    int i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    recent[0] = '\0';
    for ( i = 1; i <= PLAY_RECENT; i++ )
    {
        const char *line = ch->pcdata->play_recent[
            ( ch->pcdata->play_recent_next - 1 - i + 2 * PLAY_RECENT ) % PLAY_RECENT];

        if ( line[0] == '\0' )
            continue;
        if ( recent[0] != '\0' )
            toc_strlcat( recent, " | ", sizeof(recent) );
        toc_strlcat( recent, line, sizeof(recent) );
    }
    play_clean( said, sizeof(said), text );
    snprintf( fields, sizeof(fields), "%s\t%s\t%d/%d hp\t%s", kind, said,
              ch->hit, ch->max_hit, recent );
    journal_write( "report", ch, fields );
}

/* Every real BREW, CONCOCT and SCRIBE attempt (magic2.c craft_audit). A
   wizinvis crafter's is not written (play_hidden). */
void playlog_craft( CHAR_DATA *ch, const char *fields )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    journal_write( "craft", ch, fields );
}

/* ------------------------------------------------------- the anomalies */

static long play_wealth( CHAR_DATA *ch )
{
    return coins_to_copper( ch ) + ( ch->pcdata != NULL ? ch->pcdata->bank : 0 );
}

static void anomaly( CHAR_DATA *ch, int kind, const char *what, const char *detail )
{
    char fields[PLAY_LINE];
    char buf[PLAY_LINE];

    if ( play_hidden( ch )
    ||   ch->pcdata->play_anom_last[kind] + ANOMALY_QUIET > current_time )
        return;
    ch->pcdata->play_anom_last[kind] = current_time;
    snprintf( fields, sizeof(fields), "%s\t%s", what, detail );
    journal_write( "anomaly", ch, fields );
    snprintf( buf, sizeof(buf), "ANOMALY: %s: %s (%s)", ch->name, what, detail );
    log_string( buf );
}

/*
 * Every tick, for every player in the game (char_update): states that
 * should never happen, and jumps too big for anything ordinary to cause.
 * Staff are left out of the jumps -- they set what they like.
 */
void playlog_tick( CHAR_DATA *ch )
{
    char detail[200];
    long wealth;
    int span;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->in_room == NULL )
        return;
    wealth = play_wealth( ch );
    if ( !ch->pcdata->play_baseline )
    {
        ch->pcdata->play_baseline = true;
        ch->pcdata->play_last_exp = ch->exp;
        ch->pcdata->play_last_wealth = wealth;
        ch->pcdata->play_start_wealth = wealth;
        ch->pcdata->play_last_max_hit = ch->max_hit;
        return;
    }

    if ( ch->hit > ch->max_hit + UMAX( 100, ch->max_hit / 2 ) )
    {
        /* What the maximum was a tick ago says whether it fell (a buff or
           a piece of gear gone) or the hit points rose. */
        if ( ch->pcdata->play_last_max_hit > 0
        &&   ch->pcdata->play_last_max_hit != ch->max_hit )
            snprintf( detail, sizeof(detail), "%d of %d hit points; max was %d a tick ago",
                      ch->hit, ch->max_hit, ch->pcdata->play_last_max_hit );
        else
            snprintf( detail, sizeof(detail), "%d of %d hit points", ch->hit, ch->max_hit );
        anomaly( ch, 0, "hit points far over max", detail );
    }
    if ( ch->new_platinum < 0 || ch->new_gold < 0 || ch->new_silver < 0
    ||   ch->new_copper < 0 || ch->pcdata->bank < 0 )
    {
        snprintf( detail, sizeof(detail), "%ldp %ldg %lds %ldc, bank %ld",
                  ch->new_platinum, ch->new_gold, ch->new_silver,
                  ch->new_copper, ch->pcdata->bank );
        anomaly( ch, 1, "negative coin", detail );
    }
    if ( ch->practice < 0 || ch->train < 0 )
    {
        snprintf( detail, sizeof(detail), "%d practices, %d trains", ch->practice, ch->train );
        anomaly( ch, 2, "negative practices or trains", detail );
    }
    if ( ch->position == POS_FIGHTING && ch->fighting == NULL )
        anomaly( ch, 3, "fighting nobody", "position is fighting, no opponent" );
    else if ( ch->fighting != NULL && ch->fighting->in_room != ch->in_room )
        anomaly( ch, 3, "fighting across rooms", ch->fighting->name != NULL
                 ? ch->fighting->name : "?" );

    if ( !IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
    {
        if ( ch->level > 54 + ch->pcdata->num_remorts && ch->level < LEVEL_IMMORTAL )
        {
            snprintf( detail, sizeof(detail), "level %d with %d remorts",
                      ch->level, ch->pcdata->num_remorts );
            anomaly( ch, 4, "level past the remort cap", detail );
        }
        span = exp_per_level( ch, ch->pcdata->points );
        if ( span > 0 && ch->exp - ch->pcdata->play_last_exp > 3L * span )
        {
            snprintf( detail, sizeof(detail), "%ld experience in one tick, %d a level",
                      ch->exp - ch->pcdata->play_last_exp, span );
            anomaly( ch, 5, "experience jump", detail );
        }
        if ( wealth - ch->pcdata->play_last_wealth
             > 2000L * black_market_kill_value( ch->level ) )
        {
            snprintf( detail, sizeof(detail), "%ld copper in one tick, %ld a kill",
                      wealth - ch->pcdata->play_last_wealth,
                      black_market_kill_value( ch->level ) );
            anomaly( ch, 6, "coin jump", detail );
        }
    }
    ch->pcdata->play_last_exp = ch->exp;
    ch->pcdata->play_last_wealth = wealth;
    ch->pcdata->play_last_max_hit = ch->max_hit;
}

/* ------------------------------------------------------------- coin */

/*
 * Every change to a purse, from the four functions that make one
 * (adjust_coin_balance, spend_copper, gain_copper, add_money): `amount`
 * of `unit` copper each, `pile` for coin picked up, looted or handed
 * over. The source is the command running for that character -- AQUEST
 * pays quests, SELL sales, the casino's commands gambling -- or what
 * playlog_coin_as() names. Money moved between the purse and the bank,
 * or changed into other coins, is no gain and is left out.
 */
void playlog_coin_as( const char *source )
{
    coin_override = source;
}

void playlog_coin( CHAR_DATA *ch, long amount, long unit, bool pile )
{
    static const char *const gambling[] =
        { "gamble", "slots", "bet", "roulette", "poker", NULL };
    static const char *const neutral[] =
        { "deposit", "withdraw", "convert", "balance", NULL };
    bool own = false;
    long size, copper;
    int kind, i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || amount == 0 || unit <= 0 )
        return;
    size = amount == LONG_MIN ? LONG_MAX : ( amount < 0 ? -amount : amount );
    copper = size > LONG_MAX / unit ? LONG_MAX : size * unit;
    if ( current_set && ch->name != NULL && !str_cmp( current_name, ch->name ) )
        own = true;
    if ( own )
        for ( i = 0; neutral[i] != NULL; i++ )
            if ( !str_cmp( current_cmd, neutral[i] ) )
                return;

    if ( amount < 0 )
    {
        kind = COIN_SPENT;
        /* What it went on: the character's own command (STASH, HEAL,
           REPAIR, BUY, TRAIN ...), what playlog_coin_as() names, or
           "other" -- somebody else's command took it. */
        tally_add( ch->pcdata->play_spent_on, ch->pcdata->play_spent,
                   coin_override != NULL ? coin_override
                                         : own ? current_cmd : "other",
                   copper );
    }
    else
    {
        kind = pile ? COIN_LOOT : COIN_OTHER;
        if ( coin_override != NULL )
        {
            for ( i = 0; i < COIN_SPENT; i++ )
                if ( !str_cmp( coin_override, coin_source_names[i] ) )
                    kind = i;
        }
        else if ( own && !str_cmp( current_cmd, "aquest" ) )
            kind = COIN_QUEST;
        else if ( own && !str_cmp( current_cmd, "sell" ) )
            kind = COIN_SOLD;
        else if ( own )
            for ( i = 0; gambling[i] != NULL; i++ )
                if ( !str_cmp( current_cmd, gambling[i] ) )
                    kind = COIN_GAMBLING;
    }
    if ( ch->pcdata->play_coin[kind] > LONG_MAX - copper )
        ch->pcdata->play_coin[kind] = LONG_MAX;
    else
        ch->pcdata->play_coin[kind] += copper;
}

/*
 * Experience, from gain_exp -- the one place that changes it in play --
 * and the two exchanges that take it outside gain_exp. The source is what
 * playlog_exp_as() named just before (kills, death, flee, recall,
 * drained, skill use, exchange), else the character's own command, else
 * "other". A gain gain_exp refused outright (level 50, the remort cap) is
 * tallied as "capped:<source>" with what was offered, so a session that
 * fought for nothing says so. The override is spent by every call.
 */
void playlog_exp_as( const char *source )
{
    exp_override = source;
}

void playlog_exp( CHAR_DATA *ch, long amount, bool capped )
{
    char label[48];
    const char *source = exp_override;
    bool own;

    exp_override = NULL;
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || amount == 0 )
        return;
    own = current_set && ch->name != NULL && !str_cmp( current_name, ch->name );
    if ( source == NULL )
        source = own ? current_cmd : "other";
    if ( capped )
    {
        snprintf( label, sizeof(label), "capped:%s", source );
        source = label;
    }
    tally_add( ch->pcdata->play_exp_from, ch->pcdata->play_exp, source, amount );
}

/* "stash 1550p, heal 30g" -- "kills +12034, death -800" -- or "none". */
static void tally_summary( char names[][PLAY_TALLY_NAME], const long *vals,
                           bool coin, char *buf, size_t size )
{
    char amount[64], part[96];
    int i;

    buf[0] = '\0';
    for ( i = 0; i < PLAY_TALLY_KINDS; i++ )
    {
        if ( names[i][0] == '\0' || vals[i] == 0 )
            continue;
        if ( coin )
            format_price( vals[i], amount, sizeof(amount) );
        else
            snprintf( amount, sizeof(amount), "%+ld", vals[i] );
        snprintf( part, sizeof(part), "%s%s %s", buf[0] != '\0' ? ", " : "",
                  names[i], amount );
        toc_strlcat( buf, part, size );
    }
    if ( buf[0] == '\0' )
        toc_strlcpy( buf, "none", size );
}

/* "loot 3p 20g, quests 162p, spent 400g" -- or "none". */
static void coin_summary( CHAR_DATA *ch, char *buf, size_t size )
{
    char price[64], part[96];
    int i;

    buf[0] = '\0';
    for ( i = 0; i < PLAY_COIN_KINDS; i++ )
    {
        if ( ch->pcdata->play_coin[i] <= 0 )
            continue;
        format_price( ch->pcdata->play_coin[i], price, sizeof(price) );
        snprintf( part, sizeof(part), "%s%s %s", buf[0] != '\0' ? ", " : "",
                  coin_source_names[i], price );
        toc_strlcat( buf, part, size );
    }
    if ( buf[0] == '\0' )
        toc_strlcpy( buf, "none", size );
}

/* ---------------------------------------------------------- a session */

/* At QUIT and at link loss: what one sitting came to. */
void playlog_session( CHAR_DATA *ch, const char *how )
{
    char fields[PLAY_LINE];
    char coin[PLAY_LINE / 4], spent[PLAY_LINE / 4], exp[PLAY_LINE / 4];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL
    ||   ch->pcdata->session_logon <= 0 )
        return;
    hylog_session_end( ch, how );       /* log/hyrule.tsv */
    coin_summary( ch, coin, sizeof(coin) );
    tally_summary( ch->pcdata->play_spent_on, ch->pcdata->play_spent, true,
                   spent, sizeof(spent) );
    tally_summary( ch->pcdata->play_exp_from, ch->pcdata->play_exp, false,
                   exp, sizeof(exp) );
    /* Two columns after the coin (2026-11-05), so a reader that stops at
       the coin reads them all: what the spending went on, and where the
       experience came from and went. */
    snprintf( fields, sizeof(fields),
              "%s\t%lds\t%+d levels\t%+ld exp\t%+ld copper\t%d kills\t%d deaths"
              "\t%d quests\t%d commands\t%d refused\tcoin: %s"
              "\tspent on: %s\texp: %s",
              how, (long) ( current_time - ch->pcdata->session_logon ),
              (int) ch->level - ch->pcdata->session_start_level,
              ch->exp - ch->pcdata->session_start_exp,
              ch->pcdata->play_baseline
                  ? play_wealth( ch ) - ch->pcdata->play_start_wealth : 0L,
              ch->pcdata->session_kills, ch->pcdata->session_deaths,
              ch->pcdata->session_quests, ch->pcdata->play_cmds,
              ch->pcdata->play_refused, coin, spent, exp );
    journal_write( "session", ch, fields );
}


/* --------------------------------------------------------------------
 * log/progress.tsv: what leveling is made of (2026-10-22, the progression
 * pass). One line per credited kill and per flee or player death, so XP
 * per combat minute, recovery and route choice can be measured instead of
 * guessed from arrivals and adjacent timestamps.
 *
 * Columns, tab-separated: epoch, kind (kill, flee, death), character id
 * (the file's Id, never a name -- reports count independent histories by
 * it), level, class, remorts, hp%, mana%, foe vnum, foe level, area file,
 * then for a kill: encounter ms (from the mobile's first blow, set in
 * set_fighting), base xp, rested xp, accepted xp, group members.
 *
 * Never a room: an area file is the finest place written. The black
 * market dealer and the treasure goblin are left out entirely. Trimmed
 * past PROGRESS_MAX lines to the newest PROGRESS_KEEP, like the journal.
 * ------------------------------------------------------------------ */

#define PROGRESS_FILE   "../log/progress.tsv"
#define PROGRESS_MAX    40000
#define PROGRESS_KEEP   20000

static long progress_lines = -1;

/* Durations only -- a pulse, a fight, a command -- so on the monotonic
   clock (comm.c, monotonic_ms): a wall-clock step no longer reads as a
   stall or a negative fight. */
long playlog_now_ms( void )
{
    return monotonic_ms();
}

static void progress_trim( void )
{
    char line[PLAY_LINE];
    FILE *in, *out;
    long total = 0, seen = 0, skip;

    if ( ( in = fopen( PROGRESS_FILE, "r" ) ) == NULL )
    {
        progress_lines = 0;
        return;
    }
    while ( fgets( line, sizeof(line), in ) != NULL )
        if ( strchr( line, '\n' ) != NULL )
            total++;
    progress_lines = total;
    if ( total <= PROGRESS_MAX || ( out = fopen( PROGRESS_FILE ".tmp", "w" ) ) == NULL )
    {
        fclose( in );
        return;
    }
    skip = total - PROGRESS_KEEP;
    rewind( in );
    while ( fgets( line, sizeof(line), in ) != NULL )
    {
        if ( seen >= skip )
            fputs( line, out );
        if ( strchr( line, '\n' ) != NULL )
            seen++;
    }
    fclose( in );
    if ( temp_file_commit( out, PROGRESS_FILE ".tmp", PROGRESS_FILE ) )
        progress_lines = PROGRESS_KEEP;
}

static void progress_write( const char *kind, CHAR_DATA *ch, CHAR_DATA *foe, const char *tail )
{
    FILE *fp;
    const char *area = "-";
    int hp_pct, mana_pct;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || foe == NULL || !IS_NPC(foe)
    ||   foe->pIndexData == NULL || is_unfindable_mob( foe ) || play_hidden( ch ) )
        return;
    if ( progress_lines < 0 || progress_lines >= PROGRESS_MAX )
        progress_trim();
    if ( foe->in_room != NULL && foe->in_room->area != NULL
    &&   foe->in_room->area->file_name != NULL )
        area = foe->in_room->area->file_name;
    hp_pct = ch->max_hit > 0 ? (int) ( 100L * ch->hit / ch->max_hit ) : 0;
    mana_pct = ch->max_mana > 0 ? (int) ( 100L * ch->mana / ch->max_mana ) : 0;
    if ( ( fp = fopen( PROGRESS_FILE, "a" ) ) == NULL )
        return;
    fprintf( fp, "%ld\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s%s%s\n",
             (long) current_time, kind, ch->pcdata->id, ch->level, ch->class,
             ch->pcdata->num_remorts, hp_pct, mana_pct,
             foe->pIndexData->vnum, foe->level, area,
             tail[0] != '\0' ? "\t" : "", tail );
    fclose( fp );
    progress_lines++;
}

void progress_kill( CHAR_DATA *gch, CHAR_DATA *victim, int base_xp, int rested_xp,
                    long accepted_xp, int members, long victim_coin )
{
    char tail[256];
    long encounter = victim != NULL && victim->fight_began_ms > 0
                   ? playlog_now_ms() - victim->fight_began_ms : -1;

    char buffs[8];
    PC_DATA *pc = gch != NULL && !IS_NPC(gch) ? gch->pcdata : NULL;
    int n = 0;

    /* The fight in aggregate, for balance (class review, 2026-10-26):
       the guild, the buffs worn (T titanic, E empower, S sanctuary,
       H haste), and from the fight's ledger -- everything since this
       character's own fight began (set_fighting), which is the kill's
       encounter for a fight with one foe and the whole melee for one with
       several -- the damage dealt; the hit points lost, every way; the
       hit points seen to rise (healing, regeneration, drains: never
       negative); the mana spent; and of the losses, those outside
       damage() (reflection, traps). Numbers only -- nothing typed, said
       or named. */
    if ( pc != NULL )
    {
        fight_ledger_observe( gch );
        if ( is_affected( gch, gsn_titanic ) ) buffs[n++] = 'T';
        if ( is_affected( gch, gsn_empower ) ) buffs[n++] = 'E';
        if ( IS_AFFECTED( gch, AFF_SANCTUARY ) ) buffs[n++] = 'S';
        if ( IS_AFFECTED( gch, AFF_HASTE ) ) buffs[n++] = 'H';
    }
    if ( n == 0 )
        buffs[n++] = '-';
    buffs[n] = '\0';
    /* Last, the coin the foe carried when it fell (2026-11-05), copper:
       what its corpse holds before any holiday treat, so loot per kill
       can be held against the level roll (mob_index_set_wealth). */
    snprintf( tail, sizeof(tail), "%ld\t%d\t%d\t%ld\t%d\t%d\t%s\t%ld\t%ld\t%ld\t%d\t%ld\t%ld",
              encounter, base_xp, rested_xp, accepted_xp, members,
              pc != NULL ? pc->guild : -1, buffs,
              pc != NULL ? pc->meter_damage : 0L,
              pc != NULL ? pc->fight_taken + pc->fight_direct : 0L,
              pc != NULL ? pc->fight_healed : 0L,
              pc != NULL ? pc->fight_mana_start - gch->mana : 0,
              pc != NULL ? pc->fight_direct : 0L, victim_coin );
    progress_write( "kill", gch, victim, tail );
}

/* kind is "flee" or "death"; foe is the mobile it was against. */
void progress_event( CHAR_DATA *ch, const char *kind, CHAR_DATA *foe )
{
    progress_write( kind, ch, foe, "" );
}


/* --------------------------------------------------------------------
 * Deep bug logging (2026-11-05): what a player feels and nothing else
 * wrote down -- the game hitching, how a death came about, and things
 * vanishing from a pack. Rows in log/play.tsv like the rest.
 * ------------------------------------------------------------------ */

/*
 * A pulse is a quarter of a second (PULSE_PER_SECOND). One that runs past
 * STALL_MS is lag every player feels, and the row says where it went: the
 * slowest stretch of the pulse (input -- the commands typed -- or one of
 * update_handler's phases, or output) and the slowest command. One row a
 * STALL_QUIET at most; the next says how many were left out since.
 */
#define STALL_MS        250
#define STALL_QUIET     60

static long pulse_start_ms;
static long pulse_mark_ms;
static long pulse_phase_ms;
static const char *pulse_phase_now = "input";
static const char *pulse_phase_worst = "-";
static long pulse_cmd_ms;
static char pulse_cmd[32];
static time_t stall_last;
static int stall_unwritten;

void playlog_pulse_begin( void )
{
    pulse_start_ms = pulse_mark_ms = playlog_now_ms();
    pulse_phase_now = "input";
    pulse_phase_worst = "-";
    pulse_phase_ms = 0;
    pulse_cmd_ms = 0;
    pulse_cmd[0] = '\0';
}

/* update_handler's phases: also playlog_phase, which BUG lines and the
   crash recorder name. The time since the last mark is the last phase's. */
void playlog_phase_enter( const char *phase )
{
    long now = playlog_now_ms();

    if ( pulse_start_ms > 0 && now - pulse_mark_ms > pulse_phase_ms )
    {
        pulse_phase_ms = now - pulse_mark_ms;
        pulse_phase_worst = pulse_phase_now;
    }
    pulse_mark_ms = now;
    pulse_phase_now = phase;
    playlog_phase = phase;
}

static void playlog_pulse_command( const char *name, long ms )
{
    if ( ms > pulse_cmd_ms )
    {
        pulse_cmd_ms = ms;
        play_clean( pulse_cmd, sizeof(pulse_cmd), name != NULL ? name : "?" );
    }
}

void playlog_pulse_end( void )
{
    char fields[PLAY_LINE];
    DESCRIPTOR_DATA *d;
    long total;
    int players = 0;

    if ( pulse_start_ms <= 0 )
        return;
    playlog_phase_enter( "game loop" );
    total = pulse_mark_ms - pulse_start_ms;
    pulse_start_ms = 0;
    if ( total < STALL_MS )
        return;
    if ( stall_last + STALL_QUIET > current_time )
    {
        stall_unwritten++;
        return;
    }
    for ( d = descriptor_list; d != NULL; d = d->next )
        if ( d->connected == CON_PLAYING )
            players++;
    snprintf( fields, sizeof(fields), "%ldms\tslowest %s %ldms\tcommand %s %ldms"
              "\t%d players\t%d more since",
              total, pulse_phase_worst, pulse_phase_ms,
              pulse_cmd[0] != '\0' ? pulse_cmd : "-", pulse_cmd_ms,
              players, stall_unwritten );
    journal_write( "stall", NULL, fields );
    stall_last = current_time;
    stall_unwritten = 0;
}

/* What a blow was: a skill or spell by name, else the weapon's noun. */
static const char *blow_noun( int dt )
{
    static int attacks = -1;

    if ( attacks < 0 )
        for ( attacks = 0; attack_table[attacks].name != NULL; attacks++ )
            ;
    if ( dt >= 0 && dt < MAX_SKILL && skill_table[dt].name != NULL )
        return skill_table[dt].name;
    if ( dt >= TYPE_HIT && dt - TYPE_HIT < attacks )
        return attack_table[dt - TYPE_HIT].name;
    return "hit";
}

/* Who struck: a mobile's vnum, -1 another player, 0 the victim themself. */
static int blow_from( CHAR_DATA *ch, CHAR_DATA *victim )
{
    if ( ch == NULL || ch == victim )
        return 0;
    if ( IS_NPC(ch) && ch->pIndexData != NULL )
        return ch->pIndexData->vnum;
    return -1;
}

/*
 * damage(), just after a player's hit points really come off: the last blow,
 * and the biggest in the last minute, so a death can say what did it --
 * one blow from full, or a slow bleed -- and a balance question has its
 * number. Memory only.
 */
void playlog_blow( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dt )
{
    PC_DATA *pc;

    if ( victim == NULL || IS_NPC(victim) || ( pc = victim->pcdata ) == NULL || dam <= 0 )
        return;
    pc->blow_last_dam = dam;
    pc->blow_last_dt = dt;
    pc->blow_last_hp = victim->hit + dam;     /* called after the subtraction */
    pc->blow_last_from = blow_from( ch, victim );
    pc->blow_last_at = current_time;
    if ( dam >= pc->blow_big_dam || pc->blow_big_at + 60 < current_time )
    {
        pc->blow_big_dam = dam;
        pc->blow_big_dt = dt;
        pc->blow_big_from = blow_from( ch, victim );
        pc->blow_big_at = current_time;
    }
}

/*
 * A player's death (raw_kill_internal): what killed them and how. The
 * killer is a mobile by vnum and short description, "player", "self"
 * (poison, a brew) or "none" (a death trap, a slay); the last blow with
 * the hit points before it and how long ago it landed -- a death with no
 * recent blow was not a fight -- the biggest blow of the last minute, the
 * maximum, how many foes were on them, wimpy, and the room's death-trap
 * flag. Never a room the journal hides.
 */
void playlog_death( CHAR_DATA *killer, CHAR_DATA *victim )
{
    char fields[PLAY_LINE];
    char who[64];
    CHAR_DATA *rch;
    PC_DATA *pc;
    int foes = 0;

    if ( victim == NULL || IS_NPC(victim) || ( pc = victim->pcdata ) == NULL )
        return;
    if ( killer == NULL )
        toc_strlcpy( who, "none", sizeof(who) );
    else if ( killer == victim )
        toc_strlcpy( who, "self", sizeof(who) );
    else if ( IS_NPC(killer) && killer->pIndexData != NULL )
    {
        char shortd[40];

        play_clean( shortd, sizeof(shortd), killer->short_descr );
        snprintf( who, sizeof(who), "mob %d %s", killer->pIndexData->vnum, shortd );
    }
    else
        toc_strlcpy( who, "player", sizeof(who) );
    if ( victim->in_room != NULL )
        for ( rch = victim->in_room->people; rch != NULL; rch = rch->next_in_room )
            if ( rch->fighting == victim )
                foes++;
    snprintf( fields, sizeof(fields),
              "%s\tkiller_lvl=%d last=%d %s hp_before=%d from=%d age=%lds"
              " big=%d %s from=%d age=%lds max_hp=%d foes=%d wimpy=%d dt_room=%d"
              " sanct=%d linkdead=%d",
              who, killer != NULL ? killer->level : 0,
              pc->blow_last_dam, pc->blow_last_at > 0 ? blow_noun( pc->blow_last_dt ) : "-",
              pc->blow_last_hp, pc->blow_last_from,
              pc->blow_last_at > 0 ? (long) ( current_time - pc->blow_last_at ) : -1L,
              pc->blow_big_dam, pc->blow_big_at > 0 ? blow_noun( pc->blow_big_dt ) : "-",
              pc->blow_big_from,
              pc->blow_big_at > 0 ? (long) ( current_time - pc->blow_big_at ) : -1L,
              victim->max_hit, foes, victim->wimpy,
              victim->in_room != NULL && IS_SET( victim->in_room->room_flags, ROOM_DT ) ? 1 : 0,
              IS_AFFECTED( victim, AFF_SANCTUARY ) ? 1 : 0,
              victim->desc == NULL ? 1 : 0 );
    journal_write( "death", victim, fields );
    pc->blow_last_at = pc->blow_big_at = 0;
    pc->blow_last_dam = pc->blow_big_dam = 0;
}

/*
 * An object a player holds, at any depth, leaving the game (extract_obj):
 * "my sword vanished" is a report nobody could answer. Quitting frees a
 * player's things through extract_obj_player, never here, so whatever
 * reaches this is gone for good -- rotted on its timer, shattered, taken
 * by a keyed quit, junked, eaten by a spell. The why is the holder's own
 * command, someone else's command, or the update phase running. Things
 * meant to be used up (food, potions, pills, scrolls, coin, herbs and
 * components, cakes, Hyrule's bombs, a key UNLOCK spends, a quest's item
 * AQUEST takes) are left out; a container counts what went with it.
 */
void playlog_obj_gone( OBJ_DATA *obj )
{
    char fields[PLAY_LINE];
    char shortd[60], why[48];
    OBJ_DATA *top, *in;
    CHAR_DATA *holder;
    int inside = 0;

    if ( obj == NULL || obj->pIndexData == NULL )
        return;
    switch ( obj->item_type )
    {
    case ITEM_POTION: case ITEM_PILL: case ITEM_FOOD: case ITEM_SCROLL:
    case ITEM_MONEY: case ITEM_HERB: case ITEM_SPELL_COMPONENT: case ITEM_CAKE:
        return;
    default:
        break;
    }
    /* Used up as meant, not lost (play journal, 2026-11-07): Hyrule's
       bombs are spent by BOMB and a new bundle folds into the one already
       carried -- a kill's bomb read as "four bombs" gone on KILL -- and a
       dungeon's small key vanishes into the lock UNLOCK opens with it. */
    if ( obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMBS )
        return;
    if ( obj->item_type == ITEM_KEY && current_set && !str_cmp( current_cmd, "unlock" ) )
        return;
    /* A quest's item handed in to the Quest Master (play journal,
       2026-11-08: three recover quests read as three things lost). */
    if ( current_set && !str_cmp( current_cmd, "aquest" ) )
        return;
    for ( top = obj; top->in_obj != NULL; top = top->in_obj )
        ;
    holder = top->carried_by;
    if ( holder == NULL || IS_NPC(holder) || holder->pcdata == NULL )
        return;
    for ( in = obj->contains; in != NULL; in = in->next_content )
        inside++;
    if ( current_set && holder->name != NULL && !str_cmp( current_name, holder->name ) )
        snprintf( why, sizeof(why), "%s", current_cmd );
    else if ( current_set )
        snprintf( why, sizeof(why), "%s (another's)", current_cmd );
    else
        snprintf( why, sizeof(why), "%s", playlog_phase != NULL ? playlog_phase : "?" );
    play_clean( shortd, sizeof(shortd), obj->short_descr );
    snprintf( fields, sizeof(fields),
              "%d\t%s\ttype=%s level=%d worn=%d nested=%d timer=%d cond=%d inside=%d\t%s",
              obj->pIndexData->vnum, shortd, item_type_name( obj ), obj->level,
              obj->wear_loc != WEAR_NONE ? 1 : 0, obj != top ? 1 : 0,
              obj->timer, obj->condition, inside, why );
    journal_write( "item", holder, fields );
}
