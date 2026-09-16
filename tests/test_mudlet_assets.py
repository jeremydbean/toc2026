from __future__ import annotations

import importlib.util
import io
import re
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_mudlet_package", ROOT / "scripts" / "build_mudlet_package.py"
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class MudletAssetTests(unittest.TestCase):
    @staticmethod
    def package_script() -> str:
        root = ElementTree.fromstring(
            (ROOT / "mudlet" / "package" / "TimesOfChaos.xml").read_bytes()
        )
        return "\n".join(
            node.text or "" for node in root.findall(".//Script/script")
        )

    def test_generated_assets_are_current(self) -> None:
        self.assertEqual(
            (ROOT / "mudlet" / "toc-world-map.xml").read_bytes(),
            BUILDER.build_map_bytes(),
        )
        self.assertEqual(
            (ROOT / "mudlet" / "TimesOfChaos.mpackage").read_bytes(),
            BUILDER.build_package_bytes(),
        )

    def test_package_contains_valid_mudlet_xml(self) -> None:
        package = BUILDER.build_package_bytes()
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            self.assertEqual(
                set(archive.namelist()), {"config.lua", "TimesOfChaos.xml"}
            )
            self.assertTrue(all(
                entry.compress_type == zipfile.ZIP_STORED
                for entry in archive.infolist()
            ))
            root = ElementTree.fromstring(archive.read("TimesOfChaos.xml"))
        self.assertEqual(root.tag, "MudletPackage")

    def test_package_versions_match_server_advertisement(self) -> None:
        sources = (
            ROOT / "src" / "gmcp.c",
            ROOT / "mudlet" / "package" / "config.lua",
            ROOT / "mudlet" / "package" / "TimesOfChaos.xml",
        )
        patterns = (
            r'TOC_MUDLET_PACKAGE_VERSION\s+"([^"]+)"',
            r'version\s*=\s*"([^"]+)"',
            r'tocMudlet\.version\s*=\s*"([^"]+)"',
        )
        versions = []
        for source, pattern in zip(sources, patterns):
            match = re.search(pattern, source.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, source)
            versions.append(match.group(1))
        self.assertEqual(versions, [versions[0]] * len(versions))

    def test_dynamic_mapper_reconciles_changed_exits(self) -> None:
        script = self.package_script()
        self.assertIn("getRoomExits", script)
        self.assertIn("mapped[LONG_DIRECTION[direction]]", script)
        self.assertIn("pcall(setExit, roomId, -1, direction)", script)
        self.assertIn("pcall(setExitStub, roomId, direction, false)", script)

    @unittest.skipUnless(shutil.which("lua"), "Lua interpreter is not installed")
    def test_package_lua_compiles(self) -> None:
        result = subprocess.run(
            ["lua", "-e", 'assert(load(io.read("*a")))'],
            input=self.package_script(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_player_help_covers_mapper_and_clients(self) -> None:
        help_text = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        for heading in (
            "0 MAP MAPPER AUTOMAP AUTOMAPPER MAPPING~",
            "0 MUDLET TOCGUI~",
            "0 GMCP~",
            "0 WEBCLIENT BROWSERCLIENT BROWSER~",
        ):
            self.assertIn(heading, help_text)
        for detail in (
            "tocgui status",
            "Room.Info",
            "Secret exits are not sent",
            "removed or points somewhere new",
            "browser client and plain Telnet do not currently show",
        ):
            self.assertIn(detail, help_text)

    def test_world_map_covers_every_room_without_overlaps(self) -> None:
        """The shipped atlas is what makes the Mudlet map look deliberate.

        Placing rooms by walking gives overlapping squares wherever the world
        is not a grid, which is most of it. The generator lays each area out
        offline instead, so the contract is: every room present, and no two
        rooms in an area sharing a square.
        """
        root = ElementTree.fromstring(BUILDER.build_map_bytes())
        room_nodes = root.find("rooms").findall("room")
        room_ids = {int(room.attrib["id"]) for room in room_nodes}

        rooms, areas = BUILDER.load_world_rooms()
        self.assertEqual(room_ids, set(rooms), "atlas does not cover every room")
        self.assertGreater(len(room_ids), 7000)

        # Mudlet gives each area its own coordinate space, so uniqueness is
        # per area, not global.
        seen = {}
        for room in room_nodes:
            coord = room.find("coord")
            key = (
                room.attrib["area"],
                coord.attrib["x"],
                coord.attrib["y"],
                coord.attrib["z"],
            )
            self.assertNotIn(
                key, seen, f"rooms {seen.get(key)} and {room.attrib['id']} overlap"
            )
            seen[key] = room.attrib["id"]

        for room in room_nodes:
            for room_exit in room.findall("exit"):
                self.assertIn(int(room_exit.attrib["target"]), room_ids)

        declared = {area.attrib["id"] for area in root.find("areas").findall("area")}
        self.assertEqual(declared, {str(area_id) for area_id, _, _ in areas})

    def test_world_map_area_names_match_what_gmcp_sends(self) -> None:
        """A name mismatch would silently duplicate every area.

        The package looks areas up by name, so if the map says one thing and
        Room.Info says another, Mudlet creates a second area and the prebuilt
        layout is wasted.
        """
        gmcp_source = (ROOT / "src" / "gmcp.c").read_text(encoding="utf-8")
        self.assertIn("gmcp_area_name", gmcp_source)

        def as_gmcp_sends(raw: str) -> str:
            # Mirrors gmcp_area_name(): strip a leading {...} and whitespace.
            name = (raw or "").lstrip()
            if name.startswith("{"):
                brace = name.find("}")
                if brace != -1:
                    name = name[brace + 1:].lstrip()
            return name or "Unknown Area"

        rooms, _areas = BUILDER.load_world_rooms()
        expected = {as_gmcp_sends(room.area_name) for room in rooms.values()}

        root = ElementTree.fromstring(BUILDER.build_map_bytes())
        declared = {area.attrib["name"] for area in root.find("areas").findall("area")}
        self.assertEqual(expected - declared, set())

    def test_mud_school_remains_area_one_and_connected(self) -> None:
        """Mud School keeps area 1 so existing profiles are not reshuffled."""
        root = ElementTree.fromstring(BUILDER.build_map_bytes())
        areas = root.find("areas").findall("area")
        self.assertEqual(areas[0].attrib["id"], "1")
        self.assertIn("Mud School", areas[0].attrib["name"])

        school = {
            int(room.attrib["id"])
            for room in root.find("rooms").findall("room")
            if room.attrib["area"] == "1"
        }
        self.assertTrue(set(BUILDER.STARTER_ROOM_IDS) <= school)

        graph = {room_id: set() for room_id in school}
        for room in root.find("rooms").findall("room"):
            if room.attrib["area"] != "1":
                continue
            source = int(room.attrib["id"])
            for room_exit in room.findall("exit"):
                target = int(room_exit.attrib["target"])
                if target in school:
                    graph[source].add(target)
                    graph[target].add(source)

        visited, pending = set(), [min(BUILDER.STARTER_ROOM_IDS)]
        while pending:
            room_id = pending.pop()
            if room_id in visited:
                continue
            visited.add(room_id)
            pending.extend(graph[room_id] - visited)
        self.assertTrue(set(BUILDER.STARTER_ROOM_IDS) <= visited)


if __name__ == "__main__":
    unittest.main()
