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


if __name__ == "__main__":
    unittest.main()
