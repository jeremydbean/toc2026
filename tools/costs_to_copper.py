"""Restate every object price in copper instead of gold.

obj->cost was gold, so the cheapest anything could be was one gold piece --
ten thousand copper. A loaf of bread in Mud School cost a newbie a gold
coin, because the format had no way to say anything smaller.

Multiplying every price by COPPER_PER_GOLD keeps what everything is worth
exactly as it was, and makes a copper expressible for the first time.

The object section is read the way load_objects() reads it: as a stream of
tokens, not as lines. That matters. Several areas are written double-spaced,
one object has its flag line and its value line run together, another
carries letters rather than numbers in its value fields, and an object whose
extra flags include ITEM_FLAGS2 has a second flag word that shifts
everything after it along by one. A line-shaped parser gets all four of
those wrong; this one cannot, because it counts the same tokens the game
counts.

Only the cost token is rewritten, in place, by byte offset. Everything else
in the file -- spacing, blank lines, comments, order -- comes through
untouched.

    python tools/costs_to_copper.py            # report
    python tools/costs_to_copper.py --apply    # write
"""
from __future__ import annotations

import pathlib
import re
import sys

AREA = pathlib.Path("area")
COPPER_PER_GOLD = 10000
ITEM_FLAGS2 = 1 << 25          # (Z), the second extra-flag word's marker


class Stream:
    """Just enough of the game's readers to walk an object header."""

    def __init__(self, text: str, pos: int):
        self.text = text
        self.pos = pos

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def string(self) -> str:
        """Up to the next tilde, as fread_string does."""
        self.skip_space()
        end = self.text.find("~", self.pos)
        if end < 0:
            raise ValueError("unterminated string")
        out = self.text[self.pos:end]
        self.pos = end + 1
        return out

    def token(self) -> tuple[str, int, int]:
        """One whitespace-delimited run, with where it sat."""
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and not self.text[self.pos].isspace():
            self.pos += 1
        if start == self.pos:
            raise ValueError("expected a token")
        return self.text[start:self.pos], start, self.pos

    def letter(self) -> str:
        self.skip_space()
        if self.pos >= len(self.text):
            raise ValueError("expected a letter")
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def number(self) -> int:
        """fread_number: an optional sign and a run of digits."""
        self.skip_space()
        if self.pos < len(self.text) and self.text[self.pos] in "+-":
            self.pos += 1
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise ValueError("expected a number")
        return int(self.text[start:self.pos])

    def flag(self) -> tuple[str, int, int]:
        """A flag, including the way fread_flag mishandles a minus sign.

        fread_flag never considers a sign: on "-1" the digit loop does not
        run, the letter loop does not run, and it ungets the "-" and returns
        zero having consumed nothing. The next reader then picks the "-1" up
        as a number. So an object with a negative value field quietly shifts
        its own header along by one, and level, weight and cost are all read
        from the following tokens. Reproduced here because a tool that reads
        those objects differently from the game writes the price into the
        wrong field.
        """
        self.skip_space()
        if self.pos < len(self.text) and self.text[self.pos] == "-":
            return "0", self.pos, self.pos      # consumed nothing
        return self.token()


def flag_value(token: str) -> int:
    """A flag word as the game reads it: a number, or letters summed."""
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    total = 0
    for ch in token:
        if "A" <= ch <= "Z":
            total |= 1 << (ord(ch) - ord("A"))
        elif "a" <= ch <= "z":
            total |= 1 << (26 + ord(ch) - ord("a"))
    return total


def cost_spans(text: str) -> tuple[list[tuple[int, int, int]], list[str]]:
    """Every object's (start, end, value) for its cost token."""
    section = re.search(r"^#OBJECTS\s*$(.*?)^#0\s*$", text, re.S | re.M)
    if not section:
        return [], []

    stream = Stream(text, section.start(1))
    limit = section.end(1)
    found: list[tuple[int, int, int]] = []
    problems: list[str] = []

    while True:
        stream.skip_space()
        if stream.pos >= limit or text[stream.pos] != "#":
            break

        stream.pos += 1                       # the '#'
        vnum_token, _, _ = stream.token()
        if not re.fullmatch(r"-?\d+", vnum_token) or int(vnum_token) == 0:
            break
        vnum = int(vnum_token)

        try:
            for _ in range(4):                # name, short, long, material
                stream.string()

            stream.token()                    # item type
            extra, _, _ = stream.flag()       # extra flags
            if flag_value(extra) & ITEM_FLAGS2:
                stream.flag()                 # the second flag word
            stream.flag()                     # wear flags
            for _ in range(5):                # value[0..4]
                stream.flag()
            stream.token()                    # level
            stream.token()                    # weight

            cost, start, end = stream.token()
            if not re.fullmatch(r"-?\d+", cost):
                problems.append(f"#{vnum}: cost token {cost!r}")
            else:
                found.append((start, end, int(cost)))

            stream.token()                    # condition

            # Affects, extra descriptions and object actions, read the
            # way load_objects() reads them. This used to skip to the
            # next "\n#" instead, which is not a record boundary: a
            # Hyrule dungeon map carries an ASCII floor plan in an extra
            # description and several of its rows start with a hash. The
            # scan landed in one, found no vnum after it and stopped, and
            # the last 85 objects in the world were never converted.
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
        except ValueError as exc:
            problems.append(f"#{vnum}: {exc}")
            break

    return found, problems


def convert(path: pathlib.Path, apply: bool) -> tuple[int, int, list[str]]:
    text = path.read_text("latin-1")
    spans, problems = cost_spans(text)
    priced = [s for s in spans if s[2] != 0]

    if apply and priced:
        out = []
        last = 0
        for start, end, value in spans:
            if value == 0:
                continue
            out.append(text[last:start])
            out.append(str(value * COPPER_PER_GOLD))
            last = end
        out.append(text[last:])
        path.write_text("".join(out), encoding="latin-1", newline="\n")

    return len(spans), len(priced), [f"{path.name} {p}" for p in problems]


def loaded_areas() -> list[pathlib.Path]:
    """Only what area.lst actually boots.

    Two unlisted files (c.are, trcult.are) carry objects the game could
    not read if it tried -- one has a material string with no closing
    tilde. Converting half of a file nobody loads would leave it worse
    than leaving it alone.
    """
    listed = [l.strip() for l in (AREA / "area.lst").read_text("latin-1").splitlines()
              if l.strip() and not l.strip().startswith("$")]
    return [AREA / name for name in listed if (AREA / name).is_file()]


def main() -> int:
    apply = "--apply" in sys.argv
    seen = priced = 0
    problems: list[str] = []

    for path in sorted(loaded_areas()):
        s, p, odd = convert(path, apply)
        seen += s
        priced += p
        problems.extend(odd)

    print(f"{seen} objects read, {priced} carried a price")

    if problems:
        print(f"\n{len(problems)} could not be read:")
        for line in problems[:20]:
            print("   " + line)
        return 1

    print("applied" if apply else "dry run -- pass --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
