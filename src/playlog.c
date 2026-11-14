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

/* execinfo's backtrace() for crash.log is a GNU interface: asked for
   before any header, as POSIX is in comm.c. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

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
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
/* __GLIBC__ comes from the libc headers above; macOS and musl go without. */
#if defined(__GLIBC__)
#include <execinfo.h>
#define CRASH_BACKTRACE     1
#define CRASH_FRAMES        64
#endif
#include "merc.h"
#include "numparse.h"

#define PLAY_JOURNAL_FILE   "../log/play.tsv"
#define CRASH_LOG_FILE      "../log/crash.log"
/* Doubled when every coin, object, level, area, achievement and skill gain
   joined the journal (owner, 2026-11-10: log everything players do, so a
   bug is found by reading, not by digging). */
#define PLAY_JOURNAL_MAX    60000
#define PLAY_JOURNAL_KEEP   30000
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
static char crash_build[48];    /* the commit running, read at boot */
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
static char play_from[80];          /* playlog_from(): where a thing came from */
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

/* -------------------------------------------------- the telemetry files
 *
 * play.tsv, progress.tsv and hyrule.tsv are written the same way
 * (review, 2026-11-12: a row that did not reach the disk was counted as
 * written and nobody was told, and a trim read the file a line at a time
 * on the game loop -- and, when it could not cut, read it again for every
 * row after).
 *
 * A row is formatted whole and handed to write() once; a short or failed
 * write is cut back off the file (ftruncate to the size before it), so the
 * next row never lands on the tail of a torn one. Only a row that reached
 * the file is counted in `rows`. One that did not is counted in `lost`,
 * and toc.log hears of it at most once a TELEMETRY_REPORT_SECS -- how many
 * since the last report, why, and the count the file stands at; never the
 * row. The first loss is reported at once, and so is the recovery once a
 * report is due.
 *
 * Past `max` rows the file is cut to its newest `keep`, written aside and
 * renamed (temp_file_commit), in one sequential pass of 64K blocks (memchr,
 * not a line at a time), and the file is counted first only when its count
 * is not known (the first row after a boot). Medians on synthetic files,
 * warm / cold page cache: 40,001 progress rows (6.5 MB) went from about
 * 11 / 14 ms to 5 / 8 ms (5 / 9 counted first); 60,001 journal rows
 * (12.6 MB) from 16 / 23 ms to 8 / 15 ms (10 / 17). Not enough to move off
 * the game loop (a pulse is 250 ms). Each trim says what it took in
 * toc.log. A trim that fails is not tried again for
 * TELEMETRY_RETRY_SECS, where it used to rescan the whole file every row.
 * Rows cut from the file are not lost to analysis: the state sync commits
 * log/ every five minutes, and a trim comes every `max - keep` rows.
 * ------------------------------------------------------------------ */

#define TELEMETRY_REPORT_SECS   60
#define TELEMETRY_RETRY_SECS    60
#define TELEMETRY_BLOCK         65536

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

static char telemetry_block[TELEMETRY_BLOCK];

/* How often toc.log may hear of lost rows: TOC_TELEMETRY_REPORT_SECS
   (0 to 3600) for tests, else a minute. */
static long telemetry_report_secs( void )
{
    static long secs = -1;
    const char *env;
    long value;

    if ( secs < 0 )
    {
        secs = TELEMETRY_REPORT_SECS;
        if ( ( env = getenv( "TOC_TELEMETRY_REPORT_SECS" ) ) != NULL
        &&   parse_long( env, 0, 3600, &value ) )
            secs = value;
    }
    return secs;
}

/* "log/progress.tsv": the path as staff know it. */
static const char *telemetry_name( const TELEMETRY_LOG *log )
{
    return !strncmp( log->path, "../", 3 ) ? log->path + 3 : log->path;
}

static void telemetry_count_text( const TELEMETRY_LOG *log, char *buf, size_t size )
{
    if ( log->rows < 0 )
        snprintf( buf, size, "not counted yet" );
    else
        snprintf( buf, size, "%ld row%s counted in the file", log->rows,
                  log->rows == 1 ? "" : "s" );
}

/* A row that did not reach the file. */
static void telemetry_lost( TELEMETRY_LOG *log, const char *what, int err )
{
    char buf[MAX_STRING_LENGTH], count[64];

    if ( err != 0 )
        snprintf( log->why, sizeof(log->why), "%s: %s", what, strerror( err ) );
    else
        toc_strlcpy( log->why, what, sizeof(log->why) );
    if ( log->lost < LONG_MAX )
        log->lost++;
    if ( log->reported != 0 && current_time - log->reported < telemetry_report_secs() )
        return;
    telemetry_count_text( log, count, sizeof(count) );
    snprintf( buf, sizeof(buf),
              "Telemetry: %s: %ld row%s not written since the last report (%s); %s.",
              telemetry_name( log ), log->lost, log->lost == 1 ? "" : "s",
              log->why, count );
    log_string( buf );
    log->reported = current_time;
    log->lost = 0;
}

/* A row that did: if rows were lost and a report is due, say it is over. */
static void telemetry_wrote( TELEMETRY_LOG *log )
{
    char buf[MAX_STRING_LENGTH], count[64];

    if ( log->rows >= 0 && log->rows < LONG_MAX )
        log->rows++;
    if ( log->lost == 0
    ||   ( log->reported != 0 && current_time - log->reported < telemetry_report_secs() ) )
        return;
    telemetry_count_text( log, count, sizeof(count) );
    snprintf( buf, sizeof(buf),
              "Telemetry: %s: writing again; %ld row%s not written before it did (%s); %s.",
              telemetry_name( log ), log->lost, log->lost == 1 ? "" : "s",
              log->why, count );
    log_string( buf );
    log->reported = current_time;
    log->lost = 0;
}

static void telemetry_close( TELEMETRY_LOG *log )
{
    if ( log->fd >= 0 )
    {
        close( log->fd );
        log->fd = -1;
    }
}

static void telemetry_trim_failed( TELEMETRY_LOG *log, const char *what, int err )
{
    char buf[MAX_STRING_LENGTH];

    log->trim_after = current_time + TELEMETRY_RETRY_SECS;
    snprintf( buf, sizeof(buf), "Telemetry: %s could not be trimmed (%s%s%s); "
              "it is kept whole and tried again in %d seconds.",
              telemetry_name( log ), what, err != 0 ? ": " : "",
              err != 0 ? strerror( err ) : "", TELEMETRY_RETRY_SECS );
    log_string( buf );
}

