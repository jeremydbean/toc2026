# Times of Chaos Hosting Guide

This guide covers installation, configuration, service management,
persistence, backup, upgrades, monitoring, the web dashboard, and production
hardening. Docker Compose is the recommended deployment. Native Linux is useful
for development and controlled hosts; Windows should use Docker Desktop or WSL
2 rather than a direct Win32 build.

## Deployment Model

ToC has two cooperating processes:

1. `merc`, the single C game server, listens on the MUD Telnet port (default
   `9000`) and reads world data relative to `area/`.
2. `webadmin.server`, an optional FastAPI process, listens on the dashboard port
   (default `9001`), parses area/player data, and writes administrative actions
   to `area/webadmin.queue` for the C server to consume.

The dashboard is not required to play. It should normally be private even when
the game port is public.

## Security Decisions Before Installation

Read [SECURITY.md](../SECURITY.md) before opening firewall ports. At minimum:

- Use a unique, random `WEB_ADMIN_TOKEN`.
- Bind the dashboard to `127.0.0.1` or restrict port 9001 by firewall/VPN.
- Do not assume the admin token protects every dashboard route. Player list and
  player detail endpoints are public to any client that can reach the port.
- Remember that game login uses unencrypted Telnet and legacy DES hashes.
- Protect `player/`, `gods/`, `backups/`, and logs as sensitive data.
- Keep encrypted off-host backups and test restoration.

## Docker Compose Quick Start

### Requirements

- Git
- Docker Engine with the Compose plugin, or Docker Desktop
- Approximately 2 GB free disk for build layers, image, logs, and backups
- Ports 9000 and 9001 free on the host, unless you change them

### Linux Or macOS

```bash
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026

umask 077
printf 'WEB_ADMIN_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env

docker compose up --build -d
docker compose ps
docker compose logs -f game
```

### Windows PowerShell

```powershell
git clone https://github.com/jeremydbean/toc2026.git
Set-Location toc2026

$tokenBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($tokenBytes)
$token = [Convert]::ToHexString($tokenBytes)
Set-Content -LiteralPath .env -Value "WEB_ADMIN_TOKEN=$token" -Encoding ascii

docker compose up --build -d
docker compose ps
docker compose logs -f game
```

Test locally:

```text
MUD client: localhost:9000
Dashboard:  http://localhost:9001
Health:     http://localhost:9001/api/health
```

The `.env` file is ignored by Git. On a shared host, restrict its permissions
and do not paste its token into tickets or chat.

## Production Port Binding

The checked-in Compose file maps both ports on every host interface:

```yaml
ports:
  - "9000:9000"
  - "9001:9001"
```

For a typical public server, leave the game port public but change the
dashboard mapping to loopback:

```yaml
ports:
  - "9000:9000"
  - "127.0.0.1:9001:9001"
```

Then reach the dashboard through an SSH tunnel, VPN, or authenticated HTTPS
reverse proxy. Example SSH tunnel from an administrator workstation:

```bash
ssh -L 9001:127.0.0.1:9001 user@mud-host
```

Open `http://127.0.0.1:9001` locally while the tunnel is active.

If the dashboard is not needed, set this in Compose and remove its published
port:

```yaml
environment:
  - WEB_ADMIN_ENABLED=0
```

## Compose Lifecycle

```bash
# Build and start/recreate as needed.
docker compose up --build -d

# Show container and port state.
docker compose ps

# Follow combined entrypoint, game, and dashboard output.
docker compose logs -f --tail 200 game

# Stop while preserving the container and bind-mounted data.
docker compose stop

# Start an existing stopped container.
docker compose start

# Recreate after configuration changes.
docker compose up -d --force-recreate

# Remove the container/network; host bind mounts remain.
docker compose down
```

The service uses `restart: unless-stopped`. Docker applies that policy even
when the entrypoint exits cleanly after an in-game `shutdown`. Use
`docker compose stop` or `docker compose down` when the instance must stay off.

