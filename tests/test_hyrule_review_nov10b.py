"""Two more ways round Hyrule's bound items and guardians (review,
2026-11-10, against 29e558ff).

1. A charmed follower ORDERed to GET took a bound Hyrule object from an
   offline player's corpse: the ownership guard in get_obj began with
   !IS_NPC(ch), so a mobile was never asked. Once the follower died its
   corpse was an NPC's, which the guard does not know, and anybody could
   loot the piece from it. A mobile is never the owner now, and since
   2026-11-12 no mobile takes anything from a player's corpse at all
   (loot_refusal in act_obj.c): the dagger stays for its owner too, who
   still recovers their own corpse.

2. TRAP THE SOUL asked is_protected_npc, which is not Hyrule's: a level
   51-59 caster with the necromancers' bottle (Neerabd sells it) took a
   guardian whole -- its key gone with it, its shutters reading the room
   as clear, no clear-room reward, and a copy loose wherever the bottle
   was opened. Hyrule's mobiles are refused before the roll; trapping
   anything else is as it was, and the bottle keeps its catch over a
   save.
"""

from __future__ import annotations

import re
import unittest

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, skip_reason)

SKIP = skip_reason()
PW = "Zrevpass11"
SHARD = 30401           # the second Triforce shard: NODROP, bound
MASTER_SWORD = 30200    # bound
BAG = 3032
DAGGER = 3701           # ordinary loot
BOTTLE = 91             # a prison for the soul (Neerabd's stock)
SHARD_THREE = 30402
# Hyrule natives where the review found them bottled (2026-11-10), each in
# its own room: an early guardian, the goriya whose death leaves a
# boomerang, a keese behind a shutter, and Level 7's guardian.
NATIVES = {"aquamentus": 30413, "goriya": 30410, "keese": 30404, "ancient": 30546}
AQUAMENTUS = 30222


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


def obj(vnum: int, nest: int = 0) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev 1\nCond 100\nEnd\n\n" % (vnum, nest)


def world_count(staff, vnum: int) -> int:
    said = staff.must(f"oshow {vnum}", "In the world now:")
    return int(re.search(r"In the world now: (\d+)", said).group(1))


def stat_of(staff, room: int, keyword: str) -> str:
    return staff.must(f"at {room} stat mob {keyword}", "Vnum:")


def field(stat: str, name: str) -> int:
    return int(re.search(name + r":\s*(-?\d+)", stat).group(1))


