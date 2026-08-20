#!/usr/bin/env bash
# Fresh-machine bootstrap for Debian, Ubuntu, and Raspberry Pi OS.

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
            echo "Usage: bootstrap_linux.sh [--local|--public] [--install-dir PATH]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This bootstrap supports Debian, Ubuntu, and Raspberry Pi OS." >&2
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update
        apt-get install -y git ca-certificates
    else
        sudo apt-get update
        sudo apt-get install -y git ca-certificates
    fi
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

exec "$install_directory/install.sh" "$network"
