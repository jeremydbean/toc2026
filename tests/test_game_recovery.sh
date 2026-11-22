#!/bin/bash
# Exercise deploy/windows-vm/toc-game-recovery without a real systemd, a real
# repository, or a real game.
#
# The recovery script only earns its place in the failure paths, and those are
# exactly the paths nobody runs by hand. systemctl, git, make and the port
# probe are stubbed so every stage can be driven deterministically: healthy,
# recovered by restart, recovered by rebuild, and rebuild-fails-so-roll-back.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/deploy/windows-vm/toc-game-recovery"

failures=0
# The stand-in binaries are scripts, so identity lives in a comment line.
binary_id() {
    grep -oE '(OLD|NEW)-BINARY' "$WORK/live/merc" 2>/dev/null | head -1
}

count_calls() {
    [ -f "$WORK/calls" ] || { echo 0; return; }
    grep -c "$1" "$WORK/calls" 2>/dev/null | head -1
}

check() {
    if [ "$2" = "$3" ]; then
        printf '  OK   %s\n' "$1"
    else
        printf '  FAIL %s: got %q want %q\n' "$1" "$2" "$3"
        failures=$((failures + 1))
    fi
}

# Each scenario gets a throwaway world: stub bin/, live tree, state, backups.
setup() {
    WORK="$(mktemp -d)"
    mkdir -p "$WORK/bin" "$WORK/live/area" "$WORK/state" "$WORK/backups" "$WORK/etc"
    # Runnable stand-ins: the script executes merc --check-area, so these must
    # actually run, while still carrying a greppable identity.
    printf '#!/bin/bash\n# OLD-BINARY\nexit 0\n' > "$WORK/live/merc"
    chmod +x "$WORK/live/merc"
    # What toc-deploy recorded as live: the only commit a rebuild may use.
    mkdir -p "$WORK/live/log"
    echo "1abe0c0de 2026-10-25T00:00:00Z" > "$WORK/live/log/deployed-commit"

    # Stubs. Behaviour is driven by files the test writes into $WORK.
    cat > "$WORK/bin/systemctl" <<'STUB'
#!/bin/bash
case "$1" in
  is-active) [ -f "$WORK/up" ] && exit 0 || exit 1 ;;
  start) [ -f "$WORK/start-works" ] && touch "$WORK/up"; echo start >> "$WORK/calls" ;;
  reset-failed) echo reset >> "$WORK/calls" ;;
esac
exit 0
STUB

    # Stands in for the /dev/tcp probe: up iff the service is "running".
    cat > "$WORK/bin/timeout" <<'STUB'
#!/bin/bash
# timeout <secs> <cmd...>; only the port probe and long commands use it.
shift
if [ "${1:-}" = "bash" ]; then
  [ -f "$WORK/up" ] && exit 0 || exit 1
fi
exec "$@"
STUB

    cat > "$WORK/bin/git" <<'STUB'
#!/bin/bash
for a in "$@"; do
  case "$a" in
    clone) mkdir -p "$TOC_BUILD_ROOT/area"; touch "$TOC_BUILD_ROOT/.git"; echo clone >> "$WORK/calls"; exit 0 ;;
    fetch) echo fetch >> "$WORK/calls"; exit 0 ;;
    rev-parse) echo "newcommit"; exit 0 ;;
    reset) echo "reset $*" >> "$WORK/calls"; exit 0 ;;
    clean) exit 0 ;;
  esac
done
exit 0
STUB

    cat > "$WORK/bin/make" <<'STUB'
#!/bin/bash
[ -f "$WORK/build-fails" ] && exit 1
# Emit a "new" binary, and a merc the validation stub can run.
mkdir -p "$TOC_BUILD_ROOT/area"
printf '#!/bin/bash\n# NEW-BINARY\nexit 0\n' > "$TOC_BUILD_ROOT/merc"
chmod +x "$TOC_BUILD_ROOT/merc"
echo make >> "$WORK/calls"
exit 0
STUB

    # The validation step runs ../merc --check-area from the build area dir.
    cat > "$WORK/bin/nproc" <<'STUB'
