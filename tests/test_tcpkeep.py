"""TCP keepalive on every connection, on Linux and macOS (review,
2026-11-12).

new_descriptor meant to probe an idle connection after 120 seconds, but it
set only TCP_KEEPIDLE, which macOS does not define -- its name for the same
option is TCP_KEEPALIVE -- so on macOS the idle time was never set, both
builds warned that idle_secs was unused, and no setsockopt result was
looked at. src/tcpkeep.c chooses the platform's option and reports what
failed; comm.c logs it once.

Two checks: tests/test_tcpkeep.c sets the options on a real loopback
connection and reads each one back (this platform's); and tcpkeep.c built
as macOS sees it -- no TCP_KEEPIDLE, a TCP_KEEPALIVE -- still sets an idle
time and builds clean under -Werror, so the macOS branch is compiled and
checked on any host.
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
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wunused", "-Werror"]

# What macOS's headers give: TCP_KEEPALIVE (0x10 there), no TCP_KEEPIDLE.
MACOS_SHIM = """
#include <netinet/tcp.h>
#undef TCP_KEEPIDLE
#ifndef TCP_KEEPALIVE
#define TCP_KEEPALIVE 0x10
#endif
"""
MACOS_MAIN = """
#include <stdio.h>
#include <string.h>
#include "tcpkeep.h"
int main(void)
{
    const char *idle = tcp_keepalive_idle_option();
    puts(idle ? idle : "none");
    return idle != NULL && strcmp(idle, "TCP_KEEPALIVE") == 0 ? 0 : 1;
}
"""


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class TcpKeepaliveTests(unittest.TestCase):
    def test_the_options_read_back_on_this_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_tcpkeep"
            build = subprocess.run(
                [CC, *FLAGS, "-I", str(ROOT / "src"), "-o", str(binary),
                 str(ROOT / "tests" / "test_tcpkeep.c"), str(ROOT / "src" / "tcpkeep.c")],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_macos_headers_take_the_tcp_keepalive_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "macos_tcp.h"
            shim.write_text(MACOS_SHIM)
            main = Path(tmp) / "main.c"
            main.write_text(MACOS_MAIN)
            binary = Path(tmp) / "macos_idle"
            build = subprocess.run(
                [CC, *FLAGS, "-D_DEFAULT_SOURCE", "-include", str(shim),
                 "-I", str(ROOT / "src"), "-o", str(binary), str(main),
                 str(ROOT / "src" / "tcpkeep.c")],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(run.stdout.strip(), "TCP_KEEPALIVE")

    def test_comm_uses_it_and_checks_the_result(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertIn("tcp_keepalive_set( desc, 120, 30, 4, &missing )", comm)
        self.assertNotIn("TCP_KEEPIDLE", comm, "the platform choice is tcpkeep.c's")
        self.assertIn("src/tcpkeep.c", (ROOT / "CMakeLists.txt").read_text())


if __name__ == "__main__":
    unittest.main()
