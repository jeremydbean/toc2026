#include "merc.h"
#include "interp.h"

void init_web( int port )
{
    UNUSED_PARAM(port);
}

void handle_web( void )
{
}

void send_info( char *argument )
{
    UNUSED_PARAM(argument);
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
    UNUSED_PARAM(invalid);

    if ( output == NULL || length == 0 )
        return FALSE;

    toc_strlcpy( output, argument != NULL ? argument : "", length );
    return TRUE;
}

void grant_psionics( CHAR_DATA *ch, int chance, bool force_grant )
{
    /* 4 thematic psionic skill sets.  Normal remorts (2-4): 1 random skill
     * per set (4 total).  Final remort (num_remorts == 5): all 15 skills.
     * Immortal grantpsi with a spec: honours the spec and bypasses sets.
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
        /* Grant only the skills matching the immortal-supplied spec string. */
        for ( s = 0; s < 4; s++ )
        {
            for ( i = 0; psi_sets[s][i] != NULL; i++ )
            {
                sh_int sn = *psi_sets[s][i];
                if ( sn >= 0 &&
                     strstr( ch->pcdata->psionic_grant_spec,
                             skill_table[(int)sn].name ) != NULL )
                {
                    if ( ch->pcdata->learned[(int)sn] < 75 )
                        ch->pcdata->learned[(int)sn] = 75;
                }
            }
        }
    }
    else if ( is_final )
    {
        /* Final remort: award all 15 psionic skills. */
        for ( s = 0; s < 4; s++ )
        {
            for ( i = 0; psi_sets[s][i] != NULL; i++ )
            {
                sh_int sn = *psi_sets[s][i];
                if ( sn >= 0 && ch->pcdata->learned[(int)sn] < 75 )
                    ch->pcdata->learned[(int)sn] = 75;
            }
        }
    }
    else
    {
        /* Normal remorts (2-4): pick 1 random skill from each set = 4 skills. */
        for ( s = 0; s < 4; s++ )
        {
            int pick = number_range( 0, psi_set_sizes[s] - 1 );
            sh_int sn = *psi_sets[s][pick];
            if ( sn >= 0 && ch->pcdata->learned[(int)sn] < 75 )
                ch->pcdata->learned[(int)sn] = 75;
        }
    }

    ch->pcdata->psionic               = 1;
    ch->pcdata->psionic_grant_pending = false;
    /* Clear spec so future auto-grants use set logic, not a stale immortal list. */
    free_string( ch->pcdata->psionic_grant_spec );
    ch->pcdata->psionic_grant_spec = str_dup( "" );
    send_to_char( "\n\r{0E}Your mind awakens to hidden psionic powers!{x}\n\r", ch );
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

void do_note( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_castle( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_cgos( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_ignore( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_info( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_alias( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_beep( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_leveling( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_qui( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_roll( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_dns( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_godtalk( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_hero( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_immtalk( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    stub_notify( ch );
}

void do_notell( CHAR_DATA *ch, char *argument )
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
