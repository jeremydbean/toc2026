"""COMPARE in colour (owner, 2026-11-24): "green for good, red for bad".

The winner of each row, its edge and the verdict's pick are drawn in the
player's BETTER colour and the number that lost in their WORSE colour
(bright green and bright red unless they chose others); the "A instead
of B" line is A's side, gains green and losses red.
The colours are tokens, so with colour off -- or a screen reader on --
the words are exactly what they were. Synthetic characters only.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      skip_reason)

PW = "testpw12"
ME = "Zcolcmp"
IMM = "Zcolimm"
GREEN = "\x1b[92m"
RED = "\x1b[91m"
PLAIN_RED = "\x1b[31m"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

_SKIP = skip_reason()


def raw_reply(client, line: str, settle: float = 1.5) -> str:
    start = len(client.raw)
    client.command(line, settle)
    return client.raw[start:].decode("latin-1").replace("\r", "")


def plain(text: str) -> str:
    return ANSI.sub("", text)


def line_with(text: str, needle: str) -> str:
    return next(line for line in text.split("\n") if needle in line)


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class CompareColourLive(unittest.TestCase):
    def test_better_is_green_worse_is_red_and_off_is_plain(self):
        with LiveMud() as mud:
            for name in (ME, IMM):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
            patch_player_file(mud, ME, Levl=52, Race="dwarf~", Cla=3, Room=4207)
            patch_player_file(mud, IMM, Levl=70, Room=4207)
            with mud.connect(timeout=120) as me, mud.connect(timeout=120) as imm:
                login(me, ME, PW)
                login(imm, IMM, PW)
                imm.command("set skill %s all 100" % ME, 1.0)
                imm.command("set char %s str 22" % ME, 0.3)
                for vnum, key in ((9923, "moonray"), (756, "banner"),
                                  (29049, "starlight")):
                    imm.command("load obj %d 52" % vnum, 0.4)
                    imm.command("give %s %s" % (key, ME.lower()), 0.4)
                me.command("wield moonray", 0.5)
                me.command("wear banner", 0.5)

                # Starlight beats the worn banner: A wins.
                on = raw_reply(me, "compare starlight")
                verdict = line_with(on, "Verdict:")
                self.assertIn(GREEN + "A, Starlight", verdict, on)
                row = line_with(on, "Weapon dmg/round")
                self.assertRegex(row, re.escape(GREEN) + r"\s*[\d.]+" , on)
                self.assertRegex(row, re.escape(RED) + r"\s*[\d.]+", on)
                self.assertIn(GREEN + "A +", row, on)

                # The banner against Starlight: B wins. The winner is
                # still green; A's numbers, and what A gives up, are red.
                rev = raw_reply(me, "compare banner starlight")
                self.assertIn(GREEN + "B, Starlight", line_with(rev, "Verdict:"), rev)
                row = line_with(rev, "Weapon dmg/round")
                self.assertIn(GREEN + "B +", row, rev)
                self.assertRegex(row, r"Weapon dmg/round " + re.escape(RED), rev)
                self.assertIn("hit " + RED + "-", line_with(rev, "A instead of B"), rev)

                # Colour off: not one escape, and the same words.
                me.command("color off", 0.5)
                off = raw_reply(me, "compare starlight")
                self.assertNotIn("\x1b[", off, off)
                self.assertEqual(plain(on).strip(), off.strip())

                # The categories are the player's: BETTER can be any colour.
                me.command("color on", 0.5)
                listing = me.command("color", 1.0)
                self.assertRegex(listing, r"better\s+: bright_green")
                self.assertRegex(listing, r"worse\s+: bright_red")
                me.command("color better red", 0.5)
                mine = raw_reply(me, "compare starlight")
                self.assertIn(PLAIN_RED + "A, Starlight",
                              line_with(mine, "Verdict:"), mine)

    def test_a_character_saved_before_the_categories_gets_their_defaults(self):
        # A file from before 2026-11-24 has no Color 17 or 18 line. Those
        # slots used to start at 0, which is grey.
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcololder", PW)
                client.send("quit")
                client.wait_closed()
            path = mud.player_dir / "Zcololder"
            lines = path.read_text(encoding="latin-1").split("\n")
            kept = [line for line in lines
                    if not re.match(r"^Color (17|18) ", line)]
            self.assertLess(len(kept), len(lines), "the save wrote no Color 17/18")
            path.write_text("\n".join(kept), encoding="latin-1", newline="")
            with mud.connect(timeout=120) as client:
                login(client, "Zcololder", PW)
                listing = client.command("color", 1.0)
                self.assertRegex(listing, r"better\s+: bright_green")
                self.assertRegex(listing, r"worse\s+: bright_red")
                self.assertRegex(listing, r"room_name\s+: brown")


if __name__ == "__main__":
    unittest.main()
