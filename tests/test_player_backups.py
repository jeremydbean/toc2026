"""Player backups (owner, 2026-10-23: "basically no way we can't restore a
player and all their gear to any state, including stash").

- Every save is a snapshot (at most one a minute, was one per half hour),
  kept as snapshot_prune in save.c says: every one from the last day, the
  newest of each hour for a week, the newest of each day for a year.
  Milestones -- before a death, a remort, a deletion, a staff change; after
  a level or a quest -- keep every one for ninety days and the newest
  hundred of each kind whatever their age.
- The state sync sends the high-value milestones to git as well, so they
  outlive the host; player/'s own history there is the five-minute copy.
- PRESTORE lists the newest thirty, or one kind (DEATHS, REMORTS, LEVELS,
  QUESTS, MILESTONES), or ALL; SHOW lists what a snapshot holds.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zbackpass1"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def stamp(seconds_ago: float) -> str:
    """A snapshot stamp, in the server's local time as save.c writes it."""
    return time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time() - seconds_ago))


class BackupSourceTests(unittest.TestCase):
    def test_levels_and_quests_are_milestones(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        level = update[update.index("void advance_level( CHAR_DATA *ch, bool is_advance )\n{"):]
        self.assertIn('player_snapshot_milestone( ch, "level", true );', level[:400])
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        wrapper = quest[quest.index("static void complete_automatic_quest( CHAR_DATA *ch, CHAR_DATA *questman,"):]
        self.assertIn('player_snapshot_milestone( ch, "quest", true );', wrapper[:500])
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("#define PLAYER_SNAPSHOT_MIN_INTERVAL 60", merc)

    def test_the_sync_sends_milestones_to_git_and_nothing_else_from_versions(self) -> None:
        if shutil.which("git") is None or shutil.which("flock") is None or shutil.which("rsync") is None:
            self.skipTest("needs git, flock and rsync")
        script = ROOT / "deploy" / "windows-vm" / "toc-state-sync"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git = lambda *a, cwd=None: subprocess.run(  # noqa: E731
                ["git", *a], cwd=cwd, check=True, capture_output=True)
            bare, seed = root / "remote.git", root / "seed"
            git("init", "--bare", "-b", "main", str(bare))
            git("clone", str(bare), str(seed))
            (seed / "README").write_text("seed\n")
            git("-c", "user.name=t", "-c", "user.email=t@t", "add", "README", cwd=seed)
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=seed)
            git("push", "-q", "origin", "HEAD:main", cwd=seed)
            live = root / "live"
            versions = live / "player" / "versions" / "Zsynced"
            versions.mkdir(parents=True)
            (live / "player" / "Zsynced").write_text("#PLAYER\nName Zsynced~\nEnd\n")
            for name in ("Zsynced.20261023_023244", "Zsynced.20261023_023244.death",
                         "Zsynced.20261023_023244_02.death", "Zsynced.20261023_023200.prepenalty",
                         "Zsynced.20261023_030000.remort", "Zsynced.20261023_031000.quest",
                         "Zsynced.20261023_032000.level", "Zsynced.20261023_033000.prestore",
                         "Zsynced.20261023_034000.gitrestore", "Zsynced.20261023_035000_02",
                         ".partial"):
                (versions / name).write_text("#PLAYER\nName Zsynced~\nEnd\n#END\n")
            # The recovery ledger rides with player/; corpses have their own.
            (live / "player" / "recovery").mkdir()
            (live / "player" / "recovery" / "ledger.tsv").write_text("1\t0\tuid\tassign\n")
            (live / "corpse" / "live").mkdir(parents=True)
            (live / "corpse" / "live" / "c1.corpse").write_text("#CORPSE\n")
            (live / "corpse" / "live" / "c1.corpse.tmp").write_text("half")
            (live / "corpse" / "history" / "Zsynced").mkdir(parents=True)
            (live / "corpse" / "history" / "Zsynced" / "c0.carried.corpse").write_text("#CORPSE\n")
            key = root / "key"
            key.write_text("not a key\n")
            env = dict(os.environ, TOC_ROOT=str(live), STATE_REPO=str(root / "state"),
                       REMOTE=str(bare), BRANCH="main", GIT_SSH_KEY=str(key),
                       LOCK_FILE=str(root / "sync.lock"),
                       TOC_DEPLOY_LOCK=str(root / "deploy.lock"))
            (root / "deploy.lock").write_text("")
            done = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
            tree = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main"],
                                  capture_output=True, text=True, check=True).stdout.split()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("player/Zsynced", tree)
        self.assertIn("player/versions/Zsynced/Zsynced.20261023_023244.death", tree)
        self.assertIn("player/versions/Zsynced/Zsynced.20261023_030000.remort", tree)
        for tagged in ("Zsynced.20261023_023244_02.death", "Zsynced.20261023_023200.prepenalty",
                       "Zsynced.20261023_033000.prestore", "Zsynced.20261023_034000.gitrestore"):
            self.assertIn("player/versions/Zsynced/" + tagged, tree)
        for kept_on_host in ("Zsynced.20261023_023244", "Zsynced.20261023_031000.quest",
                             "Zsynced.20261023_032000.level", "Zsynced.20261023_035000_02",
                             ".partial"):
            self.assertNotIn("player/versions/Zsynced/" + kept_on_host, tree)
        self.assertIn("player/recovery/ledger.tsv", tree)
        self.assertIn("corpse/live/c1.corpse", tree)
        self.assertNotIn("corpse/live/c1.corpse.tmp", tree)
        self.assertIn("corpse/history/Zsynced/c0.carried.corpse", tree)

    def test_the_encrypted_backup_checks_every_stage_and_carries_corpses(self) -> None:
        """deploy/sync-player-backup.sh: tar, its listing and age are each
        checked (sh has no pipefail), corpse/ rides along, and a stage that
        fails pushes nothing. `age` is a stand-in that copies or fails."""
        for tool in ("git", "flock", "tar", "sha256sum"):
            if shutil.which(tool) is None:
                self.skipTest(f"needs {tool}")
        script = ROOT / "deploy" / "sync-player-backup.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bare = root / "backup.git"
            subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True)
            live = root / "live"
            (live / "player" / "recovery").mkdir(parents=True)
            (live / "player" / "Zbacked").write_text("#PLAYER\nEnd\n#END\n")
            (live / "player" / "recovery" / "ledger.tsv").write_text("1\n")
            (live / "corpse" / "live").mkdir(parents=True)
            (live / "corpse" / "live" / "c1.corpse").write_text("#CORPSE\n")
            (root / "recipient").write_text("age1stand-in\n")
            (root / "key").write_text("not a key\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "age"

            def push(age_body: str):
                stub.write_text("#!/bin/sh\n" + age_body)
                stub.chmod(0o755)
                env = dict(os.environ, TOC_ROOT=str(live), BACKUP_REMOTE=str(bare),
                           AGE_RECIPIENT_FILE=str(root / "recipient"),
                           GIT_SSH_KEY=str(root / "key"), XDG_RUNTIME_DIR=str(root),
                           PATH=f"{bin_dir}:{os.environ['PATH']}")
                return subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)

            failed = push("exit 1\n")
            failed_refs = subprocess.run(["git", "--git-dir", str(bare), "branch", "--list"],
                                         capture_output=True, text=True).stdout
            # The stand-in "encrypts" by copying its last argument to -o.
            done = push('while [ $# -gt 1 ]; do [ "$1" = -o ] && out="$2"; shift; done\n'
                        'cp "$1" "$out"\n')
            snap = subprocess.run(["git", "--git-dir", str(bare), "show", "snapshots:snapshot.txt"],
                                  capture_output=True, text=True).stdout
            blob = subprocess.run(["git", "--git-dir", str(bare), "show",
                                   "snapshots:player-latest.tar.gz.age"], capture_output=True).stdout
            (root / "out.tgz").write_bytes(blob)
            listing = subprocess.run(["tar", "-tzf", str(root / "out.tgz")],
                                     capture_output=True, text=True).stdout

        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("age failed; nothing was pushed", failed.stderr)
        self.assertEqual(failed_refs.strip(), "")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("directories=player corpse", snap)
        self.assertRegex(snap, r"archive_sha256=[0-9a-f]{64}")
        self.assertIn("player/recovery/ledger.tsv", listing)
        self.assertIn("corpse/live/c1.corpse", listing)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BackupLiveTests(unittest.TestCase):
    def test_retention_the_list_and_show(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zbackstaff", 70), ("Zbacked", 20)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207)

            text = (mud.player_dir / "Zbacked").read_text(encoding="latin-1")
            versions = mud.player_dir / "versions" / "Zbacked"
            versions.mkdir(parents=True, exist_ok=True)
            day = 24 * 3600
            plant = {
                # The last day: all kept.
                "recent": [stamp(600 + 60 * i) for i in range(35)],
                # One hour three days ago: only its newest.
                "hour": [stamp(3 * day + 10 * 60), stamp(3 * day + 20 * 60), stamp(3 * day + 30 * 60)],
                # One day thirty days ago: only its newest.
                "daily": [stamp(30 * day + 3600), stamp(30 * day + 7200)],
                # Two years ago: gone.
                "ancient": [stamp(730 * day)],
            }
            for group in plant.values():
                for s in group:
                    (versions / f"Zbacked.{s}").write_text(text, encoding="latin-1")
            # A death long ago is still kept: milestones keep their newest hundred.
            old_death = stamp(730 * day)
            (versions / f"Zbacked.{old_death}.death").write_text(text, encoding="latin-1")
            # Old enough that the next save is not held back by the throttle.
            past = time.time() - 3600
            for path in versions.iterdir():
                os.utime(path, (past, past))

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as backed:
                login(staff, "Zbackstaff", PW)
                login(backed, "Zbacked", PW)
                run(staff, "scroll 0", 0.5)
                run(backed, "save", 1.5)              # a snapshot, and the prune
                names = {p.name for p in versions.iterdir()}

                listing = run(staff, "prestore zbacked", 3.0)
                deaths = run(staff, "prestore zbacked deaths", 2.0)
                shown = run(staff, f"prestore zbacked {old_death} show", 2.5)

        for s in plant["recent"]:
            self.assertIn(f"Zbacked.{s}", names)
        self.assertEqual([s for s in plant["hour"] if f"Zbacked.{s}" in names], [plant["hour"][0]])
        self.assertEqual([s for s in plant["daily"] if f"Zbacked.{s}" in names], [plant["daily"][0]])
        self.assertNotIn(f"Zbacked.{plant['ancient'][0]}", names)
        self.assertIn(f"Zbacked.{old_death}.death", names)

        # Newest thirty by default, with how many more and how to see them.
        self.assertEqual(len(re.findall(r"\[\s*\d+\]", listing)), 30, listing)
        self.assertIn("older.  PRESTORE Zbacked ALL", listing)
        self.assertRegex(listing, r"\[ 1\] (just now|\d+ minutes? ago)")
        # One kind.
        self.assertEqual(len(re.findall(r"\[\s*\d+\]", deaths)), 1, deaths)
        self.assertIn("before death", deaths)
        # What it holds, and nothing changed.
        self.assertIn("Worn and carried", shown)
        self.assertIn("sub issue sword", shown)
        self.assertIn("Stash (0)", shown)
        self.assertIn("Nothing was changed", shown)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(SKIP is not None, SKIP or "")
class GitRestoreTests(unittest.TestCase):
    def test_a_request_in_git_gives_the_gear_back_once_and_installs_a_file(self) -> None:
        """area/restores.dat (restores.c): what a cloud session can push to
        put a player back. A gear request applies at their next login,
        once; a file from git history becomes a snapshot PRESTORE lists."""
        with LiveMud() as mud:
            for name, level in (("Zgitstaff", 70), ("Zgitlost", 20)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4202)

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as lost:
                login(staff, "Zgitstaff", PW)
                login(lost, "Zgitlost", PW)
                run(staff, "slay zgitlost", 2.0)
                run(staff, "get all corpse", 1.5)     # nothing left to fetch
                for client in (staff, lost):
                    client.send("quit")
                    client.wait_closed()
            death = next(p.name for p in (mud.player_dir / "versions" / "Zgitlost").iterdir()
                         if p.name.endswith(".death"))
            death_stamp = death[len("Zgitlost."):]

            area = mud.root / "area"
            (area / "restores").mkdir(exist_ok=True)
            (area / "restores" / "Zgitlost.old").write_text(
                (mud.player_dir / "Zgitlost").read_text(encoding="latin-1"), encoding="latin-1")
            (area / "restores.dat").write_text(
                "# test\n"
                f"t1 zgitlost gear {death_stamp}\n"
                "t2 zgitlost import 20250101_000000 Zgitlost.old\n", encoding="latin-1")
            mud.restart()

            with mud.connect(timeout=120) as lost:
                login(lost, "Zgitlost", PW)
                lost.drain(1.0)
                self.assertIn("given back", lost.transcript)
                self.assertIn("sub issue sword", run(lost, "inventory", 1.0))
                lost.send("quit")
                lost.wait_closed()
            with mud.connect(timeout=120) as lost:
                login(lost, "Zgitlost", PW)
                lost.drain(1.0)
                self.assertNotIn("given back", lost.transcript)   # once
                lost.send("quit")
                lost.wait_closed()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zgitstaff", PW)
                imported = run(staff, "prestore zgitlost milestones", 2.0)
                staff.send("quit")
                staff.wait_closed()
            installed = (mud.player_dir / "versions" / "Zgitlost" / "Zgitlost.20250101_000000.import").exists()
            saved = (mud.player_dir / "Zgitlost").read_text(encoding="latin-1")
        self.assertTrue(installed)
        self.assertIn("imported from git", imported)
        self.assertIn("restore:t1", saved)


class PlayerHistoryToolTests(unittest.TestCase):
    def test_the_tool_reads_worn_carried_and_stash_apart(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import player_history

        text = ("#PLAYER\nName Ztool~\nLevl 33\nPassword xyz~\nNewGold 12\nEnd\n"
                "#O\nVnum 100\nNest 0\nShD  a worn ring~\nWear 1\nEnd\n"
                "#O\nVnum 101\nNest 0\nShD  a bag~\nWear -1\nEnd\n"
                "#O\nVnum 102\nNest 1\nShD  a gem in the bag~\nWear -1\nEnd\n"
                "#PET\nVnum 3000\nEnd\n"
                "#STASH\n#O\nVnum 103\nNest 0\nShD  a stashed axe~\nWear -1\nEnd\n#END\n")
        state = player_history.parse(text)
        self.assertEqual(state["level"], 33)
        self.assertEqual([o["short"] for o in state["worn"]], ["a worn ring"])
        self.assertEqual([o["short"] for o in state["carried"]], ["a bag", "a gem in the bag"])
        self.assertEqual([o["short"] for o in state["stash"]], ["a stashed axe"])
        self.assertEqual(state["coin"], {"NewGold": 12})
        self.assertNotIn("xyz", repr(state))          # never the password
