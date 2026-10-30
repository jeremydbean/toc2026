"""The help loader's keyword fold stays inside its buffer.

help_fold_keyword() checked for one byte and the terminator, then could
write a separator and a character in one step: a header of 4094 letters,
a tab and one more letter wrote the terminator at buf[4096] (review,
2026-10-30, AddressSanitizer). The fold is src/text_fold.c now, a module
with no game state, and tests/test_text_fold.c holds its boundaries under
AddressSanitizer when the compiler has it.
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


def build(out: Path, sanitize: bool) -> subprocess.CompletedProcess:
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g"] if sanitize else []
    return subprocess.run(
        [CC, "-std=gnu89", "-Wall", "-Werror", *flags, "-I", str(ROOT / "src"),
         "-o", str(out), str(ROOT / "tests" / "test_text_fold.c"),
         str(ROOT / "src" / "text_fold.c")],
        capture_output=True, text=True)


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class TextFoldHarnessTests(unittest.TestCase):
    def test_the_boundaries_hold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_text_fold"
            made = build(binary, sanitize=True)
            if made.returncode != 0:            # no sanitizer runtime here
                made = build(binary, sanitize=False)
            self.assertEqual(made.returncode, 0, made.stderr)
            env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1")
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=60, env=env)
        self.assertNotIn("AddressSanitizer", run.stderr, run.stderr)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn("FAIL", run.stdout)
        self.assertGreaterEqual(run.stdout.count("ok "), 11)


class TextFoldCallSiteTests(unittest.TestCase):
    def test_the_help_loader_folds_through_it(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        body = db[db.index("static void help_fold_keyword("):db.index("void load_helps(")]
        self.assertIn("fold_whitespace( pHelp->keyword, buf, sizeof(buf), &changed )", body)
        self.assertIn("kept unfolded", body, "an overlong header is said, not cut")
        self.assertNotIn("buf[n++]", body)
        self.assertIn("src/text_fold.c", (ROOT / "CMakeLists.txt").read_text())
