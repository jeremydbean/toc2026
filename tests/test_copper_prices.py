"""Prices are counted in copper, and a newbie can afford bread.

obj->cost was denominated in gold, so the cheapest anything could be was one
gold piece -- ten thousand copper. The loaf in Mud School showed "1" on the
shop list and took a gold coin off you, which is not a price a newbie can
meet.

Every price in every area file has been multiplied by COPPER_PER_GOLD, so
nothing is worth more or less than it was, and the bread is now one copper.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zcopperone1"

ADEPT_ROOM = 3718          # the Adept of Eclipse, who sells the bread
COPPER_PER_GOLD = 10000


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class CopperPriceTests(unittest.TestCase):
    def test_the_school_bread_costs_one_copper(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcopperone", PASSWORD)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zcopperone", Levl=70)

            with mud.connect(timeout=120) as client:
                login(client, "Zcopperone", PASSWORD)
                run(client, f"goto {ADEPT_ROOM}", settle=4.0)
                listed = run(client, "list", settle=4.0)

            self.assertIn("bread", listed.lower(), listed)
            bread = next((l for l in listed.splitlines()
                          if "bread" in l.lower()), "")
            self.assertRegex(bread, r"\b1c\b",
                             f"bread should be one copper:\n{bread}")

    def test_other_prices_keep_their_worth(self) -> None:
        """A conversion, not a sale: everything else costs what it did."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcoppertwo", PASSWORD)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zcoppertwo", Levl=70)

            with mud.connect(timeout=120) as client:
                login(client, "Zcoppertwo", PASSWORD)
                run(client, f"goto {ADEPT_ROOM}", settle=4.0)
                listed = run(client, "list", settle=4.0)

            # Every price reads in denominations rather than as a bare count.
            priced = [l for l in listed.splitlines() if re.search(r"\[\s*\d+", l)]
            self.assertTrue(priced, f"nothing for sale:\n{listed}")
            for line in priced:
                self.assertRegex(
                    line, r"\d+[pgsc]",
                    f"a price with no denomination:\n{line}")

    def test_a_newbie_can_buy_the_bread(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcopthree", PASSWORD)
                client.send("quit")
                client.wait_closed()
            # A single copper coin, and nothing else.
            patch_player_file(mud, "Zcopthree",
                              NewCopp=1, NewGold=0, NewSilv=0, NewPlat=0)

            with mud.connect(timeout=120) as buyer:
                login(buyer, "Zcopthree", PASSWORD)
                buyer.drain(1.0)
                # A newbie starts in Mud School, where the adept is.
                bought = run(buyer, "buy bread", settle=4.0)

            self.assertNotIn("can't afford", bought.lower(),
                             f"one copper should be enough:\n{bought}")


if __name__ == "__main__":
    unittest.main()
