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
MAP_OUTPUT = ROOT / "mudlet" / "toc-world-map.xml"

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


def load_world_rooms():
    """Every room in the shipped world, grouped into Mudlet areas.

    One Mudlet area per .are file. Mud School keeps area id 1 so an existing
    profile that already mapped it does not have its rooms shuffled into a
    different area; everything else is numbered by file name, which keeps the
    output byte-identical between runs and between machines.
    """
    sys.path.insert(0, str(ROOT))
    from webadmin.area_parser import AreaParser  # pylint: disable=import-outside-toplevel

    parser = AreaParser(ROOT / "area")
    parser.parse_all()

    rooms = dict(parser.rooms)
    missing = STARTER_ROOM_IDS - rooms.keys()
    if missing:
        raise RuntimeError(f"Mud School starter rooms are missing: {sorted(missing)}")

    by_file = {}
    for vnum, room in rooms.items():
        by_file.setdefault(room.area_file or "unknown", set()).add(vnum)

    school_file = next(
        (name for name, members in by_file.items() if 3700 in members), None
    )
    ordered = sorted(by_file)
    if school_file is not None:
        ordered.remove(school_file)
        ordered.insert(0, school_file)

    areas = []
    for index, name in enumerate(ordered, start=1):
        members = by_file[name]
        sample = rooms[min(members)]
        title = (sample.area_name or name).strip() or name
        areas.append((index, title, sorted(members)))

    return rooms, areas


def sector_index(room) -> int:
    """Best-effort sector number for a room.

    Four rooms in the shipped world do not yield a plain integer: mountain.are
    25022 uses ROM's bitwise `0|11` notation, valhalla.are 9945 and
    underdrk.are 25123 have records the C loader tolerates but that leave a
    word of prose here, and one room carries -1. None of that should stop the
    map being built, so fall back to Inside and keep the value in range.
    """
    raw = str(getattr(room, "sector_type", "0") or "0").strip()
    value = None
    if raw.lstrip("-").isdigit():
        value = int(raw)
    elif "|" in raw:
        parts = [part.strip() for part in raw.split("|")]
        if all(part.lstrip("-").isdigit() for part in parts if part):
            value = 0
            for part in parts:
                if part:
                    value |= int(part)
    if value is None or not 0 <= value <= 11:
        return 0
    return value


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
    rooms, areas = load_world_rooms()

    # Each Mudlet area has an independent coordinate space, so lay every area
    # out on its own. Sharing one space would push later areas thousands of
    # squares from the origin for no benefit.
    coordinates = {}
    area_of = {}
    for area_id, _title, members in areas:
        subset = {vnum: rooms[vnum] for vnum in members}
        coordinates.update(assign_coordinates(subset))
        for vnum in members:
            area_of[vnum] = area_id

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<map>",
        " <areas>",
    ]
    for area_id, title, _members in areas:
        lines.append(f'  <area id="{area_id}" name={quoteattr(title)} />')
    lines.extend((" </areas>", " <rooms>"))

    for vnum in sorted(rooms):
        room = rooms[vnum]
        sector = sector_index(room)
        x, y, z = coordinates[vnum]
        lines.append(
            f"  <room id={quoteattr(str(vnum))} area=\"{area_of[vnum]}\" "
            f"title={quoteattr(room.name)} environment={quoteattr(str(sector + 1))}>"
        )
        lines.append(f'   <coord x="{x}" y="{y}" z="{z}" />')
        for room_exit in sorted(room.exits, key=lambda item: item.direction):
            # Cross-area exits are kept: Mudlet links them fine and they are
            # what makes the atlas navigable as one world.
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
    # Stored entries avoid zlib-version-dependent bytes across build hosts.
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
        for filename in PACKAGE_FILES:
            source = PACKAGE_SOURCE / filename
            info = zipfile.ZipInfo(filename, date_time=(2026, 9, 11, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
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
