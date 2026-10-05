"""toc-auto-deploy: a push to main ships itself, but only code, only green (2026-10-05).

A cloud session can push to GitHub and do nothing else -- HTTPS only, no
SSH, no key -- so the host polls main and runs toc-deploy when code lands
and CI has passed. This plays the real script against a throwaway
repository, with a fake GitHub API (a curl on PATH that prints what the
test says the run is) and a fake toc-deploy that records how it was
called, and checks each decision the script makes.

The source checks hold the pieces that live elsewhere: toc-deploy writing
the live marker, pinning the commit, rolling back unattended and
installing the timer; toc-restore installing it; and the script ignoring
every path the state sync commits, so a sync never restarts the game.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "windows-vm" / "toc-auto-deploy"
DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-deploy"
RESTORE = ROOT / "deploy" / "toc-restore"

NEEDS = ("sh", "git", "flock", "python3")
MISSING = [tool for tool in NEEDS if shutil.which(tool) is None]
SKIP = f"needs {', '.join(MISSING)}" if MISSING else None


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


@unittest.skipIf(SKIP is not None, SKIP or "")
class AutoDeployDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="toc-auto-deploy-"))
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.build = self.tmp / "build"
        self.current = self.tmp / "current"
        self.state = self.tmp / "state"
        self.bin = self.tmp / "bin"
        for d in (self.current / "log", self.state, self.bin):
            d.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True,
                       capture_output=True)
        git(self.work, "config", "user.email", "t@example.com")
        git(self.work, "config", "user.name", "t")
        git(self.work, "checkout", "-q", "-b", "main")
        self.live = self.commit("first", {"src/game.c": "int a;\n", "README.md": "hi\n"})
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.build)], check=True,
                       capture_output=True)
        # A fake GitHub API: prints whatever CI verdict the test sets.
        (self.bin / "curl").write_text(
            "#!/bin/sh\n[ -n \"$FAKE_CI\" ] || exit 7\nprintf '%s' \"$FAKE_CI\"\n")
        (self.bin / "logger").write_text("#!/bin/sh\nexit 0\n")
        # A fake toc-deploy: records the commit it was pinned to.
        self.calls = self.tmp / "deploy-calls"
        (self.bin / "toc-deploy").write_text(
            "#!/bin/sh\necho \"$TOC_DEPLOY_REF $TOC_DEPLOY_ROLLBACK\" >> " + str(self.calls) +
            "\n[ -z \"$FAKE_DEPLOY_FAILS\" ]\n")
        for f in self.bin.iterdir():
            f.chmod(0o755)
        self.mark_live(self.live)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, message: str, files: dict) -> str:
        for name, text in files.items():
            path = self.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            git(self.work, "add", name)
        git(self.work, "commit", "-q", "-m", message)
        git(self.work, "push", "-q", "origin", "main")
        return git(self.work, "rev-parse", "HEAD")

    def mark_live(self, sha: str) -> None:
        (self.current / "log" / "deployed-commit").write_text(f"{sha} 2026-10-05T00:00:00Z\n")

    def ci(self, sha: str, status: str, conclusion: str | None = None) -> str:
        return json.dumps({"workflow_runs": [{
            "name": "Validate", "event": "push", "head_sha": sha,
            "status": status, "conclusion": conclusion,
            "created_at": "2026-10-05T00:00:00Z"}]})

    def run_script(self, fake_ci: str = "", deploy_fails: bool = False) -> str:
        env = dict(os.environ,
                   PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                   BUILD=str(self.build), CURRENT=str(self.current),
                   STATE_DIR=str(self.state), TOC_DEPLOY_LOCK=str(self.tmp / "lock"),
                   TOC_DEPLOY_BIN=str(self.bin / "toc-deploy"),
                   FAKE_CI=fake_ci, FAKE_DEPLOY_FAILS="1" if deploy_fails else "")
        subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
        return (self.current / "log" / "auto-deploy.status").read_text() \
            if (self.current / "log" / "auto-deploy.status").exists() else ""

    def deploys(self) -> list:
        return self.calls.read_text().split("\n")[:-1] if self.calls.exists() else []

    def test_nothing_new_does_nothing(self) -> None:
        self.run_script()
        self.assertEqual([], self.deploys())

    def test_no_live_record_waits_for_a_deploy_by_hand(self) -> None:
        (self.current / "log" / "deployed-commit").unlink()
        self.commit("code", {"src/game.c": "int b;\n"})
        self.assertIn("no record of what is live", self.run_script())
        self.assertEqual([], self.deploys())

    def test_docs_tests_and_state_never_deploy(self) -> None:
        self.commit("docs", {"README.md": "more\n", "wiki/page.md": "x\n",
                             "tests/test_x.py": "pass\n"})
        self.commit("State sync [skip ci]", {"player/Zed": "Name Zed~\n",
                                             "log/toc.log": "line\n",
                                             "area/bugs.txt": "[1] Zed: bug\n"})
        self.assertIn("differs only in docs, tests or state", self.run_script())
        self.assertEqual([], self.deploys())

    def test_code_waits_for_ci_then_ships_that_commit(self) -> None:
        code = self.commit("fix the game", {"src/game.c": "int b;\n"})
        self.assertIn("waiting for CI", self.run_script(self.ci(code, "in_progress")))
        self.assertEqual([], self.deploys())
        status = self.run_script(self.ci(code, "completed", "success"))
        self.assertIn("deployed", status)
        self.assertEqual([f"{code} 1"], self.deploys(), "pinned to the commit, rollback on")

    def test_a_state_sync_on_top_does_not_hide_the_code_commits_ci(self) -> None:
        code = self.commit("fix", {"src/game.c": "int c;\n"})
        sync = self.commit("State sync: 1 files [skip ci]", {"player/Zed": "x\n"})
        # CI ran for the code commit; the sync commit has no run at all.
        self.run_script(self.ci(code, "completed", "success"))
        self.assertEqual([f"{sync} 1"], self.deploys(),
                         "the tip is deployed once the code under it is green")

    def test_red_ci_does_not_deploy(self) -> None:
        code = self.commit("broken", {"src/game.c": "int ;\n"})
        self.assertIn("CI on", self.run_script(self.ci(code, "completed", "failure")))
        self.assertEqual([], self.deploys())

    def test_an_unreachable_api_waits_rather_than_deploys(self) -> None:
        self.commit("fix", {"src/game.c": "int d;\n"})
        self.assertIn("unreachable", self.run_script(fake_ci=""))
        self.assertEqual([], self.deploys())

    def test_deploy_now_skips_the_ci_wait(self) -> None:
        code = self.commit("hotfix [deploy now]", {"src/game.c": "int e;\n"})
        self.assertIn("[deploy now]", self.run_script(fake_ci=""))
        self.assertEqual([f"{code} 1"], self.deploys())

    def test_a_failed_deploy_is_not_retried_every_tick(self) -> None:
        code = self.commit("fix", {"src/game.c": "int f;\n"})
        green = self.ci(code, "completed", "success")
        self.assertIn("FAILED", self.run_script(green, deploy_fails=True))
        self.run_script(green, deploy_fails=True)
        self.run_script(green)
        self.assertEqual(1, len(self.deploys()), "one attempt per commit")
        newer = self.commit("fix the fix", {"src/game.c": "int g;\n"})
        self.run_script(self.ci(newer, "completed", "success"))
        self.assertEqual(2, len(self.deploys()), "a new commit is tried")


class AutoDeploySourceTests(unittest.TestCase):
    def test_every_state_sync_path_is_ignored(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
        block = workflow[workflow.index("paths-ignore:"):workflow.index("pull_request:")]
        ignored = re.findall(r"- '([^']+)'", block)
        script = SCRIPT.read_text()
        excludes = re.findall(r":\(exclude(?:,glob)?\)([^']+)'", script)
        for path in ignored:
            covered = any(path == e or path.rstrip("*").rstrip("/") == e.rstrip("*").rstrip("/")
                          or (e.endswith("*") and path.startswith(e.rstrip("*")))
                          or path.startswith(e.rstrip("*") + "/") or path.split("/")[0] == e
                          for e in excludes)
            self.assertTrue(covered, f"{path} is synced by toc-state-sync but would trigger a deploy")

    def test_toc_deploy_records_pins_rolls_back_and_installs_the_timer(self) -> None:
        deploy = DEPLOY.read_text()
        self.assertIn('REF="${TOC_DEPLOY_REF:-origin/$BRANCH}"', deploy)
        self.assertIn('reset --quiet --hard "$REF"', deploy)
        self.assertIn('"$CURRENT/log/deployed-commit"', deploy)
        self.assertIn("--exclude 'log/'", deploy, "the marker must survive the rsync")
        self.assertIn('TOC_DEPLOY_ROLLBACK:-0}" = 1', deploy)
        self.assertIn("toc-auto-deploy.timer", deploy)
        self.assertIn("toc-auto-deploy", deploy.split("for s in toc-deploy", 1)[1].split("do", 1)[0])
        # The timer's own deploy must not restart the service it runs in.
        self.assertNotIn("restart toc-auto-deploy", deploy)

    def test_toc_restore_installs_and_starts_it(self) -> None:
        restore = RESTORE.read_text()
        self.assertIn("toc-auto-deploy.service toc-auto-deploy.timer", restore)
        self.assertIn("enable --now toc-auto-deploy.timer", restore)
        self.assertIn("log/deployed-commit", restore)

    def test_the_script_is_lf(self) -> None:
        for path in (SCRIPT, DEPLOY, RESTORE):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
