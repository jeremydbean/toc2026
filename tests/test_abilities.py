"""GAINLIST (and its alias ABILITIES) shows what a character can still learn.

Owner, 2026-10-04: Alaric reached 28 as a necromancer without the life &
undeath group that raises his servants, and nothing in the game told him.
GAINLIST now lists every skill and spell his class and guild can learn,
crossed when missing with who sells it, where, and the WALKTO to them;
GAINLIST TRAINERS keeps the old per-trainer view. Nothing is announced at a
level gain. The Oracle is handed the same list with every question.
"""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    from live_mud import LiveMud, create_character, patch_player_file, login, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)

PW = "Zabilpw1"


class SourceTests(unittest.TestCase):
    def test_alias_and_no_level_announcement(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        self.assertRegex(interp, r'"abilities",\s*do_gainlist')
        for name in ("act_info.c", "update.c", "stubs.c"):
            text = (ROOT / "src" / name).read_text(encoding="latin-1")
            self.assertNotIn("show_abilities(", text, name)

    def test_oracle_receives_the_list(self) -> None:
        oracle_c = (ROOT / "src" / "oracle.c").read_text(encoding="latin-1")
        self.assertIn("abilities_oracle_summary( ch, summary", oracle_c)
        oracle_py = (ROOT / "webadmin" / "oracle.py").read_text(encoding="utf-8")
        self.assertIn("ABILITIES_FIELD", oracle_py)


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class LiveTests(unittest.TestCase):
    def test_necromancer_sees_life_and_undeath_missing(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as c:
                create_character(c, "Zabiler", PW)
                c.send("quit")
                self.assertTrue(c.wait_closed())
            patch_player_file(mud, "Zabiler", Levl=28, Room=4207, Cla=5, Gui=5)
            with mud.connect(timeout=120) as c:
                login(c, "Zabiler", PW)
                c.send("scroll 0")
                c.drain(2)
                mark = len(c.transcript)
                c.send("abilities")
                c.drain(4)
                out = c.transcript[mark:]
                mark = len(c.transcript)
                c.send("gainlist trainers")
                c.drain(4)
                trainers = c.transcript[mark:]
                c.send("quit")
                self.assertTrue(c.wait_closed())
            self.assertIn("Abilities for a level 28", out)
            self.assertIn("Not yet learned", out)
            # Animate dead comes in life & undeath, sold by the Soul Trapper.
            self.assertIn("life & undeath", out)
            self.assertIn("Soul Trapper", out)
            self.assertIn("walkto", out)
            self.assertNotIn("Abilities for a level", trainers)


if __name__ == "__main__":
    unittest.main()
