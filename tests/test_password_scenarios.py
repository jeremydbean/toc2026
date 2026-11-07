"""Every way a player meets the move to SHA-512 (owner, 2026-11-07).

"We need to test every combination of things. Existing players who fail to
log in before converting. Existing players who do. Disconnect. Reconnect.
Sign out. Sign in again. Do something else weird immediately. Etc."

Each character here starts as a player from before the change: created,
then given an old DES hash of a known password, offline. The rule every
scenario holds to is the one the move promises -- whatever DES let in
still gets in, nothing else does, and the hash moves exactly once:

- wrong passwords before the move change nothing, count toward the
  lockout as ever, and a lockout neither moves nor loses the hash;
- a connection dropped at the MOTD, before the character is in the game,
  saves nothing: the file keeps DES, and the next login moves it;
- dropping the link in the game, reconnecting (with the whole password or
  its first eight), "connect anyway", two logins racing, quitting at once,
  typing through the MOTD, a restart -- none moves it twice or loses it;
- DELETE, PKILL and PASSWORD take the old password as DES did; a new
  password from PASSWORD or RESETPWD counts every character;
- spaces and symbols in a password are read as they always were.

Synthetic Z fixtures in throwaway worlds; tests/test_password.py holds the
module itself to libxcrypt and plays the simple paths.
"""

from __future__ import annotations

import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
from test_password import des_hash, set_pass, stored_pass

SKIP = skip_reason()
NOTICE = "now kept with stronger encryption"


def quit_out(client) -> None:
    client.sync("save")
    client.send("quit")
    assert client.wait_closed(30), "quit did not close the connection"


def make_legacy(mud: LiveMud, name: str, password: str, **fields) -> str:
    """A character from before the change, offline, with a DES hash."""
    with mud.connect() as client:
        create_character(client, name, "Zthrowaway1")
        quit_out(client)
    if fields:
        patch_player_file(mud, name, **fields)
    des = des_hash(password, name[:2])
    set_pass(mud, name, des)
    return des


def try_password(mud: LiveMud, name: str, password: str) -> str:
    """One attempt that stops at the outcome: 'wrong', 'locked', 'in'
    (the character is let in and the connection quits again) or
    'playing' (connect anyway asked, answered no)."""
    with mud.connect(timeout=60) as client:
        first = client.expect("by what name", "too many failed login", timeout=60)
        if first == "too many failed login":
            return "locked"
        client.send(name)
        client.expect("password", timeout=60)
        client.send(password)
        said = client.expect("wrong password", "connect anyway", "[hit return",
                             "press enter", "mv>", "reconnecting", timeout=60)
        if said == "wrong password":
            assert client.wait_closed(30)
            return "wrong"
        if said == "connect anyway":
            client.send("N")
            return "playing"
        client.send("")
        client.sync("time")
        quit_out(client)
        return "in"


def login_and_quit(mud: LiveMud, name: str, password: str) -> str:
    with mud.connect() as client:
        login(client, name, password)
        client.sync("time")
        transcript = client.transcript
        quit_out(client)
    return transcript


