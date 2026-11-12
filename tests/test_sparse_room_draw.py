"""A random room is drawn from the rooms there are, not guessed by vnum
(review, 2026-11-12).

TELEPORT and get_random_room (a recall misfire, FLING) asked
random_room_candidate for a room two hundred times, and it guessed a vnum
between 0 and top_vnum_room; a random portal (value[0] 1) did the same
when made and at the turn of the hour. Vnums are sparse: one area with a
room at 1,000,000 leaves the world's 7,767 rooms about one guess in 129,
so all two hundred missed about one time in five -- TELEPORT fizzled, a
misfire fell back to the Temple and a portal kept no destination, although
nearly every room was eligible. Now TELEPORT and get_random_room draw from
db.c's list of every world room (random_room_index), each equally likely
as before, and a portal picks among the rooms it may open on
(random_room_where).

The live test boots a world holding one more area, a single room at
1,000,000 (MAX_VNUM), and asks for thirty teleports, thirty throws and
thirty random portals: none may fizzle, fall back or open on nothing. On
the old binary 4 teleports and 11 throws of 30 did.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      room_of, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zsparsepass11"
FAR = 1000000          # MAX_VNUM: the highest a room may be numbered
RANDOM_PORTAL = 26     # limbo.are: a portal whose value[0] 1 opens anywhere
AREA_NAME = "zsparsefar.are"
TEMPLE = 4207
TRIES = 30

AREA = (
    "#AREA   { ALL } Tests   Sparse Far Room~\n\n#ROOMS\n"
    f"#{FAR}\nThe Far Sparse Room~\nA bare test room at the top of the vnums.\n~\n"
    "0 D 0\nS\n#0\n\n#$\n"
)


def add_built_area(area_dir: Path, name: str, text: str) -> None:
    """List an area file in area/built/, as tests/test_wide_vnums.py does."""
    built = area_dir / "built"
    built.mkdir(exist_ok=True)
    (built / name).write_bytes(text.encode("latin-1"))
    listing = built / "built.lst"
    lines = [line for line in (listing.read_text().split() if listing.exists() else [])
             if line != "$"]
    lines.append(f"built/{name}")
    listing.write_text("\n".join(lines + ["$"]) + "\n")


class SparseMud(LiveMud):
    """A test world with one room at 999,999, listed before the first boot."""

    def _launch(self) -> None:
        assert self.root is not None
        area = self.root / "area"
        if not (area / "built" / AREA_NAME).exists():
            add_built_area(area, AREA_NAME, AREA)
        super()._launch()


class SparseDrawSourceTests(unittest.TestCase):
    def test_every_random_pick_draws_from_the_rooms_there_are(self) -> None:
        for path in sorted((ROOT / "src").glob("*.c")):
            code = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="latin-1"), flags=re.S)
            self.assertNotRegex(code, r"get_(room|mob|obj)_index\(\s*number_range\(",
                                path.name)
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        candidate = move.split("ROOM_INDEX_DATA *random_room_candidate( int attempt )", 1)[1]
        candidate = candidate.split("\n}\n", 1)[0]
        self.assertIn('getenv( "TOC_RANDOM_ROOM" )', candidate)
        self.assertIn("return random_room_index( );", candidate)
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        # The random portals choose among eligible rooms, with no retry cap.
        self.assertIn("random_room_where( random_portal_room_ok )", db)
        self.assertIn("random_room_where( portal_shift_room_ok )", update)
        for text in (db, update):
            self.assertNotRegex(text, r"to_room = random_room_index")
        # Every way a world room or a mobile prototype enters its hash puts
        # it in the list too, and a freed room leaves it.
        self.assertEqual(len(re.findall(r"room_index_hash\[iHash\]\s*=", db)), 1)
        self.assertEqual(len(re.findall(r"mob_index_hash\[iHash\]\s*=", db)), 1)
        self.assertGreaterEqual(db.count("room_index_link( pRoomIndex );"), 2)
        self.assertGreaterEqual(db.count("mob_index_link("), 3)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        extract = handler.split("void extract_room( ROOM_INDEX_DATA *pRoom )", 1)[1]
        extract = extract.split("\n}\n", 1)[0]
        self.assertLess(extract.index("room_index_forget( pRoom );"), extract.index("free_mem("))


@unittest.skipIf(SKIP is not None, SKIP or "")
class SparseDrawLiveTests(unittest.TestCase):
    def make(self, mud: LiveMud, name: str, **fields: object) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PW)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, name, **fields)

    def test_teleport_and_a_throw_never_miss_for_want_of_a_room(self) -> None:
        hearty = dict(HMV="30000 30000 30000 30000 1000 1000", HMVP="30000 30000 1000")
        with SparseMud() as mud:
            self.make(mud, "Zsparstaff", Levl=70, Room=TEMPLE, **hearty)
            self.make(mud, "Zsparthrown", Levl=70, Room=TEMPLE, **hearty)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as thrown:
                login(staff, "Zsparstaff", PW)
                login(thrown, "Zsparthrown", PW)
                for client in (staff, thrown):
                    client.sync("scroll 0")
                # The far room is there, past every other vnum.
                staff.must(f"stat room {FAR}", f"Vnum: {FAR}")
                staff.must("set skill zsparstaff teleport 100", "")

                # A random portal opens on a room whenever it is made.
                staff.must(f"goto {FAR}", "Far Sparse Room")
                unset = []
                for i in range(TRIES):
                    staff.must(f"load obj {RANDOM_PORTAL}", "You create")
                    values = staff.must("stat obj portal", "Values:")
                    target = int(re.search(r"Values: -?\d+ (-?\d+)", values).group(1))
                    if target <= 0 or "Vnum:" not in staff.sync(f"stat room {target}"):
                        unset.append(target)
                    staff.must("purge portal", "")
                staff.must(f"goto {TEMPLE}", "")

                fizzled = []
                for i in range(TRIES):
                    staff.must("restore zsparstaff", "")
                    reply = staff.sync("cast teleport zsparstaff", timeout=30)
                    if "fizzles" in reply or "You failed" in reply:
                        fizzled.append(reply[:200])

                temple = 0
                for i in range(TRIES):
                    staff.must(f"transfer zsparthrown {TEMPLE}", "")
                    staff.must("fling zsparthrown", "hurl")
                    if room_of(staff, "zsparthrown") == TEMPLE:
                        temple += 1
                for client in (staff, thrown):
                    client.send("quit")
                    client.wait_closed()
        # The Temple may be drawn as any room may, once in thousands;
        # falling back to it was about one throw in four.
        summary = (f"{len(fizzled)} of {TRIES} teleports fizzled, {temple} of {TRIES} "
                   f"throws fell back to the Temple, {len(unset)} of {TRIES} portals "
                   f"opened on nothing")
        self.assertEqual(unset, [], summary)
        self.assertEqual(len(fizzled), 0, summary + "\n" + "\n".join(fizzled[:2]))
        self.assertLessEqual(temple, 1, summary)


if __name__ == "__main__":
    unittest.main()
