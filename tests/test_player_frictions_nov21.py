"""What the players' logs of 2026-11-19 to 21 found (play journal).

- DESPAIR answered a flee with the foe's flight even with others on the
  fleer: Trentlin, at one hit point among five killer clowns, typed FLEE,
  one clown ran, and another killed him. Despair now answers only when
  that foe is the only one fighting them; otherwise they flee themselves.
  And a foe despair drives off that finds no way out says so, and the
  fleer's own flight goes on (2026-11-22: it said the foe fled, and the
  fleer stayed in the fight).
- A mobile's armour was read without stock ROM's times ten, so a builder's
  poorly armoured beast -- Mud School's educated goblin, 8 meaning 80 --
  wore armour of 8 and a level 4 fighter missed seven blows in ten. A
  positive figure is now read as meant (times ten, under the level's cap);
  negative figures and Hyrule's are as they were.
- CONSIDER said "You should win easily" of a 158-round fight; a win that
  would take two minutes or more now says how long.
- WEAR ALL refused "this object" without naming it; the fountain said "no
  longer thirsty" at every sip; DRINK and SLEEP refused for thirst without
  saying where water is; DODGE answered "Huh?"; STASH GET did not mention
  ALL.<name>.

Synthetic Z characters in a throwaway world.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (SPARRING_GUARD, LiveMud, create_character, login,
                      patch_player_file, room_of, skip_reason)

SKIP = skip_reason()
PW = "Zfrpass1"
TEMPLE = 4207
HALLS_FOUNTAIN = 4206
QUIET = 32703                 # fixture room: north to nothing walks in
GOBLIN = 3720                 # Mud School's educated goblin: armour "8 8 8 10"
RING_OF_HOLDING = 4498        # level 10, what Ravagger's WEAR ALL refused


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def flat(text: str) -> str:
    return " ".join(text.split())


@unittest.skipIf(SKIP is not None, SKIP or "")
class FrictionTests(unittest.TestCase):
    def test_messages_armour_and_consider(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zfrstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zfrhero", Levl=4, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zfrstaff", PW)
                login(hero, "Zfrhero", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")

                # WEAR names what it refuses.
                staff.must(f"load obj {RING_OF_HOLDING}", "")
                staff.must("give holding zfrhero", "You give")
                said = flat(hero.sync("wear all"))
                self.assertIn("You must be level 10 to use a ring of holding.", said, said)

                # Water: DRINK with nothing here, and the fountain.
                said = flat(hero.sync("drink"))
                self.assertIn("There is no fountain here.", said)
                self.assertIn("RECALL, then SOUTH and EAST", said)
                staff.must(f"transfer zfrhero {HALLS_FOUNTAIN}", "")
                hero.sync("look")
                staff.must("set char zfrhero thirst 0", "")
                said = flat(hero.sync("drink fountain"))
                self.assertIn("You drink your fill from", said, said)
                self.assertIn("You are no longer thirsty.", said)
                said = flat(hero.sync("drink fountain"))
                self.assertIn("your thirst is already quenched", said, said)
                self.assertNotIn("no longer thirsty", said)

                # DODGE and STASH GET.
                said = flat(hero.sync("dodge"))
                self.assertIn("DODGE works on its own in every fight", said, said)
                staff.must(f"transfer zfrhero {TEMPLE + 1}", "")
                said = flat(hero.sync("stash get nosuchthing"))
                self.assertIn("STASH GET ALL.<name> takes every one by that name", said, said)

                # Armour: a positive figure is ten times, under the cap.
                staff.must(f"goto {QUIET}", "")
                staff.must(f"load mob {GOBLIN}", "You create")
                stat = staff.must("stat goblin", "Armor:")
                found = re.search(r"Armor: pierce: (-?\d+)\s+bash: (-?\d+)\s+slash: (-?\d+)\s+magic: (-?\d+)", stat)
                self.assertIsNotNone(found, stat)
                level = int(re.search(r"Lv: (\d+)", stat).group(1))
                cap = 100 - 6 * level
                self.assertEqual([int(x) for x in found.groups()],
                                 [min(cap, 80), min(cap, 80), min(cap, 80), min(cap, 100)], stat)

                # CONSIDER says a long win is long.
                staff.must("set char goblin hp 30000", "")
                staff.sync("restore goblin")
                staff.must("set char zfrhero hp 30000", "")
                staff.sync("restore zfrhero")
                staff.must(f"transfer zfrhero {QUIET}", "")
                hero.sync("look")
                said = flat(hero.must("consider goblin", "level"))
                self.assertRegex(said, r"You should win")
                self.assertRegex(said, r"It would be a long fight, though: about \d+ minutes?\.")

    def test_despair_answers_only_a_lone_foe(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zfrkeeper", Levl=70, Room=TEMPLE)
            make(mud, "Zfrdesp", Levl=40, Room=TEMPLE,
                 HMV="9000 9000 900 900 900 900", HMVP="9000 900 900")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zfrkeeper", PW)
                login(hero, "Zfrdesp", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("set skill zfrdesp despair 100", "")
                staff.must(f"goto {QUIET}", "")

                def fight(guards: int) -> str:
                    staff.sync("peace")
                    staff.sync("purge")
                    staff.must(f"transfer zfrdesp {QUIET}", "")
                    staff.sync("restore zfrdesp")
                    for _ in range(guards):
                        staff.must(f"load mob {SPARRING_GUARD}", "You create")
                    hero.sync("look")
                    hero.sync("kill sparring")
                    for n in range(2, guards + 1):
                        staff.must(f"force {n}.sparring murder zfrdesp", "Force command issued")
                    mark = len(hero.transcript)
                    for _ in range(20):
                        said = hero.sync("flee")
                        if "despair" in said or "You flee" in said:
                            break
                        hero.drain(0.5)
                    return hero.transcript[mark:]

                # Alone with one foe: despair drives it off. At 100% the roll
                # still misses one time in a hundred (number_percent() < 100
                # fails on a 100), and the fleer then flees themselves: CI
                # drew it on 2026-11-22. Three fights make that one in a
                # million; the two-foe case below stays strict.
                for _ in range(3):
                    said = fight(1)
                    if "is overcome with a feeling of despair" in said:
                        break
                self.assertIn("is overcome with a feeling of despair", said, said[-1500:])
                # With a second on them: they flee themselves.
                said = fight(2)
                self.assertNotIn("despair", said, said[-1500:])
                self.assertIn("You flee", said, said[-1500:])

                # A foe despair drives off that finds no way out -- its only
                # exit leads into a NO_MOB room -- stays and fights: the
                # fleer is told so and their own flight goes on (play
                # journal, 2026-11-21: killer clowns in Korzath's maze).
                staff.must(f"set room {QUIET - 1} flags +no_mob", "no_mob")
                for _ in range(3):
                    said = fight(1)
                    if "is overcome with a feeling of despair" in said:
                        break
                self.assertIn("is overcome with a feeling of despair", said, said[-1500:])
                self.assertIn("But a sparring guard finds no way out!", said, said[-1500:])
                self.assertIn("You flee from combat", said, said[-1500:])
                self.assertEqual(room_of(staff, "zfrdesp"), QUIET - 1, "the fleer fled")


if __name__ == "__main__":
    unittest.main()
