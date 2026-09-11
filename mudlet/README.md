# Times of Chaos for Mudlet

Times of Chaos automatically offers this package and the Mud School starter
map to GMCP-capable Mudlet clients. The package provides:

- health, mana, movement, and experience gauges;
- an embedded mapper centered by `Room.Info` GMCP messages;
- the mapped Mud School path from character creation through graduation;
- automatic mapping of newly visited rooms beyond the starter area; and
- automatic updates through `Client.GUI` version negotiation.

Players normally do not need to install anything manually. In Mudlet, leave
**Enable GMCP** and **Allow server to install script packages** enabled, create
a profile for `toc.jeremybean.com` port `9000`, and connect. The local Mudlet
alias `tocgui off` hides the interface and `tocgui on` restores it.

For local development, connect to `localhost` port `9000`. To build or verify
the committed assets:

```bash
python3 scripts/build_mudlet_package.py
python3 scripts/build_mudlet_package.py --check
```

The generated `TimesOfChaos.mpackage` is a deterministic ZIP containing
`config.lua` and `TimesOfChaos.xml`. The generated MMP file is
`toc-newbie-map.xml`.
