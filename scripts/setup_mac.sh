#!/usr/bin/env bash
# Install ToC prerequisites on a current macOS host with Homebrew.
# Review wiki/hosting-guide.md and SECURITY.md before running a public server.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required by this helper." >&2
    echo "Install it from https://brew.sh, review its installer, then rerun." >&2
    exit 1
fi

if ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode Command Line Tools are required for native builds." >&2
    echo "Run: xcode-select --install" >&2
    exit 1
fi

brew install git cmake python

if ! command -v docker >/dev/null 2>&1; then
    brew install --cask docker
    echo "Docker Desktop was installed. Open it once and complete its setup."
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
echo "Start Docker Desktop, then run: docker compose up --build -d"
echo "Connect to localhost:9000 after startup."
echo "Before production, bind dashboard port 9001 to loopback as documented."
