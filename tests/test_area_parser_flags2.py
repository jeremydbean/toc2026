"""The dashboard parser reads an object's flag line in the game's order.

load_objects reads "type extra [extra2] wear", and extra2 is there only
when the extra flags carry ITEM_FLAGS2 (Z). The dashboard parser used to
take the fourth token as extra2 instead, swapping the two on every such
object: Starlight, a dwarf-only light, read as human-only and worn on the
neck, so the gear finder never showed it to a dwarf.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin.area_parser import (  # noqa: E402
    ITEM_FLAGS2, WEAR_FLAGS, AreaParser, decode_flags)

AREA = """#OBJECTS
#100
starlight~
Starlight~
A gleam of Starlight.~
adamantite~
1 AGWZ C AO
0 0 999 0 0
45 5 100 P
#101
banner~
a banner~
A banner.~
cloth~
1 A AO
0 0 9999 0 0
35 10 100 P
#102
pool~
a pool~
A pool.~
stone~
30 VZ I 0
5 13401 0 0 0
1 1 2 P
#0

#ROOMS
"""


class Flags2OrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = AreaParser(ROOT / "area")
        self.parser._parse_objects(AREA, "test.are", "Test")

    def test_extra2_comes_before_the_wear_flags(self) -> None:
        star = self.parser.objects[100]
        self.assertEqual(decode_flags(star.extra_flags2, ITEM_FLAGS2), ["dwarf-only"])
        self.assertEqual(decode_flags(star.wear_flags, WEAR_FLAGS), ["take", "hold"])
        self.assertEqual(star.values, ["0", "0", "999", "0", "0"])
        self.assertEqual(star.level, 45)

    def test_without_the_flags2_bit_the_third_token_is_wear(self) -> None:
        banner = self.parser.objects[101]
        self.assertEqual(banner.extra_flags2, "0")
        self.assertEqual(decode_flags(banner.wear_flags, WEAR_FLAGS), ["take", "hold"])

    def test_a_zero_wear_field_after_extra2(self) -> None:
        pool = self.parser.objects[102]
        self.assertEqual(pool.extra_flags2, "I")
        self.assertEqual(pool.wear_flags, "0")
        self.assertEqual(pool.values[1], "13401")


if __name__ == "__main__":
    unittest.main()
