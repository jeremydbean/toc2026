"""CHANGES shows what is new, and stops showing an entry after three times.

Owner, 2026-10-04: the list had grown too long to read. CHANGES (src/changes.c)
shows the last two weeks' entries a character has been shown fewer than
three times, and counts each showing in the player file (ChangesSeen);
CHANGES ALL shows the whole history from area/changes.dat.

The live test does not assume any entry is still recent -- the window moves
with the clock -- only that what is shown stops being shown after three
showings, including across a relog.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PASSWORD = "Zchangepw1"
DATA = (ROOT / "area" / "changes.dat").read_text(encoding="latin-1")
ENTRIES = re.findall(r"(?m)^@ (\w+) (\d{4}-\d\d-\d\d)\n(.+)$", DATA)


class SourceTests(unittest.TestCase):
    def test_ids_are_unique_and_dated(self) -> None:
        ids = [entry_id for entry_id, _date, _first in ENTRIES]
        self.assertGreater(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)), "an id was reused")
        dates = [date for _id, date, _first in ENTRIES]
        self.assertEqual(dates, sorted(dates, reverse=True), "entries are newest first")

    def test_the_count_is_saved_under_its_letter(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_c = save.split("case 'C':", 1)[1].split("case 'D':", 1)[0]
        self.assertIn('"ChangesSeen"', case_c)
        self.assertIn('"ChangesSeen %s~', save)

    def test_the_file_is_loaded_at_boot_and_built(self) -> None:
        self.assertIn("changes_load( );", (ROOT / "src" / "db.c").read_text(encoding="latin-1"))
        self.assertIn("src/changes.c", (ROOT / "CMakeLists.txt").read_text(encoding="utf-8"))


def first_lines_shown(text: str) -> set[str]:
    return {first.strip() for _id, _date, first in ENTRIES if first.strip() in text}


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_an_entry_stops_showing_after_three_times(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zchanger", PASSWORD)
                client.send("scroll 0")
                client.drain(1.0)
                everything = client.command("changes all", settle=3.0)
                for _id, _date, first in ENTRIES[:3] + ENTRIES[-3:]:
                    self.assertIn(first.strip(), everything)
                first = client.command("changes", settle=3.0)
                shown = first_lines_shown(first)
                client.command("changes", settle=3.0)
                client.command("save", settle=1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            with mud.connect(timeout=120) as client:
                login(client, "Zchanger", PASSWORD)
                client.send("scroll 0")
                client.drain(1.0)
                third = client.command("changes", settle=3.0)
                fourth = client.command("changes", settle=3.0)
                again = client.command("changes all", settle=3.0)
                client.send("quit")
            if shown:
                self.assertEqual(shown, first_lines_shown(third),
                                 "the third showing should still show them")
            self.assertEqual(set(), first_lines_shown(fourth) & shown, fourth)
            self.assertIn("Nothing new", fourth)
            self.assertEqual(first_lines_shown(everything), first_lines_shown(again))


if __name__ == "__main__":
    unittest.main()
