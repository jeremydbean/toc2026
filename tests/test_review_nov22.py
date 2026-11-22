"""What the review of 2026-11-22 confirmed, each played in a throwaway world.

- An immunity that wore off took every immunity it named, though the
  character was born with it or something else still gave it: an iron
  statue (fixture mob 32701) born immune to blunt, piercing and slashing
  blows lost one of them for good when its iron skin wore off.
- A reply to a player's report counted as posted when ANY note's subject
  held its "[id]" -- a player's own note blocked it; an impossible date
  (Feb 31) was taken; a date ahead posted at once; and a character could
  be named Immortals, the replies' sender.
- DRINK of a potion said only "You can't drink from that."; HELP SAVES,
  HELP SAVE VS and HELP JUG found nothing.
- toc.log and the dashboard's event log grew for ever, committed whole by
  the state sync (GitHub refuses a file over 100 MB). Now each is cut to
  its newest half past a limit, and what is cut is summed by day in
  log/toc-summary.tsv first -- never an address.
- tools/log_report.py headed the game's BUG: lines "bugs (0)" while the
  players' BUG reports sat lower down; they have their own heading now.

Synthetic Z characters only.
"""
from __future__ import annotations

import datetime
import re
import sys
import time
import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      skip_reason)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import log_report  # noqa: E402

SKIP = skip_reason()
PW = "Zrvpass1"
TEMPLE = 4207
QUIET = 32703
STATUE = 32701
POTION = 75


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def immune_line(stat: str) -> str:
    m = re.search(r"Immune: ([^\n\r]*)", stat)
    return m.group(1).strip() if m else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmunityTests(unittest.TestCase):
    def test_an_immunity_wearing_off_keeps_what_the_mobile_was_born_with(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrvstaff", Levl=70, Room=QUIET)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zrvstaff", PW)
                staff.sync("scroll 0")
                staff.must(f"goto {QUIET}", "")
                staff.must(f"load mob {STATUE}", "You create")
                born = immune_line(staff.must("stat mob statue", "Immune:"))
                for word in ("blunt", "piercing", "slashing"):
                    self.assertIn(word, born)
                # Iron skin draws one of the three, or none; cast until it
                # draws one (a second affect of the type, at "immunity").
                for _ in range(30):
                    staff.must("force statue iron statue", "")
                    stat = staff.must("stat mob statue", "Immune:")
                    if "'iron skin' modifies immunity" in stat:
                        break
                    staff.sync("purge statue")
                    staff.must(f"load mob {STATUE}", "You create")
                else:
                    self.fail("iron skin never drew an immunity")
                # It lasts a tick or two: wait it out.
                deadline = time.time() + 240
                while time.time() < deadline:
                    stat = staff.must("stat mob statue", "Immune:")
                    if "'iron skin'" not in stat:
                        break
                    staff.drain(5)
                else:
                    self.fail("iron skin never wore off")
                after = immune_line(stat)
                staff.send("quit")
                staff.wait_closed()
        for word in ("blunt", "piercing", "slashing"):
            self.assertIn(word, after, f"born immune to {word}, still immune after: {after}")


