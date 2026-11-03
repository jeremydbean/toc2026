"""The Battleground's levers answer to their numbers (owner, 2026-11-03).

Room 29217 in korzath2.are draws ten levers labelled 1 to 10, and each
answered only to its number in words: PULL 5 was refused three times in
one evening (play journal, 2026-11-02). Each now has its digit as a
keyword too. Names match on prefixes, and "1" is the start of "10", so a
manipulation verb now takes an object in the room whose keyword is
exactly the word typed before any prefix match
(`get_manipulation_here`) -- otherwise PULL 1 would pull lever ten
whenever it lay first in the room.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zleverpass1"
LEVER_ROOM = 29217


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def pulled(reply: str) -> str | None:
    found = re.search(r"You (?:pull up on|push down on) (\w+)\.", reply)
    return found.group(1) if found else None


class LeverKeywordSourceTests(unittest.TestCase):
    def test_every_lever_answers_to_word_and_digit(self) -> None:
        text = (ROOT / "area" / "korzath2.are").read_text(encoding="latin-1").replace("\r\n", "\n")
        words = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
        for number, word in enumerate(words, start=1):
            with self.subTest(lever=number):
                self.assertIn(f"#{29255 + number}\n{word} {number}~\n{word}~\nLever {number}.~\n", text)

    def test_every_manipulation_verb_prefers_an_exact_keyword(self) -> None:
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        start = handler.index("void do_flip( CHAR_DATA *ch, char *argument )")
        end = handler.index("\n}\n", handler.index("void do_jump( CHAR_DATA *ch, char *argument )"))
        verbs = handler[start:end]
        self.assertNotIn("get_obj_here", verbs)
        self.assertEqual(verbs.count("get_manipulation_here( ch, arg )"), 8)
        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        body = act_obj[act_obj.index("void do_manipulate( CHAR_DATA *ch, char *argument )"):]
        body = body[:body.index("switch( obj->value[0] )")]
        self.assertIn("get_manipulation_here( ch, arg )", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LeverNumberLiveTests(unittest.TestCase):
    def test_pull_by_number_and_by_word(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zleverstaff", Levl=70, Room=LEVER_ROOM)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zleverstaff", PW)
                staff.sync("scroll 0")
                staff.must(f"goto {LEVER_ROOM}", "")
                cases = [("1", "one"), ("10", "ten"), ("5", "five"), ("five", "five"),
                         ("8", "eight"), ("eight", "eight"), ("2", "two")]
                for typed, lever in cases:
                    with self.subTest(typed=typed):
                        staff.must(f"goto {LEVER_ROOM}", "")
                        reply = staff.sync(f"pull {typed}")
                        self.assertEqual(pulled(reply), lever, reply)


if __name__ == "__main__":
    unittest.main()
