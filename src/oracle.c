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
#include "interp.h"

/* Both spools live in the game working directory (area/), beside
   webadmin.queue, so the two processes agree on where they are.  The
   transcript lives in ../log with the other journals. */
#define ORACLE_ASK_FILE      "oracle.ask"
#define ORACLE_ANSWER_FILE   "oracle.answer"
#define ORACLE_JOURNAL_FILE  "../log/oracle.tsv"

/* An audience in her sanctum lasts at most this long, and ends sooner after
   this much silence.  She warns a minute before the end. */
#define ORACLE_SESSION_SECONDS 300
#define ORACLE_IDLE_SECONDS    180

/* The model answers an off-topic question with exactly this token; she turns
   it into a refusal rather than speaking it.  After this many in one sitting
   she leaves and the offender is held out for a while. */
#define ORACLE_OFFTOPIC          "__OFFTOPIC__"
#define ORACLE_OFFTOPIC_MAX      3
#define ORACLE_COOLDOWN_SECONDS  300

/* One summoning at a time.  oracle_mob is cleared on every path that removes
   her (oracle_on_char_from_room catches the extraction), so it is valid
   whenever it is non-NULL.  The summoner is held by name, not pointer, so a
   quit or death cannot leave a dangling reference. */
static CHAR_DATA *oracle_mob      = NULL;
static char       oracle_summoner[MAX_INPUT_LENGTH] = "";
static int        oracle_room_vnum = 0;
static time_t     oracle_last      = 0;

/* The audience: where the supplicant prayed from (a vnum, so a room that is
   later freed cannot dangle), when it began, and whether she has warned. */
static int        oracle_origin_vnum = 0;
static time_t     oracle_started     = 0;
static bool       oracle_warned      = FALSE;

/* Off-topic strikes this sitting, and a short hold on an offender after she
   walks out on them.  In memory only -- a reboot forgives, which is fine for
   an abuse cooldown; the lasting bar is the immortal flag, handled elsewhere. */
static int        oracle_strikes = 0;
static char       oracle_cooldown_name[MAX_INPUT_LENGTH] = "";
static time_t     oracle_cooldown_until = 0;

/* The last question asked this sitting and the last real answer given, so a
   supplicant who says WRONG files a report naming exactly what was wrong. */
static char       oracle_last_question[MAX_INPUT_LENGTH] = "";
static char       oracle_last_answer[MAX_INPUT_LENGTH * 2] = "";  /* answers are under 500 */

/* A record whose question field starts with this byte is a message from the
   game to the poller, not a question.  oracle_sanitize turns every control
   byte a player types into a space, so no player can forge one. */
#define ORACLE_CONTROL       '\001'


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


/* Is this character the Oracle?  She is never a valid target: attack, spell
   and slay paths check this so she cannot be fought, slain or farslain.  An
   immortal who wants her gone uses ORACLE DISMISS. */
bool is_oracle_mob( CHAR_DATA *ch )
{
    return ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
        && ch->pIndexData->vnum == MOB_VNUM_ORACLE;
}


/* Killuminati is warded against every hostile rite, even a god's. */
bool is_killuminati( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC(ch) && ch->name != NULL
        && !str_cmp( ch->name, "Killuminati" );
}


/* The Oracle, Herbie and Killuminati: warded against the ordinary rites
   (farslay scroll, fatality). The god-level FARSLAY command answers only to
   the narrower is_killuminati(). */
bool is_divinely_warded( CHAR_DATA *ch )
{
    return is_oracle_mob( ch )
        || ( ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
          && ch->pIndexData->vnum == MOB_VNUM_HERBIE )
        || is_killuminati( ch );
}


/* The blade -- farslay or slay -- turned back on the one who threw it, 100%,
   mortal or god. */
