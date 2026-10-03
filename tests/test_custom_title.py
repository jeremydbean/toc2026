"""A title the player chose survives a level-up.

advance_level set the class title on every level, so TITLE worked until the
next level and then quietly undid itself -- the help even told players to
set it again each time. A chosen title is now marked (pcdata->title_custom,
saved as TitleSet under case 'T' in fread_char) and only TITLE DEFAULT
hands the character back to the class title.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()

PASSWORD = "Ztitlepw12"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.8) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class TitleSourceTests(unittest.TestCase):
    def test_the_flag_is_read_under_its_own_first_letter(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        reader = save.index("void fread_char( CHAR_DATA *ch, FILE *fp )")
        case_t = save[save.index("case 'T':", reader):]
        case_t = case_t[:case_t.index("case 'V':")]
        self.assertIn('KEY( "TitleSet"', case_t)
        self.assertIn('"TitleSet 1\\n"', save)

    def test_advance_level_only_moves_a_class_title(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        body = update[update.index("void advance_level("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("set_class_title( ch, false )", body)
        self.assertNotIn("title_table", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CustomTitleLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mud = LiveMud()
        self.mud.__enter__()
        self.addCleanup(self.mud.__exit__, None, None, None)
        for name, fields in (("Ztitleimm", dict(Levl=70, Room=TEMPLE)),
                             ("Ztitleone", dict(Levl=5, Room=TEMPLE))):
            with self.mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(self.mud, name, **fields)

    def test_a_chosen_title_survives_levels_and_default_restores_the_class_one(self) -> None:
        with self.mud.connect(timeout=120) as player, \
             self.mud.connect(timeout=120) as staff:
            login(player, "Ztitleone", PASSWORD)
            login(staff, "Ztitleimm", PASSWORD)

            self.assertIn("Ok.", run(player, "title the Unbowed"))
            shown = run(player, "title")
            self.assertIn("the Unbowed", shown, shown)
            self.assertIn("You chose it", shown, shown)

            out = run(staff, "advance ztitleone 8", 3.0)
            self.assertIn("now level 8", out, out)
            kept = run(player, "title")
            self.assertIn("the Unbowed", kept, kept)

            back = run(player, "title default")
            self.assertIn("class title again", back, back)
            self.assertNotIn("Unbowed", back, back)

            run(staff, "advance ztitleone 10", 3.0)
            moved = run(player, "title")
            self.assertNotIn("Unbowed", moved, moved)
            self.assertIn("It is your class title", moved, moved)

    def test_the_choice_is_saved_and_survives_a_relog(self) -> None:
        with self.mud.connect(timeout=120) as player:
            login(player, "Ztitleone", PASSWORD)
            run(player, "title of the Long Road")
            player.send("quit")
            self.assertTrue(player.wait_closed())

        saved = (self.mud.player_dir / "Ztitleone").read_text(encoding="latin-1")
        self.assertRegex(saved, r"(?m)^TitleSet 1$")

        with self.mud.connect(timeout=120) as player, \
             self.mud.connect(timeout=120) as staff:
            login(player, "Ztitleone", PASSWORD)
            login(staff, "Ztitleimm", PASSWORD)
            run(staff, "advance ztitleone 7", 3.0)
            kept = run(player, "title")
            self.assertIn("of the Long Road", kept, kept)

    def test_an_old_file_without_the_flag_still_follows_the_class(self) -> None:
        """Characters saved before the flag existed load as automatic."""
        saved = (self.mud.player_dir / "Ztitleone").read_text(encoding="latin-1")
        self.assertNotIn("TitleSet", saved)
        with self.mud.connect(timeout=120) as player:
            login(player, "Ztitleone", PASSWORD)
            shown = run(player, "title")
            self.assertIn("It is your class title", shown, shown)


if __name__ == "__main__":
    unittest.main()
