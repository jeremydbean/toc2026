#!/bin/sh
set -e

cd /app/area

DEFAULT_PORT="${PORT:-${MUD_PORT:-9000}}"
WEB_ADMIN_PORT="${WEB_ADMIN_PORT:-9001}"
WEB_ADMIN_HOST="${WEB_ADMIN_HOST:-0.0.0.0}"

# Ensure expected data directories exist for writes
mkdir -p ../log ../player ../backups ../gods ../heroes ../corpse
touch webadmin.queue
export PYTHONPATH="/app:${PYTHONPATH}"

if [ "${WEB_ADMIN_ENABLED:-1}" != "0" ]; then
  python3 -m webadmin.server --host "$WEB_ADMIN_HOST" --port "$WEB_ADMIN_PORT" --queue /app/area/webadmin.queue --log-file /app/log/toc.log &
fi

if [ "$#" -eq 0 ]; then
  exec ./merc "$DEFAULT_PORT"
fi

# Allow explicit invocation without duplicating the binary name
if [ "$1" = "merc" ]; then
  shift
fi

# Accept a convenience alias for starting the server
if [ "$1" = "server" ]; then
  shift
  exec ./merc "$DEFAULT_PORT" "$@"
fi

# Support enabling newplayer lock while still respecting the env port
if [ "$1" = "newlock" ]; then
  shift
  PORT_ARG="$1"
  if [ -z "$PORT_ARG" ]; then
    PORT_ARG="$DEFAULT_PORT"
  else
    shift
  fi
  exec ./merc newlock "$PORT_ARG" "$@"
fi

case "$1" in
  [0-9]*)
    exec ./merc "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
