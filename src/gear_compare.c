#include <math.h>
#include <stdio.h>
#include <string.h>
#include "merc.h"
#include "interp.h"
#include "magic.h"

enum gear_focus
{
    GEAR_FOCUS_INVALID = -1,
    GEAR_FOCUS_OVERALL,
    GEAR_FOCUS_DAMAGE,
    GEAR_FOCUS_SPELLS,
    GEAR_FOCUS_DEFENSE,
    GEAR_FOCUS_LEVELING,
    GEAR_FOCUS_UTILITY
};

typedef struct gear_profile GEAR_PROFILE;
typedef struct gear_loadout GEAR_LOADOUT;
typedef struct gear_metrics GEAR_METRICS;

struct gear_profile
{
    double melee_weight;
    double spell_weight;
    double defense_weight;
    double leveling_weight;
    double utility_weight;
    int known_spells;
    int offensive_spells;
    int support_spells;
    int primary_stat;
    const char *style;
};

struct gear_loadout
{
    int raw_stat[MAX_STATS];
    int max_hit;
    int max_mana;
    int max_move;
    int hitroll;
    int damroll;
    int armor[4];
    int saving_throw;
    int exp_bonus;
    long affected_by;
    long affected_by2;
    long imm_flags;
    OBJ_DATA *main_weapon;
    OBJ_DATA *offhand;
};

struct gear_metrics
{
    double melee;
    double spells;
    double survival;
    double leveling;
    double utility;
    double overall;
    int stat[MAX_STATS];
    int hitroll;
    int damroll;
    int max_hit;
    int max_mana;
    int max_move;
    int average_ac;
    int saving_throw;
    int exp_bonus;
    int weapon_skill;
};

static int gear_skill( CHAR_DATA *ch, int sn )
{
    if ( sn < 0 || sn >= MAX_SKILL )
        return 0;
    return get_skill( ch, sn );
}

static int gear_focus_lookup( const char *name )
{
    if ( !str_cmp( name, "overall" ) || !str_cmp( name, "all" ) )
        return GEAR_FOCUS_OVERALL;
    if ( !str_cmp( name, "damage" ) || !str_cmp( name, "melee" )
        || !str_cmp( name, "weapon" ) )
        return GEAR_FOCUS_DAMAGE;
    if ( !str_cmp( name, "spell" ) || !str_cmp( name, "spells" )
        || !str_cmp( name, "casting" ) )
        return GEAR_FOCUS_SPELLS;
    if ( !str_cmp( name, "defense" ) || !str_cmp( name, "survival" )
        || !str_cmp( name, "tank" ) )
        return GEAR_FOCUS_DEFENSE;
    if ( !str_cmp( name, "level" ) || !str_cmp( name, "leveling" )
        || !str_cmp( name, "experience" ) )
        return GEAR_FOCUS_LEVELING;
    if ( !str_cmp( name, "utility" ) || !str_cmp( name, "mobility" )
        || !str_cmp( name, "travel" ) )
        return GEAR_FOCUS_UTILITY;
    return GEAR_FOCUS_INVALID;
}

static const char *gear_focus_name( int focus )
{
    switch ( focus )
    {
    case GEAR_FOCUS_DAMAGE:   return "weapon damage";
    case GEAR_FOCUS_SPELLS:   return "spellcasting";
    case GEAR_FOCUS_DEFENSE:  return "survivability";
    case GEAR_FOCUS_LEVELING: return "leveling";
    case GEAR_FOCUS_UTILITY:  return "utility";
    default:                  return "your inferred playstyle";
    }
}

static void gear_add_role_weights( GEAR_PROFILE *profile, int role, double scale )
{
    switch ( role )
    {
    case CLASS_MAGE:
        profile->melee_weight += 0.4 * scale;
        profile->spell_weight += 2.4 * scale;
        profile->utility_weight += 0.8 * scale;
        break;
    case CLASS_CLERIC:
        profile->melee_weight += 0.8 * scale;
        profile->spell_weight += 1.9 * scale;
        profile->defense_weight += 0.7 * scale;
        break;
    case CLASS_THIEF:
        profile->melee_weight += 1.9 * scale;
        profile->defense_weight += 0.4 * scale;
        profile->utility_weight += 1.2 * scale;
        break;
    case CLASS_WARRIOR:
        profile->melee_weight += 2.3 * scale;
        profile->defense_weight += 1.2 * scale;
        break;
    case CLASS_MONK:
        profile->melee_weight += 1.7 * scale;
        profile->spell_weight += 0.7 * scale;
        profile->defense_weight += 0.9 * scale;
        profile->utility_weight += 0.4 * scale;
        break;
    case CLASS_NECRO:
        profile->melee_weight += 0.5 * scale;
        profile->spell_weight += 2.3 * scale;
        profile->defense_weight += 0.3 * scale;
        profile->utility_weight += 0.6 * scale;
        break;
    default:
        break;
    }
}

static void gear_build_profile( CHAR_DATA *ch, GEAR_PROFILE *profile )
{
    int sn;
    int learned;
    int guild;
    int martial_signal;
    int defense_signal;
    int utility_signal;

    memset( profile, 0, sizeof( *profile ) );
    profile->melee_weight = 0.4;
    profile->spell_weight = 0.15;
    profile->defense_weight = 0.7;
    profile->leveling_weight = 1.5;
    profile->utility_weight = 0.35;
    profile->primary_stat = class_table[ch->class].attr_prime;

    gear_add_role_weights( profile, ch->class, 1.0 );
    guild = ch->pcdata->guild;
    if ( guild >= 0 && guild < MAX_CLASS && guild != ch->class )
        gear_add_role_weights( profile, guild, 0.55 );

    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        learned = ch->pcdata->learned[sn];
        if ( learned < 2 || skill_table[sn].spell_fun == NULL
            || skill_table[sn].spell_fun == spell_null )
            continue;

        profile->known_spells++;
        if ( skill_table[sn].target == TAR_CHAR_OFFENSIVE )
            profile->offensive_spells++;
        else
            profile->support_spells++;
    }

    if ( profile->known_spells > 0 )
    {
        profile->spell_weight += UMIN( 1.4,
            profile->known_spells * 0.035 );
        if ( profile->offensive_spells > profile->support_spells )
            profile->spell_weight += 0.2;
    }

    martial_signal = gear_skill( ch, gsn_second_attack )
        + gear_skill( ch, gsn_third_attack )
        + gear_skill( ch, gsn_enhanced_damage )
        + gear_skill( ch, gsn_dual_wield )
        + gear_skill( ch, gsn_backstab )
        + gear_skill( ch, gsn_smite )
        + gear_skill( ch, gsn_archery )
        + gear_skill( ch, gsn_fists_of_fury );
    profile->melee_weight += martial_signal / 650.0;

    defense_signal = gear_skill( ch, gsn_dodge )
        + gear_skill( ch, gsn_parry )
        + gear_skill( ch, gsn_shield_block )
        + gear_skill( ch, gsn_iron_skin );
    profile->defense_weight += defense_signal / 450.0;

    utility_signal = gear_skill( ch, gsn_stealth )
        + gear_skill( ch, gsn_tracking )
        + gear_skill( ch, gsn_danger_sense )
        + gear_skill( ch, gsn_haggle )
        + gear_skill( ch, gsn_lore );
    profile->utility_weight += utility_signal / 700.0;

    if ( gear_skill( ch, gsn_dual_wield ) >= 50 )
        profile->style = "dual-wield skirmisher";
    else if ( gear_skill( ch, gsn_backstab ) >= 50 )
        profile->style = "burst weapon specialist";
    else if ( profile->spell_weight > profile->melee_weight * 1.25 )
        profile->style = profile->support_spells > profile->offensive_spells
            ? "support caster" : "offensive caster";
    else if ( profile->melee_weight > profile->spell_weight * 1.6 )
        profile->style = profile->defense_weight > 1.8
            ? "front-line weapon fighter" : "weapon specialist";
    else
        profile->style = "hybrid combatant";
}

