"""Generate ``area/hyrule.are`` from the First Quest manifest.

What is generated, and from where:

- Rooms and resets come from ``data/hyrule_first_quest.json`` (the NES
  topology, the enemies each NES screen or room shows, the level bands)
  and their names and prose from ``data/hyrule_room_prose.json``.
- What the enemies and the bosses look like -- their room line and their
  description -- comes from ``data/hyrule_mob_prose.json``.
- Every enemy that fights is generated here, as one record per kind per
  level band (see ENEMY_TYPES), so a keese in Level 1 and a keese on Death
  Mountain are different mobiles statted for their own band.
- The nine bosses are retained catalog records whose stat line is rewritten
  from BOSS_STATS, and each carries a generated weapon from BOSS_WEAPONS.

The rest of the object and mobile catalog -- names, flags, descriptions,
shopkeepers, the old men, Princess Zelda -- is retained as builders left it.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "hyrule_first_quest.json"
DEFAULT_PROSE = ROOT / "data" / "hyrule_room_prose.json"
DEFAULT_MOB_PROSE = ROOT / "data" / "hyrule_mob_prose.json"
DEFAULT_AREA = ROOT / "area" / "hyrule.are"

DIRECTION_NUMBERS = {
    "north": 0, "east": 1, "south": 2, "west": 3, "up": 4, "down": 5,
}
OPPOSITE_DIRECTIONS = {
    "north": "south", "east": "west", "south": "north", "west": "east",
    "up": "down", "down": "up",
}

NEW_MOBILE_VNUMS = set(range(30338, 30346)) | set(range(30346, 30450))
NEW_OBJECT_VNUMS = (
    set(range(30500, 30515))
    | {30520}
    | set(range(30530, 30591))
    | set(range(30591, 30650))     # heart containers, drops, keys, chests
    | set(range(30649, 30700))     # the Magical Sword, boss drops, bombs, the bomb bag
    | set(range(30700, 30763))     # the guardians' further drops (BOSS_EXTRA_DROPS)
    | {30408}                      # the ninth piece, the final Triforce piece
)
# Catalog objects taken out altogether. The plain "red ring" (30261) filled
# the Red Ring Cellar until the Red Ring of Hyrule (30579) took its place;
# nothing placed it after that and no saved character held one, so the
# owner had it removed rather than leave a second red ring in VNUM.
RETIRED_OBJECT_VNUMS = {30261}
# 30578, Ganon's Blue Ring of Hyrule, sits inside NEW_OBJECT_VNUMS and is
# simply no longer written: the shop's ring (30551) took its name.

# Everyone who is not an enemy has a record of their own, written from the
# "npcs" table of data/hyrule_mob_prose.json: each dungeon and cave old man,
# old woman, merchant, potion seller, door-repair man, gambler, fountain
# fairy and moblin, and Zelda. Their vnums are in the table; src/merc.h
# names the range (HYRULE_NPC_FIRST-LAST) so is_hyrule_bystander() covers
# them all.
NPC_VNUM_FIRST = 30346
NPC_VNUM_LAST = 30449
ZELDA_VNUM = 30338

BOSS_MOBS = {
    1: 30222, 2: 30218, 3: 30305, 4: 30307, 5: 30309,
    6: 30223, 7: 30314, 8: 30316, 9: 30225,
}
BOSS_GEAR = {
    1: 30339, 2: 30349, 3: 30359, 4: 30369, 5: 30374,
    6: 30378, 7: 30382, 8: 30385, 9: 30388,
}
GANON_GOLDEN_KEY_VNUM = 30243
BOSS_NAMES = {
    30222: "Aquamentus", 30218: "Dodongo", 30305: "Manhandla", 30307: "Gleeok",
    30309: "Digdogger", 30223: "Gohma", 30314: "ancient Aquamentus",
    30316: "ashen Gleeok", 30225: "Ganon",
}

# The manifest's non-enemy entities. Old men and fairies are a person per
# room (npc_key below); Zelda keeps her one record.
NPC_KINDS = {"old_man", "princess_zelda", "fairy"}

# The catalog records that used to be spawned as ordinary enemies. Each is
# replaced by the per-band records generated from ENEMY_TYPES, so the old
# single-level record is dropped rather than left behind unspawned. 30335-
# 30337 (peahat, armos, the shared hazard) were generated here before.
# 30216 (the fairy) and 30228 (the old man) were one record shared by every
# fountain and every old man's room; each is a person of their own now.
RETIRED_MOBILE_VNUMS = {
    30200, 30201, 30202, 30203, 30205, 30206, 30207, 30208,
    30211, 30212, 30213, 30214, 30215, 30216, 30217, 30219, 30220, 30221,
    30228,
    30300, 30301, 30302, 30304, 30306, 30308, 30310, 30312,
    30315, 30317, 30318, 30320, 30321, 30322, 30323, 30327,
    30328, 30329, 30330, 30335, 30336, 30337,
}

# The NES stock, shop by shop kind. Every shop of a kind has its own
# merchant (npcs "merchant:<guide coordinate>", "potion:<...>"), who sells
# this and buys nothing.
SHOP_INVENTORY = {
    "regular_bomb": [30541, 30695, 30543],      # Shield 130, Bombs 20, Arrows 80
    "regular_candle": [30544, 30545, 30546],    # Shield 160, Key 100, Blue Candle 60
    "deluxe_shield": [30547, 30548, 30549],     # Shield 90, Bait 100, Heart 10
    "deluxe_ring": [30550, 30551, 30552],       # Key 80, Blue Ring 250, Bait 60
    "potion": [30553, 30554],                   # Blue Potion 40, Red Potion 68
}
SHOP_NPC_PREFIX = {"shop": "merchant", "potion_shop": "potion"}

PUZZLE_OBJECTS = {
    "bomb": {"north": 30502, "east": 30503, "south": 30504, "west": 30505, "down": 30509},
    "burn": 30506,
    "recorder": 30507,
    "feed": 30508,
    "push": 30513,
    "armos": 30514,
    "bracelet": 30564,
    "grave": 30697,         # HYRULE_GRAVESTONE_VNUM
}

# Take any one you want: a Heart Container or the red potion. The same
# Heart Container lies on the P6 dock. src/hyrule.c's claim table lets each
# character take one, once.
TAKE_ANY_OFFER = (30501, 30554)

# The dungeon old men who sell a bigger bomb bag (Levels 5 and 7).
BOMB_BAG_SELLERS = ("old_man:L5:D7", "old_man:L7:A4")


def shop_stock(manifest: dict[str, Any]) -> dict[int, list[int]]:
    """Keeper vnum -> what they sell, for the G resets and #SHOPS."""
    stock: dict[int, list[int]] = {}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] in {"shop", "potion_shop"}:
                keeper = npc_vnum(
                    f"{SHOP_NPC_PREFIX[landmark['type']]}:{landmark['zelda_coordinate']}")
                stock[keeper] = list(SHOP_INVENTORY[landmark["shop_kind"]])
    for key in BOMB_BAG_SELLERS:
        stock[npc_vnum(key)] = [30696]          # HYRULE_BOMB_BAG_VNUM
    return stock

# The gear chests. Stage 0 is the Wooden Sword cave; stage N sits in Level
# N's map room. The catalog gear runs one piece per level, 1 to 70, and each
# chest holds the pieces for the band of the dungeon it stands in, so what
# a chest gives can be worn by the character who reached it.
GEAR_STAGES = {
    0: (30440, range(30320, 30324)),   # levels 1-4
    1: (30441, range(30324, 30329)),   # 5-9
    2: (30443, range(30329, 30335)),   # 10-15
    3: (30445, range(30335, 30341)),   # 16-21
    4: (30447, range(30341, 30348)),   # 22-28
    5: (30449, range(30348, 30355)),   # 29-35
    6: (30451, range(30355, 30362)),   # 36-42
    7: (30453, range(30362, 30368)),   # 43-48
    8: (30455, range(30368, 30375)),   # 49-55
    9: (30520, range(30375, 30389)),   # 56-70
}


# --------------------------------------------------------------------------
# Enemies.
#
# Hyrule runs from level 1 on the start screen to 59 in Death Mountain, and
# the same NES enemy turns up all the way along it: a keese flies in Level 1
# and in Level 9. So each kind is generated once per level band. The band of
# a dungeon is its manifest "recommended_levels"; an overworld screen takes
# the band its own recommended level falls in.
#
# A generated enemy's vnum encodes its kind: TIER_VNUM_FIRST + code * 10 +
# (band - 1). The code is the offset of the catalog record the kind used to
# be (30215 -> 15 for the like like), so src/fight.c can map any band of a
# like like, bubble or wallmaster back to the effect it has always had --
# see hyrule_enemy_kind() there. Keep the two in step.
# --------------------------------------------------------------------------

TIER_VNUM_FIRST = 31000
TIER_VNUM_LAST = TIER_VNUM_FIRST + 145 * 10 + 9


@dataclass(frozen=True)
class EnemyType:
    code: int
    race: str
    keywords: str
    short: str
    rank: float          # where in its band it sits: 0 bottom, 1 top
    hp: float = 1.0      # hit points against an ordinary mobile of its level
    damage: float = 1.0  # damage against an ordinary mobile of its level
    attack: int = 0      # attack_table index (const.c)
    off: str = "0"
    size: str = "M"
    special: str = ""    # spec_fun, carried over from the record it replaced


ENEMY_TYPES: dict[str, EnemyType] = {
    # The overworld.
    "red_octorok": EnemyType(
        0, "fish", "octorok red", "a red octorok",
        0.0, 0.8, 0.8, 6, size="S"),
    "blue_octorok": EnemyType(
        1, "fish", "octorok blue", "a blue octorok",
        0.35, 1.0, 1.0, 6, size="S"),
    "red_moblin": EnemyType(
        2, "pig", "moblin red", "a red moblin",
        0.3, 1.0, 1.0, 2),
    "blue_moblin": EnemyType(
        3, "pig", "moblin blue", "a blue moblin",
        0.6, 1.15, 1.1, 2),
    "red_tektite": EnemyType(
        122, "insect", "tektite red spider", "a red tektite",
        0.1, 0.7, 0.8, 10, off="F", size="S"),
    "blue_tektite": EnemyType(
        5, "insect", "tektite blue spider", "a blue tektite",
        0.45, 0.9, 0.9, 10, off="F", size="S"),
    "red_leever": EnemyType(
        6, "insect", "leever red sand", "a red leever",
        0.2, 0.9, 0.9, 22, size="S"),
    "blue_leever": EnemyType(
        7, "insect", "leever blue sand", "a blue leever",
        0.55, 1.1, 1.0, 22, size="S"),
    "red_lynel": EnemyType(
        127, "horse", "lynel red centaur lion", "a red lynel",
        0.8, 1.3, 1.2, 3, off="K", size="L"),
    "blue_lynel": EnemyType(
        8, "horse", "lynel blue centaur lion", "a blue lynel",
        1.0, 1.5, 1.3, 3, off="K", size="L"),
    "peahat": EnemyType(
        135, "plant", "peahat spinning flower", "a peahat",
        0.4, 0.9, 0.9, 1, off="F"),
    "zora": EnemyType(
        121, "fish", "zola zora river", "a Zola",
        0.45, 0.9, 1.1, 6),
    "ghini": EnemyType(
        130, "undead", "ghini ghost", "a ghini",
        0.7, 1.2, 1.0, 5),
    "armos": EnemyType(
        136, "modron", "armos knight statue", "an Armos knight",
        0.85, 1.4, 1.2, 8, size="L"),
    "falling_rock": EnemyType(
        26, "modron", "boulder rock falling", "a tumbling boulder",
        0.5, 0.8, 1.2, 8, size="L"),
    # The dungeons.
    "keese": EnemyType(
        11, "bat", "keese bat", "a keese",
        0.0, 0.5, 0.7, 10, off="F", size="T"),
    "gel": EnemyType(
        100, "unique", "gel slime", "a gel",
        0.0, 0.45, 0.6, 12, size="T"),
    "zol": EnemyType(
        13, "unique", "zol slime", "a zol",
        0.3, 1.0, 0.9, 14),
    "bubble": EnemyType(
        104, "undead", "bubble skull flame", "a bubble",
        0.3, 0.6, 0.7, 29, off="F", size="S"),
    "rope": EnemyType(
        102, "snake", "rope snake", "a rope",
        0.3, 0.8, 0.9, 10, size="S"),
    "stalfos": EnemyType(
        12, "undead", "stalfos skeleton", "a stalfos",
        0.4, 1.0, 1.0, 3),
    "red_goriya": EnemyType(
        14, "goblin", "goriya red", "a red goriya",
        0.4, 1.0, 1.0, 7),
    "blue_goriya": EnemyType(
        112, "goblin", "goriya blue", "a blue goriya",
        0.7, 1.15, 1.1, 7),
    "wallmaster": EnemyType(
        101, "undead", "wallmaster hand", "a wallmaster",
        0.55, 1.0, 0.9, 8),
    "vire": EnemyType(
        106, "bat", "vire bat demon", "a vire",
        0.6, 1.0, 1.0, 10),
    "like_like": EnemyType(
        15, "unique", "like likelike tube", "a like like",
        0.6, 1.2, 0.8, 14),
    "pols_voice": EnemyType(
        108, "rabbit", "pols voice", "a pols voice",
        0.6, 1.0, 1.0, 15),
    "gibdo": EnemyType(
        19, "undead", "gibdo mummy", "a gibdo",
        0.7, 1.25, 1.0, 8, special="spec_cast_undead"),
    "red_darknut": EnemyType(
        20, "human", "darknut red knight", "a red darknut",
        0.8, 1.3, 1.1, 3, off="K"),
    "blue_darknut": EnemyType(
        115, "human", "darknut blue knight", "a blue darknut",
        1.0, 1.5, 1.2, 3, off="K"),
    "red_wizzrobe": EnemyType(
        110, "human", "wizzrobe red wizard", "a red wizzrobe",
        0.7, 0.9, 1.2, 19, special="spec_cast_mage"),
    "blue_wizzrobe": EnemyType(
        21, "human", "wizzrobe blue wizard", "a blue wizzrobe",
        0.9, 1.0, 1.3, 19, special="spec_cast_mage"),
    "red_lanmola": EnemyType(
        117, "centipede", "lanmola red centipede", "a red lanmola",
        0.8, 1.3, 1.1, 10, off="H", size="L"),
    "blue_lanmola": EnemyType(
        17, "centipede", "lanmola blue centipede", "a blue lanmola",
        1.0, 1.5, 1.2, 10, off="H", size="L"),
    "patra": EnemyType(
        118, "unique", "patra eye", "a patra",
        1.0, 2.0, 1.3, 19, off="F", size="L", special="spec_hyrule_patra"),
    "dodongo": EnemyType(
        18, "lizard", "dodongo dinosaur", "a dodongo",
        1.0, 1.75, 1.1, 10, size="L"),
    "digdogger": EnemyType(
        109, "unique", "digdogger urchin", "a digdogger",
        1.0, 1.75, 1.1, 8, size="L"),
    "blade_trap": EnemyType(
        137, "modron", "blade trap spiked", "a blade trap",
        0.5, 0.8, 1.2, 1),
}

_codes = [enemy.code for enemy in ENEMY_TYPES.values()]
if len(set(_codes)) != len(_codes) or not all(0 <= code <= 145 for code in _codes):
    raise ValueError("ENEMY_TYPES codes must be unique and within 0-145")


def band_index(level: int, bands: dict[int, tuple[int, int]]) -> int:
    """The dungeon band an overworld level falls in."""
    for band, (_, high) in sorted(bands.items()):
        if level <= high:
            return band
    return max(bands)


def tier_vnum(kind: str, band: int) -> int:
    return TIER_VNUM_FIRST + ENEMY_TYPES[kind].code * 10 + band - 1


def tier_level(kind: str, band: int, bands: dict[int, tuple[int, int]]) -> int:
    low, high = bands[band]
    return round(low + ENEMY_TYPES[kind].rank * (high - low))


# Ordinary mobiles elsewhere in the world, read off the area files with the
# dashboard parser: the median hit points, and the median damage a ROUND
# (every attack the mobile makes), of a spawned mobile within two levels
# either side. A Hyrule enemy scales from these by its kind, so a dungeon's
# enemies are on par with what a character of its band fights elsewhere
# (owner, 2026-10-04). The damage curve used to be per blow and read about
# half the world's, and fast races hit twice on top of it.
HIT_POINT_CURVE = (
    (1, 25), (5, 67), (10, 135), (15, 225), (20, 350), (25, 560),
    (30, 890), (35, 1350), (40, 1700), (45, 2400), (50, 3300),
    (55, 4600), (60, 6200), (65, 8000),
)
DAMAGE_CURVE = (
    (1, 4.5), (5, 8), (10, 14), (15, 22), (20, 29), (25, 42), (30, 59),
    (35, 73), (40, 86), (45, 117), (50, 129), (55, 147), (60, 150), (65, 160),
)

