"""Read area files token for token, the way src/db.c reads them.

Every Python tool that looks inside a ``.are`` file goes through here: the
dashboard's ``AreaParser``, the area lint, the directions router, the
Mudlet map, the price tools and the reference checks at the repository
root. They used to read the files several ways each, and the ways
disagreed -- 176 resets were commented out as "room does not exist"
because one reader missed ``D 0``; 85 objects were left priced in gold
because another stopped at a ``#`` inside an extra description. A reader
that takes the same tokens the game takes cannot disagree with the game,
and tools that share one cannot disagree with each other.

An area file is a token stream, not lines. ``fread_letter``,
``fread_number``, ``fread_flag``, ``fread_string`` and ``fread_word``
all skip whitespace, newlines included, so the game does not care where
a builder broke a line. ``TokenReader`` reproduces each of them,
including the odd corners the shipped world depends on:

* ``fread_number`` and ``fread_flag`` add up ``a|b``;
* ``fread_flag`` never reads a sign: on ``-1`` it consumes nothing and
  returns 0, and the next reader picks the ``-1`` up;
* ``fread_string`` skips leading whitespace, drops ``\\r`` and keeps
  everything else up to the tilde, ``#`` included.

The text is Latin-1 and is read without newline translation, so every
record and token keeps its exact offset in the file -- which is what lets
``tools/costs_to_copper.py`` and ``tools/reprice_by_level.py`` rewrite a
single token in place and leave every other byte alone, CRLF included.

Deliberate leniencies, each harmless to a file the game boots:

* a room's area-number field is taken as a raw token (the game wants a
  number there and ignores it);
* the file may end without ``#$``;
* ``#HELPS`` and ``#SOCIALS`` are read past, never kept: help has its
  own reader, ``webadmin/help_index.py``.

Anything else the game would refuse raises ``AreaFormatError``, with the
line it happened on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

BUILT_AREA_LIST = "built/built.lst"

# C's isspace() and isdigit() in the "C" locale. Python's str.isspace()
# and str.isdigit() accept Latin-1 characters the game does not (a
# no-break space, a superscript two), which would split or end a token
# where the game does not.
SPACE = frozenset(" \t\n\v\f\r")
DIGITS = frozenset("0123456789")

FLAGS2 = 1 << 25            # (Z): ACT_FLAGS2, AFF_FLAGS2, ITEM_FLAGS2, ...
ROOM_RIVER = 1 << 4         # (E)
ROOM_TELEPORT = 1 << 5      # (F)
ROOM_AFFECTED_BY = 1 << 7   # (H)


# The ranges fread_number and fread_long hold a number to (int and a
# 64-bit long, as the game is built).
INT_MIN, INT_MAX = -2**31, 2**31 - 1
LONG_MIN, LONG_MAX = -2**63, 2**63 - 1


class AreaFormatError(ValueError):
    """The file says something the game's loader would refuse."""

    def __init__(self, message: str, text: str = "", pos: int = 0,
                 name: str = ""):
        self.pos = pos
        self.line = text.count("\n", 0, pos) + 1 if text else 0
        self.name = name
        where = f"{name}:{self.line}: " if name and self.line else (
            f"line {self.line}: " if self.line else "")
        super().__init__(where + message)


# ------------------------------------------------------------------ tokens

@dataclass
class Token:
    """A run of the file, as one of the readers below took it."""
    text: str
    start: int
    end: int
    value: int = 0


def flag_value(token: str) -> int:
    """A flag word's value, as fread_flag reads it: letters summed (A is
    bit 0, a bit 26), then digits continuing the same number, and ``|``
    adding the next part."""
    total = 0
    for part in token.split("|"):
        part = part.strip(" \t\n\v\f\r")
        number = 0
        i = 0
        if part[:1] not in DIGITS:
            while i < len(part) and ("A" <= part[i] <= "Z" or "a" <= part[i] <= "z"):
                ch = part[i]
                number += (1 << (ord(ch) - 65)) if ch <= "Z" else (1 << (26 + ord(ch) - 97))
                i += 1
        while i < len(part) and part[i] in DIGITS:
            number = number * 10 + ord(part[i]) - 48
            i += 1
        total += number
    return total


