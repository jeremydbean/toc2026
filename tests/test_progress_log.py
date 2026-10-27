"""log/progress.tsv: what leveling is made of (2026-10-22).

The watch log and the play journal could not say how long a fight took,
how much experience was actually accepted, or how often a hunt ended in a
flee -- only arrivals and adjacent timestamps, which measure nothing.
Every credited kill now writes a line with the encounter's length, the
base, rested and accepted experience and the group size, and a flee or a
player's death writes one too. The character is the file's numeric Id,
never a name, and the finest place written is the area file.
"""
from __future__ import annotations

import sys
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zprogress1"
HALLS = 4202            # not safe
SMURF = 104             # a handy smurf, level 3
WORKER = 13428          # a construction worker, 3,400 hit points: one to flee from


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ProgressLogTests(unittest.TestCase):
    def test_a_kill_and_a_flee_are_recorded_without_a_name(self) -> None:
        with LiveMud() as mud:
            # Level 5 against a level 3 smurf earns experience; a level 20
            # earns none (xp_compute's range is 3 - 20 + 3), which is the
            # second kill: a kill that pays nothing is logged too.
            for name, level in (("Zhunter", 5), ("Zsetter", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=HALLS,
                                  HMV="9000 9000 500 500 500 500", HMVP="9000 500 500")
            with mud.connect(timeout=120) as hunter, mud.connect(timeout=120) as setter:
                login(hunter, "Zhunter", PW)
                login(setter, "Zsetter", PW)
                setter.must("set char zhunter hitroll 40", "")
                run(setter, f"load mob {SMURF}")
                # One hit point: the first blow that lands kills, before a
                # wimpy smurf can run.
                # SET sets the maximum; RESTORE brings it down to it.
                setter.must("set char smurf hp 1", "")
                setter.must("restore smurf", "")
                hunter.buffer = ""
                run(hunter, "kill smurf", 1.0)
                hunter.expect("is DEAD", timeout=60)
                hunter.drain(1.0)

                run(setter, "advance zhunter 20", 1.5)
                run(setter, f"load mob {SMURF}")
                # SET sets the maximum; RESTORE brings it down to it.
                setter.must("set char smurf hp 1", "")
                setter.must("restore smurf", "")
                hunter.buffer = ""
                run(hunter, "kill smurf", 1.0)
                hunter.expect("is DEAD", timeout=60)
                hunter.drain(1.0)

                run(setter, f"load mob {WORKER}")
                run(hunter, "kill worker", 1.0)
                # Watch everything since the first FLEE: a success that
                # arrives late lands in the next command's leading drain,
                # and a slice per command missed it and fled on and on.
                mark = len(hunter.transcript)
                for _ in range(30):
                    hunter.send("flee")
                    hunter.drain(2.0)
                    if "You flee from combat" in hunter.transcript[mark:]:
                        break
                else:
                    self.fail("thirty tries never fled:\n" + hunter.transcript[-1500:])
                run(setter, "peace", 0.5)
                for client in (hunter, setter):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")
            hunter_id = next(line.split()[1] for line in
                             (mud.player_dir / "Zhunter").read_text(encoding="latin-1").splitlines()
                             if line.startswith("Id "))

        rows = [line.split("\t") for line in text.splitlines()]
        kills = [r for r in rows if r[1] == "kill"]
        flees = [r for r in rows if r[1] == "flee"]
        self.assertEqual(len(kills), 2, text)
        kill, unpaid = kills
        self.assertEqual(len(kill), 23, kill)
        self.assertEqual(kill[2], hunter_id)                  # the Id, not a name
        self.assertEqual((kill[3], kill[8], kill[9]), ("5", str(SMURF), "3"))
        self.assertTrue(kill[10].endswith(".are"), kill)       # an area file, never a room
        self.assertGreaterEqual(int(kill[11]), 0, "encounter length")
        self.assertGreater(int(kill[14]), 0, "accepted experience")
        self.assertEqual(kill[15], "1", "group size")
        # The fight's ledger (class review, 2026-10-26): guild, buffs worn,
        # damage dealt and taken, hit points recovered, mana spent --
        # numbers only.
        self.assertRegex(kill[16], r"^-?\d+$", "guild")
        self.assertRegex(kill[17], r"^(-|[TESH]+)$", "buffs")
        self.assertGreater(int(kill[18]), 0, "damage dealt")
        for col in kill[19:23]:
            self.assertRegex(col, r"^-?\d+$", kill)
        self.assertGreaterEqual(int(kill[20]), 0, "healing is only ever seen to rise")
        # Fifteen levels over the smurf: nothing earned, still recorded.
        self.assertEqual((unpaid[3], unpaid[8]), ("20", str(SMURF)), unpaid)
        self.assertEqual(int(unpaid[14]), 0, unpaid)
        self.assertEqual(len(flees), 1, text)
        self.assertEqual(flees[0][8], str(WORKER))
        self.assertNotIn("Zhunter", text)
        self.assertNotIn(str(HALLS), text)


    def test_reflected_damage_is_a_loss_not_negative_healing(self) -> None:
        """A foe's fire shield burns the attacker outside damage(): the
        ledger inferred healing as now - start + taken and wrote a negative
        heal with no heal cast (review, 2026-10-27). Losses outside damage()
        are counted where they happen now, and healing is only ever seen to
        rise."""
        with LiveMud() as mud:
            for name, level in (("Zburner", 20), ("Zsetter", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=HALLS,
                                  HMV="9000 9000 500 500 500 500", HMVP="9000 500 500")
            with mud.connect(timeout=120) as hunter, mud.connect(timeout=120) as setter:
                login(hunter, "Zburner", PW)
                login(setter, "Zsetter", PW)
                setter.must("set char zburner hitroll 40", "")
                run(setter, f"load mob {SMURF}")
                # Too many hit points to reach its wimpy point: it stands
                # and burns the hunter until staff end it at one hit point.
                setter.must("set char smurf hp 30000", "")
                setter.must("restore smurf", "")
                setter.must("empower smurf perm", "mpower")      # fire shield among them
                # EMPOWER brings divine protection: the first death is
                # spared and credits nobody, and the next fight starts a
                # new ledger (set_fighting) -- so each fight is fought until
                # the aura has burned the hunter before it is ended.
                mark = len(hunter.transcript)
                for _ in range(2):
                    setter.must("set char smurf hp 30000", "")
                    setter.must("restore smurf", "")
                    burn = len(hunter.transcript)
                    hunter.buffer = ""              # expect() must see this fight's lines
                    hunter.send("kill smurf")
                    hunter.expect("Flaming Aura", timeout=60)
                    self.assertIn("Flaming Aura", hunter.transcript[burn:])
                    setter.must("set char smurf hp 1", "")
                    setter.must("restore smurf", "")
                    hunter.expect("is DEAD", timeout=120)
                    hunter.drain(2.0)
                    if "experience points" in hunter.transcript[mark:]:
                        break
                self.assertIn("experience points", hunter.transcript[mark:])
                for client in (hunter, setter):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")

        kills = [r for r in (line.split("\t") for line in text.splitlines()) if r[1] == "kill"]
        self.assertEqual(len(kills), 1, text)
        kill = kills[0]
        self.assertEqual(len(kill), 23, kill)
        taken, healed, direct = int(kill[19]), int(kill[20]), int(kill[22])
        self.assertGreater(direct, 0, f"the shield's burns are direct losses: {kill}")
        self.assertGreaterEqual(taken, direct, kill)
        self.assertGreaterEqual(healed, 0, kill)


class ProgressReportTests(unittest.TestCase):
    def test_the_report_aggregates_and_prints_no_ids(self) -> None:
        import io
        import sys
        from contextlib import redirect_stdout
        from datetime import datetime, timezone
        from pathlib import Path
        from types import SimpleNamespace
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import log_report

        text = ("1792700000\tkill\t4242\t30\t3\t0\t80\t100\t24112\t32\tcoven.are\t60000\t900\t0\t900\t1\n"
                "1792700100\tkill\t5353\t31\t0\t1\t60\t40\t24112\t32\tcoven.are\t60000\t800\t100\t900\t1\n"
                "1792700200\tflee\t5353\t31\t0\t1\t10\t40\t24112\t32\tcoven.are\n"
                "1792700300\tdeath\t4242\t30\t3\t0\t0\t0\t24112\t32\tcoven.are\n")
        summary = log_report.progress_summary(text, datetime(2026, 1, 1, tzinfo=timezone.utc))
        foe = summary["by_foe"][("coven.are", "24112", "32")]
        self.assertEqual((summary["characters"], foe["kills"], foe["xp"], foe["ms"]), (2, 2, 1800, 120000))
        area = summary["by_area"]["coven.are"]
        self.assertEqual((area["kills"], area["flee"], area["death"]), (2, 1, 1))

        original = log_report.git_show
        log_report.git_show = lambda ref, path: text
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                log_report.progress_report(SimpleNamespace(ref="x"),
                                           datetime(2026, 1, 1, tzinfo=timezone.utc))
        finally:
            log_report.git_show = original
        printed = out.getvalue()
        self.assertIn("2 distinct characters", printed)
        self.assertIn("900", printed)               # 1800 xp over two combat minutes
        self.assertNotIn("4242", printed)
        self.assertNotIn("5353", printed)

    def test_an_untimed_kill_does_not_inflate_the_rate(self) -> None:
        """A kill with no measured encounter (-1, or 0) adds to the total
        experience but not to the rate: 100 xp over one timed minute is
        100 a minute, whatever the untimed 900 beside it (review,
        2026-10-22)."""
        from datetime import datetime, timezone
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import log_report

        text = ("1792700000\tkill\t4242\t30\t3\t0\t80\t100\t24112\t32\tcoven.are\t60000\t100\t0\t100\t1\n"
                "1792700100\tkill\t4242\t30\t3\t0\t80\t100\t24112\t32\tcoven.are\t-1\t900\t0\t900\t1\n"
                "1792700200\tkill\t4242\t30\t3\t0\t80\t100\t24112\t32\tcoven.are\t0\t50\t0\t50\t1\n")
        foe = log_report.progress_summary(text, datetime(2026, 1, 1, tzinfo=timezone.utc))[
            "by_foe"][("coven.are", "24112", "32")]
        self.assertEqual((foe["xp"], foe["timed_xp"], foe["ms"], foe["untimed"]), (1050, 100, 60000, 2))
        self.assertEqual(foe["timed_xp"] / (foe["ms"] / 60000), 100)


if __name__ == "__main__":
    unittest.main()
