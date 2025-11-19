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
    UNUSED_PARAM(ch);
    UNUSED_PARAM(argument);
}

bool normalize_psionic_arguments( const char *argument, char *output, size_t length, char *invalid )
{
    UNUSED_PARAM(invalid);

    if ( output == NULL || length == 0 )
        return FALSE;

    strlcpy( output, argument != NULL ? argument : "", length );
    return TRUE;
}

void grant_psionics( CHAR_DATA *ch, int chance, bool force_grant )
{
    UNUSED_PARAM(ch);
    UNUSED_PARAM(chance);
    UNUSED_PARAM(force_grant);
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
    stub_notify( ch );
}
