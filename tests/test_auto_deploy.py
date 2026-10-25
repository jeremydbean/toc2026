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
PROBE = ROOT / "deploy" / "windows-vm" / "toc-game-probe"

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
        # A fake GitHub API: the runs list is whatever the test sets, and
        # a run's jobs are FAKE_JOBS -- by default a deploy-gate that
        # passed. The URLs it was asked for are kept, to check which.
        self.urls = self.tmp / "curl-urls"
        (self.bin / "curl").write_text(
            "#!/bin/sh\nfor a; do url=$a; done\necho \"$url\" >> " + str(self.urls) + "\n"
            "case \"$url\" in\n"
            "  */jobs*) [ -n \"$FAKE_JOBS\" ] || exit 7; printf '%s' \"$FAKE_JOBS\" ;;\n"
            "  *) [ -n \"$FAKE_CI\" ] || exit 7; printf '%s' \"$FAKE_CI\" ;;\n"
            "esac\n")
        (self.bin / "logger").write_text("#!/bin/sh\nexit 0\n")
        # A fake player count: what the game would answer over MSSP.
        (self.bin / "players").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"${FAKE_PLAYERS-0}\"\n")
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

    @staticmethod
    def wf_run(sha: str, status: str, conclusion: str | None = None, *, run_id: int = 1,
            event: str = "push", branch: str = "main",
            created: str = "2026-10-05T00:00:00Z") -> dict:
        return {"id": run_id, "name": "Validate", "event": event, "head_branch": branch,
                "head_sha": sha, "status": status, "conclusion": conclusion,
                "created_at": created, "run_attempt": 1}

    def ci(self, sha: str, status: str, conclusion: str | None = None, **kw) -> str:
        return json.dumps({"workflow_runs": [self.wf_run(sha, status, conclusion, **kw)]})

    @staticmethod
    def jobs(gate: str | None = "success", gate_status: str = "completed",
             present: bool = True) -> str:
        jobs = [{"name": "build", "status": "completed", "conclusion": "success"},
                {"name": "tests (1)", "status": "completed", "conclusion": "success"}]
        if present:
            jobs.append({"name": "deploy-gate", "status": gate_status, "conclusion": gate})
        return json.dumps({"jobs": jobs})

    def run_script(self, fake_ci: str = "", deploy_fails: bool = False,
                   players: str = "0", fake_jobs: str | None = None) -> str:
        env = dict(os.environ,
                   PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                   BUILD=str(self.build), CURRENT=str(self.current),
                   STATE_DIR=str(self.state), TOC_DEPLOY_LOCK=str(self.tmp / "lock"),
                   TOC_DEPLOY_BIN=str(self.bin / "toc-deploy"),
                   FAKE_CI=fake_ci, FAKE_DEPLOY_FAILS="1" if deploy_fails else "",
                   FAKE_JOBS=self.jobs() if fake_jobs is None else fake_jobs,
                   TOC_PLAYERS_PROBE=str(self.bin / "players"), FAKE_PLAYERS=players,
                   TOC_PLAYERS_WARN_SECONDS="0")
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

    def test_players_online_hold_the_deploy_until_the_game_is_empty(self) -> None:
        """Owner, 2026-10-20: do not reboot while players are on. The
        held commit is not marked attempted, so the first empty tick
        ships it; a game that does not answer has nobody to protect."""
        code = self.commit("fix [deploy now]", {"src/game.c": "int h;\n"})
        status = self.run_script(players="3")
        self.assertIn("holding", status)
        self.assertIn("3 player(s) online", status)
        self.assertEqual([], self.deploys())
        self.assertFalse((self.state / "attempted").exists())
        self.run_script(players="1")
        self.assertEqual([], self.deploys())
        self.assertIn("deployed", self.run_script(players="0"))
        self.assertEqual([f"{code} 1"], self.deploys())
        newer = self.commit("again [deploy now]", {"src/game.c": "int i;\n"})
        self.assertIn("deployed", self.run_script(players="down"))
        self.assertEqual([f"{code} 1", f"{newer} 1"], self.deploys(),
                         "a game that is not running has nobody to protect")

    def test_an_unknown_player_count_is_not_zero(self) -> None:
        """A game that accepts a connection and does not say who is on --
        hung, half started -- may have players in it. It holds the deploy
        like a count above zero; only [deploy with players], with its
        warning, ships past it."""
        code = self.commit("fix [deploy now]", {"src/game.c": "int u;\n"})
        for answer in ("unknown", "", "garbage", "-1"):
            status = self.run_script(players=answer)
            self.assertIn("holding", status, answer)
            self.assertIn("did not say who is online", status, answer)
        self.assertEqual([], self.deploys())
        self.assertFalse((self.state / "attempted").exists())
        self.commit("ship it [deploy with players]", {"README.md": "go\n"})
        status = self.run_script(players="unknown")
        self.assertIn("[deploy with players], the game did not say who is online", status)
        self.assertEqual(1, len(self.deploys()))
        self.assertNotEqual(code, self.deploys()[0].split()[0], "the tip ships")

    def test_deploy_with_players_ships_past_them_with_a_warning(self) -> None:
        """Owner, 2026-10-24: "ship now, just send the announcement before
        reboot", from a session that can only push. The marker may ride
        any waiting commit, warns through the queue, and never skips CI."""
        (self.current / "area").mkdir(parents=True, exist_ok=True)
        queue = self.current / "area" / "webadmin.queue"
        queue.write_text("")
        code = self.commit("fix", {"src/game.c": "int p;\n"})
        green = self.ci(code, "completed", "success")
        self.assertIn("holding", self.run_script(green, players="2"))
        self.assertEqual([], self.deploys())
        self.assertEqual("", queue.read_text())

        # Docs-only, so the code commit is still the one shipped and the
        # one CI must cover.
        tip = self.commit("ship it [deploy with players]", {"README.md": "now\n"})
        status = self.run_script(green, players="2")
        self.assertIn("deployed", status)
        self.assertIn("[deploy with players], 2 player(s) online", status)
        self.assertEqual([f"{tip} 1"], self.deploys())
        self.assertIn("announce|The game restarts for an update in one minute",
                      queue.read_text())

    def test_deploy_with_players_does_not_skip_ci(self) -> None:
        self.commit("fix [deploy with players]", {"src/game.c": "int q;\n"})
        status = self.run_script(fake_ci="", players="1")
        self.assertIn("waiting for CI", status)
        self.assertEqual([], self.deploys())

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

    def test_state_syncs_do_not_retry_a_failed_payload(self) -> None:
        """Audit 2026-10-21: the failed-attempt record was the tip, so a
        state sync on top made the same failed code new again."""
        code = self.commit("fix", {"src/game.c": "int j;\n"})
        green = self.ci(code, "completed", "success")
        self.run_script(green, deploy_fails=True)
        for n in range(3):
            self.commit("State sync: %d files [skip ci]" % n, {"log/toc.log": "x%d\n" % n})
            self.run_script(green)
        self.assertEqual(1, len(self.deploys()), "one attempt for one payload")
        fixed = self.commit("fix the fix", {"src/game.c": "int k;\n"})
        self.run_script(self.ci(fixed, "completed", "success"))
        self.assertEqual(2, len(self.deploys()))

    def test_an_old_deploy_now_does_not_pass_newer_code(self) -> None:
        """Audit 2026-10-21: [deploy now] anywhere in live..target passed
        a later, unchecked commit too."""
        self.commit("hotfix [deploy now]", {"src/game.c": "int l;\n"})
        newer = self.commit("more code", {"src/game.c": "int m;\n"})
        status = self.run_script(self.ci(newer, "completed", "failure"))
        self.assertEqual([], self.deploys(), status)
        # A state sync on top of an override still ships under it.
        override = self.commit("hotfix again [deploy now]", {"src/game.c": "int n;\n"})
        sync = self.commit("State sync [skip ci]", {"player/Zed": "y\n"})
        self.assertIn("[deploy now] on", self.run_script(fake_ci=""))
        self.assertEqual([f"{sync} 1"], self.deploys())
        self.assertNotEqual(override, sync)

    def test_ci_on_an_older_commit_does_not_cover_skipped_code(self) -> None:
        """Audit 2026-10-21: green CI on C passed D, which changed code but
        carried [skip ci]."""
        good = self.commit("good", {"src/game.c": "int good;\n"})
        self.commit("sneak [skip ci]", {"src/game.c": "int unchecked;\n"})
        status = self.run_script(self.ci(good, "completed", "success"))
        self.assertIn("no CI run after it", status)
        self.assertEqual([], self.deploys())

    def test_a_green_run_without_a_passing_gate_job_ships_nothing(self) -> None:
        """deploy-gate is the verdict. A run whose gate failed, was
        skipped or is still going -- or a run with no gate job at all, as
        an older workflow or a renamed job would leave -- ships nothing,
        and is not marked attempted: it is not a failed deploy."""
        code = self.commit("fix", {"src/game.c": "int v;\n"})
        green = self.ci(code, "completed", "success")
        for jobs, word in ((self.jobs("failure"), "failure"), (self.jobs("skipped"), "skipped"),
                           (self.jobs("cancelled"), "cancelled"),
                           (self.jobs(None, "in_progress"), "in_progress"),
                           (self.jobs(present=False), "missing")):
            status = self.run_script(green, fake_jobs=jobs)
            self.assertIn(f"deploy-gate job is {word}", status)
        status = self.run_script(green, fake_jobs="not json")
        self.assertIn("cannot read CI's deploy-gate", status)
        status = self.run_script(green, fake_jobs="")
        self.assertIn("cannot read CI's deploy-gate", status)
        self.assertEqual([], self.deploys())
        self.assertFalse((self.state / "attempted").exists())
        self.assertIn("deployed", self.run_script(green))
        urls = self.urls.read_text()
        self.assertIn("/actions/runs/1/jobs", urls, "the gate is read from the run that decided")
        self.assertIn("workflows/validate.yml/runs?branch=main&event=push", urls)

    def test_only_a_push_to_main_for_this_code_counts(self) -> None:
        """A pull request's run, a run on another branch, and a run for an
        older commit are all green and none of them tested what main is
        about to ship."""
        old = self.live
        code = self.commit("fix", {"src/game.c": "int w;\n"})
        for run in (self.wf_run(code, "completed", "success", event="pull_request"),
                    self.wf_run(code, "completed", "success", branch="feature"),
                    self.wf_run(old, "completed", "success")):
            status = self.run_script(json.dumps({"workflow_runs": [run]}))
            self.assertIn("waiting for CI", status)
            self.assertIn("(none)", status)
        self.assertEqual([], self.deploys())

    def test_the_newest_run_on_or_above_the_code_decides(self) -> None:
        """Code and a test-only commit pushed together get one run, on the
        tip: that run tested the code and decides it. And when a later
        push supersedes an earlier run, the later verdict wins -- a stale
        green under it does not."""
        code = self.commit("fix", {"src/game.c": "int x;\n"})
        tests = self.commit("its test", {"tests/test_x.py": "pass\n"})
        runs = {"workflow_runs": [
            self.wf_run(code, "completed", "success", run_id=1, created="2026-10-05T00:00:00Z"),
            self.wf_run(tests, "completed", "failure", run_id=2, created="2026-10-05T00:01:00Z")]}
        self.assertIn("CI on", self.run_script(json.dumps(runs)))
        self.assertEqual([], self.deploys(), "the newer red run covers the code")
        runs["workflow_runs"][1]["conclusion"] = "cancelled"
        self.assertIn("was cancelled", self.run_script(json.dumps(runs)))
        self.assertEqual([], self.deploys(), "a cancelled run is never a pass")
        self.assertFalse((self.state / "attempted").exists())
        runs["workflow_runs"].append(
            self.wf_run(tests, "completed", "success", run_id=3, created="2026-10-05T00:02:00Z"))
        self.assertIn("deployed", self.run_script(json.dumps(runs)))
        self.assertEqual([f"{tests} 1"], self.deploys())
        self.assertIn("/actions/runs/3/jobs", self.urls.read_text())

    def test_a_run_under_a_newer_unrun_commit_still_counts(self) -> None:
        """A docs-only push starts no run (paths-ignore); the code under
        it keeps its own verdict."""
        code = self.commit("fix", {"src/game.c": "int y;\n"})
        tip = self.commit("note", {"README.md": "docs\n"})
        self.assertIn("deployed", self.run_script(self.ci(code, "completed", "success")))
        self.assertEqual([f"{tip} 1"], self.deploys())


