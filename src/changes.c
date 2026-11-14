/***************************************************************************
 * changes.c -- CHANGES: what is new, without telling a player twice.
 *
 * Owner, 2026-10-04: the list had grown long enough that nobody read to the
 * end of it. CHANGES now shows what is recent and what this character has
 * not already been shown three times; CHANGES ALL shows the whole history.
 *
 * The entries live in area/changes.dat (code, not runtime state), each
 * headed "@ <id> <yyyy-mm-dd>" and ended by a blank line. Ids never change
 * and are never reused: a character's counts are kept by id, saved as
 * ChangesSeen under case 'C' in fread_char.
 *
 * A change only staff can use is headed "@ <id> <yyyy-mm-dd> staff" and
 * is shown to staff alone (owner, 2026-10-23): a player is never shown
 * it, by CHANGES or CHANGES ALL, and it is not in their count.
 ***************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "interp.h"

#define CHANGES_FILE        "changes.dat"
#define CHANGES_MAX         400
#define CHANGES_TEXT        2048
#define CHANGES_ID          24
#define CHANGES_FRESH_DAYS  14     /* older than this, only CHANGES ALL */
#define CHANGES_SHOW_TIMES  3      /* shown this often, only CHANGES ALL */

typedef struct change_entry
{
    char   id[CHANGES_ID];
    char   date[16];               /* yyyy-mm-dd */
    time_t when;
    char   text[CHANGES_TEXT];
    bool   staff;                  /* "staff" after the date */
} CHANGE_ENTRY;

static CHANGE_ENTRY *changes = NULL;
static int changes_count = 0;

static time_t change_date( const char *date )
{
    struct tm tm;
    int y, m, d;

    if ( sscanf( date, "%d-%d-%d", &y, &m, &d ) != 3 )
        return 0;
    memset( &tm, 0, sizeof(tm) );
    tm.tm_year = y - 1900;
    tm.tm_mon = m - 1;
    tm.tm_mday = d;
    tm.tm_hour = 12;
    return mktime( &tm );
}

void changes_load( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    CHANGE_ENTRY *cur = NULL;
    bool gap = false;

    if ( changes == NULL )
        changes = calloc( CHANGES_MAX, sizeof(*changes) );
    if ( changes == NULL )
        return;
    changes_count = 0;
    if ( ( fp = fopen( CHANGES_FILE, "r" ) ) == NULL )
    {
        log_string( "changes_load: no " CHANGES_FILE );
        return;
    }
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        size_t len = strlen( line );

        while ( len > 0 && ( line[len - 1] == '\n' || line[len - 1] == '\r' ) )
            line[--len] = '\0';
        /* A comment, anywhere: the website's reader (changes_index.py)
           skips one the same way. */
        if ( line[0] == '#' )
            continue;
        if ( line[0] == '@' )
        {
            if ( changes_count >= CHANGES_MAX )
                break;
            cur = &changes[changes_count++];
            memset( cur, 0, sizeof(*cur) );
            gap = false;
            {
                char tag[16];
                int fields = sscanf( line + 1, "%23s %15s %15s",
                                     cur->id, cur->date, tag );

                if ( fields < 2 )
                {
                    changes_count--;
                    cur = NULL;
                    continue;
                }
                cur->staff = fields == 3 && !str_cmp( tag, "staff" );
            }
            cur->when = change_date( cur->date );
            continue;
        }
        if ( cur == NULL )
            continue;
        /* A blank line inside an entry is a paragraph break, as the
           website shows it (review, 2026-11-13: an entry's second paragraph
           was dropped in game and shown on the website). */
        if ( line[0] == '\0' )
        {
            gap = cur->text[0] != '\0';
            continue;
        }
        if ( cur->text[0] != '\0' )
            toc_strlcat( cur->text, gap ? "\n\r\n\r" : "\n\r", sizeof(cur->text) );
        gap = false;
        toc_strlcat( cur->text, "  ", sizeof(cur->text) );
        toc_strlcat( cur->text, line, sizeof(cur->text) );
    }
    fclose( fp );
    snprintf( line, sizeof(line), "changes_load: %d entries.", changes_count );
    log_string( line );
}

