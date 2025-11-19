/**************************************************************************
 * SEGROMv1 was written and concieved by Eclipse<Eclipse@bud.indirect.com *
 * Soulcrusher <soul@pcix.com> and Gravestone <bones@voicenet.com> all    *
 * rights are reserved.  This is based on the original work of the DIKU   *
 * MERC coding team and Russ Taylor for the ROM2.3 code base.             *
 **************************************************************************/

/***************************************************************************
*  Automated Quest code written by Vassago of MOONGATE, moongate.ams.com   *
*  4000. Copyright (c) 1996 Ryan Addams, All Rights Reserved. Use of this  *
*  code is allowed provided you add a credit line to the effect of:        *
*  "Quest Code (c) 1996 Ryan Addams" to your logon screen with the rest    *
*  of the standard diku/rom credits. If you use this or a modified version *
*  of this code, let me know via email: moongate@moongate.ams.com. Further *
*  updates will be posted to the rom mailing list. If you'd like to get    *
*  the latest version of quest.c, please send a request to the above add-  *
*  ress. Quest Code v2.00.                                                 *
***************************************************************************/
/***************************************************************************
 * Just to toot my own horn *grin* some of the quest code was modified by  *
 * Me Gravestone to work with Times of Chaos MUD.		           *
 ***************************************************************************/

#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <time.h>
#include "merc.h"
#include "interp.h"

DECLARE_DO_FUN( do_say );
/* Object vnums for Quest Rewards */

#define QUEST_ITEM1 29031
#define QUEST_ITEM2 4639
#define QUEST_ITEM3 24
#define QUEST_ITEM4 3081
#define QUEST_ITEM5 29203
#define QUEST_HERO_COST_BASE 7000
#define QUEST_HERO_COST_REMORT 5000
#define QUEST_ENDGAME_BOON_COST 750
#define QUEST_ENDGAME_TROPHY_COST 600
#define QUEST_ENDGAME_CACHE_COST 500

/* Object vnums for object quest 'tokens'. In Moongate, the tokens are
   things like 'the Shield of Moongate', 'the Sceptre of Moongate'. These
   items are worthless and have the rot-death flag, as they are placed
   into the world when a player receives an object quest. */

#define QUEST_OBJQUEST1 25038
#define QUEST_OBJQUEST2 25039
#define QUEST_OBJQUEST3 25040
#define QUEST_OBJQUEST4 25041
#define QUEST_OBJQUEST5 25042

/* Local functions */

void generate_quest	args(( CHAR_DATA *ch, CHAR_DATA *questman ));
void quest_update	args(( void ));
bool chance		args(( int num ));
void advance_level	args(( CHAR_DATA *ch, bool is_advance ));
ROOM_INDEX_DATA *find_location	args( ( CHAR_DATA *ch, char *arg ) );

/* CHANCE function. I use this everywhere in my code, very handy :> */

bool chance(int num)
{
    if (number_range(1,100) <= num) return true;
    else return false;
}

/* The main quest function */

