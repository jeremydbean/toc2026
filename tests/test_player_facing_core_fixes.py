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
        cls.act_move = (ROOT / "src" / "act_move.c").read_text(encoding="utf-8")
        cls.act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.act_wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
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

    def test_invalid_portals_do_not_spend_money_or_charges(self) -> None:
        enter = function_body(self.act_move, "void do_enter", "void trapped")

        destination = enter.index("to_room = get_room_index( obj->value[1] )")
        self.assertLess(destination, enter.index("add_money(ch,-500)"))
        self.assertLess(destination, enter.index("obj->value[2] -= 1"))
        self.assertIn('act("You can not enter the $p.",ch,obj,NULL,TO_CHAR)', enter)

    def test_riding_uses_equipment_hooks_and_survives_stale_mount_state(self) -> None:
        ride = function_body(self.act_move, "void do_ride", "void do_dismount")
        dismount = function_body(self.act_move, "void do_dismount", "void do_riding")

        self.assertIn("equip_char(victim,obj,WEAR_BODY)", ride)
        self.assertIn("get_eq_char(victim, WEAR_BODY) != obj", ride)
        self.assertIn("check_improve(ch,gsn_ride,true,6)", ride)
        self.assertLess(
            dismount.index("if(ch->pet == NULL)"),
            dismount.index("ch->pet->short_descr"),
        )
        self.assertIn("mount->master != NULL && mount->master->pet == mount", dismount)

    def test_monk_abilities_do_not_charge_for_impossible_actions(self) -> None:
        steel = function_body(self.fight, "void do_steel_fist", "void do_crane_dance")
        crane = function_body(self.fight, "void do_crane_dance", "void do_nerve_damage")
        iron = function_body(self.fight, "void do_iron_skin", "void damage_eq")

        self.assertLess(
            steel.index("is_affected(ch,gsn_steel_fist)"),
            steel.index("ch->mana -= 15"),
        )
        self.assertLess(
            iron.index("is_affected(ch,gsn_iron_skin)"),
            iron.index("ch->mana -= 45"),
        )
        self.assertNotIn("ch->mana -= 50", crane)
        self.assertIn("check_improve(ch,gsn_crane_dance,false,4)", crane)

        attacks = (
            ("void do_nerve_damage", "void do_blinding_fists", "ch->mana -= 15"),
            ("void do_blinding_fists", "void do_fists_of_fury", "ch->mana -= 20"),
            ("void do_fists_of_fury", "void do_stunning_blow", "ch->mana -= 30"),
            ("void do_stunning_blow", "void do_iron_skin", "ch->mana -= 15"),
        )
        for start, end, cost in attacks:
            body = function_body(self.fight, start, end)
            self.assertLess(body.index("IS_AFFECTED2( victim, AFF2_GHOST )"), body.index(cost))
            self.assertLess(body.index("IS_AFFECTED2( ch, AFF2_GHOST )"), body.index(cost))

    def test_bulk_put_rolls_concealment_per_item_and_reports_no_match(self) -> None:
        put = function_body(self.act_obj, "void do_put", "void do_drop")
        bulk = put.split("/* 'put all container' or 'put all.obj container' */", 1)[1]

        self.assertLess(bulk.index("hidden = false"), bulk.index("number_percent"))
        self.assertIn("You have nothing suitable to put in $P.", bulk)
        self.assertIn("check_improve(ch,gsn_sleight_of_hand,true,8)", put)

    def test_lycanthropy_ticks_consistently_and_handles_stale_saved_items(self) -> None:
        weather = function_body(self.update, "void weather_update", "static void bank_interest")
        char_update = function_body(self.update, "void char_update", "void obj_update")
        lycanthropy = function_body(self.update, "void do_lycanthropy", "void sanity_check")

        descriptor_loop = weather.index("for ( d = descriptor_list")
        self.assertLess(descriptor_loop, weather.index("if ( buf[0] != '\\0'", descriptor_loop))
        self.assertLess(descriptor_loop, weather.index("do_lycanthropy(d->character", descriptor_loop))
        self.assertIn("!IS_SET(ch->act2, ACT2_LYCANTH)", char_update)
        self.assertIn("UMIN(ch->were_shape.can_carry, 4)", lycanthropy)
        self.assertIn("if (pObjIndex == NULL)", lycanthropy)
        self.assertLess(
            lycanthropy.index("if (pObjIndex == NULL)"),
            lycanthropy.index("create_object(pObjIndex, 0)"),
        )

    def test_were_form_admin_input_rejects_negative_indexes(self) -> None:
        mset = function_body(self.act_wiz, "void do_mset", "void do_string")
        self.assertIn("if(value < 0 || value > 6)", mset)


if __name__ == "__main__":
    unittest.main()
