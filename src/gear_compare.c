/*
 * COMPARE -- what a piece of gear does for the character wearing it.
 *
 * Every question here is asked the same way: put the item on in place of
 * what is in that slot, keep everything else exactly as the character
 * stands now, and measure two things.
 *
 *   Damage     how much harder you hit.  Weapon damage per round,
 *              worked through the same steps as multi_hit and one_hit;
 *              and for a caster, the mana there is to cast with, because
 *              a spell's damage is set by the caster's level and gear
 *              only changes how many of them you get.
 *   Toughness  effective hit points against an equal-level opponent.
 *
 * Damage is the point.  Toughness counts a quarter as much, so a large hp
 * bump can still beat a marginal damage gain but an ordinary one cannot.
 * The website's gear finder ranks by the same rule with fixed weights per
 * class; this ranks for the character in front of it.
 *
 * COMPARE UPGRADES runs that over every piece of gear a mobile in the
 * world carries or wears and that this character could put on today.
 */

#include <math.h>
#include <stdio.h>
#include <string.h>
#include "merc.h"
#include "interp.h"
#include "magic.h"

#define GEAR_TOUGH_WEIGHT   0.25    /* toughness, against damage at 1.0 */
#define GEAR_EVEN           0.005   /* under half a percent is a tie */
#define GEAR_UPGRADE_TOP    5

extern const int dice_thrown[];
extern const int dice_size[];
extern AREA_DATA *area_first;

typedef struct gear_profile GEAR_PROFILE;
typedef struct gear_loadout GEAR_LOADOUT;
typedef struct gear_result  GEAR_RESULT;

/* Where this character's damage comes from. */
struct gear_profile
{
    double spell_share;     /* 0..1 of it from spells */
    int spell_sn;           /* the attack spell measured, or -1 */
    int spell_cost;         /* its mana per cast */
};

/* A character's figures with some set of gear on. */
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
    int hyrule_hero_tunic_count;
    int hyrule_blue_ring_count;
    int hyrule_red_ring_count;
    int hyrule_mirror_shield_count;
    int hyrule_pegasus_boots_count;
};

/* What a loadout comes to. */
struct gear_result
{
    double melee;           /* weapon damage per round */
    double spell;           /* mana to cast with: the pool plus regen */
    double toughness;       /* effective hit points */
    double attacks;         /* swings a round */
    double hit_chance;      /* of the main hand, 0..1 */
    double per_hit;         /* main hand, when it lands */
    int weapon_skill;
    int casts;              /* full-mana casts of the profile's spell */
    int stat[MAX_STATS];
    int hitroll;
    int damroll;
    int max_hit;
    int max_mana;
    int max_move;
    int average_ac;
    int saving_throw;
    int exp_bonus;
    long affected_by;
    long affected_by2;
    int relic_damage_reduction;
    int relic_nonphysical_reduction;
    int relic_movement_reduction;
    int relic_kill_heal;
};

static const int gear_all_slots[] = {
    WEAR_WIELD, WEAR_SHIELD, WEAR_HOLD, WEAR_LIGHT, WEAR_BODY, WEAR_HEAD,
    WEAR_LEGS, WEAR_FEET, WEAR_HANDS, WEAR_ARMS, WEAR_ABOUT,
    WEAR_WAIST, WEAR_FINGER_L, WEAR_FINGER_R, WEAR_NECK_1,
    WEAR_NECK_2, WEAR_WRIST_L, WEAR_WRIST_R
};
#define GEAR_SLOT_COUNT \
    ((int)(sizeof( gear_all_slots ) / sizeof( gear_all_slots[0] )))

/* ------------------------------------------------------------------ */
/* Who is asking                                                       */
/* ------------------------------------------------------------------ */

static int gear_skill( CHAR_DATA *ch, int sn )
{
    if ( sn < 0 || sn >= MAX_SKILL )
        return 0;
    return get_skill( ch, sn );
}

static double gear_class_spell_share( int class_num )
{
    switch ( class_num )
    {
    case CLASS_MAGE:    return 0.85;
    case CLASS_NECRO:   return 0.85;
    case CLASS_CLERIC:  return 0.50;
    case CLASS_MONK:    return 0.15;
    default:            return 0.0;
    }
}

/*
 * How much of the damage is spells: the class's habit, leaning a little
 * toward the guild's, and nothing at all for a character who knows no
 * attack spell.  The spell measured is the latest-learned attack spell
 * they hold -- the one they will be casting -- and only its mana cost
 * matters, since gear changes how many casts there are and never what
 * each one does.
 */
static void gear_build_profile( CHAR_DATA *ch, GEAR_PROFILE *profile )
{
    int sn;
    int level;
    int best_level = -1;
    int guild;

    profile->spell_share = gear_class_spell_share( ch->class );
    guild = ch->pcdata->guild;
    if ( guild >= 0 && guild < MAX_CLASS && guild != ch->class )
        profile->spell_share = 0.7 * profile->spell_share
            + 0.3 * gear_class_spell_share( guild );

    profile->spell_sn = -1;
    profile->spell_cost = 0;
    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        if ( skill_table[sn].name == NULL )
            break;
        /* An attack spell: aimed at a foe, castable mid-fight, and
           leaving no affect behind -- a debuff has a wear-off message,
           a damage spell only the "!Name!" placeholder. */
        if ( skill_table[sn].spell_fun == NULL
            || skill_table[sn].spell_fun == spell_null
            || skill_table[sn].target != TAR_CHAR_OFFENSIVE
            || skill_table[sn].minimum_position > POS_FIGHTING
            || skill_table[sn].msg_off == NULL
            || skill_table[sn].msg_off[0] != '!'
            || ch->pcdata->learned[sn] < 1 || gear_skill( ch, sn ) < 1 )
            continue;
        level = skill_table[sn].skill_level[ch->class];
        if ( level > ch->level && guild >= 0 && guild < MAX_CLASS )
            level = skill_table[sn].skill_level[guild];
        if ( level > ch->level )
            continue;
        if ( level > best_level
            || (level == best_level
                && skill_table[sn].min_mana
                    > skill_table[profile->spell_sn].min_mana) )
        {
            best_level = level;
            profile->spell_sn = sn;
        }
    }

    if ( profile->spell_sn < 0 )
        profile->spell_share = 0.0;
    else
        profile->spell_cost = UMAX( 1, mana_cost( ch,
            skill_table[profile->spell_sn].min_mana, best_level ) );
}

/* ------------------------------------------------------------------ */
/* Where an item goes                                                  */
/* ------------------------------------------------------------------ */

static int gear_slot_wear_flag( int slot )
{
    switch ( slot )
    {
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
    case WEAR_WIELD:    return "wield";
    case WEAR_HOLD:     return "held";
    default:            return "unknown slot";
    }
}

static int gear_pair_partner( int slot )
{
    switch ( slot )
    {
    case WEAR_FINGER_L: return WEAR_FINGER_R;
    case WEAR_FINGER_R: return WEAR_FINGER_L;
    case WEAR_NECK_1:   return WEAR_NECK_2;
    case WEAR_NECK_2:   return WEAR_NECK_1;
    case WEAR_WRIST_L:  return WEAR_WRIST_R;
    case WEAR_WRIST_R:  return WEAR_WRIST_L;
    default:            return -1;
    }
}

/*
 * The one wear flag wear_obj acts on.  An item carrying several goes to
 * the first of them in wear_obj's order and never to the others, and a
 * light is always a light whatever else it says: Starlight is take and
 * hold, and WEAR puts it in the light slot.
 */
static int gear_natural_wear_flag( int wear_flags )
{
    static const int order[] = {
        ITEM_WEAR_FINGER, ITEM_WEAR_NECK, ITEM_WEAR_BODY, ITEM_WEAR_HEAD,
        ITEM_WEAR_LEGS, ITEM_WEAR_FEET, ITEM_WEAR_HANDS, ITEM_WEAR_ARMS,
        ITEM_WEAR_ABOUT, ITEM_WEAR_WAIST, ITEM_WEAR_WRIST, ITEM_WEAR_SHIELD,
        ITEM_WIELD, ITEM_HOLD
    };
    int i;

    for ( i = 0; i < (int)(sizeof( order ) / sizeof( order[0] )); i++ )
        if ( IS_SET( wear_flags, order[i] ) )
            return order[i];
    return 0;
}

static bool gear_item_fits( OBJ_DATA *obj, int slot )
{
    int wear_flag;

    if ( obj == NULL )
        return false;
    if ( slot == WEAR_LIGHT )
        return obj->item_type == ITEM_LIGHT;
    if ( obj->item_type == ITEM_LIGHT )
        return false;
    /* SECONDARY puts a wieldable weapon in the off hand. */
    if ( slot == WEAR_SHIELD && obj->item_type == ITEM_WEAPON )
        return CAN_WEAR( obj, ITEM_WIELD );
    wear_flag = gear_slot_wear_flag( slot );
    return wear_flag != 0
        && gear_natural_wear_flag( obj->wear_flags ) == wear_flag;
}

/* The slot two items would compete for, or WEAR_NONE. */
static int gear_choose_slot( OBJ_DATA *obj1, OBJ_DATA *obj2 )
{
    int i;

    if ( obj2->wear_loc != WEAR_NONE && gear_item_fits( obj1, obj2->wear_loc ) )
        return obj2->wear_loc;
    if ( obj1->wear_loc != WEAR_NONE && gear_item_fits( obj2, obj1->wear_loc ) )
        return obj1->wear_loc;
    for ( i = 0; i < GEAR_SLOT_COUNT; i++ )
        if ( gear_item_fits( obj1, gear_all_slots[i] )
            && gear_item_fits( obj2, gear_all_slots[i] ) )
            return gear_all_slots[i];
    return WEAR_NONE;
}

