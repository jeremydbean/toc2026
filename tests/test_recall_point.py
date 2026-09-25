"""A recall point a player can move, and put back.

RECALL used to be a one-way trip to the Temple for everybody. It now goes
wherever the character last set it, which makes it a standing shortcut to
one room -- a hunting ground, a questmaster, a shop. The wait is on
*moving* the point rather than on using it: recall stays free and
repeatable, and what the wait stops is changing where it lands in the
middle of something, which is the version that would matter in a fight.

RECALL DEFAULT is deliberately exempt from the wait. It is the way back
from a choice that turned out badly, and a character who cannot reach
their own recall point has no other way to reset it.

These run against a real server in a throwaway tree.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "Zrecall1"

OAK_SQUARE = 2401          # the start room: ordinary, and recallable
OAK_NORTH = 2402           # one step away
TEMPLE = 4207              # ROOM_VNUM_TEMPLE, the default
HYRULE_DUNGEON = 30400     # ROOM_NO_RECALL, so it cannot be a home


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class RecallPointTests(unittest.TestCase):
    def character(self, mud: LiveMud, name: str, **fields: object) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed(), "character did not leave")
        patch_player_file(mud, name, **fields)

    def test_a_player_can_move_their_recall_and_put_it_back(self) -> None:
        with LiveMud() as mud:
            self.character(mud, "Zhomer", Levl=40, Room=OAK_SQUARE)

            with mud.connect(timeout=120) as client:
                login(client, "Zhomer", PASSWORD)

                fresh = run(client, "recall where", 1.5)
                self.assertIn("where it started", fresh, fresh)
                self.assertIn("whenever you like", fresh)

                self.assertIn(
                    "Oak Tree Square", run(client, "recall set", 1.6))

                moved = run(client, "recall where", 1.5)
                self.assertIn("Oak Tree Square", moved, moved)
                self.assertIn("30 minutes", moved)

                # Setting the same room again is a no-op, not a wasted
                # half hour.
                self.assertIn(
                    "already set here", run(client, "recall set", 1.5))

                # And the trip itself lands there.
                run(client, "north", 1.4)
                for _ in range(8):          # recall is a skill, and can fail
                    arrived = run(client, "recall", 2.0)
                    if "Oak Tree Square" in arrived:
                        break
                    run(client, "north", 1.4)
                self.assertIn("Oak Tree Square", arrived, arrived)

                back = run(client, "recall default", 1.5)
                self.assertIn("back to the Temple", back, back)
                self.assertIn(
                    "where it started", run(client, "recall where", 1.5))

    def test_going_back_to_the_temple_is_never_blocked(self) -> None:
        """The wait is on choosing a new home, not on giving one up."""
        with LiveMud() as mud:
            self.character(mud, "Zpilgrim", Levl=40, Room=OAK_SQUARE)

            with mud.connect(timeout=120) as client:
                login(client, "Zpilgrim", PASSWORD)
                run(client, "recall set", 1.6)

                # Straight after setting, so the wait is certainly running.
                waiting = run(client, "recall where", 1.5)
                self.assertIn("30 minutes", waiting)

                self.assertIn(
                    "back to the Temple",
                    run(client, "recall default", 1.5),
                )
                # ...and the wait is still running, so this is not a way
                # to move the point twice.
                self.assertIn("30 minutes", run(client, "recall where", 1.5))

    def test_a_forsaken_room_cannot_be_a_home(self) -> None:
        with LiveMud() as mud:
            self.character(mud, "Zlost", Levl=40, Room=HYRULE_DUNGEON)

            with mud.connect(timeout=120) as client:
                login(client, "Zlost", PASSWORD)
                refused = run(client, "recall set", 1.6)
                self.assertIn("will not answer", refused, refused)
                self.assertIn(
                    "where it started", run(client, "recall where", 1.5))

    def test_the_point_survives_logging_out(self) -> None:
        with LiveMud() as mud:
            self.character(mud, "Zkeeper", Levl=40, Room=OAK_SQUARE)

            with mud.connect(timeout=120) as client:
                login(client, "Zkeeper", PASSWORD)
                self.assertIn(
                    "Oak Tree Square", run(client, "recall set", 1.6))
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            saved = (mud.player_dir / "Zkeeper").read_text(encoding="latin-1")
            self.assertIn("RecallRoom %d" % OAK_SQUARE, saved)

            # The server can still be holding the old descriptor, and a
            # reconnect into that takes a different path through nanny.
            time.sleep(3)
            with mud.connect(timeout=120) as client:
                login(client, "Zkeeper", PASSWORD)
                self.assertIn(
                    "Oak Tree Square", run(client, "recall where", 1.5))

    def test_an_unrecognised_word_still_recalls(self) -> None:
        """RECALL is what people type when something is going badly. A
        typo must not be the thing that stops it."""
        with LiveMud() as mud:
            self.character(mud, "Ztypo", Levl=40, Room=OAK_NORTH)

            with mud.connect(timeout=120) as client:
                login(client, "Ztypo", PASSWORD)
                for _ in range(8):
                    said = run(client, "recall sword", 2.0)
                    if "Before the Altar" in said:
                        break
                    run(client, "north", 1.4)
                self.assertIn("Before the Altar", said, said)


class RecallSourceTests(unittest.TestCase):
    """Things a live run cannot show, and the help that describes them."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.move = (ROOT / "src" / "act_move.c").read_text(encoding="utf-8")
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.commands = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1")
        cls.skills = (ROOT / "area" / "skills.are").read_text(
            encoding="latin-1")

    def test_recall_no_longer_hardcodes_the_temple(self) -> None:
        body = self.move.split("void do_recall(", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertNotIn("ROOM_VNUM_TEMPLE", body)
        self.assertIn("recall_room( ch )", body)

    def test_the_spell_goes_where_the_skill_goes(self) -> None:
        body = self.magic.split("void spell_word_of_recall", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertIn("recall_room( victim )", body)
        self.assertNotIn("ROOM_VNUM_TEMPLE", body)

    def test_a_point_is_rechecked_rather_than_trusted(self) -> None:
        """An area edit can take the room away or make it no-recall after
        a character has saved it."""
        helper = self.move.split("ROOM_INDEX_DATA *recall_room(", 1)[1]
        helper = helper.split("\n}", 1)[0]
        self.assertIn("room_allows_recall_point( home )", helper)
        self.assertIn("ROOM_VNUM_TEMPLE", helper)

    def test_the_help_describes_all_three_words(self) -> None:
        for source, name in ((self.commands, "commands.are"),
                             (self.skills, "skills.are")):
            entry = source.split("\n0 RECALL /~\n", 1)[1].split("\n~\n", 1)[0]
            for word in ("RECALL SET", "RECALL DEFAULT", "RECALL WHERE",
                         "30 minutes"):
                with self.subTest(file=name, word=word):
                    self.assertIn(word, entry)

    def test_help_changes_lists_changes(self) -> None:
        """It used to promise a log of recent updates and then not have
        one."""
        entry = self.commands.split("\n0 CHANGES~\n", 1)[1].split("\n~\n", 1)[0]
        self.assertGreater(len(entry.splitlines()), 20, entry)
        self.assertRegex(entry, r"\d{1,2}[- ]?\w* ?\w+ 20\d\d")
        for topic in ("RECALL", "AQUEST", "REMORT", "REPAIR"):
            with self.subTest(topic=topic):
                self.assertIn(topic, entry)


if __name__ == "__main__":
    unittest.main()
