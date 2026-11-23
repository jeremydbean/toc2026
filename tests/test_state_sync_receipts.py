"""The state sync says honestly how it went, and never pushes a gutted tree
(review, 2026-11-23).

toc-state-sync.service took exit 1 for success and toc-state-sync-check
judged systemd's Result and a recent exit, so a sync failing every run read
healthy; an unpushed count that could not be read was taken for zero; and an
empty or half-mounted player/ would have been mirrored with --delete and
pushed over the last good state. Now:

- every run writes last-attempt (ok / nochange / skipped / failed, why);
- last-success is written only when GitHub shows the run's commit -- a push
  ls-remote then sees, or a no-change run whose tree GitHub already holds;
- the check judges those receipts, and anything it cannot read is a fault;
- a tree that shrank past belief is refused before anything is copied,
  unless a reason in allow-drop says it is meant, which is used once.

Each case runs the real scripts against a local bare repository standing in
for GitHub, with synthetic Z characters only. Nothing touches a real host
path.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "deploy" / "windows-vm" / "toc-state-sync"
CHECK = ROOT / "deploy" / "windows-vm" / "toc-state-sync-check"
UNITS = ROOT / "deploy" / "windows-vm"
REAL_GIT = shutil.which("git")


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run([REAL_GIT or "git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def receipt(path: Path) -> dict:
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


@unittest.skipIf(REAL_GIT is None or shutil.which("flock") is None
                 or shutil.which("rsync") is None, "needs git, flock and rsync")
class StateSyncReceiptTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self._tmp.name)
        self.bare, seed = root / "remote.git", root / "seed"
        git("init", "-q", "--bare", "-b", "main", str(self.bare))
        git("clone", "-q", str(self.bare), str(seed))
        (seed / "README").write_text("seed\n")
        git("add", "README", cwd=seed)
        git("commit", "-qm", "seed", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)
        self.live = root / "live"
        (self.live / "player").mkdir(parents=True)
        (self.live / "log").mkdir()
        for n in range(12):
            self.player(f"Zfix{chr(97 + n)}", n)
        self.state = root / "sync-state"
        self.state.mkdir()
        key = root / "key"
        key.write_text("not a key\n")
        self.stubs = root / "bin"
        self.stubs.mkdir()
        self.env = dict(os.environ, TOC_ROOT=str(self.live), STATE_REPO=str(root / "state"),
                        REMOTE=f"file://{self.bare}", BRANCH="main", GIT_SSH_KEY=str(key),
                        LOCK_FILE=str(root / "sync.lock"), TOC_DEPLOY_LOCK=str(root / "d.lock"),
                        TOC_HOST_ACTION_RESULTS=str(root / "results"),
                        TOC_SYNC_STATE_DIR=str(self.state),
                        PATH=f"{self.stubs}:{os.environ['PATH']}")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def hold(argv: list[str]) -> subprocess.Popen:
        # In a group of its own: the sleep flock starts holds the lock too.
        return subprocess.Popen(argv, start_new_session=True)

    @staticmethod
    def release(holder: subprocess.Popen) -> None:
        os.killpg(holder.pid, 9)
        holder.wait()

    def player(self, name: str, n: int = 0) -> None:
        (self.live / "player" / name).write_text(f"#PLAYER\nName {name}~\n{'#' * (n + 1)}\nEnd\n")

    def sync(self) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", str(SYNC)], env=self.env, capture_output=True,
                              text=True, timeout=120)

    def check(self, **extra) -> tuple[subprocess.CompletedProcess, str, str]:
        queue = self.root / "webadmin.queue"
        queue.write_text("")
        marker = self.root / "status"
        (self.stubs / "systemctl").write_text("#!/bin/sh\necho inactive\n")
        (self.stubs / "logger").write_text("#!/bin/sh\nexit 0\n")
        for stub in self.stubs.iterdir():
            stub.chmod(0o755)
        env = dict(self.env, QUEUE=str(queue), MARKER=str(marker), DISK_PATH=str(self.root),
                   DISK_MIN_FREE_MB="1", **extra)
        done = subprocess.run(["sh", str(CHECK)], env=env, capture_output=True,
                              text=True, timeout=60)
        return done, marker.read_text() if marker.exists() else "", queue.read_text()

    def remote_main(self) -> str:
        return git("--git-dir", str(self.bare), "rev-parse", "main").strip()

    def remote_files(self) -> list[str]:
        return git("--git-dir", str(self.bare), "ls-tree", "-r", "--name-only", "main").split()

    def success(self) -> dict:
        return receipt(self.state / "last-success")

    def attempt(self) -> dict:
        return receipt(self.state / "last-attempt")

    def age_success(self, minutes: int) -> None:
        got = self.success()
        got["time"] = str(int(time.time()) - minutes * 60)
        (self.state / "last-success").write_text("".join(f"{k}={v}\n" for k, v in got.items()))

    # --- what a run records -------------------------------------------------

    def test_a_push_is_a_success_only_once_github_shows_it(self) -> None:
        done = self.sync()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.attempt()["result"], "ok")
        got = self.success()
        self.assertEqual(got["kind"], "pushed")
        self.assertEqual(got["remote_commit"], self.remote_main())
        self.assertEqual(got["characters"], "12")
        self.assertIn("player/Zfixa", self.remote_files())
        # Each receipt is whole: no temporary left behind.
        self.assertEqual(sorted(p.name for p in self.state.iterdir()),
                         ["last-attempt", "last-success"])

    def test_a_run_with_nothing_to_push_is_a_verified_success(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        first = self.success()
        time.sleep(1.1)
        done = self.sync()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.attempt()["result"], "nochange")
        got = self.success()
        self.assertEqual(got["kind"], "nochange")
        self.assertEqual(got["remote_commit"], first["remote_commit"])
        self.assertGreater(int(got["time"]), int(first["time"]))

    def test_nothing_changed_but_github_cannot_be_read_is_a_failure(self) -> None:
        """An unreadable upstream: the fetch worked but ls-remote did not, so
        nothing proves GitHub holds the state. Not a success."""
        self.assertEqual(self.sync().returncode, 0)
        before = self.success()
        (self.stubs / "git").write_text(
            "#!/bin/sh\nfor a in \"$@\"; do [ \"$a\" = ls-remote ] && exit 128; done\n"
            f"exec {REAL_GIT} \"$@\"\n")
        (self.stubs / "git").chmod(0o755)
        done = self.sync()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(self.attempt()["result"], "failed")
        self.assertIn("could not be shown to hold", self.attempt()["reason"])
        self.assertEqual(self.success(), before, "last-success untouched")

    def test_a_missing_key_fails_and_keeps_the_last_success(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        before = self.success()
        self.env["GIT_SSH_KEY"] = str(self.root / "gone")
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.attempt()["result"], "failed")
        self.assertIn("no deploy key", self.attempt()["reason"])
        self.assertEqual(self.success(), before)

    def test_a_missing_player_directory_fails_before_any_commit(self) -> None:
        self.env["TOC_ROOT"] = str(self.root / "nowhere")
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertIn("no player dir", self.attempt()["reason"])
        self.assertEqual(self.success(), {})
        self.assertEqual(self.remote_files(), ["README"])

    def test_a_failed_fetch_is_a_failure(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        before = self.success()
        git("remote", "set-url", "origin", str(self.root / "nowhere.git"), cwd=self.root / "state")
        self.env["REMOTE"] = str(self.root / "nowhere.git")
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertIn("could not bring the clone up to date", self.attempt()["reason"])
        self.assertEqual(self.success(), before)

    def test_a_refused_push_is_a_failure_and_the_check_says_so(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        hook = self.bare / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.player("Znew", 40)
        started = time.time()
        done = self.sync()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("push failed after 5 attempts", self.attempt()["reason"])
        self.assertLess(time.time() - started, 100)
        self.assertNotIn("player/Znew", self.remote_files())
        # The last success is still recent: healthy by age, but the clone
        # now holds a commit GitHub does not, which the check names at once.
        said, marker, queue = self.check()
        self.assertEqual(said.returncode, 1, said.stdout)
        self.assertIn("1 commits committed but never pushed", marker)
        self.assertIn("last_attempt=failed", marker)
        self.assertIn("wizinfo|60|Player-state backup to GitHub is not working", queue)

    def test_retries_keep_failing_until_the_cause_goes_then_recover(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        good = self.env["GIT_SSH_KEY"]
        self.env["GIT_SSH_KEY"] = str(self.root / "gone")
        for _ in range(3):
            self.assertEqual(self.sync().returncode, 1)
        self.age_success(30)
        said, marker, _ = self.check()
        self.assertEqual(said.returncode, 1)
        self.assertRegex(marker, r"^FAILING .*last verified sync was 30 minutes ago")
        self.assertIn("no deploy key", marker)
        self.env["GIT_SSH_KEY"] = good
        self.player("Zback", 50)
        self.assertEqual(self.sync().returncode, 0)
        said, marker, _ = self.check()
        self.assertEqual(said.returncode, 0, said.stderr)
        self.assertRegex(marker, r"^ok .*kind=pushed .*last_attempt=ok .*unpushed=0")

    def test_a_held_lock_records_nothing_and_a_deploy_is_a_skip(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        attempt = (self.state / "last-attempt").read_text()
        success = self.success()
        holder = self.hold(["flock", str(self.root / "sync.lock"), "sleep", "30"])
        try:
            time.sleep(0.5)
            done = self.sync()
            self.assertEqual(done.returncode, 0)
            self.assertIn("another sync is running", done.stdout)
            self.assertEqual((self.state / "last-attempt").read_text(), attempt,
                             "the run holding the lock records its own attempt")
        finally:
            self.release(holder)
        (self.root / "d.lock").write_text("")
        holder = self.hold(["flock", "-x", str(self.root / "d.lock"), "sleep", "30"])
        try:
            time.sleep(0.5)
            self.player("Zdeploy", 60)
            done = self.sync()
            self.assertEqual(done.returncode, 0)
            self.assertEqual(self.attempt()["result"], "skipped")
            self.assertIn("a deploy is running", self.attempt()["reason"])
            self.assertEqual(self.success(), success, "a skip is never a success")
        finally:
            self.release(holder)

    # --- the drop guard ---------------------------------------------------

    def test_an_emptied_player_tree_is_refused_and_github_keeps_it(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        before = self.remote_main()
        for path in (self.live / "player").iterdir():
            path.unlink()
        done = self.sync()
        self.assertEqual(done.returncode, 1, done.stdout)
        reason = self.attempt()["reason"]
        self.assertIn("refused", reason)
        self.assertIn("player:12->0", reason)
        self.assertEqual(self.remote_main(), before, "nothing pushed")
        self.assertIn("player/Zfixa", self.remote_files())
        self.assertTrue((self.root / "state" / "player" / "Zfixa").exists(),
                        "nothing deleted from the clone either")
        # The check reports a refusal at once, whatever the age.
        said, marker, queue = self.check()
        self.assertEqual(said.returncode, 1)
        self.assertIn("refused", marker)
        self.assertIn("refused", queue)

    def test_a_missing_player_tree_is_refused(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        (self.live / "gods").mkdir()
        (self.live / "gods" / "Zgod").write_text("x\n")
        self.assertEqual(self.sync().returncode, 0)
        shutil.rmtree(self.live / "gods")
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertIn("gods:1->0", self.attempt()["reason"])
        self.assertIn("gods/Zgod", self.remote_files())

    def test_a_partial_tree_is_refused_but_ordinary_churn_is_not(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        # One character in twelve gone (8%): an ordinary deletion.
        (self.live / "player" / "Zfixa").unlink()
        self.assertEqual(self.sync().returncode, 0, self.attempt())
        self.assertNotIn("player/Zfixa", self.remote_files())
        # Half the rest at once: refused.
        for name in ("Zfixb", "Zfixc", "Zfixd", "Zfixe", "Zfixf", "Zfixg"):
            (self.live / "player" / name).unlink()
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertIn("player:11->5", self.attempt()["reason"])
        self.assertIn("player/Zfixb", self.remote_files())

    def test_an_intended_drop_passes_once_with_its_reason_recorded(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        for name in ("Zfixb", "Zfixc", "Zfixd", "Zfixe", "Zfixf", "Zfixg"):
            (self.live / "player" / name).unlink()
        stale = self.state / "allow-drop"
        stale.write_text("old permission\n")
        old = time.time() - 2 * 86400
        os.utime(stale, (old, old))
        self.assertEqual(self.sync().returncode, 1, "a stale override is ignored")
        stale.write_text("purge of test characters, ticket 12\n")
        done = self.sync()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("drop allowed", done.stderr)
        message = git("--git-dir", str(self.bare), "log", "-1", "--format=%B", "main")
        self.assertIn("Drop allowed by override (player:12->6): purge of test characters, "
                      "ticket 12", message)
        self.assertFalse(stale.exists(), "used once")
        self.assertEqual(len(list(self.state.glob("allow-drop.used-*"))), 1)
        self.assertNotIn("player/Zfixb", self.remote_files())

    def test_corpses_that_rot_are_not_a_drop(self) -> None:
        (self.live / "corpse" / "live").mkdir(parents=True)
        for n in range(4):
            (self.live / "corpse" / "live" / f"{n}.corpse").write_text("x\n")
        self.assertEqual(self.sync().returncode, 0)
        for path in (self.live / "corpse" / "live").iterdir():
            path.unlink()
        self.assertEqual(self.sync().returncode, 0, self.attempt())

    @unittest.skipIf(os.geteuid() == 0, "root reads a directory whatever its mode")
    def test_a_tree_that_cannot_be_read_is_refused(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        locked = self.live / "player" / "recovery"
        locked.mkdir()
        (locked / "ledger.tsv").write_text("x\n")
        locked.chmod(0)
        try:
            done = self.sync()
            self.assertEqual(done.returncode, 1)
            self.assertIn("cannot read all of", self.attempt()["reason"])
        finally:
            locked.chmod(0o755)

    def test_a_read_error_part_way_is_refused_even_as_root(self) -> None:
        """What a half-mounted or failing disk looks like to find: some files
        and an error. The count is not trusted, so nothing is copied."""
        self.assertEqual(self.sync().returncode, 0)
        before = self.remote_main()
        real = shutil.which("find")
        (self.stubs / "find").write_text(
            "#!/bin/sh\ncase \"$1\" in\n"
            f"  {self.live}/player) echo \"$1/Zfixa\"; echo 'find: I/O error' >&2; exit 1 ;;\n"
            f"esac\nexec {real} \"$@\"\n")
        (self.stubs / "find").chmod(0o755)
        (self.live / "player" / "Zfixa").write_text("changed, never pushed\n")
        done = self.sync()
        self.assertEqual(done.returncode, 1)
        self.assertIn("cannot read all of", self.attempt()["reason"])
        self.assertEqual(self.remote_main(), before)

    # --- the check, with nothing to read ----------------------------------

    def test_no_receipt_is_unhealthy(self) -> None:
        git("clone", "-q", str(self.bare), str(self.root / "state"))
        said, marker, queue = self.check()
        self.assertEqual(said.returncode, 1)
        self.assertIn("no verified sync on record", marker)
        self.assertIn("no sync attempt on record", marker)
        self.assertIn("wizinfo|60|", queue)

    def test_an_unreadable_unpushed_count_is_unhealthy(self) -> None:
        self.assertEqual(self.sync().returncode, 0)
        git("branch", "--unset-upstream", cwd=self.root / "state")
        said, marker, _ = self.check()
        self.assertEqual(said.returncode, 1)
        self.assertIn("cannot tell whether the clone holds unpushed commits", marker)
        self.assertIn("unpushed=unknown", marker)
        shutil.rmtree(self.root / "state")
        said, marker, _ = self.check()
        self.assertEqual(said.returncode, 1)
        self.assertIn("no state clone", marker)


class StateSyncUnitTests(unittest.TestCase):
    """The units: a failure is a failure, and the schedule does not lean on
    the last run's result."""

    def test_exit_one_is_no_longer_success(self) -> None:
        unit = "\n".join(line for line in (UNITS / "toc-state-sync.service").read_text()
                         .splitlines() if not line.startswith("#"))
        self.assertNotIn("SuccessExitStatus", unit)
        self.assertIn("StateDirectory=toc-state-sync", unit)
        self.assertIn("TOC_SYNC_STATE_DIR=/var/lib/toc-state-sync", unit)

    def test_the_timers_are_on_the_wall_clock(self) -> None:
        for name, every in (("toc-state-sync.timer", "*:00/5:00"),
                            ("toc-state-sync-check.timer", "*:07/15:00")):
            timer = (UNITS / name).read_text()
            lines = [line for line in timer.splitlines() if not line.startswith("#")]
            self.assertIn(f"OnCalendar=*-*-* {every}", lines, name)
            self.assertIn("Persistent=true", lines, name)
            self.assertNotIn("OnUnitActiveSec", "\n".join(lines), name)


if __name__ == "__main__":
    unittest.main()
