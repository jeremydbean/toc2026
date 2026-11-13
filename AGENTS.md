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
- `mudlet/listing-submission.md`: Mudlet listing readiness and review handoff
- `wiki/operator-guide.md`: immortal and incident procedures
- `wiki/developer-guide.md`: architecture and development workflow
- `wiki/area-building-guide.md`: authoritative area format reference
- `wiki/validation-and-area-health.md`: validators and issue codes
- `wiki/hyrule-area.md`: generated Hyrule design and workflow
- `.github/SECURITY.md`: actual security boundaries and hardening
- `.github/CONTRIBUTING.md`: review checklist

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

The Make build is `-std=c17` (it was `-std=gnu89` until 2026-11-11), with
ROM definitions and `libcrypt`/`libm` where applicable.

**Build both trees before believing a change works.** They disagree on more
than warnings:

- Both are strict C17 now (owner, 2026-11-11: the Makefile was
  `-std=gnu89`, and POSIX functions visible under one were hidden under the
  other). A file needing POSIX -- `getaddrinfo`, `fileno`, `ftruncate`,
  `fsync` -- must define `_DEFAULT_SOURCE` and `_POSIX_C_SOURCE` **before
  any header**, as `src/comm.c` and `src/act_wiz.c` do; `inet_aton` and
  `gethostbyname` fail both builds. They still differ in warning flags and
  in how `unix` is defined, so build both.
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
  -DENABLE_SANITIZERS=ON \
  -DTOC_BIN_DIR="$PWD/build-sanitize/bin"
cmake --build build-sanitize
```

Every CMake tree writes `bin/rom` unless `TOC_BIN_DIR` says otherwise
(2026-11-12), so a Release rebuild used to overwrite the sanitizer binary
a test was about to run; give a second tree its own `TOC_BIN_DIR`. The
default stays `bin/` for the docs, the area scripts and CI.

**Build cost, measured 2026-11-12** (4 cores, gcc 13, no ccache): a clean
Make build is 6.8 s at -j4 (24.3 s at -j1), CMake 8.0 s; touching
`merc.h` rebuilds 62 of 75 objects in 6.1 s; touching one `.c` file, 1.0
s. Parsing `merc.h` alone is 24 ms a file (about 1.5 s of CPU across a
build); the time is the large files (`act_wiz.c` 1.8 s). Splitting
`merc.h`, or a precompiled header, would save at most those seconds, and
only for edits to a part few files use, so neither was done.

Supported long-running native wrapper:

```bash
./startup.sh 9000
```

`area/startup.sh` delegates to the root `startup.sh`, for hosts that launched
from `area/`. The other retired root names (`startup`, `install`, `cleanup`,
`refresh`) were removed on 2026-11-12; use `startup.sh`, `install.sh`,
`make clean`, and `bash scripts/validate.sh build`.

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
python3 scripts/check_parser.py
python3 scripts/check_exits.py
python3 scripts/check_resets.py
python3 scripts/check_shops.py
python3 scripts/area_lint.py --fail-on critical --limit 100
python3 -m unittest discover -s tests
python3 -m unittest tests.test_money_safety tests.test_bank_interest tests.test_pkill_persistence tests.test_achievements
git diff --check
```

Current October 2026 Python baseline:

```text
102 listed area entries
2,508 mobiles
3,761 objects
7,766 rooms
0 critical, 12 warning, 1,690 information findings
```

The exploration maps (2026-11-12) added one mobile and one object and
exactly two information findings: the wandering cartographer (29942 in
`seasonal.are`, `mob-has-no-spawn`: `maps.c` places him) and the area map
(96 in `limbo.are`, `object-has-no-source`: `map_item_create` makes every
one). The count read 2,507, 3,760 and 1,688 before them.

The cleanup of 2026-11-11 took the Quest Zone's 13 rooms and its one
mobile, Temple Despair (the list entry and its 7 rooms) and 18 information
findings with them; the count read 1,707 before it.

The shared area reader (2026-11-11) took one information finding off: room
17024's `one-way-exit` was false, because the dashboard parser had missed
17022's `D3 too dark to tell` back to it. Recounted then: 102 areas, 2,507
mobiles, 3,760 objects, 7,766 rooms, 0 critical, 12 warning, 1,688 info.

The guardians' keys (2026-11-10) added exactly nine information findings:
each is `object-has-no-source` now, made by `hyrule_guardian_slain` at the
guardian's death for every player it credits, not by a reset. The count
read 1,698 before them.

The holiday fairs (`area/holidays.are`, 2026-11-02) added the entry, ten
mobiles (the vendors), thirty-nine objects and exactly fifty information
findings: every one of them is made by `holiday.c` -- a vendor when its
holiday starts, its wares, the decoration, the treats on corpses and the
eggs -- and nothing places them with a reset. The count read 102, 2,498,
3,721 and 1,648 before them.

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
| `build` | `validate.sh build`: C17 Make with strict warnings, world load, recovery scenarios, list iterator, smoke; then strict C17 CMake and its world load. Hands `merc` on. | 1 min |
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
  no fight is the sign. Nor random visits from Herbie the angel
  (`TOC_NO_HERBIE`, 2026-11-03), who heals the most hurt player in the
  world: a fixture set to one hit point was healed before its next
  command in CI. Staff HERBIE still sends him.
- **A mobile a test loads may walk away -- use the fixture world.** The
  Korzath security guard (29012) six tests fought is WIMPY and STAY_AREA,
  and on a busy runner it left the room between LOAD and the first KILL
  or CAST often enough to fail three modules in one afternoon
  (2026-10-25: "They aren't here"). `set mob 29012 act +sentinel` was the
  advice here, and it never worked: SET MOB refuses every prototype that
  came with the game, and the tests checked only that the reply lacked
  "Syntax". `LiveMud(fixtures=True)` loads `tests/fixtures/area/ztestfix.are`
  into the test world (rooms 32700-32708 joined to nothing -- the bout
  ring 32707 leads only into the lava pit 32708, whose VOLCANIC room
  affect kills whoever arrives -- a sentinel sparring guard, mob 32700)
  and `place_sparring_guard()` loads it and
  proves with STAT that it stands where it was put.
  `tests/test_fixture_hygiene.py` fails on the old habit.
- **Something dropped or killed on a street may be eaten.** A stray dog
  (`spec_fido`) devours an NPC corpse and a janitor picks up what lies
  about; `test_disasters` failed on "You do not see that here" when one
  wandered in between the dragon's death and LOOK IN CORPSE. Fight or drop
  where nothing walks in -- `transfer` both to a fixture room (the
  sparring floor, 32700, or 32703) -- rather than allowing for the luck.
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
- `src/diary.c`: DIARY -- each mortal's daily summary, kept in `player/diary/<Name>`
- `src/recycle.c`, `src/memguard.c`: allocation, liveness tags, the
  quarantine, the stale-pointer sweep and MEMCHECK
- `src/db.c`: world boot and native area parser
- `src/interp.c`: command registration/order/trust/logging
- `src/act_move.c`: movement, exits, traps, recall, run/speedwalk
- `src/walkto.c`: WALKTO -- named destinations, pathfinding from the
  player's room, and the paced walk
- `src/jail.c`: JAIL, the sentence's hold at every placement
  (`jail_hold_room` from `char_to_room`), its expiry, and the refusals
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
- `webadmin/area_reader.py`: the one Python reader of `.are` files, token
  for token as `src/db.c` reads them, with offsets; every tool goes through it
- `webadmin/area_parser.py`: the dashboard's dataclasses and flag tables,
  built from `area_reader`'s records
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

- Match the surrounding style; both builds compile as C17.
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
- **A listing that loops is built in a bounded `DString`, never a fixed
  array** (growable output buffers, 2026-11-12). `src/dstring.h`:
  `dstring_init_limit( &out, DSTRING_OUTPUT_MAX )` (256K), then
  `dstring_printf` / `dstring_append_cstr`, then `page_to_char(
  dstring_cstr( &out ), ch )` and `dstring_free( &out )` on every way out.
  It grows with `realloc`, not `alloc_mem`, so the 32,704-byte size class
  does not apply; `page_to_char` sends text past its 32,000-byte pager
  block unpaged and `write_to_buffer` sends a large text in pieces, so no
  sink has a ceiling it can reach. An append that would pass the limit
  appends nothing, returns false and sets `out.truncated` -- whole lines
  only -- and `dstring_fits( &out, n )` asks first, which is how a
  listing keeps room for its trailer and says "... the rest" only when it
  really was cut. STASH (a 500-slot stash listed about 185 in 4,096
  bytes, while STASH GET takes the numbers shown), HISTORY, NOTE
  LIST/UNREAD/SEARCH, WHO, REPORTS, GAINLIST and GAINLIST PREVIEW,
  CHANGES, DIARY LIST and the Hall of Heroes' plaque and tablet were
  converted; output is byte-identical whenever nothing was cut
  (`tests/test_long_listings.py`, `tests/test_dstring.py`, which also
  holds each to it). Commands that send line by line (INVENTORY,
  EQUIPMENT, a shop's LIST, AFFECTS, PRACTICE, SCORE, WHERE, COMPARE
  UPGRADES, MEMCHECK, DNS LIST) never had a ceiling and are left alone; a
  line of its own is still a fixed `buf` with `snprintf`.
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
- **A skill typed by its whole name is that skill.** `full_command_names`
  in `interp.c` is matched, whole words in any case, before the prefix
  lookup: MIND LEECH ran MINDBLAST (which "mind" begins) and spent its
  mana, and FISTS OF FURY passed "of fury" as the target (review,
  2026-10-30). A new command for a skill with a multi-word name needs a
  row; `tests/test_command_name_tails.py` checks each row names a real
  skill and command, and plays the handler chosen and its cost.
- **An abbreviation leans to what the character can use** (owner,
  2026-10-30). A word of two letters or more that begins a skill command
  the character lacks (`command_usable`: the command's own name or whole
  name as a skill, never a spell -- HEAL is the healer's) goes to the next
  command it begins that they have (`cmd_tab_usable_lookup`, the same
  candidate list), never to one `command_lean_refused` names (QUIT,
  DELETE, REMORT, PASSWORD, SACRIFICE...). A single letter and a whole
  name typed are never moved, and staff are never leaned. A whole name
  may be abbreviated a word at a time (MI LE, CR DA BOB) when the
  character can use it. CAST resolves through `find_spell` (exact, then
  the caster's own by prefix, then by word, then `skill_lookup`), reads a
  slip in the rest of a name whose start is right, and suggests from
  `spell_suggest`; the Huh hint offers usable commands, whole names and
  known spells by `name_nearness`. `text_edit_distance` counts two
  swapped letters as one (HELP suggestions too).
  `tests/test_command_guessing.py`. **Neither reading of the rest takes a
  target** (review, 2026-10-30: CAST 'CHILL' TORCH ate Torch as a slip of
  "touch" and struck whoever the caster was fighting): a quoted name is
  exactly the spell's name, and a word that names something the spell
  can be cast at here (`cast_word_is_target`, by the spell's target
  type) is the target unless it is that word of the name whole
  (`tests/test_cast_targets.py`) -- asked of the spell already read,
  whether or not the longer name is the same spell: CAST CAUSE LI, with
  cause critical and cause light known, is the first at Lightfoot
  (review, 2026-11-02).
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
  **An area file's wealth figure is held to the level** (owner,
  2026-11-04): the figure splits into every denomination at once, so 400
  on a level 8 outlaw was two platinum, and `mob_index_set_wealth` now
  caps the coin at `MOB_WEALTH_CAP_ROLLS` (3) times the most the level
  roll gives (`mob_wealth_roll_max`), keeping the figure itself for the
  area writer (`tests/test_mob_wealth_cap.py`). Change the roll and the
  cap's mirror of it together.
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

## Strict Warnings

Owner, 2026-11-12 ("do it all"). Silent narrowing -- an int stored into a
16-bit field -- is the class behind the WIMPY and pool bugs, so the whole
of `src/` is clean under **`-Wshadow -Wsign-compare -Wconversion
-Wsign-conversion`** (gcc 13 and clang 18, at -O0, at -O2 and under
ASan/UBSan), and both
builds carry them: the Makefile's default `WARNFLAGS` through
`CONVERSION_WARNINGS`, `scripts/validate.sh`'s strict set, and CMake's
`TOC_CONVERSION_WARNINGS` (CMake no longer passes `-Wno-sign-compare`).
CI makes them errors: `TOC_STRICT_CONVERSION=ON` on both CMake builds and
`TOC_STRICT_CONVERSION=1` for `validate.sh build`.
`tests/test_strict_warnings.py` compiles every `src/*.c` with them at -O0,
at -O2 and at -O0 with `-fsanitize=address,undefined`, and fails on any
warning, naming the file, line and flag. The three disagree: gcc folds
constants at -O2 it warns about at -O0 (a const size_t handed to
`alloc_mem`), and UBSan's instrumentation hides the ranges -Wconversion
reads (`LOWER`/`UPPER` into a char, clean until `-fsanitize=undefined`;
the shifted branch is cast to char now).

Keeping a file clean, without changing what the game does:

- **A sum of modifiers is an int.** `CHAR_DATA`'s `wait`, `carry_weight`,
  `carry_number`, `saving_throw`, `hitroll`, `damroll`, `armor[4]` and
  `mod_stat[]` were sh_int with int modifiers added into them; they are
  int now, as the pools and WIMPY are. Widening a field changes nothing a
  value in range does; its readers (`fread_number`, no `(sh_int)` cast)
  must not narrow it back. So are `pcdata->exp_bonus` (a sum of
  APPLY_EXP modifiers; `gain_exp` applies it in long long), the kill
  counts (`kill_table[].killed`, a prototype's `killed`), a prototype's
  `count` and `ch->timer`, which counts for ever for a link-dead immortal
  (2026-11-12). Values a builder writes (a prototype's dice, a room
  affect's numbers) and the capped ones (`queststreak`, practices,
  conditions) stay sh_int.
- **A value that must stay 16-bit goes through `sh_int_clamp(long long)`**
  (merc.h): unchanged when it fits, saturated at the ends otherwise --
  practices and trains at a level, the sex sums in `reset_char` and
  `affect_modify`, a mobile's computed armour and stats, a saved
  `PsiGrant`. Never a bare `(sh_int)` cast to quiet the warning: that
  keeps the wrap.
- **A cast is for a range you can see**: a constant (`(int) size` of a
  30000 buffer), a count already known non-negative (`(size_t) (count -
  at)` when `at < count`), a bit set read back as the bits it was written
  as. Say why in a short comment when it is not obvious.
- **Shadowing is fixed by renaming the inner one**, never by reusing the
  outer variable, which can change what a later line reads.
- **A signed/unsigned comparison is fixed at the type**, not by casting
  away a negative that can really happen.

**The second pass (2026-11-12) added four more to the line**:
`-Wcast-qual` (23 sites), `-Wmissing-prototypes` (12), `-Wunused-parameter`
(3) and gcc's `-Warith-conversion` (51: `sh_int += 1` and its kin -- the
`LOWER`/`UPPER` casts had already taken the rest). They ride in the
Makefile's `QUALITY_WARNINGS` (`-Wno-unused-parameter` is gone from the
default `WARNFLAGS`), in CMake's `TOC_CONVERSION_WARNINGS`/`_ERRORS`, and in
`validate.sh`'s strict set and its `TOC_STRICT_CONVERSION` errors, and
`tests/test_strict_warnings.py` compiles with all of them. **clang has no
`-Warith-conversion`**: the Makefile and `validate.sh` add it only when
`$(CC) -Werror -Warith-conversion` compiles, CMake only for
`C_COMPILER_ID` GNU, and the test only where its compiler takes it. How
each is kept clean:

- **A const string stays const.** `is_number`, `get_trust`, `get_eq_char`,
  `is_creator`, `is_creator_founder` and `is_killuminati` take const now;
  `one_argument_const( const char *, char * )` is the walk itself and
  `one_argument` hands the caller's own pointer back advanced (pointer
  arithmetic, no cast). A function that writes its argument
  (`get_char_world` and `get_obj_here`, through `number_argument`) is given
  a local copy, never `(char *)` a const string -- a string literal there
  would be written to.
- **A function is declared where its table is**: `do_` functions in
  `interp.h`, spell functions in `magic.h`, a spec function beside its
  module's other declarations in `merc.h` -- include the header in the file
  that defines it. A helper used by one file is `static`.
- **An unused parameter is `UNUSED_PARAM(x)`**, at the top of the body.
- **A 16-bit field's arithmetic is `x = sh_int_clamp( x + n )`**, never
  `x += (sh_int) n`. A field that is really a sum of modifiers is widened
  instead (`pcdata->exp_bonus`, the APPLY_EXP sum, is int: clamping it would
  make adding and taking off a modifier disagree).

`-Wstrict-prototypes`, `-Wold-style-definition` and gcc's
`-Wformat-overflow=2` joined the line on 2026-11-12 (Makefile
`QUALITY_WARNINGS`, CMake's lists, `validate.sh`, the test). Still outside
it: nothing. gcc's `-Wformat-truncation` (on by `-Wall`) is an error too
since 2026-11-12: it is reported only unoptimised (-O0, which the
sanitizer build is), so `tests/test_strict_warnings.py` compiles each file
to an object (`-c -o /dev/null`) rather than `-fsyntax-only`, which never
ran the pass that finds it. Eight `snprintf` sites had been cutting text
short silently; each was given room or a stated precision, and BUILD's
place answer is refused when PLACE could not take it whole.

**`-Wformat-truncation=2` joined the line the same day** (gcc only, like
`-Wformat-overflow=2`: Makefile `FORMAT_TRUNCATION_WARNING`, CMake's GNU
list, `validate.sh`'s gcc branch, the test). Level 1 reports only a likely
cut whose result is ignored; level 2 any cut the compiler cannot rule out,
checked or not. gcc 15 reported eight level-1 sites gcc 13 and 14 do not
(a directory entry's `d_name` is the trailing array of `struct dirent`, which
it does not bound) and eighteen at level 2. Clean under gcc 13 and 14 at
-O0, -O2 and the sanitizers; gcc 15 was not available to recheck. The
rules it leaves:

- **Text read back later is refused, never cut.** A path from a directory
  walk goes through `toc_path_join` (string_safe.c: true only when all of
  it fits, no snprintf of `d_name`); a ledger record that would lose its
  check and newline is refused (`recovery_record`); a telemetry row is
  refused whole (`telemetry_append`); test an snprintf's result with
  `snprintf_fits( n, size )` (merc.h).
- **A double is never `%.1f` into a short buffer**: that is up to 312
  bytes. `format_tenths( buf, size, value, limit )` writes one decimal
  place through integers, held to a stated limit (at most
  `FORMAT_TENTHS_MAX`); COMPARE's percentages and CONSIDER's progress row
  use it.
- **A pad is a precision on a run of spaces** (`"%.*s", pad, "      "`)
  bounded by the box, never `%*s` of an unbounded int.
- **A loop that appends lines uses a bounded DString** (ALIAS and RESETS
  were fixed buffers).

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

**A Hyrule room is dark only when it fits the room** (owner, 2026-11-10).
Every dungeon room and cave was generated ROOM_DARK -- Heartglow Hollow,
with two fires on its wall, among them. Darkness is now `"dark": true` on
the room's entry in `data/hyrule_room_prose.json` (`Prose.dark`,
`RoomSpec.dark`), set on three rooms: the Seeping Gallery ("the unlit
gloom"), the Lion's guardian's hall (its gate asks the Red Candle to light
it) and Ganon's Dark Chamber. Every other room in a sector that darkens at
night -- open ground and the dungeons' underground sector -- carries
`ROOM2_ALWAYS_LIT` (`room_flag_word`). Mark a room dark in the prose, never
in the area file; `tests/test_hyrule_progression.py` holds the list.

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
against `../merc --check-area` and `scripts/check_exits.py` before deleting
anything.

Before restoring a reset that was commented out, read what it does. One of
those 176 was a button whose `value[4] == 3` kills everyone in the room except
whoever pushes it; arming that is a gameplay decision, not a repair.

**Every Python tool reads area files through `webadmin/area_reader.py`**
(modernization project 3, 2026-11-11). Its `TokenReader` is `fread_letter`,
`fread_number` (with `|`), `fread_long`, `fread_flag` (no sign),
`fread_string` and `fread_word`, and its loaders are `load_mobiles` through
`load_specials` in the same order, so every shape above reads as the game
reads it; every token keeps its offset, and files are read and written as
bytes, so an in-place writer changes one token and nothing else, CRLF
included. `AreaParser`, the area lint, the directions router, the Mudlet
map, the seasonal builder, both price tools and `scripts/check_*.py` all
use it; `listed_area_files(dir, built=False)` is the list for anything
committed. Do not write another reader -- add what a tool needs to this one.
Help keeps its own reader (`webadmin/help_index.py`), and the Hyrule
generator edits its own output as text. Moving the tools onto it fixed what
the old readers disagreed on (CHANGELOG, 2026-11-11): the dashboard parser
had lost 38 objects' affects and 130 extra descriptions in double-spaced
files, three mobiles' FLAGS2 words, room 17022's `D3 too dark to tell`
exit and two rooms with a name over two lines; the router read archived
and seasonal copies (`korzath2old.are`, `dresden_halloween.are`) for its
portals, and missed a portal written with a second flag word (9163) and a
teleport room (24254). One thing the game reads is likely a builder's
slip: wyvern.are's `R 0 1644 0 4` is read as "randomize no exits" -- R
takes two arguments -- so that maze room never scrambles.

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
`sight_trust()` -- `staff_trust` (an immortal's trust, a mortal's level)
raised to `TRIFORCE_SIGHT_LEVEL` for the wearer -- is what sight compares
against a wizinvis or cloak level. Add a
new holylight check and it needs both; `tests/test_hyrule_progression.py`
fails on a `PLR_HOLYLIGHT` sight test that does not also ask the Triforce.

**A guardian is never driven from its chamber** (play journal,
2026-11-10: DESPAIR made Digdogger flee its den, past the gate that asks
for the recorder). `is_hyrule_guardian()` in `special.c` -- the
`spec_hyrule_guardian` or `spec_ganon` special -- is what do_flee asks
before despair answers a flee with the opponent's flight; a new way of
moving a mobile out of a fight asks it too (`tests/test_guardian_despair.py`).
Since the audit of 2026-11-10 the test is `hyrule_native()` in
`act_move.c` -- any of Hyrule's own mobiles, charmed or not -- and it is
asked by DESPAIR, FISTS OF FURY, STEAL and CHARM PERSON. Ask it, not
`hyrule_foe()`, which stops counting a charmed mobile. Instant death is
defied by the guardians of Levels 6 to 9 (`hyrule_defies_instant_death`;
owner: none on the last three dungeons).

**Hyrule's order holds however a character arrives** (audit,
2026-11-10). `hyrule_gate_check` asks for a dungeon's entry piece on any
arrival into its room range from outside it, and for the guardian's tool
on any arrival into the chamber but from its own treasure room;
`travel_spell_refuses` also refuses a Hyrule room whose every exit is a
closed secret exit (`hyrule_room_sealed`). A bound Hyrule object
(`hyrule_bound_object`) in a player's corpse is the owner's alone: GET
refuses anybody else, TELEKINESIS will not fetch the corpse for anybody
but its owner, and a corpse
that rots destroys it rather than spill it. PASS DOOR, ghost form and
DOOR BASH stop at a locked Hyrule door. Leaving a dungeon by PORTAL or
ASTRAL WALK is allowed (owner, 2026-11-10); lending a dungeon tool is not
-- see the keys, below.
`tests/test_hyrule_audit_nov10.py`. **TELEKINESIS fetches a player's corpse from anywhere** (owner,
2026-11-13): no room rule -- no-recall, safe, private, Hyrule -- stops it,
only who may loot it (`can_loot`), a corpse still settling, and the bound
rule above; everything else TK lifts keeps the room rules. **A gate counts the player's own
corpse** (bug report, 2026-11-12: a death in Level 5 left the pieces in a
corpse no entrance would let its owner reach): `hyrule_holds_for_gate` is
carried, or lying in their own `ITEM_CORPSE_PC` (owner by name) anywhere,
for the entry piece and the guardian's tool alike; nobody else's corpse
counts (`tests/test_hyrule_gate_own_corpse.py`).

