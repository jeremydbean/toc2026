"""Immunities a character holds come back with them, and go only when
nothing still gives them (review, 2026-11-22).

A player's imm_flags is never saved: a login is the race's immunities and
nothing else. Saved affects are linked straight onto the character by
fread_char, not through affect_modify, so an iron skin that had drawn
slashing came back from a reconnect still listed by AFFECTS and immune to
nothing. The Hero Quest's magic immunity (special.c) was a bare SET_BIT
the file never held, so it went at the first reconnect; and an affect
granting magic immunity that wore off during the quest took the quest's
with it, since immunity_lift did not count the quest as a source.

`immunity_sources` in handler.c is the one list of what grants a
character an immunity -- the race or prototype, every immunity affect,
worn gear, the Hero Quest -- read at load (`immunity_rebuild`) and when a
source goes (`immunity_lift`). The Hero Quest's commands are commented out
of the command table and no reset places its master, so the quest itself
is reached here through a synthetic file.

Synthetic Z characters only.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zimmpass1"
TEMPLE = 4207
APPLY_IMMUNITY = 25
IMM_MAGIC = 0x04
IMM_SLASH = 0x40


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def immune_line(stat: str) -> str:
    m = re.search(r"Immune: ([^\n\r]*)", stat)
    return m.group(1).strip() if m else ""


def affd(skill: str, level: int, duration: int, modifier: int) -> str:
    return f"'{skill}' {level} {duration} {modifier} {APPLY_IMMUNITY} 0 0"


def hero_quest(level: int = 50) -> dict:
    return {"Levl": level, "On_Quest": 1,
            "Quest_Items:": "3001 3002 3003 3004 3005 3006 3007 3008 3009 3010"}


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmunityReloadTests(unittest.TestCase):
    def test_an_immunity_affect_and_the_hero_quest_come_back_at_login(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zimmstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zimmskin", Levl=30, Room=TEMPLE,
                 AffD=affd("iron skin", 30, 50, IMM_SLASH))
            make(mud, "Zimmhero", Room=TEMPLE, **hero_quest())
            with mud.connect(timeout=120) as skin, mud.connect(timeout=120) as hero, \
                 mud.connect(timeout=120) as staff:
                login(skin, "Zimmskin", PW)
                login(hero, "Zimmhero", PW)
                login(staff, "Zimmstaff", PW)
                skin_stat = staff.must("stat zimmskin", "Name:")
                hero_stat = staff.must("stat zimmhero", "Name:")
                # And again after a real quit and login, as the file wrote it.
                for client, name in ((skin, "Zimmskin"), (hero, "Zimmhero")):
                    client.send("quit")
                    self.assertTrue(client.wait_closed(), name)
            with mud.connect(timeout=120) as skin, mud.connect(timeout=120) as hero, \
                 mud.connect(timeout=120) as staff:
                login(skin, "Zimmskin", PW)
                login(hero, "Zimmhero", PW)
                login(staff, "Zimmstaff", PW)
                skin_again = staff.must("stat zimmskin", "Name:")
                hero_again = staff.must("stat zimmhero", "Name:")
                for client in (skin, hero, staff):
                    client.send("quit")
                    client.wait_closed()
        self.assertIn("slashing", immune_line(skin_stat), "iron skin's slashing at login")
        self.assertIn("slashing", immune_line(skin_again), "and after saving again")
        self.assertIn("magic", immune_line(hero_stat), "the Hero Quest's magic at login")
        self.assertIn("magic", immune_line(hero_again), "and after saving again")

    def test_a_magic_immunity_wearing_off_leaves_the_quests(self) -> None:
        # A baura (APPLY_IMMUNITY magic) at duration 0 ends at the next
        # tick; the Hero Quest still grants magic, so magic stays.
        with LiveMud() as mud:
            make(mud, "Zimmstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zimmhero", Room=TEMPLE, AffD=affd("baura", 50, 0, IMM_MAGIC),
                 **hero_quest())
            make(mud, "Zimmplain", Levl=50, Room=TEMPLE,
                 AffD=affd("baura", 50, 0, IMM_MAGIC))
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as plain, \
                 mud.connect(timeout=120) as staff:
                login(hero, "Zimmhero", PW)
                login(plain, "Zimmplain", PW)
                login(staff, "Zimmstaff", PW)
                before = staff.must("stat zimmplain", "Name:")
                deadline = time.time() + 200
                while time.time() < deadline:
                    hero_stat = staff.must("stat zimmhero", "Name:")
                    plain_stat = staff.must("stat zimmplain", "Name:")
                    if "'baura'" not in hero_stat and "'baura'" not in plain_stat:
                        break
                    staff.drain(5)
                else:
                    self.fail("the baura never wore off")
                for client in (hero, plain, staff):
                    client.send("quit")
                    client.wait_closed()
        self.assertIn("magic", immune_line(before), "the baura's magic at login")
        self.assertIn("magic", immune_line(hero_stat), "the quest still gives magic")
        self.assertNotIn("magic", immune_line(plain_stat), "nothing else gave it here")


class HeroQuestSourceTests(unittest.TestCase):
    """The quest's own ending paths (ENDQUEST, the last RETRIEVED) are out
    of the command table, so they are held here by their source: neither
    may take the immunity off by hand."""

    def test_the_quest_ends_through_immunity_lift(self) -> None:
        source = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        self.assertIsNone(re.search(r"REMOVE_BIT\(\s*ch->imm_flags,\s*IMM_MAGIC\s*\)", source),
                          "special.c takes IMM_MAGIC off by hand")
        self.assertGreaterEqual(source.count("immunity_lift( ch, IMM_MAGIC, NULL )"), 2)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        sources = handler[handler.index("long immunity_sources("):]
        self.assertIn("on_quest", sources[:2500], "the quest is a source")


if __name__ == "__main__":
    unittest.main()
