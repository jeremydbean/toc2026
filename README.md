# Times of Chaos (ToC)

Times of Chaos is a long-running text multiplayer role-playing game descended
from DikuMUD, Merc 2.1, and ROM 2.4. The repository contains the C game server,
the complete world database, a FastAPI operations dashboard, Docker packaging,
validation tools, tests, and the source data used to generate Hyrule: First
Quest.

The current checked-in world parses as **102 listed area files, 7,787 rooms,
2,494 mobiles, and 3,721 objects**. Player progression spans six classes, five
playable races, four optional cross-class guilds, five remorts, questing, group
play, player killing, permanent achievements, advanced equipment comparison,
and a large collection of hand-built areas.

> **Where the live game runs:** the public server is an Oracle Cloud
> instance (Always Free ARM, Ubuntu 24.04) that `toc.jeremybean.com`
> resolves to. It moved there on 2026-10-01; the earlier Raspberry Pi
> (died 2026-09-29) and Hyper-V VM (powered off) are gone. Operators and
> automated sessions should read [Disaster Recovery](wiki/disaster-recovery.md)
> for the deploy command, backups, and rebuild procedure. The Pi and
> Windows material below is kept only as a generic self-hosting reference.

> **Before hosting or playing:** ToC uses plain Telnet and legacy DES `crypt(3)`
> password hashes. Traffic is not encrypted, and only the first eight password
> bytes affect a traditional DES hash. Never reuse a real-world password. Hosts
> should read [SECURITY.md](SECURITY.md) before exposing either port. The public
> repository also contains legacy character hashes; they must be considered
> exposed credentials.

## Start Here

| Audience | Best starting point |
|---|---|
| New player | [Player Guide](wiki/player-guide.md) |
| Returning player | [Player Command Reference](wiki/player-command-reference.md) |
| Mudlet player | [Official Mudlet package](mudlet/README.md) |
| Running your own copy | [Install Guide](wiki/install-guide.md) |
| Server host | [Hosting Guide](wiki/hosting-guide.md) |
| Live production host, deploys, or something broken | [Disaster Recovery](wiki/disaster-recovery.md) (Oracle Cloud) |
| Working from a new/other machine | [New Machine Setup](wiki/new-machine-setup.md) |
| Retired Windows VM host (history) | [Windows Production Runbook](wiki/windows-production-hosting.md) |
| Mudlet listing submission | [Listing Handoff](mudlet/listing-submission.md) |
| Immortal/operator | [Operator Guide](wiki/operator-guide.md) |
| Developer | [Developer Guide](wiki/developer-guide.md) and [CONTRIBUTING.md](CONTRIBUTING.md) |
| Area builder | [Area Building Guide](wiki/area-building-guide.md) |
| Immortal building in game | [In-Game Building Guide](wiki/building-guide.md) |
| Hyrule player or builder | [Hyrule: First Quest](wiki/hyrule-area.md) |
| Achievement hunter | [Achievement System](wiki/achievements.md) |
| Security reviewer | [Security Policy and Deployment Guide](SECURITY.md) |

The [wiki home page](wiki/Home.md) indexes all current and historical
documentation.

## What Is Included

- A native C server with the traditional ROM command loop, combat, magic,
  skills, quests, guilds, remorts, economy, banks, gambling, mounts, ranged
  combat, traps, scripts, seasons, and immortal tools.
- A world loaded from `area/area.lst`, including the generated 447-room Hyrule
  campaign with all nine First Quest dungeons.
- Advanced in-game `compare` analysis that models a player's complete loadout,
  class, guild, level, skills, spells, and selected gameplay focus.
- A permanent 203-achievement progression system with points, earned dates,
  hidden discoveries, live progress, retroactive milestones, group boss credit,
  world bosses, rare relics, crafting, banking and casino feats, unusual deaths,
  and complete Hyrule dungeon, map, compass, shard, and boss tracking.
- A FastAPI dashboard for world browsing, area health, maps, player inspection,
  logs, backups, server commands, protected read-only host telemetry with live
  CPU, memory, swap, network, disk, and temperature monitoring, and a
  browser-to-MUD WebSocket bridge.
- First-class Mudlet support with GA-framed prompts, GMCP vitals and room data,
  an automatically installed interface, and a mapped Mud School tutorial.
- Automated player snapshots, scheduled archive backups, diagnostics, native
  area validation, Python reference checks, area-health linting, and unit tests.
- Docker, Docker Compose, Make, CMake, Windows/WSL validation, and GitHub Actions
  workflows.
