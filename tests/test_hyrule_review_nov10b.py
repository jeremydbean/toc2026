"""Two more ways round Hyrule's bound items and guardians (review,
2026-11-10, against 29e558ff).

1. A charmed follower ORDERed to GET took a bound Hyrule object from an
   offline player's corpse: the ownership guard in get_obj began with
   !IS_NPC(ch), so a mobile was never asked. Once the follower died its
   corpse was an NPC's, which the guard does not know, and anybody could
   loot the piece from it. A mobile is never the owner now; ordinary loot
   still goes, and the owner still recovers their own corpse.

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
DIGDOGGER, DEN = 30309, 30489
DIGDOGGER_CARRIES = (30374, 30586, 30595)
KEESE, KEESE_ROOM = 31110, 30400


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


def quit_all(*clients) -> None:
    for client in clients:
        client.send("quit")
        client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class FollowerLaunderingTests(unittest.TestCase):
    def test_a_follower_takes_no_bound_thing_and_the_owner_still_does(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrevstaff", Levl=70, Room=SPARRING_FLOOR)
            # The shard loose, the Master Sword in a bag: direct and nested.
            make(mud, "Zrevowner", Levl=30, Room=SPARRING_FLOOR,
                 objects=obj(SHARD) + obj(BAG) + obj(MASTER_SWORD, 1) + obj(DAGGER))
            make(mud, "Zrevattack", Levl=50, Room=SPARRING_FLOOR, Cla=0,
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

                # Zrevattack charms a mobile and orders it to loot.
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                for _ in range(12):
                    attacker.sync("cast 'charm person' guard", timeout=60)
                    # A failed charm provokes the guard; end it and try again.
                    staff.sync("peace")
                    if "Master: Zrevattack" in staff.must("stat mob guard", "Vnum:"):
                        break
                self.assertIn("Master: Zrevattack", staff.must("stat mob guard", "Vnum:"))
                for _ in range(6):
                    ordered = attacker.sync("order guard get all zrevowner", timeout=60)
                    if "laid to rest" not in ordered:
                        break
                    attacker.drain(2.0)
                attacker.sync("order guard get shard zrevowner", timeout=60)
                attacker.sync("order guard get bag zrevowner", timeout=60)
                attacker.sync("order guard get zrevowner", timeout=60)

                # The follower dies, and its corpse is looted.
                staff.must("slay guard", "")
                looted = attacker.sync("get all corpse", timeout=60)
                pack = attacker.sync("inventory", timeout=60)

                # The owner comes back for their own corpse.
                with mud.connect(timeout=120) as owner:
                    login(owner, "Zrevowner", PW)
                    staff.must(f"transfer zrevowner {SPARRING_FLOOR}", "")
                    owner.must("get all zrevowner", "You get")
                    mine = owner.sync("inventory", timeout=60)
                    in_bag = owner.sync("look in bag", timeout=60)
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
        self.assertRegex(pack, r"(?i)dagger", "ordinary loot still goes: " + looted + pack)
        self.assertRegex(mine, r"(?i)triforce shard", mine)
        self.assertRegex(in_bag, r"(?i)master sword", in_bag)
        self.assertRegex(again, r"(?i)triforce shard")
        self.assertRegex(again, r"(?i)master sword")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SoulTrapTests(unittest.TestCase):
    def test_hyrule_refuses_the_bottle_and_elsewhere_takes_it(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrevstaff", Levl=70, Room=SPARRING_FLOOR)
            make(mud, "Zrevsouler", Levl=58, Room=SPARRING_FLOOR, Cla=5, Gui=5,
                 AfBy=512, skills=("trap the soul",), objects=obj(BOTTLE) + obj(BOTTLE),
                 HMV="5000 5000 30000 30000 1000 1000", HMVP="5000 30000 1000")
            staff = mud.connect(timeout=120)
            souler = mud.connect(timeout=120)
            try:
                login(staff, "Zrevstaff", PW)
                login(souler, "Zrevsouler", PW)
                for client in (staff, souler):
                    client.sync("scroll 0")

                # The guardian, in its own den.
                staff.must(f"transfer zrevsouler {DEN}", "")
                carried = [world_count(staff, v) for v in DIGDOGGER_CARRIES]
                den_before = staff.sync(f"at {DEN} look", timeout=60)
                guardian = "".join(souler.sync("cast 'trap the soul' digdogger", timeout=60)
                                   for _ in range(4))
                stat = staff.must(f"at {DEN} stat mob digdogger", "Vnum:")
                den_after = staff.sync(f"at {DEN} look", timeout=60)
                carried_after = [world_count(staff, v) for v in DIGDOGGER_CARRIES]

                # An ordinary dungeon foe.
                staff.must(f"transfer zrevsouler {KEESE_ROOM}", "")
                staff.must(f"at {KEESE_ROOM} load mob {KEESE}", "")
                foe = "".join(souler.sync("cast 'trap the soul' keese", timeout=60)
                              for _ in range(4))
                keese_here = staff.sync(f"at {KEESE_ROOM} look", timeout=60)
                bottles = souler.sync("inventory", timeout=60)

                # Anywhere else, the spell takes as it always did.
                staff.must(f"transfer zrevsouler {SPARRING_FLOOR}", "")
                staff.must(f"at {SPARRING_FLOOR} load mob {SPARRING_GUARD}", "")
                trapped = ""
                for _ in range(15):
                    trapped = souler.sync("cast 'trap the soul' guard", timeout=60)
                    if "sucked into" in trapped:
                        break
                souler.send("quit")
                self.assertTrue(souler.wait_closed())
                souler = mud.connect(timeout=120)
                login(souler, "Zrevsouler", PW)
                kept = souler.sync("inventory", timeout=60)
            finally:
                quit_all(souler, staff)

        self.assertIn("bound to Hyrule", guardian, guardian)
        self.assertRegex(stat, r"Room: %d\b" % DEN, "the guardian is where it was")
        self.assertEqual(carried_after, carried, "and holds what it held")
        self.assertEqual(den_after, den_before, "shutters, rewards and all")
        self.assertIn("bound to Hyrule", foe, foe)
        self.assertRegex(keese_here, r"(?i)keese", "the foe is where it was")
        empty = sum(int(n or 1) for n in
                    re.findall(r"(?:\(\s*(\d+)\)\s*)?a prison for the soul", bottles))
        self.assertEqual(empty, 2, "both bottles still empty: " + bottles)
        self.assertIn("sucked into", trapped, trapped)
        self.assertRegex(kept, r"essence of", "the catch is saved: " + kept)


if __name__ == "__main__":
    unittest.main()
