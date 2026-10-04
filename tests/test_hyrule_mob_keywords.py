"""Hyrule mobs answer to the words they are described by.

`look old' and `look man' both missed the gambling old man: his keywords
were "hyrule money game elder" and not one word of that appears in "a
gambling old man". Most of the hand-written records had the same gap -- the
stern old man, the old potion woman, the secret merchant.

The generator folds the short description into the keywords now, so the
check here is the general rule rather than a list of the records that were
wrong. A player types what they can see.

Since October 2026 every one of Hyrule's people is a record of their own
(the npcs table of data/hyrule_mob_prose.json, vnums HYRULE_NPC_FIRST to
HYRULE_NPC_LAST), so the rule is checked over all of them: some eighty old
men, old women, moblins, merchants, potion sellers, door-repair men,
gamblers, fairies, and Zelda.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "webadmin"))
sys.path.insert(0, str(ROOT / "scripts"))

from area_parser import AreaParser  # noqa: E402

# Words that identify nothing, so the generator does not index them.
STOPWORDS = {"a", "an", "the", "of", "and", "his", "her"}

NPC_FIRST, NPC_LAST, ZELDA = 30346, 30449, 30338
GAMBLE_ROOMS = range(30710, 30715)


def visible_words(short: str) -> set[str]:
    """The alphabetic words of a short description, as a player reads them."""
    words = set()
    current = ""
    for character in short.lower() + " ":
        if character.isalpha():
            current += character
            continue
        if current and current not in STOPWORDS:
            words.add(current)
        current = ""
    return words


class HyruleMobKeywordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        cls.parser = parser
        cls.mobiles = parser.mobiles
        cls.people = {
            vnum: mob for vnum, mob in parser.mobiles.items()
            if NPC_FIRST <= vnum <= NPC_LAST or vnum == ZELDA
        }
        cls.gamblers = [
            mob for mob in cls.people.values()
            if any(room in GAMBLE_ROOMS for room in mob.spawn_rooms)
        ]

    def test_the_area_still_parses(self) -> None:
        self.assertEqual(self.parser.errors, [])

    def test_every_hyrule_person_answers_to_their_own_name(self) -> None:
        unreachable = {}
        for vnum, mob in self.people.items():
            keywords = set(mob.keywords.lower().split())
            missing = visible_words(mob.short_desc) - keywords
            if missing:
                unreachable[vnum] = (mob.short_desc, sorted(missing))
        self.assertEqual({}, unreachable)
        self.assertGreater(len(self.people), 70, "the Hyrule people were not found")

    def test_no_two_people_share_a_name(self) -> None:
        shorts = [mob.short_desc for mob in self.people.values()]
        self.assertEqual(len(shorts), len(set(shorts)))

    def test_the_gamblers_can_be_found_the_obvious_ways(self) -> None:
        self.assertEqual(len(self.gamblers), 5)
        for mob in self.gamblers:
            with self.subTest(gambler=mob.short_desc):
                self.assertIn("gambler", mob.keywords.lower().split())

    def test_the_gamblers_say_how_to_play(self) -> None:
        """Each has a verb of his own, and the stake."""
        for mob in self.gamblers:
            with self.subTest(gambler=mob.short_desc):
                self.assertIn("GAMBLE", mob.description)
                self.assertIn("10 gold", mob.description)

    def test_the_descriptions_fit_a_terminal(self) -> None:
        wide = [
            (vnum, line) for vnum, mob in self.people.items()
            for line in mob.description.splitlines() if len(line) > 78
        ]
        self.assertEqual([], wide)


if __name__ == "__main__":
    unittest.main()
