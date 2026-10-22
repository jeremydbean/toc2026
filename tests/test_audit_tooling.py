"""Installer, deploy and play-client faults from the audit of 2026-10-22.

Each test runs the real script or function -- toc-deploy, toc-restore,
toc-game-recovery, toc.sh and toc.ps1, toc_common.sh and .ps1,
toc_native.sh, client.js -- with only the host stubbed: no service is
started, nothing is fetched, and every character is synthetic.

 7. toc-deploy killed by a signal never rolled back: dash runs no EXIT
    trap for a shell a signal kills.
21. The play client showed a line break twice when a frame ended between
    the "\\n" and "\\r" of one.
22. A first run that failed part way through moving an old installation's
    data out of the checkout was taken for a new installation next time,
    and the partial copy kept.
23. The native launcher took any live process with a recorded PID for the
    game: stop signalled it, start launched nothing.
24. toc-restore's "no characters" guard never fired ("0\\n0" is no number).
26. `update` refused after any restore, or with TOC_STATE inside the
    checkout, and advised removing the copy a restore sets aside.
27. `uninstall --purge` deleted whatever TOC_STATE named: the checkout,
    a folder holding it, the home folder, /.
28. toc-game-recovery never set the binary's owner: a literal "\\n" in
    the condition.
29. A quoted TOC_STATE named one folder to the launchers and another to
    Docker Compose, which takes the quotes off.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_deploy_failures as deploy_failures  # noqa: E402  (its stubs, not its tests)

DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-deploy"
RESTORE = ROOT / "deploy" / "toc-restore"
RECOVERY = ROOT / "deploy" / "windows-vm" / "toc-game-recovery"
COMMON = ROOT / "scripts" / "toc_common.sh"
NATIVE = ROOT / "scripts" / "toc_native.sh"
PWSH = shutil.which("pwsh")
NODE = shutil.which("node")


def scratch(test: unittest.TestCase, prefix: str) -> pathlib.Path:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=prefix))
    test.addCleanup(shutil.rmtree, tmp, True)
    return tmp


def write_stubs(bin_dir: pathlib.Path, stubs: dict[str, str]) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, body in stubs.items():
        path = bin_dir / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def make_checkout(tmp: pathlib.Path, gitignore: str = "/state/\n.env\n") -> pathlib.Path:
    """A git checkout carrying the launcher scripts, a tracked character
    and a source file, as test_install_layout builds it."""
    repo = tmp / "toc"
    (repo / "scripts").mkdir(parents=True)
    for name in ("toc_common.sh", "toc_native.sh", "toc_common.ps1"):
        shutil.copy(ROOT / "scripts" / name, repo / "scripts" / name)
    shutil.copy(ROOT / "toc.sh", repo / "toc.sh")
    shutil.copy(ROOT / "toc.ps1", repo / "toc.ps1")
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / ".gitignore").write_text(gitignore)
    for d in ("player", "gods", "heroes", "log"):
        (repo / d).mkdir()
        (repo / d / "Tracked").write_text(f"{d} Tracked~\n")
    (repo / "src").mkdir()
    (repo / "src" / "game.c").write_text("int main(void) { return 0; }\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def bash(repo: pathlib.Path, script: str, **env: str) -> subprocess.CompletedProcess:
    run_env = dict(os.environ, TOC_REPO_ROOT=str(repo), **env)
    return subprocess.run(
        ["bash", "-c", f'set -euo pipefail; source "{repo}/scripts/toc_common.sh"; '
                       f'source "{repo}/scripts/toc_native.sh"; {script}'],
        cwd=repo, env=run_env, capture_output=True, text=True, timeout=120)


def pwsh(script: str, cwd: pathlib.Path, **env: str) -> subprocess.CompletedProcess:
    run_env = dict(os.environ, **env)
    return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
                          cwd=cwd, env=run_env, capture_output=True, text=True, timeout=180)


# ---------------------------------------------------------------- 7

@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class DeploySignalTests(unittest.TestCase):
    """toc-deploy under /bin/sh with test_deploy_failures' stubs, and one
    command that signals the deploy shell the way Ctrl-C, a dropped ssh
    session or `systemctl stop toc-auto-deploy` does."""

    def deploy(self, signalling: str, signum: int) -> tuple[int, str, str]:
        tmp = scratch(self, "toc-deploy-signal-")
        bin_dir, build, current = tmp / "bin", tmp / "build", tmp / "current"
        for d in (build / "area", current / "area", current / "log", current / "player"):
            d.mkdir(parents=True)
        stubs = dict(deploy_failures.STUBS)
        stubs[signalling] = (f'echo "{signalling} $*" >> "$STUB_LOG"; '
                             f'kill -{signum} $PPID; exit 0')
        write_stubs(bin_dir, stubs)
        merc = build / "merc"
        merc.write_text("#!/bin/sh\necho 'world check'\nexit 0\n")
        merc.chmod(0o755)
        log = tmp / "calls.log"
        log.write_text("")
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                   BUILD=str(build), CURRENT=str(current), STUB_LOG=str(log),
                   TOC_DEPLOY_LOCKED="1", TOC_ROLLBACK_DIR=str(tmp),
                   TOC_DEPLOY_ROLLBACK="1", STUB_HEALTHY="1")
        result = subprocess.run(["sh", str(DEPLOY)], env=env, capture_output=True,
                                text=True, timeout=60)
        return result.returncode, result.stdout + result.stderr, log.read_text()

    def test_a_deploy_killed_mid_install_rolls_back(self) -> None:
        for signum, status in ((signal.SIGTERM, 143), (signal.SIGHUP, 129),
                               (signal.SIGINT, 130)):
            with self.subTest(signal=signum.name):
                rc, output, calls = self.deploy("rsync", int(signum))
                self.assertEqual(rc, 10, f"rolled back and healthy:\n{output}\n{calls}")
                self.assertIn(f"INSTALL FAILED (status {status})", output)
                rsync = calls.index("rsync")
                self.assertIn("tar xzf", calls[rsync:], "the old code goes back")
                self.assertIn("systemctl start toc-game", calls[rsync:])
                self.assertIn("systemctl start toc-web", calls[rsync:])

    def test_a_deploy_killed_before_the_stop_touches_nothing(self) -> None:
        rc, output, calls = self.deploy("make", int(signal.SIGTERM))
        self.assertEqual(rc, 143, output)
        self.assertNotIn("systemctl", calls)
        self.assertNotIn("rsync", calls)

    def test_the_traps_are_in_place(self) -> None:
        text = DEPLOY.read_text()
        for sig, status in (("HUP", 129), ("INT", 130), ("TERM", 143)):
            self.assertRegex(text, r"(?m)^trap 'exit %d' %s$" % (status, sig))


# ---------------------------------------------------------------- 24

@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class RestoreGuardTests(unittest.TestCase):
    """deploy/toc-restore as a rehearsal (TOC_PREFIX outside /srv/toc)
    against a stand-in clone."""

    def restore(self, characters: list[str], versions: bool = False) -> tuple[int, str, str]:
        tmp = scratch(self, "toc-restore-guard-")
        prefix = tmp / "srv"
        build = prefix / "build"
        for d in (build / ".git", build / "area", build / "player", build / "gods",
                  build / "heroes", build / "log"):
            d.mkdir(parents=True)
        for name in characters:
            (build / "player" / name).write_text(f"Name {name}~\n")
        if versions:
            (build / "player" / "versions").mkdir()
        merc = build / "merc"
        merc.write_text("#!/bin/sh\necho 'world loads'\nexit 0\n")
        merc.chmod(0o755)
        log = tmp / "calls.log"
        log.write_text("")
        write_stubs(tmp / "bin", {
            "git": 'echo "git $*" >> "$STUB_LOG"; case "$*" in *rev-parse*) echo abc1234;; '
                   '*log*) echo 2026-10-22T00:00:00Z;; esac; exit 0',
            "make": 'echo "make $*" >> "$STUB_LOG"; exit 0',
            "rsync": 'echo "rsync $*" >> "$STUB_LOG"; exit 0',
        })
        env = dict(os.environ, PATH=f"{tmp / 'bin'}:{os.environ['PATH']}",
                   TOC_PREFIX=str(prefix), STUB_LOG=str(log))
        result = subprocess.run(["sh", str(RESTORE)], env=env, capture_output=True,
                                text=True, timeout=60)
        return result.returncode, result.stdout + result.stderr, log.read_text()

    def test_no_characters_stops_the_restore(self) -> None:
        for versions in (False, True):
            with self.subTest(only_a_versions_folder=versions):
                rc, output, calls = self.restore([], versions=versions)
                self.assertEqual(rc, 1, output)
                self.assertIn("NO CHARACTERS IN THE REPOSITORY", output)
                self.assertIn("   0 characters", output)
                self.assertNotIn("make", calls, "nothing is built or installed")

    def test_characters_pass_the_guard(self) -> None:
        rc, output, calls = self.restore(["Zalpha", "Zbeta"], versions=True)
        self.assertEqual(rc, 0, output)
        self.assertIn("   2 characters, 0 gods files", output)
        self.assertIn("rehearsal complete", output)


# ---------------------------------------------------------------- 28

@unittest.skipUnless(shutil.which("bash"), "needs bash")
class RecoveryOwnershipTests(unittest.TestCase):
    """toc-game-recovery's ownership block, cut from the script and run
    with id and getent standing in for a root shell on the host."""

    STUBS = r"""
