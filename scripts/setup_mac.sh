#!/usr/bin/env bash
# One-touch, idempotent macOS installer for Times of Chaos.
#
# Docker (the default) installs Docker Desktop with Homebrew. Native
# (--native) compiles the game with Apple's Command Line Tools and needs
# only Homebrew's Python for the web client. Both keep all game data in
# ./state and the dashboard token in ./.env; rerunning keeps both.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOC_REPO_ROOT="$REPO_ROOT"
# shellcheck source=toc_common.sh
source "$REPO_ROOT/scripts/toc_common.sh"
# shellcheck source=toc_native.sh
source "$REPO_ROOT/scripts/toc_native.sh"

network="preserve"
mode="preserve"
start_game=1
open_browser=0
skip_prerequisites=0
import_players=0

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --docker              Run in Docker Desktop (the default for a new install)
  --native              Compile and run without Docker
  --local               Only this Mac can connect (the default)
  --public              Accept game connections from other computers
                        (the dashboard stays local)
  --import-players      Start the new world with the characters committed
                        to this repository instead of an empty one
  --no-start            Install and configure, but do not start
  --open                Open the web client once it is running
  --skip-prerequisites  Do not install Homebrew, Docker Desktop or Python
  -h, --help            Show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --docker) mode="docker" ;;
        --native) mode="native" ;;
        --local) network="local" ;;
        --public) network="public" ;;
        --import-players) import_players=1 ;;
        --no-start) start_game=0 ;;
        --open) open_browser=1 ;;
        --skip-prerequisites) skip_prerequisites=1 ;;
        --no-service) ;;     # macOS native runs as background processes
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This installer is for macOS. Run ./install.sh on the target machine." >&2
    exit 1
fi
if [ "$mode" = "preserve" ]; then
    mode="$(toc_mode)"
fi

echo "Setting up Times of Chaos ($mode) for macOS..."

load_brew() {
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

if [ "$skip_prerequisites" = "0" ]; then
    if ! xcode-select -p >/dev/null 2>&1; then
        echo "Opening Apple's Command Line Tools installer..."
        xcode-select --install 2>/dev/null || true
        echo
        echo "Finish the Apple installation, then run the installer again."
        echo "It is safe to rerun and continues where it stopped."
        exit 10
    fi

    load_brew
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
        load_brew
    fi
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew was installed but is not available in this shell." >&2
        echo "Open a new Terminal window and run the installer again." >&2
        exit 1
    fi

    command -v git >/dev/null 2>&1 || brew install git
    if [ "$mode" = "native" ]; then
        # Apple's python3 is too old for the web client; Homebrew's is not.
        toc_native_python >/dev/null 2>&1 || brew install python@3.12
    elif [ ! -d /Applications/Docker.app ] && [ ! -d "$HOME/Applications/Docker.app" ]; then
        echo "Installing Docker Desktop..."
        brew install --cask docker
    else
        echo "Docker Desktop is already installed."
    fi
fi
load_brew

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

toc_configure_instance "$network" "$mode" "$import_players"

if [ "$mode" = "native" ]; then
    toc_native_require_tools
    toc_native_build
    toc_native_venv
    toc_native_stop >/dev/null 2>&1 || true
    toc_native_install_code
else
    toc_require_docker
fi

if [ "$start_game" = "0" ]; then
    echo
    echo "Installation is complete. Run ./toc.sh start when you are ready."
    exit 0
fi

if [ "$mode" != "native" ]; then
    toc_start_docker
fi
"$REPO_ROOT/toc.sh" start

if [ "$open_browser" = "1" ]; then
    "$REPO_ROOT/toc.sh" play
fi

echo
echo "Next: create a character in the game, QUIT, then run"
echo "  ./toc.sh promote <name>"
echo "to make it your administrator."
echo "Future starts: double-click Start-ToC.command or run ./toc.sh start"
