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
#include <limits.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <time.h>
#include "merc.h"
#include "interp.h"

DECLARE_DO_FUN( do_say );
/* Object vnums for Quest Rewards */

#define QUEST_ITEM2 4639
#define QUEST_ITEM3 24
#define QUEST_ITEM4 3081
#define QUEST_ITEM5 20306
#define QUEST_ITEM_POWER 20303
#define QUEST_ITEM_GIANT 20304
#define QUEST_ITEM_FARSLAY 20305
#define QUEST_HERO_COST_BASE 7000
#define QUEST_HERO_COST_REMORT 5000
#define QUEST_ENDGAME_BOON_COST 750
#define QUEST_ENDGAME_TROPHY_COST 600
#define QUEST_ENDGAME_CACHE_COST 500

/* Object vnums for object quest 'tokens'. In Moongate, the tokens are
   things like 'the Shield of Moongate', 'the Sceptre of Moongate'. These
   items are worthless and have the rot-death flag, as they are placed
   into the world when a player receives an object quest. */

#define QUEST_OBJQUEST1 OBJ_VNUM_QUEST_TOKEN_FIRST
#define QUEST_OBJQUEST2 (OBJ_VNUM_QUEST_TOKEN_FIRST + 1)
#define QUEST_OBJQUEST3 (OBJ_VNUM_QUEST_TOKEN_FIRST + 2)
#define QUEST_OBJQUEST4 (OBJ_VNUM_QUEST_TOKEN_FIRST + 3)
#define QUEST_OBJQUEST5 OBJ_VNUM_QUEST_TOKEN_LAST

/* Local functions */

void generate_quest	args(( CHAR_DATA *ch, CHAR_DATA *questman ));
void quest_update	args(( void ));
bool chance		args(( int num ));
void advance_level	args(( CHAR_DATA *ch, bool is_advance ));

/* CHANCE function. I use this everywhere in my code, very handy :> */

bool chance(int num)
{
    if (number_range(1,100) <= num) return true;
    else return false;
}

static bool is_automatic_quest_token( const OBJ_DATA *obj )
{
    int vnum;

    if ( obj == NULL || obj->pIndexData == NULL )
        return false;

    vnum = obj->pIndexData->vnum;
    return vnum >= OBJ_VNUM_QUEST_TOKEN_FIRST
        && vnum <= OBJ_VNUM_QUEST_TOKEN_LAST;
}

static int quest_token_owner_tag( const CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return 0;
    return ch->pcdata->id + 1;
}

static bool quest_token_belongs_to( const OBJ_DATA *obj, const CHAR_DATA *ch )
{
    if ( !is_automatic_quest_token(obj)
    ||   obj->value[4] != quest_token_owner_tag(ch) )
        return false;

    return obj->owner != NULL && obj->owner[0] != '\0'
        && !str_cmp(obj->owner, ch->name);
}

static void remove_automatic_quest_tokens( CHAR_DATA *ch )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;

    FOR_EACH_OBJECT( iter, obj )
        if ( quest_token_belongs_to(obj, ch) )
            extract_obj(obj);
}

static OBJ_DATA *find_automatic_quest_token( OBJ_DATA *objects,
                                             CHAR_DATA *ch, int vnum )
{
    OBJ_DATA *obj;
    OBJ_DATA *found;

    for ( obj = objects; obj != NULL; obj = obj->next_content )
    {
        if ( obj->pIndexData != NULL
        &&   obj->pIndexData->vnum == vnum
        &&   quest_token_belongs_to(obj, ch) )
            return obj;

        found = find_automatic_quest_token(obj->contains, ch, vnum);
        if ( found != NULL )
            return found;
    }

    return NULL;
}

static int add_quest_points( CHAR_DATA *ch, int amount )
{
    int granted;

    if ( ch == NULL || amount <= 0 )
        return 0;
    if ( ch->questpoints < 0 )
        ch->questpoints = 0;
    if ( ch->questpoints >= INT_MAX )
        return 0;

    granted = UMIN(amount, INT_MAX - ch->questpoints);
    ch->questpoints += granted;
    return granted;
}

static int quest_streak_bonus( const CHAR_DATA *ch )
{
    if ( ch == NULL )
        return 0;
    return URANGE(0, ch->queststreak, 5) * 10;
}

