#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
strict_warnings="-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual"
python_bin="${PYTHON:-python3}"
run_smoke="${RUN_SMOKE:-0}"
smoke_port="${SMOKE_PORT:-9999}"

step() {
  printf '\n==> %s\n' "$1"
}

cd "$repo_root"

# One build, with the strict warnings on. It used to be two -- the
# default flags and then the strict ones -- which compiled every file
# twice to produce the same working binary. The strict set is the
# default set plus more, and neither uses -Werror, so the second build
# was only ever there to print the warnings; doing it once prints them
# just as well.
step "C clean build, strict warnings"
make clean
make "WARNFLAGS=$strict_warnings"

step "C area validation mode"
(cd area && ../merc --check-area)

step "Game recovery script scenarios"
# The recovery script only matters in failure paths nobody runs by hand,
# so they are driven against stubbed systemctl/git/make.
bash tests/test_game_recovery.sh

step "C list iterator sanitizer test"
# Guards the deferred-free contract in src/list.c. extract_char() removes the
# element a FOR_EACH_CHARACTER loop is standing on, so freeing nodes eagerly
# left the iterator cursor dangling. Run under ASan/UBSan so a regression
# fails loudly instead of corrupting memory once in a blue moon.
iterator_test_bin="$(mktemp)"
gcc -g -fsanitize=address,undefined -Isrc -o "$iterator_test_bin" tests/test_list_iterator.c src/list.c
asan_options="detect_leaks=1"
if [ "$(uname -s)" = "Darwin" ]; then
  # Apple's AddressSanitizer runtime aborts when LeakSanitizer is requested.
  asan_options="detect_leaks=0"
fi
ASAN_OPTIONS="$asan_options" "$iterator_test_bin"
rm -f "$iterator_test_bin"

if [ "$run_smoke" = "1" ]; then
  step "C startup smoke on port $smoke_port"
  (cd area && timeout 25s ../merc "$smoke_port") || test "$?" -eq 124
fi

step "Python syntax"
"$python_bin" -m py_compile \
  webadmin/server.py \
  webadmin/area_parser.py \
  webadmin/area_health.py \
  scripts/player_watcher.py \
  scripts/web_server.py \
  scripts/area_lint.py \
  scripts/extract_zelda_reference.py \
  scripts/extract_zelda_entities.py \
  scripts/extract_zelda_doors.py \
  scripts/build_hyrule_manifest.py \
  scripts/build_hyrule_area.py \
  scripts/build_mudlet_package.py \
  scripts/test_mudlet_handshake.py

step "Mudlet package and starter map"
"$python_bin" scripts/build_mudlet_package.py --check

step "Area data checks"
"$python_bin" check_parser.py
"$python_bin" check_exits.py
"$python_bin" check_resets.py
"$python_bin" check_shops.py
"$python_bin" scripts/area_lint.py --fail-on critical --limit 20

# Across every core rather than one at a time: most of these modules
# boot a real server and then spend their time waiting for it, so the
# cores are idle either way. See scripts/test-parallel.sh, which also
# keeps the timing-sensitive modules out of the crowd.
step "Unit tests"
PYTHON="$python_bin" bash scripts/test-parallel.sh

# Not log/. The game writes it, this script made it write to it two
# steps ago by running --check-area, and merc's own banner ends in a
# space -- so an unfiltered check fails on output this script caused,
# which is the worst kind of red. The check is about source hygiene.
step "Git whitespace check"
git diff --check -- . ':(exclude)log'

printf '\nValidation complete.\n'
