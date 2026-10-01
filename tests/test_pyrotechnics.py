"""Pyrotechnics is priced against a fireball, and must stay there.

It used to roll hp/14 .. hp/7 off the caster's current hit points.
At 2,500 hp that averaged near 268 a cast, every round, for 20 mana,
when its level-scaled peers ego whip and torment sit near 87 at level
50 and fireball -- the mage nuke at the same level and the same wait
-- near 162.  Worse, it grew without bound with every remort.

It now rolls fireball's own damage through one shared helper, so the
two cannot drift if fireball is ever retuned, and a failed attempt
pays its wait the way a failed cast does.
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


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    return without_comments(source[start:source.index("\n}", start)])


class PyrotechnicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic = read("src", "magic.c")
        cls.magic2 = read("src", "magic2.c")
        cls.pyro = function_body(cls.magic2, "void do_pyrotechnics")

    def test_it_rolls_fireballs_damage(self) -> None:
        self.assertIn("fireball_damage_roll( ch->level )", self.pyro)

    def test_it_no_longer_scales_with_hit_points(self) -> None:
        """The whole of the old problem: a damage roll that tracked
        the caster's hit points grew with every remort."""
        self.assertNotIn("ch->hit", self.pyro)
        self.assertNotIn("hpch", self.pyro)

    def test_fireball_and_pyrotechnics_share_one_table(self) -> None:
        """Two copies of the table is one that gets retuned and one
        that does not."""
        fireball = function_body(self.magic, "void spell_fireball(")
        self.assertIn("fireball_damage_roll( level )", fireball)
        self.assertNotIn("dam_each", fireball)
        helper = function_body(self.magic, "int fireball_damage_roll(")
        self.assertIn("dam_each", helper)

    def test_fireball_itself_is_unchanged(self) -> None:
        """Moving the table out must not move fireball. Its save is
        still rolled against the clamped level, as it always was."""
        fireball = function_body(self.magic, "void spell_fireball(")
        self.assertIn("URANGE( 0, level, 50 )", fireball)
        self.assertLess(fireball.index("URANGE( 0, level, 50 )"),
                        fireball.index("saves_spell( level, victim )"))
        helper = function_body(self.magic, "int fireball_damage_roll(")
        self.assertIn("dam_each[level] / 2, dam_each[level] * 2", helper)

    def test_a_failed_attempt_pays_its_wait(self) -> None:
        """do_cast charges the wait before it rolls. This used to
        return free, so a miss could be retried at once."""
        failure = self.pyro.split("You lost your concentration.", 1)[1]
        failure = failure.split("return;", 1)[0]
        self.assertIn("WAIT_STATE(ch, skill_table[gsn_pyrotechnics].beats)",
                      failure)

    def test_its_wait_is_fireballs(self) -> None:
        const = read("src", "const.c")
        def beats(name: str) -> int:
            block = const.split('\t"%s",' % name, 1)[1][:400]
            return int(re.search(r"SLOT\(\s*\d+\s*\),\s*\d+,\s*(\d+)",
                                 block).group(1))
        self.assertEqual(beats("pyrotechnics"), beats("fireball"))

    def test_the_help_says_what_it_does_now(self) -> None:
        skills = read("area", "skills.are")
        topic = skills.split("PYROTECHNICS~", 1)[1].split("~", 1)[0]
        self.assertIn("fireball", topic)
        self.assertNotIn("vitality", topic)


if __name__ == "__main__":
    unittest.main()
