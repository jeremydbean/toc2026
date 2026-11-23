#!/bin/sh
# Unpack one encrypted player backup into a scratch directory, checked
# against its record -- never over a live tree.
#
#   restore-player-backup.sh <backup clone or directory> <age identity file> <out dir> [<stamp>]
#
# <backup clone> is a checkout of the private backup branch (git clone
# --depth 1 -b snapshots ...). Without <stamp>, latest.txt names the archive.
# The archive's checksum is compared with its <stamp>.txt record before it is
# decrypted, the plaintext's after, and the file counts after unpacking. A
# restore to the game is then a person's choice: copy the one character's file
# (or the whole tree, game stopped) from <out dir>/player/ -- see
# wiki/player-backups.md.
set -eu

src=${1:?backup directory}
identity=${2:?age identity file}
out=${3:?output directory}
stamp=${4:-}

[ -r "$identity" ] || { echo "no identity at $identity" >&2; exit 1; }
if [ -z "$stamp" ]; then
    archive=$(sed -n 's/^archive=//p' "$src/latest.txt" 2>/dev/null | head -1)
    [ -n "$archive" ] || { echo "no latest.txt in $src; name a stamp" >&2; exit 1; }
    stamp=$(basename "$archive" .tar.gz.age)
fi
case "$stamp" in
    *[!0-9TZ]*|'') echo "not a stamp: $stamp" >&2; exit 1 ;;
esac
archive="$src/archives/$stamp.tar.gz.age"
record="$src/archives/$stamp.txt"
[ -r "$archive" ] && [ -r "$record" ] || { echo "no archive or record for $stamp" >&2; exit 1; }
field() { sed -n "s/^$1=//p" "$record" | head -1; }

[ ! -e "$out" ] || [ -z "$(ls -A "$out" 2>/dev/null)" ] ||
    { echo "$out is not empty; restore into a new directory" >&2; exit 1; }
case "$(cd "$(dirname "$out")" 2>/dev/null && pwd)/$(basename "$out")" in
    /srv/toc/current|/srv/toc/current/*) echo "never into the live tree" >&2; exit 1 ;;
esac

[ "$(sha256sum "$archive" | cut -d' ' -f1)" = "$(field archive_sha256)" ] ||
    { echo "the archive does not match its record" >&2; exit 1; }
mkdir -p "$out"
plain=$(mktemp "$out/.plain.XXXXXX")
trap 'rm -f "$plain"' EXIT
age -d -i "$identity" -o "$plain" "$archive"
[ "$(sha256sum "$plain" | cut -d' ' -f1)" = "$(field plaintext_sha256)" ] ||
    { echo "the decrypted archive does not match its record" >&2; exit 1; }
tar -C "$out" -xzf "$plain"
rm -f "$plain"
files=$(find "$out" -type f | wc -l | tr -d ' ')
players=$(find "$out/player" -type f 2>/dev/null | wc -l | tr -d ' ')
[ "$files" -ge "$(field file_count)" ] && [ "$players" -eq "$(field player_file_count)" ] ||
    { echo "unpacked $files files ($players in player/), the record says $(field file_count) ($(field player_file_count))" >&2; exit 1; }
echo "restored $stamp into $out: $files files, $players in player/, checksums match"
