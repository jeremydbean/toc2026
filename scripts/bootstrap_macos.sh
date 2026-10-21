#!/usr/bin/env bash
# Fresh-machine bootstrap for macOS: install Git, fetch Times of Chaos,
# and run the full installer. Installer options pass through
# (--native, --public, --import-players...).
#
#   curl -fsSLo /tmp/toc-install.sh \
#     https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_macos.sh
#   bash /tmp/toc-install.sh [--native] [--public]

set -euo pipefail

install_directory="${TOC_INSTALL_DIR:-$HOME/TimesOfChaos}"
repository="${TOC_REPOSITORY:-https://github.com/jeremydbean/toc2026.git}"
installer_args=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --install-dir)
            shift
            [ "$#" -gt 0 ] || { echo "--install-dir needs a path" >&2; exit 2; }
            install_directory="$1"
            ;;
        -h|--help)
            echo "Usage: bootstrap_macos.sh [--install-dir PATH] [installer options]"
            echo "Installer options: --native --docker --public --local --import-players --no-start"
            exit 0
            ;;
        *) installer_args+=("$1") ;;
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
    echo "Using the existing checkout in $install_directory"
    if [ -z "$(git -C "$install_directory" status --porcelain -- . ':(exclude)player' \
            ':(exclude)gods' ':(exclude)heroes' ':(exclude)log')" ]; then
        git -C "$install_directory" pull --ff-only \
            || echo "Could not update it; continuing with the version it has."
    else
        echo "It has local code changes, which were kept; skipping the update."
    fi
elif [ -e "$install_directory" ] && [ -n "$(ls -A "$install_directory" 2>/dev/null)" ]; then
    echo "$install_directory is not empty and is not a Times of Chaos checkout." >&2
    echo "Choose another place with --install-dir PATH." >&2
    exit 1
else
    mkdir -p "$(dirname "$install_directory")"
    # The latest commit only: the history carries years of player saves.
    git clone --depth 1 "$repository" "$install_directory"
fi

exec "$install_directory/install.sh" --open "${installer_args[@]+"${installer_args[@]}"}"
