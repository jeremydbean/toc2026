#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOC_REPO_ROOT="$REPO_ROOT"
# shellcheck source=scripts/toc_common.sh
source "$REPO_ROOT/scripts/toc_common.sh"

action="${1:-start}"
[ "$#" -gt 0 ] && shift

usage() {
    cat <<'EOF'
Usage: ./toc.sh [command]

  start      Start an existing installation (default)
  build      Build/rebuild the image and start ToC
  stop       Stop ToC while preserving all data
  restart    Restart the running container
  status     Show container health and connection addresses
  logs       Follow the latest game and dashboard logs
  doctor     Check the local installation without changing it
  update     Fast-forward from GitHub, rebuild, and restart
  open       Open the local web dashboard
  help       Show this command list
EOF
}

compose() {
    docker compose --project-directory "$REPO_ROOT" "$@"
}

start_game() {
    local build="${1:-0}"

    toc_configure_instance preserve
    toc_require_docker
    toc_start_docker
    if [ "$build" = "1" ]; then
        compose up --build -d
    else
        compose up -d
    fi
    toc_wait_for_game
    toc_print_endpoints
}

case "$action" in
    start)
        start_game 0
        ;;
    build)
        start_game 1
        ;;
    stop)
        toc_require_docker
        toc_start_docker
        compose stop
        echo "Times of Chaos is stopped. Runtime data was preserved."
        ;;
    restart)
        toc_require_docker
        toc_start_docker
        compose restart game
        toc_wait_for_game
        toc_print_endpoints
        ;;
    status)
        toc_require_docker
        if ! toc_docker_ready; then
            echo "Docker is installed but is not running." >&2
            exit 1
        fi
        compose ps
        toc_print_endpoints
        ;;
    logs)
        toc_require_docker
        toc_start_docker
        compose logs -f --tail 200 game
        ;;
    doctor)
        failures=0
        echo "Times of Chaos installation check"
        echo "Repository: $REPO_ROOT"
        if command -v docker >/dev/null 2>&1; then
            echo "[ok] Docker CLI: $(docker --version)"
        else
            echo "[missing] Docker CLI"
            failures=$((failures + 1))
        fi
        if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
            echo "[ok] $(docker compose version)"
        else
            echo "[missing] Docker Compose v2"
            failures=$((failures + 1))
        fi
        if [ -s "$TOC_ENV_FILE" ] && [ -n "$(toc_env_get WEB_ADMIN_TOKEN)" ]; then
            echo "[ok] Private runtime configuration"
        else
            echo "[missing] .env with WEB_ADMIN_TOKEN"
            failures=$((failures + 1))
        fi
        if command -v docker >/dev/null 2>&1 && toc_docker_ready; then
            echo "[ok] Docker engine is running"
            compose config --quiet || failures=$((failures + 1))
        else
            echo "[stopped] Docker engine"
            failures=$((failures + 1))
        fi
        if [ "$failures" -ne 0 ]; then
            echo "Doctor found $failures issue(s). Run ./install.sh to repair setup." >&2
            exit 1
        fi
        echo "Everything needed to launch ToC is ready."
        ;;
    update)
        if [ ! -d "$REPO_ROOT/.git" ]; then
            echo "This copy is not a Git checkout; download a current release before updating." >&2
            exit 1
        fi
        if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
            echo "Update stopped because the repository has local changes." >&2
            echo "Commit, stash, or remove those changes and rerun ./toc.sh update." >&2
            exit 1
        fi
        git -C "$REPO_ROOT" pull --ff-only
        start_game 1
        ;;
    open)
        web_port="$(toc_env_get WEB_ADMIN_PORT 9001)"
        case "$(uname -s)" in
            Darwin) open "http://127.0.0.1:$web_port" ;;
            Linux)
                if command -v xdg-open >/dev/null 2>&1; then
                    xdg-open "http://127.0.0.1:$web_port" >/dev/null 2>&1
                else
                    echo "Open http://127.0.0.1:$web_port in a browser."
                fi
                ;;
        esac
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "Unknown command: $action" >&2
        usage >&2
        exit 2
        ;;
esac
