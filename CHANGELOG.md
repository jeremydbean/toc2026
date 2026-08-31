# Changelog — Times of Chaos (ToC)

All notable changes to this project are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed

- Fixed Hyrule mobile resets using a population cap of 1,000, which could
  duplicate Ganon and every other surviving NPC whenever an empty area reset
  ran after a player disconnected. Generated limits now match each mobile's
  intended population.

### Added

- Added an authenticated dashboard operations snapshot with game reachability,
  queue depth, backup freshness, recent player saves, runtime-file activity,
  searchable Server Info/WizInfo history, and a compact expandable backup list.
- Added a guaranteed random Ganon relic drop alongside his fixed progression
  loot: the level 54-58 Hero's Tunic, Blue Ring, Red Ring, Mirror Shield, and
  Pegasus Boots. Their unique kill-healing, damage-ward, magic-ward, and travel
  effects are implemented in gameplay and modeled explicitly by `compare`.
- Added bounded semicolon command chaining to both browser game consoles, with
  ordered sends, quote and escape handling, single-entry history, and password
  protection.
- Added a WoW-style permanent character achievement system with 111 cataloged
  accomplishments, points, earned dates, nine categories, hidden discoveries,
  progress views, nearby unlock announcements, retroactive state checks, and
  save-compatible stable keys.
- Added verified world-boss, rare-relic, crafting, unusual-death, Farslay, and
  expanded level achievements, including group boss credit and collection,
  crafting, encounter, and misadventure meta achievements.
- Fixed the player-scribed deadly black Farslay scroll recipe so it contains
  the Vengence spell instead of an invalid legacy skill name.
- Added complete Hyrule achievement tracking for dungeon discovery, maps,
  compasses, Triforce shards, signature items, all nine bosses, grouped boss
  credit, Ganon, Princess Zelda, and campaign-wide meta achievements.
- Added idempotent one-command installers and fresh-machine bootstraps for
  Windows, macOS, Debian/Ubuntu, and Raspberry Pi OS; installers now obtain
  prerequisites, generate private configuration, start Docker, build, launch,
  health-check, and preserve completed work across required OS restarts.
- Added PowerShell/Bash lifecycle launchers with start, build, stop, restart,
  status, logs, doctor, update, and dashboard-open actions, plus double-click
  Windows and macOS install/start entry points.
- Added an advanced in-game `compare` command with player-specific gear
  profiles, focus modes for damage, spells, defense, leveling, and utility,
  full-loadout projections, usability warnings, and percentage recommendations.
- Added a generated Hyrule First Quest area (`30200-30799`) with a teleport-only
  Campus entry, the 128-screen overworld, all nine source-derived dungeon
  layouts, a complete level 1-70 gear curve, and two return routes.
- Added data-driven `burn`, `bomb`, `play`, and `feed` puzzle commands for
  candle bushes, cracked walls, Recorder interactions, and the hungry Goriya.
- Added Hyrule progression tests for every gear level, dungeon entrances,
  boss drops, shard sources, canonical items, puzzles, and room reachability.
- Added a unique readable map and functional boss compass to each Hyrule
  dungeon, including route guidance through legacy portal and stair links.
- Added all First Quest regular, deluxe, and Letter-gated potion shops; 14
  rupee secrets; nine one-time door-repair charges; five money-making games;
  and the four-location Power Bracelet warp network.
- Added the Hyrule `gamble` command, bomb combat against Dodongo, reusable
  Magical Key behavior, consumable dungeon keys, automatic shutters, and
  signature Like Like, Bubble, Wallmaster, Gohma, and Ganon mechanics.
- Added `merc --check-area` / `merc --validate` startup mode for loading the full area database and exiting without opening a listening socket.
- Added reusable area-health linting in `webadmin/area_health.py`, the `scripts/area_lint.py` CLI, a web admin Area Health view, and the `/api/area_health` endpoint.
- Added cross-platform validation runners: `scripts/validate.ps1` for Windows/WSL and `scripts/validate.sh` for Linux, macOS, WSL, and CI.
- Added GitHub Actions validation in `.github/workflows/validate.yml`.
- Added Python unit tests for area-health summaries and key web-admin API behavior.
- Added the immortal `diagnostics` command for boot time, world totals, descriptor/list counts, active mobs, and backup schedule visibility.

### Changed

- Psionic travel, scouting, retrieval, control, draining, healing, and defense
  powers now share consistent room protection, saving throw, mana, lag, skill
  improvement, and combat-start behavior.
- Replaced contradictory psionics help with an accurate 17-power player guide,
  real remort selection rules, command costs, defense values, and restrictions.
- Docker Compose now binds both ports to loopback by default, supports explicit
  host bind/port variables, persists god/hero/corpse state, and reports game
  readiness through a container health check. Public install mode exposes only
  the game port.
- Docker image builds now exclude private runtime state, logs, backups, and
  `.env` from their context and create empty runtime mount points instead.
- Container startup now maps its unprivileged `toc` account to configured host
  UID/GID values before dropping privileges, allowing fresh Linux bind mounts
  to remain writable without running the game or dashboard as root.
