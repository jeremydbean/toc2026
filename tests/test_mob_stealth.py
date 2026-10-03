"""Stealth and shadowmeld are invisible without holylight -- no roll.

can_see used to roll a concealment chance on every look, so a stealthed
level 20 in daylight was seen seven looks in ten and blinked in and out
between two LOOKs. The owner's rule: stealth and shadowmeld are simply not
seen without holylight or the Triforce. Getting the bit is still a skill
roll, made when the skill is used; a stealthed mobile that is fighting
shows itself, as a hiding one does, so a player can see what attacks them.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = (ROOT / "src" / "handler.c").read_text(encoding="latin-1").replace("\r\n", "\n")


def can_see_body() -> str:
    start = HANDLER.index("bool can_see( CHAR_DATA *ch, const CHAR_DATA *victim )")
    end = HANDLER.index("bool can_see_obj(", start)
    return HANDLER[start:end]


class StealthIsAbsoluteTests(unittest.TestCase):
    def test_no_roll_anywhere_in_sight(self) -> None:
        self.assertNotIn("concealment_chance(", HANDLER)
        self.assertNotIn("number_percent", can_see_body())

    def test_stealth_hides_except_a_fighting_mobile(self) -> None:
        self.assertIn(
            "if ( IS_AFFECTED2(victim, AFF2_STEALTH)\n"
            "    &&   !( IS_NPC(victim) && victim->fighting != NULL ) )\n"
            "\treturn false;",
            can_see_body())

    def test_shadowmeld_hides_outright(self) -> None:
        self.assertIn("if ( IS_AFFECTED2(victim, AFF2_SHADOWMELD) )\n\treturn false;",
                      can_see_body())

    def test_holylight_and_the_triforce_are_asked_first(self) -> None:
        body = can_see_body()
        shortcut = body.index("triforce_sight( ch )")
        self.assertLess(shortcut, body.index("AFF2_STEALTH)\n"))
        self.assertLess(shortcut, body.index("AFF2_SHADOWMELD) )"))


if __name__ == "__main__":
    unittest.main()
