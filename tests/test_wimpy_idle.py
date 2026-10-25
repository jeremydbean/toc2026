"""WIMPY fires for a player who types nothing after KILL (2026-10-22).

KILL lags its player a round, and the input loop counts lag down only
while a command is waiting, so a player who attacked and then watched kept
that round of lag all fight. damage() lets wimpy flee only under half a
round of lag, so it never did: a level 34 warrior with wimpy 143 went
118 -> 79 -> 22 -> dead without trying. Lag now counts down every pulse
for a fighting player with nothing typed (fight_lag_update, owner's
choice), as stock ROM did.

A mortal is set up in the Temple, sets WIMPY, is transferred to the test
world's sparring guard, types KILL and nothing else; the test only listens
-- no WORTH, no sync, nothing typed after KILL, because typed input is
exactly what this test proves wimpy no longer needs.
"""
from __future__ import annotations

import unittest

from live_mud import (LiveMud, SPARRING_FLOOR, create_character, login, patch_player_file,
                      place_sparring_guard, room_of, skip_reason)

SKIP = skip_reason()
PW = "Zwimpy1pass"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class WimpyWhileIdleTests(unittest.TestCase):
    def test_wimpy_fires_with_nothing_typed_after_kill(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name, level in (("Zcoward", 20), ("Zwimpgod", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            # Enough hit points to take a few rounds, wimpy well above zero.
            patch_player_file(mud, "Zcoward", Levl=20, Room=TEMPLE,
                              HMV="400 400 500 500 500 500", HMVP="400 500 500")
            patch_player_file(mud, "Zwimpgod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zcoward", PW)
                login(god, "Zwimpgod", PW)
                run(hero, "scroll 0")
                self.assertIn("150", run(hero, "wimpy 150"))
                # The fixture guard stands still and never flees; the
                # Korzath guard this used wandered off (it is WIMPY and
                # STAY_AREA, and SET MOB cannot change a shipped mobile).
                place_sparring_guard(god, "zwimpgod", SPARRING_FLOOR)
                god.must(f"transfer zcoward {SPARRING_FLOOR}", "Ok.")
                god.sync(f"goto {TEMPLE}")      # out of the guard's way
                self.assertEqual(room_of(god, "zwimpgod"), TEMPLE)
                self.assertEqual(room_of(god, "zcoward"), SPARRING_FLOOR)
                seen = hero.sync("look")       # before KILL: nothing after it
                self.assertIn("sparring guard", seen, seen)
                hero.buffer = ""
                run(hero, "kill guard", 0.5)
                # Nothing more is typed. Listen for wimpy's flee, or death.
                outcome = hero.expect("You flee from combat", "PANIC! You couldn't escape",
                                      "You have been KILLED", timeout=90)
                god.sync(f"goto {SPARRING_FLOOR}")
                god.sync("peace")
                for client in (hero, god):
                    client.send("quit")
                    client.wait_closed()

        self.assertIn(outcome, ("You flee from combat", "PANIC! You couldn't escape"),
                      "wimpy never tried before the player died")


if __name__ == "__main__":
    unittest.main()
