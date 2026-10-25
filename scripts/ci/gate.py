#!/usr/bin/env python3
"""The one verdict CI gives a commit: is it ready to deploy?

    python3 scripts/ci/gate.py --results DIR --needs "$NEEDS_JSON" \
        --sanitize "test_a test_b" --serial "test_login_throttle"

The Validate workflow's last job runs this after every other job, however
they ended, and it passes only if all of these hold:

* Every job it depends on succeeded. A failed, cancelled or skipped job --
  or one GitHub could not run -- fails the gate; nothing is assumed.
* Every test module ran exactly once. The modules on disk (tests/test_*.py)
  are the inventory; each must appear in exactly one normal shard or the
  serial job, with a result, and every sanitizer module in exactly one
  sanitizer shard. A module that went missing from the sharding, ran
  twice, or left no record fails the gate by name.
* Every module passed.
* No test skipped for a reason tests/ci_allowed_skips.json does not name.
  A skip in CI usually means something CI was meant to provide is not
  there -- a binary, Node, Lua, fastapi -- and such a run tested less
  than it says.

toc-auto-deploy deploys a commit only when this job, by name, succeeded on
a push to main for that exact commit. It also writes the summary GitHub
shows on the run page, and ci-durations.json, the measured module times
that tests/ci_durations.json is refreshed from.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(os.environ.get("TOC_TESTS_DIR") or ROOT / "tests")


def load_runs(directory: Path) -> list[dict]:
    runs = []
    for path in sorted(directory.rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "modules" in data and "kind" in data:
            data["_file"] = str(path.relative_to(directory))
            runs.append(data)
    return runs


def allowed(rules: list[dict], module: str, test_id: str, reason: str) -> bool:
    for rule in rules:
        if not fnmatch.fnmatchcase(module, rule.get("module", "*")):
            continue
        if not fnmatch.fnmatchcase(test_id, rule.get("test", "*")):
            continue
        if rule.get("reason_contains", "") in reason:
            return True
    return False


# Which workflow jobs each of a plan's "jobs" switches stands for. A job
# the plan did not ask for may be skipped; one it asked for must succeed;
# plan and quick always run.
PLAN_JOBS = {
    "build": ("build",),
    "tests": ("tests",),
    "serial": ("tests-serial",),
    "sanitize": ("build-sanitize", "sanitize-tests"),
}


def required_jobs(plan: dict | None) -> set[str] | None:
    """The jobs a plan needs, or None for "every job" (no plan: full)."""
    if plan is None:
        return None
    needed = set()
    for switch, jobs in PLAN_JOBS.items():
        if plan.get("jobs", {}).get(switch):
            needed.update(jobs)
    return needed


def evaluate(runs: list[dict], needs: dict, expected: list[str], serial: list[str],
             sanitize: list[str], rules: list[dict], plan: dict | None = None,
             sha: str | None = None) -> tuple[list[str], dict]:
    """With a plan, expected/serial/sanitize come from it: the modules it
    selected must each run once and pass; a job it did not ask for may be
    skipped. Without one, everything is required, as before plans."""
    problems: list[str] = []
    inventory = list(expected)
    required = required_jobs(plan)
    if plan is not None:
        if plan.get("scope") == "full":
            expected = inventory
        else:
            expected = list(plan.get("modules") or [])
            for module in sorted(set(expected) - set(inventory)):
                problems.append(f"plan selected `{module}`, which is not in tests/")
        serial = [m for m in plan.get("serial_modules") or [] if m in expected]
        sanitize = list(plan.get("sanitize_modules") or [])

    for job, info in sorted(needs.items()):
        result = (info or {}).get("result")
        if job in ("plan", "quick") or required is None or job in required:
            if result != "success":
                problems.append(f"job `{job}` ended `{result}`")
        elif result not in ("skipped", "success"):
            problems.append(f"job `{job}` ended `{result}` (not required by the plan, "
                            "but it ran and did not pass)")
    if required is not None:
        for job in sorted(required - set(needs)):
            problems.append(f"the plan needs job `{job}`, which this workflow does not have")

    for run in runs:
        if sha and run.get("sha") and run["sha"] != sha:
            problems.append(f"results `{run['_file']}` are for commit {run['sha'][:8]}, "
                            f"not {sha[:8]}")
        elif sha and not run.get("sha"):
            problems.append(f"results `{run['_file']}` do not say which commit they tested")

    seen: dict[str, list[str]] = {}
    sanitized: dict[str, list[str]] = {}
    records: dict[str, dict] = {}
    for run in runs:
        target = sanitized if run["kind"] == "sanitize" else seen
        for module, record in run["modules"].items():
            target.setdefault(module, []).append(run["_file"])
            if run["kind"] != "sanitize":
                records[module] = record
            if record.get("status") != "pass":
                where = "sanitizer " if run["kind"] == "sanitize" else ""
                detail = record.get("error") or next(
                    (f"{t['id']}: {f['message']}" for t in record.get("tests", [])
                     for f in t.get("failures", [])), "")
                problems.append(f"{where}module `{module}` {record.get('status')}: {detail[:200]}")
            for test in record.get("tests", []):
                if test.get("outcome") == "skip" and not allowed(
                        rules, module, test["id"], test.get("reason", "")):
                    problems.append(f"unexpected skip: `{test['id']}` ({test.get('reason', '')})")

    for module in expected:
        if module not in seen:
            problems.append(f"module `{module}` never ran (lost from the sharding?)")
        elif len(seen[module]) > 1:
            problems.append(f"module `{module}` ran {len(seen[module])} times: {seen[module]}")
    for module in sorted(set(seen) - set(inventory)):
        problems.append(f"module `{module}` ran but is not in tests/")
    for module in sorted(set(seen) - set(expected) - (set(seen) - set(inventory))):
        problems.append(f"module `{module}` ran but the plan did not select it")
    for module in sanitize:
        if module not in sanitized:
            problems.append(f"sanitizer module `{module}` never ran")
        elif len(sanitized[module]) > 1:
            problems.append(f"sanitizer module `{module}` ran {len(sanitized[module])} times")
    serial_ran = [m for run in runs if run["kind"] == "serial" for m in run["modules"]]
    for module in serial:
        if module in expected and module not in serial_ran:
            problems.append(f"timing-sensitive module `{module}` did not run on its own")

    totals: dict[str, int] = {}
    for record in records.values():
        for test in record.get("tests", []):
            totals[test["outcome"]] = totals.get(test["outcome"], 0) + 1
    stats = {"modules": len(seen), "sanitized": len(sanitized), "tests": totals,
             "records": records, "omitted": len(inventory) - len(expected),
             "scope": (plan or {}).get("scope", "full"), "class": (plan or {}).get("class", "full"),
             "omitted_reason": (plan or {}).get("omitted_reason", "")}
    return problems, stats


def write_summary(out, problems: list[str], stats: dict, runs: list[dict], needs: dict) -> None:
    verdict = "ready to deploy" if not problems else "NOT ready to deploy"
    print(f"## Deploy gate: {verdict}\n", file=out)
    t = stats["tests"]
    print(f"{stats['modules']} modules, {sum(t.values())} tests: "
          + ", ".join(f"{n} {k}" for k, n in sorted(t.items()))
          + f"; {stats['sanitized']} modules under sanitizers.\n", file=out)
    scope = stats.get("scope", "full")
    if scope == "full":
        print("Coverage: **full** -- every module.\n", file=out)
    else:
        print(f"Coverage: **{scope}** ({stats.get('class')}): {stats.get('omitted', 0)} "
              f"module(s) omitted by policy -- {stats.get('omitted_reason', '')}.\n", file=out)
    timing = stats.get("timing")
    if timing:
        print(f"Wall time so far {timing['wall_min']:.1f} min; "
              f"{timing['runner_min']:.1f} runner-minutes over {timing['jobs']} job(s); "
              f"run attempt {timing['attempt']}.\n", file=out)
    if problems:
        print("| Problem |\n| --- |", file=out)
        for p in problems[:200]:
            print(f"| {p.replace('|', chr(92) + '|')} |", file=out)
        print("", file=out)
    print("| Job | Kind | Modules | Wall (min) | Utilization |\n| --- | --- | ---: | ---: | ---: |",
          file=out)
    for run in sorted(runs, key=lambda r: r.get("label", "")):
        util = run.get("utilization")
        print(f"| {run.get('label') or run['_file']} | {run['kind']} | {len(run['modules'])} | "
              f"{run.get('wall', 0) / 60:.1f} | {'' if util is None else f'{util:.0%}'} |", file=out)
    print("", file=out)
    slow = sorted(stats["records"].items(), key=lambda kv: -kv[1].get("wall", 0))[:15]
    print("<details><summary>Slowest modules</summary>\n\n| Module | Seconds |\n| --- | ---: |",
          file=out)
    for module, record in slow:
        print(f"| {module} | {record.get('wall', 0):.0f} |", file=out)
    print("\n</details>", file=out)


def load_classifier():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "toc_classify", Path(__file__).resolve().parent / "classify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_plan(plan: dict | None, sha: str | None, serial: list[str], sanitize: list[str],
                trusted, recompute) -> list[str]:
    """Whether the plan the jobs ran is the plan this commit deserves.

    A full plan cannot cover too little. A partial one must be for this
    commit, stand on a trusted base (trusted(base, head) -> (ok, why)),
    and be exactly what classifying again from that base gives
    (recompute(base, head) -> plan): an artifact edited, a base made up,
    or a policy that changed under the run all fail here."""
    if plan is None:
        return ["no plan was found: a run without one proves nothing about coverage"]
    problems = []
    if sha and plan.get("head") != sha:
        problems.append(f"the plan is for {str(plan.get('head'))[:8]}, not {sha[:8]}")
    if plan.get("scope") == "full":
        return problems
    base = plan.get("base")
    if not base:
        return problems + ["a partial plan without a base"]
    ok, why = trusted(base, plan.get("head"))
    if not ok:
        problems.append(f"the plan's base {base[:8]} is not trusted: {why}")
        return problems
    again = recompute(base, plan.get("head"))
    for key in ("scope", "class", "modules", "jobs", "serial_modules", "sanitize_modules"):
        if again.get(key) != plan.get(key):
            problems.append(f"the plan's `{key}` does not match classifying {base[:8]}.."
                            f"{str(plan.get('head'))[:8]} again: {plan.get(key)!r} != "
                            f"{again.get(key)!r}")
    return problems


def run_timing(repo: str, run_id: str | None, token: str | None) -> dict | None:
    """Wall time since the run began and runner-minutes its jobs used so far
    (the gate's own still running), from GitHub's jobs list. None off CI or
    when GitHub does not answer: this is a report, never a verdict."""
    if not (repo and run_id):
        return None
    try:
        import datetime
        import urllib.request
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        def get(url):
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                        timeout=20) as response:
                return json.load(response)
        run = get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}")
        jobs = get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
                   "?filter=latest&per_page=100").get("jobs", [])

        def when(text):
            return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None
        now = datetime.datetime.now(datetime.timezone.utc)
        busy = 0.0
        for job in jobs:
            started, done = when(job.get("started_at")), when(job.get("completed_at"))
            if started:
                busy += ((done or now) - started).total_seconds()
        began = when(run.get("run_started_at") or run.get("created_at"))
        return {"wall_min": (now - began).total_seconds() / 60 if began else 0.0,
                "runner_min": busy / 60, "jobs": len(jobs),
                "attempt": run.get("run_attempt", 1)}
    except Exception:  # noqa: BLE001 -- a report, not a verdict
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--needs", default="{}", help="toJSON(needs) from the workflow")
    parser.add_argument("--serial", default="test_login_throttle")
    parser.add_argument("--sanitize", default="", help="space-separated sanitizer modules")
    parser.add_argument("--allowed-skips", type=Path, default=TESTS / "ci_allowed_skips.json")
    parser.add_argument("--durations-out", type=Path)
    parser.add_argument("--plan", type=Path,
                        help="the run's plan (scripts/ci/classify.py); required in CI")
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = parser.parse_args()

    runs = load_runs(args.results)
    needs = json.loads(args.needs or "{}")
    expected = sorted(p.stem for p in TESTS.glob("test_*.py"))
    try:
        rules = json.loads(args.allowed_skips.read_text())["allowed"]
    except (OSError, ValueError, KeyError):
        rules = []
    plan = None
    plan_problems: list[str] = []
    if args.plan is not None:
        try:
            plan = json.loads(args.plan.read_text())
        except (OSError, ValueError) as exc:
            plan_problems.append(f"the plan could not be read: {exc}")
        classify = load_classifier()
        token = os.environ.get("GITHUB_TOKEN")

        def trusted(base, head):
            return classify.verify_trusted_base(args.repo, base, head, token)

        def recompute(base, head):
            return classify.plan_for(
                classify.changed_paths(base, head), head=head, base=base,
                serial=args.serial.split(), sanitize=args.sanitize.split(),
                base_fingerprint=classify.fingerprint(base),
                head_fingerprint=classify.fingerprint(head))
        if plan is not None:
            plan_problems += verify_plan(plan, args.sha, args.serial.split(),
                                         args.sanitize.split(), trusted, recompute)
    problems, stats = evaluate(runs, needs, expected, args.serial.split(),
                               args.sanitize.split(), rules, plan=plan,
                               sha=args.sha if args.plan is not None else None)
    problems = plan_problems + problems
    stats["timing"] = run_timing(args.repo, os.environ.get("GITHUB_RUN_ID"),
                                 os.environ.get("GITHUB_TOKEN"))
    wanted = expected if plan is None or plan.get("scope") == "full" else plan.get("modules")
    if not runs and wanted:
        problems.insert(0, "no test results were found at all")

    write_summary(sys.stdout, problems, stats, runs, needs)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            write_summary(fh, problems, stats, runs, needs)
    # Only a full run measures every module; a partial one's file would
    # wipe the rest if somebody refreshed tests/ci_durations.json from it.
    if args.durations_out and (plan is None or plan.get("scope") == "full"):
        durations = {m: round(r.get("wall", 0), 1) for m, r in sorted(stats["records"].items())
                     if r.get("status") == "pass"}
        args.durations_out.write_text(json.dumps(
            {"source": "measured by the Validate workflow's gate job", "modules": durations},
            indent=1) + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
