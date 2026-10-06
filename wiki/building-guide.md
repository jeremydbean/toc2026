# In-Game Building Guide

This guide is for immortals who build the world from inside the game: new
areas, rooms, and -- as the later phases land -- mobiles, objects, and the
resets that make them respawn. Everything here is done with ordinary
commands at the prompt; you never leave the game or edit a file by hand.

Building commands are god-level (level 69 and up). If a command answers
"Huh?" you are not high enough, or it has not shipped yet -- check the
Roadmap at the end.

> **New to this?** Read [Concepts](#concepts) once, then jump to
> [Your first room](#your-first-room). Keep [Command reference](#command-reference)
> open beside you.

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
set room 29200 flags +AJ
set room 29200 sector 0
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

This claims vnums 29200-29249, writes `area/the_sunken_grotto.are`, lists
it so it loads next reboot, and links it live right now. From this moment a
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

Editing a prototype field by field, in plain English (`set mob 29210 race
dwarf`, `set obj 29220 type weapon`), is the next phase; see the
[Roadmap](#roadmap). Until then, copy the closest thing to what you want.

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
area. Writes `area/<slug>.are` with an `#AREADATA` header recording the
range and your name as builder, adds it to `area.lst`, and links it live so
you can build at once. See the deploy caution under
[Saving and deploys](#saving-and-deploys).

#### ALIST / ASTAT

`alist` lists everything loaded. `astat` with no argument reads the area
you are standing in; with a name, the first area whose name matches.

### Rooms

| Command | What it does |
|---|---|
| `goto <vnum>` | Go to a room; if the vnum is free, make it first. |
| `set room <vnum> name <text>` | Name the room. |
| `set room <vnum> desc <text>` | Set the room description. |
| `set room <vnum> flags <letters>` | Room flags: `+AJ` adds, `-A` removes, a number sets. |
| `set room <vnum> sector <n>` | Terrain type (inside, city, forest, water...). |
| `rstat [vnum]` | Inspect a room: flags, sector, exits, contents. |

`set room` works on any room you may edit: the room you name must be in a
buildable area (or you must be an implementor). `rstat` shows the letters
each flag uses, which is what `set room ... flags` expects.

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
| `ostat <vnum>` | Read an object prototype. |

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

**2. Reach the repository.** The live server runs from a copy that a code
deploy rebuilds from git. A new `.are` file and an `area.lst` entry made in
game live only on the running server; **a deploy will drop an area that was
never committed to the repository.** Player files and logs are synced to git
automatically; area files you create are not, yet. Until that is wired up
(see the Roadmap), tell an implementor when you have built something worth
keeping so it can be committed. This is a known limitation, not a bug.

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

## Roadmap

In-game building is being filled out in phases. Shipped so far:

- **Areas and rooms** -- ANEW/ALIST/ASTAT, GOTO-to-create, SET ROOM, RLINK,
  RSAVE.
- **Mobiles, objects and the full-area save** -- MCREATE and OCREATE, blank
  or copied from anything in the game; ASAVE writes the whole area.

Coming, in order:

- **Editing mobiles** -- change a monster in plain English: `set mob
  <vnum> race human`, `sex female`, `level 12`, flags by name.
- **Editing objects** -- change an item in plain English: type, wear
  slots, and the values that matter for that type, named not numbered.
- **Resets** -- place a mobile or object in a room so it respawns, and have
  it persist in the area file.
- **A guided wizard** -- a step-by-step builder that asks what you want and
  runs the commands for you, for people who would rather be led than
  memorise syntax.
- **Repository persistence** -- built areas reaching git on their own, so a
  deploy keeps them.

---

## Related

- `HELP BUILDING`, `HELP ANEW`, `HELP ASAVE`, `HELP MCREATE`,
  `HELP OCREATE`, `HELP RLINK`, `HELP RSAVE`, `HELP SET` in game.
- [Area Building Guide](area-building-guide.md) -- the `.are` file format,
  for editing files directly or understanding what the commands write.
- [Operator Guide](operator-guide.md) -- running the live game.
