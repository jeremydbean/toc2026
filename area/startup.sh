#!/usr/bin/env bash
# Compatibility wrapper for hosts that historically launched from area/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "area/startup.sh now delegates to the maintained root startup.sh." >&2
exec "$REPO_ROOT/startup.sh" "$@"
