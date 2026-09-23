"""A shop price says what it costs.

LIST printed a bare number while obj->cost is gold and add_money multiplies
it by COPPER_PER_GOLD, so a loaf showing "1" took ten thousand copper out
of the purse. That is how somebody ends up asking why the bread in Mud
School costs a gold piece.
"""
from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zshopone1"

# The Adept of Gravestone, who sells the Mud School bread.
ADEPT_ROOM = 3718


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShopPriceTests(unittest.TestCase):
    def test_list_shows_the_denomination(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zshopper", PASSWORD)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zshopper", Levl=70)

            with mud.connect(timeout=120) as client:
                login(client, "Zshopper", PASSWORD)
                run(client, f"goto {ADEPT_ROOM}", settle=4.0)
                listed = run(client, "list", settle=4.0)

            self.assertNotIn("I don't sell", listed,
                             f"the adept should have stock:\n{listed}")
            # A price now carries its unit rather than being a bare number.
            self.assertRegex(
                listed, r"\d+[pgsc]",
                f"prices should name their denomination:\n{listed}")


if __name__ == "__main__":
    unittest.main()
