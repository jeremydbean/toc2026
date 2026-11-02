"""The holiday calendar's pure rules (review, 2026-11-02).

tests/test_holiday_rules.c checks src/holiday_rules.c exactly: every day
from 1900 to 9999 round-trips through the day arithmetic, dates are
validated and parsed strictly (February 29 only in a leap year, no
thirty-first of a thirty-day month, nothing but YYYY-MM-DD), Easter and
Thanksgiving match published dates and fall on the right weekday every
year, and the firework cooldown table keeps one clock per area -- A then
A waits the whole gap, A then B then A does not broadcast A twice, B
keeps its own time, one second short is refused and exactly the gap is
allowed. The live tests in tests/test_holidays.py play the same rules
through the game.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class HolidayRulesHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_holiday_rules"
            build = subprocess.run(
                [CC, "-std=gnu89", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_holiday_rules.c"),
                 str(ROOT / "src" / "holiday_rules.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_the_rules_stay_free_of_game_state(self) -> None:
        source = (ROOT / "src" / "holiday_rules.c").read_text(encoding="latin-1")
        self.assertNotIn("merc.h", source)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("src/holiday_rules.c", cmake)


if __name__ == "__main__":
    unittest.main()
