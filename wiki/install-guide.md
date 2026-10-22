# Installing Times of Chaos

This is the guide to running your own copy of Times of Chaos: on your own
computer to play or build, or on a server for other people. To play on the
public server instead, nothing needs installing: open
`http://toc.jeremybean.com:9001/client`, or point a MUD client at
`toc.jeremybean.com` port `9000`.

Every installer is one command, safe to run again, and ends with the game
running and a link to play it.

## Pick A Way To Run It

| | **Docker** (recommended) | **Native** |
|---|---|---|
| Runs on | Windows 10/11, macOS, Linux | Linux, macOS |
| Installs | Docker (Docker Desktop on Windows and Mac) | A C compiler, make, rsync, Python 3.10+ |
| First start | A download of the prebuilt game (about 100 MB) | A compile, about a minute |
| Starts at boot | Yes, with Docker | Yes on Linux (systemd services) |
| Good for | Anyone; the same everywhere | A Raspberry Pi, a small VPS, or no Docker |

Both keep everything the game writes in one folder, `state/`, and your
private settings in `.env`, so updates never touch your characters or your
world. Windows is Docker only; to run natively on Windows, install inside
WSL with the Linux command.

## Install

### Windows 10 or 11

Open **PowerShell** and paste:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_windows.ps1)))
```

It installs Git and Docker Desktop with `winget` (Windows asks for
permission once), downloads Times of Chaos to `%USERPROFILE%\TimesOfChaos`,
and starts it. Windows may need **one restart** to finish turning on WSL 2;
after it, paste the same line again and it carries on where it stopped.
Docker Desktop shows its own terms the first time it opens; accept them and
the installer continues.

Add `-Public` to the end of the line to let other computers connect.

### macOS

Open **Terminal** and paste:

```bash
curl -fsSLo /tmp/toc-install.sh https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_macos.sh && bash /tmp/toc-install.sh
```

It installs Apple's Command Line Tools if needed (a dialog opens; finish
it, then paste the line again), Homebrew, Git and Docker Desktop, downloads
Times of Chaos to `~/TimesOfChaos`, starts it and opens the web client.
Add `--native` to the end to compile and run it without Docker.

### Linux

Open a terminal and paste:

```bash
curl -fsSLo /tmp/toc-install.sh https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_linux.sh && bash /tmp/toc-install.sh
```

Supported: Debian, Ubuntu, Raspberry Pi OS, Linux Mint (apt); Fedora,
RHEL, Rocky, Alma (dnf); Arch, Manjaro (pacman); openSUSE (zypper). It asks
for your password once (`sudo`) to install packages. Docker comes from the
distribution, or from Docker's official install script where the
distribution has no Compose v2. Add `--native` to compile and run without
Docker; on a systemd system the game and the web client then become
services that start at boot.

### From A Checkout You Already Have

| Platform | Click | Or run |
|---|---|---|
| Windows | `Install-ToC.cmd` | `.\install.ps1` |
| macOS | `Install-ToC.command` | `./install.sh` |
| Linux | | `./install.sh` |

### Installer Options

| Linux / macOS | Windows | Does |
|---|---|---|
| `--native` | (WSL only) | Compile and run without Docker |
| `--docker` | (default) | Switch a native install back to Docker |
| `--public` | `-Network Public` | Let other computers connect to the game port |
| `--local` | `-Network Local` | Only this computer can connect (the default) |
| `--import-players` | `-ImportPlayers` | Start with the characters committed to this repository instead of an empty world |
| `--no-service` | | Native: background processes instead of systemd services |
| `--no-start` | `-NoStart` | Set everything up but do not start |
| `--open` | (default; `-NoBrowser` to skip) | Open the web client when it is running |
| `--skip-prerequisites` | `-SkipPrerequisites` | Do not install system packages |

Options pass through the one-line commands too:
`bash /tmp/toc-install.sh --native --public`.

## After Installing

**Play.** The installer prints the addresses:

- In a browser: `http://127.0.0.1:9001/client` (or `./toc.sh play`).
- In a MUD client such as Mudlet: `localhost` port `9000`. Mudlet picks up
  the Times of Chaos interface and map by itself; see
  [mudlet/README.md](../mudlet/README.md).

**Make yourself the administrator.** A new world starts empty. Create a
character in the game, type `QUIT`, then:

```bash
./toc.sh promote <name>          # Windows: .\toc.ps1 promote <name>
```

Log in again: the character is the implementor (level 70). `WIZHELP`
lists the staff commands, and [the operator guide](operator-guide.md)
explains them. The character must be logged out when you promote it,
because the game writes its own copy over the file on QUIT.

