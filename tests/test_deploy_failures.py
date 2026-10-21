"""toc-deploy's failure paths, with every host command stubbed.

Two faults from the review of 2026-10-21:

- `../merc --check-area 2>&1 | tail -1` took tail's status under /bin/sh
  (no pipefail), so a world that would not load was installed anyway.
- set -e ended the script at a failed rsync or chown after the game had
  been stopped, before the rollback, leaving it down on a half-copied
  tree. A trap now rolls back from anywhere between the stop and the
  start, and the exit status says how far it got (10: rolled back and
  healthy), which toc-auto-deploy reports instead of "rolled back" for
  every failure.

And one from the cross-report review the same day: a `systemctl stop`
that failed part way ended the script under set -e with whatever it had
stopped left down, reported as "failed before the game was touched". A
failed stop, like an archive that cannot be made, now starts both
services again on the code they were running -- there is no archive to
roll back from -- and exits 13 if that is healthy, 14 if not.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-deploy"

STUBS = {
    # Record every call; succeed unless told otherwise.
    "systemctl": ('echo "systemctl $*" >> "$STUB_LOG"; case "$1" in'
                  ' is-active) echo active;;'
                  ' stop) exit "${STUB_STOP_STATUS:-0}";;'
                  ' start) exit "${STUB_START_STATUS:-0}";; esac; exit 0'),
    "git": 'echo "git $*" >> "$STUB_LOG"; case "$*" in *rev-parse*) echo abc1234;; esac; exit 0',
    "make": 'echo "make $*" >> "$STUB_LOG"; exit 0',
    "flock": "exit 0",
    "sleep": "exit 0",
    "tar": 'echo "tar $*" >> "$STUB_LOG"; exit "${STUB_TAR_STATUS:-0}"',
    "chown": "exit 0",
    "rsync": 'echo "rsync" >> "$STUB_LOG"; exit "${STUB_RSYNC_STATUS:-0}"',
    "curl": '[ "${STUB_HEALTHY:-1}" = 1 ] || exit 22; echo \'{"merc":true}\'; exit 0',
    "install": "exit 0",
}


@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class DeployFailureTests(unittest.TestCase):
    def deploy(self, check_status: int, rsync_status: int = 0,
               tar_status: int = 0, stop_status: int = 0, start_status: int = 0,
               healthy: bool = True) -> tuple[int, str, str]:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        bin_dir, build, current = tmp / "bin", tmp / "build", tmp / "current"
        for d in (bin_dir, build / "area", current / "area", current / "log",
                  current / "player"):
            d.mkdir(parents=True)
        for name, body in STUBS.items():
            path = bin_dir / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        merc = build / "merc"
        merc.write_text("#!/bin/sh\necho 'world check'\nexit %d\n" % check_status)
        merc.chmod(merc.stat().st_mode | stat.S_IEXEC)
        log = tmp / "calls.log"
        log.write_text("")
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                   BUILD=str(build), CURRENT=str(current), STUB_LOG=str(log),
                   STUB_RSYNC_STATUS=str(rsync_status), TOC_DEPLOY_LOCKED="1",
                   STUB_TAR_STATUS=str(tar_status), TOC_ROLLBACK_DIR=str(tmp),
                   TOC_DEPLOY_ROLLBACK="1", STUB_STOP_STATUS=str(stop_status),
                   STUB_START_STATUS=str(start_status), STUB_HEALTHY="1" if healthy else "0")
        result = subprocess.run(["sh", str(DEPLOY)], env=env, capture_output=True,
                                text=True, timeout=60)
        return result.returncode, result.stdout + result.stderr, log.read_text()

    def test_a_world_that_does_not_load_stops_before_the_game_does(self) -> None:
        status, output, calls = self.deploy(check_status=42)
        self.assertEqual(status, 1, output)
        self.assertIn("WORLD CHECK FAILED", output)
        self.assertNotIn("systemctl stop", calls)

    def test_a_failed_copy_after_the_stop_rolls_back(self) -> None:
        status, output, calls = self.deploy(check_status=0, rsync_status=23)
        self.assertEqual(status, 10, output)
        self.assertIn("INSTALL FAILED (status 23)", output)
        stop = calls.index("systemctl stop")
        self.assertIn("systemctl start toc-game", calls[stop:], calls)

    def test_no_way_back_means_nothing_is_installed(self) -> None:
        status, output, calls = self.deploy(check_status=0, tar_status=2)
        self.assertEqual(status, 13, output)
        self.assertIn("COULD NOT ARCHIVE THE RUNNING CODE", output)
        self.assertNotIn("rsync", calls)
        self.assertIn("systemctl start toc-game", calls)
        self.assertIn("systemctl start toc-web", calls)

    def test_no_way_back_and_no_restart_says_so(self) -> None:
        status, output, calls = self.deploy(check_status=0, tar_status=2,
                                            start_status=1, healthy=False)
        self.assertEqual(status, 14, output)
        self.assertIn("NOT HEALTHY AGAIN", output)
        self.assertNotIn("rsync", calls)
        self.assertNotIn("tar xzf", calls, "there is no archive to roll back from")

    def test_a_stop_that_fails_part_way_restarts_both(self) -> None:
        status, output, calls = self.deploy(check_status=0, stop_status=1)
        self.assertEqual(status, 13, output)
        self.assertIn("COULD NOT STOP THE GAME CLEANLY", output)
        self.assertNotIn("tar czf", calls, "nothing is archived")
        self.assertNotIn("rsync", calls, "nothing is installed")
        self.assertNotIn("tar xzf", calls, "there is no archive to roll back from")
        stop = calls.index("systemctl stop")
        self.assertIn("systemctl start toc-game", calls[stop:], calls)
        self.assertIn("systemctl start toc-web", calls[stop:], calls)

    def test_a_failed_stop_and_a_failed_restart_say_so(self) -> None:
        status, output, calls = self.deploy(check_status=0, stop_status=1,
                                            start_status=1, healthy=False)
        self.assertEqual(status, 14, output)
        self.assertIn("NOT HEALTHY AGAIN", output)
        self.assertNotIn("rsync", calls)
        self.assertNotIn("tar xzf", calls)

    def test_the_auto_deployer_reports_what_happened(self) -> None:
        auto = (ROOT / "deploy" / "windows-vm" / "toc-auto-deploy").read_text()
        for code, words in (("10", "FAILED and was rolled back"),
                            ("11", "rolled back but the game is NOT healthy"),
                            ("12", "not rolled back"),
                            ("13", "restarted on its old code and is healthy"),
                            ("14", "restarted on its old code and is NOT healthy"),
                            ("*", "FAILED before the game was touched")):
            self.assertRegex(auto, r'%s\)\s+how="[^"]*%s' % (re.escape(code), re.escape(words)))


if __name__ == "__main__":
    unittest.main()
