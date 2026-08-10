# Hyrule Area

## Overview

- File: `area/hyrule.are`
- Builder: Astarte
- Remastered vnum allocation: `30200-30799`
- Intended level range: `1-70`
- Primary entry: Hyrule arcade cabinet in Campus room `15068`
- Arrival room: Hyrule room `30200`
- Entry model: teleport only; Hyrule has no walking link to the main world

Hyrule is a remastered import of the original ToC2 area. The remaster keeps
the recognizable overworld, old personal spaces, secrets, and intentional
hazards while rebuilding the playable arc around all nine labyrinths from the
original *Legend of Zelda*. Combat, equipment, gates, and boss rewards now
form one continuous level 1 through 70 campaign.

## Progression Map

| Stage | Levels | Entrance and gate | Major item | Boss and completion reward |
| --- | ---: | --- | --- | --- |
| Overworld opening | 1-10 | Teleport to `30200`; starter cache in `30202` | Blue Candle and bomb bag are available before the first labyrinth | Route reaches the island statue at `30229` |
| Level 1: The Eagle | 11-20 | Portal from `30229` to `30339` | Boomerang and Bow | Aquamentus in `30353`; level 19-20 gear, boss key, shard `30400` |
| Level 2: The Moon | 21-30 | Portal at `30297`; shard `30400` opens the first seal | Magical Boomerang | Dodongo in `30376`; level 29-30 gear, boss key, shard `30401` |
| Level 3: The Manji | 31-40 | Stair at `30217`; shard `30401` opens the seal | Raft | Manhandla in `30613`; level 39-40 gear, boss key, shard `30402` |
| Level 4: The Snake | 41-50 | Use the Raft at `30299` to reach `30500`; shard `30402` opens the stair | Stepladder | Gleeok in `30633`; level 49-50 gear, boss key, shard `30403` |
| Level 5: The Lizard | 51-55 | Northern route from `30325`; shard `30403` opens the seal | Recorder | Digdogger in `30653`; level 54-55 gear, boss key, shard `30404` |
| Level 6: The Dragon | 56-60 | Stair at `30337`; shard `30404` opens the seal | Magical Wand | Gohma in `30673`; level 59-60 gear, boss key, shard `30405` |
| Level 7: The Demon | 61-64 | Play the Recorder at pool `30238`; shard `30405` opens the exposed stair | Red Candle | Elder Digdogger miniboss, hungry Goriya, ancient Aquamentus; level 63-64 gear and shard `30406` |
| Level 8: The Lion | 65-67 | Burn the solitary bush at `30295`; shard `30406` opens the seal | Magic Book and Magical Key | Ashen Gleeok in `30713`; level 67 gear and shard `30407` |
| Level 9: Death Mountain | 68-70 | Bomb Spectacle Rock at `30323`; shard `30407` opens the final seal | Silver Arrow and Red Ring | Ganon in `30436`; level 70 gear, Staff of Power, and Golden Key |

The level 58 Master Sword (`30200`) remains intentionally fixed at the level
requested for the remaster. It is sealed in pedestal `30235` in room `30466`;
the sixth shard (`30405`) is its unpickable key.

## Zelda Puzzle Rules

The remaster adds reusable, data-driven verbs for recognizable Zelda puzzle
interactions:

- `burn <target>` requires a lit candle and reveals burnable bush passages.
- `bomb <target>` requires a carried bomb bag and opens cracked walls.
- `play <instrument>` accepts the Recorder, whistle, or ocarina. It drains the
  Level 7 pool and weakens Digdogger encounters.
- `feed <guardian>` consumes bait and moves the hungry Goriya out of the way.
- `push <block>` uses the existing manipulation command for block passages.

Implemented tricks include the Eagle bomb shortcut and movable block, the
Moon bomb wall, the Manji and Snake block stairs, the Recorder weakness in the
Lizard, the Dragon false wall, the Demon's drained entrance, bait gate, nose
wall and nose block, the Lion's burned entrance and hidden passages, and the
Spectacle Rock entrance to Death Mountain.

Puzzle objects use `ITEM_MANIPULATION` (`31`) with this value layout:

| Value | Meaning |
| --- | --- |
| `value[0]` | Action type: `11` burn, `12` bomb, `13` play, `14` feed |
| `value[1]` | Room containing the exit to reveal, or `0` for an encounter-only effect |
| `value[2]` | Exit direction (`0-5`), or the target mobile vnum when `value[1]` is `0` |
| `value[3]` | Puzzle state: `1` ready, `2` solved |
| `value[4]` | `1` weakens the selected NPC prototype to one-third current hit points |

Successful puzzle objects are extracted and can return on the next area reset,
which keeps reset doors and repeatable boss encounters synchronized.

## Dungeon Maps And Compasses

Every labyrinth has its own collectible map and compass. Use
`read <dungeon> map` to display a route chart with the entrance, major item
vaults, boss, and Triforce chamber. Use `read <dungeon> compass` anywhere
inside that same labyrinth to receive the first general direction toward the
boss and a rough distance estimate. A short form such as `read compass` works
when only one matching item is present.

