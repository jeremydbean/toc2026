"""Remort psionics, end to end (owner, 2026-10-04).

* Every power starts at 1% and is trained with Salir -- one handed back
  from an earlier life too -- and one already held is never raised by a
  login (it was: "below 75, make it 75" at every login).
* A character remorted before remorts handed psionics out (Bongaboy:
  three remorts, none) is topped up to their due at login -- two of each
  discipline at three remorts -- with the awakening.
* The awakening's long message is for new powers only: a grant that finds
  the character already holding their due hands back what they had and
  says so power by power.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zpsitop1"
TEMPLE = 4207
SETS = [["ego whip", "torment", "nightmare", "mindblast"],
        ["astral walk", "shift", "project", "telekinesis"],
        ["mindbar", "psionic armor", "psychic shield", "transfusion"],
        ["clairvoyance", "confuse", "mind leech", "enervate", "pyrotechnics"]]


def make(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not quit")


@unittest.skipIf(SKIP is not None, SKIP or "")
class PsionicTopUpTests(unittest.TestCase):
    def test_a_three_remort_character_with_none_is_topped_up(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpsiowed")
            patch_player_file(mud, "Zpsiowed", Levl=30, NumRemorts=3, Room=TEMPLE,
                              Psionic=0)
            with mud.connect(timeout=120) as client:
                login(client, "Zpsiowed", PW)
                self.assertIn("Salir, The Monk of the Way", client.transcript)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            text = (mud.player_dir / "Zpsiowed").read_text(encoding="latin-1")
            known = re.search(r"(?m)^PsiKnown (.*)~", text).group(1).split(",")
            for psi_set in SETS:
                held = [p for p in psi_set if p in known]
                self.assertEqual(len(held), 2, (psi_set, known))
                for power in held:
                    self.assertRegex(text, rf"(?m)^Sk +1 '{power}'$",
                                     "a new power starts at 1%")
            self.assertRegex(text, r"(?m)^Psionic\s+1$")

    def test_a_character_holding_their_due_gets_no_awakening(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpsiheld")
            patch_player_file(mud, "Zpsiheld", Levl=30, NumRemorts=2, Room=TEMPLE,
                              Psionic=1,
                              PsiKnown="torment,telekinesis,mindbar,mind leech~")
            with mud.connect(timeout=120) as client:
                login(client, "Zpsiheld", PW)
                seen = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # Handed back, one by one, at 1% like any power not yet practised.
            self.assertIn("Your mind remembers mind leech from an earlier life.", seen)
            self.assertNotIn("Salir, The Monk of the Way", seen)
            text = (mud.player_dir / "Zpsiheld").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Sk 1 'mind leech'$")

            # And a login never raises a power the character holds: the
            # restore read "below 75, make it 75" at every login.
            with mud.connect(timeout=120) as client:
                login(client, "Zpsiheld", PW)
                again = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertNotIn("from an earlier life", again)
            text = (mud.player_dir / "Zpsiheld").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Sk 1 'mind leech'$")


if __name__ == "__main__":
    unittest.main()