The entrypoint itself runs `merc` in a loop. An in-game `reboot` or unexpected
game exit restarts `merc` after five seconds. An in-game `shutdown` writes
`area/shutdown.txt`, causing the entrypoint to exit cleanly.

## Container Entrypoint Modes

With no arguments, the entrypoint starts the dashboard once and runs the
auto-restarting game loop. Build a standalone image first, then explicit
arguments use one-shot behavior:

```bash
docker build -t toc2026 .

# Normal Compose/default mode.
docker compose up -d

# One-shot game server on the configured port.
docker run --rm toc2026 server

# One-shot game server on an explicit port.
docker run --rm toc2026 9500

# Start with new-character creation locked.
docker run --rm toc2026 newlock 9000

# Run another image command.
docker run --rm -it toc2026 bash
```

For routine operation, prefer Compose so persistence and ports remain
consistent.

## Configuration Reference

### Environment Variables

| Variable | Default | Used by | Meaning |
|---|---:|---|---|
| `PORT` | `9000` | Docker entrypoint | Primary game port; takes precedence |
| `MUD_PORT` | `9000` | Entry point/dashboard | Fallback game port and WebSocket bridge target |
| `WEB_ADMIN_ENABLED` | `1` | Docker entrypoint | `0` prevents dashboard startup |
| `WEB_ADMIN_HOST` | `0.0.0.0` | Docker entrypoint | Dashboard bind address |
| `WEB_ADMIN_PORT` | `9001` | Dashboard | Dashboard port and health check target |
| `WEB_ADMIN_TOKEN` | unset | Dashboard | Shared secret; protected routes return 503 when unset |
| `QUEUE_PATH` | `area/webadmin.queue` | Dashboard | Queue used to communicate with `merc` |
| `LOG_FILE` | `log/toc.log` | Dashboard | Log file used by tail endpoints |
| `AREA_PATH` | `area` | Dashboard | Area data parsed for browsing and health |
| `BACKUP_PATH` | `backups` | Dashboard | Archive directory listed by the API |
| `PLAYER_PATH` | `player` | Dashboard | Player files parsed by player endpoints |

The Docker entrypoint supplies absolute queue and log paths on its command line.
Command-line arguments override the matching dashboard environment defaults.

When changing the game port, set both `PORT` and `MUD_PORT` to the same
container port and update the Compose mapping. The entrypoint listens according
to `PORT`, while the dashboard bridge reads `MUD_PORT`; changing only one leaves
the browser bridge pointed at the wrong socket.

### Dashboard Command-Line Arguments

```text
python -m webadmin.server [options]

--host <address>          default 0.0.0.0
--port <number>           default 9001
--queue <path>            default area/webadmin.queue
--log-file <path>         default log/toc.log
--area-path <path>        default area
--backup-path <path>      default backups
```

Run the module from the repository root so the default `PLAYER_PATH=player`
also resolves correctly.

## Persistent Data And Permissions

The runtime image currently includes the repository's tracked legacy player,
god, and hero files. Those hashes are present in public Git history and must not
be treated as private credentials. Use a private image registry, rotate reused
passwords, and plan a sanitized initialization model before distributing an
image. Container-local changes disappear when the container is replaced. The
checked-in Compose file persists:

```text
./player  -> /app/player
./log     -> /app/log
./backups -> /app/backups
```

If the host relies on mutable immortal/hero files, add:

```yaml
volumes:
  - ./gods:/app/gods
  - ./heroes:/app/heroes
```

Consider persisting `corpse/` only if the local gameplay policy requires corpse
state to survive container replacement. Do not mount the entire repository over
`/app`; that can hide the built image and create confusing version skew.

The container runs as the non-root `toc` user. If bind mounts are not writable,
fix ownership/ACLs on the host rather than running the game as root. On Linux,
inspect the image user ID before applying ownership:

```bash
docker run --rm toc2026 id
docker compose exec game id
```

