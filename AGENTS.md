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
- `wiki/disaster-recovery.md`: current Oracle Cloud hosting, deploy and recovery
- `wiki/windows-production-hosting.md`: retired Hyper-V VM operations (history)
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
  `data/hyrule_first_quest.json`, `data/hyrule_room_prose.json` (room names
  and descriptions), `data/hyrule_mob_prose.json` (enemy and boss text)
  and/or the generator, regenerate, and test.
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

Current October 2026 Python baseline:

```text
102 listed area entries
2,494 mobiles
3,721 objects
7,787 rooms
0 critical, 12 warning, 1,635 information findings
```

Objects and information findings both rose by exactly 53 on 2026-10-04,
when every Hyrule guardian gained a drop for each armour slot its first five
left open (`BOSS_EXTRA_DROPS`, vnums 30700 on): like the first five, they
are made by `make_corpse`, so each counts as `object-has-no-source`.

Removing the catalog's unplaced plain red ring (`30261`) and Ganon's copy
of the Blue Ring of Hyrule (`30578`, the shop's ring now carries the name)
took two objects and two `object-has-no-source` findings off in October
2026.

Hyrule's NES pass (October 2026) moved all three. Mobiles rose by 68: the
78 people of Hyrule became a record each, replacing nine shared ones, and
Level 6's band lost its only gel, whose room was really an old man's.
Objects rose by 47 and information findings by exactly 45: the guardians'
drop tables are five pieces each, made by `make_corpse` like the enemy
drop potions, so they count as `object-has-no-source`; the rest are the
Magical Sword, bombs, the bigger bomb bag and a gravestone, less the
bottomless bomb satchel and the money caves' rupee piles. The four rooms
are the hint caves.

The mobile count rose by about ninety when Hyrule's enemies became one
generated record per kind per level band (see `wiki/hyrule-area.md`).
Objects rose by thirty-five, and information findings by twenty-seven, when
Hyrule's bosses gained Heart Containers and its enemies random drops: the
27 drop potions are made by `make_corpse`, not by a reset, so they count as
`object-has-no-source` exactly as Ganon's relics always have. Eighteen more
came with the dungeon chain -- eight guardian keys, nine chests and the
final Triforce piece -- and one more finding, The Triforce, which
COMBINE makes and nothing places.

The information count fell from 1,571 when 176 resets that had been
commented out as "(removed: room/obj does not exist)" went back in; every
vnum they named was present all along. See the changelog entry for the
parsing mistake behind the claim.

Seven list entries are help/social files without `#AREA` (`commands`,
`routelist`, `skills`, `spells`, `masters`, `toc`, `social`), so the native
validator reports 95 areas against the Python tools' 102 entries. Online
building saves into `custom.are` (`BUILDER_AREA_FILE`); because `area.lst`
lists it, boot creates no extra area. Do not force native and Python area
totals to match by removing valid files or hiding the builder area.

Run tests proportional to risk. Movement, combat, extraction, persistence,
world loading, command authorization, and queue changes need the full suite plus
manual gameplay checks.

**The full suite takes about 35 minutes, and the maintainer does not want it
run routinely.** Around 109 of its tests each boot a real server that parses
every area file (the generated Hyrule alone is 447 rooms and 1,519 resets),
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

`MudClient.expect` says which way it failed in the first line, because that
is all CI reprints: **"server hung up before"** means the connection closed
without the text arriving, **"timed out waiting for"** that the server was
slow. The first message is what found the login throttle tests' CI failure
(4caaafc): the server hung up at the password prompt. `do_quit`'s sweep for
duplicate logins closed every connection holding the quitter's name,
including one at the login prompts, so a quit still waiting out lag -- the
fixture's own `quit` -- killed the next login attempt silently. The sweep
now asks for `CON_PLAYING` (`tests/test_quit_isolation.py`).

Live-test gotchas that look like product bugs and are not:

- Character names must be **alphabetic only** and at most 12 characters.
  A digit makes creation fail and the save file never appears.
- **A name that is a mobile's keyword is refused too**, with the same
  symptom ("no saved player file"). New area content can break an old
  fixture this way: Hyrule's potion sellers took "seller" in October 2026
  and `test_shop_purse`'s "Seller" failed CI from then. Prefix fixture
  names with Z.
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
- `src/walkto.c`: WALKTO -- named destinations, pathfinding from the
  player's room, and the paced walk
- `src/build.c`: in-game building in words -- SET MOB/OBJ <vnum>, MSHOW, OSHOW,
  with the name tables for every mobile and object flag word; ANEW/ASAVE/MCREATE/
  OCREATE are in `act_wiz.c` and the area writer in `db.c`
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
  already know. `gainlist` (alias `abilities`, `src/abilities.c`) lists
  every skill and spell the character's class and guild can buy -- X
  missing, + learned -- grouped by what to GAIN, with the trainer and the
  WALKTO; `gainlist trainers` is the old per-trainer view
  (`gainlist_by_trainer` in `act_info.c`). The same list rides to the
  Oracle with every question (`abilities_oracle_summary`). It never
  announces itself at a level gain (owner).
- `changes` (`src/changes.c`) reads `area/changes.dat`: entries headed
  `@ <id> <yyyy-mm-dd>`, newest first. It shows the last two weeks'
  entries a character has been shown fewer than three times and counts
  each showing (`ChangesSeen`, case 'C'); `changes all` shows everything.
  Add an entry for every player-visible change, and never reuse or alter
  an id -- the counts are kept by id.
- `alias` / `unalias` live in `src/act_comm.c`; expansion is in
  `src/interp.c` and must not leave a trailing space, or commands that read
  their whole argument (`goto`) fail on it. An alias may hold up to
  `ALIAS_MAX_COMMANDS` commands split on `;` (`\;` is literal): the first
  runs at once and `queue_alias_input()` in `src/comm.c` puts the rest at
  the front of `d->inbuf`, counted by `d->alias_queued`, so lag applies
  between them and each is logged by its own name. A line that came out of
  an alias is never alias-expanded again -- that is the recursion limit --
  and is exempt from the input-spam count and from `!`.
  A *typed* line with semicolons is split the same way by
  `split_typed_commands()` in `comm.c`, on the browser client's rules
  (`webadmin/static/command-sequence.js`: quotes and `\;` keep a
  semicolon), with the rest queued through `queue_alias_input()` -- so a
  chained command is not alias-expanded either. A line whose first word is
  ALIAS, UNALIAS or a password command is never split.

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

**Retiring an object players can hold needs a row in `retired_objects`**
(`src/save.c`): the retired vnum and what replaces it. Without one,
`fread_obj` drops the item at the holder's next login with a "bad vnum"
bug line -- which is how Alaric lost four satchels of bombs when the
Hyrule NES pass retired 30542. `tests/test_retired_objects.py` checks
every row points from a vnum that is gone to one that exists.

**Check that the generator still reproduces the file before regenerating.**
It had drifted: 197 rooms in `area/hyrule.are` carried recall and always-lit
flags that had been applied to the generated output by hand, and
`scripts/build_hyrule_area.py` knew nothing about them, so the next
`make hyrule-area` would have put `ROOM_NO_RECALL` back on the whole area
and taken `tests/test_hyrule_progression.py` down with it. The rule now
lives in `room_flag_word()`. `area/hyrule.are` is also the one area file
committed with CRLF line endings; the generator writes LF, so a
regeneration rewrites every line of it.

Hyrule prices itself in ordinary gold and says so in the object
descriptions ("displayed for 130 gold"). Until 2026-10-03 it said rupees;
a rupee was always a gold coin underneath, so the owner had the word
dropped and no amount changed. The generator writes `cost *
COPPER_PER_GOLD`, and the coin piles are `ITEM_MONEY` with `value[1]` set
to `TYPE_GOLD`. The manifest's `"type": "rupee"` landmarks and the prose's
`rupee:B6` keys are data names and stay; nothing a player reads may say
rupee, which `tests/test_hyrule_progression.py` checks.
`tools/reprice_by_level.py` skips the file for both reasons: it is
generated, and its prices are already calibrated against its own drops.

Hyrule's dungeons climb from Level 1 (characters level 2-8) to Death
Mountain (53-59), and its enemies are generated once per kind per band, at
mobile vnum `31000 + code * 10 + (band - 1)` -- so a keese in Level 1 and
one in Level 9 are different mobiles. The like like, bubble and wallmaster
contact effects in `src/fight.c` find their kind through
`hyrule_enemy_kind()`, which decodes that vnum; `HYRULE_TIER_FIRST` and
`HYRULE_TIER_LAST` there must match `TIER_VNUM_FIRST`/`TIER_VNUM_LAST` in
the generator. The manifest's encounters are the NES cast; the generator
thins crowded rooms to at most three. Bosses keep their vnums (the
achievements name them); their stat lines are generated, and their room
lines and descriptions, like every enemy's, come from
`data/hyrule_mob_prose.json`. Every item a player can get sits at or below
the band it is found in -- the generator rewrites the retained catalog's
levels and stats from the bands. The Master Sword (level 58) lies in
Ganon's great chest,
and must stay the best weapon a mortal can get anywhere at 59 or below;
`tests/test_hyrule_progression.py` measures it against the whole world.
The old men, Zelda and the other non-combatants are refused by
`is_hyrule_bystander()` in `is_safe`, so their high levels cannot be
farmed.

**Nothing in Hyrule is aggressive** (owner, 2026-10-04): the generator's
`calm_mobiles()` strips `ACT_AGGRESSIVE` from every record, so do not read
that flag to tell a Hyrule enemy apart -- `hyrule_room_has_guardian()`, which
holds shutters shut, asks for a non-bystander Hyrule mobile instead. Enemy
stats follow the world's median hit points and damage a round at their
level (`HIT_POINT_CURVE`, `DAMAGE_CURVE`, the band calibrations), and the
overworld is graded along the routes to each dungeon; see
`wiki/hyrule-area.md`. `tests/test_hyrule_walkthrough.py` plays the whole
chain as a mortal -- run it after any change to the overworld, the gates
or the owl's directions.

**Worn powers are ROM `F` records.** `load_objects` reads
`F` / `A <location> <modifier> <bits>` and puts the bits on the prototype
affect; the Master Sword's haste and the Red Ring's sanctuary are the two
users. `equip_char`/`unequip_char` already apply and lift prototype
bitvectors and restore what spells or other gear still grant. Such a bit
is not an `AFFECT_DATA`, so AFFECTS and the `Char.Affects` feed list it
through `equipment_affects()` in `handler.c`, naming the item; a bit gear
can newly grant needs a row in its `gear_affect_names` table to show. A spell that
strips a bit by hand -- dispel magic on sanctuary, slow on haste -- must ask
`equipment_grants_affect()` first. The dashboard parser keeps them in
`Object.affect_bits`, apart from `affects`, which every caller reads as
stat applies, and `tools/costs_to_copper.py` and `tools/reprice_by_level.py`
step over it -- a reader that stops at an unknown trailer loses every
object after it, which `tests/test_shop_prices.py` catches. `fread_flag` reads no minus sign, so an infinite light is
written 999 (`create_object` makes it -1).

**The Triforce is holy sight, capped at 59.** `triforce_sight()` in
`handler.c` is asked wherever `PLR_HOLYLIGHT` grants sight, and
`sight_trust()` -- `get_trust` raised to `TRIFORCE_SIGHT_LEVEL` for the
wearer -- is what sight compares against a wizinvis or cloak level. Add a
new holylight check and it needs both; `tests/test_hyrule_progression.py`
fails on a `PLR_HOLYLIGHT` sight test that does not also ask the Triforce.

**Ganon needs a group, and `spec_ganon` is why.** His fireballs are spell
blows no parry stops, two every four seconds at random members of the
fight; his melee barely matters. Retune him with the simulation described
in `wiki/hyrule-area.md`, not by feel: the Silver Arrow's tenth-of-health
floor fixes the fight's length, so his damage per pulse is what decides
who wins.

**The other eight guardians are hard, and Hermie is what makes them
possible** (owner, 2026-10-04). A median player at the top of the band
loses alone; the same player buffed by Hermie (EMPOWER, TITANIC, the
defence and combat groups) wins about two fights in three. "Median" is
measured, not assumed: the saved player files' hitroll, damroll and hit
points by level, and a live playtest of a warrior in average gear (the
Gear Finder's median per slot, or the Hyrule gear they would hold by then)
-- see "Guardian Fights" in `wiki/hyrule-area.md`. The old simulation
scaled player damage by 2.5 to match the training yard's best runs, which
sized every guardian for players far above the median; do not reach for
that scale again. Hit points still climb guardian by guardian to Ganon's,
and no guardian's blow may reach his (`tests/test_hyrule_progression.py`).
Gohma's catalog sanctuary is stripped (`GUARDIAN_AFFECTS_REMOVED`): with it,
a buffed solo player could not wear her down at all.

**The dungeons are done in order, and the chain is data in three places
that must agree.** Each guardian drops its dungeon's key (Ganon's is the
Golden Key); the key opens the magical door behind it and the locked chest
there, which holds the dungeon's Triforce piece and its treasure. The next
dungeon's entrance asks for the piece and its guardian's chamber for the
treasure, through `hyrule_progress_gate` in `act_move.c`, asked per
character by `move_char` and `do_enter` -- never a door somebody else can
hold open. The generator's `DUNGEON_TREASURE`, `ENTRY_NEEDS` and
`GUARDIAN_NEEDS`, that C table, and the plan table in `wiki/hyrule-area.md`
must say the same thing; `tests/test_hyrule_progression.py` checks the first
two against each other and the chests. Pieces are treasure, not keys,
because `save.c` drops keys at quit; they are NODROP so one character cannot
carry another through. `reset_area` refills and relocks Hyrule's chests
even with players about, since Hyrule is one area -- but never one a player
is standing at. `COMBINE TRIFORCE` is the only way to The Triforce.

**Keyed chests relock themselves on the tick, and only unattended ones.**
`obj_update` closes and locks every keyed container each tick, and now and
then traps one. Until 2026-10-05 it did that to every container in the
world, so a chest slammed shut between a player's OPEN and GET whenever a
tick fell there -- the "The chest is closed" that failed the walkthrough
and the dungeon chain test in CI for days, and never on demand. It now asks
for a container lying in a room no player is in
(`tests/test_container_relock.py`). A failure that only appears on a slow
runner and lines up with a tick or a reset is worth a seven-minute loop
before anything else.

**The NES machinery lives in `src/hyrule.c`** (October 2026; the plan is
"The NES Pass: Plan" in `wiki/hyrule-area.md`). Four rules to keep:

- **A Hyrule seal is not a door.** Bomb walls, bushes, Armos, blocks, the
  lake and the hungry Goriya are exits reset secret (`D` state 4) that only
  the NES's act with its tool opens. `hyrule_seal_refuses()` in
  `act_move.c` is asked by OPEN, PICK, DOORBASH and UNLOCK; a new way of
  opening an exit must ask it too. `reset_area` leaves an opened seal open
  while anyone is in Hyrule, because its puzzle object only comes back with
  an `O` reset, which waits for the area to empty -- resealing first would
  shut a way with nothing left to open it by.
- **What pays once pays each character once.** `pcdata->hyrule_secrets`
  is saved as `HyruleSecrets` under **case 'H'**, a bit per money cave,
  take-any cave, Heart Container and bomb bag; the bit layout is at the top
  of hyrule.c's secrets section and must not be renumbered.
- **Every person is a record of their own**, generated from the `npcs`
  table of `data/hyrule_mob_prose.json` into `HYRULE_NPC_FIRST`-`LAST`;
  `is_hyrule_bystander()` covers the range. Add a person there, not by
  reusing someone else's vnum.
- **Tables mirrored in C** -- the money caves' rooms and sums, the claims,
  the guardians for the drop tables, the potion shop rooms -- are held to
  the generator by `tests/test_hyrule_progression.py`,
  `tests/test_hyrule_nes.py` and `tests/test_hyrule_boss_drops.py`.

Hyrule workflow:

```bash
make hyrule-area
make test-hyrule
python3 check_exits.py
python3 check_resets.py
python3 scripts/area_lint.py --fail-on critical --limit 100
```

## The Sanitizer Job Plays

The `sanitize` CI job used to boot the world and idle for 45 seconds, which
runs almost none of the game -- nobody connects. It now also plays a set of
live test modules against the ASan/UBSan binary (`TOC_SERVER_BINARY`,
honoured by `tests/live_mud.py`), two at a time because the sanitizer
build is slow enough that four at once miss the tests' reply windows. To
reproduce locally: build with `-DENABLE_SANITIZERS=ON`, copy `bin/rom`
somewhere, and run `TOC_SERVER_BINARY=<it> JOBS=2 scripts/test-parallel.sh
<modules>` with `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1`. Add a module
there when it exercises code nothing else in the list does.

## The Mudlet Starter Map Is Generated

`mudlet/toc-world-map.xml` is built from the rooms by
`python3 scripts/build_mudlet_package.py`, and `scripts/validate.sh` runs it
with `--check` **before the test suite**. Any change to a room's name,
exits, sector or existence -- a new room in `limbo.are`, a typo fixed in a
room title, a Hyrule regeneration -- leaves the map stale, and CI then
stops at that check: from 2026-10-02 to 10-03 every push failed there and
no test ran in CI at all, because the Oracle's sanctum room had been added
without regenerating it. Rebuild it in the same commit as the room change,
and run `python3 scripts/build_mudlet_package.py --check` before pushing.

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
documenting the command (below) and naming every area with a route and
how far out it is. That file is
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

90 of the 93 areas holding rooms have a route. Dresden has none because it
contains the start room. The Quest Zone (20301-20313) and Temple Despair
(26000-26006) have none because nothing in the world links to them -- the
first is finished content with no entrance, the second an empty shell with no
mobs or objects. Do not invent entrances for them; ask.

**Trainers and guild halls are in the JSON too**, as a `trainers` list
beside `routes` (and a short `places` list: the square, the Temple and its
altar). Each entry has `name`, `role` (`guild hall`, `guild clerk`,
`guildmaster`, `practice` or `train`), `class`, `guild`, `room`, `vnum`,
`commands`, `steps`, `rooms_away` and `members_only` -- the Mudlet package
reads exactly those keys -- plus `who`, `learners`, `teaches`, `gains`,
`trains`, `place`, `keywords` and `mob` for the Oracle and WALKTO. The
sources are the game's own tables, read from the C: `guildmaster_table`
in `src/const.c` (who teaches what, to whom) and `gg_table` in
`src/special.c` (which guard stands where). The six halls are named from
HELP GUILDS in `GUILD_HALLS`. The router does not model guards, so a route
into a hall is the members' route and `members_only` says whose; hall
rooms are walked the way `guild_closed_rooms()` walks them, except that
the hall's own door may carry you in (the monks' Palm of the Creator is a
teleport room). Castles -- Valhalla, Forsaken and the rest -- are set by
staff, not joined, and their halls are ordinary area routes.

