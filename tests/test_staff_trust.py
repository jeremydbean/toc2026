"""Staff are immortals by level; trust is command authority.

Owner, 2026-11-12: "i think trusted characters should actually be logged
also. just not immortals", "no let trusted players act as mortals across
the board", "staff-only should ONLY apply to actual immortals level 60+".

`interpret()` gates every command on `get_trust(ch)`, and that stays: a
mortal given trust may type the commands it reaches. Everything else that
asks whether somebody is staff -- a gameplay exemption, a staff channel,
notice, view or listing -- asks `is_staff()` (an immortal by level, the
original behind a switched mobile, never a mobile alone, and the creator)
or compares `staff_trust()` (an immortal's trust, anybody else's level).
This module holds the staff channels to that and sweeps the source so a
staff test by trust does not come back. tests/test_trusted_mortal.py plays
the rest live.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Ztrust12"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class StaffChannelTests(unittest.TestCase):
    def world(self) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        for name in ("Zgod", "Zimmo", "Zbuilda", "Zplain"):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zgod", Levl=70, Tru=70, Room=TEMPLE)
        patch_player_file(mud, "Zimmo", Levl=60, Room=TEMPLE)
        # Mortal level, immortal trust: a mortal everywhere but the
        # command table.
        patch_player_file(mud, "Zbuilda", Levl=45, Tru=65, Room=TEMPLE)
        patch_player_file(mud, "Zplain", Levl=45, Room=TEMPLE)
        return mud

    def test_immtalk_reaches_immortals_by_level_only(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as imm, \
                mud.connect(timeout=120) as builder, \
                mud.connect(timeout=120) as mortal:
            login(imm, "Zimmo", PASSWORD)
            login(builder, "Zbuilda", PASSWORD)
            login(mortal, "Zplain", PASSWORD)
            for client in (imm, builder, mortal):
                client.drain(1.0)

            with mud.connect(timeout=120) as god:
                login(god, "Zgod", PASSWORD)
                run(god, "immtalk a private matter", 2.0)

            self.assertIn("a private matter", run(imm, "", 2.0))
            for client in (builder, mortal):
                heard = run(client, "", 2.0)
                self.assertNotIn("a private matter", heard, heard[-500:])
            # Nor is it read back: HISTORY asks the rank hearing it needs.
            self.assertNotIn("a private matter", run(builder, "history", 2.0))
            self.assertIn("a private matter", run(imm, "history", 2.0))

    def test_trust_still_lets_them_speak_and_shows_its_rank(self) -> None:
        """Speaking is the command, and the command is trust's."""
        mud = self.world()
        with mud.connect(timeout=120) as god:
            login(god, "Zgod", PASSWORD)
            god.drain(1.0)

            with mud.connect(timeout=120) as builder:
                login(builder, "Zbuilda", PASSWORD)
                run(builder, "immtalk hello", 2.0)

            heard = run(god, "", 2.0)
            # Trust 65, not level 45.
            self.assertIn("[65]", heard, heard[-500:])


