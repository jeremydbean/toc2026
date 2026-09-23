# Agent Instructions For Times of Chaos

These instructions apply to automated coding work in this repository. Use the
source code, tests, and maintained guides as authority. Historical notes and old
wiki format pages are context, not proof of current behavior.

## Project Identity

- Repository: `jeremydbean/toc2026`
- Runtime: legacy single-process C MUD based on Diku/Merc/ROM
- World data: Latin-1 `.are` files loaded from `area/area.lst`
- Dashboard: FastAPI/Uvicorn in `webadmin/`
- Primary Make output: repository-root `merc`
- CMake output: repository-root `bin/rom`
- Game working directory: `area/`
- Default game/dashboard ports: `9000` and `9001`

Maintained documentation:

- `README.md`: project front door and quick starts
- `wiki/player-guide.md`: player progression and systems
- `wiki/player-command-reference.md`: player command map
- `wiki/achievements.md`: achievement catalog, command views, persistence, and hooks
- `wiki/game-client-guide.md`: browser terminal, ANSI, paging, and client controls
- `wiki/hosting-guide.md`: deployment/configuration/persistence
- `wiki/windows-production-hosting.md`: current Hyper-V production operations
- `mudlet/listing-submission.md`: Mudlet listing readiness and review handoff
- `wiki/operator-guide.md`: immortal and incident procedures
- `wiki/developer-guide.md`: architecture and development workflow
- `wiki/area-building-guide.md`: authoritative area format reference
- `wiki/validation-and-area-health.md`: validators and issue codes
- `wiki/hyrule-area.md`: generated Hyrule design and workflow
- `SECURITY.md`: actual security boundaries and hardening
- `CONTRIBUTING.md`: review checklist

## Non-Negotiable Data Safety

- Do not modify anything under `player/` or `gods/` without explicit user
  permission for the exact files and purpose.
- Treat `heroes/`, `backups/`, `.env`, logs, and player snapshots as sensitive.
- Never use a real character file as a test fixture.
- Do not expose or commit password hashes, admin tokens, private logs, IP data,
  or other player information.
- Do not modify archived `area/korzath2old.are` or
  `area/savedTrinidad.are` as active world content.
- Do not silently convert `.are` files to UTF-8. They are Latin-1 and contain
  `~`-terminated strings.
- Do not hand-edit generated Hyrule output for a lasting change. Update
  `data/hyrule_first_quest.json` and/or the generator, regenerate, and test.
- Work with existing uncommitted user changes. Never discard, reset, or rewrite
  unrelated work.

## Start Every Task With Context

1. Read `git status --short --branch`.
2. Inspect relevant code, declarations, tests, help, and documentation before
   deciding on an implementation.
3. Use `rg`/`rg --files` for search.
4. Trace cross-module contracts: command table, declarations, persistence,
   help, area data, parser, API, and tests.
5. Prefer established repository patterns over a new abstraction.
6. Keep scope narrow and preserve unusual behavior unless the task explicitly
   changes it.

Do not stop at a proposed fix when the user asked for implementation. Carry the
change through verification and a clear result.

## Build And Run

Primary Linux/macOS build:

```bash
make clean
make
cd area
../merc --check-area
../merc 9000
```

The Make build uses GNU89 compatibility, `-fcommon`, ROM definitions, and
`libcrypt`/`libm` where applicable.

**Build both trees before believing a change works.** They disagree on more
than warnings:

- The Makefile is `-std=gnu89`; CMake is strict `-std=c17` with
  `CMAKE_C_EXTENSIONS OFF`. POSIX functions visible under one are hidden
  under the other. `inet_aton` and `gethostbyname` compile under Make and
  fail the CMake build outright; `getaddrinfo`, `getnameinfo`, `inet_pton`
  and `inet_ntop` work in both, and are what new code should use. A file
  needing them must define `_DEFAULT_SOURCE` and `_POSIX_C_SOURCE` **before
  any header**, as `src/comm.c` and `src/act_wiz.c` do.
- `merc.h` defines `unix` as a fallback from its own include point, so a
  `#if defined(unix)` above that `#include` behaves differently in each
  build.

**If Make and CMake disagree on runtime behaviour, suspect the build before
the code.** Until 2026-09-18 the Makefile had no header dependency tracking:
its pattern rules depended only on the `.c` file, so editing a header
recompiled nothing. That is not a slow build, it is a silently corrupt one
-- `MAX_INPUT_LENGTH` sizes three arrays inside `DESCRIPTOR_DATA`, so
changing it rebuilt only the touched translation units with the new struct
layout while the rest kept the old, which links cleanly and then reads and
writes past the fields it thinks it is addressing. It is fixed with
`-MMD -MP` and `-include`, but `make clean` is still the safe answer to
anything inexplicable.

