"""An offline sentence moves the saved room, and so does an offline release
(review, 2026-11-13).

JAIL of somebody who is not in the game loads a copy of them
(offline_player_load), which is never put in a room's list of people: it
has in_room pointing at the room the file named and nothing else. The
jail saved that copy with its old room, and an offline release saved it
again with the same room -- so a player jailed and released while away
logged in where they had stood before the sentence, not at the Temple
where every release lands. jail_login_place only rescues a free
character saved in the cell.

Both paths are played here across restarts, reading the file's own Room
line and the first room the player is shown:

  jail offline -> restart -> release offline -> restart -> login: Temple
  jail offline -> restart -> the term runs out -> restart -> login: Temple

and neither copy may be placed in a room's list of people (area player
counts), which the source check holds.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zjailpw12"
CELL = 3
TEMPLE = 4207
SQUARE = 2401
PLR_JAILED = 1 << 29


def make(mud: LiveMud, name: str, level: int, room: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Levl=level, Room=room)


def field(mud: LiveMud, name: str, key: str) -> str | None:
    for line in (mud.player_dir / name).read_text(encoding="latin-1").split("\n"):
        if line.split(" ")[0] == key:
            return line[len(key):].strip()
    return None


def saved_room(mud: LiveMud, name: str) -> int:
    return int(field(mud, name, "Room") or 0)


def jailed(mud: LiveMud, name: str) -> bool:
    return bool(int(field(mud, name, "Act") or 0) & PLR_JAILED)


def booted(mud: LiveMud) -> None:
    with mud.connect(timeout=120) as probe:
        probe.expect("by what name", "name:")


def first_room_shown(transcript: str) -> str:
    """Which of the rooms in question the login showed first, by name."""
    names = {"Before the Altar.": TEMPLE, "Center of Oak Tree Square.": SQUARE}
    seen = [(transcript.find(name), name) for name in names if name in transcript]
    return min(seen)[1] if seen else ""


class OfflinePlacementSourceTests(unittest.TestCase):
    def test_no_offline_copy_enters_a_room_list(self) -> None:
        """The offline copies are moved by pointer only: char_to_room would
        add them to the room's people and the area's player count."""
        source = (ROOT / "src" / "jail.c").read_text(encoding="latin-1")
        body = source[source.index("static void jail_offline_place"):]
        body = body[:body.index("\n}\n")]
        self.assertNotIn("char_to_room", body)
        self.assertNotIn("char_from_room", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class OfflineSentenceRoomTests(unittest.TestCase):
    def test_offline_jail_then_offline_release_lands_at_the_temple(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70, TEMPLE)
            make(mud, "Zoffrel", 20, SQUARE)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                self.assertIn("(offline; saved)", warden.sync("jail zoffrel 1d"))
                warden.send("quit")
                warden.wait_closed()
            self.assertTrue(jailed(mud, "Zoffrel"))
            self.assertEqual(CELL, saved_room(mud, "Zoffrel"), "the sentence's saved room")

            mud.restart()
            booted(mud)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                self.assertIn("(offline)", warden.sync("jail zoffrel status"))
                self.assertIn("released from jail (offline; saved)",
                              warden.sync("jail zoffrel release"))
                warden.send("quit")
                warden.wait_closed()
            self.assertFalse(jailed(mud, "Zoffrel"))
            self.assertEqual(TEMPLE, saved_room(mud, "Zoffrel"), "the release's saved room")

            mud.restart()
            booted(mud)
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as freed:
                login(warden, "Zwarden", PW)
                login(freed, "Zoffrel", PW)
                self.assertEqual("Before the Altar.", first_room_shown(freed.transcript),
                                 freed.transcript[-1500:])
                self.assertEqual(TEMPLE, room_of(warden, "Zoffrel"))

    def test_offline_jail_then_expiry_while_away_lands_at_the_temple(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70, TEMPLE)
            make(mud, "Zoffexp", 20, SQUARE)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                self.assertIn("(offline; saved)", warden.sync("jail zoffexp 1d"))
                warden.send("quit")
                warden.wait_closed()
            self.assertEqual(CELL, saved_room(mud, "Zoffexp"))

            mud.restart()
            booted(mud)
            # The term runs out while nobody is about, and the game restarts.
            patch_player_file(mud, "Zoffexp", Jw_Timer=int(time.time()) - 60)
            mud.restart()
            booted(mud)
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as freed:
                login(warden, "Zwarden", PW)
                login(freed, "Zoffexp", PW)
                self.assertIn("Your sentence has been served", freed.transcript)
                self.assertEqual("Before the Altar.", first_room_shown(freed.transcript),
                                 freed.transcript[-1500:])
                self.assertEqual(TEMPLE, room_of(warden, "Zoffexp"))
                self.assertFalse(jailed(mud, "Zoffexp"))
                # The release is saved from the cell and then moves them, as
                # an online one does (jail_release_move); the quit's save
                # records the Temple.
                freed.send("quit")
                self.assertTrue(freed.wait_closed())
            self.assertEqual(TEMPLE, saved_room(mud, "Zoffexp"))


if __name__ == "__main__":
    unittest.main()
