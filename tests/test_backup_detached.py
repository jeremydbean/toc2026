"""The player backups run beside the game, not inside it (2026-11-08).

The four-hourly and daily archives of player/ were system() calls on the
game loop: every four hours the game stood still for a quarter second,
and 0.6 seconds at boot when both ran, and the play journal blamed the
disaster check (the weather step that holds them had no phase label).
They are made by a detached shell now; it writes "complete" to toc.log.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()


def dead_pid() -> int:
    """A pid no process holds now. The jobs judge a temporary or a lock by
    `kill -0` of the pid it names, and a fixed one (4242, 999999) belonged
    to a live process on a busy runner often enough to fail CI: the job
    then rightly left the "stale" file alone (2026-11-23)."""
    for pid in range(3_900_000, 4_100_000, 7919):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            continue
    raise AssertionError("no free pid found")


class BackupSourceTests(unittest.TestCase):
    def test_no_backup_waits_on_the_game_loop(self) -> None:
        code = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        start = code.index("static void backup_launch(")
        body = code[start:code.index("void show_backup(")]
        self.assertNotIn("system(", body)
        self.assertIn("execl( \"/bin/sh\"", body)
        self.assertIn("close( fd );", body, "no client socket outlives its close in a tar")
        self.assertIn("waitpid( pid, &status, 0 )", body, "the intermediate child is reaped")
        # Review, 2026-11-09: the lock is the kernel's. No job decides a
        # lock is stale and deletes it, so none can delete another's.
        self.assertIn("flock( fd, LOCK_EX | LOCK_NB )", body)
        script = code[code.index("static const char backup_script[]"):start]
        self.assertNotIn("rm -rf", script)
        self.assertNotIn("mkdir", script)
        # The weather step, which runs the backups, is timed as itself.
        self.assertRegex(code, r'playlog_phase_enter\( "weather_update" \);\s*weather_update\s*\(')


@unittest.skipIf(SKIP is not None, SKIP or "")
class BackupLiveTests(unittest.TestCase):
    def test_boot_backups_land_in_the_background(self) -> None:
        with LiveMud() as mud:
            log = mud.root / "log" / "toc.log"
            deadline = time.monotonic() + 60
            text = ""
            while time.monotonic() < deadline:
                text = log.read_text(encoding="latin-1") if log.exists() else ""
                if "Automated backup complete." in text and "Daily backup complete." in text:
                    break
                time.sleep(0.5)
            self.assertIn("Automated backup started.", text)
            self.assertIn("Daily backup started.", text)
            self.assertIn("Automated backup complete.", text)
            self.assertIn("Daily backup complete.", text)
            self.assertNotIn("archive creation failed", text)
            # The shell writes toc.log's own format.
            self.assertRegex(text, r"(?m)^\w{3} \w{3} [ \d]\d \d\d:\d\d:\d\d \d{4} :: Automated backup complete\.$")
            archives = sorted((mud.root / "backups").glob("*.tar.gz"))
            self.assertGreaterEqual(len(archives), 2, archives)
            for archive in archives:
                with tarfile.open(archive) as tar:
                    names = tar.getnames()
                self.assertTrue(any(re.match(r"\.\./player|player", n) for n in names), names[:5])
            # The game answers while and after they run.
            with mud.connect() as client:
                client.expect("by what name", "name:")


FAKE_TAR = """#!/bin/sh
# A stand-in for tar on the game's PATH, steered by a mode file.
mode=$(cat "%(mode)s" 2>/dev/null)
case "$1" in
cfz)
  case "$mode" in
  fail) printf 'partial' > "$2"; exit 2 ;;
  term) printf 'partial' > "$2"; kill -TERM "$PPID"; exit 2 ;;
  slow) echo "start $$ $(date +%%s.%%N)" >> "%(spans)s"; sleep 1
        "%(real)s" "$@"; rc=$?
        echo "end $$ $(date +%%s.%%N)" >> "%(spans)s"; exit $rc ;;
  esac ;;
