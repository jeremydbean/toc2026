"""The play journal, the crash recorder and the anomaly checks (src/playlog.c).

Owner, 2026-10-21: "really advanced logging for players who play to help
identify potential bugs through gameplay". log/play.tsv holds one line per
command -- what was typed, what the game answered, how long it took -- plus
BUG lines with the command that was running, anomalies, session summaries
and BUG/TYPO/IDEA reports with the last few commands. log/crash.log gets
the last commands when the game crashes. log/ is public, so the private
commands' words and answers are never written, and an unknown word is
written alone.
"""
from __future__ import annotations

import os
import pathlib
import signal
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zplay1pass"
TEMPLE = 4207


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def rows(mud) -> list[list[str]]:
    path = mud.root / "log" / "play.tsv"
    if not path.exists():
        return []
    return [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]


class PlaylogSourceTests(unittest.TestCase):
    def test_every_command_passes_the_wrapper(self) -> None:
        interp = source("interp.c")
        self.assertIn("static void interpret_body( CHAR_DATA *ch, char *argument );", interp)
        self.assertEqual(interp.count("interpret_body( ch, argument );"), 2)
        self.assertIn('play_note( ch, "(unknown)", command, false, true );', interp,
                      "an unknown word is written alone")

    def test_private_words_are_never_journalled(self) -> None:
        interp = source("interp.c")
        self.assertIn("secret || command_is_private( cmd_table[cmd].name ), false );", interp)
        playlog = source("playlog.c")
        self.assertIn('secret ? "(withheld)" : reply', playlog)
        self.assertIn("room_hides_from_log( ch->in_room )", playlog)

    def test_bug_lines_say_what_was_running(self) -> None:
        db = source("db.c")
        bug = db[db.index("void bug( const char *str, int param )"):]
        bug = bug[:bug.index("\n}\n")]
        self.assertIn("playlog_bug_context( context, sizeof(context) );", bug)
        self.assertIn("playlog_bug(", bug)

    def test_the_crash_handler_is_signal_safe_and_spares_sanitizers(self) -> None:
        playlog = source("playlog.c")
        handler = playlog[playlog.index("static void crash_handler( int sig )"):]
        handler = handler[:handler.index("\n}\n")]
        for unsafe in ("printf", "fopen", "malloc", "log_string"):
            self.assertNotIn(unsafe, handler)
        self.assertIn("__SANITIZE_ADDRESS__", playlog)
        self.assertIn("playlog_boot( );", source("comm.c"))

    def test_the_hooks_are_wired(self) -> None:
        self.assertIn("playlog_tick( ch );", source("update.c"))
        self.assertIn('playlog_session( ch, "quit" );', source("act_comm.c"))
        self.assertIn("playlog_session( ch, shutting_down", source("comm.c"))
        for kind in ("bug", "typo", "idea"):
            self.assertIn('playlog_report( ch, "%s", argument );' % kind, source("act_comm.c"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PlaylogLiveTests(unittest.TestCase):
    def test_a_session_in_the_journal(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zplayer", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zplayer", Levl=10, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zplayer", PASSWORD)
                client.drain(1.0)
                for line in ("look", "frobnicate foo bar", "tell zplayer opensesame",
                             "score", "bug the fountain will not fill my skin"):
                    client.send(line)
                    client.drain(1.2)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            journal = rows(mud)
            text = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
            mine = [r for r in journal if len(r) > 2 and r[2] == "Zplayer"]
            by_cmd = {r[10]: r for r in mine if r[1] in ("cmd", "refused") and len(r) > 12}

            look = by_cmd["look"]
            self.assertEqual(look[4], str(TEMPLE))
            self.assertTrue(look[12], "what the game answered is recorded")
            self.assertTrue(look[8].isdigit(), "milliseconds")

            unknown = by_cmd["(unknown)"]
            self.assertEqual(unknown[1], "refused")
            self.assertNotIn("foo bar", text, "an unknown word is written alone")

            self.assertEqual(by_cmd["tell"][12], "(withheld)")
            self.assertNotIn("opensesame", text, "a tell's words never reach the journal")

            report = [r for r in mine if r[1] == "report"]
            self.assertEqual(report[0][6], "bug")
            self.assertIn("fountain", report[0][7])
            self.assertIn("score", report[0][9], "the last commands ride with the report")

            session = [r for r in mine if r[1] == "session"]
            # The last one: the first is the session that made the character.
            self.assertEqual(session[-1][6], "quit")
            commands = int(next(f for f in session[-1] if f.endswith(" commands")).split()[0])
            self.assertGreaterEqual(commands, 6, "five typed, and the QUIT itself")
            self.assertIn("1 refused", "\t".join(session[-1]))

    @unittest.skipIf(os.environ.get("TOC_SERVER_BINARY"),
                     "a sanitizer build reports crashes itself")
    def test_a_crash_leaves_the_last_commands(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcrash", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcrash", Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zcrash", PASSWORD)
                client.drain(1.0)
                client.send("look")
                client.drain(1.0)
                mud.proc.send_signal(signal.SIGSEGV)
                deadline = time.time() + 15
                while mud.proc.poll() is None and time.time() < deadline:
                    time.sleep(0.2)
            crash = (mud.root / "log" / "crash.log").read_text(encoding="latin-1")
        self.assertIn("=== crash: signal %d" % signal.SIGSEGV, crash)
        self.assertIn("Zcrash [%d] look" % TEMPLE, crash)
        self.assertIn("=== end ===", crash)


if __name__ == "__main__":
    unittest.main()
