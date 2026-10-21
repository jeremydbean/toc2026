# Times of Chaos Installation Guide

> **Moved.** Installing your own copy -- Windows, macOS, Linux, Raspberry
> Pi, Docker or native -- is now the [Install Guide](install-guide.md).
> This filename remains because old wiki links point here.

> **The live server does not run on a Raspberry Pi.** It runs on Oracle
> Cloud (it was on a Pi until 2026-09-29, then a Hyper-V VM, then Oracle
> from 2026-10-01). For the real host, its deploys and disaster recovery,
> see [disaster-recovery.md](disaster-recovery.md).

The short version, from a checkout:

| Platform | Run |
|---|---|
| Windows | `Install-ToC.cmd`, or `.\install.ps1` |
| macOS | `Install-ToC.command`, or `./install.sh` |
| Linux, Raspberry Pi OS | `./install.sh` (add `--native` to run without Docker) |

Add `--public` (`-Network Public` on Windows) for remote players. A dedicated
headless Pi appliance is documented in [deploy/README.md](../deploy/README.md).
