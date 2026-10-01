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

That 35 minutes is a local figure. The same suite on a GitHub runner
takes **51 to 61 minutes** -- ten consecutive runs measured, successes
and failures alike -- so a `validate` job still going at fifty minutes
is on schedule rather than hung. Check the job's step list before
concluding anything is stuck.

`scripts/test-parallel.sh` runs the modules across every core instead of
one at a time, which takes the same suite from about 87 minutes to about
eight. Nothing in the fixtures needed changing to allow it: every
`LiveMud` already picks a free port and its own throwaway copy of
`area/`, so the modules were simply never run at the same time. It
reprints the failures together at the end rather than leaving them buried
in the interleaving, and exits non-zero if any module failed.

```bash
scripts/test-parallel.sh                  # everything
scripts/test-parallel.sh test_stash       # just these
JOBS=4 scripts/test-parallel.sh           # gentler on the machine
```

**It runs from the repository root, and that is load bearing.** A third
of the modules reach for `src/`, `area/` or `import webadmin` relative to
the root; `python -m` puts the working directory on `sys.path` and
`discover -s tests` adds `tests/` so `import live_mud` still resolves.
Running from inside `tests/` -- which is the obvious way to write it --
fails eleven modules with import and file-not-found errors that look
like product bugs and are not.

**`test_live_gameplay` runs on its own, after the rest.** Its
login-throttle tests measure against the wall clock, so a dozen
servers competing for the same cores make them miss a window and time
out waiting for "wrong password". `SERIAL` in the runner names the
modules that get the machine to themselves; add to it only for a real
timing dependency, not to quiet a flake with a cause.

**`LiveMud.drain(seconds)` sleeps its whole window on purpose.** Making
it return early when the game goes quiet is the obvious speedup and it
was tried in 2026-09: `test_recall_point` then failed with an `affect`
reply that arrived as an empty string, because output comes in bursts
with gaps in them and a drain that stops at the first gap returns before
the reply. The parallel runner gets the same time back without touching
the helper, so leave it alone.

CI runs the same script, so it gets the same speedup, plus three
things that only matter there:

- **Superseded runs are cancelled** (`concurrency` with
  `cancel-in-progress`). Three commits in ten minutes used to mean
  three full runs and one useful answer.
- **ccache**, because `validate.sh` opens with `make clean` on
  purpose -- stale objects have bitten this codebase before -- and the
  cache is what stops that costing a full rebuild every time. The
  Makefile's `CC` is `?=` so the workflow can point it at ccache;
  making it `:=` again silently disables this.
- **One C build, not two.** It used to build with the default warning
  flags and then again with the strict set. The strict set is the
  default plus more and neither uses `-Werror`, so the second build
  only ever printed warnings -- which one build prints just as well.

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
- **`Levl=70` in a fixture makes an immortal, and aggressives ignore
  immortals.** A test that patches a character to level 70 and drops
  them somewhere dangerous is quiet; the same fixture at a mortal level
  is in combat before the first command is typed, and the reply the
  test asserts on arrives buried in combat rounds. Put a mortal fixture
  somewhere safe -- the Temple is 4207 -- set up what you need, then
  `goto` the dangerous room. It is also the better test: whatever you
  are proving is then standing before the first blow instead of racing
  it. A live test that passes in ~57s and fails in ~30s is usually
  failing its first assertion, not behaving differently.

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
- A word that is **exactly** a social's name is that social, even when
  it is the start of a longer command: `interpret()` drops a prefix
  command match for an exact social. POKE was unusable for years as an
  abbreviation of POKER. `tests/test_social_lookup.py` lists every
  social a longer command would otherwise hide.
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

It also writes **`area/routelist.are`**, the `HELP WALKTO` topic
naming every area with a route and how far out it is. That file is
generated: edit the generator, not the help, and `area.lst` must keep
listing it or the topic quietly disappears.
`tests/test_directions_router.py` asserts the generator reproduces it
byte for byte.

The JSON also carries a `links` array: every one of those ways through
as a `{from, command, to}` edge. That is what the Mudlet mapper needs --
it builds its graph from directional exits alone, so without them the
Hyrule rooms sit on the map with nothing joining them to the world and a
click answers "cannot find a path using known exits". Teleport rooms are
deliberately not in it: they carry you on a timer with no command to
send, so there is nothing a client could walk.

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
- Player list/detail, logs, channel history (`/api/channels`), structured
  events, backups, and operational status are protected. World data, health, configuration flags, gear analysis, and
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

## Live State Goes To GitHub

`deploy/windows-vm/toc-state-sync` runs **every five minutes** on
whichever host is running the game and commits `player/`, `gods/`,
`log/` and the `area/` runtime files to `main` **in plaintext**. It
commits nothing when nothing changed.

The interval was widened twice while chasing CI noise and put back
both times. Frequent syncing is what protects the characters; a
validate per sync is a separate problem with a separate fix, below.
Do not reach for the interval again.

**A sync must never start a CI run.** Every one used to, which is an
hour and a half of runner time to be told no code changed, three times
an hour. Two guards: `paths-ignore` in `.github/workflows/validate.yml`
for the paths the sync owns, and `[skip ci]` in the commit message.
Keep both -- a path added to the sync and forgotten in `paths-ignore`
is caught by the second.

This is the owner's decision, taken with the consequences understood:
the files carry DES password hashes and player addresses, the
repository is public, and the transport was never private. It is a test
environment and he would rather lose the secrecy than the characters --
the Pi died with no warning on 2026-09-29 and its saves survived only
because the card happened to be readable. Publishing them also means
somebody cloning the repo to run the game gets a populated world. Do
not re-encrypt this, move it to a private mirror, or narrow what it
covers. `toc-player-backup` is the separate, encrypted, six-hourly
snapshot to a private repo and remains its own thing.

Everything it commits is in `.gitignore`, so every `git add` is `-f`.
That is deliberate, not a bug to tidy up.

**Its file list must name what the game actually writes.** Until
2026-10-01 seven entries lacked their `.txt` -- `area/pkilldata` for
`area/pkilldata.txt` -- and the copy loop skips a missing path without
a word, so PK standings, the wizlist, max-load state and the ban list
had reached no backup since the initial commit.
`tests/test_training_dummy.py` checks every entry against a file git
tracks or the source writes. `toc-deploy` does **not** install this
script; after changing it, install it on the VM by hand:
`sudo install -m 0755 /srv/toc/build/deploy/windows-vm/toc-state-sync /usr/local/sbin/`.