void divine_ward_backfire( CHAR_DATA *ch, CHAR_DATA *victim )
{
    char buf[MAX_STRING_LENGTH];

    if ( ch == NULL || victim == NULL )
        return;

    act( "A bright and holy light erupts in front of $N, redirecting the strike back at you!",
        ch, NULL, victim, TO_CHAR );
    act( "A bright and holy light erupts in front of $N, redirecting the strike back at $n!",
        ch, NULL, victim, TO_ROOM );
    act( "$n is DEAD!!", ch, NULL, NULL, TO_ROOM );
    send_to_char( "You have been KILLED!!\n\r\n\r", ch );
    ch->hit = 1;
    ch->mana = 1;
    ch->move = 1;
    snprintf( buf, sizeof(buf),
              "%s struck at %s and was struck down by the ward.",
              ch->name, victim->name );
    wizinfo( buf, LEVEL_IMMORTAL );
    log_string( buf );
    raw_kill( ch, ch );
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


/* Coming back to the world leaves a supplicant dazed for a tick, so the
   sanctum is never a way to step out of trouble and straight back in. */
#define ORACLE_RETURN_LAG    PULSE_TICK

static void oracle_come_back( CHAR_DATA *ch )
{
    if ( ch == NULL )
        return;
    send_to_char( "You stagger, dazed, as the world rushes back in around you.\n\r", ch );
    WAIT_STATE( ch, ORACLE_RETURN_LAG );
}


/*
 * The room to write in a player file instead of the sanctum, or 0 if the
 * character is not in it.  Nobody wakes up in her sanctum: her supplicant is
 * saved at the room they prayed from, anyone else at the Temple.
 */
int oracle_saved_room( CHAR_DATA *ch )
{
    if ( ch == NULL || ch->in_room == NULL
      || ch->in_room->vnum != ROOM_VNUM_ORACLE )
        return 0;

    if ( !IS_NPC(ch) && ch->name != NULL && oracle_origin_vnum > 0
      && !str_cmp( ch->name, oracle_summoner )
      && get_room_index( oracle_origin_vnum ) != NULL )
        return oracle_origin_vnum;

    return ROOM_VNUM_TEMPLE;
}


/* Point the sanctum's way out -- the bead curtain, down -- at a room. */
static void oracle_set_way_out( ROOM_INDEX_DATA *to )
{
    ROOM_INDEX_DATA *sanctum = get_room_index( ROOM_VNUM_ORACLE );

    if ( sanctum != NULL && to != NULL && sanctum->exit[DIR_DOWN] != NULL )
        sanctum->exit[DIR_DOWN]->u1.to_room = to;
}


/* Where the supplicant goes home to: the room they prayed in, or the Temple
   if that room is gone. */
static ROOM_INDEX_DATA *oracle_home( int vnum )
{
    ROOM_INDEX_DATA *home = vnum > 0 ? get_room_index( vnum ) : NULL;

    return home != NULL ? home : get_room_index( ROOM_VNUM_TEMPLE );
}


/*
 * End the audience.  Clears the globals first, so the char_from_room passes
 * below find nothing to do, then the Oracle fades and -- when send_home is
 * set -- the supplicant is returned to the room they prayed in.  send_home is
 * FALSE when they are already leaving on their own (walking down the bead
 * curtain, quitting, being summoned away): moving them again would fight the
 * move already in progress.  The way out is left pointing at their home
 * either way, so the curtain still leads back.
 */
static void oracle_dismiss( bool send_home )
{
    CHAR_DATA *mob = oracle_mob;
    ROOM_INDEX_DATA *sanctum = get_room_index( ROOM_VNUM_ORACLE );
    ROOM_INDEX_DATA *home = oracle_home( oracle_origin_vnum );
    char who[MAX_INPUT_LENGTH];

    toc_strlcpy( who, oracle_summoner, sizeof(who) );
    oracle_mob = NULL;
    oracle_summoner[0] = '\0';
    oracle_room_vnum = 0;
    oracle_last = 0;
    oracle_origin_vnum = 0;
    oracle_started = 0;
    oracle_warned = FALSE;
    oracle_last_question[0] = '\0';
    oracle_last_answer[0] = '\0';

    if ( mob != NULL )
    {
        if ( mob->in_room != NULL )
            act( "$n closes her eyes and fades from view.",
                mob, NULL, NULL, TO_ROOM );
        extract_char( mob, TRUE );
    }

    if ( send_home && sanctum != NULL && home != NULL && who[0] != '\0' )
    {
        CHAR_DATA *vch;
        CHAR_DATA *vch_next;

        for ( vch = sanctum->people; vch != NULL; vch = vch_next )
        {
            vch_next = vch->next_in_room;
            if ( IS_NPC(vch) || vch->name == NULL || str_cmp( vch->name, who ) )
                continue;

            send_to_char( "The incense thickens into mist, and the sanctum fades away.\n\r", vch );
            char_from_room( vch );
            char_to_room( vch, home );
            act( "$n steps out of a thinning curl of incense smoke.",
                vch, NULL, NULL, TO_ROOM );
            do_look( vch, "auto" );
            oracle_come_back( vch );
            break;
        }
    }
}


/*
 * Called from char_from_room for every character that leaves a room.  If her
 * supplicant leaves the sanctum -- down the bead curtain, quitting, summoned
 * away -- the audience ends.  If she herself is being removed (by any path)
 * the globals are simply cleared.
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
        oracle_origin_vnum = 0;
        oracle_started = 0;
        oracle_warned = FALSE;
        oracle_last_question[0] = '\0';
        oracle_last_answer[0] = '\0';
        return;
    }

    if ( !IS_NPC(ch) && ch->name != NULL
      && !str_cmp( ch->name, oracle_summoner ) )
    {
        /* Leaving on their own -- down the bead curtain, or summoned away --
           still costs the daze of coming back. */
        oracle_come_back( ch );
        oracle_dismiss( FALSE );
    }
}


/* Does what was said match one of these phrases?  Trailing punctuation is
   ignored, so "done.", "Done!" and "thanks?" all count. */
static bool oracle_said_one_of( const char *said, const char * const *words )
{
    char word[MAX_INPUT_LENGTH];
    size_t len;
    int i;

    toc_strlcpy( word, said, sizeof(word) );
    len = strlen( word );
    while ( len > 0 && ( word[len - 1] == '.' || word[len - 1] == '!'
                      || word[len - 1] == '?' || word[len - 1] == ' ' ) )
        word[--len] = '\0';

    for ( i = 0; words[i] != NULL; i++ )
        if ( !str_cmp( word, words[i] ) )
            return TRUE;

    return FALSE;
}


/* A word that ends the audience. */
static bool oracle_is_farewell( const char *said )
{
    static const char * const words[] =
    {
        "exit", "done", "bye", "goodbye", "farewell", "thanks",
        "thank you", "that is all", "nevermind", "leave", NULL
    };

    return oracle_said_one_of( said, words );
}


/* The supplicant disputing her last answer. */
static bool oracle_is_dispute( const char *said )
{
    static const char * const words[] =
    {
        "wrong", "that's wrong", "thats wrong", "that is wrong",
        "you're wrong", "youre wrong", "you are wrong", "incorrect",
        "that's incorrect", "that is incorrect", "not true", "that's not true",
        "that is not true", NULL
    };

    return oracle_said_one_of( said, words );
}


/* One Hyrule item's name for the state field, with the field's own
   separators taken out. */
static void oracle_state_item( char *out, size_t size, OBJ_DATA *obj, int *count )
{
    char name[MAX_INPUT_LENGTH];
    char *p;

    if ( obj->pIndexData == NULL || !IS_HYRULE_ROOM_VNUM( obj->pIndexData->vnum )
    ||   *count >= 40 )
        return;
    toc_strlcpy( name, obj->short_descr != NULL ? obj->short_descr : "?", sizeof(name) );
    for ( p = name; *p != '\0'; p++ )
        if ( *p == '|' || *p == ';' || *p == '=' )
            *p = ' ';
    if ( *count > 0 )
        toc_strlcat( out, "|", size );
    toc_strlcat( out, name, size );
    (*count)++;
}