/* Newlines in a block. */
static long telemetry_newlines( const char *p, size_t n )
{
    const char *end = p + n;
    long count = 0;

    while ( p < end && ( p = memchr( p, '\n', (size_t) ( end - p ) ) ) != NULL )
    {
        count++;
        p++;
    }
    return count;
}

/*
 * Past `max` rows, keep the newest `keep`, in one pass from the start: the
 * rows before the cut are counted through, the rest copied aside a block
 * at a time. The whole file is read once, in order -- a cold cache's
 * readahead wants that, and reading back from the end was slower cold.
 * The count is taken first only when it is not known (the first row after
 * a boot); the rows copied are counted, so a count that had drifted is put
 * right by the trim.
 */
static void telemetry_trim( TELEMETRY_LOG *log )
{
    char temp[256], buf[MAX_STRING_LENGTH];
    struct stat st;
    FILE *in, *out;
    long start = playlog_now_ms(), before, skip, seen = 0, kept = 0;
    size_t n;
    bool cutting = true;
    int err;

    telemetry_close( log );
    if ( !toc_path_join( temp, sizeof(temp), log->path, "", ".tmp" ) )
    {
        telemetry_trim_failed( log, "path too long", 0 );
        return;
    }
    if ( ( in = fopen( log->path, "rb" ) ) == NULL )
    {
        if ( errno == ENOENT )
            log->rows = 0;
        else
            telemetry_trim_failed( log, "open", errno );
        return;
    }
    /* A directory or a device (/dev/full reads zeros for ever) is no log. */
    if ( fstat( fileno( in ), &st ) != 0 || !S_ISREG( st.st_mode ) )
    {
        fclose( in );
        telemetry_trim_failed( log, "not a regular file", 0 );
        return;
    }
    if ( log->rows < 0 )
    {
        long total = 0;

        while ( ( n = fread( telemetry_block, 1, sizeof(telemetry_block), in ) ) > 0 )
            total += telemetry_newlines( telemetry_block, n );
        if ( ferror( in ) )
        {
            err = errno;
            fclose( in );
            telemetry_trim_failed( log, "read", err );
            return;
        }
        log->rows = total;
        if ( total < log->max )
        {
            fclose( in );
            return;
        }
        rewind( in );
    }
    before = log->rows;
    skip = log->rows - log->keep;
    cutting = skip > 0;
    if ( ( out = fopen( temp, "wb" ) ) == NULL )
    {
        err = errno;
        fclose( in );
        telemetry_trim_failed( log, "write aside", err );
        return;
    }
    /* Rows before the cut are passed over; a last row with no newline
       (none should be: a torn row is cut back) is kept with the rest. */
    while ( ( n = fread( telemetry_block, 1, sizeof(telemetry_block), in ) ) > 0 )
    {
        const char *from = telemetry_block, *end = telemetry_block + n;

        while ( cutting && from < end )
        {
            const char *nl = memchr( from, '\n', (size_t) ( end - from ) );

            if ( nl == NULL )
            {
                from = end;
                break;
            }
            from = nl + 1;
            if ( ++seen >= skip )
                cutting = false;
        }
        if ( cutting || from >= end )
            continue;
        kept += telemetry_newlines( from, (size_t) ( end - from ) );
        if ( fwrite( from, 1, (size_t) ( end - from ), out ) != (size_t) ( end - from ) )
            break;
    }
    if ( ferror( in ) )
    {
        err = errno;
        fclose( in );
        fclose( out );
        remove( temp );
        telemetry_trim_failed( log, "read", err );
        return;
    }
    fclose( in );
    if ( cutting )
    {
        /* The file held fewer rows than counted (cut short by hand?): it
           is left as it is, never replaced by nothing, and recounted. */
        fclose( out );
        remove( temp );
        log->rows = seen;
        return;
    }
    /* temp_file_commit checks the write as well as the close: a full disk
       renamed a short journal over the whole one. */
    if ( !temp_file_commit( out, temp, log->path ) )
    {
        telemetry_trim_failed( log, "replace", 0 );
        return;
    }
    log->rows = kept;
    snprintf( buf, sizeof(buf), "Telemetry: %s trimmed from %ld to %ld rows in %ld ms.",
              telemetry_name( log ), before, kept, playlog_now_ms() - start );
    log_string( buf );
}

/*
 * Append one row, formatted by the caller: `formatted` is what snprintf
 * returned for a buffer of `size`, so a row it had to cut is refused (and
 * counted lost) rather than written without its end. True when the whole
 * row reached the file.
 */
bool telemetry_append( TELEMETRY_LOG *log, const char *row, int formatted, size_t size )
{
    size_t len, done = 0;
    off_t before;
    int err = 0;

    if ( !snprintf_fits( formatted, size ) )
    {
        telemetry_lost( log, "a row longer than its buffer", 0 );
        return false;
    }
    len = (size_t) formatted;
    if ( ( log->rows < 0 || log->rows >= log->max ) && current_time >= log->trim_after )
        telemetry_trim( log );
    if ( log->fd < 0
    &&   ( log->fd = open( log->path, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0666 ) ) < 0 )
    {
        telemetry_lost( log, "open", errno );
        return false;
    }
    before = lseek( log->fd, 0, SEEK_END );
    while ( done < len )
    {
        ssize_t w = write( log->fd, row + done, len - done );

        if ( w < 0 && errno == EINTR )
            continue;
        if ( w <= 0 )
        {
            err = w < 0 ? errno : EIO;
            break;
        }
        done += (size_t) w;
    }
    if ( done < len )
    {
        /* Cut a torn row back off, so the next one starts a line. */
        if ( done > 0 && before >= 0 && ftruncate( log->fd, before ) != 0 )
            err = err != 0 ? err : errno;
        telemetry_close( log );
        telemetry_lost( log, "write", err );
        return false;
    }
    if ( !log->hold_open )
    {
        err = close( log->fd ) != 0 ? errno : 0;
        log->fd = -1;
        if ( err != 0 )
        {
            telemetry_lost( log, "close", err );
            return false;
        }
    }
    telemetry_wrote( log );
    return true;
}

/* Held open, like log_string's: a command a line, and an open and close
   for each is a filesystem round trip in the middle of the game loop. */
static TELEMETRY_LOG journal_log =
    TELEMETRY_LOG_INIT( PLAY_JOURNAL_FILE, PLAY_JOURNAL_MAX, PLAY_JOURNAL_KEEP, true );

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
static void journal_write_at( const char *kind, CHAR_DATA *ch, const char *fields,
                              bool unplaced );

