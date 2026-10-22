"""Gear wears down and breaks, but is never over-flagged or destroyed.

Alaric reported a pirate ring and Excalibur reading "(Damaged)" while being
perfectly wearable and usable.  The cause: damage_eq flagged ITEM_DAMAGED on
any dent -- a single point off 100 -- so the binary "broken" flag (which
paints "(Damaged)" and blocks wear/use) fired for cosmetic wear the graded
condition display already covers.

Two rules, both the owner's:
  1. A dent only lowers condition.  ITEM_DAMAGED is set ONLY when a piece
     actually breaks (condition below zero in the shatter branch), where it
     is also unequipped into the pack -- "so broken you can't wear it until
     you repair".
  2. Repairs never destroy a piece and always restore it to new.  The old
     "breaks it on the 25th repair" path, which extracted the object, is gone.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*p):
    return ROOT.joinpath(*p).read_text(encoding="latin-1")


def body(src, signature):
    start = src.index(signature)
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    return src[start:]


class GearDamageTests(unittest.TestCase):
    def test_a_dent_never_flags_damaged(self):
        de = body(read("src", "fight.c"), "void damage_eq(")
        # The flag is set exactly once in damage_eq: the shatter branch.
        self.assertEqual(
            de.count("SET_BIT(obj->extra_flags, ITEM_DAMAGED)"), 1,
            "damage_eq should flag ITEM_DAMAGED only when a piece breaks")
        # And that one set lives with the shatter, not the dent message.
        shatter = de.index("shatters your")
        dent = de.index("The blow damages your")
        flag = de.index("SET_BIT(obj->extra_flags, ITEM_DAMAGED)")
        self.assertLess(shatter, flag)
        self.assertLess(flag, dent)

    def test_repair_never_destroys_and_always_restores(self):
        dr = body(read("src", "act_obj.c"), "void do_repair(")
        self.assertNotIn("extract_obj", dr,
                         "repair must never destroy the item")
        self.assertNotIn("number_repair >= 25", dr,
                         "the breaks-on-25th-repair path must be gone")
        # REPAIR and REPAIR ALL both mend through repair_mend().
        self.assertIn("repair_mend( ch, rpr, obj, cost );", dr)
        mend = body(read("src", "act_obj.c"), "static void repair_mend(")
        self.assertNotIn("extract_obj", mend)
        self.assertIn("obj->condition = 100", mend)
        self.assertIn("REMOVE_BIT(obj->extra_flags, ITEM_DAMAGED)", mend)
        # Worth is never raised by repair: that undid the purchase cap.
        self.assertNotIn("obj->cost =", mend)

    def test_damage_is_wear_not_worth(self):
        """Audit 2026-10-21: a dent cut a shield's worth to a third and
        left condition at 100, so REPAIR called it perfect. Damage now
        lowers condition and never touches obj->cost; a shop pays a
        third for a broken piece instead."""
        # The dent's wear and its ledger live in one helper since
        # 2026-10-22 (gear_file_armor, handler.c), which every armour-filing
        # damage calls.
        helper = body(read("src", "handler.c"), "void gear_file_armor(")
        self.assertIn("obj->condition - REPAIR_DENT_WEAR", helper)
        self.assertIn("armor_lost", helper)
        self.assertNotIn("->cost", helper)
        block = body(read("src", "fight.c"), "bool check_shield_block(")
        self.assertIn("gear_file_armor( victim, obj );", block)
        self.assertNotIn("obj->cost", block)
        magic = read("src", "magic.c")
        for spell in ("void spell_heat_metal(", "void spell_acid_breath("):
            self.assertNotIn("->cost", body(magic, spell), spell)
            self.assertIn("gear_file_armor( victim, obj_lose );", body(magic, spell), spell)
            self.assertNotIn("->value[i] -= 1", body(magic, spell), spell)
        cost = body(read("src", "act_obj.c"), "long get_cost(")
        self.assertIn("IS_OBJ_STAT(obj, ITEM_DAMAGED)", cost)


if __name__ == "__main__":
    unittest.main()
