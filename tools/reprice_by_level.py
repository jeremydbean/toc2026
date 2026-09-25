"""Reprice the bottom of the economy so a new character can afford it.

An item's price should be worth a certain number of kills to the character
who can use it. Measured across the world that relationship already holds
from level 10 upwards: the median object costs somewhere between fourteen
and ninety kills of a mobile its own level, clustering near forty. Below
level 10 it collapses, because the income table in `load_mobiles` steps
rather than curves -- a level 4 mobile carries one to eight copper, a
level 5 one carries about five silver, and a level 10 one about five gold.
Prices did not step with it.

What that costs a player, before this ran:

    item level   median price      kills to afford it
      1 -  4         20g - 1p75g      1,000,000
      5 -  9         1p - 2p50g           2,801
     10 - 14         3p                      59
     20 - 24         5p                      43
     40 - 44         10p75g                  23

A turkey burger in Mud School cost ten gold. A level 1 mobile carries one
or two copper. That is sixty-six thousand kills for a burger, in an area
with about forty mobiles in it, and every character in the game starts
there with nothing.

So: for objects whose buyer is below level 10, scale the price to the
target the rest of the world already keeps. One factor per level, applied
to everything at that level, so every ratio a builder chose -- a pot pie
against a loaf, a hard leather jerkin against a plain one -- survives
exactly. Nothing at level 10 or above is touched, and no price is ever
raised.

This does not touch the other end, where the same measurement says the
median level 50 object costs three kills. That is not the prices: it is
the last step in the income table, which hands a level 50 mobile about
thirteen platinum. Fixing it means changing what every high-level
character earns, which is a separate decision.

Who the buyer is:

  * for anything a shop stocks, the shop. A shelf serves one bracket and
    moves as one, and the median level of the levelled things on it says
    which bracket -- falling back to the area's other shops when the shelf
    is mostly unlevelled goods with a stray levelled thing on it. Pricing
    each item on a shelf by its own level instead pulls the shelf apart:
    Dresden's leather worker stocks a level 5 hard leather jerkin among an
    otherwise level 10 set, and by item level the body piece came out a
    tenth the price of the cap. Forty-four such inversions across thirteen
    shops. An object two shops carry takes the lower, so the neediest
    buyer sets the price.
  * for everything else, the object's own level. Loot never shares a
    shelf, and its price is only ever what a shop will pay for it.
  * an object with neither keeps its price. There is no signal to price it
    by and a guess is worse than leaving it alone.

The shop is also the only honest reading for Dresden, whose `#AREA` line
says "ALL" and whose mobiles run to level 60 while its leather worker
stocks nothing above level 10.

The object section is read as the game reads it -- a stream of tokens,
not lines -- and only the cost token is rewritten, in place, by byte
offset. See `tools/costs_to_copper.py`, which this borrows its reader
from and which explains the four shapes a line-based parser gets wrong.

    python3 tools/reprice_by_level.py             # report
    python3 tools/reprice_by_level.py --verbose   # every change
    python3 tools/reprice_by_level.py --apply     # write
"""
from __future__ import annotations

import collections
import pathlib
import re
import statistics
import sys

AREA = pathlib.Path("area")

ITEM_FLAGS2 = 1 << 25          # (Z), the second extra-flag word's marker
MAX_TRADE = 5                  # buy_type slots in a #SHOPS record

# How many levelled things a shop must stock before its own shelf is
# taken as evidence of who shops there.
MIN_STOCK_FOR_OWN_LEVEL = 3

# The level from which prices already line up with income, measured: the
# median object between 10 and 49 costs between fourteen and ninety kills
# of a mobile its own level. Nothing at or above this is touched. Some of
# those levels do sit two to four times above the world median, but that
# is builder variation, and cutting it would also cut what a player of
# that level gets for selling the same loot.
HEALTHY_FROM = 10

# Everyday goods, where the object's own level is not evidence of
# anything. A bowl of grits in Mud School is marked level 5 and a turkey
# burger on the same tray is level 1; nobody decided that. For these the
# shop is the better witness, and it keeps one shelf on one scale.
EVERYDAY_TYPES = frozenset((
    1,      # ITEM_LIGHT
    13,     # ITEM_TRASH
    15,     # ITEM_CONTAINER
    17,     # ITEM_DRINK_CON
    18,     # ITEM_KEY
    19,     # ITEM_FOOD
))

# The number of kills the median object costs between levels 10 and 49.
# Measured, not chosen: see the table in the docstring.
TARGET_KILLS = 40

# How close to the target a level has to be before it is left alone.
SETTLED_WITHIN = 0.05


