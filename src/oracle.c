/***************************************************************************
 * The Oracle -- a seer who answers questions about the game by asking Claude.
 *
 * She is prayed for, not placed.  PRAY brings her into the room with the
 * supplicant, the way Herbie appears; she attends that one person until they
 * say they are DONE, walk out of the room, or fall silent for a few minutes,
 * at which point she fades away.  Only one person may have her at a time -- a
 * second supplicant is told she is busy -- so the questions, and the API
 * spend behind them, stay bounded.
 *
 * The MUD is single-process and must never block on a network call, so the
 * work crosses a file bridge, the same shape as the web-admin command queue:
 *   - ASK, or a spoken question, spools to "oracle.ask".
 *   - The web service (webadmin/oracle.py) polls it, calls Claude, and appends
 *     "<player>\t<answer>" to "oracle.answer".
 *   - spec_oracle drains "oracle.answer" on the mob's pulse and speaks each
 *     answer to the one who asked, and retires her when she is owed no more.
 *
 * Every summoning is announced to staff (wizinfo) and every question and
 * answer is written to a durable transcript (../log/oracle.tsv) so an
 * immortal can replay any conversation at any time with ORACLE.
 *
 * None of it does anything until the web service has an API key and is
 * enabled, so the whole feature is free and silent turned off.
 ***************************************************************************/

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200112L
#endif

#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 600
#endif

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "merc.h"

/* Both spools live in the game working directory (area/), beside
   webadmin.queue, so the two processes agree on where they are.  The
   transcript lives in ../log with the other journals. */
#define ORACLE_ASK_FILE      "oracle.ask"
#define ORACLE_ANSWER_FILE   "oracle.answer"
#define ORACLE_JOURNAL_FILE  "../log/oracle.tsv"

/* She leaves after this long with no question from her supplicant. */
#define ORACLE_IDLE_SECONDS  180

/* One summoning at a time.  oracle_mob is cleared on every path that removes
   her (oracle_on_char_from_room catches the extraction), so it is valid
   whenever it is non-NULL.  The summoner is held by name, not pointer, so a
   quit or death cannot leave a dangling reference. */
static CHAR_DATA *oracle_mob      = NULL;
static char       oracle_summoner[MAX_INPUT_LENGTH] = "";
static int        oracle_room_vnum = 0;
static time_t     oracle_last      = 0;


static CHAR_DATA *oracle_mob_in_room( ROOM_INDEX_DATA *room )
{
    CHAR_DATA *mob;

    if ( room == NULL )
        return NULL;

    for ( mob = room->people; mob != NULL; mob = mob->next_in_room )
    {
        if ( IS_NPC(mob) && mob->pIndexData != NULL
          && mob->pIndexData->vnum == MOB_VNUM_ORACLE )
            return mob;
    }

    return NULL;
}


bool oracle_here( CHAR_DATA *ch )
{
    return ch != NULL && ch->in_room != NULL
        && oracle_mob_in_room( ch->in_room ) != NULL;
}


/*
 * Collapse anything that would break the tab-separated records or carry
 * control data into the request file: tabs, newlines and other control bytes
 * become spaces, runs of space are squeezed, and the result is trimmed and
 * bounded.
 */
static void oracle_sanitize( char *dest, size_t size, const char *src )
{
    size_t len = 0;
    bool last_space = TRUE;   /* TRUE so a leading space is dropped */

    if ( src == NULL )
        src = "";

    while ( *src != '\0' && len + 1 < size )
    {
        unsigned char c = (unsigned char) *src++;

        if ( c == '\t' || c == '\n' || c == '\r' || c < 32 || c == 127 )
            c = ' ';

        if ( c == ' ' )
        {
            if ( last_space )
                continue;
            last_space = TRUE;
        }
        else
        {
            last_space = FALSE;
        }

        dest[len++] = (char) c;
    }

    while ( len > 0 && dest[len - 1] == ' ' )
        len--;
    dest[len] = '\0';
}


