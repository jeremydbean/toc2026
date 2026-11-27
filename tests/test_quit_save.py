"""QUIT saves before it lets anyone go (review, 2026-11-27).

do_quit announced the departure, abandoned the active quest (its items are
extracted, so that cannot be taken back), then called save_char_obj and
ignored the result, extracted the character and closed the connection: an
injected save failure closed the socket and lost an unsaved title change.
Now the save comes first. Not saved: the player stays, quest and all, and
is told to try again. In place but unconfirmed (the directory sync did not
answer): they leave, and staff hear of it. Synthetic characters only.
"""
from __future__ import annotations

import pathlib
import tempfile
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zquitpass1"
TEMPLE = 4207
QUESTMASTER_ROOM = 2497


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class QuitSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.fault = pathlib.Path(self._tmp.name) / "fault"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def arm(self, point: str) -> None:
        """The next save at `point` fails (src/recovery.c, TOC_FAULT_FILE)."""
        self.fault.write_text(point + "\n")

    def test_a_failed_save_keeps_the_player_their_quest_and_their_change(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": str(self.fault)}) as mud:
            make(mud, "Zcarver", Levl=70, Room=TEMPLE)
            make(mud, "Zquitter", Levl=20, Room=QUESTMASTER_ROOM)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zcarver", PW)
                login(hero, "Zquitter", PW)
                asked = hero.sync("aquest request", timeout=30)
                self.assertNotIn("no quest", asked.lower(), asked)
                hero.sync("title the Unsaved")

                self.arm("save-Zquitter")
                said = hero.sync("quit", timeout=30)
                self.assertIn("could not be saved, so you have not left", said)
                self.assertNotIn("all good things must come to an end", said)
                self.assertNotIn("abandons your", said, "the quest is not given up")
                time.sleep(1.0)
                self.assertIn("Zquitter the Unsaved", hero.sync("who"), "still here, change and all")
                self.assertNotIn("aren't on a quest", hero.sync("aquest info").lower())
                self.assertIn("could not be saved: still in the game", staff.drain(1.0) or
                              staff.transcript)

                # FORCE quits through the same door.
                self.arm("save-Zquitter")
                staff.sync("force zquitter quit")
                time.sleep(1.0)
                self.assertIn("Zquitter", staff.sync("where zquitter"), "a forced quit stays too")

                # Once the disk takes it, QUIT works and the change is kept.
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            saved = (mud.player_dir / "Zquitter").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("the Unsaved", saved)
        self.assertEqual(log.count("Zquitter tried to quit, but could not be saved"), 2)
        after = log.split("Zquitter tried to quit, but could not be saved", 1)[1]
        self.assertEqual(after.count("Zquitter has quit."), 1, "one real departure, at the end")

    def test_an_unconfirmed_save_still_lets_them_go(self) -> None:
        """The rename happened; only the directory sync did not answer.
        Staying would not make the file any surer: they leave, staff hear."""
        with LiveMud(extra_env={"TOC_FAULT_FILE": str(self.fault)}) as mud:
            make(mud, "Zquitter", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zquitter", PW)
                hero.sync("title the Unconfirmed")
                self.arm("dirsync-Zquitter")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            saved = (mud.player_dir / "Zquitter").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("the Unconfirmed", saved)
        self.assertIn("Zquitter's save on quitting is in place but the disk did not confirm it",
                      log)


class QuitSaveSourceTests(unittest.TestCase):
    def test_the_save_comes_before_anything_about_leaving(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        src = (root / "src" / "act_comm.c").read_text(encoding="latin-1")
        body = src[src.index("void do_quit( CHAR_DATA *ch, char *argument )"):]
        body = body[:body.index("\n}\n")]
        gate = body.index("!quit_save_first( ch )")
        for later in ("has left the game", "quest_handle_logout(ch)", "playlog_session",
                      "record_logout", "extract_char( ch, TRUE )"):
            self.assertLess(gate, body.index(later), later)


if __name__ == "__main__":
    unittest.main()