static void journal_write( const char *kind, CHAR_DATA *ch, const char *fields )
{
    journal_write_at( kind, ch, fields, false );
}

/* `unplaced`: the row is about somewhere the actor's room would give
   away (encounter.c's rows about a room the dealer stands in, written
   once the player has left it), so the room and area columns are "-". */
static void journal_write_at( const char *kind, CHAR_DATA *ch, const char *fields,
                              bool unplaced )
{
    /* The common columns are at most about 170 bytes and every writer's
       fields fit PLAY_LINE; a row that would not fit is refused whole by
       telemetry_append, never written without its end. */
    char row[PLAY_LINE + 256], room[16], area[64], name[32];
    int n;

    if ( journal_busy || play_hidden( ch ) )
        return;
    journal_busy = true;
    if ( unplaced )
    {
        snprintf( room, sizeof(room), "-" );
        snprintf( area, sizeof(area), "-" );
    }
    else
        play_room( ch, room, sizeof(room), area, sizeof(area) );
    play_clean( name, sizeof(name), ch != NULL ? ch->name : "-" );
    n = snprintf( row, sizeof(row), "%ld\t%s\t%s\t%d\t%s\t%s\t%s\n", (long) current_time,
                  kind, name, ch != NULL ? ch->level : 0, room, area, fields );
    /* A write a row: the state sync reads the file every five minutes. */
    telemetry_append( &journal_log, row, n, sizeof(row) );
    journal_busy = false;
}

/* For encounter.c: a row of its own kind through the same writer and
   rules (wizinvis writes nothing, the dealer's room is "-"), text made
   safe for a column, and whose command is running. */
void playlog_row( const char *kind, CHAR_DATA *ch, const char *fields )
{
    journal_write( kind, ch, fields );
}

void playlog_row_unplaced( const char *kind, CHAR_DATA *ch, const char *fields )
{
    journal_write_at( kind, ch, fields, true );
}

/* True while a wizinvis player's command runs: a row about something else
   that the command caused (an object cleared off the floor) is theirs too,
   and wizinvis staff leave no trace in the journal. */
bool playlog_hidden_command( void )
{
    return current_set && current_hidden;
}

void playlog_clean( char *dest, size_t size, const char *src )
{
    play_clean( dest, size, src );
}

/* True while ch's own typed command is running: what a player chose to
   do, as against a mobile's attack or a tick. */
bool playlog_own_command( CHAR_DATA *ch )
{
    return current_set && ch != NULL && ch->name != NULL
        && !str_cmp( ch->name, current_name );
}

/* Who or what is doing it now, for a row about a thing rather than a
   player: "<name>:<command>", "-" for a wizinvis command, or the update
   phase in brackets. */
const char *playlog_actor( void )
{
    static char actor[96];

    if ( !current_set )
        snprintf( actor, sizeof(actor), "(%s)", playlog_phase );
    else if ( current_hidden )
        snprintf( actor, sizeof(actor), "-" );
    else
        snprintf( actor, sizeof(actor), "%s:%s", current_name,
                  current_cmd[0] != '\0' ? current_cmd : "-" );
    return actor;
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
        if ( crash_build[0] != '\0' )
        {
            crash_write( crash_fd, "build " );
            crash_write( crash_fd, crash_build );
            crash_write( crash_fd, "\n" );
        }
#if defined(CRASH_BACKTRACE)
        /* backtrace() was called once at boot, so libgcc is loaded and it
           allocates nothing here; backtrace_symbols_fd writes straight to
           the descriptor. */
        {
            void *frames[CRASH_FRAMES];
            int depth = backtrace( frames, CRASH_FRAMES );

            crash_write( crash_fd, "--- backtrace ---\n" );
            backtrace_symbols_fd( frames, depth, crash_fd );
        }
#endif
        crash_write( crash_fd, "=== end ===\n" );
    }
    signal( sig, SIG_DFL );
    raise( sig );
}

/*
 * The code running, for crash.log: the deploy writes the live tree's
 * .code-revision ("<commit> <merc sha256>") and log/deployed-commit; the
 * first word of whichever is there. Read at boot, never in the handler.
 */
static void crash_read_build( void )
{
    static const char *const sources[] = { "../.code-revision", "../log/deployed-commit" };
    size_t i;

    crash_build[0] = '\0';
    for ( i = 0; i < sizeof(sources) / sizeof(sources[0]); i++ )
    {
        FILE *fp = fopen( sources[i], "r" );
        char word[64];

        if ( fp == NULL )
            continue;
        if ( fscanf( fp, "%63s", word ) == 1 )
        {
            size_t n;

            for ( n = 0; word[n] != '\0'; n++ )
                if ( !isxdigit( (unsigned char) word[n] ) )
                    break;
            if ( word[n] == '\0' && n >= 7 )
                toc_strlcpy( crash_build, word, sizeof(crash_build) );
        }
        fclose( fp );
        if ( crash_build[0] != '\0' )
            return;
    }
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
    crash_read_build( );
#if defined(CRASH_BACKTRACE)
    /* The first backtrace() loads libgcc's unwinder, which allocates: done
       here, so the handler's call does not. */
    {
        void *warm[2];

        (void) backtrace( warm, 2 );
    }
#endif
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
    play_from[0] = '\0';
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

    if ( !is_staff( ch ) )
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
        diary_coin( ch, true, coin_override != NULL ? coin_override
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
    if ( kind != COIN_SPENT )
        diary_coin( ch, false, coin_source_names[kind], copper );   /* diary.c */

    /* Every change of purse, one row: how much, which tally it went to,
       the command, where it came from (the corpse or box, the keeper),
       and what the character is worth after it, purse and bank -- so a
       jump in wealth is read, not reconstructed (owner, 2026-11-10). */
    {
        char fields[PLAY_LINE];
        char from[80];

        play_clean( from, sizeof(from), play_from[0] != '\0' ? play_from : "-" );
        snprintf( fields, sizeof(fields), "%s%ld\t%s\t%s\t%s\t%ld",
                  amount < 0 ? "-" : "+", copper,
                  kind == COIN_SPENT ? "spent" : coin_source_names[kind],
                  playlog_how( ch ), from, play_wealth( ch ) );
        journal_write( "coin", ch, fields );
    }
}

/* Where the thing a command moves came from -- the container GET takes it
   from, the keeper BUY buys from -- for the coin and got rows this command
   writes. Cleared when the command ends. */
void playlog_from( const char *where )
{
    if ( where == NULL )
        play_from[0] = '\0';
    else
        play_clean( play_from, sizeof(play_from), where );
}

/* The bank's own changes, which no purse function sees: interest. */
void playlog_bank( CHAR_DATA *ch, long copper, const char *why )
{
    char fields[PLAY_LINE];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || copper == 0 )
        return;
    diary_coin( ch, copper < 0, copper < 0 ? "bank" : "interest",
                copper < 0 ? ( copper == LONG_MIN ? LONG_MAX : -copper ) : copper );
    snprintf( fields, sizeof(fields), "%s%ld\t%s\t%s\t%s\t%ld",
              copper < 0 ? "-" : "+", copper < 0 ? -copper : copper,
              "bank", why != NULL ? why : "-", "bank", play_wealth( ch ) );
    journal_write( "coin", ch, fields );
}

