"""Hyrule's dungeons are drawn on a Mudlet map when their map is found.

Owner, 2026-10-04: the starter map shows the overworld, not the nine
dungeons; picking up a dungeon's map item fills that dungeon in. The game
sends the floor plan room by room as Hyrule.MapRoom (a whole dungeon does
not fit one GMCP message) and closes it with Hyrule.MapDone; the package
places each room at its plan position, in a map area of the dungeon's own
(owner, 2026-11-12: they shared the overworld's and stacked under it), and
links the exits when the batch is done. Room.Info gives a room walked into
the same square ("map").
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from live_mud import (IAC, DO, TELOPT_GMCP, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DUNGEONS = {d["level"]: d for d in MANIFEST["dungeons"]}
PASSWORD = "Zmappass1"


class SourceTests(unittest.TestCase):
    def test_the_starter_map_leaves_the_dungeons_out(self) -> None:
        xml = (ROOT / "mudlet" / "toc-world-map.xml").read_text(encoding="utf-8")
        ids = {int(v) for v in re.findall(r'<room id="(\d+)"', xml)}
        self.assertIn(30200, ids, "the overworld stays on the starter map")
        for level, dungeon in DUNGEONS.items():
            with self.subTest(level=level):
                inside = set(range(dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1))
                self.assertEqual(set(), ids & inside)

    def test_the_package_draws_a_plan_it_is_sent(self) -> None:
        package = (ROOT / "mudlet" / "package" / "TimesOfChaos.xml").read_text(encoding="utf-8")
        self.assertIn('register("gmcp.Hyrule.MapRoom"', package)
        self.assertIn('register("gmcp.Hyrule.MapDone"', package)
        self.assertIn('"Hyrule 1"', package)
        self.assertIn("10 * number(r.level)", package)

    def test_the_game_sends_it_on_getting_reading_and_arriving(self) -> None:
        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        get_obj = act_obj.split("void get_obj(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_send_map( ch, obj )", get_obj)
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        show = hyrule.split("void hyrule_show_map(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_send_map( ch, obj )", show)
        gmcp = (ROOT / "src" / "gmcp.c").read_text(encoding="latin-1")
        room = gmcp.split("void gmcp_send_room(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_map_on_arrival( ch )", room)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_getting_the_map_sends_the_whole_dungeon(self) -> None:
        dungeon = DUNGEONS[1]
        map_room = next(r["vnum"] for r in dungeon["rooms"]
                        if r["coordinate"] == dungeon["map_coordinate"])
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmapper", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmapper", Levl=10, Room=map_room)
            with mud.connect(timeout=120) as client:
                client.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(client, "Zmapper", PASSWORD)
                client.drain(2.0)
                before = len(client.subnegotiations(TELOPT_GMCP))
                got = client.command("get map", settle=2.5)
                every = [b.decode("latin-1") for b in client.subnegotiations(TELOPT_GMCP)]
                blocks = every[before:]
                client.send("quit")
            rooms = [b for b in blocks if b.startswith("Hyrule.MapRoom ")]
            done = [b for b in blocks if b.startswith("Hyrule.MapDone ")]
            self.assertTrue(rooms, got)
            self.assertEqual(len(done), 1, blocks)
            plan = {}
            for b in rooms:
                data = json.loads(b.split(" ", 1)[1])
                plan[data["num"]] = data
            sent = set(plan)
            self.assertIn(dungeon["entrance_vnum"], sent)
            self.assertIn(map_room, sent)
            # Owner, 2026-11-12: the dungeon is a map area of its own, every
            # room on its own square of it, and the room the player stands in
            # is placed by Room.Info on the very square the plan gives it.
            areas = {data["area"] for data in plan.values()}
            self.assertEqual(areas, {"Hyrule: Level 1 (The Eagle)"})
            squares = [(d["x"], d["y"], d["z"]) for d in plan.values()]
            self.assertEqual(len(squares), len(set(squares)), "two plan rooms share a square")
            cellar = dungeon["cellars"][0]["vnum"]
            self.assertEqual(plan[cellar]["z"], -1)
            infos = [json.loads(b.split(" ", 1)[1]) for b in every
                     if b.startswith("Room.Info ")]
            here = [info for info in infos if info.get("num") == map_room]
            self.assertTrue(here, "no Room.Info for the room stood in")
            self.assertEqual(here[-1]["map"], {"area": "Hyrule: Level 1 (The Eagle)",
                                               "x": plan[map_room]["x"],
                                               "y": plan[map_room]["y"], "z": 0})
            self.assertNotIn("Level", here[-1]["area"], "Room.Info's area stays the game's")
            self.assertEqual(json.loads(done[0].split(" ", 1)[1])["rooms"], len(rooms))
            # The map is learned for good (maps.c): the fog's Map.Known that
            # follows names the whole dungeon as known.
            known = [json.loads(b.split(" ", 1)[1]) for b in blocks
                     if b.startswith("Map.Known ")]
            self.assertTrue(known, "no Map.Known after the dungeon map was found")
            runs = [run for part in known for run in part["rooms"]]
            for vnum in (dungeon["entrance_vnum"], dungeon["last_room_vnum"]):
                self.assertTrue(any(a <= vnum <= b for a, b in runs), vnum)


if __name__ == "__main__":
    unittest.main()
