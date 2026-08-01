# Changelog — Times of Chaos (ToC)

All notable changes to this project are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added

- Added the remastered Hyrule area (`30200-30799`) with a teleport-only Campus
  arcade entry, all nine original Zelda labyrinths, a complete level 1-70 gear
  curve, the Triforce reward chain, and two return portals.
- Added data-driven `burn`, `bomb`, `play`, and `feed` puzzle commands for
  candle bushes, cracked walls, Recorder interactions, and the hungry Goriya.
- Added Hyrule progression tests for every gear level, dungeon entrances,
  boss drops, shard sources, canonical items, puzzles, and room reachability.
- Added `merc --check-area` / `merc --validate` startup mode for loading the full area database and exiting without opening a listening socket.
- Added reusable area-health linting in `webadmin/area_health.py`, the `scripts/area_lint.py` CLI, a web admin Area Health view, and the `/api/area_health` endpoint.
- Added cross-platform validation runners: `scripts/validate.ps1` for Windows/WSL and `scripts/validate.sh` for Linux, macOS, WSL, and CI.
- Added GitHub Actions validation in `.github/workflows/validate.yml`.
- Added Python unit tests for area-health summaries and key web-admin API behavior.
- Added the immortal `diagnostics` command for boot time, world totals, descriptor/list counts, active mobs, and backup schedule visibility.

### Changed

- Area-health source tracking now recognizes objects loaded inside containers by
  `P` resets, avoiding false orphan reports for nested rewards.
- Expanded web admin configuration with `AREA_PATH`, `BACKUP_PATH`, `--area-path`, and `--backup-path`.
- Web admin reloads now validate a complete replacement parser, reject critical issues with HTTP 422, preserve the last known-good data on failure, and list recent backup archives.
- Operational web-admin endpoints are disabled until `WEB_ADMIN_TOKEN` is configured; queue payloads are bounded and restricted to one protocol-safe line.
- Player-save snapshots now use bounded native path construction and directory creation instead of shell-built `mkdir` commands.
- Backup archive creation now verifies shell command return codes, creates the backup directory when needed, and logs success only after archive creation succeeds.
- Documentation now covers validation, CI, area-health severities, backup behavior, web-admin authentication, and operational troubleshooting.

### Fixed

- Fixed the PowerShell startup smoke test treating a healthy timeout-driven
  server shutdown as a validation failure.
- Fixed Unix game-loop web-admin queue processing so queued dashboard actions are handled on Linux/Docker builds.
- Fixed a web-admin queue race that could lose actions appended while the game loop read and deleted the queue file.
- Fixed player saves reporting success and creating snapshots after failed writes or failed atomic replacement.
- Fixed player restore overwriting the live file before its snapshot copy completed; restores now force a pre-change snapshot and atomically replace from a temporary file.
- Fixed null-stream crashes in corpse history and `areasave` failure paths, and bounded corpse-history item counts read from disk.
- Fixed shared text readers hanging or mishandling EOF when a data file ends without a newline.
- Fixed repeated area-parser and wizlist loads retaining stale state or using an invalid list tail.
- Fixed stale review/documentation notes for the previously resolved `areaload` double-close and flood movement checks.

---

## [2026.04 (April 2026)] — Area Content & Stability

### Fixed — Spelling & Grammar in World Files (Rounds 1–30)

A comprehensive audit of all 132 `.are` files was performed, correcting over 400 spelling, grammar, and article errors. Areas modified across all 30 rounds:

**Rounds 1–10** (various .are files):
- `alot` → `a lot` across many files
- there/their/they're errors
- `immediatly` → `immediately` (multiple areas)
- `strangly` → `strangely`
- Apostrophe errors in contractions and possessives
- Double-word errors (`the the`, `in in`, etc.)
- `erradicate` → `eradicate`
- `heros` → `heroes`

**Rounds 11–20**:
- Continued systematic scan across remaining areas
- Corrected verb agreement and pluralization errors
- Various jumbled/transposed word fixes

