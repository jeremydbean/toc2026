"""A new character holds its own class's groups and no other's.

load_char_obj fills in whatever a character's class, guild and race owe
them (apply_class_and_guild_skills). It ran for a brand new character
too, before a class was chosen -- class 0, which is mage -- so every
warrior, thief and cleric made since 2026-09-19 also held mage basics and
mage default, and Trentlin, a dwarf warrior, asked on 2026-10-18 whether
casting refresh was a bug.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]


class NewCharacterSourceTests(unittest.TestCase):
    def test_the_loader_fills_gaps_only_for_a_character_it_found(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        loader = save[save.index("bool load_char_obj("):]
        loader = loader[:loader.index("\n}\n")]
        self.assertIn("if ( found )\n        apply_class_and_guild_skills( ch );", loader)


@unittest.skipIf(SKIP is not None, SKIP or "")
class NewCharacterLiveTests(unittest.TestCase):
    def test_a_new_warrior_holds_no_mage_groups(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zfreshman", "Zfresh1pass")
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            saved = (mud.player_dir / "Zfreshman").read_text(encoding="latin-1")
            self.assertIn("Gr 'warrior basics'", saved)
            self.assertIn("Gr 'warrior default'", saved)
            self.assertNotIn("Gr 'mage basics'", saved)
            self.assertNotIn("Gr 'mage default'", saved)
            self.assertNotIn("'magic missile'", saved)


if __name__ == "__main__":
    unittest.main()
