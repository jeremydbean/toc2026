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

### Password Hashes

Since 2026-11-07 passwords are SHA-512 crypt (`$6$`, 5,000 rounds, a
16-character random salt), implemented in `src/password.c` and checked at
boot against the specification's test vectors (`tests/test_password.c` also
holds it to libxcrypt). Three kinds of hash can be in a player file:

- **SHA-512** (`$6$<salt>$...`): every password set since -- creation,
  PASSWORD, RESETPWD. Every byte counts.
- **Moved DES** (`$6$.8<salt>$...`): an old DES hash, moved at the player's
  first login since. It is the SHA-512 crypt of the password as DES read it
  -- the first eight bytes, seven bits each -- so the player types exactly
  what they always did and nothing else is accepted. Only eight characters
  still count until the player chooses a new password, and a DES hash of the
  same password remains in git history, so a moved hash is no stronger
  against an attacker holding that history; it is much slower to test than
  DES against one who does not.
- **DES** (13 characters): a character who has not logged in since. Read by
  the system's `crypt()` exactly as before, never written again.

A stolen player file should still be treated as credential exposure, and the
repository's history holds every DES hash ever synced. SHA-512 crypt is
salted and iterated, not memory-hard; a further move to Argon2id would follow
the same pattern (verify the old, rehash at login, mark the format).

If the SHA-512 self-test ever fails, the game logs a BUG, writes DES as it
always did and moves nothing. A rollback to code from before this change
still reads every `$6$` hash through libxcrypt, and a moved one for any
password of eight characters or fewer; a moved password typed longer than
eight characters would be refused by such code until the rollback is undone.

### Login Rate Limiting

