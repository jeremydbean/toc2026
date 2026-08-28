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


class RareEventAndSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="utf-8")
        cls.fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        cls.season = (ROOT / "src" / "season.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.command_help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_life_draining_spells_cannot_overheal(self) -> None:
        energy_drain = function_body(
            self.magic, "void spell_energy_drain", "void spell_fireball"
        )
        vampiric_touch = function_body(
            self.magic2, "void spell_vampiric_touch", "void do_brew"
        )

        for spell in (energy_drain, vampiric_touch):
            with self.subTest(spell=spell[:40]):
                self.assertIn("UMIN( ch->max_hit, ch->hit + dam / 2 )", spell)
                self.assertNotIn("ch->hit\t\t+= dam/2", spell)

    def test_elemental_shields_are_mutually_exclusive(self) -> None:
        fire = function_body(
            self.magic2, "void spell_fire_shield", "void spell_frost_shield"
        )
        frost = function_body(
            self.magic2, "void spell_frost_shield", "void spell_death_shroud"
        )
        shroud = function_body(
            self.magic2, "void spell_death_shroud", "void spell_detect_traps"
        )

        for spell in (fire, frost, shroud):
            with self.subTest(spell=spell[:40]):
                self.assertIn("IS_AFFECTED2(victim, AFF2_FLAMING_HOT)", spell)
                self.assertIn("IS_AFFECTED2(victim, AFF2_FLAMING_COLD)", spell)
                self.assertNotIn("victim->act2", spell)

        self.assertIn("is_affected( victim, sn )", fire)
        self.assertRegex(
            fire,
            r"You can't cast this spell on \$N[\s\S]*?return;\s*}",
        )
        self.assertNotIn("IS_SET(mob->act2, AFF2_FLAMING", self.special)

    def test_crafting_recipes_are_order_independent(self) -> None:
        concoct = function_body(self.magic2, "void do_concoct", "void do_scribe")
        scribe = function_body(self.magic2, "void do_scribe", "void spell_vengence")

        self.assertEqual(concoct.count("crafting_pair_matches("), 10)
        self.assertEqual(scribe.count("crafting_trio_matches("), 5)
        self.assertNotIn("pObj_one->pIndexData->vnum ==", concoct)
        self.assertNotIn("pObj_one->pIndexData->vnum ==", scribe)

    def test_failed_crafting_has_no_orphan_output_or_component_trap(self) -> None:
        concoct = function_body(self.magic2, "void do_concoct", "void do_scribe")
        scribe = function_body(self.magic2, "void do_scribe", "void spell_vengence")

        self.assertIn("extract_obj( potion )", concoct)
        self.assertIn("extract_obj( scroll )", scribe)
        self.assertRegex(
            scribe,
            r"won't make a useable ink\.\\n\\r\",ch\);\s*return;",
        )
        self.assertGreaterEqual(concoct.count("save_char_obj(ch)"), 2)
        self.assertGreaterEqual(scribe.count("save_char_obj(ch)"), 2)

    def test_event_loot_is_autolootable_and_never_empty(self) -> None:
        corpse = function_body(self.fight, "void make_corpse", "void death_cry")

        self.assertIn("obj_to_obj( drop, corpse )", self.fight)
        self.assertIn("if ( !primary_drop )", corpse)
        self.assertIn("record_event_boss_defeat( ch )", corpse)
        self.assertNotIn("event_boss_mob = NULL", corpse)
        self.assertIn("void record_event_boss_defeat", self.season)
        self.assertIn("event_boss_spawn_time = 0", self.season)

    def test_stale_event_vendors_are_checked_before_despawn(self) -> None:
        tick = function_body(
            self.season, "void tick_seasonal_vendors", "\n}"
        )
        stale_check = tick.index("Clear stale pointers")
        timed_despawn = tick.index("Despawn if either live vendor")

        self.assertLess(stale_check, timed_despawn)
        self.assertIn("seasonal_character_exists(event_vendor_halloween)", tick)
        self.assertIn("seasonal_character_exists(event_vendor_winter)", tick)

    def test_hero_quest_progress_and_cleanup_are_persistent(self) -> None:
        quest_master = function_body(
            self.special, "bool spec_quest_master", "bool spec_kidnapper"
        )

        self.assertIn("hero_quest_table_count() - 1", quest_master)
        self.assertNotIn("dice(1,77)", quest_master)
        self.assertNotIn("holder_2 < 77", quest_master)
        self.assertIn("send_hero_quest_clue", quest_master)
        self.assertGreaterEqual(quest_master.count("REMOVE_BIT(ch->act, PLR_NOFOLLOW)"), 2)
        self.assertIn("UMAX(3, ch->perm_stat[lost] - 2)", quest_master)
        self.assertRegex(
            quest_master,
            r"UMAX\(1,\s*ch->pcdata->perm_hit - 20\)",
        )
        self.assertIn("URANGE(1, ch->hit - 20, ch->max_hit)", quest_master)
        self.assertRegex(
            quest_master,
            r"REMOVE_BIT\(ch->imm_flags, IMM_MAGIC\);\s*"
            r"REMOVE_BIT\(ch->act, PLR_NOFOLLOW\);\s*save_char_obj\(ch\);",
        )

    def test_rare_training_cakes_and_crafting_help_are_honest(self) -> None:
        for vnum in (29926, 29927):
            descriptions = " ".join(
                extra["description"]
                for extra in self.parser.objects[vnum].extra_descr
            ).lower()
            self.assertIn("training session", descriptions)

        self.assertIn("Syntax: brew <herb>", self.command_help)
        self.assertIn(
            "Syntax: scribe <component> <component> <component>",
            self.command_help,
        )
        self.assertIn("Component order does not matter", self.command_help)
        self.assertNotIn("You must have a blank scroll", self.command_help)

    def test_death_ray_does_not_falsely_kill_ganon(self) -> None:
        death_ray = function_body(
            self.magic2, "void spell_death_ray", "void spell_cause_madness"
        )

        ganon_guard = death_ray.index("victim->pIndexData->vnum == 30225")
        death_message = death_ray.index('act("$n screams and dies!"')
        self.assertLess(ganon_guard, death_message)
        self.assertIn("ancient darkness refuses to let $m die", death_ray)


if __name__ == "__main__":
    unittest.main()
