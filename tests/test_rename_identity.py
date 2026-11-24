"""A rename moves a character's name, and everything keyed by the name goes
with it (review of 2b6b5826d, 2026-11-23).

RENAME used to leave three things on the old name. Notes are addressed by
name, so a private note to the renamed player vanished from their board and
a brand new character made under the old name -- another account, another
password -- read it. IGNORE lists hold names, so a player ignored before
the rename was heard after it. And a BUG/TYPO/IDEA reply written for the
old name was skipped, or would have gone to whoever took the name next.

src/renames.c keeps every rename on the disk (player/recovery/renames.tsv)
before the old file goes. An old name is then never anybody else's: the
name prompt leads it to the renamed character, whose password it asks;
notes, IGNORE lists and replies follow the record at the rename, at boot
and at each load. A rename whose record cannot be written is undone.

Synthetic Z characters in disposable worlds only.
"""
from __future__ import annotations

import datetime
import gzip
import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zrenamepass1"
OTHER_PW = "Zotherpass9"
TEMPLE = 4207


def make(mud: LiveMud, name: str, password: str = PW, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, password)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    fields.setdefault("Room", TEMPLE)
    patch_player_file(mud, name, **fields)


def note_to(sender, recipients: str, subject: str, line: str) -> None:
    sender.must(f"note to {recipients}", "")
    sender.must(f"note subject {subject}", "")
    sender.must(f"note + {line}", "")
    sender.must("note send", "Note sent")


def note_lines(mud: LiveMud) -> list[tuple[str, str, str]]:
    """(sender, to, subject) of every note on the test world's board."""
    path = mud.root / "area" / "notes.txt"
    if not path.exists():
        return []
    text = path.read_text(encoding="latin-1")
    rows = []
    for block in text.split("Sender  ")[1:]:
        sender = block.split("~", 1)[0]
        to = re.search(r"^To      (.*)~$", block, re.M)
        subject = re.search(r"^Subject (.*)~$", block, re.M)
        rows.append((sender, to.group(1) if to else "", subject.group(1) if subject else ""))
    return rows


def renames(mud: LiveMud) -> str:
    path = mud.player_dir / "recovery" / "renames.tsv"
    return path.read_text(encoding="latin-1") if path.exists() else ""


def name_prompt(mud: LiveMud, name: str) -> str:
    """What the game says to a fresh connection typing `name`."""
    with mud.connect(timeout=60) as client:
        client.expect("by what name", "name:")
        client.buffer = ""
        client.send(name)
        said = client.expect("password", "did i get that right", "not available",
                             "try another", timeout=30)
        client.send("")
        return said.lower()


