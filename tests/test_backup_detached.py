"""The player backups run beside the game, not inside it (2026-11-08).

The four-hourly and daily archives of player/ were system() calls on the
game loop: every four hours the game stood still for a quarter second,
and 0.6 seconds at boot when both ran, and the play journal blamed the
disaster check (the weather step that holds them had no phase label).
They are made by a detached shell now; it writes "complete" to toc.log.
"""

from __future__ import annotations

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


class BackupSourceTests(unittest.TestCase):
    def test_no_backup_waits_on_the_game_loop(self) -> None:
        code = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        start = code.index("static void backup_launch(")
        body = code[start:code.index("void show_backup(")]
        self.assertNotIn("system(", body)
        self.assertIn("execl( \"/bin/sh\"", body)
        self.assertIn("close( fd );", body, "no client socket outlives its close in a tar")
        self.assertIn("waitpid( pid, &status, 0 )", body, "the intermediate child is reaped")
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
                    return sorted(p.name for p in backups.iterdir() if p.name.startswith("."))

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

                # A job that died hard left its lock and a temporary archive:
                # the next job takes the lock over and clears the temporary.
                # Both boot jobs run, one after the other, and the day's
                # archive is replaced by a proven new one.
                lock = backups / ".backup.lock"
                lock.mkdir()
                (lock / "pid").write_text("999999\n")
                (backups / ".Zstale.tar.gz.tmp.4242").write_bytes(b"partial")
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


if __name__ == "__main__":
    unittest.main()
