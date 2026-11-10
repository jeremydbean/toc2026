"""Wearable gear the game makes at run time, with no reset behind it.

The Gear Finder (get_best_gear in server.py) and the Oracle read the area
files, and an area file only says what a reset puts on a mobile, in a room
or in a chest. Some gear is made only when something dies: a Hyrule
guardian's drop table, Ganon's relic, the boomerangs a cleared room lays
out, a holiday boss's drops and the rarities in a treasure goblin's sack.
Without these tables the finder never saw them (review, 2026-11-10: the
Aquamentus coat and helm, 30650 and 30651, were missing from a level 25
warrior's list though any player who kills Aquamentus may find them).

Every number here mirrors the C that makes the item, and
tests/test_gear_drop_sources.py holds each table to its source -- the C
arrays, merc.h and the Hyrule generator -- so a change there that is not
made here fails a test rather than quietly misleading the finder:

- hyrule_boss_drops() in src/hyrule.c: three distinct pieces drawn at
  random from the guardian's table of five plus hyrule_boss_extra_drops[]
  (BOSS_DROPS and BOSS_EXTRA_DROPS in scripts/build_hyrule_area.py).
- hyrule_ganon_loot_vnums[] in src/fight.c: one relic of three in Ganon's
  corpse.
- hyrule_clear_rewards[] in src/hyrule.c: the two boomerangs (the only
  wearable rewards) appear when their room's last enemy dies.
- hyrule_progress_gate[] in src/act_move.c: what a dungeon's entrance and
  its guardian's chamber ask for (ENTRY_NEEDS, GUARDIAN_NEEDS and
  GUARDIAN_ALSO in the generator), and TOOL_SOURCES for where each tool
  lies. Ganon is finished only with the Silver Arrow (damage() in fight.c).
- event_boss_drops() in src/season.c: the Headless Horseman and Father
  Winter, in the Oak Tree Square during their holiday only.
- holiday_corpse_drop() in src/holiday.c: the one treat that is worn (held)
  is Midsummer's firework.
- black_market_rarity() in src/blackmarket.c, as the treasure goblin
  (src/goblin.c) and the black dragon (src/disaster.c) roll it, and the
  black market's own stocks. Their ordinary gear --
  black_market_gear_for_level() -- is the best piece the world places on
  a mobile, already a reset item the finder counts; it is not added again.

A holiday's items are offered only in that holiday (see offered()); the
rarer year-round ways to them are named beside the holiday source.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

# merc.h and hyrule_boss_drops() in src/hyrule.c.
BOSS_DROP_FIRST = 30650             # OBJ_VNUM_HYRULE_BOSS_DROP_FIRST
BOSS_DROPS_PER_GUARDIAN = 5         # HYRULE_BOSS_DROPS_PER_GUARDIAN
BOSS_DROPS_PER_KILL = 3             # HYRULE_BOSS_DROPS_PER_KILL
BOSS_EXTRA_FIRST = 30700            # OBJ_VNUM_HYRULE_BOSS_EXTRA_FIRST
BOSS_EXTRA_STRIDE = 7               # HYRULE_BOSS_EXTRA_STRIDE

# hyrule_guardian_vnums[] and hyrule_boss_extra_drops[] in src/hyrule.c,
# dungeon by dungeon (Level 1 first).
GUARDIAN_VNUMS = (30222, 30218, 30305, 30307, 30309, 30223, 30314, 30316, 30225)
GUARDIAN_EXTRA_DROPS = (6, 6, 6, 6, 6, 6, 6, 6, 5)
GANON_VNUM = 30225                  # HYRULE_GANON_VNUM

# hyrule_ganon_loot_vnums[] in src/fight.c: one of these in Ganon's corpse.
GANON_LOOT = (30577, 30580, 30581)

# hyrule_progress_gate[] in src/act_move.c, by dungeon: the object its
# entrance asks for, the tool its guardian's chamber asks for, and the
# other tool that will also do (0 for none).
HYRULE_GATES = {
    1: (0, 0, 0),
    2: (30400, 30232, 30410),
    3: (30401, 30410, 0),
    4: (30402, 30411, 0),
    5: (30403, 30412, 0),
    6: (30404, 30222, 0),
    7: (30405, 30413, 0),
    8: (30406, 30414, 0),
    9: (30407, 30416, 0),
}
# The dungeon each of those lies in: a Triforce piece in the previous
# dungeon's chest (CHEST_PRIZES), a tool where TOOL_SOURCES puts it.
HYRULE_FOUND_IN = {
    30400: 1, 30401: 2, 30402: 3, 30403: 4, 30404: 5, 30405: 6, 30406: 7,
    30407: 8,
    30232: 1, 30222: 1, 30410: 2, 30411: 3, 30412: 4, 30413: 5, 30414: 7,
    30416: 8, 30218: 9,
}
SILVER_ARROW = 30218                # OBJ_VNUM_HYRULE_SILVER_ARROW: finishes Ganon
# The dungeons' titles (data/hyrule_first_quest.json).
DUNGEON_TITLES = {
    1: "The Eagle", 2: "The Moon", 3: "The Manji", 4: "The Snake",
    5: "The Lizard", 6: "The Dragon", 7: "The Demon", 8: "The Lion",
    9: "Death Mountain",
}

# hyrule_clear_rewards[] in src/hyrule.c, the wearable rows: object ->
# (dungeon, room). The rest are small keys, maps and compasses.
CLEAR_REWARD_GEAR = {30232: (1, 30410), 30410: (2, 30427)}

# event_boss_drops() in src/season.c: (vnum, percent, role). A boss comes to
# EVENT_BOSS_SPAWN_ROOM only while its holiday is on (tick_event_boss), and
# the holiday's dates are its row in holidays[] in src/holiday.c.
EVENT_BOSS_ROOM = 2401
EVENT_DROP_PRIMARY, EVENT_DROP_FALLBACK, EVENT_DROP_RARE = 0, 1, 2
EVENT_BOSSES = {
    29910: ("Hallows End", (10, 18), (11, 1), (
        (29920, 50, EVENT_DROP_PRIMARY),
        (29921, 50, EVENT_DROP_PRIMARY),
        (29924, 75, EVENT_DROP_FALLBACK),
        (29926, 5, EVENT_DROP_RARE),
    )),
    29911: ("Winter Veil", (12, 16), (1, 6), (
        (29922, 50, EVENT_DROP_PRIMARY),
        (29923, 50, EVENT_DROP_PRIMARY),
        (29925, 75, EVENT_DROP_FALLBACK),
        (29927, 5, EVENT_DROP_RARE),
    )),
}

# holiday_corpse_drop() in src/holiday.c: the treats that are worn, with
# their holiday, its dates and the percent of mobile kills that drop one.
HOLIDAY_TREATS = {
    29825: ("the Midsummer Fire Festival", (6, 21), (7, 5), 8),
}

# black_market_rarity() and the stock rolls in src/blackmarket.c.
BM_BOSS_DROPS = (29920, 29921, 29922, 29923, 29924, 29925)
BM_CAKES = (29926, 29927)
BM_CHARMS = (9943, 9944)
BM_BOSS_DROP_CHANCE = 40            # percent of stocks
BM_CAKE_CHANCE = 30
BM_CHARM_CHANCE = 30
GOBLIN_RARE_CHANCE = 10             # src/goblin.c
DRAGON_RARE_CHANCE = 10             # src/disaster.c
GOBLIN_VNUM = 29941                 # MOB_VNUM_TREASURE_GOBLIN
DRAGON_VNUM = 4474                  # the black dragon
DEALER_VNUM = 29940                 # MOB_VNUM_BLACK_MARKET

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")


def boss_drop_vnums(level: int) -> List[int]:
    """Every piece in a guardian's drop table, as hyrule_boss_drops() names
    them."""
    total = BOSS_DROPS_PER_GUARDIAN + GUARDIAN_EXTRA_DROPS[level - 1]
    return [BOSS_DROP_FIRST + (level - 1) * BOSS_DROPS_PER_GUARDIAN + n
            if n < BOSS_DROPS_PER_GUARDIAN else
            BOSS_EXTRA_FIRST + (level - 1) * BOSS_EXTRA_STRIDE
            + n - BOSS_DROPS_PER_GUARDIAN
            for n in range(total)]


def in_window(today: datetime.date, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
    """Whether a month/day falls in a holiday's dates, which may wrap the
    new year (Winter Veil)."""
    now = (today.month, today.day)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _dates(start: Tuple[int, int], end: Tuple[int, int]) -> str:
    return "%s %d - %s %d" % (_MONTHS[start[0] - 1], start[1], _MONTHS[end[0] - 1], end[1])


def percent_text(chance: float) -> str:
    """27%, 6.7%, 0.56%: enough figures to tell the rare from the common."""
    pct = chance * 100.0
    if pct >= 10 or pct == int(pct):
        return "%d%%" % round(pct)
    if pct >= 1:
        return "%.1f%%" % pct
    return "%.2f%%" % pct


def _name(table: dict, vnum: int, fallback: str) -> str:
    thing = table.get(vnum)
    return str(getattr(thing, "short_desc", "") or fallback)


def _room_name(rooms: dict, vnum: int) -> str:
    return str(getattr(rooms.get(vnum), "name", "") or "room %d" % vnum).rstrip(".")


def _dungeon(level: int) -> str:
    return "Level %d: %s" % (level, DUNGEON_TITLES[level])


def hyrule_requires(level: int, objects: dict, guardian: Optional[str] = None) -> List[str]:
    """What a character must carry to reach the guardian of this dungeon
    (and, for Ganon, to finish him), from hyrule_progress_gate."""
    entry, tool, also = HYRULE_GATES[level]
    needs = []
    if entry:
        needs.append("%s (from %s's chest) to enter %s" % (
            _name(objects, entry, "the previous Triforce piece"),
            _dungeon(HYRULE_FOUND_IN[entry]), _dungeon(level)))
    if tool and guardian:
        what = _name(objects, tool, "a tool")
        if also:
            what += " or " + _name(objects, also, "another tool")
        needs.append("%s (found in %s) to reach %s's chamber" % (
            what, _dungeon(HYRULE_FOUND_IN[tool]), guardian))
    if level == 9 and guardian:
        needs.append("%s (found in %s) to finish him" % (
            _name(objects, SILVER_ARROW, "the Silver Arrow"),
            _dungeon(HYRULE_FOUND_IN[SILVER_ARROW])))
    return needs


def _source(kind: str, source: str, where: str, chance: float, how: str,
            level: int, requires: Iterable[str] = (), seasonal: Optional[str] = None,
            in_season: bool = True, mob_vnum: int = 0, room: int = 0,
            needs: Iterable[str] = ()) -> Dict[str, Any]:
    return {
        "kind": kind,
        "source": source,
        "mob_vnum": mob_vnum,
        "where": where,
        "room": room,
        "chance": round(chance, 4),
        "chance_text": how,
        "requires": list(requires),
        "needs": list(needs),
        "seasonal": seasonal,
        "in_season": in_season,
        "level": level,
    }


def hyrule_needs(level: int, objects: dict, guardian: Optional[str] = None) -> List[str]:
    """hyrule_requires() as the objects alone, for a short line."""
    entry, tool, also = HYRULE_GATES[level]
    names = []
    if entry:
        names.append(_name(objects, entry, "the previous Triforce piece"))
    if tool and guardian:
        names.append(_name(objects, tool, "a tool")
                     + (" or " + _name(objects, also, "another tool") if also else ""))
    if level == 9 and guardian:
        names.append(_name(objects, SILVER_ARROW, "the Silver Arrow"))
    return names


def dynamic_sources(world: Any, today: Optional[datetime.date] = None) -> Dict[int, List[Dict[str, Any]]]:
    """Every object the game makes at run time and a player may wear, with
    each way it is made: object vnum -> sources, the likeliest first. Out of
    season sources are kept, marked, so a description can say when."""
    today = today or datetime.date.today()
    objects = getattr(world, "objects", {}) or {}
    mobiles = getattr(world, "mobiles", {}) or {}
    rooms = getattr(world, "rooms", {}) or {}
    found: Dict[int, List[Dict[str, Any]]] = {}

    def add(vnum: int, entry: Dict[str, Any]) -> None:
        if vnum in objects:
            found.setdefault(vnum, []).append(entry)

    def mob_place(mob_vnum: int) -> Tuple[str, int]:
        mob = mobiles.get(mob_vnum)
        spawn = list(getattr(mob, "spawn_rooms", None) or [])
        if not spawn:
            return "", 0
        return _room_name(rooms, spawn[0]), spawn[0]

    def level_of(vnum: int) -> int:
        return int(getattr(objects.get(vnum), "level", 0) or 0)

    # Hyrule's guardians: three distinct pieces of the table each kill.
    for level, mob_vnum in enumerate(GUARDIAN_VNUMS, start=1):
        guardian = _name(mobiles, mob_vnum, "the guardian")
        place, room = mob_place(mob_vnum)
        table = boss_drop_vnums(level)
        per_kill = min(BOSS_DROPS_PER_KILL, len(table))
        chance = per_kill / float(len(table))
        how = "%d of its %d pieces fall each kill (%s)" % (per_kill, len(table), percent_text(chance))
        needs = hyrule_requires(level, objects, guardian)
        for vnum in table:
            add(vnum, _source("hyrule_guardian", guardian, place or _dungeon(level),
                              chance, how, level_of(vnum), needs,
                              mob_vnum=mob_vnum, room=room,
                              needs=hyrule_needs(level, objects, guardian)))

    # Ganon's relic, one of three.
    ganon = _name(mobiles, GANON_VNUM, "Ganon")
    place, room = mob_place(GANON_VNUM)
    chance = 1.0 / len(GANON_LOOT)
    for vnum in GANON_LOOT:
        add(vnum, _source("hyrule_ganon", ganon, place or _dungeon(9), chance,
                          "one of his %d relics falls each kill (%s)" % (
                              len(GANON_LOOT), percent_text(chance)),
                          level_of(vnum), hyrule_requires(9, objects, ganon),
                          mob_vnum=GANON_VNUM, room=room,
                          needs=hyrule_needs(9, objects, ganon)))

    # A cleared room's boomerang: once a reset, a copy for each player.
    for vnum, (level, room) in CLEAR_REWARD_GEAR.items():
        add(vnum, _source("hyrule_room_clear", "the room's last enemy",
                          _room_name(rooms, room), 1.0,
                          "when the room's last enemy dies, once each reset "
                          "(GET gives each player a copy)",
                          level_of(vnum), hyrule_requires(level, objects), room=room,
                          needs=hyrule_needs(level, objects)))

    # The holiday bosses, in the Oak Tree Square in their holiday.
    square = _room_name(rooms, EVENT_BOSS_ROOM)
    for mob_vnum, (holiday, start, end, table) in EVENT_BOSSES.items():
        boss = _name(mobiles, mob_vnum, "the holiday boss")
        season = "%s only (%s)" % (holiday, _dates(start, end))
        no_primary = 1.0
        for vnum, pct, role in table:
            if role == EVENT_DROP_PRIMARY:
                no_primary *= 1.0 - pct / 100.0
        for vnum, pct, role in table:
            chance = pct / 100.0
            if role == EVENT_DROP_FALLBACK:
                # Rolled like the rest, and laid anyway when its own roll
                # and every primary one missed (make_corpse: a rare drop
                # does not count as something falling).
                chance += (1.0 - chance) * no_primary
            add(vnum, _source("event_boss", boss, square, chance,
                              "%s a kill" % percent_text(chance), level_of(vnum),
                              seasonal=season, in_season=in_window(today, start, end),
                              mob_vnum=mob_vnum, room=EVENT_BOSS_ROOM))

    # Holiday treats a player can wear, from any mobile's corpse.
    for vnum, (holiday, start, end, pct) in HOLIDAY_TREATS.items():
        add(vnum, _source("holiday_treat", "any mobile", "anywhere", pct / 100.0,
                          "%d%% of mobile kills" % pct, level_of(vnum),
                          seasonal="%s only (%s)" % (holiday, _dates(start, end)),
                          in_season=in_window(today, start, end)))

    # The rarities: a tenth of goblin sacks and dragon hoards, and the black
    # market's stocks. A third of the rarities are holiday pieces, a third
    # cakes and a third Valhalla's clovers.
    rarity_lists = ((BM_BOSS_DROPS, BM_BOSS_DROP_CHANCE), (BM_CAKES, BM_CAKE_CHANCE),
                    (BM_CHARMS, BM_CHARM_CHANCE))
    for items, stock_pct in rarity_lists:
        share = 1.0 / 3 / len(items)
        for vnum in items:
            goblin = GOBLIN_RARE_CHANCE / 100.0 * share
            dragon = DRAGON_RARE_CHANCE / 100.0 * share
            stock = stock_pct / 100.0 / len(items)
            add(vnum, _source("treasure_goblin", _name(mobiles, GOBLIN_VNUM, "a treasure goblin"),
                              "wandering the world (there is always one)", goblin,
                              "%s of kills: a rarity in his sack" % percent_text(goblin),
                              level_of(vnum), mob_vnum=GOBLIN_VNUM))
            add(vnum, _source("black_dragon", _name(mobiles, DRAGON_VNUM, "the Great Black Dragon"),
                              "where it lands with a mortal it carried off in a disaster",
                              dragon, "%s of kills: a rarity in its hoard" % percent_text(dragon),
                              level_of(vnum), mob_vnum=DRAGON_VNUM))
            add(vnum, _source("black_market", _name(mobiles, DEALER_VNUM, "the black market dealer"),
                              "a rare wandering dealer, about one hour in ten", stock,
                              "in %s of his stocks, one to a buyer" % percent_text(stock),
                              level_of(vnum), mob_vnum=DEALER_VNUM))

    for sources in found.values():
        sources.sort(key=lambda s: (not s["in_season"], -s["chance"]))
    return found


def offered(sources: Optional[List[Dict[str, Any]]]) -> bool:
    """Whether the finder lists the item: a holiday's item only while its
    holiday is on, anything else whenever a source makes it."""
    if not sources:
        return False
    seasonal = [s for s in sources if s.get("seasonal")]
    if seasonal:
        return any(s.get("in_season") for s in seasonal)
    return True


def describe(source: Dict[str, Any]) -> str:
    """One source in a sentence: who, where, how likely, what it needs."""
    if source["kind"] == "hyrule_room_clear":
        text = "laid in %s %s" % (source["where"], source["chance_text"])
    elif source["kind"] == "black_market":
        text = "sold by %s, %s, %s" % (source["source"], source["where"], source["chance_text"])
    else:
        text = "dropped by %s, %s: %s" % (source["source"], source["where"], source["chance_text"])
    if source.get("requires"):
        text += "; needs " + "; ".join(source["requires"])
    if source.get("seasonal"):
        text += "; " + source["seasonal"]
    return text


def source_label(sources: List[Dict[str, Any]]) -> str:
    """The finder's source line: the likeliest way, and how many more."""
    if not sources:
        return ""
    text = describe(sources[0])
    rest = [s["source"] for s in sources[1:]]
    if rest:
        text += "; also " + ", ".join(rest)
    return text


def brief(sources: List[Dict[str, Any]]) -> str:
    """The likeliest way in a few words, for a list of many slots: who,
    where, the chance, the holiday and what the way there needs."""
    if not sources:
        return ""
    first = sources[0]
    if first["kind"] == "hyrule_room_clear":
        text = "laid in %s when its last enemy dies" % first["where"]
    else:
        shop = first["kind"] == "black_market"
        text = "%s %s, %s (%s %s)" % (
            "sold by" if shop else "dropped by", first["source"], first["where"],
            percent_text(first["chance"]), "of his stocks" if shop else "a kill")
    if first.get("seasonal"):
        text += ", " + first["seasonal"]
    if first.get("needs"):
        text += "; needs " + ", ".join(first["needs"])
    return text
