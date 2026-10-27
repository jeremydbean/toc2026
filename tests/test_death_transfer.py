"""A death is a transfer from the player's file to their corpse.

make_corpse moves everything carried into the corpse and the corpse keeper
writes the corpse down at once -- but the post-death save of the player
was commented out, so until the next autosave the player's file still
held everything too. A crash in that window laid the corpse again at boot
and logged the player in with the same things: a duplication (review,
2026-10-27). Now a death is a ledgered transfer: a pending death:<id>
receipt, the corpse's record on the disk, the player's file saved with a
mark, then the commit. A crash at any point is settled from the player's
file: marked, the corpse is theirs; not marked, the file still holds
everything and the corpse is never laid.

Each test kills a fixture carrying a dagger, a bag with a dagger inside
and a box, then counts every dagger in the world after a crash.
"""
from __future__ import annotations

import os
import re
import signal
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zdtpass1"
TEMPLE = 4207
DAGGER, BAG, BOX = 3701, 3032, 3033


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def obj(vnum: int, nest: int = 0) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nEnd\n\n" % (vnum, nest)


def give(mud: LiveMud, name: str, objects: str) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def setup(mud: LiveMud) -> None:
    make(mud, "Zdtstaff", Levl=70, Room=TEMPLE)
    make(mud, "Zdtfallen", Levl=20, Room=TEMPLE,
         HMV="300 300 300 300 300 300", HMVP="300 300 300")
    give(mud, "Zdtfallen", obj(DAGGER) + obj(BAG) + obj(DAGGER, 1) + obj(BOX))


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def crash(mud: LiveMud) -> None:
    os.kill(mud.proc.pid, signal.SIGKILL)
    mud.proc.wait(timeout=15)
    mud.restart()


def file_vnums(mud: LiveMud, name: str) -> list:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)]


def corpse_vnums(mud: LiveMud) -> list:
    """Every object vnum in every live corpse record (what boot lays)."""
    found = []
    live = mud.root / "corpse" / "live"
    for path in live.glob("*.corpse"):
        if ".ending." in path.name or ".stale." in path.name:
            continue
        text = path.read_text(encoding="latin-1")
        found += [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)]
    return found


def death_states(mud: LiveMud) -> list:
    path = mud.player_dir / "recovery" / "ledger.tsv"
    if not path.exists():
        return []
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r[3] for r in rows if len(r) > 6 and r[2] == "request"
            and r[6].startswith("death:")]


def world_daggers(mud: LiveMud) -> tuple:
    """(daggers in the player's file, daggers in corpses laid at boot,
    whether boot laid a corpse) -- after a restart, before anyone logs in."""
    in_file = file_vnums(mud, "Zdtfallen").count(DAGGER)
    with mud.connect(timeout=120) as staff:
        login(staff, "Zdtstaff", PW)
        staff.sync("scroll 0")
        here = staff.sync("look").lower()
        laid = "corpse of zdtfallen" in here
        inside = staff.sync("look in corpse").lower() if laid else ""
    # "a dagger" twice at the top level would print "(2) a dagger"; count
    # the bag's dagger through the record instead of the screen.
    in_corpse = corpse_vnums(mud).count(DAGGER) if laid else 0
    return in_file, in_corpse, laid, inside


@unittest.skipIf(SKIP is not None, SKIP or "")
class DeathTransferTests(unittest.TestCase):
    def test_a_crash_right_after_a_death_never_duplicates(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fallen:
                login(staff, "Zdtstaff", PW)
                login(fallen, "Zdtfallen", PW)
                fallen.sync("scroll 0")
                staff.must("slay zdtfallen", "")
            crash(mud)                          # no autosave, no quit
            in_file, in_corpse, laid, inside = world_daggers(mud)
            states = death_states(mud)

        self.assertEqual(in_file + in_corpse, 2,
                         f"file {in_file} + corpse {in_corpse}: every dagger exactly once")
        # The death's own save landed, so the corpse is theirs.
        self.assertTrue(laid, inside)
        self.assertEqual(in_file, 0)
        self.assertIn("box", inside)
        self.assertEqual(states, ["pending", "committed"])

    def test_a_death_whose_save_failed_is_undone_by_a_crash(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fallen:
                login(staff, "Zdtstaff", PW)
                login(fallen, "Zdtfallen", PW)
                fallen.sync("scroll 0")
                fault(mud, "death-save-Zdtfallen")
                staff.must("slay zdtfallen", "")
                # Nobody may loot a corpse whose death is not yet on the disk.
                looted = staff.sync("get box corpse")
            crash(mud)
            in_file, in_corpse, laid, _ = world_daggers(mud)
            states = death_states(mud)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")

        self.assertIn("still being laid to rest", looted, looted)
        self.assertEqual(in_file + in_corpse, 2)
        self.assertFalse(laid, "the file still held everything; the corpse must not be laid")
        self.assertEqual(in_file, 2)
        self.assertEqual(states, ["pending", "abandoned"])
        self.assertIn("the death never reached their file", log)

    def test_a_failed_death_save_is_settled_by_the_next_save(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fallen:
                login(staff, "Zdtstaff", PW)
                login(fallen, "Zdtfallen", PW)
                fallen.sync("scroll 0")
                fault(mud, "death-save-Zdtfallen")
                staff.must("slay zdtfallen", "")
                fallen.must("save", "Saving")
                looted = staff.sync("get box corpse")
            crash(mud)
            in_file, in_corpse, laid, inside = world_daggers(mud)
            states = death_states(mud)

        self.assertIn("You get", looted, looted)
        self.assertTrue(laid)
        # The box: taken by staff, whose file was not saved before the crash,
        # and the corpse record catches up within a second of a change -- a
        # looting window older than this work. Only the daggers, which
        # nobody looted, are this test's to count.
        self.assertEqual(in_file + in_corpse, 2)
        self.assertEqual(in_file, 0)
        self.assertEqual(states, ["pending", "committed"])


if __name__ == "__main__":
    unittest.main()