class TokenReader:
    """The fread_* family over a string, with offsets."""

    def __init__(self, text: str, pos: int = 0, name: str = ""):
        self.text = text
        self.pos = pos
        self.name = name

    # -- helpers
    def error(self, message: str, pos: Optional[int] = None) -> AreaFormatError:
        return AreaFormatError(message, self.text,
                               self.pos if pos is None else pos, self.name)

    def at_end(self) -> bool:
        self.skip_space()
        return self.pos >= len(self.text)

    def skip_space(self) -> None:
        text, pos, n = self.text, self.pos, len(self.text)
        while pos < n and text[pos] in SPACE:
            pos += 1
        self.pos = pos

    # -- the readers
    def letter(self) -> str:
        """fread_letter: the next non-space character."""
        self.skip_space()
        if self.pos >= len(self.text):
            raise self.error("unexpected end of file")
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def _digits(self, start: int) -> int:
        pos = start
        while pos < len(self.text) and self.text[pos] in DIGITS:
            pos += 1
        return pos

    def number_token(self) -> Token:
        """fread_number: an optional sign, digits, and ``|`` adding the
        next number."""
        self.skip_space()
        start = self.pos
        value = 0
        while True:
            pos = self.pos
            sign = 1
            if pos < len(self.text) and self.text[pos] in "+-":
                sign = -1 if self.text[pos] == "-" else 1
                pos += 1
            end = self._digits(pos)
            if end == pos:
                raise self.error("bad number", pos)
            part = sign * int(self.text[pos:end])
            value += part
            if not INT_MIN <= part <= INT_MAX or not INT_MIN <= value <= INT_MAX:
                # fread_number refuses it as it reads (review of
                # d19b0e92): it used to wrap, #4295367296 into 400000.
                raise self.error("Fread_number: number out of range.", pos)
            self.pos = end
            if end < len(self.text) and self.text[end] == "|":
                self.pos = end + 1
                self.skip_space()
                continue
            break
        return Token(self.text[start:self.pos], start, self.pos, value)

    def number(self) -> int:
        return self.number_token().value

    def long_token(self) -> Token:
        """fread_long: as fread_number, but no ``|``."""
        self.skip_space()
        start = pos = self.pos
        sign = 1
        if pos < len(self.text) and self.text[pos] in "+-":
            sign = -1 if self.text[pos] == "-" else 1
            pos += 1
        end = self._digits(pos)
        if end == pos:
            raise self.error("bad number", pos)
        value = sign * int(self.text[pos:end])
        if not LONG_MIN <= value <= LONG_MAX:
            raise self.error("Fread_long: number out of range.", pos)
        self.pos = end
        return Token(self.text[start:end], start, end, value)

    def flag_token(self) -> Token:
        """fread_flag. A minus sign is neither a letter nor a digit, so on
        ``-1`` it consumes nothing at all and returns 0."""
        self.skip_space()
        start = self.pos
        text, n = self.text, len(self.text)
        while True:
            pos = self.pos
            if pos < n and text[pos] not in DIGITS:
                while pos < n and ("A" <= text[pos] <= "Z" or "a" <= text[pos] <= "z"):
                    pos += 1
            digits_at = pos
            pos = self._digits(pos)
            if pos > digits_at and int(text[digits_at:pos]) > INT_MAX:
                raise self.error("Fread_flag: number out of range.", digits_at)
            self.pos = pos
            if pos < n and text[pos] == "|":
                self.pos = pos + 1
                self.skip_space()
                continue
            break
        raw = text[start:self.pos]
        return Token(raw, start, self.pos, flag_value(raw) if raw else 0)

    def flag(self) -> int:
        return self.flag_token().value

    def raw_token(self) -> Token:
        """A whitespace-delimited run, for a field the game reads as a
        number but whose value no tool needs exactly."""
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in SPACE:
            self.pos += 1
        if start == self.pos:
            raise self.error("unexpected end of file")
        return Token(self.text[start:self.pos], start, self.pos)

    def string_token(self) -> Token:
        """fread_string: leading whitespace skipped, then everything up to
        the tilde, with carriage returns dropped."""
        self.skip_space()
        start = self.pos
        end = self.text.find("~", start)
        if end < 0:
            raise self.error("string with no closing tilde", start)
        self.pos = end + 1
        return Token(self.text[start:end].replace("\r", ""), start, self.pos)

    def string(self) -> str:
        return self.string_token().text

    def string_eol(self) -> str:
        """fread_string_eol: the rest of a line, after skipping whitespace."""
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in "\r\n":
            self.pos += 1
        out = self.text[start:self.pos]
        if self.pos < len(self.text):
            self.pos += 1
        return out

    def word(self) -> str:
        """fread_word: a run to whitespace, or a quoted run."""
        self.skip_space()
        if self.pos >= len(self.text):
            return ""
        quote = self.text[self.pos]
        if quote in "'\"":
            end = self.text.find(quote, self.pos + 1)
            if end < 0:
                end = len(self.text)
            out = self.text[self.pos + 1:end]
            self.pos = min(end + 1, len(self.text))
            return out
        return self.raw_token().text

    def to_eol(self) -> None:
        """fread_to_eol: past the end of this line and any blank ones."""
        text, n = self.text, len(self.text)
        pos = self.pos
        while pos < n and text[pos] not in "\r\n":
            pos += 1
        while pos < n and text[pos] in "\r\n":
            pos += 1
        self.pos = pos

    def line_rest(self) -> str:
        """What is left of this line, unconsumed."""
        end = self.pos
        while end < len(self.text) and self.text[end] not in "\r\n":
            end += 1
        return self.text[self.pos:end]


