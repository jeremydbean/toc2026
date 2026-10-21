#!/usr/bin/env python3
"""Compare maxload.txt's player-owned counts with what player files hold.

area/maxload.txt keeps, for each limited object, how many copies players
own (`ML <vnum> <owned> <max>`). The game moves that number at every
change of hands; until 2026-10-21 it counted an object and at most its
immediate contents, so packing bags into bags and quitting with them left
the totals wrong (see "Contracts From The October 2026 Audit" in
AGENTS.md). The code is fixed; totals already wrong stay wrong until
somebody decides to correct them.

This counts every saved copy of each limited object across the player
files -- carried, worn, nested and stashed alike -- and prints where the
recorded number differs. It changes nothing. Players online when the
files were synced may hold copies not yet saved, so a small difference
is not proof of a fault. Run from the repository root:

    git fetch -q origin main && python3 tools/audit_maxload.py
    python3 tools/audit_maxload.py --dir player --maxload area/maxload.txt

It prints vnums, object names and counts, never who holds what. Exit
status is 1 when any count differs.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from audit_players import player_files  # noqa: E402


def read_maxload(ref: str | None, path: str | None) -> dict[int, tuple[int, int]]:
    if path:
        text = Path(path).read_text(encoding="latin-1")
    else:
        text = subprocess.run(["git", "show", f"{ref}:area/maxload.txt"], cwd=ROOT,
                              capture_output=True, check=True).stdout.decode("latin-1")
    rows = {}
    for m in re.finditer(r"(?m)^ML\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s*$", text):
        rows[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return rows


def held(text: str, limited: set[int]) -> Counter:
    """Every #O record's Vnum: the file holds objects at every depth and
    the stash after #STASH as flat #O records, each with its own Vnum."""
    found = Counter()
    for m in re.finditer(r"(?m)^#O\s*\n(?:.*\n)*?Vnum\s+(\d+)\s*$", text):
        vnum = int(m.group(1))
        if vnum in limited:
            found[vnum] += 1
    return found


def object_names(vnums: set[int]) -> dict[int, str]:
    try:
        from webadmin.area_parser import AreaParser
    except Exception:
        return {}
    parser = AreaParser(ROOT / "area")
    try:
        parser.parse_all()
    except Exception:
        return {}
    return {v: parser.objects[v].short_desc for v in vnums if v in parser.objects}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", default="origin/main", help="git ref holding player/ and area/maxload.txt")
    parser.add_argument("--dir", help="read player files from this directory instead of git")
    parser.add_argument("--maxload", help="read this maxload.txt instead of the one at --ref")
    args = parser.parse_args()

    recorded = read_maxload(None if args.maxload else args.ref, args.maxload)
    limited = set(recorded)
    counted = Counter()
    players = 0
    for _name, text in player_files(None if args.dir else args.ref, args.dir):
        players += 1
        counted.update(held(text, limited))

    names = object_names(limited)
    differ = [v for v in sorted(limited) if counted[v] != recorded[v][0]]
    print(f"{len(limited)} limited objects, {players} player files.")
    if not differ:
        print("Every recorded count matches the files.")
        return 0
    print(f"{'vnum':>6}  {'recorded':>8}  {'in files':>8}  {'max':>5}  object")
    for v in differ:
        owned, cap = recorded[v]
        print(f"{v:>6}  {owned:>8}  {counted[v]:>8}  {cap:>5}  {names.get(v, '?')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
