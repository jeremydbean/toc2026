"""CONSIDER counts a patra's ring of eyes (review, 2026-11-20).

spec_hyrule_patra lashes every player fighting a patra each mobile pulse
-- each its own blow, as hard as the eyes left make it -- but CONSIDER's
model (guardian_special_expected_per_round, added in gear_consider_fight)
knew only the guardians' volleys and Ganon's fireballs: CONSIDER PATRA
warned of the ring and counted none of it. The ring is now counted from
the same range the special rolls (patra_ring_range), through damage()'s
steps (blow_landed_expected), PULSE_VIOLENCE / PULSE_MOBILE lashes a
round, and never shared: a group member takes as much as one alone. A
broken ring counts nothing.

Synthetic characters in a throwaway world, in the fixture's sparring room.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zprpass1"
PATRA = 32188
EYES = 8
RING = re.compile(r"ring's lash too: about (\d+) a round")


def considered(text: str) -> list:
    return [line.split("\t") for line in text.splitlines()
            if line.split("\t")[1:2] == ["consider"]]


def ring_range(level: int, eyes: int) -> tuple[int, int]:
    """patra_ring_range in special.c."""
    return max(1, level * eyes // (2 * EYES)), max(1, level * eyes // EYES)


class ConsiderPatraSourceTests(unittest.TestCase):
    def test_the_ring_and_consider_share_one_range(self) -> None:
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        spec = special.split("bool spec_hyrule_patra(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("patra_ring_range( mob, eyes, &lo, &hi )", spec)
        expect = special.split("double guardian_special_expected_per_round(", 1)[1]
        expect = expect.split("\n}\n", 1)[0]
        patra = expect[expect.index("spec_hyrule_patra"):expect.index("spec_ganon")]
        for piece in ("hyrule_patra_eyes_left( mob )", "patra_ring_range(",
                      "PULSE_VIOLENCE / PULSE_MOBILE", "DAM_ENERGY",
                      "guardian_expected_blow("):
            self.assertIn(piece, patra, piece)
        # Each member is lashed: the patra's figure is never divided.
        self.assertNotIn("targets", patra)
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        self.assertNotIn("is_hyrule_guardian( victim )\n        &&   ( special", info)
        self.assertEqual(info.count("consider_special_line( ch, victim );"), 2)

    def test_the_range_follows_the_eyes(self) -> None:
        lo8, hi8 = ring_range(56, 8)
        lo4, hi4 = ring_range(56, 4)
        self.assertEqual((lo8, hi8), (28, 56))
        self.assertEqual((lo4, hi4), (14, 28))
        self.assertEqual(ring_range(56, 1), (3, 7))


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConsiderPatraLiveTests(unittest.TestCase):
    def test_consider_counts_the_ring_for_each_member(self) -> None:
        players = ("Zprplay", "Zprally")
        with LiveMud(fixtures=True) as mud:
            for name in ("Zprstaff",) + players:
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zprstaff", Levl=70, Room=SPARRING_FLOOR)
            for name in players:
                patch_player_file(mud, name, Levl=50, Room=SPARRING_FLOOR,
                                  HMV="900 900 300 300 300 300", HMVP="900 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player, \
                    mud.connect(timeout=120) as ally:
                login(staff, "Zprstaff", PW)
                login(player, "Zprplay", PW)
                login(ally, "Zprally", PW)
                for client in (staff, player, ally):
                    client.sync("scroll 0")
                staff.must(f"load mob {PATRA}", "You create")
                level = int(re.search(r"Lv: (\d+)", staff.must("stat patra", "Lv:")).group(1))
                lo, hi = ring_range(level, EYES)

                alone = player.must("consider patra", "level")
                self.assertIn("out of reach while its ring of eyes orbits it", alone)
                found = RING.search(" ".join(alone.split()))
                self.assertIsNotNone(found, alone)
                said = int(found.group(1))
                # Three quarters of a lash a round, cut by armour at most to
                # its floor (half).
                self.assertLessEqual(said, 0.75 * hi + 1, (said, level))
                self.assertGreaterEqual(said, 0.75 * lo * 0.5 - 1, (said, level))

                ally.must("follow zprplay", "You now follow")
                player.must("group zprally", "joins")
                grouped = player.must("consider patra", "level")
                found = RING.search(" ".join(grouped.split()))
                self.assertIsNotNone(found, grouped)
                # Grouped, each member is lashed: nothing is shared.
                self.assertAlmostEqual(int(found.group(1)), said, delta=1)
                found = RING.search(" ".join(ally.must("consider patra", "level").split()))
                self.assertIsNotNone(found)
                self.assertAlmostEqual(int(found.group(1)), said, delta=1)

                # The fight: the ring lashes the fighter and the groupmate
                # beside them alike.
                for name in players:
                    staff.must(f"set char {name} hp 30000", "")
                    staff.sync(f"restore {name}")
                staff.must("set char zprplay hitroll 300", "hitroll set to 300")
                p_mark, a_mark = len(player.transcript), len(ally.transcript)
                player.send("kill patra")

                def broken_ring() -> bool:
                    # A groupmate who assists may cut the last eye; then the
                    # player sees only "... cuts down one of the eyes".
                    return any("cuts down the last orbiting eye" in c.transcript[m:]
                               for c, m in ((player, p_mark), (ally, a_mark)))

                for _ in range(90):
                    player.drain(1.0)
                    ally.drain(0.1)
                    if broken_ring():
                        break
                staff.sync("peace")
                player.drain(1.0)
                ally.drain(1.0)
                fought = player.transcript[p_mark:]
                self.assertTrue(broken_ring(), fought[-1500:])
                self.assertIn("tightens and lashes outward", fought, fought[-1500:])
                self.assertRegex(fought, r"patra's magic missile \w+ you")
                self.assertRegex(ally.transcript[a_mark:], r"patra's magic missile \w+ you",
                                 ally.transcript[a_mark:][-1500:])

                # The ring is broken: CONSIDER counts none of it.
                broken = player.must("consider patra", "level")
                self.assertNotIn("ring's lash", broken)
                self.assertNotIn("out of reach", broken)
                for client in (ally, player, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")

        rows = considered(text)
        self.assertGreaterEqual(len(rows), 4, text)
        # What the patra does to the player: the same alone and grouped.
        self.assertAlmostEqual(float(rows[0][12]), float(rows[1][12]), delta=1.0,
                               msg=(rows[0], rows[1]))


if __name__ == "__main__":
    unittest.main()
