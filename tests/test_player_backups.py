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
from datetime import datetime, timedelta

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


def in_hour(hours_back: int, minute: int) -> str:
    """A stamp `minute` minutes into the calendar hour that began
    `hours_back` hours before this one -- so copies meant for one hourly
    bucket are in it whatever the minute now is (independent review,
    2026-10-23: 10/20/30 minutes past "three days ago" straddled an hour
    whenever the test ran early in one)."""
    start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_back)
    return (start + timedelta(minutes=minute)).strftime("%Y%m%d_%H%M%S")


def in_day(days_back: int, hour: int) -> str:
    """A stamp `hour` hours into the calendar day `days_back` days ago."""
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
    return (start + timedelta(hours=hour)).strftime("%Y%m%d_%H%M%S")


class BackupSourceTests(unittest.TestCase):
    def test_levels_and_quests_are_milestones(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        level = update[update.index("void advance_level( CHAR_DATA *ch, bool is_advance )\n{"):]
        # The whole wrapper (it also writes the journal and the hero record).
        level = level[:level.index("\n}\n")]
        self.assertIn('player_snapshot_milestone( ch, "level", true );', level)
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        wrapper = quest[quest.index("static void complete_automatic_quest( CHAR_DATA *ch, CHAR_DATA *questman,"):]
        # The whole wrapper, to its closing brace: since 2026-11-03 it also
        # notes the reward for the play journal before the milestone.
        wrapper = wrapper[:wrapper.index("\n}\n")]
        self.assertIn('player_snapshot_milestone( ch, "quest", true );', wrapper)
        self.assertLess(wrapper.index("complete_automatic_quest_body("),
                        wrapper.index('player_snapshot_milestone( ch, "quest", true );'),
                        "the copy is taken as the reward left them")
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
            # Already in git from earlier syncs: an hourly copy the host
            # has since pruned, and a milestone it pruned too.
            gone = seed / "player" / "versions" / "Zsynced"
            gone.mkdir(parents=True)
            (gone / "Zsynced.20261001_100000").write_text("#PLAYER\n#END\n")
            (gone / "Zsynced.20261001_100000.death").write_text("#PLAYER\n#END\n")
            git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-f", "README", "player",
                cwd=seed)
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=seed)
            git("push", "-q", "origin", "HEAD:main", cwd=seed)
            live = root / "live"
            now_stamp = "Zsynced." + time.strftime("%Y%m%d_%H%M%S", time.localtime())
            versions = live / "player" / "versions" / "Zsynced"
            versions.mkdir(parents=True)
            (live / "player" / "Zsynced").write_text("#PLAYER\nName Zsynced~\nEnd\n")
            for name in ("Zsynced.20261023_023244", "Zsynced.20261023_023244.death",
                         "Zsynced.20261023_023244_02.death", "Zsynced.20261023_023200.prepenalty",
                         "Zsynced.20261023_030000.remort", "Zsynced.20261023_031000.quest",
                         "Zsynced.20261023_032000.level", "Zsynced.20261023_033000.prestore",
                         "Zsynced.20261023_034000.gitrestore", "Zsynced.20261023_035000_02",
                         "Zsynced.20261023_023000", now_stamp, ".partial"):
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
                       TOC_DEPLOY_LOCK=str(root / "deploy.lock"),
                       TOC_SYNC_STATE_DIR=str(root / "sync-state"))
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
        for kept_on_host in ("Zsynced.20261023_031000.quest", "Zsynced.20261023_032000.level",
                             ".partial"):
            self.assertNotIn("player/versions/Zsynced/" + kept_on_host, tree)
        # Hourly copies (owner, 2026-10-24): the newest ordinary copy of
        # each finished hour goes up, an older one in that hour and the
        # hour still running stay behind, and a copy the host pruned
        # leaves git -- but a milestone never does.
        for hourly in ("Zsynced.20261023_023244", "Zsynced.20261023_035000_02"):
            self.assertIn("player/versions/Zsynced/" + hourly, tree)
        for not_hourly in ("Zsynced.20261023_023000", now_stamp, "Zsynced.20261001_100000"):
            self.assertNotIn("player/versions/Zsynced/" + not_hourly, tree)
        self.assertIn("player/versions/Zsynced/Zsynced.20261001_100000.death", tree)
        self.assertIn("player/recovery/ledger.tsv", tree)
        self.assertIn("corpse/live/c1.corpse", tree)
        self.assertNotIn("corpse/live/c1.corpse.tmp", tree)
        self.assertIn("corpse/history/Zsynced/c0.carried.corpse", tree)


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
                # One calendar hour three days back, and another three hours
                # before it: only the newest of each (newest first here).
                "hour": [in_hour(72, 40), in_hour(72, 25), in_hour(72, 10)],
                "hour2": [in_hour(75, 50), in_hour(75, 5)],
                # One calendar day thirty days back, and one forty: only the
                # newest of each.
                "daily": [in_day(30, 20), in_day(30, 9), in_day(30, 2)],
                "daily2": [in_day(40, 15), in_day(40, 3)],
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
        for bucket in ("hour", "hour2", "daily", "daily2"):
            self.assertEqual([s for s in plant[bucket] if f"Zbacked.{s}" in names],
                             [plant[bucket][0]], bucket)
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


