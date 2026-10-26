"""Undead servants share one budget, whatever order they are raised in.

The three create spells checked a head count against 5, 2 and 1, so a
vampire, then a wraith, then three skeletons all passed, while five
skeletons refused anything more (review, 2026-10-26). The owner chose a
budget of 10: a skeleton 2, a wraith 5, a vampire 10. This plays it with
a mortal level 50 necromancer, every raise a real cast:

* the pure armies -- five skeletons, two wraiths, one vampire -- and the
  sixth skeleton, third wraith or second vampire refused;
* the mixes priced alike either way round, the old vampire + wraith +
  three skeletons refused at the wraith;
* a servant purged or dismissed with NOFOLLOW frees what it held;
* the count follows the bond, not the group: following somebody else
  does not lift it;
* quitting takes the servants, and the next login starts with the whole
  budget.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zundeadpw1"
GALLERY = 32701
TEMPLE = 4207
NECRO = 5
REFUSED = "can't control any more undead"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def raise_one(necro, kind: str) -> bool:
    """Cast create <kind>; True if it stood up, False if refused."""
    said = necro.sync(f"cast 'create {kind}'", 15).lower()
    if REFUSED in said:
        return False
    assert kind in said and "concentration" not in said, said
    return True


@unittest.skipIf(SKIP is not None, SKIP or "")
class UndeadBudgetTests(unittest.TestCase):
    def setUpWorld(self, mud: LiveMud) -> None:
        make(mud, "Zundeadstaff", Levl=70, Room=GALLERY)
        make(mud, "Zundeadnec", Levl=50, Room=GALLERY, Cla=NECRO, Gui=NECRO,
             HMV="2000 2000 30000 30000 1000 1000", HMVP="2000 30000 1000")
        make(mud, "Zundeadlead", Levl=50, Room=GALLERY)

    def test_the_budget_is_the_same_in_any_order(self) -> None:
        with LiveMud(fixtures=True) as mud:
            self.setUpWorld(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as necro, \
                    mud.connect(timeout=120) as lead:
                login(staff, "Zundeadstaff", PW)
                login(necro, "Zundeadnec", PW)
                login(lead, "Zundeadlead", PW)
                for spell in ("create skeleton", "create wraith", "create vampire"):
                    staff.must(f"set skill zundeadnec '{spell}' 100", "")

                def clear() -> None:
                    staff.sync("purge")
                    staff.must("restore zundeadnec", "")

                # Five skeletons; a sixth, a wraith and a vampire refused.
                self.assertEqual([raise_one(necro, "skeleton") for _ in range(6)],
                                 [True] * 5 + [False])
                self.assertFalse(raise_one(necro, "wraith"))
                self.assertFalse(raise_one(necro, "vampire"))
                # Purging one skeleton frees 2: a wraith (5) still does not fit.
                staff.must("purge skeleton", "")
                self.assertFalse(raise_one(necro, "wraith"))
                self.assertTrue(raise_one(necro, "skeleton"))
                clear()

                # The old order: vampire, then wraith and skeletons -- now
                # refused at the wraith, as raising them the other way is.
                self.assertTrue(raise_one(necro, "vampire"))
                self.assertFalse(raise_one(necro, "wraith"))
                self.assertFalse(raise_one(necro, "skeleton"))
                clear()

                # Two wraiths, no third; a wraith and two skeletons either way.
                self.assertEqual([raise_one(necro, "wraith") for _ in range(3)],
                                 [True, True, False])
                self.assertFalse(raise_one(necro, "skeleton"))
                clear()
                self.assertTrue(raise_one(necro, "wraith"))
                self.assertEqual([raise_one(necro, "skeleton") for _ in range(3)],
                                 [True, True, False])
                clear()
                self.assertEqual([raise_one(necro, "skeleton") for _ in range(2)], [True, True])
                self.assertTrue(raise_one(necro, "wraith"))
                self.assertFalse(raise_one(necro, "skeleton"))
                self.assertFalse(raise_one(necro, "vampire"))

                # NOFOLLOW dismisses them all; the whole budget is back.
                necro.must("nofollow", "")
                self.assertTrue(raise_one(necro, "vampire"))
                clear()

                # Following somebody else does not lift the count.
                necro.must("follow zundeadlead", "")
                lead.must("group zundeadnec", "")
                self.assertEqual([raise_one(necro, "skeleton") for _ in range(6)],
                                 [True] * 5 + [False])
                necro.must("follow self", "")

                # Quitting takes them; the next login has the whole budget.
                necro.send("quit")
                self.assertTrue(necro.wait_closed())
                staff.drain(1)
                self.assertNotIn("serving zundeadnec", staff.sync("look").lower())
            with mud.connect(timeout=120) as necro:
                login(necro, "Zundeadnec", PW)
                self.assertTrue(raise_one(necro, "vampire"))

    def test_a_lent_maximum_does_not_build_a_servant(self) -> None:
        """A servant's hit points come from the caster's lasting maximum.
        TITANIC lends six times it for thirty ticks; a servant lives for
        hundreds, so one raised under it was six times as tough for good.
        A skeleton with no corpse has 8d8 + max/10: at a 2000 maximum,
        264 at most, buffed or not (about 1264 on the old code)."""
        with LiveMud(fixtures=True) as mud:
            self.setUpWorld(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as necro:
                login(staff, "Zundeadstaff", PW)
                login(necro, "Zundeadnec", PW)
                staff.must("set skill zundeadnec 'create skeleton' 100", "")

                def skeleton_max() -> int:
                    self.assertTrue(raise_one(necro, "skeleton"))
                    stat = staff.sync("stat mob skeleton", 20)
                    m = re.search(r"Hp: -?\d+/(\d+)", ANSI.sub("", stat))
                    self.assertIsNotNone(m, stat)
                    staff.must("purge skeleton", "")
                    return int(m.group(1))

                plain = skeleton_max()
                staff.must("titanic zundeadnec 10", "")
                self.assertRegex(ANSI.sub("", staff.sync("stat char zundeadnec")),
                                 r"Hp: \d+/1[0-9]{4}")
                staff.must("restore zundeadnec", "")
                lent = skeleton_max()
                staff.must("titanic zundeadnec", "")
                for hp in (plain, lent):
                    self.assertGreaterEqual(hp, 8 + 200)
                    self.assertLessEqual(hp, 64 + 200)


if __name__ == "__main__":
    unittest.main()
