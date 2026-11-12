# Times of Chaos for Mudlet

Times of Chaos automatically offers this package and its world atlas to
GMCP-capable Mudlet clients: `Client.GUI` names the package and `Client.Map`
names `mudlet/toc-world-map.xml` on GitHub. The package provides:

- health, mana, movement, and experience gauges;
- an embedded mapper centered by `Room.Info` GMCP messages;
- the world atlas: every room of the shipped world except the ones listed
  below, laid out one Mudlet area per area file, with Mud School kept as
  area 1 so an older profile's map is not reshuffled;
- automatic mapping of rooms the atlas leaves out, as they are visited;
- the fog: the map shows only what the character knows (`Map.Known`,
  below), and the rest appears as it is explored or a map is learned;
- refresh of visited room names, areas, terrain, and visible exits after world
  updates, including removal or retargeting of stale exits; and
- automatic updates through `Client.GUI` version negotiation.

Players normally do not need to install anything manually. In Mudlet, leave
**Enable GMCP** and **Allow server to install script packages** enabled, create
a profile for `toc.jeremybean.com` port `9000`, and connect. The local Mudlet
alias `tocgui off` hides the interface and `tocgui on` restores it.
`tocgui status` reports the installed package version and whether GMCP data is
active. Mapping continues while the interface is hidden.

Package 1.5.12 adds the fog (owner, 2026-11-12: the map shows only rooms
you have been to, unless you hold the area's map, Dresden and the starting
areas excepted). The game sends `Map.Known` -- see "The fog" below -- and
the package takes every room the character does not know off the map,
keeping it aside in `toc-fog.lua` in the profile, and puts it back where the
atlas had it when it becomes known.

Package 1.5.13 corrects the fog and the doors against Mudlet's own source
(`TLuaInterpreterMapper.cpp`, `TRoom.cpp`): Mudlet keys doors `up` and
`down`, not `u` and `d`, so up and down doors were never drawn; deleting a
room takes the doors off its neighbours' exits into it, so a pass now reads
every room before deleting any, and a room left on the map keeps an
unexplored stub, with its door, where an exit leads into the fog. A
shrinking `Map.Known` -- a map taken away by staff GRANTMAP REVOKE --
fogs the rooms no longer known, like any other.

Package 1.5.14 and the atlas that ships with it redraw the map (owner,
2026-11-12, from a Mudlet 5.1.1 screenshot: "the way the layers look on the
map in mudlet is disorienting ... it's the map everywhere. dresden is a
mess"). Three things stacked layouts on top of each other:

- **Mudlet 5 draws the levels above and below.** In the same area it draws
  the rooms of the level below the one shown as filled grey squares and the
  level above as outlined squares (`TMapPainter.cpp`,
  `mDrawUpperLowerLevels`, on by default; 4.x draws neither). Over a city
  with sewers under it and towers over it, that is three maps laid across
  each other. The package turns it off at every start with
  `setConfig("showUpperLowerLevels", false)` (the key exists from Mudlet 5.0),
  so the map shows only the level you are on. It is a Mudlet-wide setting,
  not a profile's: `tocgui levels` turns it back on, and the choice is kept
  in `toc-settings.lua` in the profile so the package stops turning it off.
- **The atlas layout.** `scripts/build_mudlet_package.py` used to put a room
  whose square was taken on the nearest free one, which bent every exit
  around it and packed Dresden into a solid block where neighbouring squares
  were not neighbouring rooms. It now opens the level instead -- every room
  on it past that square moves one step on in the exit's direction -- so
  exits keep their direction and are only stretched; a second pass moves or
  swaps single rooms while that straightens exits, each connected part of an
  area is laid out on its own and the parts are packed in rows, and the level
  holding most of a part is z 0. 95% of the world's exits are drawn straight
  in their own direction (89% before), 91% of Dresden's (73%), and still no
  two rooms of an area share a square (the build refuses one). Loading a map
  replaces the profile's, so it is never done for you: a profile holding the
  old layout is told once a session to type `tocgui atlas`.
- **Hyrule's dungeons shared the overworld's area.** A plan from a dungeon
  map was drawn ten levels below the overworld per dungeon, and a room
  walked into one step from the room walked from -- down from a dungeon's
  gate, so under the overworld, with the other dungeons beside it. Each
  dungeon is now a map area of its own, `Hyrule: Level 1 (The Eagle)` to
  `Hyrule: Level 9 (Death Mountain)`, laid out on its floor plan (column x,
  row -y), cellars on z -1 under the room they open from. The game sends the
  square: `Hyrule.MapRoom`'s `area` is the dungeon's, and `Room.Info` for a
  dungeon room carries `"map": {"area", "x", "y", "z"}` (`hyrule_map_place`
  in `src/hyrule.c`), so a room walked into and the same room drawn from the
  map land on one square, and a dungeon room drawn under the overworld by an
  older package is moved on the next step into it. `Room.Info`'s own `area`
  stays the game's name. The overworld is `Killum Hyrule` alone.

The package also no longer moves a room into the area `Room.Info` names once
the room is on the map: the atlas's area and square stand (a seasonal copy
renames its area), and only a room it creates, or one `Room.Info` places
with `map`, takes the game's.

