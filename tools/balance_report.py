#!/usr/bin/env python3
"""Balance the world from what players kill.

Reads log/progress.tsv -- encounters, kills, rewards, flees, deaths, what
each corpse was made with and what players took back out of it
(src/playlog.c; webadmin/balance.py joins them) -- and, band by band of
five foe levels, ranks every mobile players have fought by experience per
combat minute, with its sample, the spread of its kill times, what it pays
in experience an hour (downtime included), coin and gear (generated and
actually looted), what it costs in hit points, and how often it sends a
player running or kills them. Each band's median is the yardstick:

  generous   xp/min at least twice the band's median -- the farm
  poor       half the median or less -- nobody should be sent there
  risky      a fifth or more of encounters end in a flee or a death
  rich       coin per kill three times the band's or more
  farmed     one character takes most of its kills

and a band with fewer than three equal choices (within a quarter of the
median, not risky, and reachable) is a GAP. Placed mobiles nobody has
fought are counted beside each band from the area files, so a gap says
whether the world has nothing there or players have not found it.
Hyrule's guardians and mobiles in areas no route reaches are not counted
as choices. The last section proposes manual changes, each with its
evidence and a confidence; nothing is edited.

Legacy rows (before 2026-11-10 a group kill wrote one "kill" row per
member) count as 1/members of a kill and are marked.

Aggregates only: the file names characters by Id, and Ids are counted,
never printed. Run from the repository root:

  python3 tools/balance_report.py                 # origin/main's log
  python3 tools/balance_report.py --file log/progress.tsv --band 21
  python3 tools/balance_report.py --vnum 29202     # one mobile, sliced
  python3 tools/balance_report.py --since 2026-11-01 --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import balance  # noqa: E402


def git_show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return out.stdout.decode("latin-1", "replace") if out.returncode == 0 else ""


def copper(n) -> str:
    if n is None:
        return "-"
    n = int(round(n))
    parts = []
    for unit, size in (("p", 1000000), ("g", 10000), ("s", 100)):
        if n >= size:
            parts.append(f"{n // size}{unit}")
            n %= size
    if n or not parts:
        parts.append(f"{n}c")
    return " ".join(parts[:2])


def secs(n) -> str:
    return "-" if n is None else f"{n:.0f}"


def pct(n) -> str:
    return "-" if n is None else f"{100 * n:.0f}%"


def world(skip: bool):
    """Names, placed mobiles per band and reachability, from the area
    files and the routes -- or nothing when asked not to read them."""
    if skip:
        return {}, {}, {}, None
    try:
        from webadmin.area_parser import AreaParser
        from webadmin import gear_drops
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        routes = json.loads((ROOT / "webadmin" / "directions.json").read_text(encoding="utf-8"))
    except Exception as exc:          # a report without names is still a report
        print(f"(area files not read: {exc})", file=sys.stderr)
        return {}, {}, {}, None
    key = lambda name: " ".join(str(name or "").split())   # noqa: E731
    routed = {key(r.get(k)) for r in routes.get("routes", []) for k in ("area", "area_display")}
    start = parser.rooms.get(2401)
    routed.add(key(getattr(start, "area_name", "")))
    guardians = set(gear_drops.GUARDIAN_VNUMS)
    mobs = {v: m.short_desc for v, m in parser.mobiles.items()}
    objs = {v: o.short_desc for v, o in parser.objects.items()}
    placed: Dict[tuple, int] = {}
    reach: Dict[int, bool] = {}
    for v, m in parser.mobiles.items():
        level = int(m.level or 0)
        ok = v not in guardians and key(m.area_name) in routed
        reach[v] = ok
        if level > 0 and ok and (getattr(m, "spawn_rooms", None) or []):
            band = balance.band_of(level)
            placed[band] = placed.get(band, 0) + 1
    return mobs, objs, placed, (lambda v: reach.get(v, True))


def row_line(v, m, name) -> str:
    gear = (f"{pct(m['drop_rate'])}/{copper(m['gear_looted_per_kill'])}"
            if m["drop_rate"] is not None else "-")
    coin = (f"{copper(m['coin_generated_per_kill'])}"
            + (f"/{copper(m['coin_looted_per_kill'])}" if m["coin_looted_per_kill"] is not None
               else ""))
    spread = (f"{secs(m['p25_seconds'])}-{secs(m['median_seconds'])}-{secs(m['p75_seconds'])}"
              if m["median_seconds"] else "-")
    legacy = f" L{m['legacy']}" if m["legacy"] else ""
    return (f"  {v:>5} {m['level']:>4}  {name[:24]:<24} {m['area'][:14]:<14} "
            f"{m['kills']:>6g}{legacy:<5} {m['characters']:>2} {spread:>11} "
            f"{m['xp_per_min']:>7.0f} {m.get('ratio', 0):>5.2f} {m['xp_per_hour']:>8.0f} "
            f"{coin:>13} {gear:>12} {m['hp_lost_per_kill']:>6.0f} {m['risk']:>5.2f}  "
            + ",".join(m.get("flags", [])))


HEADER = ("  vnum  lvl  name                     area            kills  ch  p25-med-p75"
          "  xp/min ratio    xp/hr  coin gen/loot  gear %/loot  hp/k  risk  flags")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="origin/main", help="git ref to read log/progress.tsv from")
    ap.add_argument("--file", help="read this file instead of git")
    ap.add_argument("--since", help="UTC YYYY-MM-DD")
    ap.add_argument("--band", type=int, help="only the band holding this foe level")
    ap.add_argument("--vnum", type=int, help="one mobile, with its slices")
    ap.add_argument("--all", action="store_true", help="list untrusted mobiles too")
    ap.add_argument("--no-names", action="store_true", help="skip reading the area files")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = (Path(args.file).read_text(encoding="latin-1") if args.file
            else git_show(args.ref, "log/progress.tsv"))
    since = 0.0
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    result = balance.compare(balance.summarize(text, since))
    mob_names, obj_names, placed, reachable = world(args.no_names or args.json)
    name = lambda v: mob_names.get(v) or "?"    # noqa: E731

    if args.json:
        out: Dict[str, Any] = {"bands": {}, "mobs": {}, "proposals": balance.proposals(result)}
        for (low, high), b in result["bands"].items():
            out["bands"][f"{low}-{high}"] = {
                "median_xp_per_min": b["median_xp_per_min"], "median_coin": b["median_coin"],
                "equal": b["equal"], "gap": b["gap"], "mobs": b["mobs"]}
        for v, m in result["mobs"].items():
            out["mobs"][str(v)] = m
        print(json.dumps(out, indent=1, sort_keys=True, default=str))
        return 0

    mobs = result["mobs"]
    if not mobs:
        print("No encounters in log/progress.tsv for the window.")
        return 0
    if args.vnum is not None:
        m = mobs.get(args.vnum)
        if m is None:
            print(f"No kills of mob {args.vnum} in the window.")
            return 0
        print(f"mob {args.vnum} {name(args.vnum)} (level {m['level']}, {m['area']}): "
              f"{'trusted' if m['trusted'] else 'too few kills to trust'}")
        print(HEADER)
        print(row_line(args.vnum, m, "all"))
        for sname, sm in sorted(m["slices"].items()):
            sm.setdefault("level", m["level"])
            sm.setdefault("area", m["area"])
            print(row_line(args.vnum, sm, sname))
        print(f"  instant kills {m['instant']}, unresolved encounters {m['unresolved']}, "
              f"capped (no xp accepted) {pct(m['capped_share'])}, unlooted corpses "
              f"{pct(m['unlooted_share'])}, multi-foe kills {pct(m['multi_foe_share'])}, "
              f"top character's share {pct(m['top_player_share'])}")
        return 0

    total = sum(m["kills"] for m in mobs.values())
    legacy = sum(m["legacy"] for m in mobs.values())
    print(f"Balance from {total:g} kills of {len(mobs)} kinds of mobile "
          f"({legacy} legacy rows, counted 1/members each). A mobile is ranked from "
          f"{balance.MIN_KILLS} kills by {balance.MIN_CHARACTERS}+ characters.")
    for (low, high) in sorted(result["bands"]):
        if args.band and not low <= args.band <= high:
            continue
        b = result["bands"][(low, high)]
        equal = [v for v in b["equal"] if reachable is None or reachable(v)]
        world_n = placed.get((low, high))
        print(f"\n== foe levels {low}-{high}: median {b['median_xp_per_min']:.0f} xp/min, "
              f"{copper(b['median_coin'])} a kill; {len(equal)} equal choice(s)"
              + ("  ** GAP **" if len(equal) < balance.EQUAL_CHOICES_WANTED else "")
              + f"; {len(b['mobs'])} kind(s) fought"
              + (f" of {world_n} placed and reachable" if world_n else ""))
        print(HEADER)
        for v in sorted(b["mobs"], key=lambda v: -mobs[v]["xp_per_min"]):
            m = mobs[v]
            if not m["trusted"] and not args.all:
                continue
            reach = "" if reachable is None or reachable(v) else " (not ordinary prey)"
            print(row_line(v, m, name(v) + reach))
        untrusted = [v for v in b["mobs"] if not mobs[v]["trusted"]]
        if untrusted and not args.all:
            print(f"  (+{len(untrusted)} kind(s) with too few kills to rank; --all lists them)")
        drops: Dict[int, int] = {}
        for v in b["mobs"]:
            for o, n in mobs[v]["dropped"].items():
                drops[o] = drops.get(o, 0) + n
        if drops:
            top = sorted(drops.items(), key=lambda kv: -kv[1])[:6]
            print("  most dropped: " + "; ".join(f"{obj_names.get(o, o)} x{n}" for o, n in top))

    props = balance.proposals(result, names=name, reachable=reachable)
    if props:
        print("\n== proposals (manual; nothing is changed)")
        for p in props:
            if args.band and not int(p["band"].split("-")[0]) <= args.band <= int(p["band"].split("-")[1]):
                continue
            who = f"{p['vnum']} {p['name']}" if p["vnum"] else "band"
            print(f"  [{p['confidence']}] {p['band']} {who}: {p['finding']} -- {p['proposal']}. "
                  f"Evidence: {p['evidence']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
