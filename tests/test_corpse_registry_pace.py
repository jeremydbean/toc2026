"""The corpse registry's ten-minute refresh no longer writes every corpse
in one pass (review, 2026-11-27).

A 417 ms pulse on Nov 26 was spent in corpse_registry_update with nobody
online: the refresh marked every tracked corpse dirty together and one pass
wrote them all, each a durable write. Now a refresh writes at most one a
pass; a real change -- a thing taken out, a death, a resurrection -- is
still written that pass, durably and in order; and a slow pass logs where
its time went. TOC_CORPSE_REFRESH_SECS and TOC_CORPSE_WRITE_DELAY_MS (tests
only) make the refresh frequent and the storage slow. Synthetic characters.
"""
from __future__ import annotations

import os
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zpacepass1"
ROOM = 4202
NAMES = ["Zpacea", "Zpaceb", "Zpacec", "Zpaced"]


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpsePaceTests(unittest.TestCase):
    def test_refreshes_are_spread_and_changes_are_not(self) -> None:
        env = {"TOC_CORPSE_REFRESH_SECS": "6", "TOC_CORPSE_WRITE_DELAY_MS": "150"}
        with LiveMud(extra_env=env) as mud:
            for name, level in [("Zpacestaff", 70)] + [(n, 20) for n in NAMES]:
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=ROOM)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zpacestaff", PW)
                staff.sync("scroll 0")
                for name in NAMES:
                    with mud.connect(timeout=120) as dead:
                        login(dead, name, PW)
                        staff.sync(f"slay {name.lower()}", timeout=30)
                        dead.send("quit")
                        dead.wait_closed()
                live = mud.root / "corpse" / "live"
                self.assertEqual(len(list(live.glob("*.corpse"))), len(NAMES))
                time.sleep(20)                      # three refreshes and more
                # The last refresh wrote them a pass apart: four different
                # seconds. Before, every refresh wrote all four in one pass
                # -- the same second, 600 ms of writing on this storage.
                written = sorted(int(os.path.getmtime(p)) for p in live.glob("*.corpse"))

                # A real change is written the pass it happens.
                target = sorted(live.glob("*.corpse"))[0]
                before = target.read_text(encoding="latin-1")
                staff.sync("get all 2.corpse", timeout=30)
                staff.sync("get all corpse", timeout=30)
                deadline = time.time() + 5
                changed = False
                while time.time() < deadline and not changed:
                    changed = any(p.read_text(encoding="latin-1") != before
                                  for p in [target]) or len(list(live.glob("*.corpse"))) < len(NAMES)
                    time.sleep(0.5)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            journal = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
        passes = re.findall(r"Corpse registry: a (\d+) ms pass -- .*?(\d+) refreshed", log)
        self.assertTrue(passes, "a slow pass says where its time went")
        self.assertTrue(all(int(refreshed) <= 1 for _, refreshed in passes), passes)
        self.assertEqual(len(set(written)), len(NAMES), f"one refresh a pass: {written}")
        # (The stall journal keeps one row a minute, so it is not the test.)
        self.assertNotRegex(journal, r"\tstall\t.*slowest corpse_registry_update")
        self.assertTrue(changed, "the change reached the disk within the pass")


if __name__ == "__main__":
    unittest.main()
