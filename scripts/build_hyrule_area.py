"""Generate ``area/hyrule.are`` from the First Quest manifest.

What is generated, and from where:

- Rooms and resets come from ``data/hyrule_first_quest.json`` (the NES
  topology, the enemies each NES screen or room shows, the level bands)
  and their names and prose from ``data/hyrule_room_prose.json``.
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
DEFAULT_AREA = ROOT / "area" / "hyrule.are"

DIRECTION_NUMBERS = {
    "north": 0, "east": 1, "south": 2, "west": 3, "up": 4, "down": 5,
}
OPPOSITE_DIRECTIONS = {
    "north": "south", "east": "west", "south": "north", "west": "east",
    "up": "down", "down": "up",
}

NEW_MOBILE_VNUMS = set(range(30338, 30346))
NEW_OBJECT_VNUMS = (
    set(range(30500, 30515))
    | {30520}
    | set(range(30530, 30591))
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

# Characters who are not enemies keep the one catalog record they always had.
NPC_MOBS = {
    "old_man": 30228,
    "princess_zelda": 30338,
    "fairy": 30216,
}

# The catalog records that used to be spawned as ordinary enemies. Each is
# replaced by the per-band records generated from ENEMY_TYPES, so the old
# single-level record is dropped rather than left behind unspawned. 30335-
# 30337 (peahat, armos, the shared hazard) were generated here before.
RETIRED_MOBILE_VNUMS = {
    30200, 30201, 30202, 30203, 30205, 30206, 30207, 30208,
    30211, 30212, 30213, 30214, 30215, 30217, 30219, 30220, 30221,
    30300, 30301, 30302, 30304, 30306, 30308, 30310, 30312,
    30315, 30317, 30318, 30320, 30321, 30322, 30323, 30327,
    30328, 30329, 30330, 30335, 30336, 30337,
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
    long: str
    description: str
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
        "A red octorok waddles through the grass, cheeks puffed with a rock.",
        "A squat red creature on four stubby legs, all mouth and bulging eyes.\n"
        "It spits stones with surprising force, then waddles off to find a\n"
        "better angle.", 0.0, 0.8, 0.8, 6, size="S"),
    "blue_octorok": EnemyType(
        1, "fish", "octorok blue", "a blue octorok",
        "A blue octorok turns its snout toward you and spits.",
        "Bigger and steadier than its red cousins, the blue octorok plants its\n"
        "stubby legs and fires stone after stone without hurrying.",
        0.35, 1.0, 1.0, 6, size="S"),
    "red_moblin": EnemyType(
        2, "pig", "moblin red", "a red moblin",
        "A red moblin stalks between the trees with a spear on its shoulder.",
        "A dog-faced brute in a ragged loincloth, the moblin carries a\n"
        "bundle of crude spears and throws them with more strength than aim.",
        0.3, 1.0, 1.0, 2),
    "blue_moblin": EnemyType(
        3, "pig", "moblin blue", "a blue moblin",
        "A blue moblin snorts and lowers its spear.",
        "Heavier and meaner than the red moblins, this one has thrown a great\n"
        "many spears and learned from the ones that missed.",
        0.6, 1.15, 1.1, 2),
    "red_tektite": EnemyType(
        122, "insect", "tektite red spider", "a red tektite",
        "A red tektite crouches on its spindly legs, ready to spring.",
        "A one-eyed hopping spider with legs like bent wire. It bounds from\n"
        "rock to rock in great unpredictable arcs.",
        0.1, 0.7, 0.8, 10, "F", "S"),
    "blue_tektite": EnemyType(
        5, "insect", "tektite blue spider", "a blue tektite",
        "A blue tektite bobs on its long legs, watching you with its one eye.",
        "Larger than the red kind and far more patient, the blue tektite waits\n"
        "until you are close before it leaps.",
        0.45, 0.9, 0.9, 10, "F", "S"),
    "red_leever": EnemyType(
        6, "insect", "leever red sand", "a red leever",
        "A red leever spins up out of the sand in a spray of grit.",
        "A burrowing thing like a spinning thistle of hard red leaves. It\n"
        "surfaces beside its prey, whirls at them and sinks away again.",
        0.2, 0.9, 0.9, 22, size="S"),
    "blue_leever": EnemyType(
        7, "insect", "leever blue sand", "a blue leever",
        "A blue leever rises from the sand and whirls toward you.",
        "The blue leevers burrow deeper and surface harder than the red, and\n"
        "they do not give up the chase.",
        0.55, 1.1, 1.0, 22, size="S"),
    "red_lynel": EnemyType(
        127, "horse", "lynel red centaur lion", "a red lynel",
        "A red lynel paces the rocks, sword drawn and mane bristling.",
        "A lion's head on a horse's body, with a man's arms that hold a broad\n"
        "sword and a shield. Lynels throw their swords like spears.",
        0.8, 1.3, 1.2, 3, "K", "L"),
    "blue_lynel": EnemyType(
        8, "horse", "lynel blue centaur lion", "a blue lynel",
        "A blue lynel stamps a hoof and raises its sword.",
        "The blue lynels are the terror of the high country: tireless, armoured\n"
        "in hide like iron, and never far from the next of their kind.",
        1.0, 1.5, 1.3, 3, "K", "L"),
    "peahat": EnemyType(
        135, "plant", "peahat spinning flower", "a peahat",
        "A peahat skims over the ground on whirling petals.",
        "A thorny flower whose petals spin like a rotor, carrying it just out\n"
        "of reach. It is easiest to strike when it settles to rest.",
        0.4, 0.9, 0.9, 1, "F"),
    "zora": EnemyType(
        121, "fish", "zola zora river", "a Zola",
        "A Zola surfaces in the water, its eyes fixed on you.",
        "A finned water-dweller with a wide, sullen mouth. It rises, spits a\n"
        "ball of fire, and sinks out of sight before the steam clears.",
        0.45, 0.9, 1.1, 6),
    "ghini": EnemyType(
        130, "undead", "ghini ghost", "a ghini",
        "A ghini drifts among the headstones, one great eye wide open.",
        "A pale, round ghost with a single staring eye and stubby arms. It\n"
        "rises from the graves of those who were disturbed.",
        0.7, 1.2, 1.0, 5),
    "armos": EnemyType(
        136, "modron", "armos knight statue", "an Armos knight",
        "An Armos knight has stirred from its pedestal and lumbers forward.",
        "A stone soldier carved to stand guard forever. Touch one, and it\n"
        "wakes, and it remembers its orders.",
        0.85, 1.4, 1.2, 8, size="L"),
    "falling_rock": EnemyType(
        26, "modron", "boulder rock falling", "a tumbling boulder",
        "A boulder bounds down the slope toward you.",
        "A loose block of mountain rock, bouncing down the slope in great\n"
        "unstoppable leaps.", 0.5, 0.8, 1.2, 8, size="L"),
    # The dungeons.
    "keese": EnemyType(
        11, "bat", "keese bat", "a keese",
        "A keese flutters in jerky circles near the ceiling.",
        "A black cave bat with ragged wings. It darts in sudden zigzags and\n"
        "never holds still long enough to strike cleanly.",
        0.0, 0.5, 0.7, 10, "F", "T"),
    "gel": EnemyType(
        100, "unique", "gel slime", "a gel",
        "A small gel quivers on the flagstones.",
        "A blob of dark jelly no bigger than a fist. It creeps in fits and\n"
        "starts and clings to whatever it touches.",
        0.0, 0.45, 0.6, 12, size="T"),
    "zol": EnemyType(
        13, "unique", "zol slime", "a zol",
        "A zol heaves itself across the floor, trembling.",
        "A great quivering mound of slime. Cut it and it splits into gels, as\n"
        "if it had never been one creature at all.",
        0.3, 1.0, 0.9, 14),
    "bubble": EnemyType(
        104, "undead", "bubble skull flame", "a bubble",
        "A flaming skull bubble bounces from wall to wall.",
        "A grinning skull wreathed in flickering light. Its touch leaves a\n"
        "chill that loosens the grip on a sword.",
        0.3, 0.6, 0.7, 29, "F", "S"),
    "rope": EnemyType(
        102, "snake", "rope snake", "a rope",
        "A rope coils on the floor, tongue flickering.",
        "A red snake that idles until it catches sight of prey, then hurls\n"
        "itself straight at it.", 0.3, 0.8, 0.9, 10, size="S"),
    "stalfos": EnemyType(
        12, "undead", "stalfos skeleton", "a stalfos",
        "A stalfos skeleton rattles forward, sword raised.",
        "The bones of a long-dead soldier, held together by the dungeon's\n"
        "old malice and still remembering how to fence.",
        0.4, 1.0, 1.0, 3),
    "red_goriya": EnemyType(
        14, "goblin", "goriya red", "a red goriya",
        "A red goriya hefts a boomerang and grins.",
        "A dog-like goblin in a red tunic. It throws its boomerang, ducks, and\n"
        "catches it again on the way back.",
        0.4, 1.0, 1.0, 7),
    "blue_goriya": EnemyType(
        112, "goblin", "goriya blue", "a blue goriya",
        "A blue goriya spins a boomerang around one claw.",
        "Tougher than the red goriyas, and quicker with the boomerang.",
        0.7, 1.15, 1.1, 7),
    "wallmaster": EnemyType(
        101, "undead", "wallmaster hand", "a wallmaster",
        "A great disembodied hand creeps along the wall.",
        "A huge grey hand that slides out of the stonework. Whatever it seizes\n"
        "it carries back to the dungeon's entrance.",
        0.55, 1.0, 0.9, 8),
    "vire": EnemyType(
        106, "bat", "vire bat demon", "a vire",
        "A vire hops across the room on leathery wings.",
        "A blue imp with bat wings and a wicked grin. Strike it, and it\n"
        "bursts into a flurry of keese.", 0.6, 1.0, 1.0, 10),
    "like_like": EnemyType(
        15, "unique", "like likelike tube", "a like like",
        "A like like squats here, a wet tube of hungry flesh.",
        "A pulsing column of flesh with a mouth at the top. It swallows what\n"
        "it can, and it is fondest of shields.",
        0.6, 1.2, 0.8, 14),
    "pols_voice": EnemyType(
        108, "rabbit", "pols voice", "a pols voice",
        "A pols voice bounds about, its great ears twitching at every sound.",
        "A ghostly rabbit-eared thing that bounces from wall to wall. Loud\n"
        "noises hurt it more than any blade.",
        0.6, 1.0, 1.0, 15),
    "gibdo": EnemyType(
        19, "undead", "gibdo mummy", "a gibdo",
        "A gibdo shambles forward in rotting wrappings.",
        "A mummy bound in grave linen, slow and patient and terribly strong.",
        0.7, 1.25, 1.0, 8, special="spec_cast_undead"),
    "red_darknut": EnemyType(
        20, "human", "darknut red knight", "a red darknut",
        "A red darknut advances behind its shield, sword levelled.",
        "A knight in red armour with a shield that turns any blow struck from\n"
        "the front. Its sword arm never tires.",
        0.8, 1.3, 1.1, 3, "K"),
    "blue_darknut": EnemyType(
        115, "human", "darknut blue knight", "a blue darknut",
        "A blue darknut bars the way, shield high.",
        "The blue darknuts are the dungeon's elite guard: heavier armour,\n"
        "harder blows and no fear at all.",
        1.0, 1.5, 1.2, 3, "K"),
    "red_wizzrobe": EnemyType(
        110, "human", "wizzrobe red wizard", "a red wizzrobe",
        "A red wizzrobe flickers into view, wand already raised.",
        "A robed sorcerer who vanishes and reappears beside its prey to loose\n"
        "a bolt of magic.", 0.7, 0.9, 1.2, 19, special="spec_cast_mage"),
    "blue_wizzrobe": EnemyType(
        21, "human", "wizzrobe blue wizard", "a blue wizzrobe",
        "A blue wizzrobe glides forward, trailing sparks from its wand.",
        "The blue wizzrobes walk through their own spells and blink from place\n"
        "to place across a room.", 0.9, 1.0, 1.3, 19, special="spec_cast_mage"),
    "red_lanmola": EnemyType(
        117, "centipede", "lanmola red centipede", "a red lanmola",
        "A red lanmola writhes across the floor in a rush of segments.",
        "A great centipede of armoured segments that races around the room\n"
        "faster than the eye can follow.", 0.8, 1.3, 1.1, 10, "H", "L"),
    "blue_lanmola": EnemyType(
        17, "centipede", "lanmola blue centipede", "a blue lanmola",
        "A blue lanmola coils and uncoils, segment over segment.",
        "Longer, harder and faster than the red kind.",
        1.0, 1.5, 1.2, 10, "H", "L"),
    "patra": EnemyType(
        118, "unique", "patra eye", "a patra",
        "A patra hangs in the air, ringed by a whirl of lesser eyes.",
        "A great floating eye at the heart of a spinning cloud of smaller ones.\n"
        "The ring tightens and widens as it hunts.",
        1.0, 2.0, 1.3, 19, "F", "L"),
    "dodongo": EnemyType(
        18, "lizard", "dodongo dinosaur", "a dodongo",
        "A dodongo lumbers about on short thick legs.",
        "A rhinoceros-sized lizard with a hide no sword can cut. It swallows\n"
        "anything that looks edible, which is how most die.",
        1.0, 1.75, 1.1, 10, size="L"),
    "digdogger": EnemyType(
        109, "unique", "digdogger urchin", "a digdogger",
        "A digdogger rolls slowly around the room, spines twitching.",
        "A giant sea urchin with a single eye in its middle. It hates certain\n"
        "sounds, and shrinks when it hears them.",
        1.0, 1.75, 1.1, 8, size="L"),
    "blade_trap": EnemyType(
        137, "modron", "blade trap spiked", "a blade trap",
        "A spiked blade trap waits in the corner, ready to slam across the floor.",
        "A block of iron set with blades, it lies still until something moves\n"
        "in its line and then it slams across the room.",
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
# dashboard parser: roughly the median hit points and average damage for a
# spawned mobile at each level. A Hyrule enemy scales from these by its kind.
HIT_POINT_CURVE = (
    (1, 15), (5, 70), (10, 140), (15, 240), (20, 380), (25, 600),
    (30, 900), (35, 1350), (40, 1750), (45, 2400), (50, 3300),
    (55, 4600), (60, 6200), (65, 8000),
)
DAMAGE_CURVE = (
    (1, 3), (5, 5), (10, 8), (15, 11), (20, 15), (25, 19), (30, 24),
    (35, 28), (40, 33), (45, 38), (50, 43), (55, 49), (60, 55), (65, 62),
)


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


def enemy_record(kind: str, band: int, bands: dict[int, tuple[int, int]]) -> str:
    enemy = ENEMY_TYPES[kind]
    level = tier_level(kind, band, bands)
    hit_dice, damage_dice, hitroll = stat_fields(
        level,
        curve(HIT_POINT_CURVE, level) * enemy.hp,
        curve(DAMAGE_CURVE, level) * enemy.damage,
    )
    keywords = merge_keywords(enemy.keywords, enemy.short)
    # ACT_IS_NPC, ACT_SENTINEL, ACT_AGGRESSIVE: NES enemies hold their
    # screen or room. A wandering one walks out of its band, and in a
    # dungeon it piles into the next room's population.
    return f"""#{tier_vnum(kind, band)}
{keywords}~
{enemy.short}~
{enemy.long}
~
{enemy.description}
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


