#!/bin/bash

set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
"$REPO_ROOT/toc.sh" start
"$REPO_ROOT/toc.sh" open
