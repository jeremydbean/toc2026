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
static char current_room[16];
static char current_line[100];
static char current_cmd[32];        /* the command's own name, for coin */
static bool current_set;

/* Where a session's coin came from (playlog_coin). SPENT is every loss. */
enum { COIN_LOOT, COIN_QUEST, COIN_DAILY, COIN_SOLD, COIN_GAMBLING,
       COIN_OTHER, COIN_SPENT };
static const char *const coin_source_names[PLAY_COIN_KINDS] =
    { "loot", "quests", "dailies", "sales", "gambling", "other", "spent" };
static const char *coin_override;   /* playlog_coin_as() */

/* ------------------------------------------------------------ helpers */

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

/* One record: the common columns, then `fields` (already tab-joined). */
static void journal_write( const char *kind, CHAR_DATA *ch, const char *fields )
{
    char room[16], area[64], name[32];

    if ( journal_busy )
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
static void first_reply_line( const char *out, int len, char *dest, size_t size )
{
    char line[PLAY_REPLY];
    size_t n = 0;
    int i, lines = 0;

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
        if ( c >= 32 && c < 127 && n + 1 < sizeof(line) )
            line[n++] = (char) c;
    }
    if ( lines < PLAY_REPLY_LINES )
        reply_add( dest, size, line, &n, &lines );
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
    play_clean( current_cmd, sizeof(current_cmd), cmd_name != NULL ? cmd_name : "" );
    if ( ch->in_room == NULL )
        snprintf( current_room, sizeof(current_room), "0" );
    else if ( room_hides_from_log( ch->in_room ) )
        snprintf( current_room, sizeof(current_room), "-" );
    else
        snprintf( current_room, sizeof(current_room), "%d", ch->in_room->vnum );
    play_clean( current_line, sizeof(current_line), shown );
    current_set = true;
    playlog_phase = "a command";

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

    current_set = false;
    playlog_phase = "game loop";
    if ( ch == NULL || IS_NPC(ch) )
        return;
    if ( refused && ch->pcdata != NULL )
        ch->pcdata->play_refused++;

    /* The line as it may be shown, less the command word. */
    space = strchr( shown, ' ' );
    play_clean( args, sizeof(args), space != NULL ? space + 1 : "" );
    if ( secret || out == NULL || out_len <= 0 )
        reply[0] = '\0';
    else
        first_reply_line( out, out_len, reply, sizeof(reply) );

    snprintf( fields, sizeof(fields), "%s\t%d\t%ld\t%s\t%s\t%s\t%s",
              play_position( pos_before ), hp_pct_before, ms,
              fighting_before ? "fight" : "-",
              cmd_name != NULL ? cmd_name : "?", args,
              secret ? "(withheld)" : reply );
    journal_write( refused ? "refused" : "cmd", ch, fields );
}

/* For bug(): " (during Name's 'look' in room 4207)", or "". */
void playlog_bug_context( char *buf, size_t size )
{
    if ( !current_set )
    {
        snprintf( buf, size, " (during %s)", playlog_phase );
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
              current_set ? current_line : playlog_phase );
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
   wizinvis crafter's line names nobody and no room: the journal is public,
   and their presence is not. */
void playlog_craft( CHAR_DATA *ch, const char *fields )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    journal_write( "craft", IS_SET( ch->act, PLR_WIZINVIS ) ? NULL : ch, fields );
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

    if ( ch->pcdata->play_anom_last[kind] + ANOMALY_QUIET > current_time )
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
        kind = COIN_SPENT;
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
    char coin[PLAY_LINE / 2];

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL
    ||   ch->pcdata->session_logon <= 0 )
        return;
    coin_summary( ch, coin, sizeof(coin) );
    snprintf( fields, sizeof(fields),
              "%s\t%lds\t%+d levels\t%+ld exp\t%+ld copper\t%d kills\t%d deaths"
              "\t%d quests\t%d commands\t%d refused\tcoin: %s",
              how, (long) ( current_time - ch->pcdata->session_logon ),
              (int) ch->level - ch->pcdata->session_start_level,
              ch->exp - ch->pcdata->session_start_exp,
              ch->pcdata->play_baseline
                  ? play_wealth( ch ) - ch->pcdata->play_start_wealth : 0L,
              ch->pcdata->session_kills, ch->pcdata->session_deaths,
              ch->pcdata->session_quests, ch->pcdata->play_cmds,
              ch->pcdata->play_refused, coin );
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

long playlog_now_ms( void )
{
    struct timeval now;

    gettimeofday( &now, NULL );
    return (long) now.tv_sec * 1000L + (long) ( now.tv_usec / 1000 );
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
    ||   foe->pIndexData == NULL || is_unfindable_mob( foe ) )
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
                    long accepted_xp, int members )
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
    snprintf( tail, sizeof(tail), "%ld\t%d\t%d\t%ld\t%d\t%d\t%s\t%ld\t%ld\t%ld\t%d\t%ld",
              encounter, base_xp, rested_xp, accepted_xp, members,
              pc != NULL ? pc->guild : -1, buffs,
              pc != NULL ? pc->meter_damage : 0L,
              pc != NULL ? pc->fight_taken + pc->fight_direct : 0L,
              pc != NULL ? pc->fight_healed : 0L,
              pc != NULL ? pc->fight_mana_start - gch->mana : 0,
              pc != NULL ? pc->fight_direct : 0L );
    progress_write( "kill", gch, victim, tail );
}

/* kind is "flee" or "death"; foe is the mobile it was against. */
void progress_event( CHAR_DATA *ch, const char *kind, CHAR_DATA *foe )
{
    progress_write( kind, ch, foe, "" );
}
