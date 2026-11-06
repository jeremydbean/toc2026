"""Brute-force login throttling, played against a real server.

Since 2026-11-06 (src/loginlock.c; owner: "if the wrong password is entered
over x times I want to ban the IP for x time, increasing with warning"):
every wrong password says how many more are allowed and how long the
lockout will be; five in fifteen minutes lock the address out for fifteen
minutes, then an hour, six hours, a day and a week for each lockout in a
week (a player's address an hour at most); lockouts survive a reboot;
logging into one's own character between guesses at another's resets
nothing; and a character hears of wrong passwords tried on them, staff of
ten in an hour. TOC_LOGIN_LOCK_SECS shrinks the ladder for these tests.


These were the timing-sensitive part of tests/test_live_gameplay.py: the
throttle counts failures inside a window measured against the wall clock,
so a dozen servers competing for the same cores made attempts miss it and
time out waiting for "wrong password". They get a runner to themselves
(SERIAL_MODULES in .github/workflows/validate.yml); the rest of that module
no longer has to wait with them, and runs in the ordinary shards.
"""

from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]

SKIP = skip_reason()


@unittest.skipIf(SKIP is not None, SKIP or "")
class LoginThrottleTests(unittest.TestCase):
    """Brute-force throttling.

    Loopback is exempt by default because the browser client bridges through
    the dashboard, so every web player shares 127.0.0.1 and throttling it
    would let one fumbled web login lock out all of them.
    TOC_THROTTLE_LOOPBACK=1 opts loopback in so this can be tested at all.
    """

    THROTTLED_ENV = {"TOC_THROTTLE_LOOPBACK": "1"}

    def _make_character(self, mud, name: str, password: str) -> None:
        with mud.connect() as client:
            create_character(client, name, password)
            client.command("save", settle=2.0)
            client.command("quit", settle=2.0)

    def _attempt(self, mud, name: str, password: str) -> str:
        """One full login attempt. Returns the transcript.

        Waits for a definite outcome rather than draining for a fixed time:
        under full-suite load the server can take longer than any fixed
        window to answer, which made this flaky. The timeouts are generous
        for the same reason -- each of these attempts is a fresh connection
        to a freshly booted world, and the suite runs several servers.
        """
        with mud.connect(timeout=90) as client:
            first = client.expect(
                "by what name", "too many failed login", timeout=90
            )
            if first == "too many failed login":
                return client.transcript
            client.send(name)
            client.expect("password", timeout=90)
            client.send(password)
            client.expect("wrong password", "mv>", timeout=90)
            return client.transcript

    def test_repeated_wrong_passwords_eventually_refuse_the_address(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestfive", "harnesspw")

            # Threshold is 5 failures; none of those should be refused outright.
            for attempt in range(5):
                transcript = self._attempt(mud, "Ziptestfive", "wrongpassword")
                with self.subTest(attempt=attempt):
                    self.assertIn("Wrong password", transcript)

            # The next connection is refused before the greeting.
            with mud.connect() as client:
                client.expect("too many failed login")
                self.assertNotIn("By what name", client.transcript)

    def test_a_successful_login_clears_the_failure_history(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestsix", "harnesspw")

            # Four failures: one short of the threshold.
            for _ in range(4):
                self.assertIn(
                    "Wrong password",
                    self._attempt(mud, "Ziptestsix", "wrongpassword"),
                )

            # A correct login must reset the counter.
            with mud.connect() as client:
                login(client, "Ziptestsix", "harnesspw")
                client.command("quit", settle=2.0)

            # So four more failures still must not trip the block.
            for _ in range(4):
                self.assertIn(
                    "Wrong password",
                    self._attempt(mud, "Ziptestsix", "wrongpassword"),
                )

            with mud.connect() as client:
                client.expect("by what name")

    def test_loopback_is_exempt_without_the_opt_in(self) -> None:
        """Default config must never throttle the shared web-bridge address."""
        with LiveMud() as mud:
            self._make_character(mud, "Ziptestseven", "harnesspw")

            for _ in range(8):
                self._attempt(mud, "Ziptestseven", "wrongpassword")

            with mud.connect() as client:
                client.expect("by what name")
                self.assertNotIn("Too many failed login", client.transcript)


    def test_every_wrong_password_warns_what_comes_next(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestwarn", "harnesspw")
            first = self._attempt(mud, "Ziptestwarn", "wrongpassword")
            self.assertIn("4 more wrong passwords from your address within 15 minutes and it "
                          "is locked out for 15 minutes.", first)
            for _ in range(3):
                last = self._attempt(mud, "Ziptestwarn", "wrongpassword")
            self.assertIn("1 more wrong password from your address", last)
            fifth = self._attempt(mud, "Ziptestwarn", "wrongpassword")
            self.assertIn("your address is locked out for 15 minutes", fifth)

    def test_lockouts_grow_and_outlast_a_reboot(self) -> None:
        env = dict(self.THROTTLED_ENV, TOC_LOGIN_LOCK_SECS="2")   # 2s, 8s, 48s...
        with LiveMud(extra_env=env) as mud:
            self._make_character(mud, "Ziptestgrow", "harnesspw")
            for _ in range(5):
                said = self._attempt(mud, "Ziptestgrow", "wrongpassword")
            self.assertIn("locked out for 2 seconds", said)
            time.sleep(3)                       # the first lockout ends
            for _ in range(5):
                said = self._attempt(mud, "Ziptestgrow", "wrongpassword")
            self.assertIn("locked out for 8 seconds", said, "the second is longer")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("locked out for 8 seconds (5 wrong passwords; lockout 2 this week)", log)

            mud.restart()
            with mud.connect() as client:
                client.expect("too many failed login", timeout=60)
            self.assertTrue((mud.root / "log" / "login_lockouts.tsv").exists())

    def test_logging_in_as_yourself_does_not_reset_guesses_at_another(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestmine", "harnesspw")
            self._make_character(mud, "Ziptestyours", "harnesspw")
            for _ in range(4):
                self._attempt(mud, "Ziptestyours", "wrongpassword")
            with mud.connect() as client:          # the guesser's own character
                login(client, "Ziptestmine", "harnesspw")
                client.command("quit", settle=2.0)
            said = self._attempt(mud, "Ziptestyours", "wrongpassword")
            self.assertIn("your address is locked out", said)

    def test_a_character_hears_of_guesses_and_staff_of_many(self) -> None:
        env = dict(self.THROTTLED_ENV, TOC_LOGIN_LOCK_SECS="1")
        with LiveMud(extra_env=env) as mud:
            self._make_character(mud, "Ziptestwatch", "harnesspw")
            self._make_character(mud, "Ziptestprey", "harnesspw")
            patch_player_file(mud, "Ziptestwatch", Levl=70)
            # Ten wrong passwords in an hour on one character: five, wait
            # out the lockout, five more.
            for batch in range(2):
                for _ in range(5):
                    self._attempt(mud, "Ziptestprey", "wrongpassword")
                time.sleep(5 if batch == 0 else 0)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertRegex(log, r"10 wrong passwords for Ziptestprey in the last hour, from 1 address")
            time.sleep(5)
            with mud.connect() as client:
                login(client, "Ziptestprey", "harnesspw")
                client.drain(1.0)
                self.assertRegex(client.transcript,
                                 r"10 failed password attempts were made on your character since "
                                 r"you last logged in, from 1 address\.")
                self.assertIn("choose a new password", client.transcript)
                client.command("quit", settle=2.0)
            with mud.connect() as client:          # told once
                login(client, "Ziptestprey", "harnesspw")
                client.drain(1.0)
                self.assertNotIn("made on your character", client.transcript)

    def test_a_players_address_is_locked_an_hour_at_most(self) -> None:
        # 1s, 4s, 24s... and a player's address capped at the hour, which
        # scales to 4s: the third lockout is 4 seconds, not 24.
        env = dict(self.THROTTLED_ENV, TOC_LOGIN_LOCK_SECS="1", TOC_GUARD_LOOPBACK="1")
        with LiveMud(extra_env=env) as mud:
            self._make_character(mud, "Ziptestcap", "harnesspw")
            with mud.connect() as client:          # a player's address now
                login(client, "Ziptestcap", "harnesspw")
                client.command("quit", settle=2.0)
            said = ""
            for wait in (2, 5, 0):
                for _ in range(5):
                    said = self._attempt(mud, "Ziptestcap", "wrongpassword")
                time.sleep(wait)
            self.assertIn("locked out for 4 seconds", said)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("lockout 3 this week; a player's address, so an hour at most", log)


class LoginLockSourceTests(unittest.TestCase):
    def test_every_wrong_password_goes_through_the_lockout(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertEqual(comm.count("login_wrong_password( d, ch )"), 3)
        self.assertNotIn("login_note_failure", comm)
        self.assertNotIn('"Wrong password.\\n\\r"', comm)
        self.assertEqual(comm.count("login_lock_refusal( "), 2)
        lock = (ROOT / "src" / "loginlock.c").read_text(encoding="latin-1")
        self.assertIn("{ 900, 3600, 6 * 3600, 86400, 7 * 86400 }", lock)
        self.assertIn("#define LOCK_TRUSTED_MAX    3600", lock)


if __name__ == "__main__":
    unittest.main()
