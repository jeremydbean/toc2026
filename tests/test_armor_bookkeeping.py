"""Spells that damage worn armour must leave armour class honest.

Audit 2026-10-21: heat metal and acid breath took a worn piece's bonus off
with the wrong sign -- they subtracted it a second time -- and heat metal
filed a piece down before unequip_char gave back its (now smaller) bonus.
Every heat or etch left the wearer permanently better armoured: naked AC
100 read 67 after the warped piece had fallen into the pack. The rule is
the shield block's in fight.c: bonus off at the old values (unequip adds),
file the piece down, bonus back on at the new ones (equip subtracts).
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zarmor1pass"
FIELD = 4202            # east of the Temple: not safe
SILVER_PLATE = 631      # body armour, ofcol.are


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def armour(smith) -> tuple[int, ...]:
    text = run(smith, "stat char zvictim", 1.4)
    found = re.findall(
        r"Armor: pierce: (-?\d+)\s+bash: (-?\d+)\s+slash: (-?\d+)\s+magic: (-?\d+)", text)
    assert found, text
    return tuple(int(n) for n in found[-1])


@unittest.skipIf(SKIP is not None, SKIP or "")
class ArmorBookkeepingTests(unittest.TestCase):
    def test_heat_metal_leaves_no_bonus_behind(self) -> None:
        with LiveMud() as mud:
            for name in ("Zvictim", "Zsmith"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zvictim", Levl=10, Room=FIELD)
            patch_player_file(mud, "Zsmith", Levl=70, Room=FIELD)

            with mud.connect(timeout=120) as victim, mud.connect(timeout=120) as smith:
                login(victim, "Zvictim", PASSWORD)
                login(smith, "Zsmith", PASSWORD)
                run(smith, "set skill zsmith 'heat metal' 100")
                run(smith, "set char zvictim hp 30000")
                run(smith, "set char zsmith mana 30000")
                # Nothing of the starting kit: the spell picks any armour
                # or weapon carried, and the plate must be all there is.
                run(victim, "remove all", 1.5)
                run(victim, "drop all", 1.5)
                run(smith, "purge", 1.0)
                naked = armour(smith)

                def plate(noremove: bool) -> None:
                    run(smith, "load obj %d" % SILVER_PLATE)
                    # Below -30 the spell always picks it (it skips a piece
                    # when number_percent() <= level + 30).
                    run(smith, "set obj plate level -40")
                    if noremove:
                        self.assertIn("NOREMOVE", run(smith, "set obj plate extra +M").upper())
                    run(smith, "give plate zvictim")
                    self.assertIn("You wear silver plate on your body.",
                                  run(victim, "wear plate", 1.5))

                def heat_until(done) -> None:
                    for _ in range(60):
                        run(smith, "restore zvictim", 0.4)
                        run(smith, "restore zsmith", 0.4)
                        smith.send("cast 'heat metal' zvictim")
                        smith.drain(1.0)
                        victim.drain(0.2)
                        if done():
                            return
                    self.fail("heat metal never caught the plate:\n"
                              + smith.transcript[-1500:])

                # A removable piece warps and falls into the pack: the
                # wearer is exactly as armoured as with nothing on.
                plate(False)
                worn = armour(smith)
                self.assertNotEqual(worn, naked)
                mark = len(victim.transcript)
                heat_until(lambda: "Your armor warps" in victim.transcript[mark:])
                self.assertEqual(armour(smith), naked)
                run(victim, "drop plate", 1.0)
                run(smith, "purge", 1.0)

                # A piece that cannot come off is filed down in place; take
                # it off afterwards and nothing of it may remain.
                plate(True)
                worn = armour(smith)
                heat_until(lambda: armour(smith) != worn)
                heated = armour(smith)
                for before, after in zip(worn, heated):
                    self.assertGreater(after, before, "a filed-down piece protects less")
                run(smith, "set obj plate extra -M")
                run(victim, "remove plate", 1.5)
                self.assertEqual(armour(smith), naked)


if __name__ == "__main__":
    unittest.main()
