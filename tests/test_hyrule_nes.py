"""The NES pass over Hyrule, checked from the files (wiki/hyrule-area.md,
"The NES Pass: Plan"): maps that carry their floor plan, seals that only
the NES's act opens, the caves' once-per-character rules, and the tables
in src/hyrule.c held to the generator's.

tests/test_hyrule_nes_live.py plays the same rules in a running game.
"""
from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from scripts.build_hyrule_area import (
    BOMB_BAG_SELLERS,
    HYRULE_BOMB_BAG_VNUM,
    HYRULE_BOMBS_VNUM,
    MAGICAL_SWORD_VNUM,
    PLAN_KEYWORD,
    SHOP_INVENTORY,
    TAKE_ANY_OFFER,
    guide_coordinate,
    npc_table,
    npc_vnum,
)
from tools.build_directions import HYRULE_SEALS
from webadmin.area_parser import AreaParser

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
PROSE = json.loads((ROOT / "data" / "hyrule_room_prose.json").read_text(encoding="utf-8"))
HYRULE_C = (ROOT / "src" / "hyrule.c").read_text(encoding="utf-8")
MERC_H = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")


def c_table(name: str) -> str:
    return HYRULE_C.split(f"{name}[] =", 1)[1].split("};", 1)[0]


class HyruleNesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()
        cls.resets = cls.parser.resets["hyrule.are"]
        cls.world = {room["coordinate"]: room for room in MANIFEST["overworld"]["rooms"]}

    # ---------------------------------------------------------- Plan 1
    def test_no_two_rooms_read_alike(self) -> None:
        """Every room's name is its own, every cave included. The only
        repeats are the two mazes' copies of their screen, which is the
        puzzle."""
        rooms = [room for room in self.parser.rooms.values() if room.area_file == "hyrule.are"]
        names = Counter(room.name for room in rooms)
        mazes = {PROSE["overworld"]["E2"]["name"], PROSE["overworld"]["H7"]["name"]}
        self.assertEqual({}, {n: c for n, c in names.items() if c > 1 and n not in mazes})
        texts = Counter(room.description for room in rooms)
        repeated = [room.vnum for room in rooms
                    if texts[room.description] > 1 and room.name not in mazes]
        self.assertEqual([], repeated)

    def test_every_enemy_band_and_person_has_its_own_text(self) -> None:
        mob_prose = json.loads((ROOT / "data" / "hyrule_mob_prose.json").read_text(encoding="utf-8"))
        longs = Counter(
            entry["long"] for bands in mob_prose["enemies"].values() for entry in bands.values())
        self.assertEqual([], [line for line, n in longs.items() if n > 1])
        descriptions = Counter(npc["description"] for npc in npc_table().values())
        self.assertEqual([], [d[:60] for d, n in descriptions.items() if n > 1])

    def test_old_men_stand_where_the_sources_put_their_words(self) -> None:
        words = {key: npc["long"] for key, npc in npc_table().items()}
        expected = {
            "old_man:L2:D7": "Dodongo dislikes smoke.",
            "old_man:L6:C2": "Aim at the eyes of Gohma.",
            "old_man:L6:D8": "There are secrets where fairies don't live.",
            "old_man:L7:A4": "I bet you'd like to have more bombs.",
            "old_man:L8:A5": "10th enemy has the bomb.",
            "old_man:L8:C5": "Spectacle Rock is an entrance to death.",
            "old_man:L9:G8": "Go to the next room.",
            "old_man:L9:D4": "Eyes of skull has a secret.",
        }
        for key, line in expected.items():
            with self.subTest(key=key):
                self.assertIn(line, words[key])

    # ---------------------------------------------------------- Plan 2
    def test_every_map_carries_its_floor_plan(self) -> None:
        self.assertIn(f'#define HYRULE_PLAN_KEYWORD     "{PLAN_KEYWORD}"', HYRULE_C)
        for dungeon in MANIFEST["dungeons"]:
            plan_obj = self.parser.objects[dungeon["map_vnum"]]
            text = next(
                ed["description"] for ed in plan_obj.extra_descr
                if PLAN_KEYWORD in ed["keyword"].split())
            numbers = [int(n) for n in re.findall(r"\d+", text)]
            rooms = {room["coordinate"]: room["vnum"] for room in dungeon["rooms"]}
            grid = [rooms.get(f"{chr(ord('A') + col)}{row}", 0)
                    for row in range(8, 0, -1) for col in range(8)]
            with self.subTest(level=dungeon["level"]):
                self.assertEqual(numbers[:64], grid)
                self.assertEqual(numbers[64:66], [rooms[dungeon["map_coordinate"]],
                                                  rooms[dungeon["compass_coordinate"]]])
                cellars = [n for c in dungeon["cellars"] for n in (c["vnum"], c["source_vnum"])]
                self.assertEqual(numbers[66:], cellars)
                self.assertEqual(plan_obj.values[0], "90")
                self.assertEqual(plan_obj.values[4], str(dungeon["level"]))

    def test_the_compass_walks_the_dungeon_itself(self) -> None:
        compass = HYRULE_C.split("static int compass_route(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("gate->first_room", compass)
        self.assertIn("HYRULE_DUNGEON_SPAN", compass)
        show = HYRULE_C.split("void hyrule_show_compass(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("gate->goal_room", show)
        self.assertIn("gate->boss_room", show)
        for path in ("src/act_move.c", "src/act_info.c"):
            self.assertIn("hyrule_look_tool( ch,", (ROOT / path).read_text(encoding="latin-1"),
                          f"{path} no longer shows the map and compass")

    # ---------------------------------------------------------- Plan 5
    def test_the_caves_pay_and_give_once_by_the_table(self) -> None:
        claims = re.findall(r"\{\s*(\d+),\s*(\w+),\s*(-?\d+),\s*(-?\d+),\s*(\d+)\s*\}",
                            c_table("hyrule_claims"))
        defines = dict(re.findall(r"#define (OBJ_VNUM_HYRULE_\w+)\s+(\d+)", MERC_H))
        rows = [(int(room), int(defines.get(obj, obj) if not obj.isdigit() else obj),
                 int(heart), int(choice), int(hearts))
                for room, obj, heart, choice, hearts in claims]
        take_any = sorted(landmark["room_vnum"] for room in MANIFEST["overworld"]["rooms"]
                          for landmark in room["landmarks"] if landmark["type"] == "take_any")
        self.assertEqual(len(take_any), 4)
        for vnum in take_any:
            with self.subTest(take_any=vnum):
                offer = {row[1]: row for row in rows if row[0] == vnum}
                self.assertEqual(set(offer), set(TAKE_ANY_OFFER))
                self.assertEqual(len({row[3] for row in offer.values()}), 1,
                                 "both gifts must share one choice")
                self.assertEqual(set(self.parser.rooms[vnum].objects), set(TAKE_ANY_OFFER))
        swords = {(row[0], row[1]): row[4] for row in rows if row[4]}
        self.assertEqual(swords, {(30651, 30251): 5, (30652, MAGICAL_SWORD_VNUM): 12})
        heart_bits = sorted(row[2] for row in rows if row[2] >= 0)
        self.assertEqual(heart_bits, list(range(16, 21)), "five hearts beyond the guardians'")

    def test_the_secrets_are_saved(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        reader = save.split("case 'H':", 1)[1].split("case '", 1)[0]
        self.assertIn('KEY( "HyruleSecrets"', reader)
        self.assertIn('"HyruleSecrets %lu', save)

    def test_hint_caves_stand_where_the_nes_put_them(self) -> None:
        hints = {landmark["zelda_coordinate"]: (room["vnum"], landmark)
                 for room in MANIFEST["overworld"]["rooms"]
                 for landmark in room["landmarks"] if landmark["type"] == "hint"}
        self.assertEqual(set(hints), {"A8", "K2", "F8", "M2"})
        self.assertEqual(hints["M2"][1].get("puzzle"), "armos")
        for guide, (screen, landmark) in hints.items():
            with self.subTest(guide=guide):
                self.assertTrue(any(e.to_room == landmark["room_vnum"]
                                    for e in self.parser.rooms[screen].exits))
                self.assertIn(landmark["room_vnum"],
                              self.parser.mobiles[npc_vnum(f"hint:{guide}")].spawn_rooms)
        self.assertIn(f"HYRULE_HINT_ROOM_WOODS      {hints['A8'][1]['room_vnum']}", HYRULE_C)
        self.assertIn(f"HYRULE_HINT_ROOM_WATERFALL  {hints['K2'][1]['room_vnum']}", HYRULE_C)

    def test_the_bomb_bag_men_sell_the_bag(self) -> None:
        for key in BOMB_BAG_SELLERS:
            keeper = self.parser.mobiles[npc_vnum(key)]
            with self.subTest(key=key):
                self.assertIn(HYRULE_BOMB_BAG_VNUM, keeper.drops)
                room = keeper.spawn_rooms[0]
                self.assertIn(str(room), HYRULE_C.split("HYRULE_BOMB_BAG_ROOM_L5", 1)[1][:200])

    # ---------------------------------------------------------- Plan 6
    def test_everything_the_shops_sell_says_what_it_is_for(self) -> None:
        stocked = sorted({v for stock in SHOP_INVENTORY.values() for v in stock})
        self.assertIn(HYRULE_BOMBS_VNUM, stocked)
        self.assertNotIn(30542, self.parser.objects, "the bottomless bomb satchel is gone")
        silent = [v for v in stocked
                  if not self.parser.objects[v].extra_descr and v != 30549]
        self.assertEqual([], silent, "a shop item with no word of what it does")

    # ---------------------------------------------------------- Plan 7
    def test_every_seal_is_secret_until_its_act_opens_it(self) -> None:
        states = {(r.arg1, r.arg2): r.arg3 for r in self.resets if r.command == "D"}
        sealed = []
        for room in self.parser.rooms.values():
            if room.area_file != "hyrule.are":
                continue
            for exit_data in room.exits:
                if exit_data.locks != 4:
                    continue
                word = exit_data.keyword.split()[0]
                sealed.append(word)
                with self.subTest(room=room.vnum, door=exit_data.direction):
                    self.assertEqual(states.get((room.vnum, exit_data.direction)), 4)
                    self.assertIn(word, HYRULE_SEALS, exit_data.keyword)
        self.assertGreater(len(sealed), 100)
        act_move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        guard = act_move.split("static bool hyrule_seal_refuses(", 1)[1].split("\n}\n", 1)[0]
        for word in sorted(set(sealed)):
            self.assertIn(f'"{word}"', guard, f"OPEN would walk round a {word} seal")
        for command in ("void do_open(", "void do_pick(", "void do_doorbash(", "void do_unlock("):
            body = act_move.split(command, 1)[1].split("\n}\n", 1)[0]
            self.assertIn("hyrule_seal_refuses( ch, ch->in_room, pexit )", body, command)
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        self.assertIn("pReset->arg3 == 4 && pArea->nplayer > 0", db,
                      "a reset would reseal an opened way with nothing to open it by")


if __name__ == "__main__":
    unittest.main()
