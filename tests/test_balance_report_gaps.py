"""A band's gap counts only the equal choices a player can take.

Review, 2026-11-12: balance.proposals() read the band's own "gap", which
counts every equal mobile -- a Hyrule guardian or one in an area nothing
leads to included -- before it filtered for reachable ones, so a band of
three equal mobiles of which one was reachable proposed no gap. And
tools/balance_report.py --json never read the world at all. Both now ask
balance.band_choices(); --no-names reads no area file and counts every
mobile reachable, in the text and the JSON alike.

Feeds are synthetic, in temporary directories; the world is a stand-in.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from webadmin import balance  # noqa: E402

EQUAL = (2101, 2102, 2103)      # three mobiles, one band, the same pay
REACHABLE = 2102                # the only one a player can walk to


def head(t, kind, who, level, vnum, foe_level):
    return [str(t), kind, str(who), str(level), "3", "0", "100", "100",
            str(vnum), str(foe_level), "zone.are"]


def feed() -> str:
    rows = []
    t, n = 1000, 0
    for vnum in EQUAL:
        for i in range(6):
            n += 1
            kid = f"1700000000-{n}"
            who = 65536 + i % 2
            rows.append(head(t, "engage", who, 22, vnum, 23)
                        + [kid, "500", "100", "100", "100", "100", "1", "0", "22", "-"])
            rows.append(head(t, "slain", who, 22, vnum, 23)
                        + [kid, "10000", "blow", "player", "1", "0", "500", "500", "0", "50", "500"])
            rows.append(head(t, "reward", who, 22, vnum, 23)
                        + ["10000", "100", "0", "100", "1", "-1", "-", "100", "20", "0", "0",
                           "0", "500", "500", kid, "1", "22", "100", "100", "100", "100"])
            t += 30
    return "".join("\t".join(r) + "\n" for r in rows)


def stand_in_world(skip):
    """world() as the report calls it, without the area files: names for
    the three, and only one of them reachable."""
    if skip:
        return {}, {}, {}, None
    return ({v: f"zgapmob {v}" for v in EQUAL}, {}, {},
            lambda v: v == REACHABLE)


class BandChoiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = balance.compare(balance.summarize(feed()))
        self.band = self.result["bands"][(21, 25)]

    def test_three_equal_choices_are_no_gap_when_all_count(self) -> None:
        self.assertEqual(sorted(self.band["equal"]), list(EQUAL))
        choices, gap = balance.band_choices(self.band)
        self.assertEqual(sorted(choices), list(EQUAL))
        self.assertFalse(gap)
        self.assertFalse(any(p["finding"] == "gap" for p in balance.proposals(self.result)))

    def test_one_reachable_of_three_is_a_gap(self) -> None:
        choices, gap = balance.band_choices(self.band, lambda v: v == REACHABLE)
        self.assertEqual(choices, [REACHABLE])
        self.assertTrue(gap)
        props = balance.proposals(self.result, reachable=lambda v: v == REACHABLE)
        gaps = [p for p in props if p["finding"] == "gap"]
        self.assertEqual(len(gaps), 1, props)
        self.assertEqual(gaps[0]["band"], "21-25")
        self.assertIn("1 equal choice(s) among 3 trusted", gaps[0]["evidence"])


class ReportTests(unittest.TestCase):
    def run_report(self, *args: str, world=stand_in_world) -> str:
        import balance_report
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.tsv"
            path.write_text(feed(), encoding="latin-1")
            out = io.StringIO()
            with patch.object(balance_report, "world", world), \
                    patch.object(sys, "argv", ["balance_report.py", "--file", str(path), *args]), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(balance_report.main(), 0)
        return out.getvalue()

    def test_the_text_and_the_json_agree_on_the_gap(self) -> None:
        text = self.run_report()
        self.assertIn("1 equal choice(s)  ** GAP **", text)
        self.assertIn("21-25 band: gap", text)
        data = json.loads(self.run_report("--json"))
        band = data["bands"]["21-25"]
        self.assertTrue(data["world_read"])
        self.assertTrue(band["gap"])
        self.assertEqual(band["equal"], [REACHABLE])
        self.assertEqual(sorted(band["equal_not_reachable"]), [2101, 2103])
        gaps = [p for p in data["proposals"] if p["finding"] == "gap"]
        self.assertEqual([p["band"] for p in gaps], ["21-25"])

    def test_the_json_reads_the_world(self) -> None:
        calls = []

        def world(skip):
            calls.append(skip)
            return stand_in_world(skip)
        self.run_report("--json", world=world)
        self.assertEqual(calls, [False], "--json asks the area files, as the text does")

    def test_no_names_counts_every_mobile_reachable(self) -> None:
        calls = []

        def world(skip):
            calls.append(skip)
            return stand_in_world(skip)
        text = self.run_report("--no-names", world=world)
        self.assertIn("3 equal choice(s);", text)
        self.assertNotIn("GAP", text)
        data = json.loads(self.run_report("--no-names", "--json", world=world))
        self.assertEqual(calls, [True, True])
        band = data["bands"]["21-25"]
        self.assertFalse(data["world_read"])
        self.assertFalse(band["gap"])
        self.assertEqual(sorted(band["equal"]), list(EQUAL))
        self.assertEqual(band["equal_not_reachable"], [])
        self.assertFalse(any(p["finding"] == "gap" for p in data["proposals"]))

    def test_no_names_runs_without_the_area_files(self) -> None:
        # The real script, as a person runs it: --no-names never opens area/.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.tsv"
            path.write_text(feed(), encoding="latin-1")
            out = subprocess.run([sys.executable, "tools/balance_report.py", "--file", str(path),
                                  "--no-names", "--json"], cwd=ROOT, capture_output=True,
                                 text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertFalse(data["bands"]["21-25"]["gap"])
        self.assertNotIn("area files not read", out.stderr)


if __name__ == "__main__":
    unittest.main()
