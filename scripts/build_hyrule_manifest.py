"""Build the checked-in Zelda First Quest layout manifest.

The reference images are deliberately not part of the repository. Run the three
``extract_zelda_*`` scripts first, then use this builder to reduce their output to
the game data needed by Hyrule's area generator and tests.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = ROOT.parent / "zelda-reference" / "extracted"
DEFAULT_OUTPUT = ROOT / "data" / "hyrule_first_quest.json"

PASSABLE_HORIZONTAL = {
    (0, 0), (4, 4), (7, 7), (0, 7), (7, 0), (4, 0), (41, 41)
}
PASSABLE_VERTICAL = {
    (0, 0), (4, 4), (7, 7), (15, 15), (4, 0), (7, 0),
    (43, 43), (44, 44), (15, 1), (15, 9), (43, 3),
}
RAFT_HORIZONTAL = {(41, 41)}
RAFT_VERTICAL = {(43, 43), (44, 44), (43, 3)}
LADDER_VERTICAL = {(15, 15), (15, 1), (15, 9)}

# NESMaps marks every bombable dungeon wall in the labeled map with the same
# 16x16 bomb sprite on both adjoining room images. The extracted cell images
# retain only annotations, making these boxes an exact, palette-independent
# signal instead of requiring inferred connectivity.
BOMB_MARKER_BOXES = {
    "north": (120, 16, 136, 32),
    "east": (224, 80, 240, 96),
    "south": (120, 144, 136, 160),
    "west": (16, 80, 32, 96),
}
BOMB_MARKER_MIN_PIXELS = 180

DUNGEON_TITLES = {
    1: "The Eagle",
    2: "The Moon",
    3: "The Manji",
    4: "The Snake",
    5: "The Lizard",
    6: "The Dragon",
    7: "The Demon",
    8: "The Lion",
    9: "Death Mountain",
}
LEVEL_BANDS = {
    1: [11, 20], 2: [21, 30], 3: [31, 40], 4: [41, 50],
    5: [51, 55], 6: [56, 60], 7: [61, 64], 8: [65, 67], 9: [68, 70],
}

DUNGEON_CELLS = {
    1: "B6 C6 C5 E5 F5 A4 B4 C4 D4 E4 B3 C3 D3 C2 B1 C1 D1",
    2: "B8 C8 C7 D7 C6 D6 C5 D5 C4 D4 C3 D3 A2 B2 C2 D2 B1 C1",
    3: "B6 C6 C5 E5 A4 B4 C4 D4 E4 A3 B3 C3 D3 E3 A2 C2 C1 D1",
    4: "A8 B8 C8 D8 A7 B7 C7 D7 A6 B6 A5 B5 C5 A4 A3 B3 B2 C2 A1 B1",
    5: "B8 C8 A7 B7 C7 D7 A6 B6 C6 D6 A5 D5 C4 D4 B3 C3 D3 A2 B2 C2 D2 C1 D1",
    6: "B8 C8 D8 E8 A7 B7 C7 D7 E7 F7 A6 B6 E6 F6 A5 B5 C5 E5 A4 A3 A2 C2 A1 B1 C1",
    7: "A8 B8 C8 D8 E8 F8 A7 B7 C7 D7 E7 A6 B6 C6 D6 A5 B5 C5 A4 B4 A3 B3 C3 D3 A2 B2 C2 D2 E2 F2 A1 B1 C1",
    8: "D8 C7 D7 E7 B6 C6 D6 A5 B5 C5 D5 E5 A4 B4 C4 D4 B3 C3 D3 E3 D2 B1 C1 D1 E1",
    9: "B8 C8 D8 E8 F8 G8 H8 A7 B7 C7 D7 E7 F7 G7 H7 A6 B6 C6 D6 E6 F6 G6 H6 A5 B5 C5 D5 E5 F5 G5 H5 A4 B4 C4 D4 E4 F4 G4 H4 A3 B3 C3 D3 E3 F3 G3 H3 B2 C2 D2 E2 F2 G2 B1 D1 E1 G1",
}
DUNGEON_CELLS = {
    level: coordinates.split() for level, coordinates in DUNGEON_CELLS.items()
}

ENTRANCES = {1: "C1", 2: "B1", 3: "D1", 4: "B1", 5: "C1", 6: "B1", 7: "B1", 8: "D1", 9: "G1"}
BOSSES = {1: "E5", 2: "C8", 3: "E4", 4: "D7", 5: "A6", 6: "E7", 7: "C6", 8: "B5", 9: "C4"}
GOALS = {1: "F5", 2: "B8", 3: "E5", 4: "D8", 5: "A7", 6: "E8", 7: "D6", 8: "B6", 9: "C5"}
MAP_ROOMS = {1: "C4", 2: "D3", 3: "D4", 4: "B6", 5: "C4", 6: "B7", 7: "A7", 8: "D6", 9: "H6"}
COMPASS_ROOMS = {1: "D3", 2: "D2", 3: "B3", 4: "C2", 5: "D5", 6: "A2", 7: "C3", 8: "E3", 9: "F5"}

MAJOR_ITEMS = {
    1: ("B6", "Bow Cellar", 30222),
    3: ("A2", "Raft Cellar", 30411),
    4: ("C5", "Stepladder Cellar", 30412),
    5: ("B8", "Recorder Cellar", 30413),
    6: ("B8", "Magical Rod Cellar", 30245),
    7: ("C7", "Red Candle Cellar", 30414),
    8: ("B1", "Magic Book Cellar", 30415),
}
DIRECT_DUNGEON_ITEMS = {
    (1, "D4"): 30232,
    (2, "D4"): 30410,
}
EXTRA_MAJOR_ITEMS = {
    8: [("E7", "Magical Key Cellar", 30416)],
    9: [("A7", "Silver Arrow Cellar", 30218), ("H8", "Red Ring Cellar", 30261)],
}
STAIR_PAIRS = {
    5: [("C8", "A2")],
    6: [("F7", "C5")],
    7: [("F8", "B6")],
    8: [("E5", "B4")],
    # Death Mountain's lettered passages A, C, D, E, G, and H. Passages B
    # and F are the Red Ring and Silver Arrow cellars, respectively.
    9: [("E7", "F3"), ("F8", "D2"), ("B1", "E1"),
        ("A6", "B2"), ("E8", "A5"), ("D8", "C3")],
}

# The map sprites are the primary encounter source. These overrides cover rooms
# where overlapping animation frames cannot be separated reliably by image
# matching. Level 9 is also cross-checked against the complete First Quest route.
ROOM_ENTITY_OVERRIDES = {
    (9, "G2"): {"old_man": 1},
    (9, "G3"): {"bubble": 2, "zol": 2, "like_like": 2},
    (9, "F3"): {"red_lanmola": 2},
    (9, "E7"): {"like_like": 5},
    (9, "F7"): {"blue_wizzrobe": 3},
    (9, "F6"): {"bubble": 2, "zol": 2, "like_like": 2},
    (9, "F5"): {"red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "G7"): {"patra": 1},
    (9, "G6"): {"gel": 8},
    (9, "H6"): {"patra": 1},
    (9, "H7"): {
        "bubble": 1, "like_like": 3, "red_wizzrobe": 2,
        "blue_wizzrobe": 2,
    },
    (9, "H8"): {"bubble": 3, "red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "G4"): {"blue_wizzrobe": 6},
    (9, "E4"): {"red_wizzrobe": 6},
    (9, "E6"): {"vire": 6},
    (9, "E5"): {"keese": 8},
    (9, "D5"): {"gel": 8},
    (9, "G5"): {"bubble": 3, "keese": 3, "zol": 2},
    (9, "H5"): {"vire": 6},
    (9, "H4"): {"bubble": 3, "red_wizzrobe": 2, "blue_wizzrobe": 2},
    (9, "H3"): {"red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "G8"): {"old_man": 1},
    (9, "F8"): {"red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "D2"): {"zol": 5},
    (9, "C2"): {"keese": 8},
    (9, "B2"): {"patra": 1},
    (9, "A6"): {"red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "A7"): {"bubble": 3, "red_wizzrobe": 2, "blue_wizzrobe": 3},
    (9, "D3"): {
        "bubble": 1, "like_like": 3, "red_wizzrobe": 2,
        "blue_wizzrobe": 2,
    },
    (9, "E1"): {"blue_lanmola": 2},
    (9, "B3"): {"like_like": 6},
    (9, "B4"): {"blade_trap": 4, "like_like": 4},
    (9, "B5"): {
        "bubble": 1, "like_like": 3, "red_wizzrobe": 2,
        "blue_wizzrobe": 2,
    },
    (9, "B6"): {"patra": 1},
    (9, "B7"): {"blue_lanmola": 2},
    (9, "B8"): {"bubble": 3, "keese": 3, "zol": 2},
    (9, "C8"): {"old_man": 1},
    (9, "C7"): {"red_lanmola": 2},
    (9, "C6"): {"bubble": 2, "zol": 2, "like_like": 2},
    (9, "A3"): {"zol": 5},
    (9, "A4"): {"red_wizzrobe": 2, "blue_wizzrobe": 2},
    (9, "A5"): {
        "blade_trap": 4, "red_wizzrobe": 2, "blue_wizzrobe": 2,
    },
    (9, "D8"): {"bubble": 2, "zol": 2, "like_like": 2},
    (9, "C3"): {"patra": 1},
}

OVERWORLD_LANDMARKS: dict[str, list[dict[str, Any]]] = {
    "H1": [{"type": "start", "name": "First Quest arrival"},
           {"type": "cave", "name": "Wooden Sword Cave", "item": 30219}],
    "H5": [{"type": "dungeon", "level": 1}],
    "M5": [{"type": "dungeon", "level": 2}],
    "E1": [{"type": "dungeon", "level": 3}],
    "F4": [{"type": "dungeon", "level": 4, "requires": 30411}],
    "L8": [{"type": "dungeon", "level": 5}],
    "C6": [{"type": "dungeon", "level": 6}],
    "C4": [{"type": "dungeon", "level": 7, "puzzle": "recorder"}],
    "N2": [{"type": "dungeon", "level": 8, "puzzle": "burn"}],
    "F8": [{"type": "dungeon", "level": 9, "puzzle": "bomb"}],
    "K8": [{"type": "cave", "name": "White Sword Cave", "item": 30251}],
    "B6": [{"type": "cave", "name": "Master Sword Grave", "item": 30200}],
    "O8": [{"type": "cave", "name": "Letter Cave", "item": 30500}],
    "E6": [{"type": "secret", "name": "Power Bracelet Armos", "item": 30276,
            "puzzle": "armos"}],
    "L1": [{"type": "heart", "puzzle": "bomb"}],
    "M6": [{"type": "heart", "puzzle": "bomb"}],
    "H4": [{"type": "heart", "puzzle": "burn"}],
    "P6": [{"type": "heart", "requires": 30411}],
    "P3": [{"type": "heart", "requires": 30412}],
    "D4": [{"type": "fairy_fountain"}],
    "J5": [{"type": "fairy_fountain"}],
    "E2": [{"type": "secret_return", "puzzle": "burn", "destination": 15068}],
    "B3": [{"type": "rupee", "amount": 10, "puzzle": "burn", "room_vnum": 30660}],
    "B1": [{"type": "rupee", "amount": 30, "puzzle": "bomb", "room_vnum": 30661}],
    "C2": [{"type": "rupee", "amount": 100, "puzzle": "burn", "room_vnum": 30662}],
    "D7": [{"type": "rupee", "amount": 30, "puzzle": "bomb", "room_vnum": 30663}],
    "G3": [{"type": "rupee", "amount": 10, "puzzle": "burn", "room_vnum": 30664}],
    "H2": [{"type": "rupee", "amount": 30, "puzzle": "bomb", "room_vnum": 30665}],
    "I6": [{"type": "rupee", "amount": 30, "puzzle": "burn", "room_vnum": 30666}],
    "I4": [{"type": "rupee", "amount": 30, "puzzle": "burn", "room_vnum": 30667}],
    "L3": [{"type": "rupee", "amount": 10, "puzzle": "burn", "room_vnum": 30668}],
    "L2": [{"type": "rupee", "amount": 100, "puzzle": "burn", "room_vnum": 30669}],
    "N6": [{"type": "rupee", "amount": 30, "puzzle": "bomb", "room_vnum": 30670}],
    "N5": [{"type": "rupee", "amount": 30, "puzzle": "armos", "room_vnum": 30671}],
    "O4": [{"type": "rupee", "amount": 10, "puzzle": "armos", "room_vnum": 30672}],
    "P8": [{"type": "rupee", "amount": 100, "room_vnum": 30673}],
}

OVERWORLD_SERVICES = [
    # Regular shops: NES coordinates are retained for source auditing; the
    # manifest coordinate uses the generator's south-to-north row numbering.
    ("E4", {"type": "shop", "shop_kind": "regular_bomb", "room_vnum": 30680,
            "zelda_coordinate": "E5"}),
    ("F6", {"type": "shop", "shop_kind": "regular_bomb", "room_vnum": 30681,
            "zelda_coordinate": "F3"}),
    ("G2", {"type": "shop", "shop_kind": "regular_candle", "room_vnum": 30682,
            "zelda_coordinate": "G7"}),
    ("K4", {"type": "shop", "shop_kind": "regular_bomb", "room_vnum": 30683,
            "zelda_coordinate": "K5"}),
    ("M8", {"type": "shop", "shop_kind": "regular_candle", "room_vnum": 30684,
            "zelda_coordinate": "M1"}),
    ("O3", {"type": "shop", "shop_kind": "regular_candle", "room_vnum": 30685,
            "zelda_coordinate": "O6"}),
    ("P2", {"type": "shop", "shop_kind": "regular_bomb", "room_vnum": 30686,
            "zelda_coordinate": "P7"}),
    # Secret deluxe shops.
    ("C7", {"type": "shop", "shop_kind": "deluxe_shield", "room_vnum": 30687,
            "zelda_coordinate": "C2", "puzzle": "bomb"}),
    ("E5", {"type": "shop", "shop_kind": "deluxe_ring", "room_vnum": 30688,
            "zelda_coordinate": "E4", "puzzle": "armos"}),
    ("G6", {"type": "shop", "shop_kind": "deluxe_shield", "room_vnum": 30689,
            "zelda_coordinate": "G3", "puzzle": "bomb"}),
    ("G4", {"type": "shop", "shop_kind": "deluxe_shield", "room_vnum": 30690,
            "zelda_coordinate": "G5", "puzzle": "burn"}),
    ("N4", {"type": "shop", "shop_kind": "deluxe_shield", "room_vnum": 30691,
            "zelda_coordinate": "N5", "puzzle": "burn"}),
    # Potion shops. E2 also contains the custom return tree, so its visible
    # shop uses the otherwise-free upward exit.
    ("D5", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30692,
            "zelda_coordinate": "D4", "puzzle": "bomb"}),
    ("E8", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30693,
            "zelda_coordinate": "E1"}),
    ("E2", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30694,
            "zelda_coordinate": "E7", "direction": "up"}),
    ("H6", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30695,
            "zelda_coordinate": "H3", "puzzle": "bomb"}),
    ("I1", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30696,
            "zelda_coordinate": "I8", "puzzle": "burn"}),
    ("L4", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30697,
            "zelda_coordinate": "L5", "puzzle": "burn"}),
    ("N8", {"type": "potion_shop", "shop_kind": "potion", "room_vnum": 30698,
            "zelda_coordinate": "N1", "puzzle": "bomb"}),
]

for service_coordinate, service in OVERWORLD_SERVICES:
    OVERWORLD_LANDMARKS.setdefault(service_coordinate, []).append(service)

OVERWORLD_ATTRACTIONS = [
    # One-time door-repair charges.
    ("B8", {"type": "door_repair", "room_vnum": 30700, "token_vnum": 30555,
            "zelda_coordinate": "B1", "puzzle": "bomb"}),
    ("D8", {"type": "door_repair", "room_vnum": 30701, "token_vnum": 30556,
            "zelda_coordinate": "D1", "puzzle": "bomb"}),
    ("D2", {"type": "door_repair", "room_vnum": 30702, "token_vnum": 30557,
            "zelda_coordinate": "D7", "puzzle": "burn"}),
    ("E7", {"type": "door_repair", "room_vnum": 30703, "token_vnum": 30558,
            "zelda_coordinate": "E2", "puzzle": "bomb"}),
    ("H8", {"type": "door_repair", "room_vnum": 30704, "token_vnum": 30559,
            "zelda_coordinate": "H1", "puzzle": "bomb"}),
    ("I2", {"type": "door_repair", "room_vnum": 30705, "token_vnum": 30560,
            "zelda_coordinate": "I7", "puzzle": "burn"}),
    ("K2", {"type": "door_repair", "room_vnum": 30706, "token_vnum": 30561,
            "zelda_coordinate": "K7", "puzzle": "burn"}),
    ("N1", {"type": "door_repair", "room_vnum": 30707, "token_vnum": 30562,
            "zelda_coordinate": "N8", "puzzle": "bomb"}),
    ("O7", {"type": "door_repair", "room_vnum": 30708, "token_vnum": 30563,
            "zelda_coordinate": "O2", "puzzle": "bomb"}),
    # Money-making games.
    ("A7", {"type": "gamble", "room_vnum": 30710,
            "zelda_coordinate": "A2", "puzzle": "bomb"}),
    ("G7", {"type": "gamble", "room_vnum": 30711,
            "zelda_coordinate": "G2", "puzzle": "bomb"}),
    ("G1", {"type": "gamble", "room_vnum": 30712,
            "zelda_coordinate": "G8", "puzzle": "bomb"}),
    ("M1", {"type": "gamble", "room_vnum": 30713,
            "zelda_coordinate": "M8", "puzzle": "bomb"}),
    ("P7", {"type": "gamble", "room_vnum": 30714,
            "zelda_coordinate": "P2"}),
    # Power Bracelet warp network. Route order is west, center, east.
    ("D6", {"type": "warp_hall", "room_vnum": 30720,
            "zelda_coordinate": "D3", "puzzle": "bracelet",
            "routes": [
                {"road": "western", "destination": "J4", "object_vnum": 30565},
                {"road": "central", "destination": "J1", "object_vnum": 30566},
                {"road": "eastern", "destination": "N7", "object_vnum": 30567},
            ]}),
    ("J4", {"type": "warp_hall", "room_vnum": 30721,
            "zelda_coordinate": "J5", "puzzle": "bracelet",
            "routes": [
                {"road": "western", "destination": "J1", "object_vnum": 30568},
                {"road": "central", "destination": "N7", "object_vnum": 30569},
                {"road": "eastern", "destination": "D6", "object_vnum": 30570},
            ]}),
    ("J1", {"type": "warp_hall", "room_vnum": 30722,
            "zelda_coordinate": "J8", "puzzle": "bracelet",
            "routes": [
                {"road": "western", "destination": "N7", "object_vnum": 30571},
                {"road": "central", "destination": "D6", "object_vnum": 30572},
                {"road": "eastern", "destination": "J4", "object_vnum": 30573},
            ]}),
    ("N7", {"type": "warp_hall", "room_vnum": 30723,
            "zelda_coordinate": "N2", "puzzle": "bracelet",
            "routes": [
                {"road": "western", "destination": "D6", "object_vnum": 30574},
                {"road": "central", "destination": "J4", "object_vnum": 30575},
                {"road": "eastern", "destination": "J1", "object_vnum": 30576},
            ]}),
]

for attraction_coordinate, attraction in OVERWORLD_ATTRACTIONS:
    OVERWORLD_LANDMARKS.setdefault(attraction_coordinate, []).append(attraction)

DOOR_CLASSES = {
    "north": {
        "open": {1, 7, 9, 12}, "locked": {2, 10},
        "shutter": {3, 8, 13, 14},
    },
    "east": {
        "open": {1, 7}, "locked": {3, 16, 17, 23},
        "shutter": {4, 8, 20},
    },
    "south": {
        "open": {1, 2, 3, 6, 11, 13, 14}, "locked": {8, 10},
        "shutter": {4, 9, 15, 18},
    },
    "west": {
        "open": {1, 9, 12}, "locked": {2, 17, 22},
        "shutter": {5, 18, 21},
    },
}

UNMATCHED_ENEMIES = {
    "gel": {
        "f2681ba53679", "f40e94c05e0f", "3ab214122a92", "8f2ee889a09c",
        "1dfd6d7719e7", "d1c8917c6b1c", "d3b613ccdf79",
    },
    "like_like": {"2b859e532d38", "71130ebd74da"},
    "vire": {"3b112d1c3b93", "14e2d99a2f03", "8c0ee52cff6e"},
    "blue_darknut": {"fe73ee8cb55d"},
    "zol": {"c4e97b0cefc4", "24d2191c7266", "9f9d1a5d6208", "d7ef144c141e", "e1e7181d9043", "13f1380c63dd"},
    "bubble": {"1cb1cd6f8632", "06eb7152af6b", "a93417b589ac", "7e775998641e", "b63a66f72376"},
    "pols_voice": {"5a404378a478", "849e680f6074"},
    "gibdo": {"f319430fb09f", "b039fce8144b", "9e1ea3027386"},
    "red_darknut": {"eac406811c00", "1bf427fa73fb", "5ee0560755e0"},
    "red_wizzrobe": {"1700bb0a001e", "cb52264c69e2", "7b70cef19bbc", "a5d7fa8a8ecb", "0843e84fbba4"},
    "blue_wizzrobe": {"7c0220aca352", "bc8eea4b56f7", "00e960d6dfa4", "22ca9a2c1fa2", "31093d7424c1"},
    "dodongo": {"2e8e4e144124", "3b5debcc5200"},
    "digdogger": {"2c2347cd9e4a"},
}

BOSS_ROSTERS = {
    1: {"aquamentus": 1},
    2: {"dodongo": 2},
    3: {"manhandla": 1},
    4: {"gleeok": 1},
    5: {"digdogger": 1},
    6: {"gohma": 1},
    7: {"aquamentus": 1},
    8: {"gleeok": 1},
    9: {"ganon": 1},
}


def coordinate_key(coordinate: str) -> tuple[int, int]:
    return int(coordinate[1:]), ord(coordinate[0]) - ord("A")


def neighbor(coordinate: str, direction: str) -> str:
    column = ord(coordinate[0]) - ord("A")
    row = int(coordinate[1:])
    dc, dr = {"north": (0, 1), "east": (1, 0), "south": (0, -1), "west": (-1, 0)}[direction]
    return f"{chr(ord('A') + column + dc)}{row + dr}"


def opposite(direction: str) -> str:
    return {"north": "south", "east": "west", "south": "north", "west": "east"}[direction]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def edge_lookup(
    records: list[dict[str, Any]],
    pair_set: set[tuple[int, int]],
    gate_pairs: dict[tuple[int, int], str],
    a_key: str,
    b_key: str,
) -> dict[tuple[str, str], str]:
    edges: dict[tuple[str, str], str] = {}
    for record in records:
        tiles = tuple(record["tiles"])
        if tiles not in pair_set:
            continue
        gate = gate_pairs.get(tiles, "open")
        for position in record["positions"]:
            edges[(position[a_key], position[b_key])] = gate
    return edges


def world_level(coordinate: str) -> int:
    """Assign a useful 1-70 leveling gradient without changing screen geometry."""
    col = ord(coordinate[0]) - ord("A")
    row = int(coordinate[1:]) - 1
    start_col, start_row = 7, 0
    distance = abs(col - start_col) + abs(row - start_row)
    danger = distance * 3 + max(0, row - 2) * 4 + max(0, 5 - col) * 2
    if coordinate in {"B6", "C6", "F8", "K8", "L8", "N2"}:
        danger += 14
    return max(1, min(70, 1 + danger))


def build_overworld(reference: Path, entities: dict[str, Any]) -> list[dict[str, Any]]:
    horizontal = edge_lookup(
        load_json(reference / "overworld-horizontal-edge-pairs.json"),
        PASSABLE_HORIZONTAL, {pair: "raft" for pair in RAFT_HORIZONTAL}, "west", "east",
    )
    vertical = edge_lookup(
        load_json(reference / "overworld-vertical-edge-pairs.json"),
        PASSABLE_VERTICAL,
        {
            **{pair: "raft" for pair in RAFT_VERTICAL},
            **{pair: "stepladder" for pair in LADDER_VERTICAL},
        },
        "north", "south",
    )
    all_coordinates = [f"{chr(ord('A') + column)}{row}" for row in range(1, 9) for column in range(16)]
    ordered_coordinates = ["H1", *[coordinate for coordinate in all_coordinates if coordinate != "H1"]]
    vnums = {coordinate: 30200 + index for index, coordinate in enumerate(ordered_coordinates)}
    exits: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for (west, east), gate in horizontal.items():
        exits[west]["east"] = {"to": east, "gate": gate}
        exits[east]["west"] = {"to": west, "gate": gate}
    for (north, south), gate in vertical.items():
        exits[north]["south"] = {"to": south, "gate": gate}
        exits[south]["north"] = {"to": north, "gate": gate}

    rooms = []
    for coordinate in all_coordinates:
        room_exits = {
            direction: {**data, "to_vnum": vnums[data["to"]]}
            for direction, data in sorted(exits[coordinate].items())
        }
        room_entities = entities.get(coordinate, {}).get("entities", {})
        rooms.append({
            "coordinate": coordinate,
            "vnum": vnums[coordinate],
            "recommended_level": world_level(coordinate),
            "exits": room_exits,
            "entities": room_entities,
            "landmarks": OVERWORLD_LANDMARKS.get(coordinate, []),
        })

    reachable = {"H1"}
    pending = deque(reachable)
    while pending:
        coordinate = pending.popleft()
        for data in exits[coordinate].values():
            if data["to"] not in reachable:
                reachable.add(data["to"])
                pending.append(data["to"])
    if len(reachable) != 128:
        raise ValueError(f"overworld graph only reaches {len(reachable)} of 128 screens")
    return rooms


def door_patterns(door_data: dict[str, Any]) -> dict[tuple[int, str, str], int]:
    patterns: dict[tuple[int, str, str], int] = {}
    expression = re.compile(r"level-(\d+):([A-H][1-8])")
    for direction, records in door_data.items():
        for record in records:
            for example in record["examples"]:
                match = expression.fullmatch(example)
                if match:
                    patterns[(int(match.group(1)), match.group(2), direction)] = record["id"]
    return patterns


def classify_door(patterns: dict[tuple[int, str, str], int], level: int, coordinate: str, direction: str) -> str:
    pattern = patterns.get((level, coordinate, direction))
    if pattern is None:
        return "wall"
    for door_class, identifiers in DOOR_CLASSES[direction].items():
        if pattern in identifiers:
            return door_class
    return "wall"


def unmatched_by_room(unmatched: list[dict[str, Any]]) -> dict[tuple[int, str], Counter[str]]:
    digest_to_name = {
        digest: name for name, digests in UNMATCHED_ENEMIES.items() for digest in digests
    }
    rooms: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    expression = re.compile(r"level-(\d+):([A-H][1-8])@")
    for component in unmatched:
        name = digest_to_name.get(component["digest"])
        if not name:
            continue
        for example in component["examples"]:
            match = expression.match(example)
            if match:
                rooms[(int(match.group(1)), match.group(2))][name] += 1
    return rooms


def _color_positions(image: Image.Image) -> dict[tuple[int, int, int], list[tuple[int, int]]]:
    positions: dict[tuple[int, int, int], list[tuple[int, int]]] = defaultdict(list)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            color = pixels[x, y]
            if color != (255, 255, 255):
                positions[color].append((x, y))
    return positions


def _masked_matches(target: Image.Image, template: Image.Image) -> list[tuple[int, int, int, int]]:
    target_positions = _color_positions(target)
    template_pixels = template.load()
    colored = [
        (x, y, template_pixels[x, y])
        for y in range(template.height)
        for x in range(template.width)
        if template_pixels[x, y] != (255, 255, 255)
    ]
    if not colored:
        return []
    anchor_x, anchor_y, anchor_color = min(
        colored, key=lambda point: len(target_positions.get(point[2], []))
    )
    target_pixels = target.load()
    matches = []
    for target_x, target_y in target_positions.get(anchor_color, []):
        left, top = target_x - anchor_x, target_y - anchor_y
        right, bottom = left + template.width, top + template.height
        if left < 28 or top < 24 or right > 229 or bottom > 139:
            continue
        if all(target_pixels[left + x, top + y] == color for x, y, color in colored):
            matches.append((left, top, right, bottom))
    return matches


def _overlaps(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> bool:
    return not (
        left[2] <= right[0] or right[2] <= left[0]
        or left[3] <= right[1] or right[3] <= left[1]
    )


def refine_unmatched_enemies(
    reference: Path,
    entity_data: dict[str, Any],
    unmatched: list[dict[str, Any]],
) -> dict[tuple[int, str], Counter[str]]:
    """Re-match classified components before nearby sprites merge together."""
    digest_to_name = {
        digest: name for name, digests in UNMATCHED_ENEMIES.items() for digest in digests
    }
    expression = re.compile(r"(level-\d+):([A-H][1-8])@(\d+),(\d+)")
    templates: dict[str, list[Image.Image]] = defaultdict(list)
    fingerprints: set[tuple[str, tuple[int, int], bytes]] = set()
    for component in unmatched:
        name = digest_to_name.get(component["digest"])
        if not name or not component["examples"]:
            continue
        width, height = component["size"]
        if width > 32 or height > 32:
            continue
        match = expression.fullmatch(component["examples"][0])
        if match is None:
            continue
        map_name, coordinate, left, top = match.groups()
        cell_path = reference / "cells" / f"{map_name}-{coordinate}.png"
        image = Image.open(cell_path).convert("RGB")
        template = image.crop((int(left), int(top), int(left) + width, int(top) + height))
        fingerprint = (name, template.size, template.tobytes())
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            templates[name].append(template)

    counts: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    for level in range(1, 10):
        map_name = f"level-{level}"
        for coordinate in DUNGEON_CELLS[level]:
            target = Image.open(reference / "cells" / f"{map_name}-{coordinate}.png").convert("RGB")
            known_bounds = [
                tuple(detection["bounds"])
                for detection in entity_data[map_name].get(coordinate, {}).get("detections", [])
            ]
            for name, enemy_templates in templates.items():
                matched_bounds: list[tuple[int, int, int, int]] = []
                for template in enemy_templates:
                    for bounds in _masked_matches(target, template):
                        if any(_overlaps(bounds, known) for known in known_bounds):
                            continue
                        if any(_overlaps(bounds, existing) for existing in matched_bounds):
                            continue
                        matched_bounds.append(bounds)
                if matched_bounds:
                    counts[(level, coordinate)][name] = len(matched_bounds)
    return counts


def add_edge(edges: dict[str, dict[str, dict[str, Any]]], source: str, target: str, direction: str, kind: str) -> None:
    reverse = opposite(direction)
    priority = {"open": 0, "shutter": 1, "bombable": 2, "locked": 3}
    current = edges[source].get(direction)
    if current is None or priority[kind] > priority[current["type"]]:
        edges[source][direction] = {"to": target, "type": kind}
        edges[target][reverse] = {"to": source, "type": kind}


def has_bomb_marker(reference: Path, level: int, coordinate: str, direction: str) -> bool:
    image = Image.open(
        reference / "cells" / f"level-{level}-{coordinate}.png"
    ).convert("RGB")
    marker = image.crop(BOMB_MARKER_BOXES[direction])
    changed_pixels = sum(
        marker.getpixel((x, y)) != (255, 255, 255)
        for y in range(marker.height)
        for x in range(marker.width)
    )
    return changed_pixels >= BOMB_MARKER_MIN_PIXELS


def dungeon_edges(
    level: int,
    patterns: dict[tuple[int, str, str], int],
    reference: Path,
) -> dict[str, dict[str, dict[str, Any]]]:
    cells = set(DUNGEON_CELLS[level])
    edges: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    direction_order = ("north", "east", "south", "west")
    for coordinate in sorted(cells, key=coordinate_key):
        for direction in direction_order:
            target = neighbor(coordinate, direction)
            if target not in cells or coordinate_key(target) < coordinate_key(coordinate):
                continue
            classes = {
                classify_door(patterns, level, coordinate, direction),
                classify_door(patterns, level, target, opposite(direction)),
            }
            bombable = (
                has_bomb_marker(reference, level, coordinate, direction)
                and has_bomb_marker(reference, level, target, opposite(direction))
            )
            if bombable:
                kind = "bombable"
            elif "locked" in classes:
                kind = "locked"
            elif "shutter" in classes:
                kind = "shutter"
            elif "open" in classes:
                kind = "open"
            else:
                continue
            add_edge(edges, coordinate, target, direction, kind)
    return edges


def normalize_entities(entities: dict[str, int]) -> dict[str, int]:
    ignored = {
        "bomb", "bow", "compass", "fire", "five_rupees", "heart_container",
        "key", "magical_boomerang", "magical_rod", "map", "raft", "recorder",
        "red_candle", "red_ring", "rupee", "silver_arrow", "triforce", "bait",
    }
    return {name: count for name, count in entities.items() if name not in ignored}


def build_dungeons(reference: Path, entity_data: dict[str, Any], unmatched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns = door_patterns(load_json(reference / "dungeon-doors.json"))
    inferred_entities = refine_unmatched_enemies(reference, entity_data, unmatched)
    next_vnum = 30400
    dungeons = []

    for level in range(1, 10):
        cells = sorted(DUNGEON_CELLS[level], key=coordinate_key)
        coordinate_vnums = {coordinate: next_vnum + index for index, coordinate in enumerate(cells)}
        next_vnum += len(cells)
        cellars = []
        cellar_specs = []
        if level in MAJOR_ITEMS:
            cellar_specs.append(MAJOR_ITEMS[level])
        cellar_specs.extend(EXTRA_MAJOR_ITEMS.get(level, []))
        for source_coordinate, name, object_vnum in cellar_specs:
            cellars.append({
                "name": name,
                "vnum": next_vnum,
                "source_coordinate": source_coordinate,
                "source_vnum": coordinate_vnums[source_coordinate],
                "item_vnum": object_vnum,
            })
            next_vnum += 1

        edges = dungeon_edges(level, patterns, reference)
        rooms = []
        map_entities = entity_data[f"level-{level}"]
        for coordinate in cells:
            room_entities = Counter(normalize_entities(map_entities.get(coordinate, {}).get("entities", {})))
            room_entities.update(inferred_entities[(level, coordinate)])
            if (level, coordinate) in ROOM_ENTITY_OVERRIDES:
                room_entities = Counter(ROOM_ENTITY_OVERRIDES[(level, coordinate)])
            if coordinate == BOSSES[level]:
                room_entities = Counter(BOSS_ROSTERS[level])
            items = []
            detected = map_entities.get(coordinate, {}).get("entities", {})
            if detected.get("key"):
                items.extend([30227] * detected["key"])
            if coordinate == MAP_ROOMS[level]:
                items.append(30479 + level)
            if coordinate == COMPASS_ROOMS[level]:
                items.append(30488 + level)
            if (level, coordinate) in DIRECT_DUNGEON_ITEMS:
                items.append(DIRECT_DUNGEON_ITEMS[(level, coordinate)])
            if coordinate == GOALS[level] and level < 9:
                items.append(30399 + level)
            if (
                detected.get("fire", 0) >= 2
                and not room_entities
                and coordinate not in {BOSSES[level], GOALS[level]}
            ):
                room_entities["old_man"] = 1
            if level == 9 and coordinate == GOALS[level]:
                room_entities["princess_zelda"] = 1
            rooms.append({
                "coordinate": coordinate,
                "vnum": coordinate_vnums[coordinate],
                "name": f"Level {level}: {DUNGEON_TITLES[level]} [{coordinate}]",
                "exits": {
                    direction: {**data, "to_vnum": coordinate_vnums[data["to"]]}
                    for direction, data in sorted(edges[coordinate].items())
                },
                "entities": dict(sorted(room_entities.items())),
                "items": items,
                "role": (
                    "entrance" if coordinate == ENTRANCES[level] else
                    "boss" if coordinate == BOSSES[level] else
                    "goal" if coordinate == GOALS[level] else
                    "map" if coordinate == MAP_ROOMS[level] else
                    "compass" if coordinate == COMPASS_ROOMS[level] else "room"
                ),
            })

        stair_links = []
        for left, right in STAIR_PAIRS.get(level, []):
            stair_links.append({
                "from": left, "from_vnum": coordinate_vnums[left],
                "to": right, "to_vnum": coordinate_vnums[right],
            })
        dungeon = {
            "level": level,
            "title": DUNGEON_TITLES[level],
            "recommended_levels": LEVEL_BANDS[level],
            "overworld_coordinate": next(
                coordinate for coordinate, landmarks in OVERWORLD_LANDMARKS.items()
                if any(item.get("type") == "dungeon" and item.get("level") == level for item in landmarks)
            ),
            "entrance_coordinate": ENTRANCES[level],
            "entrance_vnum": coordinate_vnums[ENTRANCES[level]],
            "boss_coordinate": BOSSES[level],
            "boss_vnum": coordinate_vnums[BOSSES[level]],
            "goal_coordinate": GOALS[level],
            "goal_vnum": coordinate_vnums[GOALS[level]],
            "map_coordinate": MAP_ROOMS[level],
            "map_vnum": 30479 + level,
            "compass_coordinate": COMPASS_ROOMS[level],
            "compass_vnum": 30488 + level,
            "first_room_vnum": min(coordinate_vnums.values()),
            "last_room_vnum": max([*coordinate_vnums.values(), *[cellar["vnum"] for cellar in cellars]]),
            "rooms": rooms,
            "cellars": cellars,
            "stair_links": stair_links,
        }
        dungeons.append(dungeon)

    return dungeons


def build_manifest(reference: Path) -> dict[str, Any]:
    entities = load_json(reference / "entities.json")
    overworld = build_overworld(reference, entities["maps"]["overworld"])
    dungeons = build_dungeons(reference, entities["maps"], entities["unmatched_components"])
    return {
        "schema_version": 1,
        "quest": "The Legend of Zelda - First Quest",
        "sources": [
            "https://www.nesmaps.com/maps/Zelda/Zelda.html",
            "https://www.nintendo.co.jp/clv/manuals/en/pdf/CLV-P-NAANE_en.pdf",
            "https://github.com/TheVGLC/TheVGLC",
            "https://github.com/aldonunez/zelda1-disassembly",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/level-9-death-mountain",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/shop-index",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/potion-shops",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/obtain-rupees",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/pay-rupees",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/gamble",
            "https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/warp-halls",
        ],
        "world_entry_vnum": 30200,
        "return_room_vnum": 15068,
        "overworld": {"columns": 16, "rows": 8, "start": "H1", "rooms": overworld},
        "dungeons": dungeons,
        "post_ganon": {
            "vnum": dungeons[-1]["goal_vnum"],
            "key_vnum": 30243,
            "triforce_vnum": 30286,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args.reference.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    room_count = 128 + sum(len(item["rooms"]) + len(item["cellars"]) for item in manifest["dungeons"])
    print(f"Wrote {args.output} with {room_count} canonical rooms.")


if __name__ == "__main__":
    main()
