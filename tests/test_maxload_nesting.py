"""Limited items keep their count however they are packed.

Audit 2026-10-21: the four transfer functions counted an object and at
most its immediate contents into or out of what players own. A bag
holding a limited item, put into another carried bag, left the item
counted as back in the world -- maxload.txt undercounted it and, after a
reboot, a reset would load another -- and quitting with it two deep then
counted it once too often. maxload_subtree() in handler.c counts the
whole tree at every change of hands.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zpacker1"
TEMPLE = 4207
DIPLOMA = 3715          # school.are, limited in maxload.txt
BAG = 3032


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def owned(mud) -> int:
    text = (mud.root / "area" / "maxload.txt").read_text(encoding="latin-1")
    return int(re.search(r"(?m)^ML %d (\d+) " % DIPLOMA, text).group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class MaxloadNestingTests(unittest.TestCase):
    def test_packing_a_bag_into_a_bag_keeps_the_count(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpacker", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zpacker", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zpacker", PASSWORD)
                run(client, "scroll 0")
                start = owned(mud)
                run(client, "load obj %d" % DIPLOMA)
                held = owned(mud)
                self.assertEqual(held, start + 1, "carrying it is owning it")

                run(client, "load obj %d" % BAG)
                run(client, "load obj %d" % BAG)
                run(client, "put diploma bag")           # into the newer bag
                self.assertEqual(owned(mud), held)
                run(client, "put bag 2.bag")              # that bag into the other
                self.assertEqual(owned(mud), held, "two deep, still owned")
                run(client, "get bag bag")
                self.assertEqual(owned(mud), held)
                run(client, "put bag bag")
                self.assertEqual(owned(mud), held)

                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertEqual(owned(mud), held, "leaving the game changes no ownership")

            with mud.connect(timeout=120) as client:
                login(client, "Zpacker", PASSWORD)
                client.drain(1.0)
                self.assertIn("diploma", run(client, "look in bag", 1.2) +
                              run(client, "look in 2.bag", 1.2) +
                              run(client, "get bag bag", 1.0) +
                              run(client, "look in bag", 1.2))
                self.assertEqual(owned(mud), held)


if __name__ == "__main__":
    unittest.main()
