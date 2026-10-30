"""The review tools: tools/audit_players.py, tools/audit_maxload.py and
tools/log_report.py.

Both read the game's own tables and the synced logs, so these hold the
parts that could quietly stop working: that the tables still parse, that
the audit still sees the creation bug's footprint, that staff are left
alone, and that nothing printed carries an address or a hostname.
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAYER = """#PLAYER
Name Ztest~
Race dwarf~
Cla  3
Gui  3
Levl 44
Alig  -1000
Prac 8
Fixes ~
Sk 75 'armor'
Sk 100 'sword'
Sk 76 'refresh'
Gr 'rom basics'
Gr 'mage basics'
Gr 'warrior basics'
Gr 'mage default'
Gr 'warrior default'
Gr 'warrior guild'
End
"""


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = load("audit_players")
        self.tables = self.audit.load_tables()

    def test_the_tables_parse(self) -> None:
        self.assertIn("refresh", self.tables["skills"])
        self.assertIn("mage default", self.tables["groups"])
        self.assertEqual(self.tables["races"]["dwarf"], ["bash"])
        self.assertIn("20261021-mage-groups", self.tables["fixes"])
        self.assertIn(30542, self.tables["retired"])

    def test_the_creation_bug_shows(self) -> None:
        kinds = {f["kind"] for f in self.audit.audit_one("Ztest", PLAYER, self.tables, None)}
        self.assertIn("class-group", kinds)
        self.assertIn("fix-pending", kinds)

    def test_staff_and_the_staff_trusted_are_left_alone(self) -> None:
        for change in (("Levl 44", "Levl 60"), ("Levl 44", "Levl 44\nTru  70")):
            text = PLAYER.replace(*change)
            self.assertEqual(self.audit.audit_one("Ztest", text, self.tables, None), [])

    def test_out_of_range_values(self) -> None:
        text = PLAYER.replace("Alig  -1000", "Alig  1005").replace("Prac 8", "Prac -3")
        kinds = {f["kind"] for f in self.audit.audit_one("Ztest", text, self.tables, None)}
        self.assertTrue({"alignment", "counts"} <= kinds)


class MaxloadAuditTests(unittest.TestCase):
    def test_counts_every_depth_and_skips_copies(self) -> None:
        import tempfile

        tool = load("audit_maxload")
        record = "#O\nVnum %d\nNest %d\nWear -1\nEnd\n\n"
        with tempfile.TemporaryDirectory() as tmp:
            players = pathlib.Path(tmp) / "player"
            players.mkdir()
            # A bag holding a bag holding the limited item, and one stashed.
            (players / "Zhoarder").write_text(
                "#PLAYER\nName Zhoarder~\nEnd\n\n" + record % (3032, 0)
                + record % (3032, 1) + record % (3715, 2)
                + "#STASH\n" + record % (3715, 0) + "#END\n")
            # A hand-kept copy is not a character.
            (players / "Zhoarder.Bu").write_text(record % (3715, 0))
            maxload = pathlib.Path(tmp) / "maxload.txt"
            maxload.write_text("ML 3715 2 3000\nML 911 1 2100\n$\n")
            counted = {}
            for name, text in tool.player_files(None, str(players)):
                counted[name] = tool.held(text, {3715, 911})
            self.assertEqual(list(counted), ["Zhoarder"])
            self.assertEqual(counted["Zhoarder"][3715], 2)
            self.assertEqual(tool.read_maxload(None, str(maxload)),
                             {3715: (2, 3000), 911: (1, 2100)})


class LogReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = load("log_report")

    def test_nothing_printed_carries_an_address(self) -> None:
        line = "Misery@108-81-26-245.example.net has connected from 203.0.113.9."
        cleaned = self.report.clean(line)
        self.assertNotIn("203.0.113.9", cleaned)
        self.assertNotIn("example.net", cleaned)
        # Found in review, 2026-10-21: a resolved name with no "@", IPv6,
        # and the staff line that exists to name an address.
        for line, secret in (
                ("on from cpe-12-34.res.rr.com today", "rr.com"),
                ("from 2001:db8::1 now", "2001:db8"),
                ("Zed shares an address with Bob: 2 players on from home.example.org.", "Bob")):
            self.assertNotIn(secret, self.report.clean(line), line)
        self.assertEqual(self.report.clean("a ghost wails at 12:34"), "a ghost wails at 12:34")
        self.assertTrue(self.report.WATCHED.match("Log Zed [-]: buy cake"),
                        "a room the game hides is still a watched line")

    def test_the_journal_spots_a_refusal(self) -> None:
        for reply in ("You can't do that.", "They aren't here.", "Huh?",
                      "There is no door in that direction.", "You don't have that."):
            self.assertTrue(self.report.SAID_NO.match(reply), reply)
        for reply in ("The Temple of Dresden", "You wear a sword.", "Ok."):
            self.assertFalse(self.report.SAID_NO.match(reply), reply)

    def test_a_word_refused_once_is_not_printed(self) -> None:
        source = (ROOT / "tools" / "log_report.py").read_text(encoding="utf-8")
        self.assertIn("if 2 <= n < 50", source, "a password typed by mistake is refused once")

    def test_watch_log_events_are_not_commands(self) -> None:
        for event in ("coin +4 platinum", "gold -250", "bought a pie (vnum 3009) for 1 copper",
                      "(social) smile", "stashed a sword"):
            self.assertTrue(self.report.EVENT_LINE.match(event), event)
        for command in ("smite", "get all", "goto 4207", "golem"):
            self.assertFalse(self.report.EVENT_LINE.match(command), command)

    def test_new_watch_lines_are_not_commands(self) -> None:
        for event in ("affects off: titanic; max hp 5474 -> 924",
                      "quest assigned: kill a harpy (mob 9101, level 48) in olympus.are, 20 minutes, ordinary",
                      "quest complete: 5p, 37 quest points (streak bonus 121%)",
                      "daily quest complete: 108p 16g 8s, 1 daily points (2 today)",
                      "died to a security guard"):
            self.assertTrue(self.report.EVENT_LINE.match(event), event)
        found = self.report.QUEST_ASSIGNED.match(
            "quest assigned: recover a gem (obj 3715) in haon.are, 30 minutes, daily")
        self.assertEqual(found.group(2, 4), ("haon.are", "daily"))

    def test_coin_reads_as_the_game_writes_it(self) -> None:
        self.assertEqual(self.report.format_copper(148721100), "148p 72g 11s")
        self.assertEqual(self.report.format_copper(-420 * 10_000), "-4p 20g")
        self.assertEqual(self.report.format_copper(0), "0c")

    def test_a_sitting_is_one_session_line(self) -> None:
        # 2026-10-28: a link loss writes a session line and the QUIT that
        # ends the same sitting writes another counted from the same logon,
        # so the report listed the sitting twice.
        def row(at, name, how, secs, kills):
            return [str(at), "session", name, "50", "4207", "x.are", how,
                    f"{secs}s", "+0 levels", f"{kills} kills"]
        rows = [row(1000, "Zed", "linkdead", 900, 5),
                row(1100, "Amy", "quit", 50, 1),
                row(3900, "Zed", "quit", 3801, 5),
                row(9000, "Zed", "quit", 300, 2)]
        merged = self.report.merge_sittings(rows)
        self.assertEqual([(r[2], r[6], r[9]) for r in merged],
                         [("Amy", "quit", "1 kills"),
                          ("Zed", "linkdead > quit", "5 kills"),
                          ("Zed", "quit", "2 kills")])

    def test_a_quit_ends_its_sitting(self) -> None:
        # Review, 2026-10-30: quit, login, quit two seconds apart -- starts
        # 99 and 101 -- were merged into one "quit > quit".
        quick = [["100", "session", "Zjournal", "20", "4207", "limbo.are", "quit", "1s"],
                 ["102", "session", "Zjournal", "20", "4207", "limbo.are", "quit", "1s"]]
        self.assertEqual([r[6] for r in self.report.merge_sittings(quick)], ["quit", "quit"])

        def row(at, how, secs):
            return [str(at), "session", "Zjournal", "20", "4207", "limbo.are", how, f"{secs}s"]
        # A shutdown ends one too; link losses run on until the sitting ends.
        rows = [row(100, "shutdown", 50), row(101, "quit", 50),
                row(500, "linkdead", 100), row(900, "linkdead", 500),
                row(1000, "quit", 600), row(1001, "quit", 600)]
        self.assertEqual([r[6] for r in self.report.merge_sittings(rows)],
                         ["shutdown", "quit", "linkdead > linkdead > quit", "quit"])

    def test_the_same_event_is_one_line(self) -> None:
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 10, 22, tzinfo=timezone.utc)
        events = [(start + timedelta(minutes=10 * i),
                   f"Treasure goblin: vanished from room {1000 + i} (Room {i}, a{i}.are) "
                   "(too long in one area).") for i in range(30)]
        events.append((start, "Treasure goblin: slain by Zed in room 5 (Bog, b.are)."))
        groups = self.report.collapse_events(events)
        self.assertEqual(groups[0][0], 30)
        self.assertEqual(groups[0][1], start)
        self.assertEqual([g[0] for g in groups], [30, 1])

    def test_help_that_did_not_help(self) -> None:
        from datetime import datetime, timedelta, timezone
        t = datetime(2026, 10, 22, 11, 41, tzinfo=timezone.utc)
        lines = [(t, "Trentlin", "help heroquest"),
                 (t + timedelta(seconds=7), "Trentlin", "(refused) heroquest"),
                 (t + timedelta(seconds=9), "Trentlin", "(refused) heroquest request"),
                 (t, "Alaric", "help track"),
                 (t + timedelta(minutes=30), "Alaric", "(refused) track")]
        self.assertEqual(self.report.unhelpful_help(lines),
                         [(t + timedelta(seconds=7), "Trentlin", "heroquest")],
                         "once per reading, and only soon after it")

    def test_help_that_found_nothing(self) -> None:
        def row(topic, reply):
            return ["1", "cmd", "Zed", "5", "1", "a.are", "standing", "100", "0", "-",
                    "help", topic, reply]
        rows = [row("heroquest", "No help on that word."),
                row("'heroquest'", "No help on that word.  Did you mean: HERO?"),
                row("quest", "AQUEST QUEST QUESTING")]
        self.assertEqual(self.report.help_misses(rows), {"heroquest": 2})

    def test_repeats_in_a_fight_are_fighting(self) -> None:
        def row(epoch, command, fight="-", kind="cmd"):
            return [str(epoch), kind, "Zed", "50", "1", "a.are",
                    "fighting" if fight == "fight" else "standing", "100", "0", fight,
                    command, "", "ok"]
        rows = [row(i, "smite", "fight") for i in range(13)]
        rows += [row(100 + i, "mindbar") for i in range(6)]
        rows += [row(200 + i, "(unknown)", kind="refused") for i in range(6)]
        runs = self.report.journal_repeats(rows)
        self.assertEqual([(r[1], r[2]) for r in runs], [("mindbar", 6)])


if __name__ == "__main__":
    unittest.main()
