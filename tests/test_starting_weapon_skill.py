"""A new character must be able to use the weapon it is handed.

The class groups leave the matching weapon skill at 1%, and only the
customization path granted 40. A player who declined customization -- the
default -- was issued a weapon they missed with almost every swing. It
affected every class, not just casters: a fresh warrior swung a sword at 1%.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_mud  # noqa: E402
from live_mud import LiveMud, create_character, skip_reason  # noqa: E402

SKIP = skip_reason()

PASSWORD = "Zweapskl12"
MINIMUM = 40  # STARTING_WEAPON_SKILL in src/merc.h

WEAPONS = ("sword", "dagger", "mace", "axe", "flail", "whip", "polearm", "spear")

BASE_STEPS = live_mud.CREATION_STEPS


def steps_for(klass: str):
    """The creation walk, answering with a specific class."""
    return tuple(
        (needle, klass if needle == "select a class" else reply)
        for needle, reply in BASE_STEPS
    )


@unittest.skipIf(SKIP is not None, SKIP or "")
class StartingWeaponSkillTests(unittest.TestCase):
    def tearDown(self) -> None:
        live_mud.CREATION_STEPS = BASE_STEPS

    def test_every_class_can_use_its_issued_weapon(self) -> None:
        # One server, several characters: spinning up a MUD per class is slow
        # and the creation path is what is under test, not isolation.
        with LiveMud() as mud:
            for klass, suffix in (
                ("warrior", "Warr"),
                ("necromancer", "Necr"),
                ("mage", "Mage"),
                ("cleric", "Cler"),
            ):
                with self.subTest(klass=klass):
                    live_mud.CREATION_STEPS = steps_for(klass)
                    with mud.connect(timeout=120) as client:
                        create_character(client, "Zwsk" + suffix, PASSWORD)
                        mark = len(client.transcript)
                        client.send("skills")
                        client.drain(3.0)
                        skills = client.transcript[mark:]

                    percentages = {}
                    for weapon in WEAPONS:
                        match = re.search(weapon + r"\s+(\d+)%", skills)
                        if match:
                            percentages[weapon] = int(match.group(1))

                    self.assertTrue(
                        percentages,
                        f"{klass} listed no weapon skill at all:\n{skills}",
                    )
                    best = max(percentages.values())
                    self.assertGreaterEqual(
                        best,
                        MINIMUM,
                        f"{klass} starts at {best}% with its issued weapon "
                        f"(want >= {MINIMUM}): {percentages}",
                    )


if __name__ == "__main__":
    unittest.main()
