#!/usr/bin/env python3
"""Run one test module and write down what every test did.

    python3 scripts/ci/run_module.py test_stash --json out.json

It runs exactly what `python3 -m unittest discover -s tests -p
test_stash.py` runs -- the same discovery, from the repository root, with
tests/ on sys.path -- and prints the same verbose output. What it adds is
a record: each test's outcome, how long it took, why it was skipped, and
the full traceback of anything that failed. scripts/ci/run_tests.py reads
the record to report durations and skips and to balance CI shards, and
the report job uses it to prove no module went missing.

A module that discovers no tests at all fails: a typo in a module name,
or a file that lost its test class, otherwise reads as "passed".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


class RecordingResult(unittest.TextTestResult):
    """TextTestResult that also keeps a structured record of each test."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.records: dict[str, dict] = {}
        self._started: dict[str, float] = {}

    def _record(self, test: unittest.TestCase) -> dict:
        key = test.id()
        if key not in self.records:
            self.records[key] = {"id": key, "outcome": "pass", "duration": 0.0}
        return self.records[key]

    def startTest(self, test: unittest.TestCase) -> None:
        self._started[test.id()] = time.monotonic()
        # live_mud names its artifacts after the test that made them.
        os.environ["TOC_CURRENT_TEST"] = test.id()
        self._record(test)
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:
        super().stopTest(test)
        start = self._started.pop(test.id(), None)
        if start is not None:
            self._record(test)["duration"] = round(time.monotonic() - start, 3)
        os.environ.pop("TOC_CURRENT_TEST", None)

    def _fail(self, test, err, outcome: str, sub: str | None = None) -> None:
        rec = self._record(test)
        # An error outranks a failure; either outranks a pass.
        if rec["outcome"] != "error":
            rec["outcome"] = outcome
        text = "".join(traceback.format_exception(*err))
        rec.setdefault("failures", []).append({
            "kind": outcome,
            "subtest": sub,
            "message": str(err[1]).splitlines()[0][:500] if str(err[1]) else err[0].__name__,
            "traceback": text[-20000:],
        })

    def addFailure(self, test, err) -> None:
        super().addFailure(test, err)
        self._fail(test, err, "fail")

    def addError(self, test, err) -> None:
        super().addError(test, err)
        self._fail(test, err, "error")

    def addSubTest(self, test, subtest, err) -> None:
        super().addSubTest(test, subtest, err)
        if err is not None:
            kind = "fail" if issubclass(err[0], test.failureException) else "error"
            self._fail(test, err, kind, sub=subtest._subDescription())

    def addSkip(self, test, reason) -> None:
        super().addSkip(test, reason)
        rec = self._record(test)
        rec["outcome"] = "skip"
        rec["reason"] = reason

    def addExpectedFailure(self, test, err) -> None:
        super().addExpectedFailure(test, err)
        self._record(test)["outcome"] = "expected-failure"

    def addUnexpectedSuccess(self, test) -> None:
        super().addUnexpectedSuccess(test)
        self._record(test)["outcome"] = "unexpected-success"


def run(module: str, json_path: Path | None) -> int:
    os.chdir(ROOT)
    # What `python -m unittest discover -s tests` sets up: the working
    # directory (for `import webadmin`) and tests/ (for `import live_mud`).
    for entry in (str(ROOT), str(TESTS)):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    started = time.monotonic()
    record: dict = {"module": module, "status": "error", "tests": []}
    if not (TESTS / f"{module}.py").is_file():
        record["error"] = f"no such module: tests/{module}.py"
        print(record["error"])
    else:
        loader = unittest.TestLoader()
        suite = loader.discover(str(TESTS), pattern=f"{module}.py", top_level_dir=str(TESTS))
        runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2,
                                         resultclass=RecordingResult)
        result = runner.run(suite)
        record["tests"] = list(result.records.values())
        if result.testsRun == 0:
            record["error"] = "the module discovered no tests"
            print(record["error"])
        else:
            record["status"] = "pass" if result.wasSuccessful() else "fail"
    record["duration"] = round(time.monotonic() - started, 3)
    counts: dict[str, int] = {}
    for test in record["tests"]:
        counts[test["outcome"]] = counts.get(test["outcome"], 0) + 1
    record["counts"] = counts

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = json_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=1))
        tmp.replace(json_path)
    return 0 if record["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("module")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    return run(args.module, args.json)


if __name__ == "__main__":
    sys.exit(main())
