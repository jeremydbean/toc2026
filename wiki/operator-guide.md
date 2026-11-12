# Times of Chaos Operator Guide

This guide is for trusted immortals and people responsible for a running ToC
instance. It focuses on safe operating procedures rather than gameplay. Exact
command availability depends on trust level; use `wizhelp` and
`help <command>` while logged in.

## Operating Principles

`set char <name> hp <value>`, `mana <value>` and `end <value>` accept up to
`POOL_MAX` (1,000,000,000; `hp` from -10, the others from 0). Pools are
`int`, no longer 16-bit, so the old 30,000 ceiling is gone. Each sets the
character's permanent base (`perm_hit`, `perm_mana`, `perm_move`) to the
value, and the bonuses standing at that moment -- gear, spells, TITANIC --
stay on top of it (`pool_set_base`), as a reload would rebuild them; when a
bonus later comes off, the maximum falls back to exactly the base you set.
None of them refills the current pool; use `restore <name>` when a refill
is intended. `set char <name> move <value>` sets the current
movement only, and `maxmove <value>` (1 to `POOL_MAX`) the maximum alone,
clamping the current pool to it.

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

Recounted on 2026-11-12, the checked-in parser inventory is 102 listed area
files, 7,766 rooms, 2,507 mobiles, and 3,760 objects (the native validator
said `areas=95 mobs=2507 objects=3760 rooms=7766`); recount with the tools
rather than trusting this line. Native and Python area totals differ because seven
listed help/social files have no `#AREA` record: the native validator reports
95 areas, including the `custom.are` builder workshop. Investigate unexpected deltas, not the known counting model.

### Live Host Quick Check

The live server is on Oracle Cloud; [disaster-recovery.md](disaster-recovery.md)
is the full runbook.

```bash
ssh toc-oracle 'systemctl is-active toc-game toc-web'
ssh toc-oracle 'systemctl list-timers toc-state-sync.timer toc-state-sync-check.timer toc-game-recovery.timer toc-auto-deploy.timer'
ssh toc-oracle 'curl -fsS http://127.0.0.1:9001/api/health'
```

The normal state is active game/web services and active timers. After
authenticating, the dashboard's **Host status** presents this service/timer
state plus root-disk use, boot/shutdown history, deployment state, and bounded
ToC journals without granting shell access.

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
  It does so wizinvis or not (until 2026-11-12 a wizinvis `shutdown` wrote no
  marker and was a restart); wizinvis only changes the line players see to
  "The game is shutting down." If the marker cannot be written the game stays
  up and says so, since it would only come back as after a `reboot`.
- Both are creator-only (trust 72).
- `newlock` controls new-character creation.
- `wizlock` restricts login according to the command's live help.

The Docker Compose service uses `restart: unless-stopped`, which can restart the
whole container even after a clean in-game shutdown. To keep it stopped, run:

```bash
./toc.sh stop        # or: docker compose stop
```

On the live host, use systemd instead:

```bash
sudo systemctl stop toc-game-recovery.timer toc-game toc-web
sudo systemctl start toc-game toc-web toc-game-recovery.timer
sudo systemctl restart toc-game toc-web
```

Stopping `toc-game` sends SIGTERM. The game saves connected players, closes
descriptors, and exits; systemd then starts it at boot or after a crash, and
the main-loop watchdog restarts a frozen process. `toc-game-recovery` is the
backstop for a game that crash-loops past systemd's start limit; stop its
timer first when an intentional outage must remain offline. See
[disaster-recovery.md](disaster-recovery.md).

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

A six-hour off-host layer, `toc-player-backup.timer`
(`deploy/sync-player-backup.sh`), age-encrypts `player/` before Git
transport; the recovery private key must remain off the host. Where it is
installed, check it with:

```bash
systemctl list-timers toc-player-backup.timer
sudo journalctl -u toc-player-backup -n 100 --no-pager
```

Periodically decrypt and list the archive with the recovery key. A successful
push alone does not prove the backup can be restored.

### Player Version Restore

