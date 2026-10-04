"""The Oracle knows Hyrule, the zone (owner, 2026-10-04).

webadmin/hyrule_oracle.py hands her a guide to how the zone plays, the
asker's progress as the game reports it, and walking routes from wherever
they stand. These pin the routes to the generated area and the guide's
facts to the generator and the C gate table.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))
sys.path.insert(0, str(ROOT / "scripts"))

import hyrule_oracle as ho  # noqa: E402
from area_parser import AreaParser  # noqa: E402

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DIRECTIONS = json.loads((ROOT / "webadmin" / "directions.json").read_text(encoding="utf-8"))


def _parser() -> AreaParser:
    parser = AreaParser(ROOT / "area")
    parser.parse_area_file(ROOT / "area" / "hyrule.are")
    return parser


class HyruleOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rooms = _parser().rooms
        cls.graph = ho.build_graph(cls.rooms, DIRECTIONS.get("links") or [])

    def test_dungeon_table_matches_the_manifest_and_gate_table(self) -> None:
        world = {r["coordinate"]: r["vnum"] for r in MANIFEST["overworld"]["rooms"]}
        for dungeon in MANIFEST["dungeons"]:
            level = dungeon["level"]
            with self.subTest(level=level):
                self.assertEqual(ho.DUNGEONS[level]["screen"], world[dungeon["overworld_coordinate"]])
                self.assertEqual(ho.DUNGEONS[level]["entrance"], dungeon["entrance_vnum"])
                low, high = dungeon["recommended_levels"][0], dungeon["recommended_levels"][-1]
                self.assertEqual(ho.DUNGEONS[level]["band"], "%d-%d" % (low, high))
        hyrule_c = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        screens = re.search(r"hyrule_dungeon_screens\[9\] =\s*\{([^}]*)\}", hyrule_c).group(1)
        self.assertEqual([int(v) for v in re.findall(r"\d+", screens)],
                         [ho.DUNGEONS[level]["screen"] for level in range(1, 10)])

    def test_treasures_match_the_generator(self) -> None:
        import build_hyrule_area as gen
        objects = _parser().objects
        names = {level: objects[vnum].short_desc.lower() for level, vnum in gen.DUNGEON_TREASURE.items()}
        for level in range(1, 9):
            with self.subTest(level=level):
                self.assertIn(names[level].removeprefix("the ").removeprefix("a "),
                              ho.DUNGEONS[level]["treasure"].lower())

    def test_every_entrance_is_reachable_in_order_with_what_came_before(self) -> None:
        """From the entry, each dungeon's screen can be walked to carrying
        only the treasures of the dungeons before it."""
        treasures = {3: "the raft", 4: "the stepladder"}
        for level in range(1, 10):
            items = [name for lvl, name in treasures.items() if lvl < level]
            steps = ho.route(self.graph, ho.ENTRY_ROOM, ho.DUNGEONS[level]["screen"], items)
            with self.subTest(level=level, items=items):
                self.assertIsNotNone(steps)

    def test_a_route_names_the_act_a_seal_needs(self) -> None:
        steps = ho.route(self.graph, ho.DUNGEONS[8]["screen"], ho.DUNGEONS[8]["entrance"],
                         ["the Red Candle"])
        self.assertIsNotNone(steps)
        self.assertIn("BURN BUSH", ho.describe(steps))

    def test_lines_route_the_asker_to_the_dungeon_they_are_working_on(self) -> None:
        state = {"room": ho.ENTRY_ROOM, "hyrule_next": 1, "hyrule_items": []}
        lines = ho.oracle_lines("where do I go next in hyrule?", state, self.rooms,
                                DIRECTIONS, self.graph)
        text = "\n".join(lines)
        self.assertIn("HYRULE, AS THIS ZONE WORKS", text)
        self.assertIn("working on Level 1", text)
        self.assertIn("Route from where the supplicant stands", text)
        self.assertIn("Eagle's Gate", text)

    def test_a_missing_tool_is_named_rather_than_routed_round(self) -> None:
        state = {"room": ho.ENTRY_ROOM, "hyrule_next": 4, "hyrule_items": []}
        lines = ho.oracle_lines("how do I get to level 5 dungeon?", state, self.rooms,
                                DIRECTIONS, self.graph)
        self.assertIn("the stepladder", "\n".join(lines))

    def test_not_about_hyrule_and_not_in_it_gets_nothing(self) -> None:
        state = {"room": 4207, "hyrule_next": 1, "hyrule_items": []}
        self.assertEqual(ho.oracle_lines("what does sanctuary do?", state, self.rooms,
                                         DIRECTIONS, self.graph), [])

    def test_the_guide_spells_out_each_band(self) -> None:
        for level in range(1, 10):
            band = ho.DUNGEONS[level]["band"]
            with self.subTest(level=level):
                self.assertIn(band, ho.GUIDE)


if __name__ == "__main__":
    unittest.main()
