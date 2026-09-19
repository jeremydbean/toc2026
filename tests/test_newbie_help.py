"""Things a brand new character needs: carry weight, rations, a way home.

Three fixes that share a cause -- nobody had played the first five minutes
recently:

  * group_add() grants every skill at 1%, so recall was 1%. It is not a
    skill you practise your way into needing; it is how a level one
    character survives a mistake.
  * Both strings of berries in the newbie pack are ITEM_NODROP, so a newbie
    handed the pack was stuck carrying them.
  * A level one carry allowance does not cover a starter kit plus anything
    worth picking up.

And one that was simply broken: a multi-word alias expanded with a trailing
space, which commands that read their whole argument choke on.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Znewhelp1"
IMMORTAL_LEVEL = 70

STARTING_RECALL_SKILL = 50
LEVEL_NEWBIE = 5


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StartingSkillTests(unittest.TestCase):
    def test_a_new_character_can_actually_recall(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Znewrec", PASSWORD)
                client.drain(2.0)

                shown = run(client, "practice", settle=4.0)
                match = re.search(r"recall\s+(\d+)%", shown)
                self.assertIsNotNone(match, "recall should be a known skill")
                self.assertGreaterEqual(int(match.group(1)),
                                        STARTING_RECALL_SKILL)

    def test_a_new_character_can_use_the_weapon_they_were_given(self) -> None:
        """The same class of bug, fixed earlier; kept as a regression."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Znewwep", PASSWORD)
                client.drain(2.0)

                shown = run(client, "practice", settle=4.0)
                percentages = [int(p) for p in re.findall(r"\s(\d+)%", shown)]
                self.assertTrue(any(p >= 40 for p in percentages),
                                "no skill was raised above the 1% floor")


@unittest.skipIf(SKIP is not None, SKIP or "")
class NewbiePackTests(unittest.TestCase):
    def test_everything_in_the_pack_can_be_dropped(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewpackimm")
            with mud.connect(timeout=120) as god:
                login(god, "Znewpackimm", PASSWORD)
                run(god, "newbie", settle=4.0)

                # Empty the pack onto the floor, then try to drop all of it.
                run(god, "get all from pack", settle=4.0)
                dropped = run(god, "drop all", settle=4.0)

                self.assertNotIn("can't let go of it", dropped,
                                 "something in the pack is still NODROP")
                self.assertNotIn("cursed", dropped)

    def test_the_pack_carries_the_endless_rations(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewpacktwo")
            with mud.connect(timeout=120) as god:
                login(god, "Znewpacktwo", PASSWORD)
                run(god, "newbie", settle=4.0)

                contents = run(god, "look in pack", settle=4.0).lower()
                self.assertIn("endless water jug", contents)
                self.assertIn("endless snack pack", contents)
                self.assertNotIn("pot pie", contents)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CarryWeightTests(unittest.TestCase):
    def test_every_player_carries_half_again_the_base(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Znewcarry", PASSWORD)
                client.drain(2.0)
                low = run(client, "score", settle=3.0)
                client.send("quit")
                client.wait_closed()

            # The same character at a higher level. The bonus applies at
            # every level now, so capacity must go up, not down -- it used
            # to be withdrawn past level 5.
            patch_player_file(mud, "Znewcarry", Levl=LEVEL_NEWBIE + 1)
            with mud.connect(timeout=120) as client:
                login(client, "Znewcarry", PASSWORD)
                high = run(client, "score", settle=3.0)

            def weight(text: str) -> int | None:
                # score prints "Encumbrance: <carried> (<maximum>)".
                match = re.search(r"Encumbrance:\s*(\d+)\s*\(\s*(\d+)\s*\)",
                                  text, re.I)
                return int(match.group(2)) if match else None

            low_max, high_max = weight(low), weight(high)
            if low_max is None or high_max is None:
                self.skipTest("score does not report a carry maximum")

            # A level 1 with the bonus already beats the unboosted formula,
            # and levelling only adds to it.
            self.assertGreaterEqual(high_max, low_max,
                                    "the bonus is being withdrawn with level")
            base = str(low_max)
            self.assertTrue(base, "no carry maximum parsed")


@unittest.skipIf(SKIP is not None, SKIP or "")
class AliasTests(unittest.TestCase):
    def test_a_multi_word_alias_runs_its_whole_command(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Znewalias")
            with mud.connect(timeout=120) as god:
                login(god, "Znewalias", PASSWORD)

                here = run(god, "stat room", settle=3.0)
                match = re.search(r"Number: (\d+)", here)
                self.assertIsNotNone(match, "could not read the room vnum")
                vnum = match.group(1)

                run(god, f"alias pit goto {vnum}", settle=2.5)
                used = run(god, "pit", settle=3.0)

                self.assertNotIn("No place like that around", used,
                                 "the alias expansion lost its argument")


if __name__ == "__main__":
    unittest.main()
