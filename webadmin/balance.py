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
  drop:   11 kill  12 objects  13 worth  14 top level  15 vnum:source,...
          (legacy, 2026-11-10 only: 11 objects 12 worth 13 top 14 vnums)
  loot:   11 kill  12 coin|obj  13 vnum  14 worth  15 level  16 source
          17 command  18 players
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
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
        if len(f) < 11 or not f[0].isdigit() or int(f[0]) < since:
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


def records(text: str, since: float = 0.0) -> Dict[str, Any]:
    """Kills, encounters and the rows that hang on them."""
    kills: Dict[str, Dict[str, Any]] = {}
    rewards: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    drops: Dict[str, Dict[str, Any]] = {}
    loots: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    engages: Dict[str, Dict[str, Any]] = {}
    outcomes: Dict[str, str] = {}
    legacy: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []      # flee and death, keyed or not
    legacy_drops: List[Dict[str, Any]] = []
    for f in read_rows(text, since):
        kind, vnum = f[1], _int(f[8], -1)
        if vnum < 0:
            continue
        mob = {"vnum": vnum, "mob_level": _int(f[9]), "area": f[10]}
        if kind == "engage" and len(f) > 19:
            engages[f[11]] = dict(mob, epoch=_int(f[0]), who=f[2], level=_int(f[3]),
                                  cls=_int(f[4]), players=_int(f[17], 1), pets=_int(f[18]),
                                  gear=_int(f[19], -1))
        elif kind == "slain" and len(f) > 21:
            kills[f[11]] = dict(mob, epoch=_int(f[0]), ms=_int(f[12], -1),
                                instant=f[13] == "instant", by_pet=f[14] == "pet",
                                players=max(1, _int(f[15], 1)), pets=_int(f[16]),
                                foe_hp=_int(f[17]), taken=_int(f[18]), by_pets=_int(f[19]),
                                dealt=_int(f[20]), coin=_int(f[21]), who=f[2],
                                rounds=_int(f[22], -1) if len(f) > 22 else -1,
                                swings=_int(f[23]) if len(f) > 25 else 0,
                                landed=_int(f[24]) if len(f) > 25 else 0,
                                by_skills=_int(f[25]) if len(f) > 25 else 0,
                                level=_int(f[3]), cls=_int(f[4]))
            outcomes[f[11]] = "kill"
        elif kind == "reward" and len(f) > 25:
            rewards[f[25]].append(dict(_reward(f, False), **mob))
        elif kind == "kill" and len(f) >= 16:
            legacy.append(dict(_reward(f, True), **mob))
        elif kind in ("flee", "death"):
            enc = f[14] if len(f) > 14 else None
            events.append(dict(mob, kind=kind, who=f[2], level=_int(f[3]), cls=_int(f[4]),
                               epoch=_int(f[0]), enc=enc,
                               foe_pct=_int(f[11], -1) if len(f) > 11 else -1))
            if enc and enc != "-":
                outcomes.setdefault(enc, kind)
        elif kind == "drop":
            if len(f) > 15 and "-" in f[11]:
                items = []
                if f[15] != "-":
                    for tok in f[15].split(","):
                        v, _, src = tok.partition(":")
                        if v.isdigit():
                            items.append((int(v), src or "carried"))
                drops[f[11]] = {"count": _int(f[12]), "worth": _int(f[13]),
                                "top": _int(f[14]), "items": items}
            elif len(f) > 14:
                legacy_drops.append(dict(mob, count=_int(f[11]), worth=_int(f[12]),
                                         items=[(int(v), "carried") for v in f[14].split(",")
                                                if v.isdigit()]))
        elif kind == "loot" and len(f) > 17:
            loots[f[11]].append({"coin": f[12] == "coin", "vnum": _int(f[13]),
                                 "worth": _int(f[14]), "source": f[16], "who": f[2]})
    return {"kills": kills, "rewards": rewards, "drops": drops, "loots": loots,
            "engages": engages, "outcomes": outcomes, "legacy": legacy,
            "events": events, "legacy_drops": legacy_drops}


def kill_records(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One record per kill: the slain row with its rewards, drop and loot
    joined, then legacy kill rows at a weight of 1/members each."""
    out = []
    for kid, k in rec["kills"].items():
        rw = rec["rewards"].get(kid, [])
        drop = rec["drops"].get(kid, {"count": 0, "worth": 0, "items": []})
        loot = rec["loots"].get(kid, [])
        out.append(dict(
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
        ))
    for r in rec["legacy"]:
        out.append(dict(
            vnum=r["vnum"], mob_level=r["mob_level"], area=r["area"], epoch=r["epoch"],
            ms=r["ms"], instant=r["ms"] < 0, by_pet=False, players=r["members"], pets=0,
            foe_hp=r["foe_hp"], taken=0, by_pets=0, dealt=r["lost"] if r["members"] == 1 else 0,
            coin=r["coin"], who=r["who"], level=r["level"], cls=r["class"],
            kill=None, weight=1.0 / r["members"], legacy=True, rewards=[r],
            recipients=[r["who"]], levels=[r["level"]], classes=[r["class"]], gear=[],
            solo=r["members"] == 1, multi=False, gen_items=0, gen_worth=0, gen_vnums=[],
            loot_coin=0, loot_items=0, loot_worth=0, looted=None,
        ))
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
        level, area = data.get("meta", (0, "-"))
        m = figures(data["kills"], data["events"], cyc, summary["unresolved"].get(vnum, 0))
        m.update(level=level, area=area, vnum=vnum)
        m["slices"] = _slices(data["kills"], cyc)
        dropped: Counter = Counter()
        for k in data["kills"]:
            for v, _src in k["gen_vnums"]:
                dropped[v] += 1
        m["dropped"] = dict(dropped.most_common(5))
        mobs[vnum] = m
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
    return {"mobs": mobs, "bands": bands, "seen": summary["seen"], "summary": summary}


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
        if b["gap"]:
            choices = [v for v in b["equal"] if reachable is None or reachable(v)]
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
# The dashboard's view: the live file, cached by its identity and size.
# --------------------------------------------------------------------

def _empty() -> Dict[str, Any]:
    return {"mobs": {}, "bands": {}, "seen": Counter(), "summary": None}


_CACHE: Dict[str, Any] = {"key": None, "value": None}


def load(path: Path) -> Dict[str, Any]:
    try:
        st = os.stat(path)
    except OSError:
        return _empty()
    key = (str(path), st.st_ino, st.st_size, int(st.st_mtime))
    if _CACHE["key"] == key and _CACHE["value"] is not None:
        return _CACHE["value"]
    try:
        text = Path(path).read_text(encoding="latin-1")
    except OSError:
        return _empty()
    value = compare(summarize(text))
    _CACHE["key"], _CACHE["value"] = key, value
    return value


def observed(path: Path, vnum: int) -> Optional[Dict[str, Any]]:
    """A mobile's figures if players have killed it enough to trust them."""
    m = load(path)["mobs"].get(vnum)
    return m if m and m["trusted"] else None


def near(path: Path, vnum: int, level: int, spread: int = 5) -> Optional[Dict[str, Any]]:
    """A mobile as players within `spread` levels of `level` found it --
    a level 1 and a level 20 do not take the same time over a goblin --
    or None below MIN_KILLS such kills by MIN_CHARACTERS characters."""
    summary = load(path).get("summary")
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


def seen_drops(path: Path) -> Counter:
    """How often each object vnum has fallen from a kill a player made."""
    return load(path).get("seen") or Counter()
