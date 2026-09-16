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

tar -C "$TOC_ROOT" -czf - player \
    | age -R "$AGE_RECIPIENT_FILE" -o "$archive_path"

mkdir -p "$repo_dir"
git -C "$repo_dir" init --quiet
git -C "$repo_dir" checkout --quiet --orphan "$BACKUP_BRANCH"
git -C "$repo_dir" remote add origin "$BACKUP_REMOTE"
cp "$archive_path" "$repo_dir/player-latest.tar.gz.age"
cat >"$repo_dir/README.md" <<'EOF'
# Times of Chaos encrypted player snapshot

`player-latest.tar.gz.age` is an age-encrypted archive created by the ToC
appliance. The matching private recovery key is deliberately not stored in
this repository or on the appliance.
EOF
(
    cd "$TOC_ROOT"
    printf 'created_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$(git rev-parse HEAD)"
    printf 'player_file_count=%s\n' "$(find player -type f | wc -l | tr -d ' ')"
) >"$repo_dir/snapshot.txt"

git -C "$repo_dir" config user.name "ToC Player Backup"
git -C "$repo_dir" config user.email "toc@localhost"
git -C "$repo_dir" add README.md player-latest.tar.gz.age snapshot.txt
git -C "$repo_dir" commit --quiet -m "backup: refresh encrypted player snapshot"

export GIT_SSH_COMMAND="ssh -i $GIT_SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes"
git -C "$repo_dir" push --quiet --force origin \
    "HEAD:refs/heads/$BACKUP_BRANCH"

echo "Encrypted player snapshot synchronized to GitHub."