/* ------------------------------------------------------------------ */
/* Whether you can wear it                                             */
/* ------------------------------------------------------------------ */

/* wear_requirements_met's rule: the race flags name everyone it suits. */
static bool gear_race_allowed( CHAR_DATA *ch, OBJ_DATA *obj )
{
    int allowed;
    int mine;

    if ( !IS_OBJ_STAT( obj, ITEM_RACE_RESTRICTED ) )
        return true;
    allowed = obj->extra_flags2
        & ( ITEM2_HUMAN_ONLY | ITEM2_ELF_ONLY | ITEM2_DWARF_ONLY
          | ITEM2_HALFLING_ONLY | ITEM2_SAURIAN_ONLY );
    if ( allowed == 0 )
        return true;
    switch ( ch->race )
    {
    case 1:  mine = ITEM2_HUMAN_ONLY;    break;
    case 2:  mine = ITEM2_ELF_ONLY;      break;
    case 3:  mine = ITEM2_DWARF_ONLY;    break;
    case 4:  mine = ITEM2_HALFLING_ONLY; break;
    case 5:  mine = ITEM2_SAURIAN_ONLY;  break;
    default: mine = 0;                   break;
    }
    return mine != 0 && IS_SET( allowed, mine );
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

/* Every refusal WEAR, WIELD and SECONDARY would give, and why. */
static bool gear_item_usable( CHAR_DATA *ch, OBJ_DATA *obj, int slot,
                              char *reason, size_t reason_size )
{
    OBJ_DATA *blocker;

    reason[0] = '\0';
    if ( obj->level > ch->level )
    {
        snprintf( reason, reason_size, "needs level %d", obj->level );
        return false;
    }
    if ( IS_OBJ_STAT( obj, ITEM_HEATED ) )
    {
        snprintf( reason, reason_size, "still heated" );
        return false;
    }
    if ( IS_OBJ_STAT( obj, ITEM_DAMAGED ) )
    {
        snprintf( reason, reason_size, "needs repair" );
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
        snprintf( reason, reason_size, "made for another race" );
        return false;
    }
    if ( obj->wear_loc == slot )
        return true;
    if ( ch->class == CLASS_MONK && obj->item_type == ITEM_WEAPON
        && is_affected( ch, skill_lookup( "steel fist" ) ) )
    {
        snprintf( reason, reason_size, "not during steel fist" );
        return false;
    }
    if ( obj->item_type == ITEM_WEAPON
        && get_obj_weight( obj ) > str_app[get_curr_stat( ch, STAT_STR )].wield )
    {
        snprintf( reason, reason_size, "too heavy to wield" );
        return false;
    }
    if ( slot == WEAR_SHIELD && obj->item_type == ITEM_WEAPON )
    {
        blocker = get_eq_char( ch, WEAR_WIELD );
        if ( IS_WEAPON_STAT( obj, WEAPON_TWO_HANDS ) )
        {
            snprintf( reason, reason_size, "two-handed" );
            return false;
        }
        if ( gear_skill( ch, gsn_dual_wield ) < 1 )
        {
            snprintf( reason, reason_size, "needs dual wield" );
            return false;
        }
        if ( blocker == NULL )
        {
            snprintf( reason, reason_size, "needs a main-hand weapon" );
            return false;
        }
        if ( IS_WEAPON_STAT( blocker, WEAPON_TWO_HANDS ) )
        {
            snprintf( reason, reason_size, "your weapon is two-handed" );
            return false;
        }
        if ( !IS_IMMORTAL( ch ) && !gear_offhand_power_allowed( obj ) )
        {
            snprintf( reason, reason_size, "too powerful to dual wield" );
            return false;
        }
    }
    if ( slot == WEAR_SHIELD && obj->item_type != ITEM_WEAPON )
    {
        blocker = get_eq_char( ch, WEAR_WIELD );
        if ( blocker != NULL && ch->size < SIZE_LARGE
            && IS_WEAPON_STAT( blocker, WEAPON_TWO_HANDS ) )
        {
            snprintf( reason, reason_size, "your weapon is two-handed" );
            return false;
        }
    }
    if ( slot == WEAR_WIELD && obj->item_type == ITEM_WEAPON
        && IS_WEAPON_STAT( obj, WEAPON_TWO_HANDS ) )
    {
        blocker = get_eq_char( ch, WEAR_SHIELD );
        if ( blocker != NULL && blocker != obj && !IS_IMMORTAL( ch )
            && IS_OBJ_STAT( blocker, ITEM_NOREMOVE ) )
        {
            snprintf( reason, reason_size, "your off hand is stuck" );
            return false;
        }
    }
    blocker = get_eq_char( ch, slot );
    if ( blocker != NULL && blocker != obj
        && IS_OBJ_STAT( blocker, ITEM_NOREMOVE ) )
    {
        snprintf( reason, reason_size, "what you wear there won't come off" );
        return false;
    }
    return true;
}

/* ------------------------------------------------------------------ */
/* Building a loadout                                                  */
/* ------------------------------------------------------------------ */

static void gear_apply_hyrule_relic( GEAR_LOADOUT *loadout, OBJ_DATA *obj,
                                     int sign )
{
    if ( obj == NULL || obj->pIndexData == NULL )
        return;
    switch ( obj->pIndexData->vnum )
    {
    case OBJ_VNUM_HYRULE_HEROS_TUNIC:
        loadout->hyrule_hero_tunic_count += sign;
        break;
    case OBJ_VNUM_HYRULE_BLUE_RING:
        loadout->hyrule_blue_ring_count += sign;
        break;
    case OBJ_VNUM_HYRULE_RED_RING:
        loadout->hyrule_red_ring_count += sign;
        break;
    case OBJ_VNUM_HYRULE_MIRROR_SHIELD:
        loadout->hyrule_mirror_shield_count += sign;
        break;
    case OBJ_VNUM_HYRULE_PEGASUS_BOOTS:
        loadout->hyrule_pegasus_boots_count += sign;
        break;
    default:
        break;
    }
}

static void gear_loadout_from_char( CHAR_DATA *ch, GEAR_LOADOUT *loadout )
{
    OBJ_DATA *obj;
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
    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->wear_loc != WEAR_NONE )
            gear_apply_hyrule_relic( loadout, obj, 1 );
}

static void gear_apply_affect( GEAR_LOADOUT *loadout, AFFECT_DATA *paf,
                               int sign )
{
    int modifier = paf->modifier * sign;
    int i;

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
    case APPLY_STR:     loadout->raw_stat[STAT_STR] += modifier; break;
    case APPLY_DEX:     loadout->raw_stat[STAT_DEX] += modifier; break;
    case APPLY_INT:     loadout->raw_stat[STAT_INT] += modifier; break;
    case APPLY_WIS:     loadout->raw_stat[STAT_WIS] += modifier; break;
    case APPLY_CON:     loadout->raw_stat[STAT_CON] += modifier; break;
    case APPLY_MANA:    loadout->max_mana += modifier; break;
    case APPLY_HIT:     loadout->max_hit += modifier; break;
    case APPLY_MOVE:    loadout->max_move += modifier; break;
    case APPLY_EXP:     loadout->exp_bonus += modifier; break;
    case APPLY_HITROLL: loadout->hitroll += modifier; break;
    case APPLY_DAMROLL: loadout->damroll += modifier; break;
    case APPLY_AC:
        for ( i = 0; i < 4; i++ )
            loadout->armor[i] += modifier;
        break;
    case APPLY_SAVING_PARA:
    case APPLY_SAVING_ROD:
    case APPLY_SAVING_PETRI:
    case APPLY_SAVING_BREATH:
    case APPLY_SAVING_SPELL:
        loadout->saving_throw += modifier;
        break;
    case APPLY_IMMUNITY:
        if ( sign > 0 )
            SET_BIT( loadout->imm_flags, (long)(unsigned short)paf->modifier );
        else
            REMOVE_BIT( loadout->imm_flags,
                        (long)(unsigned short)paf->modifier );
        break;
    default:
        break;
    }
}

/* unequip_char keeps an item's bit when a spell supplies the same one. */
static void gear_clear_item_affect( CHAR_DATA *ch, GEAR_LOADOUT *loadout,
                                    const char *spell, int bit )
{
    if ( !is_affected( ch, skill_lookup( spell ) ) )
        REMOVE_BIT( loadout->affected_by, bit );
}

