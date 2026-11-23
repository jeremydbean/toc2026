#!/bin/sh
# The encrypted, private copy of the characters (installed as
# /usr/local/sbin/toc-player-backup; toc-player-backup.timer, every six
# hours).
#
# The public state sync (toc-state-sync) is the five-minute copy; this is the
# one that survives the public repository too. player/ and corpse/ are
# tarred, checked, encrypted to an age recipient whose private key never
# lives on the host, and pushed to a private repository.
#
# Rebuilt 2026-11-23 (review): it force-pushed a single "latest" archive, so
# one bad run -- a half-written tree, a truncated archive -- replaced the
# only copy there was, and nothing said whether it had ever run at all.
# Now:
#
# - Generations. The branch holds archives/<stamp>.tar.gz.age with a
#   <stamp>.txt record each: the newest KEEP_RECENT, then the newest of each
#   day for KEEP_DAYS days and of each week for KEEP_WEEKS weeks. Every push
#   is one squashed commit (the archives are not history to keep twice),
#   made from the generations GitHub holds now and pushed with a lease on
#   the commit fetched, so a run never pushes over a branch it did not read.
# - It never pushes over what it cannot read: a remote that does not answer
#   is a failure, not an empty branch.
# - A tree that shrank past MAX_DROP_PCT since the last generation is
#   refused unless $STATE_DIR/allow-drop gives a reason (used once).
# - The push is verified: GitHub must show the commit, and the archive is
#   fetched back and its checksum compared with the record.
# - It says how it went in $STATE_DIR (last-attempt, last-success, status),
#   and "not configured" when it has no remote, recipient or key -- which
#   toc-ops-summary reports as such, never as healthy.
#
# Restore: deploy/restore-player-backup.sh, into a scratch directory.
set -eu

TOC_ROOT="${TOC_ROOT:-/srv/toc/current}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
BACKUP_BRANCH="${BACKUP_BRANCH:-snapshots}"
AGE_RECIPIENT_FILE="${AGE_RECIPIENT_FILE:-/etc/toc/player-backup-recipient.txt}"
GIT_SSH_KEY="${GIT_SSH_KEY:-/srv/toc/.ssh/id_ed25519_github_toc_backup}"
STATE_DIR="${TOC_BACKUP_STATE_DIR:-/var/lib/toc-player-backup}"
LOCK_FILE="${TOC_BACKUP_LOCK:-${XDG_RUNTIME_DIR:-/tmp}/toc-player-backup.lock}"
KEEP_RECENT="${TOC_BACKUP_KEEP_RECENT:-4}"
KEEP_DAYS="${TOC_BACKUP_KEEP_DAYS:-7}"
KEEP_WEEKS="${TOC_BACKUP_KEEP_WEEKS:-4}"
MAX_DROP_PCT="${TOC_BACKUP_MAX_DROP_PCT:-20}"
# GitHub refuses a file over 100 MB, and warns past 50.
MAX_ARCHIVE_MB="${TOC_BACKUP_MAX_ARCHIVE_MB:-90}"
ALLOW_DROP_MAX_AGE="${TOC_BACKUP_ALLOW_DROP_MAX_AGE:-86400}"
PLAYER_DIR="$TOC_ROOT/player"

RESULT=failed
REASON="stopped before it finished"
STEP=start
REMOTE_COMMIT=""
GENERATIONS=""
ARCHIVE=""
ARCHIVE_BYTES=""
mkdir -p "$STATE_DIR" 2>/dev/null || true

receipt_write() {
    tmp="$STATE_DIR/.$1.tmp.$$"
    if cat >"$tmp" 2>/dev/null && sync "$tmp" 2>/dev/null && mv -f "$tmp" "$STATE_DIR/$1"; then
        return 0
    fi
    rm -f "$tmp" 2>/dev/null
    echo "could not write $STATE_DIR/$1" >&2
    return 1
}

