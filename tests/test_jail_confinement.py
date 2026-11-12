"""A jail sentence confines the prisoner, not the cell's flags (owner,
2026-11-12: a mortal must not escape an active sentence).

The rule used to be the ROOM_JAIL flag that each travel check asked, so a
prisoner in a cell with an exit, or a cell without its flags, walked out
-- and a death sent them to the death room unless the room they died in
carried the flag. Now char_to_room asks jail_hold_room() at every
placement (src/jail.c), and the commands that would start something
outside the cell refuse first.

Two worlds. The stock cell (room 3, no exits, JAIL NO_RECALL SILENT)
shows a death is a whole death there now -- a corpse, the deaths log --
and the prisoner stays. A synthetic cell -- the same room given an exit
north to the Temple and no flags at all -- is what proves the sentence
does the confining: walking, recall, a recall scroll, a portal, teleport,
a pocket room, a projection, a prayer, staff TRANSFER and FORCE, remort,
DELETE, and deaths by SLAY, remote FARSLAY and a mortal's Farslay rite
all leave the prisoner in room 3, jailed, with the same deadline.

Synthetic Z characters in throwaway worlds only.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import (
    LiveMud,
    MudClient,
    create_character,
    login,
    patch_player_file,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zjailpw12"
CELL = 3
TEMPLE = 4207
DEATH_ROOM = 4216
SCROLL_OF_RECALL = 3042
PORTAL = 26
SCROLL_OF_FARSLAY = 20305
# A bare number of days, which JAIL has always taken, and both spellings of
# its answer: the old binary can then be run against these tests and fail
# where the prisoner gets out, not at the syntax.
JAILED = ("now in jail", "now in Jail")


def make(mud: LiveMud, name: str, level: int, room: int = TEMPLE, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Levl=level, Room=room, **fields)


def give_skill(mud: LiveMud, name: str, skill: str, percent: int) -> None:
    path = mud.player_dir / name
    lines = path.read_text(encoding="latin-1").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("Sk "))
    lines.insert(at, "Sk %d '%s'" % (percent, skill))
    path.write_text("\n".join(lines), encoding="latin-1", newline="")


def file_field(mud: LiveMud, name: str, key: str) -> str | None:
    for line in (mud.player_dir / name).read_text(encoding="latin-1").split("\n"):
        if line.split(" ")[0] == key:
            return line[len(key) + 1:]
    return None


def synthetic_cell(mud: LiveMud) -> None:
    """Room 3 in this world gets an exit north to the Temple and loses
    every flag; the server is restarted to read it."""
    path = mud.root / "area" / "limbo.are"
    text = path.read_bytes().decode("latin-1")
    start = text.index("#3\nThe Jail~")
    flags = text.index("0 BNX 0\nS\n", start)
    text = (text[:flags] + "0 0 0\nD0\n~\n~\n0 -1 %d\nS\n" % TEMPLE
            + text[flags + len("0 BNX 0\nS\n"):])
    path.write_bytes(text.encode("latin-1"))
    mud.restart()
    # Wait for the greeting: the port opens before the world is read.
    with mud.connect(timeout=120) as probe:
        probe.expect("by what name", "name:")


def recite_until(test, warden, reader, vnum: int, name: str, target: str,
                 effect: str, after=None) -> bool:
    """Hand the reader a scroll and have it read, again while the reading
    is only a mispronounced syllable: the scroll's roll, not the jail."""
    for _ in range(8):
        warden.must("load obj %d" % vnum, "You create")
        warden.must("give scroll %s" % name, "You give")
        reply = reader.sync("recite scroll" + target)
        if after is not None:
            after("recite")
        if effect in reply:
            return True
        test.assertIn("mispronounce", reply)
    return False


def jailed_until(reply: str) -> str:
    match = re.search(r"is jailed \((?:online|offline|link-dead)\) (until [^(]+|indefinitely)",
                      reply)
    assert match, reply
    return match.group(1).strip()


