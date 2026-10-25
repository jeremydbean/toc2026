#!/usr/bin/env python3
"""Run test modules in parallel, record what happened, and say so plainly.

    scripts/test-parallel.sh                      # everything (the usual way in)
    python3 scripts/ci/run_tests.py test_stash    # just these
    python3 scripts/ci/run_tests.py --shard 3/8   # CI: one duration-balanced shard
    python3 scripts/ci/run_tests.py --plan 8      # show how 8 shards would split

Each module runs in a process of its own, in a session of its own, through
scripts/ci/run_module.py, which records every test's outcome, duration and
skip reason. That buys three things the old shell loop could not:

* A bounded run. A module that outlives --module-timeout is killed, with
  every game server it started (they share its process group), and
  reported as a timeout instead of holding the job until GitHub gives up.
* A clean cancel. SIGINT or SIGTERM -- a cancelled CI run, a Ctrl-C --
  kills every running module's process group before this exits, so no
  merc is left listening on a port. live_mud also asks the kernel to kill
  each server when the module that started it dies, for the SIGKILL case.
* Numbers. --results writes one JSON record for the whole run: per module
  status, duration, test counts, skips with their reasons and failures
  with their tracebacks; and the run's wall time, jobs and utilization.
  The CI report job reads these to prove nothing went missing, and
  tests/ci_durations.json, refreshed from them, balances the shards.

Timing-sensitive modules (SERIAL, default test_live_gameplay: a login
throttle measured against the wall clock) run on their own. Locally that
is after everything else; CI gives them a job of their own instead of a
tail, with --serial-mode only / exclude.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# TOC_TESTS_DIR lets tests/test_ci_runner.py point the runner at fixtures.
TESTS = Path(os.environ.get("TOC_TESTS_DIR") or ROOT / "tests")
RUN_MODULE = Path(__file__).resolve().parent / "run_module.py"
DURATIONS = TESTS / "ci_durations.json"
DEFAULT_SERIAL = "test_live_gameplay"


def all_modules() -> list[str]:
    return sorted(p.stem for p in TESTS.glob("test_*.py"))


def load_durations(path: Path) -> dict[str, float]:
    try:
        return {k: float(v) for k, v in json.loads(path.read_text())["modules"].items()}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


# Every module pays for its own interpreter and imports, however few tests
# it holds; a measured 0 (a sub-second module rounded down) would otherwise
# make the planner pile all the small ones onto one shard.
MIN_MODULE_COST = 2.0


def estimate(durations: dict[str, float]):
    known = sorted(durations.values())
    default = known[len(known) // 2] if known else 30.0

    def cost(module: str) -> float:
        return max(MIN_MODULE_COST, durations.get(module, default))
    return cost


def plan_shards(modules: list[str], count: int, durations: dict[str, float]) -> list[list[str]]:
    """Longest first onto the least loaded shard. Deterministic: ties break
    on the module name, so every shard of a run computes the same plan."""
    cost = estimate(durations)
    shards: list[list[str]] = [[] for _ in range(count)]
    load = [0.0] * count
    for module in sorted(modules, key=lambda m: (-cost(m), m)):
        target = min(range(count), key=lambda i: (load[i], i))
        shards[target].append(module)
        load[target] += cost(module)
    return shards


class Runner:
    def __init__(self, args: argparse.Namespace, modules: list[str], serial: list[str]):
        self.args = args
        self.modules = modules
        self.serial = serial
        self.cost = estimate(load_durations(args.durations))
        self.python = os.environ.get("PYTHON") or sys.executable
        self.work = Path(tempfile.mkdtemp(prefix="toc-tests-"))
        self.artifacts = args.artifacts
        self.running: dict[str, tuple[subprocess.Popen, float, Path]] = {}
        self.results: dict[str, dict] = {}
        self.stopping = False

    # -- one module ---------------------------------------------------------
    def start(self, module: str) -> None:
        log = (self.artifacts / "logs" if self.artifacts else self.work) / f"{module}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        if self.artifacts:
            env["TOC_TEST_ARTIFACTS"] = str(self.artifacts / "modules" / module)
        with open(log, "wb") as out:
            proc = subprocess.Popen(
                [self.python, str(RUN_MODULE), module,
                 "--json", str(self.work / f"{module}.json")],
                cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, env=env,
                start_new_session=True)
        self.running[module] = (proc, time.monotonic(), log)

    def kill_group(self, proc: subprocess.Popen, grace: float = 10.0) -> None:
        for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 10.0)):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                return
            try:
                proc.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                continue
            # The leader is gone; anything else in the group is a stray
            # server. A plain SIGKILL to the group finishes it.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return

    def finish(self, module: str, timed_out: bool = False, cancelled: bool = False) -> None:
        proc, started, log = self.running.pop(module)
        elapsed = time.monotonic() - started
        record_path = self.work / f"{module}.json"
        try:
            record = json.loads(record_path.read_text())
        except (OSError, ValueError):
            record = {"module": module, "status": "error", "tests": [],
                      "error": "no result record (crashed or killed)"}
        if cancelled:
            record["status"] = "cancelled"
            record["error"] = "stopped: the run was cancelled"
        elif timed_out:
            record["status"] = "timeout"
            record["error"] = f"killed after {self.args.module_timeout:.0f}s"
        elif proc.returncode != 0 and record.get("status") == "pass":
            record["status"] = "error"
            record["error"] = f"exited {proc.returncode} after passing"
        record["wall"] = round(elapsed, 2)
        record["log"] = str(log.relative_to(self.artifacts)) if self.artifacts else None
        tail = log.read_bytes()[-6000:].decode("utf-8", "replace") if log.exists() else ""
        if record["status"] != "pass":
            record["log_tail"] = tail
        self.results[module] = record
        mark = {"pass": "ok  ", "timeout": "TIME", "cancelled": "STOP"}.get(record["status"], "FAIL")
        skipped = record.get("counts", {}).get("skip", 0)
        extra = f", {skipped} skipped" if skipped else ""
        print(f"  {mark}  {module} ({elapsed:.0f}s{extra})", flush=True)
        # Artifacts of a passing module are noise; keep what a failure left.
        if record["status"] == "pass" and self.artifacts:
            shutil.rmtree(self.artifacts / "modules" / module, ignore_errors=True)

    # -- the pool -----------------------------------------------------------
    def poll(self) -> None:
        for module, (proc, started, _log) in list(self.running.items()):
            if proc.poll() is not None:
                self.finish(module)
            elif time.monotonic() - started > self.args.module_timeout:
                self.kill_group(proc)
                self.finish(module, timed_out=True)

    def run_pool(self, modules: list[str], jobs: int) -> None:
        queue = sorted(modules, key=lambda m: (-self.cost(m), m))
        while (queue or self.running) and not self.stopping:
            while queue and len(self.running) < jobs and not self.stopping:
                self.start(queue.pop(0))
            time.sleep(0.2)
            self.poll()

    def stop_all(self, signum: int, _frame) -> None:
        if self.stopping:
            return
        self.stopping = True
        print(f"\n!! {signal.Signals(signum).name}: stopping {len(self.running)} running module(s)",
              flush=True)
        for module, (proc, _started, _log) in list(self.running.items()):
            self.kill_group(proc, grace=5.0)
            self.finish(module, cancelled=True)

    # -- the whole run ------------------------------------------------------
    def run(self) -> int:
        signal.signal(signal.SIGINT, self.stop_all)
        signal.signal(signal.SIGTERM, self.stop_all)
        jobs = self.args.jobs
        print(f"Running {len(self.modules)} module(s) across {jobs} job(s)"
              + (f", then {len(self.serial)} on its own" if self.serial else "") + "\n",
              flush=True)
        start = time.monotonic()
        self.run_pool(self.modules, jobs)
        for module in self.serial:
            if not self.stopping:
                self.run_pool([module], 1)
        wall = time.monotonic() - start
        busy = sum(r.get("wall", 0.0) for r in self.results.values())
        summary = {
            "label": self.args.label,
            "kind": self.args.kind,
            "shard": self.args.shard,
            "jobs": jobs,
            "wall": round(wall, 1),
            "busy": round(busy, 1),
            "utilization": round(busy / (wall * jobs), 3) if wall > 0 and jobs else None,
            "cancelled": self.stopping,
            "modules": self.results,
        }
        if self.args.results:
            self.args.results.parent.mkdir(parents=True, exist_ok=True)
            self.args.results.write_text(json.dumps(summary, indent=1))
        report(summary, sys.stdout)
        if os.environ.get("GITHUB_STEP_SUMMARY") and self.args.step_summary:
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
                markdown(summary, fh)
        shutil.rmtree(self.work, ignore_errors=True)
        failed = [m for m, r in self.results.items() if r["status"] != "pass"]
        if self.stopping:
            return 130
        return 1 if failed else 0


def report(summary: dict, out) -> None:
    results = summary["modules"]
    wall = summary["wall"]
    print(f"\n{len(results)} modules in {int(wall // 60)}m {int(wall % 60)}s"
          f" (utilization {summary['utilization']:.0%} of {summary['jobs']} job(s))"
          if summary["utilization"] is not None else "", file=out)
    skips = [(m, t) for m, r in results.items() for t in r.get("tests", [])
             if t["outcome"] == "skip"]
    if skips:
        print(f"{len(skips)} test(s) skipped:", file=out)
        reasons: dict[str, int] = {}
        for _m, t in skips:
            reasons[t.get("reason", "")] = reasons.get(t.get("reason", ""), 0) + 1
        for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {n:4d}  {reason}", file=out)
    failed = {m: r for m, r in results.items() if r["status"] != "pass"}
    if not failed:
        print("ALL PASS", file=out)
        return
    print("\n===== failures =====", file=out)
    for module, record in failed.items():
        print(f"\n--- {module} ({record['status']}) ---", file=out)
        if record.get("error"):
            print(record["error"], file=out)
        for test in record.get("tests", []):
            for failure in test.get("failures", []):
                sub = f" {failure['subtest']}" if failure.get("subtest") else ""
                print(f"{failure['kind'].upper()}: {test['id']}{sub}", file=out)
                # Long enough for a transcript an assertion quotes: cut at 300,
                # the reply that explained a failure was lost (2026-10-25).
                print(f"  {failure['message'][:3000]}", file=out)
        if not any(t.get("failures") for t in record.get("tests", [])):
            print(record.get("log_tail", "")[-1500:], file=out)
    print(f"\n{len(failed)} module(s) failed. Rerun one, from the repository root, with\n"
          f"  python3 -m unittest discover -s tests -p '<module>.py' -v", file=out)


def markdown(summary: dict, out) -> None:
    results = summary["modules"]
    failed = {m: r for m, r in results.items() if r["status"] != "pass"}
    label = summary.get("label") or "tests"
    head = "failed" if failed else "passed"
    print(f"### {label}: {len(results)} modules {head} in {summary['wall'] / 60:.1f} min\n", file=out)
    if summary["utilization"] is not None:
        print(f"{summary['jobs']} job(s), utilization {summary['utilization']:.0%}\n", file=out)
    if failed:
        print("| Module | Status | First failure |\n| --- | --- | --- |", file=out)
        for module, record in failed.items():
            first = next((f"{t['id']}: {f['message']}" for t in record.get("tests", [])
                          for f in t.get("failures", [])), record.get("error", ""))
            first = first.replace("|", "\\|").replace("\n", " ")[:200]
            print(f"| {module} | {record['status']} | {first} |", file=out)
        print("", file=out)
    slow = sorted(results.items(), key=lambda kv: -kv[1].get("wall", 0))[:10]
    print("<details><summary>Slowest modules</summary>\n\n| Module | Seconds |\n| --- | ---: |",
          file=out)
    for module, record in slow:
        print(f"| {module} | {record.get('wall', 0):.0f} |", file=out)
    print("\n</details>\n", file=out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modules", nargs="*", help="modules to run (default: every tests/test_*.py)")
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS") or os.cpu_count() or 4))
    parser.add_argument("--shard", help="K/N: run the K-th of N duration-balanced shards")
    parser.add_argument("--plan", type=int, metavar="N", help="print an N-shard plan and exit")
    parser.add_argument("--list", action="store_true", help="print every module and exit")
    parser.add_argument("--list-plan", action="store_true",
                        help="print the modules this invocation would run, and exit")
    parser.add_argument("--durations", type=Path, default=DURATIONS)
    parser.add_argument("--serial", default=os.environ.get("SERIAL", DEFAULT_SERIAL),
                        help="space-separated modules that need the machine to themselves")
    parser.add_argument("--serial-mode", choices=("tail", "exclude", "only"), default="tail",
                        help="tail: run them last, alone (local default); exclude: leave them "
                             "out (CI shards); only: run nothing else (CI's serial job)")
    parser.add_argument("--module-timeout", type=float,
                        default=float(os.environ.get("TOC_MODULE_TIMEOUT", "1200")))
    parser.add_argument("--results", type=Path, help="write the run's JSON record here")
    parser.add_argument("--artifacts", type=Path, help="keep logs and failure artifacts here")
    parser.add_argument("--label", default="", help="a name for the summary")
    parser.add_argument("--kind", default="local",
                        help="normal, serial or sanitize: how the CI report counts this run")
    parser.add_argument("--step-summary", action="store_true",
                        help="append a markdown summary to $GITHUB_STEP_SUMMARY")
    args = parser.parse_args()

    serial_set = set(args.serial.split())
    if args.list:
        print("\n".join(all_modules()))
        return 0
    if args.plan:
        normal = [m for m in all_modules() if m not in serial_set]
        cost = estimate(load_durations(args.durations))
        for i, shard in enumerate(plan_shards(normal, args.plan, load_durations(args.durations)), 1):
            print(f"shard {i}/{args.plan}: {len(shard)} modules, ~{sum(map(cost, shard)) / 60:.1f} "
                  f"module-minutes")
        print(f"serial: {' '.join(sorted(serial_set))}")
        return 0

    modules = args.modules or all_modules()
    missing = [m for m in modules if not (TESTS / f"{m}.py").is_file()]
    if missing:
        print("no such module: " + ", ".join(f"tests/{m}.py" for m in missing))
        return 2
    if args.serial_mode == "only":
        normal, serial = [], [m for m in modules if m in serial_set]
    else:
        normal = [m for m in modules if m not in serial_set]
        serial = [m for m in modules if m in serial_set] if args.serial_mode == "tail" else []
    if args.shard:
        # A shard is one of several jobs: the serial modules would run once
        # per shard with "tail", so a shard leaves them to their own job.
        if args.serial_mode == "tail":
            serial = []
        k, n = (int(x) for x in args.shard.split("/"))
        if not 1 <= k <= n:
            parser.error("--shard K/N needs 1 <= K <= N")
        normal = plan_shards(normal, n, load_durations(args.durations))[k - 1]
    if args.list_plan:
        print("\n".join(normal + serial))
        return 0
    if args.artifacts:
        args.artifacts.mkdir(parents=True, exist_ok=True)
    return Runner(args, normal, serial).run()


if __name__ == "__main__":
    sys.exit(main())
