"""An idle immortal must not fill a one-person room.

ROOM_SOLITARY closes a room once one person is in it and ROOM_PRIVATE
once two are. The count included everybody, so an immortal standing in
the quest room -- watching, building, or simply idle -- shut questing
down for every player on the mud. The flag exists to stop players
walking in on each other, not to let staff close a room by standing in
it.

The other half: every caller asked `ch->level < 69` rather than
`get_trust(ch)`, and 69 rather than immortal rank, so an ordinary
immortal was turned away from a private room and a builder trusted to
immortal rank was turned away from all of them -- the same class of bug
as the INVULN one. `can_enter_private_room()` is the one place that
decides it now.

ROOM_IMP_ONLY is not an occupancy limit and keeps the bar it had.

These are source tests. Reaching the live path needs two characters, a
solitary room and the geography to walk into it; the logic is one
function and reads plainly, so it is pinned here instead.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PrivateRooms(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        cls.move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")

    def body(self, text: str, fn: str) -> str:
        return text.split(fn)[1].split(chr(10) + "}")[0]

    def test_staff_do_not_count_towards_the_limit(self) -> None:
        body = self.body(self.handler, "bool room_is_private(")
        self.assertIn("IS_TRUSTED(rch, LEVEL_IMMORTAL)", body)
        self.assertLess(
            body.index("IS_TRUSTED(rch, LEVEL_IMMORTAL)"),
            body.index("count++"),
            "the skip has to come before the increment",
        )

    def test_one_helper_decides_who_may_walk_in(self) -> None:
        body = self.body(self.handler, "bool can_enter_private_room(")
        self.assertIn("IS_TRUSTED( ch, LEVEL_IMMORTAL )", body)
        self.assertIn(
            "bool    can_enter_private_room ( CHAR_DATA *ch, "
            "ROOM_INDEX_DATA *pRoomIndex );",
            self.merc,
            "declared in the header, not implicitly",
        )

    def test_an_implementor_only_room_keeps_its_own_bar(self) -> None:
        """It is not an occupancy limit, so the override must miss it."""
        body = self.body(self.handler, "bool can_enter_private_room(")
        self.assertIn("ROOM_IMP_ONLY", body)
        self.assertIn("get_trust( ch ) >= GOD", body)
        self.assertLess(
            body.index("ROOM_IMP_ONLY"),
            body.index("IS_TRUSTED( ch, LEVEL_IMMORTAL )"),
            "the implementor test has to be reached first",
        )

    def test_no_caller_reads_a_raw_level_any_more(self) -> None:
        """get_trust(), not ch->level, and rank rather than the number 69."""
        offenders = []
        for name, text in (("act_move.c", self.move), ("act_wiz.c", self.wiz)):
            for m in re.finditer(r"room_is_private\s*\([^)]*\)[^;{]*", text):
                clause = m.group(0)
                if "level < 69" in clause or "get_trust(ch) < 69" in clause:
                    offenders.append("%s: %s" % (name, clause.strip()[:70]))
        self.assertEqual(
            offenders, [],
            "these still gate a private room on a raw level:" + chr(10)
            + chr(10).join(offenders),
        )

    def test_movement_and_the_staff_commands_all_use_the_helper(self) -> None:
        self.assertIn("if ( !can_enter_private_room( ch, to_room ) )", self.move)
        self.assertIn(
            "if ( !can_enter_private_room( temp_ch, to_room ) )", self.move,
            "the mounted path too",
        )
        self.assertEqual(
            self.wiz.count("if ( !can_enter_private_room( ch, location ) )"), 4,
            "transfer, at, goto and itrans",
        )


if __name__ == "__main__":
    unittest.main()
