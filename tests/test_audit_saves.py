"""Saves and loads that the 2026-10-22 audit found broken.

Finding 4 -- PRESTORE <player> <snapshot> STASH skipped the #END check the
whole-file restore makes, and read straight into the live stash: a
snapshot cut inside a number made fread_number exit the game, a stray
section restored the objects before it and reported success (so a retry
duplicated them), and an object that could not be made was dropped
without a word. The STASH form is now refused for an incomplete
snapshot, the section is dry-run before anything is read, and the
objects join the stash only if every one of them came back.

Finding 25 -- restored stash objects were never counted in the limited
item totals (maxload.txt). They are counted once, as a deposit is.

Finding 5 -- every writer that writes a temp file and renames it ignored
fclose's answer, so on a full disk an empty file replaced the good one:
maxload.txt (and the next boot then hung in read_maxload_file, which
looped on the empty word fread_word gives at end of file), the pkill
standings, the benchmark board, an area file under RSAVE (which said
"Wrote N rooms") and the built-area list.

Finding 6 -- RESETPWD did the same to a player file.

Finding 13 -- a saved Wear slot was restored unchecked: a retired ring
swapped for its replacement, or the Blue Ring raised to level 45, came
back worn by a level 30, and a pair of unique rings came back on both
hands.

The write failures are injected two ways. Everywhere: the temp file is a
symlink to /dev/full, so fopen succeeds and the write fails where a full
disk fails it, in fclose -- and the old code then renamed the symlink
over the real file. Where the machine allows it (root, as on the audit
host; GitHub runners are not): a real full disk, a small tmpfs in a
private mount namespace, which skips with its reason elsewhere.

Fixture names are Z-prefixed and alphabetic; nothing here touches a real
character file.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    ROOT,
    LiveMud,
    create_character,
    find_binary,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
PASSWORD = "Zaudsave1"
TEMPLE = 4207
YARD = 2419
LIMITED = 911          # limited in area/maxload.txt
PLAIN = 3020           # a dagger, not limited
GONE = 99999           # no such object, and no retired_objects row
BLUE_RING = 30551      # the Blue Ring of Hyrule, level 45, one may be worn
GANON_RING = 30578     # retired: comes back as the Blue Ring


def run(client, command: str, settle: float = 1.6) -> str:
    client.drain(0.2)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, *names: str) -> None:
    for name in names:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PASSWORD)
            client.drain(1.0)
            client.send("quit")
            assert client.wait_closed(), name


def obj(vnum: int, wear: int = -1, extra: str = "") -> str:
    return "#O\nVnum %d\nNest 0\n%sWear %d\nCond 100\nEnd\n\n" % (vnum, extra, wear)


def stash_vnums(mud: LiveMud, name: str) -> list[str]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    if "#STASH" not in text:
        return []
    return sorted(re.findall(r"(?m)^Vnum (\d+)$", text.split("#STASH", 1)[1]))


def maxload_count(mud: LiveMud, vnum: int) -> int:
    text = (mud.root / "area" / "maxload.txt").read_text(encoding="latin-1")
    match = re.search(r"(?m)^ML %d (\d+) \d+$" % vnum, text)
    assert match is not None, text
    return int(match.group(1))


def write_snapshots(mud: LiveMud, name: str, stashes: dict[str, str]) -> None:
    """Snapshots of `name` as they are now, each with a stash tail."""
    body = (mud.player_dir / name).read_text(encoding="latin-1").rsplit("#END", 1)[0]
    versions = mud.player_dir / "versions" / name
    versions.mkdir(parents=True, exist_ok=True)
    for stamp, tail in stashes.items():
        (versions / f"{name}.{stamp}").write_text(body + "#STASH\n" + tail,
                                                  encoding="latin-1")


def full_log(mud: LiveMud) -> str:
    """Everything the server wrote; server_output() is only the tail."""
    return mud._output_path.read_bytes().decode("latin-1", "replace")


def worn_slot(mud: LiveMud, name: str, vnum: int) -> int:
    """The Wear slot the saved object with this vnum is in."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    for block in text.split("#O\n")[1:]:
        block = block.split("\nEnd\n", 1)[0]
        if re.search(r"(?m)^Vnum %d$" % vnum, block):
            return int(re.search(r"(?m)^Wear (-?\d+)$", block).group(1))
    raise AssertionError(f"no object {vnum} saved for {name}")


def add_objects(mud: LiveMud, name: str, objects: list[str]) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace("#END", "".join(objects) + "#END", 1),
                    encoding="latin-1")


