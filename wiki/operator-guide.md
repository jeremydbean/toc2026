# Times of Chaos Operator Guide

This guide is for trusted immortals and people responsible for a running ToC
instance. It focuses on safe operating procedures rather than gameplay. Exact
command availability depends on trust level; use `wizhelp` and
`help <command>` while logged in.

## Operating Principles

1. Protect player continuity before convenience. Back up before upgrades,
   restores, mass edits, or experimental commands.
2. Prefer in-game and dashboard operations over direct file edits.
3. Never edit an online player's file. The next save can overwrite the edit or
   combine states unpredictably.
4. Treat player files, logs, backups, IP data, and password hashes as sensitive.
5. Validate area data before every game reboot that will load it.
6. Keep the web dashboard private. An admin token protects operational routes,
   not every read endpoint.
7. Record who changed what, when, why, and how it was verified.

## Trust And Command Discovery

Normal players advance through level 59 after remorts. Levels 60-70 are
immortal/staff trust levels. A command's minimum trust is defined in
`src/interp.c`; do not assume every immortal can perform every operation.

```text
wizhelp
help <immortal-command>
diagnostics
```

Command logging also varies. High-impact commands are generally logged, but
logs are not a substitute for change notes and host-level audit controls.

## Daily Check

Run or review:

```text
diagnostics
backup
who
sockets
```

Confirm:

- Boot time is expected and the game is not rebooting repeatedly.
- World counts are nonzero and consistent with the deployed revision.
- Descriptor and list diagnostics do not show corruption symptoms.
- The next four-hour and daily backups are scheduled.
- `log/toc.log` has no repeated crash, area-load, queue, or backup errors.
- Disk space can accommodate player versions, logs, image layers, and archives.
- Dashboard health agrees with a real MUD client connection.

Current checked-in parser inventory is 99 listed area files, 7,781 rooms, 2,336
mobiles, and 3,551 objects. Native boot also creates an online-building area,
and native/Python area totals differ because six listed help/social files have
no `#AREA` record. Investigate unexpected deltas, not the known counting model.

## Start, Stop, And Reboot

### In-Game Commands

```text
reboot
shutdown
newlock
wizlock
```

- `reboot` exits the C server without the shutdown marker. `startup.sh` and the
  Docker entrypoint treat that as a restart request.
- `shutdown` writes `area/shutdown.txt`. The wrappers see it and exit cleanly.
- `newlock` controls new-character creation.
- `wizlock` restricts login according to the command's live help.

The Docker Compose service uses `restart: unless-stopped`, which can restart the
whole container even after a clean in-game shutdown. To keep it stopped, run:

```bash
docker compose stop
```

### Planned Reboot Checklist

1. Announce the maintenance window and expected duration.
2. Ask players to `save`; allow active fights and transfers to finish.
3. Run `backup now` and verify the archive.
4. Enable the appropriate login/new-character lock if needed.
5. Validate the deployed code and area files at the host shell.
6. Use `reboot` for a wrapper-managed restart or stop/start the service for a
   full container/process refresh.
7. Watch the complete boot log.
8. Verify `diagnostics`, player login, movement, save, and dashboard health.
9. Remove locks and announce completion.

Never repeatedly reboot a crash loop without preserving the first useful logs.

## Diagnostics

`diagnostics` is the first in-game health command. It reports boot timing,
world totals, connected descriptors, global list counts, active mobile state,
and scheduled backups. Pair it with host information:

```bash
docker compose ps
docker compose logs --tail 300 game
docker stats toc2026_game
curl -fsS http://127.0.0.1:9001/api/health
curl -fsS http://127.0.0.1:9001/api/stats
```

Additional trust-gated commands such as `memory`, `sockets`, `mwhere`, `owhere`,
`gwhere`, and `dump_exits` help inspect a suspected subsystem. Use their help
before running them against a busy production server.

## Backups

### Scheduled And Manual Archives

```text
backup
backup now
backup daily
```