/*
 * Where the asker stands, for the poller's routes, and how far along
 * Hyrule they are: "room=30237;hyrule_next=4;hyrule_items=the raft|...".
 * Items are what they carry from Hyrule's own catalog, in hand, worn or one
 * bag down -- what the dungeon gates themselves ask (hyrule_carries).
 */
static void oracle_state( CHAR_DATA *ch, char *out, size_t size )
{
    OBJ_DATA *obj;
    OBJ_DATA *in;
    int count = 0;

    snprintf( out, size, "room=%d;hyrule_next=%d;hyrule_items=",
              ch->in_room != NULL ? ch->in_room->vnum : 0, hyrule_next_level( ch ) );
    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        oracle_state_item( out, size, obj, &count );
        for ( in = obj->contains; in != NULL; in = in->next_content )
            oracle_state_item( out, size, in, &count );
    }
}

/* Spool one record for the out-of-process poller: a question, or -- when it
   begins with ORACLE_CONTROL -- a message from the game itself. */
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

    /* A real question carries the asker's abilities and where they stand
       as two last fields, so "what am I missing" and "how do I get there
       from here" are answered from the game (abilities.c, oracle_state). */
    if ( question[0] != ORACLE_CONTROL && !IS_NPC(ch) )
    {
        static char summary[4 * MAX_STRING_LENGTH];
        static char clean[4 * MAX_STRING_LENGTH];
        char state[MAX_STRING_LENGTH];
        char state_clean[MAX_STRING_LENGTH];

        abilities_oracle_summary( ch, summary, sizeof(summary) );
        oracle_sanitize( clean, sizeof(clean), summary );
        oracle_state( ch, state, sizeof(state) );
        oracle_sanitize( state_clean, sizeof(state_clean), state );
        fprintf( fp, "%ld\t%s\t%s\tABILITIES:%s\tSTATE:%s\n",
                 (long) ( current_time > 0 ? current_time : time(NULL) ),
                 ch->name, question, clean, state_clean );
    }
    else
        fprintf( fp, "%ld\t%s\t%s\n",
                 (long) ( current_time > 0 ? current_time : time(NULL) ),
                 ch->name, question );

    fclose( fp );   /* closing releases the advisory lock */
    return TRUE;
}


/* Tell the poller something about this supplicant: SITTING when a new
   audience begins (so it forgets the last one's conversation), WRONG when
   they dispute an answer (so it stops serving that answer from its cache). */
static void oracle_spool_control( CHAR_DATA *ch, const char *verb )
{
    char record[MAX_INPUT_LENGTH];

    snprintf( record, sizeof(record), "%c%s", ORACLE_CONTROL, verb );
    oracle_spool_question( ch, record );
}


/* WRONG: file the disputed exchange where staff will see it, and tell the
   poller to drop it. */
static void oracle_dispute( CHAR_DATA *ch, CHAR_DATA *mob )
{
    char report[MAX_STRING_LENGTH];

    if ( oracle_last_answer[0] == '\0' )
    {
        act( "$n says 'I have told you nothing yet.'", mob, NULL, ch, TO_VICT );
        return;
    }

    snprintf( report, sizeof(report), "[Oracle] disputed answer.  Q: %s  A: %s",
              oracle_last_question[0] != '\0' ? oracle_last_question : "?",
              oracle_last_answer );
    append_file( ch, BUG_FILE, report );
    oracle_journal( "WRONG", ch->name,
                    ch->in_room != NULL ? ch->in_room->vnum : 0,
                    oracle_last_answer );
    oracle_spool_control( ch, "WRONG" );
    oracle_last_answer[0] = '\0';

    act( "$n frowns, and the mist around her stirs.  'Then my sight was "
        "clouded.  The gods will hear of it.'", mob, NULL, ch, TO_VICT );
    watch_log( ch, "disputed an Oracle answer" );
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
        char buf[MAX_STRING_LENGTH];
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
        oracle_dismiss( TRUE );
        return;
    }

    if ( oracle_is_dispute( said ) )
    {
        oracle_last = current_time > 0 ? current_time : time(NULL);
        oracle_dispute( ch, mob );
        return;
    }

    if ( !oracle_spool_question( ch, question ) )
    {
        act( "$n murmurs, 'The mists are closed to me just now.'",
            mob, NULL, ch, TO_VICT );
        return;
    }

    oracle_last = current_time > 0 ? current_time : time(NULL);
    toc_strlcpy( oracle_last_question, question, sizeof(oracle_last_question) );
    oracle_journal( "Q", ch->name,
                    ch->in_room != NULL ? ch->in_room->vnum : 0, question );

    /* Flush the character to disk so the out-of-process poller reads the gear
       and level they have this moment, not whatever the last autosave caught. */
    save_char_obj( ch );

    act( "$n gazes at you, then closes $s eyes, considering your question.",
        mob, NULL, ch, TO_VICT );
    act( "$n gazes at $N, then closes $s eyes.",
        mob, NULL, ch, TO_NOTVICT );

    watch_log( ch, "asked the Oracle: %s", question );
}


/* ---------------------------------------------------------------- live
 * Read-only live-world lookups, so the Oracle can answer "who has X", "where
 * is X" and "what is Y wearing" from the running game.  The web poller writes
 * a request to oracle.query; this drains it on the game pulse, runs a FIXED
 * set of read-only scans -- never interpret(), never a command -- and writes
 * the finding to oracle.queryresult.  Nothing the model emits can reach this:
 * the poller decides in code what to look up; the game only ever reports.
 */
#define ORACLE_QUERY_FILE    "oracle.query"
#define ORACLE_QRESULT_FILE  "oracle.queryresult"
#define ORACLE_LIVE_MAX      8


