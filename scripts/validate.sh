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

step "C clean build"
make clean
make

step "C strict warning build"
make clean
make "WARNFLAGS=$strict_warnings"

step "C area validation mode"
(cd area && ../merc --check-area)

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
  scripts/area_lint.py

step "Area data checks"
"$python_bin" check_parser.py
"$python_bin" check_exits.py
"$python_bin" check_resets.py
"$python_bin" check_shops.py
"$python_bin" scripts/area_lint.py --fail-on critical --limit 20

step "Unit tests"
"$python_bin" -m unittest discover -s tests

step "Git whitespace check"
git diff --check

printf '\nValidation complete.\n'
