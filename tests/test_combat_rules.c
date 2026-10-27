/*
 * Exhaustive checks of src/combat_rules.c, built and run by
 * tests/test_combat_rules.py. Each check prints "ok <name>" or
 * "FAIL <name>: <detail>"; the exit status is the number of failures.
 *
 * The old formulas are kept here, as they stood in fight.c, so the
 * harness can show what was wrong with them as well as that the new
 * ones are right.
 */
#include <stdio.h>
#include <stdlib.h>
#include "combat_rules.h"

static int failures = 0;

static void report( const char *name, int ok, const char *detail )
{
    if ( ok )
        printf( "ok %s\n", name );
    else
    {
        printf( "FAIL %s: %s\n", name, detail );
        failures++;
    }
}

/* Stock ROM: thac0 -= 10 * (100 - skill). */
static int old_strike_bonus( int skill )
{
    return 10 * ( 100 - skill );
}

/* The old bands' mean, before number_range's spread. */
static int old_crane_mean( int hp )
{
    if ( hp < 1000 )
        return (int) ( hp * .275 );
    if ( hp < 4000 )
        return (int) ( hp * .125 );
    return (int) ( hp * .065 );
}

int main( void )
{
    char detail[256];
    int skill, hp, level, ok;

    /* The old bonus shrinks as skill grows: mastering backstab made it
       miss more. The harness confirms the bug it replaces. */
    report( "old_strike_bonus_rewards_ignorance",
            old_strike_bonus( 90 ) > old_strike_bonus( 100 )
            && old_strike_bonus( 100 ) == 0, "expected the stock inversion" );

    ok = 1;
    for ( skill = -50; skill <= 150 && ok; skill++ )
    {
        int b = strike_thac0_bonus( skill );

        if ( b < 0 || b > STRIKE_THAC0_BONUS_MAX
        ||   ( skill > -50 && b < strike_thac0_bonus( skill - 1 ) ) )
        {
            snprintf( detail, sizeof(detail), "skill %d gives %d", skill, b );
            ok = 0;
        }
    }
    report( "strike_bonus_bounded_and_never_decreasing", ok, detail );
    report( "strike_bonus_ends", strike_thac0_bonus( 0 ) == 0
            && strike_thac0_bonus( 100 ) == STRIKE_THAC0_BONUS_MAX
            && strike_thac0_bonus( 75 ) == 7, "0, 7 and 10 at 0, 75 and 100" );

    /* The old crane bands fell off two cliffs. */
    report( "old_crane_had_cliffs",
            old_crane_mean( 999 ) > 2 * old_crane_mean( 1000 )
            && old_crane_mean( 3999 ) > old_crane_mean( 4000 ) + 200,
            "expected 274->125 and 499->260" );

    /* New: for every level a monk can dance at, every hit point count up
       to 200,000 -- never decreasing, no step bigger than the share a
       weak foe loses per hit point, capped, and at least 1. */
    ok = 1;
    for ( level = 1; level <= 60 && ok; level++ )
    {
        int previous = crane_dance_mean( 0, level );
        int cap = level * CRANE_CAP_PER_LEVEL;

        if ( previous != 0 )
        {
            snprintf( detail, sizeof(detail), "level %d: hp 0 gives %d", level, previous );
            ok = 0;
        }
        for ( hp = 1; hp <= 200000 && ok; hp++ )
        {
            int m = crane_dance_mean( hp, level );

            if ( m < 1 || m > cap || m < previous || m - previous > 1 )
            {
                snprintf( detail, sizeof(detail),
                          "level %d: hp %d gives %d after %d (cap %d)",
                          level, hp, m, previous, cap );
                ok = 0;
            }
            previous = m;
        }
    }
    report( "crane_continuous_monotonic_capped", ok, detail );

    /* The points it is drawn through: 27.5% of a weak foe, 165 at the
       knee, about 674 at 10,000, capped at 25 a level. */
    report( "crane_shape",
            crane_dance_mean( 400, 50 ) == 110
            && crane_dance_mean( 600, 50 ) == 165
            && crane_dance_mean( 1000, 50 ) == 213
            && crane_dance_mean( 4000, 50 ) == 426
            && crane_dance_mean( 10000, 50 ) == 673
            && crane_dance_mean( 2000000000, 35 ) == 875
            && crane_dance_mean( 2000000000, 50 ) == 1250,
            "expected 110, 165, 213, 426, 673, 875, 1250" );
    snprintf( detail, sizeof(detail), "%d %d %d %d %d %d %d",
              crane_dance_mean( 400, 50 ), crane_dance_mean( 600, 50 ),
              crane_dance_mean( 1000, 50 ), crane_dance_mean( 4000, 50 ),
              crane_dance_mean( 10000, 50 ), crane_dance_mean( 2000000000, 35 ),
              crane_dance_mean( 2000000000, 50 ) );
    printf( "# crane means: %s\n", detail );

    /* The servant budget keeps the pure armies and prices mixes alike. */
    report( "undead_pure_armies",
            5 * UNDEAD_COST_SKELETON <= UNDEAD_BUDGET
            && 6 * UNDEAD_COST_SKELETON > UNDEAD_BUDGET
            && 2 * UNDEAD_COST_WRAITH <= UNDEAD_BUDGET
            && 3 * UNDEAD_COST_WRAITH > UNDEAD_BUDGET
            && UNDEAD_COST_VAMPIRE <= UNDEAD_BUDGET
            && 2 * UNDEAD_COST_VAMPIRE > UNDEAD_BUDGET
            && UNDEAD_COST_VAMPIRE + UNDEAD_COST_SKELETON > UNDEAD_BUDGET
            && UNDEAD_COST_WRAITH + 2 * UNDEAD_COST_SKELETON <= UNDEAD_BUDGET
            && UNDEAD_COST_WRAITH + 3 * UNDEAD_COST_SKELETON > UNDEAD_BUDGET,
            "5 skeletons, 2 wraiths, 1 vampire, or a wraith and 2 skeletons" );

    /* HEAL: flat to 25, then two a level, stopping at 59, never falling. */
    {
        int level, monotonic = 1;

        for ( level = -5; level < 200; level++ )
            if ( heal_spell_amount( level + 1 ) < heal_spell_amount( level ) )
                monotonic = 0;
        report( "heal_amount",
                monotonic
                && heal_spell_amount( 1 ) == 100 && heal_spell_amount( 25 ) == 100
                && heal_spell_amount( 40 ) == 130 && heal_spell_amount( 50 ) == 150
                && heal_spell_amount( 59 ) == 168 && heal_spell_amount( 70 ) == 168
                && heal_spell_amount( 2000000000 ) == 168,
                "100 to 25, 130 at 40, 150 at 50, 168 from 59" );
    }

    /* Smite's wear reaches 0 in a handful of strains, never in one. */
    report( "smite_wear",
            SMITE_WEAR_MIN > 0 && SMITE_WEAR_MAX < 100
            && SMITE_WEAR_MIN <= SMITE_WEAR_MAX,
            "a strain takes more than nothing and less than a whole weapon" );

    /* Weapon mastery: by level, more in the class's own guild, capped. */
    {
        int level, ok = 1;

        for ( level = 0; level < 200; level++ )
        {
            if ( weapon_mastery_percent( level + 1, 1 ) < weapon_mastery_percent( level, 1 )
            ||   weapon_mastery_percent( level + 1, 0 ) < weapon_mastery_percent( level, 0 )
            ||   weapon_mastery_percent( level, 0 ) > weapon_mastery_percent( level, 1 ) )
                ok = 0;
        }
        report( "weapon_mastery",
                ok && weapon_mastery_percent( 0, 1 ) == 0
                && weapon_mastery_percent( 50, 1 ) == 50 * MASTERY_OWN_GUILD
                && weapon_mastery_percent( 50, 0 ) == 50 * MASTERY_OTHER_GUILD
                && weapon_mastery_percent( 200, 1 ) == MASTERY_TOP_LEVEL * MASTERY_OWN_GUILD,
                "never falls, own guild above other, capped at the top level" );
    }

    /* The casters' own spells: a die a level for the class, half for any
       other, capped, below acid blast. */
    report( "caster_spells",
            flamestrike_dice( 50, 1 ) == 50 && lightning_bolt_dice( 50, 1 ) == 50
            && flamestrike_dice( 50, 0 ) == 25 && lightning_bolt_dice( 49, 0 ) == 25
            && flamestrike_dice( 0, 1 ) == 1 && lightning_bolt_dice( -3, 0 ) == 1
            && flamestrike_dice( 500, 1 ) == MASTERY_TOP_LEVEL
            && lightning_bolt_dice( 500, 1 ) == MASTERY_TOP_LEVEL
            && FLAMESTRIKE_SIDES < 12 && LIGHTNING_BOLT_SIDES < 12,
            "a die a level for the class, half for others, smaller dice than d12" );

    return failures;
}
