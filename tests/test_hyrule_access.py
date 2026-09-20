"""Hyrule can be entered, and left.

The area shipped with 443 rooms, nine dungeons and its own achievement
category behind a door nobody had built: no room exits into it, no object
led there, and every room carried ROOM_NO_RECALL. The help had described
the way in for as long as the area existed -- "Hyrule is entered through
the arcade cabinet" -- and the Games Room described the cabinet, but the
cabinet itself did not exist.

So: the cabinet is there and works, the overworld can be recalled out of,
and the dungeons still cannot.
"""
from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zhyruleone1"

GAMES_ROOM = 15068
HYRULE_ENTRANCE = 30200
HYRULE_DUNGEON = 30400


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def staff(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=70)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleAccessTests(unittest.TestCase):
    def test_the_cabinet_leads_to_hyrule(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zhyrule")

            with mud.connect(timeout=120) as client:
                login(client, "Zhyrule", PASSWORD)
                seen = run(client, f"goto {GAMES_ROOM}", settle=3.0)
                self.assertIn("Games Room", seen, seen)

                entered = run(client, "enter cabinet", settle=4.0)
                self.assertIn("The First Quest Begins", entered,
                              f"the cabinet should open onto Hyrule:\n{entered}")

    def test_recall_works_in_the_overworld_but_not_a_dungeon(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zhyrtwo")

            with mud.connect(timeout=120) as client:
                login(client, "Zhyrtwo", PASSWORD)

                run(client, f"goto {HYRULE_ENTRANCE}", settle=3.0)
                out = run(client, "recall", settle=4.0)
                # "The Gods have forsaken you." is what do_recall says in a
                # ROOM_NO_RECALL room.
                self.assertNotIn("forsaken", out.lower(),
                                 f"the overworld should be recallable:\n{out}")

                run(client, f"goto {HYRULE_DUNGEON}", settle=3.0)
                stuck = run(client, "recall", settle=4.0)
                self.assertIn("forsaken", stuck.lower(),
                              f"a dungeon should still refuse recall:\n{stuck}")


if __name__ == "__main__":
    unittest.main()
