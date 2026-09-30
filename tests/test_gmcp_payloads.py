"""What the GMCP feeds carry, and who is allowed to receive it.

Room.Info, Char.Affects and Comm.Channel are what the Mudlet package
draws its map, its affect panel and its chat window from. The rules
guarded here are the ones that are invisible when broken: a chat feed
whose audience is a guess rather than the channel's own, an affect
list that reports the implementation instead of the character, and a
payload that quietly stops carrying a field the client needs.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    depth = 0
    seen = False
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
            seen = True
        elif source[i] == "}":
            depth -= 1
            if seen and depth == 0:
                return source[start:i + 1]
    raise AssertionError("unterminated: " + signature)


class GmcpPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gmcp = read("src", "gmcp.c")
        cls.comm = read("src", "act_comm.c")
        cls.room = function_body(cls.gmcp, "void gmcp_send_room(")
        cls.affects = function_body(cls.gmcp, "void gmcp_send_affects(")

    def test_room_info_carries_what_the_map_draws(self) -> None:
        for key in ('\\"doors\\":{', '\\"flags\\":[', '\\"services\\":[',
                    '\\"exits\\":{'):
            self.assertIn(key, self.room, key)

    def test_a_secret_door_is_not_announced(self) -> None:
        """The doors loop must keep every guard the exits loop has."""
        doors = self.room.split('\\"doors\\":{', 1)[1].split('\\"flags\\"', 1)[0]
        self.assertIn("EX_SECRET", doors)
        self.assertIn("can_see_room", doors)
        self.assertIn("EX_ISDOOR", doors)

    def test_services_are_what_a_room_is_for(self) -> None:
        services = self.room.split('\\"services\\":[', 1)[1]
        self.assertIn("pShop", services)
        self.assertIn("ACT_QUESTM", services)
        # A mobile nobody can see is not a service, and two
        # shopkeepers in one room are one "shop".
        self.assertIn("can_see(ch, rch)", services)
        self.assertIn("seen[role]", services)

    def test_affects_report_the_character_not_the_implementation(self) -> None:
        """bless is two AFFECT_DATA sharing one name; it is one row."""
        self.assertIn("seen[i] == paf->type", self.affects)
        self.assertIn("AFF2_SHADOWMELD", self.affects)

    def test_the_affect_walk_is_bounded(self) -> None:
        self.assertRegex(self.affects, r"count\s*<\s*\d+")

    def test_affects_are_sent_only_when_they_change(self) -> None:
        self.assertIn("gmcp_last_affect_hash", self.affects)

    def test_chat_is_emitted_where_it_is_delivered(self) -> None:
        """The audience differs per channel, so the emit cannot be central.

        yell reaches one area, the staff channels are rank-gated, and
        every channel honours its own deafness flag. Emitting once
        from the history register -- which knows the channel and the
        speaker but not who heard it -- would put other people's yells
        in your chat window. Two calls per channel: one beside the
        speaker's own copy, one inside the loop that writes to each
        listener.
        """
        recordings = len(re.findall(r"^\s*channel_history_add\( ", self.comm,
                                    re.MULTILINE))
        emits = self.comm.count("gmcp_send_channel(")
        self.assertEqual(recordings, 7, "channel count moved")
        self.assertEqual(
            emits, recordings * 2 + 2,
            "every channel needs a speaker emit and a listener emit; "
            "then one inside tell_history_add, and one inside do_say "
            "whose single room loop covers the speaker too",
        )

    def test_a_say_is_journalled_but_never_replayed(self) -> None:
        """A room conversation cannot honestly be replayed.

        HISTORY hands its rings to whoever asks, including somebody
        who was nowhere near at the time, and nothing remembers who
        was standing in the room. So a say reaches the journal and
        the chat panes of the people who were there, and no ring.
        """
        # Not function_body(): do_say is full of colour codes like
        # "{%02X" and "{00", and a brace counter cannot tell those
        # from the braces it is looking for.
        body = self.comm.split("void do_say(", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertIn('channel_journal_record( "say"', body)
        self.assertIn('gmcp_send_channel( rch->desc, "say"', body)
        self.assertNotIn("channel_history_add", body)
        # The same position gate act() just used, so a sleeper who was
        # not shown the line does not receive it either.
        self.assertIn("position < POS_RESTING", body)

    def test_the_listener_emit_sits_with_the_listener_write(self) -> None:
        """Beside act_new_cstr, so it inherits that loop's filters."""
        for block in re.findall(
                r"act_new_cstr[^;]*;\s*\n\s*gmcp_send_channel\( d,",
                self.comm):
            self.assertIn("gmcp_send_channel( d,", block)
        self.assertGreaterEqual(
            len(re.findall(r"gmcp_send_channel\( d,", self.comm)), 7)

    def test_tells_are_per_recipient_and_never_broadcast(self) -> None:
        body = function_body(self.comm, "void tell_history_add(")
        self.assertIn('gmcp_send_channel( ch->desc, "tell"', body)
        self.assertNotIn("descriptor_list", body)


if __name__ == "__main__":
    unittest.main()
