#!/bin/sh
# docker-entrypoint.sh
#
# Default behaviour (no args): run merc in an auto-restart loop.
#   - Crashes / exits without shutdown.txt  → wait 5 s, restart
#   - Immortal 'shutdown' writes shutdown.txt -> exit 0 (the container process
#     stops cleanly; an outer Docker restart policy may start it again)
#   - Immortal 'reboot' exits without shutdown.txt -> loop restarts merc
#
# Explicit args still work:
#   merc 9000            one-shot foreground run
#   newlock [port]       start with new-player lock
#   server               alias for 'merc $PORT'
#   any other command    exec directly (e.g. bash)

# Begin as root only to make the image's toc account match the host owner of
# bind-mounted state. Refuse root IDs, then re-exec this script unprivileged.
if [ "$(id -u)" -eq 0 ]; then
  TOC_UID="${TOC_UID:-1000}"
  TOC_GID="${TOC_GID:-1000}"
  case "$TOC_UID" in ''|*[!0-9]*|0) TOC_UID=1000 ;; esac
  case "$TOC_GID" in ''|*[!0-9]*|0) TOC_GID=1000 ;; esac

  if ! groupmod -o -g "$TOC_GID" toc \
      || ! usermod -o -u "$TOC_UID" -g "$TOC_GID" toc; then
    echo "Unable to configure the unprivileged toc account" >&2
    exit 1
  fi
  chown -R toc:toc \
    /app/area /app/player /app/gods /app/heroes /app/corpse /app/log /app/backups \
    || echo "Warning: one or more bind-mount ownership updates were rejected" >&2
  exec gosu toc "$0" "$@"
fi

cd /app/area

DEFAULT_PORT="${PORT:-${MUD_PORT:-9000}}"
WEB_ADMIN_PORT="${WEB_ADMIN_PORT:-9001}"
WEB_ADMIN_HOST="${WEB_ADMIN_HOST:-0.0.0.0}"

# Ensure expected data directories exist for writes
mkdir -p ../log ../player ../backups ../gods ../heroes ../corpse
touch webadmin.queue
export PYTHONPATH="/app:${PYTHONPATH}"

# Start web admin once (before any merc loop)
if [ "${WEB_ADMIN_ENABLED:-1}" != "0" ]; then
  cd /app && python3 -m webadmin.server \
      --host "$WEB_ADMIN_HOST" \
      --port "$WEB_ADMIN_PORT" \
      --mud-host 127.0.0.1 \
      --mud-port "$DEFAULT_PORT" \
      --queue /app/area/webadmin.queue \
      --log-file /app/log/toc.log \
      --area-path /app/area \
      --backup-path /app/backups \
      --player-path /app/player &
  cd /app/area
fi

# ── Explicit invocation (non-default args) ──────────────────────────────────
if [ "$#" -gt 0 ]; then
  if [ "$1" = "merc" ]; then shift; fi

  if [ "$1" = "server" ]; then
    shift
    exec merc "$DEFAULT_PORT" "$@"
  fi

  if [ "$1" = "newlock" ]; then
    shift
    PORT_ARG="${1:-$DEFAULT_PORT}"
    [ "$#" -gt 0 ] && shift
    exec merc newlock "$PORT_ARG" "$@"
  fi

  case "$1" in
    [0-9]*) exec merc "$@" ;;
    *)      exec "$@" ;;
  esac
fi

# ── Auto-restart loop ────────────────────────────────────────────────────────
# A stale shutdown.txt from a previous container run would suppress the first
# start, so remove it at entry.
rm -f shutdown.txt

while true; do
  TS="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$TS] Starting merc on port $DEFAULT_PORT" | tee -a /app/log/toc.log

  # Run merc; pipe output through tee (append). The '|| true' prevents
  # set -e from aborting the script when merc exits non-zero (e.g. crash).
  merc "$DEFAULT_PORT" 2>&1 | tee -a /app/log/toc.log || true

  TS="$(date '+%Y-%m-%d %H:%M:%S')"

  # Check for intentional immortal shutdown
  if [ -f shutdown.txt ]; then
    echo "[$TS] Shutdown requested (shutdown.txt found). Stopping." \
        | tee -a /app/log/toc.log
    rm -f shutdown.txt
    exit 0
  fi

  echo "[$TS] merc exited unexpectedly. Restarting in 5 seconds..." \
      | tee -a /app/log/toc.log
  sleep 5
done
