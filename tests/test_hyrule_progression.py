from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter, deque
from pathlib import Path

from scripts.build_hyrule_area import (
    BOSS_MOBS,
    ENEMY_MOBS,
    GEAR_STAGES,
    SHOP_INVENTORY,
    SHOP_KEEPERS,
    choose_world_mob,
    build_area,
)
from webadmin.area_parser import AreaParser, ITEM_FLAGS, ROOM_FLAGS, decode_flags


OPPOSITE = {
    "north": "south",
    "east": "west",
    "south": "north",
    "west": "east",
}


class HyruleProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(Path("data/hyrule_first_quest.json").read_text(encoding="utf-8"))
        cls.parser = AreaParser(Path("area"))
        cls.parser.parse_all()
        cls.hyrule_rooms = {
            room.vnum: room
            for room in cls.parser.rooms.values()
            if room.area_file == "hyrule.are"
        }
        cls.world = {
            room["coordinate"]: room for room in cls.manifest["overworld"]["rooms"]
        }
        cls.dungeons = {
            dungeon["level"]: dungeon for dungeon in cls.manifest["dungeons"]
        }
        cls.resets = cls.parser.resets["hyrule.are"]
        cls.direct_object_sources = {
            reset.arg1
            for reset in cls.resets
            if reset.command in {"O", "G", "E"}
        }

    @classmethod
    def object_is_sourced(cls, object_vnum: int, seen: set[int] | None = None) -> bool:
        if object_vnum in cls.direct_object_sources:
            return True
        seen = set() if seen is None else seen
        if object_vnum in seen:
            return False
        obj = cls.parser.objects[object_vnum]
        return any(
            cls.object_is_sourced(container_vnum, seen | {object_vnum})
            for container_vnum in obj.contained_by
        )

    def test_manifest_has_complete_first_quest_geometry(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["overworld"]["columns"], 16)
        self.assertEqual(self.manifest["overworld"]["rows"], 8)
        self.assertEqual(self.manifest["overworld"]["start"], "H1")
        self.assertEqual(self.world["H1"]["vnum"], 30200)
        self.assertEqual(
            set(self.world),
            {f"{chr(ord('A') + column)}{row}" for column in range(16) for row in range(1, 9)},
        )
        self.assertEqual(
            [len(self.dungeons[level]["rooms"]) for level in range(1, 10)],
            [17, 18, 18, 20, 23, 25, 33, 25, 57],
        )
        self.assertEqual(
            [self.dungeons[level]["overworld_coordinate"] for level in range(1, 10)],
            ["H5", "M5", "E1", "F4", "L8", "C6", "C4", "N2", "F8"],
        )

    def test_overworld_exits_are_reciprocal_and_all_screens_are_reachable(self) -> None:
        for coordinate, room in self.world.items():
            for direction, exit_data in room["exits"].items():
                target = self.world[exit_data["to"]]
                with self.subTest(coordinate=coordinate, direction=direction):
                    self.assertEqual(
                        target["exits"][OPPOSITE[direction]]["to"],
                        coordinate,
                    )
                    self.assertEqual(
                        target["exits"][OPPOSITE[direction]]["gate"],
                        exit_data["gate"],
                    )

        reachable = {"H1"}
        pending = ["H1"]
        while pending:
            coordinate = pending.pop()
            for exit_data in self.world[coordinate]["exits"].values():
                if exit_data["to"] not in reachable:
                    reachable.add(exit_data["to"])
                    pending.append(exit_data["to"])
        self.assertEqual(reachable, set(self.world))

    def test_dungeon_manifest_edges_are_reciprocal_and_ranges_do_not_overlap(self) -> None:
        all_vnums: set[int] = set()
        for level, dungeon in self.dungeons.items():
            rooms = {room["coordinate"]: room for room in dungeon["rooms"]}
            dungeon_vnums = {
                room["vnum"] for room in dungeon["rooms"]
            } | {cellar["vnum"] for cellar in dungeon["cellars"]}
            with self.subTest(level=level, check="range"):
                self.assertEqual(
                    dungeon_vnums,
                    set(range(dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1)),
                )
                self.assertFalse(all_vnums & dungeon_vnums)
            all_vnums.update(dungeon_vnums)

            for coordinate, room in rooms.items():
                for direction, exit_data in room["exits"].items():
                    reverse = rooms[exit_data["to"]]["exits"][OPPOSITE[direction]]
                    with self.subTest(level=level, coordinate=coordinate, direction=direction):
                        self.assertEqual(reverse["to"], coordinate)
                        self.assertEqual(reverse["type"], exit_data["type"])

    def test_death_mountain_passages_match_the_lettered_map(self) -> None:
        self.assertEqual(
            {
                frozenset((link["from"], link["to"]))
                for link in self.dungeons[9]["stair_links"]
            },
            {
                frozenset(pair)
                for pair in (
                    ("E7", "F3"), ("F8", "D2"), ("B1", "E1"),
                    ("A6", "B2"), ("E8", "A5"), ("D8", "C3"),
                )
            },
        )

    def test_bomb_walls_match_the_first_quest_markers(self) -> None:
        expected_counts = [2, 5, 2, 4, 5, 3, 10, 6, 19]
        for level, expected_count in enumerate(expected_counts, start=1):
            walls = {
                frozenset((room["coordinate"], exit_data["to"]))
                for room in self.dungeons[level]["rooms"]
                for exit_data in room["exits"].values()
                if exit_data["type"] == "bombable"
            }
            with self.subTest(level=level):
                self.assertEqual(len(walls), expected_count)

        death_mountain_walls = {
            frozenset((room["coordinate"], exit_data["to"]))
            for room in self.dungeons[9]["rooms"]
            for exit_data in room["exits"].values()
            if exit_data["type"] == "bombable"
        }
        self.assertEqual(
            death_mountain_walls,
            {
                frozenset(pair)
                for pair in (
                    ("F2", "F3"), ("D3", "D4"), ("E3", "F3"),
                    ("F3", "F4"), ("F3", "G3"), ("A5", "B5"),
                    ("D5", "E5"), ("F5", "F6"), ("G5", "H5"),
                    ("H5", "H6"), ("A6", "A7"), ("B6", "C6"),
                    ("D6", "E6"), ("F6", "F7"), ("G6", "H6"),
                    ("H6", "H7"), ("H7", "H8"), ("D8", "E8"),
                    ("F8", "G8"),
                )
            },
        )

    def test_death_mountain_critical_route_has_canonical_encounters(self) -> None:
        rooms = {
            room["coordinate"]: room["entities"]
            for room in self.dungeons[9]["rooms"]
        }
        expected = {
            "G2": {"old_man": 1},
            "G3": {"bubble": 2, "like_like": 2, "zol": 2},
            "F3": {"red_lanmola": 2},
            "E7": {"like_like": 5},
            "F7": {"blue_wizzrobe": 3},
            "G7": {"patra": 1},
            "G6": {"gel": 8},
            "H6": {"patra": 1},
            "H8": {"blue_wizzrobe": 3, "bubble": 3, "red_wizzrobe": 2},
            "G8": {"old_man": 1},
            "D2": {"zol": 5},
            "C2": {"keese": 8},
            "B2": {"patra": 1},
            "B3": {"like_like": 6},
            "A3": {"zol": 5},
            "C3": {"patra": 1},
            "C4": {"ganon": 1},
            "C5": {"princess_zelda": 1},
        }
        for coordinate, roster in expected.items():
            with self.subTest(coordinate=coordinate):
                self.assertEqual(rooms[coordinate], roster)

    def test_every_manifest_room_exists_and_every_hyrule_room_blocks_recall(self) -> None:
        canonical_vnums = {room["vnum"] for room in self.world.values()}
        for dungeon in self.dungeons.values():
            canonical_vnums.update(room["vnum"] for room in dungeon["rooms"])
            canonical_vnums.update(cellar["vnum"] for cellar in dungeon["cellars"])
        self.assertTrue(canonical_vnums.issubset(self.hyrule_rooms))

        for room in self.hyrule_rooms.values():
            with self.subTest(room_vnum=room.vnum):
                self.assertIn("no_recall", decode_flags(room.room_flags, ROOM_FLAGS))

    def test_overworld_and_dungeon_reset_counts_match_the_manifest(self) -> None:
        expected: Counter[tuple[int, int]] = Counter()
        for room in self.world.values():
            for entity, count in room["entities"].items():
                mob_vnum = choose_world_mob(entity, room["recommended_level"])
                if mob_vnum is not None:
                    expected[(room["vnum"], mob_vnum)] += count

        for dungeon in self.dungeons.values():
            for room in dungeon["rooms"]:
                if room["role"] == "boss":
                    expected[(room["vnum"], BOSS_MOBS[dungeon["level"]])] = 1
                    continue
                for entity, count in room["entities"].items():
                    if entity in ENEMY_MOBS:
                        expected[(room["vnum"], ENEMY_MOBS[entity])] += count

        canonical_rooms = {
            room["vnum"] for room in self.world.values()
        } | {
            room["vnum"]
            for dungeon in self.dungeons.values()
            for room in dungeon["rooms"]
        }
        actual = Counter(
            (reset.arg3, reset.arg1)
            for reset in self.resets
            if reset.command == "M" and reset.arg3 in canonical_rooms
        )
        self.assertEqual(actual, expected)

    def test_every_dungeon_goal_is_reachable_with_keys_found_on_its_floor(self) -> None:
        for level, dungeon in self.dungeons.items():
            rooms = {room["coordinate"]: room for room in dungeon["rooms"]}
            stair_routes: dict[str, list[str]] = {}
            for link in dungeon["stair_links"]:
                stair_routes.setdefault(link["from"], []).append(link["to"])
                stair_routes.setdefault(link["to"], []).append(link["from"])
            key_rooms = {
                coordinate: index
                for index, (coordinate, room) in enumerate(rooms.items())
                if 30227 in room["items"]
            }
            start = (dungeon["entrance_coordinate"], 0, 0)
            pending = deque([start])
            seen = {start}
            reached = False
            while pending:
                coordinate, keys, collected = pending.popleft()
                if coordinate in key_rooms:
                    bit = 1 << key_rooms[coordinate]
                    if not collected & bit:
                        keys += rooms[coordinate]["items"].count(30227)
                        collected |= bit
                if coordinate == dungeon["goal_coordinate"]:
                    reached = True
                    break
                for exit_data in rooms[coordinate]["exits"].values():
                    cost = int(exit_data["type"] == "locked")
                    state = (exit_data["to"], keys - cost, collected)
                    if keys >= cost and state not in seen:
                        seen.add(state)
                        pending.append(state)
                for destination in stair_routes.get(coordinate, []):
                    state = (destination, keys, collected)
                    if state not in seen:
                        seen.add(state)
                        pending.append(state)
            with self.subTest(level=level):
                self.assertTrue(reached)

    def test_maps_and_compasses_use_generated_ranges_and_are_sourced(self) -> None:
        for level, dungeon in self.dungeons.items():
            expected_values = [
                str(dungeon["boss_vnum"]),
                str(dungeon["first_room_vnum"]),
                str(dungeon["last_room_vnum"]),
                str(level),
            ]
            map_object = self.parser.objects[dungeon["map_vnum"]]
            compass_object = self.parser.objects[dungeon["compass_vnum"]]
            map_room = next(
                room for room in dungeon["rooms"] if room["coordinate"] == dungeon["map_coordinate"]
            )
            compass_room = next(
                room for room in dungeon["rooms"] if room["coordinate"] == dungeon["compass_coordinate"]
            )
            with self.subTest(level=level, item="map"):
                self.assertEqual(map_object.values, ["90", *expected_values])
                self.assertIn(dungeon["map_vnum"], self.parser.rooms[map_room["vnum"]].objects)
                self.assertTrue(map_object.extra_descr)
            with self.subTest(level=level, item="compass"):
                self.assertEqual(compass_object.values, ["91", *expected_values])
                self.assertIn(dungeon["compass_vnum"], self.parser.rooms[compass_room["vnum"]].objects)

    def test_major_items_are_in_their_canonical_rooms(self) -> None:
        direct_items = {(1, "D4"): 30232, (2, "D4"): 30410}
        for (level, coordinate), object_vnum in direct_items.items():
            room = next(
                room for room in self.dungeons[level]["rooms"] if room["coordinate"] == coordinate
            )
            self.assertIn(object_vnum, self.parser.rooms[room["vnum"]].objects)

        expected_cellar_items = {
            1: {30222}, 3: {30411}, 4: {30412}, 5: {30413},
            6: {30245}, 7: {30414}, 8: {30415, 30416}, 9: {30218, 30261},
        }
        for level, object_vnums in expected_cellar_items.items():
            actual = {cellar["item_vnum"] for cellar in self.dungeons[level]["cellars"]}
            with self.subTest(level=level):
                self.assertEqual(actual, object_vnums)
                for cellar in self.dungeons[level]["cellars"]:
                    self.assertIn(
                        cellar["item_vnum"],
                        self.parser.rooms[cellar["vnum"]].objects,
                    )

    def test_gear_for_every_level_is_sourced_in_its_stage(self) -> None:
        sourced_levels = {
            obj.level
            for obj in self.parser.objects.values()
            if obj.area_file == "hyrule.are"
            and obj.item_type in {"5", "9"}
            and self.object_is_sourced(obj.vnum)
        }
        self.assertEqual(set(range(1, 71)) - sourced_levels, set())

        for stage, (chest_vnum, gear_vnums) in GEAR_STAGES.items():
            with self.subTest(stage=stage):
                self.assertTrue(self.object_is_sourced(chest_vnum))
                self.assertEqual(
                    set(gear_vnums),
                    {
                        obj.vnum
                        for obj in self.parser.objects.values()
                        if chest_vnum in obj.contained_by
                    },
                )

        master_sword = self.parser.objects[30200]
        self.assertEqual(master_sword.level, 58)
        self.assertTrue(self.object_is_sourced(30200))

    def test_canonical_world_secrets_and_return_paths_are_sourced(self) -> None:
        coordinate_objects = {
            coordinate: set(self.parser.rooms[room["vnum"]].objects)
            for coordinate, room in self.world.items()
        }
        self.assertIn(30514, coordinate_objects["E6"])
        self.assertIn(30539, coordinate_objects["P6"])
        self.assertIn(30540, coordinate_objects["P3"])
        self.assertIn(30507, coordinate_objects["C4"])
        self.assertIn(30506, coordinate_objects["N2"])
        self.assertIn(30509, coordinate_objects["F8"])
        for puzzle_vnum in range(30502, 30510):
            with self.subTest(puzzle_vnum=puzzle_vnum):
                self.assertEqual(self.parser.objects[puzzle_vnum].values[4], "9")
        for puzzle_vnum in (30513, 30514, 30564):
            with self.subTest(puzzle_vnum=puzzle_vnum):
                self.assertEqual(self.parser.objects[puzzle_vnum].values[4], "9")

        canonical_caves = {
            "K8": (30651, 30251),
            "B6": (30652, 30200),
            "O8": (30653, 30500),
            "E6": (30674, 30276),
        }
        for coordinate, (cave_vnum, object_vnum) in canonical_caves.items():
            with self.subTest(coordinate=coordinate):
                self.assertTrue(any(
                    exit_data.to_room == cave_vnum
                    for exit_data in self.parser.rooms[self.world[coordinate]["vnum"]].exits
                ))
                self.assertIn(object_vnum, self.parser.rooms[cave_vnum].objects)

        expected_rupees = {
            "B3": (10, "burn"), "B1": (30, "bomb"),
            "C2": (100, "burn"), "D7": (30, "bomb"),
            "G3": (10, "burn"), "H2": (30, "bomb"),
            "I6": (30, "burn"), "I4": (30, "burn"),
            "L3": (10, "burn"), "L2": (100, "burn"),
            "N6": (30, "bomb"), "N5": (30, "armos"),
            "O4": (10, "armos"), "P8": (100, None),
        }
        money_vnums = {10: 30510, 30: 30511, 100: 30512}
        for coordinate, (amount, puzzle) in expected_rupees.items():
            landmark = next(
                item for item in self.world[coordinate]["landmarks"]
                if item["type"] == "rupee"
            )
            with self.subTest(coordinate=coordinate):
                self.assertEqual(landmark.get("puzzle"), puzzle)
                self.assertIn(
                    money_vnums[amount],
                    self.parser.rooms[landmark["room_vnum"]].objects,
                )

        self.assertIn(30211, self.parser.rooms[30659].objects)
        self.assertEqual(self.parser.objects[30211].values[1], "15068")
        level_nine_goal = self.dungeons[9]["goal_vnum"]
        self.assertIn(30217, self.parser.rooms[level_nine_goal].objects)
        self.assertIn(30286, self.parser.rooms[level_nine_goal].objects)
        self.assertEqual(self.parser.objects[30217].values[1], "15068")
        self.assertEqual(self.manifest["post_ganon"]["vnum"], level_nine_goal)

    def test_all_first_quest_shops_have_canonical_locations_and_stock(self) -> None:
        expected_locations = {
            "regular_bomb": {"E4", "F6", "K4", "P2"},
            "regular_candle": {"G2", "M8", "O3"},
            "deluxe_shield": {"C7", "G6", "G4", "N4"},
            "deluxe_ring": {"E5"},
            "potion": {"D5", "E8", "E2", "H6", "I1", "L4", "N8"},
        }
        services = [
            (coordinate, landmark)
            for coordinate, room in self.world.items()
            for landmark in room["landmarks"]
            if landmark["type"] in {"shop", "potion_shop"}
        ]
        self.assertEqual(len(services), 19)

        for shop_kind, coordinates in expected_locations.items():
            actual = {
                coordinate
                for coordinate, landmark in services
                if landmark["shop_kind"] == shop_kind
            }
            with self.subTest(shop_kind=shop_kind):
                self.assertEqual(actual, coordinates)

        puzzle_objects = {"bomb": 30509, "burn": 30506, "armos": 30514}
        for coordinate, landmark in services:
            shop_vnum = landmark["room_vnum"]
            keeper_vnum = SHOP_KEEPERS[landmark["shop_kind"]]
            world_room = self.parser.rooms[self.world[coordinate]["vnum"]]
            direction = landmark.get("direction", "down")
            with self.subTest(coordinate=coordinate, shop_kind=landmark["shop_kind"]):
                self.assertIn(shop_vnum, self.hyrule_rooms)
                self.assertIn(shop_vnum, self.parser.mobiles[keeper_vnum].spawn_rooms)
                self.assertTrue(any(
                    exit_data.to_room == shop_vnum
                    and exit_data.direction == {"up": 4, "down": 5}[direction]
                    for exit_data in world_room.exits
                ))
                puzzle = landmark.get("puzzle")
                if puzzle:
                    self.assertIn(puzzle_objects[puzzle], world_room.objects)

        expected_prices = {
            30541: 130, 30542: 20, 30543: 80,
            30544: 160, 30545: 100, 30546: 60,
            30547: 90, 30548: 100, 30549: 10,
            30550: 80, 30551: 250, 30552: 60,
            30553: 40, 30554: 68,
        }
        for keeper_vnum, inventory in SHOP_INVENTORY.items():
            with self.subTest(keeper_vnum=keeper_vnum):
                self.assertTrue(set(inventory).issubset(self.parser.mobiles[keeper_vnum].drops))
            for object_vnum in inventory:
                with self.subTest(object_vnum=object_vnum):
                    obj = self.parser.objects[object_vnum]
                    self.assertEqual(obj.cost, expected_prices[object_vnum])
                    self.assertIn("inventory", decode_flags(obj.extra_flags, ITEM_FLAGS))
                    self.assertTrue(self.object_is_sourced(object_vnum))

        shop_section = Path("area/hyrule.are").read_text(encoding="utf-8").split("#SHOPS", 1)[1]
        shop_keepers = {
            int(line.split()[0])
            for line in shop_section.splitlines()
            if line and line.split()[0].isdigit() and int(line.split()[0])
        }
        self.assertEqual(shop_keepers, set(SHOP_INVENTORY))
        self.assertTrue({30226, 30227, 30228}.isdisjoint(shop_keepers))

        runtime = Path("src/act_obj.c").read_text(encoding="utf-8")
        self.assertIn("HYRULE_POTION_KEEPER_VNUM 30343", runtime)
        self.assertIn("HYRULE_LETTER_VNUM        30500", runtime)

    def test_door_repairs_gambling_and_warp_halls_match_first_quest(self) -> None:
        expected_repairs = {
            "B8": "bomb", "D8": "bomb", "D2": "burn",
            "E7": "bomb", "H8": "bomb", "I2": "burn",
            "K2": "burn", "N1": "bomb", "O7": "bomb",
        }
        expected_gambling = {
            "A7": "bomb", "G7": "bomb", "G1": "bomb",
            "M1": "bomb", "P7": None,
        }
        expected_warps = {
            "D6": ["J4", "J1", "N7"],
            "J4": ["J1", "N7", "D6"],
            "J1": ["N7", "D6", "J4"],
            "N7": ["D6", "J4", "J1"],
        }
        puzzle_objects = {"bomb": 30509, "burn": 30506, "bracelet": 30564}

        for coordinate, puzzle in expected_repairs.items():
            landmark = next(
                item for item in self.world[coordinate]["landmarks"]
                if item["type"] == "door_repair"
            )
            world_room = self.parser.rooms[self.world[coordinate]["vnum"]]
            with self.subTest(kind="repair", coordinate=coordinate):
                self.assertEqual(landmark["puzzle"], puzzle)
                self.assertIn(puzzle_objects[puzzle], world_room.objects)
                self.assertIn(30344, [
                    mobile_vnum
                    for mobile_vnum, mobile in self.parser.mobiles.items()
                    if landmark["room_vnum"] in mobile.spawn_rooms
                ])
                self.assertIn(landmark["token_vnum"], self.parser.objects)

        for coordinate, puzzle in expected_gambling.items():
            landmark = next(
                item for item in self.world[coordinate]["landmarks"]
                if item["type"] == "gamble"
            )
            world_room = self.parser.rooms[self.world[coordinate]["vnum"]]
            with self.subTest(kind="gamble", coordinate=coordinate):
                self.assertEqual(landmark.get("puzzle"), puzzle)
                if puzzle:
                    self.assertIn(puzzle_objects[puzzle], world_room.objects)
                self.assertIn(landmark["room_vnum"], self.parser.mobiles[30345].spawn_rooms)

        for coordinate, destinations in expected_warps.items():
            landmark = next(
                item for item in self.world[coordinate]["landmarks"]
                if item["type"] == "warp_hall"
            )
            hall = self.parser.rooms[landmark["room_vnum"]]
            with self.subTest(kind="warp", coordinate=coordinate):
                self.assertEqual(
                    [route["destination"] for route in landmark["routes"]],
                    destinations,
                )
                self.assertIn(30564, self.parser.rooms[self.world[coordinate]["vnum"]].objects)
                self.assertEqual(set(hall.objects), {
                    route["object_vnum"] for route in landmark["routes"]
                })
                for route in landmark["routes"]:
                    portal = self.parser.objects[route["object_vnum"]]
                    self.assertEqual(portal.item_type, "30")
                    self.assertEqual(
                        portal.values[1],
                        str(self.world[route["destination"]]["vnum"]),
                    )
                    self.assertEqual(portal.values[4], "30276")

        act_obj = Path("src/act_obj.c").read_text(encoding="utf-8")
        act_move = Path("src/act_move.c").read_text(encoding="utf-8")
        interp = Path("src/interp.c").read_text(encoding="utf-8")
        self.assertIn("void do_gamble", act_obj)
        self.assertIn("obj->pIndexData->vnum == 30564", act_obj)
        self.assertIn("charge_hyrule_door_repair", act_move)
        self.assertIn('{ "gamble",', interp)

    def test_ganon_drops_the_key_to_zelda_and_the_triforce(self) -> None:
        level_nine = self.dungeons[9]
        ganon = self.parser.mobiles[30225]
        self.assertIn(level_nine["boss_vnum"], ganon.spawn_rooms)
        self.assertIn(30243, ganon.drops)
        boss_room = self.parser.rooms[level_nine["boss_vnum"]]
        golden_exit = next(
            exit_data for exit_data in boss_room.exits if exit_data.to_room == level_nine["goal_vnum"]
        )
        self.assertEqual(golden_exit.key_vnum, 30243)
        self.assertNotEqual(golden_exit.locks, 0)

    def test_silver_arrow_explains_how_to_finish_ganon(self) -> None:
        silver_arrow = self.parser.objects[30218]
        guidance = " ".join(
            description["description"] for description in silver_arrow.extra_descr
            if "silver" in description["keyword"].lower()
        ).lower()
        self.assertIn("primary weapon slot", guidance)
        self.assertIn("final blow", guidance)
        self.assertIn("not ammunition", guidance)
        fight_source = Path("src/fight.c").read_text(encoding="utf-8").lower()
        self.assertIn("wield the silver arrow for the final blow", fight_source)

    def test_hyrule_has_teleport_only_entry_and_no_walking_world_link(self) -> None:
        arcade = self.parser.objects[30285]
        self.assertEqual(arcade.values[1], "30200")
        self.assertIn(30285, self.parser.rooms[15068].objects)

        for room in self.hyrule_rooms.values():
            for exit_data in room.exits:
                with self.subTest(room_vnum=room.vnum, destination=exit_data.to_room):
                    self.assertIn(exit_data.to_room, self.hyrule_rooms)

    def test_death_mountain_requires_bombs_and_all_eight_triforce_shards(self) -> None:
        world_room = self.parser.rooms[self.world["F8"]["vnum"]]
        entrance_vnum = self.dungeons[9]["entrance_vnum"]
        entrance = next(
            exit_data for exit_data in world_room.exits
            if exit_data.to_room == entrance_vnum
        )
        self.assertIn("bomb", entrance.keyword)
        self.assertIn("triforce", entrance.keyword)
        self.assertNotEqual(entrance.locks, 0)

        for shard_vnum in range(30400, 30408):
            with self.subTest(shard_vnum=shard_vnum):
                self.assertTrue(self.object_is_sourced(shard_vnum))

    def test_every_hyrule_room_is_reachable_and_can_return_to_campus(self) -> None:
        routes = {room_vnum: set() for room_vnum in self.hyrule_rooms}
        external_exit_rooms = set()
        for room_vnum, room in self.hyrule_rooms.items():
            destinations = {exit_data.to_room for exit_data in room.exits}
            if room.teleport_to_room is not None:
                destinations.add(room.teleport_to_room)
            for object_vnum in room.objects:
                obj = self.parser.objects.get(object_vnum)
                if obj is None or len(obj.values) < 2:
                    continue
                if obj.item_type == "30" or (
                    obj.item_type == "31" and int(obj.values[0]) in range(6, 10)
                ):
                    destinations.add(int(obj.values[1]))
            routes[room_vnum].update(destinations & self.hyrule_rooms.keys())
            if destinations - self.hyrule_rooms.keys():
                external_exit_rooms.add(room_vnum)

        reachable = {30200}
        pending = [30200]
        while pending:
            room_vnum = pending.pop()
            for destination in routes[room_vnum]:
                if destination not in reachable:
                    reachable.add(destination)
                    pending.append(destination)
        self.assertEqual(reachable, set(self.hyrule_rooms))

        can_escape = set(external_exit_rooms)
        changed = True
        while changed:
            changed = False
            for room_vnum, destinations in routes.items():
                if room_vnum not in can_escape and destinations & can_escape:
                    can_escape.add(room_vnum)
                    changed = True
        self.assertEqual(can_escape, set(self.hyrule_rooms))

    def test_door_resets_only_target_real_doors(self) -> None:
        for reset in self.resets:
            if reset.command != "D":
                continue
            room = self.parser.rooms[reset.arg1]
            exit_data = next(
                (item for item in room.exits if item.direction == reset.arg2),
                None,
            )
            with self.subTest(room_vnum=room.vnum, direction=reset.arg2):
                self.assertIsNotNone(exit_data)
                self.assertNotEqual(exit_data.locks, 0)
                self.assertIn(reset.arg3, range(6))

    def test_area_generator_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            generated = Path(temporary_directory) / "hyrule.are"
            shutil.copy2("area/hyrule.are", generated)
            build_area(Path("data/hyrule_first_quest.json").resolve(), generated)
            first = generated.read_bytes()
            build_area(Path("data/hyrule_first_quest.json").resolve(), generated)
            self.assertEqual(generated.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
