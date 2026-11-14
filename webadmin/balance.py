"""What players' kills actually took and paid, from log/progress.tsv.

The game writes numeric rows about every fight a player has with a
mobile (src/playlog.c, "The balance feed"): an ``engage`` when the
encounter starts; one ``slain`` per mobile death that credits anybody; a
``reward`` per player it pays; ``flee`` and ``death`` outcomes; a ``drop``
row of what the corpse was made with; and a ``loot`` row for everything a
player takes back out of it. They share an encounter id (``<boot>-<n>``),
which is the kill id once the mobile dies.

This module joins them into one record per kill and per encounter, then
into per-mobile figures, sliced by player level band, solo or group,
class and gear tier, and compared with the others of the mobile's level
band. The leveling guide, the Oracle, the Gear Finder and
tools/balance_report.py all read this one answer.

Only aggregates leave this module. The rows name characters by number,
never a name, and the numbers are only counted. Since 2026-11-12 the
number is the character's serial (65536 and up, unique: src/save.c);
before it, the file Id (below 65536), which nothing kept unique, so two
characters sharing one read as one in those rows -- in ``characters``,
the farming share and the time between kills. The two ranges never meet,
so an old row is never taken for a new character's, though one character
whose rows span the change counts as two until the old rows age out.

Legacy rows. Before 2026-11-10 a kill wrote one ``kill`` row per player
it paid, and nothing else, so a group kill read as several. A legacy row
is read as a reward, and counts as 1/members of a kill -- exact for a
solo kill, an estimate for a group's -- and every figure built on legacy
rows says how many it rests on (``legacy``).

Columns (tab-separated; the first eleven are every row's):

  0 epoch  1 kind  2 serial (an Id before 2026-11-12)  3 level  4 class  5 remorts  6 hp%  7 mana%
  8 foe vnum  9 foe level  10 area file
  engage: 11 enc  12 foe max hp  13 hp  14 max hp  15 mana  16 max mana
          17 players  18 pets  19 gear tier  20 buffs
  slain:  11 kill  12 ms  13 blow|instant  14 player|pet  15 players
          16 pets  17 foe max hp  18 foe hp lost  19 of it by pets
          20 dealt to players  21 coin carried (copper)  22 rounds
          23 players' melee swings  24 swings that took hp  25 hp by
          spells and skills
  engage also, 21-26: CONSIDER's unasked prediction -- the player's and
          the foe's damage a round, the rounds each would need, the
          verdict, caster
  reward (and legacy kill, to 23 or 24):
          11 ms  12 base xp  13 rested  14 accepted  15 members  16 guild
          17 buffs  18 dealt  19 lost  20 healed  21 mana  22 direct
          23 coin  24 foe max hp  25 kill  26 foes at the kill
          27 gear tier  28 hp at start  29 max hp  30 mana at start
          31 max mana
  flee, death: 11 foe hp%  12 foe max hp  13 hp lost  14 enc
  fled, parted (2026-11-14; the mobile ran, or the fight stopped): a flee
          row's columns, parted then 15 how. Not read here: a chase that
          ends in a kill is the same encounter's slain row.
  drop:   11 kill  12 objects  13 worth  14 top level  15 vnum:source,...
          (legacy, 2026-11-10 only: 11 objects 12 worth 13 top 14 vnums)
  loot:   11 kill  12 coin|obj  13 vnum  14 worth  15 level  16 source
          17 command  18 players
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections import Counter, defaultdict
from itertools import chain, islice
from pathlib import Path
from statistics import median
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# A mobile's figures are trusted only from this many kills, by more than
# one character: one player's lucky night is not a balance finding.
MIN_KILLS = 5
MIN_CHARACTERS = 2
BAND = 5                    # levels per comparison band
GENEROUS = 2.0              # xp/min this many times the band's median
POOR = 0.5                  # ... or this fraction of it
EQUAL_LOW, EQUAL_HIGH = 0.75, 1.33   # "an equal choice" around the median
RISKY = 0.20                # flees and deaths per encounter
EQUAL_CHOICES_WANTED = 3    # a band with fewer comparable foes is a gap
FARMED = 0.80               # one character's share of kills that reads as farming
CYCLE_CAP_S = 600           # a gap longer than this between kills is a break, not downtime
SLICE_MIN = 3               # a slice is shown from this many kills
# CLASS_* in src/merc.h, as the slices name them.
CLASS_NAMES = {0: "mage", 1: "cleric", 2: "thief", 3: "warrior", 4: "monk",
               5: "necromancer", 6: "other"}


def _int(text: str, default: int = 0) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def band_of(level: int) -> Tuple[int, int]:
    low = ((max(1, level) - 1) // BAND) * BAND + 1
    return low, low + BAND - 1


def gear_slice(tier: int, level: int) -> str:
    """Worn gear's average level against the character's: under, par, over."""
    if tier < 0:
        return "bare"
    if tier < level - 10:
        return "under"
    if tier > level + 5:
        return "over"
    return "par"


def quantile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def read_rows(text: str, since: float = 0.0) -> Iterable[List[str]]:
    for raw in text.splitlines():
        f = raw.split("\t")
        # isascii too: str.isdigit() takes Latin-1's superscript digits,
        # which int() then refuses, and an exception mid-fold left the
        # incremental engine half applied (review, 2026-11-13).
        if len(f) < 11 or not (f[0].isascii() and f[0].isdigit()) or int(f[0]) < since:
            continue
        yield f


# --------------------------------------------------------------------
# Rows into records.
# --------------------------------------------------------------------

def _reward(f: List[str], legacy: bool) -> Dict[str, Any]:
    return {
        "epoch": _int(f[0]), "who": f[2], "level": _int(f[3]), "class": _int(f[4]),
        "ms": _int(f[11], -1), "base": max(0, _int(f[12])), "rested": max(0, _int(f[13])),
        "accepted": max(0, _int(f[14])), "members": max(1, _int(f[15], 1)),
        "lost": max(0, _int(f[19])) if len(f) > 19 else 0,
        "coin": _int(f[23]) if len(f) > 23 else 0,
        "foe_hp": _int(f[24]) if len(f) > 24 else 0,
        "kill": f[25] if len(f) > 25 else None,
        "foes": _int(f[26], 1) if len(f) > 26 else 1,
        "gear": _int(f[27], -1) if len(f) > 27 else -1,
        "legacy": legacy,
    }


class _Fold:
    """records() as a left fold over rows, so the rows of a growing file
    can be fed a piece at a time (the dashboard's cache, below) and come
    to exactly what one pass over the whole text gives.

    A list hanging on a kill (its rewards, its loot) is replaced, never
    appended to, so a figure already built from it is never changed under
    a reader. `touched` collects the kill ids whose record a row may have
    changed; `moved` says a row rewrote a kill or an encounter already
    seen, which only a rebuild from the start reproduces exactly."""

    def __init__(self) -> None:
        self.kills: Dict[str, Dict[str, Any]] = {}
        self.rewards: Dict[str, List[Dict[str, Any]]] = {}
        self.drops: Dict[str, Dict[str, Any]] = {}
        self.loots: Dict[str, List[Dict[str, Any]]] = {}
        self.engages: Dict[str, Dict[str, Any]] = {}
        self.outcomes: Dict[str, str] = {}
        self.legacy: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []      # flee and death, keyed or not
        self.legacy_drops: List[Dict[str, Any]] = []
        self.touched: set = set()
        self.moved = False

    def feed(self, f: List[str]) -> None:
        kind, vnum = f[1], _int(f[8], -1)
        if vnum < 0:
            return
        mob = {"vnum": vnum, "mob_level": _int(f[9]), "area": f[10]}
        if kind == "engage" and len(f) > 19:
            if f[11] in self.engages:
                self.moved = True
            self.engages[f[11]] = dict(mob, epoch=_int(f[0]), who=f[2], level=_int(f[3]),
                                       cls=_int(f[4]), players=_int(f[17], 1),
                                       pets=_int(f[18]), gear=_int(f[19], -1))
        elif kind == "slain" and len(f) > 21:
            old = self.kills.get(f[11])
            if old is not None and old["vnum"] != vnum:
                self.moved = True
            self.kills[f[11]] = dict(mob, epoch=_int(f[0]), ms=_int(f[12], -1),
                                     instant=f[13] == "instant", by_pet=f[14] == "pet",
                                     players=max(1, _int(f[15], 1)), pets=_int(f[16]),
                                     foe_hp=_int(f[17]), taken=_int(f[18]),
                                     by_pets=_int(f[19]), dealt=_int(f[20]), coin=_int(f[21]),
                                     who=f[2],
                                     rounds=_int(f[22], -1) if len(f) > 22 else -1,
                                     swings=_int(f[23]) if len(f) > 25 else 0,
                                     landed=_int(f[24]) if len(f) > 25 else 0,
                                     by_skills=_int(f[25]) if len(f) > 25 else 0,
                                     level=_int(f[3]), cls=_int(f[4]))
            self.outcomes[f[11]] = "kill"
            self.touched.add(f[11])
        elif kind == "reward" and len(f) > 25:
            self.rewards[f[25]] = self.rewards.get(f[25], []) + [dict(_reward(f, False), **mob)]
            self.touched.add(f[25])
        elif kind == "kill" and len(f) >= 16:
            self.legacy.append(dict(_reward(f, True), **mob))
        elif kind in ("flee", "death"):
            enc = f[14] if len(f) > 14 else None
            self.events.append(dict(mob, kind=kind, who=f[2], level=_int(f[3]), cls=_int(f[4]),
                                    epoch=_int(f[0]), enc=enc,
                                    foe_pct=_int(f[11], -1) if len(f) > 11 else -1))
            if enc and enc != "-":
                self.outcomes.setdefault(enc, kind)
        elif kind == "drop":
            if len(f) > 15 and "-" in f[11]:
                items = []
                if f[15] != "-":
                    for tok in f[15].split(","):
                        v, _, src = tok.partition(":")
                        if v.isascii() and v.isdigit():
                            items.append((int(v), src or "carried"))
                self.drops[f[11]] = {"count": _int(f[12]), "worth": _int(f[13]),
                                     "top": _int(f[14]), "items": items}
                self.touched.add(f[11])
            elif len(f) > 14:
                self.legacy_drops.append(dict(mob, count=_int(f[11]), worth=_int(f[12]),
                                              items=[(int(v), "carried")
                                                     for v in f[14].split(",") if v.isascii() and v.isdigit()]))
        elif kind == "loot" and len(f) > 17:
            self.loots[f[11]] = self.loots.get(f[11], []) + [
                {"coin": f[12] == "coin", "vnum": _int(f[13]), "worth": _int(f[14]),
                 "source": f[16], "who": f[2]}]
            self.touched.add(f[11])

    def view(self) -> Dict[str, Any]:
        """The records as records() returns them, in containers of their
        own, so feeding more rows never changes a view already given."""
        return {"kills": dict(self.kills), "rewards": defaultdict(list, self.rewards),
                "drops": dict(self.drops), "loots": defaultdict(list, self.loots),
                "engages": dict(self.engages), "outcomes": dict(self.outcomes),
                "legacy": list(self.legacy), "events": list(self.events),
                "legacy_drops": list(self.legacy_drops)}


def records(text: str, since: float = 0.0) -> Dict[str, Any]:
    """Kills, encounters and the rows that hang on them."""
    fold = _Fold()
    for f in read_rows(text, since):
        fold.feed(f)
    return fold.view()


_NO_DROP = {"count": 0, "worth": 0, "items": []}


def _kill_record(kid: str, k: Dict[str, Any], rec: Dict[str, Any]) -> Dict[str, Any]:
    """One kill: its slain row with its rewards, drop and loot joined."""
    rw = rec["rewards"].get(kid, [])
    drop = rec["drops"].get(kid, _NO_DROP)
    loot = rec["loots"].get(kid, [])
    return dict(
        k, kill=kid, weight=1.0, legacy=False, rewards=rw,
        recipients=[r["who"] for r in rw] or [k["who"]],
        levels=[r["level"] for r in rw] or [k["level"]],
        classes=[r["class"] for r in rw] or [k["cls"]],
        gear=[r["gear"] for r in rw],
        solo=k["players"] <= 1 and k["pets"] == 0,
        multi=any(r["foes"] > 1 for r in rw),
        gen_items=drop["count"], gen_worth=drop["worth"], gen_vnums=drop["items"],
        loot_coin=sum(x["worth"] for x in loot if x["coin"]),
        loot_items=sum(1 for x in loot if not x["coin"]),
        loot_worth=sum(x["worth"] for x in loot if not x["coin"]),
        looted=bool(loot),
    )


def _legacy_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """A legacy kill row, at a weight of 1/members."""
    return dict(
        vnum=r["vnum"], mob_level=r["mob_level"], area=r["area"], epoch=r["epoch"],
        ms=r["ms"], instant=r["ms"] < 0, by_pet=False, players=r["members"], pets=0,
        foe_hp=r["foe_hp"], taken=0, by_pets=0, dealt=r["lost"] if r["members"] == 1 else 0,
        coin=r["coin"], who=r["who"], level=r["level"], cls=r["class"],
        kill=None, weight=1.0 / r["members"], legacy=True, rewards=[r],
        recipients=[r["who"]], levels=[r["level"]], classes=[r["class"]], gear=[],
        solo=r["members"] == 1, multi=False, gen_items=0, gen_worth=0, gen_vnums=[],
        loot_coin=0, loot_items=0, loot_worth=0, looted=None,
    )


def kill_records(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One record per kill: the slain row with its rewards, drop and loot
    joined, then legacy kill rows at a weight of 1/members each."""
    out = [_kill_record(kid, k, rec) for kid, k in rec["kills"].items()]
    out += [_legacy_record(r) for r in rec["legacy"]]
    return out


def cycles(rec: Dict[str, Any]) -> Dict[Tuple[str, int], float]:
    """Seconds a paid kill took the same character, per reward: the kill
    and the time between kills -- resting, walking, finding the next one.
    Gaps past CYCLE_CAP_S are a break, not downtime, and none.

    The journal stamps whole seconds, so several kills by one character
    can share an epoch (review, 2026-11-12: two 100-xp kills a second read
    as one a second, half the rate). The time since the character's
    previous second with a kill is shared among that second's kills --
    each gets (b - a) / n -- so the seconds are counted once whatever the
    number of kills, and every reward in the second looks up the same
    share by (who, epoch). Kills in a character's first second, or the
    first after a break, have no previous kill to measure from: none."""
    by_who: Dict[str, Counter] = defaultdict(Counter)
    for rw in list(rec["rewards"].values()):
        for r in rw:
            by_who[r["who"]][r["epoch"]] += 1
    for r in rec["legacy"]:
        by_who[r["who"]][r["epoch"]] += 1
    out: Dict[Tuple[str, int], float] = {}
    for who, counts in by_who.items():
        seconds = sorted(counts)
        for a, b in zip(seconds, seconds[1:]):
            if b - a <= CYCLE_CAP_S:
                out[(who, b)] = float(b - a) / counts[b]
    return out


# --------------------------------------------------------------------
# Records into figures.
# --------------------------------------------------------------------

def figures(kills: List[Dict[str, Any]], events: List[Dict[str, Any]],
            cyc: Dict[Tuple[str, int], float], unresolved: int = 0) -> Dict[str, Any]:
    """The figures for one set of kills of one mobile (or one slice)."""
    weight = sum(k["weight"] for k in kills)
    timed = [k for k in kills if k["ms"] > 0 and not k["instant"]]
    times = [k["ms"] / 1000.0 for k in timed]
    who: Counter = Counter()
    for k in kills:
        for r in k["recipients"]:
            who[r] += k["weight"] / max(1, len(k["recipients"]))
    rewards = [(k, r) for k in kills for r in k["rewards"]]
    per_player_base = [r["base"] for _k, r in rewards]
    capped = sum(1 for _k, r in rewards if r["accepted"] == 0 and r["base"] > 0)
    # Experience a combat minute, per player: what each kill offered each
    # of its recipients, over the kill's own time.
    timed_rewards = [(k, r) for k in timed for r in k["rewards"]]
    player_minutes = sum(k["ms"] for k, _r in timed_rewards) / 60000.0
    xp_per_min = (sum(r["base"] for _k, r in timed_rewards) / player_minutes
                  if player_minutes else 0.0)
    paid = [(k, r) for k, r in timed_rewards if r["accepted"] > 0]
    paid_minutes = sum(k["ms"] for k, _r in paid) / 60000.0
    accepted_per_min = sum(r["accepted"] for _k, r in paid) / paid_minutes if paid_minutes else 0.0
    cyc_times = [cyc[(r["who"], r["epoch"])] for _k, r in rewards
                 if (r["who"], r["epoch"]) in cyc]
    flees = sum(1 for e in events if e["kind"] == "flee")
    deaths = sum(1 for e in events if e["kind"] == "death")
    encounters = weight + flees + deaths
    new = [k for k in kills if not k["legacy"]]
    # A kill's cost in hit points: what the mobile itself took off players
    # (its own ledger, so a melee of several is never one total for all),
    # per player; a legacy row's own ledger only for a solo kill.
    hp_cost = [k["dealt"] / max(1, k["players"]) for k in new]
    hp_cost += [k["dealt"] for k in kills if k["legacy"] and k["solo"] and k["dealt"]]
    gen_coin = sum(k["coin"] * k["weight"] for k in kills)
    looted_coin = sum(k["loot_coin"] for k in new)
    kill_xp = median(per_player_base) if per_player_base else 0.0
    cycle = median(cyc_times) if cyc_times else None
    kill_s = median(times) if times else None
    loop = max(cycle or 0.0, kill_s or 0.0) or None
    top_share = (max(who.values()) / sum(who.values())) if who else 0.0
    return {
        "kills": int(weight) if weight == int(weight) else round(weight, 2),
        "samples": len(kills),
        "legacy": sum(1 for k in kills if k["legacy"]),
        "characters": len(who),
        "median_seconds": kill_s,
        "p25_seconds": quantile(times, 0.25),
        "p75_seconds": quantile(times, 0.75),
        "instant": sum(1 for k in kills if k["instant"]),
        "xp_per_kill": kill_xp,
        "xp_per_min": xp_per_min,
        "accepted_xp_per_min": accepted_per_min,
        "capped_share": capped / len(rewards) if rewards else 0.0,
        "cycle_seconds": cycle,
        "xp_per_hour": kill_xp * 3600.0 / loop if loop else 0.0,
        "coin_generated_per_kill": gen_coin / weight if weight else 0.0,
        "coin_looted_per_kill": looted_coin / len(new) if new else None,
        "coin_per_hour": (looted_coin / len(new)) * 3600.0 / loop if new and loop else None,
        "drop_rate": (sum(1 for k in new if k["gen_items"] > 0) / len(new)) if new else None,
        "gear_generated_per_kill": sum(k["gen_worth"] for k in new) / len(new) if new else None,
        "gear_looted_per_kill": sum(k["loot_worth"] for k in new) / len(new) if new else None,
        "unlooted_share": (sum(1 for k in new if (k["gen_items"] or k["coin"]) and not k["looted"])
                           / len(new)) if new else None,
        "hp_lost_per_kill": median(hp_cost) if hp_cost else 0.0,
        "flees": flees, "deaths": deaths, "unresolved": unresolved,
        "risk": (flees + deaths) / encounters if encounters else 0.0,
        "multi_foe_share": sum(1 for k in new if k["multi"]) / len(new) if new else 0.0,
        "hit_rate": (sum(k.get("landed", 0) for k in new) / sum(k.get("swings", 0) for k in new))
                    if sum(k.get("swings", 0) for k in new) else None,
        "skill_share": (sum(k.get("by_skills", 0) for k in new) / sum(k["taken"] for k in new))
                       if sum(k["taken"] for k in new) else None,
        "group_share": sum(1 for k in kills if not k["solo"]) / len(kills) if kills else 0.0,
        "top_player_share": top_share,
        "farmed": len(who) >= 2 and top_share >= FARMED,
        "foe_hp": median([k["foe_hp"] for k in kills if k["foe_hp"] > 0] or [0]),
        "player_level": median([lv for k in kills for lv in k["levels"]]) if kills else None,
        "trusted": weight >= MIN_KILLS and len(who) >= MIN_CHARACTERS,
    }


def summarize(text: str, since: float = 0.0) -> Dict[str, Any]:
    """The joined records, grouped by mobile."""
    rec = records(text, since)
    kills = kill_records(rec)
    by_vnum: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"kills": [], "events": []})
    for k in kills:
        by_vnum[k["vnum"]]["kills"].append(k)
        by_vnum[k["vnum"]].setdefault("meta", (k["mob_level"], k["area"]))
    for e in rec["events"]:
        by_vnum[e["vnum"]]["events"].append(e)
        by_vnum[e["vnum"]].setdefault("meta", (e["mob_level"], e["area"]))
    unresolved: Counter = Counter()
    for enc, e in rec["engages"].items():
        by_vnum[e["vnum"]].setdefault("meta", (e["mob_level"], e["area"]))
        if enc not in rec["outcomes"]:
            unresolved[e["vnum"]] += 1
    seen: Counter = Counter()
    for k in kills:
        for v, _src in k["gen_vnums"]:
            seen[v] += 1
    for d in rec["legacy_drops"]:
        for v, _src in d["items"]:
            seen[v] += 1
    return {"by_vnum": dict(by_vnum), "unresolved": unresolved, "seen": seen,
            "cycles": cycles(rec), "records": rec}


