# Security Policy And Deployment Guide

Times of Chaos is legacy MUD software with modern packaging around a protocol
and password format designed long before current Internet security standards.
This document describes the actual boundaries so hosts and players can make
informed decisions.

## Reporting A Vulnerability

Report security issues privately to `j@jeremybean.com`. Include:

- affected revision or image
- deployment model and relevant configuration
- impact and who can trigger it
- minimal reproduction steps
- logs with passwords, tokens, hashes, IP addresses, and player data removed
- any proposed fix or mitigation

Do not open a public issue containing a working exploit, player file, password
hash, admin token, private log, or personally identifying information. Allow the
maintainer time to reproduce, patch, validate, and notify hosts before broad
disclosure.

The actively maintained target is the current `main` branch. Historical
revisions and archived utilities may retain known legacy weaknesses.

Current `password`, deletion guard/full command, `pkill`, `remort`, and
`resetpwd` entries are registered `LOG_NEVER` so their arguments are blanked
before command logging and snoop output. Treat logs from older revisions as
potentially containing remort or staff-reset passwords and restrict or purge
them according to incident/data-retention policy.

## Known Security Limitations

### Plain Telnet

The game protocol is unencrypted Telnet. Anyone able to observe traffic between
the player and host may read login names, passwords, private messages, commands,
and game output.

**Player rule:** use a unique game-only password and never reuse a valuable
credential.

**Host rule:** do not describe the base port as secure. Offer a trusted VPN,
SSH tunnel, TLS wrapper, or HTTPS/WSS browser path when confidentiality matters,
and explain which path players are actually using.

### Traditional DES Password Hashes

New passwords and password changes call `crypt(password, character_name)`. On
the supported Linux runtime, existing player hashes are traditional 13-character
DES `crypt` hashes.

Consequences:

- only the first eight password bytes affect the hash
- the effective salt is only the traditional two-character DES salt derived
  from the character name
- the format is intentionally fast and inexpensive to test offline
- a stolen player file should be treated as credential exposure
- adding characters after byte eight does not strengthen or meaningfully change
  the credential

This is compatibility behavior, not modern password storage. A future migration
should use a versioned password field and a slow, memory-hard password KDF such
as Argon2id, with transparent upgrade after a successful legacy login. Preserve
rollback and old-file compatibility during that work.

### Login Rate Limiting

Failed password attempts are counted per source address. After five failures
the address is refused at accept() time, before the greeting, with an
escalating backoff starting at 30 seconds and capped at 15 minutes. A
successful login clears the address, and history older than ten minutes
decays, so an honest player who mistypes is clear again shortly. The table is
a fixed 64 entries, so it cannot be used to exhaust memory; the least recently
active entry is recycled.

Blocks are logged and sent to WizInfo.

**Loopback is exempt by default.** The browser client bridges through the
dashboard on the same host, so every web player shares `127.0.0.1`.
Throttling it would let one fumbled web login lock out every web player,
which is a worse denial of service than the problem being solved, and a local
attacker already has host access. Set `TOC_THROTTLE_LOOPBACK=1` to include
loopback; the test suite uses this to exercise the code.

This bounds online guessing. It does nothing for an attacker who has already
stolen a player file, which remains the reason the DES hashes above matter.

### Dashboard Read Endpoints

`WEB_ADMIN_TOKEN` protects operational routes, but several read routes are
public at the application layer, including:

```text
/api/config
/api/areas
/api/rooms
/api/mobs
/api/objects
/api/area_health
/api/stats
/ws
```

Player-list and player-detail routes require the admin token. World data and
the browser-to-MUD bridge remain public at the application layer. Browser
WebSockets must be same-origin unless their complete origin is listed in
`WEB_ALLOWED_ORIGINS`; native clients without an Origin header remain
compatible. Binary and oversized browser-to-game frames are rejected. Do not
expose port 9001 to untrusted networks even when an admin token is configured.
Use firewall, loopback binding, VPN, or proxy authentication for the entire web
service.

### Shared Admin Token

The dashboard uses one shared `WEB_ADMIN_TOKEN` in `X-Admin-Token` for protected
HTTP routes. It does not provide per-user identity, roles, expiration, or an
operator audit trail. The log WebSocket accepts the token only as its first
message, keeping it out of URLs and ordinary reverse-proxy access logs.

