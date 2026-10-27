#!/usr/bin/env python3
"""What each of the 18 builds can learn, and when -- read from the game's
own tables (src/const.c), with GAIN's rules (src/abilities.c).

A build is a class and a guild: the four ordinary classes (mage, cleric,
thief, warrior) may each join the mage, cleric, thief or warrior guild;
monks and necromancers have their own paths. That is 4 x 4 + 2 = 18.

What a build holds: its class's basics and default groups and its guild's
group, which every member is given, and what a trainer serving that class
and guild will sell -- a group rated above 0 for the class, or a single
skill (never a spell) rated above 0. A skill opens at the class's column
of skill_table's levels, whatever the guild.

    python3 tools/class_balance.py milestones          # every build
    python3 tools/class_balance.py milestones --build W/C
    python3 tools/class_balance.py gaps                # long dry spells
    python3 tools/class_balance.py --json milestones

This is a model of the tables, not a measurement: it says what is
available at a level, not how strong it is. tools/class_bench.py
measures builds in the real engine.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLASSES = ("mage", "cleric", "thief", "warrior", "monk", "necromancer")
LETTER = {0: "M", 1: "C", 2: "T", 3: "W"}
CLASS_ANY, CLASS_OTHER = -1, 6
GUILD_ANY = -1
GUILD_GROUP = {0: "mage guild", 1: "cleric guild", 2: "thief guild", 3: "warrior guild"}
MORTAL_MAX = 59

# The abilities that decide a fight, by what they do. Everything else a
# build holds is listed too, but these are what milestones and gaps track.
ATTACKS = ("second attack", "third attack", "enhanced damage", "dual wield",
           "hand to hand", "haste")
DEFENCES = ("dodge", "parry", "shield block", "iron skin",
            "sanctuary", "stone skin", "armor", "shield", "fast healing")
SIGNATURES = ("backstab", "fatality", "smite", "destruction",
              "berserk", "bash", "kick", "trip", "dirt kicking", "disarm",
              "fists of fury", "steel fist", "crane dance", "nerve damage",
              "blinding fists", "stunning blow", "rescue", "archery")
DAMAGE_SPELLS = ("magic missile", "chill touch", "burning hands",
                 "shocking grasp", "lightning bolt", "colour spray", "fireball",
                 "acid blast", "chain lightning", "meteor swarm", "energy drain",
                 "cause light", "cause serious", "cause critical", "harm",
                 "flamestrike", "earthquake", "dispel evil", "dispel good",
                 "demonfire", "call lightning", "tentacles", "heat metal",
                 "vortex", "animate parts", "cone of cold", "icicle", "moonbeam",
                 "dust devil", "force sword", "water burst", "geyser", "sunray",
                 "holy word", "spiritual hammer", "blizzard", "skeletal hands",
                 "vampiric touch", "shock sphere", "power gloves")
HEALING = ("cure light", "cure serious", "cure critical", "heal", "mass healing",
           "divine intervention", "refresh")
SERVANTS = ("create skeleton", "create wraith", "create vampire")
TRACKED = ATTACKS + DEFENCES + SIGNATURES + DAMAGE_SPELLS + HEALING + SERVANTS


def _section(src: str, marker: str) -> str:
    start = src.index(marker)
    return src[start:src.index("\n};", start)]


def load_tables() -> dict:
    src = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    # Comments sit between an entry's brace and its name in places
    # ("necro maladictions"); the tables are read without them.
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)

    skills = {}
    table = _section(src, "skill_table     [MAX_SKILL]")
    for m in re.finditer(
            r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\},\s*(\w+),\s*(\w+)\s*,\s*(\w+),'
            r'\s*([^,]+),\s*SLOT\(\s*-?\d+\),\s*(-?\d+),\s*(-?\d+)', table):
        skills[m.group(1)] = {
            "levels": [int(x) for x in re.findall(r"-?\d+", m.group(2))],
            "ratings": [int(x) for x in re.findall(r"-?\d+", m.group(3))],
            "spell": m.group(4) != "spell_null",
            "target": m.group(5),
            "mana": int(m.group(8)),
            "beats": int(m.group(9)),
        }

    groups = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\}',
                         _section(src, "group_table     [MAX_GROUP]")):
        groups[m.group(1).lower()] = {
            "ratings": [int(x) for x in re.findall(r"-?\d+", m.group(2))],
            "members": re.findall(r'"([^"]+)"', m.group(3)),
        }

    trainers = []
    gm = _section(src, "guildmaster_table       []  =")
    for m in re.finditer(r'\{\s*(?:/\*[^*]*\*/\s*)?(\d+),\s*(CLASS_\w+),\s*(GUILD_\w+),'
                         r'\s*\{(.*?)\},\s*\{(.*?)\},?\s*\}', gm, re.S):
        trainers.append({
            "vnum": int(m.group(1)),
            "class": _class_const(m.group(2)),
            "guild": _guild_const(m.group(3)),
            "gains": re.findall(r'"([^"]+)"', re.sub(r"/\*.*?\*/", "", m.group(5), flags=re.S)),
        })

    classes = []
    for m in re.finditer(r'\{\s*"(\w+)",\s*"[^"]*",\s*STAT_\w+,\s*\w+,\s*\{[^}]*\},'
                         r'\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*(\d+),\s*(\d+),\s*(\w+),'
                         r'\s*\{[^}]*\},\s*"([^"]+)",\s*"([^"]+)"',
                         _section(src, "class_table     [MAX_CLASS]")):
        classes.append({"name": m.group(1), "adept": int(m.group(2)),
                        "thac0_00": int(m.group(3)), "thac0_32": int(m.group(4)),
                        "hp_min": int(m.group(5)), "hp_max": int(m.group(6)),
                        "mana": m.group(7) == "true",
                        "basics": m.group(8), "default": m.group(9)})
    return {"skills": skills, "groups": groups, "trainers": trainers, "classes": classes}


def _class_const(name: str) -> int:
    return {"CLASS_ANY": -1, "CLASS_MAGE": 0, "CLASS_CLERIC": 1, "CLASS_THIEF": 2,
            "CLASS_WARRIOR": 3, "CLASS_MONK": 4, "CLASS_NECRO": 5, "CLASS_OTHER": 6}[name]


def _guild_const(name: str) -> int:
    return {"GUILD_ANY": -1, "GUILD_MAGE": 0, "GUILD_CLERIC": 1, "GUILD_THIEF": 2,
            "GUILD_WARRIOR": 3, "GUILD_MONK": 4, "GUILD_NECRO": 5}[name]


def skill_lookup(t: dict, name: str) -> str | None:
    """skill_lookup (src/magic.c): the first skill, in table order, that
    the name begins, without case."""
    name = name.lower()
    return next((s for s in t["skills"] if s.lower().startswith(name)), None)


def group_lookup(t: dict, name: str) -> str | None:
    """group_lookup (src/skills.c): the first group the name begins.
    Trainers rely on it -- the Archmage sells "mage transport"."""
    name = name.lower()
    return next((g for g in t["groups"] if g.startswith(name)), None)


def group_skills(t: dict, name: str, seen: set | None = None) -> set:
    """Every skill a group gives, through nested groups. A member is a
    skill first and a group only otherwise, as group_add reads it; group
    names are matched without case, as group_lookup does ("Necro default")."""
    name = name.lower()
    seen = set() if seen is None else seen
    if name in seen or name not in t["groups"]:
        return set()
    seen.add(name)
    out = set()
    for member in t["groups"][name]["members"]:
        skill = skill_lookup(t, member)
        if skill:
            out.add(skill)
        elif group_lookup(t, member):
            out |= group_skills(t, group_lookup(t, member), seen)
    return out


def builds() -> list:
    out = [(c, g) for c in range(4) for g in range(4)]
    return out + [(4, 4), (5, 5)]


def build_name(cls: int, guild: int) -> str:
    if cls == 4:
        return "Monk"
    if cls == 5:
        return "Necro"
    return f"{LETTER[cls]}/{LETTER[guild]}"


def serves(trainer: dict, cls: int, guild: int) -> bool:
    """do_gain's gm_serves (src/abilities.c)."""
    if trainer["class"] == CLASS_OTHER and cls == trainer["guild"]:
        return False
    if trainer["class"] not in (CLASS_ANY, CLASS_OTHER) and cls != trainer["class"]:
        return False
    if trainer["guild"] != GUILD_ANY and guild != trainer["guild"]:
        return False
    return True


