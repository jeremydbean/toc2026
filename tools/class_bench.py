#!/usr/bin/env python3
"""Measure the 18 builds in the real engine, in the training yard.

Every character here is a synthetic, mortal, Z-named fixture made in a
disposable world (tests/live_mud.py copies area/ and starts with an empty
player/); nothing touches a real player file. Run from the repository
root:

    python3 tools/class_bench.py --levels 10,25,40,50 --modes auto,self \\
        --profiles core,full --rounds 12 --workers 4 --out bench.json
    python3 tools/class_bench.py --report bench.json

How a fixture is made, so two builds differ only in what they are:

* created, its creation skills and groups stripped, then given its class,
  guild, race human and fixed stats; logged in, so the loader hands it its
  class's and guild's groups; then ADVANCEd by staff from 1 to the level,
  so its hit points, mana and moves come from the game's own advance_level
  rolls;
* skills: "core" is only what the class and guild are given, at 75%;
  "full" is everything the build can learn by the game's GAIN rules
  (tools/class_balance.py), at 100%, with the prime stat raised -- an
  optimised legal build, whatever its trains would really have bought
  (the train cost is reported beside it);
* gear: the same for everyone at a level -- one level-appropriate weapon
  of the class's own kind (none for a monk), and a ring whose affects give
  hitroll and damroll of a third of the level and armour of three times
  it. Equal budgets, not the best kit in the world.

Modes: "auto" is plain melee, nothing typed after KILL. "self" casts the
build's own preparation buffs, then opens with its best opener and keeps
using its best attack until the bell. "hermie" is "self" after Hermie's
EMPOWER, TITANIC, defense and combat groups -- the ordinary buffed fight
AGENTS.md describes.

The yard counts only the player's own blows: a necromancer's servants and
a pet are not in its report (see the necro notes the report prints).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import class_balance as cb  # noqa: E402

PW = "Zbenchpw1"
TEMPLE, ALTAR, YARD = 4207, 4208, 2419
RING = 606
WEAPONS = {  # class -> (school vnum, weapon class value[0], attack value[3])
    0: (3701, 2, 11), 1: (3700, 4, 7), 2: (3701, 2, 11), 3: (3702, 1, 3), 5: (3701, 2, 11),
}
PRIME = {0: 1, 1: 2, 2: 3, 3: 0, 4: 4, 5: 1}  # STR INT WIS DEX CON index
ANSI = re.compile(r"\x1b\[[0-9;]*m")
PROMPT = re.compile(r"<(-?\d+)hp (-?\d+)m (-?\d+)mv>")

# Best single-target damage first. Only what a build holds and can cast at
# its level is used; area spells are fine against the lone dummy.
# Demonfire is left out: it turns on a caster who is not evil, and the
# fixtures are neutral.
SPELL_ORDER = ("meteor swarm", "tentacles", "acid blast", "chain lightning",
               "lightning bolt", "flamestrike", "fireball", "harm",
               "cone of cold", "force sword", "energy drain", "moonbeam", "icicle",
               "colour spray", "vampiric touch", "dust devil",
               "shocking grasp", "cause critical", "skeletal hands",
               "burning hands", "cause serious", "chill touch",
               "magic missile", "cause light")
SELF_BUFFS = ("sanctuary", "stone skin", "haste", "giant strength", "frenzy",
              "bless", "armor", "shield")


def letters(n: int) -> str:
    return "".join("abcdefghij"[int(d)] for d in str(n))


def fixture_name(cls: int, guild: int, level: int, tag: str) -> str:
    # Alphabetic, 12 letters at most, unique per run.
    return ("Zb" + "mctwkn"[cls] + "mctwkn"[guild] + letters(level) + tag)[:12].capitalize()


def weapon_dice(level: int) -> tuple:
    avg = level // 2 + 4                     # a fair weapon for the level
    num = 2 + level // 10
    size = max(2, (2 * avg) // num - 1)
    return num, size


def objects_for(cls: int, level: int) -> str:
    gear = (f"#O\nVnum {RING}\nNest 0\nWear 1\nLev 1\nCond 100\n"
            f"Aff -1 {level} -1 {max(1, level // 3)} 18 0 0\n"
            f"Aff -1 {level} -1 {max(1, level // 3)} 19 0 0\n"
            f"Aff -1 {level} -1 {-3 * level} 17 0 0\nEnd\n\n")
    if cls in WEAPONS:
        vnum, wclass, attack = WEAPONS[cls]
        num, size = weapon_dice(level)
        gear += (f"#O\nVnum {vnum}\nNest 0\nWear 16\nLev {min(level, 50)}\nCond 100\n"
                 f"Val  {wclass} {num} {size} {attack} 0\nEnd\n\n")
    return gear


def strip_and_patch(path: Path, fields: dict, skills: dict | None, objects: str | None) -> None:
    lines = path.read_text(encoding="latin-1").split("\n")
    out, in_obj = [], False
    for line in lines:
        if line == "#O":
            in_obj = True
            continue
        if in_obj:
            if line == "End":
                in_obj = False
            continue
        key = line.split(" ")[0]
        if key in fields:
            continue
        if skills is not None and key in ("Sk", "Gr"):
            continue
        out.append(line)
    text = "\n".join(out)
    end = text.index("\nEnd\n")
    extra = "".join(f"\n{k} {v}" for k, v in fields.items())
    if skills:
        extra += "".join(f"\nSk {pct} '{name}'" for name, pct in sorted(skills.items()))
    text = text[:end] + extra + text[end:]
    if objects:
        text = text.replace("#END", objects + "#END", 1)
    path.write_text(text, encoding="latin-1")


def parse_report(text: str) -> dict:
    text = ANSI.sub("", text)
    start = text.rfind("[ Training report ]")
    if start < 0:
        return {}
    rep = text[start:]
    out = {}
    m = re.search(r"WHAT YOU DID\s*\|\s*total (\d+)", rep)
    out["dealt"] = int(m.group(1)) if m else 0
    m = re.search(r"per round (\d+) over (\d+) rounds", rep)
    if m:
        out["per_round"], out["rounds"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"landed (\d+) of (\d+)", rep)
    if m:
        out["landed"], out["swings"] = int(m.group(1)), int(m.group(2))
    them = rep[rep.find("WHAT IT DID TO YOU"):]
    m = re.search(r"total (\d+)", them)
    out["taken"] = int(m.group(1)) if m else 0
    m = re.search(r"you stopped (\d+) of them", them)
    out["stopped"] = int(m.group(1)) if m else 0
    attacks = {}
    you = rep[:rep.find("WHAT IT DID TO YOU")]
    for name, dmg, landed, tried in re.findall(
            r"\|\s{3}([a-z][a-z' ]+?)\s{2,}(\d+)\s+\d+%\s+(\d+) of (\d+)", you):
        attacks[name.strip()] = {"damage": int(dmg), "landed": int(landed), "tried": int(tried)}
    out["attacks"] = attacks
    return out


def plan_skills(t: dict, cls: int, guild: int, level: int, profile: str) -> dict:
    held = cb.learnable(t, cls, guild)
    pct = 100 if profile == "full" else 75
    out = {}
    for name, (opens, how) in held.items():
        if profile == "core" and how != "given":
            continue
        out[name] = pct if opens <= level else 1
    return out


def train_cost(t: dict, cls: int, guild: int, level: int) -> int:
    """What buying everything the full profile holds would cost in trains,
    group by group as GAIN charges it."""
    cost, seen = 0, set()
    for name, (opens, how) in cb.learnable(t, cls, guild).items():
        if opens > level or how == "given":
            continue
        if how.startswith("group "):
            g = how[6:]
            if g not in seen:
                seen.add(g)
                cost += t["groups"][g.lower()]["ratings"][cls]
        else:
            cost += t["skills"][name]["ratings"][cls]
    return cost


# Rough average damage a cast at a level, from src/magic*.c, so a build
# casts what is best for it at that level; anything not named keeps its
# place in SPELL_ORDER below these.
SPELL_ESTIMATE = {
    "meteor swarm": lambda lv: 16 * lv, "tentacles": lambda lv: 495,
    "acid blast": lambda lv: 6.5 * lv, "chain lightning": lambda lv: 3.5 * lv,
    "lightning bolt": lambda lv: 5.5 * min(lv, 59), "flamestrike": lambda lv: 5 * min(lv, 59),
    # (a caster of another class rolls half: spell_rank halves these)
    "fireball": lambda lv: 2.5 * lv, "harm": lambda lv: 85,
}


OWN_SPELL = {"lightning bolt": 0, "flamestrike": 1}


def spell_rank(level: int, cls: int = -1) -> list:
    def est(s):
        v = SPELL_ESTIMATE[s](level)
        return v / 2 if s in OWN_SPELL and OWN_SPELL[s] != cls else v
    known = sorted((s for s in SPELL_ORDER if s in SPELL_ESTIMATE), key=lambda s: -est(s))
    return known + [s for s in SPELL_ORDER if s not in SPELL_ESTIMATE]


def choose_attack(held: dict, level: int, mana: int, t: dict, cls: int) -> str | None:
    usable = {s for s, pct in held.items() if pct > 1}
    for spell in spell_rank(level, cls):
        if spell in usable and t["skills"][spell]["spell"]:
            if mana >= t["skills"][spell]["mana"] * 2:
                return f"cast '{spell}'"
    for skill, cmd in (("fists of fury", "fists"), ("smite", "smite"),
                       ("nerve damage", "nerve"), ("bash", "bash"),
                       ("kick", "kick"), ("trip", "trip")):
        if skill in usable:
            return cmd
    return None


def opener(held: dict) -> str:
    usable = {s for s, pct in held.items() if pct > 1}
    if "crane dance" in usable:
        return "crane"
    if "backstab" in usable:
        return "backstab dummy"
    if "smite" in usable:
        return "smite dummy"
    return "kill dummy"


def run_job(mud, staff, t: dict, job: dict) -> dict:
    from live_mud import create_character, login
    cls, guild, level, profile, mode = (job["cls"], job["guild"], job["level"],
                                        job["profile"], job["mode"])
    name = job["name"]
    with mud.connect(timeout=120) as c:
        create_character(c, name, PW)
        c.send("quit")
        c.wait_closed()
    attr = [18, 18, 18, 18, 18]
    if profile == "full":
        attr[PRIME[cls]] = 23
    path = mud.player_dir / name
    strip_and_patch(path, {"Cla": cls, "Gui": guild, "Race": "human~", "Levl": 1,
                           "Attr": " ".join(map(str, attr)), "Room": TEMPLE, "Alig": 0},
                    skills={}, objects=None)
    with mud.connect(timeout=120) as c:
        login(c, name, PW)
        said = staff.sync(f"advance {name.lower()} {level}", 60)
        if "level" not in said.lower():
            raise RuntimeError(f"advance failed: {said[-300:]}")
        c.sync("save")
        c.send("quit")
        c.wait_closed()
    held = plan_skills(t, cls, guild, level, profile)
    strip_and_patch(path, {}, skills=held, objects=objects_for(cls, level))
    result = {**job, "trains": train_cost(t, cls, guild, level) if profile == "full" else 0}
    with mud.connect(timeout=120) as c:
        login(c, name, PW)
        c.sync("scroll 0")
        stat = ANSI.sub("", staff.sync(f"stat char {name.lower()}", 30))
        m = re.search(r"Hp: (\d+)/(\d+)\s+Mana: (\d+)/(\d+)\s+End: (\d+)/(\d+)", stat)
        if m:
            result.update(hp=int(m.group(2)), mana=int(m.group(4)), move=int(m.group(6)))
        m = re.search(r"Hit: (-?\d+)\s+Dam: (-?\d+)", stat)
        if m:
            result.update(hitroll=int(m.group(1)), damroll=int(m.group(2)))
        if mode == "hermie":
            staff.must(f"transfer {name.lower()} {ALTAR}", "")
            for ask in ("empower", "titanic", "defense", "combat"):
                c.sync(f"buff {ask}", 30)
        staff.must(f"restore {name.lower()}", "")
        staff.must(f"transfer {name.lower()} {YARD}", "")
        if mode in ("self", "hermie"):
            usable = {s for s, pct in held.items() if pct > 1}
            for buff in SELF_BUFFS:
                if buff in usable and t["skills"][buff]["spell"]:
                    c.sync(f"cast '{buff}'", 30)
            if "steel fist" in usable:
                c.sync("steel", 30)
            staff.must(f"restore {name.lower()}", "")
        if mode == "hermie":
            stat = ANSI.sub("", staff.sync(f"stat char {name.lower()}", 30))
            m = re.search(r"Hp: (\d+)/(\d+)", stat)
            if m:
                result["hp_buffed"] = int(m.group(2))
        c.sync(f"dummy rounds {job['rounds']}", 20)
        mark = len(c.transcript)
        start_mana = None
        first = opener(held) if mode != "auto" else "kill dummy"
        c.sync(first, 30)
        used = []
        deadline = time.monotonic() + job["rounds"] * 3.2 + 60
        while "The bell goes" not in c.transcript[mark:] and time.monotonic() < deadline:
            prompts = PROMPT.findall(c.transcript[mark:])
            mana = int(prompts[-1][1]) if prompts else 0
            if start_mana is None and prompts:
                start_mana = int(prompts[0][1])
            cmd = choose_attack(held, level, mana, t, cls) if mode != "auto" else None
            if cmd is None:
                c.drain(1.5)
            else:
                used.append(cmd)
                c.sync(cmd, 30)
        c.drain(3)
        body = c.transcript[mark:]
        result.update(parse_report(body))
        prompts = [tuple(map(int, p)) for p in PROMPT.findall(body)]
        if prompts:
            result["mana_low"] = min(p[1] for p in prompts)
            result["mana_start"] = start_mana if start_mana is not None else prompts[0][1]
        result["opener"] = first
        result["commands"] = sorted(set(used))
        c.send("quit")
        c.wait_closed()
    return result


def worker(args):
    jobs, binary, results_path = args
    from live_mud import LiveMud, create_character, login, patch_player_file
    t = cb.load_tables()
    if binary:
        os.environ["TOC_SERVER_BINARY"] = binary
    env = {"TOC_NO_BOOT_HERMIE": None}
    done = []
    with LiveMud(extra_env=env) as mud:
        with mud.connect(timeout=120) as staff:
            create_character(staff, "Zbenchstaff", PW)
            staff.send("quit")
            staff.wait_closed()
        patch_player_file(mud, "Zbenchstaff", Levl=70, Room=TEMPLE)
        with mud.connect(timeout=120) as staff:
            login(staff, "Zbenchstaff", PW)
            staff.sync("scroll 0")
            for job in jobs:
                try:
                    r = run_job(mud, staff, t, job)
                except Exception as exc:  # one bad run must not lose the rest
                    r = {**job, "error": f"{type(exc).__name__}: {exc}"[:300]}
                done.append(r)
                with open(results_path, "a") as fh:
                    fh.write(json.dumps(r) + "\n")
    return done


def make_jobs(levels, modes, profiles, rounds, only) -> list:
    jobs = []
    for cls, guild in cb.builds():
        bname = cb.build_name(cls, guild)
        if only and bname not in only:
            continue
        for level in levels:
            for profile in profiles:
                for mode in modes:
                    tag = {"auto": "a", "self": "s", "hermie": "h"}[mode] + profile[0]
                    jobs.append({"build": bname, "cls": cls, "guild": guild, "level": level,
                                 "profile": profile, "mode": mode, "rounds": rounds,
                                 "name": fixture_name(cls, guild, level, tag)})
    return jobs


def report(path: Path) -> None:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    keyf = lambda r: (r["profile"], r["mode"], r["level"], -r.get("per_round", 0))
    for r in sorted(rows, key=keyf):
        if "error" in r:
            print(f"{r['profile']:<4} {r['mode']:<6} L{r['level']:<2} {r['build']:<6} ERROR {r['error']}")
            continue
        print(f"{r['profile']:<4} {r['mode']:<6} L{r['level']:<2} {r['build']:<6} "
              f"dmg/rd {r.get('per_round', 0):>5}  taken {r.get('taken', 0):>6}  "
              f"hp {r.get('hp_buffed', r.get('hp', 0)):>6} mana {r.get('mana', 0):>5} "
              f"used {max(0, r.get('mana_start', 0) - r.get('mana_low', 0)):>5}  "
              f"hit {r.get('landed', 0)}/{r.get('swings', 0)}  trains {r.get('trains', 0):>3}  "
              f"open {r.get('opener', '')}  top {next(iter(sorted(r.get('attacks', {}).items(), key=lambda kv: -kv[1]['damage'])), ('', {}))[0]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--levels", default="10,25,40,50")
    ap.add_argument("--modes", default="auto,self")
    ap.add_argument("--profiles", default="core,full")
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--builds", help="comma list, e.g. W/W,Monk")
    ap.add_argument("--binary", help="a merc to measure instead of the repository's")
    ap.add_argument("--out", type=Path, default=Path("class-bench.jsonl"))
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    if args.report:
        report(args.report)
        return 0
    jobs = make_jobs([int(x) for x in args.levels.split(",")], args.modes.split(","),
                     args.profiles.split(","), args.rounds,
                     set(args.builds.split(",")) if args.builds else None)
    shards = [jobs[i::args.workers] for i in range(args.workers)]
    args.out.write_text("")
    with multiprocessing.Pool(args.workers) as pool:
        pool.map(worker, [(s, args.binary, str(args.out)) for s in shards if s])
    report(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