/*
 * What the Oracle may reveal is what the one asking could see for themself,
 * and never more.  Every lookup below is answered from the asker's point of
 * view, by these rules:
 *
 *   - Staff are never there.  An immortal -- by trust, wizinvis or not,
 *     switched into a mobile or not -- is not reported online, not described,
 *     and nothing they hold is found.
 *   - Stealth and shadowmeld always hide.  can_see() rolls dice for both,
 *     which is right for a glance across a room and wrong here: a question
 *     can be asked again until the roll comes up, so the Oracle would be a
 *     way to find anyone eventually.  She follows online_can_list(), which
 *     never lists them, and is stricter than it.
 *   - Invisibility and hiding hide unless the asker carries the detection
 *     that would show them.
 *   - Rooms barred to mortals are not hers to describe.
 *   - A player's pack and bags are their own: of a player she sees only what
 *     they have on, as LOOK would.
 *
 * The asker is the poller's to name and the game's to find.  When they cannot
 * be found -- a check run from the host, or a player who left mid-question --
 * the rules are applied as for an asker with no detections at all.
 */
static CHAR_DATA *oracle_find_asker( const char *name )
{
    DESCRIPTOR_DATA *d;

    if ( name == NULL || name[0] == '\0' )
        return NULL;

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *vch = d->original != NULL ? d->original : d->character;

        if ( d->connected == CON_PLAYING && vch != NULL && vch->name != NULL
          && !str_cmp( vch->name, name ) )
            return vch;
    }
    return NULL;
}


static bool oracle_is_staff( CHAR_DATA *vch )
{
    if ( vch == NULL )
        return FALSE;
    if ( IS_NPC(vch) && vch->desc != NULL && vch->desc->original != NULL )
        vch = vch->desc->original;   /* an immortal wearing a mobile */
    return !IS_NPC(vch) && get_trust( vch ) >= LEVEL_IMMORTAL;
}


static bool oracle_room_public( CHAR_DATA *asker, ROOM_INDEX_DATA *room )
{
    if ( room == NULL )
        return FALSE;
    if ( IS_SET(room->room_flags, ROOM_IMP_ONLY)
      || IS_SET(room->room_flags, ROOM_GODS_ONLY) )
        return FALSE;
    return asker == NULL || can_see_room( asker, room );
}


static bool oracle_can_see_char( CHAR_DATA *asker, CHAR_DATA *vch )
{
    bool detect_invis  = asker != NULL && IS_AFFECTED(asker, AFF_DETECT_INVIS);
    bool detect_hidden = asker != NULL && IS_AFFECTED(asker, AFF_DETECT_HIDDEN);

    if ( vch == NULL )
        return FALSE;
    if ( vch == asker )
        return TRUE;
    if ( oracle_is_staff( vch ) )
        return FALSE;
    if ( !IS_NPC(vch)
      && ( IS_SET(vch->act, PLR_WIZINVIS) || IS_SET(vch->act, PLR_CLOAKED) ) )
        return FALSE;
    if ( IS_AFFECTED2(vch, AFF2_STEALTH) || IS_AFFECTED2(vch, AFF2_SHADOWMELD) )
        return FALSE;
    if ( ( IS_AFFECTED(vch, AFF_INVISIBLE) || IS_AFFECTED2(vch, AFF2_GHOST) )
      && !detect_invis )
        return FALSE;
    if ( IS_AFFECTED(vch, AFF_HIDE) && !detect_hidden )
        return FALSE;
    return oracle_room_public( asker, vch->in_room );
}


static bool oracle_can_see_item( CHAR_DATA *asker, OBJ_DATA *obj )
{
    if ( IS_SET(obj->extra_flags, ITEM_VIS_DEATH) )
        return FALSE;
    if ( IS_SET(obj->extra_flags, ITEM_INVIS)
      && ( asker == NULL || !IS_AFFECTED(asker, AFF_DETECT_INVIS) ) )
        return FALSE;
    return TRUE;
}


/*
 * May the asker learn where this object is?  Its outermost holder decides,
 * through any nesting of containers, so a bag hides nothing.
 */
static bool oracle_can_locate_obj( CHAR_DATA *asker, OBJ_DATA *obj )
{
    OBJ_DATA *outer = obj;
    int depth = 0;

    if ( !oracle_can_see_item( asker, obj ) )
        return FALSE;

    while ( outer->in_obj != NULL && depth++ < 32 )
        outer = outer->in_obj;

    if ( outer->carried_by != NULL )
    {
        CHAR_DATA *holder = outer->carried_by;

        if ( !oracle_can_see_char( asker, holder ) )
            return FALSE;
        /* Of a player, only what they have on -- never their pack. */
        if ( !IS_NPC(holder) && holder != asker
          && ( obj != outer || obj->wear_loc == WEAR_NONE ) )
            return FALSE;
        return TRUE;
    }

    return oracle_room_public( asker, outer->in_room );
}


/* How to name a holder: a mobile's name field is its keyword list. */
static const char *oracle_holder_name( CHAR_DATA *vch )
{
    if ( IS_NPC(vch) && vch->short_descr != NULL )
        return vch->short_descr;
    return vch->name != NULL ? vch->name : "someone";
}


/* What someone has on, as the asker would see it in LOOK. */
static int oracle_worn_list( CHAR_DATA *asker, CHAR_DATA *target,
                             char *items, size_t size )
{
    OBJ_DATA *obj;
    int found = 0;

    items[0] = '\0';
    for ( obj = target->carrying; obj != NULL; obj = obj->next_content )
    {
        char line[MAX_INPUT_LENGTH];

        if ( obj->wear_loc == WEAR_NONE || !oracle_can_see_item( asker, obj ) )
            continue;
        snprintf( line, sizeof(line), "%s%s", found ? "; " : "",
                  obj->short_descr != NULL ? obj->short_descr : "something" );
        if ( strlen(items) + strlen(line) + 1 < size )
            toc_strlcat( items, line, size );
        found++;
    }
    return found;
}