/* Every object reaching a playing character (obj_to_char), with how and
   from where: looted, bought, given, made, restored. Coin piles are the
   coin rows'. */
void playlog_got( CHAR_DATA *ch, OBJ_DATA *obj )
{
    char fields[PLAY_LINE];
    char name[80], from[80];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || obj == NULL
    ||   obj->pIndexData == NULL || obj->item_type == ITEM_MONEY
    ||   ch->desc == NULL || ch->desc->connected != CON_PLAYING )
        return;
    play_clean( name, sizeof(name), obj->short_descr );
    play_clean( from, sizeof(from), play_from[0] != '\0' ? play_from : "-" );
    snprintf( fields, sizeof(fields), "%d\t%s\t%s\t%d\t%ld\t%s\t%s",
              obj->pIndexData->vnum, name, item_type_name( obj ), obj->level,
              (long) obj->cost, playlog_how( ch ), from );
    journal_write( "got", ch, fields );
    diary_got( ch, obj );                       /* diary.c */
}

/* A level gained (advance_level): from, to, how long the last one took. */
void playlog_level( CHAR_DATA *ch, int from, bool is_advance )
{
    char fields[PLAY_LINE];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    snprintf( fields, sizeof(fields), "%d\t%d\t%s\t%d\t%ld\t%ld\t%s",
              from, ch->level,
              ch->class >= 0 && ch->class < MAX_CLASS ? class_table[ch->class].who_name : "?",
              ch->pcdata->num_remorts, ch->exp,
              ch->pcdata->play_level_at > 0
                  ? (long) ( current_time - ch->pcdata->play_level_at ) : -1L,
              is_advance ? "advance" : playlog_how( ch ) );
    ch->pcdata->play_level_at = current_time;
    journal_write( "level", ch, fields );
    diary_level( ch, from );                    /* diary.c */
}

/* From char_to_room: a player crossing into another area, with the time
   spent in the one left and how they went (a command, a recall, death). */
void playlog_moved( CHAR_DATA *ch )
{
    char fields[PLAY_LINE];
    char was[64], now[64];
    AREA_DATA *area;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->in_room == NULL
    ||   ch->desc == NULL || ch->desc->connected != CON_PLAYING )
        return;
    diary_moved( ch );                          /* diary.c: time in each area */
    area = ch->in_room->area;
    if ( area == ch->pcdata->play_area )
        return;
    play_clean( was, sizeof(was), ch->pcdata->play_area != NULL
                                  ? ch->pcdata->play_area->file_name : "-" );
    play_clean( now, sizeof(now), area != NULL ? area->file_name : "-" );
    snprintf( fields, sizeof(fields), "%s\t%s\t%ld\t%s", was, now,
              ch->pcdata->play_area != NULL && ch->pcdata->play_area_since > 0
                  ? (long) ( current_time - ch->pcdata->play_area_since ) : -1L,
              playlog_how( ch ) );
    ch->pcdata->play_area = area;
    ch->pcdata->play_area_since = current_time;
    /* Never into or out of a room the dealer or goblin hides in: the
       journal names the area, not the room, but journal_write's common
       columns would name the room, and room_hides_from_log blanks it. */
    journal_write( "area", ch, fields );
}

void playlog_achieved( CHAR_DATA *ch, const char *key, int points, int total )
{
    char fields[PLAY_LINE];
    char what[80];

    if ( ch == NULL || IS_NPC(ch) )
        return;
    play_clean( what, sizeof(what), key );
    snprintf( fields, sizeof(fields), "%s\t%d\t%d\t%s", what, points, total,
              playlog_how( ch ) );
    journal_write( "achieved", ch, fields );
}

/* check_improve's gain: the skill, before and after, and whether it came
   from a success or from learning from a mistake. */
void playlog_skill( CHAR_DATA *ch, int sn, int before, bool from_success )
{
    char fields[PLAY_LINE];
    char name[64];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || sn < 0 || sn >= MAX_SKILL )
        return;
    play_clean( name, sizeof(name), skill_table[sn].name );
    snprintf( fields, sizeof(fields), "%s\t%d\t%d\t%s\t%s", name, before,
              ch->pcdata->learned[sn], from_success ? "success" : "mistake",
              playlog_how( ch ) );
    journal_write( "skill", ch, fields );
    diary_skill( ch, sn, before );              /* diary.c */
}

/* A quest handed out: its kind, what to do, the target, its level and
   area file (never the room), and the minutes given. */
