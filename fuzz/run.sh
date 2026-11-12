#!/usr/bin/env bash
# Run one reader fuzz target for a while (fuzz/README.md).
#
#   fuzz/run.sh <numparse|player|area> [seconds] [extra libFuzzer flags...]
#
# The working corpus is build-fuzz/work/<target>/corpus, started from the
# committed seeds in fuzz/corpus/<target>; what libFuzzer finds new is kept
# there between runs, never written into fuzz/. A crash, hang, leak or
# sanitizer report leaves its input in build-fuzz/work/<target>/artifacts/
# and is replayed once with the game's own output showing, so the report
# is on the screen. Exit status: 0 clean, non-zero a finding (or no build).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/build-fuzz}"
target="${1:?usage: fuzz/run.sh <numparse|player|area> [seconds] [flags...]}"
seconds="${2:-600}"
shift $(( $# >= 2 ? 2 : 1 ))

binary="$OUT/fuzz_$target"
[ -x "$binary" ] || { echo "fuzz/run.sh: no $binary; run fuzz/build.sh" >&2; exit 2; }

work="$OUT/work/$target"
mkdir -p "$work/corpus" "$work/artifacts"
if [ -d "$ROOT/fuzz/corpus/$target" ]; then
    cp -n "$ROOT/fuzz/corpus/$target"/* "$work/corpus/" 2>/dev/null || true
fi

# A target that crashed left its disposable world behind (fuzz_world.c
# removes it only on a clean exit); take those whose process is gone.
for world in "${TOC_FUZZ_DIR:-/dev/shm}"/tocfuzz-*; do
    [ -d "$world" ] || continue
    pid="${world##*-}"
    kill -0 "$pid" 2>/dev/null || rm -rf -- "$world"
done

flags=(-max_total_time="$seconds" -timeout=10 -rss_limit_mb=4096
       -artifact_prefix="$work/artifacts/" -print_final_stats=1)
case "$target" in
    numparse) flags+=(-max_len=256) ;;
    player)   flags+=(-max_len=16384 -close_fd_mask=2 -dict="$ROOT/fuzz/dict/player.dict") ;;
    # The area loaders keep what they read at boot for ever, by design.
    area)     flags+=(-max_len=16384 -close_fd_mask=2 -detect_leaks=0 -dict="$ROOT/fuzz/dict/area.dict")
              export ASAN_OPTIONS="${ASAN_OPTIONS:-detect_leaks=0}" ;;
    *) echo "fuzz/run.sh: unknown target $target" >&2; exit 2 ;;
esac

export UBSAN_OPTIONS="${UBSAN_OPTIONS:-print_stacktrace=1}"
before="$(ls "$work/artifacts" | wc -l)"
status=0
"$binary" "${flags[@]}" "$@" "$work/corpus" || status=$?
after="$(ls "$work/artifacts" | wc -l)"

if [ "$status" -ne 0 ] || [ "$after" -gt "$before" ]; then
    newest="$(ls -t "$work/artifacts" | head -1)"
    if [ -n "$newest" ]; then
        echo "=== replaying $work/artifacts/$newest ===" >&2
        extra=()
        [ "$target" = area ] && extra=(-detect_leaks=0)
        "$binary" "${extra[@]}" "$work/artifacts/$newest" 2>&1 \
            | grep -v ' :: ' | tail -60 >&2 || true
    fi
    [ "$status" -ne 0 ] || status=1
fi
exit "$status"
