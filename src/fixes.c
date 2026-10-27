/*
 * Fixing characters at their next login (owner, 2026-10-21: a standard
 * way to correct players after a bug fix).
 *
 * Player files live on the game host, and the state sync only ever
 * copies them from the host to git, never back, so a character cannot be
 * corrected by editing a file in the repository: the next sync overwrites
 * the edit and the game never reads it. A correction is code instead --
 * a row in player_fixes below -- and it runs when the character next
 * logs in, where it can tell them what changed.
 *
 * Each fix has an id that is never changed and never reused. A character
 * keeps the ids of the fixes already applied to them, saved as
 * `Fixes <id> <id> ...~` under case 'F', so each fix runs once per
 * character. A character made after a fix was written was made correct,
 * so a brand new character is marked as having every fix without running
 * any. An old file with no Fixes line has had none, and gets each one at
 * its next login.
 *
 * Writing a fix:
 *  - a static function `bool fix_<what>( CHAR_DATA *ch )` that decides
 *    for itself whether the character needs it (staff, class, level...),
 *    changes what it must, tells the player in plain words, and returns
 *    true when it changed anything. It must be safe to run on anyone.
 *  - a row at the end of player_fixes with a new id (date and a word or
 *    two), a line for the log, and whether staff get it too: a fix
 *    that is not for staff skips them and leaves them unmarked, so it
 *    reaches a builder whose trust is later taken away.
 *  - a test that plants the bug's leftovers in a test character's file,
 *    logs in and checks the correction, and that a second login does
 *    nothing.
 * The runner logs and WIZINFOs every fix that changed something, and
 * saves the character once afterwards.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"

typedef struct player_fix
{
    const char *id;                     /* never changed, never reused */
    const char *what;                   /* for the log */
    bool      (*apply)( CHAR_DATA *ch );
    bool        staff_too;              /* false: staff skip it, unmarked */
} PLAYER_FIX;

/* Whether this login's mage-groups fix found the creation bug's groups:
   the weapon fix, which runs next, trusts that over its own guess. Reset
   by player_fixes_login for every character. */
static bool fix_found_mage_groups;

static bool fix_stray_mage_groups( CHAR_DATA *ch )
{
    fix_found_mage_groups = rescind_stray_mage_groups( ch );
    return fix_found_mage_groups;
}

/*
 * The same creation bug ran the class's weapon floors for class 0 too,
 * so every new non-mage started with the mage's -- dagger at 80, whip at
 * 20 -- wherever those beat their own, and a weapon still at exactly that
 * value goes back to the class's own; anything trained off it stays.
 *
 * Only for a character the bug made. Nothing on file dates a character,
 * and the small mage values (spear 8, axe 10, flail 7) are easy to reach
 * by use, so one weapon on one of them proves nothing: an older thief
 * whose spear had climbed to 8 would have lost three points (found in
 * review, 2026-10-21, before it touched anyone). A victim is a character
 * this same login just took the mage groups from, or one holding two or
 * more weapons at exactly the mage's values -- the bug set them all at
 * once, and use does not land two of them on the mark by chance.
 */
