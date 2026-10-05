"""Hyrule, played through from the arcade to the Triforce (owner, 2026-10-04).

Alaric found the order could not be followed: Levels 1 and 2 stood behind
raft crossings and the raft is Level 3's treasure, and Level 4's island
behind a stepladder crossing, which is Level 4's own. The crossings in front
of them are open now, and this walks the whole chain as a mortal, in the
real game, so the game's own gates are what judge it:

* from The First Quest Begins, carrying nothing, walk to each dungeon's
  entrance screen by the route the Oracle would give (hyrule_oracle), doing
  each seal's act, and go in -- the entrance gate asks for the last piece;
* the guardian is slain by staff and the walker set down in its chamber
  (the walk inside each dungeon is held by
  test_every_dungeon_goal_is_reachable_with_keys_found_on_its_floor);
* take the key, unlock the door and the chest, and take the piece and the
  treasure;
* leave by the returning light, and the owl names the next dungeon;
* after Level 6, the Recorder carries the walker to the dungeons won and
  to the next one, and to no other;
* after Ganon, COMBINE TRIFORCE.

The walker is level 58 and stealthed, so nothing on the way picks a fight:
what is being proved is the way through, not the fighting.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))
sys.path.insert(0, str(ROOT / "scripts"))

import hyrule_oracle as ho  # noqa: E402
from area_parser import AreaParser  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zwalkpass1"
HERO, GOD = "Zwalker", "Zwalkgod"
DIRS = ho.DIRS

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
DUNGEONS = {d["level"]: d for d in MANIFEST["dungeons"]}


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def one_line(text: str) -> str:
    return re.sub(r"\s*[\r\n]+\s*", " | ", text).strip()


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HyruleWalkthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        cls.parser = parser
        cls.rooms = parser.rooms
        directions = json.loads((ROOT / "webadmin" / "directions.json").read_text(encoding="utf-8"))
        cls.graph = ho.build_graph(cls.rooms, directions.get("links") or [])
        import build_hyrule_area as gen
        cls.gen = gen

    def name_of(self, vnum: int) -> str:
        return self.rooms[vnum].name.strip()

    def where(self, god) -> int:
        shown = run(god, f"stat char {HERO.lower()}", 2.0)
        match = re.search(r"Room: (\d+)", shown)
        self.assertIsNotNone(match, shown)
        return int(match.group(1))

    def walk(self, hero, god, start: int, goal: int, items: list, log: list) -> None:
        """Walk the Oracle's route. A tornado or a teleport room can carry
        the walker off it -- the world's weather is not Hyrule's to stop --
        so a step that lands somewhere else asks where, and plans again."""
        here = start
        for _attempt in range(4):
            steps = ho.route(self.graph, here, goal, items, with_rooms=True)
            self.assertIsNotNone(steps, f"no route from {here} to {goal} carrying {items}")
            for cmd, act, need, to in steps:
                if act:
                    log.append(run(hero, act, 1.5))
                out = run(hero, cmd, 1.2)
                log.append(out)
                if self.name_of(to) not in out:
                    here = self.where(god)
                    if here == to:
                        continue
                    break
                here = to
            else:
                return
            if here == goal:
                return
        self.fail(f"could not reach {goal} ({self.name_of(goal)}):\n" + "".join(log[-4:]))

    def test_the_whole_chain_in_order(self) -> None:
        gen = self.gen
        items: list = []
        log: list = []
        with LiveMud() as mud:
            make(mud, HERO, Levl=58, Room=ho.ENTRY_ROOM, Attr="25 25 25 25 25",
                 HMV="9000 9000 5000 5000 5000 5000", HMVP="9000 5000 5000", AfBy2=64)
            make(mud, GOD, Levl=70, Room=4207)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, HERO, PASSWORD)
                login(god, GOD, PASSWORD)
                run(hero, "scroll 0")
                run(god, "holylight")
                here = ho.ENTRY_ROOM
                for level in range(1, 10):
                    dungeon = DUNGEONS[level]
                    screen = ho.DUNGEONS[level]["screen"]
                    with self.subTest(level=level, stage="walk to the entrance"):
                        self.walk(hero, god, here, screen, items, log)

                    # In at the door: the seal's act, then the way down.
                    if level == 7:
                        run(hero, "play recorder", 2.0)
                    elif level == 8:
                        run(hero, "hold candle", 1.0)
                        run(hero, "wear candle", 1.0)
                        log.append(run(hero, "burn bush", 2.0))
                    elif level == 9:
                        # Bombs are bought at the arrow shops; staff hand
                        # them over here.
                        run(god, f"goto {screen}", 1.5)
                        run(god, f"load obj {gen.HYRULE_BOMBS_VNUM}")
                        run(god, f"give bombs {HERO.lower()}")
                        run(god, "goto 4207", 1.0)
                        log.append(run(hero, "bomb cracked", 2.0))
                    entered = run(hero, "enter raft" if level == 4 else "down", 2.0)
                    self.assertIn(f"Level {level}:", entered,
                                  f"Level {level}'s entrance refused:\n" + "".join(log[-3:]) + entered)

                    # The guardian, slain by staff; the walker in its chamber.
                    boss_room, goal = dungeon["boss_vnum"], dungeon["goal_vnum"]
                    boss = self.parser.mobiles[gen.BOSS_MOBS[level]]
                    keyword = boss.keywords.split()[0]
                    run(god, f"goto {boss_room}", 1.5)
                    slain = run(god, f"slay {keyword}", 2.0)
                    self.assertIn("corpse", run(god, "look", 1.0).lower(), slain)
                    run(god, f"transfer {HERO.lower()} {boss_room}", 2.0)
                    run(god, "goto 4207", 1.0)
                    # The key first: with a drop for every slot, a pack that
                    # has carried every earlier dungeon's loot can be full.
                    looted = run(hero, "get key corpse", 1.5) + run(hero, "get all corpse", 2.0)
                    door = next(DIRS[x.direction] for x in self.rooms[boss_room].exits
                                if x.to_room == goal)
                    opened = run(hero, f"unlock {door}", 1.2) + run(hero, f"open {door}", 1.2)
                    inside = run(hero, door, 1.5)
                    self.assertIn(self.name_of(goal), inside, looted + opened + inside)
                    chest = run(hero, "unlock chest", 1.5) + run(hero, "open chest", 1.5)
                    prize = run(hero, "get all chest", 2.5)
                    if "is closed" in prize.lower():
                        # Twice in CI, never locally, the chest answered
                        # closed after UNLOCK and OPEN. Say so loudly and
                        # try once more, so a slow runner's timing is told
                        # apart from a chest that really will not open.
                        print(f"\n[walkthrough] Level {level} chest closed after "
                              f"unlock/open: {one_line(chest)}", file=sys.stderr)
                        chest += run(hero, "unlock chest", 2.0) + run(hero, "open chest", 2.0)
                        prize = run(hero, "get all chest", 3.0)
                    piece = self.parser.objects[gen.PIECE_VNUMS[level]].short_desc
                    treasure = self.parser.objects[gen.DUNGEON_TREASURE[level]].short_desc
                    # CI reprints only the first line of a failure, so the
                    # chest's own replies lead and the message is one line.
                    self.assertIn(piece.lower(), prize.lower(), one_line(
                        f"Level {level}: chest said [{chest}] prize [{prize}] "
                        f"inventory [{run(hero, 'inventory', 1.0)}] "
                        f"look [{run(hero, 'look', 1.0)}] "
                        f"before [{looted + opened + inside}]"))
                    self.assertIn(treasure.lower(), prize.lower(), prize)
                    items.append(treasure)

                    if level == 9:
                        break

                    # Out by the returning light, and the owl.
                    out = run(hero, "enter light", 3.0)
                    self.assertIn(self.name_of(screen), out, out)
                    self.assertIn("great owl", out, out)
                    self.assertIn(f"Level {level + 1}", out, out)
                    here = screen

                    if level == 6:
                        # The Recorder: any dungeon won, and the next one,
                        # and no other. (At the pond its tune is the pond's:
                        # the Level 7 step below drains it with PLAY RECORDER.)
                        back = run(hero, "blow recorder 1", 4.0)
                        self.assertIn(self.name_of(ho.DUNGEONS[1]["screen"]), back, back)
                        hero.drain(4.0)     # the whirlwind's lag
                        refused = run(hero, "play recorder 8", 3.0)
                        self.assertIn("knows the way", refused, refused)
                        hero.drain(1.0)
                        onward = run(hero, "play recorder", 4.0)
                        self.assertIn(self.name_of(ho.DUNGEONS[2]["screen"]), onward, onward)
                        hero.drain(4.0)
                        flown = run(hero, "play recorder 7", 4.0)
                        self.assertIn(self.name_of(ho.DUNGEONS[7]["screen"]), flown, flown)
                        hero.drain(4.0)
                        here = ho.DUNGEONS[7]["screen"]

                made = run(hero, "combine triforce", 2.0)
                self.assertIn("The Triforce", made, made)


if __name__ == "__main__":
    unittest.main()