**Rounds 21–30** (specific, documented):
- `Round 21` — `kerofk.are`: Removed redundant `potatoe` keyword; fixed `potatoe^H` (literal backspace control character artifact)
- `Round 22` — 14 files: `forboding`→`foreboding` (nether, despair, scult, prison, abyss); `amazment`→`amazement` (gcult); `unconsious`→`unconscious` (glitter); `preperation`→`preparation` (nethril1); `beneith`→`beneath`, `pedistal`→`pedestal` (tarin); `pedastal`→`pedestal` (mountain ×2); `stalagtites`→`stalactites` (horde); `Persistant`→`Persistent` (camelot); `apparant`→`apparent` (newthalo); `boundries`→`boundaries` (world)
- `Round 23` — 9 files: `Calender`→`Calendar` (korzath2); `unfamilar`→`unfamiliar` (dresden, dresden_halloween, dresden_xmas); `equipement`→`equipment` (highland); `nonexistance`→`nonexistence` (crypt); `harrasing`→`harassing` ×4 each (limbo, limbo_xmas, limbo_halloween)
- `Round 24` — 11 files: `headress`→`headdress` ×5 (northsea), ×2 (arac); `a animal`→`an animal` (horde); `a ever/emerald/even/orderly/even/orange/object/alchemy` → `an` article fixes (valhalla, mountain, ultima, solace, commands, dresden×3)
- `Round 25` — 6 files: `a elder`→`an elder` (nether); `a iron handle`→`an iron handle` (camelot); `a oak door`→`an oak door` ×2 (solace); `a east-north`→`an east-north` (moria); `a incessant`→`an incessant` ×2 (canyon); `a everlasting`→`an everlasting` (sewer)
- `Round 26` — 7 files: `terrrifying`→`terrifying` (valhalla); `apperance`→`appearance` (ag); `Sacraficial`→`Sacrificial` ×2 (abyss); `decend`→`descend` ×4 (sea), ×1 each (nether, horde, connect)
- `Round 27` — 3 files: `parliment`→`parliament` (connect); `throught`→`through` ×6, `wich`→`which` (mid_ruin); `throught`→`through` (astral)
- `Round 28` — 4 files: `crouds`→`crowds` ×3 (limbo, limbo_xmas, limbo_halloween); `maintenence`→`maintenance` ×2 (lud)
- `Round 29` — 4 files: `inscripted`→`inscribed` ×2 (ofcol), ×1 (plains); `Dispite`→`Despite` (solace); `indiscernable`→`indiscernible` (istari); `infititely`→`infinitely` (istari)
- `Round 30` — `mid_ruin.are`: `remains fo the southern` → `remains of the southern`

---

### Added — New Content

- **`area/ashen_wastes.are`** — New grinding zone "The Ashen Wastes" (vnums 26700–26799): scorched post-apocalyptic landscape with progressive difficulty mobs and rare material drops

- **Quest shop items** — Three new items purchasable with quest points:
  - Potion of Power (+str/dex/con temporarily)
  - Potion of the Giant (+str/size)
  - Scroll of Farslay (ranged damage spell)

- **Seasonal area system** — Framework for holiday events, weather-tied spawns, and seasonal bosses:
  - `dresden_halloween.are`, `limbo_halloween.are` — Halloween variants
  - `dresden_xmas.are`, `limbo_xmas.are`, `midennir_halloween.are` — Christmas/holiday variants
  - Wandering seasonal vendors appear during events
  - Holiday area portals open/close based on in-game date

- **Pyrotechnics overhaul** — `spell_pyrotechnics` fully rewritten as a psi-class area attack with proper scaling and status effects

- **Heated gear mechanic** — Objects can gain a `heated` flag (from fire magic, traps, environment); wearing heated gear deals passive burn damage; cooling happens over time via `update.c`

### Added — Immortal Commands (11 new)

Implemented in `src/act_wiz.c`:

