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
0 critical, 12 warning, 1,510 information findings
```

The information count fell from 1,571 when 176 resets that had been
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

`tests/test_webadmin_api.py`, `tests/test_web_help_and_paging.py` and
`tests/test_players_online.py` need `fastapi` and `httpx`; without them they
skip, and until 2026-09-24 two of them skipped *silently*, taking the
admin-auth and host-header-spoofing tests with them. Install into a virtualenv
outside the repo (`.venv` is not in `.gitignore`); this machine uses
`C:\Users\JeremyBean\toc-venv`. A new test module that imports
`webadmin.server` must guard the import and skip with a reason, the way those
three do, or it errors instead of skipping wherever the dependency is absent.

**A failure count is not a problem count.** CI was red for four days
reporting "203 failures", which was five problems: one asserted inside a
`subTest` looping over all 443 Hyrule rooms, so a single wrong expectation
printed itself 197 times and buried the rest. Before believing a large
number, group the failures by test name. And prefer one set comparison to a
subTest per item when the collection is large -- the same assertion rewritten
that way now prints one readable line.

Four of those five guarded code that had been deliberately refactored into a
shared helper and went on asserting at the old address. When a
source-inspection test fails after a refactor, check whether the behaviour
moved before changing the test, and repoint the assertion at where it lives
now -- never weaken it so it passes.

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
- `tools/build_directions.py`: builds `webadmin/directions.json`, the travel
  routes both the dashboard and the player client display
- `tools/costs_to_copper.py`: the one-pass area converter kept for reference
- `tools/reprice_by_level.py`: prices objects against what the character who
  can use them earns; re-runnable, and a fixed point on the committed files

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
- **`fread_char` dispatches on the first letter of the key.** A new
  persisted field's `KEY(...)` has to sit in the `case` for that letter or
  it is never matched, and the loader then desyncs on the value: two keys
  added beside a related field in `case 'Q'` instead of `case 'R'` made
  every affected character hang the game at the login prompt. Use
  `fread_long` for a `long` field, not `fread_number`.
- Keep persisted enum/flag/slot/vnum values stable unless a migration is part of
  the task.
- Prices are counted in copper. `obj->cost` is copper and is `long`; shop
  and appraisal output goes through `format_price()`, which writes the
  non-zero denominations short (`5g 20s`, `1c`, or `free`). Do not print a
  bare number as a price.
- **A price is worth a number of kills, and the number is about forty.**
  `load_mobiles` rolls a mobile's coin from its level in six steps, and the
  steps are cliffs: a level 4 mobile carries one to eight copper, a level 5
  one about five silver, a level 10 one about five gold, a level 50 one
  about thirteen platinum. From level 10 up the world's prices sit against
  that correctly. Below it they did not -- a turkey burger in Mud School
  cost ten gold, sixty-six thousand level 1 kills -- and
  `tools/reprice_by_level.py` rescaled them. Price new low-level content
  in copper and silver, and run that tool: `tests/test_shop_prices.py`
  asserts it has nothing left to change. `add_money()` and `has_enough_gold()` still take
  **gold**, so a cost computed in gold -- REPAIR's, for one -- must be
  multiplied by `COPPER_PER_GOLD` before `format_price` sees it, and clamped
  first so the multiply cannot overflow a 32-bit `long`.
- Carried denominations, bank copper, and lifetime casino totals are `long`.
  Route gameplay changes through `add_money()` (gold) or
  `spend_copper()`/`gain_copper()` (copper); preflight both source and
  destination before any transfer. **`adjust_coin_balance()` moves one
  pile, not the purse** -- it is right for picking up a specific coin and
  wrong for charging a price. Charging with it meant a character holding
  two and a half million platinum could not buy a twenty-two silver loaf,
  because the check read `ch->new_copper` alone. Use `has_enough_copper()`
  to ask, and `query_carry_copper()` rather than `query_carry_coins()` to
  weigh a payment, which otherwise weighs it as its own value in single
  coppers. Money objects hold an `int` pile size and larger corpse balances
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
eligible and not protected.

Hyrule no longer blocks recall everywhere. It used to: every room carried
`ROOM_NO_RECALL` and nothing in the world exited into it, so it was a place
staff could visit and nobody could leave. Since the arcade cabinet was built,
only the dungeons keep the flag -- vnums 30400 to 30645, the contiguous run
named "Level N: ..." -- because walking out of Level 7 by saying a word is the
opposite of what a dungeon is for. The other 197 rooms let you recall away, and
`tests/test_hyrule_progression.py` asserts exactly that split. The overworld
carries `ROOM2_ALWAYS_LIT` (flags2 `B`, formerly `ROOM2_B_UNUSED`) because
field, forest, hills, mountain and desert are sectors `room_is_dark` blacks out
at sunset.

## Area Work

The authoritative reference is `wiki/area-building-guide.md`.

**An `.are` file is a token stream, not lines.** `fread_letter`,
`fread_number`, `fread_word` and `fread_string` all skip whitespace, including
newlines, so the game does not care where a builder broke a line. Anything
that reads area files with regexes has to be equally relaxed, and every one of
these shapes is real and load-bearing in the shipped world:

- `D0` and `D 0` both mean exit zero. 2,275 exits are written the spaced way.
- An exit's description may start on the same line as its number:
  `D3 too dark to tell`.
- A record header may carry trailing whitespace (`#114 `), or its name on the
  same line (`#24377 The White Queen's Chamber~`).
