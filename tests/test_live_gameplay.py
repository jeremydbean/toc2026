"""End-to-end tests that play the real game over Telnet.

Every other test in this suite asserts on source text. These boot an actual
server, connect a socket, create a character, and play, which is the only
layer that catches a change that compiles and reads correctly but does not
work. Data is isolated in a temporary tree; see tests/live_mud.py.

Skipped automatically when there is no built binary or on Windows, where the
game is not natively runnable. Run them from WSL, Linux, macOS, or CI.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, skip_reason


SKIP = skip_reason()


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveGameplayTests(unittest.TestCase):
    def test_server_boots_and_greets(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            client.expect("by what name")
            self.assertIn("DikuMUD", client.transcript)

    def test_character_creation_reaches_the_game(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            create_character(client, "Ziptestone", "harnesspw")

            # A newly created character should be able to look around.
            output = client.command("look", settle=1.5)
            self.assertTrue(
                output.strip(),
                f"`look` produced nothing.\n{client.transcript[-2000:]}",
            )

            # And the character file should exist in the throwaway tree, not
            # anywhere near real player data.
            client.command("save", settle=1.5)
            self.assertTrue(
                (mud.player_dir / "Ziptestone").is_file(),
                f"no pfile written; player dir holds "
                f"{[p.name for p in mud.player_dir.iterdir()]}",
            )

    def test_core_commands_respond(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            create_character(client, "Ziptesttwo", "harnesspw")

            for command, expected in (
                ("score", "level"),
                ("inventory", "carrying"),
                ("commands", "commands"),
            ):
                with self.subTest(command=command):
                    output = client.command(command, settle=1.5).lower()
                    self.assertIn(
                        expected,
                        output,
                        f"`{command}` output lacked {expected!r}: {output[-600:]}",
                    )

    def test_character_persists_across_a_reconnect(self) -> None:
        with LiveMud() as mud:
            with mud.connect() as client:
                create_character(client, "Ziptestthree", "harnesspw")
                client.command("save", settle=2.0)
                client.command("quit", settle=2.0)

            # Reconnect with the same credentials.
            with mud.connect() as client:
                client.expect("by what name")
                client.send("Ziptestthree")
                client.expect("password")
                client.send("harnesspw")
                client.drain(2.5)
                self.assertNotIn("Wrong password", client.transcript)

                output = client.command("score", settle=2.0).lower()
                self.assertIn("level", output)

    def test_wrong_password_is_rejected(self) -> None:
        with LiveMud() as mud:
            with mud.connect() as client:
                create_character(client, "Ziptestfour", "harnesspw")
                client.command("save", settle=2.0)
                client.command("quit", settle=2.0)

            with mud.connect() as client:
                client.expect("by what name")
                client.send("Ziptestfour")
                client.expect("password")
                client.send("definitelywrong")
                client.drain(2.0)
                self.assertIn("Wrong password", client.transcript)


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
        """One full login attempt. Returns the transcript."""
        with mud.connect() as client:
            first = client.expect("by what name", "too many failed login")
            if first == "too many failed login":
                return client.transcript
            client.send(name)
            client.expect("password")
            client.send(password)
            client.drain(1.0)
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
                client.expect("by what name")
                client.send("Ziptestsix")
                client.expect("password")
                client.send("harnesspw")
                client.drain(2.0)
                self.assertNotIn("Wrong password", client.transcript)
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
