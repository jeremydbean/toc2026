"""The Hall of Heroes' plaque, and staff tidying the benchmark board.

The plaque has always said a new hero's name "magically appears on it",
and nothing did that. It is drawn from heroes/ now -- the record
save_char_obj writes for every hero -- without filtering on a surviving
character file, because 83 of the 212 heroes recorded on the live server
have none and the plaque is the only place their names survive.

Staff can take one run off the benchmark board or empty it, and both are
logged where a week-later question can find them.
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
PASSWORD = "plaquepw"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def clean(text: str) -> str:
    return ANSI.sub("", text).replace("\r", "")


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class PlaqueSourceTests(unittest.TestCase):
    def test_the_plaque_does_not_filter_on_a_character_file(self) -> None:
        body = read("src", "save.c").split("bool show_hero_plaque(", 1)[1]
        body = body.split("\n}\n", 1)[0]
        self.assertIn("opendir( HERO_DIR )", body)
        self.assertNotIn("PLAYER_DIR", body,
                         "filtering on a character file drops 83 heroes")

    def test_no_sort_orders_with_str_cmp(self) -> None:
        """str_cmp() answers only whether two strings differ. Both name
        sorts used it as a qsort comparator and came out in no order --
        the plaque's live test caught it, and the online roster had the
        same mistake."""
        for source in ("save.c", "gmcp.c", "act_comm.c", "interp.c"):
            text = read("src", source)
            for comparator in re.findall(
                    r"static int \w+\( const void \*\w+, const void \*\w+ \)\n\{.*?\n\}",
                    text, re.S):
                self.assertNotIn("str_cmp(", comparator, source)

    def test_look_falls_through_to_the_old_text(self) -> None:
        move = read("src", "act_move.c")
        self.assertIn('is_name( arg1, "plaque" ) && show_hero_plaque( ch )',
                      move)
        self.assertIn("plaque~", read("area", "dresden.are"))

    def test_board_staff_actions_are_logged_and_gated(self) -> None:
        dummy = read("src", "dummy.c")
        staff = dummy.split("static void dps_board_staff(", 1)[1].split("\n}\n", 1)[0]
        self.assertEqual(2, staff.count("log_string( buf )"))
        self.assertIn('str_cmp( who, "confirm" )', staff)
        self.assertIn("IS_TRUSTED( ch, LEVEL_IMMORTAL )",
                      dummy.split("dps_board_staff( ch, arg2, arg3 )", 1)[0][-400:])


@unittest.skipIf(SKIP is not None, SKIP or "")
class PlaqueAndBoardLiveTests(unittest.TestCase):
    def test_the_plaque_and_the_board(self) -> None:
        with LiveMud() as mud:
            for name in ("Zplaqueimm", "Zplaquemrt"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zplaqueimm", Levl=70, Room=4649)
            patch_player_file(mud, "Zplaquemrt", Levl=30, Room=4649)

            with mud.connect(timeout=200) as imm, mud.connect(timeout=200) as mrt:
                login(imm, "Zplaqueimm", PASSWORD)
                login(mrt, "Zplaquemrt", PASSWORD)

                # Nothing in heroes/: the old text, not an empty frame.
                fallback = clean(mrt.command("look plaque", 2.5))
                self.assertIn("Hero's of ToC", fallback)

                heroes = mud.root / "heroes"
                for name in ("Zeta", "Acidtrip", "Moonbeam"):
                    (heroes / name).write_text("Lev 51 Trust 51  %s\n" % name)
                (heroes / "notes.txt").write_text("not a hero")
                (heroes / "Bad1name").write_text("not a hero")

                plaque = clean(mrt.command("look plaque", 2.5))
                self.assertIn("Every one of the 3 who have reached", plaque)
                order = [n for n in re.findall(r"[A-Z][a-z]+", plaque)
                         if n in ("Zeta", "Acidtrip", "Moonbeam")]
                self.assertEqual(order, ["Acidtrip", "Moonbeam", "Zeta"])
                self.assertNotIn("notes", plaque)
                self.assertNotIn("Bad1name", plaque)

                (mud.root / "area" / "dpsboard.txt").write_text(
                    "#standard 2\n"
                    "Zrunone 9000 80 30 2 1790000000 2\n"
                    "Zruntwo 8000 80 30 3 1790000001 3\n"
                    "Zrunthree 7000 80 30 0 1790000002 0\n",
                    encoding="latin-1")

                # A mortal's REMOVE is just a look at the board.
                mrt.command("dummy leaderboard remove Zrunone", 2.5)
                self.assertIn("Zrunone",
                              clean(mrt.command("dummy leaderboard", 2.5)))

                out = clean(imm.command("dummy leaderboard remove zrunone", 3.0))
                self.assertIn("Done.", out)
                self.assertNotIn("Zrunone", clean(imm.command("dummy leaderboard", 2.5)))

                ask = clean(imm.command("dummy leaderboard clear", 2.5))
                self.assertIn("CLEAR CONFIRM", ask)
                self.assertIn("Zruntwo", clean(imm.command("dummy leaderboard", 2.5)))

                done = clean(imm.command("dummy leaderboard clear confirm", 3.0))
                self.assertIn("The board is empty.", done)
                self.assertIn("Nobody has run the standard benchmark yet",
                              clean(imm.command("dummy leaderboard", 2.5)))

                for client in (imm, mrt):
                    client.send("quit")

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1",
                                                         errors="replace")
            self.assertIn("Benchmark board: Zplaqueimm removed Zrunone", log)
            self.assertIn("Benchmark board: Zplaqueimm cleared it (2 runs).", log)


if __name__ == "__main__":
    unittest.main()
