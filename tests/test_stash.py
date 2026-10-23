"""A personal stash at the altar that outlives a reboot.

Items go in from anywhere and come out only at the altar. That
asymmetry is the design: it stores loot without becoming a way to
carry it.
"""
from __future__ import annotations

import pathlib
import re
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
        body = self.save.split("bool save_char_obj( CHAR_DATA *ch )", 1)[1]
        body = body.split("\n}\n", 1)[0]
        self.assertLess(body.index("fwrite_pet(ch->pet,fp)"), body.index('"#STASH'))
        self.assertLess(body.index('"#STASH'), body.index('"#END'))

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


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashDeathTests(unittest.TestCase):
    def world(self) -> LiveMud:
        """A mortal hoarder and a keeper of implementor rank, both at
        the recall point."""
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        for name, level in (("Zhoarder", 20), ("Zkeeper", 70)):
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, name, Levl=level, Room=RECALL)
        return mud

    @staticmethod
    def stash_a_bag_and_die(hero, keeper) -> None:
        """The keeper hands the hero a bag, the hero stashes it, and the
        keeper slays them. The death snapshot then holds the bag."""
        run(keeper, "load obj 3032", 1.6)          # a bag
        run(keeper, "give bag zhoarder", 1.6)
        assert "away for safe keeping" in run(hero, "stash put bag", 1.8)
        assert "bag" in run(hero, "stash", 1.8)
        mark = len(hero.transcript)
        keeper.send("slay zhoarder")
        hero.drain(2.5)                 # the hero's own socket reads the blow
        # A slay says it its own way; the first-death achievement does not.
        assert "first true death" in hero.transcript[mark:], hero.transcript[mark:]

    def test_a_death_keeps_the_stash(self) -> None:
        """A mortal stashes a bag, is slain, and the bag is still there --
        at once and after a fresh login, which reads the player file.
        tests/test_bug_reports_oct10.py pins the source; this plays it."""
        mud = self.world()
        with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as keeper:
            login(hero, "Zhoarder", PASSWORD)
            login(keeper, "Zkeeper", PASSWORD)
            self.stash_a_bag_and_die(hero, keeper)
            self.assertIn("bag", run(hero, "stash", 2.0))
            hero.drain(1.0)
            hero.send("quit")
            self.assertTrue(hero.wait_closed())

        with mud.connect(timeout=120) as hero:
            login(hero, "Zhoarder", PASSWORD)
            self.assertIn("bag", run(hero, "stash", 2.0))

    def test_staff_can_put_a_snapshots_stash_back(self) -> None:
        """PRESTORE <player> <n> STASH reads only the #STASH section of a
        snapshot and adds it to the character as they are: the hero keeps
        playing, is told, and the level is untouched. Written for the two
        stashes Alaric lost to deaths on 2026-10-10, whose death snapshots
        still hold them."""
        mud = self.world()
        with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as keeper:
            login(hero, "Zhoarder", PASSWORD)
            login(keeper, "Zkeeper", PASSWORD)
            self.stash_a_bag_and_die(hero, keeper)
            self.assertIn("holds 1 of", run(hero, "stash", 2.0))

            listing = run(keeper, "prestore zhoarder", 2.5)
            death = re.search(r"\[\s*(\d+)\][^\n]*before death", listing)
            self.assertIsNotNone(death, listing)
            number = death.group(1)

            # A word other than STASH is refused before anything happens.
            self.assertIn("only thing to restore",
                          run(keeper, "prestore zhoarder %s gold" % number, 2.0))

            reply = run(keeper, "prestore zhoarder %s stash" % number, 3.0)
            self.assertIn("Restored 1 object", reply)
            self.assertIn("now holds 2 of", reply)

            # The hero is still here, was told, and has two bags now.
            told = run(hero, "stash", 2.5)
            self.assertIn("back into your stash", told)
            self.assertIn("holds 2 of", told)
            hero.drain(1.0)
            hero.send("quit")
            self.assertTrue(hero.wait_closed())
            saved = (mud.player_dir / "Zhoarder").read_text(encoding="latin-1")
            self.assertRegex(saved, r"(?m)^Levl 20$")

            # Offline: the file is changed in place and the copy freed. The
            # restore above took its own "before stashrestore" copy, so the
            # death snapshot's number has moved down the list -- which is
            # what the stamp is for.
            stamp = re.search(r"before death\s+stamp (\d{8}_\d{6})", listing).group(1)
            # The date half alone is digits only and eight long: a stamp,
            # not a list number, and today it names every snapshot.
            self.assertIn("give more of the stamp",
                          run(keeper, "prestore zhoarder %s stash" % stamp[:8], 2.0))
            reply = run(keeper, "prestore zhoarder %s stash" % stamp, 3.0)
            self.assertIn("Restored 1 object", reply)
            self.assertIn("now holds 3 of", reply)

        with mud.connect(timeout=120) as hero:
            login(hero, "Zhoarder", PASSWORD)
            self.assertIn("holds 3 of", run(hero, "stash", 2.0))


if __name__ == "__main__":
    unittest.main()
