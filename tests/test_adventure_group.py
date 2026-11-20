"""ADVENTURE's group section counts a groupmate it cannot see (review,
2026-11-20).

adventure_group asked online_can_list -- WHO's rule -- before
is_same_group, so a grouped mortal who turned invisible dropped out of the
count and "Your group" vanished. A groupmate is known already, so they are
counted whatever the viewer can see; players outside the group are still
counted only as WHO would list them, and an invisible stranger near the
level is not "company".

Two synthetic Z characters (and a staff fixture) in a disposable world.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zadgpass1"
TEMPLE = 4207
QUIET = {"TOC_NO_TUTORIAL": None, "TOC_TUTORIAL_GAP": "600"}
GROUP = "Your group: you are grouped with 1 other."


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def adventure(client) -> str:
    return " ".join(client.sync("adventure", timeout=30).split())


@unittest.skipIf(SKIP is not None, SKIP or "")
class AdventureGroupTests(unittest.TestCase):
    def test_an_invisible_groupmate_is_still_counted(self) -> None:
        with LiveMud(extra_env=QUIET) as mud:
            make(mud, "Zadgstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zadglead", Levl=30, Room=TEMPLE)
            make(mud, "Zadgmate", Levl=30, Cla=0, Room=TEMPLE,
                 HMV="900 900 900 900 300 300", HMVP="900 900 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as lead, \
                    mud.connect(timeout=120) as mate:
                login(staff, "Zadgstaff", PW)
                login(lead, "Zadglead", PW)
                login(mate, "Zadgmate", PW)
                for client in (staff, lead, mate):
                    client.sync("scroll 0")
                staff.must("set skill zadgmate invis 100", "")
                mate.must("follow zadglead", "You now follow")
                lead.must("group zadgmate", "joins")
                self.assertIn(GROUP, adventure(lead))

                mate.must("cast invis", "fade out of existence")
                self.assertNotIn("Zadgmate", lead.sync("look"))
                self.assertIn(GROUP, adventure(lead))

                # The group dissolves: no group, and an invisible player
                # near the level is not counted as company.
                # stop_follower says nothing to a follower its leader cannot
                # see (stock ROM); the group is gone all the same.
                mate.sync("follow self")
                group = mate.sync("group")
                self.assertIn("Zadgmate's group:", group)
                self.assertNotIn("Zadglead", group)
                said = adventure(lead)
                self.assertNotIn("Your group", said)
                self.assertNotIn("Company", said)

                # Visible again, a stranger near the level is company.
                mate.must("visible", "Ok.")
                said = adventure(lead)
                self.assertNotIn("Your group", said)
                self.assertIn("Company: 1 other player near your level is on", said)
                for client in (mate, lead, staff):
                    client.send("quit")
                    client.wait_closed()


if __name__ == "__main__":
    unittest.main()
