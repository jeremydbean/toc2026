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

import re

from live_mud import LiveMud, create_character, login, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]


class NewCharacterSourceTests(unittest.TestCase):
    def test_the_cleanup_runs_at_login_and_spares_mages_and_staff(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertIn("rescind_stray_mage_groups( ch );", comm)
        skills = (ROOT / "src" / "skills.c").read_text(encoding="latin-1")
        fn = skills[skills.index("void rescind_stray_mage_groups("):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("ch->class == CLASS_MAGE", fn)
        self.assertIn("IS_TRUSTED( ch, LEVEL_IMMORTAL )", fn)


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

    def test_the_stray_groups_are_taken_back_and_the_practice_refunded(self) -> None:
        """Owner, 2026-10-21: remove the mage spells from anyone who should
        not have them and refund the practices used."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zstray", "Zstray1pass")
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            path = mud.player_dir / "Zstray"
            text = path.read_text(encoding="latin-1")
            # What the bug left on Trentlin: the two groups, their spells,
            # one practised, and the dagger the mage's spread raised.
            text = re.sub(r"(?m)^Prac .*$", "Prac 5", text)
            text = re.sub(r"(?m)^Sk \d+ 'dagger'$", "Sk 89 'dagger'", text)
            text = text.replace("Gr 'warrior basics'",
                                "Sk 76 'refresh'\nSk 1 'magic missile'\nSk 1 'scrolls'\n"
                                "Gr 'mage basics'\nGr 'warrior basics'\nGr 'mage default'", 1)
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zstray", "Zstray1pass")
                client.drain(2.0)
                self.assertIn("gave you the mage's starting spells", client.transcript)
                refunded = int(re.search(r"The (\d+) practice sessions? you spent",
                                         client.transcript).group(1))
                self.assertGreater(refunded, 0)
                client.send("quit")
                client.wait_closed()

            saved = path.read_text(encoding="latin-1")
            self.assertNotIn("Gr 'mage basics'", saved)
            self.assertNotIn("Gr 'mage default'", saved)
            self.assertNotIn("'refresh'", saved)
            self.assertNotIn("'magic missile'", saved)
            self.assertIn("Sk 89 'dagger'", saved, "a skill owed anyway keeps its training")
            self.assertIn("Prac %d" % (5 + refunded), saved)

            # Once is enough: the next login says nothing.
            with mud.connect(timeout=120) as client:
                login(client, "Zstray", "Zstray1pass")
                client.drain(2.0)
                self.assertNotIn("gave you the mage's starting spells", client.transcript)


if __name__ == "__main__":
    unittest.main()