static int gear_slot_wear_flag( int slot )
{
    switch ( slot )
    {
    case WEAR_LIGHT:    return 0;
    case WEAR_FINGER_L:
    case WEAR_FINGER_R: return ITEM_WEAR_FINGER;
    case WEAR_NECK_1:
    case WEAR_NECK_2:   return ITEM_WEAR_NECK;
    case WEAR_BODY:     return ITEM_WEAR_BODY;
    case WEAR_HEAD:     return ITEM_WEAR_HEAD;
    case WEAR_LEGS:     return ITEM_WEAR_LEGS;
    case WEAR_FEET:     return ITEM_WEAR_FEET;
    case WEAR_HANDS:    return ITEM_WEAR_HANDS;
    case WEAR_ARMS:     return ITEM_WEAR_ARMS;
    case WEAR_SHIELD:   return ITEM_WEAR_SHIELD;
    case WEAR_ABOUT:    return ITEM_WEAR_ABOUT;
    case WEAR_WAIST:    return ITEM_WEAR_WAIST;
    case WEAR_WRIST_L:
    case WEAR_WRIST_R:  return ITEM_WEAR_WRIST;
    case WEAR_WIELD:    return ITEM_WIELD;
    case WEAR_HOLD:     return ITEM_HOLD;
    default:            return 0;
    }
}

static const char *gear_slot_name( int slot )
{
    switch ( slot )
    {
    case WEAR_LIGHT:    return "light";
    case WEAR_FINGER_L:
    case WEAR_FINGER_R: return "finger";
    case WEAR_NECK_1:
    case WEAR_NECK_2:   return "neck";
    case WEAR_BODY:     return "body";
    case WEAR_HEAD:     return "head";
    case WEAR_LEGS:     return "legs";
    case WEAR_FEET:     return "feet";
    case WEAR_HANDS:    return "hands";
    case WEAR_ARMS:     return "arms";
    case WEAR_SHIELD:   return "off hand";
    case WEAR_ABOUT:    return "about body";
    case WEAR_WAIST:    return "waist";
    case WEAR_WRIST_L:
    case WEAR_WRIST_R:  return "wrist";
    case WEAR_WIELD:    return "main hand";
    case WEAR_HOLD:     return "held";
    default:            return "unknown slot";
    }
}

static bool gear_item_supports_slot( OBJ_DATA *obj, int slot )
{
    int wear_flag;

    if ( obj == NULL )
        return false;
    if ( slot == WEAR_LIGHT )
        return obj->item_type == ITEM_LIGHT;
    if ( slot == WEAR_SHIELD && obj->item_type == ITEM_WEAPON )
        return CAN_WEAR( obj, ITEM_WIELD );
    wear_flag = gear_slot_wear_flag( slot );
    return wear_flag != 0 && CAN_WEAR( obj, wear_flag );
}

static int gear_choose_slot( CHAR_DATA *ch, OBJ_DATA *obj1, OBJ_DATA *obj2 )
{
    static const int slots[] = {
        WEAR_WIELD, WEAR_SHIELD, WEAR_HOLD, WEAR_LIGHT, WEAR_BODY, WEAR_HEAD,
        WEAR_LEGS, WEAR_FEET, WEAR_HANDS, WEAR_ARMS, WEAR_ABOUT,
        WEAR_WAIST, WEAR_FINGER_L, WEAR_FINGER_R, WEAR_NECK_1,
        WEAR_NECK_2, WEAR_WRIST_L, WEAR_WRIST_R
    };
    int i;

    if ( obj1->wear_loc != WEAR_NONE
        && gear_item_supports_slot( obj2, obj1->wear_loc ) )
        return obj1->wear_loc;
    if ( obj2->wear_loc != WEAR_NONE
        && gear_item_supports_slot( obj1, obj2->wear_loc ) )
        return obj2->wear_loc;

    if ( obj1->item_type == ITEM_WEAPON && obj2->item_type == ITEM_WEAPON )
    {
        if ( get_eq_char( ch, WEAR_WIELD ) != NULL )
            return WEAR_WIELD;
        return WEAR_WIELD;
    }

    for ( i = 0; i < (int)(sizeof( slots ) / sizeof( slots[0] )); i++ )
        if ( get_eq_char( ch, slots[i] ) != NULL
            && gear_item_supports_slot( obj1, slots[i] )
            && gear_item_supports_slot( obj2, slots[i] ) )
            return slots[i];

    for ( i = 0; i < (int)(sizeof( slots ) / sizeof( slots[0] )); i++ )
        if ( gear_item_supports_slot( obj1, slots[i] )
            && gear_item_supports_slot( obj2, slots[i] ) )
            return slots[i];

    return WEAR_NONE;
}

static OBJ_DATA *gear_find_equipped_match( CHAR_DATA *ch, OBJ_DATA *candidate )
{
    static const int slots[] = {
        WEAR_WIELD, WEAR_SHIELD, WEAR_HOLD, WEAR_LIGHT, WEAR_BODY, WEAR_HEAD,
        WEAR_LEGS, WEAR_FEET, WEAR_HANDS, WEAR_ARMS, WEAR_ABOUT,
        WEAR_WAIST, WEAR_FINGER_L, WEAR_FINGER_R, WEAR_NECK_1,
        WEAR_NECK_2, WEAR_WRIST_L, WEAR_WRIST_R
    };
    OBJ_DATA *worn;
    int i;

    for ( i = 0; i < (int)(sizeof( slots ) / sizeof( slots[0] )); i++ )
    {
        worn = get_eq_char( ch, slots[i] );
        if ( worn != NULL && worn != candidate
            && gear_item_supports_slot( candidate, slots[i] ) )
        {
            if ( candidate->item_type == ITEM_WEAPON
                && worn->item_type != ITEM_WEAPON )
                continue;
            return worn;
        }
    }
    return NULL;
}

static int gear_stat_cap( CHAR_DATA *ch, int stat )
{
    int maximum;

    if ( ch->level > LEVEL_IMMORTAL )
        return MAX_STAT;
    maximum = pc_race_table[ch->race].max_stats[stat] + 4;
    if ( class_table[ch->class].attr_prime == stat )
        maximum += 2;
    if ( ch->race == race_lookup( "human" ) )
        maximum += 1;
    return UMIN( maximum, MAX_STAT );
}

static int gear_loadout_stat( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                              int stat )
{
    return URANGE( 3, loadout->raw_stat[stat], gear_stat_cap( ch, stat ) );
}

