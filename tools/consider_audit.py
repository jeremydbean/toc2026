#!/usr/bin/env python3
"""Hold CONSIDER to the fights players actually had.

CONSIDER (do_consider and consider_fight in src/act_info.c) estimates,
blow for blow, how many rounds the character would need to bring the foe
down and how many the foe would need for them, and gives a verdict from
the two. This compares those predictions with what happened next.

Three sources, best first:

- From 2026-11-10 the game makes the prediction itself, said to nobody,
  at the start of every encounter (the ``engage`` row of
  log/progress.tsv), whether or not the player typed CONSIDER; the fight's
  ``slain``, ``flee`` and ``death`` rows carry the same encounter id, and
  the slain row the rounds the mobile fought and the hit points that came
  off it and that it took off players, so every fight is an exact
  comparison: rounds, damage a round each way, and the outcome.
- A typed CONSIDER also writes a ``consider`` row to log/progress.tsv
  (the character's serial -- the file Id before 2026-11-12 -- the foe,
  both predicted rounds, both predicted
  damage a round, the verdict) and the fight that follows has its own
  rows, so the join is exact: the same character and foe vnum, the next outcome
  within ten minutes.
- Before that, log/play.tsv kept the first three lines of every command's
  reply, which hold the predicted rounds (not the verdict). Those are
  joined to log/progress.tsv by the character's level, the area and the
  time -- the two files name characters differently, by name and by number,
  and this never puts the two side by side -- and the mobile by its
  keywords in the area files. A join that finds two candidates is
  dropped. These are marked "inferred".

It prints aggregates only: how far actual kill rounds were from the
prediction, by how hard CONSIDER said the fight would be; how often each
predicted edge ended in a kill, a flee or a death; and how the hit points
the fight cost compare with the damage it predicted the foe would deal.
Run from the repository root:

  python3 tools/consider_audit.py                     # origin/main's logs
  python3 tools/consider_audit.py --play log/play.tsv --progress log/progress.tsv
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ROUND_SECONDS = 3.0           # PULSE_VIOLENCE: 3 * PULSE_PER_SECOND pulses of a quarter second
WINDOW_S = 600                # a fight this long after the CONSIDER is the one it was about
ROUNDS_RE = re.compile(
    r"you would need (a single round|about (\d+) rounds|over a hundred rounds) to bring .*? down;"
    r" \w+ would need (a single round|about (\d+) rounds|over a hundred rounds) for you")
SCRATCH_RE = re.compile(r"could barely scratch you; you would need "
                        r"(a single round|about (\d+) rounds|over a hundred rounds)")


def git_show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return out.stdout.decode("latin-1", "replace") if out.returncode == 0 else ""


def rounds_of(text: str, number: Optional[str]) -> float:
    if text.startswith("a single"):
        return 1.0
    if text.startswith("over"):
        return 101.0
    return float(number)


def edge_band(edge: Optional[float]) -> str:
    """CONSIDER's own verdict thresholds (consider_fight)."""
    if edge is None:
        return "barely scratched (win easily)"
    for cut, name in ((4.0, "edge >= 4 (win easily)"), (1.5, "1.5-4 (should win)"),
                      (1.0, "1-1.5 (win, not by much)"), (0.67, "0.67-1 (either way)"),
                      (0.25, "0.25-0.67 (probably lose)")):
        if edge >= cut:
            return name
    return "< 0.25 (almost certainly die)"


VERDICT_BAND = {
    "easily": "edge >= 4 (win easily)", "win": "1.5-4 (should win)",
    "narrow": "1-1.5 (win, not by much)", "even": "0.67-1 (either way)",
    "lose": "0.25-0.67 (probably lose)", "die": "< 0.25 (almost certainly die)",
    "scratch": "barely scratched (win easily)",
}


def keyword_matcher(skip: bool):
    if skip:
        return None
    try:
        from webadmin.area_parser import AreaParser
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
    except Exception as exc:
        print(f"(area files not read: {exc})", file=sys.stderr)
        return None
    words = {v: str(getattr(m, "keywords", "") or getattr(m, "name", "") or "").lower().split()
             for v, m in parser.mobiles.items()}

    def matches(vnum: int, arg: str) -> bool:
        arg = re.sub(r"^\d+\.", "", arg.strip().lower()).split(" ")[0]
        return bool(arg) and any(w.startswith(arg) for w in words.get(vnum, []))
    return matches


