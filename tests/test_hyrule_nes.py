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

    # ------------------------------------------------- mazes and crossings
    def walk(self, start: int, directions: str) -> int:
        """Where a run of moves (n/e/s/w letters) ends, through the area's
        own exits."""
        names = {"n": 0, "e": 1, "s": 2, "w": 3}
        here = start
        for letter in directions:
            exits = {exit.direction: exit.to_room for exit in self.parser.rooms[here].exits}
            self.assertIn(names[letter], exits, f"no {letter} exit from {here}")
            here = exits[names[letter]]
        return here

    def test_the_mazes_stand_where_the_nes_keeps_them(self) -> None:
        """CheckMazes (Z_01.asm:4828-4890): the Lost Woods is room $61 (guide
        B7, ours B2): north, west, south, west, and east always leaves. The
        Lost Hills is room $1B (guide L2, ours L7): north four times, and
        west always leaves. Any other way turns you round. Until 2026-10-25
        they stood at E2 and H7, and the hills asked five norths."""
        woods, hills = self.world["B2"]["vnum"], self.world["L7"]["vnum"]
        self.assertEqual(self.world["A2"]["vnum"], self.walk(woods, "nwsw"))
        self.assertEqual(self.world["L8"]["vnum"], self.walk(hills, "nnnn"))
        self.assertEqual(self.world["C2"]["vnum"], self.walk(woods, "e"))
        self.assertEqual(self.world["C2"]["vnum"], self.walk(woods, "nwse"))
        self.assertEqual(self.world["K7"]["vnum"], self.walk(hills, "nnnw"))
        self.assertEqual(woods, self.walk(woods, "w"))
        self.assertEqual(woods, self.walk(woods, "s"))
        self.assertEqual(woods, self.walk(woods, "nn"))
        self.assertEqual(woods, self.walk(woods, "nwn"))
        self.assertEqual(woods, self.walk(woods, "nwss"))
        self.assertEqual(hills, self.walk(hills, "e"))
        self.assertEqual(hills, self.walk(hills, "nns"))
        self.assertEqual(hills, self.walk(hills, "nnne"))
        # A wrong turn starts the count again, so the full answer still works.
        self.assertEqual(self.world["L8"]["vnum"], self.walk(hills, "nnsnnnn"))
        self.assertEqual(self.world["A2"]["vnum"], self.walk(woods, "nwnnwsw"))
        # The old screens are ordinary ground now.
        self.assertEqual(self.world["H8"]["vnum"], self.walk(self.world["H7"]["vnum"], "n"))
        self.assertEqual(self.world["D2"]["vnum"], self.walk(self.world["E2"]["vnum"], "w"))

    def test_the_overworld_asks_for_no_tool_the_nes_does_not(self) -> None:
        """The NES deploys the stepladder on six screens (LadderRoomsOW,
        Z_07.asm:3175) and needs it on the overworld only for the coast's
        Heart Container; it docks a raft in two rooms ($3F and $55). The
        blue-barred stairs of Death Mountain were read as 38 stepladder
        crossings and guide A5/A6 as a raft crossing."""
        gated = sorted((room["coordinate"], direction, exit["gate"])
                       for room in MANIFEST["overworld"]["rooms"]
                       for direction, exit in room["exits"].items()
                       if exit["gate"] != "open")
        self.assertEqual([("P5", "north", "raft"), ("P6", "south", "raft")], gated)
        keywords = {exit.keyword for room in self.parser.rooms.values()
                    if room.area_file == "hyrule.are" for exit in room.exits}
        self.assertNotIn("stepladder crossing", keywords)
        self.assertNotIn("L6", {exit["to"] for exit in self.world["L7"]["exits"].values()})

    # ---------------------------------------------------------- Plan 1
    def test_no_two_rooms_read_alike(self) -> None:
        """Every room's name is its own, every cave included. The only
        repeats are the two mazes' copies of their screen, which is the
        puzzle."""
        rooms = [room for room in self.parser.rooms.values() if room.area_file == "hyrule.are"]
        names = Counter(room.name for room in rooms)
        mazes = {PROSE["overworld"]["B2"]["name"], PROSE["overworld"]["L7"]["name"]}
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


