"""A mobile's coin from its area file is held to its level (owner, 2026-11-04).

An area file gives a mobile one wealth figure, and mob_index_set_wealth
split it into every denomination at once -- a 179th in platinum, a 69th
in gold, a 39th in silver, a 29th in copper -- so the dark horseman's
400, at level 8, was two platinum: more than two thousand of a level 9's
kills. 479 of the world's 1,704 mobiles with a figure paid more than
three times the most their level's roll gives. The coin is now held to
MOB_WEALTH_CAP_ROLLS times that roll; a figure under it is untouched, and
the figure itself is kept so a saved area writes back what it read.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zwealthpw1"
MONEY = re.compile(r"Money: (\d+) Platinum, (\d+) Gold, (\d+) Silver, (\d+) Copper")


class WealthCapSourceTests(unittest.TestCase):
    def test_the_cap_is_three_rolls_and_the_figure_is_kept(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        self.assertIn("#define MOB_WEALTH_CAP_ROLLS 3", db)
        body = db.split("void mob_index_set_wealth(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("pMobIndex->wealth       = total;", body, "the file's figure is kept")
        self.assertIn("mob_wealth_roll_max( pMobIndex->level )", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WealthCapLiveTests(unittest.TestCase):
    def money(self, staff, word: str) -> tuple[int, int, int, int]:
        found = MONEY.search(staff.sync(f"stat mob {word}"))
        self.assertIsNotNone(found, word)
        return tuple(int(v) for v in found.groups())  # type: ignore[return-value]

    def test_a_rich_figure_is_capped_and_a_modest_one_is_not(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zwealthstaff", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwealthstaff", Levl=70, Room=4207)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zwealthstaff", PW)
                staff.sync("scroll 0")

                # The dark horseman, level 8, figure 400: two platinum before.
                # Three times level 8's roll (16 silver 32 copper) is 48s 96c.
                staff.sync("load mob 3505")
                self.assertEqual(self.money(staff, "horseman"), (0, 0, 48, 96))

                # Mud School's beast, level 5, figure 50: a silver and a
                # copper, far under its cap, exactly as before.
                staff.sync("load mob 3714")
                self.assertEqual(self.money(staff, "beast"), (0, 0, 1, 1))


if __name__ == "__main__":
    unittest.main()
