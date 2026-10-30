"""A death the ledger cannot record stays unsettled, never laid twice.

A death is a ledgered transfer (tests/test_death_transfer.py): a pending
death:<id> receipt, a mark in the player's Fixes, the save, the commit.
When the receipt could not be written -- the ledger unwritable -- or the
mark could not fit -- a full Fixes list -- corpse_registry_died left the
corpse unpending, so corpse_registry_death_settle saw nothing to settle
and never saved the player. A crash then laid the corpse at boot beside a
file still holding everything: every dagger twice (review, 2026-10-30).

Now such a death is UNRECORDED: the corpse is kept but nobody may loot
it, the player's file is not saved over (it still holds everything), the
receipt is tried again every few seconds, and a crash, a quit or a login
before it lands undoes the corpse -- its twin is in the file. Each test
kills a fixture carrying a dagger and a bag with a dagger inside, with
the automatic tick saves held off (TOC_FAULT=autowrite), and counts
every dagger after a crash.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zdupass1"
TEMPLE = 4207
DAGGER, BAG = 3701, 3032
FALLEN = "Zdufallen"


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def obj(vnum: int, nest: int = 0) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nEnd\n\n" % (vnum, nest)


def setup(mud: LiveMud, fixes: str | None = None) -> None:
    make(mud, "Zdustaff", Levl=70, Room=TEMPLE)
    make(mud, FALLEN, Levl=20, Room=TEMPLE,
         HMV="300 300 300 300 300 300", HMVP="300 300 300")
    path = mud.player_dir / FALLEN
    text = path.read_text(encoding="latin-1")
    text = text.replace("#END", obj(DAGGER) + obj(BAG) + obj(DAGGER, 1) + "#END", 1)
    if fixes is not None:
        text = re.sub(r"^Fixes .*~$", "Fixes " + fixes + "~", text, count=1, flags=re.M)
        assert ("Fixes " + fixes) in text
    path.write_text(text, encoding="latin-1")


def ledger(mud: LiveMud):
    return mud.player_dir / "recovery" / "ledger.tsv"


class LedgerDown:
    """The recovery ledger made unwritable -- a directory where the file
    was, which refuses an open for writing whoever the server runs as --
    while player and corpse storage stay writable."""

    def __init__(self, mud: LiveMud) -> None:
        self.path = ledger(mud)
        self.kept = self.path.with_name("ledger.kept")

    def down(self) -> None:
        shutil.move(str(self.path), str(self.kept))
        self.path.mkdir()

    def up(self) -> None:
        self.path.rmdir()
        shutil.move(str(self.kept), str(self.path))


def kill_server(mud: LiveMud) -> None:
    os.kill(mud.proc.pid, signal.SIGKILL)
    mud.proc.wait(timeout=15)


def file_daggers(mud: LiveMud) -> int:
    text = (mud.player_dir / FALLEN).read_text(encoding="latin-1")
    return [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)].count(DAGGER)


def live_corpse_daggers(mud: LiveMud) -> int:
    found = 0
    for path in (mud.root / "corpse" / "live").glob("*.corpse"):
        if ".ending." in path.name or ".stale." in path.name:
            continue
        text = path.read_text(encoding="latin-1")
        found += [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)].count(DAGGER)
    return found


def after_restart(mud: LiveMud) -> tuple:
    """(daggers in the file, daggers in a corpse boot laid, whether one was
    laid) -- read before anyone logs in, as boot left them."""
    in_file = file_daggers(mud)
    with mud.connect(timeout=120) as staff:
        login(staff, "Zdustaff", PW)
        staff.sync("scroll 0")
        laid = "corpse of zdufallen" in staff.sync("look").lower()
    return in_file, live_corpse_daggers(mud) if laid else 0, laid


def death_states(mud: LiveMud) -> list:
    path = ledger(mud)
    if not path.is_file():
        return []
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r[3] for r in rows if len(r) > 6 and r[2] == "request"
            and r[6].startswith("death:")]


def server_log(mud: LiveMud) -> str:
    return (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")


ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}


@unittest.skipIf(SKIP is not None, SKIP or "")
class UnrecordedDeathTests(unittest.TestCase):
    def kill_fallen(self, mud: LiveMud, before=None) -> str:
        """Log both in, run `before` (the fault), slay the fallen and try
        to loot the corpse. Returns the looting reply."""
        self.staff = mud.connect(timeout=120)
        self.fallen = mud.connect(timeout=120)
        login(self.staff, "Zdustaff", PW)
        login(self.fallen, FALLEN, PW)
        self.fallen.sync("scroll 0")
        if before is not None:
            before()
        self.staff.must("slay zdufallen", "")
        return self.staff.sync("get all corpse")

    def tearDown(self) -> None:
        for client in (getattr(self, "staff", None), getattr(self, "fallen", None)):
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass

    def test_an_unwritable_ledger_then_a_crash_never_duplicates(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            down = LedgerDown(mud)
            looted = self.kill_fallen(mud, down.down)
            kill_server(mud)
            down.up()
            mud.restart()
            in_file, in_corpse, laid = after_restart(mud)
            log = server_log(mud)

        self.assertEqual((in_file, in_corpse), (2, 0),
                         f"file {in_file} + corpse {in_corpse}: every dagger exactly once")
        self.assertFalse(laid, "the file still holds everything; its twin must not be laid")
        self.assertIn("still being laid to rest", looted, looted)
        self.assertIn("not recorded", log)
        self.assertIn("was not laid -- the death was never recorded", log)

    def test_a_full_fixes_list_then_a_crash_never_duplicates(self) -> None:
        # A list one short mark below the limit has no room for the death's.
        filler = " ".join("zfill%05d" % i for i in range(1600))[:15990]
        filler = filler[:filler.rfind(" ")]
        with LiveMud(extra_env=ENV) as mud:
            setup(mud, fixes=filler)
            self.kill_fallen(mud)
            kill_server(mud)
            mud.restart()
            in_file, in_corpse, laid = after_restart(mud)

        self.assertEqual((in_file, in_corpse), (2, 0))
        self.assertFalse(laid)

    def test_the_receipt_is_retried_and_then_the_corpse_is_theirs(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            down = LedgerDown(mud)
            self.kill_fallen(mud, down.down)
            down.up()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and death_states(mud) != ["pending", "committed"]:
                self.staff.sync("time")
            states = death_states(mud)
            looted = self.staff.sync("look in corpse")
            kill_server(mud)
            mud.restart()
            in_file, in_corpse, laid = after_restart(mud)

        self.assertEqual(states, ["pending", "committed"])
        self.assertNotIn("still being laid to rest", looted)
        self.assertEqual((in_file, in_corpse), (0, 2))
        self.assertTrue(laid)

    def test_a_crash_between_the_receipt_and_the_save_undoes_the_death(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            down = LedgerDown(mud)
            self.kill_fallen(mud, down.down)
            (mud.root / "fault.once").write_text("death-recorded-crash\n")
            down.up()
            mud.proc.wait(timeout=60)       # the retry records, then dies
            mud.restart()
            in_file, in_corpse, laid = after_restart(mud)
            states = death_states(mud)

        self.assertEqual((in_file, in_corpse), (2, 0))
        self.assertFalse(laid)
        self.assertEqual(states, ["pending", "abandoned"])

    def test_a_quit_and_a_login_before_the_receipt_get_the_things_back(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            down = LedgerDown(mud)
            self.kill_fallen(mud, down.down)
            self.fallen.send("quit")
            self.assertTrue(self.fallen.wait_closed())
            self.fallen = mud.connect(timeout=120)
            login(self.fallen, FALLEN, PW)
            self.fallen.sync("scroll 0")
            inventory = self.fallen.sync("inventory").lower()
            room = self.staff.sync("look").lower()
            down.up()
            # Saved from here on, and nothing for a retry to find.
            self.fallen.must("save", "Saving")
            self.staff.sync("time")
            kill_server(mud)
            mud.restart()
            in_file, in_corpse, laid = after_restart(mud)

        self.assertIn("dagger", inventory, inventory)
        self.assertNotIn("corpse of zdufallen", room, room)
        self.assertEqual((in_file, in_corpse), (2, 0))
        self.assertFalse(laid)


if __name__ == "__main__":
    unittest.main()
