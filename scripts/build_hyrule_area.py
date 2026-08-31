"""Generate ``area/hyrule.are`` from the First Quest manifest.

The existing object and mobile catalog is retained so builders can continue to
edit its balance in OLC. Rooms and resets are generated because their topology is
reference-derived and should never drift independently from the tests.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "hyrule_first_quest.json"
DEFAULT_AREA = ROOT / "area" / "hyrule.are"

DIRECTION_NUMBERS = {
    "north": 0, "east": 1, "south": 2, "west": 3, "up": 4, "down": 5,
}
OPPOSITE_DIRECTIONS = {
    "north": "south", "east": "west", "south": "north", "west": "east",
    "up": "down", "down": "up",
}

NEW_MOBILE_VNUMS = set(range(30335, 30346))
NEW_OBJECT_VNUMS = (
    set(range(30500, 30515))
    | {30520}
    | set(range(30530, 30582))
)

BOSS_MOBS = {
    1: 30222, 2: 30218, 3: 30305, 4: 30307, 5: 30309,
    6: 30223, 7: 30314, 8: 30316, 9: 30225,
}
BOSS_GEAR = {
    1: 30339, 2: 30349, 3: 30359, 4: 30369, 5: 30374,
    6: 30378, 7: 30382, 8: 30385, 9: 30388,
}
GANON_GOLDEN_KEY_VNUM = 30243
ENEMY_MOBS = {
    "aquamentus": 30222,
    "blade_trap": 30337,
    "blue_darknut": 30315,
    "blue_goriya": 30312,
    "blue_wizzrobe": 30221,
    "bubble": 30304,
    "digdogger": 30309,
    "dodongo": 30218,
    "ganon": 30225,
    "gel": 30300,
    "gibdo": 30219,
    "gleeok": 30307,
    "gohma": 30223,
    "keese": 30211,
    "like_like": 30215,
    "manhandla": 30305,
    "moldorm": 30303,
    "old_man": 30228,
    "patra": 30318,
    "pols_voice": 30308,
    "princess_zelda": 30338,
    "red_darknut": 30220,
    "red_goriya": 30214,
    "red_lanmola": 30317,
    "red_wizzrobe": 30310,
    "rope": 30302,
    "stalfos": 30212,
    "vire": 30306,
    "wallmaster": 30301,
    "zol": 30213,
    "blue_lanmola": 30217,
}

WORLD_MOBS = {
    "armos": 30336,
    "fairy": 30216,
    "falling_rock": 30337,
    "ghini": 30330,
    "peahat": 30335,
    "zora": 30321,
}

SHOP_KEEPERS = {
    "regular_bomb": 30339,
    "regular_candle": 30340,
    "deluxe_shield": 30341,
    "deluxe_ring": 30342,
    "potion": 30343,
}
SHOP_INVENTORY = {
    30339: [30541, 30542, 30543],
    30340: [30544, 30545, 30546],
    30341: [30547, 30548, 30549],
    30342: [30550, 30551, 30552],
    30343: [30553, 30554],
}

PUZZLE_OBJECTS = {
    "bomb": {"north": 30502, "east": 30503, "south": 30504, "west": 30505, "down": 30509},
    "burn": 30506,
    "recorder": 30507,
    "feed": 30508,
    "push": 30513,
    "armos": 30514,
    "bracelet": 30564,
}

GEAR_STAGES = {
    0: (30440, range(30320, 30330)),
    1: (30441, range(30330, 30340)),
    2: (30443, range(30340, 30350)),
    3: (30445, range(30350, 30360)),
    4: (30447, range(30360, 30370)),
    5: (30449, range(30370, 30375)),
    6: (30451, range(30375, 30379)),
    7: (30453, range(30379, 30383)),
    8: (30455, range(30383, 30386)),
    9: (30520, range(30386, 30389)),
}


@dataclass
class ExitSpec:
    destination: int
    locks: int = 0
    key_vnum: int = 0
    keyword: str = ""
    description: str = ""


@dataclass
class RoomSpec:
    vnum: int
    name: str
    description: str
    flags: str = "N"
    sector: int = 2
    exits: dict[str, ExitSpec] = field(default_factory=dict)
    objects: list[int] = field(default_factory=list)
    puzzles: list[int] = field(default_factory=list)
    entities: dict[str, int] = field(default_factory=dict)
    boss_level: int | None = None


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def section(text: str, start: str, end: str) -> str:
    start_index = text.index(start) + len(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index].strip()


def strip_section_terminator(body: str, terminator: str) -> str:
    return re.sub(rf"(?:\r?\n)?{re.escape(terminator)}\s*$", "", body).rstrip()


def remove_records(body: str, vnums: set[int]) -> str:
    for vnum in sorted(vnums):
        body = re.sub(
            rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)",
            "",
            body,
        )
    return body.strip()


def replace_record(body: str, vnum: int, record: str) -> str:
    pattern = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)")
    if not pattern.search(body):
        raise ValueError(f"missing object record {vnum}")
    return pattern.sub(record.rstrip() + "\n", body, count=1)


def mobile_record(
    vnum: int,
    keywords: str,
    short: str,
    long: str,
    description: str,
    level: int,
    race: str = "human",
    act_flags: str = "AF",
) -> str:
    hit_dice = f"{max(2, level // 4)}d10+{max(20, level * level)}"
    damage_dice = f"{max(1, level // 15 + 1)}d6+{max(2, level // 2)}"
    return f"""#{vnum}
{keywords}~
{short}~
{long}
~
{description}
~
{race}~
{act_flags} 0 0 S
{level} {max(1, level // 2)} {hit_dice} 1d1+0 {damage_dice} 6
0 0 0 0
0 0 0 0
8 8 0 0
AHMV ABCDEFGHIJK M 0"""


def new_mobile_records() -> str:
    return "\n".join([
        mobile_record(
            30335, "peahat spinning plant", "a Peahat",
            "A Peahat skims over the ground on whirling leaves.",
            "Its petals spin like a rotor, carrying a thorny core just out of reach.", 8, "plant",
        ),
        mobile_record(
            30336, "armos statue knight", "an awakened Armos",
            "An Armos statue has awakened and blocks the path.",
            "Ancient stone plates grind together as the guardian advances.", 48,
        ),
        mobile_record(
            30337, "blade trap falling rock hazard", "a dungeon hazard",
            "A stone hazard tears across the room.",
            "It moves with the merciless rhythm of Hyrule's oldest defenses.", 45,
        ),
        mobile_record(
            30338, "princess zelda", "Princess Zelda",
            "Princess Zelda waits beside the completed Triforce.",
            "Zelda stands free at last, the light of the Triforce reflected in her eyes.", 70,
            act_flags="AB",
        ),
        mobile_record(
            30339, "hyrule merchant bombs arrows", "a Hyrule merchant",
            "A Hyrule merchant displays shields, bombs, and arrows.",
            "The cave merchant watches over a carefully priced spread of adventuring supplies.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30340, "hyrule merchant candle key", "a Hyrule merchant",
            "A Hyrule merchant displays a candle, a key, and a shield.",
            "The cave merchant waits patiently beside three familiar wares.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30341, "hyrule merchant deluxe shield", "a secret Hyrule merchant",
            "A secret Hyrule merchant offers hard-won supplies.",
            "This merchant's hidden grotto offers a better bargain than the open caves.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30342, "hyrule merchant blue ring", "a blue-ring merchant",
            "A blue-ring merchant guards rare equipment.",
            "The merchant gestures proudly toward a blue ring and two practical supplies.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30343, "hyrule potion woman", "an old potion woman",
            "An old woman waits silently behind two colored potions.",
            "She studies visitors for proof that the royal family sent them.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30344, "hyrule door repair elder", "a stern old man",
            "A stern old man waits beside a freshly repaired door.",
            "He keeps a precise ledger of every visitor who has paid the repair charge.",
            50, act_flags="ABMV",
        ),
        mobile_record(
            30345, "hyrule money game elder", "a gambling old man",
            "An old man waits behind three concealed rupee signs.",
            "He offers the same risky money-making game found across the First Quest.",
            50, act_flags="ABMV",
        ),
    ])


def object_record(
    vnum: int,
    keywords: str,
    short: str,
    long: str,
    material: str,
    item_line: str,
    values: str,
    level: int = 0,
    weight: int = 0,
    cost: int = 0,
    extras: str = "",
) -> str:
    record = f"""#{vnum}
{keywords}~
{short}~
{long}~
{material}~
{item_line}
{values}
{level} {weight} {cost} P"""
    if extras:
        record += "\n" + extras.strip()
    return record


def silver_arrow_object_record() -> str:
    description = """E
silver arrow~
The silver metal shines with a light that does not fade.  The Silver Arrow
requires level 54; any character level 54 or higher can wield and use it, and
immortal status is not required.
Against Ganon, normal strikes with the wielded Silver Arrow use full weapon
mastery and tear away at least one tenth of his full vitality.  Other weapons,
spells, poison, and lingering effects can wound him, but no normal attack can
kill him.
When Ganon collapses at one hit point and flashes bright red, keep the Silver
Arrow wielded and type SHOOT GANON.  That final shot always finds him, does not
require the ARCHERY skill, and does not consume the Silver Arrow.
~"""
    return object_record(
        30218,
        "silver arrow",
        "a silver arrow",
        "A single silver arrow lies here.",
        "silver",
        "5 ABGUV AN",
        "0 4 14 2 0",
        54,
        1,
        5000,
        description,
    )


def map_art(dungeon: dict[str, Any]) -> str:
    rooms = {room["coordinate"]: room for room in dungeon["rooms"]}
    major_sources = {cellar["source_coordinate"] for cellar in dungeon["cellars"]}
    symbols = {
        dungeon["entrance_coordinate"]: "E",
        dungeon["map_coordinate"]: "M",
        dungeon["compass_coordinate"]: "C",
        dungeon["boss_coordinate"]: "B",
        dungeon["goal_coordinate"]: "T",
    }
    for coordinate in major_sources:
        symbols.setdefault(coordinate, "I")
    lines = [f"Level {dungeon['level']} - {dungeon['title']}", "N", "^"]
    for row in range(8, 0, -1):
        line = []
        for column in range(8):
            coordinate = f"{chr(ord('A') + column)}{row}"
            line.append(symbols.get(coordinate, "#" if coordinate in rooms else " "))
        lines.append(" ".join(line).rstrip())
    lines.append("E entrance  M map  C compass  I item  B boss  T goal")
    return "\n".join(lines)


def map_object_record(dungeon: dict[str, Any], compass: bool) -> str:
    level = dungeon["level"]
    title = dungeon["title"].removeprefix("The ")
    vnum = (30488 if compass else 30479) + level
    kind = "compass" if compass else "map"
    opcode = 91 if compass else 90
    values = f"{opcode} {dungeon['boss_vnum']} {dungeon['first_room_vnum']} {dungeon['last_room_vnum']} {level}"
    extras = ""
    if not compass:
        extras = f"E\n{dungeon['title'].lower()} map parchment~\n{map_art(dungeon)}\n~"
    return object_record(
        vnum,
        f"level {level} {title.lower()} dungeon {kind}",
        f"the {title} dungeon {kind}",
        f"The {title}'s {kind} waits here.",
        "paper" if not compass else "gold",
        "28 G AO",
        values,
        dungeon["recommended_levels"][0],
        1,
        1000 + level * 100,
        extras,
    )


def ganon_relic_records() -> list[str]:
    return [
        object_record(
            30577,
            "heros hero tunic green courage ganon relic",
            "the Hero's Tunic",
            "The Hero's Tunic rests here, bright as Hyrule Field.",
            "cloth",
            "9 G AD",
            "15 15 15 11 0",
            54,
            8,
            18000,
            """E
hero tunic green courage~
This green tunic carries the courage of every hero who stood against darkness.
While worn, it restores up to 5 percent of your maximum health after you
personally kill an NPC, capped at twice that foe's level.
~
A
5 2
A
13 100
A
24 -2""",
        ),
        object_record(
            30578,
            "blue ring hyrule wisdom ganon relic",
            "the Blue Ring of Hyrule",
            "A blue ring shines here with a cool protective light.",
            "gold",
            "9 G AB",
            "8 8 8 6 0",
            54,
            1,
            16000,
            """E
blue ring hyrule wisdom~
The sapphire band turns danger aside with quiet wisdom. While worn, it reduces
all damage you take by 10 percent. Its ward does not stack with the Red Ring or
a second Blue Ring; only the strongest ring ward applies.
~
A
13 60
A
12 40
A
24 -1""",
        ),
        object_record(
            30579,
            "red ring hyrule power ganon relic",
            "the Red Ring of Hyrule",
            "A red ring burns here with a fierce protective light.",
            "gold",
            "9 G AB",
            "12 12 12 9 0",
            58,
            1,
            24000,
            """E
red ring hyrule power~
The ruby band holds the hard-won power of Death Mountain. While worn, it
reduces all damage you take by 20 percent. Its ward does not stack with the
Blue Ring or a second Red Ring; only the strongest ring ward applies.
~
A
5 2
A
13 100
A
24 -3""",
        ),
        object_record(
            30580,
            "mirror shield hyrule light ganon relic",
            "the Mirror Shield",
            "A polished Mirror Shield reflects an impossible point of light.",
            "silver",
            "9 G AJ",
            "16 16 16 14 0",
            56,
            12,
            22000,
            """E
mirror shield hyrule light~
The shield's flawless face turns sorcery and elemental force back toward the
dark. While worn, it reduces nonphysical damage by 15 percent. This protection
can combine with one Blue or Red Ring ward.
~
A
24 -4
A
17 -5""",
        ),
        object_record(
            30581,
            "pegasus boots hyrule speed ganon relic",
            "the Pegasus Boots",
            "A pair of wing-crested boots waits here, light as air.",
            "leather",
            "9 G AG",
            "12 12 12 8 0",
            55,
            5,
            19000,
            """E
pegasus boots hyrule speed~
These wing-crested boots make the road race beneath their wearer. While worn,
they reduce movement spent traveling on foot by 25 percent, to a minimum cost
of one movement point. They do not reduce a mount's movement cost.
~
A
2 2
A
14 150""",
        ),
    ]


def new_object_records(manifest: dict[str, Any]) -> str:
    objects = [
        object_record(30500, "letter parchment zelda", "Princess Zelda's letter", "A sealed royal letter lies here.", "paper", "8 G AO", "0 0 0 0 0", 1, 1, 100),
        object_record(30501, "heart container", "a Heart Container", "A pulsing Heart Container floats here.", "crystal", "9 G AO", "0 0 0 0 0", 1, 1, 1000, "A\n13 25"),
    ]
    for direction, vnum in zip(("north", "east", "south", "west"), range(30502, 30506)):
        objects.append(object_record(
            vnum, f"cracked wall {direction}", f"a cracked {direction} wall",
            f"Fine cracks mark the {direction} wall.", "stone", "31 UV 0",
            f"12 0 {DIRECTION_NUMBERS[direction]} 1 9",
        ))
    objects.extend([
        object_record(30506, "bush tree burn", "a dry green bush", "A strangely dry bush blocks a hidden opening.", "wood", "31 UV 0", "11 0 5 1 9"),
        object_record(30507, "pool recorder melody", "a still pool", "The water waits for an ancient melody.", "water", "31 UV 0", "13 0 5 1 9"),
        object_record(30508, "hungry goriya guardian", "a hungry Goriya guardian", "A hungry Goriya refuses to leave the doorway.", "flesh", "31 UV 0", "14 0 0 1 9"),
        object_record(30509, "cracked floor opening", "a cracked stone floor", "Fine cracks mark a concealed descent.", "stone", "31 UV 0", "12 0 5 1 9"),
        object_record(30510, "ten rupees gold money coins", "10 rupees", "Ten rupees gleam here.", "gold", "20 0 A", "10 2 0 0 0", 1, 0, 10),
        object_record(30511, "thirty rupees gold money coins", "30 rupees", "Thirty rupees gleam here.", "gold", "20 0 A", "30 2 0 0 0", 1, 0, 30),
        object_record(30512, "hundred rupees gold money coins", "100 rupees", "One hundred rupees gleam here.", "gold", "20 0 A", "100 2 0 0 0", 1, 0, 100),
        object_record(30513, "movable stone block", "a movable stone block", "Scrape marks show that this block can be pushed.", "stone", "31 UV 0", "4 0 5 1 9"),
        object_record(30514, "sleeping armos statue", "a sleeping Armos statue", "An Armos statue rests over something hidden.", "stone", "31 UV 0", "4 0 5 1 9"),
        object_record(30520, "death mountain gear chest", "Death Mountain's equipment chest", "A black-and-gold chest waits here.", "iron", "15 0 0", "250 A 0 0 0", 0, 25, 0),
    ])

    world_vnums = {room["coordinate"]: room["vnum"] for room in manifest["overworld"]["rooms"]}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] == "door_repair":
                coordinate = landmark["zelda_coordinate"].lower()
                objects.append(object_record(
                    landmark["token_vnum"],
                    f"door repair receipt {coordinate}",
                    f"a door-repair receipt for {landmark['zelda_coordinate']}",
                    "A small receipt records a paid First Quest door-repair charge.",
                    "paper", "8 HUV A", "0 0 0 0 0",
                ))
    objects.append(object_record(
        30564, "warp armos stone bracelet", "a movable warp stone",
        "A heavy stone covers a Power Bracelet road.",
        "stone", "31 UV 0", "4 0 5 1 9",
    ))
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] != "warp_hall":
                continue
            for route in landmark["routes"]:
                destination = route["destination"]
                road = route["road"]
                objects.append(object_record(
                    route["object_vnum"],
                    f"{road} road warp hall portal",
                    f"the {road} warp road",
                    f"The {road} road shimmers toward another corner of Hyrule.",
                    "stone", "30 GOV 0",
                    f"6 {world_vnums[destination]} 0 0 30276",
                ))
    for index, dungeon in enumerate(manifest["dungeons"][:8]):
        title = dungeon["title"].removeprefix("The ")
        objects.append(object_record(
            30530 + index,
            f"return light level {dungeon['level']}",
            f"the {title}'s returning light",
            "A triangular light offers a way back to the surface.",
            "energy", "30 GOV 0", f"5 {world_vnums[dungeon['overworld_coordinate']]} 0 0 0",
        ))
    level_four = manifest["dungeons"][3]
    objects.extend([
        object_record(30538, "raft level four crossing", "a waiting dungeon raft", "A raft waits at the water's edge.", "wood", "30 GOV 0", f"6 {level_four['entrance_vnum']} 0 0 30411"),
        object_record(30539, "raft heart crossing", "a waiting heart raft", "A raft waits to cross the open water.", "wood", "30 GOV 0", "6 30657 0 0 30411"),
        object_record(30540, "stepladder heart crossing", "a narrow water crossing", "A gap in the water can be crossed with the stepladder.", "water", "30 GOV 0", "6 30658 0 0 30412"),
        object_record(30541, "magical shield shop", "a Magical Shield", "A Magical Shield is displayed for 130 rupees.", "steel", "9 N AJ", "5 5 5 3 0", 15, 8, 130, "A\n17 -5"),
        object_record(30542, "bombs bomb satchel shop", "a satchel of bombs", "A bomb satchel is displayed for 20 rupees.", "leather", "15 N AO", "BCEFHIJ A 0 0 0", 5, 2, 20),
        object_record(30543, "arrows arrow quiver shop", "a quiver of arrows", "A quiver of arrows is displayed for 80 rupees.", "wood", "8 N AO", "0 0 0 0 0", 8, 2, 80),
        object_record(30544, "magical shield shop", "a Magical Shield", "A Magical Shield is displayed for 160 rupees.", "steel", "9 N AJ", "5 5 5 3 0", 15, 8, 160, "A\n17 -5"),
        object_record(30545, "key small shop", "a small key", "A small key is displayed for 100 rupees.", "iron", "18 N A", "0 0 0 0 0", 1, 1, 100),
        object_record(30546, "blue candle shop", "a Blue Candle", "A Blue Candle is displayed for 60 rupees.", "wax", "1 N AO", "0 0 999 0 0", 5, 2, 60),
        object_record(30547, "magical shield bargain shop", "a Magical Shield", "A Magical Shield is displayed for 90 rupees.", "steel", "9 N AJ", "5 5 5 3 0", 15, 8, 90, "A\n17 -5"),
        object_record(30548, "food bait shop", "enemy bait", "Enemy bait is displayed for 100 rupees.", "meat", "19 N A", "H 0 0 0 0", 55, 3, 100),
        object_record(30549, "heart recovery shop", "a Recovery Heart", "A Recovery Heart is displayed for 10 rupees.", "crystal", "10 N AO", "10 28 0 0 0", 1, 1, 10),
        object_record(30550, "key small bargain shop", "a small key", "A small key is displayed for 80 rupees.", "iron", "18 N A", "0 0 0 0 0", 1, 1, 80),
        object_record(30551, "blue ring shop", "the Blue Ring", "The Blue Ring is displayed for 250 rupees.", "gold", "9 N AB", "5 5 5 3 0", 35, 1, 250, "A\n13 15"),
        object_record(30552, "food bait bargain shop", "enemy bait", "Enemy bait is displayed for 60 rupees.", "meat", "19 N A", "H 0 0 0 0", 55, 3, 60),
        object_record(30553, "blue life potion medicine shop", "a blue Life Potion", "A blue Life Potion is displayed for 40 rupees.", "glass", "10 N AO", "30 28 28 81 0", 1, 2, 40),
        object_record(30554, "red second potion medicine shop", "a red 2nd Potion", "A red 2nd Potion is displayed for 68 rupees.", "glass", "10 N AO", "30 81 81 81 0", 1, 2, 68),
    ])
    objects.extend(ganon_relic_records())
    return "\n".join(objects)


def world_region(coordinate: str) -> tuple[str, int]:
    column = ord(coordinate[0]) - ord("A")
    row = int(coordinate[1:])
    if row >= 7:
        return "Death Mountain", 5
    if column <= 4 and row >= 4:
        return "the western highlands", 4
    if column <= 5 and row <= 3:
        return "the Lost Woods", 3
    if column >= 12 and row <= 3:
        return "the eastern desert", 10
    if column >= 12:
        return "Lake Hylia's shore", 2
    return "Hyrule Field", 2


def world_room_name(room: dict[str, Any]) -> str:
    landmarks = room["landmarks"]
    for landmark in landmarks:
        if landmark["type"] == "start":
            return "The First Quest Begins"
        if landmark["type"] == "dungeon":
            return f"Before Level {landmark['level']}: {DUNGEON_TITLE_CACHE[landmark['level']]}"
        if landmark["type"] == "fairy_fountain":
            return "A Fairy Fountain"
    region, _ = world_region(room["coordinate"])
    return f"{region} [{room['coordinate']}]"


def world_room_description(room: dict[str, Any]) -> str:
    region, _ = world_region(room["coordinate"])
    entities = [name.replace("_", " ") for name, count in room["entities"].items() if count]
    danger = ", ".join(entities[:4]) if entities else "the wind moving over an empty screen"
    landmark_text = ""
    if room["landmarks"]:
        names = [
            item.get("name")
            or (f"Level {item['level']}" if "level" in item else item["type"].replace("_", " "))
            for item in room["landmarks"]
        ]
        landmark_text = " The landscape conceals " + ", ".join(names) + "."
    return (
        f"This is First Quest screen {room['coordinate']}, one full crossing of {region}. "
        f"The visible threats are {danger}.{landmark_text}"
    )


def choose_world_mob(entity: str, recommended_level: int) -> int | None:
    if entity in WORLD_MOBS:
        return WORLD_MOBS[entity]
    if entity == "red_octorok":
        return 30320 if recommended_level < 15 else (30200 if recommended_level < 45 else 30329)
    if entity == "blue_octorok":
        return 30200 if recommended_level < 18 else 30201
    if entity == "red_moblin":
        return 30226 if recommended_level < 15 else 30202
    if entity == "blue_moblin":
        return 30202 if recommended_level < 28 else 30203
    if entity == "red_tektite":
        return 30322 if recommended_level < 25 else 30205
    if entity == "blue_tektite":
        return 30205
    if entity == "red_leever":
        return 30323 if recommended_level < 28 else 30206
    if entity == "blue_leever":
        return 30207
    if entity == "red_lynel":
        return 30327 if recommended_level < 44 else 30328
    if entity == "blue_lynel":
        return 30208
    return None


def add_two_way_exit(
    rooms: dict[int, RoomSpec],
    source: int,
    direction: str,
    destination: int,
    locks: int = 0,
    key_vnum: int = 0,
    keyword: str = "",
) -> None:
    rooms[source].exits[direction] = ExitSpec(destination, locks, key_vnum, keyword)
    reverse = OPPOSITE_DIRECTIONS[direction]
    rooms[destination].exits[reverse] = ExitSpec(source, locks, key_vnum, keyword)


def build_rooms(manifest: dict[str, Any]) -> tuple[dict[int, RoomSpec], dict[str, int]]:
    rooms: dict[int, RoomSpec] = {}
    world_vnums = {room["coordinate"]: room["vnum"] for room in manifest["overworld"]["rooms"]}

    for room in manifest["overworld"]["rooms"]:
        _, sector = world_region(room["coordinate"])
        spec = RoomSpec(
            room["vnum"], world_room_name(room), world_room_description(room), "N", sector,
        )
        for direction, exit_data in room["exits"].items():
            gate = exit_data["gate"]
            keyword = "" if gate == "open" else f"{gate} crossing"
            description = "" if gate == "open" else f"The route requires the {gate}."
            spec.exits[direction] = ExitSpec(exit_data["to_vnum"], keyword=keyword, description=description)
        for entity, count in room["entities"].items():
            mob_vnum = choose_world_mob(entity, room["recommended_level"])
            if mob_vnum is not None:
                spec.entities[str(mob_vnum)] = spec.entities.get(str(mob_vnum), 0) + count
        rooms[spec.vnum] = spec

    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        for room in dungeon["rooms"]:
            entity_names = ", ".join(name.replace("_", " ") for name in room["entities"]) or "silence"
            spec = RoomSpec(
                room["vnum"], room["name"],
                f"This chamber preserves First Quest room {room['coordinate']} of {dungeon['title']}. "
                f"Its original encounter is {entity_names}.",
                "ADN", 11,
                objects=list(room["items"]),
                entities={str(ENEMY_MOBS[name]): count for name, count in room["entities"].items() if name in ENEMY_MOBS},
                boss_level=level if room["role"] == "boss" else None,
            )
            if room["role"] == "boss":
                spec.entities = {str(BOSS_MOBS[level]): 1}
            for direction, exit_data in room["exits"].items():
                door_type = exit_data["type"]
                locks, key_vnum, keyword = 0, 0, ""
                if door_type == "locked":
                    locks, key_vnum, keyword = 5, 30227, "locked dungeon door"
                elif door_type == "shutter":
                    locks, keyword = 1, "shutter"
                elif door_type == "bombable":
                    locks, keyword = 4, f"cracked {direction} wall"
                spec.exits[direction] = ExitSpec(exit_data["to_vnum"], locks, key_vnum, keyword)
            rooms[spec.vnum] = spec

        for cellar in dungeon["cellars"]:
            rooms[cellar["vnum"]] = RoomSpec(
                cellar["vnum"], f"Level {level}: {cellar['name']}",
                f"A narrow underground passage leads to {dungeon['title']}'s hidden treasure.",
                "ADN", 11, objects=[cellar["item_vnum"]],
            )
            add_two_way_exit(
                rooms, cellar["source_vnum"], "down", cellar["vnum"],
                locks=4, keyword="block stair",
            )
            rooms[cellar["source_vnum"]].puzzles.append(PUZZLE_OBJECTS["push"])

        for stair in dungeon["stair_links"]:
            add_two_way_exit(rooms, stair["from_vnum"], "up", stair["to_vnum"])

    # Visible and hidden overworld entrances.
    for dungeon in manifest["dungeons"]:
        world_vnum = world_vnums[dungeon["overworld_coordinate"]]
        entry_vnum = dungeon["entrance_vnum"]
        landmark = next(
            item for item in next(room for room in manifest["overworld"]["rooms"] if room["vnum"] == world_vnum)["landmarks"]
            if item.get("type") == "dungeon" and item.get("level") == dungeon["level"]
        )
        if dungeon["level"] == 4:
            rooms[world_vnum].objects.append(30538)
            rooms[entry_vnum].exits["up"] = ExitSpec(world_vnum)
        else:
            puzzle = landmark.get("puzzle")
            locks = 4 if puzzle else 0
            keyword = f"{puzzle or 'stone'} dungeon entrance"
            if dungeon["level"] == 9:
                keyword = f"triforce {keyword}"
            add_two_way_exit(rooms, world_vnum, "down", entry_vnum, locks=locks, keyword=keyword)
            if puzzle:
                puzzle_vnum = PUZZLE_OBJECTS[puzzle]
                rooms[world_vnum].puzzles.append(
                    puzzle_vnum["down"] if isinstance(puzzle_vnum, dict) else puzzle_vnum
                )

    cave_specs = [
        (30650, "H1", "Wooden Sword Cave", 30219, None),
        (30651, "K8", "White Sword Cave", 30251, None),
        (30652, "B6", "Master Sword Grave", 30200, "push"),
        (30653, "O8", "Letter Cave", 30500, None),
        (30654, "L1", "Bombed Heart Cave", 30501, "bomb"),
        (30655, "M6", "Mountain Heart Cave", 30501, "bomb"),
        (30656, "H4", "Burned Heart Cave", 30501, "burn"),
        (30657, "P6", "Raft Heart Island", 30501, "portal"),
        (30658, "P3", "Stepladder Heart Ledge", 30501, "portal"),
        (30659, "E2", "The Secret Return Tree", 30211, "burn"),
        (30674, "E6", "Power Bracelet Alcove", 30276, "armos"),
    ]
    for vnum, coordinate, name, object_vnum, puzzle in cave_specs:
        rooms[vnum] = RoomSpec(
            vnum, name,
            "A compact hidden chamber preserves one of the First Quest's original rewards.",
            "ADN", 11, objects=[object_vnum],
        )
        world_vnum = world_vnums[coordinate]
        if puzzle == "portal":
            rooms[world_vnum].objects.append(30539 if coordinate == "P6" else 30540)
            rooms[vnum].exits["up"] = ExitSpec(world_vnum)
        else:
            locks = 4 if puzzle else 0
            add_two_way_exit(rooms, world_vnum, "down", vnum, locks=locks, keyword=f"{puzzle or 'cave'} opening")
            if puzzle:
                puzzle_vnum = PUZZLE_OBJECTS[puzzle]
                rooms[world_vnum].puzzles.append(
                    puzzle_vnum["down"] if isinstance(puzzle_vnum, dict) else puzzle_vnum
                )

    money_objects = {10: 30510, 30: 30511, 100: 30512}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] != "rupee":
                continue
            cave_vnum = landmark["room_vnum"]
            amount = landmark["amount"]
            puzzle = landmark.get("puzzle")
            rooms[cave_vnum] = RoomSpec(
                cave_vnum,
                f"A Secret of {amount} Rupees",
                "A hidden First Quest grotto holds the reward revealed on this screen.",
                "ADN", 11, objects=[money_objects[amount]],
            )
            world_vnum = room["vnum"]
            add_two_way_exit(
                rooms, world_vnum, "down", cave_vnum,
                locks=4 if puzzle else 0,
                keyword=f"{puzzle or 'hidden'} rupee grotto",
            )
            if puzzle:
                puzzle_vnum = PUZZLE_OBJECTS[puzzle]
                rooms[world_vnum].puzzles.append(
                    puzzle_vnum["down"] if isinstance(puzzle_vnum, dict) else puzzle_vnum
                )

    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] not in {"shop", "potion_shop"}:
                continue
            shop_kind = landmark["shop_kind"]
            shop_vnum = landmark["room_vnum"]
            keeper_vnum = SHOP_KEEPERS[shop_kind]
            potion_shop = landmark["type"] == "potion_shop"
            rooms[shop_vnum] = RoomSpec(
                shop_vnum,
                "A First Quest Potion Shop" if potion_shop else "A First Quest Item Shop",
                (
                    "An old woman waits for Princess Zelda's letter before offering her medicines."
                    if potion_shop else
                    "Three wares are arranged exactly as they were in this First Quest shop."
                ),
                "ADN", 11, entities={str(keeper_vnum): 1},
            )
            world_vnum = room["vnum"]
            puzzle = landmark.get("puzzle")
            direction = landmark.get("direction", "down")
            add_two_way_exit(
                rooms, world_vnum, direction, shop_vnum,
                locks=4 if puzzle else 0,
                keyword=f"{puzzle or 'open'} shop entrance",
            )
            if puzzle:
                puzzle_vnum = PUZZLE_OBJECTS[puzzle]
                rooms[world_vnum].puzzles.append(
                    puzzle_vnum[direction] if isinstance(puzzle_vnum, dict) else puzzle_vnum
                )

    attraction_details = {
        "door_repair": (
            "A Door-Repair Charge",
            "A stern old man demands the First Quest's one-time 20-rupee repair charge.",
            30344,
        ),
        "gamble": (
            "A Money-Making Game",
            "Three concealed amounts wait for anyone willing to gamble ten rupees.",
            30345,
        ),
        "warp_hall": (
            "A Power Bracelet Warp Hall",
            "Three stone roads connect the four corners of the First Quest overworld.",
            None,
        ),
    }
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            attraction_type = landmark["type"]
            if attraction_type not in attraction_details:
                continue
            name, description, keeper_vnum = attraction_details[attraction_type]
            attraction_vnum = landmark["room_vnum"]
            rooms[attraction_vnum] = RoomSpec(
                attraction_vnum,
                name,
                description,
                "ADN", 11,
                objects=[route["object_vnum"] for route in landmark.get("routes", [])],
                entities={} if keeper_vnum is None else {str(keeper_vnum): 1},
            )
            world_vnum = room["vnum"]
            puzzle = landmark.get("puzzle")
            add_two_way_exit(
                rooms, world_vnum, "down", attraction_vnum,
                locks=4 if puzzle else 0,
                keyword=f"{puzzle or 'open'} {attraction_type.replace('_', ' ')} entrance",
            )
            if puzzle:
                puzzle_vnum = PUZZLE_OBJECTS[puzzle]
                rooms[world_vnum].puzzles.append(
                    puzzle_vnum["down"] if isinstance(puzzle_vnum, dict) else puzzle_vnum
                )

    rooms[world_vnums["D4"]].objects.append(30225)
    rooms[world_vnums["J5"]].objects.append(30225)

    # Lost Woods: north, west, south, west. East always escapes the maze.
    lost_woods = world_vnums["E2"]
    lost_woods_east = rooms[lost_woods].exits.get("east")
    lost_woods_west = rooms[lost_woods].exits.get("west")
    for index, vnum in enumerate(range(30750, 30753), start=1):
        rooms[vnum] = RoomSpec(
            vnum, f"The Lost Woods [{index}/3]",
            "The trees repeat with impossible precision; only the old route continues.", "N", 3,
        )
        if lost_woods_east:
            rooms[vnum].exits["east"] = lost_woods_east
    rooms[lost_woods].exits["north"] = ExitSpec(30750)
    rooms[30750].exits["west"] = ExitSpec(30751)
    rooms[30751].exits["south"] = ExitSpec(30752)
    if lost_woods_west:
        rooms[30752].exits["west"] = lost_woods_west
    for vnum in (lost_woods, 30750, 30751, 30752):
        for direction in ("north", "west", "south"):
            rooms[vnum].exits.setdefault(direction, ExitSpec(lost_woods))

    # Lost Hills requires five consecutive northward screen crossings.
    lost_hills = world_vnums["H7"]
    north_destination = rooms[lost_hills].exits["north"].destination
    previous = lost_hills
    for index, vnum in enumerate(range(30753, 30757), start=1):
        rooms[vnum] = RoomSpec(
            vnum, f"The Lost Hills [{index}/4]",
            "The same steep ridge rises again. The northern route is the only progress.", "N", 5,
        )
        rooms[previous].exits["north"] = ExitSpec(vnum)
        previous = vnum
    rooms[previous].exits["north"] = ExitSpec(north_destination)
    for vnum in range(30753, 30757):
        for direction in ("east", "south", "west"):
            if direction in rooms[lost_hills].exits:
                rooms[vnum].exits[direction] = rooms[lost_hills].exits[direction]

    # The Hungry Goriya and Ganon use their canonical gates.
    level_seven = manifest["dungeons"][6]
    level_seven_rooms = {room["coordinate"]: room["vnum"] for room in level_seven["rooms"]}
    hungry_room = level_seven_rooms["A6"]
    if "north" in rooms[hungry_room].exits:
        rooms[hungry_room].exits["north"].locks = 4
        rooms[hungry_room].exits["north"].keyword = "hungry guardian passage"
        rooms[hungry_room].puzzles.append(PUZZLE_OBJECTS["feed"])

    level_nine = manifest["dungeons"][8]
    boss_vnum, goal_vnum = level_nine["boss_vnum"], level_nine["goal_vnum"]
    add_two_way_exit(
        rooms, boss_vnum, "north", goal_vnum,
        locks=5, key_vnum=GANON_GOLDEN_KEY_VNUM, keyword="golden door",
    )
    rooms[goal_vnum].flags = "ADKN"
    rooms[goal_vnum].objects.extend([30286, 30217])

    for dungeon in manifest["dungeons"][:8]:
        rooms[dungeon["goal_vnum"]].objects.append(30529 + dungeon["level"])

    # Gear is deliberately available throughout each band, not only as a final reward.
    rooms[30650].objects.append(GEAR_STAGES[0][0])
    for dungeon in manifest["dungeons"]:
        chest_vnum, _ = GEAR_STAGES[dungeon["level"]]
        map_room_vnum = next(room["vnum"] for room in dungeon["rooms"] if room["coordinate"] == dungeon["map_coordinate"])
        rooms[map_room_vnum].objects.append(chest_vnum)

    return rooms, world_vnums


def render_room(room: RoomSpec) -> str:
    lines = [f"#{room.vnum}", f"{room.name}~", room.description, "~", f"0 {room.flags} {room.sector}"]
    for direction, exit_spec in sorted(room.exits.items(), key=lambda item: DIRECTION_NUMBERS[item[0]]):
        lines.extend([
            f"D{DIRECTION_NUMBERS[direction]}",
            f"{exit_spec.description}~" if exit_spec.description else "~",
            f"{exit_spec.keyword}~" if exit_spec.keyword else "~",
            f"{exit_spec.locks} {exit_spec.key_vnum} {exit_spec.destination}",
        ])
    lines.append("S")
    return "\n".join(lines)


def render_resets(rooms: dict[int, RoomSpec], manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    boss_room_to_level = {dungeon["boss_vnum"]: dungeon["level"] for dungeon in manifest["dungeons"]}
    resonance_rooms = {manifest["dungeons"][4]["boss_vnum"]: 30430}
    mobile_limits = Counter(
        int(entity_vnum)
        for room in rooms.values()
        for entity_vnum, count in room.entities.items()
        for _ in range(count)
    )

    for room in sorted(rooms.values(), key=lambda item: item.vnum):
        for entity_vnum, count in sorted(room.entities.items(), key=lambda item: int(item[0])):
            for _ in range(count):
                lines.append(
                    f"M 0 {entity_vnum} {mobile_limits[int(entity_vnum)]} {room.vnum}"
                )
                for stock_vnum in SHOP_INVENTORY.get(int(entity_vnum), []):
                    lines.append(f"G 1 {stock_vnum} 100")
                if room.vnum in boss_room_to_level and int(entity_vnum) == BOSS_MOBS[boss_room_to_level[room.vnum]]:
                    level = boss_room_to_level[room.vnum]
                    lines.append(f"G 1 {BOSS_GEAR[level]} 100")
                    if level == 9:
                        lines.append(f"G 1 {GANON_GOLDEN_KEY_VNUM} 100")
        for object_vnum in room.objects:
            lines.append(f"O 0 {object_vnum} 0 {room.vnum}")
        for puzzle_vnum in room.puzzles:
            lines.append(f"O 0 {puzzle_vnum} 0 {room.vnum}")
        if room.vnum in resonance_rooms:
            lines.append(f"O 0 {resonance_rooms[room.vnum]} 0 {room.vnum}")

        for direction, exit_spec in sorted(room.exits.items(), key=lambda item: DIRECTION_NUMBERS[item[0]]):
            if exit_spec.locks:
                if exit_spec.key_vnum == GANON_GOLDEN_KEY_VNUM:
                    # The Golden Key gate is magical: keyed players may unlock
                    # it, while random area-reset traps and doorbash cannot
                    # turn the final progression gate into a dead end.
                    state = 3
                else:
                    state = 2 if exit_spec.locks == 5 else 1
                lines.append(f"D 0 {room.vnum} {DIRECTION_NUMBERS[direction]} {state}")
                if exit_spec.locks == 4 and exit_spec.keyword.startswith("cracked"):
                    puzzle_vnum = PUZZLE_OBJECTS["bomb"].get(direction)
                    if puzzle_vnum:
                        lines.append(f"O 0 {puzzle_vnum} 0 {room.vnum}")

    for stage, (chest_vnum, gear_vnums) in GEAR_STAGES.items():
        for gear_vnum in gear_vnums:
            lines.append(f"P 0 {gear_vnum} 0 {chest_vnum}")
    lines.append("O 0 30285 0 15068")
    lines.append("S")
    return "\n".join(lines)


def render_shops() -> str:
    lines = [
        f"{keeper_vnum} 0 0 0 0 0 100 75 0 23"
        for keeper_vnum in sorted(SHOP_INVENTORY)
    ]
    lines.append("0")
    return "\n".join(lines)


def build_area(manifest_path: Path, area_path: Path) -> None:
    global DUNGEON_TITLE_CACHE
    manifest = load_json(manifest_path)
    DUNGEON_TITLE_CACHE = {dungeon["level"]: dungeon["title"] for dungeon in manifest["dungeons"]}
    original = area_path.read_text(encoding="utf-8")
    header = original[:original.index("#MOBILES")].rstrip()
    mobile_body = strip_section_terminator(section(original, "#MOBILES", "#OBJECTS"), "#0")
    object_body = strip_section_terminator(section(original, "#OBJECTS", "#ROOMS"), "#0")
    specials_body = section(original, "#SPECIALS", "#RESETS")

    mobile_body = remove_records(mobile_body, NEW_MOBILE_VNUMS)
    object_body = remove_records(object_body, NEW_OBJECT_VNUMS)
    object_body = replace_record(object_body, 30218, silver_arrow_object_record())
    for dungeon in manifest["dungeons"]:
        object_body = replace_record(object_body, 30479 + dungeon["level"], map_object_record(dungeon, False))
        object_body = replace_record(object_body, 30488 + dungeon["level"], map_object_record(dungeon, True))

    rooms, _ = build_rooms(manifest)
    room_body = "\n".join(render_room(room) for room in sorted(rooms.values(), key=lambda item: item.vnum))
    resets = render_resets(rooms, manifest)

    output = (
        f"{header}\n\n#MOBILES\n{mobile_body}\n{new_mobile_records()}\n#0\n\n"
        f"#OBJECTS\n{object_body}\n{new_object_records(manifest)}\n#0\n\n"
        f"#ROOMS\n{room_body}\n#0\n\n"
        f"#SPECIALS\n{specials_body.strip()}\n\n"
        f"#RESETS\n{resets}\n\n"
        f"#SHOPS\n{render_shops()}\n\n#$\n"
    )
    area_path.write_text(output, encoding="utf-8", newline="\n")
    print(f"Wrote {area_path} with {len(rooms)} rooms and {len(resets.splitlines()) - 1} resets.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_area(args.manifest.resolve(), args.area.resolve())


if __name__ == "__main__":
    main()
