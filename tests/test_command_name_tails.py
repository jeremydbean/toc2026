"""A skill typed by its full name is that skill, not a target.

Commands match on one word, so the rest of a skill's name was handed on
as the argument: EGO WHIP looked for somebody called "whip", FISTS OF
FURY for "of", CRANE DANCE for "dance", and in a fight every one of them
was answered "They aren't here." (Rockcrusher, 2026-10-30, in Azeroth).
PICK LOCK DOOR looked for a lock to pick. full_name_command()
in interp.c takes the whole name as typed. LOOK AT <thing>
is LOOK <thing> for the same session's reason. A whole name is chosen
before the prefix lookup, so MIND LEECH no longer runs MINDBLAST, which
"mind" begins (review, 2026-10-30).
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
    def test_every_full_name_is_a_real_skill_and_command(self) -> None:
        interp = source("interp.c")
        table = interp[interp.index("full_command_names[] ="):]
        table = table[:table.index("};")]
        rows = re.findall(r'\{ "([a-z ]+)",\s*"([a-z ]+)"\s*\}', table)
        self.assertGreaterEqual(len(rows), 15)
        commands = set(re.findall(r'^\s*\{\s*"([^"]+)",\s*do_\w+', interp, re.M))
        skills = set(re.findall(r'^\s*"([a-z][a-z \']+)",', source("const.c"), re.M))
        for phrase, command in rows:
            self.assertIn(" ", phrase, phrase)
            self.assertIn(command, commands, command)
            # The phrase is the skill's name, or the one-word skill split
            # the way players type it (MIND BLAST for mindblast).
            self.assertTrue(phrase in skills or phrase.replace(" ", "") in skills,
                            (phrase, command))

    def test_a_whole_name_is_chosen_before_the_prefix_lookup(self) -> None:
        interp = source("interp.c")
        body = interp[interp.index("static void interpret_body( CHAR_DATA *ch, char *argument )\n{"):]
        self.assertLess(body.index("full_name_command( command, argument, trust, &rest )"),
                        body.index("cmd_tab_sn_lookup(command, trust)"))

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

    def test_mind_leech_is_not_mindblast_and_costs_what_it_should(self) -> None:
        """MIND LEECH ran MINDBLAST: "mind" begins mindblast, which comes
        first in the table, and spent its 50 mana (review, 2026-10-30)."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Ztailpsi", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Ztailpsi", Levl=40, Room=TEMPLE,
                              HMV="300 300 100 100 300 300")
            path = mud.player_dir / "Ztailpsi"
            text = path.read_text(encoding="latin-1")
            end = text.index("\nEnd\n")
            text = (text[:end] + "\nSk 100 'mindblast'\nSk 100 'mind leech'"
                    "\nSk 100 'mindbar'\nSk 100 'door bash'" + text[end:])
            path.write_text(text, encoding="latin-1")

            def mana(reply: str) -> int:
                return int(re.findall(r"(\d+)m ", reply)[-1])

            with mud.connect(timeout=120) as client:
                login(client, "Ztailpsi", PW)
                client.sync("scroll 0")
                reply = client.sync("mind leech")
                self.assertIn("Who do you want to leech?", reply)
                self.assertNotIn("mindblast", reply)
                self.assertEqual(mana(reply), 100, "nothing spent")
                self.assertIn("Who do you want to leech?", client.sync("MIND LEECH"))
                self.assertIn("They aren't here", client.sync("mind leech zzyzx"))

                bar = client.sync("mind bar")
                self.assertNotIn("mindblast", bar)
                before = mana(bar)

                self.assertIn("Bash what door?", client.sync("door bash"))
                self.assertNotIn("bash here", client.sync("door bash north"))

                # MIND BLAST is still mindblast, at its own price.
                blast = client.sync("mind blast")
                self.assertIn("mindblast", blast)
                self.assertEqual(before - mana(blast), 50)


if __name__ == "__main__":
    unittest.main()
