"""Level 7's hungry Goriya says how to get past it (2026-10-27).

Trentlin stood in the Hall of Grumbling on 2026-10-25, killed a goriya,
dropped trick-or-treat candy, ate it and grumbled at the door, and a day
later said in chat he was still stuck at Level 7.  The room said only that
"a little bait might help".  Now its LOOK details, the Goriya in the doorway,
OPEN NORTH and the bait itself all name FEED GORIYA, and LOOK BAIT in the
room says where bait is sold.  The details come from
data/hyrule_room_prose.json and scripts/build_hyrule_area.py.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zgoriyapass1"
HALL_OF_GRUMBLING = 30544
BAIT = 30548


class SourceTests(unittest.TestCase):
    def test_hall_names_what_it_describes(self) -> None:
        prose = json.loads((ROOT / "data" / "hyrule_room_prose.json").read_text(encoding="utf-8"))
        extras = prose["dungeons"]["L7:A6"]["extras"]
        words = " ".join(extra["keywords"] for extra in extras).split()
        for word in ("bowl", "bones", "grumble", "bait"):
            self.assertIn(word, words)
        self.assertTrue(all("FEED GORIYA" in extra["text"] or "FEED the GORIYA" in extra["text"]
                            for extra in extras))

    def test_area_carries_the_hints(self) -> None:
        text = (ROOT / "area" / "hyrule.are").read_text(encoding="latin-1")
        goriya = text[text.index("\n#30508\n"):]
        goriya = goriya[:goriya.index("\n#", 2)]
        self.assertIn("FEED GORIYA", goriya)
        bait = text[text.index(f"\n#{BAIT}\n"):]
        bait = bait[:bait.index("\n#", 2)]
        self.assertIn("Hall of Grumbling", bait)
        self.assertIn("FEED GORIYA", bait)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_the_hall_says_feed_and_feeding_opens_it(self) -> None:
        # Staff walk through Hyrule's seals, so the hall is played by a
        # mortal; a staff character brings them there and hands over bait.
        with LiveMud() as mud:
            for name in ("Zgoriya", "Zkeeper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zgoriya", Levl=40)
            patch_player_file(mud, "Zkeeper", Levl=70)

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as mortal:
                login(mortal, "Zgoriya", PW)
                mortal.sync("scroll 0")
                login(staff, "Zkeeper", PW)
                staff.sync("scroll 0")
                staff.must(f"goto {HALL_OF_GRUMBLING}", "Hall of Grumbling")
                staff.sync("wizinvis")
                staff.must(f"transfer zgoriya {HALL_OF_GRUMBLING}", "Ok")
                self.assertIn("Hall of Grumbling", mortal.sync("look"))

                for word in ("bowl", "bones", "grumble", "hungry"):
                    seen = mortal.sync(f"look {word}")
                    self.assertIn("FEED", seen, (word, seen))
                where = mortal.sync("look bait")
                self.assertIn("Western Reeds", where, where)
                self.assertIn("Silent Sentinels", where, where)

                refused = mortal.sync("open passage")
                self.assertIn("FEED GORIYA", refused, refused)
                self.assertIn("You need food suitable for bait", mortal.sync("feed goriya"))

                staff.must(f"load obj {BAIT}", "enemy bait")
                staff.must("give bait zgoriya", "You give")
                lore = mortal.sync("look bait")
                self.assertIn("Hall of Grumbling", lore, lore)
                fed = mortal.sync("feed goriya")
                self.assertIn("devours it and steps aside", fed, fed)
                self.assertIn("north", mortal.sync("exits").lower())

if __name__ == "__main__":
    unittest.main()
