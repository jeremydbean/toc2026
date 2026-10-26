"""Hyrule's guardians beaten by play, with no staff SLAY.

The walkthrough and the dungeon chain test have staff slay each guardian,
because what they prove is the way through. These prove the fights end the
way the chain needs, by the paths players use:

* melee: a warrior hacks Level 1's Aquamentus down, takes its key from the
  corpse, opens the treasure door and the chest, and has the first piece;
* caster: a mage burns Aquamentus down with spells alone;
* group: two grouped characters bomb Level 2's Dodongos -- two bombs each,
  half its health a bomb -- and the kill is shared.

Staff only stand the fixtures where they need to be and make the fights
short (fewer hit points on the guardian, sturdier fixtures); every blow
that lands is a player's.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zcamppass1"
TEMPLE = 4207
BOMBS = 30695

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DUNGEONS = {d["level"]: d for d in MANIFEST["dungeons"]}


def make(mud: LiveMud, name: str, **fields: object) -> None:
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


def hit_points(god, keyword: str) -> int:
    stat = god.must(f"stat mob {keyword}", "Hp:")
    match = re.search(r"Hp: (-?\d+)/", stat)
    assert match, stat
    return int(match.group(1))


def until(client, text: str, rounds: int, mark: int) -> bool:
    for _ in range(rounds):
        if text in client.transcript[mark:]:
            return True
        client.drain(1)
    return text in client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleCampaignLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.eagle = DUNGEONS[1]
        self.moon = DUNGEONS[2]

    def test_a_warrior_wins_the_first_piece_by_the_sword(self) -> None:
        lair, goal = self.eagle["boss_vnum"], self.eagle["goal_vnum"]
        with LiveMud() as mud:
            make(mud, "Zcampsword", Levl=8, Cla=3, Room=TEMPLE,
                 HMV="5000 5000 500 500 500 500", HMVP="5000 500 500")
            make(mud, "Zcampgod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zcampsword", PW)
                login(god, "Zcampgod", PW)
                god.sync(f"goto {lair}")
                god.must("set char aquamentus hp 400", "")
                god.must("restore aquamentus", "")
                god.must("set char zcampsword hitroll 40", "")
                god.must("set char zcampsword damroll 40", "")
                god.sync(f"goto {TEMPLE}")
                god.must(f"transfer zcampsword {lair}", "")
                self.assertEqual(lair, room_of(god, "zcampsword"))

                mark = len(hero.transcript)
                hero.sync("kill aquamentus", 30)
                self.assertTrue(until(hero, "Aquamentus is DEAD", 180, mark),
                                hero.transcript[-2000:])

                # Autoloot may have emptied the corpse already.
                hero.sync("get all corpse")
                self.assertIn("key", hero.sync("inventory").lower())
                hero.must("unlock east", "")
                hero.must("open east", "")
                inside = hero.sync("east")
                self.assertEqual(goal, room_of(god, "zcampsword"), inside)
                hero.sync("unlock chest")
                hero.sync("open chest")
                prize = hero.sync("get all chest")
                self.assertIn("first triforce shard", prize.lower(), prize)

    def test_a_mage_wins_the_fight_with_spells_alone(self) -> None:
        lair = self.eagle["boss_vnum"]
        with LiveMud() as mud:
            make(mud, "Zcampmage", Levl=8, Cla=0, Room=TEMPLE,
                 HMV="5000 5000 30000 30000 500 500", HMVP="5000 30000 500")
            add_skill(mud, "Zcampmage", "magic missile")
            make(mud, "Zcampgod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zcampmage", PW)
                login(god, "Zcampgod", PW)
                god.sync(f"goto {lair}")
                god.must("set char aquamentus hp 40", "")
                god.must("restore aquamentus", "")
                god.sync(f"goto {TEMPLE}")
                god.must(f"transfer zcampmage {lair}", "")
                hero.must("remove sword", "")
                mark = len(hero.transcript)
                for _ in range(80):
                    if "Aquamentus is DEAD" in hero.transcript[mark:]:
                        break
                    hero.sync("cast 'magic missile' aquamentus", 30)
                self.assertIn("Aquamentus is DEAD", hero.transcript[mark:],
                              hero.transcript[-2000:])

    def test_a_group_bombs_dodongo_and_shares_the_kill(self) -> None:
        lair = self.moon["boss_vnum"]
        with LiveMud() as mud:
            for name in ("Zcampone", "Zcamptwo"):
                make(mud, name, Levl=14, Room=TEMPLE,
                     HMV="5000 5000 500 500 500 500", HMVP="5000 500 500")
            make(mud, "Zcampgod", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as one, mud.connect(timeout=120) as two, \
                    mud.connect(timeout=120) as god:
                login(one, "Zcampone", PW)
                login(two, "Zcamptwo", PW)
                login(god, "Zcampgod", PW)
                two.must("follow zcampone", "")
                one.must("group zcamptwo", "")
                for name in ("zcampone", "zcamptwo"):
                    god.must(f"load obj {BOMBS}", "You create")
                    god.must(f"give bombs {name}", "You give")
                god.must(f"transfer zcampone {lair}", "")
                god.must(f"transfer zcamptwo {lair}", "")
                self.assertEqual(lair, room_of(god, "zcamptwo"))

                mark_one, mark_two = len(one.transcript), len(two.transcript)
                for _ in range(2):
                    one.sync("bomb dodongo", 30)
                    two.sync("bomb dodongo", 30)
                    if "Dodongo is DEAD" in one.transcript[mark_one:]:
                        break
                self.assertTrue(until(one, "Dodongo is DEAD", 60, mark_one),
                                one.transcript[-2000:])
                two.drain(2)
                self.assertIn("swallows it", one.transcript[mark_one:])
                self.assertIn("swallows it", two.transcript[mark_two:])
                # The kill is the group's: both are paid for it.
                self.assertIn("experience", two.transcript[mark_two:])


if __name__ == "__main__":
    unittest.main()