static void gear_apply_item( CHAR_DATA *ch, GEAR_LOADOUT *loadout,
                             OBJ_DATA *obj, int slot, int sign )
{
    AFFECT_DATA *paf;
    int i;

    if ( obj == NULL )
        return;

    gear_apply_hyrule_relic( loadout, obj, sign );
    for ( i = 0; i < 4; i++ )
        loadout->armor[i] -= sign * apply_ac( obj, slot, i );
    if ( !obj->enchanted && obj->pIndexData != NULL )
        for ( paf = obj->pIndexData->affected; paf != NULL; paf = paf->next )
            gear_apply_affect( loadout, paf, sign );
    for ( paf = obj->affected; paf != NULL; paf = paf->next )
        gear_apply_affect( loadout, paf, sign );

    if ( IS_OBJ_STAT( obj, ITEM_ADD_AFFECT ) )
    {
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_INVIS ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_INVISIBLE );
            else gear_clear_item_affect( ch, loadout, "invis", AFF_INVISIBLE );
        }
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_DETECT_INVIS ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_DETECT_INVIS );
            else gear_clear_item_affect( ch, loadout, "detect invis",
                                         AFF_DETECT_INVIS );
        }
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_FLY ) )
        {
            if ( sign > 0 ) SET_BIT( loadout->affected_by, AFF_FLYING );
            else gear_clear_item_affect( ch, loadout, "fly", AFF_FLYING );
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

static void gear_item_flags( OBJ_DATA *obj, long *aff, long *aff2, long *imm )
{
    AFFECT_DATA *paf;
    int pass;

    for ( pass = 0; pass < 2; pass++ )
    {
        if ( pass == 0 )
            paf = (obj->enchanted || obj->pIndexData == NULL)
                ? NULL : obj->pIndexData->affected;
        else
            paf = obj->affected;
        for ( ; paf != NULL; paf = paf->next )
        {
            if ( paf->bitvector != 0 )
                SET_BIT( *aff, (long)(unsigned int)paf->bitvector );
            else if ( paf->bitvector2 != 0 )
                SET_BIT( *aff2, (long)(unsigned int)paf->bitvector2 );
            if ( paf->location == APPLY_IMMUNITY )
                SET_BIT( *imm, (long)(unsigned short)paf->modifier );
        }
    }
    if ( IS_OBJ_STAT( obj, ITEM_ADD_AFFECT ) )
    {
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_INVIS ) )
            SET_BIT( *aff, AFF_INVISIBLE );
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_DETECT_INVIS ) )
            SET_BIT( *aff, AFF_DETECT_INVIS );
        if ( IS_OBJ_STAT2( obj, ITEM2_ADD_FLY ) )
            SET_BIT( *aff, AFF_FLYING );
    }
}

/*
 * Taking an item off must not take away a bit something else still gives:
 * two items granting the same flag, or a spell and an item.  Rebuild the
 * item-supplied bits from what stays on.
 */
static void gear_project_flags( CHAR_DATA *ch, OBJ_DATA *gone1,
                                OBJ_DATA *gone2, GEAR_LOADOUT *loadout )
{
    OBJ_DATA *obj;
    long all_aff = 0, all_aff2 = 0, all_imm = 0;
    long kept_aff = 0, kept_aff2 = 0, kept_imm = 0;

    for ( obj = ch->carrying; obj != NULL; obj = obj->next_content )
    {
        if ( obj->wear_loc == WEAR_NONE )
            continue;
        gear_item_flags( obj, &all_aff, &all_aff2, &all_imm );
        if ( obj != gone1 && obj != gone2 )
            gear_item_flags( obj, &kept_aff, &kept_aff2, &kept_imm );
    }
    loadout->affected_by = (ch->affected_by & ~all_aff) | kept_aff;
    loadout->affected_by2 = (ch->affected_by2 & ~all_aff2) | kept_aff2;
    loadout->imm_flags = (ch->imm_flags & ~all_imm) | kept_imm;
}

/*
 * The character as they stand, minus whatever of obj1 and obj2 is worn --
 * or, when neither is, minus what occupies the slot.  Both candidates are
 * then measured from this same base.
 */
static void gear_base_loadout( CHAR_DATA *ch, OBJ_DATA *obj1, OBJ_DATA *obj2,
                               int slot, GEAR_LOADOUT *base )
{
    OBJ_DATA *gone1 = NULL;
    OBJ_DATA *gone2 = NULL;

    gear_loadout_from_char( ch, base );
    if ( obj1 != NULL && obj1->wear_loc != WEAR_NONE )
        gone1 = obj1;
    if ( obj2 != NULL && obj2->wear_loc != WEAR_NONE && obj2 != obj1 )
        gone2 = obj2;
    if ( gone1 == NULL && gone2 == NULL )
        gone1 = get_eq_char( ch, slot );
    if ( gone1 != NULL )
        gear_apply_item( ch, base, gone1, gone1->wear_loc, -1 );
    if ( gone2 != NULL )
        gear_apply_item( ch, base, gone2, gone2->wear_loc, -1 );
    gear_project_flags( ch, gone1, gone2, base );
}

static void gear_put_on( CHAR_DATA *ch, const GEAR_LOADOUT *base,
                         OBJ_DATA *obj, int slot, GEAR_LOADOUT *result )
{
    *result = *base;
    if ( obj == NULL )
        return;
    /* A two-handed weapon takes the off hand with it. */
    if ( slot == WEAR_WIELD && obj->item_type == ITEM_WEAPON
        && IS_WEAPON_STAT( obj, WEAPON_TWO_HANDS )
        && result->offhand != NULL )
        gear_apply_item( ch, result, result->offhand, WEAR_SHIELD, -1 );
    gear_apply_item( ch, result, obj, slot, 1 );
}

/* ------------------------------------------------------------------ */
/* Measuring a loadout                                                 */
/* ------------------------------------------------------------------ */

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

static int gear_stat( CHAR_DATA *ch, const GEAR_LOADOUT *loadout, int stat )
{
    return URANGE( 3, loadout->raw_stat[stat], gear_stat_cap( ch, stat ) );
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

/* one_hit's d20: a 0 always misses, a 19 always hits. */
static double gear_hit_chance( int threshold )
{
    int roll;
    int hits = 0;

    for ( roll = 1; roll < 20; roll++ )
        if ( roll == 19 || roll >= threshold )
            hits++;
    return hits / 20.0;
}

/* The armour class of an ordinary mobile of the character's level. */
static int gear_standard_victim_ac( int level )
{
    int victim_ac = (100 - 6 * level) / 10;

    if ( victim_ac < -17 )
        victim_ac = (victim_ac + 17) / 5 - 17;
    return victim_ac;
}

/*
 * The value[4] weapon flags one_hit folds into the dice.  Must stay in
 * step with the weapon flag block in one_hit; the integer thresholds are
 * reproduced on purpose.
 */
static double gear_weapon_flag_multiplier( OBJ_DATA *weapon, int skill )
{
    double multiplier = 1.0;

    if ( weapon == NULL || weapon->item_type != ITEM_WEAPON )
        return multiplier;
    if ( IS_WEAPON_STAT( weapon, WEAPON_FLAMING ) )
        multiplier *= 1.1;
    if ( IS_WEAPON_STAT( weapon, WEAPON_FROST ) )
        multiplier *= 1.1;
    if ( IS_WEAPON_STAT( weapon, WEAPON_VAMPIRIC ) )
        multiplier *= 1.1;
    if ( IS_WEAPON_STAT( weapon, WEAPON_SHARP ) )
        multiplier *= 1.0 + (skill / 8) / 100.0;
    if ( IS_WEAPON_STAT( weapon, WEAPON_VORPAL ) )
        multiplier *= 1.0 + 2.0 * (skill / 20) / 100.0;
    return multiplier;
}

/* Weapon or bare-hand dice, before enhanced damage and damroll. */
static double gear_dice_damage( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                                OBJ_DATA *weapon, int skill, bool main_hand )
{
    double damage;
    double low;
    double high;

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
            low = 1 + ch->level + 4 * skill / 100.0;
            high = 2 * ch->level * skill / 100.0;
        }
        else
        {
            low = 1 + 4 * skill / 100.0;
            high = 2 * ch->level * skill / 300.0;
        }
        damage = high <= low ? low : (low + high) / 2.0;
    }
    return damage * gear_weapon_flag_multiplier( weapon, skill );
}

/* Damroll is added last in one_hit, after every multiplier. */
static double gear_damroll_damage( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                                   int skill )
{
    int damroll = loadout->damroll
        + str_app[gear_stat( ch, loadout, STAT_STR )].todam;

    return damroll * UMIN( 100, skill ) / 100.0;
}

/* Expected value of one_hit's "dam += dam * diceroll/200". */
static double gear_enhanced_multiplier( CHAR_DATA *ch )
{
    double enhanced = gear_skill( ch, gsn_enhanced_damage );

    return 1.0 + enhanced * (enhanced + 1) / 40000.0;
}

static double gear_hit_damage( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                               OBJ_DATA *weapon, int skill, bool main_hand )
{
    double damage = gear_dice_damage( ch, loadout, weapon, skill, main_hand )
        * gear_enhanced_multiplier( ch )
        + gear_damroll_damage( ch, loadout, skill );

    return UMAX( 1.0, damage );
}

/*
 * Weapon damage per round, walked through multi_hit: two swings, haste's
 * extra one, second attack at half its skill, the off hand at
 * (dual wield + weapon skill) / 5, a saurian's tail one time in seven,
 * and third attack at a quarter of its skill.  Backstab, smite and fists
 * of fury are openers or occasional, so the best of them counts a fifth.
 */
