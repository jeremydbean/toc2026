# Mudlet default-game listing handoff

This is the maintainer handoff for requesting a Times of Chaos entry on
Mudlet's opening connection screen after the GMCP build is deployed publicly.

## Game metadata

- **Name:** Times of Chaos
- **Host:** `toc.jeremybean.com`
- **Port:** `9000`
- **Transport:** Telnet
- **Codebase:** Merc 2.1 / ROM 2.4, heavily customized
- **Repository:** <https://github.com/jeremydbean/toc2026>
- **Package:** <https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/TimesOfChaos.mpackage>
- **Starter map:** <https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/toc-newbie-map.xml>

Suggested short description:

> Times of Chaos is a long-running fantasy hack-and-slash MUD with more than
> 7,700 rooms, mortal progression through level 59, six classes, five races,
> remorting, quests,
> seasonal content, player castles, and a guided Mud School for new players.

## Mudlet checklist

- [x] `IAC GA` is sent after every playable prompt, so `isPrompt()` works.
- [x] GMCP option 201 is negotiated and subnegotiation is removed from normal
      command input.
- [x] `Room.Info` provides numeric room IDs, names, areas, environments, and
      visible exits for mapper tracking.
- [x] A 25-room MMP map covers the Mud School path from entry to graduation.
- [x] The official package embeds a mapper and HP, mana, movement, and
      experience gauges.
- [x] `Client.Map` is sent before `Client.GUI` as recommended by Mudlet.
- [x] `Client.GUI` provides automatic installation and semantic-versioned
      updates from the public repository.
- [x] Players can hide or restore the interface with the local Mudlet aliases
      `tocgui off` and `tocgui on`.
- [x] Deploy this build and restart the public game server.
- [ ] Test a clean Mudlet profile against the public host on Windows, macOS,
      or Linux and capture a screenshot for review.
- [ ] Contact the Mudlet team through <https://www.mudlet.org/contact/> or its
      Discord and request a default-game review.

## Deployment Verification: 2026-09-16

Commit `6241b8e` was deployed to the Windows-hosted production VM after a
stopped-state backup. All 1,231 tracked state files matched before and after
installation. Both services passed health checks, and the public-hostname
handshake verified GMCP, map/interface advertisements, ping, and clean login
input. The final Python suite ran 201 tests successfully with two optional
runtime skips; seven JavaScript console tests also passed separately.

A fresh Windows Mudlet 5.0.1 profile downloaded and displayed the ToC interface.
However, its first connection disconnected during the bundled generic mapper's
login-prompt probing. An authenticated in-game map/gauge check and clean review
screenshot remain outstanding. Do not treat interface installation alone as a
completed client review. An independent external TCP probe returned no result,
so the successful public-hostname connection remains a local-network test.

The review request has not been sent. Confirm the sender identity before
contacting Mudlet; never include credentials, player data, or private logs.

## Verification commands

From the repository root:

```bash
bash scripts/validate.sh
python3 scripts/build_mudlet_package.py --check
python3 scripts/test_mudlet_handshake.py 127.0.0.1 9000
```

The handshake probe does not create or modify a player character. Run it only
against a server built from this revision.

## Suggested contact message

> Hello! We have completed Mudlet integration for Times of Chaos and would
> like to request review for the default game list. The game is available at
> toc.jeremybean.com:9000. It sends Telnet GA at every prompt; provides GMCP
> Char.Vitals, Char.Status, and Room.Info; automatically supplies a mapped
> newbie area through Client.Map; and installs a versioned interface with
> gauges and an embedded mapper through Client.GUI. Source and reproducible
> package assets are in the public toc2026 repository. We would appreciate any
> review feedback or additional requirements.
