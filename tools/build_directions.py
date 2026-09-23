"""Work out how to walk anywhere from the Oak Tree Square, and check the
directions people already had.

The old list was decades of collected knowledge in one text file, and time
had moved parts of the world out from under it. Rather than guess at what
changed, this reads the area files, builds the room graph, and finds the
route itself -- so a direction that is published is one that walks today.

What it produces:

  * every historical route, walked and marked. Ones that still land where
    they claim are published as they were written, because that is the
    string people already know. Ones that no longer walk get a fresh route
    to the same place alongside the original.
  * a route to the entrance of every area in the game, which the old list
    never had -- Hyrule among about forty others.

Routes avoid death traps and rooms only staff may enter, open doors they
need to open, and name the secret keyword where one is required. Runs of
the same direction collapse into the game's own `r <dir> <n>' so a route
stays short enough to paste.
"""
from __future__ import annotations

import collections
import heapq
import json
import pathlib
import re
import sys

AREA = pathlib.Path("area")
START = 2401

DIRNAME = ["north", "east", "south", "west", "up", "down",
           "northeast", "northwest", "southeast", "southwest"]
SHORT = ["n", "e", "s", "w", "u", "d", "ne", "nw", "se", "sw"]

# Flag letters, as the area files write them.
FLAG_DT = "I"
FLAG_STAFF = ("O", "P")          # implementor only, gods only
FLAG_NEWBIE = "R"


def flag_letters(word):
    return set() if word.isdigit() else set(word)


# ITEM_MANIPULATION value[0]. 10 answers to any of them; 9 in value[4]
# means the object acts on the room it sits in, so it leads nowhere.
MANIP_VERB = {1: "flip", 2: "move", 3: "pull", 4: "push", 5: "turn",
              6: "climb", 7: "climb", 8: "crawl", 9: "jump", 10: "enter",
              11: "burn", 12: "bomb", 13: "play", 14: "feed"}
MANIP_TOOL = {11: "needs a lit candle", 12: "needs a bomb",
              13: "needs an instrument", 14: "needs bait"}
PUZZLE_CURRENT_ROOM = 9


def load_portals():
    """Ways through: room -> [(verb, keyword, destination, cost, label)].

    Both kinds of door-that-is-an-object live here -- ITEM_PORTAL, which
    you enter, and ITEM_MANIPULATION, which you climb, jump, crawl, push,
    pull, turn, burn, bomb, play to or feed.
    """
    portals = {}      # object vnum -> edge
    placed = {}       # room vnum -> list of edges

    for path in sorted(AREA.glob("*.are")):
        text = path.read_text("latin-1")
        m = re.search(r"^#OBJECTS\s*$(.*?)^#0\s*$", text, re.S | re.M)
        if not m:
            continue
        for blk in re.split(r"\n(?=#\d+[ \t\r\n])", m.group(1)):
            h = re.match(r"#(\d+)[ \t]*(.*?)~\s*\n(.*?)~", blk, re.S)
            if not h:
                continue
            v = re.search(r"\n(\d+)\s+\S+\s+\S+[ \t]*\n"
                          r"\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)",
                          blk)
            if v is None or v.group(1) not in ("30", "31"):
                continue

            kind = int(v.group(2))
            dest = int(v.group(3))
            need = int(v.group(6))
            keyword = h.group(2).strip().split()[0]

            if v.group(1) == "31":
                if dest <= 0 or need == PUZZLE_CURRENT_ROOM:
                    continue
                portals[int(h.group(1))] = (
                    MANIP_VERB.get(kind, "manipulate"), keyword, dest,
                    MANIP_TOOL.get(kind, ""), h.group(3).strip())
                continue

            if kind == 4 or dest <= 0:   # a crystal ball leads nowhere
                continue

            cost = ""
            if kind == 1:
                cost = "costs 500 gold"
            elif kind == 6 and need > 0:
                cost = f"needs object {need}"

            portals[int(h.group(1))] = ("enter", keyword, dest, cost,
                                        h.group(3).strip())

    for path in sorted(AREA.glob("*.are")):
        text = path.read_text("latin-1")
        m = re.search(r"^#RESETS\s*$(.*?)^S\s*$", text, re.S | re.M)
        if not m:
            continue
        for line in m.group(1).splitlines():
            o = re.match(r"^O\s+-?\d+\s+(\d+)\s+-?\d+\s+(\d+)", line.strip())
            if o and int(o.group(1)) in portals:
                placed.setdefault(int(o.group(2)), []).append(
                    portals[int(o.group(1))])

    return placed


