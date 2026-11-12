"""Text that is read back is never cut short (format-truncation review,
2026-11-12).

gcc 15 reported eight snprintf calls at -Wformat-truncation's first level
that gcc 13 and 14 do not, all joining a directory entry's name to a path
(d_name is the trailing array of struct dirent, which gcc 15 does not
bound), and its second level eighteen across the tree. Where a cut would
change what the game does -- a path, a ledger record, a telemetry row --
the text is now refused or given room; where it is shown to somebody, the
buffer has room for what is really there or the text a precision that
matches a real bound:

- toc_path_join joins a directory and a name only when all of it fits
  (string_safe.c); every directory walk uses it.
- format_tenths writes a number to one decimal place, held to a limit,
  through integers: "%.1f" of a double can be 312 bytes.
- snprintf_fits (merc.h) is the test of an snprintf's result.

tests/test_format_bounds.c checks the helpers; this module builds and runs
it and holds the source to them. tests/test_strict_warnings.py compiles the
tree with -Wformat-truncation=2.
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
SRC = ROOT / "src"
CC = os.environ.get("CC", "cc").split()[-1]


def strip_comments(code: str) -> str:
    """C source without its comments (no string literal here holds one)."""
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)
    return re.sub(r"//[^\n]*", " ", code)


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class FormatBoundsHarnessTests(unittest.TestCase):
    def test_the_helpers_hold_their_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_format_bounds"
            build = subprocess.run(
                [CC, "-std=c17", "-Wall", "-Wextra", "-Werror", "-DROM", "-Dunix",
                 "-I", str(SRC), "-o", str(binary), str(ROOT / "tests" / "test_format_bounds.c"),
                 str(SRC / "string_safe.c"), "-lm"],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
        self.assertEqual([l for l in run.stdout.splitlines() if l.startswith("FAIL")], [],
                         run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(run.stdout.strip(), "ok")


class FormatBoundsSourceTests(unittest.TestCase):
    def test_no_directory_entry_is_printed_into_a_path(self) -> None:
        """A directory entry's name reaches a path through toc_path_join."""
        found = []
        for path in sorted(SRC.glob("*.c")):
            code = strip_comments(path.read_text(encoding="latin-1"))
            for statement in re.split(r"[;{}]", code):
                if "snprintf" in statement and re.search(r"->d_name\b", statement):
                    found.append(f"{path.name}: {' '.join(statement.split())[:80]}")
        self.assertEqual(found, [], "snprintf of d_name; use toc_path_join")

    def test_the_ledger_refuses_a_record_it_cannot_finish(self) -> None:
        text = (SRC / "recovery.c").read_text(encoding="latin-1")
        body = text.split("bool recovery_record(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("snprintf_fits( n, sizeof(line) )", body)
        self.assertLess(body.index("snprintf_fits"), body.index("ledger_append"))

    def test_no_short_buffer_takes_a_bare_double(self) -> None:
        """The telemetry row and COMPARE's percentages go through
        format_tenths, so a huge or infinite value cannot cut them."""
        playlog = (SRC / "playlog.c").read_text(encoding="latin-1")
        consider = strip_comments(
            playlog.split("void progress_consider(", 1)[1].split("\n}\n", 1)[0])
        self.assertNotIn("%.1f", consider)
        self.assertEqual(consider.count("format_tenths("), 4)
        gear = strip_comments((SRC / "gear_compare.c").read_text(encoding="latin-1"))
        self.assertNotRegex(gear, r'"[AB] \+%\.1f')
        self.assertNotRegex(gear, r'%\.1f%% %s damage')


if __name__ == "__main__":
    unittest.main()
