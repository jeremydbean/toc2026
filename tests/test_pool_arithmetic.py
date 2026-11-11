"""Arithmetic on pools that reach POOL_MAX (review, 2026-11-11).

Hit points, mana and endurance were widened to int with a ceiling of a
billion, but the arithmetic on them was not: 100 * hit overflowed an int at
21 million, so a character at 30,000,000 of 30,000,000 was described by
LOOK as dying, and divine protection's max * 3 / 4, a servant's share of
its maker's health and the combat prompts overflowed further up. Every
multiply on a pool now goes through combat_rules.c's pool_percent,
pool_scale and pool_at_most, worked in long long.

The same review found SET CHAR reading a number that would not parse as
-1, which HP accepted: `set char x hp 999999999999999999999999` set the
maximum to -1. A numeric field now refuses it before anything changes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc")
PW = "Zpoolarpass11"
TEMPLE = 4207
LAVA_PIT = 32708          # the fixture world's volcanic room
POOL_MAX = 1_000_000_000

HARNESS = r"""
#include <limits.h>
#include <stdio.h>
#include "combat_rules.h"

static int failures;
static void check( const char *name, long long got, long long want )
{
    if ( got != want )
    {
        printf( "FAIL %s: %lld, wanted %lld\n", name, got, want );
        failures++;
    }
    else
        printf( "ok %s\n", name );
}

