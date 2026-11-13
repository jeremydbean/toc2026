"""Host names off the game loop, and the connection guard (2026-11-06).

The play journal's stall rows lined up with every outside connection:
new_descriptor's getnameinfo blocked the single-threaded game for as long
as the resolver took, up to half a second each, and nearly every one was a
scanner that hung up at once. Lookups run on a worker thread now
(src/dnsasync.c), only for a connection that sends a line, and the answer
replaces the address when it comes.

The connection guard (src/connguard.c): an address no player has logged in
from in the last 90 days is paused after repeated connections that reach no
password prompt, and a paused or flooding address is reset at connect with
no reply (owner, 2026-11-13). Pauses, their history and the strikes behind
them survive a restart (log/guard_pauses.tsv), and every connection that
goes nowhere is logged with its address. One a player has logged in from
is never held back; a login prompt left untouched is
closed, and that close, an MSSP poll and a web-bridge connection are never
strikes. Staff hear of each as WIZINFO.

The guard ignores loopback unless TOC_GUARD_LOOPBACK=1, and the resolver
looks loopback up only with TOC_DNS_LOOPBACK=1, so these tests switch both
on; TOC_GUARD_STRIKES, TOC_GUARD_FLOOD, TOC_DNS_DELAY_MS and
TOC_LOGIN_IDLE_SECS make the limits small and the resolver slow enough to
see.
"""
from __future__ import annotations

