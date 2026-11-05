"""DELETE stops unless its milestone holds the character as they are (review, 2026-11-04).

DELETE ignored player_snapshot_milestone's answer. With the save before
it failing, the "delete" milestone was a copy of the older file; QUIT then
saved the newer state, but its ordinary snapshot was throttled by the
milestone a moment before, and DELETE unlinked the file -- so nothing that
survived held what the character had picked up since the last save.

Now the milestone must land (the save before it included), the uid's
retirement must be recorded and the file must come away, in that order,
or nothing is deleted and the character is told. These tests save a
synthetic character, hand them a uniquely named dagger, fail the save
DELETE makes, and check that the character and the file are still there;
then delete for real and find the dagger in the surviving milestone.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zdelpass1"
STAFF, VICTIM = "Zdelstaff", "Zdeleter"
DAGGER = 3701
TOKEN = "zdelgem"
ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def snapshots_holding(mud: LiveMud, token: str) -> list[str]:
    vdir = mud.root / "player" / "versions" / VICTIM
    if not vdir.is_dir():
        return []
    return sorted(p.name for p in vdir.iterdir()
                  if p.is_file() and token in p.read_text(encoding="latin-1"))


def ledger(mud: LiveMud) -> str:
    path = mud.root / "player" / "recovery" / "ledger.tsv"
    return path.read_text(encoding="latin-1") if path.is_file() else ""


class DeleteSourceTests(unittest.TestCase):
    def test_every_step_is_checked_and_the_file_goes_last(self) -> None:
        src = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")
        body = src.split("void do_delete(", 1)[1].split("\nvoid ", 1)[0]
        milestone = body.index('player_milestone_required( ch, ch, "delete" )')
        retire = body.index("!recovery_player_retire(")
        unlink = body.index("unlink( strsave )")
        quit = body.index('do_quit(ch,"")')
        self.assertLess(milestone, retire)
        self.assertLess(retire, unlink)
        self.assertLess(unlink, quit)
        self.assertIn("quit_discards_file = TRUE", body)

    def test_destructive_choices_refuse_without_their_milestone(self) -> None:
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertIn('player_milestone_required( ch, ch, "remort" )', info)
        self.assertIn('player_milestone_required( ch, ch, "combine" )', info)
        self.assertIn('player_milestone_required( ch, victim, "advance" )', wiz)
        self.assertIn('player_milestone_required( ch, victim, "staffset" )', wiz)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DeleteMilestoneLiveTests(unittest.TestCase):
    def test_a_failed_save_stops_delete_and_the_newest_item_survives(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            make(mud, STAFF, Levl=70, Room=4207)
            make(mud, VICTIM, Levl=20, Room=4207)
            pfile = mud.player_dir / VICTIM
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as victim:
                login(staff, STAFF, PW)
                login(victim, VICTIM, PW)
                staff.sync("scroll 0")
                victim.sync("scroll 0")
                victim.must("save", "Saving")
                self.assertNotIn(TOKEN, pfile.read_text(encoding="latin-1"))

                # Picked up after the last save.
                staff.must(f"load obj {DAGGER}", "You create")
                staff.must(f"string obj dagger name {TOKEN} dagger", "")
                staff.must(f"string obj {TOKEN} short a {TOKEN} dagger", "")
                staff.must(f"give {TOKEN} {VICTIM.lower()}", "You give")
                self.assertIn(TOKEN, victim.sync("inventory"))

                # The save DELETE makes fails: nothing is deleted.
                victim.must("delete", "Type delete again")
                (mud.root / "fault.once").write_text(f"save-{VICTIM}\n", encoding="ascii")
                said = victim.sync(f"delete {PW}")
                self.assertIn("nothing has been changed", said)
                self.assertIn("Delete cancelled", said)
                self.assertTrue(pfile.is_file(), "the file stays")
                self.assertIn(TOKEN, victim.sync("inventory"), "still in the game")
                self.assertFalse(re.search(rf"\tuid\tretire\t.*{VICTIM}", ledger(mud)))

                # A second try, the fault spent: deleted, and the milestone
                # holds the dagger picked up after the last ordinary save.
                victim.must("delete", "Type delete again")
                victim.send(f"delete {PW}")
                self.assertTrue(victim.wait_closed(), "deletion leaves the game")

            self.assertFalse(pfile.exists(), "the file is gone")
            holding = snapshots_holding(mud, TOKEN)
            self.assertTrue(any(name.endswith(".delete") for name in holding), holding)
            self.assertRegex(ledger(mud), rf"\tuid\tretire\t.*{VICTIM}")

    def test_a_snapshot_directory_not_confirmed_on_the_disk_is_not_durable(self) -> None:
        """A versions directory whose entry was never flushed into its
        parent is not called durable (review, 2026-11-04: mkdir succeeded,
        nothing synced the parent, and EEXIST later was taken as proof).
        After a restart nothing is known confirmed, so the first milestone
        flushes the directories' parents; "snapshot-dir" fails that flush
        once. DELETE is then refused. Armed again, the retry -- which finds
        the directory already there -- must flush again, and is refused
        again; only a flush that lands lets DELETE go on. Every ordinary
        copy in between is held off by the throttle, its newest file kept
        fresh, so the milestone's own flush is the one the fault meets."""
        import os
        with LiveMud(extra_env=ENV) as mud:
            make(mud, VICTIM, Levl=20, Room=4207)
            pfile = mud.player_dir / VICTIM
            vdir = mud.root / "player" / "versions" / VICTIM
            fault = mud.root / "fault.once"

            def fresh() -> None:
                for path in vdir.iterdir():
                    os.utime(path, None)

            mud.restart()
            fresh()
            with mud.connect(timeout=120) as victim:
                login(victim, VICTIM, PW)
                victim.sync("scroll 0")
                said = []
                for _ in range(2):
                    fresh()
                    fault.write_text("snapshot-dir\n", encoding="ascii")
                    victim.must("delete", "Type delete again")
                    said.append(victim.sync(f"delete {PW}"))
                    self.assertFalse(fault.exists(), "the flush was not asked: " + said[-1])
                victim.must("delete", "Type delete again")
                victim.send(f"delete {PW}")
                self.assertTrue(victim.wait_closed())

            for reply in said:
                self.assertIn("Delete cancelled", reply)
            self.assertFalse(pfile.exists())
            self.assertTrue(any(p.name.endswith(".delete") for p in vdir.iterdir()))

if __name__ == "__main__":
    unittest.main()
