"""BUG, TYPO and IDEA say "logged" only when the report is stored
(review, 2026-11-27).

They acknowledged success whatever happened: append_file skipped an empty
line without a word and reported a file it could not open only as "Could
not open the file!", and write and close errors went unnoticed; the play
journal holds an empty BUG. A blank report is refused with the syntax, a
report the disk would not take says so, and one longer than the journal's
field is marked there as an excerpt -- the report's own file has it whole.
Synthetic characters; no player names or report texts in output.
"""
from __future__ import annotations

import pathlib
import tempfile
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zreportpw1"
TEMPLE = 4207


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="latin-1") if path.exists() else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReportCommandTests(unittest.TestCase):
    def test_blank_long_and_a_failed_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fault = pathlib.Path(tmp) / "fault"
            with LiveMud(extra_env={"TOC_FAULT_FILE": str(fault)}) as mud:
                make(mud, "Zreporter", Levl=10, Room=TEMPLE)
                bugs = mud.root / "area" / "bugs.txt"
                journal = mud.root / "log" / "play.tsv"
                with mud.connect(timeout=120) as player:
                    login(player, "Zreporter", PW)
                    before = read(bugs)
                    # Blank: the syntax, nothing stored, no "logged".
                    for blank in ("bug", "bug    ", "typo", "idea"):
                        said = player.sync(blank)
                        self.assertIn("Syntax:", said, blank)
                        self.assertNotIn("logged", said, blank)
                    self.assertEqual(read(bugs), before, "a blank report writes nothing")

                    # Long: stored whole; the journal's copy says it is an excerpt.
                    long_text = "synthetic report " + "x" * 300 + " end"
                    self.assertIn("Bug logged", player.sync("bug " + long_text))
                    self.assertIn(long_text, read(bugs), "the report's file has all of it")

                    # The disk will not take it: said, and not "logged".
                    fault.write_text("report-file\n")
                    said = player.sync("bug a second synthetic report")
                    self.assertIn("could not be saved", said)
                    self.assertNotIn("logged", said)
                    self.assertNotIn("a second synthetic report", read(bugs))
                    # It works again once the disk does.
                    self.assertIn("Typo logged", player.sync("typo synthetic typo"))
                    self.assertIn("Idea logged", player.sync("idea synthetic idea"))
                # The journal's report rows (a command's own row, with its
                # reply, is a "cmd" row and is expected for a blank one too).
                rows = [r for r in read(journal).splitlines() if "\treport\t" in r]
        excerpt = [r for r in rows if "synthetic report" in r]
        self.assertTrue(excerpt, "the long report reached the journal")
        self.assertIn("[excerpt: REPORTS has it whole]", excerpt[0])
        self.assertFalse([r for r in rows if "\tbug\t\t" in r], "no empty BUG report in the journal")
        self.assertEqual(len(rows), 3, "the long bug, the typo and the idea: nothing else")


class ReportSourceTests(unittest.TestCase):
    def test_every_caller_hears_whether_it_was_stored(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        body = db[db.index("bool append_file( CHAR_DATA *ch, char *file, char *str )"):]
        body = body[:body.index("\n}\n")]
        for check in ("fflush( fp )", "ferror( fp )", "fclose( fp ) == 0"):
            self.assertIn(check, body)
        self.assertNotIn("send_to_char", body, "the callers speak, not the helper")
        oracle = (ROOT / "src" / "oracle.c").read_text(encoding="latin-1")
        self.assertIn("if ( !append_file( ch, BUG_FILE, report ) )", oracle)


if __name__ == "__main__":
    unittest.main()