**`area/walkto.dat` is generated from the same payload**, one
tab-separated line per destination (`kind vnum name place keywords who`),
LF line endings (`.gitattributes`), and `tests/test_walkto.py` asserts the
generator reproduces it byte for byte. It is code, not runtime state:
`toc-deploy`'s `area/*.txt` exclusion does not touch it and the test
copies `area/` wholesale. Regenerate after anything that moves a trainer,
a guard, a guild hall or an area entrance.

## In-Game Building

The player-facing reference is `wiki/building-guide.md`; it is built in
phases (areas and rooms; MCREATE/OCREATE and ASAVE; English SET MOB/OBJ,
resets and a guided wizard to come). Three rules the code depends on:

- **An area made with ANEW owns its vnum range**, declared in an
  `#AREADATA` header (`load_areadata`). Mobiles and objects carry no area
  pointer, so the range is how `save_area_full` in `db.c` knows what to
  write, and why MCREATE/OCREATE refuse a vnum outside one. RSAVE on such
  an area saves it whole; a legacy `#AREA` area still saves rooms only.
- **The writer is the loader's exact inverse**, and
  `tests/test_building_mobs_objs.py` holds it to that: save, reboot, save,
  byte for byte. Change a loader and change its writer in the same commit.
  Object trailers are prepended on load, so they are written last to
  first; spell values are written as slots; a reset the loader would exit
  on is left out and counted. One difference is the game's own: boot makes
  a room with no exits NO_MOB (`fix_exits`).
