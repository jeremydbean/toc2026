"""The last two guardians are group fights, by rule (owner, 2026-10-28).

The ashen Gleeok, Level 8's guardian, needs two players fighting
together and Ganon three: below that a blow is turned aside, an instant
kill too, and the fight can only be lost. Numbers alone could not
promise it -- a buffed soloist beat the Gleeok and a buffed pair beat
Ganon in the live playtests. hyrule_party_refuses in src/hyrule.c is the
rule; damage() asks it through hyrule_blow_turned_aside, and the instant
kills through hyrule_instant_kill_resisted.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, MIND_ARENA, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zpartypass1"
ASHEN_GLEEOK = 30316


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


class PartyRuleSourceTests(unittest.TestCase):
    def test_the_party_sizes(self) -> None:
        merc = source("merc.h")
        self.assertRegex(merc, r"#define HYRULE_PARTY_GLEEOK\s+2\b")
        self.assertRegex(merc, r"#define HYRULE_PARTY_GANON\s+3\b")
        hyrule = source("hyrule.c")
        self.assertIn("HYRULE_ASHEN_GLEEOK_VNUM  30316", hyrule)
        self.assertIn("HYRULE_GANON_VNUM_PARTY   30225", hyrule)

    def test_blows_and_instant_kills_both_ask(self) -> None:
        hyrule = source("hyrule.c")
        turned = hyrule[hyrule.index("bool hyrule_blow_turned_aside("):]
        turned = turned[:turned.index("\n}\n")]
        self.assertIn("hyrule_party_refuses( ch, victim, true )", turned)
        fight = source("fight.c")
        resisted = fight[fight.index("static bool hyrule_instant_kill_resisted("):]
        resisted = resisted[:resisted.index("\n}\n")]
        self.assertLess(resisted.index("hyrule_party_refuses"), resisted.index("share ="))
        defies = fight[fight.index("bool hyrule_defies_instant_death("):]
        defies = defies[:defies.index("\n}\n")]
        self.assertIn("hyrule_party_needed( victim ) > 0", defies)

    def test_staff_are_not_counted(self) -> None:
        hyrule = source("hyrule.c")
        size = hyrule[hyrule.index("int hyrule_party_size("):]
        size = size[:size.index("\n}\n")]
        self.assertIn("IS_TRUSTED(rch, LEVEL_IMMORTAL)", size)


def gleeok_hp(staff) -> tuple:
    said = staff.sync("stat mob gleeok")
    hp = re.search(r"Hp: (-?\d+)/(-?\d+)", said)
    if hp is None:
        raise AssertionError(said)
    return int(hp.group(1)), int(hp.group(2))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PartyRuleLiveTests(unittest.TestCase):
    def test_one_cannot_wound_the_ashen_gleeok_and_two_can(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Zpartya", "Zpartyb", "Zpkeeper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            for name in ("Zpartya", "Zpartyb"):
                # Enough to stand through the test; the fight is not the point.
                patch_player_file(mud, name, Levl=55, Room=4207,
                                  HMV="30000 30000 500 500 500 500",
                                  HMVP="30000 500 500")
            patch_player_file(mud, "Zpkeeper", Levl=70, Room=4207)

            with mud.connect(timeout=120) as staff, \
                    mud.connect(timeout=120) as one, \
                    mud.connect(timeout=120) as two:
                login(staff, "Zpkeeper", PW)
                login(one, "Zpartya", PW)
                login(two, "Zpartyb", PW)
                for c in (staff, one, two):
                    c.sync("scroll 0")
                staff.sync("holylight")
                staff.must(f"goto {MIND_ARENA}", "")
                staff.sync("wizinvis")
                staff.must(f"load mob {ASHEN_GLEEOK}", "You create")
                for name in ("zpartya", "zpartyb"):
                    staff.must(f"transfer {name} {MIND_ARENA}", "Ok")
                hp, max_hp = gleeok_hp(staff)
                self.assertEqual(hp, max_hp)

                # Alone: every blow is shrugged off, and it says why.
                said = one.sync("kill gleeok", barrier="time")
                said += one.sync("look", barrier="time")
                said += one.sync("look", barrier="time")
                self.assertIn("It takes 2 of you", said, said)
                self.assertIn("you stand alone", said, said)
                self.assertEqual(gleeok_hp(staff)[0], max_hp)

                # Two fighting together wound it.
                two.must("follow zpartya", "You now follow")
                one.must("group zpartyb", "joins")
                two.sync("kill gleeok", barrier="time")
                for _ in range(4):
                    one.sync("look", barrier="time")
                    two.sync("look", barrier="time")
                self.assertLess(gleeok_hp(staff)[0], max_hp)


if __name__ == "__main__":
    unittest.main()