def earn(level: int) -> int:
    """Expected copper from one kill of a mobile this level.

    Mirrors the `total == 0` branch of load_mobiles() in src/db.c, which
    is what almost every mobile takes: a wealth of zero in the area file
    means roll it from the level. Each line is the mean of its
    number_range, in copper.
    """
    L = max(1, int(level))
    if L < 5:                                   # copper 1..2L
        return L
    if L < 10:                                  # silver 1..2L, copper 1..4L
        return 100 * L + 2 * L
    if L < 20:                                  # gold 1..L, silver, copper
        return 10000 * L // 2 + 100 * L + 4 * L
    if L < 30:
        return 10000 * L + 200 * L + 8 * L
    if L < 50:
        return 15000 * L + 300 * L + 6 * L
    return 1000000 * L // 4 + 20000 * L + 400 * L + 2 * L


def tidy(copper: float) -> int:
    """Two significant figures, and never free.

    A scaled price lands on something like 15,347 copper. Nobody writes a
    price like that, and the extra digits claim a precision the model does
    not have.
    """
    value = int(round(copper))
    if value <= 0:
        return 1
    if value < 100:
        return value
    digits = len(str(value))
    step = 10 ** (digits - 2)
    return max(1, int(round(value / step)) * step)


# --------------------------------------------------------------- reading

class Stream:
    """Just enough of the game's readers to walk a record."""

    def __init__(self, text: str, pos: int = 0):
        self.text = text
        self.pos = pos

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def eol(self) -> None:
        end = self.text.find("\n", self.pos)
        self.pos = len(self.text) if end < 0 else end + 1

    def string(self) -> str:
        self.skip_space()
        end = self.text.find("~", self.pos)
        if end < 0:
            raise ValueError("unterminated string")
        out = self.text[self.pos:end]
        self.pos = end + 1
        return out

    def token(self) -> tuple[str, int, int]:
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and not self.text[self.pos].isspace():
            self.pos += 1
        if start == self.pos:
            raise ValueError("expected a token")
        return self.text[start:self.pos], start, self.pos

    def number(self) -> int:
        """fread_number: a signed run of digits, and nothing after it."""
        self.skip_space()
        sign = 1
        if self.pos < len(self.text) and self.text[self.pos] in "+-":
            sign = -1 if self.text[self.pos] == "-" else 1
            self.pos += 1
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise ValueError("expected a number")
        return sign * int(self.text[start:self.pos])

    def letter(self) -> str:
        self.skip_space()
        if self.pos >= len(self.text):
            raise ValueError("expected a letter")
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def flag(self) -> tuple[str, int, int]:
        """A flag, including the way fread_flag mishandles a minus sign."""
        self.skip_space()
        if self.pos < len(self.text) and self.text[self.pos] == "-":
            return "0", self.pos, self.pos      # consumed nothing
        return self.token()


def flag_value(token: str) -> int:
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    total = 0
    for ch in token:
        if "A" <= ch <= "Z":
            total |= 1 << (ord(ch) - ord("A"))
        elif "a" <= ch <= "z":
            total |= 1 << (26 + ord(ch) - ord("a"))
    return total


def section(text: str, name: str) -> tuple[int, int] | None:
    m = re.search(r"^#%s\s*$" % name, text, re.M)
    if not m:
        return None
    nxt = re.compile(r"^#[A-Z$]", re.M).search(text, m.end())
    return m.end(), (nxt.start() if nxt else len(text))


def read_objects(text: str) -> list[dict]:
    """Every object's vnum, type, level and the span its cost token fills."""
    bounds = section(text, "OBJECTS")
    if bounds is None:
        return []
    start, limit = bounds

    stream = Stream(text, start)
    out: list[dict] = []
    while True:
        stream.skip_space()
        if stream.pos >= limit or text[stream.pos] != "#":
            break
        stream.pos += 1
        vnum_token, _, _ = stream.token()
        if not re.fullmatch(r"-?\d+", vnum_token) or int(vnum_token) == 0:
            break

        try:
            for _ in range(4):                  # name, short, long, material
                stream.string()
            item_type, _, _ = stream.token()
            extra, _, _ = stream.flag()
            if flag_value(extra) & ITEM_FLAGS2:
                stream.flag()
            stream.flag()                       # wear flags
            for _ in range(5):                  # value[0..4]
                stream.flag()
            level_token, _, _ = stream.token()
            stream.token()                      # weight
            cost, cost_start, cost_end = stream.token()
            stream.token()                      # condition
        except ValueError:
            break

        if re.fullmatch(r"-?\d+", cost) and re.fullmatch(r"-?\d+", level_token):
            out.append(dict(
                vnum=int(vnum_token),
                item_type=flag_value(item_type),
                level=int(level_token),
                cost=int(cost),
                span=(cost_start, cost_end),
            ))

        # Affects, extra descriptions and object actions, read the way
        # load_objects() reads them. Skipping ahead to the next "\n#"
        # instead is what stopped tools/costs_to_copper.py eighty-five
        # objects early: Hyrule's dungeon maps carry an ASCII floor plan
        # in an extra description, and several of its rows begin with a
        # hash.
        try:
            while True:
                mark = stream.pos
                letter = stream.letter()
                if letter == "A":
                    stream.number()
                    stream.number()
                elif letter in ("E", "T"):
                    stream.string()
                    stream.string()
                else:
                    stream.pos = mark
                    break
        except ValueError:
            break

    return out