- **A prototype string made after boot goes through `str_perm`, never
  `str_dup`.** `create_object` and `create_mobile` give an instance its
  prototype's strings by pointer, and extracting the instance frees them
  unless they sit in `string_space`. A `str_dup`ed prototype name was freed
  by the first OSTAT and read back as garbage. Editing a prototype string
  replaces the pointer with a new `str_perm` and never frees the old one.

## Loading Somebody Who Is Not Playing

**Use `offline_player_load()`, never `load_char_obj` on a raw name.**
Every command that changes a character who is not in the game -- the
stash's LINK/OF/TAKE, GRANTPSI, UNDENY -- goes through it: it takes only
2-12 letters (a typed `../area/area.lst` reached a file path and was
saved over), refuses anyone `player_in_game()` finds, and frees what a
missing file leaves. **`player_in_game(name, &logging_in)`, not
`get_char_world`, decides whether somebody is online**: `get_char_world`
asks `can_see`, so an unseen partner looked offline and was loaded a
second time -- an item duplication. A character at the password prompt
counts as in the game.

A loaded character's pet has no room until login places it
(`CON_READ_MOTD` does, as it did before November 2025). `save_char_obj`
keeps an unplaced pet, `nuke_pets` gives one a room before extracting
it, and `free_char` clears the stash and an unplaced pet of a copy that
never entered -- a wrong password, a reconnect.

