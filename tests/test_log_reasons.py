"""The journals say why, and a corpse taken back is no find (2026-11-22).

Reading the logs, the owner asked whether Alaric had found all eight
Triforce pieces: the Hyrule log's report listed them all as gained in one
second. They were Trentlin's own, taken back from his corpse after a
death, and the row said only how=get. And when no command explains a row
it named an update phase -- a death "(mobile_update)", a login "(game
loop)", a guardian's key and every autoloot "(violence_update)", a thief's
robbery "spent (mobile_update)".

Now a reason is named where it happens (playlog_reason): own-corpse,
own-bag, autoloot, autogold, death, login, walkto, guardian-key, stolen;
the Hyrule got row names where the thing came from; flee and death rows
give the foe's hit points, not only a percentage that reads 0 at 40 hit
points; a crumbled row names whose dungeon's things they were; and the
death row says what came off in the last ten seconds. The report counts
what was taken back apart from what was found, old rows included.

Synthetic Z characters in the fixture world.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from live_mud import (SPARRING_FLOOR, LiveMud, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import log_report  # noqa: E402

SKIP = skip_reason()
PW = "Zreasonpw1"
QUESTMASTER = 2497
DAGGER = 3701
EPOCH0 = datetime.fromtimestamp(0, timezone.utc)


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


class ReportTests(unittest.TestCase):
    def test_a_corpse_taken_back_is_counted_apart(self) -> None:
        self.assertTrue(log_report.is_recovery("Zed", "own-corpse", "-"))
        self.assertTrue(log_report.is_recovery("Zed", "own-bag", "a pack"))
        # Rows from before the reasons: known by their source.
        self.assertTrue(log_report.is_recovery("Zed", "get", "corpse of Zed"))
        self.assertTrue(log_report.is_recovery("Zed", "get", "corpse_of_Zed"))
        self.assertFalse(log_report.is_recovery("Zed", "get", "corpse of a kobold"))
        self.assertFalse(log_report.is_recovery("Zed", "get", "corpse of Zedd"))

        play = "\n".join([
            "1794300000\tgot\tZed\t50\t30489\thyrule.are\t30400\tthe first shard\ttreasure"
            "\t2\t0\tget\tcorpse of Zed",
            "1794300001\tgot\tZed\t50\t30489\thyrule.are\t30401\tthe second shard\ttreasure"
            "\t8\t0\tget\tthe floor",
        ])
        recovered = log_report.own_corpse_gets(play, EPOCH0)
        self.assertEqual(recovered, {(1794300000, "Zed", "30400")})

        prefix = "\tZed\t50\t0\tMonk\t4207\tout\t"
        hyrule = "\n".join([
            # An old row: no source, matched to the play journal's.
            "1794300000\tgot" + prefix + "obj=30400 obj_name=the_first_shard how=get",
            "1794300001\tgot" + prefix + "obj=30401 obj_name=the_second_shard how=get from=the_floor",
            "1794300002\tgot" + prefix + "obj=30402 obj_name=the_third_shard how=own-corpse"
            " from=corpse_of_Zed",
        ])
        summary = log_report.hyrule_summary(log_report.hyrule_rows(hyrule, EPOCH0), recovered)
        self.assertEqual(list(summary["got"]), [("30401", "the_second_shard")])
        self.assertEqual(summary["recovered"]["Zed"], 2)

        activity = log_report.activity_summary(log_report.activity_rows(play, EPOCH0))
        self.assertEqual(list(activity["got"]), [("30401", "the second shard")])
        self.assertEqual(activity["recovered"]["Zed"], 1)


class SourceTests(unittest.TestCase):
    def test_reasons_are_named_where_they_happen(self) -> None:
        read = lambda name: (ROOT / "src" / name).read_text(encoding="latin-1")  # noqa: E731
        self.assertIn('playlog_reason( "own-corpse" )', read("act_obj.c"))
        self.assertIn('playlog_reason( "own-bag" )', read("act_obj.c"))
        fight = read("fight.c")
        for reason in ("autoloot", "autogold", "death"):
            self.assertIn(f'playlog_reason( "{reason}" )', fight)
        self.assertIn('playlog_reason( "guardian-key" )', read("hyrule.c"))
        self.assertIn('playlog_reason( "walkto" )', read("walkto.c"))
        self.assertIn('playlog_reason( "login" )', read("comm.c"))
        special = read("special.c")
        self.assertIn('playlog_reason( "stolen" )', special)
        self.assertIn('playlog_coin_as( "stolen" )', special)
        hylog = read("hyrulelog.c")
        self.assertIn("how=%s from=%s", hylog)
        self.assertIn("foe_hit=%d foe_max=%d", hylog)
        self.assertIn("of=%s", hylog)
        self.assertIn("burst=%ld burst_secs=%ld", read("playlog.c"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_a_death_and_the_corpse_taken_back(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zreasongod", Levl=70, Room=QUESTMASTER)
            make(mud, "Zrecover", Levl=10, Room=QUESTMASTER,
                 HMV="200 200 100 100 100 100", HMVP="200 100 100")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Zreasongod", PW)
                login(hero, "Zrecover", PW)
                god.sync("scroll 0")
                hero.sync("scroll 0")
                god.must(f"load obj {DAGGER}", "You create")
                god.must("give dagger zrecover", "You give")

                place_sparring_guard(god, "zreasongod", SPARRING_FLOOR)
                god.must(f"transfer zrecover {SPARRING_FLOOR}", "")
                god.must("set char zrecover hp 5", "")
                god.must("restore zrecover", "")
                hero.buffer = ""
                hero.send("kill guard")
                hero.expect("You have been KILLED", timeout=120)
                hero.drain(2.0)
                god.must("purge guard", "")
                god.must(f"transfer zrecover {SPARRING_FLOOR}", "")
                hero.must("get all corpse", "You get")
                for client in (hero, god):
                    client.send("quit")
                    client.wait_closed()
            mine = [r for r in rows(mud) if len(r) > 2 and r[2] == "Zrecover"]

        deaths = [r for r in mine if r[1] == "death"]
        self.assertEqual(len(deaths), 1, mine[-20:])
        self.assertRegex(deaths[0][7], r"burst=\d+ burst_secs=\d+")
        got = [r for r in mine if r[1] == "got" and r[6] == str(DAGGER)]
        self.assertTrue(got, mine[-20:])
        self.assertEqual(got[-1][11], "own-corpse", got[-1])
        self.assertEqual(got[-1][12], "corpse of Zrecover", got[-1])
        moved = [r for r in mine if r[1] == "area"]
        self.assertIn("death", [r[9] for r in moved if len(r) > 9], moved)


if __name__ == "__main__":
    unittest.main()