Generated local installations also set `WEB_ADMIN_LOCAL_UNLOCK=1`. While
`WEB_ADMIN_BIND` is loopback and the page is opened through `localhost`,
`127.0.0.1`, or `::1`, the server can issue an HttpOnly, SameSite=Strict session
cookie derived from the admin token. The token itself is not exposed to page
JavaScript. This path is unavailable for non-loopback page hosts and is
disabled when the configured web bind is not loopback. Set
`WEB_ADMIN_LOCAL_UNLOCK=0` to require manual token entry even locally.

Treat the token as an immortal credential. Generate at least 32 random bytes,
store it outside Git, limit who can read it, and rotate it when staff access
changes or exposure is suspected.

### Local Command Queue

The dashboard writes immortal actions to `area/webadmin.queue`, and the game
consumes them. File write access to this queue is administrative access. Keep
the queue local, restrict filesystem permissions, bound dashboard inputs, and
do not place it on an untrusted shared volume.

### Player Files, Backups, And Logs

These can contain password hashes, account/game history, IP information,
private communication context, staff actions, and valuable persistent state.
They are sensitive even though they are plain files.

Protect:

```text
player/
player/versions/
gods/
heroes/
backups/
log/
.env
area/webadmin.queue
```

Do not commit real character data, attach it to public issues, or use it as a
test fixture. Encrypt off-host backups and restrict backup restore access.

This repository currently tracks a large legacy set of player, god, and hero
files, and the Dockerfile copies those tracked files into the runtime image.
Their password hashes must be considered publicly exposed. Character owners
must change any password reused elsewhere immediately, and hosts must not trust
the checked-in hashes as private credentials. Treat built images and registries
as sensitive until the runtime image is redesigned to initialize from a
sanitized seed set. The ignore rules prevent newly created character/staff files
from being added accidentally, but they do not remove data already tracked or
present in Git history.

## Recommended Network Layout

```text
Internet players ---- TCP 9000 ----> merc (plain Telnet; disclose risk)

Players/staff ----- VPN/SSH/HTTPS ----> 127.0.0.1:9001 web client/dashboard
                                           |
                                           +--> 127.0.0.1:9000 bridge
                                           +--> local queue/log/data
```

The dashboard should not be directly reachable from the public Internet.

### Compose Binding

The repository defaults both published ports to loopback. The automatic
installer writes the same safe defaults to `.env`. For a public game/private
dashboard, use:

```dotenv
MUD_BIND=0.0.0.0
MUD_PORT=9000
WEB_ADMIN_BIND=127.0.0.1
WEB_ADMIN_PORT=9001
```

Running `.\install.ps1 -Network Public` or `./install.sh --public` applies this
game-only exposure. Do not set `WEB_ADMIN_BIND=0.0.0.0` without a separate
authenticated and encrypted access layer.

`.dockerignore` excludes `.env`, player, god, hero, corpse, log, and backup
data from the image build context. Do not override those exclusions in a
private deployment; use the checked-in bind mounts for runtime state.

The container entrypoint begins as root only to map the `toc` account to the
configured `TOC_UID`/`TOC_GID` and adjust mounted runtime directories. It then
re-executes through `gosu`; the game and dashboard do not run as root. Never set
either ID to zero or replace this with a permanently root container.

### UFW Example

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 9000/tcp
sudo ufw enable
```

Do not allow port 9001 globally. Scope any direct rule to a trusted source
network.

## Admin Token Generation

Linux/macOS:

```bash
umask 077
printf 'WEB_ADMIN_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
```

Windows PowerShell 5.1 or newer:

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$token = -join ($bytes | ForEach-Object { $_.ToString('x2') })
Set-Content -LiteralPath .env -Value "WEB_ADMIN_TOKEN=$token" -Encoding ascii
```

The automatic installers perform this generation without displaying the token
and preserve an existing nonempty value.

Do not use an example value from documentation. Recreate the dashboard/container
after changing the environment.

## HTTPS Reverse Proxy

If the web client or dashboard must be available beyond loopback, use a
maintained reverse proxy with TLS and an additional identity layer.
Requirements:

- valid HTTPS certificate
- WebSocket upgrade support for `/ws` and `/ws/logs`
- proxy or VPN authentication before the request reaches FastAPI
- request body and connection limits
- no query-string logging for the protected log WebSocket
- same-origin public page and WebSocket URLs, or a narrowly scoped
  `WEB_ALLOWED_ORIGINS` value