static void gear_loadout_from_char( CHAR_DATA *ch, GEAR_LOADOUT *loadout )
{
    int i;

    memset( loadout, 0, sizeof( *loadout ) );
    for ( i = 0; i < MAX_STATS; i++ )
        loadout->raw_stat[i] = ch->perm_stat[i] + ch->mod_stat[i];
    loadout->max_hit = ch->max_hit;
    loadout->max_mana = ch->max_mana;
    loadout->max_move = ch->max_move;
    loadout->hitroll = ch->hitroll;
    loadout->damroll = ch->damroll;
    for ( i = 0; i < 4; i++ )
        loadout->armor[i] = ch->armor[i];
    loadout->saving_throw = ch->saving_throw;
    loadout->exp_bonus = ch->pcdata->exp_bonus;
    loadout->affected_by = ch->affected_by;
    loadout->affected_by2 = ch->affected_by2;
    loadout->imm_flags = ch->imm_flags;
    loadout->main_weapon = get_eq_char( ch, WEAR_WIELD );
    loadout->offhand = get_eq_char( ch, WEAR_SHIELD );
}

static void gear_apply_affect( GEAR_LOADOUT *loadout, AFFECT_DATA *paf,
                               int sign )
{
    int modifier;
    int i;

    modifier = paf->modifier * sign;
    if ( paf->bitvector != 0 )
    {
        if ( sign > 0 )
            SET_BIT( loadout->affected_by, paf->bitvector );
        else
            REMOVE_BIT( loadout->affected_by, paf->bitvector );
    }
    else if ( paf->bitvector2 != 0 )
    {
        if ( sign > 0 )
            SET_BIT( loadout->affected_by2, paf->bitvector2 );
        else
            REMOVE_BIT( loadout->affected_by2, paf->bitvector2 );
    }

    switch ( paf->location )
    {
    case APPLY_STR: loadout->raw_stat[STAT_STR] += modifier; break;
    case APPLY_DEX: loadout->raw_stat[STAT_DEX] += modifier; break;
    case APPLY_INT: loadout->raw_stat[STAT_INT] += modifier; break;
    case APPLY_WIS: loadout->raw_stat[STAT_WIS] += modifier; break;
    case APPLY_CON: loadout->raw_stat[STAT_CON] += modifier; break;
    case APPLY_MANA: loadout->max_mana += modifier; break;
    case APPLY_HIT: loadout->max_hit += modifier; break;
    case APPLY_MOVE: loadout->max_move += modifier; break;
    case APPLY_EXP: loadout->exp_bonus += modifier; break;
    case APPLY_AC:
        for ( i = 0; i < 4; i++ )
            loadout->armor[i] += modifier;
        break;
    case APPLY_HITROLL: loadout->hitroll += modifier; break;
    case APPLY_DAMROLL: loadout->damroll += modifier; break;
    case APPLY_SAVING_PARA:
    case APPLY_SAVING_ROD:
    case APPLY_SAVING_PETRI:
    case APPLY_SAVING_BREATH:
    case APPLY_SAVING_SPELL:
        loadout->saving_throw += modifier;
        break;
    case APPLY_IMMUNITY:
        if ( sign > 0 )
            SET_BIT( loadout->imm_flags,
                     (long)(unsigned short)paf->modifier );
        else
            REMOVE_BIT( loadout->imm_flags,
                        (long)(unsigned short)paf->modifier );
        break;
    default:
        break;
    }
}

static void gear_apply_item( GEAR_LOADOUT *loadout, OBJ_DATA *obj,
                             int slot, int sign )
{
    AFFECT_DATA *paf;
    int i;

    if ( obj == NULL )
        return;

    for ( i = 0; i < 4; i++ )
        loadout->armor[i] -= sign * apply_ac( obj, slot, i );

    if ( obj->pIndexData != NULL )
        for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
            gear_apply_affect( loadout, paf, sign );
    for ( paf = obj->affected; paf != NULL; paf = paf->next )
        gear_apply_affect( loadout, paf, sign );

    if ( IS_OBJ_STAT( obj, ITEM_ADD_AFFECT ) )
    {
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_INVIS ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_INVISIBLE );
            else REMOVE_BIT( loadout->affected_by, AFF_INVISIBLE );
        }
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_DETECT_INVIS ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_DETECT_INVIS );
            else REMOVE_BIT( loadout->affected_by, AFF_DETECT_INVIS );
        }
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_FLY ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_FLYING );
            else REMOVE_BIT( loadout->affected_by, AFF_FLYING );
        }
    }

    if ( slot == WEAR_WIELD )
    {
        if ( sign > 0 ) loadout->main_weapon = obj;
        else if ( loadout->main_weapon == obj ) loadout->main_weapon = NULL;
    }
    else if ( slot == WEAR_SHIELD )
    {
        if ( sign > 0 ) loadout->offhand = obj;
        else if ( loadout->offhand == obj ) loadout->offhand = NULL;
    }
}

/* Rebuild flag contributions without losing duplicate bonuses from gear. */
static void gear_collect_item_flags( OBJ_DATA *obj, long *affected_by,
                                     long *affected_by2, long *imm_flags )
{
    AFFECT_DATA *paf;

    if ( obj == NULL )
        return;

    if ( obj->pIndexData != NULL )
        for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
        {
            if ( paf->bitvector != 0 )
                SET_BIT( *affected_by, (long)(unsigned int)paf->bitvector );
            else if ( paf->bitvector2 != 0 )
                SET_BIT( *affected_by2, (long)(unsigned int)paf->bitvector2 );
            if ( paf->location == APPLY_IMMUNITY )
                SET_BIT( *imm_flags, (long)(unsigned short)paf->modifier );
        }

    for ( paf = obj->affected; paf != NULL; paf = paf->next )
    {
        if ( paf->bitvector != 0 )
            SET_BIT( *affected_by, (long)(unsigned int)paf->bitvector );
        else if ( paf->bitvector2 != 0 )
            SET_BIT( *affected_by2, (long)(unsigned int)paf->bitvector2 );
        if ( paf->location == APPLY_IMMUNITY )
            SET_BIT( *imm_flags, (long)(unsigned short)paf->modifier );
    }

    if ( IS_OBJ_STAT( obj, ITEM_ADD_AFFECT ) )
    {
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_INVIS ) )
            SET_BIT( *affected_by, AFF_INVISIBLE );
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_DETECT_INVIS ) )
            SET_BIT( *affected_by, AFF_DETECT_INVIS );
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_FLY ) )
            SET_BIT( *affected_by, AFF_FLYING );
    }
}

static void gear_project_equipped_flags( CHAR_DATA *ch, OBJ_DATA *exclude1,
                                         OBJ_DATA *exclude2,
                                         GEAR_LOADOUT *loadout )
{
    OBJ_DATA *obj;
    long all_affected_by = 0;
    long all_affected_by2 = 0;
    long all_imm_flags = 0;
    long remaining_affected_by = 0;
    long remaining_affected_by2 = 0;
    long remaining_imm_flags = 0;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->wear_loc != WEAR_NONE )
            gear_collect_item_flags( obj, &all_affected_by,
                                      &all_affected_by2, &all_imm_flags );

    /* Remove item-provided bits from the live aggregate, retaining spell,
     * race, and class effects that are not supplied by equipped items. */
    loadout->affected_by = ch->affected_by & ~all_affected_by;
    loadout->affected_by2 = ch->affected_by2 & ~all_affected_by2;
    loadout->imm_flags = ch->imm_flags & ~all_imm_flags;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->wear_loc != WEAR_NONE && obj != exclude1
            && obj != exclude2 )
            gear_collect_item_flags( obj, &remaining_affected_by,
                                      &remaining_affected_by2,
                                      &remaining_imm_flags );

    loadout->affected_by |= remaining_affected_by;
    loadout->affected_by2 |= remaining_affected_by2;
    loadout->imm_flags |= remaining_imm_flags;
}

