"""The play journal's deep bug rows (2026-11-05).

What players report and nothing wrote down: the game hitching (a pulse
past its quarter second, with the phase and the command that took the
time), how a death came about (the killing blow, the biggest blow of the
last minute, the hit points before it, how many foes), things vanishing
from a pack (an object a player held leaving the game, with the command
or update phase that took it), and quests lost to the clock or given up
(the target, how many of it the world still holds, whether the questor
was in its area).

Synthetic Z characters in the fixture world.
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, LiveMud, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zdeeppass1"
QUESTMASTER = 2497
DAGGER = 3701


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def rows(mud) -> list[list[str]]:
    path = mud.root / "log" / "play.tsv"
    if not path.exists():
        return []
    return [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]


class DeepSourceTests(unittest.TestCase):
    def test_the_hooks_sit_where_the_events_happen(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        loop = comm.split("void game_loop_unix( int control )", 1)[1]
        begin = loop.index("playlog_pulse_begin( );")
        update = loop.index("update_handler( );")
        output = loop.index('playlog_phase_enter( "output" );')
        end = loop.index("playlog_pulse_end( );")
        sleep = loop.index("Synchronize to a clock.")
        self.assertLess(begin, update)
        self.assertLess(update, output)
        self.assertLess(output, end)
        self.assertLess(end, sleep)

        update_c = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        handler = update_c.split("void update_handler( void )", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("playlog_phase =", handler, "every phase is timed through the helper")
        for phase in ("area_update", "mobile_update", "violence_update", "char_update",
                      "obj_update", "aggr_update"):
            self.assertIn(f'playlog_phase_enter( "{phase}" );', handler)

        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertLess(fight.index("victim->hit -= dam;"),
                        fight.index("playlog_blow( ch, victim, dam, dt );"),
                        "just after the subtraction, which is the guard's own statement")
        self.assertIn("playlog_death( ch, victim );", fight)

        handler_c = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        extract = handler_c.split("void extract_obj( OBJ_DATA *obj )", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(extract.index("playlog_obj_gone( obj );"), extract.index("obj_from_char( obj );"),
                        "asked while the object still has a holder")
        quitting = handler_c.split("void extract_obj_player( OBJ_DATA *obj )", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("playlog_obj_gone", quitting, "a quit is not a loss")


class DeepReportTests(unittest.TestCase):
    def test_the_report_groups_the_deep_rows(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import log_report

        rows = [
            ["1", "stall", "-", "0", "0", "-", "412ms", "slowest char_update 380ms",
             "command look 3ms", "2 players", "0 more since"],
            # One blow from full: 60 against 50 of 60 hit points.
            ["2", "death", "Zx", "10", "1", "a.are", "mob 32700 a sparring guard",
             "killer_lvl=20 last=60 hit hp_before=50 from=32700 age=0s big=60 hit from=32700 "
             "age=0s max_hp=60 foes=1 wimpy=0 dt_room=0 sanct=0 linkdead=0"],
            # A slow bleed is not one.
            ["3", "death", "Zy", "10", "1", "a.are", "mob 32700 a sparring guard",
             "killer_lvl=20 last=5 hit hp_before=4 from=32700 age=0s big=9 hit from=32700 "
             "age=3s max_hp=60 foes=1 wimpy=0 dt_room=0 sanct=0 linkdead=0"],
            ["4", "item", "Zx", "10", "1", "a.are", "3701", "a dagger",
             "type=weapon level=1 worn=0 nested=0 timer=0 cond=100 inside=0", "obj_update"],
            ["5", "outcome", "Zx", "10", "1", "a.are", "quest-failed", "failure", "timeout", "-",
             "ordinary target=mob:3011 level=5 alive=0 area=x.are there=0 streak=2"],
        ]
        deep = log_report.deep_summary(rows)
        self.assertEqual(dict(deep["stalls"]), {"char_update": 1})
        self.assertEqual(deep["stall_ms"], {"char_update": 412})
        self.assertEqual(deep["deaths"]["mob 32700 a sparring guard"], 2)
        self.assertEqual([d[0] for d in deep["one_blow"]], ["Zx"])
        self.assertEqual(dict(deep["gone"]), {("obj_update", "a dagger"): 1})
        self.assertEqual(dict(deep["lost"]), {("mob:3011", "timeout"): 1})
        self.assertIn("mob:3011", deep["impossible"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class DeepLiveTests(unittest.TestCase):
    def test_a_rot_a_lost_quest_and_a_death_are_written_down(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zdeepgod", Levl=70, Room=QUESTMASTER)
            make(mud, "Zdeephero", Levl=10, Room=QUESTMASTER,
                 HMV="200 200 100 100 100 100", HMVP="200 100 100")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Zdeepgod", PW)
                login(hero, "Zdeephero", PW)
                god.sync("scroll 0")
                hero.sync("scroll 0")

                # A dagger on a one-tick timer, in the hero's pack.
                god.must(f"load obj {DAGGER}", "You create")
                god.must("set obj dagger timer 1", "")
                god.must("give dagger zdeephero", "You give")

                # A quest asked for and given up.
                hero.must("aquest request", "")
                hero.must("aquest abort", "")

                hero.expect("crumbles into dust", timeout=180)

                # A death: one hit point's worth of hero against the guard.
                place_sparring_guard(god, "zdeepgod", SPARRING_FLOOR)
                god.must(f"transfer zdeephero {SPARRING_FLOOR}", "")
                god.must("set char zdeephero hp 5", "")
                god.must("restore zdeephero", "")
                hero.buffer = ""
                hero.send("kill guard")
                hero.expect("You have been KILLED", timeout=120)
                hero.drain(2.0)
                for client in (hero, god):
                    client.send("quit")
                    client.wait_closed()
            mine = [r for r in rows(mud) if len(r) > 2 and r[2] == "Zdeephero"]

        items = [r for r in mine if r[1] == "item"]
        self.assertTrue(items, mine[-20:])
        self.assertEqual(items[0][6], str(DAGGER), items[0])
        self.assertIn("type=weapon", items[0][8])
        self.assertEqual(items[0][9], "obj_update", "rotted on the tick, not by a command")

        failed = [r for r in mine if r[1] == "outcome" and r[6] == "quest-failed"]
        self.assertEqual(len(failed), 1, mine[-20:])
        self.assertEqual((failed[0][7], failed[0][8]), ("failure", "abandoned"))
        self.assertRegex(failed[0][10], r"^(ordinary|rush|emergency) target=(mob|obj):\d+ level=\d+ alive=\d+ "
                                        r"area=\S+ there=[01] streak=0$")

        deaths = [r for r in mine if r[1] == "death"]
        self.assertEqual(len(deaths), 1, mine[-20:])
        self.assertRegex(deaths[0][6], r"^mob 32700 ")
        detail = deaths[0][7]
        self.assertRegex(detail, r"last=\d+ \S+ hp_before=\d+ from=32700 age=\d+s")
        self.assertIn("max_hp=5", detail)
        self.assertIn("foes=1", detail)


if __name__ == "__main__":
    unittest.main()
