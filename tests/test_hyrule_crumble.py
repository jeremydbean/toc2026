"""A Hyrule dungeon's own things crumble once it is left (owner,
2026-11-12: "once you leave a dungeon in hyrule, the items that are used
only in that dungeon, like small keys and compass and map once used should
crumble. i don't want a players inventory cluttered with items that are
useless after a dungeon run").

What crumbles (src/hyrule.c, crumble_kind): the dungeon's map and
compass, the dungeons' own small keys (object 30227, laid only inside
dungeons), and a guardian's key once its chest has given its holder the
prize. Never the two small keys Hyrule's shops sell, a progression tool,
a piece, gear or anything else; never the stash or the floor; never an
immortal's. It is checked once a pulse against where the character was at
the last check, so any way out counts -- a walk, a transfer, recall, a
death -- while a move that comes straight back (SCAN, AT, the idle void)
counts for nothing. What a map taught stays: the dungeon is still on the
client's map (Map.Known), and the plan is sent again on the next visit.

A login fix (20261112-hyrule-crumble) clears what characters carried out
of a dungeon before this.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from live_mud import (IAC, DO, TELOPT_GMCP, LiveMud, create_character, login,
                      patch_player_file, room_of, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zcrumblepw1"
TEMPLE = 4207
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DUNGEONS = {d["level"]: d for d in MANIFEST["dungeons"]}
ENTRANCE = 30401                # Level 1's entrance; UP is the overworld
MAP1, COMPASS1, MAP2 = 30480, 30489, 30481
SMALL_KEY, SHOP_KEY = 30227, 30545
BOOMERANG = 30232               # a progression tool: never crumbles
EAGLE_KEY, FIRST_PIECE = 30630, 30400
BAG = 3032
FIX_ID = "20261112-hyrule-crumble"


def obj(vnum: int, nest: int = 0) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nEnd\n\n" % (vnum, nest)


def make(mud: LiveMud, name: str, room: int, objects: str = "", level: int = 10,
         owe_fix: bool = False) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=room, AfBy=512,
                      HMV="2000 2000 1000 1000 1000 1000", HMVP="2000 1000 1000")
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if owe_fix:
        # A fixture is a new character, born with every fix marked done;
        # an old file from before the crumbling is owed this one.
        text, n = re.subn(r"(?m)^(Fixes .*?) ?%s(.*~)$" % re.escape(FIX_ID), r"\1\2", text)
        assert n == 1, "the fixture was not marked with the fix"
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def play_rows(mud: LiveMud, name: str) -> list[str]:
    path = mud.root / "log" / "play.tsv"
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="latin-1").splitlines()
            if f"\titem\t{name}\t" in line]


def hyrule_rows(mud: LiveMud, name: str) -> list[dict]:
    path = mud.root / "log" / "hyrule.tsv"
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="latin-1").splitlines():
        cols = line.split("\t")
        if len(cols) < 8 or cols[1] != "crumbled" or cols[2] != name:
            continue
        row = {"zone": cols[7]}
        for word in " ".join(cols[8:]).split():
            key, _, value = word.partition("=")
            row[key] = value
        out.append(row)
    return out


class SourceTests(unittest.TestCase):
    def test_wired_once_a_pulse_and_never_in_char_to_room(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertIn("hyrule_crumble_update( );", update)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        to_room = handler.split("void char_to_room(", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("crumble", to_room)
        # The trips there and back count as the room they left.
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        zone = hyrule.split("static int crumble_zone(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("was_in_room", zone)
        self.assertIn("oracle_saved_room( ch )", zone)

    def test_tools_shop_keys_and_prizes_are_never_dungeon_only(self) -> None:
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        kind = hyrule.split("static int crumble_kind(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("HYRULE_SMALL_KEY", kind)
        self.assertNotIn("SHOP_KEY", kind)
        self.assertNotIn("hyrule_progression_tool", kind)
        self.assertIn("holds_chest_prize", kind)
        # Every small key the area lays lies inside a dungeon: that is what
        # makes one carried outside a leftover.
        area = (ROOT / "area" / "hyrule.are").read_text(encoding="latin-1")
        rooms = {int(m.group(1)) for m in re.finditer(r"(?m)^O \d+ %d \d+ (\d+)" % SMALL_KEY, area)}
        self.assertTrue(rooms)
        ranges = [(d["first_room_vnum"], d["last_room_vnum"]) for d in DUNGEONS.values()]
        for room in rooms:
            self.assertTrue(any(a <= room <= b for a, b in ranges), room)

    def test_the_report_counts_what_crumbled(self) -> None:
        import sys
        from datetime import datetime, timezone
        sys.path.insert(0, str(ROOT / "tools"))
        import log_report
        text = "\n".join([
            "1794300000\tcrumbled\tZed\t10\t0\tWar\t30271\tover\tdungeon=1 maps=1"
            " compasses=1 keys=3 guardian_keys=0 why=left how=up",
            "1794300100\tcrumbled\tZed\t10\t0\tWar\t4207\tout\tdungeon=0 maps=2"
            " compasses=0 keys=1 guardian_keys=0 why=stray how=-",
        ])
        rows = log_report.hyrule_rows(text, datetime(2026, 1, 1, tzinfo=timezone.utc))
        crumbled = log_report.hyrule_summary(rows)["crumbled"]
        self.assertEqual(crumbled[("L1", "keys")], 3)
        self.assertEqual(crumbled[("stray", "maps")], 2)

    def test_the_fix_is_registered(self) -> None:
        fixes = (ROOT / "src" / "fixes.c").read_text(encoding="latin-1")
        self.assertIn('"%s"' % FIX_ID, fixes)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_leaving_a_dungeon_crumbles_its_own_things(self) -> None:
        # The Eagle's key with no piece yet: unspent, so it is kept.
        pack = (obj(MAP1) + obj(COMPASS1) + obj(SMALL_KEY) + obj(SMALL_KEY)
                + obj(SHOP_KEY) + obj(BOOMERANG) + obj(EAGLE_KEY)
                + obj(BAG) + obj(SMALL_KEY, 1))
        with LiveMud() as mud:
            make(mud, "Zkeeper", TEMPLE, level=70)
            make(mud, "Zwalker", ENTRANCE, pack)
            # The Eagle's key with the piece it opens the chest for: spent.
            make(mud, "Zcarried", ENTRANCE, obj(COMPASS1) + obj(SMALL_KEY)
                 + obj(EAGLE_KEY) + obj(FIRST_PIECE))
            make(mud, "Zstray", TEMPLE, obj(MAP1) + obj(MAP2) + obj(SMALL_KEY) + obj(SHOP_KEY),
                 owe_fix=True)
            make(mud, "Zinside", ENTRANCE, obj(MAP1) + obj(MAP2) + obj(SMALL_KEY), owe_fix=True)

            staff = mud.connect(timeout=120)
            login(staff, "Zkeeper", PW)
            staff.sync("scroll 0")

            # --- walking out --------------------------------------------
            walker = mud.connect(timeout=120)
            walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
            login(walker, "Zwalker", PW)
            walker.sync("scroll 0")
            self.assertNotIn("crumbles", walker.transcript, "nothing goes at a login inside")
            # SCAN steps into the overworld and straight back: nothing goes.
            walker.sync("scan")
            held = walker.sync("inventory")
            self.assertIn("Eagle dungeon map", held)
            self.assertIn("Eagle dungeon compass", held)
            said = walker.sync("up")
            self.assertIn("As you leave Level 1 (The Eagle)", said)
            self.assertIn("crumbles to dust", said)
            self.assertIn("the Eagle dungeon map", said)
            self.assertIn("a small key (3)", said, "both keys in the pack and the one in the bag")
            self.assertIn("still on your map", said)
            held = walker.sync("inventory")
            self.assertNotIn("dungeon map", held)
            self.assertNotIn("dungeon compass", held)
            self.assertIn("a small key", held, "the shop's key is kept")
            self.assertIn("boomerang", held.lower(), "a progression tool is kept")
            self.assertIn("the Eagle's key", held, "an unspent guardian's key is kept")
            inside = walker.sync("look in bag")
            self.assertNotIn("small key", inside)
            self.assertIn("Hyrule dungeon maps: 1", walker.sync("maps"))
            # Walking back in brings nothing back, and takes nothing more.
            again = walker.sync("down")
            self.assertNotIn("crumbles", again)
            self.assertEqual(room_of(staff, "zwalker"), ENTRANCE)

            rows = hyrule_rows(mud, "Zwalker")
            self.assertEqual(len(rows), 1, rows)
            self.assertEqual((rows[0]["dungeon"], rows[0]["maps"], rows[0]["compasses"],
                              rows[0]["keys"], rows[0]["why"]), ("1", "1", "1", "3", "left"))
            items = play_rows(mud, "Zwalker")
            gone = [line for line in items if "crumbled leaving Level 1" in line]
            self.assertEqual(len(gone), 5, items)
            self.assertFalse([line for line in gone if "\t%d\t" % SHOP_KEY in line])
            walker.send("quit")
            walker.wait_closed(10)

            # What the map taught stays: a fresh login's Map.Known still
            # names the whole of Level 1.
            walker = mud.connect(timeout=120)
            walker.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
            login(walker, "Zwalker", PW)
            walker.sync("scroll 0")
            blocks = [b.decode("latin-1") for b in walker.subnegotiations(TELOPT_GMCP)]
            known = [json.loads(b.split(" ", 1)[1]) for b in blocks if b.startswith("Map.Known ")]
            self.assertTrue(known, "no Map.Known at login")
            runs = [run for part in known for run in part["rooms"]]
            level1 = DUNGEONS[1]
            for vnum in (level1["entrance_vnum"], level1["last_room_vnum"]):
                self.assertTrue(any(a <= vnum <= b for a, b in runs), vnum)
            # ... and being in the dungeon again (the walk back in above
            # left Zwalker there) draws its plan, with no map held.
            self.assertNotIn("dungeon map", walker.sync("inventory"))
            self.assertTrue([b for b in blocks if b.startswith("Hyrule.MapDone ")],
                            [b[:60] for b in blocks])
            walker.send("quit")
            walker.wait_closed(10)

            # --- carried out, with nothing typed ------------------------
            carried = mud.connect(timeout=120)
            login(carried, "Zcarried", PW)
            carried.sync("scroll 0")
            staff.must("transfer zcarried %d" % TEMPLE, "")
            held = carried.sync("inventory")
            self.assertIn("As you leave Level 1 (The Eagle)", carried.transcript)
            self.assertNotIn("dungeon compass", held)
            self.assertNotIn("small key", held)
            self.assertNotIn("Eagle's key", held, "its chest has given its prize")
            self.assertIn("first Triforce shard", held)
            self.assertIn("nothing left to open", carried.transcript)
            self.assertEqual([r["guardian_keys"] for r in hyrule_rows(mud, "Zcarried")], ["1"])
            carried.send("quit")
            carried.wait_closed(10)

            # --- an immortal keeps what they carry -----------------------
            staff.must("goto %d" % ENTRANCE, "")
            staff.must("load obj %d" % MAP1, "")
            said = staff.sync("up")
            self.assertNotIn("crumbles", said)
            self.assertIn("Eagle dungeon map", staff.sync("inventory"))

            # --- the login fix: leftovers from before --------------------
            stray = mud.connect(timeout=120)
            login(stray, "Zstray", PW)
            stray.sync("scroll 0")
            self.assertIn("What you carry for a Hyrule dungeon you are not in", stray.transcript)
            held = stray.sync("inventory")
            self.assertNotIn("dungeon map", held)
            self.assertIn("a small key", held, "the shop's key is kept")
            self.assertEqual([r["why"] for r in hyrule_rows(mud, "Zstray")], ["stray"])
            stray.send("quit")
            stray.wait_closed(10)
            stray = mud.connect(timeout=120)
            login(stray, "Zstray", PW)
            stray.sync("scroll 0")
            self.assertNotIn("crumbles", stray.transcript, "the fix runs once")
            stray.send("quit")
            stray.wait_closed(10)

            # Inside a dungeon its own things stay; another's map goes.
            inside = mud.connect(timeout=120)
            login(inside, "Zinside", PW)
            inside.sync("scroll 0")
            held = inside.sync("inventory")
            self.assertIn("the Moon dungeon map", inside.transcript)
            self.assertNotIn("Moon dungeon map", held)
            self.assertIn("Eagle dungeon map", held)
            self.assertIn("a small key", held)
            inside.send("quit")
            inside.wait_closed(10)
            staff.send("quit")
            staff.wait_closed(10)


if __name__ == "__main__":
    unittest.main()