static void complete_automatic_quest( CHAR_DATA *ch, CHAR_DATA *questman,
                                      int gold_min, int gold_max )
{
    char buf[MAX_STRING_LENGTH];
    bool completed_rush = ch->questrush;
    bool completed_last_minute = ch->countdown == 1;
    int pointreward = number_range(10,40);
    int reward = number_range(gold_min, gold_max);
    int streak_bonus = quest_streak_bonus(ch);

    if ( completed_rush )
        pointreward *= 2;
    pointreward += (pointreward * streak_bonus) / 100;

    switch (number_range(0, 2))
    {
        case 0: do_say(questman, "Excellent work! The realm is in your debt!"); break;
        case 1: do_say(questman, "Splendid - you've returned victorious!"); break;
        default: do_say(questman, "Well done! I knew you were right for the job."); break;
    }

    if ( !IS_NPC(ch) && ch->pcdata->session_quests < INT_MAX )
        ch->pcdata->session_quests++;
    if ( completed_rush )
        do_say(questman,
            "Rush contract fulfilled - your double reward is well earned!");
    if ( ch->queststreak > 0 )
    {
        snprintf(buf, sizeof(buf),
            "Streak of %d in a row! A +%d%% bonus has been added!",
            ch->queststreak + 1, streak_bonus);
        do_say(questman, buf);
    }

    REMOVE_BIT(ch->act, PLR_QUESTOR);
    ch->questgiver = NULL;
    ch->countdown = 0;
    ch->questmob = 0;
    ch->questobj = 0;
    ch->questrush = false;
    if ( ch->queststreak < 0 )
        ch->queststreak = 0;
    if ( ch->queststreak < SHRT_MAX )
        ch->queststreak++;

    achievement_record_quest(ch);
    if ( completed_rush )
        achievement_record_event(ch, ACHIEVEMENT_EVENT_QUEST_RUSH, true);
    if ( completed_last_minute )
        achievement_record_event(ch, ACHIEVEMENT_EVENT_QUEST_LAST_MINUTE, true);

    add_money(ch, reward);
    ch->questgamble_pts = (sh_int)pointreward;
    snprintf(buf, sizeof(buf), "Here's your %d gold - well earned!", reward);
    do_say(questman, buf);
    send_to_char(
        "{09.-[ Double-or-Nothing Gamble Offer ]-------------------------.{00\n\r", ch);
    snprintf(buf, sizeof(buf),
        "{09|{00 {04Earned :{00 {0D%d{00 quest points\n\r"
        "{09|{00 {06Win     :{00 50%% chance to earn {0D%d{00 pts\n\r"
        "{09|{00 {07Lose    :{00 50%% chance to earn {0D0{00 pts\n\r"
        "{09|{00  Type {0DAQUEST GAMBLE YES{00 or {0DAQUEST GAMBLE NO{00\n\r"
        "{09'---------------------------------------------------------------'{00\n\r",
        pointreward, pointreward * 2);
    send_to_char(buf, ch);

    ch->nextquest = ch->level == 50 ? 5 : 15;
    save_char_obj(ch);
}

static void credit_automatic_quest_kill( CHAR_DATA *ch, int target_vnum )
{
    if ( ch == NULL || IS_NPC(ch)
    ||   !IS_SET(ch->act, PLR_QUESTOR)
    ||   ch->questmob != target_vnum )
        return;

    send_to_char("You have almost finished your QUEST!\n\r", ch);
    send_to_char(
        "Return to any questmaster before it is too late!\n\r", ch);
    ch->questmob = -1;
    save_char_obj(ch);
}

void quest_record_kill( CHAR_DATA *killer, CHAR_DATA *victim )
{
    CHAR_DATA *credit;
    CHAR_DATA *member;
    int target_vnum;

    if ( victim == NULL || !IS_NPC(victim) || victim->pIndexData == NULL
    ||   victim->in_room == NULL )
        return;

    credit = killer;
    if ( credit != NULL && IS_NPC(credit) && credit->master != NULL
    &&   !IS_NPC(credit->master) )
        credit = credit->master;
    if ( credit == NULL || IS_NPC(credit) )
        return;

    target_vnum = victim->pIndexData->vnum;
    credit_automatic_quest_kill(credit, target_vnum);
    for ( member = victim->in_room->people; member != NULL;
          member = member->next_in_room )
    {
        if ( IS_NPC(member)
	||   member == credit
	||   !is_same_group(member, credit) )
            continue;

	credit_automatic_quest_kill(member, target_vnum);
    }
}

void quest_handle_logout( CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC(ch) || !IS_SET(ch->act, PLR_QUESTOR) )
        return;

    remove_automatic_quest_tokens(ch);
    REMOVE_BIT(ch->act, PLR_QUESTOR);
    ch->questgiver = NULL;
    ch->countdown = 0;
    ch->questmob = 0;
    ch->questobj = 0;
    ch->questrush = false;
    ch->queststreak = 0;
    ch->nextquest = ch->level == 50 ? 5 : 15;
    send_to_char(
        "Leaving the game abandons your active quest and breaks its streak.\n\r",
        ch);
}

/* The main quest function */

