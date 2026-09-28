"""Sharing a stash between two of your own characters.

Proving you can log in as both is the proof of ownership. It is
stronger than a password typed into a command, which on plain Telnet
would cross the wire in clear, land in the log and in the player's own
scrollback, and answer guesses at MUD speed.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zlink123"
ALTAR = 4208


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashLinkTests(unittest.TestCase):
    def pair(self) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        for name in ("Zalpha", "Zbeta"):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, name, Levl=60, Tru=70, Room=ALTAR)
        return mud

    def test_one_side_alone_shares_nothing(self) -> None:
        """The handshake is the point: an unanswered offer is not a
        link, and it says so rather than looking broken."""
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            said = run(client, "stash link Zbeta", 2.0)
            self.assertIn("Nothing is shared", said, said)
            self.assertIn("Zbeta", said, said)

            # Listed, but marked as not yet answered.
            self.assertIn("waiting", run(client, "stash", 1.8))
            # And reaching it is refused.
            self.assertIn("do not share",
                          run(client, "stash of Zbeta", 1.8))

    def test_both_sides_make_it_live(self) -> None:
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            run(client, "load obj 3032", 1.4)
            run(client, "stash put bag", 1.6)
            run(client, "stash link Zbeta", 1.8)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zbeta", PASSWORD)
            said = run(client, "stash link Zalpha", 2.2)
            self.assertIn("now share a stash", said, said)

            # Zalpha is offline, so this reads their saved file.
            listing = run(client, "stash of Zalpha", 2.2)
            self.assertIn("bag", listing, listing)

    def test_taking_from_a_linked_stash_moves_it(self) -> None:
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            run(client, "load obj 3032", 1.4)
            run(client, "stash put bag", 1.6)
            run(client, "stash link Zbeta", 1.8)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zbeta", PASSWORD)
            run(client, "stash link Zalpha", 2.0)
            self.assertIn("out of their stash",
                          run(client, "stash take Zalpha bag", 2.4))
            self.assertIn("bag", run(client, "inventory", 1.8))
            # Gone from theirs, not copied.
            self.assertNotIn("bag", run(client, "stash of Zalpha", 2.2))

    def test_unlinking_closes_the_door_from_either_side(self) -> None:
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            run(client, "stash link Zbeta", 1.8)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zbeta", PASSWORD)
            run(client, "stash link Zalpha", 2.0)
            self.assertIn("no longer share",
                          run(client, "stash unlink Zalpha", 2.0))
            self.assertIn("do not share",
                          run(client, "stash of Zalpha", 2.0))

    def test_you_cannot_link_to_yourself(self) -> None:
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            self.assertIn("own stash", run(client, "stash link Zalpha", 1.8))

    def test_score_shows_the_stash_and_who_shares_it(self) -> None:
        mud = self.pair()
        with mud.connect(timeout=120) as client:
            login(client, "Zalpha", PASSWORD)
            run(client, "stash link Zbeta", 1.8)
            sheet = run(client, "score", 2.2)
            self.assertIn("Stash:", sheet, sheet[-700:])
            self.assertIn("Zbeta", sheet, sheet[-700:])


class StashLinkSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")

    def test_no_password_is_ever_taken(self) -> None:
        """The handshake exists so that nothing secret is typed as a
        command argument on a plain Telnet connection."""
        body = self.obj.split("void do_stash(", 1)[1]
        body = body.split("\nvoid do_donate(", 1)[0]
        for word in ("pwd", "password", "crypt"):
            with self.subTest(word=word):
                self.assertNotIn(word, body.lower())

    def test_a_link_needs_both_halves(self) -> None:
        body = self.obj.split("static bool stash_link_is_mutual(", 1)[1]
        body = body.split("\n}", 1)[0]
        # Their list must name us, not merely ours name them.
        self.assertIn("stash_is_linked( other, ch->name )", body)
        self.assertIn("is_name( ch->name, theirs )", body)

    def test_a_cross_character_move_saves_both_files(self) -> None:
        """The item left one character and joined another. A crash
        between the two writes would copy it."""
        body = self.obj.split('if ( !str_prefix( arg, "of" )', 1)[1]
        body = body.split('if ( !str_prefix( arg, "buy" )', 1)[0]
        self.assertIn("save_char_obj( owner )", body)
        self.assertIn("save_char_obj( ch )", body)


if __name__ == "__main__":
    unittest.main()
