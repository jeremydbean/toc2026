"""A level is rolled against gear, never against spells (owner, 2026-11-11:
"buffs shouldn't affect leveling, but gear should").

advance_level_body read get_curr_stat, which counts every affect, so a
character levelling under EMPOWER (WIS +15) kept the practices, mana and
hit points of a much wiser, tougher character for good. It now reads
get_level_stat: the permanent stat plus what worn gear lends it.

The practices a level gives are wis_app[WIS].practice -- deterministic at
level 20 and above -- so they show which WIS the roll saw: 10 gives 1,
16 gives 2, and EMPOWER's 25 would give 5.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zlvlpass11"
WIS_AMULET = 32711          # tests/fixtures/area/ztestfix.are: WIS +6, neck


def practices(client) -> int:
    reply = client.sync("practice", timeout=60)
    found = re.search(r"You have (\d+) practice sessions? left", reply)
    assert found, reply
    return int(found.group(1))


class LevelStatSourceTests(unittest.TestCase):
    def test_the_level_body_reads_the_gear_stat(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        body = update.split("static void advance_level_body(", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("get_curr_stat(", body)
        self.assertIn("get_level_stat(", body)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        helper = handler.split("int get_level_stat(", 1)[1].split("\n}\n", 1)[0]
        for part in ("obj->wear_loc == WEAR_NONE", "obj->pIndexData->affected",
                     "obj->affected", "stat_ceiling( ch, stat )"):
            self.assertIn(part, helper, part)
        self.assertNotIn("mod_stat", helper)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LevelStatLiveTests(unittest.TestCase):
    def test_a_buff_is_left_out_and_gear_is_counted(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name, level, extra in (("Zlvlstaff", 70, {}),
                                       ("Zlvlwise", 30, {"Attr": "13 13 10 13 13"})):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207, **extra)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zlvlstaff", PW)
                login(player, "Zlvlwise", PW)
                for client in (staff, player):
                    client.sync("scroll 0")

                before = practices(player)
                staff.must("advance zlvlwise 31", "31")
                plain = practices(player) - before

                staff.sync("empower zlvlwise", timeout=60)
                self.assertIn("empower", player.sync("affects").lower())
                before = practices(player)
                staff.must("advance zlvlwise 32", "32")
                buffed = practices(player) - before

                staff.must(f"load obj {WIS_AMULET}", "You create", "amulet")
                staff.must("give fixture zlvlwise", "give")
                player.must("wear fixture", "amulet")
                before = practices(player)
                staff.must("advance zlvlwise 33", "33")
                geared = practices(player) - before

                for client in (player, staff):
                    client.send("quit")
                    client.wait_closed()

        self.assertEqual(plain, 1, "WIS 10 gives one practice a level")
        self.assertEqual(buffed, plain, "EMPOWER's wisdom is not counted")
        self.assertEqual(geared, 2, "the amulet's +6 (WIS 16) is counted")


if __name__ == "__main__":
    unittest.main()
