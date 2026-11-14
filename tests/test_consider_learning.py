"""CONSIDER learns each player's skills and spells (2026-11-14).

The fights held to CONSIDER showed weapons predicted well -- melee 1.13x
what it said, the foe's blows 1.01x -- and skills and spells, which it did
not count, adding about half again. Which a player uses is theirs to
choose, so each kill alone feeds the skill and spell damage the foe took
a round into an average (consider_learn_fight in act_info.c), saved as
SkillDamage <tenths> <fights> <level>, and CONSIDER adds it once three
fights are in, while the level is within five of where it was learned.
Synthetic characters only, in the fixture world.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

SKIP = skip_reason()
PW = "Zlearner1"
FLOOR = 32700
BIG = "9000 9000 500 500 500 500"
LEARNED = "That counts about"


def make(mud: LiveMud, name: str, extra: str = "", **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    if extra:
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        end = text.index("\nEnd\n")
        path.write_text(text[:end] + "\n" + extra + text[end:], encoding="latin-1")


def skill_damage(mud: LiveMud, name: str):
    found = re.search(r"^SkillDamage (\d+) (\d+) (\d+)$",
                      (mud.player_dir / name).read_text(encoding="latin-1"), re.M)
    return tuple(int(x) for x in found.groups()) if found else None


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConsiderLearningTests(unittest.TestCase):
    def test_a_kill_alone_is_learned_and_counted_once_three_are_in(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zref", Levl=70, Room=FLOOR)
            make(mud, "Zkicker", "Sk 100 'kick'", Levl=20, Cla=3, Room=FLOOR,
                 HMV=BIG, HMVP="9000 500 500")
            # Learned three fights ago at this level: counted.
            make(mud, "Zseasoned", "SkillDamage 500 3 20", Levl=20, Room=FLOOR,
                 HMV=BIG, HMVP="9000 500 500")
            # Two fights, or learned at level 40: not yet, or no longer.
            make(mud, "Zgreen", "SkillDamage 500 2 20", Levl=20, Room=FLOOR,
                 HMV=BIG, HMVP="9000 500 500")
            make(mud, "Zremort", "SkillDamage 500 9 40", Levl=20, Room=FLOOR,
                 HMV=BIG, HMVP="9000 500 500")

            with mud.connect(timeout=120) as ref, mud.connect(timeout=120) as kicker:
                login(ref, "Zref", PW)
                login(kicker, "Zkicker", PW)
                for client in (ref, kicker):
                    client.sync("scroll 0")
                place_sparring_guard(ref, "Zref", FLOOR)
                # A guard a level 20 finishes in a minute or so, over rounds.
                ref.must("set char sparring level 8", "")
                ref.must("set char sparring hp 250", "")
                ref.must("restore sparring", "")
                ref.must("set char zkicker hitroll 40", "")
                ref.must("set char zkicker damroll 25", "")
                self.assertNotIn(LEARNED, kicker.sync("consider sparring"))

                mark = len(kicker.transcript)
                kicker.send("kill sparring")
                for _ in range(60):
                    kicker.drain(1.5)
                    if "is DEAD" in kicker.transcript[mark:]:
                        break
                    kicker.send("kick")
                else:
                    self.fail("the guard never fell:\n" + kicker.transcript[-1200:])
                self.assertIn("Your kick", kicker.transcript[mark:])
                kicker.drain(1.0)
                kicker.must("save", "Saving")
                tenths, fights, level = skill_damage(mud, "Zkicker")
                self.assertGreater(tenths, 0, "the kicks were learned")
                self.assertEqual((fights, level), (1, 20))

                place_sparring_guard(ref, "Zref", FLOOR)     # a fresh one to consider
                for name, counted in (("Zseasoned", True), ("Zgreen", False),
                                      ("Zremort", False)):
                    with mud.connect(timeout=120) as looker:
                        login(looker, name, PW)
                        reply = looker.sync("consider sparring")
                        with self.subTest(name=name):
                            if counted:
                                self.assertIn(LEARNED + " 50 a round", reply)
                            else:
                                self.assertNotIn(LEARNED, reply)
                        looker.sync("save")
                        looker.send("quit")
                        looker.wait_closed()
                # Kept as it was read, through a save.
                self.assertEqual(skill_damage(mud, "Zseasoned"), (500, 3, 20))
                self.assertEqual(skill_damage(mud, "Zremort"), (500, 9, 40))


if __name__ == "__main__":
    unittest.main()