- A low-memory native Raspberry Pi appliance profile with headless systemd
  startup, process and hardware watchdogs, end-to-end health repair, bounded
  reboot/rebuild recovery, encrypted off-host player snapshots, guarded Git and
  operating-system updates in a weekly maintenance window, automatic Namecheap
  Dynamic DNS, an onboard ACT LED status signal, and direct private-LAN browser
  play and administration.

## Easy Install

One command installs everything missing, starts the game and prints where to
play. It is safe to rerun, keeps your characters and settings, and works the
same way on every platform. The full walkthrough -- options, updating,
backups, letting others connect, troubleshooting -- is the
**[Install Guide](wiki/install-guide.md)**.

| Platform | Paste this |
|---|---|
| Windows 10/11 (PowerShell) | `& ([scriptblock]::Create((irm https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_windows.ps1)))` |
| macOS (Terminal) | `curl -fsSLo /tmp/toc-install.sh https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_macos.sh && bash /tmp/toc-install.sh` |
| Linux (Debian, Ubuntu, Raspberry Pi OS, Fedora, RHEL, Arch, openSUSE) | `curl -fsSLo /tmp/toc-install.sh https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_linux.sh && bash /tmp/toc-install.sh` |

From a checkout you already have: double-click `Install-ToC.cmd` (Windows) or
`Install-ToC.command` (macOS), or run `./install.sh` / `.\install.ps1`.

- **Docker or native.** The default runs in Docker (Docker Desktop on Windows
  and macOS), from a prebuilt image when one is published and built locally
  when not. On Linux and macOS, add `--native` to compile and run without
  Docker; on a systemd host the game then starts at boot as a service.
- **Local by default.** Only this computer can connect. Add `--public`
  (Windows: `-Public`, or `-Network Public` for `install.ps1`) to open the
  game port to others; the dashboard always stays local.
- **Your data in one place.** Characters, logs and the live world -- notes,
  reports, bans, builders' areas -- live in `state/`, the dashboard token in
  `.env`. Updates replace the code and keep both.
- **Become the administrator.** Create a character, `QUIT`, then
  `./toc.sh promote <name>`.

Day to day (`.\toc.ps1` on Windows; `Start-ToC.cmd` / `Start-ToC.command`
start the game and open it):

| Command | Does |
|---|---|
| `./toc.sh start` / `stop` / `restart` | Run it; a stop saves every player first |
| `./toc.sh play` / `admin` | Open the web client / dashboard |
| `./toc.sh status` / `logs` / `doctor` | See what it is doing; check the install |
| `./toc.sh update` | Update to the newest version |
| `./toc.sh promote <name>` | Make a character the implementor |
| `./toc.sh backup` / `restore <archive>` | Archive or restore `.env` and `state/` |
| `./toc.sh uninstall [--purge]` | Remove it, keeping (or deleting) the data |

Open the web client at `http://127.0.0.1:9001/client`, or connect a MUD client
to `localhost:9000`. The administration dashboard is `http://127.0.0.1:9001`;
on this computer it unlocks itself, elsewhere it asks for `WEB_ADMIN_TOKEN`
from `.env`, which the installers never print or replace.

To reach the live public server instead of a local copy, use
`http://toc.jeremybean.com:9001/client` for the browser client and
`http://toc.jeremybean.com:9001/` for the dashboard. Keep the `:9001`
port -- a bare URL targets port 80, where ToC does not listen. The game
itself is `toc.jeremybean.com` port `9000` for any MUD client.

For a dedicated headless Raspberry Pi that runs only ToC, the native systemd
appliance adds watchdogs, bounded recovery, off-device player backups,
validated `main` updates and a weekly OS maintenance window. See the
[Raspberry Pi appliance runbook](deploy/README.md) and
[`deploy/pi.env.example`](deploy/pi.env.example).

### Mudlet (Recommended Desktop Client)

Leave **Enable GMCP** and **Allow server to install script packages** enabled,
then connect to `toc.jeremybean.com` port `9000` (or `localhost:9000` for a
local server). The server automatically supplies the official package and Mud
School map. The interface includes live health, mana, movement, and experience
gauges plus an embedded mapper; `Room.Info` continues mapping as the character
explores beyond the tutorial. Revisited rooms refresh their names, areas,
terrain, and visible exits, so removed or retargeted exits do not remain stale.

Inside Mudlet, `tocgui off` hides the interface, `tocgui on` restores it, and
`tocgui status` reports its version and GMCP state. Package sources, manual
installation notes, and reproducible build instructions are in
[`mudlet/README.md`](mudlet/README.md).

