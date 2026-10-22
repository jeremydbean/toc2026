#!/usr/bin/env bash

# Native (no Docker) installation helpers. Source after toc_common.sh.
#
# The game runs from the state folder, not the checkout, exactly as the
# production host runs from /srv/toc/current: state/merc and state/area
# (brought up to date from the checkout's area/ by toc_sync_area.sh)
# beside state/player, state/log and the rest. The dashboard runs from
# the checkout with a virtualenv in state/venv.
#
# Services: systemd units (timesofchaos-game, timesofchaos-web) when the
# installer could create them -- they start at boot and restart a crashed
# dashboard -- otherwise background processes with PID files in state/run.

TOC_UNIT_GAME="timesofchaos-game.service"
TOC_UNIT_WEB="timesofchaos-web.service"

toc_native_service() {
    toc_env_get TOC_SERVICE none
}

toc_native_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

toc_native_require_tools() {
    local missing=""
    local tool
    for tool in make cc rsync; do
        command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
    done
    toc_native_python >/dev/null || missing="$missing python3(>=3.10)"
    if [ -n "$missing" ]; then
        echo "Missing for a native install:$missing" >&2
        echo "Run ./install.sh --native to install them." >&2
        return 1
    fi
}

# Compile in the checkout and load the new world in a scratch copy, so a
# change that does not build or boot is caught while the old game runs.
toc_native_build() {
    local state staging jobs
    state="$(toc_state_dir)"
    staging="$state/.staging"
    jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"

    echo "Compiling the game..."
    make -C "$TOC_REPO_ROOT" -j"$jobs" >"$state/log/build.log" 2>&1 || {
        tail -30 "$state/log/build.log" >&2
        echo "The build failed; the full log is $state/log/build.log." >&2
        return 1
    }

    echo "Checking that the world loads..."
    rm -rf "$staging"
    mkdir -p "$staging/log" "$staging/player" "$staging/gods" "$staging/heroes" \
             "$staging/corpse" "$staging/backups"
    sh "$TOC_REPO_ROOT/scripts/toc_sync_area.sh" "$TOC_REPO_ROOT/area" "$staging/area"
    if ! (cd "$staging/area" && "$TOC_REPO_ROOT/merc" --check-area) \
            >"$state/log/check-area.log" 2>&1; then
        tail -20 "$state/log/check-area.log" >&2
        echo "The world did not load; nothing was installed." >&2
        return 1
    fi
    rm -rf "$staging"
}

# Put the built game into the live tree. The game must be stopped.
toc_native_install_code() {
    local state
    state="$(toc_state_dir)"
    sh "$TOC_REPO_ROOT/scripts/toc_sync_area.sh" "$TOC_REPO_ROOT/area" "$state/area"
    cp "$TOC_REPO_ROOT/merc" "$state/merc.new"
    chmod 755 "$state/merc.new"
    mv -f "$state/merc.new" "$state/merc"
}

toc_native_venv() {
    local state python stamp want
    state="$(toc_state_dir)"
    python="$(toc_native_python)" || {
        echo "Python 3.10 or newer is required for the web client and dashboard." >&2
        return 1
    }
    want="$(cksum < "$TOC_REPO_ROOT/webadmin/requirements.txt")"
    stamp="$state/venv/.requirements"
    if [ -x "$state/venv/bin/python" ] && [ "$(cat "$stamp" 2>/dev/null)" = "$want" ]; then
        return 0
    fi
    echo "Installing the web client's Python packages..."
    [ -x "$state/venv/bin/python" ] || "$python" -m venv "$state/venv"
    "$state/venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    "$state/venv/bin/python" -m pip install --quiet -r "$TOC_REPO_ROOT/webadmin/requirements.txt"
    printf '%s\n' "$want" > "$stamp"
}

# The environment both processes run with: .env, plus the bind address
# the game understands.
toc_native_bind_address() {
    case "$(toc_env_get MUD_BIND 127.0.0.1)" in
        0.0.0.0|'') printf '\n' ;;
        *) toc_env_get MUD_BIND 127.0.0.1 ;;
    esac
}

