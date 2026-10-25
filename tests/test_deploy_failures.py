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

And from the CI and deploy redesign (2026-10-25): the way back is a
snapshot of the live code taken before the game is stopped, with the
install's own excludes, so a rollback puts the code back and never
rewinds a player, corpse, note or builder's area (the tar archive it
replaced held all of area/). A snapshot that cannot be made stops the
deploy with the game still running. Healthy needs the game itself to
answer MSSP with a count, not only the dashboard's TCP connect, which
passed while the world was still loading.
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
    "tar": 'echo "tar $*" >> "$STUB_LOG"; exit 0',
    "chown": "exit 0",
    # Which copy it is, by its arguments: the install reads the build
    # tree, the snapshot writes a rollback directory, the restore reads
    # one into the live tree.
    "rsync": ('case "$*" in'
              ' *" $BUILD/ "*) echo "rsync install" >> "$STUB_LOG";'
              ' exit "${STUB_RSYNC_STATUS:-0}";;'
              ' *rollback-code*" $CURRENT/") echo "rsync restore" >> "$STUB_LOG";'
              ' exit "${STUB_RESTORE_STATUS:-0}";;'
              ' *rollback-code*) echo "rsync snapshot" >> "$STUB_LOG";'
              ' exit "${STUB_SNAPSHOT_STATUS:-0}";;'
              ' esac; echo "rsync other" >> "$STUB_LOG"; exit 0'),
    "curl": '[ "${STUB_HEALTHY:-1}" = 1 ] || exit 22; echo \'{"merc":true}\'; exit 0',
    # What the game answers over MSSP: a count when its loop runs.
    "toc-game-probe": 'echo "${STUB_PROBE-0}"',
    "install": "exit 0",
}


@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class DeployFailureTests(unittest.TestCase):
    def deploy(self, check_status: int, rsync_status: int = 0,
               snapshot_status: int = 0, stop_status: int = 0, start_status: int = 0,
               healthy: bool = True, probe: str = "0",
               args: tuple = ()) -> tuple[int, str, str]:
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
                   STUB_SNAPSHOT_STATUS=str(snapshot_status), TOC_ROLLBACK_DIR=str(tmp),
                   TOC_DEPLOY_ROLLBACK="1", STUB_STOP_STATUS=str(stop_status),
                   STUB_START_STATUS=str(start_status), STUB_HEALTHY="1" if healthy else "0",
                   TOC_GAME_PROBE=str(bin_dir / "toc-game-probe"), STUB_PROBE=probe)
        self.rollback_dir = tmp
        result = subprocess.run(["sh", str(DEPLOY), *args], env=env, capture_output=True,
                                text=True, timeout=60)
        return result.returncode, result.stdout + result.stderr, log.read_text()

    def snapshots(self) -> list:
        return sorted(p.name for p in self.rollback_dir.glob("rollback-code-*"))

    def test_a_world_that_does_not_load_stops_before_the_game_does(self) -> None:
        status, output, calls = self.deploy(check_status=42)
        self.assertEqual(status, 1, output)
        self.assertIn("WORLD CHECK FAILED", output)
        self.assertNotIn("systemctl stop", calls)

    def test_a_failed_copy_after_the_stop_rolls_back(self) -> None:
        status, output, calls = self.deploy(check_status=0, rsync_status=23)
        self.assertEqual(status, 10, output)
        self.assertIn("INSTALL FAILED (status 23)", output)
        self.assertLess(calls.index("rsync snapshot"), calls.index("systemctl stop"),
                        "the way back is made while the game still runs")
        stop = calls.index("systemctl stop")
        self.assertIn("rsync restore", calls[calls.index("rsync install"):], calls)
        self.assertIn("systemctl start toc-game", calls[stop:], calls)
        self.assertNotIn("tar ", calls, "no archive of area/ and its runtime files")

    def test_no_way_back_means_the_game_is_never_stopped(self) -> None:
        status, output, calls = self.deploy(check_status=0, snapshot_status=11)
        self.assertEqual(status, 1, output)
        self.assertIn("COULD NOT SNAPSHOT THE RUNNING CODE", output)
        self.assertNotIn("systemctl", calls, "nothing was stopped, so nothing restarts")
        self.assertNotIn("rsync install", calls)
        self.assertEqual([], self.snapshots(), "a partial snapshot is removed")

    def test_a_restore_that_fails_says_the_game_is_not_healthy(self) -> None:
        status, output, calls = self.deploy(check_status=0, rsync_status=23,
                                            healthy=False)
        self.assertEqual(status, 11, output)
        self.assertIn("NOT HEALTHY AFTER THE ROLLBACK", output)

    def test_a_dashboard_alone_is_not_health(self) -> None:
        """The dashboard says merc:true on a TCP connect, which the game
        accepts before it has loaded the world. A game that does not
        answer MSSP with a count is not healthy, and is rolled back."""
        for probe in ("unknown", "down", ""):
            with self.subTest(probe=probe):
                status, output, calls = self.deploy(check_status=0, probe=probe)
                self.assertEqual(status, 11, output)
                self.assertIn("DID NOT COME BACK HEALTHY", output)
                self.assertIn("rsync restore", calls)

    def test_a_healthy_deploy_keeps_its_snapshot(self) -> None:
        status, output, calls = self.deploy(check_status=0)
        self.assertEqual(status, 0, output)
        self.assertIn("healthy at", output)
        self.assertNotIn("rsync restore", calls)
        self.assertEqual(1, len(self.snapshots()), "kept for --rollback by hand")
        self.assertTrue((self.rollback_dir / self.snapshots()[0] / ".snapshot-ok").exists())

    def test_rollback_by_hand_needs_a_complete_snapshot(self) -> None:
        status, output, calls = self.deploy(check_status=0, args=("--rollback",))
        self.assertEqual(status, 1, output)
        self.assertIn("no complete code snapshot", output)
        self.assertNotIn("systemctl", calls)

    def test_a_stop_that_fails_part_way_restarts_both(self) -> None:
        status, output, calls = self.deploy(check_status=0, stop_status=1)
        self.assertEqual(status, 13, output)
        self.assertIn("COULD NOT STOP THE GAME CLEANLY", output)
        self.assertNotIn("rsync install", calls, "nothing is installed")
        self.assertNotIn("rsync restore", calls, "nothing to roll back")
        stop = calls.index("systemctl stop")
        self.assertIn("systemctl start toc-game", calls[stop:], calls)
        self.assertIn("systemctl start toc-web", calls[stop:], calls)

    def test_a_failed_stop_and_a_failed_restart_say_so(self) -> None:
        status, output, calls = self.deploy(check_status=0, stop_status=1,
                                            start_status=1, healthy=False)
        self.assertEqual(status, 14, output)
        self.assertIn("NOT HEALTHY AGAIN", output)
        self.assertNotIn("rsync install", calls)
        self.assertNotIn("rsync restore", calls)

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
