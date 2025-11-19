/***************************************************************************
 * Original Diku Mud copyright (C) 1990, 1991 by Sebastian Hammer,        *
 * Michael Seifert, Hans Henrik St{rfeldt, Tom Madsen, and Katja Nyboe.   *
 * *
 * Merc Diku Mud improvments copyright (C) 1992, 1993 by Michael          *
 * Chastain, Michael Quan, and Mitchell Tse.                              *
 * *
 * In order to use any part of this Merc Diku Mud, you must comply with   *
 * both the original Diku license in 'license.doc' as well as the         *
 * Merc license in 'license.txt'.  In particular, you may not remove      *
 * these copyright notices.                                               *
 * *
 * Much time and thought has gone into this software and you are          *
 * benefitting.  We hope that you share your changes too.  What goes      *
 * around, comes around.                                                  *
 ***************************************************************************/

/***************************************************************************
*	ROM 2.4 is copyright 1993-1998 Russ Taylor			                   *
*	ROM has been brought to you by the ROM consortium		               *
*	    Russ Taylor (rtaylor@hypercube.org)				                   *
*	    Gabrielle Taylor (gtaylor@hypercube.org)			               *
*	    Brian Moore (zump@rom.org)					                       *
*	By using this code, you have agreed to follow the terms of the	       *
*	ROM license, in the file Rom24/doc/rom.license			               *
***************************************************************************/

#include <sys/types.h>
#include <sys/time.h>
#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <stdarg.h>
#include "merc.h"
#include "interp.h"
#include "db.h" // For resolving declarations

/* RT code to delete yourself */

void do_delet( CHAR_DATA *ch, char *argument)
{
    UNUSED_PARAM(argument);

    send_to_char("You must type the full command to delete yourself.\n\r",ch);
}

void do_delete( CHAR_DATA *ch, char *argument)
{
    char strsave[MAX_INPUT_LENGTH];

    if (IS_NPC(ch))
	return;

    if (ch->pcdata->confirm_delete)
    {
	if (argument[0] != '\0')
	{
	    send_to_char("Delete status removed.\n\r",ch);
	    ch->pcdata->confirm_delete = FALSE;
	    return;
	}
	else
	{
	    sprintf( strsave, "%s%s", PLAYER_DIR, capitalize( ch->name ) );
            log_string("[DELETE] Character self-deleted.");
	    stop_fighting(ch,TRUE);
	    do_quit(ch,"");
	    unlink(strsave);
	    return;
	}
    }

    if (argument[0] != '\0')
    {
	send_to_char("Just type delete. No argument.\n\r",ch);
	return;
    }

    send_to_char("Type delete again to confirm this command.\n\r",ch);
    send_to_char("WARNING: this command is irreversible.\n\r",ch);
    send_to_char("Typing delete with an argument will undo the delete status.\n\r",
	ch);
    ch->pcdata->confirm_delete = TRUE;
    log_string("[DELETE] Character is contemplating deletion.");
}
	    

void do_channels( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];

    UNUSED_PARAM(argument);

    /* lists all channels and their status */
    send_to_char("   channel     status\n\r",ch);
    send_to_char("---------------------\n\r",ch);
 
    send_to_char("gossip         ",ch);
    if (!IS_SET(ch->comm,COMM_NOGOSSIP))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    send_to_char("music          ",ch);
    if (!IS_SET(ch->comm,COMM_NOMUSIC))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    send_to_char("Q/A            ",ch);
    if (!IS_SET(ch->comm,COMM_NOQUESTION))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    send_to_char("grats          ",ch);
    if (!IS_SET(ch->comm,COMM_NOGRATZ))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    if (IS_IMMORTAL(ch))
    {
      send_to_char("god channel    ",ch);
      if(!IS_SET(ch->comm,COMM_NOWIZ))
        send_to_char("ON\n\r",ch);
      else
        send_to_char("OFF\n\r",ch);
    }

    send_to_char("shouts         ",ch);
    if (!IS_SET(ch->comm,COMM_NOSHOUT))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    send_to_char("tells          ",ch);
    if (!IS_SET(ch->comm,COMM_DEAF))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    send_to_char("quiet mode     ",ch);
    if (IS_SET(ch->comm,COMM_QUIET))
      send_to_char("ON\n\r",ch);
    else
      send_to_char("OFF\n\r",ch);

    if (IS_SET(ch->act,PLR_AFK))
      send_to_char("You are AFK.\n\r",ch);
   
    if (ch->lines != PAGELEN)
    {
      if (ch->lines)
      {
        snprintf(buf, sizeof(buf), "You display %d lines of scroll.\n\r",ch->lines+2);
        send_to_char(buf,ch);
      }
      else
        send_to_char("Scroll buffering is off.\n\r",ch);
    }

    if (ch->prompt != NULL)
    {
      snprintf(buf, sizeof(buf), "Your current prompt is: %s\n\r",ch->prompt);
      send_to_char(buf,ch);
    }

    if (IS_SET(ch->comm,COMM_NOSHOUT))
      send_to_char("You cannot shout.\n\r",ch);
  
    if (IS_SET(ch->comm,COMM_NOTELL))
      send_to_char("You cannot use tell.\n\r",ch);
 
    if (IS_SET(ch->comm,COMM_NOCHANNELS))
     send_to_char("You cannot use channels.\n\r",ch);

    if (IS_SET(ch->comm,COMM_NOEMOTE))
      send_to_char("You cannot show emotions.\n\r",ch);

}

/* RT deaf blocks all tells */