# ----------------------------------------------------------------- records

@dataclass
class Record:
    """Where a record sits: from its ``#`` to its last token."""
    vnum: int
    start: int
    end: int


@dataclass
class MobRecord(Record):
    keywords: str = ""
    short_desc: str = ""
    long_desc: str = ""
    description: str = ""
    race: str = ""
    act: Token = None
    act2: Optional[Token] = None
    affected: Token = None
    affected2: Optional[Token] = None
    alignment: Token = None
    style: str = "S"
    level: int = 0
    hitroll: int = 0
    hit_dice: Tuple[int, int, int] = (0, 0, 0)
    mana_dice: Tuple[int, int, int] = (0, 0, 0)
    damage_dice: Tuple[int, int, int] = (0, 0, 0)
    # The three dice as written ("1d1+200"), whitespace removed.
    hit_text: str = ""
    mana_text: str = ""
    damage_text: str = ""
    dam_type: int = 0
    ac: List[int] = field(default_factory=list)
    off: Token = None
    off2: Optional[Token] = None
    imm: Token = None
    imm2: Optional[Token] = None
    res: Token = None
    res2: Optional[Token] = None
    vuln: Token = None
    vuln2: Optional[Token] = None
    start_pos: Token = None
    default_pos: Token = None
    sex: Token = None
    wealth: int = 0
    form: Token = None
    parts: Token = None
    size: str = "M"
    material: str = ""
    # M-style mobiles' { A level str str ... } actions.
    actions: List[Tuple[int, str, str]] = field(default_factory=list)


