"""Paths nothing played until 2026-11-12, played live.

1. A bottle that shatters with age (obj_update) lets its captive out where
   its holder really stands -- one creature, once. A bottle kept in the
   stash is in the object list but nowhere in the world, and its timer
   ran: it "shattered" there, the captive went with it, and the object
   was extracted while pcdata->stash still held it, so the next save read
   freed memory. Nothing in a stash runs out now (obj_held_nowhere); it
   keeps its timer and its captive until it is taken out.
2. WIMPY across a remort: an int wimpy past the old short (80,000 of
   200,000 hit points) is saved whole, and the remort cuts it to a fifth
   of the new life's maximum (do_wimpy's own cap); one within half of the
   new maximum is kept.
3. RENAME keeps the character's serial: the file under the new name
   carries it, a restart's index finds it there and gives no other, and
   a new character under the old name gets one of its own.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GALLERY, SPARRING_GUARD, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zuntested12"
TEMPLE = 4207
ALTAR = 4208
BOTTLE = 32711          # the fixture amulet, standing in for a bottle


def bottle(timer: int) -> str:
    return ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\nTime %d\nCond 100\nTrap %d\nEnd\n\n"
            % (BOTTLE, timer, SPARRING_GUARD))


def guards(staff) -> list[int]:
    reply = staff.sync("mwhere sparring", timeout=60)
    return [int(room) for room in
            re.findall(r"\[\s*%d\]\s.*?\[\s*(\d+)\]" % SPARRING_GUARD, reply)]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    if fields:
        patch_player_file(mud, name, **fields)


def saved(mud: LiveMud, name: str) -> str:
    return (mud.player_dir / name).read_text(encoding="latin-1")


def boot_finished(mud: LiveMud) -> None:
    with mud.connect(timeout=180) as client:
        client.expect("by what name", "name:", "what is your name")


class UntestedPathSourceTests(unittest.TestCase):
    def test_a_stash_keeps_its_timers(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        body = update.split("void obj_update( void )", 1)[1].split("\n}\n", 1)[0]
        guard = body.index("if ( obj->timer > 0 && obj_held_nowhere( obj ) )")
        self.assertLess(guard, body.index("if ( obj->timer <= 0 || --obj->timer > 0 )"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class UntestedPathLiveTests(unittest.TestCase):
    def test_a_bottle_shattering_with_age_frees_one_where_its_holder_stands(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zshatstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zshatter", Levl=20, Room=SPARRING_GALLERY)
            path = mud.player_dir / "Zshatter"
            path.write_text(saved(mud, "Zshatter").replace(
                "#END", bottle(1) + "#STASH\n" + bottle(1) + "#END", 1), encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as holder:
                login(staff, "Zshatstaff", PW)
                login(holder, "Zshatter", PW)
                for client in (staff, holder):
                    client.sync("scroll 0")
                self.assertEqual(guards(staff), [], "both captives still bottled")
                # The next tick (forty to eighty seconds) runs the carried
                # bottle's last minute out.
                holder.expect("crumbles into dust", timeout=200)
                staff.drain(1.0)
                freed = guards(staff)
                kept = holder.sync("stash", timeout=60)
                holder.send("save")
                holder.sync("time")
                holder.send("quit")
                self.assertTrue(holder.wait_closed())
                staff.drain(1.0)
                after_quit = guards(staff)
                staff.send("quit")
                staff.wait_closed()
            text = saved(mud, "Zshatter")
        self.assertEqual(freed, [SPARRING_GALLERY], "exactly one, where the holder stands")
        self.assertIn("fixture amulet", kept, "the stashed bottle is still in the stash")
        self.assertEqual(after_quit, [SPARRING_GALLERY], "nothing more at the quit")
        stash = text.split("#STASH", 1)[1] if "#STASH" in text else ""
        self.assertRegex(stash, r"(?m)^Trap %d$" % SPARRING_GUARD, "the stashed captive is kept")
        self.assertRegex(stash, r"(?m)^Time 1$", "and its timer has not run")
        self.assertEqual(len(re.findall(r"(?m)^Trap ", text)), 1, "the shattered bottle is gone")

    def test_wimpy_across_a_remort(self) -> None:
        big = {"HMV": "200000 200000 1000 1000 1000 1000", "HMVP": "200000 1000 1000"}
        with LiveMud() as mud:
            make(mud, "Zwimpcut", Levl=54, Room=ALTAR, Wimp=80000, **big)
            make(mud, "Zwimpkept", Levl=54, Room=ALTAR, Wimp=90, **big)
            for name in ("Zwimpcut", "Zwimpkept"):
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.sync("scroll 0")
                    before = client.must("score", "Wimpy")
                    client.must("save", "Saving")
                    on_file = saved(mud, name)
                    said = client.sync("remort %s mage none human" % PW, timeout=60)
                    self.assertIn("You have remorted to level 3", said, said[-800:])
                    after = client.must("score", "Wimpy")
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                text = saved(mud, name)
                if name == "Zwimpcut":
                    self.assertRegex(before, r"Wimpy Points:\s*80000\b")
                    self.assertRegex(on_file, r"(?m)^Wimp +80000$", "an int, saved whole")
                    # A fifth of the new life's 200 hit points.
                    self.assertRegex(after, r"Wimpy Points:\s*40\b", after)
                    self.assertRegex(text, r"(?m)^Wimp +40$")
                else:
                    self.assertRegex(after, r"Wimpy Points:\s*90\b", after)
                    self.assertRegex(text, r"(?m)^Wimp +90$")

    def test_rename_keeps_the_serial(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zrenstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrenold", Levl=20, Room=TEMPLE)
            serial = int(re.search(r"(?m)^Serial (\d+)$", saved(mud, "Zrenold")).group(1))
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zrenstaff", PW)
                login(player, "Zrenold", PW)
                staff.sync("scroll 0")
                staff.must("rename zrenold Zrennew", "renamed")
                player.send("quit")
                self.assertTrue(player.wait_closed())
                staff.send("quit")
                staff.wait_closed()
            self.assertFalse((mud.player_dir / "Zrenold").exists())
            moved = int(re.search(r"(?m)^Serial (\d+)$", saved(mud, "Zrennew")).group(1))

            mud.restart()
            boot_finished(mud)
            with mud.connect(timeout=120) as player:
                login(player, "Zrennew", PW)
                player.sync("scroll 0")
                player.send("quit")
                self.assertTrue(player.wait_closed())
            make(mud, "Zrenold")
            kept = int(re.search(r"(?m)^Serial (\d+)$", saved(mud, "Zrennew")).group(1))
            fresh = int(re.search(r"(?m)^Serial (\d+)$", saved(mud, "Zrenold")).group(1))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertEqual(moved, serial, "the renamed file carries the serial")
        self.assertEqual(kept, serial, "a restart's index finds it under the new name")
        self.assertNotEqual(fresh, serial, "the old name, made again, is somebody else")
        self.assertNotIn("Zrennew's serial", log)


if __name__ == "__main__":
    unittest.main()