void do_deaf( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);

    
    if (IS_SET(ch->comm,COMM_DEAF))
    {
      send_to_char("You can now hear tells again.\n\r",ch);
      REMOVE_BIT(ch->comm,COMM_DEAF);
    }
    else 
    {
      send_to_char("From now on, you won't hear tells.\n\r",ch);
      SET_BIT(ch->comm,COMM_DEAF);
    }
}

/* RT quiet blocks the user from communiation */

void do_quiet ( CHAR_DATA *ch, char * argument)
{
    UNUSED_PARAM(argument);

    if (IS_SET(ch->comm,COMM_QUIET))
    {
      send_to_char("Quiet mode removed.\n\r",ch);
      REMOVE_BIT(ch->comm,COMM_QUIET);
    }
   else
   {
     send_to_char("From now on, you will only hear says and emotes.\n\r",ch);
     SET_BIT(ch->comm,COMM_QUIET);
   }
}

/* afk command */

void do_afk ( CHAR_DATA *ch, char * argument)
{
    UNUSED_PARAM(argument);
    if (IS_SET(ch->act,PLR_AFK))
    {
      send_to_char("AFK mode removed.\n\r",ch);
      REMOVE_BIT(ch->act,PLR_AFK);
    }
   else
   {
     send_to_char("You are now in AFK mode.\n\r",ch);
     SET_BIT(ch->act,PLR_AFK);
   }
}

void do_replay (CHAR_DATA *ch, char *argument)
{
    UNUSED_PARAM(argument);
    send_to_char("Replay history is unavailable.\n\r", ch);
}

void do_auction( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    send_to_char("The auction channel is currently unavailable.\n\r", ch);
}

void do_gossip( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;
 
    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOGOSSIP))
      {
        send_to_char("Gossip channel is now ON.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOGOSSIP);
      }
      else
      {
        send_to_char("Gossip channel is now OFF.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOGOSSIP);
      }
    }
    else  /* gossip message sent, turn gossip on if it is off */
    {
        if (IS_SET(ch->comm,COMM_QUIET))
        {
          send_to_char("You must turn off quiet mode first.\n\r",ch);
          return;
        }
 
        if (IS_SET(ch->comm,COMM_NOCHANNELS))
        {
          send_to_char("The gods have revoked your channel priviliges.\n\r",ch);
          return;
 
        }
 
      REMOVE_BIT(ch->comm,COMM_NOGOSSIP);
 
      snprintf( buf, sizeof(buf), "You gossip '%s'\n\r", argument );
      send_to_char( buf, ch );
      for ( d = descriptor_list; d != NULL; d = d->next )
      {
        CHAR_DATA *victim;
 
        victim = d->original ? d->original : d->character;
 
        if ( d->connected == CON_PLAYING &&
             d->character != ch &&
             !IS_SET(victim->comm,COMM_NOGOSSIP) &&
             !IS_SET(victim->comm,COMM_QUIET) )
        {
            act_new_cstr( "$n gossips '$t'", 
		     ch,argument, d->character, TO_VICT,POS_SLEEPING );
        }
      }
    }
}

void do_grats( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    send_to_char("The grats channel is currently unavailable.\n\r", ch);
}

void do_quote( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    send_to_char("The quote channel is currently unavailable.\n\r", ch);
}

void do_question( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;
 
    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOQUESTION))
      {
        send_to_char("Q/A channel is now ON.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOQUESTION);
      }
      else
      {
        send_to_char("Q/A channel is now OFF.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOQUESTION);
      }
    }
    else  /* question message sent, turn question on if it is off */
    {
        if (IS_SET(ch->comm,COMM_QUIET))
        {
          send_to_char("You must turn off quiet mode first.\n\r",ch);
          return;
        }
 
        if (IS_SET(ch->comm,COMM_NOCHANNELS))
        {
          send_to_char("The gods have revoked your channel priviliges.\n\r",ch);
          return;
 
        }
 
      REMOVE_BIT(ch->comm,COMM_NOQUESTION);
 
      snprintf( buf, sizeof(buf), "You question '%s'\n\r", argument );
      send_to_char( buf, ch );
      for ( d = descriptor_list; d != NULL; d = d->next )
      {
        CHAR_DATA *victim;
 
        victim = d->original ? d->original : d->character;
 
        if ( d->connected == CON_PLAYING &&
             d->character != ch &&
             !IS_SET(victim->comm,COMM_NOQUESTION) &&
             !IS_SET(victim->comm,COMM_QUIET) )
        {
            act_new_cstr( "$n questions '$t'", 
		     ch,argument, d->character, TO_VICT,POS_SLEEPING );
        }
      }
    }
}

/* RT answer command is same as question */

void do_answer( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;
 
    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOQUESTION))
      {
        send_to_char("Q/A channel is now ON.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOQUESTION);
      }
      else
      {
        send_to_char("Q/A channel is now OFF.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOQUESTION);
      }
    }
    else  /* answer message sent, turn answer on if it is off */
    {
        if (IS_SET(ch->comm,COMM_QUIET))
        {
          send_to_char("You must turn off quiet mode first.\n\r",ch);
          return;
        }
 
        if (IS_SET(ch->comm,COMM_NOCHANNELS))
        {
          send_to_char("The gods have revoked your channel priviliges.\n\r",ch);
          return;
 
        }
 
      REMOVE_BIT(ch->comm,COMM_NOQUESTION);
 
      snprintf( buf, sizeof(buf), "You answer '%s'\n\r", argument );
      send_to_char( buf, ch );
      for ( d = descriptor_list; d != NULL; d = d->next )
      {
        CHAR_DATA *victim;
 
        victim = d->original ? d->original : d->character;
 
        if ( d->connected == CON_PLAYING &&
             d->character != ch &&
             !IS_SET(victim->comm,COMM_NOQUESTION) &&
             !IS_SET(victim->comm,COMM_QUIET) )
        {
            act_new_cstr( "$n answers '$t'", 
		     ch,argument, d->character, TO_VICT,POS_SLEEPING );
        }
      }
    }
}