## Travel Spells Keep Room Rules

`travel_spell_refuses(ch, room)` in `act_move.c` is what earth travel,
gate, the portal spell, astral walk and ENTER ask before carrying a
character anywhere, and what `random_travel_room()` -- recall misfires,
tornadoes, teleport traps -- picks against: another class's guild
rooms, rooms `guild_closed_rooms()` says a guard would turn this
character from, and Hyrule's order. Staff, newbie and private rooms are
`can_see_room` and the flags the spells already test. A new spell that
moves a character to another's room asks it too. Hyrule's check is
`hyrule_gate_check(ch, from, to, speak)`; WALKTO asks it silently through
`hyrule_gate_would_refuse` when choosing a route.

## WALKTO

`walkto <place>` (`src/walkto.c`) walks a player from wherever they are
to any destination in `area/walkto.dat`: the areas HELP WALKTO lists,
every guild hall, Melancholy the guild clerk, every guildmaster and
trainer, and the Temple. Staff may also give a room vnum. The pieces:

- **It finds the way again before every step**, with its own Dijkstra
  priced as the router prices it (a move or a portal one, a room that
  carries you eight), not `find_first_step` in `hunt.c` -- that walks
  six directions only, straight through death traps, locked doors and
  portals it cannot see. A door somebody shut, a room that filled up or a
  teleport that carried the walker are then just the next search, not a
  stale plan. Exits, free portals (`do_enter`), climb/crawl/jump objects
  (`do_manipulate`) and waits in teleport rooms are all ways through;
  portals that charge, levers and anything wanting a tool are not.
