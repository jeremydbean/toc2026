"""HELP answers every spell group, and DOOR BASH (2026-10-05).

Necromancers asked HELP NECRO MALADICTIONS, NECRO PROTECTIVE, NECRO
ELEMENTAL and NECRO ENHANCEMENT and were told there was no help: 43 of the
58 groups have no entry. A group with none is answered from group_table,
so the list cannot drift from what GAIN sells. HELP DOOR BASH found nothing
because the command is DOORBASH.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zhelpgrp1"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.4)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class HelpGroupTests(unittest.TestCase):
    def test_groups_and_door_bash_have_answers(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelpgrp", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # Class 5 is the necromancer.
            patch_player_file(mud, "Zhelpgrp", Cla=5, Levl=10)
            with mud.connect(timeout=120) as client:
                login(client, "Zhelpgrp", PASSWORD)
                # Long entries page; a pending pager eats the next command.
                run(client, "scroll 0")
                group = run(client, "help necro maladictions")
                self.assertIn("Necro maladictions is a group of abilities:", group, group)
                self.assertIn("It costs you 2 trains.", group, group)
                self.assertNotIn("No help on that word", group)
                other = run(client, "help mage protective")
                self.assertIn("Your class does not buy it.", other, other)
                # A group that has its own entry keeps it.
                self.assertNotIn("is a group of abilities", run(client, "help maladictions"))
                self.assertIn("DOORBASH", run(client, "help door bash"))
                self.assertIn("No help on that word", run(client, "help zzqqxx"))


if __name__ == "__main__":
    unittest.main()
