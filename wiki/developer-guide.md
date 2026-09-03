# Times of Chaos Developer Guide

This guide explains the repository architecture, development environment,
validation workflow, extension points, data rules, debugging tools, and release
expectations. Read [CONTRIBUTING.md](../CONTRIBUTING.md) for the concise change
checklist and [AGENTS.md](../AGENTS.md) for automation-specific repository rules.

## Architecture

ToC combines a legacy single-process C MUD with a separate Python operations
application.

### C Game Server

`merc` owns authoritative live state:

- TCP/Telnet descriptors and login state
- characters, mobiles, objects, rooms, affects, combat, and updates
- commands, skills, spells, quests, guilds, remorts, and persistence
- area boot/loading from `area/area.lst`
- player saves, player snapshots, archive scheduling, and command queue intake

The design is event-loop based rather than thread-per-player. Changes in global
lists, extraction, movement, combat, and update code can affect every connected
player and deserve broader testing.

### Python Dashboard

`webadmin/server.py` runs FastAPI/Uvicorn and owns no authoritative game state.
It:

- parses area files independently through `webadmin/area_parser.py`
- computes findings through `webadmin/area_health.py`
- parses player files for browsing
- reads logs and backup metadata
- writes high-impact actions to `area/webadmin.queue`
- bridges a browser WebSocket to the local game port

Dashboard `reload` swaps the Python parser after critical validation succeeds.
It does not hot-reload the C game's world.

### Data Flow

```text
area/*.are + area/area.lst -----> merc boot -----> live game state
             |                         ^
             +----> AreaParser         |
                         |              |
player/* -------------->+--> dashboard +-- area/webadmin.queue
log/toc.log ------------>+
backups/*.tar.gz -------->+
```

Do not mistake a successful dashboard parse for a successful native world boot.
The parsers have different purposes and both must pass.

## Repository Layout

| Path | Purpose |
|---|---|
| `src/` | Game server C sources and headers |
| `area/` | World, help, social, and load-list data |
| `webadmin/` | FastAPI app, area parser, and health engine |
| `tests/` | Python unit/API/progression tests |
| `scripts/` | Validation, setup, Hyrule generation, and utilities |
| `data/` | Structured source manifests |
| `wiki/` | Maintained user and technical documentation |
| `notes/` | Design records and audits, not the primary user docs |
| `archive/` | Retired source kept for reference, not linked into runtime |
| `player/` | Mutable character files; sensitive and normally off-limits |
| `gods/`, `heroes/` | Mutable staff/hero data; sensitive |
| `backups/`, `log/` | Runtime output |
| `.github/workflows/validate.yml` | CI entrypoint |

## Core C Module Map

| Module | Main responsibility |
|---|---|
| `comm.c` | Process startup, sockets, descriptors, login flow, output, pager, main loop |
| `color.c` | Canonical color tokens, per-player color settings, ANSI conversion |
| `db.c` | World boot, area parsing, indexes, allocation, database helpers |
| `merc.h` | Shared types, constants, flags, macros, and function declarations |
| `interp.c`, `interp.h` | Command table, dispatch, command declarations |
| `act_move.c` | Movement, exits, doors, recall, mounts, run/speedwalk |
| `act_info.c` | Player information, help-facing displays, leveling/remort UI |
| `achievements.c` | Achievement catalog, progress, events, display, and persistence helpers |
| `act_obj.c` | Inventory, equipment, consumables, shops, banks, item actions |
| `act_comm.c` | Channels, tells, socials, notes, and communication state |
| `act_wiz.c` | Immortal operations, diagnostics, restoration, moderation |
| `fight.c` | Combat loop, attacks, death, fleeing, ranged combat |
| `magic.c`, `magic2.c` | Spells and magical effects |
| `skills.c` | Skill groups, practice/gain/teaching, skill utilities |
| `gear_compare.c` | Advanced loadout/profile comparison model |
| `handler.c` | Character/object/affect lookup and state helpers |
| `update.c` | Periodic updates, advancement, archive backups, world ticks |
| `save.c` | Player serialization, loading, and version snapshots |
| `quest.c`, `pkill.c` | Automated quest and player-killing systems |
| `special.c` | Mobile special functions |
| `script_event.c` | Scripted event support |
| `season.c` | Seasonal world behavior |
| `string_safe.c` | Bounded string compatibility helpers |
| `const.c` | Class, race, skill, group, title, and constant tables |

Before editing a module, trace its declarations and call sites with `rg`. Legacy
code often shares behavior through globals and macros rather than an obvious
modern interface.

## Toolchain And Builds

### Make Build

The primary Make build uses GCC with GNU89 compatibility:

```bash
make clean
make
```