void do_music( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;
 
    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOMUSIC))
      {
        send_to_char("Music channel is now ON.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOMUSIC);
      }
      else
      {
        send_to_char("Music channel is now OFF.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOMUSIC);
      }
    }
    else  /* music message sent, turn music on if it is off */
    {
        if (IS_SET(ch->comm,COMM_QUIET))
        {
          send_to_char("You must turn off quiet mode first.\n\r",ch);
          return;
        }
 
        if (IS_SET(ch->comm,COMM_NOCHANNELS))
        {
          send_to_char("The gods have revoked your channel priviliges.\n\r",ch);
          return;
 
        }
 
      REMOVE_BIT(ch->comm,COMM_NOMUSIC);
 
      snprintf( buf, sizeof(buf), "You MUSIC: '%s'\n\r", argument );
      send_to_char( buf, ch );
      for ( d = descriptor_list; d != NULL; d = d->next )
      {
        CHAR_DATA *victim;
 
        victim = d->original ? d->original : d->character;
 
        if ( d->connected == CON_PLAYING &&
             d->character != ch &&
             !IS_SET(victim->comm,COMM_NOMUSIC) &&
             !IS_SET(victim->comm,COMM_QUIET) )
        {
            act_new_cstr( "$n MUSIC: '$t'", 
		     ch,argument, d->character, TO_VICT,POS_SLEEPING );
        }
      }
    }
}

void do_clan( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);
    send_to_char("Clan chat is currently unavailable.\n\r", ch);
}

void do_immort( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    DESCRIPTOR_DATA *d;
 
    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOWIZ))
      {
        send_to_char("Immortal channel is now ON.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOWIZ);
      }
      else
      {
        send_to_char("Immortal channel is now OFF.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOWIZ);
      }
    }
    else  /* immort message sent, turn immort on if it is off */
    {
        if (IS_SET(ch->comm,COMM_QUIET))
        {
          send_to_char("You must turn off quiet mode first.\n\r",ch);
          return;
        }
 
        if (IS_SET(ch->comm,COMM_NOCHANNELS))
        {
          send_to_char("The gods have revoked your channel priviliges.\n\r",ch);
          return;
 
        }
 
      REMOVE_BIT(ch->comm,COMM_NOWIZ);
 
      snprintf( buf, sizeof(buf), "You immort '%s'\n\r", argument );
      send_to_char( buf, ch );
      for ( d = descriptor_list; d != NULL; d = d->next )
      {
        CHAR_DATA *victim;
 
        victim = d->original ? d->original : d->character;
 
        if ( d->connected == CON_PLAYING &&
             d->character != ch &&
             IS_IMMORTAL(victim) &&
             !IS_SET(victim->comm,COMM_NOWIZ) &&
             !IS_SET(victim->comm,COMM_QUIET) )
        {
            act_new_cstr( "$n immorts '$t'", 
		     ch,argument, d->character, TO_VICT,POS_DEAD );
        }
      }
    }
}

void do_say( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];

    if ( argument[0] == '\0' )
    {
	send_to_char( "Say what?\n\r", ch );
	return;
    }

    /* Code Safety: Truncate argument if too long to prevent issues downstream */
    if ( strlen(argument) > MAX_INPUT_LENGTH - 100 )
        argument[MAX_INPUT_LENGTH - 100] = '\0';

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "You say '%s'$d\n\r", argument );
    act( buf, ch, NULL, NULL, TO_CHAR );

    snprintf( buf, sizeof(buf), "$n says '%s'$d", argument );
    act( buf, ch, NULL, NULL, TO_ROOM );

    return;
}


void do_shout( CHAR_DATA *ch, char *argument )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];

    if (argument[0] == '\0' )
    {
      if (IS_SET(ch->comm,COMM_NOSHOUT))
      {
        send_to_char("You can hear shouts again.\n\r",ch);
        REMOVE_BIT(ch->comm,COMM_NOSHOUT);
      }
      else
      {
        send_to_char("You will no longer hear shouts.\n\r",ch);
        SET_BIT(ch->comm,COMM_NOSHOUT);
      }
      return;
    }

    if ( IS_SET(ch->comm, COMM_NOSHOUT) )
    {
        send_to_char( "You can't shout.\n\r", ch );
        return;
    }

    REMOVE_BIT(ch->comm,COMM_NOSHOUT);

    WAIT_STATE( ch, 12 );
    
    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "You shout '%s'\n\r", argument );
    send_to_char( buf, ch );
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
	CHAR_DATA *victim;

	victim = d->original ? d->original : d->character;

	if ( d->connected == CON_PLAYING &&
	     d->character != ch &&
             !IS_SET(victim->comm, COMM_NOSHOUT) &&
	     !IS_SET(victim->comm, COMM_QUIET) ) 
	{
	    act_new_cstr("$n shouts '$t'",ch,argument,d->character,TO_VICT,POS_SLEEPING);
	}
    }

    return;
}



