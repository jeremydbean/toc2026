"""Hit points, mana and endurance are no longer held under 32,767 (owner,
2026-11-11: "is there a reason HP/mana/end is capped at 32k?").

The permanent pools (pcdata->perm_hit/mana/move) and every affect's
modifier were 16-bit, so SET refused anything past 30,000 and TITANIC
stopped a pool at 30,000. Both fields are int now and the ceiling is
POOL_MAX (a billion), far from overflowing when bonuses are added.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zpoolpass11"


class PoolSourceTests(unittest.TestCase):
    def test_the_fields_are_int(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        for field in ("perm_hit", "perm_mana", "perm_move"):
            self.assertRegex(merc, r"\bint\s+%s;" % field)
        self.assertRegex(merc, r"int\s+modifier;\s+/\* int, not sh_int")
        self.assertIn("#define POOL_MAX        1000000000", merc)

    def test_no_pool_is_squeezed_into_a_short(self) -> None:
        for path in sorted((ROOT / "src").glob("*.c")):
            text = path.read_text(encoding="latin-1")
            self.assertNotRegex(text, r"(perm_(hit|mana|move)|(\.|->)modifier)\s*[-+]?=\s*\(sh_int\)"
                                if path.name != "db.c" else r"perm_(hit|mana|move)\s*=\s*\(sh_int\)",
                                path.name)
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertNotIn("30,000 hit points", wiz)


def max_hit(staff, name: str) -> int:
    text = staff.sync(f"stat {name}", timeout=60)
    found = re.search(r"Hp:\s*-?\d+/(\d+)", text)
    assert found, text
    return int(found.group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PoolLiveTests(unittest.TestCase):
    def test_a_pool_past_the_old_short(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zpoolstaff", 70), ("Zpoolbig", 30)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zpoolstaff", PW)
                login(player, "Zpoolbig", PW)
                staff.sync("scroll 0")
                staff.must("set char zpoolbig hp 100000", "100000")
                self.assertEqual(max_hit(staff, "zpoolbig"), 100000)
                player.send("save")
                player.sync("time")
                player.send("quit")
                self.assertTrue(player.wait_closed())
            text = (mud.player_dir / "Zpoolbig").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^HMVP 100000 ")

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zpoolstaff", PW)
                login(player, "Zpoolbig", PW)
                staff.sync("scroll 0")
                self.assertEqual(max_hit(staff, "zpoolbig"), 100000, "kept across a reload")
                # Five times the pool is past what a short holds -- and it is
                # five times in all, not five times added on top (owner,
                # 2026-11-12: it read 120,000 here before).
                staff.must("set char zpoolbig hp 20000", "20000")
                staff.sync("titanic zpoolbig", timeout=60)
                self.assertEqual(max_hit(staff, "zpoolbig"), 100000)
                staff.sync("titanic zpoolbig", timeout=60)      # toggles off
                self.assertEqual(max_hit(staff, "zpoolbig"), 20000)
                # EMPOWER carries half again the experience now.
                staff.sync("empower zpoolbig 10", timeout=60)
                self.assertRegex(player.sync("affects", timeout=60), r"experience by 50")
                for client in (player, staff):
                    client.send("quit")
                    client.wait_closed()


if __name__ == "__main__":
    unittest.main()
