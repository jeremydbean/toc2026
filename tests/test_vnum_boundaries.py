"""Vnums at the old boundaries and the ceiling load and work (second review
of the overflow fix, 2026-11-12).

The readers now refuse a number past int while they accumulate it
(tests/test_number_overflow.py); this holds the other side: every number
that fits still reads exactly. 32767 and 32768 straddle the old sh_int,
65535 and 65536 an unsigned short, and 1,000,000 is MAX_VNUM itself. A
disposable area holds rooms 32767, 32768 and 1000000 joined by exits (a
locked door whose key is object 32767), mobiles 32767 (a shopkeeper
selling object 32768) and 32768 (wearing 32768), object 1000000 on the
floor, all placed by resets; a mortal starts in 32767, unlocks, walks to
1000000, sets recall there and stashes 1000000, and after a reboot is back
with all of it. ANEW 65530-65540 builds rooms, a mobile and objects at
65535 and 65536 with a door between, the writer saves them, a reboot loads
them, and a second save is byte for byte the first.
"""

from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
from test_wide_vnums import add_built_area, mobile, room, thing

SKIP = skip_reason()
PW = "Zboundpass1"
LOW, HIGH, TOP = 32767, 32768, 1000000          # rooms
SHOP, WARDEN = 32767, 32768                     # mobiles
KEY, AMULET, TRINKET = 32767, 32768, 1000000    # objects
LO, HI = 65530, 65540                           # the ANEW range
A, B = 65535, 65536
AREA_NAME = "zboundvnums.are"
WORKS_FILE = "zbound_works.are"

AREA = (
    "#AREA   { ALL } Tests   Boundary Vnums~\n\n#MOBILES\n"
    + mobile(SHOP, "shopkeeper zbshop", "a zbound shopkeeper",
             "A zbound shopkeeper minds a counter here.")
    + mobile(WARDEN, "warden zbwarden", "a zbound warden",
             "A zbound warden keeps the top room.")
    + "#0\n\n#OBJECTS\n"
    + thing(KEY, "key zbkey iron", "an iron zbound key", "An iron zbound key lies here.",
            "18", "A", 0)
    + thing(AMULET, "amulet zbamulet", "a zbound amulet", "A zbound amulet lies here.",
            "9", "AC", 100)
    + thing(TRINKET, "trinket zbtrinket", "a topmost zbound trinket",
            "A topmost zbound trinket glints here.", "8", "A", 50)
    + "#0\n\n#ROOMS\n"
    + room(LOW, "The Zbound Low Room", [(1, "An iron door.", "door", f"1 {KEY} {HIGH}")])
    + room(HIGH, "The Zbound High Room",
           [(3, "An iron door.", "door", f"1 {KEY} {LOW}"),
            (4, "A stair up.", "", f"0 -1 {TOP}")])
    + room(TOP, "The Zbound Top Room", [(5, "The stair down.", "", f"0 -1 {HIGH}")])
    + "#0\n\n#RESETS\n"
    + f"M 0 {SHOP} 1 {LOW}\n"
    + f"G 0 {AMULET} 5\n"      # a limit the shop's and the warden's copies both fit
    + f"O 0 {KEY} 1 {LOW}\n"
    + f"D 0 {LOW} 1 2\n"
    + f"D 0 {HIGH} 3 2\n"
    + f"M 0 {WARDEN} 1 {TOP}\n"
    + f"E 0 {AMULET} 5 3\n"
    + f"O 0 {TRINKET} 1 {TOP}\n"
    + "S\n\n#SHOPS\n"
    + f"{SHOP} 0 0 0 0 0 100 100 0 23\n0\n\n#$\n"
)


class BoundMud(LiveMud):
    def _launch(self) -> None:
        assert self.root is not None
        area = self.root / "area"
        if not (area / "built" / AREA_NAME).exists():
            add_built_area(area, AREA_NAME, AREA)
        super()._launch()


