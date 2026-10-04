#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include "merc.h"
#include "interp.h"

/* Defined below, beside the grant it reports on; do_check_psi
   above it needs the prototype. */
static void psi_log( CHAR_DATA *ch, const char *fmt, ... );

static const char * const psionic_skill_names[] =
{
    "astral walk",
    "clairvoyance",
    "confuse",
    "ego whip",
    "enervate",
    "mind leech",
    "mindbar",
    "mindblast",
    "nightmare",
    "project",
    "psionic armor",
    "psychic shield",
    "pyrotechnics",
    "shift",
    "telekinesis",
    "torment",
    "transfusion",
    NULL
};

static char *trim_psionic_selection( char *text )
{
    char *end;

    while ( *text != '\0' && isspace((unsigned char)*text) )
        text++;

    end = text + strlen(text);
    while ( end > text && isspace((unsigned char)end[-1]) )
        end--;
    *end = '\0';
    return text;
}

static const char *canonical_psionic_selection( const char *selection )
{
    int i;

    for ( i = 0; psionic_skill_names[i] != NULL; i++ )
        if ( !str_cmp(selection, psionic_skill_names[i]) )
            return psionic_skill_names[i];

    if ( !str_cmp(selection, "astral") )
        return "astral walk";
    if ( !str_cmp(selection, "ego") )
        return "ego whip";
    if ( !str_cmp(selection, "mindleech") )
        return "mind leech";
    if ( !str_cmp(selection, "psionic") )
        return "psionic armor";
    if ( !str_cmp(selection, "psychic") )
        return "psychic shield";
    if ( !str_cmp(selection, "tk") )
        return "telekinesis";

    return NULL;
}

static bool psionic_spec_contains( const char *spec, const char *name )
{
    const char *start;
    const char *end;
    size_t name_length;

    if ( spec == NULL || name == NULL )
        return false;

    name_length = strlen(name);
    for ( start = spec; *start != '\0'; start = *end == ',' ? end + 1 : end )
    {
        end = strchr( start, ',' );
        if ( end == NULL )
            end = start + strlen(start);

        if ( (size_t)(end - start) == name_length
        &&   !strncmp(start, name, name_length) )
            return true;

        if ( *end == '\0' )
            break;
    }

    return false;
}

void init_web( int port )
{
    UNUSED_PARAM(port);
}

void handle_web( void )
{
}

void send_info( char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;

    if ( argument == NULL || argument[0] == '\0' )
        return;

    write_web_admin_event( "info", argument, 0 );

    /*
     * And to the people playing.
     *
     * This only ever wrote the dashboard event, so every announcement
     * the game makes -- remorts, and the level notices the INFO help
     * promises -- reached the web panel and nobody in the game.
     */
    snprintf( buf, sizeof(buf), "{%02X[INFO] %s{00\n\r",
              COL_HIGHLIGHT, argument );

    for ( d = descriptor_list; d != NULL; d = d->next )
    {
        CHAR_DATA *victim = d->original != NULL ? d->original
                                                : d->character;

        if ( d->connected != CON_PLAYING || victim == NULL )
            continue;

        if ( IS_SET( victim->comm, COMM_NOINFO )
          || IS_SET( victim->comm, COMM_QUIET ) )
            continue;

        send_to_char( buf, d->character );
    }
}

void die_follower( CHAR_DATA *ch )
{
    UNUSED_PARAM(ch);
}

