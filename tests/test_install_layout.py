"""The installers' layout: code in the checkout, everything the game
writes in the state folder, and updates that keep the latter.

Before 2026-10-21 a Docker install kept the live world inside the
container -- notes, bug reports, max-load counts, the ban list, builders'
areas -- and `toc.sh update` recreated the container, losing all of it.
It also bind-mounted the checkout's player/, gods/ and heroes/, which git
tracks, so the first character saved made `update` refuse for good. And
a `docker stop` reached only the entrypoint shell, which as PID 1 ignored
it, so Docker killed the game ten seconds later without a save.

These tests run the real scripts on synthetic trees: the shared world
sync (scripts/toc_sync_area.sh, whose rules must stay toc-deploy's), the
first-run move of an old installation's data, PROMOTE, the code-change
guard, and the native runner's handling of a stop.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "toc_sync_area.sh"
RUNNER = ROOT / "scripts" / "toc_run_game.sh"
COMMON = ROOT / "scripts" / "toc_common.sh"
HAVE_TOOLS = all(shutil.which(t) for t in ("bash", "rsync", "git"))


def area_excludes_from_deploy() -> set[str]:
    """toc-deploy's excludes that concern area/, written as the sync
    script writes them (anchored at the area root)."""
    text = (ROOT / "deploy" / "windows-vm" / "toc-deploy").read_text()
    block = text[text.index('rsync -a --delete'):text.index('"$BUILD/" "$CURRENT/"')]
    return {"/" + p[len("area/"):] for p in re.findall(r"--exclude '([^']+)'", block)
            if p.startswith("area/")}


def runtime_txt(text: str) -> set[str]:
    m = re.search(r'runtime_txt="([^"]+)"', text)
    return set(m.group(1).split())


@unittest.skipUnless(HAVE_TOOLS, "needs bash, rsync and git")
class WorldSyncTests(unittest.TestCase):
    def test_the_rules_are_toc_deploys(self) -> None:
        sync = SYNC.read_text()
        ours = set(re.findall(r"--exclude '([^']+)'", sync))
        self.assertEqual(ours, area_excludes_from_deploy())
        deploy = (ROOT / "deploy" / "windows-vm" / "toc-deploy").read_text()
        self.assertEqual(runtime_txt(sync), runtime_txt(deploy))

    def tree(self) -> pathlib.Path:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        return tmp

    def test_an_update_keeps_what_the_game_wrote(self) -> None:
        tmp = self.tree()
        code, live = tmp / "code", tmp / "live"
        (code / "built").mkdir(parents=True)
        (code / "area.lst").write_text("help.are\n$\n")
        (code / "help.are").write_text("new help\n")
        (code / "social.txt").write_text("help text that is code\n")
        (code / "custom.are").write_text("git's workshop\n")
        (code / "built" / "fresh.are").write_text("from git\n")
        (code / "built" / "mine.are").write_text("git's older copy\n")
        (code / "notes.txt").write_text("a note committed by the state sync\n")
        (code / "shutdown.txt").write_text("stale\n")

        (live / "built").mkdir(parents=True)
        (live / "help.are").write_text("old help\n")
        (live / "retired.are").write_text("no longer in the code\n")
        (live / "notes.txt").write_text("the live board\n")
        (live / "maxload.txt").write_text("ML 3715 4 10\n")
        (live / "bugs.txt.20261021-000000").write_text("an archive\n")
        (live / "custom.are").write_text("rooms a builder saved\n")
        (live / "built" / "mine.are").write_text("the builder's newest\n")
        (live / "shutdown.txt").write_text("left by SHUTDOWN\n")

        subprocess.run(["sh", str(SYNC), str(code), str(live)], check=True)

        self.assertEqual((live / "help.are").read_text(), "new help\n")
        self.assertEqual((live / "social.txt").read_text(), "help text that is code\n")
        self.assertFalse((live / "retired.are").exists(), "code the checkout dropped goes")
        self.assertEqual((live / "notes.txt").read_text(), "the live board\n")
        self.assertEqual((live / "maxload.txt").read_text(), "ML 3715 4 10\n")
        self.assertTrue((live / "bugs.txt.20261021-000000").exists())
        self.assertEqual((live / "custom.are").read_text(), "rooms a builder saved\n")
        self.assertEqual((live / "built" / "mine.are").read_text(), "the builder's newest\n")
        self.assertEqual((live / "built" / "fresh.are").read_text(), "from git\n")
        self.assertFalse((live / "shutdown.txt").exists(), "a marker would stop the game starting")

    def test_a_new_world_is_seeded_but_gets_no_runtime_files(self) -> None:
        tmp = self.tree()
        code, live = tmp / "code", tmp / "live"
        code.mkdir()
        (code / "area.lst").write_text("$\n")
        (code / "custom.are").write_text("seed\n")
        (code / "ban.txt").write_text("somebody else's ban list\n")
        subprocess.run(["sh", str(SYNC), str(code), str(live)], check=True)
        self.assertEqual((live / "custom.are").read_text(), "seed\n")
        self.assertFalse((live / "ban.txt").exists())

    def test_it_refuses_a_directory_that_is_not_a_world(self) -> None:
        tmp = self.tree()
        (tmp / "live").mkdir()
        (tmp / "live" / "keep.are").write_text("x\n")
        result = subprocess.run(["sh", str(SYNC), str(tmp / "nothing"), str(tmp / "live")],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((tmp / "live" / "keep.are").exists(), "--delete never ran")


@unittest.skipUnless(HAVE_TOOLS, "needs bash, rsync and git")
class LauncherStateTests(unittest.TestCase):
    """toc_common.sh's functions, sourced into bash against a scratch
    checkout. Docker is never asked: TOC_MODE is native."""

    def checkout(self) -> pathlib.Path:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        repo = tmp / "toc"
        (repo / "scripts").mkdir(parents=True)
        shutil.copy(COMMON, repo / "scripts" / "toc_common.sh")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=repo, check=True)
        (repo / ".gitignore").write_text("/state/\n.env\n")
        (repo / "player").mkdir()
        (repo / "player" / "Tracked").write_text("Name Tracked~\nLevl 10\n#END\n")
        (repo / "src").mkdir()
        (repo / "src" / "game.c").write_text("int main(void) { return 0; }\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
        return repo

    def bash(self, repo: pathlib.Path, script: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, TOC_REPO_ROOT=str(repo))
        return subprocess.run(
            ["bash", "-c", f'source "{repo}/scripts/toc_common.sh"; toc_mode() {{ echo native; }}; {script}'],
            cwd=repo, env=env, capture_output=True, text=True)

    def test_a_new_install_starts_an_empty_world_with_a_private_env(self) -> None:
        repo = self.checkout()
        r = self.bash(repo, "toc_configure_instance local")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = (repo / ".env").read_text()
        self.assertRegex(env, r"(?m)^WEB_ADMIN_TOKEN=[0-9a-f]{64}$")
        self.assertIn("TOC_STATE=./state", env)
        self.assertEqual((repo / ".env").stat().st_mode & 0o777, 0o600)
        for d in ("area", "player", "gods", "heroes", "corpse", "log", "backups"):
            self.assertTrue((repo / "state" / d).is_dir(), d)
        self.assertEqual(list((repo / "state" / "player").iterdir()), [],
                         "the repository's characters are imported only on request")

        r = self.bash(repo, "toc_configure_instance preserve native 1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((repo / "state" / "player" / "Tracked").exists())

    def test_a_hand_made_env_is_a_new_install(self) -> None:
        repo = self.checkout()
        shutil.copy(ROOT / ".env.example", repo / ".env")
        r = self.bash(repo, "toc_configure_instance preserve")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list((repo / "state" / "player").iterdir()), [],
                         "the repository's characters were not imported")
        self.assertRegex((repo / ".env").read_text(), r"(?m)^WEB_ADMIN_TOKEN=[0-9a-f]{64}$")

    def test_an_old_install_moves_its_data_out_once(self) -> None:
        repo = self.checkout()
        (repo / ".env").write_text("MUD_PORT=9000\nWEB_ADMIN_TOKEN=abc\n")
        with (repo / "player" / "Tracked").open("a") as f:
            f.write("Played 1\n")
        (repo / "player" / "Newcomer").write_text("Name Newcomer~\nLevl 3\n#END\n")

        r = self.bash(repo, "toc_configure_instance preserve")
        self.assertEqual(r.returncode, 0, r.stderr)
        state = repo / "state"
        self.assertIn("Played 1", (state / "player" / "Tracked").read_text())
        self.assertTrue((state / "player" / "Newcomer").exists())
        self.assertTrue((state / ".migrated-from-checkout").exists())
        self.assertIn("WEB_ADMIN_TOKEN=abc", (repo / ".env").read_text(), "the token is kept")

        # Once: later saves in the state folder are never overwritten.
        (state / "player" / "Tracked").write_text("newer\n")
        self.bash(repo, "toc_configure_instance preserve")
        self.assertEqual((state / "player" / "Tracked").read_text(), "newer\n")

        # update's guard sees the old saves as data, not code ...
        r = self.bash(repo, "toc_code_changes")
        self.assertEqual(r.stdout.strip(), "")
        # ... and puts git's copies back so a pull can fast-forward.
        r = self.bash(repo, "toc_release_checkout_state")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Played 1", (repo / "player" / "Tracked").read_text())
        self.assertEqual((state / "player" / "Tracked").read_text(), "newer\n",
                         "the live copy is untouched")

    def test_code_changes_still_stop_an_update(self) -> None:
        repo = self.checkout()
        (repo / "src" / "game.c").write_text("int main(void) { return 1; }\n")
        r = self.bash(repo, "toc_code_changes")
        self.assertIn("src/game.c", r.stdout)

    def test_promote(self) -> None:
        repo = self.checkout()
        self.bash(repo, "toc_configure_instance local")
        pfile = repo / "state" / "player" / "Zowner"
        pfile.write_text("#PLAYER\nName Zowner~\nLevl 5\nRace human~\n#END\n")

        r = self.bash(repo, "toc_promote_file zOWNER")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Levl 70\n", pfile.read_text())
        self.assertNotIn("Levl 5", pfile.read_text())
        self.assertTrue(list((repo / "state" / "backups").glob("Zowner.before-promote-*")),
                        "a copy of the file as it was")
        self.assertEqual([p.name for p in (repo / "state" / "player").iterdir()], ["Zowner"],
                         "nothing beside the character files")

        for bad in ("../area", "Zow ner", "Nobody", ""):
            with self.subTest(name=bad):
                r = self.bash(repo, f"toc_promote_file '{bad}'")
                self.assertNotEqual(r.returncode, 0)
        r = self.bash(repo, "toc_promote_file Zowner 71")
        self.assertNotEqual(r.returncode, 0)


@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class NativeRunnerTests(unittest.TestCase):
    """scripts/toc_run_game.sh with a stand-in merc that records how it
    was asked to stop."""

    FAKE_MERC = """#!/bin/sh