void playlog_quest( CHAR_DATA *ch, const char *kind, const char *target, int vnum,
                    const char *name, int level, const char *area, int minutes )
{
    char fields[PLAY_LINE];
    char what[80], where[64];

    if ( ch == NULL || IS_NPC(ch) )
        return;
    play_clean( what, sizeof(what), name );
    play_clean( where, sizeof(where), area );
    snprintf( fields, sizeof(fields), "%s\t%s\t%d\t%s\t%d\t%s\t%d",
              kind, target, vnum, what, level, where, minutes );
    journal_write( "quest", ch, fields );
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
    if ( !capped )
        diary_exp( ch, amount );                /* diary.c */
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
    encounter_session_end( ch, how );   /* passed by, and the sightings */
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
 * (never a name -- reports count independent histories by it: the file's
 * Id until 2026-11-12, which two characters could share, and the
 * character's serial since, 65536 and up and unique; save.c), level, class, remorts, hp%, mana%, foe vnum, foe level, area file,
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

static TELEMETRY_LOG progress_log =
    TELEMETRY_LOG_INIT( PROGRESS_FILE, PROGRESS_MAX, PROGRESS_KEEP, false );

/* Durations only -- a pulse, a fight, a command -- so on the monotonic
   clock (comm.c, monotonic_ms): a wall-clock step no longer reads as a
   stall or a negative fight. */
long playlog_now_ms( void )
{
    return monotonic_ms();
}

/*
 * The balance feed (owner, 2026-11-10: "log everything in a way that'll
 * allow you to balance the game learning from players who play"). Every
 * row is numbers and vnums: a character's serial, never a name (rows
 * before 2026-11-12 carry the file Id, below 65536, which two characters
 * could share -- such rows may merge them; see webadmin/balance.py), an area
 * file, never a room, and nothing typed or said. Staff write none -- what
 * an immortal's kills take is no measure of anything -- and nor does a
 * wizinvis player. The rows, after the eleven columns every row has
 * (epoch, kind, Id, level, class, remorts, hp%, mana%, foe vnum, foe
 * level, area file):
 *
 *   engage  a mobile entering a fight with a player: the encounter id,
 *           the foe's max hp, the player's hp, max hp, mana, max mana,
 *           players and pets of their group in the room, gear tier, buffs,
 *           then what CONSIDER would have said, unasked: the player's and
 *           the foe's damage a round, the rounds each would need, the
 *           verdict (scratch easily win narrow even lose die), caster
 *   slain   one per mobile death that credits anybody: the encounter id
 *           (the kill id), encounter ms, how (blow or instant), by whom
 *           (player or pet), players credited, pets of the group there,
 *           the foe's max hp, the hit points that came off it, of them by
 *           pets, what it took off players, the coin it carried (copper),
 *           the rounds it fought, players' melee swings at it, the swings
 *           that took hit points, and the hit points spells and skills
 *           took (CONSIDER counts weapon blows only, every one landing)
 *   reward  one per player the kill pays (a kill's old row, the column
 *           layout kept): encounter ms, base, rested and accepted xp,
 *           group members, guild, buffs, the player's own fight ledger
 *           (dealt, lost, healed, mana, lost outside blows), coin, foe max
 *           hp; then the kill id, foes fighting them at the kill (the
 *           ledger is the whole melee's when that is more than one), gear
 *           tier, hp and mana at the fight's start and their maxima
 *   flee, death  how much of the foe was left (hp%), its max hp, the hit
 *           points the fight cost, the encounter id
 *   fled    the mobile ran (do_flee): laid out as a flee row
 *   parted  a fight that stopped otherwise (PEACE, the player gone or
 *           asleep): a flee row's columns, then how ("stopped")
 *   drop    what the corpse was made with: the kill id, objects, worth
 *           (copper), highest level, then vnum:source for the first few
 *   consider  a CONSIDER typed: the player's and the foe's damage a
 *           round, the rounds each would need, the verdict, hp each, caster
 *   loot    an object or a coin pile taken out of a corpse by a player:
 *           the kill id, coin or obj, vnum, worth (copper), level,
 *           source, the command, players of the group in the room
 *
 * Before 2026-11-10 a kill wrote one "kill" row per player it paid, so a
 * group kill read as several: tools read those as legacy rows and say so.
 */

/* An encounter id: this boot's start and a count, so ids never repeat
   across restarts and need no state on the disk. */
static long progress_boot_epoch;
static long progress_counter;

long progress_encounter_id( CHAR_DATA *mob )
{
    if ( mob == NULL )
        return 0;
    if ( mob->encounter_seq <= 0 )
    {
        if ( progress_boot_epoch == 0 )
            progress_boot_epoch = (long) current_time;
        mob->encounter_seq = ++progress_counter;
        mob->enc_taken = mob->enc_by_pets = mob->enc_dealt = 0;
        mob->enc_rounds = 0;
        mob->enc_swings = mob->enc_landed = 0;
        mob->enc_by_skills = 0;
    }
    return mob->encounter_seq;
}

static const char *encounter_text( long seq, char *buf, size_t size )
{
    if ( seq <= 0 )
        return "-";
    if ( progress_boot_epoch == 0 )
        progress_boot_epoch = (long) current_time;
    snprintf( buf, size, "%ld-%ld", progress_boot_epoch, seq );
    return buf;
}

/* The player a mobile's fight or kill belongs to: the player, or the
   master of a pet or servant. NULL for anything else. */
static CHAR_DATA *progress_player( CHAR_DATA *ch )
{
    if ( ch == NULL )
        return NULL;
    if ( IS_NPC(ch) && ch->master != NULL && !IS_NPC(ch->master)
    &&   IS_AFFECTED(ch, AFF_CHARM) )
        ch = ch->master;
    return IS_NPC(ch) || ch->pcdata == NULL ? NULL : ch;
}

/* A coarse gear tier: the average level of what is worn, or -1. */
static int progress_gear_tier( CHAR_DATA *ch )
{
    OBJ_DATA *obj;
    long sum = 0;
    int n = 0;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->wear_loc != WEAR_NONE )
        {
            sum += obj->level;
            n++;
        }
    return n > 0 ? (int) ( sum / n ) : -1;
}

static void progress_buffs( CHAR_DATA *ch, char *buffs )
{
    int n = 0;

    if ( is_affected( ch, gsn_titanic ) ) buffs[n++] = 'T';
    if ( is_affected( ch, gsn_empower ) ) buffs[n++] = 'E';
    if ( IS_AFFECTED( ch, AFF_SANCTUARY ) ) buffs[n++] = 'S';
    if ( IS_AFFECTED( ch, AFF_HASTE ) ) buffs[n++] = 'H';
    if ( n == 0 )
        buffs[n++] = '-';
    buffs[n] = '\0';
}

/* Players and pets of ch's group standing with them. */
static void progress_party( CHAR_DATA *ch, int *players, int *pets )
{
    CHAR_DATA *gch;

    *players = *pets = 0;
    if ( ch == NULL || ch->in_room == NULL )
        return;
    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
        if ( is_same_group( gch, ch ) )
        {
            if ( IS_NPC(gch) )
                (*pets)++;
            else
                (*players)++;
        }
}

static void progress_write_raw( const char *kind, CHAR_DATA *ch, int vnum, int level,
                                const char *area, const char *tail )
{
    /* Eleven numeric columns and an area file name, then a tail of at
       most 511 bytes (the writers' buffers): 1024 holds any of them. */
    char row[1024];
    int hp_pct, mana_pct, n;

    /* Immortals by level write nothing; a mortal trusted with staff
       commands is a player and is counted (owner, 2026-11-12). */
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || play_hidden( ch )
    ||   IS_IMMORTAL( ch ) )
        return;
    hp_pct = ch->max_hit > 0 ? (int) ( 100L * ch->hit / ch->max_hit ) : 0;
    mana_pct = ch->max_mana > 0 ? (int) ( 100L * ch->mana / ch->max_mana ) : 0;
    n = snprintf( row, sizeof(row), "%ld\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s%s%s\n",
                  (long) current_time, kind, player_serial( ch ), ch->level, ch->class,
                  ch->pcdata->num_remorts, hp_pct, mana_pct, vnum, level,
                  area != NULL && area[0] != '\0' ? area : "-",
                  tail[0] != '\0' ? "\t" : "", tail );
    telemetry_append( &progress_log, row, n, sizeof(row) );
}

