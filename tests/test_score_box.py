"""SCORE is one box (owner, 2026-11-02) that fits what is in it (2026-11-24).

The stash line was printed after the box's closing rule, outside it, and
the casino row's middle bar sat two columns left of every other row's
because its labels were padded to 11 where "Quest Points:" and
"Achievements:" overflow to 13. Every line of the sheet is now a rule or
a row of exactly the box's width, the stash row is inside, and the last
line is the closing rule -- for a mortal and for staff, whose sheet adds
the Holy Light row.

It was 62 columns of fixed printf widths, and a width is only a minimum:
hit points past 99,999 pushed their row's border out past the rest
(owner, 2026-11-24). textbox.c now sizes every column and the frame to
the widest value, so the box is at least 62 wide and every line of it
the same width, whatever the numbers; the bars between cells line up
down the whole sheet.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zscorepass1"
MIN_WIDTH = 62


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def sheet_lines(reply: str) -> list[str]:
    text = re.sub(r"\x1b\[[0-9;]*m", "", reply).replace("\r", "")
    lines = [line.rstrip() for line in text.split("\n")]
    first = next(i for i, line in enumerate(lines) if line.startswith("-" * 20))
    last = max(i for i, line in enumerate(lines) if line.startswith("-" * 20))
    return lines[first:last + 1]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ScoreBoxLiveTests(unittest.TestCase):
    def check_sheet(self, client) -> list[str]:
        lines = sheet_lines(client.sync("score"))
        width = len(lines[0])
        self.assertGreaterEqual(width, MIN_WIDTH, "\n".join(lines))
        wrong = [line for line in lines
                 if len(line) != width
                 or not (line.startswith("-") or (line.startswith("|") and line.endswith("|")))]
        self.assertEqual(wrong, [], "\n".join(lines))
        # Rows with the same number of cells share their columns: every
        # bar sits where the others' do, top to bottom.
        bars: dict[int, set[tuple[int, ...]]] = {}
        for line in lines:
            if line.startswith("|"):
                where = tuple(i for i, ch in enumerate(line) if ch == "|")
                bars.setdefault(len(where), set()).add(where)
        for count, shapes in bars.items():
            if count > 2:
                self.assertEqual(len(shapes), 1, "\n".join(lines))
        return lines

    def test_every_row_is_inside_the_box_and_aligned(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zscorer", Levl=20, CasinoWon=102, CasinoLost=204)
            make(mud, "Zscorestaff", Levl=70, CasinoWon=123456, CasinoLost=7)
            for name in ("Zscorer", "Zscorestaff"):
                with self.subTest(name=name), mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.sync("scroll 0")
                    lines = self.check_sheet(client)
                    stash = [line for line in lines if "Stash:" in line]
                    self.assertEqual(len(stash), 1, "\n".join(lines))
                    self.assertRegex(stash[0], r"^\| Stash: \d+ of \d+ used +\|$")
                    casino = next(line for line in lines if "Casino Won:" in line)
                    quest = next(line for line in lines if "Quest Points:" in line)
                    self.assertEqual(casino.index("|", 1), quest.index("|", 1), casino)
                    # Colour off draws the same box.
                    client.sync("color")
                    self.check_sheet(client)

    def test_large_casino_totals_stay_inside_the_box(self) -> None:
        # A field width is a minimum: nine digits won pushed the row to 63
        # columns (review, 2026-11-03). They were split onto rows of their
        # own; now the box widens instead, every digit kept on one row.
        cases = {
            "Zscoreeight": (99999999, 123456789012345678, True),
            "Zscorenine": (100000000, 7, True),
            "Zscorelost": (5, 1234567890123456789, True),
            "Zscoremax": (9223372036854775807, 9223372036854775807, True),
            "Zscoreten": (1234567890, 0, True),
        }
        with LiveMud() as mud:
            for name, (won, lost, _) in cases.items():
                make(mud, name, Levl=20, CasinoWon=won, CasinoLost=lost)
            for name, (won, lost, one_row) in cases.items():
                with self.subTest(name=name), mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.sync("scroll 0")
                    for colour in ("on", "off"):
                        lines = self.check_sheet(client)
                        text = "\n".join(lines)
                        self.assertIn(str(won), text, colour)
                        self.assertIn(str(lost), text, colour)
                        rows = [line for line in lines if "Casino" in line]
                        self.assertEqual(len(rows), 1 if one_row else 2, text)
                        if one_row:
                            quest = next(line for line in lines if "Quest Points:" in line)
                            self.assertEqual(rows[0].index("|", 1), quest.index("|", 1))
                        client.sync("color")

    def test_huge_hit_points_mana_and_coins_widen_the_box(self) -> None:
        # Owner, 2026-11-24: "the score screen struggles to handle large
        # hp/mana". A "%5d" held 99,999 at most; these pushed the right
        # border out of line. Synthetic characters only.
        cases = {
            "Zscorebig": dict(hmv="1234567 2345678 987654 1987654 123456 223456",
                              hmvp="2345678 1987654 223456"),
            "Zscorehuge": dict(hmv="2000000000 2100000000 2000000000 2100000000 "
                                   "2000000000 2100000000",
                               hmvp="2100000000 2100000000 2100000000"),
        }
        with LiveMud() as mud:
            for name, kit in cases.items():
                make(mud, name, Levl=50, HMV=kit["hmv"], HMVP=kit["hmvp"],
                     BankCP=987654321098765432, QuestPnts=2147483647,
                     CasinoWon=1, CasinoLost=1)
            for name in cases:
                with self.subTest(name=name), mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.sync("scroll 0")
                    for colour in ("on", "off"):
                        lines = self.check_sheet(client)
                        text = "\n".join(lines)
                        hp = next(line for line in lines if "Hp:" in line)
                        mana = next(line for line in lines if "Mana:" in line)
                        shown = re.search(r"Hp:\s+(\d+) \((\d+)\)", hp)
                        self.assertIsNotNone(shown, text)
                        self.assertGreaterEqual(int(shown.group(2)), 100000, text)
                        self.assertRegex(mana, r"Mana:\s+\d{6,} \(\d{6,}\)", text)
                        self.assertRegex(text, r"Bank:\s+\d+p \d+g \d+s \d+c")
                        client.sync("color")


if __name__ == "__main__":
    unittest.main()
