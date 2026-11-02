"""CAST never takes a target for a slip in the spell's name.

The command-guessing pass (2026-10-30) mends a typo in the rest of a
spell's name: CAST CURE LGIHT is cure light. It mended too much: a mage
holding chill touch typed CAST 'CHILL' TORCH with Torch in the room and
was answered "Cast the spell on whom?" -- "torch" was read as a slip of
"touch" and eaten -- and in a fight the spell went to whoever they were
fighting instead (review, 2026-10-30). A quoted spell name is exactly
the spell's name, and a word that names something the spell can be cast
at is the target. Each test asserts who the spell actually struck: an offensive spell's victim
turns on the caster (do_cast's multi_hit), so STAT's "Fighting:" line
names whom it hit -- hit points are no measure, since a tick's healing
can outrun a chill touch that saved for half.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (LiveMud, SPARRING_GUARD, create_character, login, patch_player_file,
                      room_of, skip_reason)

SKIP = skip_reason()
PW = "Zctpass1"
FLOOR = 32700           # the fixture world's sparring floor


def make(mud: LiveMud, name: str, skills: dict, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    end = text.index("\nEnd\n")
    lines = "".join(f"\nSk {pct} '{skill}'" for skill, pct in skills.items())
    path.write_text(text[:end] + lines + text[end:], encoding="latin-1")


def fighting(staff, who: str) -> str:
    reply = staff.must(f"stat mob {who}", "Fighting:")
    return re.search(r"Fighting: (\S+)", reply).group(1).lower()


@unittest.skipIf(SKIP is not None, SKIP or "")
class CastTargetTests(unittest.TestCase):
    def arena(self, mud: LiveMud):
        make(mud, "Zctstaff", {}, Levl=70, Room=FLOOR)
        make(mud, "Zctmage", {"chill touch": 100, "cure light": 100}, Levl=30, Cla=0,
             Room=FLOOR, HMV="3000 3000 3000 3000 300 300")
        staff = mud.connect(timeout=120)
        mage = mud.connect(timeout=120)
        login(staff, "Zctstaff", PW)
        login(mage, "Zctmage", PW)
        staff.sync("scroll 0")
        mage.sync("scroll 0")
        self.assertEqual(room_of(staff, "zctstaff"), FLOOR)
        self.assertEqual(room_of(staff, "zctmage"), FLOOR)
        # Two sparring guards; the second is Torch.
        staff.must(f"load mob {SPARRING_GUARD}", "You create")
        staff.must(f"load mob {SPARRING_GUARD}", "You create")
        staff.must("string char 2.sparring name torch", "now set as: torch")
        staff.must("string char torch short Torch", "Short Desc now: Torch")
        self.assertIn("Torch", staff.must("stat mob torch", "Name:"))
        return staff, mage

    def test_a_quoted_name_and_a_real_target_are_kept(self) -> None:
        with LiveMud(fixtures=True) as mud:
            staff, mage = self.arena(mud)
            for line in ("cast 'chill' torch", "cast 'chill touch' torch", "cast chill torch"):
                staff.sync("restore zctmage")
                self.assertEqual(fighting(staff, "torch"), "(none)")
                reply = mage.sync(line)
                self.assertNotIn("Cast the spell on whom", reply, line)
                self.assertEqual(fighting(staff, "torch"), "zctmage",
                                 f"{line}: Torch was not struck: {reply!r}")
                self.assertEqual(fighting(staff, "sparring"), "(none)",
                                 f"{line}: the other guard was struck")
                staff.sync("peace")

    def test_while_fighting_another_the_named_target_is_struck(self) -> None:
        with LiveMud(fixtures=True) as mud:
            staff, mage = self.arena(mud)
            for line in ("cast 'chill' torch", "cast chill torch"):
                staff.sync("restore zctmage")
                mage.must("kill sparring", "")
                self.assertIn("Fighting: sparring", staff.must("stat char zctmage", "Fighting:"))
                self.assertEqual(fighting(staff, "torch"), "(none)")
                reply = mage.sync(line)
                self.assertNotIn("Cast the spell on whom", reply, line)
                self.assertEqual(fighting(staff, "torch"), "zctmage",
                                 f"{line}: the spell went to the fight, not to Torch: {reply!r}")
                staff.sync("peace")

    def cleric_arena(self, mud: LiveMud):
        make(mud, "Zctstaff", {}, Levl=70, Room=FLOOR)
        make(mud, "Zctcleric", {"cause critical": 100, "cause light": 100,
                                "cause serious": 100}, Levl=50, Cla=1,
             Room=FLOOR, HMV="3000 3000 3000 3000 300 300")
        staff = mud.connect(timeout=120)
        cleric = mud.connect(timeout=120)
        login(staff, "Zctstaff", PW)
        login(cleric, "Zctcleric", PW)
        staff.sync("scroll 0")
        cleric.sync("scroll 0")
        staff.must(f"load mob {SPARRING_GUARD}", "You create")
        staff.must(f"load mob {SPARRING_GUARD}", "You create")
        staff.must("string char 2.sparring name lightfoot", "now set as: lightfoot")
        staff.must("string char lightfoot short Lightfoot", "Short Desc now: Lightfoot")
        return staff, cleric

    def test_an_expansion_to_another_spell_does_not_eat_the_target(self) -> None:
        # CAUSE alone is one spell and CAUSE LI another (review, 2026-11-02):
        # LI begins Lightfoot, so it is the target, quoted or not.
        with LiveMud(fixtures=True) as mud:
            staff, cleric = self.cleric_arena(mud)
            for line in ("cast cause li", "cast 'cause' li"):
                staff.sync("restore zctcleric")
                reply = cleric.sync(line)
                self.assertNotIn("Cast the spell on whom", reply, line)
                self.assertEqual(fighting(staff, "lightfoot"), "zctcleric",
                                 f"{line}: Lightfoot was not struck: {reply!r}")
                self.assertEqual(fighting(staff, "sparring"), "(none)", line)
                staff.sync("peace")

            # In a fight with the other guard, LI is still Lightfoot.
            staff.sync("restore zctcleric")
            cleric.must("kill sparring", "")
            reply = cleric.sync("cast cause li")
            self.assertEqual(fighting(staff, "lightfoot"), "zctcleric",
                             f"in a fight, the spell went elsewhere: {reply!r}")
            staff.sync("peace")

            # A whole word of the name still extends it: CAUSE LIGHT is
            # cause light, here at Lightfoot by name.
            staff.sync("restore zctcleric")
            reply = cleric.sync("cast cause light lightfoot")
            self.assertNotIn("Cast the spell on whom", reply)
            self.assertEqual(fighting(staff, "lightfoot"), "zctcleric", repr(reply))

    def test_unquoted_mending_still_works(self) -> None:
        with LiveMud(fixtures=True) as mud:
            staff, mage = self.arena(mud)
            for line in ("cast cu li", "cast cure lgiht"):
                reply = mage.sync(line)
                self.assertTrue("You feel better" in reply or "lost your concentration" in reply,
                                f"{line}: {reply!r}")


if __name__ == "__main__":
    unittest.main()
