# Times of Chaos Documentation

Welcome to the maintained documentation for Times of Chaos. The current world
inventory is 99 listed area entries, 7,781 rooms, 2,336 mobiles, and 3,551
objects.

## Players

- [Player Guide](player-guide.md) - connection, creation, classes, races,
  movement, combat, leveling, guilds, remorts, equipment, economy, groups,
  quests, Hyrule, saving, and troubleshooting
- [Player Command Reference](player-command-reference.md) - commands grouped by
  purpose with important syntax and restrictions
- [Advanced Gear Comparison](gear-comparison.md) - `compare` focuses,
  percentages, profile inference, modeled stats, and limitations
- [Hyrule: First Quest](hyrule-area.md) - entry/exit, level bands, overworld,
  dungeons, maps, compasses, secrets, bosses, and generated content

## Hosts And Staff

- [Web Admin Guide](web-admin-guide.md) - dashboard authentication, world and
  player inspection, maps, logs, game console, operations, API use, and fixes
- [Hosting Guide](hosting-guide.md) - Docker/native setup, configuration,
  persistence, web API, firewalling, service management, upgrades, backups, and
  troubleshooting
- [Operator Guide](operator-guide.md) - daily checks, diagnostics, planned
  reboot, player restore, moderation, incidents, and maintenance records
- [Security Policy](../SECURITY.md) - Telnet/DES limitations, dashboard exposure,
  token handling, hardening, reporting, and incident response
- [Installation Guide](INSTALLING-ToC-ON-A-RASPBERRY-PI-UBUNTU-WIN10-BASH-SHELL.md)
  - automated Windows, macOS, Linux, and Raspberry Pi setup and launchers

## Developers

- [Developer Guide](developer-guide.md) - architecture, modules, builds, tests,
  extension points, persistence, generated content, debugging, and release
  checklist
- [Contributing](../CONTRIBUTING.md) - focused contribution and review rules
- [Validation And Area Health](validation-and-area-health.md) - full validation,
  linter issue codes, CI, current warning review, and troubleshooting
- [Changelog](../CHANGELOG.md) - notable repository changes
- [Agent Instructions](../AGENTS.md) - repository rules for coding agents

## Area Builders

- [Area Building Guide](area-building-guide.md) - authoritative modern `.are`
  reference, all sections/flags/values, complete template, and validation
- [Hyrule: First Quest](hyrule-area.md) - manifest/generator contract and
  campaign-specific validation
- [Validation And Area Health](validation-and-area-health.md) - parser/reference
  checks and topology/source findings

## Historical Area References

These pages preserve older builder documentation and examples. The modern
[Area Building Guide](area-building-guide.md) is authoritative wherever the
pages disagree.

- [AREAS](AREAS.md)
- [MOBS](MOBS.md)
- [MOB HP And Damage](MOBS-HP-&-DAMAGE.md)
- [OBJECTS](OBJECTS.md)
- [ROOMS](ROOMS.md)
- [RESETS](RESETS.md)
- [SHOPS](SHOPS.md)
- [SPECIALS](SPECIALS.md)
- [HELPS](HELPS.md)
- [Spell Slots](SPELLSLOT.md)
- [Old And New Values](OLD---NEW-VALUES.md)

## Getting Help

Players should use in-game `help`, `commands`, `bug`, `typo`, and `idea` first.
For repository problems, open a GitHub issue with the revision, platform,
reproduction, expected/actual result, and sanitized logs. Report security issues
privately as described in [SECURITY.md](../SECURITY.md); never post passwords,
hashes, tokens, player files, or private logs.
