# Player Backups And Restores

The owner's rule (2026-10-23): player data is the most important thing the
game keeps, and there should be basically no way a player and all their
gear -- stash included -- cannot be put back to any state. This page is how,
what it does not yet cover, and how long a loss can be.

## What is kept

| Layer | What | Where | How long |
| --- | --- | --- | --- |
| Save snapshots | a copy of the player file at every save, at most one a minute | host, `player/versions/<Name>/<Name>.<stamp>` | every one for a day, the newest of each hour for a week, the newest of each day for a year |
| Milestones | a copy taken **before** a death, remort, deletion, ADVANCE, staff SET, GRANTPSI, COMBINE, CREATOR or any restore, and **before the death penalty** of a mobile's kill; **after** a level gain or a quest | host, `<Name>.<stamp>[_NN].<kind>` | every one for 90 days, and the newest 100 of each kind for ever |
| Corpses | every player corpse as it actually is -- room, timer, every object at any depth -- written at the death and within a second of any change | host, `corpse/live/<id>.corpse` | a week in the world; made again exactly after a restart |
| Corpse history | each corpse as it was made, as it ended (rotted, picked up, purged, restored) and a log of what went in and out, by whose command | host, `corpse/history/<Owner>/` | for ever |
| Recovery ledger | every restore and its undo copy, every milestone with its checksum, every corpse made and ended, each player's permanent uid | host, `player/recovery/ledger.tsv` | for ever; append-only, never rolled back |
| Git history | every character file, the ledger and the corpses, every five minutes (`toc-state-sync`) | GitHub, `player/`, `corpse/` | for ever |
| Milestones in git | every tagged copy except level and quest ones | GitHub, `player/versions/<Name>/` | for ever (the sync never deletes them) |
| Hourly copies in git | the newest save snapshot of each finished hour | GitHub, `player/versions/<Name>/` | as the host keeps them -- hourly for a week, then daily for a year; pruned ones stay in git's history |
| Encrypted snapshot | `player/` and `corpse/` in one archive, checked at every stage | a private repository, `toc-player-backup` | the latest only -- see "Not yet" |

The stamp is the server's clock (UTC). PRESTORE shows how long ago each copy
was taken first, then the time with its zone. A second copy of one kind in
the same second gets `_02` after its stamp instead of being skipped.

Storage is small: character files average 4 KB and the largest is about
90 KB, so a heavily played character's year of snapshots is a few tens of
megabytes. A corpse file is the size of what it holds.

## Restoring in the game (staff)

```
prestore <player>                     the newest 30, how long ago, level, kind
prestore <player> all [page]          every one, 50 a page
prestore <player> deaths [page]       one kind: deaths, remorts, levels,
                                      quests, restores, or milestones
prestore <player> <stamp> show        what it holds: worn, carried, stash
prestore <player> <stamp>             the whole character, as they were then
prestore <player> <stamp> gear        only what they wore and carried, into
                                      their inventory; nothing else changes
prestore <player> <stamp> stash       only the stash, added to what it holds
prestore <player> corpses             their corpses: in the world, or ended
prestore <player> corpse <id> show    what that corpse held
prestore <player> corpse <id> gear    that, into their inventory, once
```

- Use the stamp, not the list number: every save adds a snapshot at the top.
  A unique prefix is enough; add the kind (`20261023_023244.death`) when an
  ordinary save shares the second.
- Every restore takes a copy first, so a restore can itself be undone, and
  writes a receipt to the ledger naming that copy.
- GEAR (and a request through git) waits while the player's own corpse still
  holds things -- they can fetch it, and restoring too would make two of
  everything. `gear force` overrides that when the corpse is out of reach.
- CORPSE GEAR is refused while that corpse is still in the world, and a
  second time for the same corpse; FORCE overrides either, deliberately.
- A full restore of an online player saves and disconnects them first. GEAR,
  STASH and CORPSE work online or offline.
- Any restore of a player ends their corpses' keeping (they go to history).

A "before death" copy is written inside the death, below zero hit points
in the room of the death. Anybody read from a file that way -- a full
restore to it included -- stands up at one hit point in the Temple
(`revive_at_load` in `save.c`; until 2026-10-24 Alaric logged in dead and
could not even quit).

**After a death:** `prestore <player> corpses` first -- if the corpse ended
with things in it, `corpse <id> gear` gives back exactly what was left, with
its enchantments, charges and condition. Otherwise `prestore <player>
deaths`, then `<stamp> show`, then `gear` (keeps their levels and experience
since) or the whole thing. A mobile's kill has two copies: "dying, before
the death's experience penalty" (`.prepenalty`) undoes the penalty too;
"before death" already carries it.

## Restoring from a cloud session

A cloud session cannot reach the host, but a push is a deploy, so a restore
can be asked for in `area/restores.dat`:

```
<id> <player> <kind> <stamp> [<file>]
```