- `fread_flag` never handles a minus sign: given `-1` it returns 0 and ungets
  the `-` without consuming it, shifting everything after it.

Each of those silently dropped content from `tools/build_directions.py` at
some point, and the dropped content was then acted on: 176 resets across
`chess.are`, `korzath1.are` and `world.are` had been commented out as
"(removed: room/obj does not exist)" when every vnum they named was present
and every room reachable. If a validator says something is missing, confirm
against `../merc --check-area` and `check_exits.py` before deleting anything.

Before restoring a reset that was commented out, read what it does. One of
those 176 was a button whose `value[4] == 3` kills everyone in the room except
whoever pushes it; arming that is a gameplay decision, not a repair.

- **A record ends where the game says it ends, not at the next `#`.** An
  object's affects, extra descriptions and actions follow its condition
  letter, and one of Hyrule's dungeon maps carries an ASCII floor plan in
  an extra description whose rows begin with a hash.
  `tools/costs_to_copper.py` scanned for the next `\n#`, landed inside that
  map and stopped -- leaving the last 85 objects in the world priced in
  gold after everything else had moved to copper, so a Magical Shield
  advertised at 130 rupees sold for one silver thirty. Read the trailing
  `A`/`E`/`T` records the way `load_objects` does.
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

**Check that the generator still reproduces the file before regenerating.**
It had drifted: 197 rooms in `area/hyrule.are` carried recall and always-lit
flags that had been applied to the generated output by hand, and
`scripts/build_hyrule_area.py` knew nothing about them, so the next
`make hyrule-area` would have put `ROOM_NO_RECALL` back on the whole area
and taken `tests/test_hyrule_progression.py` down with it. The rule now
lives in `room_flag_word()`. `area/hyrule.are` is also the one area file
committed with CRLF line endings; the generator writes LF, so a
regeneration rewrites every line of it.

Hyrule prices itself in rupees and says so in the object descriptions. A
rupee is a gold coin -- the rupee piles are `ITEM_MONEY` with `value[1]`
set to `TYPE_GOLD` -- so the generator writes `cost * COPPER_PER_GOLD`.
`tools/reprice_by_level.py` skips the file for both reasons: it is
generated, and its prices are already calibrated against its own drops.

Hyrule workflow:

```bash
make hyrule-area
make test-hyrule
python3 check_exits.py
python3 check_resets.py
python3 scripts/area_lint.py --fail-on critical --limit 100
```

## Directions And Reachability

`tools/build_directions.py` walks the world from the Oak Tree Square (room
2401) and writes `webadmin/directions.json`. Both the dashboard's Directions
view and the client's Routes panel read it through the public
`/api/directions`. Regenerate with `python3 tools/build_directions.py` after
any change to exits, portals or `area.lst`, and commit the JSON with the
change that caused it.

What counts as a way through, because it is more than exits:

- `ITEM_PORTAL` (30) objects, entered.
- `ITEM_MANIPULATION` (31) objects -- climbed, jumped, crawled, pushed,
  pulled, turned, burned, bombed, played to or fed. `value[0]` is the verb,
  `value[1]` the room, and `value[4] == 9` means it acts on the room it sits
  in and leads nowhere. 95 of them are in play and they are the only way into
  Dylan's front gate, the Lonely Mountain and the Mid-World treehouse.
- Rooms flagged `ROOM_TELEPORT` or `ROOM_RIVER`, which carry you on a timer.
  The three numbers after the sector are destination, speed and visibility.

Two rules keep the output honest, and both were learned the hard way:

- **Price the edges.** Routing is Dijkstra, not breadth-first. A door, a
  portal or a rope costs one; a room that carries you costs eight, because
  you wait on its timer and cannot steer. Unweighted, the Newbie Train --
  eleven stops at five ticks each -- beat walking, and 29 routes told players
  to stand still instead of walk.
- **A room that teleports you to the recall point is an ejector, not a
  passage.** Six exist. The House of Pancakes (1607, in `wyvern.are`) says the
  ceiling crushed you, prints a fake `<1hp 0m 0mv>` prompt and drops you on
  the Temple altar; six decoy objects in the Oak Tree Square lead to it. It is
  a joke, and because it lives in `wyvern.are` the published route to Wyvern's
  Tower was once the single command `crawl hole`. Ejectors are excluded from
  routing, though `load_world()` still reports them, because the parity test
  against the dashboard parser depends on that staying faithful.

89 of the 92 areas holding rooms have a route. Dresden has none because it
contains the start room. The Quest Zone (20301-20313) and Temple Despair
(26000-26006) have none because nothing in the world links to them -- the
first is finished content with no entrance, the second an empty shell with no
mobs or objects. Do not invent entrances for them; ask.

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
- **Bump the `?v=` on any file you edit under `webadmin/static/`.** Both pages
  load their assets with a cache-busting query, and editing the file without
  changing the number ships nothing: the browser keeps what it has. This bit
  three separate times in one session -- a rewritten Routes panel nobody could
  see, a stylesheet fix that did not apply, and a script that still expected a
  filter element that had been removed. The last kind is worse than stale, it
  is broken.

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
hold unless the only one online is the owner (Killuminati).

Ask the game, not the journal. `telnet_count_players()` counts descriptors
in `CON_PLAYING` and the game publishes that over MSSP, which is what
`/api/admin/status` now reports as `online.count`, with
`online.source == "game"`. A session ending without a recorded close leaves
a stale `connect` in `log/logins.tsv`, so the journal only ever
over-reports; when the game cannot be reached the field says
`source == "journal"` and the number is an upper bound, not a reading. The
names still come from the journal, because MSSP carries a count and no
names. Established sockets on port 9000 are a third, independent check.

The Pi answers SSH on the LAN as `toc@toc.local` (port 22 is deliberately
not forwarded from the internet). Over SSH the updater can be triggered
without the admin token by touching `/run/toc2026/update.request`, which
is the same path `POST /api/update` writes and is owned by `toc`.

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
- The admin token lives in `/home/toc/toc2026/.env` (gitignored, mode 600) and
  is read with `grep '^WEB_ADMIN_TOKEN=' ~/toc2026/.env`. It was rotated on
  2026-09-23 after being pasted into a chat transcript; generate a
  replacement on the Pi with `openssl rand -hex 32` so the value never leaves
  the host, and restart `toc2026-web.service`. Never paste it into a commit,
  an issue or a conversation.

## Scattering Things Into The World

`random_scatter_room()` in `src/db.c` is how anything picks a room to put
something in, optionally inside one area. **Do not guess a vnum.** The
component scatterer did -- `get_room_index(number_range(0, 65535))` in a
loop that gave up after a hundred tries -- and with 7,781 rooms spread
over 65,536 vnums the inner loop failed about nine times in ten, so herbs
and spell components had barely existed for years while the command that
placed them reported success.

Component rates live in `component_update()`: `HERB_CEILING` and
`COMPONENT_CEILING` in `merc.h`, and `telnet_count_players() < 1` stops
the world filling up while it is empty.

## Monster Wards

