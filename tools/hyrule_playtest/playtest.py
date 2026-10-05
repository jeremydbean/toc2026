"""Play one Hyrule dungeon's fights for real (owner, 2026-10-04).

A human warrior at the top of the dungeon's band, in the gear gear_plan.py
chose (average world gear, or what Hyrule had given by then where better),
skills at 75%, the hit points of a typical player of that level. Every
fight is in the dungeon's treasure room (dark, empty), from full health:

  A. Control: three ordinary world mobiles from the band's levels
     (world_controls.json), so "on par with the world" is measured, not
     assumed.
  B. Each kind of enemy that lives in this dungeon, once.
  C. The guardian, unbuffed, then after Hermie's buffs (EMPOWER, TITANIC,
     the defence and combat groups, bless).

Ganon is finished with the Silver Arrow when he collapses, as players must.
Usage (repository root, WSL):
  python3 tools/hyrule_playtest/playtest.py <dungeon 1-9> <gear_plan.json> <out.json> [guardians]
"guardians" skips the ordinary fights; "enemies" skips the guardian. world_controls.json beside this file, if
present, lists world mobiles to fight as a control: {"<dungeon>": [{"vnum", "keyword"}]}.
Each dungeon boots its own server, so the nine can run in parallel; see wiki/hyrule-area.md.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
SP = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "webadmin"))
sys.path.insert(0, str(ROOT / "scripts"))

from live_mud import LiveMud, create_character, login, patch_player_file  # noqa: E402
from area_parser import AreaParser  # noqa: E402
import build_hyrule_area as gen  # noqa: E402

LEVEL = int(sys.argv[1])
PLAN = json.loads(Path(sys.argv[2]).read_text())[str(LEVEL)]
OUT = Path(sys.argv[3])
_controls = SP / "world_controls.json"
CONTROLS = json.loads(_controls.read_text())[str(LEVEL)] if _controls.exists() else []
PW = "Zplaypass1"
HERO = "Zhero" + "abcdefghi"[LEVEL - 1] * 3
GOD = "Zgod" + "abcdefghi"[LEVEL - 1] * 3
SILVER_ARROW = 30218

parser = AreaParser(ROOT / "area")
parser.parse_all()
MAN = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
dungeon = {d["level"]: d for d in MAN["dungeons"]}[LEVEL]
boss_vnum = gen.BOSS_MOBS[LEVEL]
boss_room = dungeon["boss_vnum"]
arena = 29390 + LEVEL
GUARDIANS_ONLY = len(sys.argv) > 4 and sys.argv[4] == "guardians"
ENEMIES_ONLY = len(sys.argv) > 4 and sys.argv[4] == "enemies"
BOW, QUIVER = 30222, 30543
L = PLAN["level"]
hp_max = int(8 + 10 * L + 0.3 * L * L)
mana = int(100 + 4 * L)


def note(text):
    print(f"[L{LEVEL}] {text}", flush=True)


def run(client, command, settle=1.0):
    client.drain(0.2)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def hp_of(text):
    found = re.findall(r"<(-?\d+)hp", text)
    return int(found[-1]) if found else None


def mob_keyword(vnum):
    return parser.mobiles[vnum].keywords.split()[0]


def obj_keyword(vnum):
    o = parser.objects[vnum]
    words = (o.keywords or "").split()
    if words:
        return words[0]
    return [w for w in o.short_desc.lower().split() if w not in ("a", "an", "the", "pair", "of", "some")][-1]


def give(god, vnum):
    proto = parser.objects[vnum].level
    olevel = proto if 0 < proto <= L else L
    run(god, f"load obj {vnum} {olevel}", 0.6)
    run(god, f"give {obj_keyword(vnum)} {HERO.lower()}", 0.6)


def fight(hero, target, limit=240, ganon=False):
    """Fight until one of us dies: (won, hp_left, seconds); won is None if
    neither died in time or the target was not there."""
    start = time.time()
    mark = len(hero.transcript)
    hero.send(f"kill {target}")
    shot = False
    disarms = 0
    while time.time() - start < limit:
        hero.drain(2.0)
        text = hero.transcript[mark:]
        if text.count("DISARMS") > disarms and weapon_vnum:
            # As a player would: pick it up and wield it again.
            disarms = text.count("DISARMS")
            kw = obj_keyword(weapon_vnum)
            hero.send(f"get {kw}")
            hero.send(f"wield {kw}")
        if "You have been KILLED" in text:
            return False, 0, time.time() - start
        if "is DEAD!!" in text:
            return True, hp_of(text), time.time() - start
        if "only an arrow can finish" in text and not shot:
            hero.send("wield bow")
            hero.drain(1.0)
            shot = True
        if shot and "only an arrow can finish" in text and not ganon:
            hero.send(f"shoot {target}")
        if ganon and "flashes bright red" in text:
            if not shot:
                hero.send("wield arrow")
                hero.drain(1.0)
                shot = True
            hero.send("shoot ganon")
        if "aren't here" in text or "trying to kill" in text:
            return None, hp_of(text), time.time() - start
    return None, hp_of(hero.transcript[mark:]), time.time() - start


extras = ([SILVER_ARROW] if LEVEL == 9 else []) + ([BOW, QUIVER] if LEVEL == 6 else [])
light_vnum = next((v for v in PLAN["vnums"] if parser.objects[v].item_type == "1"), None)
weapon_vnum = next((v for v in PLAN["vnums"] if parser.objects[v].item_type == "5"), None)


def equip(hero, god):
    for vnum in PLAN["vnums"] + extras:
        give(god, vnum)
    run(hero, "wear all", 3.0)
    if weapon_vnum:
        run(hero, f"wield {obj_keyword(weapon_vnum)}", 1.0)


def recover(hero, god):
    """After a death: back at the temple, restored, in a fresh copy of the
    same gear (the old lies in a corpse in the dark)."""
    run(god, "goto 4207", 0.8)
    run(god, f"transfer {HERO.lower()} 4207", 1.2)
    run(god, f"restore {HERO.lower()}", 1.0)
    run(hero, "stand", 0.5)
    equip(hero, god)


def exactly_one(god, vnum, keyword):
    """Slay every copy in the room, then load one; a reset can have added
    a second guardian beside the one the last fight left."""
    long_desc = (parser.mobiles[vnum].long_desc or "").strip().splitlines()[0][:40]
    for _ in range(8):
        seen = run(god, "look", 1.0)
        if long_desc not in seen:
            break
        run(god, f"slay {keyword}", 0.8)
    run(god, f"load mob {vnum}", 1.0)
    seen = run(god, "look", 1.0)
    return seen.count(long_desc)


def one_fight(hero, god, vnum, label, keyword, limit=240):
    where = boss_room if label in ("unbuffed", "buffed") else arena
    run(god, f"goto {where}", 1.0)
    copies = exactly_one(god, vnum, keyword)
    if copies != 1:
        note(f"warning: {copies} copies of {keyword} in the room")
    run(god, f"restore {HERO.lower()}", 1.0)
    run(god, f"transfer {HERO.lower()} {where}", 1.2)
    run(god, "goto 4207", 0.8)
    mob = parser.mobiles.get(vnum)
    if label in ("unbuffed", "buffed"):
        run(hero, "look", 1.0)
    won, left, secs = fight(hero, keyword, limit=limit, ganon=(label != "world" and vnum == gen.GANON_VNUM))
    lost = None if left is None else round(100 * (hp_max - left) / hp_max)
    result = dict(kind=label, vnum=vnum, name=mob.short_desc if mob else "?",
                  mob_level=mob.level if mob else None, won=won, hp_left=left,
                  hp_lost_pct=lost, secs=round(secs))
    note(f"{label:8} {result['name'][:28]:28} L{result['mob_level']}: "
         f"{'WON ' if won else 'LOST' if won is False else 'n/a '} lost {lost}% hp, {secs:.0f}s")
    if won is False:
        recover(hero, god)
    elif won is None:
        run(god, f"goto {arena}", 0.8)
        run(god, "purge", 0.8)
        run(god, "goto 4207", 0.8)
    return result


results = {"level": LEVEL, "char_level": L, "fights": []}
with LiveMud(extra_env={"TOC_NO_BOOT_HERMIE": None}) as mud:
    for name in (HERO, GOD):
        with mud.connect(timeout=120) as c:
            create_character(c, name, PW)
            c.send("quit")
            c.wait_closed()
    patch_player_file(mud, HERO, Levl=L, Room=4207, Cla=3, Gui=3, Attr="18 13 13 17 17",
                      HMV=f"{hp_max} {hp_max} {mana} {mana} 300 300", HMVP=f"{hp_max} {mana} 300")
    patch_player_file(mud, GOD, Levl=70, Room=4207)
    with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
        login(hero, HERO, PW)
        login(god, GOD, PW)
        for c in (hero, god):
            run(c, "scroll 0")
        run(god, "holylight")
        run(god, f"set skill {HERO.lower()} all 75", 1.0)
        equip(hero, god)
        run(god, f"set char {HERO.lower()} gold 500", 0.8)
        run(god, f"goto {arena}", 1.0)
        run(god, "goto 4207", 0.8)
        score = run(hero, "score", 1.5)
        results["score"] = score[-1600:]
        hit = re.search(r"To Hit Bonus:\s+(-?\d+)", score)
        dam = re.search(r"To Damage Bonus:\s+(-?\d+)", score)
        note(f"level {L}, {hp_max} hp, hit {hit.group(1) if hit else '?'} dam {dam.group(1) if dam else '?'}")
        run(god, f"goto {arena}", 1.0)
        run(god, "purge", 1.0)
        run(god, "goto 4207", 0.8)

        # PLAYTEST_ONLY=<vnum,vnum>: just those Hyrule kinds, no controls.
        only = [int(x) for x in os.environ.get("PLAYTEST_ONLY", "").split(",") if x.strip()]
        # PLAYTEST_CONTROL=<vnum>: just that world control. A death skews
        # every fight after it in the same run, so a clean comparison gives
        # each fight a fresh server (tools/hyrule_playtest/one_each.sh).
        control = os.environ.get("PLAYTEST_CONTROL", "").strip()
        if control:
            only = only or [-1]
        for c in ([c for c in CONTROLS if str(c["vnum"]) == control] if control
                  else [] if GUARDIANS_ONLY or only else CONTROLS):
            results["fights"].append(one_fight(hero, god, c["vnum"], "world", c["keyword"]))
        kinds = sorted({r.arg1 for resets in parser.resets.values() for r in resets
                        if r.command == "M"
                        and dungeon["first_room_vnum"] <= r.arg3 <= dungeon["last_room_vnum"]
                        and gen.TIER_VNUM_FIRST <= r.arg1 <= gen.TIER_VNUM_LAST})
        for vnum in ([] if GUARDIANS_ONLY else [v for v in (only or kinds) if v > 0]):
            results["fights"].append(one_fight(hero, god, vnum, "hyrule", mob_keyword(vnum)))

        for label in (() if ENEMIES_ONLY else ("unbuffed", "buffed", "buffed")):
            run(god, f"goto {boss_room}", 1.0)
            for _ in range(4):
                if "aren't here" in run(god, f"slay {mob_keyword(boss_vnum)}", 0.8):
                    break
            run(god, "goto 4207", 0.8)
            run(god, f"restore {HERO.lower()}", 1.0)
            run(god, f"transfer {HERO.lower()} 4208", 1.2)
            run(hero, "buff detects", 2.0)
            if label == "buffed":
                run(god, f"transfer {HERO.lower()} 4208", 1.5)
                for b in ("empower", "titanic", "defense", "combat", "bless"):
                    run(hero, f"buff {b}", 2.0)
                run(god, f"restore {HERO.lower()}", 1.0)
            results["fights"].append(one_fight(hero, god, boss_vnum, label, mob_keyword(boss_vnum),
                                               limit=480 if LEVEL == 9 else 360))
        hero.send("quit")
        OUT.with_suffix(".hero.log").write_text(hero.transcript)
OUT.write_text(json.dumps(results, indent=1))
note("done")
