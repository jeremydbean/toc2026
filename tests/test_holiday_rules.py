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

New York's wall clock (the automatic seasonal restart is at 3am New York,
2026-11-12) is checked by the harness at the published transitions and
over every minute of 2007 to 2100, and here against the system's own
America/New_York: every hour from 2007 to 2040, and every minute of the
day either side of each change.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python before 3.9
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class HolidayRulesHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_holiday_rules"
            build = subprocess.run(
                [CC, "-std=c17", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_holiday_rules.c"),
                 str(ROOT / "src" / "holiday_rules.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_new_york_agrees_with_the_system_zone(self) -> None:
        if ZoneInfo is None:
            self.skipTest("no zoneinfo")
        try:
            zone = ZoneInfo("America/New_York")
        except ZoneInfoNotFoundError:
            self.skipTest("no tz database for America/New_York")
        epochs: list[int] = []
        start = int(datetime(2007, 1, 1, tzinfo=timezone.utc).timestamp())
        end = int(datetime(2041, 1, 1, tzinfo=timezone.utc).timestamp())
        epochs.extend(range(start, end, 3600))
        for year in range(2007, 2041):
            for month in (3, 11):
                for day in range(1, 15):
                    noon = datetime(year, month, day, 12, tzinfo=timezone.utc)
                    first = int((noon - timedelta(hours=24)).timestamp())
                    epochs.extend(range(first, first + 48 * 3600, 60))
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_holiday_rules"
            build = subprocess.run(
                [CC, "-std=c17", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_holiday_rules.c"),
                 str(ROOT / "src" / "holiday_rules.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary), "ny"], input="\n".join(map(str, epochs)) + "\n",
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        wrong = []
        lines = run.stdout.splitlines()
        self.assertEqual(len(lines), len(epochs))
        for line in lines:
            utc, y, m, d, hour, minute, offset = (int(x) for x in line.split())
            local = datetime.fromtimestamp(utc, timezone.utc).astimezone(zone)
            want = (local.year, local.month, local.day, local.hour, local.minute,
                    int(local.utcoffset().total_seconds()))
            if (y, m, d, hour, minute, offset) != want:
                wrong.append(f"{utc}: {y}-{m}-{d} {hour}:{minute} ({offset}) != {want}")
        self.assertEqual(wrong[:10], [], f"{len(wrong)} disagreements")

    def test_the_rules_stay_free_of_game_state(self) -> None:
        source = (ROOT / "src" / "holiday_rules.c").read_text(encoding="latin-1")
        self.assertNotIn("merc.h", source)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("src/holiday_rules.c", cmake)


if __name__ == "__main__":
    unittest.main()