static bool fix_mage_weapon_floors( CHAR_DATA *ch )
{
    static sh_int *const prof_gsn[8] =
    {
        &gsn_sword, &gsn_dagger, &gsn_spear,  &gsn_mace,
        &gsn_axe,   &gsn_flail,  &gsn_whip,   &gsn_polearm
    };
    char list[MAX_STRING_LENGTH];
    char buf[MAX_STRING_LENGTH * 2];
    int i, matches;

    if ( IS_NPC(ch) || ch->pcdata == NULL || ch->class == CLASS_MAGE
    ||   ch->class < 0 || ch->class >= MAX_CLASS )
        return false;
    list[0] = '\0';
    matches = 0;
    for ( i = 0; i < 8; i++ )
    {
        int sn = *prof_gsn[i];
        int mage = class_table[CLASS_MAGE].weapon_prof[i];

        if ( sn > 0 && mage > class_table[ch->class].weapon_prof[i]
        &&   ch->pcdata->learned[sn] == mage )
            matches++;
    }
    if ( matches == 0 || ( matches < 2 && !fix_found_mage_groups ) )
        return false;
    for ( i = 0; i < 8; i++ )
    {
        int sn = *prof_gsn[i];
        int mage = class_table[CLASS_MAGE].weapon_prof[i];
        int own = class_table[ch->class].weapon_prof[i];

        if ( sn <= 0 || mage <= own || ch->pcdata->learned[sn] != mage )
            continue;
        ch->pcdata->learned[sn] = (int16_t) own;
        snprintf( buf, sizeof(buf), "%s%s %d%% to %d%%",
                  list[0] != '\0' ? ", " : "", skill_table[sn].name, mage, own );
        toc_strlcat( list, buf, sizeof(list) );
    }
    if ( list[0] == '\0' )
        return false;
    snprintf( buf, sizeof(buf), "{0BA correction:{00 the same mistake started you "
              "with a mage's weapon skills.  Back to your class's own: %s.\n\r",
              list );
    send_to_char( buf, ch );
    snprintf( buf, sizeof(buf), "Mage weapon floors: %s's %s.", ch->name, list );
    log_string( buf );
    return true;
}

static const PLAYER_FIX player_fixes[] =
{
    /* Creation gave every new non-mage the mage's starting groups,
       2026-09-19 to 2026-10-21 (skills.c). */
    { "20261021-mage-groups", "mage spells from the creation bug",
      fix_stray_mage_groups, false },
    /* The same bug's mage weapon floors (dagger 80, whip 20...). */
    { "20261021-mage-weapons", "mage weapon skills from the creation bug",
      fix_mage_weapon_floors, false },
};

#define PLAYER_FIX_COUNT ( (int)( sizeof(player_fixes) / sizeof(player_fixes[0]) ) )

/* Whether `id` is one of the space-separated words in `done`. */
static bool fix_done( const char *done, const char *id )
{
    char word[MAX_INPUT_LENGTH];
    const char *p = done;

    if ( done == NULL )
        return false;
    while ( *p != '\0' )
    {
        size_t n = 0;

        while ( *p == ' ' )
            p++;
        while ( *p != '\0' && *p != ' ' && n < sizeof(word) - 1 )
            word[n++] = *p++;
        word[n] = '\0';
        while ( *p != '\0' && *p != ' ' )
            p++;
        if ( word[0] != '\0' && !strcmp( word, id ) )
            return true;
    }
    return false;
}

/*
 * The Fixes list holds two kinds of word: the ids of login fixes, which
 * are kept for ever, and restore:<receipt> marks, which say a transfer
 * reached the player's file. A mark matters only while its receipt is
 * open: once the ledger says committed, the ledger is the record, and the
 * mark is dropped the next time the list is written. Nothing else is
 * ever dropped -- not a migration marker, not a mark whose receipt is
 * pending or unknown to the ledger (a git restore from before it).
 *
 * The list was built in a 4096-byte buffer, so a long one lost its tail
 * -- the newest mark and every word after the cut -- without a word
 * (review, 2026-10-27). It is built to its real size now, and a mark that
 * would take it past PLAYER_FIXES_MAX is refused, so a caller can say no
 * before it moves anything.
 */
static bool fix_word_spent( const char *word )
{
    return !strncmp( word, "restore:", 8 )
        && recovery_request_state( word + 8 ) == RECOVERY_COMMITTED;
}

/* The list with every spent mark taken out, `skip` (if any) left out,
   and `add` (if any) put on the end, freshly allocated; NULL past the
   limit or out of memory. */
