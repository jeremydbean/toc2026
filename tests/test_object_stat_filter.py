"""/api/objects' stat_filter is read once, and a filter it cannot read is a 400.

Review, 2026-11-12: a malformed or unsupported stat_filter ("hitroll5",
"hitroll<5", "luck>2", "hitroll>x") was swallowed by a bare except inside
the loop over objects, so the filter quietly did nothing and every object
came back as though it had matched. It is parsed before the walk now
(_parse_stat_filter): "<stat> > <number>", the stat any part of an apply
location's name, and anything else answered 400 with the reason.

The world here is a stand-in of three synthetic objects.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from fastapi.testclient import TestClient
    from webadmin import server
    SKIP = None
except Exception as exc:  # pragma: no cover - env dependent
    SKIP = f"fastapi test client unavailable ({type(exc).__name__}: {exc})"


def obj(vnum, affects):
    return SimpleNamespace(vnum=vnum, short_desc=f"zfilter thing {vnum}",
                           keywords="zfilter thing", level=10, item_type="9",
                           extra_flags="0", extra_flags2="0", wear_flags="A",
                           affects=[{"location": loc, "modifier": mod} for loc, mod in affects],
                           values=["0", "0", "0", "0", "0"], carried_by=[], contained_by=[])


WORLD = SimpleNamespace(
    objects={1: obj(1, [(18, 6)]),              # hitroll +6
             2: obj(2, [(18, 2), (13, 25)]),    # hitroll +2, hit points +25
             3: obj(3, [(24, -4)])},            # save vs spell -4
    mobiles={}, rooms={})


@unittest.skipIf(SKIP is not None, SKIP or "")
class StatFilterTests(unittest.TestCase):
    def count(self, stat_filter):
        """How many objects match: offset past them all, so only the count
        is built, never an object's whole description."""
        with patch.object(server, "parser", WORLD):
            response = TestClient(server.app).get(
                "/api/objects", params={"stat_filter": stat_filter, "offset": 1000})
        return response

    def matched(self, stat_filter) -> int:
        response = self.count(stat_filter)
        self.assertEqual(response.status_code, 200, response.text)
        return int(response.headers["X-Total-Count"])

    def test_valid_filters(self) -> None:
        self.assertEqual(self.matched("hitroll>5"), 1)
        self.assertEqual(self.matched("hitroll>1"), 2)
        self.assertEqual(self.matched(" Hitroll > 1 "), 2, "case and spaces")
        self.assertEqual(self.matched("hit points>20"), 1)
        self.assertEqual(self.matched("hit_points>20"), 1, "underscores for spaces")
        self.assertEqual(self.matched("save vs spell>-5"), 1, "a negative threshold")
        self.assertEqual(self.matched("hit>5"), 2, "part of a name, as before: hitroll and hit points")
        self.assertEqual(self.matched(""), 3, "an empty filter is no filter")

    def test_malformed_filters_are_refused(self) -> None:
        for bad in ("hitroll", "hitroll5", "hitroll>", ">5", "hitroll>x", "hitroll>5>6",
                    "hitroll>5.5", "hit;roll>5", "x" * 70 + ">1", "hitroll>99999999999"):
            with self.subTest(bad=bad):
                response = self.count(bad)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn("stat_filter", response.json()["detail"])

    def test_unsupported_filters_say_why(self) -> None:
        for op in ("<", ">=", "=", "!="):
            response = self.count(f"hitroll{op}5")
            self.assertEqual(response.status_code, 400, op)
            self.assertIn("supports only '>'", response.json()["detail"])
        response = self.count("luck>2")
        self.assertEqual(response.status_code, 400)
        self.assertIn("names no stat", response.json()["detail"])
        self.assertIn("hitroll", response.json()["detail"], "it lists what is supported")


if __name__ == "__main__":
    unittest.main()
