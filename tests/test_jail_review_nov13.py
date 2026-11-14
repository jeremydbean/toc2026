"""Jail findings from the review of 2026-11-13, each played live.

- An immortal switched into a mobile who typed JAIL wrote the mobile's
  keywords into JailInfo ("lieutenant comm"); the loader read "comm" as the
  Comm key and refused the prisoner's file for good. JAIL now acts as the
  immortal's own character, the writer puts only a plain word there, and
  the reader takes the rest of the line as not the record's, which also
  rescues a file written that way before.
- A full PRESTORE to a snapshot from before the sentence ended it, with no
  JAIL RELEASE; one taken during a sentence since released brought it
  back. A restore now keeps the sentence as it stands.
- A prisoner who died in the cell and was then released left the corpse,
  and everything in it, in a cell nothing reaches. It goes to the Temple
  with them.
"""
from __future__ import annotations

import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
PW = "Zjailpw12"
CELL = 3
TEMPLE = 4207
PLR_JAILED = 1 << 29
COMM_NOCHANNELS = 1 << 22
COMM_NOTITLE = 1 << 26
BEFORE = "20260101_000000"


def make(mud: LiveMud, name: str, level: int, room: int = TEMPLE, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Levl=level, Room=room, **fields)


def text(mud: LiveMud, name: str) -> str:
    return (mud.player_dir / name).read_text(encoding="latin-1")


def field(mud: LiveMud, name: str, key: str) -> str | None:
    for line in text(mud, name).split("\n"):
        if line.split(" ")[0] == key:
            return line[len(key):].strip()
    return None


def number(mud: LiveMud, name: str, key: str) -> int:
    value = field(mud, name, key)
    return int(value) if value is not None else 0


def quit_client(client) -> None:
    client.send("quit")
    assert client.wait_closed()


def snapshot_now(mud: LiveMud, name: str, stamp: str) -> None:
    versions = mud.player_dir / "versions" / name
    versions.mkdir(parents=True, exist_ok=True)
    (versions / f"{name}.{stamp}").write_text(text(mud, name), encoding="latin-1")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SwitchedStaffJailTests(unittest.TestCase):
    def test_a_switched_immortal_jails_as_themselves(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zkept", 20)
            make(mud, "Zold", 20)
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as kept:
                login(warden, "Zwarden", PW)
                login(kept, "Zkept", PW)
                warden.must("load mob 13202", "You create")
                warden.must("switch lieutenant", "Possessed", "possess")
                warden.must("jail zkept 2h", "now in jail")
                self.assertTrue(field(mud, "Zkept", "JailInfo").endswith(" Zwarden"),
                                field(mud, "Zkept", "JailInfo"))
                self.assertIn("term set by Zwarden", warden.sync("jail zkept status"))
                warden.sync("return")
                quit_client(kept)
            # A file an older build wrote that way still loads.
            patch_player_file(mud, "Zold", Act=PLR_JAILED,
                              Jw_Timer=-1, JailInfo="1794600000 3 lieutenant comm")
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as kept, \
                    mud.connect(timeout=120) as old:
                login(warden, "Zwarden", PW)
                login(kept, "Zkept", PW)
                self.assertEqual(CELL, room_of(warden, "Zkept"))
                login(old, "Zold", PW)
                self.assertEqual(CELL, room_of(warden, "Zold"))
                self.assertIn("term set by lieutenant", warden.sync("jail zold status"))
                quit_client(old)
            # Saved again as three fields: what can be read back of it.
            self.assertEqual("1794600000 3 lieutenant", field(mud, "Zold", "JailInfo"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PrestoreKeepsTheSentenceTests(unittest.TestCase):
    def test_a_restore_neither_ends_nor_brings_back_a_sentence(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zkept", 20)
            make(mud, "Zfreed", 20)
            snapshot_now(mud, "Zkept", BEFORE)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                # Jailed now; restored to a copy from before the sentence.
                warden.must("jail zkept indefinite", "in jail")
                warden.sync(f"prestore zkept {BEFORE}", timeout=30)
                self.assertTrue(number(mud, "Zkept", "Act") & PLR_JAILED, "freed by a restore")
                self.assertEqual("-1", field(mud, "Zkept", "Jw_Timer"))
                self.assertIsNotNone(field(mud, "Zkept", "JailInfo"))
                comm = number(mud, "Zkept", "Comm")
                self.assertTrue(comm & COMM_NOCHANNELS and comm & COMM_NOTITLE, comm)
                with mud.connect(timeout=120) as kept:
                    login(kept, "Zkept", PW)
                    self.assertEqual(CELL, room_of(warden, "Zkept"))
                    quit_client(kept)

                # Free now; restored to a copy taken during a sentence.
                warden.must("jail zfreed 2h", "in jail")
                snapshot_now(mud, "Zfreed", BEFORE)
                warden.must("jail zfreed release", "released")
                warden.sync(f"prestore zfreed {BEFORE}", timeout=30)
                self.assertFalse(number(mud, "Zfreed", "Act") & PLR_JAILED, "jailed again")
                self.assertEqual("0", field(mud, "Zfreed", "Jw_Timer"))
                self.assertIsNone(field(mud, "Zfreed", "JailInfo"))
                comm = number(mud, "Zfreed", "Comm")
                self.assertFalse(comm & (COMM_NOCHANNELS | COMM_NOTITLE), comm)
                with mud.connect(timeout=120) as freed:
                    login(freed, "Zfreed", PW)
                    self.assertEqual(TEMPLE, room_of(warden, "Zfreed"))
                    quit_client(freed)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseLeavesTheCellTests(unittest.TestCase):
    def test_a_release_takes_the_corpse_out_too(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zkept", 20)
            make(mud, "Zgone", 20)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                for name in ("zkept", "zgone"):
                    with mud.connect(timeout=120) as kept:
                        login(kept, name.capitalize(), PW)
                        warden.must(f"jail {name} 1d", "in jail")
                        warden.sync("goto 3")
                        warden.must("load obj 3715", "You create")
                        warden.must(f"give diploma {name}", "You give")
                        warden.sync(f"slay {name}")
                        warden.sync("goto 4207")
                        quit_client(kept)
                # The term runs out while away: released at login.
                patch_player_file(mud, "Zkept", Jw_Timer=int(time.time()) - 60)
                with mud.connect(timeout=120) as kept:
                    login(kept, "Zkept", PW)
                    self.assertIn("served", kept.transcript)
                    self.assertEqual(TEMPLE, room_of(warden, "Zkept"))
                    self.assertIn("corpse of Zkept", kept.sync("look"))
                    kept.must("get all corpse", "diploma")
                    quit_client(kept)
                # Released offline by staff.
                warden.must("jail zgone release", "released")
                look = warden.sync("look")
                self.assertIn("corpse of Zgone", look)
                warden.sync("goto 3")
                self.assertNotIn("corpse of", warden.sync("look"))


if __name__ == "__main__":
    unittest.main()
