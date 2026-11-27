"""SCREENREADER: text for reading aloud (2026-11-15).

No colour, and lines drawn only to decorate are left out, with every word
and number kept: the same SCORE, ACHIEVEMENTS and WHO read with it off and
on hold the same words. Saved; COLOR's own setting comes back when it is
turned off; GMCP Char.Status carries it. Synthetic Z characters in a
disposable world only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zreadpass1"
RULE = re.compile(r"^[\s\-=_*~+#|:.<>]{4,}$")
PROMPT = re.compile(r"<\d+hp \d+m \d+mv>")


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", PROMPT.sub(" ", text))


def lines(text: str) -> list[str]:
    return [l for l in PROMPT.sub("", text).replace("\r", "").split("\n")]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ScreenReaderTests(unittest.TestCase):
    def test_same_words_less_decoration(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zreader", PW)
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zreader", Levl=12, Room=4207)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zreader", PW)
                hero.sync("color off")
                hero.sync("scroll 0")
                before = {cmd: hero.sync(cmd, timeout=30) for cmd in ("score", "achievements", "who", "autolist", "channels")}
                said = hero.sync("screenreader")
                self.assertIn("Screen reader mode is on", said, said)
                for cmd, plain in before.items():
                    read = hero.sync(cmd, timeout=30)
                    self.assertNotIn("\x1b", read, cmd)
                    self.assertEqual(words(plain), words(read), cmd)
                    for line in lines(read):
                        self.assertIsNone(RULE.match(line), (cmd, line))
                    self.assertLessEqual(len(lines(read)), len(lines(plain)), cmd)
                # Something decorative really went: SCORE's rules and box,
                # the toggles' underlines.
                for cmd in ("score", "autolist", "channels"):
                    self.assertTrue(any(RULE.match(l) for l in lines(before[cmd])), cmd)
                self.assertTrue(any(l.strip().startswith("|") for l in lines(before["score"])))
                hero.must("save", "Saving")
                hero.send("quit")
                hero.wait_closed()
            self.assertRegex((mud.player_dir / "Zreader").read_text(encoding="latin-1"),
                             r"(?m)^ScreenReader 1$")
            with mud.connect(timeout=120) as hero:
                login(hero, "Zreader", PW)
                hero.sync("color on")
                mark = len(hero.raw)
                hero.sync("color gossips orange")
                self.assertNotIn(b"\x1b[", hero.raw[mark:])     # still on: no colour
                self.assertIn("is off", hero.sync("screenreader off"))
                mark = len(hero.raw)
                hero.sync("color gossips orange")
                self.assertIn(b"\x1b[38;5;208m", hero.raw[mark:])  # COLOR ON again
                self.assertIn("Syntax", hero.sync("screenreader maybe"))


class ScreenReaderSourceTests(unittest.TestCase):
    def test_gmcp_and_table(self) -> None:
        gmcp = (ROOT / "src" / "gmcp.c").read_text(encoding="utf-8")
        status = gmcp.split('"Char.Status", json', 1)[0][-1500:]
        self.assertIn('\\"reader\\":', status)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        self.assertEqual(names.index("screenreader"), names.index("helper") + 1)


if __name__ == "__main__":
    unittest.main()


DUMMY_ROOM = 2419        # the training dummy's arena (area/dummy.are)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CombatLinesTests(unittest.TestCase):
    """SCREENREADER COMBAT (2026-11-27): how many routine blow lines come.
    FULL every one; BRIEF your own and those at you that land; QUIET none
    but a big one at you. Deaths, fleeing, warnings, prompts and speech
    come at every setting."""

    def test_brief_and_quiet_leave_out_blows_and_nothing_else(self) -> None:
        pw = "Zcombatpw1"
        blow = re.compile(r"(?i)\b(hits|misses|grazes|scratches|wounds|mauls|decimates|devastates|"
                          r"maims|mutilates|disembowels|dismembers|massacres|mangles|demolishes|"
                          r"annihilates|obliterates|eradicates|destroys|injures)\b.*dummy")
        with LiveMud() as mud:
            for name, level in (("Zfighter", 30), ("Zwatcher", 30)):
                with mud.connect(timeout=120) as c:
                    create_character(c, name, pw)
                    c.send("quit")
                    c.wait_closed()
                patch_player_file(mud, name, Levl=level, Room=DUMMY_ROOM,
                                  HMV="3000 3000 1000 1000 1000 1000", HMVP="3000 1000 1000")
            with mud.connect(timeout=120) as fighter, mud.connect(timeout=120) as watcher:
                login(fighter, "Zfighter", pw)
                login(watcher, "Zwatcher", pw)
                for c in (fighter, watcher):
                    c.sync("scroll 0")
                # Full: the watcher sees the fight.
                fighter.send("kill dummy")
                watcher.drain(6.0)
                self.assertRegex(watcher.transcript, r"Zfighter's .*dummy", "full shows bystanders' blows")
                # Brief: not other people's blows.
                self.assertIn("brief", watcher.sync("screenreader combat brief"))
                mark = len(watcher.transcript)
                watcher.drain(6.0)
                self.assertNotRegex(watcher.transcript[mark:], r"Zfighter's .*dummy")
                # Quiet: not even your own; FLEE and the prompt still come.
                self.assertIn("quiet", fighter.sync("screenreader combat quiet"))
                mark = len(fighter.transcript)
                fighter.drain(6.0)
                self.assertNotRegex(fighter.transcript[mark:], blow)
                fled = fighter.sync("flee", timeout=30)
                self.assertRegex(fled, r"(?i)flee|escape|panic", fled)
                self.assertIn("hp", fighter.sync("look"))
                self.assertIn("Combat lines: quiet", fighter.sync("screenreader combat"))
                fighter.sync("save")
            saved = (mud.player_dir / "Zfighter").read_text(encoding="latin-1")
        self.assertIn("\nCombatVerb 2\n", saved)
