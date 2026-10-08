# In-Game Building Guide

This guide is for immortals who build the world from inside the game: new
areas, rooms, and -- as the later phases land -- mobiles, objects, and the
resets that make them respawn. Everything here is done with ordinary
commands at the prompt; you never leave the game or edit a file by hand.

Building commands are god-level (level 69 and up; MSHOW, OSHOW, ALIST,
ASTAT and RESETS from 68). If a command answers "Huh?" you are not high
enough.

> **New to this?** Type `build` and let the game ask you what you want --
> see [The guided builder](#the-guided-builder). When you want to know what
> it is doing, read [Concepts](#concepts) and
> [Your first room](#your-first-room), and keep the
> [Command reference](#command-reference) open beside you.

---

## Concepts

**The world is one big numbered space.** Every room, every kind of mobile,
and every kind of object has a **vnum** -- a number that names it for good.
Room 4207 is the Temple; mobile 2400 is the training dummy; object 30222 is
the bow. Vnums are how everything refers to everything else: an exit points
at a room vnum, a reset says "put mobile 2400 in room 2419." Rooms run from
1 to 30000 (WORLD_SIZE). Pick a vnum nobody uses and it is yours.

**An area is a block of vnums with a name.** `area/hyrule.are` owns its
rooms and monsters; `area/midgaard.are` owns Midgaard. An area is just a
file plus the range of vnums it covers. When you build, you build *into* an
area, and saving writes that area's file.

**Two kinds of area.** An area that *shipped with the game* is read-mostly:
only an implementor may change it, and saving over it takes a deliberate,
named confirmation, so you cannot rewrite Hyrule because you happened to be
standing in it. An area *you made in game* -- the shared workshop
(`custom.are`), or one you created with [ANEW](#anew) -- is yours to edit
and save freely. `ALIST` marks the buildable ones with a `*`.

**Nothing is permanent until you save.** Rooms you make live only in the
running game until `RSAVE` writes them to the area's file. A reboot without
a save loses them. And see [Saving and deploys](#saving-and-deploys): a
file made in game also has to reach the repository, or the next code deploy
drops it.

**Strings end at a tilde.** When a command takes a description, it reads to
the end of what you typed. You do not type the `~` yourself; the game adds
it. Colour codes like `{R` (bright red) work in names and descriptions.

---

## The guided builder

`BUILD` asks you what you want, one question at a time, and builds it with
the same commands the rest of this guide describes -- so it can make
anything they can, and refuses exactly what they would.

```
build area      a new area: how many rooms, what it is called -- then its first room
build room      the room you are standing in, and rooms dug out from it
build mob       a mobile for the area you are in
build obj       an object for the area you are in
```

A session looks like this:

```
> build area
How many rooms will it have, roughly?  [20]
> 6
What is the area called?
> The Sunken Grotto
Created area 'The Sunken Grotto' (21000-21019) in built/the_sunken_grotto.are.
Building room 21000.
What is this room called?
> The Mouth of the Grotto
Describe it, a line at a time.  A line with only a . on it ends the description.
> Water drips from a low ceiling; the air smells of salt.
> .
What kind of ground is it?  inside city field forest hills mountain ...
> underground
Dig a way out?  Give a direction to dig a new room that way, or press Enter.
> north
...
```

| You type | It means |
|---|---|
| an answer | That value, checked as the command would check it. A bad one is refused in the command's words and asked again. |
| Enter | Keep what is there and go on. |
| `.` | End a description. Descriptions are typed a line at a time and wrapped for you; any punctuation is fine, semicolons included. |
| `cancel` | Stop. What was made so far stays; `ASAVE` keeps it. |
| `/<command>` | Run a command without leaving the build: `/look`, `/say hang on`. |

What each one asks:

- **BUILD AREA** -- roughly how many rooms (it allows twice that, in tens,
  to grow into) and the area's name. It finds a free block of vnums clear
  of every other area, runs ANEW, takes you to the first room, and goes on
  as BUILD ROOM.
- **BUILD ROOM** -- the room's name, its description, what kind of ground
  it is; then whether to dig a new room in some direction. Digging walks
  you into the new room and asks the same of it; Enter at the dig question
  finishes and offers to save. You end up in the last room you dug.
- **BUILD MOB** -- the vnum (the next free one is offered), whether to copy
  an existing mobile, its keywords, short and long text, description,
  race, sex, level, alignment and attack; then any other field you like
  (`act +aggressive`, `hp 4d10+80`); then whether to place it in this room
  and save.
- **BUILD OBJ** -- the same start, then its type, and the questions that
  type needs: a weapon's class, dice and attack; armour's AC; a light's
  hours; a container's capacity and lid; a drink's liquid and size; a
  potion's spells; a wand's spell and charges. Then wear slots, level,
  weight and price, any other field, and where to place it (`floor`,
  `on <mob>`, `worn <mob>`, `in <container>`, or `no`).

---

## Your first room

The shared workshop is always there and always yours. You need nothing to
start:

```
goto 29200
```

If no room uses vnum 29200, one forms out of nothing and you are standing
in it, in the workshop area. Now give it some character:

```
set room 29200 name The Long Gallery
set room 29200 desc A hall of cracked mirrors runs north, catching torchlight.
set room 29200 flags +indoors +no_mob
set room 29200 sector inside
set room 29200 detail mirrors The glass is cracked into a hundred faces.
rshow
```

Dig an exit north, and the way back comes free:

```
rlink north 29201
```

Walk `north` -- room 29201 was made for you by the dig -- build it too, and
when you are happy, keep it all:

```
rsave confirm
```

That is the whole loop: **goto, set, rlink, rsave.** Everything else is
detail.

---

## Working in your own area

Building loose in the shared workshop is fine for one-off rooms. For a real
zone, give it a home of its own with [ANEW](#anew): a name, a vnum range,
and its own file.

```
anew 29200 29249 The Sunken Grotto
```

This claims vnums 29200-29249, writes `area/built/the_sunken_grotto.are`,
lists it so it loads next reboot, and links it live right now. From this moment a
room you make anywhere in 29200-29249 is born into the Grotto, not the
workshop:

```
goto 29200
set room 29200 name The Mouth of the Grotto
...
rsave confirm
```

Pick a range that is empty. ANEW refuses a range that overlaps another area
or that already has a room, mobile, or object in it; find a free block with
`ALIST` (shows every area's range), `RLIST`, or `VNUM`. Keep an area under
5000 vnums, and leave room to grow -- a 50- or 100-vnum block is normal for
a small zone.

`ASTAT` reads your area back: its range, its file, who may build in it, and
what it holds.

---

## Mobiles and objects

Every mobile and object in the game is a **prototype**: a template with a
vnum. `LOAD MOB 4444` makes one elite guard from prototype 4444; a reset
makes one every time the area repops. Building a monster or an item means
making a prototype.

A prototype you build lives in your area's vnum range. That range is how
the area knows the prototype is its own, so `MCREATE` and `OCREATE` only
work inside an area made with [ANEW](#anew), not in the workshop.

**Start from a copy.** Almost everything in a new zone is a variation on
something that already exists, and a copy brings every field with it --
the dice, the flags, the spells, the affects -- already sensible for its
level:

```
mcreate 29210 4444       a copy of the elite guard of Dresden
ocreate 29220 3021       a copy of a small sword
```

**Or start blank.** One number makes a blank prototype: a level 1 human
called "a new mobile", or a piece of trash you can pick up called "a new
object".

```
mcreate 29211
ocreate 29221
```

Either way the new prototype is its own from that moment: changing it
changes nothing else, and a copied shopkeeper gets a shop of its own.
See it with `LOAD MOB <vnum>` or `LOAD OBJ <vnum>`, read it with
`OSTAT <vnum>`, and keep it with `ASAVE`.

Both can then be edited field by field, in words: see
[Editing a mobile](#editing-a-mobile) and [Editing an object](#editing-an-object).

---

## Editing a mobile

`SET MOB` with a **vnum** instead of a name edits a prototype, in words.
`MSHOW <vnum>` reads it back, and prints exactly the words SET takes, so
the quickest way to learn the fields is to MSHOW something and change what
you see. (`set mob guard ...`, with a name, still edits one mobile standing
in the world, as it always has.)

Here is a blank mobile becoming a village smith:

```
mcreate 29210
set mob 29210 keywords dwarf smith
set mob 29210 short a burly dwarf smith
set mob 29210 long A burly dwarf smith hammers at an anvil here.
set mob 29210 desc Soot covers his arms to the elbow, and his beard is singed short.
set mob 29210 desc + He does not look up.
set mob 29210 race dwarf
set mob 29210 sex male
set mob 29210 level 20
set mob 29210 hp 4d10+80
set mob 29210 attack pound
set mob 29210 act +sentinel
set mob 29210 offense +parry
mshow 29210
asave
```

### The words

| Field | Takes | Notes |
|---|---|---|
| `keywords` | words | What players type: `dwarf smith`. |
| `short` | text | Used in sentences: "*a burly dwarf smith* hits you". |
| `long` | text | The line in the room. A capital and a line end are added. |
| `desc` | text | What LOOK at it shows, wrapped to 72 columns for you. `desc + more` adds; `desc clear` empties. |
| `race` | a race | `human`, `elf`, `dwarf`, `giant`, `dragon`, `wolf`... |
| `sex` | `male` `female` `neutral` | |
| `size` | `tiny` `small` `medium` `large` `huge` `giant` | |
| `material` | a material | `iron`, `wood`, `cloth`... |
| `level` | 1-200 | See [what the level does](#what-the-level-does). |
| `alignment` | `good` `neutral` `evil`, or -1000..1000 | |
| `hitroll` | a number | |
| `hp` | dice | `4d10+80`: four ten-sided dice, plus 80. |
| `mana`, `damage` | dice | `2d6+3`. |
| `attack` | an attack | `slash`, `pierce`, `bite`, `claw`, `pound`, `flaming_bite`... Give none to list them. |
| `ac` | a number | All four armour classes. **Lower is better.** `ac slash -40` sets one. |
| `position` | `standing` `sitting` `resting` `sleeping` | How it is found when it appears. |
| `default` | the same | What it goes back to. |
| `wealth` | a number | Its coin. 0 means "what a mobile of its level carries". |
| `special` | a special, or `none` | A built-in behaviour: `cast_mage`, `breath_fire`, `thief`... The `spec_` is optional. |

### Flags

`act`, `affect`, `offense`, `immune`, `resist`, `vulnerable`, `form` and
`parts` are lists of names. `+name` adds one, `-name` takes one away, a bare
name adds, and `none` clears the list. Several at once is fine:

```
set mob 29210 act +aggressive -wimpy
set mob 29210 resist +fire +cold
set mob 29210 affect none
```

Give the field with nothing after it (`set mob 29210 act`) to see every
name it takes. A name you mistype is refused and the list is printed.

| Field | Some of its names |
|---|---|
| `act` | `aggressive` `sentinel` (never wanders) `stay_area` `wimpy` `scavenger` `pet` `train` `practice` `healer` `mountable` `no_purge` `questmaster` |
| `affect` | `sanctuary` `invisible` `detect_invis` `detect_hidden` `flying` `haste` `sneak` `hide` `infrared` `pass_door` |
| `offense` | `dodge` `parry` `bash` `kick` `trip` `disarm` `berserk` `rescue` `fast` `assist_all` `assist_race` `assist_guard` |
| `immune` / `resist` / `vulnerable` | `fire` `cold` `lightning` `acid` `poison` `magic` `weapon` `bash` `pierce` `slash` `holy` `negative` `mental` ... (`vulnerable` adds `iron` `wood` `silver`) |
| `form` | `biped` `mammal` `animal` `sentient` `undead` `dragon` `insect` `edible` ... |
| `parts` | `head` `arms` `legs` `hands` `claws` `fangs` `wings` `tail` `scales` ... |

### What the race does

A race comes with natural flags: a dwarf sees in the dark and resists magic
and disease; a dragon sees the invisible, bashes and lashes with its tail. Setting a race adds them, and replaces the
mobile's form and body parts with the race's. **A race's natural flags
cannot be taken away**, because every boot puts them back whatever the
file says. SET refuses and tells you why rather than let it look as though
it worked. To lose them, choose another race.

### What the level does

The game holds every mobile to a floor for its level, at every boot: its
hitroll is at least half its level, its damage bonus at least three
quarters of it, and its armour no worse than `100 - 6 x level`. SET applies
the same floor the moment you set a level, hitroll, damage or armour, and
says what it raised, so MSHOW never shows you a number a reboot would
quietly change. Set the level first, then tune upward from there.

### A shop

A shopkeeper sells what it carries -- and a shopkeeper's stock never runs
out -- and buys the item types you name:

```
set mob 29210 shop                     a shop: markup 120%, pays 80%, open all day
set mob 29210 shop markup 150          buyers pay 150% of an item's value
set mob 29210 shop pays 50             it pays 50% for what it buys
set mob 29210 shop buys weapon armor   up to five item types
set mob 29210 shop hours 6 22          open from 6 to 22
set mob 29210 shop none                not a shop any more
place mob 29210                        stand it in its stall
place obj 29221 on 29210               its stock: one reset per thing it sells
```

MSHOW shows the terms on its `shop:` line.

### Seeing it

`LOAD MOB 29210` puts one in front of you. A mobile already in the world
keeps the form it was made with: PURGE it and load a fresh one to see a
change. Nothing is kept until `ASAVE`.

---

## Editing an object

`SET OBJ` with a **vnum** edits an object prototype in words, and
`OSHOW <vnum>` reads it back in the same words. (`set obj sword ...`, with a
name, still edits one object in the world.)

A blank object becoming a sword:

```
ocreate 29220
set obj 29220 keywords sword runed
set obj 29220 short a runed sword
set obj 29220 long A runed sword lies here.
set obj 29220 desc The blade is etched from hilt to point.
set obj 29220 detail runes They spell out a name nobody remembers.
set obj 29220 type weapon
set obj 29220 class sword
set obj 29220 dice 3d6
set obj 29220 attack slash
set obj 29220 weapon +sharp
set obj 29220 wear +take +wield
set obj 29220 flags +glow +magic
set obj 29220 level 15
set obj 29220 cost 5g 20s
set obj 29220 affect +hitroll 2
oshow 29220
asave
```

### Every object

| Field | Takes | Notes |
|---|---|---|
| `keywords` | words | What players type. |
| `short` | text | In sentences: "you wield *a runed sword*". |
| `long` | text | The line when it lies on the ground. |
| `desc` | text | What `LOOK SWORD` shows. Without it, LOOK repeats the long line. |
| `detail` | a keyword, then text | What `LOOK <keyword>` shows -- runes, a seal, a crack. `detail runes + more` adds; `detail runes none` removes. Quote several keywords: `detail 'runes markings' ...`. |
| `type` | a type | `weapon` `armor` `clothing` `light` `container` `drink` `food` `potion` `pill` `scroll` `wand` `staff` `portal` `money` `key` `treasure` `furniture` `boat`... **Changing the type clears the values**, which meant something else to the old type. |
| `level` | 0-200 | Who can use it. |
| `weight` | 0-30000 | |
| `cost` | a price | `5g 20s`, `1p`, `3 gold`, or a plain number of copper. |
| `condition` | `perfect` `good` `average` `worn` `damaged` `broken` `ruined` | |
| `material` | a material | |
| `wear` | slots | `+take` (it can be picked up -- almost everything wants this), then where it goes: `wield` `hold` `finger` `neck` `torso` `head` `legs` `feet` `hands` `arms` `shield` `about` `waist` `wrist`. |
| `flags` | names | `glow` `hum` `magic` `bless` `nodrop` `noremove` `invis` `metal` `anti_good` `anti_evil` `anti_neutral` `rot_death` `no_locate` `humans_only` `elves_only` `dwarves_only` `no_steal`... |

Lists take `+name`, `-name` and `none`, as for mobiles.

### What its values mean, by type

An object's numbers mean different things for each type, so each type has
fields of its own. A field another type owns is refused with the list of
this type's.

| Type | Fields |
|---|---|
| weapon | `class sword` (dagger axe mace spear flail whip polearm bow exotic), `dice 3d6`, `attack slash`, `weapon +sharp` (flaming frost vampiric vorpal two_handed) |
| armor, clothing | `ac 5`, or `ac slash 8` -- on an item **higher is better** |
| light | `hours 24`, or `hours infinite` |
| container | `capacity 100` (weight it holds), `container +closeable +closed +locked +pickproof`, `key <object vnum>` |
| drink | `capacity 10`, `amount 10` or `amount full`, `liquid beer`, `poisoned yes` |
| food | `hours 6`, `poisoned no` |
| money | `coins 50`, `coin gold` |
| potion, pill, scroll | `spell level 20`, `spells 'cure light' armor` (up to three) |
| wand, staff | `spell level 20`, `charges 5`, `spell 'magic missile'` |
| portal | `portal plain` (or `random`, `crystal_ball`, `keyed`), `destination <room vnum>`, `key <object vnum>` |
| anything | `v0` .. `v4` -- the raw numbers, for types nobody has named yet |

A spell has to be one an item can hold: it must do something, and have a
slot number, because the area file stores spells by slot. A weapon's dice
take no bonus; give extra damage as `affect +damroll 2`.

### What it gives the wearer

```
set obj 29220 affect +hitroll 2      a stat bonus
set obj 29220 affect ac -10          armour (lower is better on a person)
set obj 29220 affect -hitroll        take it off
set obj 29220 grants +haste          a power while worn
```

Stats: `strength` `dexterity` `intelligence` `wisdom` `constitution` `hp`
`mana` `moves` `ac` `hitroll` `damroll` `saves`. One affect per stat:
setting it again replaces it. Powers (`grants`): `haste` `sanctuary`
`flying` `invisible` `detect_invis` `detect_hidden` `infrared` `pass_door`
`sneak`...

**Affects and powers cannot change while anybody is wearing one.** The game
takes an item's affects off by reading the prototype, so changing them
under a worn copy would take off something other than what went on. Have it
removed first.

---

## Placing things: resets

A prototype is a template; nothing appears in the world until something
makes one. A **reset** is a standing order: "a smith stands in this room",
"a chest lies here with a ring in it", "this door is locked". Every few
minutes the game walks each area's resets and puts back whatever is
missing. `PLACE` writes one for the room you are standing in, and carries
it out once immediately so you can see it.

```
goto 29201
place mob 29210                 the smith, here, coming back if killed
place obj 29221 worn 29210      wielding the sword
place obj 29230 on 29210        carrying a key
place obj 29240                 a chest on the floor
place obj 29241 in 29240        a ring in the chest
place door north locked         the door north locked again each reset
resets
asave
```

| Command | What it does |
|---|---|
| `place mob <vnum> [<how many>]` | A mobile in this room. `place mob 29215 3` is three of them. |
| `place obj <vnum>` | An object on the floor here. |
| `place obj <vnum> in <container>` | Inside a container already placed in this room. |
| `place obj <vnum> on <mobile>` | Carried by a mobile already placed in this room. |
| `place obj <vnum> worn <mobile>` | Worn or wielded by it. The slot comes from the item's wear slots; a second ring goes on the other finger. |
| `place door <dir> open\|closed\|locked` | The door's state after each reset -- from both sides, when the far room is one you may build in. |
| `resets` | What is placed in this room, numbered. |
| `unplace <n>` | Take reset `n` out. A mobile's items, or a container's contents, go with it. |

**Order matters, and PLACE keeps it.** A "give" or "wear" reset acts on the
mobile the reset before it made; a "put in" acts on the container. So an
item for a mobile or a chest needs that mobile or chest placed in this room
first, and PLACE files the item straight after it.

**When things come back.** Mobiles and doors come back whenever their area
resets. Objects on the floor and in containers come back only when a reset
finds the area empty of players -- stock ROM behaviour, so loot is not
restocked under somebody's feet. A mobile is never added past the number
placed in its room, however long it survives.

**Taking one out.** UNPLACE removes the reset, not what it already made:
the mobile or object in the room now stays until you PURGE it.

Resets live in the area and are written by `ASAVE`, so they need an area
made with ANEW.

**Getting players there.** `WALKTO <area name>` finds an area built in game
by its name, and walks there by the same rules as everywhere else -- so it
needs a way in. A built area starts unconnected: an implementor links it to
the world (RLINK from a shipped room, which only an implementor may edit).
The published routes on the website and in Mudlet are generated from the
shipped world and do not list built areas. A door's lock wants a key to be any use: `rlink <dir> key
<vnum>` names one.

---

## Command reference

### Areas

| Command | What it does |
|---|---|
| `anew <lo> <hi> <name>` | Make a new buildable area owning vnums lo-hi. |
| `alist` | List every area: file, vnum range, room/mob/object counts. `*` = buildable. |
| `astat [name]` | Details of one area (the one you are in, or the one named). |

#### ANEW

`anew <low vnum> <high vnum> <name>`

Creates a new area. The range must be empty and must not overlap another
area. Writes `area/built/<slug>.are` with an `#AREADATA` header recording
the range and your name as builder, adds it to `area/built/built.lst`, and
links it live so you can build at once. See
[Saving and deploys](#saving-and-deploys) for how it reaches git.

#### ALIST / ASTAT

`alist` lists everything loaded. `astat` with no argument reads the area
you are standing in; with a name, the first area whose name matches.

### Rooms

| Command | What it does |
|---|---|
| `goto <vnum>` | Go to a room; if the vnum is free, make it first. |
| `set room <vnum> name <text>` | Name the room. |
| `set room <vnum> desc <text>` | Set the description, wrapped for you. `desc + <text>` adds a line. |
| `set room <vnum> flags <names>` | Room flags by name: `+indoors -dark`, `none`. The old letters (`+AJ`) still work. |
| `set room <vnum> sector <name>` | The ground: `inside city field forest hills mountain water_swim water_noswim underwater air desert underground`. |
| `set room <vnum> detail <keyword> <text>` | What `LOOK <keyword>` shows here. `+ <text>` adds, `none` removes. |
| `rshow [vnum]` | Read a room in those words: flags, ground, description, exits and their doors, details, resets. |

`set room` works on any room you may edit: the room you name must be in a
buildable area (or you must be an implementor).

Room flag names: `dark` `jail` `no_mob` `indoors` `cult_entrance`
`death_trap` `private` `safe` `solitary` `pet_shop` `no_recall` `imp_only`
`gods_only` `heroes_only` `newbies_only` `law` `hp_regen` `mana_regen`
`arena` `castle_join` `silent` `no_teleport` `always_lit` `bank`. River,
teleport and room-affect rooms keep data a save cannot write yet, so those
flags are not set by hand.

A typed `;` separates commands, so write `\;` for a semicolon inside a
description. (The guided builder takes semicolons as they are.)

### Exits

`rlink` works on the room you are standing in.

| Command | What it does |
|---|---|
| `rlink <dir> <vnum>` | Dig an exit that way (and the way back); makes the far room if needed. |
| `rlink <dir> none` | Remove the exit. |
| `rlink <dir> open` | A plain doorway, no door. |
| `rlink <dir> door` | A door that can be opened and closed. |
| `rlink <dir> pick` | A door that cannot be picked. |
| `rlink <dir> secret` | A door hidden from EXITS until found. |
| `rlink <dir> key <vnum>` | The object that unlocks it. |
| `rlink <dir> name <words>` | What to call the door: `door gate`. |
| `rlink <dir> desc <text>` | What you see looking that way. |

Directions: `north east south west up down` and the four diagonals.

### Saving

| Command | What it does |
|---|---|
| `asave [area]` | Write a whole ANEW area: mobiles, objects, rooms, resets, shops, specials. |
| `rsave` | Report what would be written (writes nothing). |
| `rsave confirm` | Write the current area to its file. An ANEW area saves whole, as ASAVE. |
| `rsave confirm <file>` | Implementor-only, for a shipped area; names the file to prove intent. |

### Mobiles and objects

| Command | What it does |
|---|---|
| `mcreate <vnum>` | A blank mobile at a free vnum in your area's range. |
| `mcreate <vnum> <from>` | A copy of mobile `<from>`, which may be any mobile in the game. |
| `ocreate <vnum>` | A blank object at a free vnum in your area's range. |
| `ocreate <vnum> <from>` | A copy of object `<from>`. |
| `load mob <vnum>` / `load obj <vnum>` | Make one, to look at. |
| `mshow <vnum>` | Read a mobile prototype in words. |
| `set mob <vnum> <field> <value>` | Change a mobile prototype; see [Editing a mobile](#editing-a-mobile). |
| `oshow <vnum>` | Read an object prototype in words. |
| `set obj <vnum> <field> <value>` | Change an object prototype; see [Editing an object](#editing-an-object). |

### Resets

| Command | What it does |
|---|---|
| `place mob\|obj\|door ...` | Make something come back in this room; see [Placing things](#placing-things-resets). |
| `resets` | List this room's resets. |
| `unplace <n>` | Remove one. |

---

## Saving and deploys

Two different things have to happen for built work to last.

**1. Save to the file.** `ASAVE` writes everything in an ANEW area -- every
mobile and object in its range, its rooms, resets, shops and specials --
and `RSAVE CONFIRM` does the same there. In the workshop and in shipped
areas, RSAVE writes the rooms only. Anything never saved is gone at the next
reboot. Both keep the previous file beside the new one with a timestamp, so
a bad save can be undone from the shell.

ASAVE writes nothing if something in the area cannot be written faithfully,
and names it. A reset that points at something gone -- a mobile never
saved, a door taken out since -- would stop the game at the next boot, so
it is left out of the file, and ASAVE says how many it dropped.

**2. It reaches the repository on its own.** An area made with ANEW lives
in `area/built/`, with its own list, `area/built/built.lst`, which the game
loads after the shipped world's `area.lst`. Building never touches
`area.lst`. Every five minutes the server's state sync commits
`area/built/` to git along with the player files, so a lost server loses
at most the last few minutes; a code deploy leaves the live `area/built/`
exactly as it is, and only fills in a built file the server is missing.
The workshop, `custom.are`, is synced the same way. Save backups
(`*.bak`) stay on the server.

What is not saved with ASAVE or RSAVE is in memory only, and a reboot or a
deploy loses it.

---

## What will not save yet

`RSAVE` and `ASAVE` refuse, by name, a room they cannot write without
quietly losing something: a river or teleport room, or a room carrying a
room affect. Those hold data the room format does not yet round-trip. Build
elsewhere, or ask for the format to be finished, rather than save a file
that has lost it. ASAVE refuses the same way for a mobile flag word or an
object value the file format cannot hold (a negative object value, for
one).

One thing comes back changed on purpose: a room with **no exits at all** is
made NO_MOB when the game boots, as stock ROM always has. Give a room an
exit and it keeps the flags you set.

---

## Troubleshooting

- **"Huh?"** -- the command does not exist at your level, or has not
  shipped. Building is level 69+.
- **"That room came out of an area file..."** -- you are editing a shipped
  area. Only an implementor may, and saving names the file.
- **"Vnum N is already in use"** (from ANEW) -- pick an empty range; check
  with `ALIST`.
- **"That overlaps <area>"** -- your range runs into another area's.
- **A room you built is gone after a reboot** -- you did not `RSAVE`, or the
  area file never reached the repository before a deploy. See
  [Saving and deploys](#saving-and-deploys).

---

## What has been built

In-game building was built in phases, all of them now shipped:

- **Areas and rooms** -- ANEW/ALIST/ASTAT, GOTO-to-create, SET ROOM, RLINK,
  RSAVE.
- **Mobiles, objects and the full-area save** -- MCREATE and OCREATE, blank
  or copied from anything in the game; ASAVE writes the whole area.
- **Editing mobiles** -- SET MOB <vnum> and MSHOW, every field in words.
- **Editing objects** -- SET OBJ <vnum> and OSHOW: type, wear slots, flags,
  the values each type gives meaning to, affects, powers and details.
- **Resets** -- PLACE, RESETS and UNPLACE: mobiles, their gear, objects,
  containers' contents and door states that come back, saved with ASAVE.
- **Repository persistence** -- built areas live in `area/built/`, reach
  git with the state sync, and survive deploys.
- **The guided builder** -- BUILD AREA, ROOM, MOB and OBJ ask a question at
  a time and build through the same commands.
- **Rooms in words, shops, and WALKTO** -- SET ROOM flags, ground and
  details by name with RSHOW; SET MOB <vnum> SHOP; WALKTO finds a built
  area by its name.

That is the whole of the plan. Ideas for more go to `IDEA` in game.

---

## Related

- `HELP BUILDING`, `HELP ANEW`, `HELP ASAVE`, `HELP MCREATE`,
  `HELP OCREATE`, `HELP RLINK`, `HELP RSAVE`, `HELP SET` in game.
- [Area Building Guide](area-building-guide.md) -- the `.are` file format,
  for editing files directly or understanding what the commands write.
- [Operator Guide](operator-guide.md) -- running the live game.