def to_dev_full(path: Path) -> None:
    """Make `path` a file every write to fails, as a full disk does."""
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to("/dev/full")


def assert_untouched(test: unittest.TestCase, path: Path, before: bytes) -> None:
    test.assertFalse(path.is_symlink(),
                     f"{path.name} was replaced by the failed temp file")
    test.assertEqual(path.read_bytes(), before, f"{path.name} changed")


def check_area(area_dir: Path) -> subprocess.CompletedProcess:
    binary = find_binary()
    assert binary is not None
    env = dict(os.environ, TOC_SEASON="none")
    try:
        return subprocess.run([str(binary), "--check-area"], cwd=area_dir,
                              capture_output=True, text=True, errors="replace",
                              timeout=120, env=env)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError("--check-area hung: " + str(exc)) from None


# ---------------------------------------------------------------------------
# Finding 4 and 25: PRESTORE ... STASH
# ---------------------------------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class StashRestoreTests(unittest.TestCase):
    def _world(self, mud: LiveMud, stashes: dict[str, str]) -> None:
        make(mud, "Zarchon", "Zvictim")
        patch_player_file(mud, "Zarchon", Levl=70, Room=TEMPLE)
        patch_player_file(mud, "Zvictim", Levl=30, Room=TEMPLE)
        write_snapshots(mud, "Zvictim", stashes)

    def test_a_snapshot_that_is_not_whole_is_refused_and_the_game_lives(self) -> None:
        stashes = {
            # Cut after a Vnum line: the object was dropped, "Restored 1".
            "20260101_000000": obj(PLAIN) + "#O\nVnum %d\n" % LIMITED,
            # Cut inside a number: no #END, and fread_number exited the game.
            "20260102_000000": obj(PLAIN) + "#O\nVnum %d\nNest " % LIMITED,
            # Whole file, but a number missing inside it: #END is there,
            # so only reading the section first can see it.
            "20260103_000000": obj(PLAIN) + "#O\nVnum %d\nNest \nEnd\n\n#END\n" % LIMITED,
            # Whole and well formed, holding an object the world lost.
            "20260104_000000": obj(PLAIN) + obj(GONE) + "#END\n",
        }
        with LiveMud() as mud:
            self._world(mud, stashes)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)
                for stamp, expect in (("20260101_000000", "incomplete"),
                                      ("20260102_000000", "incomplete"),
                                      ("20260103_000000", "Nothing was restored"),
                                      ("20260104_000000", "Nothing was restored")):
                    reply = run(staff, f"prestore zvictim {stamp} stash", 2.5)
                    self.assertIsNone(mud.proc.poll(),
                                      f"{stamp} took the game down:\n" + mud.server_output())
                    self.assertIn(expect, reply, reply)
                    self.assertNotIn("Restored", reply, reply)
                    # The "stashrestore" safety copy saves them as they
                    # are, so the file is rewritten -- with nothing added.
                    self.assertEqual(stash_vnums(mud, "Zvictim"), [], stamp)
                self.assertIn("could not be read back",
                              run(staff, "prestore zvictim 20260104_000000 stash", 2.5))
                self.assertIn("Zarchon", run(staff, "who"))

    def test_a_malformed_stash_adds_nothing_however_often_it_is_tried(self) -> None:
        bad = obj(PLAIN) + "#GARBAGE\n" + obj(LIMITED) + "#END\n"
        with LiveMud() as mud:
            self._world(mud, {"20260105_000000": bad})
            count = maxload_count(mud, LIMITED)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)
                for attempt in (1, 2):
                    reply = run(staff, "prestore zvictim 20260105_000000 stash", 2.5)
                    self.assertIn("Nothing was restored", reply, reply)
                    self.assertEqual(stash_vnums(mud, "Zvictim"), [], f"attempt {attempt}")
            self.assertEqual(maxload_count(mud, LIMITED), count)

    def test_a_whole_stash_is_restored_and_its_limited_items_counted(self) -> None:
        good = obj(LIMITED) + obj(PLAIN) + "#END\n"
        with LiveMud() as mud:
            self._world(mud, {"20260106_000000": good})
            count = maxload_count(mud, LIMITED)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)
                reply = run(staff, "prestore zvictim 20260106_000000 stash", 2.5)
                self.assertIn("Restored 2 objects", reply, reply)
            self.assertEqual(stash_vnums(mud, "Zvictim"), sorted([str(LIMITED), str(PLAIN)]))
            # Counted once for the restore: owned now, as a deposit is.
            self.assertEqual(maxload_count(mud, LIMITED), count + 1)

            # And the count is still right after the owner logs in and out.
            with mud.connect(timeout=120) as owner:
                login(owner, "Zvictim", PASSWORD)
                owner.send("quit")
                self.assertTrue(owner.wait_closed())
            self.assertEqual(maxload_count(mud, LIMITED), count + 1)


