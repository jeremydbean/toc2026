"""Brute-force login throttling, played against a real server.

These were the timing-sensitive part of tests/test_live_gameplay.py: the
throttle counts failures inside a window measured against the wall clock,
so a dozen servers competing for the same cores made attempts miss it and
time out waiting for "wrong password". They get a runner to themselves
(SERIAL_MODULES in .github/workflows/validate.yml); the rest of that module
no longer has to wait with them, and runs in the ordinary shards.
"""

from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, skip_reason

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


if __name__ == "__main__":
    unittest.main()
