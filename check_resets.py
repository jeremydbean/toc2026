import os, re

AREA_DIR = "area"
SKIP = {"korzath2old.are", "savedTrinidad.are"}

with open(f"{AREA_DIR}/area.lst") as f:
    LOADED = {l.strip() for l in f if l.strip() and l.strip() != '$'}

SECTION_RE = re.compile(r'^#(MOBILES|OBJECTS|ROOMS|RESETS|SHOPS|SPECIALS|HELPS|AREA|END)\b', re.MULTILINE)

def parse_sections_by_type(text):
    result = {}
    sp = [(m.start(), m.group(1)) for m in SECTION_RE.finditer(text)]
    for idx, (pos, stype) in enumerate(sp):
        end = sp[idx+1][0] if idx+1 < len(sp) else len(text)
        chunk = text[pos:end]
        if stype in ('MOBILES', 'OBJECTS', 'ROOMS', 'RESETS'):
            result[stype] = chunk
    return result

mob_vnums = set()
obj_vnums = set()
room_vnums = set()

for fname in LOADED:
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path):
        continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    secs = parse_sections_by_type(content)
    for v in re.findall(r'^#(\d+)', secs.get('MOBILES', ''), re.MULTILINE):
        if int(v) > 0: mob_vnums.add(int(v))
    for v in re.findall(r'^#(\d+)', secs.get('OBJECTS', ''), re.MULTILINE):
        if int(v) > 0: obj_vnums.add(int(v))
    for v in re.findall(r'^#(\d+)', secs.get('ROOMS', ''), re.MULTILINE):
        if int(v) > 0: room_vnums.add(int(v))

print(f"Loaded vnums -- MOB:{len(mob_vnums)} OBJ:{len(obj_vnums)} ROOM:{len(room_vnums)}")

broken = []
for fname in sorted(LOADED):
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path):
        continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    secs = parse_sections_by_type(content)
    resets_text = secs.get('RESETS', '')
    if not resets_text:
        continue
    for line in resets_text.splitlines():
        line = line.strip()
        if not line or line.startswith('*'):
            continue
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0].upper()
        try:
            if cmd == 'M' and len(parts) >= 5:
                mob_vn = int(parts[2])
                room_vn = int(parts[4])
                if mob_vn > 0 and mob_vn not in mob_vnums:
                    broken.append((fname, f"M reset: mob {mob_vn} not defined"))
                if room_vn > 0 and room_vn not in room_vnums:
                    broken.append((fname, f"M reset: room {room_vn} not defined"))
            elif cmd == 'O' and len(parts) >= 5:
                obj_vn = int(parts[2])
                room_vn = int(parts[4])
                if obj_vn > 0 and obj_vn not in obj_vnums:
                    broken.append((fname, f"O reset: obj {obj_vn} not defined (room {room_vn})"))
                if room_vn > 0 and room_vn not in room_vnums:
                    broken.append((fname, f"O reset: room {room_vn} not defined"))
            elif cmd == 'G' and len(parts) >= 3:
                obj_vn = int(parts[2])
                if obj_vn > 0 and obj_vn not in obj_vnums:
                    broken.append((fname, f"G reset: obj {obj_vn} not defined"))
            elif cmd == 'E' and len(parts) >= 4:
                obj_vn = int(parts[2])
                if obj_vn > 0 and obj_vn not in obj_vnums:
                    broken.append((fname, f"E reset: obj {obj_vn} not defined"))
            elif cmd == 'P' and len(parts) >= 5:
                obj_vn = int(parts[2])
                cont_vn = int(parts[4])
                if obj_vn > 0 and obj_vn not in obj_vnums:
                    broken.append((fname, f"P reset: obj {obj_vn} not defined"))
                if cont_vn > 0 and cont_vn not in obj_vnums:
                    broken.append((fname, f"P reset: container {cont_vn} not defined"))
        except (ValueError, IndexError):
            pass

if broken:
    print(f"\nBROKEN RESETS ({len(broken)}):")
    for area, msg in sorted(broken):
        print(f"  {area}: {msg}")
else:
    print("\nAll resets reference valid vnums.")
