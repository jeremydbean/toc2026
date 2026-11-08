"""The player backups run beside the game, not inside it (2026-11-08).

The four-hourly and daily archives of player/ were system() calls on the
game loop: every four hours the game stood still for a quarter second,
and 0.6 seconds at boot when both ran, and the play journal blamed the
disaster check (the weather step that holds them had no phase label).
They are made by a detached shell now; it writes "complete" to toc.log.
"""

from __future__ import annotations

import re
import tarfile
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


if __name__ == "__main__":
    unittest.main()
