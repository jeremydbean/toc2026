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
- `wiki/player-backups.md`: snapshots, corpses, PRESTORE, and restores through git
- `wiki/game-client-guide.md`: browser terminal, ANSI, paging, and client controls
- `wiki/install-guide.md`: one-command installs (Docker or native), updates,
  backups, promote, uninstall -- for anyone running their own copy
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

Installed copies (Docker by default, `--native` without it):

```bash
./install.sh --skip-prerequisites      # or --native
./toc.sh status
./toc.sh logs
./toc.sh stop
```

Windows uses `install.ps1` and `toc.ps1`. Docker Compose binds both ports to
loopback by default; `--public`/`-Network Public` exposes only the game port.
Compose uses `restart: unless-stopped`, so use the launcher `stop` command when
the container must remain off. See "The Installers" below for what they
depend on.

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
2,498 mobiles
3,722 objects
7,786 rooms
0 critical, 12 warning, 1,648 information findings
```

The October 2026 fidelity audit's enemy corrections added generated
Hyrule enemies for kinds new to their band (darknuts in Levels 5 and 8, zols
in Level 4); the mobile count was 2,496 before them and the Hyrule maze copy
30756 went with the maze fix. Hyrule's cleared-room rewards (2026-10-26) added eight
`object-has-no-source` findings: both boomerangs, two maps and four
compasses are made by `hyrule_room_cleared` when a room's enemies die, not
by a reset (`CLEAR_REWARDS`). Small keys are laid out in other rooms too,
so they stay sourced. The count read 1,640 before them.

The achievement trophy REDEEM hands out (object 95 in `limbo.are`,
2026-10-25) added one object and one `object-has-no-source` finding: only
REDEEM makes it. The mobile count and two information findings had moved
before that without this baseline following; recount, do not copy.

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

**The full suite is about 250 module-minutes, and the maintainer does not
want it run routinely.** 216 modules, 1,553 tests (2026-10-25); around 110
modules boot a real server that parses every area file (the generated
Hyrule alone is 446 rooms and 1,519 resets), and `tests/live_mud.py`'s
`drain(n)` sleeps its whole window. No single module is the floor any
more: `test_hyrule_walkthrough` took ten minutes in fixed windows and
takes under four synced (2026-10-25); the slowest now run five to seven.
`tests/ci_durations.json` holds every module's measured time.

**CI runs what a change needs, and the policy is `scripts/ci/classify.py`**
(2026-10-25). The `plan` job sorts every changed path: state the game
writes (nothing to run), documentation (the cheap checks, plus any test
that holds a document to the code -- the achievements catalog, the install
guides; the five wiki pages the Oracle reads are dashboard content), the
browser client's static files (its browser and web tests), the dashboard's
Python (the modules that use it), test modules alone (those modules), and
everything else -- C, headers, area and generator data, scripts, the
harness (`tests/live_mud.py`, `tests/fixtures/`, `scripts/ci/`), CI and
deploy policy, dependencies, and any path the policy does not name -- the
full suite with the sanitizer and serial jobs. No base, an unreadable
diff, the nightly run and a manual run with "full" ticked are full.
`tests/test_ci_classify.py` plays the policy.

**The comparison is with the last commit CI vouched for, never the push's
parent.** `toc-auto-deploy` ships a code commit on a passing run of any
commit built on it, so a docs commit pushed on failing code must not pass
on a docs-sized check. The plan diffs from the newest commit on main, an
ancestor of this one, whose push run's `deploy-gate` passed -- which puts
the failing code in this run's diff, and its full suite in this run. That
is an induction: a commit passed either by running everything or by
changing nothing at run time since one that did. The plan also records a
fingerprint of the deployable tree (the paths `toc-auto-deploy` calls
code; the two exclude lists are held together by a test), and a class
that claims no runtime change while the fingerprint moved is promoted to
full. Pushes to branches no longer run at all: a branch is validated by
its pull request, main by its push.

**A full CI run (`.github/workflows/validate.yml`) takes about ten
minutes** from push to verdict: 9.7 minutes and 87 runner-minutes on the
first run of the planned pipeline (Validate run 40241317306, 2026-10-25),
its eight shards finishing within sixteen seconds of each other (476-492
s). The split pipeline before it took 11.4 to 14 minutes and 95 to 117
runner-minutes (runs 40210613754, 40229059412, 40231173630); the single
job before that, 67 minutes at the median, for 89 runner-minutes. The jobs, all on free `ubuntu-24.04` runners (pinned,
like production: `ubuntu-latest` moves to 26) and as parallel as GitHub
allows:

| job | what | time |
| --- | --- | --- |
| `plan` | `classify.py`: what this change needs, against the trusted base | 20 s |
| `quick` | `validate.sh quick`: py_compile, the Mudlet map and seasonal areas `--check`, the area validators, whitespace. Every test job waits for it: a failed preflight launches no matrix (a manual "diagnostic" run overrides that, and the gate still fails) | 12 s |
| `build` | `validate.sh build`: GNU89 Make with strict warnings, world load, recovery scenarios, list iterator, smoke; then strict C17 CMake and its world load. Hands `merc` on. | 1 min |
| `build-sanitize` | ASan/UBSan CMake build, world load and a 45 s idle under them. Hands `bin/rom` on. | 1.5 min |
| `tests` (x8 at most) | the planned modules but the serial ones, in duration-balanced shards (a partial plan uses as few as fit it), four at a time, against `build`'s binary | 6-8 min |
| `tests-serial` | `test_login_throttle`, alone, beside the shards | 1 min |
| `sanitize-tests` (x3) | `SANITIZE_MODULES` against the sanitizer binary, two at a time | 7 min |
| `deploy-gate` | the verdict (below) | 10 s |

A shard still going at fifteen minutes is late; at the job's own
`timeout-minutes` it is cancelled, which fails the gate. Read the job's
step summary before concluding anything: each shard and the gate publish
a table of modules, times, skips and failures.

**`deploy-gate` is the only thing that says a commit is good, and
`toc-auto-deploy` reads that job by name.** It runs whatever the jobs
before it did (`if: always()`) and passes only when the plan is the one
this commit deserves -- for this commit, standing on a trusted base, and
exactly what classifying again from that base gives (`verify_plan`) --
every job the plan needed succeeded (a job it did not need may be
skipped; GitHub calls a skipped job a success, so job results alone
prove nothing), every module the plan selected ran exactly once (in one
shard or the serial job -- a module lost or run twice is named) in
results that name this commit, each planned sanitizer module ran once,
every module passed, and no test skipped for a reason
`tests/ci_allowed_skips.json` does not explain. A skip in CI
usually means something CI was meant to provide is missing -- the binary,
Node, Lua, fastapi -- so a skip fails the gate unless a rule there names
the module, the test and the reason and says why. Its first run failed on
exactly two: a test that skipped itself when a guard died too soon (fixed
to fight the training dummy) and the disk-full test, which needs a
private tmpfs and now gets one through the runner's passwordless sudo.
Rename the job and the deployer stops deploying until both change.

**The runner is `scripts/ci/run_tests.py`; `scripts/test-parallel.sh` is
a wrapper for it.** Each module runs in its own process group under
`scripts/ci/run_module.py`, which writes a record of every test (outcome,
time, skip reason, full traceback, subtests by name); a module with no
tests is an error. A module past `--module-timeout` (20 minutes) is
killed with its whole group, servers included, and so is everything when
the runner gets SIGINT or SIGTERM (a cancelled job), which reports
`cancelled`, never a pass. Test servers also die with their test process
(`PR_SET_PDEATHSIG`). `--artifacts` keeps, for each failed module, its
log, the server's output, the clients' transcripts and the test world's
own `log/` -- synthetic fixtures only, never a real player file.

```bash
scripts/test-parallel.sh                      # everything, every core
scripts/test-parallel.sh test_stash           # just these
JOBS=4 scripts/test-parallel.sh               # gentler on the machine
python3 scripts/ci/run_tests.py --plan 8      # how CI would shard it
python3 scripts/ci/run_tests.py --shard 3/8 --serial-mode exclude --list-plan
```

The shards are planned longest first onto the least loaded, from
`tests/ci_durations.json`, deterministically, so each shard job computes
the same plan and none can drift from another. Refresh that file from the
`ci-durations` artifact the gate uploads when the shards drift apart; a
module it does not know is costed at the median, and every module at
least two seconds.

**It runs from the repository root, and that is load bearing.** A third
of the modules reach for `src/`, `area/` or `import webadmin` relative to
the root; `python -m` puts the working directory on `sys.path` and
`discover -s tests` adds `tests/` so `import live_mud` still resolves.
Running from inside `tests/` -- which is the obvious way to write it --
fails eleven modules with import and file-not-found errors that look
like product bugs and are not.

**`test_login_throttle` runs on its own.** Its tests measure against the
wall clock, so a dozen servers competing for the same cores make them miss
a window and time out waiting for "wrong password". They were part of
`test_live_gameplay`, which held the whole six-and-a-half-minute module to
a runner of its own for one minute of timing; the rest of it runs in the
shards now. `SERIAL_MODULES` in the workflow (`--serial` to the runner)
names the modules that get a machine to themselves -- in CI their own
job, beside the shards rather than after them; locally a tail after the
rest. Add to it only for a real timing dependency, not to quiet a flake
with a cause.

**`LiveMud.drain(seconds)` sleeps its whole window on purpose.** Making
it return early when the game goes quiet is the obvious speedup and it
was tried in 2026-09: `test_recall_point` then failed with an `affect`
reply that arrived as an empty string, because output comes in bursts
with gaps in them and a drain that stops at the first gap returns before
the reply. When a test needs to know a command has been answered, use
**`MudClient.sync(line)`**: it types a barrier (TIME), the line, and the
barrier again, and returns what came between the two answers. The game
answers a descriptor's commands in order, so everything the line
produced is in hand, however long its lag held it, and nothing sent
before it began is counted as its reply. TIME, not WORTH: any position
may type it (WORTH is refused to the mortally wounded) and a switched
immortal gets the same answer. The barrier is typed input, so it counts
down lag and is logged; never sync a command whose test proves something
happens with nothing typed after it -- WIMPY's flee after KILL is listened
for with `expect()`. `MudClient.must(line, *expected)` is sync that fails
unless the reply says what the command was for. Output that arrives
later on its own -- a tick, a wandering mobile, the result of lag
counting down -- is not covered; assert on what the command says.

**A test that cannot run here skips; a test that had bad luck must not.**
Five tests used to skip themselves when the world was unlucky (no quest
target, nothing fought back) or on a harness condition that never
happens; in CI each was a pass that tested nothing. Make the luck
deterministic (the training dummy cannot die; give a fixture
infravision rather than hope it is daytime) or assert. The gate fails
the skip either way.

**A sanitizer report fails the test whose server wrote it**, teardown
included: `LiveMud.__exit__` reads the server's output after stopping
it, and raises if an ASan/UBSan/LSan report is there (or prints it
beside a test that already failed). `LiveMud(expect_crash=True)` is for
the one test that crashes a server on purpose.

CI's other conveniences:

- **Superseded runs are cancelled** (`concurrency` with
  `cancel-in-progress`, per ref; the nightly and manual runs have a group
  of their own). A docs commit that cancels a code run in flight does not
  lose it: the docs commit's plan diffs from the last vouched-for commit,
  so it runs that code's full suite itself. Do not reach for `[skip ci]`
  to save a run -- the classifier is what makes a docs commit cheap; the
  state sync's `[skip ci]` is its own belt to `paths-ignore`.
- **A full regression runs every night** (`schedule`) and by hand
  (Actions -> Validate -> Run workflow, "full"); "diagnostic" runs the
  tests even when the cheap checks failed, and the gate still fails it.
- **Failures are announced as they happen**: the runner writes a GitHub
  annotation the moment a module fails -- the module, the first failing
  test and its message, and where its artifacts will be -- not only when
  the shard ends.
- **A job installs only what it is missing** (`scripts/ci/install_deps.sh`):
  a package the image carries costs nothing, a missing one is installed
  from the image's lists and only then are they refreshed, and the time
  goes to the step summary. `lua` is installed only on the shard that
  runs `test_mudlet_assets`. One shard once spent 292 s in `apt-get`.
- **ccache**, because `validate.sh` opens with `make clean` on
  purpose -- stale objects have bitten this codebase before -- and the
  cache is what stops that costing a full rebuild every time. The
  Makefile's `CC` is `?=` so the workflow can point it at ccache;
  making it `:=` again silently disables this.
- **Each binary is built once per run** and handed to the jobs that test
  it as an artifact, so every shard tests the same `merc`.

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
- **Lag counts down only while a command is waiting** (`comm.c`, the
  `ch->wait` check in the input loop) -- except in a fight, where
  `fight_lag_update` counts it every pulse -- so `drain()` after a
  lagging command outside a fight burns none of it: the next command sits out the whole lag
  before it runs, and its reply window has to hold both. A 3-second
  window after the recorder's whirlwind (`PULSE_VIOLENCE`, 3 s) failed
  `test_hyrule_walkthrough` in CI twice running on 2026-10-06 with an
  empty reply, and passed every time locally.
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
- **A client only reads its own socket while it drains.** In a two-client
  test the hero's death message is not in `hero.transcript` after
  `run(keeper, "slay zhoarder")`: nothing pumped the hero's socket. Drain
  the client whose output you assert on.
- **Test worlds have no random disasters** (`TOC_NO_DISASTERS`, set by
  `tests/live_mud.py` beside `TOC_NO_GOBLIN`; DISASTER still works). An
  earthquake stunned a level 20 fixture in the Temple mid-test in CI on
  2026-10-23 -- "You are too stunned to do that." -- which is what
  started the rework below. A low-level fixture at a few hit points with
  no fight is the sign.
- **A mobile a test loads may walk away -- use the fixture world.** The
  Korzath security guard (29012) six tests fought is WIMPY and STAY_AREA,
  and on a busy runner it left the room between LOAD and the first KILL
  or CAST often enough to fail three modules in one afternoon
  (2026-10-25: "They aren't here"). `set mob 29012 act +sentinel` was the
  advice here, and it never worked: SET MOB refuses every prototype that
  came with the game, and the tests checked only that the reply lacked
  "Syntax". `LiveMud(fixtures=True)` loads `tests/fixtures/area/ztestfix.are`
  into the test world (rooms 32700-32705 joined to nothing, a sentinel
  sparring guard, mob 32700) and `place_sparring_guard()` loads it and
  proves with STAT that it stands where it was put.
  `tests/test_fixture_hygiene.py` fails on the old habit.
- **Confirm a setup command by what it says, not by a missing error.**
  `MudClient.must(command, *expected)` syncs and fails unless the reply
  names one of `expected`; `room_of()` reads a character's room from
  STAT. `set char <x> hp N` sets the *maximum*: RESTORE brings them to it.
- **`sync` cannot follow a character who cannot type WORTH.** WORTH needs
  POS_SLEEPING; a character a trap leaves mortally wounded is answered
  "You are hurt far too bad for that." and the barrier never comes. Pass
  `barrier="time"` (TIME is POS_DEAD). And never sync after a command
  whose test proves something happens with nothing typed after it --
  WIMPY's flee after KILL is listened for with `expect()`.
- **A stinking cloud lasts one to three ticks** (`raf->timer = dice(1,3)`)
  and can blow away a moment after it is raised; a test proves it stood
  through a move by finding it still there afterwards (`stat room`), and
  counts only the gas inside the move's own burst of output, prompt to
  prompt, since the cloud also gasses its room every tick in the same
  words (`tests/test_trap_movement.py`).
- **The test servers append to tracked runtime logs.** A module run from
  the repository root leaves `log/webadmin-events.tsv` and `log/toc.log`
  modified, and `git rebase` then refuses with "unstaged changes". Check
  them out before rebasing; they are never part of a change.

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
- `src/build.c`: in-game building in words -- SET MOB/OBJ <vnum>, MSHOW, OSHOW, PLACE/RESETS/UNPLACE, BUILD,
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
  an id -- the counts are kept by id. A change only staff can use is
  headed `@ <id> <date> staff` and shown to staff alone, marked "(staff
  only)" (owner, 2026-10-23: immortal changes stay out of the players'
  list); never put the creator rank in either.
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
  `split_typed_commands()` in `comm.c` (quotes and `\;` keep a
  semicolon), with the rest queued through `queue_alias_input()` -- so a
  chained command is not alias-expanded either. A line whose first word is
  ALIAS, UNALIAS or a password command is never split.
  **The browser consoles send a typed line whole and let the game split
  it** (audit, 2026-10-21). They used to split it themselves and send the
  pieces, and the game split each piece again: `say left\;quit` quit, an
  ALIAS body was cut at its first semicolon, and a BUILD answer or a
  password became two commands. `TocCommandSequence.encode` in
  `webadmin/static/command-sequence.js` returns the line to send; only
  the play client's own aliases make it rebuild one, escaping every
  literal semicolon. Generated routes still go a command a frame
  (`sendCommandSequence`): they hold none of those and can run past the
  game's 20 commands a line.

## C Change Rules

- Match surrounding GNU89-compatible style even though CMake also compiles as
  C17.
- Add new source files to `CMakeLists.txt`; Make globs `src/*.c`, CMake does not.
- Add declarations in the established header and avoid implicit declarations.
- Use `snprintf`, `toc_strlcpy`, and `toc_strlcat` with the true destination
  size. Do not add `sprintf`, `strcpy`, or unbounded `strcat`.
- Use `UNUSED_PARAM(x)` for intentionally unused parameters.
- Preserve game output line endings (`\n\r`).
- **Every string the game sends is ASCII.** Clients are told ISO-8859-1
  and the web client decodes Latin-1, so a UTF-8 em dash reached players
  as `â€"` (56 of them, found in the logs 2026-10-21). Write `--`.
  `tests/test_source_ascii.py` fails on any byte above 127 inside a string
  literal; comments may hold anything.
- Use `send_to_char()` for immediate player text and `page_to_char()` for
  scrollable output. Both paths convert canonical `{HH}` color tokens; do not
  send raw player-facing color markup through `write_to_buffer()`.
- **Colour tokens are `{` and two hex digits, anywhere they appear.**
  Area names open with a level range in braces (`{30 50}`), so show one
  through `area_shown_name()` or the range is eaten. `act()` converts
  tokens in substituted text (`$t`, `$p`) as well as its format and
  capitalises past leading escapes; a slot set to plain emits a reset;
  cut player text with `color_truncate()` and close a coloured title with
  `color_close()`. A login never overrides a saved COLOR OFF.
  `tests/test_ansi_color.py`.
- **The COLOR palette is saved by index** (`Color <slot> <index>`), so
  `col_disp_table` in `color.c` only ever grows at the end: the 256-colour
  names (2026-10-23) follow `plain`. A new name needs its xterm value in
  the Mudlet package's `GAME_COLOUR` too (rebuild the package). A raw
  escape sent to a player asks `color_is_enabled()` first --
  `send_to_char` strips tokens, not escapes. The web consoles draw 0-15
  from their themes and 256-colour and true colour exactly
  (`ansi-fg-rgb` with an inline `--ansi-fg`); reverse video swaps the
  `--ansi-fg`/`--ansi-bg` properties every colour rule sets
  (`tests/test_ansi_web.js`).
- Both web terminals use `TocConsoleOutput` in `console-output.js`; keep the
  ANSI/Telnet state machine shared. `reset()` starts a new connection and exits
  password mode; `resetStyle()` clears display state without touching Telnet or
  password masking. The player client's Clear uses only `resetStyle()`. Control
  strings are never transcript text. Update all three Mudlet version strings
  and rebuild the package when its script changes, so existing clients upgrade.
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

**A refusal is not a miss** (owner, 2026-10-13). When a skill cannot work
-- a pickproof lock, a steal from somebody five levels above you, a
backstab on a victim under a third of their health -- say why, before any
roll, in words a missed roll never uses. PICK answered a pickproof door
with the same "You failed." as a missed roll, with the roll made before
the door was even looked at, and a thief at 75% spent 150 attempts on
three such doors before filing a bug; 165 of the 229 doors a reset locks
are pickproof, so that was most of the skill. A missed roll is a fumble
now, told one of several ways (`pick_lock_roll_fails` in `act_move.c`,
STEAL's four in `act_obj.c`, RECALL's `recall_miss_message`), and the
refusals have their own lines. `tests/test_pick_lock.py` plays a
pickproof door, a fumble at 0% and a pick at 100%. The spells' and staff
commands' "You failed." are not this pattern and were left alone.

**A miss is not a lie, either** (2026-10-20). TRACK answered a missed
roll with a random direction in the same words as a found trail, and
HIDE said "You attempt to hide." whichever way the roll went; the logs
show players repeating both to find out. Say which it was.
`tests/test_player_frictions.py`.

**A player help topic is level 0.** A level from 1 to 59 on a help hides
it from every mortal below it, and a remort is level 3 again with all
its powers. Only a topic describing a command or channel the reader
cannot use below that level keeps a gate (`ALLOWED_GATES` in
`tests/test_help_keywords.py`). A group's own name is answered from
`group_table` when no topic matches (`help necro maladictions` lists the
members), so do not add a group's name as a keyword to a written topic.

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

**What was inside a vanished container is kept, not lost.** The loader
frees its placeholder for a vnum it cannot find, but the `Nest` key had
already pointed `rgObjNest` at that placeholder, so the objects saved
inside were linked into freed memory -- lost at best, and in the test
world the login hung at the name prompt (2026-10-14). The incomplete
branch clears the slot now and a nested object whose parent slot is
NULL falls back to the character, or the stash when reading one, with a
"kept loose" log line. `tests/test_lost_containers.py` loads a gone
container holding a bag holding bombs, in both places.

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
there, which holds the dungeon's Triforce piece (Ganon's, the Master Sword
too: `CHEST_PRIZES`). The next dungeon's entrance asks for the piece and its
guardian's chamber for a tool found in an earlier dungeon, through
`hyrule_progress_gate` in `act_move.c`, asked per character by `move_char`
and `do_enter` -- never a door somebody else can hold open. The tools lie
where the NES keeps them (2026-10-25): the cellars under block stairs
(`MAJOR_ITEMS` in the manifest builder) and the goriyas' rooms for the
boomerangs (`DIRECT_DUNGEON_ITEMS`); `TOOL_SOURCES` in the generator names
each. The generator's `TOOL_SOURCES`, `ENTRY_NEEDS` and `GUARDIAN_NEEDS`,
that C table, and the plan table in `wiki/hyrule-area.md` must say the same
thing; `tests/test_hyrule_progression.py` checks them against each other and
the area file. Pieces are treasure, not keys,
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
- **A cleared room's item is given once per reset** (review, 2026-10-26).
  `raw_kill` reads `hyrule_foe(victim)` before extracting it and passes
  it to `hyrule_room_cleared`; nothing else dying clears a room, and
  `hyrule_reward_issued[]` holds each `hyrule_clear_rewards` row given
  until `reset_area` puts a foe back in its room
  (`hyrule_room_populated`, from the `M` reset). Before, any mobile's
  death in a cleared room laid the item again once it had been picked
  up (`tests/test_hyrule_clear_reward_once.py`).
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

## Help

`tools/help_audit.py` holds the help to the game (help audit,
2026-10-27); `tests/test_help_audit.py` runs it and
`tests/test_help_live.py` checks the game's own HELP picks the same pages.

- **One reader.** `webadmin/help_index.py` reads help as `load_helps` and
  `do_help` do: `area.lst` then `built/built.lst` order, Latin-1,
  `fread_string` tokens, a quoted phrase one keyword, exact before prefix,
  nothing above the reader's trust. The website, the Oracle and the audit
  all use it; never parse help with a line regex again (the old loader
  globbed and sorted files, split quoted phrases and skipped wrapped
  headers, so HELP STONE SKIN worked in game and 404ed on the website).
- **One page per topic.** `commands.are` loads first, so an exact keyword
  there shadows any later page: a command page and a skill page for the
  same word means the second is never read (fifteen psionic and twenty
  skill pages had invented `commands.are` copies). A commands page that
  RULES, NEWS or STORY's `do_help(ch, "<name>")` lands on must be the
  content, not a description of the command.
- **A shared keyword is listed with a reason** in
  `data/help_coverage.json`: `alias`, or `staff-first` -- a staff page and
  a public page sharing a word, the staff page earlier in the load order
  so staff get it (GOBLIN, FARSLAY, INVIS, TELEPORT, EMPOWER, TITANIC).
- **Class level tables and KEYWORDS are generated**: `--write-levels`
  rewrites every `Mage:.. Cleric:..` minimum-level line on a spell or
  skill page from `skill_table`, `--write-keywords` the KEYWORDS topic.
  Never hand-edit either.
- **HELP GROUP <name>** answers a group from `group_table` before any page
  (`help_group_exact` in `act_info.c`), for a group a command shares a
  name with (WEATHER).
- `db.c`'s `help_fold_keyword` folds a header that wraps a line into one
  line; `help_keyword_exact` matches a quoted keyword whole.

## Achievements

`src/achievements.c`; the player guide is `wiki/achievements.md`, whose
catalog table `tests/test_achievement_expansion.py` holds to the source.
378 entries since the 2026-10-25 expansion (owner: about 175 new ones).
Rules the code depends on:

- **The table is append-only.** Earned achievements are saved by key
  (`Achv <key> <time>`) and indexed by position at runtime, so never move,
  rename or reuse a row; add at the end. `MAX_ACHIEVEMENTS` is 512 and
  `achievement_table_must_fit` fails the build past it.
- **A meta counts an explicit list** (`cohort_*` and `achievement_cohorts`).
  The five `_v1` lists are the original metas frozen as they stood on
  2026-10-24 -- Boss Hunter, Conqueror of Chaos, the relic metas, Artisan of
  Chaos, Death Becomes You, Hero of Hyrule -- and must never change, or
  adding a boss would quietly change what "every listed boss" asks. A new
  meta gets a new list; a visible meta never names a hidden member in its
  description (search would find it).
- **New state is saved by name**: `AchCount <name> <n>`, `AchSet <name> <id
  or a-b> ... ~`, `AchSpent <spent> 0`, all under case 'A' of `fread_char`.
  Add a counter to `achievement_counter` and its name to
  `achievement_counter_names` together; the same for sets. An unknown name
  is read and dropped. Sets are heap arrays freed by `achievement_free`
  from `free_char`. Counters start at zero: nothing is backfilled that the
  save cannot prove. **A set token is read strictly** (review,
  2026-10-26: `AchSet rooms 9223372036854775807` overflowed the range
  loop's increment under UBSan): `achievement_set_token` takes digits or
  digits-digits, no sign or trailing text, no `ERANGE`, nothing past the
  set's `achievement_set_max_id` (an int for vnums and area ids), and
  `achievement_set_insert` refuses the same. The range loop stops at its
  last value instead of stepping past it, one line tries at most twice
  the set's limit of ids, and every token is read to the `~` -- it used
  to stop at 20,000 and leave the rest for `fread_char` -- though only
  the first 20,000 are looked at. The writer asks for the next id only
  below `LONG_MAX`. `tests/test_achievement_set_load.py`, also in
  `SANITIZE_MODULES`.
- **Award at the success, never at the command**, and staff earn none of
  the new feats: `ACH_STAFF` is `IS_TRUSTED(ch, LEVEL_IMMORTAL)`, and
  `achievement_unlock` refuses an expansion row (from `goblin-kills-1`
  on) to staff, because the login catch-up and the state checks never
  asked (review, 2026-10-26; `tests/test_achievement_staff.py`). Rows
  before the expansion keep their old rule; nothing earned is removed. Party
  awards (`achievement_party_count`/`_event`) reach the credited player and
  their group in the room, mortals only.
- **A boss row with a negative auxiliary** matches a death anywhere in that
  room's area (Prince Starfire is WIMPY).
- **List views are cut into parts** of `ACHIEVEMENT_PART_BYTES` raw bytes so
  a part, colour converted, fits the pager's 32,000-byte block; a hidden
  achievement not yet earned matches no search.
- **Marks** are points less `achievement_marks_spent`; REDEEM sells only
  cosmetic and convenience perks (owner, 2026-10-25), and its spend rolls
  back with the earned set in a PRESTORE.

## Crafting

BREW, CONCOCT and SCRIBE share one table, `craft_recipes` in `magic2.c`,
matched by `craft_find` in any order. Every refusal (missing or wrong
ingredient, a combination that makes nothing, an herb with no brew) comes
before the roll and costs nothing; a real attempt pays the skill's beats
(12) first; the product is the crafter's level. A recipe's identity for
the recipe-book achievements is its method plus its `signature` spell,
which must be one of its spells and have a real `spell_fun`
(`tests/test_achievement_expansion.py`). `count_components` counts only
`ITEM_SPELL_COMPONENT`: objects 74 and 75 (the crafted tea and potion) sit
in the component vnum range, and counting them once stopped components
spawning anywhere.

**A craft is on the disk or undone** (review, 2026-10-27).
`craft_commit` takes the ingredients out and puts the product in, saves,
and reads the status: `DURABLE_FAILED` puts memory back to match the old
file (ingredients in the pack, no product, the player told);
`DURABLE_UNCERTAIN` keeps the new state, since the file may already be
it, and says the next save confirms it. Nothing is extracted before the
save answers. A CONCOCT failure commits its ingredients **before** the
blast, so a fatal one leaves them in no corpse, and an undone one does
not burn. Every attempt writes a `craft` row to `log/play.tsv`
(`craft_audit`: attempt id, method, signature, colour, input and output
vnums, spells, cast level, skill, chance, outcome, burn, saved,
unconfirmed or undone; a wizinvis crafter's name is `-`). `PREVIEW` as
the first word asks the same matcher and makes nothing. A recipe names
spells by exact name (`craft_spell` has no prefix fallback), a quaffed
product carries no object or offensive spell, a scroll with an object
spell carries only those, and no recipe holds two spells that refuse
each other -- the ironbound scroll's stone skin and shield stopped its
own major globe (`tests/test_crafting_review.py`). RECITE refuses the
scroll as its own target and an object the reader does not carry before
the lag, and recasts each slot only at what is still there.

**TITANIC and EMPOWER are object-only spells** (owner, 2026-10-25). Their
skill rows sit at level 72 for every class -- `set skill all` and casting
both pass over them -- with real `spell_titanic`/`spell_empower` so a
crafted potion or scroll can carry them. The staff commands, Hermie and
the spells all go through `titanic_apply`/`empower_apply` in `act_wiz.c`;
change an effect there, once. A crafted one lasts half the maker's level,
never more than `SPELLUP_DURATION`, and refuses rather than toggles off.

## Resurrection

`src/resurrect.c` (owner, 2026-10-25). RESURRECTION is the cleric guild's,
for any class in it: it sits in the `cleric guild` group, so every member
holds it from the next login, and `spell_resurrection` refuses anyone not
in the guild (staff aside). It needs the dead player's consent: the cast
only stores an offer on them (`resurrect_by`, `resurrect_corpse`,
`resurrect_until`, memory only), and ACCEPT does the work. The corpse
pointer is looked for in the object list again before ACCEPT trusts it --
the corpse can rot, be purged or carried off in the two minutes -- and the
refusals (`resurrect_refusal`: a fight, jail, a no-recall room left, a
death trap, `travel_spell_refuses`, privacy) leave the offer standing. The
corpse is always used up, as RAISE DEAD's is, so it cannot call its owner
back twice; it ends in the corpse registry as "resurrected by <caster>".
ACCEPT sits after DEVOTE in the command table, so `ac` stays ACHIEVEMENTS
and `de` DEPART. Adding it took `MAX_SKILL` to 233: the table was full.

**ACCEPT is a transfer that is on the disk or not done** (review,
2026-10-26: it ended the corpse first and ignored the save). In order:
`corpse_registry_hold` writes the corpse's record and stops the registry
rewriting it; a pending `resurrect:<corpse id>` receipt; every object
(coin piles too) moves to the owner; the mark `restore:<op>` goes in the
file's `Fixes`; the save. `DURABLE_FAILED`: everything goes back into the
corpse in reverse, the mark is forgotten (`player_fix_forget`), the hold
lifted, the receipt abandoned and the offer still stands.
`DURABLE_UNCERTAIN` (review, 2026-10-27: it was undone like a failure,
though the file may already be the new one) leaves the transfer pending
(`corpse_registry_pending`): the next save of the owner that lands
settles it (`corpse_registry_owner_saved`, from `save_char_obj`), and so
does boot or the owner's next login, from the mark in the file. On the
disk: the held record goes into history as `resurrected` -- and if that
move fails the record stays whole and held, never a "gone" copy -- the
receipt commits, and only then does coin reach the purse and the
character the Temple. A crash between the save and the commit is settled
at boot: a pending receipt whose owner's file holds the mark
(`player_file_fix_has`) sends the record to history instead of laying
it; without the mark the corpse is laid whole and the receipt abandoned;
an unreadable file keeps the record and lays nothing.
`tests/test_resurrection_transfer.py`.

**A death is the same kind of transfer** (review, 2026-10-27: the save
after a death was commented out, so a crash laid the corpse at boot and
logged the player in with the same things). `corpse_registry_died` opens
a `death:<corpse id>` receipt, writes the corpse's record, puts the mark
in the file and holds the track pending; `corpse_registry_death_settle`,
from `raw_kill_internal`, saves the player. A save that lands commits; a
save that does not leaves it pending -- nobody may take from the corpse
meanwhile (`corpse_registry_settling`, asked by GET: "still being laid
to rest"), and the owner's next save that lands settles it. Boot settles
a crash from the file: the mark there means the corpse is theirs and is
laid; no mark means the file still holds everything, so the record goes
to history as `undone` and nothing is laid; an unreadable file keeps the
record and lays nothing. **The mark must fit**: `player_fix_can_record`
is asked before anything moves, the list is read and built whole
(`read_whole_line`, no fixed buffer), spent `restore:` marks whose
receipt committed are dropped as it is rebuilt, and past
`PLAYER_FIXES_MAX` the operation is refused, never cut short
(`tests/test_death_transfer.py`).

## The Seasonal Areas Are Generated

`src/season.c` swaps three areas for a holiday copy **at boot**: `dresden`,
`limbo` and `midennir` load as `<base>_halloween.are` from Oct 18 to Nov 1
(Hallows End) and as `<base>_xmas.are` from Dec 16 to Jan 6 (Winter Veil).
The copies are built by `python3 scripts/build_seasonal_areas.py` (`make
seasonal-areas`) from the base file as it is now plus an overlay in
`data/seasonal/<base>_<tag>.json`: the `#AREA` line, the flavour text of
the rooms and mobiles a season decorates (name and description only), the
records that exist only in season (the Halloween vendor 2442 and treat
2403) and the resets that place them. Every object, exit, stat line,
price and ordinary reset comes from the base, so the in-season world can
no longer fall behind it. `scripts/validate.sh` runs `--check`, and
`tests/test_seasonal_areas.py` holds each copy to a superset of its base.

They were hand-kept snapshots of an older world until 2026-10-19, and
nobody noticed what they lacked because they only load in season: the
Halloween dresden had no room 4216, where every killed player is moved,
so a boot during Hallows End would have crashed the game on the first
death; limbo had no Oracle (97), no Hermie (98), no sanctum (8) and no
Rest Area (9); the Quest Master (7551) was gone from dresden and sat in
limbo instead, which is a fatal duplicate once dresden has him; and
every object still carried its pre-copper gold price. The live server
had booted on Oct 17, so it was running the base files through the
first days of the season, and the next deploy would have found all of
it. Rules this leaves:

- **Edit the base, not the copy, then rebuild.** A hand edit to a
  `_halloween` or `_xmas` file is overwritten by the next build. Flavour
  text goes in the overlay JSON; a seasonal record goes in its
  `records`, and may not use a vnum any base area has.
- **The in-season totals differ from the baseline.** Hallows End adds
  one mobile and one object (`mobs=2495 objects=3722`); Winter Veil adds
  none. `../merc --check-area` loads by today's date, so a count that
  moved on the 18th is the calendar, not a lost record. To validate the
  other season, copy `area/` somewhere and list the variant files in
  that copy's `area.lst` directly: `get_seasonal_area` only maps the
  base names.
- **`TOC_SEASON` overrides the calendar** (`get_current_season` in
  `season.c`): `none` boots the ordinary world, `halloween` or `xmas` a
  season out of its dates. `tests/live_mud.py` sets `none` by default,
  so a module run in late October or December is not asserting on
  decorated room names; `tests/test_seasonal_areas.py` passes a season
  through `extra_env` to boot each holiday world and check it whole --
  the square wears its pumpkins, Hermie, the Oracle and the Quest
  Master exist, and a slain mortal lands in the death room.
- **A room's LOOK details go in the overlay's `extras`.** `{"ROOMS":
  {"<vnum>": [{"keywords": ..., "lines": [...]}]}}`; the generator adds
  them as `E` records before the room's closing `S` (`with_extras`), and
  the seasonal test strips them with `without_extras` before holding the
  room's exits and flags to the base. Players look at what a description
  names (`look pump`, `look coffins` in the October 2026 logs), so a
  decorated room's nouns should each have one.
- **The Python tools do not know the seasons.** `area_lint.py`,
  `check_exits.py` and the shop price test read `area.lst`, so they
  check the base files only; the generator is what keeps the copies
  honest.

## The Installers

`install.sh`/`install.ps1` and `toc.sh`/`toc.ps1` install and run a copy for
anyone (rebuilt 2026-10-21; the guide is `wiki/install-guide.md`). They are
not how the live host is deployed -- that is `toc-deploy` -- but they follow
its model, and the rules below are what keep an installed copy's characters
safe:

- **The game never writes into the checkout.** Everything it writes is in
  `state/` (`TOC_STATE`): `area`, `player`, `gods`, `heroes`, `corpse`,
  `log`, `backups`. Before this, Docker bind-mounted the checkout's
  `player/`, `gods/` and `heroes/`, which git tracks, so the first save made
  `toc.sh update` refuse for good; and it kept the live world inside the
  container, so every rebuild lost the notes, reports, max-load counts and
  bans. A new path the game writes must land under `state/`.
- **The live world is code plus state, synced like production.**
  `scripts/toc_sync_area.sh` brings `state/area` up to date from the code's
  `area/` with `toc-deploy`'s rules (runtime `.txt` files kept, `custom.are`
  and `built/` only filled in, a shutdown marker never carried over).
  `tests/test_install_layout.py` holds its exclude list and `runtime_txt`
  to `toc-deploy`'s: change one, change both. It compares checksums, because
  rsync's size-and-mtime check skipped a same-size edit made within the
  second.
- **The entrypoint (`docker-entrypoint.sh`) and the native runner
  (`scripts/toc_run_game.sh`) forward SIGTERM to merc** and wait for it, so
  a stop saves every player. The shell is PID 1 in the container and ignored
  the signal before; Docker then killed the game unsaved. `merc`'s output
  goes to `log/game.log`: it writes `log/toc.log` itself and copies each line
  to stderr, so redirecting it into `toc.log` doubled every line.
- **`TOC_BIND_ADDRESS`** (`init_socket` in `comm.c`) keeps the game on one
  IPv4 address; native installs set it from `MUD_BIND` so local-only means
  local-only without Docker. Unset, the game listens everywhere, as it
  always did -- production does not set it. A value that is not an address
  exits rather than widening.
- **The image is Ubuntu 24.04, like production**, loads the world at build
  time (`--check-area`), and ships no runtime state: `.dockerignore` excludes
  `state/` and the runtime files under `area/`.
  `.github/workflows/docker-image.yml` publishes amd64 and arm64 to
  `ghcr.io/jeremydbean/toc2026` only after Validate passes on `main`. The
  package starts private; the owner makes it public once. Launchers pull it
  and build locally when the pull fails or `TOC_BUILD=local`.
- **An installation from before `state/` is moved on its first start**
  (`toc_prepare_state`): an old container -- one whose `/app/area` is not a
  bind mount -- is stopped first so its players save, the checkout's data
  directories are copied, the container's world is copied out and the
  container removed. `update` then puts git's copies of the checkout's
  `player/`, `gods/`, `heroes/` and `log/` back so it can fast-forward, one
  tracked directory at a time. Nothing is deleted.
- **A restore stops the game and confirms it is gone before it moves
  anything, and keeps this installation's `.env`** (review, 2026-10-22).
  `stop_game` returns the stop's own status -- `set -e` does not reach
  inside a function called as a condition, so it returned its closing
  echo's 0 -- and `game_running` checks nothing is left (a partial stop);
  either aborts with the data and `.env` untouched and no game started.
  The data goes to this `.env`'s `TOC_STATE`; the archived `.env` named
  another machine's paths, so it is kept as `.env.from-backup` and never
  installed. A native restore rebuilds (`start_game 1`): the archive
  carries a `merc` built where the backup was taken.
  `tests/test_restore_backup.py` runs the real Bash function and the real
  `toc.ps1` against a stand-in `docker`.
- **A new world starts empty**; `--import-players` (`-ImportPlayers`) copies
  the repository's characters in. `toc.sh promote <name>` makes the owner's
  character the implementor from its file (logged out, a copy kept in
  `state/backups/`).
- **`update` finishes in the newly pulled launcher** (`exec toc.sh
  _finish-update`), so a fix to the launcher applies to the update that
  brings it. The bash and PowerShell launchers mirror each other; change
  both. `toc.ps1` writes player files in Latin-1 with LF, and PowerShell 5.1
  has no `[Text.Encoding]::Latin1` -- use `GetEncoding(28591)`.

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

Three rules keep the output honest, all learned the hard way:

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
- **A door is as a reset leaves it.** `load_world()` reads the `D`
  resets and the exits' keys, and `door_lock()` says how a door is held:
  locked with a key that exists ("key"), or wizlocked or keyless
  ("barred", which only PASS DOOR gets past -- `move_char` lets it through
  any closed door). Either costs `LOCKED_COST`, so any way round wins;
  where none exists the route says `unlock <door>` before `open`, or no
  `open` at all for a barred one, and carries `needs` (`key 13006`,
  `pass door`), which the client's Routes panel shows. Four routes said
  "open door;e" at the Crystalmir farmhouse door (13039 east, reset
  locked) until 2026-10-21 and stopped at "It's locked".

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

The player-facing reference is `wiki/building-guide.md`. It was built in
phases, all shipped by 2026-10-08: ANEW/ALIST/ASTAT; MCREATE/OCREATE and
ASAVE; SET MOB/OBJ <vnum> in words with MSHOW/OSHOW; PLACE/RESETS/UNPLACE;
built areas in git; and BUILD, the guided builder. BUILD takes every typed
line while it runs (`build_wizard_input`, called from comm.c **before**
`split_typed_commands`, since a description may hold a semicolon) and
builds only by calling the commands themselves, so it can never make what
they would refuse; `build_set_mob`/`build_set_obj` return whether the
change took so it can ask again. SET ROOM's flags, sector, desc and
detail are `build_set_room` too; its old flag letters still work, read
with `word_keep_case` because `one_argument` lowercases and the letters
are capitals -- and only capitals or digits count as letters, or a
mistyped name would set bits. WALKTO finds a built area by name at run
time (`walkto_built_area`): the generated, committed `walkto.dat`,
`directions.json` and HELP WALKTO must never read `area/built/`, or each
state sync would leave them stale and fail CI. Rules the code depends on:

- **An area made with ANEW owns its vnum range**, declared in an
  `#AREADATA` header (`load_areadata`). Mobiles and objects carry no area
  pointer, so the range is how `save_area_full` in `db.c` knows what to
  write, and why MCREATE/OCREATE refuse a vnum outside one. RSAVE on such
  an area saves it whole; a legacy `#AREA` area still saves rooms only.
- **Built areas live in `area/built/`**, listed in `area/built/built.lst`
  (`BUILT_AREA_DIR`/`BUILT_AREA_LIST`), which boot loads after `area.lst`
  and skips a missing file in rather than exiting. Building never edits
  `area.lst`, which is code. `toc-state-sync` commits the directory (no
  `--delete`, no `*.bak`/`*.tmp`), `toc-deploy` excludes it and only fills
  in missing files with `--ignore-existing`, and `.gitignore`,
  `validate.yml`'s `paths-ignore` and `toc-auto-deploy`'s excludes all
  name it -- `tests/test_building_areas.py` checks each. The Python tools
  read both lists through `listed_area_files()` in `area_parser.py`, and
  key a built area as `built/<name>.are`.
- **The writer is the loader's exact inverse**, and
  `tests/test_building_mobs_objs.py` holds it to that: save, reboot, save,
  byte for byte. Change a loader and change its writer in the same commit.
  Object trailers are prepended on load, so they are written last to
  first; spell values are written as slots; a reset the loader would exit
  on is left out and counted. One difference is the game's own: boot makes
  a room with no exits NO_MOB (`fix_exits`).
- **BUILD's slash escape re-finds its descriptor.** `/quit`, `/delete`
  and `/switch` inside the wizard free the character and its descriptor
  or move the descriptor to a mobile, and the next question was written
  into released memory. `build_wizard_input` looks its descriptor up in
  `descriptor_list` after `interpret` and asks only if it still holds
  `ch`. Any command run on behalf of a character must assume the
  character may be gone when it returns.
- **The index lookups refuse a negative vnum.** `is_number` accepts a
  leading minus and `vnum % MAX_KEY_HASH` is negative for a negative vnum,
  so `MSHOW -5` read before `mob_index_hash`. `get_mob_index`,
  `get_obj_index` and `get_room_index` return NULL below zero, which also
  covers stock MLOAD and anything else that forgot to check.
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

**`load_char_obj` fills a found character's gaps, never a new one's.**
`apply_class_and_guild_skills()` runs at the end of the loader so a
character short of something their class, guild or race owes them gets
it at login -- but the loader also builds the empty character a new name
starts from, whose class is still 0 (mage). Until 2026-10-21 every
character made since 2026-09-19 therefore held mage basics and mage
default beside their own class's groups; Trentlin, a warrior, asked in
say whether casting refresh was a bug. It now runs only when the file
was found, and creation applies the chosen class's groups at
`CON_GET_ALIGNMENT`. `tests/test_new_character_groups.py`.

**Those already made are corrected at login** (owner, 2026-10-21: remove
the mage spells from anyone who should not have them and refund the
practices). `rescind_stray_mage_groups()` in `skills.c`, the first login
fix (below), takes `mage basics` and `mage default`
from any mortal who is not a mage -- a remort wipes every group, so the
bug is the only way one got there -- zeroes their members, then gives
back through `apply_class_and_guild_skills` and the groups still held
everything owed another way, at the percentage it had (the dagger every
class wields, a spell in a group they bought). Each spell that does not
come back refunds the sessions its percentage above 1% would cost at
the character's intelligence now, which errs the player's way since some
came from use. Staff are left alone. It logs and WIZINFOs what it took,
and does nothing once the groups are gone.

## Fixing Characters At Their Next Login

**A bug that left characters wrong is corrected by a login fix, never by
editing player files** (owner, 2026-10-21: a standard method). The files
live on the host and the state sync only copies host to git, so an edit
in the repository is overwritten five minutes later and never read.
`src/fixes.c` holds `player_fixes[]`: an id that is never changed or
reused, a line for the log, and a function. `player_fixes_login()`,
called from the nanny once the character is in their room, runs each
fix the character has not had, records its id in `pcdata->fixes_done`
(`Fixes <id> <id>...~`, **case 'F'**), logs and WIZINFOs the ones that
changed something, and saves once. A character made after a fix exists
is born correct: a new character has every id marked and nothing run.
An old file with no `Fixes` line runs every fix once. A fix function
decides for itself who needs it (staff, class, level), says what it did
in plain words to the player, returns whether it changed anything, and
must be harmless on anyone. Its test plants the bug's leftovers in a
fixture's file -- **and deletes the fixture's `Fixes` line**, since a
fixture is a new character and would otherwise skip the fix -- logs in,
checks the correction, and checks a second login says nothing (see
`tests/test_new_character_groups.py`). Staff list them with `FIXES` and
see an online player's with `FIXES <player>`. A row says whether staff
get the fix; one that does not skips them **without marking**, so a
builder whose trust is later taken away still gets it. The second fix,
`20261021-mage-weapons`, undoes the same creation bug's other half --
the mage's weapon floors (dagger 80, whip 20) applied to every new
character -- for a weapon still at exactly the mage's value, which was
never trained since.

## Player Backups And Restores

Owner, 2026-10-23: player data is the most important thing the game
keeps, and there must be basically no way a player and all their gear,
stash included, cannot be put back. `wiki/player-backups.md` is the
guide, with the loss windows and what is still only a proposal. The
rules the code depends on:

- **Snapshots are `player/versions/<Name>/<Name>.<stamp>[_NN][.<kind>]`**,
  taken at every save (at most one a minute) and as milestones: before
  death, remort, delete, ADVANCE, staff SET, GRANTPSI, COMBINE, CREATOR
  and every restore (`prestore`, `gitrestore`, `gearrestore`,
  `stashrestore`, `corpserestore`); before a mobile's kill takes its
  experience (`prepenalty`: the `death` copy already carries the
  penalty); after a level (`advance_level`'s wrapper) and a quest.
  `_NN` is a second copy of one kind in one second -- never skip one.
  `snapshot_name_parse()` is the one reader of the name; a new tool that
  lists snapshots goes through it. `snapshot_prune()` keeps every
  untagged copy for a day, the newest of each hour for a week and of each
  day for a year; a tagged one for 90 days and the newest
  `PLAYER_MILESTONE_MAX` of its kind for ever; the pinned one always.
  No list has a fixed cap (`snapshot_list_sorted` grows; PRESTORE pages).
- **A save or snapshot says whether it landed, and whether it is on the
  disk.** `save_char_obj` returns true only for a save fsynced and with
  its directory flushed; `save_char_obj_status()` tells `DURABLE_FAILED`
  (the old file stands) from `DURABLE_UNCERTAIN` (renamed into place, not
  confirmed -- the old file is gone, so it is not a failure to undo).
  `durable_commit` returns the same three. A snapshot is published only
  whole (it ends `#END`), read back against its checksum, and `ok` and
  `durable` are separate; a milestone goes in the ledger with its
  checksum. Record nothing, and report nothing done, on the strength of a
  save or snapshot that is not `DURABLE_OK` (independent review,
  2026-10-23: unconfirmed writes were reported as done). Test faults:
  `TOC_FAULT` (`fsync`, `dirsync`, and `autowrite`, which holds every
  save the tick makes on its own -- the autosave and bank interest's -- off for a test that must know which save wrote a file --
  matched by substring, so never a name holding `save`) and `TOC_FAULT_FILE` (one named point,
  `save 2` for the second save, `save-<Name> 2` for that character's
  second, which an autosave of somebody else cannot take -- though one
  of that character can, so ACCEPT's save has its own `accept-save`
  (CI, 2026-10-27), a death's `death-save-<Name>`, a craft's
  `craft-save` and a PRESTORE give's or retry's `prestore-save`; `dirsync-<Name>` makes that character's next save
  unconfirmed, `corpse-move` fails a corpse record's move into history;
  `ledger`, `crash-before-commit`), read
  by `recovery_fault()` and set nowhere but `tests/`.
- **Nobody comes out of a file dead** (`revive_at_load`, end of
  `load_char_obj`): a `death` copy is written below zero hit points,
  position DEAD, in the room of the death, and a full PRESTORE to one
  logged Alaric in as a corpse no tick heals and QUIT refuses
  (2026-10-24). Read below STUNNED or at no hit points, a character
  stands at one hit point in the Temple. `tests/test_revive_at_load.py`.
- **Reading a snapshot never touches the game until all of it read.**
  `snapshot_read_gear`/`snapshot_read_stash`/`corpse_file_read` read aside
  through `read_objects_aside` and return the list or nothing.
- **Receipts live in the recovery ledger, never only in the player
  file** (handoff review, 2026-10-23: a git request's `restore:<id>` mark
  in the file was rolled back by a PRESTORE to its own undo copy, and the
  request ran again). `player/recovery/ledger.tsv` is append-only and
  fsynced: requests (pending, committed, rejected, retry), every PRESTORE
  with the copy that undoes it, milestones, corpses, and each player's
  uid (`recovery_uid`: made with the character, retired at deletion,
  never in the player file). An undo is a new event. Retry is for what
  may work later (a file not installed, a read or save that failed, a
  corpse still holding things); rejected for what never will. A record is
  whole only with its FNV check and its newline: a torn tail is copied to
  `ledger.torn.<epoch>` and cut off at boot, and a failed append is cut
  back at once (`ledger_append`), because a torn line once swallowed the
  next record and gave a player a second uid.
- **Every restore that gives objects goes through `prestore_give`**
  (GEAR, STASH, CORPSE): an undo copy that is `DURABLE_OK`, a pending
  receipt, the objects and the mark `restore:<op>` in the file, the save,
  the committed receipt -- in that order, each checked. A failed save
  gives an offline copy nothing (abandoned; the source is untouched) and
  leaves an online player's objects in memory, pending. Pending staff
  restores (ids with a colon: `gear:N`, `stash:N`, `corpse:<id>`,
  `full:N`) are settled at login by `recovery_reconcile_login` from the
  file's mark: committed, or abandoned and free to be done again. **A
  retry of a pending restore trusts the mark only from the disk**: an
  offline copy's mark was just read from the file, but an online
  player's is in memory, so the retry saves first -- giving nothing
  again -- and commits only on `DURABLE_OK` and a ledger write that
  landed (review, 2026-10-26: it committed unsaved, and a crash lost the
  restore and refused another). Git
  requests (no colon) are restores.c's. A full PRESTORE saves an online
  target, takes a `DURABLE_OK` undo copy, writes the new file aside and
  flushes it, writes pending -- and only then disconnects, renames and
  commits; any failure before the rename changes nothing. It keeps from
  the current file, never the snapshot, `Pass`, `Tru`, `Creator`,
  `Fixes` (with its own mark added), `HyruleSecrets` and `BlackMarket`,
  so a rollback restores play, never an old password, rank, a login
  fix to run twice or a one-time claim to pay twice. **A deleted
  character can be restored** (review, 2026-10-26): with no file there is
  no copy to undo with, so absence -- proved by `stat`'s ENOENT, never
  inferred from a failed open -- is recorded in the receipt as the undo
  state ("no file"). The snapshot must name the character, rank is
  checked from it (`prestore_snapshot_identity`, get_trust's rule), and
  the uid the ledger recorded with that snapshot (`recovery_snapshot_uid`)
  is put back after the commit (`recovery_reinstate_uid`). A name that
  another uid holds now is refused, as is one whose snapshot the ledger
  never recorded while somebody holds the name; a file that is there and
  cannot be copied is refused exactly as before
  (`tests/test_prestore_deleted.py`).
- **A player's corpse is written down as it is** (`src/corpses.c`):
  `corpse/live/<id>.corpse` with every object at any depth -- keys and
  blank maps too (`fwrite_obj_everything`) -- at the death and within a
  second of any change (`corpse_note_change` from `obj_from_obj` and
  `obj_to_obj`, `corpse_registry_moved` from `obj_to_room`), every ten
  minutes for its timer, and at shutdown (`corpse_registry_flush_all`).
  Boot makes each again exactly; one that cannot be read is renamed
  `.unreadable`, never deleted. When one ends (picked up, rotted, purged,
  restored) its last state goes to `corpse/history/<Owner>/` with why --
  and the live copy goes only once that is `DURABLE_OK`. If history
  cannot be written the end state waits in `live/` as
  `<id>.ending.corpse` (never laid in the world, listed and restorable,
  moved to history each minute and at boot once it can be); if nothing
  can be written the live copy is renamed `.stale.corpse`. A track never
  outlives its object. One put down again is kept again as a new record
  (a new id: lineage between the two is not recorded yet). CORPSE GEAR
  refuses a corpse whose recorded uid is not the name's uid now, unless
  FORCE. `make_corpse` wraps
  its `obj_to_room` in `corpse_registry_making` so a death is not taken
  for a corpse put down. PRESTORE GEAR and the git requests wait while
  the corpse holds things; any restore ends the owner's corpses.
- **A cloud session restores through `area/restores.dat`**
  (`src/restores.c`): `<id> <player> gear|stash|import <stamp> [<file>]`.
  `tools/player_history.py` finds a state in git and `export`s it.
- **Off the host**: the state sync carries `player/` (ledger included),
  every tagged copy but `level` and `quest`, the newest ordinary copy of
  each finished hour (mirrored to the host's keeping, so a pruned one
  leaves the tree but not git's history; owner, 2026-10-24), and
  `corpse/` (`live/`
  mirrored with `--delete`, so an ended corpse never comes back from git;
  `history/` never deleted); `toc-restore` lays all of it down. The
  encrypted `sync-player-backup.sh` checks tar, its listing and age apart
  (sh has no pipefail) and carries `corpse/`; it keeps the latest archive
  only, and is not installed by `toc-deploy`.
  `tests/test_recovery_ledger.py`, `tests/test_corpse_keep.py`,
  `tests/test_player_backups.py`.

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
- A typed line goes to the game whole from both consoles; the game splits
  it (see Commands above). Do not split it in the browser again. Store one
  history entry, and never touch password input.
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
`log/`, the `area/` runtime files and the areas built in game
(`area/built/`, see In-Game Building) to `main` **in plaintext**. It
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
live and CI's `deploy-gate` job passed on a push to `main` for it (see
CI above; nothing else counts), it runs `toc-deploy` pinned
to that commit, with automatic rollback if the game does not come back
healthy. Docs, tests and state-sync commits never trigger it, and a
commit that failed to deploy is not retried until something newer lands.
So a session that can only push -- a cloud session -- still ships: push,
and the game updates up to ten minutes after CI goes green (CI takes
about fifteen minutes), once nobody is playing. Put `[deploy now]` on a line of its own in the message of the commit that
changes the code to skip the CI wait for an urgent fix -- it covers that
commit's code and state-only commits on top of it, never later code
(audit, 2026-10-21); `toc-deploy` still refuses anything that does not
build or whose world does not load. Every auto-deploy decision is about
the newest commit that changed deployable content: the failed-attempt
record, the override and the CI run -- the newest Validate run on a push
to `main` for that commit or a descendant, so a `[skip ci]` code commit
is never covered by an older green run, and a cancelled, failed or
missing run, or one with no passing `deploy-gate`, ships nothing. A desktop session may still run
`toc-deploy` by hand for an immediate deploy; the two share a lock.

**Nothing pasted into a cloud session's chat gets it onto the host**
(2026-10-11). Its sandbox has no `ssh` binary, its only outbound path is
an HTTPS proxy with a domain allowlist that does not include the game
host, a connection to port 22 is refused at the network layer, and the
harness refuses attempts to tunnel out or to add a git-carried command
runner as a containment escape. An SSH key, the dashboard token or
`chmod 600` on a key file changes none of that, so do not ask for them;
the owner pasted the key three times before this was written down. What
such a session can do is everything that lands by push, and it can
verify a staff action from the synced log. A staff command that has to
run on the host -- a PRESTORE, an ANNOUNCE -- is the desktop's job or
the owner's, in game.

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

**Give the owner times in Atlanta local time** (America/New_York: EDT,
UTC-4, until the first Sunday of November, then EST, UTC-5) (owner,
2026-10-21). GitHub, the logs and `log/deployed-commit` are in UTC:
convert before reporting, and schedule check-ins with that in mind.

Recount world totals from the tools (`area_lint.py`, `merc --check-area`)
rather than copying a figure from a doc -- the baseline above was wrong
for a day because one was copied.

On the host: `/srv/toc/build` is the git checkout `toc-deploy` resets
and builds, `/srv/toc/current` the live tree it rsyncs into, units
`toc-game` and `toc-web`, plus `toc-state-sync`, `toc-state-sync-check`,
`toc-game-recovery`, `toc-auto-deploy`, `toc-game-probe` and
`toc-daily-backup`, all in `/usr/local/sbin`. `toc-deploy` installs the
newer copies of the first six, and the auto-deploy units, at the end of
every healthy deploy.
`toc-auto-deploy` keeps its state in `/var/lib/toc-auto-deploy`
(`attempted`, `last.log`); `journalctl -t toc-auto-deploy` has its
history.
The SSH user is **ubuntu** (the VM used `tocadmin`; that is history).

`wiki/disaster-recovery.md` is the one page to read when something is
broken: what is down, how to deploy, whether the backups are working,
and how to rebuild on a new machine.

**The automatic deploy waits for an empty game** (owner, 2026-10-20: do
not reboot while players are on). `toc-auto-deploy` asks the game for
its count of playing descriptors over MSSP (`toc-game-probe`, the same
question webadmin's `probe_game` asks) and holds a commit -- status
`holding <sha>: N player(s) online` -- until it reads zero, looking
again every ten minutes; it is not marked attempted, so the first empty
tick ships it. **A count nobody can read is not zero** (redesign,
2026-10-25): the probe answers a number, `down` (connection refused --
no game, so nobody in it, and the deploy goes ahead) or `unknown` (it
connected and got no count: a hung or half-started game, where players
may be stuck), and `unknown` holds the commit exactly like a count
above zero. It used to deploy on `unknown`. Recovering a sick game is
`toc-game-recovery`'s job, not a reason to push new code through it.
`tests/test_auto_deploy.py` plays the gate and runs the probe against a
live server and a silent listener. The host's copy of the script only updates at
the end of a healthy deploy, so the first deploy after this rule landed
had to be timed by hand against the synced login journal.
`toc-deploy` run by hand is the override, and it still warns and saves
everyone first. **A cloud session's override is `[deploy with players]`**
on a line of its own in any commit waiting to ship -- only when the owner asks to ship with
people on (owner, 2026-10-24: "ship now, just send the announcement
before reboot"). It lifts the hold and nothing else: CI still has to
pass (that is `[deploy now]`'s, for its own commit), players get a
minute's warning through the queue, then `toc-deploy`'s announce, save
and announce. A commit pushed only to carry the marker works. Like any
change to the script, it works from the deploy after the one that
installs it.

**A marker counts only on a line of its own** (`has_marker` in
`toc-auto-deploy`; blanks around it allowed). Anywhere in the message, a
sentence that merely named one was an order: on 2026-10-25 a commit body
saying "[deploy now] and [deploy with players] keep their meanings" was
read as both, and the game was restarted under a player it was holding
for. Never write either marker on a line of its own unless you mean it,
and when you only mean to name one in prose, keep it inside a sentence --
or in backticks, as here.

*Superseded for automatic deploys by the rule above; still how a deploy
by hand behaves.* **Deploy whenever the change is ready, connected
players or not.** The owner settled this on 2026-09-29: do not hold, do
not ask, and do not wait for an empty mud. By the time the stop is reached the update has
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
`toc-state-sync`, `toc-state-sync-check`, `toc-game-recovery`,
`toc-auto-deploy` and `toc-game-probe` from the build tree once the game
answers healthy, so a change to any of them takes effect on the deploy
that carries it, from the end of that run.

**The webadmin queue runs commands as a stand-in character with no
player data**, so anything that needs `pcdata` -- `dummy`, for one --
does nothing from it. Use it for `fsave`, `announce` and staff commands
that act on the world; do the rest in game.

`toc-deploy` exists because doing this by hand is how `area/custom.are`
went missing: it is tracked in git *and* listed in `area.lst`, so
treating it as a runtime file and excluding it left the game unable to
boot. **It is excluded now and seeded only when missing**, like
`area/built/` (audit, 2026-10-21): RSAVE writes builders' workshop rooms
there and the state sync carries it host to git, so git's copy is up to
a sync behind and copying it over the live one lost what was saved
since. A change to it is made in game. `tests/test_deploy_install.py`
runs the script's own rsync and seeding on synthetic trees.

**How `toc-deploy` fails** (`tests/test_deploy_failures.py`, stubbed): a
world that fails `--check-area` stops it before the game is stopped (the
check was piped into `tail`, and `/bin/sh` has no pipefail -- so was
`toc-restore`'s); the way back is made before the game is stopped,
and a deploy that cannot make it stops there with the game still
running; and any failure between stopping the game and starting it
rolls back through an EXIT trap. A stop that fails part way installs
nothing: both services are started again on the code they were running
and their health checked (`restart_unchanged`). `disrupted` says a stop
was asked for and `installing` that files may have changed; the trap
reads them in that order. Its exit status says how far it got -- 10
rolled back and healthy, 11 rolled back and still unhealthy, 12 new code
unhealthy and left alone, 13 nothing installed and the old code healthy
again, 14 nothing installed and not healthy, anything else stopped
before the game was touched -- and `toc-auto-deploy`'s status line says
the same.

**A rollback puts back code, never state** (redesign, 2026-10-25). The
way back is `/srv/toc/rollback-code-<stamp>/`, a copy of the live tree
made by `sync_code` -- the very function, and so the very exclude list,
the install uses -- with unchanged files hard-linked to the previous
snapshot and a `.snapshot-ok` marker written last; the two before it
are kept. Rolling back is `sync_code` from the snapshot over the live
tree, and rsync's `--delete` never removes an excluded path, so players,
corpses, notes, bans, max-load counts, `custom.are` and `area/built/`
stay exactly as the game left them. The tar of `merc src area webadmin`
it replaced held all of `area/`, runtime files included, so a rollback
rewound every note, ban and builder's room written since the deploy
began. `toc-deploy --rollback` restores the newest snapshot by hand
(`TOC_ROLLBACK_SNAPSHOT` names another) after an exit 12.
`tests/test_deploy_install.py` runs snapshot, install and rollback on
real trees and checks every piece of state survives.

**A rollback names the code it put back** (review, 2026-10-26: it left
`log/deployed-commit` naming the code it had removed, so recovery would
have rebuilt that and the auto-deployer thought it live). The install
writes `.code-revision` in the live tree -- `<commit> <sha256 of merc>`;
`sync_code` never copies it or `.snapshot-revision` -- and a snapshot
records the running tree's identity as `.snapshot-revision` before its
`.snapshot-ok`, only when it is a full commit id and the merc beside it
is the binary it was written with (`code_identity`). Rollback writes the
snapshot's identity to both places (`put_file`: aside, then renamed),
healthy or not, since recovery rebuilds what the record names; a legacy
snapshot or a copy that did not finish is recorded as `unknown`, and
both `toc-auto-deploy` and `toc-game-recovery` then wait for a person.
The commit rolled back from is appended to the auto-deployer's
`rolled-back` list (`TOC_AUTO_DEPLOY_STATE`), which holds it and its
ancestors until newer code lands. `toc-game-recovery` refuses to build
when the tree's `.code-revision` and the record disagree, and keeps the
identity's checksum current when it swaps the binary (`note_binary`).
`toc-restore` writes the identity too. `tests/test_deploy_rollback_identity.py`
runs three real deploys, rolls back to the newest, an older and a legacy
snapshot, and asks both scripts what they would do after each.

**Healthy means the game answered, not that a port opened.** The game
binds its port before it loads the world (`init_socket`, then
`boot_db`), and the dashboard's `"merc":true` is only a TCP connect, so
the old check passed for a game still booting -- or hung while it did.
`healthy()` now also asks `toc-game-probe` for a count, which only the
running game loop gives, and waits up to ninety seconds for it.

**Recovery rebuilds what is live, never the tip of main.**
`toc-game-recovery`'s second stage used to fetch `origin/main`, build it
and install the binary -- untested code, shipped because the game was
down. It now rebuilds the commit in `log/deployed-commit`, and with no
record there builds nothing and says it needs a person. Newer tested
code reaches a down game through `toc-auto-deploy`, which deploys when
the probe says `down` (`tests/test_game_recovery.sh`).
**`toc-game-recovery` takes the deploy lock** (`/run/toc-deploy.lock`,
non-blocking, after its own) and leaves the game alone while a deploy
holds it: a deploy stops the game on purpose and builds in the tree
recovery would reset.

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
TELL, REPLY, GTELL, NOTE and the commands that read them back: `log/` is published, and AGENTS' rule on private
messages holds. One flagged with LOG <name> is recorded in full.

**A watched line names no room the black market dealer or the treasure
goblin stands in** (`room_hides_from_log()` in `interp.c`; the room is
written `-`, and an arrival into or out of such a room names neither).
Their own lines never logged where they are now, but every player is
watched, so a buyer's `buy cake` beside the room vnum published him all
the same (review, 2026-10-21). A new line that writes a room must go
through `watch_room_tag()` or ask the helper.

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
- Every purse change -- `adjust_coin_balance` (picking up, looting,
  splitting, giving), `gain_copper`, `spend_copper` and `add_money`.
  Coin from nowhere is the oldest exploit there is. Until 2026-10-08 only
  `gain_copper` was watched, and three weeks of watched play logged no
  coin at all: nothing players do much goes through it.
- `raw_kill_internal` -- both sides of a death, so a death has a cause
  and a kill has a victim. Not `raw_kill`: `damage()`, every ordinary
  combat death, calls the internal one directly, and with the hook in
  the wrapper not one combat death was ever logged.
  `tests/test_watch_log_events.py`.

Staff actions that change shared state should reach `log_string` and
not only `wizinfo`: wizinfo tells whoever is online at that moment and
nobody afterwards, which is no use when the question is asked a week
later. `REPORTS CLEAR` does both.

## The Play Journal

`src/playlog.c` (owner, 2026-10-21: "really advanced logging for players
who play to help identify potential bugs through gameplay"). The watch
log says what a player typed; the journal says what happened, in columns
`tools/log_report.py` reads:

- **`log/play.tsv`**, tab-separated: epoch, kind, name, level, room,
  area, then the kind's fields. `cmd`/`refused`: position, hp%, ms,
  fight, command, args, and the first `PLAY_REPLY_LINES` (3) lines the
  game answered, joined with ` // ` -- not `|`, which SCORE and every
  boxed display draw with -- skipping lines of nothing but rules and
  borders. `bug`: the BUG message and what was running. `anomaly`: what
  and the numbers (hit points over max also says what the maximum was a
  tick ago). `report`: BUG/TYPO/IDEA, the text, hp, the last
  `PLAY_RECENT` commands. `session`: at QUIT, link loss and shutdown,
  what the sitting came to, ending `coin: loot 3p, quests 162p, ...` --
  the session's coin by source. Trimmed past `PLAY_JOURNAL_MAX` lines to the newest
  `PLAY_JOURNAL_KEEP`, like the channel journal; the whole of `log/`
  reaches git with the state sync and CI ignores it.
- **`interpret()` is now a wrapper** round `interpret_body()`: it times
  the command, snapshots `d->outtop`, and after the body finds the
  descriptor again (QUIT frees it) before reading the answer from
  `d->outbuf`. Only the outermost call for a player is recorded, so AT,
  FORCE and ORDER do not double up. `play_note()` in the body is where
  the command, its shown line and its privacy are decided: **a private
  or password command's words and answer are never written, watched in
  full or not, and an unknown word is written alone** -- `log/` is
  public, and a password typed at the wrong moment is an unknown word.
  A room holding the dealer or the goblin is `-`. **A command whose
  answer can hold somebody else's private words is private too**:
  HISTORY and REPLAY read tells back, and once the journal kept three
  lines of an answer, `history tell` published a tell (audit,
  2026-10-22; `command_is_private`, `tests/test_playlog.py`). A new
  command that shows tells, notes or anything else said in private goes
  on that list.
- **Every `BUG:` line says what was running** -- whose command, which
  room, or the update phase (`playlog_phase`, set in `update_handler`)
  -- and lands in the journal too. Not at boot, where FILE/LINE says it.
- **`log/crash.log`**: `playlog_boot()` (after `boot_db`) opens it and
  installs a handler for SEGV, BUS, FPE, ILL and ABRT that writes the
  last `CRASH_RING` commands and the phase with `write()` only, then
  re-raises. Nothing in the handler may call stdio, malloc or
  log_string. It is not installed under AddressSanitizer, whose report
  is worth more. `tests/test_playlog.py` crashes a live server with
  SIGSEGV and reads the file.
- **Coin by source** (`playlog_coin`, owner 2026-10-22). The four
  purse functions -- `adjust_coin_balance`, `spend_copper`,
  `gain_copper`, `add_money` -- report every change: a pile picked up,
  looted or handed over is loot; otherwise the command running for that
  character decides (AQUEST quests, SELL sales, the casino's commands
  gambling), `playlog_coin_as("dailies")` around a payment names it, and
  anything else is other. Every loss is spent. DEPOSIT, WITHDRAW,
  CONVERT and BALANCE move coin within the character's wealth and are
  left out. A new purse function must call it too.
- **Watch-log lines a command log cannot show**: `affects off: titanic;
  max hp 5474 -> 924; hp 5474 -> 924` from `char_update`'s expiry, one
  line a tick, after the clamp; and `quest assigned: kill <mob> (mob N,
  level N) in <area file>, N minutes, ordinary|rush|emergency|daily`
  from `quest_log_assigned()` -- the area, never the room.
- **Anomalies** (`playlog_tick`, from `char_update` each tick): hit
  points far over max, negative coin, practices or trains, fighting
  nobody or across rooms, and -- not for staff -- level past the remort
  cap, more than three levels of experience or two thousand kills of
  coin in one tick. One line per kind per player per ten minutes, to the
  journal and to toc.log as `ANOMALY:`.

- **`log/progress.tsv`** (2026-10-22, the progression pass): a line per
  credited kill (`progress_kill`, from `group_gain` after `gain_exp`) and
  per player flee or death by a mobile (`progress_event`). Columns:
  epoch, kind, the character's file **Id, never a name**, level, class,
  remorts, hp%, mana%, foe vnum and level, **area file, never a room**;
  a kill adds encounter ms, base, rested and accepted XP (what `gain_exp`
  took, so the level 50 stop shows) and group size. The encounter starts
  at `fight_began_ms`, stamped in `set_fighting` when a mobile enters a
  fight or a player strikes one that is in none, and never cleared --
  `damage()` stops a dead victim's fight before `group_gain` reads it.
  The dealer and the goblin are never written. Trimmed past
  `PROGRESS_MAX` to `PROGRESS_KEEP`. `tools/log_report.py` aggregates it
  by foe and area -- XP per combat minute, median encounter, flees,
  deaths, distinct characters -- and prints no ids
  (`tests/test_progress_log.py`).

`tools/log_report.py` prints the slowest commands, what the game said no
with (grouped by command and answer -- the cheapest way to find a command
that confuses players), **help that did not help** (HELP X, then X refused
within ten minutes -- it found HELP HEROQUEST teaching commands that did
not exist), repeats outside a fight, events collapsed to one line a kind
with a count (the goblin's drift was 275 lines in two days), quests
assigned by area and kind, anomalies with the buff that wore off just
before, BUG lines with context, reports with their commands, sessions
with their coin by source and crashes. The morning routine runs it.

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

**In practice nobody rolls the band any more** (checked 2026-10-20).
A second or later remort pays its powers *at the remort*
(`psionic_remort_grant`, which `do_remort` and `psionic_login` share),
so `psionic` is 1 before the character is level 4, and a remorted
character short of their due is topped up at every login. A GRANTPSI
pays where it was asked to (below). The band roll in
`do_check_psi` is the fallback for a remort-owed character a grant
somehow left with nothing. The "one in three finish the band with
nothing" below describes no path a player can reach today; it is kept
as history, not as a rule to preserve.

**A remorted character holds powers it cannot use yet.** The powers'
skill levels run from 17 (psionic armor) to 28 (transfusion), and
`get_skill` returns 0 below them, so a level 3 holds them at 1% and
can neither use nor practise them until each opens. Salir says so
("You hold mindbar, but cannot train it until level 22.") -- any
trainer does, for any skill held below its level -- where it used to
say "You can't practice that."

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

**Hermie appears only when staff place her** (owner, 2026-10-27). From
2026-10-04 she stood at the altar for six hours after every boot
(`spellup_boot_place`); that is gone, with its `TOC_NO_BOOT_HERMIE`
switch. A test or tool that needs her has a staff fixture type SPELLUP
(`at 4208 spellup` puts her at the altar), as
`tests/test_journal_frictions_oct22.py` and `tools/class_bench.py` do.

**A staff GRANTPSI is a promise; a remort's owing is a chance.** The
dice decide *when* a granted character awakens, but if they miss at 18,
19 and 20, level 21 pays the grant anyway (owner, 2026-10-04: Alaric was
granted and missed three rolls). The one-in-three who finish the band
with nothing are remort-owed characters only. *Superseded the same
night:* a pending grant now pays on the very next level gained, at any
level, before the band is consulted, and GRANTPSI no longer tells the
player anything.

**GRANTPSI has three forms, and none tells the player anything**
(owner, 2026-10-27; superseding the above). `pcdata->psionic_grant_pending`
is a `PSI_GRANT_*` value, saved as `PsiGrant <n>` under **case 'P'**:
`GRANTPSI <name>` is `PSI_GRANT_BAND` (1) -- certain, at the awakening
check, the first level gained from 18 to 21; past the band it waits until
they reach it again after a remort. `GRANTPSI <name> LEVEL` is
`PSI_GRANT_NEXT_LEVEL` (2) -- the next level gained, any level. `NOW`
grants at once, online or offline (the loaded copy is saved). Nothing
lands at a login; only `do_check_psi(ch, "levelup")` pays a flag. A file
saved before 2026-10-27 with `PsiGrant 1` now waits for the band. The
player hears of it only through the awakening message, as anybody whose
mind awakens on its own. Staff hear the moment any grant lands --
GRANTPSI, a remort or the band roll -- from `grant_psionics` itself: a
WIZINFO (at `staff_notice_level`) and a log line naming the powers
given. `tests/test_dns_and_grantpsi.py` walks a band grant through levels
17 and 18 and a LEVEL grant through one level.

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

## The Class Review's Mechanical Fixes

Found by an independent class/guild review (2026-10-26), each verified
against the source first and pinned by a test that fails on the old code:

- **Backstab and smite aim better the better they are known.** The stock
  line `thac0 -= 10 * (100 - skill)` gave anything under about 90% an
  automatic hit and took the bonus away at 100%. `strike_thac0_bonus()` in
  `src/combat_rules.c` is 0 to 10, never decreasing.
- **Crane dance is one curve** (`crane_dance_mean`): 27.5% of a weak foe's
  health to 600, then `165 * sqrt(hp / 600)`, capped at 25 a level of the
  dancer. The old bands fell from about 275 to 125 at 1,000 hit points and
  from 500 to 260 at 4,000, and had no ceiling against a boss.
- **Psionic armor and psychic shield turn mental hit-point damage.**
  `damage()` asked `skill_lookup("psionic_armor")`, which names no skill;
  it now asks `psionic_mental_reduce()` in `magic2.c`, by gsn, as the mana
  and movement drains always did -- once each, since drains never pass
  through `damage()` (`tests/test_mental_defence.py`, in the fixture
  world's arena, room 32706).
- **A destruction attempt replaces the third attack only when it
  shatters a weapon.** A passing destruction check without the quarter
  roll used to lose the blow outright.
- **Undead servants share a budget of 10** (owner, 2026-10-26): skeleton 2,
  wraith 5, vampire 10 (`undead_budget_used`, costed by the name
  `raise_undead` gives each). The head counts of 5, 2 and 1 depended on the
  order of raising (`tests/test_undead_budget.py`).
- **Nerve damage's free failed strike stays free** (owner, 2026-10-26,
  confirming 2026-09): the review proposed lagging it; see below.

`src/combat_rules.c` holds arithmetic with no game state and includes no
`merc.h`, so `tests/test_combat_rules.c` can check it exhaustively; put a
new pure formula there rather than in `fight.c`.

- **GAINLIST reads a group's members as `group_add` does: a skill first.**
  `group_lookup` is a prefix match, so asking it first read "harm" as the
  "harmful" group and listed cause serious and cause critical for builds
  that never get them. Every name lookup in the game is a prefix in table
  order -- the Archmage sells "mage transport" -- and
  `tools/class_balance.py` mirrors that (`skill_lookup`, `group_lookup`).

Balance changes from the same review, each its own commit:

- **HEAL is `heal_spell_amount(level)`**: 100 to 25, two more a level, 168
  from 59 (non-clerics two thirds).
- **Smite strains its weapon** by `SMITE_WEAR_MIN`-`MAX` condition on the
  3% roll; only a weapon worn to 0 breaks.
- **A servant's hit points come from `lasting_max_hit()`**, the caster's
  maximum less positive `APPLY_HIT` affects that will wear off. A new
  creature sized from its maker should use it too.

**The main classes were brought up, not the strong ones cut down**
(owner, 2026-10-27: scale the other main classes up to the more
powerful ones rather than nerf them). Measured in the yard at level 50,
the four ordinary classes sat at 68-180 a round against the monk's 271,
the necromancer's tentacles at 417 and a mage's meteors at 690. Three
levers, all in `combat_rules.c`, each a constant to tune:

- **Weapon mastery** (`weapon_mastery_percent`): a warrior's or thief's
  ordinary weapon blow gains `MASTERY_OWN_GUILD` (4) percent of the
  weapon's own damage a level in the class's own guild,
  `MASTERY_OTHER_GUILD` (3) elsewhere, to level 59. Not a backstab (it
  multiplies itself) and not damroll, added after it, so gear does not
  run away with it.
- **The casters' own attack spells grow a die a level**: flamestrike
  (every cleric's) is level d`FLAMESTRIKE_SIDES` (9), lightning bolt
  (every mage's) level d`LIGHTNING_BOLT_SIDES` (10) -- a flat 8d8 and a
  table that stopped at 64 before. Another class casting them rolls half
  the dice: a warrior in the mage guild has mastery too, and must not
  out-hit the warrior in the warriors' guild. **A mobile keeps the old spell**
  (owner, 2026-10-27): `IS_NPC(ch)` casts 8d8 and the old bolt table,
  because the 99 `spec_cast_cleric` mobiles (median level 22) otherwise
  flamestruck for about five times their level, past harm's cap.
- After them every main-class build sat at 174-256 a round at level 50
  (24-round yard fights, self-buffed, equal gear) -- the monk's band.
  The necromancer and M/M's meteors stay above it on purpose. Faster
  kills for everybody make the Hyrule guardians' calibration (a median
  player loses alone) easier; retune them by the simulation in
  `wiki/hyrule-area.md` if that matters, never by nerfing a class.
  `area/dpsboard.txt` was not reset: the standard fight did not change,
  only who hits how hard.

The tools: `tools/class_balance.py` (`milestones`, `gaps`; the 18 builds'
kits from `const.c`), GAINLIST PREVIEW (the same in game, held to the tool
by `tests/test_gainlist_preview.py`), and `tools/class_bench.py`, which
makes synthetic Z fixtures in disposable worlds -- staff ADVANCE for the
game's own hit point rolls, equal gear, "core" (given skills at 75%) or
"full" (everything learnable at 100%) -- and fights the yard dummy in
`auto`, `self` or `hermie` mode. The yard counts only the player's own
blows, so servants and pets are not in its numbers. A run is one sample
of 12 rounds; differences under about a third are noise. It uses the
repository's `merc` unless given `--binary`; never rebuild that while a
bench runs.

**Two progression rules look like bugs and are left alone pending the
owner's call.** `advance_level_body` reads `get_curr_stat`, so INT, WIS
and CON lent by spells and gear at the moment of a level count toward
the permanent gain. And every mana range there is
`number_range(int_app[INT].mana_gain, (INT+WIS)/k)` with the lower end
above the upper (40 against 12 at INT 18), so `number_range` returns the
lower end and mana a level is a step function of INT alone, before the
class and guild factors (x1 pure casters, x3/4 hybrids and monks, x1/2
warrior and thief in their own guilds). Together: a pure caster levelling
under EMPOWER (INT 18 to 25) gains about 81 mana a level instead of 41,
for good; CON adds only about 3 hit points. Swapping the endpoints would
cut every future level's mana by about a third. Either change is a
policy decision with lasting effects on characters, not a local fix --
and never fix it by changing `number_range`.

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
it -- and before the fourth remort it puts back whatever was kept, so a
shadowmeld an immortal gave with SET SKILL survives the next remort too
(it was wiped until 2026-10-20). **GRANTPSI's deferred flag sets the flag
and nothing else**: it also zeroed `psionic` and `last_level`, and the
second sends the next login through `reset_char`'s full rebuild of the
permanent stats. `load_char_obj` grants it to anyone at `REMORTS_FOR_SHADOWMELD` who
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

**Limbo is not AFK protection** (owner, 2026-10-23). An idle player is
moved to Limbo and any command brings them back (`stop_idling`), an
anti-idle client trigger included -- Alaric's client answered the void
with WHO and WORTH and walked him back into the Korzath maze, where a
Shadowman killed him. That is working as intended: staying safe while
away is shadowmeld's, rope trick's and haven's job. Do not make
commands answer from the void without returning the player.

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

**A death keeps the stash; only leaving the game frees it.** `extract_char`
freed `pcdata->stash` on every call until 2026-10-10, and a death calls it
with `fPull` false while the player stays in the game, so the next save
wrote an empty stash. Alaric lost 51 objects to one death and 65 more to
the next, after re-stashing his gear for a remort in between. The free
sits under `fPull` now, and `tests/test_stash.py` slays a character and
checks the bag is still there, at once and after a fresh login.

**The death snapshot is the way back.** `player_snapshot_milestone(victim,
"death", true)` runs before the dead are extracted, so a `before death`
copy in `player/versions/<Name>/` holds the stash as it stood at the
moment of death. `PRESTORE <player> <stamp|number> STASH`
(`prestore_stash` in `act_wiz.c`, `stash_restore_from_file` in `save.c`)
reads only that copy's `#STASH` section with the loader's own `fread_obj`
-- enchantments, Hyrule levels and nesting included, laid out by the
snapshot's own `Vers` line, not the live character's -- and adds it to
whatever the stash holds now, changing nothing else. It works on a
player who is online (the live stash, saved at once, and they are told)
or offline (a loaded copy through `offline_player_load`, saved and
freed), takes a `stashrestore` copy first, and may push the count past
`stash_max`, which only refuses deposits until it fits. "Restored 35
objects" counts top-level objects, as the stash does; the 30 inside a
pack came back inside it. The whole-file restore would have taken a new
life's levels with it, which is why this exists. Alaric's two stashes
were put back this way on 2026-10-11 and survived his next death.

**Pick a snapshot by its stamp when the player is online.** Every save
adds a snapshot at the top of the PRESTORE list and renumbers the rest,
so a number typed a minute after listing can name the wrong file; the
list prints `stamp 20261010_162657` beside each entry and PRESTORE takes
it, or a unique prefix. Eight or more characters is always a stamp
(`20261010` alone is digits, and a list number is never that long); a
whole file name, `20261010_162657.death`, beats an untagged copy taken
the same second.

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

**Summon immunity is not a reason** (2026-10-20): `AB` is the builders'
default and refusing it left five areas in the pool. It had also been
the only thing keeping out mobiles nobody may fight -- The Watcher, level
55, stands in the Temple where `is_safe` refuses every blow -- so the
filter now asks `is_protected_npc()`, refuses anything standing in the
Temple or at the altar, and names Hermie, the dealer, the goblin and the
holiday bosses. A quest for a mobile that cannot be killed is a quest
that can only time out.

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

## Mining The Watch Log For Gaps

Two cheap sweeps find real gaps, and both were run on 2026-10-20
(`tests/test_help_keywords.py` pins what they found): every `help <x>`
a watched character typed, checked against the keywords of the topics a
mortal may read (an exact keyword wins in `do_help`, then a prefix, so
`help quest` reached QUESTION until QUEST was a keyword of AQUEST); and
the first word of every logged command, checked against the command
table and the socials -- a word refused many times is a command players
expect (`chat`, nine times). Alias names are logged as typed before the
expansion, so a short word repeated hundreds of times (`oe`) is somebody's
alias, not a refusal. Public channel lines in `log/channels.tsv` are the
third sweep: a shopkeeper saying "I don't trade with folks I can't see"
twice in three days is why the keeper now says what is hiding you.

**Two tools do those sweeps now** (2026-10-21), both reading the synced
files from `origin/main` after a `git fetch`, both from the repository
root, both stripping addresses from what they print:

- `python3 tools/log_report.py [--since 2026-10-20] [--player Name]` --
  players, `BUG:` lines with the commands before them, refused words
  (frequent ones listed apart as likely aliases), the same command five
  or more times running, deaths, black market and goblin events, coin
  picked up, and public chat. Never tells; they are not in the logs.
- `python3 tools/audit_players.py [--json] [--no-objects]` -- every
  mortal file against the game's own tables (`const.c`, `fixes.c`,
  `retired_objects`, the area files): a group or skill the class cannot
  hold, out-of-range values, a level past the remort cap, objects whose
  vnum is gone, and login fixes not yet applied. It exits 1 on any
  finding but a pending fix. The creation bug that handed every new
  character the mage's groups would have shown here weeks before a
  player asked about it in chat. Only files named 2-12 letters are
  characters; `Kyrus.Bu` and the like are hand-kept copies.
- `python3 tools/audit_maxload.py` -- each limited object's player-owned
  count in `area/maxload.txt` against the copies the player files hold
  at every depth, stash included. Read-only; it exits 1 when any count
  differs. On 2026-10-21 all twelve differed slightly (the shallow
  counting fixed that day), every one far below its cap; correcting the
  totals is the owner's decision and would have to be done on the host,
  since the state sync carries maxload.txt host to git.

A routine runs both each morning in a fresh cloud session and reports
without changing anything. `tests/test_ops_tools.py` holds the table
parsing to the source.

## The Black Market

`src/blackmarket.c` (owner's design, 2026-10-20). Vesh the Smuggler, mob
29940 (`MOB_VNUM_BLACK_MARKET`) in `seasonal.are` with a shop that buys
nothing, is **a rare spawn, in the world about one hour in ten**: a visit
of twenty to forty minutes, three to six hours away, the first visit ten
minutes to six hours after a boot. His long description opens `(Rare)`
and his LOOK says plainly what he is and how he trades. While he is
about, `black_market_update()` (every mobile pulse) moves him every 45-75
seconds -- a step through an exit, or one move in eight a vanishing to a
random room -- never into a room `bm_room_ok()` refuses: guild halls
(`guild_hall_rooms()` in `special.c`, `guild_closed_rooms`' walk with
nobody admitted), staff, newbie, hero, private, no-mob, death-trap and
exitless rooms, and Hyrule, the yard, `seasonal.are`, the Quest Zone and
Temple Despair.

**One find, one customer** (owner, 2026-10-20: so several people cannot
buy from him in one place, but whoever finds him has time to buy one of
everything). A mortal standing with him has `BM_BROWSE_MAX` (90 s) to
start buying before he moves on. The first purchase opens a sale window
for that buyer alone -- `BM_SALE_FIRST` (60 s) plus `BM_SALE_MORE` (30 s)
per further purchase -- and anyone else is told he is with a customer.
When the window closes, the buyer leaves his room, or the buyer has had
one of everything, he vanishes to a random room with a line to the room.
His stock stays the same for the whole visit.

**Edge cases, checked 2026-10-20.** `black_market_sees()` wants the
looker in the room's `people` list, not just `in_room` pointing there:
CLAIRVOYANCE sets `in_room` to a friend's room for its LOOK, and showed
him. SCAN does the same on purpose and is let through by its own `scan`
flag. `can_see_obj` asks the holder (`black_market_holder`), so a copy
staff MLOAD does not read the real dealer's room. That copy is not the
market either: `black_market_buy_refuses` sends anyone away from a
keeper that is not `black_market_dealer`, so it cannot open a sale
window or record a purchase against the live stock. **He never dies**:
`black_market_cheats_death()`, asked first in `raw_kill_internal`, sends
him off whole to a random room (a staff slay sends him off the world
instead, so no corpse ever holds his stock), and `black_market_forget`
gives any other exit the away time, so he cannot come straight back with
a fresh stock on his old leaving time. A fight somebody started with him
is stopped each pulse, and his moves are topped up so a walk never
strands him. `add_hate` and a backstab's fatality refuse him and the
goblin both.

**Ten minutes in one area and he crosses the world** (owner,
2026-10-20): `bm_area_stale()` times the area he stands in, and at
`BM_AREA_MAX` he vanishes to a room in another (`bm_random_room_away`)
-- only when nobody is with him and no sale is open. The treasure goblin
does the same at `GOBLIN_AREA_MAX` while nobody is with or after him.

**Logged -- but never where he is now.** `log/` reaches a public
repository every five minutes, and he stays twenty to forty minutes, so a
logged room was a map to him (found in review, 2026-10-20: the synced log
named his room within minutes). Arrivals (stock size, how long) and
purchases (buyer, item, vnum, price) go to the log without a room;
WIZINFO, which only staff online see, carries the room as well.
Departures and vanishings log the room he *left* and why, never where he
went, and a staff summons logs who called him, not to where. The goblin
follows the same rule. `bm_where()` writes a room the same way wherever
one is allowed.

**Rooms he never stands in**, beyond the list above: sky, deep water and
under water (`SECT_AIR`, `SECT_WATER_NOSWIM`, `SECT_UNDER_WATER`), which a
walker cannot follow into and the goblin could not run out of -- the logs
had him on a cloud, the Dragon Sea and a whirlpool; `ROOM_TELEPORT` and
`ROOM_RIVER`, which carry mobiles too (one drops on the Temple altar,
one in a no-mob death trap), and any room holding another shopkeeper --
`find_keeper` takes the first in the room, so he took over the shop.
Nobody may FOLLOW him or the goblin (`do_follow` asks
`is_unfindable_mob`): it walked a follower after every step and every
flight. His goods are seen by anyone with him who is not blind, dark
room or not (`can_see_obj`), since he wanders into night fields where
LIST otherwise said nothing was for sale.

**He is seen in his own room and nowhere else.** `can_see` asks
`black_market_sees()` after the wizinvis test and before the immortal-mob
shortcut: staff see him anywhere, nobody else from another room, and
PROJECT's stand-in (`MOB_VNUM_PSIONIC_PROJECTION`, now in `merc.h`) never.
Every remote finder -- `get_char_world`, `travel_target`, WHERE,
clairvoyance, TRACK, summon -- goes through `can_see`, so they all miss
him; `can_see_obj` hides his goods (`black_market_holds`), which is what
LOCATE OBJECT asks, and `oracle_can_see_char` refuses him by name. SCAN
steps the scanner into each neighbour, so it sees him one room out, and
skips him further out. A new way of finding a character elsewhere must go
through `can_see` or ask `is_black_market_dealer` itself. TELEKINESIS
only pulls what lies in rooms, so his pack is out of its reach anyway.

**The stock is chosen from the world, at run time, and the pool is
hundreds deep** (owner, 2026-10-20). `bm_build_gear()` marks every object
a G or E reset puts on a mobile outside the skipped areas and staff rooms,
then keeps, for each wear slot (`wear_obj`'s order) in each band of five
levels **from `BM_GEAR_MIN_LEVEL` (29) up** (owner, 2026-10-20: best in
slot from 29, and below that only what is otherwise rare or
unobtainable), the three highest scorers (`BM_PER_SLOT`): damroll,
hitroll and stats first, then hit points, armour and a weapon's average
blow -- up to 294 pieces; BLACKMARKET reports how many the world fills.
The rarities below come at any level. Load-limited,
no-drop, no-remove, rot-death and quest-token items are never sold. **He
carries `BM_STOCK_MAX` (five) things at most**: a holiday boss's drop at
40%, a training cake at 30% (the two holiday cakes; Valhalla's wedding
cake, 9955, was taken off the list because `maxload.txt` limits it to one,
and `bm_stock_one` now refuses anything load-limited) and a lucky clover
at 30% (Valhalla's 9943 and 9944) are
rolled first, and the rest is drawn from the pool, each made with
`create_object` at a negative level so nothing is randomised.

**Nothing progression-based, ever** (owner, 2026-10-20). `bm_progression()`
refuses Hyrule's whole object range (`BM_HYRULE_OBJ_FIRST`-`LAST`,
30200-30999: the Triforce and its pieces, the Master Sword, the
guardians' keys and treasures), every `ITEM_KEY`, and any object a door
or a container in the world takes as its key; both the gear table and
`bm_stock_one` ask it, so a hand-written rare list cannot slip one in.

**Prices.** The standard price is sixty kills of the item's level
(`bm_kill_value`, the averages of `mob_index_set_wealth`) or three times
its cost, whichever is more, and a cake forty level-50 kills. **Anything
no reset puts on a mobile costs `BM_RARE_MARKUP` (five) times that**
(owner, 2026-10-20: black market stuff is expensive and hard to get) --
the holiday drops, the cakes, the clovers. Rounded to whole coins, never
haggled. Because the standard is anchored to the item's level, a low
level rare piece stays cheap even marked up: the level 5 clover is about
fifteen gold.

**One of each, per character, per stock.** The stock's id is the time it
was rolled; `pcdata->black_market_stock` and `black_market_bought` (the
vnums) save as `BlackMarket <id> <vnums>~` under **case 'B'**, written
at the purchase. A new visit is a new allowance. `extract_char` calls
`black_market_forget`, so a PURGE cannot leave a dangling pointer, and
`is_safe` already refuses any shopkeeper. `TOC_BLACK_MARKET_STILL` holds
his wandering, his browsing limit and his departure for the live tests;
the sale window still runs, so the tests can watch it end.
`tests/test_black_market.py`.

## The Treasure Goblin

`src/goblin.c` (owner's design, 2026-10-20, after Diablo's). Mob 29941
(`MOB_VNUM_TREASURE_GOBLIN`) in `seasonal.are`. **There is always one**:
`treasure_goblin_update()` (every mobile pulse) spawns one at boot and
another a minute to three after a death, at a room `gob_room_ok()`
allows -- the black market's rooms (`black_market_room_ok`) less safe
rooms, the Temple and the altar, because a goblin nobody may strike is a
goblin nobody can finish. He is a sentinel to `mobile_update` and does
his own wandering under the same rule. **He is hidden as the dealer is**:
`is_unfindable_mob()` covers both in `can_see`, SCAN and the Oracle.
`TOC_NO_GOBLIN` stops the automatic spawn and `tests/live_mud.py` sets
it by default; `TOC_GOBLIN_STILL` holds his wandering and his portal.

**The chase.** `damage()` asks `treasure_goblin_blow()` before its
message: a landed blow takes a share of his health set by how hard it
hit -- one thirteenth for 160 damage and up, one eighteenth below 15
(owner, 2026-10-20: a level 50 must not finish him in a few blows, and
a low level must still be able to) -- so hit points never decide who
can kill him and the floor is twelve flights. After the blow, if he
lives, `treasure_goblin_struck()` spills coin and sends him through a
random exit with `move_char`, after `stop_fighting(gob, true)`, so a
caller's `ch->fighting != victim` check stops the swings that follow;
`gone_after_blow()` reads him as gone. **Nothing holds him** (owner,
2026-10-21: immune to stuns, always flees after a hit):
`gob_shake_off()` strips a stunning blow, sleep, confuse and maze and
stands him up, in `_struck` before every flight and every pulse in
`treasure_goblin_update`, and `do_confuse` refuses him outright through
`treasure_goblin_refuses_daze()` before any mana is spent -- confuse
deals no damage, so it never made him run, and a confused mobile's
step is picked at random by `move_char`, past `gob_pick_exit`'s choice
of a room he may stand in. `multi_hit` returns at once for him: he never
strikes back. His own poison and plague do nothing to him. His hit
points are clamped each pulse so a tick's regeneration cannot undo a
chase.

**The portal.** As in Diablo, a chase has to be kept up: `GOBLIN_ALONE`
(60 s) without a blow and he starts a portal, through it a pulse later
to a random room, wounds kept; a blow while it opens collapses it.

**The money is counted in kills.** Spills are four to eight, and the
hoard about two hundred, of `black_market_kill_value()` at the striker's
or killer's level (a pet's master's), so it is worth chasing at every
level. `treasure_goblin_slain()` runs in `raw_kill_internal` before
`make_corpse`: the hoard goes into his purse with `gain_copper` and out
into the corpse as piles, with half the time
`black_market_gear_for_level()` -- the best placed piece for a random
slot within five levels below the killer's -- and a tenth of the time a
black market rarity.

**An instant kill is a hard blow.** `treasure_goblin_cheats_death()`,
asked first in `raw_kill_internal`, turns a death ray, a fatality or a
farslayer into one blow of the largest share (a thirteenth) and a flight;
only a death `damage()` already decided (`POS_DEAD`) or a staff slay kills
him -- and the blow is a share of where the last real blow left him:
a farslayer sets his hit points to 1 before `raw_kill`, so
`cheats_death` puts back `gob_hp` before subtracting. Healing does not
help him either: `treasure_goblin_blow` and `_struck` hold him at or
below `gob_hp`, or a cleric healing between a partner's blows kept him
spilling coin for ever. His moves are topped up so he never runs out.
**One share a flight** (`gob_floor()`): his hit points may not fall
below one hardest share for every flight so far and one more, so he
cannot die before his twelfth flight; a blow that would take more
takes nothing, and he still runs. History, so nobody brings it back:
for one night bash, trip and stunning blow *held* him, and a hold let a
fighter's rounds land shares with no flight -- Trentlin's bash wore one
down that way on 2026-10-21 and Misery finished it in two blows. Flights
are counted (`gob_flights`) only when he leaves the room; the kill line
says how many. A copy staff MLOAD runs and spills like him but leaves the real
goblin's chase clocks alone, and his hoard is capped where `long` is 32
bits. Appearances go to the log and WIZINFO, the room to WIZINFO only;
kills to both with the room (he is dead); escapes and drifts to the log
with the room he left. Staff command GOBLIN.
`tests/test_treasure_goblin.py` chases one down live.

## Alignment

`src/alignment.c` (owner, 2026-10-21: rebuilt to be "more modern"; the
design was chosen from four options -- a tiered single axis, kills plus
Temple deeds plus quests, tier perks plus an XP bonus plus shop prices,
and existing values kept). The number is unchanged on disk (`Alig`) and
`IS_GOOD`/`IS_EVIL` still start at 300/-300, so the 615 anti-good,
anti-evil and anti-neutral items and every spell that reads a side mean
what they did. The rules:

- **Every change goes through `alignment_shift()`.** It clamps, tells a
  DAMAGENUMBERS player the small moves, tells everyone a change of tier
  and logs it with `watch_log`. Do not write `ch->alignment` anywhere
  else in gameplay code; SET and the loader are the exceptions.
- **You are what you slay** (`alignment_kill`, from `xp_compute`): the
  side opposite the victim's, a point per hundred of its alignment, half
  eight levels down, nothing fifteen down; neutral and `ACT_NOALIGN`
  victims (every school monster, by race) move nothing. The old rule
  pushed you away from every victim, so -1000 and 1000 were one-way doors.
- **No kill pays less** (`alignment_xp_percent`): 100%, plus 10% a tier
  for slaying the other side, 10% for the balanced slaying either.
- **Perks are for players only**, at three hooks: `alignment_damage_mod`
  before `check_immune` in `damage()`, `alignment_drain` inside the block
  where hit points really come off (so the dummy, which absorbs, feeds
  nobody), and `alignment_regen` at the end of `hit_gain`.
- **Shop prices** go through `alignment_price()` at all five `get_cost`
  call sites in `act_obj.c`; the black market is exempt. A new price
  shown to a player must be wrapped the same way. **Nothing may pay a
  player above list or sell below worth**: no shop's buyback exceeds 100,
  so that is what keeps buying at one shop and selling at another from
  being a loop -- and **a haggled sale is capped at worth** for the same
  reason, from the unadjusted list price. The first draft paid a tenth more to a keeper's own side,
  which opened thousands of them; `test_alignment.py` brute-forces the
  floor and checks every shop's buyback.
- **`alignment_shift(ch, delta, loud)`**: loud reports small moves to
  DAMAGENUMBERS and takes off gear when the side changes. A vampiric
  weapon's point a hit is quiet -- a line a swing was spam, and zapping
  the weapon mid-swing pulls it out from under the blow. Tier changes are
  always announced. GMCP `Char.Status` carries the `tier`, resent only when it changes.
- **The dark's drain** counts only the hit points the victim had and
  never the treasure goblin, whose damage is a share of his health.
- **Gear checks** are `alignment_rejects_obj()`; `test_alignment.py`
  fails on an open-coded `ITEM_ANTI_EVIL && IS_EVIL`.
- **DEVOTE** is a Temple deed (4207 or the altar 4208): `ALIGN_DEED_SHIFT`
  for `ALIGN_DEED_KILLS` kills' coin, `ALIGN_DEED_COOLDOWN` apart, saved
  as `AlignDeed <epoch>` under **case 'A'**, clamped to one wait on load.
- `alignment` and `devote` sit after `alias` and `deposit` in the command
  table, so `al` is still ALIAS and `de` still DEPART.

## Rested Experience And Daily Quests

Both after World of Warcraft (owner, 2026-10-20).

**Rested** lives in `src/rested.c`. `rest_xp_on_quit()` runs in `do_quit`
before the save and asks `rest_room_ok()`: safe, hit point or mana
regeneration rooms, the Temple, the altar (the pit healer) or the
character's `recall_room()`, never a jail; an idle character already moved
into the void is judged by `was_in_room`. `rest_xp_on_login()` runs in the
nanny beside `psionic_login` -- a real login only, never a reconnect -- and
banks `REST_PERCENT_PER_HOUR` (5) of a level per hour since `last_logout`,
to `REST_CAP_PERCENT` (150). `group_gain` adds `rest_xp_bonus()` to each
kill: as much again, while the pool lasts, and nothing where `gain_exp`
would refuse it (level 50, the remort cap). Saved as `Rested <pool>
<eligible>` under **case 'R'**. Less than `REST_MIN_AWAY` (15 minutes)
away is a relog, not a rest, and banks nothing; the minutes are capped at
what fills the pool before they multiply a level's span, which a hero's
span times a long absence would otherwise overflow in a 32-bit `long`.
`rest_xp_clamp()` holds the pool to a level and a half **of the level
the character is now**, at login and at every draw: the cap used to be
applied only when rest was added, so a hero's pool carried through a
remort doubled about ten levels of a level 3's kills. The login line for
somebody who did not quit somewhere safe says they come back unrested,
not that they "slept rough": a crash, a lost link and a file from before
rest existed all land there too.

**REMOVE CURSE leaves Hyrule's bound items alone** (`hyrule_bound_object`
in `hyrule.c`: a NODROP object in `HYRULE_OBJ_FIRST`-`LAST`). Triforce
pieces and the old men's gifts are NODROP so one character cannot carry
another through, and the spell stripped NODROP from anything; the pit
healer now refuses an uncurse, free, when `remove_curse_has_work` finds
nothing to lift. **REPAIR ALL** mends everything worn and carried,
cheapest first, as far as the purse goes (`repair_all`, `repair_mend`).

**Dailies** live in `quest.c`, beside the ordinary quest and apart from
it: `ch->questdaily` marks one, cleared on the line after every
`questemergency` clear (`tests/test_rested_and_dailies.py` checks), and
`complete_automatic_quest` hands a daily to `complete_daily_quest`, which
pays coin and daily points and never touches the gamble, the streak or
`nextquest`. **The prices are a promise** (owner, 2026-10-20: every daily
for a month buys about one train): a point a daily, one for the set, and
`daily_streak_bonus()` for days in a row with all three; a train is
`DAILY_TRAIN_COST` (160) against a perfect month's 162, which
`tests/test_rested_and_dailies.py` recomputes from the constants. Change
one and check the month still lands on a train. Abort, timeout and logout spare a daily the streak and the
cooldown. **Giving a daily up costs `DAILY_GIVE_UP_WAIT`** (ten minutes
before the next daily, saved as `DailyWait <epoch>` under **case 'D'**
while it runs): without it, abandoning and asking again rerolled the
target until it stood next door. A request that finds no target puts
`nextquest` back as it was, since `generate_quest` sets it. GMCP's quest
feed sends the target room's `num` to staff only, as WALKTO QUEST is;
the Mudlet client falls back to walking to the area. **The ordinary
cooldown runs while logged out too** (`quest_login_cooldown`, from the
nanny): `quest_update` only counts characters in the game, and Trentlin,
back after nine hours, was told to wait fourteen minutes. `quest_update` decrements the cooldown and a quest's countdown
side by side -- they were an if/else, which froze a daily taken during a
cooldown. Saved as `Daily <points> <day> <done> <streak> <last full day>`
under **case 'D'**, the day
being `current_time / 86400`. **The day does not turn under a daily
that is out**: `quest_daily_rollover` waits for `questdaily` to clear, and
a finished set's streak is judged by `daily_day`, the day it was taken --
otherwise a third daily finished at five past midnight UTC counted toward
the new day and cost the set and the streak. **Read each saved value into a local
before clamping it**: `UMAX`/`URANGE` evaluate their argument more than
once, and a `fread_number` inside one reads the file twice and desyncs the
loader -- the first draft of these keys hung the login.

## The Oracle's Sanctum Is No Inn

SLEEP in room 8 (`ROOM_VNUM_ORACLE`) is refused by
`oracle_refuses_sleep()`, asked first in `do_sleep` (owner, 2026-10-20:
kick them out immediately). Her supplicant's audience ends through
`oracle_dismiss(TRUE)`; anyone else goes to `oracle_saved_room()`'s
answer. Staff are exempt. `tests/test_oracle_sanctum_live.py`.

**Coming back from her is a minute's daze on the clock, never lag**
(owner, 2026-10-27: it looked like the mud was lagging). It was
`WAIT_STATE` for a tick, and lag counts down only while a command waits,
so the first command typed sat unanswered for a minute.
`pcdata->oracle_daze_until` (memory only) is set by `oracle_come_back`;
the input loop asks `oracle_dazed()` before running any line and refuses
all but QUIT and a blank line, saying how many seconds are left;
`oracle_daze_update()` (every pulse) says when it ends. `TOC_ORACLE_DAZE`
shortens it for tests. **A prayer said in a `ROOM_SAFE` room comes back
with no daze** (owner, 2026-10-27): `oracle_come_back(ch, prayed_from)`
is given the room prayed in -- the altar (4208) is safe, the Temple floor
(4207) is not.

## Disasters And The Black Dragon

`src/disaster.c` (owner, 2026-10-23: fix them, rework them, and let the
black dragon carry you off to a fight you choose). `disaster_update()`
runs every six or seven seconds from `update_handler`; an occupied area
other than Mud School and Limbo is struck two times in ten thousand per
cycle (`DISASTER_CHANCE`). The rules:

- **A disaster warns before it hurts.** The cycle that starts one only
  tells the area (`disaster_warning`); `disaster_warned` is set on the
  next cycle, which strikes, and every cycle after that ends it half the
  time or strikes again. Fire, tidal wave and the dragon strike once.
- **It never kills.** `disaster_harm()` leaves one hit point and takes
  them off directly -- not through `damage()`, which would make the
  victim their own attacker and feed the dark's drain and a vampiric
  weapon from their own wounds. An earthquake knocks the character down
  (`POS_SITTING` and a round of lag); nothing sets `POS_STUNNED`, which
  lasted to the next tick.
- **Shelter** is `disaster_spares()`: NPCs, staff (by level),
  characters below `DISASTER_MIN_LEVEL` (10), and the Temple, the altar,
  safe rooms and arenas (the training yard). A flood sweeps through real
  moves (`move_char`), so guards, private rooms and Hyrule's gates still
  refuse it.
- **The weather decides two of them**: a flood needs rain, a lightning
  storm `SKY_LIGHTNING` (it needed clouds). Staff DISASTER ignores the
  weather.
- **The dragon** (mob 4474) is created per encounter: `dragon_snatch()`
  takes one character in the area who is a mortal of level 10 or more,
  outdoors, linked, out of a fight and not in a no-recall room or jail,
  to another outdoor room of the same area (`dragon_landing`: no NO_MOB,
  safe, private, teleport, river or death-trap room, nothing
  `travel_spell_refuses`, no other player) and lands beside them,
  `dragon_scale`d to two levels above them with three times
  `dummy_typical_hp` at that level. It is not aggressive and has no spec
  fun; `spec_kidnapper` is inert, kept so the area file loads. It leaves
  `DRAGON_WAIT` (180) seconds after landing, or `DRAGON_PREY_GONE` (15)
  after its prey leaves, never during a fight. Killed, its hoard goes
  into its purse before `make_corpse` (`disaster_dragon_slain`, from
  `raw_kill_internal`), as the goblin's does: `DRAGON_HOARD_KILLS` kills'
  coin and **always a piece of gear** from `black_market_gear_for_level`
  at the level of the one it took (`dragon_prey_level`, kept even if they
  quit; owner, 2026-10-23), with a rarity on top `DRAGON_RARE_CHANCE` in
  a hundred or when the level finds no gear. `extract_char` calls
  `disaster_dragon_forget`; the quest master never picks it.
- **Logged without the room it waits in**: who was taken and from which
  area file; WIZINFO carries the rooms. `TOC_DRAGON_WAIT` shortens the
  wait for the live test (`tests/test_disasters.py`).

## The Holiday Bosses

The Headless Horseman (29910) and Father Winter (29911) in
`area/seasonal.are` are **not aggressive and do not wander** (owner,
2026-10-20): `ABGV`, sentinel and stay-area. They were `AFGV`, so a
boss announced in the square had walked off by the time anyone arrived
-- the undead race's departure line read as fleeing -- and attacked
whoever it met on the way. Their drop tables are `horseman_drops` and
`father_winter_drops` in `season.c` (`EVENT_DROP`: vnum, percent, role),
read by `make_corpse` to roll the loot and by `show_char_to_char_1`
through `event_boss_show_drops()` so LOOK tells the player what falls
and how often; the FALLBACK row is added when nothing else fell. Change
a drop in the table, nowhere else. `tests/test_event_boss.py`.

## Wizinvis Leaves No Trace

`wizinvis_hides(wch, looker)` in `handler.c` is the one test for whether
a wizinvis player is hidden from somebody: `PLR_WIZINVIS` at a level
above the looker's `sight_trust()`. `can_see` asks it first, and
`act_new` in `comm.c` asks it to **drop** a wizinvis actor's `TO_ROOM`
and `TO_NOTVICT` messages for anyone it hides them from, rather than
deliver them with "someone" in the name's place (owner, 2026-10-20:
nobody below the level sees anything). `PERS()` says "someone" for
anyone unseen; it used to say "An Immortal" for an unseen immortal,
which announced every wizinvis recall to the room. Messages aimed at a
victim (`TO_VICT`) still land, and name an unseen immortal "an
immortal" (owner, 2026-10-23: a poke or a tell from staff says so; a
poof stays unseen): `pers_acting_on()` in `handler.c` decides it, for
`act()`'s `$n` in `TO_VICT` and for TELL, REPLY and GTELL. What a room
sees stays `PERS()`, "someone". `act()` capitalises the first letter
past any leading colour escapes, so "An immortal pokes you" is not
"an immortal" behind a social's colour code. The per-recipient
loops that bypass `act()` were audited on 2026-10-20 and each already
asks: `do_goto`'s bamf loop (trust against `invis_level`), WHO and the
GMCP online feed (`online_can_list`), `show_char_to_char`, `do_count`,
`do_where`, `do_scan` and the GMCP room list (`can_see`). `do_say` tells a
wizinvis speaker when nobody below the level heard, and its chat-pane
loop skips them too; a new per-listener loop that bypasses `act()` --
as `do_goto`'s bamf loop and the GMCP feeds do -- has to ask the helper
itself. `tests/test_wizinvis.py` walks, speaks and recalls past a
mortal both ways. **A staff notice naming somebody goes out at their
`staff_notice_level`, and one naming two at the higher of the pair's**
(`staff_notice_level_pair`): resurrection, EMPOWER, TITANIC (staff and
crafted) and GRANTPSI named a wizinvis participant to every builder until
2026-10-26. A spell's spoken words reach each listener by `TO_VICT`, so
`say_spell` skips anyone `wizinvis_hides` the caster from
(`tests/test_notice_visibility.py`).

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

**No GMCP string carries colour.** `gmcp_json_append_quoted()`, which
writes every one, drops `{HH` tokens: the client draws GMCP text in its
own windows, and a coloured gossip reached Mudlet's chat pane as
"{0Bshiny" (2026-10-23). A change to the package's Lua bumps
`TOC_MUDLET_PACKAGE_VERSION`, `config.lua` and `tocMudlet.version`
together, or installed packages never fetch it.

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
  aimed at exactly their peers. The exemption covers peers and those below: trust
  71 and the creator outrank every implementor (next section). Commands that should not target the user
  keep their own `victim == ch` guard; rank is a separate question.
- `is_loopback_ip(ip)` -- one place that knows what 127/8 means, used to
  keep the healthcheck's two-minute probe out of the log and to decide
  whether a PROXY header may be trusted.

## The Creator And Trust 71

Owner, 2026-10-22. Levels still stop at `MAX_LEVEL`; above it are trusts.

- **The creator is a saved flag** (owner, 2026-10-22): `pcdata->creator`,
  written `Creator 1` under **case 'C'** only when set. `is_creator` is
  true for it and, always, for the founder, Killuminati
  (`is_creator_founder`, by name, `is_killuminati` in `oracle.c`).
  `get_trust()` returns `LEVEL_CREATOR` (72) for a creator, through a
  switch too, whatever their level; WHO shows the level. CREATOR
  (`do_creator`, at CR) lists the creators online, and the founder alone
  grants or takes the rank, online or in an offline file
  (`offline_player_load`), with a `creator` snapshot first, a log line
  and a creator-only WIZINFO. Nobody takes it from the founder, and
  `rank_protects` lets no other creator act on him, though they share 72.
  Taking it brings the WIZINVIS level down to the trust that remains.
  **Nothing else asks the name.** The rank asks `is_creator`; the
  protections that come with it ask `is_creator_in_person` (his own body,
  never a mobile he has switched into): he cannot die -- `damage()` holds
  him at one hit point like an immortal at any level, so a blow records
  no kill and costs nothing, and `raw_kill_internal` turns every instant
  death aside -- SLAY and FARSLAY strike down whoever throws them,
  `is_divinely_warded` covers him against fatalities and death rites, and
  his deaths take no snapshot. A creator granted the flag has all of it.
- **TRUST gives up to `LEVEL_TRUST_MAX` (71)**, limited to the giver's
  own trust, so only the creator gives 71; `get_trust` caps any stored
  trust at 71. TRUST refuses a target who outranks the giver. 71 outranks
  every implementor and is outranked by the creator.
- **Creator-only commands** sit at `CR` in `interp.h`: SHUTDOWN, REBOOT,
  LOG, SNOOP, BAN, ALLOW, WIZLOCK, NEWLOCK, DENY, UNDENY. Leave FSAVE and
  ANNOUNCE alone: `toc-deploy` sends them through the webadmin queue at
  trust 70. A live test that needs one of these uses a synthetic
  Killuminati -- the creator is a name, and test worlds start with an
  empty `player/`.
- **WIZINVIS defaults to the character's trust**, so his is 72 and hidden
  from everyone; WIZI 71 lets trust 71 see him. **He always logs in
  wizinvis**: at 72 unless he left wizinvis at a level he chose, set in
  the nanny right after `login_reload_character`, before the first
  notice. Arrival, departure,
  lost-link, reconnect, shared-address and TRUST notices go out at
  `staff_notice_level(ch, level)` -- no lower than the subject's WIZINVIS
  level -- and `wizinfo` picks listeners by `get_trust`. Every one is
  still written to `log/toc.log`, which is published.
- **Never test trust for exactly 70.** Write `get_trust(ch) < MAX_LEVEL`
  or `>= MAX_LEVEL`; `== 70` locks out 71 and 72. Object levels stop at
  `MAX_LEVEL`: LOAD's default is `UMIN(get_trust, MAX_LEVEL)`.
  `tests/test_creator_rank.py`.
- **From the independent review (2026-10-22)**: TRUST 71 asks
  `is_creator`, not only the giver's trust, or a 71 passes it on;
  ADVANCE, SET CHAR and SET SKILL ask `rank_protects` for a player other
  than the caller, before the snapshot; SET CHAR ... DENY and PARDON ...
  DENY are the creator's, like DENY and UNDENY -- a creator-only command
  with a second route through another command is not creator-only; a
  notice naming two people goes out at the higher of their
  `staff_notice_level`s; and WHO and SOCKETS ask `can_see` of the
  original as well as the body, because a switched character is listed by
  the original's name. A new listing that prints `d->original` asks the
  same.
- **From the review of 2026-10-23**: RESETPWD asks `rank_protects` of
  the loaded target before freeing it -- two trusts of 72 compared by
  hand let a granted creator reset the founder's password. **PRESTORE
  never restores a creator flag**: the copy is line by line, drops the
  snapshot's `Creator` line and writes the character's current flag
  before the player section's `End` -- a snapshot from before CREATOR
  OFF handed the rank back. CREATOR alone changes it. **A snoop is
  rechecked at every forwarding** (`snoop_still_allowed` in `comm.c`:
  SNOOP's level from the command table, and `rank_protects`), so losing
  the rank ends one in progress. SLAY and FARSLAY ask `rank_protects`
  beside their own tests, after the creator's backfire. The creator's
  arrival unseen is `creator_arrives_unseen()`, called after the password
  on a fresh login and in `check_reconnect`, before either's notices.

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

## Contracts From The October 2026 Audit

An outside audit (2026-10-21) found these; each is fixed, and each has a
test that fails on the old code. Keep them.

- **Build a replacement string before freeing the old one.** `do_stash`
  freed `stash_links` and then read it to build the new list; the pool
  reuses a freed block's first bytes, so a second LINK wrote allocator
  bytes before the first partner's name and locked them out
  (`tests/test_stash_link.py`). ASan cannot see this through the pool.
- **Changing a worn piece's armour values: `+= apply_ac` at the old
  values, change them, `-= apply_ac` at the new** -- `unequip_char` adds
  and `equip_char` subtracts. Heat metal and acid breath had the signs the
  other way round and left a permanent AC bonus; heat metal also filed a
  removable piece down before unequipping it. Unequip first, then file
  (`tests/test_armor_bookkeeping.py`).
- **`is_safe_spell` refuses the Temple, the altar and `ROOM_SAFE` exactly
  as `is_safe` does.** Both tests were commented out, so poison landed
  where MURDER was refused (`tests/test_safe_room_spells.py`).
- **After anything that can kill, ask `gone_after_blow(ch, room)`, never
  `in_room == NULL`.** A slain player is moved to the death room, not
  extracted, so a lethal trap on the way out let the dead walk through
  the exit (`tests/test_trap_movement.py`; every `room_affect` call in
  `act_move.c` and `update.c`).
- **Damage is condition, never worth.** A dent, a heat or an etch files
  armour down and takes `REPAIR_DENT_WEAR` condition, so REPAIR sees it;
  `obj->cost` is left alone, and a shop pays a third for an
  `ITEM_DAMAGED` piece in `get_cost`. Repair restores condition and armour
  values, never worth: raising `obj->cost` to the prototype's undid the cap
  a discounted purchase sets, and bought low and sold high
  (`tests/test_repair_gear.py`, `tests/test_gear_damage.py`).
  `repair_needed` also counts armour filed below its prototype, which is
  how a shield dented before this reads.
- **A playing character's save writes `LastOut` as now**
  (`saved_last_logout` in `save.c`); memory keeps the previous logout for
  HISTORY's marker. A shutdown saved everyone before `close_socket`
  stamped the departure, so a restart counted the sitting as time away
  and cleared quest cooldowns (`tests/test_rested_and_dailies.py`).
- **A command's privacy is its inner command's.** `line_privacy()` in
  `interp.c`: ALIAS is secret (its body may hold a password, and `alias
  <name>` answers with it), and AT, FORCE and ORDER take the privacy of
  the command they carry. Every log sink -- the journal, the watch log,
  the unwatched LOG_ALWAYS line -- asks it (`tests/test_playlog.py`).
- **MCCP drains until the flush is done, and DONT COMPRESS2 finishes the
  stream** (`Z_FINISH` to `Z_STREAM_END`) before any plaintext; a stream
  that cannot finish closes the connection rather than writing plaintext
  into it. `tests/test_mccp.c` runs the real `telnet_proto.c` and
  `tests/test_mccp.py` decodes it with zlib.
- **HISTORY TELL is tells only** (`HISTORY_NO_CHANNELS`,
  `tests/test_channel_history.py`).
- **Corpse histories end `-1 -1`.** `99 99` also began a 99-item record;
  `corpse_history_read` (`save.c`) takes `99` as the old end marker only
  when nothing follows it, bounds every count, never exits on a short
  file, and returns how many records it found -- NEWCORPSE checks a slot
  against that (`tests/test_corpse_history.py`). Nothing writes these at
  present: `corpse_back`'s call in `fight.c` is commented out.
- **The Oracle's answer cache keys on everything per-player that changes
  the answer**: the guild in `_oracle_cache_key`, and a digest of the
  asker's ABILITIES in `oracle.poll_once`, the one place that has them
  (`tests/test_oracle.py`).
- **Full PRESTORE finds its target with `player_in_game`, never by
  sight**, refuses a login in progress, rank-checks an offline target
  from a loaded copy, and refuses a snapshot without `#END` before
  disturbing anybody (`tests/test_prestore.py`). Snapshots are written
  to `.partial` and renamed into place, so a crash mid-copy leaves
  nothing PRESTORE offers. **The chosen snapshot is pinned
  (`player_snapshot_pin`) until PRESTORE returns**: its own safety copies
  -- the forced pre-restore snapshot, the online target's save, the STASH
  form's milestone -- each rotate the directory, and at the limit the
  oldest copy, the one being restored, was deleted before it was opened.
  `do_prestore` is a wrapper that unpins on every way out.
- **Limited items are counted by whole subtree at every change of
  hands** (`maxload_subtree` in `handler.c`, used by the four transfer
  functions and the stash). The shallow counts undercounted a bag packed
  into another carried bag and overcounted at a quit two deep
  (`tests/test_maxload_nesting.py`). Totals already wrong in
  `maxload.txt` are not reconciled by this; that is a separate decision.
- **Cross-room SHOOT goes through `damage()`** and undoes the fight it
  starts between rooms (`tests/test_ranged_shot.py`).
- **Leaving password mode clears the field** in both browser consoles
  (`tests/test_secret_input.js`).
- **Remort** (report, 2026-10-21; `tests/test_remort_report.py`): a pet
  at its owner's side goes to the Temple with them; OUTFIT fills each
  empty slot, from a matching starter item already carried where there
  is one; practices and trains saturate at `SHRT_MAX`, never cut.
  OUTFIT takes only a carried piece `wear_requirements_quiet` (the WEAR
  checks, silent) accepts and confirms `equip_char` kept it, so a broken
  or heated piece is left in the pack and a new one made; and a monk's
  hand to hand gets the same `STARTING_WEAPON_SKILL` floor as the weapon
  a class starts with, since a monk who kept a sword has no dagger.
  OUTFIT also asks `shield_hand_free()`, WEAR's own test, before a
  shield: `equip_char` takes a shield off for a two-hander but never
  refuses one beside it, so a remort keeping a two-handed sword was given
  the school shield too (review, 2026-10-22).
- **No output may reach `alloc_mem` or the buffer ceiling whole.**
  `alloc_mem`'s largest block is 32,704 bytes and a larger request
  aborts the game; a descriptor's buffer stops at 32,000. CHANGES ALL
  grew past both on 2026-10-21: with paging on the pager asked for one
  block that size (a crash anyone could type), with paging off the
  connection was closed. `write_to_buffer` now sends what is queued and
  carries on, and `page_to_char` writes text too big for one pager block
  unpaged (`tests/test_changes.py`). Keep both when touching either.
- **The dashboard's player-file parser tracks sections**: the player
  block ends at its `End`, `#PET` and `#STASH` are not the player's, so a
  character carrying nothing no longer reads their pet's stats as their own
  (`tests/test_player_file_parser.py`).

## Contracts From The 2026-10-22 Audit

A second audit (2026-10-22) found 29 bugs; the 28 fixed after it are in
`tests/test_audit_{connections,saves,gameplay,tooling}.py`, each failing on
the old code. The rules they leave:

- **No write blocks the game loop.** `write_raw_to_descriptor` waits on
  a full socket at most `WRITE_STALL_MS` without progress and
  `WRITE_STALL_MAX_MS` in all, then sets `d->write_failed`; the output
  pass closes that descriptor. The budget is also the connection's:
  `d->write_stalled_ms` adds up the waiting across writes until one goes
  out without waiting, and past `WRITE_STALL_BUDGET_MS` (2 s) the client
  is let go (2026-10-26) -- a client whose kernel took a trickle could
  otherwise cost a second on every write for as long as it typed. **No
  close blocks it either**: the listening socket's `SO_LINGER` (30 s) is
  inherited by every accepted connection, so `close()` on one holding
  unsent output -- exactly the client just dropped for not reading --
  held the whole game for up to thirty seconds. `new_descriptor` turns
  linger off on each connection, and `close_socket` resets one dropped
  for `write_failed` (`test_audit_connections`; found in CI only, by
  reading the stuck server's syscall: `close`). Never close a descriptor from inside
  `write_to_buffer` -- its callers are still using it.
- **A login enters with the file as it is now.** CON_GET_NAME's copy is
  only for the password check: `login_reload_character` frees it and
  reads the file again once the password is accepted, then re-checks
  password, deny, ban and wizlock. A quit, an idle purge or a PRESTORE
  while somebody waits at the prompt otherwise duplicated items or undid
  the restore. **A connection not in the game is never saved**
  (`save_dropped_player`): hanging up at the password prompt saved the
  stale copy over the file. A new name another connection holds is
  refused, at the name and again at entry.
- **A PROXY header counts only as a connection's first line**
  (`first_line_read`), and the web bridge always sends one (TCP4, TCP6 or
  UNKNOWN); a bridged player's address is then put through the login
  throttle, which saw only loopback before.
- **A file written to a temp name is renamed over the real one only if
  the write finished** (`file_write_finished`, `temp_file_commit` in
  `save.c`; `replace_area_file` for areas): a full disk once left a 0-byte
  `maxload.txt` that hung boot, a 0-byte area and a 0-byte player file
  from RESETPWD. `read_maxload_file` stops at end of file. Tests inject the
  failure with a `/dev/full` symlink, which needs no root.
- **PRESTORE STASH is all-or-nothing**: the snapshot's `#END` is checked
  first, the `#STASH` section is validated without reading anything into
  the game (no `fread_number` exit), objects are read aside and spliced in
  only if all came back, and each is counted with `maxload_subtree`.
- **Worn gear is checked at load** (`unwear_illegal_at_load`, end of
  `load_char_obj`, before `reset_char`): a slot the object cannot take, a
  second object in a slot, a second unique ring, or (mortals) an object
  above the character's level comes back carried. Checked against the
  961 character files on 2026-10-22: 2 of 10,910 worn objects affected.
  The name-prompt copy logs nothing; the copy that enters does.
- **REMORT re-equips through `wear_slot_allowed_quiet`**: WEAR's own
  requirements, the wield weight, a hand for a shield, and SECONDARY's
  rules (`secondary_weapon_refusal`) for the off hand.
- **`obj->enchanted` means the enchant spells worked on it**, and they set
  it now. It no longer changes which affects count anywhere -- equip
  always applied the prototype's too (its stock ROM test is commented
  out) and COMPARE now does the same. SECONDARY refuses an enchanted
  weapon and any single hit or damage bonus over 5, the prototype's or the
  weapon's own; a bonus `create_object` rolled is not an enchantment.
- **A shop never sells for less than a copper or hands over an item it
  was not paid for**: haggling discounts the price already computed (a
  part-used wand is priced by charges), and the sale stops if
  `spend_copper` fails. SELL pays before the item moves.
- **REPAIR restores only what was lost**: a level -1 armour piece is
  compared against the least `create_object` can roll at its level
  (`repair_armor_floor`), not its prototype.
- **Moving someone through an object asks what ENTER asks**
  (`manipulate_move_refuses`: fighting, private rooms, `can_see_room`,
  travel rules, newbie rooms, Hyrule gates); CRAWL and JUMP are
  POS_STANDING. **LOOK IN a portal only points `in_room` at the far room
  and back**, as CLAIRVOYANCE does, so no arrival hooks fire.
- `tests/test_damage_result.py` also catches a variable assigned from
  `damage(` and then branched on (meteor swarm did that).
- Tooling: `toc-deploy` turns HUP, INT and TERM into exits so its EXIT
  trap rolls back; migration is resumable through `state/.migrating`; a
  native PID is trusted only if its command line is the game's or the
  dashboard's; `uninstall --purge` refuses a state path that is the
  checkout, holds it, `/` or `$HOME`; `.env` values have one level of
  matching quotes stripped, as Compose does; `update` ignores the state
  folder wherever it is, its pre-restore copy and restore leftovers.
- **The audit's leads, followed up** (`tests/test_audit_leads.py`): NOTE
  is a private command (`command_is_private`), exactly as TELL is: its
  words and answers never reach the journal or the plain log line, the
  "posted a note" line names no subject, and a character staff flag with
  LOG <name> is recorded in full, as their tells are
  (`tests/test_playlog.py` pins both); RESETPWD ranks its target by
  `get_trust` on a loaded copy (`offline_player_load`, as PRESTORE does),
  so a `Tru`/`Trust` above the level counts;
  a faded ENCHANT ARMOR keeps the piece, damaged, instead of taking it out
  of the inventory into nowhere; RESETPWD checks the name with
  `prestore_name_ok` and the target with `player_in_game`, refusing a
  login in progress; STASH refuses a container holding anything on a
  timer (`stash_holds_timed`); an overlong input line is cut short without
  discarding the lines queued behind it; `close_socket` frees the
  descriptor's `outbuf` and pager text, and `write_to_buffer` ignores a
  descriptor whose buffer is gone; ANEW checks its write; a quest or daily
  reward the purse refuses is said and logged, never announced as paid;
  dashboard queue payloads are ASCII (typographic punctuation is
  transliterated, anything else refused); every shell writer appends to
  the queue under the fcntl lock the game takes while it truncates it,
  through `python3` -- where there is none (a Docker host without it) the
  append is plain and best-effort, since failing a backup or a deploy for
  want of a lock would be worse than the rare lost line;
  and `toc.ps1 update` finishes in the newly pulled launcher, as `toc.sh`
  does. PROJECT already calls `do_return` (lead U10 was wrong).
- **Nothing the game keeps is rewritten in place** (owner, 2026-10-22:
  "use your best judgement"). The note board, the ban list, the wizlist
  and the trims of the channel, login and play journals write
  `<file>.tmp` and go through `temp_file_commit`, so a crash or a full
  disk mid-write keeps the old file -- a truncated `ban.txt` lifted every
  ban. A new writer of a whole file does the same.
- **`toc-state-sync` copies nothing while a deploy holds
  `/run/toc-deploy.lock`**: it takes the lock shared and non-blocking for
  the copy alone (opened read-only, since `toc-deploy` creates it as
  root), skips the run if a deploy has it, and lets go before the push.
  A rollback extracting over the live tree could otherwise be copied half
  written. Snoop showing alias bodies and LOG <name> recording a
  character in full are staff tools working as meant (owner, 2026-10-22).

## Contracts From The 2026-10-22 Gameplay Review

A post-fix gameplay review (G1-G6) and the views added beside it. Each fix
has a live or behaviour test that fails on the old code.

- **BOMB spends a carried bomb, once, before anything goes off**
  (`tests/test_hyrule_bombs.py`). Usable means carried at any depth
  (`find_bombs_in`, `hyrule_bombs_usable`); the stash still counts against
  the bag (`hyrule_bombs_carried`) and is never spent from afar --
  `hyrule_no_bomb_to_use` says which. Combat refuses unless
  `hyrule_use_bomb` succeeds. A puzzle is checked with
  `puzzle_manipulation_ready` (no change, no cost), then a bomb is spent,
  then `trigger_puzzle_manipulation` opens it; a refused target or puzzle
  costs nothing.
- **Armour damage is a ledger, and REPAIR puts back exactly it**
  (`tests/test_gear_damage_ledger.py`). Heat metal, acid breath and a
  shield's dent go through `gear_file_armor()` in `handler.c`: worn AC off
  at the old values and on at the new, a point per value into
  `obj->armor_lost[4]`, `REPAIR_DENT_WEAR` condition. It saves as
  `ArmorLost a b c d` under **case 'A'** of `fread_obj`, only when
  non-zero, and PRESTORE STASH's scanner knows it. `repair_armor_target()`
  is value plus ledger, never below `repair_armor_floor` -- the floor is
  the backstop for pieces damaged before the ledger, so **an old file
  repairs exactly as it did** (no free upgrade, nothing lost). A ledger,
  not a recorded baseline, so staff tuning and spells that change values
  are never taken for damage. A new armour-filing effect calls the helper.
- **A rider sets off the arrival trap once**, after the look, with
  `rev_dir[door]`, as a walker does (`tests/test_trap_movement.py`); the
  source test no longer pins a count of `room_affect` calls.
- **Heat metal counts an effect when it lands**, cursed branches included,
  before the blow (`tests/test_audit_leads.py`).
- **The dashboard's `/api/config` resolves off the event loop**
  (`asyncio.to_thread(public_game_host)`, lookups coalesced under
  `_PUBLIC_IP_LOCK`), and **the log and event followers track file
  identity** (`FollowedFile`: device and inode with the offset, a carry for
  half-written records, an incremental UTF-8 decoder)
  (`tests/test_webadmin_followers.py`).
- **Views share the predicates of the thing they describe**
  (`tests/test_staff_views.py`): `devote_plan` decides DEVOTE, DEVOTE
  PREVIEW and ALIGNCHECK's forecasts; `quest_request_refusal` decides
  AQUEST REQUEST, AQUEST DAILY REQUEST, AQUEST INFO, DAILY STATUS and
  QUESTDIAG; `repair_armor_target`/`repair_cost_copper` decide REPAIR,
  REPAIR QUOTE and GEARDIAG. A preview that computes its own answer will
  drift. QUESTDIAG, GEARDIAG, HYRULESTATUS and ALIGNCHECK are L5,
  read-only, online targets, `rank_protects`, and sit below every command
  a shorter word already means.
- **Test gotchas found on the way.** `test-parallel.sh` runs modules as
  background jobs, which start with SIGINT ignored, and POSIX forbids
  trapping a signal ignored on entry: a test that signals a child shell
  must give it SIGINT back (`preexec_fn`). Under the sanitizer build a
  reply can land on the prompt's line, so a parser of command output
  strips a leading `<...>` prompt.
- **Worn to 0 is broken** (owner, 2026-10-22): `damage_eq` shatters a
  piece at `condition <= 0`, as heat metal sets 0 and the flag together.
  The five prototypes authored at 0 (condition letter R -- a pentagram,
  a rotted jacket, bagpipes and two others) stay as made; the rule is
  about wear (`tests/test_gear_damage.py`, a source assertion: damage_eq
  is a 10% roll on a random slot, too rare to play).
- **A vampiric weapon drinks only from what a blow takes** (owner,
  2026-10-22): `one_hit` sets `vampiric_blow`, `damage()` takes it at
  entry, and the twentieth and the point toward the dark come where hit
  points really come off, beside `alignment_drain` -- never the overkill,
  never the goblin, never the dummy (`tests/test_vampiric_landing.py`).
- **Lag counts down every pulse in a fight** (owner, 2026-10-22):
  `fight_lag_update()`, beside `walkto_update` in `update_handler`, takes
  a pulse off a fighting player's `wait` when nothing is typed. Without
  it a player who typed KILL and watched kept a round of lag all fight,
  and `damage()`'s wimpy test (under half a round) never passed: WIMPY
  never fired. A typed command is still the input loop's, a walker
  WALKTO's; bash and trip lag still hold wimpy off until they wear away
  (`tests/test_wimpy_idle.py`).

## Completion Standard

A task is complete only when the requested behavior or documentation is
implemented, relevant tests pass, the diff is reviewed, and any limitation or
unrun test is reported. Do not leave required long-running test/server sessions
unattended at final response.
