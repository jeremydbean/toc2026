"""Check all room exits in loaded areas for destinations that don't exist.

The world is read by webadmin/area_reader.py, token for token as the game
reads it -- "D0" and "D 0" alike, and an exit whose description starts on
the same line as its number ("D3 too dark to tell"), which a line-shaped
reader here used to skip.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from webadmin.area_reader import read_world  # noqa: E402

AREA_DIR = Path("area")

areas = read_world(AREA_DIR)
room_vnums = {room.vnum for area in areas for room in area.rooms}

print(f"Total room vnums: {len(room_vnums)}")

broken = []
for area in areas:
    for room in area.rooms:
        for door in room.exits:
            if door.to_room > 0 and door.to_room not in room_vnums:
                broken.append((area.name, room.vnum, door.to_room))

if broken:
    print(f"\nBROKEN EXIT DESTINATIONS ({len(broken)}):")
    for area, room, dest in sorted(broken):
        print(f"  {area}: room {room} -> {dest} (not defined)")
else:
    print("\nAll room exits point to valid destinations.")
