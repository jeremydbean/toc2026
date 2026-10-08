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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "webadmin"))
from area_parser import (  # noqa: E402
    AreaParser, flag_bit, format_area_name, parse_flag_value, split_area_name)

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


# Where the game puts you when you recall or die. A room that teleports
# you to one of these is throwing you out, not carrying you somewhere:
# the House of Pancakes in wyvern.are is the joke version, reached by six
# decoy objects in the Oak Tree Square, and the router used to publish
# "crawl hole" as the way to Wyvern's Tower because of it.
EJECT_ROOMS = {4207, 4208}      # ROOM_VNUM_TEMPLE, ROOM_VNUM_ALTAR


# ITEM_MANIPULATION value[0]. 10 answers to any of them; 9 in value[4]
# means the object acts on the room it sits in, so it leads nowhere.
MANIP_VERB = {1: "flip", 2: "move", 3: "pull", 4: "push", 5: "turn",
              6: "climb", 7: "climb", 8: "crawl", 9: "jump", 10: "enter",
              11: "burn", 12: "bomb", 13: "play", 14: "feed"}
MANIP_TOOL = {11: "needs a lit candle", 12: "needs a bomb",
              13: "needs an instrument", 14: "needs bait"}
PUZZLE_CURRENT_ROOM = 9

# Hyrule's hidden ways are not doors. The exit is secret until the NES's
# act opens it -- BOMB, BURN, PUSH, PLAY or FEED at the object lying in the
# room, with the tool in hand -- and OPEN by its keyword is refused
# (hyrule_seal_refuses in src/act_move.c). The exit's keyword starts with
# the word that names the seal; this is what a route has to say instead of
# "open <keyword>", and what it needs. See Plan 7 in wiki/hyrule-area.md.
HYRULE_SEALS = {
    "bomb": ("bomb cracked", "needs a bomb, which it uses up"),
    "cracked": ("bomb cracked", "needs a bomb, which it uses up"),
    "burn": ("burn bush", "needs a lit candle"),
    "armos": ("push armos", ""),
    "grave": ("push gravestone", ""),
    "block": ("push block", ""),
    "bracelet": ("push stone", "needs the Power Bracelet"),
    "recorder": ("play recorder", "needs the Recorder"),
    "hungry": ("feed goriya", "needs bait"),
    "triforce": ("bomb cracked", "needs all eight Triforce pieces and a bomb"),
}


HYRULE_ROOMS = range(30200, 30800)

# Portals that let only the carrier of an object through (value[4]), named
# for the route rather than by vnum.
NEEDED_OBJECTS = {30276: "the Power Bracelet", 30411: "the raft",
                  30412: "the stepladder"}


def seal_for(from_vnum, lock, keyword):
    """(command, need) for a Hyrule seal, or None for an ordinary door."""
    if from_vnum not in HYRULE_ROOMS or lock != 4 or not keyword:
        return None
    return HYRULE_SEALS.get(keyword.split()[0].lower())


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
                cost = f"needs {NEEDED_OBJECTS.get(need, f'object {need}')}"

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


