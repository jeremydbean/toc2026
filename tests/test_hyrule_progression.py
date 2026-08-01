from __future__ import annotations

import unittest
from pathlib import Path

from webadmin.area_parser import AreaParser


class HyruleProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = AreaParser(Path("area"))
        cls.parser.parse_all()
        cls.hyrule_rooms = {
            room.vnum: room
            for room in cls.parser.rooms.values()
            if room.area_file == "hyrule.are"
        }

        cls.direct_object_sources = {
            object_vnum
            for room in cls.hyrule_rooms.values()
            for object_vnum in room.objects
        }
        for mobile in cls.parser.mobiles.values():
            if any(room in cls.hyrule_rooms for room in mobile.spawn_rooms):
                cls.direct_object_sources.update(mobile.drops)

    @classmethod
    def object_is_sourced(cls, object_vnum: int, seen: set[int] | None = None) -> bool:
        if object_vnum in cls.direct_object_sources:
            return True

        seen = set() if seen is None else seen
        if object_vnum in seen:
            return False
        seen.add(object_vnum)

        obj = cls.parser.objects[object_vnum]
        return any(
            cls.object_is_sourced(container_vnum, seen)
            for container_vnum in obj.contained_by
        )

    def test_every_level_from_one_through_seventy_has_sourced_gear(self) -> None:
        sourced_gear_levels = {
            obj.level
            for obj in self.parser.objects.values()
            if obj.area_file == "hyrule.are"
            and obj.item_type in {"5", "9"}
            and self.object_is_sourced(obj.vnum)
        }

        self.assertEqual(set(range(1, 71)) - sourced_gear_levels, set())

    def test_gear_is_staged_in_the_matching_dungeon_band(self) -> None:
        chest_levels = {
            30440: range(1, 11),
            30441: range(11, 19),
            30443: range(21, 29),
            30445: range(31, 39),
            30447: range(41, 49),
            30449: range(51, 54),
            30451: range(56, 58),
            30453: range(61, 63),
            30455: range(65, 67),
        }

        for chest_vnum, expected_levels in chest_levels.items():
            actual_levels = {
                obj.level
                for obj in self.parser.objects.values()
                if obj.item_type in {"5", "9"}
                and chest_vnum in obj.contained_by
            }
            with self.subTest(chest_vnum=chest_vnum):
                self.assertTrue(set(expected_levels).issubset(actual_levels))

    def test_bosses_guard_the_top_of_each_level_band(self) -> None:
        bosses = {
            30222: (30353, {30234, 30338, 30339}),
            30218: (30376, {30248, 30348, 30349}),
            30305: (30613, {30460, 30358, 30359}),
            30307: (30633, {30461, 30368, 30369}),
            30309: (30653, {30462, 30373, 30374}),
            30223: (30673, {30463, 30377, 30378}),
            30314: (30693, {30464, 30381, 30382}),
            30316: (30713, {30465, 30385}),
            30225: (30436, {30243, 30244, 30388}),
        }

        for mobile_vnum, (room_vnum, rewards) in bosses.items():
            mobile = self.parser.mobiles[mobile_vnum]
            with self.subTest(mobile_vnum=mobile_vnum):
                self.assertIn(room_vnum, mobile.spawn_rooms)
                self.assertTrue(rewards.issubset(set(mobile.drops)))

    def test_all_nine_dungeons_and_canonical_items_are_present(self) -> None:
        entries = {
            30339: "Level 1: The Eagle",
            30355: "Level 2: The Moon",
            30600: "Level 3 - The Manji",
            30620: "Level 4 - The Snake",
            30640: "Level 5 - The Lizard",
            30660: "Level 6 - The Dragon",
            30680: "Level 7 - The Demon",
            30700: "Level 8 - The Lion",
            30378: "Level 9: Death Mountain",
        }
        for room_vnum, expected_name in entries.items():
            with self.subTest(room_vnum=room_vnum):
                self.assertIn(expected_name, self.parser.rooms[room_vnum].name)

        item_containers = {
            30410: 30443,  # Magical Boomerang, Level 2
            30411: 30445,  # Raft, Level 3
            30412: 30447,  # Stepladder, Level 4
            30413: 30449,  # Recorder, Level 5
            30414: 30453,  # Red Candle, Level 7
            30415: 30455,  # Magic Book, Level 8
            30416: 30455,  # Magical Key, Level 8
            30218: 30237,  # Silver Arrow, Level 9
            30261: 30260,  # Red Ring, Level 9
        }
        for object_vnum, container_vnum in item_containers.items():
            with self.subTest(object_vnum=object_vnum):
                self.assertIn(container_vnum, self.parser.objects[object_vnum].contained_by)

        master_sword = self.parser.objects[30200]
        self.assertEqual(master_sword.level, 58)
        self.assertIn(30235, master_sword.contained_by)
        self.assertEqual(self.parser.objects[30235].values[2], "30405")

    def test_each_dungeon_has_its_own_map_and_compass(self) -> None:
        dungeon_items = {
            1: (30480, 30347, 30489, 30344, 30353, 30339, 30354),
            2: (30481, 30362, 30490, 30369, 30376, 30355, 30377),
            3: (30482, 30611, 30491, 30602, 30613, 30600, 30614),
            4: (30483, 30631, 30492, 30622, 30633, 30620, 30634),
            5: (30484, 30651, 30493, 30645, 30653, 30640, 30654),
            6: (30485, 30670, 30494, 30663, 30673, 30660, 30674),
            7: (30486, 30683, 30495, 30692, 30693, 30680, 30694),
            8: (30487, 30706, 30496, 30712, 30713, 30700, 30714),
            9: (30488, 30400, 30497, 30398, 30436, 30378, 30437),
        }

        for level, (
            map_vnum,
            map_room,
            compass_vnum,
            compass_room,
            boss_room,
            first_room,
            last_room,
        ) in dungeon_items.items():
            dungeon_map = self.parser.objects[map_vnum]
            compass = self.parser.objects[compass_vnum]
            expected_path = [str(boss_room), str(first_room), str(last_room), str(level)]

            with self.subTest(level=level, item="map"):
                self.assertEqual(dungeon_map.item_type, "28")
                self.assertEqual(dungeon_map.values, ["90", *expected_path])
                self.assertIn(map_vnum, self.parser.rooms[map_room].objects)
                self.assertTrue(
                    any("map" in description["keyword"].split()
                        for description in dungeon_map.extra_descr)
                )

            with self.subTest(level=level, item="compass"):
                self.assertEqual(compass.item_type, "28")
                self.assertEqual(compass.values, ["91", *expected_path])
                self.assertIn(compass_vnum, self.parser.rooms[compass_room].objects)

        self.assertNotIn(30418, self.parser.objects)
        self.assertNotIn(30419, self.parser.objects)

    def test_compass_can_route_to_each_boss_from_nonlethal_rooms(self) -> None:
        for compass_vnum in range(30489, 30498):
            compass = self.parser.objects[compass_vnum]
            boss_room, first_room, last_room, level = map(int, compass.values[1:])
            dungeon_rooms = {
                room_vnum
                for room_vnum in self.hyrule_rooms
                if first_room <= room_vnum <= last_room
            }
            routes = {
                room_vnum: {
                    exit_data.to_room
                    for exit_data in self.parser.rooms[room_vnum].exits
                    if exit_data.to_room in dungeon_rooms
                }
                for room_vnum in dungeon_rooms
            }

            for room_vnum in dungeon_rooms:
                for object_vnum in self.parser.rooms[room_vnum].objects:
                    obj = self.parser.objects.get(object_vnum)
                    if obj is None:
                        continue
                    if obj.item_type == "30" or (
                        obj.item_type == "31" and int(obj.values[0]) in {6, 7}
                    ):
                        destination = int(obj.values[1])
                        if destination in dungeon_rooms:
                            routes[room_vnum].add(destination)

            can_reach_boss = {boss_room}
            changed = True
            while changed:
                changed = False
                for room_vnum, destinations in routes.items():
                    if room_vnum not in can_reach_boss and destinations & can_reach_boss:
                        can_reach_boss.add(room_vnum)
                        changed = True

            lethal_teleports = {
                room_vnum
                for room_vnum in dungeon_rooms
                if self.parser.rooms[room_vnum].teleport_to_room is not None
                and self.parser.rooms[room_vnum].teleport_to_room not in dungeon_rooms
            }
            with self.subTest(level=level):
                self.assertEqual(
                    dungeon_rooms - can_reach_boss - lethal_teleports,
                    set(),
                )

    def test_shards_and_data_driven_puzzles_have_sources(self) -> None:
        for shard_vnum in range(30400, 30408):
            with self.subTest(shard_vnum=shard_vnum):
                self.assertTrue(self.object_is_sourced(shard_vnum))

        puzzle_sources = {
            30420: (11, 30204),
            30421: (11, 30254),
            30422: (11, 30295),
            30423: (12, 30323),
            30424: (12, 30343),
            30426: (12, 30360),
            30429: (12, 30644),
            30430: (13, 30653),
            30431: (12, 30665),
            30432: (13, 30238),
            30433: (13, 30684),
            30434: (14, 30687),
            30435: (12, 30690),
            30438: (12, 30709),
        }
        for object_vnum, (puzzle_type, source_room) in puzzle_sources.items():
            obj = self.parser.objects[object_vnum]
            with self.subTest(object_vnum=object_vnum):
                self.assertEqual(int(obj.values[0]), puzzle_type)
                self.assertIn(object_vnum, self.parser.rooms[source_room].objects)

    def test_hyrule_specials_section_is_loaded(self) -> None:
        expected_specials = {
            30222: "spec_breath_fire",
            30225: "spec_cast_necro",
            30307: "spec_breath_fire",
            30310: "spec_cast_mage",
            30314: "spec_breath_fire",
            30316: "spec_breath_fire",
            30332: "spec_breath_acid",
            30334: "spec_cast_mage",
        }
        for mobile_vnum, special in expected_specials.items():
            with self.subTest(mobile_vnum=mobile_vnum):
                self.assertEqual(self.parser.mob_specials.get(mobile_vnum), special)

    def test_door_resets_only_target_real_doors(self) -> None:
        for reset in self.parser.resets["hyrule.are"]:
            if reset.command != "D":
                continue
            room = self.parser.rooms[reset.arg1]
            matching_exit = next(
                (exit_data for exit_data in room.exits if exit_data.direction == reset.arg2),
                None,
            )
            with self.subTest(room_vnum=room.vnum, direction=reset.arg2):
                self.assertIsNotNone(matching_exit)
                self.assertNotEqual(matching_exit.locks, 0)
                self.assertIn(reset.arg3, range(6))

    def test_every_hyrule_room_is_reachable_when_puzzles_are_solved(self) -> None:
        reachable = {30200}
        pending = [30200]

        while pending:
            room_vnum = pending.pop()
            room = self.hyrule_rooms[room_vnum]
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

            for destination in destinations & self.hyrule_rooms.keys():
                if destination not in reachable:
                    reachable.add(destination)
                    pending.append(destination)

        self.assertEqual(set(self.hyrule_rooms) - reachable, set())


if __name__ == "__main__":
    unittest.main()
