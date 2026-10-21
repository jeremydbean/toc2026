"""class_table has MAX_CLASS (6) rows; a guild can be GUILD_NONE (11).

mana_gain read class_table[ch->pcdata->guild] every tick, past the end of
the table for every player without a guild. A normal build read garbage
silently; the sanitizer build stopped on it ("index 11 out of bounds for
type 'class_type [6]'") partway through test_black_market, which is how
the sanitizer CI job failed there (2026-10-21). The live half of the
check is that job; this keeps the raw index from coming back.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class GuildIndexTests(unittest.TestCase):
    def test_no_unguarded_guild_index_into_class_table(self) -> None:
        for path in sorted((ROOT / "src").glob("*.c")):
            text = path.read_text(encoding="latin-1")
            for m in re.finditer(r"class_table\[\s*ch->pcdata->guild\s*\]", text):
                window = text[max(0, m.start() - 200):m.start()]
                self.assertIn("ch->pcdata->guild < MAX_CLASS", window,
                              f"{path.name}: {text[m.start():m.start() + 60]}")

    def test_mana_and_level_gain_treat_no_guild_as_the_class(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertIn("if (guild < 0 || guild >= MAX_CLASS)", update)
        self.assertIn("ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS", update)


if __name__ == "__main__":
    unittest.main()
