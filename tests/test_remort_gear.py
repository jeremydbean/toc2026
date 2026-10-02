"""Remort no longer loses or uselessly wears over-level gear.

Two halves:
  1. save.c dropped the "castrate storage characters" clause, which
     refused to save any item more than two levels above its owner -- and
     so deleted a remorter's whole kit (a level-3 body is far more than two
     under its own armour) and punished the stash.
  2. do_remort now re-equips only what a level-3 body can wear and folds
     the rest into a named pack in the stash, rather than leaving it worn
     or carried-but-useless.
"""
import re
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


class RemortGearTests(unittest.TestCase):
    def test_the_level_castrate_clause_is_gone(self):
        save = read("src", "save.c")
        fw = body(save, "void fwrite_obj(")
        self.assertNotIn("obj->level - 2", fw,
                         "the level-castrate clause is still saving-gating gear")
        # Keys and blank maps are still (correctly) not saved.
        self.assertIn("ITEM_KEY", fw)

    def test_remort_bags_unwearable_gear_into_the_stash(self):
        act = read("src", "act_info.c")
        self.assertIn("remort_gear_bag", act)
        dr = body(act, "void do_remort(")
        # Only wearable gear is re-equipped.
        self.assertIn("worn[iWear]->level > ch->level", dr)
        # The rest is moved into a bag and put in the stash.
        self.assertIn("obj_to_obj(obj, bag)", dr)
        self.assertIn("stash_receive(ch, bag)", dr)
        # The bag is named for the life left behind.
        self.assertIn("old_level", dr)

    def test_the_bag_never_ticks_down(self):
        # Stash items must have no timer or obj_update would purge them.
        bag = body(read("src", "act_info.c"), "remort_gear_bag(")
        self.assertIn("bag->timer = 0", bag)


if __name__ == "__main__":
    unittest.main()
