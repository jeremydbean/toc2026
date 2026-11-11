"""Vnums are not 16-bit (owner, 2026-11-11).

Rooms, mobiles and objects held their vnums in sh_int, so nothing could be
numbered past 32,767: an area file that said #40000 was read as -25536 and
hashed into a negative bucket. And WORLD_SIZE, 30,000, was the ceiling ANEW
and DIG accepted and the room saver walked -- below vnums the world already
used. Every vnum is an int now, held to MAX_VNUM (a million).

The live test boots a world holding a disposable area numbered from 40,000
to 900,000 -- rooms joined by exits and a locked door whose key is an
object of its own, a shopkeeper selling a piece, a warden wearing one, a
trinket on the floor -- and plays it: staff walk it, unlock the door with
its key, STAT, MSHOW, OSHOW and LOAD at a high vnum, and GOTO a room past
the old ceiling; a mortal starts in it, picks up a high-vnum object, sets
recall there, saves, and after a reboot comes back holding it; and ANEW at
600,000 saves a whole area and reads it back byte for byte.

Player files and area files always wrote vnums as plain decimal numbers,
so nothing on disk changed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, find_binary, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
MERC = ROOT / "src" / "merc.h"
PW = "Zwidevnum11"

ENTRY, HALL, VAULT, LOFT = 40000, 40001, 40002, 900000
KEY, AMULET, WARE, TRINKET, BAUBLE = 40000, 40001, 40002, 40003, 900000
SHOPKEEPER, WARDEN, HERMIT = 40000, 40001, 900000
NEW_ROOM = 950000                       # GOTO makes it: past the old 30,000
LO, HI = 600000, 600019                 # an ANEW area well past 32,767
WORKS_FILE = "zwide_far_works.are"
AREA_NAME = "zwidevnums.are"


def mobile(vnum: int, keywords: str, short: str, long: str) -> str:
    return f"""#{vnum}
{keywords}~
{short}~
{long}
~
A test fixture with a vnum past what a short holds.
~
human~
AB 0 0 S
10 0 10d10+100 10d10+100 2d4+2 17
-8 -8 -8 -8
0 0 0 0
8 8 1 0
0 0 M 0
"""


def thing(vnum: int, keywords: str, short: str, long: str, kind: str,
          wear: str, cost: int) -> str:
    return f"""#{vnum}
{keywords}~
{short}~
{long}~
iron~
{kind} 0 {wear}
0 0 0 0 0
1 1 {cost} P
"""


def room(vnum: int, name: str, exits: list[tuple[int, str, str, str]]) -> str:
    text = f"#{vnum}\n{name}~\nA bare test room numbered {vnum}.\n~\n0 D 0\n"
    for door, desc, keyword, lock_key_to in exits:
        text += f"D{door}\n{desc}\n~\n{keyword}~\n{lock_key_to}\n"
    return text + "S\n"


AREA = (
    "#AREA   { ALL } Tests   Wide Vnum Fixtures~\n\n#MOBILES\n"
    + mobile(SHOPKEEPER, "shopkeeper zwshop", "a zwide shopkeeper",
             "A zwide shopkeeper minds a counter here.")
    + mobile(WARDEN, "warden zwwarden", "a zwide warden",
             "A zwide warden stands guard over the vault.")
    + mobile(HERMIT, "hermit zwhermit", "a far zwide hermit",
             "A far zwide hermit sits in the loft.")
    + "#0\n\n#OBJECTS\n"
    + thing(KEY, "key zwkey brass", "a brass zwide key",
            "A brass zwide key lies here.", "18", "A", 0)
    + thing(AMULET, "amulet zwamulet", "a zwide warden's amulet",
            "A zwide warden's amulet lies here.", "9", "AC", 10)
    + thing(WARE, "pendant zwpendant", "a zwide pendant",
            "A zwide pendant lies here.", "9", "AC", 100)
    + thing(TRINKET, "trinket zwtrinket", "a zwide trinket",
            "A zwide trinket glints on the floor.", "8", "A", 50)
    + thing(BAUBLE, "bauble zwbauble", "a far-flung zwide bauble",
            "A far-flung zwide bauble lies here.", "8", "A", 50)
    + "#0\n\n#ROOMS\n"
    + room(ENTRY, "The Zwide Entry",
           [(1, "The hall.", "", f"0 -1 {HALL}")])
    + room(HALL, "The Zwide Hall",
           [(3, "The entry.", "", f"0 -1 {ENTRY}"),
            (0, "A brass-bound door.", "door", f"1 {KEY} {VAULT}")])
    + room(VAULT, "The Zwide Vault",
           [(2, "A brass-bound door.", "door", f"1 {KEY} {HALL}"),
            (4, "A ladder up.", "", f"0 -1 {LOFT}")])
    + room(LOFT, "The Far Zwide Loft",
           [(5, "The vault.", "", f"0 -1 {VAULT}")])
    + "#0\n\n#RESETS\n"
    + f"M 0 {SHOPKEEPER} 1 {ENTRY}\n"
    + f"G 0 {WARE} 1\n"
    + f"O 0 {TRINKET} 1 {ENTRY}\n"
    + f"O 0 {KEY} 1 {HALL}\n"
    + f"D 0 {HALL} 0 2\n"
    + f"D 0 {VAULT} 2 2\n"
    + f"M 0 {WARDEN} 1 {VAULT}\n"
    + f"E 0 {AMULET} 1 3\n"
    + f"M 0 {HERMIT} 1 {LOFT}\n"
    + "S\n\n#SHOPS\n"
    + f"{SHOPKEEPER} 0 0 0 0 0 100 100 0 23\n0\n\n#$\n"
)


def add_built_area(area_dir: Path, name: str, text: str) -> None:
    """List an area file in area/built/, as the fixtures are listed."""
    built = area_dir / "built"
    built.mkdir(exist_ok=True)
    (built / name).write_bytes(text.encode("latin-1"))
    listing = built / "built.lst"
    lines = [line for line in (listing.read_text().split() if listing.exists() else [])
             if line != "$"]
    lines.append(f"built/{name}")
    listing.write_text("\n".join(lines + ["$"]) + "\n")


class WideMud(LiveMud):
    """A test world with the wide-vnum area listed before the first boot."""

    def _launch(self) -> None:
        assert self.root is not None
        area = self.root / "area"
        if not (area / "built" / AREA_NAME).exists():
            add_built_area(area, AREA_NAME, AREA)
        super()._launch()


class WideVnumSourceTests(unittest.TestCase):
    def test_no_vnum_field_is_a_short(self) -> None:
        merc = MERC.read_text(encoding="latin-1")
        self.assertIn("#define MAX_VNUM               1000000", merc)
        narrow = re.findall(
            r"^\s*(?:sh_int|int16_t|short)\s+(vnum|key|keeper|min_vnum|max_vnum"
            r"|to_room|arg[123]|questobj|questmob|weapon|guild\[MAX_GUILD\])\s*;",
            merc, re.M)
        self.assertEqual(narrow, [], "vnum fields still 16-bit")
        for struct in ("mob_index_data", "obj_index_data", "room_index_data"):
            body = re.search(r"struct\s+%s\s*\{(.*?)\n\};" % struct, merc, re.S)
            assert body, struct
            self.assertRegex(body.group(1), r"\bint\s+vnum;", struct)
        exit_body = re.search(r"struct\s+exit_data\s*\{(.*?)\n\};", merc, re.S).group(1)
        self.assertRegex(exit_body, r"\bint\s+vnum;")
        self.assertRegex(exit_body, r"\bint\s+key;")
        self.assertNotIn("WORLD_SIZE", re.sub(r"/\*.*?\*/", "", merc, flags=re.S))

    def test_nothing_squeezes_a_vnum_or_caps_one_at_a_short(self) -> None:
        cast = re.compile(
            r"(\bvnum|->key|\.key|keeper|to_room|->arg[123]|min_vnum|max_vnum)\s*=\s*"
            r"\(\s*(sh_int|int16_t|short)\s*\)")
        for path in sorted((ROOT / "src").glob("*.[ch]")):
            text = path.read_text(encoding="latin-1")
            code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            self.assertNotRegex(code, cast, path.name)
            self.assertNotRegex(code, r"\b(sh_int|int16_t|short)\s+vnum\b", path.name)
            self.assertNotIn("WORLD_SIZE", code, path.name)
            # A random vnum is guessed up to the highest in use, not 65535.
            self.assertNotRegex(code, r"get_\w+_index\(\s*number_range\(\s*0\s*,\s*65535\s*\)",
                                path.name)
            # A vnum typed by staff is a whole number in range, however
            # many digits it takes: a million is seven.
            self.assertNotRegex(code, r"strlen\(\s*\w+\s*\)\s*>\s*5\s*\n\s*\|\|\s*\(.*typed_vnum",
                                path.name)
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertNotIn("parse_int( argument, -1, SHRT_MAX, &key )", wiz)
        self.assertNotIn("We only have about 32000 objects", wiz)
        build = (ROOT / "src" / "build.c").read_text(encoding="latin-1")
        self.assertNotIn("plain_number( value, 32767 )", build)
        for scratch, name in (("walkto.c", "WALK_SLOTS"), ("blackmarket.c", "BM_VNUM_MAX")):
            text = (ROOT / "src" / scratch).read_text(encoding="latin-1")
            self.assertRegex(text, r"#define %s\s+\(\s*MAX_VNUM \+ 1\s*\)" % name, scratch)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WideVnumBootTests(unittest.TestCase):
    """--check-area loads the wide area and refuses one past MAX_VNUM."""

    def check_area(self, area: Path) -> subprocess.CompletedProcess:
        binary = find_binary()
        assert binary is not None
        return subprocess.run([str(binary), "--check-area"], cwd=area,
                              capture_output=True, text=True, timeout=600,
                              errors="replace")

    def test_check_area_reads_the_wide_area_and_refuses_past_the_ceiling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="toc-wide-") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "area", root / "area")
            for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
                (root / name).mkdir()
            # The shipped world's totals, then the same with the area.
            base = self.check_area(root / "area")
            self.assertEqual(base.returncode, 0, base.stdout[-2000:] + base.stderr[-2000:])
            counts = re.search(r"areas=(\d+) mobs=(\d+) objects=(\d+) rooms=(\d+)",
                               base.stdout + base.stderr)
            assert counts, base.stdout[-2000:] + base.stderr[-2000:]
            areas, mobs, objects, rooms = map(int, counts.groups())

            add_built_area(root / "area", AREA_NAME, AREA)
            wide = self.check_area(root / "area")
            out = wide.stdout + wide.stderr
            self.assertEqual(wide.returncode, 0, out[-2000:])
            self.assertIn(f"Validation OK: areas={areas + 1} mobs={mobs + 3} "
                          f"objects={objects + 5} rooms={rooms + 4}", out)

            # One vnum past the ceiling stops the boot, as any malformed
            # record does; it used to wrap into a short and load as
            # somebody else's number.
            add_built_area(root / "area", "zwidetoofar.are",
                           "#AREA   { ALL } Tests   Too Far~\n\n#ROOMS\n"
                           + room(1000001, "Too Far", []) + "#0\n\n#$\n")
            far = self.check_area(root / "area")
            out = far.stdout + far.stderr
            self.assertNotEqual(far.returncode, 0, out[-2000:])
            self.assertIn("Load_rooms: vnum 1000001 is outside 1 to 1000000.", out)

            # Nor may a built area claim a range past it: its range bounds
            # every walk over its prototypes, which a short used to cap.
            (root / "area" / "built" / "zwidetoofar.are").write_text(
                "#AREADATA\nName Too Wide~\nBuilders All~\nVNUMs 700000 2000000\n"
                "End\n\n#ROOMS\n#0\n\n#$\n", encoding="latin-1")
            wide_range = self.check_area(root / "area")
            out = wide_range.stdout + wide_range.stderr
            self.assertNotEqual(wide_range.returncode, 0, out[-2000:])
            self.assertIn("Load_areadata: VNUMs 700000 2000000 is not a range in 1 to 1000000.",
                          out)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WideVnumLiveTests(unittest.TestCase):
    def make(self, mud: LiveMud, name: str, **fields: object) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PW)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, name, **fields)

    def test_a_world_past_the_old_ceiling(self) -> None:
        with WideMud() as mud:
            self.make(mud, "Zvnumstaff", Levl=70, Room=4207)
            self.make(mud, "Zvnumhero", Levl=20, Room=ENTRY,
                      HMV="2000 2000 500 500 500 500")
            works = mud.root / "area" / "built" / WORKS_FILE

            with mud.connect(timeout=120) as hero:
                # The player file's Room 40000 is a room again.
                login(hero, "Zvnumhero", PW)
                here = hero.sync("look", timeout=60)
                self.assertIn("The Zwide Entry", here)
                self.assertIn("A zwide shopkeeper minds a counter here.", here)
                self.assertIn("A zwide trinket glints on the floor.", here)
                self.assertIn("a zwide pendant", hero.sync("list", timeout=60))
                hero.must("get zwtrinket", "You get a zwide trinket")
                hall = hero.sync("east", timeout=60)
                self.assertIn("The Zwide Hall", hall)
                hero.must("recall set", "The Zwide Hall")
                hero.must("save", "Saving")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            saved = (mud.player_dir / "Zvnumhero").read_text(encoding="latin-1")
            self.assertRegex(saved, rf"(?m)^Vnum {TRINKET}$")
            self.assertRegex(saved, rf"(?m)^RecallRoom {HALL}$")
            self.assertRegex(saved, rf"(?m)^Room {HALL}$")

            with mud.connect(timeout=120) as staff:
                login(staff, "Zvnumstaff", PW)
                staff.sync("scroll 0")
                self.assertIn("The Zwide Hall", staff.sync(f"goto {HALL}", timeout=60))
                staff.must("get zwkey", "You get a brass zwide key")
                staff.must("unlock north", "*Click*", "Click")
                staff.must("open north", "Ok.", "You open")
                vault = staff.sync("north", timeout=60)
                self.assertIn("The Zwide Vault", vault)
                self.assertIn("A zwide warden stands guard over the vault.", vault)
                self.assertIn(f"Vnum: {VAULT}", staff.sync("stat room", timeout=60))
                warden = staff.must("stat mob zwwarden", f"Vnum: {WARDEN}")
                self.assertRegex(warden, rf"Room: {VAULT}\b")
                self.assertIn("a zwide warden's amulet",
                              staff.sync("look zwwarden", timeout=60))

                loft = staff.sync("up", timeout=60)
                self.assertIn("The Far Zwide Loft", loft)
                self.assertIn("A far zwide hermit sits in the loft.", loft)
                self.assertIn(f"Vnum: {LOFT}", staff.sync("stat room", timeout=60))
                staff.must("stat mob zwhermit", f"Vnum: {HERMIT}")
                self.assertIn(str(HERMIT), staff.must(f"mshow {HERMIT}", "far zwide hermit"))
                self.assertIn(str(BAUBLE), staff.must(f"oshow {BAUBLE}", "far-flung zwide bauble"))
                staff.must(f"load obj {BAUBLE}", "You create a far-flung zwide bauble")
                staff.must("ostat zwbauble", f"Vnum: {BAUBLE}")
                staff.must(f"load mob {HERMIT}", "You create a far zwide hermit")
                self.assertIn(f"Vnum: {SHOPKEEPER}",
                              staff.sync(f"at {ENTRY} stat mob zwshop", timeout=60))

                # GOTO a number nothing holds makes the room, now to MAX_VNUM.
                staff.must(f"goto {NEW_ROOM}", "You form order from nothingness")
                self.assertIn(f"Vnum: {NEW_ROOM}", staff.sync("stat room", timeout=60))
                staff.must("goto 1000001", "too large")

                # A whole area built past 32,767, saved by the writer.
                staff.must(f"anew {LO} {HI} Zwide Far Works", "Created area")
                staff.sync(f"goto {LO + 1}", timeout=60)
                staff.sync(f"set room {LO + 1} name The Far Works", timeout=60)
                staff.sync(f"rlink north {LO + 2}", timeout=60)
                staff.sync("rlink north door", timeout=60)
                staff.must(f"rlink north key {LO + 6}", f"Object {LO + 6} unlocks")
                staff.must(f"mcreate {LO + 5} {HERMIT}", f"a copy of {HERMIT}")
                staff.must(f"ocreate {LO + 6} {KEY}", f"a copy of {KEY}")
                staff.must(f"ocreate {LO + 7} {BAUBLE}", f"a copy of {BAUBLE}")
                staff.sync(f"place mob {LO + 5}", timeout=60)
                staff.sync(f"place obj {LO + 7}", timeout=60)
                before = staff.must(f"ostat {LO + 7}", f"Vnum: {LO + 7}")
                staff.must("asave", "Saved Zwide Far Works")
                staff.send("quit")
                self.assertTrue(staff.wait_closed())

            first = works.read_bytes()
            text = first.decode("latin-1")
            self.assertIn(f"VNUMs {LO} {HI}", text)
            for vnum in (LO + 1, LO + 2, LO + 5, LO + 6, LO + 7):
                self.assertRegex(text, rf"(?m)^#{vnum}$")
            self.assertRegex(text, rf"(?m)^1 {LO + 6} {LO + 2}$", "the door's key and room")
            self.assertRegex(text, rf"(?m)^M 0 {LO + 5} \d+ {LO + 1}$")
            self.assertRegex(text, rf"(?m)^O 0 {LO + 7} \d+ {LO + 1}$")

            mud.restart()

            with mud.connect(timeout=120) as hero:
                login(hero, "Zvnumhero", PW)
                self.assertIn("The Zwide Hall", hero.sync("look", timeout=60))
                self.assertIn("a zwide trinket", hero.sync("inventory", timeout=60))
                self.assertIn("The Zwide Hall", hero.sync("recall where", timeout=60))
                hero.send("quit")
                self.assertTrue(hero.wait_closed())

            with mud.connect(timeout=120) as staff:
                login(staff, "Zvnumstaff", PW)
                staff.sync("scroll 0")
                again = staff.must(f"ostat {LO + 7}", f"Vnum: {LO + 7}")
                self.assertEqual(ostat_lines(again), ostat_lines(before))
                works_room = staff.sync(f"goto {LO + 1}", timeout=60)
                self.assertIn("The Far Works", works_room)
                self.assertIn("A far zwide hermit sits in the loft.", works_room)
                self.assertIn("A far-flung zwide bauble lies here.", works_room)
                staff.must("asave", "Saved Zwide Far Works")
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            self.assertEqual(first, works.read_bytes(),
                             "the area file changed when saved again after a reboot")


def ostat_lines(text: str) -> list[str]:
    keep = re.compile(r"^(Name\(s\)|Short description|Long description"
                      r"|Wear bits|Extra bits|Level|Values:)")
    return [line.strip() for line in text.replace("\r", "").split("\n")
            if keep.match(line.strip())]


if __name__ == "__main__":
    unittest.main()