/* Append one record to the durable transcript for immortal playback. */
static void oracle_journal( const char *role, const char *who, int room_vnum,
                            const char *text )
{
    FILE *fp;
    char clean[MAX_STRING_LENGTH];

    fp = fopen( ORACLE_JOURNAL_FILE, "a" );
    if ( fp == NULL )
        return;

    oracle_sanitize( clean, sizeof(clean), text );
    fprintf( fp, "%ld\t%d\t%s\t%s\t%s\n",
             (long) ( current_time > 0 ? current_time : time(NULL) ),
             room_vnum, role, who != NULL ? who : "?", clean );
    fclose( fp );
}


/*
 * Send her home.  Clears the globals first, then speaks the farewell and
 * extracts the mob, so the extraction's own char_from_room pass finds the
 * globals already clear and does nothing.
 */
static void oracle_dismiss( void )
{
    CHAR_DATA *mob = oracle_mob;

    oracle_mob = NULL;
    oracle_summoner[0] = '\0';
    oracle_room_vnum = 0;
    oracle_last = 0;

    if ( mob != NULL )
    {
        if ( mob->in_room != NULL )
            act( "$n closes her eyes and fades from view.",
                mob, NULL, NULL, TO_ROOM );
        extract_char( mob, TRUE );
    }
}


/*
 * Called from char_from_room for every character that leaves a room.  If her
 * supplicant walks out she returns whence she came; if she herself is being
 * removed (by any path) the globals are simply cleared.
 */
void oracle_on_char_from_room( CHAR_DATA *ch )
{
    if ( oracle_mob == NULL || ch == NULL )
        return;

    if ( ch == oracle_mob )
    {
        oracle_mob = NULL;
        oracle_summoner[0] = '\0';
        oracle_room_vnum = 0;
        oracle_last = 0;
        return;
    }

    if ( !IS_NPC(ch) && ch->name != NULL
      && !str_cmp( ch->name, oracle_summoner ) )
        oracle_dismiss();
}


/* A word that ends a session, said rather than asked. */
static bool oracle_is_farewell( const char *said )
{
    static const char * const words[] =
    {
        "exit", "done", "bye", "goodbye", "farewell", "thanks",
        "thank you", "that is all", "nevermind", "leave", NULL
    };
    int i;

    for ( i = 0; words[i] != NULL; i++ )
        if ( !str_cmp( said, words[i] ) )
            return TRUE;

    return FALSE;
}


/*
 * Should a spoken line reach the Oracle?  A question (ends in '?') or a
 * farewell does; ordinary room chat does not, so casual talk near her never
 * spends an API call.
 */
bool oracle_hears( const char *argument )
{
    char said[MAX_INPUT_LENGTH];
    size_t len;

    oracle_sanitize( said, sizeof(said), argument );
    len = strlen( said );
    if ( len == 0 )
        return FALSE;

    if ( said[len - 1] == '?' )
        return TRUE;

    {
        size_t i;
        for ( i = 0; i < len; i++ )
            said[i] = (char) LOWER( said[i] );
    }
    return oracle_is_farewell( said );
}


/* Spool one question for the out-of-process poller. */
static bool oracle_spool_question( CHAR_DATA *ch, const char *question )
{
    FILE *fp;
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    struct flock lock;
#endif

    fp = fopen( ORACLE_ASK_FILE, "a" );
    if ( fp == NULL )
        return FALSE;

#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    memset( &lock, 0, sizeof(lock) );
    lock.l_type = F_WRLCK;
    lock.l_whence = SEEK_SET;
    if ( fcntl( fileno(fp), F_SETLKW, &lock ) == -1 )
    {
        fclose( fp );
        return FALSE;
    }
#endif

    fprintf( fp, "%ld\t%s\t%s\n",
             (long) ( current_time > 0 ? current_time : time(NULL) ),
             ch->name, question );

    fclose( fp );   /* closing releases the advisory lock */
    return TRUE;
}


/*
 * A question for the Oracle, from ASK or from a spoken question.  Only the
 * supplicant she was prayed for may drive her; a farewell retires her.
 */
