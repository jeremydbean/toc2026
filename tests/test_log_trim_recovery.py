"""The log trim sums every cut line exactly once, whatever fails (review,
2026-11-22).

src/logtrim.c appends a batch of summary rows to log/toc-summary.tsv and
then renames the trimmed copy over the log. A rename that failed, or a
game that stopped between the two, left the summed lines in the log, and
the next trim summed them again; a batch cut short left rows no reader
could tell from a whole one. Each batch now ends with a "#batch" marker
naming the file (device and inode) and the bytes it summed, with a
checksum: a later trim of the same file sums only what came after, and
rows a marker does not close are cut off before the next batch. Fault
points (TOC_FAULT_FILE, tests only): logtrim-commit (the rename refused),
logtrim-crash (the game gone after the batch landed), logtrim-torn (gone
half way through the batch).

Also held here: the summary's kinds (lead 3 -- the watch log's arrivals,
coin and items are not commands, and "killed X" is a kill, not a death)
and its keys (lead 4 -- no host name, address, path or mail address,
whatever line it comes from).

Every check is the invariant: each synthetic line is either still in the
log or counted once in a closed batch, never both and never twice.
Synthetic lines and Z characters only.
"""
from __future__ import annotations

import datetime
import sys
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, skip_reason

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import log_report  # noqa: E402

SKIP = skip_reason()
LIMIT = 65536
STAMP = "Sat Nov 21 10:00:00 2026"
KEY = "Ztrimkey: line #"
LINES = 1600
SINCE = datetime.datetime(2026, 11, 1)


def synthetic_lines() -> list[str]:
    return [f"{STAMP} :: [*****] BUG: Ztrimkey: line {n}" for n in range(LINES)]


def counted(summary: str) -> int:
    return sum(r[4] for r in log_report.summary_rows(summary, SINCE)
               if r[2] == "bug" and r[3] == KEY)


def remaining(log: str) -> int:
    return log.count("BUG: Ztrimkey: line ")


def torn_rows(summary: str) -> list[str]:
    lines = summary.splitlines()
    marks = [i for i, line in enumerate(lines) if line.startswith("#batch\t")]
    after = lines[marks[-1] + 1:] if marks else lines   # a first batch cut short
    return [line for line in after if line and not line.startswith("#")]


