"""A number past its type's range is malformed, never wrapped (review of
d19b0e92, 2026-11-12).

fread_number accumulated `number * 10 + digit` in an int with no check,
and fread_record_vnum checked the range only afterwards: an area file
holding room #4295367296 overflowed (undefined behaviour, which UBSan
reports) and wrapped to 400000 -- inside 1..MAX_VNUM -- so --check-area
passed and the room loaded under somebody else's number. fread_long and
fread_flag's digits had the same accumulator. Each digit is now checked
before the arithmetic (digit_append, numparse.c): an area file at boot
stops with the file and line, as any malformed record does, and a player
file refuses that character (fread_player_trap) while the game plays on.

The --check-area cases run against whichever binary live_mud finds, so
under TOC_SERVER_BINARY=<a sanitizer build> they also prove the reading
itself raises no UBSan report.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, find_binary, login, patch_player_file, skip_reason
from test_audit_saves import PASSWORD, PLAIN, TEMPLE, make, obj, run, stash_vnums, write_snapshots

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
NAME = "znumover.are"


def room(vnum: str, exits: str = "") -> str:
    return f"#{vnum}\nA Numbered Room~\nA bare test room.\n~\n0 D 0\n{exits}S\n"


def area(rooms: str, extra: str = "") -> str:
    return ("#AREA   { ALL } Tests   Number Overflow~\n\n" + extra
            + "#ROOMS\n" + rooms + "#0\n\n#$\n")


def thing(vnum: int, cost: str, value0: str = "0") -> str:
    """value[0] is read by fread_flag, the cost by fread_long."""
    return (f"#{vnum}\nzflag zthing~\na ztest thing~\nA ztest thing lies here.~\n"
            f"iron~\n8 0 A\n{value0} 0 0 0 0\n1 1 {cost} P\n")


class PythonReaderTests(unittest.TestCase):
    """webadmin/area_reader.py reads as db.c does, so it refuses the same
    numbers and reads the same boundaries."""

    def test_the_python_reader_refuses_what_the_game_refuses(self) -> None:
        from webadmin.area_reader import AreaFormatError, parse_area_text

        for vnum in ("2147483648", "4295367296", "9" * 40, "-2147483649"):
            with self.subTest(vnum=vnum), self.assertRaises(AreaFormatError) as caught:
                parse_area_text(area(room(vnum)), NAME)
            self.assertIn("out of range", str(caught.exception))
        with self.assertRaises(AreaFormatError):
            parse_area_text("#AREA   { ALL } Tests   N~\n\n#OBJECTS\n"
                            + thing(940000, "9" * 25) + "#0\n\n#$\n", NAME)
        with self.assertRaises(AreaFormatError):
            parse_area_text("#AREA   { ALL } Tests   N~\n\n#OBJECTS\n"
                            + thing(940000, "10", "4294967296") + "#0\n\n#$\n", NAME)
        rooms = "".join(room(str(v)) for v in (32767, 32768, 65535, 65536, 1000000))
        parsed = parse_area_text(area(rooms), NAME)
        self.assertEqual([r.vnum for r in parsed.rooms], [32767, 32768, 65535, 65536, 1000000])
        cost = parse_area_text("#AREA   { ALL } Tests   N~\n\n#OBJECTS\n"
                               + thing(940000, "9223372036854775807", "2147483647")
                               + "#0\n\n#$\n", NAME)
        self.assertEqual(len(cost.objects), 1)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AreaNumberOverflowTests(unittest.TestCase):
    """--check-area on a disposable copy of the world, one built area at a
    time: each overflowing number stops the boot with the file named."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="toc-numover-")
        cls.root = Path(cls.tmp.name)
        shutil.copytree(ROOT / "area", cls.root / "area")
        for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
            (cls.root / name).mkdir()
        built = cls.root / "area" / "built"
        built.mkdir(exist_ok=True)
        listing = built / "built.lst"
        lines = [line for line in (listing.read_text().split() if listing.exists() else [])
                 if line != "$"]
        listing.write_text("\n".join(lines + [f"built/{NAME}", "$"]) + "\n")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def check(self, text: str) -> tuple[int, str]:
        (self.root / "area" / "built" / NAME).write_bytes(text.encode("latin-1"))
        binary = find_binary()
        assert binary is not None
        run = subprocess.run([str(binary), "--check-area"], cwd=self.root / "area",
                             capture_output=True, text=True, timeout=600, errors="replace")
        out = run.stdout + run.stderr
        self.assertNotIn("runtime error", out, out[-3000:])
        return run.returncode, out

    def refused(self, text: str, message: str) -> str:
        code, out = self.check(text)
        self.assertNotEqual(code, 0, out[-2000:])
        self.assertNotIn("Validation OK", out, out[-2000:])
        self.assertIn(message, out, out[-2000:])
        self.assertRegex(out, rf"FILE: built/{re.escape(NAME)} LINE: \d+", out[-2000:])
        return out

    def test_a_record_vnum_past_int_is_refused_never_wrapped(self) -> None:
        for vnum in ("2147483648", "4295367296", "4294967296", "9" * 40, "-2147483649"):
            with self.subTest(vnum=vnum):
                out = self.refused(area(room(vnum)), "Fread_number: number out of range.")
                self.assertNotIn("Validation OK", out)

    def test_in_range_but_past_the_ceiling_or_negative_is_still_refused(self) -> None:
        self.refused(area(room("1000001")), "Load_rooms: vnum 1000001 is outside 1 to 1000000.")
        self.refused(area(room("2147483647")),
                     "Load_rooms: vnum 2147483647 is outside 1 to 1000000.")
        self.refused(area(room("-5")), "Load_rooms: vnum -5 is outside 1 to 1000000.")

    def test_the_terminator_still_ends_a_section(self) -> None:
        code, out = self.check(area(room("940000") + room("940001")))
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("Validation OK", out)

    def test_every_number_a_vnum_rides_on_is_checked(self) -> None:
        # An exit's destination, a reset's argument, an area's declared
        # range, an object's cost (fread_long) and a flag's digits.
        self.refused(area(room("940000", "D0\nnorth\n~\n~\n0 -1 4295367296\n")),
                     "Fread_number: number out of range.")
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#ROOMS\n" + room("940000")
                     + "#0\n\n#RESETS\nO 0 4295367296 1 940000\nS\n\n#$\n",
                     "Fread_number: number out of range.")
        self.refused(area(room("940000", "D0\nnorth\n~\ndoor~\n1 4295367296 940000\n")),
                     "Fread_number: number out of range.")             # an exit's key
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#SHOPS\n"
                     "4295367296 0 0 0 0 0 100 100 0 23\n0\n\n#$\n",
                     "Fread_number: number out of range.")             # a shop's keeper
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#SPECIALS\n"
                     "M 4295367296 spec_cast_mage\nS\n\n#$\n",
                     "Fread_number: number out of range.")             # a special's mobile
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#MOBILES\n#4295367296\n#0\n\n#$\n",
                     "Fread_number: number out of range.")             # a mobile's record
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#OBJECTS\n#4295367296\n#0\n\n#$\n",
                     "Fread_number: number out of range.")             # an object's record
        self.refused("#AREADATA\nName Too Wide~\nBuilders All~\nVNUMs 940000 4295367296\n"
                     "End\n\n#ROOMS\n#0\n\n#$\n", "Fread_number: number out of range.")
        self.refused("#AREADATA\nName Too Wide~\nBuilders All~\nVNUMs -4295367296 1\n"
                     "End\n\n#ROOMS\n#0\n\n#$\n", "Fread_number: number out of range.")
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#OBJECTS\n"
                     + thing(940000, "9" * 25) + "#0\n\n#$\n",
                     "Fread_long: number out of range.")
        self.refused("#AREA   { ALL } Tests   Number Overflow~\n\n#OBJECTS\n"
                     + thing(940000, "10", "4294967296") + "#0\n\n#$\n",
                     "Fread_flag: number out of range.")
        # The largest numbers that fit still read: a long cost, an int flag.
        code, out = self.check("#AREA   { ALL } Tests   Number Overflow~\n\n#OBJECTS\n"
                               + thing(940000, "9223372036854775807", "2147483647")
                               + "#0\n\n#$\n")
        self.assertEqual(code, 0, out[-2000:])


