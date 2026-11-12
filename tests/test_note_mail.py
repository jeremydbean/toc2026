"""The note board as mail: reply, forward, search, unread, catchup.

Answering a note used to mean reading it, remembering who sent it and
what it was called, then typing `note to', `note subject Re: ...' and
hoping you had the name right.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Znotes12"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def write_note(client, to: str, subject: str, *lines: str) -> None:
    run(client, "note to " + to, 1.2)
    run(client, "note subject " + subject, 1.2)
    for line in lines:
        run(client, "note + " + line, 1.0)
    run(client, "note send", 1.8)


@unittest.skipIf(SKIP is not None, SKIP or "")
class NoteMailTests(unittest.TestCase):
    def two_players(self) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        for name in ("Zsender", "Zreader"):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, name, Levl=30, Room=TEMPLE)
        return mud

    def test_reply_addresses_itself(self) -> None:
        mud = self.two_players()

        with mud.connect(timeout=120) as client:
            login(client, "Zsender", PASSWORD)
            write_note(client, "Zreader", "the west gate",
                       "It sticks when you open it.")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            listing = run(client, "note list", 2.0)
            self.assertIn("the west gate", listing, listing)

            said = run(client, "note reply 1", 2.0)
            self.assertIn("Zsender", said, said)
            self.assertIn("Re: the west gate", said, said)

            # The draft really is addressed, not merely announced.
            shown = run(client, "note show", 2.0)
            self.assertIn("Zsender", shown, shown)
            self.assertIn("Re: the west gate", shown, shown)

    def test_a_reply_to_a_reply_does_not_stack_re(self) -> None:
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zsender", PASSWORD)
            write_note(client, "Zreader", "Re: already answered", "quite.")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            said = run(client, "note reply 1", 2.0)
            self.assertIn("Re: already answered", said, said)
            self.assertNotIn("Re: Re:", said, said)

    def test_forward_carries_the_original_and_says_whose_it_was(self) -> None:
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zsender", PASSWORD)
            write_note(client, "Zreader", "a secret", "the password is swordfish")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            said = run(client, "note forward 1 Zsender", 2.0)
            self.assertIn("Fwd: a secret", said, said)

            shown = run(client, "note show", 2.0)
            self.assertIn("swordfish", shown, shown)
            # Marked as somebody else's words rather than silently yours.
            self.assertIn("forwarded from Zsender", shown, shown)

    def test_unread_and_catchup(self) -> None:
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zsender", PASSWORD)
            write_note(client, "Zreader", "first one", "hello")
            write_note(client, "Zreader", "second one", "hello again")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            waiting = run(client, "note unread", 2.0)
            self.assertIn("first one", waiting, waiting)
            self.assertIn("second one", waiting, waiting)

            said = run(client, "note catchup", 2.0)
            self.assertIn("2 notes marked", said, said)

            self.assertIn("read everything", run(client, "note unread", 2.0))

    def test_search_finds_by_body_and_keeps_the_list_numbering(self) -> None:
        """A number read off a filtered list has to mean the same thing
        to `note read', or searching then reading opens the wrong one."""
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zsender", PASSWORD)
            write_note(client, "Zreader", "alpha", "nothing of interest")
            write_note(client, "Zreader", "beta", "the portcullis is stuck")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            found = run(client, "note search portcullis", 2.0)
            self.assertIn("beta", found, found)
            self.assertNotIn("alpha", found, found)
            # It is note 2 in the full list, and must still say 2.
            self.assertIn("  2)", found, found)

            opened = run(client, "note read 2", 2.0)
            self.assertIn("portcullis", opened, opened)

    def test_search_needs_something_to_look_for(self) -> None:
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            self.assertIn("for what", run(client, "note search", 1.6).lower())

    def test_reply_to_a_number_that_is_not_there(self) -> None:
        mud = self.two_players()
        with mud.connect(timeout=120) as client:
            login(client, "Zreader", PASSWORD)
            self.assertIn("no note", run(client, "note reply 99", 1.6).lower())
            self.assertIn("syntax", run(client, "note reply", 1.6).lower())


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmortalMailTests(unittest.TestCase):
    def test_mail_to_the_immortals_reaches_immortals_by_level(self) -> None:
        """Staff are immortals by level (owner, 2026-11-12: "staff-only
        should ONLY apply to actual immortals level 60+"). A level 60
        receives mail to the immortals; a level 45 with trust 65 -- who
        may run staff commands -- does not, any more than a mortal."""
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)

        for name in ("Zwriter", "Zimmortal", "Zbuilder", "Zmortal"):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())

        patch_player_file(mud, "Zwriter", Levl=70, Tru=70, Room=TEMPLE)
        patch_player_file(mud, "Zimmortal", Levl=60, Room=TEMPLE)
        # Mortal level, immortal trust: the disagreement is the point.
        patch_player_file(mud, "Zbuilder", Levl=45, Tru=65, Room=TEMPLE)
        patch_player_file(mud, "Zmortal", Levl=45, Room=TEMPLE)

        with mud.connect(timeout=120) as client:
            login(client, "Zwriter", PASSWORD)
            write_note(client, "immortal", "staff only", "for the gods")
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zimmortal", PASSWORD)
            self.assertIn("staff only", run(client, "note list", 2.0))

        # A mortal given trust does not see it...
        with mud.connect(timeout=120) as client:
            login(client, "Zbuilder", PASSWORD)
            self.assertNotIn("staff only", run(client, "note list", 2.0))

        # ...and an ordinary player still does not.
        with mud.connect(timeout=120) as client:
            login(client, "Zmortal", PASSWORD)
            self.assertNotIn("staff only", run(client, "note list", 2.0))


class NoteSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comm = (ROOT / "src" / "act_comm.c").read_text(encoding="utf-8")

    def test_one_lister_backs_all_three_views(self) -> None:
        """List, unread and search must number identically."""
        self.assertEqual(3, self.comm.count("note_list_filtered( ch,"))

    def test_the_number_shown_is_the_position_in_the_full_list(self) -> None:
        body = self.comm.split("static void note_list_filtered(", 1)[1]
        body = body.split("\n}", 1)[0]
        # Counted before the filter drops anything.
        self.assertLess(body.index("number++"), body.index("filter =="))

    def test_the_note_system_asks_staff_by_level(self) -> None:
        """Both gates: who receives staff mail, and who may remove a
        note that is not their own -- staff by level, through is_staff
        (owner, 2026-11-12: "staff-only should ONLY apply to actual
        immortals level 60+"), never a mortal's trust."""
        body = self.comm.split("bool is_note_to(", 1)[1].split(chr(10) + "}", 1)[0]
        self.assertIn("is_staff( ch )", body)
        self.assertNotIn("IS_TRUSTED", body)
        self.assertNotIn("get_trust", body)
        remove = self.comm.split("Your own note, one addressed to you by name", 1)[1][:300]
        self.assertIn("!is_staff( ch )", remove)

    def test_search_is_not_quadratic(self) -> None:
        body = self.comm.split("static bool note_contains(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertEqual(1, body.count("strlen( haystack )"))


if __name__ == "__main__":
    unittest.main()
