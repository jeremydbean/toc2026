# Times of Chaos Web Admin Guide

The web admin is a private operations console for the Times of Chaos server.
It combines runtime status, parsed world inspection, area validation, protected
player lookup, gear analysis, a browser game connection, live logs, backups,
and queue-based administrative actions.

The interface is self-contained. CSS and JavaScript are served from
`webadmin/static/`; a running dashboard does not download fonts, frameworks,
icons, images, or terminal code from third-party CDNs.

The play-first browser client is available at `/client` and includes a compact
authenticated administration panel. See the [Game Client Guide](game-client-guide.md).

## Open The Dashboard

The automated installers start the dashboard with Docker and bind it to the
local machine by default:

```text
http://127.0.0.1:9001
```

Start a native development instance from the repository root with:

```bash
python -m webadmin.server \
  --host 127.0.0.1 \
  --port 9001 \
  --mud-host 127.0.0.1 \
  --mud-port 9000 \
  --queue area/webadmin.queue \
  --log-file log/toc.log \
  --area-path area \
  --backup-path backups \
  --player-path player
```

The legacy `python scripts/web_server.py` command is a compatibility launcher
for the same canonical server. It no longer starts a separate prototype.

## Authenticate

World data, status, maps, gear results, and the browser game bridge are
readable without an admin token. These capabilities require
`WEB_ADMIN_TOKEN`:

- player save names and parsed player profiles
- server logs and live log streaming
- backup archive listing and backup requests
- dashboard area-data refreshes
- WizInfo broadcasts
- immortal commands
- game shutdown

Select **Admin locked** in the lower-left corner, enter the token, and select
**Unlock**. The token is kept in session storage by default and disappears
when that browser session ends. **Remember on this browser** stores it in local
storage until it is replaced or browser storage is cleared.

An unset server-side token disables protected routes with HTTP `503`. An
incorrect token returns HTTP `403`.

Treat the token as an immortal credential. Keep the listener on `127.0.0.1`, a
private management network, or behind a VPN/reverse proxy with TLS and access
control. Do not publish port `9001` directly to the internet.

## Interface Sections

### Overview

Overview shows parsed area, room, mobile, and object totals; dashboard and game
reachability; the configured game endpoint; authentication state; and the
current area-health severity totals.

The dashboard status is always online when `/api/health` answers. Game status
is a short TCP reachability check against `MUD_HOST:MUD_PORT`; it does not prove
that login, area loading, or gameplay is healthy.

### World Database

World Database searches mobiles, objects, and rooms. Results are requested in
pages of 25, 50, or 100 records, so large worlds do not create thousands of
browser rows at once.

Select a row to inspect decoded flags, values, affects, descriptions, spawn
rooms, carried objects, exits, and related records. Data comes from the Python
area parser's current snapshot, not directly from live C structures.

### Areas And Health

**Health issues** shows the complete area-health report with severity and text
filters. Findings are paginated in the browser.

**Area catalog** searches area names, builders, filenames, and vnum ranges.
Select **Map** to open the computed room graph. Scroll over the map to zoom,
drag empty map space to pan, and select a room to open its detail record.

The map is a graph layout derived from exits. It preserves adjacency but may
move colliding rooms away from their exact compass grid position. Up/down and
disconnected components are also placed in available two-dimensional space.

### Players

Players reads extensionless, alphabetic save filenames from `PLAYER_PATH`.
Names are resolved case-insensitively while preserving their real filename
casing. Symlinks and invalid filenames are ignored.

The profile includes resources, class, guild, race, remorts, currency,
attributes, armor, active affects, learned skills, description, and equipped
objects. Password hashes and carried inventory are not returned.

### Gear Finder

Gear Finder ranks parsed objects for a selected class, race, and level. It
uses class-specific stat weights, object affects, race restrictions, wear
locations, and average weapon damage. Expand **Score details** to see the
calculation used for an item.

The result is an analysis aid, not an exact combat simulator. It does not model
every proc, spell interaction, resistance matchup, temporary affect, dual-wield
rule, or player preference.

### Game Console

Game Console opens a WebSocket bridge to the configured game endpoint. It uses
a command field with history instead of loading a third-party terminal library.
Basic Telnet negotiation and ANSI control sequences are removed from display;
password prompts switch the command field to masked input when the MUD requests
server-side echo handling.

