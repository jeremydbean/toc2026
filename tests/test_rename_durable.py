"""RENAME writes the new file before it removes the old one (review,
2026-11-13).

It unlinked the old player file first and then saved under the new name
without looking at the result, so a failed save -- or a crash between the
two -- left the character with no file at all. A save that fails now
changes nothing: the old name, the old file and the diary stay as they
were.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zrenpass1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Room=TEMPLE, **fields)


class RenameOrderSourceTests(unittest.TestCase):
    def test_the_old_file_goes_only_after_the_save(self) -> None:
        source = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        body = source[source.index("void do_rename("):]
        body = body[:body.index("\n}\n")]
        self.assertLess(body.index("save_char_obj( victim )"), body.index("unlink( old_file )"))
        self.assertIn("save_char_obj_status() == DURABLE_FAILED", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameLiveTests(unittest.TestCase):
    def test_a_failed_save_changes_nothing_and_a_good_one_moves_the_file(self) -> None:
        env = {"TOC_FAULT_FILE": "../fault.once", "TOC_FAULT": "autowrite"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zrenstaff", Levl=70)
            make(mud, "Zrenold", Levl=20)
            before = (mud.player_dir / "Zrenold").read_text(encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zrenstaff", PW)
                login(player, "Zrenold", PW)
                staff.sync("scroll 0")
                (mud.root / "fault.once").write_text("save-Zrennew\n")
                said = staff.must("rename zrenold zrennew", "could not be saved")
                self.assertNotIn("renamed", said)
                self.assertTrue((mud.player_dir / "Zrenold").exists())
                self.assertFalse((mud.player_dir / "Zrennew").exists())
                self.assertEqual(before, (mud.player_dir / "Zrenold").read_text(encoding="latin-1"))
                self.assertIn("Zrenold", staff.sync("stat char zrenold"))

                staff.must("rename zrenold zrennew", "renamed")
                self.assertFalse((mud.player_dir / "Zrenold").exists())
                self.assertTrue((mud.player_dir / "Zrennew").exists())
                player.send("quit")
                self.assertTrue(player.wait_closed())
            with mud.connect(timeout=120) as player:
                login(player, "Zrennew", PW)


if __name__ == "__main__":
    unittest.main()
