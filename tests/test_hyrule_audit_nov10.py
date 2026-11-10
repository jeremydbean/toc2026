"""Hyrule's progression, held against the audit of 2026-11-10.

Three investigations found ways round Hyrule's order, each proven on a
live server or traced to the line:

- The Triforce was not NODROP, and it opens every dungeon gate.
- A non-owner looted a player's corpse of a Triforce piece and the Master
  Sword; a rotting corpse spilled them for anybody.
- TELEKINESIS lifted a cave's own Heart Container from anywhere.
- STEAL took a guardian's key with the guardian alive; CHARM PERSON took
  six of the nine guardians, and a charmed one handed its key over, opened
  its shutters and walked out.
- FISTS OF FURY made a guardian flee, and DESPAIR an ordinary enemy.
- An instant kill ended Level 7's guardian (owner: none on the last
  three dungeons' guardians).
- RESURRECTION at a corpse carried into Gohma's nest put a character with
  no pieces there; ASTRAL WALK stood one in a cave still bombed shut.
- PASS DOOR and DOOR BASH beat the small-key doors.

Each is refused now, and each test here fails on the code before.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (WEST_PADDOCK, LiveMud, create_character, login,
                      patch_player_file, room_of, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zauditpass1"
TEMPLE = 4207
DIGDOGGER = 30309
SHARD_TWO = 30401
MASTER_SWORD = 30200
GOHMA_NEST = 30519            # Level 6, behind the fifth piece and the bow
HEART_CAVE = 30655            # a take-any cave, bombed shut at boot
L1_KEY_DOOR_ROOM = 30401      # its north door resets locked (D state 2)
SIGHT = 512                   # infravision: Hyrule's rooms may be dark
PASS_DOOR = 1 << 20           # AFF_PASS_DOOR (U)


def make(mud: LiveMud, name: str, objects: str = "", **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    if objects:
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def add_skill(mud: LiveMud, name: str, skill: str) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    at = text.index("\nEnd\n")
    path.write_text(text[:at] + f"\nSk 100 '{skill}'" + text[at:], encoding="latin-1")


def carried(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


def area_object(vnum: int) -> list[str]:
    lines = (ROOT / "area" / "hyrule.are").read_text(encoding="latin-1").splitlines()
    at = lines.index(f"#{vnum}")
    return lines[at:at + 8]


class AuditSourceTests(unittest.TestCase):
    def test_the_triforce_is_nodrop_like_its_pieces(self) -> None:
        flags = area_object(30286)[5].split()
        self.assertIn("H", flags[1], area_object(30286))
        generator = (ROOT / "scripts" / "build_hyrule_area.py").read_text(encoding="utf-8")
        self.assertIn('"1 ABGHIV A"', generator)

    def test_the_last_three_guardians_defy_instant_death(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        body = fight.split("bool hyrule_defies_instant_death(", 1)[1].split("\n}", 1)[0]
        for name in ("HYRULE_ANCIENT_AQUAMENTUS_VNUM", "HYRULE_ASHEN_GLEEOK_VNUM",
                     "is_hyrule_ganon"):
            self.assertIn(name, body)
        self.assertIn("#define HYRULE_ANCIENT_AQUAMENTUS_VNUM 30314", fight)

    def test_nothing_drives_a_hyrule_creature_off(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        fists = fight.split("You attack in an all consuming fury", 1)[1].split("\n}", 1)[0]
        flee_at = fists.index("do_flee(victim")
        self.assertIn("hyrule_native( victim )", fists[:flee_at])
        self.assertIn("!hyrule_native( victim ) && skill_roll_missed( ch, number_percent( ) > chance )",
                      fists[:flee_at], "a creature of Hyrule never reaches the flight")
        flee = fight.split("void do_flee(", 1)[1].split("\nvoid ", 1)[0]
        self.assertLess(flee.index("hyrule_native( victim )"), flee.index("do_flee(victim"))

    def test_steal_and_charm_ask_first(self) -> None:
        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        steal = act_obj.split("void do_steal(", 1)[1].split("\nvoid ", 1)[0]
        self.assertLess(steal.index("hyrule_native( victim )"), steal.index("WAIT_STATE"))
        magic = (ROOT / "src" / "magic.c").read_text(encoding="latin-1")
        charm = magic.split("void spell_charm_person(", 1)[1].split("\nvoid ", 1)[0]
        self.assertLess(charm.index("hyrule_native( victim )"), charm.index("add_follower"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianControlTests(unittest.TestCase):
    def test_steal_and_charm_are_refused_on_a_guardian(self) -> None:
        hearty = dict(HMV="20000 20000 20000 20000 1000 1000", HMVP="20000 20000 1000",
                      AfBy=SIGHT)
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zauditstaff", Levl=70, Room=WEST_PADDOCK)
            make(mud, "Zauditthief", Levl=40, Room=WEST_PADDOCK, Cla=2,
                 Sk="100 'steal'", **hearty)
            make(mud, "Zauditmage", Levl=50, Room=WEST_PADDOCK, Cla=0,
                 Sk="100 'charm person'", **hearty)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as thief, \
                    mud.connect(timeout=120) as mage:
                for client, name in ((staff, "Zauditstaff"), (thief, "Zauditthief"),
                                     (mage, "Zauditmage")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                staff.must(f"goto {WEST_PADDOCK}", "")
                staff.must(f"load mob {DIGDOGGER}", "You create")
                staff.must("goto 4207", "")
                stolen = thief.sync("steal key digdogger", timeout=60)
                charmed = "".join(mage.sync("cast 'charm person' digdogger", timeout=60)
                                  for _ in range(4))
                master = staff.must("stat mob digdogger", "Vnum:")
                for client in (staff, thief, mage):
                    client.send("quit")
                    client.wait_closed()
        self.assertIn("you win it", stolen, stolen)
        self.assertIn("your charm finds no hold", charmed, charmed)
        self.assertNotRegex(master, r"Master: Zauditmage", master)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BoundItemTests(unittest.TestCase):
    def test_a_corpse_keeps_its_bound_things_for_its_owner(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zauditstaff", Levl=70, Room=WEST_PADDOCK)
            make(mud, "Zauditdead", Levl=30, Room=WEST_PADDOCK,
                 objects=carried(SHARD_TWO) + carried(MASTER_SWORD))
            make(mud, "Zauditlooter", Levl=20, Room=WEST_PADDOCK, AfBy=SIGHT)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as looter:
                login(staff, "Zauditstaff", PW)
                login(looter, "Zauditlooter", PW)
                with mud.connect(timeout=120) as dead:
                    login(dead, "Zauditdead", PW)
                    staff.must(f"goto {WEST_PADDOCK}", "")
                    staff.must("slay zauditdead", "")
                    dead.drain(2.0)
                    dead.send("quit")
                    dead.wait_closed()
                looted = ""
                for _ in range(5):
                    looted = looter.sync("get all corpse", timeout=60)
                    if "laid to rest" not in looted:
                        break
                    looter.drain(2.0)
                pack = looter.sync("inventory", timeout=60)
                for client in (staff, looter):
                    client.send("quit")
                    client.wait_closed()
        self.assertIn("bound to the one who fell", looted, looted)
        self.assertNotIn("Triforce", pack, pack)
        self.assertNotIn("Master Sword", pack, pack)

    def test_telekinesis_and_astral_walk_do_not_reach_a_sealed_cave(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zauditpsi", Levl=50, Room=TEMPLE, Cla=0,
                 Sk="100 'telekinesis'", HMV="2000 2000 20000 20000 1000 1000",
                 HMVP="2000 20000 1000", AfBy=SIGHT)
            add_skill(mud, "Zauditpsi", "astral walk")
            make(mud, "Zauditstaff", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as psi, mud.connect(timeout=120) as staff:
                login(psi, "Zauditpsi", PW)
                login(staff, "Zauditstaff", PW)
                psi.sync("scroll 0")
                lifted = psi.sync("telekinesis container", timeout=60)
                pack = psi.sync("inventory", timeout=60)
                walked = psi.sync("astral ruddy", timeout=60)
                where = room_of(staff, "zauditpsi")
                for client in (psi, staff):
                    client.send("quit")
                    client.wait_closed()
        self.assertNotIn("Heart Container", pack, lifted + pack)
        self.assertIn("slides off", lifted, lifted)
        self.assertNotEqual(where, HEART_CAVE, walked)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GateTests(unittest.TestCase):
    def test_locked_doors_and_carried_corpses_keep_the_order(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zauditstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zauditghost", Levl=40, Room=TEMPLE, Cla=3,
                 Sk="100 'doorbash'", AfBy=SIGHT | PASS_DOOR,
                 HMV="5000 5000 1000 1000 1000 1000", HMVP="5000 1000 1000")
            make(mud, "Zauditrisen", Levl=20, Room=WEST_PADDOCK,
                 HMV="300 300 300 300 300 300", HMVP="300 300 300")
            make(mud, "Zauditcleric", Levl=45, Room=TEMPLE, Cla=1, Gui=1, AfBy=SIGHT,
                 HMV="900 900 2000 2000 500 500", HMVP="900 2000 500")
            add_skill(mud, "Zauditcleric", "resurrection")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as ghost:
                login(staff, "Zauditstaff", PW)
                login(ghost, "Zauditghost", PW)
                ghost.sync("scroll 0")
                staff.must(f"transfer zauditghost {L1_KEY_DOOR_ROOM}", "")
                passed = ghost.sync("north", timeout=60)
                bashed = ghost.sync("doorbash north", timeout=60)
                ghost_room = room_of(staff, "zauditghost")

                with mud.connect(timeout=120) as risen:
                    login(risen, "Zauditrisen", PW)
                    staff.must(f"goto {WEST_PADDOCK}", "")
                    staff.must("slay zauditrisen", "")
                    risen.drain(2.0)
                    taken = ""
                    for _ in range(5):
                        taken = staff.sync("get corpse", timeout=60)
                        if "laid to rest" not in taken:
                            break
                        staff.drain(2.0)
                    staff.must(f"goto {GOHMA_NEST}", "")
                    staff.sync("drop corpse")
                    staff.must("goto 4207", "")
                    with mud.connect(timeout=120) as cleric:
                        login(cleric, "Zauditcleric", PW)
                        staff.must(f"transfer zauditcleric {GOHMA_NEST}", "")
                        offered = cleric.sync("cast resurrection corpse", timeout=60)
                        cleric.send("quit")
                        cleric.wait_closed()
                    risen.drain(1.5)
                    accepted = risen.sync("accept", timeout=60)
                    risen_room = room_of(staff, "zauditrisen")
                    risen.send("quit")
                    risen.wait_closed()
                for client in (staff, ghost):
                    client.send("quit")
                    client.wait_closed()
        self.assertIn("only its key will open it", passed, passed)
        self.assertIn("wants its key", bashed, bashed)
        self.assertEqual(ghost_room, L1_KEY_DOOR_ROOM)
        self.assertIn("soul home", offered, taken + offered)
        self.assertNotEqual(risen_room, GOHMA_NEST, taken + accepted)
        self.assertIn("may not go", accepted, accepted)


if __name__ == "__main__":
    unittest.main()
