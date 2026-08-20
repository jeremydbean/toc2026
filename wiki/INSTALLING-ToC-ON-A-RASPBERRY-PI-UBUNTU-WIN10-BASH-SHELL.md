# Times of Chaos Installation Guide

This filename remains because old wiki links point here. These are the current
automated instructions for Windows, macOS, Debian/Ubuntu, and Raspberry Pi OS.
For production design, backups, reverse proxies, and service management, use
the complete [Hosting Guide](hosting-guide.md).

## What The Installer Does

The maintained installers perform the complete first-run path:

1. Install or check Git and Docker with the platform package manager.
2. Enable or initiate required operating-system components.
3. Create `player/`, `gods/`, `heroes/`, `corpse/`, `log/`, and `backups/`.
4. Generate a private `.env` and random 256-bit dashboard token.
5. Keep an existing token and runtime data unchanged on every rerun.
6. Start Docker Desktop or Docker Engine.
7. Build the image and start the game/dashboard container.
8. Wait for the game-port health check to pass.
9. Show connection details and optionally open the dashboard.

The default is intentionally local-only. Both ports bind to `127.0.0.1`.
Selecting public mode changes only the game binding to `0.0.0.0`; the dashboard
continues to bind to loopback.

## Already Downloaded The Repository

### Windows

Double-click `Install-ToC.cmd`, or open PowerShell in the repository and run:

```powershell
.\install.ps1
```

Use this only when remote players should connect:

```powershell
.\install.ps1 -Network Public
```

### macOS

Double-click `Install-ToC.command`, or run:

```bash
./install.sh
```

For a public game:

```bash
./install.sh --public
```

### Debian, Ubuntu, Or Raspberry Pi OS

```bash
./install.sh
```

Add `--public` for an intended network server. The Linux helper installs Docker
Engine and Compose v2, enables Docker under systemd, adds the current user to
the Docker group, and starts the first build with refreshed group membership.

## Fresh Windows 10/11 Machine

Windows Package Manager (`winget`) is provided by Microsoft App Installer on
current Windows 10 and Windows 11 systems. Open PowerShell and paste:

```powershell
$bootstrap = Join-Path $env:TEMP 'toc-bootstrap.ps1'
Invoke-WebRequest `
  'https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_windows.ps1' `
  -OutFile $bootstrap
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap
```

This installs Git, clones ToC to `$HOME\TimesOfChaos`, and launches the full
installer. To choose another location:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap `
  -InstallDirectory 'D:\Games\TimesOfChaos'
```

Add `-Public` to either bootstrap invocation for remote game connections.

Docker Desktop uses WSL 2 on the supported default path. If WSL was not already
enabled, Windows can require one restart. The installer says so explicitly;
restart and double-click `Install-ToC.cmd` in the cloned folder. Docker Desktop
can also display its own first-run license/setup window. Complete it while the
installer waits.

Direct Win32 compilation is not supported. Docker Desktop is the normal player
and host path; WSL remains available for native C development and validation.

## Fresh Mac

Open Terminal and paste:

```bash
bootstrap="$(mktemp /tmp/toc-bootstrap.XXXXXX)"
curl -fsSL \
  https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_macos.sh \
  -o "$bootstrap"
bash "$bootstrap"
```

The bootstrap clones to `~/TimesOfChaos`. Use another destination with:

```bash
bash "$bootstrap" --install-dir "$HOME/Games/TimesOfChaos"
```

Add `--public` for remote game connections.

macOS controls two interactions that a project script cannot accept for you:

- Apple displays the Command Line Tools installer if the tools are absent.
- Docker Desktop displays its subscription agreement and first-run choices.

Complete the displayed step and rerun the same bootstrap. Homebrew, the clone,
the generated token, and all runtime data are preserved. The helper downloads
the official Homebrew installer to a temporary file before executing it rather
than piping remote content directly to a shell.

## Fresh Debian, Ubuntu, Or Raspberry Pi OS

```bash
bootstrap="$(mktemp /tmp/toc-bootstrap.XXXXXX)"
curl -fsSL \
  https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_linux.sh \
  -o "$bootstrap"
bash "$bootstrap"
```

Use `--public` and/or `--install-dir PATH` with the final command as needed.
The Docker image builds locally for the machine architecture, including 64-bit
Raspberry Pi systems.

Do not install ToC with `sudo git clone`, recursive `chmod 755`, or broad root
ownership. Those old instructions damaged ownership and exposed sensitive
character data.

## Launcher Commands

Double-click `Start-ToC.cmd` on Windows or `Start-ToC.command` on macOS. The
terminal launchers expose the complete lifecycle:

| Operation | Windows | macOS/Linux |
|---|---|---|
| Start | `.\toc.ps1 start` | `./toc.sh start` |
| Rebuild/start | `.\toc.ps1 build` | `./toc.sh build` |
| Stop | `.\toc.ps1 stop` | `./toc.sh stop` |
| Restart | `.\toc.ps1 restart` | `./toc.sh restart` |
| Status | `.\toc.ps1 status` | `./toc.sh status` |
| Follow logs | `.\toc.ps1 logs` | `./toc.sh logs` |
| Diagnose | `.\toc.ps1 doctor` | `./toc.sh doctor` |
| Update | `.\toc.ps1 update` | `./toc.sh update` |
| Open dashboard | `.\toc.ps1 open` | `./toc.sh open` |

`update` refuses to pull over local repository changes. It performs only a
fast-forward pull, then rebuilds and waits for the health check.

## Installer Options

Windows:

```powershell
.\install.ps1 -Network Local
.\install.ps1 -Network Public
.\install.ps1 -NoStart
.\install.ps1 -NoBrowser
.\install.ps1 -SkipPrerequisites
```

macOS/Linux:

```bash
./install.sh --local
./install.sh --public
./install.sh --no-start
./install.sh --open
./install.sh --skip-prerequisites
```

`Preserve` is the Windows default and the equivalent Unix behavior when neither
`--local` nor `--public` is supplied. A fresh configuration becomes local; an
existing explicit binding remains unchanged.

## Connection And Files

After a default install:

```text
MUD client: localhost:9000
Dashboard:  http://127.0.0.1:9001
Health API: http://127.0.0.1:9001/api/health
```

The generated `.env` is ignored by Git. It controls host bindings/ports and the
admin token. Persistent data lives beside the source in `player/`, `gods/`,
`heroes/`, `corpse/`, `log/`, and `backups/`.

To keep ToC stopped, use the launcher `stop` command. The Compose restart policy
can otherwise restart a container after an in-game shutdown.

## Required Security Notice

The game protocol is unencrypted Telnet and player passwords use traditional
DES hashes, where only the first eight bytes are effective. Players must use a
unique game-only password. Keep the dashboard bound to loopback even with an
admin token because not every read route requires that token.

Read [Security](../SECURITY.md) before exposing the game port and the
[Hosting Guide](hosting-guide.md) before operating a public server.