class StaffTrustSourceTests(unittest.TestCase):
    """A standing sweep, so a staff test by trust is caught here."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {p.name: p.read_text(encoding="latin-1")
                       for p in (ROOT / "src").glob("*.c")}

    def body(self, filename: str, function: str) -> str:
        text = self.sources[filename]
        start = re.search(r"^(?:static )?(?:void|bool|int) " + function + r"\s*\(",
                          text, re.M)
        self.assertIsNotNone(start, function + " not found in " + filename)
        end = text.find("\n}", start.start())
        return text[start.start():end]

    def test_is_staff_is_by_level(self) -> None:
        body = self.body("handler.c", "is_staff")
        self.assertIn("ch->desc->original", body, "a switched immortal is their own character")
        self.assertIn("IS_NPC(ch)", body, "a mobile alone is never staff")
        self.assertIn("ch->level >= LEVEL_IMMORTAL", body)
        self.assertIn("is_creator( ch )", body, "the creator keeps the rank")
        self.assertNotIn("get_trust", body)
        self.assertNotIn("->trust", body)
        rank = self.body("handler.c", "staff_trust")
        self.assertIn("if ( is_staff( ch ) )", rank)
        self.assertIn("return get_trust( ch );", rank)

    def test_no_staff_test_by_trust_is_left(self) -> None:
        """IS_TRUSTED( x, LEVEL_IMMORTAL ) asks whether somebody is staff
        by trust. The one survivor picks SWITCH's message over the
        werewolf branch: command authority, not staff-ness."""
        found = []
        for name, text in sorted(self.sources.items()):
            for m in re.finditer(r"IS_TRUSTED\s*\([^;]*?LEVEL_IMMORTAL\s*\)", text):
                line = text.count("\n", 0, m.start()) + 1
                found.append("%s:%d" % (name, line))
        switch = self.body("act_wiz.c", "do_switch")
        self.assertEqual(len(found), 1, found)
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", switch)
        staff_compare = re.compile(r"get_trust\s*\([^)]*\)\s*(?:>=|<)\s*LEVEL_IMMORTAL")
        for name, text in sorted(self.sources.items()):
            with self.subTest(file=name):
                self.assertIsNone(staff_compare.search(text),
                                  "a staff test by trust: use is_staff()")

    def test_the_channels_and_their_history_ask_staff_trust(self) -> None:
        body = self.body("act_comm.c", "channel_say")
        self.assertIn("staff_trust( victim ) < hear_level", body)
        self.assertNotIn("get_trust( victim )", body)
        self.assertNotIn("victim->level < hear_level", body)
        history = self.body("act_comm.c", "history_may_read")
        self.assertIn("staff_trust( ch )", history)

    def test_wizinfo_reaches_staff_only(self) -> None:
        body = self.body("comm.c", "wizinfo")
        self.assertIn("staff_trust( d->character ) >= UMAX( level, LEVEL_IMMORTAL )", body)

    def test_sight_is_staff_trust(self) -> None:
        body = self.body("handler.c", "sight_trust")
        self.assertIn("staff_trust( ch )", body)
        self.assertNotIn("get_trust", body)

    def test_the_gameplay_exemptions_ask_level(self) -> None:
        for filename, function in (
            ("act_obj.c", "do_eat"),
            ("act_comm.c", "is_note_to"),
            ("act_comm.c", "report_login_notice"),
            ("act_comm.c", "is_ignoring"),
            ("act_wiz.c", "is_invulnerable"),
            ("handler.c", "room_is_private"),
            ("handler.c", "can_enter_private_room"),
            ("handler.c", "newbie_room_refuses"),
            ("act_move.c", "travel_spell_refuses"),
            ("update.c", "hunger_thirst_applies"),
        ):
            with self.subTest(function=function):
                body = self.body(filename, function)
                self.assertIn("is_staff(", body)
                self.assertNotIn("IS_TRUSTED", body)
        self.assertIn("#define ACH_STAFF(ch) is_staff((ch))", self.sources["achievements.c"])

    def test_command_authority_and_rank_keep_trust(self) -> None:
        """What trust still decides: the command table, and who may act
        on whom."""
        self.assertIn("cmd_table[cmd].level <= trust", self.sources["interp.c"])
        rank = self.body("handler.c", "rank_protects")
        self.assertIn("get_trust( ch )", rank)
        self.assertIn("get_trust( victim )", rank)
        snoop = self.sources["comm.c"]
        self.assertIn("if ( get_trust( snooper ) < snoop_level )", snoop)

    def test_switch_does_not_drop_staff_into_the_werewolf_branch(self) -> None:
        """The else arm moves the character to room 9 and copies a
        were_shape onto the mobile. Anybody SWITCH's trust lets in must
        take the first arm, so it stays trust's."""
        body = self.body("act_wiz.c", "do_switch")
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", body)
        self.assertLess(body.index("IS_TRUSTED"), body.index("were_shape"))


if __name__ == "__main__":
    unittest.main()
