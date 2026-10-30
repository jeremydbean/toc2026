"""The game guesses what a player means from what they can do.

Owner, 2026-10-30: make it smarter about what players mean, leaning to
commands they can use and spells they have, single words and multi-word
names alike.

- An abbreviation that begins a skill command the character lacks goes to
  the next command it begins that they have (MIND, for somebody holding
  mind leech but not mindblast, which comes first in the table).
- A multi-word skill may be abbreviated word by word (MI LE, CR DA BOB).
- CAST prefers the spells the caster knows (CAST CU for a level 1 cleric
  is cure light, not the cure blindness that comes first), and takes a
  name abbreviated word by word (CAST CU LI).
- A typo is answered with what they can do: their commands, the whole
  names of multi-word ones, and their own spells as CAST '<name>', each
  weighed word by word (CUER LIGHT, MND LEECH); a spell typed as a
  command is told how to cast it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zguesspw1"
TEMPLE = 4207


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def make(mud: LiveMud, name: str, skills: dict, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    end = text.index("\nEnd\n")
    lines = "".join(f"\nSk {pct} '{skill}'" for skill, pct in skills.items())
    path.write_text(text[:end] + lines + text[end:], encoding="latin-1")


def mana(reply: str) -> int:
    return int(re.findall(r"(\d+)m ", reply)[-1])


class CommandGuessingSourceTests(unittest.TestCase):
    def test_the_lean_only_moves_an_abbreviation(self) -> None:
        interp = source("interp.c")
        body = interp[interp.index("static void interpret_body( CHAR_DATA *ch, char *argument )\n{"):]
        lean = body[body.index("cmd = cmd_tab_sn_lookup(command, trust);"):]
        lean = lean[:lean.index("if (cmd != -1) found = true;")]
        self.assertIn("strlen( command ) > 1", lean, "a single letter keeps its default")
        self.assertIn("str_cmp( command, cmd_table[cmd].name )", lean, "a whole name is never moved")
        self.assertIn("!command_usable( ch, cmd )", lean)

    def test_nothing_irreversible_is_leaned_to(self) -> None:
        interp = source("interp.c")
        refused = interp[interp.index("static bool command_lean_refused("):]
        refused = refused[:refused.index("\n}\n")]
        for word in ("quit", "delete", "remort", "password", "sacrifice"):
            self.assertIn(f'"{word}"', refused)

    def test_cast_resolves_through_find_spell(self) -> None:
        magic = source("magic.c")
        cast = magic[magic.index("void do_cast( CHAR_DATA *ch, char *argument )"):]
        cast = cast[:cast.index("if(skill_table[sn].spell_fun == spell_null)")]
        self.assertIn("find_spell( ch, candidate )", cast)
        self.assertIn("( sn = find_spell( ch, arg1 ) )", cast)
        code = "\n".join(l for l in cast.splitlines() if not l.strip().startswith(("*", "/*")))
        self.assertNotIn("skill_lookup(", code)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CommandGuessingLiveTests(unittest.TestCase):
    def test_a_psionic_reaches_the_power_they_hold(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zguesspsi", {"mind leech": 100}, Levl=40,
                 HMV="300 300 100 100 300 300")
            with mud.connect(timeout=120) as client:
                login(client, "Zguesspsi", PW)
                client.sync("scroll 0")
                # MIND begins mindblast first, which they do not hold.
                reply = client.sync("mind")
                self.assertIn("Who do you want to leech?", reply)
                self.assertEqual(mana(reply), 100, "mindblast's 50 not spent")
                self.assertIn("Who do you want to leech?", client.sync("mi le"))
                self.assertIn("They aren't here", client.sync("mi le zzyzx"))
                self.assertIn("Who do you want to leech?", client.sync("mind le"))
                # A typo of a multi-word name they can use is named whole.
                self.assertIn("MIND LEECH", client.sync("mnd leech"))

    def test_a_cleric_casts_and_is_told_what_they_meant(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zguesscler", {"cure light": 75}, Levl=1, Cla=1,
                 HMV="20 300 1000 1000 300 300")
            with mud.connect(timeout=120) as client:
                login(client, "Zguesscler", PW)
                client.sync("scroll 0")
                def cured(reply: str) -> bool:
                    # Cast either way: healed, or the roll missed (which
                    # still spends). Mana is no measure: a tick can top a
                    # thousand back up before the prompt.
                    return "You feel better" in reply or "lost your concentration" in reply

                # CU begins cure blindness first, beyond a level 1 cleric.
                first = client.sync("cast cu")
                self.assertTrue(cured(first), first)
                self.assertTrue(cured(client.sync("cast cu li")))
                # A typo in the rest of a name of theirs is that spell.
                self.assertTrue(cured(client.sync("cast cure lgiht")))
                # A typo from the first word on is answered with it.
                self.assertIn("Did you mean 'cure light'?", client.sync("cast 'cuer ligt' self"))
                self.assertIn("Did you mean 'cure light'?", client.sync("cast cuer light"))

                self.assertIn("Spells are cast: CAST 'cure light'.", client.sync("cure light"))
                self.assertIn("CAST 'cure light'", client.sync("cuer light"))
                # A typo with nothing of theirs near it stays a plain Huh.
                self.assertIn("Huh?", client.sync("zqxvw"))


if __name__ == "__main__":
    unittest.main()
