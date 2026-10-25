"""The CI test runner, the deploy gate and LiveMud's teardown checks
(CI and deploy redesign, 2026-10-25).

scripts/ci/run_tests.py runs every module in its own process group and
records what each test did; scripts/ci/gate.py turns every job's records
into the one verdict toc-auto-deploy deploys on. Both are played here
against throwaway test modules (TOC_TESTS_DIR), never the real suite:

* a shard plan covers every module exactly once, the same way each time;
* a pass, a skip with its reason, a failure with its traceback, a module
  with no tests and a module that hangs are each recorded as what they
  are -- the hang killed with its whole process group, a stray "server"
  included;
* a cancelled run (SIGTERM, as GitHub sends one) leaves no child behind
  and says it was cancelled, never passed;
* the gate fails a failed or skipped job, a module that never ran or ran
  twice, an unexplained skip, and a run with no results at all;
* a sanitizer report a server writes as it shuts down fails the test that
  started it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "ci" / "run_tests.py"
GATE = ROOT / "scripts" / "ci" / "gate.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill 0; it is dead for our purposes.
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split(") ", 1)[1][0] != "Z"
    except OSError:
        return True


FIXTURES = {
    "test_good": '''
        import unittest
        class Good(unittest.TestCase):
            def test_passes(self):
                self.assertTrue(True)
            @unittest.skip("needs a unicorn")
            def test_skipped(self):
                pass
    ''',
    "test_bad": '''
        import unittest
        class Bad(unittest.TestCase):
            def test_fails(self):
                self.assertEqual(1, 2, "one is not two")
            def test_sub(self):
                for n in (1, 2):
                    with self.subTest(n=n):
                        self.assertLess(n, 2)
    ''',
    "test_empty": '''
        X = 1
    ''',
    "test_hang": '''
        import os, subprocess, sys, time, unittest
        class Hang(unittest.TestCase):
            def test_hangs(self):
                child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
                with open(os.environ["PID_FILE"], "w") as fh:
                    fh.write(str(child.pid))
                time.sleep(300)
    ''',
}


class FixtureMixin:
    def make_tests(self, names) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="toc-ci-fixture-"))
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(tmp)]))
        tests = tmp / "tests"
        tests.mkdir()
        for name in names:
            (tests / f"{name}.py").write_text(textwrap.dedent(FIXTURES[name]))
        self.tmp = tmp
        return tests

    def run_runner(self, tests: Path, *args: str, timeout: float = 120, **env):
        results = self.tmp / "results.json"
        full = dict(os.environ, TOC_TESTS_DIR=str(tests), PID_FILE=str(self.tmp / "pid"), **env)
        proc = subprocess.run([sys.executable, str(RUNNER), "--results", str(results),
                               "--artifacts", str(self.tmp / "art"), *args],
                              cwd=ROOT, env=full, capture_output=True, text=True,
                              timeout=timeout)
        record = json.loads(results.read_text()) if results.exists() else None
        return proc, record


class ShardPlanTests(unittest.TestCase):
    def test_every_module_once_and_the_same_plan_every_time(self) -> None:
        runner = load(RUNNER, "toc_run_tests")
        modules = [f"test_m{n:03d}" for n in range(215)]
        durations = {m: float((n * 37) % 400 + 1) for n, m in enumerate(modules[:180])}
        plan = runner.plan_shards(modules, 8, durations)
        self.assertEqual(plan, runner.plan_shards(list(reversed(modules)), 8, durations))
        flat = [m for shard in plan for m in shard]
        self.assertEqual(sorted(flat), sorted(modules), "each module in exactly one shard")
        cost = runner.estimate(durations)
        loads = [sum(map(cost, shard)) for shard in plan]
        self.assertLess(max(loads) - min(loads), max(durations.values()),
                        "balanced to within one module")

    def test_tiny_modules_are_spread_not_piled(self) -> None:
        """Forty modules measured at 0 s once all landed on one shard."""
        runner = load(RUNNER, "toc_run_tests")
        modules = [f"test_big{n}" for n in range(8)] + [f"test_tiny{n:02d}" for n in range(40)]
        durations = {m: 600.0 for m in modules[:8]}
        durations.update({m: 0.0 for m in modules[8:]})
        sizes = [len(shard) for shard in runner.plan_shards(modules, 8, durations)]
        self.assertLessEqual(max(sizes) - min(sizes), 1, sizes)

    def test_the_real_inventory_plans_cleanly(self) -> None:
        out = subprocess.run([sys.executable, str(RUNNER), "--plan", "8"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertEqual(8, out.stdout.count("shard "))


class RunnerTests(FixtureMixin, unittest.TestCase):
    def test_outcomes_are_recorded_as_they_happened(self) -> None:
        tests = self.make_tests(["test_good", "test_bad", "test_empty"])
        proc, record = self.run_runner(tests, "--jobs", "3", "--serial", "")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        mods = record["modules"]
        self.assertEqual("pass", mods["test_good"]["status"])
        skip = [t for t in mods["test_good"]["tests"] if t["outcome"] == "skip"]
        self.assertEqual("needs a unicorn", skip[0]["reason"])
        self.assertEqual("fail", mods["test_bad"]["status"])
        failures = [f for t in mods["test_bad"]["tests"] for f in t.get("failures", [])]
        self.assertTrue(any("one is not two" in f["message"] for f in failures), failures)
        self.assertTrue(any(f.get("subtest") for f in failures), "subtests keep their names")
        self.assertIn("Traceback", json.dumps(failures))
        self.assertNotEqual("pass", mods["test_empty"]["status"],
                            "a module that ran no tests did not pass")
        self.assertIn("1 test(s) skipped", proc.stdout)

    def test_a_hung_module_is_killed_with_its_children(self) -> None:
        tests = self.make_tests(["test_hang", "test_good"])
        proc, record = self.run_runner(tests, "--jobs", "2", "--serial", "",
                                       "--module-timeout", "8")
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertEqual("timeout", record["modules"]["test_hang"]["status"])
        self.assertEqual("pass", record["modules"]["test_good"]["status"])
        pid = int((self.tmp / "pid").read_text())
        deadline = time.monotonic() + 10
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(alive(pid), "the hung module's child was killed too")

    def test_a_cancelled_run_leaves_nothing_running(self) -> None:
        tests = self.make_tests(["test_hang"])
        results = self.tmp / "results.json"
        env = dict(os.environ, TOC_TESTS_DIR=str(tests), PID_FILE=str(self.tmp / "pid"))
        proc = subprocess.Popen([sys.executable, str(RUNNER), "--results", str(results),
                                 "--serial", ""], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.monotonic() + 30
        while not (self.tmp / "pid").exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        pid = int((self.tmp / "pid").read_text())
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(130, proc.returncode, out)
        record = json.loads(results.read_text())
        self.assertTrue(record["cancelled"])
        self.assertEqual("cancelled", record["modules"]["test_hang"]["status"])
        self.assertIn("STOP  test_hang", out, "a cancelled module is not reported as failed")
        deadline = time.monotonic() + 10
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(alive(pid))

    def test_shards_and_the_serial_job_split_the_inventory(self) -> None:
        tests = self.make_tests(["test_good", "test_bad", "test_empty", "test_hang"])
        seen = []
        for k in (1, 2):
            proc = subprocess.run(
                [sys.executable, str(RUNNER), "--shard", f"{k}/2", "--serial", "test_hang",
                 "--serial-mode", "exclude", "--list-plan"], cwd=ROOT,
                env=dict(os.environ, TOC_TESTS_DIR=str(tests)),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(0, proc.returncode, proc.stderr)
            seen += proc.stdout.split()
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "--serial", "test_hang", "--serial-mode", "only",
             "--list-plan"], cwd=ROOT, env=dict(os.environ, TOC_TESTS_DIR=str(tests)),
            capture_output=True, text=True, timeout=60)
        seen += proc.stdout.split()
        self.assertEqual(sorted(seen), ["test_bad", "test_empty", "test_good", "test_hang"])


def run(kind: str, modules: dict, label: str = "x") -> dict:
    return {"kind": kind, "label": label, "_file": f"{label}.json", "modules": modules}


def passed(*skips) -> dict:
    tests = [{"id": "m.T.test_a", "outcome": "pass"}]
    tests += [{"id": f"m.T.test_{n}", "outcome": "skip", "reason": r} for n, r in skips]
    return {"status": "pass", "tests": tests, "wall": 1.0}


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = load(GATE, "toc_gate")
        self.ok_needs = {j: {"result": "success"} for j in
                         ("quick", "build", "build-sanitize", "tests", "tests-serial",
                          "sanitize-tests")}

    def evaluate(self, runs, needs=None, expected=("test_a", "test_b", "test_live_gameplay"),
                 serial=("test_live_gameplay",), sanitize=("test_a",), rules=()):
        problems, _stats = self.gate.evaluate(runs, self.ok_needs if needs is None else needs,
                                              list(expected), list(serial), list(sanitize),
                                              list(rules))
        return problems

    def good_runs(self) -> list:
        return [run("normal", {"test_a": passed()}, "n1"),
                run("normal", {"test_b": passed()}, "n2"),
                run("serial", {"test_live_gameplay": passed()}, "s"),
                run("sanitize", {"test_a": passed()}, "z1")]

    def test_everything_green_passes(self) -> None:
        self.assertEqual([], self.evaluate(self.good_runs()))

    def test_a_job_that_did_not_succeed_fails_the_gate(self) -> None:
        for result in ("failure", "cancelled", "skipped", None):
            needs = dict(self.ok_needs, build={"result": result})
            self.assertTrue(any("`build`" in p for p in self.evaluate(self.good_runs(), needs)),
                            result)

    def test_a_lost_or_doubled_module_fails_the_gate(self) -> None:
        runs = self.good_runs()
        runs[1]["modules"] = {}
        self.assertTrue(any("`test_b` never ran" in p for p in self.evaluate(runs)))
        runs = self.good_runs()
        runs[1]["modules"]["test_a"] = passed()
        self.assertTrue(any("`test_a` ran 2 times" in p for p in self.evaluate(runs)))
        runs = self.good_runs()
        runs[0]["modules"]["test_ghost"] = passed()
        self.assertTrue(any("`test_ghost` ran but is not in tests/" in p
                            for p in self.evaluate(runs)))

    def test_serial_and_sanitizer_modules_must_run_where_they_belong(self) -> None:
        runs = self.good_runs()
        runs[2]["kind"] = "normal"
        self.assertTrue(any("did not run on its own" in p for p in self.evaluate(runs)))
        runs = self.good_runs()[:3]
        self.assertTrue(any("sanitizer module `test_a` never ran" in p
                            for p in self.evaluate(runs)))

    def test_a_failure_anywhere_fails_the_gate(self) -> None:
        runs = self.good_runs()
        runs[3]["modules"]["test_a"] = {"status": "fail", "tests": [
            {"id": "m.T.test_a", "outcome": "fail",
             "failures": [{"kind": "fail", "message": "ASan said no"}]}]}
        self.assertTrue(any("sanitizer module `test_a` fail" in p for p in self.evaluate(runs)))

    def test_only_an_explained_skip_is_allowed(self) -> None:
        runs = self.good_runs()
        runs[0]["modules"]["test_a"] = passed(("b", "no built server binary"))
        self.assertTrue(any("unexpected skip" in p for p in self.evaluate(runs)))
        rules = [{"module": "test_a", "test": "*test_b", "reason_contains": "server binary"}]
        self.assertEqual([], self.evaluate(runs, rules=rules))

    def test_no_results_at_all_fails(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.run([sys.executable, str(GATE), "--results", empty,
                                  "--needs", json.dumps(self.ok_needs)],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(1, out.returncode)
        self.assertIn("no test results were found", out.stdout)

    def test_the_allowed_skips_file_explains_every_rule(self) -> None:
        data = json.loads((ROOT / "tests" / "ci_allowed_skips.json").read_text())
        for rule in data["allowed"]:
            self.assertTrue(rule.get("why"), f"say why this skip is fine in CI: {rule}")
            self.assertTrue(rule.get("reason_contains"), rule)
            self.assertNotEqual("*", rule.get("module", "*"), "name the module")


sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_mud  # noqa: E402


@unittest.skipIf(sys.platform.startswith("win"), "POSIX only")
class SanitizerTeardownTests(unittest.TestCase):
    """A fake server that writes an AddressSanitizer report as it shuts
    down, which is when leaks and use-after-free in teardown show."""

    def fake_server(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="toc-fake-server-")) / "fake-rom"
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(path.parent)]))
        path.write_text(textwrap.dedent(f'''\
            #!{sys.executable}
            import signal, socket, sys
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", int(sys.argv[1])))
            s.listen(5)
            def bye(*_):
                sys.stdout.write("==42==ERROR: AddressSanitizer: heap-use-after-free on address 0x1\\n")
                sys.stdout.flush()
                sys.exit(1)
            signal.signal(signal.SIGTERM, bye)
            while True:
                conn, _ = s.accept()
                conn.close()
            '''))
        path.chmod(0o755)
        return path

    def test_a_report_at_shutdown_fails_the_test(self) -> None:
        os.environ["TOC_SERVER_BINARY"] = str(self.fake_server())
        self.addCleanup(os.environ.pop, "TOC_SERVER_BINARY", None)
        with self.assertRaises(AssertionError) as caught:
            with live_mud.LiveMud():
                pass
        self.assertIn("heap-use-after-free", str(caught.exception))

    def test_an_expected_crash_is_not_a_failure(self) -> None:
        os.environ["TOC_SERVER_BINARY"] = str(self.fake_server())
        self.addCleanup(os.environ.pop, "TOC_SERVER_BINARY", None)
        with live_mud.LiveMud(expect_crash=True):
            pass


if __name__ == "__main__":
    unittest.main()
