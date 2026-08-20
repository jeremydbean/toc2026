#!/bin/bash

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$REPO_ROOT/install.sh" --open "$@"
