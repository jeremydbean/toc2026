"""Server maintenance from the admin website (owner, 2026-11-22: the state
sync failed for a day and fixing it needed SSH; "fixed actions" chosen over
a command box).

The dashboard (webadmin/host_actions.py) writes one request file naming an
action; the root helper deploy/windows-vm/toc-host-action, started by
toc-host-action.path, runs only the actions it names and writes a result
the dashboard reads. These tests run the real helper script against
stand-in systemctl, journalctl, logger and toc-deploy in a temporary
directory, and the real module against the same directories, end to end.
Nothing here touches a real host path.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "deploy" / "windows-vm" / "toc-host-action"

import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from webadmin import host_actions  # noqa: E402

STUB = """#!/bin/sh
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0") $*" in
    "systemctl show"*) echo success ;;
    "systemctl is-active"*) echo active ;;
    "journalctl"*) echo "Nov 22 sync: pushed" ;;
esac
exit "${STUB_EXIT:-0}"
"""
DEPLOY_STUB = """#!/bin/sh
echo "toc-deploy rollback=$TOC_DEPLOY_ROLLBACK" >> "$STUB_LOG"
echo "== healthy"
exit "${STUB_EXIT:-0}"
"""


def group_name() -> str:
    import grp
    return grp.getgrgid(os.getgid()).gr_name


class HostActionWorld:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.requests = tmp / "lib-toc" / "host-actions"
        self.results = tmp / "lib-toc-host-actions"
        self.results.mkdir(parents=True)
        self.stubs = tmp / "bin"
        self.stubs.mkdir()
        self.log = tmp / "stub.log"
        for name in ("systemctl", "journalctl", "logger"):
            (self.stubs / name).write_text(STUB)
            (self.stubs / name).chmod(0o755)
        self.deploy = tmp / "toc-deploy"
        self.deploy.write_text(DEPLOY_STUB)
        self.deploy.chmod(0o755)
        self.state_repo = tmp / "state-repo"
        self.current = tmp / "current"
        (self.current / "log").mkdir(parents=True)
        self.env = {
            "TOC_HOST_ACTION_REQUESTS": str(self.requests),
            "TOC_HOST_ACTION_RESULTS": str(self.results),
        }

    def run_helper(self, exit_code: int = 0) -> subprocess.CompletedProcess:
        env = dict(os.environ, **self.env)
        env.update({
            "TOC_HOST_ACTION_GROUP": group_name(),
            "TOC_HOST_ACTION_PATH": f"{self.stubs}:/usr/bin:/bin",
            "TOC_DEPLOY_BIN": str(self.deploy),
            "STATE_REPO": str(self.state_repo),
            "CURRENT": str(self.current),
            "STUB_LOG": str(self.log),
            "STUB_EXIT": str(exit_code),
        })
        return subprocess.run(["sh", str(HELPER)], env=env, capture_output=True,
                              text=True, timeout=60)

    def calls(self) -> str:
        return self.log.read_text() if self.log.exists() else ""

    def submit(self, action: str) -> dict:
        with patch.dict(os.environ, self.env):
            return host_actions.submit(action, action)

    def snapshot(self) -> dict:
        with patch.dict(os.environ, self.env):
            return host_actions.snapshot()


@unittest.skipIf(shutil.which("sh") is None, "no sh")
class HostActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.world = HostActionWorld(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_the_helper_and_the_dashboard_name_the_same_actions(self) -> None:
        helper = HELPER.read_text()
        case = re.search(r"\n    (state-sync\|[a-z|-]+)\) ;;", helper)
        self.assertIsNotNone(case)
        self.assertEqual(set(case.group(1).split("|")), set(host_actions.ACTIONS))
        run = helper[helper.index("run_action() {"):helper.index("prune() {")]
        named = set(re.findall(r"^\s+([a-z-]+)\)\s+act_", run, re.M))
        self.assertEqual(named, set(host_actions.ACTIONS))
        # The dashboard never runs a command itself.
        source = (ROOT / "webadmin" / "host_actions.py").read_text()
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)

    def test_a_request_runs_end_to_end(self) -> None:
        asked = self.world.submit("state-sync")
        request = self.world.requests / "request"
        self.assertEqual(request.read_text(), f"{asked['id']} state-sync\n")
        self.assertEqual(self.world.snapshot()["busy"], "waiting")
        with self.assertRaises(host_actions.HostActionError) as caught:
            self.world.submit("auto-deploy")
        self.assertEqual(caught.exception.status, 409)

        done = self.world.run_helper()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(request.exists())
        self.assertIn("systemctl start toc-state-sync.service", self.world.calls())
        snap = self.world.snapshot()
        self.assertIsNone(snap["busy"])
        result = snap["results"][0]
        self.assertEqual((result["id"], result["action"], result["state"], result["exit"]),
                         (asked["id"], "state-sync", "ok", 0))
        self.assertIn("Nov 22 sync: pushed", result["output"])
        self.assertGreaterEqual(result["finished"], result["started"])
        # Root's file, readable by the group, written whole.
        mode = (self.world.results / asked["id"]).stat().st_mode & 0o777
        self.assertEqual(mode, 0o640)
        self.assertEqual([p.name for p in self.world.results.iterdir()], [asked["id"]])

    def test_reclone_keeps_the_old_clone(self) -> None:
        self.world.state_repo.mkdir()
        (self.world.state_repo / "marker").write_text("old")
        self.world.submit("state-sync-reclone")
        self.world.run_helper()
        self.assertFalse(self.world.state_repo.exists())
        aside = [p for p in self.world.tmp.iterdir() if p.name.startswith("state-repo.broken-")]
        self.assertEqual(len(aside), 1)
        self.assertEqual((aside[0] / "marker").read_text(), "old")
        calls = self.world.calls()
        self.assertLess(calls.index("systemctl stop toc-state-sync.service"),
                        calls.index("systemctl start toc-state-sync.service"))
        output = self.world.snapshot()["results"][0]["output"]
        self.assertIn("kept; remove it once the sync works", output)

    def test_deploy_rolls_back_by_itself_and_failure_is_reported(self) -> None:
        self.world.submit("deploy")
        self.world.run_helper(exit_code=12)
        self.assertIn("toc-deploy rollback=1", self.world.calls())
        result = self.world.snapshot()["results"][0]
        self.assertEqual((result["state"], result["exit"]), ("failed", 12))

    def test_auto_deploy_and_restart_web(self) -> None:
        (self.world.current / "log" / "auto-deploy.status").write_text("holding abc: 1 player(s) online\n")
        self.world.submit("auto-deploy")
        self.world.run_helper()
        self.assertIn("holding abc", self.world.snapshot()["results"][0]["output"])
        self.world.submit("restart-web")
        self.world.run_helper()
        self.assertIn("systemctl restart toc-web.service", self.world.calls())

    def test_the_helper_refuses_what_is_not_an_action(self) -> None:
        self.world.requests.mkdir(parents=True)
        request = self.world.requests / "request"
        bad_id = "0123456789abcdef0123456789abcdef"
        request.write_text(f"{bad_id} rm -rf /\n")
        self.world.run_helper()
        self.assertFalse(request.exists())
        self.assertNotIn("systemctl", self.world.calls())
        result = host_actions.parse_result((self.world.results / bad_id).read_text())
        self.assertEqual((result["action"], result["state"]), ("unknown", "refused"))
        self.assertNotIn("rm -rf", (self.world.results / bad_id).read_text())

        request.write_text("not-an-id state-sync\n")
        self.world.run_helper()
        self.assertFalse(request.exists())
        self.assertNotIn("systemctl", self.world.calls())

        secret = self.world.tmp / "secret"
        secret.write_text(f"{bad_id} state-sync\n")
        request.symlink_to(secret)
        self.world.run_helper()
        self.assertFalse(request.is_symlink())
        self.assertTrue(secret.exists())
        self.assertNotIn("systemctl", self.world.calls())

    def test_the_dashboard_refuses_before_writing(self) -> None:
        for action, confirm, status in (("rm -rf /", "rm -rf /", 400),
                                        ("deploy", "", 400),
                                        ("deploy", "state-sync", 400)):
            with patch.dict(os.environ, self.world.env):
                with self.assertRaises(host_actions.HostActionError) as caught:
                    host_actions.submit(action, confirm)
            self.assertEqual(caught.exception.status, status)
        self.assertFalse(self.world.requests.exists())
        shutil.rmtree(self.world.results)
        with patch.dict(os.environ, self.world.env):
            with self.assertRaises(host_actions.HostActionError) as caught:
                host_actions.submit("state-sync", "state-sync")
            self.assertEqual(caught.exception.status, 503)
            self.assertFalse(host_actions.snapshot()["available"])

    def test_a_running_action_blocks_until_it_is_stale(self) -> None:
        now = time.time()
        rid = "a" * 32
        (self.world.results / rid).write_text(
            f"id {rid}\naction deploy\nstate running\nstarted {int(now) - 60}\nfinished 0\nexit 0\n\n")
        self.assertEqual(self.world.snapshot()["busy"], "running")
        with self.assertRaises(host_actions.HostActionError):
            self.world.submit("state-sync")
        (self.world.results / rid).write_text(
            f"id {rid}\naction deploy\nstate running\nstarted {int(now) - 3 * 3600}\nfinished 0\nexit 0\n\n")
        self.assertIsNone(self.world.snapshot()["busy"])
        self.world.submit("state-sync")

    def test_old_results_are_pruned(self) -> None:
        for n in range(45):
            rid = f"{n:032x}"
            path = self.world.results / rid
            path.write_text(f"id {rid}\naction state-sync\nstate ok\nstarted {n}\nfinished {n}\nexit 0\n\n")
            os.utime(path, (1_700_000_000 + n, 1_700_000_000 + n))
        self.world.submit("state-sync")
        self.world.run_helper()
        self.assertEqual(len(list(self.world.results.iterdir())), 40)

    def test_deploys_install_the_helper(self) -> None:
        deploy = (ROOT / "deploy" / "windows-vm" / "toc-deploy").read_text()
        self.assertIn("toc-auto-deploy toc-game-probe toc-host-action", deploy)
        self.assertIn("toc-host-action.service toc-host-action.path", deploy)
        self.assertIn("install -d -m 0750 -o root -g toc /var/lib/toc-host-actions", deploy)
        self.assertIn("systemctl enable --now toc-host-action.path", deploy)
        restore = (ROOT / "deploy" / "toc-restore").read_text()
        self.assertIn("toc-host-action.service toc-host-action.path", restore)
        self.assertIn("toc-game-probe toc-host-action", restore)
        # The first deploy to bring the helper runs the toc-deploy before it,
        # which does not name it: the auto-deployer installs it once while it
        # is missing, as root, from the live commit's build tree.
        auto = (ROOT / "deploy" / "windows-vm" / "toc-auto-deploy").read_text()
        boot = auto[auto.index('HOST_ACTION_SBIN='):auto.index("players_online() {")]
        self.assertIn('[ "$(id -u)" = 0 ]', boot)
        self.assertIn('[ ! -f "$HOST_ACTION_UNITS/toc-host-action.path" ]', boot)
        self.assertIn("systemctl enable --now toc-host-action.path", boot)
        # The path unit goes in last, so it is never there without the rest.
        self.assertLess(boot.index("toc-host-action.service"), boot.index('toc-host-action.path" "$HOST_ACTION_UNITS/"'))
        path_unit = (ROOT / "deploy" / "windows-vm" / "toc-host-action.path").read_text()
        self.assertIn("PathExists=/var/lib/toc/host-actions/request", path_unit)
        web_unit = (ROOT / "deploy" / "windows-vm" / "toc-web.service").read_text()
        self.assertIn("StateDirectory=toc", web_unit)
        self.assertIn("NoNewPrivileges=true", web_unit)



AUTO_DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-auto-deploy"
STATE_SYNC = ROOT / "deploy" / "windows-vm" / "toc-state-sync"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


@unittest.skipIf(shutil.which("git") is None, "needs git")
class GitRequestTests(unittest.TestCase):
    """ops/host-requests.txt: what a session that can only push may ask for.
    Runs toc-auto-deploy's own hand-over function against a build tree whose
    origin/main carries the file."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.build = self.tmp / "build"
        self.build.mkdir()
        git("init", "-q", "-b", "main", cwd=self.build)
        self.requests = self.tmp / "host-actions"
        self.results = self.tmp / "results"
        self.results.mkdir()
        self.state = self.tmp / "auto-state"
        self.state.mkdir()
        self.now = int(time.time())
        source = AUTO_DEPLOY.read_text()
        block = source[source.index('HOST_REQUESTS_PATH="${TOC_HOST_REQUESTS_PATH'):
                       source.index("# How many descriptors the game has")]
        self.probe = self.tmp / "probe.sh"
        self.probe.write_text("set -eu\nlogger() { :; }\n" + block + "hand_over_git_requests\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def publish(self, *lines: str) -> None:
        ops = self.build / "ops"
        ops.mkdir(exist_ok=True)
        (ops / "host-requests.txt").write_text("# header\n" + "".join(f"{l}\n" for l in lines))
        git("add", "ops", cwd=self.build)
        git("commit", "-qm", "ask", cwd=self.build)
        git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.build)

    def hand_over(self) -> None:
        env = dict(os.environ, BUILD=str(self.build), STATE_DIR=str(self.state),
                   TOC_HOST_ACTION_REQUESTS=str(self.requests),
                   TOC_HOST_ACTION_RESULTS=str(self.results),
                   TOC_HOST_ACTION_OWNER=f"{os.getuid()}:{os.getgid()}")
        done = subprocess.run(["sh", str(self.probe)], env=env, capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)

    def request(self) -> str:
        path = self.requests / "request"
        return path.read_text() if path.exists() else ""

    def test_the_lists_agree_and_never_deploy(self) -> None:
        source = AUTO_DEPLOY.read_text()
        listed = re.search(r'^GIT_HOST_ACTIONS="([^"]+)"', source, re.M).group(1).split()
        self.assertEqual(set(listed), set(host_actions.GIT_ACTIONS))
        self.assertTrue(set(listed) <= set(host_actions.ACTIONS))
        self.assertNotIn("deploy", listed)
        self.assertNotIn("auto-deploy", listed)
        # Handed over on the way out, after the deploy lock is let go: the
        # sync the helper starts skips a run made while a deploy holds it.
        trap = source.index("trap 'rc=$?; exec 9>&-; hand_over_git_requests")
        self.assertGreater(trap, source.index('if ! flock -n 9; then'))
        self.assertLess(trap, source.index('git -C "$BUILD" fetch --quiet origin main'))
        self.assertTrue((ROOT / "ops" / "host-requests.txt").exists())

    def test_a_new_request_is_handed_over_once(self) -> None:
        rid = "a" * 32
        self.publish(f"{rid} status {self.now}")
        self.hand_over()
        self.assertEqual(self.request(), f"{rid} status\n")
        (self.requests / "request").unlink()
        self.hand_over()
        self.assertEqual(self.request(), "", "an id runs once")
        self.assertEqual(list(self.requests.glob(".request.*")), [])

    def test_one_at_a_time_and_never_over_the_websites(self) -> None:
        first, second = "b" * 32, "c" * 32
        self.publish(f"{first} state-sync {self.now}", f"{second} restart-web {self.now}")
        self.requests.mkdir()
        (self.requests / "request").write_text(f"{'d' * 32} status\n")
        self.hand_over()
        self.assertEqual(self.request(), f"{'d' * 32} status\n", "the website's request stands")
        (self.requests / "request").unlink()
        self.hand_over()
        self.assertEqual(self.request(), f"{first} state-sync\n")
        (self.requests / "request").unlink()
        self.hand_over()
        self.assertEqual(self.request(), f"{second} restart-web\n")

    def test_refusals_leave_a_result_and_run_nothing(self) -> None:
        old, deploy, future, bare, extra = ("1" * 32, "2" * 32, "3" * 32, "4" * 32, "5" * 32)
        self.publish(f"{old} status {self.now - 7 * 3600}",
                     f"{deploy} deploy {self.now}",
                     f"{future} status {self.now + 3600}",
                     f"{bare} status",
                     f"{extra} status {self.now} rm",
                     "not-an-id status 1",
                     f"{'6' * 32} status {self.now}")
        for _ in range(6):
            self.hand_over()
            if self.request():
                break
        self.assertEqual(self.request(), f"{'6' * 32} status\n")
        for rid in (old, deploy, future, bare, extra):
            parsed = host_actions.parse_result((self.results / rid).read_text())
            self.assertEqual(parsed["state"], "refused", rid)
        self.assertIn("cannot be asked for through GitHub",
                      (self.results / deploy).read_text())

    def test_nothing_without_the_helper_installed(self) -> None:
        self.results.rmdir()
        self.publish(f"{'7' * 32} status {self.now}")
        self.hand_over()
        self.assertEqual(self.request(), "")


