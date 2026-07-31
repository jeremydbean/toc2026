# ToC MUD Area Building Guide

**Comprehensive reference for creating `.are` files for the ToC (Times of Chaos) MUD.**  
This document covers every section, every flag, every option, and every value used in area files.
Prefer this document over the old HTML wiki files, which contain the same information in a harder-to-read format.

---

## Table of Contents

1. [Overview & File Structure](#overview--file-structure)
2. [Vnum Conventions & Naming](#vnum-conventions--naming)
3. [#AREA Section](#area-section)
4. [#HELPS Section](#helps-section)
5. [#MOBILES Section](#mobiles-section)
   - [Mobile Format](#mobile-format)
   - [ACT Flags](#act-flags)
   - [AFF (Affected By) Flags](#aff-affected-by-flags)
   - [OFF (Offense) Flags](#off-offense-flags)
   - [IMM (Immunity) Flags](#imm-immunity-flags)
   - [RES (Resistance) Flags](#res-resistance-flags)
   - [VULN (Vulnerability) Flags](#vuln-vulnerability-flags)
   - [FORM Flags](#form-flags)
   - [PARTS Flags](#parts-flags)
   - [Position Values](#position-values)
   - [Sex Values](#sex-values)
   - [Races](#races)
   - [Size Values](#size-values)
   - [Damage / Attack Types](#damage--attack-types)
   - [HP & Damage Reference Chart](#hp--damage-reference-chart)
6. [#OBJECTS Section](#objects-section)
   - [Object Format](#object-format)
   - [Object Types](#object-types)
   - [Object Flags (ITEM_FLAGS)](#object-flags-item_flags)
   - [Item Flags 2 (ITEM_FLAGS2)](#item-flags-2-item_flags2)
   - [Wear Flags](#wear-flags)
   - [Weapon Class](#weapon-class)
   - [Weapon Types](#weapon-types)
   - [Apply Types](#apply-types)
   - [Values by Object Type](#values-by-object-type)
   - [Container Flags](#container-flags)
   - [Liquid Values](#liquid-values)
   - [Object Condition](#object-condition)
   - [Item Wear Message (T flag)](#item-wear-message-t-flag)
   - [Materials](#materials)
7. [#ROOMS Section](#rooms-section)
   - [Room Format](#room-format)
   - [Room Flags](#room-flags)
   - [Sector Types](#sector-types)
   - [Exit Directions](#exit-directions)
   - [Door Type Values](#door-type-values)
   - [ROOM_AFF_BY Details](#room_aff_by-details)
8. [#RESETS Section](#resets-section)
   - [Reset Commands](#reset-commands)
   - [Wear Location Values (E command)](#wear-location-values-e-command)
   - [Door State Values (D command)](#door-state-values-d-command)
9. [#SHOPS Section](#shops-section)
   - [Shop Format](#shop-format)
   - [Item Types for Shops](#item-types-for-shops)
10. [#SPECIALS Section](#specials-section)
    - [Specials Format](#specials-format)
    - [Available Spec-Functions](#available-spec-functions)
11. [#$ End Marker](#-end-marker)
12. [Spell Slot Reference](#spell-slot-reference)
13. [Complete Area Template](#complete-area-template)
14. [Design & Balance Guidelines](#design--balance-guidelines)

---

## Overview & File Structure

An area file (`.are`) is a plain-text file that defines all the content in one area of the game. All `.are` files must be listed in `area/area.lst` for the game to load them.

### Section Order (mandatory)

Every area file must have sections in this exact order:

```
#AREA   { level range } Author   Area Name~
#HELPS
  ... (optional help entries)
0$~
#MOBILES
  ... (mob definitions)
#0
#OBJECTS
  ... (object definitions)
#0
#ROOMS
  ... (room definitions)
#0
#RESETS
  ... (reset commands)
S
#SHOPS
  ... (shop definitions)
0
#SPECIALS
  ... (special function assignments)
#$
```

Rules:
- Every **string field** ends with a tilde `~` on the same line or on its own line.
- Every **section** ends with its designated terminator (`#0`, `S`, `0`, or `#$`).
- The `#$` on the last line marks the end of the entire area file.
- Vnums in `.are` files use the **two-letter prefix** assigned to your area (e.g., `QQ` for Dresden, `AC` for Acult). Every `#VNUM` is written as `#QQ00`, `#QQ01`, etc.
- Lines starting with `*` in `#RESETS` are comments and are ignored.

### Encoding

All `.are` files use **Latin-1 (ISO-8859-1)** encoding. Do not save as UTF-8.

---

## Vnum Conventions & Naming

Each area is assigned a **two-letter prefix** (e.g., `QQ`, `AC`, `DR`). Vnums within an area follow the convention:
- `QQ00`–`QQ99` or `QQ00`–`QQ999` depending on area size.
- Rooms, mobs, and objects share the same vnum namespace within their respective sections.
- Keep mobs, objects, and rooms in logically grouped vnum blocks (e.g., QQ00–QQ19 rooms, QQ20–QQ39 mobs, QQ40–QQ79 objects).

---

## #AREA Section

```
#AREA   { min_level max_level } Author   Area Name~
```

**Fields:**
- `{ min_level max_level }` — Suggested level range for players (e.g., `{ 5 15 }`). Use `ALL` or `{ 0 100 }` for a universal area.
- `Author` — Your immortal name (no spaces; use underscores if needed).
- `Area Name~` — The full area name as players see it, followed by a tilde.

**Example:**
```
#AREA   { 10 25 } Drakk   City of Dresden~
```

---

## #HELPS Section

Optional. Used to add help entries accessible via the `help` command.

```
#HELPS
<level> <keywords>~
<help text>
~

0 $~
```

**Fields:**
- `level` — Minimum character level to read this help. Negative level hides keywords (useful for opening screens).
- `keywords~` — Space-separated keywords that trigger this help entry.
- Text ends with `~` on its own line.
- Section ends with `0 $~`.

**Example:**
```
#HELPS
-1 Dresden~
Dresden, City of Adventure! Welcome to our city.
~

0 $~
```

---

## #MOBILES Section

### Mobile Format

Each mobile entry follows this exact structure:

```
#VNUM
keywords~
Short description (shown next to name in room)~
Long description (seen when looking at room).
~
Look-at description (seen when typing 'look <mob>').
~
race~
ACT_FLAGS AFF_FLAGS ALIGNMENT S
level hitroll HitDice ManaDice DamDice dam_type
ac_pierce ac_bash ac_slash ac_exotic
OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS
start_pos default_pos sex gold
form parts SIZE material
```

**Field-by-field breakdown:**

| Field | Description |
|---|---|
| `#VNUM` | The mob's unique virtual number (e.g., `#QQ10`) |
| `keywords~` | Space-separated words players type to interact with this mob |
| `Short description~` | What shows in "XXX is standing here." — begins lowercase |
| `Long description~` | Multi-line text shown in room description. Ends with `~` alone on a line |
| `Look-at description~` | Text shown when a player specifically `look`s at the mob |
| `race~` | Mob's race string (see Races table below) |
| `ACT_FLAGS` | Letter-flag bitmask (see ACT Flags table) |
| `AFF_FLAGS` | Letter-flag bitmask (see AFF Flags table) |
| `ALIGNMENT` | Integer from -1000 (evil) to +1000 (good). 0 = neutral. |
| `S` | Literal letter `S` — always required at end of this line |
| `level` | Mob's level (1–60+) |
| `hitroll` | Bonus to hit rolls (typically 0–30) |
| `HitDice` | HP formula: `NdM+X` (e.g., `5d10+550`) |
| `ManaDice` | Mana formula: `NdM+X` (e.g., `10d20+100`) |
| `DamDice` | Damage per hit: `NdM+X` (e.g., `2d10+7`) |
| `dam_type` | Bare-hand attack type (integer; see Damage Types table) |
| `ac_pierce` | Armor class vs pierce attacks (lower = better; 0 to -30) |
| `ac_bash` | Armor class vs bash attacks |
| `ac_slash` | Armor class vs slash attacks |
| `ac_exotic` | Armor class vs exotic/magic attacks |
| `OFF_FLAGS` | Letter-flag bitmask: offensive capabilities |
| `IMM_FLAGS` | Letter-flag bitmask: immunities |
| `RES_FLAGS` | Letter-flag bitmask: resistances (takes half damage) |
| `VULN_FLAGS` | Letter-flag bitmask: vulnerabilities (takes double damage) |
| `start_pos` | Position when first loaded (integer; see Positions) |
| `default_pos` | Position it returns to after combat (integer; see Positions) |
| `sex` | 0=neuter, 1=male, 2=female |
| `gold` | Gold carried by mob |
| `form` | Body form flags (letters; see FORM Flags; usually `0`) |
| `parts` | Body parts flags (letters; see PARTS Flags; usually `0`) |
| `SIZE` | One letter: T/S/M/L/H/G (see Sizes) |
| `material` | Material string or `0` for default |

**Example mob:**
```
#QQ10
orc warrior~
an orc warrior~
An orc warrior stands here, weapon drawn.
~
This stocky warrior sports battle scars and a menacing scowl.
~
orc~
ABFG DF -350 S
15 3 3d9+208 10d10+100 2d6+3 5
-2 -2 -2 0
CFIKL AB 0 0
8 8 1 50
MH ABC M steel
```

---

### Flag Encoding

Flags use **letters as bit positions**: `A`=bit0, `B`=bit1, ..., `Z`=bit25.
To combine flags, list the letters with no separator: `ABF` = bits 0+1+5.

When a flag field exceeds 26 bits, use the extension mechanism: include `Z` in the current field to signal that a second set follows on the next token. For example:
- ACT FLAGS: include `Z` in the ACT_FLAGS field → next token is ACT_FLAGS2 letters
- AFF FLAGS: include `Z` in AFF_FLAGS → next token is AFF_FLAGS2 letters

---

### ACT Flags

First field on the "ACT_FLAGS AFF_FLAGS ALIGNMENT S" line.

| Flag | Letter | Description |
|---|---|---|
| ACT_IS_NPC | A | Automatically set for all mobs — **always include A** |
| ACT_SENTINEL | B | Mob stays in its room (does not wander) |
| ACT_SCAVENGER | C | Mob picks up objects from the ground |
| ACT_IS_HEALER | D | Mob is a healer (with spec_cast_adept) |
| ACT_GAIN | E | Mob can reward XP/gain to players |
| ACT_AGGRESSIVE | F | Mob attacks all players it sees |
| ACT_STAY_AREA | G | Mob cannot wander outside its area |
| ACT_WIMPY | H | Mob flees when HP drops too low |
| ACT_PET | I | Autoset when mob is a pet — do not set manually |
| ACT_TRAIN | J | Mob can train players (**requires permission**) |
| ACT_PRACTICE | K | Mob can practice skills with players (**requires permission**) |
| ACT_UPDATE_ALWAYS | L | Mob always resets even when players are present |
| ACT_NOPUSH | M | Mob cannot be shoved |
| ACT_UNDEAD | O | Mob has basic undead abilities |
| ACT_CLERIC | Q | Mob has basic cleric abilities |
| ACT_MAGE | R | Mob has basic mage abilities |
| ACT_THIEF | S | Mob has basic thief abilities (steal) |
| ACT_WARRIOR | T | Mob has basic warrior abilities |
| ACT_NOALIGN | U | Killing mob does not affect player alignment (**use sparingly**) |
| ACT_NOPURGE | V | Mob cannot be purged with immortal purge command |
| ACT_MOUNTABLE | W | Mob may be ridden (requires ITEM_SADDLE) |
| ACT_NOKILL | X | Mob vanishes if a player attacks it (for charmed pets) |
| ACT_FLAGS2 | Z | Signals that ACT_FLAGS2 letters follow in the next token |

**ACT_FLAGS2** (follow after Z; currently none implemented):
- None at this time.

**Tip:** Nearly all mobs should have at minimum `A` (IS_NPC). Shopkeepers should also have `B` (SENTINEL) and `V` (NOPURGE).

---

### AFF (Affected By) Flags

Second field on the "ACT_FLAGS AFF_FLAGS ALIGNMENT S" line.

| Flag | Letter | Description |
|---|---|---|
| AFF_BLIND | A | Mob is blind |
| AFF_INVISIBLE | B | Mob is invisible |
| AFF_DETECT_EVIL | C | Mob can detect evil |
| AFF_DETECT_INVIS | D | Mob can detect invisible |
| AFF_DETECT_MAGIC | E | Mob can detect magic |
| AFF_DETECT_HIDDEN | F | Mob can detect hidden characters |
| AFF_BERSERK | G | Mob is berserk |
| AFF_SANCTUARY | H | Mob has sanctuary (halved damage) |
| AFF_FAERIE_FIRE | I | Mob has faerie fire (easier to hit) |
| AFF_INFRAVISION | J | Mob can see in the dark |
| AFF_CURSE | K | Mob is cursed |
| AFF_SWIM | L | Mob can swim |
| AFF_POISON | M | Mob is poisoned |
| AFF_PROTECT | N | Mob is protected from evil |
| AFF_REGENERATION | O | Mob regenerates HP quickly |
| AFF_SNEAK | P | Mob is sneaking |
| AFF_HIDE | Q | Mob is hidden |
| AFF_SLEEP | R | Mob is asleep |
| AFF_CHARM | S | Mob is charmed |
| AFF_FLYING | T | Mob is flying |
| AFF_PASS_DOOR | U | Mob can pass through closed doors |
| AFF_HASTE | V | Mob is hasted (extra attacks) |
| AFF_CALM | W | Mob is calmed (cannot be attacked) |
| AFF_PLAGUE | X | Mob is plagued and spreads it |
| AFF_WEAKEN | Y | Mob is weakened |
| AFF_FLAGS2 | Z | Signals AFF_FLAGS2 letters follow in next token |

**AFF_FLAGS2** (follow after Z):

| Flag | Letter | Description |
|---|---|---|
| AFF2_DARK_VISION | A | Mob can see clearly in the dark |
| AFF2_DETECT_GOOD | B | Mob can detect good |
| AFF2_HOLD | C | *Disabled* |
| AFF2_FLAMING | D | Mob has fireshield |
| AFF2_FLAMING_COLD | E | Mob has frostshield |
| AFF2_STEALTH | F | Mob is stealthed |

**Note:** Do not flag mobs with AFF_POISON, AFF_PLAGUE, AFF_WEAKEN, AFF_CURSE, or AFF_SLEEP unless you specifically want that effect. A mob with AFF_PLAGUE will actively spread plague to players.

---

### OFF (Offense) Flags

First field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.

| Flag | Letter | Description |
|---|---|---|
| OFF_AREA_ATTACK | A | Mob can cast area attack spells (requires spec_fun) |
| OFF_BACKSTAB | B | Mob can backstab |
| OFF_BASH | C | Mob can bash |
| OFF_BERSERK | D | Mob can go berserk |
| OFF_DISARM | E | Mob can disarm opponents |
| OFF_DODGE | F | Mob can dodge attacks |
| OFF_FADE | G | Mob fades in and out (hard to hit) |
| OFF_FAST | H | Mob is fast (2+ attacks per round) |
| OFF_KICK | I | Mob can kick |
| OFF_KICK_DIRT | J | Mob can dirt kick (blind opponent) |
| OFF_PARRY | K | Mob can parry |
| OFF_RESCUE | L | Mob can rescue allies |
| OFF_TAIL | M | Mob has an extra tail attack |
| OFF_TRIP | N | Mob can trip opponents |
| OFF_CRUSH | O | Mob has a crushing attack |
| ASSIST_ALL | P | Mob randomly assists any mob in a fight |
| ASSIST_ALIGN | Q | Mob assists mobs of the same alignment |
| ASSIST_RACE | R | Mob assists mobs of the same race |
| ASSIST_PLAYERS | S | Mob assists players fighting other mobs |
| ASSIST_GUARDS | T | Mob assists guard-type mobs |
| ASSIST_VNUM | U | Mob assists mobs with the same VNUM |
| OFF_SUMMONER | V | Mob may summon aggressive mobs to assist it |
| NEEDS_MASTER | W | Autoset for pets — do not set manually |
| OFF_FLAGS2 | Z | Signals OFF_FLAGS2 letters follow in next token |

**OFF_FLAGS2** (follow after Z):

| Flag | Letter | Description |
|---|---|---|
| OFF2_HUNTER | A | Mob hunts the PC until one of them dies |
| OFF_ATTACK_DOOR_OPENER | X | Mob attacks first PC to open a door to/from its room |

---

### IMM (Immunity) Flags

Second field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.

| Flag | Letter | Description |
|---|---|---|
| IMM_SUMMON | A | Cannot be gated to (**flag MOST mobs with this**) |
| IMM_CHARM | B | Cannot be charmed (**flag MOST mobs with this**) |
| IMM_MAGIC | C | Immune to all magic |
| IMM_WEAPON | D | Immune to all weapons |
| IMM_BASH | E | Immune to bash attacks |
| IMM_PIERCE | F | Immune to pierce damage |
| IMM_SLASH | G | Immune to slash damage |
| IMM_FIRE | H | Immune to fire damage |
| IMM_COLD | I | Immune to cold damage |
| IMM_LIGHTNING | J | Immune to lightning damage |
| IMM_ACID | K | Immune to acid damage |
| IMM_POISON | L | Immune to poison |
| IMM_NEGATIVE | M | Immune to negative energy |
| IMM_HOLY | N | Immune to holy damage |
| IMM_ENERGY | O | Immune to energy attacks |
| IMM_MENTAL | P | Immune to psychic/mental attacks |
| IMM_DISEASE | Q | Immune to plague/disease |
| IMM_DROWNING | R | Immune to water/drowning damage |
| IMM_LIGHT | S | Immune to light-based attacks |
| IMM_FLAGS2 | Z | Signals IMM_FLAGS2 letters follow in next token |

**IMM_FLAGS2:** None yet implemented.

**Shopkeepers** should typically be flagged `ABCD` (IMM_SUMMON, IMM_CHARM, IMM_MAGIC, IMM_WEAPON) plus LQRP to prevent exploitation.

---

### RES (Resistance) Flags

Third field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.
A mob with a resistance takes approximately **half damage** from that type.

| Flag | Letter | Type resisted |
|---|---|---|
| RES_CHARM | B | Charm spells |
| RES_MAGIC | C | All magic |
| RES_WEAPON | D | All weapons |
| RES_BASH | E | Bash attacks |
| RES_PIERCE | F | Pierce damage |
| RES_SLASH | G | Slash damage |
| RES_FIRE | H | Fire |
| RES_COLD | I | Cold |
| RES_LIGHTNING | J | Lightning |
| RES_ACID | K | Acid |
| RES_POISON | L | Poison |
| RES_NEGATIVE | M | Negative energy |
| RES_HOLY | N | Holy |
| RES_ENERGY | O | Energy |
| RES_MENTAL | P | Mental/psi attacks |
| RES_DISEASE | Q | Plague/disease |
| RES_DROWNING | R | Water/drowning |
| RES_LIGHT | S | Light-based attacks |
| RES_FLAGS2 | Z | Signals RES_FLAGS2 follow |

**RES_FLAGS2:** None yet implemented.

---

### VULN (Vulnerability) Flags

Fourth field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.
A vulnerable mob takes approximately **double damage** from that type.

| Flag | Letter | Type vulnerable to |
|---|---|---|
| VULN_MAGIC | C | All magic |
| VULN_WEAPON | D | All weapons |
| VULN_BASH | E | Bash |
| VULN_PIERCE | F | Pierce |
| VULN_SLASH | G | Slash |
| VULN_FIRE | H | Fire |
| VULN_COLD | I | Cold |
| VULN_LIGHTNING | J | Lightning |
| VULN_ACID | K | Acid |
| VULN_POISON | L | Poison |
| VULN_NEGATIVE | M | Negative energy |
| VULN_HOLY | N | Holy |
| VULN_ENERGY | O | Energy |
| VULN_MENTAL | P | Mental/psi |
| VULN_DISEASE | Q | Disease |
| VULN_DROWNING | R | Drowning/water |
| VULN_LIGHT | S | Light |
| VULN_WOOD | T | Wooden weapons |
| VULN_SILVER | U | Silver weapons |
| VULN_FLAGS2 | Z | Signals VULN_FLAGS2 follow |

**VULN_FLAGS2:**

| Flag | Letter | Description |
|---|---|---|
| VULN2_IRON | A | Mob takes double damage from iron weapons (e.g., elves) |

**Common patterns:**
- Undead: `IMM_POISON+DISEASE`, `VULN_HOLY+LIGHT+SILVER`
- Fire-based: `IMM_FIRE`, `VULN_COLD+WATER`
- Demons/evil: `IMM_FIRE+NEGATIVE`, `VULN_HOLY`

---

### FORM Flags

First field on the "form parts SIZE material" line. Describes the mob's body form.
Use `0` if none apply (most humanoid mobs).

| Flag | Letter | Description |
|---|---|---|
| FORM_EDIBLE | A | Mob can be eaten |
| FORM_POISON | B | Mob's flesh is poisonous if eaten |
| FORM_MAGICAL | C | Mob is magical in nature |
| FORM_INSTANT_DECAY | D | Mob's corpse decays instantly |
| FORM_OTHER | E | Other/unusual form |
| FORM_ANIMAL | G | Mob is an animal |
| FORM_SENTIENT | H | Mob is a thinking creature |
| FORM_UNDEAD | I | Mob is undead |
| FORM_CONSTRUCT | J | Mob is a construct (golem, etc.) |
| FORM_MIST | K | Mob is made of mist |
| FORM_INTANGIBLE | L | Mob is intangible (ghost, etc.) |
| FORM_BIPED | M | Mob walks on two legs |
| FORM_CENTAUR | N | Mob is centaur-shaped |
| FORM_INSECT | O | Mob is insect-shaped |
| FORM_SPIDER | P | Mob is spider-shaped |
| FORM_CRUSTACEAN | Q | Mob is crustacean-shaped |
| FORM_WORM | R | Mob is worm-shaped |
| FORM_BLOB | S | Mob is blob/ooze-shaped |
| FORM_MAMMAL | V | Mob is a mammal |
| FORM_BIRD | W | Mob is bird-shaped |
| FORM_REPTILE | X | Mob is reptile-shaped |

---

### PARTS Flags

Second field on the "form parts SIZE material" line. Describes body parts present on the mob.
Use `0` for default human-type body (code will use race defaults). Set explicitly for unusual mobs.

| Flag | Letter | Body part |
|---|---|---|
| PART_HEAD | A | Has a head |
| PART_ARMS | B | Has arms |
| PART_LEGS | C | Has legs |
| PART_HEART | D | Has a heart |
| PART_BRAINS | E | Has brains |
| PART_GUTS | F | Has guts |
| PART_HANDS | G | Has hands |
| PART_FEET | H | Has feet |
| PART_FINGERS | I | Has fingers |
| PART_EAR | J | Has ears |
| PART_EYE | K | Has eyes |
| PART_LONG_TONGUE | L | Has a long tongue |
| PART_EYESTALKS | M | Has eyestalks |
| PART_TENTACLES | N | Has tentacles |
| PART_FINS | O | Has fins |
| PART_WINGS | P | Has wings |
| PART_TAIL | Q | Has a tail |
| PART_CLAWS | U | Has claws |
| PART_FANGS | V | Has fangs |
| PART_HORNS | W | Has horns |
| PART_SCALES | X | Has scales |

**Standard humanoid:** `ABCDEFGHI JK` (head, arms, legs, heart, brains, guts, hands, feet, fingers, ear, eye)

---

### Position Values

Used for `start_pos` and `default_pos` on the "start_pos default_pos sex gold" line.

| Value | Name | Description |
|---|---|---|
| 0 | POS_DEAD | Dead — *internal use only* |
| 1 | POS_MORTAL | Mortally wounded — *internal use only* |
| 2 | POS_INCAP | Incapacitated — *internal use only* |
| 3 | POS_STUNNED | Stunned — *internal use only* |
| 4 | POS_SLEEPING | Sleeping |
| 5 | POS_RESTING | Resting |
| 6 | POS_SITTING | Sitting |
| 7 | POS_FIGHTING | Fighting — *internal use only* |
| 8 | POS_STANDING | Standing |
| 9 | POS_MOUNTED | Mounted on another mob |

**Most mobs use `8 8`** (start standing, return to standing). Sleeping watch animals use `4 8` (starts asleep, returns to standing).

---

### Sex Values

Third field on the "start_pos default_pos sex gold" line.

| Value | Name |
|---|---|
| 0 | Neuter (it) |
| 1 | Male |
| 2 | Female |

---

### Races

The race string determines some default combat behaviors and vulnerabilities. Write the exact string followed by `~`.

| Race | Race | Race | Race | Race |
|---|---|---|---|---|
| bat | elf | hobgoblin | plant | undead |
| bear | fido | horse | rabbit | unique |
| cat | fish | human | saurian | vampire |
| centipede | fox | kobold | school monster | water fowl |
| dog | fox | lizard | snake | wolf |
| doll | goblin | modron | song bird | wyvern |
| dragon | giant | orc | tree | — |
| dwarf | head | pig | troll | — |
| dwarf | hobbit | plant | undead | — |

**Note:** The race does not have to match the mob's appearance. An ogre mob can have race "human". The race affects internal combat and loot generation behaviors. Use `unique` for mobs that don't fit any category.

---

### Size Values

Third field on "form parts SIZE material" line — a single letter.

| Letter | Size | Example |
|---|---|---|
| T | Tiny | Pixie, rat |
| S | Small | Halfling, gnome |
| M | Medium | Human, elf, orc |
| L | Large | Ogre, troll |
| H | Huge | Giant, large dragon |
| G | Giant | Elder dragon, titan |

---

### Damage / Attack Types

Used for `dam_type` (mob's bare-hand attack) and `<damage type>` in weapon objects.

| Value | Name | Type |
|---|---|---|
| 0 | Hit | Bash |
| 1 | Slice | Slash |
| 2 | Stab | Pierce |
| 3 | Slash | Slash |
| 4 | Whip | Slash |
| 5 | Claw | Slash |
| 6 | Blast | Bash |
| 7 | Pound | Bash |
| 8 | Crush | Bash |
| 9 | Grep | Bash |
| 10 | Bite | Pierce |
| 11 | Pierce | Pierce |
| 12 | Suction | Bash |
| 13 | Beating | Bash |
| 14 | Digestion | Acid |
| 15 | Charge | Bash |
| 16 | Slap | Bash |
| 17 | Punch | Bash |
| 18 | Wrath | Energy |
| 19 | Magic | Magic |
| 20 | Divine Power | Holy |
| 21 | Cleave | Slash |
| 22 | Scratch | Slash |
| 23 | Peck (Pierce) | Pierce |
| 24 | Peck (Bash) | Bash |
| 25 | Chop | Slash |
| 26 | Sting | Pierce |
| 27 | Smash | Bash |
| 28 | Shocking Bite | Lightning |
| 29 | Flaming Bite | Fire |
| 30 | Freezing Bite | Cold |
| 31 | Acidic Bite | Acid |
| 32 | Chomp | Pierce |

---

### HP & Damage Reference Chart

Format for HP dice: `NdM+X` where N×M is max, (N×(M+1)/2)+X is average.
**Default AC from the chart assumes average equipment.** Adjust by ±2–4 for heavily or lightly armored mobs.

| Lvl | HP Dice | AC | Damage Die | Lvl | HP Dice | AC | Damage Die |
|---|---|---|---|---|---|---|---|
| 1 | 2d6+10 | 9 | 1d4+0 | 31 | 6d12+928 | -10 | 4d6+9 |
| 2 | 2d7+21 | 8 | 1d5+0 | 32 | 10d10+1000 | -10 | 6d4+9 |
| 3 | 2d6+35 | 7 | 1d6+0 | 33 | 10d10+1100 | -11 | 6d4+10 |
| 4 | 2d7+46 | 6 | 1d5+1 | 34 | 10d10+1200 | -11 | 4d7+10 |
| 5 | 2d6+60 | 5 | 1d6+1 | 35 | 10d10+1300 | -11 | 4d7+11 |
| 6 | 2d7+71 | 4 | 1d7+1 | 36 | 10d10+1400 | -12 | 3d10+11 |
| 7 | 2d6+85 | 4 | 1d8+1 | 37 | 10d10+1500 | -12 | 3d10+12 |
| 8 | 2d7+96 | 3 | 1d7+2 | 38 | 10d10+1600 | -13 | 5d6+12 |
| 9 | 2d6+110 | 2 | 1d8+2 | 39 | 15d10+1700 | -13 | 5d6+13 |
| 10 | 2d7+121 | 1 | 2d4+2 | 40 | 15d10+1850 | -13 | 4d8+13 |
| 11 | 2d8+134 | 1 | 1d10+2 | 41 | 25d10+2000 | -14 | 4d8+14 |
| 12 | 2d10+150 | 0 | 1d10+3 | 42 | 25d10+2250 | -14 | 3d12+14 |
| 13 | 2d10+170 | -1 | 2d5+3 | 43 | 25d10+2500 | -15 | 3d12+15 |
| 14 | 2d10+190 | -1 | 1d12+3 | 44 | 25d10+2750 | -15 | 8d4+15 |
| 15 | 3d9+208 | -2 | 2d6+3 | 45 | 25d10+3000 | -15 | 8d4+16 |
| 16 | 3d9+233 | -2 | 2d6+4 | 46 | 25d10+3250 | -16 | 6d6+16 |
| 17 | 3d9+258 | -3 | 3d4+4 | 47 | 25d10+3500 | -17 | 6d6+17 |
| 18 | 3d9+283 | -3 | 2d7+4 | 48 | 25d10+3750 | -18 | 6d6+18 |
| 19 | 3d9+308 | -4 | 2d7+5 | 49 | 50d10+4000 | -19 | 4d10+18 |
| 20 | 3d9+333 | -4 | 2d8+5 | 50 | 50d10+4500 | -20 | 5d8+19 |
| 21 | 4d10+360 | -5 | 4d4+5 | 51 | 50d10+5000 | -21 | 5d8+20 |
| 22 | 5d10+400 | -5 | 4d4+6 | 52 | 50d10+5500 | -22 | 6d7+20 |
| 23 | 5d10+450 | -6 | 3d6+6 | 53 | 50d10+6000 | -23 | 6d7+21 |
| 24 | 5d10+500 | -6 | 2d10+6 | 54 | 50d10+6500 | -24 | 7d6+22 |
| 25 | 5d10+550 | -7 | 2d10+7 | 55 | 50d10+7000 | -25 | 10d4+23 |
| 26 | 5d10+600 | -7 | 3d7+7 | 56 | 50d10+7500 | -26 | 10d4+24 |
| 27 | 5d10+650 | -8 | 5d4+7 | 57 | 50d10+8000 | -27 | 6d8+24 |
| 28 | 6d12+703 | -8 | 2d12+8 | 58 | 50d10+8500 | -28 | 5d10+25 |
| 29 | 6d12+778 | -9 | 2d12+8 | 59 | 50d10+9000 | -29 | 8d6+26 |
| 30 | 6d12+853 | -9 | 4d6+8 | 60 | 50d10+9500 | -30 | 8d6+28 |

**AC adjustments by class:**
- **Warrior:** read HP and damage one level higher
- **Mage:** read HP and AC one level lower; read damage three levels lower
- **Cleric:** read HP one level lower; read damage two levels lower
- **Thief:** read HP, AC, and damage one level lower
- **Magic AC** (exotic slot): `(ac - 10) / n + 10` where n=4 for most, n=3 for thief/cleric, n=2 for mage

**Mana guidelines:**
- No magic talent: `100`
- Normal mob: `100 + 1d5/lvl` → e.g., lvl 20 = `4d20+100`
- Spell caster: `100 + 1d10/lvl` → e.g., lvl 20 = `4d40+100`

The section ends with `#0` on its own line after the last mob.

---

## #OBJECTS Section

### Object Format

```
#VNUM
keywords~
Short name (shown in inventory, room)~
Long description (seen lying in room).~
material~
<item_type> <ITEM_FLAGS> <ITEM_FLAGS2> <WEAR_FLAGS>
<value0> <value1> <value2> <value3> <value4>
<level> <weight> <cost> <condition>
E
<extra-desc-keywords>~
<extra description text>
~
A
<apply_type> <apply_value>
```

**Optional sections:**
- `E` sections add extra descriptions (unlimited; come before `A` sections)
- `A` sections add bonuses/penalties to player stats when worn (unlimited)
- `T` section adds a wear message (see Item Wear Message below)

**The item type, flags, and wear flags line format:**
```
<item_type> <ITEM_FLAGS> <ITEM_FLAGS2> <WEAR_FLAGS>
```
- If no ITEM_FLAGS2 are needed, put `0` in place of the flags2 field, or omit it
- If no WEAR_FLAGS are needed, put `0`

**Example weapon object:**
```
#QQ40
sword underworld~
The Sword of the Underworld~
A large, dark sword of solid obsidian gleams evilly here.~
adamantite~
5 ABCEJL 0 AN
1 11 6 6 DE
50 30 35000 P
E
sword underworld~
This heavy sword has an evil, dark shine to its metal.
~
A
1 1
A
18 1
A
19 1
```

**Field descriptions:**
- Line 1 (`5 ABCEJL 0 AN`): item type=5 (weapon), flags=ABCEJL, flags2=0, wear flags=AN (TAKE + WIELD)
- Line 2 (`1 11 6 6 DE`): weapon class=1 (sword), 11 dice of 6 sides, damage type=6 (blast), weapon flags=DE (SHARP+VORPAL)
- Line 3 (`50 30 35000 P`): level=50, weight=30, cost=35000, condition=P (perfect)

The section ends with `#0` on its own line after the last object.

---

### Object Types

Used as the first number on the `<item_type> <flags> <flags2> <wear_flags>` line.

| Value | Name | Description | Worn/Used via |
|---|---|---|---|
| 1 | ITEM_LIGHT | Light source | hold/light slot |
| 2 | ITEM_SCROLL | Scroll containing spells | recite |
| 3 | ITEM_WAND | Wand with charges | zap |
| 4 | ITEM_STAFF | Staff with charges | brandish |
| 5 | ITEM_WEAPON | Weapon | wield |
| 8 | ITEM_TREASURE | Treasure (jewels/gems) | sell to jeweler |
| 9 | ITEM_ARMOR | Armor/equipment | wear |
| 10 | ITEM_POTION | Potion | quaff |
| 11 | ITEM_CLOTHING | Clothing (low AC) | wear |
| 12 | ITEM_FURNITURE | Static prop, no interaction | — |
| 13 | ITEM_TRASH | Junk, unsellable | — |
| 15 | ITEM_CONTAINER | Container for items | put/get |
| 17 | ITEM_DRINK_CON | Drink container | drink/fill |
| 18 | ITEM_KEY | Key for doors/containers | unlock |
| 19 | ITEM_FOOD | Food | eat |
| 20 | ITEM_MONEY | Money/coins | auto-looted |
| 22 | ITEM_BOAT | Boat (cross WATER_NOSWIM) | hold |
| 23 | ITEM_CORPSE_NPC | NPC corpse | — |
| 25 | ITEM_FOUNTAIN | Fountain (infinite drink) | drink |
| 26 | ITEM_PILL | Pill with spells | eat |
| 28 | ITEM_MAP | Map (shows ASCII map on look) | look |
| 29 | ITEM_SCUBA_GEAR | Breathing gear for underwater | wear |
| 30 | ITEM_PORTAL | Portal to another room | enter |
| 31 | ITEM_MANIPULATION | Object with interactive trigger | push/pull/flip/etc. |
| 33 | ITEM_SADDLE | Saddle (needed to mount mobs) | wear |
| 37 | ITEM_ACTION | Object that triggers an event | interact |

---

### Object Flags (ITEM_FLAGS)

Second field on the flags line. Combined letter bitmask.

| Flag | Letter | Description |
|---|---|---|
| ITEM_GLOW | A | Item glows (shows GLOWING tag) |
| ITEM_HUM | B | Item hums (shows HUMMING tag) |
| ITEM_DARK | C | Item is dark (shows DARK tag — for evil items) |
| ITEM_LOCK | D | Item starts locked (for containers) |
| ITEM_EVIL | E | Item has red aura with detect evil; pair with ITEM_ANTI_GOOD |
| ITEM_INVIS | F | Item is invisible; requires detect invis to see |
| ITEM_MAGIC | G | Item shows as magical with detect magic |
| ITEM_NODROP | H | Item cannot be dropped (cursed-like) |
| ITEM_BLESS | I | Item is blessed; shows blue aura with detect good |
| ITEM_ANTI_GOOD | J | Zaps good-aligned characters, forcing them to drop it |
| ITEM_ANTI_EVIL | K | Zaps evil-aligned characters, forcing them to drop it |
| ITEM_ANTI_NEUTRAL | L | Zaps neutral-aligned characters, forcing them to drop it |
| ITEM_NOREMOVE | M | Cannot be un-worn once equipped (cursed-like) |
| ITEM_INVENTORY | N | Does not use an inventory slot (**use only with permission**) |
| ITEM_NOPURGE | O | Cannot be purged by immortal `purge` command (fountains, pits) |
| ITEM_ROT_DEATH | P | Decays after a number of ticks |
| ITEM_BOUNCE | S | Randomly teleports room-to-room within area |
| ITEM_TPORT | T | Randomly teleports area-to-area |
| ITEM_NOIDENTIFY | U | Immune to identify spell |
| ITEM_NOLOCATE | V | Immune to locate object spell |
| ITEM_RACE_RESTRICTED | W | Only wearable by specified race (requires ITEM_FLAGS2 race value) |
| ITEM_FLAGS2 | Z | Signals ITEM_FLAGS2 letters follow in next `<flags2>` token |

---

### Item Flags 2 (ITEM_FLAGS2)

Third field on the flags line (or the token after `Z` in ITEM_FLAGS).

| Flag | Letter | Description |
|---|---|---|
| ITEM2_HUMAN_ONLY | A | Only wearable by humans |
| ITEM2_HALFLING_ONLY | B | Only wearable by halflings |
| ITEM2_DWARF_ONLY | C | Only wearable by dwarves |
| ITEM2_ELF_ONLY | D | Only wearable by elves |
| ITEM2_SAURIAN_ONLY | E | Only wearable by saurians |
| ITEM2_ADD_INVIS | F | Bestows invisibility when worn (**requires permission**) |
| ITEM2_ADD_DETECT_INVIS | G | Bestows detect invisible when worn (**requires permission**) |
| ITEM2_ADD_FLY | H | Bestows fly when worn (**requires permission**) |

---

### Wear Flags

Fourth field on the flags line.

| Flag | Letter | Wear location |
|---|---|---|
| ITEM_TAKE | A | **Required** for item to be picked up/gotten |
| ITEM_WEAR_FINGER | B | Worn on finger(s) |
| ITEM_WEAR_NECK | C | Worn around neck |
| ITEM_WEAR_BODY | D | Worn on body |
| ITEM_WEAR_HEAD | E | Worn on head |
| ITEM_WEAR_LEGS | F | Worn on legs |
| ITEM_WEAR_FEET | G | Worn on feet |
| ITEM_WEAR_HANDS | H | Worn on hands |
| ITEM_WEAR_ARMS | I | Worn on arms |
| ITEM_WEAR_SHIELD | J | Worn as shield |
| ITEM_WEAR_ABOUT | K | Worn about body (cloak) |
| ITEM_WEAR_WAIST | L | Worn around waist (belt) |
| ITEM_WEAR_WRIST | M | Worn on wrist(s) |
| ITEM_WIELD | N | Wieldable as weapon |
| ITEM_HOLD | O | Holdable in hand |
| ITEM_TWO_HANDS | P | Requires two free hands to wield (pair with WEAPON_TWO_HANDS weapon type) |

**Typical wear flag combinations:**
- Weapon: `AN` (take + wield)
- Armor: `A` + one wear flag, e.g., `AD` (take + body)
- Ring: `AB` (take + finger)
- Two-hander: `ANP` (take + wield + two hands)

---

### Weapon Class

First value in the weapon values line.

| Value | Name | Description |
|---|---|---|
| 0 | WEAPON_EXOTIC | Exotic weapon; immune to enchantment spells |
| 1 | WEAPON_SWORD | Sword |
| 2 | WEAPON_DAGGER | Dagger |
| 3 | WEAPON_SPEAR | Spear |
| 4 | WEAPON_MACE | Mace |
| 5 | WEAPON_AXE | Axe |
| 6 | WEAPON_FLAIL | Flail |
| 7 | WEAPON_WHIP | Whip |
| 8 | WEAPON_POLEARM | Polearm |
| 9 | WEAPON_BOW | Bow (requires archery skill) |

---

### Weapon Types

Fifth value in the weapon values line (the `<weapon type>` flags field). Letter bitmask.

| Flag | Letter | Description |
|---|---|---|
| WEAPON_FLAMING | A | Deals fire-type damage |
| WEAPON_FROST | B | Deals cold-type damage |
| WEAPON_VAMPIRIC | C | *Disabled* |
| WEAPON_SHARP | D | Never needs sharpening *disabled* |
| WEAPON_VORPAL | E | Minor chance of instant kill *disabled* |
| WEAPON_TWO_HANDS | F | Requires two hands (pair with ITEM_TWO_HANDS wear flag) |

Use `0` if no weapon type flags apply.

---

### Apply Types

Used with `A` sections; format: `A\n<type> <value>`

| Value | Name | Effect |
|---|---|---|
| 0 | APPLY_NONE | No effect (placeholder) |
| 1 | APPLY_STR | Modifies strength |
| 2 | APPLY_DEX | Modifies dexterity |
| 3 | APPLY_INT | Modifies intelligence |
| 4 | APPLY_WIS | Modifies wisdom |
| 5 | APPLY_CON | Modifies constitution |
| 6 | APPLY_SEX | Shifts sex (0=neuter, 1=male, 2=female) |
| 7 | APPLY_CLASS | Shifts character class (rarely used) |
| 8 | APPLY_LEVEL | Modifies effective level |
| 9 | APPLY_AGE | Modifies character age in years |
| 10 | APPLY_HEIGHT | Modifies height |
| 11 | APPLY_WEIGHT | Modifies weight |
| 12 | APPLY_MANA | Modifies maximum mana |
| 13 | APPLY_HIT | Modifies maximum hit points |
| 14 | APPLY_MOVE | Modifies maximum movement |
| 15 | APPLY_GOLD | Modifies gold carried |
| 16 | APPLY_EXP | Modifies experience points |
| 17 | APPLY_AC | Modifies armor class (negative = better) |
| 18 | APPLY_HITROLL | Modifies to-hit roll |
| 19 | APPLY_DAMROLL | Modifies damage roll |
| 20 | APPLY_SAVING_PARA | Modifies saving throw vs paralysis |
| 21 | APPLY_SAVING_ROD | Modifies saving throw vs rods/wands |
| 22 | APPLY_SAVING_PETRI | Modifies saving throw vs petrification |
| 23 | APPLY_SAVING_BREATH | Modifies saving throw vs breath (**use sparingly**) |
| 24 | APPLY_SAVING_SPELL | Modifies saving throw vs spell (**use sparingly**) |
| 25 | APPLY_IMMUNITY | Grants immunity to a damage type |

**Balance rule:** For every bonus there should be a roughly equal penalty. Objects with strong stats (+5 damroll, +5 hitroll) will be carefully scrutinized by the IMP.

---

### Values by Object Type

The values line format is: `<value0> <value1> <value2> <value3> <value4>`
If a value is unused, use `0` — never leave blank.

| Type | value0 | value1 | value2 | value3 | value4 |
|---|---|---|---|---|---|
| ITEM_LIGHT | unused | unused | hours of light (9999=infinite) | unused | unused |
| ITEM_SCROLL | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_WAND | spell level | max charges | current charges | spell slot | unused |
| ITEM_STAFF | spell level | max charges | current charges | spell slot | unused |
| ITEM_WEAPON | weapon class | # dice | die size | damage type | weapon type flags |
| ITEM_TREASURE | unused | unused | unused | unused | unused |
| ITEM_ARMOR | pierce AC | bash AC | slash AC | magic AC | unused |
| ITEM_POTION | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_CLOTHING | pierce AC | bash AC | slash AC | magic AC | unused |
| ITEM_FURNITURE | unused | unused | unused | unused | unused |
| ITEM_TRASH | unused | unused | unused | unused | unused |
| ITEM_CONTAINER | weight capacity | container flags | key VNUM | unused | unused |
| ITEM_DRINK_CON | liquid capacity | current qty | liquid type (0-15) | 0 | unused |
| ITEM_KEY | unused | unused | unused | unused | unused |
| ITEM_FOOD | hours of food satisfaction | unused | unused | unused | unused |
| ITEM_MONEY | gold value | unused | unused | unused | unused |
| ITEM_BOAT | unused | unused | unused | unused | unused |
| ITEM_FOUNTAIN | capacity | current qty | unused | unused | unused |
| ITEM_PILL | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_MAP | unused | unused | unused | unused | unused |
| ITEM_PORTAL | portal type | to_room VNUM | timer ticks | closeable/lockable | key VNUM |
| ITEM_MANIPULATION | manip type | to_room VNUM | door direction | object state | 0 |
| ITEM_SADDLE | unused | unused | unused | unused | unused |
| ITEM_ACTION | action type | unused | poison duration (game hrs) | unused | unused |

**Notes:**
- `spell level` is the *casting level* of the spell, not the reader's level
- Use `vnum spell <spell name>` in-game to get spell slot numbers, or see [Spell Slot Reference](#spell-slot-reference)
- Scrolls, potions, and pills can have up to 3 spells; use `0` for unused spell slots
- `ITEM_ARMOR` values: lower values = better protection (e.g., -5 is better than 0). Use the level chart: roughly level/2 for AC value. Use `0` to let code auto-assign
- `ITEM_DRINK_CON` value2: non-zero liquid type value poisons the drink
- `ITEM_MONEY` objects with `gold` material are auto-looted even if autoloot is off
- Set `<obj level>` to `-1` to have the game assign level based on the mob carrying it

**Portal types:**
| Value | Behavior |
|---|---|
| 1 | Hall of Heroes-style; to_room and timer unused |
| 4 | Crystal ball; timer optional |
| 5 | Teleport-pad style (berry→smurf, clown→froboz) |
| 6 | Closeable/lockable portal, otherwise type 5 behavior |

**Manipulation types:**
| Value | Type | Value | Type |
|---|---|---|---|
| 1 | Flip | 6 | Climb Up |
| 2 | Move | 7 | Climb Down |
| 3 | Pull | 8 | Crawl |
| 4 | Push | 9 | Jump |
| 5 | Turn | — | — |

**Action item types:**
| Value | Type | Effect |
|---|---|---|
| 1 | Recall | Instantly recalls the player |
| 2 | Death | Instantly kills the player |
| 3 | Poison | Instantly poisons the player (no save) |

---

### Container Flags

Used as `value1` on ITEM_CONTAINER's values line. **Values add together (bitmask with powers of 2).**

| Value | Flag | Description |
|---|---|---|
| 1 | CONT_CLOSEABLE | Container can be closed |
| 2 | CONT_PICKPROOF | Container's lock cannot be picked |
| 4 | CONT_CLOSED | Container starts closed |
| 8 | CONT_LOCKED | Container starts locked |
| 16 | CONT_TRAPPED | Container is trapped (harm if opened improperly) |

**Example:** A locked, closeable chest = 1+4+8 = `13` as value1.

---

### Liquid Values

Used as `value2` on ITEM_DRINK_CON values line.

| Value | Liquid | Effect |
|---|---|---|
| 0 | Water | Quenches thirst normally |
| 1 | Beer | Intoxicating; more consumed = more drunk |
| 2 | Wine | Same as beer |
| 3 | Ale | Same as beer |
| 4 | Dark Ale | Same as beer |
| 5 | Whiskey | Same as beer |
| 6 | Lemonade | Quenches thirst better |
| 7 | Firebreather | Instantly drunk with one drink |
| 8 | Local Specialty | Instantly drunk with one drink |
| 9 | Slime Mold Juice | Makes drinker sick (poison) |
| 10 | Milk | Quenches thirst and slightly reduces hunger |
| 11 | Tea | Quenches thirst; rare burn damage |
| 12 | Coffee | Quenches thirst; rare burn damage |
| 13 | Blood | Quenches thirst and hunger for vampires |
| 14 | Salt Water | Increases thirst |
| 15 | Cola | Quenches thirst; random belching |

Values above 15 default to water.

---

### Object Condition

Fourth field on the `<level> <weight> <cost> <condition>` line.

| Letter | Condition |
|---|---|
| P | Perfect |
| G | Good |
| A | Average |
| W | Worn |
| D | Damaged |
| R | Ruined |

Most objects use `P` (Perfect).

---

### Item Wear Message (T flag)

You can add a message triggered when a player equips an item:

```
T
<room message (others see)>~
<personal message (wearer sees)>~
```

- `$p` substitutes the item's name
- `$n` substitutes the wearer's name

Place the `T` section after any `A` sections.

---

### Materials

Used in the material field (followed by `~`). Affects vulnerability to fire, acid, etc.
Objects made of **wood, paper, or glass** can be destroyed by fire/acid.
Objects made of **gold** material are auto-looted like coins.
Objects made of **pill** material can be eaten for spell effects.
Objects made of **food** material satisfy hunger when eaten.
Objects made of **silver** or **wood** interact with mob vulnerabilities to silver/wooden weapons.
Objects made of **iron** interact with elves' vulnerability to iron.

| Material | Material | Material | Material |
|---|---|---|---|
| adamantite | cloth | iron | steel |
| brass | food | leather | stone |
| bronze | glass | paper | vellum |
| silver | gold | pill | wood |

---

## #ROOMS Section

### Room Format

```
#VNUM
Room Name~
Multi-line room description.
Can span many lines.
~
<area_prefix> <ROOM_FLAGS> <sector_type>
[<room_aff_by data line — only if ROOM_AFF_BY flag H is set>]
D<direction>
<exit description>
~
<door keyword or empty>
~
<door type> <key VNUM or -1> <destination VNUM>
E
<extra desc keywords>~
<extra desc text>
~
S
```

**Field descriptions:**

| Field | Description |
|---|---|
| `#VNUM` | Room's unique virtual number |
| `Room Name~` | Short name of the room (shown in status bar/compact view) |
| `description~` | Multi-line room description; `~` alone on final line |
| `area_prefix` | Two-letter area code (e.g., `QQ`, `AC`); informational only |
| `ROOM_FLAGS` | Letter bitmask; see Room Flags table |
| `sector_type` | Integer; see Sector Types table |
| `D<direction>` | Exit section; `D0` or `D 0`=north, `D1` or `D 1`=east, ..., `D9`=southwest |
| `exit description` | Text player sees when typing `look north`, etc. |
| `door keyword~` | Keyword(s) for the door; empty line followed by `~` if no door |
| `door type` | 0=open passage, 1=door, 2=locked door, etc. (see Door Types) |
| `key VNUM` | VNUM of key object; use `-1` if no key |
| `destination VNUM` | VNUM of room this exit leads to |
| `E` | Optional extra-description section |
| `S` | **Mandatory** end marker for each room |

**Important rules:**
- Every room **must** end with `S` — forgetting this is the most common area file error
- Exits must be bidirectional unless you deliberately want a one-way passage
- Use `-1` for key VNUM when no key exists (never use `0`)
- Use destination `-1` only for a descriptive, non-traversable direction; the game retains its look text but does not let players move through it
- Multiple `D`, `E` sections are allowed before the `S`
- The `#ROOMS` section ends with `#0` after the final room's `S`

**Example room:**
```
#QQ00
Rock Carving~
You scramble through this mountain pass, the frightening stony walls reaching
to the sky on either side of you. Cut into the rock face is an imposing
monolithic statue of a long forgotten king. Ahead, iron gates block passage.
~
QQ 0 5
D0
A pass through tall iron gates.
gate gates~
~
2 QQ23 QQ01
D2
A pass through the mountains.
~
~
0 -1 QQ02
E
statue~
An imposing stone statue of the ancient king Ozymandias gazes down upon you.
~
S
```

---

### Room Flags

Second field on the `<area_prefix> <ROOM_FLAGS> [ROOM_FLAGS2] <sector_type>` line. The loader accepts letter bitmasks, decimal masks, and additive pipe syntax such as `8|4096`, although letters are preferred for new rooms.

| Flag | Letter | Description |
|---|---|---|
| ROOM_DARK | A | Room is dark; light source required to see |
| ROOM_JAIL | B | Configured jail or related holding room |
| ROOM_NO_MOB | C | Mobs cannot wander into this room |
| ROOM_INDOORS | D | Room is inside; immune to weather |
| ROOM_RIVER | E | Room is a river; pushes players in the exit direction |
| ROOM_TELEPORT | F | Room transports player to a designated room after N ticks |
| ROOM_AFF_BY | H | Room deals periodic damage (requires extra data line; see below) |
| ROOM_DEATHTRAP | I | Instantly kills all in room. **Use only with permission; requires warning exits** |
| ROOM_PRIVATE | J | Maximum 2 occupants |
| ROOM_SAFE | K | No combat allowed. **Use sparingly; requires permission** |
| ROOM_SOLITARY | L | Maximum 1 occupant |
| ROOM_PET_SHOP | M | Pet shop designation. **Requires permission** |
| ROOM_NO_RECALL | N | Players cannot recall, word of recall, or scroll from this room |
| ROOM_IMP_ONLY | O | Only implementors can enter |
| ROOM_GODS_ONLY | P | Only immortals can enter |
| ROOM_HEROES_ONLY | Q | Only heroes and immortals can enter |
| ROOM_NEWBIES_ONLY | R | Only levels 1-5 and immortals can enter |
| ROOM_LAW | S | Law-enforcement room behavior |
| ROOM_HP_REGEN | T | Increased hit-point regeneration |
| ROOM_MANA_REGEN | U | Increased mana regeneration |
| ROOM_ARENA | V | Arena room behavior |
| ROOM_CASTLE_JOIN | W | Castle joining room |
| ROOM_SILENT | X | No spells can be cast in this room |
| ROOM_FLAGS2 | Z | Signals that a ROOM_FLAGS2 token follows |

`ROOM_JAIL` (`B`) is reserved for the configured jail and related holding rooms.

When `Z` is present, place a ROOM_FLAGS2 token between ROOM_FLAGS and the sector type:

| Flag | Letter | Description |
|---|---|---|
| ROOM2_NO_TPORT | A | Excludes the room from the teleport spell's random destinations |
| ROOM2_B_UNUSED | B | Reserved; do not use |
| ROOM2_BANK | C | Enables room-based banking commands |

---

### Sector Types

Third field on the room data line.

| Value | Name | Description |
|---|---|---|
| 0 | SECT_INSIDE | Building interior; immune to most weather |
| 1 | SECT_CITY | City streets; minimal endurance use |
| 2 | SECT_FIELD | Open field; small endurance use |
| 3 | SECT_FOREST | Forest; moderate endurance use |
| 4 | SECT_HILLS | Hills; higher endurance use |
| 5 | SECT_MOUNTAIN | Mountain; heavy endurance use |
| 6 | SECT_WATER_SWIM | Shallow water; crossable without boat |
| 7 | SECT_WATER_NOSWIM | Deep water; requires boat item to cross |
| 8 | SECT_UNDER_WATER | Underwater; requires scuba gear (or drowning damage) |
| 9 | SECT_AIR | Airborne; requires flying to enter/move |
| 10 | SECT_DESERT | Desert; thirst increases faster, higher endurance use |
| 11 | SECT_UNDERGROUND | Underground (caves); immune to most weather |

---

### Exit Directions

Used as suffix to the `D` command.

| Value | Direction | Value | Direction |
|---|---|---|---|
| 0 | North | 5 | Down |
| 1 | East | 6 | Northeast |
| 2 | South | 7 | Northwest |
| 3 | West | 8 | Southeast |
| 4 | Up | 9 | Southwest |

---

### Door Type Values

First number on the `<door type> <key VNUM> <destination VNUM>` line.

| Value | Meaning |
|---|---|
| 0 | Open passage (no door) |
| 1 | Door (EX_ISDOOR) |
| 2 | Locked door (EX_LOCKED) |
| 3 | Pickproof locked door (EX_PICKPROOF) |
| 4 | Secret exit (EX_SECRET) |
| 5 | Wizard-locked door (EX_WIZLOCKED) |
| 6 | Trapped door (EX_TRAPPED) |

For a secret door: use type `4`, put the secret word as `door keyword`, and leave a blank tilde for the door name. Without the keyword the exit does not appear in the room description.

---

### ROOM_AFF_BY Details

When ROOM_FLAGS includes `H`, add this line immediately after the room flags line:

```
<type> <level> <unused> <unused> <unused> <unused> <unused> <dam_dice> <dam_sides>
```

| Field | Description |
|---|---|
| `type` | Damage type (see table below) |
| `level` | Minimum PC level required to enter room |
| next 5 fields | Unused — put `0` for each |
| `dam_dice` | Number of damage dice per tick |
| `dam_sides` | Sides on each die |

**Room AFF types:**

| Value | Name | Effect |
|---|---|---|
| 1 | STINKING_CLOUD | Poisons all PCs in room; causes choking |
| 3 | VOLCANIC | Fire/heat damage to all PCs per tick |
| 4 | SHOCKER | Electrical damage to all PCs per tick |

**Example:** A volcanic room with minimum entry level 20, dealing 3d8 damage per tick:
```
QQ H 3
3 20 0 0 0 0 0 3 8
```

---

## #RESETS Section

### Reset Commands

The `#RESETS` section populates the area with mobs and objects at game load and at each area reset.

```
* comment line (ignored)
M 0 <mob_vnum> <limit> <room_vnum>      — load mobile in room
O 0 <obj_vnum> <limit> <room_vnum>      — load object in room
G <number> <obj_vnum> <limit>           — give object to last loaded mob
E <number> <obj_vnum> <limit> <wear_loc> — equip object on last loaded mob
P <number> <obj_vnum> <limit> <container_vnum> — put object in container
D 0 <room_vnum> <door_dir> <door_state> — set door state
R 0 <room_vnum> <last_door>             — randomize exit directions
H 0 <container_vnum> <mob_count> <mob_vnum> — load mob in container object
S                                        — end of resets section
```

**Detailed descriptions:**

**M — Load Mobile:**
```
M 0 QQ10 5 QQ03
```
Loads mob `QQ10` in room `QQ03`. Up to `5` may exist worldwide simultaneously (limit).

**G — Give Object to Mobile:**
```
G 1 QQ40 -1
```
Gives 1 of object `QQ40` to the most recently loaded mob. `-1` limit = unlimited.
- `G` **must** immediately follow the `M` (or another `G`/`E`) for that mob
- If the `M` command hit its limit, the `G` object is not created

**E — Equip Object on Mobile:**
```
E 1 QQ50 -1 16
```
Equips 1 of object `QQ50` on the most recently loaded mob in wear slot `16` (wield). See Wear Location Values table below.

**O — Load Object in Room:**
```
O 0 QQ35 1 QQ41
```
Loads object `QQ35` in room `QQ41`, limit 1.

**P — Put Object in Container:**
```
P 1 QQ23 1 QQ30
```
Puts 1 of object `QQ23` into the most recently loaded container `QQ30`.
- The container must have been loaded first (with `O`)
- Works on the most recently loaded object with that container VNUM

**D — Set Door State:**
```
D 0 QQ10 3 2
```
In room `QQ10`, set exit direction `3` (west) to state `2` (locked).

**R — Randomize Exits:**
```
R 0 QQ55 4
```
In room `QQ55`, randomize exit directions 0 through 4 (5 directions shuffled). Do not combine with D command on the same room.

**H — Load Mob in Container:**
```
H 0 QQ70 3 QQ15
```
Loads mob `QQ15` inside container object `QQ70`. Must be followed by a `G` command. The container's object type must be a bottle/container.

**Limit `-1`:** Unlimited — the object/mob respawns at every reset with no cap.

**Comments:** Lines starting with `*` are comments.

---

### Wear Location Values (E command)

| Value | Name | Slot |
|---|---|---|
| -1 | WEAR_NONE | Not equipped (seldom useful) |
| 0 | WEAR_LIGHT | Light slot (torch, lantern) |
| 1 | WEAR_FINGER_L | Left finger |
| 2 | WEAR_FINGER_R | Right finger |
| 3 | WEAR_NECK_1 | Neck slot 1 |
| 4 | WEAR_NECK_2 | Neck slot 2 |
| 5 | WEAR_BODY | Body armor |
| 6 | WEAR_HEAD | Helm |
| 7 | WEAR_LEGS | Leggings |
| 8 | WEAR_FEET | Boots |
| 9 | WEAR_HANDS | Gloves |
| 10 | WEAR_ARMS | Sleeves/arm guards |
| 11 | WEAR_SHIELD | Shield |
| 12 | WEAR_ABOUT | Cloak/cape |
| 13 | WEAR_WAIST | Belt |
| 14 | WEAR_WRIST_L | Left wrist bracer |
| 15 | WEAR_WRIST_R | Right wrist bracer |
| 16 | WEAR_WIELD | Weapon wield slot |
| 17 | WEAR_HOLD | Held item slot |

---

### Door State Values (D command)

Last field in the `D` reset command.

| Value | State |
|---|---|
| 0 | Open |
| 1 | Closed |
| 2 | Locked |
| 3 | Pickproof (locked, cannot pick) |

---

## #SHOPS Section

### Shop Format

```
#SHOPS
<mob_vnum> <trade0> <trade1> <trade2> <trade3> <trade4> <buy%> <sell%> <open_hr> <close_hr> ; comment
0
```

| Field | Description |
|---|---|
| `mob_vnum` | VNUM of the mob who is the shopkeeper. All mobs of this VNUM become shopkeepers |
| `trade0–trade4` | Up to 5 item types the shopkeeper will **buy** from players (see Item Types for Shops). Use `0` for unused slots |
| `buy%` | Markup for players buying from shop. `100`=list price, `150`=50% markup. Should be ≥100 |
| `sell%` | Markdown for players selling to shop. `100`=list price, `75`=25% markdown. Should be ≤100 |
| `open_hr` | Hour shop opens (0–23) |
| `close_hr` | Hour shop closes (0–23). Use `0 23` for 24-hour shop |

Section ends with `0` on its own line.

**Example:**
```
#SHOPS
QQ00 2 3 4 10 0 105 15 0 23 ; The Wizard (buys scrolls, wands, staffs, furniture)
QQ01 0 0 0 0 0 110 100 0 23 ; The Baker (buys nothing)
QQ02 5 0 0 0 0 130 40 0 23  ; Weaponsmith (buys weapons)
0
```

**Notes:**
- The objects the shopkeeper **sells** are those given to it via `G` resets in `#RESETS`
- Objects sold TO the shopkeeper are kept for resale if no duplicate exists (but don't replenish)
- Shopkeeper mobs should have ACT flags `ABV` (SENTINEL + NOPURGE) and immunity flags `ABCD` minimum

---

### Item Types for Shops (trade values)

These are **different** from the object type numbers used in `#OBJECTS`. These are the shop's trade type indices:

| Value | Buys this type |
|---|---|
| 1 | Lights |
| 2 | Scrolls |
| 3 | Wands |
| 4 | Staffs |
| 5 | Weapons |
| 6 | Treasure |
| 7 | Armor |
| 8 | Potions |
| 9 | Clothing |
| 10 | Furniture |
| 11 | Trash |
| 12 | Containers |
| 13 | Drink containers |
| 14 | Keys |
| 15 | Food |
| 16 | Money |
| 17 | Boats |
| 23 | NPC Corpses |
| 24 | Pills |
| 25 | Maps |
| 26 | Scuba gear |

---

## #SPECIALS Section

### Specials Format

```
#SPECIALS
M <mob_vnum> <spec_function_name> ; optional comment
#$
```

One `M` line per mob/spec assignment. The `#$` line ends the file (not just this section).

**Example:**
```
#SPECIALS
M QQ00 spec_cast_mage    ; The Wizard
M QQ11 spec_executioner  ; The Watcher (guard)
M QQ12 spec_cast_adept   ; Healer at temple
M QQ60 spec_guard        ; City guards
M QQ61 spec_janitor      ; Janitors
#$
```

---

### Available Spec-Functions

**Warning:** Spec-functions add significant CPU load. Do not add spec-functions to large numbers of mobs.

| Function | Description |
|---|---|
| `spec_breath_any` | Randomly breathes one of the 6 breath weapons below |
| `spec_breath_acid` | Breathes acid |
| `spec_breath_fire` | Breathes fire |
| `spec_breath_frost` | Breathes frost/cold |
| `spec_breath_gas` | Breathes poisonous gas |
| `spec_breath_lightning` | Breathes lightning |
| `spec_breath_dispel` | Breathes dispel magic |
| `spec_cast_adept` | Healer; casts healing spells |
| `spec_cast_cleric` | Casts any cleric spell up to mob's level |
| `spec_cast_judge` | Casts general-purpose ammo and high explosive |
| `spec_cast_mage` | Casts any mage spell up to mob's level |
| `spec_cast_undead` | Casts undead spells (chill touch, vampiric touch, etc.) |
| `spec_psionic` | Casts psionic spells (best in ROOM_SILENT rooms) |
| `spec_executioner` | Attacks all players with Killer or Thief flags |
| `spec_fido` | Eats corpses |
| `spec_guard` | Attacks Killer/Thief-flagged players; assists victims being attacked |
| `spec_janitor` | Picks up corpses and objects lying in its room |
| `spec_poison` | Casts poison spell on opponents |
| `spec_thief` | Steals from players it encounters |
| `spec_mayor` | Peripatetic mayor behavior (wanders and locks gates etc.) |

---

## #$ End Marker

The last line of every area file is simply:

```
#$
```

This terminates the `#SPECIALS` section and ends the area file.

---

## Spell Slot Reference

Full list of spell names and their slot numbers for use in scroll, wand, staff, potion, and pill objects.

| Spell | Slot | Spell | Slot | Spell | Slot |
|---|---|---|---|---|---|
| acid blast | 70 | fireball | 26 | sanctuary | 36 |
| aid | 517 | fire shield | 522 | shield | 67 |
| animate parts | 547 | flamestrike | 65 | shocking grasp | 53 |
| armor | 1 | fly | 56 | skeletal hands | 527 |
| bless | 3 | force sword | 543 | sleep | 38 |
| blindness | 4 | frenzy | 504 | slow | 511 |
| blizzard | 520 | frost shield | 566 | spiritual hammer | 539 |
| burning hands | 5 | gate | 83 | stinking cloud | 552 |
| butcher | 547 | geyser | 538 | stone skin | 66 |
| call lightning | 6 | giant strength | 39 | summon | 40 |
| calm | 509 | harm | 27 | sunray | 541 |
| cancellation | 507 | haste | 502 | teleport | 2 |
| cause critical | 63 | haven | 554 | tentacles | 556 |
| cause light | 62 | heal | 28 | trap the soul | 530 |
| cause serious | 64 | heat metal | 514 | vampiric touch | 529 |
| chain lightning | 500 | holy word | 506 | vengeance | 532 |
| change sex | 82 | icicle | 521 | ventriloquate | 41 |
| charm person | 7 | identify | 45 | vortex | 536 |
| chill touch | 8 | infravision | 77 | water burst | 537 |
| color spray | 10 | invis | 29 | waterfall | 534 |
| cone of cold | 549 | know alignment | 58 | weaken | 68 |
| continual light | 57 | lightning bolt | 30 | word of recall | 42 |
| control weather | 11 | locate object | 31 | acid breath | 200 |
| create food | 12 | magic missile | 32 | fire breath | 201 |
| create spring | 80 | major globe | 526 | frost breath | 202 |
| create skeleton | 544 | mana convert | 565 | gas breath | 203 |
| create vampire | 546 | mass healing | 508 | lightning breath | 204 |
| create water | 13 | mass invis | 69 | death ray | 563 |
| create wraith | 545 | neutrality field | 560 | dispel breath | 524 |
| cure blindness | 14 | bewitch weapon | 548 | general purpose ammo | 401 |
| cure critical | 15 | earth travel | 528 | high explosive | 402 |
| cure disease | 501 | embalm | 567 | ghostly presence | 562 |
| cure light | 16 | enchant armor | 510 | shock sphere | 561 |
| cure nightmare | 519 | enchant weapon | 24 | shroud | 548 |
| detect evil | — | energy drain | 25 | evil eye | 540 |
| detect good | — | faerie fire | 72 | |
| faerie fog | 73 | | | |

To look up any spell not listed here, use the in-game command: `vnum spell <spell name>`

---

## Complete Area Template

Copy this template as a starting point for a new area. Replace `QQ` with your area prefix and fill in all fields.

```
#AREA   { 15 25 } YourName   Your Area Name~

#HELPS
0 $~

#MOBILES
#QQ01
guard soldier warrior~
a city guard~
A city guard stands watch here.
~
He eyes you with professional wariness.
~
human~
ABG JK -100 S
20 2 3d9+333 5d10+100 2d8+5 0
-4 -4 -4 0
CFIK AB 0 0
8 8 1 50
MH ABC M steel

#QQ02
shopkeeper merchant trader~
the weapon merchant~
A weapon merchant stands behind the counter.
~
The merchant carefully appraises potential customers.
~
human~
ABV DF 100 S
25 0 5d10+550 5d10+100 2d10+7 0
-7 -7 -7 0
IK ABCDLQ 0 0
8 8 1 1000
MH ABC M 0

#0

#OBJECTS
#QQ01
longsword blade sword~
a steel longsword~
A steel longsword lies here.~
steel~
5 ABG 0 AN
1 5 5 1 0
20 20 500 P

#QQ02
potion healing red~
a potion of cure critical~
A red potion sits here.~
glass~
10 G 0 A
20 15 0 0 0
20 2 200 P

#0

#ROOMS
#QQ00
Market Square~
The bustling market square forms the heart of the area. Merchants hawk
their wares from colorful stalls that line the cobblestone plaza. Exits
lead north to the keep and east to the residential district.
~
QQ 0 1
D0
Tall iron gates lead to the keep.
gate gates~
~
1 -1 QQ01
D1
A cobbled road leads east into the residential district.
~
~
0 -1 QQ02
S

#QQ01
Before the Keep Gates~
Imposing iron gates bar the way into the keep. Guards stand watch.
~
QQ 0 1
D2
A cobbled road leads back to the market.
~
~
0 -1 QQ00
S

#QQ02
Residential Road~
A quiet cobbled road winds through modest homes.
~
QQ 0 1
D3
The cobbled road leads west back to the market.
~
~
0 -1 QQ00
S

#0

#RESETS
*
* Guards
*
M 0 QQ01 3 QQ00                           The gate guard
E 1 QQ01 -1 16                            - wield longsword
*
* Shopkeeper
*
M 0 QQ02 1 QQ00                           The weapon merchant
G 1 QQ01 -1                               - longsword in stock
G 1 QQ01 -1                               - second longsword
*
* Objects
*
O 0 QQ02 3 QQ01                           potions near gate
S

#SHOPS
QQ02 5 0 0 0 0 130 40 0 23                ; Weapon merchant
0

#SPECIALS
M QQ01 spec_guard                         ; Gate guard
#$
```

---

## Design & Balance Guidelines

### Mob Balance
- **One or two boss mobs** per area is acceptable; the rest should be groupable near the area's recommended level range.
- **Boss mobs** should require a group rather than being soloable; compensate with exceptional equipment drops.
- Never create mobs that are both heavily immuned AND have high HP and strong attacks — balance immunity with lower HP.
- **Shopkeeper mobs** must be: SENTINEL (B), NOPURGE (V), immune to SUMMON+CHARM+MAGIC+WEAPON (ABCD at minimum).
- Check the HP/damage chart before submitting — mobs outside ±10% will likely be adjusted.
- For class-based mobs (mage, cleric, warrior, thief), apply the AC/HP adjustments from the chart notes.

### Object Balance
- **For every significant bonus there should be a balancing penalty:** e.g., +5 damroll AND -5 AC.
- Objects with strong applies (+5 to any stat) will be scrutinized.
- Weapon damage dice should follow the weapon damage chart.
- Armor values: use `-1` for level to let code auto-assign, or follow the AC column in the HP chart.
- Do not create objects stronger than the area level warrants.
- `ITEM_FLAGS2` items with `ADD_INVIS`, `ADD_FLY`, or `ADD_DETECT_INVIS` **require permission**.

### Room Design
- `ROOM_SAFE` rooms **require permission** — use very sparingly.
- `ROOM_DEATHTRAP` rooms **require permission** — every entrance must clearly hint at danger.
- `ROOM_NO_RECALL` rooms should be area-climax or boss rooms only — don't apply to an entire area.
- `ROOM_PET_SHOP` rooms **require permission**.
- Provide logical connectivity — all rooms should be reachable and exits should make geographic sense.
- Write a minimum of 3–5 sentences per room description.

### Reset Guidelines
- Limit numbers for common trash mobs can be 5–10; powerful or unique mobs should be limited to 1–3.
- Use `-1` limit sparingly — it means **infinite** respawn of that object/mob worldwide.
- Every mob that carries equipment should have `G` or `E` resets for that equipment.
- Comment your resets generously (`*`) — it makes debugging much easier.

### Naming & Style
- Short descriptions begin **lowercase** (e.g., `the orc warrior~` — because they appear as "An orc warrior walks in.").
- Room names are **Title Case** and concise.
- Room descriptions are written in second-person present tense ("You see..." or "The room is...").
- Tilde `~` always goes on a **separate line** when ending a multi-line block.
- Keep object keywords lowercase and comprehensive — players type these to interact with the object.

### Submission Checklist
- [ ] All vnums in your assigned range (no conflicts)
- [ ] Area file listed in `area/area.lst`
- [ ] Every room ends with `S`
- [ ] `#ROOMS`, `#MOBILES`, `#OBJECTS` sections end with `#0`
- [ ] `#RESETS` ends with `S`
- [ ] `#SHOPS` ends with `0`
- [ ] Area file ends with `#$`
- [ ] No mob is flagged with `ACT_TRAIN` or `ACT_PRACTICE` without permission
- [ ] No `ROOM_SAFE`, `ROOM_DEATHTRAP`, or `ROOM_PET_SHOP` without permission
- [ ] No `ITEM_FLAGS2` fly/invis/detect-invis items without permission
- [ ] All door key VNUMs use `-1` when no key exists (not `0`)
- [ ] Mob IMM flags include at minimum `AB` (SUMMON, CHARM) on all mobs
- [ ] Exit descriptions on all exits (even just a simple `~` on a blank line)
- [ ] Encoding saved as Latin-1 (not UTF-8)

---

*Document generated from the ToC wiki HTML files, source code (`merc.h`, `db.c`, `const.c`), and real area files. Last updated: 2025.*
