"""BUY <count> <item> and TRAIN <stat> <count>, played.

The command log showed players typing BUY FLY thirteen times running and
TRAIN HP twelve (2026-10-05). Both take a count now and repeat the single
command, so every purchase and every session takes the checks one would,
and the first refusal stops the run.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zcountpw1"
SHOP = 2474         # the wizard, Magic Street: sells potions of fly
TRAINER = 4720      # the Undead Spirit trains


def run(client, command: str, settle: float = 2.0) -> str:
    client.drain(0.4)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CountTests(unittest.TestCase):
    def test_buy_and_train_take_a_count(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcountbuy", Levl=20, Room=SHOP, NewPlat=1000)
            make(mud, "Zcounttrain", Levl=20, Room=TRAINER, Trai=7)
            with mud.connect(timeout=120) as buyer:
                login(buyer, "Zcountbuy", PASSWORD)
                bought = run(buyer, "buy 5 fly", 3.0)
                self.assertEqual(5, bought.count("You buy"), bought)
                self.assertNotIn("asked for", bought, bought)
                self.assertIn("Buy how many?", run(buyer, "buy 99999 fly"))
                self.assertIn("Buy how many?", run(buyer, "buy 0 fly"))
                # The position index still means which one, not how many.
                self.assertEqual(1, run(buyer, "buy 1.fly").count("You buy"))
            with mud.connect(timeout=120) as trainee:
                login(trainee, "Zcounttrain", PASSWORD)
                before = int(re.search(r"<(\d+)hp", run(trainee, "score")).group(1))
                trained = run(trainee, "train hp 3", 3.0)
                self.assertEqual(3, trained.count("Your durability increases!"), trained)
                after = int(re.search(r"<(\d+)hp", run(trainee, "score")).group(1))
                self.assertEqual(before + 30, after)
                # Four sessions are left: asking for ten trains four and says so.
                rest = run(trainee, "train mana 10", 3.0)
                self.assertEqual(4, rest.count("Your power increases!"), rest)
                self.assertIn("You trained 4 of the 10 you asked for.", rest)
                self.assertIn("Train how many?", run(trainee, "train hp lots"))


if __name__ == "__main__":
    unittest.main()
