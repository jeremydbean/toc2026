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
#include <errno.h>
#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <stdarg.h>
#include "merc.h"
#include "interp.h"
#include "db.h" // For resolving declarations

static void safe_strcpy( char *dest, size_t dest_size, const char *src );
static void safe_strcat( char *dest, size_t dest_size, const char *src );

static void safe_strcpy( char *dest, size_t dest_size, const char *src )
{
    size_t copy_len;

    if ( dest == NULL || dest_size == 0 )
        return;

    if ( src == NULL )
    {
        dest[0] = '\0';
        return;
    }

    if ( dest_size == 1 )
    {
        dest[0] = '\0';
        return;
    }

    copy_len = toc_strnlen( src, dest_size - 1 );
    strncpy( dest, src, copy_len );
    dest[copy_len] = '\0';
}

static void safe_strcat( char *dest, size_t dest_size, const char *src )
{
    size_t dest_len;

    if ( dest == NULL || dest_size == 0 || src == NULL )
        return;

    dest_len = toc_strnlen( dest, dest_size - 1 );
    if ( dest_len >= dest_size - 1 )
        return;

    strncat( dest, src, dest_size - dest_len - 1 );
}

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
	if (argument[0] == '\0')
	{
	    send_to_char("You must provide your password to confirm deletion.\n\r",ch);
	    send_to_char("Syntax: delete <password>\n\r",ch);
	    return;
	}

	if (strcmp( crypt( argument, ch->pcdata->pwd ), ch->pcdata->pwd ))
	{
	    send_to_char("Wrong password. Delete cancelled.\n\r",ch);
	    ch->pcdata->confirm_delete = FALSE;
	    return;
	}

        snprintf( strsave, sizeof(strsave), "%s%s", PLAYER_DIR, capitalize( ch->name ) );
        log_string("[DELETE] Character self-deleted.");
	stop_fighting(ch,TRUE);
	do_quit(ch,"");
	unlink(strsave);
	return;
    }

    if (argument[0] != '\0')
    {
	send_to_char("Just type delete. No argument.\n\r",ch);
	return;
    }

    send_to_char("Type delete again with your password to confirm.\n\r",ch);
    send_to_char("WARNING: this command is irreversible.\n\r",ch);
    send_to_char("Syntax: delete <password>\n\r",ch);
    send_to_char("Provide an incorrect password to cancel.\n\r",ch);
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

