#!/bin/sh
set -eu

TOC_ROOT="${TOC_ROOT:-/home/toc/toc2026}"
cd "$TOC_ROOT"

dirty_paths="$(git status --porcelain --untracked-files=normal | awk '{print $2}' \
    | grep -Ev '^(player/|gods/|heroes/|backups/|corpse/|log/|area/shutdown\.txt$|area/webadmin\.queue$)' || true)"
if [ -n "$dirty_paths" ]; then
    echo "Refusing to update because non-runtime files have local changes:" >&2
    printf '%s\n' "$dirty_paths" >&2
    exit 1
fi

sudo systemctl start toc2026-player-backup.service
sudo systemctl stop toc2026-web.service toc2026-game.service

restart_services()
{
    sudo systemctl start toc2026-game.service toc2026-web.service || true
}
trap restart_services EXIT HUP INT TERM

git fetch origin main
git merge --ff-only origin/main
make -j1
(
    cd area
    ../merc --check-area
)
.venv/bin/python -m pip install --only-binary=:all: \
    -r webadmin/requirements.txt

sudo systemctl start toc2026-game.service toc2026-web.service
trap - EXIT HUP INT TERM
echo "ToC update complete."