static void progress_write( const char *kind, CHAR_DATA *ch, CHAR_DATA *foe, const char *tail )
{
    const char *area = "-";

    if ( foe == NULL || !IS_NPC(foe) || foe->pIndexData == NULL || is_unfindable_mob( foe ) )
        return;
    if ( foe->in_room != NULL && foe->in_room->area != NULL
    &&   foe->in_room->area->file_name != NULL )
        area = foe->in_room->area->file_name;
    progress_write_raw( kind, ch, foe->pIndexData->vnum, foe->level, area, tail );
}

/* A mobile entering a fight (set_fighting): the encounter begins. */
void progress_engage( CHAR_DATA *mob, CHAR_DATA *opponent )
{
    CHAR_DATA *pc = progress_player( opponent );
    char tail[384], id[48], buffs[8];
    double yours = 0, theirs = 0, your_rounds = 0, their_rounds = 0;
    const char *verdict = "-";
    bool caster = false;
    int players, pets;

    if ( mob == NULL || !IS_NPC(mob) )
        return;
    mob->encounter_seq = 0;
    mob->enc_open = false;
    mob->enc_with = 0;
    progress_encounter_id( mob );
    if ( pc == NULL || pc->in_room == NULL || pc->in_room != mob->in_room
    ||   IS_IMMORTAL( pc ) || play_hidden( pc ) || is_unfindable_mob( mob ) )
        return;
    progress_party( pc, &players, &pets );
    progress_buffs( pc, buffs );
    /* What CONSIDER would have told them, said to nobody (owner,
       2026-11-10: every fight held to it, whether or not the player
       asked): each side's damage a round, the rounds each would need,
       the verdict. The slain row's rounds and the mobile's ledger are
       what it came to. */
    verdict = consider_predict( pc, mob, &yours, &theirs, &your_rounds, &their_rounds, &caster );
    mob->enc_open = true;
    mob->enc_with = player_serial( pc );
    mob->enc_left_ms = 0;
    snprintf( tail, sizeof(tail),
              "%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%.1f\t%.1f\t%.1f\t%.1f\t%s\t%d",
              encounter_text( mob->encounter_seq, id, sizeof(id) ), mob->max_hit,
              pc->hit, pc->max_hit, pc->mana, pc->max_mana, players, pets,
              progress_gear_tier( pc ), buffs, yours, theirs, your_rounds, their_rounds,
              verdict, caster ? 1 : 0 );
    progress_write( "engage", pc, mob, tail );
}

/* One row per mobile death that credits anybody (group_gain). */
void progress_slain( CHAR_DATA *killer, CHAR_DATA *victim, int players, int pets )
{
    CHAR_DATA *pc = progress_player( killer );
    char tail[320], id[48];
    long encounter;

    if ( victim == NULL || !IS_NPC(victim) || pc == NULL )
        return;
    progress_encounter_id( victim );
    encounter = victim->fight_began_ms > 0 ? playlog_now_ms() - victim->fight_began_ms : -1;
    snprintf( tail, sizeof(tail), "%s\t%ld\t%s\t%s\t%d\t%d\t%d\t%ld\t%ld\t%ld\t%ld\t%d\t%d\t%d\t%ld",
              encounter_text( victim->encounter_seq, id, sizeof(id) ), encounter,
              victim->hit > 0 ? "instant" : "blow",
              IS_NPC(killer) ? "pet" : "player", players, pets, victim->max_hit,
              victim->enc_taken, victim->enc_by_pets, victim->enc_dealt,
              coins_to_copper( victim ), victim->enc_rounds, victim->enc_swings,
              victim->enc_landed, victim->enc_by_skills );
    progress_write( "slain", pc, victim, tail );
    victim->enc_open = false;
    consider_learn_fight( pc, victim, players, pets );   /* act_info.c */
}

void progress_kill( CHAR_DATA *gch, CHAR_DATA *victim, int base_xp, int rested_xp,
                    long accepted_xp, int members, long victim_coin )
{
    char tail[512], id[48], buffs[8];
    long encounter = victim != NULL && victim->fight_began_ms > 0
                   ? playlog_now_ms() - victim->fight_began_ms : -1;
    PC_DATA *pc = gch != NULL && !IS_NPC(gch) ? gch->pcdata : NULL;
    CHAR_DATA *rch;
    int foes = 1;
    bool fought;

    /* The fight in aggregate, for balance (class review, 2026-10-26):
       the guild, the buffs worn (T titanic, E empower, S sanctuary,
       H haste), and from the fight's ledger -- everything since this
       character's own fight began (set_fighting), which is the kill's
       encounter for a fight with one foe and the whole melee for one with
       several, so the foes column says which -- the damage dealt; the hit
       points lost, every way; the hit points seen to rise (healing,
       regeneration, drains: never negative); the mana spent; and of the
       losses, those outside damage() (reflection, traps). Numbers only --
       nothing typed, said or named. */
    if ( pc == NULL || victim == NULL )
        return;
    /* A member of the group who never struck has no fight of their own:
       their ledger is an old fight's, or nothing, so it is written as
       zeros and foes as 0 (review, 2026-11-10: a bystander's read as
       five thousand hit points healed). A fight that ended with this kill
       ended a moment ago. */
    fought = pc->meter_active
          || ( pc->fight_stopped_ms > 0 && playlog_now_ms() - pc->fight_stopped_ms < 5000 );
    progress_buffs( gch, buffs );
    if ( !fought )
    {
        snprintf( tail, sizeof(tail),
                  "%ld\t%d\t%d\t%ld\t%d\t%d\t%s\t0\t0\t0\t0\t0\t%ld\t%d"
                  "\t%s\t0\t%d\t%d\t%d\t%d\t%d",
                  encounter, base_xp, rested_xp, accepted_xp, members, pc->guild, buffs,
                  victim_coin, victim->max_hit,
                  encounter_text( victim->encounter_seq, id, sizeof(id) ),
                  progress_gear_tier( gch ), gch->hit, gch->max_hit, gch->mana, gch->max_mana );
        progress_write( "reward", gch, victim, tail );
        return;
    }
    fight_ledger_observe( gch );
    if ( gch->in_room != NULL )
        for ( rch = gch->in_room->people; rch != NULL; rch = rch->next_in_room )
            if ( rch != victim && IS_NPC(rch) && rch->fighting == gch )
                foes++;
    snprintf( tail, sizeof(tail),
              "%ld\t%d\t%d\t%ld\t%d\t%d\t%s\t%ld\t%ld\t%ld\t%d\t%ld\t%ld\t%d"
              "\t%s\t%d\t%d\t%d\t%d\t%d\t%d",
              encounter, base_xp, rested_xp, accepted_xp, members,
              pc->guild, buffs, pc->meter_damage,
              pc->fight_taken + pc->fight_direct, pc->fight_healed,
              pc->fight_mana_start - gch->mana, pc->fight_direct, victim_coin,
              victim->max_hit,
              encounter_text( victim->encounter_seq, id, sizeof(id) ), foes,
              progress_gear_tier( gch ), pc->fight_hp_start, gch->max_hit,
              pc->fight_mana_start, gch->max_mana );
    progress_write( "reward", gch, victim, tail );
}

