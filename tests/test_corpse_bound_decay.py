"""A rotting corpse keeps its owner's bound Hyrule gear in the owner's
keeping, and nobody else's (review, 2026-11-10).

The audit of 2026-11-10 made a player's corpse destroy what binds to them
in Hyrule rather than spill it for anybody, unless the corpse rots in its
owner's own hands -- but it asked only the corpse's own carried_by, which
is NULL when the corpse lies in a bag, so an owner who put their own
corpse in their own bag lost the piece when it rotted. Four real deaths,
each holding the second Triforce shard, and four places to rot:

- carried by its owner: the shard goes to them;
- in its owner's bag: the shard goes into the bag;
- carried by another player: the shard is destroyed, never theirs;
- on the ground: the shard is destroyed, never on the floor.
"""

from __future__ import annotations

import re
import time
import unittest

from live_mud import (LiveMud, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
PW = "Zrotpass11"
# Indoors and lit at any hour: death strips infravision, and an outdoor
# room at night hid each owner's corpse from them.
ROOM = 4207
SHARD = 30401           # the second Triforce shard: NODROP, bound
PACK = 730             # Pellinore's trailpack: a real pack a corpse fits in


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


def carried(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


@unittest.skipIf(SKIP is not None, SKIP or "")
class BoundDecayTests(unittest.TestCase):
    def test_bound_gear_stays_in_its_owners_keeping(self) -> None:
        owners = {"direct": "Zrotdirect", "nested": "Zrotnested",
                  "other": "Zrotother", "ground": "Zrotground"}
        with LiveMud() as mud:
            make(mud, "Zrotstaff", Levl=70, Room=ROOM)
            make(mud, "Zrotcarrier", Levl=20, Room=ROOM, AfBy=512)
            for case, name in owners.items():
                make(mud, name, objects=carried(SHARD), Levl=20,
                     Room=ROOM, AfBy=512)
            clients = {}
            try:
                staff = mud.connect(timeout=120)
                login(staff, "Zrotstaff", PW)
                carrier = mud.connect(timeout=120)
                login(carrier, "Zrotcarrier", PW)
                for case, name in owners.items():
                    clients[case] = mud.connect(timeout=120)
                    login(clients[case], name, PW)
                for client in [staff, carrier, *clients.values()]:
                    client.sync("scroll 0")
                staff.must(f"goto {ROOM}", "")
                # Chests in Hyrule hold a shard too; count from here.
                before = int(re.search(r"In the world now: (\d+)", staff.must(
                    f"oshow {SHARD}", "In the world now:")).group(1))

                # Each dies -- a real death through raw_kill and
                # make_corpse -- and comes back to the corpse.
                for case, name in owners.items():
                    staff.must(f"slay {name.lower()}", "")
                    clients[case].drain(1.5)
                    staff.must(f"transfer {name.lower()} {ROOM}", "")
                    staff.must(f"restore {name.lower()}", "")

                def owner_gets(case: str) -> str:
                    said = ""
                    for _ in range(8):
                        said = clients[case].sync(f"get {owners[case].lower()}", timeout=60)
                        if "laid to rest" not in said:
                            break
                        clients[case].drain(2.0)
                    return said

                for case in ("direct", "nested", "other"):
                    got = owner_gets(case)
                    self.assertIn("You get", got, f"{case}: {got}")
                # A pack a corpse fits in -- an ordinary bag is too small --
                # handed over after the death, so it is not in the corpse.
                staff.must(f"load obj {PACK}", "You create")
                staff.must("set obj trailpack v1 0", "")      # not closed or locked
                staff.must("give trailpack zrotnested", "You give")
                clients["nested"].must(f"put {owners['nested'].lower()} trailpack", "You put")
                clients["other"].must(f"give {owners['other'].lower()} zrotcarrier",
                                      "You give")
                # The ground's corpse stays where it fell.

                for name in owners.values():
                    staff.must(f"set obj {name.lower()} timer 1", "Timer on")
                # A tick is a minute: wait until every corpse has rotted.
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    left = staff.sync("owhere corpse", timeout=60)
                    if not any(name in left for name in owners.values()):
                        break
                    time.sleep(5)
                self.assertFalse([n for n in owners.values() if n in left], left)

                direct = clients["direct"].sync("inventory", timeout=60)
                nested = clients["nested"].sync("look in trailpack", timeout=60)
                other = carrier.sync("inventory", timeout=60)
                ground = staff.sync("look", timeout=60)
                world = staff.must(f"oshow {SHARD}", "In the world now:")
            finally:
                for client in [*clients.values()]:
                    client.send("quit")
                    client.wait_closed()
                for client in (locals().get("carrier"), locals().get("staff")):
                    if client is not None:
                        client.send("quit")
                        client.wait_closed()

        shard = re.compile(r"Triforce shard", re.I)
        self.assertRegex(direct, shard, "carried by its owner: the shard is theirs")
        self.assertRegex(nested, shard, "in its owner's pack: the shard stays in the pack")
        self.assertNotRegex(other, shard, "another player never gets it")
        self.assertNotRegex(ground, shard, "it never lies on the floor")
        # The owners' two are left; the other two went with their corpses.
        after = int(re.search(r"In the world now: (\d+)", world).group(1))
        self.assertEqual(after, before - 2, world)


if __name__ == "__main__":
    unittest.main()
