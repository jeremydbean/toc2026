/**************************************************************************
 * SEGROMv1 was written and concieved by Eclipse<Eclipse@bud.indirect.com *
 * Soulcrusher <soul@pcix.com> and Gravestone <bones@voicenet.com> all    *
 * rights are reserved.  This is based on the original work of the DIKU   *
 * MERC coding team and Russ Taylor for the ROM2.3 code base.             *
 **************************************************************************/


#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <time.h>
#include "merc.h"
#include "interp.h"
#include "magic.h"

/* command procedures needed */
DECLARE_DO_FUN(do_look	);
DECLARE_DO_FUN(do_switch);
DECLARE_DO_FUN(do_return);
DECLARE_DO_FUN(do_cast  );
DECLARE_DO_FUN(do_echo  );
DECLARE_DO_FUN(do_drop  );
DECLARE_DO_FUN(do_slay  );

void	check_killer	args( ( CHAR_DATA *ch, CHAR_DATA *victim ) );
bool    check_dispel    args( ( int dis_level, CHAR_DATA *victim, int sn) );

/*
 * The kludgy global is for spells who want more stuff from command line.
 */
extern char *target_name;

extern void say_spell   args( ( CHAR_DATA *ch, int sn ) );
extern void set_fighting args( ( CHAR_DATA *ch, CHAR_DATA *victim ) );
extern  const char * dir_name	[];
extern ROOM_INDEX_DATA *	room_index_hash		[MAX_KEY_HASH];
extern int top_room;
extern AREA_DATA * new_area;

#define MOB_VNUM_PSIONIC_PROJECTION 7550

static bool psionic_defense_active( CHAR_DATA *victim )
{
    return is_affected( victim, gsn_psionic_armor )
        || is_affected( victim, gsn_psychic_shield )
        || is_affected( victim, gsn_mindbar );
}

static int psionic_reduce_mental_drain( CHAR_DATA *victim, int amount )
{
    if ( is_affected( victim, gsn_psionic_armor )
    ||   is_affected( victim, gsn_psychic_shield ) )
        amount -= amount / 4;
    else if ( is_affected( victim, gsn_mindbar ) )
        amount /= 2;

    return UMAX( 0, amount );
}

static bool psionic_remote_room_blocked( CHAR_DATA *ch,
                                         ROOM_INDEX_DATA *room,
                                         bool block_safe,
                                         bool block_no_recall )
{
    if ( room == NULL
    ||   !can_see_room( ch, room )
    ||   room_is_private( room )
    ||   IS_SET( room->room_flags, ROOM_PRIVATE )
    ||   IS_SET( room->room_flags, ROOM_SOLITARY )
    ||   IS_SET( room->room_flags, ROOM_JAIL )
    ||   IS_SET( room->room_flags, ROOM_DT )
    ||   IS_SET( room->room_flags, ROOM_GODS_ONLY )
    ||   IS_SET( room->room_flags, ROOM_IMP_ONLY )
    ||   IS_SET( room->room_flags, ROOM_NEWBIES_ONLY )
    ||   IS_SET( room->room_flags2, ROOM2_NO_TPORT ) )
        return true;

    if ( block_safe && IS_SET( room->room_flags, ROOM_SAFE ) )
        return true;

    if ( block_no_recall && IS_SET( room->room_flags, ROOM_NO_RECALL ) )
        return true;

    return false;
}

static bool psionic_switch_into( CHAR_DATA *ch, CHAR_DATA *projection )
{
    if ( ch == NULL || projection == NULL || ch->desc == NULL
    ||   ch->desc->original != NULL || projection->desc != NULL )
        return false;

    ch->desc->character = projection;
    ch->desc->original  = ch;
    projection->desc    = ch->desc;
    ch->desc             = NULL;
    projection->comm     = ch->comm;
    projection->lines    = ch->lines;
    return true;
}

static void psionic_start_combat( CHAR_DATA *ch, CHAR_DATA *victim )
{
    if ( ch == NULL || victim == NULL || ch == victim )
        return;

    check_killer( ch, victim );

    if ( ch->fighting == NULL && ch->position > POS_STUNNED )
        set_fighting( ch, victim );
    if ( victim->fighting == NULL && victim->position > POS_STUNNED )
        set_fighting( victim, ch );
}

static int lore_estimate( int value )
{
    int half = value / 2;
    int twice = value * 2;

    return number_range( UMIN(half, twice), UMAX(half, twice) );
}

/* Temp version of Lore. Needs work. */
void do_lore( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *obj;
    AFFECT_DATA *paf;
    int chance;
    int check = 0;
    int stat1 = 0;
    int stat2 = 0;
    int research_cost;
    int i;

    if(IS_NPC(ch) )
       return;

    argument = one_argument (argument, arg);

    if ( arg[0] == '\0' )
    {
	send_to_char( "Use your Lore knowledge on what?\n\r", ch );
	return;
    }

    if ( ( obj = get_obj_carry( ch, arg ) ) == NULL )
    {
      send_to_char( "You do not have that item.\n\r", ch );
      return;
    }


    if( IS_SET(obj->extra_flags, ITEM_NOIDENTIFY) )
    {
      send_to_char("It appears to be magical.\n\r",ch);
      return;
    }


    if( (chance = ch->pcdata->learned[gsn_lore]) < 1)
       return;

    research_cost = UMAX( 0,
        obj->level * 20 - ( chance * 2 + ch->level / 2 ) );
    if (!has_enough_gold(ch, research_cost))
    {
      send_to_char("You don't have enough gold for the research.\n\r",ch);
      return;
    }

    if ( research_cost > 0 )
    {
      add_money(ch, -research_cost);
      save_char_obj(ch);
    }

    WAIT_STATE( ch, skill_table[gsn_lore].beats );

    snprintf( buf, sizeof(buf), "The %s is a %s of some sort, and weights around %d stone.\n\r",
        obj->name,
        item_type_name( obj ),
        lore_estimate(obj->weight) );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf), "Looking it over closely, you estimate it's worth about %d gold.\n\r",
        lore_estimate(obj->cost) );
    send_to_char( buf, ch );


    switch ( obj->item_type )
    {
    case ITEM_SCROLL:
    case ITEM_POTION:
    case ITEM_PILL:
        snprintf( buf, sizeof(buf), "Level %d spells of:",
        lore_estimate(obj->value[0]) );
        send_to_char( buf, ch );

        for ( i = 1; i <= 3; i++ )
        {
          if ( obj->value[i] >= 0 && obj->value[i] < MAX_SKILL
          &&   number_percent() <= chance )
          {
            send_to_char( " '", ch );
            send_to_char( skill_table[obj->value[i]].name, ch );
            send_to_char( "'", ch );
            check++;
          }
        }
        if( check < 1)
            send_to_char("Unknown",ch);

        send_to_char( ".\n\r", ch );
        break;

    case ITEM_WAND:
    case ITEM_STAFF:
        snprintf( buf, sizeof(buf), "The %s has %d(%d) charges of level %d,",
            obj->item_type == ITEM_WAND ? "wand" : "staff",
            lore_estimate(obj->value[1]),
            lore_estimate(obj->value[2]),
            lore_estimate(obj->value[0]) );
	send_to_char( buf, ch );

	if( number_percent () < chance )
	{
	  if ( obj->value[3] >= 0 && obj->value[3] < MAX_SKILL )
	  {
	    send_to_char( " '", ch );
	    send_to_char( skill_table[obj->value[3]].name, ch );
	    send_to_char( "'", ch );
	  }
	}
        else
            send_to_char("\n\rof a spell you can't seem to determine",ch);

        send_to_char( ".\n\r", ch );
        break;

    case ITEM_WEAPON:
	send_to_char("Weapon type is ",ch);
	switch (obj->value[0])
	{
	    case(WEAPON_EXOTIC) : send_to_char("exotic.\n\r",ch);	break;
	    case(WEAPON_SWORD)  : send_to_char("sword.\n\r",ch);	break;
	    case(WEAPON_DAGGER) : send_to_char("dagger.\n\r",ch);	break;
	    case(WEAPON_SPEAR)	: send_to_char("spear/staff.\n\r",ch);	break;
	    case(WEAPON_MACE) 	: send_to_char("mace/club.\n\r",ch);	break;
	    case(WEAPON_AXE)	: send_to_char("axe.\n\r",ch);		break;
	    case(WEAPON_FLAIL)	: send_to_char("flail.\n\r",ch);	break;
	    case(WEAPON_WHIP)	: send_to_char("whip.\n\r",ch);		break;
	    case(WEAPON_POLEARM): send_to_char("polearm.\n\r",ch);	break;
	case(WEAPON_BOW)        : send_to_char("bow.\n\r",ch);          break;
	    default		: send_to_char("unknown.\n\r",ch);	break;
	}

	if( number_percent () < chance )
	{
	    stat1 = number_range(obj->value[1]/2, obj->value[1] + 5);
	    stat2 = number_range(obj->value[2]/2, obj->value[2] + 5);
	    check += 1;
	    snprintf(buf, sizeof buf,"Damage is %dd%d (average %d).\n\r",
		stat1,
		stat2,
		stat1 * ( stat2 + 1 ) / 2);
	}

	if( check > 0)
	  send_to_char( buf, ch );
	else
	  send_to_char("Your not sure what it's combat values are",ch);
	break;

    case ITEM_ARMOR:
        snprintf( buf, sizeof(buf),
        "Armor class is %d pierce, %d bash, %d slash, and %d vs. magic.\n\r",
            lore_estimate(obj->value[0]),
            lore_estimate(obj->value[1]),
            lore_estimate(obj->value[2]),
            lore_estimate(obj->value[3]) );
        send_to_char( buf, ch );
        break;
    }
/* BB
    if (!obj->enchanted)
*/
    for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
    {
	if ( paf->location != APPLY_NONE && paf->modifier != 0 )
	{
            snprintf( buf, sizeof(buf), "Affects %s by %d.\n\r",
                affect_loc_name( paf->location ),
                lore_estimate(paf->modifier) );
            send_to_char( buf, ch );
        }
    }

    for ( paf = obj->affected; paf != NULL; paf = paf->next )
    {
	if ( paf->location != APPLY_NONE && paf->modifier != 0 )
	{
            snprintf( buf, sizeof(buf), "Affects %s by %d.\n\r",
                affect_loc_name( paf->location ),
                lore_estimate(paf->modifier) );
            send_to_char( buf, ch );
        }
    }

    check_improve(ch,gsn_lore,true,5);
    return;
}

