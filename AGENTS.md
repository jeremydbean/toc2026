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
1. Complete `-Wconversion` cleanup in `db.c` file loaders (add clamping for all `sh_int` assignments)
2. Add token-based authentication to web admin API endpoints
3. Archive or convert unsafe code in `area/resolve.c`
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
