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


if __name__ == "__main__":
    unittest.main()