/*   psi, same as wizard eye  */
void do_project( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    ROOM_INDEX_DATA *in_room;
    ROOM_INDEX_DATA *to_room;
    MOB_INDEX_DATA *pMobIndex;
    CHAR_DATA *victim;
    int chance;
    int level;
    int door;
    int move;


    if ( IS_NPC(ch) || (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
        return;

    argument = one_argument (argument, arg);

    if ( (chance = get_skill(ch, gsn_project)) == 0 )
    {
	send_to_char("Do what?\n\r",ch);
	return;
    }

    if ( arg[0] == '\0' )
    {
	 send_to_char( "Specify a direction.\n\r", ch);
	 return;
    }
	    if ( !str_cmp( arg, "n" ) || !str_cmp( arg, "north" ) ) door = 0;
    else if ( !str_cmp( arg, "e" ) || !str_cmp( arg, "east"  ) ) door = 1;
    else if ( !str_cmp( arg, "s" ) || !str_cmp( arg, "south" ) ) door = 2;
    else if ( !str_cmp( arg, "w" ) || !str_cmp( arg, "west"  ) ) door = 3;
    else if ( !str_cmp( arg, "u" ) || !str_cmp( arg, "up"    ) ) door = 4;
    else if ( !str_cmp( arg, "d" ) || !str_cmp( arg, "down"  ) ) door = 5;
    else if ( !str_cmp( arg, "ne" ) || !str_cmp( arg, "northeast"  ) ) door = 6;
    else if ( !str_cmp( arg, "nw" ) || !str_cmp( arg, "northwest"  ) ) door = 7;
    else if ( !str_cmp( arg, "se" ) || !str_cmp( arg, "southeast"  ) ) door = 8;
    else if ( !str_cmp( arg, "sw" ) || !str_cmp( arg, "southwest"  ) ) door = 9;
    else
    {
	send_to_char("That's not a direction.\n\r",ch);
	return;
    }

    if ( ch->desc == NULL || ch->desc->original != NULL )
    {
        send_to_char( "Your spirit cannot leave your body right now.\n\r", ch );
        return;
    }

    if ( (pMobIndex = get_mob_index(MOB_VNUM_PSIONIC_PROJECTION)) == NULL )
    {
        bug( "Do_project: projection mobile %d is missing.",
             MOB_VNUM_PSIONIC_PROJECTION );
        send_to_char( "The astral plane is unavailable right now.\n\r", ch );
        return;
    }

    if ( ch->mana < 25 )
    {
	 send_to_char("You don't have enough mana.\n\r",ch);
	 return;
    }

    if ( number_percent() > chance )
    {
        send_to_char( "You lost your concentration.\n\r", ch );
        ch->mana -= 5;
        check_improve( ch, gsn_project, false, 4 );
        return;
    }

    ch->mana -= 25;

    victim = create_mobile( pMobIndex );
    char_to_room( victim, ch->in_room );

    level = ch->level/4;
    in_room = ch->in_room;

    act( "Your spirit rises out of your body and floats off to the $t.", ch,
		dir_name[door], NULL, TO_CHAR );

    if( number_percent () > 50)
	 act( "A glowing aura rises out of $n and drifts off to the $t.", ch,
		 dir_name[door], NULL, TO_ROOM );

    if ( !psionic_switch_into(ch, victim) )
    {
        extract_char( victim, true );
        ch->mana = (sh_int)(UMIN(ch->max_mana, ch->mana + 25));
        send_to_char( "Your spirit cannot separate from your body.\n\r", ch );
        return;
    }

    for ( move = 0; move <= level; move++ )
    {
        EXIT_DATA *pexit;

        if ( (pexit = in_room->exit[door]) == NULL
        ||   (to_room = pexit->u1.to_room) == NULL
        ||   IS_SET(pexit->exit_info, EX_SECRET)
        ||   IS_SET(pexit->exit_info, EX_WIZLOCKED)
        ||   psionic_remote_room_blocked(ch, to_room, false, false) )
        {
            send_to_char( "Your spirit has run into an impassable barrier.\n\r",
                          victim );
            send_to_char( "You return to your body.\n\r", victim );
            do_return( victim, "" );
            extract_char( victim, true );
            check_improve( ch, gsn_project, true, 4 );
            WAIT_STATE( ch, skill_table[gsn_project].beats );
            return;
        }

        char_from_room( victim );
        char_to_room( victim, to_room );
        do_look( victim, "auto" );
        if ( number_percent() > 50 )
            act( "You notice a ghostly figure out of the corner of your eye.",
                 victim, NULL, NULL, TO_ROOM );
        send_to_char( "\n\r", victim );
        in_room = victim->in_room;
    }

    send_to_char("You reach the end of your astral endurance.\n\r",victim );
    send_to_char( "You return to your body.\n\r", victim );

    do_return( victim, "" );
    extract_char( victim, true );
    check_improve( ch, gsn_project, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_project].beats );
    return;

}

/* psi */
void do_mindleech( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    int chance;
    int drain;
    bool resisted;

    one_argument( argument, arg );

    if ( !IS_NPC(ch) )
    {
        if ( (chance = get_skill(ch, gsn_mindleech)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }

        if ( arg[0] == '\0' && ch->fighting == NULL )
        {
            send_to_char( "Who do you want to leech?\n\r", ch );
            return;
        }
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
        {
            send_to_char( "They aren't here.\n\r", ch );
            return;
        }

        if ( victim == ch )
        {
            send_to_char( "You cannot leech yourself.\n\r", ch );
            return;
        }

        if ( ch->mana < 30 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( is_safe_spell(ch, victim, false) )
        {
            act( "$N cannot be harmed by you.", ch, NULL, victim, TO_CHAR );
            return;
        }

        if ( IS_AFFECTED2(victim, AFF2_GHOST) || IS_AFFECTED2(ch, AFF2_GHOST) )
        {
            send_to_char( "Ghosts have no mind to leech.\n\r", ch );
            return;
        }

        if ( victim->fighting != NULL && !is_same_group(ch, victim->fighting) )
        {
            send_to_char( "Kill stealing is not permitted.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve(ch, gsn_mindleech, false, 4);
            return;
        }

        ch->mana -= 30;
    }
    else
    {
        if ( IS_SET(ch->act, ACT_PET) || IS_SET(ch->affected_by, AFF_CHARM) ||
             (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;

        if ( arg[0] == '\0' && ch->fighting == NULL )
            return;
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
            return;

        if ( victim == ch )
            return;

        if ( is_safe_spell(ch, victim, false)
        ||   IS_AFFECTED2(victim, AFF2_GHOST)
        ||   IS_AFFECTED2(ch, AFF2_GHOST) )
            return;
    }

    /* Amount to drain scales with caster level. */
    drain = number_range( ch->level * 2, ch->level * 3 );
    resisted = saves_spell( ch->level, victim );
    if ( resisted )
        drain /= 2;
    drain = psionic_reduce_mental_drain( victim, drain );
    drain = UMIN( drain, victim->mana );

    if ( drain > 0 )
    {
        psionic_start_combat( ch, victim );
        victim->mana -= drain;
        /* Caster absorbs half the drained mana. */
        ch->mana = (sh_int)(UMIN( ch->max_mana, ch->mana + drain / 2 ));
        act( "You reach into $N's mind and siphon away their mental energy!", ch, NULL, victim, TO_CHAR );
        act( "$n reaches into your mind, draining your mental energy!", ch, NULL, victim, TO_VICT );
        act( "$n's eyes glow as $e leeches $N's mental energy.", ch, NULL, victim, TO_NOTVICT );
    }
    else
    {
        /* Target has no mana, so the failed drain becomes mental damage. */
        drain = number_range( ch->level, ch->level * 2 );
        if ( resisted )
            drain /= 2;
        act( "You probe $N's empty mind and the shock damages $M!", ch, NULL, victim, TO_CHAR );
        act( "$n probes your empty mind and the backlash hurts!", ch, NULL, victim, TO_VICT );
        if (damage( ch, victim, drain, gsn_mindleech, DAM_MENTAL ))
        {
            /* victim was killed — skip the fight-start block */
            check_improve(ch, gsn_mindleech, true, 4);
            WAIT_STATE(ch, skill_table[gsn_mindleech].beats);
            return;
        }
    }

    check_improve(ch, gsn_mindleech, true, 4);
    WAIT_STATE(ch, skill_table[gsn_mindleech].beats);

    return;
}

/* psi */
void do_enervate( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    int chance;
    int hp_drain;
    int move_drain;
    int victim_hit_before;
    int actual_damage;
    bool resisted;

    one_argument( argument, arg );

    if ( !IS_NPC(ch) )
    {
        if ( (chance = get_skill(ch, gsn_enervate)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }

        if ( arg[0] == '\0' && ch->fighting == NULL )
        {
            send_to_char( "Who do you want to enervate?\n\r", ch );
            return;
        }
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
        {
            send_to_char( "They aren't here.\n\r", ch );
            return;
        }

        if ( victim == ch )
        {
            send_to_char( "You would only drain yourself.\n\r", ch );
            return;
        }

        if ( ch->mana < 35 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( is_safe_spell(ch, victim, false) )
        {
            act( "$N cannot be harmed by you.", ch, NULL, victim, TO_CHAR );
            return;
        }

        if ( IS_AFFECTED2(victim, AFF2_GHOST) || IS_AFFECTED2(ch, AFF2_GHOST) )
        {
            send_to_char( "Ghosts have no vitality to drain.\n\r", ch );
            return;
        }

        if ( victim->fighting != NULL && !is_same_group(ch, victim->fighting) )
        {
            send_to_char( "Kill stealing is not permitted.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve(ch, gsn_enervate, false, 4);
            return;
        }

        ch->mana -= 35;
    }
    else
    {
        if ( IS_SET(ch->act, ACT_PET) || IS_SET(ch->affected_by, AFF_CHARM) ||
             (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;

        if ( arg[0] == '\0' && ch->fighting == NULL )
            return;
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
            return;

        if ( victim == ch )
            return;

        if ( is_safe_spell(ch, victim, false)
        ||   IS_AFFECTED2(victim, AFF2_GHOST)
        ||   IS_AFFECTED2(ch, AFF2_GHOST) )
            return;
    }

    /* Drain endurance (move) and absorb half back. */
    resisted = saves_spell( ch->level, victim );
    move_drain = number_range( ch->level, ch->level * 2 );
    if ( resisted )
        move_drain /= 2;
    move_drain = psionic_reduce_mental_drain( victim, move_drain );
    move_drain = UMIN( move_drain, victim->move );
    if ( move_drain > 0 )
    {
        victim->move -= move_drain;
        ch->move = (sh_int)(UMIN( ch->max_move, ch->move + move_drain / 2 ));
    }

    /* Deal HP damage and absorb half as healing. */
    hp_drain = number_range( ch->level, ch->level * 2 );
    if ( resisted )
        hp_drain /= 2;

    act( "You tear the life force from $N, drinking in $S vitality!", ch, NULL, victim, TO_CHAR );
    act( "$n tears your life force away, leaving you weakened and spent!", ch, NULL, victim, TO_VICT );
    act( "$n's eyes dim as $e drains $N's very life and endurance.", ch, NULL, victim, TO_NOTVICT );

    victim_hit_before = victim->hit;
    if (damage( ch, victim, hp_drain, gsn_enervate, DAM_MENTAL ))
    {
        /* victim was killed — skip healing and fight-start */
        check_improve(ch, gsn_enervate, true, 4);
        WAIT_STATE(ch, skill_table[gsn_enervate].beats);
        return;
    }

    /* Heal only from damage that actually passed saves, defenses, and immunity. */
    actual_damage = UMAX( 0, victim_hit_before - victim->hit );
    ch->hit = (sh_int)(UMIN( ch->max_hit, ch->hit + actual_damage / 2 ));

    check_improve(ch, gsn_enervate, true, 4);
    WAIT_STATE(ch, skill_table[gsn_enervate].beats);

    return;
}

/* psi */
void do_mindblast( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *vch;
    bool found = false;
    LIST_ITERATOR iter;
    int chance;
    int level;

    static const int16_t dam_each[] =
    {
	 0,
	 0,  0,  0,  0,	 0,	 0,  0,  0, 0,  0,
	 0,  0,  0,  0,	 0,	 0,  0,  0, 30, 31,
	32, 33, 34, 35,	36,	37, 38, 39, 40, 41,
	42, 43, 44, 45,	46,	47, 48, 49, 50, 51,
	52, 53, 54, 55,	56,	56, 57, 58, 59, 60
    };
    int dam;

    one_argument( argument, arg );

    if ( IS_AFFECTED2(ch, AFF2_GHOST) )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "You cannot attack while in this form.\n\r", ch );
        return;
    }

    if(!IS_NPC(ch))
    {
	 if( (chance = get_skill(ch,gsn_mindblast)) == 0)
	 {
	   send_to_char("Do what?\n\r",ch);
	   return;
	 }

	 if( ch->mana < 50)
	 {
	   send_to_char("You don't have enough mana.\n\r",ch);
	   return;
	 }

	 if( number_percent( ) > chance )
	 {
	   send_to_char("You lost your concentration.\n\r",ch);
	   ch->mana -= 5;
	   check_improve(ch,gsn_mindblast,false,4);
	   return;
	 }
	 ch->mana -= 50;
    }
	if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	    (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

    level = ch->level;

    FOR_EACH_CHARACTER( iter, vch )
    {

	if ( vch->in_room == NULL )
	    continue;

        if ( IS_AFFECTED2(vch, AFF2_GHOST ) )
            continue;

	if ( vch->in_room == ch->in_room )
	{
	if ( vch != ch && !is_safe_spell(ch,vch,true) )
	{
	 level	= UMIN(level, (int)(sizeof(dam_each)/sizeof(dam_each[0]) - 1));
	 level	= UMAX(0, level);
	 dam		= number_range( dam_each[level] / 2, dam_each[level] * 2 );
	 if ( saves_spell( level, vch ) )
	   dam /= 2;
         act("Blood oozes from $N's ears.",ch,NULL,vch,TO_ROOM);
	 act("Blood oozes from $N's ears.",ch,NULL,vch,TO_CHAR);
	 damage( ch, vch, dam, gsn_mindblast, DAM_MENTAL );
	 found = true;
        }
	 continue;
	}

	if ( vch->in_room->area == ch->in_room->area )
	 send_to_char( "A wave of vertigo hits you, then slowly passes.\n\r", vch );
    }

    check_improve(ch,gsn_mindblast,true, 4);
    WAIT_STATE(ch,skill_table[gsn_mindblast].beats);

    if(!found)
	 send_to_char("Your mindblast didn't affect anyone.\n\r",ch);

    return;
}

/* psi */
void do_nightmare( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim = NULL;
    AFFECT_DATA af;
    int dream;
    int chance;
    int level;

    one_argument( argument, arg );

    level = ch->level;

    if(!IS_NPC(ch))
    {
	 if(( chance = get_skill(ch,gsn_nightmare)) == 0 )
	 {
	  send_to_char("Do what?\n\r",ch);
	  return;
	 }

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Who do you want to give nightmares to?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	     victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if( victim == ch)
	   return;

	 if( ch->mana < 20)
	 {
	   send_to_char("You don't have enough mana.\n\r",ch);
	   return;
	 }

	 if(is_safe_spell(ch,victim,false))
	 {
	   act("$N cannot be harmed by you.",ch,NULL,victim,TO_CHAR);
		return;
	 }

         if ( IS_AFFECTED2(victim, AFF2_GHOST ) )
         {
           act("Your attack passes right thru $N!",ch,NULL,victim,TO_CHAR);
           act("$n's attack passes right thru $N!",ch,NULL,victim,TO_ROOM);
           return;
         }

         if ( IS_AFFECTED2(ch, AFF2_GHOST ) )
         {
           send_to_char("You cannot attack while in this form.\n\r",ch);
           return;
         }

	 if ( victim->fighting != NULL && !is_same_group(ch,victim->fighting))
	 {
	   send_to_char("Kill stealing is not permitted.\n\r",ch);
	   return;
	 }

         if ( is_affected(victim, gsn_nightmare) )
         {
             act( "$N is already trapped in a nightmare.",
                  ch, NULL, victim, TO_CHAR );
             return;
         }

	 if( number_percent( ) > chance )
	 {
	   send_to_char("You lost your concentration.\n\r",ch);
	   ch->mana -= 5;
	   check_improve(ch,gsn_nightmare,false,4);
	   return;
	 }
    ch->mana -= 20;
    }
    else
    {

	if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	    (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Who do you want to give nightmares to?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	   victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if( victim == ch)
	    return;
    }

    if ( is_affected(victim, gsn_nightmare) )
    {
        if ( !IS_NPC(ch) )
            act( "$N is already trapped in a nightmare.",
                 ch, NULL, victim, TO_CHAR );
        return;
    }

    if ( saves_spell(level, victim) )
    {
        send_to_char( "You failed.\n\r", ch );
        psionic_start_combat( ch, victim );
        check_improve( ch, gsn_nightmare, false, 4 );
        WAIT_STATE( ch, skill_table[gsn_nightmare].beats );
        return;
    }

    dream = number_range( level/2, level * 3 );
    if(dream > victim->mana)
	 dream = victim->mana;

    af.type      = gsn_nightmare;
    af.level     = (sh_int)(level);
    af.duration  = (sh_int)(level/3);
    af.location  = APPLY_MANA;
    af.modifier  = (sh_int)(-1 * (dream));
    af.bitvector = 0;
    af.bitvector2= AFF2_NO_RECOVER;
    affect_to_char( victim, &af );

    if(!IS_NPC(ch) && IS_NPC(victim) )
    {
	af.location = APPLY_AC;
	af.modifier = (sh_int)(dice(level/2,3));
	affect_to_char( victim, &af);
    }

    send_to_char( "You scream as horrible visions enter your mind!\n\r",
			    victim );
    act("$n breaks out in a cold sweat.",victim,NULL,NULL,TO_ROOM);
    send_to_char( "Your victim is now seeing horrible visions.\n\r",ch);
    check_improve(ch,gsn_nightmare,true,4);
    WAIT_STATE( ch,skill_table[gsn_nightmare].beats);
    psionic_start_combat( ch, victim );

    return;
}

/* psi or cleric */
void spell_cure_nightmare( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    CHAR_DATA *victim = (CHAR_DATA *) vo;

	if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	    (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

    if ( !is_affected( victim, skill_lookup("nightmare") ) )
    {
	   if (victim == ch)
		send_to_char("You don't have problems sleeping.\n\r",ch);
	   else
		act("$N doesn't appear to have any problems sleeping.",ch,
		    NULL,victim,TO_CHAR);
	   return;
    }

    if (check_dispel(level,victim,skill_lookup("nightmare")))
    {
	send_to_char("The horrifying visions are gone.\n\r",victim);
	act("$n is no longer afraid of $s shadow.",victim,NULL,NULL,TO_ROOM);
    }
    else
	send_to_char("Spell failed.\n\r",ch);

    return;


}

/* psi */
void do_astral_walk( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    bool trans_pet;
    int chance = 0;

    one_argument( argument, arg );

    if ( !IS_NPC(ch) )
    {
        if ( (chance = get_skill(ch, gsn_astral_walk)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }
    }
    else if ( IS_SET(ch->act, ACT_PET)
         ||   IS_SET(ch->affected_by, AFF_CHARM)
         ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
        return;

    if ( arg[0] == '\0' )
    {
        send_to_char( "Whose mind do you want to walk toward?\n\r", ch );
        return;
    }

    victim = get_char_world( ch, arg );
    if ( victim == NULL
    ||   victim == ch
    ||   IS_IMMORTAL(victim)
    ||   (victim != NULL && victim->in_room == ch->in_room)
    ||   psionic_remote_room_blocked(ch, ch->in_room, false, true)
    ||   psionic_remote_room_blocked(ch, victim != NULL ? victim->in_room : NULL,
                                     true, true)
    ||   (victim != NULL
      && IS_SET(victim->in_room->room_flags, ROOM_NEWBIES_ONLY))
    ||   (victim != NULL && IS_NPC(victim)
      && IS_SET(victim->imm_flags, IMM_SUMMON))
    ||   (victim != NULL && !IS_NPC(victim)
      && IS_SET(victim->act, PLR_NOSUMMON)) )
    {
        send_to_char( "You cannot find a safe astral path to that target.\n\r", ch );
        return;
    }

    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < 70 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= 5;
            check_improve( ch, gsn_astral_walk, false, 4 );
            return;
        }
        ch->mana -= 70;
    }

    if ( IS_NPC(victim) && saves_spell(ch->level, victim) )
    {
        send_to_char( "The target resists your astral pull.\n\r", ch );
        check_improve( ch, gsn_astral_walk, false, 4 );
        WAIT_STATE( ch, skill_table[gsn_astral_walk].beats );
        return;
    }

    if (ch->pet != NULL && ch->in_room == ch->pet->in_room)
	trans_pet = true;
    else
	trans_pet = false;

    act("$n bows $s head, then shimmers and is gone.",ch,NULL,NULL,TO_ROOM);
    send_to_char("You feel disorientated.\n\r",ch);
    char_from_room(ch);
    char_to_room(ch,victim->in_room);

    act("There is a shimmering in the air, followed by the appearance of $n.",
	   ch, NULL,NULL,TO_ROOM);
    send_to_char("\n\r",ch);
    do_look(ch,"auto");

    if (trans_pet)
    {
	act("$n shimmers and is gone.",ch->pet,NULL,NULL,TO_ROOM);
	send_to_char("You feel disorientated for a moment.\n\r",ch->pet);
	char_from_room(ch->pet);
	char_to_room(ch->pet,victim->in_room);
	act("There is a shimmering in the air, followed by the appearance of $n.",
		ch->pet,NULL,NULL,TO_ROOM);
	do_look(ch->pet,"auto");
    }

    if ( !IS_IMMORTAL(ch) )
        ch->position = POS_STUNNED;
    check_improve( ch, gsn_astral_walk, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_astral_walk].beats );
    return;
}

/*  psi  */
void do_telekinesis( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    OBJ_DATA *obj;
    bool found = false;
    int chance;
    LIST_ITERATOR iter;

    one_argument( argument, arg );

    if ( IS_NPC(ch) )
        return;

    if ( ch->pcdata->on_quest )
    {
        send_to_char( "You must prove that you know the game. TK will not\n\r", ch );
        send_to_char( "function while you are on a Hero Quest.\n\r", ch );
        return;
    }

    if ( (chance = get_skill(ch, gsn_telekinesis)) == 0 )
    {
        send_to_char( "Do what?\n\r", ch );
        return;
    }

    if ( arg[0] == '\0' )
    {
        send_to_char( "You must specify an object.\n\r", ch );
        return;
    }

    if ( ch->mana < 50 )
    {
        send_to_char( "You don't have enough mana.\n\r", ch );
        return;
    }

    if ( number_percent() > chance / 2 && !IS_IMMORTAL(ch) )
    {
        send_to_char( "You lost your concentration.\n\r", ch );
        ch->mana -= (dice(1,5) + 3);
        check_improve( ch, gsn_telekinesis, false, 4 );
        return;
    }
    ch->mana -= 50;

        FOR_EACH_OBJECT( iter, obj )
        {


      /* item weight and item count fixes - Rico 9/9/98 */
      if (obj->item_type != ITEM_CORPSE_PC)
       {
    if ( ch->carry_number + get_obj_number( obj ) > can_carry_n( ch ) )
        continue;

    if ( query_carry_weight(ch) + get_obj_weight( obj ) > can_carry_w( ch ) )
        continue;
       }

	   if ( !is_full_name( arg, obj->name )
		|| obj->item_type == ITEM_TREASURE
		|| obj->item_type == ITEM_MONEY
		|| IS_OBJ_STAT(obj, ITEM_NOLOCATE)
		|| IS_SET(obj->extra_flags2, ITEM2_NO_TPORT)
		|| !can_see_obj(ch,obj)
		|| !CAN_WEAR(obj, ITEM_TAKE)
                || obj->level > ch->level
                || obj->carried_by != NULL
                || obj->in_obj != NULL
                || obj->in_room == NULL
                || psionic_remote_room_blocked(ch, obj->in_room, true, true)
                || !can_loot(ch, obj)
                || (obj->pIndexData != NULL
                 && obj->pIndexData->vnum >= OBJ_VNUM_QUEST_TOKEN_FIRST
                 && obj->pIndexData->vnum <= OBJ_VNUM_QUEST_TOKEN_LAST
                 && obj->value[4] != 0
                 && (!IS_IMMORTAL(ch)
                  && (ch->pcdata == NULL
                   || obj->value[4] != ch->pcdata->id + 1
                   || obj->owner == NULL
                   || str_cmp(obj->owner, ch->name)))) )
		   continue;

           found = true;
           snprintf(buf, sizeof buf,"%s has TK'd %s from room %d",ch->name,
                    obj->name,obj->in_room->vnum);
           wizinfo(buf, LEVEL_IMMORTAL);
           obj_from_room( obj );
           obj_to_char( obj, ch );
	   break;
	 }

    if ( !found )
	 act("Either you couldn't find the $T, or you aren't able to TK it.",ch,
		 NULL, arg, TO_CHAR);
    else
	 {
	 act("You concentrate and $T flies to your hand.",ch, NULL,
		obj->short_descr, TO_CHAR);
	 act("$n bows $s head and $T flies to $s hand.",ch, NULL,
		obj->short_descr, TO_ROOM);
	 }
    check_improve(ch,gsn_telekinesis,found,4);
    WAIT_STATE(ch,skill_table[gsn_telekinesis].beats);
    return;
}



/*
 * Confuse is a focused mental intrusion rather than a broad spell, so a psion
 * who holds concentration reaches any mind that is not specifically warded
 * against mental attack. A DAM_MENTAL-resistant target gets one bounded roll
 * to throw the intrusion off, scaled by level difference. These stay well
 * under the generic saves_spell() curve on purpose: that curve clamps to a 95%
 * resist rate against the negative saving throws most mobiles carry, which
 * made a mastered power fail nearly every attempt.
 */
#define CONFUSE_RESIST_BASE     25
#define CONFUSE_RESIST_MIN       5
#define CONFUSE_RESIST_MAX      50

/*  psi  */
void do_confuse( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim = NULL;
    AFFECT_DATA af;
    int chance = 0;
    int mana_cost;
    int psi_ward;

    one_argument(argument,arg);

    if ( !IS_NPC(ch) )
    {
        if ( (chance = get_skill(ch, gsn_confuse)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }
    }
    else if ( IS_SET(ch->act, ACT_PET)
         ||   IS_SET(ch->affected_by, AFF_CHARM)
         ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
        return;

    if ( arg[0] == '\0' && ch->fighting == NULL )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "Who do you want to confuse?\n\r", ch );
        return;
    }
    else if ( arg[0] == '\0' )
        victim = ch->fighting;
    else if ( (victim = get_char_room(ch, arg)) == NULL )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "They aren't here.\n\r", ch );
        return;
    }

    if ( victim == ch )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "You cannot confuse yourself.\n\r", ch );
        return;
    }

    if ( is_safe_spell(ch, victim, false) )
    {
        if ( !IS_NPC(ch) )
            act( "$N cannot be harmed by you.", ch, NULL, victim, TO_CHAR );
        return;
    }

    if ( IS_AFFECTED2(victim, AFF2_GHOST) || IS_AFFECTED2(ch, AFF2_GHOST) )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "Ghosts cannot be affected by this power.\n\r", ch );
        return;
    }

    if ( victim->fighting != NULL && !is_same_group(ch, victim->fighting) )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "Kill stealing is not permitted.\n\r", ch );
        return;
    }

    if ( is_affected(victim, gsn_confuse) )
    {
        act( "$N is already pretty confused.", ch, NULL, victim, TO_CHAR );
        return;
    }

    mana_cost = ch->level + 50;
    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < mana_cost )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve( ch, gsn_confuse, false, 4 );
            return;
        }
        ch->mana -= mana_cost;
    }

    psi_ward = check_immune( victim, DAM_MENTAL );

    if ( psi_ward == IS_IMMUNE )
    {
        act( "$N's mind is sealed against psionic intrusion.",
             ch, NULL, victim, TO_CHAR );
        act( "You feel $n groping at your thoughts and shrug it off.",
             ch, NULL, victim, TO_VICT );
        psionic_start_combat( ch, victim );
        check_improve( ch, gsn_confuse, false, 4 );
        WAIT_STATE( ch, skill_table[gsn_confuse].beats );
        return;
    }

    if ( psi_ward == IS_RESISTANT )
    {
        int resist_chance;

        resist_chance = URANGE( CONFUSE_RESIST_MIN,
                                CONFUSE_RESIST_BASE
                                    + (victim->level - ch->level),
                                CONFUSE_RESIST_MAX );

        if ( number_percent() <= resist_chance )
        {
            act( "$N resists your attempt to cloud $S mind.",
                 ch, NULL, victim, TO_CHAR );
            act( "You push $n's confusing presence out of your mind.",
                 ch, NULL, victim, TO_VICT );
            psionic_start_combat( ch, victim );
            check_improve( ch, gsn_confuse, false, 4 );
            WAIT_STATE( ch, skill_table[gsn_confuse].beats );
            return;
        }
    }

    af.type       = gsn_confuse;
    af.level      = (sh_int)(ch->level);
    af.duration   = (sh_int)(4 + (ch->level >= 30) + (ch->level >= 40));
    af.modifier   = 0;
    af.location   = APPLY_NONE;
    af.bitvector  = 0;
    af.bitvector2 = AFF2_STUNNED;
    affect_to_char( victim, &af );
    act( "You feel very confused.", victim, NULL, NULL, TO_CHAR );
    act( "$n looks very confused.", victim, NULL, NULL, TO_NOTVICT );

    psionic_start_combat( ch, victim );
    check_improve( ch, gsn_confuse, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_confuse].beats );

    return;
}
/* psi */
void do_clairvoyance( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    ROOM_INDEX_DATA *was_in_room;
    CHAR_DATA *victim;
    int chance;

    one_argument(argument,arg);

    if(!IS_NPC(ch))
    {
	if ( (chance = get_skill(ch,gsn_clairvoyance)) == 0 )
	 {
	   send_to_char("Do what?\n\r",ch);
	   return;
	 }

	 if( arg[0] == '\0')
	 {
	   send_to_char( "Who do you want to snoop on?\n\r", ch );
	   return;
	 }

	 if ( ( victim = get_char_world( ch, arg ) ) == NULL
	    ||  psionic_remote_room_blocked(ch, victim->in_room, false, false) )
	 {
	   send_to_char( "They aren't here.\n\r", ch );
	   return;
	 }

         if( IS_IMMORTAL(victim) && !IS_NPC(victim) )
         {
           send_to_char( "Scrying Immortals is not a good idea.\n\r", ch );
           return;
         }

         if ( victim == ch )
         {
           send_to_char( "You get an image of yourself.\n\r", ch );
           return;
         }

	 if( ch->mana < 25)
	 {
	   send_to_char("You don't have enough mana.\n\r",ch);
	   return;
	 }

	 if ( number_percent( ) > chance )
	 {
	   send_to_char("All you can see is a fuzzy image.\n\r",ch);
	   check_improve(ch,gsn_clairvoyance,false,4);
	   ch->mana -= (dice(1,5) +3);
	   return;
	 }
	    ch->mana -= 25;
    }
    else
    {
	if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	    (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

	 if( arg[0] == '\0')
	 {
	   send_to_char( "Who do you want to snoop on?\n\r", ch );
	   return;
	 }

	 if ( ( victim = get_char_world( ch, arg ) ) == NULL
	    ||  psionic_remote_room_blocked(ch, victim->in_room, false, false) )
	 {
	   send_to_char( "They aren't here.\n\r", ch );
	   return;
	 }
    }

    if( victim == ch)
	 {
	   send_to_char("You get an image of yourself.\n\r",ch);
	   return;
	 }

    act( "You concentrate, and an image of $N appears in your mind.", ch,
	   NULL, victim, TO_CHAR );
    send_to_char("\n\r",ch);

    was_in_room = ch->in_room;
    ch->in_room = victim->in_room;
    do_look( ch, "auto" );
    if( number_percent () > 50)
	 send_to_char("You feel as if someone is watching you.\n\r",victim);
    ch->in_room = was_in_room;
    check_improve(ch,gsn_clairvoyance,true,4);
    WAIT_STATE(ch,skill_table[gsn_clairvoyance].beats);
    return;

}

void do_pyrotechnics ( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    int chance;
    int dam;
    int hpch;

    one_argument(argument, arg);

    if ( !IS_NPC(ch) )
    {
        if ( (chance = get_skill(ch, gsn_pyrotechnics)) == 0 )
        {
            send_to_char("Do what?\n\r", ch);
            return;
        }

        if ( arg[0] == '\0' && ch->fighting == NULL )
        {
            send_to_char("Who do you want to burn?\n\r", ch);
            return;
        }
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
        {
            send_to_char("They aren't here.\n\r", ch);
            return;
        }

        if ( victim == ch )
            return;

        if ( ch->mana < 20 )
        {
            send_to_char("You don't have enough mana.\n\r", ch);
            return;
        }

        if ( is_safe_spell(ch, victim, false) )
        {
            act("$N cannot be harmed by you.", ch, NULL, victim, TO_CHAR);
            return;
        }

        if ( IS_AFFECTED2(victim, AFF2_GHOST) )
        {
            act("Your attack passes right thru $N!", ch, NULL, victim, TO_CHAR);
            act("$n's attack passes right thru $N!", ch, NULL, victim, TO_ROOM);
            return;
        }

        if ( IS_AFFECTED2(ch, AFF2_GHOST) )
        {
            send_to_char("You cannot attack while in this form.\n\r", ch);
            return;
        }

        if ( victim->fighting != NULL
        &&   !is_same_group(ch, victim->fighting) )
        {
            send_to_char("Kill stealing is not permitted.\n\r", ch);
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char("You lost your concentration.\n\r", ch);
            check_improve(ch, gsn_pyrotechnics, false, 4);
            ch->mana -= (dice(1, 5) + 3);
            return;
        }

        ch->mana -= 20;
    }
    else
    {
        if ( IS_SET(ch->act, ACT_PET) || IS_SET(ch->affected_by, AFF_CHARM) ||
             (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;

        if ( arg[0] == '\0' && ch->fighting == NULL )
            return;
        else if ( arg[0] == '\0' && ch->fighting != NULL )
            victim = ch->fighting;
        else if ( (victim = get_char_room(ch, arg)) == NULL )
            return;

        if ( victim == ch )
            return;
    }

    if ( victim->fighting != NULL && !is_same_group(ch, victim->fighting) )
    {
        send_to_char("Kill stealing is not permitted.\n\r", ch);
        return;
    }

    act("You focus your mind and unleash a torrent of psionic fire at $N!", ch, NULL, victim, TO_CHAR);
    act("$n's eyes blaze white as a column of psionic fire erupts around $N!", ch, NULL, victim, TO_ROOM);
    act("$n's mind ignites the air around you in searing psionic flame!", ch, NULL, victim, TO_VICT);

    hpch = UMAX(10, ch->hit);
    dam  = number_range(hpch / 14 + 1, hpch / 7);
    if ( saves_spell(ch->level, victim) )
        dam /= 2;

    try_heat_gear(ch, victim);
    damage(ch, victim, dam, gsn_pyrotechnics, DAM_FIRE);
    check_improve(ch, gsn_pyrotechnics, true, 4);
    WAIT_STATE(ch, skill_table[gsn_pyrotechnics].beats);
    return;

}


void do_ego_whip( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    AFFECT_DATA af;
    int what_affect;
    int chance;
    int level;
    int dam;
    bool resisted;

    one_argument(argument,arg);

    if(!IS_NPC(ch))
    {
	 if ( (chance = get_skill(ch,gsn_ego_whip)) == 0 )
	 {
	  send_to_char("Do what?\n\r",ch);
	  return;
	 }

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Whose mind do you wish to warp?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	   victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if( victim == ch)
	   return;

	 if( ch->mana < 20)
	 {
	   send_to_char("You don't have enough mana.\n\r",ch);
	   return;
	 }

	 if ( victim->fighting != NULL && !is_same_group(ch,victim->fighting))
	 {
	   send_to_char("Kill stealing is not permitted.\n\r",ch);
	   return;
	 }

	 if(is_safe_spell(ch,victim,false))
	 {
	   act("$N cannot be harmed by you.",ch,NULL,victim,TO_CHAR);
		return;
	 }

    if ( IS_AFFECTED2(victim, AFF2_GHOST ) )
    {
        act("Your attack passes right thru $N!",ch,NULL,victim,TO_CHAR);
        act("$n's attack passes right thru $N!",ch,NULL,victim,TO_ROOM);
        return;
    }

    if ( IS_AFFECTED2(ch, AFF2_GHOST ) )
    {
        send_to_char("You cannot attack while in this form.\n\r",ch);
        return;
    }


	 if ( number_percent( ) > chance )
	 {
	  send_to_char("You lost your concentration.\n\r",ch);
	  ch->mana -= (dice(1,5) + 3);
	  check_improve(ch,gsn_ego_whip,false,4);
	  return;
	 }

	ch->mana -= 20;
    }
    else
    {
    if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	(IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Whose mind do you wish to warp?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	   victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if( victim == ch)
	   return;
    }

    level = ch->level;
    dam = dice(level/2, 4) + level/2;
    resisted = saves_spell( level, victim );

    if ( !resisted && !is_affected( victim, gsn_ego_whip ) )
    {
	af.type      = gsn_ego_whip;
	af.level	   = (sh_int)(level);
	af.duration  = (sh_int)(dice(4,5));
	af.bitvector  = 0;
	af.bitvector2 = 0;
	what_affect  = dice(1,4);
	switch (what_affect)
	 {
	  case 1:
	    af.location = APPLY_STR;
	    af.modifier = -1*(2 + (level >= 15) + (level >= 25) + (level >= 35));
	    send_to_char("You feel like such a weakling.\n\r",victim);
	    affect_to_char( victim, &af );
	  break;
	  case 2:
	    af.location  = APPLY_INT;
	    af.modifier  = -1*(2 + (level >= 15) + (level >= 25) + (level >= 35));
	    send_to_char("Everyone seems so much smarter than you.\n\r",victim);
	    affect_to_char( victim, &af );
	  break;
	  case 3:
	    af.location  = APPLY_WIS;
	    af.modifier  = -1*(2 + (level >= 15) + (level >= 25) + (level >= 35));
	    send_to_char("You feel like you do the stupidest things sometimes.\n\r",
				  victim);
	    affect_to_char( victim, &af );
	  break;
	  case 4:
	    af.location  = APPLY_DEX;
	    af.modifier  = -1*(2 + (level >= 15) + (level >= 25) + (level >= 35));
	    send_to_char("You sure feel like a klutz.\n\r",victim);
	    affect_to_char( victim, &af );
	  break;
	 }
    }

    if ( resisted )
	 dam /= 2;
    damage( ch, victim, dam, gsn_ego_whip, DAM_MENTAL );
    check_improve(ch,gsn_ego_whip,true,4);
    WAIT_STATE(ch,skill_table[gsn_ego_whip].beats);
    return;
}

void do_psionic_armor( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim = NULL;
    AFFECT_DATA af;
    int chance = 0;
    int level;

    one_argument(argument,arg);
    level = ch->level;

    if ( IS_NPC(ch) )
    {
        if ( IS_SET(ch->act, ACT_PET)
        ||   IS_SET(ch->affected_by, AFF_CHARM)
        ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;
    }
    else
    {
        if ( (chance = get_skill(ch, gsn_psionic_armor)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }
    }

    if ( arg[0] == '\0' )
        victim = ch;
    else if ( (victim = get_char_room(ch, arg)) == NULL )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "They aren't here.\n\r", ch );
        return;
    }

    if ( psionic_defense_active(victim) )
    {
        if ( victim == ch )
            send_to_char( "You are already protected.\n\r", ch );
        else
            act( "$N is already protected.", ch, NULL, victim, TO_CHAR );
        return;
    }

    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < 20 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve( ch, gsn_psionic_armor, false, 4 );
            return;
        }
        ch->mana -= 20;
    }

    af.type      = gsn_psionic_armor;
    af.level	  = (sh_int)(level);
    af.duration  = (sh_int)(level/2);
    af.location  = APPLY_NONE;
    af.modifier  = 0;
    af.bitvector = 0;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
    send_to_char( "You feel mentally defensive.\n\r", victim );

    check_improve( ch, gsn_psionic_armor, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_psionic_armor].beats );
    return;
}

void do_psychic_shield( CHAR_DATA *ch, char *argument )
{
    CHAR_DATA *gch;
    AFFECT_DATA af;
    int chance = 0;
    int level;
    int recipients = 0;

    UNUSED_PARAM(argument);
    level = ch->level;

    if ( IS_NPC(ch) )
    {
        if ( IS_SET(ch->act, ACT_PET)
        ||   IS_SET(ch->affected_by, AFF_CHARM)
        ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;
    }
    else if ( (chance = get_skill(ch, gsn_psychic_shield)) == 0 )
    {
        send_to_char( "Do what?\n\r", ch );
        return;
    }

    if ( ch->in_room == NULL )
        return;

    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
        if ( is_same_group(gch, ch) && !psionic_defense_active(gch) )
            recipients++;

    if ( recipients == 0 )
    {
        send_to_char( "Everyone in your group is already protected.\n\r", ch );
        return;
    }

    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < 50 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve( ch, gsn_psychic_shield, false, 4 );
            return;
        }
        ch->mana -= 50;
    }

    for ( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
        if ( !is_same_group(gch, ch) || psionic_defense_active(gch) )
            continue;

        af.type       = gsn_psychic_shield;
        af.level      = (sh_int)(level);
        af.duration   = (sh_int)(level/2);
        af.location   = APPLY_NONE;
        af.modifier   = 0;
        af.bitvector  = 0;
        af.bitvector2 = 0;
        affect_to_char( gch, &af );
        send_to_char( "You feel a barrier surround your mind.\n\r", gch );
    }
    send_to_char( "You raise a psychic shield around your group.\n\r", ch );
    check_improve( ch, gsn_psychic_shield, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_psychic_shield].beats );
    return;
}

