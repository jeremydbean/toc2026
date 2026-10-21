"""validate.sh's whitespace check sees what was committed.

Audit 2026-10-21: CI ran a bare `git diff --check`, which compares the
working tree to the index -- always clean in a fresh checkout -- so a
pushed commit with trailing whitespace passed. whitespace_check() checks
the committed range from TOC_WHITESPACE_BASE (the workflow passes the
push's "before"), and still ignores log/, which the game writes.

The function under test is cut from scripts/validate.sh.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def function_source() -> str:
    script = (ROOT / "scripts" / "validate.sh").read_text()
    start = script.index("whitespace_check() {")
    return script[start:script.index("\n}\n", start) + 3]


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "needs git and bash")
class WhitespaceGateTests(unittest.TestCase):
    def repo(self) -> pathlib.Path:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=tmp, check=True)
        (tmp / "code.c").write_text("int a;\n")
        self.commit(tmp, "base")
        return tmp

    @staticmethod
    def commit(repo: pathlib.Path, message: str) -> str:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def check(self, repo: pathlib.Path, base: str) -> int:
        env = dict(os.environ, TOC_WHITESPACE_BASE=base)
        return subprocess.run(["bash", "-c", function_source() + "\nwhitespace_check"],
                              cwd=repo, env=env, capture_output=True).returncode

    def test_committed_whitespace_fails(self) -> None:
        repo = self.repo()
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.strip()
        (repo / "code.c").write_text("int a;\nint b;   \n")
        self.commit(repo, "trailing")
        self.assertNotEqual(self.check(repo, base), 0)
        self.assertEqual(self.check(repo, ""), 0, "no base: the committed range is unknown")

    def test_runtime_logs_are_not_source(self) -> None:
        repo = self.repo()
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.strip()
        (repo / "log").mkdir()
        (repo / "log" / "toc.log").write_text("ROM is ready to rock on port 9000. \n")
        self.commit(repo, "a log line ends in a space")
        self.assertEqual(self.check(repo, base), 0)

    def test_staged_whitespace_fails_locally(self) -> None:
        repo = self.repo()
        (repo / "code.c").write_text("int a;  \n")
        subprocess.run(["git", "add", "code.c"], cwd=repo, check=True)
        self.assertNotEqual(self.check(repo, ""), 0)


if __name__ == "__main__":
    unittest.main()
