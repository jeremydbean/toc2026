"""Staff notices name nobody to staff who could not see them.

Resurrection's notice named the caster and the risen, and the crafted
EMPOWER and TITANIC notices the user and the target, all at
LEVEL_IMMORTAL: a wizinvis implementor's casting reached every builder
(review, 2026-10-26). Each now goes out at the higher of the two
participants' staff_notice_level, through staff_notice_level_pair, as the
Wizinvis Leaves No Trace contract asks.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Znoticepw1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def add_skill(mud: LiveMud, name: str, skill: str) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    end = text.index("\nEnd\n")
    path.write_text(text[:end] + f"\nSk 100 '{skill}'" + text[end:], encoding="latin-1")


class NoticeSourceTests(unittest.TestCase):
    def test_no_named_notice_goes_out_at_a_fixed_level(self) -> None:
        resurrect = (ROOT / "src" / "resurrect.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertNotIn("wizinfo( note, LEVEL_IMMORTAL )", resurrect)
        for start in ("void do_titanic(", "void do_empower(", "void spell_empower(",
                      "void spell_titanic(", "void do_grantpsi("):
            body = wiz[wiz.index(start):]
            body = body[:body.index("\n}\n")]
            with self.subTest(fn=start):
                self.assertNotIn("wizinfo( note, LEVEL_IMMORTAL )", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class NoticeLiveTests(unittest.TestCase):
    def test_a_wizinvis_participant_is_not_named_below_their_level(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zvisimp", Levl=70, Room=TEMPLE,
                 HMV="900 900 9000 9000 500 500", HMVP="900 9000 500")
            add_skill(mud, "Zvisimp", "resurrection")
            make(mud, "Zvislisten", Levl=60, Room=TEMPLE)
            for name in ("Zvisone", "Zvistwo"):
                make(mud, name, Levl=20, Room=TEMPLE,
                     HMV="300 300 300 300 300 300", HMVP="300 300 300")
            with mud.connect(timeout=120) as imp, \
                    mud.connect(timeout=120) as listener, \
                    mud.connect(timeout=120) as one, \
                    mud.connect(timeout=120) as two:
                login(imp, "Zvisimp", PW)
                login(listener, "Zvislisten", PW)
                login(one, "Zvisone", PW)
                login(two, "Zvistwo", PW)
                for client in (imp, listener, one, two):
                    client.sync("scroll 0")
                imp.must("wizinvis 70", "vanish into thin air")
                listener.drain(1.0)
                mark = len(listener.transcript)   # the login notices came before

                # Hidden from a trust-60 listener: the staff TITANIC...
                imp.must("titanic zvisone", "titanic", "Titanic", "colossus")
                # ...and a resurrection the hidden implementor answers.
                imp.sync("slay zvistwo")
                two.drain(1.5)
                imp.must("cast resurrection corpse", "soul")
                two.drain(1.5)
                rose = two.sync("accept")
                self.assertIn("edge of life", rose, rose)
                listener.drain(2.0)
                heard = "\n".join(line for line in listener.transcript[mark:].splitlines()
                                  if "[WIZINFO]" in line)
                self.assertNotIn("Zvisimp", heard)
                self.assertNotIn("titanic", heard)
                self.assertNotIn("raised", heard)
                # Nor does the room hear the hidden caster's words.
                self.assertNotIn("utters the words", listener.transcript[mark:])

                # Visible again, the same listener is told.
                imp.must("wizinvis", "fade back into existence")
                imp.must("titanic zvistwo", "titanic", "Titanic", "colossus")
                listener.drain(2.0)
                self.assertIn("Zvisimp made Zvistwo titanic", listener.transcript)


if __name__ == "__main__":
    unittest.main()