def read_shops(text: str) -> dict[int, int]:
    """keeper vnum -> profit_buy, read the way load_shops() reads it."""
    bounds = section(text, "SHOPS")
    if bounds is None:
        return {}
    stream = Stream(text, bounds[0])
    shops: dict[int, int] = {}
    try:
        while True:
            keeper = stream.number()
            if keeper == 0:
                break
            for _ in range(MAX_TRADE):
                stream.number()
            profit_buy = stream.number()
            stream.number()                     # profit_sell
            stream.number()                     # open_hour
            stream.number()                     # close_hour
            stream.eol()
            shops[keeper] = profit_buy
    except ValueError:
        pass
    return shops


def read_resets(text: str) -> list[tuple[str, int, int]]:
    """(command, arg1, arg3) per reset, the way load_resets() reads it."""
    bounds = section(text, "RESETS")
    if bounds is None:
        return []
    stream = Stream(text, bounds[0])
    out: list[tuple[str, int, int]] = []
    try:
        while True:
            letter = stream.letter()
            if letter == "S":
                break
            if letter == "*":
                stream.eol()
                continue
            stream.number()                     # if_flag
            arg1 = stream.number()
            stream.number()                     # arg2
            arg3 = 0 if letter in ("G", "R") else stream.number()
            stream.eol()
            out.append((letter, arg1, arg3))
    except ValueError:
        pass
    return out


# Generated output. Writing into it would be undone by the next
# `make hyrule-area`, and Hyrule prices itself in rupees against its own
# drops -- a rupee is a gold coin there -- which already lands inside the
# target band. Its prices belong to scripts/build_hyrule_area.py.
GENERATED = frozenset(("hyrule.are",))


def listed_areas() -> list[pathlib.Path]:
    lines = (AREA / "area.lst").read_text("latin-1").splitlines()
    names = [l.strip() for l in lines if l.strip() and not l.strip().startswith("$")]
    return [AREA / n for n in names
            if n not in GENERATED and (AREA / n).is_file()]


# ----------------------------------------------------------------- model

def build_world() -> dict:
    objects: dict[int, dict] = {}
    per_file: dict[pathlib.Path, list[dict]] = {}
    shops: dict[int, int] = {}
    keeper_file: dict[int, pathlib.Path] = {}
    stock: dict[int, list[int]] = collections.defaultdict(list)

    for path in listed_areas():
        text = path.read_text("latin-1")
        found = read_objects(text)
        per_file[path] = found
        for o in found:
            o["file"] = path
            objects.setdefault(o["vnum"], o)

        here = read_shops(text)
        for keeper, profit in here.items():
            shops[keeper] = profit
            keeper_file[keeper] = path

        holder = None
        for command, arg1, _ in read_resets(text):
            if command == "M":
                holder = arg1
            elif command in ("G", "E") and holder is not None:
                if holder in here or holder in shops:
                    stock[holder].append(arg1)

    return dict(objects=objects, per_file=per_file, shops=shops,
                keeper_file=keeper_file, stock=stock)