@unittest.skipIf(SKIP is not None, SKIP or "")
class PasswordScenarioTests(unittest.TestCase):

    def test_failures_and_a_lockout_before_and_after_the_move(self) -> None:
        env = {"TOC_THROTTLE_LOOPBACK": "1", "TOC_LOGIN_LOCK_SECS": "2"}
        with LiveMud(extra_env=env) as mud:
            des = make_legacy(mud, "Zscfail", "Zfailpassw0rd")

            # Wrong, then nothing at all: refused, counted, nothing moved.
            self.assertEqual(try_password(mud, "Zscfail", "Zfailpassw0rx"[:7] + "q"), "wrong")
            self.assertEqual(try_password(mud, "Zscfail", ""), "wrong")
            self.assertEqual(try_password(mud, "Zscfail", "zfailpassw0rd"), "wrong")
            self.assertEqual(stored_pass(mud, "Zscfail"), des)

            # The right one: in, told of the move and of the failures.
            first = login_and_quit(mud, "Zscfail", "Zfailpassw0rd")
            self.assertIn(NOTICE, first)
            self.assertIn("failed password attempts were made on your character", first)
            moved = stored_pass(mud, "Zscfail")
            self.assertTrue(moved.startswith("$6$.8"), moved)

            # Locked out after the move: the lockout keeps the hash.
            for _ in range(5):
                self.assertEqual(try_password(mud, "Zscfail", "Zwrongpass"), "wrong")
            self.assertEqual(try_password(mud, "Zscfail", "Zfailpassw0rd"), "locked")
            self.assertEqual(stored_pass(mud, "Zscfail"), moved)
            time.sleep(3)                                   # the 2-second lockout ends
            later = login_and_quit(mud, "Zscfail", "Zfailpas")
            self.assertNotIn(NOTICE, later)
            self.assertEqual(stored_pass(mud, "Zscfail"), moved, "moved once")

            # Locked out before the move: a second old character.
            des2 = make_legacy(mud, "Zsclock", "Zlockedpass1")
            for _ in range(5):
                try_password(mud, "Zsclock", "Zwrongpass")
            self.assertEqual(try_password(mud, "Zsclock", "Zlockedpass1"), "locked")
            self.assertEqual(stored_pass(mud, "Zsclock"), des2)
            time.sleep(3)
            self.assertIn(NOTICE, login_and_quit(mud, "Zsclock", "Zlockedpass1"))
            self.assertTrue(stored_pass(mud, "Zsclock").startswith("$6$.8"))

    def test_disconnects_reconnects_and_quitting_at_once(self) -> None:
        with LiveMud() as mud:
            des = make_legacy(mud, "Zscdrop", "Zdroppassword")

            # Dropped at the MOTD, before the game: nothing is saved.
            with mud.connect() as client:
                client.expect("by what name")
                client.send("Zscdrop")
                client.expect("password")
                client.send("Zdroppassword")
                client.expect("[hit return", "press enter", "motd", "welcome", timeout=30)
            time.sleep(1.5)
            self.assertEqual(stored_pass(mud, "Zscdrop"), des, "a login never finished moves nothing")

            # The next login moves it, and says so.
            client = mud.connect()
            login(client, "Zscdrop", "Zdroppa" + "ss")      # the first eight
            self.assertIn(NOTICE, client.transcript)
            client.sync("time")
            moved = stored_pass(mud, "Zscdrop")
            self.assertTrue(moved.startswith("$6$.8"), moved)

            # Drop the link in the game, reconnect with the whole password.
            client.close()
            time.sleep(1.5)
            with mud.connect() as again:
                login(again, "Zscdrop", "Zdroppassword")
                self.assertIn("reconnecting", again.transcript.lower())
                self.assertNotIn(NOTICE, again.transcript)
                again.sync("time")
                again.close()                               # and drop it again
            time.sleep(1.5)
            # Reconnect with the first eight and something after them.
            with mud.connect() as again:
                login(again, "Zscdrop", "ZdroppasXYZ")
                self.assertIn("reconnecting", again.transcript.lower())
                quit_out(again)
            self.assertEqual(stored_pass(mud, "Zscdrop"), moved)

            # In and straight out again: the quit typed with nothing between.
            with mud.connect() as client:
                login(client, "Zscdrop", "Zdroppassword")
                client.send("quit")
                self.assertTrue(client.wait_closed(30))
            self.assertEqual(stored_pass(mud, "Zscdrop"), moved)

            # A second old character typing straight through the MOTD into
            # a quit, never waiting for anything.
            make_legacy(mud, "Zscrush", "Zrushpassword")
            with mud.connect() as client:
                client.expect("by what name")
                client.send("Zscrush")
                client.expect("password")
                client.send("Zrushpassword")
                client.send("")
                client.send("")
                client.send("quit")
                self.assertTrue(client.wait_closed(30), "never got out")
            rushed = stored_pass(mud, "Zscrush")
            self.assertTrue(rushed.startswith("$6$.8"), rushed)
            self.assertNotIn(NOTICE, login_and_quit(mud, "Zscrush", "Zrushpas"))
            self.assertEqual(stored_pass(mud, "Zscrush"), rushed)

            # Sign out, sign in again, through a restart.
            mud.restart()
            self.assertEqual(try_password(mud, "Zscdrop", "Zdroppassword"), "in")
            self.assertEqual(try_password(mud, "Zscdrop", "Zdroppas"), "in")
            self.assertEqual(try_password(mud, "Zscdrop", "Zdroppaz"), "wrong")
            self.assertEqual(stored_pass(mud, "Zscdrop"), moved)

    def test_connect_anyway_and_two_logins_racing(self) -> None:
        with LiveMud() as mud:
            make_legacy(mud, "Zscdual", "Zdualpassw0rd")

            # Playing on one connection; another says "connect anyway".
            first = mud.connect()
            login(first, "Zscdual", "Zdualpassw0rd")
            self.assertIn(NOTICE, first.transcript)
            first.sync("time")
            moved = stored_pass(mud, "Zscdual")
            with mud.connect() as second:
                login(second, "Zscdual", "Zdualpas")        # login() answers Y
                self.assertNotIn(NOTICE, second.transcript)
                second.sync("time")
                quit_out(second)
            first.close()
            self.assertEqual(stored_pass(mud, "Zscdual"), moved)

            # Two logins racing: the second is at the password prompt with
            # the old file read when the first finishes and moves it.
            des = make_legacy(mud, "Zscrace", "Zracepassword")
            slow = mud.connect()
            slow.expect("by what name")
            slow.send("Zscrace")
            slow.expect("password")                         # holds the DES copy
            fast = mud.connect()
            login(fast, "Zscrace", "Zracepassword")
            self.assertIn(NOTICE, fast.transcript)
            fast.sync("time")
            moved = stored_pass(mud, "Zscrace")
            self.assertNotEqual(moved, des)
            slow.send("Zracepas")                           # the first eight
            said = slow.expect("connect anyway", "wrong password", timeout=30)
            self.assertEqual(said, "connect anyway")
            slow.send("Y")
            slow.expect("reconnecting", timeout=30)
            self.assertNotIn(NOTICE, slow.transcript)
            slow.sync("time")
            quit_out(slow)
            fast.close()
            self.assertEqual(stored_pass(mud, "Zscrace"), moved, "moved once, by the first")

            # The racer whose password is wrong is refused by the character
            # in the game, whatever the old file said.
            slow = mud.connect()
            slow.expect("by what name")
            slow.send("Zscrace")
            slow.expect("password")
            slow.send("Zracepaz")
            self.assertEqual(slow.expect("wrong password", "connect anyway", timeout=30), "wrong password")
            slow.close()

            # A second connection while the first sits at the MOTD, moved in
            # memory but not yet saved.
            des = make_legacy(mud, "Zscmotd", "Zmotdpassword")
            waiting = mud.connect()
            waiting.expect("by what name")
            waiting.send("Zscmotd")
            waiting.expect("password")
            waiting.send("Zmotdpassword")
            waiting.expect("[hit return", "press enter", "motd", "welcome", timeout=30)
            other = mud.connect()
            other.expect("by what name")
            other.send("Zscmotd")
            other.expect("password")
            other.send("Zmotdpassword")
            said = other.expect("connect anyway", "[hit return", "press enter", timeout=30)
            if said == "connect anyway":
                other.send("Y")
                other.drain(2.0)
            waiting.close()
            other.close()
            time.sleep(1.5)
            # Whatever either got to, the character logs in after and the
            # hash is DES or moved -- never anything else.
            self.assertEqual(try_password(mud, "Zscmotd", "Zmotdpas"), "in")
            final = stored_pass(mud, "Zscmotd")
            self.assertTrue(final.startswith("$6$.8"), final)
            self.assertEqual(try_password(mud, "Zscmotd", "Zmotdpaz"), "wrong")

    def test_commands_that_ask_for_the_password(self) -> None:
        with LiveMud() as mud:
            # PKILL and PASSWORD take the old password as DES did.
            make_legacy(mud, "Zsccmd", "Zcmdpassword1", Levl=15)
            with mud.connect() as client:
                login(client, "Zsccmd", "Zcmdpass")
                self.assertIn(NOTICE, client.transcript)
                client.must("pkill Zcmdpass", "You are now a PKILLER")
                client.must("password Zcmdpassword1 Znewpassword12", "Ok.")
                quit_out(client)
            new = stored_pass(mud, "Zsccmd")
            self.assertTrue(new.startswith("$6$") and not new.startswith("$6$.8"), new)
            self.assertEqual(try_password(mud, "Zsccmd", "Znewpass"), "wrong")
            self.assertEqual(try_password(mud, "Zsccmd", "Zcmdpassword1"), "wrong")
            mud.restart()
            self.assertEqual(try_password(mud, "Zsccmd", "Znewpassword12"), "in")
            with mud.connect() as client:
                login(client, "Zsccmd", "Znewpassword12")
                reply = client.must("password Znewpass Zother12345", "Wrong password")
                self.assertIn("Wrong password", reply)
                quit_out(client)
            self.assertEqual(stored_pass(mud, "Zsccmd"), new)

            # DELETE: a wrong password cancels; the first eight confirm.
            make_legacy(mud, "Zscdel", "Zdelpassword")
            with mud.connect() as client:
                login(client, "Zscdel", "Zdelpassword")
                client.must("delete", "password to confirm")
                client.must("delete Zdelpasz", "Delete cancelled")
                client.must("delete", "password to confirm")
                client.send("delete Zdelpass")
                self.assertTrue(client.wait_closed(30))
            self.assertFalse((mud.player_dir / "Zscdel").exists(), "deleted")

            # RESETPWD on an old character, offline: every character counts.
            make_legacy(mud, "Zscstaff", "Zstaffpass1", Levl=70)
            make_legacy(mud, "Zscreset", "Zresetpass1")
            with mud.connect() as staff:
                login(staff, "Zscstaff", "Zstaffpass1")
                staff.must("resetpwd zscreset Zbrandnew99", "has been reset")
                quit_out(staff)
            reset = stored_pass(mud, "Zscreset")
            self.assertTrue(reset.startswith("$6$") and not reset.startswith("$6$.8"), reset)
            self.assertEqual(try_password(mud, "Zscreset", "Zresetpass1"), "wrong")
            self.assertEqual(try_password(mud, "Zscreset", "Zbrandne"), "wrong")
            self.assertNotIn(NOTICE, login_and_quit(mud, "Zscreset", "Zbrandnew99"))

    def test_spaces_and_symbols_read_as_they_always_were(self) -> None:
        with LiveMud() as mud:
            make_legacy(mud, "Zscspace", "Zab cd efgh")
            self.assertIn(NOTICE, login_and_quit(mud, "Zscspace", "Zab cd efgh"))
            self.assertEqual(try_password(mud, "Zscspace", "Zab cd e"), "in")
            self.assertEqual(try_password(mud, "Zscspace", "Zab cd ezzz"), "in")
            self.assertEqual(try_password(mud, "Zscspace", "Zab cd"), "wrong")
            self.assertEqual(try_password(mud, "Zscspace", "Zabcdefgh"), "wrong")

            make_legacy(mud, "Zscsym", "Z!@#$%^&*()")
            self.assertIn(NOTICE, login_and_quit(mud, "Zscsym", "Z!@#$%^&*()"))
            self.assertEqual(try_password(mud, "Zscsym", "Z!@#$%^&"), "in")
            self.assertEqual(try_password(mud, "Zscsym", "Z!@#$%^*"), "wrong")

            # A short old password (five characters, the least the game took).
            make_legacy(mud, "Zscshort", "Zab12")
            self.assertIn(NOTICE, login_and_quit(mud, "Zscshort", "Zab12"))
            self.assertEqual(try_password(mud, "Zscshort", "Zab12"), "in")
            self.assertEqual(try_password(mud, "Zscshort", "Zab123"), "wrong")
            self.assertEqual(try_password(mud, "Zscshort", "Zab1"), "wrong")


if __name__ == "__main__":
    unittest.main()