def outcomes(progress: str) -> List[dict]:
    """Every fight's end from log/progress.tsv, new rows and legacy."""
    out = []
    for raw in progress.splitlines():
        f = raw.split("\t")
        if len(f) < 11 or not f[0].isdigit():
            continue
        kind = f[1]
        row = {"epoch": int(f[0]), "who": f[2], "level": f[3], "vnum": int(f[8]) if f[8].isdigit() else -1,
               "area": f[10], "kind": None, "ms": -1, "lost": None, "hp_pct": int(f[6]) if f[6].isdigit() else None}
        if kind in ("kill", "reward") and len(f) > 19:
            row.update(kind="kill", ms=int(f[11]) if f[11].lstrip("-").isdigit() else -1,
                       lost=int(f[19]) if f[19].lstrip("-").isdigit() else None,
                       group=int(f[15]) > 1 if f[15].isdigit() else False)
        elif kind in ("flee", "death"):
            row.update(kind=kind)
        elif kind == "consider" and len(f) > 18:
            row.update(kind="consider", yours=float(f[11]), theirs=float(f[12]),
                       your_rounds=float(f[13]), their_rounds=float(f[14]), verdict=f[15],
                       player_hp=int(f[16]), foe_hp=int(f[17]))
        else:
            continue
        out.append(row)
    return out


def exact_pairs(rows: List[dict]) -> List[dict]:
    by = defaultdict(list)
    for r in rows:
        by[(r["who"], r["vnum"])].append(r)
    pairs = []
    for key, rs in by.items():
        rs.sort(key=lambda r: r["epoch"])
        for i, r in enumerate(rs):
            if r["kind"] != "consider":
                continue
            nxt = next((o for o in rs[i + 1:] if o["kind"] in ("kill", "flee", "death")
                        and o["epoch"] - r["epoch"] <= WINDOW_S), None)
            if nxt is None or any(o["kind"] == "consider" and o["epoch"] < nxt["epoch"]
                                  for o in rs[i + 1:]):
                continue
            edge = (r["their_rounds"] / r["your_rounds"]
                    if r["theirs"] >= 0.5 and r["your_rounds"] > 0 else None)
            pairs.append({"pred_yours": r["your_rounds"], "pred_theirs": r["their_rounds"],
                          "edge": edge, "band": VERDICT_BAND.get(r["verdict"], edge_band(edge)),
                          "outcome": nxt, "player_hp": r["player_hp"], "inferred": False})
    return pairs


def inferred_pairs(play: str, rows: List[dict], matches) -> List[dict]:
    ends = [r for r in rows if r["kind"] in ("kill", "flee", "death")]
    pairs = []
    for raw in play.splitlines():
        f = raw.split("\t")
        if len(f) < 13 or f[1] != "cmd" or not f[10].lower().startswith("con") or not f[0].isdigit():
            continue
        reply = f[12]
        m = ROUNDS_RE.search(reply)
        s = None if m else SCRATCH_RE.search(reply)
        if not m and not s:
            continue
        when, level, area, arg = int(f[0]), f[3], f[5], f[11]
        cands = [o for o in ends if o["level"] == level and o["area"] == area
                 and 0 <= o["epoch"] - when <= WINDOW_S
                 and (matches is None or matches(o["vnum"], arg))]
        if not cands:
            continue
        first = min(cands, key=lambda o: o["epoch"])
        same_time = [o for o in cands if o["epoch"] == first["epoch"] and o["who"] != first["who"]]
        if same_time:
            continue          # two characters it could be: not a join
        if m:
            yours = rounds_of(m.group(1), m.group(2))
            theirs = rounds_of(m.group(3), m.group(4))
            edge = theirs / yours if yours else None
        else:
            yours, theirs, edge = rounds_of(s.group(1), s.group(2)), None, None
        pairs.append({"pred_yours": yours, "pred_theirs": theirs, "edge": edge,
                      "band": edge_band(edge), "outcome": first, "player_hp": None,
                      "inferred": True})
    return pairs


