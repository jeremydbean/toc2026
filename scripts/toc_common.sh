#!/usr/bin/env bash

# Shared installer and launcher helpers. Source this file; do not execute it.
#
# An installation is this checkout (the code), a private .env (settings
# and the dashboard token) and the state folder (everything the game
# writes: TOC_STATE, ./state by default). The game never writes into the
# checkout, so `toc.sh update` can always fast-forward it, and backing up
# or moving an installation is .env plus the state folder.
#
# TOC_MODE in .env is docker (the default) or native.

TOC_REPO_ROOT="${TOC_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TOC_ENV_FILE="$TOC_REPO_ROOT/.env"
TOC_DOCKER_WAIT_SECONDS="${TOC_DOCKER_WAIT_SECONDS:-300}"
TOC_GAME_WAIT_SECONDS="${TOC_GAME_WAIT_SECONDS:-180}"
TOC_DEFAULT_IMAGE="ghcr.io/jeremydbean/toc2026:latest"
# Where the game keeps state inside the checkout before 2026-10-21; the
# first run after that moves an existing installation's data out of them.
TOC_LEGACY_DIRS="player gods heroes corpse backups log"
TOC_STATE_DIRS="area player gods heroes corpse backups log"

toc_env_get() {
    local key="$1"
    local fallback="${2:-}"
    local value

    if [ ! -f "$TOC_ENV_FILE" ]; then
        printf '%s\n' "$fallback"
        return
    fi

    # One level of matching quotes comes off, as Docker Compose and
    # systemd's EnvironmentFile take it off: TOC_STATE="./data" kept its
    # quotes here and named another folder than the game's, so backup,
    # restore and purge worked on one folder while the game ran on
    # another (audit, 2026-10-22).
    value="$(awk -F= -v wanted="$key" '
        $1 == wanted {
            sub(/^[^=]*=/, "")
            gsub(/\r$/, "")
            if (length($0) >= 2) {
                first = substr($0, 1, 1)
                last = substr($0, length($0), 1)
                if (first == last && (first == "\"" || first == "\047")) {
                    $0 = substr($0, 2, length($0) - 2)
                }
            }
            print
            exit
        }
    ' "$TOC_ENV_FILE")"
    printf '%s\n' "${value:-$fallback}"
}

# A value as .env has to hold it to be read back the same by toc_env_get,
# Docker Compose, systemd and a shell sourcing the file (toc_native_start
# does): bare when it is only safe characters, otherwise in single
# quotes, which all four take literally. A single quote or a line break
# cannot be written that way and is refused.
toc_env_quote() {
    local value="$1"
    case "$value" in
        *"'"*|*$'\n'*|*$'\r'*)
            echo "A setting cannot hold a single quote or a line break: $value" >&2
            return 2
            ;;
        *[!A-Za-z0-9_./:@+,=-]*) printf "'%s'\n" "$value" ;;
        *) printf '%s\n' "$value" ;;
    esac
}

toc_set_env() {
    local key="$1"
    local value="$2"
    local temp

    value="$(toc_env_quote "$value")" || return 2
    temp="$(mktemp "${TOC_ENV_FILE}.tmp.XXXXXX")"
    # Through the environment, not -v: awk -v reads backslash escapes.
    TOC_ENV_REPLACEMENT="$value" awk -v wanted="$key" '
        BEGIN { found = 0; replacement = ENVIRON["TOC_ENV_REPLACEMENT"] }
        $0 ~ "^[[:space:]]*" wanted "=" {
            if (!found) {
                print wanted "=" replacement
                found = 1
            }
            next
        }
        { print }
        END {
            if (!found) {
                print wanted "=" replacement
            }
        }
    ' "$TOC_ENV_FILE" > "$temp"
    chmod 600 "$temp" 2>/dev/null || true
    mv "$temp" "$TOC_ENV_FILE"
}

toc_random_token() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
        return
    fi

    od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

toc_mode() {
    toc_env_get TOC_MODE docker
}