**The dashboard** is `http://127.0.0.1:9001` (or `./toc.sh admin`). On this
computer it unlocks itself; elsewhere it asks for the token, which is
`WEB_ADMIN_TOKEN` in `.env`. Keep that token private.

## Everyday Commands

Run these in the install folder. On Windows use `.\toc.ps1 <command>`, or
double-click `Start-ToC.cmd` (macOS: `Start-ToC.command`) to start and play.

| Command | Does |
|---|---|
| `./toc.sh start` | Start it |
| `./toc.sh stop` | Stop it; every player is saved first |
| `./toc.sh restart` | Stop and start |
| `./toc.sh status` | Is the game answering, and where |
| `./toc.sh logs` | Follow the game's log |
| `./toc.sh play` / `admin` | Open the web client / dashboard |
| `./toc.sh update` | Update to the newest version and restart |
| `./toc.sh build` | Rebuild from this folder's code and restart |
| `./toc.sh promote <name> [level]` | Set a character's level (default 70) |
| `./toc.sh backup [folder]` | Save `.env` and all game data to a dated archive |
| `./toc.sh restore <archive>` | Put a backup back |
| `./toc.sh doctor` | Check the installation without changing anything |
| `./toc.sh uninstall` | Remove it, keeping the data (`--purge` deletes it too) |

## Where Your Data Lives

```text
TimesOfChaos/              the code (a Git checkout; update replaces it)
  .env                     settings and the dashboard token (private)
  state/                   everything the game writes:
    player/                  characters and their snapshots
    gods/  heroes/           immortal and hero state
    area/                    the live world: notes, bug reports, max-load
                             counts, bans, builders' areas
    log/                     the game's logs and journals
    backups/                 the game's own archives of player files
    corpse/                  recoverable corpses
  toc-backups/             what ./toc.sh backup writes
```

**Back up** with `./toc.sh backup`: it asks the running game to save
everyone, then archives `.env` and `state/`. The archive holds the token and
every character's password hash, so keep it private. **Move** an
installation by installing on the new computer, then
`./toc.sh restore <archive>` there. Restoring sets the data it replaces
aside as `state.before-restore-<date>` rather than deleting it.

A restore puts the backup's data where **this** installation keeps its
data and leaves this `.env` as it is: its mode, data folder, ports and
token describe this computer. The backup's own settings are saved beside it
as `.env.from-backup` (private, like `.env`) for you to copy anything you
want from. It stops the game first and changes nothing at all if the game
cannot be stopped; a native installation then rebuilds the game for this
computer before starting it.

The game also archives player files itself every four hours into
`state/backups/` and keeps up to 30 snapshots per character. Those copies
live on the same disk: for safety, copy `./toc.sh backup` archives
elsewhere.

## Updating

`./toc.sh update` fetches the newest code and restarts:

- **Docker** downloads the matching prebuilt image. If none can be fetched
  (no network, a fork, a version not published yet), it builds the image
  from your checkout instead, which needs nothing but Docker and takes a few
  minutes. Set `TOC_BUILD=local` in `.env` to always build.
- **Native** compiles and loads the new world while the old game keeps
  running, and only then stops it for the few seconds the copy takes.

Either way the code is replaced and `state/` is kept: characters, notes,
reports, bans and builders' areas all survive. An update stops if you have
changed the code yourself; commit or stash your changes first.

## Letting Others Connect

Install with `--public` (Windows: `-Network Public`), or set
`MUD_BIND=0.0.0.0` in `.env` and restart. Only the game port is opened;
the dashboard stays on this computer.

For players outside your network, forward **TCP port 9000** on your router
to this computer and allow it in its firewall. **Never forward 9001**: the
dashboard is not built to face the internet. Players then connect with a
MUD client to your public address, port 9000. Read [SECURITY.md](../SECURITY.md)
first: the game protocol is plain Telnet.

For a server that runs nothing else, the [hosting guide](hosting-guide.md)
covers firewalls, reverse proxies and monitoring, and the
[Oracle Cloud ARM guide](oracle-arm-hosting.md) a free cloud host.

## Upgrading An Older Installation

Installations made before 2026-10-21 kept characters in the checkout's
`player/`, `gods/` and `heroes/` folders and, under Docker, the live world
inside the container, where every rebuild lost its notes, reports and
max-load counts. The first `./toc.sh start` or `update` with the new
version moves everything into `state/` by itself:

```text
Moved this installation's data into .../TimesOfChaos/state.
Copied the world's runtime files out of the old container.
```

It stops the old container first so its players are saved, copies, and
only then replaces it. The checkout's old folders are left alone until the
next `update`, which puts git's copies back so updates work again.