FIGHT_C = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
SPECIAL_C = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
MAGIC2_C = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")


def c_function(source: str, signature: str) -> str:
    start = source.index(signature)
    body = source.index("\n{", start)
    depth, i = 0, body + 1
    while True:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1


class HyruleMechanicsSourceTests(unittest.TestCase):
    """The 2026-10-25 mechanics audit's findings that are random or need a
    world-ending spell to play: held to the source instead.
    tests/test_hyrule_mechanics_live.py plays the rest."""

    def test_a_like_like_eats_only_the_magical_shield(self) -> None:
        """UpdateLikeLike (Z_04.asm ~6886) clears InvMagicShield and nothing
        else. It dissolved any worn shield, the Mirror Shield and rare
        pieces from outside Hyrule included."""
        effect = c_function(FIGHT_C, "static void apply_hyrule_contact_effect(")
        like_like = effect.split("HYRULE_LIKE_LIKE_VNUM", 1)[1].split("HYRULE_BUBBLE_VNUM", 1)[0]
        guard = like_like.index("IS_HYRULE_MAGICAL_SHIELD")
        self.assertLess(guard, like_like.index("extract_obj"))
        self.assertNotIn("item_type == ITEM_ARMOR", like_like)

    def test_instant_kills_are_one_hard_blow_to_ganon_and_gohma(self) -> None:
        """Farslay from anywhere stunned Ganon at full health, and a backstab
        fatality killed Gohma with no arrow: raw_kill_internal guarded Ganon
        only by collapsing him, and Gohma not at all."""
        raw = c_function(FIGHT_C, "static void raw_kill_internal(")
        self.assertIn("hyrule_instant_kill_resisted", raw.split("black_market_cheats_death")[0])
        resisted = c_function(FIGHT_C, "static bool hyrule_instant_kill_resisted(")
        self.assertIn("HYRULE_SILVER_ARROW_GANON_DAMAGE_DIVISOR", resisted)
        self.assertIn("HYRULE_GOHMA_VNUM", c_function(FIGHT_C, "bool hyrule_defies_instant_death("))
        self.assertIn("hyrule_instant_kill_resisted", c_function(FIGHT_C, "void fatality("))
        self.assertIn("hyrule_defies_instant_death", c_function(FIGHT_C, "void do_backstab("))
        self.assertEqual(2, MAGIC2_C.count("hyrule_defies_instant_death( victim )"))
        # A death damage() has judged arrives with the bypass: damage()
        # already holds Gohma to an arrow and Ganon to the Silver Arrow.
        self.assertNotIn("raw_kill_internal( ch, victim, is_hyrule_ganon(victim) )", FIGHT_C)

    def test_gohma_is_finished_by_an_arrow_not_by_holding_a_bow(self) -> None:
        damage = c_function(FIGHT_C, "bool damage( CHAR_DATA *ch")
        gohma = damage.split("HYRULE_GOHMA_VNUM", 1)[1][:400]
        self.assertIn("dt == gsn_archery", gohma)

    def test_a_stunned_ganon_cannot_be_healed_out_of_the_stun(self) -> None:
        """A heal lifted him above one hit point with the stun's mark kept:
        neither shootable nor regenerating, for good."""
        ganon = c_function(SPECIAL_C, "bool spec_ganon(")
        self.assertIn("IS_AFFECTED2(mob, AFF2_NO_RECOVER) && mob->hit > 1", ganon)

    def test_manhandlas_heads_change_the_fight(self) -> None:
        """The heads left decide how many blows and how hard
        (UpdateManhandla, Z_04.asm:7832); it used to throw four whatever
        the message said."""
        guardian = SPECIAL_C.split("mob->pIndexData->vnum == 30305", 1)[1][:1200]
        self.assertIn("count = heads == 1 ? 2 : heads;", guardian)
        self.assertIn("( 6 - heads )", guardian)

    def test_a_money_cave_pays_before_it_is_claimed(self) -> None:
        enter = c_function(HYRULE_C, "void hyrule_enter_room(")
        self.assertLess(enter.index("gain_copper"), enter.index("secret_set"))
        self.assertNotIn("add_money", enter)

    def test_a_bubble_does_not_take_a_weapon_that_cannot_come_off(self) -> None:
        effect = c_function(FIGHT_C, "static void apply_hyrule_contact_effect(")
        bubble = effect.split("HYRULE_BUBBLE_VNUM", 1)[1]
        self.assertLess(bubble.index("ITEM_NOREMOVE"), bubble.index("unequip_char"))

    def test_bubbles_and_blade_traps_hold_no_shutter(self) -> None:
        """Clearing a room never asks for them on the NES; nothing harms
        them, so a shutter they held would never open."""
        act_move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        self.assertIn("hyrule_enemy_is_invincible( victim )",
                      c_function(act_move, "bool hyrule_foe("))