Failed password attempts are counted per source address (an IPv6 /64
counts as one), in `src/loginlock.c` (owner, 2026-11-06: "if the wrong
password is entered over x times I want to ban the IP for x time.
Increasing with warning"):

- Every wrong password says how many more the address may make within 15
  minutes and how long the lockout will be.
- Five within 15 minutes lock the address out, refused before the greeting:
  15 minutes the first time, then 1 hour, 6 hours, 1 day and 7 days for
  each further lockout within a week. An address a player has logged in
  from in the last 90 days is locked out for an hour at most, so a
  forgotten password cannot shut a household out for a week.
- Lockouts and their history are kept in `log/login_lockouts.tsv` and read
  at boot: a reboot or a deploy does not lift them.
- A successful login clears the count only when every failure counted was
  for that same character; logging into one's own character between
  guesses at another's resets nothing.
- Failures are also counted per character across addresses: the character
  is told at their next login how many attempts were made and from how
  many addresses, and staff get a WizInfo when one character draws ten in
  an hour (guessing spread over many addresses).
- The table holds 1,024 addresses and never recycles a standing lockout
  while anything else will do, so it cannot be used to exhaust memory or
  to push a lockout out.

Lockouts are logged and sent to WizInfo; staff `DNS GUARD` lists them and
`DNS ALLOW <address>` lifts one.

**Loopback is exempt by default.** The browser client bridges through the
dashboard on the same host and names each player's real address in a PROXY
header, which is what is counted; a connection still on `127.0.0.1` is the
dashboard itself.
Throttling it would let one fumbled web login lock out every web player,
which is a worse denial of service than the problem being solved, and a local
attacker already has host access. Set `TOC_THROTTLE_LOOPBACK=1` to include
loopback; the test suite uses this to exercise the code.

This bounds online guessing. It does nothing for an attacker who has already
stolen a player file, which remains the reason the DES hashes above matter.

### Connection Guard

Scanners made up nearly all outside connections (13,977 from 982 addresses
between 2026-09-17 and 11-06; 951 of those addresses never logged in). The
game now (`src/connguard.c`, owner's rules of 2026-11-06):

- pauses an address **no player has logged in from in the last 90 days**
  for six hours after six connections in six hours that reach no password
  prompt, or twenty in a minute, doubling for each pause in a week, to
  seven days. A pause stops **new characters only**: a player on an
  address the guard does not know yet (a new ISP, a phone, a carrier's
  shared address) still logs in, and that lifts the pause. A connection
  the login prompt timed out, an MSSP poll and a web-bridge connection are
  never strikes;
- refuses a flood -- sixty connections in a minute -- before the greeting
  for an hour;
- tells staff, as WIZINFO, every pause, flood refusal and lifted pause, a
  new character or waiting connection refused, and the hourly count;
- never pauses or limits an address a player has logged in from in the last
  90 days, or is playing from now. Those addresses are kept in
  `log/player_addresses.tsv`: a line a day at most per address, measured
  from the last line that landed, every write checked and a failed one
  retried (`src/guardstore.c`). With no file yet it is started once from
  the login journals' records that name their own numeric address, never
  from a host name or a connection line joined to a later login;
- allows any address at most eight connections waiting to log in, and the
  whole game two hundred from addresses no player uses; refuses a
  descriptor `select()` could not hold (`FD_SETSIZE`);
- keeps pauses in memory: a restart lifts them, deliberately (the record of
  players' addresses is what is kept). That record is believed only when
  read whole -- an unreadable file is never taken for a missing one or
  written over -- and only record by record: a torn line, a time that
  overflows or lies more than a day ahead is refused, and every write
  error is kept, so a failed write is never mistaken for a saved one;
- trusts an address only after a login has passed every check: the
  password against the character as it stands now (in the game, or the
  file), then deny, ban and wizlock -- a refused login trusts nothing and
  clears no failures; staff notices naming a player go no lower than
  that player's wizinvis level;
- closes a connection that types nothing at the login prompts for ten
  minutes;
- looks up host names on a worker thread, and only for a connection that
  sends a line, so no connection can stall the game while a resolver
  answers.

An immortal's `BAN` is a separate list and still shuts out anybody. Every
connection keeps its address by family and bytes (`src/netaddr.c`) apart
from the host name the resolver may later put in its place: a ban on an
address (IPv4, or IPv6 in any spelling, stored canonically) matches that
address whatever DNS has done, and a ban on a host name is asked of the
resolved name, again when it arrives. Shared-address notices, SOCKETS IP
and DNS LIST read the address too; a shared address is reported as an
observation, not as proof of one person. Staff `DNS GUARD` lists pauses;
`DNS ALLOW <address>` (IPv4 or IPv6) lifts one. Loopback is
exempt (`TOC_GUARD_LOOPBACK=1` includes it for tests). This is no firewall:
a flood that fills the kernel's accept queue is a host's job (`ufw limit`,
fail2ban), below.

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

> **Self-host option.** This describes the Raspberry Pi appliance for running
> your own copy. The live `toc.jeremybean.com` server runs on Oracle Cloud --
> see [disaster-recovery.md](wiki/disaster-recovery.md).

The Raspberry Pi LAN appliance uses manual token entry because its dashboard
bind is not loopback. Its private `.env` is preserved across reboots, rebuilds,
and guarded Git updates, so the token remains stable until an operator rotates
it or replaces the file. **Remember on this browser** stores the supplied token
in that browser profile's local storage; **Lock**, clearing site data, or token
rotation removes or invalidates that convenience. Never include the token in a
URL, screenshot, repository file, issue, or chat transcript.

The Pi's Namecheap Dynamic DNS password is a separate domain-level credential.
Store it only in `/etc/toc2026/namecheap-ddns.env` with mode `0600`; never place
it in `.env`, a command-line URL, logs, screenshots, or Git. It is not the
Namecheap account password. Rotate it in Namecheap and on the Pi if exposure is
suspected. Publishing the game hostname does not make the dashboard safe for
the public internet: forward only TCP 9000, never TCP 9001.

### Read-Only Host Telemetry

`GET /api/host/status` and `GET /api/host/resources` are token-protected and
disabled unless `WEB_ADMIN_HOST_STATUS=1`. The full status route runs only fixed
`systemctl`, `journalctl`, and read-only local Git queries selected by server
code. The lightweight resource route reads only fixed `/proc`, thermal, and
root-filesystem sources; its rolling history exists only in the browser and is
bounded to 60 samples. Neither API accepts a command, unit, file path, journal
scope, or repository selector from the browser. Output is bounded and limited
to resource totals and rates, ToC unit/timer state, recent boot ranges, revision
metadata, and allowlisted operational journals.

The Raspberry Pi web service remains the unprivileged `toc` account. Its
supplementary `systemd-journal` membership permits read-only journal access but
does not grant sudo, arbitrary root-file access, or a shell. Keep this endpoint
behind the same private-network boundary as every other protected dashboard
route; system journals can still reveal operational timing and failure detail.

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
state/              an installed copy keeps all of the below in here
player/
player/versions/
gods/
heroes/
backups/
log/
.env
area/webadmin.queue
toc-backups/        what ./toc.sh backup writes: .env and state/ together
```

Do not commit real character data, attach it to public issues, or use it as a
test fixture. Encrypt off-host backups and restrict backup restore access.

The native Pi appliance implements this by encrypting the complete `player/`
snapshot with an age public recipient before pushing it to its dedicated
backup repository. The private recovery key stays off the Pi and outside Git.
The six-hour timer, successful remote push, and a periodic decrypt/list test
should all be checked; a ciphertext file alone is not proof of restorable data.

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

A dedicated appliance on a trusted, non-guest home LAN may instead use this
private-network layout:

```text
Trusted LAN browsers ---- TCP 9001 ----> Pi web client/dashboard
                                            |
                                            +--> 127.0.0.1:9000 bridge
Internet/router ---------- no forward ----X
```

This deliberately exposes the public world-read APIs and game bridge to every
device on that LAN. Keep `WEB_ADMIN_LOCAL_UNLOCK=0`, require the admin token for
operations, do not forward port 9001 on the router, and do not use this profile
on guest, campus, hotel, or other untrusted networks.

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
game-only exposure. Do not set `WEB_ADMIN_BIND=0.0.0.0` on an Internet-facing
or untrusted host. The checked-in `deploy/pi.env.example` is a narrow exception
for a dedicated trusted-LAN appliance; it still requires a strong token,
disables local auto-unlock, and assumes the router does not forward port 9001.

`.dockerignore` excludes `.env`, `state/`, player, god, hero, corpse, log, and
backup data, and the runtime files the game writes into `area/` (reports,
notes, bans), from the image build context, so neither a local build nor the
published `ghcr.io/jeremydbean/toc2026` image carries any of it. Do not
override those exclusions in a private deployment; use the checked-in bind
mounts under `state/` for runtime state.

A native install (`./install.sh --native`) keeps the game on `127.0.0.1` by
setting `TOC_BIND_ADDRESS` from `MUD_BIND`; without it the game listens on
every interface, so a hand-run `merc` on a public host needs a firewall.

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

For a private appliance whose trusted LAN is `192.168.1.0/24`, a scoped rule is:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 9001 proto tcp
```

Use the appliance's real LAN prefix; do not copy that example onto a different
network without checking it.

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

The native Pi updater likewise never replaces `.env`, so automatic updates do
not rotate the token. On a trusted Mac used to administer that Pi, the operator
can transfer it straight to the clipboard without echoing it:

```bash
ssh toc "sed -n 's/^WEB_ADMIN_TOKEN=//p' /home/toc/toc2026/.env" | pbcopy
```

This still places the credential in the macOS clipboard; paste it promptly and
do not run the command on an untrusted workstation.

The dedicated Pi profile installs distribution updates through a weekly
`toc2026-maintenance` systemd job rather than permitting Debian's generic daily
timer to install packages or reboot independently. It uses the distribution's
configured unattended-upgrade origins, requests a fresh encrypted player
snapshot before any required reboot, and relies on bounded systemd retry limits.
Review changes on `main`: validated updates may refresh the root-owned,
fixed-scope ToC unit files and recovery commands so resilience fixes do not
require a later SSH session.

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

1. Argon2id password hashes (SHA-512 crypt with login migration from DES is
   done, 2026-11-07).
2. A TLS-capable player endpoint or a documented maintained TLS proxy path.
   Planned and on hold (owner, 2026-11-07: "keep it on the table for a
   future project"), so Mudlet's Secure box works: nginx's stream module
   on the host terminating TLS on its own port (9443 proposed) with a
   Let's Encrypt certificate for toc.jeremybean.com, forwarding to the
   game on loopback with `proxy_protocol on` so the real address reaches
   `d->addr` as the web bridge's does; MSSP advertising the port (`TLS`)
   only once the terminator is up, so Mudlet can offer to switch; help and
   the website naming it. Owner steps: open the port (and 80 for the
   certificate, or use a DNS challenge) in the Oracle security list, and
   run a one-time setup script over SSH. Known gap to close with it: a
   proxied connection is exempt from the connection guard's strikes
   (`guard_proxied`), so the terminator should connect from its own
   loopback address (127.0.0.2) and only the web bridge keep that
   exemption.
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

> This game uses an unencrypted Telnet connection. Use a unique game-only
> password and never reuse a password from another service. Do not send
> passwords to staff.

A password chosen before 2026-11-07 still counts only its first eight
characters until the player changes it.

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
