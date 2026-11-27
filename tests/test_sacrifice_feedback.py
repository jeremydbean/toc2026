"""SACRIFICE says it takes only what lies on the floor, and asks before it
takes a corpse or container's contents with it (review, 2026-11-27).

The play journal had one burst of fifteen SACRIFICEs at one target, six
answered "You can't find it." -- it was in the pack; SACRIFICE searches the
floor only, and never said so. And SACRIFICE by hand took a monster's
corpse with its loot still inside, where AUTOSAC leaves a corpse that
holds anything. Now: the floor rule is said, with DROP when the thing is
carried, and a corpse or container that holds anything needs SACRIFICE
<it> ALL. Synthetic characters.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zsacpass1"
TEMPLE = 4207
MERCENARY = 2404
SWORD = 3022
BAG = 3032


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SacrificeFeedbackTests(unittest.TestCase):
    def test_the_floor_rule_is_said_and_contents_are_asked_for(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zsacstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zsacker", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zsacstaff", PW)
                login(hero, "Zsacker", PW)
                staff.sync("holylight")
                # Carried: say so, and DROP.
                staff.must(f"load obj {SWORD}", "You create")
                staff.must("give sword zsacker", "You give")
                said = hero.sync("sacrifice sword")
                self.assertIn("takes only what lies on the floor", said)
                self.assertIn("DROP it first", said)
                # Nowhere: still the floor rule.
                said = hero.sync("sacrifice zzznothing")
                self.assertIn("nothing like that on the floor", said)

                # A container holding something: asked for, then given whole.
                staff.must(f"load obj {BAG}", "You create")
                staff.must(f"load obj {SWORD}", "You create")
                staff.sync("put sword bag")
                staff.sync("drop bag")
                said = hero.sync("sacrifice bag")
                self.assertIn("still holds 1 thing", said)
                self.assertIn("SACRIFICE bag ALL", said)
                self.assertIn("bag", staff.sync("look").lower(), "nothing was taken")
                said = hero.sync("sacrifice bag all")
                self.assertIn("for your sacrifice", said)

                # A monster's corpse with its loot: the same.
                staff.must(f"load mob {MERCENARY}", "You create")
                staff.sync("slay mercenary")
                staff.must(f"load obj {SWORD}", "You create")
                staff.sync("put sword corpse")
                said = hero.sync("sacrifice corpse")
                self.assertIn("still holds", said)
                self.assertIn("corpse", staff.sync("look").lower())
                hero.sync("get all corpse")
                said = hero.sync("sacrifice corpse")
                self.assertIn("for your sacrifice", said, "an empty one goes at once, as before")


if __name__ == "__main__":
    unittest.main()