static void gear_melee( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                        GEAR_RESULT *result )
{
    OBJ_DATA *main_weapon = loadout->main_weapon;
    OBJ_DATA *off_weapon = loadout->offhand;
    double attacks;
    double accuracy;
    double per_hit;
    double round;
    double off_chance;
    double opener;
    double special;
    double chance;
    double bonus;
    int skill;
    int off_skill;
    int hitroll;
    int threshold;
    int thac0;
    int ability;
    int multiplier;

    if ( main_weapon != NULL && main_weapon->item_type != ITEM_WEAPON )
        main_weapon = NULL;
    if ( off_weapon != NULL && off_weapon->item_type != ITEM_WEAPON )
        off_weapon = NULL;

    skill = get_weapon_skill( ch, gear_weapon_sn( main_weapon ) );
    hitroll = loadout->hitroll
        + str_app[gear_stat( ch, loadout, STAT_STR )].tohit;
    thac0 = interpolate( ch->level, class_table[ch->class].thac0_00,
                         class_table[ch->class].thac0_32 );
    threshold = thac0 - gear_standard_victim_ac( ch->level )
        - hitroll * skill / 100 + 5 * (100 - skill) / 100;
    accuracy = gear_hit_chance( threshold );
    per_hit = gear_hit_damage( ch, loadout, main_weapon, skill, true );

    attacks = 2.0
        + gear_skill( ch, gsn_second_attack ) / 200.0
        + gear_skill( ch, gsn_third_attack ) / 400.0;
    if ( IS_SET( loadout->affected_by, AFF_HASTE ) )
        attacks += 1.0;
    if ( IS_IMMORTAL( ch ) )
        attacks += 3.0;
    if ( ch->race == 5 )
        attacks += 0.13;
    round = per_hit * accuracy * attacks;

    result->weapon_skill = skill;
    result->hit_chance = accuracy;
    result->per_hit = per_hit;
    result->attacks = attacks;

    if ( off_weapon != NULL )
    {
        off_skill = get_weapon_skill( ch, gear_weapon_sn( off_weapon ) );
        off_chance = UMIN( 1.0,
            (gear_skill( ch, gsn_dual_wield ) + off_skill) / 500.0 );
        /* one_hit skips the normal hit roll for the off-hand swing. */
        round += off_chance
            * gear_hit_damage( ch, loadout, off_weapon, off_skill, false );
        result->attacks += off_chance;
    }

    special = 0.0;

    ability = gear_skill( ch, gsn_backstab );
    if ( ability > 0 && main_weapon != NULL )
    {
        /* No enhanced damage on a backstab: the multiplier takes the dice
           alone and damroll comes after. */
        multiplier = main_weapon->value[0] == WEAPON_DAGGER
            ? 2 + ch->level / 10 : 2 + ch->level / 15;
        opener = (2.0 * gear_dice_damage( ch, loadout, main_weapon, skill, true )
                  * multiplier + gear_damroll_damage( ch, loadout, skill ))
            * gear_hit_chance( threshold - 10 * (100 - ability) )
            * ability / 100.0;
        special = UMAX( special, opener - 2.0 * per_hit * accuracy );
    }

    ability = gear_skill( ch, gsn_smite );
    if ( ability > 0 && main_weapon != NULL
        && (main_weapon->value[0] == WEAPON_SWORD
            || main_weapon->value[0] == WEAPON_AXE
            || main_weapon->value[0] == WEAPON_FLAIL
            || main_weapon->value[0] == WEAPON_MACE) )
    {
        chance = 2 * ability / 3.0;
        if ( gear_stat( ch, loadout, STAT_STR ) > 22 )
            chance += 10.0;
        if ( gear_stat( ch, loadout, STAT_DEX ) > 24 )
            chance += 10.0;
        bonus = main_weapon->value[1] * (main_weapon->value[2] + 1) / 2.0
            * skill / (main_weapon->value[0] == WEAPON_SWORD ? 125.0 : 150.0)
            * (1 + (ch->level > 30) + (ch->level > 50));
        special = UMAX( special, bonus * attacks
            * gear_hit_chance( threshold - 10 * (100 - ability) )
            * UMIN( 100.0, chance ) / 100.0 );
    }

    ability = gear_skill( ch, gsn_fists_of_fury );
    if ( ability >= 2 && main_weapon == NULL && loadout->max_mana >= 30
        && loadout->max_move >= 15 )
    {
        chance = UMIN( 100, ability + 60 ) / 100.0;
        bonus = chance * (3.5 + (ch->level >= 35) + (ch->level >= 45))
            * ch->level * 1.5;
        special = UMAX( special, bonus - round );
    }

    result->melee = UMAX( 0.1, round + special / 5.0 );
}

/*
 * Effective hit points: how much an equal-level opponent has to deal to
 * put you down, after armour turns blows aside and softens the rest,
 * sanctuary and divine protection, dodge, parry and block, the Hyrule
 * relics, and saving throws against the half of it that is magic.
 */
static void gear_toughness( CHAR_DATA *ch, const GEAR_LOADOUT *loadout,
                            GEAR_RESULT *result )
{
    double incoming;
    double avoid;
    double raw;
    double reduced;
    double factor;
    double save_chance;
    int victim_ac;
    int skill;
    int stat;
    int hitroll;
    int threshold;
    int dexterity;
    int i;
    int total_ac = 0;

    dexterity = gear_stat( ch, loadout, STAT_DEX );
    for ( i = 0; i < 4; i++ )
        total_ac += loadout->armor[i] + dex_app[dexterity].defensive;
    result->average_ac = total_ac / 4;

    victim_ac = result->average_ac / 10;
    if ( victim_ac < -17 )
        victim_ac = (victim_ac + 17) / 5 - 17;
    skill = URANGE( 0, 40 + 5 * ch->level / 2, 100 );
    stat = UMIN( MAX_STAT, 11 + ch->level / 4 );
    hitroll = ch->level / 2 + str_app[stat].tohit;
    threshold = interpolate( ch->level, 20, -4 ) - victim_ac
        - hitroll * skill / 100 + 5 * (100 - skill) / 100;
    incoming = gear_hit_chance( threshold );

    avoid = 1.0 - UMIN( 95, gear_skill( ch, gsn_dodge ) / 2 ) / 100.0;
    if ( loadout->main_weapon != NULL || ch->class == CLASS_MONK )
        avoid *= 1.0 - UMIN( 95, gear_skill( ch, gsn_parry ) / 2 ) / 100.0;
    if ( loadout->offhand != NULL )
        avoid *= 1.0 - UMIN( 95, gear_skill( ch, gsn_shield_block ) / 2 ) / 100.0;
    if ( ch->race == 4 )
        avoid *= 0.87;
    incoming = UMAX( 0.01, incoming * avoid );

    raw = UMAX( 5.0, (double)ch->level );
    reduced = URANGE( 1.0, raw + (-100 + result->average_ac) / 12.0, raw );
    factor = (raw + reduced) / (2.0 * raw);
    if ( IS_SET( loadout->affected_by, AFF_SANCTUARY ) )
        factor *= 0.5;
    if ( IS_SET( loadout->affected_by2, AFF2_DIVINE_PROT ) )
        factor *= IS_SET( loadout->affected_by, AFF_SANCTUARY ) ? 0.9375 : 0.75;
    factor *= (100.0 - result->relic_damage_reduction) / 100.0;
    /* Half of the standard opponent's damage is nonphysical. */
    factor *= 1.0 - result->relic_nonphysical_reduction / 200.0;

    save_chance = URANGE( 5, 50 - loadout->saving_throw * 5, 95 ) / 100.0;
    result->toughness = UMAX( 1, loadout->max_hit )
        / (incoming * UMAX( 0.05, factor ))
        * (1.0 + save_chance * 0.35);
}

/*
 * Mana to cast with: the pool, plus four sleeping ticks of mana_gain's
 * WIS + INT + level regeneration.
 */
static double gear_spell_fuel( CHAR_DATA *ch, const GEAR_LOADOUT *loadout )
{
    double regen = (gear_stat( ch, loadout, STAT_WIS )
        + gear_stat( ch, loadout, STAT_INT ) + ch->level) * 0.75;

    return UMAX( 1.0, (double)loadout->max_mana + regen * 4.0 );
}

static void gear_measure( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                          const GEAR_LOADOUT *loadout, GEAR_RESULT *result )
{
    int i;

    memset( result, 0, sizeof( *result ) );
    for ( i = 0; i < MAX_STATS; i++ )
        result->stat[i] = gear_stat( ch, loadout, i );
    result->hitroll = loadout->hitroll + str_app[result->stat[STAT_STR]].tohit;
    result->damroll = loadout->damroll + str_app[result->stat[STAT_STR]].todam;
    result->max_hit = UMAX( 1, loadout->max_hit );
    result->max_mana = UMAX( 0, loadout->max_mana );
    result->max_move = UMAX( 0, loadout->max_move );
    result->saving_throw = loadout->saving_throw;
    result->exp_bonus = loadout->exp_bonus;
    result->affected_by = loadout->affected_by;
    result->affected_by2 = loadout->affected_by2;

    if ( loadout->hyrule_red_ring_count > 0 )
        result->relic_damage_reduction = 20;
    else if ( loadout->hyrule_blue_ring_count > 0 )
        result->relic_damage_reduction = 10;
    if ( loadout->hyrule_mirror_shield_count > 0 )
        result->relic_nonphysical_reduction = 15;
    if ( loadout->hyrule_pegasus_boots_count > 0 )
        result->relic_movement_reduction = 25;
    if ( loadout->hyrule_hero_tunic_count > 0 )
        result->relic_kill_heal = UMAX( 1,
            UMIN( result->max_hit / 20, ch->level * 2 ) );

    gear_melee( ch, loadout, result );
    gear_toughness( ch, loadout, result );
    result->spell = gear_spell_fuel( ch, loadout );
    if ( profile->spell_cost > 0 )
        result->casts = result->max_mana / profile->spell_cost;
}

