"""A skill typed by its full name is that skill, not a target.

Commands match on one word, so the rest of a skill's name was handed on
as the argument: EGO WHIP looked for somebody called "whip", FISTS OF
FURY for "of", CRANE DANCE for "dance", and in a fight every one of them
was answered "They aren't here." (Rockcrusher, 2026-10-30, in Azeroth).
PICK LOCK DOOR looked for a lock to pick. skip_command_name_tail() in
interp.c drops the rest of the name when it was typed. LOOK AT <thing>
is LOOK <thing> for the same session's reason.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Ztailpw1"
TEMPLE = 4207


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


class CommandNameTailSourceTests(unittest.TestCase):
    def test_every_tail_finishes_a_real_skill_name_of_a_real_command(self) -> None:
        interp = source("interp.c")
        table = interp[interp.index("command_name_tails[] ="):]
        table = table[:table.index("};")]
        tails = re.findall(r'\{ "([a-z]+)",\s*"([a-z ]+)"\s*\}', table)
        self.assertGreaterEqual(len(tails), 10)
        commands = set(re.findall(r'^\s*\{\s*"([^"]+)",\s*do_\w+', interp, re.M))
        skills = set(re.findall(r'^\s*"([a-z][a-z \']+)",', source("const.c"), re.M))
        for command, tail in tails:
            self.assertIn(command, commands, command)
            self.assertIn(f"{command} {tail}", skills, (command, tail))

    def test_the_tail_is_dropped_just_before_dispatch(self) -> None:
        interp = source("interp.c")
        self.assertIn("argument = skip_command_name_tail( cmd_table[cmd].name, argument );\n"
                      "    (*cmd_table[cmd].do_fun) ( ch, argument );", interp)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CommandNameTailLiveTests(unittest.TestCase):
    def test_full_skill_names_and_look_at(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Ztailmonk", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Ztailmonk", Levl=30, Cla=4, Room=TEMPLE,
                              HMV="300 300 300 300 300 300")
            path = mud.player_dir / "Ztailmonk"
            text = path.read_text(encoding="latin-1")
            end = text.index("\nEnd\n")
            text = (text[:end] + "\nSk 100 'fists of fury'\nSk 100 'ego whip'"
                    "\nSk 100 'crane dance'" + text[end:])
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Ztailmonk", PW)
                client.sync("scroll 0")
                client.sync("remove all")   # fists of fury wants empty hands
                # Out of a fight with no target, each says its own "whom?".
                self.assertIn("Who do you want to attack?", client.sync("fists of fury"))
                self.assertIn("Whose mind do you wish to warp?", client.sync("ego whip"))
                self.assertIn("Whose mind do you wish to warp?", client.sync("EGO Whip"))
                crane = client.sync("crane dance")
                self.assertNotIn("They aren't here", crane)
                # A target after the full name is still the target.
                self.assertIn("They aren't here", client.sync("fists of fury zzyzx"))
                # A word that only looks like the tail is left alone.
                self.assertIn("They aren't here", client.sync("ego whipper"))

                at = client.sync("look at self")
                self.assertNotIn("You do not see that here", at)
                self.assertEqual(at, client.sync("look self"))


if __name__ == "__main__":
    unittest.main()