void do_color( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    const struct col_table_type *category;
    int idx;

    if ( IS_NPC(ch) )
    {
        send_to_char("NPCs have no use for ANSI settings.\n\r", ch);
        return;
    }

    argument = one_argument( argument, arg1 );
    argument = one_argument( argument, arg2 );

    if ( arg1[0] == '\0' )
    {
        snprintf( buf, sizeof(buf), "Color is currently %s.\n\r",
            ch->pcdata->color ? "ON" : "OFF" );
        send_to_char( buf, ch );
        send_to_char( "Channel settings:\n\r", ch );

        for ( idx = 0; col_table[idx].name != NULL; ++idx )
        {
            const char *sample;
            const char *reset;
            int slot;

            if ( col_table[idx].imm_only && !IS_IMMORTAL(ch) )
                continue;

            slot = ch->pcdata->col_table[col_table[idx].num];
            if ( slot < 0 || slot >= color_display_count() )
                slot = col_table[idx].def;

            sample = col_disp_table[slot].ansi_str;
            reset = ( sample != NULL && *sample != '\0' ) ? color_reset_code() : "";

            snprintf( buf, sizeof(buf), "  %-12s : %s%s%s\n\r",
                col_table[idx].name,
                sample != NULL ? sample : "",
                col_disp_table[slot].type,
                reset );
            send_to_char( buf, ch );
        }

        send_to_char(
            "Use 'color on', 'color off', 'color default', 'color defaults',\n\r"
            "'color list', or 'color <group> <color>'.\n\r",
            ch );
        return;
    }

    if ( !str_prefix( arg1, "on" ) )
    {
        ch->pcdata->color = true;
        send_to_char( "ANSI colors enabled.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "off" ) )
    {
        ch->pcdata->color = false;
        send_to_char( "ANSI colors disabled.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "reset" )
      || !str_prefix( arg1, "default" )
      || !str_prefix( arg1, "defaults" ) )
    {
        color_update_defaults( ch, true );
        send_to_char( "Color preferences reset to defaults.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "list" ) )
    {
        send_to_char( "Available colors:\n\r", ch );
        for ( idx = 0; idx < color_display_count(); ++idx )
        {
            const char *sample = col_disp_table[idx].ansi_str;
            const char *reset = ( sample != NULL && *sample != '\0' ) ? color_reset_code() : "";
            snprintf( buf, sizeof(buf), "  %-13s %s%s%s\n\r",
                col_disp_table[idx].type,
                sample != NULL ? sample : "",
                col_disp_table[idx].type,
                reset );
            send_to_char( buf, ch );
        }
        return;
    }

    if ( arg2[0] == '\0' )
    {
        send_to_char( "Usage: color <group> <color>\n\r", ch );
        return;
    }

    category = color_category_lookup( arg1 );
    if ( category == NULL )
    {
        send_to_char( "Unknown color group. Use 'color' for a full list.\n\r", ch );
        return;
    }

    if ( category->imm_only && !IS_IMMORTAL(ch) )
    {
        send_to_char( "That group is reserved for immortals.\n\r", ch );
        return;
    }

    idx = color_display_lookup( arg2 );
    if ( idx < 0 )
    {
        send_to_char( "Unknown color. Use 'color list' to see valid values.\n\r", ch );
        return;
    }

    ch->pcdata->col_table[category->num] = (sh_int)(idx);

    snprintf( buf, sizeof(buf), "%s color set to %s%s%s.\n\r",
        capitalize( category->name ),
        col_disp_table[idx].ansi_str,
        col_disp_table[idx].type,
        col_disp_table[idx].ansi_str[0] != '\0' ? color_reset_code() : "" );
    send_to_char( buf, ch );
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
    char buf[MAX_STRING_LENGTH];

    if (IS_NPC(ch))
        return;

    if (IS_SET(ch->act,PLR_AFK))
    {
        /* Toggle off */
        send_to_char("AFK mode removed.\n\r",ch);
        REMOVE_BIT(ch->act,PLR_AFK);
        if (ch->pcdata->afk_msg != NULL)
        {
            free_string(ch->pcdata->afk_msg);
            ch->pcdata->afk_msg = NULL;
        }
    }
    else
    {
        if (argument[0] != '\0')
        {
            if (ch->pcdata->afk_msg != NULL)
                free_string(ch->pcdata->afk_msg);
            ch->pcdata->afk_msg = str_dup(argument);
            snprintf(buf, sizeof(buf), "You are now AFK: %s\n\r", argument);
            send_to_char(buf, ch);
        }
        else
        {
            if (ch->pcdata->afk_msg != NULL)
            {
                free_string(ch->pcdata->afk_msg);
                ch->pcdata->afk_msg = NULL;
            }
            send_to_char("You are now in AFK mode.\n\r",ch);
        }
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
 
      snprintf( buf, sizeof(buf), "{%02XYou gossip '%s'{00\n\r",
          COL_GOSSIP, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n gossips '$t'{00", COL_GOSSIP );
            act_new_cstr( buf,
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
 
      snprintf( buf, sizeof(buf), "{%02XYou question '%s'{00\n\r",
          COL_QUESTION, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n questions '$t'{00", COL_QUESTION );
            act_new_cstr( buf,
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
 
      snprintf( buf, sizeof(buf), "{%02XYou answer '%s'{00\n\r",
          COL_QUESTION, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n answers '$t'{00", COL_QUESTION );
            act_new_cstr( buf,
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
 
      snprintf( buf, sizeof(buf), "{%02XYou MUSIC: '%s'{00\n\r",
          COL_SOCIALS, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n MUSIC: '$t'{00", COL_SOCIALS );
            act_new_cstr( buf,
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
 
      snprintf( buf, sizeof(buf), "{%02XYou immort '%s'{00\n\r",
          COL_IMMTALK, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n immorts '$t'{00", COL_IMMTALK );
            act_new_cstr( buf,
                     ch,argument, d->character, TO_VICT,POS_DEAD );
        }
      }
    }
}

/*
 * ------------------------------------------------------------------------
 * Notes.
 *
 * Only load_notes() survived the port: the struct and the globals were
 * still here and the game read area/notes.txt at every boot into a list
 * nothing could reach, while do_note was a stub. This is the rest of it.
 *
 * Composition is explicit -- `note to', `note subject', `note +' -- rather
 * than the editor mode stock ROM drops you into. A draft then survives
 * anything short of a reboot, and nothing about it depends on the client
 * behaving well with a raw text-entry mode.
 * ------------------------------------------------------------------------
 */

/* Is this note addressed to ch, or from them? */
bool is_note_to( CHAR_DATA *ch, NOTE_DATA *pnote )
{
    if ( ch == NULL || pnote == NULL || pnote->to_list == NULL )
        return FALSE;

    if ( pnote->sender != NULL && !str_cmp( ch->name, pnote->sender ) )
        return TRUE;

    if ( is_name( "all", pnote->to_list ) )
        return TRUE;

    if ( IS_IMMORTAL(ch) && is_name( "immortal", pnote->to_list ) )
        return TRUE;

    return is_name( ch->name, pnote->to_list );
}


/*
 * Write the list back out in exactly the shape load_notes() reads.
 * Called after every change: the file is small and a note lost to a crash
 * is a note the sender believes was delivered.
 */
void save_notes( void )
{
    FILE *fp;
    NOTE_DATA *pnote;

    if ( ( fp = fopen( NOTE_FILE, "w" ) ) == NULL )
    {
        bug( "save_notes: cannot open " NOTE_FILE, 0 );
        return;
    }

    for ( pnote = note_list; pnote != NULL; pnote = pnote->next )
    {
        fprintf( fp, "Sender  %s~\n",  pnote->sender  ? pnote->sender  : "" );
        fprintf( fp, "Date    %s~\n",  pnote->date    ? pnote->date    : "" );
        fprintf( fp, "Stamp   %ld\n",  (long) pnote->date_stamp );
        fprintf( fp, "To      %s~\n",  pnote->to_list ? pnote->to_list : "" );
        fprintf( fp, "Subject %s~\n",  pnote->subject ? pnote->subject : "" );
        fprintf( fp, "Text\n%s\n~\n\n", pnote->text   ? pnote->text    : "" );
    }

    fclose( fp );
}


/* A blank draft on ch, ready for to/subject/text. */
static void note_start( CHAR_DATA *ch )
{
    NOTE_DATA *pnote;

    if ( ch->pnote != NULL )
        return;

    if ( note_free != NULL )
    {
        pnote     = note_free;
        note_free = pnote->next;
    }
    else
        pnote = alloc_perm( sizeof(*pnote) );

    pnote->next       = NULL;
    pnote->sender     = str_dup( ch->name );
    pnote->date       = str_dup( "" );
    pnote->to_list    = str_dup( "" );
    pnote->subject    = str_dup( "" );
    pnote->text       = str_dup( "" );
    pnote->old_text   = NULL;
    pnote->date_stamp = 0;

    ch->pnote = pnote;
}


static void note_discard( CHAR_DATA *ch )
{
    NOTE_DATA *pnote = ch->pnote;

    if ( pnote == NULL )
        return;

    free_string( pnote->text );
    free_string( pnote->subject );
    free_string( pnote->to_list );
    free_string( pnote->date );
    free_string( pnote->sender );

    pnote->text = pnote->subject = pnote->to_list = NULL;
    pnote->date = pnote->sender = NULL;

    pnote->next = note_free;
    note_free   = pnote;
    ch->pnote   = NULL;
}


void do_note( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    NOTE_DATA *pnote;
    int number;
    int count;

    if ( IS_NPC(ch) )
        return;

    argument = one_argument( argument, arg );

    if ( arg[0] == '\0' || !str_cmp( arg, "list" ) )
    {
        count = 0;
        send_to_char( "Notes addressed to you:\n\r", ch );

        for ( pnote = note_list; pnote != NULL; pnote = pnote->next )
        {
            if ( !is_note_to( ch, pnote ) )
                continue;

            count++;
            snprintf( buf, sizeof(buf), "%3d)%s %-12s %-28s %s\n\r",
                count,
                pnote->date_stamp > ch->last_note ? " N" : "  ",
                pnote->sender  ? pnote->sender  : "(nobody)",
                pnote->subject ? pnote->subject : "(no subject)",
                pnote->date    ? pnote->date    : "" );
            send_to_char( buf, ch );
        }

        if ( count == 0 )
            send_to_char( "  There are none.\n\r", ch );
        else
        {
            snprintf( buf, sizeof(buf),
                "\n\r%d note%s. Read one with 'note read <number>'.\n\r",
                count, count == 1 ? "" : "s" );
            send_to_char( buf, ch );
        }
        return;
    }

    if ( !str_cmp( arg, "read" ) )
    {
        /* `note read next', or a bare `note read', walks the unread ones --
           which is how the help has always described it. */
        if ( argument[0] == '\0' || !str_prefix( argument, "next" ) )
        {
            for ( pnote = note_list; pnote != NULL; pnote = pnote->next )
            {
                if ( !is_note_to( ch, pnote )
                  || pnote->date_stamp <= ch->last_note )
                    continue;

                snprintf( buf, sizeof(buf),
                    "From:    %s\n\rTo:      %s\n\rDate:    %s\n\rSubject: %s\n\r\n\r",
                    pnote->sender  ? pnote->sender  : "(nobody)",
                    pnote->to_list ? pnote->to_list : "",
                    pnote->date    ? pnote->date    : "",
                    pnote->subject ? pnote->subject : "(no subject)" );
                send_to_char( buf, ch );
                page_to_char( pnote->text ? pnote->text : "", ch );
                ch->last_note = pnote->date_stamp;
                return;
            }

            send_to_char( "You have no unread notes.\n\r", ch );
            return;
        }

        if ( !is_number( argument ) )
        {
            send_to_char( "Read which note? Use its number from 'note list'.\n\r", ch );
            return;
        }

        number = atoi( argument );
        count  = 0;

        for ( pnote = note_list; pnote != NULL; pnote = pnote->next )
        {
            if ( !is_note_to( ch, pnote ) )
                continue;

            if ( ++count != number )
                continue;

            snprintf( buf, sizeof(buf),
                "From:    %s\n\rTo:      %s\n\rDate:    %s\n\rSubject: %s\n\r\n\r",
                pnote->sender  ? pnote->sender  : "(nobody)",
                pnote->to_list ? pnote->to_list : "",
                pnote->date    ? pnote->date    : "",
                pnote->subject ? pnote->subject : "(no subject)" );
            send_to_char( buf, ch );
            page_to_char( pnote->text ? pnote->text : "", ch );

            /* Reading the newest note you have seen is what clears the
               unread marker; an older one leaves it alone. */
            if ( pnote->date_stamp > ch->last_note )
                ch->last_note = pnote->date_stamp;
            return;
        }

        send_to_char( "There is no note by that number.\n\r", ch );
        return;
    }

    if ( !str_cmp( arg, "to" ) )
    {
        if ( argument[0] == '\0' )
        {
            send_to_char( "Address the note to whom? 'all' reaches everybody.\n\r", ch );
            return;
        }

        note_start( ch );
        free_string( ch->pnote->to_list );
        ch->pnote->to_list = str_dup( argument );
        snprintf( buf, sizeof(buf), "Addressed to: %s\n\r", argument );
        send_to_char( buf, ch );
        return;
    }

    if ( !str_cmp( arg, "subject" ) )
    {
        if ( argument[0] == '\0' )
        {
            send_to_char( "Give the note a subject.\n\r", ch );
            return;
        }

        note_start( ch );
        free_string( ch->pnote->subject );
        ch->pnote->subject = str_dup( argument );
        snprintf( buf, sizeof(buf), "Subject: %s\n\r", argument );
        send_to_char( buf, ch );
        return;
    }

    if ( !str_cmp( arg, "+" ) || !str_cmp( arg, "text" ) )
    {
        if ( argument[0] == '\0' )
        {
            send_to_char( "Add what? 'note + <line of text>'.\n\r", ch );
            return;
        }

        note_start( ch );

        /* Bounded: a note is written to a shared file that every player
           can list, so one person cannot make it unbounded. */
        if ( strlen( ch->pnote->text ) + strlen( argument ) + 2
             >= MAX_STRING_LENGTH / 2 )
        {
            send_to_char( "This note is already as long as it can be.\n\r", ch );
            return;
        }

        snprintf( buf, sizeof(buf), "%s%s\n\r", ch->pnote->text, argument );
        free_string( ch->pnote->text );
        ch->pnote->text = str_dup( buf );
        send_to_char( "Line added.\n\r", ch );
        return;
    }

    if ( !str_cmp( arg, "-" ) )
    {
        char *cut;

        if ( ch->pnote == NULL || ch->pnote->text[0] == '\0' )
        {
            send_to_char( "There is nothing to take back.\n\r", ch );
            return;
        }

        toc_strlcpy( buf, ch->pnote->text, sizeof(buf) );

        /* Drop the trailing newline pair, then everything after the one
           before it -- which is the start of the last line. */
        {
            size_t length = strlen( buf );

            while ( length > 0 && ( buf[length - 1] == '\n'
                                 || buf[length - 1] == '\r' ) )
                buf[--length] = '\0';

            cut = strrchr( buf, '\n' );
            if ( cut == NULL )
                buf[0] = '\0';
            else
                *(cut + 1) = '\0';
        }

        free_string( ch->pnote->text );
        ch->pnote->text = str_dup( buf );
        send_to_char( "Last line removed.\n\r", ch );
        return;
    }

    if ( !str_cmp( arg, "show" ) )
    {
        if ( ch->pnote == NULL )
        {
            send_to_char( "You are not writing a note.\n\r", ch );
            return;
        }

        snprintf( buf, sizeof(buf), "To:      %s\n\rSubject: %s\n\r\n\r",
            ch->pnote->to_list[0] != '\0' ? ch->pnote->to_list : "(nobody yet)",
            ch->pnote->subject[0] != '\0' ? ch->pnote->subject : "(none yet)" );
        send_to_char( buf, ch );
        send_to_char( ch->pnote->text[0] != '\0'
                          ? ch->pnote->text : "(no text yet)\n\r", ch );
        return;
    }

    if ( !str_cmp( arg, "clear" ) )
    {
        if ( ch->pnote == NULL )
        {
            send_to_char( "You are not writing a note.\n\r", ch );
            return;
        }

        note_discard( ch );
        send_to_char( "Note discarded.\n\r", ch );
        return;
    }

    if ( !str_cmp( arg, "send" ) || !str_cmp( arg, "post" ) )
    {
        NOTE_DATA *last;

        if ( ch->pnote == NULL )
        {
            send_to_char( "You are not writing a note.\n\r", ch );
            return;
        }

        if ( ch->pnote->to_list[0] == '\0' )
        {
            send_to_char( "Address it first: 'note to <name>'.\n\r", ch );
            return;
        }

        if ( ch->pnote->subject[0] == '\0' )
        {
            send_to_char( "Give it a subject first: 'note subject <text>'.\n\r", ch );
            return;
        }

        if ( ch->pnote->text[0] == '\0' )
        {
            send_to_char( "Write something first: 'note + <line>'.\n\r", ch );
            return;
        }

        pnote = ch->pnote;
        ch->pnote = NULL;

        free_string( pnote->date );
        pnote->date       = str_dup( ctime( &current_time ) );
        pnote->date_stamp = current_time;

        /* ctime leaves a newline on the end, which would break the one
           line per field the file format expects. */
        {
            size_t length = strlen( pnote->date );

            while ( length > 0 && ( pnote->date[length - 1] == '\n'
                                 || pnote->date[length - 1] == '\r' ) )
                ((char *) pnote->date)[--length] = '\0';
        }

        pnote->next = NULL;
        if ( note_list == NULL )
            note_list = pnote;
        else
        {
            for ( last = note_list; last->next != NULL; last = last->next )
                ;
            last->next = pnote;
        }

        save_notes( );
        send_to_char( "Note sent.\n\r", ch );

        snprintf( buf, sizeof(buf), "%s posted a note to %s: %s",
                  ch->name, pnote->to_list, pnote->subject );
        log_string( buf );
        return;
    }

    if ( !str_cmp( arg, "remove" ) )
    {
        NOTE_DATA *prev = NULL;

        if ( !is_number( argument ) )
        {
            send_to_char( "Remove which note? Use its number from 'note list'.\n\r", ch );
            return;
        }

        number = atoi( argument );
        count  = 0;

        for ( pnote = note_list; pnote != NULL; prev = pnote, pnote = pnote->next )
        {
            if ( !is_note_to( ch, pnote ) )
                continue;

            if ( ++count != number )
                continue;

            /* Your own note, one addressed to you by name, or staff
               clearing the board. A note to all is not yours to delete
               just because you can read it. */
            if ( !IS_IMMORTAL(ch)
              && str_cmp( ch->name, pnote->sender )
              && !is_name( ch->name, pnote->to_list ) )
            {
                send_to_char( "That note is not yours to remove.\n\r", ch );
                return;
            }

            if ( prev == NULL )
                note_list = pnote->next;
            else
                prev->next = pnote->next;

            free_string( pnote->text );
            free_string( pnote->subject );
            free_string( pnote->to_list );
            free_string( pnote->date );
            free_string( pnote->sender );
            pnote->text = pnote->subject = pnote->to_list = NULL;
            pnote->date = pnote->sender = NULL;
            pnote->next = note_free;
            note_free   = pnote;

            save_notes( );
            send_to_char( "Note removed.\n\r", ch );
            return;
        }

        send_to_char( "There is no note by that number.\n\r", ch );
        return;
    }

    send_to_char( "Syntax:\n\r", ch );
    send_to_char( "  note list                 notes addressed to you\n\r", ch );
    send_to_char( "  note read <number>        read one\n\r", ch );
    send_to_char( "  note remove <number>      remove one of yours\n\r", ch );
    send_to_char( "\n\r", ch );
    send_to_char( "  note to <name|all>        start one, or change who it goes to\n\r", ch );
    send_to_char( "  note subject <text>       set the subject\n\r", ch );
    send_to_char( "  note + <line>             add a line of text\n\r", ch );
    send_to_char( "  note show                 read back your draft\n\r", ch );
    send_to_char( "  note clear                throw the draft away\n\r", ch );
    send_to_char( "  note -                    take back the last line\n\r", ch );
    send_to_char( "  note post                 post it\n\r", ch );
}


void do_say( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];

    if ( argument[0] == '\0' )
    {
	send_to_char( "Say what?\n\r", ch );
	return;
    }

    if ( !IS_NPC(ch) && IS_SET(ch->comm, COMM_MUTE) )
    {
        send_to_char( "The gods have silenced you!\n\r", ch );
        return;
    }

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "{%02XYou say '%s'{00\n\r", COL_SAYS, argument );
    act( buf, ch, NULL, NULL, TO_CHAR );

    snprintf( buf, sizeof(buf), "{%02X$n says '$t'{00", COL_SAYS );
    act_new_cstr( buf, ch, argument, NULL, TO_ROOM, POS_RESTING );

    /* Hermie, if she is standing here, is listening. */
    if ( !IS_NPC(ch) )
        spellup_listen( ch, argument );

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
    snprintf( buf, sizeof(buf), "{%02XYou shout '%s'{00\n\r", COL_SHOUTS, argument );
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
            snprintf( buf, sizeof(buf), "{%02X$n shouts '$t'{00", COL_SHOUTS );
            act_new_cstr(buf,ch,argument,d->character,TO_VICT,POS_SLEEPING);
	}
    }

    return;
}



void do_tell( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim;

    /* If the sender is AFK, sending a tell means they're back — auto-clear */
    if ( !IS_NPC(ch) && IS_SET(ch->act, PLR_AFK) )
    {
        send_to_char( "AFK mode removed.\n\r", ch );
        REMOVE_BIT(ch->act, PLR_AFK);
        if ( ch->pcdata->afk_msg != NULL )
        {
            free_string( ch->pcdata->afk_msg );
            ch->pcdata->afk_msg = NULL;
        }
    }

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
        if (victim->pcdata->afk_msg != NULL)
        {
            snprintf( buf, sizeof(buf), "$E is AFK: %s",
                victim->pcdata->afk_msg );
            act(buf, ch, NULL, victim, TO_CHAR);
        }
        else
            act("$E is AFK and may not respond right away.",ch,NULL,victim,TO_CHAR);
    }

    /* Code Safety: snprintf and buffer safety */
    snprintf( buf, sizeof(buf), "{%02XYou tell %s '%s'{00\n\r",
        COL_TELL, victim->name, argument );
    send_to_char( buf, ch );
    
    snprintf( buf, sizeof(buf), "{%02X%s tells you '%s'{00\n\r",
        COL_TELL, PERS(ch, victim), argument );
    send_to_char( buf, victim );
    victim->reply	= ch;

    return;
}



void do_reply( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *victim;
    char buf[MAX_STRING_LENGTH];

    /* If the sender is AFK, replying means they're back — auto-clear */
    if ( !IS_NPC(ch) && IS_SET(ch->act, PLR_AFK) )
    {
        send_to_char( "AFK mode removed.\n\r", ch );
        REMOVE_BIT(ch->act, PLR_AFK);
        if ( ch->pcdata->afk_msg != NULL )
        {
            free_string( ch->pcdata->afk_msg );
            ch->pcdata->afk_msg = NULL;
        }
    }

    if ( IS_SET(ch->comm, COMM_NOTELL) || IS_SET(ch->comm, COMM_DEAF) )
    {
	send_to_char( "Your message didn't get through.\n\r", ch );
	return;
    }

    if ( IS_SET(ch->comm, COMM_QUIET) )
    {
	send_to_char( "You must turn off quiet mode first.\n\r", ch);
	return;
    }

    if ( argument[0] == '\0' )
    {
	send_to_char( "Reply what?\n\r", ch );
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
    &&  !IS_IMMORTAL(ch))
    {
        act( "$E is not receiving tells.", ch, 0, victim, TO_CHAR );
        return;
    }

    if (IS_SET(victim->act,PLR_AFK))
    {
        if (victim->pcdata->afk_msg != NULL)
        {
            snprintf( buf, sizeof(buf), "$E is AFK: %s",
                victim->pcdata->afk_msg );
            act(buf, ch, NULL, victim, TO_CHAR);
        }
        else
            act("$E is AFK and may not respond right away.",ch,NULL,victim,TO_CHAR);
    }

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf), "{%02XYou reply to %s '%s'{00\n\r",
        COL_TELL, victim->name, argument );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf), "{%02X%s replies '%s'{00\n\r",
        COL_TELL, PERS(ch, victim), argument );
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
    snprintf( buf, sizeof(buf), "{%02XYou yell '%s'{00\n\r", COL_SHOUTS, argument );
    send_to_char( buf, ch );
    
    for ( d = descriptor_list; d != NULL; d = d->next )
    {
	if ( d->connected == CON_PLAYING
	&&   d->character != ch
	&&   d->character->in_room != NULL
	&&   ch->in_room != NULL
	&&   d->character->in_room->area == ch->in_room->area 
        &&   !IS_SET(d->character->comm,COMM_QUIET) )
	{
            snprintf( buf, sizeof(buf), "{%02X$n yells '$t'{00", COL_SHOUTS );
            act_new_cstr(buf,ch,argument,d->character,TO_VICT,POS_SLEEPING);
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
            safe_strcat( buf, sizeof(buf), "." );
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

        safe_strcpy(temp, sizeof(temp), argument);
	temp[strlen(argument) - strlen(letter)] = '\0';
	last[0] = '\0';
	name = vch->name;
	
	for (; *letter != '\0'; letter++)
	{ 
	    if (*letter == '\'' && matches == strlen(vch->name))
	    {
                safe_strcat(temp,sizeof(temp),"r");
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
                    safe_strcat(temp,sizeof(temp),"you");
		    last[0] = '\0';
		    name = vch->name;
		    continue;
		}
		strncat(last,letter,1);
		continue;
	    }

	    matches = 0;
            safe_strcat(temp,sizeof(temp),last);
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

/*
 * Aliases.
 *
 * The storage, the save format and the substitution in interp.c all survived;
 * only the command to read and write them was a stub, so players kept the
 * aliases already in their files and could neither list nor change them.
 *
 *   alias                 list them
 *   alias <name>          show one
 *   alias <name> <text>   set one
 *   unalias <name>        remove one
 */
void do_alias( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    int slot;
    int free_slot;
    size_t length;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    argument = one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
        int shown = 0;

        buf[0] = '\0';
        for ( slot = 0; slot < MAX_ALIASES; slot++ )
        {
            if ( ch->pcdata->alias[slot].first == NULL
              || ch->pcdata->alias[slot].second == NULL )
                continue;

            length = strlen( buf );
            snprintf( buf + length, sizeof(buf) - length, "    %-12s %s\n\r",
                ch->pcdata->alias[slot].first,
                ch->pcdata->alias[slot].second );
            shown++;
        }

        if ( shown == 0 )
        {
            send_to_char( "You have no aliases defined.\n\r", ch );
            return;
        }

        send_to_char( "Your aliases:\n\r", ch );
        send_to_char( buf, ch );
        return;
    }

    /* The documented removal form; unalias does the same thing. */
    if ( !str_cmp( arg, "delete" ) && argument[0] != '\0' )
    {
        do_unalias( ch, argument );
        return;
    }

    if ( !str_cmp( arg, "alias" ) || !str_cmp( arg, "unalias" ) )
    {
        send_to_char( "Aliasing that would leave you no way to undo it.\n\r",
                      ch );
        return;
    }

    /* No argument beyond the name: report what it expands to. */
    if ( argument[0] == '\0' )
    {
        for ( slot = 0; slot < MAX_ALIASES; slot++ )
        {
            if ( ch->pcdata->alias[slot].first != NULL
              && !str_cmp( arg, ch->pcdata->alias[slot].first ) )
            {
                snprintf( buf, sizeof(buf), "%s aliases to '%s'.\n\r",
                    ch->pcdata->alias[slot].first,
                    ch->pcdata->alias[slot].second );
                send_to_char( buf, ch );
                return;
            }
        }

        send_to_char( "That alias is not defined.\n\r", ch );
        return;
    }

    /* Replace an existing one, otherwise take the first free slot. */
    free_slot = -1;
    for ( slot = 0; slot < MAX_ALIASES; slot++ )
    {
        if ( ch->pcdata->alias[slot].first == NULL )
        {
            if ( free_slot == -1 )
                free_slot = slot;
            continue;
        }

        if ( !str_cmp( arg, ch->pcdata->alias[slot].first ) )
        {
            free_slot = slot;
            free_string( ch->pcdata->alias[slot].first );
            free_string( ch->pcdata->alias[slot].second );
            ch->pcdata->alias[slot].first  = NULL;
            ch->pcdata->alias[slot].second = NULL;
            break;
        }
    }

    if ( free_slot == -1 )
    {
        send_to_char( "You have too many aliases; remove one first.\n\r", ch );
        return;
    }

    ch->pcdata->alias[free_slot].first  = str_dup( arg );
    ch->pcdata->alias[free_slot].second = str_dup( argument );

    snprintf( buf, sizeof(buf), "%s is now aliased to '%s'.\n\r",
        arg, argument );
    send_to_char( buf, ch );
    return;
}


void do_unalias( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    int slot;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
        send_to_char( "Remove which alias?\n\r", ch );
        return;
    }

    for ( slot = 0; slot < MAX_ALIASES; slot++ )
    {
        if ( ch->pcdata->alias[slot].first != NULL
          && !str_cmp( arg, ch->pcdata->alias[slot].first ) )
        {
            free_string( ch->pcdata->alias[slot].first );
            free_string( ch->pcdata->alias[slot].second );
            ch->pcdata->alias[slot].first  = NULL;
            ch->pcdata->alias[slot].second = NULL;
            send_to_char( "Alias removed.\n\r", ch );
            return;
        }
    }

    send_to_char( "That alias is not defined.\n\r", ch );
    return;
}


void do_quit( CHAR_DATA *ch, char *argument )
{
    DESCRIPTOR_DATA *d,*d_next;
    char quitter_name[MAX_INPUT_LENGTH];

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
    snprintf( log_buf, 2 * MAX_INPUT_LENGTH, "%s has quit.", ch->name );
    log_string( log_buf );
    log_string("[QUIT] Player rejoined the real world.");

    quest_handle_logout(ch);
    
    /* Snapshot session stats so they can be viewed offline */
    {
        long dur = (long)(current_time - ch->pcdata->session_logon);
        ch->pcdata->last_session_login    = (long)ch->pcdata->session_logon;
        ch->pcdata->last_session_dur      = dur;
        ch->pcdata->last_session_exp_gain = ch->exp - ch->pcdata->session_start_exp;
        ch->pcdata->last_session_lvl_gain = (int)ch->level - ch->pcdata->session_start_level;
        ch->pcdata->last_session_kills    = ch->pcdata->session_kills;
        ch->pcdata->last_session_pk_kills = ch->pcdata->session_pk_kills;
        ch->pcdata->last_session_deaths   = ch->pcdata->session_deaths;
        ch->pcdata->last_session_quests   = ch->pcdata->session_quests;

        /* The same value the character sheet shows, so the journal and
           the sheet cannot disagree about one session. */
        record_logout( ch->name,
            ch->desc != NULL ? ch->desc->host : "(unknown)", "quit", dur );
    }

    /*
     * After extract_char the ch is no longer valid!
     */
    /* save_char_obj now takes a post-mv snapshot internally, so the final
       quit state (with session stats) is always captured without a separate
       call here. */
    save_char_obj( ch );
    /* extract_char frees ch, so take the name while it is still there. */
    toc_strlcpy( quitter_name, ch->name != NULL ? ch->name : "",
                 sizeof(quitter_name) );
    d = ch->desc;
    extract_char( ch, TRUE );
    if ( d != NULL )
	close_socket( d );

    /*
     * Close any *other* descriptor still holding this same character --
     * a duplicate login that the reconnect handling in nanny missed.
     *
     * This compared CHAR_DATA.id until 2026-09-18. Nothing in the
     * codebase ever assigns that field; it was only ever read, right
     * here. So every character's id was 0, the test was 0 == 0, and one
     * player typing `quit' silently disconnected everyone else online.
     */
    for (d = descriptor_list; d != NULL; d = d_next)
    {
	CHAR_DATA *tch;

	d_next = d->next;
	tch = d->original ? d->original : d->character;
	if (tch != NULL && !IS_NPC(tch) && tch->name != NULL
	 && quitter_name[0] != '\0'
	 && !str_cmp(tch->name, quitter_name))
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
	|| (IS_IMMORTAL(victim) && rank_protects( ch, victim )))
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
    LIST_ITERATOR iter;

    one_argument( argument, arg );

    if ( arg[0] == '\0' )
    {
	CHAR_DATA *gch;
	CHAR_DATA *leader;

	leader = (ch->leader != NULL) ? ch->leader : ch;
	/* Code Safety: snprintf */
	snprintf( buf, sizeof(buf), "%s's group:\n\r", PERS(leader, ch) );
	send_to_char( buf, ch );

        FOR_EACH_CHARACTER( iter, gch )
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
    char arg2[MAX_INPUT_LENGTH];
    CHAR_DATA *gch;
    int members;
    long amount;
    long share;
    long extra;
    char *endptr;
    int coin_type;
    const char *coin_name;

    argument = one_argument( argument, arg );
    one_argument( argument, arg2 );

    if ( arg[0] == '\0' )
    {
	send_to_char( "Split how much?\n\r", ch );
	return;
    }
    
    errno = 0;
    amount = strtol( arg, &endptr, 10 );

    if ( errno == ERANGE || *endptr != '\0' )
    {
	send_to_char( "That is not a valid coin amount.\n\r", ch );
	return;
    }

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

    /* Determine coin type from optional second arg; default to gold. */
    if ( arg2[0] == '\0' || !str_prefix( arg2, "gold" ) )
        { coin_type = TYPE_GOLD;     coin_name = "gold";     }
    else if ( !str_prefix( arg2, "platinum" ) )
        { coin_type = TYPE_PLATINUM; coin_name = "platinum"; }
    else if ( !str_prefix( arg2, "silver" ) )
        { coin_type = TYPE_SILVER;   coin_name = "silver";   }
    else if ( !str_prefix( arg2, "copper" ) )
        { coin_type = TYPE_COPPER;   coin_name = "copper";   }
    else
    {
        send_to_char("Choose platinum, gold, silver, or copper.\n\r", ch);
        return;
    }

    /* Check the player has enough of the right coin type. */
    switch ( coin_type )
    {
    case TYPE_PLATINUM:
        if ( ch->new_platinum < amount )
            { send_to_char( "You don't have that much platinum.\n\r", ch ); return; }
        break;
    case TYPE_SILVER:
        if ( ch->new_silver < amount )
            { send_to_char( "You don't have that much silver.\n\r", ch ); return; }
        break;
    case TYPE_COPPER:
        if ( ch->new_copper < amount )
            { send_to_char( "You don't have that much copper.\n\r", ch ); return; }
        break;
    default: /* gold */
        if ( !has_enough_gold( ch, amount ) )
            { send_to_char( "You don't have that much gold.\n\r", ch ); return; }
        break;
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

    /* Validate every recipient before moving any coins. */
    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
        if ( gch != ch && is_same_group( gch, ch )
        &&   !IS_AFFECTED( gch, AFF_CHARM )
        && ( query_carry_coins( gch, share ) > can_carry_w( gch )
          || !can_adjust_coin_balance(gch, share, coin_type) ) )
        {
            act( "$N cannot carry a share that heavy.",
                 ch, NULL, gch, TO_CHAR );
            return;
        }
    }

    /* Deduct from splitter, credit their own share back. */
    switch ( coin_type )
    {
    case TYPE_PLATINUM:
        adjust_coin_balance(ch, share + extra - amount, TYPE_PLATINUM);
        break;
    case TYPE_SILVER:
        adjust_coin_balance(ch, share + extra - amount, TYPE_SILVER);
        break;
    case TYPE_COPPER:
        adjust_coin_balance(ch, share + extra - amount, TYPE_COPPER);
        break;
    default: /* gold */
        add_money(ch, share + extra - amount);
        break;
    }

    /* Code Safety: snprintf */
    snprintf( buf, sizeof(buf),
        "You split %ld %s coins.  Your share is %ld %s.\n\r",
        amount, coin_name, share + extra, coin_name );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf), "$n splits %ld %s coins.  Your share is %ld %s.",
        amount, coin_name, share, coin_name );

    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
	if ( gch != ch && is_same_group( gch, ch ) && !IS_AFFECTED(gch,AFF_CHARM))
	{
	    act( buf, ch, NULL, gch, TO_VICT );
            switch ( coin_type )
            {
            case TYPE_PLATINUM:
                adjust_coin_balance(gch, share, TYPE_PLATINUM); break;
            case TYPE_SILVER:
                adjust_coin_balance(gch, share, TYPE_SILVER); break;
            case TYPE_COPPER:
                adjust_coin_balance(gch, share, TYPE_COPPER); break;
            default:            add_money(gch, share);      break;
            }
        }
    }

    return;
}



void do_gtell( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *gch;
    LIST_ITERATOR iter;

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

    FOR_EACH_CHARACTER( iter, gch )
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
