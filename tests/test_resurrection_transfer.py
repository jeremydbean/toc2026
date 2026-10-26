"""ACCEPT is a transfer that is done on the disk or not done at all.

Resurrection ended the corpse first and saved last, ignoring the save:
with the save failed and a crash before the next one, the risen player
had lost everything the corpse held and no live corpse remained (review,
2026-10-26). Now the corpse's record is written and held, a pending
receipt goes down, everything moves, the owner's file is saved -- and
only on the disk does the held record go to history and the receipt
commit. A failed save puts everything back; a crash between the save and
the commit is settled at boot from the owner's file.

Each test plays a partly looted corpse holding a dagger, a bag with a
dagger inside, and a pile of coin.
"""
from __future__ import annotations

import os
import re
import signal
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
PW = "Zrtpass1"
TEMPLE = 4207
DAGGER, BAG, BOX = 3701, 3032, 3033


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def add_lines(mud: LiveMud, name: str, objects: str = "", skill: str = "") -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if skill:
        at = text.index("\nEnd\n")
        text = text[:at] + f"\nSk 100 '{skill}'" + text[at:]
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def obj(vnum: int, nest: int = 0) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nEnd\n\n" % (vnum, nest)


def coins(amount: int) -> str:
    """A pile of gold carried as an object: a purse stays with its owner
    at death, but a pile in the pack falls into the corpse."""
    return ("#O\nVnum 3\nNest 0\nWear -1\nLev 1\nCond 100\nName gold coins~\n"
            "ShD  %d gold coins~\nDesc A pile of %d gold coins.~\n"
            "Val  %d 2 0 0 0\nEnd\n\n" % (amount, amount, amount))


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def setup(mud: LiveMud) -> None:
    make(mud, "Zrtstaff", Levl=70, Room=TEMPLE)
    make(mud, "Zrtcleric", Levl=45, Room=TEMPLE, Cla=1, Gui=1,
         HMV="900 900 2000 2000 500 500", HMVP="900 2000 500")
    add_lines(mud, "Zrtcleric", skill="resurrection")
    make(mud, "Zrtfallen", Levl=20, Room=TEMPLE,
         HMV="300 300 300 300 300 300", HMVP="300 300 300")
    # A dagger; a bag holding a dagger; a box, which staff loot first.
    add_lines(mud, "Zrtfallen", objects=obj(DAGGER) + obj(BAG) + obj(DAGGER, 1) + obj(BOX)
                                       + coins(40))


def kill_loot_and_call(staff, cleric, fallen) -> None:
    staff.must("slay zrtfallen", "")
    fallen.drain(1.5)
    staff.must("get box corpse", "You get")                 # partly looted
    cleric.must("cast resurrection corpse", "soul home")
    fallen.drain(1.5)


def ledger_states(mud: LiveMud) -> list:
    path = mud.player_dir / "recovery" / "ledger.tsv"
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r[3] for r in rows if len(r) > 6 and r[2] == "request"
            and r[6].startswith("resurrect:")]


def live_corpses(mud: LiveMud) -> list:
    return [p.name for p in (mud.root / "corpse" / "live").glob("*.corpse")]


def resurrected_history(mud: LiveMud) -> str:
    found = list((mud.root / "corpse" / "history" / "Zrtfallen").glob("*.resurrected.corpse"))
    assert len(found) == 1, found
    return found[0].read_text(encoding="latin-1")


def crash(mud: LiveMud) -> None:
    os.kill(mud.proc.pid, signal.SIGKILL)
    mud.proc.wait(timeout=15)
    mud.restart()