static int gear_weapon_sn( OBJ_DATA *weapon )
{
    if ( weapon == NULL || weapon->item_type != ITEM_WEAPON )
        return gsn_hand_to_hand;
    switch ( weapon->value[0] )
    {
    case WEAPON_SWORD:   return gsn_sword;
    case WEAPON_DAGGER:  return gsn_dagger;
    case WEAPON_SPEAR:   return gsn_spear;
    case WEAPON_MACE:    return gsn_mace;
    case WEAPON_AXE:     return gsn_axe;
    case WEAPON_FLAIL:   return gsn_flail;
    case WEAPON_WHIP:    return gsn_whip;
    case WEAPON_POLEARM: return gsn_polearm;
    case WEAPON_BOW:     return gsn_archery;
    default:             return -1;
    }
}

static double gear_hit_chance( int threshold )
{
    int roll;
    int hits = 0;

    for ( roll = 0; roll < 20; roll++ )
        if ( roll != 0 && (roll == 19 || roll >= threshold) )
            hits++;
    return hits / 20.0;
}

static int gear_standard_victim_ac( int level )
{
    int victim_ac;

    victim_ac = (100 - 6 * level) / 10;
    if ( victim_ac < -17 )
        victim_ac = (victim_ac + 17) / 5 - 17;
    return victim_ac;
}

static double gear_smite_bonus( CHAR_DATA *ch, OBJ_DATA *weapon, int skill )
{
    double weapon_dice;
    double divisor;
    int tiers;

    if ( weapon == NULL || weapon->item_type != ITEM_WEAPON )
        return 0.0;

    switch ( weapon->value[0] )
    {
    case WEAPON_SWORD:
        divisor = 125.0;
        break;
    case WEAPON_AXE:
    case WEAPON_FLAIL:
    case WEAPON_MACE:
        divisor = 150.0;
        break;
    default:
        return 0.0;
    }

    tiers = 1 + (ch->level > 30) + (ch->level > 50);
    weapon_dice = weapon->value[1] * (weapon->value[2] + 1) / 2.0;
    return weapon_dice * skill / divisor * tiers;
}

static double gear_fists_burst( CHAR_DATA *ch, int skill )
{
    double chance;
    double expected_hits;
    double attempts;

    if ( skill < 2 )
        return 0.0;

    chance = UMIN( 100, skill + 60 ) / 100.0;
    attempts = 3.5 + (ch->level >= 35) + (ch->level >= 45);
    expected_hits = chance * attempts;
    return expected_hits * ch->level * 1.5;
}

static double gear_weapon_hit_damage( CHAR_DATA *ch,
                                      const GEAR_LOADOUT *loadout,
                                      OBJ_DATA *weapon, int skill,
                                      bool main_hand )
{
    double damage;
    double minimum;
    double maximum;
    double enhanced;
    int damroll;

    if ( weapon != NULL && weapon->item_type == ITEM_WEAPON )
    {
        damage = weapon->value[1] * (weapon->value[2] + 1) / 2.0;
        damage *= skill / 100.0;
        if ( main_hand && loadout->offhand == NULL )
            damage *= 1.05;
    }
    else
    {
        if ( ch->class == CLASS_MONK )
        {
            minimum = 1 + ch->level + 4 * skill / 100.0;
            maximum = 2 * ch->level * skill / 100.0;
        }
        else
        {
            minimum = 1 + 4 * skill / 100.0;
            maximum = 2 * ch->level * skill / 300.0;
        }
        damage = maximum <= minimum
            ? minimum : (minimum + maximum) / 2.0;
    }

    damroll = loadout->damroll
        + str_app[gear_loadout_stat( ch, loadout, STAT_STR )].todam;
    damage += damroll * UMIN( 100, skill ) / 100.0;

    enhanced = gear_skill( ch, gsn_enhanced_damage );
    damage *= 1.0 + enhanced * (enhanced + 1) / 40000.0;
    return UMAX( 1.0, damage );
}

static double gear_melee_output( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                                 int *main_skill_result )
{
    OBJ_DATA *main_weapon;
    OBJ_DATA *off_weapon;
    double main_damage;
    double main_accuracy;
    double main_attacks;
    double output;
    double off_damage;
    double off_chance;
    double opener;
    double enhanced_multiplier;
    double base_damage;
    double normal_round;
    double special_round;
    double smite_bonus;
    double smite_chance;
    double special_accuracy;
    double fists_burst;
    int main_sn;
    int off_sn;
    int main_skill;
    int off_skill;
    int hitroll;
    int threshold;
    int backstab;
    int smite;
    int thac0;
    int victim_ac;
    int multiplier;

    main_weapon = loadout->main_weapon;
    if ( main_weapon != NULL && main_weapon->item_type != ITEM_WEAPON )
        main_weapon = NULL;
    off_weapon = loadout->offhand;
    if ( off_weapon != NULL && off_weapon->item_type != ITEM_WEAPON )
        off_weapon = NULL;

    main_sn = gear_weapon_sn( main_weapon );
    main_skill = get_weapon_skill( ch, main_sn );
    *main_skill_result = main_skill;
    hitroll = loadout->hitroll
        + str_app[gear_loadout_stat( ch, loadout, STAT_STR )].tohit;
    thac0 = interpolate( ch->level, class_table[ch->class].thac0_00,
                         class_table[ch->class].thac0_32 );
    victim_ac = gear_standard_victim_ac( ch->level );
    threshold = thac0 - victim_ac - hitroll * main_skill / 100
        + 5 * (100 - main_skill) / 100;
    main_accuracy = gear_hit_chance( threshold );
    main_damage = gear_weapon_hit_damage( ch, loadout, main_weapon,
                                          main_skill, true );

    main_attacks = 2.0
        + gear_skill( ch, gsn_second_attack ) / 200.0
        + gear_skill( ch, gsn_third_attack ) / 400.0;
    if ( IS_SET( loadout->affected_by, AFF_HASTE ) )
        main_attacks += 1.0;
    if ( IS_IMMORTAL( ch ) )
        main_attacks += 3.0;
    normal_round = main_damage * main_accuracy * main_attacks;
    output = normal_round;

    if ( off_weapon != NULL )
    {
        off_sn = gear_weapon_sn( off_weapon );
        off_skill = get_weapon_skill( ch, off_sn );
        off_chance = (gear_skill( ch, gsn_dual_wield ) + off_skill) / 500.0;
        off_chance = UMIN( 1.0, off_chance );
        off_damage = gear_weapon_hit_damage( ch, loadout, off_weapon,
                                             off_skill, false );
        /* one_hit deliberately skips the normal hit roll for dual attacks. */
        output += off_damage * off_chance;
    }

    enhanced_multiplier = 1.0 + gear_skill( ch, gsn_enhanced_damage )
        * (gear_skill( ch, gsn_enhanced_damage ) + 1) / 40000.0;
    base_damage = main_damage / enhanced_multiplier;
    backstab = gear_skill( ch, gsn_backstab );
    if ( backstab > 0 && main_weapon != NULL )
    {
        multiplier = main_weapon->value[0] == WEAPON_DAGGER
            ? 2 + ch->level / 10 : 2 + ch->level / 15;
        special_accuracy = gear_hit_chance(
            threshold - 10 * (100 - backstab) );
        opener = 2.0 * base_damage * multiplier * special_accuracy
            * backstab / 100.0;
        output += UMAX( 0.0, opener - 2.0 * main_damage * main_accuracy )
            / 5.0;
    }

    smite = gear_skill( ch, gsn_smite );
    smite_chance = 2 * smite / 3.0;
    if ( gear_loadout_stat( ch, loadout, STAT_STR ) > 22 )
        smite_chance += 10.0;
    if ( gear_loadout_stat( ch, loadout, STAT_DEX ) > 24 )
        smite_chance += 10.0;
    smite_bonus = gear_smite_bonus( ch, main_weapon, main_skill );
    if ( smite_chance > 5.0 && smite_bonus > 0.0 )
    {
        smite_chance = UMIN( 100.0, smite_chance ) / 100.0;
        special_accuracy = gear_hit_chance(
            threshold - 10 * (100 - smite) );
        special_round = (main_damage + smite_bonus) * special_accuracy
            * main_attacks * smite_chance;
        output += UMAX( 0.0, special_round - normal_round ) / 5.0;
    }

    if ( main_weapon == NULL && loadout->max_mana >= 30
        && loadout->max_move >= 15 )
    {
        fists_burst = gear_fists_burst( ch,
            gear_skill( ch, gsn_fists_of_fury ) );
        output += UMAX( 0.0, fists_burst - normal_round ) / 5.0;
    }

    return UMAX( 0.1, output );
}

