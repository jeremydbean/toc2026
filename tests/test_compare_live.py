"""COMPARE, live: damage first, pairs, empty slots, and the upgrade search.

A level 52 dwarf warrior with trained skills, real hit points and a kit,
because a fresh character's 20 hp and empty skill list make every
percentage meaningless.
"""
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

PW = "testpw12"
ME = "Zcmpdwarf"
IMM = "Zcmpimm"

# (vnum, keyword) -- the moonray sword, the blue war banner (a light),
# Starlight (a dwarf-only light), and an assassin's ring.
KIT = [(9923, "moonray"), (756, "banner"), (29049, "starlight"),
       (16033, "assassin")]

_SKIP = skip_reason()


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class CompareLive(unittest.TestCase):
    def test_compare_ranks_damage_first_for_a_kitted_warrior(self):
        with LiveMud() as mud:
            for name in (ME, IMM):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
            patch_player_file(mud, ME, Levl=52, Race="dwarf~", Cla=3, Room=4207)
            patch_player_file(mud, IMM, Levl=70, Room=4207)

            with mud.connect(timeout=120) as me, mud.connect(timeout=120) as imm:
                login(me, ME, PW)
                login(imm, IMM, PW)
                imm.command("set skill %s all 100" % ME, 1.0)
                imm.command("set char %s hp 1400" % ME, 0.5)
                imm.command("set char %s str 22" % ME, 0.3)
                for vnum, key in KIT:
                    imm.command("load obj %d 52" % vnum, 0.4)
                    imm.command("give %s %s" % (key, ME.lower()), 0.4)
                me.command("wield moonray", 0.5)
                me.command("wear banner", 0.5)

                out = me.command("compare profile", 1.5)
                self.assertIn("Your damage comes from weapons.", out)
                self.assertIn("Each round:", out)
                self.assertNotIn("Spells:", out)   # a warrior casts nothing

                # Against the worn light: Starlight hits harder.
                out = me.command("compare starlight", 1.5)
                self.assertIn("B) the blue war banner", out)
                self.assertIn("Weapon dmg/round", out)
                self.assertIn("A instead of B:", out)
                self.assertIn("Verdict: A, Starlight", out)
                self.assertNotIn("Hit Return", out)

                # Nothing on either finger: measured against the empty slot.
                out = me.command("compare assassin", 1.5)
                self.assertIn("B) nothing -- the slot is empty", out)
                self.assertIn("more damage", out)

                # The search finds Starlight for a dwarf, says where it is,
                # and fits one screen.
                out = me.command("compare upgrades light", 4.0)
                self.assertIn("Starlight", out)
                self.assertIn("Korzath", out)
                out = me.command("compare upgrades", 4.0)
                self.assertIn("Best upgrade you can get for each slot", out)
                self.assertNotIn("Hit Return", out)

                out = me.command("compare defense upgrades finger", 4.0)
                self.assertIn("tougher", out)


if __name__ == "__main__":
    unittest.main()
