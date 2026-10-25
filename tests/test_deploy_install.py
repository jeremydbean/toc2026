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


def code_sync() -> str:
    """toc-deploy's runtime_txt list and sync_code function, as written."""
    script = DEPLOY.read_text()
    txt = script.index("runtime_txt=")
    fn = script.index("sync_code() {")
    end = script.index("\n}\n", fn) + len("\n}\n")
    return script[txt:script.index('"\n', txt) + 2] + script[fn:end]


def install_block() -> str:
    script = DEPLOY.read_text()
    start = script.index('sync_code "$BUILD" "$CURRENT"')
    seed = script.index('if [ ! -f "$CURRENT/area/custom.are" ]', start)
    end = script.index("\nfi\n", seed) + len("\nfi\n")
    return code_sync() + script[start:end]


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


@unittest.skipUnless(shutil.which("rsync"), "rsync is required")
class RollbackStateSafetyTests(unittest.TestCase):
    """The snapshot toc-deploy takes before the stop, and the rollback from
    it, run with the script's own sync_code on real trees: the code goes
    back, and everything the game wrote between the snapshot and the
    rollback stays exactly as the game left it (redesign, 2026-10-25: the
    old rollback untarred all of area/ and rewound notes, bans, max-load
    counts and builders' rooms)."""

    def write(self, root: pathlib.Path, files: dict) -> None:
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def test_rollback_restores_code_and_keeps_live_state(self) -> None:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        build, current = tmp / "build", tmp / "current"
        snap = tmp / "rollback-code-1"
        old_code = {"merc": "old binary", "src/game.c": "old", "area/limbo.are": "old limbo",
                    "area/area.lst": "limbo.are\n$\n", "area/help.txt": "old help",
                    "webadmin/server.py": "old dashboard"}
        state_before = {"player/Zed": "Name Zed~ level 10", "gods/Zed": "god",
                        "corpse/live/1.corpse": "corpse 1", "log/toc.log": "log 1",
                        "area/notes.txt": "note 1", "area/ban.txt": "ban 1",
                        "area/maxload.txt": "max 1", "area/custom.are": "workshop 1",
                        "area/built/keep.are": "built 1", "area/bugs.txt.20261001": "old report",
                        "area/webadmin.queue": ""}
        self.write(current, {**old_code, **state_before})
        script = code_sync() + 'sync_code "$CURRENT" "$SNAP" && touch "$SNAP/.snapshot-ok"\n'
        subprocess.run(["sh", "-eu", "-c", script], check=True,
                       env=dict(os.environ, CURRENT=str(current), SNAP=str(snap)))
        self.assertTrue((snap / ".snapshot-ok").exists())
        for name in state_before:
            self.assertFalse((snap / name).exists(), f"{name} is state, not code")
        self.assertEqual((snap / "area/help.txt").read_text(), "old help",
                         "help text under area/ is code and is kept")

        # The deploy installs new code. (Sizes differ from the old: rsync
        # compares size and time, and these files are all written within
        # the same second, which a real build never is.)
        new_code = {"merc": "the new binary", "src/game.c": "the new code",
                    "area/limbo.are": "the new limbo", "area/new.are": "new area",
                    "area/help.txt": "the new help", "webadmin/server.py": "the new dashboard"}
        self.write(build, {**new_code, "area/area.lst": "limbo.are\nnew.are\n$\n",
                           "area/custom.are": "git's workshop", "player/Zed": "git's Zed"})
        subprocess.run(["sh", "-eu", "-c", install_block()], check=True,
                       env=dict(os.environ, BUILD=str(build), CURRENT=str(current)))
        self.assertEqual((current / "merc").read_text(), "the new binary")
        self.assertEqual((current / "player/Zed").read_text(), "Name Zed~ level 10")

        # ...the game runs on it and players play...
        state_after = {"player/Zed": "Name Zed~ level 11", "player/Newbie": "made today",
                       "corpse/live/2.corpse": "corpse 2", "log/toc.log": "log 2",
                       "area/notes.txt": "note 2", "area/ban.txt": "ban 2",
                       "area/maxload.txt": "max 2", "area/custom.are": "workshop 2",
                       "area/built/new.are": "built 2", "area/bugs.txt.20261025": "new report"}
        self.write(current, state_after)

        # ...and the code is rolled back.
        script = code_sync() + 'sync_code "$SNAP" "$CURRENT"\n'
        subprocess.run(["sh", "-eu", "-c", script], check=True,
                       env=dict(os.environ, CURRENT=str(current), SNAP=str(snap)))
        for name, text in old_code.items():
            self.assertEqual((current / name).read_text(), text, f"{name} is the old code again")
        self.assertFalse((current / "area/new.are").exists(), "the new code's area is gone")
        self.assertFalse((current / ".snapshot-ok").exists())
        expected = {**state_before, **state_after}
        for name, text in expected.items():
            self.assertEqual((current / name).read_text(), text,
                             f"{name} is the game's, and stays as the game left it")


if __name__ == "__main__":
    unittest.main()
