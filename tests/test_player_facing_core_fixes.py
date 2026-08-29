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


class PlayerFacingCoreFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.command_help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.skill_help = (ROOT / "area" / "skills.are").read_text(
            encoding="latin-1"
        )

    def test_autogold_takes_actual_money_and_autosac_preserves_loot(self) -> None:
        helper = function_body(
            self.fight,
            "static void handle_automatic_corpse_commands",
            "static bool is_hyrule_ganon",
        )
        damage = function_body(self.fight, "bool damage", "bool is_safe")
        fatality = function_body(self.fight, "void fatality", "void do_shoot")

        self.assertIn("coin->item_type == ITEM_MONEY", helper)
        self.assertIn("get_obj( ch, coin, corpse )", helper)
        self.assertNotIn("do_get(ch, coin->name)", helper)
        self.assertLess(
            helper.index("if ( corpse->contains != NULL )"),
            helper.index('do_sacrifice( ch, "corpse" )'),
        )
        self.assertIn("still contains loot", helper)
        self.assertIn("handle_automatic_corpse_commands( ch )", damage)
        self.assertIn("handle_automatic_corpse_commands( ch )", fatality)

    def test_normal_shoot_respects_routes_targets_and_skill_growth(self) -> None:
        shoot = function_body(self.fight, "void do_shoot", "void do_steel_fist")

        self.assertIn("chance = get_skill( ch, gsn_archery )", shoot)
        self.assertIn("EX_CLOSED", shoot)
        self.assertIn("EX_SECRET", shoot)
        self.assertIn("can_see_room(ch, pexit->u1.to_room)", shoot)
        self.assertIn("if ( !IS_NPC(victim) )", shoot)
        self.assertLess(
            shoot.index("if ( !IS_NPC(victim) )"), shoot.index("check_killer( ch, victim )")
        )
        self.assertNotIn("ACT_NOPURGE", shoot)
        self.assertIn("check_improve( ch, gsn_archery, true, 4 )", shoot)
        self.assertIn("check_improve( ch, gsn_archery, false, 4 )", shoot)
        self.assertIn("ch->hit = UMAX(1, ch->hit - 4)", shoot)

        pursuit = shoot.split("move_char(victim,door2,false);", 1)[1]
        self.assertLess(
            pursuit.index("character_is_active(victim)"),
            pursuit.index("victim->in_room == was_in_room"),
        )

    def test_reflected_damage_honors_relics_without_dead_position(self) -> None:
        damage = function_body(self.fight, "bool damage", "bool is_safe")
        reflection = damage.split("int dt1, dam_type1;", 1)[1].split(
            "Sleep spells and extremely wounded folks", 1
        )[0]

        self.assertIn(
            "apply_hyrule_relic_damage_reduction( ch, dam1, dam_type1 )",
            reflection,
        )
        self.assertLess(
            reflection.index("if(ch->hit <= 0)"),
            reflection.index("update_pos(ch)"),
        )

    def test_guards_can_reach_the_innocent_protection_branch(self) -> None:
        guard = function_body(self.special, "bool spec_guard", "bool spec_janitor")
        no_criminal = guard.split("if ( victim == NULL )", 1)[1].split(
            "if ( victim->level", 1
        )[0]

        self.assertIn("if ( ech == NULL )", no_criminal)
        self.assertIn("multi_hit( mob, ech, TYPE_UNDEFINED )", no_criminal)
        self.assertIn("PROTECT THE INNOCENT!!  BANZAI!!'", no_criminal)

    def test_npc_mana_convert_never_dereferences_pcdata(self) -> None:
        mana_convert = function_body(
            self.magic, "void spell_mana_convert", "void spell_mass_healing"
        )

        special_case = mana_convert.split("Special case for the C/M", 1)[1].split(
            "if (counter == 1)", 1
        )[0]
        self.assertIn("!IS_NPC(ch)", special_case)
        self.assertLess(
            special_case.index("!IS_NPC(ch)"),
            special_case.index("ch->pcdata->guild"),
        )

    def test_player_help_describes_safe_loot_and_ranged_rules(self) -> None:
        command_help = " ".join(self.command_help.lower().split())
        skill_help = " ".join(self.skill_help.lower().split())

        self.assertIn("only empty corpses are sacrificed", command_help)
        self.assertIn("open adjacent exit", command_help)
        self.assertIn("visible mobile through an open exit", skill_help)


if __name__ == "__main__":
    unittest.main()