void do_tell( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim;

    if ( IS_SET(ch->comm, COMM_NOTELL) || IS_SET(ch->comm,COMM_DEAF))
    {
	send_to_char( "Your message didn't get through.\n\r", ch );
	return;
    }

    if ( IS_SET(ch->comm, COMM_QUIET) )
    {
	send_to_char( "You must turn off quiet mode first.\n\r", ch);
	return;
    }

    if (IS_SET(ch->comm,COMM_DEAF))
    {
	send_to_char("You must turn off deaf mode first.\n\r",ch);
	return;
    }

    argument = one_argument( argument, arg );

    if ( arg[0] == '\0' || argument[0] == '\0' )
    {
	send_to_char( "Tell whom what?\n\r", ch );
	return;
    }

    /*
     * Can tell to PC's anywhere, but NPC's only in same room.
     * -- Furey
     */
    if ( ( victim = get_char_world( ch, arg ) ) == NULL
    || ( IS_NPC(victim) && victim->in_room != ch->in_room ) )
    {
	send_to_char( "They aren't here.\n\r", ch );
	return;
    }

    if ( !(IS_IMMORTAL(ch) && ch->level > LEVEL_IMMORTAL) && !IS_AWAKE(victim) )
    {
        act( "$E can't hear you.", ch, 0, victim, TO_CHAR );
        return;
    }

    if ((IS_SET(victim->comm,COMM_QUIET) || IS_SET(victim->comm,COMM_DEAF))
    && !IS_IMMORTAL(ch))
    {
	act( "$E is not receiving tells.", ch, 0, victim, TO_CHAR );
  	return;
    }

    if (IS_SET(victim->act,PLR_AFK))
    {
        act("$E is AFK and may not respond right away.",ch,NULL,victim,TO_CHAR);
        return;
    }

    /* Code Safety: snprintf and buffer safety */
    snprintf( buf, sizeof(buf), "You tell %s '%s'\n\r", victim->name, argument );
    send_to_char( buf, ch );
    
    snprintf( buf, sizeof(buf), "%s tells you '%s'\n\r", PERS(ch, victim), argument );
    buf[0] = UPPER(buf[0]);
    send_to_char( buf, victim );
    victim->reply	= ch;

    return;
}



void do_reply( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *victim;
    char buf[MAX_STRING_LENGTH];

    if ( IS_SET(ch->comm, COMM_NOTELL) )
    {
	send_to_char( "Your message didn't get through.\n\r", ch );
	return;
    }

    if ( ( victim = ch->reply ) == NULL )
    {
	send_to_char( "They aren't here.\n\r", ch );
	return;
    }

    if ( !IS_IMMORTAL(ch) && !IS_AWAKE(victim) )
    {
        act( "$E can't hear you.", ch, 0, victim, TO_CHAR );
        return;
    }

    if ((IS_SET(victim->comm,COMM_QUIET) || IS_SET(victim->comm,COMM_DEAF))
    &&  !IS_IMMORTAL(ch) && !IS_IMMORTAL(victim))
    {
        act( "$E is not receiving tells.", ch, 0, victim, TO_CHAR );
        return;
    }

    if (IS_SET(victim->act,PLR_AFK))
    {
        act("$E is AFK and may not respond right away.",ch,NULL,victim,TO_CHAR);
        return;
    }

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "You reply to %s '%s'\n\r", victim->name, argument );
    send_to_char( buf, ch );
    
    snprintf( buf, sizeof(buf), "%s replies '%s'\n\r", PERS(ch, victim), argument );
    buf[0] = UPPER(buf[0]);
    send_to_char( buf, victim );
    victim->reply	= ch;

    return;
}



void do_yell( CHAR_DATA *ch, char *argument )
{
    DESCRIPTOR_DATA *d;
    char buf[MAX_STRING_LENGTH];

    if ( IS_SET(ch->comm, COMM_NOSHOUT) )
    {
	send_to_char( "You can't yell.\n\r", ch );
	return;
    }

    if ( argument[0] == '\0' )
    {
	send_to_char( "Yell what?\n\r", ch );
	return;
    }


    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "You yell '%s'\n\r", argument );
    send_to_char( buf, ch );
    
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
	if ( d->connected == CON_PLAYING
	&&   d->character != ch
	&&   d->character->in_room != NULL
	&&   d->character->in_room->area == ch->in_room->area 
        &&   !IS_SET(d->character->comm,COMM_QUIET) )
	{
	    act_new_cstr("$n yells '$t'",ch,argument,d->character,TO_VICT,POS_SLEEPING);
	}
    }

    return;
}


void do_emote( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char *plast;

    if ( !IS_NPC(ch) && IS_SET(ch->comm, COMM_NOEMOTE) )
    {
	send_to_char( "You can't show your emotions.\n\r", ch );
	return;
    }

    if ( argument[0] == '\0' )
    {
	send_to_char( "Emote what?\n\r", ch );
	return;
    }

    if ( isalpha(argument[0]) || isdigit(argument[0]) )
    {
        /* Code Safety: snprintf */
        snprintf( buf, sizeof(buf), "$n %s", argument );
    }
    else
    {
        /* Code Safety: snprintf */
        snprintf( buf, sizeof(buf), "$n%s", argument );
    }

    /*
     * Buffer overflow safety check for punctuation appendage
     */
    if ( strlen(buf) < MAX_STRING_LENGTH - 2 ) // Ensure space for punctuation + null
    {
        plast = buf + strlen(buf) - 1;
        if ( isalpha(*plast) )
            strcat( buf, "." );
    }

    act( buf, ch, NULL, NULL, TO_ROOM );
    act( buf, ch, NULL, NULL, TO_CHAR );
    return;
}


