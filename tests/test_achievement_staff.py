"""Staff earn none of the 2026-10-25 expansion's achievements.

The gameplay hooks each asked ACH_STAFF, but the login catch-up and the
state checks did not: a level 20 builder trusted to 60, with sword and
dagger at 100%, logged in and out and was saved holding Weapons Scholar I
and Practice Makes Permanent I (review, 2026-10-26). achievement_unlock is
where every award passes, and it now refuses an expansion row to staff.
Rows from before the expansion keep their rule, and nothing already earned
is taken away.

Staff are immortals by level (owner, 2026-11-12: "let trusted players act
as mortals across the board"): that builder trusted to 60 at level 20 is a
mortal now and is caught up like one; a level 60 immortal earns none.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zachstaff1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    end = text.index("\nEnd\n")
    path.write_text(text[:end] + "\nSk 100 'sword'\nSk 100 'dagger'" + text[end:],
                    encoding="latin-1")


def earned_after_a_visit(mud: LiveMud, name: str) -> set:
    with mud.connect(timeout=120) as client:
        login(client, name, PW)
        client.sync("save")
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return set(re.findall(r"^Achv (\S+) ", text, re.M))


@unittest.skipIf(SKIP is not None, SKIP or "")
class StaffAchievementTests(unittest.TestCase):
    def test_staff_by_level_earn_no_new_feat_and_trusted_mortals_do(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zachstaff", Levl=60, Room=TEMPLE)
            make(mud, "Zachtrust", Levl=20, Tru=60, Room=TEMPLE)
            make(mud, "Zachmortal", Levl=20, Room=TEMPLE)

            staff = earned_after_a_visit(mud, "Zachstaff")
            trusted = earned_after_a_visit(mud, "Zachtrust")
            mortal = earned_after_a_visit(mud, "Zachmortal")

            # The ordinary mortal is caught up on both...
            self.assertTrue({"weapons-1", "mastered-1"} <= mortal, mortal)
            # ...and so is the mortal given trust: a mortal, by level.
            self.assertTrue({"weapons-1", "mastered-1"} <= trusted, trusted)
            # The immortal gets neither, by level...
            self.assertFalse({"weapons-1", "mastered-1"} & staff, staff)
            # ...and still the achievements from before the expansion.
            self.assertIn("level-20", staff)

            # Made mortal again: the next login catches the character up.
            patch_player_file(mud, "Zachstaff", Levl=20)
            demoted = earned_after_a_visit(mud, "Zachstaff")
            self.assertTrue({"weapons-1", "mastered-1"} <= demoted, demoted)

            # Immortal again: nothing already earned is taken away.
            patch_player_file(mud, "Zachstaff", Levl=60)
            again = earned_after_a_visit(mud, "Zachstaff")
            self.assertTrue(demoted <= again, demoted - again)


if __name__ == "__main__":
    unittest.main()
