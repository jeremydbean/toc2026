"""A vampiric weapon drinks only from blows that land (owner, 2026-10-22).

one_hit healed the wielder a twentieth of the blow and moved them a point
toward the dark before damage() had resolved parry, dodge, shield block or
immunity, so a blow that did nothing still fed. The drink now happens
where hit points really come off, from what was taken.

Measured by alignment, which no tick regenerates: a vampiric sword against
the training dummy -- which absorbs every blow, so nothing is ever taken --
must leave the wielder's alignment where it was, and the same sword
against a mobile that does lose hit points must move it.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zvampire1"
HALLS = 4202            # not safe
YARD = 2419             # the training yard: the dummy absorbs every blow
GUARD = 29012           # a Korzath security guard, 600 hit points: hit, not killed
VAMPIRIC = 4            # WEAPON_VAMPIRIC, bit C, in value[4]


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def alignment(client) -> int:
    client.drain(2.0)
    # A command waits out the fight's lag (a bash is two rounds) before it
    # runs, and its reply window has to hold both.
    match = re.search(r"alignment (-?\d+)", run(client, "alignment", 10.0))
    if not match:
        raise AssertionError("no alignment in:\n" + client.transcript[-600:])
    return int(match.group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class VampiricLandingTests(unittest.TestCase):
    def test_only_a_landed_blow_feeds_the_wielder(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zvampwield", 30), ("Zvampgod", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=HALLS, Alig=0,
                                  HMV="9000 9000 500 500 500 500", HMVP="9000 500 500")
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zvampwield", PW)
                login(god, "Zvampgod", PW)
                run(hero, "scroll 0")
                # Both start with a school sword: away with them, so the
                # one made vampiric is the only sword about.
                for client in (hero, god):
                    run(client, "remove sword")
                    run(client, "drop sword")
                run(god, "purge", 0.8)
                run(god, "load obj 3702")
                run(god, f"set obj sword v4 {VAMPIRIC}")
                self.assertIn("vampiric", run(god, "stat obj sword", 1.2).lower())
                run(god, "give sword zvampwield")
                run(hero, "wield sword")

                # The dummy: every swing lands on something that loses
                # nothing. Staff stop the fight in the yard.
                before = alignment(hero)
                run(god, f"transfer zvampwield {YARD}", 1.0)
                run(hero, "kill dummy", 1.0)
                hero.drain(15.0)              # five rounds of swings
                run(god, f"goto {YARD}", 0.6)
                run(god, "peace", 0.6)
                run(god, f"transfer zvampwield {HALLS}", 1.0)
                run(god, f"goto {HALLS}", 0.6)
                immune_after = alignment(hero)

                # A worker with hit points to lose: landed blows move it.
                run(god, f"set mob {GUARD} act +sentinel")   # it wanders off otherwise
                run(god, f"load mob {GUARD}")
                run(hero, "kill guard", 1.0)
                hero.drain(9.0)               # three rounds: hurt, not killed
                run(god, "purge guard", 0.6)  # ends the fight outright
                landed_after = alignment(hero)
                for client in (hero, god):
                    client.send("quit")
                    client.wait_closed()

        self.assertEqual(immune_after, before, "blows that did nothing moved the wielder")
        self.assertLess(landed_after, immune_after, "landed blows did not drink")