**Tracking `log/` gave the old Pi trap a new route.** Running
`--check-area` from the repository's own `area/` writes `log/toc.log`,
which is tracked, so a working tree goes dirty every time somebody
validates the world -- check `git status` before committing and
`git checkout -- log/toc.log` if it did. Worse, merc's banner ends in
a space, so an unfiltered `git diff --check` then fails on output the
validation itself caused; `scripts/validate.sh` excludes `log/` from
that check for exactly that reason, and the exclusion must stay. The same command run from
`build/area` makes merc write `build/log/toc.log`,
which is now a tracked file, so `git merge --ff-only` in the build tree
refuses and every later deploy fails. `toc-deploy` discards and
`reset --hard`s the build tree instead of merging, which is correct
there because it holds no local work. Anything else that keeps a second
checkout has to do the same.

It works in a clone of its own at `/srv/toc/state-repo`. The deployed
tree must not become a git repository -- installs rsync over it. Before
committing it does `fetch` then `reset --hard origin/main`, and on a
rejected push it rebases and retries, because a developer pushes to the
same branch.

**This changes the rule about committing files the game writes.** On
the Pi that was forbidden outright: its updater advanced the checkout
with `git merge --ff-only`, and a tracked file the game rewrites makes
that merge refuse, breaking every later deploy. The VM does not have
that problem -- its build tree at `/srv/toc/build` holds no live state,
and the state clone is not what gets deployed. Keep the two separate
and the trap stays shut.

**Two halves, and the second is the one people skip.**
`deploy/toc-restore` rebuilds a working game from the public repository
alone -- no archive to find, no key to have kept -- and takes
`TOC_PREFIX` so it can be rehearsed into a scratch directory without
touching anything live. Rehearse it when you change what the sync
covers; an untested restore is a hope.

`toc-state-sync-check` runs every fifteen minutes and makes a stalled
sync loud: journal at `daemon.err`, a marker at
`/run/toc-state-sync.status`, and an in-game announcement, because the
way backups fail is quietly.

**`AUTOSAVE_CYCLE_TICKS` is the other half of the five-minute
promise.** Syncing every five minutes is pointless if the game only
writes a character's file every thirty, which is what stock ROM did.
`char_update` saves each playing character once per cycle, staggered by
descriptor so a full mud does not write every file in one tick.

## Where This Actually Runs

**The game runs in the Hyper-V VM `TOC-Production` on the Windows
desktop.** The Raspberry Pi died on 2026-09-29 -- abruptly, with the
game answering health checks fifteen minutes earlier and no
under-voltage, storage error or clean shutdown in its journal -- and it
is not coming back. Its characters were recovered from the SD card and
are what the VM now serves.

    ssh -i C:\ProgramData\ToC\secrets\toc-admin tocadmin@172.28.90.2
    sudo /usr/local/sbin/toc-deploy          # fetch, build, check, restart
    sudo /usr/local/sbin/toc-deploy --dry-run

`wiki/disaster-recovery.md` is the one page to read when something is
broken: what is down, how to deploy, whether the backups are working,
and how to rebuild on a new machine. Everything on it has been run at
least once.

**Deploy whenever the change is ready, connected players or not.** The
owner settled this on 2026-09-29: do not hold, do not ask, and do not
wait for an empty mud. By the time the stop is reached the update has
already been fetched, built and validated, and holding a validated
update until nobody is on is the worse failure -- the Pi's updater
waited up to fifteen minutes and then went ahead regardless, which is
the same answer taken slowly.

What is owed to whoever is connected is a **warning and a save**, in
that order, and `toc-deploy` does both before `systemctl stop`: an
announce, then `command|fsave` through the webadmin queue, which is
`do_forcesave` and writes every playing character, then a second
announce. The game saves on a clean shutdown as well; the explicit
save is the belt to that pair of braces, because a session's progress
is not something to lose to a restart nobody expected. The queue is
polled rather than read on write, so each step needs a moment before
the next one is worth sending.

Because the install step runs before the restart in the same run, a
change to `toc-deploy` itself takes effect on the *next* deploy, not
the one carrying it.

`toc-deploy` exists because doing this by hand is how `area/custom.are`
went missing: it is tracked in git *and* listed in `area.lst`, so
treating it as a runtime file and excluding it left the game unable to
boot. The script carries the exclude list that is actually correct.

The section below describes the Pi. **It is history**, kept because the
appliance scripts are still in the tree and because the reasoning
behind the update gate is worth keeping. Nothing in it is a live
instruction: there is no `toc.local` to reach and no
`/run/toc2026/update.request` to touch.

## Deploying To The Raspberry Pi (historical)

The Pi at `toc.jeremybean.com` was the live server, not a staging box. Real
players logged in; `log/logins.tsv` recorded who had been on lately.

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

**The updater now checks for players itself, immediately before the
restart.** Check before triggering as well, but understand what that
check is and is not worth: everything between the trigger and the
restart -- fetch, `make clean`, a full rebuild, the world check and the
Python suite -- takes about four minutes, and a reading taken before all
that is stale by exactly the window that matters. Somebody logged in
during a build and was disconnected by a check that had already said the
game was empty. The gate lives in `deploy/toc2026-update`:

- It holds while anyone who is not in `TOC_UPDATE_OWNERS` (default
  `Killuminati`) is connected, polling every 30s up to
  `TOC_UPDATE_HOLD_SECONDS` (default 900), then goes ahead anyway --
  the update is already built and validated by that point, and holding
  a validated update forever is the worse failure.
- The count is the game's own MSSP reading and the names come from the
  login journal, which only ever over-reports. A count higher than the
  owners it can name holds: it waits too often rather than too rarely.
- If the API cannot be read it falls back to established sockets on
  port 9000, so an unhealthy dashboard does not hold every deploy for a
  quarter of an hour.
- It queues an `announce` before the stop, so whoever is on gets told.

**The gate does not protect the owner**, by design -- an owner alone is
not a reason to hold. If you are deploying while the owner is testing,
say so first; the check will not do it for you.