CMake:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
cd area
../bin/rom --check-area
```

Sanitizers:

```bash
cmake -S . -B build-sanitize \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_SANITIZERS=ON
cmake --build build-sanitize
```

Supported long-running native wrapper:

```bash
./startup.sh 9000
```

The root compatibility file named `startup` and `area/startup.sh` delegate to
the maintained root `startup.sh`. Files under `zStartup/` are archived history
and must not be used as current launchers.

Docker:

```bash
./install.sh --skip-prerequisites
./toc.sh status
./toc.sh logs
./toc.sh stop
```

Windows uses `install.ps1` and `toc.ps1`. Docker Compose binds both ports to
loopback by default; `--public`/`-Network Public` exposes only the game port.
Compose uses `restart: unless-stopped`, so use the launcher `stop` command when
the container must remain off.

## Validation

Full Linux/macOS/CI suite:

```bash
bash scripts/validate.sh
```

Full Windows PowerShell suite (requires WSL):

```powershell
.\scripts\validate.ps1
.\scripts\validate.ps1 -RunSmoke
```

Focused checks:

```bash
make
cd area && ../merc --check-area && cd ..
python3 check_parser.py
python3 check_exits.py
python3 check_resets.py
python3 check_shops.py
python3 scripts/area_lint.py --fail-on critical --limit 100
python3 -m unittest discover -s tests
python3 -m unittest tests.test_money_safety tests.test_bank_interest tests.test_pkill_persistence tests.test_achievements
git diff --check
```

Current September 2026 Python baseline:

```text
100 listed area entries
2,337 mobiles
3,560 objects
7,781 rooms
0 critical, 12 warning, 1,511 information findings
```

The information count fell from 1,571 when 175 resets that had been
commented out as "(removed: room/obj does not exist)" went back in; every
vnum they named was present all along. See the changelog entry for the
parsing mistake behind the claim.

Six list entries are help/social files without `#AREA`; native boot creates one
online-building area. Do not force native and Python area totals to match by
removing valid files or hiding the generated area.

Run tests proportional to risk. Movement, combat, extraction, persistence,
world loading, command authorization, and queue changes need the full suite plus
manual gameplay checks.

**The full suite takes about 35 minutes, and the maintainer does not want it
run routinely.** Around 109 of its tests each boot a real server that parses
every area file (the generated Hyrule alone is 443 rooms and 1,706 resets),
and `tests/live_mud.py`'s `drain(n)` sleeps its whole window rather than
returning when output arrives -- roughly eight minutes of the total is
waiting for replies that already landed. `tests/test_bank_interest.py` waits
on a randomised 40-80 second game tick.

Default to: build both trees, run the one relevant test module, ship. Write
the regression test and let CI run everything. Reach for the full suite only
when a change is broad enough that collateral damage is a real risk, and say
why. Wrap any live probe in `timeout` -- never poll in a shell loop waiting
for a test to finish.

`tests/test_webadmin_api.py` and `tests/test_web_help_and_paging.py` need
`fastapi` and `httpx`; without them they skip *silently*, including the
admin-auth and host-header-spoofing tests. Install into a virtualenv outside
the repo (`.venv` is not in `.gitignore`).

Live-test gotchas that look like product bugs and are not:

- Character names must be **alphabetic only** and at most 12 characters.
  A digit makes creation fail and the save file never appears.
- `stat room` prints both `Number:` (the area-relative number) and
  `Vnum:`. Only `Vnum:` is what `goto` and `set room` want.
- `parse_login_journal()` returns **file order, oldest first**.
- Guildmaster mob vnums are not room vnums. `goto 4701` goes to a room;
  the Necro Guild Master lives in room 4721.

## Source Ownership Map

- `src/comm.c`: sockets, descriptors, login, main loop, output, and paging
- `src/color.c`: canonical game-color parsing and terminal color conversion
- `src/telnet_proto.c`, `src/gmcp.c`: Telnet negotiation and Mudlet protocol data
- `src/achievements.c`: achievement catalog, progress, display, and persistence helpers
- `src/db.c`: world boot and native area parser
- `src/interp.c`: command registration/order/trust/logging
- `src/act_move.c`: movement, exits, traps, recall, run/speedwalk
- `src/act_info.c`: displays, leveling, remort
- `src/act_obj.c`: objects, equipment, shops, banks, item use
- `src/act_comm.c`: channels and communication
- `src/act_wiz.c`: immortal operations and player restore
- `src/fight.c`: combat, death, flee, ranged attacks
- `src/magic.c`, `src/magic2.c`: spell behavior
- `src/skills.c`: practices, groups, gain, teaching
- `src/gear_compare.c`: advanced equipment comparison
- `src/save.c`: pfile format and player snapshots
- `src/update.c`: ticks, advancement, scheduled archives
- `src/const.c`: class/race/skill/group/title tables
- `webadmin/server.py`: dashboard UI/API/queue/WebSockets
- `webadmin/static/client.*`, `command-sequence.js`: play-first browser
  terminal, client controls, and shared bounded command chaining
