"""A guild's skills follow the guild, however you came by it.

Joining at the clerk called group_add for the guild's group. Remorting set
ch->pcdata->guild directly and never did, and the clerk refuses anyone
already in a guild -- so once you remorted into one there was no way left
to be given what it grants. A remorted warrior/warrior was simply missing
second attack.

Nothing re-checked it either: load_char_obj only re-applied class groups
for characters at version < 2. The grants are now applied on every load, so
a character short of anything their class, guild or race owes them is
repaired at their next login.
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

PASSWORD = "Zguildone1"

CLASS_WARRIOR, GUILD_WARRIOR = 3, 3
CLASS_THIEF, GUILD_THIEF = 2, 2


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def character(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuildSkillGrantTests(unittest.TestCase):
    def test_a_warrior_in_the_warrior_guild_has_second_attack(self) -> None:
        with LiveMud() as mud:
            # A guild set on the character without the group being given,
            # which is exactly the state remort left people in.
            character(mud, "Zguildone", Levl=30, Cla=CLASS_WARRIOR,
                      Gui=GUILD_WARRIOR)

            with mud.connect(timeout=120) as client:
                login(client, "Zguildone", PASSWORD)
                listed = run(client, "practice", settle=4.0)

            self.assertRegex(
                listed, r"second attack\s+\d+%",
                f"the warrior guild grants second attack:\n{listed}")

    def test_a_thief_in_the_thief_guild_has_trip(self) -> None:
        with LiveMud() as mud:
            character(mud, "Zguildtwo", Levl=30, Cla=CLASS_THIEF,
                      Gui=GUILD_THIEF)

            with mud.connect(timeout=120) as client:
                login(client, "Zguildtwo", PASSWORD)
                listed = run(client, "practice", settle=4.0)

            self.assertRegex(listed, r"trip\s+\d+%",
                             f"the thief guild grants trip:\n{listed}")

    def test_a_guildless_character_gains_nothing_extra(self) -> None:
        with LiveMud() as mud:
            character(mud, "Zguildnil", Levl=30, Cla=CLASS_WARRIOR)

            with mud.connect(timeout=120) as client:
                login(client, "Zguildnil", PASSWORD)
                listed = run(client, "practice", settle=4.0)

            self.assertNotRegex(
                listed, r"second attack\s+\d+%",
                f"no guild should mean no guild skills:\n{listed}")


if __name__ == "__main__":
    unittest.main()
