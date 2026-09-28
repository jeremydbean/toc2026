#include <ctype.h>
#include "merc.h"
#include "interp.h"

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
    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    /* Grant psionics when an immortal advances a char who has remorted 2+ times
     * and hasn't received psionics yet. */
    if ( ch->pcdata->num_remorts >= 2 && ch->pcdata->psionic <= 0 )
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

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    if ( !force_grant && number_percent() >= chance )
        return;

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
                    ch->pcdata->learned[(int)sn] = 75;
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

            while ( held < want && count > 0 )
            {
                int pick = number_range( 0, count - 1 );

                psionic_learn( ch, *psi_sets[s][unknown[pick]] );
                selected++;
                held++;
                unknown[pick] = unknown[--count];
            }
        }
    }

    if ( selected == 0 )
    {
        bug( "Grant_psionics: no valid skills were selected.", 0 );
        return;
    }

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
