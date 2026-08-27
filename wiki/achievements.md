# Achievement System

Times of Chaos has a permanent, character-based achievement system inspired by
the progression and collection model used by modern MMORPGs. Achievements are
recognition and long-term goals: they award points, dates, and announcements,
but never combat stats or economic rewards.

## Player Commands

| Command | Result |
|---|---|
| `achievements` | Summary, category totals, points, and five newest unlocks |
| `achievements <category>` | One category with requirements and live progress |
| `achievements earned` | Every earned achievement and date |
| `achievements incomplete` | Remaining visible goals and hidden entries |
| `achievements all` | Entire catalog |
| `achievements <words>` | Search keys, titles, and descriptions |

Categories are `character`, `combat`, `quests`, `exploration`, and `hyrule`.
The command accepts normal unambiguous command prefixes, but full category
names are clearest. `score` also shows earned count and achievement points.

An unlock displays its title, description, points, and new total. Other players
in the room see a short announcement. Hidden achievements display a generic
placeholder until earned.

## What Is Tracked

| Category | Milestones |
|---|---|
| Character | Levels 10, 25, 50, and 59; first and fifth remorts; 24 hours and seven days played |
| Combat | 1, 100, 1,000, and 10,000 mobile kills; 1, 25, and 100 qualifying player kills |
| Quests | 1, 10, 50, 100, and 500 completions; streaks of 5 and 10 |
| Exploration | Arrival in Hyrule and discovery of all nine dungeon entrances |
| Hyrule | Signature items, shards, maps, compasses, nine bosses, Ganon, Zelda, and meta completion |

Hyrule's boss achievements correspond to the principal encounter in each First
Quest dungeon. A boss kill awards every non-NPC group member present in the
boss room, not only the character delivering the final blow. Ordinary lifetime
kill progress still belongs to the credited killer.

Maps, compasses, and Triforce shards are remembered when acquired, even if the
item is later spent, dropped, or stored. On migration, currently carried items
are scanned recursively, so items inside bags also count. The Master Sword,
Silver Arrow, and complete Triforce achievements require possession when the
state is evaluated.

## Existing Characters

The first login after upgrading checks facts already present in an old player
file. Existing characters can immediately receive level, remort, play-time,
qualifying player-kill, current quest-streak, and currently owned Hyrule-item
achievements. Their current Hyrule room can also record a matching discovery.

Old player files did not retain lifetime mobile-kill or completed-quest totals.
Those two counters therefore begin when this system first records them. They
are not estimated from session snapshots, because an estimate could award
progress a character did not earn.

## Persistence And Compatibility

Achievement data is stored in the normal player file:

- `Achv <stable-key> <timestamp>` records each unlock by key, not table index.
- `AchKills` and `AchQuests` store lifetime counters introduced by the system.
- `AchExplore`, `AchMaps`, `AchCompass`, and `AchTriforce` store compact Hyrule
  discovery and collection masks.

Missing fields default to zero, so old player files remain valid. Stable string
keys allow catalog entries to move without changing the meaning of saved data.
Unknown retired keys are ignored safely. Achievement state follows ordinary
character save, quit, autosave, snapshot, backup, and restore behavior.

## Developer Notes

The catalog and command live in `src/achievements.c`. `PC_DATA` reserves 64
timestamp slots through `MAX_ACHIEVEMENTS`; the current catalog uses 43. Add a
new entry only with a unique key that will never be repurposed.

Event hooks are intentionally central:

- `fight.c` records NPC deaths and qualifying player-kill milestones.
- `quest.c` records successful quest completions after streak advancement.
- `handler.c` records room entry and item acquisition.
- `update.c`, `act_info.c`, `comm.c`, and `save.c` evaluate state milestones at
  level-up, remort, login, score display, and save.

`achievement_check_state()` is idempotent. Event-only room and boss criteria
unlock only from their event hook; state criteria can be checked repeatedly.
The save writer serializes earned entries by key. The loader resolves each key
back to the current runtime index.

Run the normal native build, CMake build, area validation, and
`python -m unittest tests.test_achievements -v` after changing the catalog or
hooks. The test verifies key uniqueness, catalog capacity, persistence wiring,
and the generated Hyrule boss-to-room contract.
