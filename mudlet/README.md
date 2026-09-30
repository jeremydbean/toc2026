# Times of Chaos for Mudlet

Times of Chaos automatically offers this package and the Mud School starter
map to GMCP-capable Mudlet clients. The package provides:

- health, mana, movement, and experience gauges;
- an embedded mapper centered by `Room.Info` GMCP messages;
- the mapped Mud School path from character creation through graduation;
- automatic mapping of newly visited rooms beyond the starter area;
- refresh of visited room names, areas, terrain, and visible exits after world
  updates, including removal or retargeting of stale exits; and
- automatic updates through `Client.GUI` version negotiation.

Players normally do not need to install anything manually. In Mudlet, leave
**Enable GMCP** and **Allow server to install script packages** enabled, create
a profile for `toc.jeremybean.com` port `9000`, and connect. The local Mudlet
alias `tocgui off` hides the interface and `tocgui on` restores it.
`tocgui status` reports the installed package version and whether GMCP data is
active. Mapping continues while the interface is hidden.

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
- **`walk <name>`.** `walk routes` fetches the published route list,
  then `walk thalos` or `walk wyvern` walks there if it is on your
  map, or prints the published route from the Oak Tree Square if it
  is not.

Package 1.0.9 adds click-to-walk. Click a room on the map, or type
`walk <vnum>`, and the character walks there one room at a time. Each
step is sent when GMCP confirms you arrived in the room the route
expected, so the walk keeps pace with the server and stops the moment
something goes wrong -- a mob in the way, a recall, being dragged off.
A shut door is opened and retried once. `walk stop` breaks off, and
`walk` on its own reports progress.

Package 1.0.8 sets `mudlet.mapper_script`, which stops Mudlet's own
mapper printing "Prompt not auto-detected, use 'map prompt' to set a
prompt pattern" when the map opens. This package maps from GMCP
`Room.Info` and never reads the prompt, so that warning never applied.

Package 1.0.7 capitalises the race and class shown in the identity panel.
`Char.Status` carries them the way the game stores them -- "half-elf",
"cleric" -- because GMCP is data rather than presentation, so the panel
title-cases them on the way to the screen.

Package 1.0.6 restores mapper visibility and stacking on refresh, resize,
atlas import, and `tocgui on`. If the gauges work but the map pane is blank,
`tocgui on` repairs the display without replacing your map. `tocgui off`
remains respected by delayed refreshes and window resizing.

The map is intentionally exploration-based. `Room.Info` never reveals secret
exits or rooms the character cannot see. Portals, `enter` routes, teleports,
and scripted movement may not produce ordinary directional map links. A room
that has been deleted and can no longer be revisited can remain in the local
Mudlet map; use Mudlet's mapper tools to remove it or re-download the starter
map when a clean profile is preferable. Map data belongs to the Mudlet profile,
not to a ToC character file.

For local development, connect to `localhost` port `9000`. To build or verify
the committed assets:

```bash
python3 scripts/build_mudlet_package.py
python3 scripts/build_mudlet_package.py --check
```

The generated `TimesOfChaos.mpackage` is a deterministic ZIP containing
`config.lua` and `TimesOfChaos.xml`. The generated MMP file is
`toc-world-map.xml`.
