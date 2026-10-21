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


if __name__ == "__main__":
    unittest.main()