toc_native_web_args() {
    local state
    state="$(toc_state_dir)"
    printf '%s\n' \
        --host "$(toc_env_get WEB_ADMIN_BIND 127.0.0.1)" \
        --port "$(toc_env_get WEB_ADMIN_PORT 9001)" \
        --mud-host 127.0.0.1 \
        --mud-port "$(toc_env_get MUD_PORT 9000)" \
        --queue "$state/area/webadmin.queue" \
        --log-file "$state/log/toc.log" \
        --event-log-file "$state/log/webadmin-events.tsv" \
        --area-path "$state/area" \
        --backup-path "$state/backups" \
        --player-path "$state/player"
}

# systemd units, written for this checkout and user. Needs sudo once.
toc_native_install_units() {
    local state user group sudo bind web_cmd
    state="$(toc_state_dir)"
    user="$(id -un)"
    group="$(id -gn)"
    sudo=""
    [ "$(id -u)" -eq 0 ] || sudo="sudo"
    bind="$(toc_native_bind_address)"
    web_cmd="$state/venv/bin/python -m webadmin.server $(toc_native_web_args | tr '\n' ' ')"

    $sudo tee "/etc/systemd/system/$TOC_UNIT_GAME" >/dev/null <<EOF
# Written by the Times of Chaos installer ($TOC_REPO_ROOT).
[Unit]
Description=Times of Chaos MUD
After=network.target

[Service]
Type=simple
User=$user
Group=$group
WorkingDirectory=$state/area
Environment=TOC_BIND_ADDRESS=$bind
ExecStart=$TOC_REPO_ROOT/scripts/toc_run_game.sh $state $(toc_env_get MUD_PORT 9000)
# The game saves every player on SIGTERM before it exits.
KillMode=mixed
TimeoutStopSec=60
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    $sudo tee "/etc/systemd/system/$TOC_UNIT_WEB" >/dev/null <<EOF
# Written by the Times of Chaos installer ($TOC_REPO_ROOT).
[Unit]
Description=Times of Chaos web client and dashboard
After=network.target $TOC_UNIT_GAME

[Service]
Type=simple
User=$user
Group=$group
WorkingDirectory=$TOC_REPO_ROOT
EnvironmentFile=$TOC_ENV_FILE
Environment=PYTHONUNBUFFERED=1
ExecStart=$web_cmd
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    $sudo systemctl daemon-reload
    $sudo systemctl enable "$TOC_UNIT_GAME" "$TOC_UNIT_WEB" >/dev/null 2>&1
    toc_set_env TOC_SERVICE systemd
    echo "Installed $TOC_UNIT_GAME and $TOC_UNIT_WEB; they start at boot."
}

toc_native_remove_units() {
    local sudo=""
    [ "$(id -u)" -eq 0 ] || sudo="sudo"
    $sudo systemctl disable --now "$TOC_UNIT_GAME" "$TOC_UNIT_WEB" >/dev/null 2>&1 || true
    $sudo rm -f "/etc/systemd/system/$TOC_UNIT_GAME" "/etc/systemd/system/$TOC_UNIT_WEB"
    $sudo systemctl daemon-reload 2>/dev/null || true
    toc_set_env TOC_SERVICE none
}

# A process's command line, arguments space-separated, or nothing.
toc_native_pid_command() {
    if [ -r "/proc/$1/cmdline" ]; then
        tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null
    else
        ps -p "$1" -o command= 2>/dev/null
    fi
}

toc_native_pid_parent() {
    ps -p "$1" -o ppid= 2>/dev/null | tr -d ' '
}

# Whether the PID in a run/<name>.pid file is still this installation's
# game or dashboard. kill -0 alone said yes to whatever process had been
# given that number since -- after a reboot or a crash, usually -- so stop
# sent it SIGTERM and then SIGKILL, and start never launched the game
# (audit, 2026-10-22). The command line has to be the game's runner or
# the dashboard; a process this shell has just started counts as well,
# because between its fork and its exec it still reads as this script.
toc_native_pid_alive() {
    local file="$1" want="${2:-}" pid command
    [ -f "$file" ] || return 1
    pid="$(cat "$file" 2>/dev/null)"
    case "$pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    kill -0 "$pid" 2>/dev/null || return 1
    if [ -z "$want" ]; then
        case "$(basename "$file")" in
            game.pid) want="toc_run_game.sh" ;;
            web.pid)  want="webadmin.server" ;;
            *) return 1 ;;
        esac
    fi
    command="$(toc_native_pid_command "$pid")"
    case "$command" in
        *"$want"*) return 0 ;;
    esac
    [ "$(toc_native_pid_parent "$pid")" = "$$" ]
}

