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


/*
 * damage()'s steps on a landed blow, as fight.c wrote them inline until
 * 2026-11-12, so the shared functions can be held to them exactly.
 */
static int inline_wards( int dam, int sanct, int prot, int divine, int evil )
{
    if ( sanct )
        dam /= 2;
    if ( prot && evil )
    {
        if ( !sanct )
            dam -= dam / 4;
        else
            dam -= dam / 16;
    }
    if ( divine )
    {
        if ( !sanct )
            dam -= dam / 4;
        else if ( !prot )
            dam -= dam / 16;
        else
            dam -= dam / 8;
    }
    return dam;
}

/* damage()'s armour cut, the roll's two ends: number_range( reduce, dam ). */
static int inline_armor_low( int dam, int ac, int npc )
{
    int dam_reduce;

    if ( dam <= 1 )
        return dam;
    if ( !npc )
        dam_reduce = dam + ( -100 + ac ) / 12;
    else
        dam_reduce = dam + ( -100 + ac ) / 3;
    if ( dam_reduce < 0 )
        dam_reduce = 1;
    return dam_reduce;
}

/* The mean of number_range( from, to ), by db.c's rules: 0 for (0, 0),
   from when the range holds one value or none, else every value once. */
static double number_range_mean( int from, int to )
{
    long long sum = 0;
    int v;

    if ( from == 0 && to == 0 )
        return 0.0;
    if ( to - from + 1 <= 1 )
        return from;
    for ( v = from; v <= to; v++ )
        sum += v;
    return (double) sum / ( to - from + 1 );
}

/* CONSIDER before 2026-11-12: the armour's mean cut first, then the
   wards as a factor (consider_after_armor, then consider_blow_factor). */
