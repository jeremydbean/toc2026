import os, re

AREA_DIR = "area"
with open(f"{AREA_DIR}/area.lst") as f:
    LOADED = {l.strip() for l in f if l.strip() and l.strip() != '$'}

SECTION_RE = re.compile(r'^#(MOBILES|SHOPS|SPECIALS)\b', re.MULTILINE)

mob_vnums = set()

# First pass: collect all mob vnums from loaded areas
for fname in sorted(LOADED):
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path): continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    sp = [(m.start(), m.group(1)) for m in SECTION_RE.finditer(content)]
    for idx, (pos, stype) in enumerate(sp):
        if stype != 'MOBILES': continue
        end = sp[idx+1][0] if idx+1 < len(sp) else len(content)
        chunk = content[pos:end]
        for v in re.findall(r'^#(\d+)', chunk, re.MULTILINE):
            if int(v) > 0: mob_vnums.add(int(v))

# Second pass: check shops and specials
issues = []
for fname in sorted(LOADED):
    path = os.path.join(AREA_DIR, fname)
    if not os.path.exists(path): continue
    with open(path, encoding="latin-1") as f:
        content = f.read()
    sp = [(m.start(), m.group(1)) for m in SECTION_RE.finditer(content)]
    secs = {}
    for idx, (pos, stype) in enumerate(sp):
        end = sp[idx+1][0] if idx+1 < len(sp) else len(content)
        secs[stype] = content[pos:end]

    if 'SHOPS' in secs:
        for line in secs['SHOPS'].splitlines():
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('#'): continue
            parts = line.split()
            if parts and parts[0].isdigit():
                mob_v = int(parts[0])
                if mob_v > 0 and mob_v not in mob_vnums:
                    issues.append(f"{fname}: SHOPS keeper {mob_v} not defined")

    if 'SPECIALS' in secs:
        for line in secs['SPECIALS'].splitlines():
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('#'): continue
            parts = line.split()
            if len(parts) >= 2 and parts[0] == 'M' and parts[1].isdigit():
                mob_v = int(parts[1])
                spec = parts[2] if len(parts) > 2 else '?'
                if mob_v > 0 and mob_v not in mob_vnums:
                    issues.append(f"{fname}: SPECIALS mob {mob_v} ({spec}) not defined")

if issues:
    print(f"ISSUES ({len(issues)}):")
    for i in issues: print(f"  {i}")
else:
    print("All shop keepers and special mobs are defined.")