void do_quest(CHAR_DATA *ch, char *argument)
{
    CHAR_DATA *questman;
    OBJ_DATA *obj=NULL;
    OBJ_INDEX_DATA *questinfoobj;
    OBJ_INDEX_DATA *reward_index;
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
	    /* Active quest status panel */
	    send_to_char(
		"{09.-[ Quest Status ]--------------------------------------------.{00\n\r", ch);
	    if (ch->questmob == -1)
	    {
		snprintf(buf, sizeof(buf),
		    "{09|{00 {04Type  :{00 Quest nearly done!\n\r"
		    "{09|{00 {04Return:{00 {06Report to any questmaster right away!{00\n\r");
		send_to_char(buf, ch);
	    }
	    else if (ch->questobj > 0)
	    {
		questinfoobj = get_obj_index(ch->questobj);
		if (questinfoobj != NULL)
		{
		    snprintf(buf, sizeof(buf),
			"{09|{00 {04Type  :{00 Recovery Quest\n\r"
			"{09|{00 {04Target:{00 {0DRecover {01%s{00\n\r",
			questinfoobj->short_descr);
		    send_to_char(buf, ch);
		}
	    }
	    else if (ch->questmob > 0)
	    {
		questinfo = get_mob_index(ch->questmob);
		if (questinfo != NULL)
		{
		    snprintf(buf, sizeof(buf),
			"{09|{00 {04Type  :{00 Kill Quest\n\r"
			"{09|{00 {04Target:{00 {07Slay %s{00\n\r",
			questinfo->short_descr);
		    send_to_char(buf, ch);
		}
	    }
	    if (ch->countdown > 0)
	    {
		const char *tcol = (ch->countdown <= 3) ? "{0C" : "{0D";
		snprintf(buf, sizeof(buf),
		    "{09|{00 {04Timer :{00 %s%d minute%s remaining{00\n\r",
		    tcol, ch->countdown,
		    ch->countdown == 1 ? "" : "s");
		send_to_char(buf, ch);
	    }
	    if (ch->questrush)
		send_to_char(
		    "{09|{00 {0C** RUSH CONTRACT - double reward for finishing on time! **{00\n\r", ch);
	    if (ch->queststreak > 0)
	    {
		int bonus_pct = quest_streak_bonus(ch);
		snprintf(buf, sizeof(buf),
		    "{09|{00 {06Streak:{00 {0D%d{00 win%s in a row"
		    " ({0D+%d%%{00 bonus on completion)\n\r",
		    ch->queststreak,
		    ch->queststreak == 1 ? "" : "s",
		    bonus_pct);
		send_to_char(buf, ch);
	    }
	    send_to_char(
		"{09'------------------------------------------------------'{00\n\r", ch);
	    return;
	}

	/* Not currently questing - summary panel */
	send_to_char(
	    "{09.-[ Quest Summary ]-------------------------------------------.{00\n\r", ch);
	snprintf(buf, sizeof(buf),
	    "{09|{00 {04Quest Points:{00 {0D%d{00\n\r", ch->questpoints);
	send_to_char(buf, ch);
	if (ch->nextquest > 1)
	{
	    snprintf(buf, sizeof(buf),
		"{09|{00 {04Next Quest  :{00 {07%d{00 minutes before you may quest again\n\r",
		ch->nextquest);
	    send_to_char(buf, ch);
	}
	else if (ch->nextquest == 1)
	    send_to_char(
		"{09|{00 {04Next Quest  :{00 {07Less than 1 minute{00 remaining\n\r", ch);
	else
	    send_to_char(
		"{09|{00 {04Next Quest  :{00 {06Ready!{00 Find a questmaster and type"
		" {0DAQUEST REQUEST{00.\n\r", ch);
	if (ch->questgamble_pts > 0)
	{
	    snprintf(buf, sizeof(buf),
		"{09|{00 {0CGamble Offer:{00 {0D%d{00 pts pending -"
		" type {0DAQUEST GAMBLE YES{00 or {0DAQUEST GAMBLE NO{00\n\r",
		ch->questgamble_pts);
	    send_to_char(buf, ch);
	}
	if (ch->queststreak > 0)
	{
	    int bonus_pct = quest_streak_bonus(ch);
	    snprintf(buf, sizeof(buf),
		"{09|{00 {06Win Streak  :{00 {0D%d{00 win%s in a row"
		" (next quest earns {0D+%d%%{00 bonus)\n\r",
		ch->queststreak,
		ch->queststreak == 1 ? "" : "s",
		bonus_pct);
	    send_to_char(buf, ch);
	}
	send_to_char(
	    "{09'-------------------------------------------------------'{00\n\r", ch);
	return;
    }
    if (!strcmp(arg1, "points"))
    {
	snprintf(buf, sizeof(buf),
	    "Quest Points: {0D%d{00\n\r", ch->questpoints);
	send_to_char(buf, ch);
	return;
    }
    else if (!strcmp(arg1, "time"))
    {
	if (!IS_SET(ch->act, PLR_QUESTOR))
	{
	    if (ch->nextquest > 1)
	    {
		snprintf(buf, sizeof(buf),
		    "Not on a quest. {07%d{00 minute%s before you may quest again.\n\r",
		    ch->nextquest, ch->nextquest == 1 ? "" : "s");
		send_to_char(buf, ch);
	    }
	    else if (ch->nextquest == 1)
		send_to_char(
		    "Not on a quest. {07Under 1 minute{00 before you may quest again.\n\r", ch);
	    else
		send_to_char(
		    "Not on a quest. {06Ready to quest!{00 Find a questmaster.\n\r", ch);
	}
	else if (ch->countdown > 0)
	{
	    const char *tcol = (ch->countdown <= 3) ? "{0C" : "{0D";
	    snprintf(buf, sizeof(buf),
		"Quest timer: %s%d minute%s remaining.{00\n\r",
		tcol, ch->countdown, ch->countdown == 1 ? "" : "s");
	    send_to_char(buf, ch);
	}
	else
	{
	    if (ch->nextquest > 0)
	    {
		snprintf(buf, sizeof(buf),
		    "Quest complete. {07%d{00 minute%s before you may quest again.\n\r",
		    ch->nextquest, ch->nextquest == 1 ? "" : "s");
		send_to_char(buf, ch);
	    }
	    else
		send_to_char(
		    "{06Ready to start a new quest!{00 Find a questmaster.\n\r", ch);
	}
	return;
    }
    else if (!strcmp(arg1, "gamble"))
    {
        if (IS_NPC(ch)) return;
        if (ch->questgamble_pts <= 0)
        {
            send_to_char("{07You have no pending double-or-nothing offer.{00\n\r", ch);
            return;
        }
        if (arg2[0] == '\0'
        || (str_cmp(arg2,"yes") && str_cmp(arg2,"y") && str_cmp(arg2,"no") && str_cmp(arg2,"n")))
        {
            send_to_char(
		"{09.-[ Double-or-Nothing Gamble ]-------------------------------.{00\n\r", ch);
            snprintf(buf, sizeof(buf),
                "{09|{00 {04Wager:{00 {0D%d{00 quest points\n\r"
                "{09|{00 {06Win  :{00 {0D%d{00 quest points  {01(50%% chance){00\n\r"
                "{09|{00 {07Lose :{00 {0D0{00 quest points  {01(50%% chance){00\n\r"
                "{09|{00\n\r"
		"{09|{00  Type {0DAQUEST GAMBLE YES{00 to risk it all!\n\r"
		"{09|{00  Type {0DAQUEST GAMBLE NO{00  to collect {0D%d{00 pts safely.\n\r"
		"{09'---------------------------------------------------------------'{00\n\r",
                ch->questgamble_pts, ch->questgamble_pts * 2, ch->questgamble_pts);
            send_to_char(buf, ch);
            return;
        }
        if (!str_cmp(arg2, "yes") || !str_cmp(arg2, "y"))
        {
            int wagered = ch->questgamble_pts;
            ch->questgamble_pts = 0;
            if (chance(50))
            {
		int awarded = add_quest_points(ch, wagered * 2);

                snprintf(buf, sizeof(buf),
		    "\n\r{0D** Fortune SMILES upon you!"
		    " You WIN %d quest points! **{00\n\r\n\r",
		    awarded);
                send_to_char(buf, ch);
                act("{0DFortune{00 shines on $n - they won the gamble!",
		    ch, NULL, NULL, TO_ROOM);
		achievement_record_event(
		    ch, ACHIEVEMENT_EVENT_QUEST_GAMBLE_WIN, true);
            }
            else
            {
                snprintf(buf, sizeof(buf),
		    "\n\r{0AThe dice BETRAY you!"
		    " Your %d quest points are lost.{00\n\r\n\r",
		    wagered);
                send_to_char(buf, ch);
                act("$n curses their luck and slams a fist on the table.",
		    ch, NULL, NULL, TO_ROOM);
            }
            save_char_obj(ch);
            return;
        }
        /* arg2 == "no" or "n" */
        {
            int claimed = ch->questgamble_pts;
	    int awarded;

            ch->questgamble_pts = 0;
	    awarded = add_quest_points(ch, claimed);
            snprintf(buf, sizeof(buf),
		"{06Wise choice. You safely collect {0D%d{00{06 quest points.{00\n\r",
		awarded);
            send_to_char(buf, ch);
            save_char_obj(ch);
            return;
        }
    }

