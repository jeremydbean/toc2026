# Validation and Area Health

This guide explains the ToC validation stack: what to run locally, what CI runs, what the area-health severities mean, and where to start when something fails.

## Quick Start

From PowerShell on Windows:

```powershell
.\scripts\validate.ps1
```

From Linux, macOS, or WSL:

```bash
bash scripts/validate.sh
```

Run the optional live-start smoke test when a change touches startup, the game loop, sockets, backups, or area loading:

```powershell
.\scripts\validate.ps1 -RunSmoke
```

```bash
RUN_SMOKE=1 bash scripts/validate.sh
```

## Prerequisites

Windows validation uses both Windows Python and WSL:

- WSL distro with `gcc`, `make`, and `libcrypt` development support
- Python 3.9+ in the Windows checkout
- Python dependencies installed from both requirement files

```powershell
.\.venv\Scripts\python.exe -m pip install -r webadmin\requirements.txt -r scripts\requirements.txt
```

Linux, macOS, WSL, and CI use the Bash runner:

```bash
python3 -m pip install -r webadmin/requirements.txt -r scripts/requirements.txt
```

## Full Validation Scripts

### `scripts/validate.ps1`

Use this from PowerShell at the repository root. It:

- maps the Windows checkout path to `/mnt/<drive>/...`
- runs C build steps in WSL
- runs Python checks and unit tests from the Windows checkout
- accepts `-Distro <name>` when your WSL distro is not named `Ubuntu`
- accepts `-RunSmoke` and `-SmokePort <port>` for a short live server smoke test

Example:

```powershell
.\scripts\validate.ps1 -Distro Ubuntu -RunSmoke -SmokePort 9999
```

### `scripts/validate.sh`

Use this from Linux, macOS, WSL, containers, and CI. It accepts:

- `PYTHON=/path/to/python` to choose a Python interpreter
- `RUN_SMOKE=1` to run the live startup smoke test
- `SMOKE_PORT=9999` to choose the smoke-test port

Example:

```bash
PYTHON=python3 RUN_SMOKE=1 SMOKE_PORT=9999 bash scripts/validate.sh
```

## What The Suite Runs

| Step | Command or behavior | Purpose |
|------|---------------------|---------|
| C clean build | `make clean && make` | Proves the default native build still works |
| Strict C build | `make WARNFLAGS=...` | Catches warning regressions under the project strict-warning set |
| Area validation mode | `cd area && ../merc --check-area` | Boots the world database and exits without listening on a port |
| Optional smoke | `timeout 25s ../merc <port>` | Confirms the server can start and remain alive briefly |
| Python syntax | `python -m py_compile ...` | Catches import and syntax errors in admin/helper scripts |
| Legacy area checks | `check_parser.py`, `check_exits.py`, `check_resets.py`, `check_shops.py` | Validates basic parser counts and cross-reference integrity |
| Area-health lint | `scripts/area_lint.py --fail-on critical` | Catches structural area issues with severity tiers |
| Unit tests | `python -m unittest discover -s tests` | Exercises area-health output and web-admin API behavior |
| Whitespace check | `git diff --check` | Catches trailing whitespace and patch formatting problems |

## Focused Commands

Load all area files without opening a socket:

```bash
cd area
../merc --check-area
```

Run only area-health lint:

```bash
python scripts/area_lint.py --fail-on critical --limit 20
```

Emit full JSON for tooling:

```bash
python scripts/area_lint.py --json > area-health.json
```

Fail on warnings too when doing cleanup work:

```bash
python scripts/area_lint.py --fail-on warning --limit 100
```

## Area-Health Severity Model

The linter is intentionally tiered. The repository should stay at zero critical issues. Warnings and info findings are still valuable, but many reflect legacy world-design patterns and can be cleaned up gradually.

Connectivity follows valid exits across area-file boundaries, teleport-room destinations, reset portal objects, movement manipulation objects (`climb`, `crawl`, and `jump`), and active `spec_pet_shop_owner` links to the shop's `vnum + 1` storage room. Rooms whose isolated group is entirely marked jail, private, solitary, implementor-only, or gods-only are reported as informational restricted rooms. Other code-driven transfers and unmarked staging rooms remain warnings because the area data does not prove how players reach them.

The parser accepts the same room-bitvector forms as the C loader, including letters (`DM`), decimal masks (`524`), and additive pipe syntax (`8|4096`). This matters for both connectivity and restriction classification.

