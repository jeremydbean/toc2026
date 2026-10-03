"""Misspellings players reported with TYPO stay fixed.

Every line ever filed to area/typos.txt was worked through in two passes
(October 2026). The slips below were each reported by a player -- or are
the same slip found elsewhere while fixing one -- and none may come back in
an active area file or in the source. Archived areas are not checked.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = {"korzath2old.are", "savedTrinidad.are"}

# pattern -> what it should read
REPORTED = {
    r"\bexplodeds\b": "explodes",
    r"\blooses its hardness\b": "loses its hardness",
    r"\bparliment\b": "parliament",
    r"\baboce\b": "above",
    r"\bdesperatly\b": "desperately",
    r"\bindecypherable\b": "indecipherable",
    r"\bbrige\b": "bridge",
    r"\brythm\b": "rhythm",
    r"\bjewlery\b": "jewelry",
    r"\btruely\b|\btruley\b": "truly",
    r"\baracne\b": "arcane",
    r"\bFactoy\b": "Factory",
    r"\bSrine\b": "Shrine",
    r"\bagins\b": "against",
    r"\balot of gold\b": "a lot of gold",
    r"\bCrytalmir\b": "Crystalmir",
    r"\btoo drunk too\b": "too drunk to",
    r"\bGods appreciates\b": "Gods appreciate",
    r"\b(?:what|this|it) use to be\b": "used to be",
    r"\bshiney\b": "shiny",
    r"\bfly's up\b": "flies up",
    r"\byour in too much pain\b": "you're in too much pain",
    r"\bcomes to life and ATTACK!": "ATTACKS!",
    r"covers the walls give off": "gives off",
}


def active_area_files() -> list[Path]:
    listed = (ROOT / "area" / "area.lst").read_text(encoding="latin-1").split()
    return [ROOT / "area" / name for name in listed
            if name.endswith(".are") and name not in ARCHIVED
            and (ROOT / "area" / name).is_file()]


class ReportedTypoTests(unittest.TestCase):
    def test_no_reported_misspelling_is_back(self) -> None:
        files = active_area_files() + sorted((ROOT / "src").glob("*.c"))
        found = []
        for path in files:
            text = path.read_text(encoding="latin-1")
            for pattern, wanted in REPORTED.items():
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    line = text.count("\n", 0, match.start()) + 1
                    found.append(f"{path.name}:{line}: {match.group(0)!r} -> {wanted}")
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