@dataclass
class ObjRecord(Record):
    keywords: str = ""
    short_desc: str = ""
    long_desc: str = ""
    material: str = ""
    item_type: Token = None
    extra: Token = None
    extra2: Optional[Token] = None
    wear: Token = None
    values: List[Token] = field(default_factory=list)
    level: Token = None
    weight: Token = None
    cost: Token = None
    condition: str = "P"
    affects: List[Tuple[int, int]] = field(default_factory=list)
    # F records: (where, location, modifier, bits token), in file order.
    affect_bits: List[Tuple[str, int, int, Token]] = field(default_factory=list)
    extra_descr: List[Tuple[str, str]] = field(default_factory=list)
    actions: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class ExitRecord:
    door: int
    description: str
    keyword: str
    lock: int           # as written; load_rooms makes a "secret..." keyword 4
    key: int
    to_room: int
    start: int = 0
    end: int = 0


@dataclass
class RoomRecord(Record):
    name: str = ""
    description: str = ""
    number: Token = None
    flags: Token = None
    flags2: Optional[Token] = None
    sector: Token = None
    # ROOM_RIVER / ROOM_TELEPORT: destination (a direction for a river),
    # speed in ticks, visible.
    travel: Optional[Tuple[int, int, int]] = None
    # ROOM_AFFECTED_BY: the nine values load_rooms reads, as written.
    affect: Optional[List[Token]] = None
    exits: List[ExitRecord] = field(default_factory=list)
    extra_descr: List[Tuple[str, str]] = field(default_factory=list)
    # Where the closing S sits (the overlays insert before it).
    close: int = 0


@dataclass
class ResetRecord:
    command: str
    if_flag: int
    arg1: int
    arg2: int
    arg3: int           # 0 for G and R, which read only two arguments
    start: int
    end: int            # end of its line
    rest: str = ""      # whatever followed the arguments on the line


@dataclass
class ShopRecord:
    keeper: int
    buy_types: List[int]
    profit_buy: int
    profit_sell: int
    open_hour: int
    close_hour: int
    start: int = 0
    end: int = 0


@dataclass
class SpecialRecord:
    vnum: int
    spec: str
    start: int = 0
    end: int = 0


@dataclass
class Section:
    name: str           # as written after the '#', upper-cased ("$" for #$)
    start: int          # the '#'
    end: int            # after its terminator
    # Where its terminator starts: the '#0' after the last mobile, object
    # or room, the 'S' that ends resets and specials, the '0' that ends
    # shops. None for a section that has no terminator of its own.
    close: Optional[int] = None


@dataclass
class AreaFile:
    """One file, read whole."""
    name: str
    text: str
    header: Optional[str] = None        # "AREA", "AREADATA" or None
    area_name: Optional[str] = None     # the #AREA string, or AREADATA Name
    builders: Optional[str] = None
    vnum_range: Optional[Tuple[int, int]] = None
    sections: List[Section] = field(default_factory=list)
    mobiles: List[MobRecord] = field(default_factory=list)
    objects: List[ObjRecord] = field(default_factory=list)
    rooms: List[RoomRecord] = field(default_factory=list)
    resets: List[ResetRecord] = field(default_factory=list)
    shops: List[ShopRecord] = field(default_factory=list)
    specials: List[SpecialRecord] = field(default_factory=list)
    has_helps: bool = False
    has_socials: bool = False

    def section(self, name: str) -> Optional[Section]:
        for sec in self.sections:
            if sec.name == name:
                return sec
        return None


# ----------------------------------------------------------------- loaders
#
# Each mirrors its namesake in src/db.c, in the same order.

def _record_vnum(r: TokenReader, what: str) -> Tuple[int, int]:
    """'#' and a vnum, and where the '#' was. A vnum of 0 ends the
    section."""
    r.skip_space()
    start = r.pos
    if r.letter() != "#":
        raise r.error(f"Load_{what}: # not found.", start)
    return r.number(), start


def _dice(r: TokenReader) -> Tuple[Tuple[int, int, int], str]:
    """NdS+B, three numbers with a letter between each."""
    r.skip_space()
    start = r.pos
    number = r.number()
    r.letter()                  # 'd'
    size = r.number()
    r.letter()                  # '+'
    bonus = r.number()
    raw = "".join(ch for ch in r.text[start:r.pos] if ch not in SPACE)
    return (number, size, bonus), raw