```text
prestore <player>
prestore <player> list
prestore <player> <number|stamp>
prestore <player> <number|stamp> stash
```

The list is newest first and includes the snapshot's level when readable,
and the stamp to type: the numbers move whenever a save adds a snapshot,
the stamp does not.
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

### Restoring A Lost Stash

A snapshot marked `before death` is taken before the dead character is
extracted, so it holds the stash exactly as it stood when they died. When
a stash has been lost, put it back from that copy alone rather than the
whole file, which would roll back levels, gear and gold as well:

```text
prestore alaric
prestore alaric 20261010_162657 stash
```

Use the stamp when the player is online: their autosaves renumber the
list under you. The restore adds the snapshot's stash to whatever the
stash holds now and saves at once; the player keeps playing and is told,
or if offline finds it at their next login. The count it reports is of
top-level objects, as `stash` itself counts; anything inside a container
came back inside it. Each restore takes its own `before stashrestore`
copy, and nothing is removed, so a restore that turns out not to have
been needed leaves duplicates to take out rather than a loss. The
command's log line reaches `log/toc.log`, and the state sync carries it
to GitHub within five minutes, so a session without host access can
confirm the result.

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

Passwords are stored as SHA-512 crypt hashes (`src/password.c`; see
[SECURITY.md](../SECURITY.md)). A password set by RESETPWD or PASSWORD counts
every byte. A character still on an old DES hash is moved to SHA-512 at their
next login but keeps DES's effective limit -- the first eight bytes -- until
they choose a new password, so ask a recovered player to change it. Telnet
sends login traffic unencrypted. Encourage a unique random replacement and
document the security limitation rather than promising modern protection.

### Corrupt Or Missing Player File

1. Stop automatic login/save activity for that character.
2. Preserve the file exactly as found.
3. Check `player/versions/<Name>/` and `backups/` (under `state/` in an
   installed copy) without modifying them.
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

### Maps And The Cartographer

The Mudlet map shows a player only what their character knows (`src/maps.c`,
HELP MAPS). Two level 65 commands, both logged:

```text
grantmap <player> <area|hyrule1..hyrule9|all>
grantmap list
cartographer [status|spawn|here|dismiss]
```

GRANTMAP gives the whole map of an area (by file name, as `camelot`, or the
start of its name), of one Hyrule dungeon, or of everything, to a player online
or saved. It saves their file, reports an unconfirmed save, refuses a player who
outranks you, and goes to WIZINFO at the pair's notice level. A map cannot be
taken away again. CARTOGRAPHER shows where the wandering cartographer (mob
29942) is and when he leaves or next comes, or calls or dismisses him. His
arrival goes to the public log without a room and to WIZINFO with it.

## Moderation And Player Safety

Relevant command families include:

- Access: `allow`, `ban`, `deny`, `newlock`, `wizlock`.
- Session control: `sockets`, `dump`/disconnect handling, `freeze`, `jail`.
- Communication restrictions: `nochannels`, `noemote`, `nonote`, `noshout`,
  `notell`, `notitle`.
- Investigation: `finger`, `activity`, `where` variants, logs, and diagnostics.
- Correction: `restore`, `advance`, `transfer`, `goto`, `at`, `force`, and
  player-version restore, according to trust.

### Jail sentences

```text
jail <player> status
jail <player> 30m | 2h | 7d | <days>     timed, at most 30 days
jail <player> indefinite                 until staff release them
jail <player> release                    (or: jail <player> 0)
```

- Works on players online, link-dead or offline (not on somebody still at
  the login prompts -- try again in a moment). Rank protects as for any
  staff command.
- A duration starts now and **replaces** any term being served; it never
  adds to it. A bare number is days, as it always was.
- The sentence is saved the moment it is given or lifted. If the save
  fails you are told and nothing changed; "written, not confirmed" means
  the change stands and the next save confirms it.
- A timed sentence ends by itself at its time: online with nothing typed,
  or at the next login if they are away. The release lands in the Temple.
  A release whose save fails leaves them jailed and is tried again ten
  seconds later (logged, and on WIZINFO).
