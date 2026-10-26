"""Psionic armor and psychic shield turn a mental blow (review, 2026-10-26).

damage() asked skill_lookup("psionic_armor") and "psychic_shield" for its
DAM_MENTAL reduction; the skills are named with a space, so neither ever
matched and only mindbar turned a mental blow. It now asks the same rule
the mana and movement drains use, by gsn: a quarter off for armor or
shield, half for mindbar, and the three exclude one another.

The players fight in the fixture world's arena. TORMENT at level 50 rolls
25 to 150 before anything else, and every later step of damage() can only
lower it, so with armor or shield no torment can show more than 113 on the
caster's DAMAGENUMBERS, and with mindbar no more than 75. That bound is
certain on the fixed code; on the old code an armored victim took an
unreduced roll above 113 in about one torment in seven.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    MIND_ARENA,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zmindpass1"
LEVEL = 50
RAW_MAX = LEVEL * 3                  # torment: number_range(level/2, level*3)
TRIALS = 15
ANSI = re.compile(r"\x1b\[[0-9;]*m")
NUMBER = re.compile(r"Your pain [^\n]*?\[-(\d+)\]")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def torments(test, staff, caster, victim: str) -> list:
    """TRIALS torments at the victim; the numbers the caster was shown."""
    seen = []
    for _ in range(TRIALS):
        staff.must(f"restore {victim}", "")
        staff.must("restore zmindcaster", "")
        said = ANSI.sub("", caster.sync(f"torment {victim}", 20))
        # Its damage message names it "pain".
        test.assertNotIn("lost your concentration", said)
        seen += [int(n) for n in NUMBER.findall(said)]
    return seen


@unittest.skipIf(SKIP is not None, SKIP or "")
class MentalDefenceTests(unittest.TestCase):
    def test_armor_shield_and_mindbar_each_turn_a_mental_blow(self) -> None:
        hmv = dict(HMV="3000 3000 30000 30000 1000 1000", HMVP="3000 30000 1000",
                   Levl=LEVEL, Room=MIND_ARENA, Alig=0)
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zmindstaff", Levl=70, Room=MIND_ARENA)
            for name in ("Zmindcaster", "Zmindarmor", "Zmindshield", "Zmindbar"):
                make(mud, name, **hmv)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as caster, \
                    mud.connect(timeout=120) as armor, mud.connect(timeout=120) as shield, \
                    mud.connect(timeout=120) as bar:
                for client, name in ((staff, "Zmindstaff"), (caster, "Zmindcaster"),
                                     (armor, "Zmindarmor"), (shield, "Zmindshield"),
                                     (bar, "Zmindbar")):
                    login(client, name, PW)
                staff.must("set skill zmindcaster torment 100", "")
                for name in ("zmindarmor", "zmindshield", "zmindbar"):
                    for power in ("psionic armor", "psychic shield", "mindbar"):
                        staff.must(f"set skill {name} '{power}' 100", "")
                caster.must("damagenumbers", "")

                armor.must("psionic", "")
                shield.must("psychic", "")
                bar.must("mindbar", "")
                # Each holds one, and the others refuse: they exclude.
                for client, others in ((armor, ("mindbar", "psychic")),
                                       (shield, ("psionic", "mindbar")),
                                       (bar, ("psionic", "psychic"))):
                    for other in others:
                        self.assertRegex(client.sync(other).lower(), "already protected")

                at_armor = torments(self, staff, caster, "zmindarmor")
                at_shield = torments(self, staff, caster, "zmindshield")
                at_bar = torments(self, staff, caster, "zmindbar")

        quarter_off = RAW_MAX - RAW_MAX // 4
        for name, seen, bound in (("armor", at_armor, quarter_off),
                                  ("shield", at_shield, quarter_off),
                                  ("mindbar", at_bar, RAW_MAX // 2)):
            with self.subTest(name):
                self.assertGreaterEqual(len(seen), TRIALS // 2, f"{name}: too few landed")
                self.assertLessEqual(max(seen), bound, f"{name}: {sorted(seen)}")


if __name__ == "__main__":
    unittest.main()