Default compile definitions/options include `-std=gnu89`, `-O2`, `-fcommon`,
`-DROM`, `-Dunix`, `-Wall`, and `-Wextra`. Linux links `libcrypt`, `libm`, and
`libz`; macOS links `libm` and `libz` and expects `crypt` from the platform C
library. `libz` backs MCCP2 output compression in `src/telnet_proto.c`.

Override warning flags without editing the Makefile:

```bash
make clean
make WARNFLAGS='-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual'
```

The output is `./merc`.

### CMake Build

CMake uses C17, an explicit source list, stricter baseline diagnostics, and
optional AddressSanitizer/UndefinedBehaviorSanitizer support:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Output is `bin/rom` at the repository root, not inside the build directory.

Sanitizer build:

```bash
cmake -S . -B build-sanitize \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_SANITIZERS=ON
cmake --build build-sanitize
cd area
ASAN_OPTIONS=detect_leaks=1 ../bin/rom --check-area
```

When adding a new C source file, update `CMakeLists.txt`. Make discovers
`src/*.c`, but CMake intentionally does not glob.

## Runtime Working Directory

Legacy paths in `merc.h` and runtime code are relative to `area/`. Launch from
that directory:

```bash
cd area
../merc 9000
../merc --check-area

# CMake binary:
../bin/rom 9000
```

`startup.sh` handles the directory change and logging when invoked from the
repository root. A server started from the wrong directory may fail to find
`area.lst`, player files, logs, or backups.

Compatibility entrypoints are intentionally conservative: root `startup` and
`area/startup.sh` delegate to `startup.sh`; root `install` delegates to the
Linux setup helper; `cleanup` only removes build output; and `refresh` builds
and validates without killing or restarting a process. `zStartup/` is archived
machine-specific history and is not executable guidance.

## Python Environment

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r webadmin/requirements.txt
python -m pip install -r scripts/requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r webadmin\requirements.txt
python -m pip install -r scripts\requirements.txt
```

The Windows full validator also requires WSL because the C runtime and native
area boot are POSIX-oriented.

## Full Validation

### Linux, macOS, And CI

```bash
bash scripts/validate.sh
```

### Windows PowerShell

```powershell
.\scripts\validate.ps1
.\scripts\validate.ps1 -RunSmoke
.\scripts\validate.ps1 -Distro Ubuntu-24.04
```

The suite covers:

1. clean default C build
2. clean strict-warning C build
3. native `merc --check-area`
4. optional timed live startup smoke
5. Python syntax compilation
6. parser inventory and exit/reset/shop references
7. shared area-health linting
8. Python unit/API tests
9. `git diff --check`

Run the full suite before merging changes to shared gameplay, persistence,
world loading, build configuration, generated content, or dashboard contracts.

## Focused Validation

```bash
# Native database boot without opening a listening socket.
cd area
../merc --check-area
cd ..

# Parsed world inventory.
python3 check_parser.py

# Cross-reference checks.
python3 check_exits.py
python3 check_resets.py
python3 check_shops.py

# Shared dashboard/CLI health engine.
python3 scripts/area_lint.py --fail-on critical --limit 20
python3 scripts/area_lint.py --format json --output area-health.json

# Tests.
python3 -m unittest discover -s tests

# Patch hygiene.
git diff --check
```

August 2026 parser baseline:

```text
99 listed area entries
2,336 mobiles
3,557 objects
7,781 rooms
0 critical, 11 warning, 1,571 information area-health findings
```

Six `area.lst` entries (`commands.are`, `skills.are`, `spells.are`,
`masters.are`, `toc.are`, and `social.are`) are help/social files without an
`#AREA` record. The C server also creates one online-building area at boot, so
native and Python area totals are expected to use different counting models.

## Test Layout

| Test file | Coverage |
|---|---|
| `tests/test_area_health.py` | Parser/health issue detection and severity behavior |
| `tests/test_webadmin_api.py` | API authentication, queueing, reload, parsing, and limits |
| `tests/test_hyrule_progression.py` | Generated Hyrule topology, progression, bosses, items, and routes |
| `tests/test_achievements.py` | Catalog stability, persistence, event hooks, world/Hyrule boss-room contracts, rare-item vnums, Farslay crafting, summary layout, and pager color conversion |

Add focused regression tests for fixed bugs. Expand to integration/smoke testing
when a change crosses C/Python, parser/runtime, persistence, or world boundaries.

## Adding Or Changing A Player Command

1. Find the command in `src/interp.c` and its `do_*` function.
2. Add or update the declaration in `src/interp.h` or the established shared
   header used by that subsystem.
3. Implement behavior in the owning module, preserving command position, trust,
   logging, and visibility semantics.
4. Validate all early returns restore temporary/global state.
5. Consider NPC callers, extracted/killed characters, combat transitions,
   movement traps, charm, switched staff, and invalid/hostile input.