- Nothing else ends it. Death (any kind, including SLAY and FARSLAY),
  recall, portals, travel spells, pocket rooms, PROJECT, PRAY, REMORT,
  DELETE, quitting, link loss and reboots leave the prisoner in room 3.
  TRANSFER, ITRANS and DRAG refuse a prisoner: release them first. FORCE
  makes them try, and the sentence refuses them like anyone else.
- Jailing turns on NOCHANNELS and NOTITLE only if they were off, and
  remembers which; release takes off only those. A nochannel or notitle
  you toggle during the sentence is yours, and release leaves it. Titles,
  WARNED and EXCON are never touched.
- STATUS shows the release time (UTC) and what is left, who set the term,
  since when, and what it imposed. A sentence from before 2026-11-12 shows
  as indefinite and "sentenced before sentences were recorded": nothing
  says which restrictions it added, so release leaves channels and title
  bans for you to lift by hand (an old " . (JAILED)" title is put back to
  the class title).

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
GET  /api/events
WS   /ws/events (token in first JSON message)
GET  /api/admin/status
GET  /api/host/status
GET  /api/host/resources
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
  resulting game/log state. The Operations page and `/api/admin/status` expose
  a pending line count without exposing the privileged command text.
- The operational snapshot also reports game reachability, latest backup age,
  recent player-save timestamps, and log/event file activity. Use it to notice
  stale protection or a stuck queue, then verify with the underlying service.
- `/api/host/status` is an opt-in, read-only snapshot. It covers a fixed list
  of ToC services/timers (`TOC_HOST_SERVICE_UNITS` and friends), root
  filesystem capacity, memory/load/
  temperature, recent journal boots, deployed Git metadata, and bounded ToC
  operational journals. It accepts no arbitrary command, unit, or path and is
  not SSH. An authenticated request receives 503 when
  `WEB_ADMIN_HOST_STATUS` is disabled.
- `/api/host/resources` is the matching lightweight live sample for CPU,
  memory, swap, aggregate non-loopback network throughput, root disk, load,
  uptime, and temperature. Host Status polls it every five seconds only while
  that view is visible and keeps at most 60 samples in the browser.
- The main Operations page has a bounded, filterable Server Info/WizInfo event
  view. Routine activity is useful context but is not a durable audit log.
- `online.count` on `/api/admin/status` is the game's own tally of descriptors
  in `CON_PLAYING`, asked for over MSSP, and `online.source` reads `"game"`
  when that is where it came from. If the game cannot be reached the field
  reads `"journal"` and the number is only an upper bound: a session that ends
  without a recorded close leaves a stale `connect` in `log/logins.tsv`, so
  the journal over-reports and never under-reports. Check `source` before
  trusting the count to decide whether a restart is safe.
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

The live host's token in `/etc/toc/web.env` is persistent across deploys.
The dashboard there requires manual entry because `WEB_ADMIN_LOCAL_UNLOCK=0`;
**Remember on this browser** retains it only in that browser profile. Read it
on the host with `sudo` and never print it anywhere shared.

## Travel Directions

The dashboard's **Directions** view and the browser client's **Routes** panel
list every published route: those worked out of the world as it currently
stands, and those handed down by players. Both are public -- no admin token --
and both read the same `/api/directions`. Each card is tagged with which kind
it is and how well it holds up, and a drifted route that has a worked-out
replacement shows both.

The file is generated, not live. After any change to exits, portals or
`area.lst`, regenerate and commit it:

```bash
python3 tools/build_directions.py
```

Two areas have no route because nothing in the world links to them: the Quest
Zone (20301-20313), which is finished content with no entrance, and Temple
Despair (26000-26006), which has no mobs or objects at all. Dresden has none
because it contains the square the routes start from.

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
any DES hash still in a file, or in git history, is fast to test offline, and
that SHA-512 crypt is slower but not proof against a weak password. Do not
publish the files or hashes while investigating.

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