def load_teleports():
    """Rooms that move you: room -> [(verb, keyword, dest, cost, label)].

    The three numbers sit after the sector, and a Z in the room flags
    (ROOM_FLAGS2) pushes everything along by one token.
    """
    carried = {}
    listed = [l.strip() for l in (AREA / "area.lst").read_text("latin-1").splitlines()
              if l.strip() and not l.strip().startswith("$")]

    for fname in listed:
        path = AREA / fname
        if not path.is_file():
            continue
        text = path.read_text("latin-1")
        m = re.search(r"^#ROOMS\s*$(.*?)^#0\s*$", text, re.S | re.M)
        if not m:
            continue

        for blk in re.split(r"\n(?=#\d+[ \t\r\n])", m.group(1)):
            h = re.match(r"#(\d+)[ \t]*(.*?)~", blk, re.S)
            if not h:
                continue
            # area, flags, [flags2], sector, then the teleport triple.
            # The builder may break that line anywhere, so read the
            # whole tail as tokens rather than one line.
            fl = re.search(r"\n~\n(.*)", blk, re.S)
            if not fl:
                continue

            tok = fl.group(1).split()
            if len(tok) < 3:
                continue
            flags = tok[1]
            if not (set("EF") & set(flags)):
                continue

            rest = tok[4:] if "Z" in flags else tok[3:]
            if not rest:
                continue
            try:
                dest, speed = int(rest[0]), int(rest[1]) if len(rest) > 1 else 0
            except ValueError:
                continue
            if dest <= 0:
                continue

            name = h.group(2).strip().replace("\n", " ")
            carried.setdefault(int(h.group(1)), []).append(
                ("wait", "", dest,
                 f"the room moves you every {speed} ticks" if speed else
                 "the room moves you",
                 name))

    return carried


def load_world():
    """vnum -> {name, area, flags, exits{door: (to, lock, keyword)}}"""
    rooms = {}
    listed = [l.strip() for l in (AREA / "area.lst").read_text("latin-1").splitlines()
              if l.strip() and not l.strip().startswith("$")]

    for fname in listed:
        path = AREA / fname
        if not path.is_file():
            continue
        text = path.read_text("latin-1")
        am = re.search(r"#AREA\s+(.*?)~", text, re.S)
        aname = re.sub(r"\{.*?\}", "", am.group(1)).strip() if am else fname
        aname = re.sub(r"\s+", " ", aname)

        m = re.search(r"^#ROOMS\s*$(.*?)^#0\s*$", text, re.S | re.M)
        if not m:
            continue

        for blk in re.split(r"\n(?=#\d+[ \t\r\n])", m.group(1)):
            h = re.match(r"#(\d+)[ \t]*(.*?)~", blk, re.S)
            if not h:
                continue
            vnum = int(h.group(1))

            fl = re.search(r"\n~\n(\S+) (\S+) ", blk)
            flags = flag_letters(fl.group(2)) if fl else set()

            exits = {}
            # "D 0" is as common as "D0": fread_letter takes the D and
            # fread_number skips space before the digit, so the game
            # reads both and the router has to as well.
            # "D 0", "D0", and a description that starts on the same
            # line as the number are all the same token stream to
            # fread_letter/fread_number/fread_string.
            for d in re.finditer(r"^D\s*(\d)\s*(.*?)~\s*\n(.*?)~\s*\n"
                                 r"\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)",
                                 blk, re.S | re.M):
                to = int(d.group(6))
                if to > 0:
                    exits[int(d.group(1))] = (to, int(d.group(4)),
                                              d.group(3).strip())

            rooms[vnum] = {"name": h.group(2).strip().replace("\n", " "),
                           "area": aname, "flags": flags, "exits": exits}
    return rooms


def passable(room):
    """Somewhere a player can walk through without dying or being refused."""
    if room is None:
        return False
    if FLAG_DT in room["flags"]:
        return False
    if any(f in room["flags"] for f in FLAG_STAFF):
        return False
    if FLAG_NEWBIE in room["flags"]:
        return False
    return True


# What an edge is worth, in rooms walked. A door or a rope is one move you
# make yourself; a room that carries you is a wait on somebody else's
# timer, so it has to be dear enough that the router walks instead when
# walking is possible at all.
WAIT_COST = 8


def shortest_paths(rooms, start, portals):
    """Cheapest route from start, walking and using the ways through.

    A step is (door, from_vnum) for an exit, or (edge, from_vnum) for a
    portal, handhold or teleport room -- the type of the first element
    says which.
    """
    seen = {start: []}
    spent = {start: 0}
    queue = [(0, start)]

    while queue:
        paid, here = heapq.heappop(queue)
        if paid > spent.get(here, paid):
            continue

        moves = []
        for door in range(10):
            step = rooms[here]["exits"].get(door)
            if step is not None:
                moves.append((1, step[0], (door, here)))

        for verb, keyword, dest, cost, label in portals.get(here, []):
            price = WAIT_COST if verb == "wait" else 1
            moves.append((price, dest, ((verb, keyword, cost, label), here)))

        for price, to, step in moves:
            if to not in rooms or not passable(rooms[to]):
                continue
            total = paid + price
            if total >= spent.get(to, total + 1):
                continue
            spent[to] = total
            seen[to] = seen[here] + [step]
            heapq.heappush(queue, (total, to))

    return seen


