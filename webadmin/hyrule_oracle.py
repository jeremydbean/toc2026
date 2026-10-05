"""What the Oracle knows about Hyrule, the zone (owner, 2026-10-04).

Players will have many questions about how Hyrule progresses, so every
question that touches it -- or comes from somebody standing in it -- is
grounded with three things:

* GUIDE: how the zone actually plays here -- the order of the dungeons,
  where each entrance is and what opens it, what each guardian's chest
  gives, and the commands the zone uses. About this zone as built, not
  about the NES game it was drawn from.
* The asker's own progress, from the game (src/oracle.c, oracle_state):
  the dungeon they are working on and the Hyrule items they carry.
* A route from the room they are standing in to the next dungeon's
  entrance, and to any place in Hyrule, or the world, the question names,
  walked over the parsed area files with the same rules the game applies:
  raft and stepladder crossings need the item, and each seal needs its
  act, which the route spells out.

The facts in GUIDE and DUNGEONS are held to the generator and the C gate
table by tests/test_hyrule_oracle.py.
"""
from __future__ import annotations

import heapq
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

HYRULE_FIRST, HYRULE_LAST = 30200, 30799
OVERWORLD_FIRST, OVERWORLD_LAST = 30200, 30327
ENTRY_ROOM = 30200          # The First Quest Begins
CABINET_ROOM = 15068        # the arcade cabinet, in the Strange Campus
TEMPLE_ROOM = 4207          # where RECALL lands by default
DIRS = ["north", "east", "south", "west", "up", "down",
        "northeast", "northwest", "southeast", "southwest"]
ROOM_DT_LETTER = "I"

# level: (title, overworld screen, entrance room, guardian, treasure in its
# chest, what stands at the door). Held to the generator by the test.
DUNGEONS: Dict[int, Dict[str, Any]] = {
    1: dict(title="The Eagle", screen=30271, entrance=30401, band="2-8",
            guardian="Aquamentus", treasure="a small boomerang",
            door="nothing; the entrance is down from the Eagle's Gate"),
    2: dict(title="The Moon", screen=30276, entrance=30418, band="8-14",
            guardian="Dodongo", treasure="the Magical Boomerang",
            door="Level 1's Triforce piece"),
    3: dict(title="The Manji", screen=30205, entrance=30437, band="14-20",
            guardian="Manhandla", treasure="the dungeon raft",
            door="Level 2's Triforce piece"),
    4: dict(title="The Snake", screen=30253, entrance=30456, band="20-27",
            guardian="Gleeok", treasure="the stepladder",
            door="Level 3's Triforce piece, and the raft (ENTER RAFT on the island)"),
    5: dict(title="The Lizard", screen=30323, entrance=30476, band="27-33",
            guardian="Digdogger", treasure="a short bow",
            door="Level 4's Triforce piece"),
    6: dict(title="The Dragon", screen=30282, entrance=30501, band="33-40",
            guardian="Gohma", treasure="the Recorder",
            door="Level 5's Triforce piece"),
    7: dict(title="The Demon", screen=30250, entrance=30527, band="40-46",
            guardian="an ancient Aquamentus", treasure="the Red Candle",
            door="Level 6's Triforce piece, and PLAY RECORDER at the pond to drain it"),
    8: dict(title="The Lion", screen=30229, entrance=30562, band="46-52",
            guardian="an ashen Gleeok", treasure="the Magical Key",
            door="Level 7's Triforce piece, and BURN BUSH with a lit candle"),
    9: dict(title="Death Mountain", screen=30317, entrance=30590, band="53-59",
            guardian="Ganon", treasure="the Master Sword and the final Triforce piece",
            door="Level 8's Triforce piece, and BOMB CRACKED with all eight pieces held"),
}

# What each dungeon's guardian chamber asks for: the previous chest's treasure.
GUARDIAN_NEEDS = {
    2: "a small boomerang (or the Magical Boomerang)", 3: "the Magical Boomerang",
    4: "the dungeon raft", 5: "the stepladder", 6: "a short bow", 7: "the Recorder",
    8: "the Red Candle", 9: "the Magical Key",
}