# Races whose race table entry carries OFF_FAST, and so strike twice a round
# (const.c's race_table); and the fast offence letter itself.
FAST_RACES = {"bat", "cat", "dog", "fish", "fox", "insect", "rabbit", "song bird", "wolf"}
OFF_FAST_LETTER = "H"


# What each band's mix of kinds comes to against the world, corrected: a
# band of keese and gels (Level 1) runs light, one of darknuts and lynels
# heavy. Measured with the dashboard parser against the world's spawned
# mobiles at each band's middle level (hit points, damage a round), so that
# a dungeon's enemies average out on par with the world's (2026-10-04).
BAND_HP_CALIBRATION = {1: 1.5, 2: 1.4, 3: 1.18, 4: 1.16, 5: 0.82, 6: 1.1,
                       7: 0.74, 8: 0.9, 9: 0.75}
BAND_DAMAGE_CALIBRATION = {1: 1.2, 4: 1.08, 8: 1.08, 9: 0.94}


def attacks_per_round(enemy: "EnemyType") -> int:
    return 2 if enemy.race in FAST_RACES or OFF_FAST_LETTER in enemy.off else 1


def curve(points: tuple[tuple[int, int], ...], level: int) -> float:
    if level <= points[0][0]:
        return float(points[0][1])
    for (low_level, low_value), (high_level, high_value) in zip(points, points[1:]):
        if level <= high_level:
            share = (level - low_level) / (high_level - low_level)
            return low_value + share * (high_value - low_value)
    return float(points[-1][1])


def stat_fields(level: int, hit_points: float, damage: float) -> tuple[str, str, int]:
    """Hit dice, damage dice and hitroll for a mobile of this level.

    load_mobiles raises the damage bonus to 3 * level / 4 and the hitroll to
    level / 2 whatever the file says, so the dice are built on top of those
    floors rather than fighting them.
    """
    hit_count = max(1, level // 4)
    hit_bonus = max(1, round(hit_points - hit_count * 5.5))
    floor = 3 * level // 4
    bonus = max(floor, round(damage * 0.6))
    dice_average = max(1.0, damage - bonus)
    dice_count = max(1, level // 15 + 1)
    dice_size = max(2, round(2 * dice_average / dice_count - 1))
    return (f"{hit_count}d10+{hit_bonus}",
            f"{dice_count}d{dice_size}+{bonus}",
            level // 2)


def enemy_record(kind: str, band: int, bands: dict[int, tuple[int, int]],
                 text: dict[str, str]) -> str:
    """One generated enemy. `text` is its entry in hyrule_mob_prose.json."""
    enemy = ENEMY_TYPES[kind]
    level = tier_level(kind, band, bands)
    hit_dice, damage_dice, hitroll = stat_fields(
        level,
        curve(HIT_POINT_CURVE, level) * enemy.hp * BAND_HP_CALIBRATION.get(band, 1.0),
        curve(DAMAGE_CURVE, level) * enemy.damage * BAND_DAMAGE_CALIBRATION.get(band, 1.0)
        / attacks_per_round(enemy),
    )
    keywords = merge_keywords(enemy.keywords, enemy.short)
    # ACT_IS_NPC, ACT_SENTINEL, ACT_AGGRESSIVE: NES enemies hold their
    # screen or room. A wandering one walks out of its band, and in a
    # dungeon it piles into the next room's population.
    return f"""#{tier_vnum(kind, band)}
{keywords}~
{enemy.short}~
{text["long"]}
~
{text["description"]}
~
{enemy.race}~
ABF 0 0 S
{level} {hitroll} {hit_dice} 1d1+0 {damage_dice} {enemy.attack}
0 0 0 0
{enemy.off} 0 0 0
8 8 0 0
AHMV ABCDEFGHIJK {enemy.size} 0"""


# --------------------------------------------------------------------------
# Population.
#
# The manifest records what each NES screen and room shows, and some NES
# rooms are crowded -- eight keese, six like likes, a wall of wizzrobes. In
# the MUD every one of those is a full fight, so a room keeps every kind it
# had but far fewer of each, and no room holds more than ROOM_ENEMY_CAP
# unless it has more kinds than that.
# --------------------------------------------------------------------------

ROOM_ENEMY_CAP = 3
SINGLE_ENEMIES = {"blade_trap", "patra", "dodongo", "digdogger"}


def thinned_count(kind: str, nes_count: int) -> int:
    if nes_count <= 0:
        return 0
    if kind in SINGLE_ENEMIES or nes_count <= 3:
        return 1
    return 2 if nes_count <= 6 else 3


def thin_population(entities: dict[str, int]) -> dict[str, int]:
    counts = {
        kind: thinned_count(kind, count)
        for kind, count in entities.items() if count > 0
    }
    while sum(counts.values()) > ROOM_ENEMY_CAP:
        crowded = sorted(
            (kind for kind, count in counts.items() if count > 1),
            key=lambda kind: (-counts[kind], kind),
        )
        if not crowded:
            break
        counts[crowded[0]] -= 1
    return counts


def guide_coordinate(coordinate: str) -> str:
    """A manifest coordinate the way a printed guide writes it: rows count
    from the north there, so H1 (the start) is H8."""
    return f"{coordinate[0]}{9 - int(coordinate[1:])}"


_NPC_TABLE: dict[str, dict[str, Any]] | None = None


def npc_table() -> dict[str, dict[str, Any]]:
    """The people of Hyrule, from data/hyrule_mob_prose.json's npcs."""
    global _NPC_TABLE
    if _NPC_TABLE is None:
        _NPC_TABLE = load_json(DEFAULT_MOB_PROSE)["npcs"]
    return _NPC_TABLE


def npc_vnum(key: str) -> int:
    try:
        return int(npc_table()[key]["vnum"])
    except KeyError:
        raise KeyError(f"data/hyrule_mob_prose.json has no npc {key!r}") from None


def world_spawns(room: dict[str, Any], bands: dict[int, tuple[int, int]]) -> dict[int, int]:
    """Mobile vnum -> count for one overworld screen.

    The overworld already asks for at most two of anything, so its counts
    are the manifest's; only the band changes with the screen's level.
    """
    band = band_index(room["recommended_level"], bands)
    spawns: Counter[int] = Counter()
    for kind, count in room["entities"].items():
        if kind == "fairy":
            spawns[npc_vnum(f"fairy:{guide_coordinate(room['coordinate'])}")] += 1
        elif kind == "princess_zelda":
            spawns[ZELDA_VNUM] += 1
        elif kind in ENEMY_TYPES:
            spawns[tier_vnum(kind, band)] += count
    return dict(spawns)


def dungeon_spawns(level: int, room: dict[str, Any]) -> dict[int, int]:
    """Mobile vnum -> count for one dungeon room."""
    if room["role"] == "boss":
        return {BOSS_MOBS[level]: 1}
    spawns: Counter[int] = Counter()
    enemies = {kind: count for kind, count in room["entities"].items() if kind in ENEMY_TYPES}
    for kind, count in thin_population(enemies).items():
        spawns[tier_vnum(kind, level)] += count
    for kind, count in room["entities"].items():
        if kind == "old_man":
            spawns[npc_vnum(f"old_man:L{level}:{room['coordinate']}")] += 1
        elif kind == "princess_zelda":
            spawns[ZELDA_VNUM] += 1
        elif kind not in ENEMY_TYPES:
            raise ValueError(f"Level {level} {room['coordinate']}: no mobile for {kind!r}")
    return dict(spawns)


def manifest_bands(manifest: dict[str, Any]) -> dict[int, tuple[int, int]]:
    return {
        dungeon["level"]: tuple(dungeon["recommended_levels"])
        for dungeon in manifest["dungeons"]
    }


def enemy_text(mob_prose: dict[str, Any], kind: str, band: int) -> dict[str, str]:
    """One kind's text in one band: every band of a kind is written on its
    own, so a Death Mountain lynel is not an overworld one."""
    try:
        text = mob_prose["enemies"][kind][str(band)]
    except KeyError:
        raise KeyError(
            f"data/hyrule_mob_prose.json has no enemy entry for {kind} in band {band}"
        ) from None
    description = text["description"]
    if "\n" not in description:
        description = wrap_description(description)
    return {"long": text["long"], "description": description}


def enemy_records(manifest: dict[str, Any], mob_prose: dict[str, Any]) -> str:
    bands = manifest_bands(manifest)
    return "\n".join(
        enemy_record(kind, band, bands, enemy_text(mob_prose, kind, band))
        for kind, band in enemy_tiers(manifest)
    )


def enemy_specials(manifest: dict[str, Any]) -> list[str]:
    return [
        f"M {tier_vnum(kind, band)} {ENEMY_TYPES[kind].special} Load to: "
        f"{ENEMY_TYPES[kind].short} (Level {band} band)"
        for kind, band in enemy_tiers(manifest)
        if ENEMY_TYPES[kind].special
    ]


def enemy_tiers(manifest: dict[str, Any]) -> list[tuple[str, int]]:
    """Every (kind, band) the manifest spawns, in vnum order."""
    bands = manifest_bands(manifest)
    wanted: set[tuple[str, int]] = set()
    for room in manifest["overworld"]["rooms"]:
        band = band_index(room["recommended_level"], bands)
        wanted.update((kind, band) for kind in room["entities"] if kind in ENEMY_TYPES)
    for dungeon in manifest["dungeons"]:
        for room in dungeon["rooms"]:
            if room["role"] == "boss":
                continue
            wanted.update(
                (kind, dungeon["level"]) for kind in room["entities"] if kind in ENEMY_TYPES
            )
    return sorted(wanted, key=lambda item: tier_vnum(*item))


# --------------------------------------------------------------------------
# Bosses.
#
# Levels sit a little above the top of their dungeon's band; hit points are
# several times an ordinary mobile of that level, weighted by how hard the
# boss is in the NES game -- Aquamentus and Dodongo are the gentle ones,
# Gohma and the four-headed Gleeok are not, and Ganon is Ganon. The stat
# line is rewritten, and the room line and description come from
# data/hyrule_mob_prose.json; names, flags, resistances and Ganon's silver
# vulnerability stay as the catalog has them.
#
# Ganon is sized to need a group, but not to flatten one. Solo, a level
# 59 lands the ten Silver Arrow blows that bring him down at a little
# under one and a half a round through his parry and dodge (a level 64
# parries and dodges a level 59 35% of the time each), so the fight lasts
# about seven rounds. What hurts is spec_ganon in src/special.c: every
# four seconds two fireballs of 300-420 at random members of the fight,
# which no parry stops -- 150-210 each through sanctuary, less with the
# Red Ring's fifth and the Blue Ring's tenth.
#
# They were 1,400-1,900, sized against a 4,000 hit point hero, and
# nobody met them until October 2026: Ganon's hit points overflowed a
# short and he fell to the first punch. Once he could fight, one pulse
# through sanctuary was more than a typical level 59 has (about 1,640),
# and even a level 70 was shown UNSPEAKABLE on every blow. Retuned by
# hand, not by the simulation the other guardians came from: a soloist
# with sanctuary now takes roughly 550 per four seconds from fire and
# melee together, dead in about four rounds of the seven the arrow
# needs; three split it to under 200 each and see the fight out.
# GANON_ARMOR is the file value, times ten in game: -400 shaves about 80
# off each ordinary blow, while the Silver Arrow's tenth of his health is
# taken after armour and is untouched.
# --------------------------------------------------------------------------

#
# The guardians of Levels 1-8 were sized the same way, by simulation (the
# player model and the results are in wiki/hyrule-area.md): a lone
# character at the top of the band usually loses, one six levels above
# usually wins, and a group of three at the band usually wins. Each now
# has an NES attack in spec_hyrule_guardian (src/special.c), a volley of
# spell blows at random members of the fight -- BOSS_VOLLEYS, which that
# table must match.
# --------------------------------------------------------------------------

BOSS_STATS = {
    # dungeon: (level, hit points, average damage per blow)
    1: (10, 820, 10),     # Aquamentus
    2: (16, 2200, 19),    # Dodongo
    3: (23, 3400, 30),    # Manhandla
    4: (30, 6000, 64),    # Gleeok, two heads
    5: (36, 16800, 40),   # Digdogger
    6: (43, 20000, 27),   # Gohma: her sanctuary and haste do the rest
    7: (49, 30000, 66),   # Aquamentus again, older and harder
    8: (55, 33000, 80),   # Gleeok, four heads
    9: (64, 36000, 200),  # Ganon -- see above, and spec_ganon
}
# dungeon: (projectiles a pulse, least, most) -- spec_hyrule_guardian and
# spec_ganon; src/special.c's tables must say the same.
BOSS_VOLLEYS = {
    1: (3, 4, 6),         # Aquamentus's fan of three fireballs
    2: (1, 22, 31),       # Dodongo's charge
    3: (4, 9, 13),        # Manhandla's four heads
    4: (2, 39, 55),       # Gleeok's two heads
    5: (1, 48, 67),       # Digdogger's roll; two at half each once split
    6: (1, 32, 45),       # Gohma's eye
    7: (3, 26, 36),       # the ancient Aquamentus's fan
    8: (4, 24, 34),       # the ashen Gleeok's four heads
    9: (2, 300, 420),     # Ganon's fireballs
}
GANON_VNUM = 30225
GANON_ARMOR = -40
# Spec_funs the generator owns rather than retains: Ganon's fireballs and
# his healing out of a fight replace the necromancer's spell list he had,
# and the other guardians' NES attacks replace their dragon breath, which
# scaled with the breather's own hit points.
BOSS_SPECIALS = {
    **{vnum: "spec_hyrule_guardian" for level, vnum in BOSS_MOBS.items() if level <= 8},
    GANON_VNUM: "spec_ganon",
}


def set_item_line(body: str, vnum: int, item_line: str) -> str:
    """Rewrite a retained object's item line: type, extra and wear flags.
    It is the fifth line of the record, after the four strings."""
    record = re.compile(rf"(?ms)^#{vnum}\r?\n(?:[^\n]*\n){{4}}([^\n]*)\n").search(body)
    if not record:
        raise ValueError(f"missing object record {vnum}")
    return body[:record.start(1)] + item_line + body[record.end(1):]


def rename_object(body: str, vnum: int, keywords: str, short: str) -> str:
    """Rewrite a retained object's keywords and short description, the
    first two strings of its record."""
    record = re.compile(rf"(?m)^#{vnum}\r?\n([^\r\n]*)\r?\n([^\r\n]*)\r?\n").search(body)
    if not record:
        raise ValueError(f"missing object record {vnum}")
    return (body[:record.start(1)] + f"{keywords}~" + body[record.end(1):record.start(2)]
            + f"{short}~" + body[record.end(2):])


def redescribe_mobile(body: str, vnum: int, long: str, description: str,
                      short: str | None = None) -> str:
    """Replace a retained mobile's room line and description.

    A record opens "#vnum", keywords~, short~, long~, description~; the
    keywords stay as the catalog has them, and the short name too unless
    one is given.
    """
    pattern = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)")
    record = pattern.search(body)
    if not record:
        raise ValueError(f"missing mobile record {vnum}")
    keywords, old_short, _, _, rest = record.group(0).split("~", 4)
    short = old_short if short is None else f"\n{short}"
    text = f"{keywords}~{short}~\n{long}\n~\n{description}\n~{rest}"
    return body[:record.start()] + text + body[record.end():]


def rearm_mobile(body: str, vnum: int, armour: int) -> str:
    """Set a retained mobile's four armour classes (the line after its
    stat line), in the file's units: the game multiplies them by ten."""
    record = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)").search(body)
    if not record:
        raise ValueError(f"missing mobile record {vnum}")
    armour_line = re.compile(
        r"(?m)^(-?\d+ -?\d+ \d+d\d+\+-?\d+ \d+d\d+\+-?\d+ \d+d\d+\+-?\d+ -?\d+\n)"
        r"-?\d+ -?\d+ -?\d+ -?\d+$"
    )
    match = armour_line.search(body, record.start(), record.end())
    if not match:
        raise ValueError(f"missing armour line for mobile {vnum}")
    line = f"{match.group(1)}{armour} {armour} {armour} {armour}"
    return body[:match.start()] + line + body[match.end():]


def restat_mobile(body: str, vnum: int, level: int, hit_points: int, damage: int) -> str:
    """Rewrite one retained mobile's level, hitroll, hit and damage dice.

    The stat line is the first line of the record shaped like one: level,
    hitroll, then hit, mana and damage dice and the attack type. Mana dice
    and the attack type are kept.
    """
    record = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)").search(body)
    if not record:
        raise ValueError(f"missing mobile record {vnum}")
    stat_line = re.compile(
        r"(?m)^-?\d+ -?\d+ \d+d\d+\+-?\d+ (\d+d\d+\+-?\d+) \d+d\d+\+-?\d+ (-?\d+)(?=\r?$)"
    )
    match = stat_line.search(body, record.start(), record.end())
    if not match:
        raise ValueError(f"missing stat line for mobile {vnum}")
    hit_dice, damage_dice, hitroll = stat_fields(level, hit_points, damage)
    line = f"{level} {hitroll} {hit_dice} {match.group(1)} {damage_dice} {match.group(2)}"
    return body[:match.start()] + line + body[match.end():]


