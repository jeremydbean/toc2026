from __future__ import annotations

import re
import unittest
from pathlib import Path

from webadmin.area_parser import AreaParser


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


class AdditionalRareMechanicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.act_move = (ROOT / "src" / "act_move.c").read_text(encoding="utf-8")
        cls.act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        cls.magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="utf-8")
        cls.quest = (ROOT / "src" / "quest.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.command_help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.skill_help = (ROOT / "area" / "skills.are").read_text(
            encoding="latin-1"
        )
        cls.spell_help = (ROOT / "area" / "spells.are").read_text(
            encoding="latin-1"
        )
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_lore_cannot_mint_gold_and_reports_complete_estimates(self) -> None:
        lore = function_body(self.magic2, "void do_lore", "void do_project")

        self.assertRegex(lore, r"research_cost\s*=\s*UMAX\(\s*0,")
        self.assertIn("add_money(ch, -research_cost)", lore)
        self.assertIn("save_char_obj(ch)", lore)
        self.assertRegex(
            lore,
            r"estimate it's worth about %d gold[^;]+;\s*send_to_char\( buf, ch \)",
        )
        self.assertIn("for ( i = 1; i <= 3; i++ )", lore)
        self.assertIn("number_percent() <= chance", lore)
        self.assertGreaterEqual(lore.count("lore_estimate(paf->modifier)"), 2)
        self.assertIn("stat1 * ( stat2 + 1 ) / 2", lore)

    def test_water_spells_choose_sufficient_water_and_preserve_container(self) -> None:
        catalyst = function_body(
            self.magic2, "static OBJ_DATA *find_water_catalyst", "void spell_water_burst"
        )
        burst = function_body(
            self.magic2, "void spell_water_burst", "void spell_geyser"
        )
        geyser = function_body(
            self.magic2, "void spell_geyser", "void spell_spiritual_hammer"
        )

        self.assertIn("obj->value[2] == LIQ_WATER", catalyst)
        self.assertIn("obj->value[1] >= amount", catalyst)
        self.assertIn("obj->value[1] -= 20", burst)
        self.assertIn("obj->value[1] -= 45", geyser)
        self.assertNotIn("extract_obj(obj)", geyser)
        self.assertIn("save_char_obj(ch)", burst)
        self.assertIn("save_char_obj(ch)", geyser)

    def test_soul_containers_skip_filled_bottles_and_persist(self) -> None:
        trap = function_body(
            self.magic2,
            "void spell_trap_the_soul_fixed",
            "/*(void spell_trap_the_soul",
        )
        open_command = function_body(self.act_move, "void do_open", "void do_close")

        self.assertIn("obj->value[3] == 0", trap)
        self.assertIn("no empty soul container", trap)
        self.assertIn("save_char_obj(ch)", trap)
        self.assertRegex(
            open_command,
            r"extract_obj\(obj\);\s*if \( !IS_NPC\(ch\) \)\s*"
            r"save_char_obj\(ch\);\s*if \( attacks_opener \)",
        )

    def test_raise_dead_preserves_items_that_cannot_be_carried(self) -> None:
        raise_dead = function_body(
            self.magic2, "void spell_raise_dead", "void spell_dust_devil"
        )

        self.assertIn("find_online_player_exact(arg)", raise_dead)
        self.assertNotIn("get_char_world(ch,arg)", raise_dead)
        self.assertGreaterEqual(raise_dead.count("continue;"), 2)
        self.assertIn("if ( corpse->contains == NULL )", raise_dead)
        self.assertIn("remain in the corpse", raise_dead)
        self.assertIn("save_char_obj(victim)", raise_dead)

    def test_summoned_undead_remain_controlled_for_their_lifetime(self) -> None:
        boundaries = (
            ("void spell_create_skeleton", "void spell_create_wraith"),
            ("void spell_create_wraith", "void spell_create_vampire"),
            ("void spell_create_vampire", "void spell_animate_parts"),
        )
        for start, end in boundaries:
            with self.subTest(spell=start):
                body = function_body(self.magic2, start, end)
                self.assertIn("af.duration  = victim->timer", body)
                self.assertNotIn("number_fuzzy( ch->level )", body)

    def test_transfusion_cannot_leave_the_user_at_zero_hp(self) -> None:
        transfusion = function_body(
            self.magic2, "void do_transfusion", "void do_shift"
        )

        self.assertIn("if ( ch->hit <= 50 )", transfusion)
        self.assertIn("ch->hit -= 50", transfusion)

    def test_quest_rewards_are_not_overwritten_or_overflowed(self) -> None:
        quest = function_body(self.quest, "void do_quest", "void generate_quest")
        converter = function_body(
            self.special, "bool spec_xp_converter", "bool spec_club_bouncer"
        )

        pending = quest.index("Resolve your pending AQUEST GAMBLE offer")
        assignment = quest.index("generate_quest(ch, questman)")
        self.assertLess(pending, assignment)
        self.assertIn("SHRT_MAX - ch->practice", quest)
        self.assertIn("ch->queststreak < SHRT_MAX", quest)
        self.assertIn("ch->questrush  = false", quest)
        self.assertGreaterEqual(quest.count("save_char_obj(ch)"), 8)

        self.assertIn("ch->exp >= xp", converter)
        self.assertIn("SHRT_MAX - ch->practice", converter)
        self.assertIn("save_char_obj(ch)", converter)

    def test_multi_race_restrictions_are_allowed_race_lists(self) -> None:
        requirements = function_body(
            self.act_obj, "static bool wear_requirements_met", "void do_secondary"
        )

        self.assertIn("allowed_races = obj->extra_flags2", requirements)
        self.assertIn("!IS_SET(allowed_races, wearer_race_flag)", requirements)
        self.assertNotIn("ITEM2_HUMAN_ONLY) && ch->race !=", requirements)

    def test_signature_relics_have_correct_slots_and_powers(self) -> None:
        expected = {
            9101: ("AG", "H"),   # winged boots: take + feet, flight
            29051: ("AK", "F"),  # robe: take + about, invisibility
            29056: ("AE", "G"),  # Eversight: take + head, detect invis
            29224: ("AE", "G"),  # Virtual Vision: take + head, detect invis
            29225: ("AI", "H"),  # wings: take + arms, flight
        }

        for vnum, (wear_flags, power_flag) in expected.items():
            with self.subTest(vnum=vnum):
                obj = self.parser.objects[vnum]
                self.assertEqual(obj.wear_flags, wear_flags)
                self.assertIn(power_flag, obj.extra_flags2)

    def test_removing_one_effect_source_preserves_other_sources(self) -> None:
        self.assertIn("static void restore_character_affect_bits", self.handler)
        self.assertIn("race_table[ch->race].aff", self.handler)
        self.assertGreaterEqual(
            self.handler.count("restore_character_affect_bits("), 4
        )
        self.assertIn("IS_OBJ_STAT2(obj, ITEM2_ADD_FLY)", self.handler)

    def test_help_matches_the_repaired_mechanics(self) -> None:
        self.assertIn("possibly to zero for simple items", self.command_help)
        self.assertIn("pending double-or-nothing offer", self.command_help)
        self.assertIn("5-7 more", self.command_help)
        self.assertIn("cannot be used when doing so would reduce", self.skill_help)
        self.assertIn("too heavy remains safely in the corpse", self.spell_help)
        self.assertIn("Water burst consumes 20 units", self.spell_help)
        self.assertIn("Geyser consumes 45 units", self.spell_help)


if __name__ == "__main__":
    unittest.main()