def encounter_pairs(progress: str) -> List[dict]:
    """Every encounter with the silent prediction made at its start,
    joined by its id to how it ended."""
    engages, ends = {}, {}
    for raw in progress.splitlines():
        f = raw.split("\t")
        if len(f) < 11 or not f[0].isdigit():
            continue
        if f[1] == "engage" and len(f) > 26:
            engages[f[11]] = {"yours": float(f[21]), "theirs": float(f[22]),
                              "your_rounds": float(f[23]), "their_rounds": float(f[24]),
                              "verdict": f[25], "caster": f[26] == "1", "class": f[4],
                              "player_hp": int(f[13])}
        elif f[1] == "slain" and len(f) > 22:
            ends[f[11]] = {"kind": "kill", "rounds": int(f[22]), "taken": int(f[18]),
                           "swings": int(f[23]) if len(f) > 25 else 0,
                           "landed": int(f[24]) if len(f) > 25 else 0,
                           "by_skills": int(f[25]) if len(f) > 25 else 0,
                           "dealt": int(f[20]), "solo": f[15] == "1" and f[16] == "0",
                           "instant": f[13] == "instant",
                           "ms": int(f[12]) if f[12].lstrip("-").isdigit() else -1}
        elif f[1] in ("flee", "death") and len(f) > 14 and f[14] != "-":
            ends.setdefault(f[14], {"kind": f[1]})
    out = []
    for enc, e in engages.items():
        if e["verdict"] == "-" or enc not in ends:
            continue
        edge = (e["their_rounds"] / e["your_rounds"]
                if e["verdict"] != "scratch" and e["your_rounds"] > 0 else None)
        out.append(dict(e, outcome=ends[enc], edge=edge,
                        band=VERDICT_BAND.get(e["verdict"], edge_band(edge))))
    return out


def encounter_report(pairs: List[dict]) -> None:
    if not pairs:
        print("\nNo encounters carry the silent prediction yet (rows from 2026-11-10 on).")
        return
    print(f"\n== every encounter, held to what CONSIDER would have said ({len(pairs)})")
    print("  verdict                            n  kill flee death  pred rds  actual rds"
          "  your dmg/rd pred-actual  foe dmg/rd pred-actual")
    order = ["barely scratched (win easily)", "edge >= 4 (win easily)", "1.5-4 (should win)",
             "1-1.5 (win, not by much)", "0.67-1 (either way)", "0.25-0.67 (probably lose)",
             "< 0.25 (almost certainly die)"]
    bands = defaultdict(list)
    for p in pairs:
        bands[p["band"]].append(p)
    for band in order:
        ps = bands.get(band, [])
        if not ps:
            continue
        kills = [p for p in ps if p["outcome"]["kind"] == "kill"
                 and p["outcome"]["rounds"] > 0 and not p["outcome"]["instant"]]
        solo = [p for p in kills if p["outcome"]["solo"]]
        act_rds = median(p["outcome"]["rounds"] for p in kills) if kills else None
        your_act = median(p["outcome"]["taken"] / p["outcome"]["rounds"] for p in solo) if solo else None
        foe_act = median(p["outcome"]["dealt"] / p["outcome"]["rounds"] for p in kills) if kills else None
        print(f"  {band:<31} {len(ps):>4} "
              f"{sum(p['outcome']['kind'] == 'kill' for p in ps):>5} "
              f"{sum(p['outcome']['kind'] == 'flee' for p in ps):>4} "
              f"{sum(p['outcome']['kind'] == 'death' for p in ps):>5} "
              f"{median(p['your_rounds'] for p in ps):>9.1f} "
              f"{'-' if act_rds is None else f'{act_rds:.1f}':>11} "
              f"{median(p['yours'] for p in ps):>12.0f}-{'-' if your_act is None else f'{your_act:.0f}':<8}"
              f"{median(p['theirs'] for p in ps):>12.0f}-{'-' if foe_act is None else f'{foe_act:.0f}'}")
    kills = [p["outcome"] for p in pairs if p["outcome"]["kind"] == "kill"]
    swings = sum(o.get("swings", 0) for o in kills)
    if swings:
        landed = sum(o.get("landed", 0) for o in kills)
        print(f"  Players' melee swings that took hit points: {landed / swings:.0%} "
              f"({swings} swings) -- CONSIDER counts every one as landing.")
    taken = sum(o["taken"] for o in kills)
    if taken:
        print(f"  Hit points that came off by spells and skills: "
              f"{sum(o.get('by_skills', 0) for o in kills) / taken:.0%} -- CONSIDER counts none.")
    by_class = defaultdict(list)
    for p in pairs:
        o = p["outcome"]
        if o["kind"] == "kill" and o.get("rounds") and not o["instant"] and p["your_rounds"] < 101:
            by_class[p["class"]].append(o["rounds"] / p["your_rounds"])
    names = {"0": "mage", "1": "cleric", "2": "thief", "3": "warrior", "4": "monk", "5": "necromancer"}
    for c, ratios in sorted(by_class.items()):
        print(f"  {names.get(c, c):<12} kills took {median(ratios):.2f}x the predicted rounds "
              f"({len(ratios)} kills)")


