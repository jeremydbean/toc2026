"""Every class gets the weapon proficiencies class_table gives it.

class_table has carried a weapon_prof[8] per class since forever -- how
good each class is with sword, dagger, spear, mace, axe, flail, whip and
polearm. Only do_remort ever read it, so a character who had not remorted
was left with the single weapon named in their base group and no way to
acquire another: the Weaponsmaster can practice all eight but do_practice
refuses a skill you do not already have, and his gain list is archery and
shove.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zprofone1"

# What a level 1 warrior can already use: the rest of the eight are known
# but gated behind level 3 (spear) and level 5 (polearm).
WARRIOR_AT_ONE = ("sword", "dagger", "mace", "axe", "flail", "whip")


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ClassWeaponProfTests(unittest.TestCase):
    def test_a_new_warrior_is_not_limited_to_swords(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zprofone", PASSWORD)
                listed = run(client, "practice", settle=4.0)

            for weapon in WARRIOR_AT_ONE:
                self.assertRegex(
                    listed, rf"\b{weapon}\s+\d+%",
                    f"a warrior should start able to use a {weapon}:\n{listed}")

            # And at their class's competence, not at 1%.
            sword = re.search(r"\bsword\s+(\d+)%", listed)
            self.assertIsNotNone(sword, listed)
            self.assertGreaterEqual(int(sword.group(1)), 40,
                                    f"sword should reflect the class:\n{listed}")

    def test_an_existing_character_gets_them_on_load(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zproftwo", PASSWORD)
                client.send("quit")
                client.wait_closed()

            # A character saved before the proficiencies were granted.
            path = mud.player_dir / "Zproftwo"
            weapon_line = re.compile(
                r"^Sk \d+ '(%s)'$" % "|".join(WARRIOR_AT_ONE))
            kept = [line for line in path.read_text("latin-1").split("\n")
                    if not weapon_line.match(line)]
            path.write_text("\n".join(kept), encoding="latin-1", newline="")

            with mud.connect(timeout=120) as client:
                login(client, "Zproftwo", PASSWORD)
                listed = run(client, "practice", settle=4.0)

            for weapon in WARRIOR_AT_ONE:
                self.assertRegex(
                    listed, rf"\b{weapon}\s+\d+%",
                    f"{weapon} should have been restored on load:\n{listed}")


if __name__ == "__main__":
    unittest.main()
