from __future__ import annotations

import importlib.util
import io
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
