# Player Backups And Restores

The owner's rule (2026-10-23): player data is the most important thing the
game keeps, and there should be basically no way a player and all their
gear -- stash included -- cannot be put back to any state. This page is how.

## What is kept

| Layer | What | Where | How long |
| --- | --- | --- | --- |
| Save snapshots | a copy of the player file at every save, at most one a minute | host, `player/versions/<Name>/<Name>.<stamp>` | every one for a day, the newest of each hour for a week, the newest of each day for a year |
| Milestones | a copy taken **before** a death, remort, deletion, ADVANCE, staff SET, GRANTPSI, COMBINE, CREATOR or any restore; **after** a level gain or a quest | host, `<Name>.<stamp>.<kind>` | every one for 90 days, and the newest 100 of each kind for ever |
| Git history | every character file, every five minutes (`toc-state-sync`) | GitHub, `player/<Name>` | for ever |
| Milestones in git | death, remort, delete, advance, staffset, grantpsi and creator copies | GitHub, `player/versions/<Name>/` | for ever (the sync never deletes them) |
| Encrypted snapshot | `toc-player-backup`, every six hours | a private repository | see that script |
| Corpses | a player's corpse lasts a week, and one not yet touched is made again from its death snapshot after a restart | host, `corpse/registry.tsv` | until it is touched, picked up or gone |

The stamp is the server's clock (UTC). PRESTORE shows how long ago each copy
was taken first, then the time with its zone.

Storage is small: character files average 4 KB and the largest is about
90 KB, so a heavily played character's year of snapshots is a few tens of
megabytes.

## Restoring in the game (staff)

```
prestore <player>                     the newest 30, how long ago, level, kind
prestore <player> all                 every one
prestore <player> deaths              one kind: deaths, remorts, levels, quests,
                                      or milestones for all of them
prestore <player> <stamp> show        what it holds: worn, carried, stash
prestore <player> <stamp>             the whole character, as they were then
prestore <player> <stamp> gear        only what they wore and carried, into
                                      their inventory; nothing else changes
prestore <player> <stamp> stash       only the stash, added to what it holds
```

- Use the stamp, not the list number: every save adds a snapshot at the top.
  A unique prefix is enough; add the kind (`20261023_023244.death`) when an
  ordinary save shares the second.
- Every restore takes a copy first, so a restore can itself be undone.
- GEAR (and a request through git) waits while the player's own corpse still
  holds things -- they can fetch it, and restoring too would make two of
  everything. `gear force` overrides that when the corpse is out of reach.
- A full restore of an online player saves and disconnects them first. GEAR
  and STASH work online or offline.
- Any restore takes the player's corpses off the rebuild list.

**After a death:** `prestore <player> deaths`, then `prestore <player>
<stamp> show` to check, then either `gear` (keeps their levels and
experience since) or the whole thing (also undoes what the death cost).

## Restoring from a cloud session

A cloud session cannot reach the host, but a push is a deploy, so a restore
can be asked for in `area/restores.dat`:

```
<id> <player> <kind> <stamp> [<file>]
```

`gear` and `stash` apply at the player's next login, once (the id is kept in
their file as `restore:<id>`). `import` only installs a file as a snapshot
staff can PRESTORE. Ids are never reused.

`tools/player_history.py` finds the state to restore, from the repository
root after `git fetch`:

```bash
python3 tools/player_history.py log Alaric           # saved states, newest first
python3 tools/player_history.py show Alaric <ref>    # worn, carried, stash
python3 tools/player_history.py diff Alaric <ref1> <ref2>
python3 tools/player_history.py export Alaric <ref> <id> gear
```

`<ref>` is a commit from `log`, or a milestone's file name
(`Alaric.20261023_023244.death`). `export` writes that version to
`area/restores/` and adds the request line; commit both and push. After
the deploy (which waits for an empty game) the player gets it at their
next login. For a whole-character restore from git, export it as `import`
and have staff run the full PRESTORE on `<stamp>.import`.

Check the result the same way: `log` shows the file's worn, carried and
stash counts after the next state sync.

## What can still be lost

- Anything between a player's last save and a crash of the game process
  (saves happen every few minutes and at every level, quest and death).
- A corpse a player had started looting when a restart came: what was left
  in it. Their death snapshot still has all of it, for GEAR.
- Everything, if the host and GitHub were lost together.
