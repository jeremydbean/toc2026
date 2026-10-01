"""Two bugs a player found by playing, and what they have in common.

Both are cases where a code path that handles the ordinary case grew
a feature and the path handling the unusual case did not.

[ 2401] AFFECT did not list mindbar.  Mindbar is a real affect with a
        real duration and nothing else -- no location, no modifier,
        no bits -- because all it is is a named timer that other code
        looks for by name.  do_affect skipped exactly that shape as a
        "pure sentinel", so the one psionic whose whole job is to be
        checked for was the one the player could not see.

[16001] Exotic weapons showed no damage number.  A weapon's attack
        noun is attack_table[value[3]], and fifteen weapons in the
        world carry value[3] == 0, the generic "hit".  dt is then
        TYPE_HIT exactly, and the TYPE_HIT branch of dam_message is
        the one branch that never got the bracketed number.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


def without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


class AffectListingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        src = read("src", "act_info.c")
        start = src.index("void do_affect(")
        cls.body = without_comments(src[start:src.index("\n}", start)])

    def test_a_marker_affect_is_still_listed(self) -> None:
        """An affect with no location, no modifier and no bits is not
        a sentinel -- it is how every psionic ward is built."""
        self.assertNotIn("paf->bitvector == 0 && paf->bitvector2 == 0",
                         self.body,
                         "marker affects are being skipped again")
        self.assertIn("skill_table[paf->type].name == NULL", self.body,
                      "the skip should now be about having a name")

    def test_only_nameless_entries_are_skipped(self) -> None:
        """Something has to be skipped, or a corrupt type indexes the
        skill table out of bounds."""
        self.assertIn("paf->type < 0 || paf->type >= MAX_SKILL", self.body)

    def test_a_psionic_is_not_called_a_spell(self) -> None:
        """The player who went looking for one knows the difference,
        and the shadowmeld line in the same function already says
        Skill."""
        self.assertIn("spell_fun == spell_null", self.body)
        self.assertIn('"Skill" : "Spell"', self.body)

    def test_mindbar_is_the_shape_this_is_about(self) -> None:
        """If mindbar ever grows a modifier this test is pointless,
        so pin the thing the bug was actually about."""
        magic2 = read("src", "magic2.c")
        body = magic2.split("void do_mindbar(", 1)[1].split("\n}", 1)[0]
        self.assertIn("af.type      = gsn_mindbar", body)
        self.assertIn("af.location  = APPLY_NONE", body)
        self.assertIn("af.modifier  = 0", body)
        self.assertIn("af.bitvector = 0", body)


class DamageNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        src = read("src", "fight.c")
        start = src.index("void dam_message(")
        cls.body = src[start:src.index("\n    dam = old_dam;", start)]
        cls.plain = cls.body.split("if ( dt == TYPE_HIT )", 1)[1]
        cls.plain = cls.plain.split("\t\t\t\t    else", 1)[0]

    def test_the_plain_hit_branch_shows_damage_numbers(self) -> None:
        """This is the branch a weapon with attack type 0 lands in,
        and bare hands with it."""
        self.assertIn("PLR_DAMAGE_NUMBERS", self.plain,
                      "the TYPE_HIT branch still has no damage numbers")
        self.assertGreaterEqual(self.plain.count("-%d"), 3,
                                "all three viewpoints need the number")

    def test_bystanders_never_see_a_number(self) -> None:
        """buf1 is the room's copy, and the other branch has always
        kept raw numbers out of it."""
        for line in self.plain.splitlines():
            if "buf1" in line and "snprintf" in line:
                self.assertNotIn("-%d", line, line.strip())

    def test_each_side_sees_its_own_setting(self) -> None:
        """Your preference governs what you see, not your opponent's."""
        self.assertIn("IS_SET(ch->act, PLR_DAMAGE_NUMBERS)", self.plain)
        self.assertIn("IS_SET(victim->act, PLR_DAMAGE_NUMBERS)", self.plain)
        self.assertIn("!IS_NPC(victim)", self.plain,
                      "reading act on a mobile reads ACT_ flags instead")
        self.assertIn("!IS_NPC(ch)", self.plain)

    def test_the_world_really_does_use_attack_type_zero(self) -> None:
        """If nothing used it the bug would not exist; fifteen
        weapons do, which is why a player hit it."""
        found = 0
        for area in sorted((ROOT / "area").glob("*.are")):
            lines = area.read_text(encoding="latin-1",
                                   errors="replace").splitlines()
            for i, line in enumerate(lines):
                parts = line.split()
                if len(parts) == 3 and parts[0] == "5" and i + 1 < len(lines):
                    values = lines[i + 1].split()
                    if (len(values) >= 4 and values[0].isdigit()
                            and values[3] == "0"):
                        found += 1
        self.assertGreater(found, 0,
                           "no weapon uses attack type 0 any more")


if __name__ == "__main__":
    unittest.main()
