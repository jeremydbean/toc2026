"""tools/consider_audit.py holds CONSIDER to the fights players had (owner,
2026-11-10: "i feel like the consider command isn't that accurate").

Past CONSIDERs live only in log/play.tsv's reply lines; they are joined
to the next fight in log/progress.tsv by level, area, time and the
mobile's keywords, and a join with two candidates is dropped. New
encounters carry the prediction itself (the engage row) and join by id.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import consider_audit  # noqa: E402

PLAY = ("1000\tcmd\tZsomeone\t30\t500\tzone.are\tstanding\t100\t0\t-\tconsider\tgob\t"
        "A goblin is about your level. // A goblin has about half your hit points. // "
        "Blow for blow, you would need about 6 rounds to bring a goblin down; "
        "he would need about 40 rounds for you.\t-\t-\n")
PROGRESS = ("1100\tkill\t77\t30\t3\t0\t90\t100\t4000\t30\tzone.are\t36000\t100\t0\t100\t1\t"
            "-1\t-\t400\t50\t0\t0\t0\t0\n")


class ConsiderAuditTests(unittest.TestCase):
    def test_a_past_consider_joins_the_fight_after_it(self) -> None:
        rows = consider_audit.outcomes(PROGRESS)
        pairs = consider_audit.inferred_pairs(PLAY, rows, lambda vnum, arg: vnum == 4000)
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual((p["pred_yours"], p["pred_theirs"]), (6.0, 40.0))
        self.assertEqual(p["band"], "edge >= 4 (win easily)")
        self.assertEqual(p["outcome"]["kind"], "kill")
        self.assertAlmostEqual(p["outcome"]["ms"] / 1000 / consider_audit.ROUND_SECONDS / 6.0, 2.0)
        self.assertTrue(p["inferred"])

    def test_two_candidates_is_no_join(self) -> None:
        other = PROGRESS.replace("\t77\t", "\t88\t")
        rows = consider_audit.outcomes(PROGRESS + other)
        self.assertEqual(consider_audit.inferred_pairs(PLAY, rows, lambda v, a: True), [])

    def test_the_silent_prediction_joins_by_encounter(self) -> None:
        engage = ("2000\tengage\t5\t30\t3\t0\t100\t100\t4000\t30\tzone.are\t9-1\t300\t500\t500\t"
                  "100\t100\t1\t0\t28\t-\t50.0\t20.0\t6.0\t25.0\twin\t0\n")
        slain = ("2030\tslain\t5\t30\t3\t0\t80\t100\t4000\t30\tzone.are\t9-1\t30000\tblow\tplayer\t"
                 "1\t0\t300\t300\t0\t100\t0\t10\t20\t12\t60\n")
        pairs = consider_audit.encounter_pairs(engage + slain)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["band"], "1.5-4 (should win)")
        self.assertEqual(pairs[0]["outcome"]["rounds"], 10)
        self.assertEqual((pairs[0]["outcome"]["swings"], pairs[0]["outcome"]["landed"]), (20, 12))


if __name__ == "__main__":
    unittest.main()