The bridge is not token-protected because it behaves like another route to the
public game port. Network controls around the dashboard still apply.

### Live Logs

Live Logs requires admin authentication. **Connect** opens `/ws/logs` and sends
the token in the first WebSocket message, keeping credentials out of URLs and
proxy access logs. **Read latest** uses `GET /api/logs` for a bounded snapshot
of 1 to 5,000 lines.

The stream follows appends and detects truncation or rotation. The browser caps
retained terminal text so a long-running tab does not grow without bound.

### Operations

Operations contains the queue-backed administrative controls:

| Control | Result |
|---|---|
| Create backup | Queues `backup`; the game creates and prunes archives |
| Refresh dashboard data | Reparses area files and swaps in a validated snapshot |
| Shut down game | Queues `shutdown`; requires typing `SHUTDOWN` |
| WizInfo broadcast | Queues a staff message with a minimum level |
| Immortal command | Runs one command through the game's WebAdmin actor |

**Refresh dashboard data does not reload the running game world.** It updates
only the dashboard parser after rejecting snapshots with critical area-health
issues. Reboot or use the appropriate in-game workflow for live world changes.

Immortal commands have maximum trust and can alter live state. Queue payloads
reject newlines, control characters, and the `|` protocol delimiter, but the
meaning of an accepted command remains as powerful as entering it in game.

## HTTP And WebSocket Authentication

Protected HTTP requests send:

```text
X-Admin-Token: <WEB_ADMIN_TOKEN>
```

Validate a token without performing an operation:

```bash
curl -H "X-Admin-Token: $WEB_ADMIN_TOKEN" \
  http://127.0.0.1:9001/api/auth/check
```

The log WebSocket connects to `/ws/logs`, then sends this within five seconds:

```json
{"type":"auth","token":"<WEB_ADMIN_TOKEN>"}
```

Do not put the token in a WebSocket query parameter. The old
`?x_admin_token=` form is no longer accepted.

## Useful API Queries

Return only the area-health summary:

```text
GET /api/area_health?include_issues=false
```

Search and page mobiles or rooms:

```text
GET /api/mobs?q=ganon&limit=50&offset=0
GET /api/rooms?q=hyrule&limit=50&offset=0
```

Search and page objects:

```text
GET /api/objects?name=sword&min_level=20&max_level=40&limit=50&offset=0
```

List responses include `X-Total-Count`, the number of records matching the
query before `offset` and `limit` are applied.

The complete endpoint matrix is in the [Hosting Guide](hosting-guide.md).

## Troubleshooting

### Admin remains locked

Confirm the server process received `WEB_ADMIN_TOKEN`, recreate the container
after `.env` changes, and ensure the browser token matches exactly:

```bash
docker compose config
docker compose up -d --force-recreate
```

`GET /api/config` reports `admin_token_configured` but never returns the token.

### Game shows offline

Check the dashboard's configured endpoint and the game process:

```bash
curl -fsS http://127.0.0.1:9001/api/health
docker compose ps
docker compose logs --tail 100 game
```

For a split deployment, pass the reachable game address with `--mud-host` and
`--mud-port` or set `MUD_HOST` and `MUD_PORT`.

### Player list is empty

Unlock admin access, verify `PLAYER_PATH`, and confirm the dashboard account
can read regular player files. Directories, dotted files, names containing
nonletters, and symlinks are intentionally hidden.

### Logs say file not found

Verify `LOG_FILE` points to the same log written by the game and that the
dashboard process can read it. In Docker the standard path is
`/app/log/toc.log`.

### World changes do not appear

Use **Refresh dashboard data** after editing area files. If the refresh is
rejected, open **Areas and health** and resolve the critical findings. Changes
inside the running game still require its own reload or reboot procedure.

## Development Checks

Run the focused web-admin suite:

```bash
python -m unittest tests.test_webadmin_api -v
```

Run all repository validation before publishing:

```powershell
.\scripts\validate.ps1
```

The focused suite checks self-contained assets, API pagination, player privacy,
mixed-case save resolution, log authentication, bounded log tailing, queue
validation, and last-known-good parser reload behavior.
