"""A personal stash at the altar that outlives a reboot.

Items go in from anywhere and come out only at the altar. That
asymmetry is the design: it stores loot without becoming a way to
carry it.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zstash12"
ALTAR = 4208
RECALL = 4207
MUD_SCHOOL = 3700


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashTests(unittest.TestCase):
    def player(self, room: int = ALTAR, **fields) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        with mud.connect(timeout=120) as client:
            create_character(client, "Zhoarder", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zhoarder", Levl=60, Tru=70, Room=room, **fields)
        return mud

    def test_it_survives_a_reboot(self) -> None:
        """The whole point. The objects are written to the player file
        under their own section and read back into the stash."""
        mud = self.player()
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            run(client, "load obj 3032", 1.6)          # a bag
            self.assertIn("away for safe keeping",
                          run(client, "stash put bag", 1.8))
            self.assertIn("bag", run(client, "stash", 1.8))
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        # A fresh login is a fresh read of the player file.
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            self.assertIn("bag", run(client, "stash", 2.0))
            # And it is not in inventory.
            self.assertNotIn("bag", run(client, "inventory", 1.8))

    def test_it_goes_in_from_anywhere_and_comes_out_only_here(self) -> None:
        mud = self.player(room=MUD_SCHOOL)
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            run(client, "load obj 3032", 1.6)

            # Deposit from the far side of the world.
            self.assertIn("away for safe keeping",
                          run(client, "stash put bag", 1.8))
            # Withdrawal is refused away from the altar.
            self.assertIn("at the altar", run(client, "stash get bag", 1.8))

            run(client, "goto %d" % ALTAR, 1.8)
            self.assertIn("out of your stash",
                          run(client, "stash get bag", 1.8))
            self.assertIn("bag", run(client, "inventory", 1.8))

    def test_the_listing_is_readable_from_anywhere(self) -> None:
        """Knowing what you own is not the same as reaching it."""
        mud = self.player(room=MUD_SCHOOL)
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            run(client, "load obj 3032", 1.6)
            run(client, "stash put bag", 1.6)
            said = run(client, "stash", 1.8)
            self.assertIn("bag", said, said)
            self.assertIn("50", said, said)

    def test_a_full_stash_refuses(self) -> None:
        """SET will not go below 50, but the loader reads StashMax from
        the file without a range check, so the fixture can start at two
        and the limit is reachable in three commands."""
        mud = self.player(**{"StashMax": 2})
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)

            for _ in range(2):
                run(client, "load obj 3032", 1.2)
                self.assertIn("safe keeping", run(client, "stash put bag", 1.4))

            run(client, "load obj 3032", 1.2)
            said = run(client, "stash put bag", 1.6)
            self.assertIn("full at 2", said, said)
            # Refused means refused: it is still in hand.
            self.assertIn("bag", run(client, "inventory", 1.6))

    def test_shrinking_to_a_size_that_still_fits_is_allowed(self) -> None:
        """The guard is about stranding items, not about shrinking."""
        mud = self.player()
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            run(client, "set player Zhoarder stash 100", 1.6)
            run(client, "load obj 3032", 1.2)
            run(client, "stash put bag", 1.4)

            self.assertIn("now holds 50",
                          run(client, "set player Zhoarder stash 50", 1.6))
            self.assertIn("bag", run(client, "stash", 1.8))

    def test_staff_can_grant_room_but_not_strand_items(self) -> None:
        mud = self.player()
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            self.assertIn("now holds 200",
                          run(client, "set player Zhoarder stash 200", 1.8))
            # Out of range is refused.
            self.assertIn("range", run(client, "set player Zhoarder stash 9000", 1.6))
            self.assertIn("range", run(client, "set player Zhoarder stash 1", 1.6))

    def test_bought_room_survives_a_reboot(self) -> None:
        """stash_max is saved. Without it a purchase evaporates at the
        next login, which is worse than not selling it at all."""
        mud = self.player()
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            run(client, "set player Zhoarder stash 125", 1.8)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            self.assertIn("125", run(client, "stash", 2.0))

    def test_buying_costs_coin_and_only_at_the_altar(self) -> None:
        mud = self.player(room=MUD_SCHOOL)
        with mud.connect(timeout=120) as client:
            login(client, "Zhoarder", PASSWORD)
            self.assertIn("at the altar", run(client, "stash buy", 1.8))

            run(client, "goto %d" % ALTAR, 1.8)
            # No coin yet.
            self.assertIn("do not have it", run(client, "stash buy", 1.8))


class StashSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        cls.obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")

    def test_the_slots_bought_are_saved_under_their_own_letter(self) -> None:
        """fread_char dispatches on the first letter of the key."""
        section = self.save.split("\tcase 'S':", 1)[1].split("\tcase 'T':", 1)[0]
        self.assertIn('"StashMax"', section)
        self.assertIn("StashMax %d", self.save)

    def test_the_stash_section_is_written_last(self) -> None:
        """The marker puts fread_obj into stash mode for every #O after
        it, so nothing of the character's own may follow."""
        self.assertLess(self.save.index("fwrite_pet(ch->pet,fp)"),
                        self.save.index('"#STASH'))
        self.assertLess(self.save.index('"#STASH'),
                        self.save.index('"#END'))

    def test_every_branch_that_moves_something_saves_at_once(self) -> None:
        """A stash written only at quit is a duplication bug waiting for
        a crash.

        Checked branch by branch rather than by counting calls: a count
        was the first version of this and it broke the moment the
        command grew a subcommand, which tells you it was measuring the
        wrong thing.
        """
        body = self.obj.split("void do_stash(", 1)[1]
        body = body.split(chr(10) + "void do_donate(", 1)[0]

        for opens_with in ('!str_prefix( arg, "put" )',
                           '!str_prefix( arg, "get" )',
                           '!str_prefix( arg, "buy" )'):
            with self.subTest(branch=opens_with):
                self.assertIn(opens_with, body)
                branch = body.split(opens_with, 1)[1]
                # To the start of the next subcommand, or the end.
                nxt = branch.find("    if ( !str_prefix( arg,")
                if nxt > 0:
                    branch = branch[:nxt]
                self.assertIn("save_char_obj( ch )", branch)

    def test_shrinking_below_the_contents_is_refused(self) -> None:
        """Checked here rather than against a live server: SET will not
        go below 50 and the cap starts at 50, so tripping this needs
        fifty-one deposits -- a hundred and two commands at about a
        second each. The guard still matters, because a player who
        bought room up to 200 and filled it can have staff set them
        back to 50, and those items would then sit there unreturnable:
        the count is checked on the way in, not on the way out."""
        setter = self.wiz.split('if ( !str_prefix( arg2, "stash" ) )', 1)[1]
        setter = setter.split(chr(10) + "    }", 1)[0]
        self.assertIn("stash_count( victim )", setter)
        self.assertIn("already has", setter)

    def test_leaving_the_game_frees_the_stash(self) -> None:
        """It is not in ch->carrying, so the extract loop never sees it."""
        self.assertIn("stash_extract( ch )", self.handler)


if __name__ == "__main__":
    unittest.main()