`dshield` and `baura` are in the skill table but belong to mobiles: level
72 for every class, above MAX_LEVEL, so nothing can learn, practise or
gain them. They stay in the table because it is also the affect registry
-- the type, the duration and the wear-off message all live there.
`spec_dominion_ward` in `src/special.c` is what casts them, and any
builder can put it on a mobile.

**An immunity granted by an affect goes on the affect,** through
`APPLY_IMMUNITY`, so `affect_remove` lifts it. `iron skin` is the model.
These two used to set `imm_flags` from a sweep in `update.c` that ran when
any unrelated affect expired and tested "still affected" rather than "no
longer affected" -- it would have stripped the immunity while the ward was
standing, had anything ever granted one.

`set skill <char> all` skips abilities no class can reach, which is what
kept these two out of players' skill lists.

## Where RECALL Goes

`recall_room(ch)` in `src/act_move.c` is the one place that answers it.
`ch->pcdata->recall_vnum` holds a player's chosen room, or 0 for the
Temple, and the stored vnum is rechecked on every use rather than trusted
from the player file -- an area edit can take the room away or make it
no-recall under a saved character, and the honest answer then is the
Temple. `room_allows_recall_point()` is the test for whether a room may be
chosen, and it is deliberately the same test recall applies on the way
out. `spell_word_of_recall` goes through the same helper, so the spell and
the skill cannot disagree.

Moving the point waits `RECALL_MOVE_COOLDOWN`, and `RECALL DEFAULT` is
exempt on purpose: a character who cannot reach their own recall point has
no other way to reset it. Recall itself is not rate-limited -- the point
of the feature is a standing shortcut to one room.

**Only the skill uses the chosen point, and only the skill is stopped by a
curse.** `recall_travel()` takes an `own_prayer` flag for exactly these two
differences; `recall_char_to_temple()` is the door for everything else --
the Recall Ring in `handler.c`, the link-dead rescue in `fight.c`, the
drunk who announces he is leaving in `update.c` -- and
`spell_word_of_recall` keeps its own copy of the same rules. A scroll or
potion of recall is that spell, so it inherits them. The result is a
second way home that does not move and still answers when the gods will
not hear you, which is the whole reason to carry one. `ROOM_NO_RECALL`
blocks all of it: that flag is how an area keeps you inside, and it is a
property of the place rather than the traveller. A new way of sending a
character home goes through `recall_char_to_temple()`, not `do_recall`.

## Reading An Offline Character

`do_finger` and `do_mirror` in `src/act_wiz.c` both read a player file
directly rather than going through `load_char_obj`, which would drag in
room placement, pets and mail. The format is line-oriented for this
purpose: `#O` opens an object, `Vnum`, `Nest` and `Wear` are always
written, and nest zero with a wear location is something the character had
on when they saved. Anything new that needs to look at an offline
character should follow that rather than loading them.

MIRROR forces the kit on: the three `ITEM_ANTI_*` flags are cleared on
each copy, so an item that would zap itself off the immortal goes on
anyway, and both equip loops run from `MAX_WEAR - 1` downwards so a
two-handed weapon does not knock the shield back off. `ITEM_ACTION` is
the one exception and stays off, because `equip_char` fires those and one
of them kills you.

`mirror restore` puts the borrowed kit in a pack and the immortal's own
gear back on. What came off is remembered in `pcdata->mirror_worn` as
**vnums, not pointers** -- an object can be dropped, sacrificed or purged
between the two commands, and a stale pointer to one is a crash where a
stale vnum is merely a piece that does not come back. Neither field is
saved; a relog ends the mirror. The pack is filled before the immortal's
own kit goes back on, and `mirror_find_carried` only considers items at
`WEAR_NONE`, so a mirrored copy of something the immortal owns one of too
cannot be picked up in place of the original.

## Staff Invulnerability

`is_invulnerable(ch)` is the one test, and it is only true for an
immortal, so a demotion takes the protection away without anyone
remembering to unset the bit. `damage()` honours it in three places: an
early return for `PLR_INVULN_ABSORB`, the `damage_eq` call, and the
subtraction from hit points. Leaving the subtraction as the chokepoint is
deliberate -- everything above it, `dam_message` included, still runs, so
the default reading of a blow is the ordinary one and only the loss is
skipped. Nothing displays the flag: not `score`, not the room. That is a
deliberate difference from WIZINVIS and CLOAK.

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
