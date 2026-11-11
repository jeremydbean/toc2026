"""No item is capped (owner, 2026-11-11: "no need to cap anything. remove
the caps").

Resets ask do_maxload_item before loading a limited object; it now always
says yes. The counts in area/maxload.txt are still kept -- MAXLOADS shows
them -- but no figure in that file refuses a load any more.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaxloadUncappedTests(unittest.TestCase):
    def test_no_limit_refuses_a_load(self) -> None:
        src = (ROOT / "src" / "maxload.c").read_text(encoding="latin-1")
        body = src.split("int do_maxload_item(int vnum)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("return 1;", body)
        self.assertNotIn("return 0", body)
        self.assertNotIn("item_max_load", body)


if __name__ == "__main__":
    unittest.main()