- `webadmin/area_parser.py`: independent Python area parser
- `webadmin/static/console-output.js`: streaming ANSI/Telnet console decoder
- `webadmin/area_health.py`: shared lint engine

Commands added or revived in September 2026, and where they live:

- `spellup` / `spellpurge` (`src/act_wiz.c`) place and clear Hermie, mob
  vnum 98 in `limbo.are`, who casts from a menu. There is no speech hook in
  this codebase -- spec_funs run on a pulse and never see player speech --
  so `do_say` in `src/act_comm.c` calls `spellup_listen()` directly.
- `dns` (`src/act_wiz.c`) toggles hostname resolution, lists connected
  descriptors, and resolves one address. It was a stub in `src/stubs.c`.
- `practicelist` (`src/act_info.c`) lists who can practise the skills you
  already know; `gainlist` beside it marks what you already have.
- `alias` / `unalias` live in `src/act_comm.c`; expansion is in
  `src/interp.c` and must not leave a trailing space, or commands that read
  their whole argument (`goto`) fail on it.

## C Change Rules

- Match surrounding GNU89-compatible style even though CMake also compiles as
  C17.
- Add new source files to `CMakeLists.txt`; Make globs `src/*.c`, CMake does not.
- Add declarations in the established header and avoid implicit declarations.
- Use `snprintf`, `toc_strlcpy`, and `toc_strlcat` with the true destination
  size. Do not add `sprintf`, `strcpy`, or unbounded `strcat`.
- Use `UNUSED_PARAM(x)` for intentionally unused parameters.
- Preserve game output line endings (`\n\r`).
- Use `send_to_char()` for immediate player text and `page_to_char()` for
  scrollable output. Both paths convert canonical `{HH}` color tokens; do not
  send raw player-facing color markup through `write_to_buffer()`.
- Test formatted output with color enabled and disabled, and with paging both
  enabled and disabled. Keep normal summary views within the default page size
  when practical.
- Validate player-controlled numbers before conversion, multiplication, loops,
  indexing, allocation, or narrowing.
- Revalidate pointers after calls that can kill, extract, move, or free a
  character/object.
- Restore temporary room pointers, global movement flags, and iterator state on
  every return path.
- Preserve command-table order semantics. Prefix matching can make an earlier
  entry win.
- Password-bearing commands must not be logged.
- Keep persisted enum/flag/slot/vnum values stable unless a migration is part of
  the task.
- Carried denominations, bank copper, and lifetime casino totals are `long`.
  Route gameplay changes through `add_money()` or
  `adjust_coin_balance()`; preflight both source and destination before any
  transfer. Money objects hold an `int` pile size and larger corpse balances
  must be split into representable piles.

## Player-Facing Bug Review

For each changed command or gameplay path, check:

- missing, malformed, negative, zero, huge, and overflow input
- abbreviations and case handling
- unavailable skill/class/guild/race/level
- sleeping/resting/fighting/dead state
- NPC, charmed, switched, grouped, mounted, PK, and immortal variants
- closed/hidden/one-way/self-loop exits and all ten directions
- traps or scripts that kill/extract/move during a command
- target/item disappearance during combat or trigger callbacks
- duplicate/lost items, currency, experience, quest credit, or corpse ownership
- early returns that leave global state or room pointers changed
- save/reload behavior and old player files
- help text and actual behavior agreement
- color enabled/disabled, paging enabled/disabled, and narrow terminal layout

Do not label deliberate random recall as a bug. It can choose any room that is
eligible and not protected. Some areas, including Hyrule, intentionally disable
recall and provide explicit return paths.

## Area Work

The authoritative reference is `wiki/area-building-guide.md`.

- Parse sections structurally; do not use unbounded global text replacement.
- Keep vnums globally unique within each indexed type.
- Ensure positive exit targets exist.
- Validate reset context and references.
- Review one-way exits, disconnected groups, unspawned definitions, source-less
  objects, traps, teleports, portals, pet storage, and restricted rooms.
- Add active files to `area/area.lst` in the intended load order.
- Run native and Python validation after every area change.
- Explain intentional warning/info findings with evidence instead of adding a
  silent allowlist.

Hyrule workflow:

```bash
make hyrule-area
make test-hyrule
python3 check_exits.py
python3 check_resets.py
python3 scripts/area_lint.py --fail-on critical --limit 100
```

## Dashboard Work

- The C server is authoritative. Dashboard parser reload is dashboard-only.
- Protected routes use `WEB_ADMIN_TOKEN` in `X-Admin-Token`; an unset token
  disables them with 503.
