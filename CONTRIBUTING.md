# Contributing To Times of Chaos

Thank you for improving ToC. This repository mixes a legacy C runtime, mutable
MUD data, generated content, and a Python dashboard, so small changes can cross
more boundaries than their diff suggests.

## Read First

- [Developer Guide](wiki/developer-guide.md)
- [Security Policy](SECURITY.md)
- [Area Building Guide](wiki/area-building-guide.md) for `.are` changes
- [Validation And Area Health](wiki/validation-and-area-health.md)
- [AGENTS.md](AGENTS.md) when using a coding agent

## Development Rules

- Work on a focused branch and keep unrelated cleanup out of the change.
- Do not commit real files from `player/`, `gods/`, `heroes/`, `backups/`, or
  private logs.
- Do not edit production character files as part of development.
- Preserve Latin-1 encoding in `.are` files.
- Do not modify archived `area/korzath2old.are` or
  `area/savedTrinidad.are` as active content.
- Treat `data/hyrule_first_quest.json` and the Hyrule generator as source of
  truth; regenerate the area and include both source and output diffs.
- Preserve save-file, vnum, flag, spell-slot, and enum compatibility unless the
  change includes a reviewed migration.
- Add or update in-game help whenever player syntax or behavior changes.
- Route formatted player output through `send_to_char()` or `page_to_char()`;
  test color-on, color-off, paged, and unpaged display paths.
- Document deployment, API, persistence, or security changes in the appropriate
  maintained guide.

## Build And Test

Linux/macOS/CI:

```bash
bash scripts/validate.sh
```

Windows PowerShell with WSL:

```powershell
.\scripts\validate.ps1
.\scripts\validate.ps1 -RunSmoke
```

Useful focused checks:

```bash
make
cd area && ../merc --check-area && cd ..
python3 check_parser.py
python3 check_exits.py
python3 check_resets.py
python3 check_shops.py
python3 scripts/area_lint.py --fail-on critical --limit 100
python3 -m unittest discover -s tests
git diff --check
```

Add regression coverage proportional to risk. Shared movement, combat,
persistence, extraction, world loading, authorization, and queue changes need
broader validation than a text-only correction.

## Change Checklist

Before requesting review:

1. Re-read the diff from a clean `git status`.
2. Confirm only intended source, generated output, tests, and docs changed.
3. Run focused tests during development and the full validation suite at the
   end.
4. Test invalid input and interrupted/error paths, not only success.
5. Verify player-facing text, in-game help, and documentation agree with code.
6. Verify formatted output with color and paging both enabled and disabled.
7. Explain save/API/world-format compatibility and deployment impact.
8. Include manual verification steps and their result.
9. Note any test that could not run and why.
10. Keep secrets, hashes, player data, and machine-specific paths out of the
   patch.
11. Ensure `git diff --check` is clean.

## Commit And Review Guidance

Use an imperative subject that describes the behavior, for example:

```text
Fix flee handling after fatal movement traps
Document secure dashboard deployment
Regenerate Hyrule dungeon progression
```

In the pull request, lead with the user-visible problem and result. Include:

- scope and motivation
- implementation summary
- risk and compatibility notes
- automated test commands/results
- manual test steps/results
- screenshots only when they help review UI behavior and contain no sensitive
  data
- rollback notes for persistence, world data, or deployment changes

Do not hide unrelated refactors inside a bug fix. Do not reduce area-health
counts by silently suppressing findings; resolve the world design or document
the evidence for an intentional state.

## Reporting Bugs

Include the deployed revision, platform, command or action, expected result,
actual result, repeatability, relevant room/object/mobile vnums, and a sanitized
log excerpt. Never post a password, admin token, password hash, raw player file,
private IP/history data, or unredacted backup.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