def _flag_pair(r: TokenReader) -> Tuple[Token, Optional[Token]]:
    first = r.flag_token()
    second = r.flag_token() if first.value & FLAGS2 else None
    return first, second


def load_mobiles(r: TokenReader, out: List[MobRecord]) -> int:
    while True:
        vnum, start = _record_vnum(r, "mobiles")
        if vnum == 0:
            return start
        m = MobRecord(vnum, start, start)
        m.keywords = r.string()
        m.short_desc = r.string()
        m.long_desc = r.string()
        m.description = r.string()
        m.race = r.string()
        m.act, m.act2 = _flag_pair(r)
        m.affected, m.affected2 = _flag_pair(r)
        m.alignment = r.number_token()
        m.style = r.letter()
        m.level = r.number()
        m.hitroll = r.number()
        m.hit_dice, m.hit_text = _dice(r)
        m.mana_dice, m.mana_text = _dice(r)
        m.damage_dice, m.damage_text = _dice(r)
        m.dam_type = r.number()
        m.ac = [r.number() for _ in range(4)]
        m.off, m.off2 = _flag_pair(r)
        m.imm, m.imm2 = _flag_pair(r)
        m.res, m.res2 = _flag_pair(r)
        m.vuln, m.vuln2 = _flag_pair(r)
        m.start_pos = r.number_token()
        m.default_pos = r.number_token()
        m.sex = r.number_token()
        m.wealth = r.number()
        m.form = r.flag_token()
        m.parts = r.flag_token()
        m.size = r.letter()
        m.material = r.word()
        if m.style not in ("S", "M"):
            raise r.error(f"Load_mobiles: vnum {vnum} non-S and non-M.")
        if m.style == "M":
            if r.letter() != "{":
                raise r.error(f"Load_mobiles: vnum {vnum}, {{ }} section not found.")
            while True:
                letter = r.letter()
                if letter == "}":
                    break
                if letter != "A":
                    raise r.error(f"Load_mobiles: vnum {vnum}, unknown field in M-style section.")
                m.actions.append((r.number(), r.string(), r.string()))
        m.end = r.pos
        out.append(m)


def load_objects(r: TokenReader, out: List[ObjRecord]) -> int:
    while True:
        vnum, start = _record_vnum(r, "objects")
        if vnum == 0:
            return start
        o = ObjRecord(vnum, start, start)
        o.keywords = r.string()
        o.short_desc = r.string()
        o.long_desc = r.string()
        o.material = r.string()
        o.item_type = r.number_token()
        o.extra, o.extra2 = _flag_pair(r)
        o.wear = r.flag_token()
        o.values = [r.flag_token() for _ in range(5)]
        o.level = r.number_token()
        o.weight = r.number_token()
        o.cost = r.long_token()
        o.condition = r.letter()
        o.end = r.pos
        while True:
            mark = r.pos
            letter = r.letter() if not r.at_end() else ""
            if letter == "A":
                o.affects.append((r.number(), r.number()))
            elif letter == "F":
                where = r.letter()
                location = r.number()
                modifier = r.number()
                o.affect_bits.append((where, location, modifier, r.flag_token()))
            elif letter == "E":
                o.extra_descr.append((r.string(), r.string()))
            elif letter == "T":
                o.actions.append((r.string(), r.string()))
            else:
                r.pos = mark
                break
            o.end = r.pos
        out.append(o)


