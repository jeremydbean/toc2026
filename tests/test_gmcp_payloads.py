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

    def test_the_quest_feed_says_which_contract_and_how_long(self) -> None:
        body = function_body(self.gmcp, "void gmcp_send_quest(")
        for key in ('"active"', '"kind"', '"countdown"', '"target"',
                    '"streak"', '"wait"'):
            self.assertIn(key.replace('"', chr(92) + '"'), body, key)
        # An emergency and a rush are different contracts and the panel
        # has to be able to tell them apart.
        self.assertIn("questemergency", body)
        self.assertIn("questrush", body)
        # The target room's vnum rides along so the Mudlet client can walk
        # there -- the map keys rooms by vnum, so WALK QUEST is gotoRoom.
        self.assertIn(r'\"num\"', body)
        self.assertIn("ch->questroom", body)

    def test_the_target_feed_respects_sight(self) -> None:
        """You cannot watch the health of something you cannot see."""
        body = function_body(self.gmcp, "void gmcp_send_target(")
        self.assertIn("can_see( ch, victim )", body)
        self.assertIn("gmcp_percent", body)

    def test_the_lag_feed_sends_on_change_not_every_pulse(self) -> None:
        """A lag bar that was told the wait four times a second would
        flood the link; it is sent only when the wait rises or clears."""
        body = function_body(self.gmcp, "void gmcp_send_lag(")
        self.assertIn("ch->wait", body)
        self.assertIn("PULSE_PER_SECOND", body)
        # Immortals are never held, so they are sent no lag.
        self.assertIn("IS_IMMORTAL", body)
        # The guard is "increased, or cleared from non-zero", not "differs".
        self.assertIn("> d->gmcp_last_wait", body)

    def test_the_group_feed_is_players_and_needs_two(self) -> None:
        """A party panel: real group members only, and never a list of
        one, which is just you."""
        body = function_body(self.gmcp, "void gmcp_send_group(")
        self.assertIn("is_same_group", body)
        self.assertIn("count < 2", body)
        self.assertIn(r'\"leader\"', body)

    def test_room_chars_skips_you_and_what_you_cannot_see(self) -> None:
        body = function_body(self.gmcp, "void gmcp_send_chars(")
        self.assertIn("rch == ch || !can_see( ch, rch )", body)
        self.assertIn("ACT_AGGRESSIVE", body)
        # Bounded: a crowded room must not run the payload off the end.
        self.assertRegex(body, r"count\s*<\s*\d+")

    def test_a_health_bar_never_divides_by_zero(self) -> None:
        """max_hit can be zero on a half-built mobile."""
        body = function_body(self.gmcp, "static int gmcp_percent(")
        self.assertIn("maximum <= 0", body)

    def test_items_hash_a_signature_rather_than_the_payload(self) -> None:
        """This one runs off the main loop and an inventory is long.

        The other feeds build their JSON and hash that. Doing it here
        would build dozens of short strings four times a second and
        throw them away, so the signature is integer arithmetic over
        the vnums and wear slots -- what a change to either moves.
        """
        body = function_body(self.gmcp, "void gmcp_send_items(")
        signature_at = body.index("gmcp_items_signature")
        build_at = body.index("inventory")
        self.assertLess(signature_at, build_at,
                        "the payload is being built before the check")
        self.assertIn("return;", body[signature_at:build_at])

    def test_an_achievement_is_announced_once_and_never_in_bulk(self) -> None:
        """A login can hand out a dozen silent catch-up awards."""
        achievements = read("src", "achievements.c")
        announce = achievements.split("achievement_can_announce(ch, announce)",
                                      1)[1]
        announce = announce[:announce.index("return true;")]
        self.assertIn("gmcp_send_achievement(", announce)
        # And nowhere else.
        self.assertEqual(achievements.count("gmcp_send_achievement("), 1)

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
