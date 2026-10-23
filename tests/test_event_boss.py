"""The holiday bosses stand still, start nothing, and say what they drop.

The Headless Horseman (29910) and Father Winter (29911) were ACT_AGGRESSIVE
and wandered Dresden like any mobile, so a boss announced in the square
had "fled" by the time anyone arrived -- the undead race's departure line
-- and attacked whoever it met (owner, 2026-10-20: not aggressive, and
looking at them shows what they drop). Their drop tables live in
season.c now, read by make_corpse to roll the loot and by LOOK to tell
the player, so the two cannot disagree.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zboss1pass"
TEMPLE = 4207
HORSEMAN = 29910
FATHER = 29911


def mob_act_flags(vnum: int) -> str:
    text = (ROOT / "area" / "seasonal.are").read_text(encoding="latin-1")
    body = text[text.index("#%d\n" % vnum):]
    body = body[:body.index("\n#", 1)]
    # keywords, short, long, description, race, then "act affected align S"
    after_race = body.split("~\n")[5]
    return after_race.split()[0]


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class EventBossSourceTests(unittest.TestCase):
    def test_neither_boss_is_aggressive_and_both_stand_still(self) -> None:
        for vnum in (HORSEMAN, FATHER):
            flags = mob_act_flags(vnum)
            with self.subTest(vnum=vnum, flags=flags):
                self.assertNotIn("F", flags, "ACT_AGGRESSIVE")
                self.assertIn("B", flags, "ACT_SENTINEL")

    def test_the_corpse_and_look_read_one_table(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("event_boss_drops( ch->pIndexData->vnum )", fight)
        for literal in ("OBJ_VNUM_HORSEMAN_REAPER", "OBJ_VNUM_WINTER_HAMMER",
                        "number_percent() <= 50", "number_percent() <= 75"):
            self.assertNotIn(literal, fight, "the drop table belongs to season.c")
        look = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        body = look[look.index("void show_char_to_char_1("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("event_boss_show_drops( victim, ch )", body)
        season = (ROOT / "src" / "season.c").read_text(encoding="latin-1")
        for vnum_name in ("OBJ_VNUM_HORSEMAN_REAPER", "OBJ_VNUM_HORSEMAN_HELM",
                          "OBJ_VNUM_PUMPKIN_CHARM", "OBJ_VNUM_HORSEMAN_CAKE",
                          "OBJ_VNUM_WINTER_HAMMER", "OBJ_VNUM_WINTER_MANTLE",
                          "OBJ_VNUM_SNOWFLAKE_PEND", "OBJ_VNUM_WINTER_CAKE"):
            self.assertIn(vnum_name, season)
        self.assertEqual(2, len(re.findall(r"EVENT_DROP_FALLBACK\s*\}", season)),
                         "one fallback per boss")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SeasonalVendorSourceTests(unittest.TestCase):
    def test_the_vendor_stocks_one_endless_copy_of_each(self) -> None:
        # Madame Hexley carried ten plain copies of each item and LIST
        # printed all twenty (2026-10-23); one ITEM_INVENTORY copy is a
        # shop's endless stock and lists once.
        text = (ROOT / "src" / "season.c").read_text(encoding="latin-1")
        body = text[text.index("static void give_vendor_items"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("SET_BIT( obj->extra_flags, ITEM_INVENTORY )", body)
        self.assertNotIn("i < 10", body)


class EventBossLiveTests(unittest.TestCase):
    def test_the_horseman_leaves_a_mortal_alone_and_look_lists_his_drops(self) -> None:
        with LiveMud() as mud:
            for name in ("Zmortal", "Zsummoner"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Room=TEMPLE)
            patch_player_file(mud, "Zmortal", Levl=20)
            patch_player_file(mud, "Zsummoner", Levl=70)

            with mud.connect(timeout=120) as mortal, mud.connect(timeout=120) as imm:
                login(mortal, "Zmortal", PASSWORD)
                login(imm, "Zsummoner", PASSWORD)
                run(imm, "scroll 0", 1.0)
                run(mortal, "scroll 0", 1.0)
                run(imm, "load mob %d" % HORSEMAN, 1.6)
                run(imm, "load mob %d" % FATHER, 1.6)

                # Aggression runs every pulse; four seconds with a level 20
                # in the room and neither boss has swung.
                mark = len(mortal.transcript)
                mortal.drain(4.0)
                quiet = mortal.transcript[mark:]
                for word in ("hits you", "misses you", "You are fighting", "slash", "pound"):
                    self.assertNotIn(word, quiet, quiet)

                look = run(mortal, "look horseman", 2.0)
                self.assertIn("Slain, the Headless Horseman leaves on the corpse:", look)
                self.assertIn("the Headless Horseman's Reaper", look)
                self.assertIn("half the time", look)
                self.assertIn("a pumpkin-lantern charm", look)
                self.assertIn("always when nothing else fell", look)
                self.assertIn("one time in twenty", look)

                look = run(mortal, "look father", 2.0)
                self.assertIn("Slain, Father Winter leaves on the corpse:", look)
                self.assertIn("Frostbite", look)
                self.assertIn("a snowflake pendant", look)

                # An ordinary mobile gets no such paragraph.
                self.assertNotIn("leaves on the corpse", run(mortal, "look watcher", 2.0))


if __name__ == "__main__":
    unittest.main()
