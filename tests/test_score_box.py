"""SCORE is one box, 62 columns wide (owner, 2026-11-02).

The stash line was printed after the box's closing rule, outside it, and
the casino row's middle bar sat two columns left of every other row's
because its labels were padded to 11 where "Quest Points:" and
"Achievements:" overflow to 13. Every line of the sheet is now a rule or
a row of exactly the box's width, the stash row is inside, and the last
line is the closing rule -- for a mortal and for staff, whose sheet adds
the Holy Light row.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zscorepass1"
WIDTH = 62


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
        wrong = [line for line in lines
                 if len(line) != WIDTH
                 or not (line.startswith("-") or (line.startswith("|") and line.endswith("|")))]
        self.assertEqual(wrong, [], "\n".join(lines))
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


if __name__ == "__main__":
    unittest.main()