void do_mindbar( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    AFFECT_DATA af;
    int chance = 0;
    int level;

    one_argument(argument,arg);
    level = ch->level;

    if ( IS_NPC(ch) )
    {
        if ( IS_SET(ch->act, ACT_PET)
        ||   IS_SET(ch->affected_by, AFF_CHARM)
        ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;
    }
    else if ( (chance = get_skill(ch, gsn_mindbar)) == 0 )
    {
        send_to_char( "Do what?\n\r", ch );
        return;
    }

    if ( arg[0] != '\0' )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "You can only use this on yourself.\n\r", ch );
        return;
    }

    if ( psionic_defense_active(ch) )
    {
        send_to_char( "You are already protected.\n\r", ch );
        return;
    }

    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < 50 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve( ch, gsn_mindbar, false, 4 );
            return;
        }
        ch->mana -= 50;
    }

    af.type      = gsn_mindbar;
    af.level	  = (sh_int)(level);
    af.duration  = (sh_int)(number_fuzzy( level / 6 ));
    af.location  = APPLY_NONE;
    af.modifier  = 0;
    af.bitvector = 0;
    af.bitvector2 = 0;
    affect_to_char( ch, &af );
    send_to_char( "A mental fortress protects your mind.\n\r", ch );

    check_improve( ch, gsn_mindbar, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_mindbar].beats );
    return;
}


void do_torment( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    int chance;
    int level;
    int dam;

    one_argument(argument,arg);

    if(!IS_NPC(ch))
    {
	 if ( (chance = get_skill(ch,gsn_torment)) == 0 )
	 {
	  send_to_char("Do what?\n\r",ch);
	  return;
	 }

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Who do you want to inflict pain on?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	   victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if(victim == ch)
	    return;

	 if( ch->mana < 20)
	 {
	   send_to_char("You don't have enough mana.\n\r",ch);
	   return;
	 }

	 if ( is_safe_spell(ch, victim,false ) )
	 {
	   act("$N cannot be harmed by you.",ch,NULL,victim,TO_CHAR);
		return;
	 }

    if ( IS_AFFECTED2(victim, AFF2_GHOST ) )
    {
        act("Your attack passes right thru $N!",ch,NULL,victim,TO_CHAR);
        act("$n's attack passes right thru $N!",ch,NULL,victim,TO_ROOM);
        return;
    }

    if ( IS_AFFECTED2(ch, AFF2_GHOST ) )
    {
        send_to_char("You cannot attack while in this form.\n\r",ch);
        return;
    }

	 if ( victim->fighting != NULL && !is_same_group(ch,victim->fighting))
	 {
	   send_to_char("Kill stealing is not permitted.\n\r",ch);
	   return;
	 }

	 if ( number_percent( ) > chance )
	 {
	  send_to_char("You lost your concentration.\n\r",ch);
	  ch->mana -= (dice(1,5) + 3);
	  check_improve(ch,gsn_torment,false,4);
	  return;
	 }

	ch->mana -= 20;
    }
    else
    {
	if( IS_SET(ch->act,ACT_PET) || IS_SET(ch->affected_by,AFF_CHARM) ||
	    (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
		 return;

	 if( arg[0] == '\0' && ch->fighting == NULL)
	 {
	  send_to_char( "Who do you want to inflict pain on?\n\r", ch );
	  return;
	 }
	 else if(arg[0] == '\0' && ch->fighting != NULL)
	   victim = ch->fighting;
	 else if ( ( victim = get_char_room( ch, arg ) ) == NULL )
	 {
	  send_to_char( "They aren't here.\n\r", ch );
	  return;
	 }

	 if(victim == ch)
	   return;
    }

    level = ch->level;

	act( "$N convulses in pain.", ch,
		 NULL, victim, TO_CHAR );
	act( "Your muscles contort and you scream out in agony!", ch,
		 NULL, victim, TO_VICT );
	act( "$N screams in agony!", ch,
		 NULL, victim, TO_NOTVICT );

    dam = number_range( level/2, level * 3 );
    if ( saves_spell( level, victim ) )
	 dam /= 2;
    damage( ch, victim, dam, gsn_torment, DAM_MENTAL );
    check_improve(ch,gsn_torment,true,4);
    WAIT_STATE(ch,skill_table[gsn_torment].beats);
    return;
}


/* psi */
void do_transfusion( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim = NULL;
    int chance = 0;

    one_argument(argument, arg);

    if ( IS_NPC(ch) )
    {
        if ( IS_SET(ch->act, ACT_PET)
        ||   IS_SET(ch->affected_by, AFF_CHARM)
        ||   (IS_SWITCHED(ch) && !IS_IMMORTAL(ch)) )
            return;
    }
    else
    {
        if ( (chance = get_skill(ch, gsn_transfusion)) == 0 )
        {
            send_to_char( "Do what?\n\r", ch );
            return;
        }
    }

    if ( arg[0] == '\0' )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "Who do you wish to give energy to?\n\r", ch );
        return;
    }

    if ( (victim = get_char_room(ch, arg)) == NULL )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "They aren't here.\n\r", ch );
        return;
    }

    if ( victim == ch )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "You cannot transfuse energy into yourself.\n\r", ch );
        return;
    }

    if ( victim->hit >= victim->max_hit )
    {
        if ( !IS_NPC(ch) )
            act( "$N is already at full health.", ch, NULL, victim, TO_CHAR );
        return;
    }

    if ( ch->hit <= 50 )
    {
        if ( !IS_NPC(ch) )
            send_to_char( "You need more than 50 hit points to transfuse safely.\n\r", ch );
        return;
    }

    if ( !IS_NPC(ch) )
    {
        if ( ch->mana < 20 )
        {
            send_to_char( "You don't have enough mana.\n\r", ch );
            return;
        }

        if ( number_percent() > chance )
        {
            send_to_char( "You lost your concentration.\n\r", ch );
            ch->mana -= (dice(1,5) + 3);
            check_improve( ch, gsn_transfusion, false, 4 );
            return;
        }
        ch->mana -= 20;
    }

    send_to_char( "You feel weary as energy leaves your body.\n\r", ch );
    send_to_char( "Some of your wounds disappear.\n\r", victim );
    act( "A strange aura envelopes $N and $n.", ch, NULL, victim,
	  TO_NOTVICT );

    ch->hit -= 50;
    victim->hit = UMIN( victim->hit + 50, victim->max_hit);
    update_pos( victim );
    check_improve( ch, gsn_transfusion, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_transfusion].beats );
    return;

}

