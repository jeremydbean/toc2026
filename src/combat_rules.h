/*
 * Combat arithmetic with no game state behind it, so it can be tested
 * exhaustively on its own (tests/test_combat_rules.c). fight.c and
 * magic2.c call these; nothing here may include merc.h.
 */
#ifndef COMBAT_RULES_H
#define COMBAT_RULES_H

/* The to-hit bonus a backstab or smite earns from its own proficiency:
   0 at no skill to STRIKE_THAC0_BONUS_MAX at 100%, never decreasing. */
#define STRIKE_THAC0_BONUS_MAX 10
int strike_thac0_bonus( int skill );

/* Crane dance's average blow against a victim with `hp` hit points, by a
   dancer of `level`. Continuous and never decreasing in hp; a weak foe
   loses CRANE_WEAK_PERCENT of its health, a strong one a shrinking share,
   and no blow is larger than CRANE_CAP_PER_LEVEL a level. */
#define CRANE_WEAK_PERCENT   275    /* tenths of a percent: 27.5% */
#define CRANE_KNEE_HP        600    /* where the share starts to shrink */
#define CRANE_CAP_PER_LEVEL  25
int crane_dance_mean( int hp, int level );

/* Undead servants share one budget (owner, 2026-10-26): a skeleton costs
   2, a wraith 5, a vampire 10, against UNDEAD_BUDGET. */
#define UNDEAD_BUDGET        10
#define UNDEAD_COST_SKELETON 2
#define UNDEAD_COST_WRAITH   5
#define UNDEAD_COST_VAMPIRE  10

/* Smite strains its weapon: on the 3% roll after a smite lands, the
   weapon loses this much condition, and breaks only at 0 -- about four
   strains from new. */
#define SMITE_WEAR_MIN 15
#define SMITE_WEAR_MAX 35

/* HEAL's hit points at a casting level: HEAL_BASE through HEAL_FLAT_TO,
   HEAL_PER_LEVEL more a level above it, no further than HEAL_TOP_LEVEL.
   A caster who is not a cleric heals two thirds of it. */
#define HEAL_BASE       100
#define HEAL_FLAT_TO    25
#define HEAL_PER_LEVEL  2
#define HEAL_TOP_LEVEL  59
int heal_spell_amount( int level );

/* Weapon mastery (class review, 2026-10-27; owner: bring the main classes
   up to the strongest rather than cut the strongest down). A warrior's or
   thief's ordinary weapon blow -- not a backstab, which multiplies itself
   -- gains this percent of the weapon's own damage a level, more in the
   class's own guild, so the specialist stays ahead of the hybrid. Damroll
   is added after, unmultiplied, so gear does not run away with it. */
#define MASTERY_OWN_GUILD     4
#define MASTERY_OTHER_GUILD   3
#define MASTERY_TOP_LEVEL     59
int weapon_mastery_percent( int level, int own_guild );

/* The casters' own attack spells, which every member of the class keeps in
   any guild, grow with the caster: flamestrike (clerics) is level d
   FLAMESTRIKE_SIDES and lightning bolt (mages) level d LIGHTNING_BOLT_SIDES,
   both at most MASTERY_TOP_LEVEL levels deep -- below acid blast's level
   d12 and a mage's meteors, which stay the top of the scale. A caster of
   another class (a warrior in the clerics' guild) rolls half the dice:
   a hybrid that also has weapon mastery must not out-hit the specialist. */
#define FLAMESTRIKE_SIDES     9
#define LIGHTNING_BOLT_SIDES  10
int flamestrike_dice( int level, int own_class );
int lightning_bolt_dice( int level, int own_class );

/* Swings a round as multi_hit rolls them for a player who is not hasted
   (review, 2026-10-27: GAINLIST PREVIEW counted second and third attack
   as whole sure swings). Two are sure; each extra one is a
   number_percent() < chance roll, which lands chance - 1 times in a
   hundred: second attack at skill/2, dual wield at (dual + the off-hand
   weapon's skill)/5 with a weapon held there, third attack at skill/4.
   In hundredths: at full skill a warrior expects 273, 312 dual-wielding. */
int swing_chance_percent( int chance );
int expected_swings_x100( int second_skill, int third_skill,
                          int dual_skill, int dual_weapon_skill );

/* Pool arithmetic in a wide type (review, 2026-11-11). Hit points, mana and
   endurance reach POOL_MAX (a billion) now, so 100 * hit overflowed an int
   at 21 million: a character at 30 million of 30 million read as dying.
   Every multiply on a pool goes through these, worked in long long and
   brought back into an int's range. */

/* current as a percentage of maximum, 0 when maximum is not above 0,
   held to [INT_MIN, INT_MAX]. */
int pool_percent( long long current, long long maximum );

/* value * num / den, truncated toward zero as C's own division is, held to
   [-ceiling, ceiling]; den <= 0 gives 0. */
int pool_scale( long long value, long long num, long long den, int ceiling );

/* current is at most num/den of maximum: current * den <= maximum * num. */
int pool_at_most( long long current, long long maximum, long long num, long long den );

/*
 * damage()'s steps on a blow that got past the defender's ducking, parry,
 * dodge and shield block, in damage()'s order (review, 2026-11-12):
 *
 *   1. the wards: sanctuary, protection from an evil attacker, divine
 *      protection (a mental blow takes psionic_mental_reduce instead);
 *   2. a fire or frost shield: a blow of its own element does half again;
 *   3. alignment_damage_mod, for holy and negative blows;
 *   4. immunity: none, a third off, or half again;
 *   5. armour: number_range( blow_armor_floor(), dam ) -- a fixed cut, so
 *      it has to come last of these: armour first made a sanctuaried
 *      foe's blow of 100 against armour -20 read 40 where the fight
 *      averages 30;
 *   6. a Hyrule ring or shield on a player (fight.c).
 *
 * damage() and CONSIDER (blow_landed_expected in fight.c) both run these,
 * so the estimate cannot drift from the fight.
 */
#define BLOW_WARD_SANCTUARY   1
#define BLOW_WARD_PROTECT     2     /* the defender has protection */
#define BLOW_WARD_DIVINE      4
#define BLOW_WARD_EVIL_FOE    8     /* the attacker is evil: protection's cue */
int blow_ward_cut( int dam, int wards );

/* A fire or frost shield's wearer takes half again from its own element. */
int blow_element_shield( int dam, int own_element );

/* check_immune's verdicts, by merc.h's numbers (IS_NORMAL ... IS_VULNERABLE). */
#define BLOW_NORMAL      0
#define BLOW_IMMUNE      1
#define BLOW_RESISTANT   2
#define BLOW_VULNERABLE  3
int blow_immunity_cut( int dam, int verdict );

/* The low end of the armour roll: dam less (100 - ac) a third against a
   mobile, a twelfth against a player, truncated as C divides; below zero
   is 1. A blow of 1 or less is not rolled (the floor is the blow). */
int blow_armor_floor( int dam, int ac, int npc_victim );

/* What number_range( blow_armor_floor(), dam ) averages, number_range's
   rules included: a floor at or above the blow is the floor. */
double blow_armor_mean( int dam, int ac, int npc_victim );

/* A fire or frost shield burns back 60% of a landed blow, truncated. */
int blow_reflection( int dam );

#endif
