#!/usr/bin/env bash
# Build the libFuzzer targets for the file readers (fuzz/README.md).
#
#   fuzz/build.sh            # build-fuzz/fuzz_{numparse,player,area}
#   OUT=dir fuzz/build.sh    # somewhere else
#
# Needs clang with libFuzzer and the sanitizer runtimes (Ubuntu:
# clang and libclang-rt-<version>-dev). The game is compiled again with
# -DTOC_FUZZ, which adds only fuzz_world_mark/fuzz_world_rewind to db.c;
# the Makefile and CMake builds never define it. main() in comm.c is
# renamed for libFuzzer's, and every exit() is wrapped (fuzz_world.c).
# Run from anywhere; paths are taken from this script's place.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/build-fuzz}"
CC="${FUZZ_CC:-clang}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 2)}"

SAN="-fsanitize=address,undefined -fno-sanitize-recover=undefined"
CFLAGS="-std=c17 -g -O1 -DROM -Dunix -DTOC_FUZZ -fno-omit-frame-pointer $SAN"
WARN="-w"   # the game's own warnings are the Make and CMake builds' business
LIBS="-lcrypt -lm -lz -pthread"

if ! printf 'int LLVMFuzzerTestOneInput(const char *d, unsigned long s){return 0;}\n' \
     | "$CC" -x c - -fsanitize=fuzzer,address,undefined -o /dev/null 2>/dev/null; then
    echo "fuzz/build.sh: $CC cannot link -fsanitize=fuzzer,address,undefined" >&2
    echo "(on Ubuntu: apt-get install clang libclang-rt-18-dev)" >&2
    exit 2
fi

mkdir -p "$OUT/obj"

compile() {
    local src="$1" obj extra=""
    obj="$OUT/obj/$(basename "${src%.c}").o"
    # libFuzzer brings its own main.
    [ "$(basename "$src")" = comm.c ] && extra="-Dmain=toc_game_main"
    if [ ! -e "$obj" ] || [ "$src" -nt "$obj" ] || [ -n "$(find "$ROOT/src" -name '*.h' -newer "$obj" -print -quit)" ]; then
        "$CC" $CFLAGS $WARN -fsanitize=fuzzer-no-link $extra -I"$ROOT/src" \
            -DTOC_FUZZ_REPO="\"$ROOT\"" -c "$src" -o "$obj"
    fi
}
export -f compile
export CC CFLAGS WARN OUT ROOT

ls "$ROOT"/src/*.c "$ROOT"/fuzz/fuzz_*.c | xargs -P "$JOBS" -I{} bash -c 'compile "$@"' _ {}

GAME_OBJS=()
for src in "$ROOT"/src/*.c; do
    GAME_OBJS+=("$OUT/obj/$(basename "${src%.c}").o")
done

# (a) numparse.c is pure: it links alone.
"$CC" $CFLAGS -fsanitize=fuzzer -o "$OUT/fuzz_numparse" \
    "$OUT/obj/fuzz_numparse.o" "$OUT/obj/numparse.o"

# (b), (c): the whole game.
for target in player area; do
    "$CC" $CFLAGS -fsanitize=fuzzer -Wl,--wrap=exit -o "$OUT/fuzz_$target" \
        "$OUT/obj/fuzz_$target.o" "$OUT/obj/fuzz_world.o" "${GAME_OBJS[@]}" $LIBS
done

echo "built: $OUT/fuzz_numparse $OUT/fuzz_player $OUT/fuzz_area"
