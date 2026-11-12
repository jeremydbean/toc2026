"""Check every reset in loaded areas names a mobile, object or room that
exists.

The world is read by webadmin/area_reader.py, token for token as
load_resets() reads it: a G or R reset takes two arguments, not three,
and anything after the last argument on the line is a comment.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository root
sys.path.insert(0, str(ROOT))

from webadmin.area_reader import read_world  # noqa: E402

AREA_DIR = ROOT / "area"

areas = read_world(AREA_DIR)
mob_vnums = {m.vnum for area in areas for m in area.mobiles}
obj_vnums = {o.vnum for area in areas for o in area.objects}
room_vnums = {r.vnum for area in areas for r in area.rooms}

print(f"Loaded vnums -- MOB:{len(mob_vnums)} OBJ:{len(obj_vnums)} ROOM:{len(room_vnums)}")

broken = []
for area in areas:
    fname = area.name
    for reset in area.resets:
        cmd = reset.command
        if cmd == 'M':
            if reset.arg1 > 0 and reset.arg1 not in mob_vnums:
                broken.append((fname, f"M reset: mob {reset.arg1} not defined"))
            if reset.arg3 > 0 and reset.arg3 not in room_vnums:
                broken.append((fname, f"M reset: room {reset.arg3} not defined"))
        elif cmd == 'O':
            if reset.arg1 > 0 and reset.arg1 not in obj_vnums:
                broken.append((fname, f"O reset: obj {reset.arg1} not defined (room {reset.arg3})"))
            if reset.arg3 > 0 and reset.arg3 not in room_vnums:
                broken.append((fname, f"O reset: room {reset.arg3} not defined"))
        elif cmd in ('G', 'E'):
            if reset.arg1 > 0 and reset.arg1 not in obj_vnums:
                broken.append((fname, f"{cmd} reset: obj {reset.arg1} not defined"))
        elif cmd == 'P':
            if reset.arg1 > 0 and reset.arg1 not in obj_vnums:
                broken.append((fname, f"P reset: obj {reset.arg1} not defined"))
            if reset.arg3 > 0 and reset.arg3 not in obj_vnums:
                broken.append((fname, f"P reset: container {reset.arg3} not defined"))

if broken:
    print(f"\nBROKEN RESETS ({len(broken)}):")
    for area, msg in sorted(broken):
        print(f"  {area}: {msg}")
else:
    print("\nAll resets reference valid vnums.")