/* ------------------------------------------------------------------ */
/* Scoring A against B                                                 */
/* ------------------------------------------------------------------ */

/* Fractional change in damage from B to A, blended by where it comes from. */
static double gear_damage_change( const GEAR_PROFILE *profile,
                                  const GEAR_RESULT *a, const GEAR_RESULT *b )
{
    return (1.0 - profile->spell_share)
            * (a->melee / UMAX( 0.1, b->melee ) - 1.0)
        + profile->spell_share
            * (a->spell / UMAX( 1.0, b->spell ) - 1.0);
}

static double gear_tough_change( const GEAR_RESULT *a, const GEAR_RESULT *b )
{
    return a->toughness / UMAX( 1.0, b->toughness ) - 1.0;
}

/* Above zero when A is the better choice.  DEFENSE ranks by toughness. */
static double gear_score( const GEAR_PROFILE *profile, const GEAR_RESULT *a,
                          const GEAR_RESULT *b, bool defense )
{
    if ( defense )
        return gear_tough_change( a, b );
    return gear_damage_change( profile, a, b )
        + GEAR_TOUGH_WEIGHT * gear_tough_change( a, b );
}

/*
 * obj1 and obj2 in one slot, each measured from the same base: the
 * character with that slot empty.  Either may be NULL for "nothing".
 */
static void gear_evaluate( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                           OBJ_DATA *obj1, OBJ_DATA *obj2, int slot,
                           GEAR_RESULT *result1, GEAR_RESULT *result2 )
{
    GEAR_LOADOUT base;
    GEAR_LOADOUT loadout;

    gear_base_loadout( ch, obj1, obj2, slot, &base );
    gear_put_on( ch, &base, obj1, slot, &loadout );
    gear_measure( ch, profile, &loadout, result1 );
    gear_put_on( ch, &base, obj2, slot, &loadout );
    gear_measure( ch, profile, &loadout, result2 );
}

/*
 * What a carried item would replace.  For a ring, an amulet or a bracer
 * it is the weaker of the two worn -- the one you would take off.
 */
