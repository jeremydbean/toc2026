# Hyrule: First Quest

## Status

Hyrule is a generated level 1-70 campaign based on the First Quest from the
original *Legend of Zelda*. It replaces the old ToC2 room layout while retaining
the useful Hyrule mobile and object catalog.

| Property | Value |
| --- | --- |
| Area file | `area/hyrule.are` |
| Reserved vnums | `30200-30799` |
| Entry object | Hyrule arcade cabinet `30285` in Campus room `15068` |
| Arrival | Overworld screen `H1`, room `30200` |
| Exit model | Secret return tree and post-Ganon return light |
| Recall | Disabled in every Hyrule room |
| Level range | `1-70` |
| Canonical geometry | 128 overworld screens plus 246 dungeon rooms and cellars |
| Generated area size | 443 rooms and 2,265 reset records |

There is no walking exit from the main world into Hyrule. Players arrive by
entering the arcade cabinet, matching the intended "teleported into Zelda"
opening. They can leave through the burned secret tree at `E2` or the return
light in Zelda's room after Ganon.

## Sources Of Truth

Do not hand-edit generated rooms or resets in `area/hyrule.are`. The checked-in
source chain is:

1. `data/hyrule_first_quest.json` stores normalized screen, room, encounter,
   door, landmark, shop, secret, and progression data.
2. `scripts/build_hyrule_area.py` combines that manifest with the retained area
   catalog and writes `area/hyrule.are`.
3. `tests/test_hyrule_progression.py` checks geometry, placement, progression,
   reachability, resets, services, and generation idempotence.

The manifest itself is built by `scripts/build_hyrule_manifest.py`. Its image
diagnostics come from:

- [NESMaps First Quest maps](https://www.nesmaps.com/maps/Zelda/Zelda.html)
- [Nintendo's Zelda manual](https://www.nintendo.co.jp/clv/manuals/en/pdf/CLV-P-NAANE_en.pdf)
- [The Video Game Level Corpus](https://github.com/TheVGLC/TheVGLC)
- [zelda1-disassembly](https://github.com/aldonunez/zelda1-disassembly)
- [GameFAQs First Quest guide](https://gamefaqs.gamespot.com/nes/563433-the-legend-of-zelda/faqs/75987/quick-guide)

Reference images and sprite sheets are audit inputs and are deliberately not
committed. The normalized JSON contains the data needed for ordinary builds.

## Coordinate System

The manifest uses columns `A-P` and rows `1-8`, with `H1` as the southern
starting screen. Printed Zelda guides usually number from north to south, so a
guide coordinate `(column, row)` becomes `(column, 9 - row)` in the manifest.

Examples:

| First Quest guide | Manifest | Landmark |
| --- | --- | --- |
| `H8` | `H1` | Starting cave |
| `N7` | `N2` | Level 8 |
| `F1` | `F8` | Level 9 |
| `K1` | `K8` | White Sword |
| `B3` | `B6` | Master Sword |
| `O1` | `O8` | Letter |
| `E3` | `E6` | Power Bracelet |

Service landmarks also retain a `zelda_coordinate` field so reviewers can
compare them directly with a printed guide.

## Dungeon Progression

Each overworld movement crosses one original screen. Each dungeon movement
crosses one original room edge. Locked doors and shutters come from the
background door graphics. Bomb walls come from the matching 16x16 bomb markers
drawn on both adjoining rooms in the labeled maps, and lettered stair passages
come from the First Quest route references.

| Level | Player levels | Overworld | Entry | Rooms | Boss | Goal |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| 1: The Eagle | 11-20 | `H5` | `30401` | `30400-30417` | `30413` | `30414` |
| 2: The Moon | 21-30 | `M5` | `30418` | `30418-30435` | `30435` | `30434` |
| 3: The Manji | 31-40 | `E1` | `30437` | `30436-30454` | `30449` | `30451` |
| 4: The Snake | 41-50 | `F4` | `30456` | `30455-30475` | `30470` | `30474` |
| 5: The Lizard | 51-55 | `L8` | `30476` | `30476-30499` | `30489` | `30493` |
| 6: The Dragon | 56-60 | `C6` | `30501` | `30500-30525` | `30519` | `30524` |
| 7: The Demon | 61-64 | `C4` | `30527` | `30526-30559` | `30546` | `30547` |
| 8: The Lion | 65-67 | `N2` | `30562` | `30560-30586` | `30574` | `30578` |
| 9: Death Mountain | 68-70 | `F8` | `30590` | `30587-30645` | `30607` | `30615` |

Dungeon 1 starts after the level 1-10 overworld opening. Equipment chests cover
every player level through 70. Bosses carry the top gear for their band, while
maps, cellars, and intermediate rooms source the rest. The Master Sword remains
fixed at level 58 as requested.

Death Mountain requires all eight Triforce shards before its bombed entrance
can be used. Ganon drops Golden Key `30243`; that key opens Zelda's room, which
contains the complete Triforce `30286` and return portal `30217`.

## Maps And Compasses

Every dungeon contains one generated map and compass:

| Level | Map object and room | Compass object and room |
| --- | --- | --- |
| 1 | `30480` in `30409` | `30489` in `30406` |
| 2 | `30481` in `30425` | `30490` in `30423` |
| 3 | `30482` in `30448` | `30491` in `30441` |
| 4 | `30483` in `30466` | `30492` in `30458` |
| 5 | `30484` in `30485` | `30493` in `30488` |
| 6 | `30485` in `30516` | `30494` in `30503` |
| 7 | `30486` in `30548` | `30495` in `30537` |
| 8 | `30487` in `30580` | `30496` in `30568` |
| 9 | `30488` in `30628` | `30497` in `30618` |

`read <map>` prints the dungeon silhouette and marks the entrance, map,
compass, item cellars, boss, and goal. `read <compass>` reports the first
general direction and approximate route distance to the boss. Routing stays
inside that dungeon's generated vnum range and understands stair passages.

Map values use opcode `90`; compass values use opcode `91`. Values 1-4 contain
the boss vnum, first room, last room, and dungeon level.

## Overworld Secrets And Services

The generated overworld includes the complete major First Quest service set:

- 14 secret rupee caves with their original 10, 30, or 100 rupee rewards
- 7 regular item shops and 5 hidden deluxe shops
- 7 potion shops, gated by Princess Zelda's Letter
- 9 one-time 20-rupee door-repair charges
- 5 money-making games using the `gamble` command
- 4 Power Bracelet warp halls with the original west, center, and east routes
- 5 overworld Heart Containers and 2 Fairy Fountains
- Wooden, White, and Master Sword caves, the Letter, and the Power Bracelet

The regular shops source bombs and the Blue Candle inside Hyrule, so early
secrets do not depend on equipment imported from another area. Shop inventory
uses the original item groupings and prices. Potion shops offer the 40-rupee
Life Potion and 68-rupee 2nd Potion only while the character carries the Letter.

Door-repair rooms charge at most 20 rupees on the first visit. A hidden,
non-droppable receipt records payment separately for each location and survives
normal player saves. The gambling rooms charge 10 rupees and choose among the
First Quest-style positive and negative outcomes.

Warp stones require the Power Bracelet. Their route permutations are:

| Hall | West | Center | East |
| --- | --- | --- | --- |
| `D6` | `J4` | `J1` | `N7` |
| `J4` | `J1` | `N7` | `D6` |
| `J1` | `N7` | `D6` | `J4` |
| `N7` | `D6` | `J4` | `J1` |

## Puzzle Commands

| Command | Requirement | First Quest use |
| --- | --- | --- |
| `burn <target>` | Blue or Red Candle | Bushes, shops, hearts, repairs, Level 8 |
| `bomb <target>` | Bomb satchel or bomb bag | Rock walls, caves, Dodongo, Level 9 |
| `play <instrument>` | Recorder, whistle, or ocarina | Level 7 entrance and Digdogger |
| `feed <guardian>` | Enemy bait | Hungry Goriya |
| `push <target>` | Context dependent | Blocks, Armos, sword grave, warp stones |
| `gamble` | 10 rupees in a money game | First Quest gambling caves |

Puzzle objects use `ITEM_MANIPULATION` type `31`. Generated overworld targets
use a zero destination plus dynamic-target flag `value[4] = 9`, allowing one
prototype to reveal the current room's exit. Bomb, burn, play, and feed use
opcodes 12, 11, 13, and 14 respectively.

Runtime rules add the behaviors the area format cannot express alone:

- Hyrule small keys are consumed; the Magical Key is reusable.
- Shutters open when aggressive room guardians are defeated.
- Dodongo takes bomb damage.
- Gohma requires a bow or Silver Arrow for the finishing hit.
- Ganon requires the Silver Arrow for the finishing hit.
- Like Likes can swallow equipped shields; Bubbles can disarm weapons.
- Wallmasters can return a player to that dungeon's entrance.
- Raft and Stepladder crossings verify the corresponding item.
- Warp stones verify the Power Bracelet.

## Regeneration

For normal work, regenerate from the checked-in manifest:

```bash
python scripts/build_hyrule_area.py
python -m unittest tests.test_hyrule_progression
```

The generator is idempotent. Running it twice must produce byte-identical area
files.

To rebuild the manifest from external reference assets, install Pillow and put
the labeled/background map pairs and sprite references under
`../zelda-reference`. Then run:

```bash
python scripts/extract_zelda_reference.py ../zelda-reference ../zelda-reference/extracted
python scripts/extract_zelda_entities.py ../zelda-reference/extracted/cells ../zelda-reference/sprites-complete ../zelda-reference/extracted/entities.json
python scripts/extract_zelda_doors.py ../zelda-reference ../zelda-reference/extracted/diagnostics.json ../zelda-reference/extracted
python scripts/build_hyrule_manifest.py --reference ../zelda-reference/extracted
python scripts/build_hyrule_area.py
```

Review extraction diagnostics and unmatched sprite composites before accepting
a rebuilt manifest. They are evidence for a human audit, not generated files to
commit.

## Validation

Run the focused test while editing Hyrule:

```bash
python -m unittest tests.test_hyrule_progression -v
```

Before publishing, run the complete repository suite:

```powershell
.\scripts\validate.ps1
```

The Hyrule tests verify:

- all 128 overworld screens and every canonical dungeon room
- reciprocal topology, non-overlapping ranges, and complete reachability
- all 56 marked bomb walls, including Death Mountain's exact 19 wall pairs
- exact reset counts for source-derived encounters
- locked-door solvability using keys found in each dungeon
- Death Mountain passages, encounters, Ganon key, and Triforce gate
- every level from 1 through 70 having sourced weapon or armor
- maps, compasses, shops, rupees, repairs, gambling, and warp routes
- teleport-only entry, no recall, and a path back from every Hyrule room
- area-generator idempotence

The full validator also performs clean and strict-warning C builds, boots the
engine in area-check mode, validates all area references, runs area health, and
executes the complete Python test suite.

## Fidelity Boundary

The canonical topology, room counts, cardinal adjacency, dungeon silhouettes,
door classes, encounter counts, major item locations, services, and route
permutations are data-derived. MUD combat is real-time rather than tile-based,
and one Zelda screen is represented by one text room rather than a pixel map.
Area resets make enemies and rewards replayable. These are intentional engine
adaptations; they do not alter the crossing count or progression route.
