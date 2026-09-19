"""Rooms built in game come back after a reboot.

The point of the feature is persistence, so that is what this checks: build
a room, connect it, save it, restart the server against the same data tree,
and walk into it. Everything else about building was already there and did
nothing useful without this.

Also checks the two rules on top of it: a room that shipped in an area file
is an implementor's to change, and writing over an existing .are takes a
confirmation that names the file.
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

PASSWORD = "Zbuildone1"
BUILDER_VNUM = 29126
LINKED_VNUM = 29127


def run(client, command: str, settle: float = 2.0) -> str:
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
class RoomBuildingTests(unittest.TestCase):
    def test_a_built_room_survives_a_reboot(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zbuilder", 70)

            with mud.connect(timeout=120) as client:
                login(client, "Zbuilder", PASSWORD)

                run(client, f"goto {BUILDER_VNUM}", settle=3.0)
                run(client, f"set room {BUILDER_VNUM} name The Proving Ground")
                run(client, f"set room {BUILDER_VNUM} desc "
                            "Bare stone, waiting to be made into something.")
                run(client, f"rlink north {LINKED_VNUM}", settle=3.0)
                saved = run(client, "rsave confirm", settle=6.0)

            self.assertIn("Wrote", saved,
                          f"rsave should have written the builder area:\n{saved}")

            custom = (mud.root / "area" / "custom.are").read_text("latin-1")
            self.assertIn(f"#{BUILDER_VNUM}", custom)
            self.assertIn("The Proving Ground", custom)
            self.assertIn("Bare stone", custom)

            # The whole point: a fresh boot off the same tree.
            mud.restart()

            with mud.connect(timeout=120) as client:
                login(client, "Zbuilder", PASSWORD)
                seen = run(client, f"goto {BUILDER_VNUM}", settle=3.0)

                self.assertIn("The Proving Ground", seen,
                              f"the built room did not come back:\n{seen}")
                self.assertNotIn("You form order from nothingness", seen,
                                 "the room was recreated, not reloaded")

                moved = run(client, "north", settle=3.0)
                self.assertNotIn("You cannot go that way", moved,
                                 f"the dug exit did not survive:\n{moved}")

    def test_shipped_rooms_and_files_are_protected(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zgodling", 69)

            with mud.connect(timeout=120) as client:
                login(client, "Zgodling", PASSWORD)

                # A shipped Mud School room is not a 69's to rename.
                denied = run(client, "set room 3700 name Zgodlings Parlour")
                self.assertIn("implementor", denied.lower(),
                              f"a god should not be able to edit 3700:\n{denied}")

                run(client, "goto 3700", settle=3.0)
                refused = run(client, "rsave confirm", settle=3.0)
                self.assertIn("implementor", refused.lower(),
                              f"a god should not write school.are:\n{refused}")

            staff(mud, "Zoverlord", 70)

            with mud.connect(timeout=120) as client:
                login(client, "Zoverlord", PASSWORD)
                run(client, "goto 3700", settle=3.0)

                # An implementor may, but not by accident.
                plan = run(client, "rsave", settle=3.0)
                self.assertIn("rsave confirm", plan,
                              f"rsave alone should explain, not write:\n{plan}")

                wrong = run(client, "rsave confirm", settle=3.0)
                self.assertIn("Name the file", wrong,
                              f"a shipped area needs its filename typed:\n{wrong}")


if __name__ == "__main__":
    unittest.main()
