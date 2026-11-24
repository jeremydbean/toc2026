"""The giant turkey of Pilgrim's Bounty (src/disaster.c, owner 2026-11-24).

"change the dragon disaster to a giant turkey for thanksgiving and make it
more common he comes and picks you up, i'd like the players we have to see
it", "only picking up level 40+ and make the gear scale also", "have the
turkey do some funny things during fight", and "1% isn't good enough for
the holiday. make it likely to happen without doing it multiple times per
player ruining their play".

So in Pilgrim's Bounty the dragon is a giant turkey that visits every
mortal of level 40 or more once, a while into their play, and never twice
that holiday; it is scaled to them, clowns about in the fight, and drops a
piece of its own gear made for their level. Synthetic characters only.
"""
from __future__ import annotations

import pathlib
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zturkey1"
SQUARE = 2401            # Center of Oak Tree Square: outdoors, not safe
TEMPLE = 4207
QUIET_ROOM = 32700       # the fixture world's sparring floor: joined to nothing
SOURCE = (ROOT / "src" / "disaster.c").read_text(encoding="latin-1")
GEAR = {"Drumstick of Destiny": "drumstick", "gravy-boat helm": "gravy",
        "cloak of turkey feathers": "cloak", "Wishbone of Second Helpings": "wishbone",
        "Golden Wattle": "wattle"}


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def wait_for(client, text: str, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        client.drain(1.0)
        if text in client.transcript:
            return True
    return False


class TurkeySourceTests(unittest.TestCase):
    def body(self, signature: str) -> str:
        text = SOURCE[SOURCE.index(signature):]
        return text[:text.index("\n}\n")]

    def test_once_a_holiday_level_40_and_not_from_the_disaster_roll(self) -> None:
        update = self.body("static void turkey_update(")
        self.assertIn("fch->pcdata->turkey_year == year", update)
        self.assertIn("current_time - fch->pcdata->session_logon < grace", update)
        self.assertIn("#define TURKEY_MIN_LEVEL     40", SOURCE)
        self.assertIn("vch->level >= TURKEY_MIN_LEVEL", self.body("static bool turkey_can_snatch("))
        self.assertIn("!IS_SET(vch->act, PLR_AFK)", self.body("static bool turkey_can_snatch("))
        self.assertIn("!( type == DISASTER_DRAGON && turkey_season( ) )",
                      self.body("void disaster_update( void )"))
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn('fprintf( fp, "Turkey %d\\n", ch->pcdata->turkey_year );', save)
        self.assertIn('KEY( "Turkey",\tch->pcdata->turkey_year, fread_number( fp ) );', save)

    def test_the_pop_up_timer_and_no_dragon_achievements(self) -> None:
        self.assertIn("pop-up timer", self.body("static bool spec_giant_turkey("))
        slain = self.body("void disaster_dragon_slain(")
        self.assertIn("!dragon_is_turkey", slain)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TurkeyLiveTests(unittest.TestCase):
    ENV = {"TOC_SEASON": "pilgrim", "TOC_TURKEY": "on", "TOC_TURKEY_ODDS": "1",
           "TOC_TURKEY_GRACE": "0", "TOC_TURKEY_GAP": "0", "TOC_TURKEY_GAGS": "100",
           "TOC_DRAGON_WAIT": "90"}

    def test_it_visits_once_scales_clowns_and_drops_gear_for_the_level(self) -> None:
        with LiveMud(extra_env=self.ENV, fixtures=True) as mud:
            make(mud, "Zcarver", Levl=70, Room=TEMPLE)
            make(mud, "Zgobble", Levl=45, Room=SQUARE, AfBy=512,
                 HMV="3000 3000 1000 1000 1000 1000", HMVP="3000 1000 1000")
            make(mud, "Zpoult", Levl=39, Room=SQUARE)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as prey, \
                    mud.connect(timeout=120) as young:
                for client, name in ((imm, "Zcarver"), (prey, "Zgobble"), (young, "Zpoult")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                imm.sync("holylight")

                # It comes on its own, for the level 45, within a few cycles.
                self.assertTrue(wait_for(prey, "GOBBLE GOBBLE GOBBLE", 40), prey.transcript[-1500:])
                self.assertIn("KILL TURKEY", prey.transcript)
                self.assertIn("not on the menu", prey.transcript)
                status = imm.sync("disaster")
                self.assertRegex(status, r"giant turkey \(level 47\) waits in room \d+ with Zgobble")

                # The fight, where nothing can walk in: it clowns about.
                imm.sync("goto zgobble")
                imm.must(f"transfer turkey {QUIET_ROOM}", "Ok.")
                imm.must(f"transfer zgobble {QUIET_ROOM}", "Ok.")
                imm.must(f"goto {QUIET_ROOM}", "Sparring Floor")
                mark = len(prey.transcript)
                prey.send("kill turkey")
                gags = ("cranberry sauce", "feathers", "plays dead", "chickens", "pilgrim hat",
                        "gravy boat", "LOOK! A HAM!", "birds fall out of trees", "baster",
                        "trips over its own wattle")
                deadline = time.time() + 30
                while time.time() < deadline:
                    prey.drain(1.0)
                    if any(g in prey.transcript[mark:] for g in gags):
                        break
                fought = prey.transcript[mark:]
                self.assertTrue(any(g in fought for g in gags), fought[-1500:])

                # Slain: coin, dinner, and its gear made for level 45.
                slain = imm.sync("slay turkey")
                self.assertIn("feast's worth of loot", slain + prey.transcript[-800:])
                corpse = imm.sync("look in corpse")
                self.assertIn("plate of roast turkey", corpse)
                dropped = [kw for short, kw in GEAR.items() if short in corpse]
                self.assertTrue(dropped, corpse)
                imm.sync("get all corpse")
                stat = imm.sync(f"stat obj {dropped[0]}")
                self.assertIn("Level: 45", stat)
                self.assertRegex(stat, r"Affects \w+ by -?\d+")

                # Never twice in a holiday; never below level 40.
                mark = len(prey.transcript)
                young_mark = len(young.transcript)
                imm.must(f"transfer zgobble {SQUARE}", "Ok.")
                prey.drain(25.0)
                self.assertNotIn("GOBBLE GOBBLE GOBBLE", prey.transcript[mark:])
                self.assertNotIn("GOBBLE GOBBLE GOBBLE", young.transcript)
                self.assertIn("cannot reach them", imm.sync("disaster dragon zpoult"))
                prey.send("save")
                prey.drain(1.0)
            saved = (mud.player_dir / "Zgobble").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertRegex(saved, r"\nTurkey 20\d\d\n")
        self.assertIn("Giant turkey: snatched Zgobble (level 45)", log)
        self.assertEqual(log.count("Giant turkey: snatched"), 1)
        self.assertRegex(log, r"Giant turkey: slain by Zcarver, dropping [^\n]*(Drumstick|gravy|"
                              r"turkey feathers|Wishbone|Wattle)")

    def test_out_of_the_holiday_it_is_the_dragon(self) -> None:
        env = dict(self.ENV, TOC_SEASON="none")
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zcarver", Levl=70, Room=TEMPLE)
            make(mud, "Zgobble", Levl=45, Room=SQUARE)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as prey:
                login(imm, "Zcarver", PW)
                login(prey, "Zgobble", PW)
                prey.drain(15.0)
                self.assertNotIn("GOBBLE", prey.transcript, "no turkey visits out of season")
                self.assertIn("Done.", imm.sync("disaster dragon zgobble"))
                prey.drain(1.0)
                self.assertIn("snatches you up in its claws", prey.transcript)


if __name__ == "__main__":
    unittest.main()