static int gear_count_bits( long value )
{
    int count = 0;

    while ( value != 0 )
    {
        count += (int)(value & 1L);
        value = (long)((unsigned long)value >> 1);
    }
    return count;
}

static double gear_skill_proc_multiplier( int skill )
{
    skill = URANGE( 0, skill, 100 );
    return 1.0 + skill * (skill - 1) / 20000.0;
}

static void gear_calculate_metrics( CHAR_DATA *ch,
                                    const GEAR_PROFILE *profile,
                                    const GEAR_LOADOUT *loadout,
                                    GEAR_METRICS *metrics )
{
    double mana_regen;
    double hp_regen;
    double move_regen;
    double incoming_chance;
    double save_chance;
    double avoidance;
    double damage_factor;
    double raw_damage;
    double reduced_damage;
    double parry_chance;
    double dodge_chance;
    double block_chance;
    double combat_score;
    double focus_total;
    double learning_score;
    double exp_multiplier;
    int intelligence;
    int wisdom;
    int constitution;
    int dexterity;
    int effective_ac;
    int victim_ac;
    int attacker_skill;
    int attacker_stat;
    int attacker_hitroll;
    int attacker_thac0;
    int threshold;
    int i;

    memset( metrics, 0, sizeof( *metrics ) );
    for ( i = 0; i < MAX_STATS; i++ )
        metrics->stat[i] = gear_loadout_stat( ch, loadout, i );

    intelligence = metrics->stat[STAT_INT];
    wisdom = metrics->stat[STAT_WIS];
    constitution = metrics->stat[STAT_CON];
    dexterity = metrics->stat[STAT_DEX];
    metrics->hitroll = loadout->hitroll
        + str_app[metrics->stat[STAT_STR]].tohit;
    metrics->damroll = loadout->damroll
        + str_app[metrics->stat[STAT_STR]].todam;
    metrics->max_hit = UMAX( 1, loadout->max_hit );
    metrics->max_mana = UMAX( 0, loadout->max_mana );
    metrics->max_move = UMAX( 0, loadout->max_move );
    metrics->saving_throw = loadout->saving_throw;
    metrics->exp_bonus = UMAX( 0, loadout->exp_bonus );

    effective_ac = 0;
    for ( i = 0; i < 4; i++ )
        effective_ac += loadout->armor[i] + dex_app[dexterity].defensive;
    metrics->average_ac = effective_ac / 4;

    metrics->melee = gear_melee_output( ch, loadout,
                                         &metrics->weapon_skill );

    mana_regen = (wisdom + intelligence + ch->level) * 0.75;
    mana_regen *= gear_skill_proc_multiplier(
        gear_skill( ch, gsn_meditation ) );
    metrics->spells = UMAX( 1.0,
        metrics->max_mana + mana_regen * 8.0
        + int_app[intelligence].learn * 1.5
        + wis_app[wisdom].practice * 20.0 );

    victim_ac = metrics->average_ac / 10;
    if ( victim_ac < -17 )
        victim_ac = (victim_ac + 17) / 5 - 17;
    attacker_skill = URANGE( 0, 40 + 5 * ch->level / 2, 100 );
    attacker_stat = UMIN( MAX_STAT, 11 + ch->level / 4 );
    attacker_hitroll = ch->level / 2 + str_app[attacker_stat].tohit;
    attacker_thac0 = interpolate( ch->level, 20, -4 );
    threshold = attacker_thac0 - victim_ac
        - attacker_hitroll * attacker_skill / 100
        + 5 * (100 - attacker_skill) / 100;
    incoming_chance = gear_hit_chance( threshold );

    parry_chance = 0.0;
    if ( loadout->main_weapon != NULL || ch->class == CLASS_MONK )
        parry_chance = UMIN( 95, gear_skill( ch, gsn_parry ) / 2 ) / 100.0;
    dodge_chance = UMIN( 95, gear_skill( ch, gsn_dodge ) / 2 ) / 100.0;
    block_chance = loadout->offhand == NULL ? 0.0
        : UMIN( 95, gear_skill( ch, gsn_shield_block ) / 2 ) / 100.0;
    avoidance = (1.0 - parry_chance) * (1.0 - dodge_chance)
        * (1.0 - block_chance);
    if ( ch->race == 4 )
        avoidance *= 0.87;
    incoming_chance = UMAX( 0.01, incoming_chance * avoidance );

    raw_damage = UMAX( 5.0, (double)ch->level );
    reduced_damage = raw_damage + (-100 + metrics->average_ac) / 12.0;
    reduced_damage = URANGE( 1.0, reduced_damage, raw_damage );
    damage_factor = (raw_damage + reduced_damage) / (2.0 * raw_damage);
    if ( IS_SET( loadout->affected_by, AFF_SANCTUARY ) )
        damage_factor *= 0.5;
    if ( IS_SET( loadout->affected_by2, AFF2_DIVINE_PROT ) )
        damage_factor *= IS_SET( loadout->affected_by, AFF_SANCTUARY )
            ? 0.9375 : 0.75;
    save_chance = URANGE( 5, 50 - metrics->saving_throw * 5, 95 ) / 100.0;
    hp_regen = UMAX( 6.0, constitution + ch->level / 2.0 )
        + class_table[ch->class].hp_max;
    hp_regen *= gear_skill_proc_multiplier(
        gear_skill( ch, gsn_fast_healing ) );
    metrics->survival = (metrics->max_hit + hp_regen * 6.0)
        / (incoming_chance * damage_factor)
        * (1.0 + save_chance * 0.35)
        * (1.0 + gear_count_bits( loadout->imm_flags ) * 0.04);

    move_regen = UMAX( 25.0, (double)ch->level ) + dexterity / 2.0;
    metrics->utility = 100.0 + metrics->max_move * 0.7
        + move_regen * 4.0 + dexterity * 3.0 + constitution * 2.0
        + gear_count_bits( loadout->imm_flags ) * 25.0;
    if ( IS_SET( loadout->affected_by, AFF_FLYING ) )
        metrics->utility += 35.0;
    if ( IS_SET( loadout->affected_by, AFF_INVISIBLE ) )
        metrics->utility += 25.0;
    if ( IS_SET( loadout->affected_by, AFF_DETECT_INVIS ) )
        metrics->utility += 15.0;

    focus_total = profile->melee_weight + profile->spell_weight;
    combat_score = (metrics->melee * profile->melee_weight
        + metrics->spells / 15.0 * profile->spell_weight)
        / UMAX( 0.1, focus_total );
    learning_score = int_app[intelligence].learn * 0.5
        + wis_app[wisdom].practice * 12.0;
    exp_multiplier = 1.0 + metrics->exp_bonus / 100.0;
    metrics->leveling = (100.0 + combat_score * 2.0
        + metrics->survival / 45.0 + metrics->utility / 8.0
        + mana_regen * profile->spell_weight + hp_regen
        + learning_score) * exp_multiplier;
}

