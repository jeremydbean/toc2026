"""A chest somebody has just opened stays open.

obj_update locks every keyed container on each tick, and now and then traps
one, so a chest left lying about is locked again for the next visitor. It
used to do that to every container in the world, including the one a player
had unlocked and opened a second before -- the lid slammed and locked
between OPEN and GET whenever a tick fell there, and a keyed box in a pack
locked itself in its owner's hands. Hyrule's Triforce chests showed it: the
walkthrough and the dungeon chain test failed in CI with "The chest is
closed" whenever the tick landed mid-sequence (2026-10-05).

The relock now asks for a container lying in a room no player is in.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContainerRelockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        start = update.index("void obj_update( void )")
        cls.body = update[start:update.index("\n}\n", start)]
        cls.update = update

    def test_the_relock_only_touches_an_unattended_chest_in_a_room(self) -> None:
        relock = self.body.index("obj->value[1] = 13;")
        guard = self.body.rindex("if(obj->item_type == ITEM_CONTAINER", 0, relock)
        condition = self.body[guard:relock]
        self.assertIn("obj->in_room != NULL", condition)
        self.assertIn("!room_has_player( obj->in_room )", condition)

    def test_the_trap_roll_sits_inside_the_same_guard(self) -> None:
        relock = self.body.index("obj->value[1] = 13;")
        guard = self.body.rindex("if(obj->item_type == ITEM_CONTAINER", 0, relock)
        trap = self.body.index("SET_BIT(obj->value[1], CONT_TRAPPED)")
        self.assertLess(guard, trap)
        # Nothing between the guard and the trap closes the guarded block.
        block = self.body[guard:trap]
        self.assertEqual(block.count("{") - block.count("}"), 2, block)

    def test_any_player_counts_as_somebody_there(self) -> None:
        helper = re.search(r"static bool room_has_player\(.*?\n}\n", self.update, re.S)
        self.assertIsNotNone(helper)
        self.assertIn("!IS_NPC(rch)", helper.group(0))


if __name__ == "__main__":
    unittest.main()
