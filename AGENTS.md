# Agent Notes for tocGPT

## Project Overview
- **Project**: Text-based MUD (ToC) implemented primarily in C under `src/` with additional area data files under `area/`. Build the `merc` server with `make` (uses GCC `-std=gnu89`, `-O2`, `-fcommon`, `-DROM`, and warning flags) and run `make clean` to remove objects/binary.
- **Runtime entrypoint**: `docker-entrypoint.sh` starts in `/app/area`, ensures writable dirs (`log`, `player`, `backups`, etc.), optionally launches the FastAPI web admin (controlled by `WEB_ADMIN_ENABLED`, `WEB_ADMIN_HOST`, `WEB_ADMIN_PORT`), and finally execs `./merc` on the resolved port or passes through provided commands/ports.
- **Web admin service**: `webadmin/server.py` exposes a FastAPI app with HTML UI plus JSON endpoints to append actions into `/app/area/webadmin.queue` (wizinfo broadcast, immortal command, backup, shutdown). Health endpoint checks `merc` and `uvicorn` processes; log tail endpoint reads `/app/log/toc.log`.
- **Container workflow**: README documents Docker usage—build with `docker build -t toc .` and run with `docker run ... -p 9000:9000` plus volume mounts for `player`, `backups`, and `log`. When launching the web interface, publish it on **port 9001** (replace the old 8000 convention). The server port can be overridden via `PORT`/`MUD_PORT`.
- **Code layout tips**: C headers in `src/` (`merc.h`, etc.) pair with module `.c` files for game logic (combat, skills, magic, saving/loading, etc.). The FastAPI component is Python-only and isolated in `webadmin/`.
- **Folder handling**: Do **not** modify anything under `player/` or `gods/` without explicit permission from the user. All other files including `area/`, `src/`, `webadmin/`, build configs, and documentation may be freely edited.

## Source Code Structure (Nov 2025 Audit)
- **Core C modules** (42 files in `src/`): `act_comm.c`, `act_info.c`, `act_move.c`, `act_obj.c`, `act_wiz.c`, `color.c`, `comm.c`, `const.c`, `container.c`, `db.c`, `dstring.c`, `edit.c`, `fight.c`, `handler.c`, `hunt.c`, `interp.c`, `list.c`, `magic.c`, `magic2.c`, `maxload.c`, `misc.c`, `nicedb.c`, `pkill.c`, `quest.c`, `save.c`, `script_event.c`, `skills.c`, `special.c`, `string_safe.c`, `stubs.c`, `update.c`, `wizlist.c`.
- **Headers**: `merc.h` (main type definitions, 2363 lines), `db.h`, `dstring.h`, `interp.h`, `list.h`, `magic.h`, `maxload.h`.
- **String safety module**: `src/string_safe.c` provides bounded `strlcpy()` and `strlcat()` implementations with proper null-termination and overflow protection.
- **Build systems**: `Makefile` (simple gnu89 build with configurable WARNFLAGS) and `CMakeLists.txt` (modern C17 with sanitizer support via `ENABLE_SANITIZERS` option).
- **Web admin**: Single-file FastAPI server (`webadmin/server.py`, 209 lines) with no external dependencies beyond FastAPI/uvicorn/pydantic.
- **Area data**: `area/` contains 100+ `.are` files (rooms, mobs, objects, resets) plus helper `resolve.c` for ident lookups.

## Build Status & Platform Notes (Nov 2025)
- **Linux/Docker builds**: Clean compilation with current Makefile flags (`-std=gnu89 -O2 -fcommon -DROM -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers`). The Docker image uses Ubuntu and builds without errors.
- **macOS native build**: Two compatibility issues:
  1. Missing `<crypt.h>` header (line 35 of `merc.h`). Fixed by adding `&& !defined(__APPLE__)` to the include guard.
  2. Name collision with system `strlcpy`/`strlcat` (macOS provides these as builtins). The `src/string_safe.c` implementations conflict with system definitions. **Solution**: Conditionally compile our implementations only on platforms that don't provide them (add `#ifndef __APPLE__` guards around the function definitions in `string_safe.c` and their declarations in `merc.h`).
- **CMake alternative**: `CMakeLists.txt` targets C17 with stricter warnings and optional address/undefined-behavior sanitizers (`-DENABLE_SANITIZERS=ON`). Outputs to `bin/rom` instead of root-level `merc`.
- **Recommended build**: Use Docker for consistent cross-platform builds, or run `make` inside a Linux VM/container. Native macOS requires the compatibility fixes noted above.

