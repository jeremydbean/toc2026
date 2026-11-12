# If Something Is Broken, Start Here

One page, in the order you will actually need it. Everything on it has
been run at least once rather than only written down.

The game runs on an Oracle Cloud instance (Always Free ARM, Ubuntu
24.04) reached at `129.159.105.156`, which `timesofchaos.com` (and
`www.timesofchaos.com`, and the older `toc.jeremybean.com`) points to.
It moved there on 2026-10-01. Two earlier hosts are gone and not coming
back: a Hyper-V VM on the owner's Windows desktop (powered off), and
before that a Raspberry Pi that died on 2026-09-29. Anything telling you
to `ssh toc@toc.local`, touch `/run/toc2026/update.request`, or start a
`TOC-Production` VM is describing a dead machine.

## Where everything is

| | |
| --- | --- |
| Host | Oracle Cloud instance, Ubuntu 24.04 ARM, region us-ashburn-1 |
| Public IP | `129.159.105.156` -- **reserved**, so it survives a stop/recreate |
| Reach it | `ssh toc-oracle` from PowerShell or Git Bash on the owner's desktop (alias in `~/.ssh/config`, key `~/.ssh/toc-oracle`). Fallback, Git Bash only: `ssh -i /c/Users/JeremyBean/Downloads/oci_game_private_key ubuntu@129.159.105.156` -- PowerShell refuses that copy of the key as unprotected |
| Game lives in | `/srv/toc/current` (state) and `/srv/toc/build` (git checkout) |
| Public | `timesofchaos.com:9000` game (plain Telnet); `https://timesofchaos.com/` website -- dashboard and browser client -- through Caddy on 80 and 443 |
| Dashboard | `toc-web` on `127.0.0.1:9001` behind Caddy, in proxy mode (see "The website" below) |
| Firewall | OCI VCN security list **and** the instance's own iptables -- a port must be open in both (22, 80, 443, 9000) |
| Admin token | `/etc/toc/web.env` on the host (mode 600) |

## Is it up?

```bash
curl -s https://timesofchaos.com/api/health
```

`{"status":"ok","merc":true,"webadmin":true}` means the game process is
alive and the dashboard can see it. Anything else, work down this page --
and if only the website is down while the game answers on 9000, see "The
website" below (`systemctl status caddy toc-web`).

## The game is down

```bash
ssh toc-oracle
systemctl status toc-game toc-web
sudo journalctl -u toc-game -n 50
```

The game is set to restart itself: `Restart=always` after a crash, a
60-second watchdog for a hang, enabled units after a reboot, and
`toc-game-recovery` every couple of minutes as the backstop if it ever
crash-loops past systemd's start limit. If it is still down, things that
have actually caused it:

- **`custom.are: No such file or directory`** -- `area/custom.are` is
  tracked in git and listed in `area.lst`, and an install that treated
  it as a runtime file left it out. Copy it from
  `/srv/toc/build/area/custom.are`. (`toc-deploy` now keeps the live copy,
  which holds builders' RSAVEd rooms newer than git's, and copies git's
  only when the live tree has none.)
- **Unmet condition `ConditionPathExists=!/etc/toc/maintenance`** --
  a maintenance marker is in place. `sudo mv /etc/toc/maintenance
  /etc/toc/maintenance.off` and start the units.
- **A shutdown marker** at `/srv/toc/current/area/shutdown.txt`, left by
  an in-game `shutdown`. It is tracked in git, so a restore brings it
  back -- `toc-restore` removes it. Delete it, `systemctl reset-failed`,
  start.

## The instance itself is down

Soft-reboot or start it from the OCI console (Compute -> Instances ->
the instance -> Reboot / Start), or `sudo reboot` over SSH if you can
still reach it. The enabled units bring the game, dashboard, sync and
recovery back on their own; a full reboot has been tested end to end. If
the instance will not start with "out of host capacity", that is the ARM
free-tier capacity limit -- retry later, or restore onto another shape
or another provider (see "The machine is gone").

## The website: Caddy on 80 and 443

