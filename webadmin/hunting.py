"""HUNTING's suggestions for the game, from the website's leveling guide.

The dashboard's leveling guide (server.leveling_guide, /api/leveling) ranks
the creatures a player of each level might hunt, from players' own kills
where enough of them have been measured and a calibrated model elsewhere.
The game cannot read that guide, so the dashboard writes a short file of
numbers into the game's working directory (area/hunting.txt), and the
game's HUNTING command (src/hunting.c) reads it, filling in names and the
WALKTO to each area from its own world.

Rules (2026-11-15):

- Several alternatives, never one favourite: at most one creature an area,
  and among them the best experience an hour, the safest and the least
  hunted, then the rest by experience -- so a level's players are not all
  sent to the same few rooms.
- Aggregates only: a creature measured from players near the level counts
  only when HUNTING_MIN_CHARACTERS characters or more were measured (the
  guide itself trusts two); a row measured from fewer is left out, never
  shown as if modelled. The file holds no name, no player, no room.
- Ordinary prey only: no Hyrule dungeon creature (its row names what the way
  in needs), no area nothing leads to (the guide already leaves those out).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

HUNTING_FILE = "hunting.txt"
HUNTING_LEVELS = range(1, 60)          # mortal levels 1-59
HUNTING_PER_LEVEL = 5                  # suggestions a level (fits a screen)
HUNTING_MIN_CHARACTERS = 3             # measured rows need this many
VIABLE_SHARE = 0.4                     # of the level's best xp an hour
HEADER = (
    "# HUNTING's suggestions (src/hunting.c), written by the dashboard from\n"
    "# its leveling guide (webadmin/hunting.py). Regenerated; never edit.\n"
    "# level vnum basis(M measured/E estimate) xp_per_hour kill_seconds\n"
    "# risk_permille(-1 unknown) aggressive(0/1) area_file\n"
)


def _usable(row: Dict[str, Any]) -> bool:
    if row.get("needs") or not row.get("area_file") or " " in str(row["area_file"]):
        return False
    if int(row.get("xp_per_hour") or 0) <= 0:
        return False
    if row.get("basis") == "measured" and int(row.get("measured_characters") or 0) < HUNTING_MIN_CHARACTERS:
        return False
    return True


def _risk(row: Dict[str, Any]) -> float:
    risk = row.get("risk")
    return float(risk) if risk is not None else (0.5 if row.get("aggressive") else 0.1)


def _hunted(row: Dict[str, Any]) -> int:
    seen = row.get("observed") or {}
    return int(seen.get("kills") or 0)


def pick(rows: Iterable[Dict[str, Any]], per_level: int = HUNTING_PER_LEVEL) -> List[Dict[str, Any]]:
    """Up to `per_level` creatures for one level from the guide's rows:
    one an area, viable (at least VIABLE_SHARE of the best experience an
    hour), chosen best, safest, least hunted, then by experience, and
    returned best first."""
    ordered = sorted((r for r in rows if _usable(r)),
                     key=lambda r: (-int(r["xp_per_hour"]), int(r["vnum"])))
    if not ordered:
        return []
    best = int(ordered[0]["xp_per_hour"])
    by_area: Dict[str, Dict[str, Any]] = {}
    for r in ordered:
        if int(r["xp_per_hour"]) < best * VIABLE_SHARE:
            break
        by_area.setdefault(str(r["area_file"]), r)
    choices = list(by_area.values())
    chosen: List[Dict[str, Any]] = []

    def take(r: Dict[str, Any]) -> None:
        if r not in chosen and len(chosen) < per_level:
            chosen.append(r)

    take(choices[0])
    take(min(choices, key=lambda r: (_risk(r), -int(r["xp_per_hour"]), int(r["vnum"]))))
    take(min(choices, key=lambda r: (_hunted(r), -int(r["xp_per_hour"]), int(r["vnum"]))))
    for r in choices:
        take(r)
    chosen.sort(key=lambda r: (-int(r["xp_per_hour"]), int(r["vnum"])))
    return chosen


def line(level: int, row: Dict[str, Any]) -> str:
    risk = row.get("risk")
    return "%d %d %s %d %d %d %d %s\n" % (
        level, int(row["vnum"]), "M" if row.get("basis") == "measured" else "E",
        int(row["xp_per_hour"]), int(round(float(row.get("kill_seconds") or 0))),
        -1 if risk is None else int(round(float(risk) * 1000)),
        1 if row.get("aggressive") else 0, row["area_file"])


def render(by_level: Dict[int, List[Dict[str, Any]]]) -> str:
    out = [HEADER]
    for level in sorted(by_level):
        out.extend(line(level, r) for r in by_level[level])
    return "".join(out)


def write(path: Path, text: str) -> bool:
    """Write the file whole, only when it changed: aside, flushed, renamed.
    Returns whether it was written."""
    try:
        if path.read_text(encoding="ascii") == text:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return True
