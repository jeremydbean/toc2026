"""A mortal cannot GOTO, and the watch log says the attempt was refused.

Alaric, a level 27 necromancer, typed `goto kitten` while asleep; the log
of the build running then wrote it as a found command. This pins what a
mortal gets now: "Huh?", no move, and "(refused)" in the log.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, patch_player_file, login, skip_reason

SKIP = skip_reason()
PW = "Zgotopw12"


@unittest.skipIf(SKIP is not None, SKIP or "")
class MortalGotoTests(unittest.TestCase):
    def test_a_mortal_cannot_goto(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zgotoer", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zgotoer", Levl=27, Room=4210, Cla=5, Gui=5)
            with mud.connect(timeout=120) as client:
                login(client, "Zgotoer", PW)
                client.send("sleep")
                client.drain(1)
                mark = len(client.transcript)
                client.send("goto 2401")
                client.drain(2)
                reply = client.transcript[mark:]
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertIn("Huh?", reply)
            text = (mud.player_dir / "Zgotoer").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Room 4210$")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Log Zgotoer [4210]: (refused) goto 2401", log)
            # Arrivals name the room left behind, never a room of [0].
            self.assertNotIn("Log Zgotoer [0]:", log)


if __name__ == "__main__":
    unittest.main()
