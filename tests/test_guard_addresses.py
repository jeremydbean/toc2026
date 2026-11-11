"""Client addresses and the guard's record of players' addresses (review, 2026-11-06).

tests/test_guard_addresses.c checks src/netaddr.c and src/guardstore.c
alone, against a synthetic clock and a disk that fails:

- an address is parsed whole, by family and bytes: a numeric prefix is no
  address, expanded and compressed IPv6 are one address, an IPv4-mapped
  peer is its IPv4 address, and an IPv6 /64 is one guard key;
- a player who logs in twice a day for a hundred days is still trusted
  after a restart: the write is due a day after the last line that landed,
  never a day after the last login (which postponed it for ever);
- a write that fails (a full disk, no directory) records nothing and is
  tried again at the next chance;
- the start from older journals takes only a login record that names its
  own numeric address -- never a host name, never a connection line joined
  to a later login by nearness;
- (review of f1388da0) a file that is there and cannot be read is never
  taken for absent or written over; a record counts only whole -- a
  timestamp that overflows, runs on, is negative or lies beyond the clock
  skew is refused -- and an unfinished last record is ended before the
  next append, so the two never read as one far-future record; a rewrite
  or append whose first flush failed fails even when the next flush
  works, and the good file stays.
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
class GuardAddressHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_guard_addresses"
            build = subprocess.run(
                [CC, "-std=c17", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-DGUARD_STORE_FFLUSH=test_fflush",
                 "-o", str(binary), str(ROOT / "tests" / "test_guard_addresses.c"),
                 str(ROOT / "src" / "netaddr.c"), str(ROOT / "src" / "guardstore.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary), tmp], capture_output=True, text=True, timeout=60)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_the_modules_stay_free_of_game_state(self) -> None:
        for name in ("netaddr.c", "guardstore.c", "netaddr.h", "guardstore.h"):
            self.assertNotIn('#include "merc.h"', (ROOT / "src" / name).read_text(encoding="latin-1"), name)
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("src/netaddr.c", cmake)
        self.assertIn("src/guardstore.c", cmake)


if __name__ == "__main__":
    unittest.main()
