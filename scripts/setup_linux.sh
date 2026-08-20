#!/usr/bin/env bash
# Install ToC prerequisites on a current Debian/Ubuntu host.
# Review wiki/hosting-guide.md and SECURITY.md before running a public server.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This helper supports Debian/Ubuntu apt hosts only." >&2
    echo "Use wiki/hosting-guide.md for Fedora, macOS, Docker, and other paths." >&2
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

echo "Installing Git, native build tools, Python, OpenSSL, and Docker..."
$SUDO apt-get update

COMPOSE_PACKAGE=""
for candidate in docker-compose-v2 docker-compose-plugin; do
    if apt-cache show "$candidate" >/dev/null 2>&1; then
        COMPOSE_PACKAGE="$candidate"
        break
    fi
done

PACKAGES=(
    git
    build-essential
    libcrypt-dev
    python3
    python3-venv
    openssl
    docker.io
)

if [ -n "$COMPOSE_PACKAGE" ]; then
    PACKAGES+=("$COMPOSE_PACKAGE")
fi

$SUDO apt-get install -y "${PACKAGES[@]}"

if command -v systemctl >/dev/null 2>&1 && [ "$(ps -p 1 -o comm= 2>/dev/null)" = "systemd" ]; then
    $SUDO systemctl enable --now docker
fi

if [ "$TARGET_USER" != "root" ] && getent group docker >/dev/null 2>&1; then
    if ! id -nG "$TARGET_USER" | grep -qw docker; then
        $SUDO usermod -aG docker "$TARGET_USER"
        echo "Added $TARGET_USER to the docker group; log out and back in before using Docker."
    fi
fi

cd "$REPO_ROOT"
mkdir -p player log backups gods heroes

if [ ! -f .env ]; then
    umask 077
    printf 'WEB_ADMIN_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
    echo "Created a private .env with a random WEB_ADMIN_TOKEN."
else
    echo "Kept the existing .env unchanged."
fi

echo
echo "Prerequisite setup complete."
if docker compose version >/dev/null 2>&1; then
    echo "Next: docker compose up --build -d"
else
    echo "Docker Compose v2 was not found in this apt repository."
    echo "Install the current Docker Compose plugin, then run: docker compose up --build -d"
fi
echo "Connect to localhost:9000 after startup."
echo "Before production, bind dashboard port 9001 to loopback as documented."
