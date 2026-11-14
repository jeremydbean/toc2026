"""What players come across and what they do about it (owner, 2026-11-13:
"count/track components and herbs and stuff so we can see how often
players are coming across them ... and see which ones they choose to pick
up or move past").

src/encounter.c writes laid, spotted, picked, passed and cleared rows for
herbs, components, eggs, maps and coin on the ground, rare-seen / rare-acted
/ rare-passed rows for the rare visitors, a sightings table of mobiles seen
against fought and floor items seen against taken at the end of a sitting,
and a census. tools/log_report.py's encounter section reads them.

The live test drops two herbs at the altar beside Hermie, brings a mortal
in, has them take one and leave, purges the other, lays a round with staff
COMPONENT, fights the fixture world's sparring guard and quits; then reads
log/play.tsv for every row it should have made, once each.
"""
from __future__ import annotations

import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from live_mud import (
    SPARRING_FLOOR,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import log_report  # noqa: E402

SKIP = skip_reason()
PW = "Zencpass1"
TEMPLE, ALTAR = 4207, 4208
AMARANTH, ANGELICA = 34, 35
HERMIE = 98
SPARRING_GUARD = 32700


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def rows(mud: LiveMud) -> list[list[str]]:
    text = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
    return [line.split("\t") for line in text.splitlines() if line.strip()]


class EncounterSummaryTests(unittest.TestCase):
    """The report's arithmetic, on rows written the way encounter.c writes
    them."""

    def test_summary_counts_choices_rare_visitors_and_tallies(self) -> None:
        t = "1794600000"
        common = [t, "", "Zhero", "20", "4208", "dresden.are"]

        def row(kind, *fields):
            r = list(common)
            r[1] = kind
            return r + [str(f) for f in fields]

        data = [
            row("laid", 1, "herb", 34, "an amaranth plant", 3001, "midgaard.are", "scatter"),
            row("spotted", 1, "herb", 34, "an amaranth plant", 600, 1, "scatter", "arrive"),
            row("picked", 1, "herb", 34, "an amaranth plant", 660, 60, 1, "scatter", "get"),
            row("spotted", 2, "herb", 35, "a sprig of angelica", 1200, 1, "scatter", "look"),
            row("passed", 2, "herb", 35, "a sprig of angelica", 1260, 60, 1, "scatter", "4208", "left"),
            row("cleared", 2, "herb", 35, "a sprig of angelica", 9000, 1, "scatter", "mob 3062",
                "(mobile_update)", "4208", "dresden.are"),
            row("rare-seen", "dealer", 29940, 77, "arrive"),
            row("rare-acted", "dealer", 29940, 77, "bought", 30),
            row("rare-seen", "goblin", 29941, 78, "arrive"),
            row("rare-passed", "goblin", 29941, 78, 12, "left"),
            row("sightings", "mob", "3011:4/1/1 3012:6/0/0"),
            row("sightings", "item", "3005:2/1"),
            row("census", "herbs=12/150 components=8/100 eggs=0 coin_piles=1",
                "herbs_held=3 components_held=2 players=1", "laid=4 spotted=2 secs=900"),
            row("session", "quit", "7200s", "+0 levels"),
        ]
        s = log_report.encounter_summary(data)
        herb = s["kinds"]["herb"]
        self.assertEqual((1, 2, 2, 1, 1, 1),
                         (herb["laid"], herb["objects"], herb["sightings"], herb["picked"],
                          herb["passed"], herb["cleared"]))
        self.assertEqual({"mob": 1}, dict(s["cleared_why"]["herb"]))
        self.assertEqual([10.0, 20.0], s["lain_first"]["herb"])
        self.assertEqual(1, s["per_vnum"][("herb", "35", "a sprig of angelica")]["passed"])
        self.assertEqual(1, s["rare"]["dealer"]["bought"])
        self.assertEqual(1, s["rare"]["goblin"]["passed"])
        self.assertEqual([4, 1, 1], s["mobs"]["3011"])
        self.assertEqual([2, 1], s["items"]["3005"])
        self.assertEqual("12/150", s["census"][0][1]["herbs"])
        self.assertAlmostEqual(2.0, s["play_hours"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class EncounterLiveTests(unittest.TestCase):
    def test_a_walk_past_the_herbs(self) -> None:
        with LiveMud(fixtures=True, extra_env={"TOC_ENCOUNTER_CENSUS_SECS": "2"}) as mud:
            make(mud, "Zencstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zenchero", Levl=20, Room=TEMPLE,
                 HMV="5000 5000 500 500 500 500", HMVP="5000 500 500")
            started = int(time.time()) - 1
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zencstaff", PW)
                login(hero, "Zenchero", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")

                staff.must(f"goto {ALTAR}", "")
                staff.must(f"load obj {AMARANTH}", "You create")
                staff.must("drop amaranth", "You drop")
                staff.must(f"load obj {ANGELICA}", "You create")
                staff.must("drop angelica", "You drop")
                staff.must(f"load mob {HERMIE}", "You create")

                staff.must(f"transfer zenchero {ALTAR}", "")
                hero.sync("look")                     # a second look counts nothing new
                hero.must("get amaranth", "You get")
                staff.must(f"transfer zenchero {TEMPLE}", "")
                staff.must("purge", "")               # the angelica, and Hermie
                staff.must("component", "lie waiting")

                place_sparring_guard(staff, "Zencstaff", SPARRING_FLOOR)
                staff.must(f"transfer zenchero {SPARRING_FLOOR}", "")
                hero.sync("kill sparring", 10)
                hero.drain(2)
                staff.sync("peace")
                hero.drain(3)                         # a census or two
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                staff.send("quit")
                staff.wait_closed()

            mine = [r for r in rows(mud) if r[0].isdigit() and int(r[0]) >= started]

        def kind(name):
            return [r for r in mine if r[1] == name]

        spotted = [r for r in kind("spotted") if r[2] == "Zenchero"]
        self.assertEqual(sorted(["34", "35"]), sorted(r[8] for r in spotted), spotted)
        self.assertTrue(all(r[7] == "herb" and r[12] == "dropped" and r[13] == "arrive"
                            for r in spotted), spotted)
        picked = [r for r in kind("picked") if r[2] == "Zenchero"]
        self.assertEqual(["34"], [r[8] for r in picked], picked)
        self.assertGreaterEqual(int(picked[0][11]), 0, picked)
        self.assertEqual("get", picked[0][14], picked)
        passed = [r for r in kind("passed") if r[2] == "Zenchero"]
        self.assertEqual(["35"], [r[8] for r in passed], passed)
        self.assertEqual(str(ALTAR), passed[0][14], passed)
        cleared = [r for r in kind("cleared") if r[8] == "35"]
        self.assertEqual(["gone"], [r[13] for r in cleared], cleared)
        self.assertIn("purge", cleared[0][14], cleared)
        # Staff's own pick-up and drop are nobody's sighting.
        self.assertFalse([r for r in mine if r[1] in ("spotted", "picked", "passed")
                          and r[2] == "Zencstaff"])

        self.assertEqual([("hermie", "98")], [(r[6], r[7]) for r in kind("rare-seen")
                                              if r[2] == "Zenchero"])
        self.assertEqual(["hermie"], [r[6] for r in kind("rare-passed") if r[2] == "Zenchero"])

        laid = kind("laid")
        self.assertTrue(laid, "staff COMPONENT laid nothing")
        self.assertTrue(all(r[12] == "scatter" and r[7] in ("herb", "component") for r in laid), laid)
        self.assertTrue(kind("census"), "no census in the window")
        self.assertIn("herbs=", kind("census")[-1][6])

        sightings = " ".join(r[7] for r in kind("sightings") if r[2] == "Zenchero" and r[6] == "mob")
        self.assertIn(f"{SPARRING_GUARD}:1/1/0", sightings)
        self.assertIn(f"{HERMIE}:1/0/0", sightings)

        # And the report reads them without complaint.
        since = datetime.fromtimestamp(started, timezone.utc)
        s = log_report.encounter_summary(
            [r for r in mine if r[1] in log_report.ENCOUNTER_KINDS
             and datetime.fromtimestamp(int(r[0]), timezone.utc) >= since])
        self.assertEqual(1, s["kinds"]["herb"]["picked"])
        self.assertEqual(1, s["kinds"]["herb"]["passed"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class EncounterPrivacyTests(unittest.TestCase):
    """The journal is published every five minutes (review, 2026-11-13)."""

    def test_wizinvis_staff_clearing_the_floor_writes_no_row(self) -> None:
        """A wizinvis immortal's GET and SACRIFICE of a herb were written as
        `cleared` rows naming the room and "staff"."""
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zencinvis", Levl=70, Room=TEMPLE)
            started = int(time.time()) - 1
            with mud.connect(timeout=120) as staff:
                login(staff, "Zencinvis", PW)
                staff.sync("scroll 0")
                staff.must("wizinvis", "")
                staff.must(f"goto {ALTAR}", "")
                staff.must(f"load obj {AMARANTH}", "You create")
                staff.must("drop amaranth", "You drop")
                staff.must("get amaranth", "You get")
                staff.must("drop amaranth", "You drop")
                staff.must("sacrifice amaranth", "")
                staff.send("quit")
                staff.wait_closed()
            mine = [r for r in rows(mud) if r[0].isdigit() and int(r[0]) >= started]
            self.assertEqual([], [r for r in mine if r[1] == "cleared"], mine)

    def test_leaving_the_dealer_names_no_room(self) -> None:
        """Rows about what was passed by in a room the dealer stands in are
        written after the player has left it: they carried the room walked
        into, one exit from him."""
        with LiveMud(extra_env={"TOC_BLACK_MARKET_STILL": "1"}) as mud:
            make(mud, "Zencfixer", Levl=70, Room=TEMPLE)
            make(mud, "Zencwalker", Levl=20, Room=ALTAR)
            started = int(time.time()) - 1
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zencfixer", PW)
                login(hero, "Zencwalker", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("blackmarket here", f"in room {TEMPLE}")
                staff.must(f"transfer zencwalker {TEMPLE}", "")
                hero.sync("look")
                staff.must(f"transfer zencwalker {ALTAR}", "")
                hero.sync("look")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            mine = [r for r in rows(mud) if r[0].isdigit() and int(r[0]) >= started
                    and r[2] == "Zencwalker"]
        seen = [r for r in mine if r[1] == "rare-seen" and r[6] == "dealer"]
        passed = [r for r in mine if r[1] == "rare-passed" and r[6] == "dealer"]
        self.assertEqual(1, len(seen), mine)
        self.assertEqual(1, len(passed), mine)
        self.assertEqual(("-", "-"), (seen[0][4], seen[0][5]), seen)
        self.assertEqual(("-", "-"), (passed[0][4], passed[0][5]), passed)


if __name__ == "__main__":
    unittest.main()
