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

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PASSWORD = "Zchangepw1"
DATA = (ROOT / "area" / "changes.dat").read_text(encoding="latin-1")
ENTRIES = re.findall(r"(?m)^@ (\w+) (\d{4}-\d\d-\d\d)\n(.+)$", DATA)
# Changes only staff can use: "@ <id> <date> staff", shown to staff alone
# (owner, 2026-10-23).
STAFF = re.findall(r"(?m)^@ (\w+) (\d{4}-\d\d-\d\d) staff\n(.+)$", DATA)


class SourceTests(unittest.TestCase):
    def test_ids_are_unique_and_dated(self) -> None:
        ids = [entry_id for entry_id, _date, _first in ENTRIES + STAFF]
        self.assertGreater(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)), "an id was reused")
        # Every header is one of the two shapes: a malformed one is
        # read as an entry of its own or dropped with what follows it.
        headers = re.findall(r"(?m)^@.*$", DATA)
        self.assertEqual(len(headers), len(ids), headers)
        dates = sorted(((date, entry_id) for entry_id, date, _first in ENTRIES + STAFF),
                       key=lambda pair: DATA.index("@ " + pair[1] + " "))
        dates = [date for date, _id in dates]
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

    def test_staff_changes_are_shown_to_staff_alone(self) -> None:
        self.assertTrue(STAFF)
        firsts = [first.strip() for _id, _date, first in STAFF]
        with LiveMud() as mud:
            for name in ("Zmortalchg", "Zstaffchg"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zstaffchg", Levl=70)
            with mud.connect(timeout=120) as mortal, mud.connect(timeout=120) as imm:
                login(mortal, "Zmortalchg", PASSWORD)
                login(imm, "Zstaffchg", PASSWORD)
                for client in (mortal, imm):
                    client.send("scroll 0")
                    client.drain(1.0)
                said = mortal.command("changes all", settle=3.0)
                said += mortal.command("changes", settle=3.0)
                for first in firsts:
                    self.assertNotIn(first, said)
                self.assertNotIn("staff only", said)
                self.assertIn(ENTRIES[0][2].strip(), said)
                seen = imm.command("changes all", settle=3.0)
                for first in firsts:
                    self.assertIn(first, seen)
                self.assertIn("(staff only)", seen)

    def test_a_list_past_the_buffer_is_neither_a_crash_nor_a_disconnect(self) -> None:
        """2026-10-21: CHANGES ALL grew past 32,704 bytes. With paging on
        the pager asked alloc_mem for one block that big, and alloc_mem
        aborts the game; with paging off write_to_buffer closed the
        connection at 32,000. Neither may happen for any long output."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zreader", PASSWORD)
                client.drain(1.0)
                client.send("scroll 40")
                client.drain(1.0)
                said = client.command("changes all", settle=3.0)
                self.assertIn(ENTRIES[0][2].strip(), said)
                self.assertIn(ENTRIES[-1][2].strip(), said, "the oldest arrives too")
                client.send("scroll 0")
                client.drain(1.0)
                said = client.command("changes all", settle=3.0)
                self.assertIn(ENTRIES[-1][2].strip(), said)
                self.assertIn("You say", client.command("say still here", settle=1.5))
            self.assertIsNone(mud.proc.poll(), "the game is still running")


if __name__ == "__main__":
    unittest.main()
