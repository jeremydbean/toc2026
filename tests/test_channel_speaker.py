"""A mobile speaks under its short description, not its keyword list.

The say journal, the HISTORY rings and the Comm.Channel GMCP feed all took
ch->name as the speaker, and a mobile's name is its keywords: the
dashboard's Chat view showed a shopkeeper saying "I don't trade with folks
I can't see" as "merchant shopkeeper moustache moustached" (2026-10-09).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ChannelSpeakerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.comm = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")

    def test_a_mobile_is_named_by_its_short_description(self) -> None:
        helper = self.comm[self.comm.index("static const char *channel_speaker("):]
        helper = helper[:helper.index("\n}\n")]
        self.assertIn("IS_NPC( ch )", helper)
        self.assertIn("ch->short_descr", helper)

    def test_no_channel_names_a_speaker_by_keywords(self) -> None:
        self.assertNotRegex(self.comm, r"gmcp_send_channel\([^;]*, ch->name, argument \);")
        self.assertIn('channel_journal_record( "say", channel_speaker( ch ), argument );',
                      self.comm)

    def test_a_questmasters_patter_is_not_journaled(self) -> None:
        """Owner, 2026-11-24: Questor Thews was 415 of 416 says on the
        website's chat log."""
        guard = 'if ( !IS_NPC( ch ) || ch->desc != NULL || !IS_SET( ch->act, ACT_QUESTM ) )\n' \
                '        channel_journal_record( "say", channel_speaker( ch ), argument );'
        self.assertIn(guard, self.comm)
        self.assertIn("line->name = str_dup( channel_speaker( ch ) );", self.comm)


if __name__ == "__main__":
    unittest.main()