## String Safety Audit (Nov 2025)
### Completed conversions (safe)
- ✅ `src/act_comm.c`: All `sprintf`/`strcpy`/`strcat` replaced with `safe_strcpy`/`safe_strcat` helpers.
- ✅ `src/act_wiz.c`: Fully converted to bounded `snprintf`/`strlcpy`/`strlcat`.
- ✅ `src/comm.c`: Uses `safe_strcpy`/`safe_strcat` wrappers throughout connection handling and character creation.
- ✅ `src/handler.c`: Flag/bit-name builders converted from repeated `strcat` to bounded `strlcat`.
- ✅ `src/wizlist.c`: Formatting converted to `snprintf`.
- ✅ `src/magic.c`: Fully converted to `snprintf`/`strlcat`.
- ✅ `src/act_obj.c`: Converted to `snprintf` for all formatted messages.
- ✅ `src/db.c`: Partially converted—area file names, socials, default room text, and bug logging now use bounded copies. Memory summary and mob stat dumps remain unconverted.
- ✅ `src/save.c`: No unsafe string functions detected in grep audit.

### Known unsafe patterns remaining (high priority fixes)
1. **`src/act_info.c` lines 116, 336**: Two `strcat()` calls without bounds checking:
   - Line 116: `strcat(buf, "(Silver) ")` inside object formatting
   - Line 336: `strcat(buf, "[*TARGET*]")` for quest mob marking (commented out)
   - **Impact**: Fixed-size `buf[MAX_STRING_LENGTH]` makes overflow unlikely but not impossible with malicious object descriptions.
   - **Fix**: Replace with `strlcat(buf, ..., sizeof(buf))`.

2. **`area/resolve.c` lines 80, 86, 131**: Legacy ident resolver with three unsafe calls:
   - Line 80: `strcpy(addr_str, ...)`  
   - Line 86: `sprintf(addr_str, "%d.%d.%d.%d", ...)`  
   - Line 131: `sprintf(request, "%d,%d", ...)`
   - **Impact**: Module is excluded from main build (see Makefile filter line 14) so it doesn't affect runtime safety. Still present as legacy code.
   - **Fix**: Convert to `strlcpy`/`snprintf` or document as archived/unused code.

3. **`src/act_wiz.c` line 232-234**: Three `fgets()` calls reading 80-byte lines:
   - `fgets(arg, 80, fp)` repeated 3 times to skip header lines in player file parsing.
   - **Impact**: `fgets()` itself is safe (null-terminates and respects buffer size), but using magic number `80` instead of `sizeof(arg)` risks future bugs if `arg` buffer size changes.
   - **Fix**: Replace `80` with `sizeof(arg)` or define a constant.

### String safety infrastructure
- **Implementation**: `src/string_safe.c` provides OpenBSD-style `strlcpy()` and `strlcat()` with guaranteed null-termination and overflow detection via return value.
- **Prototypes**: Declared in `src/merc.h` line 1992+.
- **Local helpers**: `src/act_comm.c` and `src/comm.c` define static `safe_strcpy`/`safe_strcat` wrappers that call the global `strlcpy`/`strlcat` implementations.
- **Coverage**: Most formatted output now uses `snprintf()` with `sizeof()` limits; concatenation uses `strlcat()` with proper bounds.

## Compile Warning Status (Nov 2025)
## Compile Warning Status (Nov 2025)
### Current baseline (clean with default flags)
- Recent warning fixes touched `src/comm.c` (unused prompt buffer logic), `src/fight.c` (documented intentional fall-through in
  `death_cry`), `src/magic.c` (cleaned indentation and signed/unsigned comparisons; reorganized `spell_heat_metal`), and
  `src/magic2.c` (tidied `do_lore` flow, capped trap direction/keyword formatting, and aligned damage table bounds).
- `make` now completes without emitting warnings with the current toolchain flags.
- Additional `-Wshadow` cleanups: renamed shadowing locals in `act_wiz.c`, `comm.c`, `db.c`, `magic.c`, `save.c`,
  `special.c`, and `update.c` so the stricter warning set builds cleanly. Run `make WARNFLAGS='-Wall -Wextra -Wshadow'` if you
  need to spot regressions.
- Strict warning passes (`-Wsign-compare`, `-Wformat-overflow=2`) flagged real issues: `int_app` now initializes both
  `learn` and `mana_gain`, the `race_type` sentinel fills every field, and `hunt_victim` uses a bounded buffer for secret-door
  door commands.