void do_pmote( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *vch;
    char *letter,*name;
    char last[MAX_INPUT_LENGTH], temp[MAX_STRING_LENGTH];
    size_t matches = 0;

    if ( !IS_NPC(ch) && IS_SET(ch->comm, COMM_NOEMOTE) )
    {
        send_to_char( "You can't show your emotions.\n\r", ch );
        return;
    }

    if ( argument[0] == '\0' )
    {
        send_to_char( "Emote what?\n\r", ch );
        return;
    }

    act( "$n $t", ch, argument, NULL, TO_CHAR );

    for (vch = ch->in_room->people; vch != NULL; vch = vch->next_in_room)
    {
	if (vch->desc == NULL || vch == ch)
	    continue;

	if ((letter = strstr(argument,vch->name)) == NULL)
	{
	    act("$n $t",ch,argument,vch,TO_VICT);
	    continue;
	}

	strcpy(temp,argument);
	temp[strlen(argument) - strlen(letter)] = '\0';
	last[0] = '\0';
	name = vch->name;
	
	for (; *letter != '\0'; letter++)
	{ 
	    if (*letter == '\'' && matches == strlen(vch->name))
	    {
		strcat(temp,"r");
		continue;
	    }

	    if (*letter == 's' && matches == strlen(vch->name))
	    {
		matches = 0;
		continue;
	    }
	    
 	    if (matches == strlen(vch->name))
	    {
		matches = 0;
	    }

	    if (*letter == *name)
	    {
		matches++;
		name++;
		if (matches == strlen(vch->name))
		{
		    strcat(temp,"you");
		    last[0] = '\0';
		    name = vch->name;
		    continue;
		}
		strncat(last,letter,1);
		continue;
	    }

	    matches = 0;
	    strcat(temp,last);
	    strncat(temp,letter,1);
	    last[0] = '\0';
	    name = vch->name;
	}

	act("$n $t",ch,temp,vch,TO_VICT);
    }
	
    return;
}


/*
 * All the posing stuff.
 */
struct	pose_table_type
{
    char *	message[2*MAX_CLASS];
};

const	struct	pose_table_type	pose_table	[]	=
{
    {
	{
	    "You sizzle with energy.",
	    "$n sizzles with energy.",
	    "You feel very holy.",
	    "$n looks very holy.",
	    "You perform a small theatrical pose.",
	    "$n performs a small theatrical pose.",
	    "You show your bulging muscles.",
	    "$n shows $s bulging muscles."
	}
    },

    {
	{
	    "You turn into a butterfly, then return to your normal shape.",
	    "$n turns into a butterfly, then returns to $s normal shape.",
	    "You nonchalantly turn wine into water.",
	    "$n nonchalantly turns wine into water.",
	    "You wiggle your ears alternately.",
	    "$n wiggles $s ears alternately.",
	    "You crack knuckles.",
	    "$n cracks $s knuckles."
	}
    },

    {
	{
	    "Blue sparks fly from your fingers.",
	    "Blue sparks fly from $n's fingers.",
	    "A halo appears over your head.",
	    "A halo appears over $n's head.",
	    "You perform a dazzling pirouette.",
	    "$n performs a dazzling pirouette.",
	    "You flex your biceps.",
	    "$n flexes $s biceps."
	}
    },

    {
	{
	    "Little red lights dance in your eyes.",
	    "Little red lights dance in $n's eyes.",
	    "You recite words of wisdom.",
	    "$n recites words of wisdom.",
	    "You pull a white rabbit out of your hat.",
	    "$n pulls a white rabbit out of $s hat.",
	    "You do a back flip.",
	    "$n does a back flip."
	}
    },

    {
	{
	    "A slimy green monster appears before you and bows.",
	    "A slimy green monster appears before $n and bows.",
	    "Deep in prayer, you levitate.",
	    "Deep in prayer, $n levitates.",
	    "You twirl your whiskers.",
	    "$n twirls $s whiskers.",
	    "You stand on your hands.",
	    "$n stands on $s hands."
	}
    },

    {
	{
	    "You turn your hands into the claws of a dragon.",
	    "$n turns $s hands into the claws of a dragon.",
	    "An angel consults you.",
	    "An angel consults $n.",
	    "You wiggle your nose.",
	    "$n wiggles $s nose.",
	    "You pump your chest.",
	    "$n pumps $s chest."
	}
    },

    {
	{
	    "You write runes in the air with a finger.",
	    "$n writes runes in the air with a finger.",
	    "Your body glows with an unearthly light.",
	    "$n's body glows with an unearthly light.",
	    "You spider-walk up the wall.",
	    "$n spider-walks up the wall.",
	    "You grab your head and scream in pain.",
	    "$n grabs $s head and screams in pain."
	}
    },

    {
	{
	    "You open a door to another dimension.",
	    "$n opens a door to another dimension.",
	    "A spot light hits you.",
	    "A spot light hits $n.",
	    "You grab your rose and put it in your teeth.",
	    "$n grabs $s rose and puts it in $s teeth.",
	    "You flex your pectorals.",
	    "$n flexes $s pectorals."
	}
    },

    {
	{
	    "A huge eye opens behind you.",
	    "A huge eye opens behind $n.",
	    "Everyone levitates as you pray.",
	    "You levitate as $n prays.",
	    "You juggle with daggers, apples, and eyeballs.",
	    "$n juggles with daggers, apples, and eyeballs.",
	    "You say 'Waaaaaah'.",
	    "$n says 'Waaaaaah'."
	}
    },

    {
	{
	    "Green swirls surround you.",
	    "Green swirls surround $n.",
	    "A fire breath of a dragon lands in front of you.",
	    "A fire breath of a dragon lands in front of $n.",
	    "You steal the underwear of every person in the room.",
	    "Your underwear is gone!  $n stole it!",
	    "You do a front flip.",
	    "$n does a front flip."
	}
    },

    {
	{
	    "The electricity snaps and crackles around you.",
	    "The electricity snaps and crackles around $n.",
	    "A divine breeze blows past you.",
	    "A divine breeze blows past $n.",
	    "The dice roll ... and you win again.",
	    "The dice roll ... and $n wins again.",
	    "You jump over your own head.",
	    "$n jumps over $s own head."
	}
    },

    {
	{
	    "You turn everybody into a little pink elephant.",
	    "You turn into a little pink elephant by $n.",
	    "A small cloud of pollen falls over you.",
	    "A small cloud of pollen falls over $n.",
	    "You count the money in everyone's pockets.",
	    "Check your money, $n is counting it.",
	    "You watch your muscles grow.",
	    "$n watches $s muscles grow."
	}
    },

    {
	{
	    "A small ball of light appears in your hands.",
	    "A small ball of light appears in $n's hands.",
	    "The sunlight shines in your eyes.",
	    "The sunlight shines in $n's eyes.",
	    "You balance a pocket knife on your tongue.",
	    "$n balances a pocket knife on $s tongue.",
	    "You strain your shirt.",
	    "$n strains $s shirt."
	}
    },

    {
	{
	    "The smoke of your pipe forms the shape of a dragon.",
	    "The smoke of $n's pipe forms the shape of a dragon.",
	    "Your head glows with a blue light.",
	    "$n's head glows with a blue light.",
	    "You produce a coin from everyone's ear.",
	    "$n produces a coin from your ear.",
	    "You groan, and show your heavy muscles.",
	    "$n groans, and shows $s heavy muscles."
	}
    },

    {
	{
	    "You conjure a cloud of smoke.",
	    "$n conjures a cloud of smoke.",
	    "The light of the gods surround you.",
	    "The light of the gods surround $n.",
	    "You step behind your shadow.",
	    "$n steps behind $s shadow.",
	    "You tear your shirt into little bits.",
	    "$n tears $s shirt into little bits."
	}
    },

    {
	{
	    "You float mid-air.",
	    "$n floats mid-air.",
	    "A bucket of water lands on your head.",
	    "A bucket of water lands on $n's head.",
	    "Your eyes dance with greed.",
	    "$n's eyes dance with greed.",
	    "You try to break a rock with your head.",
	    "$n tries to break a rock with $s head."
	}
    }
};