def _slices(kills, cyc) -> Dict[str, Dict[str, Any]]:
    """By player level band, solo or group, class and gear tier: each a
    figure set once it holds SLICE_MIN kills."""
    groups: Dict[str, List] = defaultdict(list)
    for k in kills:
        lv = int(median(k["levels"])) if k["levels"] else k["level"]
        lo, hi = band_of(lv)
        groups[f"level {lo}-{hi}"].append(k)
        groups["solo" if k["solo"] else "group"].append(k)
        for c in set(k["classes"]):
            groups[f"class {CLASS_NAMES.get(c, c)}"].append(k)
        for g in {gear_slice(g, lv) for g, lv in zip(k["gear"], k["levels"])}:
            groups[f"gear {g}"].append(k)
    out = {}
    for name, ks in groups.items():
        if sum(k["weight"] for k in ks) >= SLICE_MIN:
            out[name] = figures(ks, [], cyc)
    return out


def compare(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Every mobile's figures and slices, then each band's: its median
    xp/min and coin per kill among trusted mobiles, each one's ratio to
    them, the findings (generous, poor, risky, rich, farmed) and how many
    equal choices the band offers."""
    cyc = summary["cycles"]
    mobs: Dict[int, Dict[str, Any]] = {}
    for vnum, data in summary["by_vnum"].items():
        mobs[vnum] = _mob_entry(vnum, data, cyc, summary["unresolved"].get(vnum, 0))
    return {"mobs": mobs, "bands": _band_pass(mobs), "seen": summary["seen"],
            "summary": summary}


def _mob_entry(vnum: int, data: Dict[str, Any], cyc: Dict[Tuple[str, int], float],
               unresolved: int) -> Dict[str, Any]:
    """One mobile's figures and slices, before its band is read."""
    level, area = data.get("meta", (0, "-"))
    m = figures(data["kills"], data["events"], cyc, unresolved)
    m.update(level=level, area=area, vnum=vnum)
    m["slices"] = _slices(data["kills"], cyc)
    dropped: Counter = Counter()
    for k in data["kills"]:
        for v, _src in k["gen_vnums"]:
            dropped[v] += 1
    m["dropped"] = dict(dropped.most_common(5))
    return m


def _band_pass(mobs: Dict[int, Dict[str, Any]]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Each band's medians, and every mobile's ratio and flags against its
    band (written into the mobile's figures)."""
    bands: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for vnum, m in mobs.items():
        b = bands.setdefault(band_of(m["level"] or 1), {"mobs": [], "trusted": []})
        b["mobs"].append(vnum)
        if m["trusted"] and m["xp_per_min"] > 0:
            b["trusted"].append(vnum)
    for (low, high), b in bands.items():
        rates = [mobs[v]["xp_per_min"] for v in b["trusted"]]
        coins = [mobs[v]["coin_generated_per_kill"] for v in b["trusted"]]
        b["median_xp_per_min"] = median(rates) if rates else 0.0
        b["median_coin"] = median(coins) if coins else 0.0
        equal = []
        for v in b["mobs"]:
            m = mobs[v]
            m["ratio"] = (m["xp_per_min"] / b["median_xp_per_min"]
                          if b["median_xp_per_min"] else 0.0)
            flags = []
            if v in b["trusted"]:
                if len(rates) >= 2 and m["ratio"] >= GENEROUS:
                    flags.append("generous")
                if len(rates) >= 2 and m["ratio"] <= POOR:
                    flags.append("poor")
                if m["risk"] >= RISKY:
                    flags.append("risky")
                if b["median_coin"] and m["coin_generated_per_kill"] >= 3 * b["median_coin"]:
                    flags.append("rich")
                if m["farmed"]:
                    flags.append("farmed")
                if EQUAL_LOW <= m["ratio"] <= EQUAL_HIGH and m["risk"] < RISKY:
                    equal.append(v)
            m["flags"] = flags
        b["equal"] = equal
        b["gap"] = len(equal) < EQUAL_CHOICES_WANTED
    return bands


def band_choices(b: Dict[str, Any],
                 reachable: Optional[Callable[[int], bool]] = None) -> Tuple[List[int], bool]:
    """A band's equal choices a player can actually take -- reachable
    ordinary prey, when the world was read -- and whether that is a gap.
    The band's own "gap" counts every equal mobile, a Hyrule guardian or
    one in an area nothing leads to included; three equal mobiles of which
    one is reachable are one choice, and a gap (review, 2026-11-12). Every
    reader -- the proposals, the report's bands and its JSON -- asks this."""
    choices = [v for v in b["equal"] if reachable is None or reachable(v)]
    return choices, len(choices) < EQUAL_CHOICES_WANTED


def confidence(m: Dict[str, Any]) -> str:
    if m["kills"] >= 30 and m["characters"] >= 3 and m["legacy"] < m["samples"] / 2:
        return "high"
    if m["kills"] >= 10 and m["characters"] >= 2:
        return "medium"
    return "low"


def proposals(result: Dict[str, Any], names: Optional[Callable[[int], str]] = None,
              reachable: Optional[Callable[[int], bool]] = None) -> List[Dict[str, Any]]:
    """Manual balance changes worth considering, each with its evidence
    and a confidence. Nothing here edits a mobile: it is a list to read."""
    name = names or (lambda v: f"mob {v}")
    out = []
    for (low, high), b in sorted(result["bands"].items()):
        for v in b["mobs"]:
            m = result["mobs"][v]
            if not m["trusted"] or (reachable is not None and not reachable(v)):
                continue
            ev = (f"{m['kills']:g} kills by {m['characters']} characters; "
                  f"{m['xp_per_min']:.0f} xp/min against the band's "
                  f"{b['median_xp_per_min']:.0f}; risk {m['risk']:.0%}")
            if m["legacy"]:
                ev += f"; {m['legacy']} legacy rows"
            for flag, what in (
                    ("generous", "pays far over its band: lower its experience (level) or raise its "
                                 "hit points, or add peers so it is not the only farm"),
                    ("poor", "pays far under its band: raise its level or lower its hit points, "
                             "or leave it as scenery"),
                    ("risky", "sends players running or kills them: lower its damage or warn "
                              "in its description"),
                    ("rich", "carries far more coin than its band: check its wealth figure"),
                    ("farmed", "one character takes most of its kills: read their log before "
                               "changing anything")):
                if flag in m["flags"]:
                    out.append({"vnum": v, "name": name(v), "band": f"{low}-{high}",
                                "finding": flag, "proposal": what, "evidence": ev,
                                "confidence": confidence(m)})
        choices, gap = band_choices(b, reachable)
        if gap:
            out.append({"vnum": None, "name": "-", "band": f"{low}-{high}", "finding": "gap",
                        "proposal": ("too few comparable places to level: add or retune "
                                     "mobiles here so there are at least "
                                     f"{EQUAL_CHOICES_WANTED}"),
                        "evidence": (f"{len(choices)} equal choice(s) among "
                                     f"{len(b['trusted'])} trusted mobile(s), "
                                     f"{len(b['mobs'])} fought"),
                        "confidence": "medium" if len(b["trusted"]) >= 3 else "low"})
    return out


# --------------------------------------------------------------------
# The dashboard's view: the live file, kept up to date as it grows.
# --------------------------------------------------------------------
#
# The game appends to log/progress.tsv on every fight and, past
# PROGRESS_MAX lines, rewrites it to the newest PROGRESS_KEEP through a
# temporary file and a rename (progress_trim in src/playlog.c). Reading
# and reparsing the whole feed after every append cost the dashboard most
# of a second a request on a full feed, on the event loop. Now:
#
#   * an unchanged file (same device, inode, size and mtime) is the last
#     answer, untouched;
#   * a file that only grew is read from where the last read stopped, and
#     only the mobiles the new rows touch are figured again (_Engine) --
#     the same functions in the same order, so the answer is exactly what
#     compare(summarize(text)) gives for the same complete lines;
#   * anything else -- another inode (the trim's rename), a shorter file,
#     a first or last 64 bytes that are not what was read (a rewrite in
#     place), a row that rewrites a kill or an encounter already seen --
#     is read again from the start.
#
# A last line with no newline yet is a row the game is still writing: it
# is carried, never read, until its newline arrives (a torn row read as
# numbers would skew a figure). One lock serialises it, so requests that
# arrive together share one parse; the async routes call load_async(),
# which runs it off the event loop.

def _empty() -> Dict[str, Any]:
    return {"mobs": {}, "bands": {}, "seen": Counter(), "summary": None}


def _rows_of(data: bytes) -> Iterable[List[str]]:
    return read_rows(data.decode("latin-1"))


class _Engine:
    """compare(summarize(...)) kept up to date, batch of rows by batch."""

    def __init__(self) -> None:
        self.fold = _Fold()
        self.kill_rec: Dict[str, Dict[str, Any]] = {}
        self.kids_by_vnum: Dict[int, List[str]] = defaultdict(list)
        self.legacy_by_vnum: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.events_by_vnum: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.engage_meta: Dict[int, Tuple[int, str]] = {}
        self.cyc_kids: Dict[Tuple[str, int], set] = defaultdict(set)
        self.cyc_legacy: Dict[Tuple[str, int], set] = defaultdict(set)
        self.cycles: Dict[Tuple[str, int], float] = {}
        self.unresolved: Counter = Counter()
        self.data: Dict[int, Dict[str, Any]] = {}
        self.entry: Dict[int, Dict[str, Any]] = {}
        self.result: Dict[str, Any] = _empty()
        self.fresh = True

    def apply(self, rows: Iterable[List[str]]) -> bool:
        """Fold the rows in and figure again what they touched. False when
        a row rewrote a kill or an encounter from an earlier batch: only a
        rebuild from the start gives the same answer then."""
        fold = self.fold
        n_kills, n_legacy = len(fold.kills), len(fold.legacy)
        n_events, n_engages = len(fold.events), len(fold.engages)
        fold.touched, fold.moved = set(), False
        count = 0
        for f in rows:
            fold.feed(f)
            count += 1
        if fold.moved and not self.fresh:
            return False
        if count == 0 and not self.fresh:
            return True
        dirty: set = set()
        rec = {"rewards": fold.rewards, "drops": fold.drops, "loots": fold.loots}
        for kid in islice(fold.kills, n_kills, None):
            self.kids_by_vnum[fold.kills[kid]["vnum"]].append(kid)
        for kid in fold.touched:
            for r in fold.rewards.get(kid, ()):
                self.cyc_kids[(r["who"], r["epoch"])].add(kid)
            k = fold.kills.get(kid)
            if k is not None:
                self.kill_rec[kid] = _kill_record(kid, k, rec)
                dirty.add(k["vnum"])
        for r in fold.legacy[n_legacy:]:
            self.legacy_by_vnum[r["vnum"]].append(_legacy_record(r))
            self.cyc_legacy[(r["who"], r["epoch"])].add(r["vnum"])
            dirty.add(r["vnum"])
        for e in fold.events[n_events:]:
            self.events_by_vnum[e["vnum"]].append(e)
            dirty.add(e["vnum"])
        for enc in islice(fold.engages, n_engages, None):
            e = fold.engages[enc]
            self.engage_meta.setdefault(e["vnum"], (e["mob_level"], e["area"]))
            if e["vnum"] not in self.data:
                dirty.add(e["vnum"])
        # The time between kills is the whole feed's: figure it again, and
        # every mobile one of whose rewards it changed for.
        cyc = cycles({"rewards": fold.rewards, "legacy": fold.legacy})
        unresolved: Counter = Counter()
        for enc, e in fold.engages.items():
            if enc not in fold.outcomes:
                unresolved[e["vnum"]] += 1
        if not self.fresh:      # a first build figures every mobile anyway
            for key in cyc.keys() | self.cycles.keys():
                if cyc.get(key) != self.cycles.get(key):
                    dirty.update(self.kill_rec[k]["vnum"] for k in self.cyc_kids.get(key, ())
                                 if k in self.kill_rec)
                    dirty.update(self.cyc_legacy.get(key, ()))
            for v in unresolved.keys() | self.unresolved.keys():
                if unresolved.get(v, 0) != self.unresolved.get(v, 0):
                    dirty.add(v)
        # summarize()'s order: kills, then legacy rows, events, encounters.
        order = dict.fromkeys(chain((k["vnum"] for k in fold.kills.values()),
                                    (r["vnum"] for r in fold.legacy),
                                    (e["vnum"] for e in fold.events),
                                    (e["vnum"] for e in fold.engages.values())))
        if self.fresh:
            dirty = set(order)
        for v in dirty:
            if v not in order:
                continue
            kills = ([self.kill_rec[k] for k in self.kids_by_vnum.get(v, ())]
                     + list(self.legacy_by_vnum.get(v, ())))
            events = list(self.events_by_vnum.get(v, ()))
            if kills:
                meta = (kills[0]["mob_level"], kills[0]["area"])
            elif events:
                meta = (events[0]["mob_level"], events[0]["area"])
            else:
                meta = self.engage_meta[v]
            data = {"kills": kills, "events": events, "meta": meta}
            self.data[v] = data
            self.entry[v] = _mob_entry(v, data, cyc, unresolved.get(v, 0))
        seen: Counter = Counter()
        for k in self.kill_rec.values():
            for v, _src in k["gen_vnums"]:
                seen[v] += 1
        for d in fold.legacy_drops:
            for v, _src in d["items"]:
                seen[v] += 1
        # Fresh containers each time, so a result already handed out is
        # never changed under its reader.
        mobs = {v: dict(self.entry[v]) for v in order}
        summary = {"by_vnum": {v: self.data[v] for v in order}, "unresolved": unresolved,
                   "seen": seen, "cycles": cyc, "records": fold.view()}
        self.cycles, self.unresolved = cyc, unresolved
        self.result = {"mobs": mobs, "bands": _band_pass(mobs), "seen": seen,
                       "summary": summary}
        self.fresh = False
        return True


_CHECK = 64             # bytes at each end of what was read, compared before growing
_STATES_MAX = 4         # files kept at once (the live feed, and a test's or two)
_LOCK = threading.Lock()
_STATES: Dict[str, "_FeedState"] = {}
STATS: Counter = Counter()      # "full", "grow", "same": how each load was answered


class _FeedState:
    def __init__(self) -> None:
        self.ident: Tuple[int, int] = (-1, -1)
        self.mtime_ns = -1
        self.consumed = 0       # bytes read, the carry included
        self.carry = b""        # a last line with no newline yet
        self.head = b""
        self.tail = b""
        self.engine = _Engine()


def _full(path: Path, st: os.stat_result) -> Dict[str, Any]:
    with open(path, "rb") as fh:
        data = fh.read()
    s = _FeedState()
    cut = data.rfind(b"\n") + 1
    s.engine.apply(_rows_of(data[:cut]))
    s.ident, s.mtime_ns = (st.st_dev, st.st_ino), st.st_mtime_ns
    s.consumed, s.carry = len(data), data[cut:]
    s.head, s.tail = data[:_CHECK], data[-_CHECK:]
    _STATES.pop(str(path), None)
    _STATES[str(path)] = s
    while len(_STATES) > _STATES_MAX:
        _STATES.pop(next(iter(_STATES)))
    STATS["full"] += 1
    return s.engine.result


def _grow(path: Path, st: os.stat_result, s: _FeedState) -> Optional[Dict[str, Any]]:
    """Read what was appended; None when the file is not the one read."""
    with open(path, "rb") as fh:
        if fh.read(len(s.head)) != s.head:
            return None
        fh.seek(s.consumed - len(s.tail))
        if fh.read(len(s.tail)) != s.tail:
            return None
        new = fh.read()
    data = s.carry + new
    cut = data.rfind(b"\n") + 1
    if not s.engine.apply(_rows_of(data[:cut])):
        return None
    s.carry = data[cut:]
    s.consumed += len(new)
    if len(s.head) < _CHECK:
        s.head = (s.head + new)[:_CHECK]
    s.tail = (s.tail + new)[-_CHECK:]
    s.mtime_ns = st.st_mtime_ns
    STATS["grow"] += 1
    return s.engine.result


def load(path: Path) -> Dict[str, Any]:
    """Every mobile's figures and every band's, from the feed at `path`."""
    with _LOCK:
        try:
            st = os.stat(path)
        except OSError:
            _STATES.pop(str(path), None)
            return _empty()
        s = _STATES.get(str(path))
        try:
            if s is not None and s.ident == (st.st_dev, st.st_ino) \
                    and st.st_size >= s.consumed:
                if st.st_size == s.consumed and st.st_mtime_ns == s.mtime_ns:
                    STATS["same"] += 1
                    return s.engine.result
                got = _grow(path, st, s)
                if got is not None:
                    return got
            return _full(path, st)
        except OSError:
            _STATES.pop(str(path), None)
            return _empty()
        except Exception:
            # A row nothing writes broke the fold part way: start again
            # from the file rather than fold the same rows a second time.
            _STATES.pop(str(path), None)
            try:
                return _full(path, st)
            except Exception:
                return _empty()


async def load_async(path: Path) -> Dict[str, Any]:
    """load(), off the event loop: a full parse of a long feed takes a
    while, and the dashboard's other routes must answer meanwhile."""
    return await asyncio.to_thread(load, path)


def version(path: Path) -> str:
    """Which feed an answer was given from: anything built on these
    figures (the Oracle's cached leveling and gear advice) keys on it, so
    a new row retires it. One stat, no read."""
    try:
        st = os.stat(path)
    except OSError:
        return "none"
    return "%d.%d.%d.%d" % (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


def _loaded(source: Any) -> Dict[str, Any]:
    """A loaded result as it is, or the feed at a path, loaded."""
    return source if isinstance(source, dict) else load(source)


def observed(source: Any, vnum: int) -> Optional[Dict[str, Any]]:
    """A mobile's figures if players have killed it enough to trust them.
    `source` is the feed's path or what load() returned for it."""
    m = _loaded(source)["mobs"].get(vnum)
    return m if m and m["trusted"] else None


def near(source: Any, vnum: int, level: int, spread: int = 5) -> Optional[Dict[str, Any]]:
    """A mobile as players within `spread` levels of `level` found it --
    a level 1 and a level 20 do not take the same time over a goblin --
    or None below MIN_KILLS such kills by MIN_CHARACTERS characters.
    `source` is the feed's path or what load() returned for it."""
    summary = _loaded(source).get("summary")
    if not summary:
        return None
    data = summary["by_vnum"].get(vnum)
    if not data:
        return None
    kills = [k for k in data["kills"]
             if k["levels"] and abs(median(k["levels"]) - level) <= spread]
    events = [e for e in data["events"] if abs(e["level"] - level) <= spread]
    if not kills:
        return None
    m = figures(kills, events, summary["cycles"])
    if m["kills"] < MIN_KILLS or m["characters"] < MIN_CHARACTERS or not m["median_seconds"]:
        return None
    return m


def seen_drops(source: Any) -> Counter:
    """How often each object vnum has fallen from a kill a player made.
    `source` is the feed's path or what load() returned for it."""
    return _loaded(source).get("seen") or Counter()
