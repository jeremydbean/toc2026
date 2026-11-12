/*
 * The diary (owner, 2026-11-12): "a diary feature that uses the player
 * logging system to allow players to see their daily progress and what
 * they did each day."
 *
 * Each mortal keeps one page a day: time played, levels and experience,
 * kills (the notable ones by name), deaths and close calls, quests and
 * dailies with their points, achievements, skills improved, the areas
 * visited and the time in each, notable things gained, and coin earned
 * and spent by source. The hooks are the play journal's own (playlog.c
 * calls diary_coin, diary_got, diary_level, diary_moved, diary_exp and
 * diary_skill from the functions that write log/play.tsv; the rest sit
 * beside the journal's calls), so the two say the same things -- but the
 * diary is a summary of its own and never reads the journal, which is
 * trimmed and can be large.
 *
 * Today's page is in memory (pcdata->diary) and written at every save
 * and at the day's end to player/diary/<Name>, a text file of whole
 * records, written aside and renamed into place (temp_file_commit). It
 * keeps the newest DIARY_DAYS days. Nothing of it is in the player file.
 *
 * A day is the game's local calendar day -- holiday_date(), the date the
 * holiday calendar reads (the host's localtime, or TOC_DATE/TOC_DATE_FILE
 * in tests) -- so the diary turns its page when the holidays do.
 *
 * Privacy: only its owner reads a diary; staff may read any player's for
 * support (DIARY <name>, by rank as rank_protects asks). Staff keep none,
 * so a wizinvis immortal leaves no page anywhere, and nothing written
 * names anybody else: no giver, no player killer, no room (an area is the
 * finest place written, so the black market dealer and the treasure
 * goblin are never placed), nothing said or typed.
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"
#include "holiday_rules.h"
#include "numparse.h"

#define DIARY_DIR       "../player/diary"
#define DIARY_DAYS      30          /* days kept; the oldest rolls off */
#define DIARY_NAME      48
#define DIARY_LIST_MAX  12
#define DIARY_LINE      256
#define DIARY_GAP_MAX   ( 15 * 60 ) /* the most one accounting adds */
#define DIARY_WIDTH     76          /* fits an 80-column terminal */
#define DIARY_FORMAT    1

enum { DL_NOTABLE, DL_DEATH, DL_CLOSE, DL_ACHV, DL_SKILL, DL_AREA, DL_ITEM,
       DL_EARN, DL_SPEND, DL_COUNT };

/* Each list's name in the file and how many names it keeps; past that the
   rest are counted ("and 3 more"). */
static const struct { const char *key; int max; } diary_lists[DL_COUNT] =
{
    { "notable", 8 }, { "death", 6 }, { "close", 6 }, { "achv", 10 },
    { "skill", 12 }, { "area", 12 }, { "item", 12 }, { "earn", 8 },
    { "spend", 8 }
};

typedef struct
{
    char name[DIARY_NAME];
    long a;                 /* a count, seconds, points, copper, or a skill before */
    long b;                 /* a skill after */
} DIARY_ENTRY;

struct diary_day
{
    int         day;            /* yyyymmdd, the game's local calendar */
    long        played;         /* seconds */
    int         level_from;
    int         level_to;
    long        levels;         /* levels gained */
    long        exp_gain;
    long        exp_loss;
    long        kills;
    long        deaths;
    long        close_calls;
    long        quests;
    long        quest_points;
    long        dailies;
    long        daily_points;
    int         n[DL_COUNT];
    long        more[DL_COUNT];
    DIARY_ENTRY list[DL_COUNT][DIARY_LIST_MAX];
    /* memory only */
    time_t      touch;          /* time played is counted up to here */
    AREA_DATA * area;           /* the area that time is counted to */
    bool        dirty;
};

/* get_obj taking from the character's own bag or corpse, and the stash's
   own withdrawals: moving their own things is not gaining them. */
static bool own_move;

/* --------------------------------------------------------------- helpers */

static long sat_add( long a, long b )
{
    if ( b > 0 && a > LONG_MAX - b )
        return LONG_MAX;
    if ( b < 0 && a < LONG_MIN - b )
        return LONG_MIN;
    return a + b;
}

/* A name as the diary keeps it: plain printable ASCII, colour tokens and
   braces gone, no tilde or line break, spaces trimmed. */
static void diary_clean( char *dest, size_t size, const char *src )
{
    size_t n = 0;

    if ( size == 0 )
        return;
    for ( ; src != NULL && *src != '\0' && n + 1 < size; src++ )
    {
        unsigned char c = (unsigned char) *src;

        if ( c == '{' )
        {
            if ( isxdigit( (unsigned char) src[1] ) && isxdigit( (unsigned char) src[2] ) )
                src += 2;
            continue;
        }
        if ( c == '}' || c == '~' )
            continue;
        if ( c < 32 || c > 126 )
            c = ' ';
        if ( c == ' ' && ( n == 0 || dest[n - 1] == ' ' ) )
            continue;
        dest[n++] = (char) c;
    }
    while ( n > 0 && dest[n - 1] == ' ' )
        n--;
    dest[n] = '\0';
}

static bool diary_name_ok( const char *name )
{
    size_t i, len;

    if ( name == NULL )
        return false;
    len = strlen( name );
    if ( len < 2 || len > 12 )
        return false;
    for ( i = 0; i < len; i++ )
        if ( !isalpha( (unsigned char) name[i] ) )
            return false;
    return true;
}

static void diary_path( const char *name, char *out, size_t size )
{
    char proper[16];
    size_t i;

    toc_strlcpy( proper, name, sizeof(proper) );
    for ( i = 0; proper[i] != '\0'; i++ )
        proper[i] = (char) ( i == 0 ? UPPER( proper[i] ) : LOWER( proper[i] ) );
    snprintf( out, size, "%s/%s", DIARY_DIR, proper );
}

/* --------------------------------------------------------------- the days */