trap 'echo saved > ../log/fake-saved; exit 0' TERM
echo started >> ../log/fake-starts
if [ -f ../exit-with-shutdown ]; then echo x > shutdown.txt; exit 0; fi
while :; do sleep 1; done
"""

    def state(self) -> pathlib.Path:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "area").mkdir()
        (tmp / "log").mkdir()
        merc = tmp / "merc"
        merc.write_text(self.FAKE_MERC)
        merc.chmod(0o755)
        return tmp

    def test_a_stop_saves_and_does_not_restart(self) -> None:
        state = self.state()
        proc = subprocess.Popen(["sh", str(RUNNER), str(state), "9999"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 10
        while not (state / "log" / "fake-starts").exists() and time.time() < deadline:
            time.sleep(0.2)
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(timeout=20), 0)
        self.assertEqual((state / "log" / "fake-saved").read_text(), "saved\n",
                         "the game was told to save, not killed")
        self.assertEqual((state / "log" / "fake-starts").read_text().count("started"), 1)
        self.assertIn("every player was saved", (state / "log" / "toc.log").read_text())

    def test_an_in_game_shutdown_ends_it(self) -> None:
        state = self.state()
        (state / "exit-with-shutdown").write_text("")
        result = subprocess.run(["sh", str(RUNNER), str(state), "9999"], timeout=20,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((state / "area" / "shutdown.txt").exists())

    def test_the_container_entrypoint_does_the_same(self) -> None:
        entry = (ROOT / "docker-entrypoint.sh").read_text()
        self.assertIn("trap on_signal TERM INT HUP", entry)
        self.assertIn('kill -TERM "$merc_pid"', entry)
        self.assertIn("toc-sync-area /app/dist/area /app/area", entry)
        # merc writes log/toc.log itself; its output into the same file
        # doubled every line.
        self.assertRegex(entry, r'merc "\$DEFAULT_PORT" >> "\$OUT" 2>&1 &')


@unittest.skipUnless((ROOT / "merc").exists(), "needs the game built (make)")
class BindAddressTests(unittest.TestCase):
    def test_a_bad_bind_address_is_refused_not_widened(self) -> None:
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(ROOT / "area", tmp / "area",
                        ignore=shutil.ignore_patterns("*.txt", "*.queue"))
        for d in ("log", "player", "gods", "heroes", "corpse", "backups"):
            (tmp / d).mkdir()
        env = dict(os.environ, TOC_BIND_ADDRESS="everywhere", TOC_SEASON="none")
        result = subprocess.run([str(ROOT / "merc"), "9998"], cwd=tmp / "area", env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TOC_BIND_ADDRESS 'everywhere' is not an IPv4 address", result.stderr)


if __name__ == "__main__":
    unittest.main()
