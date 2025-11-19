#!/bin/sh
set -eu

# Run the MUD server under Valgrind with leak checking enabled.
# Usage: ./scripts/run_valgrind.sh [--] [rom arguments]

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
BINARY_PATH="$SCRIPT_DIR/../area/rom"

exec valgrind \
  --leak-check=full \
  --show-leak-kinds=all \
  --track-origins=yes \
  --verbose \
  --log-file=valgrind.log \
  "$BINARY_PATH" "$@"
