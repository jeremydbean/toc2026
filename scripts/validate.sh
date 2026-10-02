#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
strict_warnings="-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual"
python_bin="${PYTHON:-python3}"
run_smoke="${RUN_SMOKE:-0}"
smoke_port="${SMOKE_PORT:-9999}"

step() {
  printf '\n==> %s\n' "$1"
}

# Every check after the build runs, whatever happened before it, and the
# failures are listed together at the end.
#
# The script used to stop at the first one. From 2026-10-02 to 10-03 the
# Mudlet starter map was stale -- a room had been added without
# regenerating it -- and every push stopped at that check, so the unit
# tests did not run in CI for a day and nobody could see what else was
# broken. A stale generated file is one red line among the results now,
# with the command that fixes it, instead of a wall in front of them.
failures=()
fixes=()

check() {
  # check "<name>" "<how to fix>" command args...
  local name="$1" fix="$2"
  shift 2
  step "$name"
  if ! "$@"; then
    printf '\n!! FAILED: %s\n' "$name"
    failures+=("$name")
    fixes+=("$fix")
  fi
}

cd "$repo_root"

# One build, with the strict warnings on. It used to be two -- the
# default flags and then the strict ones -- which compiled every file
# twice to produce the same working binary. The strict set is the
# default set plus more, and neither uses -Werror, so the second build
# was only ever there to print the warnings; doing it once prints them
# just as well.
#
# The build is the one step that stops everything: nothing after it can
# run without a binary.
step "C clean build, strict warnings"
make clean || exit 1
make "WARNFLAGS=$strict_warnings" || { printf '\n!! FAILED: C build\n'; exit 1; }

check "C area validation mode" \
  "cd area && ../merc --check-area  (the log names the record)" \
  bash -c 'cd area && ../merc --check-area'

# The recovery script only matters in failure paths nobody runs by hand,
# so they are driven against stubbed systemctl/git/make.
check "Game recovery script scenarios" \
  "bash tests/test_game_recovery.sh" \
  bash tests/test_game_recovery.sh

# Guards the deferred-free contract in src/list.c. extract_char() removes the
# element a FOR_EACH_CHARACTER loop is standing on, so freeing nodes eagerly
# left the iterator cursor dangling. Run under ASan/UBSan so a regression
# fails loudly instead of corrupting memory once in a blue moon.
iterator_test() {
  local bin asan_options="detect_leaks=1"
  bin="$(mktemp)"
  gcc -g -fsanitize=address,undefined -Isrc -o "$bin" tests/test_list_iterator.c src/list.c || return 1
  if [ "$(uname -s)" = "Darwin" ]; then
    # Apple's AddressSanitizer runtime aborts when LeakSanitizer is requested.
    asan_options="detect_leaks=0"
  fi
  ASAN_OPTIONS="$asan_options" "$bin"
  local rc=$?
  rm -f "$bin"
  return $rc
}
check "C list iterator sanitizer test" \
  "see tests/test_list_iterator.c" \
  iterator_test

if [ "$run_smoke" = "1" ]; then
  smoke() { (cd area && timeout 25s ../merc "$smoke_port") || test "$?" -eq 124; }
  check "C startup smoke on port $smoke_port" "run the game by hand" smoke
fi

check "Python syntax" \
  "fix the file py_compile names" \
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

# Generated from the rooms: any change to a room's name, exits or sector
# makes it stale, and it is committed so a fresh clone has a map.
check "Mudlet package and starter map" \
  "python3 scripts/build_mudlet_package.py   (then commit mudlet/)" \
  "$python_bin" scripts/build_mudlet_package.py --check

area_checks() {
  local rc=0
  "$python_bin" check_parser.py || rc=1
  "$python_bin" check_exits.py || rc=1
  "$python_bin" check_resets.py || rc=1
  "$python_bin" check_shops.py || rc=1
  "$python_bin" scripts/area_lint.py --fail-on critical --limit 20 || rc=1
  return $rc
}
check "Area data checks" \
  "run the failing check_*.py / area_lint.py on its own" \
  area_checks

# Across every core rather than one at a time: most of these modules
# boot a real server and then spend their time waiting for it, so the
# cores are idle either way. See scripts/test-parallel.sh, which also
# keeps the timing-sensitive modules out of the crowd.
check "Unit tests" \
  "scripts/test-parallel.sh <module>   (the failures are reprinted above)" \
  env PYTHON="$python_bin" bash scripts/test-parallel.sh

# Not log/. The game writes it, this script made it write to it two
# steps ago by running --check-area, and merc's own banner ends in a
# space -- so an unfiltered check fails on output this script caused,
# which is the worst kind of red. The check is about source hygiene.
check "Git whitespace check" \
  "remove the trailing whitespace git diff --check names" \
  git diff --check -- . ':(exclude)log'

if [ "${#failures[@]}" -eq 0 ]; then
  printf '\nValidation complete.\n'
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    printf '### Validation passed\n' >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 0
fi

printf '\n==> %d check(s) failed\n' "${#failures[@]}"
for i in "${!failures[@]}"; do
  printf '  FAILED  %s\n          fix: %s\n' "${failures[$i]}" "${fixes[$i]}"
done
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    printf '### Validation failed\n\n| Check | How to fix |\n| --- | --- |\n'
    for i in "${!failures[@]}"; do
      printf '| %s | `%s` |\n' "${failures[$i]}" "${fixes[$i]}"
    done
  } >> "$GITHUB_STEP_SUMMARY"
fi
exit 1