- Protected WebSockets use an authenticated local cookie or a first JSON auth
  message. Never place the token in a WebSocket URL or query parameter.
- Player list/detail, logs, structured events, backups, and operational status
  are protected. World data, health, configuration flags, gear analysis, and
  the browser-to-game `/ws` bridge are public at the app layer. Do not claim
  the token protects the entire dashboard.
- `/api/admin/status` may expose queue depth and file metadata, but never queue
  payloads, player-file contents, tokens, or log messages.
- Treat queue writing as immortal command execution.
- Bound payloads and result limits; reject newlines/control data that can split
  queue records.
- Preserve the last known-good parser when reload validation fails.
- Keep semicolon command parsing shared across both browser consoles. Preserve
  quoted and escaped semicolons, cap batches, store one history entry, and
  never split password input.
- Add tests for no/wrong/correct token, malformed bodies, boundaries,
  filesystem races, and failed parser reload.
- Document authentication status for every new route.

## Security Facts

- Game transport is plain Telnet.
- Supported player password files use traditional DES `crypt` hashes.
- Only the first eight password bytes are effective.
- Player files and backups must be treated as exposed credentials if stolen.
- The dashboard should be loopback/private even with a token.
- Do not provide offensive password-cracking automation from repository data.
  Defensive verification must use explicit authorization and sanitized inputs.

See `SECURITY.md` for mitigation and reporting procedures.

## Documentation Rules

- Keep `README.md` concise and route detail to focused guides.
- Update in-game help for player-visible syntax/behavior.
- Make commands runnable from the directory stated above them.
- Separate defaults, current measured baselines, and design guarantees.
- Recalculate world totals after `area.lst` or generated-world changes.
- Preserve historical format pages, but mark the modern area guide as
  authoritative.
- Correct stale instructions when source behavior changes.
- Distinguish source availability, verified deployment, submission, and listing
  acceptance. A GitHub commit alone does not establish any of the latter three.
- Never deploy a Git checkout over live player directories. Preserve runtime
  state, graceful saves (including link-dead players), and watchdog heartbeats.
- Use ASCII for new documentation unless an existing file requires otherwise.

## Git And Delivery

- Inspect status and diffs before editing and before final delivery.
- Never reset, discard, or overwrite unrelated user changes.
- Keep generated source/output changes together.
- Run `git diff --check`.
- Do not stage, commit, push, merge, or open a pull request unless the user has
  explicitly authorized that action for the current task.
- When publishing is authorized, use a focused branch/review flow and report the
  exact validation result.

## Deploying To The Raspberry Pi

The Pi at `toc.jeremybean.com` is the live server, not a staging box. Real
players log in; check `log/logins.tsv` for who has been on lately.

**The updater restarts the game, which disconnects whoever is playing.**
Before triggering `toc2026-update.service`, check for connected players and
hold unless the only one online is the owner (Killuminati). Two signals are
needed and neither is sufficient alone: established sockets on port 9000 say
how many people are really connected, and the login journal says who -- a
session ending without a recorded close leaves a stale `connect`, so the
journal over-reports on its own.

The updater does `make clean` first, so production has never been exposed to
the incremental-build trap described under Build And Run.

Other deploy facts:

- Never run the Pi installer or updater against the Windows VM; that host is
  a test environment only.
- Never copy player files, logs, PK standings, max-load state, shutdown
  markers, or queued commands from Git into production.
- `MUD_HOST` is where the web service dials (loopback). `MUD_PUBLIC_HOST` is
  what the dashboard displays, resolved to an address so it follows the DDNS
  record rather than going stale.

## Permission Helpers

Two helpers exist so a rule is stated once. Prefer them to open-coding a
comparison:

- `get_trust(ch)` -- **never read `ch->trust` directly.** The field is 0
  unless somebody explicitly assigned a trust, which is the normal state, so
  a raw comparison refuses everybody including implementors. Nine gates had
  this bug.
- `rank_protects(ch, victim)` -- whether rank stops `ch` acting on `victim`.
  Implementors are exempt, because `get_trust(victim) >= get_trust(ch)` reads
  `70 >= 70` at MAX_LEVEL and locked implementors out of twenty-two commands
  aimed at exactly their peers. Commands that should not target the user
  keep their own `victim == ch` guard; rank is a separate question.
- `is_loopback_ip(ip)` -- one place that knows what 127/8 means, used to
  keep the healthcheck's two-minute probe out of the log and to decide
  whether a PROXY header may be trusted.

## Completion Standard

A task is complete only when the requested behavior or documentation is
implemented, relevant tests pass, the diff is reviewed, and any limitation or
unrun test is reported. Do not leave required long-running test/server sessions
unattended at final response.
