"""Each Hyrule guardian's drop table is a little better than the best gear
a character of its band can get anywhere else.

The tables are BOSS_DROPS and BOSS_EXTRA_DROPS in
scripts/build_hyrule_area.py: a piece for every armour slot but the neck
(and Ganon's head), three of which fall at random each kill
(hyrule_boss_drops() in src/hyrule.c, from make_corpse). Each is the best in
its slot for the guardian's band, for a fighter and for a caster alike
(owner, 2026-10-04). "Better" is the
Gear Finder's own judgement -- get_best_gear and gear_item_score in
webadmin/server.py, warrior weights -- measured against the world as it is
now, so a stronger piece added somewhere later fails here rather than
quietly making a guardian's drops second best.
"""
from __future__ import annotations

import asyncio
import json
import re
import unittest
from pathlib import Path

from scripts.build_hyrule_area import (
    BOSS_DROP_FIRST,
    BOSS_DROPS,
    BOSS_DROPS_PER_GUARDIAN,
    BOSS_DROPS_PER_KILL,
    BOSS_EXTRA_DROP_FIRST,
    BOSS_EXTRA_DROP_STRIDE,
    BOSS_EXTRA_DROPS,
    BOSS_MOBS,
    WEAR_SLOT_FLAG,
    boss_drop_level,
    boss_drop_vnum,
    boss_drops,
    manifest_bands,
)

try:
    import webadmin.server as server
except ImportError as error:          # fastapi or httpx missing
    server = None
    SKIP = f"webadmin.server needs its dependencies: {error}"
else:
    SKIP = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
# How far above the best existing piece a drop may sit: "comparable to or
# slightly better", so never below it and never a leap past it.
CEILING = 1.25
SLACK = 6.0


class DropTableSourceTests(unittest.TestCase):
    """What can be checked without the dashboard."""

    def test_every_guardian_covers_every_armour_slot(self) -> None:
        self.assertEqual(sorted(BOSS_DROPS), list(range(1, 10)))
        self.assertEqual(sorted(BOSS_EXTRA_DROPS), list(range(1, 10)))
        armour_slots = set(WEAR_SLOT_FLAG) - {"neck"}
        for level in range(1, 10):
            with self.subTest(level=level):
                self.assertEqual(len(BOSS_DROPS[level]), BOSS_DROPS_PER_GUARDIAN)
                self.assertLessEqual(len(BOSS_EXTRA_DROPS[level]), BOSS_EXTRA_DROP_STRIDE)
                slots = [piece.slot for piece in boss_drops(level)]
                self.assertEqual(len(slots), len(set(slots)), slots)
                # The Heart Guard is worn at the neck, Ganon's crown on the
                # head: a drop never competes with the guardian's own piece.
                self.assertNotIn("neck", slots)
                if level == 9:
                    self.assertNotIn("head", slots)
                    self.assertEqual(set(slots), armour_slots - {"head"})
                else:
                    self.assertEqual(set(slots), armour_slots)

    def test_the_c_side_names_the_same_guardians_and_vnums(self) -> None:
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="utf-8")
        merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        table = hyrule.split("hyrule_guardian_vnums[9] =", 1)[1].split("};", 1)[0]
        self.assertEqual([int(v) for v in re.findall(r"\d+", table)],
                         [BOSS_MOBS[level] for level in range(1, 10)])
        self.assertRegex(merc, rf"#define OBJ_VNUM_HYRULE_BOSS_DROP_FIRST\s+{BOSS_DROP_FIRST}\b")
        self.assertRegex(merc, rf"#define HYRULE_BOSS_DROPS_PER_GUARDIAN\s+{BOSS_DROPS_PER_GUARDIAN}\b")
        self.assertRegex(merc, rf"#define HYRULE_BOSS_DROPS_PER_KILL\s+{BOSS_DROPS_PER_KILL}\b")
        self.assertRegex(merc, rf"#define OBJ_VNUM_HYRULE_BOSS_EXTRA_FIRST\s+{BOSS_EXTRA_DROP_FIRST}\b")
        self.assertRegex(merc, rf"#define HYRULE_BOSS_EXTRA_STRIDE\s+{BOSS_EXTRA_DROP_STRIDE}\b")
        extra = hyrule.split("hyrule_boss_extra_drops[9] =", 1)[1].split("};", 1)[0]
        self.assertEqual([int(v) for v in re.findall(r"\d+", extra)],
                         [len(BOSS_EXTRA_DROPS[level]) for level in range(1, 10)])
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        corpse = fight.split("void make_corpse(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_boss_drops( ch, corpse )", corpse)

    def test_every_piece_sits_at_the_top_of_its_band(self) -> None:
        from webadmin.area_parser import AreaParser

        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        bands = manifest_bands(MANIFEST)
        for level in range(1, 10):
            for index, _piece in enumerate(boss_drops(level)):
                obj = parser.objects[boss_drop_vnum(level, index)]
                with self.subTest(level=level, vnum=obj.vnum):
                    self.assertEqual(obj.level, boss_drop_level(level, bands))
                    self.assertLessEqual(obj.level, bands[level][1])
                    self.assertEqual(obj.item_type, "9")