GUIDE = """\
HYRULE, AS THIS ZONE WORKS (answer from this, not from the NES game):
Getting there: the arcade cabinet in the Strange Campus (ENTER CABINET) sets
you down at The First Quest Begins, the overworld's south edge. The overworld
is open sky: recall works there. Every dungeon room is no-recall, and nothing
magical (gate, portal, summon, astral walk) lands in one.
The nine dungeons go in order, each sized for a band of character levels:
L1 2-8, L2 8-14, L3 14-20, L4 20-27, L5 27-33, L6 33-40, L7 40-46, L8 46-52,
L9 (Death Mountain) 53-59. Each one works the same way: its entrance asks for
the previous dungeon's Triforce piece; inside, the way into the guardian's
chamber asks for the previous dungeon's treasure; the guardian drops a key
that opens the locked door behind it and the locked chest there; the chest
holds this dungeon's piece and its treasure. Both gates ask the character
walking -- nobody can hold a door for anyone -- and count what you carry in
hand, worn, or one bag down (not the stash). Pieces cannot be dropped or
given. Guardians, keys and chests come back at every area reset, so nothing
is lost for good: lose a treasure and you can redo that dungeon.
Treasures: L1 a small boomerang, L2 the Magical Boomerang, L3 the dungeon raft,
L4 the stepladder, L5 a short bow,
L6 Recorder, L7 Red Candle, L8 Magical Key, L9 the Master Sword and the final
piece. Guardians: Aquamentus, Dodongo, Manhandla, Gleeok, Digdogger, Gohma,
an ancient Aquamentus, an ashen Gleeok, Ganon. Guardians are hard: an
ordinary character at the top of the band loses alone. With Hermie's buffs
first (she stands at the Temple altar after a reboot: BUFF EMPOWER, BUFF
TITANIC, BUFF DEFENSE, BUFF COMBAT) one can win alone, though it is close;
a group does better. Ganon is a fight for a buffed group: two players
buffed by Hermie can beat him, one alone cannot. Each
guardian carries its weapon and Heart Guard and drops three more pieces from
a table with one for every other armour slot, each the best in the game for
its band, for fighters and casters alike. Nothing in Hyrule attacks first;
its creatures are as tough as the world's at the same level, and the land
around each dungeon is graded for that dungeon's band. Enemies killed near a
cracked wall leave a bomb now and then, and every tenth foe in a row killed
without taking a wound leaves one too.
Where the entrances are, from The First Quest Begins:
 L1 Eagle's Gate: north to the River Landing, stepping stones west, DOWN.
 L2 Moon Gate: east through the meadows to Moblin Hollow, north to the Wooded
   Crossroads, west to the Eastern Dock, the ferry north, DOWN.
 L3 Grove of the Manji: west through the woods (Candle Shop Knoll, Forest
   Stream, Lost Woods, Bramble Wood), south to the Path to the Manji, east, DOWN.
 L4 Isle of the Snake: Forest Stream north to the Shore Below the Snake, plank
   bridge north, ENTER RAFT (needs the raft).
 L5 Lizard's Gate: River Landing north, east across the sands to Below the
   Lost Hills, north twice over stepladder crossings, DOWN.
 L6 Dragon's Gate: west to the Western Meadow Edge, north by raft to the
   graveyard, east to Ghost Hill, north by stepladder, DOWN.
 L7 The Still Pond: Shore Below the Snake west to the Lost Woods Crossing,
   north; PLAY RECORDER to drain the pond, DOWN.
 L8 Lion's Thicket: east along the river from Bush Row; BURN BUSH, DOWN.
 L9 Spectacle Rock: River Landing north, west to the Foot of Death Mountain,
   north FIVE times through the Lost Hills, west twice; BOMB CRACKED with all
   eight pieces held, DOWN.
Crossings: a "raft crossing" exit needs the raft carried; a "stepladder
crossing" the stepladder. Sealed ways open only by their act: BOMB CRACKED
(a bomb, used up), BURN BUSH (a lit Blue or Red Candle in the light slot),
PUSH an Armos, block or grave, PUSH STONE at a warp hall (Power Bracelet),
PLAY RECORDER, FEED the hungry Goriya bait. Shutters open when the room's
enemies are dead. Small-key doors use up a small key (found in the dungeon,
or bought for 80-100 gold); the Magical Key opens them all.
Helps: each dungeon's map (LOOK MAP) draws its floor plan, and its compass
names the first step toward the Triforce chest. Coming out of a dungeon you
have won by its returning light, an owl says where the next one is. Once you
hold the Recorder, PLAY RECORDER (or BLOW RECORDER) on the overworld calls a
whirlwind to any dungeon whose piece you carry and to the one you are working
on; PLAY RECORDER <level> goes straight to one.
Shops sell bombs (20), arrows (80), the Blue Candle (60), keys, bait, shields
and the Blue Ring; potion shops sell only to someone carrying Zelda's Letter.
Money caves pay once per character. HEARTS counts hearts (3, plus one per
guardian of 1-8 beaten and per Heart Container taken); the White Sword needs
5, the Magical Sword 12. SHOOT <enemy> fires the wielded bow (a gold coin an
arrow, quiver carried) or throws a boomerang. Gohma dies only to an arrow.
Ganon cannot be killed by ordinary blows: bring him to his knees, then with
the Silver Arrow (Death Mountain's cellar) wielded, SHOOT GANON. After Ganon,
COMBINE TRIFORCE joins the nine pieces into The Triforce, which counts as
every piece. The Quest Master never sends anyone into Hyrule.
"""