6. Add or update the matching help entry in the correct Latin-1 `.are` help
   file, normally `area/commands.are`.
7. Test exact syntax, abbreviations, no arguments, bad arguments, unavailable
   state, success, and interrupted success.

Command-table order matters because prefix matching selects the first eligible
match. Place aliases deliberately and use `LOG_NEVER` for password-bearing
commands.

## Player Output, Color, And Paging

Game source uses canonical three-byte `{HH}` color tokens, where `HH` is a
hexadecimal color slot. Player-facing output must use one of the normal paths:

- `send_to_char()` color-converts immediate output for the recipient.
- `page_to_char()` color-converts once, then stores the converted text in the
  descriptor pager for `show_string()` to send a page at a time.
- A player with color disabled receives the same text with color markers
  removed.

`write_to_buffer()` is a descriptor/protocol primitive. Do not pass raw
player-facing color tokens to it or to `show_string()`; those layers expect
plain text, protocol bytes, or text already converted for that descriptor.
Likewise, do not HTML-encode spaces for the web client. The browser bridge
transports Latin-1 text, and `client.js` renders it through text nodes while
parsing ANSI into fixed CSS classes.

For formatted command changes, test color on and off, `scroll 0` and a finite
page length, continuation prompts, narrow terminal wrapping, and both summary
and long-list views. Keep frequently used summaries within the default page
length when doing so does not hide useful information.

## Skills, Spells, Classes, And Races

Definitions are distributed across `src/const.c`, `src/merc.h`, skill/spell
implementations, group tables, and help data. A complete change may require:

- `gsn_*` declaration and slot/table entry
- class level/rating values
- skill group/default group membership
- command or spell function declaration/implementation
- save compatibility for new persistent fields
- help entry and player-facing syntax
- trainer/guildmaster exposure
- object spell slots for consumables
- tests across every eligible and ineligible class/guild/race

Never renumber persisted enums, wear locations, spell slots, or flags casually.
Area files and player files store many values numerically.

## Persistence Changes

Player files are an external compatibility contract. When adding a field:

1. Choose a unique, stable save keyword.
2. Write the field in `save.c`.
3. Initialize a safe default for new characters and old files.
4. Parse it without changing unrelated fields.
5. Clamp or validate values before storing into narrow C types.
6. Test a new character, an existing fixture, save/reload, missing field,
   malformed value, and repeated save.
7. Preserve case-sensitive player filename behavior.
8. Document migration and rollback implications.

Do not use real files under `player/` or `gods/` as test fixtures. Create
sanitized temporary fixtures under `tests/` or a temporary directory.

Player save code also creates version snapshots. Avoid recursive snapshotting,
partial writes, or replacing the live file before a complete temporary file is
ready.

## Area Data Development

Read [Area Building Guide](area-building-guide.md) before editing `.are` files.
Key rules:

- Files are Latin-1 and use `~`-terminated strings.
- The load list is `area/area.lst`; order affects cross-area availability.
- Vnums must be globally unique for each indexed type.
- Positive exit destinations must resolve to a room.
- Resets must reference valid mobs, objects, rooms, containers, and wear slots.
- Shops need a valid keeper; special functions must exist in C.
- One-way exits, isolated rooms, unspawned definitions, and source-less objects
  may be intentional, but findings require review.
- Never modify archived `area/korzath2old.are` or
  `area/savedTrinidad.are` as if they were active content.

Use structured parsers/generators for bulk edits. Do not use global string
replacement across area files without parsing section boundaries.

## Hyrule Generated Content

Source of truth:

```text
data/hyrule_first_quest.json
scripts/build_hyrule_area.py
```

Generated output is loaded as an area file. Normal workflow:

```bash
make hyrule-area
make test-hyrule
python3 check_exits.py
python3 check_resets.py
python3 scripts/area_lint.py --fail-on critical --limit 100
git diff --check
```

`make hyrule-manifest` rebuilds the manifest through the reference extraction
pipeline and is not the default for a small content change. Review manifest and
generated-area diffs together. See [Hyrule: First Quest](hyrule-area.md) for
vnum ranges, progression contracts, map/compass behavior, secrets, and source
provenance.

## Web Dashboard Development

Run from the repository root:

```bash
export WEB_ADMIN_TOKEN=development-only-random-value
python -m webadmin.server --host 127.0.0.1 --port 9001
```

Development rules:

- Keep request bodies typed with Pydantic models.
- Validate and bound queue payloads before writing.
- Keep the command queue line-oriented and compatible with the C consumer.
- Use constant-time token comparison for secrets.
- Clamp list/log/result limits to prevent avoidable resource exhaustion.
- Make parser reload atomic: preserve the last known-good parser on failure.
- Add API tests for success, missing token, wrong token, malformed input,
  boundary limits, filesystem races, and parser failure.
