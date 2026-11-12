"""The telemetry files are written whole or say they were not (review,
2026-11-12).

log/progress.tsv, log/play.tsv and log/hyrule.tsv go through one writer,
telemetry_append in src/playlog.c. Before it, a row that could not be
written (the file a directory, a full disk) was dropped without a word and
counted as written anyway, so the next trim came early; and a trim read the
file a line at a time on the game loop -- and when it could not cut, read
it again for every row after.

Now a row that does not reach the file is counted as lost and toc.log hears
of it at most once a TOC_TELEMETRY_REPORT_SECS (a minute in play): how many,
why, and the count the file stands at -- never the row. Only rows that
reached the file are counted, which the reports show; and a trim says how
long it took.

Synthetic Z characters in the fixture world; every file here is in the
test's throwaway tree.
"""
from __future__ import annotations

import os
import re
import time
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, LiveMud, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Ztelemetry1"
FULL = Path("/dev/full")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def toc_log(mud: LiveMud) -> str:
    path = mud.root / "log" / "toc.log"
    return path.read_text(encoding="latin-1") if path.exists() else ""


def synthetic_rows(count: int) -> str:
    """Rows shaped like progress.tsv's (numbers and an area file only)."""
    return "".join(f"{1762900000 + i}\tconsider\t{70000 + i % 7}\t10\t3\t0\t100\t100"
                   f"\t32700\t10\tztestfix.are\t1.0\t1.0\t2.0\t2.0\teven\t100\t100\t0\n"
                   for i in range(count))