void do_quest(CHAR_DATA *ch, char *argument)
{
    CHAR_DATA *questman;
    OBJ_DATA *obj=NULL, *obj_next;
    OBJ_INDEX_DATA *questinfoobj;
    MOB_INDEX_DATA *questinfo;
    char buf [MAX_STRING_LENGTH];
    char arg1 [MAX_INPUT_LENGTH];
    char arg2 [MAX_INPUT_LENGTH];

    argument = one_argument(argument, arg1);
    argument = one_argument(argument, arg2);

    if (!strcmp(arg1, "info"))
    {
	if (IS_SET(ch->act, PLR_QUESTOR))
	{
	    if (ch->questmob == -1 && ch->questgiver->short_descr != NULL)
	    {
		snprintf(buf, sizeof(buf), "Your quest is ALMOST complete!\n\rGet back to %s before your time runs out!\n\r",ch->questgiver->short_descr);
		send_to_char(buf, ch);
                return;
	    }
	    else if (ch->questobj > 0)
	    {
                questinfoobj = get_obj_index(ch->questobj);
		if (questinfoobj != NULL)
		{
		    snprintf(buf, sizeof(buf), "You are on a quest to recover the %s!\n\r",questinfoobj->name);
		    send_to_char(buf, ch);
                    return;
		}
	    }
	    else if (ch->questmob > 0)
	    {
                questinfo = get_mob_index(ch->questmob);
		if (questinfo != NULL)
		{
	            snprintf(buf, sizeof(buf), "You are on a quest to slay the dreaded %s!\n\r",questinfo->short_descr);
		    send_to_char(buf, ch);
                    return;
		}
	    }
	}
        if (ch->nextquest > 1)
        {
           snprintf(buf, sizeof(buf), "There are %d minutes remaining until you can go on another quest.\n\r",ch->nextquest);
           send_to_char(buf, ch);
           return;
        }
        else if (ch->nextquest == 1)
        {
           snprintf(buf, sizeof(buf), "There is less than a minute remaining until you can go on another quest.\n\r");
           send_to_char(buf, ch);
           return;
        }
        send_to_char("You aren't currently on a quest.\n\r",ch);
        return;
    }
    if (!strcmp(arg1, "points"))
    {
	snprintf(buf, sizeof(buf), "You have %d quest points.\n\r",ch->questpoints);
	send_to_char(buf, ch);
	return;
    }
    else if (!strcmp(arg1, "time"))
    {
	if (!IS_SET(ch->act, PLR_QUESTOR))
	{
	    send_to_char("You aren't currently on a quest.\n\r",ch);
	    if (ch->nextquest > 1)
	    {
		snprintf(buf, sizeof(buf), "There are %d minutes remaining until you can go on another quest.\n\r",ch->nextquest);
		send_to_char(buf, ch);
	    }
	    else if (ch->nextquest == 1)
	    {
		snprintf(buf, sizeof(buf), "There is less than a minute remaining until you can go on another quest.\n\r");
		send_to_char(buf, ch);
	    }
	}
        else if (ch->countdown > 0)
        {
	    snprintf(buf, sizeof(buf), "Time left for current quest: %d\n\r",ch->countdown);
	    send_to_char(buf, ch);
	}
        else
        {   if (ch->nextquest > 0)
            { snprintf(buf, sizeof(buf), "Time left before you can start a next quest: %d\n\r",ch->nextquest);
              send_to_char(buf,ch);
            }
            else
            { snprintf(buf, sizeof(buf),"You can start a new quest if you want.\n\r");
              send_to_char(buf,ch);
            }
        }
	return;
    }

/* Checks for a character in the room with spec_questmaster set. This special
   procedure must be defined in special.c. You could instead use an
   ACT_QUESTMASTER flag instead of a special procedure. */

    for ( questman = ch->in_room->people; questman != NULL; questman = questman->next_in_room )
    {
	if (!IS_NPC(questman)) continue;
        if (IS_SET(questman->act, ACT_QUESTM)) break;
    }

    if (questman == NULL || (!IS_SET(questman->act, ACT_QUESTM)))
    {
        send_to_char("You can't do that here.\n\r",ch);
        return;
    }

    if ( questman->fighting != NULL)
    {
	send_to_char("Wait until the fighting stops.\n\r",ch);
        return;
    }

    ch->questgiver = questman;

/* And, of course, you will need to change the following lines for YOUR
   quest item information. Quest items on Moongate are unbalanced, very
   very nice items, and no one has one yet, because it takes awhile to
   build up quest points :> Make the item worth their while. */

/*  commented this section out below, and replaced with quest.c data from 1999 - Forrest */
/*    if (!strcmp(arg1, "list"))
    {
        act( "$n asks $N for a list of quest items.", ch, NULL, questman, TO_ROOM);
	act ("You ask $N for a list of quest items.",ch, NULL, questman, TO_CHAR);
	snprintf(buf, sizeof(buf), "Current Quest Items available for Purchase:\n\r\
	Potion of Sanctuary		150qp\n\r
	1-3 Practices:			500qp\n\r
	Potion of Extra Heal		450qp\n\r
	Jug O' Moonshine		450qp\n\r
	level 51 hero! (non remort)     500qp\n\r
        level 51 hero! (remort)         1000qp\n\r
To buy an item, type 'AQUEST BUY <item>'.\n\r");
	send_to_char(buf, ch);
	return;
    }*/

    if (!strcmp(arg1, "list"))
    {
        act( "$n asks $N for a list of quest items.", ch, NULL, questman, TO_ROOM);
        act ("You ask $N for a list of quest items.",ch, NULL, questman, TO_CHAR);
        send_to_char("Current Quest Items available for Purchase:\n\r"
    "Potion of Sanctuary                150qp\n\r"
        "1-3 Practices:                 500qp\n\r"
        "Potion of Extra Heal           450qp\n\r"
        "Jug O' Moonshine               450qp\n\r"
        "level 51 hero! (non-remort)   7000qp\n\r"
        "level 51 hero! (remort)       5000qp\n\r"
    "To buy an item, type 'AQUEST BUY <item>'.\n\r", ch);

        if (ch->level >= LEVEL_HERO)
        {
            send_to_char("\n\rEnd-game rewards for maxed heroes:\n\r"
                "Legendary boon (gold + pracs)       750qp\n\r"
                "Keepsake trophy                     600qp\n\r"
                "Surprise cache (potion bundle)      500qp\n\r", ch);
        }
        return;
    }

    else if (!strcmp(arg1, "buy"))
    {
	if (arg2[0] == '\0')
	{
	    send_to_char("To buy an item, type 'AQUEST BUY <item>'.\n\r",ch);
	    return;
	}
        if (IS_NPC(ch))
           return;
        if (is_name(arg2, "hero"))
        {
            int hero_cost = ch->pcdata->num_remorts >= 1 ? QUEST_HERO_COST_REMORT : QUEST_HERO_COST_BASE;

            if( ch->level != 50 ) {
                snprintf(buf, sizeof(buf),"Sorry %s you need to be level 50 to buy that.",ch->name);
                do_say( questman,buf );
                return;
            }

            if (ch->questpoints >= hero_cost)
            {
                ch->questpoints -= hero_cost;
                ch->level += 1;
                ch->exp = exp_per_level(ch,ch->pcdata->points) * ch->level;
                send_to_char("You raise a level!  ", ch );
                advance_level(ch,false);
            }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "heal"))
	{
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
	        obj = create_object(get_obj_index(QUEST_ITEM2),ch->level);
	    }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "moonshine"))
	{
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
	        obj = create_object(get_obj_index(QUEST_ITEM3),ch->level);
	    }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "sanctuary"))
	{
	    if (ch->questpoints >= 150)
	    {
		ch->questpoints -= 150;
	        obj = create_object(get_obj_index(QUEST_ITEM4),ch->level);
	    }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
        else if (is_name(arg2, "practices pracs prac practice"))
        {
            if (ch->questpoints >= 500)
            {
                ch->questpoints -= 500;
                ch->practice += dice(1,2) + 1;
                act( "$N gives some practices to $n.", ch, NULL, questman, TO_ROOM );
                act( "$N gives you some practices.",   ch, NULL, questman, TO_CHAR );
                snprintf(log_buf, 2 * MAX_INPUT_LENGTH, "%s gained pracs from quest.", ch->name);
                log_string(log_buf);
                return;
            }
            else
            {
                snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
                do_say(questman,buf);
                return;
            }
        }
        else if (is_name(arg2, "boon"))
        {
            if (ch->level < LEVEL_HERO)
            {
                snprintf(buf, sizeof(buf), "That favor is reserved for maxed heroes, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

            if (ch->questpoints >= QUEST_ENDGAME_BOON_COST)
            {
                int boon_pracs = number_range(2,4);
                int boon_gold = number_range(8000,15000);

                ch->questpoints -= QUEST_ENDGAME_BOON_COST;
                ch->practice += boon_pracs;
                add_money(ch, boon_gold);

                snprintf(buf, sizeof(buf), "$N calls in favors and grants you %d practices and %d gold!", boon_pracs, boon_gold);
                act(buf, ch, NULL, questman, TO_CHAR);
                act("$N whispers ancient secrets to $n and hands over a hefty purse.", ch, NULL, questman, TO_ROOM);
                return;
            }

            snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
            do_say(questman,buf);
            return;
        }
        else if (is_name(arg2, "trophy"))
        {
            OBJ_INDEX_DATA *trophy_index;

            if (ch->level < LEVEL_HERO)
            {
                snprintf(buf, sizeof(buf), "Keepsakes are only for legendary heroes, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

            trophy_index = get_obj_index(QUEST_ITEM5);
            if (trophy_index == NULL)
            {
                snprintf(buf, sizeof(buf), "I'm afraid we're out of trophies right now, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

            if (ch->questpoints >= QUEST_ENDGAME_TROPHY_COST)
            {
                obj = create_object(trophy_index, ch->level);
                ch->questpoints -= QUEST_ENDGAME_TROPHY_COST;
            }
            else
            {
                snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
                do_say(questman,buf);
                return;
            }
        }
        else if (is_name(arg2, "cache"))
        {
            if (ch->level < LEVEL_HERO)
            {
                snprintf(buf, sizeof(buf), "That cache is sealed to all but the greatest heroes, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

            if (ch->questpoints >= QUEST_ENDGAME_CACHE_COST)
            {
                int reward_count = number_range(2,3);
                int choice;

                ch->questpoints -= QUEST_ENDGAME_CACHE_COST;

                for (choice = 0; choice < reward_count; choice++)
                {
                    switch(number_range(0,2))
                    {
                        case 0:
                            obj = create_object(get_obj_index(QUEST_ITEM2), ch->level);
                            break;
                        case 1:
                            obj = create_object(get_obj_index(QUEST_ITEM3), ch->level);
                            break;
                        default:
                            obj = create_object(get_obj_index(QUEST_ITEM4), ch->level);
                            break;
                    }

                    if (obj != NULL)
                    {
                        act( "$N slides $p into your surprise cache.", ch, obj, questman, TO_CHAR );
                        obj_to_char(obj, ch);
                    }
                }

                act("$N seals a chest and hands it to $n with a knowing grin.", ch, NULL, questman, TO_ROOM);
                return;
            }

            snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
            do_say(questman,buf);
            return;
        }
        else
        {
            snprintf(buf, sizeof(buf), "I don't have that item, %s.",ch->name);
            do_say(questman, buf);
        }
	if (obj != NULL)
	{
    	    act( "$N gives $p to $n.", ch, obj, questman, TO_ROOM );
    	    act( "$N gives you $p.",   ch, obj, questman, TO_CHAR );
	    obj_to_char(obj, ch);
	}
	return;
    }
    else if (!strcmp(arg1, "request"))
    {
        act( "$n asks $N for a quest.", ch, NULL, questman, TO_ROOM);
	act ("You ask $N for a quest.",ch, NULL, questman, TO_CHAR);
	if (IS_SET(ch->act, PLR_QUESTOR))
	{
	    snprintf(buf, sizeof(buf), "But you're already on a quest!");
	    do_say(questman, buf);
	    return;
	}
	if (ch->nextquest > 0)
	{
	    snprintf(buf, sizeof(buf), "You're very brave, %s, but let someone else have a chance.",ch->name);
	    do_say(questman, buf);
	    snprintf(buf, sizeof(buf), "Come back later.");
	    do_say(questman, buf);
	    return;
	}

	snprintf(buf, sizeof(buf), "Thank you, brave %s!",ch->name);
	do_say(questman, buf);

	generate_quest(ch, questman);

        if (ch->questmob > 0 || ch->questobj > 0)
	{
            ch->countdown = number_range(10,30);
	    SET_BIT(ch->act, PLR_QUESTOR);
	    snprintf(buf, sizeof(buf), "You have %d minutes to complete this quest.",ch->countdown);
	    do_say(questman, buf);
	    snprintf(buf, sizeof(buf), "May the gods go with you!");
	    do_say(questman, buf);
	}
	return;
    }
    else if (!strcmp(arg1, "complete"))
    {
        act( "$n informs $N $e has completed $s quest.", ch, NULL, questman, TO_ROOM);
	act ("You inform $N you have completed $s quest.",ch, NULL, questman, TO_CHAR);
	if (ch->questgiver != questman)
	{
	    snprintf(buf, sizeof(buf), "I never sent you on a quest! Perhaps you're thinking of someone else.");
	    do_say(questman,buf);
	    return;
	}

	if (IS_SET(ch->act, PLR_QUESTOR))
	{
	    if (ch->questmob == -1 && ch->countdown > 0)
	    {
		int reward, pointreward;

		reward = number_range(1,30);
		pointreward = number_range(10,40);

		snprintf(buf, sizeof(buf), "Congratulations on completing your quest!");
		do_say(questman,buf);
		snprintf(buf, sizeof(buf),"As a reward, I am giving you %d quest points, and %d gold.",pointreward,reward);
		do_say(questman,buf);

	        REMOVE_BIT(ch->act, PLR_QUESTOR);
	        ch->questgiver = NULL;
	        ch->countdown = 0;
	        ch->questmob = 0;
		ch->questobj = 0;
                add_money(ch,reward);
		ch->questpoints += pointreward;
		if( ch->level == 50 )
		    ch->nextquest = 5;
		else
		    ch->nextquest = 15;
	        return;
	    }
	    else if (ch->questobj > 0 && ch->countdown > 0)
	    {
		bool obj_found = false;

    		for (obj = ch->carrying; obj != NULL; obj= obj_next)
    		{
        	    obj_next = obj->next_content;

		    if (obj != NULL && obj->pIndexData->vnum == ch->questobj)
		    {
			obj_found = true;
            	        break;
		    }
        	}
		if (obj_found == true)
		{
		    int reward, pointreward;

		    reward = number_range(15,30);
		    pointreward = number_range(10,40);

		    act("You hand $p to $N.",ch, obj, questman, TO_CHAR);
		    act("$n hands $p to $N.",ch, obj, questman, TO_ROOM);

	    	    snprintf(buf, sizeof(buf), "Congratulations on completing your quest!");
		    do_say(questman,buf);
		    snprintf(buf, sizeof(buf),"As a reward, I am giving you %d quest points, and %d gold.",pointreward,reward);
		    do_say(questman,buf);

	            REMOVE_BIT(ch->act, PLR_QUESTOR);
	            ch->questgiver = NULL;
	            ch->countdown = 0;
	            ch->questmob = 0;
		    ch->questobj = 0;
                    add_money(ch,reward);
		    ch->questpoints += pointreward;
		    extract_obj(obj);
		    if( ch->level == 50 )
			ch->nextquest = 6;
		    else
			ch->nextquest = 15;
		    return;
		}
		else
		{
		    snprintf(buf, sizeof(buf), "You haven't completed the quest yet, but there is still time!");
		    do_say(questman, buf);
		    return;
		}
		return;
	    }
	    else if ((ch->questmob > 0 || ch->questobj > 0) && ch->countdown > 0)
	    {
		snprintf(buf, sizeof(buf), "You haven't completed the quest yet, but there is still time!");
		do_say(questman, buf);
		return;
	    }
	}
	if (ch->nextquest > 0)
	    snprintf(buf, sizeof(buf),"But you didn't complete your quest in time!");
	else snprintf(buf, sizeof(buf), "You have to REQUEST a quest first, %s.",ch->name);
	do_say(questman, buf);
	return;
    }
    else if (!strcmp(arg1,"abort") )
    {
	act( "$n informs $N that $e is quitting for now.",ch,NULL,questman,TO_ROOM );
	act( "You inform $N that you are quitting for now.",ch,NULL,questman,TO_CHAR);
/*        snprintf(test_buf, sizeof(test_buf),"%s is aborting a quest.",ch->name);
        log_string(test_buf);*/

	if( ch->questgiver != questman )
	{
	    snprintf(buf, sizeof(buf),"I never sent you on a quest!.");
	    do_say(questman,buf);
	    return;
	}

        if (ch -> level >= 50)
        {
            snprintf(buf, sizeof(buf),"HERO's are not allowed to abort quests!.");
            do_say(questman,buf);
            return;
        }
        if( IS_SET(ch->act, PLR_QUESTOR) )
        {
            snprintf(buf, sizeof(buf),"You are removed from your quest obligation %s.",ch->name );
	    do_say(questman,buf);
	    snprintf(buf, sizeof(buf),"Better luck next time!");
	    do_say(questman,buf);

	    REMOVE_BIT(ch->act, PLR_QUESTOR);
	    ch->questgiver = NULL;
	    ch->countdown  = 0;
	    ch->questmob   = 0;
	    ch->questobj   = 0;
	    if( ch->level == 50 )
		ch->nextquest = 7;
	    else
		ch->nextquest = 15;
	    return;
	}
    }

    send_to_char("AQUEST commands: POINTS INFO TIME REQUEST COMPLETE LIST BUY ABORT.\n\r",ch);
    send_to_char("For more information, type 'HELP AQUEST'.\n\r",ch);
    return;
}

void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)
{
    CHAR_DATA *victim;
    MOB_INDEX_DATA *vsearch;
    ROOM_INDEX_DATA *room;
    OBJ_DATA *questitem;
    char buf [MAX_STRING_LENGTH];
    long mcounter;
    int mob_vnum;

    /*  Randomly selects a mob from the world mob list. If you don't
	want a mob to be selected, make sure it is immune to summon.
	Or, you could add a new mob flag called ACT_NOQUEST. The mob
	is selected for both mob and obj quests, even tho in the obj
	quest the mob is not used. This is done to assure the level
	of difficulty for the area isn't too great for the player. */

    for (mcounter = 0; mcounter < 99999; mcounter ++)
    {
	mob_vnum = number_range(50, 30000);

	if ( (vsearch = get_mob_index(mob_vnum) ) != NULL )
	{

		if( vsearch->level > 2
		&& vsearch->level < ch->level
		&& !IS_SET(vsearch->imm_flags, IMM_SUMMON)
		&& vsearch->pShop == NULL
		&& ch->level <= 59
    		&& !IS_SET(vsearch->act,ACT_TRAIN)
    		&& !IS_SET(vsearch->act,ACT_PRACTICE)
    		&& !IS_SET(vsearch->act,ACT_IS_HEALER)
		&& !IS_SET(vsearch->affected_by, AFF_CHARM )
		&& chance(35)) break;
		else vsearch = NULL;
	}
    }

    if ( vsearch == NULL || ( victim = get_char_world( ch, vsearch->player_name ) ) == NULL )
    {
	snprintf(buf, sizeof(buf), "I'm sorry, but I don't have any quests for you at this time.");
	do_say(questman, buf);
	snprintf(buf, sizeof(buf), "Try again later.");
	do_say(questman, buf);
	ch->nextquest = 5;
        return;
    }

    if ( ( room = find_location( ch, victim->name ) ) == NULL )
    {
	snprintf(buf, sizeof(buf), "I'm sorry, but I don't have any quests for you at this time.");
	do_say(questman, buf);
	snprintf(buf, sizeof(buf), "Try again later.");
	do_say(questman, buf);
	ch->nextquest = 5;
        return;
    }

    /*  40% chance it will send the player on a 'recover item' quest. */

    if (chance(40))
    {
	int objvnum = 0;

	switch(number_range(0,4))
	{
	    case 0:
	    objvnum = QUEST_OBJQUEST1;
	    break;

	    case 1:
	    objvnum = QUEST_OBJQUEST2;
	    break;

	    case 2:
	    objvnum = QUEST_OBJQUEST3;
	    break;

	    case 3:
	    objvnum = QUEST_OBJQUEST4;
	    break;

	    case 4:
	    objvnum = QUEST_OBJQUEST5;
	    break;
	}

        questitem = create_object( get_obj_index(objvnum), ch->level );
	obj_to_room(questitem, room);
	ch->questobj = questitem->pIndexData->vnum;

	snprintf(buf, sizeof(buf), "Robbers have stolen %s!",questitem->short_descr);
	do_say(questman,buf);
	do_say(questman, "A bounty of questpoints for you if you recover it!");

	/* I changed my area names so that they have just the name of the area
	   and none of the level stuff. You may want to comment these next two
	   lines. - Vassago */

	snprintf(buf, sizeof(buf), "Look in the general area of %s for %s!",room->area->name, room->name);
	do_say(questman,buf);
	return;
    }

    /* Quest to kill a mob */

    else
    {
    switch(number_range(0,1))
    {
	case 0:
        snprintf(buf, sizeof(buf), "%s has been declared a outlaw!",victim->short_descr);
	do_say(questman,buf);
        snprintf(buf, sizeof(buf), "They must be found and killed!");
	do_say(questman,buf);
	break;

	case 1:
	snprintf(buf, sizeof(buf), "Soulcrusher accidentally left %s escape from jail!",victim->short_descr);
	do_say(questman,buf);
	snprintf(buf, sizeof(buf), "Since the escape, %s has murdered %d civillians!",victim->short_descr, number_range(2,20));
	do_say(questman,buf);
	do_say(questman,"You must find and kill them!");
	break;
    }

    if (room->name != NULL)
    {
        snprintf(buf, sizeof(buf), "Seek %s out somewhere in the vicinity of %s!",victim->short_descr,room->name);
	do_say(questman,buf);

	/* I changed my area names so that they have just the name of the area
	   and none of the level stuff. You may want to comment these next two
	   lines. - Vassago */

	snprintf(buf, sizeof(buf), "That location is in the general area of %s.",room->area->name);
	do_say(questman,buf);
    }

  /* This last if statment should not be necessary, but it appears that
     it is needed to avoid crashes - Rico */

       if (victim->pIndexData->vnum < 30001 && victim->pIndexData->vnum > 0)
       ch->questmob = victim->pIndexData->vnum;
       else
       {
       bug("Questman messed up on the mob's vnum",0);
       ch->questmob = 0;
       do_say(questman,"OOOPS. I've somehow messed up your quest, just type aquest complete.");

       }
    }
    return;
}

/* Called from update_handler() by pulse_area */

void quest_update(void)
{
    CHAR_DATA *ch, *ch_next;

    for ( ch = char_list; ch != NULL; ch = ch_next )
    {
        ch_next = ch->next;

	if (IS_NPC(ch)) continue;

        if (ch->nextquest > 0)
        {
            ch->nextquest--;

            if (ch->nextquest == 0)
            {
                send_to_char("You may now quest again.\n\r",ch);
                continue;
            }
        }
        else if (IS_SET(ch->act,PLR_QUESTOR))
        {
            if (--ch->countdown <= 0)
	    {
    	        char buf [MAX_STRING_LENGTH];

	        if(ch->level == 50)
                    ch->nextquest = 5;
                else
                    ch->nextquest = 15;
                snprintf(buf, sizeof(buf), "You have run out of time for your quest!\n\rYou may quest again in %d minutes.\n\r",ch->nextquest);
                send_to_char(buf, ch);
                REMOVE_BIT(ch->act, PLR_QUESTOR);
                ch->questgiver = NULL;
                ch->countdown = 0;
                ch->questmob = 0;
            }
            if (ch->countdown > 0 && ch->countdown < 6)
            {
                send_to_char("Better hurry, you're almost out of time for your quest!\n\r",ch);
                continue;
            }
        }
    }
}
