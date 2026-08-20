# Times of Chaos (ToC)

Times of Chaos is a long-running text multiplayer role-playing game descended
from DikuMUD, Merc 2.1, and ROM 2.4. The repository contains the C game server,
the complete world database, a FastAPI operations dashboard, Docker packaging,
validation tools, tests, and the source data used to generate Hyrule: First
Quest.

The current checked-in world parses as **99 listed area files, 7,781 rooms,
2,336 mobiles, and 3,551 objects**. Player progression spans six classes, five
playable races, four optional cross-class guilds, five remorts, questing, group
play, player killing, advanced equipment comparison, and a large collection of
hand-built areas.

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
- A FastAPI dashboard for world browsing, area health, maps, player inspection,
  logs, backups, server commands, and a browser-to-MUD WebSocket bridge.
- Automated player snapshots, scheduled archive backups, diagnostics, native
  area validation, Python reference checks, area-health linting, and unit tests.
- Docker, Docker Compose, Make, CMake, Windows/WSL validation, and GitHub Actions
  workflows.

## Quick Start With Docker

Docker is the most predictable way to run ToC. Install Git and Docker Desktop
or Docker Engine with Compose support first.

Current prerequisite helpers are `scripts/setup_windows.ps1`,
`scripts/setup_linux.sh`, and `scripts/setup_mac.sh`. Review a helper before
running it with administrative privileges; each creates `.env` only when one
does not already exist.

### Linux or macOS

```bash
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
export WEB_ADMIN_TOKEN="$(openssl rand -hex 32)"
docker compose up --build -d
docker compose logs -f game
```

### Windows PowerShell

```powershell
git clone https://github.com/jeremydbean/toc2026.git
Set-Location toc2026

$tokenBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($tokenBytes)
$env:WEB_ADMIN_TOKEN = [Convert]::ToHexString($tokenBytes)

docker compose up --build -d
docker compose logs -f game
```

Connect a MUD client to `localhost` port `9000`. Open the dashboard at
`http://localhost:9001`. Protected dashboard actions require the value of
`WEB_ADMIN_TOKEN` in the `X-Admin-Token` header or the dashboard token field.

The Compose file publishes both ports on all host interfaces. That is useful
for local testing but is not a production security boundary. Bind port 9001 to
loopback, firewall it, or put it behind an authenticated TLS reverse proxy
before using ToC on an Internet host.

```bash
# Stop without deleting persistent host data.
docker compose stop

# Start again.
docker compose start

# Remove containers and the private Compose network; bind-mounted data remains.
docker compose down
```

The Compose service uses `restart: unless-stopped`. Use `docker compose stop`
or `docker compose down` when the server must remain stopped; Docker can restart
the container after an in-game shutdown because the restart policy applies to
clean process exits too.

## Native Build

The native runtime is POSIX-oriented. Use Linux, macOS, or WSL 2. Direct native
Windows builds are not a supported path.

### Ubuntu or Debian

```bash
sudo apt update
sudo apt install build-essential libcrypt-dev python3 python3-venv

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

Install `gcc`, `make`, `libxcrypt-devel`, `python3`, and `python3-pip`, then use
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

## Native Web Dashboard

Run this in a second terminal from the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r webadmin/requirements.txt
export WEB_ADMIN_TOKEN="$(openssl rand -hex 32)"
python -m webadmin.server \
  --host 127.0.0.1 \
  --port 9001 \
  --queue area/webadmin.queue \
  --log-file log/toc.log \
  --area-path area \
  --backup-path backups
```

Windows users can activate with `.\.venv\Scripts\Activate.ps1` and use the
same `python -m webadmin.server` arguments. The game itself should still run in
Docker or WSL.

## Runtime Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `PORT` | `9000` | Preferred game port used by the container entrypoint |
| `MUD_PORT` | `9000` | Fallback game port and dashboard bridge destination |
| `WEB_ADMIN_ENABLED` | `1` | Set to `0` to skip the dashboard in Docker |
| `WEB_ADMIN_HOST` | `0.0.0.0` | Dashboard bind address in Docker |
| `WEB_ADMIN_PORT` | `9001` | Dashboard port |
| `WEB_ADMIN_TOKEN` | unset | Shared secret for operational API routes; unset disables them |
| `QUEUE_PATH` | `area/webadmin.queue` | Dashboard-to-game command queue |
| `LOG_FILE` | `log/toc.log` | Dashboard log source |
| `AREA_PATH` | `area` | Dashboard area-parser source |
| `BACKUP_PATH` | `backups` | Dashboard backup archive directory |
| `PLAYER_PATH` | `player` | Dashboard player-file directory |

`PORT` takes precedence over `MUD_PORT` in the Docker entrypoint. When changing
the game from port 9000, set both variables to the same container port so the
dashboard WebSocket bridge follows the game, and update the Compose port
mapping. The Hosting Guide documents entrypoint modes, bind mounts, firewalls,
reverse proxies, service management, upgrades, and rollback procedures.

## Persistent Data

These paths contain mutable runtime state:

| Path | Contents | Back up? |
|---|---|---|
| `player/` | Character files and `versions/` snapshots | Yes, sensitive |
| `gods/` | Immortal state | Yes, sensitive |
| `heroes/` | Hero state | Yes |
| `backups/` | Compressed player archives | Yes, sensitive |
| `log/` | Server logs | As required |
| `area/webadmin.queue` | Transient dashboard command queue | No |

The Compose file bind-mounts `player/`, `backups/`, and `log/`. If the instance
uses mutable `gods/`, `heroes/`, or other local state, add explicit mounts or an
external backup for those paths.

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

## Web Dashboard And API

The dashboard can browse areas, maps, rooms, mobiles, objects, gear, player
files, live game status, logs, backups, and area-health findings. It also has a
WebSocket bridge to the game port.

Operational routes such as log access, command queueing, backup, reload,
wizinfo, and shutdown require `X-Admin-Token`. Browsing routes, including the
player list and player detail endpoints, are currently public to anyone who can
reach port 9001. Dashboard `reload` refreshes the Python parser's view of area
files; it does not hot-reload the live C game world.

See the [Hosting Guide](wiki/hosting-guide.md) for the complete endpoint and
authentication matrix and the [Operator Guide](wiki/operator-guide.md) for
normal operating procedures.

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

The August 2026 baseline is 0 critical, 11 warning, and 1,565 informational
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