id() {
    # As id(1): -u alone is this user, -u NAME an account; anything else
    # (an extra operand, such as a stray "n") is an error.
    if [ "$#" -eq 1 ] && [ "$1" = -u ]; then echo "$FAKE_UID"; return 0; fi
    if [ "$#" -eq 2 ] && [ "$1" = -u ] && [ "$2" = "$FAKE_USER" ]; then echo 1001; return 0; fi
    return 1
}
getent() { [ "$#" -eq 2 ] && [ "$1" = group ] && [ "$2" = "$FAKE_GROUP" ]; }
"""

    def own_flags(self, uid: str, user: str, group: str) -> str:
        text = RECOVERY.read_text()
        block = re.search(r"(?ms)^OWNER=.*?^own_flags=\(\)\n.*?^fi\n", text)
        self.assertIsNotNone(block, "the ownership block moved")
        script = self.STUBS + block.group(0) + 'printf "%s\\n" "${own_flags[*]-}"\n'
        result = subprocess.run(["bash", "-c", "set -eu\n" + script],
                                env=dict(os.environ, FAKE_UID=uid, FAKE_USER=user,
                                         FAKE_GROUP=group),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_root_with_the_account_sets_the_owner(self) -> None:
        self.assertEqual(self.own_flags("0", "toc", "toc"), "-o toc -g toc")

    def test_without_root_or_the_account_the_flags_are_dropped(self) -> None:
        self.assertEqual(self.own_flags("1000", "toc", "toc"), "")
        self.assertEqual(self.own_flags("0", "nobody-else", "toc"), "")
        self.assertEqual(self.own_flags("0", "toc", "other-group"), "")

    def test_no_literal_escape_in_the_script(self) -> None:
        for number, line in enumerate(RECOVERY.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            self.assertNotRegex(code, r"\\n\s+&&", f"line {number}: {line}")


# ---------------------------------------------------------------- 22

MIGRATION_HARNESS = r"""
toc_legacy_container() { return 1; }
# A copy that runs out of room on one directory, the first time only.
cp() {
    if [ -n "${FAIL_DIR:-}" ] && [ ! -f "$FAILED_ONCE" ]; then
        case "$*" in
            *"/$FAIL_DIR/."*) : > "$FAILED_ONCE"; echo "cp: No space left on device" >&2; return 1 ;;
        esac
    fi
    command cp "$@"
}
toc_configure_instance preserve
"""


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class MigrationRetryTests(unittest.TestCase):
    def old_install(self) -> pathlib.Path:
        repo = make_checkout(scratch(self, "toc-migrate-"))
        # The .env the installers wrote before the state folder: no TOC_MODE.
        (repo / ".env").write_text("MUD_PORT=9000\nWEB_ADMIN_TOKEN=abc\n")
        (repo / "player" / "Zold").write_text("Name Zold~\n")
        (repo / "heroes" / "plaque").write_text("Zold the brave\n")
        (repo / "log" / "toc.log").write_text("old log\n")
        return repo

    def test_a_failed_move_is_finished_by_the_next_run(self) -> None:
        repo = self.old_install()
        failed = repo.parent / "failed-once"
        first = bash(repo, MIGRATION_HARNESS, FAIL_DIR="heroes", FAILED_ONCE=str(failed))
        self.assertNotEqual(first.returncode, 0, "the failed copy is reported")
        state = repo / "state"
        self.assertIn("TOC_MODE=docker", (repo / ".env").read_text(),
                      "the scenario: .env no longer looks old")
        self.assertFalse((state / "heroes" / "plaque").exists(), "the scenario: a partial copy")

        second = bash(repo, MIGRATION_HARNESS, FAILED_ONCE=str(failed))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((state / "player" / "Zold").exists())
        self.assertEqual((state / "heroes" / "plaque").read_text(), "Zold the brave\n")
        self.assertEqual((state / "log" / "toc.log").read_text(), "old log\n")
        self.assertFalse((state / ".migrating").exists(), "the marker goes once the copy is whole")
        self.assertTrue((state / ".migrated-from-checkout").exists())
        self.assertTrue((state / ".layout").exists())

        # Once whole, never again: a later save is not overwritten.
        (state / "player" / "Zold").write_text("newer\n")
        third = bash(repo, MIGRATION_HARNESS, FAILED_ONCE=str(failed))
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual((state / "player" / "Zold").read_text(), "newer\n")

    def test_a_new_install_has_nothing_to_move(self) -> None:
        repo = make_checkout(scratch(self, "toc-migrate-new-"))
        r = bash(repo, MIGRATION_HARNESS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((repo / "state" / ".migrating").exists())
        self.assertEqual(list((repo / "state" / "player").iterdir()), [])

    @unittest.skipIf(PWSH is None, "PowerShell (pwsh) is not installed")
    def test_powershell_finishes_a_failed_move_too(self) -> None:
        repo = self.old_install()
        failed = repo.parent / "failed-once"
        script = r"""
