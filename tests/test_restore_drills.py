"""A restore drill from every place a character is kept (review, 2026-11-23:
"perform a synthetic Z-character restore drill from each backup
destination").

A synthetic character, Zdrill, is made in a throwaway world, given a title
to recognise it by, and saved. Its file then goes to each destination the
way the host sends it:

  public    toc-state-sync pushes the live tree to a bare repository
            standing in for GitHub;
  private   sync-player-backup.sh encrypts it to a key made for the drill
            and pushes it to a second bare repository;
  local     the game's own boot backup archives player/ into backups/.

The character is then deleted from the world, which forgets it -- the name
is new again -- and brought back from each destination in turn, by the
documented way for that destination, and logged in with its password: the
same character, alias and all, from every one. Nothing here touches a real
player file or a real host path.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, MudClient, create_character, login, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
TOOLS = ("git", "age", "age-keygen", "flock", "rsync", "tar")
PASSWORD = "Zdrillpass1"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


@unittest.skipIf(SKIP is not None, SKIP or "")
@unittest.skipIf(any(shutil.which(t) is None for t in TOOLS), "needs " + ", ".join(TOOLS))
class RestoreDrillTests(unittest.TestCase):

    def wait_for(self, log: Path, text: str, count: int) -> None:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if log.exists() and log.read_text(encoding="latin-1").count(text) >= count:
                return
            time.sleep(0.3)
        self.fail(f"{text!r} x{count} never came")

    def logs_in_as_the_drill_character(self, mud: LiveMud) -> str:
        with mud.connect() as client:
            login(client, "Zdrill", PASSWORD)
            said = client.sync("alias")
            client.send("quit")
            client.drain(1.0)
        return said

    def test_every_destination_brings_the_character_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with LiveMud() as mud:
                with mud.connect() as client:
                    create_character(client, "Zdrill", PASSWORD)
                    client.must("alias zdrilled look", "zdrilled")
                    client.sync("save")
                    client.send("quit")
                    client.drain(1.5)
                original = (mud.player_dir / "Zdrill").read_bytes()
                self.assertIn(b"zdrilled", original)

                # --- send it to each destination -------------------------
                live = work / "live"
                shutil.copytree(mud.player_dir, live / "player")
                (live / "log").mkdir()
                public = work / "public.git"
                git("init", "-q", "--bare", "-b", "main", str(public))
                seed = work / "seed"
                git("clone", "-q", str(public), str(seed))
                (seed / "README").write_text("seed\n")
                git("add", "README", cwd=seed)
                git("commit", "-qm", "seed", cwd=seed)
                git("push", "-q", "origin", "HEAD:main", cwd=seed)
                (work / "key").write_text("not a key\n")
                env = dict(os.environ, TOC_ROOT=str(live), STATE_REPO=str(work / "state"),
                           REMOTE=f"file://{public}", BRANCH="main", GIT_SSH_KEY=str(work / "key"),
                           LOCK_FILE=str(work / "s.lock"), TOC_DEPLOY_LOCK=str(work / "d.lock"),
                           TOC_HOST_ACTION_RESULTS=str(work / "results"),
                           TOC_SYNC_STATE_DIR=str(work / "sync-state"))
                done = subprocess.run(["sh", str(ROOT / "deploy" / "windows-vm" / "toc-state-sync")],
                                      env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(done.returncode, 0, done.stderr)

                identity = work / "drill-identity.txt"
                subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
                (work / "recipient").write_text(subprocess.run(
                    ["age-keygen", "-y", str(identity)], check=True, capture_output=True,
                    text=True).stdout)
                private = work / "private.git"
                git("init", "-q", "--bare", "-b", "main", str(private))
                env = dict(os.environ, TOC_ROOT=str(live), BACKUP_REMOTE=f"file://{private}",
                           AGE_RECIPIENT_FILE=str(work / "recipient"),
                           TOC_BACKUP_STATE_DIR=str(work / "backup-state"),
                           TOC_BACKUP_LOCK=str(work / "b.lock"))
                done = subprocess.run(["sh", str(ROOT / "deploy" / "sync-player-backup.sh")],
                                      env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(done.returncode, 0, done.stderr)

                log = mud.root / "log" / "toc.log"
                before = log.read_text(encoding="latin-1").count("Daily backup complete.")
                mud.restart()                        # the boot backup holds Zdrill now
                self.wait_for(log, "Daily backup complete.", before + 1)
                local = max((mud.root / "backups").glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)

                # --- each way back ------------------------------------------
                public_clone = work / "public-clone"
                git("clone", "-q", "--depth", "1", f"file://{public}", str(public_clone))
                private_clone = work / "private-clone"
                git("clone", "-q", "--depth", "1", "-b", "snapshots", f"file://{private}",
                    str(private_clone))
                unpacked = work / "private-out"
                done = subprocess.run(["sh", str(ROOT / "deploy" / "restore-player-backup.sh"),
                                       str(private_clone), str(identity), str(unpacked)],
                                      capture_output=True, text=True, timeout=60)
                self.assertEqual(done.returncode, 0, done.stderr)
                local_out = work / "local-out"
                local_out.mkdir()
                with tarfile.open(local) as tar:
                    member = next(m for m in tar.getmembers() if m.name.endswith("player/Zdrill"))
                    (local_out / "Zdrill").write_bytes(tar.extractfile(member).read())

                sources = {"public": public_clone / "player" / "Zdrill",
                           "private": unpacked / "player" / "Zdrill",
                           "local": local_out / "Zdrill"}
                for where, copy in sources.items():
                    with self.subTest(where=where):
                        self.assertEqual(copy.read_bytes(), original, where)
                        mud._stop()
                        (mud.player_dir / "Zdrill").unlink()
                        mud._launch()
                        with mud.connect() as client:
                            client.expect("by what name", "name:")
                            client.send("Zdrill")
                            said = client.expect("right", "password")
                            self.assertEqual(said, "right", "the name is free: it is gone")
                        mud._stop()
                        shutil.copyfile(copy, mud.player_dir / "Zdrill")
                        mud._launch()
                        said = self.logs_in_as_the_drill_character(mud)
                        self.assertIn("zdrilled", said, where)


if __name__ == "__main__":
    unittest.main()