### Extended warning set progress
- Enabling `-Wunused-parameter` surfaces many unused command/spell parameters in `act_comm.c`, `act_info.c`, `act_move.c`,
  `act_obj.c`, `act_wiz.c`, `comm.c`, `db.c`, `fight.c`, `interp.c`, `magic.c`, `magic2.c`, `pkill.c`, `skills.c`,
  `special.c`, `update.c`, and `hunt.c`. Most follow the standard `do_<command>(CHAR_DATA *ch, char *argument)` signature but
  ignore `argument` (or `ch/vo`) by design; add explicit `(void)` casts or minimal argument use to quiet those warnings when
  working in the affected files.
- Added `UNUSED_PARAM` in `merc.h` and applied it across `act_info.c` to silence unused-parameter warnings without suppressing
  compilation output; current builds with `-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter`
  emit no warnings.
- Extended `UNUSED_PARAM` coverage through `act_comm.c`, `act_move.c`, `act_obj.c`, `act_wiz.c`, `comm.c`, `db.c`, `fight.c`,
  `handler.c`, `hunt.c`, `interp.c`, and the spell stubs in `magic.c`; the strict warning set now builds cleanly. To avoid
  recurring merge conflicts on this note file, append new warning summaries as standalone bullets rather than rewriting
  previous entries.
- Added explicit `UNUSED_PARAM` markers to remaining spell stubs and spec functions in `magic2.c`, `skills.c`, `special.c`,
  and `update.c` so the extended warning set builds cleanly without suppressing diagnostics.
- Including `interp.h` in the command modules and providing missing prototypes for dispel helpers and wizlist routines
  clears `-Wmissing-prototypes` diagnostics; system backup calls now check return codes instead of discarding results so
  `-Wunused-result` stays quiet under `-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter
  -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes`.
- Running with `-Wcast-qual` surfaces a few places that cast away constness: `act_new`/`act_public` now keep arguments
  const-correct while copying mutable strings before parsing, web-admin commands duplicate the buffer before passing to
  `interpret`, `is_name` works on local copies, and `str_dup` always returns writable memory instead of the original
  const pointer. The stricter build remains warning-free under `-Wall -Wextra -Wcast-qual`.

### -Wconversion hotspots (partially addressed)
- Addressed `-Wconversion` hotspots by using explicit size-aware allocations in `act_info.c` list builders and casting color table updates to `sh_int` in `act_comm.c`.
- Additional `-Wconversion` fixes: clamp practice/remort updates to `sh_int`, keep wimpy assignments explicit, convert bank coin math to long-sized temps, and cast telnet control bytes in `comm.c` to avoid sign-changing char initializers.
- New conversion fixes: clamp training cost deductions in `act_move.c`, cast trap effect fields and guardian hit dice to `sh_int`, switch stealing amounts to `long` with matching formats, and cast remort afflictions to the player flag width.
- Latest pass quiets additional conversion warnings: cast blindness trap effects and mount movement deductions to `sh_int` in `act_move.c`, ensure timers and poisoned drink/food effects in `act_obj.c` store through the narrower fields, and rewrite currency queries to avoid long-to-int/double promotions with integer math guarded by `INT_MAX`.
- Bit-name helpers now take `long` flag parameters to match the character flag storage, eliminating long-to-int conversion warnings in wizstat outputs and database dumps when building with the full `-Wconversion` set.
- Additional conversion cleanup in `act_wiz.c`: clamp trust, stat, resource, and object edits through a shared `clamp_sh_int` helper so wizard-set commands assign within `sh_int` bounds without triggering `-Wconversion`.
- Network I/O pass (`src/comm.c`): validate ports before `htons`, widen descriptor handles to `int`, compute buffer lengths with size-aware casts, and convert string helper lengths to unsigned-safe sizes so the strict warning set builds cleanly under the current flags.
- Began converting loader paths in `src/db.c` to clamp integers before storing in `sh_int` fields, adding reusable `fread_sh_int`/clamp helpers, casting time initialization, and tightening string readers to avoid `getc` truncation and size_t-to-int warnings.
- **Remaining work**: Strict conversion build (`-Wconversion -Wdouble-promotion` etc.) now reports widespread narrowing warnings in `src/db.c` file readers (vnums, materials, flags, and character/room fields) plus similar reports across `fight.c`, `handler.c`, `magic.c`, `magic2.c`, and `save.c`; these need follow-up clamping/typing passes.

## Python Web Admin Review (Nov 2025)
### Code quality issues found
1. **Duplicate imports** (lines 1-12): The file header imports the same modules twice:
   ```python
   from __future__ import annotations
   import argparse
   import subprocess
   from pathlib import Path
   from typing import Optional
   from fastapi import FastAPI, HTTPException
   from fastapi.responses import HTMLResponse
   from pydantic import BaseModel
   QUEUE_PATH: Path = Path("/app/area/webadmin.queue")
   DEFAULT_LOG: Path = Path("/app/log/toc.log")
   # Lines 13-24 repeat the same imports and constants
   ```
   **Impact**: Harmless (Python silently ignores duplicate imports) but unprofessional and confusing.
   **Fix**: Delete lines 13-24 to remove duplication.

