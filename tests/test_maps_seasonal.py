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


if __name__ == "__main__":
    unittest.main()
