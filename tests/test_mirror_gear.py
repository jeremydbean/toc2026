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

# The silver set in limbo.are carries ITEM_ANTI_EVIL, so only a good or
# neutral character can wear it -- and equip_char zaps it off an evil one.
ANTI_EVIL_SET = (631, 632, 633, 634, 635)
ANTI_EVIL_WORN = ("silver helm", "silver leggings", "silver boots",
                  "silver gauntlets")


def slots(equipment: str) -> list:
    """The "<worn on head>  A silver helm" lines, in order."""
    return [line.strip() for line in equipment.splitlines()
            if line.startswith("<worn") or line.startswith("<wielded")
            or line.startswith("<used") or line.startswith("<held")]


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

    def test_restore_bags_their_kit_and_puts_your_own_back_on(self) -> None:
        """The immortal wears a set nobody else in this test has, so the
        two kits cannot be confused for one another."""
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)

            # Something distinctive of their own, over the starter kit.
            run(client, "mirror clear", 1.8)
            for vnum in ANTI_EVIL_SET:
                run(client, "load obj %d" % vnum, 1.4)
            run(client, "wear all", 2.2)
            mine = run(client, "equipment", 1.8)
            for piece in ANTI_EVIL_WORN:
                with self.subTest(piece=piece):
                    self.assertIn(piece, mine, mine)

            run(client, "mirror Ztarget", 2.5)
            borrowed = run(client, "equipment", 1.8)
            self.assertIn("sub issue vest", borrowed, borrowed)
            self.assertNotIn("silver helm", borrowed, borrowed)

            said = run(client, "mirror restore", 2.5)
            self.assertIn("Ztarget's gear", said, said)

            # Their kit is in the pack, not on the immortal and not gone.
            self.assertIn("Ztarget's gear", run(client, "inventory", 1.8))
            # "gear" and the owner's bare name are both keywords on it.
            # The short description is not: the parser reads one word and
            # "Ztarget's" is not what the pack answers to.
            packed = run(client, "look in gear", 2.0)
            self.assertIn("sub issue vest", packed, packed)

            # Slot for slot what they had on before, which is the whole
            # promise. Both characters own a sub issue vest, so no single
            # piece tells the two kits apart -- the list does.
            self.assertEqual(slots(mine), slots(run(client, "equipment", 1.8)))

    def test_restore_without_a_mirror_says_so(self) -> None:
        mud = self.world()
        with mud.connect(timeout=120) as client:
            login(client, "Zmirror", PASSWORD)
            self.assertIn("not wearing anybody else's",
                          run(client, "mirror restore", 1.8))

            # And it is a one-shot: the second one has nothing to undo.
            run(client, "mirror Ztarget", 2.5)
            run(client, "mirror restore", 2.5)
            self.assertIn("not wearing anybody else's",
                          run(client, "mirror restore", 1.8))

    def test_an_items_alignment_cannot_refuse_the_immortal(self) -> None:
        """MIRROR is for seeing the kit, so nothing about the wearer gets
        to turn a piece down. equip_char zaps an anti-aligned item off
        you and drops it on the floor, which left holes in the mirror and
        litter in the room."""
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)

        with mud.connect(timeout=120) as client:
            create_character(client, "Ztargev", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Ztargev", Levl=70, Room=MUD_SCHOOL, Alig=1000)

        with mud.connect(timeout=120) as client:
            create_character(client, "Zmirrorz", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zmirrorz", Levl=70, Room=MUD_SCHOOL,
                          Alig=-1000)

        # A good character puts the anti-evil set on and logs off.
        with mud.connect(timeout=120) as client:
            login(client, "Ztargev", PASSWORD)
            for vnum in ANTI_EVIL_SET:
                run(client, "load obj %d" % vnum, 1.4)
            run(client, "wear all", 2.2)
            worn = run(client, "equipment", 1.8)
            for piece in ANTI_EVIL_WORN:
                with self.subTest(piece=piece):
                    self.assertIn(piece, worn, worn)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        # An evil one mirrors it, and keeps all of it.
        with mud.connect(timeout=120) as client:
            login(client, "Zmirrorz", PASSWORD)
            said = run(client, "mirror Ztargev", 3.0)
            self.assertNotIn("zapped", said.lower(), said)

            worn = run(client, "equipment", 2.0)
            for piece in ANTI_EVIL_WORN:
                with self.subTest(piece=piece):
                    self.assertIn(piece, worn, worn)

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

    def test_nothing_about_the_wearer_can_refuse_a_piece(self) -> None:
        helper = self.wiz.split("static bool mirror_wear(", 1)[1]
        helper = helper.split(chr(10) + "}", 1)[0]
        for flag in ("ITEM_ANTI_GOOD", "ITEM_ANTI_EVIL", "ITEM_ANTI_NEUTRAL"):
            with self.subTest(flag=flag):
                self.assertIn("REMOVE_BIT( obj->extra_flags, %s )" % flag,
                              helper)

    def test_the_weapon_goes_on_before_the_shield(self) -> None:
        """equip_char takes a shield off to free both hands for a
        two-hander, so forwards it would undo a kit the owner was wearing
        quite happily."""
        body = self.body()
        self.assertEqual(
            body.count("for ( iWear = MAX_WEAR - 1; iWear >= 0; iWear-- )"), 2)

    def test_what_was_taken_off_is_remembered_as_vnums(self) -> None:
        """Not pointers. An object can be dropped, sacrificed or purged
        between MIRROR and MIRROR RESTORE, and a stale pointer to one is a
        crash where a stale vnum is merely a piece that does not return."""
        merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        self.assertIn("int                 mirror_worn[MAX_WEAR];", merc)

        strip = self.wiz.split("static void mirror_strip(", 1)[1]
        strip = strip.split(chr(10) + "}", 1)[0]
        self.assertIn("obj->pIndexData->vnum", strip)

    def test_restore_forgets_the_mirror_so_it_cannot_run_twice(self) -> None:
        restore = self.wiz.split("static void mirror_restore(", 1)[1]
        restore = restore.split(chr(10) + "}", 1)[0]
        self.assertIn("mirror_of[0] == ", restore)
        self.assertIn("mirror_of[0] = ", restore)

    def test_the_pack_is_filled_before_the_immortals_own_kit_goes_on(self):
        """Otherwise mirror_find_carried picks up a mirrored copy of a
        piece the immortal owns one of too, and the original stays loose
        in the bag."""
        restore = self.wiz.split("static void mirror_restore(", 1)[1]
        restore = restore.split(chr(10) + "}", 1)[0]
        self.assertLess(restore.index("obj_to_obj( obj, pack )"),
                        restore.index("mirror_find_carried"))
        # And only loose items are candidates, never one just bagged.
        finder = self.wiz.split("static OBJ_DATA *mirror_find_carried(", 1)[1]
        finder = finder.split(chr(10) + "}", 1)[0]
        self.assertIn("wear_loc == WEAR_NONE", finder)

    def test_the_immortal_keeps_what_they_took_off(self) -> None:
        strip = self.wiz.split("static void mirror_strip(", 1)[1]
        strip = strip.split(chr(10) + "}", 1)[0]
        self.assertIn("unequip_char", strip)
        self.assertNotIn("extract_obj", strip)

        restore = self.wiz.split("static void mirror_restore(", 1)[1]
        restore = restore.split(chr(10) + "}", 1)[0]
        self.assertNotIn("extract_obj", restore)


if __name__ == "__main__":
    unittest.main()
