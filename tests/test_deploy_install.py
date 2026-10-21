"""toc-deploy's install step, run on synthetic trees.

Audit 2026-10-21: the deploy's rsync copied git's area/custom.are over the
live one. custom.are is where RSAVE puts builders' workshop rooms and the
state sync carries it host to git, so git's copy is up to one sync behind
-- and a deploy pinned to an older commit further -- and whatever was
saved since was lost. It is now treated like area/built/: kept, and only
seeded when the live tree has none.

The block under test is cut from the script itself, from its rsync to the
seeding of custom.are, so the test runs what the host runs.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-deploy"


def install_block() -> str:
    script = DEPLOY.read_text()
    start = script.index("rsync -a --delete \\")
    seed = script.index('if [ ! -f "$CURRENT/area/custom.are" ]', start)
    end = script.index("\nfi\n", seed) + len("\nfi\n")
    return script[start:end]


@unittest.skipUnless(shutil.which("rsync"), "rsync is required")
class DeployInstallTests(unittest.TestCase):
    def run_install(self, live_custom: str | None) -> pathlib.Path:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        build, current = tmp / "build", tmp / "current"
        for tree in (build, current):
            (tree / "area" / "built").mkdir(parents=True)
        (build / "area" / "custom.are").write_text("OLDER SYNCED CUSTOM WORLD\n")
        (build / "area" / "limbo.are").write_text("the new code, a different size\n")
        (current / "area" / "limbo.are").write_text("old code\n")
        if live_custom is not None:
            (current / "area" / "custom.are").write_text(live_custom)
        env = dict(os.environ, BUILD=str(build), CURRENT=str(current))
        subprocess.run(["sh", "-eu", "-c", install_block()], env=env, check=True)
        return current

    def test_the_live_workshop_survives_a_deploy(self) -> None:
        current = self.run_install("NEW BUILDER WORK SAVED SINCE LAST SYNC\n")
        self.assertEqual((current / "area" / "custom.are").read_text(),
                         "NEW BUILDER WORK SAVED SINCE LAST SYNC\n")
        self.assertEqual((current / "area" / "limbo.are").read_text(), "the new code, a different size\n")

    def test_a_tree_without_one_is_seeded(self) -> None:
        current = self.run_install(None)
        self.assertEqual((current / "area" / "custom.are").read_text(),
                         "OLDER SYNCED CUSTOM WORLD\n",
                         "area.lst loads it: the game will not boot without it")


if __name__ == "__main__":
    unittest.main()
