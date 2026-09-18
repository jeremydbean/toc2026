"""Hyrule mobs answer to the words they are described by.

`look old' and `look man' both missed the gambling old man: his keywords
were "hyrule money game elder" and not one word of that appears in "a
gambling old man". Most of the hand-written records had the same gap -- the
stern old man, the old potion woman, the secret merchant.

The generator folds the short description into the keywords now, so the
check here is the general rule rather than a list of the eleven records
that were wrong. A player types what they can see.
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

GAMBLER_VNUM = 30345


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

    def test_the_area_still_parses(self) -> None:
        self.assertEqual(self.parser.errors, [])

    def test_every_hyrule_mob_answers_to_its_own_name(self) -> None:
        checked = 0
        for vnum, mob in self.mobiles.items():
            if not 30335 <= vnum <= 30345:
                continue
            checked += 1
            keywords = set(mob.keywords.lower().split())
            missing = visible_words(mob.short_desc) - keywords
            self.assertEqual(
                missing, set(),
                f"mob {vnum} ({mob.short_desc!r}) cannot be referred to by "
                f"{sorted(missing)}",
            )
        self.assertGreater(checked, 5, "the Hyrule mob block was not found")

    def test_the_gambler_can_be_found_the_obvious_ways(self) -> None:
        keywords = set(self.mobiles[GAMBLER_VNUM].keywords.lower().split())
        for word in ("old", "man", "gambling"):
            self.assertIn(word, keywords)

    def test_the_gambler_says_how_to_play(self) -> None:
        """He is the one mob in the area with a verb of his own."""
        description = self.mobiles[GAMBLER_VNUM].description
        self.assertIn("GAMBLE", description)
        self.assertIn("10 rupees", description)

    def test_the_description_fits_a_terminal(self) -> None:
        description = self.mobiles[GAMBLER_VNUM].description
        for line in description.splitlines():
            self.assertLessEqual(len(line), 78, f"too wide: {line!r}")


if __name__ == "__main__":
    unittest.main()
