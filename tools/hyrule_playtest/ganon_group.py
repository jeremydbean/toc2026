"""Play Ganon as a group (owner, 2026-10-04: "Ganon remains a group fight").

The guardian playtests (playtest.py) measure one character. Ganon is meant
for a buffed group, and the simulation that sized him overrated players by
2.5 times, so this plays the claim: N human warriors at the top of Death
Mountain's band, in the gear gear_plan.py chose for dungeon 9, skills at
75%, the hit points of a typical player of that level, each buffed by
Hermie (EMPOWER, TITANIC, the defence and combat groups, bless), grouped,
attacking together. The leader carries the Silver Arrow and shoots when
Ganon flashes red, as a player must.

Usage (repository root, WSL):
  python3 tools/hyrule_playtest/ganon_group.py <gear_plan.json> <out.json> [members=3] [tries=2]
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "webadmin"))
sys.path.insert(0, str(ROOT / "scripts"))

from live_mud import LiveMud, create_character, login, patch_player_file  # noqa: E402
from area_parser import AreaParser  # noqa: E402
import build_hyrule_area as gen  # noqa: E402

PLAN = json.loads(Path(sys.argv[1]).read_text())["9"]
OUT = Path(sys.argv[2])
MEMBERS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
TRIES = int(sys.argv[4]) if len(sys.argv) > 4 else 2
PW = "Zplaypass1"
NAMES = ["Zgana", "Zganb", "Zganc", "Zgand", "Zgane"][:MEMBERS]
GOD = "Zganon"
SILVER_ARROW = 30218

parser = AreaParser(ROOT / "area")
parser.parse_all()
MAN = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
boss_room = {d["level"]: d for d in MAN["dungeons"]}[9]["boss_vnum"]
L = PLAN["level"]
hp_max = int(8 + 10 * L + 0.3 * L * L)
mana = int(100 + 4 * L)
weapon_vnum = next((v for v in PLAN["vnums"] if parser.objects[v].item_type == "5"), None)


def note(text):
    print(f"[ganon x{MEMBERS}] {text}", flush=True)


def run(client, command, settle=1.0):
    client.drain(0.2)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def hp_of(text):
    found = re.findall(r"<(-?\d+)hp", text)
    return int(found[-1]) if found else None


def obj_keyword(vnum):
    o = parser.objects[vnum]
    words = (o.keywords or "").split()
    if words:
        return words[0]
    return [w for w in o.short_desc.lower().split()
            if w not in ("a", "an", "the", "pair", "of", "some")][-1]


def equip(god, hero, name, arrow):
    for vnum in PLAN["vnums"] + ([SILVER_ARROW] if arrow else []):
        proto = parser.objects[vnum].level
        olevel = proto if 0 < proto <= L else L
        run(god, f"load obj {vnum} {olevel}", 0.5)
        run(god, f"give {obj_keyword(vnum)} {name.lower()}", 0.5)
    run(hero, "wear all", 3.0)
    if weapon_vnum:
        run(hero, f"wield {obj_keyword(weapon_vnum)}", 1.0)


def fight(heroes, limit=600):
    """(won, survivors, seconds, hp_left per member)."""
    start = time.time()
    marks = [len(h.transcript) for h in heroes]
    for h in heroes:
        h.send("kill ganon")
    shot = False
    disarms = [0] * len(heroes)
    dead = [False] * len(heroes)
    while time.time() - start < limit:
        for h in heroes:
            h.drain(0.7)
        for i, h in enumerate(heroes):
            text = h.transcript[marks[i]:]
            if "You have been KILLED" in text:
                dead[i] = True
            if text.count("DISARMS") > disarms[i] and weapon_vnum:
                disarms[i] = text.count("DISARMS")
                kw = obj_keyword(weapon_vnum)
                h.send(f"get {kw}")
                h.send(f"wield {kw}")
            if "is DEAD!!" in text:
                return True, dead.count(False), time.time() - start, \
                    [hp_of(x.transcript[m:]) for x, m in zip(heroes, marks)]
        lead = heroes[0].transcript[marks[0]:]
        if not dead[0] and "flashes bright red" in lead:
            if not shot:
                heroes[0].send("wield arrow")
                heroes[0].drain(1.0)
                shot = True
            heroes[0].send("shoot ganon")
        if all(dead):
            return False, 0, time.time() - start, [0] * len(heroes)
        # A survivor who is not fighting (a member died, or the fight
        # dropped them) joins back in, as a player in a group would.
        for i, h in enumerate(heroes):
            tail = h.transcript[-400:]
            if not dead[i] and "Ganon" not in tail[-200:] and (time.time() - start) > 10:
                h.send("kill ganon")
    return None, dead.count(False), time.time() - start, \
        [hp_of(x.transcript[m:]) for x, m in zip(heroes, marks)]


results = {"members": MEMBERS, "level": L, "hp": hp_max, "fights": []}
with LiveMud(extra_env={"TOC_NO_BOOT_HERMIE": None}) as mud:
    for name in NAMES + [GOD]:
        with mud.connect(timeout=120) as c:
            create_character(c, name, PW)
            c.send("quit")
            c.wait_closed()
    for name in NAMES:
        patch_player_file(mud, name, Levl=L, Room=4207, Cla=3, Gui=3, Attr="18 13 13 17 17",
                          HMV=f"{hp_max} {hp_max} {mana} {mana} 300 300",
                          HMVP=f"{hp_max} {mana} 300")
    patch_player_file(mud, GOD, Levl=70, Room=4207)
    clients = [mud.connect(timeout=120) for _ in NAMES]
    with mud.connect(timeout=120) as god:
        heroes = [c.__enter__() for c in clients]
        for h, name in zip(heroes, NAMES):
            login(h, name, PW)
            run(h, "scroll 0")
        login(god, GOD, PW)
        run(god, "scroll 0")
        run(god, "holylight")
        for i, (h, name) in enumerate(zip(heroes, NAMES)):
            run(god, f"set skill {name.lower()} all 75", 1.0)
            equip(god, h, name, arrow=(i == 0))
        for name in NAMES[1:]:
            run(heroes[NAMES.index(name)], f"follow {NAMES[0].lower()}", 0.8)
            run(heroes[0], f"group {name.lower()}", 0.8)
        note(f"level {L}, {hp_max} hp each")

        for attempt in range(TRIES):
            run(god, f"goto {boss_room}", 1.0)
            for _ in range(6):
                if "aren't here" in run(god, "slay ganon", 0.8):
                    break
            run(god, f"load mob {gen.GANON_VNUM}", 1.0)
            run(god, "goto 4207", 0.8)
            for h, name in zip(heroes, NAMES):
                run(god, f"transfer {name.lower()} 4208", 1.0)
                run(god, f"restore {name.lower()}", 0.8)
                run(h, "stand", 0.5)
                run(h, "buff detects", 2.0)
                for b in ("empower", "titanic", "defense", "combat", "bless"):
                    run(h, f"buff {b}", 2.0)
            for h, name in zip(heroes, NAMES):
                run(god, f"restore {name.lower()}", 0.6)
                run(god, f"transfer {name.lower()} {boss_room}", 1.0)
            won, alive, secs, left = fight(heroes)
            result = dict(attempt=attempt + 1, won=won, survivors=alive,
                          secs=round(secs), hp_left=left)
            results["fights"].append(result)
            note(f"try {attempt + 1}: {'WON' if won else 'LOST' if won is False else 'n/a'}"
                 f", {alive} of {MEMBERS} standing, {secs:.0f}s, hp left {left}")
            if attempt + 1 < TRIES:
                # The dead lie in the dark in their corpses' gear: fresh copies.
                for i, (h, name) in enumerate(zip(heroes, NAMES)):
                    run(god, f"transfer {name.lower()} 4207", 1.0)
                    run(god, f"restore {name.lower()}", 0.8)
                    run(h, "stand", 0.5)
                    if won is not True:
                        equip(god, h, name, arrow=(i == 0))
                for name in NAMES[1:]:
                    run(heroes[NAMES.index(name)], f"follow {NAMES[0].lower()}", 0.8)
                    run(heroes[0], f"group {name.lower()}", 0.8)
        for h in heroes:
            h.send("quit")
        OUT.with_suffix(".hero.log").write_text(heroes[0].transcript)
OUT.write_text(json.dumps(results, indent=1))
note("done")