_HYRULE_WORDS = (
    "hyrule", "zelda", "triforce", "dungeon", "ganon", "raft", "stepladder",
    "ladder", "recorder", "whistle", "flute", "owl", "boomerang", "arcade",
    "cabinet", "overworld", "rupee", "heart container", "hearts", "aquamentus",
    "dodongo", "manhandla", "gleeok", "digdogger", "gohma", "master sword",
    "silver arrow", "magical key", "red candle", "blue candle", "lost woods",
    "lost hills", "death mountain", "spectacle rock", "eagle", "moon gate",
    "manji", "snake", "lizard", "dragon's gate", "lion", "still pond",
    "letter", "power bracelet", "moblin", "octorok", "tektite", "lynel",
    "darknut", "wizzrobe", "like like", "keese", "goriya", "first quest",
)


def in_hyrule(vnum: int) -> bool:
    return HYRULE_FIRST <= (vnum or 0) <= HYRULE_LAST


def is_hyrule_question(question: str) -> bool:
    ql = (question or "").lower()
    return any(w in ql for w in _HYRULE_WORDS)


# ---------------------------------------------------------------------
# Routing.
# ---------------------------------------------------------------------

def _carries(items: Iterable[str], word: str) -> bool:
    return any(word in (i or "").lower() for i in items)


def _seal_act(keyword: str, direction: str) -> Tuple[str, str]:
    """The command that opens a sealed Hyrule exit, and what it needs."""
    kw = keyword.lower()
    if "triforce" in kw:
        return "bomb cracked", "a bomb and all eight Triforce pieces"
    if "recorder" in kw:
        return "play recorder", "the Recorder"
    if "hungry" in kw:
        return "feed goriya", "bait"
    if kw.startswith("cracked") or kw.startswith("bomb"):
        return "bomb cracked", "a bomb"
    if kw.startswith("burn"):
        return "burn bush", "a lit candle"
    if kw.startswith("armos"):
        return "push armos", ""
    if kw.startswith("block"):
        return "push block", ""
    if kw.startswith("grave"):
        return "push grave", ""
    if kw.startswith("bracelet"):
        return "push stone", "the Power Bracelet"
    return "open " + direction, ""