static void oracle_lookup_obj( CHAR_DATA *asker, const char *keyword,
                               char *out, size_t size )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;
    int found = 0;

    out[0] = '\0';
    if ( keyword == NULL || keyword[0] == '\0' )
        return;

    FOR_EACH_OBJECT( iter, obj )
    {
        char where[MAX_INPUT_LENGTH];
        char line[MAX_STRING_LENGTH];

        if ( obj->pIndexData == NULL || obj->name == NULL )
            continue;
        if ( !is_name( keyword, obj->name ) )
            continue;
        if ( !oracle_can_locate_obj( asker, obj ) )
            continue;

        if ( obj->carried_by != NULL )
        {
            CHAR_DATA *holder = obj->carried_by;

            /* A mobile's room is part of the answer -- it is where to go.
               A player's is not hers to give away. */
            if ( IS_NPC(holder) && holder->in_room != NULL )
                snprintf( where, sizeof(where), "%s %s in %s (%d)",
                          obj->wear_loc != WEAR_NONE ? "worn by" : "carried by",
                          oracle_holder_name( holder ),
                          holder->in_room->name != NULL ? holder->in_room->name : "?",
                          holder->in_room->vnum );
            else
                snprintf( where, sizeof(where), "%s %s",
                          obj->wear_loc != WEAR_NONE ? "worn by" : "carried by",
                          oracle_holder_name( holder ) );
        }
        else if ( obj->in_room != NULL )
            snprintf( where, sizeof(where), "in %s (%d)",
                      obj->in_room->name != NULL ? obj->in_room->name : "?",
                      obj->in_room->vnum );
        else if ( obj->in_obj != NULL )
            snprintf( where, sizeof(where), "inside %s",
                      obj->in_obj->short_descr != NULL ? obj->in_obj->short_descr
                                                       : "a container" );
        else
            continue;

        snprintf( line, sizeof(line), "%s%s %s", found ? "; " : "",
                  obj->short_descr != NULL ? obj->short_descr : "it", where );
        if ( strlen(out) + strlen(line) + 1 < size )
            toc_strlcat( out, line, size );
        if ( ++found >= ORACLE_LIVE_MAX )
            break;
    }

    if ( found == 0 )
        snprintf( out, size, "No '%s' is anywhere in the world right now.", keyword );
}


static void oracle_lookup_mob( CHAR_DATA *asker, const char *keyword,
                               char *out, size_t size )
{
    LIST_ITERATOR iter;
    CHAR_DATA *mob;
    int found = 0;

    out[0] = '\0';
    if ( keyword == NULL || keyword[0] == '\0' )
        return;

    FOR_EACH_CHARACTER( iter, mob )
    {
        char line[MAX_INPUT_LENGTH];

        if ( !IS_NPC(mob) || mob->in_room == NULL
          || mob->pIndexData == NULL || mob->name == NULL )
            continue;
        if ( !is_name( keyword, mob->name ) || !oracle_can_see_char( asker, mob ) )
            continue;

        snprintf( line, sizeof(line), "%s%s in %s (%d)", found ? "; " : "",
                  mob->short_descr != NULL ? mob->short_descr : mob->name,
                  mob->in_room->name != NULL ? mob->in_room->name : "?",
                  mob->in_room->vnum );
        if ( strlen(out) + strlen(line) + 1 < size )
            toc_strlcat( out, line, size );
        if ( ++found >= ORACLE_LIVE_MAX )
            break;
    }

    if ( found == 0 )
        snprintf( out, size, "No '%s' is roaming the world right now.", keyword );
}


static void oracle_lookup_eq( CHAR_DATA *asker, const char *name,
                              char *out, size_t size )
{
    LIST_ITERATOR iter;
    CHAR_DATA *vch;
    CHAR_DATA *target = NULL;
    char items[MAX_STRING_LENGTH / 2];
    int found;

    out[0] = '\0';
    if ( name == NULL || name[0] == '\0' )
        return;

    FOR_EACH_CHARACTER( iter, vch )
    {
        if ( !IS_NPC(vch) && vch->name != NULL && !str_cmp( vch->name, name ) )
        {
            target = vch;
            break;
        }
    }

    /* Hidden and absent read the same, so the reply gives nothing away. */
    if ( target == NULL || !oracle_can_see_char( asker, target ) )
    {
        snprintf( out, size, "%s is not online right now.", name );
        return;
    }

    found = oracle_worn_list( asker, target, items, sizeof(items) );
    snprintf( out, size, "%s is wearing right now: %s.", target->name,
              found ? items : "nothing of note" );
}


/* What a mobile is wearing: the first one in the world answering to the
   keywords that the asker could see, and where it stands. */
static void oracle_lookup_mobeq( CHAR_DATA *asker, const char *keyword,
                                 char *out, size_t size )
{
    LIST_ITERATOR iter;
    CHAR_DATA *mob;
    CHAR_DATA *target = NULL;
    char items[MAX_STRING_LENGTH / 2];
    int found;

    out[0] = '\0';
    if ( keyword == NULL || keyword[0] == '\0' )
        return;

    FOR_EACH_CHARACTER( iter, mob )
    {
        if ( IS_NPC(mob) && mob->in_room != NULL && mob->pIndexData != NULL
          && mob->name != NULL && is_name( keyword, mob->name )
          && oracle_can_see_char( asker, mob ) )
        {
            target = mob;
            break;
        }
    }

    if ( target == NULL )
        return;     /* the plain mob lookup already says it is not about */

    found = oracle_worn_list( asker, target, items, sizeof(items) );
    snprintf( out, size, "%s, in %s (%d), is wearing right now: %s.",
              oracle_holder_name( target ),
              target->in_room->name != NULL ? target->in_room->name : "?",
              target->in_room->vnum, found ? items : "nothing at all" );
}