/* psi */
void do_shift( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *victim;
    int chance;

    one_argument( argument, arg );

    if ( IS_NPC(ch) )
        return;

    if ( (chance = get_skill(ch, gsn_shift)) == 0 )
    {
        send_to_char( "Do what?\n\r", ch );
        return;
    }

    if ( arg[0] == '\0' )
    {
        send_to_char( "Who do you want to shift?\n\r", ch );
        return;
    }

    victim = get_char_world( ch, arg );
    if ( victim == NULL
    ||   victim == ch
    ||   IS_IMMORTAL(victim)
    ||   (victim != NULL && victim->in_room == ch->in_room)
    ||   victim->fighting != NULL
    ||   ch->fighting != NULL
    ||   (IS_NPC(victim) && IS_SET(victim->act,ACT_AGGRESSIVE))
    ||   psionic_remote_room_blocked(ch, ch->in_room, false, true)
    ||   psionic_remote_room_blocked(ch, victim != NULL ? victim->in_room : NULL,
                                     true, true)
    ||   IS_SET(ch->in_room->room_flags, ROOM_TELEPORT)
    ||   IS_SET(ch->in_room->room_flags, ROOM_RIVER)
    ||   IS_SET(ch->in_room->room_flags, ROOM_ARENA)
    ||   IS_SET(victim->in_room->room_flags, ROOM_NEWBIES_ONLY)
    ||   (IS_NPC(victim) && IS_SET(victim->imm_flags,IMM_SUMMON))
    ||   (!IS_NPC(victim) && IS_SET(victim->act,PLR_NOSUMMON) ) )
    {
        send_to_char( "You cannot form a safe spatial path to that target.\n\r", ch );
        return;
    }

    if ( ch->mana < 70 )
    {
        send_to_char( "You don't have enough mana.\n\r", ch );
        return;
    }

    if ( number_percent() > chance )
    {
        send_to_char( "You lost your concentration.\n\r", ch );
        ch->mana -= (dice(1,5) + 3);
        check_improve( ch, gsn_shift, false, 4 );
        return;
    }
    ch->mana -= 70;

    if ( IS_NPC(victim) && saves_spell(ch->level, victim) )
    {
        send_to_char( "The target resists your spatial pull.\n\r", ch );
        check_improve( ch, gsn_shift, false, 4 );
        WAIT_STATE( ch, skill_table[gsn_shift].beats );
        return;
    }
    snprintf(buf, sizeof buf,"%s has shifted %s to room %d",ch->name,
	(IS_NPC(victim) ? victim->short_descr : victim->name), ch->in_room->vnum);
    wizinfo(buf,LEVEL_IMMORTAL);
    act( "$n is pulled into a spatial rift.", victim, NULL, NULL, TO_ROOM );
    char_from_room( victim );
    char_to_room( victim, ch->in_room );
    act( "A spatial rift opens up and $n falls out. The rift closes.", victim,
		NULL, NULL, TO_ROOM );
    act( "You have been pulled into a spatial rift by $n.", ch,
	   NULL, victim, TO_VICT );
    send_to_char("\n\r",victim);
    do_look( victim, "auto" );

    if ( !IS_IMMORTAL(ch) )
        ch->position = POS_STUNNED;

    if ( IS_NPC(victim) )
        victim->timer = 400;
    check_improve( ch, gsn_shift, true, 4 );
    WAIT_STATE( ch, skill_table[gsn_shift].beats );
    return;

}

void spell_major_globe( int sn, int level, CHAR_DATA *ch, void *vo )
{
    AFFECT_DATA af;
    CHAR_DATA *victim = (CHAR_DATA *) vo;

    if ( IS_AFFECTED(victim, sn) )
    {
  if (victim == ch)
  send_to_char("You are already in a protective globe.\n\r",ch);
  else
    act("$N is already in protective globe.",ch,NULL,victim,TO_CHAR);
  return;
    }

/*
    if(is_affected(ch, skill_lookup("armor") )
    || is_affected(ch, skill_lookup("shield") )
    || is_affected(ch, skill_lookup("shroud") )
    || is_affected(ch, skill_lookup("stone skin") ) )
    {
      send_to_char("You can't combine this with other protective spells.\n\r",ch);
      return;
    }
*/
    af.type      = (sh_int)(sn);
    af.level	 = (sh_int)(level);
    if(IS_IMMORTAL(ch) )
    af.duration  = ch->level;
    else
    af.duration  = 24;
    af.modifier  = -80 - ch->level;
    af.location  = APPLY_AC;
    af.bitvector = 0;
    af.bitvector2= 0;
    affect_to_char( victim, &af );
    send_to_char("A misty globe surrounds you.\n\r",victim);
    act("A misty globe surrounds $n.",victim,NULL,NULL,TO_ROOM);
    return;
}

void spell_earth_travel( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(vo);
    CHAR_DATA *victim;
    char buf[MAX_STRING_LENGTH];

    if ( ( victim = get_char_world( ch, target_name ) ) == NULL
    ||   victim == ch
    ||   victim->in_room == NULL
    ||   !can_see_room(ch,victim->in_room)
    ||   IS_SET(victim->in_room->room_flags, ROOM_SAFE)
    ||   IS_SET(victim->in_room->room_flags, ROOM_PRIVATE)
    ||   IS_SET(victim->in_room->room_flags, ROOM_SOLITARY)
    ||   IS_SET(victim->in_room->room_flags, ROOM_NO_RECALL)
    ||   IS_SET(ch->in_room->room_flags, ROOM_NO_RECALL)
    ||   IS_SET(victim->in_room->room_flags, ROOM_JAIL)
    ||   IS_SET(ch->in_room->room_flags, ROOM_JAIL)
    ||   victim->level >= level + 3
    ||   (!IS_NPC(ch) && ch->pcdata->mounted)
    ||   (!IS_NPC(victim) && victim->level >= LEVEL_HERO3)  /* NOT trust */
    ||   (IS_NPC(victim) && IS_SET(victim->imm_flags,IMM_SUMMON))
    ||   (!IS_NPC(victim) && IS_SET(victim->act,PLR_NOSUMMON))
    ||   (IS_NPC(victim) && saves_spell( level, victim ) ) )
    {
	send_to_char( "You failed.\n\r", ch );
	   return;
    }

    act("$n crosses $s arms and eerily sinks into the earth.",ch,NULL,NULL,TO_ROOM);
    send_to_char("You sink into the earth.\n\r",ch);
    char_from_room(ch);
    char_to_room(ch,victim->in_room);

    act("$n hauntingly rises out of the earth, dust settling at $s feet.",ch,
       NULL,NULL,TO_ROOM);
    do_look(ch,"auto");

    snprintf(buf, sizeof buf,"%s traveled to %s via the earth. [Room: %d]",
	 (ch->short_descr == NULL ? ch->name : ch->short_descr),
	 (victim->short_descr == NULL ? victim->name : victim->short_descr),
	  victim->in_room->vnum);

    if (IS_SET(ch->act, PLR_WIZINVIS) )
      wizinfo(buf, ch->invis_level);
    else
      wizinfo(buf, LEVEL_IMMORTAL);
}


void spell_remove_align( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
  OBJ_DATA *obj = (OBJ_DATA *) vo;

    if(number_percent () > level + 40)
    {
	act("$p begins to vibrate radically, then explodes!",ch,obj,NULL,TO_CHAR);
	act("$p begins to vibrate radically, then explodes!",ch,obj,NULL,TO_ROOM);
	extract_obj(obj);
	return;
    }

    if(IS_SET(obj->extra_flags, ITEM_ANTI_GOOD) )
       REMOVE_BIT(obj->extra_flags, ITEM_ANTI_GOOD);
    if(IS_SET(obj->extra_flags, ITEM_ANTI_EVIL) )
       REMOVE_BIT(obj->extra_flags, ITEM_ANTI_EVIL);
    if(IS_SET(obj->extra_flags, ITEM_ANTI_NEUTRAL) )
       REMOVE_BIT(obj->extra_flags, ITEM_ANTI_NEUTRAL);

    act("$p vibrates radically, then becomes still.",ch,obj,NULL,TO_CHAR);
    act("$p vibrates radically, then becomes still.",ch,obj,NULL,TO_ROOM);
    return;

}
/* psi
void do_danger_sense( CHAR_DATA *ch, char *argument )
{

}
*/

/*
void do_mind_drain( CHAR_DATA *ch, char *argument )
{

}
*/

void spell_skeletal_hands( int sn, int level, CHAR_DATA *ch, void *vo )
{
   CHAR_DATA *victim = (CHAR_DATA *) vo;
   int hands, count, dam;

   hands = 1 + ( level >= 20 ) + ( level >= 30 )
	     + ( level >= 45 ) + ( level >= 55 );

   if( hands == 1)
     act("A pair of moldy hands rise up out of the ground and claw $N.",ch,
	 NULL,victim,TO_ROOM);
   else
     act("Moldy hands rise up out of the ground and claw $N.",ch,
	 NULL,victim,TO_ROOM);

   send_to_char("You summon aid from the netherworld.\n\r",ch);


   for( count = 0; count < hands; count++)
   {
     dam  = dice(4, ch->level/3);
     if ( saves_spell( level, victim ) )
	 dam /= 2;
     if (damage( ch, victim, dam, sn, DAM_NEGATIVE ))
         return;  /* victim was killed */
   }

   return;
}

void spell_tentacles( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
   CHAR_DATA *vch;
   CHAR_DATA *vch_next;
   int tentacle, count, dam;

   send_to_char("You call forth the power of the earth!\n\r",ch);

    for ( vch = ch->in_room->people; vch != NULL; vch = vch_next )
    {
      vch_next = vch->next_in_room;

      if ( !is_safe_spell(ch,vch,true) )
      {
	  act("Black tentacles rip out of the ground, flailing $n.",vch,
		NULL,NULL,TO_ROOM);

	  tentacle = dice(2,4) + 1;

	  for( count = 0; count < tentacle; count++)
	  {
	    dam  = dice(15, 10);
	    if (damage( ch, vch, dam, sn, DAM_SLASH))
		break;  /* vch was killed */
	    if( vch->in_room != ch->in_room)
		break;
	  }
      }
    }

    return;
}


void spell_vampiric_touch( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    int dam;

    if ( saves_spell( level, victim ) )
    {
    act("You see a cold mist rise off of $N's hand as it barely misses you.",
	ch, NULL,victim,TO_VICT);
	return;
    }

    dam		 = dice(5, ch->level/3);
    ch->hit = (sh_int)UMIN( ch->max_hit, ch->hit + dam / 2 );

    act("$n's hand touches you, devouring your life force.",ch,
       NULL,victim,TO_VICT);
    act("You touch $N and devour $s life force.",ch,
       NULL,victim,TO_CHAR);
    damage( ch, victim, dam, sn, DAM_NEGATIVE );

    return;

}

void do_brew( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *pObj;
   OBJ_DATA *tea = NULL;
   int chance;
   char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];

   if(IS_NPC(ch) || (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
      return;

   argument = one_argument (argument, arg);

   if(( chance = get_skill(ch,gsn_brew)) < 2)
   {
     send_to_char("Do what?\n\r",ch);
     return;
   }

   if( arg[0] == '\0')
   {
     send_to_char( "What do you want to brew?\n\r", ch );
     return;
   }

   if ( ( pObj = get_obj_carry( ch, arg ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if( pObj->item_type != ITEM_HERB)
   {
     send_to_char("That's not a brewable herb.\n\r",ch);
     return;
   }

   send_to_char("You set about to make your herbal brew.\n\r",ch);
   act("$n lights a small fire and places a pot of water on it to boil.",
	ch,NULL,NULL,TO_ROOM);
   act("The water begins to boil, so $n adds some herbs to it.",ch,
	NULL,NULL,TO_ROOM);
   act("As the brew cools down, $n spoons out a small amount.",ch,
	NULL,NULL,TO_ROOM);

   if( number_percent () > chance  )
   {
      send_to_char("It doesn't taste right. You failed.\n\r",ch);
      act("$n spits it out. Apparently the herbs didn't mix correctly.",ch,
	NULL,NULL,TO_ROOM);
      extract_obj( pObj );
      check_improve(ch,gsn_brew,false,3);
      save_char_obj(ch);
      return;
   }

   tea = create_object(get_obj_index(74), ch->level);

   switch( pObj->pIndexData->vnum )
   {
     case 34:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("refresh");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a blue container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"blue tea");
	      tea->name = str_dup( buf );
     break;
     case 35:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("cure blindness");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a white container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"white tea");
	      tea->name = str_dup( buf );
     break;
     case 36:
	      tea->value[0] = ch->level;
	      if(number_percent () < 25)
	      {
		send_to_char("Hmmm. It seems to have brewed correctly, but"
			     " the taste is slightly off.\n\r",ch);
		tea->value[1] = skill_lookup("sleep");
		tea->value[2] = skill_lookup("poison");
		tea->value[3] = skill_lookup("blindness");
		free_string( tea->short_descr );
		snprintf(buf, sizeof buf,"a redish-black container of tea");
		tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"redish-black tea");
	      tea->name = str_dup( buf );
	      }
	      else
	      {
		tea->value[1] = skill_lookup("cure light");
		tea->value[2] = skill_lookup("cure light");
		free_string( tea->short_descr );
		snprintf(buf, sizeof buf,"a pink container of tea");
		tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"pink tea");
	      tea->name = str_dup( buf );
	      }
     break;
     case 37:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("infravision");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a bloodstone container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"bloodstone tea");
	      tea->name = str_dup( buf );
     break;
     case 38:
	      tea->value[0] = 1 + ch->level/2;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("haste");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a ruby container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"ruby tea");
	      tea->name = str_dup( buf );
     break;
     case 39:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a plain container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"plain tea");
	      tea->name = str_dup( buf );
     break;
     case 40:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("detect poison");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"an off-white container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"off-white tea");
	      tea->name = str_dup( buf );
     break;
     case 41:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure serious");
	      tea->value[2] = skill_lookup("cure disease");
	      tea->value[3] = skill_lookup("cure nightmare");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a diamond container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"diamond tea");
	      tea->name = str_dup( buf );
     break;
     case 42:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure critical");
	      tea->value[2] = skill_lookup("cure nightmare");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a sapphire container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"sapphire tea");
	      tea->name = str_dup( buf );
     break;
     case 43:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure serious");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a green container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"green tea");
	      tea->name = str_dup( buf );
     break;
     case 44:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("protection");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a golden container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"golden tea");
	      tea->name = str_dup( buf );
     break;
     case 45:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("cure serious");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a silver container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"silver tea");
	      tea->name = str_dup( buf );
     break;
     case 46:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("cure critical");
	      tea->value[3] = skill_lookup("cure critical");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a onyx container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"onyx tea");
	      tea->name = str_dup( buf );
     break;
     case 47:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure serious");
	      tea->value[2] = skill_lookup("cure disease");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a lavender colored container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"lavender tea");
	      tea->name = str_dup( buf );
     break;
     case 48:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("giant strength");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a purple colored container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"purple tea");
	      tea->name = str_dup( buf );
     break;
     case 49:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("calm");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a hazel colored container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"hazel tea");
	      tea->name = str_dup( buf );
     break;
     case 50:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a pale green container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"pale green tea");
	      tea->name = str_dup( buf );
     break;
     case 51:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure critical");
	      tea->value[2] = skill_lookup("heal");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a sky blue container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"sky blue tea");
	      tea->name = str_dup( buf );
     break;
     case 52:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("cure poison");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a sea green container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"sea green tea");
	      tea->name = str_dup( buf );
     break;
     case 53:
	      tea->value[0] = ch->level;
	      tea->value[1] = skill_lookup("cure light");
	      tea->value[2] = skill_lookup("refresh");
	      tea->value[3] = skill_lookup("restore mana");
	      free_string( tea->short_descr );
	      snprintf(buf, sizeof buf,"a rainbow colored container of tea");
	      tea->short_descr = str_dup( buf );
	      free_string( tea->name );
	      snprintf(buf, sizeof buf,"rainbow tea");
	      tea->name = str_dup( buf );
     break;

   }
   act("$n says, 'Tastes good,' and smiles.",ch,NULL,NULL,TO_ROOM);
   act("$n then pours the brewed liquid into a container.",ch,
	NULL,NULL,TO_ROOM);
   send_to_char("The herbs have brewed, and you pour the liquid into a container.\n\r",ch);
   check_improve(ch,gsn_brew,true,5);
   extract_obj( pObj );
   obj_to_char(tea, ch);
   achievement_record_event(ch, ACHIEVEMENT_EVENT_BREW, true);
   save_char_obj(ch);
   return;

}

static int crafting_component_vnum( const OBJ_DATA *obj )
{
   return obj != NULL && obj->pIndexData != NULL
        ? obj->pIndexData->vnum : -1;
}

static bool crafting_pair_matches( const OBJ_DATA *one, const OBJ_DATA *two,
                                   int first_vnum, int second_vnum )
{
   int one_vnum = crafting_component_vnum( one );
   int two_vnum = crafting_component_vnum( two );

   return ( one_vnum == first_vnum && two_vnum == second_vnum )
       || ( one_vnum == second_vnum && two_vnum == first_vnum );
}

static bool crafting_trio_matches( const OBJ_DATA *one, const OBJ_DATA *two,
                                   const OBJ_DATA *three, int first_vnum,
                                   int second_vnum, int third_vnum )
{
   int one_vnum = crafting_component_vnum( one );
   int two_vnum = crafting_component_vnum( two );
   int three_vnum = crafting_component_vnum( three );

   return ( one_vnum == first_vnum || two_vnum == first_vnum
         || three_vnum == first_vnum )
       && ( one_vnum == second_vnum || two_vnum == second_vnum
         || three_vnum == second_vnum )
       && ( one_vnum == third_vnum || two_vnum == third_vnum
         || three_vnum == third_vnum );
}

