"""A guardian's strikers are known by serial, never by the file Id
(review of d19b0e92, 2026-11-12).

A character's Id is number_range( 0, 65535 ), saved and never checked for
uniqueness, and the guardian's striker list held Ids: two ungrouped
characters sharing one, one fighting Aquamentus and one standing idle in
its room, and the idle one was handed the Eagle's key when it fell. The
balance feed (log/progress.tsv) keyed every row by the same Id, so the two
merged into one character in every per-character figure.

Every character now carries a serial (save.c, `Serial` in the file): wide,
checked against every file in player/ and its archive, given at the first
login without one and kept. The striker list, a mobile's hates and the
feed's character column hold it; the Id stays as it is (quest objects are
bound to it), and a new character's is one no other file holds.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason
from test_hyrule_guardian_keys import LAIR, PW, TEMPLE, connect, kill, make, quit_all

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
SHARED_ID = 4321
SERIAL_FIRST = 65536


def file_field(mud: LiveMud, name: str, key: str) -> int | None:
    found = re.search(rf"(?m)^{key} +(-?\d+)$",
                      (mud.player_dir / name).read_text(encoding="latin-1"))
    return int(found.group(1)) if found else None


def boot_finished(mud: LiveMud) -> None:
    """The port opens before boot reads the files; the name prompt is sent
    only by the running game loop, after it has."""
    with mud.connect(timeout=180) as client:
        client.expect("by what name", "name:", "what is your name")


class SerialSourceTests(unittest.TestCase):
    def test_nothing_compares_characters_by_the_file_id(self) -> None:
        hyrule = (ROOT / "src" / "hyrule.c").read_text(encoding="latin-1")
        self.assertNotIn("hyrule_struck[i] == ch->pcdata->id", hyrule)
        self.assertNotIn("= ch->pcdata->id;", hyrule)
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertNotRegex(fight, r"hate->ch\s*(==|=)\s*\w+->pcdata->id")
        playlog = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        raw = playlog.split("static void progress_write_raw(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("player_serial( ch )", raw)
        self.assertNotIn("pcdata->id", raw)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianSerialTests(unittest.TestCase):

    def test_an_idle_bystander_sharing_the_fighters_id_gets_no_key(self) -> None:
        names = ("Zserfight", "Zseridle", "Zsergroup", "Zserrelog")
        with LiveMud() as mud:
            make(mud, "Zserstaff", Levl=70, Room=TEMPLE, AfBy=0)
            for name in names:
                make(mud, name, Levl=58, Room=TEMPLE, Id=SHARED_ID)
            staff, fight, idle, group, relog = connect(mud, "Zserstaff", *names)
            fight.name = "Zserfight"
            try:
                for name in names:
                    staff.must(f"transfer {name.lower()} {LAIR}", "")
                group.must("follow zserfight", "You now follow")
                fight.must("group zsergroup", "")
                staff.must(f"at {LAIR} set char aquamentus hp 30000", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                # One strikes it, stops, quits and comes back before it
                # falls: the serial is saved, so they are still known.
                relog.sync("kill aquamentus", timeout=60)
                relog.drain(3.0)
                staff.must(f"at {LAIR} peace", "")
                relog.send("quit")
                self.assertTrue(relog.wait_closed(30))
                relog = connect(mud, "Zserrelog")[0]
                back = room_of(staff, "zserrelog")
                staff.must(f"at {LAIR} set char aquamentus hp 10", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                fought = kill(staff, fight, "aquamentus", LAIR)
                packs = {c: c.sync("inventory", timeout=60) for c in (fight, idle, group, relog)}
            finally:
                quit_all(fight, idle, group, relog, staff)

            serials = {name: file_field(mud, name, "Serial") for name in names}
            ids = {name: file_field(mud, name, "Id") for name in names}
            rows = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1") \
                if (mud.root / "log" / "progress.tsv").exists() else ""

        self.assertEqual(back, LAIR, "the returning striker is back in the lair")
        self.assertIn("is DEAD", fought, fought)
        self.assertIn("Eagle's key", packs[fight], "the killer")
        self.assertIn("Eagle's key", packs[group], "a grouped member in the room")
        self.assertIn("Eagle's key", packs[relog], "a striker who quit and came back")
        self.assertNotIn("Eagle's key", packs[idle], "an idle bystander sharing the Id")

        # The Id is left as it was; every serial is its own and wide.
        self.assertEqual(set(ids.values()), {SHARED_ID}, ids)
        self.assertTrue(all(s is not None and s >= SERIAL_FIRST for s in serials.values()), serials)
        self.assertEqual(len(set(serials.values())), len(names), serials)

        # The balance feed names each character by serial, never the Id.
        who = {f.split("\t")[2] for f in rows.splitlines()
               if len(f.split("\t")) > 10 and f.split("\t")[0].isdigit()}
        self.assertIn(str(serials["Zserfight"]), who, rows[-2000:])
        self.assertIn(str(serials["Zserrelog"]), who, rows[-2000:])
        self.assertNotIn(str(SHARED_ID), who, rows[-2000:])

    def test_a_serial_two_files_hold_stays_with_one(self) -> None:
        with LiveMud() as mud:
            for name in ("Zsercopya", "Zsercopyb"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed(30))
            first = {name: file_field(mud, name, "Serial") for name in ("Zsercopya", "Zsercopyb")}
            ids = {name: file_field(mud, name, "Id") for name in ("Zsercopya", "Zsercopyb")}
            # A file copied by hand: both hold one serial.
            patch_player_file(mud, "Zsercopyb", Serial=first["Zsercopya"])
            mud.restart()
            boot_finished(mud)
            for name in ("Zsercopya", "Zsercopyb"):
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.must("look", "")
                    client.send("quit")
                    self.assertTrue(client.wait_closed(30))
            after = {name: file_field(mud, name, "Serial") for name in ("Zsercopya", "Zsercopyb")}
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")

        self.assertTrue(all(s is not None and s >= SERIAL_FIRST for s in first.values()), first)
        self.assertNotEqual(first["Zsercopya"], first["Zsercopyb"], "new characters differ")
        self.assertNotEqual(ids["Zsercopya"], ids["Zsercopyb"], "a new character's Id is free")
        self.assertNotEqual(after["Zsercopya"], after["Zsercopyb"], after)
        self.assertIn(first["Zsercopya"], after.values(), "one of them keeps it")
        self.assertIn("is another file's; given", log)


if __name__ == "__main__":
    unittest.main()
