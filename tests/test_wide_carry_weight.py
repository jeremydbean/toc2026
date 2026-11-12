"""What a character carries is counted past 32,767.

Strict-warnings sweep, 2026-11-12: -Wconversion named `ch->carry_weight +=
get_obj_weight( obj )` -- an int added into a 16-bit field. Past 32,767 the
weight wrapped negative, and query_carry_weight(), which refuses a negative
total, then answered INT_MAX: SCORE read "Encumbrance: 2147483647" and every
weight check after it compared against that. Only those with no carrying
limit (staff, and the fifth remort) can get there, which is why nobody saw
it. carry_weight, carry_number, hitroll, damroll, armour, saving throw,
the stat modifiers and lag are ints now, as the pools are.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zheavy1pass"
TEMPLE = 4207
SILVER_PLATE = 631          # body armour, ofcol.are: takeable, holds nothing
HEAVY = 20000               # fits an object's own 16-bit weight


def encumbrance(client) -> int:
    reply = client.sync("score")
    found = re.findall(r"Encumbrance:\s+(-?\d+)", reply)
    assert found, reply
    return int(found[-1])


@unittest.skipIf(SKIP is not None, SKIP or "")
class WideCarryWeightTests(unittest.TestCase):
    def test_two_heavy_pieces_weigh_what_they_weigh(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zheavy", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # Staff carry without limit (can_carry_w), so the weight can
            # pass 32,767 by picking things up.
            patch_player_file(mud, "Zheavy", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zheavy", PASSWORD)
                before = encumbrance(client)
                for _ in range(2):
                    client.must("load obj %d" % SILVER_PLATE, "You create")
                # Weighed down on the floor, so what is picked up is the
                # weight carried (carry_weight is counted at obj_to_char).
                client.sync("drop all.plate")
                client.must("set obj 1.plate weight %d" % HEAVY, "Weight on")
                client.must("set obj 2.plate weight %d" % HEAVY, "Weight on")
                got = client.sync("get all.plate")
                self.assertEqual(got.lower().count("you get"), 2, got)

                after = encumbrance(client)
                self.assertEqual(after, before + 2 * HEAVY,
                                 "carry weight wrapped at 16 bits")

                # And it comes off again exactly.
                client.sync("drop all.plate")
                self.assertEqual(encumbrance(client), before)


if __name__ == "__main__":
    unittest.main()
