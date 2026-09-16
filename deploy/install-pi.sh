#!/bin/sh
set -eu

case "${1:-}" in
    ''|--refresh) ;;
    *) echo "Usage: $0 [--refresh]" >&2; exit 2 ;;
esac

pending_install=
cleanup()
{
    if [ -n "$pending_install" ]; then
        rm -f -- "$pending_install"
    fi
}
trap cleanup EXIT HUP INT TERM

install_asset()
{
    source_path=$1
    destination_path=$2
    mode=$3
    pending_install="$destination_path.new.$$"
    install -m "$mode" "$source_path" "$pending_install"
    mv -f "$pending_install" "$destination_path"
    pending_install=
}

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi
if ! id toc >/dev/null 2>&1; then
    echo "The toc service account does not exist." >&2
    exit 1
fi
if [ ! -x /home/toc/toc2026/merc ]; then
    echo "Build /home/toc/toc2026/merc before installing services." >&2
    exit 1
fi
if [ ! -x /home/toc/toc2026/.venv/bin/python ]; then
    echo "Create the dashboard virtual environment before installing services." >&2
    exit 1
fi
if [ ! -s /home/toc/toc2026/.env ]; then
    echo "Create /home/toc/toc2026/.env before installing services." >&2
    exit 1
fi

install -d -m 0755 /etc/toc2026 /etc/systemd/journald.conf.d \
    /etc/systemd/system.conf.d /etc/apt/apt.conf.d /var/lib/toc2026
install -d -m 0755 /usr/local/sbin
for command_name in update namecheap-ddns led recover stable healthcheck maintenance; do
    install_asset "/home/toc/toc2026/deploy/toc2026-$command_name" \
        "/usr/local/sbin/toc2026-$command_name" 0755
done
systemd-analyze verify \
    /home/toc/toc2026/deploy/systemd/*.service \
    /home/toc/toc2026/deploy/systemd/*.timer \
    /home/toc/toc2026/deploy/systemd/*.path
for unit_path in /home/toc/toc2026/deploy/systemd/toc2026-*; do
    install_asset "$unit_path" "/etc/systemd/system/$(basename "$unit_path")" 0644
done
install_asset /home/toc/toc2026/deploy/systemd/99-toc2026-watchdog.conf \
    /etc/systemd/system.conf.d/99-toc2026-watchdog.conf 0644
install_asset /home/toc/toc2026/deploy/journald/99-toc2026.conf \
    /etc/systemd/journald.conf.d/99-toc2026.conf 0644
install_asset /home/toc/toc2026/deploy/tmpfiles/toc2026.conf \
    /etc/tmpfiles.d/toc2026.conf 0644
install_asset /home/toc/toc2026/deploy/apt/52toc2026-maintenance \
    /etc/apt/apt.conf.d/52toc2026-maintenance 0644

install -d -m 0755 /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
systemd-tmpfiles --create /etc/tmpfiles.d/toc2026.conf
if [ ! -s /var/lib/toc2026/deployed-commit ]; then
    runuser -u toc -- git -C /home/toc/toc2026 rev-parse HEAD \
        >/var/lib/toc2026/deployed-commit
    chmod 0644 /var/lib/toc2026/deployed-commit
fi
systemctl daemon-reload
systemctl restart systemd-journald
systemctl enable --now toc2026-game.service toc2026-web.service \
    toc2026-healthcheck.timer toc2026-update.timer toc2026-update.path
systemctl enable --now toc2026-stable.service
if [ -e /sys/class/leds/ACT/trigger ]; then
    systemctl enable --now toc2026-led.service
else
    echo "ACT LED is unavailable; game status indicator not enabled."
fi

if [ -s /etc/toc2026/player-backup.env ] \
   && [ -s /etc/toc2026/player-backup-recipient.txt ] \
   && [ -s /home/toc/.ssh/id_ed25519_github_toc_backup ]; then
    systemctl enable --now toc2026-player-backup.timer
else
    echo "Player backup credentials are not installed; timer not enabled yet."
fi

if [ -s /etc/toc2026/namecheap-ddns.env ] \
   && ! grep -q 'replace-with-' /etc/toc2026/namecheap-ddns.env; then
    if ! command -v curl >/dev/null 2>&1; then
        echo "curl is required for Namecheap Dynamic DNS." >&2
        exit 1
    fi
    systemctl enable --now toc2026-namecheap-ddns.timer
else
    echo "Namecheap Dynamic DNS credentials are not installed; timer not enabled yet."
fi

if command -v unattended-upgrade >/dev/null 2>&1; then
    systemctl enable --now toc2026-maintenance.timer
else
    echo "unattended-upgrades is unavailable; weekly OS maintenance not enabled yet."
fi

echo "ToC systemd configuration installed."
