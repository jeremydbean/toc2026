"""Full PRESTORE: who is in the game is not who staff can see.

Audit 2026-10-21: the whole-file restore found its target with
get_char_world, which goes by sight, and every check -- self, rank, the
save and the disconnect -- sat inside a successful lookup. A wizinvis
target, one at the password prompt, or one simply offline read as "not
online": no rank check ran, and an online copy went on to save over the
restore. It now asks player_in_game, refuses a login in progress,
rank-checks an offline target from a loaded copy, and refuses a snapshot
that is not a whole player file before disturbing anybody. Snapshots are
written to .partial and renamed into place, so a crash mid-copy leaves
nothing PRESTORE offers.

Review 2026-10-21: the restore's own safety copies -- the forced
pre-restore snapshot, the online target's save, the STASH form's
milestone -- rotate the directory, and at the limit the oldest copy went
first: the one being restored, deleted before it was opened. The chosen
snapshot is pinned (player_snapshot_pin) until PRESTORE returns.

Snapshots here are the fixtures' own files with one line changed.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zrestore1"
TEMPLE = 4207
GOOD = "20260101_000000"
CUT = "20260102_000000"


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def level_of(mud, name: str) -> int:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return int(re.search(r"(?m)^Levl (\d+)$", text).group(1))


def snapshot(mud, name: str, level: int) -> None:
    """A whole snapshot at `level`, and one cut short."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    text = re.sub(r"(?m)^Levl \d+$", "Levl %d" % level, text)
    versions = mud.player_dir / "versions" / name
    versions.mkdir(parents=True, exist_ok=True)
    (versions / f"{name}.{GOOD}").write_text(text, encoding="latin-1")
    (versions / f"{name}.{CUT}").write_text(text[:len(text) // 2], encoding="latin-1")


VER_MAX = 30           # PLAYER_VER_MAX
MILESTONE_MAX = 20     # PLAYER_MILESTONE_MAX


def fill_rotation(mud, name: str, level: int, tag: str = "") -> str:
    """Top the rotation (untagged, or one tag's) up to its limit with old
    copies; the oldest is at `level`. Returns the oldest's stamp."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    text = re.sub(r"(?m)^Levl \d+$", "Levl %d" % level, text)
    versions = mud.player_dir / "versions" / name
    versions.mkdir(parents=True, exist_ok=True)
    suffix = "." + tag if tag else ""
    pattern = re.compile(r"^%s\.\d{8}_\d{6}%s$" % (name, re.escape(suffix)))
    have = [p for p in versions.iterdir() if pattern.match(p.name)]
    limit = MILESTONE_MAX if tag else VER_MAX
    stamps = ["2025%02d%02d_000000" % (1 + i // 28, 1 + i % 28) for i in range(limit - len(have))]
    for stamp in stamps:
        (versions / f"{name}.{stamp}{suffix}").write_text(text, encoding="latin-1")
    return stamps[0] + suffix


@unittest.skipIf(SKIP is not None, SKIP or "")
class PrestoreTests(unittest.TestCase):
    def test_presence_and_rank_do_not_depend_on_sight(self) -> None:
        with LiveMud() as mud:
            for name in ("Zarchon", "Zhigher", "Ztarget"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zarchon", Levl=66, Room=TEMPLE)
            patch_player_file(mud, "Zhigher", Levl=68, Room=TEMPLE)
            patch_player_file(mud, "Ztarget", Levl=30, Room=TEMPLE)
            snapshot(mud, "Zhigher", 20)
            snapshot(mud, "Ztarget", 25)

            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)

                # Offline and above the caller: refused, file untouched.
                self.assertIn("You failed.", run(staff, f"prestore zhigher {GOOD}"))
                self.assertEqual(level_of(mud, "Zhigher"), 68)

                # A snapshot cut short is refused before anything happens.
                self.assertIn("incomplete", run(staff, f"prestore ztarget {CUT}"))
                self.assertEqual(level_of(mud, "Ztarget"), 30)

                # A snapshot is written as .partial and renamed whole; a
                # leftover from a crash mid-copy is never offered.
                (mud.player_dir / "versions" / "Ztarget" / ".partial").write_text(
                    "#PLAYER\nLevl 1\n", encoding="latin-1")
                listing = run(staff, "prestore ztarget")
                self.assertNotIn("partial", listing)

                # A name that is not a name never reaches a path.
                self.assertIn("not a player's name", run(staff, "prestore ../area 1"))

                # Online and invisible to the caller: still found, still
                # refused on rank, and still connected.
                with mud.connect(timeout=120) as higher:
                    login(higher, "Zhigher", PASSWORD)
                    run(higher, "wizinvis 68", 1.0)
                    self.assertIn("You failed.", run(staff, f"prestore zhigher {GOOD}"))
                    self.assertEqual(level_of(mud, "Zhigher"), 68)
                    self.assertIn("You say", run(higher, "say still here"))

                # Permitted: the target is put out, and the restore is
                # what they log back into.
                with mud.connect(timeout=120) as target:
                    login(target, "Ztarget", PASSWORD)
                    target.drain(1.0)
                    said = run(staff, f"prestore ztarget {GOOD}", 2.5)
                    self.assertIn("was online and has been disconnected", said)
                    self.assertTrue(target.wait_closed())
                self.assertEqual(level_of(mud, "Ztarget"), 25)
                with mud.connect(timeout=120) as target:
                    login(target, "Ztarget", PASSWORD)
                    target.drain(1.0)
                    target.send("quit")
                    self.assertTrue(target.wait_closed())
                self.assertEqual(level_of(mud, "Ztarget"), 25)

    def test_the_oldest_snapshot_survives_its_own_restore(self) -> None:
        with LiveMud() as mud:
            for name in ("Zarchon", "Zoffline", "Zonline", "Zstasher"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zarchon", Levl=66, Room=TEMPLE)
            for name in ("Zoffline", "Zonline", "Zstasher"):
                patch_player_file(mud, name, Levl=30, Room=TEMPLE)
            offline = fill_rotation(mud, "Zoffline", 12)
            online = fill_rotation(mud, "Zonline", 14)
            stash = fill_rotation(mud, "Zstasher", 16, tag="stashrestore")

            def versions(name: str) -> list[str]:
                return sorted(p.name for p in (mud.player_dir / "versions" / name).iterdir())

            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)

                # Offline, at the limit, the oldest copy.
                said = run(staff, f"prestore zoffline {offline}", 2.5)
                self.assertIn("restored to", said)
                self.assertEqual(level_of(mud, "Zoffline"), 12)
                kept = versions("Zoffline")
                self.assertIn(f"Zoffline.{offline}", kept, "the restored copy is still there")
                levels = [int(re.search(r"(?m)^Levl (\d+)$",
                          (mud.player_dir / "versions" / "Zoffline" / v).read_text(
                              encoding="latin-1")).group(1)) for v in kept]
                self.assertIn(30, levels, "the pre-restore copy was taken")

                # Online: their save and the forced copy both rotate.
                with mud.connect(timeout=120) as target:
                    login(target, "Zonline", PASSWORD)
                    target.drain(1.0)
                    said = run(staff, f"prestore zonline {online}", 2.5)
                    self.assertIn("was online and has been disconnected", said)
                    self.assertTrue(target.wait_closed())
                self.assertEqual(level_of(mud, "Zonline"), 14)
                self.assertIn(f"Zonline.{online}", versions("Zonline"))

                # STASH, from the oldest of a full set of its own milestones.
                said = run(staff, f"prestore zstasher {stash} stash", 2.5)
                self.assertNotIn("cannot read", said)
                self.assertIn("stash", said)
                self.assertIn(f"Zstasher.{stash}", versions("Zstasher"))

                # Unpinned afterwards: the next restore's forced copy
                # rotates it out as usual, and pins its own choice.
                second = sorted(v for v in versions("Zoffline") if v != f"Zoffline.{offline}")[0]
                run(staff, f"prestore zoffline {second.split('.', 1)[1]}", 2.5)
                kept = versions("Zoffline")
                self.assertNotIn(f"Zoffline.{offline}", kept)
                self.assertIn(second, kept)


if __name__ == "__main__":
    unittest.main()