Because `install-pi.sh --refresh` runs before the restart in the same
run, a change to the updater takes effect on the *next* deploy, not the
one carrying it.

**Never commit a change to a file the running game writes.** The
updater advances the checkout with `git merge --ff-only`, and the game
rewrites several tracked paths continuously, so on the Pi they are
always dirty. A commit that touches one of them does not merely lose
the live copy -- the merge refuses outright and **every later deploy
fails** until somebody fixes the tree by hand. The `dirty_paths`
allowlist earlier in the script does not help: it decides whether to
start, while the refusal comes from the merge itself.

The paths that behave this way are the ones that allowlist names:
`area/custom.are` and, under `area/`, `shutdown`, `ban`, `maxload`,
`wizlist`, `offense`, `relics`, `not` and `pkilldata`. `bugs`, `ideas`,
`typos` and `notes` were among them until 2026-09-26 and are now
untracked and gitignored, which is the right shape for all of these:
runtime state does not belong in the repository. Untracking one is
itself such a commit, so it needs the same care -- back the live copies
up, restore the tracked versions so the paths are clean, let the merge
remove them, then put the live content back.

## Watching A Player

`log <name>` sets `PLR_LOG`, and what it records is the point of the
feature: somebody is watching that character because of a suspected bug
or a suspected cheat.

Two things it used to get wrong, both found by reading the first
session anyone captured. All ten directions are `LOG_NEVER`, so every
step wrote a line with nothing after the colon -- **82 of 296 lines**.
And an unrecognised command was not logged at all, because the write
sat inside `if ( found )`, although a command the game refused is
exactly what a cheat hunt wants to see.

`LOG_NEVER` was doing two unrelated jobs: *too noisy for the global
log* (movement) and *must never be written down* (`password`,
`resetpwd`, `delete`). Only the second is a rule, and reading both off
the one flag was itself the second bug: `command_hides_arguments()` in
`interp.c` now holds the secrecy list -- `password`, `resetpwd`,
`delete`, `delet`, and `remort`, whose syntax is
`remort <password> <class> <guild> <race>` -- while `LOG_NEVER` goes
on meaning only "keep it out of the global log". Before that split,
every step a watched character took logged
`south (arguments withheld)`, claiming something was hidden where
there was nothing to hide and burying the handful of lines where
something really was: 800-odd of them in one session. The watched
write also has to happen **before** `logline` is blanked, or movement
loses its argument the way it originally did. For a watched
character `interpret()` now records every command with the room vnum,
refusals included, and for the second kind logs the command's **name
with its arguments dropped** -- so a password change is visible and the
password never is.

Recording refused input means a password typed at the wrong moment can
reach the log. That is the cost of the feature doing its job; the logs
are already handled as sensitive.

**`watch_log(ch, fmt, ...)`** is the hook for everything a command log
cannot see. It returns immediately unless that character carries
`PLR_LOG`, which is one bit test, which is why it can sit somewhere as
hot as `char_to_room`. Add to it rather than open-coding another
`log_string` behind an `IS_SET(ch->act, PLR_LOG)`; every line it writes
carries the room vnum in the same shape, so one grep finds a whole
session.

It is wired where a bug or a cheat shows itself:

- `char_to_room` -- where they ended up. A portal, a teleport or a
  recall ring moves a character with no command to account for it, so
  the command log alone cannot reconstruct a route.
- `advance_level` -- `level 34 -> 35`, and whether it was an advance or
  a restore.
- `gain_copper` -- any change. Coin from nowhere is the oldest exploit
  there is.
- `raw_kill` -- both sides of it, so a death has a cause and a kill has
  a victim.

Staff actions that change shared state should reach `log_string` and
not only `wizinfo`: wizinfo tells whoever is online at that moment and
nobody afterwards, which is no use when the question is asked a week
later. `REPORTS CLEAR` does both.

## Hermie

`spellup` places her; `buff` is how a player asks. She is modelled on
the healer at the pit -- `do_heal` in `src/misc.c` -- except that she
charges nothing, so `buff` sits at level 0. Speech still works and goes
through `spellup_listen()`, the same path as the command, so the two
cannot drift.

`SPELLUP_RESTORE` entries fill a pool outright rather than casting the
spell behind it. The watched session showed why: `refresh` and `heal`
hand out a slice, so a player topping up said `22` nine times in three
seconds and `23` nine times in two, and **every one of them
succeeded**. A free service standing in the temple can simply fill the
pool.

**Her menu has to fit one screen, and that is a correctness rule, not
a taste one.** `page_to_char` stops at "[Hit Return to continue]" and
the next thing the player sends is consumed as that return -- so a
menu that pages silently eats the command after it, and the player
sees their buff simply not happen. Hers ran to three screens (one
spell per line, its full name beside it, and "free" written forty
times) and cost two tests before anyone noticed it was the product.
It is three columns of keywords with the groups on one line now, and
`tests/test_spellup_mob.py` asserts both that it does not page and
that the next command lands. If you add to her list, take something
out of the layout.

Two things the compact version must keep saying, because they are the
whole point of her: that it is **free**, and how long a buff lasts.

Only spells with a real `spell_fun` and a character target belong on
her list. `iron skin`, `psionic armor`, `psychic shield`, `mindbar` and
`levitate` are all `spell_null` -- the same dead-registry state
`dshield` and `baura` were in -- and `detect poison`, `identify` and
`haven` target an object or an exit. `spellup_grant` refuses a
`spell_null` politely, but listing one is advertising nothing.

## Remort Gifts

A remort taken at level L leaves the character with `L - 53` remorts,
so the count and the level are not the same number and the code gates
on the count. They are named rather than written as bare integers:

| count | level | gift |
| --- | --- | --- |
| 1 | 54 | no hunger or thirst |
| 2 | 55 | psionics -- one power from each of four disciplines |
| 3 | 56 | `REMORTS_FOR_LONG_IDLE`, `REMORTS_FOR_BIG_PACK`, `REMORTS_FOR_EXTRA_PSI`, `REMORTS_FOR_SURE_RECALL` |
| 4 | 57 | `REMORTS_FOR_SHADOWMELD` -- the skill at `SHADOWMELD_GRANTED_AT`, and a third power each |
| 5 | 58 | every psionic power, no carry limit, a free choice of class and guild |

