#!/usr/bin/env bash
# Fresh-machine bootstrap for Linux: install Git, fetch Times of Chaos,
# and run the full installer. Every option the installer takes is passed
# through (./install.sh --help): --native, --public, --import-players...
#
#   curl -fsSLo /tmp/toc-install.sh \
#     https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_linux.sh
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
            echo "Usage: bootstrap_linux.sh [--install-dir PATH] [installer options]"
            echo "Installer options: --native --docker --public --local --import-players --no-service --no-start --open"
            exit 0
            ;;
        *) installer_args+=("$1") ;;
    esac
    shift
done

sudo_cmd=""
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo "sudo is required." >&2; exit 1; }
    sudo_cmd="sudo"
fi

if ! command -v git >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        $sudo_cmd apt-get update
        $sudo_cmd env DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates
    elif command -v dnf >/dev/null 2>&1; then
        $sudo_cmd dnf install -y git
    elif command -v pacman >/dev/null 2>&1; then
        $sudo_cmd pacman -Sy --needed --noconfirm git
    elif command -v zypper >/dev/null 2>&1; then
        $sudo_cmd zypper --non-interactive install git
    else
        echo "Install Git, then run this again." >&2
        exit 1
    fi
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

exec "$install_directory/install.sh" "${installer_args[@]+"${installer_args[@]}"}"
