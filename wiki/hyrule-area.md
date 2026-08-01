# Hyrule Area

## Overview

- File: `area/hyrule.are`
- Builder: Astarte
- Vnum allocation: `30200-30550`
- Intended level range: `10-70`
- Primary entry: the Hyrule arcade cabinet in Campus room `15068`
- Arrival room: Hyrule room `30200`

This is a remastered import of the original ToC2 Hyrule area. Its rooms,
characters, puzzles, personal spaces, and novelty items were preserved while
the file format, vnums, combat statistics, rewards, and travel links were
updated for the current game.

## Progression

1. Enter the arcade cabinet in Campus room `15068` to arrive in room `30200`.
2. Explore Hyrule and its dungeons for the keys and equipment needed to reach
   Ganon in room `30436`.
3. Ganon carries object `30243`, the Golden Key. It unlocks the northern door
   into the Golden Room (`30437`).
4. The golden chest in `30437` contains object `30286`, the complete Triforce.
5. The Triforce is also the unpickable key for the stone pedestal in `30466`.
   Unlock and open the pedestal to claim the level 58 Master Sword (`30200`).

## Return Travel

- The bright golden light in the post-Ganon Golden Room (`30437`) returns to
  the Campus Games Room (`15068`).
- The secret hollow tree in the Dead Forest (`30270`) also returns to Campus.
- The Temple of Time quiz fallback in `30455` now returns to the Temple
  entrance (`30438`) instead of sending players into an unrelated area.

## Intentional Hazards

The area's original `NO_RECALL` flags are intentionally preserved. The
following lethal paths are also intentional and are warned in nearby room
text:

- Rooms `30316` and `30408` lead to the death room `30467`.
- A wrong answer in the final Temple trial can lead through `30463` to death
  room `30470`.
- The red button in trapped room `30361` is labeled `DO NOT PUSH` and remains
  a lethal interaction.

Do not remove these flags or hazards as generic area-health cleanup without a
specific design decision. The arcade, Golden Room, and secret tree portals are
the supported ways back to the main world.

## Migration Notes

- Original range `15200-15550` was shifted by `+15000`.
- Six rooms and two objects copied from the active Forsaken clan hall were
  removed from the import, along with their Tarrasque reset.
- Empty legacy room `15500` was removed.
- All retained mobiles received current-world hit, mana, damage, and boss
  tuning; the old definitions used zero dice and spawned with zero hit points.
- Legacy containers and rewards were repaired, including the Golden Room
  chest, Gohma's silver-arrow chest, the Master Sword pedestal, and previously
  unsourced treasure objects.