`REMORTS_FOR_BIG_PACK` is read by `remort_carry_multiplier()` in
`handler.c`, which doubles both `can_carry_n` and `can_carry_w`. It sits
below the `num_remorts >= 5` branches that lift the limits outright, so
the ladder stays monotonic.

**Psionics stack, and that costs a persisted field.** A remort wipes
`learned[]` wholesale, so re-granting from the sets alone redealt the
hand and could take a discipline a player had spent a life with.
`pcdata->psionic_known` is a comma-separated list of canonical skill
names, saved as `PsiKnown` under **case 'P'**, and `grant_psionics`
re-learns everything in it before awarding anything new. The per-set
target is `num_remorts - 1`, so the third remort holds two of each and
the fourth three. The `is_final` branch is checked **ahead of** an
immortal `grantpsi` spec: the last life gets all 17 whatever else was
asked for. `psionic_sync_known()` seeds the list from `learned[]` when a
player file is loaded, so characters who earned powers before the field
existed keep them across their next remort.

Hunger and thirst are moot in practice: `gain_condition` returns early
for anyone at `LEVEL_HERO` or above, and a remorting character is 54 or
better. A 2018 note complaining that the last remort carries none of
the earlier gifts was checked in 2026-09 and needs nothing.

**`idle_purge_ticks(ch)`** is the only place that decides how long an
idle character has. Both branches in `char_update` use it -- link-dead
and connected-but-idle -- and a test asserts `LINKDEAD_PURGE_TICKS` is
never compared against directly there, so a new branch cannot quietly
skip the bonus.

## The Psionic Awakening

**Psionics awaken between levels 18 and 21 and nowhere else.**
`PSI_AWAKEN_MIN` and `PSI_AWAKEN_MAX` in `merc.h` name the band, and
`do_check_psi()` in `src/stubs.c` is the one place that holds it: one
`number_range(18, 21)` per level *gained* inside the band, granting
when it equals the character's level. Four rolls at one in four, so
about a third of those owed finish the band with nothing. That is the
design and it is not a bug to be smoothed out.

Two ways to be owed psionics: a second remort
(`num_remorts >= 2 && psionic <= 0`), or an immortal's `GRANTPSI`.
Being owed is not receiving -- the band still has to be rolled
through. The exception is **above** the band: there is no level check
left to wait for, so a grant to a character past 21 lands at once,
exactly as though the roll had hit.

Four things were wrong here in 2026-09, all of them from the roll
living in the wrong place -- open-coded as
`chance = number_range(18,21); if (level == chance && psionic < 1)`
at each of two call sites:

- **`psionic_grant_pending` was written to the save file and read by
  nothing.** `GRANTPSI` set it, saved it as `PsiGrant`, told the
  immortal "they will receive psionics on their next level check" and
  the player "your mind tingles with unfamiliar potential" -- and
  then `do_check_psi` tested only the remort count. A level 50
  character carried `PsiGrant 1` for days having been promised it
  twice.
- **A login re-rolled.** `load_char_obj` calls `do_check_psi`, so with
  the roll at the call sites a character inside the band could relog
  until it landed. The call from the loader passes no argument now and
  only `"levelup"` rolls.
- **A grant above the band waited for ever**, because the band is
  behind you and nothing was checking whether it still could happen.
- **`number_percent() >= chance` in `grant_psionics`** made a chance
  of 100 miss one time in a hundred. `number_percent()` is 1..100, so
  a miss is `roll > chance`. Every caller forces the grant, which is
  the only reason nobody saw it.

And the offline branch of `GRANTPSI` loads a *copy* of the character:
any path that grants and returns without `save_char_obj` **and**
`extract_char` throws the grant away and leaks the copy into the
character list for the life of the process. There is one immediate
path for that reason. `tests/test_psionics.py` pins all of it.

**`psi_log()` writes the arithmetic, not the outcome.** Which power,
out of which set, against which roll, and why that one -- a grant is
rare and irreversible and the hardest thing in the game to argue
about afterwards, and none of it used to be recorded anywhere but the
player's own skill list. It writes one line per decision through
`log_string`, with the room vnum folded in; do **not** also call
`watch_log` from it, because both sinks are the same file and a
watched character then gets every line twice.

## The Remort Class History

Every life must be a different game from the last, so `do_remort` refuses
a class the character has already lived as -- until the fifth remort,
gated on `REMORTS_FOR_FREE_CHOICE`, which is free of it.

**The class is the whole of the restriction. The guild is free.** The
class is what decides how a life plays, so it is what the rule is for.
Guilds used to be barred as well, out of one flat
`had_classes[2*MAX_CLASS]` pool shared with the classes -- and a guild is
stored as its matching class index (`GUILD_MAGE == CLASS_MAGE`), so the
pool conflated the two and having been in the mage guild barred you from
ever living as a mage. A non-monk life also burned two of only six
values, so a reachable history left a player with no legal choice at
their fourth remort: an empty list, stuck at 57, with 59 out of reach for
good. `tests/test_remort_gifts.py` walks every path exhaustively.

`ListRemorts` is unchanged on disk and is **not** a flat list of numbers.
It is written one life at a time as `<class>` alone for a monk or a necro,
who have no guild, and `<class> <guild>` for everybody else. Read it back
the same way -- class first, and only look for a guild token when the
class was neither monk nor necro -- or the pairs misalign. `none` (-1) is
always a legal guild, which is what guarantees a choice always exists.

## Damage Costs Lag

**Wherever a command calls `damage()` and then returns, a `WAIT_STATE`
has to lie either before the call or between the call and the return.**
Otherwise the ability can be typed as fast as the player can type and
the damage piles up with nothing throttling it.
`tests/test_damage_lag.py` scans every `do_` function for it.

The exceptions live in that file's `EXEMPT`, each with its reason: the
stock "the victim died, do not touch the pointer" return, where the
fight is already over; `do_concoct`, whose damage lands on the brewer;
and `do_nerve_damage`, where a *missed* strike still deals `dice(4,4)`
and returns free **on purpose** -- a monk fights with no weapon, and
that consolation damage is part of what pays for it. Lagging it was
tried in 2026-09 and reverted. Adding to `EXEMPT` is a balance
decision, not a way to quiet a failure. A failed attempt that deals no
damage is outside the rule as well: it costs mana and nothing else.