def world_spawns(room: dict[str, Any], bands: dict[int, tuple[int, int]]) -> dict[int, int]:
    """Mobile vnum -> count for one overworld screen.

    The overworld already asks for at most two of anything, so its counts
    are the manifest's; only the band changes with the screen's level.
    """
    band = band_index(room["recommended_level"], bands)
    spawns: Counter[int] = Counter()
    for kind, count in room["entities"].items():
        if kind in NPC_MOBS:
            spawns[NPC_MOBS[kind]] += count
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
        if kind in NPC_MOBS:
            spawns[NPC_MOBS[kind]] += 1
        elif kind not in ENEMY_TYPES:
            raise ValueError(f"Level {level} {room['coordinate']}: no mobile for {kind!r}")
    return dict(spawns)


def manifest_bands(manifest: dict[str, Any]) -> dict[int, tuple[int, int]]:
    return {
        dungeon["level"]: tuple(dungeon["recommended_levels"])
        for dungeon in manifest["dungeons"]
    }


def enemy_records(manifest: dict[str, Any]) -> str:
    bands = manifest_bands(manifest)
    return "\n".join(enemy_record(kind, band, bands) for kind, band in enemy_tiers(manifest))


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
# Gohma and the four-headed Gleeok are not, and Ganon is Ganon. Only the
# stat line is rewritten: names, flags, resistances and Ganon's silver
# vulnerability stay as the catalog has them.
# --------------------------------------------------------------------------

