"""An old savefile's carried items keep their worth.

Player files hold a Cost per carried object, written in gold until the
prices moved to copper. Without a migration every item anybody was carrying
would come back worth a ten thousandth of what they put it down with, and
they would find it out at a shop counter.

Files now carry `Vers 4`. Anything older has its object costs scaled on
load.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zmigrate1"
COPPER_PER_GOLD = 10000


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class CopperMigrationTests(unittest.TestCase):
    def test_a_pre_copper_savefile_keeps_its_item_values(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmigrate", PASSWORD)
                client.send("quit")
                client.wait_closed()

            path = mud.player_dir / "Zmigrate"
            saved = path.read_text("latin-1")

            costs = [int(m) for m in re.findall(r"^Cost (\d+)$", saved, re.M)]
            self.assertTrue(costs, "the character should be carrying something")

            # Put the file back the way it was written before the move:
            # version 3, with every object cost in gold.
            old = saved.replace("Vers 4", "Vers 3")
            old = re.sub(r"^Cost (\d+)$",
                         lambda m: f"Cost {int(m.group(1)) // COPPER_PER_GOLD}",
                         old, flags=re.M)
            path.write_text(old, encoding="latin-1", newline="")

            with mud.connect(timeout=120) as client:
                login(client, "Zmigrate", PASSWORD)
                run(client, "save", settle=3.0)

            rewritten = path.read_text("latin-1")

        self.assertIn("Vers 4", rewritten, "the file should be brought forward")

        after = [int(m) for m in re.findall(r"^Cost (\d+)$", rewritten, re.M)]
        self.assertEqual(
            sorted(after), sorted(costs),
            "an old file's item values should survive the move to copper")


if __name__ == "__main__":
    unittest.main()