- Four-hour archives use a timestamped filename.
- Daily archives use a date-oriented filename.
- Both archive `player/` and prune `*.tar.gz` files older than 30 days from the
  configured backup directory.
- Dashboard `POST /api/backup` queues the same backup operation.

Verify success in three places: the in-game/log completion message, a new
nonempty file in `backups/`, and an off-host copy when the operation protects a
major change.

### Player Version Restore

```text
prestore <player>
prestore <player> list
prestore <player> <number>
```

The list is newest first and includes the snapshot's level when readable.
Before restoring:

1. Confirm identity and the exact loss window with the player.
2. Ensure the character is disconnected.
3. Run `prestore <player>` and record the current file and intended snapshot.
4. Select the smallest rollback that fixes the problem.
5. Complete the restore and preserve the automatically created safety copy.
6. Have the player log in, inspect inventory/equipment/level, and `save` only
   after confirming the restored state.

Do not extract a full server archive to recover one character unless the
version history is unavailable and a staged file-by-file restore is required.

## Player Account Incidents

### Forgotten Or Compromised Password

Do not ask the player to send their old password. Verify ownership using the
host's established policy and private historical information that does not
expose another secret. Preserve the current player file and relevant audit log,
disconnect the character if compromise is active, then use an approved offline
recovery process.

Trusted staff can use the current recovery command only while the target is
offline:

```text
resetpwd <player> <newpassword>
```

The command refuses a target at or above the operator's trust, validates the
new value, rewrites through a temporary player file, and announces the reset
without logging the password argument. Set a unique temporary value, deliver it
through an appropriately private channel, and ask the player to change it after
login. The command still crosses the operator's unencrypted Telnet connection.

The current password format is traditional DES `crypt(3)` with the character
name supplied as salt. Only the first eight password bytes are effective, and
Telnet sends login traffic unencrypted. Encourage a unique random replacement
and document the security limitation rather than promising modern protection.

### Corrupt Or Missing Player File

1. Stop automatic login/save activity for that character.
2. Preserve the file exactly as found.
3. Check `player/versions/<Name>/` and `backups/` without modifying them.
4. Review logs around the last successful save and failure.
5. Use `prestore` if the live parser can safely list snapshots; otherwise stage
   an offline restore while the game is stopped.
6. Validate file ownership, capitalization, terminators, and required fields.
7. Test with the affected player and keep the safety copy.

Never use another character's file as a template without removing credentials,
identity, inventory, quest, and relationship state. Prefer a known valid
snapshot.

### Player Stuck Or Trapped

First determine whether the area intentionally blocks recall or requires a
puzzle/portal. Inspect room vnum, flags, exits, and area documentation. Use
trust-gated movement commands only after recording the original location and
checking carried followers, mounts, combat, and scripted state.

For Hyrule, recall is intentionally disabled. Valid exits are the secret-tree
return and post-Ganon portal; do not treat that design as a generic recall bug.

## Moderation And Player Safety

Relevant command families include:

- Access: `allow`, `ban`, `deny`, `newlock`, `wizlock`.
- Session control: `sockets`, `dump`/disconnect handling, `freeze`, `jail`.
- Communication restrictions: `nochannels`, `noemote`, `nonote`, `noshout`,
  `notell`, `notitle`.
- Investigation: `finger`, `activity`, `where` variants, logs, and diagnostics.
- Correction: `restore`, `advance`, `transfer`, `goto`, `at`, `force`, and
  player-version restore, according to trust.

Use the least invasive action that stops harm. Preserve evidence before
changing state, avoid discussing private account details publicly, and make
time-bounded sanctions explicit in operator notes. `force` and arbitrary
dashboard commands are especially high impact because they can perform actions
as or around another character.

## Web Dashboard Operations

Protected dashboard routes require `X-Admin-Token`:

```text
GET  /api/logs
WS   /ws/logs (token in first JSON message)
GET  /api/players
GET  /api/player/{name}
POST /api/wizinfo
POST /api/command
POST /api/backup
GET  /api/backups
POST /api/shutdown
POST /api/reload
```

Important distinctions:

- `/api/command` writes a command to `area/webadmin.queue`; it is not a shell.
  The C server consumes and executes the queued immortal command.
- Queue acknowledgement means queued, not necessarily completed. Confirm the
  resulting game/log state.
- `/api/reload` reparses area files for the dashboard and rejects a parser swap
  if critical area-health findings exist. It does not reload the live game.
- `/api/shutdown` queues an in-game shutdown request. Compose restart policy may
  still restart the container.
- The token is a shared secret without individual operator identity. Rotate it
  when staff access changes and keep separate host-level audit records.
- World browsing and the browser game bridge are not token-protected.
  Network-restrict the whole dashboard.

Never place the admin token in a screenshot, command history shared with
others, issue report, or URL. The log WebSocket sends it in the first JSON
message rather than the URL.

## Area And World Changes

The dashboard browser reads files independently of the C server. The safe
deployment sequence is:

```bash
cd /path/to/toc2026
bash scripts/validate.sh
```

Or, for focused area work:

```bash
cd area
../merc --check-area
cd ..
python3 check_parser.py
python3 check_exits.py
python3 check_resets.py
python3 check_shops.py
python3 scripts/area_lint.py --fail-on critical --limit 100
```

Then:

1. Review all new critical, warning, and information findings.
2. Refresh the dashboard parser if staff need to inspect the files before the
   maintenance reboot.
3. Back up player state.
4. Reboot/restart `merc` to load the world.
5. Visit every changed entry, exit, reset, boss, shop, portal, trap, and reward
   with a test character of the intended level.

Area files are Latin-1. Do not convert them to UTF-8. `area/area.lst` determines
load order. Duplicate vnums and cross-area references can break areas other than
the file being edited.

Hyrule is generated from `data/hyrule_first_quest.json`. Edit the manifest and
generator, run `make hyrule-area`, and run Hyrule tests rather than changing the
generated `.are` file by hand.

## Incident Runbooks

### Repeated Crash Or Restart Loop

1. Preserve logs from before the first restart.
2. Stop the outer service to prevent log churn and repeated data writes.
3. Record the deployed commit/image, configuration, last player action, and
   latest area/data change.
4. Run native area validation and the full test suite on the same revision.
5. Reproduce on a copy with sanitizers or Valgrind if the failure is in C.
6. Roll back code/world together when a recent deployment is implicated.
7. Restore player data only if evidence shows it was corrupted.

### World Boots With Area Errors

Stop before allowing players in. Do not patch around a duplicate vnum or parse
failure on production. Correct the source branch, run validation, deploy a
reviewed build, and retain the failed log for diagnosis.

### Disk Nearly Full

Stop write amplification first. Inspect logs, Docker images, build trees, player
versions, and backup retention. Move verified backups off-host before deleting
local copies. Do not delete the current player directory, newest known-good
archive, or evidence from an active incident.

### Dashboard Token Exposure

1. Restrict dashboard network access immediately.
2. Generate a new random token and recreate/restart the dashboard process.
3. Invalidate browser-stored old values and update the authorized secret store.
4. Review web/proxy logs and `area/webadmin.queue` for unexpected operations.
5. Change affected staff/game credentials if the token appeared beside them.

### Suspected Player-File Theft

Treat it as credential exposure. Preserve access logs, remove public dashboard
access, notify affected users to use unique replacements, and remind them that
DES hashes are fast to test offline. Do not publish the files or hashes while
investigating.

## Maintenance Record Template

```text
Date/time and timezone:
Operator:
Reason:
Revision/image before:
Revision/image after:
Backup verified:
Validation run and result:
Player impact:
Commands/actions performed:
Smoke tests:
Rollback point:
Follow-up:
```

## Related Documentation

- [Hosting Guide](hosting-guide.md)
- [Security](../SECURITY.md)
- [Validation And Area Health](validation-and-area-health.md)
- [Developer Guide](developer-guide.md)
- [Area Building Guide](area-building-guide.md)
- [Hyrule: First Quest](hyrule-area.md)