Never solve a permissions problem with world-writable player files.

## Backup Model

ToC has two local backup layers:

1. **Player snapshots:** before eligible character saves, the prior player file
   is copied to `player/versions/<Name>/`. At most 30 snapshots are retained per
   player, and snapshots are throttled to one every 30 minutes.
2. **Player archives:** the running game creates a timestamped `tar.gz` archive
   every four hours and a daily archive every 24 hours. Archives older than 30
   days are pruned.

Immortal commands:

```text
backup                 show the next scheduled archive times
backup now             create the four-hour style archive immediately
backup daily           create the daily archive immediately
prestore <player>      list numbered player snapshots
prestore <player> <n>  restore a selected snapshot
```

`prestore` validates the selection, protects the current file with a safety
copy, and replaces through a temporary file. Follow its live output and ensure
the affected player is disconnected before restoration.

### Off-Host Backup

Local snapshots do not protect against host loss, ransomware, disk corruption,
or accidental deletion of the whole project. Back up at least:

```text
player/
gods/
heroes/
backups/
area/ and data/ if the host has unpublished world changes
.env or a separately managed replacement secret
```

Encrypt the backup because player files contain password hashes, IP/history
fields, and gameplay data. Keep more than one retention tier and perform a test
restore on a non-production copy.

### Archive Restore Procedure

1. Announce maintenance and stop the Compose service.
2. Copy the current `player/` directory to a separate safety location.
3. Extract the selected archive into a new staging directory, not directly over
   production.
4. Inspect the archive's paths and compare the staged player count and recent
   files with expectations.
5. Replace only the intended data, preserving ownership and permissions.
6. Start the server and verify logins, `diagnostics`, and recent character
   state before declaring the restore complete.

Archive layout is produced by running `tar` from `area/` against `../player`.
Always inspect with `tar tzf <archive>` before extracting because `tar`
normalizes parent-path components differently across implementations.

## Native Linux Deployment

### Build

```bash
sudo apt update
sudo apt install build-essential libcrypt-dev python3 python3-venv
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make clean
make
cd area
../merc --check-area
cd ..
```

Run once in the foreground:

```bash
cd area
../merc 9000
```

Run with the checked-in restart/log wrapper:

```bash
./startup.sh 9000
```

The root compatibility file named `startup` and `area/startup.sh` both delegate
to the maintained root `startup.sh`. Use `startup.sh` directly in new service
definitions.

Other retired root names are now safe compatibility helpers: `install`
delegates to `scripts/setup_linux.sh`, `cleanup` only runs `make clean`, and
`refresh` performs a clean build plus native area validation without killing or
restarting any process. Files under `zStartup/` are archived history and must
not be used on a current host.

### systemd Example

Install the repository at `/opt/toc2026`, create an unprivileged `toc` account,
make the runtime directories writable by that account, and create
`/etc/systemd/system/toc2026.service`:

```ini
[Unit]
Description=Times of Chaos MUD
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=toc
Group=toc
WorkingDirectory=/opt/toc2026
ExecStart=/opt/toc2026/startup.sh 9000
Restart=on-failure
RestartSec=10
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now toc2026
sudo systemctl status toc2026
sudo journalctl -u toc2026 -f
```

`startup.sh` already restarts `merc`; the systemd restart policy covers failure
of the wrapper itself. Run the dashboard as a separate restricted service, or
use Docker for the combined deployment.

## Native Dashboard Installation

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r webadmin/requirements.txt

export WEB_ADMIN_TOKEN="$(openssl rand -hex 32)"
python -m webadmin.server \
  --host 127.0.0.1 \
  --port 9001 \
  --queue area/webadmin.queue \
  --log-file log/toc.log \
  --area-path area \
  --backup-path backups