def quit_all(*clients) -> None:
    for client in clients:
        client.send("quit")
        client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class FollowerLaunderingTests(unittest.TestCase):
    def test_a_follower_takes_no_bound_thing_and_the_owner_still_does(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrevstaff", Levl=70, Room=SPARRING_FLOOR)
            # A shard and the Master Sword loose, a third shard in a bag,
            # and a dagger nothing binds.
            make(mud, "Zrevowner", Levl=30, Room=SPARRING_FLOOR,
                 objects=obj(SHARD) + obj(MASTER_SWORD) + obj(BAG) + obj(SHARD_THREE, 1)
                         + obj(DAGGER))
            make(mud, "Zrevattack", Levl=59, Room=SPARRING_FLOOR, Cla=0,
                 skills=("charm person",),
                 HMV="5000 5000 20000 20000 1000 1000", HMVP="5000 20000 1000")
            staff = mud.connect(timeout=120)
            attacker = mud.connect(timeout=120)
            try:
                login(staff, "Zrevstaff", PW)
                login(attacker, "Zrevattack", PW)
                for client in (staff, attacker):
                    client.sync("scroll 0")

                # Zrevowner dies holding them, and leaves once it settles.
                with mud.connect(timeout=120) as owner:
                    login(owner, "Zrevowner", PW)
                    staff.must("slay zrevowner", "")
                    owner.drain(2.0)
                    owner.send("quit")
                    self.assertTrue(owner.wait_closed())

                # Zrevattack charms a mobile and orders it to loot every way.
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                for _ in range(12):
                    attacker.sync("cast 'charm person' guard", timeout=60)
                    # A failed charm provokes the guard; end it and try again.
                    staff.sync("peace")
                    if "Master: Zrevattack" in staff.must("stat mob guard", "Vnum:"):
                        break
                self.assertIn("Master: Zrevattack", staff.must("stat mob guard", "Vnum:"))
                orders = ""
                for _ in range(6):
                    said = attacker.sync("order guard get all zrevowner", timeout=60)
                    if "laid to rest" not in said:
                        break
                    attacker.drain(2.0)
                for order in ("get shard zrevowner", "get sword zrevowner",
                              "get bag zrevowner", "get zrevowner"):
                    orders += attacker.sync(f"order guard {order}", timeout=60)

                # The follower dies in ordinary combat, and autoloot takes
                # what it carried -- which is nothing of the corpse's.
                staff.must("set char zrevattack hitroll 300", "")
                staff.must("set char zrevattack damroll 300", "")
                attacker.sync("autoloot", timeout=60)
                for _ in range(20):
                    attacker.sync("kill guard", timeout=60)
                    attacker.drain(2.0)
                    if "guard" not in staff.sync(f"at {SPARRING_FLOOR} look", timeout=60):
                        break
                looted = attacker.sync("get all corpse", timeout=60)
                pack = attacker.sync("inventory", timeout=60)
                # Nothing bound reached the attacker, by any of it.
                self.assertNotRegex(pack, r"(?i)triforce shard", orders + looted + pack)
                self.assertNotRegex(pack, r"(?i)master sword", orders + looted + pack)

                # The owner comes back for their own corpse.
                with mud.connect(timeout=120) as owner:
                    login(owner, "Zrevowner", PW)
                    staff.must(f"transfer zrevowner {SPARRING_FLOOR}", "")
                    owner.must("get all zrevowner", "You get")
                    mine = owner.sync("inventory", timeout=60) + owner.sync("look in bag", timeout=60)
                    owner.send("quit")
                    self.assertTrue(owner.wait_closed())
                # And keeps them over a save.
                with mud.connect(timeout=120) as owner:
                    login(owner, "Zrevowner", PW)
                    again = owner.sync("inventory", timeout=60) + owner.sync("look in bag", timeout=60)
                    owner.send("quit")
                    owner.wait_closed()
            finally:
                quit_all(attacker, staff)

        self.assertNotRegex(pack, r"(?i)triforce shard", looted + pack)
        self.assertNotRegex(pack, r"(?i)master sword", looted + pack)
        # No creature takes from a player's corpse (2026-11-12): the
        # ordinary dagger stays there for its owner too.
        self.assertNotRegex(pack, r"(?i)dagger", "a creature took loot: " + orders + looted + pack)
        for held in (mine, again):
            self.assertRegex(held, r"(?i)dagger", held)
            self.assertEqual(len(re.findall(r"(?i)triforce shard", held)), 2, held)
            self.assertRegex(held, r"(?i)master sword", held)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SoulTrapTests(unittest.TestCase):
    def test_hyrule_refuses_the_bottle_and_elsewhere_takes_it(self) -> None:
        bottle_of_aquamentus = ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\n"
                                "Val  0 0 0 %d 0\nEnd\n\n" % (BOTTLE, AQUAMENTUS))
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrevstaff", Levl=70, Room=SPARRING_FLOOR)
            make(mud, "Zrevsouler", Levl=59, Room=SPARRING_FLOOR, Cla=5, Gui=5,
                 AfBy=512, skills=("trap the soul",),
                 objects=obj(BOTTLE) + obj(BOTTLE) + obj(BOTTLE),
                 HMV="5000 5000 30000 30000 1000 1000", HMVP="5000 30000 1000")
            # One filled with Aquamentus before Hyrule refused the spell.
            make(mud, "Zrevkeeper", Levl=30, Room=SPARRING_FLOOR,
                 objects=bottle_of_aquamentus)
            staff = mud.connect(timeout=120)
            souler = mud.connect(timeout=120)
            try:
                login(staff, "Zrevstaff", PW)
                login(souler, "Zrevsouler", PW)
                for client in (staff, souler):
                    client.sync("scroll 0")

                seen = {}
                for keyword, room in NATIVES.items():
                    staff.must(f"transfer zrevsouler {room}", "")
                    if keyword == "keese":
                        seen["shut before"] = souler.sync("east", timeout=60)
                    before = (stat_of(staff, room, keyword),
                              staff.sync(f"at {room} look", timeout=60))
                    said = "".join(souler.sync(f"cast 'trap the soul' {keyword}", timeout=60)
                                   for _ in range(3))
                    after = (stat_of(staff, room, keyword),
                             staff.sync(f"at {room} look", timeout=60))
                    if keyword == "keese":
                        seen["shut after"] = souler.sync("east", timeout=60)
                    seen[keyword] = (before, said, after)
                bottles = souler.sync("inventory", timeout=60)
                for keyword in NATIVES:
                    _, said, after = seen[keyword]
                    self.assertIn("bound to Hyrule", said, f"{keyword}: {said}")
                    self.assertIn(f"Room: {NATIVES[keyword]}", after[0], f"{keyword} is gone")

                # An old bottle of Aquamentus lets nothing loose.
                with mud.connect(timeout=120) as keeper:
                    login(keeper, "Zrevkeeper", PW)
                    released = keeper.sync("open bottle", timeout=60)
                    keeper_room = staff.sync(f"at {SPARRING_FLOOR} look", timeout=60)
                    keeper.send("quit")
                    keeper.wait_closed()
                aquamentus = stat_of(staff, NATIVES["aquamentus"], "aquamentus")

                # Anywhere else, the spell takes as it always did ...
                staff.must(f"transfer zrevsouler {SPARRING_FLOOR}", "")
                staff.must(f"at {SPARRING_FLOOR} load mob {SPARRING_GUARD}", "")
                trapped = ""
                for _ in range(15):
                    trapped = souler.sync("cast 'trap the soul' guard", timeout=60)
                    # A failed cast provokes the guard; QUIT is refused mid-fight.
                    staff.sync(f"at {SPARRING_FLOOR} peace")
                    if "sucked into" in trapped:
                        break
                # ... the catch is kept over a save ...
                souler.send("quit")
                self.assertTrue(souler.wait_closed())
                souler = mud.connect(timeout=120)
                login(souler, "Zrevsouler", PW)
                kept = souler.sync("inventory", timeout=60)
                # ... and lets it out again.
                let_out = ""
                for n in (1, 2, 3):
                    let_out = souler.sync(f"open {n}.bottle", timeout=60)
                    if "let out" in let_out:
                        break
                guard = staff.must(f"at {SPARRING_FLOOR} stat mob guard", "Vnum:")
            finally:
                quit_all(souler, staff)

        for keyword in NATIVES:
            before, said, after = seen[keyword]
            self.assertIn("bound to Hyrule", said, f"{keyword}: {said}")
            self.assertEqual(field(after[0], "Room"), NATIVES[keyword], keyword)
            self.assertEqual(field(after[0], "Count"), field(before[0], "Count"), keyword)
            self.assertEqual(field(after[0], "Carry number"), field(before[0], "Carry number"),
                             f"{keyword} holds what it held")
            self.assertEqual(after[1], before[1], f"{keyword}: its room, shutters and rewards")
        self.assertIn("sealed fast", seen["shut before"], seen["shut before"])
        self.assertIn("sealed fast", seen["shut after"], seen["shut after"])
        empty = sum(int(n or 1) for n in
                    re.findall(r"(?:\(\s*(\d+)\)\s*)?a prison for the soul", bottles))
        self.assertEqual(empty, 3, "every bottle still empty: " + bottles)
        self.assertIn("back to Hyrule", released, released)
        self.assertNotRegex(keeper_room, r"(?i)aquamentus", keeper_room)
        self.assertEqual(field(aquamentus, "Count"), 1, "one Aquamentus in the world")
        self.assertIn("sucked into", trapped, trapped)
        self.assertRegex(kept, r"essence of", "the catch is saved: " + kept)
        self.assertIn("let out", let_out, let_out)
        self.assertEqual(field(guard, "Room"), SPARRING_FLOOR, guard)


if __name__ == "__main__":
    unittest.main()
