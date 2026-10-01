"""A word that is exactly a social's name is that social.

Reported in play: POKE could not be used, because commands are looked up
first and by prefix, so it was taken as an abbreviation of POKER. COMB
went to COMBINE the same way, and staff lost WHINE to WHINER. A word
that is exactly a command's name is still that command, so the
deliberate abbreviation order the command table encodes is untouched.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


def social_names() -> list[str]:
    text = read("area", "social.are").replace("\r", "")
    body = text.split("#SOCIALS", 1)[1].split("\n#0", 1)[0]
    return [rec.strip("\n").split()[0].lower()
            for rec in re.split(r"\n\s*\n", body) if rec.strip()]


def command_names() -> list[str]:
    # Commented-out entries are not commands: COMBINE sat in the table
    # behind /* */ for years, and counting it made COMB look shadowed
    # when it never was.
    source = re.sub(r"/\*.*?\*/", " ", read("src", "interp.c"), flags=re.S)
    return re.findall(r'\{\s*"([^"]+)",\s*\w+,\s*\w+,\s*\w+,', source)


class SocialLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.interp = read("src", "interp.c")

    def test_the_shadowed_socials_are_the_ones_reported(self) -> None:
        """If this list grows, a new command has hidden a social; the
        fix below covers it, but somebody should know it happened."""
        commands = command_names()
        shadowed = sorted(
            social for social in social_names()
            if social not in commands
            and any(c.startswith(social) for c in commands))
        self.assertEqual(shadowed, ["comb", "poke", "whine"])

    def test_an_exact_social_beats_a_prefix_command(self) -> None:
        body = self.interp.split("void interpret(", 1)[1]
        lookup = body.index("cmd = cmd_tab_sn_lookup(command, trust);")
        guard = body.index("str_cmp( command, cmd_table[cmd].name )")
        self.assertLess(lookup, guard)
        block = body[guard:guard + 300]
        self.assertIn("social_exact_index( command ) >= 0", block)
        self.assertIn("found = false;", block)
        self.assertIn("cmd = -1;", block)

    def test_an_exact_command_still_wins(self) -> None:
        """The guard only fires when the match was a prefix: str_cmp is
        non-zero exactly when the typed word is not the command's name."""
        body = self.interp.split("void interpret(", 1)[1]
        self.assertIn("if ( found && str_cmp( command, cmd_table[cmd].name )",
                      body)

    def test_an_exact_social_beats_a_prefix_social(self) -> None:
        body = self.interp.split("bool check_social(", 1)[1].split("\n}", 1)[0]
        self.assertLess(body.index("social_tab_sn_lookup(command, 0)"),
                        body.index("social_exact_index( command )"))

    def test_the_exact_lookup_walks_the_loaded_table(self) -> None:
        body = self.interp.split("static int social_exact_index(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("i < social_count", body)
        self.assertIn("!str_cmp( name, social_table[i].name )", body)


if __name__ == "__main__":
    unittest.main()