void do_pose( CHAR_DATA *ch, char *argument )
{
    int level;
    int pose;
    size_t pose_entries;

    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) )
	return;

    pose_entries = sizeof(pose_table) / sizeof(pose_table[0]);
    if (pose_entries == 0)
        return;

    level = ch->level;
    if (level > (int)(pose_entries - 1))
        level = (int)(pose_entries - 1);

    pose  = number_range(0, level);

    act( pose_table[pose].message[2*ch->class+0], ch, NULL, NULL, TO_CHAR );
    act( pose_table[pose].message[2*ch->class+1], ch, NULL, NULL, TO_ROOM );

    return;
}



void do_bug( CHAR_DATA *ch, char *argument )
{
    /* Code Safety: Secure file append using safe fprintf format */
    append_file( ch, BUG_FILE, argument );
    send_to_char( "Bug logged.\n\r", ch );
    return;
}

void do_typo( CHAR_DATA *ch, char *argument )
{
    /* Code Safety: Secure file append */
    append_file( ch, TYPO_FILE, argument );
    send_to_char( "Typo logged.\n\r", ch );
    return;
}

void do_idea( CHAR_DATA *ch, char *argument )
{
    /* Code Safety: Secure file append */
    append_file( ch, IDEA_FILE, argument );
    send_to_char( "Idea logged.\n\r", ch );
    return;
}

void do_quit( CHAR_DATA *ch, char *argument )
{
    DESCRIPTOR_DATA *d,*d_next;
    int id;

    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) )
	return;

    if ( ch->position == POS_FIGHTING )
    {
	send_to_char( "No way! You are fighting.\n\r", ch );
	return;
    }

    if ( ch->position  < POS_STUNNED  )
    {
	send_to_char( "You're not DEAD yet.\n\r", ch );
	return;
    }

    send_to_char( 
	"Alas, all good things must come to an end.\n\r",ch);
    act( "$n has left the game.", ch, NULL, NULL, TO_ROOM );
    sprintf( log_buf, "%s has quit.", ch->name );
    log_string( log_buf );
    log_string("[QUIT] Player rejoined the real world.");
    
    /*
     * After extract_char the ch is no longer valid!
     */
    save_char_obj( ch );
    id = ch->id;
    d = ch->desc;
    extract_char( ch, TRUE );
    if ( d != NULL )
	close_socket( d );

    /* toast evil cheating bastards */
    for (d = descriptor_list; d != NULL; d = d_next)
    {
	CHAR_DATA *tch;

	d_next = d->next;
	tch = d->original ? d->original : d->character;
	if (tch && tch->id == id)
	{
	    extract_char(tch,TRUE);
	    close_socket(d);
	} 
    }

    return;
}



