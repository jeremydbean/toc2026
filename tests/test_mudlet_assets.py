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
            (ROOT / "mudlet" / "toc-newbie-map.xml").read_bytes(),
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

    def test_starter_map_is_connected_and_has_unique_coordinates(self) -> None:
        root = ElementTree.fromstring(BUILDER.build_map_bytes())
        rooms = root.find("rooms")
        self.assertIsNotNone(rooms)
        room_nodes = rooms.findall("room")
        room_ids = {int(room.attrib["id"]) for room in room_nodes}
        self.assertEqual(room_ids, set(BUILDER.STARTER_ROOM_IDS))

        coordinates = {
            tuple(room.find("coord").attrib[key] for key in ("x", "y", "z"))
            for room in room_nodes
        }
        self.assertEqual(len(coordinates), len(room_nodes))

        graph = {room_id: set() for room_id in room_ids}
        for room in room_nodes:
            source = int(room.attrib["id"])
            for room_exit in room.findall("exit"):
                target = int(room_exit.attrib["target"])
                graph[source].add(target)
                graph[target].add(source)

        visited = set()
        pending = [min(room_ids)]
        while pending:
            room_id = pending.pop()
            if room_id in visited:
                continue
            visited.add(room_id)
            pending.extend(graph[room_id] - visited)
        self.assertEqual(visited, room_ids)


if __name__ == "__main__":
    unittest.main()
