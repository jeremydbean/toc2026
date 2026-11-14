"""Review (2026-11-13), fixed by season_base_area: exploration maps across a seasonal area swap.

season.c loads dresden/limbo/midennir as <base>_halloween.are or
<base>_xmas.are, and load_area_file stores that variant name in
area->file_name. maps.c keys "always known" (map_always_known_files) and
every map region id (achievement_area_id: an FNV hash of file_name) on
file_name, so in season:
  * Dresden and Limbo are no longer always known, and
  * a Miden'nir map learned out of season (map-areas id of
    "midennir.are") no longer covers Miden'nir's rooms.
Synthetic Z characters in a throwaway world only.
"""
from __future__ import annotations

import unittest

from live_mud import IAC, DO, TELOPT_GMCP, LiveMud, create_character, login, \
    patch_player_file, skip_reason
from test_exploration_maps import append_player_line, known_ranges, knows

SKIP = skip_reason()
PW = "Zseasonpw1"
TEMPLE = 4207            # dresden.are: where the fixture stands (walked)
SQUARE = 2401            # dresden.are (and dresden_halloween.are): never walked
SANCTUM = 8              # limbo.are (and limbo_halloween.are)
MIDENNIR_ROOM = 3500     # midennir.are #ROOMS


def fnv_area_id(file_name: str) -> int:
    h = 2166136261
    for c in file_name.lower().encode("latin-1"):
        h ^= c
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


@unittest.skipIf(SKIP is not None, SKIP or "")
class SeasonalMapTests(unittest.TestCase):
    def known_for(self, season: str) -> tuple:
        with LiveMud(extra_env={"TOC_SEASON": season}) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zseasonmap", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zseasonmap", Levl=10, Room=TEMPLE)
            # A map of Miden'nir read out of season: its id is the base file's.
            append_player_line(mud, "Zseasonmap",
                               "AchSet map-areas %d ~" % fnv_area_id("midennir.are"))
            with mud.connect(timeout=120) as walker:
                walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(walker, "Zseasonmap", PW)
                walker.drain(2.0)
                ranges = known_ranges(walker)
                maps = walker.sync("maps")
                walker.send("quit")
        return ranges, maps

    def test_always_known_and_held_maps_survive_the_season(self) -> None:
        plain, plain_maps = self.known_for("none")
        self.assertIsNotNone(plain)
        self.assertTrue(knows(plain, SQUARE))
        self.assertTrue(knows(plain, SANCTUM))
        self.assertTrue(knows(plain, MIDENNIR_ROOM), "control: the held map counts")

        season, season_maps = self.known_for("halloween")
        self.assertIsNotNone(season)
        problems = []
        if not knows(season, SQUARE):
            problems.append("Hallows End: the Oak Tree Square (Dresden) is not always known")
        if not knows(season, SANCTUM):
            problems.append("Hallows End: Limbo is not always known")
        if not knows(season, MIDENNIR_ROOM):
            problems.append("Hallows End: a Miden'nir map held from before is not known")
        self.assertEqual(problems, [], "\nMAPS out of season:\n%s\nMAPS in season:\n%s"
                         % (plain_maps, season_maps))


@unittest.skipIf(SKIP is not None, SKIP or "")
class SeasonIdMigrationTests(unittest.TestCase):
    def test_holiday_copy_ids_move_to_their_area_at_login(self) -> None:
        """Visits and maps saved during Hallows End 2026 sat under the
        copy's own id; the login fix 20261114-season-area-ids moves them to
        the base area, once, and says so."""
        import re
        copy = {
            "map-areas": fnv_area_id("midennir_halloween.are"),
            "quest-areas": fnv_area_id("dresden_halloween.are"),
            "areas": fnv_area_id("limbo_halloween.are"),
        }
        base = {
            "map-areas": fnv_area_id("midennir.are"),
            "quest-areas": fnv_area_id("dresden.are"),
            "areas": fnv_area_id("limbo.are"),
        }
        with LiveMud(extra_env={"TOC_SEASON": "none"}) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zseasonids", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zseasonids", Levl=10, Room=TEMPLE)
            path = mud.player_dir / "Zseasonids"
            # A fixture is a new character, marked for every fix: unmark it.
            path.write_text(re.sub(r"(?m)^Fixes .*\n", "",
                                   path.read_text(encoding="latin-1")),
                            encoding="latin-1", newline="")
            for name, ident in copy.items():
                append_player_line(mud, "Zseasonids", "AchSet %s %d ~" % (name, ident))

            with mud.connect(timeout=120) as walker:
                walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(walker, "Zseasonids", PW)
                said = walker.drain(2.0)
                self.assertIn("counted as the areas they stand for", said)
                self.assertTrue(knows(known_ranges(walker), MIDENNIR_ROOM),
                                "a Miden'nir map learned in season is honoured")
                walker.sync("save")
                walker.send("quit")
                self.assertTrue(walker.wait_closed())

            saved = path.read_text(encoding="latin-1")
            ids = {}
            for line in saved.split("\n"):
                parts = line.split()
                if parts[:1] == ["AchSet"] and len(parts) > 2:
                    ids.setdefault(parts[1], set()).update(
                        int(t) for t in parts[2:] if t.isdigit())
            for name in copy:
                self.assertNotIn(copy[name], ids.get(name, set()), name)
                self.assertIn(base[name], ids.get(name, set()), name)
            self.assertIn("20261114-season-area-ids", saved)

            with mud.connect(timeout=120) as again:
                login(again, "Zseasonids", PW)
                self.assertNotIn("counted as the areas they stand for", again.drain(2.0))
                again.send("quit")


if __name__ == "__main__":
    unittest.main()