int main( void )
{
    const int big = 1000000000;

    check( "percent_ordinary", pool_percent( 50, 200 ), 25 );
    check( "percent_30m_full", pool_percent( 30000000, 30000000 ), 100 );
    check( "percent_max_full", pool_percent( big, big ), 100 );
    check( "percent_max_half", pool_percent( big / 2, big ), 50 );
    check( "percent_negative", pool_percent( -10, 100 ), -10 );
    check( "percent_no_max", pool_percent( 5, 0 ), 0 );
    check( "percent_past_int", pool_percent( INT_MAX, 1 ), INT_MAX );
    check( "scale_three_quarters", pool_scale( big, 3, 4, INT_MAX ), 750000000 );
    check( "scale_30m", pool_scale( 30000000, 3, 4, INT_MAX ), 22500000 );
    check( "scale_ordinary", pool_scale( 1000, 3, 2, big ), 1500 );
    check( "scale_capped", pool_scale( big, 3, 1, big ), big );
    check( "scale_negative_capped", pool_scale( -(long long) big, 3, 1, big ), -big );
    check( "scale_no_den", pool_scale( 5, 1, 0, big ), 0 );
    check( "scale_servant", pool_scale( 64LL * 400 + (long long) big * 100, 1, 400, big ),
           64 + 250000000 );
    check( "at_most_twentieth", pool_at_most( 50, big, 1, 20 ), 1 );
    check( "at_most_not", pool_at_most( big, big, 1, 20 ), 0 );
    check( "at_most_edge", pool_at_most( 50000000, big, 1, 20 ), 1 );
    check( "at_most_past_edge", pool_at_most( 50000001, big, 1, 20 ), 0 );
    return failures;
}
"""


def sanitize_flags() -> list[str]:
    """UBSan where the compiler has it, so an overflow fails the harness."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.c"
        probe.write_text("int main(void){return 0;}\n")
        flags = ["-fsanitize=undefined", "-fno-sanitize-recover=all"]
        built = subprocess.run([CC, *flags, "-o", str(Path(tmp) / "probe"), str(probe)],
                               capture_output=True)
        return flags if built.returncode == 0 else []


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class PoolHelperTests(unittest.TestCase):
    def test_the_helpers_under_ubsan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "pool.c"
            source.write_text(HARNESS)
            binary = Path(tmp) / "pool"
            build = subprocess.run(
                [CC, "-std=c17", "-Wall", "-Werror", *sanitize_flags(),
                 "-I", str(ROOT / "src"), "-o", str(binary), str(source),
                 str(ROOT / "src" / "combat_rules.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn("runtime error", run.stderr)


class PoolSourceTests(unittest.TestCase):
    """The old expressions, each of which overflows below POOL_MAX."""

    OLD = {
        "act_info.c": ["( 100 * victim->hit ) / victim->max_hit"],
        "comm.c": ["victim->hit * 100 / victim->max_hit", "ch->hit * 100 / ch->max_hit"],
        "magic2.c": ["lasting_max_hit( ch ) * grade / 400", "victim->max_hit * 3 / 2"],
        "fight.c": ["victim->max_hit * 3 / 4", "victim->max_mana * 3 / 4",
                    "victim->max_move * 3 / 4", "100 * ch->hit/ch->max_hit",
                    "ch->hit * 20 <= ch->max_hit", "fled_on * 20 <= ch->max_hit",
                    "help->max_hit = victim->max_hit * 3;"],
        "interp.c": ["ch->hit * 100 / ch->max_hit"],
        "act_move.c": ["ch->hit * 20 <= ch->max_hit", "guardian->max_hit = ch->max_hit * 3;"],
        "special.c": ["100 * UMAX(0, vch->hit) / vch->max_hit", "4 * mob->hit + mob->max_hit"],
    }

    def test_no_pool_is_multiplied_in_an_int(self) -> None:
        for name, olds in self.OLD.items():
            text = (ROOT / "src" / name).read_text(encoding="latin-1")
            for old in olds:
                self.assertNotIn(old, text, f"{name}: {old}")

    def test_set_refuses_a_number_that_does_not_parse(self) -> None:
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        body = wiz.split("void do_mset( CHAR_DATA *ch, char *argument )", 1)[1].split("\n}\n", 1)[0]
        refuse = body.index("mset_field_is_numeric( arg2 )")
        self.assertLess(refuse, body.index('player_milestone_required( ch, victim, "staffset" )'),
                        "refused before the snapshot")


def stat_pools(staff, name: str) -> tuple[int, int]:
    text = staff.sync(f"stat {name}", timeout=60)
    found = re.search(r"Hp:\s*(-?\d+)/(\d+)", text)
    assert found, text
    return int(found.group(1)), int(found.group(2))


def make(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class PoolLiveTests(unittest.TestCase):
    def test_look_describes_huge_pools_by_their_health(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpoolarstaff", Levl=70, Room=TEMPLE)
            for name, pool in (("Zpoolarsmall", 500), ("Zpoolarbig", 30_000_000),
                               ("Zpoolarmax", POOL_MAX)):
                make(mud, name, Levl=30, Room=TEMPLE,
                     HMV=f"{pool} {pool} 100 100 100 100", HMVP=f"{pool} 100 100")
            with mud.connect(timeout=120) as staff:
                login(staff, "Zpoolarstaff", PW)
                staff.sync("scroll 0")
                others = []
                try:
                    for name in ("Zpoolarsmall", "Zpoolarbig", "Zpoolarmax"):
                        client = mud.connect(timeout=120)
                        client.__enter__()
                        others.append(client)
                        login(client, name, PW)
                        reply = staff.sync(f"look {name.lower()}", timeout=60)
                        self.assertIn("is in excellent condition", reply, name)
                        self.assertNotIn("is dying", reply, name)
                    # Half of a billion reads as half, not as an overflow.
                    staff.must("set char zpoolarmax hp 1000000000", "1000000000")
                    staff.sync("restore zpoolarmax")
                    self.assertEqual(stat_pools(staff, "zpoolarmax"), (POOL_MAX, POOL_MAX))
                finally:
                    for client in others:
                        client.send("quit")
                        client.wait_closed()
                        client.__exit__(None, None, None)
                staff.send("quit")
                staff.wait_closed()

    def test_set_refuses_malformed_numbers_and_keeps_negatives(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpoolarstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrevwide", Levl=30, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zpoolarstaff", PW)
                login(player, "Zrevwide", PW)
                staff.sync("scroll 0")
                staff.must("set char zrevwide hp 40000", "40000")
                before = stat_pools(staff, "zrevwide")[1]
                for field in ("hp", "align", "hitroll", "damroll", "armor"):
                    for bad in ("999999999999999999999999", "12abc", "abc", "-"):
                        reply = staff.sync(f"set char zrevwide {field} {bad}", timeout=60)
                        self.assertIn("takes a whole number", reply, (field, bad))
                self.assertEqual(stat_pools(staff, "zrevwide")[1], before, "nothing changed")
                stat = staff.sync("stat zrevwide", timeout=60)
                # Legitimate negatives still work.
                staff.must("set char zrevwide align -750", "-750")
                staff.must("set char zrevwide hitroll -5", "-5")
                staff.must("set char zrevwide damroll -3", "-3")
                staff.must("set char zrevwide armor -100", "-100")
                stat = staff.sync("stat zrevwide", timeout=60)
                self.assertRegex(stat, r"Align:\s*-750")
                # A text field still reads its text.
                staff.must("set char zrevwide race elf", "elf")
                for client in (player, staff):
                    client.send("quit")
                    client.wait_closed()

    def test_divine_protection_and_a_servant_at_pool_max(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zpoolarstaff", Levl=70, Room=TEMPLE)
            # One hit point of a billion, so the lava pit kills them.
            make(mud, "Zpooldivine", Levl=30, Room=TEMPLE,
                 HMV=f"1 {POOL_MAX} 100 100 100 100", HMVP=f"{POOL_MAX} 100 100")
            # A necromancer of a billion hit points raises a servant.
            make(mud, "Zpoolnecro", Levl=50, Room=TEMPLE, Cla=5,
                 HMV=f"{POOL_MAX} {POOL_MAX} 5000 5000 500 500",
                 HMVP=f"{POOL_MAX} 5000 500")
            with mud.connect(timeout=120) as staff, \
                 mud.connect(timeout=120) as divine, \
                 mud.connect(timeout=120) as necro:
                login(staff, "Zpoolarstaff", PW)
                login(divine, "Zpooldivine", PW)
                login(necro, "Zpoolnecro", PW)
                for client in (staff, divine, necro):
                    client.sync("scroll 0")
                staff.sync("empower zpooldivine", timeout=60)
                self.assertIn("divine protection", divine.sync("affects", timeout=60).lower())
                hit, top = stat_pools(staff, "zpooldivine")
                self.assertEqual(hit, 1)
                staff.sync(f"transfer zpooldivine {LAVA_PIT}", timeout=60)
                divine.expect("spared from death", timeout=120)
                hit, top = stat_pools(staff, "zpooldivine")
                # Three quarters of the maximum at the moment of the save (an
                # empowered maximum carries a few more points than the base).
                self.assertGreater(hit, 700_000_000, "three quarters of a billion, not a wrap")
                self.assertLess(abs(hit - top * 3 // 4), 1000)
                staff.sync(f"transfer zpooldivine {TEMPLE}", timeout=60)

                staff.must("set skill zpoolnecro 'create skeleton' 100", "")
                reply = necro.sync("cast 'create skeleton'", timeout=60)
                self.assertNotIn("Nothing answers", reply)
                stat = staff.sync("stat mob skeleton", timeout=60)
                found = re.search(r"Hp:\s*-?\d+/(\d+)", stat)
                self.assertTrue(found, stat)
                # dice(8, 8) plus a tenth of a billion (grade 40 of 400).
                self.assertGreaterEqual(int(found.group(1)), 100_000_008)
                self.assertLessEqual(int(found.group(1)), 100_000_064)
                for client in (necro, divine, staff):
                    client.send("quit")
                    client.wait_closed()


if __name__ == "__main__":
    unittest.main()
