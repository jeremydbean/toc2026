"""One of each Triforce shard: a refilled chest gives no second copy.

Hyrule's chests relock and refill at every area reset, so a character
who replays a dungeon finds its shard there again. Nothing refused it:
Trentlin replayed Level 1 on 2026-10-21 and left with two first shards
(play journal: "You get the first Triforce shard from the Eagle's
treasure chest." a day after his first). The shards are NODROP, so the
spare could go nowhere -- not dropped, given, put, sold or stashed -- but
it is clutter, and the take is now refused. A login fix,
20261029-spare-shards, takes back a spare already carried.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zshardpw1"
TEMPLE = 4207
FIRST, SECOND = 30400, 30401


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def shard(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


def make(mud: LiveMud, name: str, objects: str = "", unfix: bool = False, **fields) -> Path:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if unfix:
        # A fixture is a new character, born with every fix marked; an
        # old file has no Fixes line and is owed them all.
        text = re.sub(r"(?m)^Fixes .*\n", "", text)
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")
    return path


class SpareShardSourceTests(unittest.TestCase):
    def test_get_obj_refuses_a_shard_already_held(self) -> None:
        act_obj = source("act_obj.c")
        get = act_obj[act_obj.index("void get_obj("):]
        get = get[:get.index("\n}\n")]
        self.assertIn("hyrule_carries( ch, obj->pIndexData->vnum )", get)
        self.assertIn("HYRULE_PIECE_FIRST_VNUM", get)
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", get, "staff may test freely")

    def test_the_fix_is_listed_once_for_mortals(self) -> None:
        fixes = source("fixes.c")
        self.assertEqual(fixes.count('"20261029-spare-shards"'), 1)
        self.assertIn("fix_spare_triforce_shards, false }", fixes)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SpareShardLiveTests(unittest.TestCase):
    def test_a_held_shard_is_not_taken_twice(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zshardkeep", Levl=70)
            make(mud, "Zshardhold", shard(FIRST), Levl=20)
            make(mud, "Zshardnew", Levl=20)
            with mud.connect(timeout=120) as staff, \
                 mud.connect(timeout=120) as holder, \
                 mud.connect(timeout=120) as fresh:
                login(staff, "Zshardkeep", PW)
                login(holder, "Zshardhold", PW)
                login(fresh, "Zshardnew", PW)
                for client in (staff, holder, fresh):
                    client.sync("scroll 0")
                staff.must("load obj %d" % FIRST, "You create")
                staff.must("drop shard", "You drop")

                refused = holder.sync("get shard")
                self.assertIn("You already hold the first Triforce shard", refused)
                self.assertEqual(holder.sync("inventory").count("the first Triforce shard"), 1)

                # Somebody who needs it still takes it.
                self.assertIn("You get the first Triforce shard", fresh.sync("get shard"))

    def test_a_spare_already_carried_is_taken_back_once(self) -> None:
        with LiveMud() as mud:
            path = make(mud, "Zshardtwo", shard(FIRST) + shard(FIRST) + shard(SECOND),
                        unfix=True, Levl=20)
            with mud.connect(timeout=120) as client:
                login(client, "Zshardtwo", PW)
                client.drain(2.0)
                self.assertIn("Triforce shard you already had", client.transcript)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            saved = path.read_text(encoding="latin-1")
            self.assertEqual(saved.count("Vnum %d\n" % FIRST), 1, "one of each kept")
            self.assertEqual(saved.count("Vnum %d\n" % SECOND), 1)
            self.assertIn("20261029-spare-shards", saved, "applied once, and recorded")

            with mud.connect(timeout=120) as client:
                login(client, "Zshardtwo", PW)
                client.drain(2.0)
                self.assertNotIn("Triforce shard you already had", client.transcript)
                client.send("quit")
                client.wait_closed()


if __name__ == "__main__":
    unittest.main()