class HyruleClearRewardTests(unittest.TestCase):
    """Items the NES hides until a room's enemies die (trigger 7, or a
    Stalfos or Gibdo carrying it): CLEAR_REWARDS in the generator, and
    hyrule_clear_rewards in src/hyrule.c, which makes them appear."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()
        cls.resets = cls.parser.resets["hyrule.are"]

    def test_the_c_table_is_the_generators(self) -> None:
        from scripts.build_hyrule_area import CLEAR_REWARDS
        rooms = {(d["level"], r["coordinate"]): r for d in MANIFEST["dungeons"] for r in d["rooms"]}
        expected = sorted((rooms[key]["vnum"], vnum)
                          for key, vnums in CLEAR_REWARDS.items() for vnum in vnums)
        table = c_table("hyrule_clear_rewards")
        actual = sorted((int(a), int(b)) for a, b in re.findall(r"\{\s*(\d+),\s*(\d+)\s*\}", table))
        self.assertEqual(expected, actual)

    def test_a_hidden_item_waits_for_the_rooms_enemies(self) -> None:
        """Each is in the manifest's room, the room has an enemy that
        counts in ours, and no reset lays it out there."""
        from scripts.build_hyrule_area import CLEAR_REWARDS
        uncounted = {"old_man", "bubble", "blade_trap"}
        rooms = {(d["level"], r["coordinate"]): r for d in MANIFEST["dungeons"] for r in d["rooms"]}
        for key, vnums in CLEAR_REWARDS.items():
            room = rooms[key]
            with self.subTest(room=key):
                for vnum in vnums:
                    self.assertIn(vnum, room["items"])
                    laid = [r for r in self.resets if r.command == "O"
                            and r.arg1 == vnum and r.arg3 == room["vnum"]]
                    self.assertEqual([], laid)
                self.assertTrue(set(room["entities"]) - uncounted, room["entities"])

    def test_patra_has_the_map(self) -> None:
        """The Level 9 old man's text decodes to "PATRA HAS THE MAP." The
        map's room holds a patra, and the map appears when it dies."""
        from scripts.build_hyrule_area import CLEAR_REWARDS
        level_nine = next(d for d in MANIFEST["dungeons"] if d["level"] == 9)
        room = next(r for r in level_nine["rooms"] if r["coordinate"] == "H6")
        self.assertIn("patra", room["entities"])
        self.assertEqual([30479 + 9], CLEAR_REWARDS[(9, "H6")])

    def test_raw_kill_tells_hyrule_a_room_may_be_clear(self) -> None:
        raw = c_function(FIGHT_C, "static void raw_kill_internal(")
        self.assertLess(raw.index("extract_char( victim, true );\n\t  hyrule_room_cleared"),
                        len(raw))


if __name__ == "__main__":
    unittest.main()