`gear` and `stash` apply at the player's next login, once. Once is kept in
the recovery ledger, which no restore of the player's file rolls back: a full
PRESTORE to the copy taken before the request undoes it and the request
never runs again (until 2026-10-23 it did -- the mark lived in the player
file). A request moves through `pending` (written before anything is given)
to `committed` (the player file holding it is saved). One that can never
apply -- no snapshot matches, two match, the snapshot is not whole -- is
`rejected` for good and needs a new id; one that cannot apply yet -- its
imported file is not installed, a file would not open, the corpse still
holds things -- is noted as `retry` and tried at the next login. `import`
only installs a file as a snapshot staff can PRESTORE. Ids are never reused.

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
stash counts after the next state sync, and `player/recovery/ledger.tsv` in
git says what each request came to.

## When something fails

Every restore is one operation that is either done or not, and says
which (independent review, 2026-10-23):

- GEAR, STASH and CORPSE take a copy that would undo them, write a pending
  receipt, give the objects with a mark in the player's file, save, and
  commit the receipt. If the undo copy or the receipt cannot be written,
  nothing is given. If the save fails, an offline player is given nothing
  (the receipt says abandoned; try again); an online player has the
  objects in hand and the receipt stays pending. A pending receipt is
  settled at the player's next login by the mark in their file.
- A full PRESTORE saves an online target and takes its undo copy first;
  if either fails, nothing changes and nobody is disconnected. It keeps
  the player's current password, trust, creator rank, login fixes,
  Hyrule claims and black market purchases, whatever the snapshot held.
- "Not confirmed on the disk" (a directory that would not flush) is never
  reported as done.
- A corpse whose history cannot be written keeps its end state in
  `corpse/live/<id>.ending.corpse` -- listed by PRESTORE CORPSES as "NOT
  yet in history", restorable as usual -- until it can be moved.
- A torn ledger record is set aside in `player/recovery/ledger.torn.*`
  and cut off; the records before it stand.
- A death is a receipt too (2026-10-27): `death:<corpse id>` opens, the
  corpse's record is written, the player's file is saved with a mark, and
  the receipt commits. Until it does, nobody can take from the corpse. A
  crash before the save lands is settled at boot from the file: no mark,
  the file still holds everything and the corpse is not laid (its record
  goes to history as `undone`); a mark, the corpse is laid as theirs.
- RESURRECTION's ACCEPT whose save is not confirmed stays pending and is
  settled by the next save, boot or login -- never undone on a guess.
- A receipt's mark never shortens the file's list of fixes: a list that
  cannot take another refuses the restore, death or ACCEPT before
  anything moves.

## How long a loss can be

Measured from the code, not promised:

- **A crash of the game process:** what changed since the player's last
  save. Saves happen at least every autosave cycle and at every level,
  quest, death, restore and stash change; the file and its rename are
  flushed to the disk before the save counts.
- **A death:** none -- the corpse and the player's file are a single
  transfer (above).
- **A corpse:** up to a second of looting before a crash (changes are
  written within a second); its timer, up to ten minutes stale. The
  looter's own file is saved on its own schedule, so a crash after the
  corpse's record caught up and before the looter's next save loses what
  they took (a known window, older than the death receipts).
- **The host lost:** up to five minutes (the state sync), plus anything
  since the last sync that only the host had. A rebuilt host's PRESTORE
  lists the same hourly, daily and milestone copies the lost one did,
  except the current hour's (2026-10-24); a restore drill from GitHub
  alone took under two minutes the same day.
- **The host and GitHub lost together:** everything since the last
  encrypted archive, if it is installed, up to six hours.

## Not yet

Known boundaries of what is built:

- A corpse picked up and put down again is a new record with a new id;
  restoring both records, or restoring a record whose corpse someone is
  still carrying, can give the same things twice. Stable item identities
  are what will catch that.
- Corpse history is filed by name; CORPSE GEAR checks the recorded uid
  against the name's uid now and needs FORCE for an earlier character.
- The state sync copies files that change independently, every five
  minutes; it is not a consistent snapshot across players, and its
  interval is not a measured maximum under failures.

These are proposals, not built (handoff review, 2026-10-23):

- Stable identities for objects, so a restore can say which sword came back
  and refuse one already returned through another route; today a restore
  matches by what is in a snapshot, and repeating GEAR on the same snapshot
  adds copies.
- Selective restores of single items, item properties, worn layout or
  chosen stats, with preview, conflicts, escrow for displaced items and a
  compensating undo; and transactional, exactly-once recording of trades
  and other multi-character changes.
- A private recovery vault apart from the public sync, with immutable
  versioned copies (the encrypted archive keeps only the latest), and a
  measured restore drill on a fresh host.
- Causal gameplay audit events (reason codes, before/after state, output
  capture) beyond the play journal and watch log.
- Archive receipts held off the host before an action is acknowledged; the
  state sync is asynchronous.
