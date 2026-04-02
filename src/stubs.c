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
    /* All fifteen psionic skill gsn pointers. */
    static const sh_int *psionics[] = {
        &gsn_astral_walk,   &gsn_clairvoyance, &gsn_confuse,
        &gsn_ego_whip,      &gsn_mindbar,      &gsn_mindblast,
        &gsn_nightmare,     &gsn_project,      &gsn_psionic_armor,
        &gsn_psychic_shield,&gsn_pyrotechnics, &gsn_shift,
        &gsn_telekinesis,   &gsn_torment,      &gsn_transfusion,
        NULL
    };
    int i;
    bool spec_only;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    if ( !force_grant && number_percent() >= chance )
        return;

    /* If an immortal specified a particular skill list, honour it. */
    spec_only = ( ch->pcdata->psionic_grant_spec != NULL
               && ch->pcdata->psionic_grant_spec[0] != '\0' );

    for ( i = 0; psionics[i] != NULL; i++ )
    {
        sh_int sn = *psionics[i];
        if ( sn < 0 )
            continue;

        if ( spec_only )
        {
            /* Match by skill name substring (names are unique enough). */
            if ( strstr( ch->pcdata->psionic_grant_spec,
                         skill_table[(int)sn].name ) == NULL )
                continue;
        }

        if ( ch->pcdata->learned[(int)sn] < 75 )
            ch->pcdata->learned[(int)sn] = 75;
    }

    ch->pcdata->psionic              = 1;
    ch->pcdata->psionic_grant_pending = false;
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
