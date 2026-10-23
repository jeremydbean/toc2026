"""PRESTORE <player> <stamp> GEAR (owner, 2026-10-23).

Alaric died AFK in the Korzath maze, his corpse rotted and a restart took
the gear off the floor. A full PRESTORE could give it back only by rolling
the whole character back. The GEAR form puts what a snapshot's character
wore and carried into their inventory and changes nothing else -- the
"before death" snapshot taken at every death holds exactly what they died
with. It refuses while the player's own corpse still holds things, since
that would make two of each, unless staff add FORCE.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zgearpass1"
ROOM = 4202              # not safe, so a slay is a death
KIT = "sub issue sword"  # part of the kit every new character wears


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class PrestoreGearTests(unittest.TestCase):
    def test_gear_comes_back_from_the_death_snapshot_and_nothing_else_moves(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zgearstaff", 70), ("Zgearlost", 20)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=ROOM)

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as lost:
                login(staff, "Zgearstaff", PW)
                login(lost, "Zgearlost", PW)
                for client in (staff, lost):
                    run(client, "scroll 0", 0.5)
                self.assertIn(KIT, run(lost, "equipment", 1.0))

                run(staff, "slay zgearlost", 2.0)
                lost.drain(1.0)
                self.assertNotIn(KIT, run(lost, "inventory", 1.0))
                self.assertNotIn(KIT, run(lost, "equipment", 1.0))

                mark = len(staff.transcript)
                run(staff, "prestore zgearlost", 3.0)
                listing = staff.transcript[mark:]
                stamp = re.search(r"before death\s+stamp (\d{8}_\d{6})", listing)
                self.assertIsNotNone(stamp, listing)
                # How long ago, then the time with its zone.
                self.assertRegex(listing, r"\[ 1\] (just now|\d+ minutes? ago) +\w{3} \d\d \d\d:\d\d")
                death = stamp.group(1) + ".death"

                # The corpse still holds the kit: refused, unless forced.
                said = run(staff, f"prestore zgearlost {death} gear", 1.5)
                self.assertIn("corpse still lies in the world", said)
                self.assertNotIn(KIT, run(lost, "inventory", 1.0))

                # Emptied -- nothing left in it to fetch -- and the kit
                # comes back.
                run(staff, "get all corpse", 1.5)
                said = run(staff, f"prestore zgearlost {death} gear", 2.0)
                restored = re.search(r"Restored (\d+) object", said)
                self.assertIsNotNone(restored, said)
                self.assertGreaterEqual(int(restored.group(1)), 4)
                lost.drain(1.0)
                self.assertIn("given back", lost.transcript)
                self.assertIn(KIT, run(lost, "inventory", 1.0))
                # Nothing else moved: still where the death left them,
                # nothing worn.
                self.assertIn("Death room", run(lost, "look", 1.0))
                self.assertNotIn(KIT, run(lost, "equipment", 1.0))

                lost.send("quit")
                lost.wait_closed()
            saved = (mud.player_dir / "Zgearlost").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Wear -1", saved)                    # carried, not worn
        self.assertRegex(log, r"Zgearstaff restored \d+ gear objects to Zgearlost")


if __name__ == "__main__":
    unittest.main()
