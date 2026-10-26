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

static void fix_mark( CHAR_DATA *ch, const char *id )
{
    char buf[MAX_STRING_LENGTH];

    toc_strlcpy( buf, ch->pcdata->fixes_done != NULL ? ch->pcdata->fixes_done : "",
                 sizeof(buf) );
    if ( buf[0] != '\0' )
        toc_strlcat( buf, " ", sizeof(buf) );
    toc_strlcat( buf, id, sizeof(buf) );
    free_string( ch->pcdata->fixes_done );
    ch->pcdata->fixes_done = str_dup( buf );
}

/* The same record, for other once-per-character work (restores.c). */
bool player_fix_has( CHAR_DATA *ch, const char *id )
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL
        && fix_done( ch->pcdata->fixes_done, id );
}

void player_fix_record( CHAR_DATA *ch, const char *id )
{
    if ( ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL )
        fix_mark( ch, id );
}

/* A mark taken back: a transfer that did not reach the disk is undone in
   memory too, and must not leave a mark behind to be saved later. */
void player_fix_forget( CHAR_DATA *ch, const char *id )
{
    char buf[MAX_STRING_LENGTH] = "";
    char word[MAX_INPUT_LENGTH];
    const char *p;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL || ch->pcdata->fixes_done == NULL )
        return;
    for ( p = ch->pcdata->fixes_done; *p != '\0'; )
    {
        size_t n = 0;

        while ( *p == ' ' )
            p++;
        while ( *p != '\0' && *p != ' ' && n < sizeof(word) - 1 )
            word[n++] = *p++;
        word[n] = '\0';
        while ( *p != '\0' && *p != ' ' )
            p++;
        if ( word[0] == '\0' || !strcmp( word, id ) )
            continue;
        if ( buf[0] != '\0' )
            toc_strlcat( buf, " ", sizeof(buf) );
        toc_strlcat( buf, word, sizeof(buf) );
    }
    free_string( ch->pcdata->fixes_done );
    ch->pcdata->fixes_done = str_dup( buf );
}

/* Whether a player's FILE holds a mark: its Fixes line, as written. For
   settling at boot, before anybody is loaded. -1 if the file cannot be
   read, so a caller can tell "not there" from "cannot say". */
int player_file_fix_has( const char *name, const char *id )
{
    char path[MAX_INPUT_LENGTH];
    char line[MAX_STRING_LENGTH];
    FILE *fp;
    int found = 0;

    snprintf( path, sizeof(path), "%s%s", PLAYER_DIR, capitalize( name ) );
    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return -1;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        if ( !strcmp( line, "End\n" ) || !strcmp( line, "End\r\n" ) )
            break;
        if ( !strncmp( line, "Fixes ", 6 ) )
        {
            line[strcspn( line, "~\r\n" )] = '\0';
            found = fix_done( line + 6, id ) ? 1 : 0;
            break;
        }
    }
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
