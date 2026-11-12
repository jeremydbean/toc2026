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

A dashboard whose bind is not loopback -- the live Oracle host's, for one
(see [disaster-recovery.md](../wiki/disaster-recovery.md)) -- uses manual token
entry. **Remember on this browser** stores the supplied token in that browser
profile's local storage; **Lock**, clearing site data, or token rotation
removes or invalidates that convenience. Never include the token in a URL,
screenshot, repository file, issue, or chat transcript.

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

The unit names come from `TOC_HOST_SERVICE_UNITS`, `TOC_HOST_TIMER_UNITS` and
`TOC_HOST_JOURNAL_UNITS` in the dashboard's environment (`deploy/toc-restore`
writes the Oracle host's), defaulting to the `toc-*` units in
`deploy/windows-vm/`. The live host's web service runs as the unprivileged
`toc` account; reading the journal needs `systemd-journal` group membership,
which grants read-only journal access but not sudo, arbitrary root-file access,
or a shell, and without it the journal panels report themselves unavailable.
Keep this endpoint behind the same boundary as every other protected dashboard
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

`deploy/sync-player-backup.sh` (the `toc-player-backup` timer) implements
this by encrypting the complete `player/` snapshot with an age public
recipient before pushing it to a dedicated private backup repository. The
private recovery key stays off the host and outside Git. The six-hour timer,
successful remote push, and a periodic decrypt/list test should all be
checked; a ciphertext file alone is not proof of restorable data.

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

The dashboard should not be directly reachable from the public Internet. A
LAN-only dashboard exposes the public world-read APIs and game bridge to every
device on that LAN: keep `WEB_ADMIN_LOCAL_UNLOCK=0`, require the admin token
for operations, do not forward port 9001 on the router, and do not use it on
guest, campus, hotel, or other untrusted networks.

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
or untrusted host.

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

For a private host whose trusted LAN is `192.168.1.0/24`, a scoped rule is:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 9001 proto tcp
```

Use the host's real LAN prefix; do not copy that example onto a different
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

On the live host the token lives in `/etc/toc/web.env` (mode 600, root);
`toc-deploy` never replaces it. Read it there with `sudo` and never print it.

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

## Planned: A TLS Player Port For Mudlet's Secure Box

**Status: planned and on hold** (owner, 2026-11-07: hold off on TLS, "keep
it on the table for a future project"). Nothing in this section is
implemented or deployed. It is written so the project can be picked up
without re-deriving it; until the owner takes it off hold, port 9000 stays
the only native-client port and nothing advertises another.

Every claim below is marked one of three ways:

- **[source]** -- read in this repository's code, with the file and
  function named. True of `main` as of 2026-11-09; recheck before relying
  on it, since `src/comm.c` and `src/loginlock.c` change often.
- **[host]** -- needs verification on the Oracle host
  (`toc.jeremybean.com`, an Always Free ARM (aarch64) Ubuntu 24.04
  instance) or in the OCI console.
- **[mudlet]** -- needs a real Mudlet test; Mudlet's documentation is not
  reachable from a cloud session and its behaviour changes by version.

### Status And Scope

In scope: TLS-wrapped Telnet for native clients -- Mudlet's "Secure"
connection box, and any client that can open a TLS socket -- terminated by
nginx's `stream` module on the host and handed to the game over loopback
with a PROXY protocol v1 header. Certificate issuance, renewal, TLS
handshakes and their resource cost all stay outside the game process and
outside the game loop.

Out of scope, and **not** secured by this work:

- port 9000, which stays plain Telnet throughout;
- the browser client and dashboard on 9001, which the live host serves as
  plain HTTP on every interface [source: `deploy/windows-vm/toc-web.service`
  runs `webadmin.server --host 0.0.0.0 --port 9001`;
  `wiki/disaster-recovery.md` lists `:9001` as public]. HTTPS/WSS for the
  browser path is a separate project (see "HTTPS Reverse Proxy" above);
- TLS inside `merc` (OpenSSL in the game loop) and the Telnet START-TLS
  option. Both were considered and rejected: the first puts handshakes
  and certificate reloads on the single game thread, which AGENTS.md's
  "Nothing on the game loop may wait" rule forbids in spirit; the second
  has no Mudlet support [mudlet].

### Recommended Defaults

| Choice | Default | Why |
| --- | --- | --- |
| Terminator | nginx `stream` from Ubuntu's packages (`nginx` + `libnginx-mod-stream`) | maintained, small, reloads without dropping sessions [host] |
| Public TLS port | `9443/tcp` (proposed), IPv4 | no conflict with 9000/9001 [host: `ss -ltnp`] |
| IPv6 | off until verified end to end | never advertise a family that does not work |
| Backend | a second, loopback-only game listener, `127.0.0.1:9002` (proposed) | header required there; the public 9000 keeps today's rules |
| nginx to game | PROXY protocol v1, `proxy_protocol on;` in the `server` block | the format `proxy_header_accept()` already parses [source] |
| Source binding | `proxy_bind 127.0.0.2;` plus a peer check in the game | hygiene, not authentication (below) |
| TLS versions | TLSv1.2 and TLSv1.3, session tickets off | Mozilla "intermediate"; old Mudlet builds [mudlet] |
| Certificate | Let's Encrypt via Ubuntu's `certbot`, HTTP-01 webroot, `certbot.timer` | unattended; needs only port 80 |
| Handshake / connect / idle | `ssl_handshake_timeout 10s`, `proxy_connect_timeout 5s`, `proxy_timeout 24h` | see "Limits And Availability" |
| Client keepalive | `so_keepalive=120s:30s:4` on the listen | mirrors the game's own (below) |
| Connection caps | 10 per address, 300 in total | under the game's 1,024 descriptor ceiling |
| MSSP advertisement | off; on only when `TOC_MSSP_TLS_PORT` is set | enabled after the port works from outside |
| Plaintext auto-login on 9000 | still allowed during transition | refusing it is an owner decision |

### Architecture And Trust Boundary

```text
Mudlet (Secure) --TLS--> :9443 nginx stream --PROXY v1 + bytes--> 127.0.0.1:9002 merc (kind: tls)
  [peer 127.0.0.2 via proxy_bind]
