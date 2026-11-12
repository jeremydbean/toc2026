"""Memory classification without undefined pointer comparisons or reads.

Two findings of the 2026-11-12 review of the allocator and the memory
guard, each held by a C harness built from the real source:

* **Permanent memory was recognised with undefined comparisons.**
  is_perm_memory and perm_block_note in src/db.c ordered a pointer --
  usually an ordinary heap allocation -- against alloc_perm's block bounds
  with < and >=, and free_string, str_dup and str_perm did the same against
  the boot string space. C defines relational comparison only within one
  object; ASan's pointer-compare check
  (-fsanitize=address,pointer-compare, ASAN_OPTIONS
  detect_invalid_pointer_pairs=2) stopped the old code with
  "invalid-pointer-pair" on the first block noted out of order. The range
  logic is src/memrange.c now, on uintptr_t, and tests/test_memrange.c
  plays it under that check.

* **The liveness checks read freed memory.** char_is_live, obj_is_live and
  desc_is_live read the block's mem_magic tag, which is a use after free
  once recycle_flush has freed it -- after the quarantine window, or at
  once when MEM_QUARANTINE_MAX more blocks are released behind it. They ask
  src/memtrack.c's address set now. tests/test_memtrack.c checks the set
  against a brute-force reference; tests/test_recycle_liveness.c links the
  real src/recycle.c and plays a zero window, a 60 s window, cap saturation
  and stack stand-ins under ASan (the old recycle.c failed the cap and zero
  cases with heap-use-after-free in char_is_live).

* **An address reused by the same kind read live** (2026-11-12). The set
  gives every registration a serial, a long-lived pointer keeps the one it
  was set with (MEM_REF, SET_CHAR_REF), and mem_ref_liveness says
  MEM_STATE_REUSED when they differ: "ok serials" in test_memtrack.c and
  the "reuse" mode of test_recycle_liveness.c, which the old sources do
  not build. Stand-ins are registered while in use ("ok standins",
  "standin").
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
CC = os.environ.get("CC", "cc").split()[-1]


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"no end to {signature}")


def can_build(flags: list[str]) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.c"
        probe.write_text("int main(void) { return 0; }\n")
        out = subprocess.run([CC, *flags, "-o", str(Path(tmp) / "probe"), str(probe)],
                             capture_output=True, text=True)
        return out.returncode == 0


ASAN_COMPARE = ["-fsanitize=address,pointer-compare"]
ASAN = ["-fsanitize=address,undefined"]


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class MemoryHarnessTests(unittest.TestCase):
    def build_and_run(self, name: str, sources: list[Path], flags: list[str],
                      env: dict[str, str], args: list[list[str]],
                      extra: list[str] | None = None) -> list[str]:
        outputs = []
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / name
            build = subprocess.run(
                [CC, "-std=c17", "-g", "-Wall", "-Wextra", "-Wno-unused-parameter",
                 "-Werror", *flags, *(extra or []), "-I", str(SRC),
                 "-o", str(binary), *map(str, sources)],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            for argv in args:
                run = subprocess.run([str(binary), *argv], capture_output=True, text=True,
                                     timeout=120, env={**os.environ, **env})
                report = run.stdout + run.stderr
                self.assertNotIn("AddressSanitizer", report, report)
                self.assertNotIn("runtime error", report, report)
                self.assertEqual(run.returncode, 0, report)
                self.assertNotIn("FAIL", run.stdout, run.stdout)
                outputs.append(run.stdout)
        return outputs

    def sanitizer(self, flags: list[str]) -> list[str]:
        if not can_build(flags):
            self.skipTest(f"{CC} cannot build with {' '.join(flags)}")
        return flags

    def test_perm_classifier_has_no_invalid_pointer_pairs(self) -> None:
        flags = self.sanitizer(ASAN_COMPARE)
        out = self.build_and_run(
            "test_memrange", [TESTS / "test_memrange.c", SRC / "memrange.c"], flags,
            {"ASAN_OPTIONS": "detect_invalid_pointer_pairs=2:halt_on_error=1:detect_leaks=0"},
            [[]])
        for step in ("ok sorted", "ok interior", "ok heap", "ok space"):
            self.assertIn(step, out[0])
        self.assertIn(", 0 failures", out[0])

    def test_address_set_matches_a_reference(self) -> None:
        flags = self.sanitizer(ASAN)
        out = self.build_and_run(
            "test_memtrack", [TESTS / "test_memtrack.c", SRC / "memtrack.c"], flags,
            {"ASAN_OPTIONS": "halt_on_error=1:detect_leaks=0"}, [[]])
        for step in ("ok basics", "ok serials", "ok standins", "ok churn", "ok forget"):
            self.assertIn(step, out[0])

    def test_recycle_liveness_never_reads_a_freed_block(self) -> None:
        flags = self.sanitizer(ASAN)
        out = self.build_and_run(
            "test_recycle_liveness",
            [TESTS / "test_recycle_liveness.c", SRC / "recycle.c", SRC / "memtrack.c"],
            flags, {"ASAN_OPTIONS": "halt_on_error=1:detect_leaks=0"},
            [["zero"], ["window"], ["cap"], ["standin"], ["reuse"]],
            extra=["-DROM", "-Dunix", "-DNOCRYPT"])
        for mode, text in zip(("zero", "window", "cap", "standin", "reuse"), out):
            self.assertRegex(text, rf"(?m)^{mode}: \d+ checks, 0 failures", text)

    def test_real_address_reuse_is_caught_by_serial(self) -> None:
        """Without ASan (whose quarantine never hands a freed block back),
        glibc gives freed characters' addresses to new ones within a few
        allocations; every one the reuse mode finds must read live by
        address and reused by its serial."""
        out = self.build_and_run(
            "test_recycle_reuse",
            [TESTS / "test_recycle_liveness.c", SRC / "recycle.c", SRC / "memtrack.c"],
            ["-O2"], {}, [["reuse"]], extra=["-DROM", "-Dunix", "-DNOCRYPT"])
        self.assertRegex(out[0], r"(?m)^reuse: \d+ checks, 0 failures", out[0])
        if sys.platform.startswith("linux"):
            self.assertRegex(out[0], r"real allocator reuse seen \([1-9]\d*\)", out[0])


class MemoryRangeSourceTests(unittest.TestCase):
    def test_no_relational_comparison_against_permanent_memory(self) -> None:
        db = strip_comments((SRC / "db.c").read_text(encoding="latin-1"))
        # A pointer ordered against the string space or a perm block's
        # bounds: what the review found in free_string, str_dup, str_perm
        # and is_perm_memory.
        bad = re.findall(
            r"\w+\s*(?:<|<=|>|>=)\s*(?:string_space|top_string|perm_blocks)\b"
            r"|\b(?:string_space|top_string|perm_blocks)\b(?:\[[^\]]*\])?\s*(?:<|<=|>|>=)\s*\w+"
            r"|top_string\s*\+\s*len\s*>",
            db)
        self.assertEqual(bad, [])
        self.assertIn("mem_block_set_has( &perm_blocks, pMem )",
                      function_body(db, "bool is_perm_memory( const void *pMem )"))
        self.assertIn("mem_block_set_add( &perm_blocks, block )",
                      function_body(db, "static void perm_block_note( char *block )"))
        for sig in ("void free_string( char *pstr )", "char *str_dup( const char *str )",
                    "char *str_perm( const char *str )"):
            self.assertIn("in_string_space(", function_body(db, sig), sig)
        self.assertIn("mem_addr_in( str, string_space",
                      function_body(db, "static bool in_string_space( const char *str )"))

    def test_the_pure_files_stay_pure_and_are_built(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        for name in ("memrange", "memtrack"):
            text = (SRC / f"{name}.c").read_text(encoding="latin-1")
            self.assertNotIn('"merc.h"', text, name)
            self.assertIn(f"src/{name}.c", cmake)
        memrange = strip_comments((SRC / "memrange.c").read_text(encoding="latin-1"))
        # Only integers are ordered in memrange.c.
        self.assertNotRegex(memrange, r"\b(?:p|block|base)\s*(?:<|>|<=|>=)\s*\w")


if __name__ == "__main__":
    unittest.main()
