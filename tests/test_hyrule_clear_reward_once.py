"""A cleared Hyrule room gives its item once per reset (review, 2026-10-26).

raw_kill asked after every mobile's death whether any foe was left in the
room, and laid the room's item again whenever it was not on the floor. So
once the boomerang of Level 1's D4 had been picked up, killing anything
else in that room -- here the fixture world's sentinel sparring guard,
which is no Hyrule foe -- laid another. Now only the death of one of
Hyrule's own foes can clear a room, the item is given once, and a reset
that fills the room with goriyas again owes it again.
"""
from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zclearpass1"
TEMPLE = 4207
EAGLE_D4 = 30410        # Level 1's goriyas and their boomerang
CHIME = "a bright chime"


def make(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def kill_all(test: unittest.TestCase, hero, keyword: str) -> str:
    """Kill every `keyword` in the room, one at a time. While any is left
    standing, no item may have appeared. Returns what was said since."""
    mark = len(hero.transcript)
    for _ in range(12):
        # CONSIDER finds only the living: corpses and severed limbs on the
        # floor still carry the name, so LOOK cannot say who is left.
        if "not here" in hero.sync(f"consider {keyword}").lower():
            return hero.transcript[mark:]
        test.assertNotIn(CHIME, hero.transcript[mark:],
                         f"an item appeared with a {keyword} still standing")
        hero.sync(f"kill {keyword}", 30)
        hero.drain(3)
    raise AssertionError(f"the {keyword}s did not die: {hero.sync('look')}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ClearRewardOnceTests(unittest.TestCase):
    def test_the_boomerang_is_given_once_per_reset(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zclearhero", Levl=58, Room=TEMPLE,
                 HMV="20000 20000 1000 1000 1000 1000", HMVP="20000 1000 1000")
            make(mud, "Zcleargod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zclearhero", PW)
                login(god, "Zcleargod", PW)
                god.must(f"transfer zclearhero {EAGLE_D4}", "")
                self.assertEqual(EAGLE_D4, room_of(god, "zclearhero"))
                god.must("set char zclearhero hitroll 300", "")
                god.must("set char zclearhero damroll 300", "")

                # The goriyas fall, the last one lays the boomerang; taken.
                said = kill_all(self, hero, "goriya")
                self.assertIn(CHIME, said)
                self.assertIn("boomerang", hero.sync("get boomerang").lower())
                inv = hero.sync("inventory").lower()
                self.assertEqual(1, inv.count("boomerang"), inv)
                self.assertNotRegex(inv, r"\(\s*\d+\)[^\n]*boomerang", inv)

                # Something that is no Hyrule foe dies in the cleared room.
                place_sparring_guard(god, "zcleargod", EAGLE_D4)
                god.must("set char sparring hp 20", "")
                god.must("restore sparring", "")
                said = kill_all(self, hero, "sparring")
                self.assertNotIn(CHIME, said, "an unrelated death laid the item again")
                self.assertIn("see no", hero.sync("get boomerang").lower())

                # A reset fills the room with goriyas: the item is owed again.
                god.must("repop", "repopulated")
                self.assertNotIn("not here", hero.sync("consider goriya").lower())
                said = kill_all(self, hero, "goriya")
                self.assertIn(CHIME, said, "a reset's goriyas owe the item again")
                self.assertIn("boomerang", hero.sync("get boomerang").lower())
                inv = hero.sync("inventory").lower()
                self.assertRegex(inv, r"\(\s*2\)[^\n]*boomerang", inv)


if __name__ == "__main__":
    unittest.main()
