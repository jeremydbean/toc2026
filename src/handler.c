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
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <time.h>
#include "merc.h"
#include "interp.h"
#include <stdlib.h>
#include <stdlib.h>

/* command procedures needed */
DECLARE_DO_FUN(do_return        );
DECLARE_DO_FUN(do_recall	);
DECLARE_DO_FUN(do_manipulate	);
DECLARE_DO_FUN(do_equipment);

int crash_prot = 0;

extern ROOM_INDEX_DATA *	room_index_hash		[MAX_KEY_HASH];

AFFECT_DATA *           affect_free;
ROOM_AFF_DATA *         room_aff_free;
ROOM_INDEX_DATA *       room_index_free;

/*
 * Local functions.
 */
void    affect_modify   args( ( CHAR_DATA *ch, AFFECT_DATA *paf, bool fAdd ) );
int     get_dual_sn     args( ( CHAR_DATA *ch ) );

char *	const	material_type	[]		=
{
   "adamantite", "brass", "bronze", "cloth", "copper", "food",
   "glass", "gold", "herb", "iron", "leather", "paper", "pill",
   "silver", "spell component", "steel", "stone", "vellum", "wood",
   "unknown"
};

/* return the material name */
char* material_name(int material)
{
  if (material < 0 || material >= 20)
    return "unknown";
  return material_type[material];
}

/* returns material number */
int material_lookup (const char *name)
{
  int type;

   for( type = 0; type < 20; type++)
   {
      if(!str_prefix(name, material_type[type]) )
	return type;
   }

   return 19; /* unknown */
}

/* returns race number */
int race_lookup (const char *name)
{
   int race;

   for ( race = 0; race_table[race].name != NULL; race++)
   {
	if (LOWER(name[0]) == LOWER(race_table[race].name[0])
	&&  !str_prefix( name,race_table[race].name))
	    return race;
   }

   return 0;
}

/* returns class number */
int class_lookup (const char *name)
{
   int class;

   for ( class = 0; class < MAX_CLASS; class++)
   {
	if (LOWER(name[0]) == LOWER(class_table[class].name[0])
	&&  !str_prefix( name,class_table[class].name))
	    return class;
   }

   return -1;
}

/* returns guild number */
int guild_lookup (const char *name)
{
   if (!str_prefix( name, "mage"    ))  return GUILD_MAGE;
   if (!str_prefix( name, "cleric"  ))  return GUILD_CLERIC;
   if (!str_prefix( name, "warrior" ))  return GUILD_WARRIOR;
   if (!str_prefix( name, "thief"   ))  return GUILD_THIEF;
   if (!str_prefix( name, "none"    ))  return GUILD_NONE;
   if (!str_prefix( name, "any"     ))  return GUILD_ANY;

   return -1;
}
/* returns string of guild name */
char* get_guildname(int guild)
{
    if (guild == GUILD_NONE)    return "none";
    if (guild == GUILD_ANY)     return "any";
    if (guild == GUILD_MAGE)    return "mage";
    if (guild == GUILD_CLERIC)  return "cleric";
    if (guild == GUILD_WARRIOR) return "warrior";
    if (guild == GUILD_THIEF)   return "thief";
    if (guild == GUILD_MONK)    return "monk";
    if (guild == GUILD_NECRO)   return "necro";

    return NULL;
}


/* Castle name routines */
int castle_lookup (const char *name)
{
   if (!str_prefix( name, "none"	))  return CASTLE_NONE;
   if (!str_prefix( name, "Valhalla"	))  return CASTLE_VALHALLA;
   if (!str_prefix( name, "Horde"	))  return CASTLE_HORDE;
   if (!str_prefix( name, "Legion"	))  return CASTLE_LEGION;
   if (!str_prefix( name, "Forsaken"	))  return CASTLE_FORSAKEN;
   if (!str_prefix( name, "Consortium"	))  return CASTLE_CONSORTIUM;
   if (!str_prefix( name, "Outcast"	))  return CASTLE_OUTCAST;
   if (!str_prefix( name, "Rogue" 	))  return CASTLE_ROGUE;
   return -1;
}

char * get_castlename(int castle)
{
    if (castle == CASTLE_NONE)		return "none";
    if (castle == CASTLE_VALHALLA)	return "Valh";
    if (castle == CASTLE_HORDE)		return "Hord";
    if (castle == CASTLE_LEGION)	return "Legi";
    if (castle == CASTLE_FORSAKEN)	return "Fors";
    if (castle == CASTLE_CONSORTIUM)	return "Cons";
    if (castle == CASTLE_OUTCAST)	return "Outc";
    if (castle == CASTLE_ROGUE)		return "Rogu";

    return NULL;
}


/* for immunity, vulnerabiltiy, and resistant
   the 'globals' (magic and weapons) may be overriden
   three other cases -- wood, silver, and iron -- are checked in fight.c */

int check_immune(CHAR_DATA *ch, int dam_type)
{
    int immune;
    int bit;

    immune = IS_NORMAL;

    if (dam_type == DAM_NONE)
	return immune;

    if (dam_type <= 3)
    {
	if (IS_SET(ch->imm_flags,IMM_WEAPON))
	    immune = IS_IMMUNE;
	else if (IS_SET(ch->res_flags,RES_WEAPON))
	    immune = IS_RESISTANT;
	else if (IS_SET(ch->vuln_flags,VULN_WEAPON))
	    immune = IS_VULNERABLE;
    }
    else /* magical attack */
    {
	if (IS_SET(ch->imm_flags,IMM_MAGIC))
	    immune = IS_IMMUNE;
	else if (IS_SET(ch->res_flags,RES_MAGIC))
	    immune = IS_RESISTANT;
	else if (IS_SET(ch->vuln_flags,VULN_MAGIC))
	    immune = IS_VULNERABLE;
    }

    /* set bits to check -- VULN etc. must ALL be the same or this will fail */
    switch (dam_type)
    {
	case(DAM_BASH):         bit = IMM_BASH;         break;
	case(DAM_PIERCE):       bit = IMM_PIERCE;       break;
	case(DAM_SLASH):        bit = IMM_SLASH;        break;
	case(DAM_FIRE):         bit = IMM_FIRE;         break;
	case(DAM_COLD):         bit = IMM_COLD;         break;
	case(DAM_LIGHTNING):    bit = IMM_LIGHTNING;    break;
	case(DAM_ACID):         bit = IMM_ACID;         break;
	case(DAM_POISON):       bit = IMM_POISON;       break;
	case(DAM_NEGATIVE):     bit = IMM_NEGATIVE;     break;
	case(DAM_HOLY):         bit = IMM_HOLY;         break;
	case(DAM_ENERGY):       bit = IMM_ENERGY;       break;
	case(DAM_MENTAL):       bit = IMM_MENTAL;       break;
	case(DAM_DISEASE):      bit = IMM_DISEASE;      break;
	case(DAM_DROWNING):     bit = IMM_DROWNING;     break;
	case(DAM_LIGHT):        bit = IMM_LIGHT;        break;
	case(DAM_WIND):         bit = IMM_WIND;         break;
	default:                return immune;
    }

    if (IS_SET(ch->imm_flags,bit))
	immune = IS_IMMUNE;
    else if (IS_SET(ch->res_flags,bit))
	immune = IS_RESISTANT;
    else if (IS_SET(ch->vuln_flags,bit))
	immune = IS_VULNERABLE;

    return immune;
}


/* checks mob format */
bool is_old_mob(CHAR_DATA *ch)
{
    if (ch->pIndexData == NULL)
	return false;
    else if (ch->pIndexData->new_format)
	return false;
    return true;
}

/* for returning skill information */
int get_skill(const CHAR_DATA *ch, int sn)
{
    int skill;

    if (sn == -1) /* shorthand for level based skills */
    {
	skill = ch->level * 5 / 2;
    }

    else if (sn < -1 || sn > MAX_SKILL)
    {
	bug("Bad sn %d in get_skill.",sn);
	skill = 0;
    }

    else if (!IS_NPC(ch))
    {
	if (ch->level < skill_table[sn].skill_level[ch->class])
	    skill = 0;
	else
	    skill = ch->pcdata->learned[sn];
    }

    else /* mobiles */
    {

	if (sn == gsn_sneak)
	    skill = ch->level * 2 + 20;

	if (sn == gsn_stealth)
	    skill = ch->level * 2 + 10;

	if (sn == gsn_second_attack
	&& (IS_SET(ch->act,ACT_WARRIOR) || IS_SET(ch->act,ACT_THIEF)))
	    skill = 10 + 3 * ch->level;

	else if (sn == gsn_third_attack && IS_SET(ch->act,ACT_WARRIOR))
	    skill = 4 * ch->level - 40;

	else if (sn == gsn_hand_to_hand)
	    skill = 40 + 2 * ch->level;

	else if (sn == gsn_trip && IS_SET(ch->off_flags,OFF_TRIP))
	    skill = 10 + 3 * ch->level;

	else if (sn == gsn_bash && IS_SET(ch->off_flags,OFF_BASH))
	    skill = 10 + 3 * ch->level;

	else if (sn == gsn_disarm
	     &&  (IS_SET(ch->off_flags,OFF_DISARM)
	     ||   IS_SET(ch->off_flags,ACT_WARRIOR)
	     ||   IS_SET(ch->off_flags,ACT_THIEF)))
	    skill = 20 + 3 * ch->level;

	else if (sn == gsn_berserk && IS_SET(ch->off_flags,OFF_BERSERK))
	    skill = 3 * ch->level;

	else if (sn == gsn_dual_wield)
	    skill = 20 + 3 * ch->level;

        else if ( sn == gsn_fatality)
	    skill = dice(1,ch->level/10);

	else if ( sn == gsn_destruction && ch->level > 19)
	    skill = dice(1,ch->level/10);

	else if( sn == gsn_crane_dance && ch->level > 25)
	   skill = 75;

	else if (sn == gsn_sword
	||  sn == gsn_dagger
	||  sn == gsn_spear
	||  sn == gsn_mace
	||  sn == gsn_axe
	||  sn == gsn_flail
	||  sn == gsn_whip
	||  sn == gsn_polearm
	||  sn == gsn_archery)
	    skill = 40 + 5 * ch->level / 2;

	else
	   skill = 0;
    }

    if (IS_AFFECTED(ch,AFF_BERSERK))
	skill -= ch->level / 2;

    return URANGE(0,skill,100);
}

/* for returning weapon information */
int get_weapon_sn(CHAR_DATA *ch)
{
    OBJ_DATA *wield;
    int sn;

    wield = get_eq_char( ch, WEAR_WIELD );
    if (wield == NULL || wield->item_type != ITEM_WEAPON)
	sn = gsn_hand_to_hand;
    else switch (wield->value[0])
    {
	default :               sn = -1;                break;
	case(WEAPON_SWORD):     sn = gsn_sword;         break;
	case(WEAPON_DAGGER):    sn = gsn_dagger;        break;
	case(WEAPON_SPEAR):     sn = gsn_spear;         break;
	case(WEAPON_MACE):      sn = gsn_mace;          break;
	case(WEAPON_AXE):       sn = gsn_axe;           break;
	case(WEAPON_FLAIL):     sn = gsn_flail;         break;
	case(WEAPON_WHIP):      sn = gsn_whip;          break;
	case(WEAPON_POLEARM):   sn = gsn_polearm;       break;
	case(WEAPON_BOW):       sn = gsn_archery;       break;
   }
   return sn;
}

int get_dual_sn(CHAR_DATA *ch)
{
    OBJ_DATA *wield;
    int sn;

    wield = get_eq_char( ch, WEAR_SHIELD );
    if (wield == NULL || wield->item_type != ITEM_WEAPON)

/*      return NULL;*/

/* Above line commented out because it gives a pointer error
   and replaced with the line shown below - Rico */

    return -1;

    else switch (wield->value[0])
    {
	default :               sn = -1;                break;
	case(WEAPON_SWORD):     sn = gsn_sword;         break;
	case(WEAPON_DAGGER):    sn = gsn_dagger;        break;
	case(WEAPON_SPEAR):     sn = gsn_spear;         break;
	case(WEAPON_MACE):      sn = gsn_mace;          break;
	case(WEAPON_AXE):       sn = gsn_axe;           break;
	case(WEAPON_FLAIL):     sn = gsn_flail;         break;
	case(WEAPON_WHIP):      sn = gsn_whip;          break;
	case(WEAPON_POLEARM):   sn = gsn_polearm;       break;
	case(WEAPON_BOW):       sn = gsn_archery;       break;
   }
   return sn;
}

int get_weapon_skill(CHAR_DATA *ch, int sn)
{
     int skill;

     /* -1 is exotic */
    if (IS_NPC(ch))
    {
	if (sn == -1)
	    skill = 3 * ch->level;
	else if (sn == gsn_hand_to_hand)
	    skill = 40 + 2 * ch->level;
	else
	    skill = 40 + 5 * ch->level / 2;
    }

    else
    {
	if (sn == -1)
	    skill = 3 * ch->level;
	else
	    skill = ch->pcdata->learned[sn];
    }

    return URANGE(0,skill,100);
}


