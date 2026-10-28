"""The last two guardians are sized for groups (owner, 2026-10-28).

The ashen Gleeok, Level 8's guardian, is a fight for two average players
at the top of the band and Ganon one for three; one may try, and should
expect to lose. It is balance, not a rule: the numbers are BOSS_STATS and
BOSS_VOLLEYS in scripts/build_hyrule_area.py, played live with
tools/hyrule_playtest/ganon_group.py (wiki/hyrule-area.md, "Guardian
Fights"). An instant kill takes a tenth of either's health, so a lucky
fatality cannot skip a fight meant for a group.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LastGuardianTests(unittest.TestCase):
    def test_the_ashen_gleeok_defies_instant_death(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("#define HYRULE_ASHEN_GLEEOK_VNUM 30316", fight)
        defies = fight[fight.index("bool hyrule_defies_instant_death("):]
        defies = defies[:defies.index("\n}\n")]
        self.assertIn("HYRULE_ASHEN_GLEEOK_VNUM", defies)
        self.assertIn("is_hyrule_ganon(victim)", defies)

    def test_no_party_rule(self) -> None:
        """One may try: nothing turns a lone player's blows aside."""
        for name in ("hyrule.c", "fight.c", "merc.h"):
            text = (ROOT / "src" / name).read_text(encoding="latin-1")
            self.assertNotIn("hyrule_party", text, name)


if __name__ == "__main__":
    unittest.main()
