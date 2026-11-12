# ToC MUD Area Building Guide

**Comprehensive reference for creating `.are` files for the ToC (Times of Chaos) MUD.**  

> **An `.are` file is a token stream, not a line format.** `fread_letter`,
> `fread_number`, `fread_word` and `fread_string` all skip whitespace,
> newlines included, so the loader does not care where you break a line.
> `D0` and `D 0` are the same exit; an exit's description may begin on the
> same line as its number (`D3 too dark to tell`); a record header may carry
> trailing spaces (`#114 `) or its name alongside the vnum
> (`#24377 The White Queen's Chamber~`). All of those shapes are in the
> shipped world. Write new records in the ordinary layout described below,
> but any tool that *reads* area files has to accept every one of them --
> several did not, and content was deleted on the strength of their false
> negatives.
>
> `fread_flag` is the real trap: it has no handling for a minus sign, so a
> `-1` returns 0 *and* leaves the `-` unconsumed, shifting every field after
> it.
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
   - [How Immunity, Resistance And Vulnerability Work](#how-immunity-resistance-and-vulnerability-work)
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
   - [ROOM_AFFECTED_BY Details](#room_affected_by-details)
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

> **Cost is copper.** The cost field on an object's value line is counted in copper, not gold: a gold piece is 10000 and a silver is 100. `tools/costs_to_copper.py` converted the world in one pass and is kept for reference; new areas should be written in copper directly.

## Overview & File Structure

An area file (`.are`) is a plain-text file that defines all the content in one area of the game. All `.are` files must be listed in `area/area.lst` for the game to load them.

### How The Loader Reads Sections

`load_area_file` in `src/db.c` reads a `#`, then a section name, and
dispatches on it, until it reads `#$`. It accepts these sections, each as
often as it appears and in any order: `#AREA`, `#AREADATA`, `#HELPS`,
`#MOBILES`, `#OBJECTS`, `#ROOMS`, `#RESETS`, `#SHOPS`, `#SOCIALS` and
`#SPECIALS`. Any other name stops the boot with `Boot_db: bad section
name.` Every section is optional: the help files in `area.lst`
(`commands.are`, `skills.are` and the rest) hold only `#HELPS` and `#$`,
and `custom.are`, the builder workshop, is whatever online building last
saved into it.

Each section ends with its own terminator:

| Section | Ends with |
|---|---|
| `#AREA` | its one `~`-terminated string |
| `#AREADATA` | `End` |
| `#HELPS` | a help whose keyword is `$` (written `0 $~`) |
| `#MOBILES`, `#OBJECTS`, `#ROOMS` | `#0` |
| `#RESETS` | `S` |
| `#SHOPS` | `0` |
| `#SPECIALS` | `S` |
| the file | `#$` |

The order that matters is the order of *dependencies*, because some
sections look up records as they are read:

- `#ROOMS` and `#RESETS` belong to the most recent `#AREA` or `#AREADATA`
  header (`area_last`); without one the boot stops with `no #AREA seen
  yet`. Mobiles and objects carry no area pointer at all.
- `#RESETS` looks up the rooms, mobiles and objects it names, and a `D`
  reset needs the exit to exist and to be a door, so it must come after
  the records it names -- in this file or in a file listed earlier in
  `area.lst`.
- `#SHOPS` and `#SPECIALS` look up their keeper or mobile, so they come
  after the `#MOBILES` that defines it.
- Exits name destination rooms by vnum and are joined after every file
  has loaded, so an exit may lead into a later file.

The preferred layout for a new area -- the one every shipped area uses --
is:

```
#AREA
#MOBILES
#OBJECTS
#ROOMS
#RESETS
#SHOPS
#SPECIALS
#$
```

with an optional `#HELPS` after `#AREA`. An area built in game with ANEW
starts with `#AREADATA` instead of `#AREA` (see `load_areadata`).

Rules:
- Every **string field** ends with a tilde `~`, on the same line or on its own line.
- The `#$` marks the end of the entire area file.
- Vnums are decimal integers (see below). Every record header is `#` and a number: `#41000`.
- Lines starting with `*` in `#RESETS` and `#SPECIALS` are comments and are ignored.

### Encoding

All `.are` files use **Latin-1 (ISO-8859-1)** encoding. Do not save as UTF-8.

---

## Vnum Conventions & Naming

Each area is assigned a **block of vnums** -- a range of plain decimal
numbers such as 41000 to 41099. Every example in this guide uses that
block as a stand-in for yours; substitute your own numbers.

- Rooms, mobiles and objects are three separate namespaces: room 41000,
  mobile 41000 and object 41000 can all exist. Within one namespace a vnum
  must be unique across the whole world (`Load_mobiles: vnum N
  duplicated.` stops the boot).
- A vnum is a whole number from 1 to 1,000,000 (`MAX_VNUM` in `src/merc.h`).
  Vnums were 16-bit until 2026-11-11 and stopped at 32,767; an area may now
  use any number up to the ceiling. A record whose vnum lies outside it stops
  the boot with `Load_rooms: vnum N is outside 1 to 1000000.` (or
  `Load_mobiles`/`Load_objects`). `0` still ends a section.
- Keep each kind in a logically grouped run inside your block (for
  example rooms from 41000, mobiles from 41000, objects from 41000), and
  check `../merc --check-area` and `scripts/area_lint.py` for collisions
  before submitting.

---

## #AREA Section

```
#AREA   { min_level max_level } Author   Area Name~
```

`load_area` reads everything after `#AREA` up to the tilde as **one
string**, the area's name as AREAS and the dashboard show it; the parts
below are a convention of that string, not separate fields.

**Fields:**
- `{ min_level max_level }` — Suggested level range for players (e.g., `{ 5 15 }`). Use `ALL` or `{ 0 100 }` for a universal area. Code that shows an area name goes through `area_shown_name()` so the braces are not taken for a colour code.
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
- `level` — Minimum trust to read this help. Negative level hides keywords (useful for opening screens). A topic for players is level 0: a level from 1 to 59 hides it from every mortal below it, remorts included (`tests/test_help_keywords.py`).
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
ACT_FLAGS [ACT_FLAGS2] AFF_FLAGS [AFF_FLAGS2] ALIGNMENT S
level hitroll HitDice ManaDice DamDice dam_type
ac_pierce ac_bash ac_slash ac_exotic
OFF_FLAGS [OFF_FLAGS2] IMM_FLAGS [IMM_FLAGS2] RES_FLAGS [RES_FLAGS2] VULN_FLAGS [VULN_FLAGS2]
start_pos default_pos sex wealth
form parts SIZE material
```

A bracketed `[..._FLAGS2]` token is present **only** when the field
before it contains `Z` (see Flag Encoding); otherwise leave it out
entirely, or every field after it shifts.

**Field-by-field breakdown:**

| Field | Description |
|---|---|
| `#VNUM` | The mob's unique virtual number (e.g., `#41010`) |
| `keywords~` | Space-separated words players type to interact with this mob |
| `Short description~` | What shows in "XXX is standing here." — begins lowercase |
| `Long description~` | Multi-line text shown in room description. Ends with `~` alone on a line |
| `Look-at description~` | Text shown when a player specifically `look`s at the mob |
| `race~` | Mob's race string (see Races table below); matched by prefix, unknown races read as `unique` |
| `ACT_FLAGS` | Letter-flag bitmask (see ACT Flags table); the race's own ACT bits and `ACT_IS_NPC` are added |
| `AFF_FLAGS` | Letter-flag bitmask (see AFF Flags table); the race's own AFF bits are added |
| `ALIGNMENT` | Integer from -1000 (evil) to +1000 (good). 0 = neutral. |
| `S` | The letter `S` for an ordinary mobile. `M` instead means a `{ ... }` block of `A <level> <room msg>~ <victim msg>~` actions follows the material (`read_m_mob_extras`); anything else stops the boot |
| `level` | Mob's level (1–60+) |
| `hitroll` | Bonus to hit rolls; raised to at least `level/2` on load |
| `HitDice` | HP formula: `NdM+X` (e.g., `5d10+550`) |
| `ManaDice` | Mana formula: `NdM+X` (e.g., `10d20+100`) |
| `DamDice` | Damage per hit: `NdM+X` (e.g., `2d10+7`); the bonus is raised to at least `3*level/4` on load |
| `dam_type` | Bare-hand attack, an index into `attack_table` (see Damage Types table) |
| `ac_pierce` | Armor class vs pierce attacks (lower = better); capped at `100 - 6*level` on load |
| `ac_bash` | Armor class vs bash attacks (same cap) |
| `ac_slash` | Armor class vs slash attacks (same cap) |
| `ac_exotic` | Armor class vs exotic/magic attacks (same cap) |
| `OFF_FLAGS` | Letter-flag bitmask: offensive capabilities (plus the race's) |
| `IMM_FLAGS` | Letter-flag bitmask: immunities (plus the race's) |
| `RES_FLAGS` | Letter-flag bitmask: resistances (see RES Flags for the arithmetic) |
| `VULN_FLAGS` | Letter-flag bitmask: vulnerabilities (see VULN Flags for the arithmetic) |
| `start_pos` | Position when first loaded (integer; see Positions) |
| `default_pos` | Position it returns to after combat (integer; see Positions) |
| `sex` | 0=neuter, 1=male, 2=female |
| `wealth` | `0` rolls the coin a mobile of its level carries; any other figure is split across the denominations and capped at three times the most the level roll gives (`mob_index_set_wealth`) |
| `form` | Body form flags (letters; see FORM Flags); the race's are added |
| `parts` | Body parts flags (letters; see PARTS Flags); the race's are added |
| `SIZE` | One letter: T/S/M/L/H/G (see Sizes); anything else is medium |
| `material` | One **word**, no tilde (`fread_word`), e.g. `flesh` or `0`; see Materials |

**Example mob:**
```
#41010
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

Lower-case letters are bits 26 and up: `a` = bit 26, `b` = bit 27, and so
on (`flag_convert`). The tables below write such a flag as its lower-case
letter; `src/merc.h` names the same bit `aa`, `bb`, ... A flag field may
also be written as a decimal number, or as numbers and letters joined by
`|` (`8|4096`). It may never be negative: `fread_flag` has no minus sign,
and `-1` reads as 0 and leaves the `-` behind for the next field.

Some fields have a second word. Where the table says `Z` is the
`..._FLAGS2` marker, putting `Z` in the field tells the loader that a
second flag token follows immediately; without `Z` that token must not be
written. The extension exists for ACT, AFF, OFF, IMM, RES and VULN on
mobiles, for an object's extra flags, and for a room's flags:
- ACT FLAGS: include `Z` in the ACT_FLAGS field → next token is ACT_FLAGS2 letters
- AFF FLAGS: include `Z` in AFF_FLAGS → next token is AFF_FLAGS2 letters

FORM and PARTS have no extension: there `Z` is an ordinary bit
(`FORM_DRAGON`).

---

### ACT Flags

First field on the "ACT_FLAGS AFF_FLAGS ALIGNMENT S" line. Names are the
`#define`s in `src/merc.h`; `tests/test_area_guide.py` holds every table
of letters in this guide to them.

| Flag | Letter | Description |
|---|---|---|
| ACT_IS_NPC | A | Set on every mobile by the loader whether written or not |
| ACT_SENTINEL | B | Mob stays in its room (does not wander) |
| ACT_SCAVENGER | C | Mob picks up objects from the ground |
| ACT_IS_HEALER | D | Mob is a healer (with spec_cast_adept); protected from attack |
| ACT_GAIN | E | Skill trainer for GAIN; protected from attack (`is_protected_npc`) |
| ACT_AGGRESSIVE | F | Mob attacks players it sees |
| ACT_STAY_AREA | G | Mob cannot wander outside its area |
| ACT_WIMPY | H | Mob flees when HP drops too low |
| ACT_PET | I | Runtime: set on a pet-shop mobile when it is loaded -- do not set |
| ACT_TRAIN | J | Mob can train players (**requires permission**) |
| ACT_PRACTICE | K | Mob can practice skills with players (**requires permission**) |
| ACT_UPDATE_ALWAYS | L | Mob keeps acting (wandering, specials) while its area is empty |
| ACT_NOSHOVE | M | Mob cannot be shoved |
| ACT_B_BOY | N | Unused; no code reads it |
| ACT_UNDEAD | O | Mob has basic undead abilities |
| ACT_CLERIC | Q | Mob has basic cleric abilities |
| ACT_MAGE | R | Mob has basic mage abilities |
| ACT_THIEF | S | Mob has basic thief abilities (steal) |
| ACT_WARRIOR | T | Mob has basic warrior abilities |
| ACT_NOALIGN | U | Killing mob does not affect player alignment (**use sparingly**) |
| ACT_NOPURGE | V | A room-wide PURGE leaves the mob; PURGE naming it still removes it |
| ACT_MOUNTABLE | W | Mob may be ridden (requires ITEM_SADDLE) |
| ACT_NOKILL | X | Mob vanishes if a player attacks it (for charmed pets) |
| ACT_QUESTM | Y | Quest master; protected from attack |
| ACT_FLAGS2 | Z | Signals that ACT_FLAGS2 letters follow in the next token |

**ACT_FLAGS2** (the token after a `Z`):

| Flag | Letter | Description |
|---|---|---|
| ACT2_NO_TPORT | A | A teleport room (`ROOM_TELEPORT`) does not carry this mobile away |
| ACT2_LYCANTH | B | Lycanthrope -- **inert**: `LYCANTHROPY_ENABLED` is 0 in `merc.h`, so the infection code never runs |
| ACT2_REPAIR | C | Mob offers REPAIR to players in its room |

Lycanthropy was switched off because catching it took no saving throw and
had no cure; the machinery is kept, and setting `LYCANTHROPY_ENABLED` to 1
would bring it back. Do not build content that depends on it.

**Tip:** `A` is added by the loader anyway. Shopkeepers should have `B` (SENTINEL) and `V` (NOPURGE).

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
| AFF_SANCTUARY | H | Mob has sanctuary |
| AFF_FAERIE_FIRE | I | Mob has faerie fire (easier to hit) |
| AFF_INFRARED | J | Mob can see in the dark (infravision); a reset also sets it on a mobile loaded into a dark room |
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

**AFF_FLAGS2** (the token after a `Z`). Dark vision, detect good, the two
shields and stealth are reasonable on a prototype; the rest are the marks
of spells and skills, listed so the letters are known, and are not for
area files.

| Flag | Letter | Description |
|---|---|---|
| AFF2_DARK_VISION | A | Mob can see clearly in the dark |
| AFF2_DETECT_GOOD | B | Mob can detect good |
| AFF2_HOLD | C | No effect: nothing in the game reads it |
| AFF2_FLAMING_HOT | D | Fire shield: burns whoever strikes the mob |
| AFF2_FLAMING_COLD | E | Frost shield: chills whoever strikes the mob |
| AFF2_PARALYSIS | F | No effect: nothing in the game reads it |
| AFF2_STEALTH | G | Stealthed: unseen without holylight |
| AFF2_STUNNED | H | Stunned by a skill; loses its actions -- spell/skill effect |
| AFF2_NO_RECOVER | I | Does not regenerate (nerve damage, nightmare) -- spell/skill effect |
| AFF2_FORCE_SWORD | J | Force sword's extra blows -- spell effect |
| AFF2_GHOST | K | Ghost form -- spell effect |
| AFF2_MADNESS | L | Cause madness -- spell effect |
| AFF2_DIVINE_PROT | M | Divine protection -- spell effect |
| AFF2_SHADOWMELD | N | Shadowmeld -- skill effect |

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
| ASSIST_GUARD | T | Mob assists guard-type mobs |
| ASSIST_VNUM | U | Mob assists mobs with the same VNUM |
| OFF_SUMMONER | V | Mob may summon aggressive mobs to assist it |
| NEEDS_MASTER | W | Autoset for pets — do not set manually |
| OFF_ATTACK_DOOR_OPENER | X | Mob attacks whoever opens a door into or out of its room |
| OFF_FLAGS2 | Z | Signals OFF_FLAGS2 letters follow in next token |

**OFF_FLAGS2** (the token after a `Z`):

| Flag | Letter | Description |
|---|---|---|
| OFF2_HUNTER | A | Mob hunts the PC until one of them dies |

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
| IMM_WIND | T | Immune to wind damage |
| IMM_FLAGS2 | Z | Signals IMM_FLAGS2 letters follow in next token |

**IMM_FLAGS2:** none are defined; a `Z` here only makes the loader read
one more token.

**Shopkeepers** should typically be flagged `ABCD` (IMM_SUMMON, IMM_CHARM, IMM_MAGIC, IMM_WEAPON) plus LQRP to prevent exploitation.

---

### How Immunity, Resistance And Vulnerability Work

`check_immune()` in `src/handler.c` gives a blow one verdict, and
`blow_immunity_cut()` in `src/combat_rules.c` applies it, in integer
arithmetic:

| Verdict | Damage taken | 30 becomes | 31 becomes |
|---|---|---|---|
| Immune | `0` | 0 | 0 |
| Resistant | `dam - dam/3` (about two thirds) | 20 | 21 |
| Vulnerable | `dam + dam/2` (about one and a half times) | 45 | 46 |

How the verdict is reached:

- A bash, pierce or slash blow first asks the WEAPON flags (`IMM_WEAPON`,
  then `RES_WEAPON`, then `VULN_WEAPON`); every other damage type asks the
  MAGIC flags the same way.
- Then the flag for the blow's own type (`IMM_FIRE`, `RES_FIRE`,
  `VULN_FIRE`, ...) is asked, and if any of the three is set it replaces
  the first answer -- immunity first, then resistance, then
  vulnerability. So a mob with `VULN_WEAPON` and `RES_SLASH` resists
  slashing blows.
- `CHARM` and `SUMMON` are not damage types: the charm and summon spells
  read those bits themselves.

Exceptions that read the flags their own way rather than through the
table above: plague's spread and the disease tick (`DAM_DISEASE`),
energy drain (`DAM_NEGATIVE`), and the psionic mental drains
(`DAM_MENTAL`, `magic2.c`). Sanctuary, protection and the elemental
shields are separate reductions applied before the verdict.

---

### RES (Resistance) Flags

Third field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.
A resistant mob takes `dam - dam/3` from that type (see above).

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
| RES_WIND | T | Wind |
| RES_FLAGS2 | Z | Signals RES_FLAGS2 follow |

**RES_FLAGS2:** none are defined.

---

### VULN (Vulnerability) Flags

Fourth field on the "OFF_FLAGS IMM_FLAGS RES_FLAGS VULN_FLAGS" line.
A vulnerable mob takes `dam + dam/2` from that type (see above).

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
| VULN_WIND | T | Wind |
| VULN_IRON | U | Iron weapons (elves carry it from the race table) |
| VULN_WOOD | X | Wooden weapons |
| VULN_SILVER | Y | Silver weapons |
| VULN_FLAGS2 | Z | Signals VULN_FLAGS2 follow |

`VULN_IRON`, `VULN_WOOD` and `VULN_SILVER` are recorded, and shown by STAT
and the race table, but nothing in a fight reads them today:
`check_immune` has no iron, wood or silver damage type and no weapon
material is consulted. There is no `VULN_FLAGS2` flag; iron is
`VULN_IRON` in the first field.

**Common patterns:**
- Undead: `IMM_POISON+DISEASE`, `VULN_HOLY+LIGHT`
- Fire-based: `IMM_FIRE`, `VULN_COLD+DROWNING`
- Demons/evil: `IMM_FIRE+NEGATIVE`, `VULN_HOLY`

---

### FORM Flags

First field on the "form parts SIZE material" line. Describes the mob's
body form; the race's form is added to whatever is written. Use `0` if
none apply. There is no extension token: `Z` is `FORM_DRAGON`.

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
| FORM_SNAKE | Y | Mob is snake-shaped |
| FORM_DRAGON | Z | Mob is dragon-shaped |
| FORM_AMPHIBIAN | a | Mob is an amphibian |
| FORM_FISH | b | Mob is a fish |
| FORM_COLD_BLOOD | c | Mob is cold-blooded |

---

### PARTS Flags

Second field on the "form parts SIZE material" line. Describes body parts present on the mob.
The race's parts are added to whatever is written, so `0` gives the race's body. Set explicitly for unusual mobs.

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
| PART_TUSKS | Y | Has tusks |

**Standard humanoid:** `ABCDEFGHIJK` (head, arms, legs, heart, brains, guts, hands, feet, fingers, ear, eye) -- one token, no space.

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

The names `race_table` in `src/const.c` holds (a race is matched by
prefix, and a name that matches none reads as `unique`):

| Race | Race | Race | Race | Race |
|---|---|---|---|---|
| unique | human | elf | dwarf | hobbit |
| saurian | bat | bear | cat | centipede |
| dog | doll | dragon | fido | fish |
| fox | giant | goblin | head | hobgoblin |
| horse | insect | kobold | lizard | modron |
| orc | pig | plant | rabbit | school monster |
| snake | song bird | tree | troll | undead |
| vampire | water fowl | wolf | wyvern | |

**Note:** The race does not have to match the mob's appearance. An ogre mob can have race "human". The race adds its own ACT, AFF, OFF, IMM, RES, VULN, form and parts bits to the ones written. Use `unique` for mobs that don't fit any category.

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

Used for `dam_type` (mob's bare-hand attack) and a weapon's `value3`: an index into `attack_table` in `src/const.c`, which names the blow and gives its damage type. `tests/test_area_guide.py` holds this table to it.

| Value | Name | Type |
|---|---|---|
| 0 | Hit | Bash (no type of its own; `one_hit` reads it as bash) |
| 1 | Slice | Slash |
| 2 | Stab | Pierce |
| 3 | Slash | Slash |
| 4 | Whip | Slash |
| 5 | Claw | Slash |
| 6 | Blast | Bash |
| 7 | Pound | Bash |
| 8 | Crush | Bash |
| 9 | Grep | Slash |
| 10 | Bite | Pierce |
| 11 | Pierce | Pierce |
| 12 | Suction | Bash |
| 13 | Beating | Bash |
| 14 | Digestion | Acid |
| 15 | Charge | Bash |
| 16 | Slap | Bash |
| 17 | Punch | Bash |
| 18 | Wrath | Energy |
| 19 | Magic | Energy |
| 20 | Divine Power | Holy |
| 21 | Cleave | Slash |
| 22 | Scratch | Pierce |
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

Without the `ITEM_FLAGS2` extension -- the ordinary case:

```
#VNUM
keywords~
Short name (shown in inventory, room)~
Long description (seen lying in room).~
material~
<item_type> <ITEM_FLAGS> <WEAR_FLAGS>
<value0> <value1> <value2> <value3> <value4>
<level> <weight> <cost> <condition>
```

With it -- `ITEM_FLAGS` contains `Z`, so one more flag token follows it:

```
<item_type> <ITEM_FLAGS-with-Z> <ITEM_FLAGS2> <WEAR_FLAGS>
```

`load_objects` reads the `ITEM_FLAGS2` token **only** when `ITEM_FLAGS`
has `Z` in it. Writing a `0` placeholder without the `Z` makes the loader
take that `0` for the wear flags, the real wear flags for value0, and
shifts every field after it; there is no "put 0 if unused" form.

After the condition letter come any number of optional trailing records,
in any order, until a letter that is none of them:

```
E
<extra-desc-keywords>~
<extra description text>
~
A
<apply_type> <apply_value>
F
A <apply_type> <apply_value> <affect bits>
T
<room message>~
<wearer message>~
```

- `E` adds an extra description (unlimited).
- `A` adds a bonus or penalty while worn (unlimited); see Apply Types.
- `F` is ROM's affect-bit record: an apply plus `AFF_` bits granted while
  worn (the Master Sword's haste). Only `F A ...` is understood.
- `T` adds a wear message (see Item Wear Message below).

**Example weapon object:**
```
#41040
sword underworld~
The Sword of the Underworld~
A large, dark sword of solid obsidian gleams evilly here.~
adamantite~
5 ABCEJL AN
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
- Line 1 (`5 ABCEJL AN`): item type=5 (weapon), flags=ABCEJL (no `Z`, so no flags2 token), wear flags=AN (TAKE + WIELD)
- Line 2 (`1 11 6 6 DE`): weapon class=1 (sword), 11 dice of 6 sides, attack type=6 (blast), weapon flags=DE (SHARP+VORPAL)
- Line 3 (`50 30 35000 P`): level=50, weight=30, cost=35000 copper, condition=P (perfect)

The same sword with the second flag word -- here `ITEM2_NOSTEAL` (`J`) --
gains a `Z` and one token:

```
5 ABCEJLZ J AN
```

The values line is read with `fread_flag`, so each value may be a number
or letters (weapon flags, container flags) but **never negative**: `-1`
reads as 0 and shifts the rest of the record. Write `999` for an endless
light, for example, not `-1`.

The section ends with `#0` on its own line after the last object.

---

### Object Types

Used as the first number on the type/flags/wear line (`ITEM_*` in `merc.h`).

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
| 11 | ITEM_CLOTHING | Clothing (no armour value) | wear |
| 12 | ITEM_FURNITURE | Static prop, no interaction | — |
| 13 | ITEM_TRASH | Junk | — |
| 15 | ITEM_CONTAINER | Container for items | put/get |
| 17 | ITEM_DRINK_CON | Drink container | drink/fill |
| 18 | ITEM_KEY | Key for doors/containers (dropped when its holder quits) | unlock |
| 19 | ITEM_FOOD | Food | eat |
| 20 | ITEM_MONEY | A pile of coins | get |
| 22 | ITEM_BOAT | Boat (cross WATER_NOSWIM) | carry |
| 23 | ITEM_CORPSE_NPC | NPC corpse -- made by the game | — |
| 24 | ITEM_CORPSE_PC | Player corpse -- made by the game | — |
| 25 | ITEM_FOUNTAIN | Fountain (endless water) | drink/fill |
| 26 | ITEM_PILL | Pill with spells | eat |
| 27 | ITEM_PROTECT | No special behaviour; only named | — |
| 28 | ITEM_MAP | Map (shows ASCII map on look) | look |
| 29 | ITEM_SCUBA_GEAR | Breathing gear for underwater | wear |
| 30 | ITEM_PORTAL | Portal to another room | enter |
| 31 | ITEM_MANIPULATION | Object with interactive trigger | push/pull/flip/etc. |
| 32 | ITEM_CASTLE_RELIC | A castle's relic -- staff-placed | — |
| 33 | ITEM_SADDLE | Saddle (needed to mount mobs) | wear |
| 34 | ITEM_HERB | Herb for BREW and CONCOCT -- scattered by the game | — |
| 35 | ITEM_SPELL_COMPONENT | Spell component for crafting -- scattered by the game | — |
| 36 | ITEM_SOUL_CONTAINER | Holds a trapped soul (trap the soul) | — |
| 37 | ITEM_ACTION | Object that triggers an event when worn | wear |
| 38 | ITEM_CAKE | Training food: eaten for trains | eat |

---

### Object Flags (ITEM_FLAGS)

Second field on the flags line. Combined letter bitmask.

| Flag | Letter | Description |
|---|---|---|
| ITEM_GLOW | A | Shows (Glowing); visible in the dark; helps enchanting |
| ITEM_HUM | B | Shows (Humming) |
| ITEM_DARK | C | No effect: only named by STAT and the builder |
| ITEM_LOCK | D | No effect: only named by STAT and the builder (a container's lock is in its values) |
| ITEM_EVIL | E | Red aura to detect evil; pair with ITEM_ANTI_GOOD |
| ITEM_INVIS | F | Item is invisible; requires detect invis to see |
| ITEM_MAGIC | G | Item shows as magical with detect magic |
| ITEM_NODROP | H | Item cannot be dropped (cursed-like) |
| ITEM_BLESS | I | Blessed; eases enchanting and remove curse |
| ITEM_ANTI_GOOD | J | Zaps good-aligned characters, forcing them to drop it |
| ITEM_ANTI_EVIL | K | Zaps evil-aligned characters, forcing them to drop it |
| ITEM_ANTI_NEUTRAL | L | Zaps neutral-aligned characters, forcing them to drop it |
| ITEM_NOREMOVE | M | Cannot be un-worn once equipped (cursed-like) |
| ITEM_INVENTORY | N | Shop stock -- see below (**use only with permission**) |
| ITEM_NOPURGE | O | A room-wide PURGE leaves it (fountains, pits); PURGE naming it still removes it |
| ITEM_ROT_DEATH | P | Crumbles when its carrier dies (given a timer in the corpse) |
| ITEM_VIS_DEATH | Q | Unseen until its carrier dies; the corpse shows it |
| ITEM_METAL | R | Metal: worn, it cuts the chance of SNEAK and STEALTH |
| ITEM_BOUNCE | S | Randomly teleports room-to-room within area |
| ITEM_TPORT | T | Randomly teleports area-to-area |
| ITEM_NOIDENTIFY | U | Immune to identify spell |
| ITEM_NOLOCATE | V | Immune to locate object spell |
| ITEM_RACE_RESTRICTED | W | Only wearable by the races its ITEM_FLAGS2 `*_ONLY` bits name |
| ITEM_ADD_AFFECT | X | Worn, grants the ITEM2_ADD_* affects (needed for them to work) |
| ITEM_EMBALMED | Y | Set by EMBALM on a corpse -- do not set |
| ITEM_FLAGS2 | Z | Signals ITEM_FLAGS2 letters follow in the next token |
| ITEM_DAMAGED | a | Runtime: damaged armour (heat, acid, dents) -- do not set |
| ITEM_HEATED | b | Runtime: heated by heat metal -- do not set |

**ITEM_INVENTORY** is a shopkeeper's endless stock, not "uses no inventory
slot". A shopkeeper's `G` items get it at every reset; BUY then hands over
a fresh copy and the shelf keeps the original. `obj_to_char` clears it the
moment anything reaches a player (bought, picked up or given), and
`make_corpse` destroys a mobile's `ITEM_INVENTORY` items rather than drop
them, so a shopkeeper never spills his shelves. Carrying weight and count
are unaffected: `get_obj_number` counts every object but coins.

---

### Item Flags 2 (ITEM_FLAGS2)

The token after `ITEM_FLAGS`, present only when `ITEM_FLAGS` has `Z`.

| Flag | Letter | Description |
|---|---|---|
| ITEM2_HUMAN_ONLY | A | Only wearable by humans (with ITEM_RACE_RESTRICTED) |
| ITEM2_ELF_ONLY | B | Only wearable by elves (with ITEM_RACE_RESTRICTED) |
| ITEM2_DWARF_ONLY | C | Only wearable by dwarves (with ITEM_RACE_RESTRICTED) |
| ITEM2_HALFLING_ONLY | D | Only wearable by halflings (with ITEM_RACE_RESTRICTED) |
| ITEM2_SAURIAN_ONLY | E | Only wearable by saurians (with ITEM_RACE_RESTRICTED) |
| ITEM2_ADD_INVIS | F | Bestows invisibility when worn, with ITEM_ADD_AFFECT (**requires permission**) |
| ITEM2_ADD_DETECT_INVIS | G | Bestows detect invisible when worn, with ITEM_ADD_AFFECT (**requires permission**) |
| ITEM2_ADD_FLY | H | Bestows fly when worn, with ITEM_ADD_AFFECT (**requires permission**) |
| ITEM2_NO_CAN_SEE | I | A container whose contents cannot be seen |
| ITEM2_NOSTEAL | J | Cannot be stolen |
| ITEM2_NO_TPORT | K | Teleport rooms do not carry it; telekinesis will not fetch it |

---

### Wear Flags

Last field on the flags line.

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

Fifth value in the weapon values line (the `<weapon type>` flags field). Letter bitmask. The effects are in `one_hit` in `src/fight.c`.

| Flag | Letter | Description |
|---|---|---|
| WEAPON_FLAMING | A | +10% damage, and a bash/pierce/slash blow becomes fire |
| WEAPON_FROST | B | +10% damage, and a bash/pierce/slash blow becomes cold |
| WEAPON_VAMPIRIC | C | +10% damage; the wielder drinks a share of what the blow really takes |
| WEAPON_SHARP | D | Now and then (skill/8 percent) a blow bites deep for double damage |
| WEAPON_VORPAL | E | Rarely (skill/20 percent) a blow shears for triple damage |
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
If a value is unused, use `0` -- never leave it blank, and never write a
negative number (see Object Format).

| Type | value0 | value1 | value2 | value3 | value4 |
|---|---|---|---|---|---|
| ITEM_LIGHT | unused | unused | hours of light (`999` = endless; `create_object` makes it -1) | unused | unused |
| ITEM_SCROLL | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_WAND | spell level | max charges | current charges | spell slot | unused |
| ITEM_STAFF | spell level | max charges | current charges | spell slot | unused |
| ITEM_WEAPON | weapon class | # dice | die size | attack type (`attack_table` index) | weapon type flags |
| ITEM_TREASURE | unused | unused | unused | unused | unused |
| ITEM_ARMOR | pierce AC | bash AC | slash AC | magic AC | unused |
| ITEM_POTION | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_CLOTHING | unused (no armour: `apply_ac` counts only ITEM_ARMOR) | unused | unused | unused | unused |
| ITEM_FURNITURE | unused | unused | unused | unused | unused |
| ITEM_TRASH | unused | unused | unused | unused | unused |
| ITEM_CONTAINER | weight capacity | container flags | key VNUM (`0` none) | unused | trap kind, set by the game when CONT_TRAPPED |
| ITEM_DRINK_CON | liquid capacity | current qty | liquid type (0-15) | poisoned if non-zero | `1` = never runs dry |
| ITEM_KEY | unused | unused | unused | unused | unused |
| ITEM_FOOD | hours of food satisfaction | unused | unused | poisoned if non-zero | `1` = never runs out |
| ITEM_MONEY | number of coins | coin type: 0 copper, 1 silver, 2 gold, 3 platinum | unused | unused | unused |
| ITEM_BOAT | unused | unused | unused | unused | unused |
| ITEM_FOUNTAIN | unused | unused | unused | unused | unused |
| ITEM_PILL | spell level | spell slot 1 | spell slot 2 | spell slot 3 | unused |
| ITEM_MAP | unused | unused | unused | unused | unused |
| ITEM_PORTAL | portal type | to_room VNUM | timer ticks | closeable/lockable | key VNUM |
| ITEM_MANIPULATION | manip type | to_room VNUM | door direction | object state | `9` = acts on its own room |
| ITEM_SADDLE | unused | unused | unused | unused | unused |
| ITEM_ACTION | action type | unused | poison strength (type 3) | unused | unused |

**Notes:**
- `spell level` is the *casting level* of the spell, not the reader's level
- Use `vnum spell <spell name>` in-game to get spell slot numbers, or see [Spell Slot Reference](#spell-slot-reference); the loader turns slots into skill numbers
- Scrolls, potions, and pills can have up to 3 spells; use `0` for unused spell slots
- Armour values are **positive** and higher is better: `apply_ac` takes each value off the wearer's armour class, three times over on the body and twice on the head, legs and about-body slots. With object level `-1`, `create_object` rolls the first three from the level the object is made at
- A drink container's liquid comes from `value2`; the drink is poisoned by a non-zero `value3`, never by the liquid's name
- A fountain's values are not read: DRINK from it quenches thirst outright, and FILL from it fills a container with water
- Set `<obj level>` to `-1` to have the game assign level based on the mob carrying it

**Portal types:**
| Value | Behavior |
|---|---|
| 1 | Hall of Heroes-style; to_room and timer unused |
| 4 | Crystal ball; timer optional |
| 5 | Teleport-pad style (berry→smurf, clown→froboz) |
| 6 | Required-item portal; `value[4]` is a carried object vnum (`0` means no requirement) |

**Manipulation types:**
| Value | Type | Value | Type |
|---|---|---|---|
| 1 | Flip | 6 | Climb Up |
| 2 | Move | 7 | Climb Down |
| 3 | Pull | 8 | Crawl |
| 4 | Push | 9 | Jump |
| 5 | Turn | — | — |

**Action item types** (fired when the item is worn, `equip_char`):
| Value | Type | Effect |
|---|---|---|
| 1 | Recall | Sends the wearer to the Temple and destroys the item |
| 2 | Death | Kills the wearer |
| 3 | Poison | Poisons the wearer (strength from `value2`, no save) and destroys the item |

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

Used as `value2` on ITEM_DRINK_CON's values line. The names are
`liq_table` in `src/const.c`. Each sip (3 to 10 units) changes the
drinker's drunkenness and thirst by the amount times the liquid's figure;
`do_drink` reads only those two of the table's three columns, so no
liquid feeds you.

| Value | Liquid | Drunk per unit | Thirst per unit |
|---|---|---|---|
| 0 | water | 0 | 10 |
| 1 | beer | 3 | 5 |
| 2 | wine | 5 | 5 |
| 3 | ale | 2 | 5 |
| 4 | dark ale | 1 | 5 |
| 5 | whisky | 6 | 4 |
| 6 | lemonade | 0 | 8 |
| 7 | firebreather | 10 | 0 |
| 8 | local specialty | 3 | 3 |
| 9 | slime mold juice | 0 | -8 |
| 10 | milk | 0 | 6 |
| 11 | tea | 0 | 6 |
| 12 | coffee | 0 | 6 |
| 13 | blood | 0 | -1 |
| 14 | salt water | 0 | -2 |
| 15 | cola | 0 | 5 |

A negative thirst figure makes the drinker thirstier. Past 10
drunkenness the drinker is told they are drunk and cannot drink more;
past 25 they slump to resting. A value outside 0 to 15 is logged as a
bug and the drink is turned into water. Poison is `value3`, whatever the
liquid.

---

### Object Condition

Fourth field on the `<level> <weight> <cost> <condition>` line.

| Letter | Condition |
|---|---|
| P | Perfect (100) |
| G | Good (90) |
| A | Average (75) |
| W | Worn (50) |
| D | Damaged (25) |
| B | Badly damaged (10) |
| R | Ruined (0) |

Any other letter reads as perfect. Most objects use `P` (Perfect).

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

A `T` record may come anywhere among the trailing records.

---

### Materials

The material is a name, read with `material_lookup()` against the 20
names in `material_type` (`src/handler.c`); a name that begins none of
them is `unknown`. An object's material is a `~`-terminated string; a
mobile's is a single word with no tilde.

| Material | Material | Material | Material |
|---|---|---|---|
| adamantite | brass | bronze | cloth |
| copper | food | glass | gold |
| herb | iron | leather | paper |
| pill | silver | spell component | steel |
| stone | vellum | wood | unknown |

The material is descriptive: STAT, OSHOW and the builder show it, and
nothing in the game changes behaviour by it, with one cosmetic exception
-- a mobile whose material is the first name, `adamantite` (or an empty
word), may get the "splatters blood on your armor" death cry. What an
object *does* comes from its item type: food is eaten because it is
`ITEM_FOOD`, pills because they are `ITEM_PILL`, coins are `ITEM_MONEY`.
Iron, silver and wood do not reach a mobile's iron, silver or wood
vulnerability (see VULN Flags).

---

## #ROOMS Section

### Room Format

```
#VNUM
Room Name~
Multi-line room description.
Can span many lines.
~
<number> <ROOM_FLAGS> [<ROOM_FLAGS2>] <sector_type>
[<to_room> <speed> <visible>          -- only with ROOM_RIVER (E) or ROOM_TELEPORT (F)]
[<nine-number room affect record>     -- only with ROOM_AFFECTED_BY (H)]
D<direction>
<exit description>
~
<door keyword>~
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
| `number` | A plain integer, kept as `Room.number` and shown by `stat room` as `Number:`; nothing else reads it. Every shipped room writes `0`; do so too |
| `ROOM_FLAGS` | Flag bitmask; see Room Flags table |
| `ROOM_FLAGS2` | Present **only** when `ROOM_FLAGS` contains `Z` |
| `sector_type` | Integer; see Sector Types table |
| `to_room speed visible` | A river or teleport room's destination, its timer in ticks, and whether the arrival LOOKs (`1`) or not (`0`) |
| `D<direction>` | Exit section; `D0` or `D 0`=north, `D1` or `D 1`=east, ..., `D9`=southwest |
| `exit description` | Text player sees when typing `look north`, etc. |
| `door keyword~` | Keyword(s) for the door, then `~`; just `~` for no door. OPEN, CLOSE, LOCK and UNLOCK match this |
| `door type` | 0=open passage, 1=door, 2=pickproof door, etc. (see Door Types) |
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
#41000
Rock Carving~
You scramble through this mountain pass, the frightening stony walls reaching
to the sky on either side of you. Cut into the rock face is an imposing
monolithic statue of a long forgotten king. Ahead, iron gates block passage.
~
0 0 5
D0
A pass through tall iron gates.
~
gate gates~
2 41023 41001
D2
A pass through the mountains.
~
~
0 -1 41002
E
statue~
An imposing stone statue of the ancient king Ozymandias gazes down upon you.
~
S
```

The north exit's description is "A pass through tall iron gates." and its
keyword is `gate gates`, so OPEN GATE and UNLOCK GATE find it. Putting the
keyword *above* the first tilde makes it part of the description and
leaves the door with no name.

---

### Room Flags

Second field on the `<number> <ROOM_FLAGS> [ROOM_FLAGS2] <sector_type>` line. The loader accepts letter bitmasks, decimal masks, and additive pipe syntax such as `8|4096`, although letters are preferred for new rooms.

| Flag | Letter | Description |
|---|---|---|
| ROOM_DARK | A | Room is dark; light source required to see |
| ROOM_JAIL | B | Configured jail or related holding room |
| ROOM_NO_MOB | C | Mobs cannot wander into this room |
| ROOM_INDOORS | D | Room is inside; immune to weather |
| ROOM_RIVER | E | Room is a river: carries whoever is in it on a timer (needs the `to_room speed visible` line) |
| ROOM_TELEPORT | F | Room transports whoever is in it to a designated room after N ticks (needs the same line) |
| ROOM_CULT_ENTRANCE | G | Hidden from, and closed to, characters below level 25 (`can_see_room`) |
| ROOM_AFFECTED_BY | H | Room affect: gas, heat or shocks (requires the record below) |
| ROOM_DT | I | Death trap -- see below. **Use only with permission; requires warning exits** |
| ROOM_PRIVATE | J | At most 2 mortal players |
| ROOM_SAFE | K | No combat allowed. **Use sparingly; requires permission** |
| ROOM_SOLITARY | L | At most 1 mortal player |
| ROOM_PET_SHOP | M | Pet shop; mobiles reset into the room with the next vnum become its pets. **Requires permission** |
| ROOM_NO_RECALL | N | Players cannot recall, word of recall, or scroll from this room |
| ROOM_IMP_ONLY | O | Only implementors can enter |
| ROOM_GODS_ONLY | P | Only immortals can enter |
| ROOM_HEROES_ONLY | Q | Only heroes and immortals can enter |
| ROOM_NEWBIES_ONLY | R | Mud School: closed to mortals above level 10 -- see below |
| ROOM_LAW | S | City limits: no charming, no aggressive followers |
| ROOM_HP_REGEN | T | Increased hit-point regeneration |
| ROOM_MANA_REGEN | U | Increased mana regeneration |
| ROOM_ARENA | V | Arena room behavior |
| ROOM_CASTLE_JOIN | W | Castle joining room |
| ROOM_SILENT | X | No spells can be cast in this room (immortals excepted) |
| ROOM_BFS_MARK | Y | Runtime: the tracker's pathfinding mark -- do not set |
| ROOM_FLAGS2 | Z | Signals that a ROOM_FLAGS2 token follows |

`ROOM_JAIL` (`B`) is reserved for the configured jail and related holding rooms.

`ROOM_PRIVATE` and `ROOM_SOLITARY` count mortal players only: mobiles and
staff standing in the room take no place (`room_is_private`).

**ROOM_DT** is not instant death on entry. `dtrap_update` runs every two
seconds (`PULSE_DEATHTRAP`) for each mortal player standing in such a
room: the first pass halves a standing character's hit points, sits them
down and says "Your fate has been sealed!"; the next pass (or the first,
for anyone already down or at 20 hit points or fewer) kills them.
Mobiles and immortals are never touched. WALKTO never walks into one.

**ROOM_NEWBIES_ONLY** is Mud School's flag. `move_char`, WALKTO, the
travel spells, MANIPULATE and random arrivals all close it to mortals
above level 10 ("Mud School is for newbies only"). Note that
`can_see_room` in `src/handler.c` still hides such a room from mortals
above level 5, and `move_char` asks that first, so in practice a mortal
of level 6 to 10 cannot walk in either -- the two limits disagree in the
code. Immortals are never stopped.

When `Z` is present, place a ROOM_FLAGS2 token between ROOM_FLAGS and the sector type:

| Flag | Letter | Description |
|---|---|---|
| ROOM2_NO_TPORT | A | Excludes the room from the teleport spell's random destinations |
| ROOM2_ALWAYS_LIT | B | Lit whatever the sky is doing (ROOM_DARK still wins); Hyrule's overworld |
| ROOM2_BANK | C | Enables room-based banking commands |

---

### Sector Types

Last field on the room data line.

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

As `load_rooms` reads it (this table used to list values the code does not
have):

| Value | Meaning |
|---|---|
| 0 | Open passage (no door) |
| 1 | Door (EX_ISDOOR) |
| 2 | Pickproof door (EX_ISDOOR, EX_PICKPROOF) -- the one to use for a door with a key |
| 3 | Door (EX_ISDOOR), the same as 1 |
| 4 | Secret door: `load_resets` turns every `D` reset of it into state 4 |
| 5 | Pickproof door whose every `D` reset `load_resets` turns into state 5, **trapped** |

A door keyword beginning `secret` makes the exit type 4 whatever the file
says. Type 5 is not "locked": until 2026-10 Hyrule used it for every keyed
door, and every one went off as a trap on four unlocks in five.

For a secret door: use type `4`, put the secret word as `door keyword`, and leave a blank tilde for the door name. Without the keyword the exit does not appear in the room description.

---

### ROOM_AFFECTED_BY Details

When ROOM_FLAGS includes `H`, nine numbers follow the room flags line
(after the river/teleport line, if the room has one). `load_rooms` reads
them in this order:

```
<type> <level> <bitvector> <bitvector2> <modifier> <location> <duration> <dam_dice> <dam_sides>
```

| Field | Read with | Meaning |
|---|---|---|
| `type` | number | The room affect (table below) |
| `level` | number | The affect's power: a stinking cloud poisons a character below this level outright, and anyone else who fails a save against it; it is also the poison's level. **Not** a minimum level to enter |
| `bitvector` | flag | `AFF_` bits the stinking cloud's poison lays on its victim |
| `bitvector2` | flag | `AFF2_` bits the same poison lays |
| `modifier` | number | The poison affect's modifier |
| `location` | number | The poison affect's apply location (see Apply Types) |
| `duration` | number | The poison affect's duration in ticks |
| `dam_dice` | number | Number of damage dice per hit |
| `dam_sides` | number | Sides on each die |

The room affect hits a character who leaves the room, one who arrives,
and every player standing in it at each tick (`room_affect` in
`src/handler.c`). With `dam_dice` 0 it does nothing unless both
bitvectors are non-zero.

**Room affect types:**

| Value | Name | Effect |
|---|---|---|
| 1 | STINKING_CLOUD | Poisons (affect from the fields above) and does poison damage |
| 3 | VOLCANIC | Fire damage, with a sweating message |
| 4 | SHOCKER | Lightning damage, with a metal rod |

Type 2 (`EXTRA_DIMENSIONAL`) does nothing in `room_affect`. `load_rooms`
names the affect from `room_aff_type` in `src/db.c`, which names every
type from 0 to 4 (`ROOM_AFF_TYPES` in `merc.h`); a type outside that
range stops the boot with "bad room affect type". Until 2026-11-12 the
table stopped at 3, so a type 4 room could not be loaded. The three
shipped rooms that carry the flag are camelot 781 and canyon 9245,
volcanic, and whouse 14040, a stinking cloud.

**Example:** A volcanic room dealing 3d8 fire damage, level 20:
```
0 H 3
3 20 0 0 0 0 0 3 8
```

---

## #RESETS Section

### Reset Commands

The `#RESETS` section populates the area with mobs and objects at game load and at each area reset.

Every reset line is a letter, an ignored number (the old "if" flag,
written `0` or `1`), then the arguments; anything after the last argument
on the line is a comment. `G` and `R` read two arguments, the others
three (`load_resets`).

```
* comment line (ignored)
M 0 <mob_vnum> <world_limit> <room_vnum>           — load mobile in room
O 0 <obj_vnum> <ignored> <room_vnum>               — load object in room
G 1 <obj_vnum> <limit>                             — give object to last loaded mob
E 1 <obj_vnum> <limit> <wear_loc>                  — equip object on last loaded mob
P 1 <obj_vnum> <ignored> <container_vnum>          — put object in container
D 0 <room_vnum> <door_dir> <door_state>            — set door state
R 0 <room_vnum> <exit_count>                       — shuffle exits 0 .. exit_count-1
H 0 <container_vnum> <obj_vnum or 0> <mob_vnum>    — put a mob inside a container
S                                                  — end of resets section
```

**Detailed descriptions** (each as `reset_area` in `src/db.c` carries it out):

**M — Load Mobile:**
```
M 0 41010 5 41003
```
Loads mob `41010` in room `41003` while fewer than `5` of it exist in the
whole world. Each room also stops at the number of `M` resets that name
the same mobile and room (`fix_reset_room_limits`), so survivors do not
pile up reset after reset.

**G — Give Object to Mobile:**
```
G 1 41040 -1
```
Gives object `41040` to the most recently loaded mob.
- `G` belongs to the `M` (or `G`/`E`) just before it: if that `M` loaded nobody, the `G` does nothing
- For a shopkeeper the object is shop stock and always made (see ITEM_INVENTORY)
- Otherwise the limit is the world-wide count: `-1` means 999, a figure over 50 is an old format and means 6, and even at the limit one reset in five makes one more

**E — Equip Object on Mobile:**
```
E 1 41050 -1 16
```
As `G`, then equips it in wear slot `16` (wield). See Wear Location Values table below.

**O — Load Object in Room:**
```
O 0 41035 1 41041
```
Loads object `41035` in room `41041` if there is not already one there
and nobody is in the area. The middle number is read and not used. An
object made by `O` is given a cost of 0.

**P — Put Object in Container:**
```
P 1 41023 1 41030
```
Puts object `41023` into the first copy of object `41030` in the world,
if that container exists, holds none already, and nobody is in the area
(Hyrule's chests excepted). A container in a room is closed and locked
again as its prototype says first. The middle number is not used.

**D — Set Door State:**
```
D 0 41010 3 2
```
In room `41010`, set exit direction `3` (west) to state `2` (locked). The
exit must exist and be a door, or the boot stops.

**R — Randomize Exits:**
```
R 0 41055 4
```
In room `41055`, shuffle the exits in directions 0 to 3 -- the second
number is how many directions take part, counted from north, so `4`
mixes north, east, south and west and leaves up and down alone. It may be
0 to 6. Do not combine with a D reset on the same room.

**H — Put A Mob In A Container:**
```
H 0 41070 41071 41015
```
Creates mob `41015` and puts it *inside* the first copy of object `41070`
in the world -- a bottled creature, released when the container is
opened. The second number is an optional object vnum given to that mob
(`0` for none); it is made at the reset's level and marked
`ITEM_INVENTORY`. Nothing happens while anyone is in the area, if the
container does not exist, if it is not in a room and the previous reset
did not run, or if it already holds a creature. No `G` is needed after an
`H`; one that follows gives to the same mob.

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
| 2 | Closed and locked |
| 3 | Closed, locked and magical (EX_WIZLOCKED): its key opens it, but no pick, doorbash or pass door below level 68, and no random trap |
| 4 | Closed and secret, and locked if it has a key |
| 5 | Closed, locked and trapped (pickproof removed) |

Any closed, locked door that is not magical has a tiny chance at each reset of
becoming trapped as well.

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
| `trade0–trade4` | Up to 5 object type numbers the shopkeeper will **buy** from players (see Item Types for Shops). Use `0` for unused slots |
| `buy%` | Markup for players buying from shop. `100`=list price, `150`=50% markup. Should be ≥100 |
| `sell%` | Markdown for players selling to shop. `100`=list price, `75`=25% markdown. Should be ≤100 |
| `open_hr` | Hour shop opens (0–23) |
| `close_hr` | Hour shop closes (0–23). Use `0 23` for 24-hour shop |

Section ends with `0` on its own line.

**Example:**
```
#SHOPS
41000 2 3 4 10 0 105 15 0 23 ; The Wizard (buys scrolls, wands, staffs, potions)
41001 0 0 0 0 0 110 100 0 23 ; The Baker (buys nothing)
41002 5 0 0 0 0 130 40 0 23  ; Weaponsmith (buys weapons)
0
```

**Notes:**
- The objects the shopkeeper **sells** are those given to it via `G` resets in `#RESETS`
- Objects sold TO the shopkeeper are kept for resale if no duplicate exists (but don't replenish)
- Shopkeeper mobs should have ACT flags `ABV` (SENTINEL + NOPURGE) and immunity flags `ABCD` minimum

---

### Item Types for Shops (trade values)

The five trade numbers **are object type numbers** -- the same values as
the first number on an object's type line (see Object Types). `get_cost`
in `src/act_obj.c` offers to buy an object only when
`obj->item_type` equals one of the shop's `buy_type` entries. `0` is an
empty slot. The ones shops commonly use:

| Value | Name | Buys |
|---|---|---|
| 1 | ITEM_LIGHT | Lights |
| 2 | ITEM_SCROLL | Scrolls |
| 3 | ITEM_WAND | Wands |
| 4 | ITEM_STAFF | Staffs |
| 5 | ITEM_WEAPON | Weapons |
| 8 | ITEM_TREASURE | Treasure |
| 9 | ITEM_ARMOR | Armor |
| 10 | ITEM_POTION | Potions |
| 11 | ITEM_CLOTHING | Clothing |
| 12 | ITEM_FURNITURE | Furniture |
| 13 | ITEM_TRASH | Trash |
| 15 | ITEM_CONTAINER | Containers |
| 17 | ITEM_DRINK_CON | Drink containers |
| 18 | ITEM_KEY | Keys |
| 19 | ITEM_FOOD | Food |
| 22 | ITEM_BOAT | Boats |
| 26 | ITEM_PILL | Pills |
| 28 | ITEM_MAP | Maps |
| 29 | ITEM_SCUBA_GEAR | Scuba gear |

---

## #SPECIALS Section

### Specials Format

```
#SPECIALS
M <mob_vnum> <spec_function_name> ; optional comment
S
```

One `M` line per mob/spec assignment; a line starting `*` is a comment.
The section **must** end with `S`. `load_specials` accepts only `M`, `*`
and `S`: a `#` -- the `#$` that ends the file, say -- stops the boot with
`Load_specials: letter '#' not *MS.` Put the file's `#$` after the `S`.

**Example:**
```
#SPECIALS
M 41000 spec_cast_mage    ; The Wizard
M 41011 spec_executioner  ; The Watcher (guard)
M 41012 spec_cast_adept   ; Healer at temple
M 41060 spec_guard        ; City guards
M 41061 spec_janitor      ; Janitors
S

#$
```

---

### Available Spec-Functions

**Warning:** Spec-functions add significant CPU load. Do not add spec-functions to large numbers of mobs.

These are the general-purpose ones. `spec_table` in `src/special.c` lists every name `spec_lookup` knows -- guild guards, clerks, the Hyrule and holiday specials and the rest; a name it does not know stops the boot.

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

It ends the area file. It does not end any section: every section before
it needs its own terminator, `#SPECIALS` included.

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

Copy this template as a starting point for a new area. It uses the block
41000 to 41099 as a stand-in: replace every vnum with one from the block
you were assigned, and fill in all fields. Exactly as written it loads --
`tests/test_area_guide.py` reads it through `webadmin/area_reader.py` and
boots it with `../merc --check-area` in a disposable copy of the world
(3 rooms, 2 mobiles, 2 objects, 1 shop, 1 special).

```
#AREA   { 15 25 } YourName   Your Area Name~

#MOBILES
#41001
guard soldier warrior~
a city guard~
A city guard stands watch here.
~
He eyes you with professional wariness.
~
human~
ABG J -100 S
20 2 3d9+333 5d10+100 2d8+5 0
-4 -4 -4 0
CFIK AB 0 0
8 8 1 50
MH ABCDEFGHIJK M steel

#41002
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
MH ABCDEFGHIJK M 0

#0

#OBJECTS
#41001
longsword blade sword~
a steel longsword~
A steel longsword lies here.~
steel~
5 G AN
1 5 5 1 0
20 20 5000 P

#41002
potion healing red~
a potion of cure critical~
A red potion sits here.~
glass~
10 G A
20 15 0 0 0
20 2 2000 P

#0

#ROOMS
#41000
Market Square~
The bustling market square forms the heart of the area. Merchants hawk
their wares from colorful stalls that line the cobblestone plaza. Exits
lead north to the keep and east to the residential district.
~
0 0 1
D0
Tall iron gates lead to the keep.
~
gate gates~
1 -1 41001
D1
A cobbled road leads east into the residential district.
~
~
0 -1 41002
S

#41001
Before the Keep Gates~
Imposing iron gates bar the way back to the market. Guards stand watch.
~
0 0 1
D2
The iron gates lead back to the market.
~
gate gates~
1 -1 41000
S

#41002
Residential Road~
A quiet cobbled road winds through modest homes.
~
0 0 1
D3
The cobbled road leads west back to the market.
~
~
0 -1 41000
S

#0

#RESETS
*
* The gates start closed, on both sides
*
D 0 41000 0 1                             gate, market side
D 0 41001 2 1                             gate, keep side
*
* Guards
*
M 0 41001 3 41001                         The gate guard
E 1 41001 -1 16                           - wield longsword
*
* Shopkeeper
*
M 0 41002 1 41000                         The weapon merchant
G 1 41001 -1                              - longsword in stock
*
* Objects
*
O 0 41002 1 41002                         a potion on the road
S

#SHOPS
41002 5 0 0 0 0 130 40 0 23               ; Weapon merchant
0

#SPECIALS
M 41001 spec_guard                        ; Gate guard
S

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
- Armor: use `-1` for the object level to let the code roll the values, or write positive values sized to the level.
- Do not create objects stronger than the area level warrants.
- `ITEM_FLAGS2` items with `ADD_INVIS`, `ADD_FLY`, or `ADD_DETECT_INVIS` **require permission**.

### Room Design
- `ROOM_SAFE` rooms **require permission** — use very sparingly.
- `ROOM_DT` (death trap) rooms **require permission** — every entrance must clearly hint at danger.
- `ROOM_NO_RECALL` should be deliberate and documented. Hyrule shows the
  pattern: its dungeons (rooms 30400 to 30645, the run named "Level N:
  ...") are no-recall, because walking out of a dungeon by saying a word
  defeats it, while its overworld and caves allow recall. Wherever a run of
  rooms disables recall, provide validated return routes from every
  reachable room in it.
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
- [ ] `#SPECIALS` ends with `S`
- [ ] Area file ends with `#$`
- [ ] No mob is flagged with `ACT_TRAIN` or `ACT_PRACTICE` without permission
- [ ] No `ROOM_SAFE`, `ROOM_DT`, or `ROOM_PET_SHOP` without permission
- [ ] No `ITEM_FLAGS2` fly/invis/detect-invis items without permission
- [ ] Every `..._FLAGS2` token follows a field that has `Z` in it, and no `Z` lacks one
- [ ] All door key VNUMs use `-1` when no key exists (not `0`)
- [ ] Mob IMM flags include at minimum `AB` (SUMMON, CHARM) on all mobs
- [ ] Every exit has its description, then `~`, then its keyword (or nothing), then `~`
- [ ] Encoding saved as Latin-1 (not UTF-8)

---

## Related Documentation

- [Validation And Area Health](validation-and-area-health.md)
- [Developer Guide](developer-guide.md)
- [Operator Guide](operator-guide.md)
- [Hyrule: First Quest](hyrule-area.md)

*Maintained from the historical ToC wiki, current source code (`merc.h`,
`db.c`, `const.c`, `handler.c`), `webadmin/area_reader.py`, and active area
files. Last reviewed against the source: November 2026.*
