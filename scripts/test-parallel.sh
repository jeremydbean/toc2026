#!/usr/bin/env bash
# Run the test modules across every core instead of one at a time.
#
# `unittest discover` is serial, and 50 of the 75 modules boot a real
# server that parses all 7,781 rooms. On a twelve-core machine that
# means eleven cores idle for an hour and a half. Each LiveMud already
# picks its own free port and its own throwaway copy of area/, so the
# modules do not collide -- nothing in the fixtures needed changing,
# they were simply never run at the same time.
#
#   scripts/test-parallel.sh                  # everything
#   scripts/test-parallel.sh test_stash       # just these
#   JOBS=4 scripts/test-parallel.sh           # gentler on the machine
#
# Exit status is non-zero if any module failed, and the failures are
# reprinted together at the end rather than buried in the interleaving.
set -uo pipefail

# From the repository root, the way validate.sh runs it. Modules reach
# for src/, area/ and `import webadmin` relative to the root, and
# `python -m` puts the working directory on sys.path; discover adds
# tests/ so `import live_mud` still resolves. Running from inside
# tests/ breaks a third of the suite.
cd "$(dirname "$0")/.." || exit 1

JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"

# Modules to run on their own, after the rest, however many jobs were
# asked for. test_live_gameplay measures a login throttle against the
# wall clock, so a dozen servers competing for the same cores make it
# miss its window and fail for a reason that has nothing to do with
# the code. Everything else is happy to share.
SERIAL="${SERIAL:-test_live_gameplay}"
PYTHON="${PYTHON:-python3}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

if [ "$#" -gt 0 ]; then
    modules=("$@")
else
    modules=()
    for f in tests/test_*.py; do
        f="${f##*/}"
        modules+=("${f%.py}")
    done
fi

# Split the list: everything that can share, and the tail that cannot.
parallel_modules=()
serial_modules=()
for mod in "${modules[@]}"; do
    case " $SERIAL " in
        *" $mod "*) serial_modules+=("$mod") ;;
        *)          parallel_modules+=("$mod") ;;
    esac
done

printf 'Running %d modules across %d jobs' \
    "${#parallel_modules[@]}" "$JOBS"
if [ "${#serial_modules[@]}" -gt 0 ]; then
    printf ', then %d on its own' "${#serial_modules[@]}"
fi
printf '\n\n'
start=$(date +%s)

run_one() {
    local mod="$1"
    local log="$OUT/$mod.log"

    # A name that is not a module at all discovers nothing, passes,
    # and tells you nothing -- which reads exactly like a module that
    # ran and was fine. Say so instead.
    if [ ! -f "tests/$mod.py" ]; then
        printf '  MISS  %s (no tests/%s.py)
' "$mod" "$mod"
        printf '%s
' "$mod" >>"$OUT/failed"
        printf 'no such module: tests/%s.py
' "$mod" >"$log"
        return
    fi
    if "$PYTHON" -m unittest discover -s tests -p "$mod.py" >"$log" 2>&1; then
        # "OK (skipped=3)" still counts as a pass.
        printf '  ok    %s\n' "$mod"
    else
        printf '  FAIL  %s\n' "$mod"
        printf '%s\n' "$mod" >>"$OUT/failed"
    fi
}

running=0
for mod in "${parallel_modules[@]}"; do
    run_one "$mod" &
    running=$((running + 1))
    if [ "$running" -ge "$JOBS" ]; then
        wait -n 2>/dev/null || wait
        running=$((running - 1))
    fi
done
wait

# The ones that need the machine to themselves.
for mod in "${serial_modules[@]}"; do
    run_one "$mod"
done

elapsed=$(( $(date +%s) - start ))
printf '\n%d modules in %dm %ds\n' "${#modules[@]}" $((elapsed / 60)) $((elapsed % 60))

if [ -f "$OUT/failed" ]; then
    printf '\n===== failures =====\n'
    while read -r mod; do
        printf '\n--- %s ---\n' "$mod"
        # The assertion and its message, not the whole run.
        grep -E '^(FAIL|ERROR):|^AssertionError|^[A-Za-z]*Error:|^no such module' \
            "$OUT/$mod.log" | head -12
    done <"$OUT/failed"
    printf '\n%d module(s) failed. Full logs: rerun one with\n' \
        "$(wc -l <"$OUT/failed")"
    printf '  cd tests && %s -m unittest <module> -v\n' "$PYTHON"
    exit 1
fi

printf 'ALL PASS\n'
