#!/usr/bin/env bash
# Install only the apt packages a CI job is missing, and say how long it took.
#
#   scripts/ci/install_deps.sh gcc zlib1g-dev gdb [lua5.4]
#
# A test shard once spent 292 s here: every job ran `apt-get update` and
# installed its whole list whatever the runner image already had. Now a
# package the image carries costs nothing, a missing one is installed
# without refreshing the package lists first (the image's lists usually
# serve), and only if that fails are the lists refreshed and the install
# tried again. The time goes to the job's step summary, so the variance
# can be read off the runs instead of guessed at.
set -euo pipefail

start=$(date +%s)
missing=()
for pkg in "$@"; do
    if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
        missing+=("$pkg")
    fi
done

how="nothing to install"
if [ "${#missing[@]}" -gt 0 ]; then
    apt=(sudo apt-get install -y --no-install-recommends -o Acquire::Retries=3)
    if DEBIAN_FRONTEND=noninteractive timeout 300 "${apt[@]}" "${missing[@]}"; then
        how="installed ${missing[*]} from the image's package lists"
    else
        DEBIAN_FRONTEND=noninteractive timeout 300 sudo apt-get update -o Acquire::Retries=3
        DEBIAN_FRONTEND=noninteractive timeout 300 "${apt[@]}" "${missing[@]}"
        how="refreshed the package lists and installed ${missing[*]}"
    fi
fi

# lua is looked up by that name too (tests/test_mudlet_assets.py).
if command -v lua5.4 >/dev/null && ! command -v lua >/dev/null; then
    sudo ln -sf "$(command -v lua5.4)" /usr/local/bin/lua
fi

took=$(( $(date +%s) - start ))
line="dependencies: $how in ${took}s (asked for: $*)"
echo "$line"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    echo "$line" >> "$GITHUB_STEP_SUMMARY"
fi
