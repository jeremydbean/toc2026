"""WIMPY fires for a player who types nothing after KILL (2026-10-22).

KILL lags its player a round, and the input loop counts lag down only
while a command is waiting, so a player who attacked and then watched kept
that round of lag all fight. damage() lets wimpy flee only under half a
round of lag, so it never did: a level 34 warrior with wimpy 143 went
118 -> 79 -> 22 -> dead without trying. Lag now counts down every pulse
for a fighting player with nothing typed (fight_lag_update, owner's
choice), as stock ROM did.

A mortal is set up in the Temple, sets WIMPY, is transferred to a security
guard, types KILL and nothing else; the test only listens.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zwimpy1pass"
TEMPLE = 4207
HALLS = 4202            # not safe
GUARD = 29012           # a Korzath security guard: hits hard enough to matter


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class WimpyWhileIdleTests(unittest.TestCase):
    def test_wimpy_fires_with_nothing_typed_after_kill(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zcoward", 20), ("Zwimpgod", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            # Enough hit points to take a few rounds, wimpy well above zero.
            patch_player_file(mud, "Zcoward", Levl=20, Room=TEMPLE,
                              HMV="400 400 500 500 500 500", HMVP="400 500 500")
            patch_player_file(mud, "Zwimpgod", Levl=70, Room=HALLS)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zcoward", PW)
                login(god, "Zwimpgod", PW)
                run(hero, "scroll 0")
                self.assertIn("150", run(hero, "wimpy 150"))
                # The guard wanders: one walked south before the KILL and
                # the test waited 90 s on nothing (CI, 2026-10-25).
                said = god.sync(f"set mob {GUARD} act +sentinel")
                self.assertNotIn("Syntax", said, said)
                # Every staff step is synced, and the hero has to see the
                # guard before typing KILL: on a loaded runner the hero
                # arrived to a room with no guard in it and KILL said
                # "They aren't here." (CI, 2026-10-25).
                god.sync(f"goto {HALLS}")
                god.sync(f"transfer zcoward {HALLS}")
                god.sync(f"load mob {GUARD}")
                seen = hero.sync("look")
                self.assertIn("security guard", seen.lower(), seen)
                god.sync(f"goto {TEMPLE}")      # out of the guard's way
                hero.buffer = ""
                run(hero, "kill guard", 0.5)
                # Nothing more is typed. Listen for wimpy's flee, or death.
                outcome = hero.expect("You flee from combat", "PANIC! You couldn't escape",
                                      "You have been KILLED", timeout=90)
                run(god, f"goto {HALLS}", 0.6)
                run(god, "peace", 0.6)
                for client in (hero, god):
                    client.send("quit")
                    client.wait_closed()

        self.assertIn(outcome, ("You flee from combat", "PANIC! You couldn't escape"),
                      "wimpy never tried before the player died")


if __name__ == "__main__":
    unittest.main()