void do_concoct( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *pObj_one, *pObj_two;
   OBJ_DATA *potion = NULL;
   int chance;
   int slot_one = 0;
   int slot_two = 0;
   int slot_three = 0;
   char arg[MAX_INPUT_LENGTH];
   char arg2[MAX_INPUT_LENGTH];
   char buf[MAX_STRING_LENGTH];
   bool found = false;

   if(IS_NPC(ch) || (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
      return;

   argument = one_argument (argument, arg);
   argument = one_argument (argument, arg2);

   if(( chance = get_skill(ch,gsn_concoct)) < 2)
   {
     send_to_char("Do what?\n\r",ch);
     return;
   }

   if( arg[0] == '\0' || arg2[0] == '\0')
   {
     send_to_char( "What ingredients to you want to combine?\n\r", ch );
     return;
   }

   if ( ( pObj_one = get_obj_carry( ch, arg ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if ( ( pObj_two = get_obj_carry( ch, arg2 ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if( pObj_one == pObj_two)
   {
     send_to_char("You can't use two of the same components.\n\r",ch);
     return;
   }

   if( pObj_one->item_type != ITEM_SPELL_COMPONENT
   ||  pObj_two->item_type != ITEM_SPELL_COMPONENT)
   {
     send_to_char("That's not a spell ingredient.\n\r",ch);
     return;
   }


   if(crafting_pair_matches(pObj_one, pObj_two, 60, 64))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("fire shield");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a flaming red potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"flaming red potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 63, 66))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("cancellation");
     slot_two = skill_lookup("heal");
     slot_three = skill_lookup("restore mana");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a colorless potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"colorless potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 61, 73))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("restore mana");
     slot_two = skill_lookup("restore mana");
     slot_three = skill_lookup("restore mana");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a pinkish potion ");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"pinkish potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 55, 59))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("sanctuary");
     slot_two = skill_lookup("heal");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a white potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"white potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 62, 56))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("heal");
     slot_two = skill_lookup("pass door");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a clear potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"clear potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 54, 69))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("heal");
     slot_two = skill_lookup("heal");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a yellowish potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"yellowish potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 67, 65))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("heal");
     slot_two = skill_lookup("heal");
     slot_three = skill_lookup("sanctuary");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a pale potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"pale potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 70, 71))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("cure critical");
     slot_two = skill_lookup("heal");
     slot_three = skill_lookup("sanctuary");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a blue potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"blue potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 55, 68))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("heal");
     slot_two = skill_lookup("heal");
     slot_three = skill_lookup("heal");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a bright white potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"bright white potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(crafting_pair_matches(pObj_one, pObj_two, 58, 72))
   {
     potion = create_object(get_obj_index(75), ch->level);
     slot_one = skill_lookup("mass heal");
     slot_two = skill_lookup("mass sanctuary");
     slot_three = skill_lookup("power gloves");
     free_string( potion->short_descr );
     snprintf(buf, sizeof buf,"a softly glowing potion");
     potion->short_descr = str_dup( buf );
     free_string( potion->name );
     snprintf(buf, sizeof buf,"softly glowing potion");
     potion->name = str_dup( buf );
     found = true;
   }

   if(found)
   {
     send_to_char("You pull out your equipment and begin to concoct a potion.\n\r",ch);
     act("$n lights a small fire and places a cauldron of water on it to boil.",
	  ch,NULL,NULL,TO_ROOM);
     act("As the water begins to bubble and boil, $n then adds",ch,
	  NULL,NULL,TO_ROOM);
     snprintf(buf, sizeof buf,"%s and %s to the mixture.",pObj_one->short_descr,
	    pObj_two->short_descr);
     act(buf,ch,NULL,NULL,TO_ROOM);
     act("$n then says a few arcane words over it as the contents begin to",ch,
	  NULL,NULL,TO_ROOM);

     act("froth and smoke.",ch,
	  NULL,NULL,TO_ROOM);


     if( number_percent () > chance / 2 + 45 )
     {
       send_to_char("Uh oh. Something isn't right.\n\r",ch);
       act("The cauldron explodes it's noxious contents all over $n!",ch,
	NULL,NULL,TO_ROOM);
       extract_obj( potion );
       potion = NULL;
       if (!damage( ch, ch, dice(2,10), gsn_concoct, DAM_FIRE ))
       {
           /* ch survived; extract the spent ingredients */
           extract_obj( pObj_one );
           extract_obj( pObj_two );
           save_char_obj(ch);
       }
       /* if ch was killed, make_corpse already moved objects to corpse */
       return;
     }

     check_improve(ch,gsn_concoct,true,5);
     potion->value[0] = ch->level;
     potion->value[1] = slot_one;
     if(slot_two > 0)
	potion->value[2] = slot_two;
     if(slot_three > 0)
	potion->value[3] = slot_three;
     obj_to_char(potion,ch);
     achievement_record_event(ch, ACHIEVEMENT_EVENT_CONCOCT, true);
   }
   else
   {
     send_to_char("Combining those ingredients won't do anything.\n\r",ch);
     return;
   }

   extract_obj( pObj_one );
   extract_obj( pObj_two );
   save_char_obj(ch);
   return;
}

void do_scribe( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *pObj_one, *pObj_two, *pObj_three;
   OBJ_DATA *scroll = NULL;
   int chance;
   int spell_one = 0;
   int spell_two = 0;
   int spell_three = 0;
   char arg[MAX_INPUT_LENGTH];
   char arg2[MAX_INPUT_LENGTH];
   char arg3[MAX_INPUT_LENGTH];
   char buf[MAX_STRING_LENGTH];
   bool found = false;
   bool farslay_scroll = false;

   if(IS_NPC(ch) || (IS_SWITCHED(ch) && !IS_IMMORTAL(ch) ))
      return;

   argument = one_argument (argument, arg);
   argument = one_argument (argument, arg2);
   argument = one_argument (argument, arg3);

   if(( chance = get_skill(ch,gsn_scribe)) < 2)
   {
     send_to_char("Do what?\n\r",ch);
     return;
   }

   if( arg[0] == '\0' || arg2[0] == '\0' || arg3[0] == '\0')
   {
     send_to_char( "What ingredients to you want to combine?\n\r", ch );
     return;
   }

   if ( ( pObj_one = get_obj_carry( ch, arg ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if ( ( pObj_two = get_obj_carry( ch, arg2 ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if ( ( pObj_three = get_obj_carry( ch, arg3 ) ) == NULL )
   {
     send_to_char( "You are not carrying that.\n\r", ch );
     return;
   }

   if( pObj_one == pObj_two || pObj_one == pObj_three
    || pObj_two == pObj_three)
   {
     send_to_char("You can't use two of the same components.\n\r",ch);
     return;
   }

   if( pObj_one->item_type != ITEM_SPELL_COMPONENT
   ||  pObj_two->item_type != ITEM_SPELL_COMPONENT
   ||  pObj_three->item_type != ITEM_SPELL_COMPONENT)
   {
     send_to_char("That's not a spell ingredient.\n\r",ch);
     return;
   }


   if(crafting_trio_matches(pObj_one, pObj_two, pObj_three, 80, 84, 76))
   {
     scroll = create_object(get_obj_index(90), ch->level);
     spell_one = skill_lookup("remove align");
     free_string( scroll->short_descr );
     snprintf(buf, sizeof buf,"a blank scroll");
     scroll->short_descr = str_dup( buf );
     free_string( scroll->name );
     snprintf(buf, sizeof buf,"blank scroll");
     scroll->name = str_dup( buf );
     found = true;
     snprintf(buf, sizeof buf,"A remove align scroll may have been created by %s",ch->name);
     log_string(buf);
     wizinfo(buf,LEVEL_IMMORTAL);
   }

   if(crafting_trio_matches(pObj_one, pObj_two, pObj_three, 83, 88, 77))
   {
     scroll = create_object(get_obj_index(90), ch->level);
     spell_one = skill_lookup("fire shield");
     spell_two = skill_lookup("sanctuary");
     spell_three = skill_lookup("restore mana");
     free_string( scroll->short_descr );
     snprintf(buf, sizeof buf,"a redish-white scroll");
     scroll->short_descr = str_dup( buf );
     free_string( scroll->name );
     snprintf(buf, sizeof buf,"redish-white scroll");
     scroll->name = str_dup( buf );
     found = true;
   }

   if(crafting_trio_matches(pObj_one, pObj_two, pObj_three, 78, 81, 79))
   {
     scroll = create_object(get_obj_index(90), ch->level);
     spell_one = skill_lookup("power gloves");
     spell_two = skill_lookup("sanctuary");
     spell_three = skill_lookup("heal");
     free_string( scroll->short_descr );
     snprintf(buf, sizeof buf,"a blinding white scroll");
     scroll->short_descr = str_dup( buf );
     free_string( scroll->name );
     snprintf(buf, sizeof buf,"blinding white scroll");
     scroll->name = str_dup( buf );
     found = true;
   }

   if(crafting_trio_matches(pObj_one, pObj_two, pObj_three, 84, 78, 87))
   {
     scroll = create_object(get_obj_index(90), ch->level);
     spell_one = skill_lookup("restore mana");
     spell_two = skill_lookup("mass sanctuary");
     spell_three = skill_lookup("restore mana");
     free_string( scroll->short_descr );
     snprintf(buf, sizeof buf,"a yellow scroll");
     scroll->short_descr = str_dup( buf );
     free_string( scroll->name );
     snprintf(buf, sizeof buf,"yellow scroll");
     scroll->name = str_dup( buf );
     found = true;
   }


      if(crafting_trio_matches(pObj_one, pObj_two, pObj_three, 77, 76, 88))
      {
        scroll = create_object(get_obj_index(90), ch->level);
        spell_one = skill_lookup("vengence");
        free_string( scroll->short_descr );
        snprintf(buf, sizeof buf,"a deadly black scroll");
        scroll->short_descr = str_dup( buf );
        free_string( scroll->name );
        snprintf(buf, sizeof buf,"deadly black scroll");
        scroll->name = str_dup( buf );
        found = true;
        farslay_scroll = true;
        snprintf(buf, sizeof buf,"Vengence may soon fall upon you from %s!", ch->name);
        log_string(buf);
        wizinfo(buf,LEVEL_IMMORTAL);
      }


   if(found)
   {
     send_to_char("You pull out your equipment and start work on the ink.\n\r",ch);
     act("$n pulls out $p and pours it into a bowl.",
	  ch,pObj_one,NULL,TO_ROOM);
     act("Stirring it, $e adds a pinch of $p.",ch,
	  pObj_two,NULL,TO_ROOM);
     act("$e then mumbles some strange syllables and the mixture begins to smoke.",ch,
	  NULL,NULL,TO_ROOM);
     act("Ever so carefully, $n then carefully adds $p to the bowl.",ch,
	  pObj_three,NULL,TO_ROOM);
     act("A brief flash of light follows the addition of the final ingredient.",ch,
	  NULL,NULL,TO_ROOM);


     if( number_percent () > chance / 2 + 45 )
     {
       send_to_char("You measured out the wrong amount of liquids.\n\r",ch);
       act("$n throws the mix on the ground, cussing about random chance!",ch,
	NULL,NULL,TO_ROOM);
       extract_obj( scroll );
       scroll = NULL;
       extract_obj( pObj_one );
       extract_obj( pObj_two );
       extract_obj( pObj_three);
       save_char_obj(ch);
       return;
     }
     send_to_char("Success!!! The ink will work!\n\r",ch);
     send_to_char("You get out your quill and begin writting the spells with the ink.\n\r",ch);
     act("Smiling gleefully, $n pulls out a sheet of vellum and writes out the spells.",ch,
	  NULL,NULL,TO_ROOM);
     check_improve(ch,gsn_scribe,true,5);
     scroll->value[0] = ch->level;
     scroll->value[1] = spell_one;
     if(spell_two > 0)
       scroll->value[2] = spell_two;
     if(spell_three > 0)
       scroll->value[3] = spell_three;
     obj_to_char(scroll,ch);
     achievement_record_event(ch, ACHIEVEMENT_EVENT_SCRIBE, true);
     if (farslay_scroll)
       achievement_record_event(ch, ACHIEVEMENT_EVENT_FARSLAY_SCROLL, true);
   }
   else
   {
     send_to_char("Combining those ingredients won't make a useable ink.\n\r",ch);
     return;
   }

   extract_obj( pObj_one );
   extract_obj( pObj_two );
   extract_obj( pObj_three );
   save_char_obj(ch);
   return;
}

void spell_vengence( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    int nuke = 0;
    char buf[MAX_STRING_LENGTH];
    int chance;
    int penalty;

    if(victim == NULL)
      return;

    if(victim == ch)
    {
      send_to_char("You can not kills yourself with Farslayer.\n\r",ch);
      return;
    }

    act("A strange mist begins to rise from the ground, swirling at $n's",
	 ch,NULL,NULL,TO_ROOM);
    act("A strange mist begins to rise from the ground, swirling at your feet.",
	 ch,NULL,NULL,TO_CHAR);
    act("feet.  A small vortex opens in the center of the mist and a",
	 ch,NULL,NULL,TO_ROOM);
    act("A small vortex opens in the center of the mist and a sword begins",
	 ch,NULL,NULL,TO_CHAR);
    act("sword begins to rise out of it.  $n reaches down and grasps the",
	 ch,NULL,NULL,TO_ROOM);
    act("to rise out of it.  You reach down and grasp the hilt.",
	 ch,NULL,NULL,TO_CHAR);
    act("hilt. Spinning in circles $e begins to recite:",
	 ch,NULL,NULL,TO_ROOM);
    act("You start to spin in circles uncontrollable, then words are forced out of you:",
	 ch,NULL,NULL,TO_CHAR);
    act("Farslayer howls across the world", ch,NULL,NULL,TO_ROOM);
    act("Farslayer howls across the world", ch,NULL,NULL,TO_CHAR);
    act("For thy heart, for thy heart, who hast wronged",ch,
	NULL,NULL,TO_ROOM);
    act("For thy heart, for thy heart, who hast wronged",ch,
	NULL,NULL,TO_CHAR);
    act("me!", ch,NULL,NULL,TO_ROOM);
    act("me!", ch,NULL,NULL,TO_CHAR);
    act("Vengence is his who casts the blade",ch,NULL,NULL,TO_ROOM);
    act("Vengence is his who casts the blade",ch,NULL,NULL,TO_CHAR);
    act("Yet he will in the end no triumph see.",ch,NULL,NULL,TO_ROOM);
    act("Yet he will in the end no triumph see.",ch,NULL,NULL,TO_CHAR);
    act("Die $N!!!",ch,NULL,victim,TO_ROOM);
    act("Die $N!!!",ch,NULL,victim,TO_CHAR);

    act("The sword rips out of $n's hand, flashing across the sky.",
	 ch,NULL,NULL,TO_ROOM);
    act("The sword rips out of your hand, flashing across the sky.",
	 ch,NULL,NULL,TO_CHAR);

    chance = number_percent();

    if (chance > 50)
    {
    send_to_char("You hear a whistling sound. As you look up, a SWORD plunges into your heart!\n\r",victim);
    act("You hear a whistling sound, then a SWORD plunges into $n's heart!",victim,NULL,NULL,TO_ROOM);
    if(!IS_NPC(victim) && IS_IMMORTAL(victim) )
      do_echo(ch,"You hear a horrible howling as a GOD meets FARSLAYER!");
    }
    else
    {
    send_to_char("You hear a whistling sound. Your vengeance has gone awry!!!\n\r",ch);
    act("You hear a whistling sound, then a SWORD plunges into $n's heart!",ch,NULL,NULL,TO_ROOM);
    }

    if ( !IS_IMMORTAL(ch) )
    {
      ch->hit = 1;
      ch->mana = 1;
      ch->move = 1;
      ch->position = POS_STUNNED;

      if ( !IS_NPC(ch) && ch->pcdata != NULL )
      {
	penalty = UMAX(25, 2 * ch->level);
	ch->max_hit = (sh_int)UMAX(1, ch->max_hit - penalty);
	ch->max_mana = (sh_int)UMAX(1, ch->max_mana - penalty);
	ch->max_move = (sh_int)UMAX(1, ch->max_move - penalty);
	ch->pcdata->perm_hit = (sh_int)UMAX(1, ch->pcdata->perm_hit - penalty);
	ch->pcdata->perm_mana = (sh_int)UMAX(1, ch->pcdata->perm_mana - penalty);
	ch->pcdata->perm_move = (sh_int)UMAX(1, ch->pcdata->perm_move - penalty);

	nuke = number_range(0, MAX_STATS - 1);
	ch->perm_stat[nuke] = (sh_int)UMAX(3, ch->perm_stat[nuke] - 3);
	save_char_obj( ch );
      }
    }

    if (chance > 50)
    {
    if ( IS_NPC(victim) && victim->pIndexData != NULL
    &&   victim->pIndexData->vnum == 30225 )
    {
      act("Farslayer tears through $n, but ancient darkness binds $m to life!",
	  victim,NULL,NULL,TO_ROOM);
      act("Farslayer tears through you, but ancient darkness binds you to life!",
	  victim,NULL,NULL,TO_CHAR);
      if ( !IS_NPC(ch) )
      {
	SET_BIT(ch->act, PLR_WANTED);
	send_to_char("You are now WANTED!!\n\r",ch);
      }
      raw_kill(ch,victim);
      return;
    }

    act("Farslayer does UNSPEAKABLE things to $n!",victim,NULL,NULL,TO_ROOM);
    act("Farslayer does UNSPEAKABLE things to you!",victim,NULL,NULL,TO_CHAR);
    act( "$n is DEAD!!", victim, NULL, NULL, TO_ROOM );
    send_to_char( "You have been KILLED!!\n\r\n\r", victim );
    victim->hit = 1;
    victim->mana = 1;
    victim->move = 1;
    snprintf(buf, sizeof buf,"%s got farslayed by %s.",victim->name,ch->name);
    wizinfo(buf, LEVEL_IMMORTAL);
    log_string(buf);
    if ( !IS_NPC(ch) )
    {
      SET_BIT(ch->act, PLR_WANTED);
      send_to_char("You are now WANTED!!\n\r",ch);
    }
    if (!IS_NPC(victim))
    {
      achievement_record_event(victim, ACHIEVEMENT_EVENT_FARSLAYED, true);
      achievement_record_event(ch, ACHIEVEMENT_EVENT_FARSLAY_KILL, true);
    }
    raw_kill(ch,victim);
    }
    else
    {
    act("Farslayer does UNSPEAKABLE things to $n!",ch,NULL,NULL,TO_ROOM);
    act("Farslayer does UNSPEAKABLE things to you!",ch,NULL,NULL,TO_CHAR);
    act("$n is DEAD!!",ch,NULL,NULL,TO_ROOM);
    send_to_char("You have been KILLED!!\n\r\n\r",ch);
    ch->hit = 1;
    ch->mana = 1;
    ch->move = 1;
    snprintf(buf, sizeof buf,"%s got hit by their own farslay *tee-hee*",ch->name);
    wizinfo(buf,LEVEL_IMMORTAL);
    log_string(buf);
    achievement_record_event(ch, ACHIEVEMENT_EVENT_FARSLAY_BACKFIRE, true);
    raw_kill(ch,ch);
    }

    return;
}

static CHAR_DATA *find_online_player_exact( const char *name )
{
    LIST_ITERATOR iter;
    CHAR_DATA *victim;

    if ( name == NULL || name[0] == '\0' )
        return NULL;

    FOR_EACH_CHARACTER( iter, victim )
        if ( !IS_NPC(victim) && !str_cmp(victim->name, name) )
            return victim;

    return NULL;
}

void spell_raise_dead( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    OBJ_DATA *corpse = (OBJ_DATA *) vo;
    OBJ_DATA *obj;
    OBJ_DATA *obj_next;
    CHAR_DATA *victim;
    char arg[MAX_INPUT_LENGTH];


    if(corpse->item_type != ITEM_CORPSE_PC)
    {
      send_to_char("That's not a players corpse!\n\r",ch);
      return;
    }

    one_argument(corpse->name, arg);

    if(( victim = find_online_player_exact(arg) ) == NULL)
    {
      send_to_char("Their spirit is adrift on another plane right now.\n\r",ch);
      return;
    }

    if(victim == ch)
    {
      send_to_char("The gods will only allow you to raise the dead of others.\n\r",ch);
      return;
    }

    if(IS_SET(victim->act, PLR_NOSUMMON) )
    {
      send_to_char("They do not wish to return to the land of the living.\n\r",ch);
      return;
    }

    if(ch->class == CLASS_CLERIC)
    {
      act(" $n bows $s head in prayer. Saying 'amen', $n holds up $s holy symbol.",ch,
	  NULL,NULL,TO_ROOM);
      send_to_char("You bow your head in a prayer to your god.\n",ch);
      act("Asking for $N's life returned to $S.",ch,NULL,victim,TO_CHAR);
      act("$n shouts, 'RETURN TO THE LIVING $N!!!'",ch,NULL,victim,TO_ROOM);
    }
    else
    {
      act("$n sprinkles a strange power all over the corpse of $N.",ch,
	 NULL,victim,TO_ROOM);
      send_to_char("You sprinkle the dust of life over the corpse,\n",ch);
      send_to_char("then call on the powers of death to let loose there bonds.\n\r",ch);
      act("$n then shouts, 'NATHRAC VENCOSE ELMORTIS $N'",ch,NULL,victim,TO_ROOM);
    }

    if(victim->in_room != ch->in_room)
    {
      act("$n slowly loses $s corporeal form to return to a previous existance.", victim, NULL,NULL, TO_ROOM);
      send_to_char("Your corporeal form dissipates as you return to a previous existance.\n\r",victim);
      char_from_room(victim);
      char_to_room(victim, ch->in_room);
    }

    for ( obj = corpse->contains; obj != NULL; obj = obj_next )
    {
      obj_next = obj->next_content;

      if( victim->carry_number + get_obj_number( obj ) > can_carry_n( victim ) )
	continue;

      if( query_carry_weight(victim) + get_obj_weight( obj ) > can_carry_w( victim ) )
	continue;

      obj_from_obj( obj );
      obj_to_char(obj, victim);
    }

    if ( corpse->contains == NULL )
      extract_obj(corpse);
    else
    {
      send_to_char("Some belongings were too heavy to return and remain in the corpse.\n\r",victim);
      act("Some of $N's belongings remain in the corpse.",ch,NULL,victim,TO_CHAR);
    }

    save_char_obj(victim);

    if(ch->class == CLASS_CLERIC)
    {
      act("A strange glow envelopes the corpse of $N.",ch,NULL,victim,TO_NOTVICT);
      act("Moments later, $N blinks and sits up.",ch,NULL,victim,TO_NOTVICT);
    }
    else
    {
      act("The corpse of $N jerks about in convulsive spasms.",ch,NULL,victim,TO_NOTVICT);
      act("When the convulsions stop, $N sits up and screams, 'No!!!'",ch,NULL,victim,TO_NOTVICT);
    }

    act("$N has risen from the dead.",ch,NULL,victim,TO_NOTVICT);
    act("You have returned $N to the land of the living.",ch,NULL,victim,TO_CHAR);
    act("Everything goes black. When you wake up, you notice a vaguely familiar scene",
	  ch,NULL,victim,TO_VICT);
    act("$n has returned you to the land of the living.",ch,NULL,victim,TO_VICT);
    return;


}

void spell_dust_devil( int sn, int level, CHAR_DATA *ch, void *vo )
{

    damage( ch, (CHAR_DATA *) vo, dice(8, 6) + level, sn, DAM_WIND );
    return;
}

void spell_vortex( int sn, int level, CHAR_DATA *ch, void *vo )
{
    send_to_char("You call forth the power of the winds!\n\r",ch);
    act("$n calls forth the power of the winds!",ch,NULL,NULL,TO_ROOM);
    damage( ch, (CHAR_DATA *) vo, dice(10, 10) + level, sn, DAM_WIND );
    return;
}

static OBJ_DATA *find_water_catalyst( CHAR_DATA *ch, int amount )
{
    OBJ_DATA *obj;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        if ( obj->wear_loc == WEAR_NONE
        &&   can_see_obj(ch, obj)
        &&   obj->item_type == ITEM_DRINK_CON
        &&   obj->value[2] == LIQ_WATER
        &&   obj->value[1] >= amount )
            return obj;
    }

    return NULL;
}

void spell_water_burst( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    OBJ_DATA *obj;

    obj = find_water_catalyst( ch, 20 );
    if( obj == NULL )
    {
      send_to_char("You need a carried water container holding at least 20 units.\n\r",ch);
      return;
    }

    obj->value[1] -= 20;
    if ( !IS_NPC(ch) )
        save_char_obj(ch);
    act("Water jets out of $p and slams into $N!",ch,obj,victim,TO_ROOM);
    act("Water jets out of $p and slams into $N!",ch,obj,victim,TO_CHAR);
    act("Water jets out of $n's $p and slams into you!",ch,obj,victim,TO_VICT);
    damage( ch, victim, dice(5, 8) + level/2, sn, DAM_DROWNING );
    return;

}
void spell_geyser( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    OBJ_DATA *obj;

    obj = find_water_catalyst( ch, 45 );
    if( obj == NULL )
    {
      send_to_char("You need a carried water container holding at least 45 units.\n\r",ch);
      return;
    }

    act("$n pours water out of $p onto the ground.",ch,obj,NULL,TO_ROOM);
    act("Seconds later, a geyser of water erupts under $N!",ch,obj,victim,TO_ROOM);
    act("$n pours water out of $p onto the ground.",ch,obj,NULL,TO_CHAR);
    act("Seconds later, a geyser of water erupts under $N!",ch,obj,victim,TO_CHAR);
    act("$n pours water out of $p onto the ground.",ch,obj,NULL,TO_VICT);
    act("Seconds later, a geyser of water erupts under YOU!",ch,obj,victim,TO_VICT);

    obj->value[1] -= 45;
    if ( !IS_NPC(ch) )
        save_char_obj(ch);

    if (!damage( ch, victim, dice(10, 10) + level, sn, DAM_DROWNING ))
        victim->position = POS_RESTING;  /* victim survived; knock them down */
    return;
}

void spell_spiritual_hammer( int sn, int level, CHAR_DATA *ch, void *vo )
{
    OBJ_DATA *obj;
    bool found = false;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( obj->wear_loc == WEAR_NONE
	&&   can_see_obj( ch, obj )
	&&   obj->item_type == ITEM_WEAPON
	&&   obj->value[0] == WEAPON_MACE )
	{
	  found = true;
	  break;
	}
    }

    if(!found)
    {
      send_to_char("You need a hammer to fuel this spell.\n\r",ch);
      return;
    }

    {
    int saved_obj_level = obj->level;  /* save before extract frees obj */
    extract_obj(obj);

    if(ch->alignment > 250)
       damage( ch, (CHAR_DATA *) vo, dice(level/3, 6) + saved_obj_level/2, sn, DAM_HOLY );
    else if(ch->alignment < -250 )
       damage( ch, (CHAR_DATA *) vo, dice(level/3, 6) + saved_obj_level/2, sn, DAM_UNHOLY );
    else
       damage( ch, (CHAR_DATA *) vo, dice(level/3, 6) + saved_obj_level/2, sn, DAM_BASH );
    return;
    }

}

void spell_evil_eye( int sn, int level, CHAR_DATA *ch, void *vo )
{
   CHAR_DATA *victim = (CHAR_DATA *) vo;

    send_to_char("    ___     ___   \n",victim);
    send_to_char("   ( 0 )   ( 0 )  \n\r\n\r",victim);

    damage( ch, victim, dice(level/2, 5), sn, DAM_NEGATIVE );
    return;

}

void spell_sunray( int sn, int level, CHAR_DATA *ch, void *vo )
{
   CHAR_DATA *victim = (CHAR_DATA *) vo;

    if( weather_info.sunlight == 0 || weather_info.sunlight == 3 )
    {
      send_to_char("There isn't enough light to use this spell.\n\r",ch);
      return;
    }

    send_to_char("You gather the light of the sun and project it!\n\r",ch);
    act("$n gather's the light of the sun and projects it at $N",ch,NULL,victim,TO_ROOM);
    damage( ch, victim, dice(level, 4) + level, sn, DAM_LIGHT );
    return;
}

void spell_moonbeam( int sn, int level, CHAR_DATA *ch, void *vo )
{
   CHAR_DATA *victim = (CHAR_DATA *) vo;

    if( weather_info.sunlight == 1 || weather_info.sunlight == 2 )
    {
      send_to_char("There isn't enough moonlight to use this spell.\n\r",ch);
      return;
    }

    send_to_char("You gather the light of the moon and project it!\n\r",ch);
    act("$n gather's the light of the moon and projects it at $N",ch,NULL,victim,TO_ROOM);
    damage( ch, victim, dice(level, 4) + level, sn, DAM_LIGHT );
    return;
}

void spell_force_sword( int sn, int level, CHAR_DATA *ch, void *vo )
{
    AFFECT_DATA af;
    CHAR_DATA *victim = (CHAR_DATA *) vo;

    if ( IS_AFFECTED2(victim, AFF2_FORCE_SWORD) )
    {
       send_to_char("You already have a force sword on guard.\n\r",ch);
       return;
    }
    act( "A sword materializes out of nowhere to guard $n.", victim, NULL, NULL, TO_ROOM );
    af.type      = (sh_int)(sn);
    af.level	 = (sh_int)(level);
    if(IS_IMMORTAL(ch) )
    af.duration  = ch->level;
    else
    af.duration  = (sh_int)(dice(2,2) + 1);
    af.location  = APPLY_NONE;
    af.modifier  = 0;
    af.bitvector = 0;
    af.bitvector2 = AFF2_FORCE_SWORD;
    affect_to_char( victim, &af );
    send_to_char( "A sword materializes next to you and stands guard.\n\r", victim );
    return;

}

/* TAR_OBJ_HERE */
void spell_create_skeleton( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    OBJ_DATA *corpse = (OBJ_DATA *) vo;
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim, *gch;
    AFFECT_DATA af;
    int count = 0;
    LIST_ITERATOR iter;

    if(corpse->item_type != ITEM_CORPSE_NPC)
    {
      send_to_char("That's corpse can't be animated.\n\r",ch);
      return;
    }

    FOR_EACH_CHARACTER( iter, gch )
        {
            if ( is_same_group( gch, ch ) )
            {
              if(IS_NPC(gch) && gch->pIndexData->vnum == MOB_VNUM_ANIMATE)
                count++;
            }
        }

    if(count >= 5)
    {
      send_to_char("You can't control any more undead.\n\r",ch);
      return;
    }
    act("$n chants, 'Oh lost spirit of the damned, come to me from wence thou haunt.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'Oh lost spirit of the damned, come to me from wence thou haunt.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'My offer, the chance for revenge on the living.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'My offer, the chance for revenge on the living.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'My command, POSSESSION!!!",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'My command, POSSESSION!!!",ch,NULL,NULL,TO_CHAR);


    victim = create_mobile(  get_mob_index(  MOB_VNUM_ANIMATE ) );
    char_to_room( victim, ch->in_room );
    victim->level = (sh_int)UMAX(1, corpse->level/3);
    victim->max_hit = (sh_int)(dice(5,8) + ch->max_hit / 4);
    victim->hit = victim->max_hit;
    victim->timer = 75;
    victim->armor[AC_PIERCE] = 0;
    victim->armor[AC_BASH]   = 0;
    victim->armor[AC_SLASH]  = 0;
    victim->armor[AC_EXOTIC] = 0;
    victim->hitroll          = 10;
    victim->damroll          = 10;
    victim->damage[DICE_NUMBER] = 10;
    victim->damage[DICE_TYPE]   = 10;
    snprintf(buf, sizeof buf,"skeleton");
    free_string(victim->name);
    victim->name = str_dup(buf);
    snprintf(buf, sizeof buf,"a skeleton");
    free_string(victim->short_descr);
    victim->short_descr = str_dup(buf);
    snprintf(buf, sizeof buf,"A skeleton is here serving %s.\n\r",ch->name);
    free_string(victim->long_descr);
    victim->long_descr = str_dup(buf);
    victim->timer = 50;
    extract_obj(corpse);
    act("Flesh melts from bone, and a skeleton stands up.",ch,NULL,NULL,TO_ROOM);
    act("Flesh melts from bone, and a skeleton stands up.",ch,NULL,NULL,TO_CHAR);
    add_follower( victim, ch );
    victim->leader = ch;
    af.type      = (sh_int)(skill_lookup("charm person"));
    af.level	 = ch->level;
    af.duration  = victim->timer;
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = AFF_CHARM;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
    return;
}
/* TAR_OBJ_HERE */
void spell_create_wraith( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    OBJ_DATA *corpse = (OBJ_DATA *) vo;
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim, *gch;
    AFFECT_DATA af;
    int count = 0;
    LIST_ITERATOR iter;

    if(corpse->item_type != ITEM_CORPSE_NPC)
    {
      send_to_char("That's corpse can't be animated.\n\r",ch);
      return;
    }

    FOR_EACH_CHARACTER( iter, gch )
        {
            if ( is_same_group( gch, ch ) )
            {
              if(IS_NPC(gch) && gch->pIndexData->vnum == MOB_VNUM_ANIMATE)
                count++;
            }
        }

    if(count >= 2)
    {
      send_to_char("You can't control any more undead.\n\r",ch);
      return;
    }

    act("$n chants, 'From the bottom of the Abyss I summon thee spirit.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'From the bottom of the Abyss I summon thee spirit.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'Return to the living to tear flesh from bone.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'Return to the living to tear flesh from bone.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'Return now, RETURN NOW!!!",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'Return now, RETURN NOW!!!",ch,NULL,NULL,TO_CHAR);

    victim = create_mobile(  get_mob_index(  MOB_VNUM_ANIMATE ) );
    char_to_room( victim, ch->in_room );
    victim->level = (sh_int)UMAX(1, corpse->level/2);
    victim->max_hit = (sh_int)(dice(20,8) + ch->max_hit / 2);
    victim->hit = victim->max_hit;
    victim->timer = 150;
    victim->armor[AC_PIERCE]    = ch->armor[AC_PIERCE];
    victim->armor[AC_BASH]	= ch->armor[AC_BASH];
    victim->armor[AC_SLASH]     = ch->armor[AC_SLASH];
    victim->armor[AC_EXOTIC]    = ch->armor[AC_EXOTIC];
    victim->hitroll             = ch->hitroll;
    victim->damroll             = GET_DAMROLL(ch)/2;
    victim->damage[DICE_NUMBER] = ch->damage[DICE_NUMBER] + 1;
    victim->damage[DICE_TYPE]   =  ch->damage[DICE_TYPE] + 1;
    snprintf(buf, sizeof buf,"wraith");
    free_string(victim->name);
    victim->name = str_dup(buf);
    snprintf(buf, sizeof buf,"a wraith");
    free_string(victim->short_descr);
    victim->short_descr = str_dup(buf);
    snprintf(buf, sizeof buf,"A wraith is here serving %s.\n\r",ch->name);
    free_string(victim->long_descr);
    victim->long_descr = str_dup(buf);
    victim->timer = 150;
    extract_obj(corpse);
    act("Flesh flakes and rots, and a wraith stands up.",ch,NULL,NULL,TO_ROOM);
    act("Flesh flakes and rots, and a wraith stands up.",ch,NULL,NULL,TO_CHAR);
    add_follower( victim, ch );
    victim->leader = ch;
    af.type      = (sh_int)(skill_lookup("charm person"));
    af.level	 = ch->level;
    af.duration  = victim->timer;
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = AFF_CHARM;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
    return;
}
/* TAR_OBJ_HERE */
void spell_create_vampire( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    OBJ_DATA *corpse = (OBJ_DATA *) vo;
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *victim, *gch;
    AFFECT_DATA af;
    int count = 0;
    LIST_ITERATOR iter;

    if(corpse->item_type != ITEM_CORPSE_NPC)
    {
      send_to_char("That's corpse can't be animated.\n\r",ch);
      return;
    }

    FOR_EACH_CHARACTER( iter, gch )
        {
            if ( is_same_group( gch, ch ) )
            {
              if(IS_NPC(gch) && gch->pIndexData->vnum == MOB_VNUM_ANIMATE)
                count++;
            }
        }

    if(count >= 1)
    {
      send_to_char("You can't control any more undead.\n\r",ch);
      return;
    }

    act("$n chants, 'From the depths of hell I summon thee spirit of the damned.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'From the depths of hell I summon thee spirit of the damned.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'Return to the living to once again draw blood.",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'Return to the living to once again draw blood.",ch,NULL,NULL,TO_CHAR);
    act("$n chants, 'Return now, I COMMAND THEE!!!",ch,NULL,NULL,TO_ROOM);
    act("You chant, 'Return now, I COMMAND THEE!!!",ch,NULL,NULL,TO_CHAR);
    victim = create_mobile(  get_mob_index(  MOB_VNUM_ANIMATE ) );
    char_to_room( victim, ch->in_room );
    victim->level = ch->level-10;
    victim->max_hit = (sh_int)(dice(30,8) + ch->max_hit/2);
    victim->hit = victim->max_hit;
    victim->timer = 250;
    victim->armor[AC_PIERCE]    = ch->armor[AC_PIERCE];
    victim->armor[AC_BASH]	= ch->armor[AC_BASH];
    victim->armor[AC_SLASH]     = ch->armor[AC_SLASH];
    victim->armor[AC_EXOTIC]    = ch->armor[AC_EXOTIC];
    victim->hitroll             = ch->hitroll;
    victim->damroll             = GET_DAMROLL(ch);
    victim->damage[DICE_NUMBER] = ch->damage[DICE_NUMBER] + 1;
    victim->damage[DICE_TYPE]   = ch->damage[DICE_TYPE] + 1;
    snprintf(buf, sizeof buf,"vampire");
    free_string(victim->name);
    victim->name = str_dup(buf);
    snprintf(buf, sizeof buf,"a vampire");
    free_string(victim->short_descr);
    victim->short_descr = str_dup(buf);
    snprintf(buf, sizeof buf,"A vampire is here serving %s.\n\r",ch->name);
    free_string(victim->long_descr);
    victim->long_descr = str_dup(buf);
    snprintf(buf, sizeof buf,"spec_cast_mage");
    victim->spec_fun = spec_lookup ( buf );
    extract_obj(corpse);
    act("Flesh rejuvenates itself, and a vampire stands up.",ch,NULL,NULL,TO_ROOM);
    act("Flesh rejuvenates itself, and a vampire stands up.",ch,NULL,NULL,TO_CHAR);
    add_follower( victim, ch );
    victim->leader = ch;
    af.type      = (sh_int)(skill_lookup("charm person"));
    af.level	 = ch->level;
    af.duration  = victim->timer;
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = AFF_CHARM;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
    return;
}

/* TAR_OBJ_HERE */
void spell_animate_parts( int sn, int level, CHAR_DATA *ch, void *vo )
{
  OBJ_DATA *obj = (OBJ_DATA *) vo;
  CHAR_DATA *victim;
  int count;
  int part = 0;
  int dam = 0;


  if(ch->fighting == NULL)
  {
    send_to_char("You can only cast this while fighting.\n\r",ch);
    return;
  }
  else
    victim = ch->fighting;

  for( count = 12; count < 17; count++ )
  {
    if(obj->pIndexData->vnum == count)
    {
      part = count;
      break;
    }
  }

  if(part == 0 )
  {
    send_to_char("There are no body parts here to animate.\n\r",ch);
    return;
  }

  switch( part )
  {
    case 12:
      send_to_char("A head rolls over and bites you on the leg!\n\r",victim);
      act("A head rolls over and bites $N on the leg!",ch,NULL,victim,TO_ROOM);
      dam = dice(level,4);
    break;
    case 13:
      send_to_char("A bleeding heart fly's up and...bleeds on you?\n\r",victim);
      act("A bleeding heart fly's up and...bleeds on $N.",ch,NULL,victim,TO_ROOM);
      dam = dice(level,8);
    break;
    case 14:
      send_to_char("A severed arm leaps into the air and hits you!\n\r",victim);
      act("A severed arm leaps into the air and beats on $N!",ch,NULL,victim,TO_ROOM);
      dam = dice(level,6);
    break;
    case 15:
      send_to_char("A severed leg hops up and kicks you!\n\r",victim);
      act("A severed leg hops up and kicks $N!",ch,NULL,victim,TO_ROOM);
      dam = dice(level,6);
    break;
    case 16:
      send_to_char("Some guts float over to you and try to strangle you!\n\r",victim);
      act("Some guts float over and try to strangle $N!",ch,NULL,victim,TO_ROOM);
      dam = dice(level,5);
    break;
  }
  send_to_char("The severed part attacks!\n\r",ch);
  damage( ch, victim, dam, sn, DAM_BASH );
  extract_obj(obj);
  return;
}

void spell_maze( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;
    int chance;

    if ( is_affected( victim, sn ) )
    {
	if (victim == ch)
	  send_to_char("You can't use this on yourself.\n\r",ch);
	else
	  act("$N is already affected.",ch,NULL,victim,TO_CHAR);
	return;
    }

    chance = number_percent();

    if ( saves_spell( level, victim ) && chance < 65 )
      victim = ch;

    af.type      = (sh_int)(sn);
    af.level	 = (sh_int)(level);
    af.duration  = 12;
    af.modifier  = 0;
    af.location  = 0;
    af.bitvector = 0;
    af.bitvector2= 0;
    affect_to_char( victim, &af );
    send_to_char( "You lose your direction sense.\n\r", victim );
    if ( ch != victim )
	act("$N has lost their direction sense.",ch,NULL,victim,TO_CHAR);
    return;

}

void spell_shroud( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;

    if( is_affected(victim, skill_lookup("major globe") ) )
    {
      send_to_char("You can't combine this with a globe spell.\n\r",ch);
      return;
    }

    if ( is_affected( victim, sn ) )
    {
	if (victim == ch)
	  send_to_char("You are already cloaked in a shroud of darkness.\n\r",ch);
	else
	  act("$N is already cloaked in a shroud of darkness.",ch,NULL,victim,TO_CHAR);
	return;
    }
    af.type      = (sh_int)(sn);
    af.level     = (sh_int)(level);
    af.duration  = (sh_int)(level);
    af.location  = APPLY_AC;
    af.modifier  = -35;
    af.bitvector = 0;
    af.bitvector2 = 0;
    affect_to_char( victim, &af );
    act( "$n is cloaked in a shroud of darkness.", victim, NULL, NULL, TO_ROOM );
    send_to_char( "A shroud of darkness enfolds you in it's protection.\n\r", victim );
    return;
}

void spell_cone_of_cold( int sn, int level, CHAR_DATA *ch, void *vo )
{
   UNUSED_PARAM(vo);
   CHAR_DATA *vch;
   CHAR_DATA *vch_next;


    send_to_char( "A cone of frost fans out from your hands!\n\r", ch );
    act( "A cone of frost fans out from $n's hands.", ch, NULL, NULL, TO_ROOM );

    for ( vch = ch->in_room->people; vch != NULL; vch = vch_next )
    {
      vch_next = vch->next_in_room;

      if ( !is_safe_spell(ch,vch,true) )
      {
          if ( vch != ch )
          {
              if ( damage(ch,vch,dice(level/2,6),sn,DAM_COLD) )
                  continue;
          }
          if( vch->in_room != ch->in_room)
              break;
      }

    }
   return;
}


void spell_embalm( int sn, int level, CHAR_DATA *ch, void *vo )
{
  UNUSED_PARAM(sn);
  UNUSED_PARAM(level);
  OBJ_DATA *obj = (OBJ_DATA *) vo;
  char buf[MAX_STRING_LENGTH];
  int part = 0;
  int count;

  for( count = 10; count < 17; count++ )
  {
    if(obj->pIndexData->vnum == count)
    {
      part = count;
      break;
    }
  }

  if(part == 0 )
  {
    send_to_char("There is nothing here that you can embalm.",ch);
    return;
  }

  if(obj->timer > 0 && obj->timer < 30)
  {
    snprintf(buf, sizeof buf,"%s throws a strange powder on the %s.",
	   ch->name,obj->short_descr ? obj->short_descr : obj->name);
    act( buf, ch, NULL, NULL, TO_ROOM );
    snprintf(buf, sizeof buf,"The powder is quickly absorbed by the %s.",
	   obj->short_descr ? obj->short_descr : obj->name);
    act( buf, ch, NULL, NULL, TO_ROOM );

    snprintf(buf, sizeof buf,"You throw a preservative powder on the %s, which is quickly absorbed.",
	   obj->short_descr ? obj->short_descr : obj->name);
    act( buf, ch, NULL, NULL, TO_CHAR );
    obj->timer += 5;
    SET_BIT( obj->extra_flags, ITEM_EMBALMED );
  }
  else
    send_to_char("You can't preserve it any more than it already is!",ch);

  return;

}

/* Meteor swarm recoded on 2/25/99 - Rico */
void spell_meteor_swarm( int sn, int level, CHAR_DATA *ch, void *vo )
{
     UNUSED_PARAM(vo);
     CHAR_DATA *gch, *vch;
   int count2,count3;

    send_to_char( "Meteors explode from your hands!\n\r", ch );
    act( "Meteors explode from $n's outstretched palms.", ch, NULL, NULL, TO_ROOM );


    vch = ch->in_room->people;

    count2 = 0;
    count3 = 0;

    /* count up the mobs/players in the room, 3 meteors per */
    for ( gch = vch; gch != NULL; gch = gch->next_in_room )
       count3 += 3;

    /* Don't give too many attacks, 12 is plenty */
    if (count3 > 12)
       count3 = 12;

      {
      CHAR_DATA *gch_next;
      for ( gch = vch; gch != NULL; gch = gch_next )
      {
        gch_next = gch->next_in_room;  /* save before possible extraction */
                            /*fix?*/
        if ( gch != ch && !is_safe_spell(ch,gch,true) && gch->in_room == ch->in_room)
        {
           bool gch_killed = false;
           /* For some randomness, lets subtract 1 meteor 15% of the time */
           if (number_percent() > 85)
             count3--;

           /* Do 4 attacks at most per mob, then go to the next mob */
           while( count2 < 4 && count3 > 0 && gch->in_room == ch->in_room)
           {
             if(saves_spell(level,gch) )
               gch_killed = damage(ch,gch,dice(level,5),sn,DAM_FIRE);
             else
               gch_killed = damage(ch,gch,dice(level,7),sn,DAM_FIRE);
             count2++;
             count3--;
             if (gch_killed)
               break;  /* gch was killed; stop attacking it */
           }

           if (count3 < 1)
             break;

           count2 = 0;

        }
      }
      }
   return;
}


/* Fixed trap the soul recoded from the original trap the soul code by Ricochet on
   10/1/97.  Look at the do_open function in act_move.c for the rest of the code */

void spell_trap_the_soul_fixed(int sn,int level, CHAR_DATA *ch, void *vo)
{

  UNUSED_PARAM(sn);
  CHAR_DATA *victim = (CHAR_DATA *) vo;
  OBJ_DATA *obj;
  bool found=false;
  char buf[MAX_STRING_LENGTH];

      if(!IS_NPC(victim) || is_safe_spell(ch,victim,false) ||
       saves_spell(level,victim) || IS_SET(victim->act, ACT_AGGRESSIVE) ||
       victim->fighting != NULL)
      {
        send_to_char("Spell failed.\n\r",ch);
        return;
      }

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        if ( obj->wear_loc == WEAR_NONE
        &&   can_see_obj( ch, obj )
        &&   obj->item_type == ITEM_SOUL_CONTAINER
        &&   obj->trapped == NULL
        &&   obj->value[3] == 0 )
        {
          found = true;
          break;
        }
    }

    if (!found)
    {
        send_to_char("You have no empty soul container to put them in.\n\r",ch);
        return;
    }

    if ( victim->fighting != NULL)
    {
        send_to_char("Spell failed.\n\r",ch);
        return;
    }


    if (IS_SET(victim->act,ACT_AGGRESSIVE))
    {
	send_to_char("Spell failed.\n\r",ch);
        return;
    }

    if (victim->level > ch->level)
    {
        send_to_char("Spell failed.\n\r",ch);
        return;
    }

    if(found)
     {
      act("$N screams as $e is sucked into $p!",ch,obj,victim,TO_NOTVICT);
      act("$N screams as $e is sucked into $p!",ch,obj,victim,TO_CHAR);
      act("You scream as you are sucked into $p!",ch,obj,victim,TO_VICT);
      obj->value[3] = victim->pIndexData->vnum;
      free_string(obj->short_descr);
      snprintf(buf, sizeof buf,"a bottle containing essence of %s",victim->name);
      obj->short_descr = str_dup(buf);
      free_string(obj->description);
      snprintf(buf, sizeof buf,"A bottle containing essence of %s is here.",victim->name);
      obj->description = str_dup(buf);
      extract_char(victim, true);
      if ( !IS_NPC(ch) )
        save_char_obj(ch);
     }
    else
      send_to_char("Nothing happens.\n\r",ch);
   return;
}


/*(void spell_trap_the_soul( int sn, int level, CHAR_DATA *ch, void *vo )
{
  CHAR_DATA *victim = (CHAR_DATA *) vo;
  OBJ_DATA *obj;
  bool found = false;
  char buf[MAX_STRING_LENGTH];

    if(!IS_IMMORTAL(ch) )
    {
      if(!IS_NPC(victim) || is_safe_spell(ch,victim,false) ||
       saves_spell(level,victim) || IS_SET(victim->act, ACT_AGGRESSIVE) ||
       victim->fighting != NULL)
      {
	send_to_char("Spell failed.\n\r",ch);
	return;
      }
    }
    else if( !IS_NPC(victim) )
      return;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( obj->wear_loc == WEAR_NONE
	&&   can_see_obj( ch, obj )
	&&   obj->item_type == ITEM_SOUL_CONTAINER
	&&   obj->trapped == NULL )
	{
	  found = true;
	  break;
	}
    }

    if(found)
    {
      act("$N screams as $e is sucked into $p!",ch,obj,victim,TO_NOTVICT);
      act("$N screams as $e is sucked into $p!",ch,obj,victim,TO_CHAR);
      act("You scream as you are sucked into $p!",ch,obj,victim,TO_VICT);
      if(!IS_NPC(victim) )
	obj->timer = 1;
      char_to_obj(victim,obj);
      free_string(obj->short_descr);
      snprintf(buf, sizeof buf,"a bottle containing essence of %s",victim->name);
      obj->short_descr = str_dup(buf);
      free_string(obj->description);
      snprintf(buf, sizeof buf,"A bottle containing essence of %s is here.",victim->name);
      obj->description = str_dup(buf);
    }
    else
      send_to_char("Nothing happens.\n\r",ch);
   return;

}*/

void spell_fire_shield( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;

  if( is_affected( victim, sn )
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_HOT)
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_COLD) )
    {
	if (victim == ch)
	  send_to_char("You are already enveloped in flames.\n\r",ch);
	else
	  act("You can't cast this spell on $N.",ch,NULL,victim,TO_CHAR);
	return;
    }
    af.type      = (sh_int)(sn);
    af.level     = (sh_int)(level);
    if(IS_IMMORTAL(ch) )
      af.duration  = ch->level;
    else
      af.duration  = (sh_int)(dice(10,2) + 5);
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = 0;
    af.bitvector2 = AFF2_FLAMING_HOT;
    affect_to_char( victim, &af );
    act( "$n's shouts 'FLAME ON!' and bursts into flames.", victim,
	  NULL, NULL, TO_ROOM );
    send_to_char( "You are enveloped in an aura of molten flame!\n\r", victim );
    return;
}

void spell_frost_shield( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;

  if( is_affected( victim, sn )
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_HOT)
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_COLD) )
    {
	if (victim == ch)
	  send_to_char("You are already enveloped in frost.\n\r",ch);
	else
	  act("You can't cast this spell on $N.",ch,NULL,victim,TO_CHAR);
	return;
    }
    af.type      = (sh_int)(sn);
    af.level     = (sh_int)(level);
    if(IS_IMMORTAL(ch) )
    af.duration  = ch->level;
    else
    af.duration  = (sh_int)(dice(10,2) + 5);
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = 0;
    af.bitvector2 = AFF2_FLAMING_COLD;
    affect_to_char( victim, &af );
    act( "$n's shouts 'ICE ICE BABY!' and bursts into flames.", victim,
	  NULL, NULL, TO_ROOM );
    send_to_char( "You are enveloped in an aura of frozen flame!\n\r", victim );
    return;
}

void spell_death_shroud( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;

  if( is_affected( victim, sn )
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_HOT)
  ||  IS_AFFECTED2(victim, AFF2_FLAMING_COLD) )
    {
	if (victim == ch)
	  send_to_char("You are already surrounded by dark flames.\n\r",ch);
	else
	  act("You can't cast this spell on $N.",ch,NULL,victim,TO_CHAR);
	return;
    }
    af.type      = (sh_int)(sn);
    af.level     = (sh_int)(level);
    if(IS_NPC(ch) )
      af.duration  = (sh_int)(dice(10,2) + 5);
    else
      af.duration  = (sh_int)(level/15 + 1);
    af.location  = 0;
    af.modifier  = 0;
    af.bitvector = 0;
    if(number_percent () > 60)
       af.bitvector2 = AFF2_FLAMING_COLD;
    else
       af.bitvector2 = AFF2_FLAMING_HOT;
    affect_to_char( victim, &af );
    act( "$n's chants, 'Harm those who would harm me.'", victim,
	  NULL, NULL, TO_ROOM );
    send_to_char( "You an aura of dark flames surrounds you.\n\r", victim );
    return;
}


void spell_detect_traps( int sn, int level, CHAR_DATA *ch, void *vo )
{
  UNUSED_PARAM(sn);
  UNUSED_PARAM(level);
  UNUSED_PARAM(vo);
  int door;
  OBJ_DATA *obj;
  bool found = false;
  EXIT_DATA *pexit;
  char buf[MAX_STRING_LENGTH];
  char direction[MAX_STRING_LENGTH];

     for ( door = 0; door <= 9; door++ )
     {
       switch ( door )
       {
        case 0:  toc_strlcpy( direction, "north", sizeof(direction));
        break;
        case 1:  toc_strlcpy( direction, "east", sizeof(direction));
        break;
        case 2:  toc_strlcpy( direction, "south", sizeof(direction));
        break;
        case 3:  toc_strlcpy( direction, "west", sizeof(direction));
        break;
        case 4:  toc_strlcpy( direction, "up", sizeof(direction));
        break;
        case 5:  toc_strlcpy( direction, "down", sizeof(direction));
        break;
        case 6:  toc_strlcpy( direction, "northeast", sizeof(direction));
        break;
        case 7:  toc_strlcpy( direction, "northwest", sizeof(direction));
        break;
        case 8:  toc_strlcpy( direction, "southeast", sizeof(direction));
        break;
        case 9:  toc_strlcpy( direction, "southwest", sizeof(direction));
        break;
       }

         if ( ( pexit = ch->in_room->exit[door] ) != NULL
             && IS_SET(pexit->exit_info, EX_ISDOOR)
             && IS_SET(pexit->exit_info, EX_TRAPPED) )
             {
              snprintf(buf, sizeof buf,
                       "There is a trap on the %.200s to the %.32s!\n\r",
                       pexit->keyword,
                       direction);
	     send_to_char(buf,ch);
	     found = true;
	   }
     }

    for ( obj = ch->in_room->contents; obj != NULL; obj = obj->next_content )
    {
	if ( can_see_obj( ch, obj ) )
	{
	 if ( obj->item_type == ITEM_CONTAINER
	  &&  IS_SET(obj->value[1], CONT_TRAPPED) )
	  {
	    act( "$p is trapped!", ch,  obj, NULL, TO_CHAR );
	    found = true;
	  }
	}

    }

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( can_see_obj( ch, obj ) )
	{
	 if ( obj->item_type == ITEM_CONTAINER
	  &&  IS_SET(obj->value[1], CONT_TRAPPED) )
	  {
	    act( "$p you hold is trapped!", ch, obj, NULL, TO_CHAR );
	    found = true;
	  }
	}
    }

    if(!found)
      send_to_char("Your magic revealed no traps.\n\r",ch);
    return;
}


void spell_stinking_cloud( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
    ROOM_AFF_DATA *raf;
    CHAR_DATA *gch;
    CHAR_DATA *gch_next;

    if(ch->in_room->affected != NULL)
    {
       send_to_char("Nothing seems to happen.\n\r",ch);
       return;
    }

    raf             = alloc_mem(sizeof(*raf) );
    raf->room       = ch->in_room;
    raf->timer      = (sh_int)(dice(1,3));
    raf->type       = 1;
    raf->level      = ch->level;
    raf->name       = "stinking cloud";
    raf->bitvector  = AFF_POISON;
    raf->bitvector2 = 0;
    raf->modifier   = -2;
    raf->location   = APPLY_HITROLL;
    raf->duration   = (sh_int)(dice(1,4));
    raf->aff_exit   = 10;
    raf->dam_dice   = 2;
    raf->dam_number = 8;
    ch->in_room->affected = raf;
    affect_to_room(ch->in_room, ch->in_room->affected);

    send_to_char("You call forth noxious fumes from the bowels of the earth.\n\r",ch);
    act("$n shouts out, 'Lords of the Earth! I beseach your aid! Guard my retreat!'",ch,NULL,NULL,TO_ROOM);
    act("$n call is heard, and noxious fumes rise out of the ground!",ch,NULL,NULL,TO_ROOM);

    for ( gch = ch->in_room->people; gch != NULL; gch = gch_next )
    {
       gch_next = gch->next_in_room;
       if(gch == ch)
         continue;
       room_affect(gch, ch->in_room, 10);
    }
    return;
}

void spell_rope_trick( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
    ROOM_AFF_DATA *raf;
    EXIT_DATA *pexit;
    ROOM_INDEX_DATA *pRoomIndex, *pHolder;
    char *defaultRoomName = "In a pocket dimension.\n\r";
    char *defaultRoomDesc = "You stand in a misty room out of phase with the world.\n\r";
    size_t name_len, desc_len;
    int iHash, door, vnum;


    if(ch->in_room->affected != NULL && ch->in_room->affected->type == EXTRA_DIMENSIONAL)
    {
      send_to_char("You failed.\n\r",ch);
      return;
    }

    pRoomIndex                  = alloc_mem( sizeof(*pRoomIndex) );
    pRoomIndex->people          = NULL;
    pRoomIndex->contents        = NULL;
    pRoomIndex->extra_descr     = NULL;
    pRoomIndex->area            = new_area;
    {
      int attempts;
      for (attempts = 0; attempts < 1000; attempts++)
      {
         vnum = number_range( 1, 30000);
         pHolder = get_room_index( vnum );
         if ( pHolder == NULL )
            break;
      }
      if ( pHolder != NULL ) /* no free vnum found */
      {
         send_to_char("The magic fails to find a suitable dimension.\n\r",ch);
         return;
      }
    }
    pRoomIndex->vnum            = (sh_int)(vnum);
    name_len                    = strlen(defaultRoomName) + 1;
    pRoomIndex->name            = alloc_mem( (int)name_len );
    toc_strlcpy(pRoomIndex->name, defaultRoomName, name_len);
    desc_len                    = strlen(defaultRoomDesc) + 1;
    pRoomIndex->description     = alloc_mem( (int)desc_len );
    toc_strlcpy(pRoomIndex->description, defaultRoomDesc, desc_len);
    pRoomIndex->room_flags      = 0;
    pRoomIndex->room_flags2     = 0;
    pRoomIndex->sector_type     = 0;
    pRoomIndex->light           = 0;
    pRoomIndex->affected        = NULL;
    for ( door = 0; door <= 9; door++ )
       pRoomIndex->exit[door] = NULL;

    iHash                      = vnum % MAX_KEY_HASH;
    pRoomIndex->next           = room_index_hash[iHash];
    room_index_hash[iHash]     = pRoomIndex;

    ch->was_in_room = ch->in_room;
    char_from_room(ch);
    char_to_room(ch,pRoomIndex);

    pexit                   = alloc_mem( sizeof(*pexit) );
    pexit->description      = "";
    pexit->keyword          = "";
    pexit->exit_info        = 0;
    pexit->lock             = 0;
    pexit->key              = 0;
    pexit->u1.to_room    = ch->was_in_room;
    ch->in_room->exit[5] = pexit;

    raf             = alloc_mem(sizeof(*raf) );
    raf->room       = pRoomIndex;
    raf->timer      = (sh_int)(1 + dice(2,2));
    raf->type       = 2;
    raf->level      = ch->level;
    raf->name       = "rope trick";
    raf->bitvector  = 0;
    raf->bitvector2 = 0;
    raf->modifier   = 0;
    raf->location   = 0;
    raf->duration   = 0;
    raf->aff_exit   = 10;
    raf->dam_dice   = 0;
    raf->dam_number = 0;
    pRoomIndex->affected = raf;
    affect_to_room(pRoomIndex, pRoomIndex->affected);
    SET_BIT(pRoomIndex->room_flags, ROOM_MANA_REGEN);
    SET_BIT(pRoomIndex->room_flags, ROOM_SAFE);
    SET_BIT(pRoomIndex->room_flags, ROOM_NO_RECALL);

    send_to_char("You throw a rope into the air and climb up it.\n\r",ch);
    act("$n throw's a rope in the air, climbs up it, and is gone!",ch,NULL,NULL,TO_ROOM);
    do_look(ch,"auto");
    return;

}
void spell_haven( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
    ROOM_AFF_DATA *raf;
    CHAR_DATA *gch, *gch_next;
    EXIT_DATA *pexit;
    ROOM_INDEX_DATA *pRoomIndex, *pHolder, *in_room;
    char *defaultRoomName = "In a pocket dimension.\n\r";
    char *defaultRoomDesc = "You stand in a misty room out of phase with the world.\n\r";
    size_t name_len, desc_len;
    int iHash, door, vnum;


    if(ch->in_room->affected != NULL && ch->in_room->affected->type == EXTRA_DIMENSIONAL)
    {
      send_to_char("You failed.\n\r",ch);
      return;
    }

    pRoomIndex                  = alloc_mem( sizeof(*pRoomIndex) );
    pRoomIndex->people          = NULL;
    pRoomIndex->contents        = NULL;
    pRoomIndex->extra_descr     = NULL;
    pRoomIndex->area            = new_area;
    {
        int attempts;
        for (attempts = 0; attempts < 1000; attempts++)
        {
            vnum = number_range( 1, 30000);
            pHolder = get_room_index( vnum );
            if ( pHolder == NULL )
                break;
        }
        if ( pHolder != NULL ) /* no free vnum found */
        {
            send_to_char("The magic fails to find a suitable haven.\n\r",ch);
            return;
        }
    }
    pRoomIndex->vnum            = (sh_int)(vnum);
    name_len                    = strlen(defaultRoomName) + 1;
    pRoomIndex->name            = alloc_mem( (int)name_len );
    toc_strlcpy(pRoomIndex->name, defaultRoomName, name_len);
    desc_len                    = strlen(defaultRoomDesc) + 1;
    pRoomIndex->description     = alloc_mem( (int)desc_len );
    toc_strlcpy(pRoomIndex->description, defaultRoomDesc, desc_len);
    pRoomIndex->room_flags      = 0;
    pRoomIndex->room_flags2     = 0;
    pRoomIndex->sector_type     = 0;
    pRoomIndex->light           = 0;
    pRoomIndex->affected        = 0;
    for ( door = 0; door <= 9; door++ )
	pRoomIndex->exit[door] = NULL;

    iHash			= vnum % MAX_KEY_HASH;
    pRoomIndex->next    	= room_index_hash[iHash];
    room_index_hash[iHash]	= pRoomIndex;

    act("$n says, 'Rulers of the elemental planes, hear my plea!'",ch,NULL,NULL,TO_ROOM);
    act("'My companions and I are weary, and would seek a safe haven.'",ch,NULL,NULL,TO_ROOM);
    act("'Lend us but a small part of your vast holdings so we may rest.'",ch,NULL,NULL,TO_ROOM);

    in_room = ch->in_room;
    for(gch = in_room->people; gch != NULL; gch = gch_next)
    {
      gch_next = gch->next_in_room;

      if(is_same_group(gch,ch) && !gch->fighting)
      {
	act("$n is pulled into a magical portal and is gone.",gch,NULL,NULL,TO_ROOM);
	gch->was_in_room = gch->in_room;
	char_from_room(gch);
	char_to_room(gch,pRoomIndex);
	do_look(gch,"auto");
      }
    }

    pexit                   = alloc_mem( sizeof(*pexit) );
    pexit->description      = "";
    pexit->keyword          = "";
    pexit->exit_info        = 0;
    pexit->lock             = 0;
    pexit->key              = 0;
    pexit->trap             = 0;
    pexit->u1.to_room    = ch->was_in_room;
    ch->in_room->exit[5] = pexit;

    raf             = alloc_mem(sizeof(*raf) );
    raf->room       = pRoomIndex;
    raf->timer      = (sh_int)(2 + dice(3,2));;
    raf->type       = 2;
    raf->level      = ch->level;
    raf->name       = "haven";
    raf->bitvector  = 0;
    raf->bitvector2 = 0;
    raf->modifier   = 0;
    raf->location   = 0;
    raf->duration   = 0;
    raf->aff_exit   = 10;
    raf->dam_dice   = 0;
    raf->dam_number = 0;
    pRoomIndex->affected = raf;
    affect_to_room(pRoomIndex, pRoomIndex->affected);
    SET_BIT(pRoomIndex->room_flags, ROOM_MANA_REGEN);
    SET_BIT(pRoomIndex->room_flags, ROOM_HP_REGEN);
    SET_BIT(pRoomIndex->room_flags, ROOM_SAFE);
    SET_BIT(pRoomIndex->room_flags, ROOM_NO_RECALL);

    return;
}

void spell_butcher( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    OBJ_DATA *corpse = (OBJ_DATA *) vo;
    OBJ_DATA *arm1 = NULL;
    OBJ_DATA *arm2 = NULL;
    OBJ_DATA *head = NULL;
    OBJ_DATA *leg1 = NULL;
    OBJ_DATA *leg2 = NULL;
    char buf[MAX_STRING_LENGTH];

    if(corpse->item_type != ITEM_CORPSE_NPC)
    {
	send_to_char( "You can't do this on players corpses!\n\r",ch);
	return;
    }

    act("$n pulls out a rusty cleaver and cuts into the corpse.",ch,NULL,NULL,TO_ROOM);
    act("You pull out a rusty cleaver and cut into the corpse.",ch,NULL,NULL,TO_CHAR);
    act("$n yells 'Praise the dark lords fresh body parts!'",ch,NULL,NULL,TO_ROOM);
    act("You yell 'Praise the dark lords fresh body parts!'",ch,NULL,NULL,TO_CHAR);


    arm1 = create_object( get_obj_index( OBJ_VNUM_SLICED_ARM ), 0 );
    snprintf( buf, sizeof(buf), "A surgically removed arm" );
    free_string( arm1->short_descr );
    arm1->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), "A surgically removed arm waits to serve %s", ch->name );
    free_string( arm1->description );
    arm1->description = str_dup( buf );
    obj_to_room( arm1, ch->in_room );
    arm1->timer = 250;
    arm2 = create_object( get_obj_index( OBJ_VNUM_SLICED_ARM ), 0 );
    snprintf( buf, sizeof(buf), "A surgically removed arm" );
    free_string( arm2->short_descr );
    arm2->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), "A surgically removed arm waits to serve %s", ch->name );
    free_string( arm2->description );
    arm2->description = str_dup( buf );
    obj_to_room( arm2, ch->in_room );
    arm2->timer = 250;
    leg1 = create_object( get_obj_index( OBJ_VNUM_SLICED_LEG ), 0 );
    snprintf( buf, sizeof(buf), "A surgically removed leg" );
    free_string( leg1->short_descr );
    leg1->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), "A surgically removed leg waits to serve %s", ch->name );
    free_string( leg1->description );
    leg1->description = str_dup( buf );
    obj_to_room( leg1, ch->in_room );
    leg1->timer = 250;
    leg2 = create_object( get_obj_index( OBJ_VNUM_SLICED_LEG ), 0 );
    snprintf(buf, sizeof buf,"A surgically removed leg" );
    free_string( leg2->short_descr );
    leg2->short_descr = str_dup( buf );
    snprintf(buf, sizeof buf,"A surgically removed leg waits to serve %s", ch->name );
    free_string( leg2->description );
    leg2->description = str_dup( buf );
    obj_to_room( leg2, ch->in_room );
    leg2->timer = 250;
    head = create_object( get_obj_index( OBJ_VNUM_SEVERED_HEAD ), 0 );
    snprintf( buf, sizeof(buf), "A surgically removed head" );
    free_string( head->short_descr );
    head->short_descr = str_dup( buf );
    snprintf( buf, sizeof(buf), "A surgically removed head grins at %s", ch->name );
    free_string( head->description );
    head->description = str_dup( buf );
    obj_to_room( head, ch->in_room );
    head->timer = 250;
    extract_obj( corpse );
    return;
}