static char *fix_list_build( const char *done, const char *skip, const char *add )
{
    size_t cap = ( done != NULL ? strlen( done ) : 0 ) + ( add != NULL ? strlen( add ) : 0 ) + 2;
    char *out = malloc( cap );
    size_t len = 0;
    const char *p = done != NULL ? done : "";

    if ( out == NULL )
        return NULL;
    out[0] = '\0';
    while ( *p != '\0' )
    {
        const char *w;
        size_t n;

        while ( *p == ' ' )
            p++;
        w = p;
        while ( *p != '\0' && *p != ' ' )
            p++;
        n = (size_t)( p - w );
        if ( n == 0 )
            continue;
        {
            char word[MAX_INPUT_LENGTH];

            if ( n < sizeof(word) )
            {
                memcpy( word, w, n );
                word[n] = '\0';
                if ( ( skip != NULL && !strcmp( word, skip ) )
                ||   ( add != NULL && !strcmp( word, add ) )
                ||   fix_word_spent( word ) )
                    continue;
            }
        }
        if ( len > 0 )
            out[len++] = ' ';
        memcpy( out + len, w, n );
        len += n;
        out[len] = '\0';
    }
    if ( add != NULL && add[0] != '\0' )
    {
        if ( len > 0 )
            out[len++] = ' ';
        memcpy( out + len, add, strlen( add ) + 1 );
        len += strlen( add );
    }
    if ( len > PLAYER_FIXES_MAX )
    {
        free( out );
        return NULL;
    }
    return out;
}

static bool fix_list_set( CHAR_DATA *ch, const char *skip, const char *add )
{
    char *built;

    if ( add != NULL && ( add[0] == '\0' || strchr( add, ' ' ) != NULL
                       || strchr( add, '~' ) != NULL || strlen( add ) >= MAX_INPUT_LENGTH ) )
        return false;
    if ( ( built = fix_list_build( ch->pcdata->fixes_done, skip, add ) ) == NULL )
        return false;
    free_string( ch->pcdata->fixes_done );
    ch->pcdata->fixes_done = str_dup( built );
    free( built );
    return true;
}

static bool fix_mark( CHAR_DATA *ch, const char *id )
{
    if ( !fix_list_set( ch, NULL, id ) )
    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf), "Fixes: %s's list could not take %.80s (%d bytes "
                  "already); nothing was changed.", ch->name, id,
                  ch->pcdata->fixes_done != NULL ? (int) strlen( ch->pcdata->fixes_done ) : 0 );
        log_string( buf );
        return false;
    }
    return true;
}

/* The same record, for other once-per-character work (restores.c). */
bool player_fix_has( CHAR_DATA *ch, const char *id )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && fix_done( ch->pcdata->fixes_done, id );
}

/* Whether a mark would fit, spent marks taken out: asked before a
   transfer moves anything, so a full list refuses it cleanly. */
bool player_fix_can_record( CHAR_DATA *ch, const char *id )
{
    char *built;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return false;
    if ( ( built = fix_list_build( ch->pcdata->fixes_done, NULL, id ) ) == NULL )
        return false;
    free( built );
    return true;
}

/* Puts the mark on; false, and nothing changed, if it cannot be (the
   list is full) -- callers that keep a receipt on it must check, and
   player_fix_has() afterwards proves the whole word went in. */
bool player_fix_record( CHAR_DATA *ch, const char *id )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return false;
    return fix_mark( ch, id ) && fix_done( ch->pcdata->fixes_done, id );
}

/* A mark taken back: a transfer that did not reach the disk is undone in
   memory too, and must not leave a mark behind to be saved later; or a
   transfer settled, whose mark the ledger now stands for. */
void player_fix_forget( CHAR_DATA *ch, const char *id )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->fixes_done == NULL )
        return;
    if ( !fix_list_set( ch, id, NULL ) )
        bug( "player_fix_forget: out of memory; the mark stays", 0 );
}

/*
 * One whole line from a file, however long, in a buffer the caller frees
 * (the newline kept); NULL at the end. Readers of player files must not
 * use a fixed fgets buffer for a line that can be long: the Fixes line
 * split at 4096 bytes and its mark read as missing.
 */
char *read_whole_line( FILE *fp )
{
    size_t cap = 256, len = 0;
    char *buf = malloc( cap );

    if ( buf == NULL )
        return NULL;
    while ( fgets( buf + len, (int)( cap - len ), fp ) != NULL )
    {
        len += strlen( buf + len );
        if ( len > 0 && buf[len - 1] == '\n' )
            return buf;
        if ( len + 1 >= cap )
        {
            char *grown = realloc( buf, cap * 2 );

            if ( grown == NULL )
            {
                free( buf );
                return NULL;
            }
            buf = grown;
            cap *= 2;
        }
    }
    if ( len > 0 && !ferror( fp ) )
        return buf;
    free( buf );
    return NULL;
}

