"""One of each Triforce shard: a refilled chest gives no second copy.

Hyrule's chests relock and refill at every area reset, so a character
who replays a dungeon finds its shard there again. Nothing refused it:
Trentlin replayed Level 1 on 2026-10-21 and left with two first shards
(play journal: "You get the first Triforce shard from the Eagle's
treasure chest." a day after his first). The shards are NODROP, so the
spare could go nowhere -- not dropped, given, put, sold or stashed -- but
it is clutter, and the take is now refused. A login fix,
20261029-spare-shards, takes back a spare already carried.

That fix first took back at most 64 and was marked done whatever it
left, so the characters it had already visited kept the rest for good
when the cap came off: a fixture marked with it and holding sixteen first
shards kept all sixteen (review, 2026-10-30). The corrected sweep runs
again under its own id, 20261030-spare-shards-again, which every
character is owed whatever the first one did.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zshardpw1"
TEMPLE = 4207
FIRST, SECOND, THIRD = 30400, 30401, 30402
OLD_FIX, NEW_FIX = "20261029-spare-shards", "20261030-spare-shards-again"


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def shard(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


def make(mud: LiveMud, name: str, objects: str = "", unfix: bool = False,
         keep_old: bool = False, **fields) -> Path:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if unfix:
        # A fixture is a new character, born with every fix marked; an
        # old file has no Fixes line and is owed them all.
        text = re.sub(r"(?m)^Fixes .*\n", "", text)
    if keep_old:
        # Visited by the first sweep, as it was: its id marked and the
        # corrected sweep's not (a character from before the second).
        text = re.sub(r"(?m)^Fixes .*~\n",
                      "Fixes 20261021-mage-groups 20261021-mage-weapons %s~\n" % OLD_FIX, text)
        assert ("Fixes 20261021-mage-groups 20261021-mage-weapons %s~" % OLD_FIX) in text
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")
    return path


class SpareShardSourceTests(unittest.TestCase):
    def test_get_obj_refuses_a_shard_already_held(self) -> None:
        act_obj = source("act_obj.c")
        get = act_obj[act_obj.index("void get_obj("):]
        get = get[:get.index("\n}\n")]
        self.assertIn("hyrule_carries( ch, obj->pIndexData->vnum )", get)
        self.assertIn("HYRULE_PIECE_FIRST_VNUM", get)
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", get, "staff may test freely")

    def test_the_fix_is_listed_once_for_mortals(self) -> None:
        fixes = source("fixes.c")
        self.assertEqual(fixes.count('"20261029-spare-shards"'), 1)
        self.assertIn("fix_spare_triforce_shards, false }", fixes)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SpareShardLiveTests(unittest.TestCase):
    def test_a_held_shard_is_not_taken_twice(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zshardkeep", Levl=70)
            make(mud, "Zshardhold", shard(FIRST), Levl=20)
            make(mud, "Zshardnew", Levl=20)
            with mud.connect(timeout=120) as staff, \
                 mud.connect(timeout=120) as holder, \
                 mud.connect(timeout=120) as fresh:
                login(staff, "Zshardkeep", PW)
                login(holder, "Zshardhold", PW)
                login(fresh, "Zshardnew", PW)
                for client in (staff, holder, fresh):
                    client.sync("scroll 0")
                staff.must("load obj %d" % FIRST, "You create")
                staff.must("drop shard", "You drop")

                refused = holder.sync("get shard")
                self.assertIn("You already hold the first Triforce shard", refused)
                self.assertEqual(holder.sync("inventory").count("the first Triforce shard"), 1)

                # Somebody who needs it still takes it.
                self.assertIn("You get the first Triforce shard", fresh.sync("get shard"))

    def test_a_spare_already_carried_is_taken_back_once(self) -> None:
        with LiveMud() as mud:
            path = make(mud, "Zshardtwo", shard(FIRST) + shard(FIRST) + shard(SECOND),
                        unfix=True, Levl=20)
            with mud.connect(timeout=120) as client:
                login(client, "Zshardtwo", PW)
                client.drain(2.0)
                self.assertIn("Triforce shard you already had", client.transcript)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            saved = path.read_text(encoding="latin-1")
            self.assertEqual(saved.count("Vnum %d\n" % FIRST), 1, "one of each kept")
            self.assertEqual(saved.count("Vnum %d\n" % SECOND), 1)
            self.assertIn("20261029-spare-shards", saved, "applied once, and recorded")

            with mud.connect(timeout=120) as client:
                login(client, "Zshardtwo", PW)
                client.drain(2.0)
                self.assertNotIn("Triforce shard you already had", client.transcript)
                client.send("quit")
                client.wait_closed()

    def test_every_spare_goes_however_many(self) -> None:
        """The fix took back at most 64 and was marked done, so a pack of
        80 kept 16 for good (review, 2026-10-30)."""
        with LiveMud() as mud:
            path = make(mud, "Zshardmany", shard(FIRST) * 80 + shard(SECOND) * 3,
                        unfix=True, Levl=54)
            with mud.connect(timeout=120) as client:
                login(client, "Zshardmany", PW)
                client.drain(2.0)
                self.assertIn("Triforce shards you already had", client.transcript)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            saved = path.read_text(encoding="latin-1")
            self.assertEqual(saved.count("Vnum %d\n" % FIRST), 1)
            self.assertEqual(saved.count("Vnum %d\n" % SECOND), 1)
            self.assertIn("20261029-spare-shards", saved)
            log = mud.server_output()
            self.assertIn("Spare Triforce shard: 79 of Zshardmany's object %d" % FIRST, log)
            self.assertIn("Spare Triforce shard: 2 of Zshardmany's object %d" % SECOND, log)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SpareShardAgainTests(unittest.TestCase):
    """The corrected sweep reaches characters the first one marked."""

    @staticmethod
    def pack() -> str:
        return shard(FIRST) * 16 + shard(SECOND) * 2 + shard(THIRD)

    @staticmethod
    def counts(path: Path) -> tuple:
        saved = path.read_text(encoding="latin-1")
        return tuple(saved.count("Vnum %d\n" % v) for v in (FIRST, SECOND, THIRD))

    @staticmethod
    def fixes(path: Path) -> str:
        found = re.search(r"(?m)^Fixes (.*)~$", path.read_text(encoding="latin-1"))
        return found.group(1) if found else ""

    def login_and_quit(self, mud: LiveMud, name: str) -> str:
        with mud.connect(timeout=120) as client:
            login(client, name, PW)
            client.sync("scroll 0")
            seen = client.transcript
            client.send("quit")
            self.assertTrue(client.wait_closed())
        return seen

    def test_marked_unmarked_staff_and_a_second_login(self) -> None:
        with LiveMud() as mud:
            marked = make(mud, "Zshardold", self.pack(), keep_old=True, Levl=30)
            unmarked = make(mud, "Zshardnone", self.pack(), unfix=True, Levl=30)
            staff = make(mud, "Zshardgod", self.pack(), keep_old=True, Levl=70)
            self.assertIn(OLD_FIX, self.fixes(marked))
            self.assertNotIn(NEW_FIX, self.fixes(marked))

            said = {name: self.login_and_quit(mud, name)
                    for name in ("Zshardold", "Zshardnone", "Zshardgod")}
            log = mud.server_output()

            # Already marked by the first sweep: the spares go now.
            self.assertEqual(self.counts(marked), (1, 1, 1), "one of each, the spares gone")
            self.assertIn("Triforce shards you already had", said["Zshardold"])
            self.assertIn(NEW_FIX, self.fixes(marked))
            self.assertIn("Spare Triforce shard: 15 of Zshardold's object %d" % FIRST, log)
            self.assertIn("Login fix %s" % NEW_FIX, log)
            # Never marked: both sweeps are owed; one of each either way.
            self.assertEqual(self.counts(unmarked), (1, 1, 1))
            self.assertIn(OLD_FIX, self.fixes(unmarked))
            self.assertIn(NEW_FIX, self.fixes(unmarked))
            # Staff are left alone, and left unmarked for the day they are not.
            self.assertEqual(self.counts(staff), (16, 2, 1))
            self.assertNotIn(NEW_FIX, self.fixes(staff))

            # A second login finds nothing to take and says nothing.
            again = self.login_and_quit(mud, "Zshardold")
            self.assertNotIn("already had", again)
            self.assertEqual(self.counts(marked), (1, 1, 1))
            self.assertEqual(self.fixes(marked).split().count(NEW_FIX), 1)


if __name__ == "__main__":
    unittest.main()
