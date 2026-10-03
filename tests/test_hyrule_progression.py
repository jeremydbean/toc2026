from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from collections import Counter, deque
from pathlib import Path

from scripts.build_hyrule_area import (
    BOSS_GEAR,
    BOSS_HEART_CONTAINER_FIRST,
    BOSS_KEYS,
    BOSS_MOBS,
    BOSS_SPECIALS,
    BOSS_VOLLEYS,
    CHESTS,
    DUNGEON_TREASURE,
    ENTRY_NEEDS,
    GUARDIAN_ALSO,
    GUARDIAN_NEEDS,
    PIECE_VNUMS,
    DROP_CLOCK_FIRST,
    DROP_FAIRY_FIRST,
    DROP_HEART_FIRST,
    GANON_ARMOR,
    GANON_VNUM,
    MASTER_SWORD_BASELINES,
    MASTER_SWORD_VNUM,
    master_sword_score,
    BOSS_STATS,
    BOSS_WEAPON_BASELINES,
    BOSS_WEAPONS,
    ENEMY_TYPES,
    GEAR_STAGES,
    NPC_MOBS,
    ROOM_ENEMY_CAP,
    SHOP_INVENTORY,
    SHOP_KEEPERS,
    TIER_VNUM_FIRST,
    TIER_VNUM_LAST,
    band_index,
    build_area,
    dungeon_spawns,
    manifest_bands,
    weapon_score,
    world_spawns,
)
from webadmin.area_parser import (
    AreaParser,
    ITEM_FLAGS,
    ROOM_FLAGS,
    ROOM_FLAGS2,
    VULN_FLAGS,
    decode_flags,
)


OPPOSITE = {
    "north": "south",
    "east": "west",
    "south": "north",
    "west": "east",
}