def build_graph(rooms: Dict[int, Any], links: Iterable[Dict[str, Any]]
                ) -> Dict[int, List[Tuple[int, str, str, str, int]]]:
    """Every way through, as {room: [(to, command, act, need, cost)]}:
    exits, and the portals and climbs directions.json lists. A seal's act
    is the command to type first; need is what it, or the crossing, asks."""
    graph: Dict[int, List[Tuple[int, str, str, str, int]]] = {}
    for vnum, room in rooms.items():
        edges = graph.setdefault(vnum, [])
        for ex in getattr(room, "exits", []) or []:
            to = getattr(ex, "to_room", 0) or 0
            if to <= 0 or to not in rooms:
                continue
            if ROOM_DT_LETTER in (getattr(rooms[to], "room_flags", "") or ""):
                continue
            d = DIRS[ex.direction] if 0 <= ex.direction < len(DIRS) else "?"
            kw = (ex.keyword or "").lower()
            act, need = "", ""
            if in_hyrule(vnum):
                if "raft crossing" in kw:
                    need = "the raft"
                elif "stepladder crossing" in kw:
                    need = "the stepladder"
                elif ex.locks == 4 and kw:
                    act, need = _seal_act(kw, d)
                elif "locked dungeon door" in kw:
                    act, need = "unlock " + d, "a small key or the Magical Key"
                elif "treasure door" in kw or "golden door" in kw:
                    act, need = "unlock " + d, "the guardian's key"
                elif kw == "shutter":
                    need = "the room's enemies dead"
            edges.append((to, d, act, need, 1))
    for link in links or []:
        try:
            frm, to = int(link["from"]), int(link["to"])
        except (KeyError, TypeError, ValueError):
            continue
        if frm not in rooms or to not in rooms:
            continue
        cmd = str(link.get("command") or "")
        need = ""
        if "raft" in cmd:
            need = "the raft"
        elif "stepladder" in cmd or "crossing" in cmd:
            need = "the stepladder"
        graph.setdefault(frm, []).append((to, cmd, "", need, 1))
    return graph


def _usable(need: str, items: List[str]) -> bool:
    if not need:
        return True
    if need == "the raft":
        return _carries(items, "raft")
    if need == "the stepladder":
        return _carries(items, "stepladder")
    if need == "the Recorder":
        return _carries(items, "recorder")
    if need == "the Power Bracelet":
        return _carries(items, "bracelet")
    return True     # keys, bombs, candles and enemies: say so, do not refuse


def route(graph, start: int, goal: int, items: Optional[List[str]] = None,
          ignore_tools: bool = False, with_rooms: bool = False):
    """The cheapest way from start to goal as [(command, act, need)], or
    None. Crossings the asker lacks the tool for are skipped unless
    ignore_tools, in which case the route names what it would need.
    with_rooms adds the room each step reaches, as a fourth field."""
    items = items or []
    if start == goal:
        return []
    best = {start: 0}
    prev: Dict[int, Tuple[int, str, str, str]] = {}
    queue = [(0, start)]
    while queue:
        cost, v = heapq.heappop(queue)
        if v == goal:
            break
        if cost > best.get(v, 1 << 30):
            continue
        for to, cmd, act, need, c in graph.get(v, ()):
            if not ignore_tools and not _usable(need, items):
                continue
            nc = cost + c + (2 if act else 0)
            if nc < best.get(to, 1 << 30):
                best[to] = nc
                prev[to] = (v, cmd, act, need)
                heapq.heappush(queue, (nc, to))
    if goal not in prev:
        return None
    steps = []
    v = goal
    while v != start:
        u, cmd, act, need = prev[v]
        steps.append((cmd, act, need, v))
        v = u
    steps.reverse()
    if with_rooms:
        return steps
    return [(cmd, act, need) for cmd, act, need, _to in steps]


