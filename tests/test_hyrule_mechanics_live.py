"""Hyrule's enemy and boss rules, played against the NES (the 2026-10-25
mechanics audit). Every check here failed on the code before it:

* Gohma falls only to an arrow -- SHOOT with the bow -- and no longer to a
  sword swung by somebody who happens to hold the bow;
* an arrow bursts a pols voice and a boomerang drops a keese every time,
  where the armour roll used to save one shot in six to ten;
* a patra's great eye cannot be touched until its ring of eyes is cut;
* a bubble cannot be harmed at all, and the fight with it ends at once;
* every Dodongo swallows a bomb for exactly half its health;
* the Blue Candle flares once a room and the Red as often as you like;
* the money game wants the worst sign's 40 gold, so a loss is paid whole.

The mobiles are loaded into the fixture world's sparring floor, which is
no safe room and holds nothing else; staff set their hit points small so
each check takes a blow or two, not a fight.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    SPARRING_FLOOR,
    SPARRING_GALLERY,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zmechpass1"
TEMPLE = 4207

GOHMA = 30223
PATRA = 32188          # band 9
BUBBLE = 32048         # band 9
POLS_VOICE = 32087     # band 8, level 50
KEESE = 31118          # band 9
DODONGO = 31184        # Level 5's
BOW, QUIVER, BOOMERANG = 30222, 30543, 30232
BLUE_CANDLE, RED_CANDLE = 30546, 30414
BOMBS = 30695
GAMBLE_ROOM = 30710


def make(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def hit_points(god, keyword: str) -> tuple[int, int]:
    stat = god.must(f"stat mob {keyword}", "Hp:")
    match = re.search(r"Hp: (-?\d+)/(\d+)", stat)
    assert match, stat
    return int(match.group(1)), int(match.group(2))


def load(god, vnum: int, keyword: str, hp: int) -> None:
    """A mobile in the room with `hp` hit points, whole."""
    god.must(f"load mob {vnum}", "You create")
    god.must(f"set char {keyword} hp {hp}", "")
    god.must(f"restore {keyword}", "")
    assert hit_points(god, keyword) == (hp, hp)


def give(god, hero: str, vnum: int, keyword: str) -> None:
    god.must(f"load obj {vnum}", "You create")
    god.must(f"give {keyword} {hero}", "You give")


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleMechanicsLiveTests(unittest.TestCase):
    def test_the_enemies_keep_the_nes_rules(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zmechhero", Levl=58, Room=SPARRING_FLOOR, NewGold=500,
                 HMV="20000 20000 1000 1000 1000 1000", HMVP="20000 1000 1000",
                 Hit=40, Dam=40)
            make(mud, "Zmechgod", Levl=70, Room=SPARRING_FLOOR)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zmechhero", PW)
                login(god, "Zmechgod", PW)
                hero.sync("scroll 0")
                god.sync(f"goto {SPARRING_FLOOR}")
                self.assertEqual(SPARRING_FLOOR, room_of(god, "zmechhero"))
                give(god, "zmechhero", BOW, "bow")
                give(god, "zmechhero", QUIVER, "quiver")
                give(god, "zmechhero", BOOMERANG, "boomerang")
                hero.must("wield bow", "wield")

                with self.subTest("an arrow bursts a pols voice every time"):
                    for _ in range(5):
                        load(god, POLS_VOICE, "pols", 2000)
                        shot = hero.sync("shoot pols", 30)
                        self.assertIn("bursts like a bubble", shot, shot)
                        self.assertIn("is DEAD", shot, shot)

                with self.subTest("Gohma: no blade finishes her, an arrow does"):
                    load(god, GOHMA, "gohma", 5)
                    hero.must("wield boomerang", "wield")
                    hero.must("wield bow", "wield")
                    mark = len(hero.transcript)
                    hero.sync("kill gohma", 30)
                    # Rounds go on until a blow would have killed her.
                    for _ in range(30):
                        if "only an arrow can finish" in hero.transcript[mark:]:
                            break
                        hero.drain(1)
                    self.assertIn("only an arrow can finish", hero.transcript[mark:])
                    self.assertNotIn("Gohma is DEAD", hero.transcript[mark:])
                    self.assertEqual(1, hit_points(god, "gohma")[0])
                    shot = hero.sync("shoot gohma", 30)
                    self.assertIn("Gohma is DEAD", shot, shot)

                with self.subTest("a boomerang drops a keese every time"):
                    hero.must("wield boomerang", "wield")
                    for _ in range(5):
                        load(god, KEESE, "keese", 2000)
                        thrown = hero.sync("shoot keese", 30)
                        self.assertIn("is DEAD", thrown, thrown)

                with self.subTest("a bubble cannot be harmed, and the fight ends"):
                    load(god, BUBBLE, "bubble", 500)
                    tried = hero.sync("kill bubble", 30)
                    self.assertIn("Nothing harms", tried, tried)
                    self.assertEqual((500, 500), hit_points(god, "bubble"))
                    self.assertIn("Fighting: (none)", god.must("stat char zmechhero", "Fighting"))
                    god.must("purge bubble", "")

                with self.subTest("a patra's eye is out of reach until the ring is cut"):
                    hero.must("wield sword", "wield")   # the starting sword
                    load(god, PATRA, "patra", 40)
                    hero.sync("kill patra", 30)
                    self.assertIn("eyes orbiting", hero.transcript)
                    self.assertEqual(40, hit_points(god, "patra")[0])
                    mark = len(hero.transcript)
                    for _ in range(120):
                        if "is DEAD" in hero.transcript[mark:]:
                            break
                        hero.drain(1)
                    tail = hero.transcript[mark:]
                    self.assertIn("is DEAD", tail, tail[-2000:])
                    self.assertLess(hero.transcript.index("last orbiting eye"),
                                    hero.transcript.index("Patra is DEAD")
                                    if "Patra is DEAD" in hero.transcript
                                    else len(hero.transcript))

                with self.subTest("every Dodongo swallows a bomb for half its health"):
                    load(god, DODONGO, "dodongo", 1000)
                    give(god, "zmechhero", BOMBS, "bombs")
                    mark = len(hero.transcript)
                    hero.sync("bomb dodongo", 30)
                    self.assertIn("swallows it", hero.transcript[mark:])
                    # Half of it at once; a tick's regeneration may follow.
                    self.assertLessEqual(hit_points(god, "dodongo")[0], 560)
                    hero.sync("bomb dodongo", 30)
                    for _ in range(10):
                        if "Dodongo is DEAD" in hero.transcript[mark:]:
                            break
                        hero.drain(1)
                    self.assertIn("is DEAD", hero.transcript[mark:])

                with self.subTest("the Blue Candle flares once a room; the Red at will"):
                    give(god, "zmechhero", BLUE_CANDLE, "blue")
                    hero.must("hold blue", "")
                    load(god, KEESE, "keese", 20000)
                    first = hero.sync("burn keese", 30)
                    self.assertIn("tongue of flame", first, first)
                    again = hero.sync("burn keese", 30)
                    self.assertIn("flared once in this room", again, again)
                    god.must("transfer zmechhero %d" % SPARRING_GALLERY, "")
                    god.must("transfer zmechhero %d" % SPARRING_FLOOR, "")
                    self.assertEqual(SPARRING_FLOOR, room_of(god, "zmechhero"))
                    self.assertIn("tongue of flame", hero.sync("burn keese", 30))
                    give(god, "zmechhero", RED_CANDLE, "red")
                    hero.must("hold red", "")
                    for _ in range(3):
                        self.assertIn("tongue of flame", hero.sync("burn keese", 30))
                    god.must("purge keese", "")

    def test_the_money_game_wants_the_worst_signs_stake(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zgambler", Levl=20, Room=GAMBLE_ROOM, NewGold=39)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zgambler", PW)
                refused = hero.sync("gamble left")
                self.assertIn("You need 40 gold to play", refused, refused)
                self.assertNotIn("You turn", refused, refused)


if __name__ == "__main__":
    unittest.main()