# --------------------------------------------------------------------------
# Boss weapons.
#
# Each boss carries a weapon that should be the best a character of that
# dungeon's band can find. "Best" was measured with the dashboard parser
# against every mobile-carried weapon in the world at or below the weapon's
# level, scored as average damage (value[1] * (value[2] + 1) / 2) plus
# damroll, and against Hyrule's own sword-cave weapons where those are
# better. Each sits 10-20% above that mark; see BOSS_WEAPON_BASELINES.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BossWeapon:
    vnum: int
    keywords: str
    short: str
    long: str
    material: str
    weapon_class: int
    dice: tuple[int, int]
    attack: int
    level: int
    hitroll: int
    damroll: int
    weight: int
    lore: str


BOSS_WEAPONS = {
    1: BossWeapon(
        30582, "aquamentus horn spear", "an Aquamentus horn-spear",
        "A spear tipped with a dragon's horn lies here.", "bone", 3, (3, 6), 2,
        8, 8, 1, 6,
        "The shaft is cut from a young tree in the Eagle's courtyard, and the\n"
        "head is the horn Aquamentus wore on its snout. It is light, quick and\n"
        "far sharper than anything a beginner has a right to carry."),
    2: BossWeapon(
        30583, "dodongo tail club", "a Dodongo tail-club",
        "A heavy club of grey, pebbled hide lies here.", "leather", 4, (4, 8), 7,
        14, 7, 2, 12,
        "A length of Dodongo tail, dried hard as wood and bound at the grip.\n"
        "Nothing that fell on the Moon's floor ever cut that hide; this is\n"
        "what it feels like to be hit by it."),
    3: BossWeapon(
        30584, "manhandla bloom whip", "the Manhandla bloom-whip",
        "A whip of thorned green vine lies coiled here.", "wood", 7, (6, 9), 4,
        20, 2, 2, 5,
        "Four thorned heads once grew from Manhandla's heart, and this whip is\n"
        "braided from the vine that joined them. It lashes faster than it\n"
        "should, as though it were still trying to grow."),
    4: BossWeapon(
        30585, "gleeok twin fang glaive", "the Gleeok twin-fang glaive",
        "A long glaive set with two dragon fangs lies here.", "steel", 8, (7, 8), 21,
        27, 3, 2, 14,
        "Two fangs from the Snake's guardian are lashed side by side on an\n"
        "ash haft. The blade is still faintly warm, and smells of smoke."),
    5: BossWeapon(
        30586, "digdogger urchin flail", "the Digdogger urchin flail",
        "A spiked iron ball on a chain lies here.", "iron", 6, (7, 9), 8,
        33, 6, 2, 15,
        "The head of this flail is a single spine-cluster from the great\n"
        "urchin of the Lizard's den. It hums faintly when swung, a sound\n"
        "Digdogger would have hated."),
    6: BossWeapon(
        30587, "gohma eye lance", "the Gohma eye-lance",
        "A slender lance with a red crystal point lies here.", "steel", 3, (7, 10), 11,
        40, 6, 1, 10,
        "The point is the crystal lens of Gohma's single eye, ground to a\n"
        "needle. It finds the weak spot in armour as surely as an arrow\n"
        "found the eye."),
    7: BossWeapon(
        30588, "demon dragonbone sword", "the Demon's dragonbone sword",
        "A pale sword of carved dragonbone lies here.", "bone", 1, (9, 9), 3,
        46, 4, 4, 12,
        "Carved from the jaw of the old Aquamentus that guarded the Demon's\n"
        "depths. The bone is harder than steel and holds an edge for ever."),
    8: BossWeapon(
        30589, "lion four crowned axe", "the Lion's four-crowned axe",
        "A great axe with four crowned heads on its blade lies here.", "steel", 5, (10, 9), 21,
        52, 9, 6, 18,
        "The Lion's guardian had four heads and this axe has four crowns\n"
        "worked into its blade, one for each. It cleaves through scale as\n"
        "though scale were cloth."),
    9: BossWeapon(
        30590, "trident ganon", "the Trident of Ganon",
        "A black trident wreathed in a dull red light lies here.", "iron", 3, (11, 10), 11,
        59, 12, 3, 16,
        "Ganon's own weapon, black iron that drinks the light around it. In\n"
        "the hand of a hero it rivals the Master Sword itself, though it has\n"
        "never once been carried for a good cause before."),
}

# The best existing weapon each boss weapon was measured against, for the
# record: (score, what it is). Score is average damage plus damroll.
BOSS_WEAPON_BASELINES = {
    1: (10.0, "the large mace, sewer.are, level 8"),
    2: (17.0, "an icy dagger, icekeep.are, level 11"),
    3: (28.0, "a barbed whip, mushroom.are, level 20"),
    4: (28.0, "a barbed whip, mushroom.are, level 20"),
    5: (32.0, "the White Sword, Hyrule sword cave, level 30"),
    6: (33.5, "a two-handed sword, dresden.are, level 38"),
    7: (42.0, "A Glaive-Guisarme, azeroth.are, level 45"),
    8: (49.0, "(Flaming) A Light Saber, glitter.are, level 50"),
    9: (54.0, "the Power of the world, crypt.are, level 54"),
}


# --------------------------------------------------------------------------
# What each guardian drops besides its key, Heart Container, weapon and
# Heart Guard: five armour pieces, two of which fall at random each kill
# (hyrule_boss_drops() in src/hyrule.c, rolled in make_corpse). Each sits at
# the top of the band and scores a little above the best piece any other
# source gives a character of that level in that slot, measured with the
# Gear Finder's own scoring (get_best_gear in webadmin/server.py, warrior
# weights). The baselines are recorded beside each piece and
# tests/test_hyrule_boss_drops.py measures the world again.
# --------------------------------------------------------------------------

BOSS_DROP_FIRST = 30650
BOSS_DROPS_PER_GUARDIAN = 5
BOSS_DROPS_PER_KILL = 3
BOSS_EXTRA_DROP_FIRST = 30700
BOSS_EXTRA_DROP_STRIDE = 7
WEAR_SLOT_FLAG = {
    "finger": "B", "neck": "C", "body": "D", "head": "E", "legs": "F", "feet": "G",
    "hands": "H", "arms": "I", "shield": "J", "about": "K", "waist": "L", "wrist": "M",
}
APPLY_CODES = {"strength": 1, "dexterity": 2, "intelligence": 3, "constitution": 5,
               "mana": 12, "hit points": 13, "hitroll": 18, "damroll": 19,
               "save vs spell": 24}


@dataclass(frozen=True)
class DropPiece:
    slot: str
    keywords: str
    short: str
    armour: int
    affects: tuple[tuple[str, int], ...]
    baseline: str           # the best piece it was measured against: score, name
    lore: str


BOSS_DROPS: dict[int, tuple[DropPiece, ...]] = {
    1: (
        DropPiece("body", "aquamentus scale coat green", "a coat of Aquamentus scale", 4,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 13)), "21.0 a Rebel jumpsuit",
                  "Green scales the size of a palm, stitched to soft leather."),
        DropPiece("head", "horn crested helm aquamentus", "a horn-crested helm", 2,
                  (("save vs spell", -2), ("hit points", 19)), "7.6 the propeller hat",
                  "A light cap of hide with the young dragon's horn rising from its brow."),
        DropPiece("hands", "dragonclaw gloves claw", "a pair of dragonclaw gloves", 2,
                  (("hitroll", 1), ("damroll", 1), ("strength", 1), ("hit points", 14)),
                  "14.0 swordsman's gloves",
                  "Gloves tipped with the dragon's own claws, filed blunt for the fingers."),
        DropPiece("about", "eagle feather cloak", "an Eagle-feather cloak", 2,
                  (("hitroll", 2), ("damroll", 2), ("dexterity", 1)), "19.5 a commoner's piwafwi",
                  "Brown and white feathers from the Eagle's own eyrie, sewn in rows."),
        DropPiece("shield", "green scale buckler", "a green scale buckler", 2,
                  (("save vs spell", -2), ("hit points", 36)), "9.0 an arsenal buckler",
                  "A small round shield faced with one great green scale. Fire runs off it."),
    ),
    2: (
        DropPiece("body", "dodongo hide jerkin", "a Dodongo-hide jerkin", 7,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 22)),
                  "31.25 a Standard military battle armor",
                  "Grey, pebbled hide so thick it stands up on its own."),
        DropPiece("legs", "pebbled hide leggings", "a pair of pebbled-hide leggings", 4,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 4)),
                  "15.5 a pair of Roman-style leggings",
                  "Leggings of Dodongo hide, stiff at first and comfortable for ever after."),
        DropPiece("feet", "dodongo stompers boots", "a pair of Dodongo stompers", 3,
                  (("hitroll", 2), ("damroll", 2), ("dexterity", 2), ("hit points", 28)),
                  "24.75 some snakeskin boots",
                  "Wide, heavy boots made from the soles of the beast's own feet."),
        DropPiece("waist", "crescent buckled belt moon", "a crescent-buckled belt", 3,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 12)), "19.75 a quick sheathe",
                  "A plain belt with a silver buckle shaped like the Moon's crescent."),
        DropPiece("finger", "smoke grey moonstone ring", "a smoke-grey moonstone ring", 3,
                  (("hitroll", 1), ("damroll", 1), ("save vs spell", -2), ("hit points", 6)),
                  "11.75 a dwarven golden ring",
                  "A moonstone clouded grey, as though smoke had been trapped inside it."),
    ),
    3: (
        DropPiece("legs", "thornvine greaves", "a pair of thornvine greaves", 6,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 23)),
                  "30.5 a pair of blackened steel greaves",
                  "Greaves woven from Manhandla's thorned vine, hard as iron and still green."),
        DropPiece("about", "manhandla petal mantle", "a mantle of Manhandla's petals", 6,
                  (("hitroll", 1), ("damroll", 1), ("dexterity", 3), ("hit points", 25)),
                  "26.0 the cloak of the psionic",
                  "Four great petals, dried and joined at the collar, that rustle as you walk."),
        DropPiece("hands", "four bloom gauntlets", "a pair of four-bloom gauntlets", 5,
                  (("hitroll", 2), ("damroll", 2), ("strength", 2), ("hit points", 3)),
                  "24.75 the Titanic Horns of Capricon",
                  "Gauntlets with a closed flower-bud on each knuckle that snaps open in a fight."),
        DropPiece("wrist", "manji cross bracer", "a Manji-cross bracer", 5,
                  (("hitroll", 1), ("damroll", 1), ("dexterity", 3), ("hit points", 14)),
                  "17.25 bracers of defence",
                  "A bracer stamped with the turning four-armed cross of the Manji."),
        DropPiece("head", "flower crowned helm", "a flower-crowned helm", 6,
                  (("hitroll", 1), ("damroll", 1), ("save vs spell", -4), ("hit points", 8)),
                  "21.5 a Roman combat helmet",
                  "A helm ringed with a crown of hard red petals."),
    ),
    4: (
        DropPiece("body", "twin dragon hauberk gleeok", "a twin-dragon hauberk", 13,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 10)), "46.0 a bearskin coat",
                  "Mail of overlapping dragon scales, two necks worked in silver across the chest."),
        DropPiece("shield", "coiled snake shield", "a coiled-snake shield", 9,
                  (("hitroll", 2), ("damroll", 2), ("save vs spell", -5), ("hit points", 15)),
                  "27.95 a small round shield",
                  "A kite shield whose boss is a coiled serpent, mouth open and fangs bare."),
        DropPiece("arms", "fang vambraces", "a pair of fang vambraces", 6,
                  (("hitroll", 2), ("damroll", 2), ("strength", 1)),
                  "21.25 some platinum arm bands",
                  "Vambraces ridged with a row of the Gleeok's lesser fangs."),
        DropPiece("head", "twin horned helm", "a twin-horned helm", 9,
                  (("hitroll", 1), ("damroll", 1), ("save vs spell", -5), ("hit points", 7)),
                  "27.5 a great war helmet",
                  "A helm with two swept-back horns, one from each of the Snake's heads."),
        DropPiece("legs", "serpent scale greaves", "a pair of serpent-scale greaves", 9,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 30)), "37.5 etched steel leggings",
                  "Greaves of fine green scale that ripple like water when you move."),
    ),
    5: (
        DropPiece("body", "urchin spine mail", "a coat of urchin-spine mail", 16,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 33)),
                  "66.65 some Black velvet robes",
                  "Mail of Digdogger's spines laid flat; it hums faintly when struck."),
        DropPiece("hands", "spined gauntlets", "a pair of spined gauntlets", 8,
                  (("hitroll", 2), ("damroll", 2), ("strength", 3)), "28.75 obsidian gauntlets",
                  "Gauntlets studded with short urchin spines along the knuckles."),
        DropPiece("arms", "lizard hide armguards", "a pair of lizard-hide armguards", 8,
                  (("hitroll", 2), ("damroll", 2), ("strength", 3)),
                  "29.25 black steel vambraces",
                  "Armguards of mottled lizard hide, cool to the touch in any heat."),
        DropPiece("feet", "sand lizard boots", "a pair of sand-lizard boots", 8,
                  (("hitroll", 2), ("damroll", 2), ("dexterity", 4), ("hit points", 18)),
                  "29.5 Lamorak's spurs",
                  "Light boots that grip loose sand and stone alike."),
        DropPiece("about", "frilled lizard cloak", "a frilled lizard cloak", 11,
                  (("hitroll", 1), ("damroll", 1), ("dexterity", 1)),
                  "28.5 an armored shirt of chainmail",
                  "A cloak with a stiff frill at the collar that rises when danger is near."),
    ),
    6: (
        DropPiece("wrist", "amber eye bracer gohma", "a bracer set with an amber eye", 10,
                  (("hitroll", 3), ("damroll", 3), ("dexterity", 3)), "34.55 a white bracer",
                  "A bracer whose single amber stone seems to follow whatever moves."),
        DropPiece("shield", "gohma carapace shield", "Gohma's carapace shield", 13,
                  (("hitroll", 3), ("damroll", 3), ("save vs spell", -2)),
                  "35.25 a dented tower shield",
                  "A curved plate of the great crab's shell, harder than any forged shield."),
        DropPiece("head", "dragon crested helm", "a dragon-crested helm", 13,
                  (("hitroll", 1), ("damroll", 1), ("save vs spell", -2)), "32.5 a wolf helm",
                  "A full helm with a dragon's crest, the Dragon dungeon's own emblem."),
        DropPiece("finger", "unblinking eye ring", "an unblinking eye ring", 10,
                  (("hitroll", 2), ("damroll", 2), ("save vs spell", -5)), "25.95 a sapphire ring",
                  "A ring holding a tiny red lens that never closes."),
        DropPiece("feet", "pincer toed boots", "a pair of pincer-toed boots", 10,
                  (("hitroll", 3), ("damroll", 3), ("dexterity", 2)),
                  "33.25 a pair of mithril boots",
                  "Boots capped with curved shell at the toes, for a sure grip on wet stone."),
    ),
    7: (
        DropPiece("body", "demon scale plate", "a suit of demon-scale plate", 23,
                  (("hitroll", 7), ("damroll", 7), ("hit points", 21)),
                  "122.5 Knights of the Silver Hand Full Plate",
                  "Plate of the old dragon's darkened scales, each one scarred by a hundred fights."),
        DropPiece("head", "chipped horn crown", "a chipped-horn crown", 15,
                  (("hitroll", 2), ("damroll", 2), ("save vs spell", -8)),
                  "46.0 an ancient Ranger Lord's Stetson",
                  "A crown cut from the ancient Aquamentus's horn, chipped where blades struck it."),
        DropPiece("hands", "demonclaw gauntlets", "a pair of demonclaw gauntlets", 11,
                  (("hitroll", 4), ("damroll", 4), ("strength", 2)), "44.5 Gauntlets of Bravery",
                  "Heavy gauntlets with black claws for fingertips."),
        DropPiece("legs", "ancient scale greaves", "a pair of ancient-scale greaves", 15,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 10)),
                  "37.5 etched steel leggings",
                  "Greaves of scale gone almost black with age."),
        DropPiece("about", "demon wing cloak", "a demon-wing cloak", 15,
                  (("dexterity", 4),), "31.5 an oiled cloak",
                  "A cloak of leathery wing that folds itself about you when you stand still."),
    ),
    8: (
        DropPiece("body", "ashen dragon plate", "a suit of ashen dragon plate", 26,
                  (("hitroll", 9), ("damroll", 9), ("hit points", 4)), "143.0 Divine Breast Plate",
                  "Plate of grey, ash-dulled scale, still warm from four centuries of fire."),
        DropPiece("shield", "four crowned lion shield", "the four-crowned lion shield", 17,
                  (("hitroll", 4), ("damroll", 4), ("save vs spell", -10), ("hit points", 15)),
                  "52.85 a Ceresian kite",
                  "A lion's head on a field of ash, four crowns above it for the four heads."),
        DropPiece("waist", "lion head girdle", "a lion-head girdle", 13,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 34)), "48.75 a rib bone belt",
                  "A broad girdle fastened by a bronze lion's head."),
        DropPiece("wrist", "ash grey dragon bracer", "an ash-grey dragon bracer", 13,
                  (("hitroll", 5), ("damroll", 5), ("dexterity", 2)), "51.0 an elven bracelet",
                  "A bracer of ashen scale that leaves a smudge of soot on the skin."),
        DropPiece("arms", "ember armguards", "a pair of ember armguards", 13,
                  (("hitroll", 2), ("damroll", 2), ("strength", 1)),
                  "29.25 black steel vambraces",
                  "Armguards with a seam of live ember glowing along each edge."),
    ),
    9: (
        DropPiece("hands", "ganon black gauntlets", "Ganon's black gauntlets", 14,
                  (("hitroll", 4), ("damroll", 4), ("strength", 3)), "49.75 battle gloves",
                  "Gauntlets of black iron sized for a boar-king's hands, cinched to fit yours."),
        DropPiece("legs", "boar hide greaves", "a pair of boar-hide greaves", 19,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 7)), "44.5 some corduroys",
                  "Greaves of coarse blue hide, bristling at every seam."),
        DropPiece("arms", "ganon arm plates", "Ganon's arm plates", 14,
                  (("hitroll", 5), ("damroll", 5), ("strength", 1)), "52.5 titanic arm plates",
                  "Arm plates etched with the Triforce of Power, the lower triangle blackened."),
        DropPiece("waist", "girdle of power", "the girdle of Power", 14,
                  (("hitroll", 5), ("damroll", 5), ("hit points", 17)), "54.0 a combat belt",
                  "A girdle of gold links, its clasp a single dark triangle."),
        DropPiece("wrist", "trident chased bracer", "a trident-chased bracer", 14,
                  (("hitroll", 5), ("damroll", 5), ("dexterity", 1)), "51.0 an elven bracelet",
                  "A black bracer chased with the shape of Ganon's trident."),
    ),
}