/* Whether a player's FILE holds a mark: its Fixes line, as written. For
   settling at boot, before anybody is loaded. -1 if the file cannot be
   read, so a caller can tell "not there" from "cannot say". */
int player_file_fix_has( const char *name, const char *id )
{
    char path[MAX_INPUT_LENGTH];
    char *line;
    FILE *fp;
    int found = 0;
    bool ended = false;

    snprintf( path, sizeof(path), "%s%s", PLAYER_DIR, capitalize( name ) );
    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return -1;
    while ( ( line = read_whole_line( fp ) ) != NULL )
    {
        bool stop = false;

        if ( !strcmp( line, "End\n" ) || !strcmp( line, "End\r\n" ) )
        {
            ended = true;
            stop = true;
        }
        else if ( !strncmp( line, "Fixes ", 6 ) )
        {
            char *tilde = strchr( line + 6, '~' );

            if ( tilde == NULL )
                found = -1;             /* a line cut short: cannot say */
            else
            {
                *tilde = '\0';
                found = fix_done( line + 6, id ) ? 1 : 0;
            }
            ended = true;
            stop = true;
        }
        free( line );
        if ( stop )
            break;
    }
    if ( ferror( fp ) || !ended )
        found = -1;                     /* never reached the line or the End */
    fclose( fp );
    return found;
}

/*
 * From the nanny, once the character is in their room: every fix not yet
 * applied to them runs (or, for a character just made, is only marked).
 */
void player_fixes_login( CHAR_DATA *ch, bool new_character )
{
    char buf[MAX_STRING_LENGTH];
    bool marked = false;
    int i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    fix_found_mage_groups = false;
    for ( i = 0; i < PLAYER_FIX_COUNT; i++ )
    {
        if ( fix_done( ch->pcdata->fixes_done, player_fixes[i].id ) )
            continue;
        /* Staff are left alone and left unmarked, so a builder whose
           trust is taken away gets the fix at the next login. */
        if ( !player_fixes[i].staff_too && !new_character
        &&   IS_TRUSTED( ch, LEVEL_IMMORTAL ) )
            continue;
        /* Never run a fix whose id could not then be kept: it would run
           again at every login. */
        if ( !player_fix_can_record( ch, player_fixes[i].id ) )
        {
            bug( "player_fixes_login: the Fixes list is full; a fix waits", 0 );
            continue;
        }
        if ( !new_character && (*player_fixes[i].apply)( ch ) )
        {
            snprintf( buf, sizeof(buf), "Login fix %s (%s) applied to %s.",
                      player_fixes[i].id, player_fixes[i].what, ch->name );
            log_string( buf );
            wizinfo( buf, LEVEL_IMMORTAL );
        }
        fix_mark( ch, player_fixes[i].id );
        marked = true;
    }
    if ( marked )
        save_char_obj( ch );
}

/* FIXES: staff list the fixes and which ones a character has had. */
void do_fixes( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim = NULL;
    int i;

    one_argument( argument, arg );
    if ( arg[0] != '\0' )
    {
        DESCRIPTOR_DATA *d;

        /* Players only, by whole name, seen or not: get_char_world takes
           a mobile in the room first and misses a wizinvis immortal. */
        for ( d = descriptor_list; d != NULL; d = d->next )
            if ( d->connected == CON_PLAYING && d->character != NULL
            &&   !IS_NPC(d->character) && d->character->pcdata != NULL
            &&   !str_cmp( d->character->name, arg ) )
            {
                victim = d->character;
                break;
            }
        if ( victim == NULL )
        {
            send_to_char( "No player by that name is online.\n\r", ch );
            return;
        }
    }
    send_to_char( "Login fixes, oldest first:\n\r", ch );
    for ( i = 0; i < PLAYER_FIX_COUNT; i++ )
    {
        snprintf( buf, sizeof(buf), "  %-24s %s%s\n\r", player_fixes[i].id,
                  player_fixes[i].what,
                  victim == NULL ? ""
                  : fix_done( victim->pcdata->fixes_done, player_fixes[i].id )
                      ? "  (applied)" : "  (pending)" );
        send_to_char( buf, ch );
    }
}
