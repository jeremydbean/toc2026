#!/usr/bin/env bash
# Fresh-machine bootstrap: install Git, clone ToC, and run the full installer.

set -euo pipefail

install_directory="${TOC_INSTALL_DIR:-$HOME/TimesOfChaos}"
network="--local"
repository="https://github.com/jeremydbean/toc2026.git"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --public) network="--public" ;;
        --local) network="--local" ;;
        --install-dir)
            shift
            [ "$#" -gt 0 ] || { echo "--install-dir needs a path" >&2; exit 2; }
            install_directory="$1"
            ;;
        -h|--help)
            echo "Usage: bootstrap_macos.sh [--local|--public] [--install-dir PATH]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This bootstrap is for macOS." >&2
    exit 1
fi

echo "Times of Chaos fresh-machine setup"

if ! xcode-select -p >/dev/null 2>&1; then
    echo "Opening Apple's Command Line Tools installer..."
    xcode-select --install 2>/dev/null || true
    echo "Finish that installation, then run this bootstrap again."
    exit 10
fi

if ! command -v git >/dev/null 2>&1; then
    if ! command -v brew >/dev/null 2>&1; then
        brew_installer="$(mktemp -t toc-homebrew.XXXXXX)"
        trap 'rm -f "$brew_installer"' EXIT
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
    brew install git
fi

if [ -d "$install_directory/.git" ]; then
    echo "Using existing checkout: $install_directory"
    if [ -z "$(git -C "$install_directory" status --porcelain)" ]; then
        git -C "$install_directory" pull --ff-only
    else
        echo "Existing local changes were preserved; skipping git pull."
    fi
elif [ -e "$install_directory" ] && [ -n "$(ls -A "$install_directory" 2>/dev/null)" ]; then
    echo "Install directory is not empty and is not a Git checkout: $install_directory" >&2
    exit 1
else
    mkdir -p "$(dirname "$install_directory")"
    git clone "$repository" "$install_directory"
fi

exec "$install_directory/install.sh" "$network" --open
