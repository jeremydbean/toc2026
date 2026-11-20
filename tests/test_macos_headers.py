"""The game's sources against macOS's feature-macro rules (review,
2026-11-20: both macOS builds failed).

Darwin's headers hide what they call BSD and Darwin extras when a file
defines _POSIX_C_SOURCE or _XOPEN_SOURCE without _DARWIN_C_SOURCE:
<sys/socket.h> drops MSG_DONTWAIT, and <sys/file.h> drops flock() and
LOCK_SH/LOCK_EX/LOCK_NB/LOCK_UN. glibc shows them under _DEFAULT_SOURCE, so
a Linux build never noticed: comm.c's hang-up peek asked for MSG_DONTWAIT
and update.c's backup lock is an flock.

This compiles every src/*.c that defines _POSIX_C_SOURCE or _XOPEN_SOURCE
(the files Darwin would restrict) with __APPLE__ defined and stand-in
<sys/socket.h> and <sys/file.h> that hide exactly those names under
Darwin's condition, as the C17 build does (-fsyntax-only, -Werror for
implicit declarations). A use that would not build on macOS fails here,
on any host.
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

HIDDEN = ("(defined(_POSIX_C_SOURCE) || defined(_XOPEN_SOURCE)) "
          "&& !defined(_DARWIN_C_SOURCE)")

# glibc's MSG_DONTWAIT is an enum constant as well as a macro, so the
# constant is renamed while the real header is read, and the name is given
# back only where Darwin would show it.
SOCKET_SHIM = """
#ifndef TOC_DARWIN_SOCKET_SHIM
#define TOC_DARWIN_SOCKET_SHIM
#define MSG_DONTWAIT glibc_MSG_DONTWAIT
#include_next <sys/socket.h>
#undef MSG_DONTWAIT
#if !(%s)
#define MSG_DONTWAIT glibc_MSG_DONTWAIT
#endif
#endif
""" % HIDDEN

FILE_SHIM = """
#include_next <sys/file.h>
#if %s
#undef LOCK_SH
#undef LOCK_EX
#undef LOCK_NB
#undef LOCK_UN
#define flock(fd, op) darwin_hides_flock_without__DARWIN_C_SOURCE
#endif
""" % HIDDEN


def restricted_sources() -> list[Path]:
    files = []
    for path in sorted((ROOT / "src").glob("*.c")):
        text = path.read_text(encoding="latin-1")
        if re.search(r"^#\s*define\s+_(POSIX_C|XOPEN)_SOURCE\b", text, re.M):
            files.append(path)
    return files


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class MacosHeaderTests(unittest.TestCase):
    def compile(self, inc: Path, source: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [CC, "-std=c17", "-fsyntax-only", "-DROM", "-Dunix", "-D__APPLE__",
             "-Werror=implicit-function-declaration", "-Wno-builtin-macro-redefined",
             "-I", str(inc), "-I", str(ROOT / "src"), str(source)],
            capture_output=True, text=True, timeout=180, cwd=ROOT)

    def test_the_shims_hide_what_darwin_hides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inc = Path(tmp)
            (inc / "sys").mkdir()
            (inc / "sys" / "socket.h").write_text(SOCKET_SHIM)
            (inc / "sys" / "file.h").write_text(FILE_SHIM)
            probe = inc / "probe.c"
            probe.write_text("#define _POSIX_C_SOURCE 200809L\n"
                             "#include <sys/socket.h>\n#include <sys/file.h>\n"
                             "int a = MSG_DONTWAIT;\n"
                             "int b(int fd) { return flock(fd, LOCK_EX); }\n")
            said = self.compile(inc, probe)
            self.assertNotEqual(said.returncode, 0, "the shims hid nothing")
            self.assertIn("MSG_DONTWAIT", said.stderr)
            self.assertIn("LOCK_EX", said.stderr)
            probe.write_text("#define _POSIX_C_SOURCE 200809L\n#define _DARWIN_C_SOURCE\n"
                             "#include <sys/socket.h>\n#include <sys/file.h>\n"
                             "int a = MSG_DONTWAIT;\n"
                             "int b(int fd) { return flock(fd, LOCK_EX); }\n")
            said = self.compile(inc, probe)
            self.assertEqual(said.returncode, 0, said.stderr)

    def test_every_restricted_file_builds_as_macos_sees_it(self) -> None:
        sources = restricted_sources()
        names = {path.name for path in sources}
        self.assertTrue({"comm.c", "update.c"} <= names, names)
        with tempfile.TemporaryDirectory() as tmp:
            inc = Path(tmp)
            (inc / "sys").mkdir()
            (inc / "sys" / "socket.h").write_text(SOCKET_SHIM)
            (inc / "sys" / "file.h").write_text(FILE_SHIM)
            failed = {}
            for source in sources:
                said = self.compile(inc, source)
                if said.returncode != 0:
                    failed[source.name] = said.stderr[-1500:]
            self.assertEqual(failed, {}, "\n".join(
                "%s:\n%s" % item for item in failed.items()))


if __name__ == "__main__":
    unittest.main()
