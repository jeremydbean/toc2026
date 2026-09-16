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
`toc-newbie-map.xml`.
