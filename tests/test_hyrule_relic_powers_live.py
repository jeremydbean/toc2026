"""Hyrule's worn powers, in a running game.

The Triforce, made whole, is a light, and worn in the light slot it gives the
sight of a level 59 character with HOLYLIGHT on: through invisibility and
the wizinvis of anybody at or below 59, and no further. The Master Sword
hastens whoever wields it and the Red Ring of Hyrule wraps its wearer in
sanctuary; both come off with the item, and haste a spell gave stays.

Everything runs in the Temple (4207), where nothing attacks a mortal.
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

PASSWORD = "Ztrifpass1"
TEMPLE = 4207
TRIFORCE = 30286
LETTER = 30500          # Princess Zelda's letter: "A sealed royal letter"
MASTER_SWORD = 30200
RED_RING = 30579
CLOCK_FLASK = 30628     # the Death Mountain clock-flask: a potion of haste


def run(client, command: str, settle: float = 1.5) -> str:
    # Swallow what arrived since the last command first -- "Ztrigod gives
    # you The Triforce" names the god the look must not see.
    client.drain(0.5)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    # Full strength: a weight-20 sword is too heavy for a fresh character.
    patch_player_file(mud, name, Levl=level, Room=TEMPLE, Attr="25 25 25 25 25")


def affected_by(god, name: str) -> str:
    """The "Affect 1" line of STAT CHAR -- which is left out altogether
    when nothing is set, so an absent line is an empty answer."""
    shown = run(god, f"stat char {name}", settle=2.0)
    if "Name:" not in shown:
        raise AssertionError(f"stat did not answer:\n{shown}")
    match = re.search(r"Affect 1: ([^\r\n]*)", shown)
    return match.group(1) if match else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class TriforceSightTests(unittest.TestCase):
    def test_the_triforce_sees_what_a_level_59_with_holylight_sees(self) -> None:
        with LiveMud() as mud:
            make(mud, "Ztriwear", 58)
            make(mud, "Ztrigod", 70)

            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Ztriwear", PASSWORD)
                login(god, "Ztrigod", PASSWORD)

                # An invisible letter on the floor, and the god hiding
                # at wizinvis 59 -- one level above the hero.
                setup = "".join((
                    run(god, f"load obj {LETTER}"),
                    # Dropped first: once invisible, the god cannot see it.
                    run(god, "drop letter"),
                    run(god, "set obj letter extra +F"),
                    run(god, f"load obj {TRIFORCE}"),
                    run(god, "give triforce ztriwear"),
                    run(god, "wizinvis 59", settle=2.0),
                ))

                bare = run(hero, "look", settle=2.0)
                self.assertNotIn("sealed royal letter", bare.lower(),
                                 f"an invisible letter should be unseen:\n{bare}")
                self.assertNotIn("Ztrigod", bare,
                                 f"wizinvis 59 hides from a level 58:\n{bare}")

                worn = run(hero, "wear triforce", settle=2.0)
                self.assertIn("triforce", worn.lower(), worn)
                eq = run(hero, "equipment", settle=2.0)
                self.assertRegex(eq.lower(), r"light[^\n]*\n?[^\n]*triforce",
                                 f"the Triforce goes in the light slot:\n{eq}")

                seeing = run(hero, "look", settle=2.0)
                self.assertIn("sealed royal letter", seeing.lower(),
                              f"the Triforce sees the invisible:\n{seeing}\n"
                              f"--- setup ---\n{setup}")
                self.assertIn("Ztrigod", seeing,
                              f"a level 59's holy sight sees wizinvis 59:\n{seeing}")

                # A level 59 immortal could not see wizinvis 60, and nor
                # can the Triforce.
                run(god, "wizinvis 60", settle=2.0)
                above = run(hero, "look", settle=2.0)
                self.assertNotIn("Ztrigod", above,
                                 f"wizinvis 60 is beyond the Triforce:\n{above}")
                self.assertIn("sealed royal letter", above.lower(), above)

                run(hero, "remove triforce", settle=2.0)
                after = run(hero, "look", settle=2.0)
                self.assertNotIn("sealed royal letter", after.lower(),
                                 f"the sight goes with the Triforce:\n{after}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class WornPowersTests(unittest.TestCase):
    def test_the_sword_hastens_and_the_ring_sanctifies_while_worn(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zswordhand", 58)
            make(mud, "Zswordgod", 70)

            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zswordhand", PASSWORD)
                login(god, "Zswordgod", PASSWORD)

                for vnum, keyword in ((MASTER_SWORD, "sword"), (RED_RING, "ring"),
                                      (CLOCK_FLASK, "clock")):
                    run(god, f"load obj {vnum}")
                    run(god, f"give {keyword} zswordhand")

                self.assertNotIn("haste", affected_by(god, "zswordhand"))
                wielded = run(hero, "wield sword", settle=2.0)
                self.assertIn("haste", affected_by(god, "zswordhand"),
                              f"the Master Sword hastens its wielder:\n{wielded}")
                # ...and AFFECTS says so, with what is giving it: a bit
                # on an item is not an affect on the character, and the
                # list used to leave it out.
                listed = run(hero, "affect", settle=1.5)
                self.assertIn("Spell: 'haste' from the Master Sword", listed)
                run(hero, "remove sword", settle=2.0)
                self.assertNotIn("haste", affected_by(god, "zswordhand"),
                                 "and the haste goes with it")
                self.assertNotIn("'haste'", run(hero, "affect", settle=1.5))

                run(hero, "wear ring", settle=2.0)
                self.assertIn("sanctuary", affected_by(god, "zswordhand"),
                              "the Red Ring gives sanctuary")
                listed = run(hero, "affect", settle=1.5)
                self.assertIn("Spell: 'sanctuary' from the Red Ring of Hyrule",
                              listed)
                run(hero, "remove ring", settle=2.0)
                self.assertNotIn("sanctuary", affected_by(god, "zswordhand"))
                self.assertNotIn("'sanctuary'", run(hero, "affect", settle=1.5))

                # Haste from a spell outlasts the sword.
                quaffed = run(hero, "quaff clock", settle=2.0)
                self.assertIn("haste", affected_by(god, "zswordhand"), quaffed)
                run(hero, "wield sword", settle=2.0)
                run(hero, "remove sword", settle=2.0)
                self.assertIn("haste", affected_by(god, "zswordhand"),
                              "a spell's haste stays when the sword comes off")


if __name__ == "__main__":
    unittest.main()
