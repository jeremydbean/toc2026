#!/bin/sh
# docker-entrypoint.sh -- the Times of Chaos container.
#
# Default (no arguments): bring the live world up to date from the image,
# start the dashboard, and run merc in a restart loop.
#   - merc crashes or exits without shutdown.txt -> restart after 5 s
#   - an immortal's REBOOT (no shutdown.txt)     -> restart
#   - an immortal's SHUTDOWN writes shutdown.txt -> the container exits 0
#     (compose's restart policy may start it again; `toc.sh stop` will not)
#   - `docker stop` / `toc.sh stop` (SIGTERM)    -> merc saves every player
#     and exits, then the container stops. Before 2026-10-21 the signal
#     reached only this shell, which ignored it as PID 1, and Docker
#     killed the game ten seconds later without a save.
#
# Explicit arguments still work:
#   merc 9000 | server | newlock [port] | sync | any other command
set -eu

# Begin as root only to give the image's toc account the host owner's IDs
# for bind-mounted state. Root IDs are refused; then re-exec unprivileged.
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
  for d in /app/area /app/player /app/gods /app/heroes /app/corpse /app/log /app/backups; do
    mkdir -p "$d"
    # Only what is not already ours: a large player directory on a slow
    # bind mount (Docker Desktop) made a blanket chown -R take minutes.
    find "$d" \( ! -user toc -o ! -group toc \) -exec chown toc:toc {} + 2>/dev/null \
      || echo "Warning: could not take ownership of everything in $d" >&2
  done
  exec gosu toc "$0" "$@"
fi

DEFAULT_PORT="${PORT:-${MUD_PORT:-9000}}"
WEB_ADMIN_PORT="${WEB_ADMIN_PORT:-9001}"
WEB_ADMIN_HOST="${WEB_ADMIN_HOST:-0.0.0.0}"
LOG=/app/log/toc.log        # merc writes this itself (GAME_LOG_FILE)
OUT=/app/log/game.log       # merc's stdout and stderr, as on the host

mkdir -p /app/log /app/player /app/backups /app/gods /app/heroes /app/corpse

# The live world: code from the image, state from the volume.
toc-sync-area /app/dist/area /app/area
cd /app/area
: > webadmin.queue
export PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

web_pid=""
start_dashboard() {
  [ "${WEB_ADMIN_ENABLED:-1}" != "0" ] || return 0
  (cd /app && exec python3 -m webadmin.server \
      --host "$WEB_ADMIN_HOST" \
      --port "$WEB_ADMIN_PORT" \
      --mud-host 127.0.0.1 \
      --mud-port "$DEFAULT_PORT" \
      --queue /app/area/webadmin.queue \
      --log-file "$LOG" \
      --event-log-file /app/log/webadmin-events.tsv \
      --area-path /app/area \
      --backup-path /app/backups \
      --player-path /app/player) &
  web_pid=$!
}

# ── Explicit invocation ─────────────────────────────────────────────────────
if [ "$#" -gt 0 ]; then
  if [ "$1" = "sync" ]; then exit 0; fi       # the sync above was the job
  if [ "$1" = "merc" ]; then shift; fi
  if [ "$#" -gt 0 ] && [ "$1" = "server" ]; then
    shift
    start_dashboard
    exec merc "$DEFAULT_PORT" "$@"
  fi
  if [ "$#" -gt 0 ] && [ "$1" = "newlock" ]; then
    shift
    PORT_ARG="${1:-$DEFAULT_PORT}"
    [ "$#" -gt 0 ] && shift
    start_dashboard
    exec merc newlock "$PORT_ARG" "$@"
  fi
  case "${1:-}" in
    [0-9]*) start_dashboard; exec merc "$@" ;;
    *)      exec "$@" ;;
  esac
fi

# ── Restart loop ────────────────────────────────────────────────────────────
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
# To the game's log, for the dashboard, and to `docker logs`.
say() { echo "[$(stamp)] $*" | tee -a "$LOG"; }

merc_pid=""
stopping=0
on_signal() {
  stopping=1
  if [ -n "$merc_pid" ] && kill -0 "$merc_pid" 2>/dev/null; then
    say "Stop requested; saving players and shutting the game down."
    kill -TERM "$merc_pid" 2>/dev/null || true
  fi
}
trap on_signal TERM INT HUP

start_dashboard

# merc writes log/toc.log itself and copies every line to stderr, so its
# output goes to game.log (redirecting it into toc.log doubled every
# line), and following game.log is what `docker logs` and `toc.sh logs`
# show.
# Kept to one old generation; the game's own log is trimmed by the game.
if [ -f "$OUT" ] && [ "$(wc -c < "$OUT")" -gt 52428800 ]; then
  mv -f "$OUT" "$OUT.1"
fi
touch "$OUT"
tail -n 0 -F "$OUT" 2>/dev/null &
tail_pid=$!

# A stale marker from a previous run would stop the first start.
rm -f shutdown.txt

status=0
while [ "$stopping" = 0 ]; do
  say "Starting merc on port $DEFAULT_PORT (${TOC_VERSION:-dev})"
  merc "$DEFAULT_PORT" >> "$OUT" 2>&1 &
  merc_pid=$!
  # wait returns early when a trapped signal arrives; keep waiting until
  # merc has finished saving and exited.
  while kill -0 "$merc_pid" 2>/dev/null; do
    wait "$merc_pid" 2>/dev/null && status=0 || status=$?
  done
  merc_pid=""

  if [ "$stopping" = 1 ]; then
    say "The game has stopped; every player was saved."
    break
  fi
  if [ -f shutdown.txt ]; then
    say "Shutdown requested in game (shutdown.txt). Stopping."
    rm -f shutdown.txt
    break
  fi
  say "merc exited (status $status). Restarting in 5 seconds..."
  sleep 5 &
  wait $! 2>/dev/null || true
done

[ -n "$web_pid" ] && kill -TERM "$web_pid" 2>/dev/null || true
kill "$tail_pid" 2>/dev/null || true
exit 0
