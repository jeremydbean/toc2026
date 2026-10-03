# Hyrule: First Quest

## Status

Hyrule is a generated level 1-59 campaign based on the First Quest from the
original *Legend of Zelda*. It replaces the old ToC2 room layout while retaining
the useful Hyrule mobile and object catalog.

| Property | Value |
| --- | --- |
| Area file | `area/hyrule.are` |
| Reserved vnums | rooms and objects `30200-30799`; mobiles `30200-30345` and generated enemies `31000-32459` |
| Entry object | Hyrule arcade cabinet `30285` in Campus room `15068` |
| Arrival | Overworld screen `H1`, room `30200` |
| Exit model | Secret return tree, post-Ganon return light, and recall from the overworld |
| Recall | Blocked only inside the nine dungeons (`30400-30645`) |
| Level range | `1-59` |
| Canonical geometry | 128 overworld screens plus 246 dungeon rooms and cellars |
| Generated area size | 443 rooms and 1,497 reset records |

There is no walking exit from the main world into Hyrule. Players arrive by
entering the arcade cabinet, matching the intended "teleported into Zelda"
opening. They can leave through the burned secret tree at `E2` or the return
light in Zelda's room after Ganon.

## Sources Of Truth

Do not hand-edit generated rooms or resets in `area/hyrule.are`. The checked-in
source chain is:

1. `data/hyrule_first_quest.json` stores normalized screen, room, encounter,
   door, landmark, shop, secret, and progression data. Its encounters are what
   the NES screen or room shows, not what the MUD spawns (see Population).
2. `data/hyrule_room_prose.json` holds every room's name and description,
   written from the NES screen or dungeon room it stands for. Keys are the
   manifest coordinate for the overworld, `L<level>:<coordinate>` for dungeon
   rooms, `L<level>:cellar:<coordinate>` for block-stair cellars, and named
   `special` entries for caves, shops, and secrets. Descriptions are one
   paragraph; the generator wraps them at 75 columns and prefixes dungeon names
   with `Level N: `. A missing entry stops the build.
3. `data/hyrule_mob_prose.json` holds what the enemies and bosses look like:
   each enemy kind's room line and description (shared by every band of that
   kind), and each boss's room line and description, written from the NES
   game. A kind with no entry stops the build.
4. `scripts/build_hyrule_area.py` combines those with the retained area
   catalog and writes `area/hyrule.are`. It also owns every enemy record, the
   bosses' stat lines, the boss weapons, the Master Sword, the Triforce, the
   Heart Containers, and the enemy drops.
5. `tests/test_hyrule_progression.py` checks geometry, placement, progression,
   reachability, resets, services, and generation idempotence;
   `tests/test_hyrule_relic_powers_live.py` plays the worn powers in a running
   game.

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
| `B3` | `B6` | Hero's Grave (the Master Sword's, now empty) |
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
| 1: The Eagle | 2-8 | `H5` | `30401` | `30400-30417` | `30413` | `30414` |
| 2: The Moon | 8-14 | `M5` | `30418` | `30418-30435` | `30435` | `30434` |
| 3: The Manji | 14-20 | `E1` | `30437` | `30436-30454` | `30449` | `30451` |
| 4: The Snake | 20-27 | `F4` | `30456` | `30455-30475` | `30470` | `30474` |
| 5: The Lizard | 27-33 | `L8` | `30476` | `30476-30499` | `30489` | `30493` |
| 6: The Dragon | 33-40 | `C6` | `30501` | `30500-30525` | `30519` | `30524` |
| 7: The Demon | 40-46 | `C4` | `30527` | `30526-30559` | `30546` | `30547` |
| 8: The Lion | 46-52 | `N2` | `30562` | `30560-30586` | `30574` | `30578` |
| 9: Death Mountain | 53-59 | `F8` | `30590` | `30587-30645` | `30607` | `30615` |

The bands are `LEVEL_BANDS` in `scripts/build_hyrule_manifest.py`, copied
into each dungeon's `recommended_levels`. Each overworld screen's
`recommended_level` comes from `world_level()` there: an inverse-square-
distance average of every dungeon's band midpoint, with the start screen
anchored at 1. Standing on a dungeon's screen gives that dungeon's midpoint,
so the ground around Level 8 is graded for the high forties even though it is
six screens from the start. The manifest builder needs reference images that
are not committed, so when the bands change, apply `LEVEL_BANDS` and
`world_level()` to the checked-in JSON as well.

### The Order Of The Dungeons

