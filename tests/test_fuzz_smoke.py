"""The file readers' fuzz targets build, replay what they found, and run.

fuzz/README.md has the design. This builds the three libFuzzer targets
(fuzz/build.sh, into a scratch directory), replays every input in
fuzz/regressions/ -- each one crashed, hung, leaked or tripped a sanitizer
before its fix -- and fuzzes each target briefly from the committed seeds.
A finding fails the test, with libFuzzer's report and the input left in
the scratch directory's work/<target>/artifacts.

It needs clang with libFuzzer and the sanitizer runtimes (Ubuntu: clang
and libclang-rt-18-dev); CI's shard that runs this module installs them
(.github/workflows/validate.yml). Without them it skips and says why.
Each target fuzzes a fixed number of inputs from a fixed seed, so a run
is the same run every time and CI cannot fail on luck; a real search is
fuzz/run.sh's, for minutes, not this test's. TOC_FUZZ_SMOKE_SCALE
multiplies the counts.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("numparse", "player", "area")
SCALE = max(1, int(os.environ.get("TOC_FUZZ_SMOKE_SCALE", "1")))
# Inputs per target: about ten to twenty seconds each on a CI runner.
RUNS = {"numparse": 500000, "player": 4000, "area": 100000}


def toolchain_missing() -> str | None:
    clang = shutil.which(os.environ.get("FUZZ_CC", "clang"))
    if clang is None:
        return "no clang (apt-get install clang libclang-rt-18-dev)"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.c"
        src.write_text("int LLVMFuzzerTestOneInput(const char *d, unsigned long s){return 0;}\n")
        proc = subprocess.run([clang, str(src), "-fsanitize=fuzzer,address,undefined",
                               "-o", str(Path(tmp) / "t")],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            return "clang cannot link libFuzzer with ASan/UBSan (apt-get install libclang-rt-18-dev)"
    return None


MISSING = toolchain_missing()


@unittest.skipIf(MISSING is not None, MISSING or "")
class FuzzSmoke(unittest.TestCase):
    out: Path
    tmp: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="toc-fuzz-")
        cls.out = Path(cls.tmp.name)
        env = dict(os.environ, OUT=str(cls.out))
        proc = subprocess.run(["bash", str(ROOT / "fuzz" / "build.sh")], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=1800)
        if proc.returncode != 0:
            raise AssertionError("fuzz/build.sh failed:\n"
                                 + proc.stdout.decode("latin-1", "replace")[-4000:])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def env(self) -> dict[str, str]:
        return dict(os.environ, OUT=str(self.out), TOC_FUZZ_DIR=str(self.out),
                    UBSAN_OPTIONS="print_stacktrace=1")

    def test_regressions_replay_clean(self) -> None:
        for target in TARGETS:
            inputs = sorted((ROOT / "fuzz" / "regressions" / target).glob("*"))
            if not inputs:
                continue
            with self.subTest(target=target):
                args = [str(self.out / ("fuzz_" + target))]
                env = self.env()
                if target == "area":
                    # The boot's strings are never freed, by design.
                    args.append("-detect_leaks=0")
                    env["ASAN_OPTIONS"] = "detect_leaks=0"
                proc = subprocess.run(args + [str(p) for p in inputs], env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      timeout=600)
                report = proc.stdout.decode("latin-1", "replace")
                report = "\n".join(line for line in report.splitlines()
                                   if " :: " not in line)
                self.assertEqual(proc.returncode, 0,
                                 "a fixed finding is back:\n" + report[-6000:])

    def test_each_target_fuzzes_clean(self) -> None:
        for target in TARGETS:
            with self.subTest(target=target):
                proc = subprocess.run(["bash", str(ROOT / "fuzz" / "run.sh"), target,
                                       "600", "-seed=1", "-runs=%d" % (RUNS[target] * SCALE)],
                                      env=self.env(),
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      timeout=1200)
                report = proc.stdout.decode("latin-1", "replace")
                self.assertEqual(proc.returncode, 0,
                                 "fuzz_%s found something:\n%s" % (target, report[-6000:]))
                self.assertIn("stat::number_of_executed_units", report)


if __name__ == "__main__":
    unittest.main()
