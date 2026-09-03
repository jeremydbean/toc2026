# Times of Chaos (ToC)

Times of Chaos is a long-running text multiplayer role-playing game descended
from DikuMUD, Merc 2.1, and ROM 2.4. The repository contains the C game server,
the complete world database, a FastAPI operations dashboard, Docker packaging,
validation tools, tests, and the source data used to generate Hyrule: First
Quest.

The current checked-in world parses as **99 listed area files, 7,781 rooms,
2,336 mobiles, and 3,557 objects**. Player progression spans six classes, five
playable races, four optional cross-class guilds, five remorts, questing, group
play, player killing, permanent achievements, advanced equipment comparison,
and a large collection of hand-built areas.

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
| Server host | [Hosting Guide](wiki/hosting-guide.md) |
| Immortal/operator | [Operator Guide](wiki/operator-guide.md) |
| Developer | [Developer Guide](wiki/developer-guide.md) and [CONTRIBUTING.md](CONTRIBUTING.md) |
| Area builder | [Area Building Guide](wiki/area-building-guide.md) |
| Hyrule player or builder | [Hyrule: First Quest](wiki/hyrule-area.md) |
| Achievement hunter | [Achievement System](wiki/achievements.md) |
| Security reviewer | [Security Policy and Deployment Guide](SECURITY.md) |

The [wiki home page](wiki/Home.md) indexes all current and historical
documentation.

## What Is Included

- A native C server with the traditional ROM command loop, combat, magic,
  skills, quests, guilds, remorts, economy, banks, gambling, mounts, ranged
  combat, traps, scripts, seasons, and immortal tools.
- A world loaded from `area/area.lst`, including the generated 443-room Hyrule
  campaign with all nine First Quest dungeons.
- Advanced in-game `compare` analysis that models a player's complete loadout,
  class, guild, level, skills, spells, and selected gameplay focus.
- A permanent 111-achievement progression system with points, earned dates,
  hidden discoveries, live progress, retroactive milestones, group boss credit,
  world bosses, rare relics, crafting, unusual deaths, and complete Hyrule
  dungeon, map, compass, shard, and boss tracking.
- A FastAPI dashboard for world browsing, area health, maps, player inspection,
  logs, backups, server commands, and a browser-to-MUD WebSocket bridge.
- Automated player snapshots, scheduled archive backups, diagnostics, native
  area validation, Python reference checks, area-health linting, and unit tests.
- Docker, Docker Compose, Make, CMake, Windows/WSL validation, and GitHub Actions
  workflows.

## Easy Install

The automatic installer is now the recommended path. It installs missing host
prerequisites, creates private configuration and persistent data directories,
starts Docker, builds ToC, waits for the game to become healthy, and opens the
local dashboard. It is idempotent: rerunning it preserves the admin token and
runtime data.

The default installation is local-only. The game and dashboard bind to
`127.0.0.1`; remote players cannot connect until the host explicitly selects
public-game mode. Public-game mode exposes only the Telnet game port by default.
The dashboard remains local.

### Existing Checkout: One Click

| Platform | Easy button | Terminal equivalent |
|---|---|---|
| Windows 10/11 | Double-click `Install-ToC.cmd` | `.\install.ps1` |
| macOS | Double-click `Install-ToC.command` | `./install.sh` |
| Debian, Ubuntu, Raspberry Pi OS | Run `./install.sh` | `./install.sh` |

To accept remote game connections during installation:

```powershell
# Windows
.\install.ps1 -Network Public
```

```bash
# macOS or Linux
./install.sh --public
```

### Fresh Windows Machine

Open PowerShell, paste this block, and approve the normal Windows installer
prompts:

```powershell
$bootstrap = Join-Path $env:TEMP 'toc-bootstrap.ps1'
Invoke-WebRequest `
  'https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_windows.ps1' `
  -OutFile $bootstrap
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap
```

The bootstrap installs Git with `winget`, clones ToC to
`$HOME\TimesOfChaos`, and runs the full installer. Add `-Public` to the final
command to expose the game port. Windows may require one restart after enabling
WSL 2. If so, rerun the same block or double-click `Install-ToC.cmd` afterward;
the first pass is preserved.

### Fresh Mac

Open Terminal and paste:

```bash
bootstrap="$(mktemp /tmp/toc-bootstrap.XXXXXX)"
curl -fsSL \
  https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_macos.sh \
  -o "$bootstrap"
bash "$bootstrap"
```

