"""Staff commands decide staffhood the way the command table does.

`interpret()` gates every command on `get_trust(ch)`. Anything that asks
`ch->level` instead disagrees with it for exactly one kind of character:
a builder given immortal trust without an immortal level. That character
could run the command and then be refused by it, which is how INVULN,
the note board and all three staff channels were broken.
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
        for name in ("Zgod", "Zbuilda", "Zplain"):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zgod", Levl=70, Tru=70, Room=TEMPLE)
        # The case the level test missed: mortal level, immortal trust.
        patch_player_file(mud, "Zbuilda", Levl=45, Tru=65, Room=TEMPLE)
        patch_player_file(mud, "Zplain", Levl=45, Room=TEMPLE)
        return mud

    def test_a_trusted_builder_hears_immtalk(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as builder:
            login(builder, "Zbuilda", PASSWORD)
            builder.drain(1.0)

            with mud.connect(timeout=120) as god:
                login(god, "Zgod", PASSWORD)
                run(god, "immtalk anybody there", 2.0)

            heard = run(builder, "", 2.0)
            self.assertIn("anybody there", heard, heard[-500:])

    def test_a_plain_mortal_does_not(self) -> None:
        """Widening who hears a staff channel is only safe if the people
        it was keeping out are still kept out."""
        mud = self.world()
        with mud.connect(timeout=120) as mortal:
            login(mortal, "Zplain", PASSWORD)
            mortal.drain(1.0)

            with mud.connect(timeout=120) as god:
                login(god, "Zgod", PASSWORD)
                run(god, "immtalk a private matter", 2.0)

            heard = run(mortal, "", 2.0)
            self.assertNotIn("a private matter", heard, heard[-500:])

    def test_the_rank_shown_is_the_rank_that_let_them_speak(self) -> None:
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
    """A standing sweep, so the next one of these is caught here."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {p.name: p.read_text(encoding="utf-8", errors="replace")
                       for p in (ROOT / "src").glob("*.c")}

    def body(self, filename: str, function: str) -> str:
        text = self.sources[filename]
        start = re.search(r"^(?:static )?(?:void|bool) " + function + r"\s*\(",
                          text, re.M)
        self.assertIsNotNone(start, function + " not found in " + filename)
        end = text.find("\n}", start.start())
        return text[start.start():end]

    def test_the_channels_ask_trust(self) -> None:
        body = self.body("act_comm.c", "channel_say")
        self.assertIn("get_trust( victim ) < hear_level", body)
        self.assertNotIn("victim->level < hear_level", body)

    def test_the_commands_that_were_gated_by_level_are_not(self) -> None:
        for filename, function in (
            ("act_obj.c", "do_eat"),
            ("act_wiz.c", "do_finger"),
            ("act_wiz.c", "do_switch"),
            ("act_comm.c", "is_note_to"),
            ("maxload.c", "do_lst_maxload"),
        ):
            with self.subTest(function=function):
                self.assertNotIn("IS_IMMORTAL", self.body(filename, function))

    def test_switch_does_not_drop_staff_into_the_werewolf_branch(self) -> None:
        """The else arm moves the character to room 9 and copies a
        were_shape onto the mobile. A trusted builder landed in it."""
        body = self.body("act_wiz.c", "do_switch")
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", body)
        self.assertLess(body.index("IS_TRUSTED"), body.index("were_shape"))


if __name__ == "__main__":
    unittest.main()
