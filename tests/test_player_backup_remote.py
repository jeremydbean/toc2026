"""The encrypted private backup: generations, verified pushes, an honest
status, and a restore drill (review, 2026-11-23).

deploy/sync-player-backup.sh force-pushed one "latest" archive, so a bad run
replaced the only encrypted copy, and nothing recorded whether it had ever
run. It keeps generations now, pushes with a lease on what it read, verifies
the push by fetching the archive back, refuses a tree that shrank past
belief, and writes last-attempt / last-success / status -- "not-configured"
when it has nothing to push to.

Everything runs against a local bare repository and a throwaway age key made
for the test, with synthetic Z characters only. The drill decrypts a pushed
generation with deploy/restore-player-backup.sh into a scratch directory and
compares it with what was archived.
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
BACKUP = ROOT / "deploy" / "sync-player-backup.sh"
RESTORE = ROOT / "deploy" / "restore-player-backup.sh"
UNITS = ROOT / "deploy" / "windows-vm"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def receipt(path: Path) -> dict:
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


@unittest.skipIf(any(shutil.which(t) is None for t in ("git", "age", "age-keygen", "flock")),
                 "needs git, age, age-keygen and flock")
class PlayerBackupTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self._tmp.name)
        self.bare = root / "backups.git"
        git("init", "-q", "--bare", "-b", "main", str(self.bare))
        self.live = root / "live"
        (self.live / "player" / "versions" / "Zalpha").mkdir(parents=True)
        (self.live / "corpse" / "live").mkdir(parents=True)
        (self.live / "log").mkdir()
        (self.live / "log" / "deployed-commit").write_text("a" * 40 + " 2026-11-23T00:00:00Z\n")
        for n, name in enumerate(("Zalpha", "Zbravo", "Zcharl", "Zdelta", "Zecho")):
            (self.live / "player" / name).write_text(f"#PLAYER\nName {name}~\n{'#' * (n + 1)}\nEnd\n")
        (self.live / "player" / "versions" / "Zalpha" / "Zalpha.20261123_000000").write_text("old\n")
        (self.live / "corpse" / "live" / "1.corpse").write_text("#CORPSE\n")
        self.identity = root / "drill-identity.txt"
        subprocess.run(["age-keygen", "-o", str(self.identity)], check=True, capture_output=True)
        recipient = subprocess.run(["age-keygen", "-y", str(self.identity)], check=True,
                                   capture_output=True, text=True).stdout
        (root / "recipient.txt").write_text(recipient)
        self.state = root / "backup-state"
        self.stubs = root / "bin"
        self.stubs.mkdir()
        (self.stubs / "logger").write_text("#!/bin/sh\nexit 0\n")
        (self.stubs / "logger").chmod(0o755)
        self.env = dict(os.environ, TOC_ROOT=str(self.live), BACKUP_REMOTE=f"file://{self.bare}",
                        BACKUP_BRANCH="snapshots", AGE_RECIPIENT_FILE=str(root / "recipient.txt"),
                        GIT_SSH_KEY=str(root / "no-key"), TOC_BACKUP_STATE_DIR=str(self.state),
                        TOC_BACKUP_LOCK=str(root / "backup.lock"),
                        PATH=f"{self.stubs}:{os.environ['PATH']}")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_backup(self, **extra) -> subprocess.CompletedProcess:
        # A generation is named to the second, and a second run in the same
        # second is refused as a duplicate: wait for the next one.
        last = getattr(self, "_last_second", None)
        while int(time.time()) == last:
            time.sleep(0.05)
        self._last_second = int(time.time())
        return subprocess.run(["sh", str(BACKUP)], env=dict(self.env, **extra),
                              capture_output=True, text=True, timeout=120)

    def remote_files(self) -> list[str]:
        return git("--git-dir", str(self.bare), "ls-tree", "-r", "--name-only",
                   "snapshots").split()

    def archives(self) -> list[str]:
        return sorted(f for f in self.remote_files() if f.endswith(".tar.gz.age"))

    def head(self) -> str:
        return git("--git-dir", str(self.bare), "rev-parse", "snapshots").strip()

    def status(self) -> str:
        path = self.state / "status"
        return path.read_text().strip() if path.exists() else ""

    def checkout(self) -> Path:
        out = self.root / f"clone-{time.time_ns()}"
        git("clone", "-q", "--depth", "1", "-b", "snapshots", f"file://{self.bare}", str(out))
        return out

    def backup_at(self, stamp_epoch: float) -> subprocess.CompletedProcess:
        """A run whose clock reads `stamp_epoch`, through a date stand-in that
        shifts only plain `date -u +FORMAT` (what names a generation)."""
        real = shutil.which("date")
        offset = int(stamp_epoch - time.time())
        (self.stubs / "date").write_text(
            "#!/bin/sh\n"
            f"if [ \"$1\" = -u ] && [ \"$#\" -eq 2 ]; then exec {real} -u -d \"@$(( $({real} +%s) + {offset} ))\" \"$2\"; fi\n"
            f"exec {real} \"$@\"\n")
        (self.stubs / "date").chmod(0o755)
        try:
            return self.run_backup()
        finally:
            (self.stubs / "date").unlink()

    # --- configuration ----------------------------------------------------

    def test_without_configuration_it_says_not_configured_never_ok(self) -> None:
        done = self.run_backup(BACKUP_REMOTE="")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.status(), "not-configured")
        attempt = receipt(self.state / "last-attempt")
        self.assertEqual(attempt["result"], "not-configured")
        self.assertIn("BACKUP_REMOTE", attempt["reason"])
        self.assertFalse((self.state / "last-success").exists())
        done = self.run_backup(AGE_RECIPIENT_FILE=str(self.root / "gone"))
        self.assertEqual(self.status(), "not-configured")
        self.assertIn("recipient", receipt(self.state / "last-attempt")["reason"])
        done = self.run_backup(BACKUP_REMOTE="git@example.invalid:x/y.git")
        self.assertIn("key(", receipt(self.state / "last-attempt")["reason"])

    # --- a run, and what it proves --------------------------------------------

    def test_a_push_is_verified_and_recorded(self) -> None:
        done = self.run_backup()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.status(), "ok")
        got = receipt(self.state / "last-success")
        self.assertEqual(got["remote_commit"], self.head())
        self.assertEqual(got["generations"], "1")
        self.assertEqual(got["player_file_count"], "6")
        self.assertEqual(self.archives(), [got["archive"]])
        self.assertIn("latest.txt", self.remote_files())
        blob = subprocess.run(["git", "--git-dir", str(self.bare), "show",
                               f"snapshots:{got['archive']}"], capture_output=True).stdout
        self.assertTrue(blob.startswith(b"age-encryption.org/v1"))
        self.assertNotIn(b"Zalpha", blob, "nothing in the clear")

    def test_restore_drill_from_the_remote(self) -> None:
        """The drill: clone the backup branch, decrypt with the identity
        into a scratch directory, and hold every file to what was archived."""
        self.assertEqual(self.run_backup().returncode, 0)
        clone = self.checkout()
        out = self.root / "drill"
        done = subprocess.run(["sh", str(RESTORE), str(clone), str(self.identity), str(out)],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("checksums match", done.stdout)
        for path in self.live.rglob("*"):
            rel = path.relative_to(self.live)
            if path.is_file() and rel.parts[0] in ("player", "corpse"):
                self.assertEqual((out / rel).read_bytes(), path.read_bytes(), rel)
        self.assertFalse((out / "log").exists(), "only player/ and corpse/")
        # A tampered archive is refused before anything is decrypted.
        target = self.root / "drill2"
        archive = next((clone / "archives").glob("*.tar.gz.age"))
        archive.write_bytes(archive.read_bytes() + b"x")
        done = subprocess.run(["sh", str(RESTORE), str(clone), str(self.identity), str(target)],
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("does not match its record", done.stderr)
        self.assertFalse(target.exists())
        # And never into a directory that holds anything.
        done = subprocess.run(["sh", str(RESTORE), str(clone), str(self.identity), str(out)],
                              capture_output=True, text=True, timeout=60)
        self.assertIn("not empty", done.stderr)

    def test_generations_are_kept_and_thinned(self) -> None:
        now = time.time()
        # Every six hours for twelve days: 48 runs.
        for n in range(48):
            done = self.backup_at(now - (47 - n) * 6 * 3600)
            self.assertEqual(done.returncode, 0, done.stderr)
        kept = [Path(a).name[:16] for a in self.archives()]
        self.assertLessEqual(len(kept), 4 + 7 + 4)
        days = {k[:8] for k in kept}
        self.assertGreaterEqual(len(days), 7, kept)
        newest = time.strftime("%Y%m%dT%H%M", time.gmtime(now))
        self.assertTrue(kept[-1].startswith(newest[:11]), (kept[-1], newest))
        self.assertEqual(len(git("--git-dir", str(self.bare), "log", "--format=%H",
                                 "snapshots").split()), 1, "one squashed commit")
        self.assertEqual(receipt(self.state / "last-success")["generations"], str(len(kept)))

    def test_an_old_single_archive_branch_becomes_the_first_generation(self) -> None:
        seed = self.root / "old"
        seed.mkdir()
        git("init", "-q", "-b", "snapshots", str(seed))
        (seed / "player-latest.tar.gz.age").write_bytes(b"age-encryption.org/v1\nold")
        (seed / "snapshot.txt").write_text("created_utc=2026-11-01T00:00:00Z\nplayer_file_count=6\n")
        git("add", "-A", cwd=seed)
        git("commit", "-qm", "old", cwd=seed)
        git("push", "-q", f"file://{self.bare}", "snapshots", cwd=seed)
        self.assertEqual(self.run_backup().returncode, 0)
        files = self.remote_files()
        self.assertIn("archives/20261101T000000Z.tar.gz.age", files)
        self.assertNotIn("player-latest.tar.gz.age", files)
        self.assertEqual(len(self.archives()), 2)

    # --- failures, none of which may touch the last good copy -----------------

    def test_a_remote_that_does_not_answer_pushes_nothing(self) -> None:
        self.assertEqual(self.run_backup().returncode, 0)
        before = self.head()
        done = self.run_backup(BACKUP_REMOTE=f"file://{self.root / 'nowhere.git'}")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.status(), "failed")
        self.assertIn("did not answer", receipt(self.state / "last-attempt")["reason"])
        self.assertEqual(self.head(), before)

    def test_a_refused_push_keeps_the_branch(self) -> None:
        self.assertEqual(self.run_backup().returncode, 0)
        before, success = self.head(), receipt(self.state / "last-success")
        hook = self.bare / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        done = self.run_backup()
        self.assertEqual(done.returncode, 1)
        self.assertIn("push was refused", receipt(self.state / "last-attempt")["reason"])
        self.assertEqual(self.head(), before)
        self.assertEqual(receipt(self.state / "last-success"), success)

    def test_a_branch_moved_by_someone_else_is_not_pushed_over(self) -> None:
        self.assertEqual(self.run_backup().returncode, 0)
        # Between this run's read and its push, the branch moves: played by
        # a git stand-in that pushes another commit just before the push.
        real = shutil.which("git")
        other = self.root / "other"
        git("clone", "-q", "-b", "snapshots", f"file://{self.bare}", str(other))
        (other / "note").write_text("someone else\n")
        git("add", "note", cwd=other)
        git("commit", "-qm", "other", cwd=other)
        (self.stubs / "git").write_text(
            "#!/bin/sh\nfor a in \"$@\"; do if [ \"$a\" = push ] && [ ! -e "
            f"{self.root}/moved ]; then : > {self.root}/moved; "
            f"{real} -C {other} push -q origin snapshots; fi; done\nexec {real} \"$@\"\n")
        (self.stubs / "git").chmod(0o755)
        done = self.run_backup()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("note", self.remote_files(), "the other commit stands")

    def test_a_failed_archive_pushes_nothing(self) -> None:
        self.assertEqual(self.run_backup().returncode, 0)
        before = self.head()
        (self.stubs / "tar").write_text("#!/bin/sh\nexit 2\n")
        (self.stubs / "tar").chmod(0o755)
        done = self.run_backup()
        self.assertEqual(done.returncode, 1)
        self.assertIn("tar failed", receipt(self.state / "last-attempt")["reason"])
        self.assertEqual(self.head(), before)

    def test_an_emptied_player_tree_is_refused_then_allowed_once(self) -> None:
        self.assertEqual(self.run_backup().returncode, 0)
        before = self.head()
        for name in ("Zbravo", "Zcharl", "Zdelta", "Zecho"):
            (self.live / "player" / name).unlink()
        done = self.run_backup()
        self.assertEqual(done.returncode, 1)
        self.assertIn("refused", receipt(self.state / "last-attempt")["reason"])
        self.assertEqual(self.head(), before)
        (self.state / "allow-drop").write_text("purging test characters\n")
        done = self.run_backup()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((self.state / "allow-drop").exists())
        self.assertEqual(len(self.archives()), 2, "the older generation is kept")

    def test_an_archive_too_big_for_github_is_refused(self) -> None:
        done = self.run_backup(TOC_BACKUP_MAX_ARCHIVE_MB="0")
        self.assertEqual(done.returncode, 1)
        self.assertIn("GitHub refuses", receipt(self.state / "last-attempt")["reason"])
        self.assertEqual(git("--git-dir", str(self.bare), "branch", "--list"), "")


class PlayerBackupUnitTests(unittest.TestCase):

    def test_the_timer_runs_on_the_wall_clock(self) -> None:
        lines = [line for line in (UNITS / "toc-player-backup.timer").read_text().splitlines()
                 if not line.startswith("#")]
        self.assertIn("OnCalendar=*-*-* 00/6:17:00", lines)
        self.assertIn("Persistent=true", lines)
        self.assertFalse([line for line in lines if line.startswith("OnUnitActiveSec")])

    def test_the_service_records_its_state(self) -> None:
        unit = (UNITS / "toc-player-backup.service").read_text()
        self.assertIn("EnvironmentFile=-/etc/toc/player-backup.env", unit)
        self.assertIn("StateDirectory=toc-player-backup", unit)


if __name__ == "__main__":
    unittest.main()
