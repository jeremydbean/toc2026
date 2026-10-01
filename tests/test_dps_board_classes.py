"""The benchmark board names class and guild the way players say them.

T/T for a thief in the thieves' guild, W/W, T/W for a thief in the
warriors' guild, and Monk and Necro in full because they have no guild.
The guild is stored with each run; a line written before it was stored
has none, so it is read from the character's own file rather than left
blank until their next run.

The board loads lazily on first use, so the live test writes one into the
test world after boot and before anybody reads it.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason  # noqa: E402

SKIP = skip_reason()
PASSWORD = "boardpass"


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class BoardClassSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dummy = read("src", "dummy.c")

    def test_the_guild_is_stored_with_each_run(self) -> None:
        self.assertIn("entry.guild   = ch->pcdata->guild;", self.dummy)
        save = self.dummy.split("static void dps_board_save(", 1)[1].split("\n}", 1)[0]
        self.assertIn('"%s %ld %d %d %d %ld %d\\n"', save)

    def test_an_old_line_still_loads_and_finds_its_guild(self) -> None:
        load = self.dummy.split("static void dps_board_load(", 1)[1].split("\n}", 1)[0]
        self.assertIn("&e.guild ) < 6", load)
        # Looked up only after the name has been checked, so a damaged
        # board cannot steer the lookup at another path.
        self.assertLess(load.index("dps_board_name_ok( name )"),
                        load.index("dps_board_guild_from_file( e.name )"))

    def test_monk_and_necro_are_named_in_full(self) -> None:
        cls = self.dummy.split("static void dps_board_class(", 1)[1].split("\n}", 1)[0]
        self.assertIn('"Monk"', cls)
        self.assertIn('"Necro"', cls)
        self.assertIn('"%c/%c"', cls)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BoardClassLiveTests(unittest.TestCase):
    def test_the_board_reads_like_who_says_it(self) -> None:
        with LiveMud() as mud:
            for name in ("Zboardtw", "Zboardtt", "Zboardmk", "Zboardnc"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            # A thief in the warriors' guild, the shape of Astarte, whose
            # board line predates the guild being stored.
            patch_player_file(mud, "Zboardtw", Cla=2, Gui=3)

            (mud.root / "area" / "dpsboard.txt").write_text(
                "#standard 2\n"
                "Zboardtw 9000 80 30 2 1790000000\n"          # six fields
                "Zboardtt 8000 80 30 2 1790000001 2\n"
                "Zboardmk 7000 80 30 4 1790000002 11\n"
                "Zboardnc 6000 80 30 5 1790000003 11\n",
                encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zboardtt", PASSWORD)
                board = re.sub(r"\x1b\[[0-9;]*m", "",
                               client.command("dummy leaderboard", 3.0))
                rows = {line.split()[2]: line for line in board.splitlines()
                        if re.match(r"\|\s+\d+\s+Zboard", line)}
                self.assertRegex(rows["Zboardtw"], r"\s30\s+T/W\s")
                self.assertRegex(rows["Zboardtt"], r"\s30\s+T/T\s")
                self.assertRegex(rows["Zboardmk"], r"\s30\s+Monk\s")
                self.assertRegex(rows["Zboardnc"], r"\s30\s+Necro\s")
                client.send("quit")


if __name__ == "__main__":
    unittest.main()