/* used to de-screw characters */
void reset_char(CHAR_DATA *ch)
{
     int loc,mod,stat;
     OBJ_DATA *obj;
     AFFECT_DATA *af;
     int i;

     if (IS_NPC(ch))
	return;

    if (ch->pcdata->perm_hit == 0
    ||  ch->pcdata->perm_mana == 0
    ||  ch->pcdata->perm_move == 0
    ||  ch->pcdata->last_level == 0)
    {
    /* do a FULL reset */
	for (loc = 0; loc < MAX_WEAR; loc++)
	{
	    obj = get_eq_char(ch,loc);
	    if (obj == NULL)
		continue;
/* BB
	    if (!obj->enchanted)
*/
	    for ( af = obj->pIndexData->affected; af != NULL; af = af->next )
	    {
		mod = af->modifier;
		switch(af->location)
		{
		    case APPLY_SEX:     ch->sex         -= mod;
					if (ch->sex < 0 || ch->sex >2)
					    ch->sex = IS_NPC(ch) ?
						0 :
						ch->pcdata->true_sex;
									break;
		    case APPLY_MANA:    ch->max_mana    -= mod;         break;
		    case APPLY_HIT:     ch->max_hit     -= mod;         break;
		    case APPLY_MOVE:    ch->max_move    -= mod;         break;
		}
	    }

	    for ( af = obj->affected; af != NULL; af = af->next )
	    {
		mod = af->modifier;
		switch(af->location)
		{
		    case APPLY_SEX:     ch->sex         -= mod;         break;
		    case APPLY_MANA:    ch->max_mana    -= mod;         break;
		    case APPLY_HIT:     ch->max_hit     -= mod;         break;
		    case APPLY_MOVE:    ch->max_move    -= mod;         break;
		}
	    }
	}
	    for ( af = ch->affected; af != NULL; af = af->next )
	    {
		mod = af->modifier;
		switch(af->location)
		{
		    case APPLY_MANA:    ch->max_mana    -= mod;         break;
		    case APPLY_HIT:     ch->max_hit     -= mod;         break;
		    case APPLY_MOVE:    ch->max_move    -= mod;         break;
		}
	    }
	/* now reset the permanent stats */
	ch->pcdata->perm_hit    = ch->max_hit;
	ch->pcdata->perm_mana   = ch->max_mana;
	ch->pcdata->perm_move   = ch->max_move;
	if (ch->pcdata->true_sex < 0 || ch->pcdata->true_sex > 2) {
		if (ch->sex > 0 && ch->sex < 3)
		    ch->pcdata->true_sex        = ch->sex;
		else
		    ch->pcdata->true_sex        = 0;
	}
    }

    /* now restore the character to his/her true condition */
    for (stat = 0; stat < MAX_STATS; stat++)
	ch->mod_stat[stat] = 0;

    if (ch->pcdata->true_sex < 0 || ch->pcdata->true_sex > 2)
	ch->pcdata->true_sex = 0;
    ch->sex             = ch->pcdata->true_sex;
    ch->max_hit         = ch->pcdata->perm_hit;
    ch->max_mana        = ch->pcdata->perm_mana;
    ch->max_move        = ch->pcdata->perm_move;

    for (i = 0; i < 4; i++)
	ch->armor[i]    = 100;

    ch->hitroll         = 0;
    ch->damroll         = 0;
    ch->saving_throw    = 0;

    /* now start adding back the effects */
    for (loc = 0; loc < MAX_WEAR; loc++)
    {
	obj = get_eq_char(ch,loc);
	if (obj == NULL)
	    continue;
	for (i = 0; i < 4; i++)
	    ch->armor[i] -= apply_ac( obj, loc, i );
/*
	if (!obj->enchanted)
*/
	for ( af = obj->pIndexData->affected; af != NULL; af = af->next )
	{
	    mod = af->modifier;
	    switch(af->location)
	    {
		case APPLY_STR:         ch->mod_stat[STAT_STR]  += mod; break;
		case APPLY_DEX:         ch->mod_stat[STAT_DEX]  += mod; break;
		case APPLY_INT:         ch->mod_stat[STAT_INT]  += mod; break;
		case APPLY_WIS:         ch->mod_stat[STAT_WIS]  += mod; break;
		case APPLY_CON:         ch->mod_stat[STAT_CON]  += mod; break;

		case APPLY_SEX:         ch->sex                 += mod; break;
		case APPLY_MANA:        ch->max_mana            += mod; break;
		case APPLY_HIT:         ch->max_hit             += mod; break;
		case APPLY_MOVE:        ch->max_move            += mod; break;

		case APPLY_AC:
		    for (i = 0; i < 4; i ++)
			ch->armor[i] += mod;
		    break;
		case APPLY_HITROLL:     ch->hitroll             += mod; break;
		case APPLY_DAMROLL:     ch->damroll             += mod; break;

		case APPLY_SAVING_PARA:         ch->saving_throw += mod; break;
		case APPLY_SAVING_ROD:          ch->saving_throw += mod; break;
		case APPLY_SAVING_PETRI:        ch->saving_throw += mod; break;
		case APPLY_SAVING_BREATH:       ch->saving_throw += mod; break;
		case APPLY_SAVING_SPELL:        ch->saving_throw += mod; break;
	    }
	}

	for ( af = obj->affected; af != NULL; af = af->next )
	{
	    mod = af->modifier;
	    switch(af->location)
	    {
		case APPLY_STR:         ch->mod_stat[STAT_STR]  += mod; break;
		case APPLY_DEX:         ch->mod_stat[STAT_DEX]  += mod; break;
		case APPLY_INT:         ch->mod_stat[STAT_INT]  += mod; break;
		case APPLY_WIS:         ch->mod_stat[STAT_WIS]  += mod; break;
		case APPLY_CON:         ch->mod_stat[STAT_CON]  += mod; break;

		case APPLY_SEX:         ch->sex                 += mod; break;
		case APPLY_MANA:        ch->max_mana            += mod; break;
		case APPLY_HIT:         ch->max_hit             += mod; break;
		case APPLY_MOVE:        ch->max_move            += mod; break;

		case APPLY_AC:
		    for (i = 0; i < 4; i ++)
			ch->armor[i] += mod;
		    break;
		case APPLY_HITROLL:     ch->hitroll             += mod; break;
		case APPLY_DAMROLL:     ch->damroll             += mod; break;

		case APPLY_SAVING_PARA:         ch->saving_throw += mod; break;
		case APPLY_SAVING_ROD:          ch->saving_throw += mod; break;
		case APPLY_SAVING_PETRI:        ch->saving_throw += mod; break;
		case APPLY_SAVING_BREATH:       ch->saving_throw += mod; break;
		case APPLY_SAVING_SPELL:        ch->saving_throw += mod; break;
	    }
	}
    }

    /* now add back spell effects */
    for (af = ch->affected; af != NULL; af = af->next)
    {
	mod = af->modifier;
	switch(af->location)
	{
		case APPLY_STR:         ch->mod_stat[STAT_STR]  += mod; break;
		case APPLY_DEX:         ch->mod_stat[STAT_DEX]  += mod; break;
		case APPLY_INT:         ch->mod_stat[STAT_INT]  += mod; break;
		case APPLY_WIS:         ch->mod_stat[STAT_WIS]  += mod; break;
		case APPLY_CON:         ch->mod_stat[STAT_CON]  += mod; break;

		case APPLY_SEX:         ch->sex                 += mod; break;
		case APPLY_MANA:        ch->max_mana            += mod; break;
		case APPLY_HIT:         ch->max_hit             += mod; break;
		case APPLY_MOVE:        ch->max_move            += mod; break;

		case APPLY_AC:
		    for (i = 0; i < 4; i ++)
			ch->armor[i] += mod;
		    break;
		case APPLY_HITROLL:     ch->hitroll             += mod; break;
		case APPLY_DAMROLL:     ch->damroll             += mod; break;

		case APPLY_SAVING_PARA:         ch->saving_throw += mod; break;
		case APPLY_SAVING_ROD:          ch->saving_throw += mod; break;
		case APPLY_SAVING_PETRI:        ch->saving_throw += mod; break;
		case APPLY_SAVING_BREATH:       ch->saving_throw += mod; break;
		case APPLY_SAVING_SPELL:        ch->saving_throw += mod; break;
	}
    }

    /* make sure sex is RIGHT!!!! */
    if (ch->sex < 0 || ch->sex > 2)
	ch->sex = ch->pcdata->true_sex;
}


/*
 * Retrieve a character's trusted level for permission checking.
 */
int get_trust( CHAR_DATA *ch )
{
    if ( ch->desc != NULL && ch->desc->original != NULL )
	ch = ch->desc->original;

    if ( ch->trust != 0 )
	return ch->trust;

    if ( IS_NPC(ch) && ch->level >= LEVEL_HERO )
	return LEVEL_HERO - 1;
    else
	return ch->level;
}


/*
 * Retrieve a character's age.
 */
int get_age( CHAR_DATA *ch )
{
    return 17 + ( ch->played + (int) (current_time - ch->logon) ) / 72000;
}

/* command for retrieving stats */
int get_curr_stat( CHAR_DATA *ch, int stat )
{
    int max;

    if (IS_NPC(ch) || ch->level > LEVEL_IMMORTAL)
	max = MAX_STAT;

    else
    {
	max = pc_race_table[ch->race].max_stats[stat] + 4;

	if (class_table[ch->class].attr_prime == stat)
	    max += 2;

	if ( ch->race == race_lookup("human"))
	    max += 1;

	max = UMIN(max,MAX_STAT);
    }

    return URANGE(3,ch->perm_stat[stat] + ch->mod_stat[stat], max);
}

/* command for returning max training score */
int get_max_train( CHAR_DATA *ch, int stat )
{
    int max;

    if (IS_NPC(ch) || ch->level > LEVEL_IMMORTAL)
	return MAX_STAT;

    max = pc_race_table[ch->race].max_stats[stat];
    if (class_table[ch->class].attr_prime == stat) {
	if (ch->race == race_lookup("human"))
	   max += 3;
	else
	   max += 2;
    }

    return UMIN(max,MAX_STAT);
}

int can_carry_n( CHAR_DATA *ch )
{
    if ( !IS_NPC(ch) && ch->level >= LEVEL_IMMORTAL )
	return 1000;

   if (ch->pcdata->num_remorts >= 5)
  return 1000;

    if(IS_SET(ch->act2,ACT2_LYCANTH) )
       return ch->were_shape.can_carry;

    if ( IS_NPC(ch) && IS_SET(ch->act, ACT_PET) )
	return 0;

    return MAX_WEAR +  2 * get_curr_stat(ch,STAT_DEX) + ch->level;
}

int can_carry_w( CHAR_DATA *ch )
{
    if ( !IS_NPC(ch) && ch->level >= LEVEL_IMMORTAL )
	return 1000000;

   if (ch->pcdata->num_remorts >= 5)
	return 1000000;

    if(IS_SET(ch->act2,ACT2_LYCANTH) )
      return str_app[get_curr_stat(ch,STAT_STR)].carry + ch->level  * 5 / 2;

    if ( IS_NPC(ch) && IS_SET(ch->act, ACT_PET) )
	return 0;

    return str_app[get_curr_stat(ch,STAT_STR)].carry + ch->level  * 5 / 2;
}



/*
 * See if a string is one of the names of an object.
 */
/*
bool is_name( const char *str, char *namelist )
{
    char name[MAX_INPUT_LENGTH];

    for ( ; ; )
    {
	namelist = one_argument( namelist, name );
	if ( name[0] == '\0' )
	    return false;
	if ( !str_prefix( str, name ) )
	    return true;
    }
}
*/

bool is_name ( const char *str, const char *namelist )
{
    char name[MAX_INPUT_LENGTH], part[MAX_INPUT_LENGTH];
    char list[MAX_STRING_LENGTH];
    char string[MAX_STRING_LENGTH];
    char *list_ptr, *string_ptr;

    strncpy( string, str, sizeof(string) - 1 );
    string[sizeof(string) - 1] = '\0';
    strncpy( list, namelist, sizeof(list) - 1 );
    list[sizeof(list) - 1] = '\0';

    string_ptr = string;
    /* we need ALL parts of string to match part of namelist */
    for ( ; ; )  /* start parsing string */
    {
        string_ptr = one_argument(string_ptr,part);

        if (part[0] == '\0' )
            return true;

	/* check to see if this is part of namelist */
        list_ptr = list;
        for ( ; ; )  /* start parsing namelist */
        {
            list_ptr = one_argument(list_ptr,name);
            if (name[0] == '\0')  /* this name was not found */
                return false;

            if (!str_cmp(string,name))
                return true; /* full pattern match */

            if (!str_prefix(part,name))
                break;
        }
    }
}

/* where abbrs don't work */
bool is_full_name ( char *str, char *namelist )
{
    char name[MAX_INPUT_LENGTH], part[MAX_INPUT_LENGTH];
    char *list, *string;


    string = str;
    /* we need ALL parts of string to match part of namelist */
    for ( ; ; )  /* start parsing string */
    {
	str = one_argument(str,part);

	if (part[0] == '\0' )
	    return true;

	/* check to see if this is part of namelist */
	list = namelist;
	for ( ; ; )  /* start parsing namelist */
	{
	    list = one_argument(list,name);
	    if (name[0] == '\0')  /* this name was not found */
		return false;

	    if (!str_cmp(string,name))
		return true; /* full pattern match */

	    if (!str_cmp(part,name))
		break;
	}
    }
}




/*
 * Apply or remove an affect to a character.
 */
void affect_modify( CHAR_DATA *ch, AFFECT_DATA *paf, bool fAdd )
{
    OBJ_DATA *wield;
    int mod,i;

    mod = paf->modifier;

    if ( fAdd )
    {
	if(paf->bitvector != 0)
	  SET_BIT( ch->affected_by, paf->bitvector );
	else
	  SET_BIT( ch->affected_by2, paf->bitvector2 );
    }
    else
    {
	if(paf->bitvector != 0)
	  REMOVE_BIT( ch->affected_by, paf->bitvector );
	else
	  REMOVE_BIT( ch->affected_by2, paf->bitvector2 );
	mod = 0 - mod;
    }

    switch ( paf->location )
    {
    default:
	bug( "Affect_modify: unknown location %d.", paf->location );
	return;

    case APPLY_NONE:                                            break;
    case APPLY_STR:           ch->mod_stat[STAT_STR]    += mod; break;
    case APPLY_DEX:           ch->mod_stat[STAT_DEX]    += mod; break;
    case APPLY_INT:           ch->mod_stat[STAT_INT]    += mod; break;
    case APPLY_WIS:           ch->mod_stat[STAT_WIS]    += mod; break;
    case APPLY_CON:           ch->mod_stat[STAT_CON]    += mod; break;
    case APPLY_SEX:           ch->sex                   += mod; break;
    case APPLY_CLASS:                                           break;
    case APPLY_LEVEL:                                           break;
    case APPLY_AGE:                                             break;
    case APPLY_HEIGHT:                                          break;
    case APPLY_WEIGHT:                                          break;
    case APPLY_MANA:          ch->max_mana              += mod; break;
    case APPLY_HIT:           ch->max_hit               += mod; break;
    case APPLY_MOVE:          ch->max_move              += mod; break;
    case APPLY_GOLD:                                            break;
    case APPLY_EXP:                                             break;
    case APPLY_AC:
	for (i = 0; i < 4; i ++)
	    ch->armor[i] += mod;
	break;
    case APPLY_HITROLL:       ch->hitroll               += mod; break;
    case APPLY_DAMROLL:       ch->damroll               += mod; break;
    case APPLY_SAVING_PARA:   ch->saving_throw          += mod; break;
    case APPLY_SAVING_ROD:    ch->saving_throw          += mod; break;
    case APPLY_SAVING_PETRI:  ch->saving_throw          += mod; break;
    case APPLY_SAVING_BREATH: ch->saving_throw          += mod; break;
    case APPLY_SAVING_SPELL:  ch->saving_throw          += mod; break;
    }

    /*
     * Check for weapon wielding.
     * Guard against recursion (for weapons with affects).
     */
    if (get_curr_stat(ch,STAT_STR) < 6)
    {
    if ( !IS_NPC(ch) && ( wield = get_eq_char( ch, WEAR_WIELD ) ) != NULL
    &&   get_obj_weight(wield) > str_app[get_curr_stat(ch,STAT_STR)].wield )
    {
	static int depth;

	if ( depth == 0 )
	{
	    depth++;
	    act( "You drop $p.", ch, wield, NULL, TO_CHAR );
	    act( "$n drops $p.", ch, wield, NULL, TO_ROOM );
	    obj_from_char( wield );
	    obj_to_room( wield, ch->in_room );
            log_string("Low strength drop of weapon.");
	    depth--;
	}
    }
    }
    return;
}



/*
 * Give an affect to a char.
 */
void affect_to_char( CHAR_DATA *ch, AFFECT_DATA *paf )
{
    AFFECT_DATA *paf_new;
    char buf[1000];

/* Blackbird
    if ( affect_free == NULL )
    {
	paf_new         = alloc_perm( sizeof(*paf_new) );
    }
    else
    {
	paf_new         = affect_free;
	affect_free     = affect_free->next;
    }
*/

    paf_new             = new_affect();
    paf_new->location       =  paf->location;
    paf_new->modifier       =  paf->modifier;
    paf_new->type           =  paf->type;
    paf_new->duration       =  paf->duration;
    paf_new->bitvector      =  paf->bitvector;
    paf_new->bitvector2     =  paf->bitvector2;
    if ((paf_new->bitvector != 0) && (paf_new->bitvector2 != 0)) {
      snprintf(buf, sizeof(buf), "Trying to add: %s AND %s as bitvectors to %s\n\r",
               affect_bit_name(paf_new->bitvector),
               affect_bit_name(paf_new->bitvector2),
               ch->name);
      log_string(buf);
      send_to_char("Something went wrong, it got logged, report to wiz\n\r",ch);
      send_to_char("So we know we have to debug.\n\r",ch);
      return;
    }
    paf_new->next       = ch->affected;
    ch->affected        = paf_new;

    affect_modify( ch, paf_new, true );
    return;
}

