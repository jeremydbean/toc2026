"""Live tests set up their world with commands that prove they worked.

CI, 2026-10-25: five modules "pinned" the Korzath security guard with
SET MOB 29012 ACT +SENTINEL and checked only that the reply did not say
"Syntax". SET MOB refuses every prototype that came with the game ("came
with the game, not from an area built here"), so the guard went on
wandering and fleeing (it is WIMPY and STAY_AREA), and three tests failed
at random when it had walked off. The fixture world (LiveMud(fixtures=True),
tests/fixtures/area/ztestfix.are) has a guard that is a sentinel by
design, and place_sparring_guard() proves it with STAT.

These source checks keep the two habits from coming back: making a shipped
mobile stand still with SET MOB, and confirming a setup command by the
absence of an error rather than by what it says it did.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import live_mud  # noqa: E402

TESTS = sorted(p for p in (ROOT / "tests").glob("test_*.py") if p.name != Path(__file__).name)


class FixtureHygieneTests(unittest.TestCase):
    def test_no_test_pins_a_shipped_mobile_with_set_mob(self) -> None:
        offenders = []
        for path in TESTS:
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"set mob \S+ act \+sentinel", text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line}")
        self.assertEqual([], offenders, "use LiveMud(fixtures=True) and place_sparring_guard()")

    def test_no_setup_is_confirmed_by_a_missing_syntax_message(self) -> None:
        offenders = []
        for path in TESTS:
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r'assertNotIn\(\s*"Syntax"', text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line}")
        self.assertEqual([], offenders, "confirm with MudClient.must(command, what it says)")

    def test_the_fixture_guard_is_a_sentinel_that_never_flees_or_attacks(self) -> None:
        text = live_mud.FIXTURE_AREA.read_text(encoding="latin-1")
        record = text[text.index(f"#{live_mud.SPARRING_GUARD}\n"):text.index("#0\n")]
        act = record.split("human~\n", 1)[1].split()[0]   # the line after the race
        self.assertEqual(act, "AB", "npc and sentinel only: no aggressive (F), "
                                    "stay-area (G) or wimpy (H)")

    def test_the_fixture_vnums_belong_to_no_shipped_area(self) -> None:
        sys.path.insert(0, str(ROOT / "webadmin"))
        from area_parser import AreaParser
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        fixture = range(32700, 32720)
        used = (set(parser.rooms) | set(parser.mobiles) | set(parser.objects)) & set(fixture)
        self.assertEqual(set(), used)


if __name__ == "__main__":
    unittest.main()
