"""Typing a whole help keyword must reach that topic.

do_help walks the help list in file order and matched with is_name, which
treats the argument as a prefix. So any short keyword was stolen by a longer
one that happened to appear earlier in the area files: "help cast" answered
with CASTLE, "help steal" with STEALTH, "help drag" with the Lucky Dragon
casino. An audit found 28 topics shadowed this way.

An exact keyword now wins; prefixes still work when nothing matches exactly,
so "help sco" still finds SCORE.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


if __name__ == "__main__":
    unittest.main()
