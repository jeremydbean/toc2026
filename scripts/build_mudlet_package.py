#!/usr/bin/env python3
"""Build and verify the official Times of Chaos Mudlet assets."""

from __future__ import annotations

import argparse
import dataclasses
import heapq
import io
import json
import sys
import zipfile
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


def secret_exits(parser):
    """Every exit a player finds secret: (room vnum, direction).

    Read as the game reads it. load_rooms makes any exit whose keyword
    starts with "secret" lock 4; a door with lock 4 is made secret by its
    'D' reset (load_resets forces such a reset to state 4) and again by
    CLOSE whenever somebody shuts it; and a 'D' reset in state 4 hides any
    door it names -- Hyrule's bomb walls, bushes and Armos among them.
    """
    resets = {}
    for area_resets in parser.resets.values():
        for reset in area_resets:
            if reset.command == "D":
                resets[(reset.arg1, reset.arg2)] = reset.arg3
    hidden = set()
    for vnum, room in parser.rooms.items():
        for room_exit in room.exits:
            lock = room_exit.locks
            if (room_exit.keyword or "").strip().lower().startswith("secret"):
                lock = 4
            if lock == 4 or resets.get((vnum, room_exit.direction)) == 4:
                hidden.add((vnum, room_exit.direction))
    return hidden


def load_world_rooms():
    """Every room in the shipped world, grouped into Mudlet areas.

    One Mudlet area per .are file. Mud School keeps area id 1 so an existing
    profile that already mapped it does not have its rooms shuffled into a
    different area; everything else is numbered by file name, which keeps the
    output byte-identical between runs and between machines.
    """
    sys.path.insert(0, str(ROOT))
    from webadmin.area_parser import (  # pylint: disable=import-outside-toplevel
        ROOM_FLAGS, AreaParser, decode_flags)

    # Only what is committed: an area built in game (area/built/) changes
    # with every state sync, and a committed map must never depend on it.
    parser = AreaParser(ROOT / "area")
    parser.parse_all(built=False)

    # Death traps stay off the starter map: you should find one the hard
    # way, not read it off the atlas. Exits into them are dropped with them
    # (build_map_bytes skips any exit whose target is not on the map), so
    # nothing points at the gap either. GMCP still sends the room when you
    # walk into one, so the mapper learns it then -- the owner's rule.
    #
    # Hyrule's nine dungeons stay off it too (owner, 2026-10-04): a dungeon
    # is drawn when its dungeon map is found -- the game sends the plan as
    # Hyrule.MapRoom -- or room by room as it is walked. The overworld is
    # on the map from the start.
    dungeons = json.loads((ROOT / "data" / "hyrule_first_quest.json")
                          .read_text(encoding="utf-8"))["dungeons"]
    hidden = set()
    for dungeon in dungeons:
        hidden.update(range(dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1))
    #
    # Secret exits are left off as well: the map would otherwise point at
    # every hidden door in the world. The rooms behind one stay on the map,
    # laid out only by the exits a player can see, so where they sit does
    # not give the door away either.
    secret = secret_exits(parser)
    rooms = {vnum: dataclasses.replace(room, exits=[
                 room_exit for room_exit in room.exits
                 if (vnum, room_exit.direction) not in secret])
             for vnum, room in parser.rooms.items()
             if "deathtrap" not in decode_flags(room.room_flags, ROOM_FLAGS)
             and vnum not in hidden}
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


def room_title(room) -> str:
    """A room's name on one line. fread_string keeps a name's line breaks:
    valhalla.are 9945 writes its name across two lines, and underdrk.are
    25123 puts the tilde on the line after it."""
    return room.name.rstrip("\n").replace("\n", " ")


