# Archived One-Off Tools

These scripts are retired history, kept for provenance. Nothing in the runtime,
build, validation suite, or CI references them, and they are not maintained.
Do not treat them as current guidance.

They previously lived in the repository root, where they were easy to mistake
for maintained tooling alongside the four checkers that validation actually
runs (`check_parser.py`, `check_exits.py`, `check_resets.py`, `check_shops.py`,
all still in the root).

| Group | Files | What they were |
|---|---|---|
| Help-file rewriting | `improve_help_pass3.py` … `improve_help_pass18.py`, `improve_help_quality.py`, `fix_help_files.py` | The numbered passes that modernized in-game help entries in `area/*.are`. Their results are already committed. |
| Area repair | `fix_areas.py`, `audit_areas.py`, `apply_all_fixes.py`, `final_scan.py`, `fix_unix.py` | Bulk `.are` auditing and repair from earlier cleanup work. Superseded by `webadmin/area_health.py`, `scripts/area_lint.py`, and the `check_*.py` reference checkers. |
| Typo sweeps | `fix_typos.py`, `scan_typos.py`, `scan2.py` | One-time spelling passes over world and help text. |
| Dashboard prototypes | `middleware.py`, `overwrite_server.py`, `websocket_bridge.py` | Abandoned early web-admin experiments. Superseded by `webadmin/server.py`; `scripts/web_server.py` is the only supported compatibility launcher. |

If you need to run one against current data, copy it out and review it first.
Several perform unbounded global text replacement across `.are` files, which
the [Area Building Guide](../../wiki/area-building-guide.md) explicitly warns
against because it ignores section boundaries. They also predate the Latin-1
encoding rules now documented in [AGENTS.md](../../AGENTS.md).