void do_check_psi( CHAR_DATA *ch, char *argument )
{
    bool on_level_gain;
    bool owed;
    int roll;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    /*
     * Two ways to be owed psionics: a second remort, or an immortal's
     * GRANTPSI.  Only the first was ever checked here, so a deferred
     * grant set psionic_grant_pending, saved it as PsiGrant, told the
     * player their mind tingles with unfamiliar potential -- and then
     * nothing read the flag back.
     *
     * Being owed is not the same as receiving.  Psionics awaken in the
     * PSI_AWAKEN_MIN..PSI_AWAKEN_MAX band, one roll per level gained
     * inside it, and that is the whole of the chance: four rolls at
     * one in four, so roughly a third of those owed finish the band
     * with nothing.  That is the design, not an accident.
     *
     * The roll used to sit open-coded at the two call sites, which
     * cost three things: it could not be written down, a login ran it
     * again (relog until it lands), and a flag set above the band
     * waited on a roll that was never coming round again.  It lives
     * here now, once, and says what it did.
     */
    on_level_gain = ( argument != NULL && !str_cmp( argument, "levelup" ) );

    owed = ch->pcdata->psionic_grant_pending
        || ( ch->pcdata->num_remorts >= 2 && ch->pcdata->psionic <= 0 );

    if ( !owed )
        return;

    /*
     * A flag set above the band has no future roll to wait for, so it
     * lands at once -- which is what an immortal granting psionics to
     * a level 50 character means by it.  This also carries the
     * characters flagged while nothing was reading the flag at all.
     */
    if ( ch->pcdata->psionic_grant_pending && ch->level > PSI_AWAKEN_MAX )
    {
        psi_log( ch, "flagged grant honoured at level %d, past the %d-%d "
                     "awakening band", ch->level, PSI_AWAKEN_MIN,
                 PSI_AWAKEN_MAX );
        grant_psionics( ch, 100, true );
        return;
    }

    /* A login is not a fresh chance. Only gaining a level is. */
    if ( !on_level_gain )
        return;

    if ( ch->level < PSI_AWAKEN_MIN || ch->level > PSI_AWAKEN_MAX )
        return;

    roll = number_range( PSI_AWAKEN_MIN, PSI_AWAKEN_MAX );

    psi_log( ch, "awakening roll at level %d: rolled %d of %d-%d, hits on "
                 "%d -- %s", ch->level, roll, PSI_AWAKEN_MIN, PSI_AWAKEN_MAX,
             ch->level, roll == ch->level ? "AWAKENED" : "missed" );

    if ( roll != ch->level )
        return;

    grant_psionics( ch, 100, true );
}

bool normalize_psionic_arguments( const char *argument, char *output, size_t length, char *invalid )
{
    char work[MAX_STRING_LENGTH];
    char *cursor;
    char *comma;
    char *selection;
    const char *canonical;

    if ( output == NULL || length == 0 )
        return FALSE;

    toc_strlcpy( work, argument != NULL ? argument : "", sizeof(work) );
    output[0] = '\0';
    if ( invalid != NULL )
        invalid[0] = '\0';

    selection = trim_psionic_selection( work );
    if ( selection[0] == '\0' )
        return TRUE;

    if ( selection != work )
        memmove( work, selection, strlen(selection) + 1 );

    cursor = work;
    while ( cursor != NULL )
    {
        comma = strchr( cursor, ',' );
        if ( comma != NULL )
            *comma = '\0';

        selection = trim_psionic_selection( cursor );
        canonical = canonical_psionic_selection( selection );
        if ( selection[0] == '\0' || canonical == NULL )
        {
            if ( invalid != NULL )
                toc_strlcpy( invalid,
                    selection[0] != '\0' ? selection : "<empty selection>",
                    MAX_INPUT_LENGTH );
            output[0] = '\0';
            return FALSE;
        }

        if ( !psionic_spec_contains(output, canonical) )
        {
            if ( strlen(output) + strlen(canonical) + 2 > length )
            {
                if ( invalid != NULL )
                    toc_strlcpy( invalid, "selection list is too long",
                                 MAX_INPUT_LENGTH );
                output[0] = '\0';
                return FALSE;
            }

            if ( output[0] != '\0' )
                toc_strlcat( output, ",", length );
            toc_strlcat( output, canonical, length );
        }

        cursor = comma != NULL ? comma + 1 : NULL;
    }

    return TRUE;
}

/*
 * Powers already awarded are remembered by name, because a remort wipes the
 * whole skill table and these are meant to accumulate across lives rather
 * than be redealt.  The list survives the wipe; the learned entries do not,
 * and are put back from it on the next grant.
 */
static void psionic_remember( CHAR_DATA *ch, const char *name )
{
    char buf[MAX_STRING_LENGTH];

    if ( name == NULL || name[0] == '\0' )
        return;

    if ( ch->pcdata->psionic_known == NULL )
        ch->pcdata->psionic_known = str_dup( "" );

    if ( psionic_spec_contains( ch->pcdata->psionic_known, name ) )
        return;

    toc_strlcpy( buf, ch->pcdata->psionic_known, sizeof(buf) );
    if ( buf[0] != '\0' )
        toc_strlcat( buf, ",", sizeof(buf) );
    toc_strlcat( buf, name, sizeof(buf) );

    free_string( ch->pcdata->psionic_known );
    ch->pcdata->psionic_known = str_dup( buf );
}

