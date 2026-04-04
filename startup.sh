#!/bin/bash
# startup.sh — bare-metal / VM auto-restart wrapper for merc
#
# Usage: ./startup.sh [port]   (default port 9000)
#
# Restart logic:
#   - merc crashes or exits without shutdown.txt → restart after 5 s
#   - Immortal 'reboot' command         → restart (no shutdown.txt written)
#   - Immortal 'shutdown' command       → exit cleanly (shutdown.txt written)
#
# Output is appended to ../log/toc.log and echoed to stdout.
# Run this in a screen/tmux session or as a systemd service so it survives
# terminal disconnects.

PORT="${1:-${MUD_PORT:-${PORT:-9000}}}"
AREA_DIR="$(cd "$(dirname "$0")/area" && pwd)"
LOG_DIR="$(cd "$(dirname "$0")" && pwd)/log"
LOG_FILE="$LOG_DIR/toc.log"
MERC="$(cd "$(dirname "$0")" && pwd)/merc"

if [ ! -x "$MERC" ]; then
    echo "ERROR: merc binary not found at $MERC" >&2
    echo "Run 'make' first." >&2
    exit 1
fi

mkdir -p "$LOG_DIR"
cd "$AREA_DIR"

# Remove any stale shutdown.txt from a previous run
rm -f shutdown.txt

_log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

_log "=== ToC startup — port $PORT ==="

while true; do
    _log "Starting merc..."

    "$MERC" "$PORT" 2>&1 | tee -a "$LOG_FILE" || true

    if [ -f shutdown.txt ]; then
        _log "Shutdown requested (shutdown.txt). Stopping."
        rm -f shutdown.txt
        exit 0
    fi

    _log "merc exited unexpectedly. Restarting in 5 seconds..."
    sleep 5
done