static OBJ_DATA *gear_find_worn_match( CHAR_DATA *ch,
                                       const GEAR_PROFILE *profile,
                                       OBJ_DATA *candidate, bool defense )
{
    GEAR_RESULT with_candidate;
    GEAR_RESULT with_worn;
    OBJ_DATA *worn;
    OBJ_DATA *other;
    double score_worn;
    double score_other;
    int partner;
    int i;

    for ( i = 0; i < GEAR_SLOT_COUNT; i++ )
    {
        worn = get_eq_char( ch, gear_all_slots[i] );
        if ( worn == NULL || worn == candidate
            || !gear_item_fits( candidate, gear_all_slots[i] ) )
            continue;
        /* A weapon is weighed against a weapon, not a shield. */
        if ( candidate->item_type == ITEM_WEAPON
            && worn->item_type != ITEM_WEAPON )
            continue;

        partner = gear_pair_partner( gear_all_slots[i] );
        other = partner < 0 ? NULL : get_eq_char( ch, partner );
        if ( other == NULL || other == candidate )
            return worn;

        gear_evaluate( ch, profile, candidate, worn, gear_all_slots[i],
                       &with_candidate, &with_worn );
        score_worn = gear_score( profile, &with_candidate, &with_worn, defense );
        gear_evaluate( ch, profile, candidate, other, partner,
                       &with_candidate, &with_worn );
        score_other = gear_score( profile, &with_candidate, &with_worn, defense );
        return score_other > score_worn ? other : worn;
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Saying it                                                           */
/* ------------------------------------------------------------------ */

static void gear_send_row( CHAR_DATA *ch, const char *label,
                           double value1, double value2, bool whole )
{
    char buf[MAX_STRING_LENGTH];
    char edge[32];
    double percent;

    if ( fabs( value1 - value2 ) <= UMAX( 0.01, fabs( value2 ) * GEAR_EVEN ) )
        toc_strlcpy( edge, "even", sizeof( edge ) );
    else if ( value1 > value2 )
    {
        percent = (value1 / UMAX( 0.1, value2 ) - 1.0) * 100.0;
        snprintf( edge, sizeof( edge ), "A +%.1f%%", UMIN( 999.9, percent ) );
    }
    else
    {
        percent = (value2 / UMAX( 0.1, value1 ) - 1.0) * 100.0;
        snprintf( edge, sizeof( edge ), "B +%.1f%%", UMIN( 999.9, percent ) );
    }
    if ( whole )
        snprintf( buf, sizeof( buf ), "  %-16s %9.0f %9.0f   %s\n\r",
                  label, value1, value2, edge );
    else
        snprintf( buf, sizeof( buf ), "  %-16s %9.1f %9.1f   %s\n\r",
                  label, value1, value2, edge );
    send_to_char( buf, ch );
}

/* Append a part to a comma list, wrapping before 76 columns. */
static void gear_list_add( CHAR_DATA *ch, char *line, size_t size,
                           const char *part, bool *first )
{
    if ( !*first && strlen( line ) + strlen( part ) + 2 > 76 )
    {
        toc_strlcat( line, ",\n\r", size );
        send_to_char( line, ch );
        toc_strlcpy( line, "    ", size );
    }
    else if ( !*first )
        toc_strlcat( line, ", ", size );
    toc_strlcat( line, part, size );
    *first = false;
}

static void gear_list_number( CHAR_DATA *ch, char *line, size_t size,
                              const char *label, int delta, bool *first )
{
    char part[64];

    if ( delta == 0 )
        return;
    snprintf( part, sizeof( part ), "%s %+d", label, delta );
    gear_list_add( ch, line, size, part, first );
}

static void gear_list_flags( CHAR_DATA *ch, char *line, size_t size,
                             char sign, const char *names, bool *first )
{
    char part[MAX_INPUT_LENGTH];

    if ( names == NULL || names[0] == '\0' || !str_cmp( names, "none" ) )
        return;
    snprintf( part, sizeof( part ), "%c%s", sign, names );
    gear_list_add( ch, line, size, part, first );
}

/* What changes on the score sheet with A on instead of B. */
static void gear_send_changes( CHAR_DATA *ch, OBJ_DATA *obj1, OBJ_DATA *obj2,
                               const GEAR_RESULT *a, const GEAR_RESULT *b )
{
    static const char *stat_names[MAX_STATS] = {
        "STR", "INT", "WIS", "DEX", "CON"
    };
    char line[MAX_STRING_LENGTH];
    char part[64];
    bool first = true;
    int i;

    toc_strlcpy( line, "A instead of B: ", sizeof( line ) );
    if ( obj2 != NULL
        && obj1->item_type == ITEM_WEAPON && obj2->item_type == ITEM_WEAPON
        && (obj1->value[1] != obj2->value[1]
            || obj1->value[2] != obj2->value[2]) )
    {
        snprintf( part, sizeof( part ), "dice %dd%d not %dd%d",
                  obj1->value[1], obj1->value[2],
                  obj2->value[1], obj2->value[2] );
        gear_list_add( ch, line, sizeof( line ), part, &first );
    }
    gear_list_number( ch, line, sizeof( line ), "hit",
                      a->hitroll - b->hitroll, &first );
    gear_list_number( ch, line, sizeof( line ), "dam",
                      a->damroll - b->damroll, &first );
    gear_list_number( ch, line, sizeof( line ), "hp",
                      a->max_hit - b->max_hit, &first );
    gear_list_number( ch, line, sizeof( line ), "mana",
                      a->max_mana - b->max_mana, &first );
    gear_list_number( ch, line, sizeof( line ), "move",
                      a->max_move - b->max_move, &first );
    gear_list_number( ch, line, sizeof( line ), "AC",
                      a->average_ac - b->average_ac, &first );
    gear_list_number( ch, line, sizeof( line ), "save",
                      a->saving_throw - b->saving_throw, &first );
    for ( i = 0; i < MAX_STATS; i++ )
        gear_list_number( ch, line, sizeof( line ), stat_names[i],
                          a->stat[i] - b->stat[i], &first );
    if ( a->exp_bonus != b->exp_bonus )
    {
        snprintf( part, sizeof( part ), "XP %+d%%",
                  a->exp_bonus - b->exp_bonus );
        gear_list_add( ch, line, sizeof( line ), part, &first );
    }
    gear_list_flags( ch, line, sizeof( line ), '+',
        affect_bit_name( a->affected_by & ~b->affected_by ), &first );
    gear_list_flags( ch, line, sizeof( line ), '-',
        affect_bit_name( b->affected_by & ~a->affected_by ), &first );
    gear_list_flags( ch, line, sizeof( line ), '+',
        affect2_bit_name( a->affected_by2 & ~b->affected_by2 ), &first );
    gear_list_flags( ch, line, sizeof( line ), '-',
        affect2_bit_name( b->affected_by2 & ~a->affected_by2 ), &first );
    if ( first )
        toc_strlcat( line, "nothing on the score sheet changes",
                     sizeof( line ) );
    toc_strlcat( line, ".\n\r", sizeof( line ) );
    send_to_char( line, ch );
}

static bool gear_has_relic( const GEAR_RESULT *result )
{
    return result->relic_damage_reduction > 0
        || result->relic_nonphysical_reduction > 0
        || result->relic_movement_reduction > 0
        || result->relic_kill_heal > 0;
}

/* The Hyrule relics do things the score sheet cannot show. */
static void gear_send_relic_facts( CHAR_DATA *ch, char label,
                                   const GEAR_RESULT *result )
{
    char buf[MAX_STRING_LENGTH];
    char part[64];

    if ( !gear_has_relic( result ) )
        return;
    snprintf( buf, sizeof( buf ), "%c's unique relic effects:", label );
    if ( result->relic_damage_reduction > 0 )
    {
        snprintf( part, sizeof( part ), " all damage -%d%%",
                  result->relic_damage_reduction );
        toc_strlcat( buf, part, sizeof( buf ) );
    }
    if ( result->relic_nonphysical_reduction > 0 )
    {
        snprintf( part, sizeof( part ), " magic damage -%d%%",
                  result->relic_nonphysical_reduction );
        toc_strlcat( buf, part, sizeof( buf ) );
    }
    if ( result->relic_movement_reduction > 0 )
    {
        snprintf( part, sizeof( part ), " walking -%d%% moves",
                  result->relic_movement_reduction );
        toc_strlcat( buf, part, sizeof( buf ) );
    }
    if ( result->relic_kill_heal > 0 )
    {
        snprintf( part, sizeof( part ), " heals about %d hp a kill",
                  result->relic_kill_heal );
        toc_strlcat( buf, part, sizeof( buf ) );
    }
    toc_strlcat( buf, ".\n\r", sizeof( buf ) );
    send_to_char( buf, ch );
}

/* "Your damage: weapons." or "Your damage: 85% spells (acid blast), ..." */
static void gear_send_damage_source( CHAR_DATA *ch,
                                     const GEAR_PROFILE *profile )
{
    char buf[MAX_STRING_LENGTH];

    if ( profile->spell_share <= 0.0 )
        toc_strlcpy( buf, "Your damage comes from weapons.\n\r", sizeof( buf ) );
    else
        snprintf( buf, sizeof( buf ),
                  "Your damage: %.0f%% spells (%s), %.0f%% weapons.\n\r",
                  profile->spell_share * 100.0,
                  skill_table[profile->spell_sn].name,
                  (1.0 - profile->spell_share) * 100.0 );
    send_to_char( buf, ch );
}

/* "4.0% more damage, 1.2% less tough" -- the winner over the loser. */
static void gear_describe_gain( const GEAR_PROFILE *profile,
                                const GEAR_RESULT *win,
                                const GEAR_RESULT *lose,
                                char *out, size_t size )
{
    double damage = gear_damage_change( profile, win, lose ) * 100.0;
    double tough = gear_tough_change( win, lose ) * 100.0;
    bool damage_moves = fabs( damage ) >= GEAR_EVEN * 100.0;
    bool tough_moves = fabs( tough ) >= GEAR_EVEN * 100.0;

    if ( damage_moves && tough_moves )
        snprintf( out, size, "%.1f%% %s damage, %.1f%% %s",
                  UMIN( 999.9, fabs( damage ) ), damage > 0 ? "more" : "less",
                  UMIN( 999.9, fabs( tough ) ),
                  tough > 0 ? "tougher" : "less tough" );
    else if ( damage_moves )
        snprintf( out, size, "%.1f%% %s damage",
                  UMIN( 999.9, fabs( damage ) ), damage > 0 ? "more" : "less" );
    else if ( tough_moves )
        snprintf( out, size, "same damage, %.1f%% %s",
                  UMIN( 999.9, fabs( tough ) ),
                  tough > 0 ? "tougher" : "less tough" );
    else
        toc_strlcpy( out, "no real difference", size );
}

static void gear_send_verdict( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                               OBJ_DATA *obj1, OBJ_DATA *obj2,
                               const GEAR_RESULT *a, const GEAR_RESULT *b,
                               bool usable1, bool usable2,
                               const char *why1, const char *why2,
                               bool defense )
{
    char buf[MAX_STRING_LENGTH];
    char detail[MAX_INPUT_LENGTH];
    double score;

    if ( !usable1 && !usable2 )
    {
        send_to_char( "Verdict: you can use neither of them yet.\n\r", ch );
        return;
    }
    if ( !usable1 || !usable2 )
    {
        snprintf( buf, sizeof( buf ),
                  "Verdict: %c, because you cannot use %c yet (%s).\n\r",
                  usable1 ? 'A' : 'B', usable1 ? 'B' : 'A',
                  usable1 ? why2 : why1 );
        send_to_char( buf, ch );
        return;
    }

    score = gear_score( profile, a, b, defense );
    if ( fabs( score ) <= GEAR_EVEN )
    {
        send_to_char( "Verdict: no real difference -- wear whichever you like.\n\r", ch );
        return;
    }
    if ( score > 0 )
        gear_describe_gain( profile, a, b, detail, sizeof( detail ) );
    else
        gear_describe_gain( profile, b, a, detail, sizeof( detail ) );
    snprintf( buf, sizeof( buf ), "Verdict: %c, %s -- %s.\n\r",
              score > 0 ? 'A' : 'B',
              score > 0 ? obj1->short_descr
                        : obj2 != NULL ? obj2->short_descr : "nothing",
              detail );
    send_to_char( buf, ch );
}

static void gear_send_item( CHAR_DATA *ch, char label, OBJ_DATA *obj,
                            bool usable, const char *why )
{
    char buf[MAX_STRING_LENGTH];

    snprintf( buf, sizeof( buf ), "%c) %s (level %d)%s%s%s\n\r",
              label, obj->short_descr, obj->level,
              obj->wear_loc != WEAR_NONE ? ", worn" : "",
              usable ? "" : " -- can't use: ", usable ? "" : why );
    send_to_char( buf, ch );
}

/* ------------------------------------------------------------------ */
/* COMPARE PROFILE: how your damage is made                            */
/* ------------------------------------------------------------------ */

static void gear_send_profile( CHAR_DATA *ch, const GEAR_PROFILE *profile )
{
    char buf[MAX_STRING_LENGTH];
    GEAR_LOADOUT now;
    GEAR_RESULT result;
    OBJ_DATA *weapon;

    gear_loadout_from_char( ch, &now );
    gear_measure( ch, profile, &now, &result );
    weapon = get_eq_char( ch, WEAR_WIELD );

    gear_send_damage_source( ch, profile );
    if ( weapon != NULL && weapon->item_type == ITEM_WEAPON )
        snprintf( buf, sizeof( buf ), "Weapon: %s, %dd%d, your skill %d%%.\n\r",
                  weapon->short_descr, weapon->value[1], weapon->value[2],
                  result.weapon_skill );
    else
        snprintf( buf, sizeof( buf ), "Weapon: bare hands, your skill %d%%.\n\r",
                  result.weapon_skill );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "Each round: %.1f swings, %.0f%% land, %.1f a hit: %.1f damage.\n\r",
              result.attacks, result.hit_chance * 100.0, result.per_hit,
              result.melee );
    send_to_char( buf, ch );
    snprintf( buf, sizeof( buf ),
              "Hitroll %+d and damroll %+d, counting strength.\n\r",
              result.hitroll, result.damroll );
    send_to_char( buf, ch );
    if ( profile->spell_share > 0.0 )
    {
        snprintf( buf, sizeof( buf ),
                  "Spells: %d mana is %d casts of %s; %.0f counting regen.\n\r",
                  result.max_mana, result.casts,
                  skill_table[profile->spell_sn].name, result.spell );
        send_to_char( buf, ch );
    }
    snprintf( buf, sizeof( buf ),
              "Toughness: %.0f effective hp (hp %d, AC %d, save %+d).\n\r",
              result.toughness, result.max_hit, result.average_ac,
              result.saving_throw );
    send_to_char( buf, ch );
    send_to_char( "COMPARE ranks gear by damage first; toughness settles close calls.\n\r", ch );
}

/* ------------------------------------------------------------------ */
/* COMPARE UPGRADES: the gear finder, for this character               */
/* ------------------------------------------------------------------ */

typedef struct gear_upgrade
{
    OBJ_INDEX_DATA *pObj;
    MOB_INDEX_DATA *pMob;
    AREA_DATA *area;
    int level;
    int slot;
    double score;
    char gain[MAX_INPUT_LENGTH];
} GEAR_UPGRADE;

typedef struct gear_slot_state
{
    int slot;
    GEAR_LOADOUT base;
    GEAR_RESULT now;
} GEAR_SLOT_STATE;

static const struct
{
    const char *name;
    int first;
    int second;
} gear_groups[] = {
    { "light",    WEAR_LIGHT,    -1 },
    { "finger",   WEAR_FINGER_L, WEAR_FINGER_R },
    { "neck",     WEAR_NECK_1,   WEAR_NECK_2 },
    { "body",     WEAR_BODY,     -1 },
    { "head",     WEAR_HEAD,     -1 },
    { "legs",     WEAR_LEGS,     -1 },
    { "feet",     WEAR_FEET,     -1 },
    { "hands",    WEAR_HANDS,    -1 },
    { "arms",     WEAR_ARMS,     -1 },
    { "off hand", WEAR_SHIELD,   -1 },
    { "about",    WEAR_ABOUT,    -1 },
    { "waist",    WEAR_WAIST,    -1 },
    { "wrist",    WEAR_WRIST_L,  WEAR_WRIST_R },
    { "wield",    WEAR_WIELD,    -1 },
    { "held",     WEAR_HOLD,     -1 }
};
#define GEAR_GROUP_COUNT \
    ((int)(sizeof( gear_groups ) / sizeof( gear_groups[0] )))

static int gear_group_lookup( const char *arg )
{
    static const struct { const char *alias; const char *group; } aliases[] = {
        { "ring", "finger" }, { "rings", "finger" }, { "amulet", "neck" },
        { "necklace", "neck" }, { "armor", "body" }, { "armour", "body" },
        { "helm", "head" }, { "helmet", "head" }, { "boots", "feet" },
        { "gloves", "hands" }, { "shield", "off hand" },
        { "offhand", "off hand" }, { "off", "off hand" },
        { "secondary", "off hand" }, { "cloak", "about" },
        { "belt", "waist" }, { "bracer", "wrist" }, { "bracers", "wrist" },
        { "weapon", "wield" }, { "main", "wield" }, { "hold", "held" }
    };
    const char *name = arg;
    int i;

    for ( i = 0; i < (int)(sizeof( aliases ) / sizeof( aliases[0] )); i++ )
        if ( !str_cmp( arg, aliases[i].alias ) )
        {
            name = aliases[i].group;
            break;
        }
    for ( i = 0; i < GEAR_GROUP_COUNT; i++ )
        if ( !str_prefix( name, gear_groups[i].name ) )
            return i;
    return -1;
}

/*
 * The object a reset would make, without making it: create_object would
 * put it in object_list, count it against its limit and advance max-load
 * bookkeeping, all for a figure.  Only what the measurement reads is
 * filled in, and nothing outlives the call.
 *
 * A level -1 prototype takes its level from what loads it, as
 * create_object and reset_area decide: the mobile's level less two, or
 * a shopkeeper's by item type, never above 52.  Weapon dice and armour
 * follow that level, using the commonest of create_object's weapon rolls.
 */
static void gear_object_from_index( OBJ_DATA *obj, OBJ_INDEX_DATA *pObj,
                                    MOB_INDEX_DATA *pMob )
{
    int level;
    int i;

    memset( obj, 0, sizeof( *obj ) );
    obj->pIndexData = pObj;
    obj->name = pObj->name;
    obj->short_descr = pObj->short_descr;
    obj->description = pObj->description;
    obj->item_type = pObj->item_type;
    obj->extra_flags = pObj->extra_flags;
    obj->extra_flags2 = pObj->extra_flags2;
    obj->wear_flags = pObj->wear_flags;
    obj->wear_loc = WEAR_NONE;
    obj->weight = pObj->weight;
    obj->cost = pObj->cost;
    obj->condition = pObj->condition;
    obj->material = pObj->material;
    for ( i = 0; i < 5; i++ )
        obj->value[i] = pObj->value[i];

    if ( pObj->level != -1 )
    {
        obj->level = pObj->level;
        return;
    }
    if ( pMob->pShop != NULL )
        level = (pObj->item_type == ITEM_WEAPON
                 || pObj->item_type == ITEM_ARMOR) ? 10 : 0;
    else
        level = URANGE( 0, pMob->level - 2, LEVEL_HERO2 - 1 );
    level = UMIN( level, 52 );
    obj->level = (sh_int)level;
    if ( pObj->item_type == ITEM_WEAPON )
    {
        obj->value[1] = dice_thrown[level];
        obj->value[2] = dice_size[level];
    }
    else if ( pObj->item_type == ITEM_ARMOR )
        for ( i = 0; i < 3; i++ )
            obj->value[i] = level / 5 + 3;
}

/*
 * Whether a reset puts something in a player's hands to keep.  Rot-death
 * gear crumbles a few ticks after its carrier dies, inventory-flagged
 * items on anything but a shopkeeper go with the corpse, staff rooms are
 * not the world, and Mud School turns away anyone past newbie level.
 */
static bool gear_reset_yields_gear( CHAR_DATA *ch, OBJ_INDEX_DATA *pObj,
                                    MOB_INDEX_DATA *pMob,
                                    ROOM_INDEX_DATA *pRoom )
{
    if ( pObj == NULL || pMob == NULL )
        return false;
    if ( IS_SET( pObj->extra_flags, ITEM_ROT_DEATH ) )
        return false;
    if ( IS_SET( pObj->extra_flags, ITEM_INVENTORY ) && pMob->pShop == NULL )
        return false;
    if ( pRoom != NULL )
    {
        if ( IS_SET( pRoom->room_flags, ROOM_IMP_ONLY | ROOM_GODS_ONLY ) )
            return false;
        if ( IS_SET( pRoom->room_flags, ROOM_NEWBIES_ONLY )
            && ch->level > LEVEL_NEWBIE )
            return false;
    }
    return pObj->item_type == ITEM_LIGHT
        || gear_natural_wear_flag( pObj->wear_flags ) != 0;
}

static void gear_prepare_slot( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                               int slot, GEAR_SLOT_STATE *state )
{
    GEAR_LOADOUT now;
    OBJ_DATA *worn = get_eq_char( ch, slot );

    state->slot = slot;
    gear_base_loadout( ch, worn, NULL, slot, &state->base );
    gear_put_on( ch, &state->base, worn, slot, &now );
    gear_measure( ch, profile, &now, &state->now );
}

/* Keep the best GEAR_UPGRADE_TOP, one entry per prototype, best first. */
static void gear_keep_upgrade( GEAR_UPGRADE *list, int *count,
                               const GEAR_UPGRADE *found )
{
    int i;
    int at;

    for ( i = 0; i < *count; i++ )
        if ( list[i].pObj == found->pObj )
        {
            if ( found->score < list[i].score
                || (found->score == list[i].score
                    && found->pMob->level >= list[i].pMob->level) )
                return;
            for ( ; i < *count - 1; i++ )
                list[i] = list[i + 1];
            (*count)--;
            break;
        }

    for ( at = 0; at < *count; at++ )
        if ( found->score > list[at].score )
            break;
    if ( at >= GEAR_UPGRADE_TOP )
        return;
    if ( *count < GEAR_UPGRADE_TOP )
        (*count)++;
    for ( i = *count - 1; i > at; i-- )
        list[i] = list[i - 1];
    list[at] = *found;
}

/*
 * Every piece of gear a mobile carries or wears, through the same
 * measurement as COMPARE, in place of what this character wears in the
 * slot it would go to.  Only what they could put on today counts.
 */
static void gear_find_upgrades( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                                int only_group, bool defense,
                                GEAR_UPGRADE best[][GEAR_UPGRADE_TOP],
                                int found[] )
{
    static GEAR_SLOT_STATE states[GEAR_GROUP_COUNT][2];
    AREA_DATA *pArea;
    RESET_DATA *pReset;
    MOB_INDEX_DATA *pMob;
    ROOM_INDEX_DATA *pRoom;
    OBJ_INDEX_DATA *pObj;
    OBJ_DATA candidate;
    GEAR_LOADOUT loadout;
    GEAR_RESULT result;
    GEAR_UPGRADE entry;
    char why[MAX_INPUT_LENGTH];
    double score;
    int g;
    int side;
    int slot;

    for ( g = 0; g < GEAR_GROUP_COUNT; g++ )
    {
        found[g] = 0;
        if ( only_group >= 0 && g != only_group )
            continue;
        gear_prepare_slot( ch, profile, gear_groups[g].first, &states[g][0] );
        if ( gear_groups[g].second >= 0 )
            gear_prepare_slot( ch, profile, gear_groups[g].second,
                               &states[g][1] );
    }

    for ( pArea = area_first; pArea != NULL; pArea = pArea->next )
    {
        pMob = NULL;
        pRoom = NULL;
        for ( pReset = pArea->reset_first; pReset != NULL;
              pReset = pReset->next )
        {
            if ( pReset->command == 'M' )
            {
                pMob = get_mob_index( pReset->arg1 );
                pRoom = get_room_index( pReset->arg3 );
                continue;
            }
            if ( pReset->command != 'G' && pReset->command != 'E' )
                continue;

            pObj = get_obj_index( pReset->arg1 );
            if ( !gear_reset_yields_gear( ch, pObj, pMob, pRoom ) )
                continue;
            gear_object_from_index( &candidate, pObj, pMob );
            if ( candidate.level > ch->level )
                continue;

            for ( g = 0; g < GEAR_GROUP_COUNT; g++ )
            {
                if ( (only_group >= 0 && g != only_group)
                    || !gear_item_fits( &candidate, gear_groups[g].first ) )
                    continue;
                for ( side = 0; side < 2; side++ )
                {
                    slot = side == 0 ? gear_groups[g].first
                                     : gear_groups[g].second;
                    if ( slot < 0 )
                        break;
                    if ( !gear_item_usable( ch, &candidate, slot, why,
                                            sizeof( why ) ) )
                        continue;
                    gear_put_on( ch, &states[g][side].base, &candidate, slot,
                                 &loadout );
                    gear_measure( ch, profile, &loadout, &result );
                    score = gear_score( profile, &result,
                                        &states[g][side].now, defense );
                    if ( score <= GEAR_EVEN )
                        continue;
                    entry.pObj = pObj;
                    entry.pMob = pMob;
                    entry.area = pArea;
                    entry.level = candidate.level;
                    entry.slot = slot;
                    entry.score = score;
                    gear_describe_gain( profile, &result, &states[g][side].now,
                                        entry.gain, sizeof( entry.gain ) );
                    gear_keep_upgrade( best[g], &found[g], &entry );
                }
            }
        }
    }
}

static void gear_upgrade_source( const GEAR_UPGRADE *u, char *out,
                                 size_t size )
{
    char area[128];

    quest_area_name( u->area->name, area, sizeof( area ) );
    snprintf( out, size, "%s %s in %s",
              u->pMob->pShop != NULL ? "sold by" : "from",
              u->pMob->short_descr, area );
}

static void gear_send_upgrades( CHAR_DATA *ch, const GEAR_PROFILE *profile,
                                bool defense, int only_group )
{
    static GEAR_UPGRADE best[GEAR_GROUP_COUNT][GEAR_UPGRADE_TOP];
    int found[GEAR_GROUP_COUNT];
    char buf[MAX_STRING_LENGTH];
    char source[512];
    char none[MAX_STRING_LENGTH];
    OBJ_DATA *worn;
    OBJ_DATA *other;
    int g;
    int i;

    gear_find_upgrades( ch, profile, only_group, defense, best, found );

    if ( only_group < 0 )
    {
        snprintf( buf, sizeof( buf ), "Best upgrade you can get for each slot%s:\n\r",
                  defense ? ", for toughness" : "" );
        send_to_char( buf, ch );
        none[0] = '\0';
        for ( g = 0; g < GEAR_GROUP_COUNT; g++ )
        {
            if ( found[g] == 0 )
            {
                if ( none[0] != '\0' )
                    toc_strlcat( none, ", ", sizeof( none ) );
                toc_strlcat( none, gear_groups[g].name, sizeof( none ) );
                continue;
            }
            snprintf( buf, sizeof( buf ), " %-8s %s (L%d): %s\n\r",
                      gear_groups[g].name, best[g][0].pObj->short_descr,
                      best[g][0].level, best[g][0].gain );
            send_to_char( buf, ch );
        }
        if ( none[0] != '\0' )
        {
            snprintf( buf, sizeof( buf ),
                      "Nothing you can get beats your %s.\n\r", none );
            send_to_char( buf, ch );
        }
        send_to_char( "COMPARE UPGRADES <slot> shows the top five and where to find them.\n\r",
                      ch );
        return;
    }

    g = only_group;
    worn = get_eq_char( ch, gear_groups[g].first );
    other = gear_groups[g].second >= 0
        ? get_eq_char( ch, gear_groups[g].second ) : NULL;
    if ( gear_groups[g].second >= 0 )
        snprintf( buf, sizeof( buf ), "Your %s: %s and %s.\n\r",
                  gear_groups[g].name,
                  worn != NULL ? worn->short_descr : "nothing",
                  other != NULL ? other->short_descr : "nothing" );
    else
        snprintf( buf, sizeof( buf ), "Your %s: %s.\n\r", gear_groups[g].name,
                  worn != NULL ? worn->short_descr : "nothing" );
    send_to_char( buf, ch );

    if ( found[g] == 0 )
    {
        send_to_char( "Nothing you can get today beats it.\n\r", ch );
        return;
    }
    for ( i = 0; i < found[g]; i++ )
    {
        snprintf( buf, sizeof( buf ), " %d. %s (L%d): %s\n\r", i + 1,
                  best[g][i].pObj->short_descr, best[g][i].level,
                  best[g][i].gain );
        send_to_char( buf, ch );
        gear_upgrade_source( &best[g][i], source, sizeof( source ) );
        worn = get_eq_char( ch, best[g][i].slot );
        if ( gear_groups[g].second >= 0 && worn != NULL )
            snprintf( buf, sizeof( buf ), "    %s; replaces %s\n\r",
                      source, worn->short_descr );
        else
            snprintf( buf, sizeof( buf ), "    %s\n\r", source );
        send_to_char( buf, ch );
    }
}

/* ------------------------------------------------------------------ */
/* The command                                                         */
/* ------------------------------------------------------------------ */

static void gear_send_usage( CHAR_DATA *ch )
{
    send_to_char( "COMPARE <item> [item]     A against B, or against what you wear\n\r", ch );
    send_to_char( "COMPARE UPGRADES [slot]   the best gear you can get today\n\r", ch );
    send_to_char( "COMPARE PROFILE           how your damage is made\n\r", ch );
    send_to_char( "Add DEFENSE first to rank by toughness instead of damage.\n\r", ch );
}

void do_compare( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    char why1[MAX_INPUT_LENGTH];
    char why2[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    OBJ_DATA *obj1;
    OBJ_DATA *obj2;
    GEAR_PROFILE profile;
    GEAR_RESULT a;
    GEAR_RESULT b;
    bool usable1;
    bool usable2;
    bool defense = false;
    int group;
    int slot;
    int i;

    if ( IS_NPC( ch ) )
    {
        send_to_char( "Only players can compare gear.\n\r", ch );
        return;
    }

    argument = one_argument( argument, arg1 );
    if ( !str_cmp( arg1, "defense" ) || !str_cmp( arg1, "defence" )
        || !str_cmp( arg1, "tank" ) )
    {
        defense = true;
        argument = one_argument( argument, arg1 );
    }
    if ( arg1[0] == '\0' || !str_cmp( arg1, "help" ) )
    {
        gear_send_usage( ch );
        return;
    }

    gear_build_profile( ch, &profile );

    if ( !str_cmp( arg1, "profile" ) )
    {
        gear_send_profile( ch, &profile );
        return;
    }

    if ( !str_cmp( arg1, "upgrades" ) || !str_cmp( arg1, "upgrade" ) )
    {
        one_argument( argument, arg2 );
        group = -1;
        if ( arg2[0] != '\0' && (group = gear_group_lookup( arg2 )) < 0 )
        {
            send_to_char( "Slots: light, finger, neck, body, head, legs, feet, hands, arms,\n\r"
                          "off hand, about, waist, wrist, wield, held.\n\r", ch );
            return;
        }
        gear_send_upgrades( ch, &profile, defense, group );
        return;
    }

    one_argument( argument, arg2 );
    if ( (obj1 = get_obj_carry( ch, arg1 )) == NULL
        && (obj1 = get_obj_wear( ch, arg1 )) == NULL )
    {
        send_to_char( "You do not have that item.\n\r", ch );
        return;
    }
    if ( arg2[0] != '\0' )
    {
        if ( (obj2 = get_obj_carry( ch, arg2 )) == NULL
            && (obj2 = get_obj_wear( ch, arg2 )) == NULL )
        {
            send_to_char( "You do not have the second item.\n\r", ch );
            return;
        }
    }
    else
        obj2 = gear_find_worn_match( ch, &profile, obj1, defense );

    /* Nothing worn where it goes: weigh it against the empty slot. */
    slot = WEAR_NONE;
    if ( obj2 == NULL && arg2[0] == '\0' )
    {
        for ( i = 0; i < GEAR_SLOT_COUNT; i++ )
            if ( get_eq_char( ch, gear_all_slots[i] ) == NULL
                && gear_item_fits( obj1, gear_all_slots[i] )
                && !(gear_all_slots[i] == WEAR_SHIELD
                     && obj1->item_type == ITEM_WEAPON) )
            {
                slot = gear_all_slots[i];
                break;
            }
        if ( slot == WEAR_NONE )
        {
            act( "$p is not something you can wear.", ch, obj1, NULL, TO_CHAR );
            return;
        }
    }
    else
    {
        if ( obj1 == obj2 )
        {
            act( "$p is exactly as good as itself.", ch, obj1, NULL, TO_CHAR );
            return;
        }
        if ( obj1->wear_loc != WEAR_NONE && obj2->wear_loc != WEAR_NONE
            && obj1->wear_loc != obj2->wear_loc
            && gear_pair_partner( obj1->wear_loc ) != obj2->wear_loc )
        {
            send_to_char( "You wear those in different slots, so neither replaces the other.\n\r", ch );
            return;
        }
        if ( (slot = gear_choose_slot( obj1, obj2 )) == WEAR_NONE )
        {
            send_to_char( "Those don't go in the same slot.\n\r", ch );
            return;
        }
    }

    gear_evaluate( ch, &profile, obj1, obj2, slot, &a, &b );
    usable1 = gear_item_usable( ch, obj1, slot, why1, sizeof( why1 ) );
    usable2 = obj2 == NULL
        || gear_item_usable( ch, obj2, slot, why2, sizeof( why2 ) );

    gear_send_item( ch, 'A', obj1, usable1, why1 );
    if ( obj2 != NULL )
        gear_send_item( ch, 'B', obj2, usable2, why2 );
    else
        send_to_char( "B) nothing -- the slot is empty\n\r", ch );
    snprintf( buf, sizeof( buf ), "Slot: %s.  ", gear_slot_name( slot ) );
    send_to_char( buf, ch );
    gear_send_damage_source( ch, &profile );
    send_to_char( "                           A         B\n\r", ch );
    if ( profile.spell_share < 1.0 )
        gear_send_row( ch, "Weapon dmg/round", a.melee, b.melee, false );
    if ( profile.spell_share > 0.0 )
        gear_send_row( ch, "Mana to cast", a.spell, b.spell, true );
    gear_send_row( ch, "Toughness", a.toughness, b.toughness, true );
    gear_send_changes( ch, obj1, obj2, &a, &b );
    gear_send_relic_facts( ch, 'A', &a );
    gear_send_relic_facts( ch, 'B', &b );
    gear_send_verdict( ch, &profile, obj1, obj2, &a, &b, usable1, usable2,
                       why1, why2, defense );
}