Paying the lag before the roll, as `do_kick`, `do_smite`, `do_backstab`
and `do_shoot` do, covers every path below it. The psionics pay it after
instead, which is equally sound because each of their damage paths
reaches one.

One command broke the rule and was fixed in 2026-09: `BOMB`, which
takes half a target's maximum hit points with no roll, nothing consumed
and no lag at all.

**Immortals bypass lag entirely** -- `comm.c` reads
`if ( ch->wait > 0 && !IS_IMMORTAL(ch) )`, and `IS_IMMORTAL` is the raw
level, not trust. A staff character spamming an attack is that rule
working, not a missing `WAIT_STATE`; check the level before hunting for
one. No damaging ability has `beats` of 0 in `skill_table`: every
zero-beat entry is a passive (weapon proficiencies, dodge, parry,
second and third attack, fast healing, meditation).

## Shadowmeld

`AFF2_SHADOWMELD` is **stealth** with the timer removed and the room
nailed down: it holds through sitting, sleeping and everything else, and
ends on leaving the room, on striking, and on VIS.

It exists for two things, and both matter when judging a change to it:
going AFK without being killed for it, and laying in wait in a room
somebody has to walk through. The first is why no mobile may ever see a
melded character; the second is why striking ends it rather than being
forbidden.

It is a real skill. `gsn_shadowmeld` sits in `skill_table` at
**level 3 for every class**, which is deliberate -- a remort restarts at
3, and `get_skill` returns 0 below `skill_level` while `check_improve`
refuses to improve there, so a gift priced at the level it is given at
would be frozen until the character had climbed all the way back. Its
rating must stay non-zero for the same reason. Nothing teaches it: it is
in no group and no guildmaster's `can_gain`, so `do_practice`'s
`learned[sn] < 1` test and `do_gain`'s per-guildmaster list are what keep
it to the fourth remort and `SET SKILL`. `do_shadowmeld` does not look at
the remort count at all -- holding the skill is the gate, which is what
lets a grant work on a character who has never remorted.

`do_remort` reads the practised value **before** the skill wipe and puts
back `UMAX(kept, SHADOWMELD_GRANTED_AT)`, so a later remort never costs
it. `load_char_obj` grants it to anyone at `REMORTS_FOR_SHADOWMELD` who
holds none, which carries the characters who earned it when it was a flat
flag.

**Against players it is stealth, not hide.** `concealment_chance()` in
`handler.c` is the one place the roll and its weather modifiers live, and
both skills go through it, so the two cannot drift. Detect hidden does
not beat it; holylight does, from the shortcut above. Faerie fog strips
it, `damage()` breaks it for the attacker (which covers spells, where
`multi_hit` covers only melee), WHERE omits a melded character and
DANGER SENSE counts them, all exactly as they do for stealth.

**The check in `can_see` sits above the `IS_NPC(ch) && IS_IMMORTAL(ch)`
shortcut, and must stay there.** That shortcut hands every mobile of
immortal level perfect sight, so below it an aggressive high-level
mobile would walk in and kill somebody who had stepped away -- which
is the one thing the gift exists to prevent. `aggr_update` chooses its
victims with `can_see`, so that placement is the whole of the
protection. Against players it behaves like hide, so detect hidden and
holylight still find them.

`shadowmeld_break()` is called from `char_from_room`, which is every
way a character leaves a room. It must run **after** that function's
`in_room == NULL` check, and it guards its own `act()` as well: it is
reachable from extraction paths where there is no room to speak to.

## The Stash

Storage at `ROOM_VNUM_ALTAR` (4208), one room west of where RECALL
lands. Items go in from anywhere and come out only there, which is the
whole design: it stores loot without becoming a way to carry it.

The objects live in `ch->pcdata->stash`. They are **not** in
`ch->carrying`, not in a room and not in a container, so:

- `extract_char` never sees them and they need `stash_extract()`, or
  they leak on every quit.
- `obj_update` never touches them, because its first test is
  `obj->timer <= 0`, and anything with a timer is refused on the way
  in.
- They weigh nothing and count against nothing the character carries.

They are written to the player file under a `#STASH` marker **after**
everything else, including the pet. The marker puts `fread_obj` into
stash mode for every `#O` that follows, so nothing of the character's
own may ever be written after it. `stash_max` saves separately as
`StashMax` under **case 'S'**, and forgetting it means a bought upgrade
evaporates at the next login -- worse than not selling it at all.

Every deposit and withdrawal calls `save_char_obj()` immediately. A
stash written only at quit is a duplication bug waiting for a crash.

Fifty slots to start, twenty-five per purchase at `250 * n^2` gold, to
a ceiling of 500. The whole road is 527,250 gold, which against the
coin a level 50 mobile carries is something over four hundred kills.
`set player <name> stash <n>` grants room without the coin and refuses
to shrink a stash below what is already in it, which would strand
items nobody could reach.

`set` also answers to `player` now, not only `mobile` and `character`.

## The Note Board

`note_list_filtered()` in `src/act_comm.c` backs LIST, UNREAD and
SEARCH. Keep it that way: **the number it prints is the note's place in
the character's full list, not its place in the filtered one.** A
player who searches, sees `2)` and types `note read 2` has to get that
note. A filtered view that renumbers is worse than no search at all.

REPLY and FORWARD build an ordinary draft in `ch->pnote` through
`note_start()`, so everything downstream -- `note +`, `note show`,
`note send` -- is unchanged. REPLY does not stack `Re:`.

**A test world must not inherit the live board.** `tests/live_mud.py`
copies `area/` wholesale, and a working copy still holds `notes.txt`,
`bugs.txt`, `typos.txt` and `ideas.txt` even though they are untracked
now -- so a test that wrote its own note found it numbered 23 behind a
thousand real ones from the year 2000. They are excluded from the copy.
Clearing them after `__enter__` does not work: notes are read into
memory at boot and written back from there, so the file has to be
missing before the server starts.

## Player Reports

`bug`, `typo` and `idea` append one line each to `area/bugs.txt`,
`area/typos.txt` and `area/ideas.txt`, and always did nothing else. The
files reached 135, 106 and 500 lines on the live server because nothing
announced a report and nothing read one back.