# merc.h: obj->cost is copper, and Hyrule quotes itself in rupees.
COPPER_PER_GOLD = 10000


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

    def test_every_manifest_room_exists_and_only_dungeons_block_recall(self) -> None:
        canonical_vnums = {room["vnum"] for room in self.world.values()}
        for dungeon in self.dungeons.values():
            canonical_vnums.update(room["vnum"] for room in dungeon["rooms"])
            canonical_vnums.update(cellar["vnum"] for cellar in dungeon["cellars"])
        self.assertTrue(canonical_vnums.issubset(self.hyrule_rooms))

        # Hyrule once held everyone: every room carried ROOM_NO_RECALL and
        # nothing in the world exited into it, so it was a place staff
        # could visit and nobody could leave. The arcade cabinet is the way
        # in now, and only the dungeons keep the flag -- walking out of
        # Level 7 by saying a word is the opposite of what a dungeon is
        # for. The overworld, sword caves, shops, repair rooms, money
        # games, warp halls and the Lost Woods all let you recall away.
        dungeon_vnums = set()
        for dungeon in self.dungeons.values():
            dungeon_vnums.update(range(dungeon["first_room_vnum"],
                                       dungeon["last_room_vnum"] + 1))

        blocking = {vnum for vnum, room in self.hyrule_rooms.items()
                    if "no_recall" in decode_flags(room.room_flags, ROOM_FLAGS)}

        # One assertion rather than one per room: a wrong expectation here
        # used to print 197 near-identical failures and bury the reason.
        self.assertEqual(
            sorted(dungeon_vnums & set(self.hyrule_rooms)), sorted(blocking),
            "only the dungeon rooms should stop a player recalling out")

    def test_the_overworld_is_lit_after_sunset(self) -> None:
        """Field, forest, hills, mountain and desert black out at night.

        The overworld is not flagged dark, but room_is_dark blacks those
        sectors out at sunset, which left half of every day unreadable.
        ROOM2_ALWAYS_LIT is checked after ROOM_DARK and answers for it.
        """
        dungeon_vnums = set()
        for dungeon in self.dungeons.values():
            dungeon_vnums.update(range(dungeon["first_room_vnum"],
                                       dungeon["last_room_vnum"] + 1))

        nightfall_sectors = {2, 3, 4, 5, 10}   # field forest hills mountain desert
        unlit = sorted(
            vnum for vnum, room in self.hyrule_rooms.items()
            if vnum not in dungeon_vnums
            and int(room.sector_type) in nightfall_sectors
            and "always_lit" not in decode_flags(room.room_flags2, ROOM_FLAGS2)
        )
        self.assertEqual([], unlit,
                         "these overworld rooms go dark at sunset")

    def test_overworld_and_dungeon_reset_counts_match_the_manifest(self) -> None:
        bands = manifest_bands(self.manifest)
        expected: Counter[tuple[int, int]] = Counter()
        for room in self.world.values():
            for mob_vnum, count in world_spawns(room, bands).items():
                expected[(room["vnum"], mob_vnum)] += count

        for dungeon in self.dungeons.values():
            for room in dungeon["rooms"]:
                for mob_vnum, count in dungeon_spawns(dungeon["level"], room).items():
                    expected[(room["vnum"], mob_vnum)] += count

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

    def test_crowded_rooms_keep_their_kinds_with_fewer_of_each(self) -> None:
        """The NES room's cast, not its crowd.

        Death Mountain alone asked for 254 mobiles -- eight keese here, six
        like likes there -- and every one is a full fight in the MUD. A room
        keeps every kind of enemy its NES room shows, never more of any kind
        than the NES had, and no more than ROOM_ENEMY_CAP in all unless it
        has more kinds than that.
        """
        kind_of = {
            TIER_VNUM_FIRST + enemy.code * 10 + band - 1: kind
            for kind, enemy in ENEMY_TYPES.items()
            for band in range(1, 10)
        }
        problems = []
        for level, dungeon in self.dungeons.items():
            for room in dungeon["rooms"]:
                if room["role"] == "boss":
                    continue
                spawned = Counter()
                for reset in self.resets:
                    if reset.command == "M" and reset.arg3 == room["vnum"] and reset.arg1 in kind_of:
                        spawned[kind_of[reset.arg1]] += 1
                nes = {kind: count for kind, count in room["entities"].items()
                       if kind in ENEMY_TYPES}
                if set(spawned) != set(nes):
                    problems.append((level, room["coordinate"], "kinds", dict(spawned), nes))
                if any(spawned[kind] > nes[kind] for kind in spawned):
                    problems.append((level, room["coordinate"], "more than the NES", dict(spawned)))
                if sum(spawned.values()) > max(ROOM_ENEMY_CAP, len(nes)):
                    problems.append((level, room["coordinate"], "crowded", dict(spawned)))
        self.assertEqual([], problems)

        dungeon_total = sum(
            1 for reset in self.resets
            if reset.command == "M"
            and any(dungeon["first_room_vnum"] <= reset.arg3 <= dungeon["last_room_vnum"]
                    for dungeon in self.dungeons.values())
        )
        self.assertLess(dungeon_total, 350, "the dungeons are crowded again")

    def test_dungeons_climb_from_the_first_levels_to_fifty_nine(self) -> None:
        bands = manifest_bands(self.manifest)
        self.assertLessEqual(bands[1][0], 3, "Level 1 is for characters fresh from school")
        self.assertEqual(bands[9][1], 59, "Death Mountain is for the top of mortal play")
        for level in range(1, 9):
            with self.subTest(level=level):
                self.assertLess(bands[level][0], bands[level + 1][0])
                self.assertLessEqual(bands[level + 1][0] - bands[level][1], 1,
                                     "a gap between bands leaves levels with no dungeon")

        # The ground a dungeon stands on is graded for that dungeon.
        self.assertEqual(self.world["H1"]["recommended_level"], 1)
        for level, dungeon in self.dungeons.items():
            screen = self.world[dungeon["overworld_coordinate"]]
            with self.subTest(level=level, screen=dungeon["overworld_coordinate"]):
                low, high = bands[level]
                self.assertTrue(low <= screen["recommended_level"] <= high)
                self.assertEqual(band_index(screen["recommended_level"], bands), level)

    def test_enemies_are_statted_for_the_band_they_stand_in(self) -> None:
        bands = manifest_bands(self.manifest)
        room_band = {room["vnum"]: band_index(room["recommended_level"], bands)
                     for room in self.world.values()}
        for level, dungeon in self.dungeons.items():
            room_band.update({vnum: level for vnum in range(
                dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1)})

        out_of_band = []
        for reset in self.resets:
            if reset.command != "M" or not TIER_VNUM_FIRST <= reset.arg1 <= TIER_VNUM_LAST:
                continue
            mob = self.parser.mobiles[reset.arg1]
            low, high = bands[room_band[reset.arg3]]
            if not low <= mob.level <= high:
                out_of_band.append((reset.arg3, reset.arg1, mob.level, (low, high)))
            if "B" not in mob.act_flags:
                out_of_band.append((reset.arg3, reset.arg1, "wanders out of its band"))
        self.assertEqual([], out_of_band)

        # Every enemy that spawns in Hyrule is one of the generated records,
        # apart from the bosses and the people who are not enemies at all.
        allowed = set(BOSS_MOBS.values()) | set(NPC_MOBS.values()) | set(SHOP_INVENTORY) | {30344, 30345}
        stray = {
            reset.arg1 for reset in self.resets
            if reset.command == "M"
            and not TIER_VNUM_FIRST <= reset.arg1 <= TIER_VNUM_LAST
            and reset.arg1 not in allowed
        }
        self.assertEqual(set(), stray)

    def test_contact_effects_find_every_band_of_their_kind(self) -> None:
        """fight.c decodes a generated vnum back to the kind it was.

        The like like eats shields, the bubble disarms and the wallmaster
        drags you to the entrance, all keyed on the vnum the kind used to
        have. If the generator's layout and fight.c's decoding drift, those
        effects silently stop at every band.
        """
        fight = Path("src/fight.c").read_text(encoding="utf-8")
        self.assertIn(f"#define HYRULE_TIER_FIRST       {TIER_VNUM_FIRST}", fight)
        self.assertIn(f"#define HYRULE_TIER_LAST        {TIER_VNUM_LAST}", fight)
        self.assertIn("attacker_vnum = hyrule_enemy_kind( ch->pIndexData->vnum );", fight)
        for kind, old_vnum in (("like_like", 30215), ("bubble", 30304), ("wallmaster", 30301)):
            with self.subTest(kind=kind):
                self.assertEqual(30200 + ENEMY_TYPES[kind].code, old_vnum)
                spawned = [vnum for vnum in self.parser.mobiles
                           if TIER_VNUM_FIRST <= vnum <= TIER_VNUM_LAST
                           and 30200 + (vnum - TIER_VNUM_FIRST) // 10 == old_vnum]
                self.assertTrue(spawned, f"no {kind} is generated")

    def test_each_boss_is_a_step_up_and_tops_its_band(self) -> None:
        bands = manifest_bands(self.manifest)
        previous_level = previous_hp = 0
        for level in range(1, 10):
            boss = self.parser.mobiles[BOSS_MOBS[level]]
            hit_dice = boss.hitp_dice
            count, rest = hit_dice.split("d")
            size, bonus = rest.split("+")
            hit_points = int(count) * (int(size) + 1) / 2 + int(bonus)
            with self.subTest(level=level, boss=boss.short_desc):
                self.assertEqual(boss.level, BOSS_STATS[level][0])
                self.assertGreater(boss.level, bands[level][1],
                                   "a boss should out-level the dungeon it rules")
                self.assertGreater(boss.level, previous_level)
                self.assertGreater(hit_points, previous_hp)
                self.assertIn(self.dungeons[level]["boss_vnum"], boss.spawn_rooms)
            previous_level, previous_hp = boss.level, hit_points
        self.assertLessEqual(self.parser.mobiles[BOSS_MOBS[9]].level, 65)

    def test_each_boss_carries_the_best_weapon_for_its_band(self) -> None:
        bands = manifest_bands(self.manifest)
        previous = 0.0
        for level in range(1, 10):
            weapon = BOSS_WEAPONS[level]
            obj = self.parser.objects[weapon.vnum]
            boss = self.parser.mobiles[BOSS_MOBS[level]]
            affects = {affect["location"]: affect["modifier"] for affect in obj.affects}
            average = int(obj.values[1]) * (int(obj.values[2]) + 1) / 2
            score = average + affects.get(19, 0)
            baseline = BOSS_WEAPON_BASELINES[level][0]
            with self.subTest(level=level, weapon=obj.short_desc):
                self.assertEqual(obj.item_type, "5")
                self.assertIn("N", obj.wear_flags, "a weapon has to be wieldable")
                self.assertIn(weapon.vnum, boss.drops)
                self.assertTrue(bands[level][0] <= obj.level <= bands[level][1])
                self.assertEqual(score, weapon_score(weapon))
                self.assertGreater(score, previous)
                # Best in slot, but not absurdly so: 10-20% over the best
                # weapon a character of that level could otherwise carry.
                self.assertGreaterEqual(score, baseline * 1.10)
                self.assertLessEqual(score, baseline * 1.20)
                self.assertEqual(obj.cost, obj.level * obj.level * 6 * COPPER_PER_GOLD)
                # The boss is the only source: one G reset, nothing else.
                self.assertEqual(
                    [reset.command for reset in self.resets
                     if reset.command in {"O", "G", "E", "P"} and reset.arg1 == weapon.vnum],
                    ["G"],
                )
            previous = score

    def room_bands(self) -> dict[int, int]:
        """The band of every Hyrule room: its dungeon, its screen, or the
        screen whose exit or portal leads into it (caves, shops, cellars)."""
        bands = manifest_bands(self.manifest)
        room_band = {room["vnum"]: band_index(room["recommended_level"], bands)
                     for room in self.world.values()}
        for level, dungeon in self.dungeons.items():
            room_band.update({vnum: level for vnum in range(
                dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1)})
        changed = True
        while changed:
            changed = False
            for vnum, room in self.hyrule_rooms.items():
                if vnum not in room_band:
                    continue
                leads_to = {exit_data.to_room for exit_data in room.exits}
                for object_vnum in room.objects:
                    obj = self.parser.objects.get(object_vnum)
                    if obj is not None and obj.item_type == "30":
                        leads_to.add(int(obj.values[1]))
                for target in leads_to:
                    if target in self.hyrule_rooms and target not in room_band:
                        room_band[target] = room_band[vnum]
                        changed = True
        return room_band

    def test_items_sit_at_or_below_the_band_they_are_found_in(self) -> None:
        """A level 15 wooden sword on the start screen helped nobody.

        Every place an item comes from -- a room, a boss or shopkeeper, a
        chest -- has a band, and the item must be usable at the top of
        it. The Master Sword used to be the one exception, a level 58
        sword in a band 6 graveyard; Ganon carries it now, inside his band.
        """
        bands = manifest_bands(self.manifest)
        room_band = self.room_bands()
        holder_band: dict[int, int] = {}
        found: dict[int, set[int]] = {}
        mob_room = None
        for reset in self.resets:
            if reset.command == "M":
                mob_room = reset.arg3
            elif reset.command == "O" and reset.arg3 in room_band:
                found.setdefault(reset.arg1, set()).add(room_band[reset.arg3])
                holder_band[reset.arg1] = room_band[reset.arg3]
            elif reset.command in {"G", "E"} and mob_room in room_band:
                found.setdefault(reset.arg1, set()).add(room_band[mob_room])
                holder_band[reset.arg1] = room_band[mob_room]
        for reset in self.resets:
            if reset.command == "P" and reset.arg3 in holder_band:
                found.setdefault(reset.arg1, set()).add(holder_band[reset.arg3])

        too_high = []
        for vnum, found_in in sorted(found.items()):
            obj = self.parser.objects[vnum]
            for band in found_in:
                if obj.level > bands[band][1]:
                    too_high.append((vnum, obj.short_desc, obj.level, band, bands[band]))
        self.assertEqual([], too_high)
        self.assertEqual(self.parser.objects[30200].level, 58)
        self.assertEqual(found[30200], {9}, "the Master Sword is Ganon's")

        # The first things a new character can pick up.
        self.assertLessEqual(self.parser.objects[30219].level, 3, "the Wooden Sword")
        self.assertLessEqual(self.parser.objects[30232].level, bands[1][1], "the boomerang")
        for level, heart_guard in BOSS_GEAR.items():
            with self.subTest(level=level, heart_guard=heart_guard):
                low, high = bands[level]
                self.assertTrue(low <= self.parser.objects[heart_guard].level <= high)

        # The Silver Arrow rule must sit inside Death Mountain's band.
        merc = Path("src/merc.h").read_text(encoding="utf-8")
        arrow_level = int(merc.split("#define HYRULE_SILVER_ARROW_LEVEL", 1)[1].split()[0])
        self.assertEqual(arrow_level, self.parser.objects[30218].level)
        self.assertTrue(bands[9][0] <= arrow_level <= bands[9][1])

    def test_nothing_found_outdoes_its_bands_boss_weapon(self) -> None:
        """The boss weapons stay best in slot after the re-levelling.

        The one exception is the Master Sword, which Ganon carries beside
        his trident and which is meant to beat every weapon in the game;
        test_the_master_sword_is_the_best_weapon_a_mortal_can_get holds
        it to that instead.
        """
        bands = manifest_bands(self.manifest)
        better = []
        for obj in self.parser.objects.values():
            if (obj.area_file != "hyrule.are" or obj.item_type != "5"
                    or obj.vnum in {weapon.vnum for weapon in BOSS_WEAPONS.values()}
                    or obj.vnum == MASTER_SWORD_VNUM
                    or not self.object_is_sourced(obj.vnum)):
                continue
            affects = {affect["location"]: affect["modifier"] for affect in obj.affects}
            score = int(obj.values[1]) * (int(obj.values[2]) + 1) / 2 + affects.get(19, 0)
            for level, weapon in BOSS_WEAPONS.items():
                if bands[level][0] <= obj.level <= bands[level][1] and score >= weapon_score(weapon):
                    better.append((obj.vnum, obj.short_desc, obj.level, score, level))
        self.assertEqual([], better)

    def obtainable_weapons(self, max_level: int) -> list[tuple[float, int, str, str]]:
        """(score, vnum, name, area) for every weapon a mortal can get at or
        below max_level: from a mobile, a room, a container or a shop
        anywhere in the world, or as a quest reward."""
        quest = Path("src/quest.c").read_text(encoding="latin-1")
        quest_rewards = {
            int(line.split()[2]) for line in quest.splitlines()
            if line.startswith("#define QUEST_ITEM") and line.split()[2].isdigit()
        }
        direct = set(quest_rewards)
        containers: dict[int, set[int]] = {}
        for resets in self.parser.resets.values():
            for reset in resets:
                if reset.command in {"O", "G", "E"}:
                    direct.add(reset.arg1)
                elif reset.command == "P":
                    containers.setdefault(reset.arg1, set()).add(reset.arg3)

        def sourced(vnum: int, seen: frozenset[int] = frozenset()) -> bool:
            if vnum in direct:
                return True
            return any(container not in seen and sourced(container, seen | {vnum})
                       for container in containers.get(vnum, ()))

        weapons = []
        for obj in self.parser.objects.values():
            if obj.item_type != "5" or not 0 <= obj.level <= max_level:
                continue
            if not sourced(obj.vnum):
                continue
            try:
                average = int(obj.values[1]) * (int(obj.values[2]) + 1) / 2
            except (ValueError, IndexError):
                continue
            damroll = sum(affect["modifier"] for affect in obj.affects
                          if affect["location"] == 19)
            weapons.append((average + damroll, obj.vnum, obj.short_desc, obj.area_file))
        return sorted(weapons, reverse=True)

    def test_the_master_sword_is_the_best_weapon_a_mortal_can_get(self) -> None:
        """Ganon's great chest holds it, and nothing a mortal can get
        anywhere beats it.

        The comparison is the boss weapons': average damage plus damroll,
        against every weapon at or below level 59 from any mobile, room,
        container, shop or quest in the world -- Ganon's trident included.
        """
        sword = self.parser.objects[MASTER_SWORD_VNUM]
        ganon = self.parser.mobiles[GANON_VNUM]
        self.assertNotIn(MASTER_SWORD_VNUM, ganon.drops)
        self.assertEqual(
            [(reset.command, reset.arg3) for reset in self.resets
             if reset.command in {"O", "G", "E", "P"} and reset.arg1 == MASTER_SWORD_VNUM],
            [("P", CHESTS[9])], "Ganon's great chest is the only source")
        self.assertEqual(sword.level, 58)
        self.assertIn("N", sword.wear_flags)

        weapons = self.obtainable_weapons(59)
        best, best_vnum, _, _ = weapons[0]
        self.assertEqual(best_vnum, MASTER_SWORD_VNUM, weapons[:3])
        self.assertEqual(best, master_sword_score())
        runner_up = weapons[1]
        self.assertEqual(runner_up[1], BOSS_WEAPONS[9].vnum, "the trident is next")
        self.assertEqual(runner_up[0], MASTER_SWORD_BASELINES[0][0])
        outside = next(weapon for weapon in weapons if weapon[3] != "hyrule.are")
        self.assertEqual(outside[0], MASTER_SWORD_BASELINES[1][0], outside)
        # Best by a clear margin over the trident, without running away.
        self.assertGreaterEqual(best, runner_up[0] * 1.05)
        self.assertLessEqual(best, runner_up[0] * 1.20)

        # Its gift: haste while wielded, as a ROM F record.
        self.assertIn({"where": "A", "location": 0, "modifier": 0, "bits": "V"},
                      sword.affect_bits)
        lore = " ".join(" ".join(ed["description"].split()) for ed in sword.extra_descr)
        self.assertIn("hastens you", lore)

    def test_every_dungeon_runs_key_door_chest(self) -> None:
        """Kill the guardian, take its key, unlock the door behind it,
        unlock the chest there: the piece and the treasure are inside."""
        fight = Path("src/fight.c").read_text(encoding="latin-1")
        self.assertIn("!IS_HYRULE_BOSS_KEY(obj->pIndexData->vnum)", fight,
                      "a guardian's key must not crumble in the corpse")
        sources: dict[int, list[tuple[str, int]]] = {}
        for reset in self.resets:
            if reset.command in {"O", "G", "E", "P"}:
                sources.setdefault(reset.arg1, []).append((reset.command, reset.arg3))
        self.assertEqual(len(set(BOSS_KEYS.values())), 9, "one key per dungeon")
        for level, dungeon in self.dungeons.items():
            key, chest_vnum = BOSS_KEYS[level], CHESTS[level]
            boss = self.parser.mobiles[BOSS_MOBS[level]]
            boss_room = self.parser.rooms[dungeon["boss_vnum"]]
            goal = self.parser.rooms[dungeon["goal_vnum"]]
            chest = self.parser.objects[chest_vnum]
            with self.subTest(level=level):
                self.assertIn(key, boss.drops)
                self.assertEqual(self.parser.objects[key].item_type, "18")
                for flag in "NPR":   # inventory, rot-death, meltdrop
                    self.assertNotIn(flag, self.parser.objects[key].extra_flags)
                # The door between the lair and the treasure room, both ways.
                door = next(e for e in boss_room.exits if e.to_room == goal.vnum)
                back = next(e for e in goal.exits if e.to_room == boss_room.vnum)
                for side, room in ((door, boss_room), (back, goal)):
                    self.assertEqual((side.locks, side.key_vnum), (2, key),
                                     "pickproof; lock 5 resets as a trapped door")
                    resets = [r.arg3 for r in self.resets if r.command == "D"
                              and r.arg1 == room.vnum and r.arg2 == side.direction]
                    self.assertEqual(resets, [3], "locked, and magical like the golden door")
                # The chest: closed, locked, pickproof, keyed, in the room.
                self.assertEqual(chest.item_type, "15")
                self.assertEqual(chest.values[1], "ABCD")
                self.assertEqual(int(chest.values[2]), key)
                self.assertEqual(sources[chest_vnum], [("O", goal.vnum)])
                self.assertNotIn("A", chest.wear_flags, "nobody carries the chest off")
                # Its prize: the piece and the treasure, and nowhere else.
                for prize in (PIECE_VNUMS[level], DUNGEON_TREASURE[level]):
                    self.assertEqual(sources[prize], [("P", chest_vnum)], prize)
                    for flag in "NPR":
                        self.assertNotIn(flag, self.parser.objects[prize].extra_flags)
                piece = self.parser.objects[PIECE_VNUMS[level]]
                self.assertEqual(piece.item_type, "8", "saved on quit, unlike a key")
                self.assertIn("H", piece.extra_flags, "a piece cannot be handed on")
                lore = " ".join(" ".join(e["description"].split()) for e in piece.extra_descr)
                self.assertIn("one of nine", lore)
                self.assertIn("COMBINE TRIFORCE", lore)
                self.assertNotEqual(self.parser.objects[DUNGEON_TREASURE[level]].item_type, "18",
                                    "a treasure is saved when you quit")
        # load_resets makes every reset of a lock 5 exit a trapped door, so
        # none of Hyrule's doors may use it.
        trapped = sorted((room.vnum, e.direction) for room in self.hyrule_rooms.values()
                         for e in room.exits if e.locks == 5)
        self.assertEqual([], trapped)
        self.assertEqual(BOSS_KEYS[9], 30243, "Ganon's key is the Golden Key")
        self.assertEqual(DUNGEON_TREASURE[9], MASTER_SWORD_VNUM)
        self.assertEqual(PIECE_VNUMS[9], 30408)

        db = Path("src/db.c").read_text(encoding="latin-1")
        reset_p = db.split("case 'P':", 2)[2].split("case 'G':", 1)[0]
        self.assertIn("IS_HYRULE_CHEST(pObjToIndex->vnum)", reset_p,
                      "Hyrule's chests refill with players about")
        self.assertIn("obj_to->value[1] = obj_to->pIndexData->value[1];", reset_p,
                      "and close and lock again when they do")

    def gate_rows(self) -> dict[int, list[str]]:
        source = Path("src/act_move.c").read_text(encoding="latin-1")
        table = source.split("hyrule_progress_gate[] =", 1)[1].split("};", 1)[0]
        rows = {}
        for chunk in table.split("{ ")[1:]:
            fields = [field.strip() for field in
                      re.sub(r'(?:"[^"]*"\s*)+', "STR ", chunk.split("},", 1)[0]).replace(
                          "\n", " ").split(",")]
            fields = [field for field in fields if field]
            rows[int(fields[0])] = fields
        return rows

    def test_the_dungeons_form_one_unbroken_chain(self) -> None:
        """Each dungeon's entrance asks for the previous piece, and its
        guardian's chamber for the previous treasure -- both of which are
        in the previous guardian's chest."""
        rows = self.gate_rows()
        self.assertEqual(sorted(rows), list(range(1, 10)))
        chest_contents: dict[int, set[int]] = {}
        for reset in self.resets:
            if reset.command == "P":
                chest_contents.setdefault(reset.arg3, set()).add(reset.arg1)
        for level, dungeon in self.dungeons.items():
            (number, first, last, entrance, boss, goal,
             entry_need, entry_text, boss_need, boss_also, boss_text) = rows[level]
            with self.subTest(level=level):
                self.assertEqual(
                    [int(first), int(last), int(entrance), int(boss), int(goal)],
                    [dungeon["first_room_vnum"], dungeon["last_room_vnum"],
                     dungeon["entrance_vnum"], dungeon["boss_vnum"], dungeon["goal_vnum"]])
                if level == 1:
                    self.assertEqual((entry_need, boss_need), ("0", "0"))
                    continue
                self.assertEqual(int(entry_need), ENTRY_NEEDS[level])
                self.assertEqual(int(boss_need), GUARDIAN_NEEDS[level])
                self.assertEqual(int(boss_also), GUARDIAN_ALSO.get(level, 0))
                self.assertEqual(entry_text, "STR")
                self.assertEqual(boss_text, "STR")
                # Both come out of the previous dungeon's chest.
                previous = chest_contents[CHESTS[level - 1]]
                self.assertIn(int(entry_need), previous)
                self.assertIn(int(boss_need), previous)
        move = Path("src/act_move.c").read_text(encoding="latin-1")
        move_char = move.split("void move_char(", 1)[1].split("\n}", 1)[0]
        enter = move.split("void do_enter(", 1)[1].split("\n}", 1)[0]
        self.assertIn("hyrule_gate_refuses( ch, in_room, to_room )", move_char)
        self.assertIn("hyrule_gate_refuses( ch, ch->in_room, to_room )", enter)
        gate = move.split("bool hyrule_gate_refuses(", 1)[1].split("\n}", 1)[0]
        self.assertIn("IS_TRUSTED(subject, LEVEL_IMMORTAL)", gate)
        self.assertIn("subject = subject->master", gate)

    def test_every_dungeon_room_blocks_magical_arrival(self) -> None:
        """Gate, summon, portal, astral walk and teleport refuse a no-recall
        destination, so the only ways into a dungeon are the gated ones."""
        no_recall = "N"   # ROOM_NO_RECALL
        for level, dungeon in self.dungeons.items():
            for vnum in range(dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1):
                with self.subTest(vnum=vnum):
                    self.assertIn(no_recall, self.parser.rooms[vnum].room_flags)

    def test_guardian_volleys_match_the_specials(self) -> None:
        special = Path("src/special.c").read_text(encoding="latin-1")
        table = special.split("hyrule_guardian_volleys[] =", 1)[1].split("};", 1)[0]
        found = {
            int(vnum): (int(count), int(low), int(high))
            for vnum, count, low, high in re.findall(
                r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),", table)
        }
        expected = {BOSS_MOBS[level]: BOSS_VOLLEYS[level] for level in range(1, 9)}
        self.assertEqual(found, expected)
        count, low, high = BOSS_VOLLEYS[9]
        self.assertIn(f"#define GANON_FIREBALLS          {count}", special)
        self.assertIn(f"#define GANON_FIREBALL_MIN    {low}", special)
        self.assertIn(f"#define GANON_FIREBALL_MAX    {high}", special)
        area = Path("area/hyrule.are").read_text(encoding="latin-1")
        for vnum, name in BOSS_SPECIALS.items():
            with self.subTest(vnum=vnum):
                self.assertIn(f"M {vnum} {name}", area)
                self.assertIn(f'"{name}"', special)

    def test_combine_makes_the_triforce_from_nine_pieces(self) -> None:
        info = Path("src/act_info.c").read_text(encoding="latin-1")
        recipes = info.split("combine_recipes[] =", 1)[1].split("};", 1)[0]
        self.assertIn('"triforce", OBJ_VNUM_HYRULE_TRIFORCE', recipes)
        self.assertEqual(
            sorted(int(v) for v in re.findall(r"\b(30[0-9]{3})\b", recipes)),
            sorted(PIECE_VNUMS.values()))
        combine = info.split("void do_combine(", 1)[1].split("\n}", 1)[0]
        self.assertIn("COMM_COMBINE", combine, "COMBINE alone still toggles the list")
        commands = Path("area/commands.are").read_text(encoding="latin-1")
        self.assertIn("COMBINE TRIFORCE", commands)

    def test_worn_affect_bits_load_and_come_off_with_the_item(self) -> None:
        """The F record the Master Sword and Red Ring use, end to end."""
        db = Path("src/db.c").read_text(encoding="latin-1")
        loader = db.split("void load_objects( FILE *fp )", 1)[1].split("\n}", 1)[0]
        self.assertIn("letter_inner == 'F'", loader)
        self.assertIn("paf->bitvector      = (int)bits;", loader)
        handler = Path("src/handler.c").read_text(encoding="latin-1")
        unequip = handler.split("void unequip_char( CHAR_DATA *ch, OBJ_DATA *obj )", 1)[1]
        unequip = unequip.split("\n}", 1)[0]
        # Lifting a worn bit puts back any a spell or other gear still gives.
        self.assertIn("removed_primary |= paf->bitvector;", unequip)
        self.assertIn("restore_character_affect_bits( ch, removed_primary", unequip)
        magic = Path("src/magic.c").read_text(encoding="latin-1")
        self.assertIn("!equipment_grants_affect(victim, AFF_SANCTUARY)", magic)
        self.assertIn("!equipment_grants_affect( victim, AFF_HASTE )", magic)

    def test_the_red_ring_lies_in_death_mountain_and_gives_sanctuary(self) -> None:
        ring = self.parser.objects[30579]
        self.assertIn({"where": "A", "location": 0, "modifier": 0, "bits": "H"},
                      ring.affect_bits)
        cellar_rooms = {cellar["vnum"] for cellar in self.dungeons[9]["cellars"]}
        sources = [reset for reset in self.resets
                   if reset.command in {"O", "G", "E", "P"} and reset.arg1 == 30579]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].command, "O")
        self.assertIn(sources[0].arg3, cellar_rooms)
        guidance = " ".join(" ".join(ed["description"].split()) for ed in ring.extra_descr)
        self.assertIn("sanctuary", guidance)
        self.assertIn("20 percent", guidance)

    def test_the_triforce_is_worn_as_a_light_and_gives_holy_sight(self) -> None:
        triforce = self.parser.objects[30286]
        self.assertEqual(triforce.item_type, "1", "WEAR puts a light in the light slot")
        self.assertEqual(triforce.values[2], "999", "create_object makes 999 a light that never burns down")
        self.assertLessEqual(triforce.level, 59)

        merc = Path("src/merc.h").read_text(encoding="latin-1")
        self.assertIn("#define OBJ_VNUM_HYRULE_TRIFORCE      30286", merc)
        self.assertIn("#define TRIFORCE_SIGHT_LEVEL          59", merc)
        handler = Path("src/handler.c").read_text(encoding="latin-1")
        sight = handler.split("bool triforce_sight( const CHAR_DATA *ch )", 1)[1]
        sight = sight.split("\n}", 1)[0]
        self.assertIn("IS_NPC(ch)", sight, "players only: no mobile sees through a meld")
        self.assertIn("WEAR_LIGHT", sight)
        self.assertIn("OBJ_VNUM_HYRULE_TRIFORCE", sight)
        trust = handler.split("int sight_trust( const CHAR_DATA *ch )", 1)[1].split("\n}", 1)[0]
        self.assertIn("UMAX( trust, TRIFORCE_SIGHT_LEVEL )", trust)

        # Every place holylight grants sight asks the Triforce too, and the
        # wizinvis and incognito levels are read against the sight trust.
        can_see = handler.split("bool can_see( CHAR_DATA *ch", 1)[1].split("\n}", 1)[0]
        self.assertIn("sight_trust( ch ) < victim->invis_level", can_see)
        self.assertIn("sight_trust( ch ) < victim->cloak_level", can_see)
        self.assertIn("triforce_sight( ch )", can_see)
        can_see_obj = handler.split("bool can_see_obj(", 1)[1].split("\n}", 1)[0]
        self.assertIn("triforce_sight( ch )", can_see_obj)
        for path in ("src/act_info.c", "src/act_move.c", "src/handler.c"):
            source = Path(path).read_text(encoding="latin-1")
            for index, line in enumerate(source.splitlines()):
                if "PLR_HOLYLIGHT" in line and ("IS_SET(ch->act" in line):
                    window = "\n".join(source.splitlines()[index:index + 3])
                    if "SET_BIT" in line or "REMOVE_BIT" in line or "IS_IMMORTAL" in line \
                            or '"On"' in line:
                        continue
                    with self.subTest(path=path, line=index + 1):
                        self.assertIn("triforce_sight", window)

    def test_bosses_drop_heart_containers_in_their_band(self) -> None:
        bands = manifest_bands(self.manifest)
        for level in range(1, 9):
            vnum = BOSS_HEART_CONTAINER_FIRST + level - 1
            container = self.parser.objects[vnum]
            boss = self.parser.mobiles[BOSS_MOBS[level]]
            applies = {affect["location"]: affect["modifier"] for affect in container.affects}
            with self.subTest(level=level):
                self.assertIn(vnum, boss.drops)
                self.assertEqual(container.level, bands[level][1])
                self.assertEqual(applies.get(13), 2 * bands[level][1])
                self.assertEqual(applies.get(5, 0), 1 if level >= 5 else 0)
                self.assertIn("O", container.wear_flags)
        self.assertNotIn(BOSS_HEART_CONTAINER_FIRST + 8, self.parser.objects,
                         "Ganon leaves no Heart Container, as in the NES")

    def test_enemy_drops_exist_for_every_band_and_match_fight_c(self) -> None:
        merc = Path("src/merc.h").read_text(encoding="latin-1")
        for name, first in (("HEART", DROP_HEART_FIRST), ("FAIRY", DROP_FAIRY_FIRST),
                            ("CLOCK", DROP_CLOCK_FIRST)):
            self.assertIn(f"#define OBJ_VNUM_HYRULE_{name}_FIRST   {first}", merc)
        bands = manifest_bands(self.manifest)
        for level in range(1, 10):
            for first in (DROP_HEART_FIRST, DROP_FAIRY_FIRST, DROP_CLOCK_FIRST):
                obj = self.parser.objects[first + level - 1]
                with self.subTest(level=level, vnum=obj.vnum):
                    self.assertEqual(obj.item_type, "10", "a potion: QUAFF it")
                    self.assertTrue(bands[level][0] <= obj.level <= bands[level][1])
                    self.assertEqual(int(obj.values[0]), bands[level][1])
        fight = Path("src/fight.c").read_text(encoding="latin-1")
        drop = fight.split("static void hyrule_enemy_drop(", 1)[1].split("\n}", 1)[0]
        for name in ("HEART", "FAIRY", "CLOCK"):
            self.assertIn(f"OBJ_VNUM_HYRULE_{name}_FIRST + band - 1", drop)
        self.assertIn("TYPE_GOLD", drop, "rupees are gold coins")
        self.assertIn("hyrule_enemy_drop( corpse, ch->pIndexData->vnum )", fight)
        rupees = fight.split("static const int hyrule_rupee_drop[HYRULE_BANDS] =", 1)[1]
        rupees = [int(value) for value in rupees.split("{", 1)[1].split("}", 1)[0].split(",")]
        self.assertEqual(len(rupees), 9)
        self.assertEqual(rupees, sorted(rupees), "drops climb with the band")

    def test_ganon_is_a_fight_for_a_group(self) -> None:
        ganon = self.parser.mobiles[GANON_VNUM]
        level, hit_points, damage = BOSS_STATS[9]
        self.assertEqual(ganon.level, level)
        # The file's armour; load_mobiles multiplies it by ten.
        self.assertEqual(ganon.ac, [GANON_ARMOR] * 4)
        self.assertGreaterEqual(hit_points, 30000)
        self.assertGreaterEqual(damage, 300)
        specials = Path("area/hyrule.are").read_text(encoding="latin-1")
        self.assertIn(f"M {GANON_VNUM} spec_ganon", specials)
        self.assertNotIn(f"M {GANON_VNUM} spec_cast_necro", specials)
        special = Path("src/special.c").read_text(encoding="latin-1")
        self.assertIn('{ "spec_ganon",             spec_ganon              }', special)
        spec = special.split("bool spec_ganon(", 1)[1].split("\nbool ", 1)[0]
        self.assertIn("DAM_FIRE", spec)
        self.assertIn("AFF2_NO_RECOVER", spec, "a collapsed Ganon must not heal")
        self.assertIn("can_see( mob, victim )", special.split("static bool ganon_may_target", 1)[1],
                      "a melded character is never a target")

    def test_hyrule_bystanders_cannot_be_attacked(self) -> None:
        """The old men are level 50 so nothing in Level 1 can hurt them,
        which made them the best experience in Hyrule for anyone who could."""
        fight = Path("src/fight.c").read_text(encoding="utf-8")
        for name, vnum in (("OLD_MAN", NPC_MOBS["old_man"]), ("ZELDA", NPC_MOBS["princess_zelda"]),
                           ("FAIRY", NPC_MOBS["fairy"]), ("REPAIR_MAN", 30344), ("GAMBLER", 30345)):
            self.assertIn(f"#define HYRULE_{name}_VNUM", fight)
            self.assertIn(str(vnum), fight.split(f"#define HYRULE_{name}_VNUM", 1)[1].split("\n", 1)[0])
        safe = fight.split("bool is_safe(CHAR_DATA *ch, CHAR_DATA *victim )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("is_hyrule_bystander(victim)", safe)
        self.assertGreaterEqual(fight.count("is_hyrule_bystander(victim)"), 2,
                                "both is_safe and the quiet spell check must refuse them")

    def test_room_names_carry_no_grid_labels(self) -> None:
        import re

        grid = re.compile(r"\[[A-P]\d\]|\b[A-P][1-8]\b|\[\d+/\d+\]")
        labelled = sorted(
            (vnum, room.name) for vnum, room in self.hyrule_rooms.items()
            if grid.search(room.name)
        )
        self.assertEqual([], labelled)

        dungeon_vnums = {}
        for level, dungeon in self.dungeons.items():
            for vnum in range(dungeon["first_room_vnum"], dungeon["last_room_vnum"] + 1):
                dungeon_vnums[vnum] = level
        misnamed = sorted(
            (vnum, room.name) for vnum, room in self.hyrule_rooms.items()
            if room.name.startswith("Level ") != (vnum in dungeon_vnums)
            or (vnum in dungeon_vnums
                and not room.name.startswith(f"Level {dungeon_vnums[vnum]}: "))
        )
        self.assertEqual([], misnamed)
        self.assertEqual(self.hyrule_rooms[30200].name, "The First Quest Begins")

    def test_rooms_describe_the_place_and_fit_a_terminal(self) -> None:
        """The old prose was one template that listed who was in the room."""
        lost_maze = set(range(30750, 30757))
        problems = []
        seen: dict[str, int] = {}
        for vnum, room in sorted(self.hyrule_rooms.items()):
            lines = room.description.strip().splitlines()
            if not 2 <= len(lines) <= 7:
                problems.append((vnum, "length", len(lines)))
            if any(len(line) > 78 for line in lines):
                problems.append((vnum, "too wide"))
            for phrase in ("waits here", "wait here", "Nothing moves", "hold this ground"):
                if phrase in room.description:
                    problems.append((vnum, phrase))
            text = " ".join(room.description.split())
            if (text in seen and vnum not in lost_maze
                    and not 30660 <= vnum <= 30723):
                problems.append((vnum, "same as", seen[text]))
            seen.setdefault(text, vnum)
        self.assertEqual([], problems)

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
        # The dungeon treasures are in the guardians' chests now (see
        # test_every_dungeon_runs_key_door_chest); the cellars that held
        # one hold rupees, and the rest keep the NES's loot.
        expected_cellar_items = {
            1: {30511}, 3: {30511}, 4: {30511}, 5: {30512},
            6: {30245}, 7: {30512}, 8: {30415, 30512}, 9: {30218, 30579},
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
        # Hyrule is a 1-59 climb: gear for every mortal level, none above.
        self.assertEqual(set(range(1, 60)) - sourced_levels, set())
        self.assertEqual({level for level in sourced_levels if level > 59}, set())

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
            "O8": (30653, 30500),
            "E6": (30674, 30276),
        }
        # The Hero's Grave still opens under the B6 headstone, but the
        # Master Sword is Ganon's now: the grave holds nothing.
        self.assertTrue(any(
            exit_data.to_room == 30652
            for exit_data in self.parser.rooms[self.world["B6"]["vnum"]].exits
        ))
        self.assertNotIn(30200, self.parser.rooms[30652].objects)
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
        # The complete Triforce is made with COMBINE, never found.
        self.assertNotIn(30286, self.parser.rooms[level_nine_goal].objects)
        self.assertFalse(self.object_is_sourced(30286))
        self.assertIn(CHESTS[9], self.parser.rooms[level_nine_goal].objects)
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

        # The signs still read "displayed for 130 rupees", and a rupee is a
        # gold coin -- the rupee piles are ITEM_MONEY with value[1] set to
        # TYPE_GOLD. obj->cost is counted in copper, so the price only
        # holds if it is written out in copper. It was not: the generator
        # emitted 130, one ten-thousandth of what the shield advertises,
        # and the object-section reader in tools/costs_to_copper.py had
        # stopped 85 objects short of noticing.
        expected_rupees = {
            30541: 130, 30542: 20, 30543: 80,
            30544: 160, 30545: 100, 30546: 60,
            30547: 90, 30548: 100, 30549: 10,
            30550: 80, 30551: 250, 30552: 60,
            30553: 40, 30554: 68,
        }
        stocked = [v for inventory in SHOP_INVENTORY.values() for v in inventory]
        self.assertEqual(
            {v: self.parser.objects[v].cost for v in stocked},
            {v: rupees * COPPER_PER_GOLD for v, rupees in expected_rupees.items()},
            "a shop price has drifted from the rupees its description quotes",
        )
        for keeper_vnum, inventory in SHOP_INVENTORY.items():
            with self.subTest(keeper_vnum=keeper_vnum):
                self.assertTrue(set(inventory).issubset(self.parser.mobiles[keeper_vnum].drops))
            for object_vnum in inventory:
                with self.subTest(object_vnum=object_vnum):
                    obj = self.parser.objects[object_vnum]
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
        golden_door_reset_keys = {
            (level_nine["boss_vnum"], 0),
            (level_nine["goal_vnum"], 2),
        }
        golden_door_resets = {
            (reset.arg1, reset.arg2): reset.arg3
            for reset in self.resets
            if reset.command == "D"
            and (reset.arg1, reset.arg2) in golden_door_reset_keys
        }
        self.assertEqual(golden_door_resets, {
            (level_nine["boss_vnum"], 0): 3,
            (level_nine["goal_vnum"], 2): 3,
        })

    def test_mobile_reset_limits_prevent_duplicate_spawns(self) -> None:
        mobile_resets = [reset for reset in self.resets if reset.command == "M"]
        intended_population = Counter(reset.arg1 for reset in mobile_resets)

        for reset in mobile_resets:
            with self.subTest(mob_vnum=reset.arg1, room_vnum=reset.arg3):
                self.assertEqual(reset.arg2, intended_population[reset.arg1])

        live_population: Counter[int] = Counter()
        spawned_by_pass: list[Counter[int]] = []
        for _ in range(2):
            spawned: Counter[int] = Counter()
            for reset in mobile_resets:
                if live_population[reset.arg1] >= reset.arg2:
                    continue
                live_population[reset.arg1] += 1
                spawned[reset.arg1] += 1
            spawned_by_pass.append(spawned)

        self.assertEqual(spawned_by_pass[0], intended_population)
        self.assertFalse(spawned_by_pass[1])
        self.assertEqual(intended_population[30225], 1)

    def test_ganon_guarantees_one_random_mortal_relic(self) -> None:
        relics = {
            30577: (54, "D", {(5, 2), (13, 100), (24, -2)}, "5 percent"),
            30578: (54, "B", {(13, 60), (12, 40), (24, -1)}, "10 percent"),
            30579: (58, "B", {(5, 2), (13, 100), (24, -3)}, "20 percent"),
            30580: (56, "J", {(24, -4), (17, -5)}, "15 percent"),
            30581: (55, "G", {(2, 2), (14, 150)}, "25 percent"),
        }
        for vnum, (level, wear_flag, affects, effect_text) in relics.items():
            relic = self.parser.objects[vnum]
            guidance = " ".join(
                " ".join(description["description"].split())
                for description in relic.extra_descr
            ).lower()
            with self.subTest(vnum=vnum):
                self.assertEqual(relic.item_type, "9")
                self.assertEqual(relic.level, level)
                self.assertLess(relic.level, 60)
                self.assertIn(wear_flag, relic.wear_flags)
                self.assertEqual(
                    {(affect["location"], affect["modifier"])
                     for affect in relic.affects},
                    affects,
                )
                self.assertIn(effect_text, guidance)

        fight_source = Path("src/fight.c").read_text(encoding="utf-8").lower()
        loot_table = fight_source.split(
            "static const int hyrule_ganon_loot_vnums[]", 1
        )[1].split("};", 1)[0]
        for constant in (
            "obj_vnum_hyrule_heros_tunic",
            "obj_vnum_hyrule_blue_ring",
            "obj_vnum_hyrule_mirror_shield",
            "obj_vnum_hyrule_pegasus_boots",
        ):
            self.assertEqual(loot_table.count(constant), 1)
        # The Red Ring is found, not rolled for: it lies in Death
        # Mountain's Red Ring Cellar, where the NES keeps it.
        self.assertEqual(loot_table.count("obj_vnum_hyrule_red_ring"), 0)
        red_ring_cellar = next(
            cellar for cellar in self.dungeons[9]["cellars"]
            if cellar["name"] == "Red Ring Cellar"
        )
        self.assertIn(30579, self.parser.rooms[red_ring_cellar["vnum"]].objects)
        corpse_source = fight_source.split(
            "void make_corpse( char_data *ch )", 1
        )[1].split("void death_cry", 1)[0]
        self.assertIn("if ( is_hyrule_ganon(ch) )", corpse_source)
        self.assertIn("loot_index = number_range", corpse_source)
        self.assertIn("add_loot_to_corpse(corpse, loot_vnum)", corpse_source)
        self.assertNotIn("for ( loot_index", corpse_source)

    def test_ganon_relic_passives_are_active_and_compared(self) -> None:
        fight_source = Path("src/fight.c").read_text(encoding="utf-8").lower()
        damage_source = fight_source.split(
            "static int apply_hyrule_relic_damage_reduction", 1
        )[1].split("static void reward_hyrule_hero_tunic", 1)[0]
        self.assertIn("obj_vnum_hyrule_red_ring", damage_source)
        self.assertIn("dam = dam * 80 / 100", damage_source)
        self.assertIn("else if", damage_source)
        self.assertIn("obj_vnum_hyrule_blue_ring", damage_source)
        self.assertIn("dam = dam * 90 / 100", damage_source)
        self.assertIn("obj_vnum_hyrule_mirror_shield", damage_source)
        self.assertIn("dam = dam * 85 / 100", damage_source)
        self.assertIn("dam_type != dam_bash", damage_source)
        self.assertIn("dam_type != dam_pierce", damage_source)
        self.assertIn("dam_type != dam_slash", damage_source)

        tunic_source = fight_source.split(
            "static void reward_hyrule_hero_tunic", 1
        )[1].split("static bool is_hyrule_ganon", 1)[0]
        self.assertIn("obj_vnum_hyrule_heros_tunic", tunic_source)
        self.assertIn("ch->max_hit / 20", tunic_source)
        self.assertIn("victim->level * 2", tunic_source)
        self.assertIn("reward_hyrule_hero_tunic( ch, victim )", fight_source)

        move_source = Path("src/act_move.c").read_text(encoding="utf-8").lower()
        self.assertIn("obj_vnum_hyrule_pegasus_boots", move_source)
        self.assertIn("move = umax( 1, move * 3 / 4 )", move_source)

        compare_source = Path("src/gear_compare.c").read_text(
            encoding="utf-8"
        ).lower()
        for constant in (
            "obj_vnum_hyrule_heros_tunic",
            "obj_vnum_hyrule_blue_ring",
            "obj_vnum_hyrule_red_ring",
            "obj_vnum_hyrule_mirror_shield",
            "obj_vnum_hyrule_pegasus_boots",
        ):
            self.assertIn(constant, compare_source)
        self.assertIn("relic_damage_reduction = 20", compare_source)
        self.assertIn("else if ( loadout->hyrule_blue_ring_count > 0 )", compare_source)
        self.assertIn("relic_nonphysical_reduction = 15", compare_source)
        self.assertIn("relic_movement_reduction = 25", compare_source)
        self.assertIn("unique relic effects", compare_source)

    def test_silver_arrow_explains_how_to_finish_ganon(self) -> None:
        silver_arrow = self.parser.objects[30218]
        ganon = self.parser.mobiles[30225]
        guidance = " ".join(
            " ".join(description["description"].split())
            for description in silver_arrow.extra_descr
            if "silver" in description["keyword"].lower()
        ).lower()
        self.assertEqual(silver_arrow.material, "silver")
        self.assertEqual(silver_arrow.level, 54)
        self.assertIn("level 54 or higher", guidance)
        self.assertIn("immortal status is not required", guidance)
        self.assertIn("spells, poison, and lingering effects can wound", guidance)
        self.assertIn("full weapon mastery", guidance)
        self.assertIn("one tenth", guidance)
        self.assertIn("shoot ganon", guidance)
        self.assertIn("does not require the archery skill", guidance)
        self.assertIn("does not consume the silver arrow", guidance)
        self.assertIn("no normal attack can kill", guidance)
        self.assertEqual(ganon.imm_flags, "B")
        self.assertEqual(ganon.res_flags, "CP")
        self.assertIn("silver", decode_flags(ganon.vuln_flags, VULN_FLAGS))
        fight_source = Path("src/fight.c").read_text(encoding="utf-8").lower()
        self.assertIn("is_silver_arrow_finishing_hit(ch, dt)", fight_source)
        self.assertIn("is_silver_arrow_attack(ch, dt)", fight_source)
        self.assertIn("dt == type_hit + weapon->value[3]", fight_source)
        finishing_source = fight_source.split(
            "static bool is_silver_arrow_finishing_hit", 1
        )[1].split("static bool is_stunned_hyrule_ganon", 1)[0]
        self.assertIn("dt == gsn_archery", finishing_source)
        self.assertNotIn("type_hit", finishing_source)
        self.assertIn("other attacks can wound", fight_source)
        self.assertIn("!bypass_hyrule_ganon && is_hyrule_ganon(victim)", fight_source)
        self.assertIn("raw_kill_internal( ch, victim, true )", fight_source)
        self.assertIn("hyrule_silver_arrow_ganon_skill 100", fight_source)
        self.assertIn("skill = umax(skill, hyrule_silver_arrow_ganon_skill)", fight_source)
        self.assertIn("hyrule_silver_arrow_ganon_damage_divisor 10", fight_source)
        self.assertIn("hyrule_silver_arrow_hit = dam > 0", fight_source)
        self.assertIn("victim->max_hit", fight_source)
        self.assertIn("set_bit( victim->affected_by2, aff2_no_recover )", fight_source)
        self.assertIn("is_stunned_hyrule_ganon(victim)", fight_source)
        self.assertIn("victim->position = pos_stunned", fight_source)
        self.assertIn("victim->hit <= 1", fight_source)
        reform_source = fight_source.split(
            "static void reform_hyrule_ganon", 1
        )[1].split("static int hyrule_dungeon_entrance", 1)[0]
        self.assertIn("stop_fighting( victim, true )", reform_source)
        self.assertNotIn("stop_fighting( victim, false )", reform_source)
        self.assertLess(
            reform_source.index("stop_fighting( victim, true )"),
            reform_source.index("if ( already_stunned )"),
        )
        self.assertIn("flashes bright red", reform_source)
        self.assertIn("shoot ganon", reform_source)

        shoot_source = fight_source.split(
            "void do_shoot", 1
        )[1].split("void do_steel_fist", 1)[0]
        self.assertIn("is_silver_arrow_weapon(obj)", shoot_source)
        self.assertIn("ch->level < hyrule_silver_arrow_level", shoot_source)
        self.assertIn("!is_stunned_hyrule_ganon(victim)", shoot_source)
        self.assertIn("gsn_archery, dam_pierce", shoot_source)
        self.assertLess(
            shoot_source.index("is_silver_arrow_weapon(obj)"),
            shoot_source.index("obj->value[0] != weapon_bow"),
        )

        object_source = Path("src/act_obj.c").read_text(encoding="utf-8").lower()
        self.assertIn("obj_vnum_hyrule_silver_arrow", object_source)
        self.assertIn("obj->level = hyrule_silver_arrow_level", object_source)

        look_source = Path("src/act_info.c").read_text(encoding="utf-8").lower()
        self.assertIn("is_red_hyrule_ganon", look_source)
        self.assertIn("ganon's body is blazing bright red", look_source)
        self.assertIn("wield the silver arrow and type shoot ganon", look_source)
        self.assertIn('toc_strlcat( buf, "{0c}"', look_source)

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
