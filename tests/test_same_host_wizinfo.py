"""Staff are told when a character arrives from an address already in play.

Reported missing: wizinfo used to say when players were on from the same
IP. It did -- Ricochet's code from 1998, on connect and on reconnect --
and it went in the November 2025 rewrite of comm.c. It is back, naming
the characters rather than only counting them, and comparing addresses
exactly where the original's strstr() matched 1.2.3.4 against 1.2.3.45.

The live test claims addresses with a PROXY header, exactly as the web
dashboard's bridge does, because every test connection is loopback and
loopback is deliberately never reported.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason  # noqa: E402

SKIP = skip_reason()
PASSWORD = "samehost"


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class SameHostSourceTests(unittest.TestCase):
    def test_it_runs_on_connect_and_on_reconnect(self) -> None:
        comm = read("src", "comm.c")
        self.assertEqual(2, comm.count("wizinfo_same_host( d, ch );"))
        body = comm.split("static void wizinfo_same_host( DESCRIPTOR_DATA *d", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("str_cmp( od->host, d->host )", body)
        self.assertNotIn("strstr", body)
        self.assertIn('!str_prefix( "127.", d->host )', body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SameHostLiveTests(unittest.TestCase):
    def test_staff_are_told_who_shares_an_address(self) -> None:
        with LiveMud() as mud:
            for name in ("Zhostimm", "Zhostone", "Zhosttwo", "Zhostfar"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zhostimm", Levl=70)

            with mud.connect(timeout=200) as staff, \
                    mud.connect(timeout=200) as one, \
                    mud.connect(timeout=200) as two, \
                    mud.connect(timeout=200) as far:
                login(staff, "Zhostimm", PASSWORD)
                staff.drain(1.0)

                one.send(f"PROXY TCP4 203.0.113.9 127.0.0.1 51000 {mud.port}")
                login(one, "Zhostone", PASSWORD)
                first = staff.drain(2.0)
                self.assertIn("Zhostone@203.0.113.9 has connected", first)
                self.assertNotIn("shares an address", first,
                                 "nobody else was on from there yet")

                two.send(f"PROXY TCP4 203.0.113.9 127.0.0.1 51001 {mud.port}")
                login(two, "Zhosttwo", PASSWORD)
                second = staff.drain(2.0)
                self.assertIn(
                    "Zhosttwo shares an address with Zhostone: "
                    "2 players on from 203.0.113.9.", second)

                # A different address -- including one that merely starts
                # with the same digits -- is nobody's business.
                far.send(f"PROXY TCP4 203.0.113.90 127.0.0.1 51002 {mud.port}")
                login(far, "Zhostfar", PASSWORD)
                third = staff.drain(2.0)
                self.assertIn("Zhostfar@203.0.113.90 has connected", third)
                self.assertNotIn("Zhostfar shares an address", third)

                for client in (staff, one, two, far):
                    client.send("quit")


if __name__ == "__main__":
    unittest.main()