void oracle_listen( CHAR_DATA *ch, const char *argument )
{
    char question[MAX_INPUT_LENGTH];
    char said[MAX_INPUT_LENGTH];
    CHAR_DATA *mob;
    size_t i;

    if ( ch == NULL || IS_NPC(ch) || argument == NULL )
        return;

    if ( ( mob = oracle_mob_in_room( ch->in_room ) ) == NULL )
        return;

    oracle_sanitize( question, sizeof(question), argument );

    if ( question[0] == '\0' )
    {
        act( "$n says 'Ask, and be plain about it.'", mob, NULL, ch, TO_VICT );
        return;
    }

    /* Only the one she came for may speak with her. */
    if ( str_cmp( ch->name, oracle_summoner ) != 0 )
    {
        char buf[MAX_INPUT_LENGTH];
        snprintf( buf, sizeof(buf),
                  "$n is attending to %s just now.  Wait, or pray when she is free.",
                  oracle_summoner[0] != '\0' ? oracle_summoner : "another" );
        act( buf, mob, NULL, ch, TO_VICT );
        return;
    }

    for ( i = 0; question[i] != '\0' && i + 1 < sizeof(said); i++ )
        said[i] = (char) LOWER( question[i] );
    said[i] = '\0';

    if ( oracle_is_farewell( said ) )
    {
        act( "$n inclines her head.  'Go well.'", mob, NULL, ch, TO_VICT );
        oracle_journal( "DONE", ch->name,
                        ch->in_room != NULL ? ch->in_room->vnum : 0, said );
        oracle_dismiss();
        return;
    }

    if ( !oracle_spool_question( ch, question ) )
    {
        act( "$n murmurs, 'The mists are closed to me just now.'",
            mob, NULL, ch, TO_VICT );
        return;
    }

    oracle_last = current_time > 0 ? current_time : time(NULL);
    oracle_journal( "Q", ch->name,
                    ch->in_room != NULL ? ch->in_room->vnum : 0, question );

    act( "$n gazes at you, then closes $s eyes, considering your question.",
        mob, NULL, ch, TO_VICT );
    act( "$n gazes at $N, then closes $s eyes.",
        mob, NULL, ch, TO_NOTVICT );

    watch_log( ch, "asked the Oracle: %s", question );
}


void do_ask( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *mob;

    if ( IS_NPC(ch) )
        return;

    if ( ( mob = oracle_mob_in_room( ch->in_room ) ) == NULL )
    {
        send_to_char(
            "There is no seer here.  PRAY, and the Oracle may come to you.\n\r",
            ch );
        return;
    }

    if ( argument[0] == '\0' )
    {
        act( "$n says 'Speak your question:  ask <your question>.'",
            mob, NULL, ch, TO_VICT );
        return;
    }

    oracle_listen( ch, argument );
}


/* Deliver one answer to the player who asked, if they are still here. */
static void oracle_deliver( CHAR_DATA *mob, const char *player,
                            const char *answer )
{
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *vch;

    for ( vch = mob->in_room->people; vch != NULL; vch = vch->next_in_room )
    {
        if ( !IS_NPC(vch) && vch->name != NULL && !str_cmp( vch->name, player ) )
            break;
    }

    oracle_journal( "A", player,
                    mob->in_room != NULL ? mob->in_room->vnum : 0, answer );

    if ( vch == NULL )
        return;   /* they walked off; the answer is dropped */

    snprintf( buf, sizeof(buf),
              "{%02X$n opens her eyes, turns to $N, and says, '$t'{00",
              COL_SAYS );
    act_new_cstr( buf, mob, answer, vch, TO_ROOM, POS_RESTING );

    snprintf( buf, sizeof(buf), "Oracle answered %s in room %d: %s",
              vch->name, mob->in_room != NULL ? mob->in_room->vnum : 0, answer );
    log_string( buf );

    {
        CHAR_DATA *rch;

        for ( rch = mob->in_room->people; rch != NULL; rch = rch->next_in_room )
        {
            if ( IS_NPC(rch) || rch->desc == NULL )
                continue;
            if ( rch->position < POS_RESTING )
                continue;
            gmcp_send_channel( rch->desc, "say", mob->short_descr, answer );
        }
    }
}


/*
 * The Oracle's pulse: deliver any ready answers, then retire her if her
 * supplicant has gone quiet.  Only ever called as (mob, NULL, NULL, NULL).
 */