import re
import socket
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
        self.assertIn("check_ban( d, BAN_ALL )", collect, "a host-name ban is asked again")
        self.assertIn("host_name_clean( host )", collect)
        loop = comm.split("void game_loop_unix( int control )", 1)[1]
        self.assertLess(loop.index("dns_collect( );"), loop.index("update_handler( );"))
        self.assertIn("login_idle_sweep( );", loop)
        # Players' addresses are trusted at both kinds of login.
        self.assertIn("conn_guard_trust( &d->addr, why, staff_notice_level( who, LEVEL_IMMORTAL ) );",
                      comm.split("static void login_note_success", 1)[1])
        self.assertIn("conn_guard_trust( &d->addr, who, staff_notice_level( ch, LEVEL_IMMORTAL ) );", comm)
        # A login is noted only once it is one: after every check, and
        # after a creator is made unseen (review of f1388da0).
        password = comm.split("case CON_GET_OLD_PASSWORD:", 1)[1].split("case CON_BREAK_CONNECT:", 1)[0]
        self.assertLess(password.index("login_password_current( ch->name, argument )"),
                        password.index("check_playing(d,ch->name)"))
        self.assertLess(password.index("login_reload_character( d, argument )"),
                        password.rindex("login_note_success( d );"))
        self.assertLess(password.index("creator_arrives_unseen( ch );"),
                        password.rindex("login_note_success( d );"))

    def test_what_is_never_a_strike(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        sweep = comm.split("static void login_idle_sweep( void )", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(sweep.index("d->guard_idle_closed = TRUE;"), sweep.index("close_socket( d );"))
        self.assertIn("d->guard_proxied = TRUE;", comm)
        telnet = (ROOT / "src" / "telnet_proto.c").read_text(encoding="latin-1")
        mssp = telnet.split("static void telnet_send_mssp( DESCRIPTOR_DATA *d )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("d->guard_mssp = TRUE;", mssp)
        guard = (ROOT / "src" / "connguard.c").read_text(encoding="latin-1")
        closed = guard.split("void conn_guard_closed( DESCRIPTOR_DATA *d )", 1)[1].split("\n}\n", 1)[0]
        for flag in ("guard_named", "guard_idle_closed", "guard_mssp", "guard_proxied"):
            self.assertIn(f"d->{flag}", closed)
        # Both password prompts mark a connection as having got somewhere.
        self.assertEqual(comm.count("d->guard_named = TRUE;"), 2)

    def test_staff_hear_of_it(self) -> None:
        guard = (ROOT / "src" / "connguard.c").read_text(encoding="latin-1")
        say = guard.split("static void guard_say( const char *text, int level )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("wizinfo( text, UMAX( level, LEVEL_IMMORTAL ) );", say)
        for fn in ("static void guard_block(", "const char *conn_guard_admit(",
                   "const char *conn_guard_new_char(", "void conn_guard_trust("):
            body = guard.split(fn, 1)[1].split("\n}\n", 1)[0]
            self.assertIn("guard_say( ", body, fn)
        tick = guard.split("void conn_guard_tick( void )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("wizinfo( buf, LEVEL_IMMORTAL );", tick)

    def test_both_builds_know_the_new_files(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        self.assertIn("src/dnsasync.c", cmake)
        self.assertIn("src/connguard.c", cmake)
        self.assertIn("Threads::Threads", cmake)
        self.assertIn("-pthread", (ROOT / "Makefile").read_text())


def wait_for_log(mud: LiveMud, text: str, timeout: float = 15.0) -> bool:
    """The server notices a close on its next pulse; wait for the line."""
    path = mud.root / "log" / "toc.log"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and text in path.read_text(encoding="latin-1"):
            return True
        time.sleep(0.25)
    return False


def forget_player_addresses(mud: LiveMud) -> None:
    """An empty record: the file is the record once it exists, so the
    journals (which hold this world's logins from 127.0.0.1) are not read
    to start it again."""
    (mud.root / "log" / "player_addresses.tsv").write_text("# empty\n", encoding="latin-1")


def ctime(when: float) -> str:
    """toc.log's own time stamp."""
    return time.strftime("%a %b %e %H:%M:%S %Y", time.localtime(when))


def greets(mud: LiveMud) -> bool:
    """Whether a connection is greeted: True on the greeting, False when the
    game closes or resets it having said nothing at all."""
    with socket.create_connection(("127.0.0.1", mud.port), timeout=10) as sock:
        sock.settimeout(10)
        got = b""
        try:
            while b"name" not in got.lower():
                chunk = sock.recv(4096)
                if not chunk:
                    break
                got += chunk
        except ConnectionResetError:
            pass
        if got and b"name" not in got.lower():
            raise AssertionError(f"a refused connection was told something: {got!r}")
        return b"name" in got.lower()


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardLiveTests(unittest.TestCase):
    def test_a_paused_address_is_refused_silently_and_remembered(self) -> None:
        """Owner, 2026-11-13: a paused address is refused at connect with no
        reply, every connection that goes nowhere is logged by address with
        its strike, and a restart forgets nothing."""
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_STRIKES": "3"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zguardold", Levl=70)
            # Forget that a player came from here: a new ISP, say.
            mud._stop()
            forget_player_addresses(mud)
            mud._launch()

            for _ in range(3):                   # three that go nowhere
                with mud.connect(timeout=30) as probe:
                    probe.expect("by what name", "name:", timeout=20)
            self.assertTrue(wait_for_log(mud, "Connection guard: 127.0.0.1 paused for 6 hours"))
            self.assertFalse(greets(mud), "a paused address is not greeted")
            self.assertFalse(greets(mud), "nor the next time")
            self.assertTrue(wait_for_log(mud, "Connection guard: refused 1 connection from 127.0.0.1 (paused"))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            kept = (mud.root / "log" / "guard_pauses.tsv").read_text(encoding="latin-1")

            # A restart remembers the pause.
            mud._stop()
            mud._launch()
            self.assertTrue(wait_for_log(mud, "remembered from before the boot, 1 paused now"))
            self.assertFalse(greets(mud), "the pause outlives a restart")

            # A player's address is never refused, even with a pause on file.
            mud._stop()
            (mud.root / "log" / "player_addresses.tsv").write_text(
                f"127.0.0.1\t{int(time.time())}\n", encoding="latin-1")
            mud._launch()
            self.assertTrue(greets(mud), "a player's address is greeted")
        for strike in (1, 2, 3):
            self.assertIn(f"Connection guard: 127.0.0.1 closed without a word "
                          f"(strike {strike} of 3 in 6 hours).", log)
        self.assertIn("Its connections are refused until then.", log)
        self.assertRegex(kept, r"(?m)^127\.0\.0\.1\t\d+\t1\t\d+\t0\t\d+\t0\t\d+$")
        self.assertNotIn("EOF encountered on read.", log)

    def test_the_record_starts_once_from_logins_that_name_an_address(self) -> None:
        with LiveMud() as mud:
            mud._stop()
            now = time.time()
            log = mud.root / "log"
            (log / "player_addresses.tsv").unlink(missing_ok=True)
            (log / "logins.tsv").write_text(
                f"{int(now) - 600}\tZed\t203.0.113.50\tconnect\n"        # an address: trusted
                f"{int(now) - 500}\tZed\thost.example.net\tconnect\n"    # a name: nothing
                f"{int(now) - 400}\tZed\t203.0.113.51\tquit\t60\n",      # a logout: nothing
                encoding="latin-1")
            # Two connections interleave before a login by host name, and a
            # login that names its own address comes later: only that one.
            with (log / "toc.log").open("a", encoding="latin-1") as fp:
                fp.write(f"{ctime(now - 300)} :: Sock.sinaddr:  198.51.100.60\n"
                         f"{ctime(now - 299)} :: Sock.sinaddr:  198.51.100.61\n"
                         f"{ctime(now - 290)} :: Zed@host.example.net has connected.\n"
                         f"{ctime(now - 200)} :: Zed@198.51.100.62 has connected.\n")
            mud._launch()
            with mud.connect(timeout=30) as probe:           # the boot is done
                probe.expect("by what name", "name:")
            record = (log / "player_addresses.tsv").read_text(encoding="latin-1")
            addresses = {line.split("\t")[0] for line in record.splitlines()
                         if line and not line.startswith("#")}
            self.assertEqual(addresses, {"203.0.113.50", "198.51.100.62"}, record)

            # Once the record exists it is the record: the journals are not
            # read again, and a restart keeps what it holds.
            mud._stop()
            with (log / "logins.tsv").open("a", encoding="latin-1") as fp:
                fp.write(f"{int(now)}\tZed\t203.0.113.70\tconnect\n")
            mud._launch()
            with mud.connect(timeout=30) as probe:
                probe.expect("by what name", "name:")
            again = (log / "player_addresses.tsv").read_text(encoding="latin-1")
            self.assertNotIn("203.0.113.70", again)
            self.assertIn("198.51.100.62\t", again)

    def test_a_rejected_login_trusts_nothing(self) -> None:
        """Review of f1388da0: a login checked against the copy loaded at the
        name prompt trusted its address before the file -- with a password
        changed meanwhile -- refused it. And while the character was still in
        the game, "connect anyway" took over with the old password."""
        with LiveMud() as mud:
            make(mud, "Zorderhero")
            log = mud.root / "log"

            def stale_attempt(address: str, port: int):
                b = mud.connect(timeout=60)
                b.send(f"PROXY TCP4 {address} 127.0.0.1 {port} {mud.port}")
                b.expect("by what name", "name:")
                b.expect("Name:", timeout=20)
                b.send("Zorderhero")
                b.expect("Password", timeout=20)
                return b

            # A changes the password and quits while B waits at the prompt.
            with mud.connect(timeout=120) as a:
                login(a, "Zorderhero", PW)
                a.sync("scroll 0")
                b = stale_attempt("203.0.113.95", 52001)
                a.must(f"password {PW} Zneworder2", "Ok")
                a.send("quit")
                self.assertTrue(a.wait_closed())
            with b:
                b.send(PW)
                b.expect("Wrong password", timeout=20)
                self.assertTrue(b.wait_closed())

            # A changes it and stays: the old one takes nothing over.
            with mud.connect(timeout=120) as a:
                login(a, "Zorderhero", "Zneworder2")
                a.sync("scroll 0")
                b = stale_attempt("203.0.113.96", 52002)
                # A password differs only in its first eight characters.
                a.must("password Zneworder2 Zfreshpw3", "Ok")
                with b:
                    b.send("Zneworder2")
                    got = b.expect("Wrong password", "connect anyway", timeout=20)
                    self.assertIn("Wrong password", got)
                self.assertIn("Zorderhero", a.must("score", "Zorderhero"), "A still plays")

            record = (log / "player_addresses.tsv").read_text(encoding="latin-1") \
                if (log / "player_addresses.tsv").exists() else ""
        self.assertNotIn("203.0.113.95", record, "a refused login trusts no address")
        self.assertNotIn("203.0.113.96", record)

    def test_a_flood_is_refused(self) -> None:
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_FLOOD": "4", "TOC_GUARD_BURST": "50"}
        with LiveMud(extra_env=env) as mud:
            greeted = refused = 0
            for _ in range(7):
                if greets(mud):
                    greeted += 1
                else:
                    refused += 1
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        # The harness's own wait for the port is a connection too, so the
        # fourth of the minute may come one probe sooner.
        self.assertIn(greeted, (2, 3))
        self.assertEqual(greeted + refused, 7)
        self.assertGreaterEqual(refused, 4, "refused, and it stays refused")
        self.assertRegex(log, r"Connection guard: 127\.0\.0\.1 refused for 60 minutes")

    def test_the_game_wide_waiting_budget_spares_players(self) -> None:
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_GLOBAL_PENDING": "2",
               "TOC_GUARD_STRIKES": "50", "TOC_GUARD_BURST": "50"}
        with LiveMud(extra_env=env) as mud:
            held = [mud.connect(timeout=30), mud.connect(timeout=30)]
            try:
                for client in held:
                    client.expect("by what name", "name:")
                with mud.connect(timeout=30) as third:
                    got = third.expect("by what name", "very busy", timeout=20)
                    self.assertIn("very busy", got)
                    self.assertTrue(third.wait_closed())
            finally:
                for client in held:
                    client.close()
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("connections are waiting at the login prompts", log)

    def test_a_client_left_open_never_strikes(self) -> None:
        env = {"TOC_GUARD_LOOPBACK": "1", "TOC_GUARD_STRIKES": "2", "TOC_LOGIN_IDLE_SECS": "2"}
        with LiveMud(extra_env=env) as mud:
            for _ in range(3):                   # walked away; the prompt timed out
                with mud.connect(timeout=30) as idle:
                    idle.expect("by what name", "name:")
                    self.assertTrue(idle.wait_closed(timeout=20))
            with mud.connect(timeout=30) as client:
                client.expect("by what name", "name:")
                client.send("Zguardfresh")
                client.expect("Did I get", timeout=20)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertNotIn("Connection guard: 127.0.0.1 paused", log)

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
        self.assertNotIn("Connection guard: 127.0.0.1 paused", log)

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
