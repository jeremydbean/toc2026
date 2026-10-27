"""The game's HELP and the Python reader pick the same page (2026-10-27).

The website, the Oracle and tools/help_audit.py read the help through
webadmin/help_index.py.  This plays HELP against a real server, as a mortal
and as staff, and checks every answer is the page help_index.lookup names:
quoted phrases (HELP STONE SKIN), a header that wraps a line, the
staff/public splits that depend on trust, the group query and the guards.
Synthetic Z characters in a disposable world only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))
import help_index  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zhelplive1"

# A built area holding only help, whose header wraps a line: the game reads
# it as one keyword string, newline and all, and must still find each word.
WRAPPED = ("#HELPS\n0 ZWRAPFIRST\nZWRAPSECOND 'ZWRAP PHRASE'~\n"
           "Wrapped header fixture.\n~\n0 $~\n\n#$\n")

MORTAL_TOPICS = ["stone skin", "major globe", "colour spray", "color spray",
                 "astral walk", "astral", "ego whip", "dual wield", "secondary",
                 "farslay", "scroll of farslay", "goblin", "invis", "teleport",
                 "rules", "story", "qui", "say", "unalias", "blow", "weather",
                 "weather group", "empower", "vengeance", "track", "zwrapsecond",
                 "zwrap phrase", "zwrapfirst"]
STAFF_TOPICS = ["farslay", "goblin", "invis", "teleport", "teleportspell",
                "empower", "empower spell", "sla", "newcorpse", "oracleadmin",
                "diagnostics", "wizinfo", "wizinvis"]


def first_line(entry: help_index.HelpEntry) -> str:
    return next(line.strip() for line in entry.text.split("\n") if line.strip())


@unittest.skipIf(SKIP is not None, SKIP or "")
class HelpParityTests(unittest.TestCase):
    def check(self, client, entries, topic: str, trust: int) -> None:
        reply = client.sync("help " + topic, timeout=60)
        entry = help_index.lookup(entries, topic, trust)
        self.assertIsNotNone(entry, topic)
        if entry.level >= 0:
            # do_help prints the keyword string before the body.
            self.assertIn(entry.keyword, reply, "HELP %s at trust %d" % (topic, trust))
        self.assertIn(first_line(entry), reply, "HELP %s at trust %d" % (topic, trust))

    def test_native_help_matches_the_reader(self) -> None:
        with LiveMud() as mud:
            for name in ("Zhelpmort", "Zhelpstaff"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zhelpmort", Levl=10)
            patch_player_file(mud, "Zhelpstaff", Levl=70)

            built = mud.root / "area" / "built"
            built.mkdir(exist_ok=True)
            (built / "zhelpwrap.are").write_text(WRAPPED, encoding="latin-1")
            listing = built / "built.lst"
            lines = [line for line in (listing.read_text().split() if listing.exists() else [])
                     if line != "$"]
            listing.write_text("\n".join(lines + ["built/zhelpwrap.are", "$"]) + "\n")
            mud.restart()

            entries = help_index.load_helps(mud.root / "area")
            self.assertTrue(any(e.keyword == "ZWRAPFIRST ZWRAPSECOND 'ZWRAP PHRASE'"
                                for e in entries))

            with mud.connect(timeout=120) as mortal:
                login(mortal, "Zhelpmort", PASSWORD)
                mortal.sync("scroll 0")
                for topic in MORTAL_TOPICS:
                    self.check(mortal, entries, topic, 10)
                group = mortal.sync("help group weather")
                self.assertIn("Weather is a group of abilities:", group, group)
                self.assertIn("lightning bolt", group, group)
                # QUI is QUIET, as HELP QUIT now says; QUIT is typed in full.
                self.assertIn("only hear says and emotes", mortal.sync("qui"))
                self.assertIn("Quiet mode removed", mortal.sync("quiet"))
                # A staff page is never shown below its level.
                self.assertNotIn("oracle ban", mortal.sync("help oracleadmin"))

                # Paging on: a long page stops at the pager, and a blank
                # line brings the rest.
                # The pager takes the next line typed as its return, so this
                # is sent and listened for, not synced.
                mortal.sync("scroll 10")
                mortal.send("help psionics")
                mortal.expect("[Hit Return to continue]")
                for _ in range(6):
                    mortal.send("")
                    if mortal.expect("[Hit Return to continue]",
                                     "See also: REMORT, SALIR, PRACTICE") != "[Hit Return to continue]":
                        break
                else:
                    self.fail("HELP PSIONICS never reached its end through the pager")

            with mud.connect(timeout=120) as staff:
                login(staff, "Zhelpstaff", PASSWORD)
                staff.sync("scroll 0")
                for topic in STAFF_TOPICS:
                    self.check(staff, entries, topic, 70)
                self.assertIn("If you want to SLAY, spell it out.", staff.sync("sla"))


if __name__ == "__main__":
    unittest.main()
