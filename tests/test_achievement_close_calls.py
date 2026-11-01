"""Close calls and comedy (owner, 2026-11-01).

Alaric recalled out of a Shadowman's fight on 1% of his hit points and
his client sent RECALL six more times at the altar; the owner asked for
an achievement for fleeing on one hit point, other close calls, and funny
things. Eight rows, each awarded where the thing really happens:

  close-call-thread   flee with a single hit point        do_flee
  close-call-flee     flee on a twentieth or less          do_flee
  close-call-recall   recall out of a fight on the same    recall_travel
  close-call-kill     slay a foe on the same               group_gain
  close-call-divine   divine protection spares you         damage()
  funny-sleepwalk     do something asleep                  interpret_body
  funny-already-home  recall standing on your recall point recall_travel
  funny-flee-nothing  flee with nothing fighting you       do_flee

The live test plays all but divine protection's, which needs a death to
turn aside and is held to its hook by source.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GUARD, create_character, login, patch_player_file,
                      room_of, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zccpass1"
TEMPLE, YARD, FLOOR = 4207, 2419, 32700


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def make(mud: LiveMud, name: str, skills: dict, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    end = text.index("\nEnd\n")
    lines = "".join(f"\nSk {pct} '{skill}'" for skill, pct in skills.items())
    path.write_text(text[:end] + lines + text[end:], encoding="latin-1")


def earned(text: str, title: str) -> bool:
    return re.search(r"ACHIEVEMENT EARNED\s*(?:\x1b\[[0-9;]*m)*\s*" + re.escape(title), text) is not None


class CloseCallSourceTests(unittest.TestCase):
    def test_divine_protection_records_the_save(self) -> None:
        fight = source("fight.c")
        spared = fight[fight.index("You have been spared from death by the Gods."):]
        self.assertIn("ACHIEVEMENT_EVENT_DIVINE_SAVE", spared[:400])

    def test_a_flee_into_a_trap_is_no_close_call(self) -> None:
        fight = source("fight.c")
        flee = fight[fight.index("void do_flee( CHAR_DATA *ch, char *argument )"):]
        flee = flee[:flee.index("\n}\n")]
        self.assertIn("fled_on = ch->hit;", flee)
        self.assertIn("ch->in_room == now_in", flee)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CloseCallLiveTests(unittest.TestCase):
    def test_close_calls_and_comedy(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zccstaff", {}, Levl=70)
            make(mud, "Zcclose", {"recall": 100, "second attack": 100, "third attack": 100},
                 Levl=30, Cla=3, HMV="100 100 100 100 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zccstaff", PW)
                login(hero, "Zcclose", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")

                # The comedy, in the Temple.
                self.assertTrue(earned(hero.sync("flee"), "Brave Sir Robin"))
                self.assertTrue(earned(hero.sync("recall"), "No Place Like Home"))
                hero.must("sleep", "You go to sleep")
                self.assertTrue(earned(hero.sync("north"), "Sleepwalker"))
                hero.must("wake", "You wake")

                # One hit point of a hundred: max to 1, restore, max to 100.
                staff.must("set char zcclose hp 1", "now set to 1")
                staff.must("restore zcclose", "restored")
                staff.must("set char zcclose hp 100", "now set to 100")
                self.assertRegex(staff.must("stat char zcclose", "Hp:"), r"Hp: 1/100\b")

                # Flee from a dummy that does not hit back.
                staff.must(f"transfer zcclose {YARD}", "Ok.")
                self.assertEqual(room_of(staff, "zcclose"), YARD)
                hero.sync("dummy fights no")
                hero.sync("kill dummy")
                fled = ""
                for _ in range(30):
                    fled = hero.sync("flee")
                    if "You flee from combat" in fled:
                        break
                self.assertIn("You flee from combat", fled)
                self.assertTrue(earned(fled, "By a Thread"), fled)
                self.assertTrue(earned(fled, "Live to Fight Another Day"), fled)

                # Recall out of the same fight, still on one hit point.
                staff.must(f"transfer zcclose {YARD}", "Ok.")
                hero.sync("kill dummy")
                prayed = ""
                for _ in range(30):
                    prayed = hero.sync("recall")
                    if "You recall from combat" in prayed or "Something is very wrong" in prayed:
                        break
                self.assertTrue(earned(prayed, "Answered Prayer"), prayed)

                # Slay a guard on one hit point of its own, hitting surely.
                staff.must(f"goto {FLOOR}", "")
                staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
                staff.must("set char sparring hp 1", "now set to 1")
                staff.must("restore sparring", "")
                staff.must("set char zcclose hitroll 300", "hitroll set to 300")
                staff.must(f"transfer zcclose {FLOOR}", "Ok.")
                slain = hero.sync("kill sparring")
                self.assertIn("is DEAD", slain)
                self.assertTrue(earned(slain, "Last One Standing"), slain)

                # Each once: a second flee from nothing earns nothing.
                self.assertNotIn("ACHIEVEMENT EARNED", hero.sync("flee"))

    def test_staff_earn_none_of_them(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zccgod", {}, Levl=70)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zccgod", PW)
                staff.sync("scroll 0")
                self.assertNotIn("ACHIEVEMENT EARNED", staff.sync("flee"))
                self.assertNotIn("ACHIEVEMENT EARNED", staff.sync("recall"))


if __name__ == "__main__":
    unittest.main()
