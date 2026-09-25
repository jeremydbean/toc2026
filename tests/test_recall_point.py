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

Only the skill uses the point. WORD OF RECALL, a scroll or potion of it,
the Recall Ring and the rescue of a link-dead player all go to the Temple
instead, and a curse does not stop them -- a curse silences your own
prayer, not somebody else's magic. Between them that is a second way
home that does not move and still answers, which is the reason to carry
a scroll.

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

                # And the trip itself lands there. Recall is a skill
                # roll, so this keeps asking from wherever it ends up
                # rather than walking further away between attempts.
                run(client, "north", 1.4)
                for _ in range(20):
                    arrived = run(client, "recall", 2.0)
                    if ("Oak Tree Square" in arrived
                            or "already there" in arrived):
                        break
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

    def test_the_spell_ignores_the_point_and_a_curse(self) -> None:
        """Two characters, because CURSE refuses to target the caster."""
        with LiveMud() as mud:
            # The victim casts WORD OF RECALL repeatedly too, so they
            # need the mana for it as much as the caster does.
            self.character(mud, "Zvictim", Levl=55, Room=OAK_SQUARE,
                           HpManaMove="20000 20000 20000 20000 20000 20000")
            # CURSE allows a saving throw and costs mana, so the caster
            # needs enough of it to keep trying. On a hundred points they
            # run dry after about ten casts, which is how this test failed
            # in CI while passing every time on a faster machine: the
            # saving throw went the other way a few times and the wizard
            # had nothing left to cast with.
            self.character(mud, "Zwizard", Levl=70, Room=OAK_SQUARE,
                           HpManaMove="20000 20000 20000 20000 20000 20000")

            with mud.connect(timeout=120) as wizard:
                login(wizard, "Zwizard", PASSWORD)
                run(wizard, "set skill self all 100", 2.5)

                with mud.connect(timeout=120) as victim:
                    login(victim, "Zvictim", PASSWORD)
                    run(wizard, "set skill Zvictim all 100", 2.5)

                    self.assertIn("Oak Tree Square",
                                  run(victim, "recall set", 1.6))

                    # Uncursed first: the spell ignores the chosen point.
                    run(wizard, "trans Zvictim 3700", 2.0)
                    for _ in range(10):
                        cast = run(victim, "cast 'word of recall'", 2.5)
                        if "Before the Altar" in cast:
                            break
                        run(wizard, "trans Zvictim 3700", 2.0)
                    self.assertIn("Before the Altar", cast, cast)
                    self.assertNotIn("Oak Tree Square", cast)

                    # The spell just moved the victim to the Temple and
                    # the wizard is still in the square; curse needs them
                    # in the same room.
                    run(wizard, "trans Zvictim", 2.0)
                    cast = ""
                    for _ in range(15):
                        cast += run(wizard, "cast curse Zvictim", 2.5)
                        if "curse" in run(victim, "affect", 1.6).lower():
                            break
                    self.assertNotIn("enough mana", cast, cast[-400:])
                    self.assertIn(
                        "curse", run(victim, "affect", 1.6).lower(),
                        "the curse never landed:\n" + cast[-600:])

                    run(wizard, "trans Zvictim 3700", 2.0)
                    refused = run(victim, "recall", 2.5)
                    self.assertIn("forsaken", refused, refused)

                    for _ in range(10):
                        through = run(victim, "cast 'word of recall'", 2.5)
                        if "Before the Altar" in through:
                            break
                        run(wizard, "trans Zvictim 3700", 2.0)
                    self.assertIn("Before the Altar", through, through)

                    victim.send("quit")
                    victim.wait_closed()
                wizard.send("quit")
                wizard.wait_closed()

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

    def test_the_skill_uses_the_point_the_player_chose(self) -> None:
        body = self.move.split("void do_recall(", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertNotIn("ROOM_VNUM_TEMPLE", body)
        self.assertIn("recall_travel( ch, recall_room( ch ), true )", body)

    def test_the_spell_always_goes_to_the_temple(self) -> None:
        """A second way home that does not move is the point of it."""
        body = self.magic.split("void spell_word_of_recall", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertIn("ROOM_VNUM_TEMPLE", body)
        self.assertNotIn("recall_room(", body)

    def test_the_spell_is_not_stopped_by_a_curse(self) -> None:
        """A curse silences your own prayer, not somebody else's magic."""
        body = self.magic.split("void spell_word_of_recall", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertNotIn("AFF_CURSE", body)
        # The place still decides: NO_RECALL is how an area keeps you in.
        self.assertIn("ROOM_NO_RECALL", body)

    def test_a_curse_stops_only_your_own_prayer(self) -> None:
        body = self.move.split("static void recall_travel(", 1)[1]
        body = body.split("\n/* Being sent home", 1)[0]
        self.assertIn("own_prayer && IS_AFFECTED(ch, AFF_CURSE)", body)
        self.assertIn("ROOM_NO_RECALL", body)

    def test_every_other_way_home_is_the_temple(self) -> None:
        """The Recall Ring, the link-dead rescue and the drunk who leaves."""
        for name in ("src/handler.c", "src/fight.c", "src/update.c"):
            source = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIn("recall_char_to_temple", source)
                self.assertNotIn("do_recall(ch,\"\")", source)
                self.assertNotIn("do_recall( victim, \"\" )", source)

        temple = self.move.split("void recall_char_to_temple(", 1)[1]
        temple = temple.split("\n}", 1)[0]
        self.assertIn("ROOM_VNUM_TEMPLE", temple)
        self.assertIn("false", temple)

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
