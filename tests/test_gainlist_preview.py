"""GAINLIST PREVIEW shows any build's whole kit before it is chosen.

The class review (2026-10-26) asked for a way to see a build's learnable
milestones and tradeoffs from the game's own tables. The preview lists
what a class in a guild is given and what a trainer serving it sells, at
the level the class can first use each, with the trains it all costs, the
blows a round it reaches, and what a guild outside the class's own adds
and gives up.

It is held here to tools/class_balance.py, which models the same tables
in Python for the balance tools: for every one of the 18 builds the two
must list the same abilities at the same levels.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, skip_reason

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import class_balance as cb  # noqa: E402

SKIP = skip_reason()
ANSI = re.compile(r"\x1b\[[0-9;]*m")
NAMES = ("mage", "cleric", "thief", "warrior", "monk", "necromancer")


def entries(text: str) -> dict:
    """name -> (level, bought) from the preview's 24-column cells."""
    out = {}
    for line in text.splitlines():
        if not re.match(r"^ [ \d]\d [ *]", line):
            continue
        for i in range(0, len(line), 24):
            cell = line[i:i + 24]
            m = re.match(r"^ ([ \d]\d) ([ *])(.+?)\s*$", cell)
            if m:
                out[m.group(3)] = (int(m.group(1)), m.group(2) == "*")
    return out


@unittest.skipIf(SKIP is not None, SKIP or "")
class GainlistPreviewTests(unittest.TestCase):
    def test_every_build_matches_the_tables(self) -> None:
        t = cb.load_tables()
        with LiveMud() as mud:
            with mud.connect(timeout=120) as c:
                create_character(c, "Zpreview", "Zprevpw1")
                c.sync("scroll 0")
                shown = {}
                for cls, guild in cb.builds():
                    q = f"gainlist preview {NAMES[cls]}" + (f" {NAMES[guild]}" if cls < 4 else "")
                    shown[(cls, guild)] = ANSI.sub("", c.sync(q, 30))
                bad = ANSI.sub("", c.sync("gainlist preview bard warrior"))
                no_guild = ANSI.sub("", c.sync("gainlist preview mage"))

        for (cls, guild), text in shown.items():
            name = cb.build_name(cls, guild)
            with self.subTest(name):
                got = entries(text)
                want = {s: (lvl, how != "given")
                        for s, (lvl, how) in cb.learnable(t, cls, guild).items()
                        if s not in ("psionic armor",) and lvl < 60}
                # The game truncates a long name to 19 columns.
                want = {s[:19]: v for s, v in want.items() if not s.startswith("psi")}
                self.assertEqual((sorted(set(got) - set(want)), sorted(set(want) - set(got))),
                                 ([], []), f"{name}: (only in the game, only in the model)")
                self.assertEqual({s: got[s][0] for s in got}, {s: want[s][0] for s in got},
                                 f"{name}: levels differ")
                self.assertRegex(text, r"\d+ abilities: \d+ given, \d+ more to GAIN")

        self.assertIn("level 50: 4", shown[(3, 3)], "a warrior in the warrior guild swings four times")
        self.assertIn("level 50: 3", shown[(3, 0)])
        self.assertRegex(shown[(3, 0)], r"gives up:[\s\S]*third attack")
        self.assertRegex(shown[(3, 0)], r"this adds:[\s\S]*fireball")
        self.assertEqual(entries(shown[(5, 5)])["tentacles"], (42, False))
        self.assertNotIn("this adds", shown[(4, 4)])
        self.assertIn("Syntax: gainlist preview", bad)
        self.assertIn("Which guild?", no_guild)


if __name__ == "__main__":
    unittest.main()
