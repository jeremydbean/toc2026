#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$(uname -s)" in
    Darwin) exec "$REPO_ROOT/scripts/setup_mac.sh" "$@" ;;
    Linux)  exec "$REPO_ROOT/scripts/setup_linux.sh" "$@" ;;
    *)
        echo "This installer supports macOS and Debian/Ubuntu Linux." >&2
        echo "On Windows, run Install-ToC.cmd or .\\install.ps1." >&2
        exit 1
        ;;
esac