bool spec_oracle( CHAR_DATA *mob, CHAR_DATA *ch, DO_FUN *cmd, char *arg )
{
    FILE *fp;
    FILE *pending;
    char buf[MAX_STRING_LENGTH];
    struct stat fst;
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    struct flock lock;
#endif

    UNUSED_PARAM(ch);
    UNUSED_PARAM(cmd);
    UNUSED_PARAM(arg);

    if ( mob == NULL || mob->in_room == NULL )
        return FALSE;

    if ( stat( ORACLE_ANSWER_FILE, &fst ) != -1 && fst.st_size > 0
      && ( fp = fopen( ORACLE_ANSWER_FILE, "r+" ) ) != NULL )
    {
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
        memset( &lock, 0, sizeof(lock) );
        lock.l_type = F_WRLCK;
        lock.l_whence = SEEK_SET;
        if ( fcntl( fileno(fp), F_SETLK, &lock ) == -1 )
        {
            fclose( fp );   /* poller mid-write; next pulse */
        }
        else
#endif
        {
            pending = tmpfile();
            if ( pending == NULL )
            {
                fclose( fp );
            }
            else
            {
                int staged_ok = 1;

                while ( fgets( buf, sizeof(buf), fp ) != NULL )
                {
                    if ( fputs( buf, pending ) == EOF )
                        break;
                }
                if ( ferror(fp) || ferror(pending) || fflush(pending) != 0 )
                    staged_ok = 0;

                if ( staged_ok )
                {
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
                    if ( ftruncate( fileno(fp), 0 ) != 0 )
                        staged_ok = 0;
                    fclose( fp );
#else
                    {
                        FILE *clear = freopen( ORACLE_ANSWER_FILE, "w", fp );
                        if ( clear == NULL )
                            staged_ok = 0;
                        else
                            fclose( clear );
                    }
#endif
                }
                else
                {
                    fclose( fp );
                }

                if ( staged_ok )
                {
                    rewind( pending );
                    while ( fgets( buf, sizeof(buf), pending ) != NULL )
                    {
                        char *answer;
                        size_t len = strlen( buf );

                        while ( len > 0
                          && ( buf[len - 1] == '\n' || buf[len - 1] == '\r' ) )
                            buf[--len] = '\0';
                        if ( buf[0] == '\0' )
                            continue;
                        answer = strchr( buf, '\t' );
                        if ( answer == NULL )
                            continue;
                        *answer++ = '\0';
                        if ( buf[0] == '\0' || answer[0] == '\0' )
                            continue;
                        oracle_deliver( mob, buf, answer );
                    }
                }
                fclose( pending );
            }
        }
    }

    /* Retire her if her supplicant has fallen silent. */
    if ( oracle_mob != NULL && oracle_last > 0
      && (long) ( ( current_time > 0 ? current_time : time(NULL) ) - oracle_last )
         > ORACLE_IDLE_SECONDS )
    {
        act( "$n says 'You have fallen quiet.  I will return to my rest.'",
            mob, NULL, NULL, TO_ROOM );
        oracle_dismiss();
        return TRUE;
    }

    return FALSE;
}


/*
 * PRAY -- a supplicant calls the Oracle to them.  One at a time; a second
 * caller is turned away while she is attending someone.
 */
