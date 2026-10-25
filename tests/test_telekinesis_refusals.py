"""TELEKINESIS looks before it reaches (Alaric, 2026-10-23).

His corpse had rotted in the Korzath maze while he idled in the death
room, and the gear that fell out of it is mostly NOLOCATE, which TK never
moves. TK rolled first, so at 1% skill "tk corpse" and forty "tk cloak"s
all answered "You lost your concentration." -- the words of a missed roll
-- and charged mana for it. Now a search that finds nothing, or only
gear TK cannot fetch, says so and costs nothing; only a real target is
rolled for.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Ztkpass1"
TEMPLE = 4207
ALTAR = 4208
NOLOCATE_SWORD = 10001  # the Crystalline Sword of Justice, NOLOCATE
DAGGER = 3701


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def mana(client) -> int:
    out = run(client, "score", 1.4)
    m = re.search(r"(\d+)/(\d+) mana", out) or re.search(r"Mana:\s*(\d+)", out)
    if m is None:
        raise AssertionError("no mana in score: " + out)
    return int(m.group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class TelekinesisRefusalTests(unittest.TestCase):
    def test_nothing_to_fetch_is_a_refusal_not_a_miss(self) -> None:
        with LiveMud() as mud:
            for name in ("Ztkstaff", "Ztkmind"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Ztkstaff", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Ztkmind", Levl=30, Room=ALTAR,
                              HMV="500 500 900 900 500 500", HMVP="500 900 500")
            path = mud.player_dir / "Ztkmind"
            text = path.read_text(encoding="latin-1")
            end = text.index("\nEnd\n")
            path.write_text(text[:end] + "\nSk 1 'telekinesis'" + text[end:],
                            encoding="latin-1")

            with mud.connect(timeout=120) as staff:
                login(staff, "Ztkstaff", PASSWORD)
                run(staff, "scroll 0")
                run(staff, "load obj %d" % NOLOCATE_SWORD)
                run(staff, "drop justice")
                run(staff, "load obj %d" % DAGGER)
                run(staff, "drop dagger")

                with mud.connect(timeout=120) as mind:
                    login(mind, "Ztkmind", PASSWORD)
                    run(mind, "scroll 0")
                    before = mana(mind)

                    gone = run(mind, "tk zqxnothing")
                    self.assertIn("finds no", gone, gone)
                    self.assertNotIn("concentration", gone, gone)

                    sword = run(mind, "tk justice")
                    self.assertIn("TK cannot", sword, sword)
                    self.assertNotIn("concentration", sword, sword)

                    self.assertEqual(before, mana(mind),
                                     "a refusal cost mana")

                    # A real target is rolled for: at 1% almost always a miss,
                    # told as one.
                    reach = run(mind, "tk dagger")
                    self.assertTrue("lose your concentration" in reach
                                    or "flies to your hand" in reach, reach)


if __name__ == "__main__":
    unittest.main()
