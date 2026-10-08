"""In-game building, phase 6: BUILD, the guided builder.

BUILD AREA, ROOM, MOB and OBJ ask a question at a time and build through
the commands a builder could type, so the test answers them the way a
player would -- Enter to keep, a bad answer that is asked again, a
description line with a semicolon in it (which the input splitter would
otherwise cut in two), /LOOK in the middle, CANCEL -- then saves, reboots
and checks what was made is still there.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw6"


def run(client, command: str, settle: float = 1.0) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return re.sub(r"\x1b\[[0-9;]*m", "", client.transcript[mark:].replace("\r", ""))


@unittest.skipIf(SKIP is not None, SKIP or "")
class WizardTests(unittest.TestCase):
    def answer(self, client, text: str, expect: str, settle: float = 1.0) -> str:
        out = run(client, text, settle)
        self.assertIn(expect, out, f"after {text!r}: {out}")
        return out

    def test_a_whole_area_built_by_answering_questions(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zwizard", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwizard", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zwizard", PASSWORD)
                run(imm, "scroll 0")

                self.assertIn("Stand in an area you built", run(imm, "build mob"))

                # --- an area and two rooms -------------------------------
                self.answer(imm, "build area", "How many rooms")
                self.answer(imm, "6", "What is the area called")
                made = self.answer(imm, "Zed Wizard Works", "What is this room called", 2.0)
                lo = int(re.search(r"Created area 'Zed Wizard Works' \((\d+)-(\d+)\)",
                                   made).group(1))
                self.answer(imm, "The Wizard's Door", "Describe it")
                self.answer(imm, "A heavy oak door; iron-bound and old.", "more, or . to end")
                self.answer(imm, ".", "What kind of ground")
                self.answer(imm, "lava", "Not a kind of ground")
                self.answer(imm, "forest", "Dig a way out")
                # /LOOK runs as a command, and the build asks again.
                looked = run(imm, "/look")
                self.assertIn("The Wizard's Door", looked, looked)
                self.assertIn("Dig a way out", looked, looked)
                self.answer(imm, "north", "What is this room called", 2.0)
                self.answer(imm, "The Inner Hall", "Describe it")
                self.answer(imm, ".", "What kind of ground")
                self.answer(imm, "", "Dig a way out")
                self.answer(imm, "", "Save the area now")
                self.answer(imm, "yes", "Saved Zed Wizard Works", 2.0)

                # --- a mobile --------------------------------------------
                mob = lo
                self.answer(imm, "build mob", f"Which vnum should it have?  [{mob}]")
                self.answer(imm, "", "Start from a copy")
                self.answer(imm, "", "What will players call it")
                self.answer(imm, "wizard old", "How does it read")
                self.answer(imm, "an old wizard", "What line shows it")
                self.answer(imm, "An old wizard mutters to himself here.", "What does LOOK")
                self.answer(imm, "His robes are patched; his eyes are not.", "more, or . to end")
                self.answer(imm, ".", "What race")
                self.answer(imm, "elf", "Male, female")
                self.answer(imm, "male", "What level")
                self.answer(imm, "10", "Good, neutral or evil")
                self.answer(imm, "good", "How does it hit")
                self.answer(imm, "bogus", "Attacks:")          # refused, asked again
                self.answer(imm, "punch", "Anything else")
                self.answer(imm, "act +sentinel", "another, or Enter")
                self.answer(imm, "", "Place it in this room")
                self.answer(imm, "yes", "Save the area now", 1.5)
                self.answer(imm, "yes", "Mobile %d is built" % mob, 2.0)

                # --- an object -------------------------------------------
                obj = lo
                self.answer(imm, "build obj", f"Which vnum should it have?  [{obj}]")
                self.answer(imm, "", "Start from a copy")
                self.answer(imm, "", "What will players call it")
                self.answer(imm, "staff oak", "How does it read")
                self.answer(imm, "an oak staff", "What line shows it")
                self.answer(imm, "An oak staff leans against the wall.", "What does LOOK")
                self.answer(imm, ".", "What kind of thing")
                self.answer(imm, "weapon", "What kind of weapon")
                self.answer(imm, "spear", "damage dice")
                self.answer(imm, "2d5", "How does it hit")
                self.answer(imm, "pound", "Where is it worn")
                self.answer(imm, "+take +wield", "What level")
                self.answer(imm, "5", "How heavy")
                self.answer(imm, "4", "What is it worth")
                self.answer(imm, "3 gold", "Anything else")
                self.answer(imm, "", "Place it so it comes back")
                self.answer(imm, "floor", "Save the area now", 1.5)
                self.answer(imm, "yes", "Object %d is built" % obj, 2.0)

                # --- CANCEL ----------------------------------------------
                self.answer(imm, "build mob", "Which vnum")
                self.answer(imm, "cancel", "Build stopped")
                self.assertIn("You are", run(imm, "score"))     # commands work again

                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zwizard", PASSWORD)
                run(imm, "scroll 0")
                sheet = run(imm, f"mshow {mob}", 1.5)
                self.assertIn("short:    an old wizard", sheet)
                self.assertIn("race: elf   sex: male", sheet)
                self.assertIn("level: 10   alignment: 1000", sheet)
                self.assertIn("attack: punch", sheet)
                self.assertIn("act:        sentinel", sheet)
                self.assertIn("His robes are patched; his eyes are not.", sheet)

                sheet = run(imm, f"oshow {obj}", 1.5)
                self.assertIn("type: weapon   level: 5   weight: 4   cost: 3g", sheet)
                self.assertIn("class: spear   dice: 2d5", sheet)
                self.assertIn("wear:  take wield", sheet)

                here = run(imm, f"goto {lo}", 2.0)
                self.assertIn("The Wizard's Door", here)
                self.assertIn("A heavy oak door; iron-bound and old.", here)
                # Digging north walked the builder into the Inner Hall, so
                # that is where the mobile and the staff were placed.
                hall = run(imm, "north", 1.5)
                self.assertIn("The Inner Hall", hall)
                self.assertIn("An old wizard mutters to himself here.", hall)
                self.assertIn("An oak staff leans against the wall.", hall)


if __name__ == "__main__":
    unittest.main()
