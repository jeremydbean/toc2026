from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from webadmin.area_health import _world_room_components, build_area_health
from webadmin.area_parser import AreaParser, ROOM_FLAGS, decode_flags, parse_flag_value


class AreaHealthTests(unittest.TestCase):
    def test_world_connectivity_includes_teleports_and_travel_objects(self) -> None:
        parser = SimpleNamespace(
            rooms={
                1: SimpleNamespace(vnum=1, exits=[], teleport_to_room=2, objects=[]),
                2: SimpleNamespace(vnum=2, exits=[], teleport_to_room=None, objects=[10]),
                3: SimpleNamespace(vnum=3, exits=[], teleport_to_room=None, objects=[]),
            },
            objects={10: SimpleNamespace(item_type="31", values=["6", "3"])},
        )

        component_by_room = _world_room_components(parser)

        self.assertEqual(len(set(component_by_room.values())), 1)

    def test_world_connectivity_includes_operational_pet_storage(self) -> None:
        parser = SimpleNamespace(
            rooms={
                10: SimpleNamespace(
                    vnum=10,
                    room_flags="4096",
                    exits=[],
                    teleport_to_room=None,
                    objects=[],
                ),
                11: SimpleNamespace(
                    vnum=11,
                    room_flags="0",
                    exits=[],
                    teleport_to_room=None,
                    objects=[],
                ),
                12: SimpleNamespace(
                    vnum=12,
                    room_flags="0",
                    exits=[],
                    teleport_to_room=None,
                    objects=[],
                ),
            },
            objects={},
            mobiles={20: SimpleNamespace(spawn_rooms=[10])},
            mob_specials={20: "spec_pet_shop_owner"},
        )

        component_by_room = _world_room_components(parser)

        self.assertEqual(component_by_room[10], component_by_room[11])
        self.assertNotEqual(component_by_room[10], component_by_room[12])

    def test_flag_parser_matches_rom_numeric_and_pipe_syntax(self) -> None:
        self.assertEqual(parse_flag_value("CDM"), 4108)
        self.assertEqual(parse_flag_value("8|4096"), 4104)
        self.assertEqual(parse_flag_value("524"), 524)
        self.assertEqual(decode_flags("8|4096", ROOM_FLAGS), ["indoors", "pet_shop"])

    def test_room_parser_accepts_spaced_exit_direction(self) -> None:
        content = """#AREA { 1 1 } Parser Test~
#ROOMS
#1
First Room~
The first test room.~
TT 0 0
D 2
A passage leads south.~
~
0 -1 2
S
#2
Second Room~
The second test room.~
TT 32 0
1 5 1
D0
A passage leads north.~
~
0 -1 1
S
#3
Flags2 Room~
The room uses a numeric ROOM_FLAGS2 marker.~
TT 33554432 A 0
S
#0
#RESETS
S
"""

        with tempfile.TemporaryDirectory() as temporary_directory:
            area_path = Path(temporary_directory)
            area_file = area_path / "parser-test.are"
            area_file.write_text(content, encoding="latin-1")
            parser = AreaParser(area_path)
            parser.parse_area_file(area_file)

        self.assertEqual(
            [(exit_data.direction, exit_data.to_room) for exit_data in parser.rooms[1].exits],
            [(2, 2)],
        )
        self.assertEqual(
            [(exit_data.direction, exit_data.to_room) for exit_data in parser.rooms[2].exits],
            [(0, 1)],
        )
        self.assertEqual(parser.rooms[2].teleport_to_room, 1)
        self.assertEqual(parser.rooms[3].room_flags2, "A")
        self.assertEqual(parser.rooms[3].sector_type, "0")

    def test_parse_all_replaces_stale_state(self) -> None:
        parser = AreaParser(Path("area"))
        parser.parse_all()
        expected_counts = (
            len(parser.areas),
            len(parser.mobiles),
            len(parser.objects),
            len(parser.rooms),
        )

        parser.errors.append({"file": "stale.are", "error": "old failure"})
        parser.rooms[-1] = next(iter(parser.rooms.values()))
        parser.parse_all()

        self.assertEqual(
            (
                len(parser.areas),
                len(parser.mobiles),
                len(parser.objects),
                len(parser.rooms),
            ),
            expected_counts,
        )
        self.assertNotIn(-1, parser.rooms)
        self.assertEqual(parser.errors, [])

    def test_container_reset_counts_as_object_source(self) -> None:
        content = """#AREA { 1 1 } Container Test~
#OBJECTS
#10
chest~
a chest~
A chest rests here.~
wood~
15 0 0
10 A 0 0 0
0 1 0 P
#11
gem~
a gem~
A gem sparkles here.~
glass~
8 0 A
0 0 0 0 0
1 1 1 P
#0
#ROOMS
#1
Test Room~
A test room.~
0 0 0
S
#0
#RESETS
O 0 10 1 1
P 0 11 1 10
S
#$
"""

        with tempfile.TemporaryDirectory() as temporary_directory:
            area_path = Path(temporary_directory)
            (area_path / "area.lst").write_text("container.are\n$\n", encoding="latin-1")
            (area_path / "container.are").write_text(content, encoding="latin-1")
            parser = AreaParser(area_path)
            parser.parse_all()
            result = build_area_health(parser, area_path)

        self.assertEqual(parser.objects[11].contained_by, [10])
        self.assertFalse(
            any(
                issue["code"] == "object-has-no-source" and issue.get("vnum") == 11
                for issue in result["issues"]
            )
        )

    def test_area_health_has_expected_summary_shape(self) -> None:
        area_path = Path("area")
        parser = AreaParser(area_path)
        parser.parse_all()

        result = build_area_health(parser, area_path)
        summary = result["summary"]

        self.assertGreater(summary["areas"], 0)
        self.assertGreater(summary["mobiles"], 0)
        self.assertGreater(summary["objects"], 0)
        self.assertGreater(summary["rooms"], 0)
        self.assertIn("critical", summary["by_severity"])
        self.assertIn("warning", summary["by_severity"])
        self.assertIn("info", summary["by_severity"])
        self.assertEqual(summary["by_severity"]["critical"], 0)

        warning_areas = {
            issue.get("area_file")
            for issue in result["issues"]
            if issue["severity"] == "warning"
            and issue["code"] == "disconnected-area-rooms"
        }
        self.assertFalse(
            warning_areas
            & {
                "camelot.are",
                "dresden.are",
                "htower.are",
                "korzath2.are",
                "limbo.are",
                "ratslair.are",
                "redfern.are",
                "solace.are",
                "voyage.are",
                "world.are",
            }
        )
        self.assertTrue(
            any(
                issue["code"] == "restricted-isolated-rooms"
                and issue.get("area_file") == "limbo.are"
                for issue in result["issues"]
            )
        )
        self.assertEqual(parser.mob_specials.get(13211), "spec_pet_shop_owner")

        issues = result["issues"]
        self.assertFalse(
            any(
                issue["code"] == "object-level-outlier"
                and issue.get("detail", {}).get("level") == -1
                for issue in issues
            )
        )
        self.assertFalse(
            any(
                issue["code"] == "exit-target-missing"
                and issue.get("detail", {}).get("to_room") == -1
                for issue in issues
            )
        )
        self.assertFalse(
            any(
                issue.get("area_file") == "commands.are"
                and issue["code"] in {"area-has-no-rooms", "area-has-no-content"}
                for issue in issues
            )
        )


if __name__ == "__main__":
    unittest.main()
