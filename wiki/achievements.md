# Achievement System

Times of Chaos has a permanent, character-based achievement system inspired by
the progression and collection model used by modern MMORPGs. Achievements are
recognition and long-term goals: they award points, dates, and announcements,
but never combat stats or economic rewards.

## Player Commands

| Command | Result |
|---|---|
| `achievements` | Compact two-column category totals, points, and five newest unlocks |
| `achievements <category>` | One category with requirements and live progress |
| `achievements earned` | Every earned achievement and date |
| `achievements incomplete` | Remaining visible goals and hidden entries |
| `achievements all` | Entire catalog |
| `achievements <words>` | Search keys, titles, and descriptions |

Categories are `character`, `combat`, `encounters`, `quests`, `exploration`,
`collection`, `crafting`, `misadventure`, and `hyrule`. The command accepts
normal unambiguous command prefixes, but full category names are clearest.
`score` also shows earned count and achievement points.

The normal summary is sized to fit the default page length. Longer category,
filter, and search results use the standard game pager and honor each player's
color and scroll settings.

An unlock displays its title, description, points, and new total. Other players
in the room see a short announcement. Hidden achievements display a generic
placeholder until earned.

## What Is Tracked

| Category | Milestones |
|---|---|
| Character | Levels 5, 10, 15, 20, 25, 30, 40, 50, 55, 58, and 59; first and fifth remorts; 24 hours and seven days played |
| Combat | 1, 100, 1,000, and 10,000 mobile kills; 1, 25, and 100 qualifying player kills; a hidden Farslay feat |
| Encounters | Seventeen named endgame bosses plus five-boss and full-catalog meta achievements |
| Quests | 1, 10, 50, 100, 250, and 500 completions; streaks of 5, 10, and 25; rush, final-minute, gamble-win, and keepsake feats |
| Exploration | Arrival in Hyrule and discovery of all nine dungeon entrances |
| Collection | Seventeen rare or special-source relics plus 5, 10, and 17-relic metas |
| Crafting | Brewing, concocting, scribing, the hidden Farslay-scroll recipe, and a crafting meta |
| Misadventure | 1, 10, and 100 deaths; six unusual death causes; a hidden death meta |
| Hyrule | Signature items, shards, maps, compasses, nine bosses, Ganon, Zelda, and meta completion |

The world-boss list is the Tarrasque, the Borg, Korzath, the Master Guardian,
the brilliant white light, Smaug, the minotaur god, Zeus, Odin, Ra, Dagahze,
Lolth, Eilistraee, the Dracolich, the Ashen Herald, Lord British, and Lanatir.
Hyrule's boss achievements correspond to the principal encounter in each First
Quest dungeon. Any listed boss kill awards every non-NPC group member present
in the boss room, not only the character delivering the final blow. Ordinary
lifetime kill progress still belongs to the credited killer.

The rare-relic list includes the Power of the world, Lifetaker, Starlight
Sword, minotaur-god claws, the Aegis and Thunder Bolt, Ra's amulet and Sword of
the Sun, Elfbane, Lanatir's sphere and Hammer of Wrath, an Angel's Heart, Lord
British's crown/sceptre/amulet, Farslayer, and the quest-master Scroll of
Farslay. Acquiring one is enough; the achievement remains after the object is
used, lost, stored, or destroyed.

Automatic-quest achievements also recognize completing a rush contract,
turning in a quest during its final minute, winning double-or-nothing, and
acquiring the questmaster's keepsake. Kill objectives award progress to
eligible group members present for the kill, including when a controlled pet
lands the final blow.

Unusual-death achievements distinguish a flagged room death trap, a room-wide
puzzle trap, a lethal action item, another player's Farslay, a self-inflicted
Farslay backlash, and a death ray. Arena knockouts and divine-protection saves
are not true deaths and do not advance the lifetime death counter.

Maps, compasses, and Triforce shards are remembered when acquired, even if the
item is later spent, dropped, or stored. On migration, currently carried items
are scanned recursively, so items inside bags also count. The Master Sword,
Silver Arrow, and complete Triforce achievements require possession when the
state is evaluated.

## Existing Characters

The first login after upgrading checks facts already present in an old player
file. Existing characters can immediately receive level, remort, play-time,
qualifying player-kill, current quest-streak, and currently owned collection or
Hyrule-item achievements. Their current Hyrule room can also record a matching
discovery.

Old player files did not retain lifetime mobile-kill or completed-quest totals.
They also did not retain a reliable all-cause death total. Those three counters
therefore begin when this system first records them. They are not estimated
from session snapshots or the older PK-only death field, because an estimate
could award progress a character did not earn.

## Persistence And Compatibility

Achievement data is stored in the normal player file:

- `Achv <stable-key> <timestamp>` records each unlock by key, not table index.
- `AchKills`, `AchQuests`, and `AchDeaths` store lifetime counters introduced
  by the system.
- `AchExplore`, `AchMaps`, `AchCompass`, and `AchTriforce` store compact Hyrule
  discovery and collection masks.

Missing fields default to zero, so old player files remain valid. Stable string
keys allow catalog entries to move without changing the meaning of saved data.
Unknown retired keys are ignored safely. Achievement state follows ordinary
character save, quit, autosave, snapshot, backup, and restore behavior.

## Developer Notes

The catalog and command live in `src/achievements.c`. `PC_DATA` reserves 128
timestamp slots through `MAX_ACHIEVEMENTS`; the current catalog uses 111. Add
a new entry only with a unique key that will never be repurposed.

Achievement views use canonical `{HH}` game-color tokens and
`page_to_char()`. The pager converts those tokens to the recipient's ANSI
sequences, or removes them when color is disabled, before retaining the text
between pages. Do not bypass that path with raw `write_to_buffer()` calls.

Event hooks are intentionally central:

- `fight.c` records NPC deaths, true player deaths, named bosses, and qualifying
  player-kill milestones.
- `quest.c` records successful quest completions after streak advancement,
  plus rush, final-minute, gamble-win, and keepsake-related progress.
- `handler.c` records room entry, item acquisition, and lethal action items.
- `magic2.c` records crafting, Farslay outcomes, and death rays; `act_obj.c` and
  `update.c` distinguish puzzle traps and flagged death-trap rooms.
- `update.c`, `act_info.c`, `comm.c`, and `save.c` evaluate state milestones at
  level-up, remort, login, score display, and save.

`achievement_check_state()` is idempotent. Event-only room, boss, crafting, and
death-cause criteria unlock only from their event hook; state criteria can be
checked repeatedly.
The save writer serializes earned entries by key. The loader resolves each key
back to the current runtime index.

Run the normal native build, CMake build, area validation, and
`python -m unittest tests.test_achievements -v` after changing the catalog or
hooks. The test verifies key uniqueness, catalog capacity, persistence wiring,
the generated Hyrule boss-to-room contract, compact summary layout, and paged
color conversion.