Mudlet / telnet --plain--> :9000 ----------------------------------> merc (kind: direct)
Browser --HTTP/WS--> :9001 webadmin /ws --PROXY v1 + bytes--> 127.0.0.1:9000 merc (kind: bridge)
Local probes (toc-game-probe, probe_game) --plain, no header--> 127.0.0.1:9000 merc (loopback)
```

**What the code does today** [source]:

- There is one listening socket, IPv4 only: `init_socket()` in
  `src/comm.c` makes an `AF_INET` socket, binds `TOC_BIND_ADDRESS` when set
  (an IPv4 address only) or every interface, and `game_loop_unix()` selects
  on that single `control` descriptor. The live unit sets no
  `TOC_BIND_ADDRESS`, so 9000 listens on every interface
  [source: `deploy/windows-vm/toc-game.service`].
- At accept, `new_descriptor()` fills `d->addr`, `d->addr_text`, `d->host`
  and `d->ip` (`net_addr_guard_key`) from `getpeername()`, and
  `init_descriptor()` asks `conn_guard_admit()` and
  `login_lock_remaining()`/`login_lock_refusal()`, then sends the Telnet
  offers (`telnet_offer_options()`) and the greeting -- all before any
  PROXY header can arrive.
- `nanny()`, `CON_GET_NAME`: on the connection's first line only
  (`d->first_line_read`), `proxy_header_accept()` is tried. It trusts a
  header from any 127/8 peer (`is_loopback_ip(d->ip)`) and **overwrites**
  `d->addr`, `d->addr_text`, `d->host` and `d->ip` with the header's
  source. Nothing records the original TCP peer afterwards.
- **Every accepted header sets `d->guard_proxied = TRUE`** -- including
  `PROXY UNKNOWN` and a header naming a loopback source, for which
  `proxy_header_accept()` also returns true. `conn_guard_closed()` in
  `src/connguard.c` never counts a strike for a `guard_proxied`
  connection: that is the browser bridge's reload exemption. A TLS
  terminator using today's path would inherit it, so a TLS scanner that
  completes a handshake and hangs up would never be paused. **Giving the
  terminator a different loopback source (127.0.0.2) does not fix this by
  itself**: the nanny does not look at the peer, only at whether the
  header was accepted.
- After an accepted header the nanny re-asks `login_lock_remaining()` and
  `conn_guard_admit()` for the real address, then `connection_spoke()`
  logs `Sock.sinaddr` and queues the DNS lookup. That re-check is right
  and the TLS path must keep it.
- A loopback connection that sends **no** header stays loopback: exempt
  from lockouts (`lock_applies()` in `src/loginlock.c`), from the guard
  (`guard_applies()`/`guard_watches()` in `src/connguard.c`), from
  shared-address notices (`wizinfo_same_host()` skips loopback) and from
  the `Sock.sinaddr` log line. On a terminator path that is fail-open: a
  missing `proxy_protocol on;` would make every TLS player "loopback".
- The parser is lenient: `str_prefix()` is case-blind, so `proxy tcp4 ...`
  is accepted; only the source field is parsed (destination address and
  ports are not checked); `TCP6` accepts an IPv4 source; leading spaces
  are stripped by the nanny. There is no deadline or byte cap specific to
  the header -- only the generic line reader (`read_from_descriptor()`,
  `inbuf` of 4 x `MAX_INPUT_LENGTH`) and `login_idle_sweep()`'s
  `LOGIN_IDLE_SECS` (600 s), which every read refreshes through
  `d->input_at`.

**The design.** Classify every connection **at accept**, before any header
can change its address, and never re-derive the class from the address:

- New descriptor fields (`src/merc.h`): `transport_addr` (a `NET_ADDR`,
  the TCP peer from `getpeername()`, never overwritten), `listener` (which
  listening socket accepted it) and `conn_kind`
  (`CONN_DIRECT`, `CONN_BRIDGE`, `CONN_TLS`). `d->addr`/`addr_text`/`ip`
  remain the **canonical player address**, the only thing bans, lockouts,
  the guard, trust records, shared-address notices and the journals read.
  The transport address is for staff diagnostics only.
- Header rules by listener:

  | Listener | TCP peer | First line | Result |
  | --- | --- | --- | --- |
  | public 9000 | not loopback | anything | `CONN_DIRECT`; a PROXY line is an ordinary (refused) name, as today |
  | public 9000 | loopback | valid PROXY | `CONN_BRIDGE`; `guard_proxied` set, as today |
  | public 9000 | loopback | no PROXY | `CONN_DIRECT` on loopback; exempt as today (the health probes) |
  | TLS backend | in the peer allowlist | valid strict TCP4/TCP6 | `CONN_TLS`; **`guard_proxied` never set** |
  | TLS backend | anything else, or no valid header in time | -- | closed; the line is never read as a name, a password or a login |

- **TLS is never inferred from "proxied".** The bridge is proxied and is
  itself plain HTTP on the live host. Only `conn_kind == CONN_TLS`, which
  only the TLS backend listener can set, means the player's leg was
  encrypted -- and even that is nginx's word, not the game's.
- **Who may send headers.** Recommended default: a dedicated listener on
  `127.0.0.1:<backend port>` that the game binds to loopback whatever
  `TOC_BIND_ADDRESS` says, requires a header, and accepts connections only
  from an allowlist of transport peers (`TOC_TLS_PEERS`, default
  `127.0.0.2`, matching `proxy_bind`). The public listener keeps accepting
  a header from loopback for the bridge, unchanged.
- **This is a routing convention, not authentication.** On Linux any local
  process, of any user, can connect to a loopback port and can bind any
  127/8 source address, so it can impersonate nginx and claim any player
  address -- the same exposure the bridge path has today, and consistent
  with "a local attacker already has host access" above. The box runs
  only the game's services [host]. If that ever changes, the stronger
  option is a Unix-domain backend socket (`proxy_pass unix:/run/toc/tls.sock;`)
  owned by the game's user with group access for nginx's worker user only:
  file permissions are real authentication. It needs an `AF_UNIX`
  listener in `src/comm.c`; it is listed as an owner decision.

### nginx-To-Game Protocol

**Two directives that are easy to confuse:**

- `listen 9443 ssl;` makes nginx accept ordinary TLS clients. Mudlet's
  Secure box speaks exactly this.
- `proxy_protocol on;` (a `server`-level directive in `stream`) makes
  nginx **send** a PROXY header to the backend. It is what we want.
- **Never** write `listen 9443 ssl proxy_protocol;`. That `proxy_protocol`
  parameter makes nginx **expect** a PROXY header **from the client**, and
  every Mudlet connection would fail.

nginx sends PROXY protocol **v1** (text) by default on a TCP upstream:
`PROXY TCP4 <src> <dst> <srcport> <dstport>\r\n` or `PROXY TCP6 ...`
[host: confirm the line with a capture against a test listener]. That is
the format `proxy_header_accept()` parses [source]. It sends the header as
soon as the upstream connection opens, after the client's TLS handshake
and before any client bytes, so header and client data never interleave.

Sample, for `/etc/nginx/toc-stream.d/toc-tls.conf` (see "Host
Prerequisites" for why it cannot go in `conf.d/`):

```nginx
# Times of Chaos: TLS for native clients. Managed by toc-tls-setup.
# Only one stream {} block may exist in the whole nginx configuration.
stream {
    log_format toc_tls '$remote_addr [$time_local] $status $ssl_protocol '
                       '$bytes_sent $bytes_received $session_time';
    access_log /var/log/nginx/toc-tls.log toc_tls;   # holds player IPs

    # Checked before the TLS handshake (preaccess phase).
    limit_conn_zone $binary_remote_addr zone=toc_tls_addr:1m;
    limit_conn_zone $server_port        zone=toc_tls_all:64k;

    server {
        listen 9443 ssl so_keepalive=120s:30s:4;      # NOT "proxy_protocol" here
        # listen [::]:9443 ssl so_keepalive=120s:30s:4;  # only after IPv6 is verified

        ssl_certificate       /etc/nginx/toc-tls/current/fullchain.pem;
        ssl_certificate_key   /etc/nginx/toc-tls/current/privkey.pem;
        ssl_protocols         TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers off;
        ssl_session_cache     shared:toc_tls:1m;
        ssl_session_timeout   1h;
        ssl_session_tickets   off;
        ssl_handshake_timeout 10s;

        limit_conn toc_tls_addr 10;
        limit_conn toc_tls_all  300;

        proxy_pass            127.0.0.1:9002;   # the game's TLS backend listener
        proxy_bind            127.0.0.2;        # convention, not authentication
        proxy_protocol        on;               # nginx SENDS the v1 header
        proxy_connect_timeout 5s;
        proxy_timeout         24h;
    }
}
```

**Header handling on the TLS backend listener** (to implement; today's
parser is shared and lenient, above). Everything here happens before the
nanny can treat a byte as a name, a password or a GMCP login:

| Case | Handling |
| --- | --- |
| Missing (first line is not `PROXY `) | close; log one line per peer per `GUARD_REPORT_SECS`-style window; never a name |
| Malformed (bad family, unparsable or wrong-family address, non-numeric or out-of-range ports, lower case, extra or missing fields) | close, as above. Strict on this path; the bridge path keeps today's parser until it is reviewed separately |
| Incomplete or fragmented | the line reader already joins fragments; add a deadline (`TOC_TLS_HEADER_SECS`, default 5 s from accept) and a cap of 107 bytes including CRLF (the v1 maximum); either exceeded closes |
| Coalesced with client bytes | the header is the first line; everything after it stays in `inbuf` for the nanny as today. The header is ASCII, so `telnet_filter_input()` passes it unchanged [source] |
| Duplicate (a second PROXY line) | ordinary input after the first line, so a name the nanny refuses -- as today on 9000 [source: `tests/test_audit_connections.py`] |
| `PROXY UNKNOWN` | close: on a TCP TLS listener nginx always knows the peer, so UNKNOWN means something is wrong |
| Source is loopback | accepted: it is the host probing itself through nginx (the health check); it stays loopback-exempt like the local probes |

After a valid header the TLS path runs the same re-checks the bridge path
runs today -- `login_lock_remaining()`/`login_lock_refusal()`,
`conn_guard_admit()`, `connection_spoke()` -- and differs in one thing
only: no `guard_proxied`. So TLS connections from untrusted addresses
collect strikes and pauses exactly as plain ones do, and the browser's
reload exemption stays the browser's. Bans (`check_ban()`, asked at the
name and the password), lockouts, shared-address notices
(`wizinfo_same_host()`), trust records (`conn_guard_trust()` from
`login_note_success()`) and the play journals all see the real player
address. Staff listings show the kind (`tls`, `web`, `direct`) beside the
address in SOCKETS and DNS LIST, and keep `staff_may_see_descriptor()`'s
rule that a hidden row is left out whole [source: `src/act_wiz.c`].

One cosmetic gap carries over: the greeting and Telnet offers are sent at
accept, before the header's lockout re-check, so a locked-out address on a
proxied path sees the greeting before the refusal [source:
`init_descriptor()`]. The bridge has the same behaviour today; it leaks
nothing.

### Client, Login And Downgrade Policy

Facts [source]:

- GMCP `Char.Login`: `gmcp_note_supports()` in `src/gmcp.c` sends
  `Char.Login.Default {"type":["password-credentials"]}` once, at
  `CON_GET_NAME`, when the client's `Core.Supports` names `Char.Login`.
  `gmcp_login_begin()` in `src/comm.c` takes the credentials only at the
  name prompt with nothing waiting in `inbuf`; `gmcp_login_start()` and
  `gmcp_login_after_nanny()` type the name and password through the
  ordinary prompts, so every login check still applies.
- MSSP (`telnet_send_mssp()` in `src/telnet_proto.c`) advertises NAME,
  PLAYERS, UPTIME, CODEBASE, FAMILY, CHARSET, ANSI, GMCP, MCCP and the pay
  flags -- **no `TLS` or `SSL` key**.
- Header-before-login race to close: on a header path the header line can
  still be sitting in `inbuf` (the nanny reads one line a pulse) when
  `Char.Login.Credentials` arrives, and `gmcp_login_begin()` then refuses
  with "Type your name to log in." The TLS path should not offer
  `Char.Login.Default` until the header has been consumed (offer it from
  the nanny once `first_line_read` is set on a `CONN_TLS` descriptor).

**MSSP's TLS advertisement is discovery, not protection.** A profile that
connects to 9000 has already sent whatever it sends at connect before
any upgrade prompt can appear, and an on-path attacker can strip the
advertisement from a plaintext session. Only a profile that connects to
the TLS port with Secure on is protected. To test on real Mudlet builds
[mudlet], current release and the oldest still in common use:

- which MSSP key Mudlet reads for its upgrade offer (`TLS`, `SSL`, or both)
  and whether the value is a port;
- the ordering on a plaintext connection: does Mudlet answer
  `Char.Login.Default` (or send its own saved-password text lines) before
  it reads MSSP and offers to switch? If yes, the first saved-password
  login of every existing profile crosses the network in clear;
- whether, with Secure ticked, a failed handshake ever falls back to
  plaintext (the TLS port must never speak plaintext, so a fallback to the
  same port gets nothing usable -- confirm Mudlet does not retry on 9000);
- what Mudlet shows for an expired, untrusted or wrong-host certificate,
  and which "accept anyway" options it offers;
- whether a saved password is sent by Mudlet's own auto-login as text
  lines when the game offers no `Char.Login` (this decides whether refusing
  `Char.Login` on plaintext would protect anything).

Policy:

- New instructions and any distributed profile (README, `mudlet/README.md`,
  HELP MUDLET, the website, the Mudlet default-list entry) say:
  `toc.jeremybean.com`, port 9443, **Secure on**. Plain 9000 is described
  as legacy.
- Existing profiles: migration is by notice, not by force -- the MSSP
  advertisement once enabled, a CHANGES entry, and a one-line hint after
  login for a Mudlet client (known from TTYPE, `client_name`) on a
  `CONN_DIRECT` connection, at most once a day. The hint comes after the
  password has already crossed; it is guidance for next time.
- Certificate errors: tell players never to tick Mudlet's accept-anyway
  options for this game; an error means stop and report it.
- TLS unavailable (nginx down, certificate expired): the TLS port refuses
  or fails the handshake. **No silent fallback to plaintext** anywhere we
  control; a player may choose 9000 knowingly.
- **Legacy plaintext auto-login stays available on 9000 during the
  transition.** Residual risk: anyone able to watch that path sees the
  password of every player who has not moved, exactly as today. A later
  option, an owner decision: refuse `Char.Login` on `CONN_DIRECT` and
  `CONN_BRIDGE` connections (the browser does not use it), saying why --
  useful only if the Mudlet test shows Mudlet does not then type the saved
  password as text anyway.
- MCCP stays on over TLS. It compresses only server-to-client output,
  while passwords travel client-to-server uncompressed, so the
  compression-oracle attacks on TLS do not reach a password; secrets in
  output (tells) are a theoretical exposure the owner may close by not
  offering COMPRESS2 on `CONN_TLS`.

### Certificates

**Method: Let's Encrypt with Ubuntu's `certbot` package, HTTP-01, webroot.**
Reasons: unattended renewal with no third-party credential on the box;
the certbot nginx plugin is avoided because it edits nginx configuration;
`--standalone` is avoided because it needs port 80 free at renewal time.
DNS-01 would avoid port 80, but DNS for the name is maintained by hand
(`wiki/disaster-recovery.md`), so unattended DNS-01 would need a DNS API
credential on the host; a manual TXT record is not unattended. If the
owner ever moves DNS to a provider with zone-scoped, record-restricted
API tokens, DNS-01 becomes the better choice.

- **Port 80** must be reachable from the Internet at every renewal, so it
  stays open, served by one minimal `http` server:

  ```nginx
  # /etc/nginx/conf.d/toc-acme.conf (http context on Ubuntu)
  server {
      listen 80;
      server_name toc.jeremybean.com;
      location ^~ /.well-known/acme-challenge/ {
          root /var/www/toc-acme;
          default_type text/plain;
      }
      location / { return 444; }
  }
  ```

- **First issuance**, staging first so a mistake costs no rate limit:
  `certbot certonly --webroot -w /var/www/toc-acme -d toc.jeremybean.com --staging`,
  inspect, then the same without `--staging`. An account email is
  optional; Let's Encrypt has ended its expiry-reminder emails, so
  monitoring is ours (below).
- **Renewal**: `certbot.timer` (twice a day, from the package)
  [host: `systemctl list-timers certbot.timer`]; `certbot renew --dry-run`
  after setup and after any change. Lifetimes are set to shorten, so
  thresholds below are fractions of the lifetime, not fixed day counts.
- **Deploy hook** (`/etc/letsencrypt/renewal-hooks/deploy/toc-tls`), run
  only after a successful renewal. Certificates are published the way
  `toc-deploy` publishes code: built aside, proven, then switched by one
  rename, so a reader never sees half of a pair and an interrupted run
  never leaves nginx without one.
  - **Layout.** `/etc/nginx/toc-tls/` (0700, root) holds numbered
    releases `r<UTC stamp>-<n>/` (each `fullchain.pem` and `privkey.pem`,
    0600) and two symlinks, `current` and `previous`. nginx names
    `current/fullchain.pem` and `current/privkey.pem`, never certbot's
    `live/`.
  - **Exclusion.** The whole hook runs under `flock -w 600
    /run/toc-tls.lock`, so certbot's timer, a manual `certbot renew` and
    a re-run of the hook never interleave; a second run that cannot take
    the lock in ten minutes alerts and exits, changing nothing.
  - **Steps.**
    1. Copy the pair from `$RENEWED_LINEAGE` into a fresh
       `r<stamp>-<n>.partial/`, `fsync` both files, check that the key
       matches the certificate (`openssl x509 -noout -pubkey` against
       `openssl pkey -pubout`) and that the hostname and `notAfter` are
       right, then rename the directory to `r<stamp>-<n>/`.
    2. Read the release `current` names now, then switch both links,
       each by making a temporary link and renaming it over the old one:
       `ln -sfn <old target> previous.tmp && mv -T previous.tmp previous`,
       then `ln -sfn r<stamp>-<n> current.tmp && mv -T current.tmp current`.
       Each `mv -T` is one atomic `rename(2)` of a symlink.
    3. `nginx -t`; on failure point `current` back at the `previous`
       target the same way, alert, and stop -- nginx keeps serving the
       last certificate it loaded.
    4. `systemctl reload nginx`.
    5. Verify the served certificate is the new one: the SHA-256
       fingerprint from `openssl s_client -connect 127.0.0.1:9443 -servername toc.jeremybean.com -verify_hostname toc.jeremybean.com -verify_return_error`
       must equal `openssl x509 -in current/fullchain.pem -noout -fingerprint -sha256`,
       and `notAfter` must have moved; on mismatch, point `current` back,
       reload, alert.
    6. Keep the three newest releases and whatever `current` and
       `previous` name; delete older ones only after step 5 passed.
  - **Interruption.** A run that dies anywhere leaves either the old
    `current` (steps 1-2) or a complete new one (after 2). The next run
    starts by removing `*.partial/` directories and `*.tmp` links, which
    nothing reads, and by checking that `current` and `previous` resolve
    to whole releases; if `current` does not, it points it at `previous`
    and alerts before doing anything else.
  - **Rollback** by hand is the same switch: point `current` at the
    `previous` target, `nginx -t`, reload.
  - **Tests** (stubbed `openssl`, `nginx` and `systemctl`, as
    `tests/test_deploy_install.py` stubs its tools): three successive
    renewals each leave `current` on the newest release and `previous` on
    the one before, with retention holding three; a failed `nginx -t`, a
    fingerprint mismatch and a kill at each step leave `current` on a
    whole release that serves; two hooks started together run one after
    the other; a leftover `.partial` and `.tmp` link are cleared by the
    next run.
- **Expiry monitoring**: `toc-tls-check` (a script beside
  `toc-state-sync-check`, on its own systemd timer, daily) reads the served
  certificate's `notAfter` and hostname over 127.0.0.1:9443, and the last
  `certbot` result. Warn when less than a third of the lifetime remains
  (renewal should already have happened), critical at a sixth. Alerts go
  where the state-sync check's go: `logger -p daemon.err`, a marker in
  `/run/toc-tls.status`, and a `wizinfo|<level>|...` line through the
  webadmin queue [source: `deploy/windows-vm/toc-state-sync-check`] --
  WIZINFO, never ANNOUNCE. None of those reaches the owner when no staff is
  online; an off-host check (below) is the owner's backstop.
- **Keys**: private keys stay root-owned 0600 under `/etc/letsencrypt` and
  `/etc/nginx/toc-tls/`; nginx's master process reads them as root, and the
  game's `toc` user needs no access.
- **Never in Git or the state sync.** Certificates, keys, the ACME account
  and any future DNS credential live under `/etc` only. The state sync
  copies only from `/srv/toc/current` -- `STATE_DIRS` (`player gods heroes
  log`), `STATE_FILES`, `REPORT_FILES`, `corpse/` and `area/built/`
  [source: `deploy/windows-vm/toc-state-sync`] -- and `log/` reaches a
  public repository, so nothing TLS-related (status files, nginx logs) may
  be written under `/srv/toc/current`. The encrypted backup
  (`deploy/sync-player-backup.sh`) and `toc-deploy`'s rsync touch none of
  `/etc` either.
- **Disaster recovery**: `deploy/toc-restore` rebuilds the game and its
  units and writes `/etc/toc/web.env`; it does not install nginx or
  certificates [source]. On a new box, run `toc-tls-setup` after the
  restore and issue a fresh certificate; `wiki/disaster-recovery.md` gains
  that step when this ships.

### Host Prerequisites

All [host] unless marked:

- **Packages**: `apt install nginx libnginx-mod-stream certbot`. Confirm
  the stream module and stream SSL exist: `nginx -V 2>&1 | tr ' ' '\n' |
  grep -E 'stream|ssl'` should show `--with-stream=dynamic` and
  `--with-stream_ssl_module`, and `/etc/nginx/modules-enabled/` should
  hold the stream module's `load_module` file. Both are arm64 packages in
  Ubuntu 24.04's archive; confirm with `apt-cache policy`.
- **Where the stream block goes**: Ubuntu's `nginx.conf` includes
  `conf.d/*.conf` and `sites-enabled/*` **inside** `http {}`, so a `stream`
  block there fails `nginx -t`. The setup adds one line at the main level,
  after the `modules-enabled` include:
  `include /etc/nginx/toc-stream.d/*.conf;` -- idempotently, and only after
  `nginx -T` shows no existing `stream` block (a second one is an error).
- **Do not replace unrelated configuration**: the setup writes only
  `toc-stream.d/toc-tls.conf`, `conf.d/toc-acme.conf`, `/var/www/toc-acme`,
  `/etc/nginx/toc-tls/` and the hook; it writes each aside, runs `nginx -t`,
  and moves it into place only on success, restoring the previous file
  otherwise. If the package's stock `sites-enabled/default` is present it
  answers port 80 for every other name; the setup reports it and leaves it
  unless the owner chooses to remove it.
- **Firewall, both layers** (AGENTS.md: "a port must be open in both"): an
  OCI security list or NSG ingress rule for `9443/tcp` and `80/tcp` from
  `0.0.0.0/0`, **and** an instance iptables ACCEPT for each, inserted
  before the image's REJECT rule and saved with `netfilter-persistent
  save`. Same for `::/0` and `ip6tables` only if IPv6 is enabled.
- **Ports**: `ss -ltnp` must show nothing on 80, 9443 and the backend
  port (9002 proposed) before setup.
- **IPv4/IPv6**: the game listens on IPv4 only [source: `init_socket()`],
  but nginx can accept IPv6 and still reach the game over 127.0.0.1,
  sending a `TCP6` header the game already parses [source:
  `proxy_header_accept()`]. Enable `listen [::]:9443` only after the VCN,
  subnet and VNIC have IPv6, the security list and ip6tables allow it, and
  an outside IPv6 client completes a session. Until then publish **no
  AAAA** record for `toc.jeremybean.com` (check today: `dig AAAA
  toc.jeremybean.com`), since 9000 has no IPv6 listener at all.
- **Automatic upgrades**: if `unattended-upgrades` is active, an nginx
  package upgrade restarts nginx and drops every TLS session. Either accept
  that or hold nginx and upgrade by hand -- an owner decision.
- **Game environment**: `toc-game.service` has no `EnvironmentFile`
  [source], so the backend listener and MSSP settings need
  `EnvironmentFile=-/etc/toc/game.env` added to the unit in Git (the
  leading `-` keeps it optional); `toc-deploy` installs unit changes.

### Limits And Availability

- **Handshake**: `ssl_handshake_timeout 10s` (nginx's default is 60 s).
  The game's guard cannot protect a connection that has not finished TLS:
  until the header arrives the game never hears of it. Pre-handshake
  protection is nginx's (`limit_conn` runs in the preaccess phase, before
  the handshake [host: confirm on the installed version]) and the
  host's: an iptables `hashlimit` rule on NEW connections to 9443 is the
  equivalent of the `ufw limit` advice above.
- **Connect**: `proxy_connect_timeout 5s`; the backend is loopback, so a
  slow connect means the game is down or wedged, and the client is closed.
- **Idle**: `proxy_timeout 24h`. It must exceed the game's own idle
  policies, because the game deliberately never disconnects an idle
  player [source: `char_update()` in `src/update.c` moves a mortal idle for
  `idle_purge_ticks()` minutes -- `LINKDEAD_PURGE_TICKS` (15) plus a minute
  per five levels, doubled at the third remort -- to Limbo and keeps the
  connection; immortals are never moved]. An idle player in Limbo may get
  no output for hours. Before login, `login_idle_sweep()` closes after
  `LOGIN_IDLE_SECS` (600 s) [source], so nginx needs no shorter pre-login
  limit. 24 hours bounds an abandoned session; the owner may prefer no
  practical limit, to match 9000.
- **Dead peers**: the game's TCP keepalive (120 s idle, 30 s apart, 4
  probes, set in `new_descriptor()` [source]) now reaches only nginx over
  loopback. The player's leg needs nginx's `so_keepalive=120s:30s:4` on the
  `listen`, or NAT timeouts and dead clients go unnoticed until
  `proxy_timeout`.
- **Connection caps**: 10 per address and 300 in total in nginx. The game
  shares one descriptor budget between 9000 and the backend: the unit's
  `LimitNOFILE=1024` [source: `toc-game.service`] and `new_descriptor()`'s
  refusal at `FD_SETSIZE` [source]. nginx's `worker_connections` (768 in
  Ubuntu's default `nginx.conf`) must exceed twice the TLS cap per worker
  [host]. The game's own per-address limit (`GUARD_PENDING_MAX`, 8 waiting
  to log in) and global one (`GUARD_GLOBAL_PENDING`, 200) apply after the
  header [source: `conn_guard_admit()`].
- **Reloads**: `systemctl reload nginx` (certificate or configuration
  change) starts new workers and lets old ones finish their connections, so
  established sessions should survive [host: test it]. Leave
  `worker_shutdown_timeout` unset, or every reload eventually cuts every
  session; the cost is an old worker lingering until its last player
  leaves, a handful a year. A `restart` of nginx, or of the host, drops
  every TLS session. A game restart (deploy, crash) still disconnects every
  player on every path; nginx then refuses at connect until the game is
  back, and Mudlet reconnects.
- **Health checks**, all outside the game loop (the game answers them as
  it answers any connection):
  - `toc-tls-check` on the host: a TLS connection to 127.0.0.1:9443 with
    SNI and hostname verification, then `IAC DO MSSP`, expecting a
    `PLAYERS` value -- the question `toc-game-probe` asks on 9000 [source],
    which can gain a `--tls` option. TCP-open is not healthy.
  - An off-host probe of `toc.jeremybean.com:9443` doing the same, from
    the owner's desktop or a scheduled GitHub workflow outside `validate.yml`
    (owner decision: CI's gate and classifier policy must not change).
  - `toc-deploy`'s own health check stays on 9000; the TLS path is
    independent of game deploys.

### Advertisement And Documentation

- **MSSP**: `telnet_send_mssp()` adds the TLS key (`TLS`, and `SSL` if the
  Mudlet test says so) with the port from `TOC_MSSP_TLS_PORT`. Unset,
  empty or invalid means not advertised -- the default, including in every
  test world. Set it only after the external checks pass.
- **Three paths, documented separately**, everywhere they are described:
  1. TLS Telnet: `toc.jeremybean.com` port 9443, Secure on (the
     recommended native path);
  2. legacy plaintext Telnet: port 9000, with the "Plain Telnet" warning
     above;
  3. browser and dashboard: their own HTTP(S)/WSS story; **the TLS
     listener does not secure them**. Administrative routes never go
     behind any public player-only proxy configuration, now or later.
- **What changes when it is advertised**: HELP MUDLET (and WEBCLIENT's
  pointer) in `area/commands.are`; an `area/changes.dat` entry; `README.md`
  and `mudlet/README.md`; the "Secure (TLS) port" row and the contact
  message in `mudlet/listing-submission.md`; the connect lines in
  `webadmin/static/index.html` (`mudlet-address`) and
  `webadmin/static/client.html` (bump their `?v=`); `/api/config`'s
  `mud_endpoint` in `webadmin/server.py` gains a TLS endpoint
  (`MUD_PUBLIC_TLS_PORT`); `wiki/disaster-recovery.md` and
  `wiki/hosting-guide.md`; this file's "Plain Telnet" and player notice;
  AGENTS.md's connection rules.
- **Rollback of the advertisement**: unset `TOC_MSSP_TLS_PORT` and restart
  the game; revert the docs in one commit; ask Mudlet to update the listing
  if it carries the port. Clients that cached the port will fail closed
  (no fallback), which is the safe failure.

### Implementation Phases

Each phase ships on its own and can be rolled back alone.

0. **Survey, read-only** [host]: `nginx -V` (if installed), `ss -ltnp`,
   `iptables -S`, `ip -6 addr`, `dig A/AAAA toc.jeremybean.com`, OCI
   security list, `unattended-upgrades` status. No changes.
1. **Game: classification and the backend listener, disabled by
   default.** `src/comm.c` (`init_socket()` generalised to bind a given
   address and port; `main()` and `game_loop_unix()` select on a second
   control socket when `TOC_TLS_BACKEND_PORT` is set; `new_descriptor()`
   records `transport_addr`, `listener` and `conn_kind`; the `CON_GET_NAME`
   branch of `nanny()` requires a strict header on the backend listener and
   sets `guard_proxied` only for `CONN_BRIDGE`; a header deadline beside
   `login_idle_sweep()`; `connection_spoke()` logs the kind), `src/merc.h`
   (fields, enum), a pure PROXY v1 parser in its own file with no `merc.h`
   (as `src/netaddr.c` is) plus a C harness, `src/gmcp.c` (offer
   `Char.Login.Default` after the header on `CONN_TLS`),
   `src/telnet_proto.c` (`TOC_MSSP_TLS_PORT`), `src/act_wiz.c` (SOCKETS and
   DNS LIST show the kind), `CMakeLists.txt` (any new `.c`),
   `deploy/windows-vm/toc-game.service` (`EnvironmentFile=-/etc/toc/game.env`),
   tests below. With nothing set, behaviour is byte-for-byte today's.
   Rollback: revert the commit.
2. **Host tooling in Git, not run**: `deploy/windows-vm/toc-tls-setup`
   (idempotent; refuses on an existing stream block or a busy port),
   templates for the two nginx files, the certbot deploy hook,
   `toc-tls-check` with its `.service`/`.timer`, and a `--tls` mode for
   `toc-game-probe`. `toc-deploy` does not touch nginx or certificates; it
   may refresh `toc-tls-check` only when `/etc/toc/tls.enabled` exists.
   Tests run them against stubs, as `tests/test_deploy_install.py` does.
   Rollback: revert.
3. **Bring-up on the host with a staging certificate** [host]: open port
   80 first, in both the Oracle security list and the host firewall --
   Let's Encrypt's HTTP-01 check reaches the webroot over it, staging
   included, and the plain-HTTP server block answers nothing else. Then
   the owner runs the setup over SSH, issues the staging certificate,
   sets `TOC_TLS_BACKEND_PORT` in `/etc/toc/game.env`, restarts on the
   next deploy window, and checks 127.0.0.1:9443 locally. Port 9443 stays
   closed in both firewalls. Rollback: remove the include line and
   `toc-stream.d/`, reload nginx, unset the variable, close 80.
4. **Real certificate, port opened, unadvertised soak** [host] [mudlet]:
   open 9443 (80 is already open from step 3), issue the production
   certificate, run the acceptance list from outside, run
   `certbot renew --dry-run` and a forced renewal, soak a week with staff
   only. Rollback: close 9443 in both firewalls.
5. **Advertise**: set `TOC_MSSP_TLS_PORT`, ship the documentation list
   above. Rollback: as under "Advertisement".
6. **Optional, owner decisions**: refuse `Char.Login` on plaintext; IPv6;
   a Unix-socket backend; HTTPS/WSS for the browser on the same
   certificate (with admin routes excluded).

### Owner Prerequisites

- Take the project off hold, and confirm the port (9443) and backend port.
- In the OCI console: ingress for 80/tcp and 9443/tcp (and IPv6 only if
  wanted and set up end to end).
- Over SSH from the desktop (a cloud session cannot reach the host): run
  the survey, then `toc-tls-setup`, the iptables rules and
  `netfilter-persistent save`, and create `/etc/toc/game.env`.
- DNS: confirm the A record; add no AAAA unless IPv6 is enabled.
- Real Mudlet tests on the desktop (the [mudlet] list), current and an
  older release, and the listing update afterwards.
- Choose the off-host check and who it alerts.

### Unresolved Decisions (Owner Calls)

- Port numbers (9443 public, 9002 backend).
- Backend transport: loopback TCP with a peer allowlist (recommended) or a
  Unix-domain socket (real authentication, more code).
- `proxy_timeout`: 24 hours (recommended) or effectively unlimited.
- Whether to refuse `Char.Login` on plaintext connections later, and
  whether 9000 is ever retired.
- IPv6.
- Port 80: always open with the minimal server (recommended), or a
  different ACME arrangement.
- The stock nginx default site, if present: keep or remove.
- nginx under `unattended-upgrades`, or held.
- MCCP on TLS connections.
- Where the off-host probe runs and how it reaches the owner.
- Whether `toc-deploy` should manage the TLS check script.

### Acceptance Criteria And Test Plan

Game-side tests follow AGENTS.md: synthetic `Z`-named fixtures in
disposable worlds (`tests/live_mud.py`'s `LiveMud`, settings through
`extra_env`), never a real player file; build both trees (Make, C17,
and CMake, C17) and run the focused modules with
`scripts/test-parallel.sh <modules>`; the parser's C harness and the new
live module go in `SANITIZE_MODULES`. A test that needs nginx or
`openssl` must not skip silently in CI: either `scripts/ci/install_deps.sh`
provides them or `tests/ci_allowed_skips.json` names the reason, or the
deploy gate fails.

Game, without nginx (a loopback client plays the terminator's part):

- Backend listener off by default: no second socket, MSSP has no TLS key,
  every existing test unchanged.
- Valid `TCP4` and `TCP6` headers (including a mapped IPv4) on the backend
  listener: `d->addr` is the claimed address, the kind is `tls`, the
  transport address is the 127.0.0.x peer, SOCKETS and DNS LIST show
  `tls`.
- Fragmented header (byte by byte under the deadline): accepted. Header
  coalesced with a name line and with GMCP `Core.Supports` +
  `Char.Login.Credentials` in one write: header consumed first, login
  completes, `Char.Login.Result` true.
- Missing, malformed (each case in the table), over 107 bytes, past the
  deadline, `UNKNOWN`, lower case: closed, never reaches a name prompt,
  never logs in; one log line per window.
- A header from a peer outside `TOC_TLS_PEERS`: closed. A header on 9000
  from a non-loopback peer: still an ordinary refused name.
- Guard: TLS connections from an untrusted test address that hang up
  before a password prompt collect strikes and pause the address
  (`TOC_GUARD_LOOPBACK=1`, lowered `TOC_GUARD_STRIKES`); the same through
  the bridge path still collects none.
- Bans: a numeric ban on the claimed IPv4 and on an IPv6 address in another
  spelling refuses the TLS connection; a host-name (PTR) ban matches only
  once the lookup resolves (`TOC_DNS_LOOPBACK`, `TOC_DNS_DELAY_MS`).
- Lockouts: five wrong passwords over TLS lock the claimed address
  (`TOC_THROTTLE_LOOPBACK=1`), and the lockout refuses it on 9000 and the
  bridge too; a trusted address is capped at an hour.
- Shared-address notices name two TLS players on one claimed address, at
  the higher `staff_notice_level`; a wizinvis creator's row is absent from
  SOCKETS and DNS LIST for a lower immortal.
- `TOC_MSSP_TLS_PORT` set: MSSP carries the key; invalid values are
  ignored.

Host, with nginx (staging certificate first) [host]:

- `nginx -t` passes; `nginx -T` shows one stream block; unrelated files
  unchanged (checksums before and after).
- `openssl s_client` against 127.0.0.1:9443 and, from outside, against
  `toc.jeremybean.com:9443` with `-verify_hostname` and
  `-verify_return_error`: valid chain, right name, TLSv1.2 and TLSv1.3
  accepted, TLSv1.1 refused.
- Wrong host (`-servername` another name, or connecting by IP), an expired
  certificate and an untrusted one (a self-signed pair in a scratch nginx
  on another port): verification fails, and Mudlet warns [mudlet].
- The game's log shows the client's real IPv4 address (and IPv6 when
  enabled), never 127.0.0.2.
- A plaintext connection to 9443 gets no game output; a client sending a
  PROXY header to 9443 is not believed.
- Idle session of over an hour with no output survives; pulling the
  client's network is noticed within keepalive's ~4 minutes; link loss and
  reconnect over TLS restores the character as on 9000.
- `systemctl reload nginx` with players connected: sessions survive.
  Forced renewal (`certbot renew --force-renewal` on staging): hook runs,
  served fingerprint and `notAfter` change, sessions survive. A broken
  certificate in the hook: `previous/` restored, nginx still serving,
  alert raised.
- Game stopped: TLS connects are closed within `proxy_connect_timeout`;
  game back: new sessions work. A deploy's rollback (`toc-deploy` exit
  10-14 paths) does not touch nginx.
- `toc-tls-check` reports healthy only with a valid certificate and an
  MSSP `PLAYERS` answer through TLS; it reports the expiry thresholds.
- Rolling back each phase leaves 9000, 9001, the state sync and deploys
  exactly as before.

Mudlet [mudlet]: a fresh profile on 9443 with Secure on connects, installs
the package, follows the map, fills chat, plays a sound, logs in through
GMCP `Char.Login` with a saved password, negotiates MCCP, TTYPE/MTTS and
NAWS (DNS LIST shows the client), and plays normally; an existing 9000
profile sees the MSSP offer once advertised, and the ordering of that
offer against its saved-password login is recorded in this section.

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
2. A TLS-capable player endpoint. Planned and on hold (owner, 2026-11-07:
   "keep it on the table for a future project"); the implementation-ready
   plan is "Planned: A TLS Player Port For Mudlet's Secure Box" above.
3. Authentication and authorization for every dashboard route, especially the
   MUD WebSocket bridge and detailed world data.
4. CSRF protection where applicable (done for cookie-authenticated
   dashboard requests, 2026-11-09) and an immutable audit trail for
   dashboard actions. The dashboard keeps one shared administrative
   credential by the owner's decision (2026-11-09): no per-operator
   accounts, roles or MFA. What remains is protecting that credential --
   rotation, never on a command line or in a URL, loopback-only binding --
   and recording each action with its source.
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

See [Hosting Guide](../wiki/hosting-guide.md),
[Operator Guide](../wiki/operator-guide.md), and
[Developer Guide](../wiki/developer-guide.md) for implementation procedures.