static bool psionic_is_known( CHAR_DATA *ch, sh_int sn )
{
    if ( sn < 0 )
        return false;

    return psionic_spec_contains( ch->pcdata->psionic_known,
                                  skill_table[(int)sn].name );
}

/*
 * One line per decision, to the permanent log and to the watched-player
 * log both.
 *
 * A psionic grant is rare, irreversible, and the hardest thing in the
 * game to argue about after the fact: which power, out of which set,
 * against which roll, and why that one rather than another.  None of
 * that was written down anywhere -- the only record was the player's
 * own skill list afterwards -- so a player asking "did I miss the
 * roll or did it never fire?" could not be answered at all.  Now the
 * arithmetic is in the log, not just the outcome.
 */
static void psi_log( CHAR_DATA *ch, const char *fmt, ... )
{
    /* Half-size so the name and prefix cannot push the joined line
       past the buffer it is written into. */
    char body[MAX_STRING_LENGTH / 2];
    char line[MAX_STRING_LENGTH];
    va_list args;

    if ( ch == NULL )
        return;

    va_start( args, fmt );
    vsnprintf( body, sizeof(body), fmt, args );
    va_end( args );

    /* The room vnum goes in the one line rather than in a second one
       from watch_log: both sinks write to the same file, so calling
       both printed everything twice for exactly the watched character
       whose log is hardest to read already. */
    snprintf( line, sizeof(line), "Psi %s [%d]: %s",
              ch->name != NULL ? ch->name : "(noname)",
              ch->in_room != NULL ? ch->in_room->vnum : 0, body );
    log_string( line );
}


static void psionic_learn( CHAR_DATA *ch, sh_int sn )
{
    if ( sn < 0 )
        return;

    if ( ch->pcdata->learned[(int)sn] < 75 )
        ch->pcdata->learned[(int)sn] = 75;

    psionic_remember( ch, skill_table[(int)sn].name );
}