# The state folder as an absolute path. A relative TOC_STATE is relative
# to the checkout, which is how compose reads it too.
toc_state_dir() {
    local dir
    dir="$(toc_env_get TOC_STATE ./state)"
    case "$dir" in
        /*) printf '%s\n' "$dir" ;;
        *)  printf '%s\n' "$TOC_REPO_ROOT/${dir#./}" ;;
    esac
}

# Whether toc2026_game is a container from before the state folder: one
# whose world is not a bind mount. Such a container holds the only copy
# of its notes, reports and max-load counts.
toc_legacy_container() {
    [ "$(toc_mode)" = "docker" ] || return 1
    command -v docker >/dev/null 2>&1 || return 1
    toc_docker_ready || return 1
    docker container inspect toc2026_game >/dev/null 2>&1 || return 1
    ! docker container inspect -f '{{range .Mounts}}{{if eq .Destination "/app/area"}}{{.Type}}{{end}}{{end}}' \
        toc2026_game 2>/dev/null | grep -q bind
}

# Written in the state folder before an old installation's data is
# copied out of the checkout, and removed only when the copy is whole.
TOC_MIGRATING=".migrating"

toc_begin_migration() {
    mkdir -p "$1" && printf 'moving the data out of %s\n' "$TOC_REPO_ROOT" > "$1/$TOC_MIGRATING"
}

toc_mark_migrated() {
    printf 'migrated %s from the checkout\n' "$(date '+%Y-%m-%d %H:%M:%S')" \
        >> "$1/.migrated-from-checkout"
}

# Copy an existing installation's data out of the checkout into the state
# folder, once. Before this layout the game wrote into player/, gods/,
# heroes/ and log/, which git tracks, so the first character saved made
# `toc.sh update` refuse and a pull would have met the tracked copies.
# The checkout's directories are left as they are; `update` restores
# them to git's copy once the move is recorded.
toc_migrate_checkout_dirs() {
    local state="$1"
    local d moved=0

    for d in $TOC_LEGACY_DIRS; do
        if [ -d "$TOC_REPO_ROOT/$d" ] && [ -n "$(ls -A "$TOC_REPO_ROOT/$d" 2>/dev/null)" ]; then
            # A copy that fails says so whether or not set -e is on: the
            # caller keeps the .migrating marker and the next run resumes.
            mkdir -p "$state/$d" || return 1
            cp -Rp "$TOC_REPO_ROOT/$d/." "$state/$d/" || return 1
            moved=1
        fi
    done
    if [ "$moved" = 1 ]; then
        toc_mark_migrated "$state"
        echo "Moved this installation's data into $state."
        echo "Back up that folder and .env from now on; the checkout holds code only."
    fi
}

# The old container's world, copied out before anything replaces it; the
# new container then takes its place and name.
toc_migrate_legacy_container() {
    local state="$1"
    mkdir -p "$state/area"
    if docker cp toc2026_game:/app/area/. "$state/area/" >/dev/null 2>&1; then
        echo "Copied the world's runtime files out of the old container."
        docker rm toc2026_game >/dev/null 2>&1 || true
        toc_mark_migrated "$state"
    else
        echo "Warning: could not copy the world out of the old container;" >&2
        echo "it was left in place (docker cp toc2026_game:/app/area/. state/area/)." >&2
    fi
}

# Fill an empty new world with the characters committed to this
# repository (the public server's snapshot), only when asked for.
toc_import_repository_players() {
    local state="$1"
    local d

    if [ -n "$(ls -A "$state/player" 2>/dev/null)" ]; then
        echo "The state folder already has characters; nothing was imported."
        return 0
    fi
    for d in player gods heroes; do
        if [ -d "$TOC_REPO_ROOT/$d" ]; then
            mkdir -p "$state/$d"
            cp -Rp "$TOC_REPO_ROOT/$d/." "$state/$d/"
        fi
    done
    echo "Imported the repository's characters into $state."
}

toc_prepare_state() {
    local existed="$1"
    local import_players="${2:-0}"
    local state d legacy_container

    state="$(toc_state_dir)"
    legacy_container=0
    if toc_legacy_container; then
        legacy_container=1
        # Its players save into the checkout's player/ as it stops, so
        # stop it before anything is copied.
        docker stop -t 60 toc2026_game >/dev/null 2>&1 || true
    fi
    mkdir -p "$state"
    if [ "$existed" = 1 ] && [ ! -f "$state/.layout" ]; then
        toc_begin_migration "$state"
    fi
    # The marker, not .env, says a move is owed: .env gains TOC_MODE
    # before the copy, so a run that failed part way through it used to
    # look like a new installation the next time and the partial copy was
    # kept for good (audit, 2026-10-22). It is removed only once every
    # directory has been copied, and a rerun copies them all again.
    if [ -f "$state/$TOC_MIGRATING" ]; then
        if ! toc_migrate_checkout_dirs "$state"; then
            echo "Moving this installation's data into $state did not finish." >&2
            echo "Nothing in the checkout was changed; free some space and run the command again." >&2
            return 1
        fi
        rm -f "$state/$TOC_MIGRATING"
    fi
    [ -f "$state/.layout" ] || printf '1\n' > "$state/.layout"
    if [ "$legacy_container" = 1 ]; then
        toc_migrate_legacy_container "$state"
    fi
    for d in $TOC_STATE_DIRS; do
        mkdir -p "$state/$d"
    done
    if [ "$import_players" = 1 ]; then
        toc_import_repository_players "$state"
    fi
}

# toc_configure_instance <network> [mode] [import-players]
#   network: preserve | local | public
#   mode:    preserve | docker | native
toc_configure_instance() {
    local network="${1:-preserve}"
    local mode="${2:-preserve}"
    local import_players="${3:-0}"
    local existed=0

    # An installation from before the state folder: a .env the old
    # installers wrote, which never had TOC_MODE. (A .env copied from
    # .env.example has it, and is a new install.)
    if [ -f "$TOC_ENV_FILE" ] && [ -z "$(toc_env_get TOC_MODE)" ]; then
        existed=1
        # Recorded before .env gains TOC_MODE below, which is what made
        # this an old installation; the marker carries that to a rerun.
        if [ ! -f "$(toc_state_dir)/.layout" ]; then
            toc_begin_migration "$(toc_state_dir)"
        fi
    fi

    if [ ! -f "$TOC_ENV_FILE" ]; then
        umask 077
        cat > "$TOC_ENV_FILE" <<EOF
# Generated by the Times of Chaos installer. Do not commit this file.
# Rerunning the installer keeps every value here, the token included.
TOC_MODE=docker
TOC_STATE=./state
TOC_IMAGE=$TOC_DEFAULT_IMAGE
MUD_BIND=127.0.0.1
MUD_PORT=9000
WEB_ADMIN_BIND=127.0.0.1
WEB_ADMIN_PORT=9001
WEB_ADMIN_ENABLED=1
WEB_ADMIN_LOCAL_UNLOCK=1
TOC_UID=$(id -u)
TOC_GID=$(id -g)
WEB_ADMIN_TOKEN=$(toc_random_token)
EOF
        echo "Created private runtime configuration at $TOC_ENV_FILE."
    else
        [ -n "$(toc_env_get TOC_MODE)" ] || toc_set_env TOC_MODE docker
        [ -n "$(toc_env_get TOC_STATE)" ] || toc_set_env TOC_STATE ./state
        [ -n "$(toc_env_get TOC_IMAGE)" ] || toc_set_env TOC_IMAGE "$TOC_DEFAULT_IMAGE"
        [ -n "$(toc_env_get MUD_BIND)" ] || toc_set_env MUD_BIND 127.0.0.1
        [ -n "$(toc_env_get MUD_PORT)" ] || toc_set_env MUD_PORT 9000
        [ -n "$(toc_env_get WEB_ADMIN_BIND)" ] || toc_set_env WEB_ADMIN_BIND 127.0.0.1
        [ -n "$(toc_env_get WEB_ADMIN_PORT)" ] || toc_set_env WEB_ADMIN_PORT 9001
        [ -n "$(toc_env_get WEB_ADMIN_ENABLED)" ] || toc_set_env WEB_ADMIN_ENABLED 1
        [ -n "$(toc_env_get WEB_ADMIN_LOCAL_UNLOCK)" ] || toc_set_env WEB_ADMIN_LOCAL_UNLOCK 1
        [ -n "$(toc_env_get TOC_UID)" ] || toc_set_env TOC_UID "$(id -u)"
        [ -n "$(toc_env_get TOC_GID)" ] || toc_set_env TOC_GID "$(id -g)"
        if [ -z "$(toc_env_get WEB_ADMIN_TOKEN)" ]; then
            toc_set_env WEB_ADMIN_TOKEN "$(toc_random_token)"
            echo "Added a random dashboard token to the existing .env file."
        fi
    fi

    case "$network" in
        local)  toc_set_env MUD_BIND 127.0.0.1 ;;
        public) toc_set_env MUD_BIND 0.0.0.0 ;;
        preserve) ;;
        *) echo "Unknown network mode: $network" >&2; return 2 ;;
    esac
    case "$mode" in
        docker|native) toc_set_env TOC_MODE "$mode" ;;
        preserve) ;;
        *) echo "Unknown install mode: $mode" >&2; return 2 ;;
    esac

    chmod 600 "$TOC_ENV_FILE" 2>/dev/null || true
    toc_prepare_state "$existed" "$import_players"
}

# After a move out of the checkout, its copies of player/, gods/, heroes/
# and log/ are no longer live. Put git's versions back so a pull can
# fast-forward over them; the data itself is in the state folder.
toc_release_checkout_state() {
    local state
    state="$(toc_state_dir)"
    [ -f "$state/.migrated-from-checkout" ] || return 0
    [ -d "$TOC_REPO_ROOT/.git" ] || return 0
    local d restored=0
    for d in player gods heroes log; do
        # One at a time: a directory git does not track would fail the
        # whole checkout.
        git -C "$TOC_REPO_ROOT" ls-files --error-unmatch "$d" >/dev/null 2>&1 || continue
        if ! git -C "$TOC_REPO_ROOT" diff --quiet -- "$d" 2>/dev/null; then
            git -C "$TOC_REPO_ROOT" checkout -- "$d" && restored=1
        fi
    done
    if [ "$restored" = 1 ]; then
        echo "Restored the checkout's copies of player/, gods/, heroes/ and log/ (your data is in $state)."
    fi
}

# A path made absolute with every symbolic link and . or .. resolved, as
# far as it exists; the rest is appended as written.
toc_real_path() {
    local path="$1" rest="" resolved
    case "$path" in
        /*) ;;
        *) path="$PWD/$path" ;;
    esac
    while [ ! -d "$path" ]; do
        rest="/$(basename "$path")$rest"
        path="$(dirname "$path")"
    done
    resolved="$(cd "$path" && pwd -P)" || return 1
    resolved="${resolved%/}$rest"
    printf '%s\n' "${resolved:-/}"
}

# The state folder relative to the checkout when it lies inside it (not
# the checkout itself), else nothing.
toc_state_in_checkout() {
    local root state
    root="$(toc_real_path "$TOC_REPO_ROOT")" || return 0
    state="$(toc_real_path "$(toc_state_dir)")" || return 0
    case "$state" in
        "$root"/?*) printf '%s\n' "${state#"$root"/}" ;;
    esac
}

# Local changes to code, ignoring the directories an older install wrote
# game state into, and what this one writes in the checkout: the state
# folder wherever TOC_STATE puts it inside, the copy a restore sets
# aside beside it, a restore's unpacking folder and the backup's .env.
# Only ./state was left out, so after any restore -- or with TOC_STATE=
# ./data -- update refused and told the user to remove the copy of their
# characters (audit, 2026-10-22).
toc_code_changes() {
    local state
    local excludes=(':(exclude)player' ':(exclude)gods' ':(exclude)heroes'
        ':(exclude)log' ':(exclude)corpse' ':(exclude)backups'
        ':(exclude)state' ':(exclude)state.before-restore-*'
        ':(exclude).restore.*' ':(exclude).env.from-backup'
        ':(exclude).env.before-restore*')
    state="$(toc_state_in_checkout)"
    if [ -n "$state" ]; then
        excludes+=(":(exclude,literal)$state" ":(exclude)$state.before-restore-*")
    fi
    git -C "$TOC_REPO_ROOT" status --porcelain -- . "${excludes[@]}"
}

# Why `uninstall --purge` must not delete this state folder, or nothing.
# A TOC_STATE of ./ is the checkout, and .. or $HOME holds it: purge used
# to rm -rf whatever it named (audit, 2026-10-22).
toc_purge_refusal() {
    local raw state root home
    raw="$(toc_env_get TOC_STATE ./state)"
    if [ -z "$(printf '%s' "$raw" | tr -d '[:space:]')" ]; then
        echo "TOC_STATE is empty"
        return
    fi
    state="$(toc_real_path "$(toc_state_dir)")" || { echo "$raw cannot be resolved"; return; }
    root="$(toc_real_path "$TOC_REPO_ROOT")" || { echo "the checkout cannot be resolved"; return; }
    if [ "$state" = "/" ]; then
        echo "TOC_STATE ($raw) is the root of the file system"
    elif [ "$state" = "$root" ]; then
        echo "TOC_STATE ($raw) is this checkout"
    else
        case "$root/" in
            "$state"/*) echo "TOC_STATE ($raw) holds this checkout"; return ;;
        esac
        if [ -n "${HOME:-}" ]; then
            home="$(toc_real_path "$HOME")" || home=""
            if [ -n "$home" ] && [ "$state" = "$home" ]; then
                echo "TOC_STATE ($raw) is your home folder"
            fi
        fi
    fi
}

toc_require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Docker was not found. Run ./install.sh first." >&2
        return 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        echo "Docker Compose v2 was not found. Run ./install.sh first." >&2
        return 1
    fi
}

toc_docker_ready() {
    docker info >/dev/null 2>&1
}

toc_start_docker() {
    local elapsed=0

    if toc_docker_ready; then
        return 0
    fi

    echo "Starting Docker..."
    if docker desktop --help >/dev/null 2>&1; then
        docker desktop start --detach --timeout "$TOC_DOCKER_WAIT_SECONDS" \
            >/dev/null 2>&1 || true
    fi

    if ! toc_docker_ready; then
        case "$(uname -s)" in
            # First launch can require an interactive Docker agreement.
            Darwin) open -a Docker 2>/dev/null || true ;;
            Linux)
                if command -v systemctl >/dev/null 2>&1; then
                    sudo systemctl start docker 2>/dev/null || true
                fi
                ;;
        esac
    fi

    while ! toc_docker_ready; do
        if [ "$elapsed" -ge "$TOC_DOCKER_WAIT_SECONDS" ]; then
            echo "Docker did not become ready within ${TOC_DOCKER_WAIT_SECONDS} seconds." >&2
            echo "Open Docker Desktop, complete any first-run prompts, then rerun this command." >&2
            return 1
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
}

toc_compose() {
    docker compose --project-directory "$TOC_REPO_ROOT" "$@"
}

# Have an image to run: the published one unless TOC_BUILD=local (or a
# build is forced), else build this checkout. A pull that fails -- no
# network, a fork with no published image, an architecture nobody built
# -- falls back to building, which needs nothing but Docker.
toc_ensure_image() {
    local force_build="${1:-0}"

    if [ "$force_build" = 1 ] || [ "$(toc_env_get TOC_BUILD)" = "local" ]; then
        echo "Building the Times of Chaos image from this checkout..."
        toc_compose build game
        return
    fi
    echo "Fetching the prebuilt Times of Chaos image ($(toc_env_get TOC_IMAGE "$TOC_DEFAULT_IMAGE"))..."
    if toc_compose pull --quiet game 2>/dev/null; then
        return 0
    fi
    echo "No prebuilt image could be fetched; building from this checkout instead (a few minutes)."
    toc_compose build game
}

toc_wait_for_game() {
    local elapsed=0
    local container_id
    local health

    container_id="$(toc_compose ps -q game)"
    if [ -z "$container_id" ]; then
        echo "The ToC container was not created." >&2
        return 1
    fi

    printf 'Waiting for Times of Chaos'
    while [ "$elapsed" -lt "$TOC_GAME_WAIT_SECONDS" ]; do
        health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
        case "$health" in
            healthy)
                printf ' ready.\n'
                return 0
                ;;
            unhealthy|exited|dead)
                printf ' failed.\n' >&2
                toc_compose logs --tail 80 game >&2 || true
                return 1
                ;;
        esac
        printf '.'
        sleep 3
        elapsed=$((elapsed + 3))
    done

    printf ' timed out.\n' >&2
    toc_compose logs --tail 80 game >&2 || true
    return 1
}

# Whether something answers on host:port, with no tools beyond bash.
toc_port_open() {
    (exec 3<>"/dev/tcp/$1/$2") >/dev/null 2>&1
}

toc_print_endpoints() {
    local mud_bind
    local mud_port
    local web_port
    local launcher="./toc.sh"

    mud_bind="$(toc_env_get MUD_BIND 127.0.0.1)"
    mud_port="$(toc_env_get MUD_PORT 9000)"
    web_port="$(toc_env_get WEB_ADMIN_PORT 9001)"

    [ "$mud_bind" = "0.0.0.0" ] && mud_bind="every address of this computer"

    echo
    echo "Times of Chaos is running."
    echo "Play in a browser: http://127.0.0.1:$web_port/client"
    echo "MUD client:        localhost port $mud_port ($mud_bind)"
    echo "Administration:    http://127.0.0.1:$web_port"
    echo "Your data:         $(toc_state_dir)"
    echo "Commands:          $launcher play | admin | status | logs | stop | update | promote <name> | backup"
}

# Make a character the game's implementor, from its file. The character
# must be logged out: the game writes its own copy over the file on quit.
toc_promote_file() {
    local name="$1"
    local level="${2:-70}"
    local state file capitalized

    case "$name" in
        ''|*[!A-Za-z]*) echo "A character name is letters only." >&2; return 2 ;;
    esac
    case "$level" in
        ''|*[!0-9]*) echo "The level is a number." >&2; return 2 ;;
    esac
    if [ "$level" -lt 1 ] || [ "$level" -gt 70 ]; then
        echo "The level is 1 to 70 (70 is the implementor)." >&2
        return 2
    fi
    capitalized="$(printf '%s' "${name:0:1}" | tr '[:lower:]' '[:upper:]')$(printf '%s' "${name:1}" | tr '[:upper:]' '[:lower:]')"
    state="$(toc_state_dir)"
    file="$state/player/$capitalized"
    if [ ! -f "$file" ]; then
        echo "No saved character named $capitalized in $state/player." >&2
        echo "Create the character in the game first, then QUIT and run this again." >&2
        return 1
    fi
    if ! grep -q '^Levl ' "$file"; then
        echo "$file does not look like a character file." >&2
        return 1
    fi
    # The copy goes to backups/, not beside the character files the game
    # and the tools read.
    mkdir -p "$state/backups"
    cp -p "$file" "$state/backups/$capitalized.before-promote-$(date +%Y%m%d-%H%M%S)"
    awk -v level="$level" '
        !done && /^Levl / { print "Levl " level; done = 1; next }
        { print }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
    echo "$capitalized is now level $level. Log in to use it."
    [ "$level" -ge 60 ] && echo "Type WIZHELP in the game for the staff commands."
    return 0
}

# Append one line to the webadmin queue under the fcntl lock the game and
# the dashboard take: an unlocked append that lands while the game is
# reading the queue and truncating it is lost. Plain append without python3.
toc_queue_append() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import fcntl, sys
with open(sys.argv[1], "a", encoding="ascii") as f:
    fcntl.lockf(f.fileno(), fcntl.LOCK_EX)
    f.write(sys.argv[2] + "\n")' "$1" "$2" 2>/dev/null
    else
        printf '%s\n' "$2" >> "$1" 2>/dev/null
    fi
}

# A dated archive of .env and the state folder. The game is asked to save
# everyone first when it is running, so the archive holds this minute.
toc_backup_archive() {
    local out_dir="${1:-$TOC_REPO_ROOT/toc-backups}"
    local state stamp archive queue

    state="$(toc_state_dir)"
    stamp="$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$out_dir"
    archive="$out_dir/toc-backup-$stamp.tar.gz"
    queue="$state/area/webadmin.queue"
    if [ -f "$queue" ]; then
        toc_queue_append "$queue" "command|fsave" && sleep 3
    fi
    tar -czf "$archive" -C "$TOC_REPO_ROOT" .env \
        -C "$(dirname "$state")" --exclude "$(basename "$state")/venv" \
        --exclude "$(basename "$state")/run" "$(basename "$state")"
    chmod 600 "$archive" 2>/dev/null || true
    echo "$archive"
}