/* kind is "flee" or "death"; foe is the mobile it was against. The tail
   is how much of the foe was left -- its hit points as a percentage of
   its maximum, and that maximum -- what the fight had cost the character
   (the hit points lost every way), and the encounter. A flee at a foe's
   90% is a foe out of its depth; at 10%, a close call. */
void progress_event( CHAR_DATA *ch, const char *kind, CHAR_DATA *foe )
{
    char tail[128], id[48];
    PC_DATA *pc = ch != NULL && !IS_NPC(ch) ? ch->pcdata : NULL;

    if ( foe == NULL )
        return;
    snprintf( tail, sizeof(tail), "%d\t%d\t%ld\t%s",
              foe->max_hit > 0 ? (int) ( 100L * UMAX( 0, foe->hit ) / foe->max_hit ) : 0,
              foe->max_hit,
              pc != NULL ? pc->fight_taken + pc->fight_direct : 0L,
              encounter_text( foe->encounter_seq, id, sizeof(id) ) );
    progress_write( kind, ch, foe, tail );
    if ( IS_NPC(foe) )
        foe->enc_open = false;
}

/* A chase is one encounter (2026-11-14: 35 of the first 125 encounters
   had no outcome, most of them a mobile that fled, was followed and was
   fought again under a new id, whose prediction was made against a
   wounded foe and whose ledger began at the second fight). A mobile
   that comes back into a fight with the same player within
   ENC_RESUME_MS of its last one stopping carries on the
   encounter it was in: the same id, ledger and start, and no second
   engage row -- healed or not: a test run under load saw the tick heal a
   lightly wounded guard to full while it was chased, and the two
   minutes and the one player are what make it a chase. The rounds are the rounds it fought (enc_rounds); the
   slain row's milliseconds include the chase. */
#define ENC_RESUME_MS   120000L

bool progress_resume( CHAR_DATA *mob, CHAR_DATA *opponent )
{
    CHAR_DATA *pc = progress_player( opponent );

    if ( mob == NULL || !IS_NPC(mob) || pc == NULL || mob->encounter_seq <= 0
    ||   mob->enc_with == 0 || mob->enc_with != player_serial( pc ) )
        return false;
    /* The same fight entered from its other side: the player's
       set_fighting engaged the mobile, then the mobile's own follows
       (a spell's order), or the other way about after a resume. */
    if ( mob->enc_open && mob->enc_left_ms <= 0 )
        return true;
    if ( mob->enc_left_ms <= 0
    ||   playlog_now_ms() - mob->enc_left_ms > ENC_RESUME_MS )
        return false;
    mob->enc_open = true;
    mob->enc_left_ms = 0;
    return true;
}

/* A mobile's fight stopping (stop_fighting, and do_flee for its own
   flight): an encounter still open closes with "fled" -- the mobile ran,
   laid out as a flee row -- or "parted" with how ("stopped": PEACE, the
   player gone from the room or asleep, a recall, a quit). Either way the
   time is kept for progress_resume. A mobile not awake writes nothing
   here: damage() stops the fight of a victim asleep, stunned, mortally
   wounded or dead -- the last before group_gain, whose slain row is the
   outcome -- so the encounter stays open for the blow that ends it, or
   for the fight it wakes into. Every engage
   row then has an outcome unless the mobile is still fighting or died
   crediting nobody. */
void progress_fight_stopped( CHAR_DATA *mob, CHAR_DATA *opponent, const char *how )
{
    CHAR_DATA *pc;

    if ( mob == NULL || !IS_NPC(mob) )
        return;
    mob->enc_left_ms = playlog_now_ms();
    if ( !mob->enc_open || !IS_AWAKE(mob) )
        return;
    mob->enc_open = false;
    pc = progress_player( opponent );
    if ( pc == NULL )
        return;
    if ( !str_cmp( how, "fled" ) )
        progress_event( pc, "fled", mob );
    else
    {
        char tail[160], id[48];

        snprintf( tail, sizeof(tail), "%d\t%d\t%ld\t%s\t%s",
                  mob->max_hit > 0 ? (int) ( 100L * UMAX( 0, mob->hit ) / mob->max_hit ) : 0,
                  mob->max_hit,
                  pc->pcdata != NULL ? pc->pcdata->fight_taken + pc->pcdata->fight_direct : 0L,
                  encounter_text( mob->encounter_seq, id, sizeof(id) ), how );
        progress_write( "parted", pc, mob, tail );
    }
}

/* What a kill left to take (owner: "how much gold/experience/gear is
   given"): every object in the corpse at any depth but coin, which the
   slain row counts -- how many, their worth in copper together, the
   highest level among them, and vnum:source for the first few, the
   source being what make_corpse put it there for (carried, guardian,
   ganon, enemy, holiday, event). A corpse with nothing in it writes
   "0 0 0 -", which is the answer too. */