def what_they_hold(mud: LiveMud) -> tuple:
    with mud.connect(timeout=120) as back:
        login(back, "Zrtfallen", PW)
        back.sync("scroll 0")
        inv = back.sync("inventory")
        bag = back.sync("look in bag")
        back.send("quit")
        back.wait_closed()
    text = (mud.player_dir / "Zrtfallen").read_text(encoding="latin-1")
    gold = int(re.search(r"^NewGold (\d+)", text, re.M).group(1))
    return inv, bag, gold


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResurrectionTransferTests(unittest.TestCase):
    def test_a_failed_save_puts_everything_back_and_a_retry_rises(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                for client, name in ((staff, "Zrtstaff"), (cleric, "Zrtcleric"),
                                     (fallen, "Zrtfallen")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                kill_loot_and_call(staff, cleric, fallen)
                dead_room = room_of(staff, "zrtfallen")

                fault(mud, "save-Zrtfallen")
                undone = fallen.sync("accept")
                after_undone = room_of(staff, "zrtfallen")
                in_corpse = staff.sync("look in corpse")

                rose = fallen.sync("accept")
                risen_room = room_of(staff, "zrtfallen")
            crash(mud)                       # no save after the rise
            inv, bag, gold = what_they_hold(mud)
            history = resurrected_history(mud)
            live = live_corpses(mud)
            states = ledger_states(mud)

        self.assertIn("could not be written down", undone, undone)
        self.assertEqual(after_undone, dead_room)            # never moved
        self.assertIn("dagger", in_corpse)
        self.assertIn("bag", in_corpse)
        self.assertRegex(in_corpse, r"gold|coins")
        self.assertIn("edge of life", rose, rose)
        self.assertEqual(risen_room, TEMPLE)
        # Everything once, after a crash: the dagger, the bag and its
        # dagger, the coin in the purse; the box was looted before.
        self.assertEqual(inv.count("dagger"), 1, inv)
        self.assertIn("bag", inv)
        self.assertNotIn("box", inv)
        self.assertIn("dagger", bag, bag)
        self.assertGreaterEqual(gold, 40)
        # The corpse is spent, and history holds exactly what was given.
        self.assertEqual(live, [])
        self.assertIn("Vnum %d" % BAG, history)
        self.assertEqual(history.count("Vnum %d" % DAGGER), 2, history)
        self.assertNotIn("Vnum %d" % BOX, history)
        self.assertEqual(states, ["pending", "abandoned", "pending", "committed"])

    def test_a_crash_after_an_undone_accept_lays_the_corpse_again_whole(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                for client, name in ((staff, "Zrtstaff"), (cleric, "Zrtcleric"),
                                     (fallen, "Zrtfallen")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                kill_loot_and_call(staff, cleric, fallen)
                fault(mud, "save-Zrtfallen")
                undone = fallen.sync("accept")
                staff.sync("time")           # a pulse for the record to be written
                staff.drain(2.0)
            crash(mud)
            live = live_corpses(mud)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zrtstaff", PW)
                in_corpse = staff.sync("look in corpse")
            inv, _, _ = what_they_hold(mud)
            states = ledger_states(mud)

        self.assertIn("could not be written down", undone, undone)
        self.assertEqual(len(live), 1, live)
        self.assertIn("dagger", in_corpse)
        self.assertIn("bag", in_corpse)
        self.assertNotIn("dagger", inv)              # nothing given twice
        self.assertEqual(states, ["pending", "abandoned"])

    def test_a_crash_between_the_save_and_the_commit_is_settled_at_boot(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                for client, name in ((staff, "Zrtstaff"), (cleric, "Zrtcleric"),
                                     (fallen, "Zrtfallen")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                kill_loot_and_call(staff, cleric, fallen)
                fault(mud, "crash-before-commit")
                fallen.send("accept")
                self.assertTrue(fallen.wait_closed(), "the game should have stopped")
            mud.proc.wait(timeout=15)
            mud.restart()
            live = live_corpses(mud)
            history = resurrected_history(mud)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zrtstaff", PW)
                here = staff.sync("look")
            inv, bag, gold = what_they_hold(mud)
            states = ledger_states(mud)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")

        self.assertEqual(live, [])
        self.assertNotIn("corpse of Zrtfallen", here.lower().replace("the corpse", "corpse"))
        self.assertEqual(history.count("Vnum %d" % DAGGER), 2, history)
        self.assertEqual(inv.count("dagger"), 1, inv)
        self.assertIn("dagger", bag, bag)
        self.assertGreaterEqual(gold, 0)
        self.assertEqual(states, ["pending", "committed"])
        self.assertIn("was resurrected before the restart; settled", log)


if __name__ == "__main__":
    unittest.main()
