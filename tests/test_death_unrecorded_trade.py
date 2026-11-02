"""Nothing changes hands while a death is unrecorded (review, 2026-11-02).

An unrecorded death holds the owner's file still: every save of theirs is
refused, so a quit, a fresh login or a restart puts back the file from
before the death -- that is what makes undoing the corpse safe
(tests/test_death_unrecorded.py). But the owner went on playing in
memory, and a review found the hole: WITHDRAW one gold from the bank,
GIVE it to somebody who saves, quit and log in again -- the taker kept
the gold and the bank had all of it back. Money from nothing.

corpse_registry_refuses_trade() now stops every command that moves coin
or things between the frozen character and anybody or anything else --
GIVE either way, DROP, PUT and GET with anything not carried, DONATE,
BUY, SELL, the bank, the stash, SPLIT, STEAL and SACRIFICE -- before
anything moves. Saves stay refused (allowing them would defeat the
corpse's recovery). These tests count every copper on both sides across
the death, the attempts, a quit and login, the receipt's retry and a
restart. Synthetic Z characters only.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import (BANK_ROOM_VNUM, LiveMud, create_character, login, patch_player_file,
                      skip_reason)
from test_death_unrecorded import LedgerDown, death_states, kill_server

SKIP = skip_reason()
PW = "Zdtpass1"
FALLEN, TAKER = "Zdtfallen", "Zdttaker"
REFUSED = "has not been laid to rest yet"
ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}
COPPER = {"NewPlat": 1000000, "NewGold": 10000, "NewSilv": 100, "NewCopp": 1}


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def wealth(mud: LiveMud, name: str) -> int:
    """Purse plus bank, in copper, as the file on disk holds it."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    total = 0
    for key, unit in list(COPPER.items()) + [("BankCP", 1)]:
        found = re.search(r"^%s\s+(-?\d+)" % key, text, re.M)
        if found:
            total += int(found.group(1)) * unit
    return total


def setup(mud: LiveMud, fixes: str | None = None) -> None:
    make(mud, "Zdtstaff", Levl=70, Room=BANK_ROOM_VNUM)
    make(mud, FALLEN, Levl=20, Room=BANK_ROOM_VNUM, BankCP=10000,
         NewPlat=0, NewGold=0, NewSilv=0, NewCopp=0, HMV="300 300 300 300 300 300")
    make(mud, TAKER, Levl=20, Room=BANK_ROOM_VNUM, BankCP=0,
         NewPlat=0, NewGold=1, NewSilv=0, NewCopp=0)
    if fixes is not None:
        path = mud.player_dir / FALLEN
        text = re.sub(r"^Fixes .*~$", "Fixes " + fixes + "~",
                      path.read_text(encoding="latin-1"), count=1, flags=re.M)
        path.write_text(text, encoding="latin-1")


def full_fixes() -> str:
    filler = " ".join("zfill%05d" % i for i in range(1600))[:15990]
    return filler[:filler.rfind(" ")]


@unittest.skipIf(SKIP is not None, SKIP or "")
class UnrecordedDeathTradeTests(unittest.TestCase):
    def kill_and_return(self, mud: LiveMud, before=None):
        staff = mud.connect(timeout=120)
        fallen = mud.connect(timeout=120)
        taker = mud.connect(timeout=120)
        self.clients = (staff, fallen, taker)
        login(staff, "Zdtstaff", PW)
        login(fallen, FALLEN, PW)
        login(taker, TAKER, PW)
        for client in self.clients:
            client.sync("scroll 0")
        if before is not None:
            before()
        staff.must("slay zdtfallen", "")
        staff.must(f"transfer zdtfallen {BANK_ROOM_VNUM}", "Ok.")
        self.assertIn("still being laid to rest", staff.sync("get all corpse"))
        return staff, fallen, taker

    def tearDown(self) -> None:
        for client in getattr(self, "clients", ()):
            try:
                client.close()
            except OSError:
                pass

    def assert_frozen(self, fallen, taker) -> None:
        for line in ("withdraw 1 gold", "deposit 1 copper", "drop all",
                     "give 1 gold zdttaker", "get all", "stash put sword",
                     "sell sword", "split 1 gold"):
            self.assertIn(REFUSED, fallen.sync(line), line)
        self.assertIn("nothing can pass between you", taker.sync("give 1 gold zdtfallen"))

    def test_withdraw_and_give_cannot_make_money(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud, fixes=full_fixes())
            before = wealth(mud, FALLEN) + wealth(mud, TAKER)
            staff, fallen, taker = self.kill_and_return(mud)
            self.assert_frozen(fallen, taker)
            taker.must("save", "Saving")
            fallen.send("quit")
            self.assertTrue(fallen.wait_closed())
            fallen = mud.connect(timeout=120)
            self.clients = (staff, fallen, taker)
            login(fallen, FALLEN, PW)
            fallen.sync("scroll 0")
            fallen.must("save", "Saving")
            taker.must("save", "Saving")
            kill_server(mud)
            mud.restart()
            after_fallen, after_taker = wealth(mud, FALLEN), wealth(mud, TAKER)

        self.assertEqual(before, after_fallen + after_taker, "not a copper made or lost")
        self.assertEqual((after_fallen, after_taker), (10000, 10000))

    def test_after_the_retry_records_the_death_money_moves_again(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            before = wealth(mud, FALLEN) + wealth(mud, TAKER)
            down = LedgerDown(mud)
            staff, fallen, taker = self.kill_and_return(mud, down.down)
            self.assert_frozen(fallen, taker)
            down.up()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and death_states(mud) != ["pending", "committed"]:
                staff.sync("time")
            self.assertEqual(death_states(mud), ["pending", "committed"])
            fallen.must("withdraw 1 gold", "You withdraw")
            fallen.must("give 1 gold zdttaker", "You give")
            taker.must("save", "Saving")
            fallen.must("save", "Saving")
            kill_server(mud)
            mud.restart()
            after_fallen, after_taker = wealth(mud, FALLEN), wealth(mud, TAKER)

        self.assertEqual(before, after_fallen + after_taker)
        self.assertEqual((after_fallen, after_taker), (0, 20000))


if __name__ == "__main__":
    unittest.main()