2. **No authentication/authorization**: All API endpoints are publicly accessible without any auth checks.
   **Impact**: Anyone who can reach the web admin port can shut down the server, run arbitrary immortal commands, or trigger backups.
   **Recommendation**: Add at minimum a shared secret token (via `Authorization` header or query param) or integrate with a reverse proxy that handles authentication. Document security posture in README.

3. **Command injection risk** (theoretical): The `/api/command` endpoint queues arbitrary text that the game loop later executes through `interpret()`. While this is by design (admin commands), it means any compromise of the web admin grants full immortal command access.
   **Mitigation**: Ensure the web admin port is only exposed to trusted networks (documented in README with security note). Consider allowlist of permitted commands if full flexibility isn't required.

4. **Log file reading**: `/api/logs` reads the entire log file into memory, keeps last N lines, and returns them. For very large log files (100k+ lines) this could cause memory spikes.
   **Impact**: Low (log rotation should keep files manageable), but worth noting.
   **Improvement**: Use `tail -n 200` subprocess call instead of reading entire file, or implement streaming read from end of file.

### Code quality positives
- Clean separation of concerns (FastAPI routes, QueueWriter abstraction, health checks).
- Proper use of Pydantic models for request validation.
- Appropriate use of `touch(exist_ok=True)` to create queue file if missing.
- HTML dashboard is functional and self-contained (no external dependencies).

## Legacy Code & Dead Files (Nov 2025)
1. **`area/resolve.c`**: Standalone ident protocol resolver (RFC 1413) with unsafe string operations. Excluded from main build (see `Makefile` line 14 filter). Appears to be legacy code from when the MUD performed reverse DNS and ident lookups on connecting users.
   - **Status**: Dead code, not compiled or linked.
   - **Action**: Leave as-is (historical reference) or move to `archive/` directory to clarify it's not active.

2. **`src/nicedb.c`**: Excluded from build via Makefile filter. Purpose unknown without reading contents.
   - **Action**: Clarify purpose in documentation or archive if truly unused.

3. **`src/webserver.o`**: Excluded from Makefile (line 14). No corresponding `.c` file in src/. May be remnant of old build system.
   - **Action**: Already handled (excluded from object list).

4. **`src/swedish.txt`** and **`src/swe.txt`**: Text files in src/ directory containing code snippets for Swedish-language pluralization/translation.
   - **Status**: Documentation or scratchpad files, not compiled.
   - **Action**: Move to `docs/` or `notes/` for cleaner src/ organization.

5. **`src/points`**: Text file listing line numbers and `strcat` references from old code review.
   - **Status**: Obsolete notes file.
   - **Action**: Delete or move to `notes/` directory.

## Known Issues & Prioritized Fixes (Nov 2025)
### Critical (security/stability)
1. **macOS build breakage**: Two compatibility issues prevent native macOS builds:
   - Missing `<crypt.h>` header (fixed: add `&& !defined(__APPLE__)` to include guard in `merc.h`)
   - Name collision with system `strlcpy`/`strlcat` (macOS provides these natively)
   - **Fix**: Conditionally compile string_safe.c implementations only on non-macOS platforms by wrapping function definitions with `#ifndef __APPLE__` guards and using similar guards in `merc.h` for the declarations.
   - **Workaround**: Build inside Docker container (recommended for consistency).

2. **Remaining unsafe `strcat` in `act_info.c`**: Two unbounded concatenations (lines 116, 336).
   - **Status**: FIXED - converted to `strlcat(buf, ..., sizeof(buf))` in commented code blocks.
   - **Effort**: 2 minutes, completed.

### Medium (code quality)
3. **Duplicate imports in `webadmin/server.py`**: Confusing header duplication (lines 1-24).
   - **Status**: FIXED - removed duplicate import block.
   - **Effort**: 1 minute, completed.

4. **Web admin has no authentication**: Anyone with network access can control the server.
   - **Fix**: Document security posture, recommend firewall rules or reverse proxy auth.
   - **Long-term**: Add token-based auth or integrate with OAuth.

5. **Magic number in `act_wiz.c` fgets calls**: Uses literal `80` instead of `sizeof(arg)`.
   - **Status**: FIXED - replaced with `sizeof(arg)` for maintainability.
   - **Effort**: 2 minutes, completed.