static double gear_metric_index( double value, double reference )
{
    return 100.0 * value / UMAX( 0.1, reference );
}

static void gear_calculate_overall( const GEAR_PROFILE *profile,
                                    const GEAR_METRICS *base,
                                    GEAR_METRICS *metrics )
{
    double total_weight;

    total_weight = profile->melee_weight + profile->spell_weight
        + profile->defense_weight + profile->leveling_weight
        + profile->utility_weight;
    metrics->overall = (
        gear_metric_index( metrics->melee, base->melee )
            * profile->melee_weight
        + gear_metric_index( metrics->spells, base->spells )
            * profile->spell_weight
        + gear_metric_index( metrics->survival, base->survival )
            * profile->defense_weight
        + gear_metric_index( metrics->leveling, base->leveling )
            * profile->leveling_weight
        + gear_metric_index( metrics->utility, base->utility )
            * profile->utility_weight) / UMAX( 0.1, total_weight );
}

static double gear_focus_value( const GEAR_METRICS *metrics, int focus )
{
    switch ( focus )
    {
    case GEAR_FOCUS_DAMAGE:   return metrics->melee;
    case GEAR_FOCUS_SPELLS:   return metrics->spells;
    case GEAR_FOCUS_DEFENSE:  return metrics->survival;
    case GEAR_FOCUS_LEVELING: return metrics->leveling;
    case GEAR_FOCUS_UTILITY:  return metrics->utility;
    default:                  return metrics->overall;
    }
}

static bool gear_race_allowed( CHAR_DATA *ch, OBJ_DATA *obj )
{
    if ( !IS_OBJ_STAT( obj, ITEM_RACE_RESTRICTED ) )
        return true;
    if ( IS_OBJ_STAT2( obj, ITEM2_HUMAN_ONLY ) && ch->race != 1 )
        return false;
    if ( IS_OBJ_STAT2( obj, ITEM2_ELF_ONLY ) && ch->race != 2 )
        return false;
    if ( IS_OBJ_STAT2( obj, ITEM2_DWARF_ONLY ) && ch->race != 3 )
        return false;
    if ( IS_OBJ_STAT2( obj, ITEM2_HALFLING_ONLY ) && ch->race != 4 )
        return false;
    if ( IS_OBJ_STAT2( obj, ITEM2_SAURIAN_ONLY ) && ch->race != 5 )
        return false;
    return true;
}

static bool gear_offhand_power_allowed( OBJ_DATA *obj )
{
    AFFECT_DATA *paf;

    if ( obj->enchanted )
        return false;
    for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
        if ( (paf->location == APPLY_HITROLL
              || paf->location == APPLY_DAMROLL)
            && paf->modifier > 5 )
            return false;
    return true;
}

static bool gear_item_usable( CHAR_DATA *ch, OBJ_DATA *obj, int slot,
                              char *reason, size_t reason_size )
{
    OBJ_DATA *blocker;

    reason[0] = '\0';
    if ( obj->level > ch->level )
    {
        snprintf( reason, reason_size, "requires level %d", obj->level );
        return false;
    }
    if ( IS_OBJ_STAT( obj, ITEM_HEATED ) )
    {
        snprintf( reason, reason_size, "is still heated" );
        return false;
    }
    if ( IS_OBJ_STAT( obj, ITEM_DAMAGED ) )
    {
        snprintf( reason, reason_size, "must be repaired" );
        return false;
    }
    if ( (IS_OBJ_STAT( obj, ITEM_ANTI_EVIL ) && IS_EVIL( ch ))
        || (IS_OBJ_STAT( obj, ITEM_ANTI_GOOD ) && IS_GOOD( ch ))
        || (IS_OBJ_STAT( obj, ITEM_ANTI_NEUTRAL ) && IS_NEUTRAL( ch )) )
    {
        snprintf( reason, reason_size, "rejects your alignment" );
        return false;
    }
    if ( !gear_race_allowed( ch, obj ) )
    {
        snprintf( reason, reason_size, "is restricted to another race" );
        return false;
    }
    if ( obj->wear_loc == slot )
        return true;
    if ( obj->item_type == ITEM_WEAPON
        && get_obj_weight( obj ) > str_app[get_curr_stat( ch, STAT_STR )].wield )
    {
        snprintf( reason, reason_size, "is too heavy to wield" );
        return false;
    }
    if ( slot == WEAR_SHIELD && obj->item_type == ITEM_WEAPON
        && IS_WEAPON_STAT( obj, WEAPON_TWO_HANDS ) )
    {
        snprintf( reason, reason_size, "cannot be used off hand" );
        return false;
    }
    if ( slot == WEAR_SHIELD && obj->item_type == ITEM_WEAPON )
    {
        blocker = get_eq_char( ch, WEAR_WIELD );
        if ( gear_skill( ch, gsn_dual_wield ) < 1 )
        {
            snprintf( reason, reason_size, "requires the dual wield skill" );
            return false;
        }
        if ( blocker == NULL )
        {
            snprintf( reason, reason_size, "requires a main-hand weapon" );
            return false;
        }
        if ( IS_WEAPON_STAT( blocker, WEAPON_TWO_HANDS ) )
        {
            snprintf( reason, reason_size, "conflicts with your two-handed weapon" );
            return false;
        }
        if ( !IS_IMMORTAL( ch ) && !gear_offhand_power_allowed( obj ) )
        {
            snprintf( reason, reason_size, "is too powerful to dual wield" );
            return false;
        }
    }
    if ( slot == WEAR_SHIELD && obj->item_type != ITEM_WEAPON )
    {
        blocker = get_eq_char( ch, WEAR_WIELD );
        if ( blocker != NULL && ch->size < SIZE_LARGE
            && IS_WEAPON_STAT( blocker, WEAPON_TWO_HANDS ) )
        {
            snprintf( reason, reason_size, "conflicts with your two-handed weapon" );
            return false;
        }
    }
    if ( slot == WEAR_WIELD && obj->item_type == ITEM_WEAPON
        && IS_WEAPON_STAT( obj, WEAPON_TWO_HANDS ) )
    {
        blocker = get_eq_char( ch, WEAR_SHIELD );
        if ( blocker != NULL && blocker != obj
            && !IS_IMMORTAL( ch )
            && IS_OBJ_STAT( blocker, ITEM_NOREMOVE ) )
        {
            snprintf( reason, reason_size,
                      "cannot free both hands from the off-hand item" );
            return false;
        }
    }

    blocker = get_eq_char( ch, slot );
    if ( blocker != NULL && blocker != obj
        && IS_OBJ_STAT( blocker, ITEM_NOREMOVE ) )
    {
        snprintf( reason, reason_size, "the equipped item cannot be removed" );
        return false;
    }
    return true;
}

