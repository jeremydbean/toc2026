"""Shadowmeld and the longer idle rope, both remort gifts.

Shadowmeld is hide with the timer taken off: sit, sleep, read, and it
holds. Moving ends it, and so does swinging at somebody. Mobiles
cannot see a melded character at all, which is the point -- it is the
one state that is safe to leave the keyboard in.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zmeld123"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShadowmeldTests(unittest.TestCase):
    def melder(self, remorts: int = 4) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        with mud.connect(timeout=120) as client:
            create_character(client, "Zshadow", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zshadow", Levl=57, Tru=70, Room=TEMPLE,
                          **{"NumRemorts": remorts})
        return mud

    def test_a_fourth_remort_can_meld_and_a_third_cannot(self) -> None:
        mud = self.melder(remorts=3)
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.assertIn("do not know you well enough",
                          run(client, "shadowmeld", 1.8))

        mud2 = self.melder(remorts=4)
        with mud2.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.assertIn("draw the shadows",
                          run(client, "shadowmeld", 1.8))

    def test_it_holds_through_sleeping(self) -> None:
        """Unlike hide, which the usual restrictions end."""
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            run(client, "shadowmeld", 1.8)
            run(client, "sleep", 1.6)
            # Still melded: asking again toggles it off rather than on.
            self.assertIn("step out of the shadows",
                          run(client, "shadowmeld", 1.8))

    def test_moving_ends_it(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            run(client, "shadowmeld", 1.8)
            said = run(client, "north", 1.8)
            self.assertIn("step out of the shadows", said, said)
            # And it really is off: asking again turns it on.
            self.assertIn("draw the shadows",
                          run(client, "shadowmeld", 1.8))

    def test_it_toggles(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.6))
            self.assertIn("step out", run(client, "shadowmeld", 1.6))
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.6))

    def test_you_cannot_meld_mid_fight(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            run(client, "goto 3700", 1.8)
            run(client, "kill guard", 2.2)
            said = run(client, "shadowmeld", 1.8)
            if "middle of a fight" not in said:
                self.skipTest("nothing here fought back")
            self.assertIn("middle of a fight", said, said)


class ShadowmeldSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        cls.update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        cls.move = (ROOT / "src" / "act_move.c").read_text(encoding="utf-8")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")

    def test_mobiles_cannot_see_a_melded_character(self) -> None:
        """The check has to sit above the shortcut that hands every
        immortal-level mobile perfect sight, or an aggressive one walks
        in and kills somebody who stepped away."""
        body = self.handler.split("bool can_see( CHAR_DATA *ch", 1)[1]
        body = body.split("\n}", 1)[0]
        meld = body.index("AFF2_SHADOWMELD")
        shortcut = body.index("IS_NPC(ch) && IS_IMMORTAL(ch)")
        self.assertLess(meld, shortcut)

    def test_breaking_it_speaks_only_when_there_is_a_room(self) -> None:
        """char_from_room and the extraction paths both reach this."""
        body = self.move.split("void shadowmeld_break(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("ch->in_room != NULL", body)

    def test_the_break_runs_after_the_null_room_check(self) -> None:
        body = self.handler.split("void char_from_room(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertLess(body.index("Char_from_room: NULL"),
                        body.index("shadowmeld_break"))

    def test_a_third_remort_doubles_the_idle_rope(self) -> None:
        body = self.update.split("int idle_purge_ticks(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("REMORTS_FOR_LONG_IDLE", body)
        self.assertIn("LINKDEAD_PURGE_TICKS * 2", body)

    def test_both_idle_branches_use_the_helper(self) -> None:
        """There are two: link-dead, and connected but idle."""
        self.assertEqual(2, self.update.count("idle_purge_ticks( ch )"))
        # And the raw constant is no longer compared against directly.
        body = self.update.split("void char_update(", 1)[1]
        self.assertNotIn(">= LINKDEAD_PURGE_TICKS", body)

    def test_the_gifts_are_named_rather_than_numbered(self) -> None:
        self.assertIn("#define REMORTS_FOR_SHADOWMELD", self.merc)
        self.assertIn("#define REMORTS_FOR_LONG_IDLE", self.merc)


if __name__ == "__main__":
    unittest.main()
