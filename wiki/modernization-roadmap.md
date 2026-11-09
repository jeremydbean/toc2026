# Modernization Roadmap (assessment, 2026-11-09)

**Status: an assessment and plan. Nothing in it is implemented.** It reviews
current `main` against nine areas the owner asked about, beyond the
SHA-512 password migration (done, 2026-11-07) and the TLS player port
(planned and on hold, `SECURITY.md`). Each recommendation says what
already exists first, and favours small changes that can be reviewed and
rolled back on their own.

**Owner requirements kept throughout.**

- The shared administrative credential (`WEB_ADMIN_TOKEN`) stays. Nothing
  here proposes individual staff accounts or MFA.
- Because the credential is shared, no change claims to record *which
  person* acted. Audit rows record the channel, the effective authority,
  the target and the outcome.
- Gameplay, save compatibility, staff ranks and creator-only commands
  (`get_trust`, `rank_protects`, `CR`), wizinvis hiding, recovery
  contracts (`DURABLE_OK`/`FAILED`/`UNCERTAIN`, the recovery ledger) and
  the deploy behaviour (`toc-deploy`, the auto-deploy markers, the public
  state sync) are unchanged unless an item says otherwise and asks first.

Item ids are referred to throughout:

- **A**, admin model; **R**, admin requests; **D**, dependencies and
  provenance (appendix 1).
- **F**, fuzzing; **H**, hardening; **I**, incidents; **V**, recovery
  verification (appendix 2).
- **P7**, performance; **P8**, parsing and persistence; **P9**,
  accessibility (appendix 3).

Effort is **S** (a day or less, one commit), **M** (a few days, a few
commits) or **L**. Every item in the appendices lists what exists, the
gap, the affected files, its dependencies, compatibility risks, a
rollback, and measurable acceptance criteria.

## Verified findings that set the order

The appendices cite file:function for every claim. The claims ranked at
the top were checked again against the source while this was merged:

1. **The dashboard serves plain HTTP on every interface.**
   `deploy/windows-vm/toc-web.service` starts it with
   `--host 0.0.0.0 --port 9001`. The browser play client is served on the
   same port, so it is reachable from outside. When staff use the
   dashboard remotely, the shared token crosses the network in clear
   (A1).
2. **Deploys never update the dashboard's Python environment.**
   `toc-deploy` has no pip or venv step. `webadmin/oracle.py` imports
   `anthropic`, which no requirements file names, so it was installed by
   hand. A rebuilt host gets whatever `toc-restore` installs, and
   `toc-restore` ignores failures (`|| true`) (D1, D2).
3. **One bad number in one player file stops the whole game.** In
   `src/db.c`, `fread_number` calls `exit(1)`. It is reached from
   `load_char_obj` at that player's name prompt (P8.3).
4. **The encrypted off-host backup is not versioned.**
   `deploy/sync-player-backup.sh` says its branch "holds only the latest
   archive: every push replaces it". Credentials on the host can
   therefore erase the only encrypted copy. The public state sync stays
   as the owner set it; this is about the *separate* encrypted copy (V5).
5. **The game loop's pacing and its systemd watchdog ping use the wall
   clock** (`game_loop_unix`). A clock stepped back stalls the loop and
   can miss `WatchdogSec` (P7.3).
6. **The play journal names wizinvis actors in some rows but not others.**
   `cmd`, `refused`, `report`, `anomaly`, `session` and `death` rows name
   the character; `outcome`, `state`, `craft` and `item` rows hide a
   wizinvis one (`src/playlog.c`, `journal_write` callers). The public
   watch log already names every watched character's commands
   (`Log <name> [room]: ...` in `log/toc.log`), so this exposes nothing
   new. It is an inconsistency, and a policy question for the owner
   (I0).
7. **The lag has no open cause.** All 34 stall rows on record (Nov 5-8)
   came from the two causes already fixed: the reverse-DNS lookups
   (Nov 6) and the player-file backups (Nov 8). Commands run at a median
   of 0 ms and a 99th percentile of 6 ms. Commands that save cost
   4-25 ms, and must stay synchronous because callers act on whether the
   save landed (appendix 3, 7.0). So the performance work is
   measurement, not optimisation.

## What already exists (short)

- **Admin.** A shared token is sent in `X-Admin-Token`. A token-gated
  local cookie is a constant HMAC that never expires. Protected
  WebSockets authenticate by their first message. Queue payloads are
  bounded and ASCII. The game reads the queue under an fcntl lock.
- **Recovery.** A recovery ledger with receipts (pending, committed,
  rejected, retry), uids, milestone checksums and a torn-tail repair.
  Snapshots on every save, with retention. A corpse registry with
  history. `restores.dat` delivered through git. `toc-restore`, which
  can be rehearsed into a scratch directory.
- **CI.** ASan/UBSan play live modules. There are C harnesses for the
  pure modules: `netaddr`, `guardstore`, `holiday_rules`,
  `combat_rules`, `password`, `lockwindow`, and the MCCP part of
  `telnet_proto`. A planned CI pipeline with a deploy gate. Deploys with
  code identity and code-only rollback.
- **Logs.** The play journal records commands, outcomes, state, stalls,
  deaths, items, sessions and anomalies. `progress.tsv` records kills,
  and `tools/log_report.py` reads both. The watch log covers every
  player. `tools/audit_players.py`, `tools/player_history.py`.
- **Clients.** GMCP feeds, MTTS and Core.Hello client detection, the
  COLOR palette with a 256-colour fallback, and Mudlet's extras. The
  browser client shares the ANSI decoder.
- **Parsing.** Some strict parsers exist in places (`parse_long_value`,
  the achievement-set reader, the guard store, the lockout reader). The
  file and command boundaries still use `atoi`, `is_number` and
  `fread_number`, about 460 sites in all.

## Ranked roadmap

| # | Item | Effort | Why this rank |
| --- | --- | --- | --- |
| 1 | P8.3 Player-file loads refuse instead of `exit(1)` (player files only; areas still fail fast) | M | One file can take the game down for everyone |
| 2 | A1 TLS in front of the dashboard; admin routes refuse plaintext (`WEB_ADMIN_REQUIRE_TLS`), forwarded addresses kept | M | The shared credential crosses the network in clear |
| 3 | V5 Versioned, encrypted off-host backup with independent, write-only credentials and locked retention | M | Today one host key can erase the only encrypted copy |
| 4 | D1 + D2 Hash-checked Python lock (incl. `anthropic`), installed by deploy into a versioned venv before the game stops | S + M | The live environment is not reproducible |
| 5 | P7.3 Monotonic clock for loop pacing, the watchdog and durations | S | A clock step can stall the loop and trip the watchdog |
| 6 | A3 CSRF on cookie-authenticated POSTs; A4 rotation script, token kept off argv and out of `toc.sh backup` | S + S | Cheap; closes a local cross-site path to `/api/shutdown` |
| 7 | V1 + V2 `merc --check-players` and a restore drill reporting the newest verified recovery point | M + M | Today a restore is proved to boot, not to hold the characters |
| 8 | F0 sanitizers on the single-module C harnesses; H1-H3 probe-guarded hardening flags and a binary check in CI | S each | Cheap assurance; the clang build is unhardened today |
| 9 | D5 GitHub Actions pinned to SHAs, Dependabot; D6 pip-audit/osv-scanner outside the gate; D4 build provenance | S each | Supply-chain basics, no runtime change |
| 10 | R1-R3 Versioned queue lines with request ids, a results file, and the dashboard showing queued vs executed | S + M + S | The dashboard cannot tell queued from done |
| 11 | P8.1 + P8.2 One strict number parser, adopted one boundary at a time (network, then files, then commands) | S each | Removes silent wraps and junk acceptance |
| 12 | I1 + I2 Schema version, boot id, revision and session id in the journal | S each | Prerequisite for incident timelines |
| 13 | A2 Server-side admin sessions (`__Host-` cookie, expiry, real logout, invalidated on rotation) | M | Replaces the never-expiring cookie |
| 14 | F1 + F2 Fuzz infrastructure and the Telnet target (60 s per target on PRs, 10 min nightly) | S/M + S | The highest-risk parser, with no extraction needed |
| 15 | P9.2 Text equivalents for colour-only information, then P9.1 an opt-in SCREENREADER mode | S + M | Accessibility; MTTS's screen-reader bit is unused |
| 16 | I5 + I6 `tools/incident.py` and a redacted AI export (fields passed only if listed) | M + M | Investigation without production credentials |
| 17 | P9.3 Input transliterated to ASCII at the boundary (password bytes untouched) | S/M | Accented letters typed are silently dropped today |
| 18 | P7.1 + P7.2 Stall rows saying worked vs waited; an hourly latency summary | S + S | Better measurement before any optimisation |
| 19 | R4 Typed operations (start with `fsave` for `toc-deploy`); D3 venv rollback | M + S | After R1-R3 and D2 |
| 20 | F3-F5 PROXY, GMCP and persistence fuzz targets (each needs a parser extracted first) | M each | After F1; F3 pairs with the TLS port |
| 21 | P8.4 Compatibility corpus of synthetic old-layout player files; version headers on the trust and lockout files | M | Before any `Vers` change |
| 22 | V3 + V4 End-to-end synthetic drill and scheduled drills | S each | After V1 and V2 |
| 23 | D7 SBOM and provenance per release; R5 ledger-backed restores from the dashboard; A7 read-only AI diagnostics | M each | Valuable once the basics land |

## The first three small batches

Each batch is independently reviewable and revertible, and none changes
gameplay or saves.

**Batch 1: reproducible inputs, no runtime change (S).**
- D1: `webadmin/requirements.in` (the existing pins plus `anthropic`) and a
  hash-checked, universal lock for Python 3.12 that covers x86_64 and
  aarch64 Linux and macOS. CI installs from it with `--require-hashes`.
- D5: pin every `uses:` in `.github/workflows/*.yml` to a reviewed SHA,
  with the tag in a comment. A `.github/dependabot.yml` for pip, actions
  and Docker.
- F0: the single-module C harnesses built with `-fsanitize=address,undefined`
  where the compiler supports it.
- Acceptance:
  - CI is green with `pip install --require-hashes`.
  - A test fails if any `uses:` is not a 40-hex SHA.
  - Every harness module passes under ASan/UBSan.
  - The deployed tree is unchanged, because `toc-deploy` is not touched
    in this batch.
- Rollback: revert the commit.

**Batch 2: loop robustness and binary hardening (S, C).**
- P7.3: `CLOCK_MONOTONIC` for the loop's pacing, the watchdog interval
  and measured durations (`playlog_now_ms`, `interpret()` timing).
  Persisted times stay wall-clock.
- H1/H2: probe-guarded hardening flags in the Makefile and CMake (stack
  protector, FORTIFY, PIE, RELRO/BIND_NOW, stack-clash, CET or BTI by
  arch), with no `-z` flags on macOS.
- H3: a CI step that inspects the built binaries for PIE, RELRO,
  BIND_NOW, NX, a stack canary, `_chk` imports and the CET or BTI notes.
- Acceptance:
  - Both trees build.
  - The binary check passes on x86_64 and on an `ubuntu-24.04-arm` job.
  - A C test of the pacing arithmetic: a wall-clock step of -1 h and +1 h
    leaves the sleep within one pulse.
  - The world loads, and the stall and session modules pass.
- Rollback: revert; the flags change only the binary.

**Batch 3: shared-admin hygiene (S, Python and shell).**
- A3: an Origin/`Sec-Fetch-Site` check plus a CSRF token on
  cookie-authenticated POSTs. Requests carrying `X-Admin-Token` stay
  exempt.
- A4: a rotation script that writes the new token to `/etc/toc/web.env`
  and prints only a fingerprint. `toc-deploy` sends the token from a
  file, not on curl's argv. `toc.sh backup` stops archiving it.
- A5: a request id on every admin request, and an audit journal outside
  the publicly synced `log/` and `player/`. It records channel,
  authority, token fingerprint, target and outcome, and no person.
- Acceptance:
  - Tests cover no, wrong and right tokens; a cross-origin POST refused;
    a header-token POST accepted.
  - The token never appears in `/proc/<pid>/cmdline` during a stubbed
    deploy, nor in a backup archive.
  - Audit rows carry a request id and outcome.
  - `tests/test_webadmin_api.py` passes.
- Rollback: revert; `WEB_ADMIN_TOKEN` and its file are unchanged.

The first medium item after these is **P8.3** (rank 1). It is the most
valuable, but it touches the loader's error path and needs the P8.4
compatibility corpus beside it, so it is better reviewed on its own than
squeezed into a small batch.

## Decisions for the owner (no code without a yes)

- **I0:** journal rows for wizinvis actors. Hide the name in every row,
  as `outcome`/`state`/`craft`/`item` already do, or keep naming them,
  since the watch log names them anyway?
- **R7:** the queue's `shutdown` action bypasses the creator-only SHUTDOWN
  command; keep, restrict, or remove it? And does `/api/command` (free
  command strings) stay enabled once typed operations exist?
- **V5:** where the versioned encrypted backup lives (object storage
  provider and account), and who holds the offline recovery password.
- **A1:** whether the dashboard should also stop listening on 0.0.0.0
  once nginx fronts it. The browser play client is served from the same
  port, so the proxy has to carry `/ws` too.
- **P9.1:** whether the game suggests SCREENREADER mode when a client's
  MTTS says it has a screen reader (a one-line suggestion, never forced).

## What should wait (complexity exceeds value now)

- Deploying CI's x86_64 binary to the aarch64 host (D8). Build on the
  host until CI has an arm64 job whose binary is identical.
- At-least-once queue delivery and capturing free-command output. Typed
  operations with a results file cover the need.
- Gating deploys on vulnerability scans. Report first, gate later.
- Fuzzing the player and area loaders while they `exit()` on bad input.
  Do P8.3 first.
- An in-game INCIDENT command, stable object ids, deterministic replay of
  the world.
- Async saves, io_uring, epoll, a thread pool, a database, a
  metrics/tracing stack. Saves must stay synchronous for their
  durability results, and nothing measured needs the rest.
- TELNET CHARSET negotiation. With ASCII-only output it would change
  nothing a client shows.
- A dashboard UI for full PRESTORE; restores keep going through
  `restores.dat` and in-game PRESTORE.

## Verification policy for every item

- Synthetic Z-named fixtures in disposable worlds (`LiveMud`), and
  TEST-NET addresses. Never a real player file, credential or address
  in a test, example or export.
- Both builds (`make` gnu89, `cmake --build build` c17) for any C
  change.
- The named module through `scripts/test-parallel.sh`.
  `test_login_throttle` runs alone.
- `git diff --check`. CI's planned suite and deploy gate decide the rest.

---

The three appendices below are the detailed assessments. Each item has
its existing state, gap, proposal, effort, files, dependencies, risks,
rollback and acceptance criteria. They were written independently, so
some cross-references between them are by item id.


## Appendix 1: Shared-Admin Hardening, Trackable Admin Requests, Reproducible Releases (A, R, D)

Read-only assessment of the working tree on branch `fix-review-20261109`
(2026-11-09). Line numbers are from that tree; `SECURITY.md`, `src/comm.c`,
`src/merc.h` and others carry another engineer's uncommitted edits, so
`SECURITY.md` is cited by section name. Nothing in the repository was changed.

Fixed constraints for everything below: keep the one shared
`WEB_ADMIN_TOKEN`; no per-staff accounts, no MFA. Leave gameplay, save
formats, `get_trust`/`rank_protects`/`CR`, wizinvis, the recovery-ledger
contracts and `toc-deploy`/`toc-auto-deploy` behaviour as they are. Each
item is a small change that can be reviewed alone. Effort: S is about a day or less, M a few days, L a week or more.

**A shared credential cannot say which person acted.** Every proposal below
records what the system can know for certain: the channel (dashboard, the
deploy script, the in-game queue), the authority it ran under (shared token,
host root, the WebAdmin stand-in at trust 70), the target, the result and
the code revision. The token proves that someone held the secret, not who
they were. No record should claim an operator name. A free-text "note"
field that an operator fills in is allowed, but it is labelled as typed by the operator and not verified.

---------------------------------------------------------------------------

### 0. What exists today (inventory)

#### 0.1 The dashboard's auth model (`webadmin/server.py`)

- The token is read once at import: `_WEB_ADMIN_TOKEN = os.environ.get("WEB_ADMIN_TOKEN", "")`
  (l.32). If it is unset, every protected route returns 503 (`verify_token`, l.111-125).
- HTTP auth goes through the `X-Admin-Token` header, compared with
  `secrets.compare_digest` (l.118). Any other route that should be protected depends on `Depends(verify_token)`.
- **Local-unlock cookie**: `toc_admin_session` (l.42). Its value is
  `HMAC(token, "toc-local-admin-session-v1")` (`local_admin_session_value`,
  l.79-86), so it is a constant that never expires, the same for every
  browser, and changes only when the token is rotated. It is issued by
  `POST /api/auth/local` (l.2847-2864), and only when `WEB_ADMIN_LOCAL_UNLOCK=1`, the server is bound to loopback
  (`set_bind_address` l.46, `bound_to_loopback` l.58) and the peer is
  loopback (`loopback_peer` l.66). The cookie is `httponly`,
  `samesite="strict"`, and `secure` only when `request.url.scheme == "https"` (l.2860).
- `POST /api/auth/logout` (l.2867) deletes the cookie in the browser. Since
  the value is a constant, a copied cookie stays valid until the token changes.
- **WebSocket auth**: `accept_admin_websocket` (l.3363) accepts the
  local-unlock cookie, or a first message `{"type":"auth","token":...}`
  within 5 s. The token never goes in a URL. `websocket_origin_allowed`
  (l.1545) allows a missing Origin (native clients), a same-host Origin, or one listed in `WEB_ALLOWED_ORIGINS`.
- Protected routes: `/api/admin/status`, `/api/host/*`, `/api/logins`,
  `/api/channels`, `/api/oracle`, `/api/auth/check`, `/api/logs*`,
  `/api/events`, `/ws/logs`, `/ws/events`, `/api/announce`, `/api/wizinfo`,
  `/api/command`, `/api/backup`, `/api/update`, `/api/backups`,
  `/api/shutdown`, `/api/reload`, `/api/players`, `/api/player/{name}`.
  Public: world data, help, directions, `/api/config`, `/api/health`, and the `/ws` game bridge.
- **No CORS middleware and no CSRF check.** The only middleware is
  `add_security_headers` (l.1444-1459): CSP with `script-src 'self'`, `frame-ancestors 'none'`,
  `connect-src 'self' ws: wss:`, `Referrer-Policy: no-referrer`, `nosniff`, `X-Frame-Options: DENY`. There is no HSTS.
- **No admin audit trail.** The dashboard writes no record of an action. A
  queued action answers only with the string `"queued"` (l.3525-3590).
- **Browser storage**: `webadmin/static/app.js` l.4 (`TOKEN_KEY`) and
  l.193-204 keep the token in `sessionStorage`, or in `localStorage` when
  "Remember on this browser" is ticked (`index.html` l.666). It is sent as
  a header (`app.js` l.148) and as the first WebSocket message (l.1948). It never goes in a URL.