def load_ejectors():
    """Rooms that teleport whoever stands in them back to the Temple.

    They are traps and exits, not passages: the House of Pancakes tells
    you the ceiling crushed you and then puts you on the altar. Walking a
    player into one is never directions.
    """
    out = set()
    listed = [l.strip() for l in (AREA / "area.lst").read_text("latin-1").splitlines()
              if l.strip() and not l.strip().startswith("$")]

    for fname in listed:
        path = AREA / fname
        if not path.is_file():
            continue
        m = re.search(r"^#ROOMS\s*$(.*?)^#0\s*$",
                      path.read_text("latin-1"), re.S | re.M)
        if not m:
            continue
        for blk in re.split(r"\n(?=#\d+[ \t\r\n])", m.group(1)):
            h = re.match(r"#(\d+)[ \t]*(.*?)~", blk, re.S)
            fl = re.search(r"\n~\n(.*)", blk, re.S)
            if not h or not fl:
                continue
            tok = fl.group(1).split()
            if len(tok) < 3 or not (set("EF") & set(tok[1])):
                continue
            rest = tok[4:] if "Z" in tok[1] else tok[3:]
            if rest and rest[0].lstrip("-").isdigit() \
               and int(rest[0]) in EJECT_ROOMS:
                out.add(int(h.group(1)))
    return out


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
            if dest <= 0 or dest in EJECT_ROOMS:
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
        # An area built in game (ANEW) is headed #AREADATA, Name <text>~.
        dm = re.search(r"^#AREADATA\b.*?^\s*Name\s+(.*?)~", text, re.S | re.M)
        am = dm or re.search(r"#AREA\s+(.*?)~", text, re.S)
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

        seal = seal_for(from_vnum, lock, keyword)
        if seal is not None:
            flush()
            out.append(seal[0])
        elif lock != 0:
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
        seal = seal_for(from_vnum, lock, keyword)
        if seal is not None:
            flush()
            steps.append(seal[0] + (f" ({seal[1]})" if seal[1] else ""))
        elif lock != 0:
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


def load_landmarks():
    """Where each named mob and object is reset: name -> [room vnum].

    Reset lines carry the vnum; the names come from the #MOBILES and
    #OBJECTS records they point at.
    """
    names = {}          # ("M"|"O", vnum) -> short description
    placed = {}         # ("M"|"O", vnum) -> [room vnum]

    listed = [l.strip() for l in (AREA / "area.lst").read_text("latin-1").splitlines()
              if l.strip() and not l.strip().startswith("$")]

    for fname in listed:
        path = AREA / fname
        if not path.is_file():
            continue
        text = path.read_text("latin-1")

        for kind, section in (("M", "MOBILES"), ("O", "OBJECTS")):
            m = re.search(rf"^#{section}\s*$(.*?)^#0\s*$", text, re.S | re.M)
            if not m:
                continue
            for blk in re.split(r"\n(?=#\d+[ \t\r\n])", m.group(1)):
                h = re.match(r"#(\d+)[ \t]*(.*?)~\s*\n(.*?)~", blk, re.S)
                if h:
                    names[(kind, int(h.group(1)))] = h.group(3).strip()

        m = re.search(r"^#RESETS\s*$(.*?)^S\s*$", text, re.S | re.M)
        if not m:
            continue
        for line in m.group(1).splitlines():
            r = re.match(r"^([MO])\s+-?\d+\s+(\d+)\s+-?\d+\s+(\d+)", line.strip())
            if r:
                placed.setdefault((r.group(1), int(r.group(2))), []).append(
                    int(r.group(3)))

    landmarks = {}
    for key, where in placed.items():
        label = names.get(key)
        if label:
            landmarks.setdefault(normalise(label), []).extend(where)
    return landmarks


def match_landmark(name, rooms, reach, landmarks):
    """The room a route named after a thing is trying to reach.

    Tries the room names first -- a route called "Bright White Light" may
    simply be a room -- then the mobs and objects the name could mean. A
    plural in the handed-down name ("Hobgoblins") is matched against the
    singular the world uses.
    """
    # "Pitch Black Opal (path 2)" is the same landmark as path 1; the
    # qualifier tells two routes apart, not two destinations.
    want = normalise(re.sub(r"\(.*?\)", " ", name))
    if not want:
        return None

    singular = want[:-1] if want.endswith("s") else want
    candidates = []

    for vnum in reach:
        room_name = normalise(rooms[vnum]["name"])
        if room_name and (room_name == want or want in room_name
                          or singular in room_name):
            candidates.append(vnum)

    if not candidates:
        for label, where in landmarks.items():
            if label and (label == want or want in label or singular in label):
                candidates.extend(v for v in where if v in reach)

    if not candidates:
        return None

    # Closest to the start: a route should be the short way there.
    return min(candidates, key=lambda v: len(reach[v]))


def area_entrances(rooms, reach):
    """The nearest reachable room of each area, which is its way in."""
    best = {}
    for vnum, path in reach.items():
        area = rooms[vnum]["area"]
        if area not in best or len(path) < len(best[area][1]):
            best[area] = (vnum, path)
    return best



