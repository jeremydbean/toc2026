"""./toc.sh restore and .\\toc.ps1 restore (review, 2026-10-22).

Two faults in the restore the October 2026 installers brought:

* It swallowed a failed stop (`stop_game || true`) and went on renaming
  the live state directory under a game that might still be running and
  writing to it.
* It put the archived state at this installation's TOC_STATE and then
  replaced this .env with the archived one, whose TOC_STATE could name
  another directory -- or another machine's absolute path -- so the game
  started on a world that was not the one just restored.

The Bash tests run the real `restore_backup` and `stop_game` from toc.sh
with only process control stubbed; the PowerShell tests run the real
toc.ps1 against a stand-in `docker` on PATH. Synthetic characters only.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import socket
import subprocess
import tarfile
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

HARNESS = r"""
set -euo pipefail
REPO_ROOT="$FAKE_ROOT"
TOC_REPO_ROOT="$FAKE_ROOT"
source "$REAL_ROOT/scripts/toc_common.sh"
eval "$(sed -n '/^stop_game() {/,/^}/p; /^game_running() {/,/^}/p; /^restore_backup() {/,/^}/p' "$REAL_ROOT/toc.sh")"
mode="${MODE:-docker}"
toc_require_docker() { :; }
toc_start_docker() { :; }
toc_native_stop() { echo "STOP native" >> "$CALLS"; return "${STOP_RC:-0}"; }
toc_compose() { echo "COMPOSE $*" >> "$CALLS"; return "${STOP_RC:-0}"; }
game_running() { [ "${STILL_RUNNING:-0}" = 1 ]; }
start_game() {
    echo "START build=$1 state=$(toc_state_dir)" >> "$CALLS"
    ls "$(toc_state_dir)/player" >> "$CALLS" 2>&1 || echo "NO PLAYERS" >> "$CALLS"
}
restore_backup "$ARCHIVE"
"""


def write_env(path: pathlib.Path, state: str, token: str) -> None:
    path.write_text(f"TOC_MODE=docker\nTOC_STATE={state}\nMUD_PORT=9000\n"
                    f"WEB_ADMIN_TOKEN={token}\n", encoding="utf-8")


def make_archive(where: pathlib.Path, archived_state: str, character: str) -> pathlib.Path:
    """What toc_backup_archive writes: .env and the state folder by its name."""
    source = where / "source"
    source.mkdir()
    write_env(source / ".env", archived_state, "archivedtoken")
    folder = source / "statehome" / pathlib.PurePath(archived_state).name
    (folder / "player").mkdir(parents=True)
    (folder / "player" / character).write_text("Name " + character + "~\n", encoding="latin-1")
    archive = where / "toc-backup-20261022-120000.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source / ".env", arcname=".env")
        tar.add(folder, arcname=folder.name)
    return archive


class BashRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="toc-restore-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "checkout"
        self.root.mkdir()
        self.calls = self.tmp / "calls.log"

    def install(self, state: str) -> pathlib.Path:
        write_env(self.root / ".env", state, "livetoken")
        live = pathlib.Path(state) if os.path.isabs(state) else self.root / state.removeprefix("./")
        (live / "player").mkdir(parents=True)
        (live / "player" / "Zoriginal").write_text("Name Zoriginal~\n", encoding="latin-1")
        return live

    def restore(self, archive: pathlib.Path, **env: str) -> subprocess.CompletedProcess:
        run_env = dict(os.environ, FAKE_ROOT=str(self.root), REAL_ROOT=str(ROOT),
                       CALLS=str(self.calls), ARCHIVE=str(archive), **env)
        return subprocess.run(["bash", "-c", HARNESS], env=run_env, capture_output=True,
                              text=True, timeout=60)

    def calls_text(self) -> str:
        return self.calls.read_text() if self.calls.exists() else ""

    def assert_untouched(self, live: pathlib.Path, result) -> None:
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("nothing was restored", result.stderr)
        self.assertTrue((live / "player" / "Zoriginal").exists(), "the live data stays")
        self.assertEqual(list(self.root.glob("*.before-restore-*")), [])
        self.assertEqual(list(self.root.glob(".restore.*")), [], "the unpacked copy is cleared")
        self.assertIn("livetoken", (self.root / ".env").read_text())
        self.assertFalse((self.root / ".env.from-backup").exists())
        self.assertNotIn("START", self.calls_text(), "no game is started")

    def test_a_failed_stop_restores_nothing(self) -> None:
        live = self.install("./state")
        archive = make_archive(self.tmp, "./state", "Zrestored")
        self.assert_untouched(live, self.restore(archive, STOP_RC="1"))
        self.assertIn("COMPOSE stop game", self.calls_text())

    def test_a_game_still_running_after_the_stop_restores_nothing(self) -> None:
        # A partial stop: the command said yes, but part of the game is up.
        live = self.install("./state")
        archive = make_archive(self.tmp, "./state", "Zrestored")
        self.assert_untouched(live, self.restore(archive, STILL_RUNNING="1"))

    def test_the_data_lands_where_this_installation_looks(self) -> None:
        elsewhere = "/srv/another-machine/toc-state"
        for current, archived in (("./state", "./backup-state"),
                                  ("./custom-state", "./state"),
                                  ("./one", "./two"),
                                  ("./state", elsewhere),
                                  (str(self.tmp / "abs-state"), "./state")):
            with self.subTest(current=current, archived=archived):
                self.setUp()
                live = self.install(current)
                archive = make_archive(self.tmp, archived, "Zrestored")
                result = self.restore(archive)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls_text()
                self.assertIn(f"START build=0 state={live}\n", calls)
                self.assertIn("Zrestored", calls, "the game starts on the restored characters")
                self.assertNotIn("Zoriginal", calls)
                env = (self.root / ".env").read_text()
                self.assertIn(f"TOC_STATE={current}", env, "this installation's settings stay")
                self.assertIn("livetoken", env)
                kept = (self.root / ".env.from-backup").read_text()
                self.assertIn(f"TOC_STATE={archived}", kept, "the backup's settings are kept to read")
                self.assertEqual(oct((self.root / ".env.from-backup").stat().st_mode & 0o777), "0o600")
                aside = list(live.parent.glob(live.name + ".before-restore-*"))
                self.assertEqual(len(aside), 1)
                self.assertTrue((aside[0] / "player" / "Zoriginal").exists())
                self.assertFalse(pathlib.Path(elsewhere).exists())

    def test_a_native_restore_rebuilds_for_this_machine(self) -> None:
        live = self.install("./state")
        archive = make_archive(self.tmp, "./state", "Zrestored")
        result = self.restore(archive, MODE="native")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STOP native", self.calls_text())
        self.assertIn(f"START build=1 state={live}", self.calls_text())

    def test_not_a_backup_is_refused_before_the_stop(self) -> None:
        live = self.install("./state")
        bogus = self.tmp / "bogus.tar.gz"
        with tarfile.open(bogus, "w:gz") as tar:
            tar.add(live / "player", arcname="player")
        result = self.restore(bogus)
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not a Times of Chaos backup", result.stderr)
        self.assertEqual(self.calls_text(), "", "nothing is stopped for a file that is no backup")

    def test_stop_game_reports_a_failed_stop(self) -> None:
        # Under set -e a function called as a condition runs without it, so
        # stop_game used to return its closing echo's 0 after a failure.
        script = HARNESS.replace('restore_backup "$ARCHIVE"',
                                 'if stop_game; then echo SAID-STOPPED; else echo SAID-FAILED; fi')
        run_env = dict(os.environ, FAKE_ROOT=str(self.root), REAL_ROOT=str(ROOT),
                       CALLS=str(self.calls), ARCHIVE="", STOP_RC="3")
        self.install("./state")
        result = subprocess.run(["bash", "-c", script], env=run_env, capture_output=True,
                                text=True, timeout=60)
        self.assertIn("SAID-FAILED", result.stdout, result.stderr)


FAKE_DOCKER = """#!/usr/bin/env bash
echo "docker $*" >> "$CALLS"
case "$*" in
    info*|*"compose version"*|*"image inspect"*) exit 0 ;;
    *" stop game"*) exit "${STOP_RC:-0}" ;;
    *"ps --status running -q game"*) [ "${STILL_RUNNING:-0}" = 1 ] && echo abc123; exit 0 ;;
    *" up -d"*) touch "$CALLS.up"; exit 0 ;;
    *"ps -q game"*) [ -f "$CALLS.up" ] && echo abc123; exit 0 ;;
    inspect*) echo healthy; exit 0 ;;
    *) exit 0 ;;
