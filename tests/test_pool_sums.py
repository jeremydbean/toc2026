"""A maximum pool's bonuses add up wide and come off exactly (review,
2026-11-12).

Pools are int, held to POOL_MAX (a billion), and every multiplication was
made wide (pool_scale); the additions were not. affect_modify added and
took off each APPLY_HIT/MANA/MOVE bonus straight into the int maximum,
and SET HP set that maximum under whatever bonuses stood. A TITANIC laid
on 200 million hit points is a bonus of 800 million; SET HP 100 under it
and the TITANIC's end took 800 million off a maximum of 100, leaving
-799,999,900. Now every bonus goes through pool_max_adjust: the sum is
made in long long, the stored maximum held to [POOL_FLOOR, POOL_MAX], and
what lies past the bound is carried, so a bonus taken off gives back
exactly what was there before it; SET sets the base (pcdata->perm_*) with
the standing bonuses on top, as a reload would.

The ring of vigour (object 32713, fixture world) is +1,000 hit points.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zpoolsums1"
TEMPLE = 4207
POOL_MAX = 1_000_000_000
RING = 32713


def max_hit(staff, name: str) -> int:
    text = staff.must(f"stat char {name}", "Hp:")
    found = re.search(r"Hp:\s*-?\d+/(-?\d+)", text)
    assert found, text
    return int(found.group(1))


class PoolSumSourceTests(unittest.TestCase):
    def test_every_bonus_goes_through_the_wide_sum(self) -> None:
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        modify = handler.split("void affect_modify( CHAR_DATA *ch, AFFECT_DATA *paf, bool fAdd )", 1)[1]
        modify = modify.split("\n}\n", 1)[0]
        self.assertIn("pool_max_adjust( ch, paf->location,", modify)
        reset = handler.split("void reset_char(CHAR_DATA *ch)", 1)[1].split("\n}\n", 1)[0]
        for text in (modify, reset):
            self.assertNotRegex(text, r"max_(hit|mana|move)\s*[-+]=\s*mod")
        self.assertIn("pool_carry_clear( ch );", reset)
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertNotRegex(save, r"max_(hit|mana|move)\s*-=\s*paf->modifier")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        for location in ("APPLY_HIT", "APPLY_MANA", "APPLY_MOVE"):
            self.assertIn(f"pool_set_base( victim, {location}, value );", wiz)
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("long long           pool_carry[3];", merc)


@unittest.skipIf(SKIP is not None, SKIP or "")
class PoolSumLiveTests(unittest.TestCase):
    def test_bonuses_on_and_off_leave_the_maximum_where_it_was(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name, level in (("Zsumstaff", 70), ("Zsumfat", 30)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=TEMPLE)
            seen: list[tuple[str, int]] = []
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fat:
                login(staff, "Zsumstaff", PW)
                login(fat, "Zsumfat", PW)
                for client in (staff, fat):
                    client.sync("scroll 0")

                def step(command: str, *expected: str, client=None) -> int:
                    (client or staff).must(command, *expected)
                    now = max_hit(staff, "zsumfat")
                    seen.append((command, now))
                    return now

                def ring_on_and_off() -> None:
                    staff.must(f"load obj {RING} 1", "fixture ring")
                    staff.must("give ring zsumfat", "You give")
                    step("wear ring", "ring", client=fat)
                    step("remove ring", "ring", client=fat)
                    fat.must("drop ring", "You drop")

                # The owner's case: a billion, TITANIC (nothing left to add),
                # the ring, both off -- a billion.
                start = step("set char zsumfat hp 1000000000", "1000000000")
                step("titanic zsumfat", "titanic")
                ring_on_and_off()
                end = step("titanic zsumfat", "removed")
                self.assertEqual((start, end), (POOL_MAX, POOL_MAX), seen)

                # SET over a standing TITANIC: the base is set, the boost
                # stays on top (held at the ceiling), and its end leaves the
                # base. It used to take 800 million off the new value.
                step("set char zsumfat hp 200000000", "200000000")
                self.assertEqual(step("titanic zsumfat", "titanic"), POOL_MAX)
                step("set char zsumfat hp 1000000000", "1000000000")
                ring_on_and_off()
                self.assertEqual(step("titanic zsumfat", "removed"), POOL_MAX, seen)

                # And a small base under it: never negative, back to 100.
                step("set char zsumfat hp 200000000", "200000000")
                step("titanic zsumfat", "titanic")
                self.assertEqual(step("set char zsumfat hp 100", "100"), 800_000_100, seen)
                ring_on_and_off()
                self.assertEqual(step("titanic zsumfat", "removed"), 100, seen)

                # A reload rebuilds the maximum from the base and every
                # bonus: a billion with a standing boost of 800 million is
                # held at the ceiling, not 1.8 billion.
                step("set char zsumfat hp 200000000", "200000000")
                step("titanic zsumfat", "titanic")
                step("set char zsumfat hp 1000000000", "1000000000")
                fat.send("quit")
                self.assertTrue(fat.wait_closed())
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fat:
                login(staff, "Zsumstaff", PW)
                login(fat, "Zsumfat", PW)
                staff.sync("scroll 0")
                reloaded = max_hit(staff, "zsumfat")
                after = step("titanic zsumfat", "removed")
                for client in (fat, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.player_dir / "Zsumfat").read_text(encoding="latin-1")

        self.assertEqual(reloaded, POOL_MAX, seen)
        self.assertEqual(after, POOL_MAX, seen)
        for command, value in seen:
            self.assertTrue(-POOL_MAX <= value <= POOL_MAX, (command, value, seen))
            self.assertGreater(value, 0, (command, value, seen))
        self.assertRegex(text, r"(?m)^HMVP 1000000000 ")


if __name__ == "__main__":
    unittest.main()
