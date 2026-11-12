"""Guardian keys and progression items are each player's own (owner and
review, 2026-11-10).

The review reproduced three ways round a dungeon's guardian, all through
its key: a guardian carried one key, which fell into its corpse for
whoever looted it and could be given, lent and kept, so

- one player handed all eight keys to a friend, who took every piece
  past living guardians;
- a bystander took the piece from a chest another player had opened;
- a key kept over a reset opened the refilled chest with the guardian
  standing there again.

Now a guardian carries no key. Its death hands each player the kill
credits -- the killer, a pet's master, and their group in the room, the
boss achievements' own rule -- a key of their own, NODROP. A chest's
prize is a copy given to somebody carrying the dungeon's key, which the
claim spends (Ganon's once the ninth piece and the Master Sword are both
held), and the chest keeps its own for the rest of the party. Everything
else the progression asks for -- the tools the guardians' chambers and
the overworld want, and the Silver Arrow -- is bound too, and GET in
Hyrule hands each player a copy (owner: nothing required for progression
may be traded).

Ganon's finishing phase was AFF2_NO_RECOVER, which NERVE DAMAGE and
NIGHTMARE also lay: either put him at full health into the phase the
Silver Arrow finishes (confirmed live). It is his own marker now.
"""

from __future__ import annotations

import re
import time
import unittest

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, room_of, skip_reason)

SKIP = skip_reason()
PW = "Zkeyspass11"
SIGHT = 8 | 32 | 512            # detect invis, detect hidden, infravision
TEMPLE = 4207
LAIR, TREASURE = 30413, 30414   # Level 1: Aquamentus, and the Eagle's chest
GANON_LAIR, GANON_TREASURE = 30607, 30615
RAFT_CELLAR = 30454             # Level 3's cellar, where the raft lies
KEYS = [30629 + level for level in range(1, 9)]
GOLDEN_KEY = 30243
BAG = 3032
SILVER = 30218


