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
 *    two) and a line for the log.
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
} PLAYER_FIX;

static bool fix_stray_mage_groups( CHAR_DATA *ch )
{
    return rescind_stray_mage_groups( ch );
}

static const PLAYER_FIX player_fixes[] =
{
    /* Creation gave every new non-mage the mage's starting groups,
       2026-09-19 to 2026-10-21 (skills.c). */
    { "20261021-mage-groups", "mage spells from the creation bug",
      fix_stray_mage_groups },
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
    for ( i = 0; i < PLAYER_FIX_COUNT; i++ )
    {
        if ( fix_done( ch->pcdata->fixes_done, player_fixes[i].id ) )
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
    if ( arg[0] != '\0' && ( victim = get_char_world( ch, arg ) ) == NULL )
    {
        send_to_char( "They aren't here.\n\r", ch );
        return;
    }
    if ( victim != NULL && ( IS_NPC(victim) || victim->pcdata == NULL ) )
    {
        send_to_char( "Mobiles have no fixes.\n\r", ch );
        return;
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
