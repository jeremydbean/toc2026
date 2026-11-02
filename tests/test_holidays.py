"""The holiday calendar and its fairs (owner, 2026-11-02).

Holidays follow World of Warcraft's schedule -- the Lunar Festival, Love
is in the Air, Noblegarden at Easter, Children's Week, the Midsummer Fire
Festival, Pirates' Day, Brewfest, Hallows End, the Day of the Dead,
Pilgrim's Bounty at Thanksgiving and Winter Veil -- with St. Patrick's
Day beside them. Each puts a vendor and a decoration in the Oak Tree
Square, drops a treat from NPC kills and says so at login and in TIME,
and a few treats do something of their own: a four-leaf clover's pot of
gold, a red envelope of lucky money, a rose that blesses two, a firework
the whole area sees, painted eggs with something inside.

Every world here is a test world (TOC_SEASON picks the holiday, TOC_DATE
the date, TOC_HOLIDAY_DROPS=always makes the treat certain); every
character a synthetic Z fixture.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GUARD, create_character, login, patch_player_file,
                      room_of, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zholpass1"
SQUARE, TEMPLE, FLOOR = 2401, 4207, 32700


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\x1b\[[0-9;]*m", "", text))


def slay_weak_guard(staff, hero, hero_name: str) -> str:
    """Load a sparring guard on one hit point and have the hero kill it
    with a blow that cannot miss. Returns the hero's reply."""
    staff.must(f"goto {FLOOR}", "")
    staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
    staff.must("set char sparring hp 1", "now set to 1")
    staff.must("restore sparring", "")
    staff.must(f"set char {hero_name} hitroll 300", "hitroll set to 300")
    staff.must(f"transfer {hero_name} {FLOOR}", "Ok.")
    mark = len(hero.transcript)
    reply = hero.sync("kill sparring")
    if "is DEAD" not in reply:
        # It may parry the first round; the fight goes on by itself.
        hero.expect("is DEAD", timeout=30)
        hero.sync("look")
    return hero.transcript[mark:]


