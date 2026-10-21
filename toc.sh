#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOC_REPO_ROOT="$REPO_ROOT"
# shellcheck source=scripts/toc_common.sh
source "$REPO_ROOT/scripts/toc_common.sh"
# shellcheck source=scripts/toc_native.sh
source "$REPO_ROOT/scripts/toc_native.sh"

action="${1:-start}"
[ "$#" -gt 0 ] && shift

usage() {
    cat <<'EOF'
Usage: ./toc.sh [command]

  start              Start Times of Chaos (default)
  stop               Stop it; every player is saved and all data kept
  restart            Stop and start again
  status             Show whether the game and dashboard are answering
  logs               Follow the game's log
  play | open        Open the web game client
  admin              Open the administration dashboard
  update             Update to the newest version and restart
  build              Rebuild from this checkout and restart
  promote <name>     Make a character the implementor (log it out first)
  backup [folder]    Save .env and all game data to a dated archive
  restore <archive>  Put a backup back (the current data is set aside)
  doctor             Check the installation without changing it
  uninstall          Remove containers/services; --purge also deletes data
  help               Show this command list
EOF
}

mode="$(toc_mode)"

open_url() {
    case "$(uname -s)" in
        Darwin) open "$1" ;;
        *)
            if command -v xdg-open >/dev/null 2>&1; then
                xdg-open "$1" >/dev/null 2>&1 || echo "Open $1 in a browser."
            else
                echo "Open $1 in a browser."
            fi
            ;;
    esac
}

need_install() {
    if [ ! -f "$TOC_ENV_FILE" ]; then
        echo "This checkout is not installed yet. Run ./install.sh first." >&2
        exit 1
    fi
}

# Settle .env and the data folder. In Docker mode the engine has to be up
# first: an installation from before the data folder keeps its world in
# the old container, which is copied out before anything replaces it.
prepare() {
    need_install
    if [ "$mode" != "native" ]; then
        toc_require_docker
        toc_start_docker
    fi
    toc_configure_instance preserve
}

start_game() {
    local build="${1:-0}"

    prepare
    if [ "$mode" = "native" ]; then
        toc_native_require_tools
        if [ "$build" = "1" ] || [ ! -x "$(toc_state_dir)/merc" ]; then
            toc_native_build
            toc_native_stop
            toc_native_install_code
        fi
        toc_native_venv
        toc_native_start
        toc_native_wait_for_game
    else
        if [ "$build" = "1" ]; then
            toc_ensure_image 1
        elif ! docker image inspect "$(toc_env_get TOC_IMAGE "$TOC_DEFAULT_IMAGE")" >/dev/null 2>&1; then
            toc_ensure_image 0
        fi
        toc_compose up -d --no-build game
        toc_wait_for_game
    fi
    toc_print_endpoints
}

stop_game() {
    if [ "$mode" = "native" ]; then
        toc_native_stop
    else
        toc_require_docker
        toc_start_docker
        toc_compose stop game
    fi
    echo "Times of Chaos is stopped. Every player was saved and all data kept."
}

update_game() {
    prepare
    if [ -d "$REPO_ROOT/.git" ]; then
        if [ -n "$(toc_code_changes)" ]; then
            echo "Update stopped: this checkout has local code changes:" >&2
            toc_code_changes >&2
            echo "Commit, stash or remove them and rerun ./toc.sh update." >&2
            exit 1
        fi
        toc_release_checkout_state
        echo "Fetching the newest version..."
        git -C "$REPO_ROOT" pull --ff-only
        # Finish with the launcher just pulled, which may know more.
        exec "$REPO_ROOT/toc.sh" _finish-update
    fi
    echo "This copy is not a Git checkout; only the game image is updated."
    finish_update
}

finish_update() {
    if [ "$mode" = "native" ]; then
        # Build and check while the old game keeps running; the stop is
        # only as long as the copy.
        toc_native_require_tools
        toc_native_build
        toc_native_venv
        toc_native_stop
        toc_native_install_code
        toc_native_start
        toc_native_wait_for_game
    else
        toc_ensure_image 0
        toc_compose up -d --no-build game
        toc_wait_for_game
    fi
    toc_print_endpoints
}

doctor() {
    local failures=0
    local state
    state="$(toc_state_dir)"

    echo "Times of Chaos installation check"
    echo "Checkout: $REPO_ROOT"
    echo "Mode:     $mode"
    if [ -s "$TOC_ENV_FILE" ] && [ -n "$(toc_env_get WEB_ADMIN_TOKEN)" ]; then
        echo "[ok] Private configuration (.env)"
    else
        echo "[missing] .env with WEB_ADMIN_TOKEN"
        failures=$((failures + 1))
    fi
    if [ -d "$state/player" ]; then
        echo "[ok] Data folder: $state ($(find "$state/player" -maxdepth 1 -type f | wc -l | tr -d ' ') characters)"
    else
        echo "[missing] Data folder $state"
        failures=$((failures + 1))
    fi
    if [ "$mode" = "native" ]; then
        if toc_native_require_tools 2>/dev/null; then
            echo "[ok] Compiler, make, rsync and Python 3.10+"
        else
            toc_native_require_tools || true
            failures=$((failures + 1))
        fi
        if [ -x "$state/merc" ]; then
            echo "[ok] Game built"
        else
            echo "[missing] Game not built (./toc.sh build)"
            failures=$((failures + 1))
        fi
        if [ -x "$state/venv/bin/python" ]; then
            echo "[ok] Web client environment"
        else
            echo "[missing] Web client environment (./toc.sh build)"
            failures=$((failures + 1))
        fi
        echo "[info] Services: $(toc_native_service)"
    else
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
        if command -v docker >/dev/null 2>&1 && toc_docker_ready; then
            echo "[ok] Docker engine is running"
            toc_compose config --quiet || failures=$((failures + 1))
        else
            echo "[stopped] Docker engine"
            failures=$((failures + 1))
        fi
    fi
    if [ -d "$REPO_ROOT/.git" ] && [ -n "$(toc_code_changes)" ]; then
        echo "[warn] Local code changes will stop ./toc.sh update"
    fi
    if [ "$failures" -ne 0 ]; then
        echo "Doctor found $failures issue(s). Run ./install.sh to repair setup." >&2
        exit 1
    fi
    echo "Everything needed to run Times of Chaos is ready."
}