/* Who is playing, as far as the asker could tell: no staff, nobody stealthed,
   melded, invisible or hidden from them. */
static void oracle_lookup_who( CHAR_DATA *asker, char *out, size_t size )
{
    DESCRIPTOR_DATA *d;
    char names[MAX_STRING_LENGTH];
    int count = 0;

    names[0] = '\0';
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *vch;

        if ( d->connected != CON_PLAYING )
            continue;
        vch = d->original != NULL ? d->original : d->character;
        if ( vch == NULL || vch->name == NULL )
            continue;
        if ( vch != asker
          && ( oracle_is_staff( vch ) || !oracle_can_see_char( asker, d->character ) ) )
            continue;
        if ( strlen(names) + strlen(vch->name) + 3 < sizeof(names) )
        {
            if ( count > 0 )
                toc_strlcat( names, ", ", sizeof(names) );
            toc_strlcat( names, vch->name, sizeof(names) );
        }
        count++;
    }

    snprintf( out, size, "Online now (%d): %s.", count,
              count > 0 ? names : "nobody" );
}


/* Drain the poller's live-lookup requests on the game pulse and answer them,
   read-only. */
void oracle_process_queries( void )
{
    FILE *fp;
    FILE *pending;
    FILE *out;
    char buf[MAX_STRING_LENGTH];
    struct stat fst;
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    struct flock lock;
#endif

    if ( stat( ORACLE_QUERY_FILE, &fst ) == -1 || fst.st_size == 0 )
        return;

    fp = fopen( ORACLE_QUERY_FILE, "r+" );
    if ( fp == NULL )
        return;

#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    memset( &lock, 0, sizeof(lock) );
    lock.l_type = F_WRLCK;
    lock.l_whence = SEEK_SET;
    if ( fcntl( fileno(fp), F_SETLK, &lock ) == -1 )
    {
        fclose( fp );
        return;
    }
#endif

    pending = tmpfile();
    if ( pending == NULL )
    {
        fclose( fp );
        return;
    }

    while ( fgets( buf, sizeof(buf), fp ) != NULL )
    {
        if ( fputs( buf, pending ) == EOF )
            break;
    }
    if ( ferror(fp) || ferror(pending) || fflush(pending) != 0 )
    {
        fclose( pending );
        fclose( fp );
        return;
    }

#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    if ( ftruncate( fileno(fp), 0 ) != 0 )
    {
        fclose( pending );
        fclose( fp );
        return;
    }
    fclose( fp );
#else
    {
        FILE *clear = freopen( ORACLE_QUERY_FILE, "w", fp );
        if ( clear == NULL )
        {
            fclose( pending );
            return;
        }
        fclose( clear );
    }
#endif

    rewind( pending );

    out = fopen( ORACLE_QRESULT_FILE, "a" );
#if defined(unix) || defined(__unix__) || defined(__APPLE__)
    if ( out != NULL )
    {
        memset( &lock, 0, sizeof(lock) );
        lock.l_type = F_WRLCK;
        lock.l_whence = SEEK_SET;
        if ( fcntl( fileno(out), F_SETLKW, &lock ) == -1 )
        {
            fclose( out );
            out = NULL;
        }
    }
#endif

    while ( fgets( buf, sizeof(buf), pending ) != NULL )
    {
        char ans[MAX_STRING_LENGTH];
        char *reqid;
        char *kind;
        char *asker_name;
        char *keyword;
        CHAR_DATA *asker;
        size_t len = strlen( buf );

        while ( len > 0 && ( buf[len - 1] == '\n' || buf[len - 1] == '\r' ) )
            buf[--len] = '\0';
        if ( buf[0] == '\0' )
            continue;

        /* "<id>\t<kind>\t<asker>\t<keyword>": every lookup is answered from
           the asker's point of view. */
        reqid      = strtok( buf, "\t" );
        kind       = strtok( NULL, "\t" );
        asker_name = strtok( NULL, "\t" );
        keyword    = strtok( NULL, "" );
        if ( reqid == NULL || kind == NULL || asker_name == NULL || keyword == NULL )
            continue;
        asker = oracle_find_asker( asker_name );

        ans[0] = '\0';
        if ( !str_cmp( kind, "obj" ) )
            oracle_lookup_obj( asker, keyword, ans, sizeof(ans) );
        else if ( !str_cmp( kind, "mob" ) )
            oracle_lookup_mob( asker, keyword, ans, sizeof(ans) );
        else if ( !str_cmp( kind, "eq" ) )
            oracle_lookup_eq( asker, keyword, ans, sizeof(ans) );
        else if ( !str_cmp( kind, "mobeq" ) )
            oracle_lookup_mobeq( asker, keyword, ans, sizeof(ans) );
        else if ( !str_cmp( kind, "who" ) )
            oracle_lookup_who( asker, ans, sizeof(ans) );
        else
            continue;

        if ( out != NULL && ans[0] != '\0' )
            fprintf( out, "%s\t%s\n", reqid, ans );
    }

    if ( out != NULL )
        fclose( out );
    fclose( pending );
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


/* Deliver one answer to the player who asked, if they are still here.
   Returns TRUE if the delivery ended the audience -- the mob is then gone and
   must not be touched again. */
static bool oracle_deliver( CHAR_DATA *mob, const char *player,
                            const char *answer )
{
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *vch;

    for ( vch = mob->in_room->people; vch != NULL; vch = vch->next_in_room )
    {
        if ( !IS_NPC(vch) && vch->name != NULL && !str_cmp( vch->name, player ) )
            break;
    }

    /* An off-topic question: she refuses rather than answering, and keeps
       count.  Too many in one sitting and she leaves, holding the offender
       out for a while. */
    if ( !str_cmp( answer, ORACLE_OFFTOPIC ) )
    {
        oracle_strikes++;
        oracle_journal( "OFFTOPIC", player,
                        mob->in_room != NULL ? mob->in_room->vnum : 0, "" );
        if ( vch != NULL )
            act( "$n fixes $N with a flat stare.  'I do not answer such things.'",
                mob, NULL, vch, TO_ROOM );

        if ( oracle_strikes >= ORACLE_OFFTOPIC_MAX )
        {
            if ( vch != NULL )
                act( "$n says 'You waste my sight.  Trouble me again another day.'",
                    mob, NULL, vch, TO_ROOM );
            toc_strlcpy( oracle_cooldown_name, oracle_summoner,
                         sizeof(oracle_cooldown_name) );
            oracle_cooldown_until =
                ( current_time > 0 ? current_time : time(NULL) )
                + ORACLE_COOLDOWN_SECONDS;
            oracle_dismiss( TRUE );
            return TRUE;
        }
        return FALSE;
    }

    /* A real answer: she is being used properly, so forgive earlier strikes. */
    oracle_strikes = 0;

    oracle_journal( "A", player,
                    mob->in_room != NULL ? mob->in_room->vnum : 0, answer );

    if ( vch == NULL )
        return FALSE;   /* they walked off; the answer is dropped */

    toc_strlcpy( oracle_last_answer, answer, sizeof(oracle_last_answer) );

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
    return FALSE;
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
                        if ( oracle_deliver( mob, buf, answer ) )
                        {
                            /* She left; the rest of the batch has nobody
                               to answer and the mob is gone. */
                            fclose( pending );
                            return TRUE;
                        }
                    }
                }
                fclose( pending );
            }
        }
    }

    if ( oracle_mob != NULL )
    {
        long now = (long) ( current_time > 0 ? current_time : time(NULL) );

        /* The audience has a hard limit; warn a minute before it ends. */
        if ( oracle_started > 0 && now - (long) oracle_started >= ORACLE_SESSION_SECONDS )
        {
            act( "$n says 'The vision fades.  Our time is done.'",
                mob, NULL, NULL, TO_ROOM );
            oracle_dismiss( TRUE );
            return TRUE;
        }
        if ( oracle_started > 0 && !oracle_warned
          && now - (long) oracle_started >= ORACLE_SESSION_SECONDS - 60 )
        {
            oracle_warned = TRUE;
            act( "$n says 'My sight grows dim.  Ask your last.'",
                mob, NULL, NULL, TO_ROOM );
        }

        /* Or sooner, if her supplicant has fallen silent. */
        if ( oracle_last > 0 && now - (long) oracle_last > ORACLE_IDLE_SECONDS )
        {
            act( "$n says 'You have fallen quiet.  I will return to my rest.'",
                mob, NULL, NULL, TO_ROOM );
            oracle_dismiss( TRUE );
            return TRUE;
        }
    }

    return FALSE;
}


