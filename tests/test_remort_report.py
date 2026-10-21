"""Three remort faults from the report of 2026-10-21.

1. A remort outside the Temple moved its owner and not the pet the
   cleanup had kept, and save_char_obj writes a pet only from its owner's
   room -- so the remort's own save dropped the pet, and a quit made it
   final.
2. OUTFIT returned "You already have some equipment, put it on." at the
   first carried school item, so a remort with any old school piece in
   its pack got no starter gear and no weapon-skill floor.
3. The new life's practices and trains were clamped to 30,000, cutting a
   larger balance the field holds legitimately (SHRT_MAX).

A synthetic level 54 warrior with a pony (mob 2436) at the altar, its
school kit taken off, remorts into a mage.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zremort12"
ALTAR = 4208
TEMPLE = 4207
PONY = 2436
STARTING_WEAPON_SKILL = 40

PET = """#PET
Vnum %d
Name horse pony pet~
Sex  0
Levl 1
HMV  20 20 100 100 100 100
End

""" % PONY


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def saved(mud, name: str) -> str:
    return (mud.player_dir / name).read_text(encoding="latin-1")


@unittest.skipIf(SKIP is not None, SKIP or "")
class RemortReportTests(unittest.TestCase):
    def test_pet_gear_and_balances_survive_a_remort(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zreborn", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zreborn", Levl=54, Room=ALTAR, Prac=31000, Trai=31000)
            path = mud.player_dir / "Zreborn"
            text = path.read_text(encoding="latin-1")
            path.write_text(text.replace("#END", PET + "#END", 1), encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zreborn", PW)
                run(client, "scroll 0")
                self.assertIn("pony", run(client, "look").lower())
                # The old school kit, carried rather than worn.
                run(client, "remove all", 1.5)
                said = run(client, "remort %s mage none human" % PW, 3.5)
                self.assertNotIn("already have some equipment", said, said)
                self.assertIn("equipped by the Gods", said, said)

                # Moved to the Temple, and the pony with them.
                here = run(client, "look")
                self.assertIn("pony", here.lower(), here)
                worn = run(client, "equipment").lower()
                for piece in ("dagger", "banner", "vest", "shield"):
                    self.assertIn(piece, worn, worn)
                # OUTFIT again makes nothing new.
                self.assertIn("already equipped", run(client, "outfit"))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            text = saved(mud, "Zreborn")
            self.assertIn("#PET", text, "the pony is saved")
            self.assertRegex(text, r"(?m)^Room %d$" % TEMPLE)
            self.assertRegex(text, r"(?m)^Prac 31017$")
            self.assertRegex(text, r"(?m)^Trai 31010$")
            dagger = re.search(r"(?m)^Sk (\d+) 'dagger'$", text)
            self.assertIsNotNone(dagger, "the new mage holds the dagger skill")
            self.assertGreaterEqual(int(dagger.group(1)), STARTING_WEAPON_SKILL,
                                    "and it is floored for the new life")

            with mud.connect(timeout=120) as client:
                login(client, "Zreborn", PW)
                self.assertIn("pony", run(client, "look").lower())
                client.send("quit")
                self.assertTrue(client.wait_closed())

    def test_a_full_balance_stays_full(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcapped", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcapped", Levl=54, Room=TEMPLE, Prac=32767, Trai=29999)
            with mud.connect(timeout=120) as client:
                login(client, "Zcapped", PW)
                run(client, "remort %s mage none human" % PW, 3.5)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = saved(mud, "Zcapped")
            self.assertRegex(text, r"(?m)^Prac 32767$")
            self.assertRegex(text, r"(?m)^Trai 30009$")

    def test_a_broken_starter_piece_is_not_put_on(self) -> None:
        """Review 2026-10-21: OUTFIT's new slot filler equipped a carried
        starter piece without WEAR's checks, so a broken vest went on
        unrepaired. A broken copy stays in the pack; a new one is made."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbrokevest", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbrokevest", Levl=54, Room=TEMPLE)
            path = mud.player_dir / "Zbrokevest"
            text = path.read_text(encoding="latin-1")
            text = re.sub(r"#O\nVnum 3703\nNest 0\nWear \d+\n(.*?)Cond \d+\n",
                          lambda m: "#O\nVnum 3703\nNest 0\nWear -1\nExtF 67108864\n"
                                    + m.group(1) + "Cond 0\n", text, count=1, flags=re.S)
            self.assertIn("ExtF 67108864", text)
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zbrokevest", PW)
                run(client, "scroll 0")
                self.assertIn("damaged and cannot be used", run(client, "wear vest"))
                run(client, "remort %s mage none human" % PW, 3.5)
                worn = run(client, "equipment")
                self.assertIn("vest", worn.lower(), worn)
                self.assertNotIn("Damaged", worn, "the broken vest is not what went on")
                self.assertIn("Damaged", run(client, "inventory"), "and it is kept, still broken")
                client.send("quit")
                self.assertTrue(client.wait_closed())

    def test_a_monk_with_a_kept_sword_still_fights_unarmed(self) -> None:
        """Review 2026-10-21: a remort into monk that kept a school sword
        floored sword and left hand to hand at the group's 1%."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmonkish", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmonkish", Levl=54, Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zmonkish", PW)
                run(client, "scroll 0")
                run(client, "remort %s monk none human" % PW, 3.5)
                self.assertNotIn("dagger", run(client, "equipment").lower())
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = saved(mud, "Zmonkish")
            hand = re.search(r"(?m)^Sk (\d+) 'hand to hand'$", text)
            self.assertIsNotNone(hand, text[:400])
            self.assertGreaterEqual(int(hand.group(1)), STARTING_WEAPON_SKILL)


if __name__ == "__main__":
    unittest.main()
