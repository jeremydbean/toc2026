#!/bin/sh
set -eu

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

install -d -m 0755 /etc/toc2026 /etc/systemd/journald.conf.d /var/lib/toc2026
install -d -m 0755 /usr/local/sbin
install -m 0755 /home/toc/toc2026/deploy/toc2026-update \
    /usr/local/sbin/toc2026-update
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-game.service \
    /etc/systemd/system/toc2026-game.service
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-web.service \
    /etc/systemd/system/toc2026-web.service
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-player-backup.service \
    /etc/systemd/system/toc2026-player-backup.service
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-player-backup.timer \
    /etc/systemd/system/toc2026-player-backup.timer
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-update.service \
    /etc/systemd/system/toc2026-update.service
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-update.timer \
    /etc/systemd/system/toc2026-update.timer
install -m 0644 /home/toc/toc2026/deploy/systemd/toc2026-update.path \
    /etc/systemd/system/toc2026-update.path
install -m 0644 /home/toc/toc2026/deploy/journald/99-toc2026.conf \
    /etc/systemd/journald.conf.d/99-toc2026.conf
install -m 0644 /home/toc/toc2026/deploy/tmpfiles/toc2026.conf \
    /etc/tmpfiles.d/toc2026.conf

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
    toc2026-update.timer toc2026-update.path

if [ -s /etc/toc2026/player-backup.env ] \
   && [ -s /etc/toc2026/player-backup-recipient.txt ] \
   && [ -s /home/toc/.ssh/id_ed25519_github_toc_backup ]; then
    systemctl enable --now toc2026-player-backup.timer
else
    echo "Player backup credentials are not installed; timer not enabled yet."
fi

echo "ToC systemd configuration installed."
