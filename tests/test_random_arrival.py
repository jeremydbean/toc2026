"""Random arrivals keep the rules of the room arrived in (review,
2026-11-10).

TELEPORT and get_random_room (recall misfires, FLING) chose rooms by vnum
at random against their own short lists, which never asked
travel_spell_refuses: Heartglow Hollow (30655), a cave whose only way out
is a secret bomb opening still shut, passed both. TELEPORT also asked the
caster's sight and rules when it moved somebody else. Now both ask
travel_spell_refuses of the character moved, a mobile included for a
sealed room.

TOC_RANDOM_ROOM makes a selector's first guess that room, so whether the
cave would be taken is asked once, not left to a random draw: while it is
sealed every route lands elsewhere; once a bomb opens it, each lands there.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, room_of, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zrandpass11"
CAVE = 30655            # Heartglow Hollow: sole exit the bomb opening up
SCREEN = 30292          # the screen above it, with the cracked floor
BOMBS = 30695


def make(mud: LiveMud, name: str, objects: str = "", skills=(), **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    for skill in skills:
        at = text.index("\nEnd\n")
        text = text[:at] + f"\nSk 100 '{skill}'" + text[at:]
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def mob_room(staff, keyword: str) -> int:
    stat = staff.must(f"stat mob {keyword}", "Room:")
    return int(re.search(r"Room: (-?\d+)", stat).group(1))


class RandomArrivalSourceTests(unittest.TestCase):
    def test_both_selectors_ask_of_the_one_moved(self) -> None:
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        rnd = move.split("ROOM_INDEX_DATA *get_random_room(CHAR_DATA *ch)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("travel_spell_refuses(ch, candidate)", rnd)
        refuses = move.split("bool travel_spell_refuses( CHAR_DATA *ch, ROOM_INDEX_DATA *to )", 1)[1]
        refuses = refuses.split("\n}\n", 1)[0]
        self.assertLess(refuses.index("hyrule_room_sealed( to )"), refuses.index("IS_NPC(ch)"),
                        "a mobile sent into a sealed room is refused too")
        magic = (ROOT / "src" / "magic.c").read_text(encoding="latin-1")
        tele = magic.split("void spell_teleport(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("can_see_room(victim,candidate)", tele)
        self.assertIn("travel_spell_refuses(victim,candidate)", tele)
        self.assertNotIn("can_see_room(ch,candidate)", tele)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RandomArrivalLiveTests(unittest.TestCase):
    def test_a_sealed_cave_is_no_random_destination_until_opened(self) -> None:
        hearty = dict(HMV="5000 5000 30000 30000 1000 1000", HMVP="5000 30000 1000",
                      AfBy=512)
        with LiveMud(fixtures=True, extra_env={"TOC_RANDOM_ROOM": str(CAVE)}) as mud:
            make(mud, "Zrandstaff", Levl=70, Room=SPARRING_FLOOR)
            make(mud, "Zrandflung", Levl=30, Room=SPARRING_FLOOR, **hearty)
            make(mud, "Zrandmage", Levl=59, Room=SPARRING_FLOOR, Cla=0,
                 skills=("teleport",), **hearty)
            make(mud, "Zrandbomber", Levl=40, Room=SCREEN,
                 objects="#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nVal  4 0 0 0 0\nEnd\n\n"
                         % BOMBS, **hearty)
            staff = mud.connect(timeout=120)
            flung = mud.connect(timeout=120)
            mage = mud.connect(timeout=120)
            bomber = mud.connect(timeout=120)
            clients = (mage, flung, bomber, staff)
            try:
                for client, name in ((staff, "Zrandstaff"), (flung, "Zrandflung"),
                                     (mage, "Zrandmage"), (bomber, "Zrandbomber")):
                    login(client, name, PW)
                    client.sync("scroll 0")

                def round_of_arrivals() -> dict:
                    """Each route once; the forced first guess is the cave."""
                    seen = {}
                    staff.must(f"transfer zrandflung {SPARRING_FLOOR}", "")
                    staff.must("fling zrandflung", "")
                    seen["fling"] = room_of(staff, "zrandflung")
                    staff.must(f"transfer zrandmage {SPARRING_FLOOR}", "")
                    mage.sync("cast teleport", timeout=60)
                    seen["teleport self"] = room_of(staff, "zrandmage")
                    # Another, a mobile: it gets two saves, so a few casts.
                    staff.must(f"transfer zrandmage {SPARRING_FLOOR}", "")
                    staff.must(f"at {SPARRING_FLOOR} load mob {SPARRING_GUARD}", "")
                    for _ in range(8):
                        said = mage.sync("cast teleport guard", timeout=60)
                        staff.sync(f"at {SPARRING_FLOOR} peace")
                        if "failed" not in said:
                            break
                    seen["teleport other"] = mob_room(staff, "guard")
                    staff.sync(f"at {seen['teleport other']} purge guard")
                    return seen

                sealed = round_of_arrivals()
                opened = bomber.sync("bomb cracked", timeout=60)
                self.assertIn("blast opens", opened, opened)
                unsealed = round_of_arrivals()
            finally:
                for client in clients:
                    client.send("quit")
                    client.wait_closed()

        self.assertNotIn(CAVE, sealed.values(), sealed)
        self.assertEqual(unsealed, {"fling": CAVE, "teleport self": CAVE,
                                    "teleport other": CAVE}, unsealed)


if __name__ == "__main__":
    unittest.main()