**A mobile is never a corpse's owner, and nothing of Hyrule's is bottled**
(review, 2026-11-10). `get_obj`'s bound-item guard asks every actor but
staff, a mobile included: a charmed follower ORDERed to GET took a piece
from an offline player's corpse, and its own NPC corpse -- which the
guard does not look at -- then held it for anybody. A corpse rotting in
its owner's keeping is found through its containers
(`corpse_rots_with_owner` in `update.c`), so one in its owner's pack
keeps their bound things. TRAP THE SOUL refuses `hyrule_native` victims,
and CAST refuses it and CHARM PERSON on them before the mana and before
the provocation that follows any offensive cast (`do_cast`).
`tests/test_hyrule_review_nov10b.py`, `tests/test_corpse_bound_decay.py`.
A bottle filled with a Hyrule creature before that releases nothing when
opened (`hyrule_native_vnum`): it let a guardian loose anywhere, and after
the next reset there were two.

**No creature holds a bound object, and no NPC corpse gives one** (review
of c3923e53, P1: a bottled ordinary mobile, charmed, was ORDERed to GET
the shard from an opened chest with no key, killed, and its corpse carried
out through a portal). `get_obj` refuses any NPC a bound Hyrule object
anywhere, and anybody one in an NPC corpse; `make_corpse` destroys what a
mobile dies holding and logs it. The chest claim is the dungeon's own chest
(`OBJ_VNUM_HYRULE_CHEST_FIRST + level - 1`) only, so an owner's corpse in
Hyrule gives back their piece and Master Sword
(`tests/test_hyrule_guardian_keys.py`: `CreatureLaunderingTests`,
`CorpseRecoveryTests`). Tools stay untradeable: the owner's instruction
later the same day ("anything that's required for progression should be
unable to trade") supersedes the review's note that they may be lent.

**Random arrivals ask of the one moved** (review, 2026-11-10). TELEPORT's
candidate loop and `get_random_room` (recall misfires, FLING) ask
`travel_spell_refuses` of the character carried -- TELEPORT asked the
caster's sight and rules -- and `travel_spell_refuses` refuses a sealed
Hyrule room (`hyrule_room_sealed`) to a mobile too. The pools are
otherwise as they were: `get_random_room` still refuses safe rooms and
TELEPORT does not. `TOC_RANDOM_ROOM` (tests only) makes the first guess
of both that room (`random_room_candidate`); `tests/test_random_arrival.py`.
Both draw from the rooms there are, never a guessed vnum (see "Scattering
Things Into The World").

**The last two guardians are group fights, by balance, not by rule**
(owner, 2026-10-28: the ashen Gleeok needs two average high-level
players, Ganon three, and "one person CAN try" -- a party rule that
turned a soloist's blows aside was built and taken out the same day).
The sizes are the point where Hermie-buffed median players just win,
measured live with `tools/hyrule_playtest/ganon_group.py` (any guardian,
any group size), **plus 25%**, because real players are good and get
good gear (owner). Ganon was then made half as hard again (owner,
2026-11-03): 67,500 hit points, a 350 blow (not 375, whose biggest roll
is UNSPEAKABLE through sanctuary) and fire a pulse +50%. His fireballs
are spell blows no parry stops, four every four seconds at random members
of the fight; add fireballs rather than enlarge them, since none may read
UNSPEAKABLE (over 250) through sanctuary -- and neither may his biggest
blow. **The guardians past Level 6 heal out of a fight** (owner,
2026-11-03): a tenth of their health a pulse -- Ganon in `spec_ganon`,
Levels 7 and 8 in `spec_hyrule_guardian` (`hyrule_guardians_that_heal`,
held to `BOSS_MOBS` by `tests/test_hyrule_guardian_heal.py`). Before it
the ashen Gleeok, a fight for two, fell to one player on 2026-11-02 who
fled twice, healed in town and came back to its open wounds. Levels 1-6
keep their wounds. Read a group playtest's transcripts, not only its verdict:
until 2026-10-28 the tool took a member's "is DEAD!!" for the
guardian's, so every lost group fight was scored a win, and a second
fight in one run is played in the relics the first one looted -- only a
run's first fight measures anything. DIVINE PROTECTION (one of Hermie's
buffs) spares each buffed player one death at three quarters of their
health; the tool counts those saves. An instant kill takes a tenth of
either guardian's health (`hyrule_defies_instant_death`).

**The first seven guardians are hard, and Hermie is what makes them
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
carry another through.

**Keys, prizes and tools are each player's own** (owner and review,
2026-11-10: a borrowed key took every piece past living guardians, a
bystander looted a chest another opened, a key kept over a reset opened
the refilled chest). A guardian carries no key (the generator writes no
`G` for it). Its death, in `raw_kill_internal` before the corpse, calls
`hyrule_guardian_slain`: every player the kill credits -- the killer, a
pet's or servant's master, the mortals of their group in the room (the
boss achievements' rule, `achievement_party_member`), and any mortal in
the room who struck it, grouped or not, however late they joined
(`hyrule_note_striker` from `damage()`: the latest `HYRULE_STRUCK_MAX`
fighters of its life, by character serial, never the file Id; owner, 2026-11-10: "joined late yes,
left room no"), never staff -- is handed a NODROP key of their own (`hyrule_guardian_key`: 30630-30637,
Ganon's Golden Key). A chest's prize -- the piece, and Ganon's Master
Sword -- is claimed by `hyrule_chest_claim` from `get_obj`: only with the
dungeon's key carried, as a copy, the chest keeping its own for the rest
of the party; the claim spends the key, Ganon's once both his prizes are
held, in either order or by GET ALL. Everything else the progression asks
for (`PROGRESSION_TOOLS` in the generator, `hyrule_progression_tools[]`
in hyrule.c: the boomerangs, raft, stepladder, bow, recorder, red candle,
Magical Key, Silver Arrow) is NODROP, and GET of one lying in Hyrule hands
each player a copy (`hyrule_tool_claim`), one each. Bombs, the shop's
candle and small keys stay tradeable: bought or spent, they carry nobody
past a gate. A key goes at a quit like every key, and the guardian must be
beaten again. `tests/test_hyrule_guardian_keys.py`.

**A dungeon's own things crumble once it is left** (owner, 2026-11-12:
"i don't want a players inventory cluttered with items that are useless
after a dungeon run"). `crumble_kind` in `hyrule.c` names them: the
dungeon's map and compass (`value[4]`, crumbled unless the holder is in
that dungeon), the dungeons' own small keys (`HYRULE_SMALL_KEY`, 30227 --
every reset that lays one is inside a dungeon, so one carried across a
dungeon's edge either way opens nothing ahead), and a guardian's key once
`holds_chest_prize` (an unspent one is kept, so a hurt player may step out
to heal and come back for the chest). Never the shops' small keys (bought
for any dungeon), a tool, a piece, gear, bombs or coin; never the stash or
the floor; never an immortal by level. **It is checked once a pulse, never
in `char_to_room`** (`hyrule_crumble_update`, beside `fight_lag_update`):
each playing character's zone (hylog's numbering; the idle void and the
Oracle's sanctum count as the room the character was taken from,
`was_in_room` and `oracle_saved_room`) against `pcdata->hyrule_crumble_zone`
from the last check, memory only -- so SCAN and AT, which step out and back
within a pass, and those two trips crumble nothing; a new way of taking a
player somewhere and back counts in `crumble_zone` the same way. No
caller of `char_to_room` loses an object it holds, and a login starts
unknown, so quitting inside a dungeon keeps its things. Everything carried or worn at any depth is collected
first, then extracted, with `playlog_obj_gone_as("crumbled leaving Level
N")` naming the journal's item rows, a `crumbled` row in
`log/hyrule.tsv`, and a save. **What a map taught is never taken**:
`AchMaps` is untouched, so Map.Known still unfogs the dungeon, MAPS lists
it, and `hyrule_map_on_arrival` sends the plan from the prototype
(`dungeon_plan`) when no map is carried. The login fix
`20261112-hyrule-crumble` runs the same sweep for leftovers from before
(`hyrule_crumble_leftovers`: inside a dungeon its own things stay).
`tests/test_hyrule_crumble.py`.

**Characters are known by serial, never by the file Id** (review of
d19b0e92, 2026-11-12: two ungrouped characters sharing an Id, one fighting
Aquamentus and one idle in its room, and the idle one got the key). `Id`
is `number_range( 0, 65535 )` and was never unique; it stays in the file,
left alone. `pcdata->serial` (`Serial`, case 'S',
`PLAYER_SERIAL_FIRST` 65536 to `PLAYER_SERIAL_LAST` 2^30-1, so it is never
read for an Id) is unique against an index of every file in `player/` and
`player/archive/` built at boot (`player_serial_boot`) and every serial
given since; `player_identity_login` (the nanny, beside
`recovery_player_login`) gives one to anybody without their own -- none, or
one another file holds -- and saves, and gives a new character an Id no
file holds. `player_serial(ch)` is what anything asking "is this the same
character" compares: `hyrule_note_striker`/`hyrule_struck_by`, the hate
list, and column 2 of `log/progress.tsv`. It is saved, so a striker who
quits and comes back before the kill is still known; RENAME carries it
(`player_serial_rename`). `tests/test_guardian_serials.py`.
**A quest's token is its questor's by serial too** (review, 2026-11-12:
two characters sharing an Id could each pass the other's Id test). The
token's `value[4]` is `-player_serial` -- negative, so it is never read for
an old tag of Id + 1 -- and `quest_token_owned_by()` in `quest.c` is the one
test, asked by GET, TELEKINESIS and the quest's own find and clear-up. An
old tag still answers only its questor, by that Id and the name the token
carries; the name is never saved, so one read from a file (a corpse) names
nobody. The login fix `20261112-quest-serial` binds the old-tagged tokens a
character carries, wears or stashes, at any depth, to their serial when the
tag is their own Id and the token names them or nobody; one tagged for
another Id is left nobody's. A serial-bound token follows a RENAME
(`tests/test_quest_token_serial.py`).

**Ganon's finishing phase is his own marker** (review, 2026-11-10,
confirmed live). It was `AFF2_NO_RECOVER`, which NERVE DAMAGE and
NIGHTMARE also lay, so either put him at full health into the phase the
Silver Arrow finishes. `HYRULE_GANON_STUNNED` in his `hyrule_state` is
set by `reform_hyrule_ganon` alone and read by `is_stunned_hyrule_ganon`,
`spec_ganon`'s repair and regeneration, LOOK's red flash and `hit_gain`
(the tick no longer heals him out of it when an ordinary NO_RECOVER
affect wears off). `hyrule_state` is shared with Digdogger and Patra, so
every reading also asks that it is Ganon.

**The audits' lesser holes** (2026-11-10;
`tests/test_hyrule_followups_nov10.py`). A shutter into a guardian's
chamber asks the chamber's gate before it opens, and the gate says why
(it opened, then refused, and stood open behind the player). SHOOT
through a doorway refuses any `hyrule_native` target: Hyrule's creatures
are faced in their own rooms. Hit points that come off outside a blow --
a fire or frost shield's reflection, the poison and plague ticks -- ask
`hyrule_shrugs_off` (a bubble or blade trap, a ringed patra, an unshrunk
digdogger), or the shield and a poison tick finished Digdogger with no
Recorder. A reset never traps a Hyrule door at random: a trap took
PICKPROOF off a small-key door, and its teleport left a no-recall dungeon. `reset_area` refills and relocks Hyrule's chests
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
python3 scripts/check_exits.py
python3 scripts/check_resets.py
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
- **Three passes, in order**: an exact keyword, then `is_name`'s prefix,
  then `help_phrase_prefix` -- two or more words asked, each the start of
  the matching word of one keyword phrase (HELP DIVINE INTER finds
  'DIVINE INTERVENTION'; owner, 2026-10-28). The last pass runs only when
  nothing else matched, so no page an older query found moves.
  `help_index.lookup` mirrors all three.
- **Then the group, then the first word.** After the three passes and the
  spell-group answer, two or more words fall back to the first word's
  page -- its exact keyword, or from three letters a keyword it begins --
  saying "No help on '<asked>'; here is <word>:" (play journal,
  2026-10-31: HELP GAINLIST TRAINERS found nothing). Only then the
  suggestions. `help_index.first_word_fallback` mirrors it for the
  website (`tests/test_help_exact_match.py`).

## Achievements

`src/achievements.c`; the player guide is `wiki/achievements.md`, whose
catalog table `tests/test_achievement_expansion.py` holds to the source.
378 entries since the 2026-10-25 expansion (owner: about 175 new ones),
386 since the close calls and comedy rows (owner, 2026-11-01: fleeing on
one hit point, other close calls, funny things;
`tests/test_achievement_close_calls.py`).
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
  the new feats: `ACH_STAFF` is `is_staff(ch)` -- by level, so a mortal
  given trust earns them (owner, 2026-11-12) -- and
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
unconfirmed or undone; a wizinvis crafter's attempt is not written). `PREVIEW` as
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
**Hermie offers EMPOWER, never TITANIC** (owner, 2026-11-12), and EMPOWER
carries +50% experience (`APPLY_EXP`, read by `gain_exp` through
`pcdata->exp_bonus`). **TITANIC makes each pool `TITANIC_MULTIPLE` (5)
times what it was** -- a boost of four times; it added five on top, six in
all, before that day. The guardian calibration below was measured with
Hermie's TITANIC; it no longer applies as written.

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
`tests/test_resurrection_transfer.py`. **RAISE DEAD makes the same
transfer** (review, 2026-11-04: it moved the things, extracted the corpse
and ignored the save, so a failed save and a crash lost the kit it gave
back): both go through `corpse_give_to_owner` in `resurrect.c` --
`CORPSE_GIVE_REFUSED` before anything begins (an unsettled death, a held
corpse, a full Fixes list, a refused receipt), `DURABLE_FAILED` with
everything put back, `DURABLE_UNCERTAIN` left pending -- under the same
`resurrect:<id>` receipt, so boot and login settle either spell. RAISE
DEAD keeps its own rules: no consent, only what the owner can carry (the
rest falls to the floor once the transfer is on the disk; the held record,
whole, goes to history), and the owner is pulled to the caster only after.
It finds the owner by `resurrect_find_owner` (playing, never a copy loaded
from a file), refuses an owner hidden by WIZINVIS or protected by rank,
and asks `travel_spell_refuses` and `can_enter_private_room` of the
caster's room (`tests/test_raise_dead_transfer.py`).

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

