# New Machine Setup

How to go from nothing to full control of Times of Chaos from a machine that
is not the usual desktop -- a second PC, a laptop, a phone with a shell, or a
VPS. Written so that if the usual desktop is gone, this page plus your Oracle
account and GitHub login are enough to rebuild everything.

Nothing on this page is a secret. The private key and the admin token are
**not** here and never should be; this tells you where they live and how to
get them, not what they are.

---

## What "full control" needs

Two independent things:

1. **Ship code** -- edit, build, test, and get it live. Needs only a clone of
   the repo and a GitHub push login. **Works from any machine, including a
   cloud/sandboxed Claude session.**
2. **Reach the host directly** -- deploy instantly, read the live game, run
   staff commands on the box, rotate secrets. Needs the SSH **key** on the
   machine and a network that allows outbound port 22 (or 443). **Works from
   any real machine you set up; never from a cloud sandbox**, whose network
   policy blocks the host on every port.

For day-to-day work on a friends game, (1) is enough: a push deploys itself
within about ten minutes (see below). (2) is for when you want it instant or
need to touch the host.

| Capability | Clone + GitHub | + key + port 22 | Cloud sandbox |
|---|---|---|---|
| edit / build / test / commit / push -> deploy | yes | yes | yes |
| instant SSH deploy, read live host, run restores, rotate token | no | yes | no |

---

## Ship code from anywhere (no host access needed)

A push to `main` **is** the deploy. `toc-auto-deploy` runs on the host every
ten minutes; when `main` carries new code whose CI Validate run is green, it
deploys that commit and rolls back if the game does not come back healthy.
Docs-, test-, and state-sync-only commits do not trigger it.

```bash
git clone https://github.com/jeremydbean/toc2026
cd toc2026
# ...make a change...
git fetch && git rebase origin/main && git push origin HEAD:main
```

CI takes about fifteen minutes. For an urgent fix, put `[deploy now]` on a line of its own in the message
of the commit that changes the code to skip the CI wait (it does not cover
code pushed after it) -- `toc-deploy` still refuses anything that does
not build or whose world does not load.

Check what is live without any host access:

```bash
git fetch
git show origin/main:log/deployed-commit      # the commit and when
git show origin/main:log/auto-deploy.status   # what the auto-deployer last did
```

The host also syncs `area/bugs.txt`, `typos.txt`, `ideas.txt`, `notes.txt`
and `log/toc.log` into the repo every five minutes, so `git show
origin/main:area/bugs.txt` reads the live reports (up to five minutes stale).
Those files carry player IP addresses -- filter them out of anything you
print or paste.

### Building on a new box

- **Linux / macOS / WSL:** build natively.

  ```bash
  make                                               # gnu89
  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build   # strict c17
  cd area && ../merc --check-area && cd ..
  JOBS=1 scripts/test-parallel.sh <module>           # the one relevant test
  ```

- **Windows:** the C only builds under WSL. From PowerShell or Git Bash:

  ```bash
  MSYS_NO_PATHCONV=1 wsl bash -lc 'cd /mnt/c/Users/<you>/toc2026 && make && cmake --build build'
  ```

A change must build under **both** trees before you believe it works; see
AGENTS.md for why they disagree.

---

## Reach the host directly (SSH)

### What the host is

- Oracle Cloud Always Free, ARM (aarch64) Ubuntu 24.04
- IP `129.159.105.156` (a reserved IP; `toc.jeremybean.com` resolves to it)
- SSH user `ubuntu`, port 22
- Exposed: game 9000, dashboard 9001, SSH 22
- On the box: `/srv/toc/build` (the checkout `toc-deploy` builds), `/srv/toc/current`
  (the live tree), units `toc-game`, `toc-web`, `toc-state-sync`,
  `toc-auto-deploy`, `toc-daily-backup`.

### Put the key on the new machine

The private key lives on the usual desktop at
`C:\Users\JeremyBean\Downloads\oci_game_private_key` (and a copy at
`~/.ssh/toc-oracle`). Back it up into a password manager so a new machine is
a copy-paste away:

```powershell
Get-Content -Raw C:\Users\JeremyBean\Downloads\oci_game_private_key   # PowerShell
```
```bash
cat ~/.ssh/toc-oracle                                                 # Git Bash / Linux / macOS
```

On the new machine, write that blob (from `-----BEGIN OPENSSH PRIVATE KEY-----`
through `-----END OPENSSH PRIVATE KEY-----`) to a file and lock it down:

```bash
mkdir -p ~/.ssh
# paste the key into ~/.ssh/toc-oracle with an editor, then:
chmod 600 ~/.ssh/toc-oracle
```

Add a host alias to `~/.ssh/config`:

```
Host toc-oracle
    HostName 129.159.105.156
    User ubuntu
    IdentityFile ~/.ssh/toc-oracle
```

Deploy and health-check:

```bash
ssh toc-oracle 'sudo /usr/local/sbin/toc-deploy'
ssh toc-oracle 'systemctl is-active toc-game toc-web'
```

Notes:

- Windows PowerShell's OpenSSH refuses a key whose file permissions are too
  open. Use Git Bash, or make sure the key file is readable only by you.
- If outbound port 22 is blocked on the new machine's network, `nc -vz
  129.159.105.156 22` will hang or say no route. Then either deploy by push
  (above) or set up SSH over 443 from a machine that can already reach 22.

---

## If the key is lost entirely

You are not locked out. Oracle Cloud's web console has a **Cloud Shell** and a
**serial / console connection** that get you onto the instance with no SSH key
at all. From there, append a fresh public key to
`~ubuntu/.ssh/authorized_keys` and you have SSH again. So as long as you can
log into the Oracle account and GitHub, the game is fully recoverable:

- **Host gone (reclaimed, deleted):** stand up any Debian-family box and run
  `deploy/toc-restore`, which rebuilds a working game -- code and live player
  state -- from this public repo alone. See [Disaster Recovery](disaster-recovery.md).
- **Key gone:** recover SSH via the Oracle console as above.
- **Desktop gone:** nothing here depended on it. Clone the repo, restore the
  key from your password manager (or the console), and you have everything.

---

## Related

- [Disaster Recovery](disaster-recovery.md) -- the live host, deploys, backups,
  and rebuilding on a fresh machine.
- `AGENTS.md` -- the full engineering playbook, including "Connecting and
  shipping from a new session".
