#!/usr/bin/env python3
"""Survey all .are files for mobs and their levels/stats."""
import re, os, sys

def parse_dice(s):
    """Parse NdM+B or NdM-B, return average."""
    m = re.match(r'(\d+)d(\d+)([+-]\d+)?', s)
    if not m:
        return 0
    n, d, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return n * (d + 1) / 2 + b

results = []
for fname in sorted(os.listdir('.')):
    if not fname.endswith('.are'):
        continue
    try:
        text = open(fname).read()
    except:
        continue

    # Grab MOBILES section
    m = re.search(r'#MOBILES\b(.*?)(?:\n#[A-Z])', text, re.DOTALL)
    if not m:
        continue
    mob_text = m.group(1)

    # Each mob starts with #VNUM
    for block in re.split(r'(?=\n#\d+\n)', '\n' + mob_text):
        vnum_m  = re.search(r'#(\d+)\n', block)
        name_m  = re.search(r'#\d+\n([^\n~]*)', block)
        stats_m = re.search(r'^(\d+)\s+(-?\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(-?\d+)', block, re.MULTILINE)
        if not all([vnum_m, name_m, stats_m]):
            continue
        lvl = int(stats_m.group(1))
        if lvl < 45:
            continue
        vnum  = int(vnum_m.group(1))
        name  = name_m.group(1).strip()[:35]
        hp    = int(parse_dice(stats_m.group(3)))
        dam   = int(parse_dice(stats_m.group(5)))
        ac_line = re.search(r'^(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)', block, re.MULTILINE)
        ac = int(ac_line.group(1)) if ac_line else 0
        results.append((lvl, vnum, fname, name, hp, dam, ac))

results.sort(key=lambda x: (-x[0], x[1]))
print(f"{'Lvl':>3}  {'Vnum':>6}  {'HP':>6}  {'AvDam':>5}  {'AC':>4}  {'File':<25}  Name")
print("-" * 95)
for lvl, vnum, fname, name, hp, dam, ac in results:
    print(f"{lvl:3d}  #{vnum:<6}  {hp:6d}  {dam:5d}  {ac:4d}  {fname:<25}  {name}")