/* Checks for a character in the room with spec_questmaster set. This special
   procedure must be defined in special.c. You could instead use an
   ACT_QUESTMASTER flag instead of a special procedure. */

    if ( ch->in_room == NULL )
    {
        send_to_char("You can't do that here.\n\r",ch);
        return;
    }

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
        send_to_char(
	    "{09.-[ Quest Shop ]-----------------------------------------------.{00\n\r"
	    "{09|{00\n\r"
	    "{09|{00  {04Item                               Cost{00\n\r"
	    "{09|{00  {01------------------------------------------{00\n\r"
	    "{09|{00  Potion of Sanctuary              {0D150 qp{00\n\r"
	    "{09|{00  Potion of Extra Heal             {0D450 qp{00\n\r"
	    "{09|{00  Jug O' Moonshine                 {0D450 qp{00\n\r"
	    "{09|{00  Potion of Power                  {0D450 qp{00\n\r"
	    "{09|{00  Potion of the Giant              {0D450 qp{00\n\r"
	    "{09|{00  Scroll of Farslay                {0D600 qp{00\n\r"
	    "{09|{00  1-3 Practices                    {0D500 qp{00\n\r"
	    "{09|{00  Level 51 Hero  (non-remort)     {0D7000 qp{00\n\r"
	    "{09|{00  Level 51 Hero  (remort)         {0D5000 qp{00\n\r"
	    "{09|{00\n\r"
	    "{09|{00  {04Automatic Bonus Systems:{00\n\r"
	    "{09|{00  {06Win Streak     {00+10%% per quest in a row (max +50%%)\n\r"
	    "{09|{00  {0CRush Contract  {0020%% chance: 2x reward, 5-8 minute timer\n\r"
	    "{09|{00  {0DGamble Offer   {00Double-or-nothing after every completion\n\r"
	    "{09|{00\n\r"
	    "{09|{00  Type {0DAQUEST BUY <item>{00 to purchase.\n\r"
	    "{09'---------------------------------------------------------------'{00\n\r",
	    ch);

        if (ch->level >= LEVEL_HERO)
        {
            send_to_char(
		"{09.-[ End-Game Rewards (Heroes Only) ]-------------------------.{00\n\r"
		"{09|{00  Legendary Boon  (gold + practices)   {0D750 qp{00\n\r"
		"{09|{00  Keepsake Trophy                      {0D600 qp{00\n\r"
		"{09|{00  Surprise Cache  (potion bundle)      {0D500 qp{00\n\r"
		"{09'---------------------------------------------------------------'{00\n\r",
		ch);
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
                save_char_obj(ch);
            }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "power empower"))
	{
	    reward_index = get_obj_index(QUEST_ITEM_POWER);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing Potion of Power vnum %d.", QUEST_ITEM_POWER);
		do_say(questman,"That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
		obj = create_object(reward_index,ch->level);
	    }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "giant strength"))
	{
	    reward_index = get_obj_index(QUEST_ITEM_GIANT);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing Potion of the Giant vnum %d.", QUEST_ITEM_GIANT);
		do_say(questman,"That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
		obj = create_object(reward_index,ch->level);
	    }
	    else
	    {
		snprintf(buf, sizeof(buf), "Sorry, %s, but you don't have enough quest points for that.",ch->name);
		do_say(questman,buf);
		return;
	    }
	}
	else if (is_name(arg2, "farslay scroll"))
	{
	    reward_index = get_obj_index(QUEST_ITEM_FARSLAY);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing Scroll of Farslay vnum %d.", QUEST_ITEM_FARSLAY);
		do_say(questman,"That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 600)
	    {
		ch->questpoints -= 600;
		obj = create_object(reward_index,ch->level);
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
	    reward_index = get_obj_index(QUEST_ITEM2);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing extra-heal reward vnum %d.", QUEST_ITEM2);
		do_say(questman, "That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
	        obj = create_object(reward_index,ch->level);
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
	    reward_index = get_obj_index(QUEST_ITEM3);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing moonshine reward vnum %d.", QUEST_ITEM3);
		do_say(questman, "That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 450)
	    {
		ch->questpoints -= 450;
	        obj = create_object(reward_index,ch->level);
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
	    reward_index = get_obj_index(QUEST_ITEM4);
	    if ( reward_index == NULL )
	    {
		bug("Do_quest: missing sanctuary reward vnum %d.", QUEST_ITEM4);
		do_say(questman, "That reward is temporarily unavailable.");
		return;
	    }
	    if (ch->questpoints >= 150)
	    {
		ch->questpoints -= 150;
	        obj = create_object(reward_index,ch->level);
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
                int gained;

                if ( ch->practice >= SHRT_MAX )
                {
                    do_say(questman, "You cannot retain any more practices.");
                    return;
                }

                gained = UMIN(number_range(1,3), SHRT_MAX - ch->practice);
                ch->questpoints -= 500;
                ch->practice = (sh_int)(ch->practice + gained);
                act( "$N gives some practices to $n.", ch, NULL, questman, TO_ROOM );
                act( "$N gives you some practices.",   ch, NULL, questman, TO_CHAR );
                snprintf(log_buf, 2 * MAX_INPUT_LENGTH, "%s gained pracs from quest.", ch->name);
                log_string(log_buf);
                save_char_obj(ch);
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
                snprintf(buf, sizeof(buf),
		    "That favor is reserved for heroes, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

	    if ( ch->practice >= SHRT_MAX )
	    {
		do_say(questman,
		    "You cannot retain the practices included in that boon.");
		return;
	    }

            if (ch->questpoints >= QUEST_ENDGAME_BOON_COST)
            {
                int boon_pracs = number_range(2,4);
                int boon_gold = number_range(8000,15000);

                boon_pracs = UMIN(boon_pracs, SHRT_MAX - ch->practice);
                ch->questpoints -= QUEST_ENDGAME_BOON_COST;
                ch->practice = (sh_int)(ch->practice + boon_pracs);
                add_money(ch, boon_gold);

                snprintf(buf, sizeof(buf), "$N calls in favors and grants you %d practices and %d gold!", boon_pracs, boon_gold);
                act(buf, ch, NULL, questman, TO_CHAR);
                act("$N whispers ancient secrets to $n and hands over a hefty purse.", ch, NULL, questman, TO_ROOM);
                save_char_obj(ch);
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
	    OBJ_INDEX_DATA *cache_rewards[3];
	    int cache_index;

            if (ch->level < LEVEL_HERO)
            {
                snprintf(buf, sizeof(buf), "That cache is sealed to all but the greatest heroes, %s.", ch->name);
                do_say(questman, buf);
                return;
            }

	    cache_rewards[0] = get_obj_index(QUEST_ITEM2);
	    cache_rewards[1] = get_obj_index(QUEST_ITEM3);
	    cache_rewards[2] = get_obj_index(QUEST_ITEM4);
	    for ( cache_index = 0; cache_index < 3; cache_index++ )
	    {
		if ( cache_rewards[cache_index] != NULL )
		    continue;
		bug("Do_quest: missing surprise-cache reward index %d.",
		    cache_index);
		do_say(questman, "That reward is temporarily unavailable.");
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
			    obj = create_object(cache_rewards[0], ch->level);
                            break;
                        case 1:
			    obj = create_object(cache_rewards[1], ch->level);
                            break;
                        default:
			    obj = create_object(cache_rewards[2], ch->level);
                            break;
                    }

                    if (obj != NULL)
                    {
                        act( "$N slides $p into your surprise cache.", ch, obj, questman, TO_CHAR );
                        obj_to_char(obj, ch);
                    }
                }

                act("$N seals a chest and hands it to $n with a knowing grin.", ch, NULL, questman, TO_ROOM);
                save_char_obj(ch);
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
	    save_char_obj(ch);
	}
	return;
    }
    else if (!strcmp(arg1, "request"))
    {
        if ( ch->questgamble_pts > 0 )
        {
            send_to_char(
                "Resolve your pending AQUEST GAMBLE offer before requesting another quest.\n\r",
                ch);
            return;
        }

        act( "$n approaches $N seeking a quest.", ch, NULL, questman, TO_ROOM);
	act ("You approach $N and ask for a quest.",ch, NULL, questman, TO_CHAR);
	if (IS_SET(ch->act, PLR_QUESTOR))
	{
	    snprintf(buf, sizeof(buf),
		"You're already on a quest, %s! Finish it first.", ch->name);
	    do_say(questman, buf);
	    return;
	}
	if (ch->nextquest > 0)
	{
	    snprintf(buf, sizeof(buf),
		"You've earned a rest, %s. Return in %d minute%s.",
		ch->name, ch->nextquest, ch->nextquest == 1 ? "" : "s");
	    do_say(questman, buf);
	    return;
	}

	remove_automatic_quest_tokens(ch);
	ch->questgiver = NULL;
	ch->questmob = 0;
	ch->questobj = 0;
	ch->countdown = 0;
	ch->questrush = false;

	switch (number_range(0, 3))
	{
	    case 0:
		snprintf(buf, sizeof(buf), "Ah, a brave soul! Well met, %s.", ch->name);
		break;
	    case 1:
		snprintf(buf, sizeof(buf),
		    "Your timing is perfect, %s. I have just the task for you.", ch->name);
		break;
	    case 2:
		snprintf(buf, sizeof(buf),
		    "Welcome, %s. The realm needs someone of your skill.", ch->name);
		break;
	    default:
		snprintf(buf, sizeof(buf),
		    "Thank you for answering the call, brave %s!", ch->name);
		break;
	}
	do_say(questman, buf);

	generate_quest(ch, questman);

        if (ch->questmob > 0 || ch->questobj > 0)
	{
	    if (chance(20))
	    {
		ch->countdown = (sh_int)(number_range(5, 8));
		ch->questrush = true;
		send_to_char(
		    "\n\r{0C** RUSH CONTRACT! Double reward - finish before time runs out! **{00\n\r\n\r",
		    ch);
		do_say(questman,
		    "This is a RUSH CONTRACT - finish fast and I'll double your reward!");
		snprintf(buf, sizeof(buf),
		    "You have only %d minutes. Don't waste a second!", ch->countdown);
		do_say(questman, buf);
	    }
	    else
	    {
		ch->countdown = (sh_int)(number_range(10,30));
		ch->questrush = false;
		snprintf(buf, sizeof(buf),
		    "You have %d minutes to complete this quest.", ch->countdown);
		do_say(questman, buf);
		switch (number_range(0, 2))
		{
		    case 0: do_say(questman, "May the gods guide your blade!"); break;
		    case 1: do_say(questman, "The realm is counting on you!"); break;
		    case 2: do_say(questman, "Fortune favors the bold - good luck!"); break;
		}
	    }
	    SET_BIT(ch->act, PLR_QUESTOR);
	}
	save_char_obj(ch);
	return;
    }
    else if (!strcmp(arg1, "complete"))
    {
        act( "$n informs $N $e has completed $s quest.", ch, NULL, questman, TO_ROOM);
	act ("You inform $N you have completed $s quest.",ch, NULL, questman, TO_CHAR);

	if (IS_SET(ch->act, PLR_QUESTOR))
	{
	    if (ch->questmob == -1 && ch->countdown > 0)
	    {
		complete_automatic_quest(ch, questman, 1, 30);
	        return;
	    }
	    else if (ch->questobj > 0 && ch->countdown > 0)
	    {
		obj = find_automatic_quest_token(
		    ch->carrying, ch, ch->questobj);
		if (obj != NULL)
		{
		    act("You hand $p to $N.",ch, obj, questman, TO_CHAR);
		    act("$n hands $p to $N.",ch, obj, questman, TO_ROOM);
		    remove_automatic_quest_tokens(ch);
		    complete_automatic_quest(ch, questman, 15, 30);
		    return;
		}
		else
		{
		    do_say(questman,
			"You haven't finished the quest, but there is still time!");
		    return;
		}
	    }
	    else if ((ch->questmob > 0 || ch->questobj > 0) && ch->countdown > 0)
	    {
		do_say(questman, "You haven't finished the quest, but there is still time!");
		return;
	    }
	}
	if (ch->nextquest > 0)
	    snprintf(buf, sizeof(buf),
		"Alas, %s - your quest has already timed out.", ch->name);
	else
	    snprintf(buf, sizeof(buf),
		"You have no active quest, %s. Try AQUEST REQUEST first.", ch->name);
	do_say(questman, buf);
	return;
    }
    else if (!strcmp(arg1,"abort") )
    {
	act( "$n approaches $N to abandon $s quest.",ch,NULL,questman,TO_ROOM );
	act( "You tell $N that you are abandoning your quest.",ch,NULL,questman,TO_CHAR);

        if( IS_SET(ch->act, PLR_QUESTOR) )
        {
            snprintf(buf, sizeof(buf),
		"Very well, %s. Your quest obligation is lifted.", ch->name);
	    do_say(questman,buf);
	    if (ch->queststreak > 0)
	    {
		snprintf(buf, sizeof(buf),
		    "You had a streak of %d in a row - all gone now!", ch->queststreak);
		do_say(questman, buf);
		send_to_char("{07Your winning streak has been broken!{00\n\r", ch);
	    }
	    ch->queststreak = 0;
	    switch (number_range(0, 2))
	    {
		case 0: do_say(questman,
		    "Perhaps fortune will favor you more next time."); break;
		case 1: do_say(questman,
		    "Come back when you're ready. The work won't do itself."); break;
		case 2: do_say(questman,
		    "May your next quest go better!"); break;
	    }

	    remove_automatic_quest_tokens(ch);
	    REMOVE_BIT(ch->act, PLR_QUESTOR);
	    ch->questgiver = NULL;
	    ch->countdown  = 0;
	    ch->questmob   = 0;
	    ch->questobj   = 0;
	    ch->questrush  = false;
	    if( ch->level == 50 )
		ch->nextquest = 7;
	    else
		ch->nextquest = 15;
	    save_char_obj(ch);
	    return;
	}
    }

    send_to_char(
	"{09.-[ AQUEST Commands ]-----------------------------------------.{00\n\r"
	"{09|{00  {04INFO     {00 View quest status or summary\n\r"
	"{09|{00  {04POINTS   {00 Check your quest point balance\n\r"
	"{09|{00  {04TIME     {00 Check your quest timer\n\r"
	"{09|{00  {04REQUEST  {00 Seek a quest from the questmaster\n\r"
	"{09|{00  {04COMPLETE {00 Turn in a finished quest\n\r"
	"{09|{00  {04LIST     {00 Browse the quest shop\n\r"
	"{09|{00  {04BUY      {00 Purchase a quest reward\n\r"
	"{09|{00  {04GAMBLE   {00 Double-or-nothing your pending points\n\r"
	"{09|{00  {04ABORT    {00 Give up your current quest\n\r"
	"{09'---------------------------------------------------------------'{00\n\r",
	ch);
    return;
}

static bool automatic_quest_target_is_suitable( CHAR_DATA *ch,
                                                CHAR_DATA *questman,
                                                CHAR_DATA *victim )
{
    MOB_INDEX_DATA *index;
    ROOM_INDEX_DATA *room;

    if ( victim == NULL || !IS_NPC(victim) || victim == questman
    ||   victim->pIndexData == NULL || victim->in_room == NULL
    ||   ch->level > 59 )
        return false;

    index = victim->pIndexData;
    room = victim->in_room;
    if ( index->level <= 2 || index->level >= ch->level
    ||   IS_SET(index->imm_flags, IMM_SUMMON)
    ||   index->pShop != NULL
    ||   IS_SET(index->act, ACT_GAIN)
    ||   IS_SET(index->act, ACT_TRAIN)
    ||   IS_SET(index->act, ACT_PRACTICE)
    ||   IS_SET(index->act, ACT_IS_HEALER)
    ||   IS_SET(index->act, ACT_NOKILL)
    ||   IS_SET(index->act, ACT_QUESTM)
    ||   IS_SET(index->act, ACT_PET)
    ||   IS_SET(index->affected_by, AFF_CHARM)
    ||   IS_SET(index->affected_by2, AFF2_GHOST)
    ||   IS_AFFECTED(victim, AFF_CHARM)
    ||   IS_AFFECTED2(victim, AFF2_GHOST)
    ||   !can_see(ch, victim)
    ||   !can_see_room(ch, room)
    ||   room_is_private(room)
    ||   IS_SET(room->room_flags, ROOM_SAFE)
    ||   IS_SET(room->room_flags, ROOM_DT)
    ||   IS_SET(room->room_flags, ROOM_JAIL) )
        return false;

    return true;
}

void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)
{
    CHAR_DATA *victim;
    CHAR_DATA *candidate;
    ROOM_INDEX_DATA *room;
    OBJ_DATA *questitem;
    char buf [MAX_STRING_LENGTH];
    LIST_ITERATOR iter;
    int candidate_count = 0;

    /* Choose uniformly from suitable live mobiles. The same target pool is
       used for kill and recovery quests so the destination remains level-
       appropriate and accessible to the requesting player. */

    victim = NULL;
    FOR_EACH_CHARACTER( iter, candidate )
    {
	if ( !automatic_quest_target_is_suitable(ch, questman, candidate) )
	    continue;
	if ( number_range(1, ++candidate_count) == 1 )
	    victim = candidate;
    }

    if ( victim == NULL )
    {
	snprintf(buf, sizeof(buf),
	    "My apologies, %s - there are no suitable quests at the moment.",
	    ch->name);
	do_say(questman, buf);
	do_say(questman, "Please try again shortly.");
	ch->nextquest = 5;
        return;
    }

    room = victim->in_room;

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

	/* Q3: guard against missing quest object vnum */
	{
	    OBJ_INDEX_DATA *qidx = get_obj_index(objvnum);
	    if (qidx == NULL)
	    {
		snprintf(buf, sizeof(buf),
		    "My apologies, %s - the quest item is unavailable right now.",
		    ch->name);
		do_say(questman, buf);
		ch->nextquest = 5;
		return;
	    }
	    questitem = create_object(qidx, ch->level);
	}
	questitem->value[4] = quest_token_owner_tag(ch);
	questitem->timer = 120;
	questitem->owner = str_dup(ch->name);
	obj_to_room(questitem, room);
	ch->questobj = questitem->pIndexData->vnum;

	switch (number_range(0, 2))
	{
	    case 0:
		snprintf(buf, sizeof(buf),
		    "Bandits have made off with %s!", questitem->short_descr);
		do_say(questman, buf);
		do_say(questman, "Recover it and you'll be rewarded with quest points!");
		break;
	    case 1:
		snprintf(buf, sizeof(buf),
		    "Raiders stole %s from the realm!", questitem->short_descr);
		do_say(questman, buf);
		do_say(questman, "Bring it back and I'll make it worth your while!");
		break;
	    case 2:
		snprintf(buf, sizeof(buf),
		    "A prized artifact - %s - has gone missing!", questitem->short_descr);
		do_say(questman, buf);
		do_say(questman, "Find it and I'll reward you handsomely in quest points!");
		break;
	}

	snprintf(buf, sizeof(buf),
	    "It was last spotted near %s, in the %s region.",
	    room->name, room->area->name);
	do_say(questman, buf);
	return;
    }

    /* Quest to kill a mob */

    else
    {
    switch(number_range(0,3))
    {
	case 0:
        snprintf(buf, sizeof(buf), "%s has been declared an outlaw!",victim->short_descr);
	do_say(questman,buf);
        do_say(questman, "Hunt them down before they cause more trouble!");
	break;

	case 1:
	snprintf(buf, sizeof(buf), "The criminal known as %s has escaped from prison!",victim->short_descr);
	do_say(questman,buf);
	snprintf(buf, sizeof(buf), "Since the escape, they've slain %d innocent people!",number_range(2,20));
	do_say(questman,buf);
	do_say(questman,"You must find and stop them!");
	break;

	case 2:
	snprintf(buf, sizeof(buf), "A bounty has been posted on %s.",victim->short_descr);
	do_say(questman,buf);
	do_say(questman, "Eliminate this threat and collect your reward!");
	break;

	case 3:
	snprintf(buf, sizeof(buf), "%s threatens the peace of the realm!",victim->short_descr);
	do_say(questman,buf);
	snprintf(buf, sizeof(buf), "Deal with them before %d more innocents suffer!",number_range(3,15));
	do_say(questman,buf);
	break;
    }

    if (room->name != NULL)
    {
	snprintf(buf, sizeof(buf),
	    "Your quarry was last spotted near %s, in the %s region.",
	    room->name, room->area->name);
	do_say(questman,buf);
    }

  /* Guard: vnum must be positive and within hash range. */

       if (victim->pIndexData->vnum > 0)
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
    CHAR_DATA *ch;
    LIST_ITERATOR iter;

    FOR_EACH_CHARACTER( iter, ch )
    {
        if (IS_NPC(ch)) continue;

        if (ch->nextquest > 0)
        {
            ch->nextquest--;

            if (ch->nextquest == 0)
            {
                send_to_char("You may now quest again.\n\r",ch);
		save_char_obj(ch);
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
                if (ch->queststreak > 0)
                {
                    snprintf(buf, sizeof(buf),
                        "Your winning streak of %d is lost from failing to complete in time!\n\r",
                        ch->queststreak);
                    send_to_char(buf, ch);
                }
		ch->queststreak = 0;
		remove_automatic_quest_tokens(ch);
                REMOVE_BIT(ch->act, PLR_QUESTOR);
                ch->questgiver = NULL;
                ch->countdown = 0;
                ch->questmob = 0;
                ch->questobj = 0;
		ch->questrush = false;
		save_char_obj(ch);
            }
            if (ch->countdown > 0 && ch->countdown < 6)
            {
		switch (ch->countdown)
		{
		    case 5:
			send_to_char(
			    "{0AQuest Warning:{00 Only 5 minutes remaining!\n\r", ch);
			break;
		    case 4:
		    case 3:
			send_to_char(
			    "{0C** Quest Warning: Time is running out! **{00\n\r", ch);
			break;
		    case 2:
			send_to_char(
			    "{0C** Quest Warning: 2 minutes left - hurry! **{00\n\r", ch);
			if (ch->questrush)
			    send_to_char(
				"{0C** RUSH CONTRACT: Don't lose that double reward! **{00\n\r", ch);
			break;
		    case 1:
			send_to_char(
			    "{07** FINAL MINUTE! Complete your quest NOW! **{00\n\r", ch);
			break;
		    default:
			break;
		}
                continue;
            }
        }
    }
}