$ErrorActionPreference = 'Stop'
. ./scripts/toc_common.ps1
function Test-TocLegacyContainer { return $false }
function Copy-Item {
    if ($env:FAIL_DIR -and -not (Test-Path -LiteralPath $env:FAILED_ONCE) -and
        ($args -join ' ') -match [regex]::Escape("/$env:FAIL_DIR/")) {
        Set-Content -LiteralPath $env:FAILED_ONCE -Value x
        throw 'No space left on device'
    }
    Microsoft.PowerShell.Management\Copy-Item @args
}
Initialize-TocInstance
"""
        first = pwsh(script, repo, FAIL_DIR="heroes", FAILED_ONCE=str(failed))
        self.assertNotEqual(first.returncode, 0, first.stdout + first.stderr)
        state = repo / "state"
        self.assertRegex((repo / ".env").read_text(), r"(?m)^TOC_MODE=docker")
        self.assertFalse((state / "heroes" / "plaque").exists(), "the scenario: a partial copy")

        second = pwsh(script, repo, FAIL_DIR="", FAILED_ONCE=str(failed))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue((state / "heroes" / "plaque").exists())
        self.assertTrue((state / "log" / "toc.log").exists())
        self.assertFalse((state / ".migrating").exists())


# ---------------------------------------------------------------- 23

@unittest.skipUnless(shutil.which("bash") and sys.platform != "win32", "needs bash")
class NativePidTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_checkout(scratch(self, "toc-native-pid-"))
        (self.repo / ".env").write_text("TOC_MODE=native\nTOC_STATE=./state\nTOC_SERVICE=none\n"
                                        "MUD_PORT=9\nWEB_ADMIN_ENABLED=0\n")
        self.state = self.repo / "state"
        for d in ("run", "log", "area"):
            (self.state / d).mkdir(parents=True)
        merc = self.state / "merc"
        merc.write_text("#!/bin/sh\nexit 0\n")
        merc.chmod(0o755)
        # The runner start launches: it records that it ran and waits.
        runner = self.repo / "scripts" / "toc_run_game.sh"
        runner.write_text('#!/bin/sh\necho "$$" > "$1/run/runner-started"\n'
                          'trap "exit 0" TERM\nwhile :; do sleep 1; done\n')
        runner.chmod(0o755)

    def spawn(self, argv: list[str]) -> subprocess.Popen:
        proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)

        def reap() -> None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        self.addCleanup(reap)
        return proc

    def stranger(self) -> subprocess.Popen:
        """A process that has nothing to do with the game, holding the
        number the game's PID file names -- as after a reboot."""
        proc = self.spawn(["sleep", "300"])
        (self.state / "run" / "game.pid").write_text(f"{proc.pid}\n")
        (self.state / "run" / "web.pid").write_text(f"{proc.pid}\n")
        return proc

    def test_stop_never_signals_a_stranger(self) -> None:
        proc = self.stranger()
        r = bash(self.repo, "toc_native_stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        time.sleep(0.3)
        self.assertIsNone(proc.poll(), "the unrelated process is still running")
        self.assertFalse((self.state / "run" / "game.pid").exists(), "the stale record goes")

    def test_stop_still_stops_the_game(self) -> None:
        runner = self.repo / "scripts" / "toc_run_game.sh"
        proc = self.spawn(["sh", str(runner), str(self.state), "9"])
        deadline = time.time() + 10
        while not (self.state / "run" / "runner-started").exists() and time.time() < deadline:
            time.sleep(0.05)
        (self.state / "run" / "game.pid").write_text(f"{proc.pid}\n")
        r = bash(self.repo, "toc_native_stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(proc.wait(timeout=20), 0, "the runner was asked to stop")

    def test_start_is_not_fooled_by_a_stale_pid(self) -> None:
        proc = self.stranger()
        r = bash(self.repo, "toc_native_start; sleep 1; cat \"$(toc_state_dir)/run/game.pid\"")
        self.assertEqual(r.returncode, 0, r.stderr)
        new_pid = int(r.stdout.split()[-1])
        self.addCleanup(lambda: os.kill(new_pid, signal.SIGKILL) if _alive(new_pid) else None)
        self.assertNotEqual(new_pid, proc.pid, "a new game was launched")
        started = self.state / "run" / "runner-started"
        deadline = time.time() + 10
        while not started.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(started.exists(), "the runner ran")
        r = bash(self.repo, "toc_native_pid_alive \"$(toc_state_dir)/run/game.pid\" && echo ALIVE")
        self.assertIn("ALIVE", r.stdout, "the game it launched counts as the game")
        r = bash(self.repo, "toc_native_stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(proc.poll())


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ---------------------------------------------------------------- 26

@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class CodeChangesTests(unittest.TestCase):
    def after_a_restore(self, state: str) -> pathlib.Path:
        repo = make_checkout(scratch(self, "toc-changes-"))
        (repo / ".env").write_text(f"TOC_MODE=docker\nTOC_STATE={state}\n")
        live = repo / state.removeprefix("./")
        (live / "player").mkdir(parents=True)
        (live / "player" / "Zrestored").write_text("Name Zrestored~\n")
        aside = repo / f"{state.removeprefix('./')}.before-restore-20261022-120000"
        (aside / "player").mkdir(parents=True)
        (aside / "player" / "Zoriginal").write_text("Name Zoriginal~\n")
        (repo / ".restore.Ab12Cd" / "state" / "player").mkdir(parents=True)
        (repo / ".env.from-backup").write_text("TOC_STATE=./elsewhere\n")
        (repo / ".env.before-restore").write_text("TOC_STATE=./elsewhere\n")
        return repo

    def test_a_restore_leaves_nothing_update_calls_code(self) -> None:
        for state in ("./state", "./data", "./nested/game-data"):
            with self.subTest(state=state):
                repo = self.after_a_restore(state)
                r = bash(repo, "toc_code_changes")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), "", "nothing here is code")
                (repo / "src" / "game.c").write_text("int main(void) { return 1; }\n")
                (repo / "src" / "new.c").write_text("/* new */\n")
                r = bash(repo, "toc_code_changes")
                self.assertIn("src/game.c", r.stdout)
                self.assertIn("src/new.c", r.stdout)
                self.assertNotIn("before-restore", r.stdout)

    def test_a_state_folder_outside_the_checkout_excludes_nothing_inside(self) -> None:
        repo = make_checkout(scratch(self, "toc-changes-out-"))
        (repo / ".env").write_text(f"TOC_STATE={repo.parent / 'data'}\n")
        (repo / "data").mkdir()
        (repo / "data" / "stray.c").write_text("/* not state */\n")
        r = bash(repo, "toc_code_changes")
        self.assertIn("data/", r.stdout)

    def test_the_repository_ignores_what_a_restore_leaves(self) -> None:
        for path in ("state.before-restore-20261022-120000/player/Zoriginal",
                     ".restore.Ab12Cd/state/player/Zrestored", ".env.from-backup",
                     ".env.before-restore"):
            with self.subTest(path=path):
                r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index",
                                    path], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{path} is not ignored")
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index",
                            ".env.example"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, ".env.example stays tracked")

    def test_update_does_not_advise_deleting_the_copy(self) -> None:
        for text in ((ROOT / "toc.sh").read_text(), (ROOT / "toc.ps1").read_text()):
            self.assertNotRegex(text, r"(?i)stash,? or remove")

    @unittest.skipIf(PWSH is None, "PowerShell (pwsh) is not installed")
    def test_powershell_agrees(self) -> None:
        repo = self.after_a_restore("./data")
        script = ". ./scripts/toc_common.ps1; Get-TocCodeChanges"
        r = pwsh(script, repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "", r.stdout)
        (repo / "src" / "game.c").write_text("int main(void) { return 1; }\n")
        r = pwsh(script, repo)
        self.assertIn("src/game.c", r.stdout)
        self.assertNotIn("before-restore", r.stdout)