static void gear_remove_once( GEAR_LOADOUT *loadout, OBJ_DATA *obj,
                              OBJ_DATA **removed, int *removed_count )
{
    int i;

    if ( obj == NULL || obj->wear_loc == WEAR_NONE )
        return;
    for ( i = 0; i < *removed_count; i++ )
        if ( removed[i] == obj )
            return;
    gear_apply_item( loadout, obj, obj->wear_loc, -1 );
    removed[*removed_count] = obj;
    (*removed_count)++;
}

static void gear_build_base_loadout( CHAR_DATA *ch, OBJ_DATA *obj1,
                                     OBJ_DATA *obj2, int slot,
                                     GEAR_LOADOUT *base )
{
    OBJ_DATA *removed[3];
    OBJ_DATA *equipped;
    int removed_count = 0;

    gear_loadout_from_char( ch, base );
    gear_remove_once( base, obj1, removed, &removed_count );
    gear_remove_once( base, obj2, removed, &removed_count );
    if ( removed_count == 0 )
    {
        equipped = get_eq_char( ch, slot );
        gear_remove_once( base, equipped, removed, &removed_count );
    }
    gear_project_equipped_flags( ch, obj1, obj2, base );
}

static void gear_build_candidate_loadout( const GEAR_LOADOUT *base,
                                          OBJ_DATA *candidate, int slot,
                                          GEAR_LOADOUT *result )
{
    *result = *base;
    if ( slot == WEAR_WIELD && candidate->item_type == ITEM_WEAPON
        && IS_WEAPON_STAT( candidate, WEAPON_TWO_HANDS )
        && result->offhand != NULL )
        gear_apply_item( result, result->offhand, WEAR_SHIELD, -1 );
    gear_apply_item( result, candidate, slot, 1 );
}

static void gear_send_metric( CHAR_DATA *ch, const char *label,
                              double value1, double value2,
                              const char *unit, bool selected )
{
    char buf[MAX_STRING_LENGTH];
    double percent;

    if ( fabs( value1 - value2 ) <= UMAX( 0.01, value2 * 0.005 ) )
    {
        snprintf( buf, sizeof( buf ), " %c %-15s even (%.1f vs %.1f %s)\n\r",
                  selected ? '*' : ' ', label, value1, value2, unit );
    }
    else if ( value1 > value2 )
    {
        percent = (value1 / UMAX( 0.1, value2 ) - 1.0) * 100.0;
        snprintf( buf, sizeof( buf ),
                  " %c %-15s A +%.1f%% (%.1f vs %.1f %s)\n\r",
                  selected ? '*' : ' ', label, UMIN( 999.9, percent ),
                  value1, value2, unit );
    }
    else
    {
        percent = (value2 / UMAX( 0.1, value1 ) - 1.0) * 100.0;
        snprintf( buf, sizeof( buf ),
                  " %c %-15s B +%.1f%% (%.1f vs %.1f %s)\n\r",
                  selected ? '*' : ' ', label, UMIN( 999.9, percent ),
                  value1, value2, unit );
    }
    send_to_char( buf, ch );
}

static void gear_send_loadout_facts( CHAR_DATA *ch,
                                     const GEAR_PROFILE *profile,
                                     const GEAR_METRICS *a,
                                     const GEAR_METRICS *b )
{
    static const char *stat_names[MAX_STATS] = {
        "STR", "INT", "WIS", "DEX", "CON"
    };
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof( buf ),
              "  A loadout: hit %+d dam %+d | hp %d mana %d move %d\n\r",
              a->hitroll, a->damroll, a->max_hit, a->max_mana, a->max_move );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "             avg AC %d save %+d XP %+d%% weapon skill %d%%\n\r",
              a->average_ac, a->saving_throw, a->exp_bonus, a->weapon_skill );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "  B loadout: hit %+d dam %+d | hp %d mana %d move %d\n\r",
              b->hitroll, b->damroll, b->max_hit, b->max_mana, b->max_move );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "             avg AC %d save %+d XP %+d%% weapon skill %d%%\n\r",
              b->average_ac, b->saving_throw, b->exp_bonus, b->weapon_skill );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ), "  Primary %s: A %d, B %d\n\r",
              stat_names[profile->primary_stat],
              a->stat[profile->primary_stat], b->stat[profile->primary_stat] );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "  A stats: STR %d INT %d WIS %d DEX %d CON %d\n\r",
              a->stat[STAT_STR], a->stat[STAT_INT], a->stat[STAT_WIS],
              a->stat[STAT_DEX], a->stat[STAT_CON] );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "  B stats: STR %d INT %d WIS %d DEX %d CON %d\n\r",
              b->stat[STAT_STR], b->stat[STAT_INT], b->stat[STAT_WIS],
              b->stat[STAT_DEX], b->stat[STAT_CON] );
    send_to_char( buf, ch );
}

static void gear_send_profile( CHAR_DATA *ch, const GEAR_PROFILE *profile )
{
    char buf[MAX_STRING_LENGTH];
    double total;

    total = profile->melee_weight + profile->spell_weight
        + profile->defense_weight + profile->leveling_weight
        + profile->utility_weight;
    snprintf( buf, sizeof( buf ),
              "Gear profile: level %d %s / %s guild, %s\n\r",
              ch->level, class_table[ch->class].name,
              get_guildname( ch->pcdata->guild ), profile->style );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "Priorities: damage %.0f%% spells %.0f%% defense %.0f%% leveling %.0f%% utility %.0f%%\n\r",
              100.0 * profile->melee_weight / total,
              100.0 * profile->spell_weight / total,
              100.0 * profile->defense_weight / total,
              100.0 * profile->leveling_weight / total,
              100.0 * profile->utility_weight / total );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "Signals: %d learned spells (%d offensive, %d support) and your trained combat skills.\n\r",
              profile->known_spells, profile->offensive_spells,
              profile->support_spells );
    send_to_char( buf, ch );
}

static void gear_send_recommendation( CHAR_DATA *ch, OBJ_DATA *obj1,
                                      OBJ_DATA *obj2, double value1,
                                      double value2, bool usable1,
                                      bool usable2, int focus )
{
    char buf[MAX_STRING_LENGTH];
    double percent;

    if ( usable1 && !usable2 )
    {
        snprintf( buf, sizeof( buf ),
                  "Recommendation: A is the usable choice right now; B's result is theoretical.\n\r" );
        send_to_char( buf, ch );
        return;
    }
    if ( usable2 && !usable1 )
    {
        snprintf( buf, sizeof( buf ),
                  "Recommendation: B is the usable choice right now; A's result is theoretical.\n\r" );
        send_to_char( buf, ch );
        return;
    }
    if ( !usable1 && !usable2 )
    {
        send_to_char( "Recommendation: neither item is usable by you right now.\n\r", ch );
        return;
    }

    if ( fabs( value1 - value2 ) <= UMAX( 0.01, value2 * 0.005 ) )
    {
        snprintf( buf, sizeof( buf ),
                  "Recommendation: the items are effectively tied for %s.\n\r",
                  gear_focus_name( focus ) );
    }
    else if ( value1 > value2 )
    {
        percent = (value1 / UMAX( 0.1, value2 ) - 1.0) * 100.0;
        snprintf( buf, sizeof( buf ),
                  "Recommendation: A (%s) is %.1f%% better for %s.\n\r",
                  obj1->short_descr, UMIN( 999.9, percent ),
                  gear_focus_name( focus ) );
    }
    else
    {
        percent = (value2 / UMAX( 0.1, value1 ) - 1.0) * 100.0;
        snprintf( buf, sizeof( buf ),
                  "Recommendation: B (%s) is %.1f%% better for %s.\n\r",
                  obj2->short_descr, UMIN( 999.9, percent ),
                  gear_focus_name( focus ) );
    }
    send_to_char( buf, ch );
}

