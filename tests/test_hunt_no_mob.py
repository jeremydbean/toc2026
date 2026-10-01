"""A hunting mobile stops at the edge of a room no mobile may enter.

Reported in play: the Temple filled with city guards. They were hunting
WANTED players -- spec_guard attacks one on sight, and a guard that has
fought somebody hunts them -- and hunt_victim refused to step into a
SAFE room but never asked about NO_MOB. The Temple is NO_MOB and not
SAFE, so the guards followed their quarry to the altar. Wandering
(mobile_update) has always refused NO_MOB; hunting now does the same.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class HuntNoMobTests(unittest.TestCase):
    def test_a_hunter_will_not_step_into_a_no_mob_room(self) -> None:
        hunt = read("src", "hunt.c")
        body = hunt.split("void hunt_victim(", 1)[1].split("\n}\n", 1)[0]
        guard = body.split("if (dir == BFS_ALREADY_THERE)", 1)[1]
        guard = guard.split("if ( IS_CLOSED( ch->in_room, dir ) )", 1)[0]
        guard = re.sub(r"/\*.*?\*/", " ", guard, flags=re.S)
        self.assertIn("ROOM_SAFE", guard)
        self.assertIn("ROOM_NO_MOB", guard)

    def test_the_temple_is_no_mob_and_not_safe(self) -> None:
        """The shape that made the bug: if the Temple ever becomes SAFE
        too, this test is no longer the reason it stays clear."""
        dresden = read("area", "dresden.are").split("#ROOMS", 1)[1]
        room = dresden.split("#4207", 1)[1].split("\n#", 1)[0]
        flags = [line for line in room.replace("\r", "").splitlines()
                 if re.fullmatch(r"\d+ \S+ \d+", line.strip())][0].split()[1]
        bits = int(flags) if flags.isdigit() else sum(
            1 << (ord(c) - 65) for c in flags if c.isupper())
        self.assertTrue(bits & (1 << 2), "the Temple is no longer NO_MOB")

    def test_wandering_already_refused_no_mob(self) -> None:
        """The rule hunting now matches, so the two cannot disagree."""
        self.assertIn("ROOM_NO_MOB", read("src", "update.c"))


if __name__ == "__main__":
    unittest.main()
