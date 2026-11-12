"""A new trap's WIZINFO says where it is and what it does (owner,
2026-11-12: "wizinfo shows traps but doesn't say where -- just the vnum").

A reset that traps a locked door said "New Trap: [Room: N]", and a chest
that grows a trap on the tick said "New Object Trap: <name> [Vnum: N]" --
the object's vnum, never the room. Both now name the trap's kind, the
room by name and number, its area and, for a door, its direction. The
kinds are trap_kind_name()'s, in trapped()'s own order.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


class TrapNoticeTests(unittest.TestCase):
    def test_a_door_trap_names_its_room_area_and_door(self) -> None:
        db = source("db.c")
        self.assertNotIn('"New Trap: [Room: %d]"', db)
        self.assertIn('"New %s trap on the %s door of %s [room %d], %s."', db)
        notice = db.split('"New %s trap on the %s door of %s [room %d], %s."', 1)[1][:600]
        for part in ("trap_kind_name( pexit->trap )", "dir_name[pReset->arg2]",
                     "pRoomIndex->name", "pRoomIndex->vnum", "area_shown_name"):
            self.assertIn(part, notice)

    def test_a_chest_trap_names_where_it_lies(self) -> None:
        update = source("update.c")
        self.assertNotIn('"New Object Trap: %s [Vnum: %d]"', update)
        notice = update.split('"New %s trap on %s [object %d] in %s [room %d], %s."', 1)[1][:600]
        for part in ("trap_kind_name( obj->value[4] )", "obj->in_room->name",
                     "obj->in_room->vnum", "area_shown_name"):
            self.assertIn(part, notice)

    def test_kind_names_follow_trapped(self) -> None:
        move = source("act_move.c")
        names = re.search(r'const char \*trap_kind_name\( int kind \).*?\{(.*?)\};',
                          move, re.S).group(1)
        kinds = re.findall(r'"([a-z]+)"', names)
        self.assertEqual(kinds[0], "unknown")
        trapped = move.split("void trapped( CHAR_DATA *ch, OBJ_DATA *obj, int find_trap )", 1)[1]
        cases = sorted({int(n) for n in re.findall(r"^\s*case (\d+):", trapped, re.M) if int(n) <= 10})
        self.assertEqual(cases, list(range(1, 11)), "trapped() handles kinds 1 to 10")
        self.assertEqual(len(kinds) - 1, len(cases), "one name a kind")


if __name__ == "__main__":
    unittest.main()
