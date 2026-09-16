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
- **World map:** <https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/toc-world-map.xml>

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
- [x] A full-world MMP map ships all 7,781 rooms across 92 areas, laid out
      per area with no two rooms sharing a square.
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

## External Reachability And Login Probe: 2026-09-16

An independent external TCP probe now succeeds. check-host.net reached
`toc.jeremybean.com:9000` from all eight nodes tried -- Miami 25 ms,
Vancouver 91 ms, Frankfurt 121 ms, Stockholm 126 ms, Chisinau 220 ms, Tel
Aviv 347 ms, and two in Jakarta around 1.3 s. The same service could not
reach port 9001 from any of five nodes, which is the intended result: the
dashboard must not be publicly exposed. Note that a probe from the host
network proves nothing here, because the site's public address is also the
A record, so any local connection is hairpin routed.

The cause of the Mudlet disconnect was found and fixed: a blank line at the
name prompt closed the socket with no message, which is what the bundled
generic mapper's login-prompt probing triggers. The prompt is now reissued.
A clean Mudlet profile should be retried against the public host; the
authenticated in-game map/gauge check and review screenshot are still
outstanding, and the review request has still not been sent.

## Deployment: 2026-09-16, commit a16edb9

The login-probe fix is live on the public server. Cutover followed the
Windows production runbook: stopped-state backup
(`state-20260916T180038Z.tar.gz`, with SHA-256 sidecar), a code rollback copy
of the previous binary, maintenance marker, service stop, binary install,
state comparison, then restart.

Only the compiled `merc` binary changed. The three commits since the previous
deployment touch `src/` alone; no area data, dashboard, or Mudlet asset was
altered. Player state was byte-identical across the swap: 1,209 files, the
same combined SHA-256 before and after.

Verified against the public host afterwards: a bare newline and a
whitespace-only line both answer `Name:` instead of dropping the connection,
prompts still carry `IAC GA`, and `scripts/test_mudlet_handshake.py` passes
end to end. check-host.net reached port 9000 from five of six nodes; the one
timeout was Saint Petersburg, a routing path that also fails to other US
residential addresses, and eight of eight nodes succeeded earlier.

Still outstanding: retry a clean Mudlet profile now that the disconnect is
fixed, capture the authenticated in-game map and gauge screenshot, and send
the review request. Installing the interface is not the same as a completed
client review.
