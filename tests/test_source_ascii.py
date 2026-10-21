"""Every string the game sends is plain ASCII.

The game tells clients it speaks ISO-8859-1 and the web client decodes
Latin-1, so a UTF-8 em dash in a C string reached players as three bytes
of garbage: Trentlin's smite broke his weapon seven times on 2026-10-20
and each time he read "Your weapon falls into your pack â€" take it to a
repair shop." 56 dashes were written as "--" on 2026-10-21. Comments may
hold anything.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
STRING = re.compile(rb'"(?:\\.|[^"\\\n])*"')
COMMENT = re.compile(rb"/\*.*?\*/", re.S)


class SourceStringsAreAscii(unittest.TestCase):
    def test_no_byte_above_127_in_a_string_literal(self) -> None:
        bad = []
        for path in sorted((ROOT / "src").glob("*.[ch]")):
            text = COMMENT.sub(lambda m: b"\n" * m.group(0).count(b"\n"), path.read_bytes())
            for number, line in enumerate(text.split(b"\n"), 1):
                for literal in STRING.findall(line):
                    if any(byte > 127 for byte in literal):
                        bad.append("%s:%d" % (path.name, number))
        self.assertEqual(bad, [], "write a dash as -- (players read Latin-1)")


if __name__ == "__main__":
    unittest.main()
