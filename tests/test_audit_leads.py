"""Leads from the 2026-10-22 audit, confirmed and fixed afterwards.

Each test here failed on the code before its fix.
"""
from __future__ import annotations

import os
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zlead1pass"
TEMPLE = 4207


def run(client, command: str, settle: float = 0.8) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, **fields)


def carried_count(inventory: str, what: str) -> int:
    total = 0
    for line in inventory.splitlines():
        if what in line:
            m = re.match(r"\s*\(\s*(\d+)\)", line)
            total += int(m.group(1)) if m else 1
    return total


@unittest.skipIf(SKIP is not None, SKIP or "")
class EnchantArmorTests(unittest.TestCase):
    def test_armour_that_fades_is_kept_damaged(self) -> None:
        """A failed ENCHANT ARMOR whose roll "destroyed" the piece took it
        out of the inventory and put it nowhere -- the player lost it and
        object_list kept an object with no owner. The message ("glows
        blue, then fades") and the damage flag say it was meant to stay.

        A vest with -9 AC of its own sets the failure chance at its 95%
        ceiling, so about a quarter of casts fade and a quarter explode;
        every vest is accounted for: carried, or exploded."""
        vest = "#O\nVnum 3703\nNest 0\nWear -1\nLev 1\nCond 100\nAffect -1 30 -1 -9 17 0 0\nEnd\n\n"
        with LiveMud() as mud:
            make(mud, "Zenchant", Levl=70, Room=TEMPLE)
            path = mud.player_dir / "Zenchant"
            text = path.read_text(encoding="latin-1")
            end = text.index("\nEnd\n")
            text = text[:end] + "\nSk 100 'enchant armor'" + text[end:]
            path.write_text(text.replace("#END", vest * 30 + "#END"), encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zenchant", PW)
                run(client, "scroll 0")
                run(client, "remove vest")
                before = carried_count(run(client, "inventory", 1.5), "sub issue vest")
                fades = explodes = 0
                for _ in range(40):
                    out = run(client, "cast 'enchant armor' vest")
                    fades += out.count("then fades")
                    explodes += out.count("explodes")
                    run(client, "restore self", 0.3)
                    if fades >= 2:
                        break
                after = carried_count(run(client, "inventory", 1.5), "sub issue vest")
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertGreaterEqual(fades, 1, "the 95% failure chance produced no fade")
        self.assertEqual(after, before - explodes,
                         f"{fades} faded and {explodes} exploded: a faded vest must stay carried")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetPwdTests(unittest.TestCase):
    def test_a_path_or_a_login_in_progress_is_refused(self) -> None:
        """RESETPWD put the typed name into a file path unchecked, and
        asked get_char_world whether the target was online -- which a
        character at the password prompt is not, so their login then
        saved the old password back over the reset."""
        with LiveMud() as mud:
            make(mud, "Zresetter", Levl=70, Room=TEMPLE)
            make(mud, "Zresettee", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zresetter", PW)
                path = run(staff, "resetpwd ../gods/zresetter Zfreshpw1", 1.5)
                with mud.connect(timeout=60) as waiting:
                    waiting.expect("name", timeout=30)
                    waiting.send("Zresettee")
                    waiting.expect("assword", timeout=30)
                    pending = run(staff, "resetpwd zresettee Zfreshpw1", 1.5)
                staff.send("quit")
                staff.wait_closed()
            with mud.connect(timeout=120) as client:
                login(client, "Zresettee", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "the refused reset changed the password")

        self.assertIn("No such character is saved", path)
        self.assertIn("logging in right now", pending)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashTimerTests(unittest.TestCase):
    def test_a_bag_holding_something_timed_is_refused(self) -> None:
        """STASH refused a timed object only at the top level, so one in
        a bag went in and rotted there unseen."""
        bag = "#O\nVnum 3032\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n"
        timed = "#O\nVnum 3032\nNest 1\nWear -1\nLev 1\nCond 100\nTime 40\nEnd\n\n"
        with LiveMud() as mud:
            make(mud, "Zstasher", Room=4208)
            path = mud.player_dir / "Zstasher"
            text = path.read_text(encoding="latin-1")
            path.write_text(text.replace("#END", bag + timed + "#END", 1), encoding="latin-1")
            with mud.connect(timeout=120) as client:
                login(client, "Zstasher", PW)
                one = run(client, "stash put bag", 1.2)
                every = run(client, "stash put all", 1.2)
                held = run(client, "inventory", 1.2)
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertIn("will not last long enough", one)
        self.assertIn("Nothing you are carrying can go in", every)
        self.assertIn("bag", held)


@unittest.skipIf(SKIP is not None, SKIP or "")
class OverlongLineTests(unittest.TestCase):
    def test_the_line_after_an_overlong_one_still_runs(self) -> None:
        """Cutting an overlong line short also cut the input buffer after
        it, so whatever arrived with it -- the next line typed, or the
        rest of an alias -- was silently lost."""
        with LiveMud() as mud:
            make(mud, "Zlongline", Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zlongline", PW)
                client.drain(0.5)
                mark = len(client.transcript)
                client.send_raw(b"say " + b"z" * 700 + b"\nsay zafterward\n")
                client.drain(3.0)
                out = client.transcript[mark:]
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertIn("the rest was not sent", out)
        self.assertIn("zafterward", out)


class LauncherParityTests(unittest.TestCase):
    def test_powershell_update_finishes_in_the_pulled_launcher(self) -> None:
        """toc.sh's update execs the newly pulled launcher to finish, so a
        fix to the launcher applies to the update that brings it; toc.ps1
        finished in the copy it had already loaded."""
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "toc.ps1").read_text(encoding="utf-8")
        update = text[text.index("    'update' {"):text.index("    '_finish-update' {")]
        pull = update.index("pull --ff-only")
        handoff = update.index("'toc.ps1') '_finish-update'")
        self.assertLess(pull, handoff)
        self.assertNotIn("Install-TocImage", update[pull:handoff])


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetPwdTrustTests(unittest.TestCase):
    def test_trust_in_the_file_outranks_the_level(self) -> None:
        """RESETPWD read the target's rank from "Levl" and stopped, so a
        level 10 character trusted to 69 ("Tru", or the older "Trust")
        could be reset by a level 66. get_trust on a loaded copy is the
        rule; with no trust it falls back to the level."""
        with LiveMud() as mud:
            make(mud, "Zresetboss", Levl=66, Room=TEMPLE)
            for name, key in (("Ztrusttru", "Tru"), ("Ztrusttrust", "Trust"), ("Ztrustnone", None)):
                make(mud, name, Levl=10, Room=TEMPLE)
                if key:
                    path = mud.player_dir / name
                    text = path.read_text(encoding="latin-1")
                    text = text.replace("\nLevl 10\n", "\nLevl 10\n%s  69\n" % key, 1)
                    path.write_text(text, encoding="latin-1")
            before = {n: (mud.player_dir / n).read_bytes() for n in ("Ztrusttru", "Ztrusttrust")}
            with mud.connect(timeout=120) as staff:
                login(staff, "Zresetboss", PW)
                tru = run(staff, "resetpwd ztrusttru Zfreshpw1", 2.0)
                trust = run(staff, "resetpwd ztrusttrust Zfreshpw1", 2.0)
                none = run(staff, "resetpwd ztrustnone Zfreshpw1", 2.0)
                staff.send("quit")
                staff.wait_closed()
            after = {n: (mud.player_dir / n).read_bytes() for n in before}

        self.assertIn("above your level", tru)
        self.assertIn("above your level", trust)
        self.assertEqual(before, after, "a refused reset changed the file")
        self.assertNotIn("above your level", none)
        self.assertNotIn("could not be read", none)


def full(path) -> None:
    """Make `path` a file every write to fails, as a full disk does."""
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to("/dev/full")


@unittest.skipIf(SKIP is not None, SKIP or "")
class RewriteInPlaceTests(unittest.TestCase):
    def test_a_failed_write_keeps_the_note_board_and_the_ban_list(self) -> None:
        """save_notes and ban_update truncated their file and wrote it
        again in place, so a crash or a full disk part way through lost
        the board or lifted every ban. They write aside and rename now;
        the temp is a symlink to /dev/full, so the write fails where a
        full disk fails it."""
        with LiveMud() as mud:
            make(mud, "Zboardkeep", Levl=70, Room=TEMPLE)
            area = mud.root / "area"
            with mud.connect(timeout=120) as staff:
                login(staff, "Zboardkeep", PW)
                for line in ("note to all", "note subject zfirstnote", "note + kept", "note send"):
                    run(staff, line)
                run(staff, "ban zfirstsite")
                notes, bans = area / "notes.txt", area / "ban.txt"
                kept = {notes: notes.read_bytes(), bans: bans.read_bytes()}
                full(area / "notes.txt.tmp")
                full(area / "ban.txt.tmp")
                for line in ("note to all", "note subject zsecondnote", "note + lost", "note send"):
                    run(staff, line)
                run(staff, "ban zsecondsite")
                staff.send("quit")
                staff.wait_closed()
            for path, before in kept.items():
                self.assertFalse(path.is_symlink(), path.name)
                self.assertEqual(path.read_bytes(), before, path.name)
            self.assertIn(b"zfirstnote", kept[notes])
            self.assertIn(b"zfirstsite", kept[bans])
            written = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("notes.txt is unchanged", written)
            self.assertIn("ban.txt is unchanged", written)


class StateSyncDeployLockTests(unittest.TestCase):
    def test_the_sync_copies_nothing_while_a_deploy_holds_the_lock(self) -> None:
        """toc-state-sync could copy the live tree while a deploy's
        rollback was extracting over it. It now takes the deploy lock,
        shared and non-blocking, for the copy, and skips the run if a
        deploy holds it. Runs the real script against a local bare repo."""
        import fcntl
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        if shutil.which("git") is None or shutil.which("flock") is None:
            self.skipTest("needs git and flock")
        script = Path(__file__).resolve().parent.parent / "deploy" / "windows-vm" / "toc-state-sync"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            (live / "player").mkdir(parents=True)
            (live / "player" / "Zsynced").write_text("#PLAYER\nName Zsynced~\nEnd\n")
            key = root / "key"
            key.write_text("not a key\n")
            lock = root / "deploy.lock"
            lock.write_text("")
            env = dict(os.environ, TOC_ROOT=str(live), STATE_REPO=str(root / "state"),
                       REMOTE=str(bare), BRANCH="main", GIT_SSH_KEY=str(key),
                       LOCK_FILE=str(root / "sync.lock"), TOC_DEPLOY_LOCK=str(lock))

            with open(lock, "w") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                busy = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
            free = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
            log = subprocess.run(["git", "--git-dir", str(bare), "log", "--format=%s", "main"],
                                 capture_output=True, text=True, check=True).stdout

        self.assertEqual(busy.returncode, 0, busy.stderr)
        self.assertIn("a deploy is running", busy.stdout)
        self.assertEqual(free.returncode, 0, free.stderr)
        self.assertIn("pushed", free.stdout)
        self.assertEqual(log.count("State sync:"), 1, log)


if __name__ == "__main__":
    unittest.main()