def report(pairs: List[dict]) -> None:
    if not pairs:
        print("No CONSIDER could be joined to a fight that followed it.")
        return
    print(f"{len(pairs)} CONSIDERs joined to the fight that followed "
          f"({sum(p['inferred'] for p in pairs)} inferred from play.tsv's reply lines).")
    order = ["barely scratched (win easily)", "edge >= 4 (win easily)", "1.5-4 (should win)",
             "1-1.5 (win, not by much)", "0.67-1 (either way)", "0.25-0.67 (probably lose)",
             "< 0.25 (almost certainly die)"]
    print("\n  predicted edge                    n  kill flee death  pred rds  actual rds"
          "  actual/pred (p25-med-p75)")
    bands = defaultdict(list)
    for p in pairs:
        bands[p["band"]].append(p)
    ratios_all = []
    for band in order:
        ps = bands.get(band, [])
        if not ps:
            continue
        kills = [p for p in ps if p["outcome"]["kind"] == "kill"]
        timed = [p for p in kills if p["outcome"]["ms"] > 0]
        ratios = sorted((p["outcome"]["ms"] / 1000 / ROUND_SECONDS) / p["pred_yours"]
                        for p in timed if p["pred_yours"] and p["pred_yours"] < 101)
        ratios_all += ratios
        q = (lambda k: ratios[min(len(ratios) - 1, int(k * (len(ratios) - 1) + 0.5))]) if ratios else None
        pred = median(p["pred_yours"] for p in ps)
        act = median(p["outcome"]["ms"] / 1000 / ROUND_SECONDS for p in timed) if timed else None
        print(f"  {band:<31} {len(ps):>3} {len(kills):>5} "
              f"{sum(p['outcome']['kind'] == 'flee' for p in ps):>4} "
              f"{sum(p['outcome']['kind'] == 'death' for p in ps):>5} {pred:>9.1f} "
              f"{'-' if act is None else f'{act:.1f}':>11}  "
              + (f"{q(0.25):.2f}-{q(0.5):.2f}-{q(0.75):.2f}" if ratios else "-"))
    if ratios_all:
        ratios_all.sort()
        med = ratios_all[len(ratios_all) // 2]
        print(f"\n  Over all kills: actual rounds were {med:.2f}x the prediction at the median"
              f" ({len(ratios_all)} timed kills).")
        early = sum(r < 0.5 for r in ratios_all)
        late = sum(r > 2 for r in ratios_all)
        print(f"  Under half the predicted rounds: {early}; over twice: {late}.")
    # The foe's side: the hit points a won fight cost, against the share of
    # the character's hit points CONSIDER's rounds imply it would take.
    cost = []
    for p in pairs:
        o = p["outcome"]
        if o["kind"] != "kill" or not p["pred_theirs"] or o["ms"] <= 0 or o.get("group"):
            continue
        if o["hp_pct"] is None:
            continue
        rounds = o["ms"] / 1000 / ROUND_SECONDS
        predicted_share = min(1.0, rounds / p["pred_theirs"])     # of their hit points
        actual_share = max(0.0, 1.0 - o["hp_pct"] / 100.0)        # an upper bound: from full
        cost.append((predicted_share, actual_share))
    if cost:
        pred = median(c[0] for c in cost)
        act = median(c[1] for c in cost)
        print(f"  Hit points a won solo fight left missing: {act:.0%} at the median, against "
              f"{pred:.0%} CONSIDER's foe rounds imply for that fight's length ({len(cost)} kills;"
              " the actual figure assumes a fight begun at full health, so it is an upper bound).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--play", help="read this play.tsv instead of git")
    ap.add_argument("--progress", help="read this progress.tsv instead of git")
    ap.add_argument("--no-names", action="store_true", help="skip the area files' keywords")
    args = ap.parse_args()
    play = (Path(args.play).read_text(encoding="latin-1") if args.play
            else git_show(args.ref, "log/play.tsv"))
    progress = (Path(args.progress).read_text(encoding="latin-1") if args.progress
                else git_show(args.ref, "log/progress.tsv"))
    rows = outcomes(progress)
    print("== typed CONSIDERs and the fight that followed")
    pairs = exact_pairs(rows) + inferred_pairs(play, rows, keyword_matcher(args.no_names))
    report(pairs)
    encounter_report(encounter_pairs(progress))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
