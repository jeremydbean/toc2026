"""Answering players' reports, and what Trentlin's reports of 2026-11-21 found.

- Owner, 2026-11-22: "when players report bug reports, reply to them with
  the fixes also". An entry in area/bug_replies.dat is posted at boot as a
  note from the Immortals to that player, once: a second boot finds the
  id on the board and posts nothing.
- FISTS OF FURY's strikes each carry an element; the message now names it
  ("blazing fists of fury"), so an immune foe reads as immune to fire.
- IRON SKIN says when a cast turns no blow aside, and BUY says it takes a
  count on the third identical purchase; quest coin is halved.

Synthetic Z characters in a throwaway world.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (SPARRING_GUARD, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zbrpass1"
TEMPLE = 4207
QUIET = 32703


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BugReplyTests(unittest.TestCase):
    def test_a_reply_is_posted_once_to_its_player(self) -> None:
        import datetime
        today = datetime.date.today().isoformat()
        with LiveMud() as mud:
            make(mud, "Zreporter", Levl=10, Room=TEMPLE)
            replies = mud.root / "area" / "bug_replies.dat"
            replies.write_text(
                "# test\n"
                f"@ zt-fixed {today} Zreporter\n"
                "Thank you for the report.\n\nIt is fixed now.\n"
                f"@ zt-nobody {today} Znosuchone\n"
                "Nobody reads this.\n"
                "@ zt-old 2020-01-01 Zreporter\n"
                "Too old to post.\n")
            mud.restart()
            with mud.connect(timeout=120) as hero:
                login(hero, "Zreporter", PW)
                hero.sync("scroll 0")
                listed = hero.sync("note list")
                self.assertIn("Re: your report [zt-fixed]", listed)
                self.assertNotIn("zt-old", listed)
                self.assertNotIn("zt-nobody", listed)
                read = hero.sync("note read 1")
                self.assertIn("Immortals", read)
                self.assertIn("It is fixed now.", read)
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            mud.restart()
            notes = (mud.root / "area" / "notes.txt").read_text(encoding="latin-1")
            self.assertEqual(notes.count("[zt-fixed]"), 1, "posted once, not at every boot")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Bug replies: no character Znosuchone for 'zt-nobody'; skipped.", log)

    def test_fists_name_their_element(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zbrstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zbrmonk", Levl=50, Cla=4, Room=TEMPLE,
                 HMV="9000 9000 900 900 900 900", HMVP="9000 900 900")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zbrstaff", PW)
                login(hero, "Zbrmonk", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("set skill zbrmonk 'fists of fury' 100", "")
                hero.sync("remove all")
                staff.must(f"goto {QUIET}", "")
                staff.must(f"transfer zbrmonk {QUIET}", "")
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                hero.sync("look")
                # At level 50 a fury is four to seven strikes, the first an
                # element (its count, four or more, is its damage type).
                said = hero.sync("fists sparring", timeout=30)
                self.assertRegex(said, r"(acid-slick|crackling|frost-wreathed|blazing) fists of fury",
                                 said[-1500:])


class SourceTests(unittest.TestCase):
    def test_iron_skin_buy_and_quest_coin(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("This time it turns no kind of blow aside", fight)
        const = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
        self.assertIn("Your skin loses its hardness; blows hurt you as before.", const)
        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        self.assertIn("(Tip: BUY <number> <item> buys several at once.)", act_obj)
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        coin = dict(re.findall(r"#define (QUEST_COIN_\w+)\s+(\d+)", merc))
        self.assertEqual(coin, {"QUEST_COIN_HUNT_MIN": "2", "QUEST_COIN_HUNT_MAX": "6",
                                "QUEST_COIN_RECOVER_MIN": "3", "QUEST_COIN_RECOVER_MAX": "6"})
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        self.assertNotIn("complete_automatic_quest(ch, questman, 4, 12)", quest)

    def test_the_shipped_replies_are_well_formed(self) -> None:
        text = (ROOT / "area" / "bug_replies.dat").read_text(encoding="latin-1")
        ids = re.findall(r"^@ (\S+) (\d{4}-\d{2}-\d{2}) ([A-Za-z]{2,12})$", text, re.M)
        headers = [line for line in text.splitlines() if line.startswith("@")]
        self.assertEqual(len(ids), len(headers), "every header is '@ <id> <date> <Player>'")
        names = [i for i, _, _ in ids]
        self.assertEqual(len(names), len(set(names)), "ids are never reused")
        self.assertTrue(all(ord(c) < 128 for c in text), "ASCII only")


if __name__ == "__main__":
    unittest.main()
