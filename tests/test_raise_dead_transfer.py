"""RAISE DEAD gives a corpse back through the protected transfer (review, 2026-11-04).

RAISE DEAD moved the corpse's belongings to its owner, extracted the
corpse, ignored the owner's save and announced success. With that save
failed and a crash before the next, the returned kit was in neither the
player file nor a live corpse. It now goes through corpse_give_to_owner,
the transfer ACCEPT makes: the corpse's record held whole, a pending
resurrect:<id> receipt, the mark in the owner's Fixes, then the save --
and only on the disk is the corpse used up and the owner pulled to the
caster. RAISE DEAD keeps what makes it RAISE DEAD: no consent, and only
what the owner can carry, the rest falling to the floor.

Each test kills a synthetic character carrying a dagger, a bag holding a
dagger, and coin, and has a synthetic cleric raise them.
"""
from __future__ import annotations

import os
import re
import signal
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
PW = "Zrdpass1"
TEMPLE = 4207
DEATH_ROOM = 4216
DAGGER, BAG = 3701, 3032
FALLEN, CLERIC, STAFF = "Zrdfallen", "Zrdcleric", "Zrdstaff"


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


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def setup(mud: LiveMud, extra: str = "") -> None:
    make(mud, STAFF, Levl=70, Room=TEMPLE)
    make(mud, CLERIC, Levl=45, Room=TEMPLE, Cla=1, Gui=1,
         HMV="900 900 3000 3000 500 500", HMVP="900 3000 500")
    add_lines(mud, CLERIC, skill="raise dead")
    make(mud, FALLEN, Levl=20, Room=TEMPLE,
         HMV="300 300 300 300 300 300", HMVP="300 300 300")
    add_lines(mud, FALLEN, objects=obj(DAGGER) + obj(BAG) + obj(DAGGER, 1) + extra)


def enter(mud: LiveMud, staff, cleric, fallen) -> None:
    for client, name in ((staff, STAFF), (cleric, CLERIC), (fallen, FALLEN)):
        login(client, name, PW)
        client.sync("scroll 0")
    if "now immune" in fallen.sync("nosummon"):
        fallen.must("nosummon", "no longer immune")


def kill(staff, fallen) -> None:
    staff.must(f"slay {FALLEN.lower()}", "")
    fallen.drain(1.5)


def ledger_states(mud: LiveMud) -> list:
    path = mud.player_dir / "recovery" / "ledger.tsv"
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r[3] for r in rows if len(r) > 6 and r[2] == "request"
            and r[6].startswith("resurrect:")]


def live_corpses(mud: LiveMud) -> list:
    return [p.name for p in (mud.root / "corpse" / "live").glob("*.corpse")]


def history(mud: LiveMud) -> list:
    hdir = mud.root / "corpse" / "history" / FALLEN
    return [p.read_text(encoding="latin-1") for p in hdir.glob("*.resurrected.corpse")]


def crash(mud: LiveMud) -> None:
    os.kill(mud.proc.pid, signal.SIGKILL)
    mud.proc.wait(timeout=15)
    mud.restart()


def what_they_hold(mud: LiveMud) -> tuple:
    with mud.connect(timeout=120) as back:
        login(back, FALLEN, PW)
        back.sync("scroll 0")
        inv = back.sync("inventory")
        bag = back.sync("look in bag")
        back.send("quit")
        back.wait_closed()
    return inv, bag


ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}