/* Is any mobile hunting this character right now? */
static bool oracle_is_hunted( CHAR_DATA *ch )
{
    LIST_ITERATOR iter;
    CHAR_DATA *vch;

    FOR_EACH_CHARACTER( iter, vch )
    {
        if ( IS_NPC(vch) && vch->hunting == ch )
            return TRUE;
    }
    return FALSE;
}


/*
 * PRAY -- the supplicant is drawn out of the world into the Oracle's
 * sanctum, the way rope trick or haven takes a caster aside.  The bead
 * curtain (down) leads back to the room they prayed in; so does saying DONE,
 * and so does the end of the audience.  One supplicant at a time: the
 * sanctum is solitary, no-recall and safe.  Never an escape: not in combat,
 * not while the blood is still up after a fight or a flight, and not while
 * something is hunting you.
 */
void do_pray( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    MOB_INDEX_DATA *idx;
    CHAR_DATA *mob;
    ROOM_INDEX_DATA *sanctum;
    ROOM_INDEX_DATA *origin;

    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) )
        return;

    if ( ch->in_room == NULL )
    {
        send_to_char( "You are nowhere the Oracle could reach you.\n\r", ch );
        return;
    }

    if ( ch->in_room->vnum == ROOM_VNUM_ORACLE )
    {
        send_to_char( "You are already in her sanctum.\n\r", ch );
        return;
    }

    if ( ch->fighting != NULL || ch->position == POS_FIGHTING )
    {
        send_to_char( "You cannot pray in the heat of battle.\n\r", ch );
        return;
    }

    /* Battleticks outlast the fight -- and cover the moments after a flee. */
    if ( ch->battleticks > 0 )
    {
        send_to_char( "Your blood is still up.  Let the fighting settle before you pray.\n\r", ch );
        return;
    }

    if ( oracle_is_hunted( ch ) )
    {
        send_to_char( "Something is hunting you.  The Oracle will not hide you from it.\n\r", ch );
        return;
    }

    /* Never a way out of a death trap, a cell or a duel. */
    if ( IS_SET( ch->in_room->room_flags, ROOM_DT )
      || IS_SET( ch->in_room->room_flags, ROOM_JAIL )
      || IS_SET( ch->in_room->room_flags, ROOM_ARENA )
      || ( ch->in_room->affected != NULL
        && ch->in_room->affected->type == EXTRA_DIMENSIONAL ) )
    {
        send_to_char( "Your prayer cannot reach her from here.\n\r", ch );
        return;
    }

    /* Barred by a god (ORACLE BAN). */
    if ( ch->pcdata != NULL && ch->pcdata->no_oracle )
    {
        send_to_char( "The gods have barred you from the Oracle's sight.\n\r", ch );
        return;
    }

    /* Held out after wasting her sight too often. */
    {
        time_t now = current_time > 0 ? current_time : time(NULL);

        if ( oracle_cooldown_until > now
          && !str_cmp( oracle_cooldown_name, ch->name ) )
        {
            send_to_char(
                "The Oracle will not hear you just now.  Reflect, and return later.\n\r",
                ch );
            return;
        }
    }

    if ( oracle_mob != NULL )
    {
        send_to_char( "The Oracle is attending to someone else right now.  "
                      "Pray again in a little while.\n\r", ch );
        return;
    }

    if ( ( idx = get_mob_index( MOB_VNUM_ORACLE ) ) == NULL
      || ( sanctum = get_room_index( ROOM_VNUM_ORACLE ) ) == NULL )
    {
        send_to_char( "You pray, but no answer comes.\n\r", ch );
        return;
    }

    /* Anyone left in the sanctum with no audience (a reboot, a quit) is shown
       out before the next supplicant arrives. */
    {
        CHAR_DATA *vch;
        CHAR_DATA *vch_next;
        ROOM_INDEX_DATA *temple = get_room_index( ROOM_VNUM_TEMPLE );

        for ( vch = sanctum->people; vch != NULL; vch = vch_next )
        {
            vch_next = vch->next_in_room;
            if ( IS_NPC(vch) || IS_IMMORTAL(vch) || temple == NULL )
                continue;
            send_to_char( "The sanctum dims, and you find yourself elsewhere.\n\r", vch );
            char_from_room( vch );
            char_to_room( vch, temple );
            do_look( vch, "auto" );
        }
    }

    origin = ch->in_room;

    act( "You bow your head in prayer.  The world falls away in a curl of "
        "incense, and you open your eyes somewhere else.", ch, NULL, NULL, TO_CHAR );
    act( "$n bows $s head in prayer and is gone in a curl of incense smoke.",
        ch, NULL, NULL, TO_ROOM );

    /* Move the supplicant before the globals are set, so the departure hook
       in char_from_room has nothing to act on. */
    char_from_room( ch );
    char_to_room( ch, sanctum );
    oracle_set_way_out( origin );

    mob = create_mobile( idx );
    mob->spec_fun = spec_lookup( "spec_oracle" );
    char_to_room( mob, sanctum );

    oracle_mob = mob;
    toc_strlcpy( oracle_summoner, ch->name, sizeof(oracle_summoner) );
    oracle_room_vnum = sanctum->vnum;
    oracle_origin_vnum = origin->vnum;
    oracle_last = current_time > 0 ? current_time : time(NULL);
    oracle_started = oracle_last;
    oracle_warned = FALSE;
    oracle_strikes = 0;
    oracle_last_question[0] = '\0';
    oracle_last_answer[0] = '\0';

    /* A new audience: the poller forgets the last one's conversation. */
    oracle_spool_control( ch, "SITTING" );

    do_look( ch, "auto" );
    act( "$n murmurs, 'Say what you would know, and I will answer.  Say WRONG "
        "if I err, and DONE, or part the beads, when you are finished.'",
        mob, NULL, NULL, TO_ROOM );

    /* An easter egg: she sees the mind for what it is.  Said only to the
       supplicant, so it gives nothing away to the room. */
    if ( ch->pcdata != NULL )
    {
        if ( ch->pcdata->psionic > 0 )
            act( "$n's clouded eyes linger on you a moment too long.  'Your mind is louder than most.'",
                mob, NULL, ch, TO_VICT );
        else if ( ch->pcdata->psionic_grant_pending
               || ( ch->pcdata->num_remorts >= 2 && ch->pcdata->psionic <= 0 ) )
            act( "$n pauses, as though something about you puzzles her.  'There is something unusual about your mind, seeker.'",
                mob, NULL, ch, TO_VICT );
    }

    snprintf( buf, sizeof(buf), "Oracle: %s prayed from room %d (%s) and entered her sanctum.",
              ch->name, origin->vnum,
              origin->name != NULL ? origin->name : "?" );
    log_string( buf );
    wizinfo( buf, LEVEL_IMMORTAL );
    oracle_journal( "SUMMON", ch->name, origin->vnum, "" );
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

    argument = one_argument( argument, arg );

    if ( !str_prefix( arg, "ban" ) || !str_prefix( arg, "allow" ) )
    {
        char name[MAX_INPUT_LENGTH];
        CHAR_DATA *victim;
        bool banning = ( LOWER(arg[0]) == 'b' );

        one_argument( argument, name );
        if ( name[0] == '\0' )
        {
            send_to_char( "Syntax: oracle ban <player>, or oracle allow <player>.\n\r", ch );
            return;
        }
        if ( ( victim = get_char_world( ch, name ) ) == NULL )
        {
            send_to_char( "They are not in this world.\n\r", ch );
            return;
        }
        if ( IS_NPC(victim) || victim->pcdata == NULL )
        {
            send_to_char( "Only players can be barred.\n\r", ch );
            return;
        }

        victim->pcdata->no_oracle = banning ? 1 : 0;
        save_char_obj( victim );

        snprintf( buf, sizeof(buf), "Oracle: %s %s %s.",
                  ch->name, banning ? "barred" : "restored", victim->name );
        log_string( buf );
        wizinfo( buf, LEVEL_IMMORTAL );

        snprintf( buf, sizeof(buf), "%s %s the Oracle.\n\r", victim->name,
                  banning ? "can no longer pray to" : "may pray to" );
        send_to_char( buf, ch );

        /* If the one being barred has her right now, send her home. */
        if ( banning && oracle_mob != NULL
          && !str_cmp( oracle_summoner, victim->name ) )
            oracle_dismiss( TRUE );
        return;
    }

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
        oracle_dismiss( TRUE );
        send_to_char( "You send the Oracle home.\n\r", ch );
        return;
    }

    if ( oracle_mob != NULL )
        snprintf( buf, sizeof(buf),
                  "The Oracle attends %s in her sanctum (prayed from room %d).\n\r",
                  oracle_summoner, oracle_origin_vnum );
    else
        snprintf( buf, sizeof(buf), "The Oracle is not currently summoned.\n\r" );
    send_to_char( buf, ch );

    oracle_show_transcript( ch );
}
