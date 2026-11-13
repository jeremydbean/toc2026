"""CONSIDER counts a Hyrule guardian's own attack (owner, 2026-11-13).

On 2026-11-12 CONSIDER told a level 40 that Digdogger would need "about
12 rounds" to kill them, and it did it in about three: CONSIDER counted
the guardian's melee and nothing else, and every four seconds its roll
(spec_hyrule_guardian's volley, Ganon's fireballs in spec_ganon) lands
beside the melee, through no parry. gear_consider_fight now adds
guardian_special_expected_per_round (special.c): the volley the fight
would throw now (the same hyrule_guardian_volley_now the special uses),
PULSE_VIOLENCE / PULSE_MOBILE volleys a round, each blow through
damage()'s own steps (blow_landed_expected) and shared among the members
of the fight it picks from at random.

The live test reads the consider rows in log/progress.tsv: a lone player
takes the whole volley, the same player grouped with a second takes half
of it -- the melee does not change -- so the difference is half the
volley CONSIDER says it counted.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_hyrule_area as gen  # noqa: E402

PW = "Zcgpass1"
DIGDOGGER = gen.BOSS_MOBS[5]


def considered(text: str) -> list:
    return [line.split("\t") for line in text.splitlines()
            if line.split("\t")[1:2] == ["consider"]]


class ConsiderGuardianSourceTests(unittest.TestCase):
    def test_the_fight_and_consider_share_the_volley(self) -> None:
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        spec = special.split("bool spec_hyrule_guardian(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hyrule_guardian_volley_now(", spec)
        expect = special.split("double guardian_special_expected_per_round(", 1)[1]
        expect = expect.split("\n}\n", 1)[0]
        for piece in ("hyrule_guardian_volley_now(", "blow_landed_expected(",
                      "PULSE_VIOLENCE / PULSE_MOBILE", "GANON_FIREBALLS",
                      "GANON_FIREBALL_MIN", "GANON_FIREBALL_MAX", "spec_ganon"):
            self.assertIn(piece, expect, piece)
        gear = (ROOT / "src" / "gear_compare.c").read_text(encoding="latin-1")
        fight = gear.split("void gear_consider_fight(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("guardian_special_expected_per_round( victim, ch )", fight)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConsiderGuardianLiveTests(unittest.TestCase):
    def test_consider_counts_digdoggers_roll(self) -> None:
        players = ("Zcgplay", "Zcgally")
        with LiveMud(fixtures=True) as mud:
            for name in ("Zcgstaff",) + players:
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcgstaff", Levl=70, Room=SPARRING_FLOOR)
            for name in players:
                patch_player_file(mud, name, Levl=33, Room=SPARRING_FLOOR,
                                  HMV="900 900 300 300 300 300", HMVP="900 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player, \
                    mud.connect(timeout=120) as ally:
                login(staff, "Zcgstaff", PW)
                login(player, "Zcgplay", PW)
                login(ally, "Zcgally", PW)
                for client in (staff, player, ally):
                    client.sync("scroll 0")
                staff.must(f"load mob {DIGDOGGER}", "You create")
                staff.must(f"load mob {SPARRING_GUARD}", "You create")

                alone = player.must("consider digdogger", "level")
                found = re.search(r"own attack too: about (\d+) a round", alone)
                self.assertIsNotNone(found, alone)
                said = int(found.group(1))
                guard = player.must("consider sparring", "level")
                self.assertNotIn("own attack", guard)

                ally.must("follow zcgplay", "You now follow")
                player.must("group zcgally", "joins")
                grouped = player.must("consider digdogger", "level")
                found = re.search(r"own attack too: about (\d+) a round", grouped)
                self.assertIsNotNone(found, grouped)
                shared = int(found.group(1))
                for client in (ally, player, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")

        rows = considered(text)
        self.assertEqual(len(rows), 3, text)
        _, t_alone = float(rows[0][11]), float(rows[0][12])
        _, t_grouped = float(rows[2][11]), float(rows[2][12])
        # Digdogger, whole, rolls once a pulse: three quarters of a roll a
        # round, cut by the player's armour at most to its floor.
        count, low, high = gen.BOSS_VOLLEYS[5]
        self.assertLessEqual(said, 0.75 * count * high + 1, said)
        self.assertGreaterEqual(said, 0.75 * count * low * 0.5, said)
        # Grouped, the volley is shared between two and the melee is not:
        # the drop is half of what CONSIDER said it counted.
        self.assertAlmostEqual(shared, said / 2, delta=1.0, msg=(said, shared))
        self.assertAlmostEqual(t_alone - t_grouped, said / 2, delta=1.0,
                               msg=(t_alone, t_grouped, said))
        # The volley is most of what Digdogger does to a level 33.
        self.assertGreater(t_alone, said - 0.5, (t_alone, said))


if __name__ == "__main__":
    unittest.main()
