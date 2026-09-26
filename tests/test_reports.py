"""Player reports get announced and can be read in the game.

BUG, TYPO and IDEA have always appended a line each to a flat file and
said nothing further. Nothing announced a report and nothing read one
back, so the only way to see what players filed was to open the files on
the host. On the live server those files had reached 135, 106 and 500
lines, most of it people typing a command on the same line as BUG.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zreport1"


def run(client, command: str, settle: float = 1.8) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def greet(client, name: str, settle: float = 2.5) -> str:
    """Everything the game said from connect through to the prompt.

    login() returns None and the banner arrives during it, so capturing
    its return value captures nothing -- which is how a working banner
    read as a missing one."""
    login(client, name, PASSWORD)
    client.drain(settle)
    return client.transcript


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReportsTests(unittest.TestCase):
    def staffed(self) -> LiveMud:
        """A server with a staff character who has seen nothing yet."""
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)

        with mud.connect(timeout=120) as client:
            create_character(client, "Zstaffer", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        # Mortal level, immortal trust: REPORTS is gated on trust, the
        # way interp.c gates every command.
        patch_player_file(mud, "Zstaffer", Levl=45, Tru=65)

        # The shipped area/ carries the live server's own backlog --
        # 739 lines of it -- and the harness copies the directory
        # wholesale. Start each test from an empty desk instead, in the
        # throwaway tree only.
        for name in ("bugs.txt", "typos.txt", "ideas.txt"):
            (mud.root / "area" / name).write_text("", encoding="latin-1")
        return mud

    def test_a_filed_bug_is_announced_at_the_next_login(self) -> None:
        mud = self.staffed()

        with mud.connect(timeout=120) as client:
            login(client, "Zstaffer", PASSWORD)
            run(client, "bug the west gate eats my gold", 1.5)
            run(client, "typo a heap of bones come to life", 1.5)
            # Reading them now means they are no longer new.
            run(client, "reports bugs", 1.8)
            run(client, "reports typos", 1.8)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        # Nothing new, so nothing shouted about.
        with mud.connect(timeout=120) as client:
            greeting = greet(client, "Zstaffer")
            self.assertNotIn("NEW PLAYER REPORTS", greeting, greeting[-600:])
            run(client, "idea let us donate to a god", 1.5)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        # One filed since, so the banner is back and names it.
        with mud.connect(timeout=120) as client:
            greeting = greet(client, "Zstaffer")
            self.assertIn("NEW PLAYER REPORTS", greeting, greeting[-900:])
            self.assertIn("idea", greeting, greeting[-900:])

    def test_reports_reads_back_what_was_filed(self) -> None:
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zstaffer", PASSWORD)
            run(client, "bug the portcullis is one way", 1.5)

            summary = run(client, "reports", 1.8)
            self.assertIn("bug", summary, summary)

            listing = run(client, "reports bugs", 2.0)
            self.assertIn("portcullis is one way", listing, listing)

    def test_clearing_sets_the_file_aside_rather_than_deleting_it(self) -> None:
        """These are the only record of what players told us, so a
        mistyped command must not destroy them."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zstaffer", PASSWORD)
            run(client, "bug something worth keeping", 1.5)

            said = run(client, "reports clear bugs", 2.0)
            self.assertIn("set aside", said, said)

            # Gone from the live file...
            self.assertIn("No bug reports", run(client, "reports bugs", 1.8))

        # ...but still on disk under a new name.
        area = mud.root / "area"
        archived = sorted(area.glob("bugs.txt.*"))
        self.assertTrue(archived, "the cleared reports were not kept")
        kept = archived[-1].read_text(encoding="latin-1")
        self.assertIn("something worth keeping", kept)

    def test_clearing_needs_to_be_told_which(self) -> None:
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zstaffer", PASSWORD)
            self.assertIn("which", run(client, "reports clear", 1.8).lower())

    def test_a_plain_player_is_told_about_an_unread_note(self) -> None:
        """Nothing announced a waiting note before this."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            create_character(client, "Zmailman", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zstaffer", PASSWORD)
            run(client, "note to Zmailman", 1.2)
            run(client, "note subject a welcome", 1.2)
            run(client, "note + the gate sticks, mind it", 1.2)
            run(client, "note send", 2.0)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            greeting = greet(client, "Zmailman")
            self.assertIn("unread note", greeting, greeting[-900:])
            self.assertIn("NOTE READ", greeting, greeting[-900:])
            # A player is not shown the staff backlog.
            self.assertNotIn("NEW PLAYER REPORTS", greeting, greeting[-900:])

    def test_an_ordinary_player_cannot_read_them(self) -> None:
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            create_character(client, "Zmortalz", PASSWORD)
            run(client, "bug the door sticks", 1.5)
            # No trust, so the command is not theirs to run.
            said = run(client, "reports", 1.8)
            self.assertNotIn("filed", said, said)


class ReportSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comm = (ROOT / "src" / "act_comm.c").read_text(encoding="utf-8")
        cls.interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")

    def test_the_read_marker_is_saved_under_its_own_letter(self) -> None:
        """fread_char dispatches on the first letter of the key. A key in
        the wrong case never matches, and the loader then desyncs on the
        values it did not consume -- which once hung the login prompt."""
        after_r = self.save.split("\tcase 'R':", 1)[1]
        after_r = after_r.split("\tcase 'S':", 1)[0]
        self.assertIn('"ReportsSeen"', after_r)
        self.assertIn("ReportsSeen %d %d %d", self.save)

    def test_clearing_renames_rather_than_unlinks(self) -> None:
        body = self.comm.split("void do_reports(", 1)[1]
        body = body.split("\nvoid do_bug(", 1)[0]
        self.assertIn("rename(", body)
        self.assertNotIn("unlink(", body)
        self.assertNotIn("remove(", body)

    def test_it_is_gated_on_trust_like_the_command_table(self) -> None:
        row = [line for line in self.interp.splitlines()
               if '"reports"' in line]
        self.assertEqual(len(row), 1, row)
        notice = self.comm.split("void report_login_notice(", 1)[1]
        notice = notice.split("\n}", 1)[0]
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", notice)
        self.assertNotIn("IS_IMMORTAL", notice)

    def test_everyone_is_told_about_their_own_notes(self) -> None:
        """The note count is above the staff-only return, so it reaches
        ordinary players too."""
        notice = self.comm.split("void report_login_notice(", 1)[1]
        notice = notice.split("\n}", 1)[0]
        self.assertLess(notice.index("unread_note_count"),
                        notice.index("IS_TRUSTED"))


if __name__ == "__main__":
    unittest.main()