The dashboard and browser client are served at `https://timesofchaos.com`
by Caddy (Ubuntu's `caddy` package), which gets and renews its Let's
Encrypt certificates itself and only redirects on port 80, so the admin
token never crosses plain HTTP. `www.timesofchaos.com` and
`toc.jeremybean.com` redirect to it. Caddy hands every request, WebSockets
included, to `toc-web` on `127.0.0.1:9001`, which is no longer reachable
from outside. Its configuration is `deploy/windows-vm/Caddyfile` in git,
installed as `/etc/caddy/Caddyfile`; the dashboard's side is four lines in
`/etc/toc/web.env` -- `WEB_ADMIN_LISTEN=127.0.0.1`,
`WEB_ADMIN_PROXY_HEADERS=1`, `WEB_ADMIN_FORWARDED_ALLOW_IPS=127.0.0.1`,
`WEB_ADMIN_LOCAL_UNLOCK=0` -- plus `MUD_PUBLIC_HOST=timesofchaos.com`.
`toc-web.service` reads them; a deploy never changes them.

**Setting it up (once, and again on a new box).** In this order:

1. **DNS** (Namecheap -> Domain List -> timesofchaos.com -> Advanced DNS):
   an `A` record for host `@` and one for `www`, both `129.159.105.156`.
   Remove Namecheap's parking `CNAME`/`URL Redirect` records for `@` and
   `www` if present. Publish no `AAAA` record: nothing here listens on
   IPv6. Keep `toc.jeremybean.com` pointing at the box -- old Mudlet
   profiles use it.
2. **OCI security list** (Networking -> Virtual Cloud Networks -> the VCN
   -> the subnet's security list -> Add Ingress Rules): source
   `0.0.0.0/0`, IP protocol TCP, destination port `80`; and the same for
   `443`. Stateful, no source port.
3. **The code**: the commit carrying `toc-web-proxy` must be live
   (`log/deployed-commit`); the script refuses until the live dashboard
   knows proxy mode.
4. **The script**, from the owner's desktop (PowerShell or Git Bash):

   ```bash
   ssh toc-oracle 'sudo sh /srv/toc/build/deploy/windows-vm/toc-web-proxy --dry-run'
   ssh toc-oracle 'sudo sh /srv/toc/build/deploy/windows-vm/toc-web-proxy'
   ```

   It installs Caddy and the Caddyfile (validated first), opens 80 and 443
   in iptables before the REJECT rule (saved with `netfilter-persistent`),
   starts Caddy and checks it answers, and only then moves the dashboard to
   loopback -- putting the unit and `web.env` back if the dashboard does not
   return. A failure before that last step leaves the website on public
   9001, untouched. It is safe to run again. It ends by fetching
   `https://timesofchaos.com/api/health` through Caddy; if DNS or the
   security list is not ready yet it only warns, and Caddy keeps trying for
   the certificate on its own (`journalctl -u caddy`).

Steps 1 and 2 can be done in either order and before step 4; the
certificate arrives within a minute of both being in place. DNS changes can
take a while to propagate: `dig +short timesofchaos.com` should answer
`129.159.105.156`.

**Rolling it back**:

```bash
ssh toc-oracle 'sudo sh /srv/toc/build/deploy/windows-vm/toc-web-proxy --rollback'
```

That takes the three proxy lines out of `web.env` (the token,
`MUD_PUBLIC_HOST` and `WEB_ADMIN_LOCAL_UNLOCK=0` stay), restarts the
dashboard on public `0.0.0.0:9001` -- reachable as long as 9001 is still
open in the security list and iptables, which setup leaves alone for this
reason -- and stops and disables Caddy. The Caddy package, its Caddyfile
and the 80/443 rules stay; nothing listens behind them.

**When it breaks**: `systemctl status caddy toc-web`, `journalctl -u caddy
-n 50`. `curl -s http://127.0.0.1:9001/api/health` on the host tells the
dashboard from the proxy. A certificate problem is almost always DNS or the
security list.

## Deploying a code change

```bash
sudo /usr/local/sbin/toc-deploy             # fetch, build, check, install, restart
sudo /usr/local/sbin/toc-deploy --dry-run   # build and validate only
sudo /usr/local/sbin/toc-deploy --rollback  # the code from the newest snapshot, back
```

Before it stops the game it copies the running code -- code only, with
the same exclusions the install uses -- to
`/srv/toc/rollback-code-<stamp>/` (the two before it are kept), and a
deploy that cannot make that copy stops with the game still running. A
world that fails `--check-area` stops it before anything is touched. A
step that fails after the game was stopped (an rsync out of disk), or a
game that does not come back healthy, puts that code back and restarts
the game -- automatically when the timer deployed it. **A rollback never
touches state**: players, corpses, notes, bans, max-load counts,
`custom.are` and `area/built/` stay as the game left them. Healthy means
the dashboard answers *and* the game itself answers MSSP with a player
count, which it only does once the world has loaded. A stop that fails
part way installs nothing and starts both services again on the code
they were running. Its exit status says how far it got -- 10 rolled back
and healthy, 11 rolled back but not healthy, 12 new code not healthy and
left alone (`--rollback` then), 13 nothing installed and the old code
healthy again, 14 nothing installed and not healthy, anything else
stopped before the game was touched -- and the auto-deployer's status
line says the same. It never takes player state from git.

**A rollback records the code it put back.** The install writes
`.code-revision` in the live tree (the commit and the sha256 of its
`merc`), each snapshot carries the same line as `.snapshot-revision`,
checked against the snapshot's binary, and a rollback writes that commit
to `log/deployed-commit` (third field `rollback <snapshot>`) and the
tree's `.code-revision`, each written aside and renamed into place. A
snapshot from before identities were kept, or a copy that did not
finish, is recorded as `unknown`: `toc-auto-deploy` then says "the live
code is unknown" and ships nothing, and `toc-game-recovery` builds
nothing -- run `toc-deploy` by hand. The commit rolled back from goes
into `/var/lib/toc-auto-deploy/rolled-back`, and the auto-deployer holds
it and anything older until newer code lands (remove the line to let it
ship again). Recovery also refuses to rebuild when the tree's
`.code-revision` and `log/deployed-commit` disagree -- the state an
unhealthy deploy left for a person (exit 12) is in -- since that would
put one commit's binary into another's tree.

`toc-game-recovery`, which restarts a game systemd has given up on,
rebuilds only the commit that is live when restarts do not work -- never
the untested tip of `main`.

**Usually you do not need to run it.** `toc-auto-deploy.timer` checks
`main` every ten minutes and deploys new code once CI's `deploy-gate`
job has passed for it on a push to `main` (CI takes about fifteen
minutes), pinned to that commit and rolling the code -- never player
state -- back if the game does not come back healthy; `[deploy now]` on a line of its own in the message of the commit
carrying the code skips the CI wait for that code (not for code pushed
after it). It never restarts the game while anybody is playing, or while the game
cannot say who is: the status reads `holding <sha>: N player(s) online`
(or `the game did not say who is online`) and it looks again every ten
minutes until the game is empty (owner, 2026-10-20). A game that is not
running at all is deployed. A deploy
by hand is the override; from a session that can only push, so is
`[deploy with players]` on a line of its own in any waiting commit (owner, 2026-10-24), which
still waits for CI, gives players a minute's warning and then the usual
announce and save. Docs, tests and state-sync commits never
trigger it. What it
decided last is in `/srv/toc/current/log/auto-deploy.status` (also in
git, via the state sync), the live commit in `log/deployed-commit`, and
its history in `journalctl -t toc-auto-deploy`. To stop it:
`sudo systemctl disable --now toc-auto-deploy.timer`. If a deploy failed,
`/var/lib/toc-auto-deploy/last.log` has the output; it will not retry
that commit, so push a fix or run `toc-deploy` by hand.

## Are we actually backed up right now?

```bash
cat /run/toc-state-sync.status
systemctl list-timers 'toc-state-sync*'
```

`ok ... unpushed=0` is what you want. `toc-state-sync` commits
characters, gods, heroes, the note board, the reports and the logs to
`main` every five minutes; `toc-state-sync-check` complains every
quarter hour if that stops, to the journal, to that marker file, and
into the game where staff will see it.

If it is failing, the usual causes are the deploy key
(`/srv/toc/.ssh/id_ed25519_state_sync` and the repository's deploy key
list must agree), a full disk, or a corrupt clone at
`/srv/toc/state-repo` (symptom: `object file ... is empty` -- move the
clone aside and let the sync re-clone).

## The machine is gone

This is the one that matters, and it is rehearsed rather than
theoretical. On any fresh Debian-family box:

```bash
sudo apt install -y build-essential cmake zlib1g-dev libcrypt-dev git python3-venv
git clone https://github.com/jeremydbean/toc2026.git /tmp/toc
sudo sh /tmp/toc/deploy/toc-restore
```

`toc-restore` clones, confirms the characters really came with the
clone, builds, validates the world, installs to `/srv/toc/current`, and
now also installs every systemd unit, builds the dashboard venv, writes
a fresh admin token and starts the game -- so it comes up running and
self-restarting. It stops rather than proceeding if the repository has
no characters in it.

Rehearse it any time without touching anything live:

```bash
TOC_PREFIX=/tmp/drill sh deploy/toc-restore
```

Last rehearsed 2026-10-01 on the Oracle host: 968 characters, 212
heroes, world validated, about two minutes.

Two things are not in the repository, and neither blocks a restore
because both can be made again:

- the admin token -- `openssl rand -hex 32` into `/etc/toc/web.env`
  (toc-restore writes one if none exists)
- the state-sync deploy key -- `ssh-keygen -t ed25519`, then add the
  public half to the repository with **write** access, so backups resume

One host-specific step is not automated, because it is per-provider:
**open the game port in the firewall.** On the Oracle box that is an
iptables ACCEPT before the REJECT rule, saved with
`netfilter-persistent` -- the OCI security list alone is not enough.
Most other providers (Linode and the like) need nothing here.

The restore brings the website up on public 9001 over plain HTTP. Put it
back behind Caddy with `toc-web-proxy` (see "The website" above): it opens
80 and 443 in iptables itself, but the provider's own firewall (the OCI
security list) is still yours to open.

## Moving to a different machine on purpose

Same as "The machine is gone", plus:

1. Reserve the new box's public IP with the provider so it cannot change
   under you (on OCI, convert the ephemeral IP to a reserved one).
2. Point `timesofchaos.com`, `www.timesofchaos.com` and
   `toc.jeremybean.com` at the new address. DNS is maintained by hand
   (Namecheap for timesofchaos.com) -- nothing on the host updates it.
3. Copy the two secrets across, or make new ones, and open the firewall
   (9000, 80 and 443). Run `toc-web-proxy` once DNS points at the new box.
4. Bring the game up, then enable `toc-state-sync` on the new host --
   and make sure the old host is no longer syncing, or the two will
   fight over the branch.

## What survives what

| | Where | How often | Survives a dead disk |
| --- | --- | --- | --- |
| Characters, gods, heroes, notes, reports, logs | `main` on GitHub, plaintext | 5 min | yes |
| Encrypted `player/` snapshot | private backups repo | 6 h | **not wired up on Oracle yet** |
| Full state tarball | `/var/backups/toc/` | -- | **not wired up on Oracle yet** |
| Character files on disk | `/srv/toc/current/player` | 5 min per player | no |

The five-minute GitHub sync is the live backup and it is running. The
encrypted six-hourly snapshot and the daily local tarball ran on the old
VM and are **not yet set up on Oracle** -- a follow-up. Until they are,
the GitHub sync is the whole safety net, which is enough to rebuild from
(that is what "The machine is gone" does) but is plaintext and public.

Player state is committed in **plaintext** to a public repository. That
is deliberate: it is a test environment, the owner would rather lose the
secrecy than the characters, and anyone cloning the repo to run the game
themselves gets a populated world. See the note in `AGENTS.md` before
changing it.