def sector_index(room) -> int:
    """Best-effort sector number for a room.

    Two rooms in the shipped world do not yield a plain integer in range:
    mountain.are 25022 uses ROM's `0|11` notation, which fread_number adds
    up, and one room carries -1. Neither should stop the map being built, so
    fall back to Inside and keep the value in range. (valhalla.are 9945 and
    underdrk.are 25123 used to leave a word of prose here too: the old line
    reader took the first line of a two-line name for all of it.)
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


REVERSE_DIRECTION = {0: 2, 1: 3, 2: 0, 3: 1, 4: 5, 5: 4, 6: 9, 7: 8, 8: 7, 9: 6}
UP_DOWN = (4, 5)


def exit_drawn_straight(source, target, direction) -> bool:
    """Whether Mudlet draws this exit as a line in its own direction.

    Mudlet's 2D map draws a planar exit as a straight line from the room to
    wherever the target sits in the same area, ignoring z; up and down are a
    triangle inside the room and no line at all. So an up/down exit reads
    right whenever the target is on the level above or below, and a planar
    exit whenever the target lies along the exit's own ray on the same level
    -- one square away or ten. Anything else is a line at a wrong angle, or
    one to a room on another level that is not drawn, which is what made the
    old layout a tangle.
    """
    delta = DIRECTION_OFFSET[direction]
    dx, dy, dz = (target[i] - source[i] for i in range(3))
    if direction in UP_DOWN:
        return dz == delta[2]
    steps = max(abs(dx), abs(dy))
    return dz == 0 and steps > 0 and (dx, dy) == (delta[0] * steps, delta[1] * steps)


def _links(rooms):
    """Each room's ways to its neighbours in the area, both ends of every
    exit: {vnum: [(cost, offset to the neighbour, neighbour)]}.

    An exit that comes back the way it went is the surest guide to where a
    room lies (cost 0); a one-way or mismatched exit less so (4), and the
    far end of an exit, read backwards, least (6). Up and down cost one
    more, so a level is laid out before the next is started.
    """
    links = {vnum: [] for vnum in rooms}
    for vnum, room in rooms.items():
        for room_exit in room.exits:
            target = room_exit.to_room
            if target not in rooms or target == vnum:
                continue
            delta = DIRECTION_OFFSET[room_exit.direction]
            vertical = 1 if room_exit.direction in UP_DOWN else 0
            back = any(e.direction == REVERSE_DIRECTION[room_exit.direction]
                       and e.to_room == vnum for e in rooms[target].exits)
            links[vnum].append(((0 if back else 4) + vertical, delta, target))
            if not back:
                links[target].append((6 + vertical, (-delta[0], -delta[1], -delta[2]), vnum))
    return links


def _components(rooms, links):
    """The area's connected parts, largest first, each as a sorted list."""
    seen = set()
    parts = []
    for start in sorted(rooms):
        if start in seen:
            continue
        seen.add(start)
        part, pending = [], [start]
        while pending:
            vnum = pending.pop()
            part.append(vnum)
            for _cost, _delta, other in links[vnum]:
                if other not in seen:
                    seen.add(other)
                    pending.append(other)
        parts.append(sorted(part))
    parts.sort(key=lambda part: (-len(part), part[0]))
    return parts


