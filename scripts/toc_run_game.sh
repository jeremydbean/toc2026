#!/bin/sh
# Run the game from a native install's live tree, restarting it after a
# crash or an in-game REBOOT, as docker-entrypoint.sh does in the image.
#
#   scripts/toc_run_game.sh <state-dir> [port]
#
# <state-dir> holds merc and area/ beside player/, log/ and the rest; the
# game runs in <state-dir>/area because its paths are relative to it.
#   - a crash or REBOOT (no shutdown.txt) -> restart after 5 s
#   - an immortal's SHUTDOWN (shutdown.txt) -> exit 0
#   - SIGTERM/SIGINT (toc.sh stop, systemctl stop) -> merc saves every
#     player and exits, then this exits 0
# TOC_BIND_ADDRESS, when set, keeps the game on that one interface.
set -eu

state="${1:?usage: toc_run_game.sh <state-dir> [port]}"
port="${2:-${MUD_PORT:-9000}}"
state="$(cd "$state" && pwd)"
LOG="$state/log/toc.log"        # merc writes this itself
OUT="$state/log/game.log"       # merc's stdout and stderr

if [ ! -x "$state/merc" ]; then
    echo "toc_run_game: $state/merc is missing; run ./toc.sh build" >&2
    exit 1
fi
mkdir -p "$state/log" "$state/player" "$state/gods" "$state/heroes" \
         "$state/corpse" "$state/backups"
cd "$state/area"

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

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

if [ -f "$OUT" ] && [ "$(wc -c < "$OUT")" -gt 52428800 ]; then
    mv -f "$OUT" "$OUT.1"
fi
rm -f shutdown.txt

status=0
while [ "$stopping" = 0 ]; do
    say "Starting merc on port $port"
    "$state/merc" "$port" >> "$OUT" 2>&1 &
    merc_pid=$!
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
exit 0