#!/bin/bash
echo 1
STUB

    chmod +x "$WORK/bin/"*
    export WORK
    export TOC_DEPLOY_LOCK="$WORK/deploy.lock"
    # The disk janitor reads the real disk; only its own scenarios let it act.
    export TOC_DISK_LOW_MB="${TOC_DISK_LOW_MB:-0}" TOC_DISK_LOW_INODE_PCT=0
}

teardown() { rm -rf "$WORK"; }

run_recovery() {
    PATH="$WORK/bin:$PATH" \
    WORK="$WORK" \
    TOC_SERVICE="test-game.service" \
    TOC_LIVE_ROOT="$WORK/live" \
    TOC_BUILD_ROOT="$WORK/build" \
    TOC_STATE_DIR="$WORK/state" \
    TOC_BACKUP_DIR="$WORK/backups" \
    TOC_RECOVERY_LOCK="$WORK/lock" \
    TOC_START_GRACE_SEC=0 \
    TOC_MAX_PLAIN_ATTEMPTS=1 \
    TOC_REBUILD_COOLDOWN_SEC=0 \
    TOC_MIN_FREE_MB=0 \
    bash "$SCRIPT" >"$WORK/out" 2>&1
    echo $?
}

echo "recovery script scenarios:"

# 1. Already healthy: do nothing at all.
setup; touch "$WORK/up"
rc=$(run_recovery)
check "healthy game is left alone" "$rc" "0"
check "healthy game triggers no restart" "$(count_calls start)" "0"
teardown

# 2. Down, but a plain restart fixes it: must not rebuild.
setup; touch "$WORK/start-works"
rc=$(run_recovery)
check "restart recovers the game" "$rc" "0"
check "restart path does not rebuild" "$(count_calls make)" "0"
teardown

# 3. Restart never works, rebuild produces a good binary.
setup
cat > "$WORK/bin/systemctl" <<'STUB'
#!/bin/bash
case "$1" in
  is-active) [ -f "$WORK/up" ] && exit 0 || exit 1 ;;
  start) echo start >> "$WORK/calls"
         # Only a freshly installed binary brings it up.
         grep -q NEW-BINARY "$TOC_LIVE_ROOT/merc" 2>/dev/null && touch "$WORK/up" ;;
  reset-failed) echo reset >> "$WORK/calls" ;;
esac
exit 0
STUB
chmod +x "$WORK/bin/systemctl"
rc=$(run_recovery)
check "rebuild recovers the game" "$rc" "0"
check "rebuild installed the new binary" "$(binary_id)" "NEW-BINARY"
check "previous binary was archived" "$(ls "$WORK/backups" 2>/dev/null | grep -c merc-rollback | head -1)" "1"
check "rebuild is of the live commit, never the tip of main" \
    "$(grep -c 'reset --hard 1abe0c0de' "$WORK/calls")" "1"
check "rebuild never checks out origin/main" "$(grep -c 'origin/' "$WORK/calls")" "0"
teardown

# 3b. With no record of what is live there is nothing tested to build.
setup
rm "$WORK/live/log/deployed-commit"
rc=$(run_recovery)
check "no live record: no rebuild" "$(count_calls make)" "0"
check "no live record: reported as needing a human" "$rc" "1"
check "no live record: the old binary stays" "$(binary_id)" "OLD-BINARY"
teardown

# 4. Build itself fails: keep the working binary, change nothing.
setup; touch "$WORK/build-fails"
rc=$(run_recovery)
check "failed build reports failure" "$rc" "1"
check "failed build keeps the old binary" "$(binary_id)" "OLD-BINARY"
teardown

# 5. New binary builds but still will not run: roll back.
setup
cat > "$WORK/bin/systemctl" <<'STUB'
#!/bin/bash
case "$1" in
  is-active) [ -f "$WORK/up" ] && exit 0 || exit 1 ;;
  start) echo start >> "$WORK/calls"
         grep -q OLD-BINARY "$TOC_LIVE_ROOT/merc" 2>/dev/null && [ -f "$WORK/rolled" ] && touch "$WORK/up"
         grep -q OLD-BINARY "$TOC_LIVE_ROOT/merc" 2>/dev/null && touch "$WORK/rolled" ;;
  reset-failed) echo reset >> "$WORK/calls" ;;
