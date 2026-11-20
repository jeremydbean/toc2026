"""Which bow finishes Gohma (players' logs, 2026-11-18).

A monk carrying both an Eagle archer's bow (object 30337, a drop that
wants ARCHERY) and Hyrule's short bow (30222, which needs none) wielded
the wrong one for twenty-five minutes and four retreats: Gohma said only
"Wield the bow and SHOOT", and SHOOT said only "You need to know archery
to shoot." Gohma's line now names Hyrule's short bow, and in Hyrule the
archery refusal says that bow needs none, and whether it is carried.

Synthetic characters in a throwaway world.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zbowpass1"
EAGLE_BOW = 30337
SHORT_BOW = 30222
GOHMA = 30223
HYRULE_ROOM = 30200        # the overworld's first square
QUIET_ROOM = 32703         # fixture: nothing walks in


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BowHintTests(unittest.TestCase):
    def test_shoot_and_gohma_name_hyrules_short_bow(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zbowgod", Levl=70, Room=4207)
            make(mud, "Zbowhero", Levl=46, Room=4207)
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Zbowgod", PW)
                login(hero, "Zbowhero", PW)
                god.must("set skill zbowhero archery 0", "")
                god.must("load obj %d 40" % EAGLE_BOW, "")
                god.must("give eagle zbowhero", "")
                hero.must("wield eagle", "You wield")

                # Outside Hyrule the refusal is as it was.
                said = hero.sync("shoot guard")
                self.assertIn("You need to know archery to shoot.", said)
                self.assertNotIn("short bow", said)

                # In Hyrule, without the short bow: where it is.
                god.must("transfer zbowhero %d" % HYRULE_ROOM, "")
                hero.sync("look")
                said = hero.sync("shoot octorok")
                self.assertIn("You need to know archery to shoot.", said)
                self.assertIn("An Eagle archer's bow needs ARCHERY", said, said)
                self.assertIn("from Level 1's cellar, needs none", said, said)

                # Carrying it: which to wield.
                god.must("goto %d" % HYRULE_ROOM, "")
                god.must("load obj %d 5" % SHORT_BOW, "")
                god.must("give short zbowhero", "You give")
                said = hero.sync("shoot octorok")
                self.assertIn("which you carry, needs none: WIELD SHORT BOW", said, said)

                # Gohma's finishing blow names the short bow too.
                god.must("goto %d" % QUIET_ROOM, "")
                god.must("load mob %d" % GOHMA, "Gohma")
                god.must("set char gohma hp 1", "")
                god.sync("restore gohma")
                god.sync("goto 4207")
                # A fixture keeps its creation hit points; Gohma killed one
                # before its first blow landed in CI. Make it sure of both.
                god.must("set char zbowhero hp 30000", "")
                god.must("set char zbowhero hitroll 300", "hitroll set to 300")
                god.sync("restore zbowhero")
                god.must("transfer zbowhero %d" % QUIET_ROOM, "")
                hero.must("remove eagle", "You stop using")
                hero.sync("look")
                mark = len(hero.transcript)
                hero.send("kill gohma")
                hero.expect("armored eye closes", timeout=60)
                hero.drain(1.0)
                said = hero.transcript[mark:]
                self.assertIn("only an arrow from Hyrule's short bow can finish the blow.  WIELD SHORT BOW and SHOOT", said, said)


if __name__ == "__main__":
    unittest.main()
