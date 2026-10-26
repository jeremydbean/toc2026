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
        self.assertGreaterEqual(run.stdout.count("\nok ") + run.stdout.startswith("ok "), 8)


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

    def test_servants_take_the_casters_lasting_maximum(self) -> None:
        body = function_body(self.magic2, "static CHAR_DATA *raise_undead(")
        self.assertIn("lasting_max_hit( ch ) * grade / 400", body)
        self.assertNotIn("ch->max_hit * grade", body)
        rule = function_body(self.magic2, "static int lasting_max_hit(")
        self.assertIn("paf->duration >= 0", rule)

    def test_smite_wears_its_weapon_down_before_it_breaks(self) -> None:
        body = function_body(self.fight, "void do_smite(")
        self.assertIn("obj->condition -= (sh_int)number_range( SMITE_WEAR_MIN, SMITE_WEAR_MAX );", body)
        # The break is reached only by a weapon worn to nothing.
        self.assertRegex(body, r"obj->condition > 0 \)\s*\{[^}]*obj = NULL;")
        self.assertLess(body.index("SMITE_WEAR_MIN"), body.index("loud CRACK"))


if __name__ == "__main__":
    unittest.main()