BOSS_STATS = {
    # dungeon: (level, hit points, average damage per blow)
    1: (10, 650, 15),     # Aquamentus
    2: (16, 1250, 21),    # Dodongo
    3: (23, 2400, 30),    # Manhandla
    4: (30, 4000, 39),    # Gleeok, two heads
    5: (36, 6000, 48),    # Digdogger
    6: (43, 8500, 57),    # Gohma
    7: (49, 9500, 63),    # Aquamentus again, older and harder
    8: (55, 15000, 73),   # Gleeok, four heads
    9: (62, 20000, 85),   # Ganon
}


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
        8, 2, 1, 6,
        "The shaft is cut from a young tree in the Eagle's courtyard, and the\n"
        "head is the horn Aquamentus wore on its snout. It is light, quick and\n"
        "far sharper than anything a beginner has a right to carry."),
    2: BossWeapon(
        30583, "dodongo tail club", "a Dodongo tail-club",
        "A heavy club of grey, pebbled hide lies here.", "leather", 4, (4, 8), 7,
        14, 2, 2, 12,
        "A length of Dodongo tail, dried hard as wood and bound at the grip.\n"
        "Nothing that fell on the Moon's floor ever cut that hide; this is\n"
        "what it feels like to be hit by it."),
    3: BossWeapon(
        30584, "manhandla bloom whip", "the Manhandla bloom-whip",
        "A whip of thorned green vine lies coiled here.", "wood", 7, (6, 9), 4,
        20, 2, 3, 5,
        "Four thorned heads once grew from Manhandla's heart, and this whip is\n"
        "braided from the vine that joined them. It lashes faster than it\n"
        "should, as though it were still trying to grow."),
    4: BossWeapon(
        30585, "gleeok twin fang glaive", "the Gleeok twin-fang glaive",
        "A long glaive set with two dragon fangs lies here.", "steel", 8, (6, 10), 21,
        27, 3, 3, 14,
        "Two fangs from the Snake's guardian are lashed side by side on an\n"
        "ash haft. The blade is still faintly warm, and smells of smoke."),
    5: BossWeapon(
        30586, "digdogger urchin flail", "the Digdogger urchin flail",
        "A spiked iron ball on a chain lies here.", "iron", 6, (7, 9), 8,
        33, 3, 2, 15,
        "The head of this flail is a single spine-cluster from the great\n"
        "urchin of the Lizard's den. It hums faintly when swung, a sound\n"
        "Digdogger would have hated."),
    6: BossWeapon(
        30587, "gohma eye lance", "the Gohma eye-lance",
        "A slender lance with a red crystal point lies here.", "steel", 3, (8, 10), 11,
        40, 3, 2, 10,
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
        59, 9, 3, 16,
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
    4: (31.5, "a small boomerang, Hyrule Level 1, level 17"),
    5: (31.5, "a Silver star-hilted dagger, glitter.are, level 32"),
    6: (41.0, "the White Sword, Hyrule sword cave, level 35"),
    7: (42.0, "A Glaive-Guisarme, azeroth.are, level 45"),
    8: (49.0, "(Flaming) A Light Saber, glitter.are, level 50"),
    9: (54.0, "the Power of the world, crypt.are, level 54"),
}