- security updates and restrictive firewall rules
- dashboard listener still bound to loopback or a private network

TLS at the proxy protects browser-to-proxy traffic. It does not make direct TCP
port 9000 Telnet secure.

## Host Hardening Checklist

- Run as an unprivileged dedicated account/container user.
- Keep the OS, Docker, Python dependencies, compiler toolchain, and proxy
  patched.
- Expose only required ports.
- Bind the dashboard to loopback/private networking.
- Set a random admin token and rotate it on staff changes.
- Restrict `.env`, player data, queue, logs, and backups with filesystem ACLs.
- Keep production source and mutable data writable only where necessary.
- Use a private image registry while runtime images contain tracked legacy
  player/god/hero files.
- Never run the game or dashboard as root to work around a bind-mount problem.
- Keep an encrypted, versioned, off-host backup and test restoration.
- Monitor authentication anomalies, queue actions, unexpected reboots, archive
  failures, disk usage, and dashboard access.
- Preserve the first useful logs during an incident.
- Validate code and area data before deployment.
- Use isolated development/test player data.

## Application Hardening Priorities

The following improvements would materially strengthen ToC while preserving
legacy compatibility when implemented carefully:

1. Versioned Argon2id password hashes with successful-login migration from DES.
2. A TLS-capable player endpoint or a documented maintained TLS proxy path.
3. Authentication and authorization for every dashboard route, especially the
   MUD WebSocket bridge and detailed world data.
4. Per-operator accounts, roles, expiration, CSRF protection where applicable,
   and an immutable audit trail for dashboard actions.
5. Rate limiting and login abuse controls.
6. Replace shell-based archive creation/pruning with argument-safe process or
   library APIs and explicit path validation.
7. Minimize player/API fields and redact hashes, addresses, and private data.
8. Automated dependency and static security scanning in CI.
9. Documented secret rotation, data retention, breach notification, and secure
    deletion procedures for each production host.

These are roadmap recommendations, not claims about current implementation.

## Incident Response

### Exposed Admin Token

1. Restrict dashboard network access immediately.
2. Generate a new token and restart/recreate the dashboard process.
3. Review web/proxy logs and `area/webadmin.queue` for unauthorized actions.
4. Preserve evidence and record the exposure window.
5. Rotate adjacent credentials if they appeared in the same location.

### Stolen Player Files Or Backups

1. Stop further access and preserve relevant host/proxy audit evidence.
2. Determine which files, snapshots, and dates were exposed.
3. Notify affected players that hashes are fast to test offline and that reused
   passwords elsewhere must be changed immediately.
4. Rotate staff/admin credentials and dashboard tokens present in the affected
   material.
5. Correct the access path before restoring service.
6. Avoid publishing hashes or raw files during analysis.

### Suspected Queue Or Immortal Command Abuse

1. Disable or network-isolate the dashboard.
2. Preserve the queue, game log, dashboard/proxy logs, and deployed revision.
3. Stop automated restarts if destructive commands continue.
4. Compare player/world state against the latest verified backup.
5. Restore only confirmed damaged data and keep the pre-restore copy.
6. Rotate the token and review staff access.

### Malicious Or Corrupt Area Data

Do not load it into production. Preserve the file, run native validation and
the Python health suite in an isolated checkout, review generators and vnum
collisions, and deploy only a reviewed corrected revision.

## Player-Facing Security Notice

Hosts should publish a short notice equivalent to:

> This game uses an unencrypted Telnet connection and legacy DES password
> hashes. Use a unique game-only password of eight random characters and never
> reuse a password from another service. Do not send passwords to staff.

Do not imply that a long password is fully honored while the legacy DES format
remains active.

## Security Validation Before Release

- Confirm no real player/god files, `.env`, tokens, or private logs are staged.
- Review new API routes for explicit authentication status and data exposure.
- Test missing, wrong, and correct admin tokens.
- Test queue length/newline/control-character validation.
- Review every shell/process invocation and path boundary.
- Run compiler warnings, sanitizers for risky C changes, Python tests, area
  validation, and `git diff --check`.
- Inspect container user, published ports, bind mounts, and image contents.
- Verify clean shutdown, backup, restore, and rollback behavior.

See [Hosting Guide](wiki/hosting-guide.md),
[Operator Guide](wiki/operator-guide.md), and
[Developer Guide](wiki/developer-guide.md) for implementation procedures.