def setup_pair(mud: LiveMud):
    """A staff fixture and a mortal beside the sparring guard."""
    make(mud, "Zwatcher", Levl=70, Room=SPARRING_FLOOR)
    make(mud, "Zcounter", Levl=10, Room=SPARRING_FLOOR)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ProgressAccountingTests(unittest.TestCase):
    @unittest.skipUnless(FULL.exists(), "needs /dev/full to fail a write as a full disk does")
    def test_a_lost_row_is_reported_once_and_never_counted(self) -> None:
        with LiveMud(fixtures=True, extra_env={"TOC_TELEMETRY_REPORT_SECS": "3"}) as mud:
            setup_pair(mud)
            progress = mud.root / "log" / "progress.tsv"
            progress.write_text(synthetic_rows(100), encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as mortal:
                login(staff, "Zwatcher", PW)
                login(mortal, "Zcounter", PW)
                place_sparring_guard(staff, "Zwatcher", SPARRING_FLOOR)
                mortal.sync("consider sparring")
                lines = progress.read_text(encoding="latin-1").splitlines()
                self.assertEqual(len(lines), 101)
                self.assertEqual(lines[-1].split("\t")[1], "consider")
                kept = progress.read_bytes()

                # A full disk: the file is /dev/full from here.
                link = progress.with_name("progress.link")
                link.symlink_to(FULL)
                os.replace(link, progress)
                for _ in range(3):
                    mortal.sync("consider sparring")
                time.sleep(0.5)
                log = toc_log(mud)
                reports = re.findall(r"Telemetry: log/progress\.tsv: .*", log)
                self.assertEqual(len(reports), 1, log[-3000:])
                self.assertIn("1 row not written since the last report", reports[0])
                self.assertIn("No space left on device", reports[0])
                # The failed rows were not counted: 101 is what reached it.
                self.assertIn("101 rows counted in the file", reports[0])
                self.assertIsNone(mud.proc.poll(), "the game kept running")

                # The disk has room again: the next row is written, and the
                # rows lost while it was full are said now the report is due.
                progress.unlink()
                progress.write_bytes(kept)
                time.sleep(3.5)
                mortal.sync("consider sparring")
                time.sleep(0.5)
                log = toc_log(mud)
                resumed = re.findall(r"Telemetry: log/progress\.tsv: writing again.*", log)
                self.assertEqual(len(resumed), 1, log[-3000:])
                self.assertIn("2 rows not written before it did", resumed[0])
                self.assertIn("102 rows counted in the file", resumed[0])
                lines = progress.read_text(encoding="latin-1").splitlines()
                self.assertEqual(len(lines), 102)
                for client in (staff, mortal):
                    client.send("quit")
                    client.wait_closed()

    def test_a_trim_keeps_the_newest_rows_and_says_how_long_it_took(self) -> None:
        with LiveMud(fixtures=True) as mud:
            setup_pair(mud)
            progress = mud.root / "log" / "progress.tsv"
            # One under PROGRESS_MAX (40000): the first row fills it, the
            # second trims it to PROGRESS_KEEP (20000) and is added.
            progress.write_text(synthetic_rows(39999), encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as mortal:
                login(staff, "Zwatcher", PW)
                login(mortal, "Zcounter", PW)
                place_sparring_guard(staff, "Zwatcher", SPARRING_FLOOR)
                mortal.sync("consider sparring")
                self.assertEqual(len(progress.read_text(encoding="latin-1").splitlines()), 40000)
                self.assertNotIn("trimmed", toc_log(mud))
                mortal.sync("consider sparring")
                time.sleep(0.5)
                lines = progress.read_text(encoding="latin-1").splitlines()
                self.assertEqual(len(lines), 20001)
                # The oldest kept is the 20,001st synthetic row (0-based 20000).
                self.assertTrue(lines[0].startswith(f"{1762900000 + 20000}\t"), lines[0])
                self.assertEqual([l.split("\t")[1] for l in lines[-2:]], ["consider", "consider"])
                trims = re.findall(r"Telemetry: log/progress\.tsv trimmed from (\d+) to (\d+) "
                                   r"rows in (\d+) ms\.", toc_log(mud))
                self.assertEqual([t[:2] for t in trims], [("40000", "20000")], toc_log(mud)[-2000:])
                print(f"\n  progress.tsv trim of 40000 rows: {trims[0][2]} ms", flush=True)
                for client in (staff, mortal):
                    client.send("quit")
                    client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class JournalAccountingTests(unittest.TestCase):
    def test_a_journal_that_cannot_be_written_is_said_once(self) -> None:
        with LiveMud(extra_env={"TOC_TELEMETRY_REPORT_SECS": "600"}) as mud:
            make(mud, "Zjournal", Levl=10)
            # The journal a directory: no row can be written to it, and no
            # trim can read it (once a minute at most, never every row).
            mud._stop()
            journal = mud.root / "log" / "play.tsv"
            if journal.exists():
                journal.unlink()
            journal.mkdir()
            mud._launch()
            with mud.connect(timeout=120) as client:
                login(client, "Zjournal", PW)
                for line in ("look", "inventory", "equipment"):
                    client.sync(line)
                # Still answering: the journal's trouble is the journal's.
                self.assertIn("Pkiller", client.sync("score"))
                client.send("quit")
                client.wait_closed()
            self.assertIsNone(mud.proc.poll(), "the game kept running")
            log = toc_log(mud)
            reports = re.findall(r"Telemetry: log/play\.tsv: .*", log)
            self.assertEqual(len(reports), 1, log[-3000:])
            self.assertIn("open: Is a directory", reports[0])
            self.assertIn("not counted yet", reports[0])
            trims = re.findall(r"Telemetry: log/play\.tsv could not be trimmed.*", log)
            self.assertEqual(len(trims), 1, log[-3000:])
            self.assertIn("not a regular file", trims[0])
            self.assertTrue(journal.is_dir())


class TelemetrySourceTests(unittest.TestCase):
    def test_every_telemetry_file_goes_through_the_one_writer(self) -> None:
        playlog = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        hyrule = (ROOT / "src" / "hyrulelog.c").read_text(encoding="latin-1")
        for name, text in (("playlog.c", playlog), ("hyrulelog.c", hyrule)):
            # No row is printed straight into a log file any more.
            self.assertNotRegex(text, r"\bfprintf\s*\(", name)
            self.assertNotRegex(text, r"_lines\s*\+\+", name)
        self.assertIn("telemetry_append( &journal_log,", playlog)
        self.assertIn("telemetry_append( &progress_log,", playlog)
        self.assertIn("telemetry_append( &hylog_log,", hyrule)

    def test_a_trim_never_replaces_a_file_it_could_not_account_for(self) -> None:
        """A count that ran ahead of the file (cut short by hand) must not
        trim it to nothing: the trim leaves it and recounts. Live, the count
        cannot be driven to PROGRESS_MAX without as many rows, so the guard
        is held here by its place: before the rename."""
        playlog = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        trim = playlog.split("static void telemetry_trim(", 1)[1].split("\n}\n", 1)[0]
        guard = trim.index("if ( cutting )")
        self.assertLess(guard, trim.index("temp_file_commit("))
        self.assertIn("remove( temp );", trim[guard:trim.index("temp_file_commit(")])
        self.assertIn("log->rows = seen;", trim[guard:trim.index("temp_file_commit(")])
        # A device or a directory is never read as a log (/dev/full reads
        # zeros for ever).
        self.assertIn("S_ISREG( st.st_mode )", trim)


if __name__ == "__main__":
    unittest.main()
