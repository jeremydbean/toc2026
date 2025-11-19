# Agent Notes for tocGPT

- **Project**: Text-based MUD (ToC) implemented primarily in C under `src/` with additional area data files under `area/`. Build the `merc` server with `make` (uses GCC `-std=gnu89`, `-O2`, `-fcommon`, `-DROM`, and warning flags) and run `make clean` to remove objects/binary.
- **Runtime entrypoint**: `docker-entrypoint.sh` starts in `/app/area`, ensures writable dirs (`log`, `player`, `backups`, etc.), optionally launches the FastAPI web admin (controlled by `WEB_ADMIN_ENABLED`, `WEB_ADMIN_HOST`, `WEB_ADMIN_PORT`), and finally execs `./merc` on the resolved port or passes through provided commands/ports.
- **Web admin service**: `webadmin/server.py` exposes a FastAPI app with HTML UI plus JSON endpoints to append actions into `/app/area/webadmin.queue` (wizinfo broadcast, immortal command, backup, shutdown). Health endpoint checks `merc` and `uvicorn` processes; log tail endpoint reads `/app/log/toc.log`.
- **Container workflow**: README documents Docker usage—build with `docker build -t toc .` and run with `docker run ... -p 9000:9000` plus volume mounts for `player`, `backups`, and `log`. When launching the web interface, publish it on **port 9001** (replace the old 8000 convention). The server port can be overridden via `PORT`/`MUD_PORT`.
- **Code layout tips**: C headers in `src/` (`merc.h`, etc.) pair with module `.c` files for game logic (combat, skills, magic, saving/loading, etc.). The FastAPI component is Python-only and isolated in `webadmin/`.
- **Folder handling**: Do **not** modify anything under `player/` or `gods/` without explicit permission from the user.

## Compile warning notes
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
- Addressed `-Wconversion` hotspots by using explicit size-aware allocations in `act_info.c` list builders and casting color table updates to `sh_int` in `act_comm.c`.
- Additional `-Wconversion` fixes: clamp practice/remort updates to `sh_int`, keep wimpy assignments explicit, convert bank coin math to long-sized temps, and cast telnet control bytes in `comm.c` to avoid sign-changing char initializers.
- New conversion fixes: clamp training cost deductions in `act_move.c`, cast trap effect fields and guardian hit dice to `sh_int`, switch stealing amounts to `long` with matching formats, and cast remort afflictions to the player flag width.
- Latest pass quiets additional conversion warnings: cast blindness trap effects and mount movement deductions to `sh_int` in `act_move.c`, ensure timers and poisoned drink/food effects in `act_obj.c` store through the narrower fields, and rewrite currency queries to avoid long-to-int/double promotions with integer math guarded by `INT_MAX`.
- Bit-name helpers now take `long` flag parameters to match the character flag storage, eliminating long-to-int conversion warnings in wizstat outputs and database dumps when building with the full `-Wconversion` set.
- Additional conversion cleanup in `act_wiz.c`: clamp trust, stat, resource, and object edits through a shared `clamp_sh_int` helper so wizard-set commands assign within `sh_int` bounds without triggering `-Wconversion`.
- Network I/O pass (`src/comm.c`): validate ports before `htons`, widen descriptor handles to `int`, compute buffer lengths with size-aware casts, and convert string helper lengths to unsigned-safe sizes so the strict warning set builds cleanly under the current flags.
- Began converting loader paths in `src/db.c` to clamp integers before storing in `sh_int` fields, adding reusable `fread_sh_int`/clamp helpers, casting time initialization, and tightening string readers to avoid `getc` truncation and size_t-to-int warnings.
- Strict conversion build (`-Wconversion -Wdouble-promotion` etc.) now reports widespread narrowing warnings in `src/db.c` file readers (vnums, materials, flags, and character/room fields) plus similar reports across `fight.c`, `handler.c`, `magic.c`, `magic2.c`, and `save.c`; these need follow-up clamping/typing passes.

- String safety sweep ongoing: `src/db.c` now uses bounded copies for area file names, socials, default room text, and bug logging, but many legacy `sprintf`/`strcat` sites remain in the stat dump helpers around lines 3800–4150. Future passes should replace those concatenations with `snprintf`/`strlcat` and continue checking other modules.

- String safety refactor log: converted all `sprintf`/`strcpy`/`strcat` calls in `src/act_comm.c` to bounded `snprintf`/`strlcpy`/`strlcat`. Continued updating `src/act_wiz.c` with bounded `snprintf` in room stats, gather messaging, object stats, weapon/armor output, and reboot/shutdown logs. Remaining work: convert the many other `sprintf`/`strcat` sites in `act_wiz.c` (player stats, corpse tools, skill listings, forced command output, backups, etc.) and sweep other `src/*.c` files for legacy string operations.
- String safety refactor log (cont.): replaced the remaining `sprintf`/`strcpy`/`strcat` calls in `src/act_wiz.c` with bounded `snprintf`/`strlcpy`/`strlcat`, covering player stats, force messaging, backup restores, psionic grant parsing, corpse recovery, and transfer helpers. Next steps: continue sweeping other `src/*.c` modules (`quest.c`, `hunt.c`, `act_obj.c`, `magic.c`, `db.c`, `save.c`, `wizlist.c`, etc.) for legacy string operations and convert them to safe equivalents.
- String safety refactor log (cont.): tightened `src/handler.c` money creation logging and condition reporting with `snprintf` and hardened `src/wizlist.c` formatting the wizlist output. Remaining hotspots: extensive `strcat` flag builders in `handler.c` still need conversion to `strlcat`, and other `src/*.c` modules continue to use legacy string routines.
- String safety refactor log (cont.): converted the flag/bit-name builders in `src/handler.c` from repeated `strcat` calls to bounded `strlcat` to keep the static buffers within their 512-byte limits. Remaining sweep: other `src/*.c` modules still contain legacy `sprintf`/`strcpy` usage that needs refactoring.

- String safety follow-up: `src/magic.c` now uses bounded `snprintf`/`strlcat` patterns, but other modules still rely on legacy string routines (`src/db.c`, `src/fight.c`, `src/act_obj.c`, `src/act_info.c`, `src/comm.c`, `src/interp.c`). Continue the buffer safety sweep in those files.

- Next string-safety pass: `src/fight.c`, `src/act_obj.c`, `src/db.c`, and the commented prompt stub in `src/comm.c` still use `sprintf`/`strcat` patterns; convert them to bounded helpers with `sizeof` limits.

- String safety follow-up (latest): `src/act_obj.c` now uses `snprintf` for its remaining formatted messages. Other modules (`src/fight.c`, `src/db.c`, `src/comm.c`, etc.) still contain legacy formatting and need similar treatment. `src/merc.h` prototypes should be alphabetized and audited to ensure every global has a declaration and local helpers have static prototypes where appropriate.
- String safety follow-up (current run): began converting `src/db.c` to bounded `snprintf`/`strlcat` patterns (maxload logging and `identify_obj`), but the memory summary and mob stat dump routines still use `sprintf`/`strcat` and need conversion. The `merc.h` prototype audit/sorting remains outstanding.