def load_rooms(r: TokenReader, out: List[RoomRecord]) -> int:
    while True:
        vnum, start = _record_vnum(r, "rooms")
        if vnum == 0:
            return start
        room = RoomRecord(vnum, start, start)
        room.name = r.string()
        room.description = r.string()
        room.number = r.raw_token()
        room.flags, room.flags2 = _flag_pair(r)
        room.sector = r.number_token()
        if room.flags.value & (ROOM_RIVER | ROOM_TELEPORT):
            room.travel = (r.number(), r.number(), r.number())
        if room.flags.value & ROOM_AFFECTED_BY:
            room.affect = [r.number_token(), r.number_token(), r.flag_token(),
                           r.flag_token()] + [r.number_token() for _ in range(5)]
        while True:
            r.skip_space()
            mark = r.pos
            letter = r.letter()
            if letter == "S":
                room.close = mark
                break
            if letter == "D":
                door = r.number()
                if door < 0 or door > 9:
                    raise r.error(f"Fread_rooms: vnum {vnum} has bad door number.", mark)
                room.exits.append(ExitRecord(
                    door, r.string(), r.string(), r.number(), r.number(),
                    r.number(), mark, 0))
                room.exits[-1].end = r.pos
            elif letter == "E":
                room.extra_descr.append((r.string(), r.string()))
            else:
                raise r.error(f"Load_rooms: vnum {vnum} has flag not 'DES'.", mark)
        room.end = r.pos
        out.append(room)


def load_resets(r: TokenReader, out: List[ResetRecord]) -> int:
    while True:
        r.skip_space()
        start = r.pos
        letter = r.letter()
        if letter == "S":
            return start
        if letter == "*":
            r.to_eol()
            continue
        if_flag = r.number()
        arg1 = r.number()
        arg2 = r.number()
        arg3 = 0 if letter in ("G", "R") else r.number()
        rest = r.line_rest()
        end = r.pos + len(rest)
        r.to_eol()
        if letter not in "MOPGEDRH":
            raise r.error(f"Load_resets: bad command '{letter}'.", start)
        out.append(ResetRecord(letter, if_flag, arg1, arg2, arg3, start, end, rest))


def load_shops(r: TokenReader, out: List[ShopRecord]) -> int:
    while True:
        r.skip_space()
        start = r.pos
        keeper = r.number()
        if keeper == 0:
            return start
        buy = [r.number() for _ in range(5)]
        shop = ShopRecord(keeper, buy, r.number(), r.number(), r.number(),
                          r.number(), start, r.pos)
        r.to_eol()
        out.append(shop)


def load_specials(r: TokenReader, out: List[SpecialRecord]) -> int:
    while True:
        r.skip_space()
        start = r.pos
        letter = r.letter()
        if letter == "S":
            return start
        if letter == "M":
            vnum = r.number()
            out.append(SpecialRecord(vnum, r.word(), start, r.pos))
        elif letter != "*":
            raise r.error(f"Load_specials: letter '{letter}' not *MS.", start)
        r.to_eol()


def skip_helps(r: TokenReader) -> None:
    while True:
        r.number()
        if r.string().startswith("$"):
            return
        r.string()


def skip_socials(r: TokenReader) -> None:
    while True:
        if r.word() == "#0":
            return
        r.to_eol()
        for _ in range(8):
            line = r.string_eol()
            if line == "#":
                break


def load_areadata(r: TokenReader, area: AreaFile) -> None:
    area.area_name = "Unnamed Area"
    while True:
        word = r.word() if not r.at_end() else "End"
        key = word.lower()
        if key == "end":
            return
        if key == "name":
            area.area_name = r.string()
        elif key == "builders":
            area.builders = r.string()
        elif key == "vnums":
            area.vnum_range = (r.number(), r.number())
        else:
            r.to_eol()


def _load_section(r: TokenReader, area: AreaFile, key: str) -> Optional[int]:
    """One record section's loader; its terminator's position."""
    if key == "MOBILES":
        return load_mobiles(r, area.mobiles)
    if key == "OBJECTS":
        return load_objects(r, area.objects)
    if key == "ROOMS":
        return load_rooms(r, area.rooms)
    if key == "RESETS":
        return load_resets(r, area.resets)
    if key == "SHOPS":
        return load_shops(r, area.shops)
    if key == "SPECIALS":
        return load_specials(r, area.specials)
    raise KeyError(key)