- Area-health source tracking now follows `P` reset chains back to a real room
  or mobile source, without hiding objects inside unreachable containers.
- Expanded web admin configuration with `AREA_PATH`, `BACKUP_PATH`, `--area-path`, and `--backup-path`.
- Web admin reloads now validate a complete replacement parser, reject critical issues with HTTP 422, preserve the last known-good data on failure, and list recent backup archives.
- Operational web-admin endpoints are disabled until `WEB_ADMIN_TOKEN` is configured; queue payloads are bounded and restricted to one protocol-safe line.
- Player-save snapshots now use bounded native path construction and directory creation instead of shell-built `mkdir` commands.
- Backup archive creation now verifies shell command return codes, creates the backup directory when needed, and logs success only after archive creation succeeds.
- Rebuilt the repository documentation around dedicated player, command,
  hosting, operator, developer, contributing, and security guides; the README
  is now an accurate project front door instead of a mixed-audience manual.
- Corrected documented build paths, player/immortal level boundaries, remort
  thresholds, current world totals, web API routes, Docker restart behavior,
  dashboard exposure, legacy DES/Telnet limitations, and bow/run/speedwalk help.
- Replaced obsolete install/startup/cleanup/refresh instructions that used
  hard-coded paths, permissive modes, binary copies, and broad process kills
  with current prerequisite helpers and safe compatibility wrappers.
- Added `.env` Git/Docker exclusions, a safe `.env.example`, and ignore rules
  that prevent newly created player/god/hero files from being staged by
  accident; documented that already tracked legacy hashes remain exposed.
- Hyrule documentation now records source provenance, coordinate conversion,
  generated vnum ranges, progression, secrets, runtime rules, fidelity limits,
  regeneration, and regression coverage.

### Fixed

- Invalid portals no longer consume gold or charges, crystal-ball entry now
  replies to the player, successful Riding improves correctly, saddles use
  normal equipment hooks, and stale or invisible mount state no longer crashes
  or broadcasts uninitialized text.
- Monk buffs no longer consume mana when already active, ghost-blocked attacks
  no longer consume mana or movement, and a failed Crane Dance now uses its
  documented 30 mana while recording a failed skill attempt.
- Bulk `put` now rolls concealment independently for every item and reports an
  empty match; lycanthropy checks every weather tick, avoids reinfecting tagged
  mobiles, bounds restored were-form inventory, and skips stale object vnums.
- Immortal were-form editing now rejects negative indexes instead of reading
  before the form table.
- Dashboard view changes now return to the top instead of carrying a long
  Operations-page scroll offset into Overview or another section.
- Fixed `AUTOGOLD` searching the room instead of the defeated mobile's corpse,
  and made `AUTOSAC` preserve every corpse that still contains money, boss
  drops, or loot the player could not carry.
- Repaired normal bow shooting through closed or secret exits, silent immunity
  on `NOPURGE` mobiles, unsupported player targeting, missing Archery skill
  improvement, unsafe pursuit through one-way/transport exits, and potentially
  lethal anti-cheese backlash.
- Restored city guards' unreachable innocent-protection behavior, prevented an
  NPC cleric using Mana Convert from dereferencing player-only data, and fixed
  shield reflection leaving a one-hit-point attacker marked dead.
- Applied the Red Ring, Blue Ring, and Mirror Shield wards to reflected fire and
  frost damage so those effects match their player-facing descriptions.
- Made Ganon's Silver Arrow finale an explicit `shoot ganon` action, available
  at level 54 without Archery skill, while preserving the Arrow's boosted
  normal damage and preventing normal attacks from delivering the final blow.
- Ganon's one-hit-point phase now ends combat for every attacker, turns his
  room appearance bright red, announces the Silver Arrow opening, and repeats
  that instruction when players look at him.
- Lowered Hyrule's required Silver Arrow from the immortal-only level 68 range
  to the maximum mortal level 59, restoring a mortal path to defeating Ganon.
- Fixed paged commands exposing raw `{0D` color tokens instead of terminal
  colors, and compacted the achievement summary into paired category columns
  so its normal overview fits within the default page length.
- Fixed Telekinesis bypassing take, corpse-looting, bound quest-item, and
  no-teleport rules; Confuse requiring 139 mana instead of its actual cost;
  Clairvoyance counting remote views as physical exploration; astral travel
  charging before target validation; and Project possessing the wrong ghost.
- Fixed Enervate healing from resisted damage, empty or duplicate defensive
  casts consuming full mana, Transfusion allowing ineffective casts without
  lag or skill improvement, and invalid `grantpsi` lists unlocking no powers.
- Fixed psionic special mobiles overwhelmingly selecting Torment, restored
  reliable self-defense casting, and added fair use of newer combat powers.
- Reworked automatic quests to choose suitable live targets, credit nearby
  group members and pet-assisted kills, accept turn-ins at any questmaster,
  bind and clean up recovery tokens, find tokens inside containers, and save
  cooldown and timeout transitions immediately. Protected service mobiles,
  explicitly unkillable targets, and ghosts are no longer selected.
