"""The necromancer review (October 2026), and what it found live.

Each test names the exploit or bug it pins. They are read from the source
because each turns on one condition.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1").replace("\r\n", "\n")


def code(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start:source.index("\n}", start)]


class NecroReviewTests(unittest.TestCase):
    def test_major_globe_does_not_stack(self) -> None:
        """IS_AFFECTED(victim, sn) read skill 87 as affect bits: every
        recast added another -80-level AC, ten casts about -1390."""
        globe = code(body(read("src", "magic2.c"), "void spell_major_globe("))
        self.assertNotIn("IS_AFFECTED(victim, sn)", globe)
        self.assertIn("is_affected(victim, sn)", globe)
        self.assertIn('is_affected(victim, skill_lookup("shroud"))', globe)

    def test_the_servant_cap_holds_in_a_group(self) -> None:
        """is_same_group climbs one leader; a grouped necro counted none."""
        servants = code(body(read("src", "magic2.c"), "static int undead_servants("))
        self.assertNotIn("is_same_group", servants)
        self.assertIn("gch->master == ch", servants)

    def test_a_charmed_servant_is_no_kill(self) -> None:
        gain = code(body(read("src", "fight.c"), "void group_gain("))
        self.assertIn("IS_AFFECTED(victim, AFF_CHARM) && victim->master != NULL", gain)

    def test_recite_costs_lag(self) -> None:
        recite = code(body(read("src", "act_obj.c"), "void do_recite("))
        self.assertLess(recite.index("WAIT_STATE( ch, 2 * PULSE_VIOLENCE );"),
                        recite.index("You mispronounce a syllable."))

    def test_protected_mobiles_cannot_be_bottled_or_farslayed(self) -> None:
        magic2 = code(read("src", "magic2.c"))
        trap = body(magic2, "void spell_trap_the_soul_fixed(")
        self.assertIn("is_protected_npc(victim)", trap)
        self.assertIn("is_protected_npc( victim )", magic2)
        protected = code(body(read("src", "fight.c"), "bool is_protected_npc("))
        for check in ("pShop", "ACT_TRAIN", "ACT_PRACTICE", "ACT_IS_HEALER",
                      "ACT_QUESTM", "ACT_NOKILL", "is_training_dummy",
                      "is_hyrule_bystander", "is_divinely_warded"):
            self.assertIn(check, protected, check)

    def test_consumed_corpses_spill_their_loot(self) -> None:
        magic2 = code(read("src", "magic2.c"))
        self.assertEqual(magic2.count("spill_corpse( corpse );\n"), 2)
        for match in re.finditer(r"spill_corpse\( corpse \);\s*\n\s*extract_obj\( corpse \);", magic2):
            self.assertTrue(match)

    def test_a_buff_does_not_keep_a_servant_alive(self) -> None:
        update = code(read("src", "update.c"))
        self.assertIn("IS_NPC(ch) && IS_SET(paf->bitvector, AFF_CHARM)", update)
        self.assertNotIn("IS_NPC(ch) && IS_AFFECTED(ch, AFF_CHARM) )\n\t\t    {\n\t\t\tch->timer = 150;", update)

    def test_no_iron_skin_sweep_strips_innate_immunity(self) -> None:
        update = code(read("src", "update.c"))
        self.assertNotIn('if(!is_affected(ch, skill_lookup("iron skin") ) )', update)

    def test_pocket_rooms_are_no_way_out(self) -> None:
        magic2 = code(read("src", "magic2.c"))
        for name in ("void spell_rope_trick(", "void spell_haven("):
            spell = body(magic2, name)
            self.assertIn("ROOM_JAIL", spell, name)
            self.assertIn("ROOM_NO_RECALL", spell, name)

    def test_raise_dead_keeps_summon_rules(self) -> None:
        raise_dead = code(body(read("src", "magic2.c"), "void spell_raise_dead("))
        for check in ("victim->fighting != NULL", "ROOM_JAIL", "ROOM_NO_RECALL",
                      "room_is_private( ch->in_room )"):
            self.assertIn(check, raise_dead, check)

    def test_one_rule_for_class_and_race(self) -> None:
        """Creation allowed a saurian necro that remort then refused."""
        self.assertIn("class_race_refusal( iClass, ch->race )", read("src", "comm.c"))
        self.assertIn("class_race_refusal( requested_class, requested_race )",
                      read("src", "act_info.c"))

    def test_drain_heals_nothing_from_the_undead(self) -> None:
        self.assertIn("check_immune( victim, DAM_NEGATIVE )", read("src", "magic2.c"))
        self.assertIn("check_immune( victim, DAM_NEGATIVE )", read("src", "magic.c"))

    def test_the_undead_template_is_nokill_in_every_limbo(self) -> None:
        for name in ("limbo.are", "limbo_halloween.are", "limbo_xmas.are"):
            text = read("area", name)
            mobs = text.split("#MOBILES", 1)[1].split("#OBJECTS", 1)[0]
            record = mobs.split("\n#80\n", 1)[1].split("\n#", 1)[0]
            act = [l for l in record.split("\n") if re.fullmatch(r"[A-Z]+ [A-Z0-9]+ -?\d+ [A-Z]", l)][0]
            self.assertIn("X", act.split()[0], name)

    def test_the_help_answers_to_death_shroud(self) -> None:
        spells = read("area", "spells.are")
        self.assertIn("'DEATH SHROUD'", spells)
        self.assertIn("Syntax: cast create skeleton [corpse]", spells)


if __name__ == "__main__":
    unittest.main()