**A death that cannot be recorded stays unsettled** (review, 2026-10-30:
a refused receipt or a full Fixes list left the corpse unpending, so
`corpse_registry_death_settle` saved nothing and a crash laid the corpse
beside a file holding the same things). The track is `PEND_UNRECORDED`
and its record says `State unrecorded`: nobody may take from the corpse,
and `corpse_registry_may_save` refuses every save of the owner, so their
file goes on holding everything -- that is what makes undoing the corpse
safe. `pend_retry` tries the receipt and mark again every ten seconds
while the owner is in the game, then saves them and the death settles as
any other. Before that: their leaving the game (the quit's save is
refused), a fresh login (`corpse_registry_login`, before anything at
login saves; a reconnect keeps the body that died) and a boot without a
committed receipt all undo the corpse to history as `undone`. Its cost is
that nothing the player does between the death and the recording is
saved. `death-recorded-crash` dies between recording and the save
(`tests/test_death_unrecorded.py`). **And nothing changes hands
meanwhile** (review, 2026-11-02: WITHDRAW one gold, GIVE it away, quit
and log in -- the taker kept it and the bank had it all back).
`corpse_registry_refuses_trade(ch, other)` -- true while
`corpse_registry_holds_still` (the owner's saves are refused) for either
party -- is asked first by GIVE (both ways), DROP, PUT into and GET from
anything not carried, DONATE, BUY, SELL, DEPOSIT, WITHDRAW, STASH,
SPLIT, STEAL and SACRIFICE, before anything moves. A new command that
moves coin or things between a character and anybody or anything else
asks it too. Saves stay refused: allowing them would defeat the
corpse's recovery (`tests/test_death_unrecorded_trade.py`). **Ask about
every party, not only the one typing** (review, 2026-11-03): STASH TAKE
asks about the owner it takes from (`corpse_registry_holds_still(owner)`,
an offline copy included) and SPLIT about every member it would pay --
the autosplit that picking up coin does goes through SPLIT -- and the
whole operation is refused. Looking moves nothing: STASH and STASH OF
stay open to a frozen character, and the actor's guard in `do_stash`
sits below them (`tests/test_stash_shared_transfer.py`,
`tests/test_split_frozen.py`).

## Who May Loot A Player's Corpse

`loot_refusal(ch, obj)` in `act_obj.c` is the one rule (owner, 2026-11-12:
a quit player's corpse was anybody's, and after a restart every corpse in
the world was, for the week a corpse lasts); `can_loot` is it as a bool.
The owner and staff (`is_staff`: an immortal by level, never a mortal's
trust and never a mobile's level)
always may; **no mobile ever may** -- a charmed follower ORDERed, a
janitor, a scavenger -- not even from a WANTED player's ownerless corpse;
while the owner is **in the game** (a playing descriptor whose `CH(d)` is
them -- not quit, not link-dead) their group may, and anybody when NOLOOT
gave leave (`PLR_CANLOOT`); while they are **not**, nobody else, whatever
NOLOOT said. **Killers are lootable, PKILL alone is not** (owner,
2026-11-12): a WANTED player's corpse has no owner (`make_corpse`, before
the death clears WANTED) and is anybody's -- a player's -- online or not;
a player who only had PKILL on and was attacked is protected like anyone
(`pk_state` is not leave). It returns why, for `act()`
with `$p` the corpse, and every way of taking from a corpse asks it of
the corpse at any depth (`loot_corpse_of`): GET of the corpse or out of
it, GET ALL, AUTOGOLD, SACRIFICE/JUNK of an empty one, TELEKINESIS, and
the mobiles' pick-ups (`spec_janitor`, the scavenger in `update.c`). A new
way of taking from or moving a player's corpse asks it too. **A death
still clears `PLR_CANLOOT`** (stock ROM, kept): leave is given per death
and the protection is what comes back, never what goes -- the review
that called this "death clears NOLOOT protection" had the flag backwards.
`tests/test_corpse_looting.py`.

## The Holiday Calendar

`src/holiday.c` (owner, 2026-11-02: World of Warcraft's schedule; minor
holidays simple -- clovers with a purpose, a Valentine's theme). One
table, `holidays[]`, holds every holiday: its key, name, dates, login and
TIME line, shopkeepers' word, treat and its chance, vendor and wares, and
decoration. Rules the code depends on:

- **One calendar.** `holiday_current()` decides what is on; season.c's
  `get_current_season()` asks `holiday_key()` and swaps areas for
  `halloween` and `xmas` only. A date is never compared anywhere else.
  The table is checked in order and the first match wins, so St.
  Patrick's Day (Mar 14-17) beats a Noblegarden that reaches back into
  it. Noblegarden is Easter week (`easter_date`, the Gregorian computus),
  Pilgrim's Bounty Thanksgiving week (`thanksgiving_day`, the fourth
  Thursday of November); the rest are fixed, Winter Veil across the new
  year. `HOLIDAYS <year>` prints any year's dates and `HOLIDAYS ON
  <yyyy-mm-dd>` any day's holiday from the same code. The calendar reads
  the host's local clock (`localtime`, the TZ the game runs under).
- **The arithmetic is `src/holiday_rules.c`** (review, 2026-11-02): day
  numbers, strict date parsing (`holiday_parse_date`: a real YYYY-MM-DD
  from 1900 to 9999, nothing else), Easter, Thanksgiving and the
  firework cooldown table. It includes no `merc.h`, so
  `tests/test_holiday_rules.c` checks every day from 1900 to 9999 and the
  cooldown at its boundaries; put new pure calendar rules there.
- **Test switches**: `TOC_SEASON` takes any holiday's key (`love`,
  `stpatrick`, `noblegarden`, ...) or `none`, which `tests/live_mud.py`
  sets by default; `TOC_DATE=YYYY-MM-DD` sets the date the calendar reads,
  and `TOC_DATE_FILE` names a file holding one, read at every look at the
  date, so a test walks one running world from holiday to holiday
  (`tests/test_holiday_lifecycle.py`). A test date that is not a real
  date is logged once and the clock used; staff HOLIDAYS says where the
  date came from. `TOC_HOLIDAY_DROPS=always` makes every NPC kill drop
  the treat. TIME's
  holiday line is the last line of `TIME_BARRIER_RE`, so a synced reply
  never carries it.
- **The fair is put up by the tick** (`holiday_tick`, from
  `tick_event_boss`): the decoration in the Oak Tree Square (2401) and
  the vendor for the whole holiday, both taken down when it ends, eggs
  too. Staff `HOLIDAYS REFRESH` runs it at once, and repeated refreshes
  never double it. **The vendor and the event boss are cleared at
  extraction** (`holiday_forget`, `event_boss_forget`, from
  `extract_char` beside `black_market_forget`), never found again by
  scanning the character list for their address: the allocator may hand
  a freed CHAR_DATA's address to the next mobile created, so PURGE ROSALIND then LOAD MOB
  made the loaded mobile "the vendor" (review, 2026-11-02). A boss slain
  is announced by `record_event_boss_defeat`; any other way out (PURGE,
  SUMMONEVENT, the timer) is logged "left the world without being slain"
  and announced as nothing. The boss is the actor of its own arrival and
  departure lines -- `act()` with no actor sends nothing. The two
  seasons' vendors (Hexley, Tinsel) are rows like the rest and no longer
  spawn at random. A decoration is found by vnum, never kept as a
  pointer.
- **Eggs**: the hunt keeps `EGG_CEILING` eggs lying in the square's own
  area (`eggs_lying(square->area)`; eggs dropped elsewhere do not starve
  it), and when Noblegarden ends `eggs_clear()` takes every egg lying on
  the ground anywhere, extracting as it walks the object list (tombstones
  make that safe); carried and contained eggs are their holders'.
- **Treats with a purpose**, each one hook: `holiday_corpse_drop`
  (make_corpse; red envelopes and eggs are filled as made, coin counted
  in kills at the carrier's level), `holiday_kill` (raw_kill, before the
  corpse: a clover's pot of gold goes into the victim's purse so the
  corpse lays it out), `holiday_eaten` (do_eat, after the object is gone:
  clover luck, candy heart, trick-or-treat), `holiday_given` (do_give: a
  rose to another player blesses both and is spent), `holiday_dropped`
  (single DROP: a firework; each area hears one at most every
  `FIREWORK_AREA_GAP` seconds, on its own clock in `firework_heard[]`,
  so rockets are no way to shout -- a single "last area" let A, B, A
  broadcast three times; review, 2026-11-02). Clover
  luck is `pcdata->holiday_luck`, memory only, at most `LUCK_MAX`; a
  clover past the cap is refused before the bite (`holiday_eat_refused`)
  and eating one says how much luck is held.
  `holiday_snack` lets a clover, a candy heart and trick-or-treat candy
  past "too full" -- every new character starts full.
- **Holiday objects are unlevelled** (level 0), so
  `tools/reprice_by_level.py` leaves their prices alone and they price no
  shelf; nothing sold is free, since a shop sells at least for a copper.
- `tests/test_holidays.py` plays the calendar by date (Noblegarden in
  2027, Easter and Thanksgiving across two years), Love's rose, St.
  Patrick's clover and pot of gold, the Lunar envelope, Midsummer's
  firework, trick-or-treat candy and an empty square out of season;
  `tests/test_holiday_lifecycle.py` the review's findings (a recycled
  vendor or boss, removal against defeat, the boss's room lines, the egg
  budget and cleanup at 1, 96, 97 and 120, transitions in one process)
  and a HOLIDAYS ON matrix of every holiday's boundaries.
- **Staff HOLIDAYS** also says which seasonal areas boot loaded
  (`season_loaded_name()`; SUMMONEVENT STATUS too): they swap only at a
  reboot, so they can disagree with the holiday on the calendar -- until
  the automatic restart below.
- **The game restarts itself for Hallows End and Winter Veil** (owner,
  2026-11-12: "in the middle of the night the game will automatically
  reboot itself to the new holiday. maybe 3-4am EST"). `season_restart_update`
  (season.c, once a second from update_handler's memory pulse) holds
  `season_loaded` to `get_current_season()`; when they differ, it is 3:00
  to 3:59 in New York and the game has been up `SEASON_RESTART_MIN_UPTIME`
  (an hour), it announces (`announce_to_world`) five minutes and one
  minute ahead, saves every player and ends as REBOOT does --
  `game_reboot_unattended()` then `game_reboot_close()` in act_wiz.c,
  which `do_reboot` shares: no `shutdown.txt`, so `toc-game.service`
  (`Restart=always`), `startup.sh` and the container start it again. It
  is called off if the two agree again before it goes. **New York time is
  `holiday_new_york_time()` in holiday_rules.c**, from UTC by the US rule
  (second Sunday of March 07:00 UTC to first Sunday of November 06:00
  UTC), never `localtime`: the live host runs in UTC. The hour of uptime
  is the only loop guard: a boot that still disagrees is not an hour old
  before the window closes; nothing is written to disk. Staff HOLIDAYS
  RESTART [NOW|CANCEL]: CANCEL (trust `MAX_LEVEL`) skips that night's
  window, NOW (`LEVEL_CREATOR`, REBOOT's rank) starts the warning at any
  hour. Tests only: `TOC_SEASON_REBOOT_ANYHOUR`,
  `TOC_SEASON_REBOOT_WARN_SECS`, `TOC_SEASON_REBOOT_MIN_UPTIME`
  (`tests/test_season_restart.py`; the clock, every minute of 2007-2100
  and against zoneinfo, `tests/test_holiday_rules.c`/`.py`). Every other
  holiday follows the calendar on the tick and restarts nothing. A live
  test that walks the date with `TOC_SEASON` unset across Oct 18, Nov 2,
  Dec 16 or Jan 7 is safe: its world is never an hour old.

## The Seasonal Areas Are Generated

`src/season.c` swaps three areas for a holiday copy **at boot**: `dresden`,
`limbo` and `midennir` load as `<base>_halloween.are` from Oct 18 to Nov 1
(Hallows End) and as `<base>_xmas.are` from Dec 16 to Jan 6 (Winter Veil),
and restarts itself at 3am New York when the copies loaded disagree with
the calendar (The Holiday Calendar, above). The copies are built by `python3 scripts/build_seasonal_areas.py` (`make
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
  `scripts/check_exits.py` and the shop price test read `area.lst`, so they
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
- **The entrypoint (`scripts/docker-entrypoint.sh`) and the native runner
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

## Fuzzing The Readers

Owner, 2026-11-12: every serious bug of late was in a file reader, so the
readers are fuzzed. `tests/fuzz/README.md` is the guide (the harness moved
from a root `fuzz/` into `tests/fuzz/` on 2026-11-12). Three libFuzzer
targets with ASan and UBSan, built by `tests/fuzz/build.sh` (clang and, on
Ubuntu, `libclang-rt-18-dev`) into the root's `build-fuzz/`, run by
`tests/fuzz/run.sh <target> <seconds>`. Nothing in it is a test module
(`discover` and the runner take `tests/test_*.py` only), and
`scripts/ci/classify.py` treats `tests/fuzz/**` as the harness: a change
anywhere in it runs the full suite:

- `fuzz_numparse` -- `numparse.c` against an independent 128-bit reference.
- `fuzz_player` -- a player file through `offline_player_load`, in a booted
  copy of the world: any `exit()` while reading is a crash (a player file
  refuses that character, never the game), no player may be left in the
  character list after `extract_char`, a file it accepts must survive the
  game's own save and load again, and LeakSanitizer checks (at the run's
  end at least: libFuzzer stops checking per input once global state grows).
- `fuzz_area` -- one extra area file at boot, every section loader plus
  `fix_exits`/`fix_reset_room_limits`, on an empty world: a malformed file
  must stop the boot through `exit()` (which the harness catches with
  `-Wl,--wrap=exit`), never crash, read out of bounds or hang.