static void gear_send_usage( CHAR_DATA *ch )
{
    send_to_char( "Syntax: compare <item> [item]\n\r", ch );
    send_to_char( "        compare <focus> <item> [item]\n\r", ch );
    send_to_char( "        compare profile\n\r", ch );
    send_to_char( "Focus: overall, damage, spells, defense, leveling, utility\n\r", ch );
}

void do_compare( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    char reason1[128];
    char reason2[128];
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *obj1;
    OBJ_DATA *obj2;
    GEAR_PROFILE profile;
    GEAR_LOADOUT base;
    GEAR_LOADOUT loadout1;
    GEAR_LOADOUT loadout2;
    GEAR_METRICS base_metrics;
    GEAR_METRICS metrics1;
    GEAR_METRICS metrics2;
    int focus;
    int parsed_focus;
    int slot;
    bool usable1;
    bool usable2;
    double focused_value1;
    double focused_value2;

    if ( IS_NPC( ch ) )
    {
        send_to_char( "Only players have a class-aware gear profile.\n\r", ch );
        return;
    }

    argument = one_argument( argument, arg1 );
    if ( arg1[0] == '\0' || !str_cmp( arg1, "help" ) )
    {
        gear_send_usage( ch );
        return;
    }

    if ( !str_cmp( arg1, "profile" ) )
    {
        gear_build_profile( ch, &profile );
        gear_send_profile( ch, &profile );
        return;
    }

    focus = GEAR_FOCUS_OVERALL;
    parsed_focus = gear_focus_lookup( arg1 );
    if ( parsed_focus != GEAR_FOCUS_INVALID )
    {
        focus = parsed_focus;
        argument = one_argument( argument, arg1 );
        if ( arg1[0] == '\0' )
        {
            gear_send_usage( ch );
            return;
        }
    }
    one_argument( argument, arg2 );

    obj1 = get_obj_carry( ch, arg1 );
    if ( obj1 == NULL )
        obj1 = get_obj_wear( ch, arg1 );
    if ( obj1 == NULL )
    {
        send_to_char( "You do not have the first item.\n\r", ch );
        return;
    }

    if ( arg2[0] != '\0' )
    {
        obj2 = get_obj_carry( ch, arg2 );
        if ( obj2 == NULL )
            obj2 = get_obj_wear( ch, arg2 );
        if ( obj2 == NULL )
        {
            send_to_char( "You do not have the second item.\n\r", ch );
            return;
        }
    }
    else
    {
        obj2 = gear_find_equipped_match( ch, obj1 );
        if ( obj2 == NULL )
        {
            send_to_char( "You aren't wearing anything in a comparable slot.\n\r", ch );
            return;
        }
    }

    if ( obj1 == obj2 )
    {
        act( "You compare $p to itself. It is exactly the same item.",
             ch, obj1, NULL, TO_CHAR );
        return;
    }

    if ( obj1->wear_loc != WEAR_NONE && obj2->wear_loc != WEAR_NONE
        && obj1->wear_loc != obj2->wear_loc )
    {
        send_to_char( "Those items are already worn in different slots; remove one before comparing them.\n\r",
                      ch );
        return;
    }

    slot = gear_choose_slot( ch, obj1, obj2 );
    if ( slot == WEAR_NONE )
    {
        send_to_char( "Those items do not compete for the same equipment slot.\n\r", ch );
        return;
    }

    gear_build_profile( ch, &profile );
    gear_build_base_loadout( ch, obj1, obj2, slot, &base );
    gear_build_candidate_loadout( &base, obj1, slot, &loadout1 );
    gear_build_candidate_loadout( &base, obj2, slot, &loadout2 );
    gear_calculate_metrics( ch, &profile, &base, &base_metrics );
    gear_calculate_metrics( ch, &profile, &loadout1, &metrics1 );
    gear_calculate_metrics( ch, &profile, &loadout2, &metrics2 );
    gear_calculate_overall( &profile, &base_metrics, &metrics1 );
    gear_calculate_overall( &profile, &base_metrics, &metrics2 );

    usable1 = gear_item_usable( ch, obj1, slot, reason1, sizeof( reason1 ) );
    usable2 = gear_item_usable( ch, obj2, slot, reason2, sizeof( reason2 ) );

    gear_send_profile( ch, &profile );
    snprintf( buf, sizeof( buf ), "Comparison slot: %s\n\r",
              gear_slot_name( slot ) );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ), "A) %s (level %d)%s%s%s\n\r",
              obj1->short_descr, obj1->level,
              usable1 ? "" : " [not usable: ",
              usable1 ? "" : reason1, usable1 ? "" : "]" );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ), "B) %s (level %d)%s%s%s\n\r",
              obj2->short_descr, obj2->level,
              usable2 ? "" : " [not usable: ",
              usable2 ? "" : reason2, usable2 ? "" : "]" );
    send_to_char( buf, ch );

    send_to_char( "\n\rEstimated category edges:\n\r", ch );
    if ( focus == GEAR_FOCUS_OVERALL || focus == GEAR_FOCUS_DAMAGE )
        gear_send_metric( ch, "Weapon damage", metrics1.melee, metrics2.melee,
                          "damage/round", focus == GEAR_FOCUS_DAMAGE );
    if ( focus == GEAR_FOCUS_OVERALL || focus == GEAR_FOCUS_SPELLS )
        gear_send_metric( ch, "Spellcasting", metrics1.spells, metrics2.spells,
                          "readiness", focus == GEAR_FOCUS_SPELLS );
    if ( focus == GEAR_FOCUS_OVERALL || focus == GEAR_FOCUS_DEFENSE )
        gear_send_metric( ch, "Survivability", metrics1.survival,
                          metrics2.survival, "effective hp",
                          focus == GEAR_FOCUS_DEFENSE );
    if ( focus == GEAR_FOCUS_OVERALL || focus == GEAR_FOCUS_LEVELING )
        gear_send_metric( ch, "Leveling", metrics1.leveling,
                          metrics2.leveling, "efficiency",
                          focus == GEAR_FOCUS_LEVELING );
    if ( focus == GEAR_FOCUS_OVERALL || focus == GEAR_FOCUS_UTILITY )
        gear_send_metric( ch, "Utility", metrics1.utility, metrics2.utility,
                          "readiness", focus == GEAR_FOCUS_UTILITY );
    if ( focus != GEAR_FOCUS_OVERALL )
        gear_send_metric( ch, "Overall fit", metrics1.overall,
                          metrics2.overall, "profile index", false );

    send_to_char( "\n\rProjected loadouts:\n\r", ch );
    gear_send_loadout_facts( ch, &profile, &metrics1, &metrics2 );

    focused_value1 = gear_focus_value( &metrics1, focus );
    focused_value2 = gear_focus_value( &metrics2, focus );
    send_to_char( "\n\r", ch );
    gear_send_recommendation( ch, obj1, obj2, focused_value1,
                              focused_value2, usable1, usable2, focus );
    send_to_char( "Estimate uses an equal-level opponent, current skills, and a five-round fight.\n\r",
                  ch );
}
