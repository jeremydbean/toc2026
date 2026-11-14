"""Review (2026-11-13), fixed in map_room_known: a room the game never lists in Map.Known.

map_room_known() knows a room walked into only through ACH_SET_ROOMS, and
achievement_record_room_visit() records only rooms achievement_room_counts()
accepts -- never a built area (area/built/, ANEW) or custom.are. So a mortal
standing in a built room is sent Room.Info for it (the package draws it and
marks it walked), and the next Map.Known -- any map learned, GRANTMAP, the
next login -- does not list it; the package's onMapKnown clears `walked`
and the fog deletes the room the player is standing in
(tests/zreview_mudlet_fog_probe_tail.lua, P1). Synthetic Z characters only.
"""
from __future__ import annotations

import json
import unittest

from live_mud import IAC, DO, TELOPT_GMCP, LiveMud, create_character, login, \
    patch_player_file, skip_reason
from test_exploration_maps import known_ranges, knows

SKIP = skip_reason()
PW = "Zbuiltpw1"
LO, HI = 21000, 21009
ROOMVNUM = 21001


@unittest.skipIf(SKIP is not None, SKIP or "")
class BuiltRoomTests(unittest.TestCase):
    def test_the_room_you_stand_in_is_in_map_known(self) -> None:
        with LiveMud() as mud:
            for name in ("Zbuiltimm", "Zbuiltwalk"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuiltimm", Levl=70, Room=4207)
            patch_player_file(mud, "Zbuiltwalk", Levl=10, Room=4207)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as walker:
                login(imm, "Zbuiltimm", PW)
                imm.sync("scroll 0")
                imm.must("anew %d %d Zed Probe Hollow" % (LO, HI), "Created area")
                imm.sync("goto %d" % ROOMVNUM)
                imm.sync("set room %d name A Probe Hollow" % ROOMVNUM)
                imm.sync("goto 4207")
                walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(walker, "Zbuiltwalk", PW)
                walker.drain(2.0)
                imm.must("transfer zbuiltwalk %d" % ROOMVNUM, "")
                walker.drain(1.0)
                walker.sync("look")
                blocks = [b.decode("latin-1") for b in walker.subnegotiations(TELOPT_GMCP)]
                infos = [json.loads(b.split(" ", 1)[1]) for b in blocks
                         if b.startswith("Room.Info ")]
                self.assertEqual(infos[-1]["num"], ROOMVNUM, "control: Room.Info sent")
                mark = len(blocks)
                imm.must("grantmap zbuiltwalk haon", "now knows")
                walker.drain(1.0)
                walker.sync("look")
                after = known_ranges(walker, mark)
                walker.send("quit")
                imm.send("quit")
        self.assertIsNotNone(after, "no Map.Known after GRANTMAP")
        self.assertTrue(knows(after, ROOMVNUM),
                        "Map.Known omits the room the player is standing in (%d)" % ROOMVNUM)


if __name__ == "__main__":
    unittest.main()
