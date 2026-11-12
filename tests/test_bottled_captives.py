"""A creature in a bottle is let out by opening it, never by the bottle
leaving memory (review, 2026-11-12).

An object saved with ``Trap <vnum>`` -- a bottle an H reset filled,
picked up and kept -- makes its creature again each time the file is
read. The copy a name prompt loads, an offline load and a quitting
character's things all leave memory through extract_obj_player, which
called char_from_obj: that set the creature loose in the room the
holder's file named, while the file kept the Trap. Typing the name and
hanging up at the password prompt therefore put one more creature in
the world every time, without the password. Disposal now destroys the
captive (captive_dispose); OPEN, the genie's lever and a bottle that
shatters with age still let it out (char_from_obj).

The sparring guard (mob 32700, fixture world) is the captive: one bottle
carried, one inside a carried sack and one in the stash.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GALLERY, SPARRING_GUARD, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zbottlepass1"
TEMPLE = 4207
BOTTLE = 32711      # the fixture amulet, standing in for a bottle
SACK = 32710


def bottle(nest: int) -> str:
    return ("#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nTrap %d\nEnd\n\n"
            % (BOTTLE, nest, SPARRING_GUARD))


def sack() -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % SACK


def guards(staff) -> list[int]:
    """The rooms of every sparring guard standing in the world. A captive
    has no room, so MWHERE does not list one."""
    reply = staff.sync("mwhere sparring", timeout=60)
    return [int(room) for room in
            re.findall(r"\[\s*%d\]\s.*?\[\s*(\d+)\]" % SPARRING_GUARD, reply)]


def traps(mud: LiveMud, name: str) -> int:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return len(re.findall(r"(?m)^Trap %d$" % SPARRING_GUARD, text))


class CaptiveSourceTests(unittest.TestCase):
    def test_disposal_never_releases(self) -> None:
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        for sig in ("void extract_obj( OBJ_DATA *obj )",
                    "void extract_obj_player( OBJ_DATA *obj )"):
            fn = handler.split(sig, 1)[1].split("\n}\n", 1)[0]
            self.assertIn("captive_dispose(obj);", fn, sig)
            self.assertNotIn("char_from_obj(obj)", fn, sig)
        dispose = handler.split("void captive_dispose( OBJ_DATA *obj )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("extract_char( mob, true );", dispose)
        # The release asks where the holder really stands, not the room a
        # copy loaded from a file names.
        self.assertIn("captive_carrier_placed( obj->carried_by )", handler)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CaptiveLiveTests(unittest.TestCase):
    maxDiff = None

    def test_no_way_of_leaving_memory_sets_a_captive_loose(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Zbotstaff", "Zbottler"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbotstaff", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Zbottler", Levl=20, Room=SPARRING_GALLERY)
            path = mud.player_dir / "Zbottler"
            text = path.read_text(encoding="latin-1")
            path.write_text(text.replace(
                "#END", bottle(0) + sack() + bottle(1) + "#STASH\n" + bottle(0) + "#END", 1),
                encoding="latin-1")
            self.assertEqual(traps(mud, "Zbottler"), 3)

            seen: list[tuple[str, list[int]]] = []
            with mud.connect(timeout=120) as staff:
                login(staff, "Zbotstaff", PW)
                staff.sync("scroll 0")
                self.assertEqual(guards(staff), [], "no guard before anything is loaded")

                # The name, then hang up at the password prompt.
                for _ in range(3):
                    with mud.connect(timeout=60) as client:
                        client.expect("by what name", "name:")
                        client.send("Zbottler")
                        client.expect("password")
                    staff.drain(1.5)
                seen.append(("hung up at the password prompt", guards(staff)))

                # A wrong password.
                for _ in range(2):
                    with mud.connect(timeout=60) as client:
                        client.expect("by what name", "name:")
                        client.send("Zbottler")
                        client.expect("password")
                        client.send("Znotthepass")
                        client.expect("Wrong password")
                        client.wait_closed()
                    staff.drain(1.0)
                seen.append(("wrong password", guards(staff)))

                # An offline load: GRANTPSI loads, saves and frees a copy.
                staff.sync("grantpsi zbottler", timeout=60)
                seen.append(("an offline load (GRANTPSI)", guards(staff)))
                self.assertEqual(traps(mud, "Zbottler"), 3, "the offline save kept every bottle")

                # A login: the name prompt's copy is freed and the file read
                # again; then a quit frees the playing copy's things.
                with mud.connect(timeout=120) as player:
                    login(player, "Zbottler", PW)
                    player.sync("scroll 0")
                    seen.append(("a login", guards(staff)))
                    inv = player.sync("inventory", timeout=60)
                    self.assertIn("fixture amulet", inv, inv)
                    player.send("quit")
                    self.assertTrue(player.wait_closed())
                staff.drain(1.0)
                seen.append(("a quit", guards(staff)))
                self.assertEqual(traps(mud, "Zbottler"), 3, "the bottles keep their catch in the file")

                self.assertEqual([(how, []) for how, _ in seen], seen,
                                 "a captive was set loose by its bottle leaving memory")

                # Opening a bottle in play lets exactly one out, where the
                # opener stands, and the others stay shut.
                with mud.connect(timeout=120) as player:
                    login(player, "Zbottler", PW)
                    player.sync("scroll 0")
                    opened = player.sync("open amulet", timeout=60)
                    self.assertIn("has been let out of", opened, opened)
                    self.assertEqual(guards(staff), [SPARRING_GALLERY])
                    player.send("quit")
                    self.assertTrue(player.wait_closed())
                staff.drain(1.0)
                self.assertEqual(guards(staff), [SPARRING_GALLERY], "the quit freed no other")
                self.assertEqual(traps(mud, "Zbottler"), 2, "the opened bottle is gone")
                staff.send("quit")
                staff.wait_closed()


if __name__ == "__main__":
    unittest.main()