| Level | Map location | Compass location | Boss target |
| --- | --- | --- | --- |
| 1: Eagle | `30480` in `30347` | `30489` in `30344` | `30353` |
| 2: Moon | `30481` in `30362` | `30490` in `30369` | `30376` |
| 3: Manji | `30482` in `30611` | `30491` in `30602` | `30613` |
| 4: Snake | `30483` in `30631` | `30492` in `30622` | `30633` |
| 5: Lizard | `30484` in `30651` | `30493` in `30645` | `30653` |
| 6: Dragon | `30485` in `30670` | `30494` in `30663` | `30673` |
| 7: Demon | `30486` in `30683` | `30495` in `30692` | `30693` |
| 8: Lion | `30487` in `30706` | `30496` in `30712` | `30713` |
| 9: Death Mountain | `30488` in `30400` | `30497` in `30398` | `30436` |

Both use `ITEM_MAP` (`28`). Their values are data-driven:

| Value | Meaning |
| --- | --- |
| `value[0]` | `90` for a readable dungeon map, `91` for a boss compass |
| `value[1]` | Boss-room vnum |
| `value[2]` | First room vnum in the matching dungeon |
| `value[3]` | Last room vnum in the matching dungeon |
| `value[4]` | Dungeon level number (`1-9`) |

Compass routing ignores closed-door state but remains inside the recorded
dungeon bounds. It also understands permanent portal lights and climbable
stairs, which are required to follow the Moon and Death Mountain layouts.

## Equipment Curve

Every level from 1 through 70 has at least one sourced weapon or armor item.
General caches cover the interior levels of each band, while bosses carry the
top gear for their labyrinth. The high-level curve is compressed so all nine
dungeons fit below Ganon at level 70:

- Levels `1-10`: overworld starter equipment
- Levels `11-18`, `21-28`, `31-38`, `41-48`: dungeon exploration caches
- Levels `19-20`, `29-30`, `39-40`, `49-50`: first four boss pairs
- Levels `51-57`: Lizard and Dragon caches, with boss gear at `54-55`
- Level `58`: Master Sword
- Levels `59-60`: Gohma rewards
- Levels `61-67`: Demon and Lion caches and boss rewards
- Level `68`: Silver Arrow vault gear
- Level `69`: Red Ring vault gear
- Level `70`: Ganon's shadow crown and Staff of Power

Armor wear locations follow their descriptions rather than a generated slot
rotation: boots and greaves use feet, mail and tunics use body, shields use the
off hand, and the recurring Heart Guards form a neck-slot upgrade series.

The Level 3 Raft (`30411`) is a real `ITEM_BOAT`, so it also works with the
engine's deep-water movement rules. The waiting raft portal at `30299` is type
`6` and requires the player to carry `30411`; its return trip remains open.

The progression test in `tests/test_hyrule_progression.py` verifies continuous
gear coverage, semantic wear slots, cache placement, boss rooms and drops,
shard sources, canonical item gates, dungeon map and compass metadata, puzzle
targets, room reachability, and a return route from every nonlethal room.

## Ganon And Return Travel

1. The Silver Arrow and Red Ring are found within Level 9 before Ganon.
2. Ganon in `30436` drops the Golden Key (`30243`), the Staff of Power
   (`30244`), and level 70 gear (`30388`).
3. The Golden Key opens the northern door to the Golden Room (`30437`).
4. The chest in `30437` contains the complete Triforce (`30286`) and treasure.
5. The golden light in `30437` returns to Campus room `15068`.

The secret hollow tree in Dead Forest room `30270` is the second supported
return route to Campus. The Temple of Time quiz fallback in `30455` returns to
the Temple entrance (`30438`) instead of another game area. The Master Sword
altar in `30466` has the same return light, so completing the trial never
strands the player behind its one-way entrance.

## Intentional Hazards

The old `NO_RECALL` flags remain intentional. The following lethal routes are
also preserved and warned in nearby room text:

- Rooms `30316` and `30408` lead to death room `30467`.
- A wrong final Temple answer can lead through `30463` to death room `30470`.
- The red button in trapped room `30361` is labeled `DO NOT PUSH` and remains
  a lethal interaction.

Do not remove these hazards or flags as generic area-health cleanup. The
arcade, post-Ganon portal, and secret tree portal are the supported exits.

## Migration Notes

- Original range `15200-15550` was shifted by `+15000` before expansion.
- Six rooms and two objects copied from the active Forsaken clan hall were
  omitted, along with their Tarrasque reset.
- Empty legacy room `15500` was omitted.
- All retained mobiles received current-world hit, mana, damage, and boss
  tuning; reused enemies were split into dungeon-appropriate level variants.
- Legacy containers and rewards were repaired, including the Golden Room
  chest, Gohma's Silver Arrow chest, and the Master Sword pedestal.