restore_backup() {
    local archive="${1:-}"
    local state aside work

    if [ -z "$archive" ] || [ ! -f "$archive" ]; then
        echo "Usage: ./toc.sh restore <toc-backup-....tar.gz>" >&2
        exit 2
    fi
    archive="$(cd "$(dirname "$archive")" && pwd)/$(basename "$archive")"
    state="$(toc_state_dir)"
    work="$(mktemp -d "$REPO_ROOT/.restore.XXXXXX")"
    tar -xzf "$archive" -C "$work"
    if [ ! -f "$work/.env" ] || [ -z "$(ls -d "$work"/*/player 2>/dev/null)" ]; then
        rm -rf "$work"
        echo "$archive is not a Times of Chaos backup (.env and a state folder)." >&2
        exit 1
    fi
    stop_game || true
    aside="$state.before-restore-$(date +%Y%m%d-%H%M%S)"
    [ -d "$state" ] && mv "$state" "$aside"
    mv "$(dirname "$(ls -d "$work"/*/player | head -1)")" "$state"
    cp -p "$TOC_ENV_FILE" "$TOC_ENV_FILE.before-restore" 2>/dev/null || true
    cp -p "$work/.env" "$TOC_ENV_FILE"
    rm -rf "$work"
    [ -d "${aside:-}" ] && echo "The data that was here is kept in $aside."
    mode="$(toc_mode)"
    start_game 0
}

uninstall() {
    local purge=0 yes=0 state answer
    for arg in "$@"; do
        case "$arg" in
            --purge) purge=1 ;;
            --yes|-y) yes=1 ;;
            *) echo "Unknown option: $arg" >&2; exit 2 ;;
        esac
    done
    state="$(toc_state_dir)"
    if [ "$mode" = "native" ]; then
        toc_native_stop || true
        [ "$(toc_native_service)" = "systemd" ] && toc_native_remove_units
    elif command -v docker >/dev/null 2>&1 && toc_docker_ready; then
        toc_compose down --rmi local --remove-orphans || true
        docker image rm "$(toc_env_get TOC_IMAGE "$TOC_DEFAULT_IMAGE")" >/dev/null 2>&1 || true
    fi
    if [ "$purge" = 1 ]; then
        if [ "$yes" != 1 ]; then
            printf 'Delete %s and .env -- every character and the world state? Type DELETE: ' "$state"
            read -r answer
            [ "$answer" = "DELETE" ] || { echo "Kept the data."; exit 1; }
        fi
        rm -rf "$state" "$TOC_ENV_FILE"
        echo "Times of Chaos is removed, data included. Delete this folder to finish."
    else
        echo "Times of Chaos is removed. Your data is still in $state and .env;"
        echo "run ./install.sh to use it again, or ./toc.sh uninstall --purge to delete it."
    fi
}

case "$action" in
    start)   start_game 0 ;;
    build)   start_game 1 ;;
    stop)    stop_game ;;
    restart)
        stop_game
        start_game 0
        ;;
    status)
        if [ "$mode" = "native" ]; then
            toc_native_status
        else
            toc_require_docker
            if ! toc_docker_ready; then
                echo "Docker is installed but is not running." >&2
                exit 1
            fi
            toc_compose ps
        fi
        toc_print_endpoints
        ;;
    logs)
        if [ "$mode" = "native" ]; then
            tail -n 200 -F "$(toc_state_dir)/log/game.log"
        else
            toc_require_docker
            toc_start_docker
            toc_compose logs -f --tail 200 game
        fi
        ;;
    doctor)  doctor ;;
    update)  update_game ;;
    _finish-update)
        prepare
        finish_update
        ;;
    open|play)
        open_url "http://127.0.0.1:$(toc_env_get WEB_ADMIN_PORT 9001)/client"
        ;;
    admin)
        open_url "http://127.0.0.1:$(toc_env_get WEB_ADMIN_PORT 9001)"
        ;;
    promote)
        need_install
        toc_promote_file "${1:-}" "${2:-70}"
        ;;
    backup)
        need_install
        archive="$(toc_backup_archive "${1:-}")"
        echo "Backed up to $archive"
        echo "It holds your dashboard token and every character: keep it private."
        ;;
    restore)
        need_install
        restore_backup "${1:-}"
        ;;
    uninstall) uninstall "$@" ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "Unknown command: $action" >&2
        usage >&2
        exit 2
        ;;
esac
