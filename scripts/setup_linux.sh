#!/usr/bin/env bash
# Idempotent installer for current Debian, Ubuntu, and Raspberry Pi OS hosts.

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
Usage: ./scripts/setup_linux.sh [options]

  --local               Bind the game to this computer only
  --public              Accept remote game connections (dashboard stays local)
  --no-start            Install and configure without building or starting ToC
  --open                Open the dashboard after a successful start
  --skip-prerequisites  Do not install host packages
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

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This automatic Linux installer supports Debian, Ubuntu, and Raspberry Pi OS." >&2
    echo "Other distributions can install Git, Docker Engine, and Compose v2, then run:" >&2
    echo "  ./install.sh --skip-prerequisites" >&2
    exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
    TARGET_USER="${SUDO_USER:-root}"
else
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo is required to install host packages." >&2
        exit 1
    fi
    SUDO="sudo"
    TARGET_USER="${USER}"
fi

echo "Setting up Times of Chaos for Debian/Ubuntu..."
group_added=0

if [ "$skip_prerequisites" = "0" ]; then
    $SUDO apt-get update

    compose_package=""
    for candidate in docker-compose-v2 docker-compose-plugin; do
        if apt-cache show "$candidate" >/dev/null 2>&1; then
            compose_package="$candidate"
            break
        fi
    done

    packages=(git ca-certificates openssl docker.io)
    if [ -n "$compose_package" ]; then
        packages+=("$compose_package")
    fi
    $SUDO apt-get install -y "${packages[@]}"

    if command -v systemctl >/dev/null 2>&1 && \
        [ "$(ps -p 1 -o comm= 2>/dev/null)" = "systemd" ]; then
        $SUDO systemctl enable --now docker
    fi

    if [ "$TARGET_USER" != "root" ] && getent group docker >/dev/null 2>&1; then
        if ! id -nG "$TARGET_USER" | grep -qw docker; then
            $SUDO usermod -aG docker "$TARGET_USER"
            echo "Added $TARGET_USER to the docker group."
            group_added=1
        fi
    fi
fi

# If the whole script was launched with sudo, return to the invoking account
# before creating private files or running Compose. runuser refreshes groups.
if [ "$(id -u)" -eq 0 ] && [ "$TARGET_USER" != "root" ]; then
    rerun_args=(--skip-prerequisites)
    case "$network" in
        local) rerun_args+=(--local) ;;
        public) rerun_args+=(--public) ;;
    esac
    [ "$start_game" = "0" ] && rerun_args+=(--no-start)
    [ "$open_dashboard" = "1" ] && rerun_args+=(--open)

    if command -v runuser >/dev/null 2>&1; then
        exec runuser -u "$TARGET_USER" -- "$REPO_ROOT/install.sh" "${rerun_args[@]}"
    fi
    exec sudo -u "$TARGET_USER" -H "$REPO_ROOT/install.sh" "${rerun_args[@]}"
fi

toc_configure_instance "$network"
toc_require_docker

if [ "$start_game" = "0" ]; then
    echo
    echo "Installation and configuration are complete."
    echo "Run ./toc.sh build when you are ready to start."
    exit 0
fi

if toc_docker_ready; then
    "$REPO_ROOT/toc.sh" build
elif [ "$group_added" = "1" ] && command -v sudo >/dev/null 2>&1; then
    echo "Starting the first build with refreshed Docker group membership..."
    sudo -u "$TARGET_USER" -H bash -lc \
        "cd '$REPO_ROOT' && TOC_DOCKER_WAIT_SECONDS='$TOC_DOCKER_WAIT_SECONDS' ./toc.sh build"
else
    toc_start_docker
    "$REPO_ROOT/toc.sh" build
fi

if [ "$open_dashboard" = "1" ]; then
    "$REPO_ROOT/toc.sh" open
fi

echo
echo "Future starts: ./toc.sh start"