class HolidaySourceTests(unittest.TestCase):
    def test_the_two_seasons_read_the_one_calendar(self) -> None:
        season = (ROOT / "src" / "season.c").read_text(encoding="latin-1")
        body = season[season.index("static SEASON_TYPE get_current_season( void )"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("holiday_key()", body)
        self.assertNotIn("tm_mon", body, "the dates live in holiday.c alone")

    def test_every_table_vnum_exists(self) -> None:
        text = (ROOT / "area" / "holidays.are").read_text(encoding="latin-1")
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        for name, vnum in re.findall(r"#define ((?:MOB|OBJ)_VNUM_(?:VENDOR|DECOR)_\w+|"
                                     r"OBJ_VNUM_(?:RED_|CANDY_|FOUR_|PAINTED_|LOLLIPOP|FIREWORK|"
                                     r"GROG|AUTUMN_|SUGAR_|PUMPKIN_PIE|PAPER_|RICE_|CHOCOLATE|"
                                     r"HEART_|GREEN_|BUNNY_|SPINNING_|FLOWER_|TRICORN|STEIN|"
                                     r"PRETZEL|MARIGOLDS|SKULL_|PILGRIM_|ROAST_)\w*)\s+(298\d\d)",
                                     merc):
            with self.subTest(name=name):
                self.assertIn(f"\n#{vnum}\n", text)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HolidayCalendarLiveTests(unittest.TestCase):
    def test_the_date_picks_the_holiday_and_the_calendar_moves_with_easter(self) -> None:
        env = {"TOC_SEASON": None, "TOC_DATE": "2027-03-25", "TOC_HOLIDAY_DROPS": "always"}
        with LiveMud(extra_env=env, fixtures=True) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholhero", Levl=20, Room=SQUARE, HMV="300 300 300 300 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zholstaff", PW)
                login(hero, "Zholhero", PW)
                greeting = plain(hero.transcript)
                staff.sync("scroll 0")
                hero.sync("scroll 0")
                self.assertIn("Noblegarden is here!", greeting)
                self.assertIn("celebrating Noblegarden", hero.sync("holidays"))

                cal = plain(hero.must("holidays 2027", "The holidays of 2027"))
                self.assertIn("Noblegarden Mar 22 - Mar 28", cal)
                self.assertIn("Pilgrim's Bounty Nov 22 - Nov 28", cal)
                self.assertIn("Winter Veil Dec 16 - Jan 6", cal)
                self.assertIn("Pirates' Day Sep 19", cal)
                cal = plain(hero.must("holidays 2026", "The holidays of 2026"))
                self.assertIn("Noblegarden Mar 30 - Apr 5", cal)
                self.assertIn("Pilgrim's Bounty Nov 23 - Nov 29", cal)
                self.assertIn("Name a year", hero.sync("holidays 12"))

                # The fair: decoration and vendor, and eggs hidden in Dresden.
                staff.must("holidays refresh", "up to date")
                square = plain(hero.sync("look"))
                self.assertIn("giant wicker basket of painted eggs", square)
                self.assertIn("Hopscotch the egg warden", square)
                self.assertIn("bunny ears", plain(hero.sync("list")))
                status = plain(staff.sync("holidays"))
                self.assertRegex(status, r"eggs lying [1-9]")

                # A kill's egg opens on something (fixtures autoloot).
                self.assertIn("You get a brightly painted egg",
                              slay_weak_guard(staff, hero, "zholhero"))
                hero.must("open egg", "Ok.")
                inside = plain(hero.sync("look in egg"))
                self.assertRegex(inside, r"chocolate rabbit|lollipop|bunny ears|coins?|platinum|gold|silver|copper",
                                 inside)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HolidayFairLiveTests(unittest.TestCase):
    def test_love_a_rose_blesses_two(self) -> None:
        with LiveMud(extra_env={"TOC_SEASON": "love"}) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholgiver", Levl=20, Room=SQUARE, NewPlat=100)
            make(mud, "Zholtaker", Levl=20, Room=SQUARE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as giver, \
                    mud.connect(timeout=120) as taker:
                login(staff, "Zholstaff", PW)
                login(giver, "Zholgiver", PW)
                login(taker, "Zholtaker", PW)
                self.assertIn("Love is in the Air!", plain(giver.transcript))
                for client in (staff, giver, taker):
                    client.sync("scroll 0")
                staff.must("holidays refresh", "up to date")
                square = plain(giver.sync("look"))
                self.assertIn("garland of paper hearts", square)
                self.assertIn("Rosalind", square)
                listing = plain(giver.sync("list"))
                self.assertIn("a red rose", listing)
                self.assertIn("paper heart", listing, "every shopkeeper's holiday word")
                giver.must("buy rose", "You buy")

                given = plain(giver.sync("give rose zholtaker"))
                self.assertIn("The rose blooms", given)
                self.assertIn("ACHIEVEMENT EARNED A Rose by Any Name", given)
                self.assertNotIn("red rose", plain(giver.sync("inventory")))
                self.assertNotIn("red rose", plain(taker.sync("inventory")))
                self.assertIn("bless", giver.sync("affects"))
                self.assertIn("bless", taker.sync("affects"))

                # To a mobile it is only a flower.
                giver.must("buy rose", "You buy")
                giver.sync("give rose rosalind")
                self.assertNotIn("The rose blooms", plain(giver.transcript[-400:]))

    def test_stpatrick_a_clover_turns_a_kill_into_gold(self) -> None:
        env = {"TOC_SEASON": "stpatrick", "TOC_HOLIDAY_DROPS": "always"}
        with LiveMud(extra_env=env, fixtures=True) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholhero", Levl=20, Room=TEMPLE, HMV="300 300 300 300 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zholstaff", PW)
                login(hero, "Zholhero", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")
                self.assertIn("St. Patrick's Day", hero.sync("holidays"))

                # The first kill drops a clover; eaten, the next kill pays.
                self.assertIn("You get a four-leaf clover",
                              slay_weak_guard(staff, hero, "zholhero"))
                eaten = plain(hero.sync("eat clover"))
                self.assertIn("next foe you slay will spill a pot of gold", eaten)
                staff.must("purge", "")
                slain = plain(slay_weak_guard(staff, hero, "zholhero"))
                self.assertIn("pot of gold tumbles out", slain)
                self.assertIn("ACHIEVEMENT EARNED Pot of Gold", slain)
                self.assertRegex(slain, r"You get \d+ (platinum|gold) coins?", slain)

                # Spent: the next kill is an ordinary one.
                staff.must("purge", "")
                self.assertNotIn("pot of gold", plain(slay_weak_guard(staff, hero, "zholhero")))

    def test_lunar_an_envelope_holds_lucky_money(self) -> None:
        env = {"TOC_SEASON": "lunar", "TOC_HOLIDAY_DROPS": "always"}
        with LiveMud(extra_env=env, fixtures=True) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholhero", Levl=20, Room=TEMPLE, HMV="300 300 300 300 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zholstaff", PW)
                login(hero, "Zholhero", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")
                self.assertIn("You get a red envelope",
                              slay_weak_guard(staff, hero, "zholhero"))
                hero.must("open envelope", "Ok.")
                inside = plain(hero.sync("look in envelope"))
                self.assertRegex(inside, r"platinum|gold|silver|copper", inside)

    def test_midsummer_a_firework_goes_up_and_off_season_nothing_stands(self) -> None:
        with LiveMud(extra_env={"TOC_SEASON": "midsummer"}) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholhero", Levl=20, Room=SQUARE, NewPlat=100)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zholstaff", PW)
                login(hero, "Zholhero", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")
                staff.must("holidays refresh", "up to date")
                self.assertIn("great midsummer bonfire", plain(hero.sync("look")))
                hero.must("buy firework", "You buy")
                burst = plain(hero.sync("drop firework"))
                self.assertIn("whistles straight up into the sky and bursts", burst)
                self.assertIn("Overhead, a firework bursts into", burst)
                self.assertIn("ACHIEVEMENT EARNED Light Up the Sky", burst)
                self.assertNotIn("firework", plain(hero.sync("look")).split("bonfire")[-1])

                # Trick-or-treat candy is a treat or a (harmless) trick,
                # and a bite even on a full stomach.
                staff.must("load obj 29900", "You create")
                staff.must("give candy zholhero", "You give")
                eaten = plain(hero.sync("eat candy"))
                self.assertRegex(eaten, r"(Treat|Trick)!", eaten)

        with LiveMud() as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zholstaff", PW)
                staff.sync("scroll 0")
                self.assertIn("No holiday is being celebrated", staff.sync("holidays"))
                staff.must("holidays refresh", "up to date")
                square = plain(staff.sync("look"))
                for decoration in ("bonfire", "paper lanterns", "painted eggs", "Rosalind"):
                    self.assertNotIn(decoration, square)


if __name__ == "__main__":
    unittest.main()
