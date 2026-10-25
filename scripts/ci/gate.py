#!/usr/bin/env python3
"""The one verdict CI gives a commit: is it ready to deploy?

    python3 scripts/ci/gate.py --results DIR --needs "$NEEDS_JSON" \
        --sanitize "test_a test_b" --serial "test_live_gameplay"

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


def evaluate(runs: list[dict], needs: dict, expected: list[str], serial: list[str],
             sanitize: list[str], rules: list[dict]) -> tuple[list[str], dict]:
    problems: list[str] = []

    for job, info in sorted(needs.items()):
        result = (info or {}).get("result")
        if result != "success":
            problems.append(f"job `{job}` ended `{result}`")

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
    for module in sorted(set(seen) - set(expected)):
        problems.append(f"module `{module}` ran but is not in tests/")
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
             "records": records}
    return problems, stats


def write_summary(out, problems: list[str], stats: dict, runs: list[dict], needs: dict) -> None:
    verdict = "ready to deploy" if not problems else "NOT ready to deploy"
    print(f"## Deploy gate: {verdict}\n", file=out)
    t = stats["tests"]
    print(f"{stats['modules']} modules, {sum(t.values())} tests: "
          + ", ".join(f"{n} {k}" for k, n in sorted(t.items()))
          + f"; {stats['sanitized']} modules under sanitizers.\n", file=out)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--needs", default="{}", help="toJSON(needs) from the workflow")
    parser.add_argument("--serial", default="test_live_gameplay")
    parser.add_argument("--sanitize", default="", help="space-separated sanitizer modules")
    parser.add_argument("--allowed-skips", type=Path, default=TESTS / "ci_allowed_skips.json")
    parser.add_argument("--durations-out", type=Path)
    args = parser.parse_args()

    runs = load_runs(args.results)
    needs = json.loads(args.needs or "{}")
    expected = sorted(p.stem for p in TESTS.glob("test_*.py"))
    try:
        rules = json.loads(args.allowed_skips.read_text())["allowed"]
    except (OSError, ValueError, KeyError):
        rules = []
    problems, stats = evaluate(runs, needs, expected, args.serial.split(),
                               args.sanitize.split(), rules)
    if not runs:
        problems.insert(0, "no test results were found at all")

    write_summary(sys.stdout, problems, stats, runs, needs)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            write_summary(fh, problems, stats, runs, needs)
    if args.durations_out:
        durations = {m: round(r.get("wall", 0), 1) for m, r in sorted(stats["records"].items())
                     if r.get("status") == "pass"}
        args.durations_out.write_text(json.dumps(
            {"source": "measured by the Validate workflow's gate job", "modules": durations},
            indent=1) + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
