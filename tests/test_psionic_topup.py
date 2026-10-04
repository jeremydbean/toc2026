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

    def test_an_offline_grant_to_an_owed_character_does_not_crash(self) -> None:
        """Loading a character for GRANTPSI ran the login top-up, which
        wrote to the blank descriptor of the offline load: a segfault."""
        with LiveMud() as mud:
            make(mud, "Zpsioff")
            make(mud, "Zpsiimm")
            patch_player_file(mud, "Zpsioff", Levl=30, NumRemorts=3, Room=TEMPLE,
                              Psionic=0)
            patch_player_file(mud, "Zpsiimm", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zpsiimm", PW)
                staff.send("grantpsi Zpsioff")
                staff.drain(3)
                staff.send("say still standing")
                staff.drain(2)
                seen = staff.transcript
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            self.assertIn("still standing", seen)
            # Above level 21 the grant is paid at once, into the file: two
            # of each discipline at three remorts.
            text = (mud.player_dir / "Zpsioff").read_text(encoding="latin-1")
            known = re.search(r"(?m)^PsiKnown (.*)~", text).group(1).split(",")
            self.assertEqual(len(known), 8, known)
            with mud.connect(timeout=120) as client:
                login(client, "Zpsioff", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())

    def test_a_remort_away_from_the_temple_ends_in_it(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zfarremort")
            patch_player_file(mud, "Zfarremort", Levl=54, NumRemorts=0, Room=4208,
                              Prac=7, Trai=3)
            with mud.connect(timeout=120) as client:
                login(client, "Zfarremort", PW)
                client.send(f"remort {PW} cleric none human")
                client.drain(4)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = (mud.player_dir / "Zfarremort").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Levl 3$")
            self.assertRegex(text, rf"(?m)^Room {TEMPLE}$")
            # Unspent practices and trains are kept, the first remort's
            # 17 and 10 added on top (owner, 2026-10-04).
            self.assertRegex(text, r"(?m)^Prac 24$")
            self.assertRegex(text, r"(?m)^Trai 13$")


if __name__ == "__main__":
    unittest.main()
