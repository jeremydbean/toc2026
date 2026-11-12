"""The Oracle's spools never hold the game, and lose nothing (review,
2026-11-12).

The game and the web process share four files in area/ under fcntl locks:
oracle.ask (questions out), oracle.answer (answers in), oracle.query and
oracle.queryresult (the live lookups). The game took the ask and result
locks with F_SETLKW, so a web process holding either held the whole game;
and it emptied oracle.query before it had opened oracle.queryresult, so a
result file that would not open lost the batch.

Each test here holds a lock or breaks a file the way the web process or the
disk might, and checks the game still answers at once, keeps what it could
not write, and writes it exactly once when the spool comes back. The lock
is taken from this process with fcntl.lockf, which is the same POSIX record
lock webadmin/oracle.py takes.
"""
import fcntl
import os
import tempfile
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, skip_reason

PW = "testpw12"
_SKIP = skip_reason()

# A command answered in the ordinary way comes back within a second or so;
# a game held by a lock does not come back at all until it is let go.
PROMPT_BOUND = 4.0


def lines_with(path: Path, needle: str) -> int:
    try:
        text = path.read_text(encoding="latin-1")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if needle in line)


def wait_for(fn, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return True
        time.sleep(0.2)
    return fn()


class Locked:
    """Hold the web process's lock on a spool file from this process."""

    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def __enter__(self):
        self.fh = open(self.path, "a+", encoding="latin-1")
        fcntl.lockf(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.lockf(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def timed_sync(test, client, line):
    started = time.monotonic()
    reply = client.sync(line, timeout=20)
    took = time.monotonic() - started
    test.assertLess(took, PROMPT_BOUND,
                    "%r took %.1fs: the game waited on a spool lock" % (line, took))
    return reply


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleAskSpool(unittest.TestCase):
    def test_busy_ask_spool_keeps_the_question_and_writes_it_once(self):
        with LiveMud() as mud:
            ask = mud.root / "area" / "oracle.ask"
            with mud.connect(timeout=120) as client:
                create_character(client, "Zspoolbusy", PW)
                self.assertIn("The Oracle's Sanctum", client.sync("pray"))
                self.assertTrue(wait_for(lambda: lines_with(ask, "\x01SITTING") == 1))

                with Locked(ask):
                    reply = timed_sync(self, client, "ask where is the zqbusy sword")
                    self.assertIn("considering your question", reply)
                    # Everything else goes on as usual while it is held.
                    for _ in range(3):
                        self.assertIn("Sanctum", timed_sync(self, client, "look"))
                    reply = timed_sync(self, client, "ask and the zqsecond shield")
                    self.assertIn("considering your question", reply)
                    # Long enough held for the game to say so in its log.
                    time.sleep(4.5)
                    self.assertEqual(lines_with(ask, "zqbusy"), 0,
                                     "written past the poller's lock")

                # Let go: both are written, in order, once each.
                self.assertTrue(wait_for(lambda: lines_with(ask, "zqsecond") == 1),
                                "the held question was never written")
                time.sleep(1.5)
                text = ask.read_text(encoding="latin-1")
                self.assertEqual(lines_with(ask, "zqbusy"), 1, "written twice or lost")
                self.assertEqual(lines_with(ask, "zqsecond"), 1)
                self.assertLess(text.index("zqbusy"), text.index("zqsecond"))
                for line in text.splitlines():
                    if "zqbusy" in line:
                        self.assertIn("\tABILITIES:", line)
                        self.assertIn("\tSTATE:room=", line)

                # Once the poller has taken them, nothing comes back.
                with Locked(ask) as held:
                    held.fh.truncate(0)
                time.sleep(1.5)
                self.assertEqual(lines_with(ask, "zqbusy"), 0)
                log = (mud.root / "log" / "toc.log").read_text(errors="replace")
                self.assertIn("the ask spool is locked by the poller", log)
                # The spool's own lines say how many, never what was asked.
                spool_lines = [line for line in log.splitlines()
                               if ":: Oracle: the ask spool" in line]
                self.assertTrue(spool_lines)
                self.assertFalse([line for line in spool_lines if "zq" in line])
                client.send("quit")

    def test_ask_spool_that_cannot_be_written_keeps_the_question(self):
        with LiveMud() as mud:
            ask = mud.root / "area" / "oracle.ask"
            with mud.connect(timeout=120) as client:
                create_character(client, "Zspoolbroke", PW)
                self.assertIn("The Oracle's Sanctum", client.sync("pray"))
                self.assertTrue(wait_for(lambda: lines_with(ask, "\x01SITTING") == 1))

                # The spool cannot be opened: a directory stands in its place.
                ask.unlink()
                ask.mkdir()
                reply = timed_sync(self, client, "ask what of the zqdir blade")
                self.assertIn("considering your question", reply)
                time.sleep(1.0)
                ask.rmdir()
                self.assertTrue(wait_for(lambda: lines_with(ask, "zqdir") == 1))

                # The spool opens but every write fails (a full disk).
                ask.unlink()
                os.symlink("/dev/full", ask)
                reply = timed_sync(self, client, "ask what of the zqfull helm")
                self.assertIn("considering your question", reply)
                self.assertIn("Sanctum", timed_sync(self, client, "look"))
                time.sleep(1.0)
                ask.unlink()
                self.assertTrue(wait_for(lambda: lines_with(ask, "zqfull") == 1),
                                "the question held over a failed write was lost")
                time.sleep(1.5)
                self.assertEqual(lines_with(ask, "zqfull"), 1)
                self.assertEqual(lines_with(ask, "zqdir"), 0,
                                 "an earlier record was written again")
                log = (mud.root / "log" / "toc.log").read_text(errors="replace")
                self.assertIn("the ask spool cannot be opened", log)
                self.assertIn("the ask spool could not be written", log)
                self.assertIn("the ask spool took", log)
                client.send("quit")

    def test_a_failed_save_does_not_send_the_question(self):
        """The poller reads the asker's gear from their file: a question
        whose save did not land would be answered for the old gear, so it is
        not sent, and the supplicant is told to ask again."""
        fault_dir = tempfile.TemporaryDirectory(prefix="toc-oracle-fault-")
        fault = Path(fault_dir.name) / "fault"
        try:
            with LiveMud(extra_env={"TOC_FAULT_FILE": str(fault)}) as mud:
                ask = mud.root / "area" / "oracle.ask"
                with mud.connect(timeout=120) as client:
                    create_character(client, "Zspoolsave", PW)
                    self.assertIn("The Oracle's Sanctum", client.sync("pray"))
                    fault.write_text("oracle-save\n")
                    reply = client.sync("ask where is the zqunsaved ring")
                    self.assertIn("mists are closed", reply)
                    self.assertNotIn("considering", reply)
                    self.assertFalse(fault.exists(), "the fault point was never asked")
                    reply = client.sync("ask where is the zqsaved ring")
                    self.assertIn("considering your question", reply)
                    self.assertTrue(wait_for(lambda: lines_with(ask, "zqsaved") == 1))
                    self.assertEqual(lines_with(ask, "zqunsaved"), 0)
                    client.send("quit")
        finally:
            fault_dir.cleanup()


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleLookupSpool(unittest.TestCase):
    def test_lookups_wait_for_their_result_file_and_are_answered_once(self):
        with LiveMud() as mud:
            area = mud.root / "area"
            query = area / "oracle.query"
            result = area / "oracle.queryresult"
            with mud.connect(timeout=120) as client:
                create_character(client, "Zspoollook", PW)

                # The poller holds the result file (it clears it under the
                # lock): the request waits in oracle.query.
                result.write_text("", encoding="latin-1")
                with Locked(result):
                    query.write_text("zr1\twho\tZspoollook\tall\n", encoding="latin-1")
                    for _ in range(3):
                        timed_sync(self, client, "look")
                    time.sleep(1.0)
                    self.assertEqual(lines_with(query, "zr1"), 1, "the request was lost")
                    self.assertEqual(lines_with(result, "zr1"), 0)
                self.assertTrue(wait_for(lambda: lines_with(result, "zr1") == 1))
                time.sleep(1.5)
                self.assertEqual(lines_with(result, "zr1"), 1, "answered twice")
                self.assertEqual(query.stat().st_size, 0)
                self.assertIn("Zspoollook", result.read_text(encoding="latin-1"))

                # The result file cannot be opened: the request is kept.
                result.unlink()
                result.mkdir()
                query.write_text("zr2\twho\tZspoollook\tall\n", encoding="latin-1")
                timed_sync(self, client, "look")
                time.sleep(1.0)
                self.assertEqual(lines_with(query, "zr2"), 1, "the request was lost")
                result.rmdir()
                self.assertTrue(wait_for(lambda: lines_with(result, "zr2") == 1))

                # The result file opens but takes no writes: kept, answered
                # once when it can be.
                result.unlink()
                os.symlink("/dev/full", result)
                query.write_text("zr3\twho\tZspoollook\tall\n", encoding="latin-1")
                timed_sync(self, client, "look")
                time.sleep(1.0)
                self.assertEqual(lines_with(query, "zr3"), 1, "the request was lost")
                result.unlink()
                self.assertTrue(wait_for(lambda: lines_with(result, "zr3") == 1))
                time.sleep(1.5)
                self.assertEqual(lines_with(result, "zr3"), 1, "answered twice")
                self.assertEqual(query.stat().st_size, 0)

                # A busy request file is simply tried again.
                with Locked(query) as held:
                    held.fh.write("zr4\twho\tZspoollook\tall\n")
                    held.fh.flush()
                    timed_sync(self, client, "look")
                    time.sleep(0.8)
                    self.assertEqual(lines_with(result, "zr4"), 0)
                self.assertTrue(wait_for(lambda: lines_with(result, "zr4") == 1))
                client.send("quit")


if __name__ == "__main__":
    unittest.main()
