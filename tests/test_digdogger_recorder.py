"""The Recorder shrinks Level 5's guardian in its own den (playtest,
2026-11-13).

Digdogger's den (room 30489) holds a PLAY puzzle aimed at it, "Digdogger's
resonant shell" (object 30430). PLAY RECORDER there took the puzzle's path,
which cut Digdogger's health to a third but never marked it shrunk, so
every blow afterwards still bounced off its "great rolling bulk": the
first tune in the one room where it matters left the guardian unbeatable.
The puzzle now shrinks a digdogger exactly as the Recorder does
(hyrule_digdogger_shrink in hyrule.c), and the blows that follow land.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zddpass1"
DEN = 30489
RECORDER = 30413


def hit_points(stat: str) -> tuple[int, int]:
    found = re.search(r"Hp: (-?\d+)/(\d+)", stat)
    assert found, stat
    return int(found.group(1)), int(found.group(2))


@unittest.skipIf(SKIP is not None, SKIP or "")
class DigdoggerRecorderTests(unittest.TestCase):
    def test_the_tune_in_the_den_lets_a_blade_bite(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zddstaff", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zddstaff", Levl=70, Room=4207)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zddstaff", PW)
                staff.sync("scroll 0")
                staff.must(f"goto {DEN}", "Level 5")
                # The resonant shell is in the den from its reset: STAT ROOM
                # lists it by its first keyword.
                room = staff.must("stat room", "Vnum:")
                self.assertIn("resonance", room.lower(), room)
                before, most = hit_points(staff.must("stat mob digdogger", "Hp:"))
                self.assertEqual(before, most)
                staff.must(f"load obj {RECORDER}", "Recorder")
                played = staff.must("play recorder", "melody")
                self.assertIn("shrinks to a third", played, played)
                self.assertNotIn("tears through", played, played)
                shrunk, _ = hit_points(staff.must("stat mob digdogger", "Hp:"))
                self.assertLessEqual(shrunk, max(1, most // 3), (shrunk, most))
                mark = len(staff.transcript)
                staff.send("kill digdogger")
                staff.drain(7)
                fought = staff.transcript[mark:]
                self.assertIn("digdogger", fought.lower(), fought)
                self.assertNotIn("your blows bounce", fought.lower(), fought)
                after, _ = hit_points(staff.must("stat mob digdogger", "Hp:"))
                self.assertLess(after, shrunk, (shrunk, after))
                staff.send("quit")
                staff.wait_closed()


if __name__ == "__main__":
    unittest.main()
