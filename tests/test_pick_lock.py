"""PICK tells a lock that cannot open apart from a missed roll.

A pickproof door answered "You failed." exactly as a missed skill roll
does, and the roll came before the target was even looked at, so a thief
at 75% spent 150 attempts on three such doors before filing a bug
(Alaric, 2026-10-11). Most locked doors in the world are pickproof (165
of the 229 a reset locks), so the difference is the whole skill.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zpicker1"
TEMPLE = 4207
CHAINS = 9339          # galaxy.are: the up exit is door state 2, pickproof
STOMACH = 11026        # ancala.are: the west doors are state 1, a reset locks them
CANNOT = "beyond any pick"
FUMBLES = ("tumblers drop back", "skitters out", "the lock holds", "lose them again",
           "Not this time")
LAG = 5.0              # pick lock's 12 beats are three seconds, and lag only
                       # counts down while a command waits, so the retry sits
                       # out the whole of it before it runs


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class PickSourceTests(unittest.TestCase):
    def test_the_lock_is_judged_before_the_roll(self) -> None:
        source = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        body = source[source.index("void do_pick("):]
        body = body[:body.index("\n}\n")]
        for flag in ("CONT_PICKPROOF", "EX_PICKPROOF"):
            with self.subTest(flag=flag):
                self.assertLess(body.index(flag), body.index("pick_lock_roll_fails( ch )", body.index(flag)) + 1)
        self.assertNotIn('send_to_char( "You failed.', body, "a miss is a fumble, in the helper")


@unittest.skipIf(SKIP is not None, SKIP or "")
class PickLiveTests(unittest.TestCase):
    def test_pickproof_says_so_and_a_real_lock_opens(self) -> None:
        """A mortal (so the pickproof checks apply) with staff trust, at
        100% so the only thing that can stop a pick is the lock itself."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpicker", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zpicker", Levl=40, Tru=70, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zpicker", PASSWORD)
                run(client, "set skill zpicker 'pick lock' 100", 1.6)

                run(client, "goto %d" % CHAINS, 1.8)
                run(client, "purge", 1.6)             # nobody standing too close
                for _ in range(2):
                    reply = run(client, "pick up", LAG)
                    self.assertIn(CANNOT, reply)
                    self.assertNotIn("You failed", reply)
                    self.assertFalse(any(f in reply for f in FUMBLES), reply)

                # A lock that can open: at 0% every roll misses and is a fumble...
                run(client, "goto %d" % STOMACH, 1.8)
                run(client, "purge", 1.6)
                run(client, "set skill zpicker 'pick lock' 0", 1.6)
                reply = run(client, "pick west", LAG)
                self.assertTrue(any(f in reply for f in FUMBLES), reply)
                self.assertNotIn(CANNOT, reply)
                self.assertNotIn("*Click*", reply)
                # ...and at 100% it opens.
                run(client, "set skill zpicker 'pick lock' 100", 1.6)
                reply = run(client, "pick west", LAG)
                self.assertIn("*Click*", reply)


if __name__ == "__main__":
    unittest.main()
