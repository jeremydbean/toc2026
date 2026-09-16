# Windows Production Hosting

This runbook describes the Windows/Hyper-V deployment configured on September
16, 2026. It is distinct from the Docker installer and Raspberry Pi appliance.
Do not run the Pi installer or Pi automatic updater on this VM.

## Connections And Boundaries

- Public game: `toc.jeremybean.com`, TCP port `9000`, plain Telnet.
- Public browser client: `http://toc.jeremybean.com:9001/client`.
- Dashboard: `http://toc.jeremybean.com:9001/`, on the same public port, with
  every operational route behind the admin token.
- Do not publish SSH.
- Reserve the Windows host's LAN address in router DHCP settings.
- Protected dashboard actions require the production admin token stored in
  `C:\ProgramData\ToC\secrets\web-admin-token.txt`. Do not put it in Git,
  screenshots, URLs, tickets, or public listing submissions.

Publishing 9001 was a deliberate decision, taken with these consequences
understood:

- The port carries no TLS. The admin token travels as a plaintext header and
  player passwords travel over plaintext `ws://`. Anyone between a player and
  this host can read both. Players must use game-only passwords.
- The browser client bridges to the game from `127.0.0.1`, and the game's
  login throttle exempts loopback on purpose, since every web player shares
  that address. Password guessing through `/client` is therefore unthrottled,
  while the same guessing against port 9000 is blocked after five failures.
- World data is public on this port and needs no token: `/api/mobs`,
  `/api/objects`, `/api/rooms`, `/api/areas`, `/api/best_gear`.
- Keep `WEB_ADMIN_LOCAL_UNLOCK=0` in `/etc/toc/web.env`. The unlock now gates
  on the peer address rather than the `Host` header, but it exists for a
  loopback-bound service and this one is not.

Host-side publication is `deploy/windows-vm/Publish-ToCWeb.ps1`, run elevated:
it adds the `TOC-NAT` static mapping and the inbound firewall rule, and
`-Remove` withdraws both. The router forward is separate and manual.

Mudlet connects directly to port 9000. It does not need access to the dashboard.
See the [Mudlet guide](../mudlet/README.md) and
[listing handoff](../mudlet/listing-submission.md). Listing acceptance is a
separate human review, not a consequence of starting the server.

## Authoritative State

The Hyper-V VM is `TOC-Production`, running Ubuntu 24.04. Its current allocation
is two virtual CPUs, dynamic 512 MB-2 GB RAM, 1 GB startup RAM, and a dynamically
expanding 40 GB disk. The disk is `C:\ProgramData\ToC\vm\toc-os.vhdx`.

**Live player progress is in `/srv/toc/current` inside the VM.** Neither the
original development checkout nor `C:\ProgramData\ToC\source` is a live-save
mirror. Never replace VM character files with either copy during an update.

The initial migration preserved 1,209 state files byte-for-byte. Subsequent
saves legitimately change those checksums. No inaccessible Raspberry Pi saves
were imported. Do not run two publicly accessible copies with divergent progress.

## Recovery And Maintenance

Hyper-V starts the VM on Windows boot. The SYSTEM task `TOC VM Watchdog` checks
every two minutes and starts an off VM; it does not diagnose a frozen guest OS.
Windows AC sleep and AC hibernation timeouts are disabled. The PC must remain
powered and connected; a UPS is advisable.

Linux `toc-game.service` uses systemd readiness and a main-loop heartbeat with
a 60-second watchdog. `toc-web.service` restarts on exit; the web watchdog checks
HTTP health each minute and restarts after three failures. Crash loops are
bounded to five starts per five minutes. Normal signal shutdown saves players,
including link-dead characters. A hard crash can still lose unsaved changes.

From PowerShell:

```powershell
ssh -i C:\ProgramData\ToC\secrets\toc-admin -o UserKnownHostsFile=C:\ProgramData\ToC\secrets\known_hosts tocadmin@172.28.90.2
```

Inside the VM:

```bash
systemctl status toc-game toc-web
systemctl list-timers 'toc-*'
sudo journalctl -u toc-game -u toc-web -n 100
sudo systemctl start toc-backup.service
```

For deliberate maintenance, create `/etc/toc/maintenance` before stopping the
services. Remove it only after validation, then reset failed units and start
both services. An in-game `shutdown` also leaves an intentional shutdown marker;
investigate it instead of blindly deleting it. Before intentionally powering
off the VM, create `C:\ProgramData\ToC\maintenance` to suppress the Windows
watchdog too. Remove that Windows marker when recovery should resume.

## Backups And DNS

- `toc-backup.timer` runs daily at 04:15 America/New_York, with up to two minutes
  jitter and missed-run catch-up. It briefly disconnects players while saving
  and archiving consistent state. Archives include `area`, `player`, `gods`,
  `heroes`, `corpse`, `notes`, and `data`, with SHA-256 sidecars.
- VM archives are in `/var/backups/toc`. At least seven are retained; older
  archives expire after 30 days.
- `TOC Backup Copy` runs at 04:35 Windows local time and verifies copies in
  `C:\ProgramData\ToC\backups`. This survives VM damage, not physical host loss.
  Keep encrypted off-machine backups too.
- `toc-ddns.timer` checks every five minutes. Two IP services must agree before
  updating the Namecheap `toc` record. The root-only credential is delivered
  through systemd, never through a command-line argument.
- Rotate any DDNS credential previously shared in chat. DDNS does not bypass
  CGNAT, create port forwarding, or wake a sleeping machine.

Do not restore an archive over running state. Stop safely, preserve current
state, verify the archive, restore into an empty directory, compare ownership
and contents, and explicitly decide whether the intended rollback of progress
is acceptable before replacement.

## Safe Releases

Build and test a separate source tree first. Preserve local gameplay fixes when
reconciling GitHub history. Preserve executable bits and Unix line endings when
transferring a Windows checkout. Never copy logs, credentials, player files,
PK standings, max-load state, shutdown markers, or queued commands from Git into
production. Review area-file differences individually.

During the brief cutover, take a stopped-state backup and a separate code rollback
archive, install only reviewed code/assets and the compiled executable, compare
state checksums before restarting, and verify both services. Roll back code on
failure, not player progress. The older deployment-only `game-systemd.patch`
must not be reapplied blindly: current `src/comm.c` already has notification,
watchdog, and graceful-shutdown support.

The Pi-specific dashboard host-status and automatic-update controls are not
configured for these differently named Windows-hosted services. Keep them
disabled unless explicitly adapted and tested.

Transport remains unencrypted and traditional DES password hashing still has
an eight-byte effective limit. Players must use game-only passwords. See
[Security](../SECURITY.md). An inside-network connection through the public
hostname is a router hairpin test, not an independent external reachability test.