try:
    from live_mud import LiveMud, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class PlayersProbeLiveTests(unittest.TestCase):
    def test_the_mssp_probe_counts_who_is_playing(self) -> None:
        """The probe both deploy scripts use, against a real server: one
        player in CON_PLAYING reads as 1, a port nobody listens on as
        down, and a listener that never answers MSSP as unknown."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                from live_mud import create_character
                create_character(client, "Zcounted", "Zcount1pass")
                client.drain(1.0)
                out = subprocess.run(["python3", str(PROBE), "127.0.0.1", str(mud.port)],
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual("1", out.stdout.strip(), out.stderr)
        out = subprocess.run(["python3", str(PROBE), "127.0.0.1", "1"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual("down", out.stdout.strip())


class GameProbeTests(unittest.TestCase):
    def test_the_auto_deployer_finds_the_probe_before_it_is_installed(self) -> None:
        """The deploy that brings toc-auto-deploy is made by the toc-deploy
        before it, which does not install the probe; a missing probe reads
        "unknown" and would hold every later deploy. The build tree's copy
        stands in."""
        script = SCRIPT.read_text()
        self.assertIn('elif [ -x /usr/local/sbin/toc-game-probe ]; then', script)
        self.assertIn('PLAYERS_PROBE="$BUILD/deploy/windows-vm/toc-game-probe"', script)
        self.assertLess(script.index('PLAYERS_PROBE="$BUILD/deploy'), script.index("players_online() {"))

    def test_a_silent_listener_is_unknown_not_zero(self) -> None:
        import socket
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            out = subprocess.run(["python3", str(PROBE), "127.0.0.1", str(port)],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual("unknown", out.stdout.strip())

    def test_both_deploy_scripts_use_it(self) -> None:
        self.assertIn("/usr/local/sbin/toc-game-probe", SCRIPT.read_text())
        deploy = DEPLOY.read_text()
        self.assertIn("toc-game-probe", deploy)
        self.assertIn("toc-game-probe", deploy.split("for s in toc-deploy", 1)[1].split("do", 1)[0],
                      "toc-deploy installs the probe with the scripts that use it")
        self.assertNotIn("<<'PY'", SCRIPT.read_text(), "one probe, not a copy")


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

    def test_git_is_told_the_build_tree_is_safe(self) -> None:
        # A systemd service has no HOME, so root's ~/.gitconfig, which is
        # what makes sudo toc-deploy work, is not read; the first timer
        # run on the host died on "dubious ownership" without this.
        script = SCRIPT.read_text()
        self.assertIn("GIT_CONFIG_KEY_0=safe.directory", script)
        self.assertIn('GIT_CONFIG_VALUE_0="$BUILD"', script)
        self.assertLess(script.index("GIT_CONFIG_VALUE_0"), script.index("git -C"))

    def test_the_script_is_lf(self) -> None:
        for path in (SCRIPT, DEPLOY, RESTORE, PROBE):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
