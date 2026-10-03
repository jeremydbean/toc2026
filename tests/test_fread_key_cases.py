"""Every player-file key is read in the case for its first letter.

fread_char, fread_pet and fread_obj dispatch on UPPER(word[0]) and then
test each key with KEY()/str_cmp inside that letter's case. A key filed
under the wrong letter is never matched: the loader then reads its value
as the next key and desyncs. Two keys added beside a related field in
case 'Q' instead of case 'R' made every affected character hang the game
at the login prompt. This walks every case and checks every key in it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAVE = (ROOT / "src" / "save.c").read_text(encoding="latin-1")

KEY_RE = re.compile(r'\bKEY\(\s*"([^"]+)"|str_cmp\(\s*word\s*,\s*"([^"]+)"\s*\)'
                    r'|str_cmp\(\s*"([^"]+)"\s*,\s*word\s*\)')


def reader_bodies(text: str):
    """(name, body) for every function that switches on UPPER(word[0])."""
    for match in re.finditer(r"\n(?:static\s+)?void\s+(fread_\w+)\s*\(", text):
        start = match.end()
        nxt = re.search(r"\n(?:static\s+)?[a-zA-Z_][\w \*]*\s+\**\w+\s*\([^;]*\)\s*\n\{",
                        text[start:])
        body = text[start: start + nxt.start()] if nxt else text[start:]
        if "UPPER(word[0])" in body.replace(" ", ""):
            yield match.group(1), body


def cases(body: str):
    """(letter, text) for each `case 'X':` section of the dispatch switch."""
    marks = list(re.finditer(r"case\s+'([A-Z*])'\s*:", body))
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        yield mark.group(1), body[mark.end():end]


class FreadKeyCaseTests(unittest.TestCase):
    def test_every_key_sits_under_its_own_letter(self) -> None:
        wrong = []
        seen_readers = []
        for name, body in reader_bodies(SAVE):
            seen_readers.append(name)
            for letter, text in cases(body):
                if letter == "*":
                    continue
                for m in KEY_RE.finditer(text):
                    key = next(g for g in m.groups() if g)
                    if key[0].upper() != letter:
                        wrong.append(f"{name}: '{key}' under case '{letter}'")
        self.assertIn("fread_char", seen_readers)
        # One readable line for the whole set, rather than a subTest each.
        self.assertEqual(wrong, [], "keys filed under the wrong letter")


if __name__ == "__main__":
    unittest.main()