The fuzz build compiles the game again with `-DTOC_FUZZ`, which adds only
`fuzz_world_mark`/`fuzz_world_rewind` to `db.c` (the Make and CMake
builds never define it). **A loader that writes a new global must have it
saved and put back there**, or the area target's inputs start meeting
each other's records. Seeds are synthetic only (`tests/fuzz/make_seeds.py` makes
the player ones in a throwaway world; never a real character's file);
`tests/fuzz/make_dict.py` takes the player dictionary from `save.c`'s keys.
Every input that ever found something is in `tests/fuzz/regressions/`, and
`tests/test_fuzz_smoke.py` builds the targets, replays them all and fuzzes
each target for a fixed count of inputs from a fixed seed (so CI cannot
fail on luck; the search proper is `run.sh`'s) -- CI installs clang on the
shard that runs it. A new finding's input goes in `tests/fuzz/regressions/`.
`tests/test_fuzz_findings.py` holds each finding to the real game.

What the first runs found (2026-11-12; about an hour of the player
target and 45 minutes of the area target, some 19 million inputs between
them, the last ten minutes of each clean; the README's table has them
all), each fixed:

- **An unknown key in a player file crashed the game** at that player's
  login: `bug()` formats an `int`, and `fread_char` passed the word's
  pointer cut to one, printed with `%s`. A rollback to an older build meets
  exactly that. Format a string into a buffer before `bug()`; never pass a
  pointer as its parameter -- and **`bug()` takes its text as a format**:
  a buffer holding anything a file or a player wrote has its `%`s taken
  out first, or a key `%n` writes through a null pointer (the second
  finding, once the first was fixed).
- **A refused player file with a pet and no `Room` crashed the game** in
  `free_char`'s `nuke_pets`: `stop_follower` asked `can_see` of a master
  with no room. Rooms are checked first now.
- **A player file whose `Act` carries bit A (`ACT_IS_NPC`) crashed the
  game at that login**: the player read as a mobile with no prototype.
  `fread_char` clears the bit and `fread_pet` sets it (a pet without it
  read as a player with no `pcdata`).
- **Quitting could duplicate a wielded weapon** (found as a crash freeing
  a refused, roomless copy): `extract_char` takes a player's things off
  one by one, and taking off a strength item let `affect_modify`'s
  low-strength check drop the wielded weapon into the room -- a copy the
  saved file still held, left on the floor whenever another object was
  carried between the two. `extract_obj_player` now holds that drop off
  (`unequip_leaving` in `handler.c`), and a roomless character never drops.
- **A player could lock themselves out with ALIAS** (the roundtrip
  oracle): `ALIAS "'ZQ" LOOK` saved `Alias 'zq look~`, which
  `fread_word` reads as an opening quote, so the rest of the file was
  read out of step and the next login refused the character. ALIAS
  refuses a name starting with a quote, the writer skips one (and an
  empty name), and the reader drops a nameless alias. Anything written
  as a bare word ahead of a string must be a word `fread_word` reads back.
- **A class, race or guild outside the tables** (`Cla 14`, a race no
  player may be, `Gui 9`) was read past the end of `class_table` and
  `pc_race_table` from the first stat asked for, and a `NumRemorts` of
  millions overflowed `reset_char`'s arithmetic, as an old file's gold
  `Cost` did multiplied into copper. `load_char_obj` refuses
  the character, file untouched, and gives the discarded copy values the
  tables hold so `free_char` can take off its worn things safely. A new
  field that indexes a table or scales arithmetic is checked there too.
  A second `#PLAYER` record is refused, as a second pet is.
- **An offline load of a file with no `Room`** left the copy in the
  character list (`extract_char` refuses a roomless character), and the
  player's next login "reconnected" into it. `offline_player_load` places
  it where a login would.
- **An area file cut off mid-string hung the boot** -- `bug()`'s line
  count read past EOF for ever -- a spell slot no spell has `abort()`ed
  it, a door reset in a negative room crashed it (`get_room_index`
  answers NULL for a negative vnum even at boot), a room affect type
  outside `room_aff_type[]` was read out of bounds, and a `#SOCIALS`
  section past `MAX_SOCIALS` wrote past the table. Each stops the boot
  cleanly now.
- **Leaks on every load**: the name `load_char_obj` starts with, the first
  of any repeated string key (`KEYS` in `save.c` frees what it replaces --
  use it for a new string key), the race name, a pet's or character's
  affect cut short by a malformed number (linked at once now, as an
  object's was), and every `capitalize()` -- a fresh `str_dup` nobody
  freed, at every save, file path and display. It returns one of a ring of
  sixteen static buffers now: use the result at once or copy it.

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

**The layout is drawn for Mudlet's mapper, and three things kept it from
reading** (owner, 2026-11-12, from a Mudlet 5.1.1 screenshot: "the way the
layers look on the map in mudlet is disorienting ... it's the map
everywhere. dresden is a mess"; Mudlet's source read for each):

- **Mudlet 5 draws the level above and below** the one shown, in the same
  area -- the level below as filled grey squares, the level above outlined
  (`TMapPainter.cpp`, `mudlet::mDrawUpperLowerLevels`, default on; 4.x has
  neither the drawing nor the key). It is a Mudlet-wide setting, not a
  profile's, so **the package never changes it silently** (owner,
  2026-11-12; package 1.5.15, `tocMudlet.applyLevels`): it hides the floors
  once per profile with `setConfig("showUpperLowerLevels", false)` and a line
  saying what it was (`getConfig`; when that cannot be read it says so and
  never guesses), what it is now and how to change it, keeping the old value
  as `levelsOriginal` in `toc-settings.lua`. After `tocgui levels
  on|off|toggle` (`levelsChoice`) it never touches the setting again, at start
  or anywhere; `original` and `status` exist too, and a 1.5.13/14
  `showLevels` toggle is carried over as the choice. Never reintroduce an
  apply-at-every-start. The strip over the mapper (`tocMudlet.showFloor`)
  names the map area and floor, and `tocgui mapcheck` (`tocMudlet.mapCheck`,
  bounded: 5,000 area rooms, 80 rooms within four steps, five examples a
  kind) reports the floors setting, the atlas layout against the profile's,
  rooms sharing a square in the area and bent or stretched exits near the
  player, by `exit_drawn_straight`'s rule.
- **`tocgui atlas` never replaces the map on one word** (owner, 2026-11-12):
  alone it explains what is lost; `backup` saves the map with `saveMap` as
  `toc-map-backup-<stamp>.dat` in the profile's folder; `confirm` backs up
  and loads only if the save landed; `force` loads without one. Keep the
  `ATLAS_LAYOUT` notice pointing at `tocgui atlas`.
- **`layout_area` opens the level instead of bending an exit.** A room
  whose square is taken used to go to the nearest free one, which bent every
  exit around it and packed Dresden into a block where neighbouring squares
  were not neighbouring rooms. Now every room on that level past the square
  moves one step on in the exit's direction (a half-plane moved alike can
  never stack two rooms), so exits keep their direction and are only
  stretched; `_settle` then moves or swaps single rooms while that
  straightens exits; each connected part is laid out alone and `_pack`s
  them in rows, the busiest level of each at z 0. Mudlet draws a planar exit
  as a line to wherever its room sits in the area, on any level, and up and
  down as a mark in the room: `exit_drawn_straight` is that rule, and
  `tests/test_mudlet_map_layout.py` holds the share of exits it passes (95%
  world-wide, 91% in Dresden on 2026-11-12; 89% and 73% before) and that no
  two rooms of an area share a square -- `build_map_bytes` also refuses to
  write one. A change to the layout changes every player's map only when
  they type `tocgui atlas`; bump `tocMudlet.ATLAS_LAYOUT` with a layout
  change so a profile on the old one is told once a session.
- **Each Hyrule dungeon is a map area of its own**, `Hyrule: Level N
  (<title>)` (`hyrule_map_area_name` in `src/hyrule.c`), on its floor plan:
  column x, row -y, z 0, cellars z -1 under the room they open from
  (`hyrule_map_place`, reading the plan from the dungeon map's prototype).
  `Hyrule.MapRoom`'s `area` is that name, and `Room.Info` for a dungeon room
  carries `"map": {"area", "x", "y", "z"}`; its own `area` stays the game's.
  They used to be the overworld's area: a plan ten levels down per dungeon,
  and a room walked into one step from the gate's, under the overworld. The
  dungeons stay off the atlas itself (owner, 2026-10-04).
- **The package keeps the atlas's area and square** for a room already on
  the map; only a room it creates takes `Room.Info`'s area (placed beside
  the room walked from), and a room `Room.Info` places with `map` goes
  exactly there every time. Moving every room into the area Room.Info named
  would undo any area split the atlas makes. The fog (`toc-fog.lua`) keeps
  each room's area by name, so dungeon areas survive a fog round trip.

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

90 of the 91 areas holding rooms have a route. Dresden has none because it
contains the start room. The Quest Zone's rooms and Temple Despair, which
nothing linked to, were removed on 2026-11-11 (owner: "remove any old unused
data"); `quest1.are` keeps only the objects the quest master and the newbie
kit hand out.

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

**A damaged corpse or snapshot is that file's problem, never the game's**
(review, 2026-11-12: a six-megabyte string in a corpse file ran off the
end of the string space and the boot died). `fread_string` and
`fread_string_eol` stop at the end of `string_space` as a malformed value
-- they used to check for room only once, before the string -- and
`read_objects_aside` (corpses, PRESTORE GEAR and STASH) reads under
`fread_aside_trap`, which only `fread_malformed` answers: the object part
read is released, the rest discarded, and the caller gets -1 ("a value in
its objects could not be read"), so a corpse at boot is renamed
`.unreadable` and the boot goes on. The player trap is set aside while it
reads, so a jump never lands in a loader further up the stack, and
`fread_obj_refuse` keeps its trapless handling there
(`tests/test_corpse_boot_damaged.py`).

**A player file with a malformed number refuses that character, never
the game** (roadmap, 2026-11-09). `fread_number`/`fread_long`/
`fread_string_eol` went to `exit(1)`, so one damaged file stopped the game
at that player's name prompt, and every reconnect again. While
`load_char_obj` reads a player file it arms `fread_player_trap` (a
`jmp_buf`); `fread_malformed` in `db.c` jumps back there, the copy gets
`pcdata->load_failed`, and the name prompt, `login_reload_character` and
`offline_player_load` refuse it (`player_file_unreadable`) -- never taking
it for a new name, which would save over the file. `save_char_obj`
refuses such a copy. Area files still fail fast at boot. A pet record is
the character's from `create_mobile` on, so a file abandoned mid-pet
leaves it to `free_char`; and a pet whose mobile and stand-in
(`MOB_VNUM_FIDO`) are both missing is left out instead of reaching
`create_mobile(NULL)`, which exited. `tests/test_player_file_refusal.py`
(also under the sanitizers). **One Nest a record, and nothing nested in
itself** (review, 2026-11-10): a second Nest pointed two slots at the
unfinished object, which became its own container, and the carry-weight
walk up its `in_obj` chain hung the game at that player's name. A
repeated Nest refuses the character before any slot moves, and
`fread_obj_nest_cycles` refuses a container chain that reaches the object
(readers with no trap keep the first Nest and the object loose).

**Only proven absence is a new character, and only a whole file is the
character** (review, 2026-11-09). A failed `fopen` was taken for "no such
player": a mode-000 file let the name be created again and the save
replaced a level 20 with a level 1. `player_file_presence()` in `save.c`
answers `PLAYER_FILE_ABSENT` only for `stat`'s ENOENT on the file and its
`.gz`; anything else is `PRESENT` or `UNKNOWN`, and the name prompt,
`new_name_still_free` and RENAME treat both as taken. A file that is
there and does not open, a section marker the loader does not know, a
line that is not a record, a file that ends before `#END`, a read error
(`ferror`) and a failed `fclose` all refuse the character exactly as a
malformed value does -- they used to load what came before and let the
next save write the shorter character over the file. A `.gz` copy is
decompressed only where no plain file exists. An object part way through
its record when reading stops is released (`fread_obj_unfinished`):
`create_object` had registered it, and every refused attempt left one
more object owned by nobody in the world. An object affect is linked as
soon as it is allocated. Fault points `player-open-<Name>` and
`player-read-<Name>` (`TOC_FAULT`) fail the open or the read.
**The release trusts nothing the record wrote** (review, 2026-11-09): the
prototype whose count `create_object` raised is kept apart
(`fread_obj_unfinished_index`), because a second `Vnum` key rewrote
`obj->pIndexData` -- to NULL, and the release took the game down, or to
another prototype, whose count it then lowered. A record with two Vnums
and a known object's record with no `Nest` refuse the character
(`fread_obj_refuse`, which jumps to the trap with 2 and a reason): the
dropped object let the next save write the character without it, and
went back to the pool still in the object list. A vanished prototype is
the old, kept case -- dropped, its contents loose. Readers with no trap
(a snapshot read aside, a corpse) keep their old behaviour, now through
the same release. OSHOW ends with how many of the prototype the world
holds, so a drifting count can be seen.

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

## The Hall Of Heroes' Rolls

`src/heroes.c` (owner, 2026-11-11). `heroes/<Name>` keeps one record per
character who has reached hero level or been reborn: the old first line
(`Lev N Trust N  Name title`), then `Since` (first became a hero; 0 for
records from before), `Remorts`, `Reborn` (last remort), `Class`, `Race`.
`hero_record_write(ch, reborn)` writes it from `advance_level` the moment a
character reaches hero level, from `do_remort`, and at every save; staff
(`is_staff`: immortals by level, and the creator; owner, 2026-11-12) are
on neither roll, and a record reads as staff by `hero_rank_is_staff` --
level 60 or more, or the creator's trust of 72 -- so a mortal given trust
is on the rolls. `hero_records_backfill`
fills older records once at boot from the player files, active or archived.
In the Hall of Heroes (4649), LOOK PLAQUE shows the newest heroes and the
whole roll; LOOK TABLET (stone, reborn, remorts) the reborn, most lives
first. Records are never removed: the plaque keeps heroes whose characters
are gone (`tests/test_hero_rolls.py`). A record whose first line
names staff rank is on neither roll; a mortal later promoted has the rank
written into their record at their next save, or at boot from their file,
and keeps it (hidden) for a demotion. Its numbers are read with the checked
parsers: a malformed one is 0, never atoi's guess.

## The Player Archive

Owner, 2026-11-11: archive old players for backup, and bring one back by
itself when its player returns. At a serving boot (never `--check-area`)
`player_archive_dormant()` in `save.c` moves every character whose file was
last saved (`LogO`, or `LastOut` if newer) more than `PLAYER_ARCHIVE_DAYS`
(730) ago from `player/` to `player/archive/` (`TOC_ARCHIVE_DAYS` for
tests). Nothing is deleted, and the state sync carries both folders. Rules:

- **An archived name is taken**: `player_file_presence` looks in the archive.
- **Anything that loads or rewrites a character brings it back first**:
  `player_unarchive()`, from `load_char_obj` (login, `offline_player_load`),
  PRESTORE and RESETPWD. A new command that rewrites an offline file calls it.
- **Views that only read it read it where it lies**:
  `player_file_read_path()` (FINGER, MIRROR, ACTIVITY, the benchmark board,
  stash links, `player_file_fix_has`). Snapshots in `player/versions/` stay put.
- Python tools and the dashboard list `player/` only, so archived
  characters are not in their lists. `tests/test_player_archive.py`.

## No Pointer Outlives Its Target

Since the pools went (2026-11-11), a pointer to a character, object or
descriptor that survives into a later pass reads freed memory. An audit
found five and each is fixed and pinned (`tests/test_stale_pointers.py`):
`extract_char` stops every hunt or TRACK aimed at the one leaving and
clears any switched descriptor's `original` that names it; the idle purge
skips a body whose player is switched (`body_is_switched_from`);
`do_stop_hunting` clears a pointer the hunter list does not hold (a
player's TRACK); a bottled mobile and its bottle are unlinked both ways,
and a bottle leaving with nowhere to open takes its mobile with it
(`captive_dispose`); corpse tracks match by pointer alone; the relic globals
are cleared when their object goes. A new field or global that points at a
character or object is cleared in `extract_char`/`extract_obj` or a
`*_forget` hook, or looked up by id.

**A bottle destroyed is not a bottle opened** (review, 2026-11-12). An
object saved with `Trap <vnum>` makes its creature again whenever the file
is read, so letting it out when the object left memory -- the name
prompt's copy freed (a hang-up, a wrong password, the reload after a right
one), an offline load, a quit -- put one more in the world each time,
without the password. `extract_obj` and `extract_obj_player` call
`captive_dispose`, which unlinks the captive and extracts it, never
placing it in a room. Only an act of play opening the bottle calls
`char_from_obj`: OPEN, the genie's lever (manipulation case 2) and a
bottle that shatters with age (`obj_update`, before `obj_from_obj`; never
one in a stash, whose timers do not run -- `obj_held_nowhere`). It
lets the creature out where the bottle lies or its holder, at any depth of
containers, really stands (`captive_carrier_placed`: in the room's
people, not a file copy's `in_room`), and disposes of it anywhere else. A
new way of letting one out calls `char_from_obj` before destroying the
bottle (`tests/test_bottled_captives.py`). The genie lever (manipulation
`value[4]` 2) lets out the captive of the bottle it names
(`find_obj->trapped`); it read its own and let nothing out.

**One pet a file and one captive a bottle** (review, 2026-11-12). A
second `#PET` or a second `Trap` in one object made another mobile and
overwrote `ch->pet` or `obj->trapped`, leaving the first registered and
pointing at a character or bottle that was then freed -- a use after free
in the memory sweep. Both refuse the character through the loader's trap
(`fread_obj_refuse`; "has two pet records", "has an object record with two
traps") before anything is made, so the file stays as it is; a reader
with no trap makes nothing for the second. A record malformed after a pet
or captive was made is refused and frees it (`free_char`'s `nuke_pets`,
`fread_obj_release_unfinished`) (`tests/test_duplicate_ownership.py`).

## Pools Are Not 16-Bit

Owner, 2026-11-11. Hit points, mana and endurance -- the live pools, the
permanent ones (`pcdata->perm_hit/mana/move`) and every affect's
`modifier` -- are `int`, held to `POOL_MAX` (a billion, in `merc.h`) so a
pool plus its bonuses never overflows. SET HP/MANA/END/MOVE/MAXMOVE,
TITANIC's boost and the black dragon's size stop there, not at
the 30,000 the old 16-bit fields forced. Never cast a pool or a modifier
through `(sh_int)` or `clamp_sh_int` again (`tests/test_pool_cap.py`).
**So is WIMPY** (review, 2026-11-12: with 100,000 hit points WIMPY 40000
said 40000 and stored -25536, which never flees). `ch->wimpy` is an
`int`; WIMPY (a fifth of the maximum by default, at most half), SET CHAR
WIMPY (0 to `POOL_MAX`), the remort cut and `Wimp` in the file carry it
whole, and a wrapped negative an old file holds reads as 0
(`tests/test_wide_wimpy.py`).
**So is every sum on a maximum** (review, 2026-11-12). Every bonus to
`max_hit`/`max_mana`/`max_move` -- `affect_modify`, `reset_char`, the
load's unwear, a level, TRAIN -- goes through `pool_max_adjust()` in
`handler.c`: the stored maximum, what an earlier clamp carried and the
change are summed in long long, the maximum held to `[POOL_FLOOR,
POOL_MAX]` (minus a billion to a billion: not 1, because a maximum below
zero is the wreck `reset_char` rebuilds), and the rest kept in
`ch->pool_carry[]`, so taking a bonus off gives back exactly what was
there. The carry is saved as `PoolCarry <hit> <mana> <move>` under **case
'P'** only when not zero: `reset_char`'s full rebuild takes the bonuses
off the saved maximum, and without it took them off the clamped one. A
maximum set outright from its base clears it (`pool_carry_clear`). **SET
HP/MANA/END set the base** (`pool_set_base`): `perm_*` and the maximum
with every standing bonus -- worn gear as `reset_char` counts it, spells
-- on top, as a reload would make it; SET under a TITANIC used to leave
the boost to come off a value it never went on, and the maximum at
-799,999,900. A mobile has no base and gets the value. SET MAXMOVE and
ADVANCE's lowering still set the maximum exactly (`tests/test_pool_sums.py`;
the fixture ring of vigour, object 32713, is +1,000 hit points).
**Arithmetic on a pool is wide too** (review, 2026-11-11: 100 * hit
overflowed at 21 million, so LOOK called a character at 30 million of 30
million dying, and divine protection's max * 3 / 4 wrapped negative at a
billion). Multiply a pool only through `pool_percent`, `pool_scale` and
`pool_at_most` in `combat_rules.c`, which work in long long and bring the
answer back into range (`tests/test_pool_arithmetic.py`, also under UBSan).
SET CHAR refuses a numeric field whose value does not parse
(`mset_field_is_numeric`) before the snapshot; it used to read as -1.
Player files need nothing: `HMVP` and the affect lines were always plain
numbers.

## Vnums Are Not 16-Bit

Owner, 2026-11-11. A room's, mobile's and object's vnum, and everything
that carries one -- an exit's destination and key, a reset's arguments, a
shop's keeper, an area's declared range, a teleport room's destination,
the class table's guild rooms and first weapon, a guildmaster's vnum, a
quest's target -- is `int`, held to `MAX_VNUM` (1,000,000, in `merc.h`).
The ceiling bounds the tables indexed by vnum (WALKTO's search slots, the
black market's placed and key tables, the free-block finder's map), which
are touched only where vnums are in use, and stays far from `INT_MAX`.
`WORLD_SIZE` (30,000) is gone: ANEW, DIG and GOTO take `MAX_VNUM`, and
the room saver walks to `top_vnum_room` -- it stopped at 30,000 and left
every room above it out of RSAVE's file. `top_vnum_room`, `top_vnum_mob`
and `top_vnum_obj` (db.c, kept wherever a prototype enters a hash) are
how far a walk over vnums or a random guess (`random_room_candidate`,
TELEPORT, the old `number_range( 0, 65535 )`) goes; ALIST and the
free-block finder walk the hashes instead. The area loaders read a
record's vnum with `fread_record_vnum`, which stops the boot on one
outside 1..`MAX_VNUM` (it used to wrap: #40000 hashed to a negative
bucket and the boot crashed), and `load_areadata` refuses a built area's
`VNUMs` range that leaves 1..`MAX_VNUM`, since the range bounds every walk
over its prototypes and a short used to cap it. Vnums typed by staff are
parsed whole (`parse_int`), never cut at five digits -- MSHOW, OSHOW, SET MOB/OBJ,
MCREATE, OCREATE, RSHOW and BUILD all had `strlen( arg ) > 5`. Area files
and player files always wrote vnums as plain decimal numbers, so nothing
on disk changed and no migration exists. Never store a vnum in `sh_int`
again (`tests/test_wide_vnums.py`, which also boots an area numbered from
40,000 to 900,000 and plays it).

**A number past its type is malformed, never wrapped** (review of
d19b0e92, 2026-11-12). `fread_number`, `fread_long` and `fread_flag`'s
digits accumulated with no check, so `#4295367296` overflowed (undefined
behaviour) and wrapped to 400000 -- inside every range check after it --
and `--check-area` passed. Each digit now goes through `digit_append`
(`numparse.c`, before the arithmetic) and `|` sums through
`int_add_checked`; an overflow is `fread_malformed`: the boot stops with
the file and line, a player file refuses that character. Every digit is
still consumed. `fread_flag`'s letters read as they always did. A field
written as a `long` must be read with `fread_long`, or the first value
past `INT_MAX` now refuses the file instead of wrapping (a note's stamp
went to `fread_long` for that reason). **The stash/gear/corpse scan
(`scan_number_value` in `save.c`) refuses exactly what the readers
refuse**: `read_objects_aside` has no trap, and a number the scan passed
and `fread_number` refused exited the game from PRESTORE STASH. A new
reader without the trap needs a scan that agrees with it.
`webadmin/area_reader.py` refuses the same numbers.
`tests/test_number_overflow.py` (record, exit, key, reset, shop, special
and `#AREADATA` numbers, cost, flags, player `Room`/`RecallRoom`/object
`Vnum`, the PRESTORE STASH scan) and `tests/test_vnum_boundaries.py`
(32767, 32768, 65535, 65536 and 1,000,000 loaded, walked, reset, saved by
the writer and a player, and reloaded), both in `SANITIZE_MODULES`. The
shipped world and player files held no such value on 2026-11-12.

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

**A fix corrected after it shipped runs again under a new id.** A fix is
marked done once it runs, whatever it did, so changing its function
reaches nobody it already marked: `20261029-spare-shards` took back at
most 64 shards, and lifting the cap left those it had visited with the
rest. `20261030-spare-shards-again` runs the corrected sweep for
everyone. Write the function so a second run is harmless
(`tests/test_hyrule_spare_shards.py`).

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
  2026-10-23: unconfirmed writes were reported as done). **A snapshot's
  directories are durable too** (review, 2026-11-04): `snapshot_ensure_dir`
  flushes a new directory's parent, and one found already there (EEXIST)
  is flushed once per process before it counts, since an earlier run may
  have made it without confirming it; a copy inside a directory not
  confirmed is published but not `durable`.
- **A choice that cannot be taken back waits for its milestone**
  (review, 2026-11-04: DELETE went on after its save failed, left a
  milestone of the older file and deleted the newer one).
  `player_milestone_required(asker, ch, tag)` is the current character
  saved, copied whole, on the disk and in the ledger, or a refusal that
  says so; DELETE, REMORT, COMBINE, ADVANCE and a staff SET ask it.
  DELETE then retires the uid (`recovery_player_retire` answers whether
  it was recorded) and removes the file, each checked and the uid put
  back if the file stays, and only then quits without saving
  (`quit_discards_file`) -- a save would write the file back. CREATOR and
  GRANTPSI take nothing away and only report a copy that did not land; a
  death cannot be refused and keeps its own handling
  (`tests/test_delete_milestone.py`).
- **The throttle and the prune read the directory as little as they
  can** (review, 2026-11-04). The newest copy of each player is kept in
  memory (`snap_newest`) from one scan and every publication, and read
  again only when the file it names is gone; the throttle still reads that
  file's own time. A milestone's prune reads and sorts the directory once
  for both its kind and the ordinary saves (`snapshot_prune_pass`), and
  `recovery_snapshot_uid` answers from an index built at boot from the
  ledger's whole records and kept up by each append (`snap_uid_note`). Test faults:
  `TOC_FAULT` (`fsync`, `dirsync`, and `autowrite`, which holds every
  save the tick makes on its own -- the autosave and bank interest's -- off for a test that must know which save wrote a file --
  matched by substring, so never a name holding `save`) and `TOC_FAULT_FILE` (one named point,
  `save 2` for the second save, `save-<Name> 2` for that character's
  second, which an autosave of somebody else cannot take -- though one
  of that character can, so ACCEPT's save has its own `accept-save`
  (CI, 2026-10-27), a death's `death-save-<Name>`, a craft's
  `craft-save`, GRANTPSI's `grantpsi-save` and a PRESTORE give's or retry's `prestore-save`; `dirsync-<Name>` makes that character's next save
  unconfirmed, `corpse-move` fails a corpse record's move into history;
  `ledger`, `crash-before-commit`, `death-recorded-crash`, RAISE DEAD's
`raise-save`, `snapshot-dir` (a versions directory's flush into its
parent); STASH TAKE's
  `stash-owner-save`, `stash-taker-save` and `stash-crash-between`, and
  `stash-owner-rewrite` -- the putting back, named without `save` so
  `TOC_FAULT` can hold it beside a `TOC_FAULT_FILE` point), read
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
  the corpse holds things; any restore ends the owner's corpses and takes any
  still in the world out of it (`corpse_registry_forget_player`; a FORCE
  restore of a lying corpse left it there holding the same things, 2026-11-13).
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
- **The game loop's pacing, its systemd watchdog ping and every measured
  duration use the monotonic clock** (`loop_clock`/`monotonic_ms` in
  `comm.c`; `playlog_now_ms` is it): a wall clock stepped back no longer
  sleeps the loop or starves `WatchdogSec`. `current_time` stays the wall
  clock for everything persisted and for the calendar. The ledger and
  lockout readers drain a line longer than their buffer instead of
  reading its tail as a record.
- **The in-game archives of `player/`** (`backups/<Mon.DD.YYYY-HH.MM.SS>.tar.gz`
  every four hours, `backups/<Mon.DD>.tar.gz` daily; `backup_launch` in
  `update.c`) are made by a detached shell, never on the game loop
  (2026-11-08), and **a failed one never costs the last good one**
  (review, 2026-11-09: tar wrote the day's name in place). Each job holds
  an `flock` on `backups/.backup.flock`, taken by the forked worker before
  the shell runs and kept by the shell and everything it starts, and waits
  its turn -- boot starts both. **Never a lock a job can judge stale**
  (review, 2026-11-09): the directory lock it replaced was reaped by two
  jobs that both saw one dead owner, the second deleting the lock the
  first had just taken, and both wrote. A job removes only temporaries
  whose writer's pid (in the name) is gone and an old directory lock whose
  owner is gone; it writes `.<name>.tar.gz.tmp.<pid>`, accepts it only on
  tar 0 or 1, non-empty, `gzip -t` and a full `tar t` listing, and renames
  it over the name; any failure or signal removes its own temporary and
  logs that the previous archive is kept. `tests/test_backup_detached.py`
  plays failure, interruption, a held lock, live and dead owners, overlap
  and replacement with a stand-in tar.

## Travel Spells Keep Room Rules

`travel_spell_refuses(ch, room)` in `act_move.c` is what earth travel,
gate, the portal spell, astral walk and ENTER ask before carrying a
character anywhere, and what `random_travel_room()` -- recall misfires,
tornadoes, teleport traps -- picks against: another class's guild
rooms, rooms `guild_closed_rooms()` says a guard would turn this
character from, Hyrule's order, and -- before the staff exemption -- a
jail sentence, which allows only the cell. Staff, newbie and private rooms are
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
- Host status (`WEB_ADMIN_HOST_STATUS=1`, set by `toc-restore`) defaults to
  the `toc-*` units in `deploy/windows-vm/`; there is no `POST /api/update`
  or `TOC_UPDATE_REQUEST_PATH` any more (the Pi's updater, 2026-11-11).
- Protected routes use `WEB_ADMIN_TOKEN` in `X-Admin-Token`; an unset token
  disables them with 503.
- **Behind a reverse proxy every request comes from loopback** (2026-11-12,
  Caddy at timesofchaos.com). Proxy mode (`--proxy-headers`,
  `WEB_ADMIN_PROXY_HEADERS`, off by default) is `ForwardedPeerMiddleware`:
  it keeps the TCP peer in the scope (`PEER_SCOPE_KEY`) and, only for a
  peer in `--forwarded-allow-ips` (`127.0.0.1`; `*` refused), sets
  `client` from `X-Forwarded-For` (nearest untrusted hop back) and `scheme`
  from `X-Forwarded-Proto` -- so `request.client`, `websocket.client`, the
  bridge's PROXY line (the game's guard and lockouts) and the same-origin
  checks see the player. uvicorn's own copy is turned off
  (`proxy_headers=False`): it is on by default for loopback and would
  rewrite the client before the peer is kept. **A security decision reads
  `socket_peer()`, never `request.client`.** The local unlock
  (`local_admin_connection_allowed`, HTTP and WebSocket) is refused in
  proxy mode and for any request carrying a `FORWARDING_HEADERS` header,
  proxy mode or not: through a local proxy everybody looks local
  (`tests/test_web_proxy.py`).
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
- **A query filter that cannot be read is a 400 that says why**, checked
  once before the walk, never a bare `except: pass` that drops it:
  `/api/objects`' `stat_filter` is `_parse_stat_filter` (`<stat>><n>`,
  the stat part of an apply location; other operators refused)
  (`tests/test_object_stat_filter.py`).
- **The balance feed is parsed off the event loop**: a route reads it
  through `await balance.load_async(PROGRESS_LOG)` once, and hands that
  result on (see The Play Journal).
- **`/api/changes` is public** (2026-11-12): `webadmin/changes_index.py`
  reads `area/changes.dat` as `src/changes.c` does, and the Changes view
  shows it newest first. Entries headed `staff` come back only to a
  request `verify_token` accepts (`request_is_staff`, which never refuses);
  `tests/test_web_changes.py`.
- **Bump the `?v=` on any file you edit under `webadmin/static/`.** Both pages
  load their assets with a cache-busting query, and editing the file without
  changing the number ships nothing: the browser keeps what it has. This bit
  three separate times in one session -- a rewritten Routes panel nobody could
  see, a stylesheet fix that did not apply, and a script that still expected a
  filter element that had been removed. The last kind is worse than stale, it
  is broken.

## Security Facts

- Game transport is plain Telnet.
- **Passwords are SHA-512 crypt** (`src/password.c`, 2026-11-07). Every
  password check is `password_matches(typed, stored)` and every new hash
  `password_hash(typed, name, out, size)` -- never `crypt()` directly
  (`tests/test_password.py` fails on one). A new password counts every
  byte. An old 13-character DES hash moves at the next login
  (`password_upgrade`, prepared at CON_GET_OLD_PASSWORD while the typed
  password is in hand, applied by `login_password_upgrade` from
  `login_note_success` only to a character still holding that DES hash; a
  fresh login is told and saved at CON_READ_MOTD, a reconnect at once) to
  `$6$.8<salt>$...`: SHA-512 of the first eight bytes, seven bits each, so
  exactly what DES accepted is accepted. Never move or rehash a password
  without the typed one, and never change what an existing hash accepts.
  The SHA-512 is our own, self-tested at boot ("Passwords: SHA-512 crypt
  self-test passed." in toc.log); on failure the game writes DES and moves
  nothing. A test fixture that plants a DES hash computes it through
  libcrypt by ctypes (Python 3.13 has no `crypt`), and must quit and wait
  for the close: a character left link-dead keeps its old password, and
  the next login is checked against that. The tests find crypt() per
  platform (`_libcrypt`, `crypt_link_flags`: libxcrypt and -lcrypt on
  Linux, libSystem on macOS) and compare with the system's SHA-512 only
  where it reads SHA-512 -- required on Linux, left out on macOS.
- **"Connect anyway?" is checked again at the yes** (review, 2026-11-09:
  the holder changed their password while the question waited, and the
  yes took the character). `d->auth_fp` is a fingerprint
  (`credential_fingerprint`, FNV-1a) of the stored hash the password was
  accepted against -- never the password; `connect_anyway_still_allowed`
  compares it with the hash of the character as the game holds it now
  (`connect_anyway_holder`: playing, link-dead, the body a switched
  immortal left, or a login at its MOTD) before any session is closed,
  and on a change asks for the password again and disturbs nobody; then
  deny, ban, wizlock and a lockout of the address, as a login would.
- **A password prompt takes its line whole** (`descriptor_reads_password`
  in `read_from_buffer`): '!' there is part of the password, not command
  history, and the line is never kept in `d->inlast` or counted as a
  repeat. PASSWORD accepted `!Znewpass1` and login then replaced it with
  the line before (review, 2026-11-09). Gameplay '!' is unchanged.
  `tests/test_review_nov09.py`.
- Player files and backups must be treated as exposed credentials if stolen.
- The dashboard should be loopback/private even with a token.
- Do not provide offensive password-cracking automation from repository data.
  Defensive verification must use explicit authorization and sanitized inputs.

See `.github/SECURITY.md` for mitigation and reporting procedures.

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
24.04 instance at `129.159.105.156`, which `timesofchaos.com` resolves
to** (and `www.timesofchaos.com` and the older `toc.jeremybean.com`). It
moved there on 2026-10-01. That address is a **reserved** IP, a
standalone resource that survives a stop or recreate of the instance --
so it outlives the box, and is deleted deliberately only when the whole
project is torn down. (The first few hours used an ephemeral
`129.213.53.66`, now released.) Both earlier hosts are gone --
before Oracle it ran on a Hyper-V VM on the owner's Windows desktop (now
powered off), and before that on a Raspberry Pi that died without
warning on 2026-09-29 -- and the characters were carried forward through
each move. Only Oracle is live: there is no VM to reach at `172.28.90.2`
and no Pi at `toc.local`.

**The website is Caddy on 80 and 443** (owner, 2026-11-12: "host the
admin panel on port 80 and the game on 9000 at timesofchaos.com").
`https://timesofchaos.com` is Caddy (`deploy/windows-vm/Caddyfile`,
installed as `/etc/caddy/Caddyfile`, Let's Encrypt on its own; 80 only
redirects), reverse-proxying everything, WebSockets included, to `toc-web`
on `127.0.0.1:9001`; `www.` and `toc.jeremybean.com` redirect to it. The
game stays plain Telnet on 9000. `deploy/windows-vm/toc-web-proxy` sets it
up once (`ssh toc-oracle 'sudo sh
/srv/toc/build/deploy/windows-vm/toc-web-proxy'`; `--dry-run`,
`--rollback`): Caddy installed and validated and answering first, then the
dashboard moved, with the unit and `web.env` put back if it does not
return. The move is four lines in `/etc/toc/web.env`
(`WEB_ADMIN_LISTEN=127.0.0.1`, `WEB_ADMIN_PROXY_HEADERS=1`,
`WEB_ADMIN_FORWARDED_ALLOW_IPS=127.0.0.1`, `WEB_ADMIN_LOCAL_UNLOCK=0`),
never in `toc-web.service`, whose own defaults are the old public bind:
`toc-deploy` and `toc-restore` install that one committed unit, so a deploy
never moves the dashboard by itself. The DNS records (Namecheap, `@` and
`www`) and the OCI security list's 80/443 ingress are the owner's; the
script opens iptables itself. `wiki/disaster-recovery.md` "The website".

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
`timesofchaos.com` (or `toc.jeremybean.com`) either. It should edit, build both trees, run the
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

**The old deploy appliances are gone** (removed 2026-11-11, with
`zStartup/`, `archive/`, the Pi and Hyper-V wiki pages and the dashboard's
"Update ToC" button). The Pi advanced its checkout with
`git merge --ff-only` (a tracked file the game rewrites would block that
merge). Neither the VM nor
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
  what the sitting came to, then `coin: loot 3p, quests 162p, ...` --
  the session's coin by source -- and (2026-11-05) two more columns:
  `spent on: stash 1550p, heal 5g` (each loss by the character's own
  command, else what `playlog_coin_as` named, else `other`) and
  `exp: kills +12034, flee -10, capped:kills +900` (`playlog_exp`, from
  every way out of `gain_exp` and the two exchanges outside it; a caller
  names the source with `playlog_exp_as` just before -- kills, death,
  flee, recall, drained, skill use, exchange -- and every `gain_exp`
  spends it; a gain refused at level 50 or the remort cap is
  `capped:<source>`). Each tally keeps `PLAY_TALLY_KINDS` labels, the
  last `other`; a new `gain_exp` caller names its source. Trimmed past `PLAY_JOURNAL_MAX` lines to the newest
  `PLAY_JOURNAL_KEEP`, like the channel journal; the whole of `log/`
  reaches git with the state sync and CI ignores it.
- **play.tsv, progress.tsv and hyrule.tsv share one writer**
  (`telemetry_append`, `TELEMETRY_LOG` in merc.h; review, 2026-11-12: a
  row that never reached the disk was counted as written and nobody was
  told). A row is formatted whole and written with one `write()`; a short
  write is cut back off the file (`ftruncate`), so the next row never
  lands on a torn one. Only rows that reached the file are counted
  (`rows`); one that did not is `lost`, and toc.log hears of it at most
  once a minute (`TOC_TELEMETRY_REPORT_SECS` for tests): "Telemetry:
  log/progress.tsv: N rows not written since the last report (why); M rows
  counted in the file", and "writing again" once it recovers -- never the
  row. The trim is one sequential pass in 64K blocks, counting from the
  start only when the count is unknown (the first row after a boot),
  refuses a file that is not regular (`/dev/full` reads zeros for ever),
  never replaces a file holding fewer rows than counted, logs "trimmed
  from N to M rows in X ms", and after a failure waits a minute instead of
  rescanning the file every row. A new telemetry file uses the writer
  (`tests/test_telemetry_writes.py`). Rows a trim cuts are in git: the
  state sync commits `log/` every five minutes and a trim comes every
  `max - keep` rows, so no aggregate file is kept.
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
- **Outcomes, truncation and state** (review, 2026-11-03: a known
  command that failed inside its handler read as an ordinary `cmd`, and
  53 SCORE rows in a day held only the header). `cmd`/`refused` rows
  carry two columns after the reply, so a reader that stops at the
  reply reads them all: the outcome a handler gave with
  `playlog_result(ch, result, reason)` -- `success`, `refusal`,
  `partial`, `failure`, `pending` or `uncertain`, then a short reason
  (`refusal:frozen`, `failure:owner-save`), `-` when none was given --
  and `+` when the reply kept is only the start of what was said.
  `playlog_outcome(ch, op, result, reason, op_id, detail)` adds an
  `outcome` row: the op, result, reason, the recovery ledger's
  operation id (or `-`) and the before/after numbers as key=value words.
  Wired at STASH TAKE, SPLIT, REPAIR, quest completion, the craft audit,
  PRESTORE's gives and ACCEPT (quest completion's detail names the kind
  -- ordinary, rush, emergency, daily -- the points `offered` to the
  gamble, the coin, one `kill` at the questor's level, the streak, level
  and target vnum, so a quest's pay reads in kills); a frozen-trade refusal sets
  `refusal:frozen` or `refusal:other-frozen`. SCORE writes a `state` row
  of the sheet's numbers (`playlog_state`). Never put private words,
  addresses or a hidden room in a detail.
- **Wizinvis staff leave no trace in the journal** (owner, 2026-11-09).
  `play_hidden()` -- a player with `PLR_WIZINVIS` -- makes
  `journal_write` and `progress_write` write nothing: no command, state,
  outcome, craft, item, death, session, report or anomaly row and no
  progress line, named or anonymous. Where a row is about something else
  the name and room go too: a BUG line's context says "during a
  command", and a stall row's slowest command is not theirs. **Their
  commands are not kept at all** for later (review, 2026-11-09): not in
  the crash ring, nor in the recent commands a BUG/TYPO/IDEA report
  carries once they are visible again -- a blank name left the words,
  which can name somebody or a room. A new journal writer passes the actor to
  `journal_write` and never `NULL` for a hidden one. The watch log in
  `toc.log` keeps its own rules (`tests/test_playlog.py`).

- **Deep bug rows** (2026-11-05: what players report and nothing wrote
  down). `stall`: a pulse past `STALL_MS` (250, one pulse) -- the total,
  the slowest stretch (`input`, one of update_handler's phases, `output`)
  and the slowest command, players online, and how many stalls the
  `STALL_QUIET` minute left out; update_handler times its phases with
  `playlog_phase_enter()`, never by setting `playlog_phase`, and the game
  loop calls `playlog_pulse_begin`/`_end` around the pulse. `death`: a
  player's death from `raw_kill_internal` -- the killer (`mob <vnum>
  <short>`, `player`, `self`, `none`), then key=value words: the last
  blow (`playlog_blow`, recorded where hit points come off in `damage()`)
  with the hit points before it and its age, the biggest blow of the last
  minute, max hp, foes on them, wimpy, a death-trap room, sanctuary,
  linkdead. `item`: an object a player held, at any depth, leaving the
  game through `extract_obj` (`playlog_obj_gone`, asked before it is
  taken from its holder) -- vnum, short description, type, level, worn,
  timer, condition, what was inside, and why: the holder's command,
  another's (`<cmd> (another's)`) or the update phase. Quitting frees a
  player's things through `extract_obj_player`, which never asks, so a
  row is a real loss; food, potions, pills, scrolls, coin, herbs,
  components and cakes are left out. `outcome` `quest-failed`
  (`timeout` or `abandoned`): the kind, target, how many of it the world
  holds (`alive=0` is a quest nobody could finish), its area and whether
  the questor was in it, and the streak. `tests/test_playlog_deep.py`.

- **`log/progress.tsv` is the balance feed** (2026-10-22; rebuilt
  2026-11-10, owner: "log everything in a way that'll allow you to balance
  the game learning from players who play"). Numbers and vnums only: the
  character's **serial, never a name** (the file Id before 2026-11-12,
  below 65536 and shared by some characters -- such old rows can merge
  two; see Characters Are Known By Serial), the **area file, never a room**,
  nothing typed or said; immortals by level (`IS_IMMORTAL`, never trust:
  owner, 2026-11-12, a mortal trusted with staff commands is a player and is
  counted), wizinvis
  players, the dealer and the goblin write nothing. The common columns
  are epoch, kind, serial, level, class, remorts, hp%, mana%, foe vnum and
  level, area file; the layouts are in `progress_write_raw`'s comment in
  `src/playlog.c` and `webadmin/balance.py`'s docstring. Kinds:
  `engage` (a mobile entering a fight with a player, from `set_fighting`:
  the encounter id `<boot>-<n>`, both sides' hit points and mana, the
  group and pets in the room, a coarse gear tier, buffs -- **and what
  CONSIDER would have said, unasked** (`consider_predict` in
  `act_info.c`, the same function CONSIDER speaks from; owner: every
  fight held to it, whether or not the player asked)); `slain` (**one
  per mobile death** that credits anybody, from `group_gain` before the
  rewards -- the review of c7101e78 found a group kill counted once per
  member -- with the encounter's ms, blow or instant, player or pet,
  players and pets, and the mobile's own ledger, kept on the mobile in
  `damage()` so a melee of several foes is never one total: hit points
  that came off it, of them by pets and by spells or skills, what it took
  off players, the rounds it fought, players' melee swings and those that
  took hit points); `reward` (one per player paid: the old kill row's
  columns, then the kill id, foes on them at the kill -- the player's own
  ledger is the whole melee's when that is more than one -- gear tier and
  hp/mana at the fight's start; a member who never struck writes a zero
  ledger); `flee`/`death` (how much of the foe was left, its max hp, the
  fight's cost, the encounter id); `drop` (what `make_corpse` put in the
  corpse, `vnum:source` -- carried, guardian, ganon, enemy, holiday,
  event -- through `corpse_tag_source`); `loot` (anything a player takes
  out of a mobile's corpse, at any depth, from `get_obj`, joined by the
  corpse's `kill_seq`: coin gross, before an autosplit, which is a
  transfer); `consider` (a typed CONSIDER's prediction). Rows before
  2026-11-10 are legacy `kill` rows, one per member: readers count each as
  1/members of a kill and say so. `webadmin/balance.py` joins them into
  per-kill records and per-mobile figures (kill-time quantiles, xp per
  combat minute offered and accepted, xp an hour with the time between
  kills -- `cycles()`: the seconds since a character's previous second
  with a kill, shared among that second's kills, since the journal stamps
  whole seconds and two kills a second read as one before (review,
  2026-11-12) -- coin and gear generated against looted, hit point cost from the
  mobile's ledger, flee and death rate, hit rate, spell share, farming),
  sliced by player level band, solo/group, class and gear tier, and
  compared within five-level bands: generous, poor, risky, rich, farmed
  and **gaps** (fewer than three comparable, reachable choices).
  `tools/balance_report.py` prints it with manual proposals (nothing is
  edited); `tools/consider_audit.py` holds CONSIDER to the fights;
  `/api/leveling`, the website's leveling guide and the Oracle use the
  measured figures from players within five levels when `balance.near`
  trusts them (`MIN_KILLS` by `MIN_CHARACTERS`), and the model, calibrated
  by them, as a labelled fallback; the guide leaves out Hyrule's
  guardians and areas no route reaches and names a Hyrule dungeon's
  prerequisites. The Gear Finder carries `seen_drops`. Trimmed past
  `PROGRESS_MAX` to `PROGRESS_KEEP`. `tests/test_progress_log.py`,
  `tests/test_balance_log.py`.
  **The dashboard reads the feed as it grows** (review, 2026-11-12: a
  full reparse after every row, ~0.35 s on a 40,000-row feed, on the event
  loop). `balance.load` keeps one `_Engine` per file: an unchanged file
  is the last answer; growth is read from where the last read stopped and
  only the mobiles the new rows touch are figured again; another inode
  (the trim's rename), a shorter file, a first or last 64 bytes not as
  read, or a row rewriting a kill or encounter already read starts again
  from the beginning. An unterminated last line is carried, never read.
  The answer must equal `compare(summarize(text))` for the same complete
  lines -- same functions, same order -- and `tests/test_balance_cache.py`
  holds it to that and to the pre-change reader's digests. One lock: calls
  together share a parse. Async routes call `await
  balance.load_async(...)` and pass the result to `near`/`seen_drops`,
  never a path, so no parse runs on the event loop. **A band's gap counts
  reachable equal choices only** (`balance.band_choices`), in
  `proposals()` and in the report's text and `--json` alike; the JSON
  reads the world unless `--no-names` (`tests/test_balance_report_gaps.py`).

- **More journal rows** (2026-11-10, owner: log everything so a lump of
  coin can be traced in minutes): `coin` (every purse change: amount,
  source, command, from where, wealth after; bank interest), `got` (every
  object reaching a player: vnum, name, type, level, cost, command, from
  where -- `playlog_from` names the giver, the shop or the container, and
  a wizinvis giver is "someone"), `level`, `area` (with the time spent in
  the last), `achieved`, `skill` and `quest` rows in `log/play.tsv`;
  `tools/log_report.py`'s activity section reads them
  (`tests/test_playlog_activity.py`).

- **`log/hyrule.tsv`** (`src/hyrulelog.c`, owner 2026-11-10: Hyrule
  logged heavily for balance and trends). Columns: epoch, kind, name,
  level, remorts, class, room, zone (`over`, `L1`-`L9`, `out`), then
  key=value words -- add a field at the end, never rename one. Kinds:
  `enter`/`leave` (from `char_to_room`, `hylog_moved`; a leave carries the
  seconds spent; a session's end closes the zone), `gate` (a refusal said
  aloud, not one met mid-flight), `seal` (`trigger_puzzle_manipulation`),
  `got` (any Hyrule object reaching a playing mortal, from `obj_to_char`,
  with the command that brought it), `claim` (`secret_set`), `engage` (a
  guardian entering a fight, from `set_fighting`, with every mortal in
  the room: levels, classes, hit points, buffs), `guardian-down`, `flee`
  and `death` (the foe's health left -- the number that sizes a
  guardian), `cleared`. Mortals only, by level (a trusted mortal is
  logged; owner, 2026-11-12): immortals and wizinvis are never
  written. A field holding a name is `obj_name`/`foe_name`, never `name`,
  and no field is `level`: the reader keys words beside the columns.
  `how` comes from `playlog_how()`. `tests/test_hyrule_log.py`; the
  report's `== hyrule` section reads it.

`tools/log_report.py` prints the slowest commands, what the game said no
with (grouped by command and answer -- the cheapest way to find a command
that confuses players), **help that did not help** (HELP X, then X refused
within ten minutes -- it found HELP HEROQUEST teaching commands that did
not exist), repeats outside a fight, events collapsed to one line a kind
with a count (the goblin's drift was 275 lines in two days), quests
assigned by area and kind, anomalies with the buff that wore off just
before, BUG lines with context, reports with their commands, sessions
with their coin by source and crashes. The morning routine runs it.

## The Diary

`src/diary.c` (owner, 2026-11-12: "a diary feature that uses the player
logging system to allow players to see their daily progress and what they
did each day"). DIARY is today, DIARY YESTERDAY, DIARY <yyyy-mm-dd>, DIARY
LIST (a line a day, newest first); staff (`is_staff`, by level) add a
name, `DIARY <player> [list|yesterday|date]`, refused by rank as
`rank_protects` asks (from the file's `Levl`/`Tru`/`Creator` when the
player is not in the game). `tests/test_diary.py`.

- **The journal's hooks feed it.** `playlog_coin` (gained by source,
  spent by what it went on), `playlog_bank` (interest), `playlog_got`,
  `playlog_level`, `playlog_moved` (time in each area), `playlog_skill`
  and `playlog_exp` (never a capped gain) call `diary_*`; beside them
  `group_gain` calls `diary_kill` for every player a kill pays (a boss
  row of the achievements, a Hyrule guardian, a holiday boss, the goblin
  or the black dragon is named), `raw_kill_internal` `diary_death`,
  `achievement_unlock` `diary_achieved`, the three close calls
  `diary_close_call`, and quest completion `diary_quest_done` (a daily's
  points at once; an ordinary quest's when AQUEST GAMBLE settles them,
  `diary_quest_points`). A new journal writer for something a player would
  call progress feeds the diary too. It never reads the journal.
- **Its own file, never the player file.** Today's page is
  `pcdata->diary` (heap, freed by `free_char`), made on a playing
  character's first event of a sitting (`diary_login` from the nanny,
  `diary_tick` from `char_update`) and loaded from the file when they
  played earlier that day; `save_char_obj` writes it (`diary_save`) when it
  changed, so it reaches the disk with every save and at QUIT. The file is
  `#DIARY 1`, then per day `Day yyyy-mm-dd`, `Played`, `Level from to
  gained`, `Exp`, `Kills`, `Deaths`, `Close`, `Quests n pts`, `Dailies n
  pts`, `List <list> a b <name>` rows and `More <list> n`, ending `End`, and
  `#END`; written to `<Name>.tmp` and committed by `temp_file_commit`,
  keeping the newest `DIARY_DAYS` (30). The reader takes whole records only
  (a torn last record is dropped, an over-long line skipped whole, numbers
  through `parse_long`). `player/diary/` is synced with `player/` and
  excluded from deploys with it; its name is lowercase and a directory, so
  nothing that lists characters reads it.
- **A day is the holiday calendar's** (`holiday_date`: the host's
  localtime, or `TOC_DATE`/`TOC_DATE_FILE` in tests). The page turns the
  moment any hook or tick sees the date change: the old day is written and
  the new one begun, while playing.
- **Mortals only, and nobody else in it.** `diary_keeps`: not an immortal
  by level (a trusted mortal keeps one; owner, 2026-11-12), never wizinvis, file read whole -- so a wizinvis immortal leaves
  no page. A page names no giver, no player killer ("another player", or
  "unknown causes" for an unseen immortal), no room (an area, by
  `quest_area_name`, is the finest place: the dealer and the goblin are
  never placed), nothing said or typed.
- **Moving one's own things is not gaining them**: `get_obj` from a
  container the character carries or their own corpse, and STASH's own
  withdrawals, run inside `diary_own_move(true)`. Food, potions, pills,
  scrolls, coin, herbs, components, cakes, corpses, trash and Hyrule's
  bombs are never listed.
- **The name moves with the character**: RENAME moves the file
  (`diary_rename`), DELETE sets it aside as `<Name>.deleted-<epoch>`
  (`diary_retire`) and a new character finding an old diary under its name
  sets it aside as `<Name>.old-<epoch>` (`diary_login`): nothing is read as
  somebody else's, and nothing is destroyed. The archive leaves it where it
  is. In the command table DIARY sits after DIAGNOSTICS, so staff's DIA is
  unchanged; DI is still DIRT.

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

## Starving And Parched

Owner, 2026-11-12: hunger and thirst "should damage you somewhat as they
get extreme, and maybe prevent you from sleeping". `hunger_thirst_tick` in
`update.c`, after the tick lowers the conditions: each tick at 0 takes
`HUNGER_HURT_FIRST` (2) percent of the maximum, a point more a tick in a
row to `HUNGER_HURT_MAX` (8); thirst `THIRST_HURT_FIRST` (3) to
`THIRST_HURT_MAX` (10); both add. The run is `pcdata->starving_ticks` and
`parched_ticks`, memory only, reset at the first tick the condition is not
0. Hit points come off directly through `pool_scale`, never `damage()` (no
kill, drain or fight), and never below one: hunger kills
nobody, a jailed prisoner included. One line a tick says why, in words
that grow (the tick's own "You are hungry." is silenced for that
character: `condition_change(..., speak)`). Who: `hunger_thirst_applies`
-- a mortal player under `LEVEL_HERO` with no remort, not staff by level;
`hunger_thirst_hurts_here` also spares the link-dead, the idle in the void
(`was_in_room`), Limbo and the Oracle's sanctum, whose ticks neither count
nor reset the run. SLEEP asks `hunger_refuses_sleep` before anything
changes; the tick wakes a sleeper to resting, but not one under
`AFF_SLEEP` -- the SLEEP spell still works on the starving (magic
overrides the body). `tests/test_hunger_thirst.py`.

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

**Hermie appears when staff place her, and after a restart that put
mortals off** (owner, 2026-10-27; 2026-11-10: "a play reward for players
who get kicked off due to a restart"). HERMIE is the staff command
(SPELLUP still works and is hidden from WIZHELP). `spellup_boot_update`
(every mobile pulse) writes `log/online.txt` -- the time, how many
mortals are playing, when a mortal last played and how many did then --
when the count changes and once a minute, never once the game is going
down; `spellup_boot_check` reads it at boot, and a count above zero
written within half an hour, **or a mortal who played within
`HERMIE_RECENT` (ten minutes) of the boot**, opens a four-hour window
(owner, 2026-11-11: a level 34 quit at the deploy's warning, 34 seconds
before the boot, and the file read 0)
(`TOC_HERMIE_BOOT_SECONDS` shortens it for tests) in which she stands in
the Oak Tree Square while any mortal plays and steps away while none
does. A restart with only staff or nobody on brings none; a crash with
players on counts. SPELLPURGE ends the window; a Hermie staff placed
there is never removed by it. Logged and on WIZINFO
(`tests/test_hermie_restart.py`). A test or tool that needs her has a
staff fixture type HERMIE (`at 4208 hermie` puts her at the altar), as
`tests/test_journal_frictions_oct22.py` and `tools/class_bench.py` do
with SPELLUP. Test worlds start with no `log/online.txt`, so no Hermie.

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
17 and 18 and a LEVEL grant through one level. **GRANTPSI saves what it
changed and says how it landed** (review, 2026-10-30: a failed offline
save was reported as saved and the copy freed): a failed save of an
offline character keeps nothing and says so, an online grant stays in
effect for the next save to write, and an unconfirmed save is reported,
never undone (`grantpsi_save`, fault point `grantpsi-save`).

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

## A Landed Blow's Steps Are Shared With CONSIDER

Review, 2026-11-12. After the defences (ducking, parry, dodge, shield
block), `damage()` takes a blow through `blow_before_armor` in `fight.c`
-- the wards (sanctuary, protection against an evil attacker, divine
protection; a mental blow `psionic_mental_reduce` instead), a fire or
frost shield's own element (half again), `alignment_damage_mod`, immunity
-- then the armour's cut, `number_range( blow_armor_floor(), dam )`, then
a Hyrule ring or shield on a player; a shield then burns the striker back
through `shield_burn`. The arithmetic is `combat_rules.h`'s
(`blow_ward_cut`, `blow_element_shield`, `blow_immunity_cut`,
`blow_armor_floor`, `blow_armor_mean`, `blow_reflection`), held by
`tests/test_combat_rules.c` to the inline code it replaced. CONSIDER runs
the same steps through `blow_landed_expected`, averaging the armour roll,
so it cannot drift from the fight: it used to cut the armour first and
then halve for sanctuary, and armour is a fixed cut, so a blow of 100 on
a sanctuaried mobile of armour -20 read 40 where the fight averages 30.
A new step in a landed blow goes into those helpers, never inline in
`damage()` (`tests/test_consider_effects.py` plays CONSIDER against the
arithmetic). The wards ran before the defences until then; nothing there
reads the blow.

## damage() Says Whether A Blow Landed

**Never branch on `damage()`'s result.** It is true for nearly every blow
that connects and for every blow a character deals themselves -- it is
not "the victim died". Reading it that way at more than twenty sites made
every multi-hit spell, trap and flood stop at its first landed blow and
skipped whatever followed a hit: the blindness, the stun, the lag, the
healing, the ingredients. Note the room before the blow and ask
`gone_after_blow(victim, room)` after it -- a killed mobile is extracted
(and freed only at the top of the next pass, so reading one in the same
pass is safe; see "Memory Is The System Allocator's") and a killed player
is in the death room. `tests/test_damage_result.py` fails on any `if (damage(`.

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

**A level is rolled against gear and EMPOWER, never other spells**
(owner, 2026-11-11: "buffs shouldn't affect leveling, but gear should",
then "i do want empower to boost XP and leveling that was the design").
`advance_level_body` reads `get_level_stat` in `handler.c` -- the
permanent stat, what worn gear lends it (prototype and own affects as
`equip_char` applies them) and EMPOWER's own stat affects (`gsn_empower`,
staff's or crafted), under `get_curr_stat`'s ceiling -- never
`get_curr_stat`, which counts every spell and potion
(`tests/test_level_stats.py`). Levelling in gear, empowered, is meant to
pay. The mana step below is left as it is, since
fixing it is a cut. And every mana range there is
`number_range(int_app[INT].mana_gain, (INT+WIS)/k)` with the lower end
above the upper (40 against 12 at INT 18), so `number_range` returns the
lower end and mana a level is a step function of INT alone, before the
class and guild factors (x1 pure casters, x3/4 hybrids and monks, x1/2
warrior and thief in their own guilds). Swapping the endpoints would
cut every future level's mana by about a third, against the owner's rule
of raising classes rather than cutting them. Leave both, and never
change `number_range` to touch either.

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
- `obj_update` never runs their timers: STASH refuses anything with a
  timer, and an object in no room and on nobody at any depth
  (`obj_held_nowhere`) keeps its timer anyway -- a file can bring a timed
  one in, and one that expired there was extracted while the stash still
  held it, and a bottle "shattered" with nobody to open it (review,
  2026-11-12; `tests/test_untested_paths_nov12.py`).
- They weigh nothing and count against nothing the character carries.

They are written to the player file under a `#STASH` marker **after**
everything else, including the pet. The marker puts `fread_obj` into
stash mode for every `#O` that follows, so nothing of the character's
own may ever be written after it. `stash_max` saves separately as
`StashMax` under **case 'S'**, and forgetting it means a bought upgrade
evaporates at the next login -- worse than not selling it at all.

Every deposit and withdrawal calls `save_char_obj()` immediately. A
stash written only at quit is a duplication bug waiting for a crash.

**STASH TAKE from a linked partner is a receipted transfer**
(`stash_take_commit`, review 2026-11-03: two unchecked saves copied or
lost the object). A pending `transfer` record in the recovery ledger
(`stash:<seq>`, naming the vnum, the object and both characters) or
nothing moves; the owner is saved without it first -- FAILED puts it back
where it was -- then the taker with it -- FAILED gives it back to the
owner and saves them again; if that fails too it stays in whoever's
memory can still save it (the taker's when the owner is an offline copy)
and the receipt says `retry`. UNCERTAIN is never undone. The order means
a crash between the saves leaves the object in neither file, never in
both, with the pending receipt naming it for a PRESTORE STASH from the
owner's snapshot; that window is not closed automatically, because
objects carry no identity a boot could match.

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

REPORTS itself is typed by trust, like any command. The login banner and
the mail addressed to `immortal` are staff's, by level: `report_login_notice`
and `is_note_to()` ask `is_staff()`, so a mortal given trust may read
REPORTS but is not told of new ones and receives no staff mail (owner,
2026-11-12, reversing the staff-trust sweep of 2026-10-05; see Permission
Helpers).

Other deploy facts:

- A deploy never takes player state from git. `toc-deploy` excludes
  `player/`, `gods/`, `heroes/`, the logs and the area runtime files and
  ships only code; **`toc-restore` is the only thing that lays live state
  down from git**, and only onto a fresh box in a disaster.
- `MUD_HOST` is where the web service dials (loopback, 127.0.0.1).
  `MUD_PUBLIC_HOST` is what the dashboard shows players; on Oracle it is
  set to `timesofchaos.com` in `/etc/toc/web.env` (by `toc-web-proxy`;
  also the default).
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
  those tables. A chest's P reset counts when its key can be had.
- **Or a death makes it** (review, 2026-11-10: the Aquamentus coat and helm,
  30650/30651, were missing from a level 25 warrior's list). No reset shows
  what is made at a death, so `webadmin/gear_drops.py` mirrors the C that
  makes it, each piece with its source, where, the chance a kill, what the
  way there needs and the holiday if it has one (`drop_sources` on a Gear
  Finder entry; the Oracle's gear and "where does X drop" lines say the
  same): a Hyrule guardian's drop table (three of its 10 or 11 pieces a
  kill, `hyrule_boss_drops`), Ganon's relic (one of three), the two
  boomerangs a cleared room lays (`hyrule_clear_rewards`), the holiday
  bosses' drops (`event_boss_drops`) and Midsummer's firework
  (`holiday_corpse_drop`) -- **a holiday's items only while it is on** --
  and the black market's rarities, which a treasure goblin's sack and the
  black dragon's hoard also roll (`black_market_rarity`). Their other gear,
  `black_market_gear_for_level`, is a reset item already and is not added
  twice. `tests/test_gear_drop_sources.py` holds every mirrored number to
  the C, merc.h and the generator: change a drop table there and change it
  here. COMPARE UPGRADES lists the guardians' tables and Ganon's relics too
  (`gear_find_guardian_drops`, "dropped by ... about 3 kills in 11"), but
  not the boomerangs, the holiday items or the rarities, and names no
  prerequisite.
- **COMPARE UPGRADES never calls `create_object`.** It builds a stack
  `OBJ_DATA` from the prototype, because a real object joins `object_list`
  and raises its prototype's count, all for a figure.

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

**An emergency lost to the clock keeps the streak** (owner, 2026-11-13: a
streak of 45 went to an emergency in the sewers, reached from Dresden with
21 seconds left). Its five minutes take no account of the distance, so the
timeout branch of `quest_update` spares `queststreak` when
`questemergency` is set; an ordinary or rush timeout, ABORT and quitting
still end it (`tests/test_aquest_system.py`).

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

**A random room or mobile prototype is drawn, never guessed** (review,
2026-11-12). `random_room_index()` and `random_mob_index()` in `db.c` draw
from dense lists of every world room and every mobile prototype, kept by
`room_index_link`/`mob_index_link` -- the only places a prototype enters
its hash -- and `room_index_forget` from `extract_room`. TELEPORT and
`get_random_room` (through `random_room_candidate`, which still takes
`TOC_RANDOM_ROOM` first), EXPLODE and a bounced object (`do_bounce`) all
draw from them, keeping each caller's own tests; a random portal (value[0]
1, made in `create_object` and moved in `obj_update`) picks with
`random_room_where(ok)`, a reservoir over the rooms its predicate accepts.
They guessed `number_range(0, top_vnum_room)` and vnums are sparse, so one
room at 1,000,000 made two hundred guesses all miss about one time in
five: TELEPORT fizzled, a misfire fell back to the Temple and a portal
opened on nothing (or on the last room it had rejected) with eligible
rooms to spare. Every room is as likely as before; a pocket room (rope
trick, haven) is not a world room and is never drawn, and
`random_scatter_room` walks the same list. A new room or mobile prototype made after boot goes
through those link functions (`tests/test_sparse_room_draw.py`).

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

## Jail Sentences

`src/jail.c` (owner, 2026-11-12: a mortal must not escape an active
sentence; death, farslay, suicide, travel, items, remort, disconnecting,
relogging and rebooting do not release them -- only staff release or the
expiry of a timer staff set). `wiki/operator-guide.md` has the command.

- **The sentence confines, never the room.** Every travel check used to
  ask `ROOM_JAIL`, so a prisoner in a cell given an exit or stripped of
  its flags walked out, and `raw_kill_internal` skipped the whole death
  (no `extract_char`, no deaths log) only while the room carried the
  flag. Now `char_to_room` asks `jail_hold_room(ch, room)` at every
  placement: a prisoner (`is_jailed`: a player with `PLR_JAILED`, staff
  included) put anywhere but `ROOM_VNUM_JAIL` is put in the cell
  instead, logged `JAIL: <name> kept in the cell`. That covers the death
  room (every death -- combat, SLAY, FARSLAY, the Farslay rite and its
  backfire, death rays, poison, traps -- is a whole death, and lands in
  the cell), recall, portals, spells, login placement and anything added
  later. A missing cell holds nobody and says so with `bug`.
- **Refuse before starting, so the boundary undoes nothing.**
  `jail_refuses(ch)` -- "You are serving a jail sentence..." -- is asked
  first by `move_char` (riding included), `recall_travel` (the prayer,
  the ring, the link-dead rescue), ENTER, the manipulation objects,
  PROJECT, SWITCH, ROPE TRICK, HAVEN, PRAY (before any audience); REMORT
  and DELETE (both steps: a confirmation asked for before the sentence
  dies with it) refuse a prisoner too, and `travel_spell_refuses`,
  teleport, word of recall, summon, ACCEPT and RAISE DEAD ask
  `is_jailed`; so does `travel_target` of the one sought, so GATE, the
  portal spell, earth travel and astral walk never reach a prisoner (a
  gate took its caster into a cell that had a door and no flags,
  2026-11-12). TRANSFER, ITRANS and DRAG refuse a prisoner unless the
  destination is the cell (`jail_refuses_staff_move`). There is no
  override that keeps the sentence and moves the prisoner: JAIL RELEASE,
  logged, is the deliberate act. A new way of moving a character asks
  `jail_refuses` before it starts anything the cell would undo.
- **Representation** (pcdata, **case 'J'**): `Jw_Timer` is the absolute
  release time, `JAIL_INDEFINITE` (-1) for none, 0 when free -- read with
  `fread_long` (it was `fread_number`, so a deadline past 2038 refused the
  whole character); `JailInfo <since> <added> <by>` is written only while
  jailed: `JAIL_ADDED_NOCHANNELS`/`NOTITLE` say which restriction this
  sentence turned on (it turns on only what was off), and the release
  takes off only those. NOCHANNELS, NOTITLE or MUTE toggled by staff
  during a sentence clear the matching bit (`jail_restriction_touched`):
  from then on it is theirs. Jail never touches the title, WARNED or
  EXCON (it overwrote the title with " . (JAILED)", cleared both flags,
  and release wrote "the Jailbird." and cleared every channel ban).
- **Migration**: a file with `PLR_JAILED` and no `JailInfo` is
  `JAIL_LEGACY` (`jail_load_fixup`, end of `load_char_obj`): nothing
  records what that sentence imposed, so its release lifts neither
  restriction -- staff do it by hand -- and a `Jw_Timer 0`, which the old
  code wrote for a sentence with no deadline, is indefinite, never one
  that expired in 1970. A legacy " . (JAILED)" title goes back to the
  class title at release.
- **Saved at once, reported as it landed.** JAIL and RELEASE change
  memory, save (`jail_write`; fault point `jail-write-<Name>` -- no
  "save" in it), and on `DURABLE_FAILED` put everything back and say
  nothing changed; on `DURABLE_UNCERTAIN` keep the change and say it is
  not confirmed. Only then does an online prisoner move (forced back from
  a switch or projection, out of a fight and a walk, off a mount). A file
  saved free but in room 3 logs in at the Temple (`jail_login_place`).
  **The pet beside them moves with them both ways** (review, 2026-11-12):
  `save_char_obj` writes a pet only from its owner's room, so one left in
  the cell at a release was dropped by the next save. `jail_take_in` leads
  it in and `jail_release_move` (staff release and expiry alike) leads it
  out after the release's save -- which already holds it, both being in
  the cell, and a crash before the move logs them in at the Temple with
  the pet beside them. A rider remounted in the cell goes out mounted, the
  mount with them, as TRANSFER moves one; a rider whose mount is not
  there is dismounted (`release_mount`). A saddled mount is saved with its
  saddle (see "A Saddled Mount Is Saved"), so one led out of the cell
  survives the quit too. SHIFT asks `jail_refuses` of
  the caster and `is_jailed` of the target before any cost: its room
  tests read the cell's flags (`tests/test_jail_companions.py`). Its
  destination test is the target's: `travel_spell_refuses( victim,
  ch->in_room )`, and a mobile is kept out of a `ROOM_NO_MOB` caster room
  (review, 2026-11-12: it asked `travel_spell_refuses( caster, target's
  room )`, astral walk's question, and pulled anybody into a guild hall
  whose guard turns them away; `tests/test_shift_destination.py`).
- **Expiry** is elapsed wall-clock time, never ticks: `jail_update` once
  a second (`update_handler`, beside the memory sweep) releases a timed
  prisoner past the deadline, link-dead too, with nothing typed;
  `jail_login`, after `corpse_registry_login` and before the first LOOK,
  releases one whose term ran out while away. A failed release save
  leaves them jailed and retries in `JAIL_RETRY_SECS` (10).
- **The command**: `jail <player> status | <30m|2h|7d|days> | indefinite
  | release | 0`, online or offline through `player_in_game` and
  `offline_player_load` (a login in progress refused), `rank_protects`,
  a duration from now replacing the old term, at most `JAIL_MAX_SECONDS`
  (30 days); anything malformed, zero, negative, too long or followed by
  more words changes nobody. Logged `JAIL: ...` and WIZINFO at
  `staff_notice_level_pair`. `tests/test_jail_confinement.py` (the stock
  cell and a cell given an exit and no flags), `tests/test_jail_sentence.py`,
  `tests/test_jail_paths.py` (a mount, SUMMON, GATE and portal both ways,
  RAISE DEAD, a death trap's door, TRANSFER and saved room, a poison death
  in the cell). Hunger and thirst hurt but never kill (see "Starving And
  Parched"), so nobody starves in a cell or anywhere; that test holds a
  starving, parched prisoner at one hit point through a tick to show it.
  A mount jailed under its rider is led in unridden and stays their pet;
  RIDE takes back a mount that is already the rider's own (its master is
  them), so they may sit it in the cell and go nowhere.

## A Saddled Mount Is Saved

2026-11-12. RIDE puts the rider's saddle on the mount (`WEAR_BODY`) and
makes it their pet, and `save_char_obj` wrote no pet that carried
anything, so a ridden mount and its saddle were destroyed at every quit.
`pet_saveable(pet, &saddle)` in `save.c` is the one test: a pet carrying
nothing, or only its own saddle, worn and holding nothing. `fwrite_pet`
writes the saddle as `Saddle <vnum> <level>` in the `#PET` record (case
'S' of `fread_pet`); `fread_pet_saddle` makes it again at the record's
`End` -- never part way, so a refused record leaves none -- and puts it on
(a vnum that is no saddle now is left out with a bug line, one the pet's
alignment refuses goes to the owner's pack). A second `Saddle` refuses the
character through the loader's trap ("has a pet record with two saddles"),
as a second pet does; a malformed number refuses it as any does. Only the
vnum and level are kept: the saddle comes back as its prototype makes it.
**Nobody comes back riding**: `load_char_obj` clears `mounted` when no
ridden pet came with the file (a loaded pet never is), before `jail_login`
or anything at login asks, and the nanny clears it again. The rider enters
on foot, the mount saddled beside them; RIDE lets anybody mount their own
pet and needs no saddle in the pack when the mount wears one. A pet's carry
limit is 0 (`can_carry_n`), so only RIDE ever puts anything on one, and a
pet carrying anything else is still not written. DISMOUNT lets the mount
go (not the pet any more, not saved), as it always did.
`tests/test_mount_persistence.py`, `tests/test_jail_companions.py`.

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
exitless rooms, and Hyrule, the yard, `seasonal.are` and `quest1.are`.

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
named his room within minutes). Arrivals (stock size, how long),
every stock in full (`bm_log_stock`, from `black_market_restock`: each
item's name, vnum, level and price; owner, 2026-11-02: always log what he
carries) and purchases (buyer, item, vnum, price) go to the log without a
room;
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
The rarities below come at any level. No-drop, no-remove, rot-death and
quest-token items are never sold. **He
carries `BM_STOCK_MAX` (five) things at most**: a holiday boss's drop at
40%, a training cake at 30% (the two holiday cakes) and a lucky clover
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

## Exploration Maps And The Fog

`src/maps.c` (owner, 2026-11-12: the Mudlet map shows only rooms a character
has been to, unless they hold the area's map; Dresden and the starting areas
always). The game decides and the package only draws:

- **Known** is `map_room_known`: an immortal by level (`map_sees_all`,
  never trust: owner, 2026-11-12, a mortal trusted to build explores like
  anyone) knows everything; an area in
  `map_always_known_files` (dresden, school, limbo, dummy -- the one table);
  a room in the achievements' `rooms` set (walked into); or the room's
  **region** held. A region is an area (`achievement_area_id`), except that
  each Hyrule dungeon (its `hyrule_dungeon_gate` range) is its own
  (`map_region_id`, a hash of `hyrule.are#dungeon-N`), so an area map of
  Hyrule shows the overworld. A region is held when it is in the new set
  `map-areas` (`AchSet`, case 'A'), or, for a dungeon, when its NES map's bit
  is in `AchMaps` (`achievement_hyrule_maps`, set on getting the map since
  October) -- so dungeon maps already found count, and nothing new is saved
  for them.
- **GMCP `Map.Known`** (`gmcp_send_map_known`, from the prompt block in
  `comm.c` beside `gmcp_send_room`): the known rooms as vnum runs, in parts
  of at most `MAP_KNOWN_PART_BYTES`, `"all": true` for an immortal by level. It is sent when
  `d->gmcp_map_known_sent` is false -- a new connection or GMCP (reset in
  `gmcp_reset_snapshots`) and `map_known_changed(ch)`, which every map
  learned calls (`map_grant_region`, and `achievement_note_object_vnum` when
  a Hyrule map bit is new). A room walked into needs no message: the package
  reads `Room.Info`. A new way to learn a map goes through
  `map_grant_region`.
- **The package's fog** (1.5.12, corrected in 1.5.13): unknown rooms are
  deleted from the profile's map and kept, with coordinates, area, name,
  terrain, mark, doors and both ends of every exit (with the door on the
  exit into it), in `toc-fog.lua` (`getMudletHomeDir()`, `table.save`/
  `table.load`); `tocMudlet.unfog` puts one back and relinks it.
  `Room.Info`, `Hyrule.MapRoom` and a new `Map.Known` unfog, and a smaller
  `Map.Known` (GRANTMAP ... REVOKE) fogs again; a new map in the profile
  (`tocgui atlas confirm` or `force` after its own `loadMap`, or `sysMapDownloadEvent`, which
  Mudlet raises only after its own map download -- the GMCP `Client.Map`
  one -- has parsed) starts the fog afresh. The atlas itself still holds
  every room it did: the fog is the client's, never the generator's.
  **Mudlet's rules, read from its source** (`TLuaInterpreterMapper.cpp`,
  `TRoom.cpp`, `TRoomDB.cpp`, `TMap.cpp`, 2026-11-12) and played by the
  fake mapper in `tests/mudlet_fog_spec.lua`: `getRoomExits` names exits
  "north" ... "down"; `setExit`/`setExitStub` take short or long names;
  **doors are keyed "n" ... "nw", "up", "down"** -- `setDoor(id, "u", n)`
  is refused as a special exit, so `doorKey()` maps u/d (up and down doors
  were never drawn before 1.5.13) -- and `setDoor` needs an exit or a stub
  in that direction; **`deleteRoom` takes the doors off its neighbours'
  exits into the room** (`removeExitExtras`), so a fog pass reads every
  record before deleting any, and leaves an exit stub with its door on a
  room still drawn where an exit went into the fog.
- **Map items**: one prototype, `OBJ_VNUM_AREA_MAP` (96, limbo.are, level 0),
  `ITEM_MAP` with `value[0]` `MAP_ITEM_AREA` (92 -- never 0, which `save.c`
  drops) and `value[1]` a room of its region; `map_item_create` names it.
  READ learns it and extracts it (`map_item_read`, from `do_read` after the
  Hyrule tools); one already known is left whole. `make_corpse` gives a
  slain mobile's corpse its area's map `MAP_DROP_PER_MILLE` (5) in a
  thousand (`map_corpse_drop`; never in Hyrule, for a pet or a charmed one;
  `TOC_MAP_DROPS=always` in tests), tagged `map` for the balance feed.
- **The cartographer** (mob 29942, `seasonal.are`): a twenty-to-forty-minute
  visit every two to five hours (`cartographer_update` beside the goblin's),
  in a room `black_market_room_ok` allows, not safe, outside Hyrule, in a
  mappable area; scaled to the mean level of the area's mobiles; walks the
  area himself (sentinel). Hidden as the dealer is (`is_unfindable_mob`),
  arrival logged without a room, WIZINFO with it; `cartographer_forget` from
  `extract_char`; `cartographer_slain` from `raw_kill_internal` puts the map
  of where he fell into his pack before `make_corpse`.
  `TOC_NO_CARTOGRAPHER` (set by `tests/live_mud.py`) and
  `TOC_CARTOGRAPHER_STILL` are for tests; staff CARTOGRAPHER calls him.
- **Explored**: every room of an area that counts (`map_room_countable`:
  `achievement_room_counts`, not a death trap, newbie or hero room, not in a
  guild hall, entered by some other room's exit) walked into, for an area of
  `MAP_EXPLORE_MIN_ROOMS` (10) or more: the set `explored-areas`, checked by
  `map_room_visited` when a room is new and by `map_login` at login from the
  rooms already saved (the file proves it). The per-area lists are rebuilt
  when `top_room` or `top_vnum_room` moves.
- **Staff**: GRANTMAP (L5; online or offline, `rank_protects`, saved, logged,
  WIZINFO at the pair's level) and CARTOGRAPHER (L5). `GRANTMAP <player>
  <map|all> REVOKE` takes maps back under the same rules
  (`map_revoke_region`, `map_revoke_everything`, through
  `achievement_set_remove`/`_clear`): only what the `map-areas` set holds;
  rooms walked stay known, a dungeon's NES map bit (`AchMaps`) is the
  achievements' record and is kept, and no achievement is taken back. It
  calls `map_known_changed`, so the client gets the smaller list at the
  next prompt (`tests/test_grantmap_revoke.py`). Player: MAPS (last in
  the command table, so no shorter word moved). Achievements `maps-*`
  (`ACH_REQ_AREA_MAPS`, `map_held_count`), `explored-*`,
  `cartographer-slain`, `master-cartographer` (cohort `cartography`).
  `tests/test_exploration_maps.py`.

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

**The game never waits on an Oracle spool, and loses nothing to one**
(review, 2026-11-12: `F_SETLKW` on `oracle.ask` and `oracle.queryresult`
held the whole game while the web process kept the lock, and
`oracle.query` was emptied before its results file was opened). Every
spool lock in `oracle.c` is `oracle_try_lock` (`F_SETLK`). A question or
control record is built at once and held in memory (`oracle_held`, at
most `ORACLE_HELD_MAX`; past that the supplicant is told the mists are
closed), and `oracle_spool_flush` -- at the ask and every pulse, from
`oracle_process_queries` -- writes all held records or none, cutting a
failed write back to the spool's size. Lookups take both locks without
waiting, write their findings with `write()`, and empty `oracle.query`
only after; a failure cuts the results back and keeps the requests, so
each is answered once. A spool that stays shut logs one line a minute,
counts only (a lock, only once held past `ORACLE_BUSY_QUIET`, 5 s: the
poller takes it for a moment every few seconds). **A question goes only after its save landed**: the poller
reads the asker's gear from their file, so `DURABLE_FAILED`
(`oracle-save` for tests) refuses it -- measured at 1-3 ms a question
with 1,700 objects carried, so the save stays.
`tests/test_oracle_spool_live.py` holds each lock from Python, makes the
files directories and `/dev/full`, and counts the records.

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
  fun (the old `spec_kidnapper` was removed, 2026-11-11). It leaves
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

## Connections: Lookups Off The Loop, And The Guard

**Every waiting connection is taken in one pass** (review, 2026-11-12).
`init_socket` listens with `SOMAXCONN` on a non-blocking socket, and
`init_descriptors` accepts until `accept` says EAGAIN, at most
`ACCEPT_BURST_MAX` (64) a pass; `init_descriptor` still runs the guard and
the lockout on each one. The backlog was 3 and the loop took one a pass:
four clients connecting before any logged in -- every live module does
that -- lost a greeting (macOS reset the connection; Linux left it
silent). `tests/test_connection_burst.py` opens 24 at once. **Keepalive**
is `src/tcpkeep.c` (no `merc.h`): TCP_KEEPIDLE, or TCP_KEEPALIVE on macOS,
which has no TCP_KEEPIDLE; every setsockopt is checked and a failure
logged once a boot (`tests/test_tcpkeep.py` reads the options back from a
real socket and builds the macOS branch on any host).

Found by the play journal's stall rows (2026-11-06): every slow pulse
lined up with an outside connection, because `new_descriptor` called
`getnameinfo` on the single game thread. **Nothing on the game loop may
wait on a resolver.** `src/dnsasync.c` is a worker thread with two bounded
queues and no game state (it includes no `merc.h`); `connection_spoke()`
in `comm.c` submits a lookup at a connection's first line -- after a
PROXY header has named the real address -- and logs `Sock.sinaddr` then,
so a silent scanner costs neither. `dns_collect()` runs at the top of
each pulse, gives a name only to the descriptor still holding its
`dns_serial` (`close_socket` zeroes it), refuses a name that is not plain
host characters (`host_name_clean`), and asks `check_ban` again, closing a
connection banned by name. Both builds link threads (`-pthread`,
`Threads::Threads`). `DNS <address>` by hand still blocks, deliberately.
`TOC_DNS_LOOPBACK=1` looks loopback up and `TOC_DNS_DELAY_MS` slows the
worker, for tests. Two workers (`DNS_WORKERS`), so one slow resolver
does not hold every lookup behind it; `close_socket` cancels a queued
lookup (`dns_async_cancel`), a job queued past `DNS_JOB_MAX_AGE` is
dropped, and staff DNS shows the counters (`dns_async_stats`: asked,
named, nameless, queue full, cancelled, expired, stale, average and
slowest ms). There is no cache and no per-lookup deadline: `getnameinfo`
cannot be interrupted safely, and a thread is never cancelled.

**A connection's address is not its host name** (review, 2026-11-06).
`d->addr` (`NET_ADDR`, `src/netaddr.c`: family and bytes) and
`d->addr_text` (canonical text) are set at accept or by the PROXY header
and never change; `d->host` is display only, and `d->host_resolved` says
whether it is a name `dns_collect` gave. `d->ip` is the 32-bit guard and
throttle key (`net_addr_guard_key`: IPv4 itself, an IPv6 /64 folded into
240.0.0.0/4) -- internal, never shown as an address. **Anything that asks
"is this the same address" or "is this banned" reads `d->addr`**:
`check_ban(d, type)` matches an address ban by bytes (`net_addr_equal`)
whatever DNS did, and a host-name ban only against a resolved name;
`wizinfo_same_host` compares `d->addr`, exact (not the /64); SOCKETS IP
and DNS LIST show `addr_text`. The host string used to be what all of
them compared, and the resolver rewrites it: a numeric ban stopped
matching once a PTR name came back, one address went unreported as
shared while only one connection had resolved, and two addresses with
one PTR name were reported as one. BAN and ALLOW store an address in its
canonical spelling (`net_addr_canonical`), so an IPv6 ban typed whole
matches the compressed form the web bridge sends. A parsed address is
the whole string (`net_addr_parse`): a numeric prefix is no address.
Staff listings of connections ask `staff_may_see_descriptor` (SOCKETS's
rule: the body and, switched, the original) and leave a hidden row out
whole; DNS LIST had shown a creator SOCKETS hid. `new_descriptor`
refuses a descriptor at or past `FD_SETSIZE` before it is one.
`tests/test_client_addresses.py`, `tests/test_guard_addresses.py` (the C
harness for `netaddr.c` and `guardstore.c`).

**The connection guard** (`src/connguard.c`; owner's rules, 2026-11-06:
never auto-ban an address a player uses; staff BAN still applies; staff
hear of every automatic action). **A pause stops new characters, never a
login** (false-positive review, the same day): a real player on an address
the guard does not know yet -- a new ISP, a phone, a carrier's shared
address -- gets the greeting, logs in, and that login trusts the address
and lifts the pause; `conn_guard_new_char()` in the nanny's new-name path
refuses creation with the minutes left and re-prompts. An address is
paused after `GUARD_STRIKES` (6) strikes in `GUARD_STRIKE_WINDOW` (6 h) or
`GUARD_BURST` (20) connections in a minute, `GUARD_BLOCK_BASE` (6 h)
doubling per pause in a week to `GUARD_BLOCK_MAX` (7 days). **A strike is
counted at close** (`conn_guard_closed`, from `close_socket`) for a
connection that reached no password prompt (`d->guard_named`, set at the
old character's password prompt and at a new name's confirmation) -- and
never for one the login prompt timed out (`guard_idle_closed`: a client
left open reconnects by itself), one that asked for MSSP (`guard_mssp`,
the listing crawlers) or one through the web bridge (`guard_proxied`: a
reload is a connection). Only a flood -- `GUARD_FLOOD` (60) in a minute --
is refused before the greeting, by `conn_guard_admit()` in
`init_descriptor` (and again after a PROXY header), for
`GUARD_FLOOD_SECS` (an hour) flat; so is a connection past
`GUARD_PENDING_MAX` (8) not yet playing from one address. **An address a
player logged in from within `GUARD_TRUST_DAYS` (90), or is playing from
now, is never counted, limited or paused**: `login_note_success` and the
new-player path call `conn_guard_trust(&d->addr, who)`, kept in
`log/player_addresses.tsv` by `src/guardstore.c` (no `merc.h`; an
address, IPv4 or IPv6, and the last login from it; the newest line
wins; rewritten past `GUARD_TRUST_FILE_MAX`). **A row keeps two times**:
`last`, the newest login seen, and `persisted`, the newest the file is
known to hold; a write is due a day after the last line that *landed*
(`guard_store_due`), never a day after the last login -- measured from
the last login, a player who logged in more often than daily postponed
the write for ever and a restart read back their first login. Every
`fprintf`/`fflush`/`fclose` is checked; a failed write leaves `persisted`
alone and is tried at the next login and every five minutes by
`conn_guard_tick`. **The file is the record**: once it exists the
journals are never read to repair it. With none, `guard_load` starts it
once from `log/logins.tsv` connect/reconnect/new rows and `toc.log`
`Name@host has connected/reconnected/new player.` lines whose host is a
numeric address (`guard_seed_login_row`, `guard_seed_log_line`), and
nothing else: a host-name login ties no address, and a `Sock.sinaddr`
line is never joined to a later login by nearness -- the old seeding
did, and an interleaved connection gave the trust to the wrong address.
A player missed is never shut out (a pause stops only new characters,
and their login is recorded). Pauses, strikes and floods are memory
only: a restart lifts them, deliberately. **The file is read whole or
not trusted** (review of f1388da0): `guard_store_load` returns
`GUARD_LOAD_ABSENT` only for ENOENT -- the one case that starts the
record from the journals -- and `GUARD_LOAD_UNREADABLE` for a file that
is there and could not be read whole (permission, `ferror`, a failed
close), which makes the store `read_only`: what was read is used and
nothing is ever appended or rewritten over the file until a reboot
reads it (DNS GUARD says so). A record counts only whole: an address, a
tab, digits that do not overflow, above zero and no more than
`GUARD_CLOCK_SKEW` (a day) ahead of now, and a newline; lines that fail
are counted (`bad_lines`) and the next rewrite drops them. An append
first ends an unfinished last record with a newline (`ends_whole`), so a
torn line and the new one are never read as one record with a
far-future time -- which had made trust permanent. Every write error is
sticky (`finish`: the flush, the stream's `ferror`, `fsync` only after a
good flush, the close always), and a rewrite renames nothing after any
failure; `tests/test_guard_addresses.c` injects a first flush that
fails and later ones that succeed (`-DGUARD_STORE_FFLUSH`).

**A login is noted only once it is one** (review of f1388da0).
`login_note_success` -- trusting the address and clearing its failures --
runs after the reconnect, or after `login_reload_character` and
`creator_arrives_unseen`, and after a "connect anyway" reconnect; never
straight after the password matched the copy loaded at the name prompt,
which the file could then refuse (a password changed meanwhile).
`login_password_current` asks the live character's password too, before
anything else: that copy carries the password as it was, so "connect
anyway" took over a playing character whose password had changed since.
**Guard and DNS notices that name somebody go out at their
`staff_notice_level`**: `guard_say(text, level)` (an address-only notice
at `LEVEL_IMMORTAL`), `conn_guard_trust(addr, why, level)`, and DNS
ALLOW and DNS ON/OFF name `staff_actor(ch)` -- a switched immortal's own
character -- at that character's level. A wizinvis creator lifting a
pause by logging in was named to every immortal. The log still keeps
the name, as every notice's does. **Staff hear it** through
`guard_say()` (log and WIZINFO): each pause and flood, a pause lifted by a
login, and -- once an address in `GUARD_NOTICE_SECS` -- a new character or
waiting connection refused; the hourly summary goes to WIZINFO when
anything was refused or paused. Loopback is exempt (`TOC_GUARD_LOOPBACK=1`
for tests -- apart from the login throttle's `TOC_THROTTLE_LOOPBACK`,
whose tests make many failed connections; `TOC_GUARD_STRIKES`,
`TOC_GUARD_BURST`, `TOC_GUARD_FLOOD` lower the limits). Silent connections
(closed with no line) are counted into one `Connection guard:` log line an
hour, not logged one by one; "EOF encountered on read." is logged only for
a connection that spoke. `login_idle_sweep()` closes a connection not
playing after `LOGIN_IDLE_SECS` (600; `TOC_LOGIN_IDLE_SECS`) without input
(`d->input_at`). Staff `DNS GUARD`/`DNS ALLOW <address>`. A test that
needs an untrusted loopback after creating a character stops the server,
writes an empty `log/player_addresses.tsv` (a comment line) -- deleting
it starts the record again from the journals, which hold the world's own
logins from 127.0.0.1 -- and boots again. A test of the start deletes it
and writes the journals it wants read. `GUARD_GLOBAL_PENDING` (200;
`TOC_GUARD_GLOBAL_PENDING`) caps connections not yet playing across the
game, for untrusted addresses only.

**Wrong passwords are `src/loginlock.c`** (owner, 2026-11-06: "if the
wrong password is entered over x times I want to ban the IP for x time.
Increasing with warning"; it replaced the old throttle in `comm.c`).
Every password refusal goes through `login_wrong_password(d, ch)` -- the
name prompt's copy, the live-password check and `login_reload_character`
-- which counts it, writes "Wrong password." and what comes next, and
leaves the close to the caller; `login_lock_remaining`/`login_lock_refusal`
refuse a locked-out address before the greeting and again after a PROXY
header. `LOCK_THRESHOLD` (5) in any `LOCK_WINDOW_SECS` (15 min) -- a
rolling window, `src/lockwindow.c` (no `merc.h`; each failure leaves it,
with the name it carried, fifteen minutes after it was made, and
`tests/test_lock_window.c` holds it to a synthetic clock; it used to be
cleared only by a fifteen-minute gap, so five failures fourteen minutes
apart locked an address out; review, 2026-11-09) -- locks out for the
next rung of `lock_ladder` (15 min, 1 h, 6 h, 1 d, 7 d) by lockouts within
`LOCK_MEMORY` (a week); a guard-trusted address is capped at
`LOCK_TRUSTED_MAX` (an hour) -- exempt from the scanner guard, never from
password limits. Lockouts are kept in `log/login_lockouts.tsv` (written
aside and renamed; read at boot by `login_lock_boot`, whole lines only).
**A lockout file that is there and cannot be read whole is never written
over** (review, 2026-11-09: it was taken for an absent one, and the next
lockout replaced it): only ENOENT is absence; an open that fails otherwise,
a read error or a failed close sets `lock_read_only`, logs it, keeps
lockouts in memory, writes nothing until a boot reads the file, and DNS
GUARD says NOT KEPT (fault point `lockfile-read`).
`login_lock_success`, from `login_note_success`, forgives the window's
failures that named the character that logged in and keeps every failure
at anybody else (`lock_window_forget_name`), and tells them
of attempts on them (`lock_names`: per character, across addresses;
WIZINFO at their `staff_notice_level` at `LOCK_ACCOUNT_ALERT` (10) in an
hour). Its words never say "wrong password": a client -- and
`tests/live_mud.py`'s `login()` -- reads that as its own login failing.
`TOC_THROTTLE_LOOPBACK=1` counts loopback; `TOC_LOGIN_LOCK_SECS` sets the
first rung and scales the rest, for tests. DNS GUARD lists lockouts, DNS
ALLOW lifts one. `tests/test_login_throttle.py` (a serial module).
`tests/test_connection_guard.py`, also in `SANITIZE_MODULES`.

## Staff Invulnerability

`is_invulnerable(ch)` is the one test, and it asks `is_staff(ch)` --
**level, not trust** (owner, 2026-11-12: "let trusted players act as
mortals across the board"). A mortal whose trust reaches INVULN may type
it and is told it is an immortal's; nothing is set, and a bit left from
before is read as nothing, so they are hurt like anyone
(`tests/test_wards_and_invuln.py`, `tests/test_trusted_mortal.py`). Until
then it asked trust, so a builder trusted to immortal rank was invulnerable
at a mortal level. A switched immortal is not protected: `PLR_INVULN`
shares a bitfield with the `ACT_*` flags, so the `!IS_NPC` guard is load
bearing and a mobile's own bit must never be read as this one. `damage()` honours it in three places: an
early return for `PLR_INVULN_ABSORB`, the `damage_eq` call, and the
subtraction from hit points -- and a fire or frost shield's reflection,
which takes hit points outside `damage()`, asks it too (review,
2026-11-04: `ch->hit -= dam1` burned an invulnerable attacker): ABSORB
reads as immunity, DAMAGE as a blow that takes nothing
(`tests/test_drain_and_reflection.py`). Leaving the subtraction as the chokepoint is
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
together, or installed packages never fetch it. The escaping is one
function, `gmcp_json_char`, under both the fixed-buffer writer and
`gmcp_dstring_append_quoted`.

**`telnet_send_gmcp` drops anything past its 2,048-byte frame, silently.**
A feed whose payload can grow is built in a bounded `DString` and sent with
`telnet_send_gmcp_large( d, package, json, max )` (three writes, no copy),
and its snapshot is marked sent only when that returned true. **Char.Items**
is (review, 2026-11-12: seventy-two 45-letter names overflowed the old
4,096-byte array, the cut JSON was dropped and the snapshot marked sent):
worn things whole within `GMCP_ITEMS_WORN_BYTES`, then carried things,
whole entries only, at most `GMCP_ITEMS_MAX_ENTRIES` and within
`GMCP_ITEMS_MAX_BYTES` with room kept for the worn list and the counts;
`inventory_total`, `equipment_total`, `truncated` and `equipment_truncated`
say what was left out, and the package's Items pane shows the cut. Its
"changed?" signature (`gmcp_items_signature`, the fast path at every
prompt) hashes each object's vnum, wear slot, **name bytes** and
**`can_see_obj`**, never a name pointer: RESTRING frees and `str_dup`s, and
the allocator may hand back the same address. A new field the pane shows
goes into the signature too (`tests/test_gmcp_items.py`).

**A Room.Info for the room you stand in is not an arrival** (package
1.5.15). The game resends it when a door opens or a service changes;
`tocMudlet.onRoomInfo` redraws doors, exits and buttons either way but
calls `onWalkArrival` only when the room number changed, or a walk that
opened a door on its route stopped one step short. Exit buttons and the
walker step through one helper, `tocMudlet.move` (opens a door `Room.Info`
calls closed or locked, says how to pass a locked one); the walk's
watchdog retries a compass step once with OPEN and takes a step already
landed as an arrival (`tests/mudlet_ui_spec.lua`).

**Mudlet's extras** (2026-11-07; formats read from Mudlet's own source,
since its wiki is unreachable from a cloud session). `gmcp_note_supports`
keeps what `Core.Supports.Set/Add/Remove` named: **Client.Media** gets
`Client.Media.Default` (the repository's `mudlet/media/`) and
`gmcp_play_sound(ch, name)` plays `toc-<name>.wav` -- six sounds, generated
by `tools/build_sounds.py` (`--check` in the tests; never a borrowed file),
not to a player with `COMM_NOSOUND` (SOUND OFF); **External.Discord** gets
`External.Discord.Status` (game, "Name, level N Class", "In <area>" or
"Somewhere unseen" for wizinvis, starttime), sent when its hash changes from
`gmcp_send_room` and the Char.Status branch; **Char.Login** gets
`Char.Login.Default {"type":["password-credentials"]}` once at the name
prompt. `Char.Login.Credentials` is never logged: the name is typed for the
player at the top of the next input pass (`gmcp_login_start` -- not inside
the read, which writes its own bytes over `d->inbuf`), the password at the
password prompt (`gmcp_login_after_nanny`), and `Char.Login.Result` says how
it ended (`login_wrong_password` says "Wrong password."); the password sits
on the descriptor only between the two and is wiped at close. Every check
a typed login meets still applies. **TTYPE/MTTS** (`telnet_note_ttype`)
and `Core.Hello` fill `client_name`/`client_term`/`client_mtts`; DNS LIST
shows them (`client_describe`), and `color_code` gives a client whose MTTS
lacks 256 colours and true colour the nearest basic colour for a 256-colour
name. New characters are told TOCGUI OFF/ON (Mudlet's listing requires it).
`tests/test_mudlet_extras.py`; `mudlet/listing-submission.md` has the
listing status.

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
  five that walk the descriptor list themselves each record their own.
- **Reading a channel back needs the rank that hearing it needs.**
  `history_may_read()` compares `staff_trust()` against the same
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

## IGNORE

`do_ignore` in `src/act_comm.c` (owner, 2026-11-11: "fix ignore command";
it had been a stub). `pcdata->ignore` holds capitalised names one space
apart, at most `IGNORE_MAX` (20), saved as `Ignore <names>~` under **case
'I'** only when not empty; the old `Ignoring` key every file carried is read
into the same list and cleaned, so lists players set years ago apply again.
`is_ignoring(listener, speaker)` is the one test, and a staff speaker is never
ignored. It is asked by TELL/REPLY (the sender is told), GTELL, every channel
loop beside its GMCP emit, HISTORY, `is_note_to` (so an ignored player's
notes leave the board and the numbering stays whole), and by `act_new` for
messages sent through `act_speech()` -- SAY, EMOTE and POSE -- and nothing
else: blows, spells and socials still land. A new way of speaking to other
players asks it too (`tests/test_ignore.py`).

## One-Person Rooms

`ROOM_SOLITARY` closes a room at one occupant and `ROOM_PRIVATE` at two.
Two rules, both learned from one incident where an idle immortal in the
quest room shut questing down for the whole mud:

- **Only mortal players count towards the occupancy.**
  `room_is_private()` skips NPCs and staff (`is_staff`: immortals by
  level; a mortal given trust counts like any player). A mobile
  that lives in the room filled a slot for good -- the quest giver's
  room is `ROOM_PRIVATE`, so the questmaster plus one player was already
  two, and a solitary room with a resident mobile admitted nobody at
  all. The flag exists to stop players walking in on each other, not to
  let a mobile or a staff character close a room by standing in it.
- **`can_enter_private_room(ch, room)` is the one place that decides
  who may walk in anyway.** Every caller used to ask
  `ch->level < 69` -- a number rather than a rank -- so an ordinary
  immortal was refused. It lets staff in by `is_staff` (level), never a
  mortal's trust. `ROOM_IMP_ONLY` is not an occupancy limit and keeps its
  own `GOD` bar inside that helper, asked of `staff_trust`.

`tests/test_private_rooms.py` pins both, including that no caller reads
a raw level again.

## Permission Helpers

**Staff are immortals by level; trust is command authority** (owner,
2026-11-12: "i think trusted characters should actually be logged also.
just not immortals", "no let trusted players act as mortals across the
board", "staff-only should ONLY apply to actual immortals level 60+"). It
reverses the 2026-09 staff-trust sweep, which made every staff test ask
`get_trust` so a builder trusted to immortal rank counted as staff
everywhere. The helpers:

- `is_staff(ch)` (handler.c) -- **the one test for "is this person
  staff"**: an immortal by level (`LEVEL_IMMORTAL`, 60, and up), asked of
  the original character behind a switched mobile, never a mobile on its
  own (`IS_IMMORTAL` would call a level 60 mobile staff), and always the
  creator. Every gameplay exemption or perk (invulnerability, private and
  newbie rooms, travel rules, hunger, loot, eating anything, the
  repeat-command kick, the black market and the goblin, Hyrule's order --
  `hyrule.c` asks `IS_IMMORTAL` -- jail placement, the Oracle's sanctum,
  login fixes) and every exclusion from play's bookkeeping (achievements'
  `ACH_STAFF`, quests, dailies, the diary, the journals, the hero rolls,
  the audit tool) asks it. Never `IS_TRUSTED(x, LEVEL_IMMORTAL)` or
  `get_trust(x) >= LEVEL_IMMORTAL` for that question;
  `tests/test_staff_trust.py` sweeps for both.
- `staff_trust(ch)` -- **the rank a staff-only view, channel or notice
  compares**: `get_trust` for staff, the level for anybody else. WIZINFO's
  listeners (`>= UMAX(level, LEVEL_IMMORTAL)`, so no mortal hears it at
  all), the staff channels and HISTORY of them (`channel_say`,
  `history_may_read`), `sight_trust` (wizinvis and cloak: a trusted mortal
  sees no wizinvis immortal), WHO's switched rows, ECHO's and PECHO's
  prefix, GOTO's bamfs, MEMCHECK's event names, the IMP_ONLY rooms. A
  staff-only answer inside a command anybody may type (CHANGES' staff
  entries, DIARY of another, HOLIDAYS' staff lines, WALKTO <vnum> and
  WALKTO QUEST's room, the GMCP quest room, the dummy board's removals)
  asks `is_staff`.
- `get_trust(ch)` -- **command authority and rank, and nothing else.**
  `interpret()` gates every command on it, so a mortal given trust may
  type the commands it reaches (GOTO, STAT, IMMTALK...) -- and inside them
  a staff-only effect is by level: INVULN is refused, IMMTALK may be
  spoken but not heard. Rank comparisons of who may act on whom stay
  trust's: `rank_protects`, TRUST's own limits, SNOOP's recheck, LOAD's
  and CLONE's tiers, a command's own `get_trust(ch) < MAX_LEVEL` that
  mirrors the command table, help pages' levels (`do_help`), the creator's
  72. Never read `ch->trust` directly: it is 0 unless explicitly set.
  One `IS_TRUSTED(ch, LEVEL_IMMORTAL)` survives on purpose: `do_switch`
  picks SWITCH's message over the werewolf shapeshift below it, so anybody
  the table let type SWITCH must take that arm.
- A command a trusted mortal can start and that then refuses them a
  staff-only effect by level is expected, not a bug. Holy light is the one
  exception kept: HOLYLIGHT's sight (not of wizinvis, which is
  `sight_trust`'s) works for whoever has the bit, because the Farslay
  scroll lends it to mortals for a moment.

`tests/test_trusted_mortal.py` plays a level 20 trusted to 65 against a
level 65 immortal: GOTO and STAT work; INVULN, IMMTALK, WIZINFO, staff
CHANGES and wizinvis sight do not; achievements are paid.
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
  level -- and `wizinfo` picks listeners by `staff_trust`, staff only.
  Every one is
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

## Memory Is The System Allocator's

Owner, 2026-11-11 (modernization project 4). ROM's pools -- alloc_mem's
size-class free lists and a free list per type (characters, pcdata,
objects, descriptors, affects, extra descriptions, notes, bans, wizlist
entries) -- handed a freed block to the next thing created, so ASan never
saw a use after free or a double free in any of them. They are gone:

- **`alloc_mem` is `calloc`, `free_mem` is `free`.** The size classes
  stay: a request past 32,704 bytes still aborts, and an ordinary build
  still allocates the class's size, so slack is as it was. Under ASan
  (`__SANITIZE_ADDRESS__`) a request is allocated at its exact size.
- **Permanent memory is never freed.** `alloc_perm` registers its blocks
  and `free_mem` leaves a pointer into one alone (`is_perm_memory`), as
  `free_string` leaves the boot string space and `str_empty` alone. That
  is what keeps an instance's prototype strings (shared by pointer, see
  `str_perm`) and a prototype's affects safe from extraction. Instance
  data that is freed later -- `create_object`'s random affects, notes,
  bans, an object's own extra descriptions -- comes from `alloc_mem`.
- **"Is this pointer in that block" is asked on integers**
  (`src/memrange.c`, review 2026-11-12). C defines `<`/`>=` only between
  pointers into one object, and the pointer asked about is usually an
  ordinary heap allocation, so `is_perm_memory` ordering it against
  alloc_perm's bounds and `free_string`/`str_dup`/`str_perm` against
  `string_space` were undefined (ASan `-fsanitize=pointer-compare`,
  `detect_invalid_pointer_pairs=2`: invalid-pointer-pair). The perm blocks
  are a `MEM_BLOCK_SET` of `uintptr_t` bases; membership is
  `addr - base < size` in unsigned arithmetic (`mem_addr_in`), interior
  pointers in, one past the end out; `in_string_space()` in `db.c` is the
  one string-space test. Never write `p >= block && p < end` across
  allocations again; `tests/test_memory_ranges.py` fails on it and runs
  `tests/test_memrange.c` under that sanitizer.
- **Characters (with their pcdata), objects and descriptors are released
  to `src/recycle.c`** (`char_data_release`, `obj_data_release`,
  `descriptor_data_release`) and freed by `recycle_flush()` at the top of
  the game loop, beside `flush_container_lists()`, once their quarantine
  is over (see Memory Safeguards; at once under ASan): the game reads one it
  has just extracted or closed in the same pass, and that read stays
  valid. A read in a later pass is a real use after free, and ASan says
  so. A second release, `free_char` or `extract_obj` of the same thing is
  refused with a bug line (`next_free` is non-NULL only while released).
- `tests/test_memory_pools.py` fails on any free list coming back.

## Memory Safeguards

Owner, 2026-11-11: with the pools gone, a stale pointer that survives
into a later pass reads freed memory, so any left in live play must be
**seen at once and survived**, to be fixed at the next check-in.
`src/recycle.c`, `src/memtrack.c` and `src/memguard.c`;
`tests/test_memory_guard.py`, `tests/test_memory_ranges.py`.

- **Liveness by address, never by reading** (`src/memtrack.c`, review
  2026-11-12). Every CHAR_DATA, OBJ_DATA and DESCRIPTOR_DATA is
  registered in an address set (open addressing, O(1)) by
  `char_data_new`/`obj_data_new`/`descriptor_data_new`, marked dead by
  its release and forgotten by `quarantine_free_block` before the
  `free`. `char_liveness`/`obj_liveness`/`desc_liveness` answer
  `MEM_STATE_LIVE` (NULL, or made and not released), `MEM_STATE_DEAD`
  (in quarantine: whole, its own fields safe to read) or
  `MEM_STATE_FREED` (anything else -- freed, the address now holding
  another kind, or never made here) **without touching the memory**;
  `*_is_live` is "LIVE". The checks used to read `mem_magic`, and once
  the window was over or the cap passed that read was itself a use after
  free (`tests/test_recycle_liveness.c`, cap saturation). `mem_magic`
  (`MEM_ALIVE_*`/`MEM_DEAD_*`) is still written, for a debugger, and
  decides nothing. A second release -- or a release of a stand-in -- is
  refused by the set.
- **Serials: an address reused by the same kind** (2026-11-12). Every
  registration -- each allocation, and each stand-in -- gets a 64-bit
  serial, never 0 and never repeated, kept in the set's slot (not in the
  block, which `*ch = ch_zero` and the like overwrite). The long-lived
  pointers keep a `MEM_REF` beside them -- the pointer as set and the
  serial of what it named then: on CHAR_DATA `fighting`, `master`,
  `leader`, `pet`, `hunting`, `reply`, `questgiver`, `desc`, `in_object`;
  on OBJ_DATA `trapped`; on DESCRIPTOR_DATA `character`, `original`,
  `snoop_by`; and each hunter-list slot's `ch`. **They are written only
  through `SET_CHAR_REF`, `SET_OBJ_REF` and `SET_DESC_REF`** (merc.h:
  holder, field, value; the holder is evaluated twice), and
  `tests/test_memory_serials.py` fails on any raw `->field =` for them in
  `src/*.c`. `mem_ref_liveness(p, ref, kind)` (recycle.c) answers
  `MEM_STATE_REUSED` when the address is live or dead under another
  serial than the ref's -- one probe, never reading `p` -- and memguard's
  `mg_ref` asks it for every one of those fields, in the sweep and in the
  hot spots. A field found written without its ref (`ref.ptr` is not the
  pointer: a raw write the source test missed, or memory copied whole) is
  checked by address as before, its ref taken from it then if it is live,
  counted ("written without their serial" in MEMCHECK) and logged once a
  field a minute. **What serials do not cover**: the list links
  (`carrying`/`next_content`, `contains`, room `people`/`contents`,
  `next_in_room`, the character, object and descriptor lists), an
  object's `carried_by`/`in_obj`, `resurrect_corpse`,
  `gmcp_last_character`, the stash, and any pointer not on that list --
  each still checked by address alone, so a stale one whose address the
  same kind has reused reads live. Those are either kept consistent by the
  list code itself or cleared where their target goes; a new long-lived
  field should get a `MEM_REF` and a setter, and go into `mg_ref`.
- **Stand-ins are registered while in use** (2026-11-12):
  `mem_standin_begin(p, kind)` and `mem_standin_end(p)` around the use,
  on every way out -- `offline_player_load`'s descriptor (begun at its
  `memset`, ended before each return: the loaded character never keeps
  it), gear_compare's two stack candidates, `corpse_file_read`'s static
  vessel. A registered stand-in reads LIVE, has a serial a ref can keep,
  and is refused by every release (`memtrack_dead` refuses it; the
  `*_data_release` functions say "a stand-in"), so it is never queued or
  freed. `mem_standin_end` ends only a stand-in, never a real block. The
  sweep never runs inside a command, so one still registered when it runs
  is a missed end: it is logged once a minute and counted in MEMCHECK's
  `Stand-ins` line. The zero templates (`ch_zero`, `obj_zero`, `d_zero`)
  and recycle.c's `next_free` sentinels are never pointed at by a checked
  field and stay unregistered; never store a pointer to a stack or static
  object in a checked field unless it is registered for as long as it is
  stored.
- **Quarantine.** A released block is kept whole (never poisoned, so a
  stale read behaves as the old pool did) for `MEM_QUARANTINE_SECS` (60;
  `TOC_MEM_QUARANTINE_SECS` overrides, 0 to 3600) and at most
  `MEM_QUARANTINE_MAX` (8192) blocks, then freed oldest first by
  `recycle_flush` at the top of the game loop -- never mid-pass, so the
  cap may be passed until the next flush. **Under ASan the window is 0**
  unless the environment sets one, so the sanitizer still reports a use
  after free itself (in the game's own code; the guard's checks no longer
  read, so they report "freed" instead); a test that needs the sweep to
  find a block still dead sets the window (`test_memory_guard` uses 30,
  and 0 for the freed case). Each entry keeps a label written
  at release from what is still safe to read: a player's name
  (`recycle_label_char`, called by `free_char` before the strings go), a
  mobile's or object's prototype, a descriptor's socket number -- never
  an address. Never read a dead block's strings: they are freed.
- **The sweep** (`memguard_sweep`, first thing in `update_handler`, once
  a second) walks the character list, the object list, every room's
  people and contents, the descriptor list and the hunter list, and
  checks fighting, master, leader, pet, hunting, reply, questgiver, desc,
  in_object, carrying, the stash, resurrect_corpse; trapped, contains,
  carried_by, in_obj; the room lists; a descriptor's character, original,
  snoop_by and gmcp_last_character. A dead target writes
  `MEMORY: stale <field> on <who> -> dead <kind> (<label>)` to toc.log
  (ten a field a minute, then a count), a **nameless** BUG row to the play
  journal, and a WIZINFO once a field a minute at the holder's
  `staff_notice_level`; a freed one writes `-> freed <kind> (gone from
  quarantine; not read)` -- nothing is known of it, so there is no label
  -- and MEMCHECK counts those apart. Measured at about 2 ms a run on a
  full test world (5,556 characters, 6,013 objects, 85,000 pointers),
  with or without the serial comparison (one probe either way).
- **Repairs**, each the least that leaves the game consistent:
  fighting is cleared *then* `stop_fighting(ch, FALSE)` resets the
  position (stop_fighting would write the dead opponent's battle ticks);
  hunting leaves the hunter list by `delete_from_hunter_list`, never
  `do_stop_hunting`, whose notice reads the prey's freed name; a dead
  hunter-list slot is emptied; a dead master also lifts charm and
  `ridden`; a dead pet unmounts; a dead desc leaves the character
  link-dead; a list link to a dead object or character is unlinked
  through the dead block's own link, and a list reaching a **freed** one
  is cut there (its link cannot be read) and `mg_relink` puts back what
  followed from the other side -- an object's `carried_by`, `in_obj` or
  `in_room`, a character's `in_room`, a playing character's `desc` --
  logging how many it found; a stash's objects keep no owner, so what
  followed a cut there is lost to it (PRESTORE STASH), as is a descriptor
  past a cut whose character is not in the game yet; an object whose holder or container
  is dead goes to the floor of Limbo (room 2) rather than being
  extracted, since it may be a player's -- the log line names its vnum;
  a character in a dead bottle goes as `captive_dispose` sends it (a
  mobile extracted, a player to the altar). A descriptor whose character
  is dead goes back to its `original` if that lives, else is marked
  `write_failed` and the output loop closes it. resurrect_corpse and
  gmcp_last_character are compared by pointer only, and are cleared
  where their target goes -- `resurrect_forget_corpse` from both
  extract_obj paths, the descriptor walks in `extract_char` and
  `free_char` -- so a catch of either is a real bug and is reported
  (review, 2026-11-11: they were left to go stale "by design", and the
  sweep itself then read the purged corpse once the quarantine had freed
  it -- an ASan heap-use-after-free in `obj_is_live` with no quarantine,
  whenever the sweep ran a pass after the purge;
  `tests/test_memcheck_purge.py`). Since 2026-11-12 the sweep no longer
  reads a pointer to learn whether it is dead, so it survives one past
  the window -- but it can only say "freed", or "reused" for a field kept
  with a serial, and an address reused by the same kind behind any other
  field it cannot see at all: a field that is meant to outlive its
  target must still be cleared at the target's extraction, never left
  for the sweep. A reused target is repaired exactly as a freed one and
  logged `-> reused <kind> (its address now holds a newer one; not
  read)`; nothing is known of the old target, and the quarantine label at
  that address, if any, is the newer block's, so it is not shown.
- **Hot spots ask first**: `violence_update` (`memguard_fighting_ok`),
  `hunt_victim` (`memguard_hunting_ok`), `hunting_update`
  (`memguard_hunter_slot_ok`), the output loop
  (`memguard_descriptor_ok`, before the `write_failed` check) and
  `do_reply` (`memguard_reply_ok`). A new timer that follows a stored
  pointer asks too; a new pointer field goes into the sweep.
- **MEMCHECK** (IM, after MEMORY so MEM is still MEMORY): quarantine,
  live counts, the address set's live and quarantined counts (and the
  limit above), sweep cost, catches by field (how many were already
  freed, and how many relinked), the last five events. Each
  event keeps the trust that may read it -- the higher of the holder's
  and the dead target's `staff_notice_level`, the target's taken at its
  release (`recycle_label_char`) -- and MEMCHECK shows a viewer only the
  events at or below their trust (review, 2026-11-11: a level 60 read a
  wizinvis 70's name). Counts are not names and are shown to all.
  `MEMCHECK SELFTEST` works only with `TOC_MEMCHECK_SELFTEST=1`: it
  aims the caller's REPLY at a mobile in no list, which the next sweep
  retires straight through `char_data_release` (`mg_selftest_retire`), so
  the sweep after it is the first to look, across at least one flush:
  "dead" inside a window, "freed" with `TOC_MEM_QUARANTINE_SECS=0` (or
  "reused", should a reset hand the freed address to a new mobile before
  the sweep looks). `MEMCHECK SELFTEST REUSE` instead ends the mobile's
  registration and registers its address again as a new character -- what
  the allocator does -- without freeing it, so the next sweep must say
  "reused" by the serial while the address alone reads live
  (`tests/test_memory_serials.py`; the C harness's `reuse` mode also plays
  real glibc reuse, without ASan, in `tests/test_memory_ranges.py`).
- **crash.log has a backtrace**: the handler writes the build (first word
  of `../.code-revision` or `../log/deployed-commit`, read at boot) and
  `backtrace()`/`backtrace_symbols_fd()` under `__GLIBC__` (warmed once
  in `playlog_boot` so libgcc is loaded). Both builds link `-rdynamic`
  (Makefile LDFLAGS on Linux, CMake `ENABLE_EXPORTS`) so frames are named.
- `tools/log_report.py`'s `== memory` section counts MEMORY lines by
  field, prints the newest, and shows crash.log's backtraces; the morning
  check-in reads it. Any MEMORY line is a bug: find who leaves that field
  pointing at something extracted and clear it in `extract_char`,
  `extract_obj` or a `*_forget` hook.

## Contracts From The October 2026 Audit

An outside audit (2026-10-21) found these; each is fixed, and each has a
test that fails on the old code. Keep them.

- **Build a replacement string before freeing the old one.** `do_stash`
  freed `stash_links` and then read it to build the new list; the pool
  reuses a freed block's first bytes, so a second LINK wrote allocator
  bytes before the first partner's name and locked them out
  (`tests/test_stash_link.py`). ASan could not see this through the
  pool; since 2026-11-11 there is no pool, and it would.
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
- **The Oracle's answer cache keys on everything per-player that changes
  the answer**: the guild in `_oracle_cache_key`, and a digest of the
  asker's ABILITIES in `oracle.poll_once`, the one place that has them
  (`tests/test_oracle.py`). **And a cached answer is built from nothing
  else** (review, 2026-11-12): a keyed question gets
  `_oracle_context(shared=True)` -- no name, no worn gear, no live
  lookup, no corpse, no Hyrule state -- and the prompt says "A player
  asks", so it never names its first asker to the next. The key carries
  `balance.version(PROGRESS_LOG)` when the context quotes the feed (the
  leveling guide, the gear finder's drop counts: `_oracle_wants_*`, the
  context's own tests) and the holidays on for the gear finder. The
  shared context is a callable `consult` builds only on a miss. A new
  context line that reads the asker belongs in the personal context only,
  or in the key (`tests/test_oracle_cache_sharing.py`).
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
  unpaged (`tests/test_changes.py`). Keep both when touching either: a
  bounded `DString` (C Change Rules) leans on them.
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
  area file and a 0-byte player file from RESETPWD. Tests inject the
  failure with a `/dev/full` symlink, which needs no root.
- **PRESTORE STASH is all-or-nothing**: the snapshot's `#END` is checked
  first, the `#STASH` section is validated without reading anything into
  the game (no `fread_number` exit), objects are read aside and spliced in
  only if all came back.
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
  **So does VAMPIRIC TOUCH** (review, 2026-11-04: it healed from the
  rolled number before the blow): `damage_drain_next(2)` before its
  `damage()`, and the caster drinks half of what came off, in the same
  place by the same rules. A new draining spell does the same
  (`tests/test_drain_and_reflection.py`).
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