Files in `area.lst` that contain only `#HELPS` or `#SOCIALS` are loader data files, not empty world areas, and are excluded from empty-area findings.

### Critical

Critical issues should block build, deploy, or merge decisions.

| Code | Meaning |
|------|---------|
| `missing-area-file` | A `.are` file is listed in `area/area.lst` but does not exist |
| `area-parse-error` | The Python area parser failed while reading an area file |
| `duplicate-vnum` | A mob, object, or room vnum is defined more than once |
| `exit-target-missing` | A room exit points to a positive room vnum that is not loaded |

### Warning

Warnings usually indicate bad data or design drift. They should be reviewed before large content releases.

| Code | Meaning |
|------|---------|
| `unparsed-area` | A listed file did not produce an area record |
| `area-has-no-content` | A file with an `#AREA` header has no parsed mobs, objects, or rooms |
| `disconnected-area-rooms` | An area spans more than one disconnected travel group after known exits, teleports, portals, and travel objects are included |
| `exit-target-invalid` | A room exit uses zero or another unsupported non-positive destination |
| `mob-level-outlier` | A mob level is outside the expected 0 to 100 range |
| `object-level-outlier` | A takeable object's level is outside the expected `-1` to 100 range; `-1` derives level from its carrier |

### Info

Info findings are cleanup candidates and are not deployment blockers by default.

| Code | Meaning |
|------|---------|
| `area-has-no-rooms` | An `#AREA` file intentionally contains mobs or objects but no rooms |
| `exit-placeholder` | A descriptive, non-traversable exit deliberately uses destination `-1` |
| `restricted-isolated-rooms` | A disconnected group is entirely protected by jail/private/solitary/staff-only room flags and is intentionally kept visible for review without warning severity |
| `one-way-exit` | A room exits to another room without a direct reverse exit |
| `mob-has-no-spawn` | A mob exists in area data but has no reset spawn room |
| `object-has-no-source` | An object has no room or spawned-mobile source, including through its full container-reset chain |
| `static-object-level-outlier` | A non-takeable scenery object has an unusual but gameplay-irrelevant level |

## Current Disconnected-Room Review

The August 2026 baseline is 99 listed area entries, 2,336 mobiles, 3,551 objects, and 7,781 rooms, with 0 critical, 11 warning, and 1,565 informational findings. The topology review reduced the warning-level baseline from 21 areas to 11 without hiding unexplained rooms. Operational pet storage, hardcoded/private rooms, jails, staff quest staging, and solitary rooms are now inferred or reported at info severity. The broken `#65` self-loop was repaired between `connect.are` and Hell room `#13418`, and Marilyn now uses the pet-shop special required by Solace's bird factory.

The Python tools report 99 entries from `area.lst`, while the native validator reports 94 indexed areas. This is expected: six list entries are help/social data files with no `#AREA` record, leaving 93 world areas, and the C loader adds one generated online-building area at boot.

The remaining warnings have distinct causes and should not be bulk-suppressed:

| Area | Isolated room(s) | Evidence and next decision |
|------|------------------|----------------------------|
| `chess.are` | `24373-24375` | The Joker's Teacup is a closed three-room loop. An older unlisted `c.are` has a teacup object, but the active area has no object, reset, portal, or code path into the loop. Restore the encounter deliberately or remove the stale rooms. |
| `connect.are` | `67`, `68` | Comments identify Consortium-to-Underdark and Istari-to-High-Tower links. `consortium.are` and `istari.are` are not loaded by `area.lst`, so these are currently orphaned connector halves. |
| `grove.are` | `8999` | The room describes a fatal fall but has no entry, exit, deathtrap flag, teleport metadata, reset, or code reference. Decide whether it is a real death destination or dead content. |
| `kerofk.are` | `8774` | The description explicitly calls this an accidental history room. It is unmarked, so random teleport can expose it; mark it restricted if it is builder-only, or document it as an intentional teleport Easter egg. |
| `mid_ruin.are` | `5721-5723`, `5738`, `5700`, `5708`, `5732` | This mixes a rubble-sealed but populated guild wing, a mobile work room, a collapsed-stair trap, and an obsolete pet-store room. Each needs a separate keep/restore/remove decision. |
| `newthalo.are` | `9631`, `9778` | Room `9631` contains a mercenary, but `9630` is not a pet shop and has no pet-shop owner special. Room `9778` describes freefall death but has neither an entry nor a deathtrap flag. |
| `ofcol.are` | `5577` | Ravan's personal hideout contains a pet and explicitly has no exits, but lacks a private or staff-only flag. |
| `prison.are` | `20189` | Flar's personal warehouse has five object resets and no exits or access restriction. |
| `sewer.are` | `7130`, `7301` | Room `7130` describes north/drain travel but defines no exits. Room `7301` is an unfinished Realm of Silence entrance whose two descriptive exits both target `-1`. |
| `underdrk.are` | `25187` | This is an unmarked staging room for two tooth objects and their hidden-mob resets; no runtime code moves those objects elsewhere. |
| `valhalla.are` | `9996-9997`, `9998` | The wedding chapel/garden and Azlyn's room are event or personal spaces with no world entry and no private/staff-only flag. |