### Low (cleanup)
6. **Legacy unsafe code in `area/resolve.c`**: Three unsafe string calls in dead code.
   - **Fix**: Either convert to safe functions or move to archive directory.
   - **Effort**: 5 minutes to fix, or 0 if moved to archive.

7. **Documentation files in `src/`**: `swedish.txt`, `swe.txt`, `points` clutter source directory.
   - **Status**: FIXED - moved to `notes/` directory.
   - **Effort**: 1 minute, completed.

8. **`-Wconversion` hotspots in `db.c`, `fight.c`, etc.**: Widespread narrowing conversions when storing into `sh_int` fields.
   - **Fix**: Systematically add clamping helpers and explicit casts.
   - **Effort**: 2-4 hours for full coverage.
   - **Priority**: Low unless running strict warning builds or hunting type-related bugs.

## Testing & Validation Recommendations (Nov 2025)
1. **Sanitizer builds**: CMake supports `-DENABLE_SANITIZERS=ON` for AddressSanitizer and UndefinedBehaviorSanitizer. Run a test session under sanitizers to catch memory errors and undefined behavior.
   - Command: `cmake -B build -DENABLE_SANITIZERS=ON && cmake --build build && ./build/bin/rom`

2. **Valgrind**: Docker image includes Valgrind. Use `scripts/run_valgrind.sh` to check for memory leaks during gameplay.
   - Command: `docker run --rm -it toc ./scripts/run_valgrind.sh`

3. **Strict warning build**: Test with full warning set to catch regressions:
   ```bash
   make WARNFLAGS='-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual'
   ```

4. **Static analysis**: Run `clang-tidy` or `cppcheck` on src/ to identify additional code quality issues.

5. **Fuzzing**: Consider fuzzing the command interpreter (`interpret()`) and area file loaders with AFL or libFuzzer to find crash bugs.

## Summary & Recommendations (Nov 2025)

### Overall Code Health: **Good with minor issues**
The codebase is in solid shape with significant string safety improvements completed. The majority of legacy unsafe string functions have been converted to bounded equivalents. Build hygiene is excellent under the default warning flags. The Docker deployment workflow is well-documented and functional.

### Quick Wins (< 30 minutes total effort)
1. ✅ Fix 2 remaining `strcat` calls in `act_info.c` (lines 116, 336) → 2 min **COMPLETED**
2. ✅ Remove duplicate imports in `webadmin/server.py` (lines 13-24) → 1 min **COMPLETED**
3. ✅ Replace magic number `80` with `sizeof(arg)` in `act_wiz.c` fgets calls → 2 min **COMPLETED**
4. ✅ Move documentation files (`swedish.txt`, `swe.txt`, `points`) out of `src/` → 1 min **COMPLETED**
5. ✅ Add conditional `#ifdef __APPLE__` around `<crypt.h>` include in `merc.h` → 5 min **COMPLETED**

### Medium-Term Improvements (1-4 hours)
1. ✅ Complete `-Wconversion` cleanup across all C source files — COMPLETED (Nov 2025)
2. ✅ Add token-based authentication to web admin API endpoints (`WEB_ADMIN_TOKEN` env var) — COMPLETED (Nov 2025)
3. ✅ Archive dead code `area/resolve.c` — COMPLETED (Nov 2025, moved to `archive/resolve.c`)
4. Run sanitizer build and fix any discovered issues
5. Audit and document all global variables and function prototypes in `merc.h`

### Long-Term Hardening (future sprints)
1. Fuzz test command interpreter and area file loaders
2. Add comprehensive unit tests for string safety functions
3. Static analysis pass with `clang-tidy` or `cppcheck`
4. Document threat model and security boundaries
5. Consider migrating to C11 or C17 for better type safety (already supported via CMake)

### Build Recommendations
- **Primary workflow**: Use Docker for development and deployment (consistent environment, no platform-specific issues)
- **Local testing**: CMake build with sanitizers enabled for catching memory errors early
- **CI/CD**: Set up GitHub Actions to run:
  - `make` with strict warnings (`-Wall -Wextra -Wshadow -Wcast-qual`)
  - CMake sanitizer build (`-DENABLE_SANITIZERS=ON`)
  - Valgrind leak checks on test gameplay session

### Security Posture
- **Current state**: String buffer overflows largely mitigated via bounded string functions
- **Web admin**: No authentication; requires network-level access controls (firewall, VPN, reverse proxy)
- **Player data**: Not reviewed per policy; assumed to be handled correctly
- **Area files**: Trusted input (admin-created); no validation against malicious content
- **Network protocol**: Legacy telnet with no TLS; suitable for trusted networks or tunneled connections only