```

Use a process supervisor for production. Ensure the dashboard and game share
the same queue path and filesystem. The queue is local inter-process
communication, not a network message bus.

## Dashboard API Reference

### Authentication

Protected HTTP routes require:

```text
X-Admin-Token: <WEB_ADMIN_TOKEN>
```

If no token is configured, protected HTTP routes return `503`. A wrong token
returns `403`. The protected log WebSocket uses the query parameter
`x_admin_token`; keep reverse-proxy access logs from recording that URL.

Example:

```bash
curl -H "X-Admin-Token: $WEB_ADMIN_TOKEN" \
  http://127.0.0.1:9001/api/backups
```

### Publicly Reachable Browsing Routes

These routes do not check the admin token:

| Method and path | Purpose |
|---|---|
| `GET /` | Dashboard application |
| `GET /api/health` | Game/dashboard process and port health |
| `GET /api/stats` | Parsed world totals |
| `GET /api/area_health` | Area-health summary and findings |
| `GET /api/players` | Parsed player list |
| `GET /api/player/{name}` | Parsed player detail |
| `GET /api/mobs` | Mobile list/search |
| `GET /api/mobs/{vnum}` | Mobile detail |
| `GET /api/rooms` | Room list/search |
| `GET /api/rooms/{vnum}` | Room detail |
| `GET /api/areas` | Area list |
| `GET /api/areas/{filename}/map` | Computed area map |
| `GET /api/objects` | Object list/search |
| `GET /api/objects/{vnum}` | Object detail |
| `GET /api/best_gear` | Class/race/level gear ranking |
| `WS /ws` | Browser-to-MUD bridge |

`GET /api/best_gear` requires `class_name`; optional query parameters are
`race_name` (default `human`), `level` (default `50`), and `limit` (default `5`,
maximum `50`). Example:

```text
/api/best_gear?class_name=warrior&race_name=dwarf&level=40&limit=10
```

Because player endpoints and the game bridge are public at the application
layer, restrict the entire dashboard listener at the network/proxy layer.

### Token-Protected Operational Routes

| Method and path | Purpose |
|---|---|
| `GET /api/logs?lines=200` | Tail 1-5,000 log lines |
| `WS /ws/logs?x_admin_token=...` | Stream logs |
| `POST /api/wizinfo` | Queue an in-game staff broadcast |
| `POST /api/command` | Queue an immortal command |
| `POST /api/backup` | Queue a player archive backup |
| `GET /api/backups` | List up to 100 backup archives |
| `POST /api/shutdown` | Queue an intentional shutdown |
| `POST /api/reload` | Reparse dashboard area data after validation |

`POST /api/reload` swaps the dashboard parser only after the new parse has no
critical area-health findings. It does **not** reload the live C server's world.
World changes require the appropriate game reboot/restart procedure.

`POST /api/command` is equivalent to a high-impact administrative console.
Protect the token as an immortal credential and do not expose the route through
a public browser session without TLS.

## Monitoring And Health

### Container Checks

```bash
docker compose ps
docker compose logs --tail 200 game
docker stats toc2026_game
docker compose exec game ps -ef
```

### HTTP Health

```bash
curl -fsS http://127.0.0.1:9001/api/health
curl -fsS http://127.0.0.1:9001/api/stats
```

The health endpoint reports process/port observations. A successful HTTP
response does not prove players can authenticate or the entire world booted
without data errors; check `log/toc.log` and perform a real client smoke test.

### In-Game Diagnostics

Immortals can use:

```text
diagnostics
backup
memory
sockets
```

`diagnostics` reports boot time, world totals, descriptor counts, list health,
active mobiles, and backup schedule. The exact command set is trust-level
dependent; see [Operator Guide](operator-guide.md).

## Updating A Running Host

Use a maintenance window for code or area changes.

1. Review release notes and local changes with `git status`.
2. Run `backup now` and verify a new archive exists.
3. Copy mutable data off-host or take a host snapshot.
4. Stop the service.
5. Fetch/update code without overwriting local unpublished changes.
6. Run the full validation suite.
7. Rebuild the image or native binary.
8. Start in the foreground or inspect logs immediately.
9. Test a player login, world movement, save, dashboard health, and backup list.

Docker example for a clean tracking branch:

```bash
git fetch origin
git pull --ff-only
bash scripts/validate.sh
docker compose build --pull
docker compose up -d
docker compose logs -f --tail 200 game
```

Do not update a dirty production checkout blindly. Preserve local area work on
a branch or in a separate deployment artifact before changing revisions.

### Rollback

Keep the previous image tag or release directory until the new version has
passed login/save tests. Roll back code and world data together when their
formats changed. Restore player data only when the failed deployment actually
modified it; otherwise retain the newest valid character files.

## Firewall Baseline

Example with UFW when port 9000 should be public and dashboard access comes
through SSH/VPN:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 9000/tcp
sudo ufw enable
```

