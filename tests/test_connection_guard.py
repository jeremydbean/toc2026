"""Host names off the game loop, and the connection guard (2026-11-06).

The play journal's stall rows lined up with every outside connection:
new_descriptor's getnameinfo blocked the single-threaded game for as long
as the resolver took, up to half a second each, and nearly every one was a
scanner that hung up at once. Lookups run on a worker thread now
(src/dnsasync.c), only for a connection that sends a line, and the answer
replaces the address when it comes.

The connection guard (src/connguard.c): an address no player has logged in
from in the last 90 days is blocked after repeated connections; one a
player has logged in from never is; a login prompt left untouched is closed.

The guard ignores loopback unless TOC_GUARD_LOOPBACK=1, and the resolver
looks loopback up only with TOC_DNS_LOOPBACK=1, so these tests switch both
on; TOC_GUARD_STRIKES, TOC_DNS_DELAY_MS and TOC_LOGIN_IDLE_SECS make the
limits small and the resolver slow enough to see.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zguardpw1"


class GuardSourceTests(unittest.TestCase):
    def test_no_lookup_on_the_game_loop(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        accept = comm.split("DESCRIPTOR_DATA *new_descriptor(int control) {", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("getnameinfo(", accept, "accept never waits on a resolver")
        self.assertIn("dns_async_submit", comm)
        collect = comm.split("static void dns_collect( void )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("check_ban( d->host, BAN_ALL )", collect, "a host-name ban is asked again")
        self.assertIn("host_name_clean( host )", collect)
        loop = comm.split("void game_loop_unix( int control )", 1)[1]
        self.assertLess(loop.index("dns_collect( );"), loop.index("update_handler( );"))
        self.assertIn("login_idle_sweep( );", loop)
        # Players' addresses are trusted at both kinds of login.
        self.assertIn("conn_guard_trust( d->ip );", comm.split("static void login_note_success", 1)[1])
        self.assertEqual(comm.count("conn_guard_trust( d->ip )"), 2)

    def test_both_builds_know_the_new_files(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        self.assertIn("src/dnsasync.c", cmake)
        self.assertIn("src/connguard.c", cmake)
        self.assertIn("Threads::Threads", cmake)
        self.assertIn("-pthread", (ROOT / "Makefile").read_text())


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardLiveTests(unittest.TestCase):
    def test_an_address_no_player_uses_is_blocked(self) -> None:
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_STRIKES": "3"}
        with LiveMud(extra_env=env) as mud:
            greeted = refused = 0
            for _ in range(6):
                with mud.connect(timeout=30) as probe:
                    got = probe.expect("by what name", "name:", "paused", timeout=20)
                    if "paused" in got.lower():
                        refused += 1
                        self.assertTrue(probe.wait_closed(), "a refused connection is closed")
                    else:
                        greeted += 1
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertGreaterEqual(greeted, 1)
        self.assertGreaterEqual(refused, 3, "blocked, and it stays blocked")
        self.assertRegex(log, r"Connection guard: 127\.0\.0\.1 blocked for 6 hours")
        # A connection that never said a word is not logged one by one.
        self.assertNotIn("EOF encountered on read.", log)

    def test_a_player_address_is_never_blocked(self) -> None:
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_STRIKES": "3"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zguarded", Levl=70)       # a new player trusts the address
            for _ in range(8):
                with mud.connect(timeout=30) as probe:
                    got = probe.expect("by what name", "name:", "paused", timeout=20)
                    self.assertNotIn("paused", got.lower(), got)
            with mud.connect(timeout=60) as client:
                login(client, "Zguarded", PW)
                self.assertIn("Connection guard", client.must("dns guard", "Connection guard"))
            trusted = (mud.root / "log" / "player_addresses.tsv").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertRegex(trusted, r"(?m)^127\.0\.0\.1\t\d+$")
        self.assertNotIn("Connection guard: 127.0.0.1 blocked", log)

    def test_a_lookup_never_holds_the_game(self) -> None:
        env = {"TOC_DNS_LOOPBACK": "1", "TOC_DNS_DELAY_MS": "3000"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zdnsstaff", Levl=70)
            with mud.connect(timeout=60) as staff:
                login(staff, "Zdnsstaff", PW)
                staff.sync("scroll 0")
                time.sleep(3.5)                  # the staff's own lookup is done
                with mud.connect(timeout=30) as other:
                    other.expect("by what name", "name:")
                    other.send("Zlookup")        # a line: now it is looked up
                    other.expect("right", "Did I get", timeout=20)
                    started = time.monotonic()
                    staff.must("dns", "Hostname lookups")   # never sync the barrier itself
                    took = time.monotonic() - started
                    self.assertLess(took, 1.5, "the game answered while the resolver slept")
                    host = None
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        listed = staff.must("dns list", "Connected descriptors")
                        row = re.search(r"Zlookup\s+(\S+)\s+127\.0\.0\.1", listed)
                        if row and row.group(1) != "127.0.0.1":
                            host = row.group(1)
                            break
                        time.sleep(1)
                    self.assertIsNotNone(host, "the name came back and replaced the address")

    def test_a_login_prompt_left_alone_is_closed(self) -> None:
        with LiveMud(extra_env={"TOC_LOGIN_IDLE_SECS": "3"}) as mud:
            with mud.connect(timeout=30) as idle:
                idle.expect("by what name", "name:")
                self.assertTrue(idle.wait_closed(timeout=20), "closed for idling at the prompt")
                self.assertIn("Nothing typed for a while", idle.transcript)


if __name__ == "__main__":
    unittest.main()
