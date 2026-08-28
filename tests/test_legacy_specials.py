from __future__ import annotations

import re
import unittest
from pathlib import Path

from webadmin.area_parser import AreaParser, ITEM_TYPES


ROOT = Path(__file__).resolve().parents[1]


def function_body(source: str, start: str, end: str) -> str:
    match = re.search(
        rf"{re.escape(start)}(?P<body>.*?){re.escape(end)}",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Could not locate {start!r} before {end!r}")
    return match.group("body")


class LegacySpecialSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.quest = (ROOT / "src" / "quest.c").read_text(encoding="utf-8")
        cls.act_wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        cls.command_help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_farslay_scroll_requires_target_and_casts_once(self) -> None:
        recite = function_body(self.act_obj, "void do_recite", "void do_brandish")
        self.assertIn("farslay_scroll && arg2[0] == '\\0'", recite)
        self.assertIn("Recite the Farslay scroll at whom?", recite)
        self.assertIn("scroll->value[2] == farslay_sn", recite)
        self.assertIn("scroll->value[3] == farslay_sn", recite)
        self.assertEqual(recite.count("obj_cast_spell( farslay_sn"), 1)

        scroll = self.parser.objects[20305]
        self.assertEqual(scroll.item_type, "2")
        self.assertEqual(scroll.values, ["70", "532", "0", "0", "0"])

    def test_farslay_world_lookup_restores_holylight_exactly(self) -> None:
        recite = function_body(self.act_obj, "void do_recite", "void do_brandish")
        self.assertIn("bool added_holylight", recite)
        self.assertIn("added_holylight = true", recite)
        self.assertEqual(recite.count("if ( added_holylight )"), 2)
        self.assertNotIn("&& !IS_IMMORTAL(ch)", recite)

    def test_farslay_permanent_costs_cannot_underflow(self) -> None:
        spell = function_body(self.magic2, "void spell_vengence", "void spell_raise_dead")
        self.assertIn("!IS_NPC(ch) && ch->pcdata != NULL", spell)
        self.assertIn("UMAX(1, ch->max_hit - penalty)", spell)
        self.assertIn("UMAX(1, ch->pcdata->perm_hit - penalty)", spell)
        self.assertIn("UMAX(3, ch->perm_stat[nuke] - 3)", spell)
        self.assertNotIn("ch->pcdata->perm_hit -=", spell)
        self.assertIn("victim->pIndexData->vnum == 30225", spell)
        self.assertIn("ancient darkness binds", spell)

    def test_farslay_reward_is_really_available_and_help_is_accurate(self) -> None:
        for contract in (
            "#define QUEST_ITEM_POWER 20303",
            "#define QUEST_ITEM_GIANT 20304",
            "#define QUEST_ITEM_FARSLAY 20305",
            'is_name(arg2, "power empower")',
            'is_name(arg2, "giant strength")',
            'is_name(arg2, "farslay scroll")',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.quest)

        self.assertIn("Syntax: recite farslay <character>", self.command_help)
        self.assertIn("AQUEST BUY FARSLAY", self.command_help)
        self.assertNotIn("AQUI BUY FARSLAY", self.command_help)
        self.assertNotIn("three successive castings", self.command_help)
        self.assertNotIn("type READ SCROLL", self.command_help)

    def test_herbie_selects_the_lowest_health_active_player(self) -> None:
        paramedic = function_body(
            self.special, "bool spec_paramedic", "bool spec_quest_master"
        )
        self.assertIn("lowest_health_percent", paramedic)
        self.assertIn("health_percent < lowest_health_percent", paramedic)
        self.assertIn("vch->desc == NULL", paramedic)
        self.assertIn("vch->desc->connected != CON_PLAYING", paramedic)
        self.assertIn("vch->position == POS_FIGHTING", paramedic)
        self.assertIn("IS_SET(vch->in_room->room_flags, ROOM_DT)", paramedic)
        self.assertNotIn("vch->max_hit / (vch->max_hit - vch->hit)", paramedic)

    def test_herbie_heal_is_bounded_and_returns_to_its_origin(self) -> None:
        paramedic = function_body(
            self.special, "bool spec_paramedic", "bool spec_quest_master"
        )
        self.assertIn("home_room = mob->in_room", paramedic)
        self.assertIn("most_hurt->hit = most_hurt->max_hit", paramedic)
        self.assertIn("char_to_room(mob,home_room)", paramedic)
        self.assertNotIn("while(most_hurt->hit", paramedic)
        self.assertNotIn("get_room_index(4911)", paramedic)
        self.assertIn("victim->desc->connected != CON_PLAYING", self.act_wiz)

    def test_only_rare_training_food_grants_trains(self) -> None:
        training_food = {
            obj.vnum for obj in self.parser.objects.values() if obj.item_type == "38"
        }
        self.assertEqual(training_food, {9955, 29926, 29927})
        self.assertEqual(self.parser.objects[29932].item_type, "19")
        self.assertEqual(self.parser.objects[29933].item_type, "19")
        self.assertEqual(ITEM_TYPES[38], "training food")

    def test_training_food_reward_is_bounded_saved_and_described(self) -> None:
        eat = function_body(self.act_obj, "void do_eat", "bool remove_obj")
        self.assertIn("ch->train >= SHRT_MAX", eat)
        self.assertIn("save_char_obj( ch )", eat)
        self.assertIn('return "training food"', self.handler)

        descriptions = " ".join(
            extra["description"]
            for extra in self.parser.objects[9955].extra_descr
        ).lower()
        self.assertIn("training session", descriptions)


if __name__ == "__main__":
    unittest.main()