static int diary_key( int y, int m, int d )
{
    return y * 10000 + m * 100 + d;
}

static bool diary_key_parts( int key, int *y, int *m, int *d )
{
    *y = key / 10000;
    *m = ( key / 100 ) % 100;
    *d = key % 100;
    return holiday_date_valid( *y, *m, *d );
}

/* Today, on the calendar the holidays read. */
static int diary_key_now( void )
{
    int y, m, d;

    holiday_date( &y, &m, &d );
    return diary_key( y, m, d );
}

static int diary_key_add( int key, long days )
{
    int y, m, d;

    if ( !diary_key_parts( key, &y, &m, &d ) )
        return key;
    holiday_civil_from_days( holiday_days_from_civil( y, m, d ) + days, &y, &m, &d );
    return diary_key( y, m, d );
}

/* "Thursday 12 November 2026" */
static void diary_long_date( int key, char *out, size_t size )
{
    static const char *const weekday[7] =     /* 1970-01-01 was a Thursday */
        { "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday" };
    static const char *const month[12] =
        { "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December" };
    int y, m, d;
    long days, w;

    if ( !diary_key_parts( key, &y, &m, &d ) )
    {
        snprintf( out, size, "an unknown day" );
        return;
    }
    days = holiday_days_from_civil( y, m, d );
    w = days % 7;
    if ( w < 0 )
        w += 7;
    snprintf( out, size, "%s %d %s %d", weekday[w], d, month[m - 1], y );
}

static void diary_short_date( int key, char *out, size_t size )
{
    snprintf( out, size, "%04d-%02d-%02d", key / 10000, ( key / 100 ) % 100, key % 100 );
}

/* "1h 20m", "45m", "under a minute" -- or with `tight`, "<1m". */
static void diary_duration( long secs, bool tight, char *out, size_t size )
{
    long h = secs / 3600, m = ( secs % 3600 ) / 60;

    if ( secs < 60 )
        snprintf( out, size, "%s", tight ? "<1m" : "under a minute" );
    else if ( h > 0 )
        snprintf( out, size, "%ldh %ldm", h, m );
    else
        snprintf( out, size, "%ldm", m );
}

/* The list entry named `raw`, made if there is room; NULL (and counted)
   past the list's limit. */
static DIARY_ENTRY *diary_entry( DIARY_DAY *d, int list, const char *raw )
{
    char name[DIARY_NAME];
    int i;

    diary_clean( name, sizeof(name), raw );
    if ( name[0] == '\0' )
        return NULL;
    for ( i = 0; i < d->n[list]; i++ )
        if ( !str_cmp( d->list[list][i].name, name ) )
            return &d->list[list][i];
    if ( d->n[list] >= diary_lists[list].max )
    {
        d->more[list] = sat_add( d->more[list], 1 );
        return NULL;
    }
    i = d->n[list]++;
    toc_strlcpy( d->list[list][i].name, name, DIARY_NAME );
    d->list[list][i].a = 0;
    d->list[list][i].b = 0;
    return &d->list[list][i];
}

static DIARY_ENTRY *diary_area_entry( DIARY_DAY *d, AREA_DATA *area )
{
    char name[DIARY_NAME];

    if ( area == NULL )
        return NULL;
    quest_area_name( area->name, name, sizeof(name) );
    return diary_entry( d, DL_AREA, name );
}

/* ------------------------------------------------------------ the file */

/* One line; a line longer than the buffer is read to its end and given
   back empty, never read as two records. */
static bool diary_read_line( FILE *fp, char *line, size_t size )
{
    int c;

    if ( fgets( line, (int) size, fp ) == NULL )
        return false;
    if ( strchr( line, '\n' ) == NULL && !feof( fp ) )
    {
        while ( ( c = getc( fp ) ) != EOF && c != '\n' )
            ;
        line[0] = '\0';
        return true;
    }
    line[strcspn( line, "\r\n" )] = '\0';
    return true;
}

static char *diary_word( char **p )
{
    char *start;

    while ( **p == ' ' )
        (*p)++;
    if ( **p == '\0' )
        return NULL;
    start = *p;
    while ( **p != '\0' && **p != ' ' )
        (*p)++;
    if ( **p == ' ' )
        *(*p)++ = '\0';
    return start;
}

static bool diary_number( char **p, long *out )
{
    char *word = diary_word( p );

    return word != NULL && parse_long( word, 0, LONG_MAX, out );
}

/* A finished record into `days` (sorted or not): the same day replaces,
   and a full array gives up its oldest for a newer one. */
static void diary_keep( DIARY_DAY *days, int *n, int cap, const DIARY_DAY *rec )
{
    int i, oldest = 0;

    for ( i = 0; i < *n; i++ )
        if ( days[i].day == rec->day )
        {
            days[i] = *rec;
            return;
        }
    if ( *n < cap )
    {
        days[(*n)++] = *rec;
        return;
    }
    for ( i = 1; i < *n; i++ )
        if ( days[i].day < days[oldest].day )
            oldest = i;
    if ( rec->day > days[oldest].day )
        days[oldest] = *rec;
}

/* Every whole record in name's diary, the newest `cap` of them. A record
   is whole from its Day line to its End; anything malformed in it is
   left at zero, an unknown key is skipped, and a record cut short at the
   end of the file is dropped. */
