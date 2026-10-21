"""The review tools: tools/audit_players.py and tools/log_report.py.

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

    def test_a_word_refused_once_is_not_printed(self) -> None:
        source = (ROOT / "tools" / "log_report.py").read_text(encoding="utf-8")
        self.assertIn("if 2 <= n < 50", source, "a password typed by mistake is refused once")

    def test_watch_log_events_are_not_commands(self) -> None:
        for event in ("coin +4 platinum", "gold -250", "bought a pie (vnum 3009) for 1 copper",
                      "(social) smile", "stashed a sword"):
            self.assertTrue(self.report.EVENT_LINE.match(event), event)
        for command in ("smite", "get all", "goto 4207", "golem"):
            self.assertFalse(self.report.EVENT_LINE.match(command), command)


if __name__ == "__main__":
    unittest.main()
