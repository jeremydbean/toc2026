"""The directions router has to read the world the way the game reads it.

`.are` files are a token stream. fread_letter, fread_number and
fread_string all skip whitespace, so the game does not care whether a
record is written "#114" or "#114 ", whether a room's name sits on the
next line or the same one, or whether an exit says "D0" or "D 0". A
regex-based reader cares a great deal, and four separate assumptions in
tools/build_directions.py quietly dropped content that players can walk
to -- most visibly the portal from the Eye of the Storm into Mega-City
One, which made a 28-room area look unreachable.

These tests pin the router against the dashboard's independent parser and
against the specific records that were being missed. They read files only;
no server is booted.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_directions as bd  # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402


class RouterReadsTheWholeWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rooms = bd.load_world()
        cls.portals = bd.load_portals()
        for room, edges in bd.load_teleports().items():
            cls.portals.setdefault(room, []).extend(edges)

        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        cls.parser_rooms = set(parser.rooms)

    def test_it_finds_every_room_the_dashboard_parser_finds(self) -> None:
        missing = sorted(self.parser_rooms - set(self.rooms))
        self.assertEqual(
            [], missing,
            "the router lost rooms the dashboard parser reads: "
            + ", ".join(str(v) for v in missing[:8]))

    def test_no_exit_points_at_a_room_that_does_not_exist(self) -> None:
        """A dangling exit here means a record was misread, not deleted.

        check_exits.py reports the world clean, so any disagreement is the
        router's fault.
        """
        dangling = [(v, door, e[0])
                    for v, room in self.rooms.items()
                    for door, e in room["exits"].items()
                    if e[0] not in self.rooms]
        self.assertEqual([], dangling)

    def test_a_record_named_on_its_own_header_line_is_read(self) -> None:
        """chess.are writes "#24377 The White Queen's Chamber~"."""
        room = self.rooms.get(24377)
        self.assertIsNotNone(room, "The White Queen's Chamber went missing")
        self.assertEqual("The White Queen's Chamber", room["name"])

    def test_an_exit_described_on_its_own_D_line_is_read(self) -> None:
        """ag.are writes "D3 too dark to tell" on one line.

        Without it the Assassins Guild's upper floor has no way in.
        """
        self.assertEqual(17024, self.rooms[17022]["exits"][3][0])

    def test_a_portal_whose_header_has_a_trailing_space_is_placed(self) -> None:
        """connect.are writes "#114 " and resets it into the Eye of the Storm."""
        edges = self.portals.get(28, [])
        self.assertTrue(
            any(dest == 8001 for _verb, _kw, dest, _cost, _label in edges),
            "no way from the Eye of the Storm into Mega-City One")

    def test_manipulation_objects_are_edges(self) -> None:
        """The colossal oak at the Edge of the Woods is climbed, not entered."""
        edges = self.portals.get(29418, [])
        self.assertTrue(
            any(verb == "climb" and dest == 29497
                for verb, _kw, dest, _cost, _label in edges),
            "the oak no longer leads to the Treehouse")

    def test_teleport_rooms_are_edges(self) -> None:
        """The Assassins Guild's Transportation room carries you to 17027."""
        edges = self.portals.get(17025, [])
        self.assertTrue(
            any(verb == "wait" and dest == 17027
                for verb, _kw, dest, _cost, _label in edges),
            "the guild transportation chamber goes nowhere")

    def test_the_areas_that_looked_sealed_are_reachable(self) -> None:
        reach = bd.shortest_paths(self.rooms, bd.START, self.portals)
        for vnum, what in [
            (8001, "Mega-City One"),
            (29497, "the Treehouse in Mid-World"),
            (17027, "the Assassins Guild upper floor"),
            (24388, "The Joker's Throne"),
            (29082, "Korzath's Engineering Department"),
            (25027, "The Lonely Mountain"),
            (9160, "Dylan's front gate"),
        ]:
            with self.subTest(area=what):
                self.assertIn(vnum, reach, f"{what} is unreachable")


if __name__ == "__main__":
    unittest.main()