static int diary_read_file( const char *name, DIARY_DAY *days, int cap )
{
    char path[MAX_INPUT_LENGTH];
    char line[DIARY_LINE];
    DIARY_DAY *cur;
    FILE *fp;
    bool in = false;
    int n = 0;

    if ( !diary_name_ok( name ) || cap <= 0 )
        return 0;
    diary_path( name, path, sizeof(path) );
    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return 0;
    if ( ( cur = calloc( 1, sizeof(*cur) ) ) == NULL )
    {
        fclose( fp );
        return 0;
    }
    while ( diary_read_line( fp, line, sizeof(line) ) )
    {
        char *p = line, *key;
        long a = 0, b = 0, c = 0;
        int i, y, m, d;

        if ( ( key = diary_word( &p ) ) == NULL )
            continue;
        if ( !strcmp( key, "Day" ) )
        {
            char *date = diary_word( &p );

            memset( cur, 0, sizeof(*cur) );
            in = date != NULL && holiday_parse_date( date, &y, &m, &d );
            if ( in )
                cur->day = diary_key( y, m, d );
            continue;
        }
        if ( !in )
            continue;
        if ( !strcmp( key, "End" ) )
        {
            diary_keep( days, &n, cap, cur );
            in = false;
        }
        else if ( !strcmp( key, "Played" ) && diary_number( &p, &a ) )
            cur->played = a;
        else if ( !strcmp( key, "Level" ) && diary_number( &p, &a )
             &&   diary_number( &p, &b ) && diary_number( &p, &c ) )
        {
            cur->level_from = (int) UMIN( a, 1000 );
            cur->level_to = (int) UMIN( b, 1000 );
            cur->levels = c;
        }
        else if ( !strcmp( key, "Exp" ) && diary_number( &p, &a ) && diary_number( &p, &b ) )
        {
            cur->exp_gain = a;
            cur->exp_loss = b;
        }
        else if ( !strcmp( key, "Kills" ) && diary_number( &p, &a ) )
            cur->kills = a;
        else if ( !strcmp( key, "Deaths" ) && diary_number( &p, &a ) )
            cur->deaths = a;
        else if ( !strcmp( key, "Close" ) && diary_number( &p, &a ) )
            cur->close_calls = a;
        else if ( !strcmp( key, "Quests" ) && diary_number( &p, &a ) && diary_number( &p, &b ) )
        {
            cur->quests = a;
            cur->quest_points = b;
        }
        else if ( !strcmp( key, "Dailies" ) && diary_number( &p, &a ) && diary_number( &p, &b ) )
        {
            cur->dailies = a;
            cur->daily_points = b;
        }
        else if ( !strcmp( key, "List" ) || !strcmp( key, "More" ) )
        {
            char *which = diary_word( &p );
            bool list = !strcmp( key, "List" );

            if ( which == NULL )
                continue;
            for ( i = 0; i < DL_COUNT; i++ )
                if ( !strcmp( which, diary_lists[i].key ) )
                    break;
            if ( i >= DL_COUNT || !diary_number( &p, &a ) )
                continue;
            if ( !list )
                cur->more[i] = a;
            else if ( diary_number( &p, &b ) )
            {
                DIARY_ENTRY *e = diary_entry( cur, i, p );

                if ( e != NULL )
                {
                    e->a = a;
                    e->b = b;
                }
            }
        }
    }
    fclose( fp );
    free( cur );
    return n;
}

static int diary_day_cmp( const void *x, const void *y )
{
    int a = ( (const DIARY_DAY *) x )->day, b = ( (const DIARY_DAY *) y )->day;

    return a < b ? -1 : a > b ? 1 : 0;
}

static void diary_write_day( FILE *fp, const DIARY_DAY *d )
{
    char date[16];
    int l, i;

    diary_short_date( d->day, date, sizeof(date) );
    fprintf( fp, "Day %s\n", date );
    fprintf( fp, "Played %ld\n", d->played );
    fprintf( fp, "Level %d %d %ld\n", UMAX( d->level_from, 0 ), UMAX( d->level_to, 0 ), d->levels );
    fprintf( fp, "Exp %ld %ld\n", d->exp_gain, d->exp_loss );
    fprintf( fp, "Kills %ld\n", d->kills );
    fprintf( fp, "Deaths %ld\n", d->deaths );
    fprintf( fp, "Close %ld\n", d->close_calls );
    fprintf( fp, "Quests %ld %ld\n", d->quests, d->quest_points );
    fprintf( fp, "Dailies %ld %ld\n", d->dailies, d->daily_points );
    for ( l = 0; l < DL_COUNT; l++ )
    {
        for ( i = 0; i < d->n[l]; i++ )
            fprintf( fp, "List %s %ld %ld %s\n", diary_lists[l].key,
                     UMAX( d->list[l][i].a, 0 ), UMAX( d->list[l][i].b, 0 ),
                     d->list[l][i].name );
        if ( d->more[l] > 0 )
            fprintf( fp, "More %s %ld\n", diary_lists[l].key, d->more[l] );
    }
    fprintf( fp, "End\n" );
}

/* Put `d` into name's diary: every day already there, this one replacing
   its own, the newest DIARY_DAYS kept, written aside and renamed in. */
static bool diary_write( const char *name, const DIARY_DAY *d )
{
    char path[MAX_INPUT_LENGTH], temp[MAX_INPUT_LENGTH + 8];
    DIARY_DAY *days;
    FILE *fp;
    int n, i, start;
    bool ok;

    if ( d == NULL || !diary_name_ok( name ) )
        return false;
    if ( ( days = calloc( DIARY_DAYS + 1, sizeof(*days) ) ) == NULL )
        return false;
    n = diary_read_file( name, days, DIARY_DAYS + 1 );
    diary_keep( days, &n, DIARY_DAYS + 1, d );
    qsort( days, (size_t) n, sizeof(*days), diary_day_cmp );
    start = n > DIARY_DAYS ? n - DIARY_DAYS : 0;

    if ( !recovery_ensure_dir( DIARY_DIR ) )
    {
        free( days );
        return false;
    }
    diary_path( name, path, sizeof(path) );
    snprintf( temp, sizeof(temp), "%s.tmp", path );
    if ( ( fp = fopen( temp, "w" ) ) == NULL )
    {
        free( days );
        return false;
    }
    fprintf( fp, "#DIARY %d\n", DIARY_FORMAT );
    for ( i = start; i < n; i++ )
        diary_write_day( fp, &days[i] );
    fprintf( fp, "#END\n" );
    ok = temp_file_commit( fp, temp, path );
    free( days );
    return ok;
}

