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

The order matters too (review, 2026-11-12). damage() takes the wards first
and the armour's cut last, and the armour's cut is a fixed amount, so
CONSIDER, which cut the armour first and halved what was left for
sanctuary, read a sanctuaried foe's armoured blows harder than they land:
100 against armour -20 as 40, where the fight averages 30. Both now run
the same steps (blow_landed_expected in fight.c). The live test holds
CONSIDER's numbers to damage()'s arithmetic, worked here from the blow
COMPARE PROFILE reports and the armour STAT shows.
"""

from __future__ import annotations

import re
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
        side = src.split("static double consider_side(", 1)[1].split("\n}\n", 1)[0]
        for helper in ("consider_accuracy_ratio(", "consider_defence_pass(",
                       "blow_landed_expected("):
            self.assertIn(helper, side, helper)
        fight = src.split("void gear_consider_fight(", 1)[1].split("\n}\n", 1)[0]
        self.assertEqual(fight.count("consider_side("), 2)
        # The wards, immunity and a shield are damage()'s own code now.
        steps = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        steps = steps.split("static int blow_before_armor(", 1)[1].split("\n}\n", 1)[0]
        for rule in ("AFF_SANCTUARY", "AFF_PROTECT", "AFF2_DIVINE_PROT", "check_immune("):
            self.assertIn(rule, steps, rule)
        avoid = src.split("static double consider_defence_pass(", 1)[1].split("\n}\n", 1)[0]
        for rule in ("gsn_parry", "gsn_dodge", "gsn_shield_block", "UMIN( 30, def->level )"):
            self.assertIn(rule, avoid, rule)


def c_div(a: int, b: int) -> int:
    """C's integer division: truncated toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def armor_mean(dam: int, ac: int) -> float:
    """number_range( floor, dam )'s mean against a mobile, as damage()
    rolls it: the floor is dam less (100 - ac) a third, below zero 1."""
    if dam <= 1:
        return float(dam)
    low = dam + c_div(-100 + ac, 3)
    if low < 0:
        low = 1
    return float(low) if low >= dam else (low + dam) / 2.0


def landed(blow: float, ac: int, sanctuary: bool) -> float:
    """damage()'s landed blow against a mobile with nothing after the
    roll: sanctuary first, the armour's cut last, a straight line between
    whole blows (blow_landed_expected)."""
    def whole(dam: int) -> float:
        return armor_mean(dam // 2 if sanctuary else dam, ac)
    low = int(blow)
    value = whole(low)
    if blow > low:
        value += (whole(low + 1) - value) * (blow - low)
    return value


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
                # A big blow into thick armour: the armour's cut (a fixed
                # amount) is then a large share, so where it falls in the
                # order shows.
                staff.must("set char zconsplay damroll 500", "damroll set")
                staff.must("set char sparring ac -400", "armour set")
                stat = staff.must("stat mob sparring", "Armor:")
                armour = [int(v) for v in re.search(
                    r"Armor: pierce: (-?\d+)\s+bash: (-?\d+)\s+slash: (-?\d+)"
                    r"\s+magic: (-?\d+)", stat).groups()]
                self.assertEqual(len(set(armour)), 1, stat)
                profile = player.must("compare profile", "a hit")
                blow = float(re.search(r"([\d.]+) a hit", profile).group(1))

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
        # Its sanctuary halves your blows before its armour cuts them, as
        # damage() does: from the same round, the prediction follows
        # damage()'s arithmetic, and is well short of the half the old
        # order gave.
        ac = armour[0]
        self.assertGreater(blow, 2 * (100 - ac) / 3, (blow, ac, "the floor must not clamp"))
        predicted = y0 * landed(blow, ac, True) / landed(blow, ac, False)
        self.assertAlmostEqual(y1, predicted, delta=0.15 + predicted * 0.005,
                               msg=(y0, y1, predicted, blow, ac))
        self.assertLess(y1, y0 / 2 * 0.9, (y0, y1, "the old order: armour, then sanctuary"))
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
