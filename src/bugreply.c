/***************************************************************************
 * bugreply.c -- answering a player's BUG, TYPO or IDEA with a note.
 *
 * Owner, 2026-11-22: "when players report bug reports, reply to them with
 * the fixes also". The fixes are made in a session that can only push to
 * GitHub, so the reply travels with the fix: an entry in
 * area/bug_replies.dat (code, deployed with the change it describes),
 *
 *     @ <id> <yyyy-mm-dd> <Player>
 *     the reply, one or more lines; a blank line is a paragraph break
 *
 * ended by the next "@" line or the end of the file ("#" lines are
 * comments). At every serving boot -- so the moment the fix is live --
 * each entry dated within BUG_REPLY_DAYS whose id is on no note yet is
 * posted to the board as a note from the Immortals to that player,
 * subject "Re: your report [<id>]". The board is the record: notes never
 * expire and reach git with the state sync, so a reply is posted once,
 * and the player is told of it at login like any unread note. A name
 * that is not a character's is skipped and logged. Ids are never reused.
 ***************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include "merc.h"

#define BUG_REPLY_FILE   "bug_replies.dat"
#define BUG_REPLY_DAYS   30
#define BUG_REPLY_TEXT   4096
#define BUG_REPLY_SENDER "Immortals"

static bool bug_reply_name_ok( const char *name )
{
    size_t n = strlen( name );
    size_t i;

    if ( n < 2 || n > 12 )
        return false;
    for ( i = 0; i < n; i++ )
        if ( !isalpha( (unsigned char) name[i] ) )
            return false;
    return true;
}

static bool bug_reply_id_ok( const char *id )
{
    size_t n = strlen( id );
    size_t i;

    if ( n == 0 || n > 40 )
        return false;
    for ( i = 0; i < n; i++ )
        if ( !isalnum( (unsigned char) id[i] ) && id[i] != '-' && id[i] != '_' )
            return false;
    return true;
}

static time_t bug_reply_date( const char *date )
{
    struct tm tm;
    int y, m, d;

    if ( sscanf( date, "%4d-%2d-%2d", &y, &m, &d ) != 3
    ||   y < 2000 || m < 1 || m > 12 || d < 1 || d > 31 )
        return 0;
    memset( &tm, 0, sizeof(tm) );
    tm.tm_year = y - 1900;
    tm.tm_mon = m - 1;
    tm.tm_mday = d;
    tm.tm_hour = 12;
    return mktime( &tm );
}

static bool bug_reply_posted( const char *id )
{
    char tag[64];
    NOTE_DATA *pnote;

    snprintf( tag, sizeof(tag), "[%s]", id );
    for ( pnote = note_list; pnote != NULL; pnote = pnote->next )
        if ( pnote->subject != NULL && strstr( pnote->subject, tag ) != NULL )
            return true;
    return false;
}

static void bug_reply_post( const char *id, const char *player, const char *text )
{
    char subject[96];
    char date[64];
    NOTE_DATA *pnote;
    NOTE_DATA *last;
    size_t length;

    snprintf( subject, sizeof(subject), "Re: your report [%s]", id );
    toc_strlcpy( date, ctime( &current_time ), sizeof(date) );
    length = strlen( date );
    while ( length > 0 && ( date[length - 1] == '\n' || date[length - 1] == '\r' ) )
        date[--length] = '\0';

    pnote = alloc_mem( sizeof(*pnote) );
    pnote->next       = NULL;
    pnote->sender     = str_dup( BUG_REPLY_SENDER );
    pnote->date       = str_dup( date );
    pnote->to_list    = str_dup( player );
    pnote->subject    = str_dup( subject );
    pnote->text       = str_dup( text );
    pnote->old_text   = NULL;
    pnote->date_stamp = current_time;

    if ( note_list == NULL )
        note_list = pnote;
    else
    {
        for ( last = note_list; last->next != NULL; last = last->next )
            ;
        last->next = pnote;
    }
}

/* One entry read: post it if it is due. True when a note was added. */
static bool bug_reply_entry( const char *id, const char *date, const char *player,
                             char *text )
{
    char buf[MAX_STRING_LENGTH];
    char name[16];
    time_t when = bug_reply_date( date );
    size_t length = strlen( text );

    /* No trailing blank lines on the note. */
    while ( length > 0 && ( text[length - 1] == '\n' || text[length - 1] == '\r' ) )
        text[--length] = '\0';

    if ( !bug_reply_id_ok( id ) || when == 0 || !bug_reply_name_ok( player )
    ||   text[0] == '\0' )
    {
        snprintf( buf, sizeof(buf), "Bug replies: entry '%s' is malformed; skipped.", id );
        log_string( buf );
        return false;
    }
    if ( current_time - when > (time_t) BUG_REPLY_DAYS * 24 * 60 * 60
    ||   bug_reply_posted( id ) )
        return false;

    toc_strlcpy( name, player, sizeof(name) );
    name[0] = (char) UPPER( name[0] );
    if ( player_file_presence( name ) == PLAYER_FILE_ABSENT )
    {
        snprintf( buf, sizeof(buf), "Bug replies: no character %s for '%s'; skipped.",
                  name, id );
        log_string( buf );
        return false;
    }

    bug_reply_post( id, name, text );
    snprintf( buf, sizeof(buf), "Bug replies: posted '%s' to %s.", id, name );
    log_string( buf );
    return true;
}

void bug_replies_post( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH];
    char id[64] = "";
    char date[32] = "";
    char player[32] = "";
    char *text;
    size_t used = 0;
    bool in_entry = false;
    int posted = 0;

    if ( ( fp = fopen( BUG_REPLY_FILE, "r" ) ) == NULL )
        return;
    text = malloc( BUG_REPLY_TEXT );
    if ( text == NULL )
    {
        fclose( fp );
        return;
    }
    text[0] = '\0';

    for ( ;; )
    {
        bool at_end = fgets( line, sizeof(line), fp ) == NULL;
        size_t n;

        if ( at_end || line[0] == '@' )
        {
            if ( in_entry && bug_reply_entry( id, date, player, text ) )
                posted++;
            if ( at_end )
                break;
            id[0] = date[0] = player[0] = '\0';
            if ( sscanf( line, "@ %63s %31s %31s", id, date, player ) != 3 )
            {
                log_string( "Bug replies: a header is not '@ <id> <date> <player>'; skipped." );
                in_entry = false;
                continue;
            }
            in_entry = true;
            used = 0;
            text[0] = '\0';
            continue;
        }
        if ( line[0] == '#' || !in_entry )
            continue;

        /* Lines end \n\r on the board, as NOTE + writes them. */
        n = strcspn( line, "\r\n" );
        line[n] = '\0';
        if ( used == 0 && n == 0 )
            continue;   /* no leading blank lines */
        if ( used + n + 3 >= BUG_REPLY_TEXT )
            continue;   /* too long: the rest is left off, whole lines only */
        memcpy( text + used, line, n );
        used += n;
        text[used++] = '\n';
        text[used++] = '\r';
        text[used] = '\0';
    }

    fclose( fp );
    free( text );
    if ( posted > 0 )
        save_notes( );
}