/* ------------------------------------------------------- today's page */

/* Who keeps a diary: a mortal player whose file was read. Staff keep
   none -- a wizinvis immortal leaves no trace in any diary. */
static bool diary_keeps( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && !ch->pcdata->load_failed
        && !IS_TRUSTED( ch, LEVEL_IMMORTAL )
        && !IS_SET( ch->act, PLR_WIZINVIS )
        && diary_name_ok( ch->name );
}

/* Count the time since the last count: to the day, and to the area it was
   spent in. A character without a link is not playing. */
static void diary_account( CHAR_DATA *ch, DIARY_DAY *d )
{
    long gap = (long) ( current_time - d->touch );
    DIARY_ENTRY *e;

    if ( ch->desc == NULL || gap < 0 )
        gap = 0;
    if ( gap > DIARY_GAP_MAX )
        gap = DIARY_GAP_MAX;
    d->touch = current_time;
    if ( d->level_to != ch->level )
    {
        d->level_to = ch->level;
        d->dirty = true;
    }
    if ( gap > 0 )
    {
        d->played = sat_add( d->played, gap );
        if ( ( e = diary_area_entry( d, d->area ) ) != NULL )
            e->a = sat_add( e->a, gap );
        d->dirty = true;
    }
    if ( ch->in_room != NULL && ch->in_room->area != d->area )
    {
        d->area = ch->in_room->area;
        diary_area_entry( d, d->area );
        d->dirty = true;
    }
}

/* Open the page for `key`: what the file already holds for that day (an
   earlier sitting), or a clean one. */
static void diary_begin_day( CHAR_DATA *ch, DIARY_DAY *d, int key )
{
    DIARY_DAY *days;
    int n, i;
    bool found = false;

    memset( d, 0, sizeof(*d) );
    if ( ( days = calloc( DIARY_DAYS + 1, sizeof(*days) ) ) != NULL )
    {
        n = diary_read_file( ch->name, days, DIARY_DAYS + 1 );
        for ( i = 0; i < n; i++ )
            if ( days[i].day == key )
            {
                *d = days[i];
                found = true;
                break;
            }
        free( days );
    }
    if ( !found )
    {
        d->day = key;
        d->level_from = ch->level;
    }
    d->level_to = ch->level;
    d->touch = current_time;
    d->area = ch->in_room != NULL ? ch->in_room->area : NULL;
    diary_area_entry( d, d->area );
    d->dirty = true;
}

/*
 * Today's page for ch, or NULL for somebody who keeps no diary. Made on a
 * playing character's first event of a sitting; at the day's end the old
 * page is written and a new one begun.
 */
static DIARY_DAY *diary_today( CHAR_DATA *ch )
{
    DIARY_DAY *d;
    int key;

    if ( !diary_keeps( ch ) )
        return NULL;
    key = diary_key_now();
    if ( ( d = ch->pcdata->diary ) == NULL )
    {
        if ( ch->desc == NULL || ch->desc->connected != CON_PLAYING
        ||   ch->in_room == NULL )
            return NULL;
        if ( ( d = calloc( 1, sizeof(*d) ) ) == NULL )
            return NULL;
        diary_begin_day( ch, d, key );
        ch->pcdata->diary = d;
        return d;
    }
    if ( d->day != key )
    {
        diary_account( ch, d );
        diary_write( ch->name, d );
        diary_begin_day( ch, d, key );
    }
    return d;
}

/* ---------------------------------------------------------- the hooks */

/* The nanny, as a character enters the game (not a reconnect). A new
   character's name may have been somebody's before: an old diary under
   it is set aside, never read as theirs. */
void diary_login( CHAR_DATA *ch, bool new_character )
{
    char path[MAX_INPUT_LENGTH], aside[MAX_INPUT_LENGTH + 32];
    struct stat st;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || !diary_name_ok( ch->name ) )
        return;
    if ( new_character )
    {
        diary_path( ch->name, path, sizeof(path) );
        if ( stat( path, &st ) == 0 )
        {
            snprintf( aside, sizeof(aside), "%s.old-%ld", path, (long) current_time );
            if ( rename( path, aside ) != 0 )
                remove( path );
        }
    }
    diary_today( ch );
}

void diary_tick( CHAR_DATA *ch )
{
    DIARY_DAY *d;

    if ( ( d = diary_today( ch ) ) != NULL )
        diary_account( ch, d );
}

/* save_char_obj: today's page goes to the disk with the character. */
void diary_save( CHAR_DATA *ch )
{
    DIARY_DAY *d;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->diary == NULL )
        return;
    if ( ( d = diary_today( ch ) ) == NULL )
        return;
    diary_account( ch, d );
    if ( d->dirty && diary_write( ch->name, d ) )
        d->dirty = false;
}

void diary_free( CHAR_DATA *ch )
{
    if ( ch == NULL || ch->pcdata == NULL )
        return;
    free( ch->pcdata->diary );
    ch->pcdata->diary = NULL;
}

/* RENAME: the diary goes with the character. A diary already under the
   new name -- a character since deleted -- is set aside first. */
void diary_rename( const char *old_name, const char *new_name )
{
    char from[MAX_INPUT_LENGTH], to[MAX_INPUT_LENGTH], aside[MAX_INPUT_LENGTH + 32];
    struct stat st;

    if ( !diary_name_ok( old_name ) || !diary_name_ok( new_name ) )
        return;
    diary_path( old_name, from, sizeof(from) );
    diary_path( new_name, to, sizeof(to) );
    if ( stat( from, &st ) != 0 )
        return;
    if ( stat( to, &st ) == 0 )
    {
        snprintf( aside, sizeof(aside), "%s.old-%ld", to, (long) current_time );
        rename( to, aside );
    }
    if ( rename( from, to ) != 0 )
        bug( "diary_rename: the diary could not be moved to the new name", 0 );
}