work_dir=""
on_exit() {
    code=$?
    [ -n "$work_dir" ] && rm -rf "$work_dir"
    [ "$RESULT" = busy ] && return 0
    [ "$code" -ne 0 ] && [ "$RESULT" != failed ] && RESULT=failed
    [ "$RESULT" = failed ] && [ "$REASON" = "stopped before it finished" ] &&
        REASON="failed during $STEP (exit $code)"
    printf 'time=%s\ntime_utc=%s\nresult=%s\nreason=%s\nexit=%s\nremote_commit=%s\n' \
        "$(date +%s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RESULT" \
        "$(printf '%s' "$REASON" | tr '\t\n' '  ')" "$code" "$REMOTE_COMMIT" |
        receipt_write last-attempt || true
    # status: one word the summary and a person read first.
    case "$RESULT" in
        ok) word=ok ;;
        not-configured) word=not-configured ;;
        *) word=failed ;;
    esac
    printf '%s\n' "$word" | receipt_write status || true
    if [ "$RESULT" = failed ]; then
        logger -t toc-player-backup -p daemon.err "encrypted backup failed: $REASON" 2>/dev/null || true
    fi
    return 0
}
trap on_exit EXIT
trap 'exit 1' HUP INT TERM

fail() { RESULT=failed; REASON="$1"; echo "$1" >&2; exit 1; }

# --- configured at all? ------------------------------------------------------
missing=""
[ -n "$BACKUP_REMOTE" ] || missing="$missing BACKUP_REMOTE"
[ -r "$AGE_RECIPIENT_FILE" ] || missing="$missing recipient($AGE_RECIPIENT_FILE)"
case "$BACKUP_REMOTE" in
    file://*|/*) ;;                      # a local remote needs no key
    *) [ -r "$GIT_SSH_KEY" ] || missing="$missing key($GIT_SSH_KEY)" ;;
esac
command -v age >/dev/null 2>&1 || missing="$missing age"
if [ -n "$missing" ]; then
    RESULT=not-configured
    REASON="not configured: missing${missing}"
    echo "$REASON" >&2
    # Not a failure of the unit -- nothing was asked of it -- but never a
    # success: last-success is not touched, and the status says so.
    exit 0
fi
[ -d "$PLAYER_DIR" ] || fail "player directory not found: $PLAYER_DIR"

exec 9>"$LOCK_FILE"
flock -n 9 || { RESULT=busy; echo "another player backup is running; skipping"; exit 0; }

work_dir="$(mktemp -d)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
plain="$work_dir/plain.tar.gz"
sealed="$work_dir/$stamp.tar.gz.age"
repo="$work_dir/repo"
export GIT_SSH_COMMAND="ssh -i $GIT_SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes"

# --- what GitHub holds now ---------------------------------------------------
# ls-remote answering with nothing is a new branch; ls-remote failing is a
# remote nobody may push over.
STEP=read-remote
git init --quiet "$repo"
git -C "$repo" remote add origin "$BACKUP_REMOTE"
heads=$(git -C "$repo" ls-remote origin "refs/heads/$BACKUP_BRANCH") ||
    fail "the backup repository did not answer; nothing was pushed"
lease=$(printf '%s\n' "$heads" | cut -f1 | head -1)
if [ -n "$lease" ]; then
    git -C "$repo" fetch --quiet --depth 1 origin "refs/heads/$BACKUP_BRANCH" ||
        fail "the backup branch could not be fetched; nothing was pushed"
    git -C "$repo" checkout --quiet --detach FETCH_HEAD ||
        fail "the backup branch could not be read; nothing was pushed"
fi
git -C "$repo" checkout --quiet --orphan "toc-backup-$stamp"
mkdir -p "$repo/archives"
# A branch from before generations held player-latest.tar.gz.age: it
# becomes the first generation rather than being thrown away.
if [ -f "$repo/player-latest.tar.gz.age" ]; then
    old=$(sed -n 's/^created_utc=//p' "$repo/snapshot.txt" 2>/dev/null | tr -d ':-' | head -1)
    [ -n "$old" ] || old=19700101T000000Z
    mv "$repo/player-latest.tar.gz.age" "$repo/archives/$old.tar.gz.age"
    if [ -f "$repo/snapshot.txt" ]; then
        mv "$repo/snapshot.txt" "$repo/archives/$old.txt"
    fi
fi
rm -f "$repo/player-latest.tar.gz.age" "$repo/snapshot.txt"
[ ! -e "$repo/archives/$stamp.tar.gz.age" ] ||
    fail "a generation stamped $stamp is already there; nothing was pushed"

