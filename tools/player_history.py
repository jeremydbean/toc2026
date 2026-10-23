#!/usr/bin/env python3
"""A player's saved states across git history -- for restoring them.

The state sync commits every character's file to git every five minutes,
and the milestone snapshots (before a death, a remort, a deletion, a staff
change) beside them under player/versions/. This reads them back, from the
repository root, after a `git fetch`:

  python3 tools/player_history.py log Alaric             states, newest first
  python3 tools/player_history.py show Alaric [REF]      worn, carried, stash
  python3 tools/player_history.py diff Alaric REF1 REF2  what changed between
  python3 tools/player_history.py export Alaric REF ID gear|stash|import

REF is any git revision (default origin/main), or a milestone snapshot's
file name ("Alaric.20261023_023244.death"), read from origin/main's
player/versions/. `export` writes that version to area/restores/ and adds
the request to area/restores.dat, which the game applies at the player's
next login once the commit is deployed (see wiki/player-backups.md).

It prints names, levels and objects, never a password hash or an address.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ATLANTA = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - zoneinfo missing
    ATLANTA = timezone.utc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REF = "origin/main"
_SHORT: dict[int, str] | None = None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="latin-1", check=True).stdout


def proper(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z]{2,12}", name):
        sys.exit(f"not a player name: {name}")
    return name.capitalize()


def read_version(name: str, ref: str) -> str:
    """The player file as REF holds it, or a milestone snapshot by name."""
    if ref.startswith(name + ".") and re.search(r"\.\d{8}_\d{6}", ref):
        return git("show", f"{DEFAULT_REF}:player/versions/{name}/{ref}")
    return git("show", f"{ref}:player/{name}")


def short_descriptions() -> dict[int, str]:
    global _SHORT
    if _SHORT is None:
        sys.path.insert(0, str(ROOT))
        from webadmin.area_parser import AreaParser
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        _SHORT = {int(v): getattr(o, "short_desc", "") or getattr(o, "short_descr", "")
                  for v, o in parser.objects.items()}
    return _SHORT


def parse(text: str) -> dict:
    """Level, coin and every object, by section: worn, carried, stash."""
    out = {"level": None, "worn": [], "carried": [], "stash": [], "coin": {}}
    section = "own"
    obj = None

    def finish():
        if obj is None:
            return
        if section == "stash":
            out["stash"].append(obj)
        elif section == "own":
            out["worn" if obj.get("wear", -1) >= 0 and obj.get("nest", 0) == 0 else "carried"].append(obj)

    for line in text.splitlines():
        if line.startswith("Levl ") and out["level"] is None:
            out["level"] = int(line.split()[1])
        for key in ("NewPlat", "NewGold", "NewSilv", "NewCopp"):
            if line.startswith(key + " ") and section == "own" and obj is None:
                out["coin"][key] = int(line.split()[1])
        if line.startswith("#"):
            finish()
            obj = None
            if line.startswith("#STASH"):
                section = "stash"
            elif line.startswith("#PET"):
                section = "pet"
            elif line.startswith("#O"):
                obj = {"vnum": 0, "nest": 0, "wear": -1, "short": None}
            continue
        if obj is None:
            continue
        m = re.match(r"(Vnum|Nest|Wear)\s+(-?\d+)", line)
        if m:
            obj[m.group(1).lower()] = int(m.group(2))
        elif line.startswith("ShD "):
            obj["short"] = line[4:].strip().rstrip("~")
    finish()
    return out


def name_of(obj: dict) -> str:
    return obj["short"] or short_descriptions().get(obj["vnum"], f"object {obj['vnum']}")


def when(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, ATLANTA).strftime("%b %d %I:%M %p %Z")


def cmd_log(args) -> None:
    name = proper(args.player)
    lines = git("log", f"-{args.limit}", "--format=%H %ct", DEFAULT_REF, "--",
                f"player/{name}").split("\n")
    print(f"{name}: the last {args.limit} saved states in git (newest first)")
    for line in filter(None, lines):
        sha, ct = line.split()
        try:
            state = parse(git("show", f"{sha}:player/{name}"))
        except subprocess.CalledProcessError:
            print(f"  {sha[:10]}  {when(int(ct))}  (file deleted)")
            continue
        print(f"  {sha[:10]}  {when(int(ct))}  level {state['level']}  "
              f"worn {len(state['worn'])}  carried {len(state['carried'])}  "
              f"stash {len(state['stash'])}")
    milestones = git("ls-tree", "--name-only", f"{DEFAULT_REF}:player/versions/{name}/") \
        if git("ls-tree", DEFAULT_REF, f"player/versions/{name}/").strip() else ""
    if milestones.strip():
        print("milestone snapshots (REF by name):")
        for file in sorted(milestones.split(), reverse=True):
            print(f"  {file}")


def cmd_show(args) -> None:
    name = proper(args.player)
    state = parse(read_version(name, args.ref))
    print(f"{name} at {args.ref}: level {state['level']}")
    for part in ("worn", "carried", "stash"):
        print(f"{part} ({len(state[part])}):")
        for obj in state[part]:
            print(f"  {'  ' * obj.get('nest', 0)}{name_of(obj)} ({obj['vnum']})")


def cmd_diff(args) -> None:
    name = proper(args.player)
    a, b = parse(read_version(name, args.ref1)), parse(read_version(name, args.ref2))
    print(f"{name}: {args.ref1} (level {a['level']}) -> {args.ref2} (level {b['level']})")
    for part in ("worn", "carried", "stash"):
        ca = Counter(name_of(o) for o in a[part])
        cb = Counter(name_of(o) for o in b[part])
        lost, gained = ca - cb, cb - ca
        if lost or gained:
            print(f"{part}:")
            for item, n in sorted(lost.items()):
                print(f"  - {item}" + (f" x{n}" if n > 1 else ""))
            for item, n in sorted(gained.items()):
                print(f"  + {item}" + (f" x{n}" if n > 1 else ""))


def cmd_export(args) -> None:
    name = proper(args.player)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,31}", args.id):
        sys.exit("an id is letters, digits, - and _")
    dat = ROOT / "area" / "restores.dat"
    if re.search(rf"(?m)^{re.escape(args.id)}\s", dat.read_text(encoding="latin-1")):
        sys.exit(f"id {args.id} is already used; ids are never reused")
    text = read_version(name, args.ref)
    if "#END" not in text:
        sys.exit("that version is not a whole player file")
    if args.ref.startswith(name + "."):
        epoch = None
        stamp = re.search(r"\.(\d{8}_\d{6})", args.ref).group(1)
    else:
        epoch = int(git("log", "-1", "--format=%ct", args.ref, "--", f"player/{name}").strip())
        stamp = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y%m%d_%H%M%S")
    file = f"{name}.{stamp}"
    (ROOT / "area" / "restores").mkdir(exist_ok=True)
    (ROOT / "area" / "restores" / file).write_text(text, encoding="latin-1")
    line = f"{args.id} {name} {args.kind} {stamp} {file}"
    with dat.open("a", encoding="latin-1") as fh:
        fh.write(line + "\n")
    print(f"wrote area/restores/{file}" + (f" ({when(epoch)})" if epoch else ""))
    print(f"added to area/restores.dat: {line}")
    print("commit both and push: applied at the player's next login after the deploy"
          if args.kind != "import" else
          "commit both and push: staff then see it in PRESTORE as 'imported from git'")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("log"); p.add_argument("player"); p.add_argument("--limit", type=int, default=40)
    p.set_defaults(func=cmd_log)
    p = sub.add_parser("show"); p.add_argument("player"); p.add_argument("ref", nargs="?", default=DEFAULT_REF)
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("diff"); p.add_argument("player"); p.add_argument("ref1"); p.add_argument("ref2")
    p.set_defaults(func=cmd_diff)
    p = sub.add_parser("export"); p.add_argument("player"); p.add_argument("ref"); p.add_argument("id")
    p.add_argument("kind", choices=("gear", "stash", "import")); p.set_defaults(func=cmd_export)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
