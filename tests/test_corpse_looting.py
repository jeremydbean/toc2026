"""A player's corpse is its owner's while they are away (owner, 2026-11-12).

A review found a quit player's corpse open to everybody: can_loot asked
for the owner among the characters in the game and, finding nobody,
allowed anything -- so every player's corpse in the world was anybody's
the moment its owner logged out, and all of them after a restart, for
the week a corpse now lasts. A charmed follower ORDERed to GET, and the
janitors, took from them too. The rule now (loot_refusal in act_obj.c):

  - the owner and staff always;
  - never a mobile;
  - while the owner is in the game, what they allow: NOLOOT's leave, a
    player killer's corpse, their group;
  - while the owner is not in the game -- quit or link-dead -- nobody
    else, whatever NOLOOT said.

A death still takes back NOLOOT's leave (stock ROM's rule, kept): the
protection is what returns. These tests walk every way of taking from a
corpse -- GET, GET ALL, GET ALL in the room, GET <corpse>, SACRIFICE,
TELEKINESIS, a charmed follower ORDERed -- with the owner present,
link-dead and gone, and the owner's and staff's own recovery. Synthetic
Z characters in a fixture world only.
"""
from __future__ import annotations

import unittest

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, skip_reason)

SKIP = skip_reason()
PW = "Zlootpass1"
AMULET = 32711          # a fixture amulet of wisdom
DAGGER = 3701
BAG = 3032
OWNER, THIEF, MAGE, STAFF = "Zlootowner", "Zlootthief", "Zlootmage", "Zlootstaff"
ABSENT = "out of the game"
NO_LEAVE = "given leave to loot it"


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


def settled(client, line: str) -> str:
    """The line's answer once the death is on the disk."""
    said = ""
    for _ in range(8):
        said = client.sync(line, timeout=60)
        if "laid to rest" not in said:
            break
        client.drain(2.0)
    return said


