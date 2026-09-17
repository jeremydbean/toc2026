"""RESETPWD across ranks.

The interesting rule is the exception: implementors are the top rank, so
when one of them is locked out there is nobody above to ask, and they have
to be able to reset each other. Everyone below MAX_LEVEL keeps the ordinary
rule that a peer is off limits.

That exception is also the sharp edge -- it means any implementor can take
over any other implementor's account -- so it is worth a test that fails
loudly if the boundary ever moves.
"""
from __future__ import annotations

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

MAX_LEVEL = 70          # src/merc.h
BELOW_MAX = MAX_LEVEL - 1
PASSWORD = "Zresetpw1"
NEW_PASSWORD = "Zbrandnew2"


def run_reset(client, target: str, password: str) -> str:
    """Send one resetpwd and return just that command's output."""
    mark = len(client.transcript)
    client.send(f"resetpwd {target} {password}")
    client.drain(1.5)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetPwdRankTests(unittest.TestCase):
    def test_an_implementor_may_reset_another_implementor(self) -> None:
        actor, target = "Zresetone", "Zresettwo"

        with LiveMud() as mud:
            # Two characters, both taken to the top rank.
            for name in (actor, target):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=MAX_LEVEL)

            with mud.connect(timeout=120) as client:
                login(client, actor, PASSWORD)
                output = run_reset(client, target, NEW_PASSWORD)
                client.send("quit")
                client.wait_closed()

            self.assertNotIn("cannot reset", output.lower(), output)
            self.assertNotIn("only an implementor", output.lower(), output)

            # The proof is the target logging in with the new password.
            # NEW_PASSWORD is deliberately mixed case: the command used to
            # parse it with one_argument, which lowercased it, so the player
            # was handed a password that could not log them in. If that ever
            # comes back, this login fails.
            with mud.connect(timeout=120) as client:
                login(client, target, NEW_PASSWORD)
                client.send("quit")
                self.assertTrue(
                    client.wait_closed(),
                    "target could not log in with the reset password",
                )

    def test_below_max_level_a_peer_is_still_off_limits(self) -> None:
        actor, target = "Zresetthr", "Zresetfor"

        with LiveMud() as mud:
            for name in (actor, target):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=BELOW_MAX)

            with mud.connect(timeout=120) as client:
                login(client, actor, PASSWORD)
                output = run_reset(client, target, NEW_PASSWORD)
                client.send("quit")
                client.wait_closed()

            self.assertIn("implementor", output.lower(), output)

            # And the old password must still be the live one.
            with mud.connect(timeout=120) as client:
                login(client, target, PASSWORD)
                client.send("quit")
                self.assertTrue(
                    client.wait_closed(),
                    "the refused reset changed the password anyway",
                )


if __name__ == "__main__":
    unittest.main()
