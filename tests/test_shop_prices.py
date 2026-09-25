"""Shop prices measured against what the people shopping there can earn.

`obj->cost` is copper, and the coin a mobile carries is rolled from its
level in six steps (see `load_mobiles` in src/db.c). A level 4 mobile
carries one to eight copper; a level 10 one carries about five gold. From
level 10 up, prices sit where you would expect against that -- the median
object costs roughly forty kills of a mobile its own level. Below it they
did not: a turkey burger in Mud School cost ten gold, or sixty-six
thousand level 1 kills, and every character in the game starts in Mud
School with nothing.

`tools/reprice_by_level.py` rescaled the bottom of the curve. These tests
hold it there, and hold the reader that the repricing depends on.
"""
from __future__ import annotations

import pathlib
import statistics
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import reprice_by_level as reprice          # noqa: E402
import costs_to_copper                      # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402

COPPER_PER_GOLD = 10000

# Mud School is where every character starts, with nothing in their purse.
MUD_SCHOOL_SHOPS = (3717, 3762)

# What a shelf may cost the bracket it serves. The world median is
# thirty-three kills. This is a floor under catastrophe, not the aim: a
# shop deliberately selling luxuries to rich passers-by runs into the
# hundreds, and before the reprice the worst shelf in the world stood at
# twenty-two billion.
MAX_MEDIAN_KILLS = 10000

# Dresden is the city every character walks out of Mud School into, and
# these two shops are where they buy their first armour and weapon.
DRESDEN_LEATHER_WORKER = 2427
DRESDEN_WEAPONSMITH = 2424
MAX_STARTER_KIT_KILLS = 60


class PriceCurveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = reprice.build_world()
        cls.levels = reprice.buyer_levels(cls.world)
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_the_repricing_model_has_nothing_left_to_say(self) -> None:
        """The tool is a fixed point on the committed area files.

        Which makes this a regression test for every price it set, in one
        assertion: a new object priced for a level 1 buyer at ten gold
        moves that level's median and shows up here.
        """
        self.assertEqual(
            reprice.factors(self.world, self.levels), {},
            "tools/reprice_by_level.py would still change prices; run it",
        )

    def shelf_kills(self, keeper: int) -> list[float]:
        """What each thing on one shelf costs the bracket that shop serves."""
        markup = self.world["shops"][keeper]
        bracket = reprice.shop_levels(self.world)[keeper]
        return sorted(
            self.world["objects"][v]["cost"] * markup / 100
            / reprice.earn(bracket)
            for v in set(self.world["stock"][keeper])
            if v in self.world["objects"]
            and self.world["objects"][v]["cost"] > 0
        )

    def test_no_shelf_is_priced_out_of_its_own_bracket_entirely(self) -> None:
        """Every shop, measured against the mobiles its customers fight."""
        brackets = reprice.shop_levels(self.world)
        offenders = {}
        for keeper in self.world["stock"]:
            if keeper not in self.world["shops"] or keeper not in brackets:
                continue
            kills = self.shelf_kills(keeper)
            if not kills:
                continue
            median = statistics.median(kills)
            if median > MAX_MEDIAN_KILLS:
                mob = self.parser.mobiles.get(keeper)
                offenders[keeper] = "%s (%s): median %.0f kills at level %d" % (
                    mob.short_desc if mob else "?",
                    mob.area_name if mob else "?", median, brackets[keeper])

        self.assertEqual(offenders, {})

    def test_a_character_out_of_mud_school_can_outfit_themselves(self) -> None:
        """Dresden's leather worker and weaponsmith both serve level 5.

        Before the reprice the cheapest thing either of them sold -- a
        leather cap -- was fifty-four thousand kills away.
        """
        for keeper in (DRESDEN_LEATHER_WORKER, DRESDEN_WEAPONSMITH):
            kills = self.shelf_kills(keeper)
            with self.subTest(keeper=keeper):
                self.assertLessEqual(
                    kills[0], MAX_STARTER_KIT_KILLS,
                    "nothing on shop %d's shelf is within reach" % keeper,
                )
                # Half the shelf, not just the loss leader.
                self.assertLessEqual(
                    statistics.median(kills), 4 * MAX_STARTER_KIT_KILLS,
                    "shop %d is mostly out of reach" % keeper,
                )

    def test_mud_school_is_priced_in_coppers(self) -> None:
        """A new character arrives with an empty purse and fights level 1
        and 2 mobiles, which carry one or two copper each."""
        priced = {}
        for keeper in MUD_SCHOOL_SHOPS:
            for vnum in set(self.world["stock"].get(keeper, [])):
                obj = self.world["objects"].get(vnum)
                if obj and obj["cost"] > 0:
                    priced[vnum] = obj["cost"]

        self.assertTrue(priced, "Mud School's shops stock nothing priced")
        dear = {v: c for v, c in priced.items() if c > COPPER_PER_GOLD}
        self.assertEqual(
            dear, {},
            "nothing in Mud School should cost more than a gold piece",
        )


class AreaReaderTests(unittest.TestCase):
    """The object reader both price tools depend on.

    costs_to_copper.py used to find the next record by scanning for the
    next "\\n#", which is not a record boundary: a Hyrule dungeon map
    carries an ASCII floor plan in an extra description and several of its
    rows start with a hash. The scan landed inside one, found no vnum
    after it, and stopped -- leaving the last 85 objects in the world
    priced in gold while everything else had moved to copper, so a
    Magical Shield advertised at 130 rupees sold for one silver thirty.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_both_readers_see_every_object_the_dashboard_sees(self) -> None:
        mine = {}
        for path in reprice.listed_areas():
            for obj in reprice.read_objects(path.read_text("latin-1")):
                mine[obj["vnum"]] = (obj["cost"], obj["level"])

        for path in costs_to_copper.loaded_areas():
            _, problems = costs_to_copper.cost_spans(path.read_text("latin-1"))
            self.assertEqual(problems, [], path.name)

        theirs = {
            v: (o.cost, o.level) for v, o in self.parser.objects.items()
            # hyrule.are is generated and the repricer leaves it alone,
            # so it is not in that reader's listing.
            if o.area_file != "hyrule.are"
        }
        self.assertEqual(mine, theirs)

    def test_the_converter_reaches_the_end_of_the_world(self) -> None:
        seen = sum(
            len(costs_to_copper.cost_spans(p.read_text("latin-1"))[0])
            for p in costs_to_copper.loaded_areas()
        )
        self.assertEqual(seen, len(self.parser.objects))


if __name__ == "__main__":
    unittest.main()
