"""Shops charge the purse, not the loose change in it.

A price is quoted in copper and was charged with
`can_adjust_coin_balance(ch, -cost, TYPE_COPPER)`, which reads one field:
`ch->new_copper`. So a character carrying two and a half million platinum
was told they could not afford a twenty-two silver loaf of bread, because
they had a hundred and seventy-five loose coppers on them and the baker
would not break anything larger. Nobody could buy anything they were not
already carrying exact change for, and selling had the mirror of it --
`cost > keeper->new_gold` compared a copper price against a count of gold
coins, and the payment arrived as one enormous pile of copper.

These run against a real server in a throwaway tree.
"""
from __future__ import annotations

import re
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

PASSWORD = "Zpurse1"
DRESDEN_BAKERY = 2488
DRESDEN_WEAPONSMITH_SHOP = 2494

COIN_VALUE = {"platinum": 1000000, "gold": 10000, "silver": 100, "copper": 1}


def purse(text: str) -> int:
    """Total copper from a WORTH line, whichever coins it names."""
    return sum(
        int(count) * COIN_VALUE[unit]
        for count, unit in re.findall(
            r"(\d+) (platinum|gold|silver|copper)", text
        )
    )


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShopPurseTests(unittest.TestCase):
    def character(self, mud: LiveMud, name: str, **fields: object) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PASSWORD)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, name, **fields)

    def test_a_rich_character_can_buy_a_cheap_loaf(self) -> None:
        """The purse from the report, to the coin."""
        with LiveMud() as mud:
            self.character(
                mud, "Richguy", Levl=60, Room=DRESDEN_BAKERY,
                NewPlat=2508593, NewGold=265, NewSilv=161, NewCopp=175,
            )
            with mud.connect(timeout=120) as client:
                login(client, "Richguy", PASSWORD)
                before = purse(run(client, "worth", 1.5))
                self.assertGreater(before, 0)

                bought = run(client, "buy bread", 1.6)
                self.assertIn("You buy", bought, bought)
                self.assertNotIn("can't afford", bought)

                after = purse(run(client, "worth", 1.5))
                self.assertLess(after, before, "the loaf was free")
                # 22 silver at the baker's 110% markup.
                self.assertEqual(before - after, 22 * COIN_VALUE["silver"])

    def test_one_platinum_coin_buys_a_one_copper_loaf(self) -> None:
        """Change has to come out of the coin you have, not the one you
        wish you had."""
        with LiveMud() as mud:
            self.character(
                mud, "Onecoin", Levl=5, Room=3241,
                NewPlat=1, NewGold=0, NewSilv=0, NewCopp=0,
            )
            with mud.connect(timeout=120) as client:
                login(client, "Onecoin", PASSWORD)
                before = purse(run(client, "worth", 1.5))
                self.assertEqual(before, COIN_VALUE["platinum"])

                self.assertIn("You buy", run(client, "buy bread", 1.6))
                self.assertEqual(
                    purse(run(client, "worth", 1.5)),
                    COIN_VALUE["platinum"] - 1,
                )

    def test_selling_pays_in_coins_the_seller_can_carry(self) -> None:
        """The payment used to arrive as its own weight in copper."""
        with LiveMud() as mud:
            self.character(
                mud, "Seller", Levl=10, Room=DRESDEN_WEAPONSMITH_SHOP,
                NewPlat=1, NewGold=0, NewSilv=0, NewCopp=0,
            )
            with mud.connect(timeout=120) as client:
                login(client, "Seller", PASSWORD)
                self.assertIn("You buy", run(client, "buy dagger", 1.6))
                before = purse(run(client, "worth", 1.5))

                sold = run(client, "sell dagger", 1.6)
                self.assertIn("You sell", sold, sold)
                self.assertNotIn("cannot safely carry", sold)
                self.assertGreater(purse(run(client, "worth", 1.5)), before)


class PurseSourceTests(unittest.TestCase):
    """The shop paths must go through the purse helpers, not one pile."""

    def test_buying_and_selling_use_the_whole_purse(self) -> None:
        source = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")

        header = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        for helper in ("has_enough_copper", "spend_copper", "gain_copper",
                       "query_carry_copper"):
            with self.subTest(helper=helper):
                self.assertIn(helper, header)

        # Only the two shop commands are searched, so the comment above
        # the helpers -- which quotes the call it replaced -- is not read
        # as the call itself.
        for name in ("void do_buy", "void do_sell"):
            body = source.split(name, 1)[1].split(chr(10) + "void ", 1)[0]
            with self.subTest(command=name):
                self.assertNotIn("adjust_coin_balance", body)
                self.assertNotIn("keeper->new_gold", body)
                self.assertIn("_copper(", body)


if __name__ == "__main__":
    unittest.main()
