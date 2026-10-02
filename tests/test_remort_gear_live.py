"""Live end-to-end check of the remort gear fix.

Proves the owner's rule: when you remort, nothing you were carrying or wearing
is lost.  A remort drops the body to level 3; gear it can no longer wear is
folded into a named pack in the stash rather than deleted (the old save-time
level limit) or left uselessly worn.

Setup loads two over-level pieces as an immortal -- one wielded, one in the
pack -- quits, then patches the file down to the first-remort level
(LEVEL_HERO3 == 54) and remorts warrior -> cleric.  After a relog at the altar,
both pieces must be inside the "<name>'s level 54 gear" bag in the stash.
"""
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

PW = "testpw12"
NAME = "Zremorter"
ALTAR = 4208

_SKIP = skip_reason()


def run(client, line, settle=0.9):
    return client.command(line, settle)


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class RemortGearLive(unittest.TestCase):
    def test_remort_keeps_every_piece_in_the_stash(self):
        with LiveMud() as mud:
            # Create a human warrior, then quit so the file can be patched.
            with mud.connect(timeout=120) as client:
                create_character(client, NAME, PW)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "character did not quit")

            # Immortal, so we can load and tune gear, then quit again.
            patch_player_file(mud, NAME, Levl=70)
            with mud.connect(timeout=120) as client:
                login(client, NAME, PW)
                run(client, "load obj 3700")            # a mace (not the warrior's sword)
                run(client, "set obj mace level 50")
                run(client, "wield mace")               # worn, over-level
                run(client, "load obj 3703")            # a vest, left in the pack
                run(client, "set obj vest level 50")    # carried, over-level
                saved = run(client, "equipment", 1.0)
                self.assertIn("mace", saved.lower(),
                              "mace should be wielded before the remort:\n" + saved)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "did not quit after setup")

            # Drop to the first-remort level in the file, keeping the gear.
            patch_player_file(mud, NAME, Levl=54)
            with mud.connect(timeout=120) as client:
                login(client, NAME, PW)
                out = run(client, "remort %s cleric none human" % PW, 2.5)
                self.assertIn(
                    "stash", out.lower(),
                    "remort should fold outgrown gear into the stash:\n" + out)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "did not quit after remort")

            # Stand the level-3 cleric at the altar so the stash is reachable.
            patch_player_file(mud, NAME, Room=ALTAR)
            with mud.connect(timeout=120) as client:
                login(client, NAME, PW)

                listing = run(client, "stash list", 1.4)
                self.assertIn(
                    "gear", listing.lower(),
                    "the remort gear bag should be in the stash:\n" + listing)

                run(client, "stash get gear", 1.6)      # withdraw the bag
                inside = run(client, "look in gear", 1.4)
                low = inside.lower()
                self.assertTrue(
                    "mace" in low and "vest" in low,
                    "both outgrown pieces must be inside the bag, none lost:\n"
                    + inside)


if __name__ == "__main__":
    unittest.main()
