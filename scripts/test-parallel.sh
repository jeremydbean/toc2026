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

printf 'Running %d modules across %d jobs\n\n' "${#modules[@]}" "$JOBS"
start=$(date +%s)

run_one() {
    local mod="$1"
    local log="$OUT/$mod.log"
    if "$PYTHON" -m unittest discover -s tests -p "$mod.py" >"$log" 2>&1; then
        # "OK (skipped=3)" still counts as a pass.
        printf '  ok    %s\n' "$mod"
    else
        printf '  FAIL  %s\n' "$mod"
        printf '%s\n' "$mod" >>"$OUT/failed"
    fi
}

running=0
for mod in "${modules[@]}"; do
    run_one "$mod" &
    running=$((running + 1))
    if [ "$running" -ge "$JOBS" ]; then
        wait -n 2>/dev/null || wait
        running=$((running - 1))
    fi
done
wait

elapsed=$(( $(date +%s) - start ))
printf '\n%d modules in %dm %ds\n' "${#modules[@]}" $((elapsed / 60)) $((elapsed % 60))

if [ -f "$OUT/failed" ]; then
    printf '\n===== failures =====\n'
    while read -r mod; do
        printf '\n--- %s ---\n' "$mod"
        # The assertion and its message, not the whole run.
        grep -E '^(FAIL|ERROR):|^AssertionError|^[A-Za-z]*Error:' \
            "$OUT/$mod.log" | head -12
    done <"$OUT/failed"
    printf '\n%d module(s) failed. Full logs: rerun one with\n' \
        "$(wc -l <"$OUT/failed")"
    printf '  cd tests && %s -m unittest <module> -v\n' "$PYTHON"
    exit 1
fi

printf 'ALL PASS\n'