ARENA = 32706                   # fixture: joined to nothing, so nobody flees
GUARD = 32700


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReportedFixesInPlayTests(unittest.TestCase):
    """Trentlin's reports of 2026-11-21, played after the fix (57a0c360)."""

    def test_each_fist_names_the_element_the_foe_shrugs_off(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrvstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrvmonk", Levl=50, Cla=4, Room=TEMPLE,
                 HMV="30000 30000 900 900 900 900", HMVP="30000 900 900")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zrvstaff", PW)
                login(hero, "Zrvmonk", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("set skill zrvmonk 'fists of fury' 100", "")
                hero.sync("remove all")
                staff.must(f"goto {ARENA}", "")
                staff.must(f"transfer zrvmonk {ARENA}", "")
                staff.must(f"load mob {STATUE}", "You create")
                staff.must("set char statue hp 30000", "")
                staff.sync("restore statue")
                said = ""
                for _ in range(6):
                    said += hero.sync("fists statue", timeout=30)
                    if "unaffected" in said and re.search(r"(blazing|frost-wreathed|crackling|acid-slick) fists", said):
                        break
                for client in (staff, hero):
                    client.send("quit")
                    client.wait_closed()
        # The statue is immune to slash, pierce and bash: those strikes are
        # turned aside by name; the elements land.
        unaffected = re.findall(r"is unaffected by your ([a-z -]*fists of fury)", said)
        self.assertTrue(unaffected, said[-2000:])
        self.assertTrue(set(unaffected) <= {"knife-edged fists of fury",
                                            "needle-sharp fists of fury", "fists of fury"},
                        unaffected)
        self.assertNotRegex(said, r"unaffected by your (blazing|frost-wreathed|crackling|acid-slick)")
        self.assertRegex(said, r"Your (blazing|frost-wreathed|crackling|acid-slick) fists of fury")

    def test_iron_skin_says_what_it_turns_and_leaves_in_a_fight(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrvstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrviron", Levl=50, Cla=4, Room=TEMPLE,
                 HMV="30000 30000 900 900 900 900", HMVP="30000 900 900")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zrvstaff", PW)
                login(hero, "Zrviron", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must("set skill zrviron 'iron skin' 100", "")
                said = ""
                for _ in range(10):
                    said = hero.sync("iron")
                    if "Your skin hardens" in said:
                        break
                self.assertIn("Your skin hardens", said, said)
                drew = re.search(r"(Blunt|Piercing|Slashing) blows cannot hurt you", said)
                if drew is None:
                    self.assertIn("This time it turns no kind of blow aside", said, said)
                stat = staff.must("stat zrviron", "Fighting:")
                word = {"Blunt": "blunt", "Piercing": "piercing", "Slashing": "slashing"}
                if drew:
                    self.assertIn(word[drew.group(1)], immune_line(stat), stat)
                else:
                    self.assertEqual(immune_line(stat), "", stat)
                # Into a long fight, and the skin wears off in it.
                staff.must(f"goto {ARENA}", "")
                staff.must(f"transfer zrviron {ARENA}", "")
                staff.must(f"load mob {GUARD}", "You create")
                staff.must("set char sparring hp 30000", "")
                staff.sync("restore sparring")
                hero.sync("kill sparring")
                deadline = time.time() + 240
                while time.time() < deadline:
                    stat = staff.must("stat zrviron", "Fighting:")
                    if "'iron skin'" not in stat:
                        break
                    hero.drain(5)
                else:
                    self.fail("iron skin never wore off")
                fighting = "Fighting: a sparring guard" in stat or "sparring" in stat
                staff.sync("peace")
                for client in (staff, hero):
                    client.send("quit")
                    client.wait_closed()
        self.assertTrue(fighting, "it wore off in the fight")
        self.assertEqual(immune_line(stat), "", f"no immunity left after: {stat[-400:]}")


@unittest.skipIf(SKIP is not None, SKIP or "")
class RepliesAndWordsTests(unittest.TestCase):
    def test_replies_are_matched_whole_and_dated_strictly(self) -> None:
        today = datetime.date.today()
        ahead = (today + datetime.timedelta(days=3)).isoformat()
        with LiveMud() as mud:
            make(mud, "Zrvreporter", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zrvreporter", PW)
                hero.sync("scroll 0")
                # The player's own note, its subject holding the reply's tag.
                hero.must("note subject about [zt-blocked]", "")
                hero.must("note to all", "")
                hero.must("note + a note of my own", "")
                hero.must("note send", "")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            (mud.root / "area" / "bug_replies.dat").write_text(
                f"@ zt-blocked {today.isoformat()} Zrvreporter\n"
                "The real reply.\n"
                "@ zt-badday 2026-02-31 Zrvreporter\n"
                "Never a real date.\n"
                f"@ zt-ahead {ahead} Zrvreporter\n"
                "Not yet.\n")
            mud.restart()
            with mud.connect(timeout=120) as hero:
                login(hero, "Zrvreporter", PW)
                hero.sync("scroll 0")
                listed = hero.sync("note list")
                hero.send("quit")
                hero.wait_closed()
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
        self.assertIn("Re: your report [zt-blocked]", listed, listed)
        self.assertNotIn("zt-ahead", listed)
        self.assertNotIn("[zt-badday]", listed)
        self.assertIn("entry 'zt-badday' is malformed", log)

    def test_immortals_is_no_name_and_drink_and_help_say_what_works(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                client.expect("By what name", timeout=60)
                client.send("Immortals")
                said = client.drain(2.0) or client.transcript
                self.assertRegex(client.transcript, r"(?i)illegal name|not allowed|try another")
            make(mud, "Zrvstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrvdrinker", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zrvstaff", PW)
                login(hero, "Zrvdrinker", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")
                staff.must(f"load obj {POTION}", "You create")
                staff.must("give potion zrvdrinker", "You give")
                said = hero.sync("drink potion")
                self.assertIn("is a potion: QUAFF it.", said, said)
                saves = hero.sync("help saves")
                self.assertIn("saving throw", saves.lower(), saves)
                versus = hero.sync("help save vs")
                self.assertIn("saving throw", versus.lower(), versus)
                jug = hero.sync("help jug")
                self.assertIn("drink container", jug.lower(), jug)
                for client in (staff, hero):
                    client.send("quit")
                    client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class LogTrimTests(unittest.TestCase):
    def test_a_trimmed_log_is_summed_first_and_names_no_address(self) -> None:
        limit = 65536
        with LiveMud(extra_env={"TOC_LOG_TRIM_BYTES": str(limit)}) as mud:
            logs = mud.root / "log"
            stamp = "Sat Nov 21 10:00:00 2026"
            lines = []
            for n in range(400):
                lines.append(f"{stamp} :: [*****] BUG: Zrvbug: bad thing in room {n}.")
                lines.append(f"{stamp} :: Zrvsome@192.0.2.{n % 250} has connected.")
                lines.append(f"{stamp} :: Log Zrvsome [4207]: look")
                lines.append(f"{stamp} :: Zrvsome killed by a test clown at {29000 + n}")
            with open(logs / "toc.log", "a", encoding="latin-1") as fp:
                fp.write("\n".join(lines) + "\n")
            epoch = int(datetime.datetime(2026, 11, 21, 10, tzinfo=datetime.timezone.utc).timestamp())
            with open(logs / "webadmin-events.tsv", "a", encoding="latin-1") as fp:
                for n in range(2000):
                    fp.write(f"{epoch}\tsystem\t0\tZrvsome did a thing {n}\n")
            make(mud, "Zrvlogger", Levl=10, Room=TEMPLE)     # logs lines, and an event
            with mud.connect(timeout=120) as hero:
                login(hero, "Zrvlogger", PW)
                for _ in range(3):
                    hero.sync("look")
                hero.send("quit")
                hero.wait_closed()
            summary = (logs / "toc-summary.tsv").read_text(encoding="latin-1")
            toc_size = (logs / "toc.log").stat().st_size
            events_size = (logs / "webadmin-events.tsv").stat().st_size
            toc = (logs / "toc.log").read_text(encoding="latin-1", errors="replace")
        self.assertLess(toc_size, limit + 16384, "toc.log was cut")
        self.assertLess(events_size, limit + 16384, "the event log was cut")
        self.assertIn("2026-11-21\ttoc\tbug\tZrvbug: bad thing in room #.\t", summary)
        self.assertRegex(summary, r"2026-11-21\ttoc\tlogin\tZrvsome\t\d+")
        self.assertRegex(summary, r"2026-11-21\ttoc\tcommands\tZrvsome\t\d+")
        self.assertRegex(summary, r"2026-11-21\ttoc\tdeath\ta test clown\t\d+")
        self.assertRegex(summary, r"2026-11-21\tevents\tevent:system\t-\t\d+")
        self.assertNotRegex(summary, r"192\.0\.2", "no address in the summary")
        self.assertIn("lines are summed in log/toc-summary.tsv", toc)

    def test_a_trim_that_cannot_land_waits_and_cuts_nothing(self) -> None:
        # The summary is a directory, so every cut fails before anything is
        # renamed. It used to be tried again (the whole log read, a notice
        # written) every 256 lines -- under the test limit, every line.
        limit = 65536
        with LiveMud(extra_env={"TOC_LOG_TRIM_BYTES": str(limit)}) as mud:
            logs = mud.root / "log"
            (logs / "toc-summary.tsv").mkdir()
            stamp = "Sat Nov 21 10:00:00 2026"
            with open(logs / "toc.log", "a", encoding="latin-1") as fp:
                for n in range(2000):
                    fp.write(f"{stamp} :: Log Zrvsome [4207]: look {n}\n")
            make(mud, "Zrvwaiter", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as hero:
                login(hero, "Zrvwaiter", PW)
                for _ in range(5):
                    hero.sync("look")
                hero.send("quit")
                hero.wait_closed()
            toc = (logs / "toc.log").read_text(encoding="latin-1", errors="replace")
        self.assertGreater(len(toc), limit, "nothing was cut")
        self.assertIn("Log Zrvsome [4207]: look 0", toc, "the oldest lines are kept")
        self.assertEqual(toc.count("could not be trimmed"), 1,
                         "one failure said once, then waited out")
        self.assertNotIn("trimmed to its newest half", toc)

    def test_the_log_handle_is_let_go_before_a_trim(self) -> None:
        # A failed commit says so through log_string; with the handle closed
        # and not cleared, that wrote through a freed FILE.
        source = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        at = source.index("cut = log_file_keep_tail( GAME_LOG_FILE")
        self.assertIn("log_fp = NULL;", source[at - 300:at])


class ReportHeadingTests(unittest.TestCase):
    def test_player_reports_and_summaries_are_read(self) -> None:
        since = datetime.datetime(2026, 11, 20, tzinfo=datetime.timezone.utc)
        play = ("1795300000\treport\tZed\t50\t4207\tdresden.are\tbug\tsomething broke\t100\t-\n"
                "1795300001\tcmd\tZed\t50\t4207\tdresden.are\tstanding\n")
        self.assertEqual([(r[1], r[2], r[3]) for r in log_report.player_reports(play, since)],
                         [("bug", "Zed", "something broke")])
        summary = ("# header\n2026-11-19\ttoc\tbug\told\t2\n"
                   "2026-11-21\ttoc\tbug\tnew #\t3\nbroken line\n"
                   "#batch\ttoc\t1\t2\t3\t00ff\t4\n"
                   "2026-11-21\ttoc\tbug\ttorn\t9\n")
        self.assertEqual(log_report.summary_rows(summary, since),
                         [("2026-11-21", "toc", "bug", "new #", 3)])
        source = (ROOT / "tools" / "log_report.py").read_text()
        self.assertNotIn('"\\n== bugs (', source)
        self.assertIn("== player reports: BUG, TYPO and IDEA", source)


if __name__ == "__main__":
    unittest.main()