def make(mud: LiveMud, name: str, objects: str = "", skills=(), **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    fields.setdefault("AfBy", SIGHT)
    fields.setdefault("HMV", "30000 30000 30000 30000 1000 1000")
    fields.setdefault("HMVP", "30000 30000 1000")
    patch_player_file(mud, name, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    for skill in skills:
        at = text.index("\nEnd\n")
        text = text[:at] + f"\nSk 100 '{skill}'" + text[at:]
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def obj(vnum: int, level: int = 1) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev %d\nCond 100\nEnd\n\n" % (vnum, level)


def connect(mud: LiveMud, *names: str) -> list:
    clients = []
    for name in names:
        client = mud.connect(timeout=120)
        login(client, name, PW)
        client.sync("scroll 0")
        clients.append(client)
    return clients


def quit_all(*clients) -> None:
    for client in clients:
        client.send("quit")
        client.wait_closed(10)


def kill(staff, killer, keyword: str, room: int, rounds: int = 40) -> str:
    """Fight it to the end, a blow that lands every round."""
    staff.must(f"set char {killer.name.lower()} hitroll 300", "")
    staff.must(f"set char {killer.name.lower()} damroll 300", "")
    said = killer.sync(f"kill {keyword}", timeout=60)
    for _ in range(rounds):
        if "is DEAD" in said:
            break
        said += killer.drain(2.0)
    return said


def mob_stat(staff, room: int, keyword: str) -> str:
    return staff.sync(f"at {room} stat mob {keyword}", timeout=60)


def hp_of(stat: str):
    found = re.search(r"Hp: (-?\d+)/(\d+)", stat)
    pos = re.search(r"Position: (\d+)", stat)
    return (int(found.group(1)), int(found.group(2)), int(pos.group(1))) if found else None


class ClaimSourceTests(unittest.TestCase):
    def test_only_the_dungeons_own_chest_or_floor_is_a_claim(self) -> None:
        """Review of c3923e53: any container in Hyrule was taken for the
        chest -- a player's own corpse among them."""
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "scripts"))
        from build_hyrule_area import CHESTS
        self.assertEqual(CHESTS, {level: 30639 + level for level in range(1, 10)})
        hyrule = (root / "src" / "hyrule.c").read_text(encoding="latin-1")
        chest = hyrule.split("bool hyrule_chest_claim(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("container->pIndexData->vnum != OBJ_VNUM_HYRULE_CHEST_FIRST + level - 1",
                      chest)
        tool = hyrule.split("bool hyrule_tool_claim(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("if ( container != NULL )\n        return false;", tool)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GroupKeyTests(unittest.TestCase):
    def test_a_group_kill_keys_each_and_the_chest_serves_only_key_holders(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            for name in ("Zkeyone", "Zkeytwo", "Zkeyby"):
                make(mud, name, Levl=58, Room=TEMPLE, objects=obj(BAG))
            staff, one, two, by = connect(mud, "Zkeystaff", "Zkeyone", "Zkeytwo", "Zkeyby")
            for client in (one, two, by):
                client.name = {one: "Zkeyone", two: "Zkeytwo", by: "Zkeyby"}[client]
            try:
                for name in ("zkeyone", "zkeytwo", "zkeyby"):
                    staff.must(f"transfer {name} {LAIR}", "")
                two.must("follow zkeyone", "You now follow")
                one.must("group zkeytwo", "")
                fought = kill(staff, one, "aquamentus", LAIR)
                self.assertIn("is DEAD", fought, fought)

                keys = {c.name: c.sync("inventory", timeout=60) for c in (one, two, by)}
                corpse = staff.sync(f"at {LAIR} look in corpse", timeout=60)

                # Bound: nowhere but its holder's hands.
                tries = "".join(one.sync(line, timeout=60) for line in (
                    "give key zkeyby", "drop key", "put key bag", "donate key"))
                still = one.sync("inventory", timeout=60)

                # The chest: one opens it and claims; the bystander walks in.
                opened = "".join(one.sync(line, timeout=60) for line in (
                    "unlock east", "open east", "east", "unlock chest", "open chest"))
                claimed = one.sync("get all chest", timeout=60)
                after_claim = one.sync("inventory", timeout=60)
                by.sync("east", timeout=60)
                stolen = by.sync("get all chest", timeout=60)
                by_pack = by.sync("inventory", timeout=60)
                # The other of the party still claims theirs.
                two.sync("east", timeout=60)
                second = two.sync("get all chest", timeout=60)
                two_pack = two.sync("inventory", timeout=60)
                in_chest = staff.sync(f"at {TREASURE} look in chest", timeout=60)

                # After a reset the spent key is not there to open it again.
                staff.must(f"goto {LAIR}", "")
                staff.must("repop", "repopulated")
                staff.must("goto 4207", "")
                again = "".join(one.sync(line, timeout=60) for line in (
                    "unlock chest", "open chest", "get all chest"))
                again_pack = one.sync("inventory", timeout=60)
                alive = mob_stat(staff, LAIR, "aquamentus")
                # The reset left the treasure door open on them: the spent
                # key no longer unlocks it, and the dungeon is no-recall.
                one.sync("west", timeout=60)
                walked_out = room_of(staff, "zkeyone")
            finally:
                quit_all(one, two, by, staff)

        self.assertEqual(len(re.findall(r"Eagle's key", keys["Zkeyone"])), 1, keys)
        self.assertEqual(len(re.findall(r"Eagle's key", keys["Zkeytwo"])), 1, keys)
        self.assertNotIn("Eagle's key", keys["Zkeyby"], "a bystander gets none")
        self.assertNotIn("key", corpse.lower().split("contains", 1)[-1], corpse)
        self.assertIn("Eagle's key", still, tries)
        self.assertNotIn("You give", tries)
        self.assertNotIn("You drop", tries)
        self.assertNotIn("You put", tries)
        self.assertIn("first Triforce shard", claimed, opened + claimed)
        self.assertIn("crumbles away", claimed, claimed)
        self.assertNotIn("Eagle's key", after_claim)
        self.assertIn("you carry none", stolen, stolen)
        self.assertNotIn("Triforce", by_pack, by_pack)
        self.assertIn("first Triforce shard", second, second)
        self.assertRegex(two_pack, r"first Triforce shard")
        self.assertIn("first Triforce shard", in_chest, "the chest keeps its own")
        self.assertNotIn("You get", again, again)
        self.assertEqual(len(re.findall(r"first Triforce shard", again_pack)), 1, again_pack)
        self.assertIn(f"Room: {LAIR}", alive, "the guardian is back")
        self.assertEqual(walked_out, LAIR, "nobody is shut in the treasure room")


@unittest.skipIf(SKIP is not None, SKIP or "")
class LateJoinerTests(unittest.TestCase):
    """Owner, 2026-11-10: a player who joined the fight late gets the key
    -- grouped with the killer or not -- if they are in the room when the
    guardian falls; one who struck it and left the room does not."""

    def test_a_late_fighter_in_the_room_is_keyed_and_one_who_left_is_not(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            for name in ("Zkeylead", "Zkeylate", "Zkeygone"):
                make(mud, name, Levl=58, Room=TEMPLE)
            staff, lead, late, gone = connect(mud, "Zkeystaff", "Zkeylead", "Zkeylate", "Zkeygone")
            lead.name = "Zkeylead"
            try:
                for name in ("zkeylead", "zkeylate", "zkeygone"):
                    staff.must(f"transfer {name} {LAIR}", "")
                staff.must(f"at {LAIR} set char aquamentus hp 30000", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                # Two strike it, ungrouped; one of them leaves before it falls.
                late.sync("kill aquamentus", timeout=60)
                gone.sync("kill aquamentus", timeout=60)
                late.drain(3.0)
                staff.must(f"at {LAIR} peace", "")
                staff.must(f"transfer zkeygone {TEMPLE}", "")
                staff.must(f"at {LAIR} set char aquamentus hp 10", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                fought = kill(staff, lead, "aquamentus", LAIR)
                packs = {c: c.sync("inventory", timeout=60) for c in (lead, late, gone)}
            finally:
                quit_all(lead, late, gone, staff)
        self.assertIn("is DEAD", fought, fought)
        self.assertIn("Eagle's key", packs[lead], "the killer")
        self.assertIn("Eagle's key", packs[late], "a late fighter, ungrouped, in the room")
        self.assertNotIn("Eagle's key", packs[gone], "one who left before it fell")


@unittest.skipIf(SKIP is not None, SKIP or "")
class LendingTests(unittest.TestCase):
    def test_no_key_or_tool_can_be_lent(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            make(mud, "Zkeydonor", Levl=59, Room=TEMPLE,
                 objects="".join(obj(v, 1) for v in KEYS + [GOLDEN_KEY, SILVER])
                         + obj(30411) + obj(30222))
            make(mud, "Zkeyborrow", Levl=59, Room=TEMPLE)
            make(mud, "Zkeyfinder", Levl=59, Room=RAFT_CELLAR)
            staff, donor, borrower, finder = connect(
                mud, "Zkeystaff", "Zkeydonor", "Zkeyborrow", "Zkeyfinder")
            try:
                given = "".join(donor.sync(f"give {kw} zkeyborrow", timeout=60) for kw in
                                ["key"] * 9 + ["arrow", "raft", "bow"])
                lent = borrower.sync("inventory", timeout=60)
                # A tool lying in Hyrule: a copy each, one each.
                staff.must(f"transfer zkeyborrow {RAFT_CELLAR}", "")
                first = finder.sync("get raft", timeout=60)
                second = borrower.sync("get raft", timeout=60)
                twice = finder.sync("get raft", timeout=60)
                floor = staff.sync(f"at {RAFT_CELLAR} look", timeout=60)
            finally:
                quit_all(donor, borrower, finder, staff)
        self.assertNotIn("You give", given, given)
        self.assertNotRegex(lent, r"(?i)key|silver arrow|raft|bow", lent)
        self.assertIn("You get the dungeon raft", first, first)
        self.assertIn("You get the dungeon raft", second, second)
        self.assertIn("already carry", twice, twice)
        self.assertIn("raft", floor.lower(), "the raft stays for the next")


@unittest.skipIf(SKIP is not None, SKIP or "")
class PetCreditTests(unittest.TestCase):
    def test_a_pets_kill_keys_its_master(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zkeystaff", Levl=70, Room=SPARRING_FLOOR, AfBy=0)
            make(mud, "Zkeymaster", Levl=59, Room=SPARRING_FLOOR, Cla=0,
                 skills=("charm person",))
            staff, master = connect(mud, "Zkeystaff", "Zkeymaster")
            try:
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                for _ in range(12):
                    master.sync("cast 'charm person' guard", timeout=60)
                    staff.sync("peace")
                    if "Master: Zkeymaster" in staff.must("stat mob guard", "Vnum:"):
                        break
                staff.must("set char guard damroll 300", "")
                staff.must("set char guard hitroll 300", "")
                staff.must(f"transfer zkeymaster {LAIR}", "")
                staff.must(f"transfer guard {LAIR}", "")
                fought = master.sync("order guard kill aquamentus", timeout=60)
                for _ in range(40):
                    if "is DEAD" in fought:
                        break
                    fought += master.drain(2.0)
                pack = master.sync("inventory", timeout=60)
                guard = staff.sync(f"at {LAIR} stat mob guard", timeout=60)
            finally:
                quit_all(master, staff)
        self.assertIn("is DEAD", fought, fought)
        self.assertIn("Eagle's key", pack, "the master is credited")
        self.assertIn("Carry number: 0", guard, "the pet holds none")


@unittest.skipIf(SKIP is not None, SKIP or "")
class GanonChestTests(unittest.TestCase):
    def test_the_piece_and_the_sword_in_either_order(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            orders = {"Zkeypiece": ("get piece chest", "get sword chest"),
                      "Zkeysword": ("get sword chest", "get piece chest"),
                      "Zkeyall": ("get all chest",)}
            for name in orders:
                make(mud, name, Levl=59, Room=GANON_TREASURE, objects=obj(GOLDEN_KEY))
            clients = connect(mud, "Zkeystaff", *orders)
            staff, players = clients[0], dict(zip(orders, clients[1:]))
            seen = {}
            try:
                players["Zkeypiece"].sync("unlock chest", timeout=60)
                players["Zkeypiece"].sync("open chest", timeout=60)
                for name, lines in orders.items():
                    said = [players[name].sync(line, timeout=60) for line in lines]
                    seen[name] = (said, players[name].sync("inventory", timeout=60))
                chest = staff.sync(f"at {GANON_TREASURE} look in chest", timeout=60)
            finally:
                quit_all(*players.values(), staff)
        first, _ = seen["Zkeypiece"]
        self.assertNotIn("crumbles", first[0], "the key waits for the sword")
        self.assertIn("crumbles", first[1], first)
        swordfirst, _ = seen["Zkeysword"]
        self.assertNotIn("crumbles", swordfirst[0])
        self.assertIn("crumbles", swordfirst[1], swordfirst)
        for name, (_, pack) in seen.items():
            self.assertIn("final Triforce piece", pack, name)
            self.assertIn("Master Sword", pack, name)
            self.assertNotIn("Golden Key", pack, name)
        self.assertIn("final Triforce piece", chest)
        self.assertIn("Master Sword", chest)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseRecoveryTests(unittest.TestCase):
    """Review of c3923e53 (2026-11-10): the chest claim fired for any
    container in Hyrule, a player's own corpse included, so an owner who
    died there with a piece and the Master Sword -- their keys long spent
    -- was refused both. Only the dungeon's own chest is a claim; a corpse
    gives its owner back the very objects it holds, and nobody else."""

    def test_an_owner_takes_their_pieces_back_from_their_corpse(self) -> None:
        # The Master Sword nested in a bag, to hold the stranger's refusal
        # to a container in the corpse as well as to the corpse.
        nested = ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n"
                  "#O\nVnum 30200\nNest 1\nWear -1\nLev 58\nCond 100\nEnd\n\n" % BAG)
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            make(mud, "Zkeyfallen", Levl=59, Room=TREASURE, objects=obj(KEYS[0]) + nested)
            make(mud, "Zkeyother", Levl=59, Room=TREASURE)
            staff, other = connect(mud, "Zkeystaff", "Zkeyother")
            try:
                shards = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30400", "In the world now:")).group(1))
                swords = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30200", "In the world now:")).group(1))
                with mud.connect(timeout=120) as fallen:
                    login(fallen, "Zkeyfallen", PW)
                    fallen.sync("scroll 0")
                    # The claim spends the key.
                    claimed = "".join(fallen.sync(line, timeout=60) for line in (
                        "unlock chest", "open chest", "get shard chest"))
                    keyless = fallen.sync("inventory", timeout=60)
                    staff.must(f"at {TREASURE} slay zkeyfallen", "")
                    fallen.drain(2.0)
                    staff.must(f"transfer zkeyother {TREASURE}", "")
                    taken = ""
                    for _ in range(6):
                        taken = other.sync("get all zkeyfallen", timeout=60)
                        if "laid to rest" not in taken:
                            break
                        other.drain(2.0)
                    taken += other.sync("get bag zkeyfallen", timeout=60)
                    taken += other.sync("get shard zkeyfallen", timeout=60)
                    staff.must(f"transfer zkeyfallen {TREASURE}", "")
                    back = fallen.sync("get all zkeyfallen", timeout=60)
                    pack = fallen.sync("inventory", timeout=60)
                    left = staff.sync(f"at {TREASURE} look in zkeyfallen", timeout=60)
                    fallen.send("quit")
                    self.assertTrue(fallen.wait_closed())
                shards_after = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30400", "In the world now:")).group(1))
                swords_after = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30200", "In the world now:")).group(1))
                other_pack = other.sync("inventory", timeout=60)
            finally:
                quit_all(other, staff)
        self.assertIn("crumbles away", claimed, claimed)
        self.assertNotIn("Eagle's key", keyless, keyless)
        self.assertNotIn("you carry none", back, back)
        self.assertEqual(len(re.findall(r"first Triforce shard", pack)), 1, back + pack)
        self.assertIn("bag", pack.lower(), back + pack)
        self.assertNotIn("Triforce", left, "nothing left behind: " + left)
        self.assertNotIn("bag", left.split("contains", 1)[-1].lower(), left)
        # Counted while the fallen is away: the chest's copy left with them.
        self.assertEqual((shards_after, swords_after), (shards, swords), "no copy was made")
        # Refused, by the looting rule or the bound one.
        self.assertRegex(taken, r"bound to the one who fell|given leave to loot it", taken)
        self.assertNotIn("You get", taken, taken)
        self.assertNotRegex(other_pack, r"Triforce|Master Sword|bag", taken + other_pack)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CreatureLaunderingTests(unittest.TestCase):
    """Review of c3923e53 (P1, 2026-11-10): the chest claim answered only
    for a player, so a charmed ordinary mobile -- bottled with TRAP THE
    SOUL and let out in the opened treasure room -- was ORDERed to GET the
    shard with no key, killed, and its NPC corpse carried out through a
    portal for anybody to loot. A creature takes no bound object, one it
    dies holding goes with it, and nothing bound comes out of an NPC
    corpse, wherever it lies."""

    SQUARE = 2401

    def test_a_charmed_creature_cannot_carry_a_prize_out(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            make(mud, "Zkeycharm", Levl=59, Room=TREASURE, Cla=0, skills=("charm person",))
            staff, charmer = connect(mud, "Zkeystaff", "Zkeycharm")
            try:
                shards = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30400", "In the world now:")).group(1))
                # The chest opened by somebody with the key.
                staff.must(f"goto {TREASURE}", "")
                staff.must(f"load obj {KEYS[0]}", "You create")
                staff.sync("unlock chest")
                staff.must("open chest", "Ok", "You open")
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                for _ in range(12):
                    charmer.sync("cast 'charm person' guard", timeout=60)
                    staff.sync("peace")
                    if "Master: Zkeycharm" in staff.must("stat mob guard", "Vnum:"):
                        break
                ordered = charmer.sync("order guard get shard chest", timeout=60)
                ordered += charmer.sync("order guard get all chest", timeout=60)
                guard = staff.sync("stat mob guard", timeout=60)
                chest = staff.sync("look in chest", timeout=60)
                # One that holds a prize already (a hole not yet found)
                # takes it to nobody when it dies.
                staff.must("load obj 30400", "You create")
                staff.must("give shard guard", "You give")
                staff.must("slay guard", "")
                corpse = staff.sync("look in corpse", timeout=60)
                # And an NPC corpse already holding one, outside Hyrule.
                staff.must(f"goto {self.SQUARE}", "")
                # (Staff cannot PUT into a corpse: a bag holding the shard,
                # made an NPC corpse, stands in for one filled before.)
                staff.must(f"load obj {BAG}", "You create")
                staff.must("load obj 30400", "You create")
                staff.must("put shard bag", "You put")
                staff.must("drop bag", "You drop")
                staff.must("set obj bag type 23", "Type on")
                staff.must(f"transfer zkeycharm {self.SQUARE}", "")
                looted = charmer.sync("get shard bag", timeout=60)
                looted += charmer.sync("get all bag", timeout=60)
                pack = charmer.sync("inventory", timeout=60)
                shards_after = int(re.search(r"In the world now: (\d+)", staff.must(
                    "oshow 30400", "In the world now:")).group(1))
            finally:
                quit_all(charmer, staff)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Master: Zkeycharm", guard, "the guard was charmed: " + guard)
        self.assertIn("Carry number: 0", guard, ordered + guard)
        self.assertIn("first Triforce shard", chest, "the chest keeps its prize")
        self.assertNotIn("Triforce", corpse.split("contains", 1)[-1], corpse)
        self.assertIn(f"mob {SPARRING_GUARD} died holding a bound object", log)
        self.assertIn("bound to the one who fell", looted, looted)
        self.assertNotIn("Triforce", pack, looted + pack)
        # The chest's own and the one in the square's corpse remain; the
        # guard's went with it.
        self.assertEqual(shards_after, shards + 1, (shards, shards_after))


@unittest.skipIf(SKIP is not None, SKIP or "")
class GanonPhaseTests(unittest.TestCase):
    def test_ordinary_debuffs_never_finish_him_and_real_combat_does(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zkeystaff", Levl=70, Room=TEMPLE, AfBy=0)
            make(mud, "Zkeymonk", Levl=59, Room=TEMPLE, Cla=4, Gui=4,
                 skills=("nerve damage",), objects=obj(SILVER, 54))
            make(mud, "Zkeypsi", Levl=59, Room=TEMPLE, Cla=0, Psionic=1,
                 skills=("nightmare",))
            staff, monk, psi = connect(mud, "Zkeystaff", "Zkeymonk", "Zkeypsi")
            monk.name, psi.name = "Zkeymonk", "Zkeypsi"
            out = {}
            try:
                staff.sync("holylight")
                start = hp_of(mob_stat(staff, GANON_LAIR, "ganon"))
                out["start"] = start
                for client, command in ((monk, "nerve ganon"), (psi, "nightmare ganon")):
                    staff.must(f"transfer {client.name.lower()} {GANON_LAIR}", "")
                    client.sync("remove all", timeout=60)
                    for _ in range(6):
                        client.sync(command, timeout=60)
                        if "sleepless" in mob_stat(staff, GANON_LAIR, "ganon"):
                            break
                    staff.sync(f"at {GANON_LAIR} peace")
                    staff.must(f"transfer {client.name.lower()} {TEMPLE}", "")
                time.sleep(6)       # a mobile pulse and more
                debuffed = mob_stat(staff, GANON_LAIR, "ganon")
                out["debuffed"] = hp_of(debuffed)
                out["sleepless"] = "sleepless" in debuffed
                staff.must(f"transfer zkeymonk {GANON_LAIR}", "")
                monk.sync("wield arrow", timeout=60)
                out["early shot"] = monk.sync("shoot ganon", timeout=60)
                staff.sync(f"at {GANON_LAIR} peace")
                monk.sync("remove arrow", timeout=60)

                # Real combat: beaten down to one hit point, he collapses.
                staff.must(f"at {GANON_LAIR} restore ganon", "")
                staff.must(f"at {GANON_LAIR} set char ganon hp 20", "")
                staff.must(f"at {GANON_LAIR} restore ganon", "")
                beaten = kill(staff, monk, "ganon", GANON_LAIR, rounds=30)
                out["beaten"] = beaten
                out["collapsed"] = hp_of(mob_stat(staff, GANON_LAIR, "ganon"))
                # A heal does not lift him out of it.
                staff.must(f"at {GANON_LAIR} restore ganon", "")
                time.sleep(6)
                out["healed"] = hp_of(mob_stat(staff, GANON_LAIR, "ganon"))
                monk.sync("wield arrow", timeout=60)
                out["finish"] = monk.sync("shoot ganon", timeout=60)
                out["pack"] = monk.sync("inventory", timeout=60)
            finally:
                quit_all(monk, psi, staff)

        hit, top, _ = out["start"]
        self.assertGreater(top, 60000)
        self.assertEqual(hit, top, "he starts whole")
        hit, top, pos = out["debuffed"]
        self.assertTrue(out["sleepless"], "the ordinary effect was laid")
        self.assertGreater(hit, 60000, "an ordinary debuff is not his collapse")
        self.assertNotEqual(pos, 3, "not stunned")
        self.assertIn("not vulnerable yet", out["early shot"], out["early shot"])
        self.assertIn("flashes bright red", out["beaten"], out["beaten"][-600:])
        self.assertEqual(out["collapsed"][0], 1)
        self.assertEqual(out["healed"][0], 1, "a heal does not lift him out of it")
        self.assertEqual(out["healed"][2], 3, "and he stays stunned")
        self.assertIn("Ganon is DEAD", out["finish"], out["finish"])
        self.assertIn("Golden Key", out["pack"], "the finisher is handed the key")


if __name__ == "__main__":
    unittest.main()