Package 1.5.15 (owner, 2026-11-12; review findings reproduced in
`tests/mudlet_ui_spec.lua` and `tests/mudlet_fog_spec.lua`):

- **A door on a walk no longer stops it.** The walker opens a door
  `Room.Info` says is shut before the step; the game answers the OPEN with a
  fresh `Room.Info` for the room you still stand in, and that used to count
  as arriving in the wrong room. Only a changed room number is an arrival
  now; a `Room.Info` for the same room still redraws its doors, exits,
  marks and buttons. The watchdog takes a step that landed unannounced as an
  arrival, and tries a door (never for a special exit like `enter portal`)
  once before giving up.
- **Exit buttons open doors.** A button is a step through the same
  `tocMudlet.move` the walker uses: a closed door is opened first, a locked
  one is tried and the package says to `unlock` it. Closed buttons are amber
  with `+`, locked ones red with `#`; the door is read when the button is
  pressed.
- **Floors above and below are never changed silently.** Mudlet's "Draw
  rooms on upper and lower levels" (`showUpperLowerLevels`) is Mudlet's
  setting, shared by every profile. The package now hides those floors once
  per profile and says so -- what it was (read with `getConfig`; when it
  cannot be read, it says that instead of guessing), that it is now off, and
  how to change it -- and remembers the old value. `tocgui levels
  on|off|toggle` is the player's choice from then on and the package never
  touches the setting again; `tocgui levels original` puts back the value it
  found and `tocgui levels status` reports. A 1.5.13/1.5.14 toggle carries
  over as a choice. All of it is kept in `toc-settings.lua`.
- **A floor strip over the map** names the map area and floor (z) you are
  on, and says when the floors above and below are drawn.
- **`tocgui mapcheck`**: the room, map area and square; the floors setting
  and the player's choice; the atlas layout the package draws against the
  one this profile holds; rooms sharing a square in this area (5,000 rooms
  at most); and exits within four steps (80 rooms at most) drawn at a wrong
  angle, to another floor, or stretched past three squares -- five examples
  of each at most.
