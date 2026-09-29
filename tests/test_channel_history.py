"""HISTORY: read back what was said on a channel.

A player asked for this because their Mudlet chat capture stopped part
way through a session and there was no way to get the lines back. The
game keeps the last few of every public channel in memory and hands
them over on request.

Two rules matter more than the rest and are tested live:

- a channel you may not hear is a channel you may not read back, so a
  mortal cannot pull immtalk out of the history;
- tells never go into the shared rings. Each character keeps their own,
  so nobody can read somebody else's.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "Zhist123"


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ChannelHistory(unittest.TestCase):
    def test_a_channel_can_be_read_back(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Histly", PASSWORD)

                run(client, "gossip first thing said", 1.6)
                run(client, "gossip second thing said", 1.6)

                said = run(client, "history gossip", 2.0)
                self.assertIn("first thing said", said, said)
                self.assertIn("second thing said", said, said)
                # Oldest first, so somebody reading down sees the order
                # the conversation actually happened in.
                self.assertLess(
                    said.index("first thing"), said.index("second thing"),
                    said,
                )

    def test_history_on_its_own_merges_the_channels(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Mergely", PASSWORD)

                run(client, "gossip a gossip line", 1.6)
                run(client, "question a question line", 1.6)

                said = run(client, "history", 2.2)
                self.assertIn("a gossip line", said, said)
                self.assertIn("a question line", said, said)

                # And a count narrows it to the most recent.
                said = run(client, "history 1", 2.0)
                self.assertIn("a question line", said, said)
                self.assertNotIn("a gossip line", said, said)

    def test_a_mortal_cannot_read_the_staff_channels(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Nosely", PASSWORD)
                said = run(client, "history immtalk", 2.0)
                self.assertNotIn("[", said.split("\n")[0], said)
                self.assertTrue(
                    "not yours to read" in said or "No channel" in said,
                    said,
                )

                # It is not offered in the listing either.
                listing = run(client, "history list", 2.0)
                self.assertNotIn("immtalk", listing, listing)
                self.assertIn("gossip", listing, listing)

    def test_tells_are_private_to_the_two_who_spoke(self) -> None:
        with LiveMud() as mud:
            for name in ("Talkly", "Hearly", "Nibbly"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            with mud.connect(timeout=120) as one:
                login(one, "Talkly", PASSWORD)
                with mud.connect(timeout=120) as two:
                    login(two, "Hearly", PASSWORD)

                    run(one, "tell Hearly a private matter", 1.8)

                    self.assertIn(
                        "a private matter", run(one, "history tell", 2.0))
                    self.assertIn(
                        "a private matter", run(two, "history tell", 2.0))

                    # And it is in neither of their channel histories.
                    self.assertNotIn(
                        "a private matter", run(one, "history gossip", 2.0))

                with mud.connect(timeout=120) as three:
                    login(three, "Nibbly", PASSWORD)
                    said = run(three, "history", 2.2)
                    self.assertNotIn("a private matter", said, said)
                    said = run(three, "history tell", 2.0)
                    self.assertNotIn("a private matter", said, said)


@unittest.skipIf(SKIP is not None, SKIP or "")
class MissedWhileAway(unittest.TestCase):
    """Nothing is pushed at a player on arrival; HISTORY marks the gap."""

    def test_login_says_nothing_but_history_shows_the_line(self) -> None:
        with LiveMud() as mud:
            for name in ("Awayly", "Chatly"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            with mud.connect(timeout=120) as talker:
                login(talker, "Chatly", PASSWORD)
                run(talker, "gossip something while you were out", 1.8)

                with mud.connect(timeout=120) as back:
                    mark = len(back.transcript)
                    login(back, "Awayly", PASSWORD)
                    back.drain(2.0)
                    arrival = back.transcript[mark:]

                    # Quiet on arrival: they asked for that.
                    self.assertNotIn("while you were away", arrival.lower(),
                                     arrival)
                    self.assertNotIn("something while you were out",
                                     arrival, arrival)

                    # But it is there the moment they ask.
                    said = run(back, "history", 2.2)
                    self.assertIn("something while you were out", said, said)
                    self.assertIn("while you were away", said.lower(), said)


class HistorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comm = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")
        cls.interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        cls.db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")

    def test_every_live_channel_records(self) -> None:
        """A channel that sends but does not record is a silent hole."""
        for channel in ("gossip", "shout", "yell", "question", "answer",
                        "music", "immtalk", "godtalk", "hero", "leveling"):
            self.assertIn(
                '"%s"' % channel, self.comm,
                "%s is not named in the history wiring" % channel,
            )
        # The definition, the six channels that walk the descriptor list
        # themselves, and the one call inside channel_say that covers the
        # other four. The prototype lives in merc.h.
        self.assertEqual(
            self.comm.count("channel_history_add("), 1 + 6 + 1,
            "a channel was added or dropped without its recording",
        )
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("void    channel_history_add", merc)

    def test_the_command_is_registered(self) -> None:
        self.assertIn('{ "history",       do_history,', self.interp)

    def test_a_tell_history_is_let_go_of_with_the_character(self) -> None:
        """MAX pointers per player, and nothing else frees them."""
        body = self.db.split("void free_char(")[1].split(chr(10) + "}")[0]
        self.assertIn("ch->pcdata->tell_history[i]", body)
        self.assertIn("free_string( ch->pcdata->tell_history[i] );", body)

    def test_the_ring_lets_go_of_the_line_it_replaces(self) -> None:
        body = self.comm.split("void channel_history_add(")[1]
        body = body.split(chr(10) + "}")[0]
        self.assertIn("free_string( line->name );", body)
        self.assertIn("free_string( line->text );", body)


class RecallPointSourceTests(unittest.TestCase):
    """A recall point is refused by flags, not by who is standing there."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")

    def body(self) -> str:
        return self.move.split("bool room_allows_recall_point(")[1].split(
            chr(10) + "}")[0]

    def test_an_occupancy_count_no_longer_refuses_a_recall_point(self) -> None:
        """The quest giver's room is ROOM_PRIVATE and holds a questmaster.

        With the mob counted that was already two, so a player standing
        there was told the gods would not hear them. And because the
        stored vnum is rechecked on every use, a point set in a quiet
        moment would have reverted to the Temple later.
        """
        # The comment above it explains the change; the test is about
        # what the function returns.
        returned = self.body().rsplit("return ", 1)[1]
        self.assertNotIn("room_is_private", returned)

    def test_the_permanent_refusals_are_all_still_there(self) -> None:
        body = self.body()
        for flag in ("ROOM_NO_RECALL", "ROOM_JAIL", "ROOM_DT",
                     "ROOM_IMP_ONLY", "ROOM_GODS_ONLY"):
            self.assertIn(flag, body, "%s stopped refusing a recall point" % flag)

    def test_jail_in_particular(self) -> None:
        """Called out on its own because somebody will try it."""
        self.assertIn("ROOM_JAIL", self.body())


if __name__ == "__main__":
    unittest.main()
