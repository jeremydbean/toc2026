#!/usr/bin/env python3
"""Write the libFuzzer dictionaries the readers' targets use.

    python3 fuzz/make_dict.py      # rewrites fuzz/dict/{player,area}.dict

The player dictionary is every key the player-file reader matches, taken
from src/save.c itself, so it follows the reader as keys are added. The
area dictionary is the section names and record letters of src/db.c.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fuzz" / "dict"

MARKERS = ["#PLAYER", "#O", "#OBJECT", "#PET", "#STASH", "#END", "End", "~"]
AREA = ["#AREA", "#AREADATA", "#HELPS", "#MOBILES", "#OBJECTS", "#RESETS",
        "#ROOMS", "#SHOPS", "#SOCIALS", "#SPECIALS", "#$", "#0", "End",
        "Name", "Builders", "VNUMs", "~", "S", "D0", "D9", "E", "F", "A",
        "T", "M", "O", "P", "G", "R", "H", "|", "2147483647", "-2147483648",
        "4294967296", "1000000", "1000001"]


def quoted(word: str) -> str:
    return '"%s"\n' % word.replace("\\", "\\\\").replace('"', '\\"')


def player_keys() -> list[str]:
    source = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
    body = source[source.index("void fread_char( CHAR_DATA *ch, FILE *fp )"):]
    keys = set(re.findall(r'KEYS?\(\s*"([A-Za-z0-9_]+)"', body))
    keys |= set(re.findall(r'str_cmp\(\s*word,\s*"([A-Za-z0-9_]+)"\s*\)', body))
    return sorted(keys | set(MARKERS))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "player.dict", "w", encoding="ascii") as f:
        f.write("# Keys the player-file reader knows (src/save.c); fuzz/make_dict.py.\n")
        f.writelines(quoted(k) for k in player_keys())
    with open(OUT / "area.dict", "w", encoding="ascii") as f:
        f.write("# Section names and record letters of the area loader (src/db.c); fuzz/make_dict.py.\n")
        f.writelines(quoted(k) for k in AREA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
