"""Check all room exits in loaded areas for destinations that don't exist."""
import os, re

AREA_DIR = "area"
SKIP = {"korzath2old.are", "savedTrinidad.are"}

with open(f"{AREA_DIR}/area.lst") as f:
    LOADED = {l.strip() for l in f if l.strip() and l.strip() != '$'}

SECTION_RE = re.compile(r'^#(MOBILES|OBJECTS|ROOMS|RESETS|SHOPS|SPECIALS|HELPS|AREA|END)\b', re.MULTILINE)

def get_section(text, stype):
    sp = [(m.start(), m.group(1)) for m in SECTION_RE.finditer(text)]
    for idx, (pos, st) in enumerate(sp):
        if st == stype:
            end = sp[idx+1][0] if idx+1 < len(sp) else len(text)
            return text[pos:end]
    return ""

# First pass: collect all defined room vnums
room_vnums = set()
for fname in LOADED:
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path): continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    rooms_sec = get_section(content, "ROOMS")
    for v in re.findall(r'^#(\d+)', rooms_sec, re.MULTILINE):
        if int(v) > 0: room_vnums.add(int(v))

print(f"Total room vnums: {len(room_vnums)}")

# Second pass: check exits
# In a room block, exit doors look like:
# D<dir>
# <description>~
# <keyword>~
# <lock> <key_vnum> <to_room>
broken = []
for fname in sorted(LOADED):
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path): continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    rooms_sec = get_section(content, "ROOMS")
    if not rooms_sec: continue
    
    lines = rooms_sec.splitlines()
    current_room = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Room header
        m = re.match(r'^#(\d+)$', line)
        if m:
            current_room = int(m.group(1))
            i += 1
            continue
        # Exit direction marker
        if re.match(r'^D\d$', line):
            # Skip description (up to ~)
            i += 1
            while i < len(lines) and not lines[i].rstrip().endswith('~'):
                i += 1
            i += 1  # skip the ~ line
            # Skip keyword (up to ~)
            while i < len(lines) and not lines[i].rstrip().endswith('~'):
                i += 1
            i += 1  # skip ~ line
            # Skip blank lines
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                lock_parts = lines[i].strip().split()
                if len(lock_parts) >= 3:
                    try:
                        to_room = int(lock_parts[2])
                        if to_room > 0 and to_room not in room_vnums:
                            broken.append((fname, current_room, to_room))
                    except (ValueError, IndexError):
                        pass
            i += 1
            continue
        i += 1

if broken:
    print(f"\nBROKEN EXIT DESTINATIONS ({len(broken)}):")
    for area, room, dest in sorted(broken, key=lambda x: (x[0], x[1])):
        print(f"  {area}: room {room} -> {dest} (not defined)")
else:
    print("\nAll room exits point to valid destinations.")