@unittest.skipIf(SKIP is not None, SKIP or "")
class DropTableStrengthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = server.load_area_parser(server.AREA_PATH)
        server.parser = cls.parser
        cls.weights = server.CLASS_WEIGHTS["warrior"]
        cls.mage_weights = server.CLASS_WEIGHTS["mage"]
        cls.labels = {}
        for key, label in server.GEAR_FINDER_SLOTS:
            cls.labels.setdefault(key, label)
        cls.best: dict[int, dict] = {}

    def best_at(self, level: int, class_name: str = "warrior") -> dict:
        if (level, class_name) not in self.best:
            self.best[(level, class_name)] = asyncio.run(server.get_best_gear(
                class_name=class_name, race_name="human", level=level, limit=1))
        return self.best[(level, class_name)]

    def test_each_piece_beats_the_best_of_its_slot_by_a_little(self) -> None:
        out_of_window = []
        for level in range(1, 10):
            for index, piece in enumerate(boss_drops(level)):
                obj = self.parser.objects[boss_drop_vnum(level, index)]
                slot = server._gear_natural_slot(obj, server.ITEM_TYPE_ARMOR)
                self.assertEqual(slot, piece.slot)
                score, _ = server.gear_item_score(
                    obj, server.ITEM_TYPE_ARMOR, slot, list(obj.values), self.weights)
                found = self.best_at(obj.level)[self.labels[slot]]
                best = found[0]["score"] if found else 0.0
                if not best < score <= max(best * CEILING, best + SLACK):
                    out_of_window.append(
                        (level, piece.short, round(score, 2), best,
                         found[0]["name"] if found else None))
        self.assertEqual([], out_of_window,
                         "(guardian, piece, its score, best elsewhere, which)")

    def test_each_piece_is_the_best_of_its_slot_for_a_caster_too(self) -> None:
        """The mana on every piece is there so a caster finds the drop as
        good as a fighter does."""
        behind = []
        for level in range(1, 10):
            for index, piece in enumerate(boss_drops(level)):
                obj = self.parser.objects[boss_drop_vnum(level, index)]
                slot = server._gear_natural_slot(obj, server.ITEM_TYPE_ARMOR)
                score, _ = server.gear_item_score(
                    obj, server.ITEM_TYPE_ARMOR, slot, list(obj.values), self.mage_weights)
                found = self.best_at(obj.level, "mage")[self.labels[slot]]
                best = found[0]["score"] if found else 0.0
                if score < best:
                    behind.append((level, piece.short, round(score, 2), best,
                                   found[0]["name"] if found else None))
        self.assertEqual([], behind, "(guardian, piece, its score, best elsewhere, which)")


if __name__ == "__main__":
    unittest.main()