/* DELETE: the page in memory is dropped and the file set aside as
   <Name>.deleted-<time>, so the name's next owner starts a clean diary
   and nothing is destroyed (a deleted character can be restored). */
void diary_retire( CHAR_DATA *ch )
{
    char path[MAX_INPUT_LENGTH], aside[MAX_INPUT_LENGTH + 32];
    struct stat st;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    diary_free( ch );
    if ( !diary_name_ok( ch->name ) )
        return;
    diary_path( ch->name, path, sizeof(path) );
    if ( stat( path, &st ) != 0 )
        return;
    snprintf( aside, sizeof(aside), "%s.deleted-%ld", path, (long) current_time );
    if ( rename( path, aside ) != 0 )
        remove( path );
}

/* char_to_room, through playlog_moved: time is counted to the area left. */
void diary_moved( CHAR_DATA *ch )
{
    DIARY_DAY *d;

    if ( ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
    &&   ( d = diary_today( ch ) ) != NULL
    &&   ch->in_room != NULL && ch->in_room->area != d->area )
        diary_account( ch, d );
}

/* playlog_coin and playlog_bank: coin gained by source ("loot", "quests",
   "sales" ...) and spent by what it went on ("buy", "heal", "stash" ...). */
void diary_coin( CHAR_DATA *ch, bool spent, const char *source, long copper )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( copper <= 0 || ( d = diary_today( ch ) ) == NULL )
        return;
    if ( ( e = diary_entry( d, spent ? DL_SPEND : DL_EARN,
                            source != NULL && source[0] != '\0' ? source : "other" ) ) == NULL )
        e = diary_entry( d, spent ? DL_SPEND : DL_EARN, "other" );
    if ( e != NULL )
        e->a = sat_add( e->a, copper );
    d->dirty = true;
}

void diary_own_move( bool on )
{
    own_move = on;
}

/* playlog_got: a thing that came to the character. What is used up as it
   is meant to be -- food, potions, scrolls, herbs, components, cakes --
   and coin, corpses and trash are not worth a line, and neither is a
   thing taken out of their own bag, corpse or stash. */
void diary_got( CHAR_DATA *ch, OBJ_DATA *obj )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( own_move || obj == NULL || obj->pIndexData == NULL )
        return;
    switch ( obj->item_type )
    {
    case ITEM_POTION: case ITEM_PILL: case ITEM_FOOD: case ITEM_SCROLL:
    case ITEM_MONEY: case ITEM_HERB: case ITEM_SPELL_COMPONENT: case ITEM_CAKE:
    case ITEM_CORPSE_NPC: case ITEM_CORPSE_PC: case ITEM_TRASH:
        return;
    default:
        break;
    }
    if ( obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BOMBS
    ||   ( d = diary_today( ch ) ) == NULL )
        return;
    if ( ( e = diary_entry( d, DL_ITEM, obj->short_descr ) ) != NULL )
        e->a = sat_add( e->a, 1 );
    d->dirty = true;
}

/* playlog_level: a level gained. */
void diary_level( CHAR_DATA *ch, int from )
{
    DIARY_DAY *d;

    UNUSED_PARAM( from );
    if ( ( d = diary_today( ch ) ) == NULL )
        return;
    d->levels = sat_add( d->levels, 1 );
    d->level_to = ch->level;
    d->dirty = true;
}

/* playlog_exp: experience gained or lost (a gain the level cap refused is
   no gain and never reaches here). */
void diary_exp( CHAR_DATA *ch, long amount )
{
    DIARY_DAY *d;

    if ( amount == 0 || ( d = diary_today( ch ) ) == NULL )
        return;
    if ( amount > 0 )
        d->exp_gain = sat_add( d->exp_gain, amount );
    else
        d->exp_loss = sat_add( d->exp_loss, amount == LONG_MIN ? LONG_MAX : -amount );
    d->dirty = true;
}

/* playlog_skill: check_improve raised a skill. The day keeps where it
   began and where it is now. */
void diary_skill( CHAR_DATA *ch, int sn, int before )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( sn < 0 || sn >= MAX_SKILL || skill_table[sn].name == NULL
    ||   ( d = diary_today( ch ) ) == NULL )
        return;
    if ( ( e = diary_entry( d, DL_SKILL, skill_table[sn].name ) ) != NULL )
    {
        if ( e->a == 0 && e->b == 0 )
            e->a = UMAX( before, 0 );
        e->b = ch->pcdata->learned[sn];
    }
    d->dirty = true;
}

/* achievement_unlock, beside playlog_achieved. */
void diary_achieved( CHAR_DATA *ch, const char *title, int points )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( ( d = diary_today( ch ) ) == NULL )
        return;
    if ( ( e = diary_entry( d, DL_ACHV, title ) ) != NULL )
        e->a = UMAX( points, 0 );
    d->dirty = true;
}

/* Worth a name in the diary: a boss an achievement names, a Hyrule
   guardian, a holiday boss, the treasure goblin, the black dragon. */
static bool diary_notable( CHAR_DATA *victim )
{
    int vnum = victim->pIndexData != NULL ? victim->pIndexData->vnum : 0;

    return achievement_boss_vnum( vnum ) || is_hyrule_guardian( victim )
        || is_treasure_goblin( victim ) || is_disaster_dragon( victim )
        || vnum == MOB_VNUM_EVENT_HORSEMAN || vnum == MOB_VNUM_EVENT_FATHER;
}

/* group_gain, beside progress_kill: one per player the kill paid. */
void diary_kill( CHAR_DATA *ch, CHAR_DATA *victim )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( victim == NULL || !IS_NPC(victim) || ( d = diary_today( ch ) ) == NULL )
        return;
    d->kills = sat_add( d->kills, 1 );
    if ( diary_notable( victim ) && ( e = diary_entry( d, DL_NOTABLE, victim->short_descr ) ) != NULL )
        e->a = sat_add( e->a, 1 );
    d->dirty = true;
}

/* raw_kill_internal, beside playlog_death. A mobile is named; a player
   never is, and an unseen immortal is not even that. */
