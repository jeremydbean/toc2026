"""Experience for a tough mobile, and Gangland's gang members (2026-11-15).

xp_compute pays 15% more for a mobile with special abilities, and asked
OFF_SUMMONER of `act`, where its bit is ACT_NOPURGE: every no-purge
mobile was paid the bonus and no summoner ever was. And Gangland's level 5
gang members disarmed and tripped the level 7 players who fought them,
27 seconds a kill against Mud School's 3 (tools/balance_report.py): they
keep their dodge and lose the disarm and the trip.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webadmin import area_reader  # noqa: E402


class XpBonusTests(unittest.TestCase):
    def test_the_summoner_bonus_reads_the_offensive_flags(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        body = fight.split("int xp_compute(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("IS_SET(victim->off_flags, OFF_SUMMONER)", body)
        self.assertIsNone(re.search(r"victim->act,\s*OFF_", body))

    def test_the_gang_members_neither_disarm_nor_trip(self) -> None:
        area = area_reader.read_area_file(ROOT / "area" / "hood.are")
        offs = {m.vnum: m.off.text for m in area.mobiles}
        for vnum in (2101, 2102):
            self.assertNotIn("E", offs[vnum], vnum)   # OFF_DISARM
            self.assertNotIn("N", offs[vnum], vnum)   # OFF_TRIP
            self.assertIn("F", offs[vnum], vnum)      # OFF_DODGE stays
        self.assertEqual(offs[2103], "EFNU", "the gang leader is unchanged")


if __name__ == "__main__":
    unittest.main()
