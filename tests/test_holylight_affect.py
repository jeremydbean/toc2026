"""AFFECTS lists holy sight with the level it sees at (owner, 2026-11-03).

The Red Ring's sanctuary and the Master Sword's haste are listed by
AFFECTS as gear-granted spells. Holy sight is the same kind of thing --
a flag or an item, not an AFFECT_DATA -- and was listed nowhere: neither
staff with HOLYLIGHT on nor a player wearing the Triforce could see it
in AFFECTS. HELP HOLYLIGHT is level 59 so a mortal wearing it can read
it. holylight_level() answers both, at sight_trust(), the level
wizinvis and cloak are compared against: 59 for a mortal wearing the
Triforce, the staff member's own trust otherwise.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zholypass1"
TEMPLE = 4207
TRIFORCE = 30286


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\x1b\[[0-9;]*m", "", text))


@unittest.skipIf(SKIP is not None, SKIP or "")
class HolylightAffectLiveTests(unittest.TestCase):
    def test_holylight_is_listed_with_its_level(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zholystaff", Levl=70, Room=TEMPLE)
            make(mud, "Zholyhero", Levl=59, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zholystaff", PW)
                login(hero, "Zholyhero", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")

                # HELP HOLYLIGHT is level 59, so a Triforce wearer can read it.
                self.assertIn("Wearing the Triforce", plain(hero.sync("help holylight")))

                # Nothing worn, no flag: no holylight line.
                self.assertNotIn("holylight", plain(hero.sync("affects")))

                # The Triforce, worn, at its level of 59, naming it.
                staff.must(f"load obj {TRIFORCE}", "You create")
                staff.must("give triforce zholyhero", "You give")
                hero.sync("wear triforce")
                said = plain(hero.sync("affects"))
                self.assertIn("Spell: 'holylight' at level 59 from The Triforce, "
                              "for as long as it is worn.", said)
                hero.sync("remove triforce")
                self.assertNotIn("holylight", plain(hero.sync("affects")))

                # Staff with HOLYLIGHT on: their own sight, at their trust.
                said = plain(staff.sync("affects"))
                if "holylight" in said:
                    staff.must("holylight", "Holy light mode off")
                staff.must("holylight", "Holy light mode on")
                said = plain(staff.sync("affects"))
                self.assertIn("Power: 'holylight' at level 70, until you turn it off.", said)
                staff.must("holylight", "Holy light mode off")
                self.assertNotIn("holylight", plain(staff.sync("affects")))


if __name__ == "__main__":
    unittest.main()
