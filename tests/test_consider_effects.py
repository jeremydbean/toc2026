"""CONSIDER counts what damage() does to a blow (owner, 2026-11-11:
"consider should also account for spells on the mob and you. Like if the
mob is sanctuary and you have haste").

gear_consider_fight used to count each side's weapon damage against a
standard foe, halved for sanctuary, and nothing else: the foe's real
armour, its dodge and parry (a mobile's run at its level plus the level
difference), the armour cut from every blow, protection, divine
protection, immunities and a fire or frost shield's burn back were all
left out, and the players' "should win" fights took twice its rounds. It
now mirrors each of them. A typed CONSIDER writes its numbers to
log/progress.tsv (the consider row), which is what this test reads.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zconspass11"


class ConsiderSourceTests(unittest.TestCase):
    def test_the_fight_counts_what_damage_does(self) -> None:
        src = (ROOT / "src" / "gear_compare.c").read_text(encoding="latin-1")
        fight = src.split("void gear_consider_fight(", 1)[1].split("\n}\n", 1)[0]
        for helper in ("consider_accuracy_ratio(", "consider_after_armor(",
                       "consider_defence_pass(", "consider_blow_factor(", "consider_shield("):
            self.assertIn(helper, fight, helper)
        factor = src.split("static double consider_blow_factor(", 1)[1].split("\n}\n", 1)[0]
        for rule in ("AFF_SANCTUARY", "AFF_PROTECT", "AFF2_DIVINE_PROT", "consider_immune("):
            self.assertIn(rule, factor, rule)
        avoid = src.split("static double consider_defence_pass(", 1)[1].split("\n}\n", 1)[0]
        for rule in ("gsn_parry", "gsn_dodge", "gsn_shield_block", "UMIN( 30, def->level )"):
            self.assertIn(rule, avoid, rule)


def considered(text: str) -> list:
    return [line.split("\t") for line in text.splitlines()
            if line.split("\t")[1:2] == ["consider"]]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConsiderEffectsLiveTests(unittest.TestCase):
    def test_sanctuary_shield_and_haste_move_the_prediction(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name, level, extra in (("Zconsstaff", 70, {"HMV": "3000 3000 5000 5000 500 500",
                                                           "HMVP": "3000 5000 500"}),
                                       ("Zconsplay", 30, {"HMV": "3000 3000 500 500 500 500",
                                                          "HMVP": "3000 500 500", "AfBy": 512})):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=SPARRING_FLOOR, **extra)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zconsstaff", PW)
                login(player, "Zconsplay", PW)
                for client in (staff, player):
                    client.sync("scroll 0")
                for spell in ("sanctuary", "fire shield", "haste"):
                    staff.must(f"set skill zconsstaff '{spell}' 100", "")
                staff.must(f"load mob {SPARRING_GUARD}", "You create")

                plain = player.must("consider sparring", "level")
                staff.sync("cast sanctuary sparring", timeout=60)
                self.assertIn("sanctuary", staff.sync("stat mob sparring").lower())
                sanct = player.must("consider sparring", "level")
                staff.sync("cast 'fire shield' sparring", timeout=60)
                self.assertIn("fire shield", staff.sync("stat mob sparring").lower())
                player.must("consider sparring", "level")
                cast = staff.sync("cast haste zconsplay", timeout=60)
                self.assertIn("haste", player.sync("affects").lower(), cast)
                player.must("consider sparring", "level")
                for client in (player, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")

        rows = considered(text)
        self.assertEqual(len(rows), 4, text)
        (y0, t0), (y1, t1), (y2, t2), (y3, t3) = [(float(r[11]), float(r[12])) for r in rows]
        self.assertGreater(y0, 0, rows[0])
        # Its sanctuary halves your blows, and says so.
        self.assertAlmostEqual(y1, y0 / 2, delta=0.1 + y0 * 0.02, msg=(y0, y1))
        self.assertIn("sanctuary", sanct.lower(), sanct)
        self.assertAlmostEqual(t1, t0, delta=0.1, msg="its sanctuary does not change its blows")
        # Its fire shield burns you back for every blow of yours that lands.
        self.assertGreater(t2, t1, (t1, t2))
        self.assertAlmostEqual(t2 - t1, 0.6 * y2, delta=0.2 + y2 * 0.05, msg=(t1, t2, y2))
        # Your haste is another swing a round.
        self.assertGreater(y3, y2, (y2, y3))
        self.assertIn("level", plain)


if __name__ == "__main__":
    unittest.main()