@unittest.skipIf(SKIP is not None, SKIP or "")
class SyntheticCellTests(unittest.TestCase):
    """Room 3 with an exit and no flags: only the sentence holds them."""

    def test_nothing_takes_a_prisoner_out_of_a_cell_with_a_door(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            # A mage, so the pocket rooms and teleport are hers to cast.
            make(mud, "Zinmate", 50, Cla=0, HpManaMove="300 300 900 900 300 300")
            make(mud, "Zremorter", 54)
            make(mud, "Zdeleter", 20)
            for skill in ("project", "teleport", "rope trick", "haven", "scrolls"):
                give_skill(mud, "Zinmate", skill, 100)
            synthetic_cell(mud)

            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as inmate:
                login(warden, "Zwarden", PW)
                login(inmate, "Zinmate", PW)
                warden.sync("scroll 0")
                inmate.sync("scroll 0")

                warden.must("jail zinmate 7", *JAILED)
                self.assertEqual(CELL, room_of(warden, "Zinmate"))

                def held(what: str) -> None:
                    self.assertEqual(CELL, room_of(warden, "Zinmate"), what)
                    self.assertIn("is jailed", warden.sync("jail zinmate status"), what)

                # Walking out of the door the cell now has.
                reply = inmate.sync("north")
                held("north")
                self.assertIn("serving a jail sentence", reply)
                # The sentence was saved the moment it was given.
                deadline = file_field(mud, "Zinmate", "Jw_Timer")
                self.assertGreater(int(deadline), int(time.time()) + 6 * 86400)
                # The prayer.
                self.assertIn("serving a jail sentence", inmate.sync("recall"))
                held("recall")
                # A scroll of recall: read until it is read right (a
                # mispronounced syllable is the scroll's own roll).
                warden.sync("goto %d" % CELL)
                self.assertTrue(recite_until(self, warden, inmate, SCROLL_OF_RECALL,
                                             "zinmate", "", "Spell failed", held))
                # A portal to the Temple, lying in the cell.
                warden.must("load obj %d" % PORTAL, "You create")
                warden.sync("drop portal")
                warden.must("set obj portal v1 %d" % TEMPLE, "Ok", "set")
                self.assertIn("serving a jail sentence", inmate.sync("enter portal"))
                held("portal")
                # Their own spells and powers.
                self.assertIn("You failed", inmate.sync("cast teleport"))
                held("teleport")
                self.assertIn("serving a jail sentence", inmate.sync("project north"))
                self.assertIn("serving a jail sentence", inmate.sync("cast 'rope trick' north"))
                self.assertIn("serving a jail sentence", inmate.sync("cast haven"))
                held("pocket rooms")
                self.assertIn("serving a jail sentence", inmate.sync("pray hello"))
                held("pray")
                # Staff moving them is refused; staff making them walk is a walk.
                warden.sync("goto %d" % TEMPLE)
                self.assertIn("JAIL Zinmate RELEASE", warden.sync("transfer zinmate"))
                warden.sync("force zinmate north")
                held("transfer and force")

                # Deaths: a slay beside them, a farslay from afar, each a
                # real death, and the prisoner stays with the same deadline.
                warden.sync("goto %d" % CELL)
                self.assertEqual(CELL, room_of(warden, "Zwarden"))
                warden.sync("slay zinmate")
                inmate.drain(1.0)
                self.assertIn("corpse of Zinmate", warden.sync("look"))
                held("slay")
                self.assertEqual(deadline, file_field(mud, "Zinmate", "Jw_Timer"))
                self.assertIn("DEATH: Zinmate", (mud.root / "log" / "deaths.log").read_text())
                warden.sync("goto %d" % TEMPLE)
                self.assertNotIn("not in this world", warden.sync("farslay zinmate"))
                inmate.expect("KILLED")
                held("farslay")
                self.assertEqual(deadline, file_field(mud, "Zinmate", "Jw_Timer"))
                self.assertEqual(2, (mud.root / "log" / "deaths.log").read_text().count(
                    "DEATH: Zinmate"))

                inmate.send("quit")
                self.assertTrue(inmate.wait_closed())

            # A remort from a cell with a door, at a level that may remort.
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as remorter:
                login(warden, "Zwarden", PW)
                login(remorter, "Zremorter", PW)
                warden.must("jail zremorter 1", *JAILED)
                reply = remorter.sync("remort %s mage none human" % PW)
                self.assertNotIn("equipped by the Gods", reply)
                self.assertIn("serving a jail sentence", reply)
                self.assertEqual(CELL, room_of(warden, "Zremorter"))
                self.assertIn("Levl 54", (mud.player_dir / "Zremorter").read_text(
                    encoding="latin-1"))
                remorter.send("quit")
                self.assertTrue(remorter.wait_closed())

            # A deletion asked for before the sentence does not finish in it.
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as deleter:
                login(warden, "Zwarden", PW)
                login(deleter, "Zdeleter", PW)
                self.assertIn("password to confirm", deleter.sync("delete"))
                warden.must("jail zdeleter 1", *JAILED)
                self.assertIn("serving a jail sentence", deleter.sync("delete %s" % PW))
                self.assertTrue((mud.player_dir / "Zdeleter").is_file())
                self.assertIn("serving a jail sentence", deleter.sync("delete"))
                deleter.send("quit")
                self.assertTrue(deleter.wait_closed())
            self.assertTrue((mud.player_dir / "Zdeleter").is_file())

    def test_a_mortal_farslay_rite_keeps_both_prisoners(self) -> None:
        """The rite kills its target or, backfiring, its reader: both are
        prisoners here, so whichever it does, the one who dies stays."""
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zavenger", 30)
            give_skill(mud, "Zavenger", "scrolls", 100)
            make(mud, "Zwronged", 30)
            synthetic_cell(mud)
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as avenger, \
                 mud.connect(timeout=120) as wronged:
                login(warden, "Zwarden", PW)
                login(avenger, "Zavenger", PW)
                login(wronged, "Zwronged", PW)
                warden.must("jail zavenger 3", *JAILED)
                warden.must("jail zwronged 2", *JAILED)
                warden.sync("goto %d" % CELL)
                self.assertTrue(recite_until(self, warden, avenger, SCROLL_OF_FARSLAY,
                                             "zavenger", " zwronged", "Farslayer howls"))
                warden.sync("goto %d" % TEMPLE)
                avenger.drain(1.0)
                wronged.drain(1.0)
                # One of them was killed, whichever way the rite went.
                self.assertTrue("You have been KILLED" in avenger.transcript
                                or "You have been KILLED" in wronged.transcript)
                deaths = (mud.root / "log" / "deaths.log").read_text()
                self.assertTrue("DEATH: Zavenger" in deaths or "DEATH: Zwronged" in deaths,
                                deaths)
                for name in ("Zavenger", "Zwronged"):
                    self.assertEqual(CELL, room_of(warden, name), name)
                for name in ("Zavenger", "Zwronged"):
                    self.assertIn("is jailed", warden.sync("jail %s status" % name))


@unittest.skipIf(SKIP is not None, SKIP or "")
class StockCellTests(unittest.TestCase):
    def test_a_death_in_the_stock_cell_is_whole_and_keeps_them(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zcondemned", 20)
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as condemned:
                login(warden, "Zwarden", PW)
                login(condemned, "Zcondemned", PW)
                warden.must("jail zcondemned 3", *JAILED)
                deadline = file_field(mud, "Zcondemned", "Jw_Timer")
                self.assertEqual(CELL, room_of(warden, "Zcondemned"))
                warden.sync("goto %d" % CELL)
                warden.sync("slay zcondemned")
                condemned.drain(1.0)
                # The corpse lies in the cell and the death is logged: the
                # death was not skipped for the room's flag.
                self.assertIn("corpse of Zcondemned", warden.sync("look"))
                self.assertIn("DEATH: Zcondemned",
                              (mud.root / "log" / "deaths.log").read_text())
                self.assertEqual(CELL, room_of(warden, "Zcondemned"))
                self.assertEqual(deadline, file_field(mud, "Zcondemned", "Jw_Timer"))
                self.assertNotEqual(DEATH_ROOM, room_of(warden, "Zcondemned"))
                condemned.sync("stand")
                self.assertIn("serving a jail sentence", condemned.sync("north"))


if __name__ == "__main__":
    unittest.main()