/* How many times this character has been shown entry id. */
static int seen_count( CHAR_DATA *ch, const char *id )
{
    const char *p;
    size_t len = strlen( id );

    if ( IS_NPC(ch) || ch->pcdata->changes_seen == NULL )
        return 0;
    for ( p = ch->pcdata->changes_seen; *p != '\0'; )
    {
        while ( *p == ' ' )
            p++;
        if ( !strncmp( p, id, len ) && p[len] == ':' )
        {
            /* "<id>:<count>", then a space or the end; a count that is
               not a whole number is no count, as atoi made it. */
            char count[16];
            size_t n = strcspn( p + len + 1, " " );
            int seen;

            if ( n >= sizeof(count) )
                return 0;
            memcpy( count, p + len + 1, n );
            count[n] = '\0';
            return parse_int( count, INT_MIN, INT_MAX, &seen ) ? seen : 0;
        }
        while ( *p != '\0' && *p != ' ' )
            p++;
    }
    return 0;
}

/* Rewrite the counts: every entry still in the file that has been seen,
   with the ones just shown counted once more. Ids no longer in the file
   fall away, so the field stays bounded. */
static void count_shown( CHAR_DATA *ch, const bool *shown )
{
    char out[4 * MAX_STRING_LENGTH];
    char item[64];
    int i;

    if ( IS_NPC(ch) )
        return;
    out[0] = '\0';
    for ( i = 0; i < changes_count; i++ )
    {
        int n = seen_count( ch, changes[i].id ) + ( shown[i] ? 1 : 0 );

        if ( n <= 0 )
            continue;
        snprintf( item, sizeof(item), "%s%s:%d", out[0] != '\0' ? " " : "",
                  changes[i].id, UMIN( n, 99 ) );
        toc_strlcat( out, item, sizeof(out) );
    }
    free_string( ch->pcdata->changes_seen );
    ch->pcdata->changes_seen = str_dup( out );
}

static void changes_append( DString *buf, int i, const char **last_date )
{
    if ( *last_date == NULL || strcmp( *last_date, changes[i].date ) )
    {
        dstring_append_cstr( buf, "{0B" );
        dstring_append_cstr( buf, changes[i].date );
        dstring_append_cstr( buf, "{00\n\r" );
        *last_date = changes[i].date;
    }
    if ( changes[i].staff )
        dstring_append_cstr( buf, "  (staff only)\n\r" );
    dstring_append_cstr( buf, changes[i].text );
    dstring_append_cstr( buf, "\n\r\n\r" );
}

/* CHANGES, and CHANGES ALL. */
void do_changes( CHAR_DATA *ch, char *argument )
{
    /* Grown as it is written (growable output buffers, 2026-11-12): CHANGES
       ALL is past 80K, and the static 128K array it was would have cut the
       oldest entries -- and the tail -- off without a word. */
    DString buf;
    static bool shown[CHANGES_MAX];
    char arg[MAX_INPUT_LENGTH];
    const char *last_date = NULL;
    bool all, staff;
    int i, count = 0, hidden = 0;

    one_argument( argument, arg );
    all = arg[0] != '\0' && !str_prefix( arg, "all" );
    staff = is_staff( ch );
    if ( changes_count == 0 )
    {
        send_to_char( "There is no list of changes right now.\n\r", ch );
        return;
    }

    dstring_init_limit( &buf, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &buf, all ? "{0BEvery change, newest first:{00\n\r\n\r"
                                   : "{0BWhat is new, newest first:{00\n\r\n\r" );
    for ( i = 0; i < changes_count; i++ )
    {
        shown[i] = false;
        if ( changes[i].staff && !staff )
            continue;
        if ( !all )
        {
            if ( current_time - changes[i].when > CHANGES_FRESH_DAYS * 24L * 60L * 60L
            ||   seen_count( ch, changes[i].id ) >= CHANGES_SHOW_TIMES )
            {
                hidden++;
                continue;
            }
            shown[i] = true;
        }
        changes_append( &buf, i, &last_date );
        count++;
    }

    if ( !all && count == 0 )
    {
        send_to_char( "Nothing new since you last looked.  CHANGES ALL shows every change.\n\r", ch );
        dstring_free( &buf );
        return;
    }
    if ( !all )
    {
        char tail[MAX_INPUT_LENGTH];

        snprintf( tail, sizeof(tail),
                  "An entry stops showing here once you have seen it three times, or\n\r"
                  "after two weeks.  CHANGES ALL shows all %d.\n\r", count + hidden );
        dstring_append_cstr( &buf, tail );
        count_shown( ch, shown );
    }
    page_to_char( dstring_cstr( &buf ), ch );
    dstring_free( &buf );
}