void grant_psionics( CHAR_DATA *ch, int chance, bool force_grant )
{
    /* 4 thematic psionic skill sets.  A remort awards one power from each
     * set for every remort past the first -- 4 at the second remort, 8 at
     * the third, 12 at the fourth -- and the powers stack, because what
     * was awarded before is remembered by name and put back.  The final
     * remort (num_remorts >= 5) hands over all 17, ahead of any immortal
     * spec: there is no later life to award the rest in.  An immortal
     * grantpsi with a spec otherwise honours the spec and bypasses sets.
     *
     * Set 0  Assault:  ego_whip, torment, nightmare, mindblast
     * Set 1  Astral:   astral_walk, shift, project, telekinesis
     * Set 2  Defense:  mindbar, psionic_armor, psychic_shield, transfusion
     * Set 3  Control:  clairvoyance, confuse, mindleech, enervate, pyrotechnics
     */
    static const sh_int *psi_sets[4][6] = {
        { &gsn_ego_whip,     &gsn_torment,        &gsn_nightmare,     &gsn_mindblast,    NULL,             NULL },
        { &gsn_astral_walk,  &gsn_shift,          &gsn_project,       &gsn_telekinesis,  NULL,             NULL },
        { &gsn_mindbar,      &gsn_psionic_armor,  &gsn_psychic_shield,&gsn_transfusion,  NULL,             NULL },
        { &gsn_clairvoyance, &gsn_confuse,        &gsn_mindleech,     &gsn_enervate,     &gsn_pyrotechnics,NULL }
    };
    static const int psi_set_sizes[4] = { 4, 4, 4, 5 };

    int i, s;
    int selected = 0;
    char normalized_spec[MAX_STRING_LENGTH];
    char invalid[MAX_INPUT_LENGTH];
    bool spec_only;
    bool is_final;

    static const char * const psi_set_names[4] =
        { "Assault", "Astral", "Defense", "Control" };

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    if ( force_grant )
    {
        psi_log( ch, "grant forced, no roll taken (remorts %d, pending %s)",
                 ch->pcdata->num_remorts,
                 ch->pcdata->psionic_grant_pending ? "yes" : "no" );
    }
    else
    {
        /*
         * number_percent() returns 1..100, so a miss has to be
         * `roll > chance`.  It was `>=`, which meant a chance of 100
         * still missed one time in a hundred -- invisible until now
         * only because every caller forces the grant instead.
         */
        int roll = number_percent();
        bool missed = ( roll > chance );

        psi_log( ch, "roll %d vs chance %d, miss when roll > chance -- %s",
                 roll, chance, missed ? "MISSED, nothing granted" : "passed" );

        if ( missed )
            return;
    }

    /* An immortal-specified skill list overrides set logic. */
    spec_only = ( ch->pcdata->psionic_grant_spec != NULL
               && ch->pcdata->psionic_grant_spec[0] != '\0' );

    is_final = ( ch->pcdata->num_remorts >= 5 );

    if ( spec_only )
    {
        if ( !normalize_psionic_arguments(ch->pcdata->psionic_grant_spec,
                                          normalized_spec,
                                          sizeof(normalized_spec), invalid)
        ||   normalized_spec[0] == '\0' )
        {
            bug( "Grant_psionics: discarded an invalid saved grant list.", 0 );
            free_string( ch->pcdata->psionic_grant_spec );
            ch->pcdata->psionic_grant_spec = str_dup( "" );
            spec_only = false;
        }
        else
        {
            free_string( ch->pcdata->psionic_grant_spec );
            ch->pcdata->psionic_grant_spec = str_dup( normalized_spec );
        }
    }

    /* Everything awarded in an earlier life comes back first.  The skill
     * table was wiped by the remort; the remembered list was not. */
    for ( s = 0; s < 4; s++ )
    {
        for ( i = 0; psi_sets[s][i] != NULL; i++ )
        {
            sh_int sn = *psi_sets[s][i];

            if ( psionic_is_known( ch, sn ) )
            {
                if ( ch->pcdata->learned[(int)sn] < 75 )
                {
                    ch->pcdata->learned[(int)sn] = 75;
                    psi_log( ch, "restored %s (%s set) to 75%% from an "
                                 "earlier life", skill_table[(int)sn].name,
                             psi_set_names[s] );
                }
                selected++;
            }
        }
    }

    if ( is_final )
    {
        /* The final remort hands over the whole discipline: all 17 powers,
         * ahead of any immortal-supplied list, because there is no later
         * life to award the rest in. */
        for ( s = 0; s < 4; s++ )
        {
            for ( i = 0; psi_sets[s][i] != NULL; i++ )
            {
                sh_int sn = *psi_sets[s][i];
                if ( sn >= 0 && !psionic_is_known( ch, sn ) )
                {
                    psionic_learn( ch, sn );
                    psi_log( ch, "granted %s (%s set) -- final remort, "
                                 "every power", skill_table[(int)sn].name,
                             psi_set_names[s] );
                    selected++;
                }
            }
        }
    }
    else if ( spec_only )
    {
        /* Grant only the skills matching the immortal-supplied spec string. */
        for ( s = 0; s < 4; s++ )
        {
            for ( i = 0; psi_sets[s][i] != NULL; i++ )
            {
                sh_int sn = *psi_sets[s][i];
                if ( sn >= 0 && !psionic_is_known( ch, sn )
                &&   psionic_spec_contains( ch->pcdata->psionic_grant_spec,
                                            skill_table[(int)sn].name ) )
                {
                    psionic_learn( ch, sn );
                    psi_log( ch, "granted %s (%s set) -- named in the "
                                 "immortal spec", skill_table[(int)sn].name,
                             psi_set_names[s] );
                    selected++;
                }
            }
        }
    }
    else
    {
        /* One power from each discipline at the second remort, and one more
         * from each at every remort after it.  They stack: the count below
         * is how many of a set the character should end up holding, so a
         * remort adds to what the last one gave rather than redealing it. */
        int want = UMAX( 1, ch->pcdata->num_remorts - 1 );

        for ( s = 0; s < 4; s++ )
        {
            int unknown[6];
            int count = 0;
            int held  = 0;

            for ( i = 0; i < psi_set_sizes[s]; i++ )
            {
                sh_int sn = *psi_sets[s][i];

                if ( sn < 0 )
                    continue;
                if ( psionic_is_known( ch, sn ) )
                    held++;
                else
                    unknown[count++] = i;
            }

            psi_log( ch, "%s set: holds %d of %d, target %d for remort %d, "
                         "%d candidate%s", psi_set_names[s], held,
                     psi_set_sizes[s], want, ch->pcdata->num_remorts,
                     count, count == 1 ? "" : "s" );

            while ( held < want && count > 0 )
            {
                int pick = number_range( 0, count - 1 );
                sh_int chosen = *psi_sets[s][unknown[pick]];

                psionic_learn( ch, chosen );
                psi_log( ch, "granted %s (%s set) -- drew %d of %d unheld",
                         skill_table[(int)chosen].name, psi_set_names[s],
                         pick + 1, count );
                selected++;
                held++;
                unknown[pick] = unknown[--count];
            }
        }
    }

    if ( selected == 0 )
    {
        /* Clearing the flag matters as much as the bug does: this runs
           off a level check, so a pending grant that selects nothing
           would try again on every one of them, forever. */
        psi_log( ch, "nothing could be selected -- grant abandoned" );
        ch->pcdata->psionic_grant_pending = false;
        bug( "Grant_psionics: no valid skills were selected.", 0 );
        return;
    }

    psi_log( ch, "grant complete, %d power%s now held", selected,
             selected == 1 ? "" : "s" );

    ch->pcdata->psionic               = 1;
    ch->pcdata->psionic_grant_pending = false;
    /* Clear spec so future auto-grants use set logic, not a stale immortal list. */
    free_string( ch->pcdata->psionic_grant_spec );
    ch->pcdata->psionic_grant_spec = str_dup( "" );
    send_to_char( "\n\r{0E}Your mind awakens to hidden psionic powers!{x}\n\r", ch );
}