void do_pray( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    MOB_INDEX_DATA *idx;
    CHAR_DATA *mob;

    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) )
        return;

    if ( ch->in_room == NULL )
    {
        send_to_char( "You are nowhere the Oracle could reach you.\n\r", ch );
        return;
    }

    if ( oracle_mob != NULL )
    {
        if ( !str_cmp( oracle_summoner, ch->name )
          && oracle_mob->in_room == ch->in_room )
            send_to_char( "The Oracle is already here, attending you.\n\r", ch );
        else
        {
            snprintf( buf, sizeof(buf),
                "The Oracle is attending to someone else right now.  "
                "Pray again in a little while.\n\r" );
            send_to_char( buf, ch );
        }
        return;
    }

    if ( ( idx = get_mob_index( MOB_VNUM_ORACLE ) ) == NULL )
    {
        send_to_char( "You pray, but no answer comes.\n\r", ch );
        return;
    }

    mob = create_mobile( idx );
    mob->spec_fun = spec_lookup( "spec_oracle" );
    char_to_room( mob, ch->in_room );

    oracle_mob = mob;
    toc_strlcpy( oracle_summoner, ch->name, sizeof(oracle_summoner) );
    oracle_room_vnum = ch->in_room->vnum;
    oracle_last = current_time > 0 ? current_time : time(NULL);

    act( "You bow your head in prayer.  The air stirs, and the Oracle fades "
        "into being before you.", ch, NULL, NULL, TO_CHAR );
    act( "$n bows in prayer, and the Oracle fades into being.",
        ch, NULL, NULL, TO_ROOM );
    act( "$n murmurs, 'Ask what you will.  Say DONE when you are finished.'",
        mob, NULL, NULL, TO_ROOM );

    snprintf( buf, sizeof(buf), "Oracle: %s prayed; she appeared in room %d (%s).",
              ch->name, ch->in_room->vnum,
              ch->in_room->name != NULL ? ch->in_room->name : "?" );
    log_string( buf );
    wizinfo( buf, LEVEL_IMMORTAL );
    oracle_journal( "SUMMON", ch->name, ch->in_room->vnum, "" );
}


/* Read the last of the transcript back for an immortal. */
static void oracle_show_transcript( CHAR_DATA *ch )
{
#define ORACLE_TAIL 24
    FILE *fp;
    char ring[ORACLE_TAIL][MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH];
    char out[MAX_STRING_LENGTH];
    int count = 0;
    int i;

    fp = fopen( ORACLE_JOURNAL_FILE, "r" );
    if ( fp == NULL )
    {
        send_to_char( "No Oracle conversations have been recorded yet.\n\r", ch );
        return;
    }

    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        size_t len = strlen( line );
        while ( len > 0 && ( line[len - 1] == '\n' || line[len - 1] == '\r' ) )
            line[--len] = '\0';
        toc_strlcpy( ring[count % ORACLE_TAIL], line, sizeof(ring[0]) );
        count++;
    }
    fclose( fp );

    if ( count == 0 )
    {
        send_to_char( "No Oracle conversations have been recorded yet.\n\r", ch );
        return;
    }

    send_to_char( "Recent Oracle conversations:\n\r", ch );

    i = count > ORACLE_TAIL ? count - ORACLE_TAIL : 0;
    for ( ; i < count; i++ )
    {
        char copy[MAX_STRING_LENGTH];
        char *role;
        char *who;
        char *text;

        toc_strlcpy( copy, ring[i % ORACLE_TAIL], sizeof(copy) );
        strtok( copy, "\t" );            /* epoch, discarded */
        strtok( NULL, "\t" );            /* room, discarded */
        role = strtok( NULL, "\t" );
        who  = strtok( NULL, "\t" );
        text = strtok( NULL, "" );

        snprintf( out, sizeof(out), "  %-6s %-12s %s\n\r",
                  role != NULL ? role : "?",
                  who  != NULL ? who  : "?",
                  text != NULL ? text : "" );
        send_to_char( out, ch );
    }
#undef ORACLE_TAIL
}


/*
 * ORACLE -- staff status, playback and control.
 *   oracle            status, and the recent transcript
 *   oracle dismiss    send her home now
 */
void do_oracle( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];

    one_argument( argument, arg );

    if ( !str_prefix( arg, "dismiss" ) || !str_prefix( arg, "purge" ) )
    {
        if ( oracle_mob == NULL )
        {
            send_to_char( "The Oracle is not abroad.\n\r", ch );
            return;
        }
        snprintf( buf, sizeof(buf), "Oracle: %s sent her home (was attending %s).",
                  ch->name, oracle_summoner );
        log_string( buf );
        wizinfo( buf, LEVEL_IMMORTAL );
        oracle_dismiss();
        send_to_char( "You send the Oracle home.\n\r", ch );
        return;
    }

    if ( oracle_mob != NULL )
        snprintf( buf, sizeof(buf),
                  "The Oracle attends %s in room %d.\n\r",
                  oracle_summoner, oracle_room_vnum );
    else
        snprintf( buf, sizeof(buf), "The Oracle is not currently summoned.\n\r" );
    send_to_char( buf, ch );

    oracle_show_transcript( ch );
}
