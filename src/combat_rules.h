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

#endif