# ---------------------------------------------------------------- 27

PURGE_HARNESS = r"""
REPO_ROOT="$TOC_REPO_ROOT"
eval "$(sed -n '/^uninstall() {/,/^}/p' "$TOC_REPO_ROOT/toc.sh")"
mode=docker
toc_docker_ready() { return 1; }
# Recorded, never run: a test of a purge that deletes / must not.
rm() { echo "RM $*" >> "$CALLS"; }
uninstall --purge --yes
"""


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class PurgeGuardTests(unittest.TestCase):
    def purge(self, state: str, home: pathlib.Path | None = None) -> tuple[subprocess.CompletedProcess, str]:
        tmp = scratch(self, "toc-purge-")
        repo = make_checkout(tmp)
        (repo / ".env").write_text(f"TOC_MODE=docker\nTOC_STATE={state}\n")
        calls = tmp / "calls.log"
        r = bash(repo, PURGE_HARNESS, CALLS=str(calls),
                 HOME=str(home if home else tmp / "home"))
        return r, calls.read_text() if calls.exists() else ""

    def test_a_state_that_is_or_holds_the_checkout_is_refused(self) -> None:
        home = scratch(self, "toc-purge-home-")
        for state, why in (("./", "is this checkout"), (".", "is this checkout"),
                           ("..", "holds this checkout"), ("./scripts/..", "is this checkout"),
                           ("/", "root of the file system"), (str(home), "your home folder"),
                           (" ", "TOC_STATE is empty")):
            with self.subTest(state=state):
                r, calls = self.purge(state, home=home)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("Not purging", r.stderr)
                self.assertIn(why, r.stderr)
                self.assertNotIn("RM", calls, "nothing is deleted")

    def test_the_games_own_folder_is_purged(self) -> None:
        for state in ("./state", "./data/state"):
            with self.subTest(state=state):
                r, calls = self.purge(state)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("RM -rf ", calls)
                self.assertIn(state.removeprefix("./"), calls)
        outside = scratch(self, "toc-purge-out-") / "toc-state"
        r, calls = self.purge(str(outside))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"RM -rf {outside} ", calls)

    @unittest.skipIf(PWSH is None, "PowerShell (pwsh) is not installed")
    def test_powershell_refuses_too(self) -> None:
        for kind in ("checkout", "parent", "home"):
            with self.subTest(state=kind):
                tmp = scratch(self, "toc-ps-purge-")
                repo = make_checkout(tmp)
                home = tmp / "home"
                home.mkdir()
                (home / "keep").write_text("mine\n")
                state = {"checkout": "./", "parent": "..", "home": str(home)}[kind]
                (repo / ".env").write_text(f"TOC_MODE=docker\nTOC_STATE={state}\n")
                write_stubs(tmp / "bin", {"docker": "exit 1"})
                r = subprocess.run(
                    [PWSH, "-NoProfile", "-NonInteractive", "-File", str(repo / "toc.ps1"),
                     "uninstall", "-Purge", "-Yes"],
                    cwd=repo, capture_output=True, text=True, timeout=120,
                    env=dict(os.environ, HOME=str(home),
                             PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}"))
                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("Not purging", r.stdout + r.stderr)
                self.assertTrue((repo / "src" / "game.c").exists(), "the checkout is kept")
                self.assertTrue((repo / ".env").exists())
                self.assertTrue((home / "keep").exists(), "the home folder is kept")


# ---------------------------------------------------------------- 29

@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "needs bash and git")
class QuotedEnvTests(unittest.TestCase):
    def repo_with(self, env: str) -> pathlib.Path:
        repo = make_checkout(scratch(self, "toc-env-"))
        (repo / ".env").write_text(env)
        return repo

    def test_matching_quotes_come_off_as_compose_takes_them_off(self) -> None:
        for written, read in (('"./data"', "data"), ("'./data'", "data"),
                              ('"./my data"', "my data"), ("./data", "data")):
            with self.subTest(written=written):
                repo = self.repo_with(f"TOC_STATE={written}\r\n")
                r = bash(repo, "toc_state_dir")
                self.assertEqual(r.stdout.strip(), f"{repo}/{read}", r.stderr)
        # Only one matching pair: a quote inside, or unmatched, stays.
        for written in ('"./data\'', '"', "a\"b\""):
            with self.subTest(written=written):
                repo = self.repo_with(f"TOC_STATE={written}\n")
                r = bash(repo, "toc_env_get TOC_STATE")
                self.assertEqual(r.stdout.rstrip("\n"), written)

    def test_what_toc_set_env_writes_reads_back_the_same_everywhere(self) -> None:
        for value in ("./state", "/srv/toc state", "a$b`c\\d", "ghcr.io/x/y:latest", "#hash"):
            with self.subTest(value=value):
                repo = self.repo_with("TOC_MODE=docker\n")
                r = bash(repo, 'toc_set_env TOC_STATE "$VALUE"; toc_env_get TOC_STATE; '
                               '( set -a; . "$TOC_ENV_FILE"; printf "%s\\n" "$TOC_STATE" )',
                         VALUE=value)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.split("\n")[:2], [value, value],
                                 "toc_env_get and a sourcing shell agree")
                self.assertIn("TOC_MODE=docker", (repo / ".env").read_text())
        repo = self.repo_with("TOC_MODE=docker\n")
        r = bash(repo, "toc_set_env TOC_STATE \"it's\"")
        self.assertNotEqual(r.returncode, 0, "a single quote cannot be written safely")
        self.assertNotIn("TOC_STATE", (repo / ".env").read_text())

    @unittest.skipIf(PWSH is None, "PowerShell (pwsh) is not installed")
    def test_powershell_reads_and_writes_the_same(self) -> None:
        repo = self.repo_with("TOC_STATE=\"./data\"\nTOC_IMAGE='img:1'\n")
        r = pwsh(". ./scripts/toc_common.ps1; Get-TocStateDir; "
                 "Get-TocEnvValue -Name TOC_IMAGE; "
                 "Set-TocEnvValue -Name TOC_BACKUP -Value '/srv/toc state'; "
                 "Get-TocEnvValue -Name TOC_BACKUP", repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], str(repo / "data"))
        self.assertEqual(lines[1], "img:1")
        self.assertEqual(lines[2], "/srv/toc state")
        self.assertIn("TOC_BACKUP='/srv/toc state'", (repo / ".env").read_text())
        r = bash(repo, "toc_env_get TOC_BACKUP")
        self.assertEqual(r.stdout.strip(), "/srv/toc state", "bash reads what PowerShell wrote")


# ---------------------------------------------------------------- 21

@unittest.skipUnless(NODE, "Node.js is required for the browser client tests")
class ClientDecodeTests(unittest.TestCase):
    def test_a_line_break_split_across_frames_is_one(self) -> None:
        result = subprocess.run([NODE, "--test", str(ROOT / "tests" / "test_client_decode.js")],
                                cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
