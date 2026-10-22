"""BOMB spends a bomb it can reach, exactly once, before anything goes off
(review, 2026-10-22, G1).

The bag's limit counts every bomb a character owns -- carried at any
depth and in the stash -- but BOMB could only find a bundle in hand or one
bag down, and both of its consumers ignored the failure: a character with
bombs only in the stash blew open walls and hurt Dodongo for nothing, and
the wall opened before the bomb was even looked for. Usable now means
carried, at any depth; the stash still counts against the bag and is
never reached into from afar; a refused target or puzzle costs nothing.

Counts are read from the saved files, so they are the game's own record,
not a parse of what the screen said.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Zbombpass1"
TEMPLE = 4207
BOMBS = 30695
BAG = 3032
DODONGO = 30218
OLD_MAN = 30346

MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))
WALL_ROOM = next(room for room in MANIFEST["overworld"]["rooms"]
                 if room["coordinate"] == "B1")["vnum"]


def record(vnum: int, nest: int, count: int = 0) -> str:
    return ("#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nVal  %d 0 0 0 0\nEnd\n\n"
            % (vnum, nest, count))


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.4)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, level: int, room: int, carried: str = "", stash: str = "") -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    # A level 58 made from a new character keeps a new character's hit
    # points; Dodongo would kill one, and the dead are moved to 4216.
    patch_player_file(mud, name, Levl=level, Room=room, Attr="25 25 25 25 25",
                      HMV="5000 5000 500 500 500 500", HMVP="5000 500 500")
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    extra = carried + ("#STASH\n\n" + stash if stash else "")
    path.write_text(text.replace("#END", extra + "#END", 1), encoding="latin-1")


def prototype_bombs() -> int:
    """A bundle's count when the file omits Val: save.c writes Val only
    when it differs from the prototype's."""
    import sys
    sys.path.insert(0, str(ROOT))
    from webadmin.area_parser import AreaParser
    parser = AreaParser(ROOT / "area")
    parser.parse_all()
    return int(parser.objects[BOMBS].values[0])


def bombs_on_file(mud: LiveMud, name: str) -> tuple[int, int]:
    """(carried, stashed) bombs in the saved file."""
    default = prototype_bombs()
    carried = stashed = 0
    in_stash = False
    vnum = count = None
    for line in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if line.startswith("#STASH"):
            in_stash = True
        elif line.startswith("#O"):
            vnum = count = None
        elif line.startswith("Vnum "):
            vnum = int(line.split()[1])
        elif line.startswith("Val "):
            count = int(line.split()[1])
        elif line == "End" and vnum == BOMBS:
            if in_stash:
                stashed += default if count is None else count
            else:
                carried += default if count is None else count
            vnum = None
    return carried, stashed


@unittest.skipIf(SKIP is not None, SKIP or "")
class BombSpendingTests(unittest.TestCase):
    def test_only_a_carried_bomb_goes_off_and_each_goes_off_once(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zstashbomb", 58, WALL_ROOM, stash=record(BOMBS, 0, 4))
            # Two bags deep: a bag holding a bag holding two bombs.
            make(mud, "Zdeepbomb", 58, WALL_ROOM,
                 carried=record(BAG, 0) + record(BAG, 1) + record(BOMBS, 2, 2))
            make(mud, "Zbombgod", 70, WALL_ROOM)
            with mud.connect(timeout=120) as stash, mud.connect(timeout=120) as deep, \
                    mud.connect(timeout=120) as god:
                login(stash, "Zstashbomb", PASSWORD)
                login(deep, "Zdeepbomb", PASSWORD)
                login(god, "Zbombgod", PASSWORD)

                # Bombs in the stash count against the bag, but open nothing.
                refused = run(stash, "bomb cracked")
                self.assertIn("in your stash", refused, refused)
                self.assertNotIn("blast opens", refused, refused)
                still_shut = run(stash, "down")
                self.assertIn("cannot go that way", still_shut, still_shut)

                # Two bags down is carried: the wall opens and one is spent.
                blast = run(deep, "bomb cracked", 2.0)
                self.assertIn("blast opens a passage", blast, blast)
                gone = run(deep, "bomb cracked")
                self.assertIn("no cracked surface", gone, gone)

                run(god, f"load mob {DODONGO}")
                run(god, f"load mob {OLD_MAN}")

                # A target the game refuses costs nothing.
                run(deep, "bomb man", 1.5)
                # Stash bombs do not hurt Dodongo either.
                swallowed = run(stash, "bomb dodongo", 1.5)
                self.assertIn("in your stash", swallowed, swallowed)
                self.assertNotIn("swallows", swallowed, swallowed)

                # The last carried bomb: Dodongo swallows it, and then there are none.
                last = run(deep, "bomb dodongo", 2.0)
                self.assertIn("swallows it", last, last)
                # The blast's round of lag holds this command until it is
                # paid. Dodongo may have fled the blast; the old man stays.
                empty = run(deep, "bomb man", 5.0)
                self.assertIn("You have no bombs", empty, empty)

                run(god, "slay dodongo", 1.0)   # if it is still here
                run(god, "slay man", 1.0)
                for client in (stash, deep, god):
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            # Exactly one spent on the wall and one on Dodongo; none on the
            # refused old man; the stash untouched.
            self.assertEqual(bombs_on_file(mud, "Zdeepbomb"), (0, 0))
            self.assertEqual(bombs_on_file(mud, "Zstashbomb"), (0, 4))


if __name__ == "__main__":
    unittest.main()
