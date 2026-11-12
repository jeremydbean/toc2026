"""WIMPY is as wide as the hit points it is a threshold of (review,
2026-11-12).

Hit points went to int on 2026-11-11 (POOL_MAX) and wimpy stayed a
short: with 100,000 hit points WIMPY 40000 said "Wimpy set to 40000"
and stored -25536, and a negative threshold never flees. Wimpy is an int
now through WIMPY (explicit and the default, a fifth of the maximum),
staff SET, the save and the load; a wrapped value an old file holds
reads as 0.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, create_character, login, patch_player_file,
                      place_sparring_guard, room_of, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zwidewimpy1"
TEMPLE = 4207


def wimpy_of(staff, name: str) -> int:
    reply = staff.must(f"stat char {name}", "Wimpy:")
    found = re.search(r"Wimpy: (-?\d+)", reply)
    assert found, reply
    return int(found.group(1))


class WimpySourceTests(unittest.TestCase):
    def test_wimpy_is_an_int(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertRegex(merc, r"\bint\s+wimpy;")
        for path in sorted((ROOT / "src").glob("*.c")):
            text = path.read_text(encoding="latin-1")
            self.assertNotRegex(text, r"wimpy\s*=\s*(\(sh_int\)|\(int16_t\)|clamp_sh_int)", path.name)
            self.assertNotRegex(text, r"KEY\(\s*\"Wimpy?\"", path.name)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WimpyLiveTests(unittest.TestCase):
    def test_a_wimpy_past_the_old_short(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Zwidestaff", "Zwidebig"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwidestaff", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Zwidebig", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zwidestaff", PW)
                login(hero, "Zwidebig", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("set char zwidebig hp 200000", "200000")

                # The default: a fifth of the maximum.
                hero.must("wimpy", "Wimpy set to 40000")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 40000)
                # Explicit, and still held to half the maximum.
                hero.must("wimpy 90000", "Wimpy set to 90000")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 90000)
                hero.must("wimpy 100001", "cowardice")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 90000)
                # Staff SET.
                staff.must("set char zwidebig wimpy 50000", "wimpy set to 50000")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 50000)

                # A fight: 99,010 hit points of 200,000 and a wimpy of
                # 99,000, so the first blow that lands is under it.
                staff.must("set char zwidebig hp 99010", "99010")
                staff.sync("restore zwidebig")
                staff.must("set char zwidebig hp 200000", "200000")
                hero.must("wimpy 99000", "Wimpy set to 99000")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 99000)
                place_sparring_guard(staff, "zwidestaff", SPARRING_FLOOR)
                staff.must(f"transfer zwidebig {SPARRING_FLOOR}", "Ok.")
                staff.sync(f"goto {TEMPLE}")
                self.assertEqual(room_of(staff, "zwidebig"), SPARRING_FLOOR)
                seen = hero.sync("look")
                self.assertIn("sparring guard", seen, seen)
                hero.buffer = ""
                hero.send("kill guard")
                # Nothing typed after KILL: listen for wimpy.
                try:
                    outcome = hero.expect("You flee from combat", "PANIC! You couldn't escape",
                                          timeout=60)
                except AssertionError:
                    outcome = "no flee: " + hero.transcript[-600:]
                staff.sync(f"goto {SPARRING_FLOOR}")
                staff.sync("peace")
                staff.sync(f"goto {TEMPLE}")
                self.assertIn(outcome, ("You flee from combat", "PANIC! You couldn't escape"),
                              "wimpy 99000 never tried")

                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            text = (mud.player_dir / "Zwidebig").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Wimp\s+99000$")

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zwidestaff", PW)
                login(hero, "Zwidebig", PW)
                staff.sync("scroll 0")
                self.assertEqual(wimpy_of(staff, "zwidebig"), 99000, "kept across a reload")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                # A value a short wrapped, as an old save holds it, is no
                # threshold at all: it reads as 0.
                patch_player_file(mud, "Zwidebig", Wimp=-25536)
                with mud.connect(timeout=120) as again:
                    login(again, "Zwidebig", PW)
                    self.assertEqual(wimpy_of(staff, "zwidebig"), 0)
                    again.send("quit")
                    self.assertTrue(again.wait_closed())
                staff.send("quit")
                staff.wait_closed()


if __name__ == "__main__":
    unittest.main()
