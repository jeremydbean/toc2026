"""The Hall of Heroes' plaque and remort tablet fill themselves (owner,
2026-11-11: "automatically displaying all heroes ... when they hit hero
level. also, make a plaque for remorts and do the same").

heroes.c writes heroes/<Name> the moment a character reaches hero level
(advance_level) or remorts (do_remort), with the date they became a hero,
class, race and remorts. Records from before then are filled in once at
boot from the player files (hero_records_backfill). LOOK PLAQUE shows the
newest heroes and the whole roll; LOOK TABLET shows the reborn, most
lives first.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zrollpass11"
HALL = 4649


class HeroRollSourceTests(unittest.TestCase):
    def test_written_when_it_happens(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        level = update.split("void advance_level( CHAR_DATA *ch, bool is_advance )", 1)[1]
        self.assertIn("hero_record_write( ch, false );", level.split("\n}\n", 1)[0])
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        remort = info.split("void do_remort( CHAR_DATA *ch, char *arg)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hero_record_write( ch, true );", remort)
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        self.assertIn("show_remort_tablet( ch )", move)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HeroRollLiveTests(unittest.TestCase):
    def test_the_plaque_and_the_tablet(self) -> None:
        with LiveMud() as mud:
            for name, fields in (("Zrollstaff", {"Levl": 70}),
                                 ("Zrollhero", {"Levl": 50}),
                                 ("Zrollreborn", {"Levl": 10, "NumRemorts": 2}),
                                 ("Zrollold", {"Levl": 52})):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Room=HALL, **fields)
            heroes = mud.root / "heroes"
            # A record from before: only the old first line.
            (heroes / "Zrollold").write_text("Lev 52 Trust 52  Zrollold the Old\n")
            for stale in ("Zrollhero", "Zrollreborn"):
                (heroes / stale).unlink(missing_ok=True)
            mud.restart()           # the boot fills the records in

            old = (heroes / "Zrollold").read_text()
            self.assertIn("Lev 52 Trust 52  Zrollold the Old", old, "first line kept")
            self.assertIn("Since 0", old, "when they became a hero was never written")
            self.assertIn("Remorts 0", old)
            reborn = (heroes / "Zrollreborn").read_text()
            self.assertIn("Remorts 2", reborn)
            self.assertFalse((heroes / "Zrollhero").exists(), "level 50 is no hero yet")

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zrollstaff", PW)
                login(hero, "Zrollhero", PW)
                staff.sync("scroll 0")
                staff.must("advance zrollhero 51", "51")
                record = (heroes / "Zrollhero").read_text()
                since = int(re.search(r"(?m)^Since (\d+)$", record).group(1))
                self.assertGreater(since, 1700000000, "dated the moment it happened")

                plaque = staff.sync("look plaque", timeout=60)
                self.assertIn("The newest:", plaque)
                self.assertRegex(plaque, r"Zrollhero\s+\S+\s+\S+\s+hero since \d{4}-\d\d-\d\d")
                self.assertIn("Zrollold", plaque)
                tablet = staff.sync("look tablet", timeout=60)
                self.assertIn("The Reborn of ToC", tablet)
                self.assertRegex(tablet, r"\b2\s+Zrollreborn\b")
                self.assertNotIn("Zrollold", tablet, "no remorts: not on the tablet")
                for client in (hero, staff):
                    client.send("quit")
                    client.wait_closed()
            self.assertFalse((heroes / "Zrollstaff").exists(), "staff are on neither roll")


@unittest.skipIf(SKIP is not None, SKIP or "")
class HeroRollStaffTests(unittest.TestCase):
    """Staff are on neither roll, however their record came to be (review,
    2026-11-11: a record saying Lev 70 Trust 70 was shown on both)."""

    def test_staff_records_are_left_out(self) -> None:
        with LiveMud() as mud:
            for name, fields in (("Zrollkeeper", {"Levl": 70}),
                                 ("Zrollpromo", {"Levl": 52}),
                                 ("Zrollfile", {"Levl": 53, "NumRemorts": 1})):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Room=HALL, **fields)
            heroes = mud.root / "heroes"
            # Legacy and current records of staff, no player file behind them.
            (heroes / "Zstaffrec").write_text("Lev 70 Trust 70  Zstaffrec\n")
            (heroes / "Zstaffnew").write_text(
                "Lev 60 Trust 70  Zstaffnew\nSince 1790000000\nRemorts 3\nReborn 0\n")
            # A mortal whose player file is gone keeps their place.
            (heroes / "Zorphan").write_text(
                "Lev 55 Trust 55  Zorphan\nSince 1790000000\nRemorts 2\nReborn 0\n")
            # A malformed number is read as unknown, never as a guess.
            (heroes / "Zmangled").write_text(
                "Lev 5x Trust 51  Zmangled\nSince 12abc\nRemorts 99999999999999\nReborn -\n")
            mud.restart()
            # Zrollfile has a mortal record from the boot; make them staff
            # in the file and boot again: the record is rewritten with the rank.
            self.assertIn("Remorts 1", (heroes / "Zrollfile").read_text())
            patch_player_file(mud, "Zrollfile", Levl=70)
            mud.restart()
            self.assertIn("Lev 70", (heroes / "Zrollfile").read_text())

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as promo:
                login(staff, "Zrollkeeper", PW)
                login(promo, "Zrollpromo", PW)
                staff.sync("scroll 0")
                staff.must("advance zrollpromo 51", "51")
                promo.sync("save")
                plaque = staff.sync("look plaque", timeout=60)
                self.assertIn("Zrollpromo", plaque, "a new hero is on the plaque")
                # Promoted to staff: off the roll at their next save.
                staff.sync("trust zrollpromo 70")
                promo.sync("save")
                plaque = staff.sync("look plaque", timeout=60)
                tablet = staff.sync("look tablet", timeout=60)
                for gone in ("Zstaffrec", "Zstaffnew", "Zrollpromo", "Zrollfile"):
                    self.assertNotIn(gone, plaque, gone)
                    self.assertNotIn(gone, tablet, gone)
                self.assertIn("Zorphan", plaque, "a gone mortal hero stays")
                self.assertRegex(tablet, r"\b2\s+Zorphan\b")
                self.assertIn("Zmangled", plaque)
                self.assertNotIn("Zmangled", tablet, "an unreadable remort count is 0")
                for client in (promo, staff):
                    client.send("quit")
                    client.wait_closed()
            self.assertTrue((heroes / "Zrollpromo").exists(), "the record is kept, only hidden")


if __name__ == "__main__":
    unittest.main()
