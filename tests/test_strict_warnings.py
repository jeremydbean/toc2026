"""The game compiles with no conversion, sign or shadow warning.

Strict-warnings sweep, 2026-11-12 (owner: "do it all"). Silent narrowing --
an int stored into a 16-bit field -- is the bug class behind the WIMPY and
pool bugs: WIMPY and the hit point pools were sh_int, read from an int, and
wrapped negative past 32,767 with nothing said. -Wconversion names every
such store. The sweep left the whole tree clean under it, -Wsign-conversion,
-Wsign-compare and -Wshadow, and both builds now carry the flags (CI makes
them errors). This module is the line: it compiles every file in src/ with
those flags and fails on any warning at all, naming the file, the line and
the flag. See "Strict Warnings" in the agents' guide for how to fix one -- never by
a bare cast that keeps the wrap.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# The class the sweep made clean, beside what both builds already use.
STRICT_FLAGS = [
    "-Wall", "-Wextra", "-Wpedantic",
    "-Wno-unused-parameter", "-Wno-missing-field-initializers",
    "-Wshadow", "-Wsign-compare", "-Wconversion", "-Wsign-conversion",
]
CONVERSION_FLAGS = ["-Wshadow", "-Wsign-compare", "-Wconversion", "-Wsign-conversion"]


def compiler() -> str | None:
    for name in ("gcc", "cc"):
        path = shutil.which(name)
        if path:
            return path
    return None


CC = compiler()


# Every way the builds compile: Release is -O2, the sanitizer build -O0
# under ASan and UBSan. They disagree: gcc folds constants at -O2 that it
# warns about at -O0 (a const size_t handed to alloc_mem's int), and
# UBSan's instrumentation hides the ranges -Wconversion reads (LOWER into
# a char was clean until -fsanitize=undefined).
SANITIZE = ("-O0", "-fsanitize=address", "-fsanitize=undefined")
VARIANTS = [("-O0",), ("-O2",), SANITIZE]


def sanitizer_supported() -> bool:
    if CC is None:
        return False
    proc = subprocess.run([CC, "-x", "c", "-fsyntax-only", *SANITIZE, "-"],
                          input="int main(void) { return 0; }\n",
                          capture_output=True, text=True)
    return proc.returncode == 0


def compile_one(job: tuple[Path, tuple[str, ...]]) -> tuple[Path, str]:
    path, variant = job
    proc = subprocess.run(
        [CC, "-std=c17", *variant, "-DROM", "-Dunix", "-I", str(SRC), "-fsyntax-only",
         *STRICT_FLAGS, str(path)],
        cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=300)
    return path, proc.stderr if proc.returncode == 0 else proc.stderr + "\n(compile failed)"


@unittest.skipIf(CC is None, "no C compiler (gcc or cc) on PATH")
class StrictWarningTests(unittest.TestCase):
    def test_every_source_file_is_clean(self) -> None:
        files = sorted(SRC.glob("*.c"))
        self.assertGreater(len(files), 50, "src/*.c not found")
        with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as pool:
            variants = [v for v in VARIANTS if v is not SANITIZE or sanitizer_supported()]
            results = list(pool.map(compile_one,
                                    [(f, v) for v in variants for f in files]))

        warnings: list[str] = []
        failed: list[str] = []
        for path, err in results:
            if "(compile failed)" in err and path.name not in failed:
                failed.append(path.name)
            warnings.extend(line for line in err.splitlines()
                            if "warning:" in line and line not in warnings)
        kinds = Counter(m.group(0) for line in warnings
                        for m in [re.search(r"\[-W[^\]]+\]", line)] if m)
        self.assertEqual(failed, [], "files that did not compile")
        self.assertEqual(
            warnings, [],
            "%d warning(s) under %s, by kind %s; first ones:\n%s"
            % (len(warnings), " ".join(CONVERSION_FLAGS), dict(kinds),
               "\n".join(warnings[:40])))


class BuildFlagTests(unittest.TestCase):
    """Both builds keep the flags on, and CI makes them errors."""

    def test_makefile_default_carries_them(self) -> None:
        text = (ROOT / "Makefile").read_text()
        line = re.search(r"^CONVERSION_WARNINGS\s*:=\s*(.*)$", text, re.M)
        self.assertIsNotNone(line, "Makefile lost CONVERSION_WARNINGS")
        for flag in CONVERSION_FLAGS:
            self.assertIn(flag, line.group(1))
        self.assertIsNotNone(
            re.search(r"^WARNFLAGS\?=.*\$\(CONVERSION_WARNINGS\)", text, re.M),
            "the default WARNFLAGS must carry $(CONVERSION_WARNINGS)")

    def test_cmake_carries_them_and_ci_makes_them_errors(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        self.assertNotIn("-Wno-sign-compare", cmake)
        self.assertIn("${TOC_CONVERSION_WARNINGS}", cmake)
        for flag in CONVERSION_FLAGS:
            self.assertIn(flag, cmake)
            self.assertIn("-Werror=" + flag[2:], cmake)
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
        self.assertGreaterEqual(workflow.count("-DTOC_STRICT_CONVERSION=ON"), 2,
                                "the CMake and sanitizer builds must both set it")
        self.assertIn('TOC_STRICT_CONVERSION: "1"', workflow)
        validate = (ROOT / "scripts" / "validate.sh").read_text()
        self.assertIn("TOC_STRICT_CONVERSION", validate)
        for flag in CONVERSION_FLAGS:
            self.assertIn("-Werror=" + flag[2:], validate)


class WideCharacterFieldTests(unittest.TestCase):
    """The sums the sweep widened stay int: each adds int modifiers."""

    def test_sums_of_modifiers_are_int(self) -> None:
        header = (SRC / "merc.h").read_text(encoding="latin-1")
        start = re.search(r"^struct\s+char_data\s*$", header, re.M).start()
        body = header[start:header.index("};", start)]
        for field in ("wait", "carry_weight", "carry_number", "saving_throw",
                      "hitroll", "damroll", r"armor\[4\]", r"mod_stat\[MAX_STATS\]"):
            self.assertRegex(body, r"\n\s*int\s+%s;" % field,
                             "CHAR_DATA.%s must stay int" % field.split("\\")[0])

    def test_growing_counts_and_bonus_sums_are_int(self) -> None:
        """The 16-bit leftovers widened on 2026-11-12: counts that grow for
        as long as the game runs, and a sum of APPLY_EXP modifiers."""
        header = (SRC / "merc.h").read_text(encoding="latin-1")

        def struct(name: str) -> str:
            start = re.search(r"^struct\s+%s\s*$" % name, header, re.M).start()
            return header[start:header.index("};", start)]

        wanted = {"kill_data": ("killed",),
                  "mob_index_data": ("count", "killed"),
                  "obj_index_data": ("count",),
                  "char_data": ("timer",),
                  "pc_data": ("exp_bonus",)}
        for name, fields in wanted.items():
            body = struct(name)
            for field in fields:
                self.assertRegex(body, r"\n\s*int\s+%s;" % field,
                                 "%s.%s must stay int" % (name, field))
        handler = (SRC / "handler.c").read_text(encoding="latin-1")
        self.assertNotIn("exp_bonus += (sh_int)", handler)

    def test_sh_int_clamp_saturates(self) -> None:
        header = (SRC / "merc.h").read_text(encoding="latin-1")
        self.assertIn("static inline sh_int sh_int_clamp( long long value )", header)


if __name__ == "__main__":
    unittest.main()
