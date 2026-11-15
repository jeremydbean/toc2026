"""A command that goes somewhere stands a resting or sitting character up
(players' logs, 2026-11-15: about twenty-five moves and flees a week were
answered "Nah... You feel too relaxed..."). Sleeping still refuses, and a
move in a fight says how to get out of it.

The mortal stands on the fixture world's sparring floor (32700), whose
north exit leads to the gallery (32701) and nowhere else.
"""
from __future__ import annotations

import unittest

from live_mud import (
    SPARRING_FLOOR,
    SPARRING_GALLERY,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zstandpass1"


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StandToMoveTests(unittest.TestCase):
    def test_resting_and_sitting_stand_up_to_go(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zstandgod", Levl=70, Room=SPARRING_FLOOR)
            make(mud, "Zstander", Levl=20, Room=SPARRING_FLOOR,
                 HMV="2000 2000 500 500 500 500")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zstandgod", PW)
                login(hero, "Zstander", PW)

                hero.must("rest", "You rest")
                said = hero.sync("north")
                self.assertIn("You stand up.", said, said)
                self.assertEqual(room_of(staff, "zstander"), SPARRING_GALLERY)

                hero.must("sit", "You sit")
                said = hero.sync("south")
                self.assertIn("You stand up.", said, said)
                self.assertEqual(room_of(staff, "zstander"), SPARRING_FLOOR)

                # FLEE out of no fight still stands them, then says so.
                hero.must("rest", "You rest")
                said = hero.sync("flee")
                self.assertIn("You stand up.", said, said)
                self.assertIn("You aren't fighting anyone", said, said)

                # Sleeping is not covered: WAKE first.
                hero.must("sleep", "You go to sleep", "You lie down")
                said = hero.sync("north")
                self.assertIn("In your dreams", said, said)
                self.assertNotIn("You stand up.", said, said)
                self.assertEqual(room_of(staff, "zstander"), SPARRING_FLOOR)
                hero.must("wake", "You wake")

                # In a fight, the refusal says how to get out.
                place_sparring_guard(staff, "Zstandgod", SPARRING_FLOOR)
                hero.sync("kill sparring")
                said = hero.sync("north")
                self.assertIn("FLEE to break away", said, said)
                staff.must("peace", "All is peaceful")
                self.assertEqual(room_of(staff, "zstander"), SPARRING_FLOOR)


if __name__ == "__main__":
    unittest.main()
