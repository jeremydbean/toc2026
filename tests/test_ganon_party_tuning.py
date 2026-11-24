"""Ganon for a party of three or four of the best-geared mortals
(owner, 2026-11-18: "tweak ganon to die to a team of ~3-4 of the highest
geared mortals").

Simulations with copies of the top mortals' own characters found three ways
to make him a free kill, each fixed here:
- CONFUSE stunned a guardian for game hours: it threw nothing and barely
  fought back. Hyrule's guardians refuse it, before any mana.
- A guardian threw only at whom it could see, so a kick of dirt in its
  eyes, an invisible attacker or one with no light in Ganon's dark chamber
  took none of its volley. It throws at whoever is fighting it now; only
  wizinvis staff above it are passed over.
- Each landed Silver Arrow blow took a tenth of his health, so a hasted
  thief landing several a round ended him in three rounds. It is a
  thirty-fifth now, and his fireballs are 250-305: a party of three or four
  wins, one or two do not (wiki/hyrule-area.md, "Ganon's Fight").

Synthetic characters in a throwaway world.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zganonpass1"
GANON = 30225
ROOM = 32703            # fixture room: nothing walks in


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as c:
        create_character(c, name, PW)
        c.send("quit")
        c.wait_closed()
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GanonExploitTests(unittest.TestCase):
    def test_confuse_refused_and_ganon_throws_at_his_fighter(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zganongod", Levl=70, Room=4207)
            make(mud, "Zganonhero", Levl=56, Room=4207)
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Zganongod", PW)
                login(hero, "Zganonhero", PW)
                god.must("set skill zganonhero confuse 100", "")
                god.must("restore zganonhero", "")
                god.must("goto %d" % ROOM, "")
                god.must("load mob %d" % GANON, "Ganon")
                god.must("transfer zganonhero %d" % ROOM, "")
                hero.sync("look")
                said = hero.sync("confuse ganon")
                self.assertIn("too vast to cloud", said, said)
                self.assertNotIn("looks very confused", said)
                # He throws at the one fighting him (sight no longer
                # decides it: the source test below holds that).
                god.must("set char zganonhero hp 60000", "")
                god.sync("restore zganonhero")
                mark = len(hero.transcript)
                hero.send("kill ganon")
                for _ in range(30):
                    god.sync("restore zganonhero")
                    hero.drain(1.0)
                    if "hurls a ball of fire straight at you" in hero.transcript[mark:]:
                        break
                self.assertIn("hurls a ball of fire straight at you",
                              hero.transcript[mark:])


class GanonTuningSourceTests(unittest.TestCase):
    def test_numbers_and_rules(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("#define HYRULE_GANON_INSTANT_KILL_DIVISOR 35", fight)
        # Owner, 2026-11-24: no Silver Arrow share during the fight.
        self.assertNotIn("HYRULE_SILVER_ARROW_GANON_DAMAGE_DIVISOR", fight)
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        target = special.split("static bool ganon_may_target", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("can_see", target)
        self.assertIn("wizinvis_hides( victim, mob )", target)
        magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")
        confuse = magic2.split("void do_confuse", 1)[1]
        self.assertLess(confuse.index("is_hyrule_guardian( victim )"),
                        confuse.index("mana_cost = ch->level + 50"))


if __name__ == "__main__":
    unittest.main()
