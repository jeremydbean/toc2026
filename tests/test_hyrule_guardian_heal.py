"""Guardians past Level 6 heal when left alone (owner, 2026-11-03).

The ashen Gleeok, sized for two, fell to one player on 2026-11-02 by
hit-and-run: he fled at 13% and 28% of his own health, healed in town and
walked back to find its wounds still open, and three tries wore its 35,000
hit points down. Ganon already closed his wounds out of a fight; now the
Level 7 and 8 guardians do too (spec_hyrule_guardian), a tenth of their
health a pulse, and the earlier guardians are left as they were. This
wounds each in a closed arena, stops the fight, and watches.
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
PW = "Zhealpass1"
HP = re.compile(r"Hp: (\d+)/(\d+)")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


class GuardianHealSourceTests(unittest.TestCase):
    def test_the_healing_list_is_levels_seven_and_eight(self) -> None:
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        listed = special.split("hyrule_guardians_that_heal[] = {", 1)[1].split("}", 1)[0]
        self.assertEqual({int(v) for v in re.findall(r"\d+", listed)},
                         {BOSS_MOBS[7], BOSS_MOBS[8]})
        self.assertIn("#define GUARDIAN_REGEN_DIVISOR  10", special)
        self.assertIn("#define GANON_REGEN_DIVISOR     10", special, "the same rate as Ganon's")


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianHealLiveTests(unittest.TestCase):
    def hp(self, staff, word: str) -> tuple[int, int]:
        found = HP.search(staff.sync(f"stat mob {word}"))
        self.assertIsNotNone(found, word)
        return int(found.group(1)), int(found.group(2))

    def raise_max(self, staff, vnum: int, word: str) -> tuple[int, int]:
        """Twenty thousand hit points short, by raising its maximum to
        SET's ceiling of 30,000: a staff member's blows land a few dozen
        through a guardian's defences, and a healer closes those before
        STAT can be typed."""
        staff.sync(f"load mob {vnum}")
        staff.must(f"set char {word} hp 30000", "")
        return self.hp(staff, word)

    def test_levels_seven_and_eight_heal_and_gohma_does_not(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zhealstaff", Levl=70, Room=MIND_ARENA,
                 HMV="30000 30000 1000 1000 1000 1000")
            with mud.connect(timeout=120) as staff:
                login(staff, "Zhealstaff", PW)
                staff.sync("scroll 0")
                staff.must(f"goto {MIND_ARENA}", "")

                # Level 7: whole again within forty seconds of a 20,000 wound.
                hit, top = self.raise_max(staff, BOSS_MOBS[7], "ancient")
                self.assertEqual(top, 30000)
                self.assertLess(hit, top)
                deadline = time.monotonic() + 40
                while hit < top and time.monotonic() < deadline:
                    time.sleep(2)
                    hit, top = self.hp(staff, "ancient")
                self.assertEqual(hit, top, "the ancient Aquamentus healed itself")
                staff.sync("purge ancient")

                # Level 6: still far short after three pulses.
                hit, top = self.raise_max(staff, BOSS_MOBS[6], "gohma")
                time.sleep(12)
                later, _ = self.hp(staff, "gohma")
                self.assertLess(later - hit, top // 10, "Gohma keeps her wounds")
                self.assertLess(later, top)
                staff.sync("purge gohma")

                # Level 8, wounded in a real fight and then left: whole again.
                # Fought until a blow lands, not for a fixed two rounds: a
                # nightly run's staff missed every swing in six seconds
                # (CI, 2026-11-05). A hitroll that lands, and a deadline.
                staff.must("set char zhealstaff hitroll 300", "")
                staff.sync(f"load mob {BOSS_MOBS[8]}")
                staff.sync("kill ashen")
                deadline = time.monotonic() + 45
                while True:
                    staff.drain(3.0)
                    hit, top = self.hp(staff, "ashen")
                    if hit < top or time.monotonic() > deadline:
                        break
                self.assertLess(hit, top, "wounded while the fight lasted")
                staff.sync("peace")
                time.sleep(6)
                hit, top = self.hp(staff, "ashen")
                self.assertEqual(hit, top, "the ashen Gleeok healed once left alone")

if __name__ == "__main__":
    unittest.main()