esac
exec "%(real)s" "$@"
"""


@unittest.skipIf(SKIP is not None, SKIP or "")
class BackupFailureTests(unittest.TestCase):
    """Review, 2026-11-09: a failed daily backup had already overwritten
    the day's good archive, and two jobs could write one name at once."""

    def wait_for(self, log: Path, text: str, count: int, timeout: float = 60) -> str:
        deadline = time.monotonic() + timeout
        seen = ""
        while time.monotonic() < deadline:
            seen = log.read_text(encoding="latin-1") if log.exists() else ""
            if seen.count(text) >= count:
                return seen
            time.sleep(0.3)
        self.fail(f"{count} x {text!r} never came; log tail:\n{seen[-1500:]}")

    def test_failure_interruption_overlap_and_replacement(self) -> None:
        real = shutil.which("tar")
        self.assertIsNotNone(real)
        with tempfile.TemporaryDirectory(prefix="toc-faketar-") as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            mode, spans = Path(tmp) / "mode", Path(tmp) / "spans"
            mode.write_text("real")
            fake = bindir / "tar"
            fake.write_text(FAKE_TAR % {"mode": mode, "spans": spans, "real": real})
            fake.chmod(0o755)
            env = {"PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
            with LiveMud(extra_env=env) as mud:
                log = mud.root / "log" / "toc.log"
                backups = mud.root / "backups"
                daily = backups / (subprocess.run(["date", "+%b.%d"], capture_output=True,
                                                  text=True).stdout.strip() + ".tar.gz")

                def leftovers() -> list[str]:
                    return sorted(p.name for p in backups.iterdir()
                                  if p.name.startswith(".") and p.name != ".backup.flock")

                # A good boot: both archives, nothing left behind.
                self.wait_for(log, "Daily backup complete.", 1)
                self.wait_for(log, "Automated backup complete.", 1)
                self.assertTrue(daily.is_file())
                good = daily.read_bytes()
                archives = sorted(p.name for p in backups.glob("*.tar.gz"))
                self.assertEqual(leftovers(), [])

                # tar fails part way: the day's good archive stands, no new
                # four-hourly one appears, and nothing is left behind.
                mode.write_text("fail")
                mud.restart()
                self.wait_for(log, "the previous archive is kept.", 2)
                self.assertEqual(daily.read_bytes(), good, "a failed daily backup kept the last good one")
                self.assertEqual(sorted(p.name for p in backups.glob("*.tar.gz")), archives)
                self.assertEqual(leftovers(), [])
                self.assertIn("archive creation failed (tar 2)", log.read_text(encoding="latin-1"))

                # The job is signalled mid-archive: the same.
                mode.write_text("term")
                mud.restart()
                self.wait_for(log, "interrupted; the previous archive is kept.", 2)
                self.assertEqual(daily.read_bytes(), good)
                self.assertEqual(leftovers(), [])

                # A job of an older build that died hard left its directory
                # lock and a temporary archive: the next job clears both,
                # since their owners are gone.
                # Both boot jobs run, one after the other, and the day's
                # archive is replaced by a proven new one.
                lock = backups / ".backup.lock"
                lock.mkdir()
                (lock / "pid").write_text(f"{dead_pid()}\n")
                (backups / f".Zstale.tar.gz.tmp.{dead_pid()}").write_bytes(b"partial")
                before = daily.stat().st_ino
                mode.write_text("slow")
                text = log.read_text(encoding="latin-1")
                done_before = text.count("Daily backup complete.")
                mud.restart()
                self.wait_for(log, "Daily backup complete.", done_before + 1)
                self.wait_for(log, "Automated backup complete.", 2)
                self.assertEqual(leftovers(), [])
                self.assertNotEqual(daily.stat().st_ino, before, "replaced, by rename")
                with tarfile.open(daily) as tar:
                    self.assertTrue(any("player" in n for n in tar.getnames()))
                rows = [line.split() for line in spans.read_text().splitlines()]
                starts = sorted(float(r[2]) for r in rows if r[0] == "start")
                ends = sorted(float(r[2]) for r in rows if r[0] == "end")
                self.assertEqual(len(starts), 2, rows)
                self.assertLessEqual(ends[0], starts[1], f"the two jobs overlapped: {rows}")


    def test_a_held_lock_and_live_owners_are_never_taken(self) -> None:
        """Review, 2026-11-09: two jobs that both saw a dead owner both
        reaped the lock, the second deleting the lock the first had just
        taken, and both wrote at once. The lock is an flock now: while
        anybody holds it no job starts, a temporary archive or an old
        directory lock whose owner is alive is left alone, and the jobs
        boot starts run one after the other."""
        real = shutil.which("tar")
        self.assertIsNotNone(real)
        with tempfile.TemporaryDirectory(prefix="toc-faketar-") as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            mode, spans = Path(tmp) / "mode", Path(tmp) / "spans"
            mode.write_text("slow")
            fake = bindir / "tar"
            fake.write_text(FAKE_TAR % {"mode": mode, "spans": spans, "real": real})
            fake.chmod(0o755)
            env = {"PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
            with LiveMud(extra_env=env) as mud:
                log = mud.root / "log" / "toc.log"
                backups = mud.root / "backups"
                self.wait_for(log, "Daily backup complete.", 1)
                self.wait_for(log, "Automated backup complete.", 1)
                spans.write_text("")

                # Somebody else's: a live writer's temporary archive and a
                # directory lock whose owner lives (this test).
                live = backups / f".Zlive.tar.gz.tmp.{os.getpid()}"
                live.write_bytes(b"in progress")
                legacy = backups / ".backup.lock"
                legacy.mkdir()
                (legacy / "pid").write_text(f"{os.getpid()}\n")
                dead = backups / f".Zdead.tar.gz.tmp.{dead_pid()}"
                dead.write_bytes(b"partial")

                lockfile = backups / ".backup.flock"
                done_before = log.read_text(encoding="latin-1").count("backup complete.")
                with open(lockfile, "a+") as held:
                    fcntl.flock(held, fcntl.LOCK_EX)
                    mud.restart()
                    self.wait_for(log, "Daily backup started.", 2)
                    time.sleep(4)
                    # Nothing ran while the lock was held elsewhere.
                    self.assertEqual(spans.read_text(), "")
                    self.assertEqual(log.read_text(encoding="latin-1").count("backup complete."),
                                     done_before)
                    self.assertTrue(dead.exists(), "nothing is cleaned without the lock")
                self.wait_for(log, "Daily backup complete.", 2)
                self.wait_for(log, "Automated backup complete.", 2)
                rows = [line.split() for line in spans.read_text().splitlines()]
                starts = sorted(float(r[2]) for r in rows if r[0] == "start")
                ends = sorted(float(r[2]) for r in rows if r[0] == "end")
                self.assertEqual(len(starts), 2, rows)
                self.assertLessEqual(ends[0], starts[1], f"the two jobs overlapped: {rows}")
                self.assertTrue(live.exists(), "a live writer's temporary was deleted")
                self.assertTrue((legacy / "pid").exists(), "a live owner's lock was deleted")
                self.assertFalse(dead.exists(), "a dead writer's temporary was kept")
                live.unlink()
                (legacy / "pid").unlink()
                legacy.rmdir()


def backup_script() -> str:
    """The shell the game runs, read out of src/update.c's C string."""
    import ast
    code = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
    start = code.index("static const char backup_script[] =")
    body = code[start:code.index("static void backup_launch(", start)]
    text = ""
    for match in re.finditer(r'"((?:[^"\\]|\\.)*)"|(BACKUP_DIR)', body[body.index("=") + 1:]):
        text += "../backups/" if match.group(2) else ast.literal_eval('"' + match.group(1) + '"')
    return text


class BackupStorageTests(unittest.TestCase):
    """Review, 2026-11-23: archives expired only after a new one succeeded,
    so a backup failing for want of room never freed any; nothing checked
    the room before tar, and nothing told staff. Expiry and the budget now
    run first and on their own, the newest TOC_BACKUP_KEEP always stay, and
    a job without room for an archive and a reserve makes none and says so.
    Runs the game's own script, read from update.c, in a synthetic tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self._tmp.name)
        for d in ("area", "backups", "log", "player", "bin"):
            (root / d).mkdir()
        (root / "player" / "Zstore").write_text("#PLAYER\nName Zstore~\nEnd\n")
        (root / "area" / "webadmin.queue").write_text("")
        self.env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def archive(self, name: str, days_old: float, size: int = 4096) -> Path:
        path = self.root / "backups" / f"{name}.tar.gz"
        path.write_bytes(os.urandom(size))
        when = time.time() - days_old * 86400
        os.utime(path, (when, when))
        return path

    def stub(self, name: str, text: str) -> None:
        path = self.root / "bin" / name
        path.write_text(text)
        path.chmod(0o755)

    def run_job(self, **env) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", "-c", backup_script(), "toc-backup", "Znew.%H%M%S",
                               "Zjob complete.", "do_backup", "held"],
                              cwd=self.root / "area", env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=60)

    def names(self) -> list[str]:
        return sorted(p.name for p in (self.root / "backups").glob("*.tar.gz"))

    def log(self) -> str:
        path = self.root / "log" / "toc.log"
        return path.read_text() if path.exists() else ""

    def test_old_archives_expire_even_when_the_new_one_fails(self) -> None:
        for n in range(10):
            self.archive(f"Zold{n:02d}", 40 + n)
        self.stub("tar", "#!/bin/sh\n[ \"$1\" = cfz ] && { printf x > \"$2\"; exit 2; }\nexit 0\n")
        self.run_job()
        # The six newest stay, however old; the four past them are gone.
        self.assertEqual(self.names(), [f"Zold{n:02d}.tar.gz" for n in range(6)])
        self.assertIn("4 old archive(s) expired", self.log())
        self.assertIn("archive creation failed (tar 2)", self.log())
        self.assertIn("wizinfo|60|The game's own player backup failed",
                      (self.root / "area" / "webadmin.queue").read_text())
        self.assertEqual([p.name for p in (self.root / "backups").iterdir()
                          if p.name.startswith(".")], [], "no temporary left")

    def test_recent_archives_are_never_expired_by_age(self) -> None:
        for n in range(8):
            self.archive(f"Zrecent{n}", n)
        self.run_job()
        self.assertEqual(len(self.names()), 9, self.log())
        self.assertIn("Zjob complete.", self.log())

    def test_the_budget_takes_the_oldest_but_never_the_newest_kept(self) -> None:
        for n in range(9):
            self.archive(f"Zbig{n}", n + 1, size=400 * 1024)
        self.run_job(TOC_BACKUP_BUDGET_MB="1")
        names = self.names()
        self.assertIn("Zbig0.tar.gz", names)
        self.assertNotIn("Zbig8.tar.gz", names)
        self.assertGreaterEqual(len([n for n in names if n.startswith("Zbig")]), 5)
        self.assertIn("Zjob complete.", self.log())

    def fake_df(self, kb: int, inodes: int) -> None:
        real = shutil.which("df")
        self.stub("df", "#!/bin/sh\n"
                  f"if [ \"$1\" = -Pk ]; then echo 'Filesystem 1K-blocks Used Available Use% Mounted';"
                  f" echo 'fake 100 0 {kb} 1% /'; exit 0; fi\n"
                  f"if [ \"$1\" = -Pi ]; then echo 'Filesystem Inodes IUsed IFree IUse% Mounted';"
                  f" echo 'fake 100 0 {inodes} 1% /'; exit 0; fi\n"
                  f"exec {real} \"$@\"\n")

    def test_no_room_means_no_archive_and_staff_are_told(self) -> None:
        for n in range(8):
            self.archive(f"Zfull{n}", n + 1)
        self.fake_df(kb=10, inodes=10 ** 6)
        self.run_job()
        names = self.names()
        # Everything past the newest six was tried; those six are kept.
        self.assertEqual(names, [f"Zfull{n}.tar.gz" for n in range(6)])
        self.assertIn("not enough room for an archive", self.log())
        self.assertNotIn("Zjob complete.", self.log())
        self.assertIn("wizinfo|60|The game's own player backup was skipped",
                      (self.root / "area" / "webadmin.queue").read_text())
        self.assertTrue((self.root / "player" / "Zstore").exists())

    def test_no_inodes_is_no_room_either(self) -> None:
        self.fake_df(kb=10 ** 9, inodes=5)
        self.run_job()
        self.assertEqual(self.names(), [])
        self.assertIn("not enough room for an archive", self.log())

    def test_room_enough_makes_the_archive(self) -> None:
        self.fake_df(kb=10 ** 9, inodes=10 ** 6)
        self.run_job()
        self.assertEqual(len(self.names()), 1, self.log())


if __name__ == "__main__":
    unittest.main()