void spell_bewitch_weapon( int sn, int level, CHAR_DATA *ch, void *vo )
{

    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);

    OBJ_DATA *obj = (OBJ_DATA *) vo;

    if ( obj->wear_loc != -1 )
    {
	send_to_char("You must be carrying this item to curse it.\n\r",ch);
	return;
    }

    if ( obj->level > ch->level )
    {
	send_to_char("The weapon resists your curse!\n\r",ch);
	return;
    }

    if ( obj->item_type != ITEM_WEAPON )
    {
	send_to_char("It has to be a weapon.\n\r",ch);
	return;
    }

    if( IS_SET(obj->extra_flags, ITEM_NOREMOVE ) )
    {
	send_to_char("This item is bewitched already!\n\r",ch);
	return;
    }

    act("$n begins a low rumbling chant..",ch, NULL,NULL,TO_ROOM);
    act("You begin a low rumbling chant.",ch,NULL,NULL,TO_CHAR);
    act("Suddenly black mists form over the weapon.",ch,NULL,NULL,TO_ROOM);
    act("Suddenly black mists form over the weapon.",ch,NULL,NULL,TO_CHAR);
    act("$n screams 'AIGEN BALTHEMEL CIOR!!",ch,NULL,NULL,TO_ROOM);
    act("You scream words of power!",ch,NULL,NULL,TO_CHAR);
    act("A sharp blast of lightning blinds you, but you see the weapon glow.",
	 ch, NULL, NULL, TO_ROOM );
    act("A sharp blast of lightning blinds you, but you see the weapon glow.",
	 ch, NULL, NULL, TO_CHAR );

    SET_BIT(obj->extra_flags, ITEM_NOREMOVE );

    return;

}