@unittest.skipIf(SKIP is not None, SKIP or "")
class VnumBoundaryTests(unittest.TestCase):
    def make(self, mud: LiveMud, name: str, **fields: object) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PW)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, name, **fields)

    def test_the_old_boundaries_and_the_ceiling(self) -> None:
        with BoundMud() as mud:
            self.make(mud, "Zboundstaff", Levl=70, Room=4207)
            self.make(mud, "Zboundhero", Levl=20, Room=LOW, HMV="2000 2000 500 500 500 500")
            works = mud.root / "area" / "built" / WORKS_FILE

            with mud.connect(timeout=120) as hero:
                login(hero, "Zboundhero", PW)
                here = hero.sync("look", timeout=60)
                self.assertIn("The Zbound Low Room", here)
                self.assertIn("A zbound shopkeeper minds a counter here.", here)
                self.assertIn("a zbound amulet", hero.sync("list", timeout=60))
                hero.must("get zbkey", "You get an iron zbound key")
                hero.must("unlock east", "*Click*", "Click")
                hero.must("open east", "Ok.", "You open")
                self.assertIn("The Zbound High Room", hero.sync("east", timeout=60))
                top = hero.sync("up", timeout=60)
                self.assertIn("The Zbound Top Room", top)
                self.assertIn("A zbound warden keeps the top room.", top)
                hero.must("get zbtrinket", "You get a topmost zbound trinket")
                hero.must("recall set", "The Zbound Top Room")
                hero.must("stash put zbtrinket", "safe keeping")
                hero.must("save", "Saving")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            saved = (mud.player_dir / "Zboundhero").read_text(encoding="latin-1")
            self.assertRegex(saved, rf"(?m)^Room {TOP}$")
            self.assertRegex(saved, rf"(?m)^RecallRoom {TOP}$")
            self.assertRegex(saved, rf"(?m)^Vnum {TRINKET}$", "the stashed trinket")

            with mud.connect(timeout=120) as staff:
                login(staff, "Zboundstaff", PW)
                staff.sync("scroll 0")
                for vnum in (LOW, HIGH, TOP):
                    staff.must(f"goto {vnum}", "")
                    self.assertIn(f"Vnum: {vnum}", staff.sync("stat room", timeout=60))
                staff.must(f"at {LOW} stat mob zbshop", f"Vnum: {SHOP}")
                warden = staff.must(f"at {TOP} stat mob zbwarden", f"Vnum: {WARDEN}")
                self.assertRegex(warden, rf"Room: {TOP}\b")
                self.assertIn("a zbound amulet", staff.sync(f"at {TOP} look zbwarden", timeout=60))
                staff.must(f"mshow {WARDEN}", "zbound warden")
                staff.must(f"oshow {TRINKET}", "topmost zbound trinket")
                staff.must(f"oshow {KEY}", "iron zbound key")
                staff.must(f"load obj {AMULET}", "You create a zbound amulet")
                staff.must("ostat zbamulet", f"Vnum: {AMULET}")
                staff.must("goto 1000001", "too large")

                # 65535 and 65536 through the writer.
                staff.must(f"anew {LO} {HI} Zbound Works", "Created area")
                staff.sync(f"goto {A}", timeout=60)
                staff.sync(f"set room {A} name The Zbound Works", timeout=60)
                staff.sync(f"rlink east {B}", timeout=60)
                staff.sync("rlink east door", timeout=60)
                staff.must(f"rlink east key {B}", f"Object {B} unlocks")
                staff.must(f"mcreate {A} {WARDEN}", f"a copy of {WARDEN}")
                staff.must(f"ocreate {B} {KEY}", f"a copy of {KEY}")
                staff.must(f"ocreate {A} {TRINKET}", f"a copy of {TRINKET}")
                staff.sync(f"place mob {A}", timeout=60)
                staff.sync(f"place obj {A}", timeout=60)
                staff.must("asave", "Saved Zbound Works")
                staff.send("quit")
                self.assertTrue(staff.wait_closed())

            first = works.read_bytes()
            text = first.decode("latin-1")
            self.assertIn(f"VNUMs {LO} {HI}", text)
            for vnum in (A, B):
                self.assertRegex(text, rf"(?m)^#{vnum}$")
            self.assertRegex(text, rf"(?m)^1 {B} {B}$", "the door's key and room")
            self.assertRegex(text, rf"(?m)^M 0 {A} \d+ {A}$")
            self.assertRegex(text, rf"(?m)^O 0 {A} \d+ {A}$")

            mud.restart()

            with mud.connect(timeout=180) as hero:
                login(hero, "Zboundhero", PW)
                self.assertIn("The Zbound Top Room", hero.sync("look", timeout=60))
                self.assertIn("The Zbound Top Room", hero.sync("recall where", timeout=60))
                self.assertIn("topmost zbound trinket", hero.sync("stash", timeout=60))
                hero.send("quit")
                self.assertTrue(hero.wait_closed())

            with mud.connect(timeout=120) as staff:
                login(staff, "Zboundstaff", PW)
                staff.sync("scroll 0")
                works_room = staff.sync(f"goto {A}", timeout=60)
                self.assertIn("The Zbound Works", works_room)
                self.assertIn("A zbound warden keeps the top room.", works_room)
                self.assertIn("A topmost zbound trinket glints here.", works_room)
                staff.must(f"mshow {A}", "zbound warden")
                self.assertIn(f"Vnum: {A}", staff.sync("stat room", timeout=60))
                staff.must(f"load obj {B}", "You create an iron zbound key")
                staff.sync("unlock east", timeout=60)
                staff.sync("open east", timeout=60)
                staff.sync("east", timeout=60)
                self.assertIn(f"Vnum: {B}", staff.sync("stat room", timeout=60))
                staff.must(f"oshow {B}", "iron zbound key")
                staff.must("asave", "Saved Zbound Works")
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            self.assertEqual(first, works.read_bytes(),
                             "the area file changed when saved again after a reboot")


if __name__ == "__main__":
    unittest.main()