# The rest of each guardian's table (owner, 2026-10-04): a piece for every
# armour slot its first five leave open -- every slot but the neck, which
# is the Heart Guard's, and for Ganon the head, his crown's -- each sized by
# the same measure as the first five and carrying mana as well, so a caster
# finds it as good as a fighter does. They live in a second block from
# BOSS_EXTRA_DROP_FIRST, BOSS_EXTRA_DROP_STRIDE to a guardian.
BOSS_EXTRA_DROPS: dict[int, tuple[DropPiece, ...]] = {
    1: (
        DropPiece("finger", "eagle eye ring amber", "an eagle's-eye ring", 2,
                  (("hit points", 24), ("mana", 3)),
                  "6.0 a glinting ring of silver",
                  "A brass ring set with a chip of amber, as sharp-sighted as the Eagle it is named for."),
        DropPiece("legs", "green scale leggings", "a pair of green-scale leggings", 2,
                  (("hit points", 16), ("mana", 3)),
                  "6.5 some soldier leggings",
                  "Leggings of the young dragon's smaller scales, light and supple."),
        DropPiece("feet", "talon boots eagle", "a pair of talon boots", 2,
                  (("hit points", 8), ("mana", 2)),
                  "3.25 spiked heel boots",
                  "Soft boots with a hooked talon sewn at each heel."),
        DropPiece("arms", "horn guard sleeves", "a pair of horn-guard sleeves", 2,
                  (("hit points", 34),),
                  "8.0 some dark metal bracers",
                  "Leather sleeves with slips of the dragon's horn laced over the forearm."),
        DropPiece("waist", "eagle buckle belt", "an eagle-buckled belt", 2,
                  (("hit points", 10), ("mana", 16)),
                  "3.5 leather belt",
                  "A belt whose bronze buckle is a spread-winged eagle."),
        DropPiece("wrist", "aquamentus scale band", "an Aquamentus scale band", 2,
                  (("hit points", 28),),
                  "7.0 an enchanted leather bracer",
                  "A wristband of one curled green scale, warm to the touch."),
    ),
    2: (
        DropPiece("head", "dodongo skull cap", "a Dodongo skull cap", 4,
                  (("hitroll", 1), ("damroll", 1), ("mana", 19)),
                  "11.2 a dark horned helmet",
                  "The bony plate from the top of the beast's head, padded inside."),
        DropPiece("hands", "pebble hide mitts", "a pair of pebble-hide mitts", 4,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 62), ("mana", 6)),
                  "22.4 some heavy wool mittens",
                  "Heavy mitts of pebbled grey hide that no blade has ever cut."),
        DropPiece("arms", "crescent armbands moon", "a pair of crescent armbands", 4,
                  (("hitroll", 1), ("damroll", 1)),
                  "8.0 some dark metal bracers",
                  "Silver armbands shaped like the waxing and the waning moon."),
        DropPiece("shield", "dodongo plate shield", "a Dodongo-plate shield", 8,
                  (("hit points", 12), ("mana", 2)),
                  "9.5 a Magical Shield",
                  "A shield made from a single plate of the beast's flank."),
        DropPiece("about", "moonlit cloak", "a moonlit cloak", 4,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 26), ("mana", 31)),
                  "19.5 a commoner's piwafwi",
                  "A pale blue cloak that seems to hold a little moonlight in its folds."),
        DropPiece("wrist", "silver crescent bracelet", "a silver crescent bracelet", 4,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 34), ("mana", 35)),
                  "17.25 bracers of defence",
                  "A slim bracelet ending in two silver crescents that never quite meet."),
    ),
    3: (
        DropPiece("finger", "thorn braided ring", "a ring of braided thorn", 5,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 14), ("mana", 15)),
                  "14.45 Lancelot's Signet Ring",
                  "Three thorns grown into a ring, still green and still sharp."),
        DropPiece("body", "bloom plated breastplate", "a bloom-plated breastplate", 10,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 60)),
                  "46.0 a bearskin coat",
                  "A breastplate faced with Manhandla's hard red petals, overlapping like scales."),
        DropPiece("feet", "rootstep boots", "a pair of rootstep boots", 5,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 70), ("mana", 7)),
                  "24.75 some snakeskin boots",
                  "Boots of woven root that grip the ground as though they grew there."),
        DropPiece("arms", "vine wrapped sleeves", "a pair of vine-wrapped sleeves", 5,
                  (("hitroll", 1), ("damroll", 1), ("mana", 3)),
                  "10.75 the Titanic Arm plates of Hercules",
                  "Sleeves bound round with living vine that tightens when you strike."),
        DropPiece("shield", "four petal shield", "a four-petal shield", 10,
                  (("hitroll", 1), ("damroll", 1)),
                  "13.2 Orcish Horde Shield",
                  "A round shield of four great petals, each one hard as horn."),
        DropPiece("waist", "manji cross sash", "a Manji-cross sash", 5,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 42)),
                  "19.75 a quick sheathe",
                  "A red sash embroidered with the turning four-armed cross of the Manji."),
    ),
    4: (
        DropPiece("finger", "coiled serpent ring", "a coiled-serpent ring", 7,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 4), ("mana", 30)),
                  "14.45 Lancelot's Signet Ring",
                  "A ring of a green serpent swallowing its own tail."),
        DropPiece("feet", "snakeskin treads", "a pair of snakeskin treads", 7,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 20), ("mana", 22)),
                  "24.75 some snakeskin boots",
                  "Silent boots of shed Gleeok skin, smooth one way and rough the other."),
        DropPiece("hands", "fang grip gloves", "a pair of fang-grip gloves", 7,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 20), ("mana", 10)),
                  "24.75 the Titanic Horns of Capricon",
                  "Gloves with small fangs set in the palms for a grip that will not slip."),
        DropPiece("about", "twin headed mantle", "a twin-headed mantle", 7,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 4), ("mana", 43)),
                  "28.5 an armored shirt of chainmail",
                  "A mantle whose collar ends in two snarling serpent heads."),
        DropPiece("waist", "scaled serpent girdle", "a scaled serpent girdle", 7,
                  (("hitroll", 2), ("damroll", 2), ("mana", 22)),
                  "19.75 a quick sheathe",
                  "A girdle of green scale that coils twice about the waist."),
        DropPiece("wrist", "venom green bracer", "a venom-green bracer", 7,
                  (("hitroll", 2), ("damroll", 2), ("mana", 41)),
                  "18.75 bracers of defence",
                  "A bracer of glossy green scale that weeps a little venom in the heat."),
    ),
    5: (
        DropPiece("finger", "urchin spine ring", "an urchin-spine ring", 8,
                  (("hitroll", 1), ("damroll", 1), ("mana", 29)),
                  "14.45 Lancelot's Signet Ring",
                  "A ring bristling with tiny urchin spines, blunted on the inside."),
        DropPiece("head", "lizard crest helm", "a lizard-crest helm", 8,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 16), ("mana", 20)),
                  "32.5 a wolf helm",
                  "A helm with a tall frilled crest that rises when you are angry."),
        DropPiece("legs", "spined greaves", "a pair of spined greaves", 8,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 44), ("mana", 113)),
                  "37.5 etched steel leggings",
                  "Greaves studded with Digdogger's short spines down each shin."),
        DropPiece("shield", "urchin shell shield", "an urchin-shell shield", 16,
                  (("hitroll", 2), ("damroll", 2), ("mana", 26)),
                  "27.95 a small round shield",
                  "A domed shield cut from the great urchin's shell, spines still at the rim."),
        DropPiece("waist", "sand hide belt", "a sand-hide belt", 8,
                  (("hitroll", 2), ("damroll", 2), ("mana", 20)),
                  "19.75 a quick sheathe",
                  "A broad belt of sandy lizard hide, cool however hot the day."),
        DropPiece("wrist", "lizard eye bracer", "a lizard's-eye bracer", 8,
                  (("hitroll", 2), ("damroll", 2), ("mana", 38)),
                  "18.75 bracers of defence",
                  "A bracer set with a yellow stone slit like a lizard's eye."),
    ),
    6: (
        DropPiece("body", "carapace cuirass gohma", "a carapace cuirass", 20,
                  (("hitroll", 2), ("damroll", 2), ("mana", 9)),
                  "66.65 some Black velvet robes",
                  "A cuirass of Gohma's shell, ridged and heavy and harder than steel."),
        DropPiece("legs", "crab leg greaves", "a pair of crab-leg greaves", 10,
                  (("hitroll", 3), ("damroll", 3), ("mana", 115)),
                  "37.5 etched steel leggings",
                  "Greaves of jointed shell from the great crab's own legs."),
        DropPiece("hands", "pincer gauntlets", "a pair of pincer gauntlets", 10,
                  (("hitroll", 3), ("damroll", 3), ("mana", 8)),
                  "28.75 obsidian gauntlets",
                  "Gauntlets with a hooked pincer over each fist."),
        DropPiece("arms", "shell vambraces", "a pair of shell vambraces", 10,
                  (("hitroll", 3), ("damroll", 3), ("mana", 14)),
                  "29.25 black steel vambraces",
                  "Vambraces of curved red shell that ring like bells when struck."),
        DropPiece("about", "dragon banner cloak", "a dragon-banner cloak", 10,
                  (("hitroll", 2), ("damroll", 2), ("mana", 36)),
                  "30.0 a chimaera cloak",
                  "A cloak cut from the Dragon dungeon's own banner, its beast in faded gold."),
        DropPiece("waist", "eye clasped belt", "an eye-clasped belt", 10,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 18), ("mana", 10)),
                  "19.75 a quick sheathe",
                  "A belt fastened with a clasp shaped like a single staring eye."),
    ),
    7: (
        DropPiece("finger", "demon horn ring", "a demon-horn ring", 12,
                  (("hitroll", 2), ("damroll", 2), ("hit points", 14), ("mana", 21)),
                  "28.5 a pirate's ring",
                  "A ring of black horn carved from the ancient dragon's brow."),
        DropPiece("feet", "ashstride boots", "a pair of ashstride boots", 12,
                  (("hitroll", 3), ("damroll", 3), ("mana", 15)),
                  "33.25 a pair of mithril boots",
                  "Boots that leave no print, even in the soft ash of the Demon's halls."),
        DropPiece("arms", "dragonbone vambraces", "a pair of dragonbone vambraces", 12,
                  (("hitroll", 3), ("damroll", 3), ("mana", 9)),
                  "29.25 black steel vambraces",
                  "Vambraces of pale dragonbone, light as wood and harder than iron."),
        DropPiece("shield", "demon scale tower shield", "a demon-scale tower shield", 24,
                  (("hitroll", 2), ("damroll", 2), ("mana", 33)),
                  "35.75 a shield of defense",
                  "A tall shield faced with dark scales, each the size of a hand."),
        DropPiece("waist", "bone link girdle", "a bone-link girdle", 12,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 8), ("mana", 8)),
                  "19.75 a quick sheathe",
                  "A girdle of linked dragon vertebrae that creaks as you breathe."),
        DropPiece("wrist", "ancient scale bracer", "an ancient-scale bracer", 12,
                  (("hitroll", 3), ("damroll", 3), ("hit points", 8), ("mana", 25)),
                  "34.55 a white bracer",
                  "A bracer of scale gone black with age, still warm at its heart."),
    ),
    8: (
        DropPiece("finger", "four crowned signet", "a four-crowned signet", 13,
                  (("hitroll", 4), ("damroll", 4), ("mana", 66)),
                  "38.0 An assassin's ring",
                  "A heavy signet ring stamped with four crowns, one for each of the Lion's heads."),
        DropPiece("head", "lion maned helm", "a lion-maned helm", 13,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 8), ("mana", 38)),
                  "55.0 battle helmet",
                  "A great helm crowned with a mane of ash-grey bristle."),
        DropPiece("legs", "ashen greaves", "a pair of ashen greaves", 13,
                  (("hitroll", 3), ("damroll", 3), ("mana", 100)),
                  "44.5 a pair of Solgartian battle armor leggings",
                  "Greaves of grey scale that smell faintly of a long-dead fire."),
        DropPiece("feet", "ember tread boots", "a pair of ember-tread boots", 13,
                  (("hitroll", 3), ("damroll", 3), ("mana", 35)),
                  "33.25 a pair of mithril boots",
                  "Boots whose soles glow faintly, as though they had walked through embers."),
        DropPiece("hands", "lion paw gauntlets", "a pair of lion-paw gauntlets", 13,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 32), ("mana", 9)),
                  "47.25 a pair of elven gloves",
                  "Gauntlets shaped like great paws, with curved claws of blackened bronze."),
        DropPiece("about", "drifting ash mantle", "a mantle of drifting ash", 13,
                  (("hitroll", 1), ("damroll", 1), ("hit points", 6), ("mana", 43)),
                  "32.5 an assassin's shroud",
                  "A grey mantle that sheds a fine ash wherever it goes and is never less."),
    ),
    9: (
        DropPiece("finger", "ganon ring power", "the ring of Power", 14,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 186), ("mana", 8)),
                  "76.75 The Masters Ring",
                  "A black iron ring holding one dark triangle, the Triforce of Power's shadow."),
        DropPiece("body", "dark lord plate ganon", "the Dark Lord's plate", 28,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 194), ("mana", 12)),
                  "143.0 Divine Breast Plate",
                  "Ganon's own armour, black plate edged in red, sized down by no smith alive."),
        DropPiece("feet", "boar king boots", "a pair of boar-king boots", 14,
                  (("hitroll", 4), ("damroll", 4), ("hit points", 2), ("mana", 31)),
                  "42.7 battle boots",
                  "Boots of blue boar hide, hoof-toed and heavier than they look."),
        DropPiece("shield", "black trident shield", "the black trident shield", 28,
                  (("hitroll", 4), ("damroll", 4), ("mana", 21)),
                  "52.85 (Dark) a Ceresian kite",
                  "A shield of black iron with Ganon's trident worked across its face."),
        DropPiece("about", "ganon crimson cape", "Ganon's crimson cape", 14,
                  (("hitroll", 1), ("damroll", 1), ("mana", 61)),
                  "32.5 an assassin's shroud",
                  "A heavy cape of crimson cloth that falls like poured blood."),
    ),
}

