"""The NES pass over Hyrule, played (wiki/hyrule-area.md, "The NES Pass:
Plan"): a dungeon map and compass that say where you are and where the
Triforce is; a hidden entrance that a bomb or a candle opens and nothing
else does; a money cave that pays once; and items that do what they did on
the NES.

A level 58 hero does the walking, so nothing in Hyrule's early bands
attacks; an immortal hands out the tools and moves the hero about.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Znespass1"
TEMPLE = 4207

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
WORLD = {room["coordinate"]: room for room in MANIFEST["overworld"]["rooms"]}
DUNGEONS = {dungeon["level"]: dungeon for dungeon in MANIFEST["dungeons"]}


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.5)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=TEMPLE, Attr="25 25 25 25 25")


def give(god, hero: str, vnum: int, keyword: str) -> None:
    run(god, f"load obj {vnum}")
    run(god, f"give {keyword} {hero}")


def rupee_cave(coordinate: str) -> dict:
    return next(landmark for landmark in WORLD[coordinate]["landmarks"]
                if landmark["type"] == "rupee")


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleNesLiveTests(unittest.TestCase):
    def test_the_map_shows_you_and_the_compass_points_the_way(self) -> None:
        moon = DUNGEONS[2]
        with LiveMud() as mud:
            make(mud, "Znesmapper", 58)
            make(mud, "Znesmapgod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Znesmapper", PASSWORD)
                login(god, "Znesmapgod", PASSWORD)
                give(god, "znesmapper", moon["map_vnum"], "map")
                give(god, "znesmapper", moon["compass_vnum"], "compass")

                away = run(hero, "look map")
                self.assertIn("Level 2: The Moon -- the dungeon map", away, away)
                self.assertIn("cannot show where you stand", away, away)
                lost = run(hero, "look compass")
                self.assertIn("will not settle", lost, lost)

                run(god, f"transfer znesmapper {moon['entrance_vnum']}", settle=2.0)
                plan = run(hero, "look map")
                self.assertIn("@ you", plan, plan)
                self.assertIn("B the guardian's chamber", plan, plan)
                self.assertIn("T the Triforce chest", plan, plan)
                # The guardian's door asks for Level 1's boomerang.
                self.assertIn("boomerang, from Level 1's chest", plan, plan)
                grid = [line for line in plan.splitlines() if line.startswith("    ")]
                self.assertTrue(any("@" in line for line in grid), plan)
                self.assertTrue(any("B" in line for line in grid), plan)

                needle = run(hero, "read compass")
                self.assertIn("The needle swings", needle, needle)
                self.assertIn("rooms away", needle, needle)
                self.assertIn("guardian's chamber", needle, needle)

    def test_a_hidden_way_opens_to_its_tool_and_the_moblin_pays_once(self) -> None:
        bombed = rupee_cave("B1")           # B8 on the NES map: bomb, 30 rupees
        burned = rupee_cave("C2")           # C7: burn, 100 rupees
        with LiveMud() as mud:
            make(mud, "Znesbomber", 58)
            make(mud, "Znesbombgod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Znesbomber", PASSWORD)
                login(god, "Znesbombgod", PASSWORD)

                run(god, f"transfer znesbomber {WORLD['B1']['vnum']}", settle=2.0)
                # The god follows, to hand things over in the same room.
                run(god, f"goto {WORLD['B1']['vnum']}")
                shut = run(hero, "down")
                self.assertIn("Alas, you cannot go that way", shut, shut)
                pried = run(hero, "open bomb") + run(hero, "down")
                self.assertIn("Alas, you cannot go that way", pried,
                              f"OPEN walked round the seal:\n{pried}")
                empty = run(hero, "bomb cracked")
                self.assertIn("You have no bombs", empty, empty)

                give(god, "znesbomber", 30695, "bombs")
                # Bombing walls is the hero's work: the god goes home first.
                run(god, f"goto {TEMPLE}")
                blast = run(hero, "bomb cracked", settle=2.0)
                self.assertIn("blast opens a passage", blast, blast)
                carried = run(hero, "inventory")
                self.assertIn("three bombs", carried, "the bomb was not used up:\n" + carried)

                paid = run(hero, "down", settle=2.0)
                self.assertIn(f"presses {bombed['amount']} rupees", paid, paid)
                run(hero, "up", settle=1.5)
                again = run(hero, "down", settle=2.0)
                self.assertIn("had your share", again, again)
                self.assertNotIn("presses", again, again)

                run(god, f"transfer znesbomber {WORLD['C2']['vnum']}", settle=2.0)
                run(god, f"goto {WORLD['C2']['vnum']}")
                dark = run(hero, "burn bush")
                self.assertIn("You need a lit candle", dark, dark)
                give(god, "znesbomber", 30546, "candle")
                run(god, f"goto {TEMPLE}")
                run(hero, "wear candle")
                lit = run(hero, "burn bush", settle=2.0)
                self.assertIn("revealing a hidden passage", lit, lit)
                rich = run(hero, "down", settle=2.0)
                self.assertIn(f"presses {burned['amount']} rupees", rich, rich)

    def test_the_items_do_what_they_did(self) -> None:
        take_any = next(landmark["room_vnum"] for landmark in WORLD["H4"]["landmarks"]
                        if landmark["type"] == "take_any")
        with LiveMud() as mud:
            make(mud, "Zneshero", 58)
            make(mud, "Znesgod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zneshero", PASSWORD)
                login(god, "Znesgod", PASSWORD)

                # The red 2nd Potion turns blue once drunk.
                give(god, "zneshero", 30554, "red")
                quaffed = run(hero, "quaff red", settle=2.0)
                self.assertIn("turns blue", quaffed, quaffed)
                self.assertIn("blue Life Potion", run(hero, "inventory"))

                # Hearts: three to start; a take-any Heart Container is one
                # more, and the other gift is then refused.
                self.assertIn("You have 3 hearts", run(hero, "hearts"))
                run(god, f"transfer zneshero {take_any}", settle=2.0)
                taken = run(hero, "get heart", settle=2.0)
                self.assertIn("you have 4 hearts", taken, taken)
                refused = run(hero, "get potion")
                self.assertIn("already made your choice", refused, refused)
                self.assertIn("You have 4 hearts", run(hero, "hearts"))

                # The White Sword wants five.
                run(god, "transfer zneshero 30651", settle=2.0)
                sword = run(hero, "get sword")
                self.assertIn("Master using it and you can have this", sword, sword)
                self.assertIn("you have 4", sword, sword)


if __name__ == "__main__":
    unittest.main()