void spell_divine_intervention( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
    CHAR_DATA *gch;

    if( ch->mana < 130 )
    {
	send_to_char("You failed.\n\r",ch);
	return;
    }

    act("$n falls to their knees and gestures at the sky",
	 ch,NULL,NULL,TO_ROOM);
    act("You fall to your knees and open your arms towards the sky.",
	 ch,NULL,NULL,TO_CHAR);
    act("Suddenly the sky breaks open and a shaft of light strikes you!",
	 ch, NULL, NULL, TO_ROOM);
    act("You are suddenly enveloped in a brillant shaft of light!",
	 ch, NULL, NULL, TO_CHAR);
    act("$n yells 'Let the stream of life HEAL! these mortal shells.'",
	 ch, NULL, NULL, TO_ROOM);
    act("You yell 'Let the stream of life HEAL! these mortal shells.'",
	 ch, NULL, NULL, TO_CHAR);

    ch->mana = 0;

    for( gch = ch->in_room->people; gch != NULL; gch = gch->next_in_room )
    {
    	if(!is_same_group(gch, ch))
	  continue;

    gch->hit = gch->max_hit;
    gch->move = gch->max_move;

    gch->position = POS_RESTING;

    }

    act("You fall to the ground exausted.",ch,NULL,NULL,TO_ROOM);
    act("You fall to the ground exausted.",ch,NULL,NULL,TO_CHAR);

    return;

}

