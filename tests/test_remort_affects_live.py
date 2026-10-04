"""Remorting under a big spell, and the wreck that used to leave.

Reported by Alaric (2026-10-03): remort while empowered or titanic and
your hit points, mana and moves go thousands below zero, for good. The
remort reset the maxima to the new life's 200 and only then stripped the
spells, and affect_remove takes an APPLY_HIT/MANA/MOVE bonus back off the
maxima -- so it came off the 200. The remort's last_level of 0 then sent
the next login through reset_char's full reset, which wrote the negative
maxima into the permanent stats. He also had nothing to wear: the remort
folds outgrown gear into the stash and handed back nothing.

Now the spells come off with the gear, before the reset; reset_char never
derives a non-positive permanent maximum, and rebuilds a broken pool full;
and a remort ends with OUTFIT.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "testpw12"
TEMPLE = 4207


def hmv(mud: LiveMud, name: str) -> list[int]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return [int(v) for v in re.search(r"(?m)^HMV\s+(.*)$", text).group(1).split()]


def add_lines(mud: LiveMud, name: str, lines: list[str]) -> None:
    """Insert lines before the player section's End."""
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1").split("\n")
    end = next(i for i, line in enumerate(text) if line.strip() == "End")
    text[end:end] = lines
    path.write_text("\n".join(text), encoding="latin-1")


def add_objects(mud: LiveMud, name: str, records: list[str]) -> None:
    """Carried objects, inserted ahead of the character's own."""
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    marker = "\n#O\n" if "\n#O\n" in text else "\n#END"
    i = text.index(marker) + 1
    path.write_text(text[:i] + "\n".join(records) + "\n" + text[i:], encoding="latin-1")


def mud_ctx() -> LiveMud:
    return LiveMud()


def make(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not quit")


@unittest.skipIf(SKIP is not None, SKIP or "")
class RemortAffectTests(unittest.TestCase):
    def test_a_titanic_remort_keeps_its_maxima_and_is_dressed(self) -> None:
        with LiveMud() as mud:
            make(mud, "Ztitanic")
            # A level 54 under titanic: +3000 to each pool, which the saved
            # maxima include, as they would for a real character.
            patch_player_file(mud, "Ztitanic", Levl=54, Room=TEMPLE,
                              HMV="3020 3020 3100 3100 3100 3100",
                              HMVP="20 100 100")
            add_lines(mud, "Ztitanic", [
                "AffD 'titanic' 54 40 3000 13 0 0",
                "AffD 'titanic' 54 40 3000 12 0 0",
                "AffD 'titanic' 54 40 3000 14 0 0",
            ])
            with mud.connect(timeout=120) as client:
                login(client, "Ztitanic", PW)
                # Bare, as a character whose whole kit is outgrown would be.
                client.command("remove all", 1.2)
                client.command("drop all", 1.2)
                out = client.command("remort %s mage none human" % PW, 3.0)
                self.assertIn("equipped by the Gods", out, out)
                worn = client.command("equipment", 1.2)
                self.assertIn("dagger", worn.lower(), worn)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            hit, max_hit, mana, max_mana, move, max_move = hmv(mud, "Ztitanic")
            self.assertEqual((max_hit, max_mana, max_move), (200, 200, 200),
                             "the remort's maxima, untouched by the stripped spell")

            # And the next login -- a full reset, since a remort clears
            # last_level -- leaves them where they are.
            with mud.connect(timeout=120) as client:
                login(client, "Ztitanic", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertEqual(hmv(mud, "Ztitanic")[1::2], [200, 200, 200])

    def test_the_rest_of_a_remort_comes_through(self) -> None:
        """From the remort review: wimpy cut back, the outgrown-gear bag
        withdrawable however heavy (owner), psionics kept on the first
        remort, and a NODROP item never bagged."""
        with mud_ctx() as mud:
            make(mud, "Zreborn")
            patch_player_file(mud, "Zreborn", Levl=54, Room=TEMPLE, Wimp=800,
                              PsiKnown="torment~")
            # Two suits of clamshell scale mail (1000 weight each), far past
            # what a level 3 can lift, and a NODROP item over level.
            add_objects(mud, "Zreborn", [
                "#O\nVnum 6415\nNest 0\nWear -1\nLev  40\nEnd\n",
                "#O\nVnum 6415\nNest 0\nWear -1\nLev  40\nEnd\n",
                "#O\nVnum 30408\nNest 0\nWear -1\nEnd\n",   # the final Triforce piece
            ])
            with mud.connect(timeout=120) as client:
                login(client, "Zreborn", PW)
                client.command("remort %s mage none human" % PW, 3.0)
                carried = client.command("inventory", 1.2)
                self.assertIn("final Triforce piece", carried,
                              "a NODROP item stays carried, out of the bag")
                client.command("west", 1.2)              # the altar, where the stash is
                got = client.command("stash get gear", 2.0)
                self.assertNotIn("too full", got.lower(), got)
                self.assertNotIn("more than you can carry", got.lower(), got)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            text = (mud.player_dir / "Zreborn").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Wimp\s+40$", "wimpy cut to a fifth of 200")
            self.assertRegex(text, r"(?m)^Sk 1 'torment'$",
                             "a known power is given back on the first remort, "
                             "at 1% until practised")
            self.assertRegex(text, r"(?m)^Psionic\s+1$")

    def test_a_character_already_wrecked_is_rebuilt_at_login(self) -> None:
        """Alaric's own numbers: the stored permanent stats survived (200),
        the maxima did not. The next login rebuilds them, full."""
        with LiveMud() as mud:
            make(mud, "Zwrecked")
            patch_player_file(mud, "Zwrecked", Levl=3, Room=TEMPLE, NumRemorts=1,
                              LLev=0, HMVP="200 200 200",
                              HMV="-5515 -5515 -6945 -6945 -1385 -1385")
            with mud.connect(timeout=120) as client:
                login(client, "Zwrecked", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            hit, max_hit, mana, max_mana, move, max_move = hmv(mud, "Zwrecked")
            self.assertGreater(min(max_hit, max_mana, max_move), 0)
            self.assertEqual((hit, mana, move), (max_hit, max_mana, max_move),
                             "a rebuilt pool starts full")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Zwrecked's broken maxima rebuilt", log)


if __name__ == "__main__":
    unittest.main()