def describe(steps: List[Tuple[str, str, str]]) -> str:
    """'north, east, north x3, BURN BUSH (needs a lit candle) then down'."""
    out: List[str] = []
    last, count = None, 0

    def flush():
        if last is not None:
            out.append(last if count == 1 else "%s x%d" % (last, count))

    for cmd, act, need in steps:
        if act or need or cmd not in DIRS:
            flush()
            last, count = None, 0
            text = cmd
            if act and not act.startswith("open "):
                text = "%s%s then %s" % (act.upper(),
                                         " (needs %s)" % need if need else "", cmd)
            elif act:
                text = "%s (needs %s) then %s" % (act, need, cmd) if need else "%s then %s" % (act, cmd)
            elif need:
                text = "%s (needs %s)" % (cmd, need)
            out.append(text)
            continue
        if cmd == last:
            count += 1
        else:
            flush()
            last, count = cmd, 1
    flush()
    return ", ".join(out)


# ---------------------------------------------------------------------
# Destinations named in a question.
# ---------------------------------------------------------------------

_DUNGEON_ALIASES = {
    1: ("eagle",), 2: ("moon",), 3: ("manji",), 4: ("snake",), 5: ("lizard",),
    6: ("dragon",), 7: ("demon", "still pond"), 8: ("lion",),
    9: ("death mountain", "spectacle", "ganon"),
}


def named_dungeon(question: str) -> Optional[int]:
    ql = (question or "").lower()
    m = re.search(r"\b(?:level|dungeon|l)\s*([1-9])\b", ql)
    if m and ("dungeon" in ql or "hyrule" in ql or "level " + m.group(1) + " dungeon" in ql
              or re.search(r"\bdungeon\s*[1-9]\b", ql) or re.search(r"\bl[1-9]\b", ql)
              or "entrance" in ql or "gate" in ql):
        return int(m.group(1))
    for level, words in _DUNGEON_ALIASES.items():
        if any(w in ql for w in words):
            return level
    return None


def named_hyrule_room(question: str, rooms: Dict[int, Any]) -> Optional[int]:
    """An overworld screen, shop or cave the question names by its room name."""
    ql = " ".join(re.findall(r"[a-z']+", (question or "").lower()))
    best, best_len = None, 0
    for vnum, room in rooms.items():
        if not in_hyrule(vnum):
            continue
        name = " ".join(re.findall(r"[a-z']+", (getattr(room, "name", "") or "").lower()))
        name = re.sub(r"^the ", "", name)
        if len(name) >= 6 and name in ql and len(name) > best_len:
            best, best_len = vnum, len(name)
    return best