toc_native_start() {
    local state run bind port sudo=""
    state="$(toc_state_dir)"
    run="$state/run"
    port="$(toc_env_get MUD_PORT 9000)"
    [ "$(id -u)" -eq 0 ] || sudo="sudo"

    if [ ! -x "$state/merc" ]; then
        echo "The game is not built yet; run ./toc.sh build." >&2
        return 1
    fi
    if [ "$(toc_native_service)" = "systemd" ]; then
        $sudo systemctl start "$TOC_UNIT_GAME" "$TOC_UNIT_WEB"
        return 0
    fi

    mkdir -p "$run"
    bind="$(toc_native_bind_address)"
    if ! toc_native_pid_alive "$run/game.pid"; then
        TOC_BIND_ADDRESS="$bind" nohup "$TOC_REPO_ROOT/scripts/toc_run_game.sh" \
            "$state" "$port" >>"$state/log/game.log" 2>&1 < /dev/null &
        echo $! > "$run/game.pid"
    fi
    if [ "$(toc_env_get WEB_ADMIN_ENABLED 1)" != "0" ] && ! toc_native_pid_alive "$run/web.pid"; then
        # The dashboard reads its token and options from the environment.
        (
            set -a
            # shellcheck disable=SC1090
            . "$TOC_ENV_FILE"
            set +a
            cd "$TOC_REPO_ROOT"
            # One argument a line, so a path with spaces stays one argument
            # (bash 3.2 on macOS has no mapfile).
            args=()
            while IFS= read -r line; do args+=("$line"); done < <(toc_native_web_args)
            exec nohup "$state/venv/bin/python" -m webadmin.server \
                "${args[@]}" >>"$state/log/webadmin.log" 2>&1 < /dev/null
        ) &
        echo $! > "$run/web.pid"
    fi
}

toc_native_stop() {
    local state run pid waited sudo=""
    state="$(toc_state_dir)"
    run="$state/run"
    [ "$(id -u)" -eq 0 ] || sudo="sudo"

    if [ "$(toc_native_service)" = "systemd" ]; then
        # Its status is the answer: a restore must not go on after a stop
        # that failed.
        $sudo systemctl stop "$TOC_UNIT_WEB" "$TOC_UNIT_GAME"
        return
    fi
    for name in web game; do
        if toc_native_pid_alive "$run/$name.pid"; then
            pid="$(cat "$run/$name.pid")"
            kill -TERM "$pid" 2>/dev/null || true
            waited=0
            # The game saves every player before it exits.
            while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 60 ]; do
                sleep 1
                waited=$((waited + 1))
            done
            kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
        fi
        rm -f "$run/$name.pid"
    done
}

toc_native_wait_for_game() {
    local port elapsed=0
    port="$(toc_env_get MUD_PORT 9000)"
    printf 'Waiting for Times of Chaos'
    while [ "$elapsed" -lt "$TOC_GAME_WAIT_SECONDS" ]; do
        if toc_port_open 127.0.0.1 "$port"; then
            printf ' ready.\n'
            return 0
        fi
        if [ "$(toc_native_service)" != "systemd" ] \
            && ! toc_native_pid_alive "$(toc_state_dir)/run/game.pid"; then
            printf ' it stopped.\n' >&2
            break
        fi
        printf '.'
        sleep 2
        elapsed=$((elapsed + 2))
    done
    [ "$elapsed" -lt "$TOC_GAME_WAIT_SECONDS" ] || printf ' timed out.\n' >&2
    tail -40 "$(toc_state_dir)/log/game.log" >&2 2>/dev/null || true
    return 1
}

toc_native_status() {
    local state port web_port ok=0
    state="$(toc_state_dir)"
    port="$(toc_env_get MUD_PORT 9000)"
    web_port="$(toc_env_get WEB_ADMIN_PORT 9001)"
    if [ "$(toc_native_service)" = "systemd" ]; then
        systemctl --no-pager --lines=0 status "$TOC_UNIT_GAME" "$TOC_UNIT_WEB" || true
    fi
    if toc_port_open 127.0.0.1 "$port"; then
        echo "Game:      answering on port $port"
    else
        echo "Game:      not answering on port $port"
        ok=1
    fi
    if toc_port_open 127.0.0.1 "$web_port"; then
        echo "Dashboard: answering on port $web_port"
    else
        echo "Dashboard: not answering on port $web_port"
    fi
    echo "Data:      $state"
    return "$ok"
}
