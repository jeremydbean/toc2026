"""The words players typed at HELP and got nothing for, and CHAT.

Three days of watched play (2026-10-17 to 20) were mined for HELP
arguments that matched no topic a mortal may read, and for commands the
game refused: QUESTING, QUESTPOINT, THEWS (the quest master's name),
ACCOUNT, FOURTH ATTACK, and nine refused CHATs. A mortal's HELP QUEST
also reached QUESTION by prefix, because the player topic was keyed
AQUEST alone. Each has a mortal-level topic now, HELP HERMIE reaches
BUFF (a player asked on gossip how she works), and CHAT is GOSSIP.

The shopkeeper who "doesn't trade with folks he can't see" now says why,
because two players checked AFFECTS and guessed.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zhelper1pass"

# word asked -> text the topic a mortal gets must contain
WANTED = {
    "quest": "questmaster",
    "questing": "questmaster",
    "questpoint": "questmaster",
    "questor": "questmaster",
    "thews": "questmaster",
    "account": "no accounts here",
    "hermie": "free healer",
    "chat": "gossip",
    "fourth attack": "no fourth attack",
}


def mortal_help_topics() -> list[tuple[list[str], str]]:
    """(keywords, text) of every help a mortal may read, in load order."""
    order = [l.strip() for l in (ROOT / "area" / "area.lst").read_text(encoding="latin-1").splitlines()]
    out = []
    for entry in order:
        path = ROOT / "area" / entry
        if not path.is_file():
            continue
        text = path.read_text(encoding="latin-1")
        if "#HELPS" not in text:
            continue
        body = text[text.index("#HELPS") + len("#HELPS"):]
        for m in re.finditer(r"^(-?\d+) ([^~\n]+)~\n(.*?)^~", body, re.M | re.S):
            level, keys, help_text = int(m.group(1)), m.group(2), m.group(3)
            if level > 0:
                continue
            words = [w.strip("'").lower() for w in re.findall(r"'[^']+'|\S+", keys)]
            out.append((words, help_text))
    return out


def lookup(topics, asked: str) -> str | None:
    """do_help's two passes: an exact keyword first, then a prefix."""
    asked = asked.lower()
    for words, text in topics:
        if asked in words:
            return text
    for words, text in topics:
        if any(w.startswith(asked) for w in words):
            return text
    return None


class HelpKeywordSourceTests(unittest.TestCase):
    def test_every_word_players_asked_for_has_a_topic(self) -> None:
        topics = mortal_help_topics()
        for asked, expect in WANTED.items():
            with self.subTest(asked=asked):
                text = lookup(topics, asked)
                self.assertIsNotNone(text, f"HELP {asked} finds nothing a mortal may read")
                self.assertIn(expect.lower(), text.lower())

    def test_chat_is_gossip(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        self.assertRegex(interp, r'\{\s*"chat",\s*do_gossip,')

    def test_the_keeper_says_why_they_cannot_see_you(self) -> None:
        source = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        refusal = source.index("I don't trade with folks I can't see")
        after = source[refusal:refusal + 1500]
        for cause in ("AFF_INVISIBLE", "AFF2_GHOST", "AFF_HIDE", "AFF2_STEALTH",
                      "AFF2_SHADOWMELD", "room_is_dark"):
            self.assertIn(cause, after, cause)
        self.assertIn("VISIBLE will fix that", after)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HelpKeywordLiveTests(unittest.TestCase):
    def test_a_mortal_gets_the_topics_and_chat_speaks(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zhelper", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zhelper", Levl=20, Room=4207)
            with mud.connect(timeout=120) as client:
                login(client, "Zhelper", PASSWORD)

                def ask(cmd: str, settle: float = 1.8) -> str:
                    mark = len(client.transcript)
                    client.send("scroll 0")
                    client.send(cmd)
                    client.drain(settle)
                    return client.transcript[mark:]

                self.assertIn("questmaster", ask("help quest"))
                self.assertNotIn("QUESTION", ask("help quest"))
                self.assertIn("questmaster", ask("help thews"))
                self.assertIn("free healer", ask("help hermie"))
                self.assertIn("no accounts here", ask("help account"))
                self.assertIn("no fourth attack", ask("help fourth attack"))
                self.assertIn("You gossip 'hello'", ask("chat hello"))


if __name__ == "__main__":
    unittest.main()
