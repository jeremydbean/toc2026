"""HUNTING: creatures worth hunting at a level (2026-11-15).

The dashboard writes area/hunting.txt from its leveling guide
(webadmin/hunting.py): several creatures a level, one an area, measured
only from three characters or more. The game's HUNTING (src/hunting.c)
reads it and names them with the WALKTO that reaches each; with no file, or
no row for the level, it estimates from the world. Played in a disposable
world with synthetic Z characters and a synthetic file; nothing under
player/, gods/, heroes/, backups/ or log/ is touched.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zhuntpass1"
TEMPLE = 4207

try:
    from webadmin import hunting
    from webadmin.area_parser import (AreaParser, ACT_FLAGS, decode_flags,
                                      flag_bit, parse_flag_value)
except ImportError:  # pragma: no cover - run from the repository root
    hunting = None
    AreaParser = None


def row(vnum, area, xp, *, basis="measured", chars=5, risk=0.05, kills=50,
        needs=None, aggressive=False, seconds=10.0):
    return {"vnum": vnum, "area_file": area, "xp_per_hour": xp, "basis": basis,
            "measured_characters": chars if basis == "measured" else 0,
            "risk": risk if basis == "measured" else None, "needs": needs or [],
            "aggressive": aggressive, "kill_seconds": seconds,
            "observed": {"kills": kills}}


@unittest.skipIf(hunting is None, "webadmin is not importable from here")
class PickTests(unittest.TestCase):
    def test_one_an_area_and_viable_only(self) -> None:
        rows = [row(1, "a.are", 1000), row(2, "a.are", 900), row(3, "b.are", 800),
                row(4, "c.are", 300)]           # under 40% of the best
        picked = hunting.pick(rows)
        self.assertEqual([r["vnum"] for r in picked], [1, 3])

    def test_too_few_characters_is_left_out_never_relabelled(self) -> None:
        rows = [row(1, "a.are", 1000, chars=2), row(2, "b.are", 900),
                row(3, "c.are", 800, basis="modelled")]
        picked = hunting.pick(rows)
        self.assertEqual([r["vnum"] for r in picked], [2, 3])

    def test_hyrule_and_bad_area_words_are_left_out(self) -> None:
        rows = [row(1, "hyrule.are", 1000, needs=["the raft"]), row(2, "bad name.are", 900),
                row(3, "", 900), row(4, "d.are", 800)]
        self.assertEqual([r["vnum"] for r in hunting.pick(rows)], [4])

    def test_safest_and_least_hunted_make_the_cut(self) -> None:
        rows = [row(i, "a%d.are" % i, 1000 - i * 10, risk=0.3, kills=500) for i in range(1, 9)]
        rows.append(row(20, "safe.are", 500, risk=0.0, kills=500))
        rows.append(row(21, "quiet.are", 450, risk=0.3, kills=1))
        picked = [r["vnum"] for r in hunting.pick(rows)]
        self.assertEqual(len(picked), hunting.HUNTING_PER_LEVEL)
        self.assertIn(1, picked)           # the best
        self.assertIn(20, picked)          # the safest
        self.assertIn(21, picked)          # the least hunted
        xp = [r["xp_per_hour"] for r in hunting.pick(rows)]
        self.assertEqual(xp, sorted(xp, reverse=True))

    def test_render_and_write_only_on_change(self) -> None:
        text = hunting.render({7: hunting.pick([row(3001, "school.are", 1234, risk=0.2,
                                                  aggressive=True, seconds=12.4)])})
        self.assertIn("\n7 3001 M 1234 12 200 1 school.are\n", text)
        self.assertTrue(all(l.startswith("#") for l in text.splitlines()[:4]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / hunting.HUNTING_FILE
            self.assertTrue(hunting.write(path, text))
            self.assertFalse(hunting.write(path, text))
            self.assertEqual(path.read_text(encoding="ascii"), text)


def prey(parser, level):
    """Ordinary creatures of a level a reset places, outside Hyrule, the yard
    and the seasonal records."""
    for vnum, mob in sorted(parser.mobiles.items()):
        if int(mob.level or 0) != level or not mob.spawn_rooms or vnum in parser.shopkeepers:
            continue
        if mob.area_file in ("hyrule.are", "dummy.are", "seasonal.are", "school.are"):
            continue
        acts = set(decode_flags(mob.act_flags, ACT_FLAGS))
        if acts & {"is-healer", "gain", "pet", "train", "practice"}:
            continue
        # NOKILL (X) and QUESTM (Y), which the table may not name.
        bits = parse_flag_value(mob.act_flags)
        if bits & (flag_bit("X") | flag_bit("Y")):
            continue
        yield vnum, mob


@unittest.skipIf(SKIP is not None or AreaParser is None, SKIP or "webadmin is not importable")
class HuntingLiveTests(unittest.TestCase):
    def test_estimates_measured_rows_and_their_guards(self) -> None:
        parser = AreaParser(ROOT / "area")
        parser.parse_all(built=False)
        candidates = list(prey(parser, 10))
        self.assertGreaterEqual(len(candidates), 3, candidates)
        shop = next(v for v in sorted(parser.shopkeepers)
                    if parser.mobiles.get(v) and parser.mobiles[v].spawn_rooms)
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhunter", PW)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zhunter", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zhunter", PW)

                # No file: estimates from the world, one an area.
                said = hero.sync("hunting", timeout=30)
                self.assertIn("Creatures to hunt at level 10", said, said)
                self.assertIn("Estimates: no players' kills", said, said)
                self.check_screen(said)
                walks = re.findall(r"(?m)^    WALKTO (.+?)\r?$", said)
                self.assertTrue(walks, said)
                self.assertEqual(len(walks), len(set(walks)), said)
                for place in walks:
                    walked = hero.sync("walkto " + place)
                    self.assertIn("You set off for", walked, (place, walked))
                    hero.sync("walkto stop")

                # Another level, and nonsense refused.
                self.assertIn("at level 25", hero.sync("hunting 25", timeout=30))
                for bad in ("hunting 0", "hunting 60", "hunting lots"):
                    self.assertIn("Syntax: hunting", hero.sync(bad), bad)

                # A file: measured rows shown best first, numbers formatted;
                # malformed lines, a shopkeeper, an unknown area and another
                # level's rows never shown.
                good = candidates[:3]
                lines = ["# synthetic", "garbage line", "10 x M 1 1 1 0 a.are",
                         "10 %d M 99999 5 10 0 %s" % (shop, parser.mobiles[shop].area_file),
                         "10 %d M 88888 5 10 0 nowhere.are" % good[0][0]]
                xp = 45678
                for vnum, mob in good:
                    lines.append("10 %d M %d 9 210 1 %s" % (vnum, xp, mob.area_file))
                    xp -= 1000
                lines.append("11 %d M 77777 5 10 0 %s" % (good[0][0], good[0][1].area_file))
                (mud.root / "area" / "hunting.txt").write_text("\n".join(lines) + "\n",
                                                               encoding="ascii")
                said = hero.sync("hunting", timeout=30)
                self.check_screen(said)
                self.assertIn("Measured: timed from players", said, said)
                self.assertIn("measured", said, said)
                self.assertIn("45,678 xp/hour", said, said)
                self.assertIn("risky", said, said)
                self.assertIn("attacks on sight", said, said)
                for absent in ("99,999", "88,888", "77,777"):
                    self.assertNotIn(absent, said, said)
                shown = [int(n.replace(",", "")) for n in re.findall(r"([\d,]+) xp/hour", said)]
                self.assertEqual(shown, sorted(shown, reverse=True), said)

                # The file rewritten is read again; removed, estimates again.
                (mud.root / "area" / "hunting.txt").write_text(
                    "# synthetic\n10 %d M 1500 30 0 0 %s\n" % (good[1][0], good[1][1].area_file),
                    encoding="ascii")
                self.assertIn("1,500 xp/hour", hero.sync("hunting", timeout=30))
                (mud.root / "area" / "hunting.txt").write_text(
                    "10 %d E 2500 30 -1 0 %s\n" % (good[2][0], good[2][1].area_file),
                    encoding="ascii")
                said = hero.sync("hunting", timeout=30)
                self.assertIn("2,500 xp/hour, estimated", said, said)
                self.assertIn("Estimates: no players' kills", said, said)
                (mud.root / "area" / "hunting.txt").unlink()
                self.assertIn("Estimates: no players' kills", hero.sync("hunting", timeout=30))

    def check_screen(self, said: str) -> None:
        self.assertNotIn("Hit Return", said, said)
        self.assertTrue(all(ord(c) < 128 for c in said), said)
        for line in said.replace("\r", "").split("\n"):
            self.assertLessEqual(len(line), 79, line)


try:
    import fastapi  # noqa: F401
    WEB_REASON = None
except Exception as exc:  # pragma: no cover
    WEB_REASON = f"webadmin deps unavailable ({exc})"


@unittest.skipIf(WEB_REASON is not None, WEB_REASON or "")
class HuntingWriterTests(unittest.TestCase):
    """The dashboard writes the file from the leveling guide itself."""

    def test_written_from_the_leveling_guide(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import patch
        from webadmin import server

        def mob(vnum, level, area):
            return SimpleNamespace(vnum=vnum, level=level, hitp_dice="2d8", dam_dice="1d4",
                                   act_flags="A", off_flags="", short_desc="mob %d" % vnum,
                                   area_name=area, area_file=area.lower() + ".are",
                                   spawn_rooms=[1, 2])
        mobs = [mob(100 + i, 10, "Area%d" % (i % 7)) for i in range(20)]
        fake = SimpleNamespace(mobiles={m.vnum: m for m in mobs}, rooms={}, objects={})
        routes = {"routes": [{"area": "Area%d" % i, "commands": "n", "rooms_away": 1}
                             for i in range(7)]}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(server, "parser", fake), \
                patch.object(server, "load_directions", lambda: routes), \
                patch.object(server, "QUEUE_PATH", Path(tmp) / "webadmin.queue"), \
                patch.object(server, "PROGRESS_LOG", Path(tmp) / "progress.tsv"):
            self.assertTrue(server.write_hunting())
            self.assertFalse(server.write_hunting())
            text = (Path(tmp) / "hunting.txt").read_text(encoding="ascii")
        rows = [l.split() for l in text.splitlines() if not l.startswith("#")]
        at10 = [r for r in rows if r[0] == "10"]
        self.assertEqual(len(at10), hunting.HUNTING_PER_LEVEL)
        self.assertEqual(len({r[7] for r in at10}), len(at10))      # one an area
        for r in rows:
            self.assertEqual(len(r), 8, r)
            self.assertEqual(r[2], "E", r)                          # nothing measured


class HuntingSourceTests(unittest.TestCase):
    def test_it_writes_nothing_and_is_last_but_nothing_moved(self) -> None:
        src = (ROOT / "src" / "hunting.c").read_text(encoding="utf-8")
        body = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
        for call in ("save_char_obj", "fopen( HUNTING_FILE, \"w", "SET_BIT", "gain_exp",
                     "achievement_unlock"):
            self.assertNotIn(call, body, call)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        self.assertEqual(names[-2:], ["adventure", "hunting"])

    def test_the_file_is_never_committed(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("area/hunting.txt\n", ignore)
        harness = (ROOT / "tests" / "live_mud.py").read_text(encoding="utf-8")
        self.assertIn('"hunting.txt"', harness)


if __name__ == "__main__":
    unittest.main()