- **Every step is a real one**: `move_char`, `do_open`, `do_enter`,
  `do_manipulate`. Private rooms, guild guards (spec funs fire in
  `move_char`), boats, flying, movement points and Hyrule's gates all
  still apply, and a refusal ends the walk with the game's own reason.
  It opens doors that are shut but not locked, and named secret doors
  outside Hyrule, exactly as the published routes say to.
- **It never walks into a `ROOM_DT`**, not even as a destination:
  `walk_room_ok()` refuses one before asking anything else, and the step
  checks again. It also refuses ejectors, newbie rooms past level 10,
  other classes' class rooms, and every room `guild_closed_rooms()` says
  this character's guards would turn them from -- so a warrior asking for
  the Necro Guild Master is told only necromancers are let in, instead
  of being walked up to the guard.
- **Pacing is lag.** `walkto_update()` runs every pulse from
  `update_handler` and counts down the walker's own `ch->wait` (the input
  loop only does that when there is input), so a step costs
  `WALKTO_STEP_PULSES` (half a second) and any lag the walker carries.
- **It stops** on arrival, on any typed command other than WALKTO
  (`walkto_interrupt()` in the input loop, before `interpret`; a blank
  line does not count), on `walkto stop`, when a fight starts, when the
  walker is not standing, when moved by anything else (recall, summons,
  death, a leader) unless the room they left was one that carries you,
  on a refused step, on running out of moves, after
  `WALKTO_MAX_STEPS`, after two minutes waiting on a teleport, and on
  losing the link (`close_socket` clears it, so a reconnect does not
  resume). Nothing about a walk is saved.
- The whole route was not queued through `queue_alias_input()` because a
  queue cannot notice that a door is locked or a room is full until it
  has typed the next ten commands into it.

`walkto` alone fits one screen; `walkto trainers` and `walkto areas` page,
because they are lists asked for by name. `walk` and `wal` reach it; `wa`
is still WAKE.

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
tracks or the source writes. `toc-deploy` installs this script, with
itself, `toc-state-sync-check` and `toc-game-recovery`, at the end of
every deploy that comes back healthy -- see below.

**If the sync starts failing with "object file ... is empty"**, its
clone is corrupt. It was, from 08:09 to 10:47 UTC on 2026-10-01, and no
player save reached GitHub in that time. Move the clone aside and let
the script re-clone: `mv /srv/toc/state-repo
/srv/toc/state-repo.corrupt-<date>`, then start `toc-state-sync.service`
and check the journal says `pushed`.

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
`/run/toc-state-sync.status`, and a staff WIZINFO line, because the way
backups fail is quietly. **WIZINFO, never ANNOUNCE** (owner, 2026-10-04):
players can do nothing about a backup. It waits out a sync that is
running -- systemd zeroes the exit time while one is, which read as
"99999 minutes ago", and a deploy starts both timers in the same second
so they collide every fifteen minutes.

**`AUTOSAVE_CYCLE_TICKS` is the other half of the five-minute
promise.** Syncing every five minutes is pointless if the game only
writes a character's file every thirty, which is what stock ROM did.
`char_update` saves each playing character once per cycle, staggered by
descriptor so a full mud does not write every file in one tick.

## Where This Actually Runs

**The game runs on Oracle Cloud: an Always Free ARM (aarch64) Ubuntu
24.04 instance at `129.159.105.156`, which `toc.jeremybean.com` resolves
to.** It moved there on 2026-10-01. That address is a **reserved** IP, a
standalone resource that survives a stop or recreate of the instance --
so it outlives the box, and is deleted deliberately only when the whole
project is torn down. (The first few hours used an ephemeral
`129.213.53.66`, now released.) Both earlier hosts are gone --
before Oracle it ran on a Hyper-V VM on the owner's Windows desktop (now
powered off), and before that on a Raspberry Pi that died without
warning on 2026-09-29 -- and the characters were carried forward through
each move. Only Oracle is live: there is no VM to reach at `172.28.90.2`
and no Pi at `toc.local`.

### Connecting and shipping from a new session

On the owner's desktop, from **either shell** (PowerShell or Git Bash):

    ssh toc-oracle 'sudo /usr/local/sbin/toc-deploy'            # ship main
    ssh toc-oracle 'sudo /usr/local/sbin/toc-deploy --dry-run'  # build + validate only
    ssh toc-oracle 'systemctl is-active toc-game toc-web'       # is it up

`toc-oracle` is a host alias in `C:\Users\JeremyBean\.ssh\config`
(129.159.105.156, user **ubuntu**, key `~/.ssh/toc-oracle`). Wrap a
deploy in `timeout 1200` from Bash; it takes a few minutes. The whole
loop for any change is: edit, build both trees in WSL, run the relevant
test module, commit, `git fetch && git rebase origin/main && git push`,
then the deploy line above -- without asking (see the deploy rule below).