def shop_levels(world: dict) -> dict[int, int]:
    """The bracket each shop serves, from the levels on its own shelf."""
    objects = world["objects"]
    stock = world["stock"]
    keeper_file = world["keeper_file"]

    own: dict[int, list[int]] = {}
    for keeper, vnums in stock.items():
        own[keeper] = sorted(objects[v]["level"] for v in vnums
                             if v in objects and objects[v]["level"] >= 1)

    # An area's shops, pooled and taken low. Dresden's grocer stocks one
    # levelled thing -- a level 10 long sword that a reset drops into four
    # different shops -- and on its own that one stray would price the
    # bread and the boxes beside it for a level 10 buyer.
    pooled: dict[pathlib.Path, list[int]] = collections.defaultdict(list)
    for keeper, levels in own.items():
        pooled[keeper_file[keeper]].extend(levels)
    area_level: dict[pathlib.Path, int] = {}
    for path, levels in pooled.items():
        if not levels:
            continue
        levels.sort()
        area_level[path] = levels[len(levels) // 4]

    shop_level: dict[int, int] = {}
    for keeper, levels in own.items():
        shelf = len(set(stock[keeper]))
        # The area pool is a fallback for a shelf of unlevelled goods with
        # a stray levelled thing on it, not for a small shop. Libby in the
        # Coven sells one item, a level 30 potion: that one item is the
        # shelf and it says exactly who shops there.
        if levels and (len(levels) >= MIN_STOCK_FOR_OWN_LEVEL
                       or len(levels) * 2 >= shelf):
            shop_level[keeper] = levels[len(levels) // 2]
        elif keeper_file[keeper] in area_level:
            shop_level[keeper] = area_level[keeper_file[keeper]]

    return shop_level


def buyer_levels(world: dict) -> dict[int, int]:
    """The level of the character each object is priced for, where known."""
    objects = world["objects"]
    stock = world["stock"]
    shop_level = shop_levels(world)

    # A shelf is one bracket's shelf, so it moves as one. Pricing each
    # item on it by its own level instead pulls the shelf apart: Dresden's
    # leather worker stocks a level 5 hard leather jerkin among a level 10
    # set, and scaling by item level alone left the body piece a tenth the
    # price of the cap. Forty-four such inversions across thirteen shops.
    # An object stocked by more than one shop takes the lowest, so the
    # neediest buyer sets the price.
    out: dict[int, int] = {}
    for keeper, vnums in stock.items():
        level = shop_level.get(keeper)
        if level is None:
            continue
        for v in vnums:
            if v in objects:
                out[v] = min(out.get(v, level), level)

    # Everything else is loot, and never shares a shelf with anything, so
    # its own level is both the best evidence and the only one that
    # matters -- its price is what a shop will pay for it.
    for vnum, o in objects.items():
        if vnum not in out and o["level"] >= 1:
            out[vnum] = o["level"]

    return out


def factors(world: dict, levels: dict[int, int]) -> dict[int, float]:
    """One scale per level, from the median price the files already hold."""
    by_level: dict[int, list[int]] = collections.defaultdict(list)
    for vnum, level in levels.items():
        cost = world["objects"][vnum]["cost"]
        if cost > 0 and level < HEALTHY_FROM:
            by_level[level].append(cost)

    out: dict[int, float] = {}
    for level, costs in by_level.items():
        median = statistics.median(costs)
        if median <= 0:
            continue
        scale = TARGET_KILLS * earn(level) / median
        # Never raise a price, and leave a level alone once it is close
        # enough: tidy() rounds, which nudges the median, which asks for
        # another one percent next time. Without the dead band the tool
        # never settles and a second run is not a no-op.
        if scale < 1.0 - SETTLED_WITHIN:
            out[level] = scale
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    verbose = "--verbose" in sys.argv

    world = build_world()
    levels = buyer_levels(world)
    scale = factors(world, levels)

    print("%d objects read, %d have a buyer level, %d levels rescaled"
          % (len(world["objects"]), len(levels), len(scale)))
    print()
    print("%5s %8s %12s" % ("level", "objects", "price x"))
    for level in sorted(scale):
        count = sum(1 for v, l in levels.items()
                    if l == level and world["objects"][v]["cost"] > 0)
        print("%5d %8d %12.5f" % (level, count, scale[level]))

    changed = 0
    for path, found in sorted(world["per_file"].items()):
        edits = []
        for o in found:
            level = levels.get(o["vnum"])
            if level is None or o["cost"] <= 0 or level not in scale:
                continue
            new = tidy(o["cost"] * scale[level])
            if new == o["cost"]:
                continue
            edits.append((o, new))

        if not edits:
            continue
        changed += len(edits)

        if verbose:
            for o, new in edits:
                print("  %-16s #%-6d lvl %2d  %12d -> %d"
                      % (path.name, o["vnum"], levels[o["vnum"]],
                         o["cost"], new))

        if apply:
            text = path.read_text("latin-1")
            out = []
            last = 0
            for o, new in sorted(edits, key=lambda e: e[0]["span"][0]):
                start, end = o["span"]
                out.append(text[last:start])
                out.append(str(new))
                last = end
            out.append(text[last:])
            path.write_text("".join(out), encoding="latin-1", newline="\n")

    print()
    print("%d prices %s" % (changed, "rewritten" if apply else "would change"))
    if not apply:
        print("dry run -- pass --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