/* give an affect to an object */
void affect_to_obj(OBJ_DATA *obj, AFFECT_DATA *paf)
{
    AFFECT_DATA *paf_new;
    char buf[1000];

/*
    if (affect_free == NULL)
	paf_new = alloc_perm(sizeof(*paf_new));
    else
    {
	paf_new         = affect_free;
	affect_free     = affect_free->next;
    }

    *paf_new            = *paf;
*/

    paf_new             = new_affect();
    paf_new->location       =  paf->location;
    paf_new->modifier       =  paf->modifier;
    paf_new->type           =  paf->type;
    paf_new->duration       =  paf->duration;
    paf_new->bitvector      =  paf->bitvector;
    paf_new->bitvector2     =  paf->bitvector2;
    if ((paf_new->bitvector != 0) && (paf_new->bitvector2 != 0)) {
      snprintf(buf, sizeof(buf), "Trying to add: %s AND %s as bitvectors to object %s\n\r",
               affect_bit_name(paf_new->bitvector),
               affect_bit_name(paf_new->bitvector2),
               obj->name);
      log_string(buf);
      return;
    }
    paf_new->next       = obj->affected;
    obj->affected       = paf_new;

    return;

}



/*
 * Remove an affect from a char.
 */
void affect_remove( CHAR_DATA *ch, AFFECT_DATA *paf )
{
    if ( ch->affected == NULL )
    {

        crash_prot++;

	bug( "Affect_remove: no affect.", 0 );
        if (crash_prot > 10)
        {
        bug( "Affect remove failed 10 times.  Crashing...",0);
        exit(1);
        }
	return;
    }


    affect_modify( ch, paf, false );

    crash_prot = 0;

    if ( paf == ch->affected )
    {
	ch->affected    = paf->next;
    }
    else
    {
	AFFECT_DATA *prev;

	for ( prev = ch->affected; prev != NULL; prev = prev->next )
	{
	    if ( prev->next == paf )
	    {
		prev->next = paf->next;
		break;
	    }
	}

	if ( prev == NULL )
	{
	    bug( "Affect_remove: cannot find paf.", 0 );
	    return;
	}
    }
    free_affect(paf);
    return;

/* Blackbird
    paf->next   = affect_free;
    affect_free = paf->next;
    affect_free = paf;
    return;
*/
}

void affect_remove_obj( OBJ_DATA *obj, AFFECT_DATA *paf)
{
    if ( obj->affected == NULL )
    {
	bug( "Affect_remove_object: no affect.", 0 );
	return;
    }

    if (obj->carried_by != NULL && obj->wear_loc != -1)
	affect_modify( obj->carried_by, paf, false );

    if ( paf == obj->affected )
    {
	obj->affected    = paf->next;
    }
    else
    {
	AFFECT_DATA *prev;

	for ( prev = obj->affected; prev != NULL; prev = prev->next )
	{
	    if ( prev->next == paf )
	    {
		prev->next = paf->next;
		break;
	    }
	}

	if ( prev == NULL )
	{
	    bug( "Affect_remove_object: cannot find paf.", 0 );
	    return;
	}
    }
    free_affect(paf);
    return;

/* Blackbird
    paf->next   = affect_free;
    affect_free = paf->next;
    affect_free = paf;
    return;
*/
}



/*
 * Strip all affects of a given sn.
 */
void affect_strip( CHAR_DATA *ch, int sn )
{
    AFFECT_DATA *paf;
    AFFECT_DATA *paf_next;

    for ( paf = ch->affected; paf != NULL; paf = paf_next )
    {
	paf_next = paf->next;
	if ( paf->type == sn )
	    affect_remove( ch, paf );
    }

    return;
}



/*
 * Return true if a char is affected by a spell.
 */
bool is_affected( CHAR_DATA *ch, int sn )
{
    AFFECT_DATA *paf;

    for ( paf = ch->affected; paf != NULL; paf = paf->next )
    {
	if ( paf->type == sn )
	    return true;
    }

    return false;
}



/*
 * Add or enhance an affect.
 */
void affect_join( CHAR_DATA *ch, AFFECT_DATA *paf )
{
    AFFECT_DATA *paf_old;
bool found __attribute__((unused));

    found = false;
    for ( paf_old = ch->affected; paf_old != NULL; paf_old = paf_old->next )
    {
	if ( paf_old->type == paf->type )
	{
	    paf->level += paf_old->level; paf->level = paf->level / 2;
	    paf->duration += paf_old->duration;
	    paf->modifier += paf_old->modifier;
	    affect_remove( ch, paf_old );
	    break;
	}
    }

    affect_to_char( ch, paf );
    return;
}

/*
 * Put a mob in an object!
 */
void char_to_obj( CHAR_DATA *ch, OBJ_DATA *obj)
{

   if(ch->in_room != NULL)
      char_from_room(ch);
   ch->in_object = obj;
   obj->trapped = ch;

}

/*
 * Ok, let the poor guy out.
 */
void char_from_obj( OBJ_DATA *obj )
{

   if(obj->in_room != NULL)
     char_to_room(obj->trapped,obj->in_room);
   else if(obj->carried_by && obj->carried_by->in_room)
     char_to_room(obj->trapped,obj->carried_by->in_room);
   else if(obj->in_obj && obj->in_obj->in_room)
     char_to_room(obj->trapped,obj->in_obj->in_room);
   else if(obj->in_obj && obj->in_obj->carried_by &&
	   obj->in_obj->carried_by->in_room)
     char_to_room(obj->trapped,obj->in_obj->carried_by->in_room);
    else
    {
	bug( "Char_from_obj: NULL.", 0 );
	return;
    }

    obj->trapped->in_object = NULL;
    obj->trapped = NULL;

    return;
}
/*
 * Move a char out of a room.
 */
void char_from_room( CHAR_DATA *ch )
{
    OBJ_DATA *obj;

    if ( ch->in_room == NULL )
    {
	bug( "Char_from_room: NULL.", 0 );
	return;
    }

    if ( !IS_NPC(ch) )
	--ch->in_room->area->nplayer;

    if ( ( obj = get_eq_char( ch, WEAR_LIGHT ) ) != NULL
    &&   obj->item_type == ITEM_LIGHT
    &&   obj->value[2] != 0
    &&   ch->in_room->light > 0 )
	--ch->in_room->light;

    if ( ch == ch->in_room->people )
    {
	ch->in_room->people = ch->next_in_room;
    }
    else
    {
	CHAR_DATA *prev;

	for ( prev = ch->in_room->people; prev; prev = prev->next_in_room )
	{
	    if ( prev->next_in_room == ch )
	    {
		prev->next_in_room = ch->next_in_room;
		break;
	    }
	}

	if ( prev == NULL )
	    bug( "Char_from_room: ch not found.", 0 );
    }

    ch->in_room      = NULL;
    ch->next_in_room = NULL;
    return;
}



/*
 * Move a char into a room.
 */
void char_to_room( CHAR_DATA *ch, ROOM_INDEX_DATA *pRoomIndex )
{
    OBJ_DATA *obj;

    if ( pRoomIndex == NULL )
    {
	bug( "Char_to_room: NULL.", 0 );
	return;
    }

    ch->in_room         = pRoomIndex;
    ch->next_in_room    = pRoomIndex->people;
    pRoomIndex->people  = ch;

    if ( !IS_NPC(ch) )
    {
	if (ch->in_room->area->empty)
	{
	    ch->in_room->area->empty = false;
	    ch->in_room->area->age = 0;
	}
	++ch->in_room->area->nplayer;
    }

    if ( ( obj = get_eq_char( ch, WEAR_LIGHT ) ) != NULL
    &&   obj->item_type == ITEM_LIGHT
    &&   obj->value[2] != 0 )
	++ch->in_room->light;

    if (IS_AFFECTED(ch,AFF_PLAGUE))
    {
	AFFECT_DATA *af, plague;
	CHAR_DATA *vch;
	int save;

	for ( af = ch->affected; af != NULL; af = af->next )
	{
	    if (af->type == gsn_plague)
		break;
	}

	if (af == NULL)
	{
	    REMOVE_BIT(ch->affected_by,AFF_PLAGUE);
	    return;
	}

	if (af->level == 1)
	    return;

	plague.type             = gsn_plague;
	plague.level            = af->level - 1;
	plague.duration         = number_range(1,2 * plague.level);
	plague.location         = APPLY_STR;
	plague.modifier         = -5;
	plague.bitvector        = AFF_PLAGUE;
	plague.bitvector2       = 0;

	for ( vch = ch->in_room->people; vch != NULL; vch = vch->next_in_room)
	{
	    switch(check_immune(vch,DAM_DISEASE))
	    {
		case(IS_NORMAL)         : save = af->level - 4; break;
		case(IS_IMMUNE)         : save = 0;             break;
		case(IS_RESISTANT)      : save = af->level - 8; break;
		case(IS_VULNERABLE)     : save = af->level;     break;
		default                 : save = af->level - 4; break;
	    }

	    if (save != 0 && !saves_spell(save,vch) && !IS_IMMORTAL(vch) &&
		!IS_AFFECTED(vch,AFF_PLAGUE) && number_bits(6) == 0)
	    {
		send_to_char("You feel hot and feverish.\n\r",vch);
		act("$n shivers and looks very ill.",vch,NULL,NULL,TO_ROOM);
		affect_join(vch,&plague);
	    }
	}
    }

    return;
}



/*
 * Give an obj to a char.
 */
void obj_to_char( OBJ_DATA *obj, CHAR_DATA *ch )
{
    OBJ_DATA *obj1;

    obj->next_content    = ch->carrying;
    ch->carrying         = obj;
    obj->carried_by      = ch;
    obj->in_room         = NULL;
    obj->in_obj          = NULL;
    ch->carry_number    += get_obj_number( obj );
    ch->carry_weight    += get_obj_weight( obj );
/* Blackbird:  update maxloadfile in case of player */
    if (!IS_NPC(ch)) {
       if ((obj->pIndexData != NULL) &&
           (get_maxload_index(obj->pIndexData->vnum) != NULL)) {
              add_maxload_index( obj->pIndexData->vnum, +1, 0);
       }
       for (obj1 = obj->contains;
            obj1 != NULL;
            obj1 = obj1 -> next_content)
       { if ((obj1->pIndexData != NULL) &&
            (get_maxload_index(obj1->pIndexData->vnum) != NULL))
         {  add_maxload_index( obj1->pIndexData->vnum, +1, 0);
         }
       }
    }

}



/*
 * Take an obj from its character.
 */
void obj_from_char( OBJ_DATA *obj )
{
    CHAR_DATA *ch;
    OBJ_DATA *obj1;


    if ( ( ch = obj->carried_by ) == NULL )
    {
	bug( "Obj_from_char: null ch.", 0 );
	return;
    }

    if ( obj->wear_loc != WEAR_NONE )
	unequip_char( ch, obj );

    if ( ch->carrying == obj )
    {
	ch->carrying = obj->next_content;
    }
    else
    {
	OBJ_DATA *prev;

	for ( prev = ch->carrying; prev != NULL; prev = prev->next_content )
	{
	    if ( prev->next_content == obj )
	    {
		prev->next_content = obj->next_content;
		break;
	    }
	}

	if ( prev == NULL )
	    bug( "Obj_from_char: obj not in list.", 0 );
    }

    obj->carried_by      = NULL;
    obj->next_content    = NULL;
    ch->carry_number    -= get_obj_number( obj );
    ch->carry_weight    -= get_obj_weight( obj );
/* Update max_load_file (Blackbird) */
    if (!IS_NPC(ch)) {
       if ((obj->pIndexData != NULL) &&
           (get_maxload_index(obj->pIndexData->vnum) != NULL)) {
              add_maxload_index( obj->pIndexData->vnum, -1, 0);
       }
       for (obj1 = obj->contains;
            obj1 != NULL;
            obj1 = obj1 -> next_content)
       { if ((obj1->pIndexData != NULL) &&
            (get_maxload_index(obj1->pIndexData->vnum) != NULL))
         {  add_maxload_index( obj1->pIndexData->vnum, -1, 0);
         }
       }
    }
    return;
}



/*
 * Find the ac value of an obj, including position effect.
 */
int apply_ac( OBJ_DATA *obj, int iWear, int type )
{
    if ( obj->item_type != ITEM_ARMOR )
	return 0;

    switch ( iWear )
    {
    case WEAR_BODY:     return 3 * obj->value[type];
    case WEAR_HEAD:     return 2 * obj->value[type];
    case WEAR_LEGS:     return 2 * obj->value[type];
    case WEAR_FEET:     return     obj->value[type];
    case WEAR_HANDS:    return     obj->value[type];
    case WEAR_ARMS:     return     obj->value[type];
    case WEAR_SHIELD:   return     obj->value[type];
    case WEAR_FINGER_L: return     obj->value[type];
    case WEAR_FINGER_R: return     obj->value[type];
    case WEAR_NECK_1:   return     obj->value[type];
    case WEAR_NECK_2:   return     obj->value[type];
    case WEAR_ABOUT:    return 2 * obj->value[type];
    case WEAR_WAIST:    return     obj->value[type];
    case WEAR_WRIST_L:  return     obj->value[type];
    case WEAR_WRIST_R:  return     obj->value[type];
    case WEAR_HOLD:     return     obj->value[type];
    }

    return 0;
}



/*
 * Find a piece of eq on a character.
 */
OBJ_DATA *get_eq_char( CHAR_DATA *ch, int iWear )
{
    OBJ_DATA *obj;

    if (ch == NULL)
	return NULL;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( obj->wear_loc == iWear )
	    return obj;
    }

    return NULL;
}

/* Check and do the obj_actions... -Graves */
static void do_obj_action(CHAR_DATA *ch, OBJ_DATA *obj)
{
    OBJ_ACTION_DATA *action;

    action = obj->pIndexData->action;

    if ( obj->action_to_room != NULL && obj->action_to_char != NULL)
    {
        act(obj->action_to_room,ch,obj,NULL,TO_ROOM);
        act(obj->action_to_char,ch,obj,NULL,TO_CHAR);
        return;
    }

    while( action != NULL )
    {
	act( action->not_vict_action,ch,obj,NULL,TO_ROOM );
	act( action->vict_action,ch,obj,NULL,TO_CHAR);
	return;
    }

    action = action->next;
}

/*
 * Equip a char with an obj.
 */