- **`tocgui atlas` never replaces the map on one word.** Alone it says what
  is lost; `tocgui atlas backup` saves the current map (Mudlet's `saveMap`)
  as `toc-map-backup-<date>.dat` in the profile's folder; `tocgui atlas
  confirm` saves one and loads the atlas only if the save landed; `tocgui
  atlas force` loads without a backup.
- **The Items pane says when its list is cut.** `Char.Items` now carries
  `inventory_total`, `equipment_total`, `truncated` and
  `equipment_truncated`; the pane counts what you carry and says how many
  are not shown.

The atlas layout was measured before this release and left alone: 7,515
rooms, no two of an area on one square, 95.0% of 16,448 exits drawn straight;
893 squares are shared by rooms on different floors of one area (2,220
rooms), of which 769 rooms sit over or under a room they are joined to by up
or down -- staircases, drawn where they belong -- and the rest only matter
when the floors above and below are drawn, which they no longer are unless
the player asks.

Package 1.5.8 delivers the 24 extended channel colors added to COLOR. The
version increase makes existing 1.5.7 installations receive the updated chat
palette automatically on reconnect, after the server is updated.

Package 1.2.0 adds the panels the new GMCP feeds were for.

- **Target strip.** Who you are fighting, with a bar for how badly
  they are hurt. The game says this in prose; a bar says it better.
- **Quest strip.** What the quest wants and the timer counting down,
  so an emergency contract's five minutes are visible without asking
  for them. Amber at three minutes, red at one.
- **Tabs below the map.** Chat, Tells, Here (who is in the room, with
  aggressives marked) and Items (worn and carried). Tells get their
  own tab so they are not lost among gossip.
- **Clickable exits** along the bottom bar, one button per way out.
- **Achievement notices** over the map for a few seconds when you
  earn one.

Package 1.1.1 fixes the chat pane printing its colour tags as text.

Package 1.1.0 adds a chat pane, an affects line, doors and room
labels on the map, and walking to a named place.

- **Chat pane.** Channels and tells appear in their own scrollback
  below the map, coloured per channel. It shows exactly what you
  heard: the game emits each line where it delivers it, so a yell
  from another area or a channel you have switched off never reaches
  it.
- **Affects line.** What is currently on you, shortest duration
  first, with anything about to lapse in orange.
- **Doors and labels.** The map draws doors, and marks a room with
  what it is for: `$` a shop, `?` a questmaster, `+` a healer, `P`
  practice, `T` training, `X` a death trap. The walker opens a door
  it knows is shut instead of bumping into it.
- **`walk <name>`.** `walk stop` (or `stop`) ends a walk. `walk routes` fetches the published route list,
  then `walk thalos` or `walk wyvern` walks there if it is on your
  map, or prints the published route from the Oak Tree Square if it
  is not.

Package 1.5.11 stops a walk on `stop` or `stop walk` as well as `walk
stop`: players typed both and were told "Huh?" while the walk went on.
When the package is not walking, the line goes to the game, whose STOP
ends a WALKTO.

Package 1.5.10 makes the quest strip clickable again for players: it
walks to the quest's area, as `walk quest` does. It had asked for the
target room's number, which the game sends to staff alone.

Package 1.5.9 removes Mudlet's generic mapper from a profile that has it,
once, and says so. Setting `mudlet.mapper_script` (1.0.8) never silenced
it: the generic mapper sets that flag itself, and older copies search for
a prompt at every install and print "Prompt not auto-detected, use 'map
prompt' to set a prompt pattern". It reads the prompt to track movement on
the same map this package draws from GMCP, so the two cannot run together.
Removing the package keeps the map.

Package 1.0.9 adds click-to-walk. Click a room on the map, or type
`walk <vnum>`, and the character walks there one room at a time. Each
step is sent when GMCP confirms you arrived in the room the route
expected, so the walk keeps pace with the server and stops the moment
something goes wrong -- a mob in the way, a recall, being dragged off.
A shut door is opened and retried once. `walk stop` breaks off, and
`walk` on its own reports progress.

Package 1.0.8 sets `mudlet.mapper_script`, meant to stop Mudlet's own
mapper printing "Prompt not auto-detected"; it did not, and 1.5.9 removes
the generic mapper instead (above).

Package 1.0.7 capitalises the race and class shown in the identity panel.
`Char.Status` carries them the way the game stores them -- "half-elf",
"cleric" -- because GMCP is data rather than presentation, so the panel
title-cases them on the way to the screen.

Package 1.0.6 restores mapper visibility and stacking on refresh, resize,
atlas import, and `tocgui on`. If the gauges work but the map pane is blank,
`tocgui on` repairs the display without replacing your map. `tocgui off`
remains respected by delayed refreshes and window resizing.

### What the atlas holds

`scripts/build_mudlet_package.py` builds the atlas from the area files
through `webadmin/area_parser.py`. It holds every room the base world lists
(7,515 of 7,766 on 2026-11-12; recount with the script) except:

- **death traps** (`ROOM_DT`), and every exit into one, so the atlas does not
  give them away -- GMCP still sends the room when a character walks in, and
  the mapper learns it then;
- **Hyrule's nine dungeons** (their vnum runs from
  `data/hyrule_first_quest.json`). A dungeon is drawn dynamically: when the
  character holds that dungeon's map, the game sends its plan room by room
  as `Hyrule.MapRoom` and then `Hyrule.MapDone`, and the package places it
  in a map area of the dungeon's own on its floor plan; otherwise it is
  mapped room by room as it is walked, each room on the same square, from
  `Room.Info`'s `map`. Hyrule's overworld is on the atlas from the start;
- the seasonal copies (`*_halloween.are`, `*_xmas.are`), which are not in
  `area.lst`: the atlas is the base world.

The script reads the area lists with `AreaParser.parse_all()`'s default,
which includes areas built in game (`area/built/`) when that directory holds
any at build time; the committed atlas is built from a checkout, where it
holds none.

It draws the directional exits between rooms it holds, cross-area exits
included. It takes them from the area files, so it does not know which are
secret in game: an exit that is secret there is drawn like any other. Live
mapping is different -- `Room.Info` never sends a secret exit or a room the
character cannot see. Portals, `enter` routes, teleports, and scripted
movement are not directional exits and are not drawn as links; the walker
reads them from the published routes (`webadmin/directions.json`) instead.

How it is laid out (`layout_area`; 2026-11-12): one Mudlet area per area
file, each connected part of it grown from its best-connected room along the
exits that come back the way they went first, a taken square answered by
opening the level rather than bending the exit, then single rooms moved or
swapped while that straightens exits; the parts are packed in rows, and each
part's busiest level is z 0. Mudlet draws a planar exit as a straight line to
wherever its room sits in the area (on any level) and up and down as marks in
the room, so "straight" is what `exit_drawn_straight` counts and
`tests/test_mudlet_map_layout.py` holds the share of it (95% world-wide, 91%
in Dresden), with no two rooms of an area on one square. Where the world's
own geometry disagrees -- a loop whose sides differ, an exit that does not
come back -- an exit is still drawn at an angle.

Mudlet only installs a server's map into a profile that has none, so a
profile that was mapping before the atlas existed keeps its own map.
`tocgui atlas confirm` saves a backup of the profile's map and then
downloads the current atlas and **replaces** the profile's saved map with
it -- deliberately never automatic, and `tocgui atlas` alone only explains
it (1.5.15). Use it, or
Mudlet's mapper tools, to clear a room that was deleted and can no longer
be revisited. Map data belongs to the Mudlet profile, not to a ToC character
file. Release notes above this section are a dated history of the package,
not a description of the current one.

### The fog

What a character knows is the game's to say (`src/maps.c`): every room they
have walked into, every room of a region whose whole map they hold -- an
area's, from READ of a map item or staff GRANTMAP, or a Hyrule dungeon's,
from its NES map -- and all of Dresden, Mud School, Limbo and the training
yard. Staff know everything. The package subscribes with `"Map 1"` in
`Core.Supports` and the game sends, at the first prompt of a connection and
again whenever a map is learned:

```
Map.Known {"part":1,"parts":2,"all":false,"rooms":[[3700,3722],[4200,4290]]}
Map.Known {"part":2,"parts":2,"all":false,"rooms":[[6000,6070]]}
```

Each run holds known rooms only (vnums no room has are skipped over); each
part fits one GMCP message; the package acts on the last part, and `"all":
true` (an immortal-level character) means every room. A room walked into after that is known from
its `Room.Info`, and a Hyrule plan room from `Hyrule.MapRoom`.

The package deletes each unknown room from the profile's map and keeps it,
with its coordinates, area, name, terrain, mark, doors and both ends of its
exits, in `toc-fog.lua` beside the map; putting it back relinks it to every
neighbour that is on the map and leaves a note on any still in the fog.
`tocgui atlas` (or Mudlet's own download on a first connection) starts the
fog again from the whole atlas. Characters sharing a profile each see their
own: the next `Map.Known` brings back what they know and hides the rest.
`tests/mudlet_fog_spec.lua` plays it against a fake mapper.

For local development, connect to `localhost` port `9000`. To build or verify
the committed assets:

```bash
python3 scripts/build_mudlet_package.py
python3 scripts/build_mudlet_package.py --check
```

The generated `TimesOfChaos.mpackage` is a deterministic ZIP containing
`config.lua` and `TimesOfChaos.xml`. The generated MMP file is
`toc-world-map.xml`.