The bootstrap starts Apple's Command Line Tools installer when necessary,
installs Homebrew and Docker Desktop, clones ToC to `~/TimesOfChaos`, and starts
the game. Run the last line as `bash "$bootstrap" --public` for a public game.
If macOS opens an Apple or Docker first-run agreement, complete it and rerun the
same command; no completed step is repeated destructively.

### Fresh Debian, Ubuntu, Or Raspberry Pi OS

Download and run the maintained bootstrap:

```bash
bootstrap="$(mktemp /tmp/toc-bootstrap.XXXXXX)"
curl -fsSL \
  https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_linux.sh \
  -o "$bootstrap"
bash "$bootstrap"
```

Use `bash "$bootstrap" --public` on an intended Internet/LAN host. Review
[SECURITY.md](SECURITY.md) and firewall the game port before inviting players.

### Day-To-Day Launcher

After installation, double-click `Start-ToC.cmd` on Windows or
`Start-ToC.command` on macOS. Terminal users have the same controls:

| Purpose | Windows | macOS/Linux |
|---|---|---|
| Start | `.\toc.ps1 start` | `./toc.sh start` |
| Stop and keep data | `.\toc.ps1 stop` | `./toc.sh stop` |
| Restart | `.\toc.ps1 restart` | `./toc.sh restart` |
| Status/health | `.\toc.ps1 status` | `./toc.sh status` |
| Follow logs | `.\toc.ps1 logs` | `./toc.sh logs` |
| Diagnose setup | `.\toc.ps1 doctor` | `./toc.sh doctor` |
| Update/rebuild | `.\toc.ps1 update` | `./toc.sh update` |
| Open game client | `.\toc.ps1 play` | `./toc.sh play` |
| Open administration | `.\toc.ps1 admin` | `./toc.sh admin` |

Open the first-party web client at `http://127.0.0.1:9001/client`, or connect a
traditional MUD client to `localhost:9000`. The administration dashboard is
`http://127.0.0.1:9001`. Protected actions use the generated token in `.env`;
the installers never print or replace an existing token. Both interfaces ship
all browser assets locally and do not require internet access after installation.

Docker Desktop can require acceptance of its own subscription terms on first
launch. The project cannot accept those terms for the host. Docker documents
its current [Windows installation requirements](https://docs.docker.com/desktop/setup/install/windows-install/)
and [macOS requirements](https://docs.docker.com/desktop/setup/install/mac-install/).

## Native Build

The native runtime is POSIX-oriented. Use Linux, macOS, or WSL 2. Direct native
Windows builds are not a supported path.

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
in-game `shutdown`.

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
| `MUD_BIND` | `127.0.0.1` | Host interface for the published game port; use `0.0.0.0` for remote players |
| `MUD_PORT` | `9000` | Game port published on the host |
| `MUD_HOST` | `127.0.0.1` | Game host used by the dashboard health check and browser console |
| `WEB_ADMIN_BIND` | `127.0.0.1` | Host interface for the dashboard; keep private |
| `WEB_ADMIN_PORT` | `9001` | Dashboard port published on the host |
| `WEB_ADMIN_ENABLED` | `1` | Set to `0` to skip the dashboard in Docker |
| `WEB_ADMIN_HOST` | `0.0.0.0` | Dashboard bind address in Docker |
| `WEB_ADMIN_TOKEN` | unset | Shared secret for operational API routes; unset disables them |
| `WEB_ADMIN_LOCAL_UNLOCK` | `1` in generated `.env` | Auto-unlock local browser sessions only while `WEB_ADMIN_BIND` and the page host are loopback |
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

## Persistent Data

These paths contain mutable runtime state:

| Path | Contents | Back up? |
|---|---|---|
| `player/` | Character files and `versions/` snapshots | Yes, sensitive |
| `gods/` | Immortal state | Yes, sensitive |
| `heroes/` | Hero state | Yes |
| `corpse/` | Recoverable player corpses | Yes |
| `backups/` | Compressed player archives | Yes, sensitive |
| `log/` | Server logs | As required |
| `area/webadmin.queue` | Transient dashboard command queue | No |

The Compose file bind-mounts all six mutable directories in this table. Keep
them with `.env` when moving or restoring an installation.

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

The August 2026 baseline is 0 critical, 11 warning, and 1,571 informational
area-health findings. The warnings are reviewed disconnected room groups; the
informational backlog includes intentional and reviewable one-way exits,
unspawned definitions, and objects without reset sources. Do not suppress a
finding merely to reduce the count.

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
- [Hosting Guide](wiki/hosting-guide.md)
- [Operator Guide](wiki/operator-guide.md)
- [Developer Guide](wiki/developer-guide.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Area Building Guide](wiki/area-building-guide.md)
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
