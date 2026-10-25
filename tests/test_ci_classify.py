"""Which tests a change needs (scripts/ci/classify.py), and the gate that
holds a run to it (scripts/ci/gate.py), 2026-10-25.

The policy is small on purpose: documentation, the browser client, the
dashboard and test modules each select what they name; everything else,
and anything ambiguous, is the full suite. These play it against throwaway
git repositories and the real tests/ inventory, never the live one:

* each class, a mixed change, a rename and a deletion, a new module, a
  changed harness, a state-sync commit, an unknown path;
* no base, an unreadable diff, a forced full run;
* a docs commit above failing code: classified from the trusted base, it
  carries the failing code's full suite with it;
* the deployable-tree fingerprint promotes a "no runtime change" class that
  moved the deployable tree, and its exclusions match toc-auto-deploy's.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSIFY = ROOT / "scripts" / "ci" / "classify.py"
GATE = ROOT / "scripts" / "ci" / "gate.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load(CLASSIFY, "toc_classify_test")
SERIAL = ["test_login_throttle"]
SANITIZE = ["test_stash", "test_training_dummy"]


def plan(paths, base="b" * 40, head="h" * 40, **kw):
    kw.setdefault("base_fingerprint", "same")
    kw.setdefault("head_fingerprint", "same")
    return C.plan_for(paths, head=head, base=base, serial=SERIAL, sanitize=SANITIZE, **kw)


class PathClassTests(unittest.TestCase):
    def test_each_class(self) -> None:
        cases = {
            "player/Alaric": "state", "log/toc.log": "state", "area/maxload.txt": "state",
            "area/built/x.are": "state",
            "wiki/building-guide.md": "docs", "notes/memory_leak_audit.md": "docs",
            "CHANGELOG.md": "docs",
            "webadmin/static/client.js": "web-ui",
            "webadmin/server.py": "web-backend",
            "tests/test_stash.py": "tests",
            "src/fight.c": "full", "src/merc.h": "full", "area/hyrule.are": "full",
            "data/hyrule_first_quest.json": "full", "scripts/build_hyrule_area.py": "full",
            "tests/live_mud.py": "full", "tests/fixtures/area/ztestfix.are": "full",
            "tests/ci_durations.json": "full", "scripts/ci/gate.py": "full",
            ".github/workflows/validate.yml": "full", "deploy/windows-vm/toc-deploy": "full",
            "webadmin/requirements.txt": "full", "Makefile": "full",
            "mudlet/package/script.lua": "full", "some/new/thing.xyz": "full",
            # Shipped content, not state, whatever its extension says.
            "area/changes.dat": "full", "area/walkto.dat": "full", "area/shutdown.txt": "full",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(C.classify_path(path)[0], expected)

    def test_a_document_a_test_holds_to_the_code_runs_that_test(self) -> None:
        cls, modules, _ = C.classify_path("wiki/hosting-guide.md")
        self.assertEqual(cls, "docs")
        self.assertIn("test_installation_assets", modules)
        # The achievements guide is a contract and an Oracle page both.
        cls, modules, _ = C.classify_path("wiki/achievements.md")
        self.assertEqual(cls, "web-backend")
        self.assertIn("test_achievement_expansion", modules)
        self.assertIn("test_achievements", modules)
        self.assertIn("test_oracle", modules)

    def test_the_oracles_wiki_pages_are_web_backend(self) -> None:
        docs = C.oracle_docs()
        self.assertIn("wiki/player-guide.md", docs)
        cls, modules, _ = C.classify_path("wiki/player-guide.md")
        self.assertEqual(cls, "web-backend")
        self.assertIn("test_oracle", modules)

    def test_web_ui_selects_its_browser_and_bridge_tests(self) -> None:
        _cls, modules, _ = C.classify_path("webadmin/static/console-output.js")
        for module in ("test_console_output", "test_command_sequence", "test_webadmin_api"):
            self.assertIn(module, modules)
        for module in C.WEB_UI_MODULES:
            self.assertTrue((ROOT / "tests" / f"{module}.py").exists(), module)

    def test_a_browser_test_file_runs_the_module_that_runs_it(self) -> None:
        cls, modules, _ = C.classify_path("tests/test_ansi_web.js")
        self.assertEqual(cls, "tests")
        self.assertEqual(modules, ["test_console_output"])


class PlanTests(unittest.TestCase):
    def test_docs_alone_build_nothing_and_run_only_their_contracts(self) -> None:
        p = plan(["wiki/building-guide.md", "AGENTS.md"])
        self.assertEqual((p["scope"], p["class"]), ("partial", "docs"))
        self.assertEqual(p["modules"], [])
        self.assertEqual(p["jobs"], {"build": False, "tests": False, "serial": False,
                                     "sanitize": False})
        self.assertGreater(p["omitted"], 100)

    def test_a_mixed_change_takes_the_widest_class(self) -> None:
        self.assertEqual(plan(["wiki/x.md", "src/fight.c"])["scope"], "full")
        p = plan(["wiki/x.md", "webadmin/static/client.css"])
        self.assertEqual(p["class"], "web-ui")
        self.assertTrue(p["jobs"]["build"])   # its integration tests boot a server

    def test_a_test_module_alone_runs_that_module(self) -> None:
        p = plan(["tests/test_stash.py"])
        self.assertEqual(p["modules"], ["test_stash"])
        # A sanitizer module changed is played under the sanitizers too.
        self.assertEqual(p["sanitize_modules"], ["test_stash"])
        self.assertTrue(p["jobs"]["sanitize"])
        p = plan(["tests/test_login_throttle.py"])
        self.assertEqual(p["serial_modules"], ["test_login_throttle"])
        self.assertFalse(p["jobs"]["tests"])
        self.assertTrue(p["jobs"]["serial"])

    def test_state_alone_runs_nothing(self) -> None:
        p = plan(["player/Alaric", "log/toc.log", "area/built/x.are"])
        self.assertEqual((p["scope"], p["class"], p["modules"]), ("partial", "state", []))

    def test_no_base_an_unreadable_diff_or_a_forced_run_is_full(self) -> None:
        self.assertEqual(plan(["wiki/x.md"], base=None)["scope"], "full")
        self.assertEqual(plan(None)["scope"], "full")
        forced = C.plan_for(["wiki/x.md"], head="h", base="b", why_full="nightly",
                            serial=SERIAL, sanitize=SANITIZE)
        self.assertEqual((forced["scope"], forced["full_reason"]), ("full", "nightly"))
        self.assertTrue(all(forced["jobs"].values()))

    def test_a_no_runtime_class_that_moved_the_deployable_tree_is_full(self) -> None:
        p = plan(["wiki/x.md"], base_fingerprint="old", head_fingerprint="new")
        self.assertEqual(p["scope"], "full")
        self.assertIn("deployable tree changed", p["full_reason"])

    def test_shards_follow_the_work(self) -> None:
        durations = {"test_a": 600.0, "test_b": 600.0, "test_c": 10.0}
        full = {"scope": "full", "modules": [], "serial_modules": [], "sanitize_modules": ["x"]}
        self.assertEqual(C.shard_counts(full, 8, 3, durations), (8, 3))
        small = {"scope": "partial", "modules": ["test_c"], "serial_modules": [],
                 "sanitize_modules": []}
        self.assertEqual(C.shard_counts(small, 8, 3, durations), (1, 0))
        big = dict(small, modules=["test_a", "test_b", "test_c"])
        self.assertEqual(C.shard_counts(big, 8, 3, durations), (2, 0))
        none = dict(small, modules=[])
        self.assertEqual(C.shard_counts(none, 8, 3, durations), (0, 0))


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout.strip()


class RepositoryTests(unittest.TestCase):
    """Diffs, renames, deletions and fingerprints on a real repository."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        self.tests = self.repo / "tests"
        self.write({"src/game.c": "int a;\n", "wiki/guide.md": "hi\n",
                    "tests/test_one.py": "x = 1\n", "tests/test_two.py": "LiveMud(\n"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, files: dict[str, str | None], message: str = "c") -> str:
        for rel, text in files.items():
            path = self.repo / rel
            if text is None:
                git(self.repo, "rm", "-q", rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            git(self.repo, "add", rel)
        git(self.repo, "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def plan_between(self, base: str, head: str) -> dict:
        return C.plan_for(C.changed_paths(base, head, self.repo), head=head, base=base,
                          serial=SERIAL, sanitize=SANITIZE, tests=self.tests,
                          base_fingerprint=C.fingerprint(base, self.repo),
                          head_fingerprint=C.fingerprint(head, self.repo))

    def test_a_docs_commit_above_failing_code_carries_the_codes_full_suite(self) -> None:
        trusted = git(self.repo, "rev-parse", "HEAD")      # deploy-gate passed here
        self.write({"src/game.c": "int a = 1;\n"}, "code that fails CI")
        docs = self.write({"wiki/guide.md": "more\n"}, "docs on top")
        # Its own diff is documentation...
        self.assertEqual(self.plan_between(git(self.repo, "rev-parse", "HEAD~1"), docs)["class"],
                         "docs")
        # ...but from the last commit CI vouched for, it is the code's run.
        self.assertEqual(self.plan_between(trusted, docs)["scope"], "full")

    def test_renames_and_deletions_count_both_ends(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "mv", "src/game.c", "src/engine.c")
        git(self.repo, "commit", "-q", "-m", "rename")
        head = git(self.repo, "rev-parse", "HEAD")
        paths = C.changed_paths(base, head, self.repo)
        self.assertEqual(sorted(paths), ["src/engine.c", "src/game.c"])
        self.assertEqual(self.plan_between(base, head)["scope"], "full")

        base = head
        head = self.write({"tests/test_one.py": None}, "delete a module")
        p = self.plan_between(base, head)
        self.assertEqual((p["scope"], p["class"], p["modules"]), ("partial", "tests", []))

    def test_a_new_module_runs_and_needs_a_server_only_if_it_boots_one(self) -> None:
        base = git(self.repo, "rev-parse", "HEAD")
        head = self.write({"tests/test_three.py": "y = 2\n"})
        p = self.plan_between(base, head)
        self.assertEqual(p["modules"], ["test_three"])
        self.assertFalse(p["jobs"]["build"])
        head2 = self.write({"tests/test_two.py": "LiveMud(fixtures=True)\n"})
        self.assertTrue(self.plan_between(head, head2)["jobs"]["build"])

    def test_the_fingerprint_sees_code_and_ignores_docs_tests_and_state(self) -> None:
        a = git(self.repo, "rev-parse", "HEAD")
        b = self.write({"wiki/guide.md": "x\n", "tests/test_one.py": "z\n",
                        "player/Alaric": "Levl 50\n"})
        self.assertEqual(C.fingerprint(a, self.repo), C.fingerprint(b, self.repo))
        c = self.write({"src/game.c": "int b;\n"})
        self.assertNotEqual(C.fingerprint(b, self.repo), C.fingerprint(c, self.repo))

    def test_an_absent_base_is_full(self) -> None:
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertIsNone(C.changed_paths("0" * 40, head, self.repo))
        self.assertEqual(C.plan_for(None, head=head, base="0" * 40, serial=SERIAL,
                                    sanitize=SANITIZE)["scope"], "full")


class DeployerAgreementTests(unittest.TestCase):
    def test_the_fingerprint_excludes_what_toc_auto_deploy_excludes(self) -> None:
        script = (ROOT / "deploy" / "windows-vm" / "toc-auto-deploy").read_text()
        body = script[script.index("deployable() {"):]
        body = body[:body.index("\n}\n")]
        excluded = set(re.findall(r"':\(exclude(?:,glob)?\)([^']+)'", body))
        # The deployer names directories bare and globs with a pattern; the
        # classifier writes both as globs.
        want = set()
        for item in excluded:
            is_file = "*" in item or "." in item.split("/")[-1].lstrip(".")
            want.add(item if is_file else f"{item}/**")
        have = {g for g in C.DEPLOY_EXCLUDES if g != "*.md"}
        self.assertEqual(want, have)


class GatePlanTests(unittest.TestCase):
    """The gate against plans: only what the policy omits may be missing."""

    def setUp(self) -> None:
        self.gate = load(GATE, "toc_gate_plan_test")
        self.inventory = ["test_a", "test_b", "test_c", "test_live_gameplay"]

    def run_record(self, kind, modules, sha="h" * 40, name="r"):
        return {"kind": kind, "_file": name, "sha": sha,
                "modules": {m: {"status": "pass", "tests": [{"id": f"{m}.T.t",
                                                              "outcome": "pass"}]}
                            for m in modules}}

    def partial(self, modules=("test_b",), jobs=None):
        return {"scope": "partial", "class": "tests", "head": "h" * 40, "base": "b" * 40,
                "modules": list(modules), "serial_modules": [], "sanitize_modules": [],
                "jobs": jobs or {"build": True, "tests": True, "serial": False,
                                 "sanitize": False}}

    def needs(self, **override):
        base = {"plan": "success", "quick": "success", "build": "success",
                "build-sanitize": "skipped", "tests": "success", "tests-serial": "skipped",
                "sanitize-tests": "skipped"}
        base.update(override)
        return {k: {"result": v} for k, v in base.items()}

    def evaluate(self, runs, plan, needs=None, sha="h" * 40):
        problems, _ = self.gate.evaluate(runs, needs or self.needs(), self.inventory,
                                         ["test_live_gameplay"], [], [], plan=plan, sha=sha)
        return problems

    def test_a_partial_plan_passes_with_exactly_its_modules(self) -> None:
        self.assertEqual([], self.evaluate([self.run_record("normal", ["test_b"])],
                                           self.partial()))

    def test_a_selected_module_with_no_result_fails(self) -> None:
        problems = self.evaluate([self.run_record("normal", [])], self.partial())
        self.assertTrue(any("`test_b` never ran" in p for p in problems), problems)

    def test_a_module_the_plan_did_not_select_fails(self) -> None:
        problems = self.evaluate([self.run_record("normal", ["test_b", "test_c"])],
                                 self.partial())
        self.assertTrue(any("plan did not select it" in p for p in problems), problems)

    def test_a_skipped_job_passes_only_when_the_plan_did_not_need_it(self) -> None:
        runs = [self.run_record("normal", ["test_b"])]
        self.assertTrue(any("`build`" in p for p in
                            self.evaluate(runs, self.partial(), self.needs(build="skipped"))))
        self.assertTrue(any("`tests`" in p for p in
                            self.evaluate(runs, self.partial(), self.needs(tests="cancelled"))))
        self.assertTrue(any("`quick`" in p for p in
                            self.evaluate(runs, self.partial(), self.needs(quick="skipped"))))
        # A job the plan did not need, and that ran and failed, still fails.
        self.assertTrue(any("`build-sanitize`" in p for p in
                            self.evaluate(runs, self.partial(),
                                          self.needs(**{"build-sanitize": "failure"}))))

    def test_a_full_plan_needs_every_job_and_module(self) -> None:
        full = {"scope": "full", "class": "full", "head": "h" * 40, "modules": self.inventory,
                "serial_modules": ["test_live_gameplay"], "sanitize_modules": [],
                "jobs": {"build": True, "tests": True, "serial": True, "sanitize": True}}
        runs = [self.run_record("normal", ["test_a", "test_b", "test_c"]),
                self.run_record("serial", ["test_live_gameplay"], name="s")]
        problems = self.evaluate(runs, full)
        self.assertTrue(any("`build-sanitize` ended `skipped`" in p for p in problems), problems)
        all_ran = self.needs(**{"build-sanitize": "success", "sanitize-tests": "success",
                                "tests-serial": "success"})
        self.assertEqual([], self.evaluate(runs, full, all_ran))
        self.assertTrue(any("never ran" in p for p in self.evaluate(runs[:1], full, all_ran)))

    def test_results_for_another_commit_fail(self) -> None:
        stale = [self.run_record("normal", ["test_b"], sha="s" * 40)]
        self.assertTrue(any("are for commit" in p for p in self.evaluate(stale, self.partial())))
        unbound = [self.run_record("normal", ["test_b"], sha=None)]
        self.assertTrue(any("do not say which commit" in p
                            for p in self.evaluate(unbound, self.partial())))

    def test_the_plan_must_be_the_one_this_commit_deserves(self) -> None:
        good = self.partial()
        ok = lambda base, head: (True, "trusted")  # noqa: E731
        same = lambda base, head: dict(good)        # noqa: E731
        self.assertEqual([], self.gate.verify_plan(good, "h" * 40, [], [], ok, same))
        self.assertTrue(self.gate.verify_plan(None, "h" * 40, [], [], ok, same))
        self.assertTrue(any("not " in p for p in
                            self.gate.verify_plan(good, "x" * 40, [], [], ok, same)))
        untrusted = lambda base, head: (False, "no green run")  # noqa: E731
        self.assertTrue(any("not trusted" in p for p in
                            self.gate.verify_plan(good, "h" * 40, [], [], untrusted, same)))
        wider = lambda base, head: dict(good, modules=["test_b", "test_c"])  # noqa: E731
        self.assertTrue(any("`modules`" in p for p in
                            self.gate.verify_plan(good, "h" * 40, [], [], ok, wider)))
        self.assertTrue(self.gate.verify_plan(dict(good, base=None), "h" * 40, [], [], ok, same))
        # A full plan needs no base: it cannot cover too little.
        full = dict(good, scope="full", base=None)
        self.assertEqual([], self.gate.verify_plan(full, "h" * 40, [], [], untrusted, same))

    def test_an_empty_docs_run_passes_only_through_a_verified_plan(self) -> None:
        docs = dict(self.partial(modules=()), **{"class": "docs"},
                    jobs={"build": False, "tests": False, "serial": False, "sanitize": False})
        skipped = self.needs(build="skipped", tests="skipped")
        self.assertEqual([], self.evaluate([], docs, skipped))
        # The same empty run with no plan is a run that tested nothing.
        problems, _ = self.gate.evaluate([], skipped, self.inventory, ["test_live_gameplay"],
                                         [], [], plan=None)
        self.assertTrue(problems)

    def test_the_gate_cli_fails_without_a_readable_plan(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.run(
                ["python3", str(GATE), "--results", empty, "--plan", f"{empty}/missing.json",
                 "--sha", "h" * 40, "--needs", json.dumps(self.needs())],
                capture_output=True, text=True, timeout=60)
        self.assertEqual(1, out.returncode)
        self.assertIn("plan could not be read", out.stdout)


WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
RUNNER = ROOT / "scripts" / "ci" / "run_tests.py"


def job_block(text: str, job: str) -> str:
    start = text.index(f"\n  {job}:\n")
    nxt = re.search(r"\n  [a-z][a-z-]*:\n", text[start + 1:])
    return text[start:start + 1 + nxt.start()] if nxt else text[start:]


class WorkflowTests(unittest.TestCase):
    """The workflow wires the plan the way the gate expects (read as text:
    CI installs no YAML parser, and a skipped test fails the gate)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text()

    def test_branches_are_validated_by_their_pull_request_not_twice(self) -> None:
        push = self.text[self.text.index("\n  push:\n"):self.text.index("\n  pull_request:")]
        self.assertIn("branches: [main]", push)
        for trigger in ("pull_request:", "schedule:", "workflow_dispatch:"):
            self.assertIn(f"\n  {trigger}", self.text)

    def test_every_job_the_gate_maps_exists_and_the_gate_needs_them_all(self) -> None:
        gate = load(GATE, "toc_gate_workflow_test")
        jobs = {j for group in gate.PLAN_JOBS.values() for j in group} | {"plan", "quick"}
        for job in jobs:
            self.assertIn(f"\n  {job}:\n", self.text, job)
        block = job_block(self.text, "deploy-gate")
        self.assertIn("if: always()", block)
        needs = re.search(r"needs: \[([^\]]*)\]", block).group(1).replace(" ", "").split(",")
        self.assertEqual(set(needs), jobs)
        self.assertIn("--plan ci-plan/plan.json", block)
        self.assertIn('--sha "$GITHUB_SHA"', block)

    def test_no_test_job_starts_after_a_failed_preflight(self) -> None:
        for job in ("tests", "tests-serial", "sanitize-tests"):
            block = job_block(self.text, job)
            self.assertIn("quick", re.search(r"needs: \[([^\]]*)\]", block).group(1), job)
            self.assertIn("needs.quick.result == 'success'", block, job)
            self.assertIn("inputs.diagnostic", block, job)
            self.assertIn("--plan-file ci-plan/plan.json", block, job)

    def test_runners_are_pinned(self) -> None:
        self.assertNotIn("ubuntu-latest", self.text)


class RunnerPlanFileTests(unittest.TestCase):
    def test_the_runner_runs_what_the_plan_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(json.dumps({"modules": ["test_ci_classify", "test_login_throttle"],
                                             "sanitize_modules": ["test_stash"]}))
            def listed(*extra):
                out = subprocess.run(["python3", str(RUNNER), "--plan-file", str(plan_path),
                                      "--list-plan", *extra], cwd=ROOT, capture_output=True,
                                     text=True, timeout=60)
                return out.stdout.split()
            self.assertEqual(listed("--serial", "test_login_throttle", "--serial-mode", "exclude"),
                             ["test_ci_classify"])
            self.assertEqual(listed("--serial", "test_login_throttle", "--serial-mode", "only"),
                             ["test_login_throttle"])
            self.assertEqual(listed("--kind", "sanitize", "--serial", ""), ["test_stash"])


if __name__ == "__main__":
    unittest.main()
