"""Hyrule tells a player how to do what its rooms describe (owner,
2026-11-13, from the play logs).

Four things the logs showed players failing at, each fixed in the data or
the game and held here:

- the stepladder crossing at the coast (room 30247) answered only to
  ENTER CROSSING: CROSS GAP, CROSS WATER and JUMP GAP found nothing. The
  crossings now answer to the words their rooms use and their room lines
  say ENTER (scripts/build_hyrule_area.py);
- twenty tries at BOMB and PUSH on Spectacle Rock's cracked left rock
  found nothing: the way down answered only to "triforce bomb dungeon
  entrance". An overworld bomb seal now answers to the surfaces its room
  describes, and BOMB takes the sealed way's keywords and direction
  (bomb_puzzle_for_way in src/act_obj.c), still spending nothing on a
  target it refuses;
- rooms describe stones, statues and blocks that LOOK could not find. The
  generator gives every room a detail for each noun of NOUN_DETAILS its
  description names, told by the room as built so it never promises an
  act that will not work there; LOOK W and LOOK S stay west and south
  (room_detail_names_word in src/act_move.c);
- LIST was refused 21 times in the old men's and old women's caves. It
  now says what the cave offers and how (hyrule_list_cave in src/hyrule.c).
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_hyrule_area as gen  # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zfindpass1"
COAST = 30247           # The Coast's Lonely Ledge: the stepladder crossing
LEDGE = 30658           # Across the Narrow Water
SPECTACLE = 30317       # Spectacle Rock: Level 9's way down
STEPLADDER = 30412
BOMBS = 30695
ROCK_FACE = 30202       # Woodland Rock Face: a bomb cave and a west exit
WATERFALL_HINT = 30331  # the old woman behind the falls, who sells hints
DUNGEON_HINT = 30407    # Level 1's old man: "Eastmost peninsula is the secret."
TAKE_ANY = 30654
MONEY_CAVE = 30660
REPAIR = 30700
GAMBLE = 30710
MERCHANT_CAVE = 30687   # a merchant: a real shop
OPEN_FIELD = 30217      # an overworld screen with nobody in it

DIRECTIONS = ("north", "east", "south", "west", "up", "down")


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def function_body(text: str, start: str) -> str:
    index = text.index(start)
    end = text.index("\n}\n", index)
    return text[index:end]


class AreaData:
    parser: AreaParser | None = None

    @classmethod
    def get(cls) -> AreaParser:
        if cls.parser is None:
            cls.parser = AreaParser(ROOT / "area")
            cls.parser.parse_all()
        return cls.parser


def hyrule_rooms(parser: AreaParser) -> dict:
    return {vnum: room for vnum, room in parser.rooms.items() if 30200 <= vnum <= 30799}


def room_objects(parser: AreaParser) -> dict[int, set[int]]:
    found: dict[int, set[int]] = {}
    for reset in parser.resets["hyrule.are"]:
        if reset.command == "O":
            found.setdefault(reset.arg3, set()).add(reset.arg1)
    return found


def answers(keywords: str, word: str) -> bool:
    """is_name for one word: a prefix of any keyword."""
    return any(name.lower().startswith(word.lower()) for name in keywords.split())


def looked(room, word: str) -> str:
    """What LOOK <word> reads from the room's details: load_rooms links
    each E record at the head of the list, so the last written answers
    first."""
    for extra in reversed(room.extra_descr):
        if answers(extra["keywords"], word):
            return " ".join(extra["description"].split())
    return ""


class GeneratedDetailTests(unittest.TestCase):
    """The area file is the generator's own output (test_hyrule_progression
    rebuilds it); these hold what the generator now writes into it."""

    def test_the_details_are_written_by_the_generator(self) -> None:
        rooms, _ = gen.build_rooms(gen.load_json(gen.DEFAULT_MANIFEST),
                                   gen.Prose(gen.load_json(gen.DEFAULT_PROSE)))
        parser = AreaData.get()
        for vnum, room in rooms.items():
            written = [extra["keywords"] for extra in parser.rooms[vnum].extra_descr]
            self.assertEqual([keywords for keywords, _ in room.extras], written, vnum)

    def test_every_noun_a_room_names_answers_to_look(self) -> None:
        parser = AreaData.get()
        missing = []
        for vnum, room in sorted(hyrule_rooms(parser).items()):
            named = set(re.findall(r"[a-z]+", room.description.lower()))
            keywords = " ".join(extra["keywords"] for extra in room.extra_descr)
            for detail in gen.NOUN_DETAILS:
                for word in sorted(named & set(detail.triggers)):
                    if not answers(keywords, word):
                        missing.append((vnum, word))
        self.assertEqual([], missing, "a noun the description names that LOOK cannot find")

    def test_no_detail_promises_an_act_the_room_cannot_do(self) -> None:
        parser = AreaData.get()
        objects = room_objects(parser)
        bombs = set(gen.PUZZLE_OBJECTS["bomb"].values())
        promises = {
            "BOMB": lambda vnum: objects.get(vnum, set()) & bombs,
            "PUSH BLOCK": lambda vnum: gen.PUZZLE_OBJECTS["push"] in objects.get(vnum, set()),
            "PUSH STATUE": lambda vnum: gen.PUZZLE_OBJECTS["armos"] in objects.get(vnum, set()),
            "PUSH STONE": lambda vnum: gen.PUZZLE_OBJECTS["bracelet"] in objects.get(vnum, set()),
            "PUSH GRAVESTONE": lambda vnum: gen.PUZZLE_OBJECTS["grave"] in objects.get(vnum, set()),
            "BURN BUSH": lambda vnum: gen.PUZZLE_OBJECTS["burn"] in objects.get(vnum, set()),
            "PLAY RECORDER": lambda vnum: gen.PUZZLE_OBJECTS["recorder"] in objects.get(vnum, set()),
            "ENTER RAFT": lambda vnum: objects.get(vnum, set()) & {30538, 30539},
            "ENTER the CROSSING": lambda vnum: 30540 in objects.get(vnum, set()),
        }
        broken = []
        for vnum, room in sorted(hyrule_rooms(parser).items()):
            exits = {DIRECTIONS[e.direction]: e for e in room.exits
                     if e.direction < len(DIRECTIONS)}
            for extra in room.extra_descr:
                text = " ".join(extra["description"].split())
                for act, holds in promises.items():
                    if act in text and not holds(vnum):
                        broken.append((vnum, extra["keywords"], act))
                for direction in re.findall(r"UNLOCK (\w+)", text):
                    door = exits.get(direction.lower())
                    if door is None or door.locks != 2 or door.key_vnum != 30227:
                        broken.append((vnum, extra["keywords"], f"UNLOCK {direction}"))
                for way in re.findall(r"go (UP|DOWN)", text):
                    if way.lower() not in exits:
                        broken.append((vnum, extra["keywords"], f"go {way}"))
        self.assertEqual([], broken)

    def test_every_hyrule_door_is_told_by_its_detail(self) -> None:
        """The door detail knows small-key doors, guardians' doors and
        shutters; any other lock would be told as open."""
        parser = AreaData.get()
        guardian_keys = set(gen.BOSS_KEYS.values())
        odd = [(vnum, e.direction, e.locks, e.keyword)
               for vnum, room in hyrule_rooms(parser).items() for e in room.exits
               if e.locks in (1, 2, 3)
               and not (e.locks == 2 and e.key_vnum in {30227} | guardian_keys)
               and e.keyword != "shutter"]
        self.assertEqual([], odd)

    def test_the_crossings_answer_to_their_rooms_words_and_say_enter(self) -> None:
        parser = AreaData.get()
        expected = {30540: ("stepladder", {"gap", "water", "ledge", "crossing"}),
                    30539: ("raft", {"water", "cave", "crossing"}),
                    30538: ("raft", {"water", "entrance", "crossing"})}
        for vnum, (first, words) in expected.items():
            with self.subTest(vnum=vnum):
                obj = parser.objects[vnum]
                keywords = obj.keywords.split()
                self.assertEqual(first, keywords[0], "the router names the first keyword")
                self.assertTrue(words <= set(keywords), keywords)
                self.assertIn("ENTER", obj.long_desc)
                self.assertTrue(obj.extra_descr, "LOOK at it says how to cross")

    def test_spectacle_rock_names_its_rock(self) -> None:
        parser = AreaData.get()
        room = parser.rooms[SPECTACLE]
        down = next(e for e in room.exits if e.direction == 5)
        self.assertEqual(4, down.locks)
        self.assertTrue(down.keyword.startswith("triforce bomb dungeon entrance"),
                        "the router and the seal read the first words")
        for word in ("rock", "boulder", "left", "crack", "hollow", "spectacle"):
            self.assertIn(word, down.keyword.split())
        keywords = " ".join(extra["keywords"] for extra in room.extra_descr)
        for word in ("left", "rock", "boulder", "crack", "sand", "spectacle"):
            self.assertTrue(answers(keywords, word), word)
        self.assertIn("BOMB ROCK", looked(room, "rock"))
        self.assertIn("BOMB ROCK", looked(room, "left"))
        self.assertIn("right-hand", looked(room, "boulder"))
        self.assertIn("only sand", looked(room, "drifts"))

    def test_overworld_bomb_seals_answer_to_their_surfaces(self) -> None:
        parser = AreaData.get()
        objects = room_objects(parser)
        bombs = set(gen.PUZZLE_OBJECTS["bomb"].values())
        unnamed = []
        for vnum, room in hyrule_rooms(parser).items():
            if not 30200 <= vnum <= 30327 or not objects.get(vnum, set()) & bombs:
                continue
            named = set(re.findall(r"[a-z]+", room.description.lower()))
            surfaces = [w for w in gen.BOMB_SURFACE_WORDS if w in named]
            for e in room.exits:
                if e.locks == 4 and e.keyword.split()[0] in gen.BOMB_SEAL_WORDS:
                    if not set(surfaces) <= set(e.keyword.split()):
                        unnamed.append((vnum, e.keyword, surfaces))
        self.assertEqual([], unnamed)


class SourceTests(unittest.TestCase):
    def test_look_lets_a_direction_word_through_unless_a_detail_is_named_whole(self) -> None:
        body = function_body(source("act_move.c"), "void do_look(")
        self.assertIn("!room_detail_names_word( ch->in_room, arg1 )", body)
        helper = function_body(source("act_move.c"), "static bool room_detail_names_word(")
        self.assertIn("str_cmp( word, name )", helper)
        self.assertNotIn("is_name", helper)

    def test_bomb_asks_the_creature_before_the_way_and_spends_after_the_puzzle(self) -> None:
        body = function_body(source("act_obj.c"), "void do_bomb(")
        self.assertLess(body.index("get_char_room( ch, argument )"),
                        body.index("bomb_puzzle_for_way( ch, argument )"))
        self.assertLess(body.index("bomb_puzzle_for_way( ch, argument )"),
                        body.index("puzzle_manipulation_ready( ch, target )"))
        self.assertLess(body.index("puzzle_manipulation_ready( ch, target )"),
                        body.index("hyrule_use_bomb( ch )"))

    def test_list_asks_the_cave_before_the_shopkeeper(self) -> None:
        body = function_body(source("act_obj.c"), "void do_list(")
        self.assertLess(body.index("hyrule_list_cave( ch )"), body.index("find_keeper( ch )"))
        cave = function_body(source("hyrule.c"), "bool hyrule_list_cave(")
        self.assertIn("pShop != NULL", cave, "a real shop answers as a shop")
        self.assertIn("is_hyrule_bystander( keeper )", cave)
        for table in ("hyrule_claims", "hint_prices", "hyrule_money_caves",
                      "HYRULE_REPAIR_ROOM_FIRST", "HYRULE_GAMBLE_LOW"):
            self.assertIn(table, source("hyrule.c").split("bool hyrule_list_cave(")[0]
                          + cave, table)


def record(vnum: int, count: int = 0) -> str:
    values = f"Val  {count} 0 0 0 0\n" if count else ""
    return f"#O\nVnum {vnum}\nNest 0\nWear -1\nLev 1\nCond 100\n{values}End\n\n"


def make(mud: LiveMud, name: str, level: int, room: int, carried: str = "") -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=room, Attr="25 25 25 25 25",
                      HMV="5000 5000 500 500 500 500", HMVP="5000 500 500")
    if carried:
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        path.write_text(text.replace("#END", carried + "#END", 1), encoding="latin-1")


def bombs_on_file(mud: LiveMud, name: str, default: int) -> int:
    total = 0
    vnum = count = None
    for line in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if line.startswith("#O"):
            vnum = count = None
        elif line.startswith("Vnum "):
            vnum = int(line.split()[1])
        elif line.startswith("Val "):
            count = int(line.split()[1])
        elif line == "End" and vnum == BOMBS:
            total += default if count is None else count
            vnum = None
    return total


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveDiscoverabilityTests(unittest.TestCase):
    def test_crossing_bombing_looking_and_listing_as_players_would(self) -> None:
        default_bombs = int(AreaData.get().objects[BOMBS].values[0])
        with LiveMud() as mud:
            make(mud, "Zladder", 30, COAST, record(STEPLADDER))
            make(mud, "Znoladder", 30, COAST)
            make(mud, "Zbomber", 58, SPECTACLE, record(BOMBS, 4))
            make(mud, "Zlister", 20, WATERFALL_HINT)
            make(mud, "Zlistgod", 70, 4207)
            with mud.connect(timeout=120) as ladder, mud.connect(timeout=120) as walker, \
                    mud.connect(timeout=120) as bomber, mud.connect(timeout=120) as lister, \
                    mud.connect(timeout=120) as god:
                login(ladder, "Zladder", PASSWORD)
                login(walker, "Znoladder", PASSWORD)
                login(bomber, "Zbomber", PASSWORD)
                login(lister, "Zlister", PASSWORD)
                login(god, "Zlistgod", PASSWORD)

                # The coast: the room line says how, LOOK GAP explains,
                # and ENTER takes the words the room uses.
                looked = walker.must("look", "ENTER the crossing")
                self.assertIn("stepladder", looked)
                walker.must("look gap", "ENTER GAP")
                walker.must("look ledge", "ENTER")
                refused = walker.must("enter water", "You need")
                self.assertIn("stepladder", refused)
                walker.must("enter gap", "You need")
                crossed = ladder.must("enter gap", "You enter")
                self.assertIn("Across the Narrow Water", crossed)

                # Spectacle Rock: LOOK finds the rock; a refused target
                # costs nothing; BOMB ROCK opens the way down.
                bomber.must("look rock", "BOMB ROCK")
                bomber.must("look boulder", "right-hand")
                # (SAND is the blue leever's own word: LOOK and BOMB find
                # a creature before anything else.)
                bomber.must("look drifts", "only sand")
                bomber.must("bomb saddle", "no cracked surface")
                bomber.must("down", "cannot go that way", "You can't go that way",
                            "Your hands find only stone", "Alas")
                bomber.must("bomb left rock", "blast opens a passage")
                bomber.must("bomb rock", "already been solved", "no cracked surface")

                # LOOK W is west even where the walls answer to WALL.
                god.must(f"goto {ROCK_FACE}", "Woodland Rock Face")
                wall = god.must("look wall", "BOMB CRACK")
                west = god.sync("look w")
                self.assertNotIn("BOMB CRACK", west, west)
                self.assertNotEqual(" ".join(wall.split()), " ".join(west.split()))
                god.must("look walls", "BOMB CRACK")

                # LIST in the caves, as a mortal and from staff's walk.
                hint = lister.must("list", "GIVE <amount> GOLD WOMAN")
                self.assertIn("5, 10 or 20 gold", hint)
                self.assertNotIn("can't do that here", hint)

                for room, expected in ((DUNGEON_HINT, "Eastmost peninsula is the secret"),
                                       (TAKE_ANY, "GET HEART"),
                                       (MONEY_CAVE, "pays 10 gold"),
                                       (REPAIR, "20 gold for the door repair"),
                                       (GAMBLE, "GAMBLE LEFT")):
                    with self.subTest(room=room):
                        god.sync(f"goto {room}")
                        god.must("list", expected)
                god.sync(f"goto {TAKE_ANY}")
                taken = god.must("list", "Take ONE")
                self.assertIn("GET RED", taken)
                god.sync(f"goto {MERCHANT_CAVE}")
                god.must("list", "[Lv Price]", "You can't buy anything here")
                god.sync(f"goto {OPEN_FIELD}")
                god.must("list", "You can't do that here")

                for client in (ladder, walker, bomber, lister, god):
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            # Exactly one bomb spent: none on the sand, none on the solved seal.
            self.assertEqual(3, bombs_on_file(mud, "Zbomber", default_bombs))


if __name__ == "__main__":
    unittest.main()
