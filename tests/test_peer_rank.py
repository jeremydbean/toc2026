"""Implementors can use immortal commands on each other.

Twenty-two commands refused when `get_trust(victim) >= get_trust(ch)'. At
MAX_LEVEL that reads 70 >= 70, so an implementor could not aim any of them
at another implementor -- the people those commands most often exist for,
and the one rank nobody could ever act against.

The pair of tests that matter are the two halves of the rule: the exemption
applies at 70, and the ordinary restriction still bites below it. A fix
that removed the check outright would pass the first and fail the second.
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

PASSWORD = "Zpeerrk11"
MAX_LEVEL = 70

# A spread across the commands that carried the check, chosen so each one
# reports something distinctive rather than silence.
REFUSALS = ("You failed", "not high enough", "cannot", "can't")


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def staff(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=level)


@unittest.skipIf(SKIP is not None, SKIP or "")
class PeerRankTests(unittest.TestCase):
    def test_an_implementor_can_act_on_another_implementor(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zpeerone", MAX_LEVEL)
            staff(mud, "Zpeertwo", MAX_LEVEL)

            with mud.connect(timeout=120) as target:
                login(target, "Zpeertwo", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Zpeerone", PASSWORD)

                    for command in ("nochannels Zpeertwo",
                                    "noemote Zpeertwo",
                                    "notitle Zpeertwo",
                                    "whiner Zpeertwo"):
                        reply = run(god, command)
                        for refusal in REFUSALS:
                            self.assertNotIn(
                                refusal, reply,
                                f"'{command}' still refuses a peer: {reply!r}")

    def test_the_restriction_still_applies_below_max_level(self) -> None:
        """Otherwise the fix removed the rule rather than exempting 70."""
        with LiveMud() as mud:
            staff(mud, "Zpeerlow", 65)
            staff(mud, "Zpeerhigh", 68)

            with mud.connect(timeout=120) as target:
                login(target, "Zpeerhigh", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Zpeerlow", PASSWORD)
                    reply = run(god, "nochannels Zpeerhigh")

                    self.assertTrue(
                        any(refusal in reply for refusal in REFUSALS),
                        f"a level 65 should not reach a level 68: {reply!r}")

    def test_an_implementor_can_snoop_another_implementor(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zpeersnoop", MAX_LEVEL)
            staff(mud, "Zpeerseen", MAX_LEVEL)

            with mud.connect(timeout=120) as target:
                login(target, "Zpeerseen", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Zpeersnoop", PASSWORD)
                    reply = run(god, "snoop Zpeerseen", settle=3.0)
                    for refusal in REFUSALS:
                        self.assertNotIn(refusal, reply,
                                         f"snoop refuses a peer: {reply!r}")

    def test_self_targeting_guards_are_untouched(self) -> None:
        """Rank is not what those guards are about, so they stay."""
        with LiveMud() as mud:
            staff(mud, "Zpeerself", MAX_LEVEL)
            with mud.connect(timeout=120) as god:
                login(god, "Zpeerself", PASSWORD)
                self.assertIn("Yeah right",
                              run(god, "purge Zpeerself", settle=3.0))


if __name__ == "__main__":
    unittest.main()