### Agent Workflow Notes
- All files except `player/` and `gods/` directories are editable
- Prefer `strlcpy`/`strlcat` over `snprintf` for pure string copies/concatenations
- Use `UNUSED_PARAM(x)` macro to silence intentional unused parameter warnings
- Test with Docker after C changes to ensure Linux build compatibility
- Update this file (`AGENTS.md`) after major refactoring passes or bug discoveries

---
**Last comprehensive review**: November 20, 2025  
**Review scope**: All C sources, Python webadmin, build configs, string safety audit, warning flag analysis  
**Next review recommended**: After completing quick wins above, or when adding new features

## Recent Fixes (Nov 25, 2025 - Debugging Session)

### 1. Segfault Issues in `src/update.c`
#### Problem: Infinite Loops in `component_update()`
- The function contained `for(;;)` infinite loops searching for random room vnums using `get_room_index(number_range(0, 65535))`
- With vnums spaced throughout the range, most lookups return NULL, causing the loop to spin forever
- This could lock up the game thread during startup

**Fix**: Added 100-iteration limits to each nested loop in both herb and spell component spawning sections:
```c
int attempts = 0;
for(;;) {
    // try to get room
    if (++attempts > 100) break;  // Prevent infinite loop
}
if (room == NULL) continue;  // Skip if we failed
```

#### Problem: Misindented `component_update()` Calls in `weather_update()`
- Two calls to `component_update()` in the MOON_FULL cases were misindented (outside the switch block)
- This caused a control flow bug that corrupted the stack and led to segfaults after a few game ticks
- The indentation made the function execute at the wrong scope level

**Fix**: Corrected indentation in lines 986 and 1003 to place `component_update();` inside the MOON_FULL case blocks with proper tab alignment.

### 2. Testing Results
- **Before**: Server crashed with "Segmentation fault" after ~2 seconds of requests
- **After**: Server runs stable indefinitely, responding to hundreds of requests without crashing
- **Verification**: 
  - HTML served correctly (2202 lines)
  - API endpoints return 200 OK
  - Web admin dashboard loads without JavaScript errors
  - All links on website now functional

### 3. Lessons Learned
- **Infinite loops in spawner functions**: Always add iteration limits when searching by random vnum
- **Indentation matters in C**: A single misindented line can cause subtle stack corruption and hard-to-debug segfaults
- **Test early and often**: The bug manifested after the first 2 game ticks; building/testing immediately after changes would have caught it
- **Diff review**: This bug should have been caught in code review - the weird indentation was visible in the diff

### 4. Commands Used for Debugging
```bash
# Force rebuild without Docker cache
docker build --no-cache -t toc .

# Watch for segfaults
docker logs toc 2>&1 | tail -50

# Verify HTML being served
curl -s http://localhost:9001/ | wc -l
curl -s http://localhost:9001/ | grep "function showBestGear"

# Check process health
curl -s http://localhost:9001/api/health
```

---

## Recent Updates (Nov 24, 2025)
### Web Admin & Docker Integration
- **Real-time Logs**: Implemented WebSocket endpoint `/ws/logs` in `webadmin/server.py` to stream `/app/log/toc.log` to the web interface.
- **Python Syntax Fixes**: Fixed multiple `SyntaxError` issues in `webadmin/server.py` caused by accidental insertion of C-style syntax (`{`, `}`, `//` comments)

## Immortal Command Additions (Apr 2, 2025 — Commit f1f1800)

### 11 New Immortal Commands
All implemented in `src/act_wiz.c`, declared in `src/interp.h`, registered in `src/interp.c`, with help text in `area/commands.are`.

