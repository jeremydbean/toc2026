"""No C string runs a hex escape straight into a hex-digit letter.

A C hex escape takes every hex digit that follows it, not two: written as
"\\x0Cdisarm", the colour code swallows the "d" into one byte, 0xCD, and
the player reads "isarm". That is exactly what HEROIC GRIP's message did
-- reported in game. The colour codes in this codebase are \\x02\\x0C and
friends, so any word starting a-f or A-F put right after one is broken
the same way. Split the literal ("\\x02\\x0C" "disarm") or put a space in.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A hex escape (not itself escaped by a preceding backslash) of exactly two
# digits followed directly by another hex digit.
GREEDY = re.compile(r"(?<!\\)\\x[0-9A-Fa-f]{2}[0-9A-Fa-f]")


def string_literals(line: str):
    """The string literals on a line, outside comments, roughly: enough for
    a C file that keeps its escapes inside double quotes."""
    code = line.split("//", 1)[0]
    return re.findall(r'"(?:[^"\\]|\\.)*"', code)


class HexEscapeTests(unittest.TestCase):
    def test_no_hex_escape_swallows_a_letter(self) -> None:
        found = []
        for path in sorted((ROOT / "src").glob("*.[ch]")):
            for number, line in enumerate(
                    path.read_text(encoding="latin-1").splitlines(), 1):
                for literal in string_literals(line):
                    for match in GREEDY.finditer(literal):
                        found.append(f"{path.name}:{number}: {match.group(0)}")
        self.assertEqual(found, [], "hex escapes that eat the next letter")


if __name__ == "__main__":
    unittest.main()
