#!/bin/bash
set -euo pipefail

# Run the MUD server under Valgrind with leak checking enabled.
# Usage: ./scripts/run_valgrind.sh [--] [merc arguments]

cd "$(dirname "$0")/.."
cd area
exec valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes ./merc "$@"