# Help files are Latin-1 with CRLF and ~-terminated strings, and the
# game is strict about all three.
HELP_EOL = chr(13) + chr(10)


def write_route_help(routes):
    """A help topic naming every area a player can walk to.

    Generated rather than hand-kept: 89 entries go stale the first
    time somebody adds an area, and a help file that lies about where
    you can go is worse than not having one. Alphabetical, because
    this is a lookup list -- you read a name off it and hand that name
    to WALK.
    """
    entries = sorted(
        ((r.get("area_display") or r["area"]), r.get("rooms_away") or 0)
        for r in routes)

    lines = [
        "0 WALKTO ROUTELIST AREALIST~",
        "Syntax: walkto                  how it works, and the guild halls",
        "        walkto <place>          walk there from wherever you are",
        "        walkto guilds           the guild halls and the guild clerk",
        "        walkto trainers         every guildmaster and trainer",
        "        walkto areas            every area, in columns",
        "        walkto quest            to where the quest master sent you",
        "        walkto stop             stop walking",
        "",
        "WALKTO finds the way from the room you are standing in and walks",
        "it for you, a room every half second, opening doors that are shut",
        "but not locked.  Name a place by any part of its name: WALKTO",
        "TEMPLE, WALKTO MORIA, WALKTO NECRO MASTER, WALKTO MAGE GUILD.",
        "",
        "You stop when you arrive, when you type any other command, when a",
        "fight starts, when you sit, rest or sleep, when you run out of",
        "movement, or when the way ahead is locked, guarded or gone.  It",
        "never walks you into a death trap, past a guild guard who would",
        "turn you away, or through a portal that takes a fare.  A few areas",
        "need a wait or a key it cannot manage for you; it says so, and",
        "ROUTES on the website gives the commands.",
        "",
        "Every area you can walk to, and how many rooms out it is from the",
        "Oak Tree Square.  In Mudlet, WALK <name> follows the same routes",
        "on the map; on the website and in the browser client they are",
        "listed with the commands to get there.",
        "",
        "The number is rooms travelled, not difficulty.  A short walk can",
        "end somewhere that will kill you, and a long one can be perfectly",
        "safe.  See ROUTES.",
        "",
    ]

    # Two columns. A name is given 32 characters, which is the longest
    # in the world plus a little, so nothing is truncated.
    labels = ["%4d  %s" % (away, name) for name, away in entries]
    half = (len(labels) + 1) // 2
    left, right = labels[:half], labels[half:]
    for index in range(half):
        a = left[index]
        b = right[index] if index < len(right) else ""
        lines.append(("  %-38s%s" % (a, b)).rstrip())

    lines += [
        "",
        "Dresden is not listed because it holds the Oak Tree Square, which",
        "is where every route begins.  The Quest Zone and Temple Despair",
        "are not listed because nothing in the world links to them.",
        "",
        "See also: ROUTES, WALK, MAP, MUDLET, AREAS, GUILDS, TEACHLIST",
        "~",
        "",
        "0 $~",
        "",
        "#$",
        "",
    ]

    body = "#HELPS" + HELP_EOL + HELP_EOL + HELP_EOL.join(lines)
    out = pathlib.Path("area/routelist.are")
    with open(out, "w", encoding="latin-1", newline="") as fh:
        fh.write(body)
    return len(entries)


# --- Trainers, guild halls and the WALKTO destinations ---------------------
#
# The game's own tables are the authority on who teaches what and who
# guards which door, so they are read from the C source rather than kept
# a second time here: guildmaster_table in src/const.c and gg_table in
# src/special.c.

CONST_C = pathlib.Path("src/const.c")
SPECIAL_C = pathlib.Path("src/special.c")

CLASS_WORD = {"CLASS_ANY": "any", "CLASS_MAGE": "mage",
              "CLASS_CLERIC": "cleric", "CLASS_THIEF": "thief",
              "CLASS_WARRIOR": "warrior", "CLASS_MONK": "monk",
              "CLASS_NECRO": "necromancer", "CLASS_OTHER": "other"}