/*
 * Balls nasty area dispel magic for necromancer
 */

void spell_neutrality_field( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    UNUSED_PARAM(vo);
    CHAR_DATA *vch;
    CHAR_DATA *vch_next;
    int sn2;

    sn2 = skill_lookup("dispel magic");
    if ( sn2 < 0 )
        return;

    if( ch->position != POS_FIGHTING )
    {
	send_to_char("You may only cast this in combat.\n\r",ch);
	return;
    }

    act("A wave of black energy flys from your hand.",ch,NULL,NULL,TO_CHAR);
    act("The room becomes dim and suffocating.",ch,NULL,NULL,TO_ROOM);


    for ( vch = ch->in_room->people; vch != NULL; vch = vch_next )
    {
	vch_next = vch->next_in_room;
	if(!is_safe_spell(ch,vch,true))
	{
	    vo = (void *)vch;
	    (*skill_table[sn2].spell_fun) (sn2, ch->level, ch, vo );
	}
    }
    return;
}

void spell_shock_sphere( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;

    act("A glowing ball of electrical energy flys from $n's hand!",
	 ch,NULL,NULL,TO_ROOM);
    act("A glowing ball of electrical energy flys from your hand!",
	 ch,NULL,NULL,TO_CHAR);
    act("It strikes $N and they jiggle and shake.",ch,NULL,victim,TO_ROOM);
    act("It strikes $N and they jiggle and shake.",ch,NULL,victim,TO_CHAR);

    damage( ch, victim, dice(level, 5)+ level, sn, DAM_LIGHTNING );
    return;

}

void spell_ghostly_presence( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(vo);
    AFFECT_DATA af;

    if( IS_AFFECTED2( ch, AFF2_GHOST ) )
    {
	send_to_char("You are already affected by this spell.\n\r",ch);
	return;
    }

    af.type = (sh_int)(sn);
    af.level		= (sh_int)(level);
    af.duration		= (sh_int)(dice(2,2) + 1);
    af.location		= APPLY_NONE;
    af.modifier		= 0;
    af.bitvector	= 0;
    af.bitvector2	= AFF2_GHOST;
    affect_to_char( ch, &af );
    act("$n chants 'To the great lords of the dead'",ch,NULL,NULL,TO_ROOM );
    act("You chant 'To the great lords of the dead'",ch,NULL,NULL,TO_CHAR );
    act("$n chants 'Protect this body from earthly dread'",ch,NULL,NULL,TO_ROOM);
    act("You chant 'Protect this body from earthly dread'",ch,NULL,NULL,TO_CHAR);
    act("$n chants 'Make this form which was alive'",ch,NULL,NULL,TO_ROOM);
    act("You chant 'Make this form which was alive'",ch,NULL,NULL,TO_CHAR);
    act("$n chants 'Appear to be the living dead!'",ch,NULL,NULL,TO_ROOM);
    act("You chant 'Appear to be the living dead!'",ch,NULL,NULL,TO_CHAR);
    act("$n's body fades and becomes ghostly in apperance.",ch,NULL,NULL,TO_ROOM);
    act("Your body fades and becomes ghostly in apperance.",ch,NULL,NULL,TO_CHAR);

    return;
}

/* spells for spec_beholder and spec_deathknight */

void spell_death_ray( int sn, int level, CHAR_DATA *ch, void *vo )
{
    UNUSED_PARAM(sn);
    UNUSED_PARAM(level);
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    char buf[MAX_STRING_LENGTH];

    if(victim == NULL)
 	return;

    if(victim == ch)
    {
	send_to_char("Trying to kill yourself pretty silly!\n\r",ch);
	return;
    }

    if(victim->level == MAX_LEVEL) {
	snprintf(buf, sizeof buf," %s",ch->name);
	do_slay(victim,buf);
	return;
    }
    send_to_char("A sickly ray of green light flys from your hand!\n\r",ch);
    act("A sickly ray of green light flys from $n's hand and strikes you!",
	 ch,NULL,NULL,TO_VICT);
    act("A sickly ray of green light flys from $n's hand and strikes $N!",
	 ch,NULL,victim,TO_ROOM);
    if ( IS_NPC(victim) && victim->pIndexData != NULL
    &&   victim->pIndexData->vnum == 30225 )
    {
        act("$n staggers in the green light, but the ancient darkness refuses to let $m die!",
            victim,NULL,NULL,TO_ROOM);
        raw_kill(ch,victim);
        return;
    }
    act("$n screams and dies!",victim,NULL,NULL,TO_ROOM);
    achievement_record_event(victim, ACHIEVEMENT_EVENT_DEATH_RAY, true);
    raw_kill(ch,victim);
    return;
}

void spell_cause_madness( int sn, int level, CHAR_DATA *ch, void *vo )
{
    CHAR_DATA *victim = (CHAR_DATA *) vo;
    AFFECT_DATA af;

    if( IS_NPC(victim) )
    {
	send_to_char("You cannot cast this on NPC's.\n\r",ch);
	return;
    }

    if( IS_AFFECTED2( victim, AFF2_MADNESS ) )
    {
	if(victim == ch)
	{
	    send_to_char("You are mad enough already.\n\r",ch);
	    return;
	}
	else
	{
	    send_to_char("They are pretty mad already.\n\r",ch);
	    return;
	}
    }

	if(victim == ch)
	{
	    send_to_char("You cannot cast this spell on yourself.\n\r",ch);
	    return;
	}

	if(victim == NULL)
		return;

    af.type		= (sh_int)(sn);
    af.level		= (sh_int)(level);
    af.duration		= 10;
    af.location		= APPLY_INT;
    af.modifier		= -3;
    af.bitvector	= 0;
    af.bitvector2	= AFF2_MADNESS;
    affect_to_char(victim, &af);
    act("$n falls to the ground clutching their head in pain!",
		victim,NULL,NULL,TO_ROOM);
    act("You fall to the ground clutching your head in pain!",
		victim, NULL, NULL, TO_CHAR);
    act("$n gets up with a insane gleam in their eyes",
		victim,NULL,NULL,TO_ROOM);
    act("You get up from the ground and feel quite insane.",
		victim,NULL,NULL,TO_CHAR);
    return;
}

/*

void spell_flash( int sn, int level, CHAR_DATA *ch, void *vo )
{

}
*/