The nine dungeons are done in order, and each one needs something only the
one before it gives. Every dungeon works the same way:

1. **Entering** it from outside needs the previous dungeon's Triforce piece.
2. **Inside**, the way into the guardian's chamber needs the previous
   dungeon's treasure.
3. **The guardian** drops its dungeon's key. The key opens the locked door
   into the room behind the guardian, and the locked chest in that room.
4. **The chest** holds this dungeon's Triforce piece and its treasure: the
   piece opens the next dungeon, and the treasure gets you through it.

Both gates are asked of the character moving, never of a door, so nobody can
hold the way open for anybody else. They are `hyrule_progress_gate` in
`src/act_move.c`, asked by `move_char` and by `do_enter` (portals), and they
pass if the character carries the item: in hand, worn, or one bag down. The
stash does not count. Staff pass by trust, and a pet or charmed follower is
asked about its master. Every dungeon room is `ROOM_NO_RECALL`, so gate,
summon, portal, astral walk, teleport, shift and earth travel cannot land
in one, and `goto` and `transfer` are staff commands.

| Level | To enter | Obstacle before the guardian (needs) | Guardian's chest | Why it is faithful |
| --- | --- | --- | --- | --- |
| 1: The Eagle | nothing | none | Piece 1 + the boomerang (`30232`) | The boomerang is the Eagle's: a Goriya drops it in the NES. The bow stays where the NES keeps it, until Level 5 needs it (below). |
| 2: The Moon | Piece 1 | Dodongo's door is held by a lever across a pit; a thrown boomerang trips it (the boomerang or the Magical Boomerang) | Piece 2 + the Magical Boomerang (`30410`) | The Magical Boomerang is the Moon's treasure. The NES boomerang fetches and strikes what you cannot reach. |
| 3: The Manji | Piece 2 | Manhandla's lever is across a chasm only the Magical Boomerang reaches | Piece 3 + the raft (`30411`) | The raft is the Manji's treasure, and the Magical Boomerang's whole point in the NES is its range. |
| 4: The Snake | Piece 3, and the raft to reach the island | Black water floods the hall before the Gleeok: the raft | Piece 4 + the stepladder (`30412`) | NES exactly: the raft carries you to Level 4's island, and the stepladder is the Snake's treasure. |
| 5: The Lizard | Piece 4 | A one-square moat across Digdogger's doorway: the stepladder | Piece 5 + the bow (`30222`) | NES exactly for the stepladder, which bridges one-square gaps. The bow moves here from Level 1, so it arrives just before the guardian it exists for. |
| 6: The Dragon | Piece 5 | Gohma's eye is armoured against everything but an arrow: the bow | Piece 6 + the Recorder (`30413`) | NES exactly: a bow and arrow beat Gohma, and Gohma still takes only an arrow's finishing blow. The Recorder moves here from Level 5, one dungeon later, so it is in hand for Level 7, where the NES uses it. |
| 7: The Demon | Piece 6, and the Recorder's song to drain the lake (as before) | Two Digdoggers block the way to the guardian; the Recorder shrinks them | Piece 7 + the Red Candle (`30414`) | NES exactly: the Recorder drains Level 7's lake and shrinks Digdogger, and the Red Candle is the Demon's treasure. |
| 8: The Lion | Piece 7, and a candle to burn the bush (as before) | The way to the guardian is utterly dark: the Red Candle | Piece 8 + the Magical Key (`30416`) | NES: the Red Candle lights dark rooms and burns Level 8's bush; the Magical Key is the Lion's treasure. |
| 9: Death Mountain | Piece 8 (and all eight pieces and a bomb at the door, as before) | The doors before Ganon's lair: the Magical Key | Great chest: piece 9, the Triforce of Power (`30408`), + the Master Sword (`30200`) | NES: the Magical Key opens every lock in the last dungeons. The Silver Arrow that finishes Ganon is in Death Mountain's own cellar, where the NES keeps it, before his lair; the Red Ring is in its other cellar. |

After Ganon, `COMBINE TRIFORCE` joins the nine pieces into the complete
Triforce (see below). The complete Triforce counts as every piece, so its
holder can walk back into any dungeon.

The Magical Rod (Level 6) and the Magic Book (Level 8) stay in their cellars
as loot the chain does not need; the cellars whose treasure moved to a chest
hold rupees instead.