- Document whether a route is public or protected whenever adding one.
- Keep player-list and player-detail routes token-protected.
- Authenticate protected WebSockets in their first message; never put tokens in
  URLs.
- Keep browser assets local and dependency-free unless a dependency is vendored
  with its license and validation coverage.
- Render untrusted area/player strings with DOM `textContent`, not HTML strings.

`webadmin/server.py` owns FastAPI routes, parser snapshots, queue I/O, and
WebSocket bridges. `webadmin/static/index.html`, `app.css`, and `app.js` own the
full dashboard. `client.html`, `client.css`, and `client.js` own the play-first
client at `/client`; `command-sequence.js` supplies their shared bounded,
quote-aware semicolon parser. Both consoles send parsed commands in order and
store the original chain as one history entry. Password input must always
bypass splitting. Both interfaces share the same APIs and bridges.
`scripts/web_server.py` is only a compatibility launcher; do not add a second
server implementation there.

## C Coding Guidance

- Match the surrounding GNU89 style in Make-built source, even though CMake
  validates under C17.
- Keep declarations compatible with both build systems.
- Use `snprintf`, `toc_strlcpy`, and `toc_strlcat` with the actual destination
  size. Avoid new `sprintf`, `strcpy`, or unbounded `strcat` calls.
- Use `UNUSED_PARAM(x)` for intentionally unused parameters.
- Preserve `\n\r` game-client line endings in C output.
- Route player-facing text through `send_to_char()` or `page_to_char()` rather
  than writing raw canonical color tokens to descriptors.
- Check allocation and file/network results where recovery is possible.
- Be explicit when narrowing to `sh_int`, `int16_t`, bit fields, vnums, ports,
  sizes, or timestamps.
- Do not retain pointers to characters/objects across code that can extract,
  kill, move, or free them without revalidation.
- Restore `ch->in_room`, global mode flags, iterators, and temporary state on
  every return path.
- Avoid shell construction for data that can be influenced by a player or web
  request.
- Keep fixes scoped; legacy behavior may be relied upon even when unusual.

## Debugging

### Live Smoke Test

```bash
cd area
timeout 25s ../merc 9999
```

Exit code 124 from `timeout` is expected if the server remained healthy until
the timer. Use a non-production port and isolated player/log data for tests that
can write state.

### Sanitizers

Use the CMake sanitizer build shown earlier. Reproduce with a minimal sequence
and retain the first stack trace. Later crashes may be secondary damage.

### Valgrind

```bash
bash scripts/run_valgrind.sh
```

Inspect the script's current arguments before running it against production
data. Valgrind is slow and should run on an isolated copy.

### Core Bugs To Consider

When reviewing player-facing code, prioritize:

- crashes, hangs, infinite loops, and descriptor corruption
- item/currency duplication or loss
- save/load incompatibility and partial writes
- death/extraction use-after-free paths
- exits, traps, portals, and movement that leave invalid room state
- combat attribution, PK safety, group ownership, and kill stealing
- authorization mistakes in immortal/web operations
- parser/runtime disagreement that deploys invalid world data
- integer overflow in player-controlled counts, distances, prices, or indexes

## Documentation Maintenance

Documentation is part of the feature:

- Update `README.md` only for project-wide entry points and facts.
- Put player behavior in `wiki/player-guide.md` or the command reference.
- Put deployment/configuration in `wiki/hosting-guide.md`.
- Put staff procedures in `wiki/operator-guide.md`.
- Put implementation details here or in focused design notes.
- Update in-game help whenever player syntax or behavior changes.
- Keep examples runnable from the directory stated above them.
- State whether values are defaults, current baselines, or permanent contracts.
- Recalculate world totals after area-list changes.
- Keep security limitations prominent and factual.

Historical format pages in `wiki/` remain useful for provenance but are
superseded by the maintained area guide where they disagree.

## Change And Release Checklist

Before requesting review:

1. Confirm `git status` contains only intended changes.
2. Review the complete diff, including generated files.
3. Run focused tests while developing.
4. Run the full platform validation suite.
5. Check `git diff --check`.
6. Update player, host, operator, developer, security, and in-game help as
   applicable.
7. Document persistence/API/world-format compatibility.
8. Include manual test steps for behavior that automated tests cannot cover.
9. Keep real player/god data and secrets out of the commit.
10. Deploy through a reviewed branch with a verified backup and rollback point.

## Related Documentation

- [Contributing](../CONTRIBUTING.md)
- [Security](../SECURITY.md)
- [Hosting Guide](hosting-guide.md)
- [Operator Guide](operator-guide.md)
- [Area Building Guide](area-building-guide.md)
- [Validation And Area Health](validation-and-area-health.md)
- [Advanced Gear Comparison](gear-comparison.md)
- [Hyrule: First Quest](hyrule-area.md)
