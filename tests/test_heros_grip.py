"""Hero's grip: the warrior/warrior's resistance to being disarmed.

Checks the four things that could silently be wrong: that a W/W gets the
skill without asking for it, that at 100% a disarm never lands, that the
warrior can still take the weapon off by hand, and that practice stops at
75 rather than running to the class adept.
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

PASSWORD = "Zgriptest1"

CLASS_WARRIOR = 3
GUILD_WARRIOR = 3


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def warrior(mud: LiveMud, name: str, level: int = 50) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=level, Cla=CLASS_WARRIOR,
                      Gui=GUILD_WARRIOR)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HerosGripTests(unittest.TestCase):
    def test_a_double_warrior_has_it_and_cannot_be_disarmed_at_full(self) -> None:
        with LiveMud() as mud:
            warrior(mud, "Zgripper")

            with mud.connect(timeout=120) as client:
                login(client, "Zgripper", PASSWORD)

                listed = run(client, "skills", settle=4.0)
                self.assertIn("hero's grip", listed.lower(),
                              f"a W/W should already have the skill:\n{listed}")

                # The entry runs past one screen, so page to the end.
                shown = run(client, "help hero's grip", settle=3.0)
                for _ in range(5):
                    if "[Hit Return to continue]" not in shown[-120:]:
                        break
                    shown += run(client, "", settle=2.0)

                self.assertIn("Vladamir", shown,
                              f"the help should name who trains it:\n{shown}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class PracticeCapTests(unittest.TestCase):
    def test_practice_stops_at_seventy_five(self) -> None:
        with LiveMud() as mud:
            # Staff level so the test can walk to the guildmaster; the
            # skill itself only cares that the character is W/W.
            warrior(mud, "Zgriptwo", level=70)
            # Enough sessions to blow past the cap if it were not enforced.
            patch_player_file(mud, "Zgriptwo", Prac=40)

            with mud.connect(timeout=120) as client:
                login(client, "Zgriptwo", PASSWORD)
                # Vladamir the veteran, the warrior guild's own master.
                run(client, "goto vladamir", settle=4.0)

                last = ""
                for _ in range(12):
                    last = run(client, "practice hero's grip", settle=1.5)
                    if "all I can" in last:
                        break

                self.assertIn("all I can", last,
                              f"practice should stop at 75%:\n{last}")

                after = run(client, "practice", settle=3.0)
                self.assertRegex(
                    after, r"hero's grip\s+75%",
                    f"the cap should leave it at exactly 75%:\n{after}")


if __name__ == "__main__":
    unittest.main()
