"""SOUVENIRS: a keepsake of each area walked end to end (2026-11-15).

Read from what is saved already -- the explored-areas set -- and picked by
the character's serial among the area's own rooms: the same every time,
nothing new in the file, no stats. Synthetic Z characters in a disposable
world, the set planted in the fixture's file.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zsouvpass1"


def area_id(file_name: str) -> int:
    h = 2166136261
    for c in file_name.lower().encode("latin-1"):
        h ^= c
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def plant_explored(mud, name, files):
    path = mud.player_dir / name
    lines = [l for l in path.read_text(encoding="latin-1").split("\n")
             if not l.startswith("AchSet explored-areas ")]
    ids = " ".join(str(i) for i in sorted(area_id(f) for f in files))
    at = next(i for i, l in enumerate(lines) if l.startswith("Levl "))
    lines.insert(at, f"AchSet explored-areas {ids} ~")
    path.write_text("\n".join(lines), encoding="latin-1")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SouvenirTests(unittest.TestCase):
    def test_keepsakes_from_explored_areas(self) -> None:
        with LiveMud() as mud:
            for name in ("Zsouvenir", "Zsouvnone"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
                patch_player_file(mud, name, Levl=20, Room=4207)
            plant_explored(mud, "Zsouvenir", ["hood.are", "mirror.are"])
            before = (mud.player_dir / "Zsouvenir").read_text(encoding="latin-1")
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as none:
                login(hero, "Zsouvenir", PW)
                login(none, "Zsouvnone", PW)
                self.assertIn("No keepsakes yet", none.sync("souvenirs"))
                said = hero.sync("souvenirs", timeout=30)
                self.assertIn("Keepsakes of the places you have walked end to end", said, said)
                kept = re.findall(r"(?m)^  (.+?): (a .+)$", said.replace("\r", ""))
                self.assertEqual(len(kept), 2, said)
                self.assertRegex(said, r"2 of \d+ areas")
                # The same every time.
                self.assertEqual(said.replace("\r", ""), hero.sync("souvenirs", timeout=30).replace("\r", ""))
                for line in said.replace("\r", "").split("\n"):
                    self.assertLessEqual(len(line), 120, line)
                hero.must("save", "Saving")
            after = (mud.player_dir / "Zsouvenir").read_text(encoding="latin-1")
            # Nothing new kept: no souvenir key, the set as it was.
            self.assertNotIn("Souvenir", after)
            self.assertEqual(re.findall(r"(?m)^AchSet explored-areas .*$", before),
                             re.findall(r"(?m)^AchSet explored-areas .*$", after))


class SouvenirSourceTests(unittest.TestCase):
    def test_writes_nothing_and_is_last(self) -> None:
        maps = (ROOT / "src" / "maps.c").read_text(encoding="utf-8")
        body = maps.split("void do_souvenirs", 1)[1]
        for call in ("save_char_obj", "achievement_set_insert", "obj_to_char", "create_object"):
            self.assertNotIn(call, body, call)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        self.assertEqual(re.findall(r'\{\s*"([^"]+)"', table)[-1], "souvenirs")


if __name__ == "__main__":
    unittest.main()
