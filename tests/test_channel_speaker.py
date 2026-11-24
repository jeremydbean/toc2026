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


def questmaster_formats(src: str) -> set[str]:
    """What quest.c has the questmaster say: each do_say( questman, ... )
    with a literal, and each with buf from the snprintf( buf, ... ) before
    it. Branches that fill buf several ways are listed by hand in
    webadmin/server.py; this catches every one it can see."""
    out = set()
    lit = r'"((?:[^"\\]|\\.)*)"'
    for m in re.finditer(r"do_say\(\s*questman\s*,", src):
        rest = src[m.end():]
        depth, i = 1, 0
        while depth and i < len(rest):
            depth += {"(": 1, ")": -1}.get(rest[i], 0)
            i += 1
        arg = rest[:i - 1].strip()
        if arg.startswith('"'):
            out.add("".join(re.findall(lit, arg)))
        elif arg == "buf":
            call = src[:m.start()][src[:m.start()].rfind("snprintf(buf"):]
            fmt = re.match(r'snprintf\(buf,\s*sizeof\(buf\),\s*((?:"(?:[^"\\]|\\.)*"\s*)+)', call)
            if fmt:
                out.add("".join(re.findall(lit, fmt.group(1))))
    return {bytes(f, "latin-1").decode("unicode_escape") for f in out}


class QuestorPatterTests(unittest.TestCase):
    """Review, 2026-11-24: the website hid every journaled say under
    "Questor Thews", a switched immortal's too. It hides only the patter,
    and the patter list must keep up with quest.c."""

    def test_the_website_knows_every_line_quest_c_gives_the_questmaster(self) -> None:
        server_src = (ROOT / "webadmin" / "server.py").read_text(encoding="utf-8")
        listed = server_src.split("QUESTOR_PATTER_FORMATS = (", 1)[1].split("\n)\n", 1)[0]
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        found = questmaster_formats(quest)
        self.assertGreater(len(found), 30)
        missing = sorted(f for f in found if repr(f) not in listed)
        self.assertEqual(missing, [], "add these to QUESTOR_PATTER_FORMATS")


if __name__ == "__main__":
    unittest.main()