@unittest.skipIf(SKIP is not None, SKIP or "")
class TrimRecoveryTests(unittest.TestCase):
    def run_world(self, fault: str | None) -> tuple[str, str, str]:
        """Fill the log, let the next line trim it with `fault` armed once,
        recover if the game stopped, and trim again. Returns the summary,
        the log and the server's last toc.log text."""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="toc-trimfault-") as tmp:
            fault_file = Path(tmp) / "fault"
            env = {"TOC_LOG_TRIM_BYTES": str(LIMIT), "TOC_LOG_TRIM_RETRY_SECS": "0",
                   "TOC_FAULT_FILE": str(fault_file)}
            with LiveMud(extra_env=env) as mud:
                logs = mud.root / "log"
                if fault is not None:
                    fault_file.write_text(fault + "\n")
                with open(logs / "toc.log", "a", encoding="latin-1") as fp:
                    fp.write("\n".join(synthetic_lines()) + "\n")
                # Any line the game logs now asks for the trim.
                try:
                    with mud.connect(timeout=60) as client:
                        create_character(client, "Ztrimmer", "Ztrimpass1")
                        client.send("quit")
                        client.wait_closed()
                except Exception:       # the game stopped under the fault
                    pass
                if fault in ("logtrim-crash", "logtrim-torn"):
                    deadline = time.time() + 30
                    while time.time() < deadline and mud.proc.poll() is None:
                        time.sleep(0.2)
                    self.assertIsNotNone(mud.proc.poll(), "the fault stopped the game")
                    summary = (logs / "toc-summary.tsv").read_text(encoding="latin-1")
                    if fault == "logtrim-torn":
                        self.assertTrue(torn_rows(summary), "the fault left a batch cut short")
                    mud.restart()
                # More lines, so a trim runs again (or first, after a restart).
                with open(logs / "toc.log", "a", encoding="latin-1") as fp:
                    fp.write("\n".join(f"{STAMP} :: filler {n}" for n in range(1500)) + "\n")
                with mud.connect(timeout=60) as client:
                    client.send("")
                    time.sleep(1.0)
                mud._stop()
                return ((logs / "toc-summary.tsv").read_text(encoding="latin-1"),
                        (logs / "toc.log").read_text(encoding="latin-1", errors="replace"),
                        "")

    def assert_counted_once(self, summary: str, log: str) -> None:
        self.assertEqual(counted(summary) + remaining(log), LINES,
                         f"summed {counted(summary)}, still in the log {remaining(log)}")
        self.assertGreater(counted(summary), 0, "something was cut")
        self.assertEqual(torn_rows(summary), [], "no rows outside a closed batch")

    def test_a_clean_trim_counts_each_line_once(self) -> None:
        summary, log, _ = self.run_world(None)
        self.assert_counted_once(summary, log)

    def test_a_refused_replacement_is_not_counted_twice(self) -> None:
        summary, log, _ = self.run_world("logtrim-commit")
        self.assert_counted_once(summary, log)
        self.assertGreaterEqual(summary.count("#batch\ttoc\t"), 2, "the retry wrote its own batch")

    def test_a_crash_after_the_summary_is_not_counted_twice(self) -> None:
        summary, log, _ = self.run_world("logtrim-crash")
        self.assert_counted_once(summary, log)

    def test_a_batch_cut_short_is_dropped_and_written_again(self) -> None:
        summary, log, _ = self.run_world("logtrim-torn")
        self.assert_counted_once(summary, log)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SummaryKindsAndKeysTests(unittest.TestCase):
    def test_watch_events_are_not_commands_and_no_key_holds_a_host(self) -> None:
        lines = [
            f"{STAMP} :: Log Zwatch [4207]: look",
            f"{STAMP} :: Log Zwatch [4207]: (social) nod",
            f"{STAMP} :: Log Zwatch [4207]: (refused) xyzzy",
            f"{STAMP} :: Log Zwatch [4207]: affects",
            f"{STAMP} :: Log Zwatch: score",
            f"{STAMP} :: Log Zwatch [4208]: arrived (walked) from 4207",
            f"{STAMP} :: Log Zwatch [4208]: arrived (recall) from 4210",
            f"{STAMP} :: Log Zwatch [4208]: copper +120 loot",
            f"{STAMP} :: Log Zwatch [4208]: gold -3",
            f"{STAMP} :: Log Zwatch [4208]: received a sword (vnum 3001) from Zother",
            f"{STAMP} :: Log Zwatch [4208]: level 10 -> 11 (advance)",
            f"{STAMP} :: Log Zwatch [4208]: killed a rat",
            f"{STAMP} :: Log Zwatch [4208]: died to a dragon",
            f"{STAMP} :: Log Zwatch [4208]: affects off: titanic; max hp 10 -> 5",
            f"{STAMP} :: Log Zwatch [4208]: quest assigned: kill a rat (mob 1, level 2) in zfield.are, 20 minutes, ordinary",
            f"{STAMP} :: c-198-51-100-7.zhost.example.net input spamming!",
            f"{STAMP} :: 198.51.100.7 input overflow, discarding partial line.",
            f"{STAMP} :: [*****] BUG: Zfunc: cannot reach zhost.example.org from 2001:db8::7 as zed@zmail.example",
            f"{STAMP} :: [*****] BUG: Zfunc: bad path ../player/Zsecret in room 3001.",
            f"{STAMP} :: ANOMALY: kind 1 for zhost.example.net",
            f"{STAMP} :: Zgadget.example.com closed oddly",
        ]
        filler = [f"{STAMP} :: filler {n}" for n in range(1600)]
        env = {"TOC_LOG_TRIM_BYTES": str(LIMIT), "TOC_LOG_TRIM_RETRY_SECS": "0"}
        with LiveMud(extra_env=env) as mud:
            logs = mud.root / "log"
            with open(logs / "toc.log", "a", encoding="latin-1") as fp:
                fp.write("\n".join(lines + filler) + "\n")
            with mud.connect(timeout=60) as client:
                create_character(client, "Zkinds", "Zkindpass1")
                client.send("quit")
                client.wait_closed()
            summary = (logs / "toc-summary.tsv").read_text(encoding="latin-1")
        rows = {(r[2], r[3]): r[4] for r in log_report.summary_rows(summary, SINCE)
                if r[0] == "2026-11-21"}
        self.assertEqual(rows.get(("commands", "Zwatch")), 5, rows)
        self.assertEqual(rows.get(("watch", "arrived")), 2, rows)
        self.assertEqual(rows.get(("watch", "coin")), 2, rows)
        self.assertEqual(rows.get(("watch", "item")), 1, rows)
        self.assertEqual(rows.get(("watch", "affects")), 1, rows)
        self.assertEqual(rows.get(("level", "Zwatch")), 1, rows)
        self.assertEqual(rows.get(("kill", "Zwatch")), 1, rows)
        self.assertEqual(rows.get(("death", "Zwatch")), 1, rows)
        self.assertEqual(rows.get(("quest", "zfield.are")), 1, rows)    # an area file names no one
        self.assertEqual(rows.get(("guard", "-")), 2, rows)
        for word in ("zhost", "example", "zmail", "zed@", "Zsecret", "db8", "198", "Zgadget"):
            self.assertNotIn(word, summary, f"{word} reached the summary")
        self.assertIn(("bug", "Zfunc: cannot reach * from * as *"), rows)
        self.assertIn(("bug", "Zfunc: bad path * in room #."), rows)


if __name__ == "__main__":
    unittest.main()