- Fixed active-quest logout preserving streaks, heroes being unable to abort,
  object quests having a different cooldown, practice rewards disagreeing with
  their advertised range, malformed gamble percentages, reward additions
  overflowing the quest-point balance, and remort preserving a high-level
  quest after returning the player to level 3.
- Replaced the quest shop's mislabeled translucent-key "trophy" with a real
  questmaster keepsake, hardened missing reward prototypes, and added quest
  achievements for 250 completions, a 25-win streak, rushes, final-minute
  turn-ins, gamble wins, and acquiring the keepsake.
- Fixed `lore` allowing negative research fees to pay repeatable gold, omitting
  its value estimate, hiding later spells, and miscalculating negative affects
  and weapon averages.
- Fixed Raise Dead destroying belongings the revived player could not carry,
  ambiguous player matching, and unsaved recoveries; heavy items now remain in
  the corpse and the spell requires the exact online owner.
- Fixed soul trapping overlooking later empty bottles, unsaved soul capture and
  release, Water Burst wasting all water, Geyser destroying its container, and
  Transfusion allowing its user to remain standing at zero hit points.
- Kept skeletons, wraiths, and vampires charmed for their full summoned lives,
  rather than allowing them to roam uncontrolled after an early charm expiry.
- Fixed multi-race equipment being wearable by no race, repaired the slots and
  advertised powers of five signature relics, and preserved invisibility,
  detect-invisibility, and flight when another worn, racial, or spell source
  still grants the effect.
- Prevented pending automatic-quest gamble rewards from being overwritten,
  bounded practice and quest-streak rewards, persisted quest state promptly,
  cleared rush state on abort, and allowed the hero experience exchange at the
  exact required experience threshold.
- Fixed fire, frost, and death-shroud shield state checks so mutually exclusive
  shields cannot stack, and capped energy-drain healing at maximum hit points.
- Made `concoct` and `scribe` recipes ingredient-order independent, removed
  failed-craft object leaks, preserved ingredients for unknown recipes, saved
  consumed rare components immediately, and corrected their player help.
- Fixed stale seasonal-vendor pointers that could crash timed despawns, restored
  event-boss defeat announcements, moved holiday rewards into corpses, and
  guaranteed each event boss awards at least one primary rare item.
- Bounded Hero Quest item lookups, saved each recovered relic, removed temporary
  magic immunity and no-follow state on every exit, and safely floored abandon
  penalties while keeping current and maximum health consistent.
- Fixed death ray falsely announcing Ganon's death before his protected reform,
  and documented the permanent training reward on the two rare holiday foods.
- Fixed the advertised quest-shop Potion of Power, Potion of the Giant, and
  Scroll of Farslay never appearing in `AQUEST LIST` or being purchasable.
- Fixed Farslay scrolls consuming themselves without a target, leaking or
  removing the reader's holy-light setting, and resolving duplicate Farslay
  slots as repeated deaths and permanent penalties.
- Bounded Farslay's permanent resource and attribute costs, protected NPC
  casters from player-data access, and stopped protected Ganon attempts from
  falsely announcing and logging his death.
- Fixed Herbie's automatic rescue choosing an arbitrary wounded player due to
  integer division, being blocked by invalid or link-dead candidates, moving
  away while fighting, flooding recipients with hundreds of heal messages,
  and returning to a hard-coded room instead of his actual origin.
- Fixed ordinary seasonal candy corn and spiced cider using the rare training-
  food type, which let inexpensive vendor snacks grant permanent trains.
- Prevented training-food rewards from overflowing the 16-bit train counter,
  saved them immediately after consumption, corrected their displayed type,
  and exposed the type accurately in the web area browser.
- Fixed `remort <password> ...` and `resetpwd <player> <newpassword>` being
  registered as `LOG_ALWAYS`, which wrote plaintext password arguments to game
  logs and snoop output; added a regression test for all credential commands.
- Fixed off-hand attacks using main-hand proficiency, secondary wield bypassing
  item restrictions, and failed weapon swaps removing the equipped weapon.
- Fixed comparison estimates for off-hand proficiency, low-skill unarmed damage,
  two-handed no-remove conflicts, and engine-applied experience bonuses.
- Fixed Hyrule's inactive Raft gate, two nonlethal dead ends, mismatched armor
  slots, held Recorder use, and Recorder effects weakening unrelated NPCs.
- Fixed incorrect overworld locations for Levels 8 and 9, the White and Master
  Swords, Princess Zelda's Letter, and the Power Bracelet.
- Fixed legacy Hyrule shopkeeper vnums being shared with dungeon elders and
  combat mobiles; generated vendors now use dedicated prototypes and stock.
- Fixed dungeon maps and compasses remaining readable while blind or in darkness.
- Fixed inferred dungeon wall links by deriving all 56 First Quest bomb walls
  from the paired NESMaps room markers, including Death Mountain's 19 pairs.
- Fixed single-item gear comparisons matching unrelated worn objects through
  the universal `ITEM_TAKE` flag instead of an actual shared equipment slot.
- Fixed the CMake/C17 build using unavailable BSD `strlcpy`/`strlcat` calls
  instead of the repository's portable bounded string helpers.
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