GUILD_WORD = {"GUILD_MAGE": "mage", "GUILD_CLERIC": "cleric",
              "GUILD_THIEF": "thief", "GUILD_WARRIOR": "warrior",
              "GUILD_MONK": "monk", "GUILD_NECRO": "necro",
              "GUILD_ANY": "any", "GUILD_NONE": "none"}
PLURAL = {"mage": "mages", "cleric": "clerics", "thief": "thieves",
          "warrior": "warriors", "monk": "monks",
          "necromancer": "necromancers", "necro": "necromancers"}

# HELP GUILDS names the six halls; gg_table says where their guards stand.
GUILD_ORDER = ("mage", "cleric", "thief", "warrior", "monk", "necro")
GUILD_HALLS = {"mage": "University of Magic", "cleric": "Temple of Breas",
               "thief": "House of Thieves", "warrior": "Citadel of War",
               "monk": "Palm of the Creator", "necro": "Morgue of Dresden"}
GUILD_KEYWORDS = {
    "mage": "mage mages magic magician wizard university",
    "cleric": "cleric clerics priest priests breas",
    "thief": "thief thieves rogue rogues",
    "warrior": "warrior warriors fighter fighters citadel war",
    "monk": "monk monks palm creator",
    "necro": "necro necros necromancer necromancers morgue",
}
GUARD_DOOR = {"north": 0, "east": 1, "south": 2, "west": 3, "up": 4,
              "down": 5}
HALL_MAX_ROOMS = 160            # GUILD_HALL_MAX_ROOMS in src/special.c

ACT_TRAIN = flag_bit("J")
ACT_PRACTICE = flag_bit("K")

# Places a player asks for by name that are neither an area nor a mob.
# ROOM_VNUM_TEMPLE and ROOM_VNUM_ALTAR in src/merc.h.
PLACES = (
    (START, "Oak Tree Square", "square oak tree start dresden"),
    (4207, "Temple of Devota", "temple devota recall"),
    (4208, "Temple Altar", "altar stash temple"),
)


