"""The training yard: a fight nobody can lose, and a number at the end.

The yard exists so that "is this sword better than that one" has an
answer other than an impression formed over an evening. Everything
guarded here is a way that answer could quietly stop being true: a
dummy that can be killed, a player who can be, a reading taken
against something that changed half way through, or a benchmark that
was invented rather than measured.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class TrainingDummyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dummy = read("src", "dummy.c")
        cls.fight = read("src", "fight.c")
        cls.area = read("area", "dummy.are")
        cls.merc = read("src", "merc.h")

    # ------------------------------------------------------------ the place
    def test_the_area_is_loaded_after_dresden(self) -> None:
        """The practice ring resets into Dresden's square, so the
        square has to exist by the time this file is read."""
        listed = read("area", "area.lst")
        self.assertIn("dummy.are", listed)
        self.assertLess(listed.index("dresden.are"), listed.index("dummy.are"))

    def test_the_yard_allows_a_fight(self) -> None:
        """ROOM_ARENA is what makes it possible.

        is_safe() returns false for an arena before it tests anything
        else, so blows land there that would be refused in a room
        that was merely safe.
        """
        self.assertRegex(self.area, r"\n0 V 1\r?\n", "the yard is not an arena")
        is_safe = self.fight.split("bool is_safe(", 1)[1][:900]
        self.assertIn("ROOM_ARENA", is_safe)

    def test_the_dummy_and_the_way_in_both_reset(self) -> None:
        self.assertRegex(self.area, r"M 0 2400 1 2419")
        self.assertRegex(self.area, r"O 0 2404 0 2409")

    def test_the_way_in_costs_nothing(self) -> None:
        """A portal's value[0] of 1 charges 50 gold, which is not what
        a training yard is for."""
        self.assertRegex(self.area, r"\n30 0 0\r?\n0 2419 0 0 0")

    # ----------------------------------------------------------- nobody dies
    def test_the_absorb_sits_on_the_damage_subtraction(self) -> None:
        """The same chokepoint invulnerability uses.

        Everything above that line, dam_message included, still runs,
        so a practice blow reads exactly like a real one -- which is
        the point, since the reading has to be of the real thing.
        """
        self.assertIn("dummy_absorb( ch, victim, dam )", self.fight)
        # The subtraction sits on its own line under the if, so the
        # guard is the statement just above it, not the same line.
        before = self.fight.split("victim->hit -= dam;")[0]
        tail = "".join(before.splitlines()[-3:])
        self.assertIn("dummy_absorb", tail,
                      "the guard is no longer on the subtraction")

    def test_the_dummy_absorbs_and_the_player_is_only_floored(self) -> None:
        body = self.dummy.split("bool dummy_absorb(", 1)[1].split("\n}", 1)[0]
        # Floored rather than made invulnerable: a brutal dummy that
        # holds you at 1 has told you something.
        self.assertIn("victim->hit = 1", body)
        self.assertIn("is_training_dummy( victim )", body)
        self.assertIn("is_training_dummy( ch )", body)

    # --------------------------------------------------- the numbers are real
    def test_the_benchmark_is_measured_not_invented(self) -> None:
        """"You would kill one in nine seconds" is only worth reading
        if the thing being killed is a real measure of the world."""
        body = self.dummy.split("long dummy_typical_hp(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("mob_index_hash", body)
        self.assertIn("proto->level != level", body)
        self.assertIn("cached[level]", body, "the walk must be cached")

    def test_a_run_cannot_be_reconfigured_half_way(self) -> None:
        """A reading blended from two opponents is worse than none."""
        self.assertIn("dummy_started != 0", self.dummy)
        self.assertIn("DUMMY REPORT first", self.dummy)

    def test_the_report_gives_both_directions_and_heals_both(self) -> None:
        body = self.dummy.split("static void dummy_report(", 1)[1]
        self.assertIn("You dealt", body)
        self.assertIn("It dealt", body)
        self.assertIn("per second", body)
        self.assertIn("dummy->hit = dummy->max_hit", body)
        self.assertIn("ch->hit = ch->max_hit", body)
        self.assertIn("dummy_session_clear", body)

    def test_it_defaults_to_your_own_level(self) -> None:
        """Almost everybody is asking how they do against something
        their own size; anything else is a different question."""
        self.assertIn("dummy->level != ch->level", self.dummy)
        self.assertIn("dummy_configure( dummy, ch->level", self.dummy)

    def test_the_damage_type_can_be_changed(self) -> None:
        """Testing resistances is half of what gear testing is."""
        self.assertIn("dummy_attack_table", self.dummy)
        for school in ("fire", "cold", "lightning", "acid", "holy"):
            self.assertIn('"%s"' % school, self.dummy, school)
        self.assertIn("dummy->dam_type", self.dummy)

    def test_the_session_is_not_persisted(self) -> None:
        """A training run is something you are doing, not something
        you are: none of it belongs in a player file."""
        save = read("src", "save.c")
        for field in ("dummy_dealt", "dummy_taken", "dummy_started",
                      "dummy_level"):
            self.assertIn(field, self.merc, field)
            self.assertNotIn(field, save, field + " reached save.c")


if __name__ == "__main__":
    unittest.main()