- **Production listener**: `deploy/windows-vm/toc-web.service` l.21 runs
  `webadmin.server --host 0.0.0.0 --port 9001`, and
  `wiki/disaster-recovery.md` l.22 lists `:9001` as public. **The admin
  token therefore crosses the internet in plaintext HTTP and `ws://`**
  whenever anyone uses the dashboard remotely. `SECURITY.md` ("Dashboard
  Read Endpoints", "Shared Admin Token", "HTTPS Reverse Proxy") says not to expose 9001. The live host does anyway.
- `uvicorn.run(app, host=..., port=...)` (l.4949) runs with uvicorn's
  defaults: access log on, `proxy_headers=True`, `forwarded_allow_ips` = 127.0.0.1.
- **The token outside the dashboard**:
  - `toc-deploy` l.381-384 greps it out of `/etc/toc/web.env` and passes it
    on the `curl` **command line** (`-H "X-Admin-Token: $token"`). Any local
    user can read it in `/proc/<pid>/cmdline` while curl runs.
  - `toc.sh backup` archives `.env`, token included (`toc.sh` l.29), and
    restore keeps the old one as `.env.from-backup` (l.286). A backup archive is therefore a credential.
  - `deploy/toc-restore` l.165 generates a fresh token on the host, which is correct.
- **Rotation** is documented only in prose ("rotate it when staff access
  changes", `SECURITY.md` "Shared Admin Token"). There is no script, no
  fingerprint to confirm which token is live, and no overlap window.

#### 0.2 The queue (dashboard and deploy to game)

- The writer is `QueueWriter.append` (`server.py` l.311-333): one line,
  refused if it holds `\n`, `\r` or NUL or exceeds 4094 bytes, written under
  `fcntl.lockf` LOCK_EX. Payloads are checked by `validated_queue_payload`
  (l.1486): ASCII only, no `|`, no control characters.
- The format is `action|arg|arg`: `announce|msg`, `wizinfo|level|msg`,
  `command|text`, `backup`, `shutdown`. There is no id, no source and no version.
- `toc-deploy` l.35-44 (`queue_append`) writes under the same lock with
  python3, and falls back to a plain best-effort append without it. It
  sends `announce|...`, `command|fsave`, `announce|...` (l.399-411).
- The reader is `process_web_admin_queue` (`src/comm.c` l.5168-5264),
  called every pulse from the game loop (l.1021). It takes an `F_SETLK`
  write lock, copies the file to a `tmpfile()`, **truncates the queue, then
  runs** each line through `process_web_admin_action` (l.5105-5165). So
  delivery is at most once: a crash after the truncate loses the rest
  without a trace. A malformed line is a `bug()` and nothing else.
- The executor is `run_web_command` (l.5046-5103). It builds a stand-in
  mobile, "WebAdmin", with `level = trust = MAX_LEVEL` (70), puts it in
  Limbo, calls `interpret`, then extracts it. **What the command prints is
  thrown away** (the stand-in has no descriptor). It cannot run `CR`
  commands (trust 70 < 72). It can act on implementors, because
  `rank_protects` exempts peers at 70. The `shutdown` queue action sets
  `merc_down = TRUE` directly (l.5157-5160), going around the creator-only
  SHUTDOWN command. That is an existing policy choice, flagged in 2.7.
- Logging: the stand-in's LOG_ALWAYS commands reach `log/toc.log` as
  `Log WebAdmin: ...` (`src/interp.c` l.1647-1663, privacy by
  `line_privacy`). `log/` goes to the public repository every five
  minutes. The queue file is excluded from the deploy rsync
  (`toc-deploy` l.109) and is not in `toc-state-sync` `STATE_FILES` (l.51).
- What exists for the game to report back is `write_web_admin_event`
  (`comm.c` l.5280), which appends `info`/`wizinfo` lines to
  `../log/webadmin-events.tsv`. It filters to those two channels and carries no request id.

#### 0.3 The recovery ledger (`src/recovery.c`, `src/restores.c`)

- `ledger.tsv` lives under `player/recovery/`. Each record is
  `seq epoch event state uid player request kind actor detail check`
  (header comment l.13-38). It is append-only and fsynced (`ledger_append`
  l.613-667). A torn tail is quarantined and cut off; each record carries an FNV check.
- Events and states: `request` pending/committed/rejected/retry/abandoned;
  `prestore`; `snapshot`; `corpse`; `uid`; `transfer` (STASH TAKE, `act_obj.c` l.864-959).
- The single append API is `recovery_record(event, state, player, request,
  kind, actor, detail)` (l.674). Lookup is `recovery_request_state(id)`
  (l.722). Reconciliation at login is `recovery_reconcile_login` (l.741),
  which uses the file's `restore:<op>` mark in `Fixes`.
- Operation ids: `gear:N`/`stash:N` (`prestore_op`, `act_wiz.c`
  l.11460/11497), `corpse:<id>[:seq]` (l.11576-11587), `full:N` (l.12167),
  git requests without a colon (`restores.c`, `restores.dat`: `<id> <player> gear|stash|import <stamp> [<file>]`), and
  `resurrect:<id>`/`death:<id>`.
- The `actor` column is a character name today (`ch->name`), or `-`, `restores.dat` or `boot`.
- `prestore_give` already retries safely: a pending id with the mark in the
  file saves first and only then commits (`act_wiz.c` l.11251-11292). It
  never gives the objects again. This is the model for idempotency below.

#### 0.4 Dependencies, builds, provenance

- `webadmin/requirements.txt` has three floating ranges: `fastapi>=0.121,<1`,
  `uvicorn[standard]>=0.38,<1`, `pydantic>=2,<3`. There are **no transitive
  pins and no hashes**. `scripts/requirements.txt` has `watchdog>=4` and
  `httpx2>=2.5,<3`; `httpx2` is the package starlette's TestClient needs, per `tests/test_webadmin_api.py` l.23.
- **The production venv is never updated by a deploy.** `toc-deploy` has
  no pip step. `/srv/toc/venv` was built once by `toc-restore` l.150-153,
  `pip install ... || true`, **so a failed install is silent**.
  `toc-auto-deploy`'s `deployable()` (l.161-173) still counts a
  `requirements.txt` change as deployable, so such a change "ships" and has
  no effect. Rollback (`toc-deploy` `rollback`, l.216) restores code only.
  The venv is shared and not part of a snapshot.
- **`anthropic` is installed by hand** (`deploy/windows-vm/oracle.env.example`:
  `/srv/toc/venv/bin/pip install anthropic`). It is imported lazily by
  `webadmin/oracle.py` l.653 and appears in no requirements file, CI
  install or Dockerfile. A venv rebuilt from a lock would drop it and
  silently turn the Oracle off. The Docker image cannot run the Oracle even with `ORACLE_ENABLED=1`.
- The native installer (`scripts/toc_native.sh` `toc_native_venv`
  l.87-104) reinstalls when the `cksum` of `requirements.txt` changes. That is a good shape, but nothing is pinned.
- `Dockerfile`: `ubuntu:24.04` by tag, not digest. The venv is built from
  the floating requirements in a separate stage.
- CI (`.github/workflows/validate.yml`) uses Python 3.12 (matching Ubuntu
  24.04's python3) and installs with `pip install -r webadmin/requirements.txt -r scripts/requirements.txt`
  (l.338, 413), with `setup-python` pip caching keyed on those files. The
  top-level permissions are `contents: read, actions: read` (l.87-89).
- **Every action is pinned by a moving tag**: `actions/checkout@v4`,
  `upload-artifact@v4`, `download-artifact@v4`, `setup-python@v5`,
  `cache@v4`, and in `docker-image.yml` `docker/setup-qemu-action@v3`,
  `setup-buildx-action@v3`, `login-action@v3`, `build-push-action@v6`.
  `docker-image.yml` runs on `ubuntu-latest` (l.34) with `packages: write`.
  There is no `.github/dependabot.yml` and no Renovate config.
- The image is tagged `:latest` and `:sha-<short>`, with an OCI revision
  label. No SBOM or provenance attestation is requested (`build-push-action` has no `sbom:`/`provenance:` inputs).
- **Code identity is already strong**: `.code-revision` = `<commit>
  <sha256 of merc>` in the live tree, and `.snapshot-revision` in each
  `rollback-code-<stamp>` (`toc-deploy` l.139-195, `code_identity` l.157).
  Both are verified against the binary and recorded as `unknown` rather
  than guessed. `log/deployed-commit` holds `<commit> <utc> [why]`.
- **Gaps in identity**: the deployed `merc` is built **on the aarch64 host**
  by `make` (`toc-deploy` l.358-363), so it is not the binary CI tested
  (x86_64). Compiler version, CFLAGS, arch, Python version and the venv's
  contents are recorded nowhere. The dashboard reads `TOC_DEPLOYED_COMMIT_FILE`, which defaults to the Pi path
  `/var/lib/toc2026/deployed-commit` (`server.py` l.171-173), not Oracle's `$CURRENT/log/deployed-commit`.

#### 0.5 What AI-assisted investigation already has

- Tools that read synced files, read-only: `tools/log_report.py`,
  `audit_players.py`, `audit_maxload.py` and `player_history.py`. They
  strip addresses from what they print (AGENTS "Mining The Watch Log").
- A fixed, read-only live query that cannot run commands: the Oracle's
  `oracle.query`/`oracle.queryresult` (`src/oracle.c` l.780-789: "never interpret(), never a command").
- A way to ask for a restore without host access: `area/restores.dat`
  through git (`src/restores.c`), receipted in the ledger. A cloud AI
  needs no credential for it, and every request is reviewable in a commit.

---------------------------------------------------------------------------

### 1. Strengthen the shared-admin model

Recommended order: A1 -> A2 -> A3 -> A4 -> A5. The rest can go in any order.

#### A1. TLS in front of the dashboard; admin refused over plaintext (M)

- **Exists**: the public HTTP listener (`toc-web.service` l.21,
  `--host 0.0.0.0`). `SECURITY.md` "HTTPS Reverse Proxy" lists the
  requirements. "Planned: A TLS Player Port" already chooses Ubuntu's
  nginx, with certificates rotated through `/etc/nginx/toc-tls/current/`
  and the certbot webroot flow (the "Certificates" subsection).
- **Gap**: the token, and the cookie when there is one, travel in
  cleartext over `http://` and `ws://`. There is no HSTS.
- **Proposal**:
  1. Reuse the same nginx and the same certificate directory with an `http`
     `server { listen 443 ssl; }` that proxies `/` and `/ws*` (with Upgrade
     headers) to `127.0.0.1:9001`. It sets, never appends,
     `X-Forwarded-For $remote_addr` and `X-Forwarded-Proto https`, caps the
     body (`client_max_body_size 16k`) and turns off query-string logging.
     Ports 443 and 80 (ACME) are opened in the Oracle security list.
  2. Add `WEB_ADMIN_REQUIRE_TLS=1` (default 0). When it is on,
     `verify_token`, `/api/auth/*` and `accept_admin_websocket` refuse
     (403, close 4003) any request whose effective scheme is not
     https/wss, unless the true peer is loopback with no forwarding
     headers, so host-local `toc-deploy` curl keeps working. Player routes
     and `/ws` stay available on plain 9001 during the transition, so the
     Mudlet listing and existing browser players are unaffected.
  3. Send `Strict-Transport-Security: max-age=31536000` only on responses whose effective scheme is https.
  4. Once the browser client has moved to 443 (a separate decision), bind
     `toc-web` to `127.0.0.1` and close 9001 publicly.
- **Compatibility risks**, each needing its own test:
  - The game bridge `/ws` sends `proxy_header_line(websocket.client)`
    (l.4808, l.4851). Behind nginx, `websocket.client` must be the real
    player. That holds only if uvicorn trusts XFF from 127.0.0.1, which is
    its default. If not, every web player becomes loopback, and loopback is
    **exempt from the connection guard and the login lockout** (AGENTS "Connections").
  - **Local unlock behind a loopback proxy**: once rebound to 127.0.0.1,
    `local_admin_unlock_enabled()` turns true when `WEB_ADMIN_LOCAL_UNLOCK=1`, and a request without XFF would look
    loopback. Fix: `local_admin_request_allowed` refuses whenever
    `X-Forwarded-For`, `Forwarded` or `X-Real-IP` is present, or when `WEB_ADMIN_BEHIND_PROXY=1`. Production must keep
    `WEB_ADMIN_LOCAL_UNLOCK` unset.
  - `websocket_origin_allowed` compares Origin to `Host`, so nginx must pass `Host` through unchanged.
- **Files**: `webadmin/server.py` (gate helper, HSTS in
  `add_security_headers`); new `deploy/windows-vm/toc-web-nginx.conf`
  sample. `toc-web.service` changes only in step 4. `SECURITY.md` is left to its owner.
- **Rollback**: set `WEB_ADMIN_REQUIRE_TLS=0` and restart toc-web. nginx can be stopped on its own.
- **Acceptance**:
  - `tests/test_webadmin_tls_gate.py` uses TestClient with `base_url="https://..."`
    or `http://...`, plus `X-Forwarded-Proto`, from a peer in `127.0.0.1`
    and one in `203.0.113.x` (TEST-NET, synthetic). It shows: admin route
    403 over http with the flag on; 200 over https; 200 from loopback with
    no forwarding headers; `/api/health` and `/ws` always open; HSTS only
    on https; and local unlock refused when XFF is present.
  - A live check that `proxy_header_line` carries the XFF address and not 127.0.0.1 (a unit test with an `Address`).
  - Run with `scripts/test-parallel.sh test_webadmin_tls_gate test_webadmin_api`.

#### A2. Server-side admin sessions with Secure cookies and real logout (M)

- **Exists**: only the loopback-unlock cookie, which is constant, never
  expires and is shared by every browser (l.79-86). Remote staff keep the
  raw token in `sessionStorage`/`localStorage` (`app.js` l.193-204).
- **Gap**: the token sits in script-readable storage. CSP lowers the risk
  but does not remove it. "Logout" cannot revoke anything, and there is no idle or absolute expiry.
- **Proposal**: `POST /api/auth/session` with `{"token": ...}` in the JSON
  body, over TLS. After `compare_digest`, it mints 32 random bytes as the
  session id and keeps `{id_hash: issued, last_seen, csrf, token_fp}` in an in-memory dict.
  - Limits: at most 64 sessions, 30 min idle, 12 h absolute.
  - The cookie is `toc_admin_sid`: `HttpOnly; Secure; SameSite=Strict; Path=/`, named `__Host-` when TLS is on.
  - `verify_token` accepts the header **or** a live session. A session
    whose `token_fp` (the first 16 hex of `sha256(token)`) no longer
    matches the current token is dead, which is what makes rotation work.
  - `POST /api/auth/logout` deletes the server record **and** the cookie.
  - A restart logs everyone out. That is acceptable and simpler than signed cookies with a denylist.
  - The local-unlock path issues the same session type, so the constant HMAC cookie goes away.
  - The JS stops storing the token after a successful session login. Keep
    "Remember on this browser" only while `admin_token_configured &&
    !https` (the LAN Pi profile), behind `WEB_ADMIN_ALLOW_REMEMBER=1`, and plan to remove it.
  - Bump `?v=` on `app.js` and `index.html` assets (AGENTS Dashboard Work).
- **Compatibility**: scripts keep `X-Admin-Token` unchanged (`toc-deploy`
  l.383). WebSocket auth also accepts the session cookie (same origin, `websocket.cookies`).
- **Rollback**: revert the module. Old clients holding a stored token keep working through the header.
- **Acceptance**:
  - `tests/test_webadmin_sessions.py`: login sets a cookie with
    HttpOnly/Secure/SameSite=Strict under https; the cookie authorizes
    `/api/auth/check`; logout makes the same cookie value fail with 403;
    idle and absolute expiry (monkeypatched clock); a token change
    invalidates existing sessions; the 65th session evicts the oldest; a
    wrong token gives 403 and creates no session; the response body never contains the token.
  - `tests/test_webadmin_api.py` still passes unchanged.

#### A3. CSRF protection for state-changing routes (S)

- **Exists**: `SameSite=Strict` on the local cookie. No Origin check on
  HTTP. Bodyless POSTs: `/api/backup`, `/api/shutdown`, `/api/update`, `/api/reload`.
- **Gap**: SameSite treats every port on a host as the same *site*. With
  local unlock on (native installs, `scripts/toc_common.sh` l.286), any
  page served from another localhost port can POST `/api/shutdown` with
  the cookie. Requests using only the header are CSRF-proof; cookie requests are not.
- **Proposal**: a middleware for POST/PUT/PATCH/DELETE. When the request is
  authenticated by cookie and not by `X-Admin-Token`, it requires (a) an
  `Origin`, or else `Referer`, equal to the request's own scheme://host or
  listed in `WEB_ALLOWED_ORIGINS`, and (b) a header
  `X-TOC-CSRF: <session csrf>` matching the session (A2; the value comes
  from `/api/auth/check`). Also require `Content-Type: application/json` on routes that take a body.
- **Rollback**: remove the middleware. It is purely additive.
- **Acceptance**: `tests/test_webadmin_csrf.py`. A cookie-only POST to
  `/api/shutdown` with a foreign Origin returns 403 and appends nothing to
  a temp queue file. The same POST without the CSRF header returns 403.
  With the matching Origin and header it returns 200 and writes one queue
  line. A header-token POST with no Origin returns 200 (the toc-deploy
  path). A `text/plain` body to `/api/command` returns 4xx.

#### A4. Rotation procedure, fingerprint and deploy hygiene (S)

- **Exists**: generation (`openssl rand -hex 32`; `toc-restore` l.165).
  Rotation guidance in prose only. The token appears in curl argv
  (`toc-deploy` l.381-384). `.env` is inside backups (`toc.sh` l.29/286).
- **Proposal**:
  1. Add `deploy/windows-vm/toc-admin-token rotate`, run as root. It
     generates the token on the host, writes `/etc/toc/web.env` via a
     temporary file and rename with mode 600 root, runs
     `systemctl restart toc-web`, and prints **only** the new fingerprint.
     The operator reads the token on the host with `sudo` as before.
     `toc-deploy` reads the file fresh on each run, so no overlap window is
     needed. Optionally, `WEB_ADMIN_TOKEN_PREVIOUS` plus `..._UNTIL=<epoch>`
     for at most 15 minutes, accepted by header only.
  2. Log `admin token fingerprint <fp>` once at startup to journald (not to
     `log/`, which is public), and return `token_fingerprint` from
     `/api/auth/check` so an operator can confirm which token is live.
  3. In `toc-deploy`, send the header from stdin: `printf 'X-Admin-Token: %s\n' "$token" | curl -H @- ...`
     (supported since curl 7.55; Ubuntu 24.04 ships 8.x).
  4. `toc.sh backup` writes `.env` with `WEB_ADMIN_TOKEN=` blanked plus a
     comment. Restore already keeps this installation's own `.env`
     (AGENTS "The Installers"), so nothing is lost. Mirror the change in `toc.ps1`.
- **Rollback**: revert. The format of the env file does not change.
- **Acceptance**:
  - `tests/test_admin_token_rotation.py` runs the script against
    `TOC_WEB_ENV=<tmpdir>/web.env` with a stub `systemctl`. It shows the
    file is rewritten atomically, 0600, holds a new 64-hex value, keeps the
    other keys byte for byte, and that nothing on stdout matches the token.
  - Extend `tests/test_deploy_failures.py`: a stub `curl` records its argv,
    and the argv never contains the token string.
  - `tests/test_restore_backup.py` (exists): the archived `.env` has an empty token.

#### A5. Request ids and an admin audit journal on the dashboard side (S)

- **Exists**: none. `/api/*` POSTs return `"queued"`.
- **Proposal**: middleware that assigns `X-Request-ID`. It accepts the
  client's value only if it matches `[A-Za-z0-9._-]{8,64}`; otherwise it
  generates `uuid4().hex`. The id is echoed in the response header.
  - Every protected route (reads included) appends one line to
    `admin-audit.tsv` in `$STATE_DIRECTORY` (systemd sets it through
    `StateDirectory=toc`; fallback `/var/lib/toc`, and in Docker
    `/app/backups/..`). **Never under `log/` or `player/`**, both of which are synced to the public repository.
  - Columns: `epoch, request_id, method, route, auth_kind (header|session|local), token_fp, peer_class
    (loopback|proxied|direct), status, result`.
  - Never the token, never the body. For an announce or command, only its length and a sha256 prefix.
  - The file is trimmed by temp file and rename (AGENTS "Nothing the game keeps is rewritten in place").
- This is the "outcome tracking" anchor for section 2.
- **Acceptance**: `tests/test_webadmin_audit.py` shows one row per call;
  no row contains the token (header and session paths both); a client id
  is echoed; an invalid client id is replaced; a failed `verify_token` is
  logged with status 403 and `auth_kind=-`; the file is created 0600.

#### A6. Small extras (S each, optional)

- Per-peer backoff on failed token checks: 10 failures a minute gives 429,
  in memory only. A 256-bit token cannot be guessed; this is about log noise.
- Tighten CSP `connect-src` to `'self'` plus the explicit `wss://host` once A1 lands.
- Run uvicorn with `--no-access-log`, or a filter that drops query strings
  (`/api/channels?search=` carries player chat text).

#### A7. AI-assisted investigation without production credentials (M)

- **Principle**: an assistant never needs `WEB_ADMIN_TOKEN`, SSH,
  `/api/command`, write access to the queue, or unrestricted reads of
  `player/`. It works from git (synced state) and from redacted exports.
  Changes go by push. Restores go by `area/restores.dat`, which is receipted in the ledger and reviewed in the commit.
- **Proposal**:
  1. `tools/incident_export.py --since T --until T [--player Z...]`
     (read-only) bundles a window of `log/toc.log`, `log/play.tsv`,
     `log/progress.tsv`, `log/crash.log`, `log/webadmin-events.tsv`, the
     ledger records for the window, `log/deployed-commit`,
     `log/auto-deploy.status` and the `admin-audit.tsv` rows for the window (A5). Redaction:
     - Every IPv4/IPv6 address becomes `addr-<hmac8>`, keyed per export so exports cannot be joined.
     - No `Pass` line, no `$6$`/DES hash, no tells.
     - Rooms are dropped where the logs already hide them (`-`).
     - It refuses any input path outside the repository's `log/`, `player/recovery/` and `area/`.
     - It writes a manifest of what was included and what was redacted.
  2. A fixed diagnostic set, modelled on the Oracle's live query: each
     check reads and reports, and none calls `interpret()`. Examples: queue
     depth, pending ledger ids, stuck corpses, the counts from `DNS GUARD`.
     It is produced as a file the state sync carries, so a cloud session
     reads it from git. Avoid a new HTTP endpoint for AI use.
- **Acceptance**: `tests/test_incident_export.py` builds synthetic logs with
  Z fixtures and TEST-NET addresses in a temporary directory. It shows: no
  address survives (regex scan); the same address maps to the same alias
  within one export and to a different alias in the next; hash-shaped
  strings are absent; paths outside the allowlist are refused; the manifest lists every source file.

---------------------------------------------------------------------------

### 2. Trackable, retry-safe administrative requests

The design reuses what exists:
- the queue file, with its lock and one line per action;
- `recovery_record` for anything touching a player;
- `prestore_give`'s "pending plus a mark in the file means it landed" reconciliation.

It adds no second receipt system for player state. Non-player actions
(announce, fsave) get a small results file, because the ledger lives under `player/` and should stay about players.

States, used the same way in all three places:

| state | written by | meaning |
| --- | --- | --- |
| accepted | dashboard or deploy (journal, A5) | validated and appended to the queue |
| started | game (results file, before running) | consumed from the queue; execution begun |
| completed / failed / refused | game (results file) | outcome known; refused = validation or authority |
| uncertain | dashboard (derived) | started and no outcome, then the game restarted; or accepted, queue empty, and no started row after a restart |
| pending / committed / abandoned | recovery ledger | player-state operations only, as today |

#### R1. Queue line v2 with request id, source and op (S, C plus Python)

- **Exists**: `action|args` (`comm.c` l.5105). The writer is `QueueWriter.append`.
- **Proposal**: lines starting with `v2|` are `v2|<rid>|<source>|<op>|<args...>`.
  - `rid` matches `[a-z0-9-]{8,40}`.
  - `source` is one of `dashboard`, `deploy` or `host`. It is
    **self-declared, because file write access is administrative access**
    (`SECURITY.md` "Local Command Queue"), so it is recorded as a claim.
  - Unprefixed lines keep today's behaviour exactly, so an old
    `toc-deploy` and a new game work together, and the reverse.
  - The C side parses with the existing strtok and rejects a bad rid with a `bug()`.
  - The Python writer adds rid and source. `toc-deploy`'s `queue_append` emits v2 lines with rid `deploy-<epoch>-<n>`.
- **Compatibility**: the v2 parser is only reached for lines beginning `v2|`, which no current writer produces.
- **Builds**: Make (gnu89) and CMake (c17). Uses only `snprintf` and `toc_strlcpy`.
- **Acceptance**:
  - `tests/test_web_queue_v2.py` (live, `LiveMud`, fixture world) writes v1
    and v2 lines under `fcntl` and shows both execute (announce visible to a Z fixture client via `sync`).
  - A bad rid is ignored and logged.
  - A `|` in a v2 rid is refused.

#### R2. A game-side results file with started/outcome rows (M, C)

- **Exists**: `write_web_admin_event` (`comm.c` l.5280); `temp_file_commit` for whole-file rewrites (`save.c`).
- **Proposal**: `area/webadmin.results`, tab-separated: `epoch rid source op state code boot_id revision detail`.
  - Not under `log/`, so it is not published. Add it to the `sync_code`
    exclude list in `toc-deploy` beside `area/webadmin.queue` (l.109), to
    `tests/test_deploy_install.py`'s expectations, and to the copy filter
    in `tests/live_mud.py`. Do **not** add it to `STATE_FILES`.
  - A `started` row is appended and flushed before each v2 action runs. An
    outcome row follows: `completed`, `failed:<code>` or `refused:<code>`.
  - `boot_id` is the game's start epoch. `revision` is the first 12 characters of `.code-revision`, read once at boot.
  - The file is trimmed past N lines to the newest M with `<file>.tmp` and `temp_file_commit`.
  - At boot the game reads the last M rids into a set, so the same rid is
    never run twice (answer `refused:duplicate`).
  - Since lines are still truncated before execution (l.5220), the
    `started` row is what turns a silent loss into a visible `uncertain`.
- **Outcome codes per op**:
  - `announce` -> completed;
  - `wizinfo` -> completed or `refused:level`;
  - `backup` -> completed (archive launched; the archive's own result is already in toc.log);
  - `shutdown` -> completed;
  - `command` -> `completed:unverified`. The stand-in's output is
    discarded, so the game can only say it ran. This is the main argument for R4.
- **Rollback**: revert. The file is a side output, and v1 lines are unaffected.
- **Acceptance**:
  - `tests/test_web_queue_results.py` (live) checks: each v2 op gives a
    started row then an outcome row with the same rid; a duplicate rid is
    refused without running (the announce is seen once); `boot_id` changes across a restart.
  - A crash test uses `TOC_FAULT_FILE` with a new point `webqueue-after-start`,
    which aborts after the started row. On reboot the rid shows started with no outcome.
  - Trimming keeps whole lines (a `/dev/full` failure leaves the old file, the same technique as `test_audit_saves`).
  - Add `test_web_queue_results` to `SANITIZE_MODULES` (new C parsing).

#### R3. The dashboard shows queued and executed apart (S, Python plus JS)

- **Proposal**: every queuing route returns `{"request_id": rid, "state": "accepted"}` with HTTP 202. Today's body
  is the string `"queued"`, so keep a `?legacy=1` or `Accept`-based
  fallback for one release, because `app.js` shows a toast on success (l.2036, 2172, 2188).
  - `GET /api/requests[?rid=]` (protected) joins the audit journal (A5)
    with `area/webadmin.results` and derives the state from the table above.
  - It derives `uncertain` from boot ids: the newest `boot_id` seen in the
    results file, compared with the request's acceptance time.
  - The UI polls a request for 30 s and shows "Queued" -> "Running" ->
    "Done", "Failed" or "Uncertain: check the game".
  - Returns no payload text, the same rule as `/api/admin/status`.
- **Acceptance**: `tests/test_webadmin_requests.py` with synthetic
  results files covers accepted only; started; completed; started then a
  newer boot_id (uncertain); and accepted with an empty queue then a newer
  boot_id (uncertain). It also checks auth (none/wrong/right token), that
  no payload text appears, and that a malformed results line is skipped.
  `tests/test_web_help_and_paging.py`-style JS checks the toast wording.

#### R4. Typed, validated operations instead of free command strings (M)

- **Exists**: `/api/command` takes any string of at most 255 characters
  and runs it at trust 70 (l.3550). Typed ops today: announce, wizinfo, backup, shutdown.
- **Proposal**: add typed ops. Each one is validated in Python and in C
  and **does not go through `interpret()`**. Each calls the same function
  the in-game command uses, so behaviour cannot drift ("Views share the
  predicates", AGENTS 2026-10-22 gameplay review).
  - `fsave` (`do_forcesave` body), used by `toc-deploy`.
  - `who-count` (read-only).
  - `freeze-trades-status <Name>` (read-only).
  - `prestore-list <Name>` (read-only; the result row carries a count, not contents).
  - Later, ledger-backed `restore <Name> gear|stash <stamp>` (R5).
  - Names are 2-12 letters (`prestore_name_ok`). Targets are resolved with
    `player_in_game`/`offline_player_load` as PRESTORE does.
    `rank_protects` is checked with the stand-in's trust 70, so CR and creator protections are unchanged.
  - `/api/command` stays, labelled "free command (unverified result)".
    Owner decision: keep it or put it behind `WEB_ADMIN_FREE_COMMANDS=1`.
    `toc-deploy` would switch to the typed `fsave` op.
- **Compatibility**: the WebAdmin stand-in stays at `MAX_LEVEL`. No CR command becomes reachable.
- **Acceptance**: `tests/test_web_typed_ops.py` (live). `fsave` writes a Z
  fixture's file (the mtime moves; check with `TOC_FAULT=autowrite` so
  only this save writes). A bad name is refused before the queue (400) and
  in C (`refused:name`). A target that `rank_protects` refuses gives
  `refused:rank`. `who-count` matches the MSSP probe. No typed op appears in `log/play.tsv` as a typed command.

#### R5. Ledger-backed restores from the dashboard, reusing the recovery ledger (M, later)

- **Exists**: `prestore_give` (`act_wiz.c` around l.11240-11400) with
  `pending -> objects -> mark -> save -> committed`, retry-by-mark and
  `abandoned`. `restores.c` handles git requests the same way.
- **Proposal**: the typed `restore` op calls the same `prestore_gear`/`prestore_stash` core with `op = "web:<rid>"`.
  - `actor` = `webadmin/<source>`. No person is named; see the preamble.
  - `detail` adds `rev=<12>` (code revision) and `via=<auth_kind>` taken
    from the queue line. This is the "source, effective authority, target,
    result, revision" record, all inside existing columns, so **the ledger
    format does not change**. The FNV check and old readers are unaffected.
  - Idempotency comes free: `recovery_request_state("web:<rid>")` committed
    -> `refused:already-committed`; pending plus mark ->
    save-then-commit, as l.11251 does; pending without the mark at login
    -> abandoned by `recovery_reconcile_login` (an id with a colon is already its domain).
  - A dashboard retry must reuse the same rid. A new rid is a new restore, and the UI says so in words.
- **Acceptance**: `tests/test_web_restore_ledger.py` (live; Z fixture with
  planted snapshots, as `tests/test_prestore.py` does). One request gives
  objects once. Repeating the same rid gives nothing more (count objects).
  `TOC_FAULT_FILE=prestore-save` gives pending, then a retry with the same
  rid gives committed with nothing duplicated. A crash after the mark and
  before commit is settled at login as committed. A rid naming a snapshot
  that does not exist gives `rejected`. The ledger lines verify with the
  existing reader (`recovery_boot`). Also in `SANITIZE_MODULES`.

#### R6. Retry and crash semantics per operation (documentation plus tests)

| op | idempotent? | retry rule | crash between started and outcome |
| --- | --- | --- | --- |
| announce / wizinfo | no (seen twice) | only from accepted or uncertain, by an operator's choice; same rid refused if started | uncertain; the operator checks the channel journal |
| fsave | yes | always safe; dashboard may auto-retry once | uncertain is harmless; the next autosave covers it |
| backup | yes (archive lock, `update.c` l.224) | safe | the archive's own toc.log line says whether it finished |
| shutdown | yes | safe | completion = a new boot_id or health down |
| update (touch file) | yes | safe | the host updater's own status |
| command (free) | unknown | **never auto-retried**; the UI requires a new rid and a confirmation | stays uncertain |
| restore (R5) | via ledger | same rid only; never re-gives | pending -> login/boot reconcile (existing) |
| deploy's announce/fsave | as above | the deploy never retries; it proceeds after its sleeps (l.399-411) | unchanged behaviour |

The queue stays at-most-once. Making it at-least-once (copying the file
aside, executing, then truncating) would replay announces and free
commands after a crash. With rid dedupe in R2 that would be safe, but it is listed under WAIT.

#### R7. Decisions to put to the owner (no code without a yes)

- The `shutdown` queue action (`comm.c` l.5157) goes around `CR` SHUTDOWN.
  Options: keep it (the shared token is the host's authority), or require
  `WEB_ADMIN_ALLOW_SHUTDOWN=1`. `toc-deploy` does not use it; it uses
  `systemctl stop`, so either answer leaves deploys unchanged.
- Whether `/api/command` stays enabled in production once R4 covers fsave.

---------------------------------------------------------------------------

### 3. Reproducible dependencies and release provenance

#### D1. Hash-checked lock files for the dashboard (S)

- **Exists**: floating ranges (0.4). `anthropic` is installed by hand.
- **Proposal**:
  - `webadmin/requirements.in` holds today's three ranges plus
    `anthropic` (optional at run time but always installed, so a venv
    rebuilt from the lock does not silently drop the Oracle).
  - `webadmin/requirements.lock` is generated by `uv pip compile --universal --python-version 3.12 --generate-hashes`.
    Universal matters: `uvicorn[standard]` pulls `uvloop`, `httptools` and
    `watchfiles` under platform markers, and pip-compile drops markers that do not apply on the machine it runs on.
  - Test-only: `scripts/requirements.in` and `scripts/requirements-test.lock` (`httpx2`, `watchdog`), with the same
    flags and `-c webadmin/requirements.lock` so the shared transitives agree.
  - Python 3.12 is what Ubuntu 24.04 ships for aarch64 production, x86_64
    CI and Docker. macOS dev on 3.12 or 3.13 can install the same lock if
    wheels exist for both: pydantic-core, uvloop and httptools all publish
    macOS arm64/x86_64 and Linux aarch64/x86_64 wheels. Check once with
    `uv pip install --dry-run --python-platform aarch64-manylinux_2_39`,
    `x86_64-manylinux_2_39` and `aarch64-apple-darwin`.
  - Keep `requirements.txt` as a one-line `-r requirements.lock` shim, so
    `toc_native.sh`, the Dockerfile and old docs keep working. Install
    everywhere with `pip install --require-hashes --no-deps -r ...lock`.
- **Compatibility**: pins today's resolved versions, so no behaviour
  changes. `anthropic` adds about 10 transitive packages to the image.
- **Rollback**: point `requirements.txt` back at the ranges.
- **Acceptance**: `tests/test_dependency_lock.py` (pure Python, no
  network) checks: every non-comment line in each lock is `name==ver` with
  at least one `--hash=sha256:`; every top-level name in `.in` appears in
  its lock; no `-e` or URL requirements; `requirements.txt` only includes
  the lock; and the test lock's shared packages equal the runtime lock's
  versions. CI's `classify.py` already treats `requirements*.txt` and
  `webadmin/requirements.txt` as full-suite paths (l.82). Add
  `**/requirements*.lock` and `*.in` to the same list, in the same commit.

#### D2. Same lock in CI, Docker, native install and production deploy (M)

- **Exists**: CI installs ranges (`validate.yml` l.338, 413). Docker
  installs ranges. `toc-deploy` installs nothing. `toc-restore` installs `|| true`.
- **Proposal**:
  - CI: `pip install --require-hashes --no-deps -r webadmin/requirements.lock -r scripts/requirements-test.lock`.
    Key the cache on the lock files.
  - Dockerfile: the same command in the `python` stage.
  - `toc_native_venv`: hash the lock, not `requirements.txt` (l.94).
  - `toc-restore`: drop the `|| true`; a failed install is a failed restore step that says so.
  - **`toc-deploy`: versioned venvs.**
    - Compute `lockhash = sha256(webadmin/requirements.lock)` in the build tree.
    - If `/srv/toc/venvs/<lockhash>/.ok` is missing, build it **before the
      game is stopped**, next to the dry-run checks: `python3 -m venv`, install with `--require-hashes --no-deps`, run
      `python -c "import webadmin.server"` with the build tree on `PYTHONPATH`, then touch `.ok`.
    - A failure here stops the deploy with the game untouched, exactly like a build failure (l.359-363).
    - At install, point the symlink `/srv/toc/venv` at it with `ln -sfn` plus rename. `toc-web.service`'s
      `ExecStart=/srv/toc/venv/bin/python` (l.21) does not change.
    - Keep the venvs the three snapshots reference and delete the rest.
- **Compatibility**: the first deploy builds a venv; this needs network to
  PyPI, which the host has. `ProtectSystem=strict` in toc-web reads the
  venv only. `/srv/toc/venv` stays a usable path.
- **Rollback**: the old symlink target is still on disk (D3).
- **Acceptance**: extend `tests/test_deploy_install.py` and
  `tests/test_deploy_failures.py` (stub `python3 -m venv` and `pip`,
  synthetic trees in a temporary directory). An unchanged lock builds no
  venv. A changed lock builds it before any stub `systemctl stop` is
  recorded. A failing pip leaves the game running, exits non-zero and
  leaves the symlink unchanged. Venvs not referenced by a kept snapshot are pruned.

#### D3. Rollback restores the Python environment too (S, after D2)

- **Exists**: snapshot identity `.snapshot-revision` = `<commit> <merc sha256>`, verified by `code_identity` (l.157).
- **Proposal**: the snapshot also records `.snapshot-venv` = `<lockhash>`,
  the live tree `.code-venv`. Both are added to `sync_code`'s
  `--exclude` list beside `.code-revision` (l.106). `rollback()` re-points
  `/srv/toc/venv` to the snapshot's lockhash if that venv still has `.ok`.
  Otherwise it records `venv unknown` and leaves the symlink, and toc-web
  may fail health. That is the same "unknown, wait for a person" rule as code identity.
- **Acceptance**: `tests/test_deploy_rollback_identity.py` (exists, real
  trees) gets three cases: rollback to a snapshot with a different lock
  re-points the symlink; a legacy snapshot without `.snapshot-venv`
  leaves the symlink and logs unknown; a missing venv directory leaves the symlink and logs unknown.

#### D4. Record build provenance with every install (S)

- **Proposal**: `toc-deploy` writes `.build-info` in the live tree (and
  `.snapshot-build-info` in snapshots, excluded from `sync_code`), one `key=value` per line:
  - `commit`, `merc_sha256`;
  - `cc=$(cc --version | head -1)`, `arch=$(uname -m)`;
  - `libc=$(ldd --version | head -1)`;
  - `cflags_sha256` of `make -pn | grep '^CFLAGS'`;
  - `python=$(venv/bin/python -V)`, `lock_sha256`;
  - `venv_freeze_sha256` of `pip freeze --all`;
  - `built_utc`. It is written with `put_file` (l.171). `record_deployed` appends
  `lock=<12>` to `log/deployed-commit`. That line already carries an
  optional trailing "why", so readers that split on the first space are
  unaffected; check the parser in `toc-auto-deploy` and `toc-game-recovery`.
  - Fix the dashboard default path: in `/etc/toc/web.env` set
    `TOC_DEPLOYED_COMMIT_FILE=/srv/toc/current/log/deployed-commit`, or
    change the default in `server.py` l.171 to try `log/deployed-commit` under the repository root first.
- **Acceptance**: the deploy tests assert `.build-info` holds every key,
  that `merc_sha256` equals the binary's, that it is excluded from
  `sync_code` both ways, and that `log/deployed-commit` stays parseable by
  `toc-auto-deploy` (`tests/test_auto_deploy.py`).

#### D5. Pin GitHub Actions to SHAs; Dependabot for actions, pip and Docker (S)

- **Proposal**:
  - Replace every `uses: x@vN` with `x@<40-hex> # vN.M.P` in both workflows.
  - Move `docker-image.yml` to `runs-on: ubuntu-24.04` like `validate.yml`.
  - Add `.github/dependabot.yml`:
    - `github-actions`, weekly, grouped;
    - `pip` in `/webadmin` and `/scripts` (Dependabot updates pip-compile
      and uv style locks with hashes), weekly, grouped minor/patch, security updates immediately;
    - `docker` for the Dockerfile base, after pinning `ubuntu:24.04@sha256:...` in `ARG BASE_IMAGE`; compose's
      `TOC_BASE_IMAGE` override still works.
  - Dependabot PRs go through the full suite, since `.github/**` and the
    lock files classify as full. A person reviews and merges; there is no auto-merge.
- **Compatibility**: the `deploy-gate` job name is unchanged
  (`toc-auto-deploy` reads it). Pinning changes no behaviour.
- **Acceptance**: `tests/test_workflow_pinning.py` parses both workflows
  with a regex and fails on any `uses:` not followed by a 40-hex SHA and a
  version comment, and on any `runs-on: ubuntu-latest`. Also add it to
  `classify.py` so a workflow change runs it (workflows already classify as full).

#### D6. Vulnerability checks, outside the deploy gate at first (S)

- **Proposal**: a new workflow, `deps-audit.yml`. It runs on push or PR touching the lock files and nightly.
  - `pip-audit --require-hashes --disable-pip -r webadmin/requirements.lock` and the test lock.
  - `osv-scanner --lockfile=requirements.txt:webadmin/requirements.lock`.
  - `osv-scanner` on the published image's SBOM (D7).
  - Report to the step summary. It is **not** wired into `deploy-gate`, so
    the auto-deployer's contract and the CI budget are untouched. Promote
    it to gating only after a month without noise, by owner decision.
  - The C side has no vendored libraries. libcrypt and zlib come from
    Ubuntu; the host's `unattended-upgrades` status belongs in the host checklist, not CI.
- **Acceptance**: the workflow passes on the current lock, or lists real
  findings for review. A planted test lock that pins a known-vulnerable
  version (in a temporary directory in the workflow's self-test step) makes `pip-audit` exit non-zero.

#### D7. SBOM and provenance per release (M)

- **Proposal**:
  - Image: `docker/build-push-action` with `sbom: true` and
    `provenance: mode=max` (BuildKit attestations attached to the GHCR manifest, so they need no extra storage).
  - Host releases: `toc-deploy` writes `/srv/toc/releases/<commit>/sbom.cdx.json`. It is produced by
    `cyclonedx-py environment /srv/toc/venvs/<lockhash>/bin/python`; that
    tool is installed from the test lock into a separate tools venv, never
    into the runtime venv. Add a small hand-made component list for `merc`
    (commit, sha256, cc, and libcrypt/zlib versions from `dpkg-query -W`) and copy `.build-info` there.
  - Keep the release directories for every kept snapshot plus the newest
    10. They are not synced to git, because they hold host details.
- **Rollback**: purely additive. Skip SBOM generation if the tool is missing (warn; never fail a deploy for it).
- **Acceptance**: the deploy test with a stub `cyclonedx-py` shows the
  file is written per commit, pruned with snapshots, and a failure is
  only a warning. In CI, `docker buildx imagetools inspect --format '{{json .SBOM}}'`
  is non-empty after a dispatch run, checked by hand once.

#### D8. Optional: deploy the CI-tested binary instead of a host build (WAIT, see below)

---------------------------------------------------------------------------

### 4. Things that should WAIT (complexity outweighs value now)

- **At-least-once queue delivery** (copy aside, execute, then truncate).
  It needs R2's rid dedupe everywhere first, and it replays free commands.
  The at-most-once loss window is one pulse and is now visible as `uncertain`.
- **Capturing free-command output** through a fake descriptor for the
  stand-in. Descriptor lifetime rules (`close_socket`, the pager,
  `write_to_buffer` on a NULL outbuf) make it risky. Typed ops (R4) give real outcomes for the actions that matter.
- **Signed stateless cookies with a revocation list**: the in-memory
  sessions in A2 are simpler, and a restart logging people out is fine.
- **Mutual TLS or a VPN in front of the dashboard**: worth it only if the
  token alone proves insufficient after A1-A3. It would also complicate `toc-deploy`'s loopback curl.
- **Shipping CI's binary to the host**: CI builds x86_64, production is
  aarch64. It would need an arm64 runner plus reproducible-build flags and
  an artifact handoff to `toc-auto-deploy`. Record host build provenance (D4) instead.
- **Fully offline wheelhouse installs on the host**: only needed if PyPI
  reachability becomes a deploy risk. D2 fails safe with the game untouched.
- **Making `deps-audit` gate deploys**: wait for a month of signal (D6).
- **A dashboard UI for every PRESTORE form** (`full:` restores, corpses).
  Keep those in game, where `rank_protects` and the interactive
  confirmations already live. R5 covers gear and stash only.
- **macOS CI jobs for the lock**: the dry-run platform checks in D1 cover most of the value at no runner cost.

---------------------------------------------------------------------------

### 5. Suggested sequencing (each a separate commit or PR)

1. D1 lock (S) and D5 pinning plus Dependabot (S): no runtime change.
2. A4 deploy-hygiene part 3 (token off argv) and A5 audit journal (S).
3. A1 TLS proxy plus `WEB_ADMIN_REQUIRE_TLS` (M), then A2 sessions (M), then A3 CSRF (S).
4. D2 versioned venvs, then D3 venv rollback, then D4 build-info.
5. R1 v2 queue lines, then R2 results file (needs both builds plus the sanitizer), then R3 dashboard states.
6. R4 typed ops (switch `toc-deploy` to typed fsave), then R5 ledger-backed restores.
7. D6 audit workflow, D7 SBOMs, A7 incident export; A6 extras as time allows.

Verification for every step: build both trees for any C change (`make`
gnu89; `cmake --build build` c17). Run the named module with
`scripts/test-parallel.sh <module>`. Fixtures are synthetic Z-named
characters in disposable worlds (`LiveMud(fixtures=True)`), and addresses
come from TEST-NET ranges. Never use a real player file. Run `git diff --check`. Let CI's planned suite run the rest.

## Appendix 2: Fuzzing And Hardening, Incident Cases, Recovery Verification (F, H, I, V)

Read-only assessment of `/home/user/toc2026` on branch `fix-review-20261109` (2026-11-09; the
working tree carries another engineer's uncommitted edits to `src/comm.c`, `src/loginlock.c`,
`src/lockwindow.[ch]`, `CMakeLists.txt` and tests -- citations below are to the tree as it stood).
Nothing in the repository was changed. Experiments were run on a copy of `src/` in the session
scratchpad (`.../scratchpad/hard`, `.../scratchpad/fuzzproto`).

Ground rules this roadmap keeps: gameplay, save format, staff ranks, wizinvis hiding, the recovery
contracts (`DURABLE_*`, receipts, PRESTORE), the deploy model (`toc-deploy`, `toc-auto-deploy`,
deploy-gate) and the owner's plaintext public state sync are unchanged. The shared admin token
stays; no per-staff accounts, no MFA. Every item is one reviewable change. Fixtures are synthetic
and Z-named; worlds are disposable (`LiveMud`, temp dirs). "Both builds" means `make` (gnu89) and
`cmake` (strict C17).

---

### 0. Findings made while assessing (evidence first)

| # | Finding | Evidence | Severity |
|---|---------|----------|----------|
| A1 | The single-module C harnesses run **without sanitizers** (only the list iterator gets ASan/UBSan). | `tests/test_mccp.py` setUpClass, `tests/test_guard_addresses.py`, `test_holiday_rules.py`, `test_combat_rules.py`, `test_password.py`, `test_text_fold.py`, `test_review_nov09.py` compile with plain `cc`; `scripts/validate.sh:84` is the one `-fsanitize=address,undefined` | medium (cheap win) |
| A2 | Ubuntu 24.04 **gcc** already hardens by default; **clang does not**. Measured on x86_64: default `make` with gcc 13.3 gives PIE, full RELRO + BIND_NOW, `__stack_chk_fail`, 12 `__*_chk` imports, IBT/SHSTK notes -- identical to an explicit-flag build. Default `make CC=clang` (clang 18) gives PIE but **no BIND_NOW, no FORTIFY (0 `_chk`), no stack protector, no CET note**. CMake Release with gcc matches the gcc default. | `readelf -hlWdn`, `nm -D` on three scratch builds | medium: any macOS/clang/other-distro build is unhardened, and nothing checks production's |
| A3 | Explicit flags `-D_FORTIFY_SOURCE=3 -fstack-protector-strong -fstack-clash-protection -fcf-protection=full -fPIE -Werror=format-security` + `-pie -Wl,-z,relro,-z,now,-z,noexecstack` compile the whole tree cleanly with gcc and clang (0 errors). Clang emits 3 benign warnings (`disaster.c:75` string concatenation that is intended, misleading indentation at `handler.c:4368`, `save.c:1441`). | scratch `build.log`, `clang.log` | info |
| A4 | libFuzzer is not linkable on this image: `clang -fsanitize=fuzzer` fails for want of `libclang_rt.asan-x86_64.a`. CI must install `libclang-rt-18-dev`. `-fsanitize=fuzzer-no-link` compiles fine. | scratch link error | info |
| A5 | A telnet fuzz harness needs **no extraction**: `tests/test_mccp.c` already links `src/telnet_proto.c` alone against `merc.h` with four stubs. A prototype split-invariance harness (gcc ASan/UBSan, 30,000 random inputs with telnet bytes weighted) ran clean in 0.5 s. A netaddr round-trip prototype ran 400,000 inputs clean. | `.../scratchpad/fuzzproto/fuzz_telnet.c`, `fuzz_netaddr.c` | info |
| A6 | `login_lock_boot` (`src/loginlock.c`) reads with `char line[256]` and on an over-long line `continue`s **without draining it**, so the remainder of that line is parsed as a record of its own. `guard_store_load` (`src/guardstore.c`) drains (`getc` to newline, `bad_lines++`). `recovery_boot` (`src/recovery.c`, `line[MAX_STRING_LENGTH*2]`) does not drain either; an 11-column remainder still needs a matching FNV, a 10-column legacy remainder does not. Neither file is written over-long by the game, so this is a hand-edit/corruption robustness gap, exactly what a fuzz target reports. | source | low |
| A7 | Play-journal rows `cmd`, `refused`, `death`, `session`, `report`, `anomaly`, `bug` are written with the actor's name even when the actor is wizinvis: `playlog_end` -> `journal_write(kind, ch, ...)`; `play_note` (`src/interp.c:1088`) has no wizinvis test. Only `outcome`, `state`, `craft`, `item` substitute `NULL` (`src/playlog.c:614,638,703,1401`). `log/` is public. Verify on a live fixture before acting; the owner decides whether staff rows belong in the journal at all. | source | medium (invisibility contract) |
| A8 | The encrypted off-host backup keeps **one** archive and **force-pushes** it (`deploy/sync-player-backup.sh`: `git push --force`, "This branch holds only the latest archive"). The host's deploy key can therefore erase the only encrypted copy, and a bad archive replaces the last good one. `wiki/player-backups.md` "Not yet" already lists a versioned private vault as a proposal. | source, wiki | high for disaster recovery |
| A9 | `toc-daily-backup` is named in `AGENTS.md` and `wiki/new-machine-setup.md:103` but its source is not in the repository (`git grep` finds no script). The in-game archive (`backup_launch`, `src/update.c:268`) tars `../player` only -- not `corpse/` -- onto the same host, 30-day retention, verified only by `gzip -t`/`tar tzf`. | `git grep`, source | medium |
| A10 | No boot id and no code revision are recorded anywhere the journal can join to. The banner is "ROM is ready to rock on port N" (`src/comm.c:580`); `boot_time_stamp` exists (`comm.c:318`) and is only exported over MSSP. The live revision exists only outside the game (`log/deployed-commit`, `.code-revision`). | source | medium for incidents |
| A11 | `log/player_addresses.tsv` and `log/logins.tsv` are tracked and synced publicly. This is inside the owner's stated policy; it means every export tool must strip addresses itself (as `tools/log_report.py:clean` does), never rely on the inputs being clean. | `git ls-files log` | policy note |

---

### 4. Fuzz testing and release-build hardening

#### What exists

- ASan/UBSan CMake build, world load, 45 s idle, and `SANITIZE_MODULES` (19 live modules, 3 shards)
  against it: `.github/workflows/validate.yml` jobs `build-sanitize`, `sanitize-tests`;
  `LiveMud.__exit__` fails a test on any sanitizer report.
- Pure modules with no `merc.h`: `netaddr.c`, `guardstore.c`, `lockwindow.c`, `holiday_rules.c`,
  `combat_rules.c`, `text_fold.c`, `password.c`, `dnsasync.c`. Harnesses: `tests/test_*.c` built by
  their Python module.
- Harness that links a game module alone with stubs: `tests/test_mccp.c` + `src/telnet_proto.c`.
- Fault injection for writers (`-DGUARD_STORE_FFLUSH`, `TOC_FAULT*`).
- Hardening: none stated in `Makefile` (`CFLAGS ?= -std=gnu89 -O2 -fcommon -DROM -Dunix`) or
  `CMakeLists.txt` (warnings only). Production is built by plain `make` in
  `deploy/windows-vm/toc-deploy:359` on Ubuntu 24.04 aarch64 gcc, so it inherits the distro defaults
  (A2) -- unverified on aarch64.

#### F0. Sanitize the existing single-module harnesses -- S

- Gap: A1. A heap overflow in `guardstore.c` or `telnet_proto.c` under the harnesses would pass
  silently today.
- Proposal: one helper in `tests/` (e.g. `tests/c_harness.py`: `build_harness(sources,
  extra_flags)`) that adds `-g -fsanitize=address,undefined -fno-sanitize-recover=all` when a probe
  compile succeeds, and sets `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1` for the run. Switch the
  seven modules to it one commit at a time (behaviour identical when the probe fails, e.g. macOS
  without ASan runtime).
- Files: `tests/c_harness.py` (new), the seven `tests/test_*.py` callers.
- Deps: none. Compat risk: a harness that was quietly wrong now fails -- that is the point; fix the
  code, not the flag.
- Rollback: revert the helper; callers fall back to their old command.
- Acceptance: `scripts/test-parallel.sh test_mccp test_guard_addresses test_holiday_rules
  test_combat_rules test_password test_text_fold test_review_nov09` passes; a deliberately planted
  one-byte overflow in a scratch copy of `netaddr.c` makes `test_guard_addresses` fail with an ASan
  report (shown in the PR description, not committed).

#### F1. Fuzz infrastructure -- S/M

- Proposal, layout:
  - `tests/fuzz/<target>.c` -- defines `LLVMFuzzerTestOneInput` only.
  - `tests/fuzz/standalone_main.c` -- `main` that replays every file or directory given (and, with
    `-n N -s SEED`, N pseudo-random inputs biased by the target's dictionary). Compiled only when
    `TOC_FUZZ_LIBFUZZER` is not defined, so the same target builds three ways: libFuzzer (`clang
    -fsanitize=fuzzer,address,undefined`), AFL++ (`afl-clang-fast -fsanitize=fuzzer`, which links
    AFL's libFuzzer-compatible driver), and gcc/Apple clang + ASan/UBSan replaying corpora.
  - `tests/fuzz/seeds/<target>/` -- small synthetic seeds (committed, a few KiB each);
    `tests/fuzz/<target>.dict` -- tokens (`IAC SB`, `PROXY TCP4 `, `"Core.Supports.Set"`, tab,
    `\\u`); `tests/fuzz/regress/<target>/` -- minimized crashers, committed with the fix.
  - `scripts/ci/fuzz.sh <target> <seconds>` -- builds and runs one target with `-max_total_time`,
    `-max_len` (per target), `-timeout=5`, `-rss_limit_mb=2048`, `-dict`, a corpus directory
    restored from `actions/cache` (key per target, never committed), then `-merge=1` to keep the
    cache small.
  - `tests/test_fuzz_corpora.py` -- builds every target with the standalone main (gcc + ASan/UBSan
    via F0's helper) and replays `seeds/` and `regress/`; runs in ordinary CI shards in seconds, so
    regressions are held on every PR even where libFuzzer is absent.
- CI (`validate.yml`): a `fuzz` job, `needs: plan`, run when the plan is full or any fuzzed source
  or `tests/fuzz/**` changed (add `tests/fuzz/**` to `scripts/ci/classify.py`; unnamed paths already
  fall to "full", which is safe). Matrix of two runners, targets split between them, **60 s per
  target** on PR/push (about 4 minutes wall, beside the 6-8 minute shards, so the run does not
  lengthen); **10 minutes per target** on the nightly `schedule` and a manual "fuzz" input. Install
  `clang libclang-rt-18-dev` through `scripts/ci/install_deps.sh`. A crash uploads the crashing
  input and the minimized one as an artifact and writes an annotation, the way the runner already
  announces failures. Make `deploy-gate` require the job only when the plan says it ran (same rule
  as other planned jobs); nightly failures do not block deploys of unrelated commits but do fail the
  nightly.
- Effort S for the skeleton + one target; M with CI wiring and gate change.
- Compat risk: gate wiring is the delicate part (`deploy-gate` is what `toc-auto-deploy` trusts).
  Ship the job first as **not required** for a week, then add it to the gate's needed set in its own
  commit.
- Rollback: drop the job; `tests/test_fuzz_corpora.py` still guards.
- Acceptance: on a PR touching `telnet_proto.c` the `fuzz` job runs each target 60 s and passes; a
  crash injected in a scratch branch produces an artifact with a reproducer and a failing gate;
  `tests/test_fuzz_corpora.py` passes under both gcc and clang locally.

#### F2. Telnet negotiation and subnegotiation target -- S (no extraction)

- Exists: `telnet_filter_input`, `telnet_handle_subneg`, `telnet_note_ttype`, MCCP start/finish
  (`src/telnet_proto.c`); stubs as in `tests/test_mccp.c`.
- Harness: first input byte picks a split size 1..64; feed the rest whole into one zeroed
  `DESCRIPTOR_DATA` and in chunks into another; record output bytes, bytes written to the stubbed
  wire, every `gmcp_handle_message` payload, final `term_width/height`, `client_name/term/mtts`,
  `ttype_round`.
- Invariants: chunked == whole for all of the above (fragmented and coalesced input are the same
  stream); `written <= length` and `<= out_max` per call; `telnet_sb_len <= MAX_TELNET_SUBNEG`; a
  GMCP payload delivered is `< MAX_TELNET_SUBNEG` and NUL-terminated; NAWS stays in
  [40,250]x[10,100] or 0 after WONT; `client_*` strings printable ASCII and NUL-terminated;
  `ttype_round <= 4` and at most 3 `IAC SB TTYPE SEND` ever written however often WILL TTYPE
  repeats; after each `DO/DONT COMPRESS2` cycle the wire inflates (zlib in the harness, as
  `test_mccp.py` does) to exactly what `write_to_descriptor` was given; `telnet_end_compression`
  leaves no stream (ASan/LSan in the fuzz build with leaks on for this target only, since it
  allocates nothing at process lifetime).
- Seeds: offers answered (`IAC DO GMCP`, `IAC WILL NAWS` + `SB NAWS 0 80 0 24 SE`), TTYPE 3 rounds +
  MTTS, `IAC IAC` in data and in SB, SB with no SE, 2,047/2,048/4,000-byte GMCP, `DO
  COMPRESS2`/`DONT` x3.
- `-max_len=8192`. Prototype already in scratch (A5).
- Acceptance: target and seeds committed; 60 s run clean; replay in `test_fuzz_corpora.py`.

#### F3. Address parsing and PROXY header -- M (extraction for PROXY)

- Exists: `net_addr_parse/text/canonical/guard_key` (`src/netaddr.c`, pure). `proxy_header_accept`
  (`src/comm.c:5429`) mixes parsing with trust (`is_loopback_ip(d->ip)`) and descriptor mutation
  (`free_string`, `str_dup`), uses ROM `str_prefix` (case-insensitive: `proxy tcp4 ...` is
  accepted), copies the source field into `src[64]` silently truncating, and ignores destination and
  ports.
- Extraction (behaviour-preserving first commit): in `netaddr.c`/`netaddr.h` add `int
  proxy_header_parse(const char *line, NET_ADDR *out)` returning `PROXY_NOT` (not a header),
  `PROXY_UNKNOWN`, `PROXY_ADDR`, `PROXY_BAD`, reproducing today's rules exactly (case-insensitive
  prefix, first field only, TCP4 requires family 4, TCP6 accepts mapped v4). `proxy_header_accept`
  keeps the loopback trust check, the "loopback names nothing" rule and the descriptor writes,
  calling the parser. A table test in `tests/test_guard_addresses.c` pins every current decision
  before the move (including the case-insensitive prefix and `PROXY UNKNOWNx`), so the extraction
  diff is provably neutral. Tightening (e.g. a 64-byte field that is cut short must be `PROXY_BAD`,
  not a prefix of an address) is a second, separate commit with its own test.
- Targets: `fuzz_netaddr` (parse -> text -> parse equal; text idempotent; canonical idempotent;
  family in {4,6}; v6 guard key in 240.0.0.0/4 unless v4-mapped; `net_addr_text` into buffers of
  size 0..8 never overruns) and `fuzz_proxy` (never `PROXY_ADDR` with family 0; `PROXY_ADDR` text
  re-parses equal; result independent of bytes after the first field's space; inputs up to
  `MAX_INPUT_LENGTH`).
- Files: `src/netaddr.[ch]`, `src/comm.c` (one function body), tests.
- Compat risk: login of web players (bridge sends TCP4/TCP6/UNKNOWN). Covered by
  `tests/test_client_addresses.py` (in `SANITIZE_MODULES`) and `test_connection_guard`.
- Rollback: revert the comm.c hunk; the parser can stay unused.
- Acceptance: both builds; `scripts/test-parallel.sh test_guard_addresses test_client_addresses
  test_connection_guard test_login_throttle`; fuzz 60 s clean; netaddr.c still free of `merc.h`
  (existing test).

#### F4. GMCP input parsing -- M (extraction)

- Exists (all `static` in `src/gmcp.c`, which needs the whole game): `gmcp_token_equal`,
  `gmcp_payload`, `gmcp_json_string` (string member reader with `\uXXXX`), `gmcp_copy_clean`,
  `gmcp_list_has` (uses ROM `str_prefix`). `gmcp_handle_message` dispatches Core.Ping (echoes
  payload), Core.Hello, Char.Login.Credentials, Core.Supports.*.
- Extraction: `src/gmcp_parse.c` + `gmcp_parse.h`, no `merc.h`, same function bodies with a local
  ASCII case-insensitive prefix replacing `str_prefix` (pin `gmcp_list_has` behaviour first with a
  table test of the current function through the live module `tests/test_mudlet_extras.py` inputs).
  Add to `CMakeLists.txt` (Make globs). `gmcp.c` includes the header.
- Target `fuzz_gmcp`: split input into message + key; invariants: `gmcp_json_string` never writes
  past `size`, result NUL-terminated, false leaves `out` as `""` or a prefix-terminated string (pin
  which), never reads past the terminator after a trailing backslash or a short `\u` (current code
  is safe: `isxdigit` stops at NUL -- the target keeps it so); `gmcp_copy_clean` output printable
  ASCII; `gmcp_list_has` false for any payload lacking the literal quote; `gmcp_token_equal`
  symmetric in case. A second target over `gmcp_json_append_quoted` (output side) waits: it needs
  `color.c`'s token parser, which includes `merc.h`.
- Credentials: the harness must not print payloads (it is synthetic anyway); note that
  `gmcp_handle_message` wipes `password` but not `account` -- harmless (a name), mention in review
  only.
- Effort M (extraction + pinning). Compat risk: Mudlet login and supports flags;
  `tests/test_mudlet_extras.py` and `test_gmcp_payloads.py` cover it.
- Acceptance: both builds; those two modules pass; target 60 s clean.

#### F5. Persistence line readers -- M overall, one commit each

| Reader | Where | Extraction | Invariants / seeds |
|---|---|---|---|
| guard trust file | `guardstore.c:parse_record` (static), `guard_store_load(path)` | none: export `guard_store_parse_record` or fuzz `guard_store_load` on a temp file written per input (`memfd_create` on Linux; tmp file elsewhere) | store `count <= max`; every row parses back from its own text; future-dated (> now + `GUARD_CLOCK_SKEW`) never believed; unfinished last line counted in `bad_lines`; 511/512/513-byte lines; a read-only store never writes (`guard_store_append` returns 0) |
| lockout file | `loginlock.c:login_lock_boot` (needs `lock_table`, `current_time`) | move the per-line parse into `lockwindow.c` (already pure, in the tree uncommitted): `int lock_record_parse(char *line, long now, long ladder_max, long memory, LOCK_RECORD *out)`; boot keeps claiming slots | fields exactly 4; `count` 1..1000; `until`/`last` digits only; nothing past `now + ladder_max`; **then fix A6**: drain an over-long line and skip it as guardstore does (separate commit, its own test) |
| recovery ledger | `recovery.c:ledger_split`, `ledger_check` (static) | `src/ledgerrow.c`/`.h` pure: split + FNV check; `recovery.c` calls it | 10/11 tabs only; FNV must match for 11; CR stripping; `col[0]` digit; a remainder of an over-long line (A6) is never accepted as an 11-column record without its check; seeds: legacy row, checked row, torn row, 9,216-byte line |
| AchSet token | `achievements.c:achievement_set_token` (uses static `achievement_set_max_id`) | `src/achset.c`: `ach_set_token(const char *, long max, long *first, long *last)`; achievements.c passes the max | digits only, no sign, `first <= last <= max`, no ERANGE; the load loop's budget is tested in the existing `test_achievement_set_load` (already sanitized) |
| corpse history | `save.c:corpse_history_read(FILE*)` | WAIT: nothing writes these files (`corpse_back` call is commented out, AGENTS) | if revived: `fmemopen` target; `count+1 <= CORPSE_VALUES-2` already holds |
| corpse record header | `save.c` around line 3295 (`#CORPSE`, `Id`, `Owner`, `Uid`...) | WAIT until corpse files move to a pure reader; covered today by `test_corpse_keep` | -- |

- Each row: Effort S, files as listed, compat risk = boot reading of live files (every change is
  held to "same records accepted" by a table test built from synthetic files before the move),
  rollback = revert the commit (formats untouched; no writer changes).
- Acceptance per reader: both builds; `test_guard_addresses`, `test_login_throttle` (serial),
  `test_recovery_ledger`, `test_achievement_set_load` pass; fuzz 60 s clean; module still has no
  `merc.h` (extend the existing "free of game state" assertion).

#### F6. Turning a crash into a regression -- S (process)

1. CI artifact holds `crash-<sha1>` and the minimized input (`-minimize_crash=1` in `fuzz.sh` on
   failure, bounded to 60 s).
2. The fix commit adds the input to `tests/fuzz/regress/<target>/` (synthetic bytes only -- never
   paste anything from a live log or player file) and, where the bug is reachable live, a focused
   `LiveMud` test (e.g. a raw socket sending the bytes for a telnet bug).
3. `tests/test_fuzz_corpora.py` replays it on every PR under gcc.
4. CHANGELOG entry; a player-visible effect also gets an `area/changes.dat` entry (AGENTS rule).
- Acceptance: documented in `wiki/developer-guide.md`; first real use exercised with a planted bug
  on a throwaway branch.

#### H1. Hardening flags in the Makefile -- S

- Gap: A2. Production gcc gets them by default; clang, macOS, other distros do not; nothing states
  intent.
- Proposal: a separate `HARDEN_CFLAGS ?=` / `HARDEN_LDFLAGS ?=` appended in the compile and link
  rules (not folded into `CFLAGS ?=`, which a user override would silently drop with `-fcommon`).
  Each flag is added only if a probe compile of `/dev/null` with `-Werror` accepts it.
  - Linux and Darwin: `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3` on Linux (glibc 2.34+; Ubuntu 24.04
    has 2.39), `=2` on Darwin; only when the flags include `-O` (FORTIFY needs optimization).
    `-fstack-protector-strong`, `-fstack-clash-protection` (probe; Apple clang may reject),
    `-Wformat -Werror=format-security` (already clean, A3).
  - x86_64: `-fcf-protection=full`. aarch64 Linux: `-mbranch-protection=standard` (probe;
    meaningless on macOS arm64, where Apple uses arm64e -- skip on Darwin).
  - Linux link: `-pie -Wl,-z,relro,-z,now,-z,noexecstack` plus `-fPIE` at compile. Darwin link:
    nothing (ld64 makes PIE by default and rejects `-z`).
  - `make HARDEN=0` turns all of it off (debugging, old toolchains).
- Files: `Makefile`. Dependency: none. Compat risk: ccache key changes once (one slow CI build);
  FORTIFY turns some silent overflows into aborts -- intended; A2 measured the Ubuntu gcc default
  (x86_64) as identical, and H3 confirms the aarch64 production build before anything is assumed.
- Rollback: `HARDEN=0` in the environment, or revert.
- Acceptance: `make` on Ubuntu gcc produces a binary byte-identical in hardening properties to today
  (H3 report equal); `make CC=clang` now passes H3; macOS dev build (`Install-ToC.command` path)
  still builds -- checked by a contributor on a Mac or a `macos-14` manual workflow run.

#### H2. Hardening in CMake -- S

- Proposal: `option(TOC_HARDEN "..." ON)`; `include(CheckCCompilerFlag)`, `include(CheckLinkerFlag)`
  (CMake >= 3.18; minimum is 3.20) for each flag of H1; `set(CMAKE_POSITION_INDEPENDENT_CODE ON)`
  with `check_pie_supported()`. FORTIFY only for non-Debug configs and **never with
  `ENABLE_SANITIZERS`** (ASan intercepts the same calls; FORTIFY wrappers hide bugs from it). Keep
  `-fcommon` absent here as today (C17 tree is clean).
- Acceptance: `cmake -DCMAKE_BUILD_TYPE=Release` binary passes H3; sanitizer build unchanged
  (`readelf` shows no `_chk` added; the 19 sanitizer modules still pass).

#### H3. Verify the binary, not the flags -- S

- Proposal: `scripts/ci/check_hardening.py <binary> [--arch x86_64|aarch64] [--json]`. Linux checks
  with `readelf`: ELF type DYN and `FLAGS_1` has PIE; `GNU_RELRO` present and `BIND_NOW`/`NOW`;
  `GNU_STACK` flags without E; no `TEXTREL`; no `RPATH`/`RUNPATH`; imports `__stack_chk_fail`;
  imports at least one `__*_chk` (FORTIFY evidence -- the tree calls `snprintf`, so zero means
  FORTIFY is off); property note `IBT, SHSTK` on x86_64, `BTI, PAC` on aarch64 (the note is dropped
  if any object lacks it, so this also catches a stray unhardened object). macOS with `otool -hv`
  (PIE flag) and `nm -u` (`___stack_chk_fail`, `___*_chk`). Exit 1 with a table on failure.
- Where: `validate.sh build` after `make` and after the CMake build; `build-sanitize` skips it. Add
  a small `hardening-arm64` job on `ubuntu-24.04-arm` (free for public repositories) that runs
  `make` and the check -- production is aarch64 and nothing tests that build today. The docker-image
  workflow runs the check inside each platform's build stage (`RUN python3
  scripts/ci/check_hardening.py merc` -- python3 is in the python stage; or ship the check as a tiny
  shell+readelf variant).
- Unit test `tests/test_check_hardening.py`: builds two scratch binaries from a hello-world (one
  with `-no-pie -Wl,-z,lazy -fno-stack-protector`) and asserts pass/fail.
- Acceptance: CI green on both arches; a scratch branch that adds `-Wl,-z,lazy` fails `build` with
  the table in the step summary.

#### H4. Production check at deploy, warn-only -- S

- Proposal: `toc-deploy` runs `check_hardening.py` (or a 15-line sh/readelf equivalent, since the
  host must not need extra packages) after the build and **logs** the result into
  `/tmp/toc-deploy-build.log` and the journal; it never refuses. After a month of clean logs the
  owner may choose to make it refusing -- a deploy-behaviour change for him to make.
- Compat risk: none (warn only). Rollback: revert; scripts self-install at the end of a healthy
  deploy, so the change takes effect one deploy later (AGENTS).
- Acceptance: `tests/test_deploy_failures.py` stub run shows the warning line and an unchanged exit
  status.

#### Wait (section 4)

- Coverage-guided fuzzing of `fread_char`/`load_char_obj`, `load_area` and `fread_obj`: they call
  `exit()` on malformed input and pull in the world. Worth it only after a "reader returns an error
  instead of exiting" project; the live loaders are covered by `test_lost_containers`,
  `test_achievement_set_load` and the area validators meanwhile.
- `nanny()` state-machine fuzzing over a socket (grammar-based, with `LiveMud`): high value, high
  cost; after F2/F3 have run a month.
- OSS-Fuzz/ClusterFuzzLite: the GitHub job above covers the need at no cost.
- `-D_GLIBCXX_ASSERTIONS`, CFI, `-ftrivial-auto-var-init=zero`: measure performance first;
  `-ftrivial-auto-var-init` changes the behaviour of latent uninitialized reads, which this codebase
  may depend on.
- `-Werror` on clang's three warnings (A3): fix them as ordinary cleanups.

---

### 5. Turning the play journal into incident cases

#### What exists

- `log/play.tsv` (`src/playlog.c`): common columns epoch, kind, name, level, room, area; kinds
  `cmd`/`refused` (pos, hp%, ms, fight, command, args, reply, outcome, truncated `+`), `outcome`
  (op, result, reason, ledger op id, key=value detail), `state` (SCORE numbers), `stall`, `death`
  (killer + key=value), `item`, `session` (coin/spent/exp tallies), `anomaly`, `report`, `bug`,
  `craft`. Trimmed 30,000 -> 15,000 lines (`journal_trim`). Privacy:
  `line_privacy`/`command_is_private` (`src/interp.c:611,722`) withhold private words and replies;
  `room_hides_from_log` writes `-`.
- `log/progress.tsv`: kill/flee/death by pfile `Id` (never a name), area file, encounter ms, XP,
  coin. Trimmed 40,000 -> 20,000.
- `log/crash.log` (signal-safe ring of 128 commands), `log/toc.log` (watch log `Log <Name> [room]:
  ...`, BUG lines with context, boots), `log/channels.tsv` (public channels only), `log/logins.tsv`,
  `log/deployed-commit` (commit + deploy time, rewritten each deploy), `log/auto-deploy.status`.
- Recovery identity: ledger uid `P<time><seq><rand>` per character, retired at deletion, new for a
  reused name (`recovery_assign_uid`, `src/recovery.c:787`); ledger rows carry seq, time, event,
  state, uid, player, request id, kind, actor, detail (snapshots: `<file> fnv <hash> <bytes>`).
- Snapshots `player/versions/<Name>/<Name>.<stamp>[_NN][.<kind>]` (`snapshot_name_parse`,
  `src/save.c:393`); corpse ids `c<time><ctr><rand>` (`corpse_new_id`, `src/corpses.c`) with
  `Snapshot`, `Uid`, `State`, `Why` in each record.
- `tools/log_report.py` reads rows by `fields[0].isdigit()` and `r[1]` kind, uses `len(r) >= 13` for
  commands, key=value regexes for death/outcome -- so extra **trailing** columns, extra key=value
  words and new kinds are ignored safely; a changed kind name or a column inserted in the middle
  would break it.
- `tools/player_history.py` (`show`/`diff` of saved states in git), `tools/audit_players.py`.

#### I0. Wizinvis actors in journal rows -- S (owner decision first)

- Gap: A7.
- Proposal: in `playlog_end`, `playlog_session`, `playlog_death`, `playlog_report`, `anomaly` and
  `playlog_bug`'s context, write `NULL` (name `-`, room `0`) when the actor `IS_SET(ch->act,
  PLR_WIZINVIS)`, the rule the other four writers already follow. Alternative the owner may prefer:
  drop rows for characters at `get_trust >= LEVEL_IMMORTAL` altogether. `crash.log` stays as is
  (local file, only written on a crash) -- or apply the same rule; owner's call.
- Files: `src/playlog.c`. Compat: `log_report.py` already copes with `-`.
- Rollback: revert.
- Acceptance: new `tests/test_playlog.py` case: a synthetic staff fixture `Zwizard` goes WIZINVIS,
  types LOOK and SCORE; the test world's `log/play.tsv` holds no row naming it; a visible staff
  fixture's rows still do (or none, per the decision).

#### I1. Versioned schema, boot id, revision -- S

- Gap: A10; no way to say which code wrote a row or which boot it belongs to.
- Proposal: a `meta` row kind, written by `playlog_boot()` (after `boot_db`) and again after every
  `journal_trim`/`progress_trim` (the trim keeps the newest lines, so a header at the top would be
  cut away): `epoch  meta  -  0  0  -  schema=play/2 boot=<id> rev=<commit12|unknown>
  bin=<sha256-12|unknown> started=<boot epoch>`. Fields are key=value in one column, so new keys
  never move columns. `boot` = 16 hex digits from `/dev/urandom` (fallback: boot epoch and pid),
  kept in a global and also written in the toc.log banner ("Boot id ..., revision ..."). `rev`/`bin`
  read from `../.code-revision` (written by `toc-deploy` and `toc-restore` in the live tree root;
  the game runs in `area/`), never compiled in (keeps ccache and reproducibility). `progress.tsv`
  gets the same row with `schema=progress/2`. Schema numbers bump only when a column's meaning
  changes; appended columns do not bump.
- `log_report.py`: ignore `meta` explicitly (one line) and print the boots in the window with their
  revisions.
- Files: `src/playlog.c`, `src/comm.c` (banner), `tools/log_report.py`.
- Compat: old readers skip the unknown kind (verified by reading `journal_report`, `deep_summary`,
  `progress_summary`: a 7-field row with kind `meta` matches none of their filters).
- Acceptance: `tests/test_playlog.py`: boot a world with a planted `.code-revision` (synthetic
  40-hex id), assert one `meta` row with that revision and a 16-hex boot id; a second boot gives a
  different id; force a trim with a test-sized `PLAY_JOURNAL_MAX` env override (add one) and assert
  a `meta` row follows it; `tests/test_ops_tools.py` passes unchanged.

#### I2. Session id -- S

- Proposal: `d->conn_serial` (a per-boot counter set in `new_descriptor`); the session id is
  `<boot>.<serial>`; reconnect keeps the character's `pcdata->play_session` (set at login, not at
  reconnect) so a link loss does not split a sitting. Written as a **trailing** column on
  `cmd`/`refused` rows (after the `+` column) and as `session=<id>` in `session`, `death`, `outcome`
  and `state` details. Never derived from the address.
- Compat: `log_report.py` reads by fixed index; trailing column ignored.
- Acceptance: `tests/test_playlog.py`: two logins of `Zsessiona` give two ids; a dropped link and
  reconnect keep one; a reader that stops at column 14 sees today's rows unchanged.

#### I3. Operation references in rows -- S each

- Death: add `corpse=<id>` and `receipt=death:<id>` to the death detail (`playlog_death` is called
  from `raw_kill_internal`; the corpse id is known once `corpse_registry_died` ran -- pass it, or
  log a second `outcome op=death-settle` row from `corpse_registry_death_settle` with the receipt
  and the save's `DURABLE_*` result). `deep_summary`'s regex takes only `\w+=-?\d+`, so the hex ids
  are ignored there.
- Snapshot: `playlog_outcome(..., op="snapshot", op_id=<file name>, detail="kind=<tag> fnv=<hash>
  durable=<0|1>")` from `player_snapshot_milestone` for milestones only (ordinary saves would flood
  the journal).
- Restores already ride `op_id` (PRESTORE gives, ACCEPT, STASH TAKE).
- Acceptance: `tests/test_death_transfer.py` and `test_prestore.py` extended to find the referenced
  ids in the test world's journal and ledger.

#### I4. Identity policy for exports -- S (documentation + tool rule)

- Journal keeps names (public anyway, owner policy; changing it breaks `log_report.py --player`).
  `progress.tsv` keeps pfile `Id`.
- Every **export** replaces identities: resolve a row's name to the ledger uid active at the row's
  time (uid `assign`/`retire` records give the intervals, so a recreated name is a different
  person), then pseudonymize `HMAC-SHA256(salt, uid)` with a random per-export salt that is never
  written out, rendered as `Zsubject` for the incident subject and `Zp01..` for others in order of
  appearance. Mobiles keep vnum + short description. Staff (row level >= `LEVEL_IMMORTAL`, 60)
  become `Zstaff` or are dropped (I6). The ledger uid itself never appears in an export (it sits
  beside the name in the public ledger, so it is not anonymous).
- Acceptance: unit test of the resolver on a synthetic ledger where name `Zreuse` has two uids in
  sequence.

#### I5. `tools/incident.py` -- M

- Read-only, from the repository root, from a git ref (default `origin/main`) or a directory (a
  disposable state copy). Never writes inside the repository; `--out` must be outside it (checked).
- `incident.py case --player Zname --at "2026-11-09 14:00" [--before 30m] [--after 10m]` (window
  capped at 24 h; default 40 minutes) assembles, sorted by time with a source tag:
  - journal rows for the subject (all kinds), plus global `stall`, `bug`, `meta` rows in the window;
  - watch-log lines `Log <Name> [...]` from `toc.log` and BUG/ANOMALY lines;
  - `progress.tsv` rows by the subject's pfile `Id` (read `Id` from the player file at the ref --
    only that key);
  - ledger records naming the subject or their uid (snapshots, receipts, prestores, uid events),
    with state;
  - corpse records in `corpse/live` and `corpse/history/<Owner>/` died or saved in the window, with
    `Snapshot`, `State`, `Why`, object count;
  - snapshots of the subject whose stamp falls in the window, and **before/after state** from the
    nearest snapshot before the window and the nearest after (or the player file at the ref): level,
    exp, hp/mana/ move maxima, coin and bank, quest points, worn/carried/stash object vnums with
    counts -- reusing `player_history.py`'s readers, field whitelist only;
  - deploys: `git log` of `log/deployed-commit` at the ref (each version holds commit + deploy time)
    and boots from `meta` rows or banner lines, so each row is labelled with the revision live at
    that moment;
  - timing: per-command ms, stalls overlapping the window.
- Output: `case.json` (machine) and `case.md` (human), each with a header: window, sources and their
  byte offsets/commit, row counts, truncations, and **gaps** (journal trimmed past the window start;
  no snapshot before; boot inside window; rows from a schema it does not know).
- Bounds: at most 5,000 source rows read into the case after filtering (streamed, never whole files
  in memory beyond `git show` of one file; `play.tsv` is at most 30,000 lines by construction), at
  most 1,500 timeline entries (oldest dropped first, stated), 240 characters per field, export file
  at most 256 KiB; processing time target < 10 s on the current logs.
- Compat: imports `clean()` and parsing helpers from `log_report.py` rather than re-implementing
  them; `tests/test_ops_tools.py` style tests.
- Acceptance: `tests/test_incident_tool.py` builds a synthetic state directory (Z players, a ledger
  with snapshot/receipt rows, a corpse record, two snapshots, a journal spanning a `meta` row and a
  deploy) and checks the timeline order, the before/after diff, the revision labels, the gap notes
  and every bound (a 50,000-row journal yields <= 1,500 entries and a stated truncation).

#### I6. Redacted export for an AI reviewer -- M

- `incident.py export <case.json>` produces the only file meant to leave the operator's machine.
  Redaction is a **whitelist of fields per row kind**, then filters; anything unknown is dropped,
  not passed.
- Never included: password hashes or any player-file line other than the whitelisted state fields
  (no `Pass`, no host/address keys, no `Fixes`); addresses and host names (strip with
  `log_report.clean`, then a second pass that drops any row still matching an address regex rather
  than editing it); `log/logins.tsv`, `log/player_addresses.tsv`, `log/login_lockouts.tsv` entirely;
  private communication: rows whose command is in the mirrored `command_is_private` list (tell,
  reply, gtell, `;`, history, replay, note) **and** the inner command of `alias`, `at`, `force`,
  `order` per `line_privacy` -- drop args and reply even if a character was LOG-flagged in full (the
  watch log keeps their words); channel text unless `--with-public-channels`; staff presence: rows
  of characters at level >= 60 and any line naming a staff character are dropped (wizinvis cannot be
  told from a historical row, so all staff are treated as hidden); dealer/goblin: `-` rooms stay
  `-`, and `Black market:` / `Treasure goblin:` lines lose their room numbers; the founder/creator
  is never named (covered by the staff rule).
- A Python mirror of `private_cmds` must be held to `src/interp.c` by a test (as
  `tests/test_ops_tools.py` already holds table parsing to the source), or a future private command
  leaks through exports.
- Output header states every rule applied and counts of rows dropped per rule, so the reviewer knows
  what is missing.
- Acceptance: `tests/test_incident_export.py` plants, in a synthetic case, a fake DES-shaped hash,
  an IPv4 and an IPv6 address, a host name, a tell with a marker word, a note, `alias zz tell Zp
  hi`, `force Zp tell ...`, a staff row, a creator-level row, a dealer room, and asserts none of the
  markers, numbers or names survive; also asserts the export is <= 256 KiB for an oversize case.

#### I7. Incident -> regression skeleton -- S

- `incident.py skeleton <case.json>` prints (stdout or `--out` outside the repo) a `unittest` module
  using `LiveMud(fixtures=True)`: creates `Zrepro` with the subject's level/class (staff fixture
  ADVANCE as existing tests do), places it in a safe room then `goto`s the incident's room (or a
  fixture room if the room is hidden or in Hyrule's dungeon), loads the named mobile vnums, replays
  the subject's non-private commands with `MudClient.sync`, and asserts on the **test world's own**
  `log/play.tsv` outcome rows (the same op/result as the incident) with `TODO` markers.
- States plainly in its docstring that it is not a deterministic replay: dice, ticks, other players,
  wandering mobiles and lag are not reproduced; it uses the existing switches (`TOC_NO_DISASTERS`,
  `TOC_NO_GOBLIN`, `TOC_NO_HERBIE`, `TOC_SEASON=none`, `TOC_DATE`) and the fixture world.
- Acceptance: the skeleton for the synthetic case of I5 runs (skips with a reason when no binary)
  and passes `tests/test_fixture_hygiene.py` rules.

Storage: no new `log/` files; `meta` adds ~2 lines a boot plus one per trim; session ids ~20 bytes
a command row (3% of the 640-byte line cap). Trim limits unchanged.

#### Wait (section 5)

- An in-game `INCIDENT` staff command: reading and joining files inside the single-threaded game
  loop costs stall time and duplicates the tool; revisit only if staff without a checkout need it,
  then as a read of the newest `play.tsv` rows only, paged, trust-gated, read-only.
- Stable object identities (`wiki/player-backups.md` "Not yet"): would let a case follow one sword
  across trades; a save-format change, own project.
- Deterministic replay (seeded RNG per command): changes gameplay randomness surfaces; not now.
- Sending exports to an AI service automatically: keep it a manual, operator-reviewed step.

---

### 6. Automated recovery verification

#### What exists, by kind

| Mechanism | Kind | Where | Off-host | Versioned | Verified restore |
|---|---|---|---|---|---|
| `toc-state-sync` every 5 min, plaintext, public `main` (owner policy, keep) | replication into git history | `deploy/windows-vm/toc-state-sync` (`STATE_DIRS="player gods heroes log"`, area runtime files, `corpse/`, hourly/tagged `player/versions/`) | yes (GitHub) | yes, via git history | partly: `deploy/toc-restore` with `TOC_PREFIX` rehearsal checks code builds and the world loads (`--check-area`), not that characters load |
| `toc-state-sync-check` | monitor | 15-minute timer, WIZINFO | -- | -- | no |
| Snapshots + milestones | local versioned copies | `player/versions/`, pruning `snapshot_prune` (`src/save.c`), ledger checksum records | via sync (subset) | yes | PRESTORE reads them; no bulk check |
| Recovery ledger | receipts, uids, snapshot checksums | `player/recovery/ledger.tsv` (`src/recovery.c`) | via sync | append-only | boot trims torn tails |
| Corpse registry | live and ended corpses | `corpse/live`, `corpse/history` (`src/corpses.c`) | via sync | history kept | boot re-lays; `.unreadable` kept |
| In-game archive | local backup | `backup_launch` (`src/update.c:268`): `tar` of `../player` only, 30 days | **no** | yes (30 d) | `gzip -t`, `tar tzf` only |
| `toc-player-backup` | encrypted off-host copy | `deploy/sync-player-backup.sh` (age, private repo) | yes | **no** (force-pushed latest) | listing count only |
| `toc-daily-backup` | unknown | host only (A9) | ? | ? | ? |
| `tools/audit_players.py`, `audit_maxload.py`, `player_history.py` | semantic checks / history | `tools/` | -- | -- | read git state; not wired to a drill |

#### V1. A read-only character verification mode in the server -- M

- Gap: nothing proves a restored `player/` loads in the real loader; the Python tools re-parse the
  format independently.
- Proposal: `merc --check-players [--json path]`, next to `--check-area`: `boot_db` (world),
  `recovery_boot`, then for every `player/<Name>` file (2-12 letters, `offline_player_load` rules)
  load it through `load_char_obj` exactly as login's first stage does, emit one manifest line and
  free it with the existing free path. **Writes nothing**: a global `verify_only` makes
  `save_char_obj`, snapshot, ledger append, corpse registry writes and `durable_commit` refuse
  (return FAILED and log once), `ledger_trim_tail` and corpse boot run in "report, do not mend"
  mode, and the mode refuses to start unless `TOC_VERIFY_DIR` names the working tree (guard against
  pointing it at live state). Login fixes, psionic login, rested-XP banking and the nanny are not
  run (they live outside the loader, AGENTS "Nothing psionic that speaks runs inside
  load_char_obj").
- Manifest per character (TSV, versioned `#check-players v1`): file name, uid (from the ledger
  index), level, class, remorts, exp, max hp/mana/move, coin in copper, bank, quest points, worn
  count + sorted worn vnums hash, carried count, stash count/`stash_max`, objects-dropped-at-load
  count (bad vnum, `unwear_illegal_at_load`), revive-at-load flag, pending `Fixes` marks
  (`restore:`), a normalized-state SHA-256 of those fields. No names of objects beyond vnums; no
  password field read out.
- Files: `src/comm.c` (argument), `src/save.c`, `src/recovery.c`, `src/corpses.c` (verify guards),
  new `src/verify.c` (+ CMake list).
- Compat risk: the guards touch durability code. Mitigation: guards are a single early `if
  (verify_only)` in each writer, covered by a test that runs the mode on a fixture tree and asserts
  every file's mtime and hash unchanged.
- Rollback: revert; no format change.
- Acceptance: `tests/test_check_players.py` (also in `SANITIZE_MODULES`): synthetic tree with
  `Zdrillone` (worn gear, stash, bag in bag), `Zdrilltwo` (a retired vnum that maps through
  `retired_objects`), `Zdrillbad` (a truncated file) -> manifest rows for the first two, a failure
  row for the third, exit status 1, no file changed; both builds.

#### V2. `tools/restore_drill.py` -- M

- Input sources (one per run): `--git-ref origin/main` (materialized with `git archive` into a temp
  dir, never a worktree inside the repo), `--age-archive file --identity file` (decrypt into the
  temp dir), or `--dir` (an already restored tree, e.g. `TOC_PREFIX=/tmp/drill toc-restore`). Always
  a fresh `mkdtemp` outside the repository; removed at the end unless `--keep`.
- Steps: build the binary from the same ref (or `--binary`), run `--check-area`, run
  `--check-players --json`, then Python cross-checks:
  - ledger: every line whole (FNV), sequence monotone, no torn tail;
  - identity: one active uid per name, no uid on two names, every player file has a uid, no uid for
    a deleted file unless retired;
  - snapshots: for each ledger `snapshot` record whose file is present, recompute FNV and bytes;
    list mismatches and records whose file was pruned (expected) apart from missing milestones (not
    expected while the keep rule says it should exist);
  - corpses: each `corpse/live/*.corpse` reads, owner file exists, recorded uid equals the owner's
    uid now, `ending`/`stale`/`unreadable` counted;
  - pending operations: receipts `pending`/`retry` with age, and players whose file holds a
    `restore:` mark without a committed receipt;
  - uniqueness: `tools/audit_maxload.py` (limited items vs `maxload.txt`) and a scan for the same
    limited vnum held twice across files/stashes/ corpses where the cap is 1;
  - `tools/audit_players.py` findings by kind;
  - coverage: which state directories the source lacked (`heroes/`, `backups/`, `gods/`, area
    runtime files), and anything the restore layout expects that was absent.
- Report (`--json` + text): source and its time ("newest verified recovery point": the commit id and
  the newest player-file save time inside it, and its age), pass/fail per check with counts,
  pseudonymized offenders (I4's scheme, never names or uids), runtime. Exit 0 only when all
  must-pass checks pass.
- Acceptance: `tests/test_restore_drill.py` on synthetic trees: a clean tree passes; each planted
  defect (torn ledger tail, duplicate uid, snapshot byte flip, corpse with the wrong uid, a unique
  item in two files, a pending receipt older than a day) fails exactly its check; total runtime
  under 60 s with the prebuilt binary.

#### V3. End-to-end synthetic drill -- S (after V1, V2)

- `tests/test_restore_drill_live.py`: `LiveMud(fixtures=True)` creates `Zdrillone` and `Zdrilltwo`,
  gives gear, stashes a bag holding a bag, kills one in the fixture ring (a corpse and a death
  milestone), runs a PRESTORE GEAR to leave a committed receipt, quits both, stops the server; runs
  `--check-players` on the world (manifest A); copies the state the way `toc-state-sync` would (its
  file list and exclusions, read from the script) into a temp "repo", lays it down with
  `toc-restore`'s rsync rules into another temp dir (or `TOC_PREFIX` rehearsal when root is
  available), runs the drill (manifest B), asserts A == B per character and that the drill's checks
  pass.
- This is the missing proof that the sync's file list and the restore's layout agree on characters,
  not just on a booting world.

#### V4. Scheduled drills -- S

- Host: a `toc-restore-drill` timer (weekly, outside 06-09 Pacific), running V2 against
  `origin/main` in `/var/tmp`, `nice`/`ionice`, never touching `/srv/toc/current`; writes
  `log/restore-drill.status` (`<time> ok|FAIL <newest recovery point> <age> <failed checks>`) so the
  state sync publishes the verdict, and WIZINFO (never ANNOUNCE) on failure, like
  `toc-state-sync-check`. Installed by `toc-deploy` like the other scripts (effective one deploy
  later).
- Optional GitHub Actions `restore-drill.yml` (weekly `schedule`): the state is already public; the
  job prints only counts and pseudonyms in its summary. It must sit outside `validate.yml` and never
  feed `deploy-gate`.
- Acceptance: status line appears in a scratch run; a planted failure on a fixture tree yields
  `FAIL` and the WIZINFO line in a `LiveMud` world running the same check-script path.

#### V5. Versioned encrypted off-host backup with independent credentials -- M

- Gap: A8, A9. Replication (the public sync) is not a backup against deletion or corruption that the
  sync faithfully copies, and the private encrypted copy is latest-only and erasable by the host's
  own key.
- Proposal: `restic` (single static binary, packaged in Ubuntu) from the host to object storage with
  immutable retention:
  - Target: an object store supporting S3 object lock or retention rules (e.g. Oracle Object Storage
    retention rules -- free tier capacity is ample for a few hundred MB -- or Backblaze B2 with
    object lock) in a **different account** from the compute host.
  - Credentials: host holds a write-only/no-delete key (bucket policy or restic `rest-server
    --append-only` if self-hosted); delete and prune are done only from the owner's desktop with a
    separate key. Repository password and the read key live in the owner's password manager and on
    one offline copy (printed or on a USB key in a drawer); never in git, never in `/etc/toc` on the
    game host except the write path.
  - Content: `player/` (with `recovery/` and `versions/`), `gods/`, `heroes/`, `corpse/`, area
    runtime files and `area/built/`, `log/` minus nothing (it is all public anyway), plus
    `/etc/toc/*.env` **excluded** (admin token stays on the host; a new host generates its own).
  - Schedule: hourly, plus before each deploy (hook in `toc-deploy` after the save, warn-only on
    failure). Retention: hourly 48, daily 30, weekly 26, monthly 24; object-lock period 30 days so a
    compromised host cannot shorten history below a month.
  - Verification: `restic check --read-data-subset=5%` weekly; monthly the drill (V2) restores the
    newest snapshot into a temp dir and verifies it (`--dir` source), recording the restic snapshot
    id in the status line.
  - Keep `toc-player-backup` (age, private repo) as is or retire it once V5 has a month of verified
    history -- owner decision; if kept, stop the force-push by writing dated archives and pruning to
    the last 14 from the desktop (S, independent change).
- Restoration when the original host is gone (runbook in `wiki/disaster-recovery.md`): new box ->
  `toc-restore` from the public repo (code + plaintext state) -> compare with the newest restic
  snapshot using the drill (`--dir` both, diff manifests) -> if the public state is damaged or
  behind, `restic restore` the chosen snapshot into `/srv/toc/current` state paths with the game
  stopped -> `--check-players` -> start. Needs: the repository password and read key (offline copy),
  the bucket name, and nothing from the lost host.
- Files: `deploy/windows-vm/toc-vault-backup` (+ `.service`, `.timer`), `deploy/vault.env.example`
  (placeholders only), docs; `toc-deploy` install list. Effort M (mostly account setup and docs;
  script ~80 lines).
- Compat risk: disk/CPU on a free-tier box (restic dedupe keeps hourly runs small; `nice`);
  credentials handling. The public sync is untouched.
- Rollback: disable the timer; the bucket keeps its locked history.
- Acceptance: on a scratch machine with a local restic repo (no cloud): back up a synthetic tree,
  corrupt the tree, restore snapshot N-1, drill passes; `restic forget --prune` with the host-side
  key is refused (append-only rest-server in the test); the runbook is executed once end to end on a
  scratch VM by the owner and the time recorded.

#### V6. Small fixes to existing backups -- S each

- In-game archive (`backup_launch`): include `../corpse` beside `../player` so a host-local restore
  has the corpse records the ledger points to (`tests/test_backup_detached.py` extended to list
  `corpse/` in the tar).
- Commit `toc-daily-backup`'s source from the host into `deploy/windows-vm/` (desktop session; read
  it first, redact nothing because it should contain no secrets -- if it does, that is a finding),
  with a stub test like the other scripts.
- `toc-restore`: after `--check-area`, run `--check-players` (V1) and print counts; warn-only so a
  damaged player file never blocks bringing the game back.

#### Wait (section 6)

- A consistent cross-player snapshot (quiescing saves) -- the sync's per-file nature is documented
  as a known boundary; restic of the live tree has the same property. Revisit only if the drill
  finds cross-file inconsistency in practice (e.g. a STASH TAKE receipt without either file).
- Automatic repair from the drill (re-laying corpses, re-committing receipts): the drill reports;
  PRESTORE and the boot settlement already repair under their contracts.
- Encrypting or narrowing the public sync: owner policy says no.

---

### Ordering (independently shippable, smallest first)

1. F0, H3 (check only, report), I1, A6 drain fixes (with F5 parsers) -- all S.
2. F1 + F2 (telnet, no extraction), H1, H2, I0 (after owner answer), I2.
3. F3 (PROXY extraction), F5 parsers one by one, I3, V6, H4.
4. V1, then V2, then V3 and V4.
5. F4 (GMCP extraction), I5, I6, I7.
6. V5 (needs owner account setup and offline key handling).

Every C change: both builds, the focused modules named above through `scripts/test-parallel.sh`,
`git diff --check`; the full suite only for V1 (touches durability writers) and I1/I2 (touch the
journal every command writes), with the reason stated in the PR.

## Appendix 3: Performance, Input And Persistence Boundaries, Accessibility (P7, P8, P9)

Read-only assessment, 2026-11-09. Source read at the working tree on branch
`fix-review-20261109` (concurrent edits pending in `src/comm.c`,
`src/loginlock.c`, `src/merc.h`, `src/misc.c`; recheck those citations
before acting). Runtime data read from `origin/main` (8c5e0f92): the synced
`log/play.tsv`, its git history since 2026-11-04, and `log/toc.log`.
Nothing in the repository was changed. No player names, addresses, hashes
or private text appear below; journal figures are aggregates.

Conventions: effort S (under a day, one commit), M (a few commits), L
(a week or more). Every proposal is independently shippable unless its
"Depends" line says otherwise. "Both builds" means Make (gnu89) and CMake
(c17, extensions off), per AGENTS.md. Fixtures are synthetic, Z-prefixed,
in disposable worlds (`tests/live_mud.py`), never a real player file.

---------------------------------------------------------------------------

### 7. Measured Performance And Safer Background Work

#### 7.0 What the stall journal actually says

Source of the rows: `playlog_pulse_begin`/`playlog_phase_enter`/
`playlog_pulse_end` in `src/playlog.c` (STALL_MS 250, STALL_QUIET 60 s),
called from `game_loop_unix` (`src/comm.c`, begin before `dns_collect`,
"output" mark before the output pass, end after it) and `update_handler`
(`src/update.c`, one mark per phase).

Every `stall` row ever synced (git history of `log/play.tsv`, first row
2026-11-05 21:10 UTC, last 2026-11-08 17:00 UTC; the current file holds
the same 34):

| measure                          | value                                  |
| -------------------------------- | -------------------------------------- |
| stall rows                       | 34 (plus 1 suppressed by STALL_QUIET)  |
| pulse total p50 / p90 / max      | 389 / 561 / 604 ms                     |
| rows with a slowest command      | 0 (every row says `command - 0ms`)     |
| players online at the stall      | 0 in 32 rows, 1 in 2 rows              |
| phase "input"                    | 21 rows, median 385 ms, max 527        |
| phase "disaster_update"          | 8 rows, median 559 ms, max 599         |
| phase "update"                   | 3 rows, ~250 ms                        |
| phase "room_update"              | 2 rows, ~255 ms                        |

Correlation with `log/toc.log` (timestamps to the second):

- All 21 "input" rows fall between 2026-11-05 21:10 and 2026-11-06 20:39,
  before the deploy of the async resolver (3a1a0297, deployed 2026-11-06
  22:00). None since. They were `getnameinfo` inside `new_descriptor`;
  the fix is `src/dnsasync.c` + `dns_collect` (AGENTS "Connections").
- All 13 later rows match a player backup to the second: 7 at a boot
  (first pulse, where both the 4-hourly and daily archive ran) and 6 on
  the 4-hour cadence. They were `system("tar cfz ...")` in
  `weather_update` (`src/update.c`), which had no phase label, so the
  time was blamed on the previous mark (disaster_update, update,
  room_update). Fixed by c51454a1 (2026-11-08, `backup_launch`: double
  fork, detached, niced), deployed 2026-11-08 17:48. Since then six
  backups (one at a boot, running both archives) produced no stall row
  through the 2026-11-09 15:07 UTC sync.
- Conclusion: **no known open hotspot above 250 ms.** Both real causes
  were found by this journal and both are fixed. The journal cannot see
  anything below 250 ms, and nearly all rows came from an empty game, so
  "no rows" is weak evidence about latency with players on.

Command latency (`cmd`/`refused` rows, ms column = `interpret()` wall
time, `src/interp.c` ~1345): 17,412 commands; p50 0 ms, p99 6 ms,
p99.9 21 ms, max 269 ms; 2 commands at 50 ms or more. By command
(counts and percentiles only): AQUEST p50 11 / p99 25 / max 64 (quest
completion saves and takes a milestone); STASH p50 4 / max 17 (save per
deposit); DEPOSIT max 11; REMORT 269 (milestone, wipe, save; rare);
COMBINE 16. Movement p99 0. Reading: **a save with its snapshot costs
roughly 4-25 ms on the Oracle host**, and saves are the only command-time
cost that shows at all.

Attribution lesson worth keeping: any unlabelled stretch is charged to
the phase before it. The "input" mark covers `dns_collect`,
`login_idle_sweep`, `conn_guard_tick`, `process_web_admin_queue`,
`oracle_process_queries`, `select`, `init_descriptor`, reading, and all
command execution (commands are timed separately via
`playlog_pulse_command`).

#### 7.1 Clock inventory (what measures durations with what)

| site | clock | used for | risk |
| --- | --- | --- | --- |
| `game_loop_unix` pacing, `src/comm.c` (~975, ~1294-1314) | `gettimeofday` | 250 ms pulse sleep | backward wall step N s => game sleeps N s; forward step => no sleep (harmless) |
| watchdog ping, `game_loop_unix` (~1000) | `current_time` (time()) | `WATCHDOG=1` every 10 s | backward step > ~50 s stops pings; `WatchdogSec=60` in `deploy/windows-vm/toc-game.service` then kills the game [host unit unverified] |
| `playlog_now_ms`, `src/playlog.c` (~1019) | `gettimeofday`, epoch ms in `long` | stall totals, phase ms, `fight_began_ms` (`src/fight.c` ~2990), encounter ms in `progress.tsv` | wall steps make negative/huge durations; epoch ms overflows a 32-bit `long` (not production, but the type is wrong) |
| `interpret()` timing, `src/interp.c` ~1345-1355 | `gettimeofday` | `cmd` row ms, slowest command | same |
| script timer payload, `src/comm.c` ~1227 | `gettimeofday` | `SCRIPT_EVENT_TIMER_TICK` delta | clamped at 0 already |
| `write_raw_to_descriptor`, `src/comm.c` ~2954-3070 | `CLOCK_MONOTONIC` | WRITE_STALL_MS/MAX/BUDGET | correct today |
| `dnsasync.c` ~54 / ~74 / ~157 | MONOTONIC for stats ms, `time(NULL)` for `DNS_JOB_MAX_AGE` | job expiry | mixed; job age should use the monotonic it already has |
| `login_idle_sweep` `src/comm.c` ~933 (`input_at`) | `current_time` | LOGIN_IDLE_SECS 600 | seconds granularity is fine; a big backward step delays the sweep |
| `src/connguard.c` (42 uses), `src/loginlock.c` (20) | `current_time` | windows, pauses (memory), lockouts (persisted epoch) | persisted lockouts and trust MUST stay wall epoch; memory windows tolerate seconds |
| oracle daze `src/oracle.c` ~281-329 | `current_time` | `oracle_daze_until` (memory only) | negligible |
| `walkto_update` `src/walkto.c` | pulses, no clock | step pacing | none |
| `holiday_current` `src/holiday.c` ~294 | `time(NULL)` + `localtime` | calendar | must stay wall/local (TOC_DATE overrides) |
| corpses, save, quest, rested | `current_time` | persisted epochs (Died, Saved, LastOut, Rested, Daily) | must stay wall |

Rule to adopt: **durations and timeouts that never leave the process use a
monotonic clock; anything persisted, logged as a time of day, compared
across restarts, or calendar-driven stays `current_time`/wall.**
`current_time` itself must stay wall-clock (it is written to every file).

#### 7.2 Synchronous work on the game loop (inventory)

| work | where | frequency | measured / estimated | verdict |
| --- | --- | --- | --- | --- |
| player save: temp write, `fflush`+`fsync`, rename, dir `fsync` | `save_char_obj` (`src/save.c` ~1020) -> `durable_commit` (`src/recovery.c` ~197) | every command that changes kept state (STASH, quest, craft, death...), autosave staggered `AUTOSAVE_CYCLE_TICKS` 5 (`src/update.c` ~1464, ~2093) | 4-25 ms per command that saves (7.0) | keep synchronous: DURABLE_FAILED/UNCERTAIN drive rollbacks (craft, ACCEPT, RAISE DEAD, STASH TAKE, DELETE) |
| snapshot per save (throttled 1/min) + milestones; prune lists and sorts the player's versions dir once | `snapshot_prune` / `snapshot_prune_pass` (`src/save.c` ~518-593), `snap_newest_scan` ~317 | with saves | synced tree: 12 version dirs, max 60 files/dir; scan is trivial at that size | keep; measure only |
| corpse records, durable, within a second of change; directory walks at refresh/boot | `corpse_registry_update` (`src/corpses.c` ~1195-1212), `opendir` at ~363, ~1398, ~1629, ~1652, ~1707 | per change, coalesced per second | unmeasured; low volume | keep; time it in 7.3 |
| journal trims: read whole file, copy newest half to `.tmp`, `temp_file_commit` | `journal_trim` (`src/playlog.c` ~194), `progress_trim` (~1027), `channel_journal_trim` (`src/act_comm.c` ~677), `login_journal_trim` (`src/comm.c` ~5358) | once per KEEP lines (play.tsv: 15,000) | play.tsv 3.4 MB synced; a trim reads ~6 MB, writes ~3 MB, inside whichever command crosses the line | unmeasured; candidate (7.5) |
| ledger appends with fsync | `src/recovery.c` (6 `fsync`) | milestones, receipts | small | keep |
| trust store append/rewrite | `src/guardstore.c` (1 `fsync`), `conn_guard_tick` retry every 300 s (`src/connguard.c` ~626) | logins, 5-minute retry | small | keep |
| `log_string`: `fprintf(stderr)` + line-buffered `toc.log` | `src/db.c` ~6694 | every log line | stderr to journald can block if journald stalls; `toc.log` is 18.9 MB and never trimmed by the game | watch; rotation is host-side (7.7) |
| queue polls: `stat` per pulse, then lock/stage/truncate | `process_web_admin_queue` (`src/comm.c` ~5168), `oracle_process_queries` (`src/oracle.c` ~1172) | 4 stats/s each | negligible | keep |
| area save (ASAVE/RSAVE), help/listing output (CHANGES ALL, ACHIEVEMENTS, WALKTO lists) | `save_area_full` (`src/db.c`), pagers | staff/rare | unmeasured, CPU-only | keep; benchmark once (7.4) |
| player backup archive | `backup_launch` (`src/update.c` ~268) | 4-hourly, daily | was 250-600 ms; now detached | done |

#### P7.1 Make every stall row say whether the game worked or waited (S)

- Exists: stall row (total, slowest phase, slowest command, players,
  suppressed count) from `playlog_pulse_end`.
- Gap: a row cannot tell CPU work from waiting (fork, page faults, I/O,
  descheduling, a clock step); the backup stalls were blamed on idle
  phases and found only by matching timestamps.
- Proposal: `getrusage(RUSAGE_SELF)` at `playlog_pulse_begin` (POSIX,
  Linux and macOS); a stall row appends one trailing column
  `cpu Nms majflt N invcsw N` (readers that stop early keep working).
  Split "input" with four static-string marks: `queues` before
  `process_web_admin_queue`, `poll` before `select`, `read` after
  `init_descriptor`, `commands` before the command loop.
- Files: `src/playlog.c`, `src/comm.c` (marks only),
  `tools/log_report.py`, `tests/test_playlog_deep.py`.
- Compatibility: additive; new phase names also appear in BUG context and
  `crash.log` (intended). Rollback: revert.
- Acceptance: a test-only fault point (`TOC_FAULT_FILE` style, e.g.
  `slow-queue`) that sleeps 300 ms in the queue stretch yields a row
  naming `queues` with `cpu` under 50 ms; a busy-loop variant yields
  `cpu` of 250 ms or more. Both builds.

#### P7.2 An hourly pulse summary row: latency below the stall line (S)

- Gap: with 0-2 players, 20-200 ms regressions (a slow save, a big trim)
  leave no trace.
- Proposal: a fixed histogram of pulse totals (0-10, 10-25, 25-50,
  50-100, 100-250, 250+ ms), max pulse, save count and max save ms
  (`playlog_save_timed(ms)` called once in `save_char_obj` after
  `durable_commit` returns; status untouched), written hourly and at
  shutdown as kind `pulse` -- numbers only, at most 24 rows a day.
- Files: `src/playlog.c`, `src/save.c` (one call), `tools/log_report.py`.
- Acceptance: with `TOC_PULSE_SUMMARY_SECS=5` (test knob) and a Z fixture
  typing SAVE ten times, one `pulse` row whose buckets sum to the pulses
  run and whose save count is at least 10 (autosave may add). Rollback:
  revert.

#### P7.3 Monotonic clock for pacing, watchdog and measurements (S)

- Exists: monotonic only in `write_raw_to_descriptor` and `dnsasync.c`.
- Gap (7.1): a backward wall-clock step (timesyncd/chrony step) freezes
  the pulse sleep for the size of the step and can starve the systemd
  watchdog; measurements go negative or huge.
- Proposal: `src/monoclock.c` (no `merc.h`; `_POSIX_C_SOURCE` before any
  header, like `dnsasync.c`; `CMakeLists.txt` entry):
  `long mono_ms(void)`, CLOCK_MONOTONIC in ms since first call plus 1
  (never 0). One commit each: (1) pacing deadline in `game_loop_unix`,
  with `time(&current_time)` left exactly where it is; (2) watchdog
  interval; (3) `playlog_now_ms` (callers only subtract;
  `fight_began_ms` is memory only); (4) `interpret()` timing; (5)
  `dnsasync.c` job age. Deliberately left wall-clock, and said so in the
  commit: persisted guard/lockout epochs, corpse/ledger/save times,
  quests, rested, holiday, oracle daze.
- Compatibility: no persisted value changes. Rollback: per commit.
- Acceptance: `tests/test_monoclock.c` (never 0, non-decreasing); a live
  test with a test-only `TOC_CLOCK_OFFSET_FILE` (read like
  `TOC_DATE_FILE`, offsetting the wall clock the loop reads) stepped back
  120 s mid-run: TIME still answers within one second and the watchdog
  ping count (shown in staff DNS or PERF) keeps rising. Both builds.

#### P7.4 Focused benchmarks, on demand, never in routine CI (M)

- Exists: `tools/class_bench.py` (disposable worlds, Z fixtures, staff
  ADVANCE) is the model; `MudClient.sync` measures replies.
- Gap: no repeatable numbers for save, prune, corpse write, trim,
  listings, area save.
- Proposal: `tools/perf_bench.py`, each case in a disposable `area/`
  copy with pre-grown state: (1) 50 SAVEs of a Z fixture with a 500-object
  stash and 60 snapshots; (2) the command that crosses
  `PLAY_JOURNAL_MAX` in a pre-filled `play.tsv`; (3) a milestone with
  2,000 snapshot files; (4) death of a Z fixture carrying 300 objects;
  (5) CHANGES ALL, ACHIEVEMENTS ALL, WALKTO AREAS, paging on/off; (6)
  ANEW + 500 MCREATE/OCREATE + ASAVE. Report p50/p99/max (client wall
  time plus P7.2's server-side save ms). Optional staff `PERF` (L5,
  read-only, one screen): last hour's histogram, worst stall, save
  count/max, monotonic uptime.
- Acceptance: two runs on one machine agree within 25% at p50; the repo
  is clean afterwards apart from the documented `log/` artefacts.

#### P7.5 Bounded journal trims (S; only if P7.4 case 2 exceeds 50 ms)

- Exists: four copy-the-newest-half trims (7.2).
- Proposal: rotate instead of copy -- at MAX lines rename `play.tsv` to
  `play.tsv.1` (replacing the old `.1`) and start afresh: one `rename`.
  Readers (`tools/log_report.py`; dashboard `FollowedFile` already
  follows inode changes) read `.1` then the live file. A new runtime file
  must be named in the five places `dpsboard.txt` is (`.gitignore`,
  `toc-state-sync`, `toc-deploy` runtime list, `validate.yml`
  `paths-ignore`, `tests/live_mud.py` filter), with a test. A detached
  child cannot trim safely: the game keeps appending.
- Acceptance: P7.4 case 2 under 5 ms; `log_report.py` totals identical
  across a rotation in a test that writes past MAX. Rollback: revert; a
  stray `.1` is harmless.

#### P7.6 A worker contract for future offloading (S, documentation)

- Models: `src/dnsasync.c` (no `merc.h`, two bounded queues, plain data,
  results matched on the game thread by `dns_serial`, cancel at close)
  and `backup_launch` (double fork, fds closed, niced, reports via log).
- Rules to add to AGENTS: (1) a worker gets copies (strings, numbers,
  paths, byte snapshots), never `CHAR_DATA`/`OBJ_DATA`/
  `DESCRIPTOR_DATA` pointers or list access; (2) queues are bounded and a
  full queue refuses at submit; (3) results are applied at the top of a
  pulse by id, dropped if the requester is gone; (4) **accepted is not
  done**: saves, snapshots, milestones, ledger, corpse records and
  receipts stay on the game thread because callers branch on
  DURABLE_OK/FAILED/UNCERTAIN before telling the player or moving objects
  (`player_milestone_required`, `craft_commit`, `corpse_give_to_owner`,
  `stash_take_commit`); (5) suitable: compressing closed logs, reports
  over immutable inputs, archive checks, DNS.
- Candidates today: none. Compress rotated journals host-side
  (logrotate) if wanted.

#### 7.7 Not worth its cost for this game (say no)

- Async or threaded player saves, io_uring, a write-behind cache: breaks
  DURABLE_* contracts for a 4-25 ms cost paid a few times a minute.
- A database (SQLite/Postgres) for players, corpses or the ledger.
- epoll/kqueue in place of `select`: `new_descriptor` already refuses
  descriptors at `FD_SETSIZE`; player counts are single digits.
- A metrics stack (Prometheus/Grafana), tracing frameworks, continuous
  profiling. The journal + `log_report.py` + ad-hoc `perf` on the host
  (owner's desktop session) cover it.
- A thread pool for game logic, lock-free queues, a second DNS cache.
- Rewriting `log_string` around a ring buffer: one `fprintf` per line;
  revisit only if a stall row ever blames logging. Host-side logrotate
  with `copytruncate` for `log/toc.log` (18.9 MB, never trimmed; the game
  holds it open in append mode, so copytruncate is safe) is the cheap
  answer and lives in deploy, not the game.

---------------------------------------------------------------------------

### 8. Safer Input And Persistence Boundaries

#### 8.0 Inventory (counts in `src/*.c`, working tree)

| call | sites | files | notes |
| --- | --- | --- | --- |
| `atoi(` | 116 | 24 | act_wiz.c 45, build.c 17, save.c 8, act_comm.c 8, act_info.c 6, edit.c 5, act_obj.c 4, maxload.c 3 |
| `atol(` | 10 | 6 | |
| `strtol(` | 18 | 11 | about half check `end`/`ERANGE`; several pass `NULL` end (env knobs) |
| `strtoul(` | 2 | 2 | |
| `sscanf(` | 36 | 9 | width-limited `%Ns` truncates silently |
| `is_number(` | 103 | 18 | |
| `number_argument(` | 11 | 5 | `atoi` before the dot |
| `fread_number(` | 243 | 5 | `int`, exits on bad format, overflows silently |
| `fread_long(` | 42 | 3 | same shape, `long` |
| `fread_flag(` | 29 | 1 | no minus sign (documented) |
| `exit(` in `src/db.c` | 43 | | loader fail-fast paths, reached from player loads too |

`mult_argument` does not exist in this tree (BUY counts parse
themselves).

Strict helpers that already exist (reuse, do not reinvent):
`parse_long_value`/`parse_positive_int` (`src/act_obj.c` ~57-85, static;
DEPOSIT/WITHDRAW/bank paths ~7781, ~7962, ~8275), the coin parser
(`src/act_obj.c` ~2932), `pkill.c` ~206, `achievement_set_token`
(`src/achievements.c` ~1975: digits only, ERANGE, max id),
`guardstore.c` ~238/~337 and `loginlock.c` ~261 (whole-record checks),
the wizinfo level in `process_web_admin_action` (`src/comm.c` ~5129), and
the non-exiting shape scanners `scan_number`/`scan_word`/`scan_string`/
`scan_stash_object` (`src/save.c` ~2570-2660) used by PRESTORE STASH.

#### 8.1 Representative defects (each verified by reading)

Network boundary:
- `telnet_note_ttype` (`src/telnet_proto.c` ~313):
  `d->client_mtts = atoi(value + 5)` on client-supplied text; a long
  digit string is undefined behaviour in `atoi` (glibc: `(int)strtol`,
  so 4294967360 reads as 64 = screen reader). Feeds `color_code`
  (`src/color.c` ~125) and staff displays.
- Env knobs with `strtol(opt, NULL, 10)`: `login_idle_sweep`
  (`src/comm.c` ~946), `connguard.c` ~144, `loginlock.c` ~119,
  `dnsasync.c` ~122. Test-only, but junk silently becomes 0 or a prefix.

Queue/file boundary:
- Webadmin queue (`process_web_admin_queue`, `src/comm.c` ~5168-5260):
  already good -- locked, staged, overlong lines dropped with a BUG,
  wizinfo level strict. The `command|...` payload goes to the
  interpreter, so its numbers inherit the command parsers below.
- `restores_boot` (`src/restores.c` ~165): `sscanf("%31s %15s %7s %47s
  %63s")` silently truncates an over-long token and reads its remainder
  as the next field; a line longer than the `fgets` buffer is read as
  two lines. Word checks (`restore_word_ok`) catch most consequences.
- `src/act_wiz.c` ~11626-11630: `atoi(line + 5)` etc. reading Level/
  Tru/Creator from a snapshot text line for PRESTORE identity.
- `fread_number` (`src/db.c` ~4904): `int` accumulates with no overflow
  check (UB), `exit(1)` on a non-digit, `isspace(c)` on a `char` from
  `getc` (negative for Latin-1 bytes). Called for player files through
  `fread_char`'s `KEY` macro (`src/save.c`, e.g. `Comm` at ~3634): **one
  malformed numeric token in any player file takes the whole game down at
  that player's name prompt** (`load_char_obj` runs at CON_GET_NAME), and
  again at the next login after restart. Saves are atomic
  (`durable_commit`), so the realistic sources are hand edits, git
  restores (`restores.dat import`), and future format changes.
- `Comm %ld` written (`src/save.c` ~1404), read with `fread_number`
  (`int`): bit `ff` (0x80000000) would not round-trip. Relevant to P9.1:
  a new COMM bit must be `ee` or below, or the read must become
  `fread_long`.

Command boundary:
- `is_number` (`src/interp.c` ~2314) accepts a lone `+` or `-`, has no
  length bound, and calls `isdigit(*arg)` on plain `char` (UB for
  Latin-1 bytes -- though input is filtered to `isprint` in the C
  locale, see 9.0).
- `number_argument` (`src/interp.c` ~2337): `atoi` before the dot;
  `4294967297.sword` is item 1.
- WIMPY (`src/act_info.c` ~4355): `wimpy ten` sets 0 silently.
- ROLL (`src/act_comm.c` ~1543): `atoi` on both sides of `d`; range
  checked after, so wraparound values can pass (`4294967298d6` rolls 2d6).
- ADVANCE (`src/act_wiz.c` ~3499) and TRUST (~3613): `atoi` then range;
  same wraparound (staff only, rank-gated; low risk, but it is the
  pattern).
- JAIL (`src/act_wiz.c` ~623-679): `atoi(arg2) > 30` checked, negative
  not; `current_time + atoi(arg2)*24*60*60` overflows `int` for large
  negative input.
- Good counter-examples to copy: `src/act_obj.c` ~5229 and
  `src/act_info.c` ~4208 (`strlen(arg) > 3 || (count = atoi(arg)) < 1`),
  `src/act_move.c` ~1699 (length cap before `atoi`), `src/quest.c` ~534.

#### P8.1 One strict parsing module with a C unit test (S)

- Proposal: `src/numparse.c`, no `merc.h` (pattern of
  `src/combat_rules.c`/`src/holiday_rules.c`), with:
  - `NUMPARSE_RESULT num_parse_long(const char *s, long lo, long hi,
    long *out)` returning `NUM_OK`, `NUM_EMPTY`, `NUM_NOT_NUMBER`
    (includes a lone sign, trailing junk), `NUM_RANGE` (ERANGE or outside
    lo..hi). Decimal only, optional leading sign, no whitespace.
  - `num_parse_int` wrapper (bounds within INT_MIN..INT_MAX).
  - `const char *num_refusal(NUMPARSE_RESULT r, long lo, long hi, char
    *buf, size_t size)`: "That is not a number." / "Choose a number from
    1 to 30." -- ASCII, `\n\r` added by callers.
  - `num_parse_dotted(const char *arg, int *count, char *rest, size_t
    size)` for `N.keyword` with the count bounded 1..`NUM_DOTTED_MAX`
    (e.g. 9999).
  - character tests always through `(unsigned char)`.
- Files: `src/numparse.c`, `src/numparse.h`, `CMakeLists.txt`,
  `tests/test_numparse.c` + a Python wrapper module that compiles and runs
  it (as `tests/test_combat_rules.c` is run).
- Acceptance: exhaustive table: "", "+", "-", "0", "-0", "007", "1x",
  " 1", "1 ", "2147483647", "2147483648", "-2147483649",
  "9223372036854775808", 64-digit strings, Latin-1 bytes; both builds,
  `-fsanitize=undefined` clean.
- Rollback: unused module, revert.

#### P8.2 Adoption order, one boundary per commit (S each, M total)

1. Network: MTTS (`telnet_proto.c` ~313) -> `num_parse_long(.., 0,
   65535)`; on failure leave `client_mtts_known` false. Env knobs ->
   strict, bad value logged once and the default used.
   Test: `tests/test_mudlet_extras.py` gains a TTYPE `MTTS 4294967360`
   case asserting DNS LIST does not show "screen reader".
2. Queue/files: `restores.dat` -- reject a line whose token exceeds its
   field (scan with `%n` and compare lengths, or tokenise with
   `strtok_r` into bounded copies) and a line longer than the buffer
   (log "line not understood", skip to newline, as the queue does).
   PRESTORE identity lines (`act_wiz.c` ~11626) -> strict.
3. Commands, highest player exposure first: `number_argument`, then
   `is_number` callers that feed `atoi` into a multiplication or index
   (JAIL, SET, ROLL, WIMPY, HISTORY count `act_comm.c` ~1081, NOTE READ
   numbers ~2221/~2323/~2552, AQUEST counts), then the staff command
   files (`act_wiz.c`, `build.c`). Each refusal goes through
   `num_refusal` and says the allowed range. Behaviour for every input
   that was valid before is unchanged (assert in tests).
- Compatibility: commands that used to accept junk silently now refuse
  with a message. Owner rule "a refusal is not a miss" is satisfied.
  `is_number` itself is not changed in place (103 callers; some rely on
  the lone-sign quirk unknowingly) -- add `is_number_strict` and migrate.
- Rollback: per-commit revert; no persisted format changes.
- Acceptance per commit: a live test with a Z fixture typing the old
  junk (`wimpy ten`, `roll 4294967298d6`, `get 4294967297.sword`,
  `history 99999999999`) gets the refusal text; the valid forms keep
  their old replies (`MudClient.must`). `test_command_guessing` and
  `test_help_keywords` unchanged.

#### P8.3 Player-file loads that refuse instead of exiting (M)

- Exists: fail-fast `exit(1)` in the `fread_*` family (`src/db.c`
  ~4904-5220), right for boot-time areas. PRESTORE STASH pre-validates
  with the non-exiting `scan_*` readers (`src/save.c` ~2570) and
  `read_objects_aside` (~3025). `load_char_obj` has no guard.
- Proposal: a "soft" mode for player-file reads only.
  `fread_soft_begin()`/`bool fread_soft_end()` wrap `load_char_obj`
  (which `offline_player_load` uses), `corpse_file_read` and the
  snapshot readers. In soft mode a bad number logs one BUG naming the
  file, consumes the token to the next blank (guaranteed progress: the
  infinite-loop risk), returns 0 and sets the flag; digits past the type
  set the flag and clamp; `fread_word`/`fread_string` overflow likewise.
  A flagged load frees the copy through the existing incomplete-load
  path; the login answers "Your character file could not be read; staff
  have been told." with a WIZINFO naming only the file; offline callers
  (GRANTPSI, STASH LINK/OF/TAKE, UNDENY, RESETPWD, PRESTORE) refuse with
  the same reason. **The file is never saved over**: the copy never
  reaches CON_PLAYING and `save_dropped_player` already refuses a
  connection not in the game. Boot stays fail-fast.
- Files: `src/db.c`, `src/save.c`, `src/comm.c` (nanny),
  `src/act_wiz.c`, `src/act_obj.c`, `src/corpses.c` (offline callers
  already handle a NULL load).
- Risks: objects made mid-load must not stay on `object_list`; reuse the
  vanished-container unwind (`rgObjNest`, `tests/test_lost_containers.py`).
  The `fread_flag` minus-sign rule is unchanged.
- Rollback: revert; soft mode off is today's behaviour.
- Acceptance: `tests/test_pfile_soft_load.py` (also in
  `SANITIZE_MODULES`): Z fixture files with `Levl 12x`,
  `BankCP 99999999999999999999999`, a truncated `#O` record, and a
  non-digit after `AchCount <name>`. Each time the server stays up (TIME
  answers on another connection), the login is refused with the message,
  the file's bytes and mtime are unchanged, no snapshot or ledger record
  appears, and another fixture logs in normally. Well-formed P8.4 corpus
  files load identically. Both builds; ASan/UBSan clean.

#### P8.4 Format versions and a compatibility corpus (M)

- Exists: `Vers 4` in player files (`src/save.c` ~1258) and corpse files
  (~3266); `ch->version < 2` branch (~2398); snapshot readers honour the
  snapshot's own `Vers` (~2838-2925). The ledger is self-describing (FNV
  `check` column, old 10-column records read; `src/recovery.c` header).
  Trust and lockout stores begin with a `#` header line
  (`src/guardstore.c` ~198, `src/loginlock.c` ~236) and skip comments.
  Unknown player keys are read and dropped ("no match").
- Gap: no checked-in corpus of old shapes (`tests/fixtures/` holds only
  `area/ztestfix.are`); each feature plants its own line.
- Proposal: (1) `tools/make_pfile_fixtures.py` generates synthetic
  Z-named files into `tests/fixtures/pfiles/`, one per historical shape
  AGENTS documents (no `Fixes` line, DES hash computed via libcrypt as the
  password tests do, `PsiGrant 1` pre-2026-10-27, `ListRemorts` pairs,
  `AchSet` ranges, `BlackMarket`, `ArmorLost`, `#STASH` after `#PET`, a
  `Nest` to a gone container), with an `INDEX.tsv` naming shape and date
  (fread_char accepts no comments); (2) `tests/test_pfile_compat.py`
  logs each in, asserts the documented migration, and checks save -> quit
  -> login -> save is stable apart from timestamps; (3) keep `Vers 4`,
  bump only when an existing key's reading changes, with a version table
  in `wiki/developer-guide.md`; (4) add `# v1` to the guard/lockout
  header lines at their next rewrite (readers already skip comments); a
  corpus entry for the old corpse-history end marker; (5) no wholesale
  migration without a demonstrated need.
- Acceptance: corpus passes on both builds; a source test requires every
  `KEY("...")` in `fread_char` to appear in a fixture or an allowlist
  with a reason. Rollback: test-only.
- Write-status rule for all of section 8: a parse refusal is a fourth
  outcome beside DURABLE_OK/FAILED/UNCERTAIN and changes nothing on disk
  -- no snapshot, no ledger record, no save. P8.3's test asserts it.

#### 8.6 Things that should wait (section 8)

- Converting all 116 `atoi` sites mechanically; do player-reachable and
  arithmetic-feeding ones first (P8.2), staff files next, the rest when
  touched.
- A strict area loader: boot is fail-fast by design and `--check-area`
  plus the Python validators guard it in CI.
- JSON or any new structured player-file format.

---------------------------------------------------------------------------

### 9. Accessibility And Client Compatibility

#### 9.0 What exists

- MTTS: `telnet_note_ttype` (`src/telnet_proto.c` ~267-315) reads the
  third TTYPE answer into `d->client_mtts`/`client_mtts_known`
  (`src/merc.h` ~765-770). Used by `color_code` (`src/color.c` ~99-125:
  a client without 256-colour or true-colour bits gets the nearest basic
  colour) and by `client_describe` (`src/gmcp.c` ~296-316), which prints
  "screen reader" for bit 64 **on staff screens only** (DNS LIST). The
  screen-reader bit changes nothing a player receives.
- COLOR on/off and palette by index (`src/color.c`, `do_color`
  `src/act_comm.c` ~294; `color_is_enabled` ~277; `col_disp_table`
  append-only). Saved COLOR OFF is never overridden at login.
- Prompt: `do_prompt` (`src/act_info.c` ~1096), default
  `"%C<%hhp %mm %vmv>%c "` (`src/comm.c` ~361), `COMM_PROMPT`,
  `COMM_COMPACT`, `COMM_BRIEF`, `COMM_TELNET_GA` (`src/merc.h`
  ~2110-2139). Bits `ee` and `ff` free in `comm`.
- Boxed displays: SCORE (`do_score`, `src/act_info.c` ~1603) is a
  three-column table of `| label value |` cells between `kader` rules;
  quest/achievement/note displays use rules (`+----`/`----` lines:
  act_comm.c 11, achievements.c 6, quest.c 18, act_info.c 3 by a rough
  grep). `alignment_bar` (`src/alignment.c` ~338) draws
  `dark [------|---*---] light` -- meaningless read aloud. Hyrule dungeon
  maps are ASCII art in extra descriptions.
- GMCP: Char.Vitals, Char.Status, Char.Affects, Char.Items, Char.Group,
  Char.Target, Char.Lag, Char.Quest, Char.Achievement, Char.Online,
  Room.Info, Room.Chars, Comm.Channel, Client.Map/GUI/Media,
  External.Discord, Char.Login (`src/gmcp.c`). No GMCP string carries
  colour (`gmcp_json_append_quoted`).
- Sound: Client.Media with SOUND OFF (`COMM_NOSOUND`).
- Browser client (`webadmin/static/client.html`): game output is
  `role="log"` with `aria-label` (implicitly polite live region),
  connection state, help, routes and toasts are `aria-live="polite"`,
  icon buttons have `aria-label`. Scrollback trimmed at
  `MAX_TERMINAL_CHARS = 350000` (`client.js` ~7, ~184). No screen-reader
  setting.
- Mudlet package (`mudlet/package/TimesOfChaos.xml`, `config.lua`): a GUI
  (gauges, chat, mapper) that installs itself; `TOCGUI OFF/ON` hides it;
  new characters are told so (`src/comm.c` ~4132). Nothing reads
  Mudlet's own screen-reader setting.
- Encoding: MSSP advertises `CHARSET ISO-8859-1`
  (`src/telnet_proto.c` ~406); no TELNET CHARSET (option 42)
  negotiation; output is ASCII by rule (`tests/test_source_ascii.py`).
  Input: `read_from_buffer` keeps only `isprint((unsigned char)c)`
  (`src/comm.c` ~2203) and the game never calls `setlocale`, so in the C
  locale **every byte >= 128 is silently dropped** ("cafe" with an accent
  arrives as "caf"; UTF-8 multibyte vanishes). The browser bridge encodes
  typed text as Latin-1 with `errors="replace"` (`webadmin/server.py`
  ~4880), so non-Latin-1 characters arrive as `?` and Latin-1 accented
  letters are then dropped by the game.

#### P9.1 An explicit SCREENREADER mode, opt-in, suggested by MTTS (M)

- Gap: nothing adapts output for speech users; MTTS bit 64 is known and
  ignored.
- Storage: `COMM_SCREENREADER` = `ee` (0x40000000), which fits the `int`
  `fread_number` reads for `Comm` (8.1); never `ff`. No new pfile key, so
  old files and old binaries are unaffected.
- Command `SCREENREADER [ON|OFF]`, level 0, placed after whatever `sc`/
  `scr` already reach (SCORE, SCAN; `tests/test_command_guessing.py`),
  HELP SCREENREADER at level 0, a `changes.dat` entry.
- Suggestion, never activation: on a real login (not a reconnect) with
  `client_mtts & 64`, flag off and not yet told (one memory bit in
  `pcdata`, saved with the flag word or as a CHANGES-style seen id), one
  line: "Your client says you use a screen reader. Type SCREENREADER ON
  for shorter, plainer output." Once per character.
- Effects, one commit each, all through one predicate
  `screenreader_on(ch)`:
  1. Prompt: if no custom prompt is set, `"%h hp %m mana %v mv> "` --
     no brackets, no colour tokens. A custom prompt is honoured as typed.
  2. Boxes: displays that draw tables get a plain branch -- SCORE as
     "Label: value." lines under short headings; quest, achievement and
     note panels without `----`/`+--+` rules. No generic stripping in
     `send_to_char` (it cannot tell art from content).
  3. Bars and art: `alignment_bar` -> number, side and tier in words;
     Hyrule ASCII maps -> exits and the dungeon's room count.
  4. GMCP Char.Status gains `"screenreader": true|false` for the clients.
- Files: `src/merc.h`, `src/interp.c`/`interp.h`, `src/act_info.c`,
  `src/alignment.c`, `src/comm.c` (suggestion, prompt default),
  `src/gmcp.c`, help area file, `area/changes.dat`; Mudlet package later.
- Compatibility: off by default; COLOR, palette and saved prompts
  untouched. Rollback: revert; the stored bit is then ignored.
- Acceptance: `tests/test_screenreader.py` with a Z fixture whose TTYPE
  answers end `MTTS 64`: one suggestion at first login, none at the
  second; the flag survives quit/login; SCORE output has no `|` and no
  line made only of `-`/`+`/`=`, and fits one default page; ALIGNMENT
  shows a number and a word; the prompt has no `<`; checked with COLOR
  ON/OFF and paging on/off. A source test lists the converted displays
  and asserts each asks `screenreader_on`. Both builds.

#### P9.2 Text equivalents everyone benefits from (S, before P9.1)

- `alignment_bar` gains the number and tier in words on the same screen
  (already partly there in ALIGNMENT output -- verify, then add only what
  is missing).
- A source audit (`tests/test_colour_meaning.py`, grep-level): flag
  `{HH`-wrapped single words in status displays where the word itself is
  not the state (colour carries meaning). Fix the handful found by adding
  the state word. Works for COLOR OFF users today.
- Acceptance: the audit test lists zero unexplained hits; COLOR OFF
  output of SCORE, AFFECTS, EQUIPMENT, CONSIDER names every state in
  words.

#### P9.3 Input encoding: deliberate conversion at the boundary (S/M)

- Policy (proposal): **the game stores and sends ASCII only for
  anything players type.** Area files stay Latin-1 and are never
  converted; output stays ASCII by test. Input is converted once, at
  `read_from_buffer`, instead of silently losing bytes:
  - Decode the line as UTF-8 if it is valid UTF-8 and contains a
    multibyte sequence; otherwise treat bytes >= 128 as Latin-1.
  - Transliterate letters with a fixed table to ASCII (e with accent ->
    e, n with tilde -> n, sharp s -> ss, typographic quotes/dashes ->
    ' " -), the same table the dashboard queue uses for typographic
    punctuation (AGENTS "dashboard queue payloads are ASCII"); share the
    table (Python side already has it).
  - Anything else becomes `?`, and the player is told once per session:
    "Characters outside plain English letters were replaced."
  - Passwords: never transliterate the password prompts' input (the
    hash must keep the bytes it always got: today high bytes are dropped
    before hashing, so keep exactly that behaviour for password states,
    or existing passwords containing them would stop matching). Names
    stay alphabetic ASCII (unchanged).
- Browser bridge: send UTF-8 bytes instead of Latin-1-with-replace only
  after the game decodes UTF-8 (otherwise keep it); one commit after the
  C side, with the `?v=` bump rule if any static file changes.
- Files: `src/comm.c` (`read_from_buffer`), new `src/translit.c` (no
  `merc.h`, C unit test), `webadmin/server.py` (later).
- Risks: alias bodies, notes, titles and channel text gain letters that
  used to vanish; ASCII output rule still holds. Telnet IAC handling runs
  before this (bytes 255 never reach it) -- confirm ordering in
  `telnet_proto.c`.
- Acceptance: `tests/test_input_translit.py` sends Latin-1 `caf\xe9`,
  UTF-8 `caf\xc3\xa9`, UTF-8 CJK, and a password containing `\xe9`;
  SAY echoes `cafe`, `cafe`, `??`+notice; an existing Z fixture whose
  password was set with the high byte still logs in. `test_source_ascii`
  unchanged.

#### P9.4 TELNET CHARSET negotiation (WAIT)

- With ASCII-only output and P9.3's input conversion, negotiating
  UTF-8 or Latin-1 changes nothing a client displays. It adds a protocol
  state machine to `telnet_proto.c` and needs a real Mudlet test
  [mudlet]. Revisit only if the game ever sends non-ASCII text; then
  negotiate (RFC 2066) UTF-8, fall back to ASCII, and convert at
  `write_to_buffer`'s single exit -- never in area files.
- Keep MSSP `CHARSET` honest: if P9.3 lands, ASCII is the truthful
  value; changing what crawlers see is harmless but optional.

#### P9.5 Client support matrix (proposal for `wiki/game-client-guide.md`)

| capability | plain Telnet (port 9000) | Mudlet (9000; Secure box planned) | browser (`/client`, 9001 WebSocket bridge) |
| --- | --- | --- | --- |
| transport security | none | none today; TLS port planned and on hold (SECURITY.md "Planned: A TLS Player Port", nginx stream + PROXY v1, outside the game loop) | plain HTTP/WS on the live host today; HTTPS is a separate project |
| colour | COLOR ON/OFF, 16/256/true colour downgraded by MTTS | same; palette names mirrored in `GAME_COLOUR` | same; themes draw 0-15, exact 256/true colour |
| output charset | ASCII | ASCII | ASCII (decoded as Latin-1) |
| input charset | high bytes dropped today (P9.3) | same | Latin-1 with `?` replacement, then dropped (P9.3) |
| GMCP | if negotiated | full package | not used (client parses text) |
| screen reader | P9.1 mode; terminal handles speech | Mudlet advertises MTTS 64 when its screen-reader option is on [mudlet]; P9.1 + TOCGUI OFF | `role=log` live region; P9.1 mode; client toggle to suppress decorative panels |
| sound | none | Client.Media, SOUND OFF | none |
| login convenience | typed | Char.Login credentials (never logged) | typed; password field masked |
| prompt | `%` tokens, COMM_PROMPT, GA | same; GA for triggers | same |

#### P9.6 Browser and Mudlet follow-ups (S each, after P9.1)

- Browser: a "Screen reader" checkbox that sends `screenreader on`, stops
  echoing typed commands into the log region, and batches bursts into one
  live-region node per pulse; bump `?v=`; JS unit test in the
  `tests/test_ansi_web.js` style.
- Mudlet: on Char.Status `screenreader: true`, draw no gauges/chat panes
  unless TOCGUI ON was typed; three version strings bumped, package
  rebuilt; Lua check in `test_mudlet_assets`.

#### 9.7 Things that should wait (section 9)

- CHARSET negotiation (P9.4); per-player locales or translations.
- Automatic activation from MTTS (opt-in only); a separate accessible
  web client.
- Rewriting every boxed display at once: SCORE, ALIGNMENT, AFFECTS,
  EQUIPMENT, quest and achievement panels first, others when touched.

---------------------------------------------------------------------------

### Cross-cutting dependencies and order

1. P7.3 (pacing/watchdog hazard) and P8.3 (one bad file downs the game)
   first: both independent and both availability fixes.
2. P8.1 before P8.2; P8.4's corpus before P8.3 merges and before any
   `Vers` change.
3. P7.1/P7.2 measurement before P7.4/P7.5 decisions.
4. P9.2 -> P9.1 -> P9.6; P9.3 independent (share the transliteration
   table with the dashboard queue's).

Owner constraints respected throughout: shared admin credential and
`WEB_ADMIN_TOKEN` unchanged; no individual staff accounts or MFA; staff
ranks, wizinvis notice levels, recovery receipts and DURABLE_* semantics
untouched; deploy behaviour (`toc-deploy`, auto-deploy markers) untouched;
no new runtime file without the five-place listing rule.