def load_guildmasters():
    """guildmaster_table: [{mob, class, guild, teaches, gains}]."""
    text = CONST_C.read_text("latin-1")
    m = re.search(r"guildmaster_table\s*\[\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        return []
    body = re.sub(r"/\*.*?\*/", " ", m.group(1), flags=re.S)
    out = []
    # The Fire mage's entry ends "}, }," -- a trailing comma C allows --
    # and without the ,? this read straight on into the next master and
    # lost the Adept of Soulcrusher inside the Fire mage's gain list.
    for e in re.finditer(r"\{\s*(\d+)\s*,\s*(CLASS_\w+)\s*,\s*(GUILD_\w+)\s*,"
                         r"\s*\{(.*?)\}\s*,\s*\{(.*?)\}\s*,?\s*\}", body, re.S):
        if int(e.group(1)) == 0:
            continue
        out.append({"mob": int(e.group(1)),
                    "class": CLASS_WORD.get(e.group(2), "any"),
                    "guild": GUILD_WORD.get(e.group(3), "any"),
                    "teaches": re.findall(r'"([^"]*)"', e.group(4)),
                    "gains": re.findall(r'"([^"]*)"', e.group(5))})
    return out


def load_guild_guards():
    """gg_table: [{mob, room, door, class, guild}], one per guarded door."""
    text = SPECIAL_C.read_text("latin-1")
    m = re.search(r"gg_table\s*\[\]\s*=\s*\{(.*?)\n\s*\};", text, re.S)
    if not m:
        return []
    out = []
    for e in re.finditer(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*do_(\w+)\s*,"
                         r"\s*(CLASS_\w+)\s*,\s*(GUILD_\w+)\s*,", m.group(1)):
        if int(e.group(1)) == 0 or e.group(3) not in GUARD_DOOR:
            continue
        out.append({"mob": int(e.group(1)), "room": int(e.group(2)),
                    "door": GUARD_DOOR[e.group(3)],
                    "class": CLASS_WORD.get(e.group(4), "any"),
                    "guild": GUILD_WORD.get(e.group(5), "any")})
    return out


def guild_halls(rooms, guards, carried=None):
    """guild -> {rooms, doors, class}: what lies behind each hall's guards.

    Walked the way guild_closed_rooms() in src/special.c walks it: from
    the room past a guard, never stepping back into a guard post, and a
    walk that grows past HALL_MAX_ROOMS has found the open world rather
    than a hall. The Templar of Devota guards a class, not a guild, and
    is not a hall anybody joins.

    `carried` is the teleport rooms (load_teleports): the monks' Palm of
    the Creator is a room with no exits that carries you on into the
    Quiet Place, where the masters are.
    """
    carried = carried or {}
    posts = {g["room"] for g in guards}
    halls = {}
    for g in guards:
        if g["guild"] not in GUILD_HALLS:
            continue
        way = rooms.get(g["room"], {}).get("exits", {}).get(g["door"])
        if way is None or way[0] not in rooms:
            continue
        hall = halls.setdefault(g["guild"], {"rooms": set(), "doors": [],
                                             "class": g["class"]})
        hall["doors"].append(way[0])
        if way[0] in hall["rooms"]:
            continue
        seen, queue, open_world = {way[0]}, [way[0]], False
        while queue and not open_world:
            here = queue.pop(0)
            onward = [rooms[here]["exits"][door][0] for door in range(10)
                      if door in rooms[here]["exits"]]
            # Only the hall's own door may carry you in. A room deeper
            # inside that carries you somewhere is a way back out --
            # the monks' "Back to the beginning" -- not more hall.
            if here == way[0]:
                onward += [edge[2] for edge in carried.get(here, [])
                           if edge[0] == "wait"]
            for to in onward:
                if to in posts or to in seen or to not in rooms:
                    continue
                if len(seen) >= HALL_MAX_ROOMS:
                    open_world = True
                    break
                seen.add(to)
                queue.append(to)
        if not open_world:
            hall["rooms"] |= seen
    return halls


def members_phrase(guild, guard_class):
    """Who a hall's guard lets in, in words."""
    if guard_class not in ("any", "other"):
        return "%s of the %s guild" % (PLURAL.get(guard_class, guard_class),
                                       guild)
    return "members of the %s guild" % guild


def learners_phrase(cls, guild):
    """Who a guildmaster will teach, as do_practice decides it."""
    if cls == "any" and guild == "any":
        return "anyone"
    if cls == "other":
        return "members of the %s guild who are not %s" % (
            guild, PLURAL.get(guild, guild))
    if guild == "any":
        return "%s only" % PLURAL.get(cls, cls)
    if cls == "any":
        return "members of the %s guild" % guild
    return "%s of the %s guild" % (PLURAL.get(cls, cls), guild)


def short_name(desc):
    """A mob's short description as a name: "the Necro Guild Master" is
    "Necro Guild Master", "Seraloi, the lost." is "Seraloi, the lost"."""
    text = re.sub(r"\{(?:[0-9A-Fa-f]{2}|.)", "", desc or "")
    text = " ".join(text.split()).rstrip(".")
    if text.lower().startswith("the "):
        text = text[4:]
    return text[:1].upper() + text[1:]


def place_name(rooms, vnum, hall_of):
    """Where a room is, for a person: its guild hall, or its area."""
    guild = hall_of.get(vnum)
    if guild:
        return GUILD_HALLS[guild]
    area = rooms[vnum]["area"]
    return split_area_name(area)[1] or area


def route_fields(rooms, reach, vnum):
    path = reach[vnum]
    return {"room": rooms[vnum]["name"], "vnum": vnum,
            "commands": to_commands(rooms, path),
            "steps": describe(rooms, path), "rooms_away": len(path)}


def _words(text):
    """Keywords once each, in the order first given."""
    seen, out = set(), []
    for word in str(text or "").lower().split():
        if word not in seen:
            seen.add(word)
            out.append(word)
    return " ".join(out)


def build_trainers(rooms, reach, carried=None):
    """Every guild hall, the guild clerk, and every trainer, routed.

    A trainer is a guildmaster_table entry whose mobile can practise
    (ACT_PRACTICE, which do_practice and do_gain both demand), or any
    mobile that trains stats (ACT_TRAIN, which do_train asks for). The
    router does not model guild guards -- it publishes the members' way
    in -- so each entry says who the guard admits in `members_only`.
    """
    guards = load_guild_guards()
    halls = guild_halls(rooms, guards, carried)
    hall_of = {room: guild for guild in GUILD_ORDER if guild in halls
               for room in halls[guild]["rooms"]}

    parser = AreaParser(AREA)
    parser.parse_all()
    mobiles = parser.mobiles
    masters = {g["mob"]: g for g in load_guildmasters()}

    out = []
    for guild in GUILD_ORDER:
        hall = halls.get(guild)
        if not hall:
            continue
        doors = [d for d in hall["doors"] if d in reach]
        if not doors:
            continue
        door = min(doors, key=lambda v: (len(reach[v]), v))
        entry = {
            "name": "%s (%s guild)" % (GUILD_HALLS[guild], guild),
            "role": "guild hall",
            "class": hall["class"],
            "guild": guild,
            "members_only": guild,
            "who": members_phrase(guild, hall["class"]),
            "place": GUILD_HALLS[guild],
            "keywords": "guild hall " + GUILD_KEYWORDS[guild],
        }
        entry.update(route_fields(rooms, reach, door))
        out.append(entry)

    for vnum in sorted(parser.mob_specials):
        if parser.mob_specials[vnum] != "spec_guild_clerk":
            continue
        mob = mobiles.get(vnum)
        placed = [r for r in (mob.spawn_rooms if mob else []) if r in reach]
        if not placed:
            continue
        room = min(placed, key=lambda v: (len(reach[v]), v))
        short = short_name(mob.short_desc)
        entry = {
            "name": "%s, the guild clerk" % short,
            "role": "guild clerk",
            "class": "any",
            "guild": "any",
            "members_only": "",
            "who": "anyone who has never joined a guild, levels 3 to 6",
            "place": place_name(rooms, room, hall_of),
            "keywords": "%s guild clerk join" % mob.keywords,
            "mob": vnum,
        }
        entry.update(route_fields(rooms, reach, room))
        out.append(entry)

    found = []
    candidates = set(masters) | {
        v for v, m in mobiles.items()
        if parse_flag_value(m.act_flags) & ACT_TRAIN}
    for vnum in sorted(candidates):
        mob = mobiles.get(vnum)
        if mob is None:
            continue
        acts = parse_flag_value(mob.act_flags)
        master = masters.get(vnum) if acts & ACT_PRACTICE else None
        trains = bool(acts & ACT_TRAIN)
        if master is None and not trains:
            continue
        placed = [r for r in mob.spawn_rooms if r in reach]
        if not placed:
            continue
        room = min(placed, key=lambda v: (len(reach[v]), v))
        guild = hall_of.get(room, "")
        short = short_name(mob.short_desc)
        place = place_name(rooms, room, hall_of)
        words = [mob.keywords, "trainer"]
        if master:
            words += ["guildmaster", "practice", "gain", "teacher"]
            cls, gld = master["class"], master["guild"]
            for name in (cls, gld):
                if name in GUILD_KEYWORDS:
                    words.append(GUILD_KEYWORDS[name])
                elif name == "necromancer":
                    words.append(GUILD_KEYWORDS["necro"])
        else:
            cls, gld = "any", "any"
        if trains:
            words += ["train", "stats"]
        if guild:
            words.append(GUILD_KEYWORDS[guild])
        entry = {
            "name": "%s (%s)" % (short, place),
            "role": ("guildmaster" if master and master["gains"]
                     else "practice" if master else "train"),
            "class": cls,
            "guild": gld,
            "members_only": guild,
            "who": (members_phrase(guild, halls[guild]["class"])
                    if guild else "anyone"),
            "learners": learners_phrase(cls, gld) if master else "anyone",
            "place": place,
            "keywords": " ".join(" ".join(words).split()),
            "mob": vnum,
            "teaches": master["teaches"] if master else [],
            "gains": master["gains"] if master else [],
            "trains": trains,
        }
        entry.update(route_fields(rooms, reach, room))
        rank = GUILD_ORDER.index(guild) if guild else len(GUILD_ORDER)
        found.append(((rank, place.lower(), entry["rooms_away"],
                       entry["name"].lower()), entry))

    # Two mobiles with one name in one room are one destination (the
    # pirates on the Levee); one name in two rooms is told apart by the
    # room (New Thalos has four mobiles called "the guildmaster").
    ordered = [entry for _key, entry in sorted(found, key=lambda f: f[0])]
    rooms_by_name = collections.defaultdict(set)
    for entry in ordered:
        rooms_by_name[entry["name"]].add(entry["vnum"])
    kept = set()
    for entry in ordered:
        if (entry["name"], entry["vnum"]) in kept:
            continue
        kept.add((entry["name"], entry["vnum"]))
        if len(rooms_by_name[entry["name"]]) > 1:
            entry["name"] = "%s (%s, %s)" % (
                short_name(mobiles[entry["mob"]].short_desc), entry["place"],
                entry["room"].rstrip("."))
        out.append(entry)

    for entry in out:
        entry["keywords"] = _words(entry["keywords"])
    return out


def build_places(rooms, reach):
    out = []
    for vnum, name, keywords in PLACES:
        if vnum not in rooms or vnum not in reach:
            continue
        entry = {"name": name, "role": "place",
                 "place": split_area_name(rooms[vnum]["area"])[1],
                 "keywords": keywords}
        entry.update(route_fields(rooms, reach, vnum))
        out.append(entry)
    return out


def _field(text):
    """One tab-separated field: no tabs, no line breaks, never empty."""
    text = " ".join(str(text or "").split())
    return text or "-"


def write_walkto_data(payload, out=pathlib.Path("area/walkto.dat")):
    """What the WALKTO command can walk to, for the game to read at boot.

    Generated from the same payload as webadmin/directions.json, so the
    command, the website and the Oracle name the same places. The game
    finds its own way from wherever the player stands; all it needs from
    here is a name and a room. Order matters: when two places match a
    name equally well, the earlier one wins, so the places and the guild
    halls come before the trainers inside them, and those before areas.
    """
    rows = []
    for place in payload.get("places", []):
        rows.append(("place", place["vnum"], place["name"],
                     place.get("place", ""), place.get("keywords", ""), ""))
    kinds = {"guild hall": "guild", "guild clerk": "clerk"}
    for entry in payload.get("trainers", []):
        rows.append((kinds.get(entry["role"], "trainer"), entry["vnum"],
                     entry["name"], entry.get("place", ""),
                     entry.get("keywords", ""),
                     entry.get("who", "") if entry.get("members_only") else ""))
    for route in sorted(payload.get("routes", []),
                        key=lambda r: (r.get("area_display") or r["area"]).lower()):
        rows.append(("area", route["vnum"],
                     route.get("area_display") or route["area"], "", "", ""))

    lines = [
        "# WALKTO destinations, generated by tools/build_directions.py.",
        "# Do not edit: change the generator or the world and regenerate.",
        "# kind<TAB>room vnum<TAB>name<TAB>place<TAB>keywords<TAB>who may enter",
    ]
    for kind, vnum, name, place, keywords, who in rows:
        lines.append("\t".join((kind, str(int(vnum)), _field(name),
                                _field(place), _field(keywords),
                                _field(who))))
    with open(out, "w", encoding="latin-1", errors="replace",
              newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(rows)


def main():
    rooms = load_world()
    portals = load_portals()

    # Kept before the teleports are merged in: a teleport carries you
    # on a timer with no command to send, so it is a way through for
    # routing but not something a client can be told to walk.
    object_links = {room: list(edges) for room, edges in portals.items()}

    for room, edges in load_teleports().items():
        portals.setdefault(room, []).extend(edges)

    # A room that throws you back to the Temple is a trap, not a way
    # anywhere, and must not be walked into or counted as an entrance.
    for vnum in load_ejectors():
        rooms.pop(vnum, None)

    reach = shortest_paths(rooms, START, portals)
    entrances = area_entrances(rooms, reach)

    routes = []
    for area, (vnum, path) in sorted(entrances.items()):
        if vnum == START or not path:
            continue
        routes.append({
            # Shown, searched and sorted on, so it leads with the zone.
            # `area` keeps the file's own wording because match_area and
            # the parity test both compare against it.
            "name": format_area_name(area),
            "commands": to_commands(rooms, path),
            "steps": describe(rooms, path),
            "room": rooms[vnum]["name"],
            "vnum": vnum,
            "area": area,
            "area_display": format_area_name(area),
            "rooms_away": len(path),
            "status": "computed",
        })

    # The handed-down list, checked and repaired where it has drifted.
    by_area = {r["area"]: r for r in routes}
    legacy_path = pathlib.Path("tools/legacy_routes.json")
    legacy = []
    landmarks = load_landmarks()

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
                "area_display": format_area_name(room.get("area", "")),
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
                    entry["fixed_area_display"] = format_area_name(
                        fixed["area"])
                else:
                    # Some of these aim at a thing rather than an area --
                    # an opal, a light, a nest of hobgoblins -- so look for
                    # what the route is named after and walk to that.
                    landmark = match_landmark(name, rooms, reach, landmarks)
                    if landmark is not None:
                        path = reach[landmark]
                        entry["fixed_commands"] = to_commands(rooms, path)
                        entry["fixed_steps"] = describe(rooms, path)
                        entry["fixed_room"] = rooms[landmark]["name"]
                        entry["fixed_area"] = rooms[landmark]["area"]
                        entry["fixed_area_display"] = format_area_name(
                            rooms[landmark]["area"])

            legacy.append(entry)

    # Every way through that is not a compass direction: a portal you
    # enter, a rope you climb, a cabinet you step into. Mudlet calls
    # these special exits and walks one by sending its command.
    links = []
    for room in sorted(object_links):
        if room not in rooms:
            continue
        for verb, keyword, dest, _cost, _label in object_links[room]:
            if dest not in rooms or not verb or not keyword:
                continue
            links.append({"from": room,
                          "command": "%s %s" % (verb, keyword),
                          "to": dest})

    # Every guild hall, the guild clerk and every trainer, and the few
    # named places that are neither: the destinations WALKTO knows
    # besides the areas, and what the Oracle answers "where do I
    # practise" from.
    trainers = build_trainers(rooms, reach, portals)
    places = build_places(rooms, reach)

    payload = {
        "start": {"vnum": START, "room": rooms[START]["name"],
                  "area": rooms[START]["area"],
                  "area_display": format_area_name(rooms[START]["area"])},
        "counts": {
            "computed": len(routes),
            "legacy_ok": sum(1 for e in legacy if e["status"] == "verified"),
            "legacy_drifted": sum(1 for e in legacy if e["status"] == "drifted"),
            "legacy_repaired": sum(1 for e in legacy if "fixed_commands" in e),
            "links": len(links),
            "trainers": len(trainers),
            "places": len(places),
        },
        "routes": routes,
        "legacy": legacy,
        "links": links,
        "trainers": trainers,
        "places": places,
    }

    out = pathlib.Path("webadmin/directions.json")
    out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    listed = write_route_help(routes)
    print(f"{listed} areas listed in area/routelist.are")
    walkable = write_walkto_data(payload)
    print(f"{walkable} WALKTO destinations in area/walkto.dat "
          f"({len(trainers)} guild halls, clerks and trainers)")
    print(f"{len(rooms)} rooms, {len(reach)} reachable from {START} "
          f"({sum(len(v) for v in portals.values())} portals and "
          f"handholds in play)")
    print(f"{len(routes)} areas routed, "
          f"{payload['counts']['legacy_ok']} handed-down routes still good, "
          f"{payload['counts']['legacy_repaired']} repaired -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
