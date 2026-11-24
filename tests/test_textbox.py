"""src/textbox.c on its own: the wrap counts colour as color_strlen does.

Review, 2026-11-24: tbox_bytes_for() skipped "{XY" colour tokens but counted
a raw "\\x02" marker and its slot byte as two columns, so a text row holding
markers wrapped early, and a cut by width alone could fall between "\\x02"
and its slot byte -- leaving the marker to eat the border's first character.
tests/test_textbox.c draws such rows and checks every line is as wide as the
box, filled before it wraps, and no marker is split. Under AddressSanitizer
and UBSan where the compiler has them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CC = os.environ.get("CC", "cc").split()[-1]
SOURCES = ["textbox.c", "color.c", "dstring.c", "string_safe.c"]


def build(binary: Path, sanitize: bool) -> subprocess.CompletedProcess:
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g"] if sanitize else []
    return subprocess.run(
        [CC, "-std=gnu89", "-DROM", "-fcommon", "-Wall", "-Wextra", "-Wno-unused-parameter",
         "-Wno-missing-field-initializers", "-Werror", *flags, "-I", str(SRC),
         "-o", str(binary), str(ROOT / "tests" / "test_textbox.c"),
         *(str(SRC / s) for s in SOURCES)],
        capture_output=True, text=True)


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class TextBoxHarnessTests(unittest.TestCase):
    def test_markers_neither_wrap_early_nor_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_textbox"
            made = build(binary, sanitize=True)
            if made.returncode != 0:
                made = build(binary, sanitize=False)
            self.assertEqual(made.returncode, 0, made.stderr)
            leaks = "detect_leaks=1:" if os.uname().sysname == "Linux" else ""
            env = dict(os.environ, ASAN_OPTIONS=leaks + "halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=60, env=env)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stdout.strip(), "ok", run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
