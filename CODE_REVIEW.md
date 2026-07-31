# Code Review Status

This file records high-signal review findings and their current status. Use it for bug-hunt context, not as a replacement for the full validation suite in `scripts/validate.ps1` and `scripts/validate.sh`.

## Current Status

No open P1/P2 review findings are documented here.

Before opening a change, run:

```bash
bash scripts/validate.sh
```

On Windows, run:

```powershell
.\scripts\validate.ps1
```

See `wiki/validation-and-area-health.md` for the full validation and area-health runbook.

## Resolved Findings

### Web admin queue processing on Unix builds

- **Previous finding**: the FastAPI web admin queued actions into `area/webadmin.queue`, but the Unix game loop did not process the queue.
- **Current status**: resolved. `game_loop_unix()` now calls `process_web_admin_queue()` before descriptor polling, so Linux and Docker deployments handle queued dashboard commands.

### Double `fclose()` in area loading

- **Previous finding**: `do_areaload()` closed the existence-check handle, loaded the area, then closed the same pointer again.
- **Current status**: resolved. The function now closes only the existence-check handle before calling `load_area_file()`.

### Flood disaster movement guard

- **Previous finding**: flood movement checked the `rand_door` array object instead of verifying that any exits had been collected.
- **Current status**: resolved. The movement code now breaks when no open exits are found and only selects from populated indexes.

## Review Priorities

- Treat `player/` and `gods/` as live data. Do not edit them without explicit permission.
- For C changes, prioritize save/load paths, update loops, command interpretation, combat death paths, and area loading.
- For web-admin changes, check token boundaries, queue-writing behavior, parser reload behavior, and large-file/log handling.
- For area-data changes, run `merc --check-area`, the legacy reference checkers, and `scripts/area_lint.py --fail-on critical`.
