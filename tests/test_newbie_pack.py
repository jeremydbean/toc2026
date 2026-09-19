"""The NEWBIE command and the two endless items.

`newbie` conjures a renamed metallic pack already full of starter gear;
`newbie <player>` hands it to someone with a bit of ceremony. The contents
live in C rather than in an area file, so this test is what notices when one
of the fifteen vnums is renumbered out from under it -- the command warns
rather than failing, and a silent warning is exactly what gets missed.

The endless jug and snack pack are marked in their object data (value[4]),
not by vnum, so the check here is behavioural: use them and confirm they are
still in inventory afterwards.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

IMMORTAL_LEVEL = 70
PASSWORD = "Znewbiepw1"


def run(client, command: str, settle: float = 1.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class NewbiePackTests(unittest.TestCase):
    def test_newbie_alone_conjures_a_full_pack(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewbone")
            with mud.connect(timeout=120) as client:
                login(client, "Znewbone", PASSWORD)
                output = run(client, "newbie", settle=3.0)

                # Every vnum in the table has to still exist.
                self.assertNotIn(
                    "could not be created",
                    output,
                    f"a pack item is missing from the world:\n{output}",
                )
                self.assertIn("NEWBIE", output.upper(), output)

                inventory = run(client, "inventory", settle=2.0)
                self.assertIn("NEWBIE", inventory.upper(), inventory)

                contents = run(client, "look in pack", settle=2.5)
                # Pot pies and the plain water jug were replaced by the
                # endless pair, which never run out.
                for expected in ("diploma", "endless snack pack", "sanctuary"):
                    self.assertIn(
                        expected,
                        contents.lower(),
                        f"{expected} missing from the pack:\n{contents}",
                    )

    def test_newbie_at_a_player_hands_it_over(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewbtwo")
            with mud.connect(timeout=120) as giver:
                login(giver, "Znewbtwo", PASSWORD)
                with mud.connect(timeout=120) as taker:
                    create_character(taker, "Znewbthr", PASSWORD)
                    run(giver, "newbie Znewbthr", settle=3.0)
                    # The recipient's socket has to be read before their
                    # transcript reflects anything the giver caused.
                    taker.drain(2.5)
                    received = taker.transcript
                    self.assertIn(
                        "gear you need to get started",
                        received,
                        f"the recipient got no ceremony:\n{received[-800:]}",
                    )
                    inventory = run(taker, "inventory", settle=2.0)
                    self.assertIn("NEWBIE", inventory.upper(), inventory)

    def test_the_endless_jug_and_snack_are_not_consumed(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewbfor")
            with mud.connect(timeout=120) as client:
                login(client, "Znewbfor", PASSWORD)
                run(client, "load obj 3093", settle=2.0)
                run(client, "load obj 3094", settle=2.0)

                inventory = run(client, "inventory", settle=2.0)
                self.assertIn("endless water jug", inventory.lower(), inventory)
                self.assertIn("endless snack pack", inventory.lower(), inventory)

                # Drink and eat several times; both must survive.
                for _ in range(3):
                    run(client, "drink jug", settle=1.0)
                    run(client, "eat snack", settle=1.0)

                after = run(client, "inventory", settle=2.0)
                self.assertIn(
                    "endless water jug",
                    after.lower(),
                    f"the jug ran dry or vanished:\n{after}",
                )
                self.assertIn(
                    "endless snack pack",
                    after.lower(),
                    f"the snack pack was eaten:\n{after}",
                )


if __name__ == "__main__":
    unittest.main()
