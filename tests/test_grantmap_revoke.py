"""GRANTMAP ... REVOKE takes a map back (2026-11-12; do_grantmap in
src/maps.c).

GRANTMAP could only give. `grantmap <player> <area|hyrule1..9|all> revoke`
takes the map out of the character's map-areas set -- online or offline,
with the same trust and rank check, saved, logged and on WIZINFO -- and
leaves what they walked: a room walked into stays known. A Hyrule dungeon
map found in play is the achievements' record (AchMaps) and is kept, and
nothing earned is taken back. The client is sent a smaller Map.Known at
once, and the package's fog takes the rooms no longer known off the map
again (tests/mudlet_fog_spec.lua, "a map taken away").

Synthetic Z characters in a throwaway world only.
"""
from __future__ import annotations

import unittest

from live_mud import IAC, DO, TELOPT_GMCP, LiveMud, create_character, login, \
    patch_player_file, skip_reason
from test_exploration_maps import DUNGEON_ONE, HAON_ROOM, area_rooms, known_ranges, knows

SKIP = skip_reason()
PW = "Zrevokepw1"
TEMPLE = 4207


@unittest.skipIf(SKIP is not None, SKIP or "")
class GrantmapRevokeTests(unittest.TestCase):
    def test_grant_then_revoke_online_offline_and_by_rank(self) -> None:
        haon = area_rooms("haon.are")
        camelot = area_rooms("camelot.are")
        unwalked = next(v for v in haon if v != HAON_ROOM)
        with LiveMud() as mud:
            for name in ("Zrvstaff", "Zrvwalker", "Zrvangel"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zrvstaff", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Zrvangel", Levl=66, Room=TEMPLE)
            patch_player_file(mud, "Zrvwalker", Levl=10, Room=TEMPLE)

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as walker:
                login(staff, "Zrvstaff", PW)
                staff.sync("scroll 0")
                walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(walker, "Zrvwalker", PW)
                walker.drain(2.0)

                # One room of Haon Dor walked into, then back.
                staff.must("transfer zrvwalker %d" % HAON_ROOM, "Ok", "transfer", "arrives")
                staff.must("transfer zrvwalker %d" % TEMPLE, "Ok", "transfer", "arrives")

                staff.must("grantmap zrvwalker haon", "now knows the map of")
                mark = len(walker.subnegotiations(TELOPT_GMCP))
                said = staff.must("grantmap zrvwalker haon revoke",
                                  "no longer holds the map of")
                self.assertIn("Haon Dor", said)
                self.assertIn("Rooms they have walked stay", said)
                walker.drain(1.0)
                walker.sync("look")
                self.assertIn("The gods take back the map of Haon Dor", walker.transcript)
                after = known_ranges(walker, mark)
                self.assertIsNotNone(after, "no Map.Known after a revoke")
                self.assertFalse(knows(after, unwalked), "the revoked map is still known")
                self.assertTrue(knows(after, HAON_ROOM), "a walked room was taken away")
                self.assertTrue(knows(after, TEMPLE), "Dresden is always known")
                staff.must("grantmap zrvwalker haon revoke", "holds no map of")

                # A dungeon's map, given and taken.
                staff.must("grantmap zrvwalker hyrule1", "now knows the map of Hyrule: Level 1")
                mark = len(walker.subnegotiations(TELOPT_GMCP))
                staff.must("grantmap zrvwalker hyrule1 revoke",
                           "no longer holds the map of Hyrule: Level 1")
                walker.drain(1.0)
                walker.sync("look")
                after = known_ranges(walker, mark)
                self.assertIsNotNone(after)
                self.assertFalse(knows(after, DUNGEON_ONE["first_room_vnum"]))

                # Syntax and rank.
                self.assertIn("Syntax", staff.sync("grantmap zrvwalker haon remove"))
                self.assertIn("Syntax", staff.sync("grantmap zrvwalker haon revoke now"))
                staff.must("grantmap zrvwalker dresden revoke", "no map to take back")
                with mud.connect(timeout=120) as angel:
                    login(angel, "Zrvangel", PW)
                    angel.must("grantmap zrvstaff camelot revoke", "You failed.")
                    angel.send("quit")

                walker.send("quit")
                self.assertTrue(walker.wait_closed())

                # Offline: given, then taken, each written to the file.
                staff.must("grantmap zrvwalker camelot", "now knows")
                staff.must("grantmap zrvwalker all", "now holds every map")
                staff.must("grantmap zrvwalker all revoke", "no longer holds any map")
                staff.must("grantmap zrvwalker all revoke", "holds no map to take back")
                staff.must("grantmap zrvwalker camelot", "now knows")
                staff.must("grantmap zrvwalker camelot revoke", "no longer holds the map of")
                self.assertNotIn("AchSet map-areas",
                                 (mud.player_dir / "Zrvwalker").read_text(encoding="latin-1"))

                log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1",
                                                               errors="replace")
                self.assertIn("Zrvstaff revoked Zrvwalker's map of Haon Dor (1 taken back).", log)
                self.assertIn("Zrvstaff revoked Zrvwalker's map of Camelot (1 taken back) "
                              "while offline.", log)
                self.assertRegex(log, r"Zrvstaff revoked Zrvwalker's maps \(\d+ taken back\) "
                                      r"while offline\.")

                with mud.connect(timeout=120) as again:
                    again.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                    login(again, "Zrvwalker", PW)
                    again.drain(2.0)
                    kept = known_ranges(again)
                    self.assertIsNotNone(kept)
                    self.assertFalse(knows(kept, camelot[0]))
                    self.assertFalse(knows(kept, unwalked))
                    self.assertTrue(knows(kept, HAON_ROOM))
                    again.send("quit")
                staff.send("quit")


if __name__ == "__main__":
    unittest.main()