`report_login_notice()` in `src/act_comm.c` now says at login how many
notes are unread -- for everybody -- and, for staff, how many reports
have arrived since they last looked. `REPORTS` reads them and
`REPORTS CLEAR <kind>` renames the file with a timestamp rather than
deleting it: those files are the only record of what a player said.
`pcdata->reports_seen[]` holds the per-character read position and
saves as one `ReportsSeen` line under **case 'R'** in `fread_char`.

Most of what is in them is not a report. A player who types `bug` and
their next command on one line files the command, so the files are full
of `wear all`, `here` and `short sword`. Clearing is therefore part of
the feature, not a nicety: a backlog nobody can clear is a backlog
nobody reads. Anything genuine in there is worth turning into work --
see the `title` command, teleport on oneself, and a Gang Land room
describing an exit it does not have.

The staff half is gated with `IS_TRUSTED(ch, LEVEL_IMMORTAL)`, not
`IS_IMMORTAL`. `is_note_to()` still uses `IS_IMMORTAL`, so a trusted
builder does not receive notes addressed to `immortal`; that is the
same class of bug as the INVULN one and has not been changed, because
it alters who receives mail.

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

## Quest Contracts

A quest request rolls for a contract before it settles the timer, and
the order is the whole of the exclusivity:

| | chance | timer | points |
| --- | --- | --- | --- |
| Emergency | `QUEST_EMERGENCY_CHANCE` (5%) | 5 minutes flat | x5 |
| Rush | 20% of what is left (~19%) | 5-8 minutes | x2 |
| Ordinary | the rest | 10-30 minutes | x1 |

**A quest is one or the other, never both.** The emergency is rolled
first and the rush is its `else if`; writing them as two independent
rolls would let a quest pay ten times. The multiplier likewise
*replaces* the rush one rather than stacking with it. The streak bonus
applies on top of whichever landed, as it always has.

**`questemergency` is cleared everywhere `questrush` is** -- six sites
-- because a flag left standing pays five times on the *next* quest.
Neither is saved: a mid-quest logout strips `PLR_QUESTOR` in `save.c`,
so there is no persisted state to migrate and no `fread_char` case to
get wrong. `tests/test_aquest_system.py` walks every `questrush`
clear and fails if one of them leaves the emergency flag set.

`complete_automatic_quest` reads both flags into locals at the top,
before anything clears them. Reading `ch->questemergency` later in that
function is reading a flag that has already gone.

## The Questing Streak

`quest_streak_bonus()` in `src/quest.c` is the whole of it, and it used
to be one line: `URANGE(0, ch->queststreak, 5) * 10`. That stopped dead
at five, so the sixth quest in a row paid exactly what the fifth did and
a run of fifty was worth no more than a run of five -- nothing rode on
keeping a streak alive past the first few, which is the opposite of what
a streak is for.

It climbs in shallower and shallower steps now, so a longer run is
always worth more without the reward running away:

| streak | each | total |
| --- | --- | --- |
| 1-5 | +10% | 50% at five |
| 6-15 | +5% | 100% at fifteen |
| 16-30 | +3% | 145% at thirty |
| 31-50 | +2% | 185% at fifty |
| 51+ | +1% | to `QUEST_STREAK_BONUS_MAX` (300%) |

Two rules if you touch the curve. **The first tier stays as it is** --
changing it would make somebody's existing streak worth less than it
was yesterday. And **the cap is load bearing**: `queststreak` is a
`sh_int` that only resets on a failure, so without one a streak nobody
breaks pays an unbounded multiple. The bonus applies to the quest-point
reward, not to the coin.

The bonus is read *before* `queststreak++`, so the message naming
"streak of N" is paying the bonus for N-1. That is how it has always
worked and changing it is a reward change, not a display fix.

## What The Quest Master Will Not Ask For

`automatic_quest_target_is_suitable()` in `src/quest.c` decides the
pool, and `quest_area_is_excluded()` keeps **Hyrule** out of it.
`QUEST_EXCLUDED_AREA` in `merc.h` names the file, not a vnum range: the
area is generated, so its vnums belong to the generator, but
`hyrule.are` is fixed. The reason is size and newness -- 443 rooms,
most generated, with no-recall dungeons, so a quest aimed seven floors
down is a half-hour march through content the player may never have
seen.

Exclude another area by name there rather than by adding a second
mechanism.

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

**A recall point is refused by flags, never by who is standing there.**
`room_allows_recall_point()` used to include `room_is_private()`, which
made it stricter than recall itself -- the way out tests `ROOM_NO_RECALL`
and `ROOM_JAIL` and nothing else -- and made it unstable, because
privacy is an occupancy count. A player at the quest giver was told the
gods would not hear them: the room is `ROOM_PRIVATE` and the questmaster
and the player together made two. And since the stored vnum is rechecked
on every use, a point set in a quiet moment would have reverted to the
Temple the next time somebody else walked in. Jail, death traps,
no-recall, implementor-only and gods-only still refuse it.

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

`is_invulnerable(ch)` is the one test, and it asks
`IS_TRUSTED(ch, LEVEL_IMMORTAL)` -- **trust, not level.** `interp.c`
gates every command on `get_trust()`, so gating the effect on
`IS_IMMORTAL()` meant a builder trusted to immortal rank could run
INVULN, was told it was on, and took damage anyway. The protection still
lapses on its own, because `get_trust()` falls back to the level when no
trust is assigned. A switched immortal is not protected: `PLR_INVULN`
shares a bitfield with the `ACT_*` flags, so the `!IS_NPC` guard is load
bearing and a mobile's own bit must never be read as this one. `damage()` honours it in three places: an
early return for `PLR_INVULN_ABSORB`, the `damage_eq` call, and the
subtraction from hit points. Leaving the subtraction as the chokepoint is
deliberate -- everything above it, `dam_message` included, still runs, so
the default reading of a blow is the ordinary one and only the loss is
skipped. Nothing displays the flag: not `score`, not the room. That is a
deliberate difference from WIZINVIS and CLOAK.

## The GMCP Feeds

`src/gmcp.c` owns the JSON; `telnet_proto.c` owns negotiation. Three
feeds carry game state to the Mudlet package, and each has a rule that
is invisible when it is broken.