# ---------------------------------------------------------------------------
# Finding 13: worn objects at login
# ---------------------------------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class WornAtLoginTests(unittest.TestCase):
    def test_what_could_not_be_put_on_now_comes_back_carried(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zringlow", "Zringtwo", "Zslotty")
            # A level 30 wearing a Blue Ring saved at its old level 24: the
            # load raises it to 45, which WEAR would refuse.
            patch_player_file(mud, "Zringlow", Levl=30, Room=TEMPLE)
            add_objects(mud, "Zringlow", [obj(BLUE_RING, 1, "Lev 24\n")])
            # A level 50 with the shop's ring on one hand and Ganon's, which
            # comes back as the shop's, on the other: one may be worn.
            patch_player_file(mud, "Zringtwo", Levl=50, Room=TEMPLE)
            add_objects(mud, "Zringtwo", [obj(BLUE_RING, 1, "Lev 45\n"),
                                          obj(GANON_RING, 2, "Lev 54\n")])
            # A dagger saved on the head.
            patch_player_file(mud, "Zslotty", Levl=30, Room=TEMPLE)
            add_objects(mud, "Zslotty", [obj(PLAIN, 6)])

            with mud.connect(timeout=120) as client:
                login(client, "Zringlow", PASSWORD)
                run(client, "scroll 0", 1.0)
                self.assertNotIn("Blue Ring", run(client, "equipment"))
                self.assertIn("Blue Ring", run(client, "inventory"))
                self.assertIn("must be level 45", run(client, "wear ring"))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            with mud.connect(timeout=120) as client:
                login(client, "Zringtwo", PASSWORD)
                run(client, "scroll 0", 1.0)
                worn = run(client, "equipment")
                self.assertEqual(worn.count("Blue Ring"), 1, worn)
                self.assertIn("Blue Ring", run(client, "inventory"))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            with mud.connect(timeout=120) as client:
                login(client, "Zslotty", PASSWORD)
                run(client, "scroll 0", 1.0)
                worn = run(client, "equipment")
                self.assertNotIn("dagger", worn, worn)
                self.assertIn("dagger", run(client, "inventory"))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # Saved carried, and nothing else was taken off anybody: the
            # school kit each fixture was made with stays on.
            self.assertEqual(worn_slot(mud, "Zslotty", PLAIN), -1)
            self.assertEqual(worn_slot(mud, "Zringlow", BLUE_RING), -1)
            log = full_log(mud)
            taken = re.findall(r"taken off: ([a-z ]+)\.", log)
            self.assertEqual(sorted(taken), ["it is above their level",
                                             "it is not worn there",
                                             "only one may be worn"], log[-2000:])


# ---------------------------------------------------------------------------
# Finding 5 and 6: a failed write never replaces the good file
# ---------------------------------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class FailedWriteTests(unittest.TestCase):
    def test_maxload_rsave_and_resetpwd_keep_the_old_file(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zimp", "Zvictim")
            patch_player_file(mud, "Zimp", Levl=70, Room=YARD)
            patch_player_file(mud, "Zvictim", Levl=30, Room=TEMPLE)
            area = mud.root / "area"
            maxload = area / "maxload.txt"
            dummy = area / "dummy.are"
            victim = mud.player_dir / "Zvictim"

            with mud.connect(timeout=120) as staff:
                login(staff, "Zimp", PASSWORD)
                run(staff, "scroll 0", 1.0)

                before = maxload.read_bytes()
                to_dev_full(area / "maxload.txt.tmp")
                run(staff, f"maxloads set {LIMITED} 2101")
                assert_untouched(self, maxload, before)
                self.assertFalse((area / "maxload.txt.tmp").is_symlink())

                before = dummy.read_bytes()
                to_dev_full(area / "dummy.are.tmp")
                reply = run(staff, "rsave confirm dummy.are", 3.0)
                self.assertIn("Nothing was written", reply, reply)
                self.assertNotIn("Wrote", reply, reply)
                assert_untouched(self, dummy, before)

                before = victim.read_bytes()
                to_dev_full(mud.player_dir / "Zvictim.tmp")
                reply = run(staff, "resetpwd zvictim Newpass99", 2.0)
                self.assertIn("password was not changed", reply, reply)
                self.assertNotIn("has been reset", reply, reply)
                assert_untouched(self, victim, before)

            # The old password still lets them in.
            with mud.connect(timeout=120) as client:
                login(client, "Zvictim", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

    def test_the_built_list_and_asave_keep_the_old_file(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zimp")
            patch_player_file(mud, "Zimp", Levl=70, Room=TEMPLE)
            built = mud.root / "area" / "built"
            built.mkdir(exist_ok=True)
            listing = built / "built.lst"
            listing.write_text("$\n", encoding="latin-1")
            to_dev_full(built / "built.lst.tmp")

            with mud.connect(timeout=120) as staff:
                login(staff, "Zimp", PASSWORD)
                run(staff, "scroll 0", 1.0)
                made = run(staff, "anew 21000 21009 Zed Mossy Hollow", 2.0)
                self.assertIn("could not list it", made, made)
                assert_untouched(self, listing, b"$\n")

                files = list(built.glob("*.are"))
                self.assertEqual(len(files), 1, files)
                stub = files[0]
                before = stub.read_bytes()
                to_dev_full(built / (stub.name + ".tmp"))
                reply = run(staff, "asave Zed Mossy Hollow", 2.0)
                self.assertIn("Nothing was written", reply, reply)
                assert_untouched(self, stub, before)

    def test_the_pkill_standings_survive_a_failed_write(self) -> None:
        with LiveMud() as mud:
            pkill = mud.root / "area" / "pkilldata.txt"
            # The area pulse saves the standings, and the first one comes
            # with the first tick after a boot: break the temp, then boot.
            mud._stop()
            before = pkill.read_bytes()
            to_dev_full(mud.root / "area" / "pkilldata.txt.tmp")
            mud._launch()
            time.sleep(4.0)
            assert_untouched(self, pkill, before)
            self.assertIn("pkill file could not be written", full_log(mud))

    def test_the_benchmark_board_survives_a_failed_write(self) -> None:
        board_text = ("#standard 2\n"
                      "Zrecord 9000 80 30 0 1790000000 -1\n")
        with LiveMud() as mud:
            make(mud, "Zbencher")
            patch_player_file(mud, "Zbencher", Levl=30, Room=YARD,
                              Attr="18 18 18 18 18")
            board = mud.root / "area" / "dpsboard.txt"
            board.write_text(board_text, encoding="latin-1")
            to_dev_full(mud.root / "area" / "dpsboard.txt.tmp")
            with mud.connect(timeout=180) as client:
                login(client, "Zbencher", PASSWORD)
                run(client, "scroll 0", 1.0)
                client.send("kill dummy")
                # Twenty-five rounds and a bell.
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    client.drain(5.0)
                    if "The bell goes." in client.transcript:
                        break
                self.assertIn("The bell goes.", client.transcript,
                              client.transcript[-2000:])
                client.drain(2.0)
            assert_untouched(self, board, board_text.encode("latin-1"))
            self.assertIn("board was not written", full_log(mud))


# ---------------------------------------------------------------------------
# Finding 5: maxload.txt that a failed write left behind
# ---------------------------------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class MaxloadReaderTests(unittest.TestCase):
    def test_a_blank_or_cut_maxload_file_still_boots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="toc-maxload-") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "area", root / "area",
                            ignore=shutil.ignore_patterns(
                                "notes.txt", "bugs.txt", "typos.txt", "ideas.txt",
                                "bugs.txt.*", "typos.txt.*", "ideas.txt.*",
                                "dpsboard.txt"))
            for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
                (root / name).mkdir()
            maxload = root / "area" / "maxload.txt"
            for label, text in (("empty", ""),
                                ("no terminator", "ML 911 3 2100\n"),
                                ("cut inside a line", "ML 911 3 2100\nML 912 2\n$\n")):
                maxload.write_text(text, encoding="latin-1")
                result = check_area(root / "area")
                self.assertEqual(result.returncode, 0,
                                 f"{label}: " + (result.stdout + result.stderr)[-800:])
                self.assertIn("Validation OK", result.stdout + result.stderr, label)


# ---------------------------------------------------------------------------
# Finding 5 and 6 on a real full disk, where the machine allows a mount
# ---------------------------------------------------------------------------

# How to get a private mount namespace here, best first: as root; as an
# unprivileged user through a user namespace (unshare -r); or through
# passwordless sudo, which GitHub's runners have and which is the only one
# that works there -- they are not root, and Ubuntu 24.04 restricts
# unprivileged user namespaces. In CI this test must run, not skip: the
# deploy gate fails an unexplained skip.
_MOUNT_PREFIXES = (["unshare", "-m"], ["unshare", "-rm"], ["sudo", "-n", "unshare", "-m"])


def _mount_prefix() -> tuple[list[str] | None, str | None]:
    """A command prefix that runs `sh -c` in a private mount namespace able
    to mount a tmpfs, or None and why there is none."""
    if shutil.which("unshare") is None:
        return None, "unshare is not installed"
    errors = []
    with tempfile.TemporaryDirectory(prefix="toc-mnt-probe-") as mnt:
        for prefix in _MOUNT_PREFIXES:
            if shutil.which(prefix[0]) is None:
                continue
            probe = subprocess.run(
                prefix + ["sh", "-c", f'mount -t tmpfs -o size=1m tmpfs "{mnt}"'],
                capture_output=True, text=True, timeout=30)
            if probe.returncode == 0:
                return prefix, None
            errors.append(f"{' '.join(prefix)}: "
                          + (probe.stderr.strip() or "exit %d" % probe.returncode))
    return None, ("cannot mount a private tmpfs (needs root, user namespaces or "
                  "passwordless sudo): " + "; ".join(errors))


def _disk_full_child(out_path: str) -> None:
    """Run inside `unshare -m` with TMPDIR on a small tmpfs: fill it, then
    ask each writer to write, and report what became of the files."""
    results: dict[str, object] = {}
    with LiveMud() as mud:
        make(mud, "Zimp", "Zvictim")
        patch_player_file(mud, "Zimp", Levl=70, Room=YARD)
        patch_player_file(mud, "Zvictim", Levl=30, Room=TEMPLE)
        area = mud.root / "area"
        files = {"maxload": area / "maxload.txt", "dummy": area / "dummy.are",
                 "victim": mud.player_dir / "Zvictim"}
        before = {key: path.read_bytes() for key, path in files.items()}
        with mud.connect(timeout=120) as staff:
            login(staff, "Zimp", PASSWORD)
            run(staff, "scroll 0", 1.0)
            filler = mud.root / "filler"
            subprocess.run(["dd", "if=/dev/zero", f"of={filler}", "bs=64k"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results["maxload_reply"] = run(staff, f"maxloads set {LIMITED} 2101")
            results["rsave_reply"] = run(staff, "rsave confirm dummy.are", 3.0)
            results["resetpwd_reply"] = run(staff, "resetpwd zvictim Newpass99", 2.0)
            filler.unlink()
            staff.send("quit")
            staff.wait_closed()
        results["unchanged"] = {key: path.read_bytes() == before[key]
                                for key, path in files.items()}
        mud._stop()
        try:
            results["check_area_rc"] = check_area(area).returncode
        except AssertionError as exc:
            results["check_area_rc"] = str(exc)[:200]
    Path(out_path).write_text(json.dumps(results), encoding="utf-8")


@unittest.skipIf(SKIP is not None, SKIP or "")
class DiskFullTests(unittest.TestCase):
    def test_a_full_disk_leaves_every_old_file_in_place(self) -> None:
        prefix, reason = _mount_prefix()
        if prefix is None:
            self.skipTest(reason)
        with tempfile.TemporaryDirectory(prefix="toc-diskfull-") as work:
            mnt = Path(work) / "mnt"
            mnt.mkdir()
            out = Path(work) / "result.json"
            pythonpath = str(Path(__file__).resolve().parent) + (
                os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
            # The environment goes inside the script: sudo starts with a
            # clean one.
            server = os.environ.get("TOC_SERVER_BINARY", "")
            script = (f'mount -t tmpfs -o size=64m tmpfs "{mnt}" && '
                      f'cd "{ROOT}" && PYTHONPATH="{pythonpath}" TMPDIR="{mnt}" '
                      + (f'TOC_SERVER_BINARY="{server}" ' if server else "")
                      + f'exec "{sys.executable}" '
                      f'"{Path(__file__).resolve()}" --disk-full-child "{out}"')
            child = subprocess.run(prefix + ["sh", "-c", script],
                                   capture_output=True, text=True,
                                   cwd=str(ROOT), timeout=600)
            self.assertEqual(child.returncode, 0,
                             (child.stdout + child.stderr)[-3000:])
            results = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(results["unchanged"],
                         {"maxload": True, "dummy": True, "victim": True}, results)
        self.assertIn("Nothing was written", results["rsave_reply"])
        self.assertIn("password was not changed", results["resetpwd_reply"])
        self.assertEqual(results["check_area_rc"], 0, results)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--disk-full-child":
        _disk_full_child(sys.argv[2])
    else:
        unittest.main()
