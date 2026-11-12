"""The Mudlet atlas is laid out so each map reads cleanly.

Owner, 2026-11-12, from a Mudlet 5.1.1 screenshot: "the way the layers look
on the map in mudlet is disorienting", then "it's the map everywhere.
dresden is a mess" and "why do i see every box that seems to overlap with it
all". Three things made it so, each held here:

* The generator squeezed a room whose square was taken onto the nearest
  free one, which bent every exit around it, and packed cities into solid
  blocks where neighbouring squares were not neighbouring rooms. It now
  opens the level instead (scripts/build_mudlet_package.py, layout_area),
  so exits keep their direction; this module holds the share of exits drawn
  straight, world-wide and for Dresden.
* Mudlet 5 draws the rooms of the level above and below the one shown,
  faintly, in the same area. The package turns that off
  (setConfig "showUpperLowerLevels"), played in tests/mudlet_fog_spec.lua.
* Hyrule's dungeons were drawn in the overworld's area: a plan ten levels
  under it, and rooms walked into one step from the room walked from. Each
  dungeon is now a map area of its own, on its floor plan, from the game
  (hyrule_map_place in src/hyrule.c, Room.Info's "map").
"""
from __future__ import annotations

import collections
import importlib.util
import json
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_mudlet_package", ROOT / "scripts" / "build_mudlet_package.py")
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

DIRECTIONS = {name: index for index, name in enumerate(BUILDER.DIRECTION_NAMES)}
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))


def atlas():
    root = ElementTree.fromstring((ROOT / "mudlet" / "toc-world-map.xml").read_bytes())
    names = {area.attrib["id"]: area.attrib["name"] for area in root.find("areas")}
    rooms = {}
    for room in root.find("rooms"):
        coord = room.find("coord")
        rooms[int(room.attrib["id"])] = (
            room.attrib["area"],
            (int(coord.attrib["x"]), int(coord.attrib["y"]), int(coord.attrib["z"])),
            [(DIRECTIONS[e.attrib["direction"]], int(e.attrib["target"]))
             for e in room.findall("exit")])
    return names, rooms


def straight_share(rooms, area=None):
    drawn = straight = 0
    for _vnum, (where, at, exits) in rooms.items():
        if area is not None and where != area:
            continue
        for direction, target in exits:
            if rooms[target][0] != where:
                continue        # an area exit: Mudlet draws a stub arrow
            drawn += 1
            straight += BUILDER.exit_drawn_straight(at, rooms[target][1], direction)
    return straight / drawn, drawn


class AtlasLayoutTests(unittest.TestCase):
    def test_no_two_rooms_of_an_area_share_a_square(self) -> None:
        _names, rooms = atlas()
        squares = collections.defaultdict(list)
        for vnum, (area, at, _exits) in rooms.items():
            squares[(area, at)].append(vnum)
        stacked = {key: vnums for key, vnums in squares.items() if len(vnums) > 1}
        self.assertEqual(stacked, {})

    def test_exits_are_drawn_in_their_own_direction(self) -> None:
        """95% world-wide and 91% in Dresden on 2026-11-12, against
        89% and 73% before; the floor leaves room for new rooms."""
        names, rooms = atlas()
        share, drawn = straight_share(rooms)
        self.assertGreater(drawn, 15000)
        self.assertGreaterEqual(share, 0.94, f"{share:.3f} of {drawn} exits drawn straight")
        dresden = next(key for key, name in names.items() if "City of Dresden" in name)
        share, drawn = straight_share(rooms, dresden)
        self.assertGreaterEqual(share, 0.88, f"Dresden: {share:.3f} of {drawn}")

    def test_the_straight_rule_is_mudlets(self) -> None:
        """A planar exit is a line to wherever its room is; up and down are
        a mark in the room and no line (TMapPainter.cpp)."""
        ok = BUILDER.exit_drawn_straight
        self.assertTrue(ok((0, 0, 0), (0, 1, 0), 0))
        self.assertTrue(ok((0, 0, 0), (0, 4, 0), 0), "a stretched exit is still straight")
        self.assertFalse(ok((0, 0, 0), (1, 1, 0), 0))
        self.assertFalse(ok((0, 0, 0), (0, 1, 1), 0), "a line to another level is not")
        self.assertTrue(ok((0, 0, 0), (2, 2, 0), 6))
        self.assertFalse(ok((0, 0, 0), (2, 1, 0), 6))
        self.assertTrue(ok((0, 0, 0), (5, -3, 1), 4), "up needs only the level above")
        self.assertFalse(ok((0, 0, 0), (0, 0, 2), 4))

    def test_the_build_refuses_a_stacked_square(self) -> None:
        source = (ROOT / "scripts" / "build_mudlet_package.py").read_text(encoding="utf-8")
        build = source.split("def build_map_bytes()", 1)[1]
        self.assertIn("share {laid[vnum]}", build)

    def test_the_layout_is_deterministic(self) -> None:
        rooms, areas = BUILDER.load_world_rooms()
        _area_id, _title, members = next(a for a in areas if "Dresden" in a[1])
        subset = {vnum: rooms[vnum] for vnum in members}
        self.assertEqual(BUILDER.layout_area(subset), BUILDER.layout_area(dict(subset)))


class HyruleDungeonAreaTests(unittest.TestCase):
    def test_every_dungeon_is_a_map_area_of_its_own(self) -> None:
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        table = hyrule.split("hyrule_map_area_names[10] =", 1)[1].split("};", 1)[0]
        names = re.findall(r'"([^"]*)"', table)[1:]
        self.assertEqual(len(names), 9)
        self.assertEqual(len(set(names)), 9)
        overworld = {name for name in atlas()[0].values() if "Hyrule" in name}
        for level, (name, dungeon) in enumerate(zip(names, MANIFEST["dungeons"]), start=1):
            with self.subTest(level=level):
                self.assertEqual(name, f"Hyrule: Level {level} ({dungeon['title']})")
                self.assertNotIn(name, overworld)

    def test_room_info_and_the_plan_name_the_dungeon_area(self) -> None:
        gmcp = (ROOT / "src" / "gmcp.c").read_text(encoding="latin-1")
        room = gmcp.split("void gmcp_send_room(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_map_place( room, &level, &x, &y, &z )", room)
        self.assertIn('",\\"map\\":{\\"area\\":"', room.replace(" ", ""))
        plan = gmcp.split("void gmcp_send_map_room(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_map_area_name( level )", plan)

    def test_the_package_keeps_the_atlas_area_and_takes_the_dungeons(self) -> None:
        package = (ROOT / "mudlet" / "package" / "TimesOfChaos.xml").read_text(encoding="utf-8")
        ensure = package.split("local function ensureRoom(roomId, info)", 1)[1].split("\nend\n", 1)[0]
        self.assertIn("info.map", ensure)
        self.assertIn("roomAreaId(roomId) <= 0", ensure,
                      "Room.Info's area must not move a room the atlas placed")
        self.assertIn('setConfig, "showUpperLowerLevels"', package)


if __name__ == "__main__":
    unittest.main()
