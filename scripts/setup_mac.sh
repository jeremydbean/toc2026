#!/usr/bin/env bash
# Idempotent macOS installer for the Docker-based Times of Chaos runtime.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOC_REPO_ROOT="$REPO_ROOT"
# shellcheck source=toc_common.sh
source "$REPO_ROOT/scripts/toc_common.sh"

network="preserve"
start_game=1
open_dashboard=0
skip_prerequisites=0

usage() {
    cat <<'EOF'
Usage: ./scripts/setup_mac.sh [options]

  --local               Bind the game to this Mac only
  --public              Accept remote game connections (dashboard stays local)
  --no-start            Install and configure without building or starting ToC
  --open                Open the dashboard after a successful start
  --skip-prerequisites  Do not install Homebrew or Docker Desktop
  -h, --help            Show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --local) network="local" ;;
        --public) network="public" ;;
        --no-start) start_game=0 ;;
        --open) open_dashboard=1 ;;
        --skip-prerequisites) skip_prerequisites=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This installer is for macOS. Run ./install.sh on the target machine." >&2
    exit 1
fi

echo "Setting up Times of Chaos for macOS..."

if [ "$skip_prerequisites" = "0" ]; then
    if ! xcode-select -p >/dev/null 2>&1; then
        echo "Opening Apple's Command Line Tools installer..."
        xcode-select --install 2>/dev/null || true
        echo
        echo "Finish the Apple installation, then double-click Install-ToC.command again."
        echo "The ToC installer is safe to rerun and will continue where it stopped."
        exit 10
    fi

    if ! command -v brew >/dev/null 2>&1; then
        brew_installer="$(mktemp -t toc-homebrew.XXXXXX)"
        trap 'rm -f "$brew_installer"' EXIT
        echo "Downloading the official Homebrew installer..."
        curl -fsSL \
            https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh \
            -o "$brew_installer"
        /bin/bash "$brew_installer"
        rm -f "$brew_installer"
        trap - EXIT
    fi

    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew was installed but is not available in this shell." >&2
        echo "Open a new Terminal window and rerun Install-ToC.command." >&2
        exit 1
    fi

    command -v git >/dev/null 2>&1 || brew install git
    if [ ! -d /Applications/Docker.app ] && [ ! -d "$HOME/Applications/Docker.app" ]; then
        echo "Installing Docker Desktop..."
        brew install --cask docker
    else
        echo "Docker Desktop is already installed."
    fi
fi

for docker_path in \
    /usr/local/bin \
    "$HOME/.docker/bin" \
    /Applications/Docker.app/Contents/Resources/bin \
    "$HOME/Applications/Docker.app/Contents/Resources/bin"; do
    if [ -x "$docker_path/docker" ]; then
        PATH="$docker_path:$PATH"
        export PATH
        break
    fi
done

toc_configure_instance "$network"

if [ "$start_game" = "0" ]; then
    echo
    echo "Installation and configuration are complete."
    echo "Run ./toc.sh build when you are ready to start."
    exit 0
fi

toc_require_docker
toc_start_docker
"$REPO_ROOT/toc.sh" build

if [ "$open_dashboard" = "1" ]; then
    "$REPO_ROOT/toc.sh" open
fi

echo
echo "Future starts: double-click Start-ToC.command or run ./toc.sh start"