# --- the archive -------------------------------------------------------------
# Each stage checked on its own: /bin/sh has no pipefail, so "tar | age"
# reported success when tar failed half way (handoff review, 2026-10-23).
STEP=archive
dirs="player"
[ -d "$TOC_ROOT/corpse" ] && dirs="$dirs corpse"
# shellcheck disable=SC2086
tar -C "$TOC_ROOT" -czf "$plain" $dirs || fail "tar failed; nothing was pushed"
tar -tzf "$plain" >"$work_dir/listing" && [ -s "$work_dir/listing" ] ||
    fail "the archive does not read back; nothing was pushed"
archived_files="$(grep -cv '/$' "$work_dir/listing" || true)"
# shellcheck disable=SC2086
live_files="$(cd "$TOC_ROOT" && find $dirs -type f | wc -l | tr -d ' ')"
[ "$archived_files" -ge "$live_files" ] ||
    fail "the archive holds $archived_files files of $live_files; nothing was pushed"
player_files="$(cd "$TOC_ROOT" && find player -type f | wc -l | tr -d ' ')"

# The drop guard, against the newest generation GitHub holds.
newest=$(ls "$repo/archives" 2>/dev/null | sed -n 's/\.txt$//p' | sort | tail -1)
if [ -n "$newest" ]; then
    before=$(sed -n 's/^player_file_count=//p' "$repo/archives/$newest.txt" | head -1)
    case "$before" in
        ''|*[!0-9]*) ;;
        *)
            if [ "$before" -gt 0 ] && [ $(( player_files * 100 )) -lt $(( before * (100 - MAX_DROP_PCT) )) ]; then
                override="$STATE_DIR/allow-drop"
                made=$(stat -c %Y "$override" 2>/dev/null || echo 0)
                if [ -f "$override" ] && [ $(( $(date +%s) - made )) -le "$ALLOW_DROP_MAX_AGE" ]; then
                    why=$(head -c 200 "$override" | tr '\t\r\n' '   ')
                    echo "drop allowed by $override (player:$before->$player_files): $why" >&2
                    logger -t toc-player-backup -p daemon.warning "drop allowed (player:$before->$player_files): $why" 2>/dev/null || true
                    mv -f "$override" "$override.used-$(date +%s)" 2>/dev/null || true
                else
                    fail "refused: player/ holds $player_files files, the last backup $before; nothing was pushed. If it is meant, write a reason to $override"
                fi
            fi ;;
    esac
fi

STEP=encrypt
age -R "$AGE_RECIPIENT_FILE" -o "$sealed" "$plain" && [ -s "$sealed" ] ||
    fail "age failed; nothing was pushed"
head -c 21 "$sealed" | grep -q '^age-encryption.org/v1' ||
    fail "the encrypted archive has no age header; nothing was pushed"
plain_sha="$(sha256sum "$plain" | cut -d' ' -f1)"
archive_sha="$(sha256sum "$sealed" | cut -d' ' -f1)"
ARCHIVE_BYTES=$(wc -c <"$sealed" | tr -d ' ')
rm -f "$plain"
[ "$ARCHIVE_BYTES" -le $(( MAX_ARCHIVE_MB * 1048576 )) ] ||
    fail "the archive is $ARCHIVE_BYTES bytes, past ${MAX_ARCHIVE_MB} MB (GitHub refuses files over 100 MB); nothing was pushed"
mv "$sealed" "$repo/archives/$stamp.tar.gz.age"
ARCHIVE="archives/$stamp.tar.gz.age"
{
    printf 'created_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    if [ -r "$TOC_ROOT/log/deployed-commit" ]; then
        printf 'source_commit=%s\n' "$(cut -d' ' -f1 "$TOC_ROOT/log/deployed-commit")"
    else
        printf 'source_commit=unknown\n'
    fi
    printf 'directories=%s\n' "$dirs"
    printf 'file_count=%s\n' "$archived_files"
    printf 'player_file_count=%s\n' "$player_files"
    printf 'plaintext_sha256=%s\n' "$plain_sha"
    printf 'archive_sha256=%s\n' "$archive_sha"
    printf 'archive_bytes=%s\n' "$ARCHIVE_BYTES"
} >"$repo/archives/$stamp.txt"