esac
exit 0
STUB
chmod +x "$WORK/bin/systemctl"
rc=$(run_recovery)
check "bad new binary is rolled back" "$(binary_id)" "OLD-BINARY"
teardown

# 6. Maintenance marker: a deliberately stopped game is not a failure.
setup
touch "$WORK/etc/maintenance"
rc=$(PATH="$WORK/bin:$PATH" WORK="$WORK" TOC_SERVICE=test-game.service \
     TOC_LIVE_ROOT="$WORK/live" TOC_BUILD_ROOT="$WORK/build" \
     TOC_STATE_DIR="$WORK/state" TOC_BACKUP_DIR="$WORK/backups" \
     TOC_RECOVERY_LOCK="$WORK/lock" TOC_START_GRACE_SEC=0 \
     TOC_MAINTENANCE_MARKER="$WORK/etc/maintenance" \
     bash "$SCRIPT" >"$WORK/out" 2>&1; echo $?)
check "maintenance marker is respected" "$rc" "0"
check "maintenance marker suppresses restarts" "$(count_calls start)" "0"
teardown

# 7. An intentional in-game shutdown is also not a failure.
setup
touch "$WORK/live/area/shutdown.txt"
rc=$(run_recovery)
check "in-game shutdown is respected" "$rc" "0"
check "in-game shutdown suppresses restarts" "$(count_calls start)" "0"
teardown

# 8. No such service account. A CI runner has no toc user and is not root, so
# scenario 3 quietly exercises a different install path there than on a
# developer box that does. Force the missing-account case everywhere: the
# binary still has to land, ownership or not.
setup
cat > "$WORK/bin/systemctl" <<'STUB'
#!/bin/bash
case "$1" in
  is-active) [ -f "$WORK/up" ] && exit 0 || exit 1 ;;
  start) echo start >> "$WORK/calls"
         grep -q NEW-BINARY "$TOC_LIVE_ROOT/merc" 2>/dev/null && touch "$WORK/up" ;;
  reset-failed) echo reset >> "$WORK/calls" ;;
esac
exit 0
STUB
chmod +x "$WORK/bin/systemctl"
rc=$(PATH="$WORK/bin:$PATH" WORK="$WORK" TOC_SERVICE=test-game.service      TOC_LIVE_ROOT="$WORK/live" TOC_BUILD_ROOT="$WORK/build"      TOC_STATE_DIR="$WORK/state" TOC_BACKUP_DIR="$WORK/backups"      TOC_RECOVERY_LOCK="$WORK/lock" TOC_START_GRACE_SEC=0      TOC_MAX_PLAIN_ATTEMPTS=1 TOC_REBUILD_COOLDOWN_SEC=0 TOC_MIN_FREE_MB=0      TOC_OWNER=toc-no-such-account TOC_GROUP=toc-no-such-account      bash "$SCRIPT" >"$WORK/out" 2>&1; echo $?)
check "missing service account still recovers" "$rc" "0"
check "missing service account still installs" "$(binary_id)" "NEW-BINARY"
teardown

# 9. A deploy holds its lock: the game it stopped is not a failure, and
# the build tree it is using is not to be reset under it.
setup
exec 7>"$TOC_DEPLOY_LOCK"
flock 7
rc=$(run_recovery)
exec 7>&-
check "a running deploy is left alone" "$rc" "0"
check "a running deploy gets no restart" "$(count_calls start)" "0"
check "a running deploy's tree is not fetched" "$(count_calls fetch)" "0"
teardown