@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameNotesTests(unittest.TestCase):
    def test_private_notes_follow_the_rename_and_the_old_name_is_not_free(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcheckstaff", Levl=70)
            make(mud, "Zcheckold", Levl=20)
            stale = mud.player_dir / "Zcheckold"
            before_rename = stale.read_bytes()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as old:
                login(staff, "Zcheckstaff", PW)
                login(old, "Zcheckold", PW)
                staff.sync("scroll 0")
                old.sync("scroll 0")
                note_to(staff, "Zcheckold", "Zprivate subject", "Zprivate words")
                note_to(old, "Zcheckstaff", "Zsent before", "Zmine")
                self.assertIn("Zprivate subject", old.must("note list", "Zprivate", "1"))
                staff.must("rename zcheckold zchecknew", "renamed")
                # The rightful player, still connected, keeps their mail.
                listed = old.sync("note list")
                self.assertIn("Zprivate subject", listed)
                self.assertIn("Zsent before", listed, "a note they sent is still theirs")
                old.send("quit")
                old.wait_closed()
            board = note_lines(mud)
            self.assertIn(("Zcheckstaff", "Zchecknew", "Zprivate subject"), board)
            self.assertIn(("Zchecknew", "Zcheckstaff", "Zsent before"), board)
            self.assertNotIn("Zcheckold", " ".join(" ".join(row) for row in board))
            self.assertRegex(renames(mud), r"^\d+\tZcheckold\tZchecknew\n$")

            # A different account typing the old name meets the renamed
            # character's password, never the new-character questions --
            # and a wrong password gets nobody in.
            said = name_prompt(mud, "Zcheckold")
            self.assertIn("password", said)
            self.assertNotIn("did i get that right", said)
            with mud.connect(timeout=60) as other:
                other.expect("by what name", "name:")
                other.send("Zcheckold")
                other.expect("password")
                other.send(OTHER_PW)
                other.expect("wrong password", timeout=30)
            self.assertFalse((mud.player_dir / "Zcheckold").exists(), "no new Zcheckold")

            # A stale copy under the old name -- a .gz sidecar from a backup
            # -- is never what the old name loads.
            with gzip.open(mud.player_dir / "Zcheckold.gz", "wb") as fp:
                fp.write(before_rename)

            # The rightful player returns by the old name and their password
            # and is the renamed character, with the note.
            with mud.connect(timeout=120) as back:
                login(back, "Zcheckold", PW)
                back.sync("scroll 0")
                who = back.sync("score")
                self.assertIn("Zchecknew", who)
                self.assertIn("Zprivate subject", back.sync("note list"))
                back.send("quit")
                back.wait_closed()

            # And after a reboot, the same.
            mud.restart()
            self.assertIn("password", name_prompt(mud, "Zcheckold"))
            with mud.connect(timeout=120) as again:
                login(again, "Zchecknew", PW)
                self.assertIn("Zprivate subject", again.sync("note list"))
                again.send("quit")
                again.wait_closed()

    def test_a_note_written_to_the_old_name_reaches_the_renamed_player(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcheckstaff", Levl=70)
            make(mud, "Zcheckold", Levl=20)
            make(mud, "Zcheckpal", Levl=20)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as old:
                login(staff, "Zcheckstaff", PW)
                login(old, "Zcheckold", PW)
                staff.must("rename zcheckold zchecknew", "renamed")
                old.send("quit")
                old.wait_closed()
                # Somebody who knew the old name writes to it after the rename.
                with mud.connect(timeout=120) as pal:
                    login(pal, "Zcheckpal", PW)
                    pal.sync("scroll 0")
                    note_to(pal, "Zcheckold", "Zlate letter", "Zlate words")
                    pal.send("quit")
                    pal.wait_closed()
                staff.send("quit")
                staff.wait_closed()
            self.assertIn(("Zcheckpal", "Zchecknew", "Zlate letter"), note_lines(mud))


@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameIgnoreTests(unittest.TestCase):
    def test_ignore_follows_the_rename_online_offline_and_after_reload(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcheckstaff", Levl=70)
            make(mud, "Zcheckold", Levl=20)
            make(mud, "Zcheckear", Levl=20)      # online at the rename
            make(mud, "Zcheckaway", Levl=20)     # offline at the rename
            with mud.connect(timeout=120) as away:
                login(away, "Zcheckaway", PW)
                away.must("ignore zcheckold", "ignoring Zcheckold")
                away.send("quit")
                away.wait_closed()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as old, \
                    mud.connect(timeout=120) as ear:
                login(staff, "Zcheckstaff", PW)
                login(old, "Zcheckold", PW)
                login(ear, "Zcheckear", PW)
                ear.must("ignore zcheckold", "ignoring Zcheckold")
                self.assertIn("ignoring you", old.sync("tell zcheckear zbefore").lower())
                staff.must("rename zcheckold zchecknew", "renamed")
                told = old.sync("tell zcheckear zafter")
                self.assertIn("ignoring you", told.lower(), "blocked after the rename")
                self.assertIn("Zchecknew", ear.sync("ignore"))
                ear.send("quit")
                ear.wait_closed()
                # Logged out and back in: the list on disk still blocks.
                with mud.connect(timeout=120) as ear2, mud.connect(timeout=120) as away:
                    login(ear2, "Zcheckear", PW)
                    login(away, "Zcheckaway", PW)
                    self.assertIn("ignoring you", old.sync("tell zcheckear zreload").lower())
                    self.assertIn("ignoring you", old.sync("tell zcheckaway zoffline").lower())
                    self.assertIn("Zchecknew", away.sync("ignore"))
                    self.assertNotIn("zreload", ear2.sync("time"))
                    # Staff are always heard, rename or not.
                    staff.must("tell zcheckear zstaffword", "")
                    self.assertIn("zstaffword", ear2.sync("time"))
                    for client in (ear2, away):
                        client.send("quit")
                        client.wait_closed()
                for client in (old, staff):
                    client.send("quit")
                    client.wait_closed()
            # A reboot reads the saved lists again: still the renamed player.
            mud.restart()
            with mud.connect(timeout=120) as old, mud.connect(timeout=120) as ear:
                login(old, "Zchecknew", PW)
                login(ear, "Zcheckear", PW)
                self.assertIn("ignoring you", old.sync("tell zcheckear zreboot").lower())
                for client in (old, ear):
                    client.send("quit")
                    client.wait_closed()
            saved = (mud.player_dir / "Zcheckaway").read_text(encoding="latin-1")
            self.assertRegex(saved, r"(?m)^Ignore .*Zchecknew.*~$")


@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameBugReplyTests(unittest.TestCase):
    def test_a_reply_queued_before_the_rename_reaches_the_new_name_once(self) -> None:
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        with LiveMud() as mud:
            replies = mud.root / "area" / "bug_replies.dat"
            make(mud, "Zcheckstaff", Levl=70)
            make(mud, "Zrepold", Levl=20)
            replies.write_text(f"@ zrepone {today} Zrepold\nZfirst answer.\n", encoding="latin-1")
            mud.restart()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as old:
                login(staff, "Zcheckstaff", PW)
                login(old, "Zrepold", PW)
                staff.must("rename zrepold zrepnew", "renamed")
                for client in (old, staff):
                    client.send("quit")
                    client.wait_closed()
            # A reply written for the old name before the rename is known,
            # booted after it -- twice.
            replies.write_text(f"@ zrepone {today} Zrepold\nZfirst answer.\n\n"
                               f"@ zreptwo {today} Zrepold\nZsecond answer.\n",
                               encoding="latin-1")
            mud.restart()
            mud.restart()
            board = note_lines(mud)
            with mud.connect(timeout=120) as new:
                login(new, "Zrepnew", PW)
                listed = new.sync("note list")
                new.send("quit")
                new.wait_closed()
        subjects = [row for row in board if row[0] == "Immortals"]
        self.assertEqual(sorted(subjects),
                         [("Immortals", "Zrepnew", "Re: your report [zrepone]"),
                          ("Immortals", "Zrepnew", "Re: your report [zreptwo]")], board)
        self.assertIn("[zrepone]", listed)
        self.assertIn("[zreptwo]", listed)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameFailureTests(unittest.TestCase):
    def test_a_rename_whose_record_fails_changes_nothing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="toc-renamefault-") as tmp:
            fault = Path(tmp) / "fault"
            with LiveMud(extra_env={"TOC_FAULT_FILE": str(fault)}) as mud:
                make(mud, "Zcheckstaff", Levl=70)
                make(mud, "Zcheckold", Levl=20)
                make(mud, "Zcheckear", Levl=20)
                with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as old, \
                        mud.connect(timeout=120) as ear:
                    login(staff, "Zcheckstaff", PW)
                    login(old, "Zcheckold", PW)
                    login(ear, "Zcheckear", PW)
                    staff.sync("scroll 0")
                    old.sync("scroll 0")
                    ear.must("ignore zcheckold", "ignoring Zcheckold")
                    note_to(staff, "Zcheckold", "Zkept subject", "Zkept words")
                    fault.write_text("rename-record\n")
                    said = staff.must("rename zcheckold zchecknew", "could not be recorded")
                    self.assertNotIn("has been renamed", said)
                    self.assertIn("Zcheckold", old.sync("score"))
                    self.assertIn("Zkept subject", old.sync("note list"))
                    self.assertIn("ignoring you", old.sync("tell zcheckear zstill").lower())
                    self.assertIn("Zcheckold", ear.sync("ignore"))
                    for client in (old, ear, staff):
                        client.send("quit")
                        client.wait_closed()
                self.assertTrue((mud.player_dir / "Zcheckold").exists(), "the old file stands")
                self.assertFalse((mud.player_dir / "Zchecknew").exists(), "no new file left")
                self.assertEqual(renames(mud), "", "nothing recorded")
                self.assertIn(("Zcheckstaff", "Zcheckold", "Zkept subject"), note_lines(mud))
                # The old name is still that character's own, and the new
                # one is free for anybody.
                with mud.connect(timeout=120) as back:
                    login(back, "Zcheckold", PW)
                    self.assertIn("Zkept subject", back.sync("note list"))
                    back.send("quit")
                    back.wait_closed()
                self.assertIn("did i get that right", name_prompt(mud, "Zchecknew"))



@unittest.skipIf(SKIP is not None, SKIP or "")
class RenameDurabilityTests(unittest.TestCase):
    """A rename's record and its files must agree, across a restart, at every
    point a step can fail (review, 2026-11-23). rename_record() wrote and
    fsynced the line, then could still return false -- the directory sync of
    a new ledger failing, or the in-memory table failing to grow -- and the
    caller undid the rename and deleted the new file while the ledger kept
    "old -> new". After the next restart the old name then led to a file
    that was gone, and the character's own file answered to no name."""

    def consistent(self, mud: LiveMud, old: str, new: str) -> bool:
        recorded = f"\t{old}\t{new}" in renames(mud)
        has_old = (mud.player_dir / old).exists()
        has_new = (mud.player_dir / new).exists()
        if recorded:
            self.assertTrue(has_new and not has_old,
                            f"ledger says {old} -> {new}, but old={has_old} new={has_new}")
        else:
            self.assertTrue(has_old and not has_new,
                            f"ledger has no {old} -> {new}, but old={has_old} new={has_new}")
        return recorded

    def rename_failing_at(self, point: str, old: str, new: str, first: str | None = None):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="toc-renamedur-") as tmp:
            fault = Path(tmp) / "fault"
            with LiveMud(extra_env={"TOC_FAULT_FILE": str(fault)}) as mud:
                make(mud, "Zdurstaff", Levl=70)
                make(mud, old, Levl=20)
                if first:
                    make(mud, first, Levl=20)
                with mud.connect(timeout=120) as staff:
                    login(staff, "Zdurstaff", PW)
                    staff.sync("scroll 0")
                    if first:   # a ledger that already exists
                        with mud.connect(timeout=120) as earlier:
                            login(earlier, first, PW)
                            staff.must(f"rename {first.lower()} {first.lower()}x",
                                       "has been renamed")
                            earlier.send("quit")
                            earlier.wait_closed()
                    with mud.connect(timeout=120) as victim:
                        login(victim, old, PW)
                        victim.sync("scroll 0")
                        fault.write_text(point + "\n")
                        staff.sync(f"rename {old.lower()} {new.lower()}")
                        self.assertFalse(fault.exists(), f"the {point} fault never fired")
                        victim.send("quit")
                        victim.wait_closed()
                    staff.send("quit")
                    staff.wait_closed()
                recorded = self.consistent(mud, old, new)
                mud.restart()
                self.consistent(mud, old, new)
                # The character answers to the name the ledger gives it.
                with mud.connect(timeout=120) as back:
                    login(back, new if recorded else old, PW)
                    self.assertIn(new if recorded else old, back.sync("score"))
                    back.send("quit")
                    back.wait_closed()
                if recorded:
                    self.assertIn("password", name_prompt(mud, old),
                                  "the old name still leads to its character")

    def test_a_new_ledger_whose_directory_sync_fails(self) -> None:
        self.rename_failing_at("rename-sync-dir", "Zdurold", "Zdurnew")

    def test_a_table_that_cannot_grow_after_the_line_landed(self) -> None:
        self.rename_failing_at("rename-remember", "Zmemold", "Zmemnew", first="Zmemfirst")

    def test_a_ledger_that_could_not_be_read_is_read_again(self) -> None:
        """rename_load() marked the ledger loaded before opening it, so one
        failed read -- EACCES, EIO, too many open files -- left every retired
        name free for the rest of the boot."""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="toc-renameload-") as tmp:
            fault = Path(tmp) / "fault"
            with LiveMud(extra_env={"TOC_FAULT_FILE": str(fault)}) as mud:
                make(mud, "Zloadstaff", Levl=70)
                make(mud, "Zloadold", Levl=20)
                with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as victim:
                    login(staff, "Zloadstaff", PW)
                    login(victim, "Zloadold", PW)
                    staff.sync("scroll 0")
                    staff.must("rename zloadold zloadnew", "has been renamed")
                    for client in (victim, staff):
                        client.send("quit")
                        client.wait_closed()
                fault.write_text("rename-load\n")
                mud.restart()
                # The first read fails; a later one must find the ledger.
                said = [name_prompt(mud, "Zloadold") for _ in range(2)]
                self.assertFalse(fault.exists(), "the rename-load fault never fired")
                self.assertIn("password", said[-1],
                              f"the retired name was free after a failed read: {said}")

    def test_a_ledger_not_read_whole_gives_no_name_out(self) -> None:
        """rename_load() ignored rename_remember() failing, marked the ledger
        loaded with the line missing, and the retired name read as free for
        the boot; and a ledger that could not be read at all let the name
        prompt and character creation go ahead as if no name were retired
        (review, 2026-11-24). Now neither counts as known, and nothing that
        decides whose a name is goes ahead until it is: fault point
        rename-hold fails every record the table would hold."""
        with LiveMud(extra_env={"TOC_FAULT": "rename-hold"}) as mud:
            make(mud, "Zholdstaff", Levl=70)
            make(mud, "Zholdold", Levl=20)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as victim:
                login(staff, "Zholdstaff", PW)
                login(victim, "Zholdold", PW)
                staff.sync("scroll 0")
                staff.must("rename zholdold zholdnew", "has been renamed")
                for client in (victim, staff):
                    client.send("quit")
                    client.wait_closed()
            self.assertIn("\tZholdold\tZholdnew", renames(mud))
            mud.restart()
            # Every record now fails to be held: the ledger is never known.
            for name in ("Zholdold", "Zholdnew", "Zholdfresh"):
                said = name_prompt(mud, name)
                self.assertIn("not available", said,
                              f"{name} was let through with the ledger unknown: {said}")
                self.assertNotIn("did i get that right", said)
            self.assertFalse((mud.player_dir / "Zholdold").exists(),
                             "no character was made under the retired name")
            self.assertIn(b"could not be held", mud._output_path.read_bytes(),
                          "the refusal is logged with its reason")

if __name__ == "__main__":
    unittest.main()
