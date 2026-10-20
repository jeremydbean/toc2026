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

# Topics deliberately gated at a mortal level: each describes a command or
# channel the character cannot use below it, and a lower level asking
# should get nothing rather than a description of something they lack.
ALLOWED_GATES = {"TEACHLIST", "CGOS CASTLECHAT CC -", "HERO ="}

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
    # 2026-10-20, the October logs since the 1st:
    "hero": "hero status is reached",
    "herolevels": "hero status is reached",
    "herolevel": "hero status is reached",
    "exchange": "exchange experience for more practices",
    "despair": "despair",
    "mind leech": "mind leech",
    "mindleech": "mind leech",
    "shieldblock": "parrying with a shield",
    "block": "parrying with a shield",
    "hitroll": "how often your blows land",
    "damroll": "how often your blows land",
    "keepsake": "questmaster's sigil",
    "multiclass": "no multiclassing",
    "start": "mud school",
    "gods": "run times of chaos",
    "god": "run times of chaos",
}


def one_argument(s: str) -> tuple[str, str]:
    """ROM's one_argument: a quoted run is one word; words are lowercased."""
    s = s.lstrip(" ")
    if not s:
        return "", ""
    end = " "
    if s[0] in "'\"":
        end, s = s[0], s[1:]
    i = s.find(end)
    if i < 0:
        return s.lower(), ""
    return s[:i].lower(), s[i + 1:].lstrip(" ")


def words_of(s: str) -> list[str]:
    out = []
    while True:
        word, s = one_argument(s)
        if not word:
            return out
        out.append(word)


def is_name(string: str, namelist: str) -> bool:
    """handler.c's is_name: every word asked must prefix some keyword."""
    names = words_of(namelist)
    for part in words_of(string):
        for name in names:
            if string.lower() == name:
                return True
            if name.startswith(part):
                break
        else:
            return False
    return True


def mortal_help_topics() -> list[tuple[str, str]]:
    """(keyword line, text) of every help any mortal may read, in load order."""
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
            if int(m.group(1)) <= 0:
                out.append((m.group(2), m.group(3)))
    return out


def lookup(topics, asked: str) -> str | None:
    """do_help's two passes: an exact keyword (split on spaces), then is_name."""
    argall = " ".join(words_of(asked))
    for keys, text in topics:
        if any(argall == w.lower() for w in keys.split()):
            return text
    for keys, text in topics:
        if is_name(argall, keys):
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

    def test_no_player_topic_is_locked_behind_a_level(self) -> None:
        """A level between 1 and 59 on a help hides it from every mortal
        below that level. DESPAIR sat at 25, the psionics at 15, EXCHANGE
        and HEROLEVELS at 51 -- and a remort is level 3 holding its
        psionics, so it could not read about its own powers."""
        locked = []
        listed = [l.strip() for l in (ROOT / "area" / "area.lst").read_text(encoding="latin-1").splitlines()]
        for name in listed:
            path = ROOT / "area" / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="latin-1")
            if "#HELPS" not in text:
                continue
            helps = text[text.index("#HELPS"):]
            helps = helps[:helps.index("$~")] if "$~" in helps else helps
            for m in re.finditer(r"^(\d+) ([^~\n]+)~$", helps, re.M):
                if 1 < int(m.group(1)) < 60 and m.group(2) not in ALLOWED_GATES:
                    locked.append(f"{path.name}: {m.group(1)} {m.group(2)}")
        self.assertEqual([], locked)

    def test_help_suggests_a_near_keyword(self) -> None:
        source = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        body = source[source.index("void do_help( CHAR_DATA *ch, char *argument )"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("help_suggest( ch, argall )", body)
        self.assertNotIn('send_to_char( "No help on that word', body)

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
                self.assertIn("hero status is reached", ask("help hero").lower())
                self.assertIn("despair", ask("help despair").lower())
                self.assertIn("Did you mean: PRAY", ask("help prayy"))
                self.assertIn("Did you mean:", ask("help warruor"))
                self.assertIn("No help on that word.", ask("help zzqqxx"))
                self.assertNotIn("Did you mean", ask("help zzqqxx"))


if __name__ == "__main__":
    unittest.main()
