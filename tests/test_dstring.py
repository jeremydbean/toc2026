"""The growable string that long listings are built in.

Growable output buffers, 2026-11-12: src/dstring.c's DString gained a limit
(dstring_init_limit, DSTRING_OUTPUT_MAX), whole-or-nothing appends that say
when they were refused (`truncated`), dstring_fits and dstring_printf.
tests/test_dstring.c checks them under AddressSanitizer and UBSan where the
compiler has them: growth past any fixed array, formatted appends longer
than the first allocation, the limit refusing a line whole and allowing one
that ends exactly on it, no wrap in the size arithmetic, and a full stash
inside DSTRING_OUTPUT_MAX.

The source checks hold the listings that were converted to it: none of them
may go back to a fixed array.
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


def build(binary: Path, sanitize: bool) -> subprocess.CompletedProcess:
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g"] if sanitize else []
    return subprocess.run(
        [CC, "-std=c17", "-Wall", "-Wextra", "-Wconversion", "-Wsign-conversion",
         "-Werror", *flags, "-I", str(SRC), "-o", str(binary),
         str(ROOT / "tests" / "test_dstring.c"), str(SRC / "dstring.c")],
        capture_output=True, text=True)


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class DStringHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_dstring"
            made = build(binary, sanitize=True)
            if made.returncode != 0:
                # No sanitizer runtime here: the checks still run plain.
                made = build(binary, sanitize=False)
            self.assertEqual(made.returncode, 0, made.stderr)
            env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=120, env=env)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stdout.strip(), "ok", run.stdout + run.stderr)


# Each converted listing: the file, the function, and what it must not
# hold again -- the fixed array it was built in.
CONVERTED = {
    ("act_obj.c", "static void stash_show( CHAR_DATA *ch )"): "char out[",
    ("act_comm.c", "static void note_list_filtered("): "char out[",
    ("act_comm.c", "static void history_print("): "char out[",
    ("act_info.c", "void do_who( CHAR_DATA *ch, char *argument )"): "char output[",
    ("abilities.c", "static void show_abilities( CHAR_DATA *ch )"): "static char out[",
    ("abilities.c", "static void build_preview("): "static char out[",
    ("changes.c", "void do_changes( CHAR_DATA *ch, char *argument )"): "static char buf[",
    ("diary.c", "static void diary_show_list("): "calloc(",
    ("heroes.c", "bool show_hero_plaque( CHAR_DATA *ch )"): "roll_out[",
    ("heroes.c", "bool show_remort_tablet( CHAR_DATA *ch )"): "roll_out[",
}


def function_body(path: Path, header: str) -> str:
    text = path.read_text(encoding="latin-1")
    start = text.index(header)
    return text[start:text.index("\n}\n", start)]


class ConvertedListingTests(unittest.TestCase):
    def test_listings_are_built_in_a_bounded_dstring(self) -> None:
        for (name, header), fixed in CONVERTED.items():
            with self.subTest(listing=header):
                body = function_body(SRC / name, header)
                self.assertNotIn(fixed, body)
                self.assertIn("dstring_init_limit(", body)
                self.assertIn("DSTRING_OUTPUT_MAX", body)
                self.assertGreaterEqual(body.count("dstring_free("),
                                        body.count("dstring_init_limit("),
                                        "every DString built is freed")

    def test_reports_page_is_a_dstring(self) -> None:
        body = function_body(SRC / "act_comm.c", "void do_reports( CHAR_DATA *ch, char *argument )")
        self.assertNotIn("char output[", body)
        self.assertIn("DString output;", body)

    def test_the_pager_still_takes_any_size(self) -> None:
        """page_to_char sends text past its pager block unpaged, and
        write_to_buffer in pieces: what a bounded DString hands them."""
        comm = (SRC / "comm.c").read_text(encoding="latin-1")
        pager = function_body(SRC / "comm.c", "void page_to_char( const char *txt, CHAR_DATA *ch )")
        self.assertRegex(pager, r"strlen\( page_text \) \+ 1u >= 32000u")
        self.assertIn("write_to_buffer( ch->desc, page_text, 0 );", pager)
        self.assertIn("void write_to_buffer( DESCRIPTOR_DATA *d, const char *txt, int length )", comm)
        header = (SRC / "dstring.h").read_text(encoding="latin-1")
        limit = re.search(r"#define DSTRING_OUTPUT_MAX\s+\(\s*(\d+)\s*\*\s*(\d+)\s*\)", header)
        self.assertIsNotNone(limit)
        self.assertLessEqual(int(limit.group(1)) * int(limit.group(2)), 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