# 10-14. The services beside the game (keep_services_up). The game is
# healthy in all of them, so only the supporting units are acted on.
watchdog_setup() {
    setup; touch "$WORK/up"
    cat > "$WORK/bin/systemctl" <<'STUB'
#!/bin/bash
unit="${2:-}"
case "$1" in
  is-enabled) [ -f "$WORK/enabled-$unit" ] && { echo enabled; exit 0; }
              echo disabled; exit 1 ;;
  is-active)
    [ "${2:-}" = --quiet ] && unit="$3"
    if [ "$unit" = test-game.service ]; then [ -f "$WORK/up" ] && exit 0 || exit 1; fi
    if [ -f "$WORK/active-$unit" ]; then [ "${2:-}" = --quiet ] || echo active; exit 0; fi
    [ "${2:-}" = --quiet ] || echo inactive; exit 3 ;;
  start) echo "unit-start $unit" >> "$WORK/calls"; touch "$WORK/active-$unit" ;;
  restart) echo "unit-restart $unit" >> "$WORK/calls" ;;
  reset-failed) echo "reset $unit" >> "$WORK/calls" ;;
esac
exit 0
STUB
    cat > "$WORK/bin/curl" <<'STUB'
#!/bin/bash
echo curl >> "$WORK/calls"
[ -f "$WORK/web-answers" ]
STUB
    chmod +x "$WORK/bin/systemctl" "$WORK/bin/curl"
    export TOC_KEEP_UNITS="t-sync.timer t-deploy.timer t-off.timer"
    export TOC_WEB_SERVICE=t-web.service
}

# 10. An enabled timer that stopped is started; a disabled one is not.
watchdog_setup
touch "$WORK/enabled-t-sync.timer" "$WORK/active-t-deploy.timer" \
      "$WORK/enabled-t-deploy.timer"
rc=$(run_recovery)
check "watchdog run exits cleanly" "$rc" "0"
check "a stopped enabled timer is started" "$(count_calls 'unit-start t-sync.timer')" "1"
check "a running timer is left alone" "$(count_calls 'unit-start t-deploy.timer')" "0"
check "a disabled timer is left alone" "$(count_calls 'unit-start t-off.timer')" "0"
check "the website, not enabled here, is never probed" "$(count_calls curl)" "0"
teardown

# 11. The website is enabled and down: started at once.
watchdog_setup
touch "$WORK/enabled-t-web.service"
rc=$(run_recovery)
check "a stopped website is started" "$(count_calls 'unit-start t-web.service')" "1"
teardown

# 12. The website runs but does not answer: restarted on the second run
# in a row, not the first.
watchdog_setup
touch "$WORK/enabled-t-web.service" "$WORK/active-t-web.service"
run_recovery >/dev/null
check "one missed health check restarts nothing" "$(count_calls 'unit-restart t-web.service')" "0"
run_recovery >/dev/null
check "two missed health checks in a row restart it" "$(count_calls 'unit-restart t-web.service')" "1"
teardown

# 13. A missed check followed by an answer starts the count again.
watchdog_setup
touch "$WORK/enabled-t-web.service" "$WORK/active-t-web.service"
run_recovery >/dev/null
touch "$WORK/web-answers"; run_recovery >/dev/null
rm -f "$WORK/web-answers"; run_recovery >/dev/null
check "an answer in between resets the count" "$(count_calls 'unit-restart t-web.service')" "0"
teardown

# 14. A maintenance window leaves the supporting units alone too.
watchdog_setup
touch "$WORK/enabled-t-sync.timer" "$WORK/enabled-t-web.service"
rc=$(TOC_MAINTENANCE_MARKER="$WORK/up" run_recovery)
check "maintenance starts no supporting unit" "$(count_calls unit-start)" "0"
teardown
unset TOC_KEEP_UNITS TOC_WEB_SERVICE

