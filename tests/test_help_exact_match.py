"""Typing a whole help keyword must reach that topic.

do_help walks the help list in file order and matched with is_name, which
treats the argument as a prefix. So any short keyword was stolen by a longer
one that happened to appear earlier in the area files: "help cast" answered
with CASTLE, "help steal" with STEALTH, "help drag" with the Lucky Dragon
casino. An audit found 28 topics shadowed this way.

An exact keyword now wins; prefixes still work when nothing matches exactly,
so "help sco" still finds SCORE.

Words after a topic that has a page reach that page, said so: HELP GAINLIST
TRAINERS, typed after GAINLIST's own output named GAINLIST TRAINERS, was told
there was no help (play journal, 2026-10-31). Only when nothing else
answered -- a page, a phrase or a spell group.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))

import help_index  # noqa: E402

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zhelppw12"


def ask_help(client, topic: str) -> str:
    # Synced, not a fixed window: on a slow runner HELP STEAL's page came
    # after a 1.2 s drain ended, and the test read only a prompt (CI,
    # 2026-10-30).
    return client.sync(f"help {topic}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class HelpExactMatchTests(unittest.TestCase):
    def test_whole_word_beats_a_longer_keyword_listed_earlier(self) -> None:
        # (typed word, what it used to reach, a phrase unique to the right page)
        cases = [
            ("cast", "CASTLE", "CAST"),
            ("steal", "STEALTH", "STEAL"),
            ("list", "LISTEN", "LIST"),
            ("north", "NORTHEAST", "NORTH"),
        ]

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelpone", PASSWORD)
                client.sync("scroll 0")
                for typed, stolen_by, expected in cases:
                    output = ask_help(client, typed)
                    header = output.strip().splitlines()
                    header = header[0].strip() if header else ""
                    self.assertNotEqual(
                        header.upper().split(),
                        [stolen_by],
                        f"'help {typed}' still lands on {stolen_by}:\n{output}",
                    )
                    self.assertIn(
                        expected,
                        output.upper(),
                        f"'help {typed}' did not reach {expected}:\n{output}",
                    )

    def test_a_prefix_still_works_when_nothing_matches_exactly(self) -> None:
        """The exact pass must not cost us ordinary abbreviation."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelptwo", PASSWORD)
                output = ask_help(client, "sco")
                self.assertIn("SCORE", output.upper(), output)

    def test_an_unknown_topic_still_says_so(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelpthr", PASSWORD)
                output = ask_help(client, "zzzznotatopic")
                self.assertIn("No help on that word", output, output)


class FirstWordFallbackIndexTests(unittest.TestCase):
    """The website's reader agrees with the game on the fallback."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = help_index.load_helps(ROOT / "area")

    def fallback(self, asked: str):
        found = help_index.first_word_fallback(self.entries, asked, 1)
        return found.keyword if found is not None else None

    def test_the_first_words_page(self) -> None:
        self.assertIsNone(help_index.lookup(self.entries, "gainlist trainers", 1))
        self.assertIn("GAINLIST", self.fallback("gainlist trainers"))
        self.assertIn("GAINLIST", self.fallback("gainl trainers"), "a prefix from three letters")

    def test_only_for_more_than_one_word_and_a_real_first_word(self) -> None:
        self.assertIsNone(self.fallback("gainlist"))
        self.assertIsNone(self.fallback("zzqq gainlist"))
        self.assertIsNone(self.fallback("ga trainers"), "two letters must be a whole keyword")


@unittest.skipIf(SKIP is not None, SKIP or "")
class FirstWordFallbackLiveTests(unittest.TestCase):
    def test_words_after_a_topic_reach_its_page(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelpfour", PASSWORD)
                client.sync("scroll 0")
                trainers = ask_help(client, "gainlist trainers")
                self.assertIn("No help on 'gainlist trainers'; here is gainlist:", trainers)
                self.assertIn("GAINLIST", trainers.upper())
                self.assertNotIn("No help on that word", trainers)
                self.assertIn("here is gainl:", ask_help(client, "gainl trainers"))
                # Nothing to fall back on is still nothing.
                self.assertIn("No help on that word", ask_help(client, "zzqq yyyy"))
                # What answered before still answers first: a phrase, a group.
                divine = ask_help(client, "divine inter")
                self.assertIn("DIVINE INTERVENTION", divine)
                self.assertNotIn("here is", divine)
                group = ask_help(client, "necro maladictions")
                self.assertIn("is a group of abilities", group)
                self.assertNotIn("here is", group)


if __name__ == "__main__":
    unittest.main()