**Nothing in the chain can be lost for good.** A guardian repops with a fresh
key at every area reset, and its chest relocks and refills at the same reset,
players or no players (`reset_area` makes an exception for Hyrule's chests,
since Hyrule is a single area and would otherwise refill nothing while anyone
was in it). So a character who dies, junks or sells a piece or a treasure
redoes the previous dungeon and has it again. Every treasure room also holds
its dungeon's way home -- the returning light, or Zelda's portal -- so being
locked in behind a door is not possible either.

The guardian's door is exit type 2 (pickproof) with a `D` reset of state 3,
magical like the golden door: its key opens it, and no pick, doorbash or random
trap gets round it. Small-key doors are type 2 with state 2. Neither may be
type 5, which `load_resets` resets as a trapped door; until 2026-10 every keyed
door in Hyrule was one.

**Pieces are NODROP; treasures are not.** A piece is the proof of having
done a dungeon, so it cannot be given, dropped, put in a container or sold:
otherwise one character could carry another through. A treasure only gets
you past an obstacle inside a dungeon you already earned your way into, so
trading one skips nothing, and a lost one comes back from the chest. Keys,
pieces and treasures carry no rot-death, inventory or meltdrop flag, and a
guardian's key does not crumble in the corpse the way an ordinary key does.
A key is not saved when you quit, like every key in the game; the guardian
has another after the next reset.

