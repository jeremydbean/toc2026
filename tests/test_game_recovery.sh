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
    reset|clean) exit 0 ;;
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

echo
if [ "$failures" -eq 0 ]; then
    echo "ALL PASS (0 failures)"
    exit 0
fi
echo "FAILED ($failures)"
exit 1
