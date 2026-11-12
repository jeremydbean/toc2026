"""A mortal trusted with staff commands is logged like any player; an
immortal is not (owner, 2026-11-12: "trusted characters should actually be
logged also. just not immortals").

The balance feed (log/progress.tsv), the Hyrule log and the diary used to
leave out anybody at staff trust, so an owner's trusted test character's
play never reached them. They now leave out immortals by level alone.
Synthetic Z characters in a disposable fixture world.
"""
from __future__ import annotations

import time
import unittest

from live_mud import (SPARRING_GUARD, LiveMud, create_character, login, patch_player_file,
                      skip_reason)

SKIP = skip_reason()
PW = "Ztrustlog1"
HALLS = 4202            # not safe


def kill_a_one_hp_guard(staff, fighter, settle: float = 1.0) -> None:
    staff.must(f"load mob {SPARRING_GUARD}", "You create")
    staff.must("set char sparring level 3", "")
    staff.must("set char sparring hp 1", "")     # SET sets the maximum ...
    staff.must("restore sparring", "")           # ... RESTORE brings it to it
    fighter.drain(0.3)
    mark = len(fighter.transcript)
    fighter.send("kill sparring")
    deadline = time.monotonic() + 60
    while "is DEAD" not in fighter.transcript[mark:]:
        if time.monotonic() > deadline:
            raise AssertionError("the guard did not die:\n" + fighter.transcript[mark:][-800:])
        fighter.drain(0.5)
    fighter.drain(settle)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TrustedLoggingTests(unittest.TestCase):
    def test_a_trusted_mortal_is_logged_and_an_immortal_is_not(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Ztrustlog", "Zimmlog"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Ztrustlog", Levl=5, Tru=60, Room=HALLS,
                              HMV="9000 9000 500 500 500 500", HMVP="9000 500 500")
            patch_player_file(mud, "Zimmlog", Levl=70, Room=HALLS)
            with mud.connect(timeout=120) as trusted, mud.connect(timeout=120) as imm:
                login(trusted, "Ztrustlog", PW)
                login(imm, "Zimmlog", PW)
                imm.must("set char ztrustlog hitroll 40", "")
                kill_a_one_hp_guard(imm, trusted)
                kill_a_one_hp_guard(imm, imm)
                for client in (trusted, imm):
                    client.send("quit")
                    client.wait_closed()
            feed = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")
            diary = mud.player_dir / "diary" / "Ztrustlog"
            imm_diary = mud.player_dir / "diary" / "Zimmlog"
            diary_text = diary.read_text(encoding="latin-1") if diary.exists() else ""

        rewards = [row.split("\t") for row in feed.splitlines()
                   if row.split("\t")[1:2] == ["reward"]]
        levels = sorted(int(row[3]) for row in rewards)
        self.assertEqual(levels, [5], "the trusted level 5 is counted; the immortal is not")
        self.assertIn("Kills 1", diary_text, "the trusted mortal keeps a diary")
        self.assertFalse(imm_diary.exists(), "an immortal keeps none")


if __name__ == "__main__":
    unittest.main()
