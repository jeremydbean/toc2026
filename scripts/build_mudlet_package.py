#!/usr/bin/env python3
"""Build and verify the official Times of Chaos Mudlet assets."""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections import deque
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE = ROOT / "mudlet" / "package"
PACKAGE_OUTPUT = ROOT / "mudlet" / "TimesOfChaos.mpackage"
MAP_OUTPUT = ROOT / "mudlet" / "toc-newbie-map.xml"

PACKAGE_FILES = ("config.lua", "TimesOfChaos.xml")
STARTER_ROOM_IDS = (frozenset(range(3700, 3723)) - {3706}) | {3757, 3758, 3759}
DIRECTION_NAMES = (
    "north", "east", "south", "west", "up", "down",
    "northeast", "northwest", "southeast", "southwest",
)
DIRECTION_OFFSET = {
    0: (0, 1, 0), 1: (1, 0, 0), 2: (0, -1, 0), 3: (-1, 0, 0),
    4: (0, 0, 1), 5: (0, 0, -1), 6: (1, 1, 0), 7: (-1, 1, 0),
    8: (1, -1, 0), 9: (-1, -1, 0),
}
SECTOR_NAMES = {
    0: "Inside", 1: "City", 2: "Field", 3: "Forest", 4: "Hills",
    5: "Mountains", 6: "Water", 7: "Deep water", 8: "Underwater",
    9: "Air", 10: "Desert", 11: "Underground",
}
SECTOR_COLOURS = {
    0: 8, 1: 7, 2: 10, 3: 2, 4: 11, 5: 15,
    6: 12, 7: 4, 8: 6, 9: 14, 10: 3, 11: 8,
}


def load_starter_rooms():
    sys.path.insert(0, str(ROOT))
    from webadmin.area_parser import AreaParser  # pylint: disable=import-outside-toplevel

    parser = AreaParser(ROOT / "area")
    parser.parse_area_file(ROOT / "area" / "school.are")
    rooms = {vnum: room for vnum, room in parser.rooms.items() if vnum in STARTER_ROOM_IDS}
    missing = STARTER_ROOM_IDS - rooms.keys()
    if missing:
        raise RuntimeError(f"Mud School starter rooms are missing: {sorted(missing)}")
    return rooms


def next_free_coordinate(desired, occupied):
    if desired not in occupied:
        return desired
    x, y, z = desired
    for radius in range(1, 100):
        candidates = (
            (x + radius, y, z), (x - radius, y, z),
            (x, y + radius, z), (x, y - radius, z),
        )
        for candidate in candidates:
            if candidate not in occupied:
                return candidate
    raise RuntimeError("Could not find a free Mud School map coordinate")


def assign_coordinates(rooms):
    coordinates = {}
    occupied = set()
    component_x = 0

    for root_vnum in sorted(rooms):
        if root_vnum in coordinates:
            continue
        root_coordinate = next_free_coordinate((component_x, 0, 0), occupied)
        coordinates[root_vnum] = root_coordinate
        occupied.add(root_coordinate)
        queue = deque([root_vnum])

        while queue:
            source_vnum = queue.popleft()
            source = rooms[source_vnum]
            source_coordinate = coordinates[source_vnum]
            for room_exit in source.exits:
                target_vnum = room_exit.to_room
                if target_vnum not in rooms or target_vnum in coordinates:
                    continue
                delta = DIRECTION_OFFSET[room_exit.direction]
                desired = tuple(source_coordinate[i] + delta[i] for i in range(3))
                target_coordinate = next_free_coordinate(desired, occupied)
                coordinates[target_vnum] = target_coordinate
                occupied.add(target_coordinate)
                queue.append(target_vnum)

        component_x = max(x for x, _, _ in occupied) + 8

    return coordinates


def build_map_bytes() -> bytes:
    rooms = load_starter_rooms()
    coordinates = assign_coordinates(rooms)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<map>",
        " <areas>",
        '  <area id="1" name="Hatchet Mud School" />',
        " </areas>",
        " <rooms>",
    ]

    for vnum in sorted(rooms):
        room = rooms[vnum]
        sector = int(room.sector_type)
        x, y, z = coordinates[vnum]
        lines.append(
            f"  <room id={quoteattr(str(vnum))} area=\"1\" "
            f"title={quoteattr(room.name)} environment={quoteattr(str(sector + 1))}>"
        )
        lines.append(f'   <coord x="{x}" y="{y}" z="{z}" />')
        for room_exit in sorted(room.exits, key=lambda item: item.direction):
            if room_exit.to_room not in rooms:
                continue
            lines.append(
                f"   <exit direction={quoteattr(DIRECTION_NAMES[room_exit.direction])} "
                f"target={quoteattr(str(room_exit.to_room))} />"
            )
        lines.append("  </room>")

    lines.extend((" </rooms>", " <environments>"))
    for sector in sorted(SECTOR_NAMES):
        lines.append(
            f'  <environment id="{sector + 1}" name={quoteattr(SECTOR_NAMES[sector])} '
            f'color="{SECTOR_COLOURS[sector]}" />'
        )
    lines.extend((" </environments>", "</map>", ""))
    data = "\n".join(lines).encode("utf-8")
    ElementTree.fromstring(data)
    return data


def build_package_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename in PACKAGE_FILES:
            source = PACKAGE_SOURCE / filename
            info = zipfile.ZipInfo(filename, date_time=(2026, 9, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    return output.getvalue()


def write_or_check(path: Path, expected: bytes, check: bool) -> bool:
    if check:
        if not path.exists() or path.read_bytes() != expected:
            print(f"out of date: {path.relative_to(ROOT)}", file=sys.stderr)
            return False
        print(f"verified: {path.relative_to(ROOT)}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    print(f"built: {path.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed assets")
    args = parser.parse_args()

    results = (
        write_or_check(MAP_OUTPUT, build_map_bytes(), args.check),
        write_or_check(PACKAGE_OUTPUT, build_package_bytes(), args.check),
    )
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