# Mana for the first five pieces, by index, so a caster finds them as
# good as a fighter does: sized to the Gear Finder's mage weights.
BOSS_DROP_MANA: dict[tuple[int, int], int] = {
    (1, 0): 1, (1, 1): 9, (1, 3): 14, (1, 4): 6, (2, 2): 22, (2, 3): 11,
    (2, 4): 3, (3, 1): 19, (3, 2): 20, (3, 3): 36, (4, 1): 5, (4, 2): 19,
    (4, 4): 3, (5, 0): 29, (5, 1): 13, (5, 2): 14, (5, 3): 17, (5, 4): 25,
    (6, 0): 30, (6, 1): 28, (6, 2): 2, (6, 3): 13, (6, 4): 18, (7, 0): 69,
    (7, 1): 11, (7, 2): 4, (7, 3): 89, (7, 4): 10, (8, 0): 79, (8, 1): 24,
    (8, 2): 12, (8, 3): 30, (8, 4): 37, (9, 0): 15, (9, 1): 70, (9, 2): 32,
    (9, 3): 18, (9, 4): 28,
}


def boss_drops(level: int) -> tuple[DropPiece, ...]:
    """Every piece a guardian can drop: the first five, then the rest."""
    return BOSS_DROPS[level] + BOSS_EXTRA_DROPS[level]


def boss_drop_vnum(level: int, index: int) -> int:
    if index < BOSS_DROPS_PER_GUARDIAN:
        return BOSS_DROP_FIRST + (level - 1) * BOSS_DROPS_PER_GUARDIAN + index
    return (BOSS_EXTRA_DROP_FIRST + (level - 1) * BOSS_EXTRA_DROP_STRIDE
            + index - BOSS_DROPS_PER_GUARDIAN)


def boss_drop_level(level: int, bands: dict[int, tuple[int, int]]) -> int:
    """Each piece is at the top of its band; Ganon's at 58, below the
    Master Sword's 59 ceiling of Death Mountain."""
    return 58 if level == 9 else bands[level][1]


def boss_drop_records(manifest: dict[str, Any]) -> list[str]:
    bands = manifest_bands(manifest)
    records = []
    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        title = dungeon["title"].removeprefix("The ")
        guardian = BOSS_NAMES[BOSS_MOBS[level]]
        item_level = boss_drop_level(level, bands)
        for index, piece in enumerate(boss_drops(level)):
            affects = piece.affects
            if BOSS_DROP_MANA.get((level, index)):
                affects = affects + (("mana", BOSS_DROP_MANA[(level, index)]),)
            applies = "\n".join(
                f"A\n{APPLY_CODES[name]} {value}" for name, value in affects)
            lore = textwrap.fill(
                f"{piece.lore} It fell from {guardian}, guardian of "
                f"{'Death Mountain' if level == 9 else 'the ' + title}.",
                width=DESCRIPTION_WIDTH)
            armour = piece.armour
            records.append(object_record(
                boss_drop_vnum(level, index), piece.keywords, piece.short,
                f"{piece.short[0].upper()}{piece.short[1:]} lies here.",
                "leather" if piece.slot in {"about", "waist", "feet", "hands"} else "steel",
                f"9 G A{WEAR_SLOT_FLAG[piece.slot]}",
                f"{armour} {armour} {armour} {armour} 0",
                item_level, 6 if piece.slot in {"body", "shield"} else 2,
                item_level * item_level * 5,
                f"E\n{piece.keywords}~\n{lore}\n~\n{applies}",
            ))
    return records


# --------------------------------------------------------------------------
# Item levels.
#
# Every item a player can get in Hyrule sits at or below the band of the
# place it is first found: a chest at its dungeon's band, a boss's Heart
# Guard at the top of that boss's band, a cave or a cellar at the band of
# the screen or dungeon it opens from. The retained catalog wrote them for
# the old 1-70 layout -- a level 15 wooden sword on the start screen, a
# level 17 boomerang in Level 1 -- so their level, values and (for the
# gear chests and Heart Guards) cost are rewritten here from the bands.
#
# The Master Sword keeps level 58, the NES's late-game sword; it is now
# Ganon's, and written whole by master_sword_record().
# --------------------------------------------------------------------------

def armor_values(level: int) -> str:
    """The catalog gear's own curve: an armour point per four levels."""
    armour = max(1, round(level / 4))
    return f"{armour} {armour} {armour} {max(1, round(armour * 0.62))} 0"


def weapon_dice(level: int) -> tuple[int, int]:
    """About 0.7 of a level in average damage, the catalog's chest weapons."""
    average = max(2.5, 0.7 * level)
    count = max(1, round(level / 5))
    size = max(2, round(2 * average / count - 1))
    return count, size


@dataclass(frozen=True)
class ItemLevel:
    level: int
    values: str | None = None   # None keeps the record's values
    cost: int | None = None     # rupees; None keeps the record's cost


# Items with one home, levelled by hand to the band they are found in.
ITEM_LEVELS = {
    # The start screen's cave, for a character on their first day.
    30219: ItemLevel(1, "1 2 4 1 0"),                 # wooden sword, 2d4
    # Level 1, band 2-8.
    30232: ItemLevel(4, "0 2 5 0 0"),                 # small boomerang, 2d5
    30222: ItemLevel(6, "9 2 5 6 0"),                 # short bow, 2d5
    # Level 2, band 8-14.
    30410: ItemLevel(12, "1 3 5 3 0"),                # Magical Boomerang, 3d5
    # Level 3, band 14-20.
    30411: ItemLevel(16),                             # the raft
    # Level 4, band 20-27.
    30412: ItemLevel(22, armor_values(22)),           # the stepladder
    # Level 5, band 27-33; the White Sword, Power Bracelet and Letter caves
    # open from band 5 screens too.
    30413: ItemLevel(30, armor_values(30)),           # the Recorder
    30251: ItemLevel(30, "1 10 5 20 D"),              # White Sword, 10d5 +2/+2
    30276: ItemLevel(30),                             # Power Bracelet
    # Level 6, band 33-40.
    30245: ItemLevel(38, "38 5 5 70 0"),              # the Magical Rod
    # Level 7, band 40-46.
    30414: ItemLevel(42),                             # the Red Candle
    # Level 8, band 46-52.
    30415: ItemLevel(48, armor_values(48)),           # the Magic Book
    30416: ItemLevel(48),                             # the Magical Key
    # (The Triforce pieces are written whole: see piece_record.)
    # Level 9, band 53-59: the Silver Arrow (54), the Red Ring of Hyrule
    # (58) and the Master Sword (58) are written whole further down. The
    # catalog's plain "red ring" (30261) is gone: see RETIRED_OBJECT_VNUMS.
}


def gear_item_levels(manifest: dict[str, Any]) -> dict[int, int]:
    """Chest gear spread across its dungeon's band; Heart Guards at its top.

    Each chest takes the levels its band adds over the band before -- the
    bands share their end levels -- from the bottom up, so that together
    with the Heart Guards every level from 1 to 59 has a piece.
    """
    bands = manifest_bands(manifest)
    heart_guards = set(BOSS_GEAR.values())
    levels = {BOSS_GEAR[level]: bands[level][1] for level in BOSS_GEAR}
    previous_high = 4                        # stage 0, the starter cave, is 1-4
    for stage, (_, gear_vnums) in GEAR_STAGES.items():
        pieces = [vnum for vnum in gear_vnums if vnum not in heart_guards]
        if stage == 0:
            low, width = 1, 4
        else:
            low, high = previous_high + 1, bands[stage][1]
            width = high - low + 1
            previous_high = high
        for index, vnum in enumerate(pieces):
            levels[vnum] = low + index * width // len(pieces)
    return levels


def relevel_object(body: str, vnum: int, level: int,
                   values: str | None = None, cost: int | None = None) -> str:
    """Rewrite a retained object's level, and optionally its values and cost.

    The level line is the first "level weight cost condition" line in the
    record; the values line is the one before it.
    """
    record = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)").search(body)
    if not record:
        raise ValueError(f"missing object record {vnum}")
    level_line = re.compile(r"(?m)^(-?\d+) (\d+) (\d+) ([PGAWDBR])(?=\r?$)")
    match = level_line.search(body, record.start(), record.end())
    if not match:
        raise ValueError(f"missing level line for object {vnum}")
    new_cost = match.group(3) if cost is None else str(cost * COPPER_PER_GOLD)
    replacement = f"{level} {match.group(2)} {new_cost} {match.group(4)}"
    start = match.start()
    if values is not None:
        values_start = body.rindex("\n", record.start(), start - 1) + 1
        start = values_start
        replacement = f"{values}\n{replacement}"
    return body[:start] + replacement + body[match.end():]


def relevel_catalog_items(body: str, manifest: dict[str, Any]) -> str:
    for vnum, level in sorted(gear_item_levels(manifest).items()):
        values_line = re.compile(rf"(?ms)^#{vnum}\r?\n(?:[^\n]*\n){{5}}([^\n]*)\n").search(body)
        old_values = values_line.group(1).split() if values_line else []
        if len(old_values) == 5 and _is_weapon(body, vnum):
            count, size = weapon_dice(level)
            values = f"{old_values[0]} {count} {size} {old_values[3]} {old_values[4]}"
        else:
            values = armor_values(level)
        body = relevel_object(body, vnum, level, values, level * level * 5)
    for vnum, item in ITEM_LEVELS.items():
        body = relevel_object(body, vnum, item.level, item.values, item.cost)
    return body


def _is_weapon(body: str, vnum: int) -> bool:
    record = re.compile(rf"(?ms)^#{vnum}\r?\n(?:[^\n]*\n){{4}}(\d+) ").search(body)
    return bool(record) and record.group(1) == "5"


def weapon_score(weapon: BossWeapon) -> float:
    count, size = weapon.dice
    return count * (size + 1) / 2 + weapon.damroll


# Mana on each guardian's weapon, so a caster finds it as good as a
# fighter does (the Gear Finder's mage weights; it weighs nothing for a
# warrior, so the warrior measure above is untouched). 2026-10-04.
BOSS_WEAPON_MANA = {1: 5, 2: 33, 3: 33, 4: 35, 5: 33, 6: 34, 7: 32, 8: 34, 9: 86}

# What each Heart Guard gives worn, beyond its armour (2026-10-04): it was
# armour alone and scored a fifth of the best neck in the game. Written onto
# the kept catalog record by add_object_applies. The Heart Guards are also
# map-room chest gear, so the chests carry the same pieces.
HEART_GUARD_APPLIES = {
    1: (("hitroll", 2), ("mana", 8)),
    2: (("hitroll", 2), ("damroll", 2), ("dexterity", 1), ("mana", 40)),
    3: (("hitroll", 3), ("damroll", 3), ("strength", 1), ("intelligence", 2), ("mana", 60)),
    4: (("hitroll", 3), ("damroll", 3), ("strength", 1), ("intelligence", 2), ("mana", 55)),
    5: (("hitroll", 3), ("damroll", 3), ("intelligence", 2), ("mana", 55)),
    6: (("hitroll", 3), ("damroll", 3), ("intelligence", 2), ("mana", 50)),
    7: (("hitroll", 3), ("damroll", 3), ("intelligence", 2), ("mana", 45)),
    8: (("hitroll", 5), ("damroll", 5), ("strength", 1), ("intelligence", 2), ("mana", 75)),
    9: (("hitroll", 6), ("damroll", 6), ("strength", 1), ("intelligence", 2), ("mana", 55)),
}


def add_object_applies(body: str, vnum: int, applies) -> str:
    """Give a kept object record stat applies, written straight after its
    level line, ahead of any extra description or trailer it already has.
    Applies already standing there are replaced, so the generator stays a
    fixed point on its own output."""
    record = re.compile(rf"(?ms)^#{vnum}\r?\n.*?(?=^#\d+\r?$|\Z)").search(body)
    if not record:
        raise ValueError(f"missing object record {vnum}")
    level_line = re.compile(r"(?m)^(-?\d+) (\d+) (\d+) ([PGAWDBR])(?=\r?$)")
    match = level_line.search(body, record.start(), record.end())
    if not match:
        raise ValueError(f"missing level line for object {vnum}")
    standing = re.compile(r"(?:\r?\nA\r?\n-?\d+ -?\d+)*").match(body, match.end())
    lines = "".join(f"\nA\n{APPLY_CODES[name]} {value}" for name, value in applies)
    return body[:match.end()] + lines + body[standing.end():]


def boss_weapon_record(dungeon_level: int) -> str:
    weapon = BOSS_WEAPONS[dungeon_level]
    count, size = weapon.dice
    lore = (
        f"{weapon.lore}\n"
        f"It is the prize of Level {dungeon_level}, carried by the guardian who rules there."
    )
    return object_record(
        weapon.vnum, weapon.keywords, weapon.short, weapon.long, weapon.material,
        "5 AG AN",
        f"{weapon.weapon_class} {count} {size} {weapon.attack} 0",
        weapon.level, weapon.weight, weapon.level * weapon.level * 6,
        f"E\n{weapon.keywords}~\n{lore}\n~\nA\n18 {weapon.hitroll}\nA\n19 {weapon.damroll}"
        f"\nA\n12 {BOSS_WEAPON_MANA[dungeon_level]}",
    )


# An exit's lock value as load_rooms reads it. 2 is a pickproof door that
# takes a key. 5 looks like the same thing -- load_rooms gives it the same
# bits -- but load_resets turns every reset of a lock 5 door into state 5,
# "trapped", so each one went off on four unlocks in five: every locked
# door in Hyrule was a trap until 2026-10.
LOCKED_DOOR = 2


@dataclass
class ExitSpec:
    destination: int
    locks: int = 0
    key_vnum: int = 0
    keyword: str = ""
    description: str = ""


# The sectors room_is_dark() blacks out at sunset: field, forest, hills,
# mountain and desert. Hyrule's overworld is all five, and standing in a
# field at night unable to see is not what the area is for.
ALWAYS_LIT_SECTORS = frozenset((2, 3, 4, 5, 10))


@dataclass
class RoomSpec:
    vnum: int
    name: str
    description: str
    flags: str = "N"
    sector: int = 2
    dungeon: bool = False
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


# Words that carry no identity, so they are not worth matching on.
KEYWORD_STOPWORDS = frozenset({"a", "an", "the", "of", "and", "his", "her"})


def merge_keywords(keywords: str, short: str) -> str:
    """Every word a player can see, plus the ones the builder chose.

    A player types what is in front of them -- `look old man' -- and the
    hand-written keyword lists routinely did not contain any of it. Folding
    the short description in means the visible name always works, while the
    explicit keywords stay first so deliberate aliases still win.
    """
    seen = []
    for word in keywords.split():
        lowered = word.lower()
        if lowered not in seen:
            seen.append(lowered)

    # Split on anything that is not a letter, so "blue-ring" offers both.
    current = ""
    for character in short.lower() + " ":
        if character.isalpha():
            current += character
            continue
        if current and current not in seen and current not in KEYWORD_STOPWORDS:
            seen.append(current)
        current = ""

    return " ".join(seen)


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
    keywords = merge_keywords(keywords, short)
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


# What each kind of person is made of. Everyone is ACT_IS_NPC and
# ACT_SENTINEL; the rest are the flags the catalog's own shopkeepers and old
# man always carried. is_hyrule_bystander() in src/fight.c keeps all of
# them out of every fight, whatever their level.
NPC_BODIES = {
    "moblin": ("pig", 50, "ABMV"),
    "fairy": ("elf", 50, "ABMV"),
    "zelda": ("human", 70, "AB"),
}


def npc_role(key: str) -> str:
    return key.split(":", 1)[0]


def new_mobile_records() -> str:
    """Hyrule's people, one record each, from the npcs table.

    Descriptions are plain prose wrapped here. Plain newlines matter:
    fread_string() turns every newline it reads into the game's own line
    ending as it goes, so spelling that ending out handed it a second
    carriage return to pass along.
    """
    records = []
    for key, npc in sorted(npc_table().items(), key=lambda item: item[1]["vnum"]):
        vnum = int(npc["vnum"])
        if vnum != ZELDA_VNUM and not NPC_VNUM_FIRST <= vnum <= NPC_VNUM_LAST:
            raise ValueError(f"npc {key} vnum {vnum} is outside {NPC_VNUM_FIRST}-{NPC_VNUM_LAST}")
        race, level, act_flags = NPC_BODIES.get(npc_role(key), ("human", 50, "ABMV"))
        records.append(mobile_record(
            vnum, npc["keywords"], npc["short"], npc["long"],
            wrap_description(npc["description"]), level, race=race, act_flags=act_flags,
        ))
    return "\n".join(records)


# obj->cost is copper; Hyrule quotes itself in rupees, which are gold.
COPPER_PER_GOLD = 10000


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
    """One #OBJECTS record. `cost` is in rupees, as the descriptions say.

    A rupee is a gold coin here -- the rupee piles are ITEM_MONEY with
    value[1] == TYPE_GOLD -- and obj->cost is counted in copper, so the
    price a sign advertises only holds if it is written out in copper.
    """
    record = f"""#{vnum}
{keywords}~
{short}~
{long}~
{material}~
{item_line}
{values}
{level} {weight} {cost * COPPER_PER_GOLD} P"""
    if extras:
        record += "\n" + extras.strip()
    return record


