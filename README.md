# Times of Chaos (ToC) MUD

**Times of Chaos** is a text-based MUD (Multi-User Dungeon) server based on the Merc 2.1 / ROM 2.4 lineage, running the ToC custom codebase. It features 132 hand-crafted areas, 70 levels, 6 player classes, 5 playable races, a full remort system, player-kill zones, seasonal events, and a modern Docker deployment with a Python web administration panel.

> **Quick links:** [Connect now](#connecting-to-the-game) · [Docker quick start](#docker-quickest-path) · [Manual build](#building-natively-without-docker) · [Web Admin](#web-administration-panel) · [Troubleshooting](#troubleshooting)

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Game Overview](#game-overview)
3. [System Requirements](#system-requirements)
4. [Platform Setup Guide](#platform-setup-guide)
   - [Windows (Docker Desktop)](#windows-docker-desktop)
   - [Windows (WSL 2 — recommended)](#windows-wsl-2--recommended)
   - [macOS (Intel & Apple Silicon)](#macos-intel--apple-silicon)
   - [Linux — Ubuntu / Debian](#linux--ubuntu--debian)
   - [Linux — Fedora / RHEL / Rocky](#linux--fedora--rhel--rocky)
   - [Raspberry Pi (ARM)](#raspberry-pi-arm)
   - [Cloud / VPS (Ubuntu Server)](#cloud--vps-ubuntu-server)
5. [Docker Quick Start](#docker-quickest-path)
6. [Building Natively (Without Docker)](#building-natively-without-docker)
7. [Running the Server](#running-the-server)
8. [Connecting to the Game](#connecting-to-the-game)
9. [Web Administration Panel](#web-administration-panel)
10. [Configuration & Environment Variables](#configuration--environment-variables)
11. [Persistent Data & Volumes](#persistent-data--volumes)
12. [Docker Compose (Multi-Service)](#docker-compose-multi-service)
13. [Development Guide](#development-guide)
14. [Project Structure](#project-structure)
15. [Security Notes](#security-notes)
16. [Troubleshooting](#troubleshooting)
17. [Credits & License](#credits--license)

---

## What Is This?

Times of Chaos (ToC) is a MUD (Multi-User Dungeon) — a real-time, text-based multiplayer role-playing game accessed via any telnet/MUD client. The server is written in C (gnu89 / C17 compatible), runs on Linux or macOS natively, and is packaged as a Docker image for easy deployment on any OS.

**Key characteristics:**
- Based on **Merc 2.1 / ROM 2.4** — a classic 1990s open-source lineage
- **Heavily customized** over years of active development
- **132 unique areas** with ~338,000 lines of world data
- Comprehensive **web admin dashboard** (Python/FastAPI, port 9001)
- **Seasonal content** — special holiday areas for Halloween, Christmas, and more
- **Player-kill** system with PKill data tracking
- **Remort system** — reincarnate at max level for bonuses
- String-safety hardened (OpenBSD `strlcpy`/`strlcat` throughout)
- Fully containerized with **Docker** for one-command deployment

---

## Game Overview

| Feature | Detail |
|---------|--------|
| Max level | 70 (Level 60 = Hero, Level 61+ = Immortal) |
| Playable classes | Mage, Cleric, Thief, Warrior, Monk, Necromancer |
| Playable races | Human, Elf, Dwarf, Hobbit, Saurian |
| World areas | 132 (ranging from starter school to end-game zones) |
| Game port | 9000 (TCP, telnet protocol) |
| Web admin port | 9001 (HTTP/WebSocket) |
| Ticks per second | 4 pulses/sec (0.25s world tick) |
| Save system | ASCII flat-file per-player saves in `player/` |
| Combat system | Round-based, multi-attack, spell memorization |
| Special features | Quests, player kills, remort, seasonal events, crafting components |

### Classes

| Class | Abbreviation | Prime Stat | Specialty |
|-------|-------------|------------|-----------|
| Mage | M | Intelligence | Offensive spells, summons |
| Cleric | C | Wisdom | Healing, buffs, undead control |
| Thief | T | Dexterity | Stealth, steal, backstab, dual wield |
| Warrior | W | Strength | Melee, berserk, enhanced damage |
| Monk | Monk | Constitution | Hand-to-hand, balance, ki abilities |
| Necromancer | Necro | Intelligence | Death magic, drain life, undead armies |

### Playable Races

| Race | Strengths | Notes |
|------|-----------|-------|
| Human | Balanced stats, bonus exp to guild | Jack of all trades |
| Elf | Infrared vision, mana bonus | Fragile but magically gifted |
| Dwarf | High constitution, infrared, resist bash | Slow but tough |
| Hobbit | High dexterity, dodge bonus | Great for thieves |
| Saurian | Unique racial abilities | Reptilian, heat-adapted |

---

## System Requirements

### Minimum (to run the Docker image)
- **CPU**: Any x86-64 or ARM64 processor (Pi 4+, modern Macs, any cloud VM)
- **RAM**: 256 MB free
- **Disk**: 2 GB free (image + volumes)
- **OS**: Anything that runs Docker Engine 20.10+
- **Network**: Open TCP ports 9000 (game) and 9001 (web admin)

### For native (non-Docker) builds
- **OS**: Linux (kernel 3.2+) or macOS 11+
- **Compiler**: GCC 7+ or Clang 10+ with C99/C17 support
- **Build tools**: `make`, `gcc`, `libcrypt` (Linux only)
- **Python**: 3.9+ (for web admin only)

---

## Platform Setup Guide

### Windows (Docker Desktop)

Docker Desktop is the easiest path on Windows. It runs Linux containers in a lightweight VM.

**Automated setup** (uses [Chocolatey](https://chocolatey.org) to install Git, Docker Desktop, and VS Code):
```powershell
# Run PowerShell as Administrator
.\scripts\setup_windows.ps1
```

**Manual steps:**
1. Enable **WSL 2** — open PowerShell as Administrator:
   ```powershell
   wsl --install
   # Restart when prompted
   ```
2. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
3. During install, ensure **Use WSL 2 based engine** is checked
4. Start Docker Desktop from the Start Menu and wait for the whale icon to show "Running"
5. Open a terminal (PowerShell, Command Prompt, or Windows Terminal) and verify:
   ```powershell
   docker --version
   docker run hello-world
   ```
6. Clone the repository:
   ```powershell
   git clone https://github.com/jeremydbean/toc2026.git
   cd toc2026
   ```
7. Build and run:
   ```powershell
   docker build -t toc .
   docker run -it --rm -p 9000:9000 -p 9001:9001 `
     -v "${PWD}/player:/app/player" `
     -v "${PWD}/log:/app/log" `
     toc
   ```

**Notes for Windows:**
- Keep Docker Desktop running in the system tray whenever you want to use the game
- Use Windows Terminal for the best experience
- If you see `exec format error`, make sure Docker is using the Linux engine (not Windows containers) — right-click the Docker Desktop tray icon and select **Switch to Linux containers**
- Volume paths use **forward slashes** in the container half (`:/app/player`) even on Windows
- The `docker run` command uses backtick (`` ` ``) for line continuation in PowerShell; use `^` in `cmd.exe`

---

### Windows (WSL 2 — recommended)

Running directly inside WSL 2 gives you a real Linux environment with better performance for development.

1. Install WSL 2 with Ubuntu:
   ```powershell
   # In PowerShell (Admin)
   wsl --install -d Ubuntu
   # Set username and password when prompted, then close and reopen WSL
   ```
2. Inside the WSL Ubuntu terminal, install Docker Engine:
   ```bash
   sudo apt update && sudo apt install -y docker.io
   sudo usermod -aG docker $USER
   newgrp docker
   ```
3. Continue with the [Linux — Ubuntu / Debian](#linux--ubuntu--debian) instructions below.
4. Connect a MUD client on Windows to `localhost:9000` — WSL 2 transparently forwards ports.

---

### macOS (Intel & Apple Silicon)

**Automated setup:**
```bash
chmod +x scripts/setup_mac.sh
./scripts/setup_mac.sh
```

**Manual Docker setup:**
1. Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
   - For **Apple Silicon (M1/M2/M3/M4)**: download the Apple Silicon version — Docker runs ARM64 Linux containers natively
   - For **Intel Macs**: download the Intel version
2. Move Docker.app to `/Applications` and launch it
3. Wait for Docker to finish starting (menu bar whale icon turns solid)
4. Verify in Terminal:
   ```bash
   docker --version
   ```

**Native (non-Docker) build on macOS:**

The C server can be built natively on macOS with a few compatibility shims:

```bash
# Install Xcode Command Line Tools (provides gcc/clang, make)
xcode-select --install

# Build (macOS-compatible — crypt.h guard already in place)
make

# Run directly
cd area
./merc 9000
```

> **Note:** macOS provides `strlcpy`/`strlcat` natively. The `string_safe.c` module includes `#ifndef __APPLE__` guards to avoid symbol conflicts. The `<crypt.h>` include in `merc.h` is also guarded for macOS.

**Docker run example (macOS):**
```bash
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
docker build -t toc .
docker run -it --rm \
  -p 9000:9000 \
  -p 9001:9001 \
  -v "$(pwd)/player:/app/player" \
  -v "$(pwd)/log:/app/log" \
  toc
```

**Web admin on macOS (without Docker):**
```bash
pip3 install fastapi "uvicorn[standard]"
cd /path/to/toc2026
python3 -m webadmin.server --host 0.0.0.0 --port 9001
```

---

### Linux — Ubuntu / Debian

**Automated setup:**
```bash
chmod +x scripts/setup_linux.sh
sudo ./scripts/setup_linux.sh
# Log out and back in to apply docker group membership
```

**Manual setup:**
```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install build tools (for native builds)
sudo apt install -y build-essential gcc make libssl-dev

# Install Docker Engine
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker   # or log out/in

# Install Python + pip (for web admin)
sudo apt install -y python3 python3-pip
pip3 install fastapi "uvicorn[standard]"

# Clone and build
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make              # native build
# OR
docker build -t toc .   # Docker build
```

**Ubuntu 24.04 note:** The Dockerfile targets Debian Bookworm Slim (compatible). Native Ubuntu 24.04 builds work without issue.

---

### Linux — Fedora / RHEL / Rocky

```bash
# Install Docker
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# Install build tools (for native builds)
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y libxcrypt-devel

# Install Python
sudo dnf install -y python3 python3-pip

# Clone and proceed as above
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
docker build -t toc .
```

> On RHEL/Rocky, if `libcrypt.so` is not found, link against `libxcrypt`: `make LDFLAGS="-lxcrypt -lm"`

---

### Raspberry Pi (ARM)

The Docker image **builds and runs on Raspberry Pi** (Pi 4 or newer recommended with 2+ GB RAM).

```bash
# Install Docker on Raspberry Pi OS (Debian-based)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
newgrp docker

# Clone the repository
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026

# Build — Docker will use the ARM64 builder automatically
docker build -t toc .

# Run
docker run -d --name toc \
  -p 9000:9000 -p 9001:9001 \
  -v $(pwd)/player:/app/player \
  -v $(pwd)/log:/app/log \
  --restart unless-stopped \
  toc
```

**Native build on Raspberry Pi OS:**
```bash
sudo apt install -y build-essential gcc make
cd toc2026
make
cp merc area/
cd area && ./merc 9000 &
```

The Pi 4/5 runs the MUD very comfortably — it's not CPU-intensive. The web admin adds minimal overhead.

---

### Cloud / VPS (Ubuntu Server)

For a public-facing server (DigitalOcean, Linode, AWS EC2, etc.):

```bash
# Fresh Ubuntu 22.04/24.04 droplet
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io git ufw
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu  # or your username

# Open firewall ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 9000/tcp  # MUD game port
sudo ufw allow 9001/tcp  # Web admin (restrict to your IP if possible)
sudo ufw enable

# Clone and build
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026

# Build
docker build -t toc .

# Run as a background daemon, auto-restarting on boot
docker run -d \
  --name toc \
  --restart unless-stopped \
  -p 9000:9000 \
  -p 9001:9001 \
  -e WEB_ADMIN_TOKEN="your-strong-secret-here" \
  -v $(pwd)/player:/app/player \
  -v $(pwd)/log:/app/log \
  -v $(pwd)/backups:/app/backups \
  toc

# Check status
docker logs -f toc
```

**Security for public servers:**
- Set `WEB_ADMIN_TOKEN` to a strong secret — this protects the web admin API
- Consider putting Nginx or Caddy in front of port 9001 with HTTPS
- Port 9000 (MUD) is plain telnet — expected for a MUD, but advise players accordingly
- Firewall port 9001 to your IP if you don't need public web admin access

---

## Docker Quickest Path

If you just want the server running with no setup beyond Docker:

```bash
# 1. Clone
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026

# 2. Build (≈2 minutes first time)
docker build -t toc .

# 3. Run (foreground — Ctrl+C to stop)
docker run -it --rm \
  -p 9000:9000 \
  -p 9001:9001 \
  -v $(pwd)/player:/app/player \
  -v $(pwd)/log:/app/log \
  toc
```

Two services start automatically:
- **MUD server** on port 9000
- **Web admin** on port 9001

Connect your MUD client to `localhost:9000` and browse to [http://localhost:9001](http://localhost:9001).

### Running as a Background Daemon

```bash
docker run -d \
  --name toc \
  --restart unless-stopped \
  -p 9000:9000 \
  -p 9001:9001 \
  -v $(pwd)/player:/app/player \
  -v $(pwd)/log:/app/log \
  -v $(pwd)/backups:/app/backups \
  toc

# View logs
docker logs -f toc

# Stop
docker stop toc

# Start again
docker start toc
```

### Auto-Restart Behaviour

The container entrypoint runs `merc` in an automatic restart loop:

| Event | Behaviour |
|-------|-----------|
| `merc` crashes or exits non-zero | Waits 5 seconds, restarts `merc` automatically |
| Immortal `shutdown` command | Writes `shutdown.txt`; entrypoint detects it and exits cleanly (container stops) |
| Immortal `reboot` command | Exits without `shutdown.txt`; entrypoint restarts `merc` |
| `docker stop toc` | Sends SIGTERM to container; container stops immediately |

The web admin (port 9001) starts once at container entry and stays up across `merc` restarts.

### Useful Docker Commands

```bash
# Rebuild after code changes
docker build -t toc . && docker restart toc

# Shell into running container
docker exec -it toc /bin/sh

# Check resource usage
docker stats toc

# Remove container (data in volumes is preserved)
docker rm -f toc

# Clean up images
docker image prune
```

---

## Building Natively (Without Docker)

### Prerequisites (Linux)
```bash
sudo apt install -y build-essential gcc make libssl-dev python3 python3-pip
```

### Build
```bash
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make
# Binary: ./merc
```

### Custom Warning Flags
The Makefile accepts `WARNFLAGS` to increase strictness:
```bash
# Standard build (default)
make

# Strict warnings (used for CI/auditing)
make WARNFLAGS='-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 \
  -Wunused-parameter -Wstrict-prototypes -Wold-style-definition \
  -Wmissing-prototypes -Wcast-qual'
```

### CMake Build (Alternative — C17 + Sanitizers)
```bash
# Configure
cmake -B build -DCMAKE_BUILD_TYPE=Debug

# With AddressSanitizer + UBSan (for debugging)
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON

# Build
cmake --build build

# Binary: ./bin/rom  (CMake outputs to bin/ instead of root merc)
```

### Run After Native Build
```bash
cd area
../merc 9000
# OR
./merc 9000 2>&1 | tee ../log/toc.log &
```

### Web Admin (Native)
```bash
pip3 install fastapi "uvicorn[standard]"
python3 -m webadmin.server \
  --host 0.0.0.0 \
  --port 9001 \
  --queue area/webadmin.queue \
  --log-file log/toc.log
```

---

## Running the Server

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `9000` | MUD game port |
| `MUD_PORT` | `9000` | Alternative to PORT |
| `WEB_ADMIN_ENABLED` | `1` | Set to `0` to disable web admin |
| `WEB_ADMIN_PORT` | `9001` | Web admin HTTP port |
| `WEB_ADMIN_HOST` | `0.0.0.0` | Web admin bind address |
| `WEB_ADMIN_TOKEN` | _(unset)_ | Shared secret for API auth (recommended for public servers) |

### Entrypoint Modes

The `docker-entrypoint.sh` supports several invocation styles:

```bash
# Default: start MUD on $PORT
docker run toc

# Specific port
docker run toc 9500

# With newplayer lock
docker run toc newlock 9000

# Run arbitrary command
docker run toc /bin/sh
```

---

## Connecting to the Game

### MUD Clients (Recommended)

| Client | Platform | Download |
|--------|----------|----------|
| **Mudlet** | Windows, macOS, Linux | [mudlet.org](https://www.mudlet.org) |
| **MUSHclient** | Windows | [mushclient.com](https://www.mushclient.com) |
| **Blowtorch** | Android | Google Play Store |
| **MUDRammer** | iOS | App Store |
| **BeipMU** | Windows | Microsoft Store |

**Connection settings:**
- Host: `localhost` (or your server's IP/hostname)
- Port: `9000`
- Protocol: Telnet (MUD clients handle this automatically)

### Raw Telnet (Testing)
```bash
telnet localhost 9000
```

### Getting Started In-Game

1. At the login screen, type `new` to create a character
2. Choose a **name** (letters only, no spaces)
3. Select **race** and **class**
4. After character creation, you start in the **School of Learning** (safe zone)
5. Type `help` for in-game help, `commands` for all commands
6. Type `score` to see your character stats
7. Type `who` to see online players

### Useful Starting Commands

| Command | Effect |
|---------|--------|
| `look` | Look at your surroundings |
| `north`, `south`, `east`, `west`, `up`, `down` | Move |
| `say hello` | Say something to the room |
| `score` | View your character stats |
| `inventory` | View your items |
| `equipment` | View worn equipment |
| `help <topic>` | In-game help |
| `quit` | Safely log out (saves your character) |

---

## Web Administration Panel

Access the web admin at [http://localhost:9001](http://localhost:9001) after starting the server.

### Dashboard Features

- **Live Log Viewer** — Real-time log stream via WebSocket; shows the last 200 lines of `toc.log`
- **Player Browser** — Browse and inspect saved player files
- **Area Browser** — Browse Mobs, Objects, Rooms, and Shops parsed from `.are` files
- **Best Gear Finder** — Select a class, get the optimal gear set from all object data
- **Wizinfo Broadcast** — Send a message to all players online
- **Immortal Command** — Execute any immortal-level game command (sent via queue file)
- **Backup** — Trigger a live player-file backup
- **Shutdown** — Gracefully shut down the game server

### API Endpoints

The web admin exposes a RESTful JSON API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check — merc process status |
| GET | `/api/logs?lines=200` | Last N lines of toc.log |
| POST | `/api/command` | Execute an immortal command |
| POST | `/api/wizinfo` | Broadcast a message |
| POST | `/api/backup` | Trigger player backup |
| POST | `/api/shutdown` | Shut down the MUD |
| GET | `/api/areas` | List all areas |
| GET | `/api/mobs` | All mobile data |
| GET | `/api/objects` | All object data |
| GET | `/api/rooms` | All room data |
| GET | `/api/bestgear/{class}` | Optimal gear set for class |
| WebSocket | `/ws/logs` | Live log stream |

### API Authentication

When `WEB_ADMIN_TOKEN` is set in the environment, mutating endpoints require the header:
```
X-Admin-Token: your-token-here
```

Read-only endpoints (health, areas, mobs, objects, rooms) remain public.

---

## Configuration & Environment Variables

### Server Configuration

The MUD reads its world data from the `area/` directory. The file `area/area.lst` controls which areas are loaded at startup. Edit this file to enable/disable areas.

### Port Configuration

```bash
# Change game port (example: 9500)
docker run -p 9500:9500 -e PORT=9500 toc

# Change web admin port
docker run -p 9000:9000 -p 8080:8080 -e WEB_ADMIN_PORT=8080 toc
```

### Disabling the Web Admin

```bash
docker run -p 9000:9000 -e WEB_ADMIN_ENABLED=0 toc
```

### Web Admin Token (Security)

```bash
docker run \
  -p 9000:9000 -p 9001:9001 \
  -e WEB_ADMIN_TOKEN="change-this-to-something-strong" \
  toc
```

---

## Persistent Data & Volumes

Player files and logs live outside the container. Always mount these volumes or data will be lost when the container is removed.

| Container Path | Description | Mount Example |
|---------------|-------------|---------------|
| `/app/player` | Player save files | `-v $(pwd)/player:/app/player` |
| `/app/log` | Server logs | `-v $(pwd)/log:/app/log` |
| `/app/backups` | Player backups | `-v $(pwd)/backups:/app/backups` |
| `/app/area` | World data files | `-v $(pwd)/area:/app/area` *(optional — for live editing)* |

> **Important:** The `player/` and `gods/` directories contain live character data. Do not edit files in those directories while the server is running.

### Backup

The web admin's **Backup** button copies the contents of `player/` into `backups/` with a timestamp. You can also run:

```bash
docker exec toc sh -c "cp -r /app/player /app/backups/backup_$(date +%Y%m%d_%H%M%S)"
```

---

## Docker Compose (Multi-Service)

A `docker-compose.yml` is included for running the full stack with a single command:

```bash
docker compose up --build           # build and start (foreground)
docker compose up --build -d        # build and start in background
docker compose down                 # stop and remove containers
docker compose logs -f game         # follow the game container logs
docker compose restart game         # restart after a code change
```

The compose file (`docker-compose.yml`) defines one service:
- **`game`** — builds the image, exposes ports `9000` (MUD) and `9001` (web admin), mounts `player/`, `log/`, and `backups/` volumes, and restarts automatically unless explicitly stopped

To enable web admin authentication, uncomment and set `WEB_ADMIN_TOKEN` in `docker-compose.yml`:
```yaml
environment:
  - WEB_ADMIN_TOKEN=your-strong-secret-here
```

> **Windows users:** Compose uses the same `$(pwd)` volume resolution. Run `docker compose` commands from the repository root in PowerShell or Windows Terminal.

---

## Development Guide

### Setting Up a Dev Environment

1. Install VS Code with the recommended extensions:
   - **C/C++** (Microsoft) — syntax, IntelliSense, debugging
   - **Python** (Microsoft) — web admin development
   - **Docker** (Microsoft) — container management
   - **clangd** — fast C analysis engine

2. Open the workspace:
   ```bash
   code /path/to/toc2026
   ```

3. For C development, use the native Makefile build (faster iteration than Docker):
   ```bash
   make && cd area && ./merc 9000
   ```

4. For web admin development:
   ```bash
   cd toc2026
   pip3 install fastapi "uvicorn[standard]"
   python3 -m webadmin.server --host 0.0.0.0 --port 9001 \
     --queue area/webadmin.queue --log-file log/toc.log
   ```
   Uvicorn auto-reloads on file changes in development mode:
   ```bash
   uvicorn webadmin.server:app --reload --host 0.0.0.0 --port 9001
   ```

### Code Conventions

- **C style**: GNU89 with `-std=gnu89` (Makefile) or C17 (CMake). Tabs for indentation.
- **String safety**: Always use `strlcpy`/`strlcat` or `snprintf` with `sizeof(buf)`. Never `strcpy`/`strcat`/`sprintf`.
- **Unused parameters**: Use the `UNUSED_PARAM(x)` macro (defined in `merc.h`) to silence `-Wunused-parameter` without suppressing warnings.
- **Adding commands**: Implement in `act_*.c`, declare in `interp.h`, register in `interp.c`, add help text to `area/commands.are`.
- **Adding spells**: Implement in `magic.c` or `magic2.c`, add skill table entry in `const.c`, set `gsn_` global in `db.c`.

### Editing Area Files

Area files (`.are`) use the ROM 2.4 format. They are plain text with `#SECTION` markers. The encoding is **latin-1** (ISO-8859-1). Key sections:

- `#AREA` — area header (name, level range, author)
- `#MOBILES` — NPC definitions
- `#OBJECTS` — item definitions
- `#ROOMS` — room definitions with descriptions and exits
- `#RESETS` — spawn instructions (what goes where at startup)
- `#SHOPS` — vendor definitions
- `#SPECIALS` — special function assignments for mobs
- `#$` — end of file marker

### Running Tests

```bash
# Sanitizer build (catches memory errors and UB)
cmake -B build -DENABLE_SANITIZERS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build
cd area && ../bin/rom 9000

# Valgrind (Docker environment recommended)
docker run --rm -it toc /bin/sh
# Inside container:
valgrind --leak-check=full --error-exitcode=1 merc 9000
```

### Immortal Commands (Level 60+)

A set of immortal commands provides in-game server management:

| Command | Level | Description |
|---------|-------|-------------|
| `mute` | L65 | Toggle all speech channels for a player |
| `drag` | L66 | Teleport a player to your location |
| `duel` | L64 | Force two players into PK combat |
| `weather` | L65 | Set global weather (sunny/cloudy/rain/storm) |
| `lights` | L65 | Toggle ROOM_DARK on current room |
| `seal` | L65 | Wizard-lock a room exit direction |
| `finger` | L65 | Look up player info (online or offline) |
| `trail` | L67 | Show last 10 rooms a player visited |
| `petrify` | L65 | Apply timed stone affect blocking all commands |
| `empower` | L64 | Apply sanctuary+haste+fly+regen+stat boosts |
| `colossus` | L64 | Apply 500% HP/mana/move boost |

---

## Project Structure

```
toc2026/
├── src/                  # C source (game server)
│   ├── merc.h            # Master header — all types, constants, prototypes
│   ├── comm.c            # Network I/O, telnet, main loop
│   ├── db.c              # Area/world loading, startup
│   ├── interp.c          # Command interpreter
│   ├── act_comm.c        # Communication commands
│   ├── act_info.c        # Informational commands (look, score, who)
│   ├── act_move.c        # Movement commands
│   ├── act_obj.c         # Object commands (get, drop, wear)
│   ├── act_wiz.c         # Immortal/wizard commands
│   ├── fight.c           # Combat engine
│   ├── magic.c           # Spells (part 1)
│   ├── magic2.c          # Spells (part 2)
│   ├── skills.c          # Skill implementations
│   ├── update.c          # Tick updates (combat, regen, weather, components)
│   ├── save.c            # Player file save/load
│   ├── handler.c         # Object/character manipulation helpers
│   ├── special.c         # Special procedures for mobs
│   ├── quest.c           # Quest system
│   ├── pkill.c           # Player-kill tracking
│   ├── string_safe.c     # Bounded strlcpy/strlcat implementations
│   └── ...               # Other modules
├── area/                 # World data (132 .are files)
│   ├── area.lst          # Area loading list
│   ├── commands.are      # Help file content
│   ├── help.are          # In-game help system
│   ├── school.are        # Starting area (School of Learning)
│   └── *.are             # 129 other zones
├── webadmin/             # Web administration (Python/FastAPI)
│   ├── server.py         # FastAPI routes, WebSocket, HTML dashboard
│   └── area_parser.py    # .are file parser for web display
├── scripts/              # Setup and utility scripts
│   ├── setup_windows.ps1 # Automated Windows setup
│   ├── setup_mac.sh      # Automated macOS setup
│   ├── setup_linux.sh    # Automated Linux setup
│   └── run_valgrind.sh   # Valgrind memory check helper
├── wiki/                 # Game documentation (area refs, mob stats, etc.)
├── notes/                # Development notes and scratchpads
├── player/               # Player save files (not committed to git)
├── log/                  # Server logs (not committed to git)
├── backups/              # Player file backups
├── gods/                 # Immortal player files
├── heroes/               # Hero player archive
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Multi-service compose config
├── docker-entrypoint.sh  # Container startup script
├── Makefile              # Simple gnu89 native build
├── CMakeLists.txt        # Modern C17 build with sanitizer support
└── AGENTS.md             # AI agent notes and architectural documentation
```

---

## Security Notes

### Network Exposure

- **Port 9000** (MUD): Plain telnet. No encryption. Suitable for trusted LAN or accepted risk for public internet (standard for MUDs). Passwords are stored via crypt(3).
- **Port 9001** (Web Admin): HTTP only. **Do not expose to untrusted networks without a reverse proxy with TLS** (Nginx, Caddy, etc.).

### Web Admin Authentication

Set `WEB_ADMIN_TOKEN` to protect mutating API endpoints. Without it, anyone who can reach port 9001 can send immortal commands, trigger backups, or shut down the server.

```bash
# Generate a good token
openssl rand -hex 32
```

### Container Security

The container runs as a non-root `toc` user. Volumes are owned by that user inside the container.

### Firewall Recommendations (Public Servers)

```bash
# Allow game traffic
ufw allow 9000/tcp

# Allow web admin only from your IP
ufw allow from YOUR.IP.ADDRESS to any port 9001 proto tcp

# Block everything else
ufw default deny incoming
ufw enable
```

---

## Troubleshooting

### "Port already allocated" (9000 or 9001)

Another process has the port. Find and stop it:
```bash
# Linux/macOS
lsof -i :9000
kill -9 <PID>

# Or stop any running ToC container
docker ps
docker stop <container_name>
```

### "exec format error"

The binary was built for a different architecture. Always build locally:
```bash
docker build --no-cache -t toc .
```

### Container starts but game crashes immediately

Check logs:
```bash
docker logs toc
```
Common causes:
- Missing or corrupt area file — check the last line before the crash
- Port conflict — another service on 9000
- Permissions issue on mounted volumes

### Web admin not accessible

1. Verify `-p 9001:9001` is in your `docker run` command
2. Check `docker logs toc` for Python/uvicorn startup errors
3. Disable your firewall temporarily to test: `sudo ufw disable`
4. Test locally first: `curl http://localhost:9001/api/health`

### Players can't connect from outside

1. Check your firewall allows port 9000 inbound
2. Use your public IP or hostname, not `localhost`
3. Check ISP/router NAT port forwarding if behind a home router

### "Permission denied" on player/ or log/ directories

```bash
# Fix ownership (replace 1000 with your UID if different)
sudo chown -R 1000:1000 player/ log/ backups/
```

### macOS native build fails with "strlcpy redefined"

The `#ifndef __APPLE__` guards in `string_safe.c` and `merc.h` should handle this. If you see the error, ensure you're using the current source — older checkouts may not have the guards.

### Server runs but immediately outputs "Segmentation fault"

Rare on current code but can happen with corrupt area files. Run under GDB:
```bash
gdb merc
(gdb) run 9000
(gdb) bt     # backtrace after crash
```

Or use the sanitizer build:
```bash
cmake -B build -DENABLE_SANITIZERS=ON && cmake --build build
cd area && ../bin/rom 9000
```

### Logs show "infinite loop in component_update"

This was fixed in November 2025. Ensure you have the fix by checking:
```bash
grep "attempts > 100" src/update.c
```
If not present, pull the latest code and rebuild.

---

## Credits & License

**Times of Chaos** is based on:
- **Merc 2.1** — Hatchet, Furey, Nemo (1992–1993)
- **ROM 2.4** — Russ Taylor (1993–1996)

Original MUD concept and code lineage trace to **DikuMUD** (1990).

ToC customizations, areas, and modern infrastructure are © their respective contributors.

This software is distributed under terms consistent with the Diku/Merc/ROM licenses:
- Free for personal, educational, and non-commercial use
- Credit to original authors must be preserved
- Commercial use is prohibited without explicit written permission from all original authors

See in-game `credit` and `help diku` commands for the full acknowledgment list.

