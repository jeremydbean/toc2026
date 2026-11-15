"""LFG and HELPER: finding a group, and players glad to help (2026-11-15).

Both opt-in. Played in a disposable world with synthetic Z characters:
WHO's tags, LFG LIST's levels and IGNORE, the helpers' one notice and its
rate limit, a group ending the mark, HELPER saved, and ADVENTURE's count.
Nothing under player/, gods/, heroes/, backups/ or log/ is touched.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zlfgpass1"
TEMPLE = 4207


def make(mud, name, **fields):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def who_line(said: str, name: str) -> str:
    for line in said.replace("\r", "").split("\n"):
        if name in line:
            return line
    return ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class LfgTests(unittest.TestCase):
    def test_lfg_and_helpers(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zlfgnew", Levl=4, Room=TEMPLE)
            make(mud, "Zlfghelp", Levl=20, Room=TEMPLE)
            make(mud, "Zlfgother", Levl=6, Room=TEMPLE)
            make(mud, "Zlfgfar", Levl=30, Room=TEMPLE)
            with mud.connect(timeout=120) as new, mud.connect(timeout=120) as hlp, \
                    mud.connect(timeout=120) as other, mud.connect(timeout=120) as far:
                login(new, "Zlfgnew", PW)
                login(hlp, "Zlfghelp", PW)
                login(other, "Zlfgother", PW)
                login(far, "Zlfgfar", PW)

                self.assertIn("level 10 or more", new.sync("helper"))
                self.assertIn("marked as a helper", hlp.sync("helper on"))

                mark = len(hlp.transcript)
                self.assertIn("looking for a group for an hour", new.sync("lfg"))
                hlp.sync("inventory")
                self.assertIn("[LFG] Zlfgnew, level 4", hlp.transcript[mark:])
                # Off and on again within ten minutes: helpers not told twice.
                self.assertIn("no longer marked", new.sync("lfg"))
                mark = len(hlp.transcript)
                new.sync("lfg on")
                hlp.sync("inventory")
                self.assertNotIn("[LFG]", hlp.transcript[mark:])
                far.sync("lfg on")

                said = other.sync("who")
                self.assertIn("(LFG) ", who_line(said, "Zlfgnew"), said)
                self.assertIn("(Helper) ", who_line(said, "Zlfghelp"), said)
                self.assertNotIn("(LFG)", who_line(said, "Zlfgother"), said)

                said = other.sync("lfg list")
                self.assertIn("Zlfgnew", said, said)
                self.assertNotIn("Zlfgfar", said, said)             # 24 levels away
                self.assertIn("Zlfghelp", said, said)
                self.assertIn("looking for a group near your level",
                              other.sync("adventure", timeout=30))

                # IGNORE hides each from the other, both ways.
                new.must("ignore zlfghelp", "ignor")
                self.assertNotIn("Zlfghelp", new.sync("lfg list"))
                self.assertNotIn("Zlfgnew", hlp.sync("lfg list"))
                new.sync("unignore zlfghelp")

                # A group ends the mark.
                followed = other.sync("follow zlfgnew")
                if "want any followers" in followed:
                    new.sync("nofollow")
                    followed = other.sync("follow zlfgnew")
                self.assertIn("You now follow", followed, followed)
                new.must("group zlfgother", "joins your group")
                self.assertNotIn("(LFG)", who_line(other.sync("who"), "Zlfgnew"))
                self.assertIn("in a group already", new.sync("lfg"))
                self.assertNotIn("Zlfgnew", far.sync("lfg list"))

                self.assertIn("Syntax: lfg", new.sync("lfg maybe"))
                hlp.must("save", "Saving")
                hlp.send("quit")
                hlp.wait_closed()

            text = (mud.player_dir / "Zlfghelp").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Helper 1$")
            self.assertNotRegex((mud.player_dir / "Zlfgnew").read_text(encoding="latin-1"),
                                r"(?m)^(Helper|Lfg)")
            with mud.connect(timeout=120) as hlp, mud.connect(timeout=120) as new:
                login(hlp, "Zlfghelp", PW)
                login(new, "Zlfgnew", PW)
                self.assertIn("(Helper) ", who_line(new.sync("who"), "Zlfghelp"))
                # The LFG mark was the sitting's; it did not come back.
                self.assertNotIn("(LFG)", who_line(new.sync("who"), "Zlfgnew"))
                self.assertIn("no longer", hlp.sync("helper off"))


class LfgSourceTests(unittest.TestCase):
    def test_last_in_the_table_and_saved_under_h(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        self.assertEqual(names.index("helper"), names.index("lfg") + 1)
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_h = save.split("case 'H':", 1)[1].split("case 'I':", 1)[0]
        self.assertIn('"Helper"', case_h)


if __name__ == "__main__":
    unittest.main()
