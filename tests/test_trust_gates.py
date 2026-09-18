"""Permission gates that read trust rather than effective level.

get_trust() returns ch->trust when it is non-zero and falls back to
ch->level otherwise. trust is 0 unless somebody has explicitly assigned
one, which is the normal state, so every gate that read ch->trust directly
was comparing 0 against its threshold and refusing everybody -- including
implementors, and including commands the same function guarded correctly a
few lines away.

These are behavioural rather than source-level checks because the failure
mode was invisible from the code: each gate reads like it works.
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

PASSWORD = "Ztrustg11"


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
class TrustGateTests(unittest.TestCase):
    def test_an_implementor_can_advance_somebody_else(self) -> None:
        """The gate is `< 69'; with raw trust it read 0 and refused everyone."""
        with LiveMud() as mud:
            staff(mud, "Ztrustimp", 70)
            with mud.connect(timeout=120) as target:
                create_character(target, "Ztrustmort", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Ztrustimp", PASSWORD)
                    run(god, "goto Ztrustmort", settle=3.0)

                    output = run(god, "advance Ztrustmort 5", settle=3.0)
                    self.assertNotIn("only advance yourself", output)

    def test_a_lower_immortal_still_cannot(self) -> None:
        """The threshold has to still bite, or the fix removed the gate."""
        with LiveMud() as mud:
            staff(mud, "Ztrustlow", 66)
            with mud.connect(timeout=120) as target:
                create_character(target, "Ztrustmorb", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Ztrustlow", PASSWORD)
                    run(god, "goto Ztrustmorb", settle=3.0)

                    output = run(god, "advance Ztrustmorb 5", settle=3.0)
                    self.assertIn("only advance yourself", output)

    def test_an_implementor_can_oset_a_portal(self) -> None:
        """Gated on `trust != 70', so nobody at all could do it."""
        with LiveMud() as mud:
            staff(mud, "Ztrustose", 70)
            with mud.connect(timeout=120) as god:
                login(god, "Ztrustose", PASSWORD)

                run(god, "iportal Ztrustose", settle=3.0)
                output = run(god, "oset portal timer 5", settle=3.0)
                self.assertNotIn("can not set this item", output)

    def test_stat_room_works_for_an_implementor(self) -> None:
        """The first of the family to turn up; kept as a regression."""
        with LiveMud() as mud:
            staff(mud, "Ztrustrst", 70)
            with mud.connect(timeout=120) as god:
                login(god, "Ztrustrst", PASSWORD)
                output = run(god, "stat room", settle=3.0)
                self.assertNotIn("must be level 65", output)
                self.assertIn("Name:", output)


if __name__ == "__main__":
    unittest.main()