@unittest.skipIf(SKIP is not None, SKIP or "")
class PlayerFileNumberOverflowTests(unittest.TestCase):
    """A player file's number past int refuses that character, and the
    file is left exactly as it is; it used to wrap into the field."""

    def test_an_overflowing_number_refuses_the_character_not_the_game(self) -> None:
        with LiveMud() as mud:
            # Vnum fields too: a Room that wrapped to 400000 put the
            # character in Limbo, and an object's Vnum read a stranger's.
            for name, key, value in (("Zbigroom", "Room", "4295367296"),
                                     ("Zbigrecall", "RecallRoom", "2147483648")):
                with mud.connect() as client:
                    create_character(client, name, "Zbignumpw1")
                    client.send("quit")
                    self.assertTrue(client.wait_closed(30))
                path = mud.player_dir / name
                path.write_text(path.read_text(encoding="latin-1").replace(
                    "\nEnd\n", f"\n{key} {value}\nEnd\n", 1), encoding="latin-1", newline="")
            with mud.connect() as client:
                create_character(client, "Zbigobj", "Zbignumpw1")
                client.send("quit")
                self.assertTrue(client.wait_closed(30))
            path = mud.player_dir / "Zbigobj"
            path.write_text(path.read_text(encoding="latin-1").replace(
                "#END", "#O\nVnum 4295367296\nNest 0\nWear -1\nEnd\n\n#END", 1),
                encoding="latin-1", newline="")
            for name in ("Zbigroom", "Zbigrecall", "Zbigobj"):
                before = (mud.player_dir / name).read_bytes()
                with mud.connect() as client:
                    client.expect("by what name", "name:")
                    client.send(name)
                    client.expect("could not be read", timeout=30)
                    self.assertTrue(client.wait_closed(30))
                self.assertEqual((mud.player_dir / name).read_bytes(), before, name)
            for name in ("Zbignum", "Zgoodnum"):
                with mud.connect() as client:
                    create_character(client, name, "Zbignumpw1")
                    client.sync("save")
                    client.send("quit")
                    self.assertTrue(client.wait_closed(30))
            path = mud.player_dir / "Zbignum"
            text = path.read_text(encoding="latin-1")
            text, n = re.subn(r"(?m)^Prac \d+$", "Prac 4294967301", text)
            self.assertEqual(n, 1)
            path.write_text(text, encoding="latin-1", newline="")
            before = path.read_bytes()

            with mud.connect() as client:
                client.expect("by what name", "name:")
                client.send("Zbignum")
                client.expect("could not be read", timeout=30)
                self.assertTrue(client.wait_closed(30))
            self.assertIsNone(mud.proc.poll(), "the game exited")
            self.assertEqual(path.read_bytes(), before, "the file was changed")
            with mud.connect() as client:
                login(client, "Zgoodnum", "Zbignumpw1")
                client.must("look", "")
                client.send("quit")
                client.wait_closed(30)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Fread_number: number out of range.", log)
            self.assertIn("Zbignum's file has a malformed value", log)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashScanOverflowTests(unittest.TestCase):
    """PRESTORE ... STASH reads a snapshot's section aside, and first scans
    it so the reader never meets a malformed number with no trap to catch
    it (that exits the game). The scan has to refuse what the reader now
    refuses: an overflowing Vnum, or a Cost past a long."""

    def test_an_overflowing_snapshot_is_refused_and_the_game_lives(self) -> None:
        stashes = {
            "20260201_000000": obj(PLAIN) + "#O\nVnum 4295367296\nNest 0\nWear -1\nEnd\n\n#END\n",
            "20260202_000000": obj(PLAIN, extra="Cost 99999999999999999999\n") + "#END\n",
            "20260203_000000": obj(PLAIN, extra="Time 2147483648\n") + "#END\n",
            # The largest that fit are read.
            "20260204_000000": obj(PLAIN, extra="Cost 9223372036854775807\n") + "#END\n",
        }
        with LiveMud() as mud:
            make(mud, "Zarchon", "Zvictim")
            patch_player_file(mud, "Zarchon", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Zvictim", Levl=30, Room=TEMPLE)
            write_snapshots(mud, "Zvictim", stashes)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zarchon", PASSWORD)
                run(staff, "scroll 0", 1.0)
                for stamp in ("20260201_000000", "20260202_000000", "20260203_000000"):
                    reply = run(staff, f"prestore zvictim {stamp} stash", 2.5)
                    self.assertIsNone(mud.proc.poll(),
                                      f"{stamp} took the game down:\n" + mud.server_output())
                    self.assertIn("Nothing was restored", reply, reply)
                    self.assertEqual(stash_vnums(mud, "Zvictim"), [], stamp)
                reply = run(staff, "prestore zvictim 20260204_000000 stash", 2.5)
                self.assertIn("Restored 1 object", reply, reply)
            self.assertEqual(stash_vnums(mud, "Zvictim"), [str(PLAIN)])


if __name__ == "__main__":
    unittest.main()