def quit_all(*clients) -> None:
    for client in clients:
        try:
            client.send("quit")
            client.wait_closed()
        except OSError:
            pass


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseLootingTests(unittest.TestCase):
    def test_an_absent_owners_corpse_is_theirs_alone(self) -> None:
        seen: dict[str, str] = {}
        with LiveMud(fixtures=True) as mud:
            make(mud, STAFF, Levl=70, Room=SPARRING_FLOOR)
            make(mud, OWNER, Levl=20, Room=SPARRING_FLOOR,
                 objects=obj(AMULET) + obj(DAGGER) + obj(BAG) + obj(AMULET, 1))
            make(mud, THIEF, Levl=25, Room=SPARRING_FLOOR, skills=("telekinesis",),
                 HMV="500 500 2000 2000 500 500", HMVP="500 2000 500")
            make(mud, MAGE, Levl=59, Room=SPARRING_FLOOR, Cla=0,
                 skills=("charm person",),
                 HMV="5000 5000 20000 20000 1000 1000", HMVP="5000 20000 1000")
            staff = mud.connect(timeout=120)
            thief = mud.connect(timeout=120)
            mage = mud.connect(timeout=120)
            owner = mud.connect(timeout=120)
            try:
                for client, name in ((staff, STAFF), (thief, THIEF), (mage, MAGE),
                                     (owner, OWNER)):
                    login(client, name, PW)
                    client.sync("scroll 0")

                # Leave to loot given before the death is taken back by it.
                seen["leave"] = owner.must("noloot", "may now be looted")
                staff.must(f"at {SPARRING_FLOOR} slay zlootowner", "")
                owner.drain(2.0)
                seen["auto after death"] = owner.sync("auto")

                # In the game, protected: a stranger is refused, and why.
                seen["present get all"] = settled(thief, "get all zlootowner")
                seen["present get corpse"] = thief.sync("get zlootowner")

                # In the game, leave given after the death: a stranger may.
                owner.must("noloot", "may now be looted")
                seen["leave get dagger"] = settled(thief, "get dagger zlootowner")

                # Link-dead: away, whatever NOLOOT said.
                owner.close()
                thief.drain(3.0)
                seen["linkdead get all"] = thief.sync("get all zlootowner")

                # Back, then gone for good.
                owner = mud.connect(timeout=120)
                login(owner, OWNER, PW)
                owner.send("quit")
                self.assertTrue(owner.wait_closed())

                seen["gone get all"] = thief.sync("get all zlootowner")
                seen["gone get amulet"] = thief.sync("get amulet zlootowner")
                seen["gone get corpse"] = thief.sync("get zlootowner")
                seen["gone room get all"] = thief.sync("get all")
                seen["gone sacrifice"] = thief.sync("sacrifice zlootowner")
                seen["gone tk"] = thief.sync("tk zlootowner", timeout=60)
                seen["thief pack"] = thief.sync("inventory")

                # A charmed follower ORDERed, in every way.
                staff.must(f"at {SPARRING_FLOOR} load mob {SPARRING_GUARD}", "")
                for _ in range(12):
                    mage.sync("cast 'charm person' guard", timeout=60)
                    staff.sync(f"at {SPARRING_FLOOR} peace")
                    if f"Master: {MAGE}" in staff.must(
                            f"at {SPARRING_FLOOR} stat mob guard", "Vnum:"):
                        break
                seen["charmed"] = staff.must(f"at {SPARRING_FLOOR} stat mob guard", "Vnum:")
                for order in ("get all zlootowner", "get amulet zlootowner",
                              "get bag zlootowner", "get zlootowner",
                              "sacrifice zlootowner"):
                    mage.sync(f"order guard {order}", timeout=60)
                seen["after orders"] = staff.sync(f"at {SPARRING_FLOOR} look in zlootowner")
                seen["room after orders"] = staff.sync(f"at {SPARRING_FLOOR} look")

                # Staff may (and hand it back below).
                seen["staff get"] = staff.sync(f"at {SPARRING_FLOOR} get amulet zlootowner")

                # The owner comes back for it all.
                owner = mud.connect(timeout=120)
                login(owner, OWNER, PW)
                owner.sync("scroll 0")
                staff.must(f"transfer zlootowner {SPARRING_FLOOR}", "")
                seen["owner get all"] = owner.sync("get all zlootowner")
                staff.sync("give amulet zlootowner")
                seen["owner pack"] = owner.sync("inventory") + owner.sync("look in bag")
            finally:
                quit_all(owner, mage, thief, staff)

        # Away -- link-dead or quit -- nobody else, by any way of taking.
        self.assertIn(ABSENT, seen["linkdead get all"], seen["linkdead get all"])
        for key in ("gone get all", "gone get amulet", "gone get corpse",
                    "gone room get all", "gone sacrifice", "gone tk"):
            self.assertIn(ABSENT, seen[key], f"{key}: {seen[key]}")
            # A death may drop a body part (death_cry: a heart, an arm) on
            # the floor beside the corpse; GET ALL in the room takes that,
            # which is not the corpse's.
            self.assertNotRegex(seen[key], r"(?i)You get [^\n]*(amulet|bag|dagger|corpse)",
                                f"{key}: {seen[key]}")
        self.assertNotRegex(seen["thief pack"], r"(?i)amulet|bag|corpse", seen["thief pack"])

        self.assertIn(f"Master: {MAGE}", seen["charmed"], seen["charmed"])
        self.assertRegex(seen["after orders"], r"(?i)amulet", seen["after orders"])
        self.assertRegex(seen["after orders"], r"(?i)bag", seen["after orders"])
        self.assertRegex(seen["room after orders"], r"(?i)corpse of zlootowner",
                         seen["room after orders"])

        # In the game: a death takes NOLOOT's leave back, and leave given
        # after it works.
        self.assertIn("safe from thieves", seen["auto after death"], seen["auto after death"])
        for key in ("present get all", "present get corpse"):
            self.assertIn(NO_LEAVE, seen[key], f"{key}: {seen[key]}")
        self.assertIn("You get", seen["leave get dagger"], seen["leave get dagger"])

        self.assertIn("You get", seen["staff get"], seen["staff get"])
        self.assertIn("You get", seen["owner get all"], seen["owner get all"])
        pack = seen["owner pack"]
        self.assertGreaterEqual(len([1 for line in pack.splitlines()
                                     if "amulet of wisdom" in line.lower()]), 2,
                                seen["owner get all"] + pack)
        self.assertRegex(pack, r"(?i)bag", pack)


if __name__ == "__main__":
    unittest.main()