Do not add a public 9001 rule. If a specific administration network must reach
it directly, scope the allow rule to that source and still use TLS.

## Raspberry Pi And ARM

Docker builds locally for the host architecture and is the simplest Raspberry
Pi path. Use a supported 64-bit Raspberry Pi OS or Ubuntu release, install
Docker/Compose, clone the repository, generate `.env`, and run the same Compose
quick start. Build time will be longer than on a desktop, so monitor free disk,
memory pressure, temperature, and SD-card wear. Store mutable data and backups
on reliable storage and maintain an off-device copy.

The historical wiki filename for Raspberry Pi/Ubuntu/WSL is retained for old
links, but its obsolete Ubuntu 18.04 instructions have been replaced by a
pointer to this guide.

## Troubleshooting

### Port Already In Use

```bash
docker compose ps
sudo ss -ltnp | grep -E ':9000|:9001'
```

Stop the conflicting service or change both the host mapping and corresponding
environment value. Do not change only one side of a `host:container` mapping.

### Game Starts From The Wrong Directory

The C server expects `area/` as its working directory. Correct native forms:

```bash
cd area
../merc 9000
# or, for CMake:
../bin/rom 9000
```

Running `./merc` from inside `area/` is wrong for the current Make output.

### Areas Fail To Load

Run:

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

Confirm the file is listed in `area/area.lst`, uses Latin-1-compatible content,
has valid sections, and does not collide with existing vnums.

### Dashboard Returns 503 On Admin Actions

`WEB_ADMIN_TOKEN` is unset in the dashboard process. Set it, recreate/restart
the service, and provide the same value through `X-Admin-Token`.

### Dashboard Returns 403

The provided token differs from the process environment. Check for trailing
whitespace, an old browser-stored token, a changed `.env`, or a container that
was not recreated after configuration changed.

### Dashboard Shows Stale World Data

Use the protected dashboard reload after validating files, or restart the
dashboard. Remember that this only refreshes dashboard parsing. Reboot `merc`
to load area changes into the game.

### Bind-Mount Permission Errors

Inspect `docker compose exec game id` and host ownership. On SELinux hosts,
apply the appropriate container volume label (`:Z` for a private bind mount)
according to local policy. Do not disable SELinux globally or make player files
world writable.

### Container Reappears After Shutdown

`restart: unless-stopped` restarts a cleanly exited container. Use
`docker compose stop` or change the deployment's restart policy to match the
desired in-game shutdown semantics.

### Backups Are Empty Or Missing

Confirm `backups/` is writable, `tar` and `find` exist in the runtime, the game
has reached its scheduled interval, and logs contain no `do_backup` errors.
Trigger `backup now`, then inspect both the in-game response/log and host
directory.

### Player Cannot Log In After Restore

Stop repeated attempts, preserve the current file, compare the restored player
name/capitalization and file permissions, and inspect the safety snapshot. Use
`prestore` for a single character when possible rather than extracting an
entire archive over a running server.

## Related Documentation

- [Operator Guide](operator-guide.md)
- [Developer Guide](developer-guide.md)
- [Validation And Area Health](validation-and-area-health.md)
- [Security](../SECURITY.md)
- [README](../README.md)