void diary_death( CHAR_DATA *victim, CHAR_DATA *killer )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;
    const char *cause;

    if ( ( d = diary_today( victim ) ) == NULL )
        return;
    if ( killer == NULL || killer == victim )
        cause = "misadventure";
    else if ( IS_NPC(killer) )
        cause = killer->short_descr;
    else if ( IS_SET( killer->act, PLR_WIZINVIS ) )
        cause = "unknown causes";
    else
        cause = "another player";
    d->deaths = sat_add( d->deaths, 1 );
    if ( ( e = diary_entry( d, DL_DEATH, cause ) ) != NULL )
        e->a = sat_add( e->a, 1 );
    d->dirty = true;
}

/* A brush with death the achievements notice too: a flight or a recall on
   a twentieth of the character's hit points or less, a kill made there. */
void diary_close_call( CHAR_DATA *ch, const char *what )
{
    DIARY_DAY *d;
    DIARY_ENTRY *e;

    if ( ( d = diary_today( ch ) ) == NULL )
        return;
    d->close_calls = sat_add( d->close_calls, 1 );
    if ( ( e = diary_entry( d, DL_CLOSE, what ) ) != NULL )
        e->a = sat_add( e->a, 1 );
    d->dirty = true;
}

/* A quest handed in: a daily with its daily points, or an ordinary quest
   whose points are settled by the gamble (diary_quest_points). */
void diary_quest_done( CHAR_DATA *ch, bool daily, int points )
{
    DIARY_DAY *d;

    if ( ( d = diary_today( ch ) ) == NULL )
        return;
    if ( daily )
    {
        d->dailies = sat_add( d->dailies, 1 );
        d->daily_points = sat_add( d->daily_points, UMAX( points, 0 ) );
    }
    else
        d->quests = sat_add( d->quests, 1 );
    d->dirty = true;
}

void diary_quest_points( CHAR_DATA *ch, int points )
{
    DIARY_DAY *d;

    if ( points <= 0 || ( d = diary_today( ch ) ) == NULL )
        return;
    d->quest_points = sat_add( d->quest_points, points );
    d->dirty = true;
}

/* ------------------------------------------------------------- reading */

#define DIARY_OUT   12288

/* "Label: text", the text wrapped to DIARY_WIDTH and its later lines
   indented. The label alone is coloured; the text holds no colour. */
static void diary_para( char *out, size_t size, const char *label, const char *text )
{
    const char *p = text;
    size_t col = strlen( label );
    bool first = true;

    toc_strlcat( out, "{0B", size );
    toc_strlcat( out, label, size );
    toc_strlcat( out, "{00", size );
    for ( ; ; )
    {
        char word[DIARY_WIDTH + 1];
        size_t len = 0;

        while ( *p == ' ' )
            p++;
        if ( *p == '\0' )
            break;
        while ( *p != '\0' && *p != ' ' && len < DIARY_WIDTH - 4 )
            word[len++] = *p++;
        word[len] = '\0';
        if ( !first && col + 1 + len > DIARY_WIDTH )
        {
            toc_strlcat( out, "\n\r  ", size );
            col = 2;
        }
        else
        {
            toc_strlcat( out, " ", size );
            col++;
        }
        toc_strlcat( out, word, size );
        col += len;
        first = false;
    }
    toc_strlcat( out, "\n\r", size );
}

/* One list as "a, b (x2), c (+25) and 3 more". */
static void diary_list_text( const DIARY_DAY *d, int list, char *out, size_t size )
{
    char part[DIARY_NAME + 64], amount[64];
    int i;

    out[0] = '\0';
    for ( i = 0; i < d->n[list]; i++ )
    {
        const DIARY_ENTRY *e = &d->list[list][i];

        amount[0] = '\0';
        switch ( list )
        {
        case DL_NOTABLE: case DL_DEATH: case DL_CLOSE: case DL_ITEM:
            if ( e->a > 1 )
                snprintf( amount, sizeof(amount), " (x%ld)", e->a );
            break;
        case DL_ACHV:
            snprintf( amount, sizeof(amount), " (+%ld)", e->a );
            break;
        case DL_SKILL:
            snprintf( amount, sizeof(amount), " %ld%% to %ld%%", e->a, e->b );
            break;
        case DL_AREA:
        {
            char dur[24];

            diary_duration( e->a, true, dur, sizeof(dur) );
            snprintf( amount, sizeof(amount), " %s", dur );
            break;
        }
        case DL_EARN: case DL_SPEND:
        {
            char price[48];

            format_price( e->a, price, sizeof(price) );
            snprintf( amount, sizeof(amount), " %s", price );
            break;
        }
        default:
            break;
        }
        snprintf( part, sizeof(part), "%s%s%s", i > 0 ? ", " : "", e->name, amount );
        toc_strlcat( out, part, size );
    }
    if ( d->more[list] > 0 )
    {
        snprintf( part, sizeof(part), " and %ld more", d->more[list] );
        toc_strlcat( out, part, size );
    }
}

static long diary_net_coin( const DIARY_DAY *d )
{
    long net = 0;
    int i;

    for ( i = 0; i < d->n[DL_EARN]; i++ )
        net = sat_add( net, d->list[DL_EARN][i].a );
    for ( i = 0; i < d->n[DL_SPEND]; i++ )
        net = sat_add( net, -d->list[DL_SPEND][i].a );
    return net;
}