# What the shops sell, and what each of it is for (Plan 6 and Plan 8 in
# wiki/hyrule-area.md). src/hyrule.c gives each its use.
HYRULE_BOMBS_VNUM = 30695
HYRULE_BOMB_BAG_VNUM = 30696
HYRULE_GRAVESTONE_VNUM = 30697
MAGICAL_SWORD_VNUM = 30649
MAGICAL_SWORD_LEVEL = 38
MAGICAL_SWORD_DICE = (11, 5)
MAGICAL_SWORD_ROLLS = 3        # hitroll and damroll
MAGICAL_SHIELD_LORE = (
    "E\nmagical shield~\nA broad shield whose face is worked with a red cross and a golden bird.\n"
    "Held, it turns aside a tenth of any fire or magic thrown at you -- a\n"
    "guardian's fireballs, a wizzrobe's beam -- though the Mirror Shield,\n"
    "which does more, cannot be carried with it. Beware the like like.\n~")
SMALL_KEY_LORE = (
    "E\nkey small~\nA small key for Hyrule's dungeon doors. UNLOCK a locked door with it\n"
    "and the lock keeps it. It stays with you when you leave the game.\n~")
BAIT_LORE = (
    "E\nbait enemy food~\nStrong-smelling bait. FEED it to the hungry Goriya in the Demon's\n"
    "halls, which eats it, or FEED BAIT anywhere else to set it down: the\n"
    "enemies in the room forget you and turn to the smell for a while, and you\n"
    "pick the bait up again. A guardian is not fooled.\n~")


def magical_sword_record() -> str:
    """The NES Magical Sword, under the graveyard's loose gravestone.

    The Master Sword is Ganon's now, so the grave holds the sword that was
    there first: better than the White Sword and short of the Dragon
    guardian's eye-lance, for a character with twelve hearts.
    """
    count, size = MAGICAL_SWORD_DICE
    return object_record(
        MAGICAL_SWORD_VNUM, "magical sword blade grave", "the Magical Sword",
        "The Magical Sword lies here, its blade faintly blue.", "steel",
        "5 ABGUV AN", f"1 {count} {size} 3 D", MAGICAL_SWORD_LEVEL, 15, 20000,
        f"E\nmagical sword~\nThe sword that slept beneath the old graveyard while the Master Sword\n"
        f"went to Ganon. The old man who keeps it gives it only to one with\n"
        f"twelve hearts: see HEARTS.\n~\n"
        f"A\n18 {MAGICAL_SWORD_ROLLS}\nA\n19 {MAGICAL_SWORD_ROLLS}",
    )


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


# --------------------------------------------------------------------------
# The Master Sword.
#
# Ganon carries it, so it lands in his corpse in his chamber. It is meant
# to be the best weapon a mortal can get anywhere in the game, and the
# comparison is the one the boss weapons use -- average damage
# (value[1] * (value[2] + 1) / 2) plus damroll -- against every weapon at
# or below level 59 that a mortal can get, from a mobile, a room, a
# container, a shop or a quest. The best of those was Ganon's own trident
# at 63.5; outside Hyrule it was the Power of the world at 54.0. 13d9 with
# +5/+5 scores 70.0. Its other gift is haste for as long as it is wielded,
# an F record that equip_char and unequip_char apply and lift.
# --------------------------------------------------------------------------

MASTER_SWORD_VNUM = 30200
MASTER_SWORD_LEVEL = 58
MASTER_SWORD_DICE = (13, 9)
MASTER_SWORD_HITROLL = 5
MASTER_SWORD_DAMROLL = 5
# The best weapon a mortal could otherwise get, and the best outside
# Hyrule, as measured above: (score, what it is).
MASTER_SWORD_BASELINES = (
    (63.5, "the Trident of Ganon, hyrule.are, level 59"),
    (54.0, "the Power of the world, crypt.are, level 54"),
)
# ROM's F record: where (A, affected_by), location, modifier, bits.
AFF_SANCTUARY_FLAG = "H"
AFF_HASTE_FLAG = "V"


def master_sword_score() -> float:
    count, size = MASTER_SWORD_DICE
    return count * (size + 1) / 2 + MASTER_SWORD_DAMROLL


def master_sword_record() -> str:
    count, size = MASTER_SWORD_DICE
    description = f"""E
master sword blade evil's bane~
The Master Sword, the blade of evil's bane, forged to oppose the darkest
powers of Hyrule. Ganon took it from the hero's grave and wore it at his
hip, and it has waited there for a hand worthy of it.
While you wield it you move with the speed of the wind: it hastens you
for as long as it is in your hand, and the haste goes when it does.
~
A
18 {MASTER_SWORD_HITROLL}
A
19 {MASTER_SWORD_DAMROLL}
F
A 0 0 {AFF_HASTE_FLAG}"""
    return object_record(
        MASTER_SWORD_VNUM,
        "master sword blade triforce",
        "the Master Sword",
        "The Master Sword rests here, its sacred blade shining with golden light.",
        "steel",
        "5 ABGHUV AN",          # no alignment bar: anyone may wield it
        f"1 {count} {size} 3 DE",
        MASTER_SWORD_LEVEL,
        20,
        50000,
        description,
    )


def triforce_record() -> str:
    """The Triforce, whole: a light, so WEAR puts it in the light slot.

    It is named just "The Triforce" wherever it is shown -- the owner's
    wish -- and never "the complete Triforce".

    Worn there it gives the sight of a level 59 character with HOLYLIGHT
    on -- triforce_sight() in src/handler.c. value[2] 999 is the light
    that never burns down: create_object turns it into -1, which the
    tick's burn-down skips. (-1 cannot be written in the file itself:
    fread_flag does not read a minus sign.)
    """
    description = """E
triforce triangles~
Three golden triangles join as one, embodying Power, Wisdom, and Courage.
Nobody finds it whole: COMBINE TRIFORCE makes it from the nine pieces, one
from each of Hyrule's dungeon guardians, and it counts as all nine.
Wear it and it rises to hover at your shoulder, lighting the way, and the
world shows you everything: what is invisible, hidden or cloaked in the
dark, as a level 59 hero with holy light would see it -- though not the
gods who hide themselves above that.
~"""
    return object_record(
        30286,
        "triforce golden triangles",
        "The Triforce",
        "The Triforce floats here, radiant with golden power.",
        "gold",
        "1 ABGIV A",
        "0 0 999 0 0",
        58,
        1,
        50000,
        description,
    )


# --------------------------------------------------------------------------
# What the bosses and the enemies leave behind.
#
# Each of the first eight bosses drops a Heart Container, as in the NES:
# a hold-slot crystal at the top of its band giving twice that level in
# hit points, and from the Lizard on a point of constitution as well. The
# boss weapons and Heart Guards are above; the Triforce shard is in the
# room beyond the boss, where the NES keeps it.
#
# Ordinary enemies drop at random, rolled in make_corpse (src/fight.c):
# rupees (gold coins), a heart, a fairy or a clock, one object of each
# per band at the vnums below. src/merc.h names the same three bases.
# --------------------------------------------------------------------------

BOSS_HEART_CONTAINER_FIRST = 30591
DROP_HEART_FIRST = 30600
DROP_FAIRY_FIRST = 30610
DROP_CLOCK_FIRST = 30620
# Spell slots (const.c SLOT()): cure light, cure serious, cure critical,
# heal, haste.
SLOT_CURE_LIGHT, SLOT_CURE_SERIOUS, SLOT_CURE_CRITICAL = 16, 61, 15
SLOT_HEAL, SLOT_HASTE = 28, 502
# A heart is a small heal and a fairy a large one, each growing with the
# band: (spell, spell, spell), zero for none.
HEART_SPELLS = {
    1: (SLOT_CURE_LIGHT, 0, 0), 2: (SLOT_CURE_LIGHT, 0, 0),
    3: (SLOT_CURE_SERIOUS, 0, 0), 4: (SLOT_CURE_SERIOUS, 0, 0),
    5: (SLOT_CURE_CRITICAL, 0, 0), 6: (SLOT_CURE_CRITICAL, 0, 0),
    7: (SLOT_HEAL, 0, 0), 8: (SLOT_HEAL, 0, 0),
    9: (SLOT_HEAL, SLOT_CURE_CRITICAL, 0),
}
FAIRY_SPELLS = {
    1: (SLOT_CURE_SERIOUS, SLOT_CURE_SERIOUS, 0),
    2: (SLOT_CURE_SERIOUS, SLOT_CURE_SERIOUS, 0),
    3: (SLOT_CURE_CRITICAL, SLOT_CURE_CRITICAL, 0),
    4: (SLOT_CURE_CRITICAL, SLOT_CURE_CRITICAL, 0),
    5: (SLOT_HEAL, SLOT_CURE_CRITICAL, 0),
    6: (SLOT_HEAL, SLOT_CURE_CRITICAL, 0),
    7: (SLOT_HEAL, SLOT_HEAL, 0), 8: (SLOT_HEAL, SLOT_HEAL, 0),
    9: (SLOT_HEAL, SLOT_HEAL, SLOT_HEAL),
}


def boss_heart_container_record(dungeon_level: int, band: tuple[int, int],
                                title: str) -> str:
    low, high = band
    hit_points = 2 * high
    extras = f"A\n13 {hit_points}"
    if dungeon_level >= 5:
        extras += "\nA\n5 1"                # APPLY_CON
    extras = (
        f"E\nheart container~\n"
        f"The heart of the {title}'s guardian, crystallised. Held, it beats in\n"
        f"time with your own and lends you its strength.\n~\n{extras}"
    )
    return object_record(
        BOSS_HEART_CONTAINER_FIRST + dungeon_level - 1,
        f"heart container {title.lower()} crystal",
        f"the {title}'s Heart Container",
        "A pulsing Heart Container floats here, red as a living heart.",
        "crystal", "9 AG AO", "0 0 0 0 0",
        high, 1, high * high * 5, extras,
    )


def drop_potion_record(vnum: int, band: tuple[int, int], keywords: str,
                       short: str, long: str, spells: tuple[int, int, int],
                       cost: int, lore: str) -> str:
    low, high = band
    return object_record(
        vnum, keywords, short, long, "glass", "10 A AO",
        f"{high} {spells[0]} {spells[1]} {spells[2]} 0",
        low, 1, cost, f"E\n{keywords}~\n{lore}\n~",
    )


def drop_records(manifest: dict[str, Any]) -> list[str]:
    records = []
    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        band = tuple(dungeon["recommended_levels"])
        title = dungeon["title"].removeprefix("The ")
        if level <= 8:
            records.append(boss_heart_container_record(level, band, title))
        records.append(drop_potion_record(
            DROP_HEART_FIRST + level - 1, band, f"heart recovery {title.lower()}",
            "a recovery heart", "A small red heart glows here, beating faintly.",
            HEART_SPELLS[level], 2 * level,
            "A little red heart, the kind that spills from a fallen enemy.\n"
            "QUAFF it and it melts into you, closing a few wounds."))
        records.append(drop_potion_record(
            DROP_FAIRY_FIRST + level - 1, band, f"fairy bottled {title.lower()}",
            "a bottled fairy", "A tiny fairy flutters here, trapped in a glass.",
            FAIRY_SPELLS[level], 10 * level,
            "A fairy caught in a glass, glowing pink. QUAFF it and she is\n"
            "free, and her thanks closes a great many wounds."))
        records.append(drop_potion_record(
            DROP_CLOCK_FIRST + level - 1, band, f"clock flask {title.lower()}",
            "a clock-flask", "A small golden clock lies here, its hands stopped.",
            (SLOT_HASTE, 0, 0), 8 * level,
            "A golden clock whose face is a stopper. In the old tales a clock\n"
            "froze every enemy where it stood; QUAFF this and time is yours,\n"
            "and for a while you move twice for every step they take."))
    return records


# --------------------------------------------------------------------------
# The order of the dungeons.
#
# Every dungeon works the same way. Its guardian carries the dungeon's key;
# the key opens the locked door into the room behind the guardian and the
# locked chest standing in it; the chest holds the dungeon's Triforce piece
# and its treasure. The piece opens the next dungeon's entrance and the
# treasure gets you past the obstacle before the next guardian -- both
# checked per character by hyrule_progress_gate in src/act_move.c, which
# tests/test_hyrule_progression.py holds to the tables here. The plan, and
# why each pairing is faithful to the NES, is in wiki/hyrule-area.md.
# --------------------------------------------------------------------------

PIECE_VNUMS = {level: 30399 + level for level in range(1, 10)}     # 30400-30408
BOSS_KEYS = {**{level: 30629 + level for level in range(1, 9)},     # 30630-30637
             9: GANON_GOLDEN_KEY_VNUM}
CHESTS = {level: 30639 + level for level in range(1, 10)}          # 30640-30648
DUNGEON_TREASURE = {
    1: 30232,   # the boomerang: a Goriya's, in the NES
    2: 30410,   # the Magical Boomerang
    3: 30411,   # the raft
    4: 30412,   # the stepladder
    5: 30222,   # the bow, moved from Level 1 to arrive just before Gohma
    6: 30413,   # the Recorder, moved from Level 5 to arrive just before Level 7
    7: 30414,   # the Red Candle
    8: 30416,   # the Magical Key
    9: 30200,   # the Master Sword (MASTER_SWORD_VNUM)
}
# What each dungeon's two gates ask for: the entrance, the previous piece;
# the guardian's chamber, the previous treasure (and a substitute, if any).
ENTRY_NEEDS = {level: PIECE_VNUMS[level - 1] for level in range(2, 10)}
GUARDIAN_NEEDS = {level: DUNGEON_TREASURE[level - 1] for level in range(2, 10)}
GUARDIAN_ALSO = {2: DUNGEON_TREASURE[2]}   # the Magical Boomerang trips a lever too
PIECE_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth",
                  "seventh", "eighth", "ninth")


def piece_record(level: int, band: tuple[int, int], title: str) -> str:
    """A Triforce piece: treasure, not a key, so it is saved when you quit
    (save.c drops keys), and NODROP so it cannot be passed to somebody who
    has not earned it."""
    ordinal = PIECE_ORDINALS[level - 1]
    if level == 9:
        # Named for what it is to the player -- the last one -- at the
        # owner's request; "power" and "ganon" stay among the keywords so
        # the old name still finds it.
        keywords = "triforce final piece ninth power ganon"
        short = "the final Triforce piece"
        long = "The final Triforce piece, Ganon's own, smoulders here with a dark gold light."
        origin = ("the final piece, Ganon's own Triforce of Power, taken from "
                  "his great chest")
    else:
        keywords = f"triforce shard piece {ordinal} {level}"
        short = f"the {ordinal} Triforce shard"
        long = f"The {ordinal} shard of the Triforce of Wisdom gleams here."
        origin = f"the {ordinal} of the eight shards of Wisdom, from the {title}'s chest"
    use = ("It is the last; the others open the dungeons, and this one completes them."
           if level == 9 else
           f"Carry it: Level {level + 1}'s door opens only for one who has it.")
    lore = textwrap.fill(
        f"This is {origin}. It is one of nine Triforce pieces, one from each of "
        f"Hyrule's dungeon guardians: eight of Wisdom, and Ganon's Power. {use} "
        "With all nine in hand, type COMBINE TRIFORCE to make the Triforce.",
        width=DESCRIPTION_WIDTH,
    )
    return object_record(
        PIECE_VNUMS[level], keywords, short, long, "gold", "8 AGH AO",
        "0 0 0 0 0", band[0], 1, 100 * level, f"E\n{keywords}~\n{lore}\n~",
    )


def boss_key_record(level: int, band: tuple[int, int], title: str) -> str:
    plain = title.lower()
    return object_record(
        BOSS_KEYS[level], f"key {plain} guardian treasure", f"the {title}'s key",
        f"A heavy key with the mark of the {title} on its bow lies here.",
        "iron", "18 AG AO", "0 0 0 0 0", band[0], 1, 0,
        f"E\nkey {plain}~\nThe key the {title}'s guardian carried. It opens the locked door into\n"
        "the room behind the guardian's chamber, and the chest standing in\n"
        "that room.\n~",
    )


def chest_record(level: int, band: tuple[int, int], title: str) -> str:
    """Closed, locked and pickproof (A B C D), keyed to the guardian's key;
    reset_area closes and locks it again whenever it refills."""
    if level == 9:
        keywords, short = "chest great ganon golden", "Ganon's great chest"
        long = "A great chest of black iron and gold squats here, locked fast."
    else:
        keywords = f"chest treasure {title.lower()}"
        short = f"the {title}'s treasure chest"
        long = "A treasure chest, banded in iron and locked fast, stands here."
    return object_record(
        CHESTS[level], keywords, short, long, "iron", "15 G 0",
        f"100 ABCD {BOSS_KEYS[level]} 0 0", band[0], 500, 0,
    )


def chain_records(manifest: dict[str, Any]) -> list[str]:
    records = []
    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        band = tuple(dungeon["recommended_levels"])
        title = dungeon["title"].removeprefix("The ")
        records.append(chest_record(level, band, title))
        if level <= 8:
            records.append(boss_key_record(level, band, title))
        if level == 9:
            records.append(piece_record(level, band, title))
    return records