def learnable(t: dict, cls: int, guild: int) -> dict:
    """skill -> (level it opens, how it is had: 'given', a group, or 'single')."""
    out = {}
    c = t["classes"][cls]
    given = (group_skills(t, "rom basics") | group_skills(t, c["basics"])
             | group_skills(t, c["default"]))
    if guild in GUILD_GROUP:
        given |= group_skills(t, GUILD_GROUP[guild])
    for s in given:
        out[s] = "given"
    for trainer in t["trainers"]:
        if not serves(trainer, cls, guild):
            continue
        for item in trainer["gains"]:
            # do_gain: a group first (never group 0, rom basics), then a skill.
            group = group_lookup(t, item)
            if group and group != "rom basics":
                if t["groups"][group]["ratings"][cls] <= 0:
                    continue
                for s in group_skills(t, group):
                    out.setdefault(s, f"group {group}")
                continue
            skill = skill_lookup(t, item)
            if skill:
                sk = t["skills"][skill]
                if not sk["spell"] and sk["ratings"][cls] > 0:
                    out.setdefault(skill, "single")
    result = {}
    for s, how in out.items():
        level = t["skills"][s]["levels"][cls]
        if 0 < level <= MORTAL_MAX:
            result[s] = (level, how)
    return result


def milestones(t: dict, only: str | None) -> list:
    rows = []
    for cls, guild in builds():
        name = build_name(cls, guild)
        if only and name.lower() != only.lower():
            continue
        held = learnable(t, cls, guild)
        tracked = sorted(((lvl, s, how) for s, (lvl, how) in held.items() if s in TRACKED))
        rows.append({"build": name, "class": CLASSES[cls], "guild": guild,
                     "count": len(held), "tracked": tracked,
                     # Expected swings at full skill, as multi_hit rolls them
                     # (combat_rules.c expected_swings_x100): two sure, second
                     # attack 49%, third 24% -- not whole sure blows.
                     "swings_at": {lvl: round(2 + sum({"second attack": 0.49, "third attack": 0.24}.get(s, 0)
                                                     for l2, s, _ in tracked if l2 <= lvl), 2)
                                   for lvl in (10, 25, 40, 50)}})
    return rows


def gaps(t: dict, minimum: int) -> list:
    """Stretches of `minimum` levels or more in which a build gains no
    tracked ability."""
    out = []
    for row in milestones(t, None):
        levels = sorted({lvl for lvl, _, _ in row["tracked"]})
        prev = 1
        for lvl in levels + [50]:
            if lvl - prev >= minimum:
                out.append({"build": row["build"], "from": prev, "to": lvl})
            prev = max(prev, lvl)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("milestones")
    m.add_argument("--build")
    g = sub.add_parser("gaps")
    g.add_argument("--min", type=int, default=10)
    args = ap.parse_args()
    t = load_tables()
    if args.cmd == "milestones":
        rows = milestones(t, args.build)
        if args.json:
            print(json.dumps(rows, indent=1))
            return 0
        for row in rows:
            print(f"== {row['build']} ({row['class']}) -- {row['count']} abilities")
            for lvl, s, how in row["tracked"]:
                print(f"  {lvl:>2}  {s:<20} {how}")
        return 0
    rows = gaps(t, args.min)
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r['build']:<6} nothing tracked from {r['from']} to {r['to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
