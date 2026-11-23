"""A guardian's boss and chest achievements are earned wherever in its
dungeon it falls, and a held Triforce piece proves both (players' logs,
2026-11-23).

The ashen Gleeok, driven from its chamber by DESPAIR before guardians
stopped fleeing (2026-11-10), died one room south of it: its killer got
the key, opened the chest and holds the eighth piece, and has neither the
boss achievement -- whose row named the chamber's room -- nor the
chest's, which asks for the boss's. A second hole, closed 2026-11-13,
gave a chest's row only to whoever OPENed it closed, so a keyholder after
the first went without. achievement_boss_room_matches now takes a Hyrule
guardian's death anywhere in its own dungeon, and the login fix
20261123-hyrule-piece-credit gives both rows for every piece a mortal
holds.

Synthetic Z characters only.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zcreditpass1"
TEMPLE = 4207
LAIR = 30413            # Level 1: Aquamentus's chamber
OUTSIDE = 30412         # Level 1, not the chamber
BAG = 3032
EIGHTH = 30407          # the eighth Triforce shard


def make(mud: LiveMud, name: str, objects: str = "", **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    fields.setdefault("HMV", "30000 30000 30000 30000 1000 1000")
    fields.setdefault("HMVP", "30000 30000 1000")
    patch_player_file(mud, name, **fields)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def obj(vnum: int, nest: int = 0, level: int = 1) -> str:
    return "#O\nVnum %d\nNest %d\nWear -1\nLev %d\nCond 100\nEnd\n\n" % (vnum, nest, level)


def achievements(mud: LiveMud, name: str) -> set[str]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return set(re.findall(r"^Achv (\S+)", text, re.M))


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianOutsideItsChamberTests(unittest.TestCase):
    def test_a_guardian_slain_elsewhere_in_its_dungeon_counts(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcreditstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zcreditkill", Levl=40, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as killer:
                login(staff, "Zcreditstaff", PW)
                login(killer, "Zcreditkill", PW)
                staff.sync("scroll 0")
                killer.sync("scroll 0")
                staff.must(f"at {LAIR} transfer aquamentus {OUTSIDE}", "")
                staff.must(f"transfer zcreditkill {OUTSIDE}", "")
                self.assertIn("Aquamentus", killer.sync("look"), "it stands outside its chamber")
                staff.must(f"at {OUTSIDE} set char aquamentus hp 10", "")
                staff.must(f"at {OUTSIDE} restore aquamentus", "")
                staff.must("set char zcreditkill hitroll 300", "")
                staff.must("set char zcreditkill damroll 300", "")
                said = killer.sync("kill aquamentus", timeout=60)
                for _ in range(30):
                    if "is DEAD" in said:
                        break
                    said += killer.drain(2.0)
                killer.drain(1.0)
                for client in (killer, staff):
                    client.send("quit")
                    client.wait_closed()
            earned = achievements(mud, "Zcreditkill")
        self.assertIn("is DEAD", said, said[-800:])
        self.assertIn("hyrule-eagle", earned, "slain in its dungeon, outside the chamber")


@unittest.skipIf(SKIP is not None, SKIP or "")
class PieceCreditFixTests(unittest.TestCase):
    def test_a_held_piece_gives_its_boss_and_chest_once(self) -> None:
        with LiveMud() as mud:
            # The eighth piece in a bag: the guardian and chest it proves.
            make(mud, "Zcreditheld", objects=obj(BAG) + obj(EIGHTH, nest=1, level=46),
                 Levl=50, Room=TEMPLE)
            make(mud, "Zcreditnone", Levl=50, Room=TEMPLE)
            for name in ("Zcreditheld", "Zcreditnone"):
                path = mud.player_dir / name
                text = path.read_text(encoding="latin-1")
                # A fixture is born with every fix marked: forget them.
                path.write_text(re.sub(r"^Fixes [^\n]*~\n", "", text, flags=re.M),
                                encoding="latin-1")
            replies = {}
            for name in ("Zcreditheld", "Zcreditnone"):
                for attempt in (1, 2):
                    with mud.connect(timeout=120) as client:
                        login(client, name, PW)
                        replies[(name, attempt)] = client.buffer + client.drain(2.0)
                        client.send("quit")
                        client.wait_closed()
            held = achievements(mud, "Zcreditheld")
            none = achievements(mud, "Zcreditnone")
        self.assertIn("hyrule-lion", held)
        self.assertIn("hyrule-chest-8", held)
        self.assertNotIn("hyrule-eagle", held, "only what the piece proves")
        self.assertIn("A correction", replies[("Zcreditheld", 1)])
        self.assertNotIn("Triforce pieces you hold", replies[("Zcreditheld", 2)], "once")
        self.assertFalse({k for k in none if k.startswith("hyrule-")}, none)
        self.assertNotIn("Triforce pieces you hold", replies[("Zcreditnone", 1)])


if __name__ == "__main__":
    unittest.main()
