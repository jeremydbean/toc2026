"""A guardian knocked down mid-fight is still in the fight (2026-11-24).

Ganon and the Level 7 and 8 guardians close their wounds out of a fight,
a tenth of their health a mobile pulse. "Out of a fight" was read as
``fighting == NULL || position != POS_FIGHTING``, so a boss whose own bash
missed -- it falls flat, POS_RESTING with a wait state -- or who was
tripped or bashed healed every pulse it spent on the ground. On the live
game every "every wound Ganon bore is gone" came straight after "You evade
Ganon's bash, causing it to fall flat on its face."

This wounds the ancient Aquamentus and Ganon in a closed arena, bashes
each to the ground while the fight goes on, and watches its health stay
put; then stops the fight and watches it heal. The mob's timer is set
above four so that the staff's own blows, which stand a downed victim back
up in damage(), leave it lying there for the whole window.
"""
from __future__ import annotations

import re
import sys
import time
import unittest
from pathlib import Path

from live_mud import MIND_ARENA, LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_hyrule_area import BOSS_MOBS  # noqa: E402

SKIP = skip_reason()
PW = "Zdownpass1"
STAFF = "Zdownstaff"
HP = re.compile(r"Hp: (\d+)/(\d+)")
POSITION = re.compile(r"Position: (\d+)")
FIGHTING = re.compile(r"Fighting: (\S+)")
POS_RESTING = 5
WHOLE = 200000              # above Ganon's own 67,501, so both start short
POS_FIGHTING = 7


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


class KnockdownSourceTests(unittest.TestCase):
    def test_neither_special_reads_a_downed_boss_as_out_of_the_fight(self) -> None:
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        for name in ("bool spec_ganon(", "bool spec_hyrule_guardian("):
            body = special.split(name, 1)[1].split("\n}\n", 1)[0]
            self.assertNotIn("mob->fighting == NULL || mob->position != POS_FIGHTING", body, name)
            self.assertIn("if ( mob->fighting == NULL )", body, name)


@unittest.skipIf(SKIP is not None, SKIP or "")
class KnockdownLiveTests(unittest.TestCase):
    def stat(self, staff, word: str) -> tuple[int, int, int, str]:
        text = staff.sync(f"stat mob {word}")
        hp, pos, fighting = HP.search(text), POSITION.search(text), FIGHTING.search(text)
        self.assertIsNotNone(hp, text)
        self.assertIsNotNone(pos, text)
        self.assertIsNotNone(fighting, text)
        return int(hp.group(1)), int(hp.group(2)), int(pos.group(1)), fighting.group(1)

    def knock_down_and_watch(self, staff, vnum: int, word: str) -> None:
        staff.sync(f"load mob {vnum}")
        staff.must(f"set char {word} hp {WHOLE}", "")
        staff.must(f"set char {word} timer 500", "")
        hit, top, _, _ = self.stat(staff, word)
        self.assertEqual(top, WHOLE)
        self.assertLess(hit, top - top // 5, f"{word} starts well short of whole")

        # Bash until one lands. A miss puts the staff on the floor for a
        # moment; the next try waits out its lag.
        deadline = time.monotonic() + 60
        while True:
            seen = staff.sync(f"bash {word}")
            seen += staff.drain(1.5)
            _, _, pos, fighting = self.stat(staff, word)
            if pos == POS_RESTING and fighting != "(none)":
                break
            self.assertLess(time.monotonic(), deadline, f"never bashed {word} down: {seen}")
            if pos == POS_FIGHTING:
                continue
            staff.drain(2.0)

        # Down and still fighting, for three mobile pulses: no healing.
        before, _, _, _ = self.stat(staff, word)
        time.sleep(13)
        after, top, pos, fighting = self.stat(staff, word)
        self.assertEqual(pos, POS_RESTING, f"{word} stayed on the ground")
        self.assertNotEqual(fighting, "(none)", f"{word} stayed in the fight")
        self.assertLess(after - before, top // 10,
                        f"{word} healed while knocked down mid-fight ({before} -> {after})")

        # The fight over, it closes its wounds as before.
        staff.sync("peace")
        time.sleep(9)
        healed, top, _, fighting = self.stat(staff, word)
        self.assertEqual(fighting, "(none)")
        self.assertGreaterEqual(healed - after, top // 10,
                                f"{word} heals once left alone ({after} -> {healed})")
        staff.sync(f"purge {word}")

    def test_the_ancient_aquamentus_and_ganon_do_not_heal_on_the_ground(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, STAFF, Levl=70, Room=MIND_ARENA,
                 HMV="30000 30000 1000 1000 1000 1000")
            with mud.connect(timeout=120) as staff:
                login(staff, STAFF, PW)
                staff.sync("scroll 0")
                staff.must(f"goto {MIND_ARENA}", "")
                staff.sync("set skill self bash 100")
                staff.must(f"set char {STAFF.lower()} hitroll 300", "")

                self.knock_down_and_watch(staff, BOSS_MOBS[7], "ancient")
                self.knock_down_and_watch(staff, BOSS_MOBS[9], "ganon")


if __name__ == "__main__":
    unittest.main()
