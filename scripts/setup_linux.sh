#!/usr/bin/env bash
# One-touch, idempotent Linux installer for Times of Chaos.
#
# Docker (the default) works on any distribution Docker supports. Native
# (--native) compiles the game here and runs it without Docker -- the
# smaller footprint for a Raspberry Pi or a small VPS. Both keep all game
# data in ./state and the dashboard token in ./.env, and rerunning the
# installer keeps both.
#
# Package managers: apt (Debian, Ubuntu, Raspberry Pi OS, Mint), dnf
# (Fedora, RHEL, Rocky, Alma), pacman (Arch, Manjaro), zypper (openSUSE).

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
service="auto"
original_args=("$@")

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --docker              Run in Docker (the default for a new install)
  --native              Compile and run without Docker
  --local               Only this computer can connect (the default)
  --public              Accept game connections from other computers
                        (the dashboard stays local)
  --import-players      Start the new world with the characters committed
                        to this repository instead of an empty one
  --no-service          Native: do not install systemd services
  --no-start            Install and configure, but do not start
  --open                Open the web client once it is running
  --skip-prerequisites  Do not install system packages
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
        --no-service) service="none" ;;
        --no-start) start_game=0 ;;
        --open) open_browser=1 ;;
        --skip-prerequisites) skip_prerequisites=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# A rerun keeps the mode it was installed with unless told otherwise.
if [ "$mode" = "preserve" ]; then
    mode="$(toc_mode)"
fi

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
    TARGET_USER="${SUDO_USER:-root}"
else
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo is required to install system packages (or rerun with --skip-prerequisites)." >&2
        exit 1
    fi
    SUDO="sudo"
    TARGET_USER="${USER:-$(id -un)}"
fi

package_manager() {
    local pm
    for pm in apt-get dnf pacman zypper; do
        if command -v "$pm" >/dev/null 2>&1; then
            echo "$pm"
            return 0
        fi
    done
    return 1
}

install_packages() {
    local pm="$1"; shift
    case "$pm" in
        apt-get)
            $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update
            $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
            ;;
        dnf)    $SUDO dnf install -y "$@" ;;
        pacman) $SUDO pacman -Sy --needed --noconfirm "$@" ;;
        zypper) $SUDO zypper --non-interactive install "$@" ;;
    esac
}

native_packages() {
    case "$1" in
        apt-get) echo "git ca-certificates openssl rsync build-essential libcrypt-dev zlib1g-dev python3 python3-venv" ;;
        dnf)     echo "git ca-certificates openssl rsync gcc make libxcrypt-devel zlib-devel python3" ;;
        pacman)  echo "git ca-certificates openssl rsync base-devel libxcrypt zlib python" ;;
        zypper)  echo "git ca-certificates openssl rsync gcc make libxcrypt-devel zlib-devel python3" ;;
    esac
}

# Docker Engine and Compose v2. The distribution's own packages where
# they include Compose v2, otherwise Docker's official install script,
# which covers Debian, Ubuntu, Raspberry Pi OS, Fedora, RHEL and CentOS.
install_docker() {
    local pm="$1"
    local candidate compose_package="" script

    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        echo "Docker and Compose v2 are already installed."
        return 0
    fi
    case "$pm" in
        apt-get)
            $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update
            for candidate in docker-compose-v2 docker-compose-plugin; do
                if apt-cache show "$candidate" >/dev/null 2>&1; then
                    compose_package="$candidate"
                    break
                fi
            done
            if [ -n "$compose_package" ]; then
                install_packages apt-get git ca-certificates openssl docker.io "$compose_package"
            fi
            ;;
        pacman) install_packages pacman git openssl docker docker-compose ;;
        zypper) install_packages zypper git openssl docker docker-compose ;;
    esac
    if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
        echo "Installing Docker Engine with Docker's official install script..."
        command -v curl >/dev/null 2>&1 || install_packages "$pm" curl
        script="$(mktemp -t toc-get-docker.XXXXXX)"
        curl -fsSL https://get.docker.com -o "$script"
        $SUDO sh "$script"
        rm -f "$script"
    fi
}

echo "Setting up Times of Chaos ($mode) for Linux..."
group_added=0

if [ "$skip_prerequisites" = "0" ]; then
    if ! pm="$(package_manager)"; then
        echo "No supported package manager (apt, dnf, pacman, zypper) was found." >&2
        if [ "$mode" = "native" ]; then
            echo "Install a C compiler, make, rsync, git, libxcrypt, zlib and Python 3.10+," >&2
        else
            echo "Install Git, Docker Engine and Docker Compose v2," >&2
        fi
        echo "then run: ./install.sh --skip-prerequisites" >&2
        exit 1
    fi

    if [ "$mode" = "native" ]; then
        # shellcheck disable=SC2046
        install_packages "$pm" $(native_packages "$pm")
    else
        install_docker "$pm"
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
fi

# Launched with sudo: return to the invoking account before creating
# private files or starting anything, so the data is theirs.
if [ "$(id -u)" -eq 0 ] && [ "$TARGET_USER" != "root" ]; then
    rerun_args=(--skip-prerequisites)
    for arg in "${original_args[@]}"; do
        [ "$arg" = "--skip-prerequisites" ] || rerun_args+=("$arg")
    done
    if command -v runuser >/dev/null 2>&1; then
        exec runuser -u "$TARGET_USER" -- "$REPO_ROOT/install.sh" "${rerun_args[@]}"
    fi
    exec sudo -u "$TARGET_USER" -H "$REPO_ROOT/install.sh" "${rerun_args[@]}"
fi

toc_configure_instance "$network" "$mode" "$import_players"

if [ "$mode" = "native" ]; then
    toc_native_require_tools
    toc_native_build
    toc_native_venv
    toc_native_stop >/dev/null 2>&1 || true
    toc_native_install_code
    if [ "$service" = "auto" ] && command -v systemctl >/dev/null 2>&1 \
        && [ "$(ps -p 1 -o comm= 2>/dev/null)" = "systemd" ]; then
        toc_native_install_units
    elif [ "$service" = "none" ] && [ "$(toc_native_service)" = "systemd" ]; then
        toc_native_remove_units
    fi
    if [ "$start_game" = "0" ]; then
        echo
        echo "Installation is complete. Run ./toc.sh start when you are ready."
        exit 0
    fi
    "$REPO_ROOT/toc.sh" start
else
    toc_require_docker
    if [ "$start_game" = "0" ]; then
        echo
        echo "Installation is complete. Run ./toc.sh start when you are ready."
        exit 0
    fi
    if toc_docker_ready; then
        "$REPO_ROOT/toc.sh" start
    elif [ "$group_added" = "1" ] && command -v sudo >/dev/null 2>&1; then
        echo "Starting with refreshed Docker group membership..."
        sudo -u "$TARGET_USER" -H bash -lc \
            "cd '$REPO_ROOT' && TOC_DOCKER_WAIT_SECONDS='$TOC_DOCKER_WAIT_SECONDS' ./toc.sh start"
    else
        toc_start_docker
        "$REPO_ROOT/toc.sh" start
    fi
fi

if [ "$open_browser" = "1" ]; then
    "$REPO_ROOT/toc.sh" play
fi

echo
echo "Next: create a character in the game, QUIT, then run"
echo "  ./toc.sh promote <name>"
echo "to make it your administrator. Future starts: ./toc.sh start"
if [ "$group_added" = "1" ]; then
    echo "Log out and back in once so plain 'docker' works without sudo."
fi
