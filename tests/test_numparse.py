"""Checked number parsing (modernization project 2, 2026-11-11).

atoi() read "5abc" as 5, "abc", "" and "-" as 0, and a number past int's
range as garbage, so a typed slip set a level, a vnum or an amount to
something nobody asked for. src/numparse.c's parse_int and parse_long
take a whole decimal number in a range or refuse it.
tests/test_numparse.c checks them exactly; this module builds and runs
it, and holds the game source to the rule: no atoi() call anywhere in
src/, so a new one cannot creep back in unnoticed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class NumparseHarnessTests(unittest.TestCase):
    def build_and_run(self, std: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_numparse"
            build = subprocess.run(
                [CC, f"-std={std}", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_numparse.c"),
                 str(ROOT / "src" / "numparse.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_the_harness_passes_gnu89(self) -> None:
        self.build_and_run("gnu89")

    def test_the_harness_passes_c17(self) -> None:
        self.build_and_run("c17")


class NumparseSourceTests(unittest.TestCase):
    def test_the_parser_stays_free_of_game_state(self) -> None:
        source = (ROOT / "src" / "numparse.c").read_text(encoding="latin-1")
        self.assertNotIn("merc.h", source)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("src/numparse.c", cmake)

    def test_no_atoi_in_the_game(self) -> None:
        """Every number the game reads goes through numparse.c or an
        explicit strtol. Comments may still name atoi."""
        call = re.compile(r"\batoi\s*\(")
        found = []
        for path in sorted((ROOT / "src").glob("*.[ch]")):
            text = path.read_text(encoding="latin-1")
            text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
            for number, line in enumerate(text.splitlines(), 1):
                code = line.split("//", 1)[0]
                if call.search(code):
                    found.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(found, [], "atoi() is back; use parse_int/parse_long:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
