from __future__ import annotations

import re
import unittest
from pathlib import Path


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


class PsionicsSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="utf-8")
        cls.stubs = (ROOT / "src" / "stubs.c").read_text(encoding="utf-8")
        cls.const = (ROOT / "src" / "const.c").read_text(encoding="utf-8")
        cls.act_wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.command_help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.skill_help = (ROOT / "area" / "skills.are").read_text(
            encoding="latin-1"
        )

    def test_all_seventeen_powers_are_grantable_and_documented(self) -> None:
        expected = {
            "astral walk",
            "clairvoyance",
            "confuse",
            "ego whip",
            "enervate",
            "mind leech",
            "mindbar",
            "mindblast",
            "nightmare",
            "project",
            "psionic armor",
            "psychic shield",
            "pyrotechnics",
            "shift",
            "telekinesis",
            "torment",
            "transfusion",
        }
        names_block = function_body(
            self.stubs,
            "static const char * const psionic_skill_names[]",
            "static char *trim_psionic_selection",
        )
        listed = set(re.findall(r'"([a-z ]+)"', names_block))

        self.assertEqual(expected, listed)
        self.assertIn("static const int psi_set_sizes[4] = { 4, 4, 4, 5 }", self.stubs)
        self.assertIn("all 17 psionic skills", self.command_help)
        for name in expected:
            self.assertIn(name.upper(), self.skill_help.upper())

    def test_grant_parser_rejects_invalid_and_uses_exact_names(self) -> None:
        normalizer = function_body(
            self.stubs,
            "bool normalize_psionic_arguments",
            "void grant_psionics",
        )
        grant = function_body(self.stubs, "void grant_psionics", "void list_group_known")

        self.assertIn("canonical_psionic_selection", normalizer)
        self.assertIn("<empty selection>", normalizer)
        self.assertIn("psionic_spec_contains", grant)
        self.assertNotIn("strstr(", grant)
        self.assertIn("normalize_psionic_arguments(ch->pcdata->psionic_grant_spec", grant)
        self.assertIn("discarded an invalid saved grant list", grant)
        self.assertIn("if ( selected == 0 )", grant)
        self.assertIn("mind leech", self.act_wiz)
        self.assertIn("enervate", self.act_wiz)

    def test_projection_controls_the_created_mobile_and_respects_barriers(self) -> None:
        project = function_body(self.magic2, "void do_project", "void do_mindleech")

        self.assertIn("psionic_switch_into(ch, victim)", project)
        self.assertNotIn('do_switch(ch,"ghost")', project)
        self.assertIn("psionic_remote_room_blocked", project)
        self.assertLess(
            project.index("get_mob_index(MOB_VNUM_PSIONIC_PROJECTION)"),
            project.index("ch->mana -= 25"),
        )
        self.assertIn("WAIT_STATE( ch, skill_table[gsn_project].beats )", project)
        self.assertRegex(
            self.const,
            r'(?s)"project".*?&gsn_project,\s+SLOT\( 0\),\s+0,\s+4,',
        )

    def test_remote_travel_validates_before_spending_mana(self) -> None:
        astral = function_body(self.magic2, "void do_astral_walk", "void do_telekinesis")
        shift = function_body(self.magic2, "void do_shift", "void spell_major_globe")

        self.assertLess(astral.index("victim = get_char_world"), astral.index("ch->mana -= 70"))
        self.assertLess(shift.index("victim = get_char_world"), shift.index("ch->mana -= 70"))
        for body in (astral, shift):
            self.assertIn("psionic_remote_room_blocked", body)
            self.assertIn("victim->in_room == ch->in_room", body)
            self.assertIn("ROOM2_NO_TPORT", self.magic2)
            self.assertIn("WAIT_STATE", body)
            self.assertIn("check_improve", body)

    def test_telekinesis_preserves_pickup_and_room_restrictions(self) -> None:
        telekinesis = function_body(self.magic2, "void do_telekinesis", "void do_confuse")

        self.assertIn("!CAN_WEAR(obj, ITEM_TAKE)", telekinesis)
        self.assertNotIn("obj->wear_flags < ITEM_TAKE", telekinesis)
        self.assertIn("ITEM2_NO_TPORT", telekinesis)
        self.assertIn("psionic_remote_room_blocked", telekinesis)
        self.assertIn("!can_loot(ch, obj)", telekinesis)
        self.assertIn("OBJ_VNUM_QUEST_TOKEN_FIRST", telekinesis)
        self.assertIn("check_improve(ch,gsn_telekinesis,found,4)", telekinesis)

    def test_confuse_uses_its_real_cost_and_allows_a_save(self) -> None:
        confuse = function_body(self.magic2, "void do_confuse", "void do_clairvoyance")

        self.assertIn("mana_cost = ch->level + 50", confuse)
        self.assertIn("if ( ch->mana < mana_cost )", confuse)
        self.assertNotIn("ch->mana < 139", confuse)
        self.assertIn("saves_spell(ch->level, victim)", confuse)
        self.assertLess(confuse.index("is_affected(victim, gsn_confuse)"), confuse.index("ch->mana -= mana_cost"))
        self.assertIn("psionic_start_combat", confuse)

    def test_clairvoyance_does_not_physically_move_or_count_exploration(self) -> None:
        clairvoyance = function_body(
            self.magic2, "void do_clairvoyance", "void do_pyrotechnics"
        )

        self.assertNotIn("char_from_room", clairvoyance)
        self.assertNotIn("char_to_room", clairvoyance)
        self.assertIn("ch->in_room = victim->in_room", clairvoyance)
        self.assertIn("ch->in_room = was_in_room", clairvoyance)

    def test_drains_respect_saves_defenses_and_actual_damage(self) -> None:
        mindleech = function_body(self.magic2, "void do_mindleech", "void do_enervate")
        enervate = function_body(self.magic2, "void do_enervate", "void do_mindblast")

        self.assertIn("saves_spell( ch->level, victim )", mindleech)
        self.assertIn("psionic_reduce_mental_drain", mindleech)
        self.assertIn("psionic_start_combat", mindleech)
        self.assertIn("psionic_reduce_mental_drain", enervate)
        self.assertIn("victim_hit_before - victim->hit", enervate)
        self.assertIn("actual_damage / 2", enervate)

    def test_ego_whip_save_prevents_the_attribute_penalty(self) -> None:
        ego_whip = function_body(
            self.magic2, "void do_ego_whip", "void do_psionic_armor"
        )

        self.assertIn("resisted = saves_spell( level, victim )", ego_whip)
        self.assertIn("if ( !resisted && !is_affected", ego_whip)
        self.assertIn("if ( resisted )", ego_whip)

    def test_nightmare_resistance_still_starts_combat(self) -> None:
        nightmare = function_body(
            self.magic2, "void do_nightmare", "void spell_cure_nightmare"
        )

        self.assertGreaterEqual(nightmare.count("psionic_start_combat"), 2)
        self.assertNotIn("damage(ch,victim,1", nightmare)
        self.assertLess(
            nightmare.index("is_affected(victim, gsn_nightmare)"),
            nightmare.index("ch->mana -= 20"),
        )

    def test_defenses_and_transfusion_do_not_charge_for_no_effect(self) -> None:
        armor = function_body(
            self.magic2, "void do_psionic_armor", "void do_psychic_shield"
        )
        shield = function_body(
            self.magic2, "void do_psychic_shield", "void do_mindbar"
        )
        mindbar = function_body(self.magic2, "void do_mindbar", "void do_torment")
        transfusion = function_body(self.magic2, "void do_transfusion", "void do_shift")

        self.assertLess(armor.index("psionic_defense_active"), armor.index("ch->mana -= 20"))
        self.assertLess(mindbar.index("psionic_defense_active"), mindbar.index("ch->mana -= 50"))
        self.assertLess(shield.index("recipients == 0"), shield.index("ch->mana -= 50"))
        self.assertIn("victim == ch", transfusion)
        self.assertIn("victim->hit >= victim->max_hit", transfusion)
        self.assertIn("check_improve( ch, gsn_transfusion, true, 4 )", transfusion)
        self.assertIn("WAIT_STATE( ch, skill_table[gsn_transfusion].beats )", transfusion)
        self.assertIn("update_pos( victim )", transfusion)
        self.assertRegex(
            self.const,
            r'(?s)"transfusion".*?&gsn_transfusion,\s+SLOT\( 0\),\s+0,\s+12,',
        )

    def test_help_no_longer_claims_nonexistent_toggle_mechanics(self) -> None:
        combined = self.command_help + self.skill_help

        self.assertNotIn("Toggle psychic resonance mode", combined)
        self.assertNotIn("Toggle the psionic awareness channel", combined)
        self.assertNotIn("all 16 psionic", combined)
        self.assertRegex(
            self.skill_help.lower(), r"does\s+not consume a light source"
        )

    def test_psionic_mob_ai_uses_a_fair_bounded_power_pool(self) -> None:
        special = function_body(
            self.special, "bool spec_psionic", "bool spec_executioner"
        )

        self.assertIn("psi_sel = number_range( 1, psi_max )", special)
        self.assertNotIn("number_bits( 4 )", special)
        self.assertIn('do_psionic_armor(mob, "")', special)
        self.assertIn('do_mindbar(mob, "")', special)
        for command in (
            "do_torment",
            "do_ego_whip",
            "do_nightmare",
            "do_pyrotechnics",
            "do_confuse",
            "do_enervate",
            "do_mindleech",
            "do_mindblast",
        ):
            self.assertIn(command, special)


if __name__ == "__main__":
    unittest.main()
