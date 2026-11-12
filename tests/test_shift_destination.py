"""SHIFT asks whether the target may be carried into the caster's room
(review, 2026-11-12; do_shift in src/magic2.c).

SHIFT pulls the target to the caster, but its room test asked
travel_spell_refuses( caster, target's room ) -- astral walk's question,
about the caster going the other way. So a psionic standing in a guild
hall pulled in somebody that hall's guard would never let walk in, and a
mobile into a no-mob room. It now asks travel_spell_refuses( target,
caster's room ), as summon and teleport ask of the one carried, and keeps
a mobile out of a no-mob room, all before any mana, stun or rift. The
jail refusals (tests/test_jail_companions.py) are untouched.

The warrior guild's hall is behind its guard (gg_table: mob 4400 at room
4401, north): the courtyard 4403 carries no room flag that SHIFT's own
tests refuse, and its tunnel 4402 is no-mob. Synthetic Z characters in a
throwaway world only.
"""
from __future__ import annotations

import unittest

from live_mud import (LiveMud, SPARRING_FLOOR, login, place_sparring_guard,
                      room_of, skip_reason)
from test_jail_companions import MANA, stat_line
from test_jail_confinement import PW, TEMPLE, give_skill, make

SKIP = skip_reason()
HALL = 4403          # Courtyard, the Citadel of War: flags INDOORS only
NO_MOB_HALL = 4402   # Tunnel to courtyard: NO_MOB, INDOORS
GUILD_WARRIOR = 3
GUILD_NONE = 11
REFUSED = "cannot form a safe spatial path"


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShiftDestinationTests(unittest.TestCase):
    def test_shift_asks_what_the_target_may_enter(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zshiftstaff", 70)
            make(mud, "Zshifter", 50, room=HALL, HpManaMove=MANA, Gui=GUILD_WARRIOR)
            make(mud, "Zoutsider", 20, Gui=GUILD_NONE)
            make(mud, "Zguildsman", 20, Gui=GUILD_WARRIOR)
            give_skill(mud, "Zshifter", "shift", 100)

            with mud.connect(timeout=120) as staff, \
                 mud.connect(timeout=120) as psion, \
                 mud.connect(timeout=120) as outsider, \
                 mud.connect(timeout=120) as guildsman:
                login(staff, "Zshiftstaff", PW)
                login(psion, "Zshifter", PW)
                login(outsider, "Zoutsider", PW)
                login(guildsman, "Zguildsman", PW)
                for client in (staff, psion, outsider, guildsman):
                    client.sync("scroll 0")
                for client in (outsider, guildsman):
                    client.must("nosummon", "no longer immune")
                self.assertEqual(HALL, room_of(staff, "Zshifter"))

                def mana() -> int:
                    return int(stat_line(staff, "Zshifter", r"Mana: (-?\d+)/").group(1))

                def position() -> int:
                    return int(stat_line(staff, "Zshifter", r"Position: (\d+)").group(1))

                # Somebody the hall's guard turns away: refused, free.
                before = mana()
                said = psion.sync("shift zoutsider")
                self.assertIn(REFUSED, said)
                self.assertNotIn("rift", said)
                self.assertEqual(before, mana(), "mana spent on a refusal")
                self.assertEqual(8, position(), "stunned by a refusal")
                self.assertEqual(TEMPLE, room_of(staff, "Zoutsider"),
                                 "pulled into a hall they may not walk into")

                # A mobile into a no-mob room: refused, free.
                place_sparring_guard(staff, "Zshiftstaff", SPARRING_FLOOR)
                staff.sync("goto %d" % TEMPLE)
                staff.must("transfer zshifter %d" % NO_MOB_HALL, "Ok", "transfer", "arrives")
                self.assertEqual(NO_MOB_HALL, room_of(staff, "Zshifter"))
                before = mana()
                said = psion.sync("shift sparring")
                self.assertIn(REFUSED, said)
                self.assertEqual(before, mana(), "mana spent on a refusal")
                self.assertEqual(SPARRING_FLOOR, room_of(staff, "sparring"))

                # Control: a member of the guild is pulled in.
                staff.must("transfer zshifter %d" % HALL, "Ok", "transfer", "arrives")
                self.assertIn("spatial rift", psion.sync("shift zguildsman"))
                self.assertEqual(HALL, room_of(staff, "Zguildsman"))


if __name__ == "__main__":
    unittest.main()