static double old_consider_blow( double blow, int ac, int npc, int sanct )
{
    double low, after;

    if ( blow <= 1.0 )
        after = blow;
    else
    {
        low = blow + ( -100.0 + ac ) / ( npc ? 3.0 : 12.0 );
        if ( low < 1.0 )
            low = 1.0;
        after = ( low + blow ) / 2.0;
    }
    return sanct ? after * 0.5 : after;
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

    /* Swings: a chance is exactly the share of number_percent() (1..100)
       rolls below it, and the preview's expectation adds them up. */
    {
        int c, r, ok = 1;

        for ( c = -10; c <= 200; c++ )
        {
            int below = 0;

            for ( r = 1; r <= 100; r++ )
                if ( r < c )
                    below++;
            if ( swing_chance_percent( c ) != below )
                ok = 0;
        }
        report( "expected_swings",
                ok && expected_swings_x100( 0, 0, 0, 0 ) == 200
                && expected_swings_x100( 100, 0, 0, 0 ) == 249
                && expected_swings_x100( 100, 100, 0, 0 ) == 273
                && expected_swings_x100( 100, 100, 100, 100 ) == 312
                && expected_swings_x100( 75, 75, 0, 0 ) == 200 + 36 + 17,
                "two sure swings, then each extra one a number_percent() chance" );
    }


    /* A landed blow's steps (review, 2026-11-12): the reviewer's case. A
       sanctuaried mobile of armour -20 takes a blow of 100 as 50 before
       its armour, and the armour then cuts up to 40: 10 to 50, 30 on
       average. CONSIDER cut the armour first and halved what was left:
       40. */
    {
        int warded = blow_ward_cut( 100, BLOW_WARD_SANCTUARY );

        snprintf( detail, sizeof( detail ), "ward %d floor %d mean %.2f old %.2f",
                  warded, blow_armor_floor( warded, -20, 1 ),
                  blow_armor_mean( warded, -20, 1 ), old_consider_blow( 100, -20, 1, 1 ) );
        report( "blow_order_sanctuary_then_armor",
                warded == 50 && blow_armor_floor( warded, -20, 1 ) == 10
                && blow_armor_mean( warded, -20, 1 ) == 30.0
                && number_range_mean( inline_armor_low( inline_wards( 100, 1, 0, 0, 0 ), -20, 1 ),
                                      inline_wards( 100, 1, 0, 0, 0 ) ) == 30.0
                && old_consider_blow( 100, -20, 1, 1 ) == 40.0, detail );
    }

    /* The wards are damage()'s arithmetic exactly, every combination. */
    {
        int dam, w, bad = -1;

        for ( dam = -50; dam <= 5000 && bad < 0; dam++ )
            for ( w = 0; w < 16; w++ )
                if ( blow_ward_cut( dam, w )
                     != inline_wards( dam, w & BLOW_WARD_SANCTUARY, w & BLOW_WARD_PROTECT,
                                      w & BLOW_WARD_DIVINE, w & BLOW_WARD_EVIL_FOE ) )
                {
                    bad = dam * 16 + w;
                    break;
                }
        snprintf( detail, sizeof( detail ), "first mismatch at dam*16+wards %d", bad );
        report( "blow_wards_exact", bad < 0, detail );
    }

    /* The armour roll: the floor is damage()'s, and the mean is what
       number_range( floor, dam ) averages -- a positive armour's floor
       above the blow included, and a floor that comes to 0. */
    {
        int dam, ac, npc, ok = 1;

        for ( npc = 0; npc <= 1 && ok; npc++ )
            for ( dam = -5; dam <= 400 && ok; dam++ )
                for ( ac = -420; ac <= 260 && ok; ac += 7 )
                {
                    int low = inline_armor_low( dam, ac, npc );
                    double want = dam > 1 ? number_range_mean( low, dam ) : dam;

                    if ( blow_armor_floor( dam, ac, npc ) != low
                    ||   blow_armor_mean( dam, ac, npc ) != want )
                    {
                        snprintf( detail, sizeof( detail ),
                                  "dam %d ac %d npc %d: floor %d/%d mean %.3f/%.3f",
                                  dam, ac, npc, blow_armor_floor( dam, ac, npc ), low,
                                  blow_armor_mean( dam, ac, npc ), want );
                        ok = 0;
                    }
                }
        report( "blow_armor_roll", ok, ok ? "" : detail );
        report( "blow_armor_edges",
                blow_armor_floor( 3, -100, 1 ) == 1          /* below zero is 1 */
                && blow_armor_floor( 66, -98, 1 ) == 0       /* zero stays zero */
                && blow_armor_mean( 66, -98, 1 ) == 33.0
                && blow_armor_floor( 10, 160, 1 ) == 30      /* above the blow */
                && blow_armor_mean( 10, 160, 1 ) == 30.0
                && blow_armor_mean( 1, -500, 1 ) == 1.0,
                "floors below, at and above the blow" );
    }

    /* Immunity, a shield's own element and its burn. */
    {
        int dam, ok = 1;

        for ( dam = 0; dam <= 3000 && ok; dam++ )
            ok = blow_immunity_cut( dam, BLOW_NORMAL ) == dam
              && blow_immunity_cut( dam, BLOW_IMMUNE ) == 0
              && blow_immunity_cut( dam, BLOW_RESISTANT ) == dam - dam / 3
              && blow_immunity_cut( dam, BLOW_VULNERABLE ) == dam + dam / 2
              && blow_element_shield( dam, 1 ) == dam + dam / 2
              && blow_element_shield( dam, 0 ) == dam
              && blow_reflection( dam ) == (int) ( dam * 0.6 );
        report( "blow_immunity_and_shield", ok, "damage()'s arithmetic" );
    }

    /* The order matters wherever armour cuts: across blows and armours the
       wards-then-armour mean is never above the old armour-then-wards
       estimate, and is below it wherever the floor does not clamp. */
    {
        int dam, ac, ok = 1, below = 0;

        for ( dam = 20; dam <= 1000 && ok; dam += 2 )
            for ( ac = -300; ac <= 100; ac += 10 )
            {
                double now = blow_armor_mean( blow_ward_cut( dam, BLOW_WARD_SANCTUARY ), ac, 1 );
                double old = old_consider_blow( dam, ac, 1, 1 );

                if ( now > old + 0.5 )
                {
                    snprintf( detail, sizeof( detail ), "dam %d ac %d: %.2f over %.2f",
                              dam, ac, now, old );
                    ok = 0;
                    break;
                }
                if ( now < old - 1.0 )
                    below++;
            }
        report( "blow_order_matters", ok && below > 0, ok ? "the old order never overstated" : detail );
    }

    return failures;
}
