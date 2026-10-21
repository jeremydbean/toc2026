"""SHOOT into the next room takes the ordinary damage path.

Audit 2026-10-21: an arrow that hit a mobile in an adjacent room took
2d4 off its hit points by hand, so piercing immunity, sanctuary and the
rest never applied. It goes through damage() now, with the fight that
starts between two rooms undone afterwards.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zarrow1pass"
HALLS = 4202            # Halls of Healing: not safe; north is 4203
NORTH_HALL = 4203
WORKER = 12002          # sentinel, so it stays put
MOBLIN = 30226          # hyrule.are: sentinel, immune to weapons (D)
SWORD = 3702            # made a bow below (weapon class 9)


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class RangedShotSourceTests(unittest.TestCase):
    def test_the_cross_room_hit_calls_damage(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        shoot = fight[fight.index("void do_shoot"):fight.index("void do_steel_fist")]
        self.assertNotIn("victim->hit -= dice(2,4)", shoot)
        self.assertIn("damage( ch, victim, dice(2,4), gsn_archery, DAM_PIERCE );", shoot)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RangedShotLiveTests(unittest.TestCase):
    def test_an_arrow_respects_immunity_and_leaves_no_fight(self) -> None:
        with LiveMud() as mud:
            for name in ("Zarcher", "Zwarden"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zarcher", Levl=40, Room=HALLS)
            patch_player_file(mud, "Zwarden", Levl=70, Room=NORTH_HALL)

            with mud.connect(timeout=120) as archer, mud.connect(timeout=120) as warden:
                login(archer, "Zarcher", PASSWORD)
                login(warden, "Zwarden", PASSWORD)
                run(archer, "scroll 0")
                run(warden, "scroll 0")
                run(warden, "set skill zarcher archery 100")
                run(warden, "goto %d" % HALLS)
                run(warden, "load obj %d" % SWORD)
                run(warden, "set obj sword v0 9")
                run(warden, "set obj sword level 1")
                run(warden, "give sword zarcher")
                self.assertIn("wield", run(archer, "wield sword", 1.5).lower())
                run(warden, "goto %d" % NORTH_HALL)

                def hp(keyword: str) -> int:
                    stat = run(warden, "stat mob " + keyword, 1.4)
                    return int(re.search(r"Hp: (\d+)/", stat).group(1))

                def volley(keyword: str, n: int) -> None:
                    for _ in range(n):
                        archer.send("shoot " + keyword)
                        archer.drain(3.5)       # archery lag, then the reply

                # Immune to weapons: arrows land and do nothing.
                run(warden, "load mob %d" % MOBLIN)
                self.assertIn("weapon", run(warden, "stat mob moblin", 1.4))
                before = hp("moblin")
                volley("moblin", 3)
                self.assertEqual(hp("moblin"), before, archer.transcript[-800:])
                fighting = run(warden, "stat char zarcher", 1.4)
                self.assertIn("Fighting: (none)", fighting)

                # The control: without the immunity the same arrows hurt.
                run(warden, "purge")
                run(warden, "load mob %d" % WORKER)
                before = hp("worker")
                volley("worker", 3)
                self.assertLess(hp("worker"), before, archer.transcript[-800:])
                self.assertIn("Fighting: (none)", run(warden, "stat char zarcher", 1.4))


if __name__ == "__main__":
    unittest.main()
