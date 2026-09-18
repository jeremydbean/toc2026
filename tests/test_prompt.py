"""The PROMPT command, and who is allowed to see a room vnum.

The old command had a trap in it: `prompt' with no argument turned prompts
*off*, so the obvious way to ask what your prompt was set to was also the
way to lose it. The help file had described the opposite behaviour for
years. That mismatch is what these tests pin down, along with the two
additions: a discoverable code list, and a staff shortcut for the vnum.

%R is staff-only now. do_exits already hid vnums from mortals; the prompt
was the one place a player could get at the builder's view of the world.
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

IMMORTAL_LEVEL = 70
PASSWORD = "Zpromptp1"


def run(client, command: str, settle: float = 2.0) -> str:
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
class PromptTests(unittest.TestCase):
    def test_bare_prompt_reports_instead_of_switching_prompts_off(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpromone", PASSWORD)
                client.drain(2.0)

                output = run(client, "prompt", settle=3.0)
                self.assertIn("Your prompt:", output)
                self.assertNotIn("no longer see prompts", output)

                # Still prompted afterwards: the report changed nothing.
                self.assertIn("hp", run(client, "look", settle=2.5))

    def test_codes_are_discoverable_in_game(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpromtwo", PASSWORD)
                client.drain(2.0)

                output = run(client, "prompt codes", settle=3.0)
                for code in ("%h", "%M", "%e", "%g", "%r", "%R", "%%"):
                    self.assertIn(code, output)
                self.assertIn("experience to level", output)

    def test_setting_and_resetting(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpromthr", PASSWORD)
                client.drain(2.0)

                run(client, "prompt <%hhp %mmana>", settle=2.5)
                self.assertIn("%hhp %mmana", run(client, "prompt", settle=2.5))

                run(client, "prompt default", settle=2.5)
                shown = run(client, "prompt", settle=2.5)
                self.assertIn("you have not set one", shown)

    def test_on_and_off_replace_the_old_bare_toggle(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpromfou", PASSWORD)
                client.drain(2.0)

                self.assertIn("no longer see prompts",
                              run(client, "prompt off", settle=2.5))
                self.assertIn("off", run(client, "prompt", settle=2.5))
                self.assertIn("now see prompts",
                              run(client, "prompt on", settle=2.5))


@unittest.skipIf(SKIP is not None, SKIP or "")
class RoomVnumVisibilityTests(unittest.TestCase):
    def test_staff_shortcut_adds_and_removes_the_vnum(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpromimm")
            with mud.connect(timeout=120) as client:
                login(client, "Zpromimm", PASSWORD)

                self.assertIn("now shows the room vnum",
                              run(client, "prompt room on", settle=3.0))
                self.assertIn("%R", run(client, "prompt", settle=2.5))

                # It renders as a real number, not the literal code.
                looked = run(client, "look", settle=3.0)
                match = re.search(r"\[(\d+)\]", looked)
                self.assertIsNotNone(match, "the vnum should appear in the prompt")

                self.assertIn("already shows",
                              run(client, "prompt room on", settle=2.5))
                self.assertIn("no longer shows",
                              run(client, "prompt room off", settle=2.5))
                self.assertNotIn("%R", run(client, "prompt", settle=2.5))

    def test_mortals_get_neither_the_shortcut_nor_the_number(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zprommort", PASSWORD)
                client.drain(2.0)

                self.assertIn("for staff",
                              run(client, "prompt room on", settle=3.0))

                # And setting %R by hand renders as nothing, rather than
                # leaking the builder's view of the world.
                run(client, "prompt <%hhp>[%R]", settle=2.5)
                looked = run(client, "look", settle=3.0)
                self.assertNotRegex(looked, r"\[\d+\]")
                self.assertIn("[]", looked)


if __name__ == "__main__":
    unittest.main()
