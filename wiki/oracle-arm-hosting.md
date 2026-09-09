# Oracle Always Free ARM Hosting

## Compatibility Status

On September 9, 2026, the published game source at `d31d074` passed the ARM64
build and smoke checks below using Ubuntu 24.04's AArch64 GCC 13 toolchain and
QEMU user-mode emulation. An older local working tree was checked separately.
No game-source changes were required for the checks that passed.

- The Make/GNU89 and CMake/C17 builds produced Linux AArch64 executables.
- Both executables loaded 94 native areas, 2,336 mobile definitions,
  3,557 object definitions, 7,781 rooms, and 6,262 active mobiles.
- An actual TCP connection received the greeting, rejected an invalid name,
  entered and cancelled name confirmation, and reached character creation.
- A disposable character exercised password hashing, rejection of a mismatched
  confirmation, and successful confirmation through to race selection.
- The Make executable remained running for another 25 seconds after login tests.
- All 22 existing live gameplay tests passed against the published-source ARM
  Make executable under QEMU (311.7 seconds total). Coverage included character
  creation, core commands, save/reconnect, password rejection, login throttling,
  money conservation, hostile amounts, persistent settings, MCCP2 compression,
  and MSSP/GMCP/NAWS protocol handling. The test harness used a local QEMU
  launcher in place of its native binary; characters and saves were disposable.
- Linux ARM64 binary dependencies resolved for the dashboard and auxiliary
  scripts on Python 3.11 and 3.12, including Pydantic Core, uvloop, httptools,
  watchfiles, watchdog, PyYAML, and websockets.
- All nine installation-asset tests passed. Whitespace validation also passed.

The source uses a POSIX C game process, zlib for MCCP2 compression, and a
Python/FastAPI dashboard. The
Debian Bookworm Docker base supports ARM64 and the installer chooses host-native
Debian/Ubuntu packages. Build from source on the ARM host; do not copy an x86
`merc` executable or its object files there.

These are emulated build and startup results, not a hardware performance test
or certification of every gameplay path. The full Docker image, dashboard
runtime on ARM, sustained player load, and real Oracle networking still need
verification on the chosen host. No live accounts were used or changed, and no
cloud instance was provisioned. The published-source check was performed in a
separate checkout to preserve the older checkout's pending gameplay changes.

## Free Instance Configuration

For a new installation, use:

| Setting | Choice |
| --- | --- |
| Instance shape | `VM.Standard.A1.Flex` (Ampere ARM64) |
| Operating system | Ubuntu 24.04 ARM64, marked Always Free eligible |
| CPU | 2 OCPUs |
| Memory | 6 GB |
| Boot disk | 50 GB, using the Always Free allowance |
| Region | The account's home region, preferably near the players |

This is a suggested starting configuration, not a measured minimum.

As checked on September 9, 2026, Oracle documents 1,500 A1 OCPU-hours and
9,000 GB-hours per month, equivalent to 2 OCPUs and 12 GB RAM for Always Free
tenancies, plus 200 GB of combined boot/block storage. These allowances are
shared across the account, not repeated for each server. Confirm the console's
Always Free eligibility and account limits before creating resources. Do not
rely on temporary trial credits to cover a configuration above these limits.

Free compute capacity may be unavailable in a region. Oracle can reclaim
instances meeting its idle-use criteria over seven days, so free hosting is not
an uninterrupted-service guarantee. Keep recoverable off-host backups of player
and world state. Do not manufacture CPU/network activity to evade idle policies.

Primary references:

- [Oracle Always Free resources and reclamation rules](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Official Debian image architectures](https://hub.docker.com/_/debian)

## Installation And First Checks

SSH into the Ubuntu instance, then run:

```bash
uname -m
sudo apt-get update
sudo apt-get install -y git ca-certificates
git clone https://github.com/jeremydbean/toc2026.git
cd toc2026
./install.sh --local
./toc.sh status
```

`uname -m` should report `aarch64`. The existing installer installs Docker and
Compose, builds the game for the host architecture, generates private
configuration, and starts both services. Initially keep them local while
validating the installation.

From your own computer, forward the dashboard through SSH (replace `SERVER_IP`):

```bash
ssh -L 9001:127.0.0.1:9001 ubuntu@SERVER_IP
```

Leave that SSH connection open and visit `http://127.0.0.1:9001/client`.
Use another unused local port if 9001 already hosts a local TOC dashboard.
The tunnel is for initial private access; it is not a permanent public URL.

For public players, follow the [Hosting Guide](hosting-guide.md) for the game
port, HTTPS browser access, administration protection, and persistent data.
Both Oracle's network rules and the guest firewall must permit the intended
traffic. Do not open the whole dashboard to the internet just to test ARM.

## Repeatable Native Or Emulated Smoke Test

On a disposable native ARM development host, install the build dependencies and
run from the repository root:

```bash
sudo apt-get install -y build-essential libcrypt-dev zlib1g-dev python3
make clean
make
python3 scripts/smoke_game.py --binary ./merc
python3 -m unittest discover -s tests -p test_live_gameplay.py -v
```

The script copies only world `.are` definitions and `area.lst` into a temporary
directory. It creates empty runtime directories and a synthetic PK table,
validates the world, starts the binary on an available high port, exercises
login/password confirmation, observes the loop, and terminates its process.
It never loads the repository's player files or sends commands to a live game.
The legacy server binds all interfaces, so run this test behind a firewall or
inside an isolated network. Do not run `make clean` in a live deployment.

On an x86 Linux development host with an ARM compiler, sysroot, and QEMU, build
in a separate directory and provide its executable and emulator explicitly:

```bash
python3 scripts/smoke_game.py \
  --binary /absolute/path/to/arm64/merc \
  --runner 'qemu-aarch64 -L /usr/aarch64-linux-gnu'
```

The emulator sysroot must supply any dynamic ARM libraries required by the
binary, including `libcrypt.so.1` and `libz.so.1` when dynamically linked. The
Make audit linked Ubuntu's ARM `libcrypt.a` and `libz.a` and used the
cross-toolchain's ARM libc at runtime. The CMake audit used ARM shared crypt
and static zlib. Emulation timings should not be used to size a cloud VM.
