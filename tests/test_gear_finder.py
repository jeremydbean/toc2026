"""The dashboard's gear finder covers every slot and every wearable item.

It used to list only what it could score from bonus affects, under the
wear flags' own names in alphabetical order. That dropped three kinds of
item without a word: lights, because a light is worn for what it is and
carries no wear flag; plain armour and most shields, because an armour
piece's own AC (values[0..3]) counted for nothing, so they scored zero
and anything scoring zero was thrown away; and it ranked a positive save
as a bonus, when saves_spell() subtracts saving_throw and a positive
save is a penalty.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import fastapi  # noqa: F401  -- webadmin.server will not import without it

    WEBADMIN_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip this
    WEBADMIN_UNAVAILABLE_REASON = (
        f"webadmin dependencies unavailable ({type(exc).__name__}: {exc}). "
        "Install webadmin/requirements.txt."
    )

SAVE_VS_SPELL = 24


def item(vnum, item_type, wear, values=("0", "0", "0", "0", "0"), affects=(),
         level=1, carried_by=(2400,)):
    from webadmin.area_parser import Object

    return Object(
        vnum=vnum, keywords="thing", short_desc=f"thing {vnum}", long_desc="",
        material="", item_type=str(item_type), extra_flags="0",
        extra_flags2="0", wear_flags=wear, values=list(values), level=level,
        weight=1, cost=0, condition="P",
        affects=[{"location": loc, "modifier": mod} for loc, mod in affects],
        area_name="Test", carried_by=list(carried_by),
    )


@unittest.skipIf(WEBADMIN_UNAVAILABLE_REASON is not None, WEBADMIN_UNAVAILABLE_REASON or "")
class GearFinderTests(unittest.TestCase):
    def find(self, *objects, level=50):
        from webadmin import server

        fake = SimpleNamespace(objects={o.vnum: o for o in objects})
        with patch.object(server, "parser", fake):
            return asyncio.run(server.get_best_gear(
                class_name="mage", race_name="human", level=level, limit=10))

    def test_every_slot_is_listed_in_game_order_even_when_empty(self) -> None:
        from webadmin import server

        result = self.find()
        self.assertEqual(list(result), [label for _k, label in server.GEAR_FINDER_SLOTS])
        self.assertIn("Light", result)
        self.assertTrue(all(items == [] for items in result.values()))

    def test_a_light_with_no_wear_flag_is_a_light(self) -> None:
        result = self.find(item(1, 1, "A"))
        self.assertEqual([i["vnum"] for i in result["Light"]], [1])

    def test_plain_armour_is_scored_by_its_own_ac(self) -> None:
        # A shield and a breastplate with no bonuses at all.
        result = self.find(item(2, 9, "AJ", ("4", "4", "4", "4", "0")),
                           item(3, 9, "AD", ("4", "4", "4", "4", "0")))
        self.assertEqual(result["Shield"][0]["score"], 4)
        # apply_ac() counts armour three times on the body.
        self.assertEqual(result["Body"][0]["score"], 12)

    def test_an_item_with_nothing_on_it_is_still_listed(self) -> None:
        result = self.find(item(4, 11, "AE"))
        self.assertEqual([i["vnum"] for i in result["Head"]], [4])

    def test_a_positive_save_is_a_penalty(self) -> None:
        result = self.find(item(5, 9, "AB", affects=[(SAVE_VS_SPELL, 5)]),
                           item(6, 9, "AB", affects=[(SAVE_VS_SPELL, -5)]))
        ranked = [i["vnum"] for i in result["Left Finger"]]
        self.assertEqual(ranked, [6, 5])
        self.assertLess(result["Left Finger"][1]["score"], 0)

    def test_every_slot_on_a_character_is_a_slot_here(self) -> None:
        """All eighteen wear locations, named as the equipment view
        names them, so the two can be read side by side."""
        from webadmin import server

        self.assertEqual(list(self.find()),
                         [server.WEAR_SLOT_NAMES[i] for i in range(18)])

    def test_a_pair_recommends_two_different_items(self) -> None:
        rings = [item(10 + n, 9, "AB", affects=[(12, 10 * n)]) for n in (1, 2, 3)]
        result = self.find(*rings)
        self.assertEqual(result["Left Finger"][0]["vnum"], 13)
        self.assertEqual(result["Right Finger"][0]["vnum"], 12)
        self.assertNotIn(13, [i["vnum"] for i in result["Right Finger"]])

    def test_weapons_are_wielded_and_worn_nowhere_else(self) -> None:
        sword = item(7, 5, "ANO", ("0", "2", "6", "3", "0"))
        result = self.find(sword)
        self.assertEqual([i["vnum"] for i in result["Wielded"]], [7])
        self.assertEqual(result["Held"], [])

    def test_items_no_mob_carries_are_excluded(self) -> None:
        """A recommendation you cannot get is noise: only gear a mob
        carries or wears (carried_by) is ranked."""
        dropped = item(9, 11, "AE", affects=[(18, 5)])          # carried
        unique = item(10, 11, "AE", affects=[(18, 50)], carried_by=())  # no mob
        result = self.find(dropped, unique)
        heads = [i["vnum"] for i in result["Head"]]
        self.assertIn(9, heads)
        self.assertNotIn(10, heads)

    def test_the_level_limit_still_applies(self) -> None:
        result = self.find(item(8, 11, "AE", level=40), level=10)
        self.assertEqual(result["Head"], [])

    # ---- damage-forward scoring --------------------------------------
    # Survivability stats roll onto gear in large numbers; damage stats in
    # single digits. The weights are tuned so an ordinary damage upgrade
    # outranks an ordinary hp roll, while a genuinely huge hp bump still
    # wins over a marginal damage gain. These pin both halves.
    def find_as(self, class_name, *objects, level=50):
        from webadmin import server

        fake = SimpleNamespace(objects={o.vnum: o for o in objects})
        with patch.object(server, "parser", fake):
            return asyncio.run(server.get_best_gear(
                class_name=class_name, race_name="human", level=level, limit=10))

    def test_damage_outranks_a_plain_hp_roll_for_a_fighter(self) -> None:
        dmg = item(20, 9, "AB", affects=[(19, 8)])    # +8 damroll
        hp = item(21, 9, "AB", affects=[(13, 50)])    # +50 hit points
        ranked = [i["vnum"] for i in self.find_as("warrior", dmg, hp)["Left Finger"]]
        self.assertEqual(ranked[0], 20,
                         "a damage upgrade should outrank a plain hp roll")

    def test_a_huge_hp_bump_still_beats_a_marginal_damage_gain(self) -> None:
        hp = item(22, 9, "AB", affects=[(13, 150)])   # +150 hit points
        dmg = item(23, 9, "AB", affects=[(19, 2)])    # +2 damroll
        ranked = [i["vnum"] for i in self.find_as("warrior", hp, dmg)["Left Finger"]]
        self.assertEqual(ranked[0], 22,
                         "a very large hp bump should still win over a tiny damage gain")


if __name__ == "__main__":
    unittest.main()