Re-run `python scripts/area_lint.py --fail-on warning --limit 100` after each world-design decision. A warning should disappear because a real route or explicit restriction was added, not because its vnum was placed on a silent allowlist.

## Web Admin Integration

The same area-health engine powers:

- the dashboard's Area Health tab
- `GET /api/area_health`
- `scripts/area_lint.py`
- unit tests in `tests/test_area_health.py`

Useful related endpoints:

| Endpoint | Authentication | Purpose |
|----------|----------------|---------|
| `GET /api/area_health` | No | Area-health summary and issues |
| `POST /api/reload` | Yes | Reparse dashboard area data |
| `GET /api/backups` | Yes | List recent `*.tar.gz` backup archives |
| `GET /api/logs` | Yes | Tail the configured log file |
| `WebSocket /ws/logs?x_admin_token=<token>` | Yes | Stream live logs |

Operational endpoints are disabled with HTTP 503 until `WEB_ADMIN_TOKEN` is configured. Once enabled, send it as:

```text
X-Admin-Token: your-token
```

## Backups And Diagnostics

The game has two backup layers:

- Scheduled/admin archives: `backup` and web-admin backup actions create `backups/*.tar.gz` archives from `player/`, then prune archives older than 30 days.
- Per-player snapshots: successful saves write snapshots under `player/versions/<Name>/`, throttled by `PLAYER_SNAPSHOT_MIN_INTERVAL` and capped by `PLAYER_VER_MAX`. `prestore` bypasses throttling for its pre-change safety snapshot and atomically replaces the live file.

The `diagnostics` immortal command shows:

- boot time
- loaded area, room, mob index, and object index counts
- active descriptor count
- character and object list sizes
- active mob count
- next pfile and daily backup times

Use it after deploys, reloads, and backup-related changes.

## CI

`.github/workflows/validate.yml` runs on pushes and pull requests. It:

- installs `build-essential`, `gcc`, `make`, and `libcrypt-dev`
- sets up Python 3.12
- installs `webadmin/requirements.txt` and `scripts/requirements.txt`
- runs `bash scripts/validate.sh`

Keep CI green by keeping local `bash scripts/validate.sh` green before pushing.

## Troubleshooting

### `merc --check-area` fails

Check the final loader output first. This usually means a C loader-level issue: malformed area syntax, missing sections, duplicate runtime assumptions, or code that crashes during `boot_db()`.

### `area_lint.py` reports critical issues

Fix critical issues before treating warnings or info findings. Start with parse errors and duplicate vnums because they can hide later findings.

### PowerShell validation cannot find WSL

Check your distro name:

```powershell
wsl -l -v
```

Then pass it explicitly:

```powershell
.\scripts\validate.ps1 -Distro YourDistroName
```

### Python API tests skip or fail

Install both requirement files into the Python environment you are using:

```bash
python -m pip install -r webadmin/requirements.txt -r scripts/requirements.txt
```

### Backup browser is empty

The web admin lists `*.tar.gz` files under `BACKUP_PATH`, defaulting to `backups`. Trigger a backup from the dashboard or in game with `backup now`, then refresh the Admin panel.

### Logs endpoint returns 403

`WEB_ADMIN_TOKEN` is set. Include `X-Admin-Token` for `GET /api/logs` and `GET /api/backups`; include `x_admin_token` in the live log WebSocket query string.

## Related Documentation

- [Developer Guide](developer-guide.md)
- [Area Building Guide](area-building-guide.md)
- [Hosting Guide](hosting-guide.md)
- [Operator Guide](operator-guide.md)