def weapon_score(weapon: BossWeapon) -> float:
    count, size = weapon.dice
    return count * (size + 1) / 2 + weapon.damroll


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
        f"E\n{weapon.keywords}~\n{lore}\n~\nA\n18 {weapon.hitroll}\nA\n19 {weapon.damroll}",
    )


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


def new_mobile_records() -> str:
    return "\n".join([
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
            30345, "hyrule money game elder gambler", "a gambling old man",
            # Plain newlines. fread_string() turns every newline it
            # reads into the game's own line ending as it goes, so
            # spelling that ending out here handed it a second
            # carriage return to pass along -- invisible while this
            # file was CRLF, and not once it was not.
            "An old man waits behind three concealed rupee signs.",
            "He offers the same risky money-making game found across the\n"
            "First Quest: three signs, one choice, and no way to tell them\n"
            "apart.\n"
            "\n"
            "Type GAMBLE to play.  Each go costs 10 rupees, and the sign you\n"
            "pick either pays you 50 or 20 rupees, or takes another 20 or 40\n"
            "off you.  All four outcomes are equally likely, so the house edge\n"
            "is real and patience is not a strategy.",
            50, act_flags="ABMV",
        ),
    ])


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
    objects.extend(boss_weapon_record(level) for level in sorted(BOSS_WEAPONS))
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
                    locks, key_vnum, keyword = 5, 30227, "locked dungeon door"
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

    cave_specs = [
        (30650, "H1", "wooden_sword_cave", 30219, None),
        (30651, "K8", "white_sword_cave", 30251, None),
        (30652, "B6", "master_sword_grave", 30200, "push"),
        (30653, "O8", "letter_cave", 30500, None),
        (30654, "L1", "heart_cave_bomb", 30501, "bomb"),
        (30655, "M6", "heart_cave_mountain", 30501, "bomb"),
        (30656, "H4", "heart_cave_burn", 30501, "burn"),
        (30657, "P6", "heart_island", 30501, "portal"),
        (30658, "P3", "heart_ledge", 30501, "portal"),
        (30659, "E2", "secret_return_tree", 30211, "burn"),
        (30674, "E6", "power_bracelet_alcove", 30276, "armos"),
    ]
    for vnum, coordinate, prose_key, object_vnum, puzzle in cave_specs:
        rooms[vnum] = RoomSpec(
            vnum, prose.name("special", prose_key),
            prose.description("special", prose_key),
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
            prose_key = f"rupee_{puzzle or 'open'}"
            rooms[cave_vnum] = RoomSpec(
                cave_vnum,
                prose.name("special", prose_key),
                prose.description("special", prose_key),
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
            puzzle = landmark.get("puzzle")
            if landmark["type"] == "potion_shop":
                prose_key = "potion_shop"
            else:
                prose_key = "shop_secret" if puzzle else "shop"
            rooms[shop_vnum] = RoomSpec(
                shop_vnum,
                prose.name("special", prose_key),
                prose.description("special", prose_key),
                "ADN", 11, entities={str(keeper_vnum): 1},
            )
            world_vnum = room["vnum"]
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

    attraction_keepers = {"door_repair": 30344, "gamble": 30345, "warp_hall": None}
    for room in manifest["overworld"]["rooms"]:
        for landmark in room["landmarks"]:
            attraction_type = landmark["type"]
            if attraction_type not in attraction_keepers:
                continue
            keeper_vnum = attraction_keepers[attraction_type]
            attraction_vnum = landmark["room_vnum"]
            rooms[attraction_vnum] = RoomSpec(
                attraction_vnum,
                prose.name("special", attraction_type),
                prose.description("special", attraction_type),
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
                    lines.append(f"G 1 {BOSS_WEAPONS[level].vnum} 100")
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
            if vnum in RETIRED_MOBILE_VNUMS or TIER_VNUM_FIRST <= vnum <= TIER_VNUM_LAST:
                continue
        if line.strip() == "S":
            continue
        lines.append(line.rstrip())
    lines.extend(enemy_specials(manifest))
    lines.append("S")
    return "\n".join(line for line in lines if line)


def build_area(manifest_path: Path, area_path: Path, prose_path: Path = DEFAULT_PROSE) -> None:
    manifest = load_json(manifest_path)
    prose = Prose(load_json(prose_path))
    original = area_path.read_text(encoding="utf-8")
    header = original[:original.index("#MOBILES")].rstrip()
    mobile_body = strip_section_terminator(section(original, "#MOBILES", "#OBJECTS"), "#0")
    object_body = strip_section_terminator(section(original, "#OBJECTS", "#ROOMS"), "#0")
    specials_body = section(original, "#SPECIALS", "#RESETS")

    mobile_body = remove_records(mobile_body, NEW_MOBILE_VNUMS | RETIRED_MOBILE_VNUMS)
    mobile_body = remove_tier_records(mobile_body)
    for level, (mob_level, hit_points, damage) in BOSS_STATS.items():
        mobile_body = restat_mobile(mobile_body, BOSS_MOBS[level], mob_level, hit_points, damage)
    object_body = remove_records(object_body, NEW_OBJECT_VNUMS)
    object_body = replace_record(object_body, 30218, silver_arrow_object_record())
    for dungeon in manifest["dungeons"]:
        object_body = replace_record(object_body, 30479 + dungeon["level"], map_object_record(dungeon, False))
        object_body = replace_record(object_body, 30488 + dungeon["level"], map_object_record(dungeon, True))

    rooms, _ = build_rooms(manifest, prose)
    room_body = "\n".join(render_room(room) for room in sorted(rooms.values(), key=lambda item: item.vnum))
    resets = render_resets(rooms, manifest)

    output = (
        f"{header}\n\n#MOBILES\n{mobile_body}\n{new_mobile_records()}\n"
        f"{enemy_records(manifest)}\n#0\n\n"
        f"#OBJECTS\n{object_body}\n{new_object_records(manifest)}\n#0\n\n"
        f"#ROOMS\n{room_body}\n#0\n\n"
        f"#SPECIALS\n{render_specials(specials_body, manifest)}\n\n"
        f"#RESETS\n{resets}\n\n"
        f"#SHOPS\n{render_shops()}\n\n#$\n"
    )
    area_path.write_text(output, encoding="utf-8", newline="\n")
    print(f"Wrote {area_path} with {len(rooms)} rooms and {len(resets.splitlines()) - 1} resets.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--area", type=Path, default=DEFAULT_AREA)
    parser.add_argument("--prose", type=Path, default=DEFAULT_PROSE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_area(args.manifest.resolve(), args.area.resolve(), args.prose.resolve())


if __name__ == "__main__":
    main()