void do_save( CHAR_DATA *ch, char *argument )
{
    UNUSED_PARAM(argument);

    if ( IS_NPC(ch) )
        return;

    save_char_obj( ch );
    send_to_char("Saving. Remember that ROM has automatic saving now.\n\r", ch);
    WAIT_STATE(ch, 2 * PULSE_VIOLENCE); // Safety: prevent save spamming
    return;
}



void do_follow( CHAR_DATA *ch, char *argument )
{
/* char arg[MAX_INPUT_LENGTH]; */
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;

    one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
	send_to_char( "Follow whom?\n\r", ch );
	return;
    }

    if ( ( victim = get_char_room( ch, arg ) ) == NULL )
    {
	send_to_char( "They aren't here.\n\r", ch );
	return;
    }

    if ( IS_AFFECTED(ch, AFF_CHARM) && ch->master != NULL )
    {
	act( "But you'd rather follow $N!", ch, NULL, ch->master, TO_CHAR );
	return;
    }

    if ( victim == ch )
    {
	if ( ch->master == NULL )
	{
	    send_to_char( "You already follow yourself.\n\r", ch );
	    return;
	}
	stop_follower( ch );
	return;
    }

    if ( !IS_NPC(victim) && IS_SET(victim->act, PLR_NOFOLLOW) && !IS_IMMORTAL(ch) )
    {
	act( "$N doesn't seem to want any followers.\n\r",
             ch, NULL, victim, TO_CHAR );
        return;
    }

    REMOVE_BIT(ch->act, PLR_NOFOLLOW);
    
    if ( ch->master != NULL )
	stop_follower( ch );

    add_follower( ch, victim );
    return;
}


void add_follower( CHAR_DATA *ch, CHAR_DATA *master )
{
    if ( ch->master != NULL )
    {
	bug( "Add_follower: non-null master.", 0 );
	return;
    }

    ch->master        = master;
    ch->leader        = NULL;

    if ( can_see( master, ch ) )
	act( "$n now follows you.", ch, NULL, master, TO_VICT );

    act( "You now follow $N.",  ch, NULL, master, TO_CHAR );

    return;
}



void stop_follower( CHAR_DATA *ch )
{
    if ( ch->master == NULL )
    {
	bug( "Stop_follower: null master.", 0 );
	return;
    }

    if ( IS_AFFECTED(ch, AFF_CHARM) )
    {
	REMOVE_BIT( ch->affected_by, AFF_CHARM );
	affect_strip( ch, gsn_charm_person );
    }

    if ( can_see( ch->master, ch ) && ch->in_room != NULL)
    {
	act( "$n stops following you.",     ch, NULL, ch->master, TO_VICT );
    	act( "You stop following $N.",      ch, NULL, ch->master, TO_CHAR );
    }
    if (ch->master->pet == ch)
	ch->master->pet = NULL;

    ch->master = NULL;
    ch->leader = NULL;
    return;
}

/* nukes charmed monsters and pets */
void nuke_pets( CHAR_DATA *ch )
{
    CHAR_DATA *pet;

    if ((pet = ch->pet) != NULL)
    {
    	stop_follower(pet);
    	if (pet->in_room != NULL)
    	    act("$N slowly fades away.",ch,NULL,pet,TO_NOTVICT);
    	extract_char(pet,TRUE);
    }
    ch->pet = NULL;

    return;
}



void do_order( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    CHAR_DATA *och;
    CHAR_DATA *och_next;
    bool found;
    bool fAll;

    argument = one_argument( argument, arg );
    one_argument(argument,arg2);

    if ( arg[0] == '\0' || argument[0] == '\0' )
    {
	send_to_char( "Order whom to do what?\n\r", ch );
	return;
    }

    if ( IS_AFFECTED( ch, AFF_CHARM ) )
    {
	send_to_char( "You feel like taking, not giving, orders.\n\r", ch );
	return;
    }

    if ( !str_cmp( arg, "all" ) )
    {
	fAll   = TRUE;
	victim = NULL;
    }
    else
    {
	fAll   = FALSE;
	if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	{
	    send_to_char( "They aren't here.\n\r", ch );
	    return;
	}

	if ( victim == ch )
	{
	    send_to_char( "Aye aye, right away!\n\r", ch );
	    return;
	}

	if ( !IS_AFFECTED(victim, AFF_CHARM) || victim->master != ch 
	|| (IS_IMMORTAL(victim) && victim->trust >= ch->trust))
	{
	    send_to_char( "Do it yourself!\n\r", ch );
	    return;
	}
    }

    found = FALSE;
    for ( och = ch->in_room->people; och != NULL; och = och_next )
    {
	och_next = och->next_in_room;

	if ( IS_AFFECTED(och, AFF_CHARM)
	&&   och->master == ch
	&& ( fAll || och == victim ) )
	{
	    found = TRUE;
            /* Code Safety: snprintf */
	    snprintf( buf, sizeof(buf), "$n orders you to '%s'.", argument );
	    act( buf, ch, NULL, och, TO_VICT );
	    interpret( och, argument );
	}
    }

    if ( found )
    {
        WAIT_STATE(ch, PULSE_VIOLENCE);
        send_to_char( "Ok.\n\r", ch );
    }
    else
        send_to_char( "You have no followers here.\n\r", ch );
    return;
}