# --- which generations stay ---------------------------------------------------
STEP=retain
keep="$work_dir/keep"
: >"$keep"
n=0 days="" weeks=""
for s in $(ls "$repo/archives" | sed -n 's/\.tar\.gz\.age$//p' | sort -r); do
    n=$((n + 1))
    day=$(printf '%s' "$s" | cut -c1-8)
    week=$(date -u -d "$(printf '%s' "$day" | sed 's/\(....\)\(..\)\(..\)/\1-\2-\3/')" +%G%V 2>/dev/null || echo "$day")
    take=no
    if [ "$n" -le "$KEEP_RECENT" ]; then take=yes; fi
    case " $days " in *" $day "*) ;; *)
        if [ "$(printf '%s\n' $days | grep -c .)" -lt "$KEEP_DAYS" ]; then
            days="$days $day"; take=yes
        fi ;; esac
    case " $weeks " in *" $week "*) ;; *)
        if [ "$(printf '%s\n' $weeks | grep -c .)" -lt "$KEEP_WEEKS" ]; then
            weeks="$weeks $week"; take=yes
        fi ;; esac
    if [ "$take" = yes ]; then
        echo "$s" >>"$keep"
    fi
done
for f in "$repo"/archives/*; do
    s=$(basename "$f"); s=${s%.tar.gz.age}; s=${s%.txt}
    grep -qx "$s" "$keep" || rm -f "$f"
done
GENERATIONS=$(wc -l <"$keep" | tr -d ' ')
newest_kept=$(sort -r "$keep" | head -1)

cat >"$repo/README.md" <<'EOF'
# Times of Chaos encrypted player backups

`archives/<stamp>.tar.gz.age` are age-encrypted archives of the game's
`player/` (characters, snapshots and the recovery ledger) and `corpse/`
directories, each with `<stamp>.txt` naming its checksums and file counts.
`latest.txt` names the newest. The private key is deliberately not stored
here or on the host.

Kept: the newest four, then the newest of each day for a week and of each
week for four weeks. Every push is one commit: older commits are not
history. Restore with deploy/restore-player-backup.sh from the game's
repository, into a scratch directory.
EOF
printf 'archive=archives/%s.tar.gz.age\nrecord=archives/%s.txt\n' "$newest_kept" "$newest_kept" >"$repo/latest.txt"

STEP=commit
git -C "$repo" add -A
git -C "$repo" -c user.name="ToC Player Backup" -c user.email="toc@localhost" \
    commit --quiet -m "backup: $stamp ($GENERATIONS generations)"
mine=$(git -C "$repo" rev-parse HEAD)

# A lease on what was read: a branch that moved meanwhile, or appeared, is
# not pushed over.
STEP=push
git -C "$repo" push --quiet --force-with-lease="refs/heads/$BACKUP_BRANCH:$lease" \
    origin "HEAD:refs/heads/$BACKUP_BRANCH" ||
    fail "the push was refused or failed; the backup repository keeps what it had"

# --- verified, or not a success ------------------------------------------------
STEP=verify
seen=$(git -C "$repo" ls-remote origin "refs/heads/$BACKUP_BRANCH" | cut -f1) ||
    fail "pushed, but the backup repository could not be read back"
[ "$seen" = "$mine" ] || fail "pushed, but the backup repository shows ${seen:-nothing}, not $mine"
REMOTE_COMMIT=$seen
check="$work_dir/check"
git init --quiet "$check"
git -C "$check" fetch --quiet --depth 1 "$BACKUP_REMOTE" "refs/heads/$BACKUP_BRANCH" ||
    fail "pushed, but the archive could not be fetched back"
got=$(git -C "$check" show "FETCH_HEAD:$ARCHIVE" | sha256sum | cut -d' ' -f1)
[ "$got" = "$archive_sha" ] || fail "pushed, but the archive fetched back does not match its checksum"

RESULT=ok
REASON="pushed $ARCHIVE ($ARCHIVE_BYTES bytes, $GENERATIONS generations)"
printf 'time=%s\ntime_utc=%s\nremote_commit=%s\narchive=%s\narchive_sha256=%s\narchive_bytes=%s\ngenerations=%s\nplayer_file_count=%s\n' \
    "$(date +%s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$REMOTE_COMMIT" "$ARCHIVE" \
    "$archive_sha" "$ARCHIVE_BYTES" "$GENERATIONS" "$player_files" |
    receipt_write last-success || fail "pushed and verified, but the receipt could not be written"
echo "$REASON"
