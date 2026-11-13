"""Exploration maps (src/maps.c; owner, 2026-11-12).

"The mudlet starter map should only display rooms you have been to unless
you get the area map item, excluding dresden and starting areas." The game
decides what a character knows -- rooms walked into, whole areas whose map
they hold, Hyrule dungeons whose map they found, and the areas everybody
knows -- and tells the Mudlet package as GMCP Map.Known; the package hides
the rest (tests/mudlet_fog_spec.lua). Maps come from READ of a map item,
which slain mobiles now and then drop and the wandering cartographer always
does, and from staff GRANTMAP. Ten achievements reward maps held and areas
walked end to end.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

from live_mud import (IAC, DO, TELOPT_GMCP, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SKIP = skip_reason()
PW = "Zmapspass1"
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DUNGEON_ONE = next(d for d in MANIFEST["dungeons"] if d["level"] == 1)
HAON_ROOM = 6000        # haon.are, The edge of the forest
HAON_RABBIT = 6003      # haon.are, a rabbit (level 3)
MARSH_MOB = 8301        # marsh.are, a swamp troll
MARSH_MOB_WORD = "troll"


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def area_rooms(area_file: str) -> list[int]:
    from webadmin.area_parser import AreaParser  # noqa: E402
    parser = AreaParser(ROOT / "area")
    parser.parse_all(built=False)
    return sorted(v for v, room in parser.rooms.items() if room.area_file == area_file)


def known_ranges(client, since: int = 0) -> tuple[bool, list[tuple[int, int]]] | None:
    """The last complete Map.Known the client was sent after `since`."""
    blocks = [b.decode("latin-1") for b in client.subnegotiations(TELOPT_GMCP)[since:]]
    result = None
    pending = None
    for block in blocks:
        if not block.startswith("Map.Known "):
            continue
        msg = json.loads(block.split(" ", 1)[1])
        if msg["part"] == 1:
            pending = (msg["all"], [])
        if pending is None:
            continue
        pending[1].extend((a, b) for a, b in msg["rooms"])
        if msg["part"] == msg["parts"]:
            result = pending
            pending = None
    return result


def knows(ranges, vnum: int) -> bool:
    every, runs = ranges
    return every or any(a <= vnum <= b for a, b in runs)


class SourceTests(unittest.TestCase):
    def test_the_always_known_areas_are_one_table(self) -> None:
        maps = source("maps.c")
        table = maps[maps.index("map_always_known_files[] ="):]
        table = table[:table.index("};")]
        files = re.findall(r'"([a-z_]+\.are)"', table)
        self.assertEqual(files, ["dresden.are", "school.are", "limbo.are", "dummy.are"])
        listed = (ROOT / "area" / "area.lst").read_text(encoding="latin-1").split()
        for name in files:
            self.assertIn(name, listed)

    def test_the_map_prototype_and_the_cartographer_exist(self) -> None:
        from webadmin.area_parser import AreaParser  # noqa: E402
        parser = AreaParser(ROOT / "area")
        parser.parse_all(built=False)
        proto = parser.objects[96]
        self.assertEqual(proto.area_file, "limbo.are")
        self.assertEqual(int(proto.item_type), 28)         # ITEM_MAP
        self.assertEqual(str(proto.values[0]), "92")       # MAP_ITEM_AREA, never 0
        self.assertEqual(int(proto.level), 0)              # unlevelled: never repriced
        self.assertEqual(parser.mobiles[29942].area_file, "seasonal.are")
        merc = source("merc.h")
        self.assertIn("#define MAP_ITEM_AREA              92", merc)
        self.assertIn("#define OBJ_VNUM_AREA_MAP          96", merc)
        self.assertIn("#define MOB_VNUM_CARTOGRAPHER      29942", merc)

    def test_map_known_rides_every_prompt_and_resets_with_gmcp(self) -> None:
        comm = source("comm.c")
        self.assertIn("gmcp_send_map_known( d );", comm)
        gmcp = source("gmcp.c")
        reset = gmcp[gmcp.index("static void gmcp_reset_snapshots("):]
        self.assertIn("d->gmcp_map_known_sent = false;", reset[:1500])
        self.assertIn("map_login( ch );", comm)

    def test_the_cartographer_is_hidden_and_logged_without_his_room(self) -> None:
        bm = source("blackmarket.c")
        unfindable = bm[bm.index("bool is_unfindable_mob("):]
        self.assertIn("is_cartographer( ch )", unfindable[:300])
        maps = source("maps.c")
        spawn = maps[maps.index("bool cartographer_spawn("):]
        spawn = spawn[:spawn.index("\n}\n")]
        self.assertIn('log_string( "Cartographer: appeared." );', spawn)
        self.assertIn("wizinfo( line, LEVEL_IMMORTAL );", spawn)
        self.assertIn('env.setdefault("TOC_NO_CARTOGRAPHER", "1")',
                      (ROOT / "tests" / "live_mud.py").read_text(encoding="utf-8"))
        handler = source("handler.c")
        self.assertIn("cartographer_forget( ch );", handler)

    def test_a_hyrule_dungeon_map_reaches_the_client(self) -> None:
        ach = source("achievements.c")
        note = ach[ach.index("static void achievement_note_object_vnum("):]
        self.assertIn("map_known_changed(ch);", note[:600])


def append_player_line(mud: LiveMud, name: str, line: str) -> None:
    path = mud.player_dir / name
    lines = path.read_text(encoding="latin-1").split("\n")
    end = next(i for i, text in enumerate(lines) if text.strip() == "End")
    lines.insert(end, line)
    path.write_text("\n".join(lines), encoding="latin-1", newline="")


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_maps_from_kills_reading_grants_the_cartographer_and_exploring(self) -> None:
        marsh = area_rooms("marsh.are")
        with LiveMud(extra_env={"TOC_MAP_DROPS": "always",
                                "TOC_CARTOGRAPHER_STILL": "1"}) as mud:
            for name in ("Zmapstaff", "Zmapwalker", "Zmapangel"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmapstaff", Levl=70)
            patch_player_file(mud, "Zmapangel", Levl=66)
            patch_player_file(mud, "Zmapwalker", Levl=10, Room=4207)

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as walker:
                login(staff, "Zmapstaff", PW)
                walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(walker, "Zmapwalker", PW)
                walker.drain(2.0)

                # What everybody knows, and nothing else yet.
                first = known_ranges(walker)
                self.assertIsNotNone(first, "no Map.Known at login")
                self.assertFalse(first[0])
                self.assertTrue(knows(first, 4207), "the Temple (Dresden) is known")
                self.assertTrue(knows(first, 3700), "Mud School is known")
                self.assertFalse(knows(first, HAON_ROOM), "Haon Dor is not known yet")
                mine = walker.must("maps", "Always known")
                self.assertIn("City of Dresden", mine)

                # A slain mobile's map (TOC_MAP_DROPS=always), read.
                staff.must("goto %d" % HAON_ROOM, "edge of the forest", "forest")
                staff.must("load mob %d" % HAON_RABBIT, "rabbit", "Ok", "You have created")
                staff.must("slay rabbit", "rabbit", "slay")
                body = staff.must("look in corpse", "map of")
                self.assertIn("a map of Haon Dor", body)
                staff.must("get map corpse", "map")
                staff.must("goto 4207", "Temple", "Altar")
                staff.must("give map zmapwalker", "map")
                walker.drain(1.0)
                mark = len(walker.subnegotiations(TELOPT_GMCP))
                read = walker.must("read map", "fixed in")
                self.assertIn("Haon Dor", read)
                walker.drain(1.5)
                walker.sync("look")
                after = known_ranges(walker, mark)
                self.assertIsNotNone(after, "no Map.Known after a map was learned")
                self.assertTrue(knows(after, HAON_ROOM))
                self.assertIn("A Map of One's Own", walker.transcript)
                # It came off a slain rabbit: Treasure Map (2026-11-13).
                self.assertIn("Treasure Map", walker.transcript)
                self.assertNotIn("map", walker.sync("inventory").lower())

                # GRANTMAP: a dungeon's map, and the rank check.
                mark = len(walker.subnegotiations(TELOPT_GMCP))
                staff.must("grantmap zmapwalker hyrule1", "now knows the map of Hyrule: Level 1")
                walker.drain(1.0)
                walker.sync("look")
                granted = known_ranges(walker, mark)
                self.assertIsNotNone(granted)
                self.assertTrue(knows(granted, DUNGEON_ONE["first_room_vnum"]))
                self.assertTrue(knows(granted, HAON_ROOM))
                staff.must("grantmap zmapwalker hyrule1", "already knows")
                staff.must("grantmap zmapwalker nowhere-at-all", "No map by that name")

                with mud.connect(timeout=120) as angel:
                    login(angel, "Zmapangel", PW)
                    angel.must("grantmap zmapstaff camelot", "You failed.")
                    angel.send("quit")

                # The cartographer, called here and slain: his map.
                staff.must("goto 6001", "forest", "path", "trail", "")
                staff.must("cartographer here", "The cartographer is in room")
                staff.must("cartographer", "The cartographer is in room")
                # A mortal who stands with him has found him: once a visit.
                staff.must("transfer zmapwalker", "")
                walker.drain(2.0)
                walker.sync("look")
                self.assertIn("A Man With a Map I", walker.transcript)
                self.assertEqual(walker.transcript.count("A Man With a Map I"), 1)
                staff.must("transfer zmapwalker 4207", "")
                staff.must("slay cartographer", "cartographer", "Odric", "slay")
                body = staff.must("look in corpse", "map of")
                self.assertIn("a map of Haon Dor", body)
                staff.must("cartographer", "no cartographer about")
                staff.must("goto 4207", "Temple", "Altar")

                walker.send("quit")
                self.assertTrue(walker.wait_closed())

                # Offline: GRANTMAP writes their file.
                staff.must("grantmap zmapwalker camelot", "while offline", "now knows")

                # Every room of the Old Marsh, walked before this was counted.
                append_player_line(mud, "Zmapwalker",
                                   "AchSet rooms " + " ".join(map(str, marsh)) + " ~")
                with mud.connect(timeout=120) as again:
                    again.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                    login(again, "Zmapwalker", PW)
                    again.drain(2.0)
                    kept = known_ranges(again)
                    self.assertIsNotNone(kept)
                    for vnum in (HAON_ROOM, DUNGEON_ONE["first_room_vnum"], marsh[0]):
                        self.assertTrue(knows(kept, vnum), vnum)
                    self.assertIn("No Stone Unturned I", again.transcript)
                    listing = again.must("maps", "Old Marsh")
                    self.assertIn("explored", listing)
                    # Hindsight: the map of an area already walked end to end.
                    staff.must("goto %d" % marsh[0], "")
                    staff.must("load mob %d" % MARSH_MOB, "Ok", "You have created", "")
                    staff.must("slay %s" % MARSH_MOB_WORD, "slay", "")
                    staff.must("get map corpse", "map")
                    staff.must("goto 4207", "Temple", "Altar")
                    staff.must("give map zmapwalker", "map")
                    again.drain(1.0)
                    again.must("read map", "map")
                    self.assertIn("Hindsight", again.transcript)
                    self.assertRegex(listing, r"Haon Dor\s+held")
                    self.assertRegex(listing, r"Camelot\s+held")
                    again.send("quit")

                # Staff know every room.
                staff.send("quit")
            with mud.connect(timeout=120) as staff:
                staff.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(staff, "Zmapstaff", PW)
                staff.drain(2.0)
                everything = known_ranges(staff)
                self.assertIsNotNone(everything)
                self.assertTrue(everything[0])
                staff.send("quit")



@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmortalMapTests(unittest.TestCase):
    def test_only_an_immortal_by_level_sees_every_room(self) -> None:
        """Owner, 2026-11-12: "trusted players shouldn't get all maps,
        only actual level immortals." A level 20 mortal trusted to 60
        explores like anyone; a level 70 immortal sees everything."""
        with LiveMud() as mud:
            for name in ("Zmaptrusted", "Zmapimm"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmaptrusted", Levl=20, Tru=60)
            patch_player_file(mud, "Zmapimm", Levl=70)
            with mud.connect(timeout=120) as trusted, mud.connect(timeout=120) as imm:
                login(trusted, "Zmaptrusted", PW)
                login(imm, "Zmapimm", PW)
                trusted.sync("scroll 0")
                imm.sync("scroll 0")
                said_trusted = trusted.sync("maps")
                said_imm = imm.sync("maps")
                trusted.send("quit")
                imm.send("quit")
        self.assertNotIn("your map shows every room", said_trusted, said_trusted)
        self.assertIn("your map shows every room", said_imm, said_imm)

if __name__ == "__main__":
    unittest.main()
