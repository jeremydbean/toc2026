"""A copy of the character before anything big happens to them.

Owner, 2026-10-04, after a remort left Alaric at -5515 hit points and the
only way back was a hand-built restore: before a remort, a death, a staff
ADVANCE or SET, a GRANTPSI, a COMBINE, a deletion or a login repair, the
character is saved and copied to player/versions/<Name>/ as
<Name>.<timestamp>.<reason>. PRESTORE lists those with their reason, and
the ordinary 30-copy rotation never prunes them.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zmilest1"
TEMPLE = 4207


class MilestoneSourceTests(unittest.TestCase):
    def test_every_big_moment_takes_a_copy(self) -> None:
        sources = {
            "remort": ("act_info.c", "player_snapshot_milestone( ch, \"remort\", true );"),
            "death": ("fight.c", "player_snapshot_milestone( victim, \"death\", true );"),
            "delete": ("act_comm.c", "player_snapshot_milestone( ch, \"delete\", true );"),
            "advance": ("act_wiz.c", "player_snapshot_milestone( victim, \"advance\", true );"),
            "staffset": ("act_wiz.c", "player_snapshot_milestone( victim, \"staffset\", true );"),
            "grantpsi": ("act_wiz.c", "player_snapshot_milestone( victim, \"grantpsi\", true );"),
            "combine": ("act_info.c", "player_snapshot_milestone( ch, \"combine\", true );"),
            "repair": ("handler.c", "player_snapshot_milestone( ch, \"repair\", false );"),
        }
        for reason, (name, call) in sources.items():
            with self.subTest(reason=reason):
                text = (ROOT / "src" / name).read_text(encoding="latin-1")
                self.assertIn(call, text)

    def test_the_remort_copy_is_taken_before_anything_changes(self) -> None:
        act_info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        body = act_info.split("void do_remort(", 1)[1]
        self.assertLess(body.index('player_snapshot_milestone( ch, "remort", true );'),
                        body.index("unequip_char(ch, worn[iWear]);"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class MilestoneLiveTests(unittest.TestCase):
    def test_advance_and_death_leave_labelled_copies(self) -> None:
        def run(client, command: str, settle: float = 1.5) -> str:
            client.drain(0.4)
            mark = len(client.transcript)
            client.send(command)
            client.drain(settle)
            return client.transcript[mark:]

        with LiveMud() as mud:
            for name, level in (("Zmilestone", 10), ("Zkeeper", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=TEMPLE)

            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as keeper:
                login(hero, "Zmilestone", PW)
                login(keeper, "Zkeeper", PW)
                run(keeper, "advance zmilestone 12", 2.0)
                time.sleep(1.1)                 # a second apart: one file each
                run(keeper, "slay zmilestone", 2.0)
                listing = run(keeper, "prestore zmilestone", 2.0)

            versions = mud.player_dir / "versions" / "Zmilestone"
            names = sorted(p.name for p in versions.iterdir()) if versions.is_dir() else []
            self.assertTrue(any(re.fullmatch(r"Zmilestone\.\d{8}_\d{6}\.advance", n)
                                for n in names), names)
            self.assertTrue(any(re.fullmatch(r"Zmilestone\.\d{8}_\d{6}\.death", n)
                                for n in names), names)
            # The advance copy holds the character as they were: level 10.
            advance = next(n for n in names if n.endswith(".advance"))
            self.assertRegex((versions / advance).read_text(encoding="latin-1"),
                             r"(?m)^Levl 10$")
            self.assertIn("before advance", listing, listing)
            self.assertIn("before death", listing, listing)


if __name__ == "__main__":
    unittest.main()