static void diary_show_day( CHAR_DATA *ch, const char *owner, const DIARY_DAY *d,
                            int today )
{
    char *out;
    char date[64], text[DIARY_OUT / 4], line[256], dur[32];
    bool quiet = true;

    if ( ( out = calloc( 1, DIARY_OUT ) ) == NULL )
        return;
    diary_long_date( d->day, date, sizeof(date) );
    snprintf( line, sizeof(line), "{0E%s diary -- %s%s{00\n\r", owner, date,
              d->day == today ? " (today)"
            : d->day == diary_key_add( today, -1 ) ? " (yesterday)" : "" );
    toc_strlcat( out, line, DIARY_OUT );

    diary_duration( d->played, false, dur, sizeof(dur) );
    if ( d->levels > 0 )
        snprintf( text, sizeof(text), "%s.  Level %d to %d (%ld gained).", dur,
                  d->level_from, d->level_to, d->levels );
    else if ( d->level_from != d->level_to )
        snprintf( text, sizeof(text), "%s.  Level %d to %d.", dur, d->level_from, d->level_to );
    else
        snprintf( text, sizeof(text), "%s.  Level %d.", dur, d->level_to );
    diary_para( out, DIARY_OUT, "Played:", text );

    if ( d->exp_gain > 0 || d->exp_loss > 0 )
    {
        quiet = false;
        if ( d->exp_loss > 0 )
            snprintf( text, sizeof(text), "%ld gained, %ld lost.", d->exp_gain, d->exp_loss );
        else
            snprintf( text, sizeof(text), "%ld gained.", d->exp_gain );
        diary_para( out, DIARY_OUT, "Experience:", text );
    }
    if ( d->kills > 0 )
    {
        quiet = false;
        snprintf( text, sizeof(text), "%ld", d->kills );
        if ( d->n[DL_NOTABLE] > 0 )
        {
            char names[DIARY_OUT / 8];

            diary_list_text( d, DL_NOTABLE, names, sizeof(names) );
            toc_strlcat( text, ", among them ", sizeof(text) );
            toc_strlcat( text, names, sizeof(text) );
        }
        toc_strlcat( text, ".", sizeof(text) );
        diary_para( out, DIARY_OUT, "Kills:", text );
    }
    if ( d->deaths > 0 )
    {
        char names[DIARY_OUT / 8];

        quiet = false;
        diary_list_text( d, DL_DEATH, names, sizeof(names) );
        snprintf( text, sizeof(text), "%ld (%s).", d->deaths, names );
        diary_para( out, DIARY_OUT, "Deaths:", text );
    }
    if ( d->close_calls > 0 )
    {
        quiet = false;
        diary_list_text( d, DL_CLOSE, text, sizeof(text) );
        toc_strlcat( text, ".", sizeof(text) );
        diary_para( out, DIARY_OUT, "Close calls:", text );
    }
    if ( d->quests > 0 || d->quest_points > 0 || d->dailies > 0 )
    {
        char part[96];

        quiet = false;
        text[0] = '\0';
        if ( d->quests > 0 || d->quest_points > 0 )
        {
            snprintf( part, sizeof(part), "%ld (%ld quest points).", d->quests, d->quest_points );
            toc_strlcat( text, part, sizeof(text) );
        }
        if ( d->dailies > 0 )
        {
            snprintf( part, sizeof(part), "%s%ld dail%s (%ld daily points).",
                      text[0] != '\0' ? "  " : "", d->dailies,
                      d->dailies == 1 ? "y" : "ies", d->daily_points );
            toc_strlcat( text, part, sizeof(text) );
        }
        diary_para( out, DIARY_OUT, "Quests:", text );
    }
    {
        static const struct { int list; const char *label; } rows[] =
        {
            { DL_ACHV,  "Achievements:" },
            { DL_SKILL, "Skills:" },
            { DL_AREA,  "Areas:" },
            { DL_ITEM,  "Gained:" },
            { DL_EARN,  "Coin in:" },
            { DL_SPEND, "Coin out:" },
        };
        size_t r;

        for ( r = 0; r < sizeof(rows) / sizeof(rows[0]); r++ )
        {
            if ( d->n[rows[r].list] == 0 && d->more[rows[r].list] == 0 )
                continue;
            if ( rows[r].list != DL_AREA )
                quiet = false;
            diary_list_text( d, rows[r].list, text, sizeof(text) );
            toc_strlcat( text, ".", sizeof(text) );
            diary_para( out, DIARY_OUT, rows[r].label, text );
        }
    }
    if ( quiet )
        toc_strlcat( out, "A quiet day.\n\r", DIARY_OUT );
    page_to_char( out, ch );
    free( out );
}