void equip_char( CHAR_DATA *ch, OBJ_DATA *obj, int iWear )
{
    AFFECT_DATA *paf;
    OBJ_DATA *shield;
    int i;


    if ( get_eq_char( ch, iWear ) != NULL )
    {
	bug( "Equip_char: already equipped (%d).", iWear );
	return;
    }

    if ( ( IS_OBJ_STAT(obj, ITEM_ANTI_EVIL)    && IS_EVIL(ch)    )
    ||   ( IS_OBJ_STAT(obj, ITEM_ANTI_GOOD)    && IS_GOOD(ch)    )
    ||   ( IS_OBJ_STAT(obj, ITEM_ANTI_NEUTRAL) && IS_NEUTRAL(ch) ) )
    {
	/*
	 * Thanks to Morgenes for the bug fix here!
	 */
	act( "You are zapped by $p and drop it.", ch, obj, NULL, TO_CHAR );
	act( "$n is zapped by $p and drops it.",  ch, obj, NULL, TO_ROOM );
	obj_from_char( obj );
	obj_to_room( obj, ch->in_room );
	return;
    }

    shield = get_eq_char(ch,WEAR_SHIELD);
    if( IS_WEAPON_STAT(obj,WEAPON_TWO_HANDS)
    && shield != NULL )
    {
	send_to_char("You remove your shield to handle the massive weapon.\n\r",ch);
	unequip_char(ch,shield);
    }

    for (i = 0; i < 4; i++)
	ch->armor[i]            -= apply_ac( obj, iWear,i );
    obj->wear_loc        = iWear;
/* BB
    if (!obj->enchanted)
*/
    for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
        affect_modify( ch, paf, true );
    for ( paf = obj->affected; paf != NULL; paf = paf->next )
	affect_modify( ch, paf, true );

    if( IS_SET(obj->extra_flags, ITEM_ADD_AFFECT) )
    {
       if(obj->timer == 0 )
	  obj->timer = 1000;

       if(IS_SET(obj->extra_flags2, ITEM2_ADD_INVIS) )
       {
	  if(!IS_SET(ch->affected_by, AFF_INVISIBLE) )
	  {
            send_to_char("You slowly fade out of existence.\n\r",ch);
            SET_BIT(ch->affected_by, AFF_INVISIBLE);
            act("$n fades out of existence.",ch,NULL,NULL,TO_ROOM);
          }
       }

       if(IS_SET(obj->extra_flags2, ITEM2_ADD_DETECT_INVIS) )
       {
	  if(!IS_SET(ch->affected_by, AFF_DETECT_INVIS) )
	  {
	    send_to_char("Your eyes begin to tingle.\n\r",ch);
	    SET_BIT(ch->affected_by, AFF_DETECT_INVIS);
	    act("$n's eyes begin to glow.",ch,NULL,NULL,TO_ROOM);
	  }
       }

       if(IS_SET(obj->extra_flags2, ITEM2_ADD_FLY) )
       {
	  if(!IS_SET(ch->affected_by, AFF_FLYING) )
	  {
	    send_to_char("You rise up into the air.\n\r",ch);
	    SET_BIT(ch->affected_by, AFF_FLYING);
	    act("$n's rises up into the air.",ch,NULL,NULL,TO_ROOM);
	  }
       }
    }
    if(obj->item_type == ITEM_ACTION)
    {
	if(obj->timer == 0)
		obj->timer = 1000;

	switch(obj->value[0])
	{
	    case 1:
		do_recall(ch,"");
		extract_obj(obj);
		break;
	    case 2:
		raw_kill(ch,ch);
		extract_obj(obj);
		break;
	    case 3:
		if(obj->value[2] != 0 && !IS_NPC(ch))
		{
		    AFFECT_DATA af;

		    act("$n turns an ugly shade of green.",ch,0,0,TO_ROOM);
		    send_to_char("You feel really bad!\n\r",ch);

		    af.type		= gsn_poison;
		    af.level		= number_fuzzy(obj->value[2]);
		    af.duration		= 3 * obj->value[2];
		    af.location		= APPLY_NONE;
		    af.modifier		= 0;
		    af.bitvector	= AFF_POISON;
		    af.bitvector2	= 0;
		    affect_join(ch,&af);
		    extract_obj(obj);
		}
		break;
	}
    }

    if (obj->action_to_room == NULL && obj->action_to_char == NULL)
    {
    if( obj->pIndexData->action != NULL )
        do_obj_action(ch,obj);
    }
    else
    do_obj_action(ch,obj);

    if ( obj->item_type == ITEM_LIGHT
    &&   obj->value[2] != 0
    &&   ch->in_room != NULL )
	++ch->in_room->light;

    return;
}



/*
 * Unequip a char with an obj.
 */
void unequip_char( CHAR_DATA *ch, OBJ_DATA *obj )
{
    AFFECT_DATA *paf;
    int i;

    if ( obj->wear_loc == WEAR_NONE )
    {
	bug( "Unequip_char: already unequipped.", 0 );
	return;
    }

    for (i = 0; i < 4; i++)
	ch->armor[i]    += apply_ac( obj, obj->wear_loc,i );
    obj->wear_loc        = -1;
/* BB
    if (!obj->enchanted)
*/  for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
	    affect_modify( ch, paf, false );
    for ( paf = obj->affected; paf != NULL; paf = paf->next )
	affect_modify( ch, paf, false );

    if( IS_SET(obj->extra_flags, ITEM_ADD_AFFECT) )
    {
       if(IS_SET(obj->extra_flags2, ITEM2_ADD_INVIS) )
       {
	  if(!is_affected(ch,skill_lookup("invis") ) )
	  {
            send_to_char("You slowly fade into existence.\n\r",ch);
            REMOVE_BIT(ch->affected_by, AFF_INVISIBLE);
            act("$n fades into existence.",ch,NULL,NULL,TO_ROOM);
          }
       }

       if(IS_SET(obj->extra_flags2, ITEM2_ADD_DETECT_INVIS) )
       {
	  if(!is_affected(ch,skill_lookup("detect invis") ) )
	  {
	    send_to_char("You lose the ability to see the invisible.\n\r",ch);
	    REMOVE_BIT(ch->affected_by, AFF_DETECT_INVIS);
	  }
       }

       if(IS_SET(obj->extra_flags2, ITEM2_ADD_FLY) )
       {
	  if(!is_affected(ch,skill_lookup("fly") ) )
	  {
	    send_to_char("You float back down to the ground.\n\r",ch);
	    REMOVE_BIT(ch->affected_by, AFF_FLYING);
	  }
       }
    }

    if ( obj->item_type == ITEM_LIGHT
    &&   obj->value[2] != 0
    &&   ch->in_room != NULL
    &&   ch->in_room->light > 0 )
	--ch->in_room->light;

    return;
}



/*
 * Count occurrences of an obj in a list.
 */
int count_obj_list( OBJ_INDEX_DATA *pObjIndex, OBJ_DATA *list )
{
    OBJ_DATA *obj;
    int nMatch;

    nMatch = 0;
    /* Bugfix blackbird */

    if (list == NULL) return 0;

    for ( obj = list; obj != NULL; obj = obj->next_content )
    {
	if ( obj->pIndexData == pObjIndex )
	    nMatch++;
    }

    return nMatch;
}



/*
 * Move an obj out of a room.
 */
void obj_from_room( OBJ_DATA *obj )
{
    ROOM_INDEX_DATA *in_room;

    if ( ( in_room = obj->in_room ) == NULL )
    {
	bug( "obj_from_room: NULL.", 0 );
	return;
    }

    if ( obj == in_room->contents )
    {
	in_room->contents = obj->next_content;
    }
    else
    {
	OBJ_DATA *prev;

	for ( prev = in_room->contents; prev; prev = prev->next_content )
	{
	    if ( prev->next_content == obj )
	    {
		prev->next_content = obj->next_content;
		break;
	    }
	}

	if ( prev == NULL )
	{
	    bug( "Obj_from_room: obj not found.", 0 );
	    return;
	}
    }

    obj->in_room      = NULL;
    obj->next_content = NULL;
    return;
}



/*
 * Move an obj into a room.
 */
void obj_to_room( OBJ_DATA *obj, ROOM_INDEX_DATA *pRoomIndex )
{
    obj->next_content           = pRoomIndex->contents;
    pRoomIndex->contents        = obj;
    obj->in_room                = pRoomIndex;
    obj->carried_by             = NULL;
    obj->in_obj                 = NULL;
    return;
}



/*
 * Move an object into an object.
 */
void obj_to_obj( OBJ_DATA *obj, OBJ_DATA *obj_to )
{
    obj->next_content           = obj_to->contains;
    obj_to->contains            = obj;
    obj->in_obj                 = obj_to;
    obj->in_room                = NULL;
    obj->carried_by             = NULL;
    if (obj_to->pIndexData->vnum == OBJ_VNUM_PIT)
	obj->cost = 0;

    for ( ; obj_to != NULL; obj_to = obj_to->in_obj )
    {
	if ( obj_to->carried_by != NULL )
	{
/* Blackbird: Update maxloadfile */
            if ((obj->pIndexData != NULL) &&
                (get_maxload_index(obj->pIndexData->vnum) != NULL) &&
                !IS_NPC(obj_to->carried_by) ) {
                add_maxload_index( obj->pIndexData->vnum, +1, 0);
            }
	    obj_to->carried_by->carry_number += get_obj_number( obj );
	    obj_to->carried_by->carry_weight += get_obj_weight( obj );
	}
    }

    return;
}



/*
 * Move an object out of an object.
 */
void obj_from_obj( OBJ_DATA *obj )
{
    OBJ_DATA *obj_from;

    if ( ( obj_from = obj->in_obj ) == NULL )
    {
	bug( "Obj_from_obj: null obj_from.", 0 );
	return;
    }

    if ( obj == obj_from->contains )
    {
	obj_from->contains = obj->next_content;
    }
    else
    {
	OBJ_DATA *prev;

	for ( prev = obj_from->contains; prev; prev = prev->next_content )
	{
	    if ( prev->next_content == obj )
	    {
		prev->next_content = obj->next_content;
		break;
	    }
	}

	if ( prev == NULL )
	{
	    bug( "Obj_from_obj: obj not found.", 0 );
	    return;
	}
    }

    obj->next_content = NULL;
    obj->in_obj       = NULL;

    for ( ; obj_from != NULL; obj_from = obj_from->in_obj )
    {
	if ( obj_from->carried_by != NULL )
	{
/* Blackbird: Update maxloadfile */
            if ((obj->pIndexData != NULL) &&
                (get_maxload_index(obj->pIndexData->vnum) != NULL) &&
                !IS_NPC(obj_from->carried_by) ) {
                add_maxload_index( obj->pIndexData->vnum, -1, 0);
            }
	    obj_from->carried_by->carry_number -= get_obj_number( obj );
	    obj_from->carried_by->carry_weight -= get_obj_weight( obj );
	}
    }

    return;
}

/*
 * Extract an obj from the world.
 * Variant made by blackbird. We must not updat player in case player leaves
 * the game.
 */
void extract_obj_player( OBJ_DATA *obj )
{
    OBJ_DATA *obj_content;
    OBJ_DATA *obj_next;
    int vnum,i=0;

    vnum = obj ->pIndexData -> vnum;

    if(vnum == 4)	i=1;
    else if(vnum == 5)	i=2;
    else if(vnum == 6)	i=3;
    else if(vnum == 7)	i=4;

    if(obj->trapped != NULL)
      char_from_obj(obj);

    if ( obj->in_room != NULL )
        obj_from_room( obj );
    else if ( obj->carried_by != NULL ) {
        obj_from_char( obj );
        if (get_maxload_index(vnum) != NULL)
           add_maxload_index(vnum, +1, 0);
    }
    else if ( obj->in_obj != NULL ) {
        obj_from_obj( obj );
        if (get_maxload_index(vnum) != NULL)
           add_maxload_index(vnum, +1, 0);
    }
/* This line added by Eclipse to check for NULL data to function call */
    else if( obj == NULL)
        return;

    for ( obj_content = obj->contains; obj_content; obj_content = obj_next )
    {
        obj_next = obj_content->next_content;
        extract_obj_player( obj->contains );
    }

    unregister_object( obj );
    {
        AFFECT_DATA *paf;
        AFFECT_DATA *paf_next;

        for ( paf = obj->affected; paf != NULL; paf = paf_next )
        {
            paf_next    = paf->next;

            paf->next   = NULL;
            free_affect(paf);
/* Blackbird
            paf->next   = affect_free;
            affect_free = paf;
*/
        }
        obj->affected = NULL;

    }

    {
        EXTRA_DESCR_DATA *ed;
        EXTRA_DESCR_DATA *ed_next;

        for ( ed = obj->extra_descr; ed != NULL; ed = ed_next )
        {
            ed_next             = ed->next;
            free_string( ed->description );
            free_string( ed->keyword     );
/* Next line added bye Eclipse to get rid of mem leak noted in merc mail */
            ed->next = extra_descr_free;
            extra_descr_free    = ed;
        }
    }

    free_string( obj->name        );
    free_string( obj->description );
    free_string( obj->short_descr );
    free_string( obj->owner     );
    free_string( obj->action_to_char );
    free_string( obj->action_to_room );

    --obj->pIndexData->count;
    obj->next_free   = obj_free;
    obj_free    = obj;

    if(i!=0)
	respawn_relic(i);

    return;
}



void extract_obj( OBJ_DATA *obj )
{
    OBJ_DATA *obj_content;
    OBJ_DATA *obj_next;
    int vnum,i=0;

    vnum = obj ->pIndexData -> vnum;

    if(vnum == 4)	i=1;
    else if(vnum == 5)	i=2;
    else if(vnum == 6)	i=3;
    else if(vnum == 7)	i=4;

/* Blackbird: Update maxloadfile */
    if ((obj->pIndexData != NULL) &&
        (get_maxload_index(obj->pIndexData->vnum) != NULL)) {
       add_maxload_index(obj->pIndexData->vnum, -1, 1);
    }
    if(obj->trapped != NULL)
      char_from_obj(obj);

    if ( obj->in_room != NULL )
	obj_from_room( obj );
    else if ( obj->carried_by != NULL )
	obj_from_char( obj );
    else if ( obj->in_obj != NULL )
	obj_from_obj( obj );
/* This line added by Eclipse to check for NULL data to function call */
    else if( obj == NULL)
	return;

    for ( obj_content = obj->contains; obj_content; obj_content = obj_next )
    {
	obj_next = obj_content->next_content;
	extract_obj( obj->contains );
    }

    unregister_object( obj );

    {
	AFFECT_DATA *paf;
	AFFECT_DATA *paf_next;

	for ( paf = obj->affected; paf != NULL; paf = paf_next )
	{
	    paf_next    = paf->next;
            paf->next   = NULL;
            free_affect(paf);

/* Blackbird
	    paf->next   = affect_free;
	    affect_free = paf;
*/
	}
        obj->affected = NULL;
    }

    {
	EXTRA_DESCR_DATA *ed;
	EXTRA_DESCR_DATA *ed_next;

	for ( ed = obj->extra_descr; ed != NULL; ed = ed_next )
	{
	    ed_next             = ed->next;
	    free_string( ed->description );
	    free_string( ed->keyword     );
/* Next line added bye Eclipse to get rid of mem leak noted in merc mail */
	    ed->next = extra_descr_free;
	    extra_descr_free    = ed;
	}
    }

    free_string( obj->name        );
    free_string( obj->description );
    free_string( obj->short_descr );
    free_string( obj->owner     );
    free_string( obj->action_to_char );
    free_string( obj->action_to_room );

    --obj->pIndexData->count;
    obj->next_free   = obj_free;
    obj_free    = obj;

    if(i!=0)
	respawn_relic(i);

    return;
}



/*
 * Extract a char from the world.
 */
