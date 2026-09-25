"""MIRROR: wear somebody else's kit, whether or not they are logged in.

For looking at a character's setup from the inside -- why they are taking
the damage they are, whether a slot is empty, what a build adds up to --
without asking them to hand anything over.

Fresh objects are made from the vnums the target wears, so what you get is
each piece's prototype rather than their copy of it. An enchantment they
put on their own sword is not reproduced, and neither is its wear.

These run against a real server in a throwaway tree.
"""
from __future__ import annotations

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

PASSWORD = "Zmirror1"
MUD_SCHOOL = 3700

# What a new character is given and can put on unaided.
STARTER_KIT = ("war banner", "sub issue vest", "sub issue shield",
               "sub issue sword")


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class MirrorTests(unittest.TestCase):
    def world(self) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)

        with mud.connect(timeout=120) as client:
            create_character(client, "Ztarget", PASSWORD)
            run(client, "wear all", 1.6)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            create_character(client, "Zmirror", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zmirror", Levl=70, Room=MUD_SCHOOL)
        return mud

    def test_it_mirrors_a_player_who_is_not_logged_in(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)
            # A new character is dressed by the Gods, so clear first to
            # prove the mirroring put the kit on rather than leaving it.
            run(client, "mirror clear", 1.8)
            self.assertIn("Nothing", run(client, "equipment", 1.6))

            said = run(client, "mirror Ztarget", 2.5)
            self.assertIn("as they last saved it", said, said)

            worn = run(client, "equipment", 1.8)
            for piece in STARTER_KIT:
                with self.subTest(piece=piece):
                    self.assertIn(piece, worn)

    def test_it_mirrors_a_player_who_is_logged_in(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)
            with mud.connect(timeout=120) as target:
                login(target, "Ztarget", PASSWORD)

                said = run(client, "mirror Ztarget", 2.5)
                self.assertIn("Ztarget's kit", said, said)
                self.assertNotIn("last saved", said)

                worn = run(client, "equipment", 1.8)
                for piece in STARTER_KIT:
                    with self.subTest(piece=piece):
                        self.assertIn(piece, worn)
                target.send("quit")
                target.wait_closed()

    def test_clear_takes_everything_off(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)
            run(client, "mirror Ztarget", 2.5)
            self.assertIn("sub issue vest", run(client, "equipment", 1.8))

            self.assertIn("take everything off",
                          run(client, "mirror clear", 1.8))
            self.assertIn("Nothing", run(client, "equipment", 1.8))

    def test_it_says_so_when_there_is_no_such_player(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)
            self.assertIn("No player by that name",
                          run(client, "mirror Nosuchguy", 2.0))
            self.assertIn("Syntax:", run(client, "mirror", 1.6))


class MirrorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")
        cls.interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")

    def body(self) -> str:
        text = self.wiz.split("void do_mirror(", 1)[1]
        return text.split("\n/*\n * FINGER", 1)[0]

    def test_it_is_a_staff_command_and_is_logged(self) -> None:
        row = [line for line in self.interp.splitlines()
               if '"mirror"' in line]
        self.assertEqual(len(row), 1, row)
        self.assertIn("L5", row[0])
        self.assertIn("LOG_ALWAYS", row[0])

    def test_it_reads_the_player_file_when_nobody_is_online(self) -> None:
        body = self.body()
        self.assertIn("PLAYER_DIR", body)
        self.assertIn('"#O"', body)
        self.assertIn('"Wear"', body)
        # Nest zero is worn rather than packed inside something.
        self.assertIn("nest == 0", body)

    def test_an_action_item_is_never_put_on(self) -> None:
        """equip_char fires those: one recalls you and one kills you."""
        helper = self.wiz.split("static bool mirror_wear(", 1)[1]
        helper = helper.split("\n}", 1)[0]
        self.assertIn("ITEM_ACTION", helper)

    def test_the_immortal_keeps_what_they_took_off(self) -> None:
        strip = self.wiz.split("static void mirror_strip(", 1)[1]
        strip = strip.split("\n}", 1)[0]
        self.assertIn("unequip_char", strip)
        self.assertNotIn("extract_obj", strip)


if __name__ == "__main__":
    unittest.main()
