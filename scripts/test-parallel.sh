#!/usr/bin/env bash
# Run the test modules across every core instead of one at a time.
#
#   scripts/test-parallel.sh                  # everything
#   scripts/test-parallel.sh test_stash       # just these
#   JOBS=4 scripts/test-parallel.sh           # gentler on the machine
#
# The work is done by scripts/ci/run_tests.py, which CI calls directly
# with shards, results and artifacts; this wrapper keeps the command
# people already type. Every module runs in a session of its own under a
# timeout (TOC_MODULE_TIMEOUT, default 1200 s), a Ctrl-C kills the game
# servers it started, timing-sensitive modules (SERIAL, default
# test_live_gameplay) run alone after the rest, and the failures are
# reprinted together at the end with their tracebacks.
#
# From the repository root, always: modules reach for src/, area/ and
# `import webadmin` relative to it, and run from inside tests/ a third of
# them fail on imports and paths in ways that look like product bugs.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
exec "${PYTHON:-python3}" scripts/ci/run_tests.py "$@"
