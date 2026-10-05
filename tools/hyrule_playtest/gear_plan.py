"""Gear for a Hyrule playtest character at each dungeon's top level.

Average world gear: the median of the Gear Finder's list for each slot,
Hyrule excluded. Hyrule gear collected before this dungeon: each earlier
guardian's weapon and Heart Guard, three of its drops (seeded random), and
the map-room chests of this dungeon and every earlier one. Each slot takes
whichever the Gear Finder scores higher. Run from the repository root with
the dashboard's dependencies (fastapi):
  python tools/hyrule_playtest/gear_plan.py warrior gear_plan.json
"""
import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, ".")
import webadmin.server as server  # noqa: E402
from scripts.build_hyrule_area import (BOSS_GEAR, BOSS_WEAPONS, GEAR_STAGES, boss_drop_vnum,  # noqa: E402
                                       boss_drops, manifest_bands)

MAN = json.loads(Path("data/hyrule_first_quest.json").read_text(encoding="utf-8"))
bands = manifest_bands(MAN)
p = server.load_area_parser(server.AREA_PATH)
server.parser = p
CLASS = sys.argv[1] if len(sys.argv) > 1 else "warrior"
weights = server.CLASS_WEIGHTS[CLASS]
rng = random.Random(4)


def hy(v):
    return 30000 <= v < 33000


def score(vnum):
    o = p.objects[vnum]
    it = int(o.item_type)
    slot = server._gear_natural_slot(o, it)
    if slot is None:
        return None, 0.0
    return slot, server.gear_item_score(o, it, slot, list(o.values), weights)[0]


collected = []
plan = {}
for level in range(1, 10):
    top = 59 if level == 9 else bands[level][1]
    if level > 1:
        prev = level - 1
        collected += [BOSS_WEAPONS[prev].vnum, BOSS_GEAR[prev]]
        pieces = list(range(len(boss_drops(prev))))
        collected += [boss_drop_vnum(prev, i) for i in rng.sample(pieces, 3)]
    for stage in range(0, level + 1):
        if stage in GEAR_STAGES:
            collected += list(GEAR_STAGES[stage][1])
    found = asyncio.run(server.get_best_gear(class_name=CLASS, race_name="human", level=top, limit=400))
    chosen = {}
    report = []
    used = set()
    for key, label in server.GEAR_FINDER_SLOTS:
        world = [i for i in found.get(label, []) if not hy(i["vnum"]) and i["vnum"] not in used]
        median = world[len(world) // 2] if world else None
        best_h = None
        for v in collected:
            if v in used or v not in p.objects or p.objects[v].level > top:
                continue
            slot, sc = score(v)
            if slot != key:
                continue
            if best_h is None or sc > best_h[1]:
                best_h = (v, sc)
        pick = None
        if median and (best_h is None or median["score"] >= best_h[1]):
            pick = (median["vnum"], median["score"], "world", median["name"])
        elif best_h:
            pick = (best_h[0], best_h[1], "hyrule", p.objects[best_h[0]].short_desc)
        if pick:
            used.add(pick[0])
            chosen[label] = pick[0]
            report.append(f"{label}: {pick[3]} ({pick[2]}, {pick[1]:.1f})")
    plan[level] = {"level": top, "vnums": list(chosen.values()), "report": report}
    print(level, top, len(chosen), "pieces;", sum(1 for r in report if "(hyrule" in r), "from Hyrule", flush=True)
Path(sys.argv[2] if len(sys.argv) > 2 else "gear_plan.json").write_text(json.dumps(plan, indent=1))