def named_world_place(question: str, directions: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """An area, guild hall or trainer the question names, from directions.json."""
    ql = (question or "").lower()
    words = set(re.findall(r"[a-z]{4,}", ql)) - {"hyrule", "from", "here", "there",
                                                 "where", "what", "with", "directions",
                                                 "route", "walk", "back", "into", "gate",
                                                 "level", "dungeon", "town", "city"}
    best, best_score = None, 0
    entries = list(directions.get("routes") or []) + list(directions.get("trainers") or []) \
        + list(directions.get("places") or [])
    for entry in entries:
        name = str(entry.get("area_display") or entry.get("name") or "")
        hay = " ".join(str(entry.get(k, "")) for k in ("name", "area", "area_display",
                                                       "keywords")).lower()
        score = sum(1 for w in words if w in hay)
        if score > best_score and entry.get("vnum"):
            best, best_score = (name, int(entry["vnum"])), score
    return best


# ---------------------------------------------------------------------
# The lines the Oracle is given.
# ---------------------------------------------------------------------

def _room_name(rooms, vnum: int) -> str:
    return (getattr(rooms.get(vnum), "name", "") or "room %d" % vnum).strip()


def _route_line(graph, rooms, start: int, goal: int, items: List[str], label: str) -> str:
    steps = route(graph, start, goal, items)
    missing = ""
    if steps is None:
        steps = route(graph, start, goal, items, ignore_tools=True)
        if steps is not None:
            wants = sorted({need for _c, _a, need in steps
                            if need in ("the raft", "the stepladder", "the Recorder",
                                        "the Power Bracelet") and not _usable(need, items)})
            if wants:
                missing = " They do not carry %s yet, which this way needs." % " and ".join(wants)
    if steps is None:
        return "No walking route found from %s to %s." % (_room_name(rooms, start), label)
    if not steps:
        return "The supplicant is already at %s." % label
    return "Route from where the supplicant stands (%s) to %s, %d moves: %s.%s" % (
        _room_name(rooms, start), label, len(steps), describe(steps), missing)


def oracle_lines(question: str, state: Dict[str, Any], rooms: Dict[int, Any],
                 directions: Dict[str, Any], graph=None) -> List[str]:
    """Hyrule grounding for one question: the guide, the asker's progress
    and routes. Empty when the question is not about Hyrule and the asker
    is not in it -- except a route from wherever they stand to a named
    place, which any question asking the way gets."""
    room = int(state.get("room") or 0)
    items = list(state.get("hyrule_items") or [])
    here_hyrule = in_hyrule(room)
    about = is_hyrule_question(question) or named_dungeon(question) is not None
    asks_way = bool(re.search(r"\b(how do i get|how to get|where is|where's|where are|"
                              r"directions?|route|way to|get to|go to|find|lost|"
                              r"how do i reach|path|from here|next)\b",
                              (question or "").lower()))
    lines: List[str] = []
    if graph is None and rooms:
        graph = build_graph(rooms, directions.get("links") or [])

    if about or here_hyrule:
        lines.append(GUIDE)
        nxt = int(state.get("hyrule_next") or 0) if state else 0
        if state:
            held = [i for i in items if "triforce" in i.lower() or "piece" in i.lower()
                    or "shard" in i.lower()]
            if nxt == 0 and "hyrule_next" in state:
                lines.append("The supplicant carries all nine Triforce pieces (or The "
                             "Triforce): every dungeon is behind them.")
            elif nxt:
                d = DUNGEONS[nxt]
                lines.append(
                    "The supplicant's Hyrule progress, from the game: working on Level %d "
                    "(%s, characters %s); its door asks for %s%s. Hyrule items they "
                    "carry: %s." % (
                        nxt, d["title"], d["band"], d["door"],
                        ("; its guardian's chamber for " + GUARDIAN_NEEDS[nxt])
                        if nxt in GUARDIAN_NEEDS else "",
                        "; ".join(items) if items else "none"))
            if held:
                lines.append("Triforce pieces carried: %s." % "; ".join(held))
        if room and graph:
            if not here_hyrule:
                lines.append("The supplicant is not in Hyrule now.")
            target = named_dungeon(question)
            if target is None and state and nxt:
                target = nxt
            if target:
                d = DUNGEONS[target]
                lines.append(_route_line(graph, rooms, room, d["screen"], items,
                                         "Level %d's entrance screen, %s" % (
                                             target, _room_name(rooms, d["screen"]))))
            other = named_hyrule_room(question, rooms)
            if other and (not target or other != DUNGEONS[target]["screen"]):
                lines.append(_route_line(graph, rooms, room, other, items,
                                         _room_name(rooms, other)))

    if room and graph and asks_way and here_hyrule:
        place = named_world_place(question, directions)
        if place and not in_hyrule(place[1]) and "hyrule" not in place[0].lower():
            lines.append(_route_line(graph, rooms, room, place[1], items, place[0]))
            # Leaving the overworld, RECALL is usually quicker than walking.
            if OVERWORLD_FIRST <= room <= OVERWORLD_LAST and TEMPLE_ROOM in rooms:
                walk = route(graph, TEMPLE_ROOM, place[1], items)
                if walk is not None:
                    lines.append("Or, quicker: RECALL works on Hyrule's overworld. From the "
                                 "Temple (the default recall point) to %s, %d moves: %s." % (
                                     place[0], len(walk), describe(walk)))
    return lines