static void diary_show_list( CHAR_DATA *ch, const char *owner, DIARY_DAY *days, int n )
{
    DString out;        /* grown as it is written (2026-11-12) */
    char line[256], date[16], dur[24], lvl[24], coin[64], price[48];
    int i;
    long net;

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    snprintf( line, sizeof(line), "{0E%s diary, newest first (the last %d days are kept){00\n\r",
              owner, DIARY_DAYS );
    dstring_append_cstr( &out, line );
    dstring_append_cstr( &out, "{0BDate        Played   Level    Kills Deaths Quests  Coin{00\n\r" );
    for ( i = n - 1; i >= 0; i-- )
    {
        const DIARY_DAY *d = &days[i];

        diary_short_date( d->day, date, sizeof(date) );
        diary_duration( d->played, true, dur, sizeof(dur) );
        if ( d->level_from != d->level_to )
            snprintf( lvl, sizeof(lvl), "%d-%d", d->level_from, d->level_to );
        else
            snprintf( lvl, sizeof(lvl), "%d", d->level_to );
        net = diary_net_coin( d );
        if ( net == 0 )
            snprintf( coin, sizeof(coin), "-" );
        else
        {
            format_price( net < 0 ? ( net == LONG_MIN ? LONG_MAX : -net ) : net,
                          price, sizeof(price) );
            snprintf( coin, sizeof(coin), "%c%s", net < 0 ? '-' : '+', price );
        }
        snprintf( line, sizeof(line), "%-10s  %-7s  %-7s %6ld %6ld %6ld  %s\n\r",
                  date, dur, lvl, d->kills, d->deaths,
                  sat_add( d->quests, d->dailies ), coin );
        dstring_append_cstr( &out, line );
    }
    dstring_append_cstr( &out, "DIARY <yyyy-mm-dd> reads one day.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}

/* The trust a player file names, read without loading the character --
   for staff reading the diary of somebody not in the game. */
static int diary_file_trust( const char *name )
{
    char path[MAX_INPUT_LENGTH], line[DIARY_LINE];
    FILE *fp;
    int level = 0, trust = 0, value;

    if ( player_file_read_path( name, path, sizeof(path) ) == NULL
    ||   ( fp = fopen( path, "r" ) ) == NULL )
        return 0;
    while ( diary_read_line( fp, line, sizeof(line) ) )
    {
        if ( !strncmp( line, "#O", 2 ) || !strncmp( line, "End", 3 )
        ||   !strncmp( line, "#PET", 4 ) )
            break;
        if ( !strncmp( line, "Levl ", 5 ) && parse_int( line + 5, 0, INT_MAX, &value ) )
            level = value;
        else if ( !strncmp( line, "Tru ", 4 ) && parse_int( line + 4, 0, INT_MAX, &value ) )
            trust = value;
        else if ( !strncmp( line, "Creator 1", 9 ) )
            trust = LEVEL_CREATOR;
    }
    fclose( fp );
    return UMAX( level, trust );
}

/* rank_protects for somebody not in the game, by the trust their file
   names. Staff keep no diary, so this guards only what a mortal life
   before a promotion wrote. */
static bool diary_file_protects( CHAR_DATA *ch, const char *name )
{
    int mine = get_trust( ch ), theirs = diary_file_trust( name );

    return mine >= MAX_LEVEL ? theirs > mine : theirs >= mine;
}

static bool diary_is_day_word( const char *arg, int today, int *key )
{
    int y, m, d;

    if ( arg[0] == '\0' || !str_cmp( arg, "today" ) )
        *key = today;
    else if ( !str_cmp( arg, "yesterday" ) )
        *key = diary_key_add( today, -1 );
    else if ( holiday_parse_date( arg, &y, &m, &d ) )
        *key = diary_key( y, m, d );
    else
        return false;
    return true;
}

void do_diary( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH], name[16], owner[32], buf[MAX_STRING_LENGTH];
    CHAR_DATA *target = NULL;
    DIARY_DAY *days, *mem = NULL;
    bool staff, list = false, self = true;
    int today = diary_key_now(), key = today, n, i;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players keep diaries.\n\r", ch );
        return;
    }
    staff = IS_TRUSTED( ch, LEVEL_IMMORTAL );
    argument = one_argument( argument, arg );

    if ( arg[0] != '\0' && str_cmp( arg, "list" ) && !diary_is_day_word( arg, today, &key ) )
    {
        if ( !staff )
        {
            if ( diary_name_ok( arg ) )
                send_to_char( "A diary is read by its owner alone.\n\r", ch );
            send_to_char( "Syntax: diary [list | yesterday | <yyyy-mm-dd>]\n\r", ch );
            return;
        }
        if ( !diary_name_ok( arg ) )
        {
            send_to_char( "Syntax: diary <player> [list | yesterday | <yyyy-mm-dd>]\n\r", ch );
            return;
        }
        toc_strlcpy( name, capitalize( arg ), sizeof(name) );
        self = !str_cmp( name, ch->name );
        if ( !self )
        {
            bool logging_in = false;

            target = player_in_game( name, &logging_in );
            if ( target != NULL && ( logging_in || IS_NPC(target) ) )
                target = NULL;
            if ( target != NULL ? rank_protects( ch, target )
                                : diary_file_protects( ch, name ) )
            {
                send_to_char( "Their diary is not yours to read.\n\r", ch );
                return;
            }
        }
        argument = one_argument( argument, arg );
        key = today;
        if ( arg[0] != '\0' && str_cmp( arg, "list" ) && !diary_is_day_word( arg, today, &key ) )
        {
            send_to_char( "Syntax: diary <player> [list | yesterday | <yyyy-mm-dd>]\n\r", ch );
            return;
        }
    }
    else
        toc_strlcpy( name, ch->name, sizeof(name) );
    list = !str_cmp( arg, "list" );

    if ( self )
    {
        if ( !diary_keeps( ch ) )
        {
            send_to_char( staff ? "Staff keep no diary.  DIARY <player> reads a player's.\n\r"
                                : "You keep no diary.\n\r", ch );
            return;
        }
        target = ch;
        snprintf( owner, sizeof(owner), "Your" );
    }
    else
        snprintf( owner, sizeof(owner), "%s's", name );

    if ( target != NULL && ( mem = diary_today( target ) ) != NULL )
        diary_account( target, mem );

    if ( ( days = calloc( DIARY_DAYS + 2, sizeof(*days) ) ) == NULL )
        return;
    n = diary_read_file( name, days, DIARY_DAYS + 1 );
    if ( mem != NULL )
        diary_keep( days, &n, DIARY_DAYS + 1, mem );
    qsort( days, (size_t) n, sizeof(*days), diary_day_cmp );
    if ( n > DIARY_DAYS )
    {
        memmove( days, days + ( n - DIARY_DAYS ), (size_t) DIARY_DAYS * sizeof(*days) );
        n = DIARY_DAYS;
    }

    if ( list )
    {
        if ( n == 0 )
            send_to_char( self ? "Nothing is written in your diary yet.\n\r"
                               : "Nothing is written in that diary.\n\r", ch );
        else
            diary_show_list( ch, owner, days, n );
        free( days );
        return;
    }
    for ( i = 0; i < n; i++ )
        if ( days[i].day == key )
        {
            diary_show_day( ch, owner, &days[i], today );
            free( days );
            return;
        }
    {
        char date[64];

        diary_long_date( key, date, sizeof(date) );
        snprintf( buf, sizeof(buf), "Nothing is written for %s.  The diary keeps the last "
                  "%d days; DIARY LIST shows them.\n\r", date, DIARY_DAYS );
        send_to_char( buf, ch );
    }
    free( days );
}
