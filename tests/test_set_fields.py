"""The fields SET can reach.

mset covered stats, money and the flag soup but not the combat numbers an
immortal actually reaches for; oset could not touch an object's name or
descriptions, so renaming anything meant editing an area file and
rebooting; rset could set only flags and sector.

The rset text fields are the ones worth a test rather than a read: that
function rejects a non-numeric value before it reaches any field, so a
string field added after that check would look right and never run.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zsetfld11"
IMMORTAL_LEVEL = 70


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SetCharTests(unittest.TestCase):
    def test_the_new_combat_and_movement_fields_apply(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zsetchar")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetchar", PASSWORD)

                for field, value in (("hitroll", 42), ("damroll", 37),
                                     ("wimpy", 13), ("maxmove", 777)):
                    reply = run(god, f"set char Zsetchar {field} {value}")
                    self.assertNotIn("Field being one of", reply,
                                     f"{field} was not recognised")
                    self.assertIn(str(value), reply)

                shown = run(god, "score", settle=3.0)
                self.assertRegex(shown, r"Wimpy Points:\s+13")

    def test_armor_sets_every_class_at_once(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zsetarm")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetarm", PASSWORD)
                reply = run(god, "set char Zsetarm armor -150")
                self.assertIn("all four", reply)

    def test_an_unknown_field_still_prints_the_usage(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zsetbad")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetbad", PASSWORD)
                reply = run(god, "set char Zsetbad nosuchfield 1")
                self.assertIn("Field being one of", reply)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SetObjTests(unittest.TestCase):
    def test_text_and_condition_can_be_changed(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zsetobj")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetobj", PASSWORD)
                run(god, "iportal Zsetobj", settle=3.0)

                renamed = run(god, "set obj portal short a shimmering doorway")
                self.assertIn("a shimmering doorway", renamed)

                # A room lists an object by its long description, so that is
                # the one to change if you want the floor to read differently.
                run(god, "set obj portal long A shimmering doorway hangs here.")
                self.assertIn("shimmering doorway hangs here",
                              run(god, "look", settle=3.0).lower())

                # Still referred to by its keywords: changing the short
                # description does not change what you can type at it.
                reply = run(god, "set obj portal condition 55")
                self.assertIn("55", reply)
                self.assertNotIn("Field being one of", reply)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SetRoomTests(unittest.TestCase):
    def test_a_room_can_be_renamed(self) -> None:
        """rset rejects non-numeric values, so text fields must run first."""
        with LiveMud() as mud:
            immortal(mud, "Zsetroom")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetroom", PASSWORD)

                here = run(god, "stat room", settle=3.0)
                match = re.search(r"Vnum: (\d+)", here)
                self.assertIsNotNone(match)
                vnum = match.group(1)

                reply = run(god, f"set room {vnum} name The Testing Floor")
                self.assertNotIn("must be numeric", reply)
                self.assertIn("The Testing Floor", reply)

                self.assertIn("The Testing Floor", run(god, "look", settle=3.0))

    def test_sector_still_works(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zsetsect")
            with mud.connect(timeout=120) as god:
                login(god, "Zsetsect", PASSWORD)

                here = run(god, "stat room", settle=3.0)
                vnum = re.search(r"Vnum: (\d+)", here).group(1)

                reply = run(god, f"set room {vnum} sector 1")
                self.assertIn("Sector set to 1", reply)


if __name__ == "__main__":
    unittest.main()