esac
"""


@unittest.skipIf(shutil.which("pwsh") is None, "PowerShell (pwsh) is not installed")
class PowerShellRestoreTests(unittest.TestCase):
    """toc.ps1 against a stand-in docker: the stop, the running check and
    the start are what the launcher asks docker, so the real script runs."""

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="toc-ps-restore-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "checkout"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy(ROOT / "toc.ps1", self.root / "toc.ps1")
        shutil.copy(ROOT / "scripts" / "toc_common.ps1", self.root / "scripts" / "toc_common.ps1")
        shutil.copy(ROOT / "docker-compose.yml", self.root / "docker-compose.yml")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "docker").write_text(FAKE_DOCKER)
        (bin_dir / "docker").chmod(0o755)
        self.bin = bin_dir
        self.calls = self.tmp / "calls.log"
        # Something answering the game port, so the start's wait ends.
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.addCleanup(self.listener.close)
        self.port = self.listener.getsockname()[1]

    def install(self, state: str) -> pathlib.Path:
        (self.root / ".env").write_text(
            f"TOC_MODE=docker\nTOC_STATE={state}\nMUD_PORT={self.port}\n"
            f"WEB_ADMIN_PORT={self.port}\nWEB_ADMIN_TOKEN=livetoken\n", encoding="utf-8")
        live = self.root / state.removeprefix("./")
        for sub in ("player", "area", "gods", "heroes", "corpse", "log", "backups"):
            (live / sub).mkdir(parents=True, exist_ok=True)
        (live / "player" / "Zoriginal").write_text("Name Zoriginal~\n", encoding="latin-1")
        return live

    def restore(self, archive: pathlib.Path, **env: str) -> subprocess.CompletedProcess:
        run_env = dict(os.environ, CALLS=str(self.calls),
                       PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", **env)
        return subprocess.run(["pwsh", "-NoProfile", "-File", str(self.root / "toc.ps1"),
                               "restore", str(archive)],
                              env=run_env, capture_output=True, text=True, timeout=180)

    def test_a_failed_or_partial_stop_restores_nothing(self) -> None:
        for failure in ({"STOP_RC": "1"}, {"STILL_RUNNING": "1"}):
            with self.subTest(**failure):
                self.setUp()
                live = self.install("./state")
                archive = make_archive(self.tmp, "./state", "Zrestored")
                result = self.restore(archive, **failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("nothing was restored", result.stdout + result.stderr)
                self.assertTrue((live / "player" / "Zoriginal").exists())
                self.assertFalse((live / "player" / "Zrestored").exists())
                self.assertEqual(list(self.root.glob("*.before-restore-*")), [])
                self.assertEqual(list(self.root.glob(".restore.*")), [])
                self.assertFalse((self.root / ".env.from-backup").exists())
                self.assertNotIn(" up ", self.calls.read_text(), "no game is started")

    def test_the_data_lands_where_this_installation_looks(self) -> None:
        live = self.install("./custom-state")
        archive = make_archive(self.tmp, "./backup-state", "Zrestored")
        result = self.restore(archive)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((live / "player" / "Zrestored").exists())
        self.assertIn("TOC_STATE=./custom-state", (self.root / ".env").read_text())
        self.assertIn("TOC_STATE=./backup-state", (self.root / ".env.from-backup").read_text())
        self.assertFalse((self.root / "backup-state").exists())
        self.assertIn("up -d --no-build game", self.calls.read_text())


if __name__ == "__main__":
    unittest.main()
