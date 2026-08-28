# Code Review Status

This file records high-signal review findings and their current status. Use it
for bug-hunt context, not as a replacement for the full validation suite in
`scripts/validate.ps1` and `scripts/validate.sh`. The maintained review workflow
and risk checklist are in `wiki/developer-guide.md`; security findings follow
`SECURITY.md`.

## Current Status

No release-blocking review finding is currently tracked in this file. That is a
recordkeeping statement, not proof that the legacy code has no defects. New
findings should include severity, player impact, reproduction, affected
revision, fix status, and regression coverage.

Before opening a change, run:

```bash
bash scripts/validate.sh
```

On Windows, run:

```powershell
.\scripts\validate.ps1
```

See `wiki/validation-and-area-health.md` for the full validation and area-health runbook.

The August 2026 parsed-world baseline is 99 listed area entries, 2,336 mobiles,
3,557 objects, and 7,781 rooms, with 0 critical, 11 warning, and 1,571
informational area-health findings.

## Resolved Findings

### Password-bearing command logging

- **Previous finding**: `remort` and immortal `resetpwd` were registered as
  `LOG_ALWAYS`, exposing plaintext password arguments to command logs and snoop
  output. The incomplete `delet` guard could also log an accidentally supplied
  password.
- **Current status**: resolved. Every password-bearing command and deletion
  guard is `LOG_NEVER`, with a regression test in
  `tests/test_sensitive_command_logging.py`.

### Web admin queue processing on Unix builds

- **Previous finding**: the FastAPI web admin queued actions into `area/webadmin.queue`, but the Unix game loop did not process the queue.
- **Current status**: resolved. `game_loop_unix()` now calls `process_web_admin_queue()` before descriptor polling, so Linux and Docker deployments handle queued dashboard commands.

### Double `fclose()` in area loading

- **Previous finding**: `do_areaload()` closed the existence-check handle, loaded the area, then closed the same pointer again.
- **Current status**: resolved. The function now closes only the existence-check handle before calling `load_area_file()`.

### Flood disaster movement guard

- **Previous finding**: flood movement checked the `rand_door` array object instead of verifying that any exits had been collected.
- **Current status**: resolved. The movement code now breaks when no open exits are found and only selects from populated indexes.

### Paged output exposed raw color tokens

- **Previous finding**: `page_to_char()` stored canonical `{HH}` game-color
  tokens and `show_string()` wrote them directly, bypassing the conversion used
  by immediate output. Commands such as `achievements` displayed raw `{0D` and
  `{0F` text whenever paging was enabled.
- **Current status**: resolved. Paged text is color-converted once before it is
  stored, color-disabled players receive plain text, and achievement regression
  coverage verifies the pager path and compact default summary.

## Review Priorities

- Treat `player/` and `gods/` as live data. Do not edit them without explicit permission.
- For C changes, prioritize save/load paths, update loops, command interpretation, combat death paths, and area loading.
- For web-admin changes, check token boundaries, queue-writing behavior, parser reload behavior, and large-file/log handling.
- For area-data changes, run `merc --check-area`, the legacy reference checkers, and `scripts/area_lint.py --fail-on critical`.
