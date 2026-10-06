"""In-game building, phase 5: PLACE, RESETS and UNPLACE.

A reset is what brings a mobile, an object or a door's state back. The
list is order sensitive -- an item a mobile wears follows that mobile's
reset, an item in a chest follows the chest's -- and PLACE keeps that
order for the builder. The test places a smith who wields a sword, a
chest with something in it, and a locked door; reads them back with
RESETS; takes the chest out with UNPLACE (its contents go with it); saves,
reboots, and finds the smith armed, the door locked and the list the same.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw5"
LO, HI = 21300, 21319
ROOM, NORTH = 21301, 21302
SMITH, SWORD, CHEST, NUGGET = 21303, 21304, 21305, 21306


def run(client, command: str, settle: float = 1.0) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def reset_lines(text: str) -> list[str]:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text.replace("\r", ""))
    return [line.strip() for line in text.split("\n")
            if re.match(r"\s*\d+\. ", line)]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetTests(unittest.TestCase):
    def test_placed_things_come_back_after_a_reboot(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbuildfive", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuildfive", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildfive", PASSWORD)
                run(imm, "scroll 0")

                # Outside an ANEW area nothing can be placed.
                self.assertIn("only an area made with ANEW", run(imm, "place mob 3011"))

                self.assertIn("Created area", run(imm, f"anew {LO} {HI} Zed Placing Works"))
                run(imm, f"goto {ROOM}", 1.5)
                run(imm, f"rlink north {NORTH}", 1.5)
                run(imm, "rlink north door", 1.5)

                run(imm, f"mcreate {SMITH}")
                run(imm, f"set mob {SMITH} keywords smith")
                run(imm, f"set mob {SMITH} short the smith")
                run(imm, f"set mob {SMITH} long The smith waits here.")
                run(imm, f"ocreate {SWORD} 3021")
                run(imm, f"ocreate {CHEST}")
                run(imm, f"set obj {CHEST} keywords chest")
                run(imm, f"set obj {CHEST} short a chest")
                run(imm, f"set obj {CHEST} type container")
                run(imm, f"set obj {CHEST} capacity 50")
                run(imm, f"ocreate {NUGGET}")

                self.assertIn("will be here", run(imm, f"place mob {SMITH}", 1.5))
                out = run(imm, f"place obj {SWORD} worn {SMITH}", 1.5)
                self.assertIn("wielded", out, out)
                self.assertIn("will lie here", run(imm, f"place obj {CHEST}", 1.5))
                self.assertIn("put back in a chest",
                              run(imm, f"place obj {NUGGET} in {CHEST}", 1.5))
                self.assertIn("Name a container placed in this room",
                              run(imm, f"place obj {NUGGET} in 21399"))
                self.assertIn("Name a mobile placed in this room",
                              run(imm, f"place obj {SWORD} on 21399"))
                out = run(imm, "place door north locked", 1.5)
                self.assertIn("from both sides", out, out)
                self.assertIn("locked", run(imm, "open north"))

                lines = reset_lines(run(imm, "resets", 1.5))
                self.assertEqual(len(lines), 5, lines)
                self.assertIn(f"mobile {SMITH}, the smith", lines[0])
                self.assertIn(f"object {SWORD}", lines[1])
                self.assertIn("wielded", lines[1])
                self.assertIn(f"object {CHEST}, a chest, on the floor", lines[2])
                self.assertIn("in a chest", lines[3])
                self.assertIn("door north, locked", lines[4])

                out = run(imm, "unplace 3", 1.5)
                self.assertIn("and what it carried or held", out, out)
                kept = reset_lines(run(imm, "resets", 1.5))
                self.assertEqual(len(kept), 3, kept)
                self.assertIn("door north, locked", kept[2])

                self.assertIn("Saved Zed Placing Works", run(imm, "asave", 2.0))
                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildfive", PASSWORD)
                run(imm, "scroll 0")
                run(imm, f"goto {ROOM}", 1.5)
                self.assertEqual(reset_lines(run(imm, "resets", 1.5)), kept)
                self.assertIn("The smith waits here.", run(imm, "look", 1.5))
                self.assertIn("wielded", run(imm, "look smith", 1.5).lower())
                self.assertIn("locked", run(imm, "open north"))
                self.assertNotIn("a chest", run(imm, "look", 1.5))


if __name__ == "__main__":
    unittest.main()
