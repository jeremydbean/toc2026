"""PWHERE lists every player and where they are; MSTAT, OSTAT and RSTAT work.

Eclipse typed both on 2026-10-04 and was told there was no such command:
do_mstat, do_ostat and do_rstat existed but were never registered, and
PWHERE did not exist. GWHERE walks the descriptors and misses the
link-dead; PWHERE walks the characters.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zpwherepw1"


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_pwhere_and_the_stat_shortcuts(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zpwgod", 70), ("Zpwmortal", 12)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207)
            with mud.connect(timeout=120) as mortal, mud.connect(timeout=120) as god:
                login(mortal, "Zpwmortal", PASSWORD)
                login(god, "Zpwgod", PASSWORD)
                god.send("scroll 0")
                god.drain(1.0)
                where = god.command("pwhere", settle=2.0)
                room = god.command("rstat", settle=2.0)
                mob = god.command("mstat zpwmortal", settle=2.0)
                denied = mortal.command("pwhere", settle=1.5)
            self.assertIn("Zpwmortal", where)
            self.assertIn("4207", where)
            self.assertRegex(where, r"\d+ players?\.")
            self.assertIn("Vnum: 4207", room)
            self.assertIn("Zpwmortal", mob)
            self.assertNotRegex(denied, r"\d+ players?\.", "a mortal gets no listing")


if __name__ == "__main__":
    unittest.main()
