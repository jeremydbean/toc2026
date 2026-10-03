"""A mobile with more than 32,767 hit points keeps them.

Hit points, mana and moves were sh_int, so 36,000 wrapped to a negative
number when Ganon spawned: the first punch counted as fatal and he
collapsed at one hit point -- reported by the owner. The ashen Gleeok
(33,000) and the Undead Cleric (up to 45,000) were broken the same way,
the cleric for as long as his file has existed. The fields are int now.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
PW = "testpw12"
GANON = 30225
UNDEAD_CLERIC = 4702

_SKIP = skip_reason()


class HitPointWidthTests(unittest.TestCase):
    def test_the_fields_are_int(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        for field in ("hit", "max_hit", "mana", "max_mana", "move", "max_move"):
            self.assertRegex(merc, r"\n    int\s+%s;" % field)
            self.assertNotRegex(merc, r"\n    sh_int\s+%s;" % field)

    def test_nothing_narrows_them_back(self) -> None:
        cast = re.compile(r"->(?:max_)?(?:hit|mana|move)\s*[-+]?=\s*\(\s*sh_int\s*\)")
        found = [f"{p.name}:{n}"
                 for p in sorted((ROOT / "src").glob("*.c"))
                 for n, line in enumerate(p.read_text(encoding="latin-1").splitlines(), 1)
                 if cast.search(line)]
        self.assertEqual(found, [])

    @unittest.skipIf(_SKIP is not None, _SKIP or "")
    def test_ganon_spawns_with_all_his_hit_points(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbighp", PW)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zbighp", Levl=70, Room=4207)
            with mud.connect(timeout=120) as client:
                login(client, "Zbighp", PW)
                # Ganon is hidden and translucent: staff need holylight to stat him.
                client.command("holylight", 1.0)
                # The floors are each mobile's lowest roll: 16d10+35912 and
                # 50d10+44500, both past 32,767.
                for vnum, floor in ((GANON, 35928), (UNDEAD_CLERIC, 44550)):
                    client.command("load mob %d" % vnum, 1.0)
                    keyword = "ganon" if vnum == GANON else "cleric"
                    said = client.command("stat mob %s" % keyword, 1.5)
                    hp = re.search(r"Hp: (-?\d+)/(-?\d+)", said)
                    self.assertIsNotNone(hp, said)
                    self.assertGreaterEqual(int(hp.group(2)), floor, said)
                    self.assertEqual(hp.group(1), hp.group(2), said)
                    client.command("purge %s" % keyword, 1.0)


if __name__ == "__main__":
    unittest.main()
