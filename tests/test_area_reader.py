"""One reader for area files, and the tools that share it.

webadmin/area_reader.py reads a .are file the way src/db.c does -- a token
stream, not lines -- and every Python tool that looks inside one goes
through it. The tools used to read the files several ways each, and the
ways disagreed: the directions router missed "D 0" and lost 176 resets to
a cleanup, the price converter stopped at a '#' inside an extra
description, and the dashboard parser lost affects in double-spaced files.

These tests pin the reader against the game's own readers, pin what the
shared reading fixed in the shipped world, and fail on a tool that grows
a reader of its own. They read files only; no server is booted.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from webadmin import area_reader as ar  # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402


MOBILE = """#MOBILES
#100
guard~
a guard~
A guard stands here.
~
~
human~
ABMTVZ C 0 0 S
23 10 1d1 +999 1d1+99 1d8+32 17
-15 -15 -15 -15
DEIJLNRZ AB AB Q JN
8 8 1 5000
0 0 M 0
#0
"""

OBJECTS = """#OBJECTS
#200

ring opal~

an opal ring~

A ring of black opal lies here.~

stone~

9 G AB

4 4 5 0 0

7 1 36000 P

E

ring opal~

It is a full circle of opal.

# a row that starts with a hash
~

A

19 2

#201
pool~
a pool~
A pool.~
stone~
30 VZ I 0
5 13401 0 0 0
1 1 2 P
#0
"""

ROOMS = """#ROOMS
#300
This room is full of water. There must be some kind of force field
here keeping it from leaking out the entrances.~
Water fills every inch of this chamber.
~
99 DNQ 8
D2
too dark to tell
~
~
0 -1 301
D3 too dark to tell
~
~
1 -1 302
D 1
~
door~
1 7 303
S
#301 The Same-Line Room~
A room named on its header line.~
99 0|8 0|11
S
#0
"""


class TokenReaderTests(unittest.TestCase):
    def test_numbers_add_up_a_pipe(self) -> None:
        self.assertEqual(ar.TokenReader("0|11").number(), 11)
        self.assertEqual(ar.TokenReader(" -5 ").number(), -5)

    def test_a_flag_reads_no_sign(self) -> None:
        """fread_flag on "-1" consumes nothing and returns 0; the next
        reader takes the -1."""
        reader = ar.TokenReader("-1 7")
        flag = reader.flag_token()
        self.assertEqual((flag.value, flag.text), (0, ""))
        self.assertEqual(reader.number(), -1)

    def test_flags_are_letters_then_digits(self) -> None:
        self.assertEqual(ar.TokenReader("DI").flag(), (1 << 3) | (1 << 8))
        self.assertEqual(ar.TokenReader("8|4096").flag(), 4104)
        self.assertEqual(ar.TokenReader("a").flag(), 1 << 26)

    def test_a_string_skips_leading_space_and_drops_carriage_returns(self) -> None:
        self.assertEqual(ar.TokenReader("  \r\n  two\r\nlines~").string(),
                         "two\nlines")

    def test_only_c_whitespace_separates_tokens(self) -> None:
        # A no-break space is not isspace() in the C locale.
        self.assertEqual(ar.TokenReader("ab\xa0cd ef").raw_token().text, "ab\xa0cd")


class RecordShapeTests(unittest.TestCase):
    def test_a_flags2_word_comes_before_the_next_field(self) -> None:
        mob = ar.parse_section_text(MOBILE, "MOBILES").mobiles[0]
        self.assertEqual(mob.act.text, "ABMTVZ")
        self.assertEqual(mob.act2.text, "C")
        self.assertEqual(mob.affected.text, "0")
        self.assertEqual(mob.alignment.value, 0)
        self.assertEqual(mob.hit_text, "1d1+999")
        # OFF_FLAGS2: AB is the second offence word, not the immunities.
        self.assertEqual((mob.off2.text, mob.imm.text, mob.res.text, mob.vuln.text),
                         ("AB", "AB", "Q", "JN"))

    def test_a_double_spaced_object_keeps_its_trailers(self) -> None:
        objs = ar.parse_section_text(OBJECTS, "OBJECTS").objects
        self.assertEqual([o.vnum for o in objs], [200, 201])
        ring = objs[0]
        self.assertEqual(ring.affects, [(19, 2)])
        self.assertEqual(ring.extra_descr[0][0], "ring opal")
        self.assertIn("# a row that starts with a hash", ring.extra_descr[0][1])
        self.assertEqual(ring.cost.value, 36000)

    def test_an_extra_flag_word_shifts_the_wear_flags(self) -> None:
        pool = ar.parse_section_text(OBJECTS, "OBJECTS").objects[1]
        self.assertEqual((pool.extra2.text, pool.wear.text), ("I", "0"))
        self.assertEqual([v.value for v in pool.values], [5, 13401, 0, 0, 0])

    def test_every_exit_shape_and_a_name_over_two_lines(self) -> None:
        rooms = ar.parse_section_text(ROOMS, "ROOMS").rooms
        first, second = rooms
        self.assertIn("\nhere keeping it", first.name)
        self.assertEqual(first.sector.value, 8)
        self.assertEqual([(e.door, e.to_room) for e in first.exits],
                         [(2, 301), (3, 302), (1, 303)])
        self.assertEqual(first.exits[1].description, "too dark to tell\n")
        self.assertEqual((first.exits[2].keyword, first.exits[2].key), ("door", 7))
        self.assertEqual(second.name, "The Same-Line Room")
        self.assertEqual((second.flags.value, second.sector.value), (8, 11))

    def test_a_reset_reads_two_arguments_for_g_and_r(self) -> None:
        resets = ar.parse_section_text(
            "#RESETS\nM 0 100 1 300\nG 1 200 5 0\n* a comment\nR 0 300 0 4\nS\n",
            "RESETS").resets
        self.assertEqual([(r.command, r.arg1, r.arg2, r.arg3) for r in resets],
                         [("M", 100, 1, 300), ("G", 200, 5, 0), ("R", 300, 0, 0)])

    def test_offsets_are_offsets_into_the_file(self) -> None:
        """A tool that rewrites one token leaves every other byte alone,
        CRLF line endings included."""
        text = OBJECTS.replace("\n", "\r\n")
        ring = ar.parse_section_text(text, "OBJECTS").objects[0]
        self.assertEqual(text[ring.cost.start:ring.cost.end], "36000")
        rewritten = text[:ring.cost.start] + "3600" + text[ring.cost.end:]
        self.assertEqual(rewritten.count("\r\n"), text.count("\r\n"))
        self.assertEqual(ar.parse_section_text(rewritten, "OBJECTS").objects[0].cost.value, 3600)

    def test_a_malformed_file_is_refused_with_its_line(self) -> None:
        with self.assertRaises(ar.AreaFormatError) as caught:
            ar.parse_area_text("#ROOMS\n#1\nA room~\nIt.~\n0 0 0\nX\n#0\n#$\n", "bad.are")
        self.assertIn("bad.are:6", str(caught.exception))


class ShippedWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.areas = ar.read_world(ROOT / "area")
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_every_file_in_the_area_directory_reads(self) -> None:
        for path in sorted((ROOT / "area").glob("*.are")):
            with self.subTest(file=path.name):
                ar.read_area_file(path)

    def test_the_dashboard_parser_holds_exactly_what_was_read(self) -> None:
        self.assertEqual(set(self.parser.rooms),
                         {r.vnum for a in self.areas for r in a.rooms})
        self.assertEqual(set(self.parser.objects),
                         {o.vnum for a in self.areas for o in a.objects})
        self.assertEqual(set(self.parser.mobiles),
                         {m.vnum for a in self.areas for m in a.mobiles})

    def test_what_the_old_readers_missed(self) -> None:
        # D3 with its description on the same line (ag.are).
        self.assertIn((3, 17024), [(e.direction, e.to_room)
                                   for e in self.parser.rooms[17022].exits])
        # A double-spaced object's affect (trollden.are's opal ring).
        self.assertEqual(self.parser.objects[2803].affects,
                         [{"location": 19, "modifier": 2}])
        # A name written over two lines (valhalla.are), and one whose tilde
        # is on the line after it (underdrk.are).
        self.assertEqual(self.parser.rooms[9945].sector_type, "8")
        self.assertEqual(self.parser.rooms[25123].sector_type, "11")

    def test_the_router_reads_only_what_the_game_loads(self) -> None:
        import build_directions as bd

        portals = bd.load_portals(self.areas)
        self.assertIn(13401, [edge[2] for edge in portals.get(9163, [])],
                      "the pool in 9163 is a portal with a second flag word")
        # The Rescue Portal is placed once, by dresden.are: its seasonal
        # copies are not loaded alongside it.
        self.assertEqual(len(portals[2497]), 1)
        # The ten levers in Korzath are placed by korzath2.are, not again
        # by the archived korzath2old.are beside it.
        self.assertEqual(len(portals[29217]), 10)
        links = json.loads((ROOT / "webadmin" / "directions.json")
                           .read_text(encoding="utf-8"))["links"]
        self.assertEqual(
            sum(1 for link in links if link["from"] == 2497), 1,
            "the Rescue Portal is published once, not once per copy of dresden")

    def test_listing_without_built_areas(self) -> None:
        listed = ar.listed_area_files(ROOT / "area", built=False)
        self.assertEqual(listed[0], "commands.are")
        self.assertNotIn(ar.BUILT_AREA_LIST, listed)
        self.assertFalse(any(name.startswith("built/") for name in listed))


class NoSecondReaderTests(unittest.TestCase):
    """A tool that scans an area file's sections with a regex of its own is
    a reader that will drift from this one."""

    # The Hyrule generator rewrites its own output as text (it generates
    # every record it reads back); help has its own reader.
    ALLOWED = {"webadmin/area_reader.py", "scripts/build_hyrule_area.py",
               "webadmin/help_index.py", "tools/help_audit.py"}
    SECTION_REGEX = re.compile(
        r"re\.\w+\(.*#.{0,40}(?:MOBILES|OBJECTS|ROOMS|RESETS|SHOPS|SPECIALS)")

    def test_no_tool_scans_area_sections_itself(self) -> None:
        files = (list((ROOT / "tools").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
                 + list((ROOT / "webadmin").glob("*.py")) + list(ROOT.glob("check_*.py")))
        offenders = []
        for path in files:
            name = path.relative_to(ROOT).as_posix()
            if name in self.ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if self.SECTION_REGEX.search(line):
                    offenders.append(f"{name}:{number}")
        self.assertEqual(offenders, [], "read area files through webadmin/area_reader.py")


if __name__ == "__main__":
    unittest.main()
