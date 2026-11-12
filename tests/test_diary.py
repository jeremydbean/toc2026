"""The diary (owner, 2026-11-12: "a diary feature that uses the player
logging system to allow players to see their daily progress and what they
did each day").

diary.c keeps each mortal's day -- time played, levels and experience,
kills (the notable ones by name), deaths and close calls, quests, achieve-
ments, skills, areas, things gained, coin in and out -- from the play
journal's own hooks, in memory until a save writes it to
player/diary/<Name>. A day is the holiday calendar's (TOC_DATE_FILE moves
it here), and the last 30 are kept. Only the owner reads it; staff may
read anybody's and keep none, so a wizinvis immortal leaves no trace.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GUARD, create_character, login, patch_player_file,
                      room_of, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zdiarypass1"
TEMPLE, FLOOR = 4207, 32700
HELMET, VEST = 4619, 3703      # a great war helmet, a sub issue vest


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\x1b\[[0-9;]*m", "", text))


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)


def diary_file(mud: LiveMud, name: str) -> Path:
    return mud.player_dir / "diary" / name


class DiarySourceTests(unittest.TestCase):
    """The diary is fed by the play journal's own hooks, so the two cannot
    disagree about what happened."""

    def test_the_journal_hooks_feed_it(self) -> None:
        playlog = source("playlog.c")
        for hook in ("diary_coin(", "diary_got(", "diary_level(", "diary_moved(",
                     "diary_skill(", "diary_exp("):
            self.assertIn(hook, playlog, hook)
        fight = source("fight.c")
        gain = fight[fight.index("progress_kill( gch, victim"):][:300]
        self.assertIn("diary_kill( gch, victim )", gain)
        self.assertIn("diary_death( victim, ch )", fight)
        self.assertIn("diary_close_call(", fight)
        self.assertIn("diary_close_call(", source("act_move.c"))
        quest = source("quest.c")
        self.assertIn("diary_quest_done( ch, true, points )", quest)
        self.assertIn("diary_quest_done( ch, false, 0 )", quest)
        self.assertEqual(quest.count("diary_quest_points("), 2)
        self.assertIn("diary_achieved(", source("achievements.c"))
        self.assertIn("diary_save( ch );", source("save.c"))
        self.assertIn("diary_free( ch );", source("db.c"))
        self.assertIn("diary_login( ch, is_new_character );", source("comm.c"))
        self.assertIn("diary_rename(", source("act_wiz.c"))
        self.assertIn("diary_retire( ch );", source("act_comm.c"))

    def test_written_whole_and_aside(self) -> None:
        diary = source("diary.c")
        self.assertIn("temp_file_commit( fp, temp, path )", diary)
        self.assertIn("#define DIARY_DAYS      30", diary)
        # The calendar the holidays read, so TOC_DATE moves it in tests.
        self.assertIn("holiday_date( &y, &m, &d )", diary)

    def test_diary_keeps_staffs_abbreviation(self) -> None:
        interp = source("interp.c")
        self.assertLess(interp.index('{ "diagnostics"'), interp.index('{ "diary"'))
        self.assertLess(interp.index('{ "dirt"'), interp.index('{ "diary"'))


@unittest.skipIf(SKIP is not None, SKIP or "")
class DiaryLiveTests(unittest.TestCase):
    def test_a_day_in_the_diary(self) -> None:
        dates = tempfile.TemporaryDirectory(prefix="toc-diary-date-")
        self.addCleanup(dates.cleanup)
        date_file = Path(dates.name) / "date"
        date_file.write_text("2027-03-01\n")
        with LiveMud(fixtures=True, extra_env={"TOC_DATE_FILE": str(date_file)}) as mud:
            make(mud, "Zdiarystaff", Levl=70, NewGold=50)
            make(mud, "Zdiaryhero", Levl=10, Cla=3, HMV="100 100 100 100 300 300")
            make(mud, "Zdiaryother")
            # Made a mortal at level 1 today, so a page exists from then;
            # as staff nothing more is ever written to it.
            staff_page = diary_file(mud, "Zdiarystaff").read_bytes()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zdiarystaff", PW)
                login(hero, "Zdiaryhero", PW)
                staff.sync("scroll 0")
                hero.sync("scroll 0")

                staff.must("advance zdiaryhero 12", "12")
                staff.must(f"load obj {HELMET}", "You create")
                staff.must("give helmet zdiaryhero", "You give")
                staff.must("give 5 gold zdiaryhero", "You give")
                hero.must("give 1 gold zdiarystaff", "You give")

                # A kill on a twentieth of their hit points: a close call too.
                staff.must(f"goto {FLOOR}", "")
                staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
                staff.must("set char sparring hp 1", "now set to 1")
                staff.must("restore sparring", "")
                staff.must("set char zdiaryhero hitroll 300", "hitroll set to 300")
                # 500 of 20,000: under a twentieth (1,000), and room for
                # ~25 of the guard's rounds -- on 50 the hero survived about
                # two, and two dodged, parried or rolled-miss rounds in a row
                # killed it (CI, 2026-11-12, both modules in one run).
                staff.must("set char zdiaryhero hp 500", "now set to 500")
                staff.must("restore zdiaryhero", "restored")
                staff.must("set char zdiaryhero hp 20000", "now set to 20000")
                staff.must(f"transfer zdiaryhero {FLOOR}", "Ok.")
                self.assertEqual(room_of(staff, "zdiaryhero"), FLOOR)
                mark = len(hero.transcript)
                if "is DEAD" not in hero.sync("kill sparring"):
                    hero.expect("is DEAD", timeout=30)
                self.assertIn("is DEAD", hero.transcript[mark:])

                # Wizinvis staff hand over a thing: it is the hero's gain,
                # and nothing anywhere says who.
                staff.must("wizinvis", "vanish")
                staff.must(f"load obj {VEST}", "You create")
                staff.must("give vest zdiaryhero", "You give")

                hero.must("color on", "")
                mark = len(hero.raw)
                today = hero.sync("diary")
                self.assertIn(b"\x1b[", hero.raw[mark:], "coloured with colour on")
                text = plain(today)
                self.assertIn("Your diary -- Monday 1 March 2027 (today)", text)
                # Made at level 1 today (make()), patched to 10, advanced to 12.
                self.assertRegex(text, r"Level 1 to 12 \(2 gained\)")
                self.assertIn("Kills: 1.", text)
                self.assertIn("won a fight near death", text)
                self.assertIn("Last One Standing (+20)", text)
                self.assertIn("a great war helmet", text)
                self.assertIn("a sub issue vest", text)
                self.assertRegex(text, r"Coin in: loot \d+g\b")
                self.assertRegex(text, r"Coin out: give 1g\b")
                self.assertRegex(text, r"Areas: .*Test Fixtures", "the fixture area is named")
                self.assertRegex(text, r"Experience: \d+ gained")
                self.assertNotIn("Zdiarystaff", text)
                for line in today.split("\n"):
                    visible = re.sub(r"\x1b\[[0-9;]*m", "", line).rstrip("\r")
                    self.assertLessEqual(len(visible), 78, visible)

                hero.must("color off", "disabled")
                mark = len(hero.raw)
                bare = hero.sync("diary")
                self.assertNotIn(b"\x1b", hero.raw[mark:])
                self.assertNotIn("{0", bare, "no colour token shown raw")
                self.assertIn("Kills: 1.", plain(bare))

                # Staff read it; their own they do not keep.
                seen = plain(staff.sync("diary zdiaryhero"))
                self.assertIn("Zdiaryhero's diary -- Monday 1 March 2027", seen)
                self.assertIn("Kills: 1.", seen)
                self.assertIn("Staff keep no diary", staff.sync("diary"))

                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            written = diary_file(mud, "Zdiaryhero").read_text(encoding="latin-1")
            self.assertIn("Day 2027-03-01", written)
            self.assertIn("Kills 1", written)
            self.assertNotIn("Zdiarystaff", written)
            self.assertEqual(diary_file(mud, "Zdiarystaff").read_bytes(), staff_page,
                             "staff keep none: a wizinvis immortal leaves no trace")

            with mud.connect(timeout=120) as other:
                login(other, "Zdiaryother", PW)
                said = other.sync("diary zdiaryhero")
                self.assertIn("read by its owner alone", said)
                self.assertNotIn("Kills", said)

            # Saved, quit and back: the day is still there; then the page
            # turns at the calendar's midnight.
            with mud.connect(timeout=120) as hero:
                login(hero, "Zdiaryhero", PW)
                hero.sync("scroll 0")
                self.assertIn("Kills: 1.", plain(hero.sync("diary")))
                date_file.write_text("2027-03-02\n")
                turned = plain(hero.sync("diary"))
                self.assertIn("Tuesday 2 March 2027 (today)", turned)
                self.assertNotIn("Kills:", turned)
                before = plain(hero.sync("diary yesterday"))
                self.assertIn("Monday 1 March 2027 (yesterday)", before)
                self.assertIn("Kills: 1.", before)
                self.assertIn("Kills: 1.", plain(hero.sync("diary 2027-03-01")))
                listed = plain(hero.sync("diary list"))
                self.assertRegex(listed, r"2027-03-02 .* 2027-03-01 ")
                self.assertRegex(listed, r"2027-03-01 +\S+ +1-12 +1 +0 +0 +\+\d+g")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())

    def test_thirty_days_kept_and_the_name_moves_on(self) -> None:
        dates = tempfile.TemporaryDirectory(prefix="toc-diary-date-")
        self.addCleanup(dates.cleanup)
        date_file = Path(dates.name) / "date"
        date_file.write_text("2027-01-01\n")
        with LiveMud(extra_env={"TOC_DATE_FILE": str(date_file)}) as mud:
            make(mud, "Zdiarykeep", Levl=70)
            make(mud, "Zdiarylong")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zdiarykeep", PW)
                login(hero, "Zdiarylong", PW)
                hero.sync("scroll 0")
                for day in range(1, 34):            # 2027-01-01 .. 2027-02-02
                    month, mday = (1, day) if day <= 31 else (2, day - 31)
                    date_file.write_text(f"2027-{month:02d}-{mday:02d}\n")
                    self.assertIn(f" {mday} ", plain(hero.sync("diary")))
                hero.sync("save")
                written = diary_file(mud, "Zdiarylong").read_text(encoding="latin-1")
                self.assertEqual(written.count("\nDay "), 30, written[:400])
                self.assertNotIn("Day 2027-01-03", written, "the oldest rolled off")
                self.assertIn("Day 2027-01-04", written)
                self.assertIn("Day 2027-02-02", written)
                self.assertIn("Nothing is written", hero.sync("diary 2027-01-02"))
                listed = hero.sync("diary list")
                self.assertEqual(len(re.findall(r"\b2027-\d\d-\d\d\b", plain(listed))), 30)

                # RENAME carries the diary to the new name.
                staff.must("rename zdiarylong Zdiarynew", "renamed")
                self.assertFalse(diary_file(mud, "Zdiarylong").exists())
                self.assertIn("Day 2027-01-04", diary_file(mud, "Zdiarynew").read_text())
                self.assertIn("2027-02-02", plain(hero.sync("diary list")))

                # DELETE sets it aside, so the name's next owner starts clean.
                hero.must("delete", "Type delete again")
                hero.send(f"delete {PW}")
                self.assertTrue(hero.wait_closed())
            self.assertFalse(diary_file(mud, "Zdiarynew").exists())
            aside = list((mud.player_dir / "diary").glob("Zdiarynew.deleted-*"))
            self.assertEqual(len(aside), 1, aside)
            with mud.connect(timeout=120) as again:
                create_character(again, "Zdiarynew", PW)
                again.sync("scroll 0")
                fresh = plain(again.sync("diary list"))
                self.assertNotIn("2027-01-04", fresh)
                self.assertIn("2027-02-02", fresh)


if __name__ == "__main__":
    unittest.main()
