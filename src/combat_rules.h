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

#endif
