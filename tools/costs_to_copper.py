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
those wrong; webadmin/area_reader.py, the reader every area tool shares,
cannot, because it counts the same tokens the game counts.

Only the cost token is rewritten, in place, by byte offset. Everything else
in the file -- spacing, blank lines, comments, order, line endings -- comes
through untouched.

This was a one-pass conversion and has been applied: running it with
--apply again would multiply every price by ten thousand a second time.
It is kept for reference and for the reader test in test_shop_prices.

    python tools/costs_to_copper.py            # report
    python tools/costs_to_copper.py --apply    # write
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "webadmin"))
from area_reader import (  # noqa: E402
    AreaFormatError, listed_area_files, parse_area_text, read_text, write_text)

AREA = pathlib.Path("area")
COPPER_PER_GOLD = 10000


def cost_spans(text: str) -> tuple[list[tuple[int, int, int]], list[str]]:
    """Every object's (start, end, value) for its cost token.

    The file is read whole by webadmin/area_reader.py, the reader every
    area tool shares, exactly as load_objects() reads it -- affects, extra
    descriptions and object actions included. This tool used to skip to
    the next "\\n#" after an object's condition instead, which is not a
    record boundary: a Hyrule dungeon map carries an ASCII floor plan in an
    extra description and several of its rows start with a hash. The scan
    landed in one, found no vnum after it and stopped, and the last 85
    objects in the world were never converted.
    """
    try:
        area = parse_area_text(text)
    except AreaFormatError as exc:
        return [], [str(exc)]
    return [(o.cost.start, o.cost.end, o.cost.value) for o in area.objects], []


def convert(path: pathlib.Path, apply: bool) -> tuple[int, int, list[str]]:
    # Read and written as bytes, so a span is a span in the file and a
    # CRLF file stays CRLF.
    text = read_text(path)
    spans, problems = cost_spans(text)
    priced = [s for s in spans if s[2] != 0]

    if apply and priced and not problems:
        out = []
        last = 0
        for start, end, value in spans:
            if value == 0:
                continue
            out.append(text[last:start])
            out.append(str(value * COPPER_PER_GOLD))
            last = end
        out.append(text[last:])
        write_text(path, "".join(out))

    return len(spans), len(priced), [f"{path.name} {p}" for p in problems]


def loaded_areas() -> list[pathlib.Path]:
    """Only what area.lst actually boots.

    Two unlisted files (c.are, trcult.are) carry objects the game could
    not read if it tried -- one has a material string with no closing
    tilde. Converting half of a file nobody loads would leave it worse
    than leaving it alone.
    """
    return [AREA / name for name in listed_area_files(AREA, built=False)
            if (AREA / name).is_file()]


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