**`Room.Info`** carries `exits`, and since 2026-09-30 also `doors`
(per direction: open, closed or locked), `flags`, and `services` --
what the room is *for*, being a shop, questmaster, guildmaster,
trainer or healer. The doors loop must keep every guard the exits loop
has: `EX_SECRET` and `can_see_room`, or the map draws a door the
player cannot see. `services` reports roles and not occupants, so a
mobile wandering through does not churn the payload hash.

`ROOM_DT` is in `flags` and is not the spoiler it looks like:
`Room.Info` describes the room you are standing in, and a death trap
kills you on the way in, so the only character who ever receives that
flag is one it has already killed. What it buys is a map that
remembers.

**`Char.Affects`** is de-duplicated by skill. Several spells are two
`AFFECT_DATA` sharing one name -- bless carries a hitroll affect and a
saving-throw affect, both called "bless" -- and a list that says so
twice reports the implementation rather than the character. The walk
is bounded, and shadowmeld is listed by hand for the same reason
`do_affect` lists it by hand: it is a bare bit with no `AFFECT_DATA`
behind it.

**`Comm.Channel` is emitted where the text is delivered, never from
one central place.** This is the important one. The tempting shortcut
is a single emit from `channel_history_add()`, the register the
HISTORY command uses -- but that register knows the channel and the
speaker and *not the audience*, and the audiences differ: yell reaches
one area, the staff channels are rank-gated, and every channel honours
its own deafness flag. A chat window built on a second guess at the
audience shows people things they did not hear. So there are two calls
per channel, one beside the speaker's own `send_to_char` and one
inside the loop that writes to each listener, and correctness comes
free from standing in the same place. Tells go through
`tell_history_add`, which is already called once per recipient.

**A say is journalled and never put in a ring.** `do_say` calls
`channel_journal_record()` and emits to everyone in the room, and
deliberately does not call `channel_history_add()`. HISTORY hands its
rings to whoever asks, including somebody who was nowhere near, and
nothing remembers who was standing where -- so a say can be recorded
for staff and shown live to the room, but it cannot honestly be
replayed. Do not "fix" this by adding say to `channel_meta_table`.

`tests/test_gmcp_payloads.py` counts the emit sites against the number
of channels, so a channel added without its two emits fails the same
way one added without its history call does.

## Channel History

`HISTORY` reads back what was said. It exists because a player's Mudlet
chat capture stopped part way through a session and nothing on the
server could recover the lines.

- **In memory for the in-game command, on disk for the dashboard.**
  The rings behind HISTORY are still memory-only and still go on a
  reboot: that is a scrollback for somebody who missed something.
  Since 2026-09-29 each line is *also* appended to
  `log/channels.tsv` -- `<epoch>\t<channel>\t<speaker>\t<text>`, the
  same shape as the login journal -- because the dashboard is a
  separate process and cannot read the game's memory, and the owner
  asked to see the history there. `channel_journal_record()` in
  `act_comm.c` writes it and trims at `CHANNEL_JOURNAL_MAX` back to
  `CHANNEL_JOURNAL_KEEP`, and it is called from inside the shared
  register so the file cannot drift from the rings.

  **Tells are not in that file and must never be put in it.** They do
  not pass through the shared register, and that separation is the
  whole reason a global channel journal is safe to write: `log/` is
  committed to a public repository every five minutes, so what lands
  in there was said to a room full of people. A private message is a
  different feature with different consequences.

  `/api/channels` reads it, token-gated like the other player views,
  and filters by channel and by text. The Chat view in the dashboard
  is that endpoint.
- **`channel_meta_table` in `act_comm.c` is the register.** A new
  channel that sends without calling `channel_history_add()` is a
  silent hole; `tests/test_channel_history.py` counts the call sites so
  one cannot be added or dropped unnoticed. The four channels that go
  through `channel_say()` are covered by the single call inside it; the
  six that walk the descriptor list themselves each record their own.
- **Reading a channel back needs the rank that hearing it needs.**
  `history_may_read()` compares `get_trust()` against the same
  `hear_level` the live channel uses, and a channel the character
  cannot read is never gathered and never listed.
- **Tells are never in the shared rings.** Each character keeps their
  own in `pcdata->tell_history`, which is not saved and is freed in
  `free_char`. Putting them in a global ring would have leaked private
  conversation to anybody who typed HISTORY.

**Nothing is pushed at a player on arrival.** That was tried and taken
out: a login notice showing what was missed is noise somebody has to
read past. `history_print()` draws a
`--- while you were away ---` line instead, at `pcdata->last_logout`,
so HISTORY answers the question only when it is asked.

`last_logout` is saved as `LastOut` and is set **both** in `do_quit` and
in `close_socket`'s link-dead branch -- setting only the first means a
dropped player's marker sits at their last clean quit instead of at the
drop.

`HISTORY` with no argument, or with a number, merges everything the
character may read and sorts it by the clock, so the tell history needs
its own `tell_history_when` -- a formatted line with the time baked in
cannot be sorted against the channels.

## One-Person Rooms

`ROOM_SOLITARY` closes a room at one occupant and `ROOM_PRIVATE` at two.
Two rules, both learned from one incident where an idle immortal in the
quest room shut questing down for the whole mud:

- **Only mortal players count towards the occupancy.**
  `room_is_private()` skips NPCs and anyone at immortal trust. A mobile
  that lives in the room filled a slot for good -- the quest giver's
  room is `ROOM_PRIVATE`, so the questmaster plus one player was already
  two, and a solitary room with a resident mobile admitted nobody at
  all. The flag exists to stop players walking in on each other, not to
  let a mobile or a staff character close a room by standing in it.
- **`can_enter_private_room(ch, room)` is the one place that decides
  who may walk in anyway.** Every caller used to ask
  `ch->level < 69` -- the raw level, and a number rather than a rank --
  so an ordinary immortal was refused and a builder trusted to immortal
  rank was refused everywhere. `ROOM_IMP_ONLY` is not an occupancy
  limit and keeps its own `GOD` bar inside that helper.

`tests/test_private_rooms.py` pins both, including that no caller reads
a raw level again.

## Permission Helpers