def to_commands(rooms, path):
    """A path as something you can paste, doors and all."""
    out = []
    run_door, run_len = None, 0

    def flush():
        nonlocal run_door, run_len
        if run_door is None:
            return
        out.append(SHORT[run_door] if run_len == 1
                   else f"r {SHORT[run_door]} {run_len}")
        run_door, run_len = None, 0

    for door, from_vnum in path:
        if isinstance(door, tuple):
            flush()
            # A teleport room needs no command; you stand in it and wait.
            if door[0] != "wait":
                out.append(f"{door[0]} {door[1]}")
            continue

        _, lock, keyword = rooms[from_vnum]["exits"][door]

        if lock != 0:
            flush()
            # The loader forces lock 4 on anything keyworded "secret", and
            # a keyworded door has to be opened by that word, not by
            # direction.
            word = keyword.split()[0] if keyword else DIRNAME[door]
            out.append(f"open {word}")

        if run_door == door:
            run_len += 1
        else:
            flush()
            run_door, run_len = door, 1

    flush()
    return ";".join(out)


def describe(rooms, path):
    """The same path in words."""
    steps, run_door, run_len = [], None, 0

    def flush():
        nonlocal run_door, run_len
        if run_door is None:
            return
        steps.append(DIRNAME[run_door] if run_len == 1
                     else f"{DIRNAME[run_door]} x{run_len}")
        run_door, run_len = None, 0

    for door, from_vnum in path:
        if isinstance(door, tuple):
            flush()
            verb, keyword, cost, label = door
            if verb == "wait":
                steps.append(f"wait in {label}"
                             + (f" ({cost})" if cost else ""))
            else:
                steps.append(f"{verb} {label or keyword}"
                             + (f" ({cost})" if cost else ""))
            continue

        _, lock, keyword = rooms[from_vnum]["exits"][door]
        if lock != 0:
            flush()
            word = keyword.split()[0] if keyword else DIRNAME[door]
            steps.append(f"open {word}")
        if run_door == door:
            run_len += 1
        else:
            flush()
            run_door, run_len = door, 1
    flush()
    return steps


DIRS = {"n": 0, "north": 0, "e": 1, "east": 1, "s": 2, "south": 2,
        "w": 3, "west": 3, "u": 4, "up": 4, "d": 5, "down": 5,
        "ne": 6, "northeast": 6, "nw": 7, "northwest": 7,
        "se": 8, "southeast": 8, "sw": 9, "southwest": 9}

IDLE = {"wake", "wa", "stand", "st", "look", "l", "rest", "sleep"}


def walk_legacy(rooms, portals, script):
    """Follow a handed-down route. Returns (vnum, problem or None)."""
    here = START

    for raw in re.split(r"[;\n]", script):
        step = raw.strip().lower().strip(".")
        if not step or step.startswith("(") or step in IDLE:
            continue
        if step.split()[0] in ("open", "close", "unlock", "lock", "c", "cast"):
            continue

        parts = step.split()

        if parts[0] in MANIP_VERB.values() and len(parts) > 1:
            wanted = parts[1]
            for verb, keyword, dest, _cost, _label in portals.get(here, []):
                if keyword.lower().startswith(wanted):
                    here = dest
                    break
            else:
                return here, f"no '{step}' here"
            continue

        if parts[0] in ("r", "run") and len(parts) >= 2 and parts[1] in DIRS:
            door = DIRS[parts[1]]
            want = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
            moved = 0
            while moved < want:
                nxt = rooms.get(here, {}).get("exits", {}).get(door)
                if nxt is None or nxt[0] not in rooms:
                    break
                here = nxt[0]
                moved += 1
            if moved == 0:
                return here, f"nothing lies {DIRNAME[door]} of here"
            if len(parts) > 2 and parts[2].isdigit() and moved < want:
                return here, (f"'{raw.strip()}' runs out after {moved} of "
                              f"{want} rooms")
            continue

        if len(parts) == 1 and parts[0] in DIRS:
            door = DIRS[parts[0]]
            nxt = rooms.get(here, {}).get("exits", {}).get(door)
            if nxt is None or nxt[0] not in rooms:
                return here, f"no exit {DIRNAME[door]} from here"
            here = nxt[0]
            continue

        return here, f"'{raw.strip()}' is not a movement"

    return here, None