static void drop_walk( OBJ_DATA *list, int *count, long *worth, int *top,
                       char *items, size_t size, int *named, int depth )
{
    OBJ_DATA *obj;

    for ( obj = list; obj != NULL && depth < 8; obj = obj->next_content )
    {
        if ( obj->item_type != ITEM_MONEY )
        {
            (*count)++;
            if ( obj->cost > 0 && *worth < LONG_MAX - obj->cost )
                *worth += obj->cost;
            if ( obj->level > *top )
                *top = obj->level;
            if ( *named < 8 && obj->pIndexData != NULL )
            {
                char one[48];

                snprintf( one, sizeof(one), "%s%d:%s", *named > 0 ? "," : "",
                          obj->pIndexData->vnum,
                          obj->drop_source != NULL ? obj->drop_source : "carried" );
                toc_strlcat( items, one, size );
                (*named)++;
            }
        }
        if ( obj->contains != NULL )
            drop_walk( obj->contains, count, worth, top, items, size, named, depth + 1 );
    }
}

void progress_drop( CHAR_DATA *killer, CHAR_DATA *victim, OBJ_DATA *corpse )
{
    CHAR_DATA *who = progress_player( killer );
    char items[320], tail[448], id[48];
    int count = 0, top = 0, named = 0;
    long worth = 0;

    if ( victim == NULL || !IS_NPC(victim) || corpse == NULL )
        return;
    /* The corpse carries the kill, so what is taken out of it later is
       joined to this row and the slain one. */
    corpse->kill_seq = progress_encounter_id( victim );
    corpse->kill_vnum = victim->pIndexData != NULL ? victim->pIndexData->vnum : 0;
    corpse->kill_level = victim->level;
    if ( who == NULL )
        return;
    items[0] = '\0';
    drop_walk( corpse->contains, &count, &worth, &top, items, sizeof(items), &named, 0 );
    snprintf( tail, sizeof(tail), "%s\t%d\t%ld\t%d\t%s",
              encounter_text( victim->encounter_seq, id, sizeof(id) ),
              count, worth, top, items[0] != '\0' ? items : "-" );
    progress_write( "drop", who, victim, tail );
}

/* What CONSIDER predicted (consider_fight): each side's damage a round,
   the rounds each would need, and the verdict's key -- so the fight that
   follows, by the same character against the same foe, can be held to it
   (tools/consider_audit.py; owner, 2026-11-10: "i feel like the
   consider command isn't that accurate"). */
void progress_consider( CHAR_DATA *ch, CHAR_DATA *victim, double yours, double theirs,
                        double your_rounds, double their_rounds, const char *verdict,
                        bool caster )
{
    /* "%.1f" of a double is up to 312 bytes, and a cut row is a row with
       columns missing: the numbers go through format_tenths, held to a
       bound no prediction reaches (rounds are at most hit points over a
       tenth of a blow: ten times POOL_MAX). The verdict is a word. */
    char tail[192], a[FORMAT_TENTHS_MAX], b[FORMAT_TENTHS_MAX], c[FORMAT_TENTHS_MAX],
         d[FORMAT_TENTHS_MAX], word[32];

    if ( ch == NULL || victim == NULL || !IS_NPC(victim) )
        return;
    play_clean( word, sizeof(word), verdict != NULL ? verdict : "-" );
    snprintf( tail, sizeof(tail), "%s\t%s\t%s\t%s\t%s\t%d\t%d\t%d",
              format_tenths( a, sizeof(a), yours, 1e12 ),
              format_tenths( b, sizeof(b), theirs, 1e12 ),
              format_tenths( c, sizeof(c), your_rounds, 1e12 ),
              format_tenths( d, sizeof(d), their_rounds, 1e12 ),
              word, ch->hit, victim->hit, caster ? 1 : 0 );
    progress_write( "consider", ch, victim, tail );
}

/* Something taken out of a mobile's corpse (get_obj, before it moves):
   what a kill actually paid, beside what it was made with. Coin is
   counted gross, before any autosplit -- the split is a transfer between
   players, which log/play.tsv's coin rows show -- and the group in the
   room says how many it may be split among. */
void progress_loot( CHAR_DATA *ch, OBJ_DATA *corpse, OBJ_DATA *obj, long copper )
{
    char tail[256], id[48];
    const char *area = "-";
    int players, pets;

    if ( ch == NULL || IS_NPC(ch) || corpse == NULL || obj == NULL
    ||   corpse->item_type != ITEM_CORPSE_NPC || corpse->kill_seq <= 0 )
        return;
    if ( corpse->in_room != NULL && corpse->in_room->area != NULL
    &&   corpse->in_room->area->file_name != NULL )
        area = corpse->in_room->area->file_name;
    progress_party( ch, &players, &pets );
    snprintf( tail, sizeof(tail), "%s\t%s\t%d\t%ld\t%d\t%s\t%s\t%d",
              encounter_text( corpse->kill_seq, id, sizeof(id) ),
              obj->item_type == ITEM_MONEY ? "coin" : "obj",
              obj->pIndexData != NULL ? obj->pIndexData->vnum : 0,
              obj->item_type == ITEM_MONEY ? copper : UMAX( 0L, obj->cost ),
              obj->level,
              obj->item_type == ITEM_MONEY ? "coin"
                  : obj->drop_source != NULL ? obj->drop_source : "carried",
              playlog_how( ch ), players );
    progress_write_raw( "loot", ch, corpse->kill_vnum, corpse->kill_level, area, tail );
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
    /* attack_table has no NULL row: it ends at MAX_DAMAGE_MESSAGE (const.c
       asserts it). Counting to a NULL ran past its end into race_table. */
    if ( dt >= 0 && dt < MAX_SKILL && skill_table[dt].name != NULL )
        return skill_table[dt].name;
    if ( dt >= TYPE_HIT && dt <= TYPE_HIT + MAX_DAMAGE_MESSAGE )
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
/* Why the objects extracted next are gone, when it is neither a command
   nor the phase alone (hyrule.c: "crumbled leaving Level 3"); NULL puts
   the ordinary reason back. */
static const char *obj_gone_override;

void playlog_obj_gone_as( const char *why )
{
    obj_gone_override = why;
}

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
    if ( obj_gone_override != NULL )
        snprintf( why, sizeof(why), "%s", obj_gone_override );
    else if ( current_set && holder->name != NULL && !str_cmp( current_name, holder->name ) )
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