void extract_char( CHAR_DATA *ch, bool fPull )
{
    CHAR_DATA *wch;
    OBJ_DATA *obj;
    OBJ_DATA *obj_next;
    LIST_ITERATOR iter;

    if(ch->in_object != NULL )
    {
      if( !IS_NPC(ch) )
      {
	char_to_room(ch,get_room_index(ROOM_VNUM_ALTAR) );
	extract_obj(ch->in_object);
      }
      else
	char_to_room(ch,get_room_index(1));
    }

    if ( ch->in_room == NULL )
    {
	bug( "Extract_char: NULL.", 0 );
	return;
    }

    nuke_pets(ch);
    ch->pet = NULL; /* just in case */

    if ( fPull )

	die_follower( ch );

    stop_fighting( ch, true );
    do_stop_hunting( ch, "hunter is dead");

    for ( obj = ch->carrying; obj != NULL; obj = obj_next )
    {
	obj_next = obj->next_content;
/* Blackbird: Take care that maxload does not get updated in case player leaves */
        if (IS_NPC(ch))
	  extract_obj( obj );
        else
          extract_obj_player( obj );
    }

    char_from_room( ch );

    if ( !fPull )
    {
	char_to_room( ch, get_room_index( ROOM_VNUM_DEATH ) );
	return;
    }

    if ( IS_NPC(ch) )
	--ch->pIndexData->count;

    if ( ch->desc != NULL && ch->desc->original != NULL )
	do_return( ch, "" );

    list_iterator_start( &iter, &character_list );
    while ( ( wch = list_iterator_next( &iter ) ) != NULL )
    {
        if ( wch->reply == ch )
            wch->reply = NULL;
    }

    unregister_character( ch );

    if ( ch->desc )
        ch->desc->character = NULL;
    free_char( ch );
    return;
}



/*
 * Find a char in the room.
 */
CHAR_DATA *get_char_room( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *rch;
    int number;
    int count;

    number = number_argument( argument, arg );
    count  = 0;
    if ( !str_prefix( arg, "self" ) )
	return ch;
    for ( rch = ch->in_room->people; rch != NULL; rch = rch->next_in_room )
    {
	if ( !can_see( ch, rch ) || !is_name( arg, rch->name ) )
	    continue;
	if ( ++count == number )
	    return rch;
    }

    return NULL;
}




/*
 * Find a char in the world.
 */
CHAR_DATA *get_char_world( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    CHAR_DATA *wch;
    int number;
    int count;
    LIST_ITERATOR iter;

    if ( ( wch = get_char_room( ch, argument ) ) != NULL )
	return wch;

    number = number_argument( argument, arg );
    count  = 0;
    FOR_EACH_CHARACTER( iter, wch )
    {
        if ( wch->in_room == NULL || !can_see( ch, wch )
        ||   !is_name( arg, wch->name ) )
            continue;
        if ( ++count == number )
            return wch;
    }

    return NULL;
}



/*
 * Find some object with a given index data.
 * Used by area-reset 'P' command.
 */
OBJ_DATA *get_obj_type( OBJ_INDEX_DATA *pObjIndex )
{
    OBJ_DATA *obj;
    LIST_ITERATOR iter;

    FOR_EACH_OBJECT( iter, obj )
    {
        if ( obj->pIndexData == pObjIndex )
            return obj;
    }

    return NULL;
}


/*
 * Find an obj in a list.
 */
OBJ_DATA *get_obj_list( CHAR_DATA *ch, char *argument, OBJ_DATA *list )
{
    char arg[MAX_INPUT_LENGTH];
    OBJ_DATA *obj;
    int number;
    int count;

    number = number_argument( argument, arg );
    count  = 0;
    for ( obj = list; obj != NULL; obj = obj->next_content )
    {
	if ( can_see_obj( ch, obj ) && is_name( arg, obj->name ) )
	{
	    if ( ++count == number )
		return obj;
	}
    }

    return NULL;
}



/*
 * Find an obj in player's inventory.
 */
OBJ_DATA *get_obj_carry( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    OBJ_DATA *obj;
    int number;
    int count;

    number = number_argument( argument, arg );
    count  = 0;
    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( obj->wear_loc == WEAR_NONE
	&&   (can_see_obj( ch, obj ) )
	&&   is_name( arg, obj->name ) )
	{
	    if ( ++count == number )
		return obj;
	}
    }

    return NULL;
}



/*
 * Find an obj in player's equipment.
 */
OBJ_DATA *get_obj_wear( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    OBJ_DATA *obj;
    int number;
    int count;

    number = number_argument( argument, arg );
    count  = 0;
    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
	if ( obj->wear_loc != WEAR_NONE
	&&   can_see_obj( ch, obj )
	&&   is_name( arg, obj->name ) )
	{
	    if ( ++count == number )
		return obj;
	}
    }

    return NULL;
}



/*
 * Find an obj in the room or in inventory.
 */
OBJ_DATA *get_obj_here( CHAR_DATA *ch, char *argument )
{
    OBJ_DATA *obj;

    obj = get_obj_list( ch, argument, ch->in_room->contents );

    if ( obj != NULL )
	return obj;

    if ( ( obj = get_obj_carry( ch, argument ) ) != NULL )
	return obj;

    if ( ( obj = get_obj_wear( ch, argument ) ) != NULL )
	return obj;

    return NULL;
}



/*
 * Find an obj in the world.
 */
OBJ_DATA *get_obj_world( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    OBJ_DATA *obj;
    int number;
    int count;
    LIST_ITERATOR iter;

    if ( ( obj = get_obj_here( ch, argument ) ) != NULL )
	return obj;

    number = number_argument( argument, arg );
    count  = 0;
    FOR_EACH_OBJECT( iter, obj )
    {
        if ( can_see_obj( ch, obj ) && is_name( arg, obj->name ) )
        {
	    if ( ++count == number )
		return obj;
	}
    }

    return NULL;
}