PLAN_KEYWORD = "hyrule-floor-plan"


def map_plan(dungeon: dict[str, Any]) -> str:
    """The floor plan src/hyrule.c draws a map from: eight rows of eight
    room vnums, north row first and 0 for no room, then the map room and
    the compass room, then each block-stair cellar and the room above it.
    The guardian, the treasure room and what the guardian's door needs come
    from the dungeon's row of hyrule_progress_gate, not from here."""
    rooms = {room["coordinate"]: room["vnum"] for room in dungeon["rooms"]}
    lines = []
    for row in range(8, 0, -1):
        lines.append(" ".join(
            str(rooms.get(f"{chr(ord('A') + column)}{row}", 0)) for column in range(8)))
    lines.append(f"map {rooms[dungeon['map_coordinate']]} "
                 f"compass {rooms[dungeon['compass_coordinate']]}")
    for cellar in dungeon["cellars"]:
        lines.append(f"cellar {cellar['vnum']} above {cellar['source_vnum']}")
    return "\n".join(lines)


def map_object_record(dungeon: dict[str, Any], compass: bool) -> str:
    level = dungeon["level"]
    title = dungeon["title"].removeprefix("The ")
    vnum = (30488 if compass else 30479) + level
    kind = "compass" if compass else "map"
    opcode = 91 if compass else 90
    values = f"{opcode} {dungeon['boss_vnum']} {dungeon['first_room_vnum']} {dungeon['last_room_vnum']} {level}"
    if compass:
        extras = (
            f"E\n{title.lower()} compass~\n"
            + textwrap.fill(
                f"A brass compass whose needle knows only the halls of Level {level}. "
                "LOOK at it inside that dungeon and it points the first step toward "
                "the Triforce chest, and says how many rooms away the chest is, and "
                "the guardian's chamber on the way.", width=DESCRIPTION_WIDTH)
            + "\n~")
    else:
        extras = f"E\n{PLAN_KEYWORD}~\n{map_plan(dungeon)}\n~"
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
            "heros hero tunic green courage relic",
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
        # 30578, a Blue Ring of Hyrule Ganon rolled for, is gone: the
        # ring shop's Blue Ring (30551) is the Blue Ring of Hyrule, and by
        # Ganon the Red Ring is the better ward anyway (the owner's call).
        object_record(
            30579,
            "red ring hyrule power relic",
            "the Red Ring of Hyrule",
            "A red ring burns here with a fierce protective light.",
            "gold",
            "9 G AB",
            "12 12 12 9 0",
            58,
            1,
            24000,
            f"""E
red ring hyrule power~
The ruby band holds the hard-won power of Death Mountain, and lies in its
deepest cellar. While worn, it wraps you in sanctuary for as long as it is
on your finger, and it reduces all damage you take by 20 percent. Worn with
the Blue Ring of Hyrule the two wards stack, but only one Red Ring may be
worn.
~
A
5 2
A
13 100
A
24 -3
F
A 0 0 {AFF_SANCTUARY_FLAG}""",
        ),
        object_record(
            30580,
            "mirror shield hyrule light relic",
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
combines with the Blue and Red Rings' wards.
~
A
24 -4
A
17 -5""",
        ),
        object_record(
            30581,
            "pegasus boots hyrule speed relic",
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
        # The money caves pay as you walk in (hyrule.c), so no pile lies on
        # their floors; these two are the dungeon cellars' rupees.
        object_record(30511, "thirty gold money coins", "30 gold coins", "Thirty gold coins gleam here.", "gold", "20 0 A", "30 2 0 0 0", 1, 0, 30),
        object_record(30512, "hundred gold money coins", "100 gold coins", "One hundred gold coins gleam here.", "gold", "20 0 A", "100 2 0 0 0", 1, 0, 100),
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
        object_record(30541, "magical shield shop", "a Magical Shield", "A Magical Shield is displayed for 130 gold.", "steel", "9 N AJ", "5 5 5 3 0", 15, 8, 130, f"{MAGICAL_SHIELD_LORE}\nA\n17 -5"),
        object_record(30543, "arrows arrow quiver shop", "a quiver of arrows", "A quiver of arrows is displayed for 80 gold.", "wood", "8 N AO", "0 0 0 0 0", 8, 2, 80,
                      "E\narrows arrow quiver~\nA quiver of arrows for the bow. Wield the bow and SHOOT an enemy in the\n"
                      "room: each arrow costs a gold coin, as it always did, and the quiver is\n"
                      "never empty while you can pay. An arrow is what finishes Gohma, and\n"
                      "one is all a pols voice can stand.\n~"),
        object_record(30544, "magical shield shop", "a Magical Shield", "A Magical Shield is displayed for 160 gold.", "steel", "9 N AJ", "5 5 5 3 0", 14, 8, 160, f"{MAGICAL_SHIELD_LORE}\nA\n17 -5"),
        object_record(30545, "key small shop", "a small key", "A small key is displayed for 100 gold.", "iron", "18 N A", "0 0 0 0 0", 1, 1, 100, SMALL_KEY_LORE),
        object_record(30546, "blue candle shop", "a Blue Candle", "A Blue Candle is displayed for 60 gold.", "wax", "1 N AO", "0 0 999 0 0", 5, 2, 60,
                      "E\nblue candle~\nA candle that never burns down. Hold it as a light, BURN a bush with it\n"
                      "to find what the bush hides, or BURN an enemy for a lick of flame.\n~"),
        object_record(30547, "magical shield bargain shop", "a Magical Shield", "A Magical Shield is displayed for 90 gold.", "steel", "9 N AJ", "5 5 5 3 0", 8, 8, 90, f"{MAGICAL_SHIELD_LORE}\nA\n17 -5"),
        object_record(30548, "food bait shop", "enemy bait", "Enemy bait is displayed for 100 gold.", "meat", "19 N A", "H 0 0 0 0", 8, 3, 100, BAIT_LORE),
        object_record(30549, "heart recovery shop", "a Recovery Heart", "A Recovery Heart is displayed for 10 gold.", "crystal", "10 N AO", "10 28 0 0 0", 1, 1, 10),
        object_record(30550, "key small bargain shop", "a small key", "A small key is displayed for 80 gold.", "iron", "18 N A", "0 0 0 0 0", 1, 1, 80, SMALL_KEY_LORE),
        object_record(30551, "blue ring hyrule shop", "the Blue Ring of Hyrule", "The Blue Ring of Hyrule is displayed for 250 gold.", "gold", "9 N AB", "5 5 5 3 0", 45, 1, 250,
                      "E\nblue ring hyrule~\nThe Blue Ring of Hyrule, a sapphire band. Worn, it takes a tenth off\n"
                      "every blow you suffer, 10 percent. Worn with the Red Ring the two wards\n"
                      "stack, but only one of each ring may be worn.\n~\nA\n13 15"),
        object_record(30552, "food bait bargain shop", "enemy bait", "Enemy bait is displayed for 60 gold.", "meat", "19 N A", "H 0 0 0 0", 20, 3, 60, BAIT_LORE),
        object_record(30553, "blue life potion medicine shop", "a blue Life Potion", "A blue Life Potion is displayed for 40 gold.", "glass", "10 N AO", "30 28 28 0 0", 1, 2, 40,
                      "E\nblue life potion~\nQUAFF it and it heals you twice over.\n~"),
        object_record(30554, "red second potion medicine shop", "a red 2nd Potion", "A red 2nd Potion is displayed for 68 gold.", "glass", "10 N AO", "30 28 28 0 0", 1, 2, 68,
                      "E\nred second potion~\nThe 2nd Potion: QUAFF it and it heals you twice over, and what is left\n"
                      "in the bottle turns blue -- a blue Life Potion, for later.\n~"),
        object_record(HYRULE_BOMBS_VNUM, "bombs bomb four", "four bombs", "Four round black bombs are displayed for 20 gold.", "iron", "8 N A", "4 0 0 0 0", 1, 2, 20,
                      "E\nbombs bomb~\nFour bombs to a purchase. BOMB a cracked wall or rock to open it, or\n"
                      "BOMB an enemy for a blast of fire; each uses one bomb. Dodongo swallows\n"
                      "one whole. Your bag carries eight, and the old men of Levels 5 and 7\n"
                      "sell room for four more each.\n~"),
        object_record(HYRULE_BOMB_BAG_VNUM, "bag bomb bigger satchel", "a bigger bomb bag", "A bigger bomb bag hangs from a peg, priced at 100 gold.", "leather", "8 N A", "0 0 0 0 0", 1, 1, 100,
                      "E\nbag bomb bigger~\nBUY it and your bag carries four more bombs, for good; the old man\n"
                      "keeps the bag and stitches the room into yours.\n~"),
        object_record(HYRULE_GRAVESTONE_VNUM, "gravestone grave headstone loose", "a loose gravestone", "One gravestone sits askew on its slab, as though it could be pushed.", "stone", "31 UV 0", "4 0 5 1 9"),
        magical_sword_record(),
    ])
    objects.extend(ganon_relic_records())
    objects.extend(boss_weapon_record(level) for level in sorted(BOSS_WEAPONS))
    objects.extend(boss_drop_records(manifest))
    objects.extend(drop_records(manifest))
    objects.extend(chain_records(manifest))
    return "\n".join(objects)


def world_sector(room: dict[str, Any]) -> int:
    """The sector an overworld screen stands on, read off its NES enemies.

    The enemies the NES draws on a screen say what the ground is: lynels,
    tektites and falling rocks live on Death Mountain's rock, leevers in
    sand, moblins in the woods. The top two rows are the mountain itself.
    """
    row = int(room["coordinate"][1:])
    kinds = set(room["entities"])
    if row >= 7 or kinds & {"red_lynel", "blue_lynel", "red_tektite",
                            "blue_tektite", "falling_rock"}:
        return 5
    if kinds & {"red_leever", "blue_leever"}:
        return 10
    if room["coordinate"] == LOST_WOODS or kinds & {"red_moblin", "blue_moblin"}:
        return 3
    return 2


# --------------------------------------------------------------------------
# Room prose.
#
# Names and descriptions live in data/hyrule_room_prose.json, written room
# by room from the NES screen or dungeon room each one stands for. Keys:
#   overworld  -- the manifest coordinate ("H1")
#   dungeons   -- "L<level>:<coordinate>", and "L<level>:cellar:<coordinate>"
#                 for the block-stair cellar under that room
#   special    -- the caves, shops and secrets that are not NES screens
# A dungeon room's name is prefixed "Level N: " here; the dungeons are the
# contiguous run of "Level N: ..." rooms, and nothing else is named so.
# A missing entry is an error rather than a fallback: the old fallback was
# a template that listed the room's occupants, which is what this replaced.
# --------------------------------------------------------------------------

LOST_WOODS = "E2"
LOST_HILLS = "H7"
DESCRIPTION_WIDTH = 75


def wrap_description(text: str) -> str:
    return textwrap.fill(" ".join(text.split()), width=DESCRIPTION_WIDTH)


class Prose:
    def __init__(self, data: dict[str, dict[str, dict[str, str]]]) -> None:
        self.data = data

    def entry(self, group: str, key: str) -> dict[str, str]:
        try:
            return self.data[group][key]
        except KeyError:
            raise KeyError(f"data/hyrule_room_prose.json has no {group} entry {key!r}") from None

    def name(self, group: str, key: str) -> str:
        return self.entry(group, key)["name"]

    def description(self, group: str, key: str) -> str:
        return wrap_description(self.entry(group, key)["description"])


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


GATE_EXIT_DESCRIPTIONS = {
    "raft": "Open water lies that way. Only a raft will carry you across.",
    "stepladder": "A narrow gap of water cuts across the way; a stepladder would bridge it.",
}


def build_rooms(manifest: dict[str, Any], prose: Prose) -> tuple[dict[int, RoomSpec], dict[str, int]]:
    rooms: dict[int, RoomSpec] = {}
    world_vnums = {room["coordinate"]: room["vnum"] for room in manifest["overworld"]["rooms"]}
    bands = manifest_bands(manifest)

    for room in manifest["overworld"]["rooms"]:
        coordinate = room["coordinate"]
        spec = RoomSpec(
            room["vnum"], prose.name("overworld", coordinate),
            prose.description("overworld", coordinate), "N", world_sector(room),
            entities={str(vnum): count for vnum, count in world_spawns(room, bands).items()},
        )
        for direction, exit_data in room["exits"].items():
            gate = exit_data["gate"]
            keyword = "" if gate == "open" else f"{gate} crossing"
            description = GATE_EXIT_DESCRIPTIONS.get(gate, "")
            spec.exits[direction] = ExitSpec(exit_data["to_vnum"], keyword=keyword, description=description)
        rooms[spec.vnum] = spec

    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        for room in dungeon["rooms"]:
            key = f"L{level}:{room['coordinate']}"
            spec = RoomSpec(
                room["vnum"], f"Level {level}: {prose.name('dungeons', key)}",
                prose.description("dungeons", key),
                "ADN", 11, dungeon=True,
                objects=list(room["items"]),
                entities={str(vnum): count for vnum, count in dungeon_spawns(level, room).items()},
                boss_level=level if room["role"] == "boss" else None,
            )
            for direction, exit_data in room["exits"].items():
                door_type = exit_data["type"]
                locks, key_vnum, keyword = 0, 0, ""
                if door_type == "locked":
                    locks, key_vnum, keyword = LOCKED_DOOR, 30227, "locked dungeon door"
                elif door_type == "shutter":
                    locks, keyword = 1, "shutter"
                elif door_type == "bombable":
                    locks, keyword = 4, f"cracked {direction} wall"
                spec.exits[direction] = ExitSpec(exit_data["to_vnum"], locks, key_vnum, keyword)
            rooms[spec.vnum] = spec

        for cellar in dungeon["cellars"]:
            key = f"L{level}:cellar:{cellar['source_coordinate']}"
            rooms[cellar["vnum"]] = RoomSpec(
                cellar["vnum"], f"Level {level}: {prose.name('dungeons', key)}",
                prose.description("dungeons", key),
                "ADN", 11, dungeon=True, objects=[cellar["item_vnum"]],
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

    def open_from_screen(world_vnum: int, cave_vnum: int, puzzle: str | None,
                         keyword: str, direction: str = "down") -> None:
        """A cave below a screen. A puzzle makes the way secret until the
        NES's act opens it (see hyrule_seal_refuses in src/act_move.c)."""
        add_two_way_exit(rooms, world_vnum, direction, cave_vnum,
                         locks=4 if puzzle else 0, keyword=keyword)
        if puzzle:
            puzzle_vnum = PUZZLE_OBJECTS[puzzle]
            rooms[world_vnum].puzzles.append(
                puzzle_vnum[direction] if isinstance(puzzle_vnum, dict) else puzzle_vnum)

    def cave(vnum: int, group: str, prose_key: str, objects: list[int],
             people: list[str]) -> RoomSpec:
        rooms[vnum] = RoomSpec(
            vnum, prose.name(group, prose_key), prose.description(group, prose_key),
            "ADN", 11, objects=objects,
            entities={str(npc_vnum(key)): 1 for key in people},
        )
        return rooms[vnum]

    # The named caves: each keeps its NES prize and the person who keeps it.
    cave_specs = [
        (30650, "H1", "wooden_sword_cave", [30219], None, "cave:H8"),
        (30651, "K8", "white_sword_cave", [30251], None, "cave:K1"),
        # The Hero's Grave: Ganon took the Master Sword long ago, and the
        # Magical Sword sleeps here as it did on the NES.
        (30652, "B6", "master_sword_grave", [MAGICAL_SWORD_VNUM], "grave", "cave:B3"),
        (30653, "O8", "letter_cave", [30500], None, "cave:O1"),
        (30659, "E2", "secret_return_tree", [30211], "burn", None),
        (30674, "E6", "power_bracelet_alcove", [30276], "armos", None),
    ]
    for vnum, coordinate, prose_key, objects, puzzle, person in cave_specs:
        cave(vnum, "special", prose_key, objects, [person] if person else [])
        open_from_screen(world_vnums[coordinate], vnum, puzzle, f"{puzzle or 'cave'} opening")

    # Take any one you want, and the Heart Container on the P6 dock. The
    # island and the dock are reached by raft and stepladder, from objects
    # on the shore rather than an exit.
    crossings = {"P6": 30539, "P3": 30540}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] not in {"take_any", "heart"}:
                continue
            guide = landmark["zelda_coordinate"]
            vnum = landmark["room_vnum"]
            if landmark["type"] == "take_any":
                cave(vnum, "special", f"take_any:{guide}", list(TAKE_ANY_OFFER),
                     [f"take_any:{guide}"])
            else:
                cave(vnum, "special", "heart_ledge", [TAKE_ANY_OFFER[0]], [])
            world_vnum = room["vnum"]
            if room["coordinate"] in crossings:
                rooms[world_vnum].objects.append(crossings[room["coordinate"]])
                rooms[vnum].exits["up"] = ExitSpec(world_vnum)
            else:
                open_from_screen(world_vnum, vnum, landmark.get("puzzle"),
                                 f"{landmark.get('puzzle') or 'cave'} opening")

    # The old men and old women who sell or give a hint.
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] != "hint":
                continue
            guide = landmark["zelda_coordinate"]
            cave(landmark["room_vnum"], "special", f"hint:{guide}", [], [f"hint:{guide}"])
            open_from_screen(room["vnum"], landmark["room_vnum"], landmark.get("puzzle"),
                             f"{landmark.get('puzzle') or 'open'} hint cave")

    # It's a secret to everybody: the moblin pays as you walk in, once per
    # character (hyrule_enter_room in src/hyrule.c), so nothing lies here.
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] != "rupee":
                continue
            guide = landmark["zelda_coordinate"]
            puzzle = landmark.get("puzzle")
            cave(landmark["room_vnum"], "special", f"rupee:{guide}", [], [f"moblin:{guide}"])
            open_from_screen(room["vnum"], landmark["room_vnum"], puzzle,
                             f"{puzzle or 'hidden'} coin grotto")

    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            if landmark["type"] not in {"shop", "potion_shop"}:
                continue
            guide = landmark["zelda_coordinate"]
            keeper = f"{SHOP_NPC_PREFIX[landmark['type']]}:{guide}"
            cave(landmark["room_vnum"], "special", f"{landmark['type']}:{guide}", [], [keeper])
            puzzle = landmark.get("puzzle")
            open_from_screen(room["vnum"], landmark["room_vnum"], puzzle,
                             f"{puzzle or 'open'} shop entrance",
                             landmark.get("direction", "down"))

    attraction_people = {"door_repair": "repair", "gamble": "gambler", "warp_hall": None}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            attraction_type = landmark["type"]
            if attraction_type not in attraction_people:
                continue
            guide = landmark["zelda_coordinate"]
            person = attraction_people[attraction_type]
            cave(landmark["room_vnum"], "special", f"{attraction_type}:{guide}",
                 [route["object_vnum"] for route in landmark.get("routes", [])],
                 [f"{person}:{guide}"] if person else [])
            open_from_screen(room["vnum"], landmark["room_vnum"], landmark.get("puzzle"),
                             f"{landmark.get('puzzle') or 'open'} "
                             f"{attraction_type.replace('_', ' ')} entrance")

    rooms[world_vnums["D4"]].objects.append(30225)
    rooms[world_vnums["J5"]].objects.append(30225)

    # The maze rooms read exactly like the screen they repeat. A counter in
    # the name ("[2/3]") told the player the answer the maze is asking for.
    # Lost Woods: north, west, south, west. East always escapes the maze.
    lost_woods = world_vnums[LOST_WOODS]
    lost_woods_east = rooms[lost_woods].exits.get("east")
    lost_woods_west = rooms[lost_woods].exits.get("west")
    for vnum in range(30750, 30753):
        rooms[vnum] = RoomSpec(
            vnum, rooms[lost_woods].name, rooms[lost_woods].description,
            "N", rooms[lost_woods].sector,
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
    lost_hills = world_vnums[LOST_HILLS]
    north_destination = rooms[lost_hills].exits["north"].destination
    previous = lost_hills
    for vnum in range(30753, 30757):
        rooms[vnum] = RoomSpec(
            vnum, rooms[lost_hills].name, rooms[lost_hills].description,
            "N", rooms[lost_hills].sector,
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

    # Every guardian's chamber opens on its treasure room through a door
    # locked with the guardian's key, and the treasure room holds the chest
    # the same key opens (see DUNGEON_CHAIN above). Each treasure room also
    # keeps its way home -- a returning light, or Zelda's portal -- so
    # nobody can be shut in it.
    for dungeon in manifest["dungeons"]:
        level = dungeon["level"]
        boss_vnum, goal_vnum = dungeon["boss_vnum"], dungeon["goal_vnum"]
        boss_room = next(room for room in dungeon["rooms"] if room["vnum"] == boss_vnum)
        direction = next(
            direction for direction, exit_data in boss_room["exits"].items()
            if exit_data["to_vnum"] == goal_vnum
        )
        title = dungeon["title"].removeprefix("The ").lower()
        add_two_way_exit(
            rooms, boss_vnum, direction, goal_vnum,
            locks=LOCKED_DOOR, key_vnum=BOSS_KEYS[level],
            keyword="golden door" if level == 9 else f"{title} treasure door",
        )
        rooms[goal_vnum].objects.append(CHESTS[level])
        rooms[goal_vnum].objects.append(30217 if level == 9 else 30529 + level)

    level_nine = manifest["dungeons"][8]
    rooms[level_nine["goal_vnum"]].flags = "ADKN"

    # Gear is deliberately available throughout each band, not only as a final reward.
    rooms[30650].objects.append(GEAR_STAGES[0][0])
    for dungeon in manifest["dungeons"]:
        chest_vnum, _ = GEAR_STAGES[dungeon["level"]]
        map_room_vnum = next(room["vnum"] for room in dungeon["rooms"] if room["coordinate"] == dungeon["map_coordinate"])
        rooms[map_room_vnum].objects.append(chest_vnum)

    return rooms, world_vnums


def room_flag_word(room: RoomSpec) -> str:
    """The flag field, with recall and light settled by where the room is.

    Hyrule used to set ROOM_NO_RECALL on all 443 rooms, and since nothing
    in the world exited into it, that made it a place staff could visit
    and nobody could leave. Only the dungeons keep the flag now -- walking
    out of Level 7 by saying a word is the opposite of what a dungeon is
    for. The overworld gets ROOM2_ALWAYS_LIT instead, because its sectors
    are the ones that go dark at sunset.

    This lived only in the generated area file for a while, hand-applied,
    which meant the next regeneration would have quietly undone it and
    taken tests/test_hyrule_progression.py down with it.
    """
    if room.dungeon:
        return room.flags

    flags = room.flags.replace("N", "")
    if room.sector in ALWAYS_LIT_SECTORS:
        return f"{flags}Z B"
    return flags or "0"


def render_room(room: RoomSpec) -> str:
    lines = [f"#{room.vnum}", f"{room.name}~", room.description, "~",
             f"0 {room_flag_word(room)} {room.sector}"]
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
    stock = shop_stock(manifest)
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
                for stock_vnum in stock.get(int(entity_vnum), []):
                    lines.append(f"G 1 {stock_vnum} 100")
                if room.vnum in boss_room_to_level and int(entity_vnum) == BOSS_MOBS[boss_room_to_level[room.vnum]]:
                    level = boss_room_to_level[room.vnum]
                    lines.append(f"G 1 {BOSS_GEAR[level]} 100")
                    lines.append(f"G 1 {BOSS_WEAPONS[level].vnum} 100")
                    if level <= 8:
                        lines.append(f"G 1 {BOSS_HEART_CONTAINER_FIRST + level - 1} 100")
                    # The dungeon's key: Ganon's is the Golden Key.
                    lines.append(f"G 1 {BOSS_KEYS[level]} 100")
        for object_vnum in room.objects:
            lines.append(f"O 0 {object_vnum} 0 {room.vnum}")
        for puzzle_vnum in room.puzzles:
            lines.append(f"O 0 {puzzle_vnum} 0 {room.vnum}")
        if room.vnum in resonance_rooms:
            lines.append(f"O 0 {resonance_rooms[room.vnum]} 0 {room.vnum}")

        for direction, exit_spec in sorted(room.exits.items(), key=lambda item: DIRECTION_NUMBERS[item[0]]):
            if exit_spec.locks:
                if exit_spec.key_vnum in BOSS_KEYS.values():
                    # A guardian's door is magical: its key unlocks it, while
                    # random area-reset traps, pick lock and doorbash cannot
                    # turn a progression gate into a dead end or a way round.
                    state = 3
                elif exit_spec.locks == 4:
                    # A Hyrule seal -- a cracked wall, a bush, an Armos, a
                    # block, the lake, the hungry Goriya -- is secret until
                    # the NES's act opens it. Reset as a plain closed door,
                    # anybody could OPEN it by its direction.
                    state = 4
                else:
                    state = 2 if exit_spec.locks == LOCKED_DOOR else 1
                lines.append(f"D 0 {room.vnum} {DIRECTION_NUMBERS[direction]} {state}")
                if exit_spec.locks == 4 and exit_spec.keyword.startswith("cracked"):
                    puzzle_vnum = PUZZLE_OBJECTS["bomb"].get(direction)
                    if puzzle_vnum:
                        lines.append(f"O 0 {puzzle_vnum} 0 {room.vnum}")

    for stage, (chest_vnum, gear_vnums) in GEAR_STAGES.items():
        for gear_vnum in gear_vnums:
            lines.append(f"P 0 {gear_vnum} 0 {chest_vnum}")
    for level in sorted(CHESTS):
        lines.append(f"P 0 {PIECE_VNUMS[level]} 0 {CHESTS[level]}")
        lines.append(f"P 0 {DUNGEON_TREASURE[level]} 0 {CHESTS[level]}")
    lines.append("O 0 30285 0 15068")
    lines.append("S")
    return "\n".join(lines)


def render_shops(manifest: dict[str, Any]) -> str:
    """Every keeper sells at the price on the sign and buys nothing (the
    five buy types are 0), so no shop is a way to turn Hyrule into coin."""
    lines = [
        f"{keeper_vnum} 0 0 0 0 0 100 75 0 23"
        for keeper_vnum in sorted(shop_stock(manifest))
    ]
    lines.append("0")
    return "\n".join(lines)


def remove_tier_records(body: str) -> str:
    """Drop every generated enemy record, whatever bands it was built for."""
    pattern = re.compile(r"(?ms)^#(\d+)\r?\n.*?(?=^#\d+\r?$|\Z)")

    def keep(match: re.Match[str]) -> str:
        vnum = int(match.group(1))
        return "" if TIER_VNUM_FIRST <= vnum <= TIER_VNUM_LAST else match.group(0)

    return pattern.sub(keep, body).strip()


def render_specials(retained: str, manifest: dict[str, Any]) -> str:
    """The retained spec_fun lines, less the retired and generated enemies."""
    lines = []
    for line in retained.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "M" and fields[1].isdigit():
            vnum = int(fields[1])
            if (vnum in RETIRED_MOBILE_VNUMS or vnum in BOSS_SPECIALS
                    or TIER_VNUM_FIRST <= vnum <= TIER_VNUM_LAST
                    or NPC_VNUM_FIRST <= vnum <= NPC_VNUM_LAST):
                continue
        if line.strip() == "S":
            continue
        lines.append(line.rstrip())
    lines.extend(
        f"M {vnum} {special} Load to: {BOSS_NAMES[vnum]}"
        for vnum, special in sorted(BOSS_SPECIALS.items())
    )
    # The fountain fairies restore whoever rests at their pond.
    lines.extend(
        f"M {npc['vnum']} spec_hyrule_fairy Load to: {npc['short']}"
        for key, npc in sorted(npc_table().items())
        if npc_role(key) == "fairy"
    )
    lines.extend(enemy_specials(manifest))
    lines.append("S")
    return "\n".join(line for line in lines if line)


ACT_AGGRESSIVE_LETTER = "F"
ACT_AGGRESSIVE_BIT = 1 << 5


def calm_mobiles(body: str) -> str:
    """Nothing in Hyrule is aggressive (owner, 2026-10-04): every mobile
    record, generated or kept from the catalog, has ACT_AGGRESSIVE taken out
    of its act flags. An enemy still fights back, and a shutter still waits
    for the room's enemies to die (hyrule_room_has_guardian in act_move.c
    no longer reads the flag). The act field is the first word after the
    fifth tilde: keywords, short, long, description, race."""
    out = []
    for record in re.split(r"(?m)^(?=#\d+\s*$)", body):
        pos = 0
        for _ in range(5):
            pos = record.find("~", pos)
            if pos < 0:
                break
            pos += 1
        if pos <= 0:
            out.append(record)
            continue
        line_start = record.find("\n", pos) + 1
        line_end = record.find("\n", line_start)
        if line_start <= 0 or line_end < 0:
            out.append(record)
            continue
        words = record[line_start:line_end].split(" ")
        act = words[0]
        if act.isdigit():
            act = str(int(act) & ~ACT_AGGRESSIVE_BIT)
        else:
            act = act.replace(ACT_AGGRESSIVE_LETTER, "") or "0"
        words[0] = act
        out.append(record[:line_start] + " ".join(words) + record[line_end:])
    return "".join(out)


def build_area(manifest_path: Path, area_path: Path, prose_path: Path = DEFAULT_PROSE,
               mob_prose_path: Path = DEFAULT_MOB_PROSE) -> None:
    global _NPC_TABLE
    manifest = load_json(manifest_path)
    prose = Prose(load_json(prose_path))
    mob_prose = load_json(mob_prose_path)
    _NPC_TABLE = mob_prose["npcs"]
    original = area_path.read_text(encoding="utf-8")
    header = original[:original.index("#MOBILES")].rstrip()
    mobile_body = strip_section_terminator(section(original, "#MOBILES", "#OBJECTS"), "#0")
    object_body = strip_section_terminator(section(original, "#OBJECTS", "#ROOMS"), "#0")
    specials_body = section(original, "#SPECIALS", "#RESETS")

    mobile_body = remove_records(mobile_body, NEW_MOBILE_VNUMS | RETIRED_MOBILE_VNUMS)
    mobile_body = remove_tier_records(mobile_body)
    for level, (mob_level, hit_points, damage) in BOSS_STATS.items():
        mobile_body = restat_mobile(mobile_body, BOSS_MOBS[level], mob_level, hit_points, damage)
        text = mob_prose["bosses"][str(level)]
        description = text["description"]
        if "\n" not in description:
            description = wrap_description(description)
        mobile_body = redescribe_mobile(
            mobile_body, BOSS_MOBS[level], text["long"], description,
            text.get("short"))
    mobile_body = rearm_mobile(mobile_body, GANON_VNUM, GANON_ARMOR)
    object_body = remove_records(object_body, NEW_OBJECT_VNUMS | RETIRED_OBJECT_VNUMS)
    object_body = replace_record(object_body, 30218, silver_arrow_object_record())
    object_body = replace_record(object_body, MASTER_SWORD_VNUM, master_sword_record())
    object_body = replace_record(object_body, 30286, triforce_record())
    for dungeon in manifest["dungeons"][:8]:
        object_body = replace_record(object_body, PIECE_VNUMS[dungeon["level"]], piece_record(
            dungeon["level"], tuple(dungeon["recommended_levels"]),
            dungeon["title"].removeprefix("The ")))
    # Keys are not saved when you quit (save.c); the Magical Key is a
    # treasure the next dungeon needs, so it must be.
    object_body = set_item_line(object_body, 30416, "8 G AO")
    # Hyrule quotes ordinary money; the burned bush's chest was a
    # "rupee chest" in the catalog.
    object_body = rename_object(object_body, 30457, "secret coin chest", "a secret coin chest")
    for dungeon in manifest["dungeons"]:
        object_body = replace_record(object_body, 30479 + dungeon["level"], map_object_record(dungeon, False))
        object_body = replace_record(object_body, 30488 + dungeon["level"], map_object_record(dungeon, True))
    object_body = relevel_catalog_items(object_body, manifest)
    for level, applies in HEART_GUARD_APPLIES.items():
        object_body = add_object_applies(object_body, BOSS_GEAR[level], applies)

    rooms, _ = build_rooms(manifest, prose)
    room_body = "\n".join(render_room(room) for room in sorted(rooms.values(), key=lambda item: item.vnum))
    resets = render_resets(rooms, manifest)

    mobiles = calm_mobiles(
        f"{mobile_body}\n{new_mobile_records()}\n{enemy_records(manifest, mob_prose)}")
    output = (
        f"{header}\n\n#MOBILES\n{mobiles}\n#0\n\n"
        f"#OBJECTS\n{object_body}\n{new_object_records(manifest)}\n#0\n\n"
        f"#ROOMS\n{room_body}\n#0\n\n"
        f"#SPECIALS\n{render_specials(specials_body, manifest)}\n\n"
        f"#RESETS\n{resets}\n\n"
        f"#SHOPS\n{render_shops(manifest)}\n\n#$\n"
    )
    area_path.write_text(output, encoding="utf-8", newline="\n")
    print(f"Wrote {area_path} with {len(rooms)} rooms and {len(resets.splitlines()) - 1} resets.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--prose", type=Path, default=DEFAULT_PROSE)
    parser.add_argument("--mob-prose", type=Path, default=DEFAULT_MOB_PROSE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_area(args.manifest.resolve(), args.area.resolve(), args.prose.resolve(),
               args.mob_prose.resolve())


if __name__ == "__main__":
    main()