| Command | Level | Description |
|---------|-------|-------------|
| `mute` | L65 | Toggle all speech: sets COMM_MUTE + NOCHANNELS/NOTELL/NOSHOUT/NOEMOTE |
| `drag` | L66 | Pull any online PC to your current room |
| `duel` | L64 | Force two online PCs into PK combat (transports p2 to p1's room) |
| `weather` | L65 | Set global weather: sunny/cloudy/rain/storm |
| `lights` | L65 | Toggle ROOM_DARK flag on current room |
| `seal` | L65 | Toggle EX_WIZLOCKED on a room exit by direction |
| `finger` | L65 | Player info lookup (online: live stats; offline: saved file scan) |
| `trail` | L67 | Show last `TRAIL_LEN` rooms visited (ring buffer in `pc_data`) |
| `petrify` | L65 | Apply timed 'stone' affect blocking ALL commands |
| `empower` | L64 | Apply sanctuary + haste + fly + passdr + protect + regen + divprot + stat boosts |
| `colossus` | L64 | Apply 500% HP/mana/move boost, heal to full (`gsn_titanic` affect) |

Infrastructure changes for new commands:
- `MAX_SKILL` bumped 228 → 231
- `COMM_MUTE` added to comm flags
- `TRAIL_LEN 10` constant; `int trail[TRAIL_LEN]` + `sh_int trail_head` in `pc_data`
- `gsn_empower`, `gsn_titanic`, `gsn_petrify` globals added
- `petrify` affect blocks ALL commands in interpreter (`interp.c`)

---

### Fixed — Crash & Stability Bugs

A systematic use-after-free (UAF) and NULL-dereference audit was performed across the entire C source tree:

- **`src/fight.c`** — Fixed UAF in `damage()` autoloot block after `raw_kill`; fixed UAF in `fatality()` autoloot block
- **`src/magic.c` / `src/magic2.c`** — Fixed 7 spell bugs; chain lightning UAF (death-check each arc target); missile/skeletal_hands loop UAF
- **`src/update.c`** — Fixed `component_update()` infinite loops (random-vnum `for(;;)` loops now bounded to 200 attempts); fixed misindented `component_update()` calls in `weather_update()` causing stack corruption; fixed UAF in river room sweep; `char_update`, `dtrap_update`, `hit_gain`, `mana_gain` NULL guards
- **`src/skills.c`** — Fixed out-of-bounds and UAF in skill loops
- **`src/special.c`** — Fixed `spec_black_dragon` character scan NULL deref; fixed `spec_whine` NULL deref; fixed `spec_healer` NULL deref (`most_hurt` in-room check)
- **`src/save.c`** — Fixed NULL deref crashes in player save/load
- **`src/act_wiz.c`** — Fixed NULL deref crashes
- **`src/quest.c`** — Added `in_room` NULL guard before questmaster search in `do_quest`
- **`src/trap.c`** (via fight/update) — Fixed guardian trap UAF; fixed `do_manipulate` trap case 3 send-after-free
- **`src/magic.c`** — Restored `spell_rope_trick` which was accidentally disabled; fixed `spell_haven` infinite loop
- Fixed 5 bugs flagged by GCC static analysis (`-Wduplicated-cond`, `-Wlogical-op`, `-Wnull-dereference`)
- Fixed 3 bugs in arena/death/fight code (arena exit, death inventory handling)
- All `for(;;)` random-vnum loops bounded to max 200 attempts (prevents game freeze)

---

### Changed — Build System & Infrastructure

- **`src/act_wiz.c`**: `fgets()` magic number `80` replaced with `sizeof(arg)` for maintainability
- **`webadmin/server.py`**: Added `WEB_ADMIN_TOKEN` environment variable; mutating API endpoints now require `X-Admin-Token` header when token is set
- **`area/resolve.c`**: Moved to `archive/resolve.c` — dead code (legacy ident resolver, not compiled)
- **`webadmin/server.py`**: Removed duplicate import block (lines 13–24 were identical to lines 1–12)
- **`src/act_info.c`**: Two remaining `strcat()` calls converted to `strlcat()` with `sizeof(buf)` bounds

---

## [2025.11 (November 2025)] — String Safety & Infrastructure Overhaul

### Added — String Safety Infrastructure (PRs #11–27)

A comprehensive string safety refactor replacing all unbounded string functions (`strcpy`, `strcat`, `sprintf`) with bounded equivalents throughout the codebase:

- **`src/string_safe.c`**: New module providing OpenBSD-style `strlcpy()` and `strlcat()` implementations with guaranteed null-termination
- **`src/merc.h`**: Added `strlcpy`/`strlcat` prototypes; `UNUSED_PARAM(x)` macro for clean unused-parameter suppression; `#ifndef __APPLE__` guards for `<crypt.h>` include; modernized `bool` and integer types

**Modules converted (PR by PR):**
- `src/act_comm.c` — All `sprintf`/`strcpy`/`strcat` → `safe_strcpy`/`safe_strcat` wrappers
- `src/act_wiz.c` — Fully converted to `snprintf`/`strlcpy`/`strlcat`; `clamp_sh_int` helper for wizard-set commands
- `src/comm.c` — `safe_strcpy`/`safe_strcat` throughout; port validation before `htons`; widened descriptor handles to `int`
- `src/handler.c` — Flag/bit-name builders from repeated `strcat` → bounded `strlcat`
- `src/wizlist.c` — Formatting converted to `snprintf`
- `src/magic.c` — Fully converted; cleaned signed/unsigned comparisons; `spell_heat_metal` reorganized
- `src/act_obj.c` — `snprintf` for all formatted messages
- `src/db.c` — Area file names, socials, default room text, bug logging bounded; `fread_sh_int`/clamp helpers added
- `src/save.c` — No unsafe functions detected in audit
- `src/hunt.c` — Bounded buffer for secret-door door commands
- `src/magic2.c` — `do_lore` flow tidied; trap direction/keyword formatting capped; damage table bounds aligned
- `src/skills.c`, `src/special.c`, `src/update.c`, `src/quest.c`, `src/pkill.c` — All converted

### Added — Modern Build Systems

- **`CMakeLists.txt`** (PR #4–7): CMake build system targeting C17 standard with:
  - Explicit source file list (reproducible builds)
  - Optional AddressSanitizer + UBSanitizer via `-DENABLE_SANITIZERS=ON`
  - Output to `bin/rom` (separate from Makefile's `merc`)
  - clang-format configuration (`.clang-format`)

- **`Dockerfile`** (PR #8): Multi-stage Docker build:
  - Build stage: `debian:bookworm-slim` + build-essential + cmake
  - Runtime stage: minimal with only `libcrypt1` + Python 3 + FastAPI/uvicorn
  - Non-root `toc` user for container security
  - `EXPOSE 9000`

- **`docker-compose.yml`** (PR #3): Multi-service orchestration:
  - `game` service: MUD server on 9000/9001
  - `middleware` service: Python bridge on 8000
  - Volume mounts for `player/`, `log/`, `area/`

### Added — Network & Socket Modernization (PR #10)

- Socket handling in `src/comm.c` modernized to use POSIX-standard APIs
- `O_NONBLOCK` set via `fcntl` (replacing deprecated flags)
- `socklen_t` used consistently for address length parameters

### Added — Web Admin

- **`webadmin/server.py`**: FastAPI web administration panel:
  - `QueueWriter` class for IPC to game via `area/webadmin.queue`
  - Dashboard HTML (self-contained, no external CDN dependencies)
  - WebSocket `/ws/logs` for real-time log streaming
  - `/api/health` — checks merc and uvicorn process status
  - Player browser, area browser (mobs/objects/rooms), best gear finder
  - `docker-entrypoint.sh` starts uvicorn automatically

### Added — Setup Scripts

- `scripts/setup_windows.ps1` — Chocolatey-based Git + Docker Desktop installer
- `scripts/setup_mac.sh` — Homebrew-based installer (Intel + Apple Silicon aware)
- `scripts/setup_linux.sh` — apt-based Docker + git installer

### Fixed — Compiler Warnings

Extended warning set (`-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual`) builds cleanly:

- `UNUSED_PARAM` macro applied across all command/spell stubs
- Renamed shadowing locals in `act_wiz.c`, `comm.c`, `db.c`, `magic.c`, `save.c`, `special.c`, `update.c`
- `int_app` fixed: both `learn` and `mana_gain` fields now initialized
- `race_type` sentinel fills every field
- `hunt_victim` uses bounded buffer
- `act_new`/`act_public` const-correct; `is_name` works on local copies
- `-Wconversion` hotspots: `sh_int` clamping in `act_comm.c`, `act_info.c`, `act_move.c`, `act_obj.c`, `act_wiz.c`, `comm.c`, `db.c`, `fight.c`, `handler.c`

---

## [Initial] — 2025-11-18 (Initial Commit)

- Initial repository created from legacy ToC codebase
- 132 area files loaded and compiling
- Basic Makefile with gnu89 build flags
- Existing MUD engine code (Merc/ROM derivative with ToC customizations)
