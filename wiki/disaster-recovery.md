# If Something Is Broken, Start Here

One page, in the order you will actually need it. Everything on it has
been run at least once rather than only written down.

The game runs in a Hyper-V VM called `TOC-Production` on the Windows
desktop. The Raspberry Pi that used to host it died on 2026-09-29 and
is not coming back; anything telling you to `ssh toc@toc.local` or
touch `/run/toc2026/update.request` is describing that dead machine.

## Where everything is

| | |
| --- | --- |
| Host | Hyper-V VM `TOC-Production`, Ubuntu 24.04 |
| Reach it | `ssh -i C:\ProgramData\ToC\secrets\toc-admin tocadmin@172.28.90.2` |
| Game lives in | `/srv/toc/current` (state) and `/srv/toc/build` (git checkout) |
| Public | `toc.jeremybean.com:9000` game, `:9001` dashboard and browser client |
| Router forwards to | `192.168.0.43`, the Windows host, which NATs to the VM |
| Admin token | `C:\ProgramData\ToC\secrets\web-admin-token.txt`, mirrored in the VM's `/etc/toc/web.env` |

## Is it up?

```bash
curl -s http://toc.jeremybean.com:9001/api/health
```

`{"status":"ok","merc":true,"webadmin":true}` means the game process is
alive and the dashboard can see it. Anything else, work down this page.

## The game is down

```bash
ssh -i C:\ProgramData\ToC\secrets\toc-admin tocadmin@172.28.90.2
systemctl status toc-game toc-web
sudo journalctl -u toc-game -n 50
```

Things that have actually caused this:

- **`custom.are: No such file or directory`** -- `area/custom.are` is
  tracked in git and listed in `area.lst`, and an install that treated
  it as a runtime file left it out. Copy it from
  `/srv/toc/build/area/custom.are`.
- **Unmet condition `ConditionPathExists=!/etc/toc/maintenance`** --
  a maintenance marker is in place. `sudo mv /etc/toc/maintenance
  /etc/toc/maintenance.off` and start the units.
- **A shutdown marker** at `/srv/toc/current/area/shutdown`, left by an
  in-game `shutdown`. Remove it, `systemctl reset-failed`, start.

## The VM is down but Windows is up

```powershell
Get-VM TOC-Production          # needs an elevated PowerShell
Start-VM TOC-Production
```

It is set to start with the host (`AutomaticStartAction Start`, 20s
delay). If Hyper-V cmdlets say "you do not have the required
permission", you are not elevated.

## Deploying a code change

```bash
sudo /usr/local/sbin/toc-deploy            # fetch, build, check, install, restart
sudo /usr/local/sbin/toc-deploy --dry-run  # build and validate only
```

It archives the running code to `/srv/toc/rollback-code-<stamp>.tgz`
first and prints the rollback command if the game does not come back
healthy. It never takes player state from git.

## Are we actually backed up right now?

```bash
cat /run/toc-state-sync.status
systemctl list-timers 'toc-state-sync*'
```

`ok ... unpushed=0` is what you want. `toc-state-sync` commits
characters, gods, the note board, the reports and the logs to `main`
every five minutes; `toc-state-sync-check` complains every quarter hour
if that stops, to the journal, to that marker file, and into the game
where staff will see it.

If it is failing, the usual causes are the deploy key
(`/srv/toc/.ssh/id_ed25519_state_sync` and the repository's deploy key
list must agree) or a full disk.

## The machine is gone

This is the one that matters, and it is rehearsed rather than
theoretical. On any fresh Debian-family box with `git`, `make`, `gcc`
and `rsync`:

```bash
git clone https://github.com/jeremydbean/toc2026.git /tmp/toc
sudo /tmp/toc/deploy/toc-restore
```

That clones, confirms the characters really came with the clone,
builds, validates the world, and installs to `/srv/toc/current`. It
stops rather than proceeding if the repository has no characters in it.

Rehearse it any time without touching anything live:

```bash
TOC_PREFIX=/tmp/drill deploy/toc-restore
```

Last rehearsed 2026-09-29: 968 characters, world validated, about two
minutes.

Two things are not in the repository, and neither blocks a restore
because both can be made again:

- the admin token -- `openssl rand -hex 32` into `/etc/toc/web.env`
- the state-sync deploy key -- `ssh-keygen -t ed25519`, then add the
  public half to the repository with **write** access

The `toc-game.service` and `toc-web.service` units are host-specific
and live on the host. Copy them from the old machine if you still have
it; otherwise they run `/srv/toc/current/merc 9000` from
`/srv/toc/current/area` as user `toc`, and uvicorn for the dashboard.

## Moving to a different machine on purpose

Same as above, plus:

1. Point the router's port forward at the new host's LAN address, and
   reserve that address in DHCP so it cannot move.
2. Check `toc.jeremybean.com` still resolves to your WAN address.
   Nothing on the VM maintains that record -- its DDNS timer updates
   `toc.beanj.com`, the test name. The Pi used to keep the real one.
3. Copy the two secrets across, or make new ones.

## What survives what

| | Where | How often | Survives a dead disk |
| --- | --- | --- | --- |
| Characters, gods, notes, reports, logs | `main` on GitHub, plaintext | 5 min | yes |
| Encrypted `player/` snapshot | private backups repo | 6 h | yes |
| Full state tarball | `/var/backups/toc/` | daily | **no** |
| Character files on disk | `/srv/toc/current/player` | 5 min per player | no |

The daily tarball is local only. It is good for undoing the last hour
and worth nothing against a dead disk.

Player state is committed in **plaintext** to a public repository. That
is deliberate: it is a test environment, the owner would rather lose
the secrecy than the characters, and anyone cloning the repo to run the
game themselves gets a populated world. See the note in `AGENTS.md`
before changing it.

## Recovering from a dead machine's disk

If the host is dead but its disk is readable, and it is a Raspberry Pi
card in a USB reader on Windows, note that **neither `wsl --mount` nor
Hyper-V disk passthrough will accept a USB card reader** -- both fail
with `ERROR_INVALID_DRIVE`. What works:

1. Read the partition table with `Get-Partition -DiskNumber N` and note
   partition 2's offset.
2. Copy that partition to a sparse file with a raw read of
   `\\.\PhysicalDriveN`, skipping all-zero chunks. A 232 GB card with
   9 GB used stores about 9 GB and takes under two hours.
3. In WSL, `losetup -f --show -r <image>` then
   `mount -t ext4 -o ro,noload <loop> /mnt/piroot`. The `noload` matters:
   it stops a dirty journal being replayed onto your only copy.

Do not open the image with an exclusive handle while writing it, or
nothing can read it until the copy finishes.

A better answer if you have a Mac: `brew install e2fsprogs`, then
`sudo debugfs -R "rdump /home/toc/toc2026/player ~/recovered" /dev/diskNs2`.
Userspace only, no kernel extension, reads only what it needs.
