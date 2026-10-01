"""The reconnect notice tells players to type REPLAY, so it must exist.

REPLAY was a stub that was never registered, yet close_socket's
reconnect message says "Type replay to see missed tells." do_replay
forwards to do_history; this pins that the command is registered and
that the notice and the table agree.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*p):
    return ROOT.joinpath(*p).read_text(encoding="latin-1")


class ReplayCommandTests(unittest.TestCase):
    def test_replay_is_registered_and_forwards_to_history(self):
        interp = read("src", "interp.c")
        self.assertRegex(interp, r'\{\s*"replay",\s*do_replay\b')
        comm = read("src", "act_comm.c")
        body = comm[comm.index("void do_replay"):]
        body = body[:body.index("\n}")]
        self.assertIn("do_history(", body)

    def test_the_reconnect_notice_names_a_real_command(self):
        comm = read("src", "comm.c")
        self.assertIn("Type replay", comm)
        self.assertRegex(read("src", "interp.c"), r'"replay"')


if __name__ == "__main__":
    unittest.main()