RECORD_SECTIONS = ("MOBILES", "OBJECTS", "ROOMS", "RESETS", "SHOPS", "SPECIALS")


def parse_area_text(text: str, name: str = "") -> AreaFile:
    """Read a whole area file's text as load_area_file does."""
    area = AreaFile(name=name, text=text)
    r = TokenReader(text, 0, name)
    while not r.at_end():
        start = r.pos
        if r.letter() != "#":
            raise r.error("Boot_db: # not found.", start)
        word = r.word()
        key = word.upper()
        close = None
        if key.startswith("$"):
            area.sections.append(Section("$", start, r.pos))
            break
        if key == "AREA":
            area.header = area.header or "AREA"
            area.area_name = r.string()
        elif key == "AREADATA":
            area.header = area.header or "AREADATA"
            load_areadata(r, area)
        elif key == "HELPS":
            area.has_helps = True
            skip_helps(r)
        elif key == "SOCIALS":
            area.has_socials = True
            skip_socials(r)
        elif key in RECORD_SECTIONS:
            close = _load_section(r, area, key)
        else:
            raise r.error(f"Boot_db: bad section name '{word}'.", start)
        area.sections.append(Section(key, start, r.pos, close))
    return area


def parse_section_text(text: str, section: str, name: str = "") -> AreaFile:
    """Read only the first ``#<section>`` in some text -- a fragment that
    need not be a whole file."""
    area = AreaFile(name=name, text=text)
    key = section.upper()
    marker = "#" + key
    pos = 0
    while True:
        pos = text.find(marker, pos)
        if pos < 0:
            return area
        after = pos + len(marker)
        if (pos == 0 or text[pos - 1] in "\r\n") and (
                after >= len(text) or text[after] in SPACE):
            break
        pos = after
    r = TokenReader(text, after, name)
    close = _load_section(r, area, key)
    area.sections.append(Section(key, pos, r.pos, close))
    return area


def read_text(path: Path) -> str:
    """A file's text, Latin-1, with its line endings exactly as stored --
    offsets into it are offsets into the file."""
    return Path(path).read_bytes().decode("latin-1")


def write_text(path: Path, text: str) -> None:
    """The inverse of read_text: no newline translation either way."""
    Path(path).write_bytes(text.encode("latin-1"))


def read_area_file(path: Path, name: Optional[str] = None) -> AreaFile:
    path = Path(path)
    return parse_area_text(read_text(path), name or path.name)


# -------------------------------------------------------------- the lists

def listed_area_files(area_directory: Path, built: bool = True) -> List[str]:
    """Every file the game loads, in its order: area.lst's entries, then
    -- unless ``built`` is false -- the areas built in game with ANEW,
    from built/built.lst (boot_db reads it after area.lst; it is missing
    until somebody builds an area). Generated files that are committed
    (directions, WALKTO's list) pass ``built=False``: a built area changes
    with every state sync and must never reach them.

    A list is words, as fread_word reads it, up to the first that starts
    with ``$``."""
    names: List[str] = []
    lists = ("area.lst", BUILT_AREA_LIST) if built else ("area.lst",)
    for list_name in lists:
        path = Path(area_directory) / list_name
        if not path.exists():
            continue
        r = TokenReader(read_text(path), 0, list_name)
        while not r.at_end():
            word = r.word()
            if not word or word.startswith("$"):
                break
            names.append(word)
    return names


def read_world(area_directory: Path, built: bool = True,
               only_existing: bool = True) -> List[AreaFile]:
    """Every listed ``.are`` file, read, in load order. A listed file that
    is missing is skipped (the area lint reports it)."""
    out: List[AreaFile] = []
    for name in listed_area_files(area_directory, built):
        if not name.endswith(".are"):
            continue
        path = Path(area_directory) / name
        if only_existing and not path.is_file():
            continue
        out.append(read_area_file(path, name))
    return out
