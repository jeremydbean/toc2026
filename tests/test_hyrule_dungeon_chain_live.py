"""Hyrule's dungeon chain, played.

Every dungeon: kill the guardian, take its key, unlock the door behind it,
unlock and open the chest there, and the Triforce piece and the treasure
are inside. The dungeons go in order -- the next entrance wants the piece,
the next guardian's chamber wants the treasure -- and the nine pieces
COMBINE into The Triforce.

A level 58 hero does the walking, so nothing in the early dungeons attacks;
an immortal sets the scene and is the bypass case.
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
PASSWORD = "Zchainpass1"
TEMPLE = 4207
TRIFORCE = 30286
PIECES = range(30400, 30409)

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
WORLD = {room["coordinate"]: room["vnum"] for room in MANIFEST["overworld"]["rooms"]}
DUNGEONS = {dungeon["level"]: dungeon for dungeon in MANIFEST["dungeons"]}
# Every room has a name of its own now; read the Eagle's treasure room's
# from the prose rather than hard-coding one that may be rewritten.
PROSE = json.loads((ROOT / "data" / "hyrule_room_prose.json").read_text(encoding="utf-8"))
TREASURE_ROOM_NAME = PROSE["dungeons"][
    f"L1:{DUNGEONS[1]['goal_coordinate']}"]["name"]


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


@unittest.skipIf(SKIP is not None, SKIP or "")
class DungeonChainTests(unittest.TestCase):
    def test_the_eagle_key_door_chest_and_its_prize(self) -> None:
        level_one = DUNGEONS[1]
        lair, treasure = level_one["boss_vnum"], level_one["goal_vnum"]
        with LiveMud() as mud:
            make(mud, "Zchainhero", 58)
            make(mud, "Zchaingod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zchainhero", PASSWORD)
                login(god, "Zchaingod", PASSWORD)
                # The Triforce lets the hero see in the dark lair.
                give(god, "zchainhero", TRIFORCE, "triforce")
                run(hero, "wear triforce")
                run(god, "holylight")
                run(god, f"goto {lair}")
                slain = run(god, "slay aquamentus", settle=2.0)
                self.assertIn("aquamentus", slain.lower(), slain)
                run(god, f"transfer zchainhero {lair}", settle=2.0)

                locked = run(hero, "east", settle=2.0)
                self.assertNotIn(TREASURE_ROOM_NAME, locked,
                                 f"the treasure room starts locked:\n{locked}")
                looted = run(hero, "get key corpse", settle=2.0)
                self.assertIn("eagle's key", looted.lower(), looted)
                opened = run(hero, "unlock east", settle=1.5) + run(hero, "open east", settle=1.5)
                self.assertNotIn("lack the key", opened, opened)
                inside = run(hero, "east", settle=2.0)
                self.assertIn(TREASURE_ROOM_NAME, inside, looted + opened + inside)

                shut = run(hero, "open chest", settle=1.5)
                self.assertIn("locked", shut.lower(), f"the chest starts locked:\n{shut}")
                chest = run(hero, "unlock chest", settle=1.5) + run(hero, "open chest", settle=1.5)
                prize = run(hero, "get all chest", settle=2.0)
                # Twice in CI, never locally, the chest answered closed after
                # UNLOCK and OPEN (also in test_hyrule_walkthrough). CI
                # reprints only a failure's first line, so the chest's own
                # replies lead it.
                self.assertIn("first triforce shard", prize.lower(), " | ".join(
                    x.strip().replace("\n", " ") for x in
                    (f"chest said [{chest}]", f"prize [{prize}]",
                     f"look [{run(hero, 'look', 1.5)}]")))
                self.assertIn("boomerang", prize.lower(), prize)

    def test_the_next_door_wants_the_previous_piece_and_treasure(self) -> None:
        level_two = DUNGEONS[2]
        screen = WORLD[level_two["overworld_coordinate"]]
        rooms = {room["coordinate"]: room["vnum"] for room in level_two["rooms"]}
        approach = rooms["C7"]          # south of Dodongo's lair
        with LiveMud() as mud:
            make(mud, "Zgatehero", 58)
            make(mud, "Zgategod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zgatehero", PASSWORD)
                login(god, "Zgategod", PASSWORD)
                run(god, "holylight")

                # The entrance: refused without the first piece.
                run(god, f"transfer zgatehero {screen}", settle=2.0)
                refused = run(hero, "down", settle=2.0)
                self.assertIn("first Triforce piece", refused, refused)
                self.assertIn("in order", refused, refused)

                # Staff are never asked.
                run(god, f"goto {screen}", settle=1.5)
                bypass = run(god, "down", settle=2.0)
                self.assertNotIn("Triforce piece", bypass, bypass)
                self.assertIn("Level 2:", bypass, bypass)
                run(god, "up", settle=1.5)

                give(god, "zgatehero", 30400, "shard")
                passed = run(hero, "down", settle=2.0)
                self.assertNotIn("Triforce piece", passed, passed)
                self.assertIn("Level 2:", passed, passed)

                # The guardian's chamber: refused without a boomerang.
                run(god, f"goto {approach}", settle=1.5)
                run(god, "purge", settle=1.5)
                run(god, f"transfer zgatehero {approach}", settle=2.0)
                lever = run(hero, "north", settle=2.0)
                self.assertIn("boomerang", lever.lower(), lever)
                self.assertIn("Level 1's treasure chest", lever, lever)

                give(god, "zgatehero", 30232, "boomerang")
                lair = run(hero, "north", settle=2.0)
                self.assertNotIn("Level 1's treasure chest", lair, lair)
                self.assertIn("Lair", lair, lair)

    def test_combine_makes_the_triforce_from_nine_pieces(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcombhero", 58)
            make(mud, "Zcombgod", 70)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zcombhero", PASSWORD)
                login(god, "Zcombgod", PASSWORD)
                for vnum in list(PIECES)[:8]:
                    give(god, "zcombhero", vnum, "shard")

                short = run(hero, "combine triforce", settle=1.5)
                self.assertIn("carrying 8 of them", short, short)

                give(god, "zcombhero", 30408, "power")
                made = run(hero, "combine triforce", settle=2.0)
                self.assertIn("The Triforce, blazing", made, made)
                carried = run(hero, "inventory", settle=1.5)
                self.assertIn("The Triforce", carried, carried)
                self.assertNotIn("Triforce shard", carried, carried)
                self.assertNotIn("final Triforce piece", carried, carried)

                # COMBINE alone is still the inventory toggle.
                toggled = run(hero, "combine", settle=1.5)
                self.assertIn("inventory selected", toggled, toggled)


if __name__ == "__main__":
    unittest.main()
