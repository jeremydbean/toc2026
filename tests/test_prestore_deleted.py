"""A full PRESTORE can bring back a deleted character.

The copy that undoes a full restore is a copy of the current file, and a
deleted character has none: PRESTORE refused, so a deletion -- regretted,
or done by somebody else at the keyboard -- could not be undone (review,
2026-10-26). Absence is now a state of its own, proved by stat's ENOENT
and recorded in the receipt as what undoes the restore. The snapshot must
name the character, rank is checked from it, and the uid retired at the
deletion is put back -- unless the name has passed to another character
since. A file that is there but cannot be copied is refused as before,
never read as "deleted".
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zdeletepw1"
TEMPLE = 4207
DAGGER = 3701


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def give_dagger(mud: LiveMud, name: str) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    obj = "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % DAGGER
    path.write_text(text.replace("#END", obj + "#END", 1), encoding="latin-1")


def self_delete(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        login(client, name, PW)
        client.must("delete", "Type delete again")
        client.send(f"delete {PW}")
        if not client.wait_closed():
            raise AssertionError(f"{name} was not deleted")
    assert not (mud.player_dir / name).exists(), f"{name}'s file is still there"


def delete_snapshot(mud: LiveMud, name: str) -> str:
    found = sorted((mud.player_dir / "versions" / name).glob(f"{name}.*.delete"))
    assert found, f"no .delete snapshot of {name}"
    return found[-1].name.split(".")[1]          # the stamp


def uid_rows(mud: LiveMud, name: str) -> list:
    path = mud.player_dir / "recovery" / "ledger.tsv"
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [(r[3], r[4], r[9]) for r in rows if len(r) > 9 and r[2] == "uid" and r[5] == name]


@unittest.skipIf(SKIP is not None, SKIP or "")
class DeletedRestoreTests(unittest.TestCase):
    def test_a_deleted_character_comes_back_with_their_uid(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zdelstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zgoner", Levl=20, Room=TEMPLE)
            give_dagger(mud, "Zgoner")
            with mud.connect(timeout=120) as client:   # a uid, recorded
                login(client, "Zgoner", PW)
                client.send("quit")
                client.wait_closed()
            self_delete(mud, "Zgoner")
            stamp = delete_snapshot(mud, "Zgoner")
            before = uid_rows(mud, "Zgoner")

            with mud.connect(timeout=120) as staff:
                login(staff, "Zdelstaff", PW)
                said = staff.sync(f"prestore zgoner {stamp}")
                staff.send("quit")
                staff.wait_closed()
            after = uid_rows(mud, "Zgoner")
            ledger = (mud.player_dir / "recovery" / "ledger.tsv").read_text(encoding="latin-1")

            self.assertIn("Zgoner restored to", said, said)
            self.assertTrue((mud.player_dir / "Zgoner").is_file())
            # Retired at the deletion, put back as the same uid.
            self.assertEqual([r[0] for r in before], ["assign", "retire"], before)
            self.assertEqual(after[-1][0], "assign", after)
            self.assertEqual(after[-1][1], before[0][1], (before, after))
            self.assertIn("restored after deletion", after[-1][2])
            # Written before the uid is put back, so its uid column is "-".
            self.assertRegex(ledger, r"\tprestore\tcommitted\t-\tZgoner\tfull:\d+\t"
                                     r"full\tZdelstaff\t[^\n]*no file \(it was absent")

            with mud.connect(timeout=120) as back:
                login(back, "Zgoner", PW)
                self.assertIn("dagger", back.sync("inventory"))
                back.send("quit")
                back.wait_closed()
            self.assertEqual(uid_rows(mud, "Zgoner")[-1], after[-1])   # no new uid

    def test_an_unreadable_or_reused_name_or_higher_rank_is_refused(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zdelangel", Levl=65, Room=TEMPLE)
            for name in ("Zsquat", "Zreuse", "Zhighgod"):
                make(mud, name, Levl=66 if name == "Zhighgod" else 20, Room=TEMPLE)
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
                self_delete(mud, name)

            # A directory where the file was: it exists, nothing can copy it.
            (mud.player_dir / "Zsquat").mkdir()
            # The name taken by another character since, whose file is lost.
            make(mud, "Zreuse", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zreuse", PW)
                client.send("quit")
                client.wait_closed()
            (mud.player_dir / "Zreuse").unlink()

            with mud.connect(timeout=120) as staff:
                login(staff, "Zdelangel", PW)
                squat = staff.sync("prestore zsquat %s" % delete_snapshot(mud, "Zsquat"))
                reuse = staff.sync("prestore zreuse %s" % delete_snapshot(mud, "Zreuse"))
                high = staff.sync("prestore zhighgod %s" % delete_snapshot(mud, "Zhighgod"))
                staff.send("quit")
                staff.wait_closed()

            self.assertIn("Nothing was changed", squat, squat)
            self.assertTrue((mud.player_dir / "Zsquat").is_dir())
            self.assertIn("belongs to", reuse, reuse)
            self.assertIn("another character", reuse, reuse)
            self.assertFalse((mud.player_dir / "Zreuse").exists())
            self.assertIn("You failed", high, high)
            self.assertFalse((mud.player_dir / "Zhighgod").exists())


if __name__ == "__main__":
    unittest.main()