Two helpers exist so a rule is stated once. Prefer them to open-coding a
comparison:

- `get_trust(ch)` -- **never read `ch->trust` directly**, and never
  read `ch->level` or `IS_IMMORTAL()` to decide whether somebody counts
  as staff. The field is 0 unless somebody explicitly assigned a trust,
  which is the normal state, so a raw comparison refuses everybody
  including implementors. Nine gates had that bug.

  `interpret()` gates every command on `get_trust(ch)`, so anything
  asking the level instead disagrees with it for exactly one kind of
  character -- a builder given immortal trust without an immortal level.
  They can start the command and then be refused by it. Eight more were
  found in 2026-09 by sweeping the 111 commands WIZHELP lists:

  - `channel_say()` tested `victim->level`, so **all three staff
    channels were half-broken**: immtalk, godtalk and hero let a
    trusted builder speak and never let them hear.
  - `do_switch` used `IS_IMMORTAL(ch)` to pick a *message*, and the
    branch below is the werewolf shapeshift -- so a trusted builder who
    switched was moved to room 9 with a `were_shape` copied onto the
    mobile.
  - `do_ksock`, `do_forcesave`, `do_hpardon`, `do_lst_maxload`,
    `do_finger`, and `is_note_to` for staff mail.

  Three look like the same bug and are not: `do_force` already asks
  `get_trust` for permission and reads `vch->level` only to pick which
  victims a sweep covers, `do_forcesave` keeps a `vch->level < 3` floor,
  and `do_remort` assigns `ch->level`. `do_immort` in `act_comm.c` is
  declared, defined, and **never registered in the command table** --
  an orphaned duplicate of immtalk with its own `IS_IMMORTAL(victim)`
  loop. `tests/test_staff_trust.py` keeps the sweep.
- `rank_protects(ch, victim)` -- whether rank stops `ch` acting on `victim`.
  Implementors are exempt, because `get_trust(victim) >= get_trust(ch)` reads
  `70 >= 70` at MAX_LEVEL and locked implementors out of twenty-two commands
  aimed at exactly their peers. Commands that should not target the user
  keep their own `victim == ch` guard; rank is a separate question.
- `is_loopback_ip(ip)` -- one place that knows what 127/8 means, used to
  keep the healthcheck's two-minute probe out of the log and to decide
  whether a PROXY header may be trusted.

## The Training Yard

`src/dummy.c`. Mob 2400 in room 2419 (`area/dummy.are`), reached by
the practice ring (object 2404) in the Grand Knight's Sparring Room,
4462, in Dresden. Every rule below was either asked for by the owner
or found broken live; keep them.

- **One fighter at a time.** The yard is `ROOM_SOLITARY` with
  `ROOM_ARENA`. `room_is_private()` counts mortals only and
  `can_enter_private_room()` lets immortals in, which is the rule.
  `do_enter` asks it **before the portal's fare** -- portals used to be
  the one way into any private room in the world that never asked.
- **Nobody can be shut in.** No walking exit; LEAVE RING is the way
  out on foot, so the yard must never become `ROOM_NO_RECALL`.
- **A run never heals.** Hit points, mana and moves are snapshotted
  at the first blow and put back at the stand-down -- never set to
  max, or the yard is a free heal for anybody who walks in half dead.
  `dummy_left_yard()` in `char_from_room` puts them back on any way
  out mid-run, because a snapshot carried out could be cashed in later.
- **Nothing is learned there.** `check_improve` returns in the yard.
- **The dummy never holds a grudge.** `add_hate` refuses it, and the
  stand-down ends only this player's fight (`stop_fighting` with
  `fBoth` froze a grouped partner's run).
- **Damage is recorded at the subtraction** in `damage()`, beside
  `is_invulnerable`, and blows turned aside by the four defensive
  checks just above it, through `dummy_defended()`.
- **The default is a fair fight, and the default is what you get.**
  Twenty-five rounds and a bell, against a dummy at your level that
  dodges, parries, blocks and hits back. `DUMMY DEFENDS NO` and
  `DUMMY FIGHTS NO` take its part out for measuring damage alone --
  separate settings, said yes or no, never toggled. The settings are
  shared statics, so `dummy_left_yard()` puts them back to standard
  when the yard empties of players; otherwise the next person to walk
  in and simply attack inherited the last fighter's endless,
  defenceless setup.
- **Every change says whether runs still count.** `do_dummy` is a thin
  wrapper that watches the configuration counter around
  `dummy_command()`, so a new setting cannot forget to say it.
  `dummy_unstandard_reason()` is the one list of what "standard" means,
  one named reason per setting.

The **benchmark board** is `area/dpsboard.txt`: every character's best
standard run, one line each. The standard run is the dummy exactly as
DUMMY RESET leaves it, at the runner's own level, reaching the bell at
`DUMMY_BENCH_ROUNDS` (25) rounds, against a dummy that defends itself
and fights back; a configuration counter noted at the first blow refuses a
run during which anybody changed the dummy. Immortals are not ranked
-- **by level, not trust**, the one deliberate exception to the rule
under Permission Helpers: a player trusted with staff commands fights at
their own level and pays lag like anyone else, so their run is real.
The board file starts `#standard N` (`DPSBOARD_STANDARD`); a board
written under another definition of the standard fight is set aside on
load rather than ranked against runs it cannot be compared with. Bump
it whenever the standard changes. The file is runtime state and has to be named as such in
**five** places -- `.gitignore`, `toc-state-sync`'s `STATE_FILES`,
`toc-deploy`'s `runtime_txt`, `validate.yml`'s `paths-ignore`, and the
copy filter in `tests/live_mud.py` -- and a test checks all five.

`tools/build_directions.py` names a portal by its **first keyword**,
which is why the ring's keywords begin with `ring`: the published route
and HELP DUMMY's walking directions both say ENTER RING, and a test
pins the help's directions to the generated route.

The quest master excludes the yard by file name beside Hyrule
(`QUEST_EXCLUDED_YARD`): the dummy cannot die, so a quest to kill it
could never finish.

## Completion Standard

A task is complete only when the requested behavior or documentation is
implemented, relevant tests pass, the diff is reviewed, and any limitation or
unrun test is reported. Do not leave required long-running test/server sessions
unattended at final response.