def _place_by_insertion(part, links):
    """First pass: grow one connected part from its best-connected room.

    The surest links are followed first (_links). A room whose square is
    taken is not squeezed in beside it, which bent every exit around it:
    the level is opened instead -- every room on it at or past that square
    moves one step on in the exit's direction -- so the exit keeps its
    direction and the exits the cut crosses are only stretched, still
    straight. Opening a half-plane moves everything in it alike, so it can
    never put two rooms on one square. A room up or down whose square is
    taken goes a level further.
    """
    coordinates = {}
    occupied = {}
    sequence = 0
    root = min(part, key=lambda vnum: (-len(links[vnum]), vnum))
    coordinates[root] = (0, 0, 0)
    occupied[(0, 0, 0)] = root
    frontier = []

    def push(source):
        nonlocal sequence
        for cost, delta, target in links[source]:
            if target not in coordinates:
                sequence += 1
                heapq.heappush(frontier, (cost, sequence, source, delta, target))

    push(root)
    while frontier:
        _cost, _seq, source, delta, target = heapq.heappop(frontier)
        if target in coordinates:
            continue
        base = coordinates[source]
        want = (base[0] + delta[0], base[1] + delta[1], base[2] + delta[2])
        if want in occupied and delta[2]:
            z = want[2]
            while (want[0], want[1], z) in occupied:
                z += delta[2]
            want = (want[0], want[1], z)
        elif want in occupied:
            level = want[2]
            moved = {}
            for vnum, (x, y, z) in coordinates.items():
                if z != level:
                    continue
                nx, ny = x, y
                if delta[0] > 0 and x >= want[0]:
                    nx += 1
                elif delta[0] < 0 and x <= want[0]:
                    nx -= 1
                if delta[1] > 0 and y >= want[1]:
                    ny += 1
                elif delta[1] < 0 and y <= want[1]:
                    ny -= 1
                if (nx, ny) != (x, y):
                    moved[vnum] = (nx, ny, z)
            for vnum in moved:
                del occupied[coordinates[vnum]]
            for vnum, coordinate in moved.items():
                coordinates[vnum] = coordinate
                occupied[coordinate] = vnum
        coordinates[target] = want
        occupied[want] = target
        push(target)
    return coordinates


def _pack(blocks):
    """Lay the parts of an area out side by side in rows, largest first.

    Each block is {vnum: (x, y, z)}; its footprint is taken over every
    level, so no two parts share a square on any of them. A row is as wide
    as the largest part, or forty squares, so a long tail of one-room parts
    (Hyrule's caves, the rooms only a portal reaches) wraps under the main
    map instead of running off to the right.
    """
    gap = 3
    shelf_width = 40
    placed = {}
    x_cursor = y_cursor = 0
    shelf_height = 0
    for index, block in enumerate(blocks):
        # The level holding most of a part's rooms is its ground floor, z 0
        # (ties to the lower level), whichever room the layout grew it from.
        levels = {}
        for _x, _y, z in block.values():
            levels[z] = levels.get(z, 0) + 1
        ground = min(levels, key=lambda z: (-levels[z], z))
        block = {vnum: (x, y, z - ground) for vnum, (x, y, z) in block.items()}
        xs = [c[0] for c in block.values()]
        ys = [c[1] for c in block.values()]
        width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        if index == 0:
            shelf_width = max(shelf_width, width)
        elif x_cursor > 0 and x_cursor + width > shelf_width:
            y_cursor -= shelf_height + gap
            x_cursor = shelf_height = 0
        # top-left of the block at (x_cursor, y_cursor); y grows north
        dx, dy = x_cursor - min(xs), y_cursor - max(ys)
        for vnum, (x, y, z) in block.items():
            placed[vnum] = (x + dx, y + dy, z)
        x_cursor += width + gap
        shelf_height = max(shelf_height, height)
    return placed


