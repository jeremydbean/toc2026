"""A rollback says which code it put back (review, 2026-10-26).

toc-deploy --rollback put old code back and left log/deployed-commit
naming the code it had just removed, so toc-game-recovery would have
rebuilt that code's binary into the old tree and toc-auto-deploy believed
it live. Now the install names the code in the tree (.code-revision: the
commit and the sha256 of the merc built from it), every snapshot carries
that identity checked against its binary (.snapshot-revision), and a
rollback records the snapshot's identity -- or "unknown", for a snapshot
from before identities were kept -- in both places, atomically. Code that
was rolled back from is held from toc-auto-deploy until newer code lands.

This plays the real toc-deploy three times against a real repository and
real trees (only systemd, make, the health checks and the clock are
stubbed), rolls back to the newest snapshot, an older one and a legacy
one, and after each asks the real toc-auto-deploy and toc-game-recovery
what they would do.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "windows-vm" / "toc-deploy"
AUTO = ROOT / "deploy" / "windows-vm" / "toc-auto-deploy"
RECOVERY = ROOT / "deploy" / "windows-vm" / "toc-game-recovery"

NEEDS = ("sh", "bash", "git", "rsync", "flock", "sha256sum", "python3")
MISSING = [tool for tool in NEEDS if shutil.which(tool) is None]
SKIP = f"needs {', '.join(MISSING)}" if MISSING else None


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipIf(SKIP is not None, SKIP or "")
class RollbackIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="toc-rollback-id-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        t = self.tmp
        self.origin, self.work, self.build = t / "origin.git", t / "work", t / "build"
        self.current, self.snaps, self.auto_state = t / "current", t / "snaps", t / "auto"
        for d in (self.snaps, self.auto_state):
            d.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True,
                       capture_output=True)
        git(self.work, "config", "user.email", "t@example.com")
        git(self.work, "config", "user.name", "t")
        git(self.work, "checkout", "-q", "-b", "main")
        self.n = 0
        self.legacy = self.commit("L")
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.build)], check=True,
                       capture_output=True)

        # The live tree as it stood before identities were kept: the
        # legacy commit's code, a player, a log, and no .code-revision.
        shutil.copytree(self.build, self.current, ignore=shutil.ignore_patterns(".git"))
        for d in ("player", "log", "area"):
            (self.current / d).mkdir(exist_ok=True)
        (self.current / "player" / "Zed").write_text("Name Zed~ level 10\n")
        (self.current / "log" / "toc.log").write_text("log 1\n")
        (self.current / "log" / "deployed-commit").write_text(
            f"{self.legacy} 2026-10-25T00:00:00Z\n")

        real_date = shutil.which("date")
        self.bin = t / "bin"
        self.bin.mkdir()
        stub(self.bin / "systemctl", 'case "$1" in is-active) echo active;; esac; exit 0')
        stub(self.bin / "make", "exit 0")
        for name in ("flock", "sleep", "chown", "install"):
            stub(self.bin / name, "exit 0")
        stub(self.bin / "curl", "echo '{\"merc\":true}'")
        stub(self.bin / "probe", "echo 0")
        # Snapshot names come from the clock; give each deploy its own.
        stub(self.bin / "date", f'[ "$1" = "+%Y%m%d-%H%M%S" ] && {{ echo "$STUB_STAMP"; exit 0; }}\n'
                                f'exec {real_date} "$@"')

    # -- the repository ------------------------------------------------
    def commit(self, label: str) -> str:
        """A commit whose code -- merc, a source file, an area -- says
        which it is, at a size no other commit's has (rsync compares size
        and time, and these are all written within a second)."""
        self.n += 1
        pad = label * self.n
        files = {"merc": f"#!/bin/sh\n# CODE-{pad}\necho 'world check {label}'\nexit 0\n",
                 "src/game.c": f"/* {pad} */\n", "area/limbo.are": f"limbo {pad}\n"}
        for name, text in files.items():
            path = self.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (self.work / "merc").chmod(0o755)
        git(self.work, "add", ".")
        git(self.work, "commit", "-q", "-m", f"code {label}")
        git(self.work, "push", "-q", "origin", "main")
        return git(self.work, "rev-parse", "HEAD")

    # -- the scripts ---------------------------------------------------
    def deploy(self, *args: str, ref: str = "", stamp: str = "", snapshot: str = "") -> tuple:
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                   BUILD=str(self.build), CURRENT=str(self.current),
                   TOC_DEPLOY_LOCKED="1", TOC_ROLLBACK_DIR=str(self.snaps),
                   TOC_GAME_PROBE=str(self.bin / "probe"), TOC_DEPLOY_REF=ref,
                   TOC_AUTO_DEPLOY_STATE=str(self.auto_state), STUB_STAMP=stamp)
        if snapshot:
            env["TOC_ROLLBACK_SNAPSHOT"] = snapshot
        r = subprocess.run(["sh", str(DEPLOY), *args], env=env, capture_output=True,
                           text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def auto_deploy(self, green: str) -> tuple:
        """toc-auto-deploy with CI green for `green`; what it said, and
        which commits it asked toc-deploy for."""
        abin = self.tmp / "autobin"
        if not abin.exists():
            abin.mkdir()
            stub(abin / "curl", 'for a; do url=$a; done\n'
                                'case "$url" in */jobs*) printf %s "$FAKE_JOBS";; '
                                '*) printf %s "$FAKE_CI";; esac')
            stub(abin / "logger", "exit 0")
            stub(abin / "players", "echo 0")
            stub(abin / "toc-deploy", f'echo "$TOC_DEPLOY_REF" >> {self.tmp}/auto-calls')
        runs = {"workflow_runs": [{"id": 1, "name": "Validate", "event": "push",
                                   "head_branch": "main", "head_sha": green,
                                   "status": "completed", "conclusion": "success",
                                   "created_at": "2026-10-26T00:00:00Z", "run_attempt": 1}]}
        jobs = {"jobs": [{"name": "deploy-gate", "status": "completed",
                          "conclusion": "success"}]}
        env = dict(os.environ, PATH=f"{abin}:{os.environ['PATH']}",
                   BUILD=str(self.build), CURRENT=str(self.current),
                   STATE_DIR=str(self.auto_state), TOC_DEPLOY_LOCK=str(self.tmp / "lock"),
                   TOC_DEPLOY_BIN=str(abin / "toc-deploy"), FAKE_CI=json.dumps(runs),
                   FAKE_JOBS=json.dumps(jobs), TOC_PLAYERS_PROBE=str(abin / "players"),
                   TOC_PLAYERS_WARN_SECONDS="0")
        calls = self.tmp / "auto-calls"
        calls.unlink(missing_ok=True)
        subprocess.run(["sh", str(AUTO)], env=env, capture_output=True, text=True,
                       timeout=120)
        status = self.current / "log" / "auto-deploy.status"
        return (status.read_text() if status.exists() else "",
                calls.read_text().split() if calls.exists() else [])

    def recovery(self) -> tuple:
        """toc-game-recovery on a copy of the live tree, with a game that
        will not start, so it reaches the rebuild: its exit status, what
        it said, the commit it checked out, and the copy."""
        live = self.tmp / f"recovery-live-{self.n}-{len(list(self.tmp.iterdir()))}"
        shutil.copytree(self.current, live, symlinks=True)
        rbin, rbuild = live.parent / (live.name + "-bin"), live.parent / (live.name + "-build")
        rbin.mkdir()
        calls = live.parent / (live.name + "-calls")
        stub(rbin / "systemctl", "exit 0")                        # never answers
        stub(rbin / "timeout", 'shift; [ "$1" = bash ] && exit 1; exec "$@"')
        stub(rbin / "git", f'echo "git $*" >> {calls}\n'
                           f'case "$*" in *clone*) mkdir -p {rbuild}/area; touch {rbuild}/.git;; '
                           f'*rev-parse*) echo rebuilt;; esac; exit 0')
        stub(rbin / "make", f"mkdir -p {rbuild}/area\n"
                            f"printf '#!/bin/sh\\n# REBUILT\\nexit 0\\n' > {rbuild}/merc\n"
                            f"chmod +x {rbuild}/merc")
        stub(rbin / "nproc", "echo 1")
        env = dict(os.environ, PATH=f"{rbin}:{os.environ['PATH']}",
                   TOC_SERVICE="test-game.service", TOC_LIVE_ROOT=str(live),
                   TOC_BUILD_ROOT=str(rbuild), TOC_STATE_DIR=str(live.parent / (live.name + "-st")),
                   TOC_BACKUP_DIR=str(live.parent / (live.name + "-bk")),
                   TOC_RECOVERY_LOCK=str(live.parent / (live.name + "-lock")),
                   TOC_DEPLOY_LOCK=str(live.parent / (live.name + "-dlock")),
                   TOC_MAINTENANCE_MARKER=str(live.parent / "no-maintenance"),
                   TOC_START_GRACE_SEC="0", TOC_MAX_PLAIN_ATTEMPTS="1",
                   TOC_REBUILD_COOLDOWN_SEC="0", TOC_MIN_FREE_MB="0")
        r = subprocess.run(["bash", str(RECOVERY)], env=env, capture_output=True, text=True,
                           timeout=120)
        resets = [line.split()[-1] for line in
                  (calls.read_text().splitlines() if calls.exists() else [])
                  if " reset --hard " in line]
        return r.returncode, r.stdout + r.stderr, resets, live

    def live_record(self) -> list:
        return (self.current / "log" / "deployed-commit").read_text().split()

    def code_line(self) -> str:
        path = self.current / ".code-revision"
        return path.read_text().strip() if path.exists() else ""

    def snapshots(self) -> list:
        return sorted(p for p in self.snaps.glob("rollback-code-*") if p.is_dir())

    # -- the test --------------------------------------------------------
    def test_rollback_records_the_code_it_put_back(self) -> None:
        a = self.commit("A")
        b = self.commit("B")
        c = self.commit("C")
        for sha, stamp in ((a, "20261026-000001"), (b, "20261026-000002"),
                           (c, "20261026-000003")):
            status, out = self.deploy(ref=sha, stamp=stamp)
            self.assertEqual(status, 0, out)
        s1, s2, s3 = self.snapshots()
        # Each snapshot names the code it holds, checked against its merc:
        # the legacy tree had no identity, so its snapshot says unknown.
        self.assertFalse((s1 / ".snapshot-revision").exists(),
                         "a tree without an identity is not given one")
        self.assertEqual((s2 / ".snapshot-revision").read_text().split(),
                         [a, sha256(s2 / "merc")])
        self.assertEqual((s3 / ".snapshot-revision").read_text().split(),
                         [b, sha256(s3 / "merc")])
        self.assertEqual(self.live_record()[0], c)
        self.assertEqual(self.code_line().split(), [c, sha256(self.current / "merc")])

        # Players play on C.
        (self.current / "player" / "Zed").write_text("Name Zed~ level 11\n")
        (self.current / "log" / "toc.log").write_text("log 2\n")

        # 1. Back to the newest snapshot, B, by hand.
        status, out = self.deploy("--rollback")
        self.assertEqual(status, 10, out)
        self.assertIn("CODE-BB", (self.current / "merc").read_text())
        self.assertEqual(self.live_record()[0], b, out)
        self.assertEqual(self.live_record()[2:], ["rollback", s3.name])
        self.assertEqual(self.code_line().split(), [b, sha256(self.current / "merc")])
        self.assertEqual((self.current / "player" / "Zed").read_text(), "Name Zed~ level 11\n")
        self.assertEqual((self.current / "log" / "toc.log").read_text(), "log 2\n")
        self.assertEqual((self.auto_state / "rolled-back").read_text().split(), [c])
        self.assertEqual([], list(self.current.glob("**/*.tmp.*")), "no temp files left")

        said, shipped = self.auto_deploy(green=c)
        self.assertEqual(shipped, [], said)
        self.assertIn("rolled back from", said)
        rc, out, resets, live = self.recovery()
        self.assertEqual(resets, [b], out)          # rebuilds B, never C
        # The rebuilt binary would not start either (nothing does here), so
        # the old one went back; through both swaps the tree kept its name,
        # checked against whichever binary is there.
        self.assertIn("rolling the previous binary back", out)
        self.assertEqual((live / ".code-revision").read_text().split(),
                         [b, sha256(live / "merc")], "a swapped binary keeps the tree's name")

        # 2. Further back, to an older snapshot: A.
        status, out = self.deploy("--rollback", snapshot=str(s2))
        self.assertEqual(status, 10, out)
        self.assertIn("CODE-AA", (self.current / "merc").read_text())
        self.assertEqual(self.live_record()[0], a)
        self.assertEqual(self.code_line().split(), [a, sha256(self.current / "merc")])
        self.assertEqual((self.auto_state / "rolled-back").read_text().split(), [c, b])
        said, shipped = self.auto_deploy(green=c)
        self.assertEqual(shipped, [], "C, rolled back from twice over, stays out: " + said)
        rc, out, resets, _ = self.recovery()
        self.assertEqual(resets, [a], out)
        # Newer code than anything rolled back from ships as usual.
        d = self.commit("D")
        said, shipped = self.auto_deploy(green=d)
        self.assertEqual(shipped, [d], said)

        # 3. To the snapshot from before identities: unknown, said so.
        status, out = self.deploy("--rollback", snapshot=str(s1))
        self.assertEqual(status, 10, out)
        self.assertIn("CODE-L", (self.current / "merc").read_text())
        self.assertEqual(self.live_record()[0], "unknown", out)
        self.assertIn("no recorded identity", out)
        self.assertEqual(self.code_line(), "")
        said, shipped = self.auto_deploy(green=d)
        self.assertEqual(shipped, [])
        self.assertIn("live code is unknown", said)
        rc, out, resets, _ = self.recovery()
        self.assertEqual((rc, resets), (1, []), out)
        self.assertIn("live code is unknown", out)
        self.assertEqual((self.current / "player" / "Zed").read_text(), "Name Zed~ level 11\n")

    def test_recovery_will_not_build_one_commit_into_another_tree(self) -> None:
        """An unhealthy deploy left for a person (exit 12) holds new code
        under the old record. Recovery used to build the recorded commit's
        binary into it."""
        b = self.commit("B")
        c = self.commit("C")
        (self.current / "log" / "deployed-commit").write_text(f"{b} 2026-10-26T00:00:00Z\n")
        (self.current / ".code-revision").write_text(f"{c} {sha256(self.current / 'merc')}\n")
        rc, out, resets, _ = self.recovery()
        self.assertEqual((rc, resets), (1, []), out)
        self.assertIn("not building one commit's binary into another's tree", out)

    def test_a_binary_changed_since_is_not_its_commit(self) -> None:
        """A snapshot of a tree whose merc is not the one its identity was
        recorded with is unknown, not the recorded commit."""
        a = self.commit("A")
        status, out = self.deploy(ref=a, stamp="20261026-000001")
        self.assertEqual(status, 0, out)
        (self.current / "merc").write_text("#!/bin/sh\n# PATCHED BY HAND\nexit 0\n")
        b = self.commit("B")
        status, out = self.deploy(ref=b, stamp="20261026-000002")
        self.assertEqual(status, 0, out)
        newest = self.snapshots()[-1]
        self.assertIn("code unknown", out)
        self.assertFalse((newest / ".snapshot-revision").exists())


if __name__ == "__main__":
    unittest.main()
