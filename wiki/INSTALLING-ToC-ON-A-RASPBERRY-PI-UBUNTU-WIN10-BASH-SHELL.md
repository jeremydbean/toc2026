# Current Installation Instructions

This filename is retained because old wiki links point here. The former Ubuntu
18.04, `sudo git clone`, world-writable permission, copied-binary, and
machine-specific startup instructions were obsolete and unsafe.

Use the maintained [Hosting Guide](hosting-guide.md) for the complete setup,
configuration, persistence, security, backup, upgrade, and troubleshooting
reference. The short paths below cover common platforms.

## Recommended: Docker Compose

Install Git and Docker with Compose support, then:

### Linux, macOS, Or Raspberry Pi OS 64-bit

```bash
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
umask 077
printf 'WEB_ADMIN_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
docker compose up --build -d
docker compose logs -f game
```

### Windows 11 PowerShell With Docker Desktop

```powershell
git clone https://github.com/jeremydbean/toc2026.git
Set-Location toc2026

$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$token = [Convert]::ToHexString($bytes)
Set-Content -LiteralPath .env -Value "WEB_ADMIN_TOKEN=$token" -Encoding ascii

docker compose up --build -d
docker compose logs -f game
```

Connect to `localhost:9000`. The dashboard is at
`http://localhost:9001`.

Before putting the server on the Internet, edit the dashboard port mapping to
bind only to loopback:

```yaml
- "127.0.0.1:9001:9001"
```

To keep the service stopped:

```bash
docker compose stop
```

## Ubuntu Or Debian Native Build

```bash
sudo apt update
sudo apt install build-essential libcrypt-dev python3 python3-venv git

git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make clean
make

cd area
../merc --check-area
cd ..
./startup.sh 9000
```

Do not copy `merc` into `area/`. The supported Make output stays at the
repository root and is launched as `../merc` while `area/` is the working
directory.

## Windows 11 With WSL 2

Install WSL and an Ubuntu distribution from an elevated PowerShell session:

```powershell
wsl --install -d Ubuntu
```

Restart if Windows requests it. In the Ubuntu shell:

```bash
sudo apt update
sudo apt install build-essential libcrypt-dev python3 python3-venv git
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
make
cd area
../merc --check-area
../merc 9000
```

For repository development from a Windows checkout, the checked-in validator
translates the path and uses WSL:

```powershell
.\scripts\validate.ps1
.\scripts\validate.ps1 -RunSmoke
```

Direct native Win32 compilation is not a supported runtime path.

## Raspberry Pi

Use a currently supported 64-bit Raspberry Pi OS or Ubuntu release. Docker is
recommended because it supplies the expected Linux runtime and builds for the
Pi architecture locally.

1. Install Docker Engine and the Compose plugin from the current Docker/Raspberry
   Pi OS instructions.
2. Use the Docker Compose commands above.
3. Keep `player/`, `backups/`, and `log/` on reliable writable storage.
4. Maintain an encrypted backup on another device.
5. Monitor disk space, SD-card wear, memory, and temperature during builds.

The project does not require Ubuntu 18.04 and should not be installed with
recursive `chmod 755` or broad root ownership.

## Setup Helper Scripts

The repository contains convenience scripts:

```text
scripts/setup_windows.ps1
scripts/setup_linux.sh
scripts/setup_mac.sh
```

These install or assist with host prerequisites; they do not replace the
repository clone, token generation, build, validation, security review, or
backup setup. Read a script before running it with administrator privileges.

## Required Security Notice

The game port is plain Telnet and player passwords use traditional DES hashes,
where only the first eight bytes are effective. Players must use unique
game-only passwords. Port 9001 should remain private even with an admin token
because player browsing routes are not all token-protected.

See [Security](../SECURITY.md) and [Hosting Guide](hosting-guide.md).