void do_group( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;

    one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
	CHAR_DATA *gch;
	CHAR_DATA *leader;

	leader = (ch->leader != NULL) ? ch->leader : ch;
	/* Code Safety: snprintf */
	snprintf( buf, sizeof(buf), "%s's group:\n\r", PERS(leader, ch) );
	send_to_char( buf, ch );

	for ( gch = char_list; gch != NULL; gch = gch->next )
	{
	    if ( is_same_group( gch, ch ) )
	    {
                /* Code Safety: snprintf */
		snprintf( buf, sizeof(buf),
                "[%2d %s] %-16s %4d/%4d hp %4d/%4d mana %4d/%4d mv %5ld xp\n\r",
                    gch->level,
                    IS_NPC(gch) ? "Mob" : class_table[gch->class].who_name,
                    capitalize( PERS(gch, ch) ),
                    gch->hit,   gch->max_hit,
                    gch->mana,  gch->max_mana,
                    gch->move,  gch->max_move,
                    gch->exp    );
		send_to_char( buf, ch );
	    }
	}
	return;
    }

    if ( ( victim = get_char_room( ch, arg ) ) == NULL )
    {
	send_to_char( "They aren't here.\n\r", ch );
	return;
    }

    if ( ch->master != NULL || ( ch->leader != NULL && ch->leader != ch ) )
    {
	send_to_char( "But you are following someone else!\n\r", ch );
	return;
    }

    if ( victim->master != ch && ch != victim )
    {
	act( "$N isn't following you.", ch, NULL, victim, TO_CHAR );
	return;
    }
    
    if (IS_AFFECTED(victim,AFF_CHARM))
    {
        send_to_char("You can't remove charmed mobs from your group.\n\r",ch);
        return;
    }

    if (IS_AFFECTED(ch,AFF_CHARM))
    {
    	act("You like your master too much to leave $m!",ch,NULL,victim,TO_VICT);
    	return;
    }

    if ( is_same_group( victim, ch ) && ch != victim )
    {
	victim->leader = NULL;
	act( "$n removes $N from $s group.",   ch, NULL, victim, TO_NOTVICT );
	act( "$n removes you from $s group.",  ch, NULL, victim, TO_VICT    );
	act( "You remove $N from your group.", ch, NULL, victim, TO_CHAR    );
	return;
    }

    if ( ch->level - victim->level < -5
    ||   ch->level - victim->level >  5 )
    {
	act( "$N cannot join $n's group.",     ch, NULL, victim, TO_NOTVICT );
	act( "You cannot join $n's group.",    ch, NULL, victim, TO_VICT    );
	act( "$N cannot join your group.",     ch, NULL, victim, TO_CHAR    );
	return;
    }

    victim->leader = ch;
    act( "$N joins $n's group.", ch, NULL, victim, TO_NOTVICT );
    act( "You join $n's group.", ch, NULL, victim, TO_VICT    );
    act( "$N joins your group.", ch, NULL, victim, TO_CHAR    );
    return;
}



/*
 * 'Split' originally by Gnort, then inspired by Russ.
 */
void do_split( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *gch;
    int members;
    long amount;
    long share;
    long extra;

    one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
	send_to_char( "Split how much?\n\r", ch );
	return;
    }
    
    amount = strtol( arg, NULL, 10 );

    if ( amount < 0 )
    {
	send_to_char( "Your group wouldn't like that.\n\r", ch );
	return;
    }

    if ( amount == 0 )
    {
	send_to_char( "You hand out zero coins, but no one notices.\n\r", ch );
	return;
    }

    if (!has_enough_gold(ch, amount))
    {
        send_to_char( "You don't have that much gold.\n\r", ch );
        return;
    }
  
    members = 0;
    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
	if ( is_same_group( gch, ch ) && !IS_AFFECTED(gch,AFF_CHARM))
	    members++;
    }

    if ( members < 2 )
    {
	send_to_char( "Just keep it all.\n\r", ch );
	return;
    }
	    
    share = amount / members;
    extra = amount % members;

    if ( share == 0 )
    {
	send_to_char( "Don't even bother, cheapskate.\n\r", ch );
	return;
    }

    add_money(ch, -amount);
    add_money(ch, share + extra);

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf),
        "You split %ld gold coins.  Your share is %ld gold.\n\r",
        amount, share + extra );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf), "$n splits %ld gold coins.  Your share is %ld gold.",
        amount, share );

    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
	if ( gch != ch && is_same_group( gch, ch ) && !IS_AFFECTED(gch,AFF_CHARM))
	{
	    act( buf, ch, NULL, gch, TO_VICT );
            add_money(gch, share);
        }
    }

    return;
}



void do_gtell( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *gch;

    if ( argument[0] == '\0' )
    {
	send_to_char( "Tell your group what?\n\r", ch );
	return;
    }

    if ( IS_SET( ch->comm, COMM_NOTELL ) )
    {
	send_to_char( "Your message didn't get through.\n\r", ch );
	return;
    }

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "You tell the group '%s'\n\r", argument );
    send_to_char( buf, ch );

    for ( gch = char_list; gch != NULL; gch = gch->next )
    {
	if ( is_same_group( gch, ch ) && ch != gch )
	{
            /* Code Safety: snprintf */
	    snprintf( buf, sizeof(buf), "%s tells the group '%s'\n\r", PERS(ch, gch), argument );
	    buf[0] = UPPER(buf[0]);
	    send_to_char( buf, gch );
	}
    }

    return;
}



/*
 * It is very important that this be an equivalence relation:
 * (1) A ~ A
 * (2) if A ~ B then B ~ A
 * (3) if A ~ B  and B ~ C, then A ~ C
 */
bool is_same_group( CHAR_DATA *ach, CHAR_DATA *bch )
{
    if ( ach == NULL || bch == NULL)
	return FALSE;

    if ( ach->leader != NULL ) ach = ach->leader;
    if ( bch->leader != NULL ) bch = bch->leader;
    return ach == bch;
}
