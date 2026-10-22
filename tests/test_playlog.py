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
QUESTMASTER = 2497        # Questor Thews, top of the Oak Tree


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
        self.assertIn("privacy != LINE_PUBLIC, false );", interp)
        # ALIAS bodies hold any command, and AT/FORCE/ORDER carry one.
        self.assertIn('"remort", "alias", NULL', interp)
        for wrapper in ('"at"', '"force"', '"order"'):
            self.assertIn(wrapper, interp[interp.index("static int line_privacy("):])
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
                             "alias zpriv tell zplayer aliasmarker",
                             "alias zpriv", "zpriv",
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
            # Audit 2026-10-21: an alias's body -- defined, shown or run --
            # reached the journal and the watch log.
            self.assertEqual(by_cmd["alias"][12], "(withheld)")
            for sink in (text,
                         (mud.root / "log" / "toc.log").read_text(encoding="latin-1"),
                         mud.server_output()):
                self.assertNotIn("aliasmarker", sink)

            report = [r for r in mine if r[1] == "report"]
            self.assertEqual(report[0][6], "bug")
            self.assertIn("fountain", report[0][7])
            self.assertIn("score", report[0][9], "the last commands ride with the report")

            session = [r for r in mine if r[1] == "session"]
            # The last one: the first is the session that made the character.
            self.assertEqual(session[-1][6], "quit")
            commands = int(next(f for f in session[-1] if f.endswith(" commands")).split()[0])
            self.assertGreaterEqual(commands, 9, "eight typed, and the QUIT itself")
            self.assertIn("1 refused", "\t".join(session[-1]))

    def test_replies_coin_sources_and_quests(self) -> None:
        """What the 2026-10-22 review could not see from the logs: SCORE's
        answer past its first line, where a session's coin came from, and
        which quest the quest master handed out."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcoiner", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcoiner", Levl=10, Room=QUESTMASTER, NewGold=20)

            with mud.connect(timeout=120) as client:
                login(client, "Zcoiner", PASSWORD)
                client.drain(1.0)
                for line in ("score", "drop 5 gold", "get gold", "aquest request"):
                    client.send(line)
                    client.drain(1.5)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            mine = [r for r in rows(mud) if len(r) > 2 and r[2] == "Zcoiner"]
            score = next(r for r in mine if r[1] == "cmd" and r[10] == "score")
            self.assertEqual(score[12].count(" // "), 2, "SCORE's first three lines")
            self.assertNotIn("----", score[12], "a rule says nothing and is skipped")

            session = [r for r in mine if r[1] == "session"][-1]
            coin = next(f for f in session if f.startswith("coin: "))
            self.assertIn("loot 5g", coin, "coin picked up is loot")
            self.assertIn("spent 5g", coin, "coin dropped is spent")

            watch = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertRegex(watch, r"Log Zcoiner \[\d+\]: quest assigned: (kill|recover) .+ "
                                    r"in \S+\.are, \d+ minutes?, (ordinary|rush|emergency)")

    def test_reading_tells_back_publishes_nothing(self) -> None:
        """Audit 2026-10-22: HISTORY and REPLAY were public commands, and
        the journal keeps three lines of an answer, so the text of a tell
        another player sent reached log/play.tsv -- published every five
        minutes -- the moment its receiver read it back."""
        with LiveMud() as mud:
            for name in ("Zteller", "Zhearer"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=10, Room=TEMPLE)

            with mud.connect(timeout=120) as hearer, mud.connect(timeout=120) as teller:
                login(hearer, "Zhearer", PASSWORD)
                login(teller, "Zteller", PASSWORD)
                hearer.drain(1.0)
                teller.send("tell zhearer zebrasecretword")
                teller.drain(1.5)
                for line in ("history tell", "history", "replay"):
                    hearer.send(line)
                    hearer.drain(1.5)
                self.assertIn("zebrasecretword", hearer.transcript, "the tell did arrive")
                for client in (hearer, teller):
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            journal = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
            self.assertNotIn("zebrasecretword", journal)
            self.assertNotIn("zebrasecretword",
                             (mud.root / "log" / "toc.log").read_text(encoding="latin-1"))
            read_back = [r for r in rows(mud) if len(r) > 12 and r[2] == "Zhearer"
                         and r[10] in ("history", "replay")]
            self.assertEqual(len(read_back), 3, read_back)
            for row in read_back:
                self.assertEqual(row[12], "(withheld)", row)

    def test_a_note_to_one_person_stays_private(self) -> None:
        """Audit lead 2026-10-22: NOTE was public, so a note's subject and
        every line of its body reached toc.log and the journal as they
        were typed, and NOTE LIST put the subject in the reader's row --
        mail to one person, published every five minutes."""
        with LiveMud() as mud:
            for name in ("Zwriter", "Zreader"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as writer:
                login(writer, "Zwriter", PASSWORD)
                for line in ("note to zreader", "note subject zsecretsubject",
                             "note + zebrabodytext", "note send"):
                    writer.send(line)
                    writer.drain(1.2)
                writer.send("quit")
                self.assertTrue(writer.wait_closed())
            with mud.connect(timeout=120) as reader:
                login(reader, "Zreader", PASSWORD)
                for line in ("note list", "note read 1"):
                    reader.send(line)
                    reader.drain(1.5)
                self.assertIn("zebrabodytext", reader.transcript, "the note arrived")
                reader.send("quit")
                self.assertTrue(reader.wait_closed())
            for sink in ((mud.root / "log" / "play.tsv").read_text(encoding="latin-1"),
                         (mud.root / "log" / "toc.log").read_text(encoding="latin-1")):
                for word in ("zsecretsubject", "zebrabodytext"):
                    self.assertNotIn(word, sink)

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
