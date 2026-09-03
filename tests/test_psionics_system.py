from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def strip_comments(source: str) -> str:
    """Drop C comments so assertions test code, not the prose describing it."""
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


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

    def test_telekinesis_is_not_capped_at_half_skill(self) -> None:
        """TK used chance/2, capping it at 50% success even at 100% skill.

        No other psionic power halves its own learned percentage, so mastery
        could never make this one reliable.
        """
        telekinesis = strip_comments(
            function_body(self.magic2, "void do_telekinesis", "void do_confuse")
        )

        self.assertNotIn("chance / 2", telekinesis)
        self.assertNotIn("chance/2", telekinesis)
        self.assertIn("number_percent() > chance && !IS_IMMORTAL(ch)", telekinesis)

    def test_telekinesis_charges_full_cost_only_when_it_retrieves(self) -> None:
        telekinesis = strip_comments(
            function_body(self.magic2, "void do_telekinesis", "void do_confuse")
        )

        # Still gated on being able to afford the power.
        self.assertIn("if ( ch->mana < 50 )", telekinesis)

        # The full cost must be paid inside the success branch, after the
        # search, not unconditionally before it.
        self.assertLess(
            telekinesis.index("found = true"),
            telekinesis.index("ch->mana -= 50"),
            "full TK cost is charged before the object is found",
        )

        # A fruitless search costs effort, not the whole casting cost. Slice
        # only the !found arm, stopping at the else that handles success.
        start = telekinesis.index("if ( !found )")
        not_found = telekinesis[start:telekinesis.index("else", start)]
        self.assertIn("ch->mana -= (dice(1,5) + 3)", not_found)
        self.assertNotIn("ch->mana -= 50", not_found)

    def test_telekinesis_reports_an_uncarryable_match_distinctly(self) -> None:
        telekinesis = function_body(self.magic2, "void do_telekinesis", "void do_confuse")

        self.assertIn("too_heavy = true", telekinesis)
        self.assertIn("you cannot carry it", telekinesis)

        # Carry limits are checked after the name match, so a too-heavy hit is
        # distinguishable from no hit at all.
        self.assertLess(
            telekinesis.index("is_full_name( arg, obj->name )"),
            telekinesis.index("too_heavy = true"),
        )

    def test_astral_walk_gates_npcs_on_wards_not_the_generic_save(self) -> None:
        astral = strip_comments(
            function_body(self.magic2, "void do_astral_walk", "void do_telekinesis")
        )

        self.assertNotIn("saves_spell", astral)
        self.assertIn("psionic_ward_check( ch, victim )", astral)
        self.assertIn("psi_ward == PSI_WARD_BLOCKED", astral)
        self.assertIn("psi_ward == PSI_WARD_REDUCED", astral)
        # Players are still never blocked by a ward roll here; only NPCs.
        self.assertIn("if ( IS_NPC(victim) )", astral)

    def test_travel_powers_keep_their_deliberate_arrival_stun(self) -> None:
        """The arrival stun is anti-player-killing balance, not an oversight.

        Astral Walk and Shift must not hand the caster a free opening turn,
        or they become a way to jump a player and act first. char_update()
        clears the stun on the next tick. This test exists so the stun is not
        quietly softened again.
        """
        for name, end in (
            ("do_astral_walk", "void do_telekinesis"),
            ("do_shift", "void spell_major_globe"),
        ):
            body = function_body(self.magic2, f"void {name}", end)
            with self.subTest(power=name):
                self.assertIn("ch->position = POS_STUNNED", body)
                self.assertNotIn("ch->position = POS_RESTING", body)
                self.assertIn("!IS_IMMORTAL(ch)", body)
                # The player should be told why they cannot act.
                self.assertIn("stunned", body)

    def test_confuse_uses_its_real_cost(self) -> None:
        confuse = function_body(self.magic2, "void do_confuse", "void do_clairvoyance")

        self.assertIn("mana_cost = ch->level + 50", confuse)
        self.assertIn("if ( ch->mana < mana_cost )", confuse)
        self.assertNotIn("ch->mana < 139", confuse)
        self.assertLess(confuse.index("is_affected(victim, gsn_confuse)"), confuse.index("ch->mana -= mana_cost"))
        self.assertIn("psionic_start_combat", confuse)

    def test_confuse_only_fails_on_psionic_wards_not_a_generic_save(self) -> None:
        """A mastered Confuse must land unless the mind is specifically warded.

        The generic saves_spell() curve clamps to a 95% resist rate against the
        negative saving throws most mobiles carry, so its presence here made a
        100%-skill power fail almost every attempt.
        """
        confuse = function_body(self.magic2, "void do_confuse", "void do_clairvoyance")

        # The blanket saving throw must not come back.
        self.assertNotIn("saves_spell", confuse)

        # Target-side gating is mental immunity / resistance only.
        self.assertIn("psi_ward == PSI_WARD_BLOCKED", confuse)
        self.assertIn("psi_ward == PSI_WARD_REDUCED", confuse)

        # Caster-side gating is still just the skill roll, so 100% never fails.
        self.assertIn("number_percent() > chance", confuse)

        # A resistant target gets one bounded roll, never a near-certain block.
        self.assertIn("psionic_ward_check( ch, victim )", confuse)

        # Both ward outcomes still start combat and record a failed attempt.
        immune_branch = confuse[confuse.index("psi_ward == PSI_WARD_BLOCKED"):]
        self.assertIn("psionic_start_combat", immune_branch)
        self.assertIn("check_improve( ch, gsn_confuse, false, 4 )", immune_branch)

    def test_confuse_resist_band_stays_well_under_the_generic_save(self) -> None:
        base, low, high = (
            int(
                re.search(rf"#define {name}\s+(\d+)", self.magic2).group(1)
            )
            for name in (
                "PSI_RESIST_BASE",
                "PSI_RESIST_MIN",
                "PSI_RESIST_MAX",
            )
        )

        self.assertLess(low, base)
        self.assertLess(base, high)
        # saves_spell() clamps at 95; a resistant mind must stay far below that.
        self.assertLessEqual(high, 50)

    def test_confuse_help_matches_the_implemented_ward_rules(self) -> None:
        entry = function_body(self.command_help, "0 CONFUSE~", "0 CRANE~")

        self.assertIn("immune to mental damage can never be", entry)
        self.assertIn("mentally resistant", entry)
        # The old text blamed Intelligence, which never affected the power.
        self.assertNotIn("Intelligence", entry)

    def test_clairvoyance_does_not_physically_move_or_count_exploration(self) -> None:
        clairvoyance = function_body(
            self.magic2, "void do_clairvoyance", "void do_pyrotechnics"
        )

        self.assertNotIn("char_from_room", clairvoyance)
        self.assertNotIn("char_to_room", clairvoyance)
        self.assertIn("ch->in_room = victim->in_room", clairvoyance)
        self.assertIn("ch->in_room = was_in_room", clairvoyance)

    def test_drains_respect_wards_defenses_and_actual_damage(self) -> None:
        mindleech = function_body(self.magic2, "void do_mindleech", "void do_enervate")
        enervate = function_body(self.magic2, "void do_enervate", "void do_mindblast")

        self.assertIn("psionic_reduce_mental_drain", mindleech)
        self.assertIn("psionic_start_combat", mindleech)
        self.assertIn("psionic_reduce_mental_drain", enervate)
        self.assertIn("victim_hit_before - victim->hit", enervate)
        self.assertIn("actual_damage / 2", enervate)

    def test_drains_gate_on_mental_wards_not_the_generic_save(self) -> None:
        """The drains must not use the saves_spell() curve either.

        The psionics pass added it to both, which silently halved a mastered
        drain against most mobiles because that curve is driven by the
        target's (usually negative) saving throw rather than by any psionic
        defense. Mental immunity now blocks the drain outright and mental
        resistance halves it; psionic_reduce_mental_drain() still applies
        Mindbar/Armor/Shield on top.
        """
        for name, end in (
            ("do_mindleech", "void do_enervate"),
            ("do_enervate", "void do_mindblast"),
        ):
            body = function_body(self.magic2, f"void {name}", end)
            with self.subTest(power=name):
                self.assertNotIn("saves_spell", body)
                self.assertIn("psionic_ward_check( ch, victim )", body)
                self.assertIn("psi_ward == PSI_WARD_BLOCKED", body)
                self.assertIn("resisted = (psi_ward == PSI_WARD_REDUCED)", body)
                # A blocked drain must not fall through and still drain.
                blocked = body[body.index("psi_ward == PSI_WARD_BLOCKED"):]
                self.assertIn("return;", blocked)

    def test_psionic_ward_helper_is_shared_and_bounded(self) -> None:
        helper = function_body(
            self.magic2, "static int psionic_ward_check", "static int lore_estimate"
        )

        self.assertIn("check_immune( victim, DAM_MENTAL )", helper)
        self.assertIn("case IS_IMMUNE:", helper)
        self.assertIn("case IS_RESISTANT:", helper)
        self.assertIn("PSI_WARD_BLOCKED", helper)
        self.assertIn("URANGE( PSI_RESIST_MIN", helper)
        # A normal or vulnerable mind must fall through to no ward at all.
        self.assertIn("default:", helper)
        self.assertIn("return PSI_WARD_NONE;", helper)
        # Null-safety, since psionic mob AI can invoke these powers.
        self.assertIn("ch == NULL || victim == NULL", helper)

        # Every power that consults a ward must use the shared helper.
        for power in ("do_confuse", "do_mindleech", "do_enervate"):
            with self.subTest(power=power):
                self.assertIn(power, self.magic2)

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
