"""Dormant characters are archived, and come back by themselves (owner,
2026-11-11: "archive old players for backup purposes, but if a player
tries to log in as one, still move it into the active players
automatically").

At boot, player_archive_dormant moves a character whose file was last
saved more than PLAYER_ARCHIVE_DAYS (two years) ago to player/archive/.
Its name stays taken, and logging in as it moves it back first.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zarchpass11"
LONG_AGO = 1000000000          # September 2001


class ArchiveSourceTests(unittest.TestCase):
    def test_the_loader_and_the_writers_bring_it_back(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        loader = save.split("bool load_char_obj(", 1)[1]
        self.assertLess(loader.index("player_unarchive( name );"),
                        loader.index("presence = player_file_presence( name );"))
        presence = save.split("int player_file_presence(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("PLAYER_ARCHIVE_DIR", presence, "an archived name stays taken")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertIn("player_unarchive( capname );", wiz)       # PRESTORE
        self.assertIn("player_unarchive( arg_name );", wiz)      # RESETPWD
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        main = comm.split("control = init_socket( port );", 1)[1]
        self.assertIn("player_archive_dormant( );", main,
                      "only a serving boot archives, never --check-area")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ArchiveLiveTests(unittest.TestCase):
    def test_archived_at_boot_and_back_at_login(self) -> None:
        with LiveMud() as mud:
            for name in ("Zarchold", "Zarchnew"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zarchold", LogO=LONG_AGO, LastOut=LONG_AGO)

            mud.restart()
            active, archive = mud.player_dir, mud.player_dir / "archive"
            self.assertTrue((archive / "Zarchold").is_file(), "dormant: archived")
            self.assertFalse((active / "Zarchold").exists())
            self.assertTrue((active / "Zarchnew").is_file(), "recent: left alone")
            self.assertFalse((archive / "Zarchnew").exists())

            # The name is still taken: the prompt asks for its password.
            with mud.connect(timeout=120) as client:
                client.expect("name", timeout=60)
                client.send("Zarchold")
                client.expect("assword", timeout=60)

            # Logging in brings it back, whole.
            with mud.connect(timeout=120) as client:
                login(client, "Zarchold", PW)
                self.assertIn("Zarchold", client.sync("score", timeout=60))
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertTrue((active / "Zarchold").is_file(), "back among the active")
            self.assertFalse((archive / "Zarchold").exists())

            # Saved just now, so the next boot leaves it be.
            mud.restart()
            self.assertTrue((active / "Zarchold").is_file())
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Archive: 1 character not seen in 730 days moved to player/archive/", log)
        self.assertIn("Archive: Zarchold brought back to the active players.", log)


if __name__ == "__main__":
    unittest.main()