@unittest.skipIf(shutil.which("rsync") is None or shutil.which("diff") is None, "needs rsync and diff")
class RestoreStateTests(unittest.TestCase):
    """deploy/toc-restore-state (review, 2026-11-23): toc-restore laid state
    into an existing tree with `rsync -a` and no --delete, so a restore over
    a non-empty install kept a character deleted since and a corpse that had
    ended -- remade at boot, gear and all -- and it never stopped the game,
    which saves back over a restore. Synthetic characters only."""

    SCRIPT = ROOT / "deploy" / "toc-restore-state"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = pathlib.Path(self._tmp.name)
        self.src, self.dst = root / "checkout", root / "srv" / "current"
        (self.src / "player" / "recovery").mkdir(parents=True)
        (self.src / "corpse" / "live").mkdir(parents=True)
        (self.src / "heroes").mkdir()
        (self.src / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nEnd\n#END\n")
        (self.src / "player" / "recovery" / "ledger.tsv").write_text("1\tmilestone\n")
        (self.src / "heroes" / "Zkept").write_text("hero\n")
        self.bin = root / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def restore(self, **env) -> subprocess.CompletedProcess:
        # Not live unless a test says so: since 2026-11-24 a standalone run
        # is live by default, and TOC_RESTORE_LIVE=0 is toc-restore's own
        # staging call -- what most of these tests stand in for.
        env.setdefault("TOC_RESTORE_LIVE", "0")
        env = {k: v for k, v in env.items() if v is not None}
        base = {k: v for k, v in os.environ.items() if k != "TOC_RESTORE_LIVE"}
        return subprocess.run(["sh", str(self.SCRIPT), str(self.src), str(self.dst)],
                              env=dict(base, PATH=f"{self.bin}:{os.environ['PATH']}", **env),
                              capture_output=True, text=True, timeout=60)

    STAMP = "20260101-000000"

    def fixed_stamp(self) -> None:
        """Every `date` the script asks for its stamp says STAMP."""
        self.stub("date", f'case "$*" in *%Y%m%d-%H%M%S*) echo {self.STAMP}; exit 0 ;; esac')

    def files(self, where: pathlib.Path) -> set[str]:
        return {str(f.relative_to(where)) for f in where.rglob("*") if f.is_file()}

    def stale_install(self) -> None:
        (self.dst / "player").mkdir(parents=True)
        (self.dst / "corpse" / "live").mkdir(parents=True)
        (self.dst / "backups").mkdir()
        (self.dst / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nolder\n")
        (self.dst / "player" / "Zgone").write_text("#PLAYER\nName Zgone~\n")
        (self.dst / "corpse" / "live" / "c-ended.corpse").write_text("#CORPSE\n")
        (self.dst / "backups" / "Nov.23.tar.gz").write_bytes(b"the game's own archive")

    def test_into_an_empty_tree_the_state_is_exactly_the_checkouts(self) -> None:
        done = self.restore()
        self.assertEqual(done.returncode, 0, done.stderr)
        for d in ("player", "corpse", "heroes"):
            self.assertEqual(self.files(self.dst / d), self.files(self.src / d), d)
        self.assertIn("compared with the checkout: 1 characters", done.stdout)

    def test_a_tree_that_holds_state_is_refused_and_left_alone(self) -> None:
        self.stale_install()
        before = self.files(self.dst)
        done = self.restore()
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn("already holds state", done.stderr)
        self.assertEqual(self.files(self.dst), before, "nothing touched")

    def test_replacing_moves_the_old_state_aside_and_keeps_nothing_stale(self) -> None:
        self.stale_install()
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.files(self.dst / "player"), self.files(self.src / "player"))
        self.assertFalse((self.dst / "player" / "Zgone").exists(), "a character the backup lacks")
        self.assertFalse((self.dst / "corpse" / "live" / "c-ended.corpse").exists(),
                         "an ended corpse would be remade at boot")
        self.assertEqual((self.dst / "player" / "Zkept").read_text(),
                         (self.src / "player" / "Zkept").read_text())
        aside = list((self.root / "srv").glob("pre-restore-*"))
        self.assertEqual(len(aside), 1, "the old state is kept, not deleted")
        self.assertTrue((aside[0] / "player" / "Zgone").exists())
        self.assertTrue((aside[0] / "corpse" / "live" / "c-ended.corpse").exists())
        self.assertTrue((self.dst / "backups" / "Nov.23.tar.gz").exists(), "backups/ is never touched")

    def test_a_live_restore_refuses_while_the_game_runs(self) -> None:
        stub = self.bin / "systemctl"
        stub.write_text('#!/bin/sh\n[ "$1" = is-active ] && [ "$3" = toc-game.service ] && exit 0\nexit 3\n')
        stub.chmod(0o755)
        done = self.restore(TOC_RESTORE_LIVE="1", TOC_DEPLOY_LOCKED="1")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("toc-game.service", done.stderr)
        self.assertFalse(self.dst.exists(), "nothing written")
        done = self.restore()                           # a drill does not ask
        self.assertEqual(done.returncode, 0, done.stderr)

    # --- a restore that fails part way leaves the tree as it was (2026-11-24) --

    def stub(self, name: str, body: str) -> None:
        real = shutil.which(name)
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\nexec {real} \"$@\"\n")
        path.chmod(0o755)

    def assert_untouched(self, before: dict[str, str], done) -> None:
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual({k: (self.dst / k).read_text() for k in before}, before)
        self.assertEqual(self.files(self.dst), set(before), "the tree is exactly as it was")
        self.assertEqual(list((self.root / "srv").glob(".*stage*")), [], "the staging tree is cleared")
        self.assertEqual(list((self.root / "srv").glob("pre-restore-*")), [], "nothing left aside")

    def snapshot(self) -> dict[str, str]:
        return {f: (self.dst / f).read_bytes().decode("latin-1") for f in self.files(self.dst)}

    # --- review, 2026-11-24 (second) -------------------------------------

    def test_a_standalone_run_is_live_unless_told_otherwise(self) -> None:
        """TOC_RESTORE_LIVE defaulted to 0: run by hand against the live tree,
        it swapped state under a running game and sync, no lock held."""
        self.stale_install()
        before = self.files(self.dst)
        self.stub("systemctl", 'case "$*" in *is-active*toc-game*) exit 0 ;; esac')
        done = self.restore(TOC_RESTORE_LIVE=None, TOC_RESTORE_REPLACE="1",
                            TOC_DEPLOY_LOCK=str(self.root / "deploy.lock"),
                            TOC_RESTORE_LOCK_WAIT="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertTrue("toc-game.service is running" in done.stderr
                        or "maintenance lock" in done.stderr, done.stderr)
        self.assertEqual(self.files(self.dst), before, "nothing touched")

    def test_the_live_tree_is_never_restored_as_a_staging_directory(self) -> None:
        self.stale_install()
        before = self.files(self.dst)
        done = self.restore(TOC_LIVE_TREE=str(self.dst), TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("is the live tree", done.stderr)
        self.assertEqual(self.files(self.dst), before)
        # Reached through a symlink, it is still the live tree.
        link = self.root / "via-link"
        link.symlink_to(self.dst.parent)
        done = self.restore(TOC_LIVE_TREE=str(link / "current"), TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)

    def test_an_aside_that_exists_is_never_moved_into(self) -> None:
        """A pre-restore-<stamp> already there (two restores in a second)
        took player/ inside its own player/."""
        self.stale_install()
        self.fixed_stamp()
        taken = self.root / "srv" / f"pre-restore-{self.STAMP}"
        (taken / "player").mkdir(parents=True)
        (taken / "player" / "Zearlier").write_text("the first restore's\n")
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.files(taken), {"player/Zearlier"}, "the earlier aside is untouched")
        mine = self.root / "srv" / f"pre-restore-{self.STAMP}-2"
        self.assertEqual((mine / "player" / "Zgone").read_text(), "#PLAYER\nName Zgone~\n")
        self.assertIn(str(mine), done.stdout)

    def test_a_rollback_beside_an_existing_aside_puts_back_the_right_state(self) -> None:
        self.stale_install()
        (self.dst / "heroes").mkdir()
        (self.dst / "heroes" / "Zold").write_text("an old plaque\n")
        self.fixed_stamp()
        taken = self.root / "srv" / f"pre-restore-{self.STAMP}"
        (taken / "player").mkdir(parents=True)
        (taken / "player" / "Zearlier").write_text("the first restore's\n")
        before = self.snapshot()
        self.stub("mv", 'for a in "$@"; do last="$a"; done\n'
                        'case "$1:$last" in *stage*/heroes:*/current/heroes) exit 1 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("putting back what was swapped", done.stderr)
        self.assertEqual(self.snapshot(), before, "the live state is exactly as it was")
        self.assertEqual(self.files(taken), {"player/Zearlier"}, "the earlier aside is untouched")
        self.assertEqual(sorted(p.name for p in (self.root / "srv").glob("pre-restore-*")),
                         [taken.name], "no half-made aside of its own left")

    def fake_proc(self, cwd: pathlib.Path, name: str = "merc") -> pathlib.Path:
        """A /proc holding one process: `name`, working in `cwd`."""
        proc = self.root / "proc"
        (proc / "4242").mkdir(parents=True)
        (proc / "4242" / "comm").write_text(name + "\n")
        (proc / "4242" / "cwd").symlink_to(cwd)
        (proc / "7").mkdir()
        (proc / "7" / "comm").write_text("merc\n")             # another tree's game
        (proc / "7" / "cwd").symlink_to(self.root)
        return proc

    def test_a_game_started_by_hand_is_seen_and_refused(self) -> None:
        """Review, 2026-11-24 (third): only toc-game.service was asked; a
        merc started by hand in the tree saves over the restore the same."""
        self.stale_install()
        (self.dst / "area").mkdir()
        before = self.files(self.dst)
        proc = self.fake_proc(self.dst / "area")
        self.stub("systemctl", "exit 3")                       # systemd: nothing running
        done = self.restore(TOC_RESTORE_LIVE=None, TOC_RESTORE_REPLACE="1", TOC_PROC=str(proc),
                            TOC_DEPLOY_LOCK=str(self.root / "deploy.lock"), TOC_RESTORE_LOCK_WAIT="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("a game is running from", done.stderr)
        self.assertIn("pid 4242", done.stderr)
        self.assertNotIn("7 ", done.stderr.split("pid", 1)[1].split(")")[0], "another tree's game is not this one")
        self.assertEqual(self.files(self.dst), before)

    def test_the_cmake_build_is_a_game_too(self) -> None:
        """Review, 2026-11-24: only a process named merc was looked for, and
        the documented CMake build runs bin/rom, which saves to the same
        tree."""
        self.stale_install()
        (self.dst / "area").mkdir()
        before = self.files(self.dst)
        proc = self.fake_proc(self.dst / "area", name="rom")
        self.stub("systemctl", "exit 3")
        done = self.restore(TOC_RESTORE_LIVE=None, TOC_RESTORE_REPLACE="1", TOC_PROC=str(proc),
                            TOC_DEPLOY_LOCK=str(self.root / "deploy.lock"), TOC_RESTORE_LOCK_WAIT="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("pid 4242", done.stderr)
        self.assertEqual(self.files(self.dst), before)

    def test_another_process_or_another_trees_game_is_not_refused(self) -> None:
        self.stale_install()
        (self.dst / "area").mkdir()
        proc = self.fake_proc(self.dst / "area", name="bash")
        done = self.restore(TOC_RESTORE_REPLACE="1", TOC_PROC=str(proc))   # staging call
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_too_little_room_for_the_staged_copy_writes_nothing(self) -> None:
        self.stale_install()
        before = self.files(self.dst)
        self.stub("df", 'printf "Filesystem 1024-blocks Used Available Capacity Mounted on\\n"\n'
                        'printf "/dev/x 1000000 990000 10000 99%% /\\n"; exit 0')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        self.assertIn("kept free", done.stderr)
        self.assertEqual(self.files(self.dst), before)
        self.assertEqual(list((self.root / "srv").glob(".*stage*")), [])
        # A smaller reserve fits the same disk, and the restore goes ahead.
        done = self.restore(TOC_RESTORE_REPLACE="1", TOC_RESTORE_RESERVE_MB="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_copy_that_fails_leaves_the_tree_as_it_was(self) -> None:
        self.stale_install()
        before = self.snapshot()
        self.stub("rsync", 'case "$*" in */corpse/*) exit 23 ;; esac')
        self.assert_untouched(before, self.restore(TOC_RESTORE_REPLACE="1"))

    def test_a_copy_that_does_not_match_leaves_the_tree_as_it_was(self) -> None:
        self.stale_install()
        before = self.snapshot()
        # A copy that "succeeds" but lands a different character file.
        real = shutil.which("rsync")
        (self.bin / "rsync").write_text(
            f'#!/bin/sh\n{real} "$@" || exit $?\n'
            'for a in "$@"; do last="$a"; done\n'
            'case "$last" in */player/) echo torn > "${last}Zkept" ;; esac\n')
        (self.bin / "rsync").chmod(0o755)
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertIn("does not match the checkout", done.stderr)
        self.assert_untouched(before, done)

    def test_a_swap_that_fails_part_way_puts_back_what_was_swapped(self) -> None:
        self.stale_install()
        (self.dst / "heroes").mkdir()
        (self.dst / "heroes" / "Zold").write_text("an old plaque\n")
        before = self.snapshot()
        # player/ and gods/ are already swapped when heroes/ will not move in.
        self.stub("mv", 'for a in "$@"; do last="$a"; done\n'
                        'case "$1:$last" in *stage*/heroes:*/current/heroes) exit 1 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertIn("putting back what was swapped", done.stderr)
        self.assert_untouched(before, done)

    @unittest.skipIf(shutil.which("flock") is None, "needs flock (util-linux)")
    def test_a_live_restore_waits_for_the_maintenance_lock_and_gives_up(self) -> None:
        lock = self.root / "deploy.lock"
        lock.write_text("")
        holder = subprocess.Popen(["flock", str(lock), "sleep", "30"])
        try:
            time.sleep(0.3)
            (self.bin / "systemctl").write_text("#!/bin/sh\nexit 3\n")
            (self.bin / "systemctl").chmod(0o755)
            done = self.restore(TOC_RESTORE_LIVE="1", TOC_DEPLOY_LOCK=str(lock),
                                TOC_RESTORE_LOCK_WAIT="1")
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertIn("maintenance lock", done.stderr)
            self.assertFalse(self.dst.exists(), "nothing written while a deploy holds it")
        finally:
            holder.kill()
            holder.wait()
        done = self.restore(TOC_RESTORE_LIVE="1", TOC_DEPLOY_LOCK=str(lock))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_mirror_on_a_drive_restores_with_github_gone(self) -> None:
        """The off-GitHub copy (review, 2026-11-23): both the public
        repository and the private mirror live in one GitHub account. The
        documented answer -- `git clone --mirror` to a drive the owner holds,
        `remote update` to keep it current -- restores with GitHub gone, and
        toc-restore takes it as REPO=<path>."""
        git = lambda *a, cwd=None: subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
            cwd=cwd, check=True, capture_output=True, text=True).stdout
        github = self.root / "github.git"
        git("init", "-q", "--bare", "-b", "main", str(github))
        work = self.root / "work"
        git("clone", "-q", str(github), str(work))
        (work / "player").mkdir()
        (work / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nv1\n")
        git("add", "-A", cwd=work)
        git("commit", "-qm", "v1", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)
        drive = self.root / "drive" / "toc-mirror.git"
        git("clone", "-q", "--mirror", str(github), str(drive))          # once
        (work / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nv2\n")
        (work / "player" / "Znew").write_text("#PLAYER\nName Znew~\n")
        git("add", "-A", cwd=work)
        git("commit", "-qm", "v2", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)
        git("--git-dir", str(drive), "remote", "update")                  # thereafter
        shutil.rmtree(github)                                              # GitHub gone
        shutil.rmtree(work)
        checkout = self.root / "restore-checkout"
        git("clone", "-q", "--branch", "main", str(drive), str(checkout))  # toc-restore's clone, REPO=<drive>
        self.src = checkout
        done = self.restore()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((self.dst / "player" / "Zkept").read_text(), "#PLAYER\nName Zkept~\nv2\n",
                         "the latest state, from the drive alone")
        self.assertTrue((self.dst / "player" / "Znew").exists())
        # And every earlier state is in the drive's history.
        self.assertIn("v1", git("--git-dir", str(drive), "log", "-p", "--format=", "main", "--", "player/Zkept"))

    def test_toc_restore_never_merges_state_with_its_code_copy(self) -> None:
        source = (ROOT / "deploy" / "toc-restore").read_text()
        self.assertTrue('RESTORE_STATE="$(dirname "$0")/toc-restore-state"' in source
                        and 'sh "$RESTORE_STATE" "$BUILD" "$STAGE"' in source,
                        "toc-restore does not lay state down with toc-restore-state")
        for d in ("player", "gods", "heroes", "log", "corpse"):
            self.assertIn(f"--exclude '/{d}/'", source)
        self.assertNotIn('rsync -a "$BUILD/$d/" "$CURRENT/$d/"', source)



@unittest.skipIf(shutil.which("flock") is None or shutil.which("rsync") is None
                 or shutil.which("make") is None, "needs flock, rsync and make (the Linux host)")
class RestoreSwapTests(unittest.TestCase):
    """deploy/toc-restore end to end against a synthetic repository (review,
    2026-11-24): it used to copy the code over the live tree and only then
    let toc-restore-state refuse or fail, and it held no lock, so the sync's
    path unit, the recovery timer and auto-deploy could all act mid-restore.
    Now the new tree is staged whole, then swapped in under the maintenance
    lock with the game stopped, and every failure puts the old tree back.
    The live path runs in a scratch prefix (TOC_RESTORE_DRILL=0 with
    TOC_RESTORE_SKIP_SERVICES=1) with a stand-in systemctl."""

    SCRIPT = ROOT / "deploy" / "toc-restore"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = pathlib.Path(self._tmp.name)
        repo = self.repo = root / "repo"
        for d in ("player", "gods", "heroes", "log", "corpse/live", "area"):
            (repo / d).mkdir(parents=True)
        (repo / "player" / "Znew").write_text("#PLAYER\nName Znew~\n")
        (repo / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nrestored\n")
        (repo / "gods" / "Zgod").write_text("god\n")
        (repo / "heroes" / "Zkept").write_text("hero\n")
        (repo / "log" / "note.log").write_text("log\n")
        (repo / "corpse" / "live" / "c1.corpse").write_text("#CORPSE\n")
        (repo / "area" / "limbo.are").write_text("#AREA\n")
        (repo / "area" / "shutdown.txt").write_text("tracked marker\n")
        (repo / "Makefile").write_text(
            "merc:\n\tprintf '#!/bin/sh\\necho world ok\\n' > merc && chmod +x merc\n"
            "clean:\n\trm -f merc\n")
        (repo / "code.c").write_text("new code\n")
        git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "synthetic")
        self.prefix = root / "srv"
        self.current = self.prefix / "current"
        for d in ("player", "backups", "area", "corpse/live"):
            (self.current / d).mkdir(parents=True)
        (self.current / "player" / "Zkept").write_text("#PLAYER\nName Zkept~\nolder\n")
        (self.current / "player" / "Zgone").write_text("#PLAYER\nName Zgone~\n")
        (self.current / "corpse" / "live" / "c-ended.corpse").write_text("#CORPSE\n")
        (self.current / "backups" / "Nov.23.tar.gz").write_bytes(b"archive")
        (self.current / "area" / "pkilldata.txt").write_text("runtime\n")
        (self.current / "code.c").write_text("old code\n")
        (self.current / "merc").write_text("#!/bin/sh\necho old\n")
        self.bin = root / "bin"
        self.bin.mkdir()
        self.lock = root / "deploy.lock"
        self.lock.write_text("")
        self.calls = root / "systemctl.calls"
        self.running = root / "running"
        self.running.write_text("toc-game.service\ntoc-web.service\n")
        # A systemctl that keeps a list of running units, and notes at every
        # stop and start whether the maintenance lock was held at the time.
        (self.bin / "systemctl").write_text(f"""#!/bin/sh
held=free; flock -n {self.lock} true || held=locked
case "$1" in
  is-active) [ "$2" = --quiet ] && shift; grep -qx "$2" {self.running} ;;
  stop) echo "stop $2 $held" >> {self.calls}; grep -vx "$2" {self.running} > {self.running}.n; mv {self.running}.n {self.running} ;;
  start) echo "start $2 $held" >> {self.calls}; echo "$2" >> {self.running} ;;
  *) exit 0 ;;
esac
""")
        (self.bin / "systemctl").chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def restore(self, live: bool = True, **env) -> subprocess.CompletedProcess:
        e = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", REPO=str(self.repo),
                 TOC_PREFIX=str(self.prefix), TOC_DEPLOY_LOCK=str(self.lock), **env)
        if live:
            e.update(TOC_RESTORE_DRILL="0", TOC_RESTORE_SKIP_SERVICES="1")
        # The backups' verdict has tests of its own below.
        e.setdefault("TOC_RESTORE_BACKUP_CHECK", "0")
        return subprocess.run(["sh", str(self.SCRIPT)], env=e, capture_output=True,
                              text=True, timeout=120)

    def files(self, where: pathlib.Path) -> dict[str, bytes]:
        return {str(f.relative_to(where)): f.read_bytes() for f in where.rglob("*") if f.is_file()}

    def calls_made(self) -> list[str]:
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def stub(self, name: str, body: str) -> None:
        real = shutil.which(name)
        (self.bin / name).write_text(f"#!/bin/sh\n{body}\nexec {real} \"$@\"\n")
        (self.bin / name).chmod(0o755)

    def assert_old_tree_back(self, before: dict[str, bytes], done) -> None:
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(self.files(self.current), before, "the old installation is exactly as it was")
        self.assertEqual(sorted(p.name for p in self.prefix.iterdir() if p.name != "build"),
                         ["current"], "no staging tree or half-made aside left behind")
        self.assertEqual(sorted(self.running.read_text().split()),
                         ["toc-game.service", "toc-web.service"], "what was running runs again")

    def test_a_live_restore_swaps_the_whole_tree_under_the_lock(self) -> None:
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        now = self.files(self.current)
        self.assertEqual(now["code.c"], b"new code\n")
        self.assertEqual(now["player/Zkept"], b"#PLAYER\nName Zkept~\nrestored\n")
        self.assertNotIn("player/Zgone", now, "a character the backup lacks")
        self.assertNotIn("corpse/live/c-ended.corpse", now, "an ended corpse")
        self.assertNotIn("area/shutdown.txt", now, "the game would not start")
        self.assertEqual(now["backups/Nov.23.tar.gz"], b"archive", "the game's own archives come across")
        self.assertEqual(now["area/pkilldata.txt"], b"runtime\n", "host-only runtime files are kept")
        aside = list(self.prefix.glob("pre-restore-*"))
        self.assertEqual(len(aside), 1)
        self.assertEqual((aside[0] / "player" / "Zgone").read_text(), "#PLAYER\nName Zgone~\n",
                         "the old tree is kept whole")
        calls = self.calls_made()
        self.assertIn("stop toc-game.service locked", calls)
        self.assertIn("stop toc-web.service locked", calls)
        self.assertTrue(all(c.endswith("locked") for c in calls),
                        f"every stop and start under the maintenance lock: {calls}")
        self.assertEqual(sorted(self.running.read_text().split()),
                         ["toc-game.service", "toc-web.service"])

    def test_a_tree_holding_state_is_refused_before_anything_is_written(self) -> None:
        before = self.files(self.current)
        done = self.restore()
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertEqual(self.files(self.current), before)
        self.assertFalse((self.prefix / "build").exists(), "refused before the clone")
        self.assertEqual(self.calls_made(), [], "the game was never stopped")

    def test_a_state_copy_that_fails_never_stops_the_game(self) -> None:
        before = self.files(self.current)
        self.stub("rsync", 'case "$*" in */gods/*) exit 23 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assert_old_tree_back(before, done)
        self.assertEqual(self.calls_made(), [], "staging fails before anything live is touched")

    def test_a_code_copy_that_fails_never_stops_the_game(self) -> None:
        before = self.files(self.current)
        self.stub("rsync", "case \"$*\" in *--exclude*.git/*) exit 23 ;; esac")
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertIn("copying the code", done.stderr)
        self.assert_old_tree_back(before, done)
        self.assertEqual(self.calls_made(), [])

    def test_carrying_the_runtime_files_fails_and_the_game_comes_back(self) -> None:
        before = self.files(self.current)
        self.stub("rsync", 'case "$*" in *--ignore-existing*) exit 23 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assert_old_tree_back(before, done)
        self.assertIn("start toc-game.service locked", self.calls_made())

    def test_moving_the_old_tree_aside_fails_and_the_game_comes_back(self) -> None:
        before = self.files(self.current)
        self.stub("mv", 'for a in "$@"; do last="$a"; done\n'
                        'case "$1:$last" in */current:*/pre-restore-*) exit 1 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertIn("moving the old tree aside failed", done.stderr)
        self.assert_old_tree_back(before, done)

    def test_moving_the_new_tree_in_fails_and_the_old_one_is_put_back(self) -> None:
        before = self.files(self.current)
        self.stub("mv", 'for a in "$@"; do last="$a"; done\n'
                        'case "$1:$last" in */.restore-stage-*:*/current) exit 1 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertIn("the old one is back", done.stderr)
        self.assert_old_tree_back(before, done)

    # --- review, 2026-11-24 (second) -------------------------------------

    STAMP = "20260101-000000"

    def fixed_stamp(self) -> None:
        self.stub("date", f'case "$*" in *%Y%m%d-%H%M%S*) echo {self.STAMP}; exit 0 ;; esac')

    def taken_aside(self) -> pathlib.Path:
        taken = self.prefix / f"pre-restore-{self.STAMP}"
        (taken / "player").mkdir(parents=True)
        (taken / "player" / "Zearlier").write_text("the first restore's\n")
        return taken

    def test_an_existing_aside_is_never_moved_into(self) -> None:
        """`mv current pre-restore-<stamp>` into a name already there put the
        live tree inside it, and a rollback then put back the wrong tree."""
        self.fixed_stamp()
        taken = self.taken_aside()
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(set(self.files(taken)), {"player/Zearlier"}, "the earlier aside is untouched")
        mine = self.prefix / f"pre-restore-{self.STAMP}-2"
        self.assertEqual((mine / "code.c").read_text(), "old code\n", "the old tree, whole")
        self.assertEqual((self.current / "code.c").read_text(), "new code\n")

    def test_a_rollback_beside_an_existing_aside_puts_back_the_old_tree(self) -> None:
        self.fixed_stamp()
        taken = self.taken_aside()
        before = self.files(self.current)
        self.stub("mv", 'for a in "$@"; do last="$a"; done\n'
                        'case "$1:$last" in */.restore-stage-*:*/current) exit 1 ;; esac')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("the old one is back", done.stderr)
        self.assertEqual(self.files(self.current), before, "the old installation is exactly as it was")
        self.assertEqual(set(self.files(taken)), {"player/Zearlier"}, "the earlier aside is untouched")
        self.assertEqual(sorted(p.name for p in self.prefix.glob("pre-restore-*")), [taken.name])
        self.assertEqual(sorted(self.running.read_text().split()),
                         ["toc-game.service", "toc-web.service"])

    def test_too_little_room_stops_it_before_the_game_is_touched(self) -> None:
        before = self.files(self.current)
        self.stub("df", 'printf "Filesystem 1024-blocks Used Available Capacity Mounted on\\n"\n'
                        'printf "/dev/x 1000000 990000 10000 99%% /\\n"; exit 0')
        done = self.restore(TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        self.assertIn("kept free for the game's saves", done.stderr)
        self.assertEqual(self.files(self.current), before)
        self.assertEqual(self.calls_made(), [], "the game was never stopped")
        self.assertEqual(list(self.prefix.glob(".restore-stage-*")), [])

    def test_a_game_started_by_hand_stops_the_swap_and_the_old_tree_stays(self) -> None:
        """Review, 2026-11-24 (third): systemd stops toc-game, but a merc
        someone started by hand in current/area/ goes on saving."""
        (self.current / "area").mkdir(exist_ok=True)
        proc = self.root / "proc"
        (proc / "4242").mkdir(parents=True)
        (proc / "4242" / "comm").write_text("merc\n")
        (proc / "4242" / "cwd").symlink_to(self.current / "area")
        before = self.files(self.current)
        done = self.restore(TOC_RESTORE_REPLACE="1", TOC_PROC=str(proc))
        self.assertIn("that systemd did not start (merc or rom, pid 4242", done.stderr)
        self.assert_old_tree_back(before, done)

    def test_a_cmake_game_started_by_hand_stops_the_swap_too(self) -> None:
        (self.current / "area").mkdir(exist_ok=True)
        proc = self.root / "proc"
        (proc / "4243").mkdir(parents=True)
        (proc / "4243" / "comm").write_text("rom\n")
        (proc / "4243" / "cwd").symlink_to(self.current / "area")
        before = self.files(self.current)
        done = self.restore(TOC_RESTORE_REPLACE="1", TOC_PROC=str(proc))
        self.assertIn("that systemd did not start (merc or rom, pid 4243", done.stderr)
        self.assert_old_tree_back(before, done)

    def backup_setup(self, sync_writes_receipt: bool) -> dict:
        """A key, a git whose push is accepted, and a systemctl whose start of
        toc-state-sync.service writes (or does not) a last-success receipt."""
        key = self.root / "key"
        key.write_text("synthetic key\n")
        receipts = self.root / "receipts"
        receipts.mkdir()
        (receipts / "last-success").write_text("time=1000\ntime_utc=1970-01-01T00:16:40Z\n")
        (receipts / "last-attempt").write_text("result=failed\nreason=Permission denied (publickey)\n")
        real_git = shutil.which("git")
        (self.bin / "git").write_text(
            '#!/bin/sh\nfor a in "$@"; do [ "$a" = push ] && exit 0; done\n'
            f'exec {real_git} "$@"\n')
        (self.bin / "git").chmod(0o755)
        text = (self.bin / "systemctl").read_text()
        if sync_writes_receipt:
            text = text.replace(
                "  start) ",
                f'  start) [ "$2" = toc-state-sync.service ] && printf "time=%s\\ntime_utc=now\\n'
                f'remote_commit=abcdef123456\\n" "$(date +%s)" > {receipts}/last-success && exit 0; ', 1)
        (self.bin / "systemctl").write_text(text)
        return dict(TOC_RESTORE_BACKUP_CHECK="1", GIT_SSH_KEY=str(key),
                    TOC_STATE_REMOTE="git@example.invalid:x.git", TOC_SYNC_STATE_DIR=str(receipts))

    def test_a_receipt_that_does_not_match_the_clone_is_not_proof(self) -> None:
        """Review, 2026-11-27: a receipt proves a sync finished, not that it
        carried the restored state. One naming a commit that is not the
        sync's clone's is turned down (the real drill is RestoreSyncDrillTests)."""
        done = self.restore(TOC_RESTORE_REPLACE="1", **self.backup_setup(sync_writes_receipt=True))
        self.assertEqual(done.returncode, 6, done.stdout + done.stderr)
        self.assertIn("a sync finished after the restore, but the receipt's commit (abcdef123456) "
                      "is not the sync's clone", done.stderr)

    def test_push_access_without_a_sync_since_is_not_called_backed_up(self) -> None:
        done = self.restore(TOC_RESTORE_REPLACE="1", **self.backup_setup(sync_writes_receipt=False))
        self.assertEqual(done.returncode, 6, done.stdout + done.stderr)
        self.assertIn("push access works", done.stderr)
        self.assertIn("no state sync has reached GitHub since the restore began", done.stderr)
        self.assertIn("Permission denied (publickey)", done.stderr, "the last attempt is named")
        self.assertIn("GAME RUNNING, BACKUPS NOT VERIFIED", done.stdout)
        self.assertTrue({"toc-game.service", "toc-web.service"} <= set(self.running.read_text().split()),
                        "the game is up regardless")

    def test_a_game_that_does_not_come_back_is_not_called_done(self) -> None:
        # A start that does nothing: the unit stays down.
        (self.bin / "systemctl").write_text(
            (self.bin / "systemctl").read_text().replace(
                'start) echo "start $2 $held" >> ' + str(self.calls) + '; echo "$2" >> '
                + str(self.running) + ' ;;',
                'start) echo "start $2 $held" >> ' + str(self.calls) + '; exit 1 ;;'))
        done = self.restore(TOC_RESTORE_REPLACE="1", TOC_RESTORE_VERIFY_WAIT="1")
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        self.assertIn("RESTORE NOT COMPLETE", done.stdout)
        self.assertIn("NOT RUNNING toc-game.service", done.stderr)
        self.assertNotIn("== done", done.stdout)

    def test_a_held_lock_is_waited_for_then_given_up_with_the_game_running(self) -> None:
        before = self.files(self.current)
        holder = subprocess.Popen(["flock", str(self.lock), "sleep", "30"])
        try:
            time.sleep(0.3)
            done = self.restore(TOC_RESTORE_REPLACE="1", TOC_RESTORE_LOCK_WAIT="1")
        finally:
            holder.kill()
            holder.wait()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("maintenance lock", done.stderr)
        self.assertEqual(self.files(self.current), before)
        self.assertFalse((self.prefix / "build").exists(), "the deploy's checkout is left to it")
        self.assertEqual(self.calls_made(), [], "a deploy holding the lock keeps the game")

    def test_a_rehearsal_takes_no_lock_and_stops_nothing(self) -> None:
        done = self.restore(live=False, TOC_RESTORE_REPLACE="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.calls_made(), [])
        self.assertEqual((self.current / "code.c").read_text(), "new code\n")


@unittest.skipIf(shutil.which("flock") is None or shutil.which("rsync") is None
                 or shutil.which("make") is None, "needs flock, rsync and make (the Linux host)")
class RestoreSyncDrillTests(unittest.TestCase):
    """The whole of it in a scratch tree (review, 2026-11-27): the real
    toc-restore, the real toc-state-sync started as systemctl would start it,
    one maintenance lock between them, and a bare repository for GitHub.
    toc-restore used to start the sync while still holding the lock the
    sync takes shared, so the sync skipped and nothing reached the remote;
    and a receipt from before the swap would have passed."""

    SCRIPT = ROOT / "deploy" / "toc-restore"
    SYNC = ROOT / "deploy" / "windows-vm" / "toc-state-sync"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = pathlib.Path(self._tmp.name)
        git = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
        seed = root / "seed"
        for d in ("player", "gods", "heroes", "log", "corpse/live", "area"):
            (seed / d).mkdir(parents=True)
        for n in range(12):
            (seed / "player" / f"Zrestored{chr(97 + n)}").write_text(
                f"#PLAYER\nName Zrestored{chr(97 + n)}~\nEnd\n#END\n")
        (seed / "gods" / "Zgod").write_text("god\n")
        (seed / "area" / "limbo.are").write_text("#AREA\n")
        (seed / "Makefile").write_text(
            "merc:\n\tprintf '#!/bin/sh\\necho world ok\\n' > merc && chmod +x merc\n"
            "clean:\n\trm -f merc\n")
        git("init", "-q", "-b", "main", cwd=seed)
        git("add", "-A", cwd=seed)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "synthetic", cwd=seed)
        self.remote = root / "remote.git"
        git("clone", "-q", "--bare", str(seed), str(self.remote))
        self.prefix = root / "srv"
        self.current = self.prefix / "current"
        (self.current / "player").mkdir(parents=True)
        (self.current / "player" / "Zold").write_text("#PLAYER\nName Zold~\nEnd\n#END\n")
        self.lock = root / "deploy.lock"
        self.lock.write_text("")
        self.key = root / "key"
        self.key.write_text("synthetic\n")
        self.receipts = root / "receipts"
        self.receipts.mkdir()
        self.bin = root / "bin"
        self.bin.mkdir()
        sync_env = " ".join([
            f"TOC_ROOT={self.current}", f"STATE_REPO={self.prefix / 'state-repo'}",
            f"REMOTE=file://{self.remote}", "BRANCH=main", f"GIT_SSH_KEY={self.key}",
            f"LOCK_FILE={root / 'sync.lock'}", f"TOC_DEPLOY_LOCK={self.lock}",
            f"TOC_SYNC_STATE_DIR={self.receipts}", f"TOC_HOST_ACTION_RESULTS={root / 'results'}",
            "TOC_SYNC_LOCK_WAIT=2", "TOC_SYNC_DEBOUNCE=0",
            "GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t"])
        # A systemctl that starts the real sync, as the unit would; the rest
        # is the running list RestoreSwapTests keeps.
        self.running = root / "running"
        self.running.write_text("toc-game.service\n")
        (self.bin / "systemctl").write_text(f"""#!/bin/sh
case "$1" in
  is-active) [ "$2" = --quiet ] && shift; grep -qx "$2" {self.running} ;;
  stop) grep -vx "$2" {self.running} > {self.running}.n; mv {self.running}.n {self.running} ;;
  start) if [ "$2" = toc-state-sync.service ]; then env {sync_env} sh {self.SYNC} > {root}/sync.out 2>&1;
         else echo "$2" >> {self.running}; fi ;;
  *) exit 0 ;;
esac
""")
        (self.bin / "systemctl").chmod(0o755)
        (self.bin / "logger").write_text("#!/bin/sh\nexit 0\n")
        (self.bin / "logger").chmod(0o755)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def remote_players(self) -> set[str]:
        listed = subprocess.run(["git", "--git-dir", str(self.remote), "ls-tree", "--name-only",
                                 "main", "player/"], capture_output=True, text=True, check=True)
        return {pathlib.Path(p).name for p in listed.stdout.split()}

    def test_the_restored_state_reaches_the_remote_under_the_real_lock(self) -> None:
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", REPO=str(self.remote),
                   TOC_PREFIX=str(self.prefix), TOC_DEPLOY_LOCK=str(self.lock),
                   TOC_RESTORE_DRILL="0", TOC_RESTORE_SKIP_SERVICES="1", TOC_RESTORE_REPLACE="1",
                   TOC_RESTORE_BACKUP_CHECK="1", GIT_SSH_KEY=str(self.key),
                   TOC_STATE_REMOTE=f"file://{self.remote}", TOC_SYNC_STATE_DIR=str(self.receipts),
                   STATE_REPO=str(self.prefix / "state-repo"), TOC_RESTORE_VERIFY_WAIT="1",
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        done = subprocess.run(["sh", str(self.SCRIPT)], env=env, capture_output=True, text=True,
                              timeout=300)
        sync_out = (self.root / "sync.out").read_text() if (self.root / "sync.out").exists() else ""
        self.assertNotIn("a deploy is running", sync_out, "the sync was shut out by the restore's lock")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr + sync_out)
        self.assertIn("holding the restored state", done.stdout)
        self.assertIn("Zrestoreda", self.remote_players())
        self.assertNotIn("Zold", self.remote_players())
        self.assertEqual({p.name for p in (self.current / "player").iterdir() if p.is_file()},
                         self.remote_players())


class RestoreVerifyTests(unittest.TestCase):
    """deploy/toc-restore-verify (review, 2026-11-24): the bare-host restore
    enabled every unit with `|| true` and said the game was up regardless.
    Now the game and the backup units must be active and enabled."""

    SCRIPT = ROOT / "deploy" / "toc-restore-verify"

    def run_with(self, active: list[str], enabled: list[str], *args: str,
                 push_rc: int | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            bin_ = pathlib.Path(tmp)
            if push_rc is not None:
                # A git whose push answers as GitHub would: accepted, or
                # refused as a read-only key is. Everything else is real.
                real = shutil.which("git")
                (bin_ / "git").write_text(
                    "#!/bin/sh\n"
                    'for a in "$@"; do [ "$a" = push ] && { echo "$GIT_SSH_COMMAND" > '
                    f'{tmp}/ssh-used; [ {push_rc} = 0 ] || echo "ERROR: The key you are '
                    'authenticating with has been marked as read only." >&2; '
                    f'exit {push_rc}; }}; done\n'
                    f'exec {real} "$@"\n')
                (bin_ / "git").chmod(0o755)
            (bin_ / "systemctl").write_text(
                "#!/bin/sh\n"
                f'ACTIVE="{" ".join(active)}"; ENABLED="{" ".join(enabled)}"\n'
                'verb=$1; shift; [ "$1" = --quiet ] && shift\n'
                'case "$verb" in\n'
                '  is-active) case " $ACTIVE " in *" $1 "*) echo active; exit 0;; esac; echo failed; exit 3;;\n'
                '  is-enabled) case " $ENABLED " in *" $1 "*) echo enabled; exit 0;; esac; echo disabled; exit 1;;\n'
                'esac\n')
            (bin_ / "systemctl").chmod(0o755)
            return subprocess.run(["sh", str(self.SCRIPT), *args],
                                  env=dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}",
                                           TOC_RESTORE_VERIFY_WAIT="1"),
                                  capture_output=True, text=True, timeout=30)

    REQUIRED = ["toc-game.service", "toc-state-sync.timer"]

    def test_all_running_and_enabled_passes(self) -> None:
        done = self.run_with(self.REQUIRED, self.REQUIRED, *self.REQUIRED, "--", "toc-web.service")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("WARN: toc-web.service is not running", done.stderr, "wanted is only a warning")

    def test_a_required_unit_down_fails(self) -> None:
        done = self.run_with(["toc-game.service"], self.REQUIRED, *self.REQUIRED)
        self.assertEqual(done.returncode, 1)
        self.assertIn("NOT RUNNING toc-state-sync.timer", done.stderr)

    def test_running_but_not_enabled_fails_unless_active_only(self) -> None:
        done = self.run_with(self.REQUIRED, ["toc-game.service"], *self.REQUIRED)
        self.assertEqual(done.returncode, 1)
        self.assertIn("NOT ENABLED toc-state-sync.timer", done.stderr)
        done = self.run_with(self.REQUIRED, [], "--active-only", *self.REQUIRED)
        self.assertEqual(done.returncode, 0, done.stderr)

    # --- remote backups, judged apart (review, 2026-11-24, third) ---------

    def test_a_missing_deploy_key_is_a_running_game_without_backups(self) -> None:
        """A fresh host has no deploy key: the sync timer runs and every sync
        fails. That used to verify as success."""
        done = self.run_with(self.REQUIRED, self.REQUIRED, "--backup-key", "/nonexistent/key",
                             "--backup-remote", "git@example.invalid:x.git", *self.REQUIRED)
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("GAME: running", done.stdout)
        self.assertRegex(done.stderr, r"REMOTE BACKUPS: NOT VERIFIED -- no state-sync deploy key "
                                      r"\S+ can read at /nonexistent/key")

    def test_a_key_that_can_push_verifies_backups(self) -> None:
        with tempfile.NamedTemporaryFile() as key:
            done = self.run_with(self.REQUIRED, self.REQUIRED, "--backup-key", key.name,
                                 "--backup-remote", "git@example.invalid:x.git", *self.REQUIRED,
                                 push_rc=0)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("REMOTE BACKUPS: push access verified", done.stdout)
        self.assertIn("no completed sync was checked", done.stdout)

    def test_a_read_only_key_is_not_verified(self) -> None:
        with tempfile.NamedTemporaryFile() as key:
            done = self.run_with(self.REQUIRED, self.REQUIRED, "--backup-key", key.name,
                                 "--backup-remote", "git@example.invalid:x.git", *self.REQUIRED,
                                 push_rc=1)
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("marked as read only", done.stderr)

    def test_run_as_root_it_asks_as_the_service_user(self) -> None:
        """Review, 2026-11-24 (fourth): the probe ran as the restore, root,
        and toc-state-sync.service runs as toc with HOME=/srv/toc. A key
        that works for root and not for toc passed. Run as root, it now
        reads the key and pushes through runuser as toc, with that HOME."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.NamedTemporaryFile() as key:
            bin_ = pathlib.Path(tmp)
            calls = bin_ / "runuser.calls"
            # Root, a toc user, and a runuser that runs the rest as "toc".
            (bin_ / "id").write_text('#!/bin/sh\ncase "$1" in -u) [ -n "$2" ] && exit 0; echo 0;; '
                                     '-un) echo root;; esac\n')
            (bin_ / "runuser").write_text(f'#!/bin/sh\necho "$*" >> {calls}\nshift 3\n'
                                          'SIMULATED_USER=toc exec "$@"\n')
            real_git = shutil.which("git")
            # GitHub takes the key from root, not from toc (no known_hosts,
            # say, or a key only root can read).
            (bin_ / "git").write_text(
                '#!/bin/sh\nfor a in "$@"; do if [ "$a" = push ]; then\n'
                '  [ "$SIMULATED_USER" = toc ] && { echo "Host key verification failed." >&2; exit 128; }\n'
                '  exit 0; fi; done\n'
                f'exec {real_git} "$@"\n')
            (bin_ / "systemctl").write_text("#!/bin/sh\nexit 0\n")
            for f in bin_.iterdir():
                f.chmod(0o755)
            done = subprocess.run(
                ["sh", str(self.SCRIPT), "--backup-key", key.name, "--backup-remote",
                 "git@example.invalid:x.git", "--home", "/srv/toc", "toc-game.service"],
                env=dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}", TOC_RESTORE_VERIFY_WAIT="1"),
                capture_output=True, text=True, timeout=30)
            ran = calls.read_text() if calls.exists() else ""
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("could not push to git@example.invalid:x.git as toc", done.stderr)
        self.assertIn("Host key verification failed", done.stderr)
        self.assertIn("-u toc -- env HOME=/srv/toc", ran)

    def test_a_stale_receipt_is_not_a_sync_since(self) -> None:
        with tempfile.TemporaryDirectory() as receipts, tempfile.NamedTemporaryFile() as key:
            pathlib.Path(receipts, "last-success").write_text("time=1000\ntime_utc=long ago\n")
            args = ("--backup-key", key.name, "--backup-remote", "git@example.invalid:x.git",
                    "--sync-receipts", receipts)
            stale = self.run_with(self.REQUIRED, self.REQUIRED, *args, "--since", "2000",
                                  *self.REQUIRED, push_rc=0)
            fresh = self.run_with(self.REQUIRED, self.REQUIRED, *args, "--since", "999",
                                  *self.REQUIRED, push_rc=0)
        self.assertEqual(stale.returncode, 3, stale.stdout + stale.stderr)
        self.assertIn("no state sync has reached GitHub since the restore began", stale.stderr)
        self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)
        self.assertIn("a state sync reached GitHub at long ago", fresh.stdout)

    def test_a_stopped_game_is_still_the_first_failure(self) -> None:
        done = self.run_with(["toc-state-sync.timer"], self.REQUIRED, "--backup-key",
                             "/nonexistent/key", *self.REQUIRED)
        self.assertEqual(done.returncode, 1)
        self.assertIn("GAME: NOT VERIFIED", done.stderr)

    def test_the_restore_says_which_it_is(self) -> None:
        source = (ROOT / "deploy" / "toc-restore").read_text()
        self.assertIn('--backup-key "${GIT_SSH_KEY:-$TOC_PREFIX/.ssh/id_ed25519_state_sync}"', source)
        self.assertIn("GAME RUNNING, BACKUPS NOT VERIFIED", source)
        tail = source.split('if [ "$verified" = 3 ]; then', 1)[1]
        self.assertLess(tail.index("exit 6"), tail.index('say "done'))

    def test_the_bare_host_restore_uses_it_and_ignores_no_failure(self) -> None:
        source = (ROOT / "deploy" / "toc-restore").read_text()
        services = source.split('say "wiring up the services"', 1)[1]
        self.assertNotRegex(services, r"enable --now[^\n]*\|\| true",
                            "an enable failure is never ignored")
        self.assertIn("verify_all toc-game.service toc-state-sync.timer toc-state-sync.path", services)
        self.assertIn("exit 4", services)
        self.assertLess(services.index("sync_once"), services.index("verify_all toc-game.service"))
        self.assertLess(services.index("verify_all"), services.index('say "done -- game is up'))


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