/*
 * Characters who earned psionics before the powers were remembered by name
 * hold them only in the skill table, which the next remort wipes. Seeding
 * the list from what they already know means their first stacking remort
 * adds to those rather than dealing a fresh hand.
 */
/*
 * Put back every power the character has been given in any life, at 75%
 * where the skill wipe left less. grant_psionics does this as its first
 * step from the second remort on; the first remort awards nothing new,
 * and used to award nothing back either, so a character who awoke at
 * 18-21 or was granted powers lost them for a whole life. Returns how
 * many it restored.
 */
int psionic_restore_known( CHAR_DATA *ch )
{
    int i;
    int restored = 0;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return 0;

    for ( i = 0; psionic_skill_names[i] != NULL; i++ )
    {
        int sn = skill_lookup( psionic_skill_names[i] );

        if ( sn < 0 || !psionic_is_known( ch, (sh_int)sn ) )
            continue;
        if ( ch->pcdata->learned[sn] < 75 )
        {
            ch->pcdata->learned[sn] = 75;
            psi_log( ch, "restored %s to 75%% from an earlier life",
                     skill_table[sn].name );
            restored++;
        }
    }
    if ( restored > 0 )
        ch->pcdata->psionic = 1;
    return restored;
}

void psionic_sync_known( CHAR_DATA *ch )
{
    int i;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    for ( i = 0; psionic_skill_names[i] != NULL; i++ )
    {
        int sn = skill_lookup( psionic_skill_names[i] );

        if ( sn >= 0 && ch->pcdata->learned[sn] > 0 )
            psionic_remember( ch, psionic_skill_names[i] );
    }
}

void list_group_known( CHAR_DATA *ch )
{
    UNUSED_PARAM(ch);
}

static void stub_notify( CHAR_DATA *ch )
{
    if ( ch != NULL )
        send_to_char( "That command is not available.\n\r", ch );
}




void do_ignore( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}












void do_wizinfo( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    
    if (IS_NPC(ch))
    {
        return;
    }

    if (argument[0] == '\0')
    {
        if (IS_SET(ch->comm, COMM_NOWIZINFO))
        {
            send_to_char("Wizinfo channel is now ON.\n\r", ch);
            REMOVE_BIT(ch->comm, COMM_NOWIZINFO);
        }
        else
        {
            send_to_char("Wizinfo channel is now OFF.\n\r", ch);
            SET_BIT(ch->comm, COMM_NOWIZINFO);
        }
    }
    else
    {
        send_to_char("Just type 'wizinfo' to toggle the channel on or off.\n\r", ch);
    }
}