OBJ_DATA *create_money( int amount, int type )
{
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *obj;

    if ( amount <= 0 ) {
	bug( "Create_money: zero or negative money %d.", amount );
	amount = 1;
    }

    if ( amount == 1 ) {
	obj = create_object( get_obj_index( OBJ_VNUM_MONEY_ONE ), 0 );
	snprintf(buf, sizeof(buf), obj->name,
	    type == TYPE_COPPER   ? "copper"   :
	    type == TYPE_SILVER   ? "silver"   :
	    type == TYPE_GOLD     ? "gold"     :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string(obj->name);
	obj->name = str_dup(buf);
	snprintf(buf, sizeof(buf), obj->short_descr,
	    type == TYPE_COPPER   ? "copper"   :
	    type == TYPE_SILVER   ? "silver"   :
	    type == TYPE_GOLD     ? "gold"     :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string(obj->short_descr);
	obj->short_descr = str_dup(buf);
	snprintf(buf, sizeof(buf), obj->description,
	    type == TYPE_COPPER   ? "copper"   :
	    type == TYPE_SILVER   ? "silver"   :
	    type == TYPE_GOLD     ? "gold"     :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string(obj->description);
	obj->description= str_dup(buf);
	obj->value[1]	= type;
    } else {
	obj = create_object( get_obj_index( OBJ_VNUM_MONEY_SOME ), 0 );
	snprintf(buf, sizeof(buf), obj->name,
	    type == TYPE_COPPER   ? "copper"   :
	    type == TYPE_SILVER   ? "silver"   :
	    type == TYPE_GOLD     ? "gold"     :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string(obj->name);
	obj->name = str_dup(buf);
	snprintf( buf, sizeof(buf), obj->short_descr, amount,
	    type == TYPE_COPPER   ? "copper" :
	    type == TYPE_SILVER   ? "silver" :
	    type == TYPE_GOLD     ? "gold" :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string( obj->short_descr );
	obj->short_descr        = str_dup( buf );
	snprintf(buf, sizeof(buf), obj->description,
	    type == TYPE_COPPER   ? "copper"   :
	    type == TYPE_SILVER   ? "silver"   :
	    type == TYPE_GOLD     ? "gold"     :
	    type == TYPE_PLATINUM ? "platinum" : "bug_money_type");
	free_string(obj->description);
	obj->description= str_dup(buf);
	obj->value[0]           = amount;
	obj->value[1]		= type;
	obj->cost               = amount;
    }

    return obj;
}



/*
 * Return # of objects which an object counts as.
 * Thanks to Tony Chamberlain for the correct recursive code here.
 */
int get_obj_number( OBJ_DATA *obj )
{
    int number;

/*    if ( obj->item_type == ITEM_CONTAINER || obj->item_type == ITEM_MONEY)*/
    if (obj->item_type == ITEM_MONEY)
	number = 0;
    else
	number = 1;

    for ( obj = obj->contains; obj != NULL; obj = obj->next_content )
	number += get_obj_number( obj );

    return number;
}

int get_obj_weight( OBJ_DATA *obj )
{
    int weight;

    if(obj->item_type == ITEM_MONEY)
	weight = obj->value[0]/100;
    else
        weight = obj->weight;

    for ( obj = obj->contains; obj; obj = obj->next_content )
	weight += get_obj_weight( obj );

    return weight;
}



/*
 * True if room is dark.
 */
bool room_is_dark( ROOM_INDEX_DATA *pRoomIndex )
{

    if ( pRoomIndex->light > 0 )
	return false;

    if ( IS_SET(pRoomIndex->room_flags, ROOM_DARK) )
	return true;

    if ( pRoomIndex->sector_type == SECT_INSIDE
    ||   pRoomIndex->sector_type == SECT_CITY )
	return false;

    if ( weather_info.sunlight == SUN_SET
    ||   weather_info.sunlight == SUN_DARK )
	return true;

    return false;
}



/*
 * True if room is private.
 */
bool room_is_private( ROOM_INDEX_DATA *pRoomIndex )
{
    CHAR_DATA *rch;
    int count;

    count = 0;
    for ( rch = pRoomIndex->people; rch != NULL; rch = rch->next_in_room)
	if(rch->battleticks == 0)
  	    count++;

    if ( IS_SET(pRoomIndex->room_flags, ROOM_PRIVATE)  && count >= 2 )
	return true;

    if ( IS_SET(pRoomIndex->room_flags, ROOM_SOLITARY) && count >= 1 )
	return true;

    if ( IS_SET(pRoomIndex->room_flags, ROOM_IMP_ONLY) )
	return true;

    return false;
}

/* visibility on a room -- for entering and exits */
bool can_see_room( CHAR_DATA *ch, ROOM_INDEX_DATA *pRoomIndex )
{
    if ( pRoomIndex == NULL )
        return false;

    if (IS_SET(pRoomIndex->room_flags, ROOM_IMP_ONLY)
    &&  get_trust(ch) < MAX_LEVEL)
	return false;

    if (IS_SET(pRoomIndex->room_flags, ROOM_GODS_ONLY)
    &&  !IS_IMMORTAL(ch))
	return false;

    if (IS_SET(pRoomIndex->room_flags, ROOM_HEROES_ONLY)
    &&  !IS_HERO(ch))
	return false;

    if (IS_SET(pRoomIndex->room_flags, ROOM_CULT_ENTRANCE)
    && ch->level < 25)
	return false;

    if (IS_SET(pRoomIndex->room_flags,ROOM_NEWBIES_ONLY)
    &&  ch->level > 5 && !IS_IMMORTAL(ch))
	return false;

    return true;
}



/*
 * True if char can see victim.
 */
bool can_see( CHAR_DATA *ch, const CHAR_DATA *victim )
{
/* RT changed so that WIZ_INVIS has levels */
    if ( ch == victim )
	return true;

    if ( !IS_NPC(victim)
    &&   IS_SET(victim->act, PLR_WIZINVIS)
    &&   get_trust( ch ) < victim->invis_level )
	return false;

    if ( IS_NPC(ch) && IS_AFFECTED(victim, AFF2_GHOST))
	return false;

    if ( !IS_NPC(victim)
    &&   IS_SET(victim->act, PLR_CLOAKED)
    &&   ch->in_room != victim->in_room
    &&   get_trust( ch ) < victim->cloak_level )
	return false;

    if ( (!IS_NPC(ch) && IS_SET(ch->act, PLR_HOLYLIGHT))
    ||   (IS_NPC(ch) && IS_IMMORTAL(ch)))
	return true;

    if ( IS_AFFECTED(ch, AFF_BLIND) )
	return false;

    if ( room_is_dark( ch->in_room ) && !IS_AFFECTED(ch, AFF_INFRARED) )
	return false;

    if ( IS_AFFECTED(victim, AFF_INVISIBLE)
    &&   !IS_AFFECTED(ch, AFF_DETECT_INVIS) )
	return false;

    if ( IS_AFFECTED2(victim, AFF2_GHOST)
    &&   !IS_AFFECTED(ch, AFF_DETECT_INVIS ) )
	return false;

    if ( IS_AFFECTED2(victim, AFF2_STEALTH) ) {
	int chance = get_skill(victim,gsn_stealth);

	if(weather_info.sunlight == SUN_RISE || weather_info.sunlight == SUN_SET)
	    chance -= 10;
	if(weather_info.sunlight == SUN_LIGHT)
	    chance -= 20;
	if(weather_info.sunlight == SUN_DARK)
	    chance += 10;

	if(weather_info.sky == SKY_RAINING || weather_info.sky == SKY_CLOUDY)
	    chance += 10;
	if(weather_info.sky == SKY_CLOUDLESS)
	    chance -= 10;
	if(weather_info.sky == SKY_LIGHTNING)
	    chance += 15;

	if(number_percent() < chance)
	    return false;
    }

    if ( IS_AFFECTED(victim, AFF_HIDE)
    &&   !IS_AFFECTED(ch, AFF_DETECT_HIDDEN)
    &&   victim->fighting == NULL)
/*    &&   ( IS_NPC(ch) ? !IS_NPC(victim) : IS_NPC(victim) ) )*/
	return false;

    return true;
}



/*
 * True if char can see obj.
 */
bool can_see_obj( CHAR_DATA *ch, const OBJ_DATA *obj )
{
    if ( !IS_NPC(ch) && IS_SET(ch->act, PLR_HOLYLIGHT) )
        return true;

    if ( IS_SET(obj->extra_flags,ITEM_VIS_DEATH))
	return false;

    if ( IS_AFFECTED( ch, AFF_BLIND ) && obj->item_type != ITEM_POTION)
	return false;

    if ( obj->item_type == ITEM_LIGHT && obj->value[2] != 0 )
	return true;

    if ( IS_SET(obj->extra_flags, ITEM_INVIS)
    &&   !IS_AFFECTED(ch, AFF_DETECT_INVIS) )
	return false;

    if ( IS_OBJ_STAT(obj,ITEM_GLOW))
	return true;

    if ( room_is_dark( ch->in_room ) && !IS_AFFECTED(ch, AFF_INFRARED) )
	return false;

    return true;
}



/*
 * True if char can drop obj.
 */
bool can_drop_obj( CHAR_DATA *ch, OBJ_DATA *obj )
{
    if ( !IS_SET(obj->extra_flags, ITEM_NODROP) )
	return true;

    if ( !IS_NPC(ch) && ch->level >= LEVEL_IMMORTAL )
	return true;

    return false;
}



/*
 * Return ascii name of an item type.
 */
char *item_type_name( OBJ_DATA *obj )
{
    switch ( obj->item_type )
    {
    case ITEM_LIGHT:            return "light";
    case ITEM_SCROLL:           return "scroll";
    case ITEM_WAND:             return "wand";
    case ITEM_STAFF:            return "staff";
    case ITEM_WEAPON:           return "weapon";
    case ITEM_TREASURE:         return "treasure";
    case ITEM_ARMOR:            return "armor";
    case ITEM_POTION:           return "potion";
    case ITEM_FURNITURE:        return "furniture";
    case ITEM_TRASH:            return "trash";
    case ITEM_CLOTHING:         return "clothing";
    case ITEM_CONTAINER:        return "container";
    case ITEM_DRINK_CON:        return "drink container";
    case ITEM_KEY:              return "key";
    case ITEM_FOOD:             return "food";
    case ITEM_MONEY:            return "money";
    case ITEM_BOAT:             return "boat";
    case ITEM_CORPSE_NPC:       return "npc corpse";
    case ITEM_CORPSE_PC:        return "pc corpse";
    case ITEM_FOUNTAIN:         return "fountain";
    case ITEM_PILL:             return "pill";
    case ITEM_MAP:              return "map";
    case ITEM_SCUBA_GEAR:       return "scuba gear";
    case ITEM_PORTAL:		        return "portal";
    case ITEM_MANIPULATION:     return "manipulate";
    case ITEM_SADDLE:           return "saddle";
    case ITEM_HERB:             return "herb";
    case ITEM_SPELL_COMPONENT:  return "spell component";
    case ITEM_SOUL_CONTAINER:   return "soul container";
    case ITEM_ACTION:		return "action";
    case ITEM_CAKE:		return "weedding cake";
    }

    bug( "Item_type_name: unknown type %d.", obj->item_type );
    return "(unknown)";
}



/*
 * Return ascii name of an affect location.
 */
char *affect_loc_name( int location )
{
    switch ( location )
    {
    case APPLY_NONE:            return "none";
    case APPLY_STR:             return "strength";
    case APPLY_DEX:             return "dexterity";
    case APPLY_INT:             return "intelligence";
    case APPLY_WIS:             return "wisdom";
    case APPLY_CON:             return "constitution";
    case APPLY_SEX:             return "sex";
    case APPLY_CLASS:           return "class";
    case APPLY_LEVEL:           return "level";
    case APPLY_AGE:             return "age";
    case APPLY_MANA:            return "mana";
    case APPLY_HIT:             return "hp";
    case APPLY_MOVE:            return "moves";
    case APPLY_GOLD:            return "gold";
    case APPLY_EXP:             return "experience";
    case APPLY_AC:              return "armor class";
    case APPLY_HITROLL:         return "hit roll";
    case APPLY_DAMROLL:         return "damage roll";
    case APPLY_SAVING_PARA:     return "save vs paralysis";
    case APPLY_SAVING_ROD:      return "save vs rod";
    case APPLY_SAVING_PETRI:    return "save vs petrification";
    case APPLY_SAVING_BREATH:   return "save vs breath";
    case APPLY_SAVING_SPELL:    return "save vs spell";
    }

    bug( "Affect_location_name: unknown location %d.", location );
    return "(unknown)";
}



/*
 * Return ascii name of an affect bit vector.
 */
char *affect_bit_name( long vector )
{
    static char buf[512];

    buf[0] = '\0';
    if ( vector & AFF_BLIND         ) toc_strlcat( buf, " blind", sizeof(buf) );
    if ( vector & AFF_INVISIBLE     ) toc_strlcat( buf, " invisible", sizeof(buf) );
    if ( vector & AFF_DETECT_EVIL   ) toc_strlcat( buf, " detect_evil", sizeof(buf) );
    if ( vector & AFF_DETECT_INVIS  ) toc_strlcat( buf, " detect_invis", sizeof(buf) );
    if ( vector & AFF_DETECT_MAGIC  ) toc_strlcat( buf, " detect_magic", sizeof(buf) );
    if ( vector & AFF_DETECT_HIDDEN ) toc_strlcat( buf, " detect_hidden", sizeof(buf) );
    if ( vector & AFF_SANCTUARY     ) toc_strlcat( buf, " sanctuary", sizeof(buf) );
    if ( vector & AFF_FAERIE_FIRE   ) toc_strlcat( buf, " faerie_fire", sizeof(buf) );
    if ( vector & AFF_INFRARED      ) toc_strlcat( buf, " infrared", sizeof(buf) );
    if ( vector & AFF_CURSE         ) toc_strlcat( buf, " curse", sizeof(buf) );
    if ( vector & AFF_POISON        ) toc_strlcat( buf, " poison", sizeof(buf) );
    if ( vector & AFF_PROTECT       ) toc_strlcat( buf, " protect", sizeof(buf) );
    if ( vector & AFF_SLEEP         ) toc_strlcat( buf, " sleep", sizeof(buf) );
    if ( vector & AFF_SNEAK         ) toc_strlcat( buf, " sneak", sizeof(buf) );
    if ( vector & AFF_HIDE          ) toc_strlcat( buf, " hide", sizeof(buf) );
    if ( vector & AFF_CHARM         ) toc_strlcat( buf, " charm", sizeof(buf) );
    if ( vector & AFF_FLYING        ) toc_strlcat( buf, " flying", sizeof(buf) );
    if ( vector & AFF_PASS_DOOR     ) toc_strlcat( buf, " pass_door", sizeof(buf) );
    if ( vector & AFF_BERSERK       ) toc_strlcat( buf, " berserk", sizeof(buf) );
    if ( vector & AFF_CALM          ) toc_strlcat( buf, " calm", sizeof(buf) );
    if ( vector & AFF_HASTE         ) toc_strlcat( buf, " haste", sizeof(buf) );
    if ( vector & AFF_PLAGUE        ) toc_strlcat( buf, " plague", sizeof(buf) );
    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *affect2_bit_name( long vector )
{
    static char buf[512];

    buf[0] = '\0';
    if ( vector & AFF2_HOLD          ) toc_strlcat( buf, " hold", sizeof(buf) );
    if ( vector & AFF2_FLAMING_HOT   ) toc_strlcat( buf, " hot flames", sizeof(buf) );
    if ( vector & AFF2_FLAMING_COLD  ) toc_strlcat( buf, " cold flames", sizeof(buf) );
    if ( vector & AFF2_PARALYSIS     ) toc_strlcat( buf, " paralysis", sizeof(buf) );
    if ( vector & AFF2_DARK_VISION   ) toc_strlcat( buf, " dark_vision", sizeof(buf) );
    if ( vector & AFF2_DETECT_GOOD   ) toc_strlcat( buf, " detect_good", sizeof(buf) );
    if ( vector & AFF2_STEALTH       ) toc_strlcat( buf, " stealth", sizeof(buf) );
    if ( vector & AFF2_STUNNED       ) toc_strlcat( buf, " stunned", sizeof(buf) );
    if ( vector & AFF2_NO_RECOVER   ) toc_strlcat( buf,  " sleepless", sizeof(buf) );
    if ( vector & AFF2_FORCE_SWORD  ) toc_strlcat( buf,  " force_sword", sizeof(buf) );
    if ( vector & AFF2_GHOST	    ) toc_strlcat( buf,  " ghostly_presence", sizeof(buf) );
    if ( vector & AFF2_DIVINE_PROT  ) toc_strlcat( buf,  " divine protection", sizeof(buf) );
    return (buf[0] != '\0' ) ? buf+1 : "none";
}
/*
 * Return ascii name of extra flags vector.
 */
char *extra_bit_name( int extra_flags )
{
    static char buf[512];

    buf[0] = '\0';
    if ( extra_flags & ITEM_GLOW         ) toc_strlcat( buf, " glow", sizeof(buf) );
    if ( extra_flags & ITEM_HUM          ) toc_strlcat( buf, " hum", sizeof(buf) );
    if ( extra_flags & ITEM_DARK         ) toc_strlcat( buf, " dark", sizeof(buf) );
    if ( extra_flags & ITEM_LOCK         ) toc_strlcat( buf, " lock", sizeof(buf) );
    if ( extra_flags & ITEM_EVIL         ) toc_strlcat( buf, " evil", sizeof(buf) );
    if ( extra_flags & ITEM_INVIS        ) toc_strlcat( buf, " invis", sizeof(buf) );
    if ( extra_flags & ITEM_MAGIC        ) toc_strlcat( buf, " magic", sizeof(buf) );
    if ( extra_flags & ITEM_NODROP       ) toc_strlcat( buf, " nodrop", sizeof(buf) );
    if ( extra_flags & ITEM_BLESS        ) toc_strlcat( buf, " bless", sizeof(buf) );
    if ( extra_flags & ITEM_DAMAGED        ) toc_strlcat( buf, " damaged", sizeof(buf) );
    if ( extra_flags & ITEM_ANTI_GOOD    ) toc_strlcat( buf, " anti-good", sizeof(buf) );
    if ( extra_flags & ITEM_ANTI_EVIL    ) toc_strlcat( buf, " anti-evil", sizeof(buf) );
    if ( extra_flags & ITEM_ANTI_NEUTRAL ) toc_strlcat( buf, " anti-neutral", sizeof(buf) );
    if ( extra_flags & ITEM_NOREMOVE     ) toc_strlcat( buf, " noremove", sizeof(buf) );
    if ( extra_flags & ITEM_INVENTORY    ) toc_strlcat( buf, " inventory", sizeof(buf) );
    if ( extra_flags & ITEM_NOPURGE      ) toc_strlcat( buf, " nopurge", sizeof(buf) );
    if ( extra_flags & ITEM_VIS_DEATH    ) toc_strlcat( buf, " vis_death", sizeof(buf) );
    if ( extra_flags & ITEM_ROT_DEATH    ) toc_strlcat( buf, " rot_death", sizeof(buf) );
    if ( extra_flags & ITEM_METAL        ) toc_strlcat( buf, " metal", sizeof(buf) );
    if ( extra_flags & ITEM_BOUNCE       ) toc_strlcat( buf, " bounce", sizeof(buf) );
    if ( extra_flags & ITEM_TPORT        ) toc_strlcat( buf, " Tport", sizeof(buf) );
    if ( extra_flags & ITEM_NOIDENTIFY   ) toc_strlcat( buf, " no_identify", sizeof(buf) );
    if ( extra_flags & ITEM_NOLOCATE     ) toc_strlcat( buf, " no_locate", sizeof(buf) );
    if ( extra_flags & ITEM_RACE_RESTRICTED) toc_strlcat( buf, " race_restrict", sizeof(buf) );
    if ( extra_flags & ITEM_ADD_AFFECT   ) toc_strlcat( buf, " aff_wearer", sizeof(buf) );
    if ( extra_flags & ITEM_EMBALMED	 ) toc_strlcat( buf, " embalmed", sizeof(buf) );
    if ( extra_flags & ITEM_FLAGS2       ) toc_strlcat( buf, " flags2", sizeof(buf) );
    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *extra2_bit_name( int extra_flags )
{
 static char buf[512];

  buf[0] = '\0';
  if ( extra_flags & ITEM2_HUMAN_ONLY        ) toc_strlcat( buf, " humans only", sizeof(buf) );
  if ( extra_flags & ITEM2_ELF_ONLY          ) toc_strlcat( buf, " elves only", sizeof(buf) );
  if ( extra_flags & ITEM2_DWARF_ONLY        ) toc_strlcat( buf, " dwarves only", sizeof(buf) );
  if ( extra_flags & ITEM2_HALFLING_ONLY     ) toc_strlcat( buf, " halflings only", sizeof(buf) );
  if ( extra_flags & ITEM2_ADD_INVIS         ) toc_strlcat( buf, " add_invis", sizeof(buf) );
  if ( extra_flags & ITEM2_ADD_DETECT_INVIS  ) toc_strlcat( buf, " detect_invis", sizeof(buf) );
  if ( extra_flags & ITEM2_ADD_FLY           ) toc_strlcat( buf, " add_flying", sizeof(buf) );
  if ( extra_flags & ITEM2_NO_CAN_SEE        ) toc_strlcat( buf, " no_can_see", sizeof(buf) );
  if ( extra_flags & ITEM2_NOSTEAL	     ) toc_strlcat( buf, " no_steal", sizeof(buf) );
  return ( buf[0] != '\0' ) ? buf+1 : "none";

}
/* return ascii name of an act vector */
char *act_bit_name( long act_flags )
{
    static char buf[512];

    buf[0] = '\0';

    if (IS_SET(act_flags,ACT_IS_NPC))
    {
	toc_strlcat( buf, " npc", sizeof(buf) );
	if (act_flags & ACT_SENTINEL    ) toc_strlcat( buf, " sentinel", sizeof(buf) );
	if (act_flags & ACT_SCAVENGER   ) toc_strlcat( buf, " scavenger", sizeof(buf) );
	if (act_flags & ACT_AGGRESSIVE  ) toc_strlcat( buf, " aggressive", sizeof(buf) );
	if (act_flags & ACT_STAY_AREA   ) toc_strlcat( buf, " stay_area", sizeof(buf) );
	if (act_flags & ACT_WIMPY       ) toc_strlcat( buf, " wimpy", sizeof(buf) );
	if (act_flags & ACT_PET         ) toc_strlcat( buf, " pet", sizeof(buf) );
	if (act_flags & ACT_TRAIN       ) toc_strlcat( buf, " train", sizeof(buf) );
	if (act_flags & ACT_PRACTICE    ) toc_strlcat( buf, " practice", sizeof(buf) );
	if (act_flags & ACT_UNDEAD      ) toc_strlcat( buf, " undead", sizeof(buf) );
	if (act_flags & ACT_CLERIC      ) toc_strlcat( buf, " cleric", sizeof(buf) );
	if (act_flags & ACT_MAGE        ) toc_strlcat( buf, " mage", sizeof(buf) );
	if (act_flags & ACT_THIEF       ) toc_strlcat( buf, " thief", sizeof(buf) );
	if (act_flags & ACT_WARRIOR     ) toc_strlcat( buf, " warrior", sizeof(buf) );
	if (act_flags & ACT_NOALIGN     ) toc_strlcat( buf, " no_align", sizeof(buf) );
	if (act_flags & ACT_NOPURGE     ) toc_strlcat( buf, " no_purge", sizeof(buf) );
	if (act_flags & ACT_IS_HEALER   ) toc_strlcat( buf, " healer", sizeof(buf) );
	if (act_flags & ACT_GAIN        ) toc_strlcat( buf, " skill_train", sizeof(buf) );
	if (act_flags & ACT_UPDATE_ALWAYS) toc_strlcat( buf, " update_always", sizeof(buf) );
	if (act_flags & ACT_NOSHOVE     ) toc_strlcat( buf, " no_shove", sizeof(buf) );
	if (act_flags & ACT_MOUNTABLE   ) toc_strlcat( buf, " mountable", sizeof(buf) );
        if (act_flags & ACT_NOKILL	) toc_strlcat( buf, " nokill", sizeof(buf) );
    }
    else
    {
	toc_strlcat( buf, " player", sizeof(buf) );
	if (act_flags & PLR_BOUGHT_PET  ) toc_strlcat( buf, " owner", sizeof(buf) );
	if (act_flags & PLR_AUTOASSIST  ) toc_strlcat( buf, " autoassist", sizeof(buf) );
	if (act_flags & PLR_AUTOEXIT    ) toc_strlcat( buf, " autoexit", sizeof(buf) );
	if (act_flags & PLR_AUTOLOOT    ) toc_strlcat( buf, " autoloot", sizeof(buf) );
	if (act_flags & PLR_AUTOSAC     ) toc_strlcat( buf, " autosac", sizeof(buf) );
	if (act_flags & PLR_AUTOGOLD    ) toc_strlcat( buf, " autogold", sizeof(buf) );
	if (act_flags & PLR_AUTOSPLIT   ) toc_strlcat( buf, " autosplit", sizeof(buf) );
	if (act_flags & PLR_HOLYLIGHT   ) toc_strlcat( buf, " holy_light", sizeof(buf) );
	if (act_flags & PLR_WIZINVIS    ) toc_strlcat( buf, " wizinvis", sizeof(buf) );
	if (act_flags & PLR_CANLOOT     ) toc_strlcat( buf, " loot_corpse", sizeof(buf) );
	if (act_flags & PLR_NOSUMMON    ) toc_strlcat( buf, " no_summon", sizeof(buf) );
	if (act_flags & PLR_NOFOLLOW    ) toc_strlcat( buf, " no_follow", sizeof(buf) );
	if (act_flags & PLR_FREEZE      ) toc_strlcat( buf, " frozen", sizeof(buf) );
	if (act_flags & PLR_WANTED      ) toc_strlcat( buf, " wanted", sizeof(buf) );
    }
    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *act2_bit_name( long act_flags, long act_flags2 )
{
    static char buf[512];

    buf[0] = '\0';

    if (IS_SET(act_flags,ACT_IS_NPC))
    {
	if (act_flags2 & ACT2_LYCANTH      ) toc_strlcat( buf, " lycanthropy", sizeof(buf) );
	if (act_flags2 & ACT2_NO_TPORT      ) toc_strlcat( buf, " YES!", sizeof(buf) );

    }
    else
    {                 /*PLR_*/
	if (act_flags2 & ACT2_NO_TPORT ) toc_strlcat( buf, " YES!", sizeof(buf) );
    }
    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *comm_bit_name(long comm_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (comm_flags & COMM_QUIET         ) toc_strlcat( buf, " quiet", sizeof(buf) );
    if (comm_flags & COMM_DEAF          ) toc_strlcat( buf, " deaf", sizeof(buf) );
    if (comm_flags & COMM_NOWIZ         ) toc_strlcat( buf, " no_wiz", sizeof(buf) );
    if (comm_flags & COMM_NOGRATZ       ) toc_strlcat( buf, " no_gratz", sizeof(buf) );
    if (comm_flags & COMM_NOGOSSIP      ) toc_strlcat( buf, " no_gossip", sizeof(buf) );
    if (comm_flags & COMM_NOQUESTION    ) toc_strlcat( buf, " no_question", sizeof(buf) );
    if (comm_flags & COMM_NOMUSIC       ) toc_strlcat( buf, " no_music", sizeof(buf) );
    if (comm_flags & COMM_COMPACT       ) toc_strlcat( buf, " compact", sizeof(buf) );
    if (comm_flags & COMM_BRIEF         ) toc_strlcat( buf, " brief", sizeof(buf) );
    if (comm_flags & COMM_PROMPT        ) toc_strlcat( buf, " prompt", sizeof(buf) );
    if (comm_flags & COMM_COMBINE       ) toc_strlcat( buf, " combine", sizeof(buf) );
    if (comm_flags & COMM_NOEMOTE       ) toc_strlcat( buf, " no_emote", sizeof(buf) );
    if (comm_flags & COMM_NOSHOUT       ) toc_strlcat( buf, " no_shout", sizeof(buf) );
    if (comm_flags & COMM_NOTELL        ) toc_strlcat( buf, " no_tell", sizeof(buf) );
    if (comm_flags & COMM_NOCHANNELS    ) toc_strlcat( buf, " no_channels", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *imm_bit_name(long imm_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (imm_flags & IMM_SUMMON          ) toc_strlcat( buf, " summon", sizeof(buf) );
    if (imm_flags & IMM_CHARM           ) toc_strlcat( buf, " charm", sizeof(buf) );
    if (imm_flags & IMM_MAGIC           ) toc_strlcat( buf, " magic", sizeof(buf) );
    if (imm_flags & IMM_WEAPON          ) toc_strlcat( buf, " weapon", sizeof(buf) );
    if (imm_flags & IMM_BASH            ) toc_strlcat( buf, " blunt", sizeof(buf) );
    if (imm_flags & IMM_PIERCE          ) toc_strlcat( buf, " piercing", sizeof(buf) );
    if (imm_flags & IMM_SLASH           ) toc_strlcat( buf, " slashing", sizeof(buf) );
    if (imm_flags & IMM_FIRE            ) toc_strlcat( buf, " fire", sizeof(buf) );
    if (imm_flags & IMM_COLD            ) toc_strlcat( buf, " cold", sizeof(buf) );
    if (imm_flags & IMM_LIGHTNING       ) toc_strlcat( buf, " lightning", sizeof(buf) );
    if (imm_flags & IMM_ACID            ) toc_strlcat( buf, " acid", sizeof(buf) );
    if (imm_flags & IMM_POISON          ) toc_strlcat( buf, " poison", sizeof(buf) );
    if (imm_flags & IMM_NEGATIVE        ) toc_strlcat( buf, " negative", sizeof(buf) );
    if (imm_flags & IMM_HOLY            ) toc_strlcat( buf, " holy", sizeof(buf) );
    if (imm_flags & IMM_ENERGY          ) toc_strlcat( buf, " energy", sizeof(buf) );
    if (imm_flags & IMM_MENTAL          ) toc_strlcat( buf, " mental", sizeof(buf) );
    if (imm_flags & IMM_DISEASE         ) toc_strlcat( buf, " disease", sizeof(buf) );
    if (imm_flags & IMM_DROWNING        ) toc_strlcat( buf, " drowning", sizeof(buf) );
    if (imm_flags & IMM_LIGHT           ) toc_strlcat( buf, " light", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *res_bit_name(long res_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (res_flags & RES_CHARM         ) toc_strlcat( buf, " charm", sizeof(buf) );
    if (res_flags & RES_MAGIC         ) toc_strlcat( buf, " magic", sizeof(buf) );
    if (res_flags & RES_WEAPON        ) toc_strlcat( buf, " weapon", sizeof(buf) );
    if (res_flags & RES_BASH          ) toc_strlcat( buf, " bash", sizeof(buf) );
    if (res_flags & RES_PIERCE        ) toc_strlcat( buf, " pierce", sizeof(buf) );
    if (res_flags & RES_SLASH         ) toc_strlcat( buf, " slash", sizeof(buf) );
    if (res_flags & RES_FIRE          ) toc_strlcat( buf, " fire", sizeof(buf) );
    if (res_flags & RES_COLD          ) toc_strlcat( buf, " cold", sizeof(buf) );
    if (res_flags & RES_LIGHTNING     ) toc_strlcat( buf, " lightning", sizeof(buf) );
    if (res_flags & RES_ACID          ) toc_strlcat( buf, " acid", sizeof(buf) );
    if (res_flags & RES_POISON        ) toc_strlcat( buf, " poison", sizeof(buf) );
    if (res_flags & RES_NEGATIVE      ) toc_strlcat( buf, " negative", sizeof(buf) );
    if (res_flags & RES_HOLY          ) toc_strlcat( buf, " holy", sizeof(buf) );
    if (res_flags & RES_ENERGY        ) toc_strlcat( buf, " energy", sizeof(buf) );
    if (res_flags & RES_MENTAL        ) toc_strlcat( buf, " mental", sizeof(buf) );
    if (res_flags & RES_DISEASE       ) toc_strlcat( buf, " disease", sizeof(buf) );
    if (res_flags & RES_DROWNING      ) toc_strlcat( buf, " drowning", sizeof(buf) );
    if (res_flags & RES_LIGHT         ) toc_strlcat( buf, " light", sizeof(buf) );
    if (res_flags & RES_WIND          ) toc_strlcat( buf, " wind", sizeof(buf) );
    if (res_flags & RES_FLAGS2        ) toc_strlcat( buf, " flags2", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";

}
char *vuln_bit_name(long vuln_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (vuln_flags & VULN_MAGIC          ) toc_strlcat( buf, " magic", sizeof(buf) );
    if (vuln_flags & VULN_WEAPON         ) toc_strlcat( buf, " weapon", sizeof(buf) );
    if (vuln_flags & VULN_BASH           ) toc_strlcat( buf, " bash", sizeof(buf) );
    if (vuln_flags & VULN_PIERCE         ) toc_strlcat( buf, " pierce", sizeof(buf) );
    if (vuln_flags & VULN_SLASH          ) toc_strlcat( buf, " slash", sizeof(buf) );
    if (vuln_flags & VULN_FIRE           ) toc_strlcat( buf, " fire", sizeof(buf) );
    if (vuln_flags & VULN_COLD           ) toc_strlcat( buf, " cold", sizeof(buf) );
    if (vuln_flags & VULN_LIGHTNING      ) toc_strlcat( buf, " lightning", sizeof(buf) );
    if (vuln_flags & VULN_ACID           ) toc_strlcat( buf, " acid", sizeof(buf) );
    if (vuln_flags & VULN_POISON         ) toc_strlcat( buf, " poison", sizeof(buf) );
    if (vuln_flags & VULN_NEGATIVE       ) toc_strlcat( buf, " negative", sizeof(buf) );
    if (vuln_flags & VULN_HOLY           ) toc_strlcat( buf, " holy", sizeof(buf) );
    if (vuln_flags & VULN_ENERGY         ) toc_strlcat( buf, " energy", sizeof(buf) );
    if (vuln_flags & VULN_MENTAL         ) toc_strlcat( buf, " mental", sizeof(buf) );
    if (vuln_flags & VULN_DISEASE        ) toc_strlcat( buf, " disease", sizeof(buf) );
    if (vuln_flags & VULN_DROWNING       ) toc_strlcat( buf, " drowning", sizeof(buf) );
    if (vuln_flags & VULN_LIGHT          ) toc_strlcat( buf, " light", sizeof(buf) );
    if (vuln_flags & VULN_WIND           ) toc_strlcat( buf, " wind", sizeof(buf) );
    if (vuln_flags & VULN_IRON           ) toc_strlcat( buf, " iron", sizeof(buf) );
    if (vuln_flags & VULN_WOOD           ) toc_strlcat( buf, " wood", sizeof(buf) );
    if (vuln_flags & VULN_SILVER         ) toc_strlcat( buf, " silver", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";

}

char *imm2_bit_name(long imm_flags)
{
    static char buf[512];

    UNUSED_PARAM(imm_flags);
    buf[0] = '\0';

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}
char *wear_bit_name(int wear_flags)
{
    static char buf[512];

    buf [0] = '\0';
    if (wear_flags & ITEM_TAKE          ) toc_strlcat( buf, " take", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_FINGER   ) toc_strlcat( buf, " finger", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_NECK     ) toc_strlcat( buf, " neck", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_BODY     ) toc_strlcat( buf, " torso", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_HEAD     ) toc_strlcat( buf, " head", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_LEGS     ) toc_strlcat( buf, " legs", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_FEET     ) toc_strlcat( buf, " feet", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_HANDS    ) toc_strlcat( buf, " hands", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_ARMS     ) toc_strlcat( buf, " arms", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_SHIELD   ) toc_strlcat( buf, " shield", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_ABOUT    ) toc_strlcat( buf, " body", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_WAIST    ) toc_strlcat( buf, " waist", sizeof(buf) );
    if (wear_flags & ITEM_WEAR_WRIST    ) toc_strlcat( buf, " wrist", sizeof(buf) );
    if (wear_flags & ITEM_WIELD         ) toc_strlcat( buf, " wield", sizeof(buf) );
    if (wear_flags & ITEM_HOLD          ) toc_strlcat( buf, " hold", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *form_bit_name(long form_flags)
{
    static char buf[512];

    buf[0] = '\0';
    if (form_flags & FORM_POISON        ) toc_strlcat( buf, " poison", sizeof(buf) );
    else if (form_flags & FORM_EDIBLE   ) toc_strlcat( buf, " edible", sizeof(buf) );
    if (form_flags & FORM_MAGICAL       ) toc_strlcat( buf, " magical", sizeof(buf) );
    if (form_flags & FORM_INSTANT_DECAY ) toc_strlcat( buf, " instant_rot", sizeof(buf) );
    if (form_flags & FORM_OTHER         ) toc_strlcat( buf, " other", sizeof(buf) );
    if (form_flags & FORM_ANIMAL        ) toc_strlcat( buf, " animal", sizeof(buf) );
    if (form_flags & FORM_SENTIENT      ) toc_strlcat( buf, " sentient", sizeof(buf) );
    if (form_flags & FORM_UNDEAD        ) toc_strlcat( buf, " undead", sizeof(buf) );
    if (form_flags & FORM_CONSTRUCT     ) toc_strlcat( buf, " construct", sizeof(buf) );
    if (form_flags & FORM_MIST          ) toc_strlcat( buf, " mist", sizeof(buf) );
    if (form_flags & FORM_INTANGIBLE    ) toc_strlcat( buf, " intangible", sizeof(buf) );
    if (form_flags & FORM_BIPED         ) toc_strlcat( buf, " biped", sizeof(buf) );
    if (form_flags & FORM_CENTAUR       ) toc_strlcat( buf, " centaur", sizeof(buf) );
    if (form_flags & FORM_INSECT        ) toc_strlcat( buf, " insect", sizeof(buf) );
    if (form_flags & FORM_SPIDER        ) toc_strlcat( buf, " spider", sizeof(buf) );
    if (form_flags & FORM_CRUSTACEAN    ) toc_strlcat( buf, " crustacean", sizeof(buf) );
    if (form_flags & FORM_WORM          ) toc_strlcat( buf, " worm", sizeof(buf) );
    if (form_flags & FORM_BLOB          ) toc_strlcat( buf, " blob", sizeof(buf) );
    if (form_flags & FORM_MAMMAL        ) toc_strlcat( buf, " mammal", sizeof(buf) );
    if (form_flags & FORM_BIRD          ) toc_strlcat( buf, " bird", sizeof(buf) );
    if (form_flags & FORM_REPTILE       ) toc_strlcat( buf, " reptile", sizeof(buf) );
    if (form_flags & FORM_SNAKE         ) toc_strlcat( buf, " snake", sizeof(buf) );
    if (form_flags & FORM_DRAGON        ) toc_strlcat( buf, " dragon", sizeof(buf) );
    if (form_flags & FORM_AMPHIBIAN     ) toc_strlcat( buf, " amphibian", sizeof(buf) );
    if (form_flags & FORM_FISH          ) toc_strlcat( buf, " fish", sizeof(buf) );
    if (form_flags & FORM_COLD_BLOOD    ) toc_strlcat( buf, " cold_blooded", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *part_bit_name(long part_flags)
{
    static char buf[512];

    buf[0] = '\0';
    if (part_flags & PART_HEAD          ) toc_strlcat( buf, " head", sizeof(buf) );
    if (part_flags & PART_ARMS          ) toc_strlcat( buf, " arms", sizeof(buf) );
    if (part_flags & PART_LEGS          ) toc_strlcat( buf, " legs", sizeof(buf) );
    if (part_flags & PART_HEART         ) toc_strlcat( buf, " heart", sizeof(buf) );
    if (part_flags & PART_BRAINS        ) toc_strlcat( buf, " brains", sizeof(buf) );
    if (part_flags & PART_GUTS          ) toc_strlcat( buf, " guts", sizeof(buf) );
    if (part_flags & PART_HANDS         ) toc_strlcat( buf, " hands", sizeof(buf) );
    if (part_flags & PART_FEET          ) toc_strlcat( buf, " feet", sizeof(buf) );
    if (part_flags & PART_FINGERS       ) toc_strlcat( buf, " fingers", sizeof(buf) );
    if (part_flags & PART_EAR           ) toc_strlcat( buf, " ears", sizeof(buf) );
    if (part_flags & PART_EYE           ) toc_strlcat( buf, " eyes", sizeof(buf) );
    if (part_flags & PART_LONG_TONGUE   ) toc_strlcat( buf, " long_tongue", sizeof(buf) );
    if (part_flags & PART_EYESTALKS     ) toc_strlcat( buf, " eyestalks", sizeof(buf) );
    if (part_flags & PART_TENTACLES     ) toc_strlcat( buf, " tentacles", sizeof(buf) );
    if (part_flags & PART_FINS          ) toc_strlcat( buf, " fins", sizeof(buf) );
    if (part_flags & PART_WINGS         ) toc_strlcat( buf, " wings", sizeof(buf) );
    if (part_flags & PART_TAIL          ) toc_strlcat( buf, " tail", sizeof(buf) );
    if (part_flags & PART_CLAWS         ) toc_strlcat( buf, " claws", sizeof(buf) );
    if (part_flags & PART_FANGS         ) toc_strlcat( buf, " fangs", sizeof(buf) );
    if (part_flags & PART_HORNS         ) toc_strlcat( buf, " horns", sizeof(buf) );
    if (part_flags & PART_SCALES        ) toc_strlcat( buf, " scales", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *weapon_bit_name(int weapon_flags)
{
    static char buf[512];

    buf[0] = '\0';
    if (weapon_flags & WEAPON_FLAMING   ) toc_strlcat( buf, " flaming", sizeof(buf) );
    if (weapon_flags & WEAPON_FROST     ) toc_strlcat( buf, " frost", sizeof(buf) );
    if (weapon_flags & WEAPON_VAMPIRIC  ) toc_strlcat( buf, " vampiric", sizeof(buf) );
    if (weapon_flags & WEAPON_SHARP     ) toc_strlcat( buf, " sharp", sizeof(buf) );
    if (weapon_flags & WEAPON_VORPAL    ) toc_strlcat( buf, " vorpal", sizeof(buf) );
    if (weapon_flags & WEAPON_TWO_HANDS ) toc_strlcat( buf, " two-handed", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *off_bit_name(long off_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (off_flags & OFF_AREA_ATTACK       ) toc_strlcat( buf, " area attack", sizeof(buf) );
    if (off_flags & OFF_BACKSTAB          ) toc_strlcat( buf, " backstab", sizeof(buf) );
    if (off_flags & OFF_BASH              ) toc_strlcat( buf, " bash", sizeof(buf) );
    if (off_flags & OFF_BERSERK           ) toc_strlcat( buf, " berserk", sizeof(buf) );
    if (off_flags & OFF_DISARM            ) toc_strlcat( buf, " disarm", sizeof(buf) );
    if (off_flags & OFF_DODGE             ) toc_strlcat( buf, " dodge", sizeof(buf) );
    if (off_flags & OFF_FADE              ) toc_strlcat( buf, " fade", sizeof(buf) );
    if (off_flags & OFF_FAST              ) toc_strlcat( buf, " fast", sizeof(buf) );
    if (off_flags & OFF_KICK              ) toc_strlcat( buf, " kick", sizeof(buf) );
    if (off_flags & OFF_KICK_DIRT         ) toc_strlcat( buf, " kick_dirt", sizeof(buf) );
    if (off_flags & OFF_PARRY             ) toc_strlcat( buf, " parry", sizeof(buf) );
    if (off_flags & OFF_RESCUE            ) toc_strlcat( buf, " rescue", sizeof(buf) );
    if (off_flags & OFF_TAIL              ) toc_strlcat( buf, " tail", sizeof(buf) );
    if (off_flags & OFF_TRIP              ) toc_strlcat( buf, " trip", sizeof(buf) );
    if (off_flags & OFF_CRUSH             ) toc_strlcat( buf, " crush", sizeof(buf) );
    if (off_flags & ASSIST_ALL            ) toc_strlcat( buf, " assist_all", sizeof(buf) );
    if (off_flags & ASSIST_ALIGN          ) toc_strlcat( buf, " assist_align", sizeof(buf) );
    if (off_flags & ASSIST_RACE           ) toc_strlcat( buf, " assist_race", sizeof(buf) );
    if (off_flags & ASSIST_PLAYERS        ) toc_strlcat( buf, " assist_players", sizeof(buf) );
    if (off_flags & ASSIST_GUARD          ) toc_strlcat( buf, " assist_guard", sizeof(buf) );
    if (off_flags & ASSIST_VNUM           ) toc_strlcat( buf, " assist_vnum", sizeof(buf) );
    if (off_flags & OFF_SUMMONER          ) toc_strlcat( buf, " off_summoner", sizeof(buf) );
    if (off_flags & NEEDS_MASTER          ) toc_strlcat( buf, " needs_master", sizeof(buf) );
    if (off_flags & OFF_ATTACK_DOOR_OPENER) toc_strlcat( buf, " attack_opener", sizeof(buf) );
    if (off_flags & OFF_FLAGS2            ) toc_strlcat( buf, " off_flags2", sizeof(buf) );
    return ( buf[0] != '\0' ) ? buf+1 : "none";
}


char *off2_bit_name(long off_flags)
{
    static char buf[512];

    buf[0] = '\0';

    if (off_flags & OFF2_HUNTER        ) toc_strlcat( buf, " hunter", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

char *room_flag_name(int room_flag)
{
    static char buf[512];

    buf[0] = '\0';
    if (room_flag & ROOM_DARK         ) toc_strlcat( buf, " Dark", sizeof(buf) );
    if (room_flag & ROOM_JAIL         ) toc_strlcat( buf, " Jail", sizeof(buf) );
    if (room_flag & ROOM_NO_MOB       ) toc_strlcat( buf, " No_Mob", sizeof(buf) );
    if (room_flag & ROOM_INDOORS      ) toc_strlcat( buf, " Indoors", sizeof(buf) );
    if (room_flag & ROOM_RIVER        ) toc_strlcat( buf, " River", sizeof(buf) );
    if (room_flag & ROOM_TELEPORT     ) toc_strlcat( buf, " Tport", sizeof(buf) );
    if (room_flag & ROOM_CULT_ENTRANCE) toc_strlcat( buf, " Cult_ent", sizeof(buf) );
    if (room_flag & ROOM_AFFECTED_BY  ) toc_strlcat( buf, " affected_by", sizeof(buf) );
    if (room_flag & ROOM_DT	      ) toc_strlcat( buf, " death_trap", sizeof(buf) );
    if (room_flag & ROOM_PRIVATE      ) toc_strlcat( buf, " Private", sizeof(buf) );
    if (room_flag & ROOM_SAFE         ) toc_strlcat( buf, " Safe", sizeof(buf) );
    if (room_flag & ROOM_SOLITARY     ) toc_strlcat( buf, " Solitary", sizeof(buf) );
    if (room_flag & ROOM_PET_SHOP     ) toc_strlcat( buf, " Pet_Shop", sizeof(buf) );
    if (room_flag & ROOM_NO_RECALL    ) toc_strlcat( buf, " No_Recall", sizeof(buf) );
    if (room_flag & ROOM_IMP_ONLY     ) toc_strlcat( buf, " Imp_Only", sizeof(buf) );
    if (room_flag & ROOM_GODS_ONLY    ) toc_strlcat( buf, " Gods_Only", sizeof(buf) );
    if (room_flag & ROOM_HEROES_ONLY  ) toc_strlcat( buf, " Heroes_Only", sizeof(buf) );
    if (room_flag & ROOM_NEWBIES_ONLY ) toc_strlcat( buf, " Newbies_Only", sizeof(buf) );
    if (room_flag & ROOM_LAW          ) toc_strlcat( buf, " Law", sizeof(buf) );
    if (room_flag & ROOM_HP_REGEN     ) toc_strlcat( buf, " Hp_Regen", sizeof(buf) );
    if (room_flag & ROOM_MANA_REGEN   ) toc_strlcat( buf, " Mana_Regen", sizeof(buf) );
    if (room_flag & ROOM_ARENA        ) toc_strlcat( buf, " Arena", sizeof(buf) );
    if (room_flag & ROOM_CASTLE_JOIN  ) toc_strlcat( buf, " Castle_Join", sizeof(buf) );
    if (room_flag & ROOM_SILENT       ) toc_strlcat( buf, " Silent", sizeof(buf) );
    if (room_flag & ROOM_BFS_MARK     ) toc_strlcat( buf, " hunt mark", sizeof(buf) );
    if (room_flag & ROOM_FLAGS2       ) toc_strlcat( buf, " Flags2", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";


}

char *room_flag2_name(int room_flag)
{
    static char buf[512];

    if (room_flag & ROOM2_NO_TPORT         ) toc_strlcat( buf, " No_Tport", sizeof(buf) );

    return ( buf[0] != '\0' ) ? buf+1 : "none";
}

/*
 * Give an affect to a room.
 */
void affect_to_room( ROOM_INDEX_DATA *pRoom, ROOM_AFF_DATA *raf )
{
    raf->next   = room_aff_list;
    room_aff_list   = raf;

    SET_BIT(pRoom->room_flags, ROOM_AFFECTED_BY);
    return;
}

/*
 * Remove an affect from a room.
 */
void remove_room_affect( ROOM_INDEX_DATA *pRoom, ROOM_AFF_DATA *raf )
{
  ROOM_AFF_DATA *aff, *affNext, *affPrev;

    if ( pRoom->affected == NULL )
    {
	bug( "Room_Aff_remove: no affect.", 0 );
	return;
    }

    if( raf->room != pRoom)
    {
      bug("Room_Aff_Remove: Affect does not go with room.",0 );
      return;
    }


    for ( aff = room_aff_list, affPrev = NULL; aff != NULL; aff = affNext )
    {

       affNext = aff->next;
       if( aff == raf )
          break;
       affPrev = aff;
    }

    if( aff != NULL)
    {
	if(affPrev == NULL)
	   room_aff_list = affNext;
	else
	   affPrev->next = affNext;
    }

    REMOVE_BIT(pRoom->room_flags, ROOM_AFFECTED_BY);
    free_mem( pRoom->affected, sizeof(*raf) );

    pRoom->affected = NULL;
    return;
}

void room_affect(CHAR_DATA *ch, ROOM_INDEX_DATA *pRoom, int door)
{
    ROOM_AFF_DATA *raf;
    AFFECT_DATA   af;
    int dam;

    raf = pRoom->affected;

    if(raf->aff_exit != 10 && raf->aff_exit != door)
      return;

/*    if(raf->dam_dice == 0 &&
      (raf->bitvector == NULL || raf->bitvector2 == NULL) )*/

/* Above if statement commented out because it gives 2 pointer errors
   and replaced with the if statement shown below - Rico */

      if (raf->dam_dice == 0 &&
      (!raf->bitvector || !raf->bitvector2))
      return;

    switch(raf->type)
    {
      case STINKING_CLOUD:

	 if(ch->level < raf->level || !saves_spell(raf->level, ch) )
	 {
	   af.type        = gsn_poison;
	   af.level       = raf->level;
	   af.duration    = raf->duration;
	   af.location    = raf->location;
	   af.modifier    = raf->modifier;
	   af.bitvector   = raf->bitvector;
	   af.bitvector2  = raf->bitvector2;
	   affect_to_char(ch,&af);

	   send_to_char("Poison gas! <cough> <cough> <choke>\n\r",ch);
	   dam = dice(raf->dam_dice,raf->dam_number);
	   damage( ch, ch, dam, gsn_poison, DAM_POISON );
	 }
	 else
	 {
	   send_to_char("You choke and gag on noxious fumes that fill the air.\n\r",ch);
	 }
      break;
      case VOLCANIC:
	   send_to_char("You sweat profusely, and your skin burns.\n\r",ch);
	   act("$n sweats profusely, and $m skin is very red.",ch,NULL,NULL,TO_ROOM);
	   dam = dice(raf->dam_dice,raf->dam_number);
	   damage(ch, ch, dam, TYPE_UNDEFINED, DAM_FIRE);
      break;
      case SHOCKER:
	   send_to_char("A metal rod pops out of the floor.\n\r",ch);
	   send_to_char("BBBBBZZZZZZZZZTTTTTTTTTTTT!!!!!!!!",ch);
	   act("$n's hair stands straight up!.",ch,NULL,NULL,TO_ROOM);
	   dam = dice(raf->dam_dice,raf->dam_number);
	   damage(ch, ch, dam, TYPE_UNDEFINED, DAM_LIGHTNING);
      break;
    }


   return;

}

void extract_room( ROOM_INDEX_DATA *pRoom )
{
    ROOM_INDEX_DATA *pRoomIndex, *pPrev, *pNext;
    int iHash, door;

    free_string( pRoom->name);
    free_string( pRoom->description);
    for ( door = 0; door <= 9; door++ )
	pRoom->exit[door] = NULL;

    iHash		     = pRoom->vnum % MAX_KEY_HASH;
    for( pRoomIndex = room_index_hash[iHash], pPrev = NULL;
         pRoomIndex != NULL;
         pRoomIndex = pNext )
    {
       pNext = pRoomIndex->next;

       if( pRoomIndex == pRoom )
	  break;

       pPrev = pRoomIndex;
    }

    if ( pRoomIndex == NULL )
      return;

    if ( pPrev == NULL )
       room_index_hash[iHash] = pRoomIndex->next;
    else
      pPrev->next = pRoomIndex->next;

    pRoom->next        	     = room_index_free;
    room_index_free          = pRoom->next;
    free_mem( pRoom, sizeof(*pRoom) );

    return;
}

void do_flip( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 1 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_move( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 2 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_pull( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

/*   if(obj->value[0] == 10)
   { do_manipulate(ch,obj->name); return; };
*/
   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };


   if( obj->value[0] == 3 )
/*     do_manipulate(ch, obj->name);*/
       do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_push( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 4 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_turn( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 5 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_climb( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 6 || obj->value[0] == 7)
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_crawl( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 8 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void do_jump( CHAR_DATA *ch, char *argument )
{
   OBJ_DATA *obj = NULL;
   char arg[MAX_INPUT_LENGTH];

   one_argument( argument, arg );

   if( ( obj = get_obj_here( ch, arg) ) == NULL )
   { act("I see no $T here.",ch, NULL, arg, TO_CHAR); return;}

   if( obj->item_type != ITEM_MANIPULATION )
   { act("You can't do that to the $T.",ch, NULL, arg, TO_CHAR); return;}

   if(obj->value[0] == 10)
   { do_manipulate(ch,arg); return; };

   if( obj->value[0] == 9 )
     do_manipulate(ch, arg);
   else
     send_to_char("Nothing seems to happen. Try something else?\n\r",ch);

   return;
}

void show_obj_condition(OBJ_DATA *obj, CHAR_DATA *ch)
{
    char buf[MAX_STRING_LENGTH];

    switch(obj->condition/10)
    {
        case 10: snprintf(buf, sizeof(buf), "The %s is in perfect condition.\n\r",
                         obj->short_descr);	break;
        case  9:
        case  8: snprintf(buf, sizeof(buf), "The %s is in great condition.\n\r",
                         obj->short_descr);	break;
        case  7:
        case  6: snprintf(buf, sizeof(buf), "The %s is in good condition.\n\r",
                         obj->short_descr);	break;
        case  5:
        case  4:
        case  3: snprintf(buf, sizeof(buf), "The %s is in average condition.\n\r",
                         obj->short_descr);	break;
        case  2:
        case  1: snprintf(buf, sizeof(buf), "The %s is in bad condition.\n\r",
                         obj->short_descr);	break;
        case  0: snprintf(buf, sizeof(buf), "The %s is falling apart.\n\r",
                         obj->short_descr);	break;
        default: snprintf(buf, sizeof(buf), "The %s is in perfect condition.\n\r",
                         obj->short_descr);	break;
    }

    send_to_char(buf,ch);
    return;
}