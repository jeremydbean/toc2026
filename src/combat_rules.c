/*
 * Combat arithmetic with no game state behind it (see combat_rules.h).
 */
#include "combat_rules.h"

/*
 * Backstab and smite used to subtract 10 * (100 - skill) from THAC0, the
 * stock ROM line: the less a character knew the skill the more surely it
 * hit, so anything under about 90% never missed and mastering it at 100%
 * took the bonus away (review, 2026-10-26). The bonus now grows with the
 * skill and stops at STRIKE_THAC0_BONUS_MAX, a tenth of the d20 for each
 * ten points of proficiency.
 */
int strike_thac0_bonus( int skill )
{
    if ( skill < 0 )
        skill = 0;
    if ( skill > 100 )
        skill = 100;
    return skill * STRIKE_THAC0_BONUS_MAX / 100;
}

/* floor(sqrt(n)), exact, for any n a long long holds. */
static long long isqrt_ll( long long n )
{
    long long low = 0;
    long long high = 3037000499LL;     /* floor(sqrt(LLONG_MAX)) */

    if ( n <= 0 )
        return 0;
    while ( low < high )
    {
        long long mid = low + ( high - low + 1 ) / 2;

        if ( mid <= n / mid )
            low = mid;
        else
            high = mid - 1;
    }
    return low;
}

/*
 * Crane dance struck 25-30% of a victim's current hit points below 1,000,
 * 10-15% below 4,000 and 5-8% above, so a foe at 999 took about 275 and
 * one at 1,000 about 125, and one at 3,999 about 500 and one at 4,000
 * about 260 (review, 2026-10-26). The curve is now one line: 27.5% up to
 * CRANE_KNEE_HP (165 there), then 165 * sqrt(hp / 600) -- about 213 at
 * 1,000, 426 at 4,000 and 673 at 10,000, close to the old 650 there --
 * capped at CRANE_CAP_PER_LEVEL a level of the dancer, so a boss or a
 * hero with tens of thousands of hit points loses at most 875 to a level
 * 35 dancer and 1,250 to a level 50 one. Square root: 165^2 / 600 is
 * 45.375, so the mean is sqrt(hp * 45375 / 1000).
 */
int crane_dance_mean( int hp, int level )
{
    long long mean;
    long long cap;

    if ( hp <= 0 )
        return 0;
    if ( hp <= CRANE_KNEE_HP )
        mean = (long long) hp * CRANE_WEAK_PERCENT / 1000;
    else
        mean = isqrt_ll( (long long) hp * 45375 / 1000 );

    cap = (long long) ( level < 1 ? 1 : level ) * CRANE_CAP_PER_LEVEL;
    if ( mean > cap )
        mean = cap;
    if ( mean < 1 )
        mean = 1;
    return (int) mean;
}


/*
 * HEAL's hit points at a casting level. It was a flat 100 from the level a
 * cleric first casts it (23) to the last a mortal reaches, while hit points
 * roughly double from 25 to 50 and Hermie's TITANIC multiplies them by
 * six: a third of a level 25's maximum became a sixth of a level 50's
 * (class review, 2026-10-26). Two more a level above 25, so the spell
 * keeps a share of a growing pool without matching it: 130 at 40, 150 at
 * 50, 168 at 59, and never more however high a potion or a mobile casts.
 */
int heal_spell_amount( int level )
{
    if ( level > HEAL_TOP_LEVEL )
        level = HEAL_TOP_LEVEL;
    if ( level <= HEAL_FLAT_TO )
        return HEAL_BASE;
    return HEAL_BASE + ( level - HEAL_FLAT_TO ) * HEAL_PER_LEVEL;
}


/*
 * Weapon mastery: the percent a warrior's or thief's weapon blow gains from
 * the level, MASTERY_OWN_GUILD a level in the class's own guild and
 * MASTERY_OTHER_GUILD elsewhere. Warriors and thieves fell to a third of the
 * monk's damage and a fifth of a mage's meteors at level 50, with gear
 * equal (class review bench, 2026-10-26).
 */
int weapon_mastery_percent( int level, int own_guild )
{
    if ( level < 1 )
        return 0;
    if ( level > MASTERY_TOP_LEVEL )
        level = MASTERY_TOP_LEVEL;
    return level * ( own_guild ? MASTERY_OWN_GUILD : MASTERY_OTHER_GUILD );
}

/* Flamestrike's number of dice of FLAMESTRIKE_SIDES: the level, to
   MASTERY_TOP_LEVEL, for a cleric; half that for anyone else. It was a
   flat 8d8 (36) at every level. */
int flamestrike_dice( int level, int own_class )
{
    if ( level < 1 )
        level = 1;
    if ( level > MASTERY_TOP_LEVEL )
        level = MASTERY_TOP_LEVEL;
    return own_class ? level : ( level + 1 ) / 2;
}

/* Lightning bolt's number of dice of LIGHTNING_BOLT_SIDES: the level, to
   MASTERY_TOP_LEVEL, for a mage; half that for anyone else. */
int swing_chance_percent( int chance )
{
    if ( chance <= 1 )
        return 0;
    return chance > 101 ? 100 : chance - 1;
}

int expected_swings_x100( int second_skill, int third_skill,
                          int dual_skill, int dual_weapon_skill )
{
    int total = 200;

    total += swing_chance_percent( second_skill / 2 );
    if ( dual_skill > 0 )
        total += swing_chance_percent( ( dual_skill + dual_weapon_skill ) / 5 );
    total += swing_chance_percent( third_skill / 4 );
    return total;
}

int lightning_bolt_dice( int level, int own_class )
{
    if ( level < 1 )
        level = 1;
    if ( level > MASTERY_TOP_LEVEL )
        level = MASTERY_TOP_LEVEL;
    return own_class ? level : ( level + 1 ) / 2;
}
