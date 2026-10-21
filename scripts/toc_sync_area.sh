#!/bin/sh
# Bring a live world tree up to date from a code tree, keeping what the
# running game owns.
#
#   scripts/toc_sync_area.sh <code-area-dir> <live-area-dir>
#
# The Docker image (docker-entrypoint.sh) and the native installer
# (scripts/toc_native.sh) both run the game in a live tree that is not
# the checkout, so an update can replace the code without touching
# player-made state. The rules are toc-deploy's, which learned them the
# hard way on the production host; tests/test_install_layout.py holds
# the two exclude lists to each other.
#
#  - Everything in the code tree is copied over, and files the code no
#    longer has are removed, except the runtime state below.
#  - custom.are (builders' RSAVE) and built/ (ANEW areas) are only
#    filled in when the live tree has none: the live copy is newer.
#  - area/*.txt is runtime state, except the help and social text that
#    is code; that is copied back by name.
#  - A shutdown marker is never carried over: the game would not start.
set -eu

src="${1:?usage: toc_sync_area.sh <code-area-dir> <live-area-dir>}"
dst="${2:?usage: toc_sync_area.sh <code-area-dir> <live-area-dir>}"

if [ ! -f "$src/area.lst" ]; then
    echo "toc_sync_area: $src has no area.lst; refusing to sync" >&2
    exit 1
fi
command -v rsync >/dev/null 2>&1 || {
    echo "toc_sync_area: rsync is required" >&2
    exit 1
}
mkdir -p "$dst"

# --checksum: rsync's quick check compares size and mtime only, and a
# same-size edit made within the second was skipped. The world is a few
# tens of megabytes; reading it is nothing beside a restart.
rsync -a --checksum --delete \
  --exclude '/shutdown' --exclude '/webadmin.queue' \
  --exclude '/oracle.ask' --exclude '/oracle.answer' \
  --exclude '/oracle.query' --exclude '/oracle.queryresult' \
  --exclude '/*.txt' \
  --exclude '/pkilldata' --exclude '/wizlist' --exclude '/maxload' \
  --exclude '/offense' --exclude '/relics' --exclude '/not' \
  --exclude '/ban' \
  --exclude '/*.are.*.bak' --exclude '/*.are.*.tmp' \
  --exclude '/*.txt.tmp' \
  --exclude '/bugs.txt.*' --exclude '/typos.txt.*' \
  --exclude '/ideas.txt.*' \
  --exclude '/built/' --exclude '/custom.are' \
  "$src/" "$dst/"

if [ ! -f "$dst/custom.are" ] && [ -f "$src/custom.are" ]; then
    cp "$src/custom.are" "$dst/custom.are"
fi
if [ -d "$src/built" ]; then
    mkdir -p "$dst/built"
    rsync -a --ignore-existing "$src/built/" "$dst/built/"
fi

runtime_txt="shutdown.txt ban.txt bugs.txt ideas.txt typos.txt notes.txt
             maxload.txt wizlist.txt offense.txt relics.txt not.txt
             pkilldata.txt dpsboard.txt"
for f in "$src"/*.txt; do
    [ -f "$f" ] || continue
    b=$(basename "$f")
    skip=0
    for r in $runtime_txt; do
        [ "$b" = "$r" ] && { skip=1; break; }
    done
    [ "$skip" = 1 ] && continue
    cp "$f" "$dst/$b"
done

rm -f "$dst/shutdown.txt" "$dst/shutdown"