**Entry levels.** There is no minimum level at any door. The gates already
make the order strict, and each dungeon's band is a warning in its own
right: its guardian is sized to beat a lone character at the top of the band.
A floor (say, the band's bottom less two) would stop a level 10 trailing a
level 50 friend into Death Mountain for the experience, but it would also
stop a lower member of a group that has earned every piece together. It is
easy to add to `hyrule_progress_gate`; it is the owner's call.

### Item Levels

Every item a player can get sits at or below the band of the place it is first
found, and its stats are rescaled to that level (`ITEM_LEVELS`,
`gear_item_levels()` and `relevel_catalog_items()` in the generator):

- Each dungeon's map-room chest (`GEAR_STAGES`) holds gear spread across the
  levels its band adds, so with the Heart Guards every level from 1 to 59 has
  sourced gear and nothing sourced is above 59. Armour follows the catalog's own
  curve (an armour point per four levels); chest weapons average about 0.7 of
  their level.
- Each boss's Heart Guard is at the top of its dungeon's band (Ganon's crown at
  59).
- Caves, cellars, and quest items take the band of the screen or dungeon they
  open from: the Wooden Sword is level 1 (2d4), the small boomerang 4, the
  short bow 6, the Magical Boomerang 12, the raft 16, the stepladder 22, the
  White Sword, Power Bracelet, and Recorder 30, the Magical Rod 38, the Red
  Candle 42, the Magic Book and Magical Key 48, and each Triforce shard the
  bottom of its dungeon's band.
- A shop item takes the lowest band it is sold in.
- The Master Sword is level 58 and lies in Ganon's great chest, inside Death
  Mountain's band. It used to lie in the B6 graveyard, a band 6 screen, as the
  one item above its band; the grave is still there and holds nothing now.
- Each guardian's key and chest are at the bottom of its dungeon's band, and
  the treasures in the chests are all at or below it (the bow, level 6, sits in
  Level 5's chest; the Recorder, level 30, in Level 6's).
- The Silver Arrow stays at level 54 (`HYRULE_SILVER_ARROW_LEVEL`), inside
  Death Mountain's band; the relics stay at 54-58, and the Red Ring of Hyrule
  (58) lies in Death Mountain's Red Ring Cellar.

`tests/test_hyrule_progression.py` walks every room, mobile, and container
source and fails on an item above its source's band, and on any sourced weapon
that matches its band's boss weapon.

### Hyrule's Bystanders

The old men, the door-repair man, the gambler, Princess Zelda, and the fountain
fairies are level 10-70 and fight nobody. `is_hyrule_bystander()` in
`src/fight.c` makes them safe from attacks and spells alike, so they cannot be
farmed for experience. The merchants were already safe as shopkeepers.

### Enemies

Each NES enemy kind (`ENEMY_TYPES` in the generator) is generated once per
band it appears in, at vnum `31000 + code * 10 + (band - 1)`. A dungeon room
uses its dungeon's band; an overworld screen uses the band its own level falls
in. Within a band a kind's level is set by its rank -- keese and gels at the
bottom, darknuts, lynels, and lanmolas at the top -- and its hit points and
damage by its kind against an ordinary mobile of that level elsewhere in the
world (`HIT_POINT_CURVE`, `DAMAGE_CURVE`, read off the other area files). All
generated enemies are sentinel and aggressive: an NES enemy holds its screen.

The code is the offset of the single catalog record the kind used to be
(`30215` -> 15 for the like like), and `hyrule_enemy_kind()` in `src/fight.c`
maps any band back to it. That is how the like like's shield-eating, the
bubble's disarm, and the wallmaster's drag back to the entrance work at every
band. Change a code and you change which effect a kind has.

### Population

The manifest records the NES cast, and some NES rooms are crowded: eight
keese, six like likes, a wall of wizzrobes. A dungeon room keeps every kind it
had but fewer of each -- one for up to three, two for four to six, three for
seven or more, and one of each blade trap, patra, dodongo, or digdogger -- and
no more than three in all unless it has more than three kinds. Death Mountain
went from 254 dungeon spawns to 114, and all nine dungeons from 559 to 308.
The overworld already asked for at most two of anything and is unchanged.

### Bosses And Their Weapons

Bosses keep their catalog records and achievements; their stat lines are
generated (`BOSS_STATS`), and each has an NES attack (`BOSS_VOLLEYS`, see
Guardian Fights below). Each carries its Heart Guard, a weapon
(`BOSS_WEAPONS`) and its dungeon's key through `G` resets.

| Level | Boss | Boss level | Hit points | Weapon | Weapon level | Avg + damroll | Best existing |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| 1 | Aquamentus | 10 | 820 | Aquamentus horn-spear 3d6, +2 hit +1 dam | 8 | 11.5 | 10.0, the large mace |
| 2 | Dodongo | 16 | 2,200 | Dodongo tail-club 4d8, +2/+2 | 14 | 20.0 | 17.0, an icy dagger |
| 3 | Manhandla | 23 | 3,400 | Manhandla bloom-whip 6d9, +2/+2 | 20 | 32.0 | 28.0, a barbed whip |
| 4 | Gleeok | 30 | 6,000 | Gleeok twin-fang glaive 7d8, +3/+2 | 27 | 33.5 | 28.0, a barbed whip |
| 5 | Digdogger | 36 | 16,800 | Digdogger urchin flail 7d9, +3/+2 | 33 | 37.0 | 32.0, Hyrule's White Sword (level 30) |
| 6 | Gohma | 43 | 20,000 | Gohma eye-lance 7d10, +3/+1 | 40 | 39.5 | 33.5, a two-handed sword |
| 7 | ancient Aquamentus | 49 | 30,000 | Demon's dragonbone sword 9d9, +4/+4 | 46 | 49.0 | 42.0, A Glaive-Guisarme |
| 8 | ashen Gleeok | 55 | 33,000 | Lion's four-crowned axe 10d9, +9/+6 | 52 | 56.0 | 49.0, a flaming Light Saber |
| 9 | Ganon | 64 | 36,000 | Trident of Ganon 11d10, +9/+3 | 59 | 63.5 | 54.0, the Power of the world |

"Best existing" is the best weapon a character of that level could otherwise
carry: every mobile-carried weapon in the world at or below the weapon's level,
scored as `value[1] * (value[2] + 1) / 2` plus damroll with the dashboard
parser, and Hyrule's own re-levelled weapons where they beat it. Each
boss weapon sits 10-20% above that mark, and the test holds it there.

The first eight bosses also drop a Heart Container, as in the NES: a hold-slot
crystal at the top of the band giving twice that level in hit points, and from
the Lizard (Level 5) on a point of constitution. Ganon leaves none. Boss text
-- room line and description -- comes from `data/hyrule_mob_prose.json`, and
Level 1's guardian is plain "Aquamentus" now, the one-horned NES dragon rather
than the catalog's "Three-headed Aquamentus".

### The Master Sword

The Master Sword (`30200`, level 58) lies in Ganon's great chest in Zelda's
chamber, beside the ninth Triforce piece; the Golden Key Ganon drops opens both
the chamber and the chest. It is the best weapon a mortal can get
anywhere in the game, measured the boss-weapon way against every weapon at or
below level 59 that a mortal can get -- from a mobile, a room, a container, a
shop, or a quest reward:

| Weapon | Level | Dice | Hit/Dam | Score |
| --- | ---: | --- | --- | ---: |
| The Master Sword (now) | 58 | 13d9 | +5/+5 | 70.0 |
| Trident of Ganon | 59 | 11d10 | +9/+3 | 63.5 |
| The Master Sword (before) | 58 | 13d8 | +3/+4 | 62.5 |
| Lion's four-crowned axe | 52 | 10d9 | +9/+6 | 56.0 |
| The Power of the world (crypt.are), best outside Hyrule | 54 | 8d10 | +9/+10 | 54.0 |

Its weapon flags are sharp and vorpal (it was flaming and sharp; Ganon resists
magic, and a flaming blade's fire is magic to him). Its unique gift is haste
while wielded: an `F` record on the object, `A 0 0 V`. `load_objects` reads
ROM 2.4's `F` records now (`F` then `A <location> <modifier> <bits>`); only
`A`, the affected_by word, is understood. `equip_char` sets the bit and
`unequip_char` lifts it and then puts back whatever a spell, the race or other
worn gear still grants, so a hasted character who takes the sword off stays
hasted. Slow and dispel magic ask `equipment_grants_affect()` before stripping
haste or sanctuary by hand, so worn powers last exactly as long as they are
worn. IDENTIFY lists them as "Grants haste while worn."

### Ganon's Fight

Ganon is meant to need a group: a solo level 59 with maximum stats should very
likely lose, and three or four should win. The numbers:

- **Level 64, 36,000 hit points, armour -40 (-400 in game), average blow 350
  (5d55+210), sanctuary and haste as before.** Level 64 parries and dodges a
  level 59 35% of the time each (`min(30, level) + level - 59`), so about four
  in ten blows land. The armour shaves about 80 off each ordinary blow; the
  Silver Arrow's tenth of his health is taken after armour, so it is untouched.
- **`spec_ganon` (`src/special.c`) replaces the necromancer's spell list.**
  Every mobile pulse (four seconds) he blinks to another spot in the dark and
  throws two fireballs of 1,400-1,900, each at a random player in the fight:
  anyone fighting him or grouped with someone who is. A fireball is a spell
  blow, so parry, dodge and shield block do nothing; sanctuary halves it, the
  Red Ring takes a fifth and the Mirror Shield three twentieths. His melee is
  ordinary, and a hero with every defence learned turns most of it aside --
  the fireballs are the fight.
- **Left alone, he heals.** Out of a fight he recovers a tenth of his health
  every pulse, as the NES Ganon is whole again when you come back, so the
  Silver Arrow's tenths cannot be banked by running out to rest. A collapsed
  Ganon (one hit point, `AFF2_NO_RECOVER`) does not heal: the finishing shot
  still waits.

The silver-arrow rule is unchanged, and it is what fixes the length of the
fight: ten landed Silver Arrow blows bring him to one hit point whatever his
hit points are. A level 59 with haste and second and third attack swings about
3.75 times a round, lands about 1.5 of those through his defences, and so needs
about seven rounds.

The fireballs were first sized against a hero of 4,000 hit points. Against the
player model fitted to the live player files (Guardian Fights, below) that was
too much for an ordinary group, so they came down to 1,400-1,900 and his hit
points went up to 36,000 to stay above the ashen Gleeok's. With every level 59
holding sanctuary, the arrow-holder the Red Ring:

| Party | Wins |
| --- | ---: |
| Solo, Silver Arrow, a typical 59 | 0% |
| Solo, Silver Arrow, 4,000 hit points | 10% |
| Three: arrow-tank, cleric, a second arrow | 90% |
| Three: arrow-tank, cleric, damage | 26% |
| Four: arrow-tank, cleric, a second arrow, damage | 98% |

A group wants two Silver Arrows: the arrow's tenth of his health is what ends
the fight, and the second arrow halves its length. Both cellars refill at each
reset, so a group can arm itself over two visits.

Death Mountain requires all eight Triforce shards before its bombed entrance
can be used. Ganon drops Golden Key `30243`, Death Mountain's guardian key;
it opens Zelda's room and Ganon's great chest in it (`30648`), which holds the
Triforce of Power `30408` and the Master Sword. The room's portal `30217`
leads home.

### Guardian Fights

Every guardian is sized so that **a lone character at the top of the band
usually loses, one six levels above usually wins, and a group of three at the
band usually wins.** The sizes come from a Monte Carlo of `fight.c`'s
formulas: `one_hit`'s to-hit and damage, NPC parry and dodge
(`min(30, level) + level - victim`), the player's parry, dodge and shield
block, sanctuary, armour's damage reduction and the mobile's damroll scaled by
its skill. The player model is fitted to the live player files -- the 80th
percentile of each four-level bucket, "geared for the band":

| | Formula | Level 8 | Level 33 | Level 52 |
| --- | --- | ---: | ---: | ---: |
| Hit points | `8 + 10L + 0.3L^2` | 107 | 665 | 1,339 |
| Hitroll | `0.02L^2 + 0.1L + 5` | 7 | 30 | 64 |
| Damroll | `0.012L^2 + 0.95L - 6` | 2 | 38 | 76 |
| Armour | `60 - 4.5L` | 24 | -88 | -174 |

Second attack from level 10, third from 25, haste from 30, enhanced damage
from 20, sanctuary alone from 30 or with a cleric from 15, a weapon averaging
`0.8L + 2`, and damage scaled by 2.5 to match the training yard's board (a
level 50 warrior there lands about 650 a round). The group is a tank, a cleric
who heals the lowest each round, and a damage dealer.

Each guardian has the attack the NES gave it, in `spec_hyrule_guardian`
(`src/special.c`): every four seconds a volley of spell blows at random members
of the fight that no parry stops. Manhandla spits from however many of its four
heads are left, Gleeok's heads fly loose below half its health, and Digdogger
splits in two below half, each half rolling for half. A patra, Death Mountain's
orbiting eye, lashes everyone fighting it each pulse (`spec_hyrule_patra`).

| Level | Guardian | Level | Hit points | Blow | Volley a pulse | Solo, top of band | Solo, six above | Three, top of band | Three, mid-band |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Aquamentus | 10 | 820 | 10 | 3 fireballs 4-6 | 0% (8) | 88% (14) | 100% | 100% |
| 2 | Dodongo | 16 | 2,200 | 19 | a charge 22-31 | 0% (14) | 87% (20) | 100% | 100% |
| 3 | Manhandla | 23 | 3,400 | 30 | 4 heads 9-13 | 0% (20) | 88% (26) | 100% | 100% |
| 4 | Gleeok | 30 | 6,000 | 64 | 2 heads 39-55 | 0% (27) | 90% (33) | 100% | 100% |
| 5 | Digdogger | 36 | 16,800 | 40 | a roll 48-67 | 0% (33) | 87% (39) | 100% | 100% |
| 6 | Gohma | 43 | 20,000 | 27 | the eye 32-45 | 0% (40) | 89% (46) | 100% | 100% |
| 7 | ancient Aquamentus | 49 | 30,000 | 66 | 3 fireballs 26-36 | 0% (46) | 85% (52) | 100% | 100% |
| 8 | ashen Gleeok | 55 | 33,000 | 80 | 4 heads 24-34 | 0% (52) | 88% (58) | 100% | 100% |

Each was set as strong as the brief allows: its hit points bisected to where
the character six levels above wins about seven times in eight. The model is
kind to groups -- a cleric's sanctuary on everybody and a heal every round --
so a real group will find these harder than the last two columns say. Gohma
keeps her catalog sanctuary and haste, Aquamentus his sanctuary and Dodongo its
haste, which is why Gohma's blow is light. The breath weapons four of them had
went: dragon breath hits for an eighth of the breather's own hit points, which
at these sizes would be a thousand a breath.

### The Complete Triforce

Nobody finds the complete Triforce (`30286`, level 58): it is made.
`COMBINE TRIFORCE` -- the COMBINE command's one recipe, `combine_recipes` in
`src/act_info.c` -- takes the nine pieces from the inventory, one from each
guardian's chest, and gives the Triforce in their place; with fewer it says
how many you carry. `COMBINE` alone is still the inventory display toggle it
always was. The Triforce counts as every piece at every dungeon door.

The complete Triforce is an `ITEM_LIGHT`, so WEAR puts it
in the light slot. Its `value[2]` is 999, which `create_object` turns into the
-1 that never burns down (the file cannot say -1: `fread_flag` reads no minus
sign). Worn there it gives **the sight of a level 59 character with HOLYLIGHT
on**, and no more:

- `triforce_sight(ch)` in `src/handler.c` is the one test: a player, wearing
  object `OBJ_VNUM_HYRULE_TRIFORCE` in `WEAR_LIGHT`. Every place holylight
  grants sight asks it beside `PLR_HOLYLIGHT`: `can_see`, `can_see_obj`, the
  online roster, `check_blind`, and the dark-room checks in LOOK, READ and SCAN.
- `sight_trust(ch)` is `get_trust` raised to `TRIFORCE_SIGHT_LEVEL` (59) for
  the wearer, and is what `can_see`, the roster and the room listing compare
  against a wizinvis or cloak level. A wearer sees wizinvis 59 and nothing
  above it, exactly as a level 59 with holylight would. Permissions still ask
  `get_trust`.
- Mobiles never get it, so the shadowmeld rule holds: the meld check stays
  above the `IS_NPC(ch) && IS_IMMORTAL(ch)` shortcut, and against players a
  wearer finds a melded character as holylight does.

### Ganon Relics

Ganon's corpse contains his crown, his trident and the Golden Key, plus
exactly one random relic from this table. All four random rewards
are usable below the immortal level boundary:

| Relic | Vnum | Level | Slot | Unique effect |
| --- | ---: | ---: | --- | --- |
| Hero's Tunic | `30577` | 54 | Body | Restores up to 5% maximum hp after the wearer personally kills an NPC, capped at twice the victim's level |
| Blue Ring of Hyrule | `30578` | 54 | Finger | Reduces all incoming damage by 10% |
| Pegasus Boots | `30581` | 55 | Feet | Reduces movement spent traveling on foot by 25%, with a minimum cost of one |
| Mirror Shield | `30580` | 56 | Shield | Reduces nonphysical damage by 15% |

The **Red Ring of Hyrule** (`30579`, level 58, finger) used to be a fifth entry.
It is found now, not rolled for: it lies in Death Mountain's Red Ring Cellar
(`30645`), where the NES keeps it, in place of the catalog's plain red ring
(`30261`, still in the catalog for anyone who holds one). It reduces all
incoming damage by 20%, and it gives permanent sanctuary while worn through an
`F` record (`A 0 0 H`), applied and lifted like the Master Sword's haste.

Blue and Red Ring wards use the strongest single value; wearing two does not
stack their percentage reduction. The Mirror Shield is a separate ward and can
combine with one Ring. Pegasus Boots do not reduce a mount's movement cost.
The advanced `compare` model includes every relic passive and lists active
relic effects in its projected loadouts; it already reads object affect bits,
so it counts the sword's haste and the ring's sanctuary as well.

### What Enemies Drop

Ordinary enemies drop at random, rolled in `make_corpse` (`hyrule_enemy_drop()`
in `src/fight.c`), in the NES's spirit. A blade trap or a falling boulder
leaves nothing.

| Roll | Drop |
| ---: | --- |
| 15% | Rupees (gold coins): 1, 1, 2, 3, 5, 8, 12, 20, 30 by band |
| 5% | Five times that, the NES's blue rupee |
| 12% | A recovery heart: a potion of cure light (bands 1-2), cure serious (3-4), cure critical (5-6), heal (7-8), heal and cure critical (9) |
| 3% | A bottled fairy: two cure serious, two cure critical, heal and cure critical, two heals, then three heals |
| 1% | A clock-flask: a potion of haste, the clock's "everything stops but you" |
| 64% | Nothing |

The heart, fairy and clock are one potion per band at
`OBJ_VNUM_HYRULE_HEART_FIRST` (`30600`), `_FAIRY_FIRST` (`30610`) and
`_CLOCK_FIRST` (`30620`) plus band - 1, at the bottom of the band to drink and
cast at its top. The rupee drops start at the NES's single rupee and stay well
under the coin an ordinary mobile of the band carries; at band 1 a rupee is
worth far more than a level 5 mobile's silver, which is what keeps Hyrule's
own rupee prices -- a 20-rupee bomb bag -- about forty kills away. Bombs are
not dropped: the bomb bag is a tool BOMB never uses up, so a second one is
worth nothing. These potions have no reset source, so the area health check
counts them under `object-has-no-source`, like the relics before them.

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

## Hyrule Achievements

The permanent achievement catalog tracks arrival at screen `H1`, discovery of
all nine dungeon entrances, all maps and compasses, all eight Triforce shards,
the Master Sword, the Silver Arrow, the complete Triforce, each principal
dungeon boss, Ganon, and reaching Princess Zelda. Finishing all nine boss
achievements awards the `Hero of Hyrule` meta achievement.

Boss credit is shared with grouped player characters present in the boss room.
The final hit still controls ordinary lifetime-kill credit, but healers and
support characters receive the dungeon achievement. Collection bits remain
earned after an item leaves the inventory. See [Achievement System](achievements.md)
for command syntax, migration rules, and save behavior.

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
- Ganon can be wounded by ordinary weapons, spells, poison, and lingering
  damage, but those effects and normal weapon attacks cannot kill him. Against
  Ganon only, normal Silver Arrow strikes use full weapon mastery and deal at
  least 10% of his maximum health after defenses. When protected from lethal
  damage, Ganon remains at one hit point, becomes stunned, and cannot recover.
  Combat immediately ends for everyone targeting him and his room-list
  appearance turns bright red. A level 54 or higher character must keep the
  Silver Arrow wielded and use `shoot ganon` in the same room. This dedicated
  finishing shot always lands, requires no Archery skill, and does not consume
  the Arrow. `Look ganon` repeats that instruction. Immortal `slay` remains an
  administrative override.
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
- reset counts derived from the NES encounters by the population rule, with
  every kind kept and no room crowded
- level bands that climb from Level 1 to 59 without gaps, and enemies statted
  inside the band they stand in
- each boss out-levelling its band and outlasting the one before, and carrying
  a weapon 10-20% better than the best existing one at that level, and the
  first eight a Heart Container at the top of their band
- the Master Sword carried by Ganon and beating every weapon a mortal can get
  anywhere in the world at level 59 or below, with haste as an `F` record
- the Red Ring in Death Mountain's cellar with sanctuary, and the Triforce a
  light whose sight is wired into every holylight check
- Ganon's level, armour, hit points and `spec_ganon`, and the enemy drop
  potions present for every band at the vnums `src/merc.h` names
- every dungeon's key, magical door and locked chest, with the piece and the
  treasure inside and nowhere else; the gate table forming one chain from 1 to
  9 out of those chests; every guardian's volley matching `BOSS_VOLLEYS`; and
  COMBINE's recipe being exactly the nine pieces
- in a running game (`tests/test_hyrule_dungeon_chain_live.py`): the Eagle's
  key, door, chest and prize; a refusal at Level 2's entrance and its
  guardian's chamber, passing once the item is carried, and staff passing
  without it; and COMBINE TRIFORCE from eight pieces (refused) and nine
- room names free of grid labels, `Level N:` naming confined to the dungeons,
  and descriptions that fit a terminal and do not list occupants
- live-population reset caps, including a single Ganon across empty-area resets
- locked-door solvability using keys found in each dungeon
- Death Mountain passages, encounters, Ganon key, and Triforce gate
- every level from 1 through 59 having sourced weapon or armor, none above 59,
  and every item at or below the band it is found in
- maps, compasses, shops, rupees, repairs, gambling, and warp routes
- teleport-only entry, recall blocked only in the dungeons, and a path back
  from every Hyrule room
- area-generator idempotence

The full validator also performs clean and strict-warning C builds, boots the
engine in area-check mode, validates all area references, runs area health, and
executes the complete Python test suite.

## Fidelity Boundary

The canonical topology, room counts, cardinal adjacency, dungeon silhouettes,
door classes, encounter kinds, major item locations, services, and route
permutations are data-derived. MUD combat is real-time rather than tile-based,
and one Zelda screen is represented by one text room rather than a pixel map.
Area resets make enemies and rewards replayable, and crowded rooms are thinned
(see Population). These are intentional engine adaptations; they do not alter
the crossing count or progression route.

The room prose was written from the NES screens and rooms with the manifest's
facts in hand -- terrain read off each screen's enemies, doors, stairs, block
cellars, and landmarks. It is approximate by design: the room shapes and old
men's hints are paraphrased from the game, not transcribed. An old man's hint
is written into his room as words carved or scratched there, so the room
describes a place rather than an occupant.

The October 2026 rewrite of every room, enemy and boss description drew on
the sources that would load. Walkthrough sites mostly refuse automated
readers, so this is a record of what was actually used:

| Source | Result |
| --- | --- |
| legendsoflocalization.com, First Quest text comparison | Loaded; the NES wording of every old man, cave and shop line and which dungeon each hint belongs to |
| zeldauniverse.net walkthrough, all nine levels, shops, heart containers | Loaded; room-by-room detail (its Level 6 and 8 boss notes were muddled and not used) |
| zeldadungeon.net walkthrough | Index only; every level page 403 |
| nesmaps.com | Map pages load but carry no text; one level page is a bot check |
| Wikipedia | General summary only |
| strategywiki.org, gamefaqs.gamespot.com, zeldawiki.wiki, neoseeker | 403, raw MediaWiki variants included |
| zelda.fandom.com and other Fandom wikis | 402 |
| web.archive.org, ign.com | Refused by the fetch tool |

What none of them covered was written from knowledge of the game.

## Related Documentation

- [Player Guide](player-guide.md)
- [Player Command Reference](player-command-reference.md)
- [Area Building Guide](area-building-guide.md)
- [Validation And Area Health](validation-and-area-health.md)
- [Developer Guide](developer-guide.md)
