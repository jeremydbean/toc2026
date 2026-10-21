#!/usr/bin/env python3
"""Audit every player file for things that should never be true.

Player files live on the game host; the state sync copies them to git
every five minutes. This reads them from a git ref (origin/main by
default, after `git fetch`) or from a directory, and checks each mortal
against the game's own tables, read from src/const.c, src/fixes.c and the
area files -- so it cannot drift from the code:

  class-group     a group the character's class can never hold (not their
                  own guild's group): the creation bug that gave every new
                  character the mage's groups would have shown here weeks
                  before a player asked about it in chat
  class-skill     a skill or spell the class can never reach, that no held
                  group, the race, psionics or a remort gift explains
  skill-range     a learned percentage below 0 or above 100
  alignment       outside -1000..1000
  counts          negative practices, trains or coin
  level-cap       a mortal past 54 + remorts
  object-gone     an object (carried, worn or stashed) whose vnum no area
                  defines and no retired_objects row replaces: it is lost
                  at the next login
  fix-pending     a login fix (src/fixes.c) the character has not had yet;
                  information, not a fault -- they have not logged in since

It prints nothing about passwords, addresses or anything else in the
files beyond names and the values it reports. Run from the repository
root:

    git fetch -q origin main && python3 tools/audit_players.py
    python3 tools/audit_players.py --dir player     # a local copy
    python3 tools/audit_players.py --json           # for other tools

Exit status is 1 when anything other than fix-pending is found, so a
routine can tell "nothing to report" from "look at this".
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LEVEL_IMMORTAL = 60
CLASS_NAMES = ("mage", "cleric", "thief", "warrior", "monk", "necromancer")
GUILD_GROUPS = {0: "mage guild", 1: "cleric guild", 2: "thief guild", 3: "warrior guild"}
ALWAYS_ALLOWED = {"recall", "shadowmeld", "heroic grip"}
MONEY_KEYS = ("NewGold", "NewPlat", "NewCopp", "NewSilv", "BankCP")


# ----------------------------------------------------------------- tables

def _section(src: str, marker: str) -> str:
    start = src.index(marker)
    return src[start:src.index("\n};", start)]


def load_tables() -> dict:
    src = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    skills = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\}',
                         _section(src, "skill_table     [MAX_SKILL]")):
        levels = [int(x) for x in re.findall(r"-?\d+", m.group(2))]
        skills[m.group(1)] = levels
    groups = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\}',
                         _section(src, "group_table     [MAX_GROUP]")):
        ratings = [int(x) for x in re.findall(r"-?\d+", m.group(2))]
        members = re.findall(r'"([^"]+)"', m.group(3))
        groups[m.group(1)] = (ratings, members)
    races = {}
    for m in re.finditer(r'"(\w[\w ]*)",\s*"[^"]*",\s*\d+,\s*\{[^}]*\},\s*\{[^}]*\},\s*\{([^}]*)\}',
                         _section(src, "pc_race_table")):
        races[m.group(1)] = [s for s in re.findall(r'"([^"]*)"', m.group(2)) if s]
    fixes = re.findall(r'\{\s*"(\d{8}-[\w-]+)"',
                       (ROOT / "src" / "fixes.c").read_text(encoding="latin-1"))
    retired = {int(a) for a, _ in re.findall(
        r"\{\s*(\d+),\s*(\d+)\s*\}",
        (ROOT / "src" / "save.c").read_text(encoding="latin-1").split("retired_objects[] =", 1)[1].split("};", 1)[0])}
    return {"skills": skills, "groups": groups, "races": races,
            "fixes": fixes, "retired": retired}


def load_object_vnums() -> set:
    from webadmin.area_parser import AreaParser
    parser = AreaParser(ROOT / "area")
    parser.parse_all()
    return set(parser.objects)


def group_members(groups: dict, name: str, seen: set | None = None) -> set:
    """Every skill a group gives, through nested groups."""
    seen = set() if seen is None else seen
    if name in seen or name not in groups:
        return set()
    seen.add(name)
    out = set()
    for member in groups[name][1]:
        if member in groups:
            out |= group_members(groups, member, seen)
        else:
            out.add(member)
    return out


# ----------------------------------------------------------------- players

# A character's file is named for them: 2 to 12 letters, capitalised.
# Kyrus.Bu, Bugtest.deleted and Misery2 are copies somebody kept by hand,
# not characters the game loads, and were audited (and counted) as such.
CHARACTER_FILE = re.compile(r"[A-Z][a-z]{1,11}")


def player_files(ref: str | None, directory: str | None):
    if directory:
        for path in sorted(Path(directory).iterdir()):
            if path.is_file() and CHARACTER_FILE.fullmatch(path.name):
                yield path.name, path.read_text(encoding="latin-1", errors="replace")
        return
    listing = subprocess.run(["git", "ls-tree", ref, "player/"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    for line in listing.splitlines():
        meta, name = line.split("\t", 1)
        if meta.split()[1] != "blob":
            continue
        base = name.split("/", 1)[1]
        if not CHARACTER_FILE.fullmatch(base):
            continue
        text = subprocess.run(["git", "show", f"{ref}:{name}"], cwd=ROOT,
                              capture_output=True, check=True).stdout.decode("latin-1", "replace")
        yield base, text


def field(text: str, key: str) -> str | None:
    m = re.search(rf"(?m)^{re.escape(key)}\s+(.*?)\s*$", text)
    return m.group(1) if m else None


def audit_one(name: str, text: str, t: dict, vnums: set | None) -> list[dict]:
    found = []

    def add(kind: str, detail: str) -> None:
        found.append({"player": name, "kind": kind, "detail": detail})

    player = text.split("\n#O", 1)[0]
    level = int(field(player, "Levl") or 0)
    trust = int(field(player, "Tru") or 0)
    if level >= LEVEL_IMMORTAL or trust >= LEVEL_IMMORTAL:
        return found                     # staff, and staff-trusted, hold what they like
    cls = int(field(player, "Cla") or 0)
    guild = int(field(player, "Gui") or 11)
    race = (field(player, "Race") or "").rstrip("~")
    remorts = int(field(player, "NumRemorts") or 0)

    held_groups = re.findall(r"(?m)^Gr '([^']+)'", player)
    explained = set(ALWAYS_ALLOWED) | set(t["races"].get(race, []))
    for g in held_groups:
        ratings = t["groups"].get(g, ([0] * 6, []))[0]
        if cls < len(ratings) and ratings[cls] < 0 and g != GUILD_GROUPS.get(guild) and g != "rom basics":
            add("class-group", f"holds '{g}', which a {CLASS_NAMES[cls]} cannot")
        explained |= group_members(t["groups"], g)
    psi = (field(player, "PsiKnown") or "").rstrip("~")
    explained |= {p.strip() for p in psi.split(",") if p.strip()}

    stray = []
    for pct, skill in re.findall(r"(?m)^Sk\s+(-?\d+)\s+'([^']+)'", player):
        pct = int(pct)
        if pct < 0 or pct > 100:
            add("skill-range", f"{skill} at {pct}%")
        levels = t["skills"].get(skill)
        if levels and cls < len(levels) and levels[cls] >= LEVEL_IMMORTAL and skill not in explained:
            stray.append(f"{skill} {pct}%")
    if stray:
        shown = ", ".join(stray[:8]) + (f", ... ({len(stray)} in all)" if len(stray) > 8 else "")
        add("class-skill", f"{len(stray)} a {CLASS_NAMES[cls]} cannot reach: {shown}")

    align = int(field(player, "Alig") or 0)
    if not -1000 <= align <= 1000:
        add("alignment", str(align))
    for key in ("Prac", "Trai") + MONEY_KEYS:
        value = field(player, key)
        if value is not None and int(value.split()[0]) < 0:
            add("counts", f"{key} {value}")
    if level > 54 + remorts:
        add("level-cap", f"level {level} with {remorts} remorts")

    if vnums is not None:
        for vnum in re.findall(r"(?m)^Vnum\s+(\d+)", text):
            v = int(vnum)
            if v not in vnums and v not in t["retired"]:
                add("object-gone", f"object {v}")

    done = set((field(player, "Fixes") or "").rstrip("~").split())
    for fix in t["fixes"]:
        if fix not in done:
            add("fix-pending", fix)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", default="origin/main", help="git ref holding player/ (default origin/main)")
    parser.add_argument("--dir", help="read player files from this directory instead of git")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--no-objects", action="store_true", help="skip the object check (no area parse)")
    args = parser.parse_args()

    tables = load_tables()
    vnums = None if args.no_objects else load_object_vnums()
    findings = []
    players = 0
    for name, text in player_files(None if args.dir else args.ref, args.dir):
        players += 1
        findings.extend(audit_one(name, text, tables, vnums))

    if args.json:
        print(json.dumps({"players": players, "findings": findings}, indent=1))
    else:
        by_kind = defaultdict(list)
        for f in findings:
            by_kind[f["kind"]].append(f)
        print(f"Audited {players} player files.")
        if not findings:
            print("Nothing found.")
        pending = by_kind.pop("fix-pending", [])
        for kind in sorted(by_kind):
            rows = by_kind[kind]
            print(f"\n{kind} ({len(rows)})")
            for f in rows[:60]:
                print(f"  {f['player']:<14} {f['detail']}")
            if len(rows) > 60:
                print(f"  ... and {len(rows) - 60} more")
        if pending:
            counts = defaultdict(int)
            for f in pending:
                counts[f["detail"]] += 1
            print("\nfix-pending (characters who have not logged in since the fix)")
            for fix in tables["fixes"]:
                if counts.get(fix):
                    print(f"  {fix:<28} {counts[fix]} characters")
    return 1 if any(f["kind"] != "fix-pending" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
