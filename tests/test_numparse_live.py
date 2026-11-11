"""Typed numbers are whole or refused, live (modernization project 2,
2026-11-11).

atoi() read "2d6+3" as 2d6, "abc" as 0 and a number past int's range as
the low 32 bits of it, so LOAD MOB 4294967297 loaded mobile 1 and
ADVANCE <name> 4294967306 asked for level 10. Every command now reads its
numbers through parse_int/parse_long (src/numparse.c) and says no. This
plays a handful of them as a mortal and as staff; tests/test_numparse.py
checks the parser itself and that no atoi() is left in src/.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Znumparse1"
TEMPLE = 4207


@unittest.skipIf(SKIP is not None, SKIP or "")
class TypedNumberTests(unittest.TestCase):
    def test_bad_numbers_are_refused(self) -> None:
        with LiveMud() as mud:
            for name in ("Zcounter", "Zcountgod"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcounter", Levl=10, Room=TEMPLE)
            patch_player_file(mud, "Zcountgod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as mortal, mud.connect(timeout=120) as god:
                login(mortal, "Zcounter", PW)
                login(god, "Zcountgod", PW)
                mortal.sync("scroll 0")
                god.sync("scroll 0")

                # A mortal's numbers.
                mortal.must("wimpy 5abc", "Wimpy is a number of hit points")
                mortal.must("roll 2d6+3", "Rolls look like 2d6.")
                mortal.must("roll 2d6", "You roll 2d6:")
                mortal.must("scroll 99999999999", "You must provide a number.")
                mortal.must("history 99999999999", "That is not a valid number.")
                mortal.must("note read 99999999999", "Read which note?")

                # Staff numbers: the low 32 bits of these name real things.
                god.must("load mob 4294967297", "Invalid mob number.")
                god.must("load obj 4294967297", "Invalid object number.")
                god.must("goto 4294967297", "Invalid room number.")
                god.must("advance zcounter 4294967306", "Level must be 1 to 70.")
                god.must("jail zcounter -5", "Syntax: jail")
                reply = god.sync("stat zcounter")
                self.assertIn("Lv: 10 ", reply, reply)

                for client in (mortal, god):
                    client.send("quit")
                    client.wait_closed()


if __name__ == "__main__":
    unittest.main()