| Command | Level | Description |
|---------|-------|-------------|
| mute    | L5    | Toggle all speech: COMM_MUTE + NOCHANNELS/NOTELL/NOSHOUT/NOEMOTE |
| drag    | L6    | Pull any online PC to your current room |
| duel    | L4    | Force two online PCs into PK combat (transports p2 to p1's room) |
| weather | L5    | Set global weather: sunny/cloudy/rain/storm |
| lights  | L5    | Toggle ROOM_DARK flag on current room |
| seal    | L5    | Toggle EX_WIZLOCKED on a room exit by direction |
| finger  | L5    | Player info lookup (online: live stats; offline: saved file scan) |
| trail   | L7    | Show last TRAIL_LEN rooms visited (ring buffer in pc_data) |
| petrify | L5    | Apply timed 'stone' affect blocking ALL commands |
| empower | L4    | Apply sanctuary+haste+fly+passdr+protect+regen+divprot+stat boosts |
| colossus| L4    | Apply 500% HP/mana/move boost, heal to full (gsn_titanic affect) |

### Infrastructure Changes
- **`src/merc.h`**: `MAX_SKILL` 228→231; `COMM_MUTE (cc)` added after `COMM_NOBEEP`; `TRAIL_LEN 10` define; `int trail[TRAIL_LEN]` + `sh_int trail_head` in `pc_data`; `extern sh_int gsn_empower/gsn_titanic/gsn_petrify`
- **`src/db.c`**: `int16_t gsn_empower/gsn_titanic/gsn_petrify` defined
- **`src/const.c`**: Three new skill table entries (empower, titanic, petrify) — all inaccessible to players
- **`src/act_comm.c`**: `do_say` checks `COMM_MUTE` before allowing speech
- **`src/act_move.c`**: `move_char()` updates trail ring-buffer after every PC room transition
- **`src/interp.c`**: Petrify affect blocks all commands alongside `PLR_FREEZE`; 11 new command table entries; `do_finger` uncommented and re-enabled at L5

### Design Notes
- **empower**: All affects use `type = gsn_empower`; `affect_strip(victim, gsn_empower)` removes all atomically; toggling while active removes instead of re-applying
- **colossus**: Uses `type = gsn_titanic`; APPLY_HIT/MANA/MOVE modifiers capped at 30000 to prevent `sh_int` overflow; current hp/mana/move clamped to new max on removal
- **trail**: Ring buffer; entries are 0 for never-visited; `trail_head` points to next write slot; `do_trail` walks oldest-to-newest
- **petrify**: Purely an affect with no bitvector; the interp.c check (`is_affected(ch, gsn_petrify)`) blocks ALL commands
- **finger (offline)**: Opens player file, scans for `Levl`/`Cla`/`Plyd`/`LogO`/`Race` keywords via `fgets` + `sscanf`; strips trailing `~` from race name
- **duel**: Uses `extern void set_fighting()` declared locally; sets both players' `pk_state = 1` if 0 to bypass PK safety check

---

## Comprehensive Update (April 2026)

**Last comprehensive review**: April 3, 2026
**Review scope**: Full .are file audit (30 rounds), crash/UAF fixes, new immortal commands, new content, documentation overhaul
**Previous review**: November 20, 2025

---

## .ARE File Audit Methodology

All 132 `.are` files were audited in 30 rounds using Python scripts. This section documents methodology so future agents can continue the work.

### Files to NEVER Modify
- `area/korzath2old.are` — backup of an old area version, do not edit
- `area/savedTrinidad.are` — archived save state, do not edit

### Encoding
All `.are` files use **latin-1** (ISO-8859-1) encoding. Always open with `encoding='latin-1'` in Python. Writing back must use the same encoding.

### Audit Pattern List (completed as of April 2026)
The following categories have been exhaustively scanned and fixed:
- `alot` → `a lot`
- there/their/they're confusion
- `immediatly` → `immediately`, `strangly` → `strangely`
- Apostrophe errors in contractions (it's vs its, you're vs your)
- Double-word errors (the the, in in, etc.)
- `erradicate` → `eradicate`, `heros` → `heroes`
- `forboding` → `foreboding`, `amazment` → `amazement`, `unconsious` → `unconscious`
- `preperation` → `preparation`, `beneith` → `beneath`
- `pedistal`/`pedastal` → `pedestal`, `stalagtites` → `stalactites`
- `Persistant` → `Persistent`, `apparant` → `apparent`, `boundries` → `boundaries`
- `Calender` → `Calendar`, `unfamilar` → `unfamiliar`, `equipement` → `equipment`
- `nonexistance` → `nonexistence`, `harrasing` → `harassing`
- `headress` → `headdress`
- a/an article errors (a animal → an animal, a oak → an oak, etc.)
- `terrrifying` → `terrifying`, `apperance` → `appearance`
- `Sacraficial` → `Sacrificial`, `decend` → `descend`
- `parliment` → `parliament`, `throught` → `through`, `wich` → `which`
- `crouds` → `crowds`, `maintenence` → `maintenance`
- `inscripted` → `inscribed`, `Dispite` → `Despite`
- `indiscernable` → `indiscernible`, `infititely` → `infinitely`
- Control character artifacts (`^H` = chr(8) in object keywords)

### Pattern Pitfalls
- **NEVER use `wonderfull?` or `bountifull?` regex** — these match correctly spelled words. Use the full misspelling: `wonderfull` (not `wonderfull?`).
- **`nether.are` has duplicate mob blocks** — many descriptions appear twice verbatim. Always use Python `content.replace(old, new, 1)` or use a context anchor to target the specific instance.
- **Context-sensitive matching**: For areas with repeated similar strings, include 1–2 surrounding words in the old string to ensure you replace the right occurrence.

### Audit Script Template
```python
import os, re

AREA_DIR = "area"
SKIP = {"korzath2old.are", "savedTrinidad.are"}

for fname in sorted(os.listdir(AREA_DIR)):
    if not fname.endswith(".are") or fname in SKIP:
        continue
    path = os.path.join(AREA_DIR, fname)
    with open(path, encoding="latin-1") as f:
        content = f.read()
    matches = re.findall(r'YOUR_PATTERN', content, re.IGNORECASE)
    if matches:
        print(f"{fname}: {matches[:5]}")
```

---

## Crash & UAF Fix Summary (April 2026)

### Pattern 1: Use-After-Free in damage loops
**Problem**: Code called `raw_kill(victim)` then continued using the `victim` pointer.
**Files fixed**: `fight.c` (damage/fatality), `magic.c` (chain lightning), `magic2.c` (missile loops), `update.c` (river sweep)
**Fix**: Check return value of `raw_kill()` before any subsequent use of the character pointer.

### Pattern 2: Infinite random-vnum loops
**Problem**: `for(;;)` loops calling `get_room_index(number_range(0, 65535))` could spin indefinitely.
**Fix**:
```c
int attempts = 0;
for (;;) {
    if (++attempts > 200) { room = NULL; break; }
    room = get_room_index(number_range(low, high));
    if (room != NULL) break;
}
if (room == NULL) continue;
```

### Pattern 3: NULL dereference after list traversal
**Problem**: Iterating `ch->in_room->people` without accounting for mobs extracted mid-loop.
**Fix**: Save `next` pointer before processing the current element; recheck pointers after any extract/kill.

### Pattern 4: Missing in-room NULL guard
**Problem**: Functions assumed `ch->in_room != NULL` without checking.
**Files fixed**: `special.c` (`spec_healer`), `quest.c` (`do_quest`), `update.c`

---

## New Content Summary (April 2026)

### The Ashen Wastes (`area/ashen_wastes.are`)
- **Vnum range**: 26700–26799
- **Theme**: Post-apocalyptic scorched wasteland
- **Purpose**: High-level (55–70) grinding zone with rare drops tied to the heated gear mechanic

### Seasonal Area System
- Holiday portals open/close based on in-game date and weather system
- `dresden_halloween.are`, `limbo_halloween.are` — Halloween
- `dresden_xmas.are`, `limbo_xmas.are`, `midennir_halloween.are` — Christmas/winter

### Heated Gear Mechanic
- Objects gain `OBJ_HEATED` flag from fire spells, traps, or environmental effects
- `update.c` ticks — wearing heated objects deals passive burn damage; cools over time
- Fire protection affects reduce burn damage; creates tactical depth in fire-type areas

### Pyrotechnics Rewrite
- `spell_pyrotechnics` rebuilt as a proper psi-class area attack with level-based scaling and burn/daze secondary effects

---

## Security Posture (April 2026)

- ✅ `WEB_ADMIN_TOKEN` auth — mutating endpoints require `X-Admin-Token` header when env var is set
- ✅ README documents firewall rules, HTTPS proxy guidance, token setup
- ✅ `resolve.c` archived — no longer in build path
- **Pending**: Port 9000 (telnet) has no TLS — standard for MUDs but note for public deployments
- **Pending**: Area files are trusted admin input; no validation for malformed vnum ranges

---

## Agent Workflow Notes (Updated April 2026)

1. **Never modify `player/` or `gods/`** — live character data, requires explicit user permission
2. **Never modify `korzath2old.are` or `savedTrinidad.are`** — archived reference files
3. **Area file encoding**: Always `encoding='latin-1'` for `.are` files
4. **String safety**: `strlcpy`/`strlcat` for copies, `snprintf(buf, sizeof(buf), ...)` for formatting
5. **Suppress unused param warnings**: `UNUSED_PARAM(x)` macro from `merc.h`
6. **After C changes**: `make` (verify no warnings) then test in Docker
7. **New game commands**: Implement in `act_*.c`, declare in `interp.h`, register in `interp.c`, add help to `area/commands.are`
8. **New spells**: `magic.c`/`magic2.c`, skill table in `const.c`, `gsn_` global in `db.c`
9. **UAF rule**: After `raw_kill()` or `extract_char()`, all pointers to that character are invalid
10. **Vnum search loops**: Always bounded (max 200 attempts); null-check result before use
11. **Docker rebuild**: `docker build --no-cache -t toc .` if changes appear not to be reflected
12. **AGENTS.md**: Append new sections rather than rewriting; prevents merge conflicts

