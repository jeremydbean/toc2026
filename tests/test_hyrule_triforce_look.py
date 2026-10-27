"""LOOK TRIFORCE draws the Triforce, and the Master Sword is not one (2026-10-27).

The owner asked for a short Triforce description with the three triangles
drawn in ASCII, and for the Master Sword to lose the "triforce" keyword it
carried, so TRIFORCE always means the Triforce. Both come from
scripts/build_hyrule_area.py.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Ztriforce1"
MASTER_SWORD = 30200
TRIFORCE = 30286
ART = ["               /\\", "             /____\\", "          /____\\/____\\"]


def record(vnum: int) -> str:
    text = (ROOT / "area" / "hyrule.are").read_text(encoding="latin-1")
    objects = text[text.index("#OBJECTS"):]
    start = objects.index(f"\n#{vnum}\n")
    return objects[start:objects.index("\n#", start + 2)]


class SourceTests(unittest.TestCase):
    def test_master_sword_is_not_a_triforce(self) -> None:
        self.assertNotIn("triforce", record(MASTER_SWORD).split("~")[0].lower())

    def test_triforce_is_drawn(self) -> None:
        text = record(TRIFORCE)
        for line in ART:
            self.assertIn(line + "\n", text)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_look_triforce(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Ztriforce", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Ztriforce", Levl=70)

            with mud.connect(timeout=120) as client:
                login(client, "Ztriforce", PW)
                client.sync("scroll 0")
                client.must(f"load obj {MASTER_SWORD}", "Master Sword")
                self.assertIn("do not see that here", client.sync("look triforce"))
                client.must(f"load obj {TRIFORCE}", "Triforce")
                seen = client.sync("look triforce")
                for line in ART:
                    self.assertIn(line, seen, seen)
                self.assertIn("Power, Wisdom and Courage", seen, seen)


if __name__ == "__main__":
    unittest.main()