def _settle(rooms, coordinates, radius=3, passes=6):
    """Second pass: move or swap single rooms while that straightens exits.

    What the world's geometry cannot agree with (a loop whose sides differ,
    an exit that does not come back the way it went) still bends somewhere;
    this pulls each such room to the free square, or swaps it with the
    room on the square, that its exits agree with best. Deterministic: rooms
    and squares are visited in sorted order and only a strict gain moves.
    """
    coordinates = dict(coordinates)
    occupied = {c: v for v, c in coordinates.items()}
    neighbours = {vnum: [] for vnum in rooms}
    for vnum, room in rooms.items():
        for room_exit in room.exits:
            if room_exit.to_room in rooms and room_exit.to_room != vnum:
                delta = DIRECTION_OFFSET[room_exit.direction]
                neighbours[vnum].append((room_exit.to_room, delta))
                neighbours[room_exit.to_room].append(
                    (vnum, (-delta[0], -delta[1], -delta[2])))

    def exit_cost(a, b, delta):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        if delta[2]:
            return 0.0 if dz == delta[2] else 3.0
        if (dx, dy, dz) == delta:
            return 0.0
        steps = max(abs(dx), abs(dy))
        if dz == 0 and steps and (dx, dy) == (delta[0] * steps, delta[1] * steps):
            return 0.05 * (steps - 1)
        off = abs(dx - delta[0]) + abs(dy - delta[1])
        return (6.0 + off) if dz else (1.0 + 0.3 * off)

    def room_cost(vnum, at):
        return sum(exit_cost(at, coordinates[other], delta)
                   for other, delta in neighbours[vnum])

    for _ in range(passes):
        moved = 0
        for vnum in sorted(rooms):
            here = coordinates[vnum]
            cost = room_cost(vnum, here)
            if cost == 0:
                continue
            candidates = {(coordinates[o][0] - d[0], coordinates[o][1] - d[1],
                           coordinates[o][2] - d[2]) for o, d in neighbours[vnum]}
            candidates.update((here[0] + dx, here[1] + dy, here[2])
                              for dx in range(-radius, radius + 1)
                              for dy in range(-radius, radius + 1))
            best, best_gain = None, 1e-9
            for spot in sorted(candidates):
                if spot == here:
                    continue
                other = occupied.get(spot)
                if other is None:
                    gain = cost - room_cost(vnum, spot)
                else:
                    before = cost + room_cost(other, spot)
                    coordinates[vnum], coordinates[other] = spot, here
                    after = room_cost(vnum, spot) + room_cost(other, here)
                    coordinates[vnum], coordinates[other] = here, spot
                    gain = before - after
                if gain > best_gain:
                    best, best_gain = (spot, other), gain
            if best is None:
                continue
            spot, other = best
            if other is None:
                del occupied[here]
            else:
                occupied[here] = other
                coordinates[other] = here
            occupied[spot] = vnum
            coordinates[vnum] = spot
            moved += 1
        if not moved:
            break
    return coordinates


def layout_area(rooms):
    """Coordinates for one Mudlet area's rooms: {vnum: (x, y, z)}.

    No two rooms share a square (checked again in build_map_bytes), and as
    many exits as the world's geometry allows are drawn straight in their
    own direction (exit_drawn_straight). The old breadth-first layout put a
    room whose square was taken on the nearest free one, which bent every
    exit around it and stacked the city into a block where neighbouring
    squares were not neighbouring rooms -- 1,700 of the world's planar exits
    drawn at a wrong angle, against about 640 now. Each connected part is
    laid out on its own and the parts packed in rows (_pack), so opening a
    level for one part never stretches another.
    """
    links = _links(rooms)
    blocks = []
    for part in _components(rooms, links):
        subset = {vnum: rooms[vnum] for vnum in part}
        blocks.append(_settle(subset, _place_by_insertion(part, links)))
    return _pack(blocks)


def build_map_bytes() -> bytes:
    rooms, areas = load_world_rooms()

    # Each Mudlet area has an independent coordinate space, so lay every area
    # out on its own. Sharing one space would push later areas thousands of
    # squares from the origin for no benefit.
    coordinates = {}
    area_of = {}
    for area_id, title, members in areas:
        subset = {vnum: rooms[vnum] for vnum in members}
        laid = layout_area(subset)
        # Two rooms on one square of one area is the stacking the owner saw
        # (2026-11-12): never ship it, whatever the layout does.
        squares = {}
        for vnum in members:
            other = squares.setdefault(laid[vnum], vnum)
            if other != vnum:
                raise RuntimeError(
                    f"{title}: rooms {other} and {vnum} share {laid[vnum]}")
        coordinates.update(laid)
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
            f"title={quoteattr(room_title(room))} environment={quoteattr(str(sector + 1))}>"
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
