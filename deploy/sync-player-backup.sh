#!/bin/sh
set -eu

TOC_ROOT="${TOC_ROOT:-/home/toc/toc2026}"
BACKUP_REMOTE="${BACKUP_REMOTE:?BACKUP_REMOTE is required}"
BACKUP_BRANCH="${BACKUP_BRANCH:-snapshots}"
AGE_RECIPIENT_FILE="${AGE_RECIPIENT_FILE:-/etc/toc2026/player-backup-recipient.txt}"
GIT_SSH_KEY="${GIT_SSH_KEY:-/home/toc/.ssh/id_ed25519_github_toc_backup}"
PLAYER_DIR="$TOC_ROOT/player"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/toc2026-player-backup.lock"

if [ ! -d "$PLAYER_DIR" ]; then
    echo "Player directory not found: $PLAYER_DIR" >&2
    exit 1
fi
if [ ! -r "$AGE_RECIPIENT_FILE" ]; then
    echo "Age recipient file not readable: $AGE_RECIPIENT_FILE" >&2
    exit 1
fi
if [ ! -r "$GIT_SSH_KEY" ]; then
    echo "GitHub deploy key not readable: $GIT_SSH_KEY" >&2
    exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Another player backup is already running; skipping."
    exit 0
fi

work_dir="$(mktemp -d)"
archive_path="$work_dir/player-latest.tar.gz.age"
repo_dir="$work_dir/repository"
cleanup()
{
    rm -rf "$work_dir"
}
trap cleanup EXIT HUP INT TERM

# Each stage checked on its own: /bin/sh has no pipefail, so "tar | age"
# reported success when tar failed half way and age encrypted what it got
# (handoff review, 2026-10-23). The plaintext lives only in this private
# temp dir. corpse/ goes too: a player's corpse is part of what they own
# (corpses.c), and player/ carries the recovery ledger and the snapshots.
plain_path="$work_dir/player.tar.gz"
dirs="player"
[ -d "$TOC_ROOT/corpse" ] && dirs="$dirs corpse"
# shellcheck disable=SC2086
if ! tar -C "$TOC_ROOT" -czf "$plain_path" $dirs; then
    echo "tar failed; nothing was pushed." >&2
    exit 1
fi
if ! tar -tzf "$plain_path" >"$work_dir/listing" || [ ! -s "$work_dir/listing" ]; then
    echo "the archive does not read back; nothing was pushed." >&2
    exit 1
fi
archived_files="$(grep -cv '/$' "$work_dir/listing" || true)"
live_files="$(cd "$TOC_ROOT" && find $dirs -type f | wc -l | tr -d ' ')"
if [ "$archived_files" -lt "$live_files" ]; then
    echo "the archive holds $archived_files files of $live_files; nothing was pushed." >&2
    exit 1
fi
if ! age -R "$AGE_RECIPIENT_FILE" -o "$archive_path" "$plain_path" || [ ! -s "$archive_path" ]; then
    echo "age failed; nothing was pushed." >&2
    exit 1
fi
plain_sha="$(sha256sum "$plain_path" | cut -d' ' -f1)"
archive_sha="$(sha256sum "$archive_path" | cut -d' ' -f1)"
rm -f "$plain_path"

mkdir -p "$repo_dir"
git -C "$repo_dir" init --quiet
git -C "$repo_dir" checkout --quiet --orphan "$BACKUP_BRANCH"
git -C "$repo_dir" remote add origin "$BACKUP_REMOTE"
cp "$archive_path" "$repo_dir/player-latest.tar.gz.age"
cat >"$repo_dir/README.md" <<'EOF'
# Times of Chaos encrypted player snapshot

`player-latest.tar.gz.age` is an age-encrypted archive of the game's
`player/` (characters, snapshots and the recovery ledger) and `corpse/`
directories. `snapshot.txt` names its checksums. The matching private
recovery key is deliberately not stored in this repository or on the host.

This branch holds only the latest archive: every push replaces it. It is
not a version history; the public state sync and the snapshots inside
the archive are where older states live.
EOF
# What a restore checks the archive against. The deployed tree is not a
# git checkout (installs rsync over it), so the commit comes from the
# deploy's own marker when there is one.
(
    cd "$TOC_ROOT"
    printf 'created_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    if [ -r log/deployed-commit ]; then
        printf 'source_commit=%s\n' "$(cut -d' ' -f1 log/deployed-commit)"
    else
        printf 'source_commit=%s\n' "$(git rev-parse HEAD 2>/dev/null || echo unknown)"
    fi
    printf 'directories=%s\n' "$dirs"
    printf 'file_count=%s\n' "$archived_files"
    printf 'player_file_count=%s\n' "$(find player -type f | wc -l | tr -d ' ')"
    printf 'plaintext_sha256=%s\n' "$plain_sha"
    printf 'archive_sha256=%s\n' "$archive_sha"
) >"$repo_dir/snapshot.txt"

git -C "$repo_dir" config user.name "ToC Player Backup"
git -C "$repo_dir" config user.email "toc@localhost"
git -C "$repo_dir" add README.md player-latest.tar.gz.age snapshot.txt
git -C "$repo_dir" commit --quiet -m "backup: refresh encrypted player snapshot"

export GIT_SSH_COMMAND="ssh -i $GIT_SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes"
git -C "$repo_dir" push --quiet --force origin \
    "HEAD:refs/heads/$BACKUP_BRANCH"

echo "Encrypted player snapshot synchronized to GitHub."