**Why the alias exists (2026-10-05).** The original key,
`C:\Users\JeremyBean\Downloads\oci_game_private_key`, is readable by the
`CodexSandboxUsers` group. Git Bash's ssh does not care, but Windows
OpenSSH -- what PowerShell runs -- refuses it ("UNPROTECTED PRIVATE KEY
FILE ... bad permissions") and then fails with `Permission denied
(publickey)`, which looks exactly like a server or key problem and is
neither. `~/.ssh/toc-oracle` is a copy readable by the owner's account
only; the Downloads original is left alone because Codex uses it. If the
alias is ever missing, `ssh -i /c/Users/JeremyBean/Downloads/oci_game_private_key
ubuntu@129.159.105.156` from **Git Bash** still works.

Three things a new session cannot get past, and should say so rather
than retry: a chat opened outside `C:\Users\JeremyBean\toc2026` loads
neither this file nor the project memory; a cloud or remote session has
no copy of the key at all; and the host's admin token never leaves
`/etc/toc/web.env` (read it there with `sudo`, never print it).

**A push to `main` is a deploy** (owner, 2026-10-05). `toc-auto-deploy`
runs on the host every ten minutes: when `main` carries code that is not
live and CI's Validate run for it has passed, it runs `toc-deploy` pinned
to that commit, with automatic rollback if the game does not come back
healthy. Docs, tests and state-sync commits never trigger it, and a
commit that failed to deploy is not retried until something newer lands.
So a session that can only push -- a cloud session -- still ships: push,
and the game updates about ten minutes after CI goes green (CI takes
about an hour). Put `[deploy now]` in a commit message to skip the CI
wait for an urgent fix; `toc-deploy` still refuses anything that does not
build or whose world does not load. A desktop session may still run
`toc-deploy` by hand for an immediate deploy; the two share a lock.

**A cloud session has HTTPS only** -- no SSH, no key, no project memory;
this file is all it gets, and the sandbox's proxy will not let it reach
`toc.jeremybean.com` either. It should edit, build both trees, run the
relevant test module, commit, and push straight to `main` after
`git fetch && git rebase origin/main` (no branch or pull request), then
check rather than assume:

- CI: `https://api.github.com/repos/jeremydbean/toc2026/actions/runs`
  (public, no auth).
- What is live: `log/deployed-commit` in git (the commit and when), and
  what the auto-deployer last decided and why: `log/auto-deploy.status`.
  The state sync carries both to GitHub within five minutes, so
  `git fetch` and read `origin/main:log/auto-deploy.status`.
- Reports: the synced `area/bugs.txt`, `typos.txt`, `ideas.txt` and
  `log/toc.log` stand in for the host's, up to five minutes stale. They
  carry player addresses, so filter IPs out of anything printed.

Recount world totals from the tools (`area_lint.py`, `merc --check-area`)
rather than copying a figure from a doc -- the baseline above was wrong
for a day because one was copied.

On the host: `/srv/toc/build` is the git checkout `toc-deploy` resets
and builds, `/srv/toc/current` the live tree it rsyncs into, units
`toc-game` and `toc-web`, plus `toc-state-sync`, `toc-state-sync-check`,
`toc-game-recovery`, `toc-auto-deploy` and `toc-daily-backup`, all in
`/usr/local/sbin`. `toc-deploy` installs the newer copies of the first
five, and the auto-deploy units, at the end of every healthy deploy.
`toc-auto-deploy` keeps its state in `/var/lib/toc-auto-deploy`
(`attempted`, `last.log`); `journalctl -t toc-auto-deploy` has its
history.
The SSH user is **ubuntu** (the VM used `tocadmin`; that is history).

`wiki/disaster-recovery.md` is the one page to read when something is
broken: what is down, how to deploy, whether the backups are working,
and how to rebuild on a new machine.

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

**The host's copies of the deploy scripts are installed at the end of a
healthy deploy.** This used to say an install step ran before the
restart; there was none. A fix to `toc-deploy` or the state sync sat in
git while the VM ran the old copy, and on 2026-10-01 that old
`toc-deploy` -- which did not list `dpsboard.txt` as runtime state --
copied git's benchmark board over the live one on every deploy,
discarding the day's best runs. Now `toc-deploy` installs itself,
`toc-state-sync`, `toc-state-sync-check` and `toc-game-recovery` from
the build tree once the game answers healthy, so a change to any of them
takes effect on the deploy that carries it, from the end of that run.

**The webadmin queue runs commands as a stand-in character with no
player data**, so anything that needs `pcdata` -- `dummy`, for one --
does nothing from it. Use it for `fsave`, `announce` and staff commands
that act on the world; do the rest in game.

`toc-deploy` exists because doing this by hand is how `area/custom.are`
went missing: it is tracked in git *and* listed in `area.lst`, so
treating it as a runtime file and excluding it left the game unable to
boot. The script carries the exclude list that is actually correct.

**It is a free-tier box, and that is the one soft spot.** The Oracle
account is still on the 30-day trial; upgrading it to Pay As You Go --
which keeps it $0 -- is what exempts an idle Always Free instance from
being reclaimed. A reclamation would lose nothing anyway: the state sync
(above) and `toc-restore` rebuild the game on a fresh box -- Oracle,
Linode, anything Debian-family -- in minutes, so a host loss here is an
outage, not a data loss. That is the whole point of the backup design.

**The old deploy appliances are dead history.** The scripts under
`deploy/` that name the Pi -- `install-pi.sh`, `toc2026-update`,
`pi.env.example` and the `toc2026-*` systemd units -- ran only on the
Pi, which advanced its checkout with `git merge --ff-only` (a tracked
file the game rewrites would block that merge). Neither the VM nor
Oracle works that way: `toc-deploy` resets the build tree and rsyncs it
over `current/`, and live state travels through the GitHub sync above.
Do not resurrect the Pi updater, `toc.local` or
`/run/toc2026/update.request` against any current host.

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

**Every player is watched by default** (owner, 2026-10-04, while the
changes settle): `fLogAll` starts true, and `player_is_watched()` --
flagged by name *or* covered by LOG ALL -- is the one test, used by
`interpret()`, `watch_log` and `char_to_room`. For a character watched
only by the default, `command_is_private()` withholds the words of
TELL, REPLY and GTELL: `log/` is published, and AGENTS' rule on private
messages holds. One flagged with LOG <name> is recorded in full.

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

**Every power starts at 1% until practised** (owner, 2026-10-04: trained
with Salir, as the awakening message says) -- a new one from
`psionic_learn` and one handed back after a remort alike. The restore
loops -- in `grant_psionics` and `psionic_restore_known`, which runs at
every login and on the first remort -- put back only what the wipe left
at 0, and at 1%. They read "below 75, make it 75", which at every login
raised a power granted at 1% to 75% without a practice spent. `psionic_owed_by_remorts`
tops up, at login, a character with two or more remorts holding fewer
than their due. The long awakening message is for new powers only
(`added` in `grant_psionics`).

**Hermie stands at the altar for six hours after every boot**
(`spellup_boot_place`, called from `main` after `boot_db`).
`TOC_NO_BOOT_HERMIE` skips it, and `tests/live_mud.py` sets it by default
because several tests count every spellup mobile; pass
`extra_env={"TOC_NO_BOOT_HERMIE": None}` to see her.

**A staff GRANTPSI is a promise; a remort's owing is a chance.** The
dice decide *when* a granted character awakens, but if they miss at 18,
19 and 20, level 21 pays the grant anyway (owner, 2026-10-04: Alaric was
granted and missed three rolls). The one-in-three who finish the band
with nothing are remort-owed characters only. *Superseded the same
night:* a pending grant now pays on the very next level gained, at any
level, before the band is consulted, and GRANTPSI no longer tells the
player anything.

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
- **A login re-rolled.** The login calls `do_check_psi`, so with the
  roll at the call sites a character inside the band could relog until
  it landed. The login call passes no argument now and only
  `"levelup"` rolls.

**Nothing psionic that speaks runs inside `load_char_obj`.** That
loader also builds characters for GRANTPSI, UNDENY and STASH LINK on a
zeroed descriptor whose output buffer is NULL, so the restore and the
remort top-up crashed the server there -- and for a real login they ran
at the name prompt, telling whoever typed the name. `psionic_login()` in
`stubs.c` does all of it, called from the nanny once the player is in
their room; only the silent `psionic_sync_known` stays in the loader.
The top-up there puts a pending GRANTPSI list aside so it is still the
next level's to pay. `grant_psionics` returns how many powers were new,
and GRANTPSI says so when it is none.
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

**The cap is a ceiling for both levels and remorts.** `gain_exp` stops
at `54 + num_remorts` or above, and `do_remort` refuses a character past
it (owner, 2026-10-04: remort does not work past the point you could
level to) and any immortal. Only staff ADVANCE puts somebody there.

**GAIN sells a spell only inside a group** (`do_gain`'s "You must learn
the full group"); a single name in a trainer's gain list works only for
skills. A spell a class can reach must therefore sit in one of its
groups, which `tests/test_necro_trainers.py` checks for necromancers.
Groups are re-applied by `gn_add` at login, so adding a member reaches
everyone already holding the group.

**A remort ends in the Temple**, and is refused from a jail cell for
that reason: it was allowed anywhere, so a level 54 could remort inside
a no-recall dungeon and be a level 3 among level 55 monsters. Charmed
followers other than the pet or mount are released and wander off, as
raised undead crumble.

**`char_from_room` only takes out a character who is in the room.** A
character loaded offline has `in_room` set but was never put there, and
taking them out drove the area's player count negative -- an area that
believes itself empty resets around the players inside it.

`ListRemorts` is unchanged on disk and is **not** a flat list of numbers.
It is written one life at a time as `<class>` alone for a monk or a necro,
who have no guild, and `<class> <guild>` for everybody else. Read it back
the same way -- class first, and only look for a guild token when the
class was neither monk nor necro -- or the pairs misalign. `none` (-1) is
always a legal guild, which is what guarantees a choice always exists.

## damage() Says Whether A Blow Landed

**Never branch on `damage()`'s result.** It is true for nearly every blow
that connects and for every blow a character deals themselves -- it is
not "the victim died". Reading it that way at more than twenty sites made
every multi-hit spell, trap and flood stop at its first landed blow and
skipped whatever followed a hit: the blindness, the stun, the lag, the
healing, the ingredients. Note the room before the blow and ask
`gone_after_blow(victim, room)` after it -- a killed mobile is extracted
(characters are pooled, so reading one is safe) and a killed player is in
the death room. `tests/test_damage_result.py` fails on any `if (damage(`.

`die_follower()` is stock ROM's again after a year as an empty stub, and
it is what keeps a follower from pointing at a character who has quit.
Raised undead (`MOB_VNUM_ANIMATE`) go with it: `dismiss_undead_servants()`
is called from `die_follower` and from `do_remort`, and `group_gain` pays
nothing for one whatever its charm says.

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

**Stealth and shadowmeld are invisible without holylight -- no roll.**
The owner's rule (2026-10-03). `can_see` used to roll a concealment
chance against the weather on every look, so a stealthed level 20 in
daylight was seen seven looks in ten and blinked in and out between two
LOOKs. Now only holylight and the Triforce, from the shortcut above, see
either; detect hidden does not. Getting the bit is still a skill roll,
made when STEALTH or SHADOWMELD is used, and a stealthed mobile that is
fighting shows itself, as a hiding one does. `tests/test_mob_stealth.py`
pins all of it; do not reintroduce a per-look roll. Faerie fog strips
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

**The archives reach git; a cleared file leaves it.** The state sync
copies every `<file>.<stamp>` REPORTS CLEAR leaves on the host, and
removes a report file from the repository once the host no longer has
one (`REPORT_FILES` in `toc-state-sync` -- the report files only; a
missing `custom.are` must never be deleted by a sync). Until 2026-10-03
the archives lived on the host alone and a cleared file stayed in git,
where `toc-restore` would have laid the cleared reports back down. The
old hosts' backlog, worked through in October 2026, is
`area/bugs.txt.20260929-151146` and `area/typos.txt.20260929-151146`.

The staff half is gated with `IS_TRUSTED(ch, LEVEL_IMMORTAL)`, not
`IS_IMMORTAL`. `is_note_to()` asks the same, so a builder trusted to
immortal rank receives notes addressed to `immortal` (the staff-trust
sweep; confirmed with the owner, 2026-10-05).

Other deploy facts:

- A deploy never takes player state from git. `toc-deploy` excludes
  `player/`, `gods/`, `heroes/`, the logs and the area runtime files and
  ships only code; **`toc-restore` is the only thing that lays live state
  down from git**, and only onto a fresh box in a disaster.
- `MUD_HOST` is where the web service dials (loopback, 127.0.0.1).
  `MUD_PUBLIC_HOST` is what the dashboard shows players; on Oracle it is
  set to `toc.jeremybean.com` in `/etc/toc/web.env`.
- The admin token lives in `/etc/toc/web.env` (mode 600, root) and is read
  with `sudo grep '^WEB_ADMIN_TOKEN=' /etc/toc/web.env`. Generate a
  replacement on the host with `openssl rand -hex 32` so the value never
  leaves it, then restart `toc-web.service`. Never paste it into a commit,
  an issue or a conversation.

## Compare And The Gear Finder

`src/gear_compare.c` (COMPARE) and `get_best_gear` in `webadmin/server.py`
(the website's Gear Finder) answer the same question -- which gear makes
you hit harder -- and must keep agreeing on what counts as gear:

- **Damage first.** COMPARE scores damage change plus a quarter of the
  toughness change (`GEAR_TOUGH_WEIGHT`). A caster's damage is mana to cast
  with, because spells cast at `ch->level` and gear changes only how many
  casts there are. `tests/test_gear_finder.py` pins the website's version
  of the same order in both directions.
- **One slot per item, the one WEAR picks**: the first of its wear flags in
  `wear_obj`'s order, and a light is always a light.
- **Race flags name everyone an item suits** (`wear_requirements_met`), and
  apply only when `ITEM_RACE_RESTRICTED` is set.
- **Obtainable means a G or E reset on a mobile**, minus rot-death gear,
  inventory-flagged gear on a non-shopkeeper, staff rooms, and Mud School
  past newbie level. A level -1 prototype comes out at the carrier's level
  less two (a shopkeeper's by item type), capped at 52, with
  `dice_thrown`/`dice_size` dice -- the dashboard keeps its own copy of
  those tables.
- **COMPARE UPGRADES never calls `create_object`.** It builds a stack
  `OBJ_DATA` from the prototype, because a real object joins `object_list`,
  counts against limits and advances max-load state, all for a figure.

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

## Hunters And NO_MOB

A hunting mobile stops at the edge of a `ROOM_NO_MOB` room exactly as
it stops at a `ROOM_SAFE` one (`hunt_victim` in `src/hunt.c`).
Wandering has always refused NO_MOB; hunting asked only about SAFE, so
city guards hunting a WANTED player -- `spec_guard` attacks one on
sight, and a guard that has fought somebody hunts them -- followed
their quarry to the Temple altar, which is NO_MOB and not SAFE, and the
Temple filled with guards. `tests/test_hunt_no_mob.py`.

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

`src/dummy.c`. Mob 2400 in room 2419 (`area/dummy.are`), reached on
foot: down from the centre of the Oak Tree Square to the Entrance to
the Hall of Heroes (4649), then south. North walks back out. Every rule
below was either asked for by the owner or found broken live; keep
them.

**Check a public place by walking it as somebody who is not in a
guild.** The yard first opened through a portal in the Grand Knight's
Sparring Room, inside the Citadel of War, where a Guild Guard
(`spec_guild_guard`, mob 4400) turns away everyone who is not a
warrior. `tools/build_directions.py` does not model guards, so it
published a route nobody else could walk, and the route looked fine.

- **One fighter at a time.** The yard is `ROOM_SOLITARY` with
  `ROOM_ARENA`. `room_is_private()` counts mortals only and
  `can_enter_private_room()` lets immortals in, which is the rule.
  Walking in goes through `move_char`, which asks it and tells a second
  mortal somebody is training. `do_enter` asks it too, **before a
  portal's fare** -- portals used to be the one way into any private
  room in the world that never asked.
- **North is the way out**, and the yard is not `ROOM_NO_RECALL`.
- **A run never heals.** Hit points, mana and moves are snapshotted
  at the first blow and put back at the stand-down -- never set to
  max, or the yard is a free heal for anybody who walks in half dead.
  `dummy_left_yard()` in `char_from_room` puts them back on any way
  out mid-run, because a snapshot carried out could be cashed in later.
- **It cannot die, by any route.** The guard in `damage()` only covers
  blows; a fatality, a death ray or a slay goes straight to `raw_kill`,
  and a fatality backstab killed it. `raw_kill_internal` refuses the
  dummy and stands it back up, and backstab never rolls a fatality on
  it, because `fatality()` pays `group_gain` before it kills.
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

HELP DUMMY's walking directions are pinned to the generated route by a
test, so moving the yard and forgetting the help fails the build. The
area is named Training Dummy Yard so the Mudlet walker's name match
finds it from WALK DUMMY.

The quest master excludes the yard by file name beside Hyrule
(`QUEST_EXCLUDED_YARD`): the dummy cannot die, so a quest to kill it
could never finish.

## Completion Standard

A task is complete only when the requested behavior or documentation is
implemented, relevant tests pass, the diff is reviewed, and any limitation or
unrun test is reported. Do not leave required long-running test/server sessions
unattended at final response.