def describe_legacy(script):
    """A handed-down command string, read aloud."""
    out = []
    for raw in re.split(r"[;\n]", script):
        s = raw.strip().lower()
        if not s:
            continue
        parts = s.split()
        if parts[0] in ("r", "run") and len(parts) >= 2 and parts[1] in DIRS:
            d = DIRNAME[DIRS[parts[1]]]
            out.append(f"run {d} {parts[2]}" if len(parts) > 2 and parts[2].isdigit()
                       else f"run {d} until you stop")
        elif len(parts) == 1 and parts[0] in DIRS:
            out.append(DIRNAME[DIRS[parts[0]]])
        elif parts[0] in ("wa", "wake"):
            out.append("wake")
        elif parts[0] in ("st", "stand"):
            out.append("stand")
        else:
            out.append(s)

    squashed, i = [], 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and out[j + 1] == out[i]:
            j += 1
        squashed.append(out[i] if j == i else f"{out[i]} x{j - i + 1}")
        i = j + 1
    return squashed


def normalise(text):
    """Squash a name to comparable words: no punctuation, no filler."""
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    words = re.sub(r"\b(the|of|a|an|path|to|and|old|new)\b", " ", words)
    return " ".join(words.split())


def match_area(name, areas):
    """Which area is a route called `name' trying to reach?

    Both sides go through the same squashing, or "Wyvern's Tower" never
    matches "Tyrst Wyvern's Tower" over a single apostrophe.
    """
    want = normalise(name)
    if not want:
        return None

    best, best_len = None, 0
    for area in areas:
        # Area names lead with the builder's handle; drop it.
        tail = normalise(" ".join(area.split()[1:]))
        if not tail:
            continue
        if want == tail:
            return area
        if (want in tail or tail in want) and len(tail) > best_len:
            best, best_len = area, len(tail)

    return best


def area_entrances(rooms, reach):
    """The nearest reachable room of each area, which is its way in."""
    best = {}
    for vnum, path in reach.items():
        area = rooms[vnum]["area"]
        if area not in best or len(path) < len(best[area][1]):
            best[area] = (vnum, path)
    return best


def main():
    rooms = load_world()
    portals = load_portals()
    for room, edges in load_teleports().items():
        portals.setdefault(room, []).extend(edges)
    reach = shortest_paths(rooms, START, portals)
    entrances = area_entrances(rooms, reach)

    routes = []
    for area, (vnum, path) in sorted(entrances.items()):
        if vnum == START or not path:
            continue
        routes.append({
            "name": area,
            "commands": to_commands(rooms, path),
            "steps": describe(rooms, path),
            "room": rooms[vnum]["name"],
            "vnum": vnum,
            "area": area,
            "rooms_away": len(path),
            "status": "computed",
        })

    # The handed-down list, checked and repaired where it has drifted.
    by_area = {r["area"]: r for r in routes}
    legacy_path = pathlib.Path("tools/legacy_routes.json")
    legacy = []

    if legacy_path.is_file():
        for name, script in sorted(
                json.loads(legacy_path.read_text("utf-8")).items()):
            here, problem = walk_legacy(rooms, portals, script)
            room = rooms.get(here, {})
            entry = {
                "name": name,
                "commands": script,
                "steps": describe_legacy(script),
                "room": room.get("name", ""),
                "vnum": here,
                "area": room.get("area", ""),
                "status": "verified" if problem is None else "drifted",
            }

            if problem is not None:
                entry["note"] = (f"The old directions stop here: {problem}.")
                target = match_area(name, by_area)
                if target:
                    fixed = by_area[target]
                    entry["fixed_commands"] = fixed["commands"]
                    entry["fixed_steps"] = fixed["steps"]
                    entry["fixed_room"] = fixed["room"]
                    entry["fixed_area"] = fixed["area"]

            legacy.append(entry)

    payload = {
        "start": {"vnum": START, "room": rooms[START]["name"],
                  "area": rooms[START]["area"]},
        "counts": {
            "computed": len(routes),
            "legacy_ok": sum(1 for e in legacy if e["status"] == "verified"),
            "legacy_drifted": sum(1 for e in legacy if e["status"] == "drifted"),
            "legacy_repaired": sum(1 for e in legacy if "fixed_commands" in e),
        },
        "routes": routes,
        "legacy": legacy,
    }

    out = pathlib.Path("webadmin/directions.json")
    out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rooms)} rooms, {len(reach)} reachable from {START} "
          f"({sum(len(v) for v in portals.values())} portals and "
          f"handholds in play)")
    print(f"{len(routes)} areas routed, "
          f"{payload['counts']['legacy_ok']} handed-down routes still good, "
          f"{payload['counts']['legacy_repaired']} repaired -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
