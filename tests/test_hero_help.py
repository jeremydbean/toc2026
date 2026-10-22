"""HELP HEROQUEST must not offer commands the game does not have.

The topic in toc.are taught heroes to type HEROQUEST, LISTCLUE, RETRIEVED
and ENDQUEST at the questmaster, and HELP HEROLEVELS sent every new hero
to it. All four are commented out of the command table and their
functions are empty stubs, so Trentlin, on reaching level 50 on
2026-10-22, read the topic three times and was answered "Huh?" by
HEROQUEST and HEROQUEST REQUEST.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTERP = ROOT / "src" / "interp.c"
TOC = ROOT / "area" / "toc.are"
HERO_COMMANDS = ("heroquest", "listclue", "retrieved", "endquest")


def registered_commands() -> set[str]:
    text = re.sub(r"/\*.*?\*/", "", INTERP.read_text(encoding="latin-1"), flags=re.S)
    return set(re.findall(r'\{\s*"([^"]+)"\s*,\s*do_', text))


def help_topic(text: str, keyword: str) -> str:
    match = re.search(rf"^-?\d+ [^\n]*\b{keyword}\b[^\n]*~\n(.*?)\n~\n", text, re.M | re.S)
    if match is None:
        raise AssertionError(f"no help topic for {keyword}")
    return match.group(1)


class HeroHelpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.toc = TOC.read_text(encoding="latin-1")
        self.commands = registered_commands()

    def test_heroquest_topic_offers_no_missing_command(self) -> None:
        topic = help_topic(self.toc, "HEROQUEST")
        for command in HERO_COMMANDS:
            if command in self.commands:
                continue
            # Naming a missing command is fine only to say it is gone; a
            # usage line ("heroquest: This will start the quest") is not.
            self.assertNotRegex(topic, rf"(?im)^\s*{command}\b[^\n]*:",
                                f"HELP HEROQUEST teaches {command}, which is not a command")
        if "heroquest" not in self.commands:
            self.assertIn("AQUEST", topic, "point heroes at the quests that exist")

    def test_herolevels_does_not_send_heroes_to_a_missing_quest(self) -> None:
        topic = help_topic(self.toc, "HEROLEVELS")
        if "heroquest" not in self.commands:
            self.assertNotIn("HELP HEROQUEST", topic)
            self.assertIn("AQUEST", topic)


if __name__ == "__main__":
    unittest.main()
