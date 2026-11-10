"""log/hyrule.tsv: Hyrule play written down for balance and trends
(owner, 2026-11-10).

A level 58 mortal crosses into Hyrule, is turned back by a dungeon's
entry gate for want of the first piece, is handed it, goes down into
the dungeon, is turned back by the guardian's gate for want of a
boomerang, fights a guardian and flees it, fights another and kills it,
and dies -- and every step is a row: enter and leave with the seconds
spent, the gate and what it wanted, what they were given and how, the
guardian fights with the party and the guardian's health, the death.
Staff leave no row.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Zhylogpass1"
TEMPLE = 4207
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
WORLD = {room["coordinate"]: room["vnum"] for room in MANIFEST["overworld"]["rooms"]}
DUNGEONS = {dungeon["level"]: dungeon for dungeon in MANIFEST["dungeons"]}
AQUAMENTUS = 30222


def rows(mud: LiveMud) -> list[dict]:
    path = mud.root / "log" / "hyrule.tsv"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="latin-1").splitlines():
        cols = line.split("\t")
        if len(cols) < 8:
            continue
        row = dict(epoch=cols[0], kind=cols[1], name=cols[2], level=cols[3],
                   remorts=cols[4], cls=cols[5], room=cols[6], zone=cols[7])
        for word in " ".join(cols[8:]).split():
            key, _, value = word.partition("=")
            row[key] = value
        out.append(row)
    return out


def make(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=TEMPLE, Attr="25 25 25 25 25",
                      HMV="20000 20000 1000 1000 1000 1000", HMVP="20000 1000 1000")


class HyruleLogSourceTests(unittest.TestCase):
    def test_every_hook_is_wired(self) -> None:
        src = {name: (ROOT / "src" / name).read_text(encoding="latin-1")
               for name in ("handler.c", "fight.c", "act_move.c", "act_obj.c",
                            "hyrule.c", "playlog.c")}
        self.assertIn("hylog_moved( ch )", src["handler.c"])
        self.assertIn("hylog_got(ch, obj)", src["handler.c"])
        for hook in ("hylog_engage(", "hylog_guardian_down(", "hylog_flee(",
                     "hylog_death(", "hylog_room_cleared("):
            self.assertIn(hook, src["fight.c"], hook)
        self.assertEqual(src["act_move.c"].count("hylog_gate("), 2)
        self.assertIn("hylog_seal(", src["act_obj.c"])
        self.assertEqual(src["hyrule.c"].count("hylog_claim("), 4)
        self.assertIn("hylog_session_end(", src["playlog.c"])
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("src/hyrulelog.c", cmake)

    def test_staff_and_wizinvis_are_never_written(self) -> None:
        text = (ROOT / "src" / "hyrulelog.c").read_text(encoding="latin-1")
        counts = text.split("static bool hylog_counts(", 1)[1].split("\n}", 1)[0]
        self.assertIn("PLR_WIZINVIS", counts)
        self.assertIn("LEVEL_IMMORTAL", counts)


class HyruleReportTests(unittest.TestCase):
    """tools/log_report.py's Hyrule section reads what the game writes."""

    def test_the_summary_counts_a_guardian_fight(self) -> None:
        sys.path.insert(0, str(ROOT / "tools"))
        import log_report
        from datetime import datetime, timezone
        prefix = "\tZed\t30\t1\tW\t30432\tL2\t"
        text = "\n".join([
            "1794300000\tenter\tZed\t30\t1\tW\t30418\tL2\tfrom=over how=down hp=100",
            "1794300030\tengage" + prefix + "foe=30218 foe_name=Dodongo foe_hp=100 party=2 levels=30,28",
            "1794300090\tflee" + prefix + "foe=30218 foe_name=Dodongo guardian=1 foe_hp=42 secs=60 hp=12",
            "1794300200\tguardian-down" + prefix + "foe=30218 foe_name=Dodongo secs=80 party=2 levels=30,28",
            "1794300210\tgot" + prefix + "obj=30401 obj_name=the_second_shard type=treasure how=get",
            "1794300300\tleave" + prefix + "to=out how=quit secs=280 hp=50",
        ])
        rows = log_report.hyrule_rows(text, datetime(2026, 1, 1, tzinfo=timezone.utc))
        summary = log_report.hyrule_summary(rows)
        dodongo = summary["guardians"][("30218", "Dodongo")]
        self.assertEqual((dodongo["engage"], dodongo["down"], dodongo["flee"]), (1, 1, 1))
        self.assertEqual(dodongo["flee_hp"], [42])
        self.assertEqual(dodongo["kill_secs"], [80])
        self.assertEqual(summary["furthest"], {"Zed": "L2"})
        self.assertEqual(summary["zones"]["L2"]["secs"], [280])
        self.assertIn(("30401", "the_second_shard"), summary["got"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleLogLiveTests(unittest.TestCase):
    def test_a_visit_is_written_down(self) -> None:
        level_two = DUNGEONS[2]
        screen = WORLD[level_two["overworld_coordinate"]]
        rooms = {room["coordinate"]: room["vnum"] for room in level_two["rooms"]}
        approach = rooms["C7"]          # south of Dodongo's lair
        with LiveMud() as mud:
            make(mud, "Zhyloghero", 58)
            make(mud, "Zhyloggod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zhyloghero", PASSWORD)
                login(god, "Zhyloggod", PASSWORD)
                for client in (hero, god):
                    client.sync("scroll 0")
                god.must("holylight", "")

                god.must(f"transfer zhyloghero {screen}", "")
                refused = hero.sync("down", timeout=60)
                self.assertIn("first Triforce piece", refused, refused)
                god.must(f"goto {screen}", "")
                god.must("load obj 30400", "You create")
                god.must("give shard zhyloghero", "You give")
                passed = hero.sync("down", timeout=60)
                self.assertIn("Level 2:", passed, passed)

                god.must(f"goto {approach}", "")
                god.sync("purge")
                god.must(f"transfer zhyloghero {approach}", "")
                lever = hero.sync("north", timeout=60)
                self.assertIn("boomerang", lever.lower(), lever)

                # A guardian fought and fled, in the dungeon's first room,
                # whose way up is open (the approach's shutter shuts behind
                # anyone while an enemy stands there).
                entrance = int([r for r in rows(mud) if r["kind"] == "enter"
                                and r["zone"] == "L2"][0]["room"])
                god.must(f"goto {entrance}", "")
                god.must(f"load mob {AQUAMENTUS}", "You create")
                god.must("goto 4207", "")
                god.must(f"transfer zhyloghero {entrance}", "")
                hero.sync("kill aquamentus", timeout=60)
                for _ in range(30):
                    said = hero.sync("flee", timeout=60)
                    if "You flee from combat" in said or "aren't fighting" in said:
                        break
                # Back, and this time to the end.
                god.must("set char zhyloghero hitroll 300", "")
                god.must("set char zhyloghero damroll 300", "")
                god.must(f"transfer zhyloghero {entrance}", "")
                hero.sync("kill aquamentus", timeout=60)
                for _ in range(40):
                    hero.drain(2.0)
                    if any(r["kind"] == "guardian-down" for r in rows(mud)):
                        break
                # Died in Hyrule.
                god.must(f"goto {entrance}", "")
                god.sync("slay zhyloghero")
                god.must("goto 4207", "")
                hero.drain(2.0)
                hero.send("quit")
                hero.wait_closed()
                god.send("quit")
                god.wait_closed()

            got = rows(mud)

        kinds = [r["kind"] for r in got]
        self.assertFalse([r for r in got if r["name"] == "Zhyloggod"], "staff leave no row")
        enter = [r for r in got if r["kind"] == "enter"]
        self.assertTrue(any(r["zone"] == "over" and r["from"] == "out" for r in enter), enter)
        self.assertTrue(any(r["zone"] == "L2" and r["from"] == "over" and r["how"] == "down"
                            for r in enter), enter)
        leave = [r for r in got if r["kind"] == "leave"]
        self.assertTrue(leave and all(int(r["secs"]) >= 0 for r in leave), leave)
        gates = [r for r in got if r["kind"] == "gate"]
        self.assertTrue(any(r["gate"] == "entry" and r["dungeon"] == "2" and r["need"] == "30400"
                            for r in gates), gates)
        self.assertTrue(any(r["gate"] == "guardian" and r["dungeon"] == "2" for r in gates), gates)
        self.assertFalse([r for r in gates if r["how"] == "flee"], "a flight writes no gate row")
        self.assertTrue(any(r["kind"] == "got" and r["obj"] == "30400"
                            and r["obj_name"] == "the_first_Triforce_shard"
                            and r["how"] == "give(another's)" for r in got),
                        [r for r in got if r["kind"] == "got"])
        engage = [r for r in got if r["kind"] == "engage"]
        self.assertTrue(engage, kinds)
        self.assertEqual(engage[0]["foe"], str(AQUAMENTUS))
        self.assertEqual(engage[0]["party"], "1")
        self.assertEqual(engage[0]["levels"], "58")
        flee = [r for r in got if r["kind"] == "flee"]
        self.assertTrue(flee and flee[0]["guardian"] == "1", flee)
        self.assertLessEqual(int(flee[0]["foe_hp"]), 100)
        down = [r for r in got if r["kind"] == "guardian-down"]
        self.assertTrue(down and down[0]["foe"] == str(AQUAMENTUS), kinds)
        self.assertGreaterEqual(int(down[0]["secs"]), 0)
        death = [r for r in got if r["kind"] == "death"]
        self.assertTrue(death and death[0]["how"] == "player", death)
        self.assertEqual(death[0]["name"], "Zhyloghero")


if __name__ == "__main__":
    unittest.main()
