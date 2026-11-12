"""The automatic seasonal restart, played live (owner, 2026-11-12).

Hallows End and Winter Veil swap dresden, limbo and midennir for their
decorated copies only at boot (season.c), so a world booted before one
starts kept the ordinary areas until somebody rebooted it. Now, when the
areas the world booted with disagree with the calendar, the game restarts
itself at 3am New York: a warning five minutes and one minute ahead,
every player saved, then REBOOT's ending -- no shutdown.txt, so whatever
runs the game starts it again.

These worlds take the date from TOC_DATE_FILE with TOC_SEASON unset, so
the calendar decides, and three test-only switches: any hour is 3am
(TOC_SEASON_REBOOT_ANYHOUR), the warning is seconds long
(TOC_SEASON_REBOOT_WARN_SECS) and the hour of uptime is waived
(TOC_SEASON_REBOOT_MIN_UPTIME). The tick's own saves are held off
(TOC_FAULT=autowrite), so the alias found in the file afterwards was
written by the restart's save.

* A world whose areas match the calendar does nothing.
* Turning the date to October 18 warns a connected player twice; an
  implementor's HOLIDAYS RESTART CANCEL calls it off and skips the night,
  and the warning time passes with the game still up; HOLIDAYS RESTART NOW
  is the creator's (REBOOT's rank), and starts it again.
* The restart saves the player, closes every connection and exits 0 with
  no shutdown.txt, and says so in the log.
* Booted again on October 18 the Hallows End copies load and nothing is
  scheduled; turned to November 2 the areas disagree again, but a game up
  less than an hour waits (the guard against restarting twice in a night).

The New York clock itself is tests/test_holiday_rules.c's.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zseasonpw1"
TEMPLE = 4207
WARN = 8


def make(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=TEMPLE)


def flat(text: str) -> str:
    return " ".join(text.split())


@unittest.skipIf(SKIP is not None, SKIP or "")
class SeasonRestartTests(unittest.TestCase):
    def test_the_world_restarts_for_the_season_and_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            date_file = Path(tmp) / "date"
            date_file.write_text("2026-10-10\n", encoding="ascii")
            env = {"TOC_SEASON": None, "TOC_DATE_FILE": str(date_file),
                   "TOC_SEASON_REBOOT_ANYHOUR": "1",
                   "TOC_SEASON_REBOOT_WARN_SECS": str(WARN),
                   "TOC_SEASON_REBOOT_MIN_UPTIME": "0",
                   "TOC_FAULT": "autowrite"}
            with LiveMud(extra_env=env) as mud:
                make(mud, "Killuminati", 70)
                make(mud, "Zseasonimp", 70)
                make(mud, "Zseasonplay", 20)

                creator = mud.connect(timeout=60)
                login(creator, "Killuminati", PW)
                imp = mud.connect(timeout=60)
                login(imp, "Zseasonimp", PW)
                player = mud.connect(timeout=60)
                login(player, "Zseasonplay", PW)

                # Matched: nothing scheduled, nothing said.
                status = flat(imp.sync("holidays"))
                self.assertIn("seasonal areas loaded at boot: the ordinary ones.", status)
                self.assertNotIn("the calendar wants", status)
                player.drain(3)
                self.assertIsNone(mud.proc.poll())
                self.assertNotIn("short restart", player.transcript.lower())

                # Something only a save puts in the file.
                player.sync("alias zqmark look")
                pfile = mud.player_dir / "Zseasonplay"
                self.assertNotIn("zqmark", pfile.read_text(encoding="latin-1"))

                marker = mud.root / "area" / "shutdown.txt"
                marked = marker.read_bytes() if marker.exists() else None

                # The calendar turns: Hallows End.
                date_file.write_text("2026-10-18\n", encoding="ascii")
                player.expect(f"the world changes for hallows end: a short restart in "
                              f"{WARN} seconds", timeout=20)
                status = flat(imp.sync("holidays"))
                self.assertIn("seasonal areas loaded at boot: the ordinary ones; the calendar "
                              "wants Hallows End; an automatic restart is due at 3am New York.",
                              status)
                self.assertIn("the restart is under way", status)
                imp.must("holidays restart now", "Only REBOOT's rank")
                imp.must("holidays restart cancel", "called off")
                player.expect("the restart is called off", timeout=10)

                # Called off for the night: the warning time passes, the game stays.
                player.drain(WARN + 3)
                self.assertIsNone(mud.proc.poll(), mud.server_output())
                self.assertIn("staff called tonight's restart off", flat(imp.sync("holidays")))

                # The creator starts it again.
                creator.must("holidays restart now", "under way")
                player.expect(f"a short restart in {WARN} seconds", timeout=10)
                player.expect("a short restart in", timeout=10)    # the last warning
                self.assertTrue(player.wait_closed(30), "the restart did not close the player")
                self.assertEqual(mud.proc.wait(timeout=60), 0, mud.server_output())

                # git tracks an old area/shutdown.txt, so the copied world has
                # one; SHUTDOWN appends to it, and the restart must not.
                self.assertEqual(marker.read_bytes() if marker.exists() else None, marked,
                                 "a seasonal restart is a reboot, not a shutdown")
                output = mud.server_output()
                self.assertIn("Seasonal restart: saving every player and restarting for "
                              "Hallows End (a reboot: no shutdown.txt).", output)
                self.assertIn("Alias zqmark look", pfile.read_text(encoding="latin-1"),
                              "the restart did not save the player")

                # Booted again on Oct 18: Hallows End's areas, nothing to do;
                # and the default hour of uptime.
                mud.extra_env["TOC_SEASON_REBOOT_MIN_UPTIME"] = None
                mud.restart()
                imp = mud.connect(timeout=60)
                login(imp, "Zseasonimp", PW)
                player = mud.connect(timeout=60)
                login(player, "Zseasonplay", PW)
                status = flat(imp.sync("holidays"))
                self.assertIn("seasonal areas loaded at boot: Hallows End.", status)
                imp.must("holidays restart cancel", "Nothing to call off")

                # Nov 2: the areas disagree again, but the game is not an hour old.
                date_file.write_text("2026-11-02\n", encoding="ascii")
                player.drain(4)
                status = flat(imp.sync("holidays"))
                self.assertIn("the calendar wants the ordinary ones", status)
                self.assertIn("the game has been up less than 60 minutes", status)
                self.assertIsNone(mud.proc.poll())
                self.assertNotIn("short restart", player.transcript.lower())


if __name__ == "__main__":
    unittest.main()