@unittest.skipIf(SKIP is not None, SKIP or "")
class RaiseDeadTransferTests(unittest.TestCase):
    def test_a_failed_save_moves_nothing_and_a_retry_survives_a_crash(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                enter(mud, staff, cleric, fallen)
                kill(staff, fallen)
                self.assertEqual(room_of(staff, FALLEN.lower()), DEATH_ROOM)

                fault(mud, "raise-save")
                undone = cleric.sync("cast 'raise dead' corpse")
                fallen.drain(1.0)
                where_undone = room_of(staff, FALLEN.lower())
                in_corpse = staff.sync("look in corpse")

                staff.sync(f"restore {CLERIC.lower()}")
                rose = cleric.sync("cast 'raise dead' corpse")
                where_risen = room_of(staff, FALLEN.lower())
            crash(mud)                       # nothing saved after the raise
            inv, bag = what_they_hold(mud)
            kept = history(mud)
            live = live_corpses(mud)
            states = ledger_states(mud)

        self.assertIn("could be written down", undone, undone)
        self.assertEqual(where_undone, DEATH_ROOM, "never moved by an undone raise")
        self.assertIn("dagger", in_corpse)
        self.assertIn("bag", in_corpse)
        self.assertIn("returned", rose, rose)
        self.assertEqual(where_risen, TEMPLE)
        # Everything once, after a crash: the dagger, and the bag with its dagger.
        self.assertEqual(inv.count("dagger"), 1, inv)
        self.assertIn("bag", inv)
        self.assertIn("dagger", bag, bag)
        self.assertEqual(live, [])
        self.assertEqual(len(kept), 1, kept)
        self.assertEqual(kept[0].count("Vnum %d" % DAGGER), 2, kept[0])
        self.assertEqual(states, ["pending", "abandoned", "pending", "committed"])

    def test_a_crash_after_an_undone_raise_lays_the_corpse_again_whole(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                enter(mud, staff, cleric, fallen)
                kill(staff, fallen)
                fault(mud, "raise-save")
                undone = cleric.sync("cast 'raise dead' corpse")
                staff.drain(2.0)
            crash(mud)
            live = live_corpses(mud)
            with mud.connect(timeout=120) as staff:
                login(staff, STAFF, PW)
                in_corpse = staff.sync("look in corpse")
            inv, _ = what_they_hold(mud)
            states = ledger_states(mud)

        self.assertIn("could be written down", undone, undone)
        self.assertEqual(len(live), 1, live)
        self.assertIn("dagger", in_corpse)
        self.assertIn("bag", in_corpse)
        self.assertNotIn("dagger", inv)              # nothing given twice
        self.assertEqual(states, ["pending", "abandoned"])

    def test_an_unconfirmed_save_stays_pending_and_never_duplicates(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                enter(mud, staff, cleric, fallen)
                kill(staff, fallen)
                fault(mud, f"dirsync-{FALLEN}")
                rose = cleric.sync("cast 'raise dead' corpse")
            crash(mud)
            live = live_corpses(mud)
            inv, bag = what_they_hold(mud)
            states = ledger_states(mud)

        self.assertIn("returned", rose, rose)
        self.assertEqual(live, [])
        self.assertEqual(inv.count("dagger"), 1, inv)
        self.assertIn("dagger", bag, bag)
        self.assertEqual(states, ["pending", "committed"])

    def test_what_does_not_fit_falls_and_the_record_keeps_it_all(self) -> None:
        many = "".join(obj(DAGGER) for _ in range(80))
        with LiveMud(extra_env=ENV) as mud:
            setup(mud, extra=many)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                enter(mud, staff, cleric, fallen)
                kill(staff, fallen)
                rose = cleric.sync("cast 'raise dead' corpse")
                floor = staff.sync("look")
                fallen.drain(1.0)
                carried = fallen.sync("inventory")
            kept = history(mud)

        self.assertIn("fall to the ground", rose, rose)
        carried_daggers = len(re.findall(r"dagger", carried))
        self.assertGreater(carried_daggers, 0, carried)
        self.assertIn("dagger", floor.lower())
        self.assertEqual(len(kept), 1, kept)
        # The held record is the whole corpse: every dagger, carried or fallen.
        self.assertEqual(kept[0].count("Vnum %d" % DAGGER), 82, "whole record")

    def test_an_unsettled_death_is_refused_before_anything_moves(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                enter(mud, staff, cleric, fallen)
                fault(mud, f"death-save-{FALLEN}")
                kill(staff, fallen)
                said = cleric.sync("cast 'raise dead' corpse")
                where = room_of(staff, FALLEN.lower())
                in_corpse = staff.sync("look in corpse")
            states = ledger_states(mud)

        self.assertIn("will not answer", said, said)
        self.assertEqual(where, DEATH_ROOM)
        self.assertIn("dagger", in_corpse)
        self.assertEqual(states, [])


if __name__ == "__main__":
    unittest.main()