# 15-17. The disk janitor (keep_disk_clear). df, journalctl, apt-get and
# git are stand-ins; the disk is "low" while $WORK/low exists.
janitor_setup() {
    setup; touch "$WORK/up"
    cat > "$WORK/bin/df" <<'STUB'
#!/bin/bash
if [ "$1" = -Pi ]; then
  printf 'Filesystem Inodes IUsed IFree IUse%% Mounted\n/dev/x 1000 500 500 50%% /\n'
elif [ -f "$WORK/low" ]; then
  printf 'Filesystem 1M-blocks Used Available Capacity Mounted\n/dev/x 48000 47900 100 100%% /\n'
else
  printf 'Filesystem 1M-blocks Used Available Capacity Mounted\n/dev/x 48000 20000 28000 42%% /\n'
fi
STUB
    for tool in journalctl apt-get; do
        printf '#!/bin/bash\necho "%s $*" >> "$WORK/calls"\n' "$tool" > "$WORK/bin/$tool"
    done
    cat > "$WORK/bin/git" <<'STUB'
#!/bin/bash
for a in "$@"; do [ "$a" = gc ] && echo "gc $*" >> "$WORK/calls"; done
exit 0
STUB
    cat > "$WORK/bin/python3" <<'STUB'
#!/bin/bash
echo "${@: -1}" >> "$WORK/staff"
STUB
    chmod +x "$WORK/bin/"*
    mkdir -p "$WORK/build/.git" "$WORK/srv/state-repo/.git" \
             "$WORK/srv/state-repo.broken-auto-20261101" "$WORK/srv/state-repo.broken-auto-20261120" \
             "$WORK/live/area"
    touch "$WORK/srv/rollback-code-20261001-000000.tgz" "$WORK/srv/rollback-code-20261002-000000.tgz" \
          "$WORK/live/area/webadmin.queue"
    mkdir -p "$WORK/srv/rollback-code-20261121-203027"
    for n in 1 2 3 4 5 6 7; do touch "$WORK/backups/merc-rollback-2026110${n}T000000Z"; done
    export TOC_DISK_PATH="$WORK/srv" TOC_STATE_REPO="$WORK/srv/state-repo" TOC_ROLLBACK_DIR="$WORK/srv" \
           TOC_SYNC_USER=root TOC_SYNC_LOCK="$WORK/no-sync-running" TOC_DISK_LOW_MB=6144 \
           TOC_DISK_LOW_INODE_PCT=10
}

# 15. Plenty of room: nothing is touched.
janitor_setup
run_recovery >/dev/null
check "a roomy disk clears nothing" "$(count_calls 'journalctl')$(count_calls ' gc ')" "00"
check "a roomy disk keeps old rollbacks" "$(ls "$WORK"/srv/*.tgz | wc -l)" "2"
teardown

# 16. Low: everything that can be made again is cleared, nothing else.
janitor_setup; touch "$WORK/low"
rc=$(run_recovery)
check "janitor run exits cleanly" "$rc" "0"
check "the journal is trimmed" "$(count_calls 'journalctl --vacuum-size')" "1"
check "apt's cache is cleaned" "$(count_calls 'apt-get clean')" "1"
check "both git copies are packed" "$(count_calls ' gc ')" "2"
check "old tar rollbacks are removed" "$(ls "$WORK"/srv/*.tgz 2>/dev/null | wc -l)" "0"
check "the current rollback folder stays" "$([ -d "$WORK/srv/rollback-code-20261121-203027" ] && echo kept)" "kept"
check "only the newest set-aside clone stays" "$(ls -d "$WORK"/srv/state-repo.broken-* | xargs -n1 basename)" "state-repo.broken-auto-20261120"
check "the sync's clone itself stays" "$([ -d "$WORK/srv/state-repo/.git" ] && echo kept)" "kept"
check "five saved binaries are kept" "$(ls "$WORK"/backups/merc-rollback-* | wc -l)" "5"
check "staff are told it is still low" "$(grep -c 'still low and needs a person' "$WORK/staff" 2>/dev/null)" "1"
teardown

# 17. Low again at once: the gap holds it off, no clearing loop.
janitor_setup; touch "$WORK/low"
run_recovery >/dev/null
run_recovery >/dev/null
check "a second low run inside the gap clears nothing more" "$(count_calls 'journalctl --vacuum-size')" "1"
teardown
unset TOC_DISK_PATH TOC_STATE_REPO TOC_ROLLBACK_DIR TOC_SYNC_USER TOC_SYNC_LOCK TOC_DISK_LOW_MB

echo
if [ "$failures" -eq 0 ]; then
    echo "ALL PASS (0 failures)"
    exit 0
fi
echo "FAILED ($failures)"
exit 1