@unittest.skipIf(any(shutil.which(t) is None for t in ("git", "flock", "rsync")),
                 "needs git, flock and rsync")
class StateSyncHealingTests(unittest.TestCase):
    """toc-state-sync repairs what used to need a person: a lock or rebase
    a killed run left, and a broken clone. And it carries the helper's
    results back to git. Runs the real script against a local bare repo."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self._tmp.name)
        self.bare, seed = root / "remote.git", root / "seed"
        git("init", "-q", "--bare", "-b", "main", str(self.bare))
        git("clone", "-q", str(self.bare), str(seed))
        (seed / "README").write_text("seed\n")
        git("add", "README", cwd=seed)
        git("commit", "-qm", "seed", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)
        self.live = root / "live"
        (self.live / "player").mkdir(parents=True)
        (self.live / "log").mkdir()
        self.results = root / "results"
        self.results.mkdir()
        self.repo = root / "state"
        key = root / "key"
        key.write_text("not a key\n")
        # A file:// remote, so the clone copies objects rather than
        # hard-linking the remote's, which breaking the clone would break too.
        self.env = dict(os.environ, TOC_ROOT=str(self.live), STATE_REPO=str(self.repo),
                        REMOTE=f"file://{self.bare}", BRANCH="main", GIT_SSH_KEY=str(key),
                        LOCK_FILE=str(root / "sync.lock"), TOC_DEPLOY_LOCK=str(root / "d.lock"),
                        TOC_HOST_ACTION_RESULTS=str(self.results))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def sync(self, player: str) -> subprocess.CompletedProcess:
        # A different length each time: rsync's quick check skips a file of
        # the same size changed within the same second.
        self.writes = getattr(self, "writes", 0) + 1
        (self.live / "player" / "Zsync").write_text(
            f"#PLAYER\nName {player}~\n{'#' * self.writes}\nEnd\n")
        return subprocess.run(["sh", str(STATE_SYNC)], env=self.env, capture_output=True,
                              text=True, timeout=120)

    def pushed(self) -> int:
        log = git("--git-dir", str(self.bare), "log", "--format=%s", "main")
        return log.count("State sync:")

    def test_results_come_back_to_git_with_addresses_masked(self) -> None:
        rid = "e" * 32
        (self.results / rid).write_text(f"id {rid}\naction status\nstate ok\n\npeer 203.0.113.9 ok\n")
        (self.results / ".x.tmp").write_text("partial\n")
        done = self.sync("Zone")
        self.assertEqual(done.returncode, 0, done.stderr)
        shown = git("--git-dir", str(self.bare), "show", f"main:log/host-actions/{rid}")
        self.assertIn("peer <address> ok", shown)
        self.assertNotIn("203.0.113.9", shown)
        names = git("--git-dir", str(self.bare), "ls-tree", "--name-only", "main", "log/host-actions/")
        self.assertEqual(names.split(), [f"log/host-actions/{rid}"])

    def test_a_lock_and_a_rebase_a_killed_run_left_are_cleared(self) -> None:
        self.assertEqual(self.sync("Zone").returncode, 0)
        (self.repo / ".git" / "index.lock").write_text("")
        (self.repo / ".git" / "rebase-merge").mkdir()
        done = self.sync("Ztwo")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("index.lock", done.stderr)
        self.assertEqual(self.pushed(), 2, done.stdout + done.stderr)

    def break_clone(self) -> None:
        for obj in (self.repo / ".git" / "objects").rglob("*"):
            if obj.is_file() and obj.parent.name not in ("pack", "info"):
                obj.chmod(0o644)
                obj.write_bytes(b"")

    def test_a_broken_clone_is_moved_aside_and_made_again(self) -> None:
        self.assertEqual(self.sync("Zone").returncode, 0)
        self.break_clone()
        done = self.sync("Ztwo")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("moved it to", done.stderr)
        aside = list(self.root.glob("state.broken-auto-*"))
        self.assertEqual(len(aside), 1, "the broken clone is kept")
        self.assertEqual(self.pushed(), 2, done.stdout + done.stderr)
        # Broken again at once: left for a person, never a clone loop.
        self.break_clone()
        again = self.sync("Zthree")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("leaving it for a person", again.stderr)
        self.assertEqual(len(list(self.root.glob("state.broken-auto-*"))), 1)

    def test_the_clone_is_shallow_and_kept_packed(self) -> None:
        """2026-11-22: the clone grew to 24 GB of loose objects and filled
        the disk. It is cloned shallow now, and packed once its loose
        objects pass TOC_GIT_COMPACT_KB."""
        self.assertEqual(self.sync("Zone").returncode, 0)
        self.assertTrue((self.repo / ".git" / "shallow").exists(), "a shallow clone")
        self.env["TOC_GIT_COMPACT_KB"] = "0"
        done = self.sync("Ztwo")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("packing the clone", done.stderr)
        # Packed, then the run's own commit adds its few new objects.
        counts = dict(line.split(": ") for line in
                      git("count-objects", "-v", cwd=self.repo).splitlines())
        self.assertGreaterEqual(int(counts["packs"]), 1)
        self.assertLessEqual(int(counts["count"]), 10)
        self.assertEqual(self.pushed(), 2)

    def test_no_reclone_onto_a_full_disk(self) -> None:
        self.assertEqual(self.sync("Zone").returncode, 0)
        self.break_clone()
        self.env["TOC_STATE_RECLONE_MIN_FREE_MB"] = str(10 ** 9)
        done = self.sync("Ztwo")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("not cloning afresh", done.stderr)
        self.assertEqual(list(self.root.glob("state.broken-auto-*")), [], "nothing set aside")
        self.assertTrue((self.repo / ".git").is_dir())
        source = STATE_SYNC.read_text()
        self.assertIn("grep -qi 'no space left'", source,
                      "a disk-full error is never read as a broken clone")

    def test_a_remote_that_cannot_be_reached_is_not_a_broken_clone(self) -> None:
        self.assertEqual(self.sync("Zone").returncode, 0)
        self.env["REMOTE"] = str(self.root / "nowhere.git")
        git("remote", "set-url", "origin", str(self.root / "nowhere.git"), cwd=self.repo)
        done = self.sync("Ztwo")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("not a broken clone", done.stderr)
        self.assertEqual(list(self.root.glob("state.broken-auto-*")), [])



@unittest.skipIf(shutil.which("sh") is None, "no sh")
class DiskWarningTests(unittest.TestCase):
    """toc-state-sync-check tells staff when the disk is nearly full, on
    its own line, whatever the sync's state (2026-11-22)."""

    def test_a_nearly_full_disk_is_a_wizinfo(self) -> None:
        check = ROOT / "deploy" / "windows-vm" / "toc-state-sync-check"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "bin"
            stubs.mkdir()
            (stubs / "systemctl").write_text(
                "#!/bin/sh\ncase \"$*\" in\n"
                "  *ActiveState*) echo inactive ;;\n"
                "  *Result*) echo success ;;\n"
                "  *Monotonic*) awk '{printf \"%d\", $1 * 1000000}' /proc/uptime ;;\n"
                "esac\n")
            (stubs / "logger").write_text("#!/bin/sh\nexit 0\n")
            for stub in stubs.iterdir():
                stub.chmod(0o755)
            queue = root / "webadmin.queue"
            queue.write_text("")
            env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", QUEUE=str(queue),
                       MARKER=str(root / "status"), STATE_REPO=str(root / "none"),
                       DISK_PATH=str(root))
            healthy = subprocess.run(["sh", str(check)], env=dict(env, DISK_MIN_FREE_MB="1"),
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(healthy.returncode, 0, healthy.stderr)
            self.assertEqual(queue.read_text(), "")
            low = subprocess.run(["sh", str(check)], env=dict(env, DISK_MIN_FREE_MB=str(10 ** 9)),
                                 capture_output=True, text=True, timeout=60)
            self.assertIn("DISK NEARLY FULL", low.stderr)
            self.assertRegex(queue.read_text(),
                             r"^wizinfo\|60\|The server's disk is nearly full: \d+ MB free\.")


class MemoryAndBigFileWarningTests(unittest.TestCase):
    """toc-state-sync-check tells staff when memory runs low and when a file
    the sync commits nears GitHub's 100 MB limit (review, 2026-11-22)."""

    def run_check(self, root: Path, **extra) -> tuple[subprocess.CompletedProcess, str]:
        check = ROOT / "deploy" / "windows-vm" / "toc-state-sync-check"
        stubs = root / "bin"
        stubs.mkdir(exist_ok=True)
        (stubs / "systemctl").write_text(
            "#!/bin/sh\ncase \"$*\" in\n"
            "  *ActiveState*) echo inactive ;;\n"
            "  *Result*) echo success ;;\n"
            "  *Monotonic*) awk '{printf \"%d\", $1 * 1000000}' /proc/uptime ;;\n"
            "esac\n")
        (stubs / "logger").write_text("#!/bin/sh\nexit 0\n")
        for stub in stubs.iterdir():
            stub.chmod(0o755)
        queue = root / "webadmin.queue"
        queue.write_text("")
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", QUEUE=str(queue),
                   MARKER=str(root / "status"), STATE_REPO=str(root / "none"),
                   DISK_PATH=str(root), DISK_MIN_FREE_MB="1")
        env.update(extra)
        done = subprocess.run(["sh", str(check)], env=env, capture_output=True,
                              text=True, timeout=60)
        return done, queue.read_text()

    def test_low_memory_is_a_wizinfo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meminfo = root / "meminfo"
            meminfo.write_text("MemTotal:       8000000 kB\nMemAvailable:   6000000 kB\n")
            done, said = self.run_check(root, MEMINFO=str(meminfo))
            self.assertNotIn("MEMORY LOW", done.stderr)
            self.assertNotIn("low on memory", said)
            meminfo.write_text("MemTotal:       8000000 kB\nMemAvailable:    200000 kB\n")
            done, said = self.run_check(root, MEMINFO=str(meminfo))
            self.assertIn("MEMORY LOW: 195 of 7812 MB available", done.stderr)
            self.assertRegex(said, r"wizinfo\|60\|The server is low on memory: 195 of 7812 MB")

    def test_a_file_near_githubs_limit_is_a_wizinfo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            (repo / "log").mkdir(parents=True)
            (repo / ".git").mkdir()
            (repo / ".git" / "huge.pack").write_bytes(b"x" * (3 * 1024 * 1024))
            (repo / "log" / "small.log").write_bytes(b"x" * 1024)
            done, said = self.run_check(root, STATE_REPO=str(repo), BIG_FILE_MB="2")
            self.assertNotIn("GITHUB'S LIMIT", done.stderr, "git's own packs are not committed files")
            (repo / "log" / "toc.log").write_bytes(b"x" * (3 * 1024 * 1024))
            done, said = self.run_check(root, STATE_REPO=str(repo), BIG_FILE_MB="2")
            self.assertIn("FILES NEAR GITHUB'S LIMIT: log/toc.log", done.stderr)
            self.assertIn("A file the backup commits is over 2 MB (log/toc.log)", said)


if __name__ == "__main__":
    unittest.main()
