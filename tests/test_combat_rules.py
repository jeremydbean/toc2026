"""Combat arithmetic and the mechanical fixes of the 2026-10-26 class review.

tests/test_combat_rules.c checks src/combat_rules.c exhaustively against
the formulas it replaces:

* backstab and smite subtracted 10 * (100 - proficiency) from THAC0, so
  the less a character knew the skill the surer it hit, and mastering it
  took the bonus away; the bonus now grows with the skill to 10;
* crane dance fell off cliffs at 1,000 and 4,000 hit points; it is one
  continuous, never-decreasing curve, capped at 25 a level;
* the undead servants' budget keeps the pure armies.

The source checks below hold the call sites to them, and to the other
two mechanical fixes: damage() asked skill_lookup("psionic_armor") and
"psychic_shield", which name no skill, so only mindbar ever turned a
mental blow; and a passing destruction check without the quarter roll
lost the third attack outright.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]


def function_body(path: Path, signature: str) -> str:
    text = path.read_text(encoding="latin-1")
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"no end to {signature}")


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class CombatRulesHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_combat_rules"
            build = subprocess.run(
                [CC, "-std=gnu89", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_combat_rules.c"),
                 str(ROOT / "src" / "combat_rules.c")],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertGreaterEqual(run.stdout.count("\nok ") + run.stdout.startswith("ok "), 12)


class CombatRulesCallSiteTests(unittest.TestCase):
    fight = ROOT / "src" / "fight.c"
    magic2 = ROOT / "src" / "magic2.c"

    def test_backstab_and_smite_use_the_bounded_bonus(self) -> None:
        body = function_body(self.fight, "void one_hit(")
        self.assertNotRegex(body, r"10\s*\*\s*\(\s*100\s*-\s*get_skill")
        self.assertIn("strike_thac0_bonus( get_skill(ch,gsn_backstab) )", body)
        self.assertIn("strike_thac0_bonus( get_skill(ch,gsn_smite) )", body)

    def test_crane_dance_uses_the_curve(self) -> None:
        body = function_body(self.fight, "void do_crane_dance(")
        self.assertIn("crane_dance_mean( vch->hit, ch->level )", body)
        self.assertNotIn("vch->hit * .", body)

    def test_mental_damage_asks_the_psionic_rule_by_gsn(self) -> None:
        body = function_body(self.fight, "bool damage(")
        self.assertNotIn('skill_lookup("psionic_armor")', body)
        self.assertNotIn('skill_lookup("psychic_shield")', body)
        self.assertIn("dam = psionic_mental_reduce( victim, dam );", body)
        rule = function_body(self.magic2, "int psionic_mental_reduce(")
        for gsn in ("gsn_psionic_armor", "gsn_psychic_shield", "gsn_mindbar"):
            self.assertIn(gsn, rule)
        # Every mana and movement drain still asks it, outside damage().
        text = self.magic2.read_text(encoding="latin-1")
        self.assertEqual(len(re.findall(r"= psionic_mental_reduce\(", text)), 2)

    def test_a_failed_destruction_keeps_the_third_attack(self) -> None:
        body = function_body(self.fight, "void multi_hit(")
        third = body[body.index("gsn_third_attack)/4"):]
        self.assertIn("destroyed = destroy( ch, victim );", third)
        self.assertRegex(third, r"if \( !destroyed \)\s*\{\s*one_hit\( ch, victim, dt \);")
        # The old shape: a blow only inside the quarter roll's failure.
        self.assertNotRegex(third, r"dice\(1,100\) < 25 \)\s*if\(!destroy")

    def test_servant_spells_ask_the_budget(self) -> None:
        for spell, cost in (("spell_create_skeleton", "UNDEAD_COST_SKELETON"),
                            ("spell_create_wraith", "UNDEAD_COST_WRAITH"),
                            ("spell_create_vampire", "UNDEAD_COST_VAMPIRE")):
            body = function_body(self.magic2, f"void {spell}(")
            self.assertIn(f"undead_budget_refuses( ch, {cost} )", body)
            self.assertNotIn("undead_servants(", body)

    def test_smite_wears_its_weapon_down_before_it_breaks(self) -> None:
        body = function_body(self.fight, "void do_smite(")
        self.assertIn("obj->condition -= (sh_int)number_range( SMITE_WEAR_MIN, SMITE_WEAR_MAX );", body)
        # The break is reached only by a weapon worn to nothing.
        self.assertRegex(body, r"obj->condition > 0 \)\s*\{[^}]*obj = NULL;")
        self.assertLess(body.index("SMITE_WEAR_MIN"), body.index("loud CRACK"))

    def test_servants_take_the_casters_lasting_maximum(self) -> None:
        body = function_body(self.magic2, "static CHAR_DATA *raise_undead(")
        self.assertIn("lasting_max_hit( ch ) * grade / 400", body)
        self.assertNotIn("ch->max_hit * grade", body)
        rule = function_body(self.magic2, "static int lasting_max_hit(")
        self.assertIn("paf->duration >= 0", rule)

    def test_heal_asks_the_bounded_amount(self) -> None:
        body = function_body(ROOT / "src" / "magic.c", "void spell_heal(")
        self.assertIn("heal = heal_spell_amount( level );", body)
        self.assertNotIn("heal = 100;", body)

    def test_warriors_and_thieves_take_weapon_mastery(self) -> None:
        body = function_body(self.fight, "void one_hit(")
        mastery = body.index("weapon_mastery_percent( ch->level")
        self.assertLess(mastery, body.index("dam += GET_DAMROLL(ch)"),
                        "mastery multiplies the weapon, not damroll")
        guard = body[body.rindex("if (", 0, mastery):mastery]
        for need in ("!IS_NPC(ch)", "wield != NULL", "dt != gsn_backstab",
                     "CLASS_WARRIOR", "CLASS_THIEF"):
            self.assertIn(need, guard)

    def test_the_casters_spells_scale(self) -> None:
        """Players' flamestrike and lightning bolt grow a die a level; a
        mobile's keep the old 8d8 and table (owner, 2026-10-27: the
        scale-up was for player classes -- the 99 spec_cast_cleric mobiles
        would otherwise have cast about five times their level)."""
        magic = ROOT / "src" / "magic.c"
        strike = function_body(magic, "void spell_flamestrike(")
        self.assertIn("flamestrike_dice( level, ch->class == CLASS_CLERIC )", strike)
        self.assertLess(strike.index("if ( IS_NPC(ch) )"), strike.index("flamestrike_dice("))
        self.assertIn("dam = dice( 8, 8 );", strike)
        bolt = function_body(magic, "void spell_lightning_bolt(")
        self.assertIn("lightning_bolt_dice( level, ch->class == CLASS_MAGE )", bolt)
        self.assertLess(bolt.index("if ( IS_NPC(ch) )"), bolt.index("lightning_bolt_dice("))
        self.assertLess(bolt.index("dam_each"), bolt.index("lightning_bolt_dice("))

if __name__ == "__main__":
    unittest.main()
