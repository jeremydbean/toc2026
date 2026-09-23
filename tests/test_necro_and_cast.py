"""CAST takes multi-word spells, and the undead no longer need a corpse.

Two reports from the same session: `cast create wraith' said the spell did
not exist because CAST only ever read one word, and the whole create line
was unusable because all three spells were TAR_OBJ_HERE and corpses decay.
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

PASSWORD = "Znecroone1"

CLASS_NECRO, GUILD_NECRO = 5, 5


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def necromancer(mud: LiveMud, name: str, level: int = 70) -> None:
    """Staff level, so the test can GOTO somewhere empty and SET its own
    skills; the spells care about class, not rank."""
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=level, Cla=CLASS_NECRO, Gui=GUILD_NECRO)


@unittest.skipIf(SKIP is not None, SKIP or "")
class NecroUndeadTests(unittest.TestCase):
    def test_create_wraith_needs_neither_quotes_nor_a_corpse(self) -> None:
        with LiveMud() as mud:
            necromancer(mud, "Znecroone")

            with mud.connect(timeout=120) as client:
                login(client, "Znecroone", PASSWORD)
                # Somewhere quiet, with certainly no corpse lying about.
                run(client, "goto 29500", settle=3.0)
                run(client, "set skill Znecroone 'create wraith' 100",
                    settle=2.0)

                cast = run(client, "cast create wraith", settle=4.0)

            self.assertNotIn("don't know any spells", cast.lower(),
                             f"unquoted multi-word cast should work:\n{cast}")
            self.assertNotIn("what should the spell be cast upon", cast.lower(),
                             f"a corpse should not be required:\n{cast}")
            self.assertIn("wraith", cast.lower(),
                          f"a wraith should have been raised:\n{cast}")

    def test_quoting_still_works(self) -> None:
        with LiveMud() as mud:
            necromancer(mud, "Znecrotwo")

            with mud.connect(timeout=120) as client:
                login(client, "Znecrotwo", PASSWORD)
                run(client, "goto 29501", settle=3.0)
                run(client, "set skill Znecrotwo 'create skeleton' 100",
                    settle=2.0)

                cast = run(client, "cast 'create skeleton'", settle=4.0)

            self.assertNotIn("don't know any spells", cast.lower(),
                             f"the quoted form must still work:\n{cast}")
            self.assertIn("skeleton", cast.lower(),
                          f"a skeleton should have been raised:\n{cast}")

    def test_a_servant_follows_the_casters_level(self) -> None:
        with LiveMud() as mud:
            necromancer(mud, "Znecrothree")

            with mud.connect(timeout=120) as client:
                login(client, "Znecrothree", PASSWORD)
                run(client, "goto 29502", settle=3.0)
                run(client, "set skill Znecrothree 'create skeleton' 100",
                    settle=2.0)
                run(client, "cast create skeleton", settle=4.0)

                stat = run(client, "stat skeleton", settle=3.0)

            # It used to be corpse->level/3, so with no corpse at all there
            # would have been nothing to raise.
            self.assertIn("Level", stat, f"no skeleton to stat:\n{stat}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuildNameTests(unittest.TestCase):
    def test_an_immortal_can_set_the_necro_guild(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zguildnec", PASSWORD)
                client.send("quit")
                client.wait_closed()
            with mud.connect(timeout=120) as client:
                create_character(client, "Zguildimp", PASSWORD)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zguildimp", Levl=70)

            with mud.connect(timeout=120) as client:
                login(client, "Zguildimp", PASSWORD)
                out = run(client, "set Zguildnec guild necro", settle=3.0)

            self.assertNotIn("not familiar", out.lower(), out)
            self.assertNotIn("value must be", out.lower(),
                             f"necro should be a nameable guild:\n{out}")


if __name__ == "__main__":
    unittest.main()