## Settings (.env)

The installer writes `.env` once and never replaces a value in it,
the dashboard token included. Restart after an edit.

| Setting | Default | Means |
|---|---|---|
| `TOC_MODE` | `docker` | `docker` or `native` |
| `TOC_STATE` | `./state` | The data folder; a relative path is relative to the install |
| `MUD_BIND` | `127.0.0.1` | `0.0.0.0` lets other computers reach the game |
| `MUD_PORT` | `9000` | The game's port on this computer |
| `WEB_ADMIN_PORT` | `9001` | The web client and dashboard's port |
| `WEB_ADMIN_BIND` | `127.0.0.1` | Keep it local, or a trusted private network |
| `WEB_ADMIN_TOKEN` | random | The dashboard's admin token |
| `TOC_IMAGE` | `ghcr.io/jeremydbean/toc2026:latest` | Docker: the image to run |
| `TOC_BUILD` | | `local` to always build the image here |
| `TOC_BASE_IMAGE` | `ubuntu:24.04` | Docker build: another Ubuntu 24.04 source (a mirror) |
| `TOC_BUILD_NETWORK` | `default` | Docker build: `host` if builds cannot resolve names behind a proxy |
| `TOC_SERVICE` | | Native: `systemd` when services were installed |
| `ORACLE_ENABLED`, `ANTHROPIC_API_KEY` | off | The in-game Oracle; see [the web admin guide](web-admin-guide.md) |

The [README](../README.md#runtime-configuration) lists the dashboard's
other settings.

## Platform Notes

- **Windows.** Docker Desktop runs on WSL 2 and needs virtualisation
  enabled in the firmware (most PCs have it on). If Docker Desktop
  reports otherwise, see
  [Docker's Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/).
  The install folder is checked out without Git's line-ending conversion,
  so a local image build gets the world files exactly as committed.
- **macOS.** Apple Silicon and Intel both work. Docker Desktop has to be
  opened once to accept its terms. Native mode installs Homebrew's Python;
  the Python Apple ships is too old for the web client. Native mode runs
  as background processes, so after a reboot run `./toc.sh start`.
- **Raspberry Pi.** Use 64-bit Raspberry Pi OS on a Pi 4 or 5. Docker
  works (the image is published for arm64); native mode uses less memory.
  For a Pi that does nothing but host the game, the
  [Pi appliance](../deploy/README.md) adds self-healing and scheduled
  updates.
- **A VPS.** Any 1 GB Linux server will do; use `--public` and open port
  9000 in its firewall.

## Uninstalling

```bash
./toc.sh uninstall            # remove containers/services and the image; keep state/ and .env
./toc.sh uninstall --purge    # also delete state/ and .env (asks you to type DELETE)
```

Then delete the folder. Docker itself stays installed.

## Troubleshooting

Start with `./toc.sh doctor`, which checks everything without changing
anything, and `./toc.sh logs`.

| You see | Do |
|---|---|
| `No prebuilt image could be fetched; building...` | Normal for a fork or a version not yet published. It builds locally once. |
| `port is already allocated` / `address already in use` | Another program uses 9000 or 9001. Set `MUD_PORT` / `WEB_ADMIN_PORT` in `.env`, then `./toc.sh start`. |
| `Docker did not become ready` | Open Docker Desktop, finish its first-run prompts, run the command again. |
| A build fails fetching packages behind a company proxy | Set `TOC_BUILD_NETWORK=host`, or `TOC_BASE_IMAGE` to an internal mirror of `ubuntu:24.04`. |
| `Update stopped: this checkout has local code changes` | You edited the code. `git stash` (or commit), then update. Your game data is not a code change. |
| `No saved character named ...` on promote | Create the character in the game and `QUIT` first; names are letters only. |
| `The world did not load; nothing was installed` (native) | A world file failed to load; the old game is still running. See `state/log/check-area.log`. |
| Players cannot connect from outside | Install with `--public` (or set `MUD_BIND=0.0.0.0`), open TCP 9000 in the firewall and router. |
| Linux: `permission denied` talking to Docker | Log out and back in once: the installer added you to the `docker` group. |

## For Maintainers

`.github/workflows/docker-image.yml` publishes the image for amd64 and
arm64 to `ghcr.io/jeremydbean/toc2026`, tagged `latest` and
`sha-<commit>`, after Validate passes on `main`. The first publish creates
the package as **private**: make it public once under the repository's
**Packages > toc2026 > Package settings > Change visibility**. Until then
installers simply build locally.

What the installers rely on, for anyone changing them, is in AGENTS.md
under "The Installers".