Docker Desktop can require acceptance of its own subscription terms on first
launch. The project cannot accept those terms for the host. Docker documents
its current [Windows installation requirements](https://docs.docker.com/desktop/setup/install/windows-install/)
and [macOS requirements](https://docs.docker.com/desktop/setup/install/mac-install/).

## Building From Source

This section is for developers working on the code. To *run* the game
natively, `./install.sh --native` does all of this and keeps the game's data
out of the checkout. The native runtime is POSIX-oriented: Linux, macOS, or
WSL 2. Direct native Windows builds are not a supported path.

### Ubuntu or Debian

```bash
sudo apt update
sudo apt install build-essential libcrypt-dev zlib1g-dev python3 python3-venv

git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make

cd area
../merc --check-area
cd ..
./startup.sh 9000
```

`startup.sh` runs from the repository root, changes into `area/`, writes to
`log/toc.log`, restarts after an unexpected exit, and stops after an intentional
in-game `shutdown`. Run this way, the game writes into the checkout itself
(`player/`, `log/`, `area/`), some of which git tracks; an installed copy
keeps all of that in `state/` instead.

Set `TOC_BIND_ADDRESS=127.0.0.1` to keep the game on one interface; unset, it
listens on all of them.

### Fedora, RHEL, or Rocky Linux

Install `gcc`, `make`, `libxcrypt-devel`, `zlib-devel`, `python3`, and
`python3-pip`, then use
the same `make`, validation, and `startup.sh` commands.

### macOS

```bash
xcode-select --install
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make
cd area
../merc --check-area
../merc 9000
```

Docker remains the recommended fallback if the local macOS toolchain does not
provide the expected legacy C interfaces.

### CMake Alternative

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
cd area
../bin/rom --check-area
../bin/rom 9000
```

For a debug sanitizer build:

```bash
cmake -S . -B build-sanitize \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_SANITIZERS=ON
cmake --build build-sanitize
```

The Make build writes `merc` at the repository root. CMake writes `bin/rom`.
Both must be launched with `area/` as the current directory because legacy data
paths are relative to that directory.

## Native Web Client And Dashboard

Run this in a second terminal from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r webadmin/requirements.txt
export WEB_ADMIN_TOKEN="$(openssl rand -hex 32)"
python -m webadmin.server \
  --host 127.0.0.1 \
  --port 9001 \
  --mud-host 127.0.0.1 \
  --mud-port 9000 \
  --queue area/webadmin.queue \
  --log-file log/toc.log \
  --event-log-file log/webadmin-events.tsv \
  --area-path area \
  --backup-path backups \
  --player-path player
```

Windows users can activate with `.\.venv\Scripts\Activate.ps1` and use the
same `python -m webadmin.server` arguments. Open `/client` to play and `/` to
administer. The game itself should still run in Docker or WSL.

## Runtime Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `TOC_MODE` | `docker` | Installed copies: `docker` or `native` |
| `TOC_STATE` | `./state` | Installed copies: the folder holding everything the game writes |
| `TOC_IMAGE` | `ghcr.io/jeremydbean/toc2026:latest` | Docker: the image to run, pulled or built under this name |
| `TOC_BUILD` | unset | Docker: `local` always builds the image from the checkout |
| `TOC_BASE_IMAGE` / `TOC_BUILD_NETWORK` | `ubuntu:24.04` / `default` | Docker builds behind a mirror or proxy |
| `TOC_BIND_ADDRESS` | unset | The one IPv4 address the game listens on (native installs set it from `MUD_BIND`); unset listens on all |
| `MUD_BIND` | `127.0.0.1` | Host interface for the published game port; use `0.0.0.0` for remote players |
| `MUD_PORT` | `9000` | Game port published on the host |
| `MUD_HOST` | `127.0.0.1` | Game host used by the dashboard health check and browser console |
| `WEB_ADMIN_BIND` | `127.0.0.1` | Host interface for the dashboard; keep loopback or on a trusted private network |
| `WEB_ADMIN_PORT` | `9001` | Dashboard port published on the host |
| `WEB_ADMIN_ENABLED` | `1` | Set to `0` to skip the dashboard in Docker |
| `WEB_ADMIN_HOST` | `0.0.0.0` | Dashboard bind address in Docker |
| `WEB_ADMIN_TOKEN` | unset | Shared secret for operational API routes; unset disables them |
| `WEB_ADMIN_LOCAL_UNLOCK` | `1` in generated `.env` | Auto-unlock local browser sessions only while `WEB_ADMIN_BIND` and the page host are loopback |
| `WEB_ADMIN_HOST_STATUS` | `0` | Enables the protected read-only host service, timer, boot, live resource, repository, and bounded journal view |
| `TOC_UPDATE_REQUEST_PATH` | unset | Host-managed request file for the protected update action; unset disables it |
| `TOC_REPOSITORY_ROOT` | repository root | Checkout inspected by host status; never accepts a browser-supplied path |
| `TOC_DEPLOYED_COMMIT_FILE` | `/var/lib/toc2026/deployed-commit` | Deployment marker read by host status |
| `WEB_ALLOWED_ORIGINS` | unset | Additional comma-separated origins allowed to open game/log WebSockets |
| `TOC_UID` | host user/`1000` | Numeric user ID used for writable container state |
| `TOC_GID` | host group/`1000` | Numeric group ID used for writable container state |
| `QUEUE_PATH` | `area/webadmin.queue` | Dashboard-to-game command queue |
| `LOG_FILE` | `log/toc.log` | Dashboard log source |
| `EVENT_LOG_FILE` | `log/webadmin-events.tsv` | Structured Server Info and WizInfo activity source |
| `AREA_PATH` | `area` | Dashboard area-parser source |
| `BACKUP_PATH` | `backups` | Dashboard backup archive directory |
| `PLAYER_PATH` | `player` | Dashboard player-file directory |

Compose always runs the game and dashboard internally on ports 9000 and 9001;
`MUD_PORT` and `WEB_ADMIN_PORT` change only the host-facing ports. The Hosting
Guide documents direct-image entrypoint modes, bind mounts, firewalls, reverse
proxies, service management, upgrades, and rollback procedures.

The Raspberry Pi appliance is deliberately different from the Compose default:
it runs natively under systemd and uses the private-LAN values in
`deploy/pi.env.example`. Its admin token survives reboots and automatic updates
because the private `.env` is not replaced.

## Persistent Data

An installed copy keeps every path the game writes in one folder, `state/`
(`TOC_STATE`), beside the private `.env`; the checkout holds code only, so
an update can always replace it. Docker mounts these as the container's
`/app/*`; a native install runs the game from `state/area` with `state/merc`.

| Path | Contents | Back up? |
|---|---|---|
| `state/player/` | Character files and `versions/` snapshots | Yes, sensitive |
| `state/gods/` | Immortal state | Yes, sensitive |
| `state/heroes/` | Hero state | Yes |
| `state/area/` | The live world: notes, reports, max-load counts, bans, PK standings, builders' areas | Yes |
| `state/corpse/` | Recoverable player corpses | Yes |
| `state/backups/` | The game's compressed player archives | Yes, sensitive |
| `state/log/` | Server logs and journals | As required |
| `.env` | Settings and the dashboard token | Yes, secret |

`./toc.sh backup` archives `.env` and `state/` after asking the game to save
everyone; `./toc.sh restore` puts an archive back. Installations from before
2026-10-21 kept these in the checkout's own `player/`, `gods/`, `heroes/` and
`log/` (and, under Docker, the live world inside the container); the first
start of the new version moves them into `state/`. A game run by hand from
the checkout (`startup.sh`) still writes in the checkout.

The game creates a player archive every four hours and a daily archive every 24
hours, pruning archives older than 30 days. Player saves also retain up to 30
per-character snapshots, no more often than every 30 minutes. These local
copies are not an off-site or encrypted backup strategy.

## Player Progression At A Glance

- Playable classes: Mage, Cleric, Thief, Warrior, Monk, and Necromancer.
- Playable races: Human, Elf, Dwarf, Hobbit, and Saurian.
- Hero status begins at level 51.
- A first-life character remorts at level 54. Later remort thresholds are
  levels 55, 56, 57, and 58. After five remorts, mortal progression ends at
  level 59.
- Levels 60 through 70 are immortal/staff trust levels, not normal player
  progression.
- Characters should choose a guild by level 5. A guildless character is placed
  into the guild matching their class at level 6.
- Monk is limited to Human or Dwarf; Necromancer is limited to Human or Elf.

Use in-game `help`, `commands`, `skills`, `spells`, `groups`, `gainlist`, and
`teachlist` for the live character-specific view. The Player Guide explains
creation, movement, combat, leveling, equipment, economy, social systems,
quests, guilds, remorts, Hyrule, death, saving, and troubleshooting.

## Web Client, Dashboard, And API

The play-first web client provides an ANSI terminal, safe password entry,
history, aliases, quick movement controls, transcripts, and an authenticated
administration panel with a live, filterable Server Info and WizInfo feed. The
full dashboard can browse areas, maps, rooms,
mobiles, objects, gear, player files, live game status, logs, backups, and
area-health findings. Its Operations view also reports command-queue depth,
backup freshness, recent player saves, and searchable Server Info/WizInfo
activity. Both interfaces use the same WebSocket bridge to the game port.
Large world tables use server-side search and pagination instead of rendering
the entire database at once.

Operational routes such as log access, command queueing, backup, reload,
wizinfo, shutdown, and player-save access require `X-Admin-Token`. Dashboard
`reload` refreshes the Python parser's view of area files; it does not
hot-reload the live C game world.

See the [Game Client Guide](wiki/game-client-guide.md) for play and embedded
administration, the [Web Admin Guide](wiki/web-admin-guide.md) for the full
operations interface, the [Hosting Guide](wiki/hosting-guide.md) for the
endpoint and authentication matrix, and the [Operator Guide](wiki/operator-guide.md)
for normal operating procedures.

## Development And Validation

### Windows PowerShell With WSL

```powershell
.\scripts\validate.ps1

# Include a short live startup smoke test.
.\scripts\validate.ps1 -RunSmoke

# Select a non-default WSL distribution.
.\scripts\validate.ps1 -Distro Ubuntu-24.04
```

### Linux, macOS, Or CI

```bash
bash scripts/validate.sh
```

The full suite performs a normal C build, strict-warning build, native area
load, Python syntax checks, area reference checks, area-health linting, unit
tests, whitespace validation, and optionally a live startup smoke test.

Focused checks:

```bash
make
cd area && ../merc --check-area && cd ..
python3 check_parser.py
python3 check_exits.py
python3 check_resets.py
python3 check_shops.py
python3 scripts/area_lint.py --fail-on critical --limit 20
python3 -m unittest discover -s tests
git diff --check
```

The October 2026 baseline is 0 critical, 12 warning, and 1,635 informational
area-health findings. The warnings are reviewed disconnected room groups; the
informational backlog includes intentional and reviewable one-way exits,
unspawned definitions, and objects without reset sources (the generated Hyrule
guardians' drop tables are made at kill time, so each counts as a source-less
object). Do not suppress a finding merely to reduce the count.

## Repository Map

| Path | Role |
|---|---|
| `src/` | C server, gameplay, persistence, networking, and commands |
| `area/` | Latin-1 world files, help files, socials, and `area.lst` |
| `webadmin/` | FastAPI dashboard, parser, and area-health engine |
| `scripts/` | Setup, validation, Hyrule generation, and utility scripts |
| `tests/` | Python tests for APIs, area health, and Hyrule progression |
| `data/` | Checked-in source manifests, including Hyrule First Quest |
| `wiki/` | Player, host, operator, developer, and area-building guides |
| `notes/` | Design notes, audits, and implementation records |
| `.github/workflows/` | Continuous validation |
| `player/`, `gods/`, `heroes/` | Mutable character and staff data |

Area files use Latin-1. Do not silently convert them to UTF-8. Do not edit
production player or god files as part of routine development. Hyrule is
generated from `data/hyrule_first_quest.json`; edit the manifest and generator,
then regenerate and test instead of hand-editing generated output.

## Documentation Map

- [Player Guide](wiki/player-guide.md)
- [Player Command Reference](wiki/player-command-reference.md)
- [Psionics Guide](wiki/psionics.md)
- [Install Guide](wiki/install-guide.md)
- [Hosting Guide](wiki/hosting-guide.md)
- [Operator Guide](wiki/operator-guide.md)
- [Developer Guide](wiki/developer-guide.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Area Building Guide](wiki/area-building-guide.md)
- [In-Game Building Guide](wiki/building-guide.md)
- [Validation and Area Health](wiki/validation-and-area-health.md)
- [Advanced Gear Comparison](wiki/gear-comparison.md)
- [Hyrule: First Quest](wiki/hyrule-area.md)
- [Changelog](CHANGELOG.md)

## Credits And License

Times of Chaos is based on:

- Merc 2.1 by Hatchet, Furey, and Nemo (1992-1993)
- ROM 2.4 by Russ Taylor (1993-1996)
- DikuMUD (1990), the original code lineage

ToC customizations, areas, and modern infrastructure remain the work of their
respective contributors. Distribution must remain consistent with the original
Diku/Merc/ROM license terms: preserve attribution, use the software only for
permitted non-commercial purposes, and do not remove the original notices. Use
in-game `credits` and `help diku` for the complete acknowledgment text.
